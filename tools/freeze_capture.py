#!/usr/bin/env python3
"""Capture a frozen host64 for the actor-list investigation (docs/freeze-actor-list.md).

The client is left exactly as it is: the probe attaches read-only, stops it for the length of
one attach, writes what it found, and detaches.  Nothing is killed, restarted or relogged.

    python3 tools/freeze_capture.py                 # the newest build/host64
    python3 tools/freeze_capture.py --pid 1234
    python3 tools/freeze_capture.py --hits 200      # longer walk sequence

Writes data/freeze-<local stamp>/:

    notes.txt        what was captured and the first thing to look at
    sample.txt       `sample <pid> 3` (the main thread's stack over three seconds)
    walk.txt         guest registers, the [node+0x54] chain, the walker's node sequence
    client-log.txt   the last 200 KB of the client's own log
    ps.txt           the process state

Then read walk.txt: a repeated node in the walker sequence is the cycle, and the chain under it
names the node that was left pointing backwards.
"""
import argparse
import datetime as dt
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TOOLS = ROOT / "tools"


def find_pid() -> int | None:
    try:
        out = subprocess.run(["pgrep", "-f", "build/host64"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    pids = [int(p) for p in out.stdout.split() if p.strip()]
    if not pids:
        return None
    # Pids grow on macOS and Linux alike, so the newest client is the largest one.
    return max(pids)


def newest_client_log() -> Path | None:
    candidates = list((Path.home() / "Library/Application Support/Fanxi/logs").glob("game-*.log"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pid", type=int, help="host64 pid (default: the newest running client)")
    ap.add_argument("--hits", type=int, default=64, help="walker hops to record (default 64)")
    ap.add_argument("--out", type=Path, help="capture folder (default data/freeze-<stamp>)")
    args = ap.parse_args()

    pid = args.pid or find_pid()
    if not pid:
        print("no running host64 found", file=sys.stderr)
        return 2
    try:
        os.kill(pid, 0)
    except OSError:
        print(f"pid {pid} is not running", file=sys.stderr)
        return 2

    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    out = args.out or (DATA / f"freeze-{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    # 1. The stack over three seconds.
    try:
        subprocess.run(["sample", str(pid), "3", "-file", str(out / "sample.txt")], timeout=30,
                       capture_output=True)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        (out / "sample.txt").write_text(f"sample failed: {exc}\n", encoding="utf-8")

    # 2. The guest state and the actor walk - only when the stack is the actor selector.  A
    # wedged client elsewhere must not be stopped by a probe whose breakpoints can never hit.
    sample = (out / "sample.txt").read_text(encoding="utf-8", errors="replace") if (out / "sample.txt").exists() else ""
    in_actor = any(name in sample for name in ("f_10158ca0", "f_10083b40", "f_10083d00"))
    if not in_actor:
        (out / "walk.txt").write_text(
            "not the actor-selector chain (no f_10158ca0 / f_10083b40 / f_10083d00 in the sample); "
            "lldb probe skipped so the client is left alone\n", encoding="utf-8")
        print("stack is not the actor chain; probe skipped")
    else:
        probe = (
            "script import sys; sys.path.insert(0, %r); import freeze_probe; "
            "freeze_probe.HITS = %d; freeze_probe.run(%r)" % (str(TOOLS), args.hits, str(out / "walk.txt"))
        )
        lldb = ["lldb", "--batch", "-p", str(pid), "-o", probe, "-o", "detach"]
        try:
            run = subprocess.run(lldb, timeout=60, capture_output=True, text=True)
            (out / "lldb.txt").write_text(run.stdout + run.stderr, encoding="utf-8")
            if run.returncode not in (0, 1):
                print(f"lldb exited {run.returncode}; see {out / 'lldb.txt'}", file=sys.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            (out / "walk.txt").write_text(f"lldb probe failed: {exc}\n", encoding="utf-8")
            # never leave the client stopped by a dead debugger
            try:
                os.kill(pid, signal.SIGCONT)
            except OSError:
                pass

    # 3. What the client itself logged, and the process state.
    log = newest_client_log()
    if log:
        size = log.stat().st_size
        with open(log, "rb") as fh:
            fh.seek(max(0, size - 200_000))
            (out / "client-log.txt").write_bytes(fh.read())
    try:
        ps = subprocess.run(["ps", "-o", "pid,ppid,etime,time,%cpu,rss,vsz,stat,command", "-p", str(pid)],
                            capture_output=True, text=True, timeout=10)
        (out / "ps.txt").write_text(ps.stdout, encoding="utf-8")
    except subprocess.SubprocessError:
        pass

    walk = (out / "walk.txt").read_text(encoding="utf-8") if (out / "walk.txt").exists() else ""
    repeated = re.findall(r"REPEATED nodes: .*", walk)
    (out / "notes.txt").write_text(
        "Freeze capture - %s (host64 pid %d)\n\n"
        "Read walk.txt first.  Phase A is the nearest-actor chain: two pointers alternating is the\n"
        "mutual-nearest cycle (the freeze), one pointer repeated is a self-match.  The chain lines\n"
        "name the actors (see docs/freeze-actor-list.md).\n\n"
        "%s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), pid,
                  repeated[0] if repeated else "walker result: see walk.txt"),
        encoding="utf-8")

    print(f"captured to {out}")
    print(repeated[0] if repeated else "no repeated node recorded; read walk.txt")
    return _finish(out, pid)


def _finish(out: Path, pid: int) -> int:
    print(f"captured to {out}")
    walk = (out / "walk.txt").read_text(encoding="utf-8") if (out / "walk.txt").exists() else ""
    m = re.findall(r"REPEATED.*", walk)
    print(m[0] if m else "see walk.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
