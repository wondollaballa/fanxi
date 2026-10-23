//! Tauri commands: the only bridge between the React UI and the Rust core.

use std::collections::BTreeMap;
use std::path::Path;

use chrono::Local;
use serde::Serialize;
use serde_json::{Value, json};
use tauri::{AppHandle, Manager, State};
use tokio::sync::Mutex;

use crate::api::ApiClient;
use crate::config::{self, AccountEntry, ConfigView, LauncherConfig};
use crate::control::{InstanceManager, InstanceView};
use crate::error::{AppError, AppResult};
use crate::game;
use crate::gear::{self, GearItem, JobInfo};
use crate::icons;

pub struct AppState {
    pub config: Mutex<LauncherConfig>,
    pub instances: Mutex<InstanceManager>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            config: Mutex::new(LauncherConfig::load()),
            instances: Mutex::new(InstanceManager::new()),
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

#[tauri::command]
pub async fn save_settings(
    state: State<'_, AppState>,
    api_url: String,
    game_dir: String,
    repo_root: String,
    api_insecure: bool,
    auto_login: bool,
) -> AppResult<ConfigView> {
    let mut config = state.config.lock().await;
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
    config.repo_root = if repo_root.trim().is_empty() {
        String::new()
    } else {
        config::expand_home(repo_root.trim())
            .to_string_lossy()
            .into_owned()
    };
    config.api_insecure = api_insecure;
    config.auto_login = auto_login;
    config.save()?;
    Ok(ConfigView::from(&*config))
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
    launch_with_config(&state, &config, &account, character_id).await
}

async fn spawn_launch(
    state: &State<'_, AppState>,
    config: &LauncherConfig,
    account: &str,
    fallback_character: Value,
    data: &Value,
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
    let game_dir = if !config.game_dir.trim().is_empty() {
        config::expand_home(&config.game_dir)
    } else {
        game::find_game_dir("").ok_or_else(|| {
            AppError::Game("choose your FINAL FANTASY XI folder in Settings first".to_string())
        })?
    };
    if game::find_host64(config).is_none() {
        return Err(AppError::Game(
            "host64 is not built yet; open Settings and build the game".to_string(),
        ));
    }
    let character = data.get("character").cloned().unwrap_or(fallback_character);
    let mut instances = state.instances.lock().await;
    instances
        .launch(config, account, character, &client, &login_token, &game_dir)
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
    let view = spawn_launch(state, config, &entry.username, character, &data).await?;
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
) -> AppResult<InstanceView> {
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in to the main account first".to_string()));
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
    spawn_launch(state, config, &username, character, &data).await
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
        return Err(AppError::Validation("sign in to the main account first".to_string()));
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
        return Err(AppError::Validation("sign in to the main account first".to_string()));
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
        return Err(AppError::Validation("sign in to the main account first".to_string()));
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
        return Err(AppError::Validation("sign in to the main account first".to_string()));
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
    launch_sub_with_config(&state, &config, sub_id, character_id).await
}

#[tauri::command]
pub async fn launch_team(state: State<'_, AppState>) -> AppResult<LaunchAllResult> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in to the main account first".to_string()));
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
        let character_id = sub
            .pointer("/character/id")
            .and_then(value_i64);
        let running = {
            let instances = state.instances.lock().await;
            instances.running_for(&username).is_some()
        };
        if running {
            continue;
        }
        match launch_sub_with_config(&state, &config, sub_id, character_id).await {
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
pub async fn delete_sub(
    state: State<'_, AppState>,
    sub_id: i64,
    purge: bool,
) -> AppResult<Value> {
    let config = state.config.lock().await.clone();
    if config.token.is_empty() {
        return Err(AppError::Validation("sign in to the main account first".to_string()));
    }
    let api = ApiClient::new(&config.api_url, config.api_insecure)?;
    api.delete_sub(&config.token, sub_id, purge).await
}

#[tauri::command]
pub async fn list_instances(state: State<'_, AppState>) -> AppResult<Vec<InstanceView>> {
    let mut instances = state.instances.lock().await;
    Ok(instances.poll().await)
}

#[tauri::command]
pub async fn stop_instance(state: State<'_, AppState>, port: u16) -> AppResult<()> {
    let mut instances = state.instances.lock().await;
    instances.stop(port).await
}

#[tauri::command]
pub async fn stop_all(state: State<'_, AppState>) -> AppResult<usize> {
    let mut instances = state.instances.lock().await;
    instances.stop_all().await
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

async fn load_gear_file(
    state: &State<'_, AppState>,
    port: u16,
    path: &Path,
    known_job: Option<String>,
) -> AppResult<GearLibrary> {
    let client = { state.instances.lock().await.control_for(port)? };
    let raw = client
        .gearswap(&path.to_string_lossy())
        .await
        .map_err(|error| {
            AppError::Control(format!("could not read {}: {error}", path.display()))
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
    let client = { state.instances.lock().await.control_for(port)? };
    client
        .phase(
            path.as_deref(),
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
