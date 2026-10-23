//! The launcher's local settings and account vault.
//!
//! The format is deliberately identical to the Python launcher's `launcher.json`: a player can move
//! between the two applications without losing accounts, and tokens stay in a mode-0600 file.

use std::collections::BTreeMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::error::AppResult;

pub const DEFAULT_API: &str = "http://127.0.0.1:8080";
const CONFIG_FILE: &str = "launcher.json";

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct AccountEntry {
    pub username: String,
    pub token: String,
    #[serde(default)]
    pub token_expires_at: String,
    #[serde(default)]
    pub account_id: Option<i64>,
    #[serde(default)]
    pub character_id: Option<i64>,
    #[serde(default)]
    pub characters: Vec<Value>,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

impl Default for AccountEntry {
    fn default() -> Self {
        Self {
            username: String::new(),
            token: String::new(),
            token_expires_at: String::new(),
            account_id: None,
            character_id: None,
            characters: Vec::new(),
            extra: BTreeMap::new(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct LauncherConfig {
    pub api_url: String,
    pub token: String,
    pub token_expires_at: String,
    pub username: String,
    pub character_id: Option<i64>,
    pub game_dir: String,
    pub host64: String,
    pub repo_root: String,
    pub api_insecure: bool,
    pub auto_login: bool,
    pub last_page: String,
    pub accounts: Vec<AccountEntry>,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

impl Default for LauncherConfig {
    fn default() -> Self {
        Self {
            api_url: DEFAULT_API.to_string(),
            token: String::new(),
            token_expires_at: String::new(),
            username: String::new(),
            character_id: None,
            game_dir: String::new(),
            host64: String::new(),
            repo_root: String::new(),
            api_insecure: env_flag("FANXI_API_INSECURE"),
            auto_login: true,
            last_page: "home".to_string(),
            accounts: Vec::new(),
            extra: BTreeMap::new(),
        }
    }
}

impl LauncherConfig {
    pub fn load() -> Self {
        let path = config_path();
        let mut config = match fs::read_to_string(&path) {
            Ok(raw) => serde_json::from_str::<LauncherConfig>(&raw).unwrap_or_default(),
            Err(_) => Self::default(),
        };
        if config.api_url.trim().is_empty() {
            config.api_url = DEFAULT_API.to_string();
        }
        config.api_url = config.api_url.trim().trim_end_matches('/').to_string();
        config.load_legacy_account();
        config
    }

    pub fn save(&self) -> AppResult<()> {
        let path = config_path();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let mut value = self.clone();
        value.sync_active_account();
        let bytes = serde_json::to_vec_pretty(&value)?;
        let tmp = path.with_extension("json.tmp");
        write_private(&tmp, &bytes)?;
        #[cfg(windows)]
        {
            let _ = fs::remove_file(&path);
        }
        fs::rename(&tmp, &path)?;
        Ok(())
    }

    pub fn saved_accounts(&self) -> Vec<&AccountEntry> {
        self.accounts
            .iter()
            .filter(|entry| !entry.username.trim().is_empty())
            .collect()
    }

    pub fn account_entry(&self, username: Option<&str>) -> Option<&AccountEntry> {
        let wanted = username.unwrap_or(&self.username).trim().to_lowercase();
        if wanted.is_empty() {
            return None;
        }
        self.accounts
            .iter()
            .find(|entry| entry.username.trim().to_lowercase() == wanted)
    }

    pub fn account_index(&self, username: &str) -> Option<usize> {
        let wanted = username.trim().to_lowercase();
        self.accounts
            .iter()
            .position(|entry| entry.username.trim().to_lowercase() == wanted)
    }

    /// Store or refresh one account's token and make it active.
    pub fn remember_account(
        &mut self,
        account: &Value,
        token: &str,
        expires_at: &str,
        characters: Option<Vec<Value>>,
    ) -> Option<AccountEntry> {
        let username = account
            .get("username")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .trim()
            .to_string();
        if username.is_empty() || token.is_empty() {
            return None;
        }
        let account_id = account.get("id").and_then(value_i64);
        let index = match self.account_index(&username) {
            Some(index) => index,
            None => {
                self.accounts.push(AccountEntry {
                    username: username.clone(),
                    ..AccountEntry::default()
                });
                self.accounts.len() - 1
            }
        };

        let existing_characters = self.accounts[index].characters.clone();
        let entry = &mut self.accounts[index];
        entry.token = token.to_string();
        if !expires_at.is_empty() {
            entry.token_expires_at = expires_at.to_string();
        }
        if account_id.is_some() {
            entry.account_id = account_id;
        }
        if let Some(characters) = characters {
            entry.characters = characters;
        } else if entry.characters.is_empty() {
            entry.characters = existing_characters;
        }
        let ids: Vec<i64> = entry
            .characters
            .iter()
            .filter_map(|character| character.get("id").and_then(value_i64))
            .collect();
        if !ids.contains(&entry.character_id.unwrap_or_default()) {
            entry.character_id = ids.first().copied();
        }

        self.username = username.clone();
        self.token = token.to_string();
        self.token_expires_at = entry.token_expires_at.clone();
        self.character_id = entry.character_id;
        self.account_entry(Some(&username)).cloned()
    }

    pub fn activate_account(&mut self, username: &str) -> bool {
        let Some(index) = self.account_index(username) else {
            return false;
        };
        let entry = self.accounts[index].clone();
        self.username = entry.username;
        self.token = entry.token;
        self.token_expires_at = entry.token_expires_at;
        self.character_id = entry.character_id;
        true
    }

    pub fn forget_account(&mut self, username: &str) {
        let active = self
            .account_entry(Some(username))
            .map(|entry| entry.username.eq_ignore_ascii_case(self.username.trim()))
            .unwrap_or(false);
        if let Some(index) = self.account_index(username) {
            self.accounts.remove(index);
        }
        if active {
            self.token.clear();
            self.token_expires_at.clear();
            self.username.clear();
            self.character_id = None;
            if let Some(first) = self.accounts.first().cloned() {
                self.activate_account(&first.username);
            }
        }
    }

    pub fn clear_session(&mut self) {
        if let Some(index) = self.account_index(&self.username.clone()) {
            self.accounts[index].token.clear();
            self.accounts[index].token_expires_at.clear();
        }
        self.token.clear();
        self.token_expires_at.clear();
        self.username.clear();
        self.character_id = None;
        if let Some(first) = self.accounts.first().cloned() {
            self.activate_account(&first.username);
        }
    }

    pub fn sync_active_account(&mut self) {
        let username = self.username.clone();
        if let Some(index) = self.account_index(&username) {
            let entry = &mut self.accounts[index];
            entry.token = self.token.clone();
            entry.token_expires_at = self.token_expires_at.clone();
            entry.character_id = self.character_id;
        }
    }

    pub fn set_characters(&mut self, username: &str, characters: Vec<Value>) {
        if let Some(index) = self.account_index(username) {
            self.accounts[index].characters = characters;
        }
    }

    pub fn set_character_id(&mut self, username: &str, character_id: Option<i64>) {
        if let Some(index) = self.account_index(username) {
            self.accounts[index].character_id = character_id;
        }
        if username.eq_ignore_ascii_case(self.username.trim()) {
            self.character_id = character_id;
        }
    }

    fn load_legacy_account(&mut self) {
        if self.username.trim().is_empty() || self.token.trim().is_empty() {
            if self.accounts.is_empty() {
                return;
            }
            if self.username.trim().is_empty() {
                let first = self.accounts[0].clone();
                self.username = first.username;
                self.token = first.token;
                self.token_expires_at = first.token_expires_at;
                self.character_id = first.character_id;
            }
            return;
        }
        if self.account_index(&self.username).is_none() {
            self.accounts.push(AccountEntry {
                username: self.username.clone(),
                token: self.token.clone(),
                token_expires_at: self.token_expires_at.clone(),
                account_id: None,
                character_id: self.character_id,
                characters: Vec::new(),
                extra: BTreeMap::new(),
            });
        } else if let Some(index) = self.account_index(&self.username) {
            if self.accounts[index].token.is_empty() {
                self.accounts[index].token = self.token.clone();
            }
        }
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountView {
    pub username: String,
    pub character_id: Option<i64>,
    pub characters: Vec<Value>,
    pub token_expires_at: String,
    pub signed_in: bool,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConfigView {
    pub api_url: String,
    pub username: String,
    pub character_id: Option<i64>,
    pub game_dir: String,
    pub host64: String,
    pub repo_root: String,
    pub api_insecure: bool,
    pub auto_login: bool,
    pub last_page: String,
    pub signed_in: bool,
    pub accounts: Vec<AccountView>,
}

impl From<&LauncherConfig> for ConfigView {
    fn from(config: &LauncherConfig) -> Self {
        Self {
            api_url: config.api_url.clone(),
            username: config.username.clone(),
            character_id: config.character_id,
            game_dir: config.game_dir.clone(),
            host64: config.host64.clone(),
            repo_root: config.repo_root.clone(),
            api_insecure: config.api_insecure,
            auto_login: config.auto_login,
            last_page: config.last_page.clone(),
            signed_in: !config.token.is_empty(),
            accounts: config
                .saved_accounts()
                .into_iter()
                .map(|entry| AccountView {
                    username: entry.username.clone(),
                    character_id: entry.character_id,
                    characters: entry.characters.clone(),
                    token_expires_at: entry.token_expires_at.clone(),
                    signed_in: !entry.token.is_empty(),
                })
                .collect(),
        }
    }
}

pub fn data_dir() -> PathBuf {
    if let Ok(override_dir) = std::env::var("FANXI_LAUNCHER_DIR") {
        if !override_dir.trim().is_empty() {
            return PathBuf::from(shellexpand_home(override_dir.trim()));
        }
    }
    let home = home_dir();
    #[cfg(target_os = "macos")]
    {
        return home
            .join("Library")
            .join("Application Support")
            .join("Fanxi");
    }
    #[cfg(target_os = "windows")]
    {
        let appdata = std::env::var_os("APPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.clone());
        return appdata.join("Fanxi");
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let data_home = std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .filter(|path| !path.as_os_str().is_empty())
            .unwrap_or_else(|| home.join(".local").join("share"));
        return data_home.join("fanxi");
    }
    #[allow(unreachable_code)]
    home.join(".fanxi")
}

pub fn config_path() -> PathBuf {
    data_dir().join(CONFIG_FILE)
}

pub fn log_dir() -> AppResult<PathBuf> {
    let path = data_dir().join("logs");
    fs::create_dir_all(&path)?;
    Ok(path)
}

pub fn downloads_dir() -> PathBuf {
    if let Ok(override_dir) = std::env::var("FANXI_DOWNLOADS_DIR") {
        if !override_dir.trim().is_empty() {
            return PathBuf::from(shellexpand_home(override_dir.trim()));
        }
    }
    let home = home_dir();
    for name in ["Downloads", "downloads"] {
        let candidate = home.join(name);
        if candidate.is_dir() {
            return candidate;
        }
    }
    home
}

pub fn home_dir() -> PathBuf {
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

pub fn expand_home(value: &str) -> PathBuf {
    PathBuf::from(shellexpand_home(value))
}

fn shellexpand_home(value: &str) -> String {
    if let Some(rest) = value.strip_prefix("~/") {
        return home_dir().join(rest).to_string_lossy().into_owned();
    }
    if value == "~" {
        return home_dir().to_string_lossy().into_owned();
    }
    value.to_string()
}

fn write_private(path: &Path, bytes: &[u8]) -> AppResult<()> {
    let mut options = fs::OpenOptions::new();
    options.write(true).create(true).truncate(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(path)?;
    file.write_all(bytes)?;
    file.flush()?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(path, fs::Permissions::from_mode(0o600));
    }
    Ok(())
}

fn value_i64(value: &Value) -> Option<i64> {
    value
        .as_i64()
        .or_else(|| value.as_u64().and_then(|number| i64::try_from(number).ok()))
        .or_else(|| value.as_str().and_then(|text| text.parse().ok()))
}

fn env_flag(name: &str) -> bool {
    std::env::var(name)
        .map(|value| matches!(value.to_lowercase().as_str(), "1" | "true" | "yes" | "on"))
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_config() -> LauncherConfig {
        LauncherConfig {
            api_url: "http://127.0.0.1:8080".to_string(),
            ..LauncherConfig::default()
        }
    }

    #[test]
    fn remembers_and_switches_accounts() {
        let mut config = temp_config();
        let account = serde_json::json!({"id": 7, "username": "Aria"});
        let characters = vec![serde_json::json!({"id": 3, "name": "Aria"})];
        config
            .remember_account(
                &account,
                "token-a",
                "2026-01-01T00:00:00Z",
                Some(characters),
            )
            .unwrap();
        assert_eq!(config.username, "Aria");
        assert_eq!(config.character_id, Some(3));

        let mule = serde_json::json!({"id": 8, "username": "Mule"});
        config
            .remember_account(&mule, "token-b", "", Some(Vec::new()))
            .unwrap();
        assert_eq!(config.username, "Mule");
        assert!(config.activate_account("aria"));
        assert_eq!(config.token, "token-a");
        assert_eq!(config.character_id, Some(3));
    }

    #[test]
    fn forgetting_the_active_account_falls_back() {
        let mut config = temp_config();
        config
            .remember_account(
                &serde_json::json!({"username": "Aria"}),
                "a",
                "",
                Some(Vec::new()),
            )
            .unwrap();
        config
            .remember_account(
                &serde_json::json!({"username": "Mule"}),
                "b",
                "",
                Some(Vec::new()),
            )
            .unwrap();
        config.forget_account("Mule");
        assert_eq!(config.username, "Aria");
        assert_eq!(config.token, "a");
        config.forget_account("Aria");
        assert!(config.username.is_empty());
        assert!(config.token.is_empty());
    }

    #[test]
    fn config_view_hides_tokens() {
        let mut config = temp_config();
        config
            .remember_account(
                &serde_json::json!({"username": "Aria"}),
                "secret",
                "",
                Some(Vec::new()),
            )
            .unwrap();
        let view = ConfigView::from(&config);
        let json = serde_json::to_string(&view).unwrap();
        assert!(!json.contains("secret"));
        assert!(view.signed_in);
    }
}
