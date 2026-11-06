//! Finding the game, building `host64`, and starting it.
//!
//! The launcher never touches the player's game files itself. It runs the repository's Python
//! build driver — `tools/build_posix.py` (clang) on macOS and Linux, `tools/build.py` (MSVC) on
//! Windows — exactly as the source installer does, then starts the resulting native host. Keeping
//! that boundary means the Rust launcher can land before the recompiler is ported.

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
use crate::display;
use crate::error::{AppError, AppResult};

/// The game executable the build produces.
///
/// The build *target* is still called `host64` (`python tools/build.py host64`); the artifact is
/// Fanxi, matching the macOS bundle, whose executable is `Fanxi.app/Contents/MacOS/Fanxi`.
pub const GAME_BIN: &str = if cfg!(windows) { "Fanxi.exe" } else { "fanxi" };
pub const GAME_BIN_HEADLESS: &str = if cfg!(windows) {
    "Fanxi-headless.exe"
} else {
    "Fanxi-headless"
};
/// What earlier builds wrote. Still searched so an existing `build/host64` keeps working.
pub const LEGACY_GAME_BIN: &str = if cfg!(windows) {
    "host64.exe"
} else {
    "host64"
};
pub const LEGACY_GAME_BIN_HEADLESS: &str = if cfg!(windows) {
    "host64-headless.exe"
} else {
    "host64-headless"
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

/// The checkout for a running config. This also understands an earlier launcher's host path
/// (`<checkout>/build/fanxi`, formerly `build/host64`) and `FANXI_HOST64`, which matters when a
/// release bundle lives deep inside the checkout instead of next to it.
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
    let tools = path.join("tools");
    (tools.join("build_posix.py").is_file() || tools.join("build.py").is_file())
        && path.join("runtime").join("portable").is_dir()
        && path.join("host").is_dir()
}

/// The build driver this platform uses.
///
/// `tools/build_posix.py` drives clang on macOS and Linux; `tools/build.py` drives MSVC on Windows
/// and activates the Visual Studio environment itself through `vswhere` and `vcvarsall`.
pub fn build_driver() -> &'static str {
    if cfg!(windows) {
        "tools/build.py"
    } else {
        "tools/build_posix.py"
    }
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
        candidates.push(root.join("build").join(GAME_BIN));
        candidates.push(root.join("build").join(GAME_BIN_HEADLESS));
        candidates.push(root.join("build").join(LEGACY_GAME_BIN));
        candidates.push(root.join("build").join(LEGACY_GAME_BIN_HEADLESS));
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

pub fn find_host64_headless(config: &crate::config::LauncherConfig) -> Option<PathBuf> {
    let root = resolve_repo_root_for(config)?;
    let build = root.join("build");
    [GAME_BIN_HEADLESS, LEGACY_GAME_BIN_HEADLESS]
        .into_iter()
        .map(|name| build.join(name))
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
    headless: bool,
) -> AppResult<Child> {
    let root = resolve_repo_root_for(config).ok_or_else(|| {
        AppError::Config("the Fanxi checkout was not found; set it in Settings".into())
    })?;
    let host64 = if headless {
        find_host64_headless(config).ok_or_else(|| {
            AppError::Game(format!(
                "the headless host is not built yet; run {} host64-headless",
                build_driver()
            ))
        })?
    } else {
        find_host64(config).ok_or_else(|| {
            AppError::Game("the game is not built yet: press Build in Settings".into())
        })?
    };
    if !is_game_dir(game_dir) {
        return Err(AppError::Game(format!(
            "{} is not a FINAL FANTASY XI folder: FFXiMain.dll, FFXi.dll and ROM are needed",
            game_dir.display()
        )));
    }

    let mut command = build_launch_command(&host64, game_dir, client, login_token);
    if headless {
        let data = config::data_dir()
            .join("headless")
            .join(safe_name(log_name));
        std::fs::create_dir_all(&data)?;
        command.extend([
            "--fps-divisor".to_string(),
            "2".to_string(),
            "--data-dir".to_string(),
            data.to_string_lossy().into_owned(),
        ]);
    } else {
        // The display overlay is loaded after the host's saved.reg, so the size and mode chosen in
        // Settings win over whatever a previous run left in the game's own settings.
        let overlay = display::write_overlay(&config.game_display).map_err(|error| {
            AppError::Game(format!(
                "cannot write the game window settings ({}): {error}",
                display::overlay_path().display()
            ))
        })?;
        command.extend([
            "--reg-final".to_string(),
            overlay.to_string_lossy().into_owned(),
        ]);
        if config.limit_main_fps {
            command.extend(["--fps-divisor".to_string(), "2".to_string()]);
        }
    }
    let log_path = config::log_dir()?.join(format!(
        "game-{}{}.log",
        safe_name(log_name),
        if headless { "-headless" } else { "" }
    ));
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
        .env("FFXI_CONTROL", control_port.to_string())
        .env("FANXI_API_URL", &config.api_url)
        .env("FANXI_API_TOKEN", &config.token);
    if headless {
        process
            .env("SDL_VIDEO_DRIVER", "dummy")
            .env("SDL_AUDIO_DRIVER", "dummy")
            .env("FFXI_FX", "0");
    } else if let Some(spec) = display::game_window_spec(&config.monitor) {
        // The sign-in window and the game window open here instead of on the main display. The
        // coordinates are the window API's own units (screen points on macOS).
        process.env("FANXI_DISPLAY", spec);
    }
    #[cfg(unix)]
    {
        // A new process group lets "Stop" take the host and any helper it starts together.
        use std::os::unix::process::CommandExt;
        process.as_std_mut().process_group(0);
    }
    let child = process
        .spawn()
        .map_err(|error| AppError::Game(format!("could not start Fanxi: {error}")))?;
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
            "{} is not a Fanxi checkout ({} is missing)",
            root.display(),
            build_driver()
        )));
    }
    let driver = build_driver();
    if !root.join(driver).is_file() {
        return Err(AppError::Config(format!(
            "{} does not contain {driver}",
            root.display()
        )));
    }
    if cfg!(windows) {
        check_windows_toolchain()?;
    }

    let python = ensure_build_tools(app, root).await?;

    // prepare.py identifies the retail build and unpacks the two DLLs into generated/.  A checkout
    // that was cloned and never prepared has no generated/build.json, and every driver refuses to
    // translate without one — so the launcher runs it, and re-runs it when the player points at a
    // different game folder.
    if needs_prepare(root, game_dir) {
        emit(
            app,
            BuildEvent {
                line: format!("Reading the game build from {}…", game_dir.display()),
                phase: None,
                percent: None,
            },
        );
        let mut prepare = Command::new(&python);
        prepare
            .arg("tools/prepare.py")
            .arg("--game")
            .arg(game_dir)
            .current_dir(root)
            .env("FFXI_PROGRESS", "1");
        let (code, tail) = stream_command(app, prepare, "Preparing the game files").await?;
        if code != 0 {
            return Err(AppError::Game(format!(
                "could not read the game files (exit {code}).\n\n{}",
                tail.join("\n")
            )));
        }
    }

    emit(
        app,
        BuildEvent {
            line: format!(
                "Translating and compiling Fanxi from {}…",
                game_dir.display()
            ),
            phase: None,
            percent: None,
        },
    );

    let mut command = Command::new(&python);
    command.current_dir(root).env("FFXI_PROGRESS", "1");
    if cfg!(windows) {
        // The MSVC driver reads the game folder that prepare.py recorded, so it takes no --game.
        command.arg("tools/build.py").arg("host64");
        if let Some(sdl3) = sdl3_dir() {
            command.env("SDL3_DIR", sdl3);
        }
    } else {
        command
            .arg("tools/build_posix.py")
            .arg("host64")
            .arg("--game")
            .arg(game_dir);
    }
    let (code, tail) = stream_command(app, command, "Building Fanxi").await?;
    if code != 0 {
        return Err(AppError::Game(format!(
            "the build failed (exit {code}).\n\n{}",
            tail.join("\n")
        )));
    }

    let host64 = root.join("build").join(GAME_BIN);
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

/// Whether `generated/build.json` was written for a different game folder, or never written.
fn needs_prepare(root: &Path, game_dir: &Path) -> bool {
    let chosen = root.join("generated").join("build.json");
    let Ok(text) = std::fs::read_to_string(&chosen) else {
        return true;
    };
    let Ok(value) = serde_json::from_str::<Value>(&text) else {
        return true;
    };
    let Some(game) = value.get("game").and_then(Value::as_str) else {
        return true;
    };
    match (Path::new(game).canonicalize(), game_dir.canonicalize()) {
        (Ok(prepared), Ok(requested)) => prepared != requested,
        _ => Path::new(game) != game_dir,
    }
}

#[cfg(not(windows))]
fn check_windows_toolchain() -> AppResult<()> {
    Ok(())
}

/// The two things `tools/build.py` needs that a player's machine may not have.
#[cfg(windows)]
fn check_windows_toolchain() -> AppResult<()> {
    let program_files = std::env::var("ProgramFiles(x86)")
        .unwrap_or_else(|_| r"C:\Program Files (x86)".to_string());
    let vswhere = Path::new(&program_files)
        .join("Microsoft Visual Studio")
        .join("Installer")
        .join("vswhere.exe");
    if !vswhere.is_file() {
        return Err(AppError::Game(
            "Visual Studio Build Tools are missing. Install them with the \"Desktop development \
             with C++\" workload (the MSVC v143 build tools and the Windows SDK), then press \
             Build again."
                .to_string(),
        ));
    }
    if sdl3_dir().is_none() {
        return Err(AppError::Game(format!(
            "SDL3 is missing. Unpack the SDL3 VC development package into {} so it contains \
             include\\SDL3\\SDL.h and lib\\x64\\SDL3.lib, or set SDL3_DIR to the package folder.",
            config::data_dir().join("tools").join("SDL3").display()
        )));
    }
    Ok(())
}

#[cfg(not(windows))]
fn sdl3_dir() -> Option<PathBuf> {
    None
}

/// The SDL3 VC package `tools/build.py` links against: `$SDL3_DIR` if set, else the managed copy
/// under the launcher's data folder, else the development default the driver itself uses.
#[cfg(windows)]
fn sdl3_dir() -> Option<PathBuf> {
    fn is_package(path: &Path) -> bool {
        path.join("include").join("SDL3").join("SDL.h").is_file()
    }
    if let Ok(value) = std::env::var("SDL3_DIR") {
        let value = value.trim();
        if !value.is_empty() && is_package(Path::new(value)) {
            return Some(PathBuf::from(value));
        }
    }
    [
        config::data_dir().join("tools").join("SDL3"),
        PathBuf::from(r"C:\Dev\SDL3\SDL3-3.4.16"),
    ]
    .into_iter()
    .find(|candidate| is_package(candidate))
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

pub(crate) fn venv_python(root: &Path) -> PathBuf {
    if cfg!(windows) {
        root.join(".venv").join("Scripts").join("python.exe")
    } else {
        root.join(".venv").join("bin").join("python")
    }
}

/// Whether `python` offers a current TLS stack, asked of the interpreter itself.
///
/// Apple's `/usr/bin/python3` (the Command Line Tools interpreter) is Python 3.9 on LibreSSL
/// 2.8.3: no TLS 1.3, and its `ssl` module drops the SNI for names that begin with an IPv4
/// literal, so `https://172.236.103.193.sslip.io` is answered with a TLS internal error by
/// Caddy. A `.venv` built from that interpreter can build `host64`, but it cannot run
/// `scripts/linux_boxes.py` against an HTTPS API. The TLS 1.3 flag is the cheap proxy for both
/// faults; every current OpenSSL and LibreSSL build has it.
pub(crate) fn python_has_modern_tls(python: &Path) -> bool {
    if python.components().count() > 1 && !python.is_file() {
        return false;
    }
    std::process::Command::new(python)
        .args([
            "-c",
            "import ssl, sys; sys.exit(0 if ssl.HAS_TLSv1_3 else 1)",
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

pub(crate) fn system_python() -> String {
    if let Some(given) = std::env::var("FANXI_PYTHON")
        .ok()
        .filter(|value| !value.trim().is_empty())
    {
        return given;
    }
    if cfg!(windows) {
        return "python".to_string();
    }
    // The interpreter decides the architecture of everything it starts: clang spawned by a process
    // running under Rosetta defaults to x86_64, so a python from PATH that is an Intel or Anaconda
    // build builds the whole client x86_64, and it then runs under Rosetta (`file build/fanxi`
    // says x86_64 rather than arm64). On macOS prefer the native Homebrew interpreter, which has
    // a current TLS stack, and the system's own interpreter as the last resort; `tools/setup.py`
    // picks the system one for the same architecture reason.
    if cfg!(target_os = "macos") {
        let homebrew = if cfg!(target_arch = "aarch64") {
            "/opt/homebrew/bin/python3"
        } else {
            "/usr/local/bin/python3"
        };
        if python_has_modern_tls(Path::new(homebrew)) {
            return homebrew.to_string();
        }
        if Path::new("/usr/bin/python3").is_file() {
            return "/usr/bin/python3".to_string();
        }
    }
    "python3".to_string()
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
        std::fs::write(repo.join("build").join(GAME_BIN), b"").unwrap();
        let host64 = repo.join("build").join(GAME_BIN);
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
