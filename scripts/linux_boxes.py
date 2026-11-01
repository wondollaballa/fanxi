#!/usr/bin/env python3
"""Run the sub-account boxes on the Linux host and tunnel their control ports to this Mac.

  python3 scripts/linux_boxes.py up
  python3 scripts/linux_boxes.py status
  python3 scripts/linux_boxes.py down
  python3 scripts/linux_boxes.py reap --dry-run

`--addons-lua <remote-folder>` (default `/home/onedough83/fanxi-live-addons`) sets
`FFXI_ADDONS_LUA` for the boxes, so a changed `host/addons/lua/control.lua` can be copied to
that folder and tried without rebuilding the remote `host64-headless`. A missing folder is
harmless: the client falls back to the copy embedded in the binary.

The Mac keeps the server and the main client; the five subs run as headless host64 processes on the
Linux box (build/fanxi-headless, SDL's dummy video and audio drivers). Each one listens on its own
loopback control port there, and an ssh -L tunnel makes the same port reachable on this Mac, so the
existing control protocol and the launcher can drive it unchanged.

This is the stopgap until the launcher grows a remote-host setting; it uses the launcher's saved
token and the server's /accounts/sub/{id}/launch route, so no passwords are stored here.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

STATE = Path.home() / ".fanxi-linux-boxes.json"
LOCK = Path.home() / ".fanxi-linux-boxes.lock"
LAUNCHER = Path.home() / "Library" / "Application Support" / "Fanxi" / "launcher.json"


def launcher_config() -> dict:
    try:
        return json.loads(LAUNCHER.read_text())
    except OSError:
        return {}


def api_call(base: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def control(port: int, cmd: str, args: dict | None = None, timeout: float = 5.0) -> dict:
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall((json.dumps({"id": 1, "cmd": cmd, "args": args or {}}) + "\n").encode())
        line = sock.makefile().readline()
    return json.loads(line)


def wait_port(port: int, timeout: float) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def remote_sh(ssh: str, command: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", ssh, command],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def load_state() -> list[dict]:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return []


def save_state(boxes: list[dict]) -> None:
    STATE.write_text(json.dumps(boxes, indent=2) + "\n")


def parse_etime_secs(text: str) -> int:
    """`ps` elapsed time: mm:ss, hh:mm:ss, or dd-hh:mm:ss."""
    days = 0
    if "-" in text:
        head, text = text.split("-", 1)
        try:
            days = int(head)
        except ValueError:
            days = 0
    parts = []
    for part in text.split(":"):
        try:
            parts.append(int(part))
        except ValueError:
            return days * 86400
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = 0, parts[0], parts[1]
    elif len(parts) == 1:
        hours, minutes, seconds = 0, 0, parts[0]
    else:
        return days * 86400
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def remote_games(ssh: str) -> list[dict]:
    """Every host64/headless process on the remote host with its account and age."""
    command = "ps -eo pid=,etime=,args= | grep -E '[h]ost64(-headless)?' || true"
    try:
        result = remote_sh(ssh, command, timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        return []
    games = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        etime, command = parts[1], parts[2]
        words = command.split()
        if not words:
            continue
        name = os.path.basename(words[0])
        if name not in ("fanxi", "host64", "fanxi-headless", "host64-headless"):
            continue
        user = ""
        for index, word in enumerate(words):
            if word == "--user" and index + 1 < len(words):
                user = words[index + 1]
                break
        if not user:
            continue
        games.append({
            "pid": pid,
            "user": user,
            "age": parse_etime_secs(etime),
            "command": command,
        })
    return games


def reap(args) -> int:
    """Kill remote game processes the registry does not know about, after a grace period.

    Anything named in the state file is protected: a tracked box may be starting, may have a
    slow control port, or may be in game. The launcher removes dead registry entries and the
    targeted `restart --only` path stops accounts it is deliberately replacing.
    """
    boxes = load_state()
    protected = {str(box.get("user") or "").lower() for box in boxes if box.get("user")}
    games = remote_games(args.ssh)
    if not games:
        print("no remote game processes")
        return 0
    killed = 0
    for game in games:
        user = game["user"]
        if user.lower() in protected:
            print(f"kept @{user} pid {game['pid']} (tracked)")
            continue
        if game["age"] < args.orphan_grace:
            print(f"kept @{user} pid {game['pid']} (starting, {game['age']}s old)")
            continue
        if getattr(args, "dry_run", False):
            print(f"would stop @{user} pid {game['pid']} (untracked, {game['age']}s old)")
            killed += 1
            continue
        command = (
            f"kill {game['pid']} 2>/dev/null || true; "
            "sleep 0.5; "
            f"kill -9 {game['pid']} 2>/dev/null || true; true"
        )
        try:
            remote_sh(args.ssh, command, timeout=10)
        except (subprocess.TimeoutExpired, OSError):
            print(f"could not stop @{user} pid {game['pid']}", file=sys.stderr)
            continue
        print(f"stopped orphan @{user} pid {game['pid']} ({game['age']}s old)")
        killed += 1
    if not killed:
        print("no orphaned remote game processes")
    return 0


def start_tunnel(ssh: str, port: int) -> subprocess.Popen:
    log = Path.home() / ".fanxi-linux-boxes" / f"tunnel-{port}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    out = log.open("wb")
    return subprocess.Popen(
        [
            "ssh", "-N",
            "-o", "BatchMode=yes",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3",
            "-L", f"{port}:127.0.0.1:{port}",
            ssh,
        ],
        stdout=out,
        stderr=out,
        start_new_session=True,
    )


def up(args) -> int:
    if not getattr(args, "no_reap", False):
        reap(args)
    config = launcher_config()
    base = args.api or config.get("api_url") or "http://127.0.0.1:8080"
    token = args.token or config.get("token") or ""
    if not token:
        print("no launcher token: pass --token or sign in with the launcher first", file=sys.stderr)
        return 1

    subs = api_call(base, token, "GET", "/api/v1/accounts/sub").get("subs", [])
    active = [s for s in subs if s.get("status") == "active" and s.get("character")]
    if args.only:
        wanted = {int(x) for x in args.only.split(",")}
        active = [s for s in active if int(s["id"]) in wanted]
    if not active:
        print("no active sub-accounts with characters", file=sys.stderr)
        return 1

    if args.replace:
        for box in load_state():
            stop_box(box, quiet=True)
        save_state([])

    boxes = load_state()
    used = {int(b["port"]) for b in boxes}
    next_port = args.base_port
    started = []
    for sub in active:
        user = sub["username"]
        character = sub["character"]
        if any(b.get("sub_id") == sub["id"] for b in boxes):
            print(f"@{user} already in the state file; use --replace to restart")
            continue
        while next_port in used:
            next_port += 1
        port = next_port
        used.add(port)
        if getattr(args, "force", False):
            # A previous helper run may have started this account without recording it; clear
            # every copy before opening the new control port.
            stop_remote_account(args.ssh, user)
            # The old process can outlive the kill by a moment; its control socket must be
            # gone before the new client listens on the same port.  A stuck client held it
            # for longer than the old 6 s window and the replacement then ran with no
            # control port at all ("opened but did not answer"), so wait up to 30 s and
            # skip the box rather than start one that cannot be controlled.
            for _ in range(60):
                if not remote_port_busy(args.ssh, port):
                    break
                time.sleep(0.5)
            else:
                print(f"@{user}: control port {port} is still held after 30 s; skipping")
                continue

        try:
            data = api_call(base, token, "POST", f"/api/v1/accounts/sub/{sub['id']}/launch", {})
        except urllib.error.HTTPError as error:
            print(f"@{user}: launch token refused: {error.read().decode(errors='replace')[:200]}")
            continue
        client = data["client"]
        login_token = data["login_token"]
        remote_data = f"{args.data}/{user}"
        remote_log = f"{remote_data}/game.log"
        remote_sh(args.ssh, f"mkdir -p {shlex.quote(remote_data)}")

        env = (
            f"FFXI_CONTROL={port} SDL_VIDEO_DRIVER=dummy SDL_AUDIO_DRIVER=dummy "
            f"FFXI_FX=0 LD_LIBRARY_PATH={shlex.quote(args.lib)} "
            f"FANXI_API_URL={shlex.quote(str(config.get('api_url', '')))} "
            f"FANXI_API_TOKEN={shlex.quote(str(config.get('token', '')))}"
            + (f" FFXI_ADDONS_LUA={shlex.quote(args.addons_lua)}" if args.addons_lua else "")
        )
        remote = " ".join(
            [
                f"cd {shlex.quote(args.repo)} &&",
                f"setsid env {env} ./build/fanxi-headless",
                "--game", shlex.quote(args.game),
                "--server", shlex.quote(str(client.get("server", ""))),
                "--user", shlex.quote(str(client.get("username", user))),
                "--login-token", shlex.quote(login_token),
                "--authport", str(client.get("auth_port", 54231)),
                "--dataport", str(client.get("data_port", 54230)),
                "--viewport", str(client.get("view_port", 54001)),
                "--fps-divisor", str(args.fps_divisor),
                "--data-dir", shlex.quote(remote_data),
                f"</dev/null > {shlex.quote(remote_log)} 2>&1 & echo $!",
            ]
        )
        try:
            result = remote_sh(args.ssh, remote, timeout=15)
            pid_text = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
            if result.returncode != 0 or not pid_text.isdigit():
                raise RuntimeError(result.stderr.strip()[:300] or "no pid")
        except (subprocess.TimeoutExpired, RuntimeError):
            # The started process keeps the ssh channel open on some hosts; ask for its pid
            # separately and leave the channel to time out.
            found = remote_sh(args.ssh, f"pgrep -f 'FFXI_CONTROL={port} ' | head -1")
            pid_text = found.stdout.strip().splitlines()[-1] if found.stdout.strip() else ""
            if not pid_text.isdigit():
                print(f"@{user}: could not start; log:")
                tail = remote_sh(args.ssh, f"tail -20 {shlex.quote(remote_log)} 2>/dev/null || true")
                print(tail.stdout[-2000:])
                continue

        tunnel = start_tunnel(args.ssh, port)
        boxes.append(
            {
                "sub_id": sub["id"],
                "user": user,
                "character": character.get("name"),
                "character_id": character.get("id"),
                "port": port,
                "ssh": args.ssh,
                "tunnel_pid": tunnel.pid,
                "remote_pid": int(pid_text),
                "log": remote_log,
                "data": remote_data,
                "started": int(time.time()),
            }
        )
        save_state(boxes)
        started.append((user, port, int(pid_text)))
        print(f"@{user} -> {character.get('name')} on 127.0.0.1:{port} (remote pid {pid_text})")
        time.sleep(1.0)

    if not started:
        return 1

    print("waiting for control ports...")
    ok = True
    for user, port, _pid in started:
        if not wait_port(port, args.wait):
            print(f"@{user}: control port {port} did not come up", file=sys.stderr)
            tail = remote_sh(args.ssh, f"tail -20 {shlex.quote(next(b['log'] for b in boxes if b['port'] == port))}")
            print(tail.stdout[-2000:])
            ok = False
            continue
        state = None
        for _ in range(20):
            try:
                state = control(port, "state").get("result", {})
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        if state is None:
            print(f"@{user}: control port {port} opened but did not answer", file=sys.stderr)
            ok = False
            continue
        for _ in range(12):
            if int(state.get("login_status") or 0) == 2:
                break
            try:
                control(port, "keys", {"keys": ["enter"], "hold_ms": 100}, timeout=3)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)
            state = control(port, "state").get("result", {})
        player = state.get("player") or {}
        print(f"@{user}: control up, character {player.get('name', '?')} zone {(state.get('zone') or {}).get('name', '?')}")
    return 0 if ok else 1


def stop_remote_account(ssh: str, user: str) -> None:
    """Kill every headless client for this account on the remote host, recorded or not."""
    if not ssh or not user:
        return
    pattern = shlex.quote(f"[h]ost64.*--user {user.replace(chr(39), '')}")
    command = (
        f"pkill -f {pattern} 2>/dev/null || true; "
        "sleep 0.5; "
        f"pkill -9 -f {pattern} 2>/dev/null || true; true"
    )
    try:
        remote_sh(ssh, command, timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        pass


def remote_port_busy(ssh: str, port: int) -> bool:
    """True when something on the remote host still accepts connections on this port."""
    probe = (
        "import socket,sys; s=socket.socket(); s.settimeout(0.5); "
        f"sys.exit(0 if s.connect_ex(('127.0.0.1',{int(port)})) == 0 else 1)"
    )
    try:
        return remote_sh(ssh, "python3 -c " + shlex.quote(probe), timeout=5).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return True


def stop_box(box: dict, quiet: bool = False) -> None:
    port = int(box.get("port", 0))
    user = str(box.get("user") or "")
    if port:
        try:
            control(port, "command", {"line": "/shutdown"}, timeout=3)
        except Exception:  # noqa: BLE001
            pass
    remote_pid = box.get("remote_pid")
    ssh = box.get("ssh")
    if ssh and user:
        # The recorded pid is the bash wrapper; kill the host64 by its account argument as well.
        pattern = shlex.quote(f"[h]ost64.*--user {user.replace(chr(39), '')}")
        command = f"pkill -f {pattern} 2>/dev/null || true; "
        if remote_pid:
            command += f"kill {int(remote_pid)} 2>/dev/null || true; pkill -P {int(remote_pid)} 2>/dev/null || true; "
        command += "sleep 1; "
        command += f"pkill -9 -f {pattern} 2>/dev/null || true; "
        if remote_pid:
            command += f"kill -9 {int(remote_pid)} 2>/dev/null || true; "
        command += "true"
        try:
            remote_sh(ssh, command, timeout=15)
        except (subprocess.TimeoutExpired, OSError):
            pass
    tunnel_pid = box.get("tunnel_pid")
    if tunnel_pid:
        try:
            os.kill(int(tunnel_pid), 15)
        except OSError:
            pass
        # The next ssh -L must be able to bind the same port; wait for the old tunnel to go.
        for _ in range(20):
            try:
                os.kill(int(tunnel_pid), 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            try:
                os.kill(int(tunnel_pid), 9)
            except OSError:
                pass
    if not quiet:
        print(f"stopped @{box.get('user')} (port {port})")


def restart(args) -> int:
    boxes = load_state()
    wanted = {int(x) for x in args.only.split(",")} if args.only else None
    keep = []
    for box in boxes:
        if wanted is not None and int(box.get("sub_id", 0)) not in wanted:
            keep.append(box)
            continue
        box.setdefault("ssh", args.ssh)
        stop_box(box, quiet=True)
    save_state(keep)
    args.force = True
    return up(args)


def down(args) -> int:
    boxes = load_state()
    if not boxes:
        print("no boxes in the state file")
        return 0
    for box in boxes:
        box.setdefault("ssh", args.ssh)
        stop_box(box)
    save_state([])
    return 0


def status(args) -> int:
    boxes = load_state()
    if not boxes:
        print("no boxes in the state file")
        return 0
    for box in boxes:
        try:
            state = control(int(box["port"]), "state", timeout=3).get("result", {})
            player = state.get("player") or {}
            zone = (state.get("zone") or {}).get("name", "?")
            print(f"@{box['user']:<12} {player.get('name', '?'):<12} {zone:<20} hp {player.get('hp', '?')}/{player.get('hpmax', '?')} port {box['port']}")
        except Exception as error:  # noqa: BLE001
            print(f"@{box['user']:<12} unreachable on {box['port']}: {error}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "down", "status", "restart", "reap"])
    parser.add_argument("--ssh", default="onedough83@192.168.7.201", help="ssh target of the Linux host")
    parser.add_argument("--repo", default="/home/onedough83/fanxi")
    parser.add_argument("--game", default="/home/onedough83/Games/FFXI2026")
    parser.add_argument("--data", default="/home/onedough83/fanxi-data")
    parser.add_argument("--lib", default="/home/onedough83/fanxi-lib", help="directory with libSDL3.so if it is not system-wide")
    parser.add_argument("--addons-lua", default="/home/onedough83/fanxi-live-addons",
                        help="remote folder for FFXI_ADDONS_LUA (a live control.lua without a rebuild)")
    parser.add_argument("--base-port", type=int, default=54400)
    parser.add_argument("--fps-divisor", type=int, default=2, help="1=60 fps, 2=30 fps")
    parser.add_argument("--wait", type=float, default=90.0)
    parser.add_argument("--api")
    parser.add_argument("--token")
    parser.add_argument("--only", help="comma-separated sub ids")
    parser.add_argument("--replace", action="store_true", help="stop the boxes in the state file first")
    parser.add_argument("--orphan-grace", type=int, default=120,
                        help="seconds an untracked remote game may run before it is reaped")
    parser.add_argument("--dry-run", action="store_true", help="print what reap would stop")
    parser.add_argument("--no-reap", action="store_true", help="do not reap untracked boxes before up")
    args = parser.parse_args()
    if args.action == "status":
        return status(args)
    if args.action == "reap":
        return reap(args)
    lock_file = LOCK.open("w")
    try:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("another linux_boxes.py run is already in progress", file=sys.stderr)
            return 1
        if args.action == "up":
            return up(args)
        if args.action == "down":
            return down(args)
        return restart(args)
    finally:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
        except OSError:
            pass
        lock_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
