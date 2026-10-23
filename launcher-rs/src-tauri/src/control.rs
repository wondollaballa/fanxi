//! The launcher's side of the in-game control port.
//!
//! `host64` loads `host/addons/lua/control.lua` when `FFXI_CONTROL` is set. The addon speaks one
//! JSON object per line over loopback, so this module only needs a TCP client and the process table.

use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use serde::Serialize;
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

pub struct Instance {
    pub account: String,
    pub character: Value,
    pub port: u16,
    pub pid: u32,
    pub log_path: PathBuf,
    pub started_at: u64,
    pub child: Child,
    pub last_state: Option<Value>,
    pub last_metrics: Option<Value>,
    pub last_error: String,
    pub last_seen: u64,
    pub exited: bool,
    pub exit_code: Option<i32>,
}

impl Instance {
    fn name(&self) -> String {
        self.character
            .get("name")
            .and_then(Value::as_str)
            .unwrap_or("?")
            .to_string()
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
}

#[derive(Default)]
pub struct InstanceManager {
    instances: Vec<Instance>,
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
            match self.instances[index].child.try_wait() {
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
            index += 1;
        }
    }

    pub fn running_for(&self, account: &str) -> Option<&Instance> {
        self.instances.iter().find(|instance| {
            !instance.exited && instance.account.eq_ignore_ascii_case(account.trim())
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
            })
            .collect()
    }

    pub async fn poll(&mut self) -> Vec<InstanceView> {
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
            game::spawn_host64(config, game_dir, client, login_token, port, account).await?;
        let pid = child.id().unwrap_or(0);
        let instance = Instance {
            account: account.to_string(),
            character: character.clone(),
            port,
            pid,
            log_path,
            started_at: game::now_epoch(),
            child,
            last_state: None,
            last_metrics: None,
            last_error: String::new(),
            last_seen: 0,
            exited: false,
            exit_code: None,
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

        let _ = ControlClient::new(port).command("/shutdown").await;
        for _ in 0..40 {
            match self.instances[index].child.try_wait() {
                Ok(Some(_status)) => {
                    self.instances.remove(index);
                    return Ok(());
                }
                Ok(None) => tokio::time::sleep(Duration::from_millis(150)).await,
                Err(_) => break,
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
        let _ =
            tokio::time::timeout(Duration::from_secs(3), self.instances[index].child.kill()).await;
        if let Ok(Some(status)) = self.instances[index].child.try_wait() {
            self.instances[index].exit_code = status.code();
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
    fn slot_aliases_are_normalised() {
        assert_eq!(crate::gear::normalize_slot("left_ear"), "ear1");
        assert_eq!(crate::gear::normalize_slot("Right Ring"), "ring2");
    }
}
