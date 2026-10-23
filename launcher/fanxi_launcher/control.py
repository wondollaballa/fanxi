"""The launcher's side of the in-game control port.

host64 loads ``host/addons/lua/control.lua`` when it starts with ``FFXI_CONTROL`` set.  The
addon listens on loopback and speaks one JSON object per line:

    -> {"id": 1, "cmd": "state", "args": {}}
    <- {"id": 1, "ok": true, "result": {...}}

This module owns the socket and the small amount of process bookkeeping around it: one
``Instance`` per running client, a free control port per client, and a log file per client.
It has no Tkinter imports so it can be tested on its own.
"""
from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .game import GameManager


class ControlError(Exception):
    pass


class ControlClient:
    """A connection to one game's control addon."""

    def __init__(self, port: int, timeout: float = 10.0):
        self.port = int(port)
        self.timeout = float(timeout)
        self.sock: socket.socket | None = None
        self.buf = b""
        self.next_id = 1
        self.lock = threading.Lock()

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.buf = b""

    def connect(self) -> None:
        self.sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buf = b""

    def call(self, cmd: str, args: dict | None = None, timeout: float | None = None):
        limit = self.timeout if timeout is None else float(timeout)
        with self.lock:
            for attempt in (0, 1):
                try:
                    if self.sock is None:
                        self.connect()
                    request_id = self.next_id
                    self.next_id += 1
                    line = json.dumps({"id": request_id, "cmd": cmd, "args": args or {}},
                                      ensure_ascii=False) + "\n"
                    assert self.sock is not None
                    self.sock.sendall(line.encode("utf-8"))
                    deadline = time.monotonic() + limit
                    while True:
                        while b"\n" in self.buf:
                            raw, self.buf = self.buf.split(b"\n", 1)
                            if not raw.strip():
                                continue
                            message = json.loads(raw.decode("utf-8", "replace"))
                            if message.get("id") != request_id:
                                continue  # a late answer to a request that timed out
                            if not message.get("ok"):
                                raise ControlError(str(message.get("error") or "the game refused"))
                            return message.get("result")
                        left = deadline - time.monotonic()
                        if left <= 0:
                            raise ControlError("%s: no answer in %.0f s" % (cmd, limit))
                        assert self.sock is not None
                        self.sock.settimeout(left)
                        chunk = self.sock.recv(65536)
                        if not chunk:
                            raise ControlError("the game closed its control port")
                        self.buf += chunk
                except (ConnectionError, OSError, ValueError) as exc:
                    self.close()
                    if attempt:
                        raise ControlError("cannot reach the game on 127.0.0.1:%d (%s)"
                                           % (self.port, exc))
            raise ControlError("control request failed")

    # --- convenience ---------------------------------------------------------------------------
    def state(self):
        return self.call("state")

    def metrics(self):
        return self.call("metrics")

    def entities(self, radius: float = 50, limit: int = 50):
        return self.call("entities", {"radius": radius, "limit": limit})

    def command(self, line: str):
        return self.call("command", {"line": line})

    def chat(self, line: str):
        return self.call("chat_send", {"line": line})

    def gear(self):
        return self.call("gear")

    def equip(self, slot: str, item: str):
        return self.call("equip", {"slot": slot, "item": item})

    def gearswap(self, path: str):
        return self.call("gearswap", {"path": path}, timeout=20)


@dataclass
class Instance:
    account: str
    character: dict
    port: int
    process: subprocess.Popen
    log_path: Path
    started_at: float = field(default_factory=time.time)
    last_state: dict | None = None
    last_metrics: dict | None = None
    last_error: str = ""
    last_seen: float = 0.0
    client: ControlClient | None = None

    @property
    def pid(self) -> int:
        return int(self.process.pid)

    @property
    def name(self) -> str:
        return str(self.character.get("name") or "?")

    @property
    def alive(self) -> bool:
        return self.process.poll() is None

    @property
    def uptime(self) -> int:
        return max(0, int(time.time() - self.started_at))

    def control(self) -> ControlClient:
        if self.client is None:
            self.client = ControlClient(self.port)
        return self.client

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(name or "game")).strip("-") or "game"


class InstanceManager:
    """Owns every game process this launcher started."""

    def __init__(self, game: GameManager, base_port: int = 54300):
        self.game = game
        self.base_port = int(base_port)
        self.instances: list[Instance] = []

    # --- process table -------------------------------------------------------------------------
    def active(self) -> list[Instance]:
        self.instances = [i for i in self.instances if i.alive]
        return list(self.instances)

    def running_for(self, username: str) -> Instance | None:
        wanted = str(username or "").lower()
        for instance in self.active():
            if instance.account.lower() == wanted:
                return instance
        return None

    def by_port(self, port: int) -> Instance | None:
        for instance in self.active():
            if instance.port == int(port):
                return instance
        return None

    def allocate_port(self) -> int:
        used = {i.port for i in self.active()}
        for port in range(self.base_port, self.base_port + 200):
            if port in used:
                continue
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            finally:
                sock.close()
            return port
        raise ControlError("no free control port between %d and %d"
                           % (self.base_port, self.base_port + 199))

    # --- launch / stop -------------------------------------------------------------------------
    def launch(self, account: dict, character: dict, client: dict, login_token: str,
               game_dir: str | Path) -> Instance:
        username = str(account.get("username") or "")
        if not username:
            raise ControlError("the account has no username")
        running = self.running_for(username)
        if running is not None:
            raise ControlError("%s is already online as %s on port %d; one client per account"
                               % (username, running.name, running.port))
        port = self.allocate_port()
        log_name = "game-%s.log" % _safe_name(username)
        process = self.game.launch(
            game_dir, client, login_token,
            extra_env={"FFXI_CONTROL": str(port)},
            log_name=log_name,
        )
        instance = Instance(
            account=username,
            character=character,
            port=port,
            process=process,
            log_path=self.game.log_path(log_name),
        )
        self.instances.append(instance)
        return instance

    def stop(self, instance: Instance, *, graceful: bool = True, timeout: float = 6.0) -> None:
        if not instance.alive:
            instance.close()
            return
        if graceful:
            try:
                instance.control().command("/shutdown")
            except ControlError:
                try:
                    instance.control().chat("/shutdown")
                except ControlError:
                    pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and instance.alive:
            time.sleep(0.15)
        if instance.alive:
            try:
                if os.name != "nt":
                    os.killpg(os.getpgid(instance.pid), signal.SIGTERM)
                else:
                    instance.process.terminate()
            except (OSError, ProcessLookupError):
                pass
            try:
                instance.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    if os.name != "nt":
                        os.killpg(os.getpgid(instance.pid), signal.SIGKILL)
                    else:
                        instance.process.kill()
                except (OSError, ProcessLookupError):
                    pass
        instance.close()
        self.active()
