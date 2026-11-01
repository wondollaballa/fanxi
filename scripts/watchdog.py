#!/usr/bin/env python3
"""Keep the Fanxi team in the world by recovering clients that drop out.

  python3 scripts/watchdog.py            # supervise until stopped
  python3 scripts/watchdog.py --once     # one sweep, then exit
  python3 scripts/watchdog.py --once --dry-run

A retail client that loses the zone server long enough shows

    Error code: FFXI-4001
    No response from the FINAL FANTASY XI server.
    Connection timed out.
    Press OK to shut down.

and then exits.  Nothing in the client retries, and the server cannot fix a network path;
the client has to be started again.  This watchdog polls each client's control port (the
main on 54300 and the sub-account boxes from ``~/.fanxi-linux-boxes.json`` through their
ssh tunnels), recognises the error dialog (``login_status 0`` with the OK menu after the
client had been in the world), presses OK, relaunches that client with a fresh launch
token, drives it back to a zone, then re-invites the party and re-applies the follow
graph.  A client whose control port dies after it was in the world is recovered the same
way with ``--relaunch-exit``.

Every client gets a cooldown after an attempt, so a network that is still down does not
become a relaunch loop.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = Path.home() / "Library" / "Application Support" / "Fanxi" / "launcher.json"
BOXES = Path.home() / ".fanxi-linux-boxes.json"
LOG_DIR = Path.home() / "Library" / "Application Support" / "Fanxi" / "logs"
LOCK = Path.home() / ".fanxi-watchdog.lock"
MAIN_PORT = 54300
MAIN_DISPLAY = Path.home() / "Library" / "Application Support" / "Fanxi" / "display.reg"
COOLDOWN = 180.0          # seconds before a failed client is tried again
DIALOG_GRACE = 3.0        # how long `ok` must be up before it is treated as the error
RECOVERY_WAIT = 120.0     # how long a relaunched client has to reach a zone
LOG = logging.getLogger("fanxi.watchdog")


def log_setup(verbose: bool) -> None:
    (ROOT / "data").mkdir(exist_ok=True)
    handlers = [logging.FileHandler(ROOT / "data" / "watchdog.log", encoding="utf-8")]
    if verbose:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


def launcher_config() -> dict:
    try:
        return json.loads(LAUNCHER.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"no launcher config at {LAUNCHER}: {exc}")


def box_state() -> list[dict]:
    try:
        return json.loads(BOXES.read_text())
    except (OSError, ValueError):
        return []


def api_call(base: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base.rstrip("/") + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def control(port: int, cmd: str, args: dict | None = None, timeout: float = 5.0) -> dict:
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall((json.dumps({"id": 1, "cmd": cmd, "args": args or {}}) + "\n").encode())
        return json.loads(sock.makefile().readline())


def read_state(port: int) -> dict | None:
    try:
        result = control(port, "state", timeout=3).get("result")
        return result if isinstance(result, dict) else None
    except (OSError, ValueError):
        return None


def in_world(state: dict | None) -> bool:
    return bool(state and state.get("login_status") == 2
                and (state.get("player") or {}).get("name"))


def error_dialog(state: dict | None) -> bool:
    """The FFXI-4001 box: out of the world, with the client's OK menu up."""
    if not state or state.get("login_status") != 0:
        return False
    return str(state.get("menu") or "").lower() == "ok"


def main_processes(cfg: dict) -> list[int]:
    """Local Fanxi processes for the leader account (not the headless boxes)."""
    username = str(cfg.get("username") or "")
    found = []
    try:
        rows = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True,
                              timeout=10).stdout.splitlines()
    except (OSError, subprocess.TimeoutExpired):
        return found
    for row in rows:
        parts = row.strip().split(None, 1)
        if len(parts) != 2:
            continue
        words = parts[1].split()
        if not words or os.path.basename(words[0]) not in ("fanxi", "host64"):
            continue
        if f"--user {username}" not in parts[1]:
            continue
        try:
            found.append(int(parts[0]))
        except ValueError:
            pass
    return found


def stop_process(pid: int, timeout: float = 10.0) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    end = time.time() + timeout
    while time.time() < end:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.3)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def drive_signin(port: int, timeout: float = RECOVERY_WAIT) -> dict | None:
    """Press Enter until the client is in a zone, the way the launcher's Play does."""
    deadline = time.time() + timeout
    state = None
    while time.time() < deadline:
        state = read_state(port)
        if in_world(state):
            return state
        if state is not None:
            try:
                control(port, "keys", {"keys": ["enter"], "hold_ms": 100}, timeout=3)
            except (OSError, ValueError):
                pass
        time.sleep(1.0)
    return state


def launch_main(cfg: dict) -> bool:
    """Dismiss the error dialog if it is up, then start a fresh main client."""
    for pid in main_processes(cfg):
        try:
            control(MAIN_PORT, "keys", {"keys": ["enter"], "hold_ms": 120}, timeout=3)
        except (OSError, ValueError):
            pass
        time.sleep(1.0)
        stop_process(pid)
    deadline = time.time() + 20
    while time.time() < deadline and read_state(MAIN_PORT) is not None:
        time.sleep(0.5)
    try:
        data = api_call(cfg["api_url"], cfg["token"], "POST", "/api/v1/launch",
                        {"character_id": int(cfg["character_id"])})
    except Exception as exc:  # noqa: BLE001 - report and let the next sweep retry
        LOG.error("main launch token failed: %s", exc)
        return False
    client = data.get("client") or {}
    args = [
        str(cfg.get("host64") or (ROOT / "build" / "fanxi")),
        "--game", str(cfg.get("game_dir")),
        "--server", str(client.get("server")),
        "--user", str(client.get("username")),
        "--login-token", str(data.get("login_token")),
        "--authport", str(client.get("auth_port", 54231)),
        "--dataport", str(client.get("data_port", 54230)),
        "--viewport", str(client.get("view_port", 54001)),
    ]
    if MAIN_DISPLAY.is_file():
        args += ["--reg-final", str(MAIN_DISPLAY)]
    log_path = LOG_DIR / f"game-{cfg.get('username') or 'main'}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    out = open(log_path, "ab")
    try:
        process = subprocess.Popen(args, cwd=str(ROOT), env=dict(os.environ, FFXI_CONTROL=str(MAIN_PORT)),
                                   stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                                   start_new_session=True)
    finally:
        out.close()
    LOG.info("relaunched the main client (pid %d); signing in", process.pid)
    state = drive_signin(MAIN_PORT)
    if in_world(state):
        LOG.info("main back in the world: %s in %s",
                 (state.get("player") or {}).get("name"),
                 (state.get("zone") or {}).get("name"))
        return True
    LOG.error("the main client did not reach a zone within %.0f s", RECOVERY_WAIT)
    return False


def restart_boxes(cfg: dict, boxes: list[dict], ids: list[int]) -> bool:
    """Restart the given sub-account boxes through the Linux helper."""
    if not ids:
        return True
    ssh = str(cfg.get("remote_ssh") or (boxes[0].get("ssh") if boxes else "") or "")
    command = [sys.executable, str(ROOT / "scripts" / "linux_boxes.py"), "restart",
               "--only", ",".join(str(i) for i in ids)]
    if ssh:
        command += ["--ssh", ssh]
    command += ["--api", str(cfg["api_url"]), "--token", str(cfg["token"])]
    LOG.info("restarting boxes: %s", ",".join(str(i) for i in ids))
    try:
        result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                                timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOG.error("box restart failed: %s", exc)
        return False
    for line in (result.stdout or "").strip().splitlines()[-8:]:
        LOG.info("  %s", line)
    if result.returncode != 0:
        for line in (result.stderr or "").strip().splitlines()[-8:]:
            LOG.error("  %s", line)
        return False
    return True


def restore_team(cfg: dict, boxes: list[dict]) -> None:
    state = read_state(MAIN_PORT)
    if not in_world(state):
        LOG.warning("team not restored: the main is not in the world")
        return
    name = (state.get("player") or {}).get("name")
    try:
        control(MAIN_PORT, "command", {"line": "//invite subs"}, timeout=10)
    except (OSError, ValueError) as exc:
        LOG.warning("party invite failed: %s", exc)
    for box in boxes:
        port = int(box.get("port") or 0)
        if not port or not in_world(read_state(port)):
            continue
        try:
            control(port, "follow", {"enabled": True, "leader": name, "distance": 1.0}, timeout=5)
        except (OSError, ValueError) as exc:
            LOG.warning("follow for @%s failed: %s", box.get("user"), exc)
    LOG.info("team restored: party invited, follow set to %s", name)


class Supervisor:
    def __init__(self, cfg: dict, *, dry_run: bool = False, relaunch_exit: bool = False,
                 main_recovery: bool = True) -> None:
        self.cfg = cfg
        self.dry_run = dry_run
        self.relaunch_exit = relaunch_exit
        self.main_recovery = main_recovery
        self.attempts: dict[int, float] = {}
        self.was_in_world: dict[int, bool] = {}
        self.error_since: dict[int, float] = {}
        self.last_state: dict[int, dict | None] = {}

    def cooled(self, port: int) -> bool:
        return time.time() - self.attempts.get(port, 0.0) >= COOLDOWN

    def problem(self, port: int) -> str | None:
        """'dialog', 'dead', or None.  Records the client's world state as it goes."""
        state = read_state(port)
        self.last_state[port] = state
        if state is None:
            self.error_since.pop(port, None)
            # The leader is the team: a main with no control port is restarted even when
            # this supervisor started after it quit.  A box is only restarted when it was
            # seen in the world (or --relaunch-exit asks for it), so a deliberate Stop is
            # not undone.
            if port == MAIN_PORT and self.main_recovery:
                return "dead"
            if self.was_in_world.get(port) and self.relaunch_exit:
                return "dead"
            return None
        if in_world(state):
            self.was_in_world[port] = True
            self.error_since.pop(port, None)
            return None
        # The dialog keeps the player block, so a supervisor started after the drop can
        # still recognise it; a title screen has no player name and is left alone.
        player = (state.get("player") or {}).get("name")
        if error_dialog(state) and (self.was_in_world.get(port) or player):
            return "dialog"
        else:
            self.error_since.pop(port, None)
        return None

    def sweep(self) -> bool:
        """One pass; True when a recovery ran (so the caller can restore the team)."""
        boxes = box_state()
        recovered = False
        main_problem = self.problem(MAIN_PORT)
        if main_problem and self.cooled(MAIN_PORT):
            LOG.warning("main client needs recovery (%s)", main_problem)
            self.attempts[MAIN_PORT] = time.time()
            if self.dry_run:
                LOG.info("dry run: would relaunch the main")
                recovered = True
            elif launch_main(self.cfg):
                recovered = True

        bad_ids: list[int] = []
        for box in boxes:
            port = int(box.get("port") or 0)
            if not port:
                continue
            problem = self.problem(port)
            if not problem or not self.cooled(port):
                continue
            LOG.warning("@%s needs recovery (%s)", box.get("user"), problem)
            self.attempts[port] = time.time()
            bad_ids.append(int(box.get("sub_id") or 0))
        if bad_ids:
            if self.dry_run:
                LOG.info("dry run: would restart boxes %s", bad_ids)
                recovered = True
            elif restart_boxes(self.cfg, boxes, bad_ids):
                recovered = True

        if recovered and not self.dry_run:
            restore_team(self.cfg, boxes)
        return recovered

    def run(self, interval: float) -> None:
        LOG.info("watching the main on %d and %d box(es)", MAIN_PORT, len(box_state()))
        while True:
            try:
                self.sweep()
            except Exception as exc:  # noqa: BLE001 - the supervisor must survive its own bugs
                LOG.exception("sweep failed: %s", exc)
            time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true", help="one sweep, then exit")
    parser.add_argument("--dry-run", action="store_true", help="report what would be recovered")
    parser.add_argument("--interval", type=float, default=3.0, help="seconds between sweeps")
    parser.add_argument("--relaunch-exit", action="store_true",
                        help="also relaunch a box whose control port died after it was in the world")
    parser.add_argument("--no-main", action="store_true",
                        help="do not start the leader when its client is not running")
    parser.add_argument("--verbose", action="store_true", help="also log to stdout")
    args = parser.parse_args(argv)
    log_setup(args.verbose)
    cfg = launcher_config()
    lock = LOCK.open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        LOG.error("another watchdog is already running")
        return 1
    supervisor = Supervisor(cfg, dry_run=args.dry_run, relaunch_exit=args.relaunch_exit,
                            main_recovery=not args.no_main)
    if args.once:
        supervisor.sweep()
        return 0
    supervisor.run(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
