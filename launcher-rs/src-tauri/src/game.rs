//! Finding the game, building `host64`, and starting it.
//!
//! The launcher never touches the player's game files itself. It runs the repository's existing
//! Python build driver (`tools/build_posix.py`) exactly as the source installer does, then starts the
//! resulting native host. Keeping that boundary means the Rust launcher can land before the
//! recompiler is ported.

use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::Serialize;
use serde_json::Value;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::mpsc;

use crate::config;
use crate::error::{AppError, AppResult};

pub const HOST64: &str = if cfg!(windows) {
    "host64.exe"
} else {
    "host64"
};
const BUILD_LOG: &str = "build.log";

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BuildEvent {
    pub line: String,
    pub phase: Option<String>,
    pub percent: Option<u32>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BuildResult {
    pub host64: String,
    pub tail: Vec<String>,
}

pub fn resolve_repo_root(configured: &str) -> Option<PathBuf> {
    if let Ok(env_root) = std::env::var("FANXI_REPO_ROOT") {
        if !env_root.trim().is_empty() {
            let path = config::expand_home(env_root.trim());
            if is_repo_root(&path) {
                return Some(path.canonicalize().unwrap_or(path));
            }
        }
    }
    if !configured.trim().is_empty() {
        let path = config::expand_home(configured.trim());
        if is_repo_root(&path) {
            return Some(path.canonicalize().unwrap_or(path));
        }
    }
    let mut starts = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        starts.push(cwd);
    }
    if let Ok(exe) = std::env::current_exe() {
        starts.push(exe);
    }
    for start in starts {
        for ancestor in start.ancestors().take(16) {
            if is_repo_root(ancestor) {
                return Some(ancestor.to_path_buf());
            }
        }
    }
    None
}

/// The checkout for a running config. This also understands the old launcher's `host64` path
/// (`<checkout>/build/host64`) and `FANXI_HOST64`, which matters when a release bundle lives deep
/// inside the checkout instead of next to it.
pub fn resolve_repo_root_for(config: &crate::config::LauncherConfig) -> Option<PathBuf> {
    if let Some(root) = resolve_repo_root(&config.repo_root) {
        return Some(root);
    }
    for hint in [
        Some(config.host64.as_str()),
        std::env::var("FANXI_HOST64").ok().as_deref(),
    ]
    .into_iter()
    .flatten()
    {
        if let Some(root) = repo_root_from_hint(hint) {
            return Some(root);
        }
    }
    None
}

fn repo_root_from_hint(hint: &str) -> Option<PathBuf> {
    if hint.trim().is_empty() {
        return None;
    }
    let path = config::expand_home(hint.trim());
    for ancestor in path.ancestors().take(16) {
        if is_repo_root(ancestor) {
            return Some(
                ancestor
                    .canonicalize()
                    .unwrap_or_else(|_| ancestor.to_path_buf()),
            );
        }
    }
    None
}

pub fn is_repo_root(path: &Path) -> bool {
    path.join("tools").join("build_posix.py").is_file()
        && path.join("runtime").join("portable").is_dir()
        && path.join("host").is_dir()
}

pub fn is_game_dir(path: &Path) -> bool {
    path.join("FFXiMain.dll").is_file()
        && path.join("FFXi.dll").is_file()
        && path.join("ROM").is_dir()
}

pub fn candidate_game_dirs(configured: &str) -> Vec<PathBuf> {
    let home = config::home_dir();
    let mut candidates = Vec::new();
    if !configured.trim().is_empty() {
        candidates.push(config::expand_home(configured.trim()));
    }
    if let Ok(env_dir) = std::env::var("FANXI_GAME_DIR") {
        if !env_dir.trim().is_empty() {
            candidates.push(config::expand_home(env_dir.trim()));
        }
    }
    let games = home.join("Games");
    if games.is_dir() {
        if let Ok(children) = std::fs::read_dir(&games) {
            let mut paths: Vec<PathBuf> = children
                .flatten()
                .map(|entry| entry.path())
                .filter(|path| path.is_dir())
                .collect();
            paths.sort();
            candidates.extend(paths);
        }
    }
    candidates.extend([
        home.join("Games").join("FINAL FANTASY XI"),
        home.join("SquareEnix").join("FINAL FANTASY XI"),
        home.join("Documents").join("FINAL FANTASY XI"),
        home.join("Desktop").join("FINAL FANTASY XI"),
        PathBuf::from("/Applications/FINAL FANTASY XI"),
        PathBuf::from("/Games/FINAL FANTASY XI"),
    ]);
    dedupe(candidates)
}

pub fn find_game_dir(configured: &str) -> Option<PathBuf> {
    candidate_game_dirs(configured)
        .into_iter()
        .find(|candidate| is_game_dir(candidate))
}

pub fn host64_candidates(config: &crate::config::LauncherConfig) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(env_host) = std::env::var("FANXI_HOST64") {
        if !env_host.trim().is_empty() {
            candidates.push(config::expand_home(env_host.trim()));
        }
    }
    if !config.host64.trim().is_empty() {
        candidates.push(config::expand_home(config.host64.trim()));
    }
    if let Some(root) = resolve_repo_root_for(config) {
        candidates.push(root.join("build").join(HOST64));
        candidates.push(
            root.join("build")
                .join("Fanxi.app")
                .join("Contents")
                .join("MacOS")
                .join("Fanxi"),
        );
    }
    dedupe(candidates)
}

pub fn find_host64(config: &crate::config::LauncherConfig) -> Option<PathBuf> {
    host64_candidates(config)
        .into_iter()
        .find(|candidate| candidate.is_file())
}

pub fn build_launch_command(
    host64: &Path,
    game_dir: &Path,
    client: &Value,
    login_token: &str,
) -> Vec<String> {
    let text = |key: &str| {
        client
            .get(key)
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string()
    };
    vec![
        host64.to_string_lossy().into_owned(),
        "--game".to_string(),
        game_dir.to_string_lossy().into_owned(),
        "--server".to_string(),
        text("server"),
        "--user".to_string(),
        text("username"),
        "--login-token".to_string(),
        login_token.to_string(),
        "--authport".to_string(),
        integer_text(client, "auth_port", "54231"),
        "--dataport".to_string(),
        integer_text(client, "data_port", "54230"),
        "--viewport".to_string(),
        integer_text(client, "view_port", "54001"),
    ]
}

pub async fn spawn_host64(
    config: &crate::config::LauncherConfig,
    game_dir: &Path,
    client: &Value,
    login_token: &str,
    control_port: u16,
    log_name: &str,
) -> AppResult<Child> {
    let root = resolve_repo_root_for(config).ok_or_else(|| {
        AppError::Config("the Fanxi checkout was not found; set it in Settings".into())
    })?;
    let host64 = find_host64(config).ok_or_else(|| {
        AppError::Game("host64 is not built yet; build the game in Settings".into())
    })?;
    if !is_game_dir(game_dir) {
        return Err(AppError::Game(format!(
            "{} is not a FINAL FANTASY XI folder: FFXiMain.dll, FFXi.dll and ROM are needed",
            game_dir.display()
        )));
    }

    let command = build_launch_command(&host64, game_dir, client, login_token);
    let log_path = config::log_dir()?.join(format!("game-{}.log", safe_name(log_name)));
    let mut log = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)?;
    use std::io::Write;
    writeln!(log, "\n$ {}", command.join(" "))?;
    let log_err = log.try_clone()?;

    let mut process = Command::new(&command[0]);
    process
        .args(&command[1..])
        .current_dir(&root)
        .stdin(Stdio::null())
        .stdout(Stdio::from(log))
        .stderr(Stdio::from(log_err))
        .env("FFXI_CONTROL", control_port.to_string());
    #[cfg(unix)]
    {
        // A new process group lets "Stop" take the host and any helper it starts together.
        use std::os::unix::process::CommandExt;
        process.as_std_mut().process_group(0);
    }
    let child = process
        .spawn()
        .map_err(|error| AppError::Game(format!("could not start host64: {error}")))?;
    Ok(child)
}

pub async fn build_game(app: &AppHandle, root: &Path, game_dir: &Path) -> AppResult<BuildResult> {
    if !is_game_dir(game_dir) {
        return Err(AppError::Game(format!(
            "{} is not a FINAL FANTASY XI folder: FFXiMain.dll, FFXi.dll and ROM are needed",
            game_dir.display()
        )));
    }
    if !is_repo_root(root) {
        return Err(AppError::Config(format!(
            "{} is not a Fanxi checkout (tools/build_posix.py is missing)",
            root.display()
        )));
    }

    let python = ensure_build_tools(app, root).await?;
    emit(
        app,
        BuildEvent {
            line: format!(
                "Translating and compiling host64 from {}…",
                game_dir.display()
            ),
            phase: None,
            percent: None,
        },
    );

    let mut command = Command::new(&python);
    command
        .arg("tools/build_posix.py")
        .arg("host64")
        .arg("--game")
        .arg(game_dir)
        .current_dir(root)
        .env("FFXI_PROGRESS", "1");
    let (code, tail) = stream_command(app, command, "Building host64").await?;
    if code != 0 {
        return Err(AppError::Game(format!(
            "the build failed (exit {code}).\n\n{}",
            tail.join("\n")
        )));
    }

    let host64 = root.join("build").join(HOST64);
    if !host64.is_file() {
        return Err(AppError::Game(format!(
            "the build finished but {} is missing",
            host64.display()
        )));
    }
    emit(
        app,
        BuildEvent {
            line: format!("Built {}", host64.display()),
            phase: Some("done".to_string()),
            percent: Some(100),
        },
    );
    Ok(BuildResult {
        host64: host64.to_string_lossy().into_owned(),
        tail,
    })
}

async fn ensure_build_tools(app: &AppHandle, root: &Path) -> AppResult<PathBuf> {
    let venv_python = venv_python(root);
    if !venv_python.is_file() {
        emit(
            app,
            BuildEvent {
                line: "Creating the Python environment for the recompiler…".to_string(),
                phase: None,
                percent: None,
            },
        );
        let system_python = system_python();
        let mut command = Command::new(&system_python);
        command
            .arg("-m")
            .arg("venv")
            .arg(root.join(".venv"))
            .current_dir(root);
        let (code, tail) = stream_command(app, command, "Creating .venv").await?;
        if code != 0 {
            return Err(AppError::Game(format!(
                "could not create .venv with {system_python}.\n\n{}",
                tail.join("\n")
            )));
        }
    }
    if !venv_python.is_file() {
        return Err(AppError::Game(format!(
            "the Python environment is missing: {}",
            venv_python.display()
        )));
    }

    let check = Command::new(&venv_python)
        .arg("-c")
        .arg("import capstone, pefile")
        .current_dir(root)
        .output()
        .await?;
    if !check.status.success() {
        emit(
            app,
            BuildEvent {
                line: "Installing the recompiler's Python packages (capstone, pefile)…".to_string(),
                phase: None,
                percent: None,
            },
        );
        let mut command = Command::new(&venv_python);
        command
            .args([
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-q",
                "capstone>=5,<6",
                "pefile>=2023",
            ])
            .current_dir(root);
        let (code, tail) = stream_command(app, command, "Installing capstone and pefile").await?;
        if code != 0 {
            return Err(AppError::Game(format!(
                "the recompiler's Python packages could not be installed.\n\n{}",
                tail.join("\n")
            )));
        }
    }
    Ok(venv_python)
}

fn venv_python(root: &Path) -> PathBuf {
    if cfg!(windows) {
        root.join(".venv").join("Scripts").join("python.exe")
    } else {
        root.join(".venv").join("bin").join("python")
    }
}

fn system_python() -> String {
    std::env::var("FANXI_PYTHON")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| {
            if cfg!(windows) {
                "python".to_string()
            } else {
                "python3".to_string()
            }
        })
}

async fn stream_command(
    app: &AppHandle,
    mut command: Command,
    label: &str,
) -> AppResult<(i32, Vec<String>)> {
    command
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("PYTHONUNBUFFERED", "1");
    let mut child = command
        .spawn()
        .map_err(|error| AppError::Game(format!("could not run {label}: {error}")))?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| AppError::Game(format!("{label}: no output pipe")))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| AppError::Game(format!("{label}: no error pipe")))?;

    let (tx, mut rx) = mpsc::unbounded_channel::<String>();
    let stderr_task = tokio::spawn(async move {
        let mut lines = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let _ = tx.send(line);
        }
    });

    let log_path = config::log_dir()?.join(BUILD_LOG);
    let mut log = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)?;
    use std::io::Write;
    writeln!(log, "\n== {label} ==")?;

    let mut tail: Vec<String> = Vec::new();
    let mut emit_line = |line: String| {
        let (phase, percent) = parse_progress(&line);
        if let Ok(mut log) = log.try_clone() {
            let _ = writeln!(log, "{line}");
        }
        tail.push(line.clone());
        if tail.len() > 40 {
            tail.remove(0);
        }
        emit(
            app,
            BuildEvent {
                line,
                phase,
                percent,
            },
        );
    };

    let mut stdout_lines = BufReader::new(stdout).lines();
    loop {
        tokio::select! {
            line = stdout_lines.next_line() => {
                match line {
                    Ok(Some(line)) => emit_line(line),
                    Ok(None) => break,
                    Err(error) => {
                        emit_line(format!("output error: {error}"));
                        break;
                    }
                }
            }
            Some(line) = rx.recv() => emit_line(line),
        }
    }
    while let Ok(line) = rx.try_recv() {
        emit_line(line);
    }
    let status = child.wait().await?;
    let _ = stderr_task.await;
    Ok((status.code().unwrap_or(1), tail))
}

fn parse_progress(line: &str) -> (Option<String>, Option<u32>) {
    if let Some(rest) = line.strip_prefix("@phase ") {
        return (Some(rest.trim().to_string()), None);
    }
    if let Some(rest) = line.strip_prefix("@progress ") {
        let mut parts = rest.split_whitespace();
        if let (Some(done), Some(total)) = (parts.next(), parts.next()) {
            if let (Ok(done), Ok(total)) = (done.parse::<u32>(), total.parse::<u32>()) {
                let percent = if total == 0 { 100 } else { done * 100 / total };
                return (None, Some(percent.min(100)));
            }
        }
    }
    (None, None)
}

fn emit(app: &AppHandle, event: BuildEvent) {
    let _ = app.emit("build-progress", event);
}

pub fn build_log_tail(lines: usize) -> Vec<String> {
    let path = config::log_dir().map(|dir| dir.join(BUILD_LOG)).ok();
    let Some(path) = path else {
        return Vec::new();
    };
    let Ok(text) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    let all: Vec<String> = text.lines().map(ToOwned::to_owned).collect();
    let start = all.len().saturating_sub(lines);
    all[start..].to_vec()
}

pub fn game_log_tail(lines: usize, name: &str) -> Vec<String> {
    let Ok(dir) = config::log_dir() else {
        return Vec::new();
    };
    let path = dir.join(format!("game-{}.log", safe_name(name)));
    let Ok(text) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    let all: Vec<String> = text.lines().map(ToOwned::to_owned).collect();
    let start = all.len().saturating_sub(lines);
    all[start..].to_vec()
}

pub fn open_data_dir() -> AppResult<()> {
    let dir = config::data_dir();
    std::fs::create_dir_all(&dir)?;
    #[cfg(target_os = "macos")]
    let mut command = {
        let mut command = std::process::Command::new("open");
        command.arg(&dir);
        command
    };
    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = std::process::Command::new("cmd");
        command.args(["/C", "start", ""]).arg(&dir);
        command
    };
    #[cfg(all(unix, not(target_os = "macos")))]
    let mut command = {
        let mut command = std::process::Command::new("xdg-open");
        command.arg(&dir);
        command
    };
    command
        .spawn()
        .map_err(|error| AppError::Io(format!("could not open {}: {error}", dir.display())))?;
    Ok(())
}

pub fn now_epoch() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

pub fn safe_name(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.') {
            out.push(ch);
        } else {
            out.push('-');
        }
    }
    let trimmed = out.trim_matches(|ch| ch == '-' || ch == '.').to_string();
    if trimmed.is_empty() || trimmed.chars().all(|ch| ch == '.') {
        "game".to_string()
    } else {
        trimmed
    }
}

fn integer_text(client: &Value, key: &str, fallback: &str) -> String {
    client
        .get(key)
        .and_then(Value::as_i64)
        .map(|number| number.to_string())
        .unwrap_or_else(|| fallback.to_string())
}

fn dedupe(paths: Vec<PathBuf>) -> Vec<PathBuf> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for path in paths {
        let resolved = path.canonicalize().unwrap_or(path);
        if seen.insert(resolved.clone()) {
            out.push(resolved);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_names_are_filesystem_friendly() {
        assert_eq!(safe_name("Aria / Mule"), "Aria---Mule");
        assert_eq!(safe_name("..."), "game");
    }

    #[test]
    fn finds_checkout_from_host64_hint() {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let base = std::env::temp_dir().join(format!("fanxi-repo-detection-{stamp}"));
        let repo = base.join("repo");
        std::fs::create_dir_all(repo.join("tools")).unwrap();
        std::fs::create_dir_all(repo.join("runtime").join("portable")).unwrap();
        std::fs::create_dir_all(repo.join("host")).unwrap();
        std::fs::create_dir_all(repo.join("build")).unwrap();
        std::fs::write(repo.join("tools").join("build_posix.py"), b"").unwrap();
        std::fs::write(repo.join("build").join(HOST64), b"").unwrap();
        let host64 = repo.join("build").join(HOST64);
        let found =
            repo_root_from_hint(&host64.to_string_lossy()).expect("checkout from host64 path");
        assert_eq!(found, repo.canonicalize().unwrap());
        let _ = std::fs::remove_dir_all(base);
    }

    #[test]
    fn progress_lines_are_understood() {
        assert_eq!(
            parse_progress("@phase compile"),
            (Some("compile".to_string()), None)
        );
        assert_eq!(parse_progress("@progress 5 10"), (None, Some(50)));
        assert_eq!(parse_progress("ordinary output"), (None, None));
    }
}
