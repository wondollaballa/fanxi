//! The Linux box registry and orphan cleanup for headless launches.
//!
//! `scripts/linux_boxes.py` records the remote boxes it starts in
//! `~/.fanxi-linux-boxes.json` so the launcher can attach to their tunnels. That registry is also
//! the only record the launcher has of a box whose tunnel died: the remote `host64` can still be
//! signed in and holding the account, so launching a second client would just fight it for the
//! session. A headless launch therefore stops everything the registry knows about the account -
//! and any local `host64` the launcher did not spawn - before it starts a new client.

use std::path::PathBuf;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde_json::Value;
use tokio::process::Command;

use crate::config;
use crate::control::ControlClient;
use crate::error::AppResult;

pub fn state_path() -> PathBuf {
    config::home_dir().join(".fanxi-linux-boxes.json")
}

pub fn load() -> Vec<Value> {
    std::fs::read_to_string(state_path())
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .unwrap_or_default()
}

fn save(entries: &[Value]) -> AppResult<()> {
    let path = state_path();
    if entries.is_empty() {
        let _ = std::fs::remove_file(&path);
        return Ok(());
    }
    let temp = path.with_extension("json.tmp");
    let text = serde_json::to_string_pretty(entries)?;
    std::fs::write(&temp, format!("{text}\n"))?;
    std::fs::rename(&temp, &path)?;
    Ok(())
}

fn entry_user(entry: &Value) -> &str {
    entry.get("user").and_then(Value::as_str).unwrap_or("")
}

fn user_matches(value: &str, account: &str) -> bool {
    value.trim().eq_ignore_ascii_case(account.trim())
}

/// Stop every box in the registry that belongs to `account` and drop its entry. This covers a
/// remote box whose tunnel is down as well as the entry the helper writes for the main client.
pub async fn stop_account(account: &str) -> Vec<String> {
    let mut entries = load();
    let mut keep = Vec::with_capacity(entries.len());
    let mut notes = Vec::new();
    let mut removed = false;
    for entry in entries.drain(..) {
        if !user_matches(entry_user(&entry), account) {
            keep.push(entry);
            continue;
        }
        removed = true;
        let port = entry.get("port").and_then(Value::as_u64).unwrap_or(0) as u16;
        let ssh = entry.get("ssh").and_then(Value::as_str).unwrap_or("");
        let remote_pid = entry.get("remote_pid").and_then(Value::as_u64).unwrap_or(0);
        let tunnel_pid = entry.get("tunnel_pid").and_then(Value::as_u64).unwrap_or(0) as i32;

        if port > 0 {
            let _ = tokio::time::timeout(
                Duration::from_secs(2),
                ControlClient::new(port).command("/shutdown"),
            )
            .await;
        }
        if !ssh.trim().is_empty() {
            notes.push(stop_remote(ssh, account, remote_pid).await);
        }
        if tunnel_pid > 0 {
            terminate(tunnel_pid as u32);
        }
        notes.push(format!("removed @{account} from the box registry"));
    }
    if removed {
        let _ = save(&keep);
    }
    notes.extend(stop_local_orphans(account).await);
    notes
}

async fn stop_remote(ssh: &str, account: &str, remote_pid: u64) -> String {
    let command = remote_kill_command(account, remote_pid);
    let mut child = Command::new("ssh");
    child
        .arg("-n")
        .arg("-o")
        .arg("BatchMode=yes")
        .arg("-o")
        .arg("ConnectTimeout=8")
        .arg(ssh)
        .arg(command)
        .kill_on_drop(true);
    match tokio::time::timeout(Duration::from_secs(15), child.status()).await {
        Ok(Ok(status)) if status.success() => format!("stopped remote @{account}"),
        Ok(Ok(status)) => format!("remote stop for @{account} exited {status}"),
        Ok(Err(error)) => format!("remote stop for @{account} failed: {error}"),
        Err(_) => format!("remote stop for @{account} timed out"),
    }
}

/// The helper records the `bash -c` wrapper's pid, not the `host64` it starts, so kill by the
/// account argument as well as by the recorded pid. The `[h]` keeps `pgrep` from matching the
/// command line of the shell that runs this command.
fn remote_kill_command(account: &str, remote_pid: u64) -> String {
    let account = shell_single_quote(account);
    let pattern = format!("[h]ost64.*--user {account}");
    format!(
        "pids=$(pgrep -f '{pattern}' 2>/dev/null || true); \
         if [ -n \"$pids\" ]; then kill $pids 2>/dev/null; fi; \
         if [ {remote_pid} -gt 0 ]; then pkill -P {remote_pid} 2>/dev/null; kill {remote_pid} 2>/dev/null; fi; \
         sleep 1; \
         if [ -n \"$pids\" ]; then kill -9 $pids 2>/dev/null; fi; \
         if [ {remote_pid} -gt 0 ]; then kill -9 {remote_pid} 2>/dev/null; fi; \
         true"
    )
}

fn shell_single_quote(value: &str) -> String {
    value.replace('\'', "").replace('\n', " ")
}

/// A local game client found on the machine, with the control port it is listening on (when
/// it has one) and how long it has been running.
#[derive(Clone, Debug)]
pub struct LocalGame {
    pub pid: u32,
    pub account: String,
    pub port: Option<u16>,
    pub age_secs: u64,
    /// A visible `host64` is user-started and is never auto-reaped; only headless clients are.
    pub headless: bool,
}

impl LocalGame {
    fn describe(&self) -> String {
        match self.port {
            Some(port) => format!("@{}, pid {}, :{}", self.account, self.pid, port),
            None => format!("@{}, pid {}", self.account, self.pid),
        }
    }
}

/// Every local `host64`/`host64-headless` process, including ones this launcher did not spawn.
/// `ps` is the source of truth for both the account argument and the process age.
pub fn local_games() -> Vec<LocalGame> {
    #[cfg(unix)]
    {
        let Ok(output) = std::process::Command::new("ps")
            .args(["-axo", "pid=,etime=,command="])
            .output()
        else {
            return Vec::new();
        };
        let me = std::process::id();
        String::from_utf8_lossy(&output.stdout)
            .lines()
            .filter_map(|line| {
                let line = line.trim_start();
                let mut parts = line.split_whitespace();
                let pid: u32 = parts.next()?.parse().ok()?;
                let etime = parts.next()?;
                let offset = line.find(etime)? + etime.len();
                let command = line[offset..].trim_start();
                if pid == me || !is_game_process(command) {
                    return None;
                }
                let account = user_arg(command)?;
                Some(LocalGame {
                    pid,
                    account,
                    port: listening_port(pid),
                    age_secs: parse_etime_secs(etime),
                    headless: is_headless_process(command),
                })
            })
            .collect()
    }
    #[cfg(not(unix))]
    {
        Vec::new()
    }
}

/// Parse `ps` elapsed time: `mm:ss`, `hh:mm:ss`, or `dd-hh:mm:ss`.
pub fn parse_etime_secs(text: &str) -> u64 {
    let (days, rest) = match text.split_once('-') {
        Some((days, rest)) => (days.parse::<u64>().unwrap_or(0), rest),
        None => (0, text),
    };
    let parts: Vec<u64> = rest
        .split(':')
        .filter_map(|part| part.parse::<u64>().ok())
        .collect();
    let (hours, minutes, seconds) = match parts.as_slice() {
        [hours, minutes, seconds] => (*hours, *minutes, *seconds),
        [minutes, seconds] => (0, *minutes, *seconds),
        [seconds] => (0, 0, *seconds),
        _ => (0, 0, 0),
    };
    days * 86_400 + hours * 3_600 + minutes * 60 + seconds
}

/// The TCP port a pid is listening on, via lsof. A game that has not opened its control socket
/// yet returns `None` and is protected by the grace period instead of being killed.
fn listening_port(pid: u32) -> Option<u16> {
    let pid = pid.to_string();
    let output = std::process::Command::new("lsof")
        .args(["-nP", "-a", "-p", &pid, "-iTCP", "-sTCP:LISTEN", "-Fn"])
        .output()
        .ok()
        .or_else(|| {
            std::process::Command::new("/usr/sbin/lsof")
                .args(["-nP", "-a", "-p", &pid, "-iTCP", "-sTCP:LISTEN", "-Fn"])
                .output()
                .ok()
        })?;
    parse_lsof_port(&String::from_utf8_lossy(&output.stdout))
}

pub fn parse_lsof_port(output: &str) -> Option<u16> {
    output.lines().find_map(|line| {
        let name = line.strip_prefix('n')?;
        name.rsplit(':').next()?.parse().ok()
    })
}

async fn port_in_game(port: u16) -> bool {
    let Ok(Ok(state)) = tokio::time::timeout(
        Duration::from_millis(1_200),
        ControlClient::new(port).state(),
    )
    .await
    else {
        return false;
    };
    state.get("login_status").and_then(Value::as_u64) == Some(2)
}

/// Split local games into "kill" and "keep" lists. Anything that answers `state` with
/// `login_status == 2` is a good active client and is never returned in the kill list. Young
/// processes are held back so a client that is still loading is not mistaken for an orphan.
async fn collect_local_orphans(
    account: Option<&str>,
    grace: Duration,
    protected: &[u32],
) -> (Vec<LocalGame>, Vec<String>) {
    let mut kill = Vec::new();
    let mut notes = Vec::new();
    for game in local_games() {
        if let Some(account) = account {
            if !user_matches(&game.account, account) {
                continue;
            }
        }
        if protected.contains(&game.pid) {
            notes.push(format!("kept {} (tracked)", game.describe()));
            continue;
        }
        let in_game = match game.port {
            Some(port) => port_in_game(port).await,
            None => false,
        };
        if let Some(note) = local_keep_note(&game, grace, protected, in_game) {
            notes.push(note);
            continue;
        }
        kill.push(game);
    }
    (kill, notes)
}

/// Why a local game is kept, or `None` when it is eligible for cleanup.
pub fn local_keep_note(
    game: &LocalGame,
    grace: Duration,
    protected: &[u32],
    in_game: bool,
) -> Option<String> {
    if protected.contains(&game.pid) {
        return Some(format!("kept {} (tracked)", game.describe()));
    }
    if !game.headless {
        return Some(format!("kept {} (visible client)", game.describe()));
    }
    if in_game {
        return Some(format!("kept {} (in game)", game.describe()));
    }
    if game.age_secs < grace.as_secs() {
        return Some(format!(
            "kept {} (starting, {}s old)",
            game.describe(),
            game.age_secs
        ));
    }
    None
}

async fn terminate_games(games: &[LocalGame]) -> Vec<String> {
    if games.is_empty() {
        return Vec::new();
    }
    for game in games {
        terminate(game.pid);
    }
    tokio::time::sleep(Duration::from_millis(800)).await;
    let remaining: Vec<u32> = games
        .iter()
        .map(|game| game.pid)
        .filter(|pid| pid_alive(*pid))
        .collect();
    for pid in &remaining {
        force_kill(*pid);
    }
    if !remaining.is_empty() {
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    games
        .iter()
        .map(|game| format!("stopped orphan {}", game.describe()))
        .collect()
}

/// A targeted cleanup for one account: keep anything in game, kill stale copies.
pub async fn stop_local_orphans(account: &str) -> Vec<String> {
    let (kill, mut notes) = collect_local_orphans(Some(account), Duration::ZERO, &[]).await;
    notes.extend(terminate_games(&kill).await);
    notes
}

/// The pre-launch reaper: every local game older than the grace period that is not in game, and
/// every registry entry whose tunnel has been dead/unanswered for the same grace period.
pub async fn reap_orphans_for_launch(protected: &[u32]) -> Vec<String> {
    let grace = Duration::from_secs(120);
    let (kill, mut notes) = collect_local_orphans(None, grace, protected).await;
    notes.extend(terminate_games(&kill).await);
    notes.extend(reap_registry(grace).await);
    notes
}

/// Remove registry entries whose control port no longer answers and whose start is older than
/// the grace period; the remote helper reaps the now-untracked process on the next launch.
async fn reap_registry(grace: Duration) -> Vec<String> {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|value| value.as_secs())
        .unwrap_or(0);
    let entries = load();
    let mut keep = Vec::with_capacity(entries.len());
    let mut notes = Vec::new();
    let mut removed = false;
    for entry in entries {
        let ssh = entry.get("ssh").and_then(Value::as_str).unwrap_or("");
        let port = entry.get("port").and_then(Value::as_u64).unwrap_or(0) as u16;
        if ssh.trim().is_empty() || (port > 0 && port_in_game(port).await) {
            keep.push(entry);
            continue;
        }
        let started = entry.get("started").and_then(Value::as_u64).unwrap_or(0);
        if started > 0 && now.saturating_sub(started) < grace.as_secs() {
            keep.push(entry);
            continue;
        }
        let user = entry_user(&entry);
        let tunnel_pid = entry.get("tunnel_pid").and_then(Value::as_u64).unwrap_or(0) as u32;
        if tunnel_pid > 0 {
            terminate(tunnel_pid);
            tokio::time::sleep(Duration::from_millis(300)).await;
            if pid_alive(tunnel_pid) {
                force_kill(tunnel_pid);
            }
        }
        removed = true;
        notes.push(format!(
            "reaped stale tunnel for @{user} (port {port}); remote cleanup follows"
        ));
    }
    if removed {
        let _ = save(&keep);
    }
    notes
}

/// Wait for the local processes that match the account to disappear.
pub async fn wait_local_gone(account: &str, timeout: Duration) {
    let deadline = tokio::time::Instant::now() + timeout;
    while tokio::time::Instant::now() < deadline {
        let games = local_games();
        if !games
            .iter()
            .any(|game| user_matches(&game.account, account))
        {
            return;
        }
        tokio::time::sleep(Duration::from_millis(200)).await;
    }
}

pub fn is_game_process(command: &str) -> bool {
    command
        .split_whitespace()
        .next()
        .map(|exe| {
            let name = exe.rsplit('/').next().unwrap_or(exe);
            name == "host64" || name == "host64-headless"
        })
        .unwrap_or(false)
}

/// A real helper process is the Python interpreter running `scripts/linux_boxes.py`. Match the
/// executable, not just the text: a shell that happens to mention the script (a status command,
/// a test, or the force request's own caller) must not be killed.
pub fn is_helper_process(command: &str) -> bool {
    let Some(exe) = command.split_whitespace().next() else {
        return false;
    };
    let name = exe.rsplit('/').next().unwrap_or(exe);
    name.starts_with("python") && command.contains("linux_boxes.py")
}

pub fn is_headless_process(command: &str) -> bool {
    command
        .split_whitespace()
        .next()
        .map(|exe| exe.rsplit('/').next().unwrap_or(exe) == "host64-headless")
        .unwrap_or(false)
}

fn parse_pid_line(line: &str) -> Option<(u32, &str)> {
    let line = line.trim_start();
    let split = line.find(char::is_whitespace)?;
    let pid = line[..split].parse().ok()?;
    Some((pid, line[split..].trim_start()))
}

pub fn user_arg(command: &str) -> Option<String> {
    let mut parts = command.split_whitespace();
    while let Some(part) = parts.next() {
        if part == "--user" {
            return parts.next().map(str::to_string);
        }
    }
    None
}

#[cfg(test)]
pub fn has_user_arg(command: &str, account: &str) -> bool {
    user_arg(command)
        .map(|value| user_matches(&value, account))
        .unwrap_or(false)
}

#[cfg(unix)]
pub fn pid_alive(pid: u32) -> bool {
    pid > 0 && unsafe { libc::kill(pid as i32, 0) == 0 }
}

#[cfg(not(unix))]
pub fn pid_alive(_pid: u32) -> bool {
    true
}

#[cfg(unix)]
fn terminate(pid: u32) {
    if pid > 0 {
        unsafe {
            libc::kill(pid as i32, libc::SIGTERM);
        }
    }
}

#[cfg(not(unix))]
fn terminate(_pid: u32) {}

#[cfg(unix)]
fn force_kill(pid: u32) {
    if pid > 0 {
        unsafe {
            libc::kill(pid as i32, libc::SIGKILL);
        }
    }
}

#[cfg(not(unix))]
fn force_kill(_pid: u32) {}

/// Force cleanup: stop every copy of the account, including a healthy one and a stale
/// registry/tunnel. This is what the explicit **Force relaunch** button uses.
pub async fn force_stop_account(account: &str) -> Vec<String> {
    let mut notes = stop_account(account).await;
    let games: Vec<LocalGame> = local_games()
        .into_iter()
        .filter(|game| game.headless && user_matches(&game.account, account))
        .collect();
    notes.extend(terminate_games(&games).await);
    notes
}

/// Stop the remote client by account even when the registry has no row for it.
pub async fn force_stop_remote(ssh: &str, account: &str) -> Vec<String> {
    vec![stop_remote(ssh, account, 0).await]
}

/// Kill a stuck `linux_boxes.py` helper so the script's flock and its parent command can end.
/// This is only used by the explicit force path.
/// Persist the sleep flag in the box registry so a launcher restart still shows the badge and
/// the next Launch wakes the box instead of treating it as freshly started.
pub fn set_sleeping(account: &str, sleeping: bool) {
    let mut entries = load();
    let mut changed = false;
    for entry in &mut entries {
        if !user_matches(entry_user(entry), account) {
            continue;
        }
        let Some(map) = entry.as_object_mut() else {
            continue;
        };
        if sleeping {
            map.insert("sleeping".to_string(), Value::Bool(true));
        } else {
            map.remove("sleeping");
        }
        changed = true;
    }
    if changed {
        let _ = save(&entries);
    }
}

pub fn kill_helper_processes() -> Vec<String> {
    #[cfg(unix)]
    {
        let Ok(output) = std::process::Command::new("ps")
            .args(["-axo", "pid=,command="])
            .output()
        else {
            return Vec::new();
        };
        let me = std::process::id();
        let mut pids = Vec::new();
        for line in String::from_utf8_lossy(&output.stdout).lines() {
            let line = line.trim_start();
            let Some((pid, command)) = parse_pid_line(line) else {
                continue;
            };
            if pid == me || !is_helper_process(command) {
                continue;
            }
            pids.push(pid);
        }
        if pids.is_empty() {
            return Vec::new();
        }
        for pid in &pids {
            terminate(*pid);
        }
        std::thread::sleep(Duration::from_millis(300));
        for pid in &pids {
            if pid_alive(*pid) {
                force_kill(*pid);
            }
        }
        vec![format!("stopped {} stuck helper process(es)", pids.len())]
    }
    #[cfg(not(unix))]
    {
        Vec::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn account_is_read_from_ps_command_line() {
        let line = "/Users/me/fanxi/build/host64-headless --game /games/FFXI --user onedough-3 --fps-divisor 2";
        assert!(is_game_process(line));
        assert!(has_user_arg(line, "onedough-3"));
        assert!(has_user_arg(line, "ONEDOUGH-3"));
        assert!(!has_user_arg(line, "onedough-4"));
    }

    #[test]
    fn other_programs_naming_the_account_are_not_game_clients() {
        let line = "/usr/bin/python3 scripts/linux_boxes.py up --user onedough-3";
        assert!(!is_game_process(line));
    }

    #[test]
    fn remote_kill_mentions_the_recorded_pid() {
        let command = remote_kill_command("onedough-3", 1234);
        assert!(command.contains("--user onedough-3"));
        assert!(command.contains("kill 1234"));
        assert!(command.contains("kill -9 1234"));
    }

    #[test]
    fn ps_elapsed_time_parses_days_hours_and_minutes() {
        assert_eq!(parse_etime_secs("05:12"), 312);
        assert_eq!(parse_etime_secs("01:02:03"), 3_723);
        assert_eq!(parse_etime_secs("2-03:04:05"), 183_845);
    }

    #[test]
    fn lsof_port_is_read_from_name_lines() {
        assert_eq!(parse_lsof_port("p123\nn*:54300\n"), Some(54300));
        assert_eq!(parse_lsof_port("p123\nn127.0.0.1:54404\n"), Some(54404));
        assert_eq!(parse_lsof_port("p123\n"), None);
    }

    #[test]
    fn only_old_untracked_nonresponsive_games_are_reapable() {
        let game = LocalGame {
            pid: 4242,
            account: "onedough-2".to_string(),
            port: Some(54400),
            age_secs: 300,
            headless: true,
        };
        let grace = Duration::from_secs(120);
        assert!(
            local_keep_note(&game, grace, &[4242], true)
                .unwrap()
                .contains("tracked")
        );
        assert!(
            local_keep_note(&game, grace, &[], true)
                .unwrap()
                .contains("in game")
        );
        let young = LocalGame {
            age_secs: 10,
            ..game.clone()
        };
        assert!(
            local_keep_note(&young, grace, &[], false)
                .unwrap()
                .contains("starting")
        );
        assert!(local_keep_note(&game, grace, &[], false).is_none());
        let visible = LocalGame {
            headless: false,
            ..game.clone()
        };
        assert!(
            local_keep_note(&visible, grace, &[], false)
                .unwrap()
                .contains("visible")
        );
    }

    #[test]
    fn only_the_python_helper_is_force_killable() {
        assert!(is_helper_process(
            "/Users/me/fanxi/.venv/bin/python /Users/me/fanxi/scripts/linux_boxes.py restart --only 5"
        ));
        assert!(!is_helper_process(
            "/bin/bash -c python3 scripts/linux_boxes.py status"
        ));
        assert!(!is_helper_process("grep linux_boxes.py"));
    }

    #[test]
    fn user_arg_stops_at_the_next_flag() {
        assert_eq!(
            user_arg("/games/host64 --game /g --user onedough-2 --fps-divisor 2").as_deref(),
            Some("onedough-2")
        );
        assert_eq!(user_arg("/games/host64 --game /g"), None);
    }
}
