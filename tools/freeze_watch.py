#!/usr/bin/env python3
"""Watch a running client and capture it the moment it freezes.

The client is left alone: this only polls its control port, and on a freeze runs
tools/freeze_capture.py (attach, dump, detach).  No restart, no relog.

    python3 tools/freeze_watch.py                 # newest host64, control port 54300
    python3 tools/freeze_watch.py --port 54300 --pid 1234

A freeze is three consecutive failed `state` calls (about 15 s) while the process is alive.
That is what the 2026-10-31 captures look like: the addon thread stops answering when the game
thread wedges.  The optional --ssh check also catches the server side ("silent for 180s"), for
the case where the control port still answers.
"""
import argparse
import datetime as dt
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "freeze-watch.log"


def log(line: str) -> None:
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {line}\n")
    print(f"{stamp} {line}", flush=True)


def newest_client() -> int | None:
    try:
        out = subprocess.run(["pgrep", "-f", "build/host64"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    pids = [int(p) for p in out.stdout.split() if p.strip()]
    return max(pids) if pids else None


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def state(port: int) -> dict | None:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as sock:
            sock.sendall((json.dumps({"id": 1, "cmd": "state", "args": {}}) + "\n").encode())
            reply = json.loads(sock.makefile().readline())
        result = reply.get("result")
        return result if isinstance(result, dict) else None
    except (OSError, ValueError):
        return None


def server_count(ssh: str, character: str) -> int:
    try:
        out = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", ssh,
             'journalctl -u fanxi --since "-8 min" --no-pager | grep -cE "silent for 180s|released ' + character + '"'],
            capture_output=True, text=True, timeout=20)
        return int(out.stdout.strip() or 0)
    except Exception:
        return -1


def server_silent(ssh: str, character: str) -> bool:
    """The server logs 'silent for 180s' when a client stops sending.  Optional second signal.

    A relative window keeps this independent of the two machines' time zones, and the character
    name keeps a box's timeout from triggering the main client's capture."""
    try:
        out = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", ssh,
             'journalctl -u fanxi --since "-6 min" --no-pager | grep -E "silent for 180s|released ' + character + '" | tail -5'],
            capture_output=True, text=True, timeout=20)
        return bool(out.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pid", type=int)
    ap.add_argument("--port", type=int, default=54300)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--fails", type=int, default=3, help="consecutive failed states that mean a freeze")
    ap.add_argument("--ssh", help="host alias for the second (server-side) signal")
    ap.add_argument("--account", default="Onedough", help="character name in the server log")
    ap.add_argument("--max-hours", type=float, default=6.0)
    args = ap.parse_args()

    pid = args.pid or newest_client()
    if not pid:
        print("no running host64 found", file=sys.stderr)
        return 2
    log(f"watching pid {pid} on port {args.port} (capture on {args.fails} failed states)")

    deadline = time.time() + args.max_hours * 3600
    baseline = server_count(args.ssh, args.account) if args.ssh else -1
    log(f"server silent baseline {baseline}")
    fails = 0
    last_ssh = 0.0
    started = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    while time.time() < deadline:
        if not alive(pid):
            log(f"pid {pid} is gone; stopping watch")
            return 0
        if state(args.port) is None:
            fails += 1
            log(f"state failed ({fails}/{args.fails})")
            if fails >= args.fails:
                log("freeze detected; capturing")
                subprocess.run([sys.executable, str(ROOT / "tools" / "freeze_capture.py"), "--pid", str(pid)])
                log("capture finished")
                return 0
        else:
            fails = 0

        if args.ssh and time.time() - last_ssh > 30:
            last_ssh = time.time()
            if args.ssh and server_count(args.ssh, args.account) > max(baseline, 0):
                log("server reports the client silent for 180s; capturing")
                subprocess.run([sys.executable, str(ROOT / "tools" / "freeze_capture.py"), "--pid", str(pid)])
                log("capture finished")
                return 0

        time.sleep(args.interval)

    log("watch deadline reached; stopping")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
