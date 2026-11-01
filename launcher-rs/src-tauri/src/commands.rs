//! Tauri commands: the only bridge between the React UI and the Rust core.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use chrono::Local;
use serde::Serialize;
use serde_json::{Value, json};
use tauri::{AppHandle, Manager, State};
use tokio::sync::Mutex;

use crate::api::ApiClient;
use crate::boxes;
use crate::config::{self, AccountEntry, ConfigView, LauncherConfig};
use crate::control::{ControlClient, InstanceManager, InstanceView, OnlineRoster};
use crate::display::{self, GameDisplay, WindowMode};
use crate::error::{AppError, AppResult};
use crate::game;
use crate::gear::{self, GearItem, JobInfo};
use crate::gear_stats;
use crate::icons;

pub struct AppState {
    pub config: Mutex<LauncherConfig>,
    pub instances: Mutex<InstanceManager>,
    /// One remote helper run at a time: it restarts every target box and takes tens of seconds.
    pub remote: Mutex<()>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            config: Mutex::new(LauncherConfig::load()),
            instances: Mutex::new(InstanceManager::new()),
            remote: Mutex::new(()),
        }
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionView {
    pub account: Value,
    pub characters: Vec<Value>,
    pub token_expires_at: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicView {
    pub status: Option<Value>,
    pub news: Vec<Value>,
    pub error: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Bootstrap {
    pub config: ConfigView,
    pub session: Option<SessionView>,
    pub session_error: Option<String>,
    pub public: PublicView,
    pub repo_root: Option<String>,
    pub game_dir: Option<String>,
    pub host64: Option<String>,
    pub gearswap_dir: Option<String>,
    pub gearswap_config: Option<Value>,
    pub version: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FailedLaunch {
    pub account: String,
    pub error: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LaunchAllResult {
    pub launched: Vec<InstanceView>,
    pub failed: Vec<FailedLaunch>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TeamView {
    pub subs: Vec<Value>,
    pub limit: i64,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TeamMutation {
    pub sub: Value,
    pub limit: i64,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GearLibrary {
    pub path: String,
    pub sets: BTreeMap<String, BTreeMap<String, String>>,
    pub detailed: BTreeMap<String, BTreeMap<String, GearItem>>,
    pub job: Option<JobInfo>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GearSetResult {
    pub sets: BTreeMap<String, BTreeMap<String, String>>,
    pub path: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EquipIcons {
    /// item id (as a string) -> PNG data URL
    pub icons: BTreeMap<String, String>,
    /// ids the game had no icon for; the UI stops asking for them this session
    pub missing: Vec<u32>,
    /// why some icons could not be fetched (the cached ones are still in `icons`)
    pub error: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ResolvedItem {
    pub name: String,
    pub id: u32,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GearSaveResult {
    pub path: String,
    pub profile: String,
}

/// Where an edited set actually landed: a bundled job library is rewritten in place, an
/// imported one is not (`persistent` is false and the UI points at Save version instead).
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GearLibrarySaveResult {
    pub path: String,
    pub backup: Option<String>,
    pub persistent: bool,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GearVersion {
    pub name: String,
    pub path: String,
    pub saved_at: String,
    pub character: String,
    pub job: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GearDefaultFile {
    pub job: String,
    pub abbr: String,
    pub name: String,
    pub path: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GearDefaults {
    pub folder: String,
    pub files: Vec<GearDefaultFile>,
}

#[tauri::command]
pub async fn bootstrap(app: AppHandle, state: State<'_, AppState>) -> AppResult<Bootstrap> {
    let config = state.config.lock().await.clone();
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let public = fetch_public(&api).await;

    let mut session: Option<SessionView> = None;
    let mut session_error: Option<String> = None;
    if !config.token.is_empty() {
        match fetch_session(&api, &config.token, &config.token_expires_at).await {
            Ok(found) => {
                session = Some(found.clone());
                let mut locked = state.config.lock().await;
                if let Some(username) = found
                    .account
                    .get("username")
                    .and_then(Value::as_str)
                    .map(ToOwned::to_owned)
                {
                    locked.set_characters(&username, found.characters.clone());
                }
                let _ = locked.save();
            }
            Err(error) => {
                if error.status() == Some(401) {
                    let mut locked = state.config.lock().await;
                    locked.token.clear();
                    locked.token_expires_at.clear();
                    if let Some(index) = locked.account_index(&locked.username.clone()) {
                        locked.accounts[index].token.clear();
                    }
                    let _ = locked.save();
                    session_error = Some("the saved session expired; sign in again".to_string());
                } else {
                    session_error = Some(error.to_string());
                }
            }
        }
    }

    let gearswap_config = if !config.token.is_empty() {
        match api.gearswap_settings(&config.token).await {
            Ok(value) => value
                .get("config")
                .cloned()
                .filter(|value| value.is_object()),
            Err(_) => None,
        }
    } else {
        None
    };

    let repo = game::resolve_repo_root_for(&config);
    if config.repo_root.trim().is_empty() {
        if let Some(root) = repo.as_ref() {
            let mut locked = state.config.lock().await;
            locked.repo_root = root.to_string_lossy().into_owned();
            let _ = locked.save();
        }
    }
    let resource = app.path().resource_dir().ok();
    let game_dir = game::find_game_dir(&config.game_dir);
    let host64 = game::find_host64(&config);
    let gearswap = gear::defaults_dir(repo.as_deref(), resource.as_deref());

    let final_config = state.config.lock().await.clone();
    Ok(Bootstrap {
        config: ConfigView::from(&final_config),
        session,
        session_error,
        public,
        repo_root: repo.map(|path| path.to_string_lossy().into_owned()),
        game_dir: game_dir.map(|path| path.to_string_lossy().into_owned()),
        host64: host64.map(|path| path.to_string_lossy().into_owned()),
        gearswap_dir: gearswap.map(|path| path.to_string_lossy().into_owned()),
        gearswap_config,
        version: env!("CARGO_PKG_VERSION").to_string(),
    })
}

#[tauri::command]
pub async fn refresh_public(state: State<'_, AppState>) -> AppResult<PublicView> {
    let config = state.config.lock().await.clone();
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    Ok(fetch_public(&api).await)
}

#[tauri::command]
pub async fn get_config(state: State<'_, AppState>) -> AppResult<ConfigView> {
    let config = state.config.lock().await;
    Ok(ConfigView::from(&*config))
}

#[tauri::command]
pub async fn login(
    state: State<'_, AppState>,
    username: String,
    password: String,
    api_url: Option<String>,
) -> AppResult<SessionView> {
    let mut config = state.config.lock().await.clone();
    if let Some(url) = api_url.filter(|value| !value.trim().is_empty()) {
        let api = ApiClient::new(&url, config.api_insecure)?;
        let normalized = api.base().to_string();
        if normalized != config.api_url {
            config.accounts.clear();
            config.token.clear();
            config.token_expires_at.clear();
            config.username.clear();
            config.character_id = None;
            config.api_url = normalized;
        }
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let data = api.login(username.trim(), &password).await?;
    let token = data
        .get("token")
        .and_then(Value::as_str)
        .ok_or_else(|| AppError::Api {
            status: 500,
            code: "bad_reply".to_string(),
            message: "the server did not return a session token".to_string(),
        })?
        .to_string();
    let expires = data
        .get("expires_at")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    let account = data.get("account").cloned().unwrap_or(Value::Null);
    let characters = data
        .get("characters")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    config.remember_account(&account, &token, &expires, Some(characters.clone()));
    config.save()?;
    let mut locked = state.config.lock().await;
    *locked = config;
    Ok(SessionView {
        account,
        characters,
        token_expires_at: expires,
    })
}

#[tauri::command]
pub async fn register(
    state: State<'_, AppState>,
    username: String,
    password: String,
    email: Option<String>,
    api_url: Option<String>,
) -> AppResult<SessionView> {
    let mut config = state.config.lock().await.clone();
    if let Some(url) = api_url.filter(|value| !value.trim().is_empty()) {
        let api = ApiClient::new(&url, config.api_insecure)?;
        let normalized = api.base().to_string();
        if normalized != config.api_url {
            config.accounts.clear();
            config.token.clear();
            config.token_expires_at.clear();
            config.username.clear();
            config.character_id = None;
            config.api_url = normalized;
        }
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let data = api
        .register(
            username.trim(),
            &password,
            email.as_deref().filter(|value| !value.trim().is_empty()),
        )
        .await?;
    let token = data
        .get("token")
        .and_then(Value::as_str)
        .ok_or_else(|| AppError::Api {
            status: 500,
            code: "bad_reply".to_string(),
            message: "the server did not return a session token".to_string(),
        })?
        .to_string();
    let expires = data
        .get("expires_at")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    let account = data.get("account").cloned().unwrap_or(Value::Null);
    let characters = api.characters(&token).await.unwrap_or_default();
    config.remember_account(&account, &token, &expires, Some(characters.clone()));
    config.save()?;
    let mut locked = state.config.lock().await;
    *locked = config;
    Ok(SessionView {
        account,
        characters,
        token_expires_at: expires,
    })
}

#[tauri::command]
pub async fn logout(state: State<'_, AppState>) -> AppResult<ConfigView> {
    let config = state.config.lock().await.clone();
    if !config.token.is_empty() {
        if let Ok(api) = ApiClient::new(&config.api_url, config.api_insecure) {
            let _ = api.logout(&config.token).await;
        }
    }
    let mut locked = state.config.lock().await;
    if config.username.is_empty() {
        locked.clear_session();
    } else {
        locked.forget_account(&config.username);
    }
    locked.save()?;
    Ok(ConfigView::from(&*locked))
}

#[tauri::command]
pub async fn switch_account(
    state: State<'_, AppState>,
    username: String,
) -> AppResult<SessionView> {
    let mut config = state.config.lock().await.clone();
    if !config.activate_account(&username) {
        return Err(AppError::Validation(format!(
            "@{username} is not saved in this launcher"
        )));
    }
    if config.token.is_empty() {
        return Err(AppError::Validation(format!(
            "@{username} needs to sign in again"
        )));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let session = fetch_session(&api, &config.token, &config.token_expires_at).await?;
    if let Some(name) = session.account.get("username").and_then(Value::as_str) {
        config.set_characters(name, session.characters.clone());
    }
    config.save()?;
    let mut locked = state.config.lock().await;
    *locked = config;
    Ok(session)
}

#[tauri::command]
pub async fn forget_account(state: State<'_, AppState>, username: String) -> AppResult<ConfigView> {
    let config = state.config.lock().await.clone();
    if let Some(entry) = config.account_entry(Some(&username)) {
        if !entry.token.is_empty() {
            if let Ok(api) = ApiClient::new(&config.api_url, config.api_insecure) {
                let _ = api.logout(&entry.token).await;
            }
        }
    }
    let mut locked = state.config.lock().await;
    locked.forget_account(&username);
    locked.save()?;
    Ok(ConfigView::from(&*locked))
}

#[tauri::command]
pub async fn create_character(state: State<'_, AppState>, data: Value) -> AppResult<SessionView> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let character = api.create_character(&config.token, data).await?;
    let characters = api
        .characters(&config.token)
        .await
        .unwrap_or_else(|_| vec![character.clone()]);
    let mut locked = state.config.lock().await;
    locked.set_characters(&config.username, characters.clone());
    let chosen =
        character_id_of(&character).or_else(|| characters.first().and_then(character_id_of));
    locked.set_character_id(&config.username, chosen);
    locked.save()?;
    let account = locked
        .account_entry(Some(&config.username))
        .map(|entry| {
            json!({
                "id": entry.account_id,
                "username": entry.username,
            })
        })
        .unwrap_or(Value::Null);
    Ok(SessionView {
        account,
        characters,
        token_expires_at: config.token_expires_at,
    })
}

#[tauri::command]
pub async fn save_character_design(
    state: State<'_, AppState>,
    character_id: i64,
    data: Value,
) -> AppResult<SessionView> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let character = api
        .save_character_design(&config.token, character_id, data)
        .await?;
    let characters = api
        .characters(&config.token)
        .await
        .unwrap_or_else(|_| vec![character.clone()]);
    let mut locked = state.config.lock().await;
    locked.set_characters(&config.username, characters.clone());
    locked.save()?;
    let account = locked
        .account_entry(Some(&config.username))
        .map(|entry| {
            json!({
                "id": entry.account_id,
                "username": entry.username,
            })
        })
        .unwrap_or(Value::Null);
    Ok(SessionView {
        account,
        characters,
        token_expires_at: config.token_expires_at,
    })
}

#[tauri::command]
pub async fn character_data(state: State<'_, AppState>, character_id: i64) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.character_data(&config.token, character_id).await
}

#[tauri::command]
pub async fn character_bags(state: State<'_, AppState>, character_id: i64) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.character_bags(&config.token, character_id).await
}

#[tauri::command]
pub async fn character_magic_bag(
    state: State<'_, AppState>,
    character_id: i64,
) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.character_magic_bag(&config.token, character_id).await
}

#[tauri::command]
pub async fn character_stats(state: State<'_, AppState>, character_id: i64) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.character_stats(&config.token, character_id).await
}

#[tauri::command]
pub async fn character_data_action(
    state: State<'_, AppState>,
    character_id: i64,
    action: String,
    payload: Option<Value>,
) -> AppResult<Value> {
    const ACTIONS: [&str; 12] = [
        "merits",
        "job-points",
        "mastery-rank",
        "gil",
        "home-points",
        "key-items",
        "mounts",
        "currencies",
        "armory",
        "items",
        "progress",
        "ascension",
    ];
    if !ACTIONS.contains(&action.as_str()) {
        return Err(AppError::Validation(format!(
            "unknown Data page action: {action}"
        )));
    }
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.character_action(
        &config.token,
        character_id,
        &action,
        payload.unwrap_or_else(|| json!({})),
    )
    .await
}

#[tauri::command]
pub async fn search_armory(
    state: State<'_, AppState>,
    character_id: i64,
    query: String,
    kind: Option<String>,
    scope: Option<String>,
    category: Option<String>,
) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.search_armory(
        &config.token,
        character_id,
        &query,
        kind.as_deref(),
        scope.as_deref(),
        category.as_deref(),
    )
    .await
}

#[tauri::command]
pub async fn character_warps(state: State<'_, AppState>, character_id: i64) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.character_warps(&config.token, character_id).await
}

#[tauri::command]
pub async fn character_warp_mark(
    state: State<'_, AppState>,
    character_id: i64,
    payload: Option<Value>,
) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.mark_character_warp(
        &config.token,
        character_id,
        payload.unwrap_or_else(|| json!({})),
    )
    .await
}

#[tauri::command]
pub async fn character_warp_rename(
    state: State<'_, AppState>,
    character_id: i64,
    slot: i64,
    alias: Option<String>,
) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.rename_character_warp(&config.token, character_id, slot, alias)
        .await
}

#[tauri::command]
pub async fn character_warp_delete(
    state: State<'_, AppState>,
    character_id: i64,
    slot: i64,
) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.delete_character_warp(&config.token, character_id, slot)
        .await
}

#[tauri::command]
pub async fn select_character(
    state: State<'_, AppState>,
    character_id: i64,
) -> AppResult<ConfigView> {
    let mut config = state.config.lock().await;
    let username = config.username.clone();
    config.set_character_id(&username, Some(character_id));
    config.save()?;
    Ok(ConfigView::from(&*config))
}

#[tauri::command]
pub async fn set_last_page(state: State<'_, AppState>, page: String) -> AppResult<()> {
    let mut config = state.config.lock().await;
    config.last_page = page;
    config.save()?;
    Ok(())
}

/// Remember the tenant bar's character in `launcher.json`, beside the active character and the
/// last page. The tenant may live on a sub-account, so this never touches `character_id`.
#[tauri::command]
pub async fn select_tenant(
    state: State<'_, AppState>,
    character_id: Option<i64>,
) -> AppResult<ConfigView> {
    let mut config = state.config.lock().await;
    config.tenant_character_id = character_id;
    config.save()?;
    Ok(ConfigView::from(&*config))
}

#[tauri::command]
pub async fn save_settings(
    app: AppHandle,
    state: State<'_, AppState>,
    api_url: String,
    game_dir: String,
    headless_game_dir: String,
    remote_ssh: String,
    repo_root: String,
    api_insecure: bool,
    auto_login: bool,
    limit_main_fps: bool,
    game_window_mode: WindowMode,
    game_width: u32,
    game_height: u32,
    game_ui_scale: f64,
    monitor: String,
) -> AppResult<ConfigView> {
    let mut config = state.config.lock().await;
    let display = GameDisplay {
        mode: game_window_mode,
        width: game_width,
        height: game_height,
        ui_scale: game_ui_scale,
    };
    display.validate()?;
    let normalized = ApiClient::new(&api_url, api_insecure)?.base().to_string();
    if normalized != config.api_url {
        config.accounts.clear();
        config.token.clear();
        config.token_expires_at.clear();
        config.username.clear();
        config.character_id = None;
    }
    config.api_url = normalized;
    config.game_dir = if game_dir.trim().is_empty() {
        String::new()
    } else {
        config::expand_home(game_dir.trim())
            .to_string_lossy()
            .into_owned()
    };
    config.headless_game_dir = if headless_game_dir.trim().is_empty() {
        String::new()
    } else {
        config::expand_home(headless_game_dir.trim())
            .to_string_lossy()
            .into_owned()
    };
    config.remote_ssh = remote_ssh.trim().to_string();
    config.repo_root = if repo_root.trim().is_empty() {
        String::new()
    } else {
        config::expand_home(repo_root.trim())
            .to_string_lossy()
            .into_owned()
    };
    config.api_insecure = api_insecure;
    config.auto_login = auto_login;
    config.limit_main_fps = limit_main_fps;
    config.game_display = display.sanitized();
    config.monitor = monitor.trim().to_string();
    config.save()?;
    let view = ConfigView::from(&*config);
    drop(config);
    // Show the choice now rather than at the next start: the window the player just asked to
    // move is the one in front of them. A display that is not attached leaves it where it is.
    if let Err(error) = display::place_launcher_window(&app, &view.monitor) {
        tracing::warn!(%error, "cannot move the launcher window to the chosen display");
    }
    Ok(view)
}

/// The displays attached to this machine. Settings lists them in the Display picker and uses the
/// chosen one's work area for "Fit this display" and to cap the resolution presets.
#[tauri::command]
pub fn display_info(app: AppHandle) -> display::DisplayInfo {
    display::info(&app)
}

#[tauri::command]
pub async fn detect_game_dir(configured: String) -> AppResult<Option<String>> {
    Ok(game::find_game_dir(&configured).map(|path| path.to_string_lossy().into_owned()))
}

#[tauri::command]
pub async fn find_host64(state: State<'_, AppState>) -> AppResult<Option<String>> {
    let config = state.config.lock().await.clone();
    Ok(game::find_host64(&config).map(|path| path.to_string_lossy().into_owned()))
}

#[tauri::command]
pub async fn defaults_dir(app: AppHandle, state: State<'_, AppState>) -> AppResult<Option<String>> {
    let config = state.config.lock().await.clone();
    let repo = game::resolve_repo_root_for(&config);
    if config.repo_root.trim().is_empty() {
        if let Some(root) = repo.as_ref() {
            let mut locked = state.config.lock().await;
            locked.repo_root = root.to_string_lossy().into_owned();
            let _ = locked.save();
        }
    }
    let resource = app.path().resource_dir().ok();
    Ok(gear::defaults_dir(repo.as_deref(), resource.as_deref())
        .map(|path| path.to_string_lossy().into_owned()))
}

#[tauri::command]
pub async fn build_game(
    app: AppHandle,
    state: State<'_, AppState>,
    game_dir: String,
) -> AppResult<game::BuildResult> {
    let config = state.config.lock().await.clone();
    let root = game::resolve_repo_root_for(&config).ok_or_else(|| {
        AppError::Config("the Fanxi checkout was not found; set it in Settings".into())
    })?;
    let folder = config::expand_home(&game_dir);
    let result = game::build_game(&app, &root, &folder).await?;
    let mut locked = state.config.lock().await;
    locked.host64 = result.host64.clone();
    locked.game_dir = folder.to_string_lossy().into_owned();
    locked.repo_root = root.to_string_lossy().into_owned();
    locked.save()?;
    Ok(result)
}

#[tauri::command]
pub async fn build_log() -> AppResult<Vec<String>> {
    Ok(game::build_log_tail(80))
}

#[tauri::command]
pub async fn open_data_dir() -> AppResult<()> {
    game::open_data_dir()
}

#[tauri::command]
pub async fn launch(
    state: State<'_, AppState>,
    account: String,
    character_id: Option<i64>,
) -> AppResult<InstanceView> {
    let config = state.config.lock().await.clone();
    let view = launch_with_config(&state, &config, &account, character_id).await?;
    // The player picks the character: the launcher waits for the client to come up and then
    // leaves the title, agreement and character-select screens alone. Boxes still drive them
    // with Enter (await_signin) because nobody is sitting at those clients.
    await_client_up(&view).await?;
    Ok(view)
}

/// Wait until the client answers on its control port, without touching its screens. The player
/// drives the title, agreement and character select; the Control and Gear pages show the client
/// as signing in until it reaches a zone.
async fn await_client_up(view: &InstanceView) -> AppResult<Value> {
    let client = ControlClient::new(view.port);
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(30);
    loop {
        if !boxes::pid_alive(view.pid) {
            return Err(AppError::Control(format!("{} exited", view.name)));
        }
        if let Ok(state) = client
            .call("state", json!({}), std::time::Duration::from_secs(2))
            .await
        {
            return Ok(state);
        }
        if tokio::time::Instant::now() >= deadline {
            return Err(AppError::Control(format!(
                "{} started but its control port did not answer",
                view.name
            )));
        }
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    }
}

async fn spawn_launch(
    state: &State<'_, AppState>,
    config: &LauncherConfig,
    account: &str,
    fallback_character: Value,
    data: &Value,
    headless: bool,
) -> AppResult<InstanceView> {
    let client = data.get("client").cloned().ok_or_else(|| AppError::Api {
        status: 500,
        code: "bad_reply".to_string(),
        message: "the server did not return a game client".to_string(),
    })?;
    let login_token = data
        .get("login_token")
        .and_then(Value::as_str)
        .ok_or_else(|| AppError::Api {
            status: 500,
            code: "bad_reply".to_string(),
            message: "the server did not return a launch token".to_string(),
        })?
        .to_string();
    let configured = if headless && !config.headless_game_dir.trim().is_empty() {
        config.headless_game_dir.as_str()
    } else {
        config.game_dir.as_str()
    };
    let game_dir = if !configured.trim().is_empty() {
        config::expand_home(configured)
    } else {
        game::find_game_dir("").ok_or_else(|| {
            AppError::Game("choose your FINAL FANTASY XI folder in Settings first".to_string())
        })?
    };
    if headless {
        if game::find_host64_headless(config).is_none() {
            return Err(AppError::Game(format!(
                "the headless host is not built yet; build it with {} host64-headless",
                game::build_driver()
            )));
        }
    } else if game::find_host64(config).is_none() {
        return Err(AppError::Game(
            "the game is not built yet: open Settings and build it".to_string(),
        ));
    }
    let character = data.get("character").cloned().unwrap_or(fallback_character);
    let mut instances = state.instances.lock().await;
    instances
        .launch(
            config,
            account,
            character,
            &client,
            &login_token,
            &game_dir,
            headless,
        )
        .await
}

async fn launch_with_config(
    state: &State<'_, AppState>,
    config: &LauncherConfig,
    account: &str,
    character_id: Option<i64>,
) -> AppResult<InstanceView> {
    let entry = config
        .account_entry(Some(account))
        .cloned()
        .ok_or_else(|| AppError::Validation(format!("@{account} is not saved in this launcher")))?;
    if entry.token.is_empty() {
        return Err(AppError::Validation(format!(
            "@{account} needs to sign in again"
        )));
    }
    let character = choose_character(&entry, character_id)?;
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let data = api
        .launch(&entry.token, character.get("id").and_then(value_i64))
        .await?;
    let view = spawn_launch(state, config, &entry.username, character, &data, false).await?;
    let mut locked = state.config.lock().await;
    locked.set_character_id(
        &entry.username,
        view.character.get("id").and_then(value_i64),
    );
    let _ = locked.save();
    Ok(view)
}

async fn launch_sub_with_config(
    state: &State<'_, AppState>,
    config: &LauncherConfig,
    sub_id: i64,
    character_id: Option<i64>,
    headless: bool,
) -> AppResult<InstanceView> {
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let data = api.launch_sub(&config.token, sub_id, character_id).await?;
    let username = data
        .pointer("/client/username")
        .and_then(Value::as_str)
        .ok_or_else(|| AppError::Api {
            status: 500,
            code: "bad_reply".to_string(),
            message: "the server did not name the sub-account".to_string(),
        })?
        .to_string();
    let character = data.get("character").cloned().unwrap_or(Value::Null);
    spawn_launch(state, config, &username, character, &data, headless).await
}

async fn sub_username(config: &LauncherConfig, sub_id: i64) -> AppResult<String> {
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let value = api.sub_accounts(&config.token).await?;
    value
        .get("subs")
        .and_then(Value::as_array)
        .and_then(|subs| {
            subs.iter()
                .find(|sub| sub.get("id").and_then(value_i64) == Some(sub_id))
        })
        .and_then(|sub| sub.get("username"))
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| {
            AppError::Validation(format!("sub-account {sub_id} is no longer in the team"))
        })
}

/// Stop the instance the launcher itself tracks for this account.
async fn stop_tracked_account(state: &State<'_, AppState>, account: &str) -> Vec<String> {
    let mut notes = Vec::new();
    loop {
        let port = {
            let instances = state.instances.lock().await;
            instances.running_for(account).map(|instance| instance.port)
        };
        let Some(port) = port else { break };
        let mut instances = state.instances.lock().await;
        match instances.stop(port).await {
            Ok(()) => notes.push(format!("stopped the client on control port {port}")),
            Err(_) => break,
        }
    }
    notes
}

/// True when the launcher already has a tracked client for the account that is in game.
async fn tracked_in_game(state: &State<'_, AppState>, account: &str) -> bool {
    poll_views(state)
        .await
        .into_iter()
        .any(|view| view.account.eq_ignore_ascii_case(account) && view_in_game(&view))
}

/// Stop anything that can still hold this account before a local headless relaunch: the instance
/// the launcher tracks, a remote box in the helper's registry whose tunnel died, and local
/// leftovers from an earlier launcher session.
async fn clean_account(state: &State<'_, AppState>, account: &str) -> Vec<String> {
    if tracked_in_game(state, account).await {
        return vec![format!("kept @{account}: already in game")];
    }
    let mut notes = stop_tracked_account(state, account).await;
    notes.extend(boxes::stop_account(account).await);
    boxes::wait_local_gone(account, std::time::Duration::from_secs(5)).await;
    notes
}

/// The remote path keeps the registry entry and any attached remote instance (the helper restarts
/// it), but a local duplicate for the account still has to go before the remote client logs in.
async fn stop_local_for_account(state: &State<'_, AppState>, account: &str) -> Vec<String> {
    if tracked_in_game(state, account).await {
        return vec![format!("kept @{account}: already in game")];
    }
    let mut notes = Vec::new();
    loop {
        let port = {
            let instances = state.instances.lock().await;
            instances
                .local_running_for(account)
                .map(|instance| instance.port)
        };
        let Some(port) = port else { break };
        let mut instances = state.instances.lock().await;
        match instances.stop(port).await {
            Ok(()) => notes.push(format!("stopped the local client on control port {port}")),
            Err(_) => break,
        }
    }
    notes.extend(boxes::stop_local_orphans(account).await);
    boxes::wait_local_gone(account, std::time::Duration::from_secs(5)).await;
    notes
}

/// Run `scripts/linux_boxes.py` against the configured Linux host. The helper mints the launch
/// tokens, starts/restarts the remote `host64-headless` processes, rebuilds their ssh tunnels and
/// waits until the characters are in a zone.
async fn run_remote_boxes(
    config: &LauncherConfig,
    action: &str,
    only: Option<&str>,
) -> AppResult<String> {
    if config.remote_ssh.trim().is_empty() {
        return Err(AppError::Config(
            "set the remote Linux host in Settings first".to_string(),
        ));
    }
    let root = game::resolve_repo_root_for(config).ok_or_else(|| {
        AppError::Config("the Fanxi checkout was not found; set it in Settings".to_string())
    })?;
    let script = root.join("scripts").join("linux_boxes.py");
    if !script.is_file() {
        return Err(AppError::Config(format!(
            "{} was not found",
            script.display()
        )));
    }
    let venv_python = root.join(".venv").join("bin").join("python");
    let python = if venv_python.is_file() {
        venv_python
    } else {
        PathBuf::from("python3")
    };
    let mut command = tokio::process::Command::new(&python);
    command
        .arg(&script)
        .arg(action)
        .arg("--ssh")
        .arg(config.remote_ssh.trim())
        .arg("--api")
        .arg(&config.api_url)
        .arg("--token")
        .arg(&config.token)
        .current_dir(&root)
        .kill_on_drop(true);
    if let Some(only) = only {
        if !only.trim().is_empty() {
            command.arg("--only").arg(only);
        }
    }
    let output = tokio::time::timeout(std::time::Duration::from_secs(180), command.output())
        .await
        .map_err(|_| AppError::Control("the remote box helper timed out".to_string()))?
        .map_err(|error| {
            AppError::Control(format!("could not run scripts/linux_boxes.py: {error}"))
        })?;
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let text = if stderr.is_empty() {
        stdout
    } else if stdout.is_empty() {
        stderr
    } else {
        format!("{stdout}\n{stderr}")
    };
    if !output.status.success() {
        let tail: Vec<&str> = text.lines().rev().take(6).collect();
        let tail: Vec<&str> = tail.into_iter().rev().collect();
        return Err(AppError::Control(format!(
            "remote box helper failed: {}",
            tail.join(" | ")
        )));
    }
    Ok(text)
}

/// The server's live zone roster, or `None` when it cannot be trusted as authoritative
/// (no sign-in, the route is missing on an older server, or the game gateway is off).
async fn online_roster(config: &LauncherConfig) -> Option<OnlineRoster> {
    if config.token.trim().is_empty() {
        return None;
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure).ok()?;
    // The UI polls every three seconds; a slow or unreachable server must not hold the whole
    // control-room refresh. Unknown is a valid answer and falls back to the client's own state.
    let value = tokio::time::timeout(
        std::time::Duration::from_secs(2),
        api.world_online(&config.token),
    )
    .await
    .ok()?
    .ok()?;
    OnlineRoster::from_value(&value)
}

/// Poll every client once, with the server's roster in hand, so a row can say whether the
/// client's "in world" is backed by a live session.
async fn poll_views(state: &State<'_, AppState>) -> Vec<InstanceView> {
    let config = state.config.lock().await.clone();
    let roster = online_roster(&config).await;
    let mut instances = state.instances.lock().await;
    instances.poll_with_online(roster.as_ref()).await
}

/// Refresh the attached boxes and return every live view.
async fn attached_views(state: &State<'_, AppState>) -> Vec<InstanceView> {
    poll_views(state).await
}

/// A box whose control port says it is in a zone but the server has no session for it. This
/// is what a server restart leaves behind: the process keeps running and answering, but
/// `//warp`, invites and `/sea` all see an offline character.
fn view_orphaned(view: &InstanceView) -> bool {
    view.alive
        && view.error.is_empty()
        && view.uptime_seconds > 15
        && view.server_online == Some(false)
        && view
            .state
            .as_ref()
            .and_then(|state| state.get("login_status"))
            .and_then(Value::as_u64)
            == Some(2)
}

/// A view is "good active" only when the client is alive, the control port is answering, and
/// the game itself says it is in a zone. `alive` alone is not enough: a disconnected client
/// can still answer the control socket while it sits on the disconnect screen.
fn view_in_game(view: &InstanceView) -> bool {
    view.alive
        && view.error.is_empty()
        && !view_orphaned(view)
        && view
            .state
            .as_ref()
            .and_then(|state| state.get("login_status"))
            .and_then(Value::as_u64)
            == Some(2)
}

/// Conservative pre-launch cleanup. Only untracked/unanswered local clients and dead registry
/// tunnels are touched; anything in game is kept.
async fn reap_before_headless(state: &State<'_, AppState>) -> Vec<String> {
    let tracked: Vec<u32> = {
        let instances = state.instances.lock().await;
        instances
            .views()
            .into_iter()
            .filter(|view| view.alive)
            .map(|view| view.pid)
            .collect()
    };
    let notes = boxes::reap_orphans_for_launch(&tracked).await;
    if !notes.is_empty() {
        eprintln!("[headless cleanup] {}", notes.join("; "));
    }
    notes
}

/// Refresh the attached boxes and return the view for one account.
async fn refresh_view(state: &State<'_, AppState>, account: &str) -> Option<InstanceView> {
    poll_views(state)
        .await
        .into_iter()
        .find(|view| view.account.eq_ignore_ascii_case(account))
}

/// The helper finished, but give the tunnel a moment to appear in the launcher's attach list.
async fn attach_remote_view(state: &State<'_, AppState>, account: &str) -> AppResult<InstanceView> {
    for _ in 0..20 {
        if let Some(view) = refresh_view(state, account).await {
            return Ok(view);
        }
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    }
    Err(AppError::Control(format!(
        "the remote helper finished, but @{account} did not attach; check the Linux box"
    )))
}

/// A client reports success as soon as the process exists, but it only becomes useful when the
/// character reaches a zone. Wait for that, nudging the title/agreement/character screens with
/// Enter the way `scripts/linux_boxes.py` does.
async fn await_signin(view: &InstanceView) -> AppResult<Value> {
    let client = ControlClient::new(view.port);
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(75);
    loop {
        if !boxes::pid_alive(view.pid) {
            return Err(AppError::Control(format!("{} exited", view.name)));
        }
        if let Ok(state) = client
            .call("state", json!({}), std::time::Duration::from_secs(2))
            .await
        {
            if state.get("login_status").and_then(Value::as_u64) == Some(2) {
                return Ok(state);
            }
        }
        let _ = client
            .call(
                "keys",
                json!({"keys": ["enter"], "hold_ms": 100}),
                std::time::Duration::from_secs(2),
            )
            .await;
        if tokio::time::Instant::now() >= deadline {
            return Err(AppError::Control(format!(
                "{} did not reach a zone within 75 s",
                view.name
            )));
        }
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
    }
}

fn tail_lines(path: &str, count: usize) -> String {
    let Ok(text) = std::fs::read_to_string(path) else {
        return String::new();
    };
    let lines: Vec<&str> = text
        .lines()
        .filter(|line| !line.trim().is_empty())
        .collect();
    lines[lines.len().saturating_sub(count)..].join(" | ")
}

async fn launch_remote_party(
    state: &State<'_, AppState>,
    config: &LauncherConfig,
) -> AppResult<LaunchAllResult> {
    let _guard = state
        .remote
        .try_lock()
        .map_err(|_| AppError::Control("a remote box operation is already running".to_string()))?;
    let _reaped = reap_before_headless(&state).await;
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let value = api.sub_accounts(&config.token).await?;
    let subs = value
        .get("subs")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut ids = Vec::new();
    let mut accounts = Vec::new();
    for sub in subs {
        if sub.get("status").and_then(Value::as_str) != Some("active")
            || sub.get("character").map(Value::is_null).unwrap_or(true)
        {
            continue;
        }
        let Some(sub_id) = sub.get("id").and_then(value_i64) else {
            continue;
        };
        let account = sub
            .get("username")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        if account.is_empty() {
            continue;
        }
        ids.push(sub_id.to_string());
        accounts.push(account);
    }
    if ids.is_empty() {
        return Err(AppError::Validation(
            "no active sub-accounts with characters".to_string(),
        ));
    }
    // Restart only the boxes that are not already in game; a healthy team makes this instant.
    let current = attached_views(state).await;
    let missing_ids: Vec<String> = ids
        .iter()
        .zip(&accounts)
        .filter(|(_, account)| {
            !current
                .iter()
                .any(|view| view_in_game(view) && view.account.eq_ignore_ascii_case(account))
        })
        .map(|(id, _)| id.clone())
        .collect();
    for (id, account) in ids.iter().zip(&accounts) {
        if missing_ids.contains(id) {
            let _ = stop_local_for_account(state, account).await;
        }
    }
    let output = if missing_ids.is_empty() {
        String::new()
    } else {
        run_remote_boxes(config, "restart", Some(&missing_ids.join(","))).await?
    };
    let views = attached_views(state).await;
    let launched: Vec<InstanceView> = views
        .into_iter()
        .filter(|view| {
            accounts
                .iter()
                .any(|account| account.eq_ignore_ascii_case(&view.account))
        })
        .collect();
    let failed: Vec<FailedLaunch> = accounts
        .iter()
        .filter(|account| {
            !launched
                .iter()
                .any(|view| view.account.eq_ignore_ascii_case(account))
        })
        .map(|account| FailedLaunch {
            account: account.clone(),
            error: format!("did not attach after the remote helper finished; {output}"),
        })
        .collect();
    Ok(LaunchAllResult { launched, failed })
}

#[tauri::command]
pub async fn launch_headless_party(state: State<'_, AppState>) -> AppResult<LaunchAllResult> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    if !config.remote_ssh.trim().is_empty() {
        return launch_remote_party(&state, &config).await;
    }
    let _reaped = reap_before_headless(&state).await;
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let value = api.sub_accounts(&config.token).await?;
    let subs = value
        .get("subs")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut launched = Vec::new();
    let mut failed = Vec::new();
    for sub in subs {
        if sub.get("status").and_then(Value::as_str) != Some("active")
            || sub.get("character").map(Value::is_null).unwrap_or(true)
        {
            continue;
        }
        let Some(sub_id) = sub.get("id").and_then(value_i64) else {
            continue;
        };
        let account = sub
            .get("username")
            .and_then(Value::as_str)
            .unwrap_or("?")
            .to_string();
        let character_id = sub.pointer("/character/id").and_then(value_i64);
        if refresh_view(&state, &account)
            .await
            .map(|view| view_in_game(&view))
            .unwrap_or(false)
        {
            continue;
        }
        let stopped = clean_account(&state, &account).await;
        match launch_sub_with_config(&state, &config, sub_id, character_id, true).await {
            Ok(view) => launched.push(view),
            Err(error) => {
                let cleanup = if stopped.is_empty() {
                    String::new()
                } else {
                    format!(" (cleaned first: {})", stopped.join("; "))
                };
                failed.push(FailedLaunch {
                    account,
                    error: format!("{error}{cleanup}"),
                });
            }
        }
        tokio::time::sleep(std::time::Duration::from_millis(700)).await;
    }
    Ok(LaunchAllResult { launched, failed })
}

#[tauri::command]
pub async fn launch_all(state: State<'_, AppState>) -> AppResult<LaunchAllResult> {
    let config = state.config.lock().await.clone();
    if config.saved_accounts().is_empty() {
        return Err(AppError::Validation("no saved accounts".to_string()));
    }
    let accounts: Vec<AccountEntry> = config
        .saved_accounts()
        .into_iter()
        .filter(|entry| !entry.token.is_empty())
        .cloned()
        .collect();
    if accounts.is_empty() {
        return Err(AppError::Validation(
            "sign in to an account first".to_string(),
        ));
    }
    let mut launched = Vec::new();
    let mut failed = Vec::new();
    for entry in accounts {
        {
            let instances = state.instances.lock().await;
            if instances.running_for(&entry.username).is_some() {
                continue;
            }
        }
        match launch_with_config(&state, &config, &entry.username, entry.character_id).await {
            Ok(view) => launched.push(view),
            Err(error) => failed.push(FailedLaunch {
                account: entry.username,
                error: error.to_string(),
            }),
        }
        tokio::time::sleep(std::time::Duration::from_millis(700)).await;
    }
    Ok(LaunchAllResult { launched, failed })
}

#[tauri::command]
pub async fn team(state: State<'_, AppState>) -> AppResult<TeamView> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let value = api.sub_accounts(&config.token).await?;
    Ok(TeamView {
        subs: value
            .get("subs")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default(),
        limit: value.get("limit").and_then(Value::as_i64).unwrap_or(5),
    })
}

#[tauri::command]
pub async fn create_sub(
    state: State<'_, AppState>,
    character: Option<Value>,
) -> AppResult<TeamMutation> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let value = api.create_sub(&config.token, character).await?;
    Ok(TeamMutation {
        sub: value.get("sub").cloned().unwrap_or(Value::Null),
        limit: value.get("limit").and_then(Value::as_i64).unwrap_or(5),
    })
}

#[tauri::command]
pub async fn activate_sub(state: State<'_, AppState>, sub_id: i64) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.activate_sub(&config.token, sub_id).await
}

#[tauri::command]
pub async fn create_sub_character(
    state: State<'_, AppState>,
    sub_id: i64,
    data: Value,
) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.create_sub_character(&config.token, sub_id, data).await
}

#[tauri::command]
pub async fn launch_sub(
    state: State<'_, AppState>,
    sub_id: i64,
    character_id: Option<i64>,
) -> AppResult<InstanceView> {
    let config = state.config.lock().await.clone();
    launch_sub_with_config(&state, &config, sub_id, character_id, false).await
}

/// Launch a single box without a visible game window, from its Team card.
#[tauri::command]
pub async fn launch_sub_headless(
    state: State<'_, AppState>,
    sub_id: i64,
    character_id: Option<i64>,
) -> AppResult<InstanceView> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    let username = sub_username(&config, sub_id).await?;
    let _reaped = reap_before_headless(&state).await;
    // Never restart a box that is alive and in game. The button can be pressed twice, and the
    // client may already be online from the previous launch or a manual start.
    if let Some(view) = refresh_view(&state, &username).await {
        if view.alive && view.error.is_empty() {
            let status = view
                .state
                .as_ref()
                .and_then(|state| state.get("login_status"))
                .and_then(Value::as_u64);
            if status == Some(2) {
                // A live box is never restarted. Wake it if it was sleeping; an awake box
                // answers "Already awake" and is returned unchanged.
                let client = ControlClient::new(view.port);
                let _ = client.command("//wake").await;
                {
                    let mut instances = state.instances.lock().await;
                    instances.set_sleeping(view.port, false);
                }
                boxes::set_sleeping(&username, false);
                return Ok(refresh_view(&state, &username).await.unwrap_or(view));
            }
        }
    }
    if !config.remote_ssh.trim().is_empty() {
        let _guard = state.remote.try_lock().map_err(|_| {
            AppError::Control("a remote box operation is already running".to_string())
        })?;
        let _stopped = stop_local_for_account(&state, &username).await;
        let only = sub_id.to_string();
        let _output = run_remote_boxes(&config, "restart", Some(&only)).await?;
        return attach_remote_view(&state, &username).await;
    }
    let stopped = clean_account(&state, &username).await;
    let view = launch_sub_with_config(&state, &config, sub_id, character_id, true).await?;
    if let Err(error) = await_signin(&view).await {
        {
            let mut instances = state.instances.lock().await;
            let _ = instances.stop(view.port).await;
        }
        let cleanup = if stopped.is_empty() {
            String::new()
        } else {
            format!(" Cleaned first: {}.", stopped.join("; "))
        };
        let tail = tail_lines(&view.log_path, 8);
        let detail = if tail.is_empty() {
            String::new()
        } else {
            format!(" Last log: {tail}")
        };
        return Err(AppError::Control(format!(
            "{error}.{cleanup}{detail} Log: {}",
            view.log_path
        )));
    }
    Ok(view)
}

#[tauri::command]
pub async fn force_relaunch_headless(
    state: State<'_, AppState>,
    sub_id: i64,
    character_id: Option<i64>,
) -> AppResult<InstanceView> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    let username = sub_username(&config, sub_id).await?;
    // The normal path can be stuck behind a remote operation that never returned. Force is
    // deliberately allowed to ignore that in-memory guard: it kills the helper, clears the
    // account's local/remote session and registry row, then starts a fresh client.
    let mut notes = boxes::kill_helper_processes();
    notes.extend(stop_tracked_account(&state, &username).await);
    notes.extend(boxes::force_stop_account(&username).await);
    if !config.remote_ssh.trim().is_empty() {
        notes.extend(boxes::force_stop_remote(config.remote_ssh.trim(), &username).await);
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        // A previously stuck task may try to spawn a new helper after the first sweep.
        notes.extend(boxes::kill_helper_processes());
        let only = sub_id.to_string();
        let _ = run_remote_boxes(&config, "restart", Some(&only)).await?;
        eprintln!("[force relaunch] {username}: {}", notes.join("; "));
        return attach_remote_view(&state, &username).await;
    }
    let view = launch_sub_with_config(&state, &config, sub_id, character_id, true).await?;
    if let Err(error) = await_signin(&view).await {
        {
            let mut instances = state.instances.lock().await;
            let _ = instances.stop(view.port).await;
        }
        return Err(AppError::Control(format!(
            "force cleanup ran ({}), but {username} did not sign in: {error}",
            notes.join("; ")
        )));
    }
    eprintln!("[force relaunch] {username}: {}", notes.join("; "));
    Ok(view)
}

#[tauri::command]
pub async fn launch_remote_team(state: State<'_, AppState>) -> AppResult<String> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    if config.remote_ssh.trim().is_empty() {
        return Err(AppError::Config(
            "set the remote Linux host in Settings first".to_string(),
        ));
    }
    let _guard = state
        .remote
        .try_lock()
        .map_err(|_| AppError::Control("a remote box operation is already running".to_string()))?;
    let reaped = reap_before_headless(&state).await;
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let value = api.sub_accounts(&config.token).await?;
    let subs = value
        .get("subs")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut ids = Vec::new();
    let mut accounts = Vec::new();
    for sub in subs {
        if sub.get("status").and_then(Value::as_str) != Some("active")
            || sub.get("character").map(Value::is_null).unwrap_or(true)
        {
            continue;
        }
        let Some(sub_id) = sub.get("id").and_then(value_i64) else {
            continue;
        };
        let account = sub
            .get("username")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        if account.is_empty() {
            continue;
        }
        ids.push(sub_id.to_string());
        accounts.push(account);
    }
    if ids.is_empty() {
        return Err(AppError::Validation(
            "no active sub-accounts with characters".to_string(),
        ));
    }
    // A local copy of a box that is not in game yet would fight the remote login. Healthy
    // remote boxes are left alone; healthy local clients are left alone too.
    let current = attached_views(&state).await;
    let missing_ids: Vec<String> = ids
        .iter()
        .zip(&accounts)
        .filter(|(_, account)| {
            !current
                .iter()
                .any(|view| view_in_game(view) && view.account.eq_ignore_ascii_case(account))
        })
        .map(|(id, _)| id.clone())
        .collect();
    for (id, account) in ids.iter().zip(&accounts) {
        if missing_ids.contains(id) {
            let _ = stop_local_for_account(&state, account).await;
        }
    }
    // The main account stays the one visible client, on this Mac.
    if !config.username.is_empty() {
        let in_game = refresh_view(&state, &config.username)
            .await
            .map(|view| view_in_game(&view))
            .unwrap_or(false);
        if !in_game {
            let _ = stop_local_for_account(&state, &config.username).await;
            let view =
                launch_with_config(&state, &config, &config.username, config.character_id).await?;
            await_signin(&view).await?;
        }
    }
    let output = if missing_ids.is_empty() {
        String::new()
    } else {
        run_remote_boxes(&config, "restart", Some(&missing_ids.join(","))).await?
    };
    let views = attached_views(&state).await;
    let missing: Vec<&str> = accounts
        .iter()
        .map(String::as_str)
        .filter(|account| {
            !views
                .iter()
                .any(|view| view.account.eq_ignore_ascii_case(account))
        })
        .collect();
    if !missing.is_empty() {
        return Err(AppError::Control(format!(
            "the remote helper finished, but these boxes did not attach: {}. {output}",
            missing.join(", ")
        )));
    }
    let cleaned = reaped
        .iter()
        .filter(|note| note.starts_with("stopped") || note.starts_with("reaped"))
        .count();
    Ok(format!(
        "team online on {}: {} boxes + main{}",
        config.remote_ssh.trim(),
        accounts.len(),
        if cleaned > 0 {
            format!("; cleaned {cleaned} orphan(s)")
        } else {
            String::new()
        }
    ))
}

#[tauri::command]
pub async fn launch_team(state: State<'_, AppState>) -> AppResult<LaunchAllResult> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let team = api.sub_accounts(&config.token).await?;
    let subs = team
        .get("subs")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();

    let mut launched = Vec::new();
    let mut failed = Vec::new();

    // The main account is the root of the team and launches like any other character.
    if !config.username.is_empty() {
        let running = {
            let instances = state.instances.lock().await;
            instances.running_for(&config.username).is_some()
        };
        if !running {
            match launch_with_config(&state, &config, &config.username, config.character_id).await {
                Ok(view) => launched.push(view),
                Err(error) => failed.push(FailedLaunch {
                    account: config.username.clone(),
                    error: error.to_string(),
                }),
            }
        }
    }

    for sub in subs {
        if sub.get("status").and_then(Value::as_str) != Some("active") {
            continue;
        }
        let Some(sub_id) = sub.get("id").and_then(value_i64) else {
            continue;
        };
        let username = sub
            .get("username")
            .and_then(Value::as_str)
            .unwrap_or("sub")
            .to_string();
        let character_id = sub.pointer("/character/id").and_then(value_i64);
        let running = {
            let instances = state.instances.lock().await;
            instances.running_for(&username).is_some()
        };
        if running {
            continue;
        }
        match launch_sub_with_config(&state, &config, sub_id, character_id, false).await {
            Ok(view) => launched.push(view),
            Err(error) => failed.push(FailedLaunch {
                account: username,
                error: error.to_string(),
            }),
        }
        tokio::time::sleep(std::time::Duration::from_millis(700)).await;
    }
    Ok(LaunchAllResult { launched, failed })
}

#[tauri::command]
pub async fn delete_sub(state: State<'_, AppState>, sub_id: i64, purge: bool) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to the main account first".to_string(),
        ));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.delete_sub(&config.token, sub_id, purge).await
}

#[tauri::command]
pub async fn list_instances(state: State<'_, AppState>) -> AppResult<Vec<InstanceView>> {
    Ok(poll_views(&state).await)
}

/// The sub-account id behind a box username, or `None` for the main account.
async fn find_sub_id(config: &LauncherConfig, account: &str) -> AppResult<Option<i64>> {
    if config.token.is_empty() {
        return Ok(None);
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    let value = api.sub_accounts(&config.token).await?;
    let found = value
        .get("subs")
        .and_then(Value::as_array)
        .and_then(|subs| {
            subs.iter()
                .find(|sub| {
                    sub.get("username")
                        .and_then(Value::as_str)
                        .map(|name| name.eq_ignore_ascii_case(account))
                        .unwrap_or(false)
                })
                .and_then(|sub| sub.get("id"))
                .and_then(value_i64)
        });
    Ok(found)
}

/// Stop one box and start the same character again.
///
/// A box that lost its zone session keeps its process and its control port, so the server has no
/// session to warp and the launcher still lists it. An attached Linux box is restarted through the
/// same helper that started it (same tunnel port, so the launcher adopts it again); a local client
/// is stopped and launched again through the normal token path.
#[tauri::command]
pub async fn relaunch_instance(state: State<'_, AppState>, port: u16) -> AppResult<InstanceView> {
    let config = state.config.lock().await.clone();
    let (account, remote, headless, character_id) = {
        let instances = state.instances.lock().await;
        let view = instances
            .views()
            .into_iter()
            .find(|view| view.port == port)
            .ok_or_else(|| AppError::Control(format!("no client on control port {port}")))?;
        (
            view.account,
            view.remote,
            view.headless,
            view.character.get("id").and_then(value_i64),
        )
    };
    let sub_id = find_sub_id(&config, &account).await?;
    if remote {
        let _guard = state.remote.try_lock().map_err(|_| {
            AppError::Control("a remote box operation is already running".to_string())
        })?;
        let id = sub_id.ok_or_else(|| {
            AppError::Validation(format!("@{account} is not a sub-account of this launcher"))
        })?;
        run_remote_boxes(&config, "restart", Some(&id.to_string())).await?;
        return attach_remote_view(&state, &account).await;
    }
    {
        let mut instances = state.instances.lock().await;
        instances.stop(port).await?;
    }
    match sub_id {
        Some(id) => launch_sub_with_config(&state, &config, id, character_id, headless).await,
        None => launch_with_config(&state, &config, &account, character_id).await,
    }
}

/// The control addon reports the client's own axes: x and y are the ground plane and z is
/// height. The server's `//pos` and `//zone` take x, y (height), z (ground), so forwarding a
/// position unchanged puts a box at (x, ground, height) — hundreds of yalms above the world
/// and outside every entity list. Fourdough sat at 515.9 height instead of -27.1 this way.
fn server_position(position: &Value) -> Option<[f64; 3]> {
    let x = position.get("x").and_then(Value::as_f64)?;
    let y = position.get("y").and_then(Value::as_f64)?;
    let z = position.get("z").and_then(Value::as_f64)?;
    if !x.is_finite() || !y.is_finite() || !z.is_finite() {
        return None;
    }
    Some([x, z, y])
}

/// `//zone` with the leader's position in the server's order. A zone hand-off also refreshes
/// the client's entity table, which a same-zone `//pos` does not.
fn zone_command(zone: u64, position: &Value) -> AppResult<String> {
    let [x, y, z] = server_position(position)
        .ok_or_else(|| AppError::Control("the leader has no usable position yet".to_string()))?;
    Ok(format!("//zone {zone} {x:.3} {y:.3} {z:.3}"))
}

fn near_position(a: &Value, b: &Value) -> bool {
    let Some([ax, ay, az]) = server_position(a) else {
        return false;
    };
    let Some([bx, by, bz]) = server_position(b) else {
        return false;
    };
    (ax - bx).hypot(ay - by) < 5.0 && (az - bz).abs() < 5.0
}

/// Wait for a restarted client to be in a loaded zone. `pid` is the local process only: an
/// attached Linux box has a remote pid that this machine cannot signal-check.
async fn await_loaded(
    port: u16,
    pid: Option<u32>,
    timeout: std::time::Duration,
) -> AppResult<Value> {
    let client = ControlClient::new(port);
    let deadline = tokio::time::Instant::now() + timeout;
    loop {
        if let Some(pid) = pid {
            if !boxes::pid_alive(pid) {
                return Err(AppError::Control(format!(
                    "the client on control port {port} exited"
                )));
            }
        }
        if let Ok(state) = client.state().await {
            if state.get("login_status").and_then(Value::as_u64) == Some(2)
                && state.pointer("/zone/id").and_then(Value::as_u64).is_some()
            {
                return Ok(state);
            }
        }
        let _ = client
            .call(
                "keys",
                json!({"keys": ["enter"], "hold_ms": 100}),
                std::time::Duration::from_secs(2),
            )
            .await;
        if tokio::time::Instant::now() >= deadline {
            return Err(AppError::Control(format!(
                "the client on control port {port} did not reach a zone in {} s",
                timeout.as_secs()
            )));
        }
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
    }
}

/// Wait until the box is in the leader's zone and near the leader's *current* spot. The
/// leader may move while the box relogs, so the live position is read again each tick.
async fn await_anchor(
    port: u16,
    zone: u64,
    leader_port: u16,
    fallback_position: &Value,
    timeout: std::time::Duration,
) -> bool {
    let client = ControlClient::new(port);
    let leader = ControlClient::new(leader_port);
    let deadline = tokio::time::Instant::now() + timeout;
    loop {
        let leader_state = leader.state().await.ok();
        let target_zone = leader_state
            .as_ref()
            .and_then(|state| state.pointer("/zone/id"))
            .and_then(Value::as_u64)
            .unwrap_or(zone);
        let target_position = leader_state
            .as_ref()
            .and_then(|state| state.pointer("/player/position"))
            .cloned()
            .unwrap_or_else(|| fallback_position.clone());
        if let Ok(follower) = client.state().await {
            let at_zone = follower.pointer("/zone/id").and_then(Value::as_u64) == Some(target_zone)
                && follower.pointer("/player/position").is_some();
            let at_position = follower
                .pointer("/player/position")
                .map(|position| near_position(position, &target_position))
                .unwrap_or(false);
            if at_zone && at_position {
                return true;
            }
        }
        if tokio::time::Instant::now() >= deadline {
            return false;
        }
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FixFollowerResult {
    pub account: String,
    pub name: String,
    pub port: u16,
    pub leader: String,
    pub zone: String,
    pub message: String,
}

/// The Follow card's Fix button: kill the box, relaunch the same character, then zone it to
/// its line leader and re-apply follow.
///
/// This is the manual escape hatch for a box that stays `waiting` after the automatic
/// recovery gave up. A client whose entity table never saw the leader — or that a bad
/// recovery left out of range — needs a new process, not another position packet. The
/// launcher owns the launch token, so it can relog; a remote box is restarted by the same
/// helper that started it.
#[tauri::command]
pub async fn fix_follower(
    state: State<'_, AppState>,
    port: u16,
    leader_port: u16,
) -> AppResult<FixFollowerResult> {
    if port == leader_port {
        return Err(AppError::Validation(
            "a box cannot be fixed onto itself".to_string(),
        ));
    }
    let config = state.config.lock().await.clone();
    // Read the leader before the restart, while the follower is still the old process.
    let (leader_name, leader_zone, leader_zone_name, leader_position, leader_client) = {
        let leader_client = { state.instances.lock().await.control_for(leader_port)? };
        let leader = leader_client.state().await?;
        if leader.get("login_status").and_then(Value::as_u64) != Some(2) {
            return Err(AppError::Control(
                "the line leader is not in game yet".to_string(),
            ));
        }
        let name = leader
            .pointer("/player/name")
            .and_then(Value::as_str)
            .filter(|name| !name.trim().is_empty())
            .unwrap_or("the leader")
            .to_string();
        let zone = leader
            .pointer("/zone/id")
            .and_then(Value::as_u64)
            .ok_or_else(|| AppError::Control("the leader is not in a zone yet".to_string()))?;
        let zone_name = leader
            .pointer("/zone/name")
            .and_then(Value::as_str)
            .map(str::to_string)
            .unwrap_or_else(|| format!("zone {zone}"));
        let position = leader
            .pointer("/player/position")
            .cloned()
            .ok_or_else(|| AppError::Control("the leader has no position yet".to_string()))?;
        if server_position(&position).is_none() {
            return Err(AppError::Control(
                "the leader has no usable position yet".to_string(),
            ));
        }
        (name, zone, zone_name, position, leader_client)
    };
    let line = zone_command(leader_zone, &leader_position)?;

    let (account, remote, headless, character_id, name) = {
        let instances = state.instances.lock().await;
        let view = instances
            .views()
            .into_iter()
            .find(|view| view.port == port)
            .ok_or_else(|| AppError::Control(format!("no client on control port {port}")))?;
        (
            view.account,
            view.remote,
            view.headless,
            view.character.get("id").and_then(value_i64),
            view.name,
        )
    };
    let sub_id = find_sub_id(&config, &account).await?;

    let view = if remote {
        let _guard = state.remote.try_lock().map_err(|_| {
            AppError::Control("a remote box operation is already running".to_string())
        })?;
        let id = sub_id.ok_or_else(|| {
            AppError::Validation(format!("@{account} is not a sub-account of this launcher"))
        })?;
        run_remote_boxes(&config, "restart", Some(&id.to_string())).await?;
        attach_remote_view(&state, &account).await?
    } else {
        {
            let mut instances = state.instances.lock().await;
            instances.stop(port).await?;
        }
        match sub_id {
            Some(id) => launch_sub_with_config(&state, &config, id, character_id, headless).await?,
            None => launch_with_config(&state, &config, &account, character_id).await?,
        }
    };
    let local_pid = (!view.remote && view.pid > 0).then_some(view.pid);
    let loaded = await_loaded(view.port, local_pid, std::time::Duration::from_secs(90)).await?;
    // The registry entry can lag behind the character that actually signed in; the live state
    // is what the server's `//warp call` resolves.
    let name = loaded
        .pointer("/player/name")
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .map(str::to_string)
        .unwrap_or(name);

    let client = ControlClient::new(view.port);
    client.command(&line).await?;
    let wait = std::time::Duration::from_secs(25);
    let mut anchored =
        await_anchor(view.port, leader_zone, leader_port, &leader_position, wait).await;
    if !anchored {
        // The first zone after a relog can still be settling; the server-side call is the same
        // hand-off from the leader's side and works across zones without coordinates.
        let _ = leader_client.command(&format!("//warp call {name}")).await;
        anchored = await_anchor(view.port, leader_zone, leader_port, &leader_position, wait).await;
    }
    if !anchored {
        return Err(AppError::Control(format!(
            "{name} relaunched but did not join {leader_name} in {leader_zone_name}"
        )));
    }
    client.follow(true, Some(&leader_name), 1.0).await?;
    Ok(FixFollowerResult {
        account,
        name: name.clone(),
        port: view.port,
        leader: leader_name.clone(),
        zone: leader_zone_name.clone(),
        message: format!("{name} was relaunched and zoned to {leader_name} in {leader_zone_name}."),
    })
}

#[tauri::command]
pub async fn stop_instance(state: State<'_, AppState>, port: u16) -> AppResult<()> {
    let sleep = {
        let instances = state.instances.lock().await;
        instances
            .by_port(port)
            .map(|instance| instance.remote.is_some() || instance.headless)
            .unwrap_or(false)
    };
    if sleep {
        let (client, account) = {
            let instances = state.instances.lock().await;
            let account = instances
                .by_port(port)
                .map(|instance| instance.account.clone())
                .ok_or_else(|| AppError::Control(format!("no client on control port {port}")))?;
            (ControlClient::new(port), account)
        };
        client.command("//sleep").await?;
        {
            let mut instances = state.instances.lock().await;
            instances.set_sleeping(port, true);
        }
        boxes::set_sleeping(&account, true);
        return Ok(());
    }
    let mut instances = state.instances.lock().await;
    instances.stop(port).await
}

/// Park or wake one live client. Sleep keeps the process, UDP session and tunnel alive; the
/// server hides the character and parks its tick. Wake resumes in place with no new login.
#[tauri::command]
pub async fn set_headless_sleep(
    state: State<'_, AppState>,
    port: u16,
    sleeping: bool,
) -> AppResult<Value> {
    let (client, account) = {
        let instances = state.instances.lock().await;
        let account = instances
            .by_port(port)
            .map(|instance| instance.account.clone())
            .ok_or_else(|| AppError::Control(format!("no client on control port {port}")))?;
        (ControlClient::new(port), account)
    };
    let result = client
        .command(if sleeping { "//sleep" } else { "//wake" })
        .await?;
    {
        let mut instances = state.instances.lock().await;
        instances.set_sleeping(port, sleeping);
    }
    boxes::set_sleeping(&account, sleeping);
    Ok(result)
}

#[tauri::command]
pub async fn stop_all(state: State<'_, AppState>) -> AppResult<usize> {
    let targets: Vec<(u16, String, bool)> = {
        let instances = state.instances.lock().await;
        instances
            .views()
            .into_iter()
            .filter(|view| view.alive)
            .map(|view| {
                let sleep = {
                    instances
                        .by_port(view.port)
                        .map(|instance| instance.remote.is_some() || instance.headless)
                        .unwrap_or(false)
                };
                (view.port, view.account, sleep)
            })
            .collect()
    };
    let mut stopped = 0;
    for (port, account, sleep) in targets {
        if sleep {
            let client = ControlClient::new(port);
            let _ = client.command("//sleep").await;
            {
                let mut instances = state.instances.lock().await;
                instances.set_sleeping(port, true);
            }
            boxes::set_sleeping(&account, true);
        } else {
            let mut instances = state.instances.lock().await;
            let _ = instances.stop(port).await;
        }
        stopped += 1;
    }
    Ok(stopped)
}

#[tauri::command]
pub async fn send_command(state: State<'_, AppState>, port: u16, line: String) -> AppResult<Value> {
    let line = line.trim().to_string();
    if line.is_empty() {
        return Err(AppError::Validation("the command is empty".to_string()));
    }
    let client = { state.instances.lock().await.control_for(port)? };
    client.command(&line).await
}

/// Change the in-game ability/spell HUD (the control addon's `hud` command). The payload is
/// passed through so the Control room can toggle, re-layout or start edit mode in one call.
/// Load the account's GearSwap/phase configuration from the game database.
#[tauri::command]
pub async fn gearswap_settings(state: State<'_, AppState>) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to load GearSwap settings".to_string(),
        ));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.gearswap_settings(&config.token).await
}

/// Replace the account's GearSwap/phase configuration in the game database.
#[tauri::command]
pub async fn save_gearswap_settings(state: State<'_, AppState>, config: Value) -> AppResult<Value> {
    let current = state.config.lock().await.clone();
    if current.token.is_empty() {
        return Err(AppError::Validation(
            "sign in to save GearSwap settings".to_string(),
        ));
    }
    let api = ApiClient::new(&current.api_url, current.api_insecure)?;
    api.save_gearswap_settings(&current.token, config).await
}

#[tauri::command]
pub async fn send_hud(state: State<'_, AppState>, port: u16, patch: Value) -> AppResult<Value> {
    if !patch.is_object() {
        return Err(AppError::Validation(
            "the hud patch must be an object".to_string(),
        ));
    }
    let client = { state.instances.lock().await.control_for(port)? };
    client.hud(patch).await
}

/// The Battle hub: state, saved profiles, assignments and start/stop.  `args` is the addon's
/// `battle` payload (`action` plus profile/name/role fields), so the page can add fields without
/// another Rust command.
#[tauri::command]
pub async fn battle(state: State<'_, AppState>, port: u16, args: Value) -> AppResult<Value> {
    if !args.is_object() {
        return Err(AppError::Validation(
            "the battle payload must be an object".to_string(),
        ));
    }
    let client = { state.instances.lock().await.control_for(port)? };
    client
        .call("battle", args, std::time::Duration::from_secs(15))
        .await
}

#[tauri::command]
pub async fn send_chat(state: State<'_, AppState>, port: u16, line: String) -> AppResult<Value> {
    let line = line.trim().to_string();
    if line.is_empty() {
        return Err(AppError::Validation("the message is empty".to_string()));
    }
    let client = { state.instances.lock().await.control_for(port)? };
    client.chat(&line).await
}

#[tauri::command]
pub async fn control_state(state: State<'_, AppState>, port: u16) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.state().await
}

#[tauri::command]
pub async fn control_metrics(state: State<'_, AppState>, port: u16) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.metrics().await
}

#[tauri::command]
pub async fn set_follow(
    state: State<'_, AppState>,
    port: u16,
    enabled: bool,
    leader: Option<String>,
    distance: Option<f64>,
) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client
        .follow(enabled, leader.as_deref(), distance.unwrap_or(1.0))
        .await
}

#[tauri::command]
pub async fn follow_status(state: State<'_, AppState>, port: u16) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.follow_status().await
}

#[tauri::command]
pub async fn follow_events(state: State<'_, AppState>, port: u16) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.follow_events().await
}

#[tauri::command]
pub async fn gear_slots(state: State<'_, AppState>, port: u16) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.gear().await
}

#[tauri::command]
pub async fn equip_icons(
    state: State<'_, AppState>,
    port: u16,
    ids: Vec<u32>,
) -> AppResult<EquipIcons> {
    let mut icons_map = BTreeMap::new();
    let mut missing = Vec::new();
    let mut wanted = Vec::new();
    let mut seen = std::collections::BTreeSet::new();
    for id in ids {
        if id == 0 || !seen.insert(id) {
            continue;
        }
        if let Some(url) = icons::cached(id) {
            icons_map.insert(id.to_string(), url);
        } else {
            wanted.push(id);
        }
    }
    let mut error = None;
    if !wanted.is_empty() {
        let client = { state.instances.lock().await.control_for(port) };
        match client {
            Ok(client) => match client.icons(&wanted).await {
                Ok(reply) => {
                    if let Some(items) = reply.get("items").and_then(Value::as_array) {
                        for item in items {
                            match icons::from_reply(item) {
                                Some((id, url)) => {
                                    icons_map.insert(id.to_string(), url);
                                }
                                None => {
                                    if let Some(id) = item.get("id").and_then(Value::as_u64) {
                                        missing.push(id as u32);
                                    }
                                }
                            }
                        }
                    }
                }
                Err(caught) => error = Some(caught.to_string()),
            },
            Err(caught) => error = Some(caught.to_string()),
        }
    }
    Ok(EquipIcons {
        icons: icons_map,
        missing,
        error,
    })
}

#[tauri::command]
pub async fn gear_item_ids(
    state: State<'_, AppState>,
    port: u16,
    names: Vec<String>,
) -> AppResult<Vec<ResolvedItem>> {
    let client = { state.instances.lock().await.control_for(port)? };
    let reply = client.item_ids(&names).await?;
    let mut out = Vec::new();
    if let Some(items) = reply.get("items").and_then(Value::as_array) {
        for item in items {
            let name = item
                .get("name")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();
            let id = item.get("id").and_then(Value::as_u64).unwrap_or(0) as u32;
            out.push(ResolvedItem { name, id });
        }
    }
    Ok(out)
}

#[tauri::command]
pub async fn gear_item_stats(
    state: State<'_, AppState>,
    port: u16,
    items: Vec<gear_stats::GearStatRequest>,
) -> AppResult<Vec<gear_stats::GearItemStats>> {
    let client = { state.instances.lock().await.control_for(port)? };
    let code = gear_stats::item_query_code(&items);
    let reply = client.lua(&code).await?;
    Ok(gear_stats::build_stats(
        &items,
        &gear_stats::parse_lua_reply(&reply),
    ))
}

#[tauri::command]
pub async fn clear_icon_cache() -> AppResult<usize> {
    icons::clear_cache()
}

#[tauri::command]
pub async fn gear_job(
    state: State<'_, AppState>,
    port: u16,
    saved_character: Option<Value>,
) -> AppResult<Option<JobInfo>> {
    let client = { state.instances.lock().await.control_for(port)? };
    let state_value = client.state().await.ok();
    Ok(gear::job_from_state(state_value.as_ref())
        .or_else(|| gear::job_from_character(saved_character.as_ref())))
}

#[tauri::command]
pub async fn gear_load_default(
    app: AppHandle,
    state: State<'_, AppState>,
    port: u16,
    job: Option<String>,
) -> AppResult<GearLibrary> {
    let config = state.config.lock().await.clone();
    let repo = game::resolve_repo_root_for(&config);
    if config.repo_root.trim().is_empty() {
        if let Some(root) = repo.as_ref() {
            let mut locked = state.config.lock().await;
            locked.repo_root = root.to_string_lossy().into_owned();
            let _ = locked.save();
        }
    }
    let resource = app.path().resource_dir().ok();
    let folder = gear::defaults_dir(repo.as_deref(), resource.as_deref())
        .ok_or_else(|| AppError::Game("the gearswap defaults folder was not found".to_string()))?;
    let job_name = job.unwrap_or_default();
    let file = gear::default_file(&folder, &job_name)
        .ok_or_else(|| AppError::Validation(format!("no default library for {job_name}")))?;
    load_gear_file(&state, port, &file, Some(job_name)).await
}

#[tauri::command]
pub async fn gear_load_file(
    state: State<'_, AppState>,
    port: u16,
    path: String,
) -> AppResult<GearLibrary> {
    load_gear_file(&state, port, Path::new(&path), None).await
}

/// The text of a GearSwap library, read where the launcher can see it. A client on another machine
/// has none of the launcher's files, so a plan and an import carry the library's own text.
fn read_library_source(path: &Path) -> AppResult<String> {
    std::fs::read_to_string(path)
        .map_err(|error| AppError::Validation(format!("cannot read {}: {error}", path.display())))
}

async fn load_gear_file(
    state: &State<'_, AppState>,
    port: u16,
    path: &Path,
    known_job: Option<String>,
) -> AppResult<GearLibrary> {
    let source = read_library_source(path)?;
    let client = { state.instances.lock().await.control_for(port)? };
    let raw = client
        .gearswap_source(&source, &path.to_string_lossy())
        .await
        .map_err(|error| {
            AppError::Control(format!("could not load {}: {error}", path.display()))
        })?;
    let sets_tree = raw.get("sets").cloned().unwrap_or(Value::Null);
    let sets = gear::flatten_sets(&sets_tree);
    let detailed = gear::flatten_sets_detailed(&sets_tree);
    let state_value = client.state().await.ok();
    let job = gear::job_from_state(state_value.as_ref()).or_else(|| {
        known_job.and_then(|value| {
            let abbr = gear::job_abbr(&Value::String(value));
            if abbr.is_empty() {
                None
            } else {
                Some(JobInfo {
                    job_id: 0,
                    name: abbr.clone(),
                    abbr,
                    level: 0,
                    sub_job_id: 0,
                    sub_name: String::new(),
                    sub_abbr: String::new(),
                    sub_level: 0,
                    character: String::new(),
                })
            }
        })
    });
    Ok(GearLibrary {
        path: raw
            .get("path")
            .and_then(Value::as_str)
            .unwrap_or_else(|| path.to_str().unwrap_or_default())
            .to_string(),
        sets,
        detailed,
        job,
    })
}

#[tauri::command]
pub async fn gear_equip(
    state: State<'_, AppState>,
    port: u16,
    slot: String,
    item: String,
) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.equip(&slot, &item).await
}

#[tauri::command]
pub async fn gear_wear_set(
    state: State<'_, AppState>,
    port: u16,
    items: BTreeMap<String, String>,
) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    let payload = items
        .into_iter()
        .map(|(slot, item)| json!({"slot": slot, "item": item}))
        .collect::<Vec<_>>();
    // The host injects the whole set in one frame; this is the round trip the Gear page shows,
    // so a regression to per-slot waiting is visible instead of just felt.
    let started = std::time::Instant::now();
    let mut result = client.equip_set(payload).await?;
    if let Value::Object(map) = &mut result {
        map.insert(
            "elapsedMs".into(),
            json!(started.elapsed().as_millis() as u64),
        );
    }
    Ok(result)
}

/// Turn the host's precast/midcast/idle engine on for this client, with the sets it should wear.
#[tauri::command]
pub async fn gear_phase(
    state: State<'_, AppState>,
    port: u16,
    path: Option<String>,
    enabled: bool,
    engaged: Option<String>,
    idle_town: Option<String>,
    idle_field: Option<String>,
    movement: Option<String>,
    options: Option<Value>,
) -> AppResult<Value> {
    // The launcher owns the library file, so the plan carries its text: a client on another
    // machine cannot read the launcher's path, and a local one reads the same text anyway.
    let source = match path.as_deref() {
        Some(value) => Some(read_library_source(Path::new(value))?),
        None => None,
    };
    let client = { state.instances.lock().await.control_for(port)? };
    client
        .phase(
            path.as_deref(),
            source.as_deref(),
            enabled,
            engaged.as_deref(),
            idle_town.as_deref(),
            idle_field.as_deref(),
            movement.as_deref(),
            options.as_ref(),
        )
        .await
}

#[tauri::command]
pub async fn gear_phase_status(state: State<'_, AppState>, port: u16) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.phase_status().await
}

/// The Active gear card's lock: keep the worn set and stop automatic swaps, or resume them.
#[tauri::command]
pub async fn gear_phase_lock(
    state: State<'_, AppState>,
    port: u16,
    locked: bool,
) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.phase_lock(locked).await
}

#[tauri::command]
pub async fn gear_phase_kiting(
    state: State<'_, AppState>,
    port: u16,
    on: bool,
) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.phase_kiting(on).await
}

#[tauri::command]
pub async fn gear_phase_resting(
    state: State<'_, AppState>,
    port: u16,
    on: bool,
) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.phase_resting(on).await
}

#[tauri::command]
pub async fn gear_phase_focus(
    state: State<'_, AppState>,
    port: u16,
    mode: String,
) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.phase_focus(&mode).await
}

#[tauri::command]
pub async fn gear_phase_lock_slots(
    state: State<'_, AppState>,
    port: u16,
    mask: u32,
) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.phase_lock_slots(mask).await
}

#[tauri::command]
pub async fn gear_job_spells(state: State<'_, AppState>, port: u16) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.job_spells().await
}

#[tauri::command]
pub async fn gear_job_abilities(state: State<'_, AppState>, port: u16) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.job_abilities().await
}

#[tauri::command]
pub async fn gear_weapons(state: State<'_, AppState>, port: u16) -> AppResult<Value> {
    let client = { state.instances.lock().await.control_for(port)? };
    client.weapons().await
}

#[tauri::command]
pub async fn gear_apply_set(
    mut sets: BTreeMap<String, BTreeMap<String, String>>,
    path: String,
    items: BTreeMap<String, String>,
    original_path: Option<String>,
    keep_original: bool,
) -> AppResult<GearSetResult> {
    let path = gear::apply_set(
        &mut sets,
        &path,
        items,
        original_path.as_deref(),
        keep_original,
    )?;
    Ok(GearSetResult { sets, path })
}

#[tauri::command]
pub async fn gear_save_library(
    app: AppHandle,
    state: State<'_, AppState>,
    path: String,
    sets: BTreeMap<String, BTreeMap<String, String>>,
    character: String,
    job: String,
    source: String,
) -> AppResult<GearLibrarySaveResult> {
    let config = state.config.lock().await.clone();
    let repo = game::resolve_repo_root_for(&config);
    let resource = app.path().resource_dir().ok();
    let folder = gear::defaults_dir(repo.as_deref(), resource.as_deref());
    let file = Path::new(&path);
    // The bundled job libraries are the launcher's own mock libraries, so a set edited on the
    // Gear page is written back to them (first copy as .lua.bak). An imported GearSwap file is
    // left untouched; the UI offers Save version for that case instead.
    if !folder
        .as_deref()
        .is_some_and(|defaults| gear::is_default_library(file, defaults))
    {
        return Ok(GearLibrarySaveResult {
            path,
            backup: None,
            persistent: false,
        });
    }
    let (target, backup) =
        gear::write_library(file, &sets, &character, &job, &source, Local::now())?;
    Ok(GearLibrarySaveResult {
        path: target.to_string_lossy().into_owned(),
        backup: backup.map(|value| value.to_string_lossy().into_owned()),
        persistent: true,
    })
}

#[tauri::command]
pub async fn gear_save(
    sets: BTreeMap<String, BTreeMap<String, String>>,
    base: String,
    character: String,
    job: String,
    source: String,
    folder: Option<String>,
) -> AppResult<GearSaveResult> {
    let target_folder = folder
        .filter(|value| !value.trim().is_empty())
        .map(|value| config::expand_home(&value))
        .unwrap_or_else(config::downloads_dir);
    std::fs::create_dir_all(&target_folder)?;
    let when = Local::now();
    let version = gear::save_version(
        &target_folder,
        &sets,
        &base,
        &character,
        &job,
        &source,
        when,
    )?;
    let profile_folder = config::data_dir().join("gearswap");
    let profile = gear::write_profile_snapshot(
        &profile_folder,
        &sets,
        &character,
        &job,
        &source,
        &version,
        when,
    )?;
    Ok(GearSaveResult {
        path: version.to_string_lossy().into_owned(),
        profile: profile.to_string_lossy().into_owned(),
    })
}

#[tauri::command]
pub async fn gear_versions() -> AppResult<Vec<GearVersion>> {
    let folder = config::data_dir().join("gearswap");
    let mut versions = Vec::new();
    if let Ok(entries) = std::fs::read_dir(&folder) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|ext| ext.to_str()) != Some("json") {
                continue;
            }
            let Ok(raw) = std::fs::read_to_string(&path) else {
                continue;
            };
            let Ok(value) = serde_json::from_str::<Value>(&raw) else {
                continue;
            };
            versions.push(GearVersion {
                name: path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .unwrap_or_default()
                    .to_string(),
                path: path.to_string_lossy().into_owned(),
                saved_at: value
                    .get("saved_at")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                character: value
                    .get("character")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                job: value
                    .get("job")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
            });
        }
    }
    versions.sort_by(|left, right| right.saved_at.cmp(&left.saved_at));
    Ok(versions)
}

#[tauri::command]
pub async fn gear_defaults(app: AppHandle, state: State<'_, AppState>) -> AppResult<GearDefaults> {
    let config = state.config.lock().await.clone();
    let repo = game::resolve_repo_root_for(&config);
    if config.repo_root.trim().is_empty() {
        if let Some(root) = repo.as_ref() {
            let mut locked = state.config.lock().await;
            locked.repo_root = root.to_string_lossy().into_owned();
            let _ = locked.save();
        }
    }
    let resource = app.path().resource_dir().ok();
    let folder = gear::defaults_dir(repo.as_deref(), resource.as_deref())
        .ok_or_else(|| AppError::Game("the gearswap defaults folder was not found".to_string()))?;
    let mut files = Vec::new();
    for (index, abbr) in gear::JOB_ABBRS.iter().enumerate() {
        let path = folder.join(format!("{abbr}.lua"));
        if path.is_file() {
            files.push(GearDefaultFile {
                job: (index + 1).to_string(),
                abbr: (*abbr).to_string(),
                name: gear::JOB_NAMES[index].to_string(),
                path: path.to_string_lossy().into_owned(),
            });
        }
    }
    Ok(GearDefaults {
        folder: folder.to_string_lossy().into_owned(),
        files,
    })
}

#[tauri::command]
pub async fn game_log(
    state: State<'_, AppState>,
    port: u16,
    lines: usize,
) -> AppResult<Vec<String>> {
    let instances = state.instances.lock().await;
    let instance = instances
        .by_port(port)
        .ok_or_else(|| AppError::Control(format!("no client on control port {port}")))?;
    let name = instance.account.clone();
    drop(instances);
    Ok(game::game_log_tail(lines.clamp(1, 500), &name))
}

async fn fetch_public(api: &ApiClient) -> PublicView {
    let status = match api.status().await {
        Ok(value) => Some(value),
        Err(_) => None,
    };
    let news = api.news(6).await.unwrap_or_default();
    let error = if status.is_none() {
        Some(format!("cannot reach {}", api.base()))
    } else {
        None
    };
    PublicView {
        status,
        news,
        error,
    }
}

async fn fetch_session(api: &ApiClient, token: &str, expires: &str) -> AppResult<SessionView> {
    let me = api.me(token).await?;
    let account = me.get("account").cloned().ok_or_else(|| AppError::Api {
        status: 500,
        code: "bad_reply".to_string(),
        message: "the server did not return an account".to_string(),
    })?;
    let characters = match me.get("characters").and_then(Value::as_array).cloned() {
        Some(characters) => characters,
        None => api.characters(token).await.unwrap_or_default(),
    };
    Ok(SessionView {
        account,
        characters,
        token_expires_at: expires.to_string(),
    })
}

fn choose_character(entry: &AccountEntry, character_id: Option<i64>) -> AppResult<Value> {
    let wanted = character_id.or(entry.character_id);
    if let Some(character) = entry.characters.iter().find(|character| {
        wanted
            .map(|id| character.get("id").and_then(value_i64) == Some(id))
            .unwrap_or(false)
    }) {
        return Ok(character.clone());
    }
    entry
        .characters
        .first()
        .cloned()
        .ok_or_else(|| AppError::Validation(format!("@{} has no character yet", entry.username)))
}

fn character_id_of(value: &Value) -> Option<i64> {
    value.get("id").and_then(value_i64)
}

fn value_i64(value: &Value) -> Option<i64> {
    value
        .as_i64()
        .or_else(|| value.as_u64().and_then(|number| i64::try_from(number).ok()))
        .or_else(|| value.as_str().and_then(|text| text.parse().ok()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn view(login_status: u64, server_online: Option<bool>, uptime_seconds: u64) -> InstanceView {
        InstanceView {
            account: "aria".to_string(),
            character: json!({"name": "Aria", "id": 1}),
            name: "Aria".to_string(),
            port: 54_300,
            pid: 42,
            started_at: 0,
            uptime_seconds,
            alive: true,
            exit_code: None,
            state: Some(json!({"login_status": login_status})),
            metrics: None,
            error: String::new(),
            log_path: String::new(),
            remote: false,
            host: None,
            headless: true,
            sleeping: false,
            server_online,
        }
    }

    #[test]
    fn an_orphaned_session_is_not_in_game() {
        let orphaned = view(2, Some(false), 120);
        assert!(view_orphaned(&orphaned));
        assert!(!view_in_game(&orphaned));
    }

    #[test]
    fn a_verified_or_unknown_session_is_in_game() {
        assert!(view_in_game(&view(2, Some(true), 120)));
        assert!(view_in_game(&view(2, None, 120)));
        assert!(!view_orphaned(&view(2, None, 120)));
        assert!(!view_in_game(&view(0, Some(false), 120)));
    }

    #[test]
    fn a_young_client_is_not_orphaned_yet() {
        let starting = view(2, Some(false), 10);
        assert!(view_in_game(&starting));
        assert!(!view_orphaned(&starting));
    }

    #[test]
    fn a_client_position_is_converted_to_the_server_axis_order() {
        // The control addon reports the client's ground plane as x/y and height as z.
        let client = json!({"x": 102.396, "y": 515.919, "z": -27.149});
        assert_eq!(server_position(&client), Some([102.396, -27.149, 515.919]));
        assert_eq!(
            zone_command(4, &client).unwrap(),
            "//zone 4 102.396 -27.149 515.919"
        );
        assert!(server_position(&json!({"x": 1.0, "y": null, "z": 2.0})).is_none());
    }

    #[test]
    fn near_position_compares_the_ground_plane_and_height() {
        let leader = json!({"x": 102.0, "y": 516.0, "z": -27.0});
        let follower = json!({"x": 104.0, "y": 516.5, "z": -27.4});
        assert!(near_position(&leader, &follower));
        let far = json!({"x": 102.0, "y": 516.0, "z": -400.0});
        assert!(!near_position(&leader, &far));
    }

    #[test]
    fn a_library_is_read_where_the_launcher_can_see_it() {
        let folder = std::env::temp_dir().join(format!("fanxi-gear-source-{}", std::process::id()));
        std::fs::create_dir_all(&folder).unwrap();
        let file = folder.join("SCH.lua");
        std::fs::write(&file, "sets = { idle = { body = 'X' } }\n").unwrap();
        let source = read_library_source(&file).unwrap();
        assert_eq!(source, "sets = { idle = { body = 'X' } }\n");
        // A file that is not on this machine is a launcher error naming the path, not a control
        // round trip to a client that cannot read it either.
        let missing = folder.join("NIN.lua");
        let error = read_library_source(&missing).unwrap_err();
        assert!(error.to_string().contains("cannot read"));
        assert!(error.to_string().contains("NIN.lua"));
        std::fs::remove_dir_all(&folder).ok();
    }
}
