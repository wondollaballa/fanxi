//! The launcher's side of the in-game control port.
//!
//! `host64` loads `host/addons/lua/control.lua` when `FFXI_CONTROL` is set. The addon speaks one
//! JSON object per line over loopback, so this module only needs a TCP client and the process table.

use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::TcpStream;
use tokio::process::Child;

use crate::config::LauncherConfig;
use crate::error::{AppError, AppResult};
use crate::game;

static NEXT_ID: AtomicU64 = AtomicU64::new(1);
const CONTROL_BASE_PORT: u16 = 54300;
const CONTROL_PORT_RANGE: u16 = 200;

#[derive(Clone, Debug)]
pub struct ControlClient {
    port: u16,
}

impl ControlClient {
    pub fn new(port: u16) -> Self {
        Self { port }
    }

    pub async fn call(&self, cmd: &str, args: Value, timeout: Duration) -> AppResult<Value> {
        let request_id = NEXT_ID.fetch_add(1, Ordering::Relaxed);
        let line = serde_json::to_string(&json!({
            "id": request_id,
            "cmd": cmd,
            "args": args,
        }))?;

        let mut stream = tokio::time::timeout(
            Duration::from_secs(5),
            TcpStream::connect(("127.0.0.1", self.port)),
        )
        .await
        .map_err(|_| {
            AppError::Control(format!(
                "timed out connecting to control port {}",
                self.port
            ))
        })?
        .map_err(|error| {
            AppError::Control(format!(
                "cannot reach the game on 127.0.0.1:{} ({error})",
                self.port
            ))
        })?;
        let _ = stream.set_nodelay(true);
        stream
            .write_all(format!("{line}\n").as_bytes())
            .await
            .map_err(|error| AppError::Control(format!("control port write failed: {error}")))?;

        let mut lines = BufReader::new(stream).lines();
        let result = tokio::time::timeout(timeout, async {
            loop {
                let next = lines.next_line().await.map_err(|error| {
                    AppError::Control(format!("control port read failed: {error}"))
                })?;
                let Some(next) = next else {
                    return Err(AppError::Control(
                        "the game closed its control port".to_string(),
                    ));
                };
                if next.trim().is_empty() {
                    continue;
                }
                let value: Value = serde_json::from_str(&next)
                    .map_err(|error| AppError::Control(format!("bad control reply: {error}")))?;
                if value.get("id").and_then(Value::as_u64) != Some(request_id) {
                    continue; // a late answer to a request that timed out
                }
                if value.get("ok").and_then(Value::as_bool) == Some(true) {
                    return Ok(value.get("result").cloned().unwrap_or(Value::Null));
                }
                let message = value
                    .get("error")
                    .and_then(Value::as_str)
                    .unwrap_or("the game refused the request");
                return Err(AppError::Control(message.to_string()));
            }
        })
        .await
        .map_err(|_| AppError::Control(format!("{cmd}: no answer in {} s", timeout.as_secs())))?;
        result
    }

    pub async fn state(&self) -> AppResult<Value> {
        self.call("state", json!({}), Duration::from_secs(10)).await
    }

    pub async fn metrics(&self) -> AppResult<Value> {
        self.call("metrics", json!({}), Duration::from_secs(10))
            .await
    }

    pub async fn gear(&self) -> AppResult<Value> {
        self.call("gear", json!({}), Duration::from_secs(10)).await
    }

    pub async fn follow(
        &self,
        enabled: bool,
        leader: Option<&str>,
        distance: f64,
    ) -> AppResult<Value> {
        self.call(
            "follow",
            json!({"enabled": enabled, "leader": leader, "distance": distance}),
            Duration::from_secs(10),
        )
        .await
    }

    pub async fn follow_status(&self) -> AppResult<Value> {
        self.call("follow_status", json!({}), Duration::from_secs(10))
            .await
    }

    pub async fn follow_events(&self) -> AppResult<Value> {
        self.call("follow_events", json!({}), Duration::from_secs(10))
            .await
    }

    pub async fn command(&self, line: &str) -> AppResult<Value> {
        self.call("command", json!({"line": line}), Duration::from_secs(10))
            .await
    }

    /// Change the in-game ability/spell HUD. `args` is the addon's `hud` command payload
    /// (`show_abilities`, `show_spells`, `edit`, `layout`, `columns`, `size`, `labels`,
    /// `opacity`, `reset_positions`), so the frontend can add fields without another command.
    pub async fn hud(&self, args: Value) -> AppResult<Value> {
        self.call("hud", args, Duration::from_secs(10)).await
    }

    pub async fn chat(&self, line: &str) -> AppResult<Value> {
        self.call("chat_send", json!({"line": line}), Duration::from_secs(10))
            .await
    }

    pub async fn equip(&self, slot: &str, item: &str) -> AppResult<Value> {
        self.call(
            "equip",
            json!({"slot": slot, "item": item}),
            Duration::from_secs(10),
        )
        .await
    }

    pub async fn equip_set(&self, items: Vec<Value>) -> AppResult<Value> {
        self.call(
            "equip_set",
            json!({"items": items}),
            Duration::from_secs(30),
        )
        .await
    }

    pub async fn phase(
        &self,
        path: Option<&str>,
        enabled: bool,
        engaged: Option<&str>,
        idle_town: Option<&str>,
        idle_field: Option<&str>,
        movement: Option<&str>,
        options: Option<&Value>,
    ) -> AppResult<Value> {
        let mut args = json!({"enabled": enabled});
        if let Some(path) = path {
            args["path"] = json!(path);
        }
        if let Some(name) = engaged {
            args["engaged"] = json!(name);
        }
        if let Some(name) = idle_town {
            args["idle_town"] = json!(name);
        }
        if let Some(name) = idle_field {
            args["idle_field"] = json!(name);
        }
        if let Some(name) = movement {
            args["move"] = json!(name);
        }
        // The spell/WS overrides and the forced-state sets ride in one object so the command
        // keeps its well-known fields and older callers still work.
        if let Some(Value::Object(map)) = options {
            for (key, value) in map {
                if !value.is_null() {
                    args[key] = value.clone();
                }
            }
        }
        self.call("phase", args, Duration::from_secs(30)).await
    }

    /// Hold the set that is worn now, or let the state machine move gear again.
    pub async fn phase_lock(&self, locked: bool) -> AppResult<Value> {
        self.call(
            "phase_lock",
            json!({"locked": locked}),
            Duration::from_secs(10),
        )
        .await
    }

    pub async fn phase_kiting(&self, on: bool) -> AppResult<Value> {
        self.call("phase_kiting", json!({"on": on}), Duration::from_secs(10))
            .await
    }

    pub async fn phase_resting(&self, on: bool) -> AppResult<Value> {
        self.call("phase_resting", json!({"on": on}), Duration::from_secs(10))
            .await
    }

    pub async fn phase_focus(&self, mode: &str) -> AppResult<Value> {
        self.call(
            "phase_focus",
            json!({"mode": mode}),
            Duration::from_secs(10),
        )
        .await
    }

    pub async fn phase_lock_slots(&self, mask: u32) -> AppResult<Value> {
        self.call(
            "phase_lock_slots",
            json!({"mask": mask}),
            Duration::from_secs(10),
        )
        .await
    }

    pub async fn job_spells(&self) -> AppResult<Value> {
        self.call("job_spells", json!({}), Duration::from_secs(15))
            .await
    }

    /// The main/sub job abilities the client's menu advertises, for the Gear page's JA cards.
    pub async fn job_abilities(&self) -> AppResult<Value> {
        self.call("job_abilities", json!({}), Duration::from_secs(15))
            .await
    }

    /// Weapons and ammo in the character's bags that the current main job can equip.
    pub async fn weapons(&self) -> AppResult<Value> {
        self.call("weapons", json!({}), Duration::from_secs(15))
            .await
    }

    pub async fn phase_status(&self) -> AppResult<Value> {
        self.call("phase_status", json!({}), Duration::from_secs(10))
            .await
    }

    pub async fn gearswap(&self, path: &str) -> AppResult<Value> {
        self.call("gearswap", json!({"path": path}), Duration::from_secs(20))
            .await
    }

    pub async fn icons(&self, ids: &[u32]) -> AppResult<Value> {
        self.call("icons", json!({"ids": ids}), Duration::from_secs(20))
            .await
    }

    pub async fn item_ids(&self, names: &[String]) -> AppResult<Value> {
        self.call("item_ids", json!({"names": names}), Duration::from_secs(10))
            .await
    }
}

#[derive(Clone, Debug, Deserialize)]
pub struct RemoteInfo {
    pub ssh: String,
    pub remote_pid: u32,
    pub tunnel_pid: u32,
}

pub struct Instance {
    pub account: String,
    pub character: Value,
    pub port: u16,
    pub pid: u32,
    pub log_path: PathBuf,
    pub started_at: u64,
    pub child: Option<Child>,
    pub remote: Option<RemoteInfo>,
    pub headless: bool,
    pub sleeping: bool,
    pub last_state: Option<Value>,
    pub last_metrics: Option<Value>,
    pub last_error: String,
    pub last_seen: u64,
    pub exited: bool,
    pub exit_code: Option<i32>,
    /// The server's live zone roster, when the launcher could read it. `None` is unknown
    /// (no token, endpoint failure, gateway off); `Some(false)` means the client's own state
    /// says it is in world but the server has no session for it.
    pub server_online: Option<bool>,
}

impl Instance {
    fn name(&self) -> String {
        self.character
            .get("name")
            .and_then(Value::as_str)
            .unwrap_or("?")
            .to_string()
    }

    /// The name and database id the server's online roster uses. The addon's player id is a
    /// wire id on some client builds, so only the character id from the API/registry is safe.
    fn online_identity(&self) -> (String, Option<i64>) {
        let name = self
            .last_state
            .as_ref()
            .and_then(|state| state.pointer("/player/name"))
            .and_then(Value::as_str)
            .filter(|name| !name.trim().is_empty())
            .map(str::to_string)
            .unwrap_or_else(|| self.name());
        let id = self.character.get("id").and_then(Value::as_i64);
        (name, id)
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InstanceView {
    pub account: String,
    pub character: Value,
    pub name: String,
    pub port: u16,
    pub pid: u32,
    pub started_at: u64,
    pub uptime_seconds: u64,
    pub alive: bool,
    pub exit_code: Option<i32>,
    pub state: Option<Value>,
    pub metrics: Option<Value>,
    pub error: String,
    pub log_path: String,
    pub remote: bool,
    pub host: Option<String>,
    pub headless: bool,
    pub sleeping: bool,
    pub server_online: Option<bool>,
}

/// The server's live zone roster, normalised for matching against a client's own state.
#[derive(Clone, Debug, Default)]
pub struct OnlineRoster {
    names: std::collections::HashSet<String>,
    ids: std::collections::HashSet<i64>,
}

impl OnlineRoster {
    /// `None` when the response is not authoritative: no game gateway, or an older server
    /// without the roster route. The launcher must not call every box orphaned in that case.
    pub fn from_value(value: &Value) -> Option<Self> {
        if value.get("gateway").and_then(Value::as_bool) != Some(true) {
            return None;
        }
        let mut roster = Self::default();
        if let Some(characters) = value.get("characters").and_then(Value::as_array) {
            for character in characters {
                if let Some(name) = character.get("name").and_then(Value::as_str) {
                    let name = name.trim();
                    if !name.is_empty() {
                        roster.names.insert(name.to_lowercase());
                    }
                }
                if let Some(id) = character.get("id").and_then(Value::as_i64) {
                    roster.ids.insert(id);
                }
            }
        }
        Some(roster)
    }

    pub fn contains(&self, name: &str, id: Option<i64>) -> bool {
        if id.is_some_and(|id| self.ids.contains(&id)) {
            return true;
        }
        let name = name.trim();
        !name.is_empty() && self.names.contains(&name.to_lowercase())
    }
}

#[derive(Default)]
pub struct InstanceManager {
    instances: Vec<Instance>,
    /// `ps`/`lsof` are not free; a local client that appears between polls is adopted within
    /// this window instead of on every three-second tick.
    local_scan_at: Option<std::time::Instant>,
}

impl InstanceManager {
    pub fn new() -> Self {
        Self::default()
    }

    pub async fn prune(&mut self) {
        let mut index = 0;
        while index < self.instances.len() {
            if self.instances[index].exited {
                self.instances.remove(index);
                continue;
            }
            if let Some(child) = self.instances[index].child.as_mut() {
                match child.try_wait() {
                    Ok(Some(_status)) => {
                        // The game closed on its own. Drop the row rather than leaving a dead control
                        // port in the UI; the log file remains on disk.
                        self.instances.remove(index);
                        continue;
                    }
                    Ok(None) => {}
                    Err(_error) => {
                        self.instances.remove(index);
                        continue;
                    }
                }
            } else {
                // An attached box has no child here: its control port is the liveness signal.
                // One busy/failed tunnel probe is not enough to drop a whole team; keep the row
                // until the box has been unreachable for a while.
                let port = self.instances[index].port;
                let addr = std::net::SocketAddr::from(([127, 0, 0, 1], port));
                if std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(500)).is_err() {
                    let now = game::now_epoch();
                    let instance = &self.instances[index];
                    let reference = if instance.last_seen > 0 {
                        instance.last_seen
                    } else {
                        instance.started_at
                    };
                    if now.saturating_sub(reference) > 20 {
                        self.instances.remove(index);
                        continue;
                    }
                }
            }
            index += 1;
        }
    }

    pub fn running_for(&self, account: &str) -> Option<&Instance> {
        self.instances.iter().find(|instance| {
            !instance.exited && instance.account.eq_ignore_ascii_case(account.trim())
        })
    }

    /// The tracked process the launcher itself spawned for this account. Attached remote boxes
    /// have no local process and are deliberately excluded.
    pub fn local_running_for(&self, account: &str) -> Option<&Instance> {
        self.instances.iter().find(|instance| {
            !instance.exited
                && instance.remote.is_none()
                && instance.account.eq_ignore_ascii_case(account.trim())
        })
    }

    pub fn by_port(&self, port: u16) -> Option<&Instance> {
        self.instances.iter().find(|instance| instance.port == port)
    }

    pub fn views(&self) -> Vec<InstanceView> {
        let now = game::now_epoch();
        self.instances
            .iter()
            .map(|instance| InstanceView {
                account: instance.account.clone(),
                character: instance.character.clone(),
                name: instance.name(),
                port: instance.port,
                pid: instance.pid,
                started_at: instance.started_at,
                uptime_seconds: now.saturating_sub(instance.started_at),
                alive: !instance.exited,
                exit_code: instance.exit_code,
                state: instance.last_state.clone(),
                metrics: instance.last_metrics.clone(),
                error: instance.last_error.clone(),
                log_path: instance.log_path.to_string_lossy().into_owned(),
                remote: instance.remote.is_some(),
                host: instance.remote.as_ref().map(|remote| remote.ssh.clone()),
                headless: instance.headless,
                sleeping: instance.sleeping,
                server_online: instance.server_online,
            })
            .collect()
    }

    pub async fn poll(&mut self) -> Vec<InstanceView> {
        self.poll_with_online(None).await
    }

    /// Poll every client and mark it against the server's live zone roster.
    ///
    /// The client's own `login_status` cannot see a server restart: the process keeps its last
    /// zone and still answers `2`. The roster is what tells the panel the difference.
    pub async fn poll_with_online(&mut self, roster: Option<&OnlineRoster>) -> Vec<InstanceView> {
        self.attach_linux();
        self.attach_local().await;
        self.prune().await;
        let ports: Vec<u16> = self
            .instances
            .iter()
            .filter(|instance| !instance.exited)
            .map(|instance| instance.port)
            .collect();
        for port in ports {
            let result = ControlClient::new(port).metrics().await;
            if let Some(instance) = self.instances.iter_mut().find(|item| item.port == port) {
                match result {
                    Ok(metrics) => {
                        instance.last_state = metrics.get("state").cloned();
                        instance.last_metrics = Some(metrics);
                        instance.last_error.clear();
                        instance.last_seen = game::now_epoch();
                    }
                    Err(error) => {
                        instance.last_error = error.to_string();
                    }
                }
            }
        }
        for instance in &mut self.instances {
            instance.server_online = roster.map(|roster| {
                let (name, id) = instance.online_identity();
                roster.contains(&name, id)
            });
        }
        self.views()
    }

    pub async fn launch(
        &mut self,
        config: &LauncherConfig,
        account: &str,
        character: Value,
        client: &Value,
        login_token: &str,
        game_dir: &std::path::Path,
        headless: bool,
    ) -> AppResult<InstanceView> {
        self.prune().await;
        if let Some(running) = self.running_for(account) {
            return Err(AppError::Control(format!(
                "{account} is already online as {} (control port {})",
                running.name(),
                running.port
            )));
        }
        let port = self.allocate_port()?;
        let log_path =
            crate::config::log_dir()?.join(format!("game-{}.log", game::safe_name(account)));
        let child =
            game::spawn_host64(config, game_dir, client, login_token, port, account, headless).await?;
        let pid = child.id().unwrap_or(0);
        let instance = Instance {
            account: account.to_string(),
            character: character.clone(),
            port,
            pid,
            log_path,
            started_at: game::now_epoch(),
            child: Some(child),
            remote: None,
            headless,
            sleeping: false,
            last_state: None,
            last_metrics: None,
            last_error: String::new(),
            last_seen: 0,
            exited: false,
            exit_code: None,
            server_online: None,
        };
        let view = InstanceView {
            account: instance.account.clone(),
            character: instance.character.clone(),
            name: instance.name(),
            port: instance.port,
            pid: instance.pid,
            started_at: instance.started_at,
            uptime_seconds: 0,
            alive: true,
            exit_code: None,
            state: None,
            metrics: None,
            error: String::new(),
            log_path: instance.log_path.to_string_lossy().into_owned(),
            remote: false,
            host: None,
            headless,
            sleeping: false,
            server_online: None,
        };
        self.instances.push(instance);
        Ok(view)
    }

    pub async fn stop(&mut self, port: u16) -> AppResult<()> {
        let Some(index) = self
            .instances
            .iter()
            .position(|instance| instance.port == port)
        else {
            return Err(AppError::Control(format!(
                "no client on control port {port}"
            )));
        };
        if self.instances[index].exited {
            self.instances.remove(index);
            return Ok(());
        }

        if let Some(remote) = self.instances[index].remote.clone() {
            let _ = ControlClient::new(port).command("/shutdown").await;
            if !remote.ssh.is_empty() {
                let _ = tokio::process::Command::new("ssh")
                    .arg("-n")
                    .arg(&remote.ssh)
                    .arg(format!("kill {}", remote.remote_pid))
                    .status()
                    .await;
            } else if remote.remote_pid > 0 {
                // A locally attached box: the panel did not spawn this process, so there is no
                // Child handle to kill; its recorded pid is the handle.
                #[cfg(unix)]
                unsafe {
                    libc::kill(remote.remote_pid as i32, libc::SIGTERM);
                }
            }
            if remote.tunnel_pid > 0 {
                let _ = std::process::Command::new("kill")
                    .arg(remote.tunnel_pid.to_string())
                    .status();
            }
            self.instances.remove(index);
            return Ok(());
        }

        let _ = ControlClient::new(port).command("/shutdown").await;
        for _ in 0..40 {
            let status = self.instances[index]
                .child
                .as_mut()
                .map(|child| child.try_wait());
            match status {
                Some(Ok(Some(_status))) => {
                    self.instances.remove(index);
                    return Ok(());
                }
                Some(Ok(None)) => tokio::time::sleep(Duration::from_millis(150)).await,
                _ => break,
            }
        }

        #[cfg(unix)]
        {
            let pid = self.instances[index].pid;
            if pid > 0 {
                unsafe {
                    libc::killpg(pid as i32, libc::SIGTERM);
                }
            }
        }
        if let Some(child) = self.instances[index].child.as_mut() {
            let _ = tokio::time::timeout(Duration::from_secs(3), child.kill()).await;
            if let Ok(Some(status)) = child.try_wait() {
                self.instances[index].exit_code = status.code();
            }
        }
        self.instances.remove(index);
        Ok(())
    }

    pub async fn stop_all(&mut self) -> AppResult<usize> {
        let ports: Vec<u16> = self
            .instances
            .iter()
            .filter(|instance| !instance.exited)
            .map(|instance| instance.port)
            .collect();
        for port in &ports {
            let _ = self.stop(*port).await;
        }
        Ok(ports.len())
    }

    /// Adopt the boxes the Linux helper started (`scripts/linux_boxes.py up`): it leaves their
    /// control ports in a local ssh tunnel, so the same ControlClient and the same panel work.
    pub fn attach_linux(&mut self) -> usize {
        let path = crate::config::home_dir().join(".fanxi-linux-boxes.json");
        let Ok(text) = std::fs::read_to_string(&path) else {
            return 0;
        };
        let Ok(boxes) = serde_json::from_str::<Vec<Value>>(&text) else {
            return 0;
        };
        let mut added = 0;
        for item in boxes {
            let Some(port) = item.get("port").and_then(Value::as_u64).map(|p| p as u16) else {
                continue;
            };
            let addr = std::net::SocketAddr::from(([127, 0, 0, 1], port));
            if std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_err() {
                continue; // the tunnel is not up (or the box was stopped)
            }
            let account = item
                .get("user")
                .and_then(Value::as_str)
                .unwrap_or("?")
                .to_string();
            let name = item
                .get("character")
                .and_then(Value::as_str)
                .unwrap_or("?");
            let ssh = item
                .get("ssh")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            if ssh.trim().is_empty() {
                // The helper also records the local main client here. It is not a tunneled box;
                // the launcher owns that process as a child and must not adopt a stale pid.
                continue;
            }
            let remote_pid = item
                .get("remote_pid")
                .and_then(Value::as_u64)
                .unwrap_or(0) as u32;
            let tunnel_pid = item
                .get("tunnel_pid")
                .and_then(Value::as_u64)
                .unwrap_or(0) as u32;
            let log = item
                .get("log")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let started = item
                .get("started")
                .and_then(Value::as_u64)
                .unwrap_or_else(game::now_epoch);
            let headless = item.get("headless").and_then(Value::as_bool).unwrap_or(true);
            let sleeping = item.get("sleeping").and_then(Value::as_bool).unwrap_or(false);
            let character = json!({
                "name": name,
                "id": item.get("character_id").cloned().unwrap_or(Value::Null),
            });
            // The helper restarts a box on the same tunnel port. Refresh the metadata of the
            // attached instance so Stop targets the new remote pid instead of the old one.
            if let Some(index) = self.instances.iter().position(|instance| instance.port == port) {
                if self.instances[index].remote.is_some() {
                    let instance = &mut self.instances[index];
                    instance.account = account;
                    instance.character = character;
                    instance.pid = remote_pid;
                    instance.log_path = PathBuf::from(log);
                    instance.started_at = started;
                    instance.remote = Some(RemoteInfo {
                        ssh,
                        remote_pid,
                        tunnel_pid,
                    });
                    instance.headless = headless;
                    instance.sleeping = sleeping;
                    instance.exited = false;
                    if instance.last_seen == 0 {
                        instance.last_seen = game::now_epoch();
                    }
                }
                continue;
            }
            self.instances.push(Instance {
                account,
                character,
                port,
                pid: remote_pid,
                log_path: PathBuf::from(log),
                started_at: started,
                child: None,
                remote: Some(RemoteInfo {
                    ssh,
                    remote_pid,
                    tunnel_pid,
                }),
                headless,
                sleeping,
                last_state: None,
                last_metrics: None,
                last_error: String::new(),
                last_seen: game::now_epoch(),
                exited: false,
                exit_code: None,
                server_online: None,
            });
            added += 1;
        }
        added
    }

    /// Adopt local `host64` clients the launcher did not spawn in this run.
    ///
    /// The launcher deliberately leaves the game running when its window closes, so after a
    /// restart the client is still in world but the new process has no `Child` handle or row
    /// for it. Its control port is enough to list, command and stop it again.
    pub async fn attach_local(&mut self) -> usize {
        if let Some(at) = self.local_scan_at {
            if at.elapsed() < Duration::from_secs(15) {
                return 0;
            }
        }
        self.local_scan_at = Some(std::time::Instant::now());
        let mut added = 0;
        for game in crate::boxes::local_games() {
            let Some(port) = game.port else {
                continue; // started without FFXI_CONTROL: nothing here can drive it
            };
            if self.instances.iter().any(|instance| {
                instance.port == port || instance.account.eq_ignore_ascii_case(game.account.trim())
            }) {
                continue;
            }
            let Ok(Ok(state)) = tokio::time::timeout(
                Duration::from_millis(1_500),
                ControlClient::new(port).state(),
            )
            .await
            else {
                continue;
            };
            let Some(name) = state
                .pointer("/player/name")
                .and_then(Value::as_str)
                .filter(|name| !name.trim().is_empty())
                .map(str::to_string)
            else {
                continue;
            };
            let character = json!({
                "name": name,
                "id": state.pointer("/player/id").cloned().unwrap_or(Value::Null),
            });
            let log_path = crate::config::log_dir()
                .map(|dir| dir.join(format!("game-{}.log", game::safe_name(&game.account))))
                .unwrap_or_default();
            let sleeping = state
                .get("sleeping")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            self.instances.push(Instance {
                account: game.account,
                character,
                port,
                pid: game.pid,
                log_path,
                started_at: game::now_epoch().saturating_sub(game.age_secs),
                child: None,
                remote: None,
                headless: game.headless,
                sleeping,
                last_state: Some(state),
                last_metrics: None,
                last_error: String::new(),
                last_seen: game::now_epoch(),
                exited: false,
                exit_code: None,
                server_online: None,
            });
            added += 1;
        }
        added
    }

    pub fn set_sleeping(&mut self, port: u16, sleeping: bool) {
        if let Some(instance) = self.instances.iter_mut().find(|item| item.port == port) {
            instance.sleeping = sleeping;
            if let Some(state) = instance.last_state.as_mut() {
                if let Some(map) = state.as_object_mut() {
                    map.insert("sleeping".to_string(), Value::Bool(sleeping));
                }
            }
        }
    }

    pub fn control_for(&self, port: u16) -> AppResult<ControlClient> {
        if self.by_port(port).is_none() {
            return Err(AppError::Control(format!(
                "no client on control port {port}"
            )));
        }
        Ok(ControlClient::new(port))
    }

    fn allocate_port(&self) -> AppResult<u16> {
        let used: std::collections::HashSet<u16> = self.instances.iter().map(|i| i.port).collect();
        for port in CONTROL_BASE_PORT..CONTROL_BASE_PORT + CONTROL_PORT_RANGE {
            if used.contains(&port) {
                continue;
            }
            if std::net::TcpListener::bind(("127.0.0.1", port)).is_ok() {
                return Ok(port);
            }
        }
        Err(AppError::Control(
            "no free control port between 54300 and 54499".to_string(),
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

    #[tokio::test]
    async fn control_client_round_trips_json_lines() {
        let listener = tokio::net::TcpListener::bind(("127.0.0.1", 0))
            .await
            .expect("bind test listener");
        let port = listener.local_addr().unwrap().port();
        let server = tokio::spawn(async move {
            let (mut socket, _) = listener.accept().await.unwrap();
            let mut lines = BufReader::new(&mut socket).lines();
            let line = lines.next_line().await.unwrap().unwrap();
            let request: Value = serde_json::from_str(&line).unwrap();
            let reply = json!({
                "id": request["id"],
                "ok": true,
                "result": {"kpi": {"dps": 12.5}, "state": {"player": {"name": "Aria"}}}
            });
            socket
                .write_all(format!("{reply}\n").as_bytes())
                .await
                .unwrap();
        });

        let value = ControlClient::new(port).metrics().await.unwrap();
        assert_eq!(value["kpi"]["dps"], 12.5);
        assert_eq!(value["state"]["player"]["name"], "Aria");
        server.await.unwrap();
    }

    #[tokio::test]
    async fn control_client_surfaces_game_errors() {
        let listener = tokio::net::TcpListener::bind(("127.0.0.1", 0))
            .await
            .expect("bind test listener");
        let port = listener.local_addr().unwrap().port();
        tokio::spawn(async move {
            let (mut socket, _) = listener.accept().await.unwrap();
            let mut lines = BufReader::new(&mut socket).lines();
            let line = lines.next_line().await.unwrap().unwrap();
            let request: Value = serde_json::from_str(&line).unwrap();
            let reply = json!({"id": request["id"], "ok": false, "error": "not in the world yet"});
            socket
                .write_all(format!("{reply}\n").as_bytes())
                .await
                .unwrap();
        });

        let error = ControlClient::new(port).metrics().await.unwrap_err();
        assert!(error.to_string().contains("not in the world yet"));
    }

    #[test]
    fn online_roster_matches_names_case_insensitively_and_ids() {
        let value = json!({
            "gateway": true,
            "characters": [
                {"id": 3, "name": "Threedough", "zone": 190},
                {"name": "Twodough", "zone": 190},
            ]
        });
        let roster = OnlineRoster::from_value(&value).expect("authoritative roster");
        assert!(roster.contains("Threedough", None));
        assert!(roster.contains("threedough", Some(3)));
        assert!(roster.contains("", Some(3)));
        assert!(!roster.contains("Fourdough", None));
        assert!(!roster.contains("", None));
    }

    #[test]
    fn online_roster_is_not_authoritative_without_a_gateway() {
        assert!(OnlineRoster::from_value(&json!({"gateway": false, "characters": []})).is_none());
        assert!(OnlineRoster::from_value(&json!({"characters": []})).is_none());
    }

    #[test]
    fn slot_aliases_are_normalised() {
        assert_eq!(crate::gear::normalize_slot("left_ear"), "ear1");
        assert_eq!(crate::gear::normalize_slot("Right Ring"), "ring2");
    }
}
