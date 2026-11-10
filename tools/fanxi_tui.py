#!/usr/bin/env python3
"""fanxi-tui — a terminal dashboard for a Fanxi server you administer over SSH.

Run it on the machine you administer *from* (your Mac), not on the server:

    ./tools/fanxi_tui.py                 # the dashboard
    ./tools/fanxi_tui.py --status        # one-shot report, no curses
    ./tools/fanxi_tui.py --deploy        # the deploy sequence, no curses
    ./tools/fanxi_tui.py --rebuild       # rebuild the local client, no curses
    ./tools/fanxi_tui.py --rebuild-launcher  # rebuild the Rust + Tauri launcher, no curses

The menu is navigable with the arrow keys and Enter, a mouse click, or the hotkey in each label.
The pane beside it explains the selected action and its risk, and every action that changes the
server confirms first, defaulting to no. A terminal that refuses mouse reporting still works.

It keeps its connection settings in ~/.fanxi-manager.json:

    {"host": "root@203.0.113.10", "remote_dir": "/srv/fanxi",
     "url": "https://203.0.113.10.sslip.io", "key": "~/.ssh/id_rsa",
     "local_backups": "~/backups/fanxi",
     "game_dir": "~/Games/FINAL FANTASY XI", "repo": "~/fanxi"}

Environment overrides: FANXI_SSH, FANXI_REMOTE_DIR, FANXI_URL, FANXI_SSH_KEY,
FANXI_LOCAL_BACKUPS, FANXI_GAME_DIR, FANXI_REPO_ROOT, FANXI_MANAGER_CONFIG.

Everything runs through `ssh` with BatchMode=yes, so it never hangs waiting for a password;
it uses the key you already use for the box. The database is only written through the server's
own tools (`db-backup.sh`, `create-admin`, `clone_character.py`), never by a query typed at
the dashboard.

The local half — the client this Mac runs and the launcher that starts it — is read from the
checkout and the launcher's own launcher.json, so the dashboard can say whether `build/fanxi`
was built from the sources on disk and rebuild it with the same sequence as the launcher's
**Build game**: `.venv`, prepare when the game folder changed, then
`tools/build_posix.py host64`. The build streams into the output pane (q cancels it) and into
build/tui-build.log; the client that was there is kept as build/fanxi.previous, and put back
if the link fails. **Rebuild launcher** does the same for launcher-rs with install.sh's own
steps (`npm ci` when needed, then `npm run tauri build`), logging to build/tui-launcher.log.
"""
from __future__ import annotations

import argparse
import curses
import json
import os
import queue
import shlex
import shutil
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

CONFIG_PATH = Path(
    os.environ.get("FANXI_MANAGER_CONFIG", "~/.fanxi-manager.json")
).expanduser()
TOOL_DIR = Path(__file__).resolve().parent
REPO = TOOL_DIR.parent

DEFAULTS = {
    "host": "root@172.236.103.193",
    "remote_dir": "/srv/fanxi",
    "url": "https://172.236.103.193.sslip.io",
    "key": "~/.ssh/id_rsa",
    "local_backups": "~/backups/fanxi",
    # Empty means "find out": the launcher's launcher.json first, then this checkout.
    "game_dir": "",
    "repo": "",
}

CLIENT_TARGET = "host64"  # the build target; it writes build/fanxi
CLIENT_BIN = "fanxi"  # what tools/build_posix.py host64 makes
LEGACY_CLIENT_BIN = "host64"  # what earlier builds wrote; still used if that is all there is
BUILD_LOG = "tui-build.log"
PACKAGES = ["capstone>=5,<6", "pefile>=2023"]

STATUS_SCRIPT = r"""
cd __REMOTE__ || exit 1
echo "SERVICE=$(systemctl is-active fanxi 2>/dev/null || true)"
echo "CADDY=$(systemctl is-active caddy 2>/dev/null || true)"
echo "HEALTH=$(curl -s --max-time 3 http://127.0.0.1:8080/api/v1/health || true)"
echo "STATUS=$(curl -s --max-time 3 http://127.0.0.1:8080/api/v1/status || true)"
echo "DB=$(du -h data/fanxi.db 2>/dev/null | cut -f1)"
echo "DISK=$(df -h / | awk 'NR==2{print $4}')"
LATEST=$(ls -1t data/backups/fanxi-*.db 2>/dev/null | head -1)
echo "BACKUP=$LATEST"
if [ -n "$LATEST" ]; then echo "BACKUP_AGE=$(( $(date +%s) - $(stat -c %Y "$LATEST") ))"; fi
echo "COMMIT=$(sudo -u fanxi -H git -C __REMOTE__ rev-parse --short HEAD 2>/dev/null)"
echo "BRANCH=$(sudo -u fanxi -H git -C __REMOTE__ rev-parse --abbrev-ref HEAD 2>/dev/null)"
"""


# (label, hotkey) pairs rendered as clickable buttons; the hotkey still works.
BUTTONS = [
    ("deploy", ord("d")),
    ("restart", ord("R")),
    ("backup", ord("b")),
    ("pull backup", ord("p")),
    ("logs", ord("l")),
    ("registration", ord("g")),
    ("admin", ord("a")),
    ("console", ord("c")),
    ("edit", ord("e")),
    ("refresh", ord("r")),
    ("quit", ord("q")),
]


# --- config ----------------------------------------------------------------------------------


def load_config() -> dict:
    data = {}
    if CONFIG_PATH.is_file():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    config = dict(DEFAULTS)
    config.update({key: value for key, value in data.items() if value})
    for env, key in (
        ("FANXI_SSH", "host"),
        ("FANXI_REMOTE_DIR", "remote_dir"),
        ("FANXI_URL", "url"),
        ("FANXI_SSH_KEY", "key"),
        ("FANXI_LOCAL_BACKUPS", "local_backups"),
        ("FANXI_GAME_DIR", "game_dir"),
        ("FANXI_REPO_ROOT", "repo"),
    ):
        value = os.environ.get(env)
        if value:
            config[key] = value
    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.chmod(CONFIG_PATH, 0o600)


# --- ssh -------------------------------------------------------------------------------------


def ssh_command(config: dict, tty: bool = False) -> list[str]:
    command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    key = os.path.expanduser(config.get("key") or "")
    if key:
        command += ["-i", key, "-o", "IdentitiesOnly=yes"]
    if tty:
        command += ["-t"]
    command.append(config["host"])
    return command


def run_remote(config: dict, script: str, timeout: int = 90) -> tuple[int, str]:
    """Run a shell script on the server; returns (exit code, combined output)."""
    try:
        done = subprocess.run(
            ssh_command(config) + ["bash -s"],
            input=script,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except OSError as error:
        return 127, str(error)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def collect_status(config: dict) -> dict:
    remote = shlex.quote(config["remote_dir"])
    code, output = run_remote(config, STATUS_SCRIPT.replace("__REMOTE__", remote), timeout=30)
    status: dict = {"error": None if code == 0 else output.strip()[-500:]}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip().lower(), value.strip()
        if key in ("health", "status"):
            try:
                status[key] = json.loads(value)
            except ValueError:
                status[key] = None
        else:
            status[key] = value
    if code != 0 and not status.get("error"):
        status["error"] = f"ssh exited {code}"
    return status


MIGRATION_SCRIPT = r"""
python3 - <<'PY'
import json
import sqlite3
from pathlib import Path

root = Path.cwd()
db = root / "data" / "fanxi.db"
files = []
for path in sorted((root / "database" / "migrations").glob("*.sql")):
    try:
        version = int(path.name.split("_", 1)[0])
    except ValueError:
        continue
    files.append({"version": version, "name": path.name})

applied = set()
error = ""
if db.is_file():
    try:
        connection = sqlite3.connect(db, timeout=10)
        try:
            applied = {
                row[0] for row in connection.execute("SELECT version FROM schema_migrations")
            }
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc).lower():
                error = str(exc)
        finally:
            connection.close()
    except sqlite3.Error as exc:
        error = str(exc)

print("MIGRATIONS=" + json.dumps({
    "total": len(files),
    "applied": len(applied),
    "pending": [path for path in files if path["version"] not in applied],
    "error": error,
}))
PY
"""


def migration_state(config: dict) -> dict:
    """The checkout's migration files against the versions the database records.

    Reads only: the server applies migrations itself during startup (``db.initialize``), and the
    deploy restarts it, so this is how the dashboard proves that actually happened. A missing
    database is a fresh install, where every file is pending.
    """
    remote = shlex.quote(config["remote_dir"])
    code, output = run_remote(config, "cd " + remote + " && " + MIGRATION_SCRIPT, timeout=30)
    for line in reversed(output.splitlines()):
        if not line.startswith("MIGRATIONS="):
            continue
        try:
            state = json.loads(line.split("=", 1)[1])
        except ValueError:
            break
        state["ok"] = code == 0 and not state.get("error")
        return state
    return {
        "ok": False,
        "error": output.strip()[-300:] or f"ssh exited {code}",
        "total": 0,
        "applied": 0,
        "pending": [],
    }


def _migration_names(pending: list[dict], limit: int = 5) -> str:
    names = ", ".join(entry.get("name", "?") for entry in pending[:limit])
    if len(pending) > limit:
        names += f", +{len(pending) - limit} more"
    return names


def migration_summary(state: dict) -> str:
    pending = state.get("pending") or []
    total = state.get("total") or 0
    if not pending:
        return f"all {total} migration{'s' if total != 1 else ''} applied"
    return (
        f"{len(pending)} pending migration{'s' if len(pending) != 1 else ''}: "
        + _migration_names(pending)
    )


def migration_applied(pending: list[dict]) -> str:
    return (
        f"applied {len(pending)} migration{'s' if len(pending) != 1 else ''}: "
        + _migration_names(pending)
    )


CHARACTER_SEARCH_SCRIPT = r"""
python3 - <<'PY'
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

query = __QUERY__
escaped = query.replace("~", "~~").replace("%", "~%").replace("_", "~_")
now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
path = Path("data/fanxi.db")
characters = []
error = ""
if not path.is_file():
    error = "no database at %s" % path
else:
    try:
        connection = sqlite3.connect(path, timeout=10)
        connection.row_factory = sqlite3.Row
        characters = [dict(row) for row in connection.execute(
            "SELECT c.id, c.name, c.main_job, c.main_level, c.account_id, "
            "EXISTS(SELECT 1 FROM game_sessions s "
            "       WHERE s.character_id = c.id AND s.expires_at > ?) AS session "
            "FROM characters c "
            "WHERE c.name LIKE ? ESCAPE '~' "
            "ORDER BY CASE WHEN c.name = ? COLLATE NOCASE THEN 0 ELSE 1 END, "
            "         c.name COLLATE NOCASE "
            "LIMIT 26",
            (now, "%" + escaped + "%", query),
        ).fetchall()]
        connection.close()
    except sqlite3.Error as exc:
        error = str(exc)

print("CHARACTERS=" + json.dumps({
    "characters": characters[:25],
    "truncated": len(characters) > 25,
    "error": error,
}))
PY
"""


def search_characters(config: dict, query: str) -> dict:
    """Characters whose name contains ``query``, with enough to pick one.

    Read-only. ``session`` is 1 when an unexpired ``game_sessions`` row exists; that row
    can outlive the client by hours, so it is a warning to check the target is logged out,
    not proof it is currently in a zone.
    """
    remote = shlex.quote(config["remote_dir"])
    script = CHARACTER_SEARCH_SCRIPT.replace("__QUERY__", json.dumps(query))
    code, output = run_remote(config, "cd " + remote + " && " + script, timeout=30)
    for line in reversed(output.splitlines()):
        if not line.startswith("CHARACTERS="):
            continue
        try:
            state = json.loads(line.split("=", 1)[1])
        except ValueError:
            break
        state["ok"] = code == 0 and not state.get("error")
        return state
    return {
        "ok": False,
        "error": output.strip()[-300:] or f"ssh exited {code}",
        "characters": [],
        "truncated": False,
    }


def clone_command(config: dict, source: str, target: str) -> str:
    """The server-side command: the clone tool's normal backup-and-apply path."""
    remote = shlex.quote(config["remote_dir"])
    return (
        f"cd {remote} && sudo -u fanxi -H python3 tools/clone_character.py "
        f"--source={shlex.quote(source)} --target={shlex.quote(target)} "
        f"--force --apply 2>&1"
    )


def human_age(seconds: str | int | None) -> str:
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        return "?"
    if seconds <= 0:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


# --- actions ---------------------------------------------------------------------------------


def deploy(config: dict, emit) -> tuple[bool, str]:
    """Backup, pull, restart (which applies migrations), verify them and /health.

    Returns (ok, previous commit).
    """
    remote = shlex.quote(config["remote_dir"])
    # The checkout is owned by `fanxi`; git run as root refuses it as "dubious ownership".
    git = f"sudo -u fanxi -H git -C {remote}"
    _, head = run_remote(config, f"{git} rev-parse HEAD")
    previous = head.strip().splitlines()[-1] if head.strip() else ""
    emit(f"current commit: {previous[:12] or '?'}")

    emit("backing up the database…")
    code, output = run_remote(
        config,
        "cd " + remote + " && sudo -u fanxi -H ./scripts/db-backup.sh 2>&1 | tail -2",
        timeout=120,
    )
    emit(("  " + output.strip().splitlines()[-1]) if output.strip() else "  (no output)")
    if code != 0:
        return False, previous

    emit("pulling…")
    code, output = run_remote(config, f"{git} pull --ff-only 2>&1", timeout=120)
    for line in output.strip().splitlines():
        emit("  " + line)
    if code != 0:
        emit("pull rejected — the server is still on the previous commit")
        return False, previous

    _, after = run_remote(config, f"{git} rev-parse HEAD")
    after = after.strip().splitlines()[-1] if after.strip() else ""
    if after != previous:
        emit(f"now at {after[:12]}")

    # The server applies database/migrations during startup, so the restart below is also the
    # migration step. Read the files first to say what is new, and again afterwards to prove it
    # ran: a deploy that leaves a migration unapplied is a failed deploy even if /health is up.
    before = migration_state(config)
    pending = before.get("pending") or []
    if before.get("ok"):
        emit("migrations — " + migration_summary(before))
    else:
        emit("migrations — could not read schema_migrations: " + before.get("error", "?"))

    if after == previous and before.get("ok") and not pending:
        emit("already on this commit — nothing to deploy")
        return True, previous
    if after == previous:
        emit("no new commit — restarting to apply or verify migrations")

    emit("restarting…")
    run_remote(config, "systemctl restart fanxi")

    for attempt in range(20):
        time.sleep(1)
        _, health = run_remote(
            config, "curl -s --max-time 3 http://127.0.0.1:8080/api/v1/health", timeout=10
        )
        if '"status":"ok"' in health:
            applied = migration_state(config)
            remaining = applied.get("pending") or []
            if not applied.get("ok"):
                emit(f"healthy after {attempt + 1}s, but migrations could not be verified: "
                     + applied.get("error", "?"))
                return True, previous
            if remaining:
                emit(f"health OK after {attempt + 1}s, but a migration was not applied — "
                     + migration_summary(applied))
                emit("check the journal (l) for the SQL error before rolling back")
                return False, previous
            if pending:
                emit("migrations — " + migration_applied(pending))
            else:
                emit("migrations — " + migration_summary(applied))
            emit(f"healthy after {attempt + 1}s")
            return True, previous
    applied = migration_state(config)
    if applied.get("ok"):
        emit("migrations — " + migration_summary(applied))
        if applied.get("pending"):
            emit("a migration did not apply: the journal (l) has the SQL error")
    else:
        emit("migrations — could not verify after the restart: " + applied.get("error", "?"))
    emit("health check did not come back")
    return False, previous


def rollback(config: dict, commit: str, emit) -> bool:
    if not commit:
        emit("no previous commit recorded")
        return False
    remote = shlex.quote(config["remote_dir"])
    emit(f"rolling back to {commit[:12]}…")
    code, _ = run_remote(config, f"sudo -u fanxi -H git -C {remote} checkout {shlex.quote(commit)}")
    run_remote(config, "systemctl restart fanxi")
    time.sleep(2)
    _, health = run_remote(config, "curl -s --max-time 3 http://127.0.0.1:8080/api/v1/health")
    ok = '"status":"ok"' in health
    emit("rollback healthy" if ok else "rollback did not come back healthy")
    return ok and code == 0


def backup_now(config: dict, emit) -> bool:
    remote = shlex.quote(config["remote_dir"])
    emit("taking a backup on the server…")
    code, output = run_remote(
        config, f"cd {remote} && sudo -u fanxi -H ./scripts/db-backup.sh 2>&1 | tail -3", timeout=120
    )
    for line in output.strip().splitlines():
        emit("  " + line)
    return code == 0


def pull_backup(config: dict, emit) -> bool:
    script = REPO / "scripts" / "pull-offsite-backup.sh"
    if not script.is_file():
        emit(f"missing {script}")
        return False
    emit("pulling the latest backup home (as the homelab job does)…")
    env = dict(os.environ)
    env["FANXI_SSH"] = config["host"]
    env["FANXI_REMOTE_DIR"] = config["remote_dir"]
    env["FANXI_BACKUP_DIR"] = os.path.expanduser(config["local_backups"])
    try:
        done = subprocess.run(["sh", str(script)], env=env, text=True, capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        emit("  timed out")
        return False
    for line in (done.stdout + done.stderr).strip().splitlines()[-4:]:
        emit("  " + line)
    return done.returncode == 0


def toggle_registration(config: dict, emit) -> bool:
    remote = shlex.quote(config["remote_dir"])
    script = f"""cd {remote} && sudo -u fanxi -H python3 - <<'PY'
import sqlite3
db = sqlite3.connect("data/fanxi.db")
row = db.execute("SELECT value FROM settings WHERE key='registration_open'").fetchone()
open_now = row is None or row[0] == "1"
value = "0" if open_now else "1"
db.execute(
    "INSERT INTO settings (key, value) VALUES ('registration_open', ?) "
    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
    (value,),
)
db.commit()
print("registration", "open" if value == "1" else "closed")
PY"""
    code, output = run_remote(config, script)
    for line in output.strip().splitlines():
        emit("  " + line)
    return code == 0


def tail_logs(config: dict, lines: int = 250) -> str:
    _, output = run_remote(
        config,
        f"journalctl -u fanxi -n {int(lines)} --no-pager --output=short-iso 2>&1",
        timeout=30,
    )
    return output


# --- local client ------------------------------------------------------------------------------
#
# The dashboard runs where the client does, so it can also answer "is build/fanxi the one these
# sources make?" and rebuild it. The sequence is the launcher's Build game (src-tauri/src/game.rs),
# kept in Python here so a rebuild needs no launcher window: .venv, prepare when the game folder
# changed, then tools/build_posix.py host64.


def read_json(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def launcher_config_path(home: Path | None = None) -> Path:
    """Where the launcher keeps launcher.json: the same rules as config::data_dir()."""
    override = os.environ.get("FANXI_LAUNCHER_DIR")
    if override:
        return Path(os.path.expanduser(override)) / "launcher.json"
    home = Path(home) if home else Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Fanxi" / "launcher.json"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or home) / "Fanxi" / "launcher.json"
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else home / ".local" / "share"
    return base / "fanxi" / "launcher.json"


def read_launcher_config(home: Path | None = None) -> dict:
    return read_json(launcher_config_path(home))


def is_repo(path: Path | str | None) -> bool:
    if not path:
        return False
    path = Path(path)
    tools = path / "tools"
    return (
        (tools / "build_posix.py").is_file() or (tools / "build.py").is_file()
    ) and (path / "host").is_dir() and (path / "runtime" / "portable").is_dir()


def resolve_repo(config: dict) -> Path | None:
    """The checkout to build: your setting, the launcher's checkout, else this script's own."""
    for value in (config.get("repo"), read_launcher_config().get("repo_root"), str(REPO)):
        if not value:
            continue
        path = Path(os.path.expanduser(str(value)))
        if is_repo(path):
            return path.resolve()
    return None


def is_game_dir(path: Path | str | None) -> bool:
    if not path:
        return False
    path = Path(path)
    return (
        (path / "FFXiMain.dll").is_file()
        and (path / "FFXi.dll").is_file()
        and (path / "ROM").is_dir()
    )


def stamped_game_dir(repo: Path | None) -> str:
    """The game folder tools/prepare.py recorded in generated/build.json, if any."""
    if not repo:
        return ""
    return str(read_json(Path(repo) / "generated" / "build.json").get("game") or "")


def game_dir_candidates(
    config: dict,
    repo: Path | None = None,
    launcher: dict | None = None,
    home: Path | None = None,
) -> list[tuple[Path, str]]:
    """The game folders on this machine, in the order they win, with where each came from."""
    home = Path(home) if home else Path.home()
    launcher = read_launcher_config(home) if launcher is None else launcher
    rows: list[tuple[Path, str]] = []

    def add(value, origin: str) -> None:
        if not value:
            return
        path = Path(os.path.expanduser(str(value)))
        if is_game_dir(path):
            rows.append((path.resolve(), origin))

    add(config.get("game_dir"), "game_dir setting")
    add(launcher.get("game_dir"), "the launcher")
    add(stamped_game_dir(repo), "generated/build.json")
    games = home / "Games"
    if games.is_dir():
        try:
            children = sorted(path for path in games.iterdir() if path.is_dir())
        except OSError:
            children = []
        for child in children:
            add(child, "~/Games")
    for path in (
        games / "FINAL FANTASY XI",
        home / "SquareEnix" / "FINAL FANTASY XI",
        home / "Documents" / "FINAL FANTASY XI",
        home / "Desktop" / "FINAL FANTASY XI",
        Path("/Applications/FINAL FANTASY XI"),
        Path("/Games/FINAL FANTASY XI"),
    ):
        add(path, "a usual place")
    seen: set[Path] = set()
    unique: list[tuple[Path, str]] = []
    for path, origin in rows:
        if path not in seen:
            seen.add(path)
            unique.append((path, origin))
    return unique


def needs_prepare(repo: Path, game: Path) -> bool:
    """Whether generated/build.json is missing or names a different game folder."""
    chosen = read_json(Path(repo) / "generated" / "build.json").get("game")
    if not chosen:
        return True
    return Path(os.path.expanduser(str(chosen))).resolve() != Path(game).resolve()


def client_binary(repo: Path) -> Path:
    build = Path(repo) / "build"
    binary = build / CLIENT_BIN
    if binary.is_file():
        return binary
    return build / LEGACY_CLIENT_BIN


def newest_source_mtime(repo: Path) -> float:
    """The newest hand-written client source; generated/ is an output, so it is left out.

    host/addons is walked through because the build embeds its Lua into the client.
    """
    newest = 0.0

    def visit(directory: Path, suffixes: tuple) -> None:
        nonlocal newest
        try:
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix in suffixes:
                    try:
                        newest = max(newest, path.stat().st_mtime)
                    except OSError:
                        pass
        except OSError:
            pass

    for folder in ("host", "runtime", "runtime/portable"):
        visit(Path(repo) / folder, (".c", ".h", ".cpp", ".m"))
    visit(Path(repo) / "host" / "addons", (".c", ".h", ".cpp", ".lua"))
    try:
        newest = max(newest, (Path(repo) / "runtime.json").stat().st_mtime)
    except OSError:
        pass
    return newest


def client_state(repo: Path) -> dict:
    """What build/fanxi is, and whether the sources on disk have moved past it.

    The launcher's rule is runtime.json's version against the stamp the build wrote in
    build/runtime.json. A newer source file is the extra hint for a checkout that was edited
    without raising the version; it is a mtime comparison, not proof.
    """
    binary = client_binary(repo)
    stamp = read_json(Path(repo) / "build" / "runtime.json")
    wanted = str(read_json(Path(repo) / "runtime.json").get("version") or "")
    state = {
        "path": binary,
        "exists": binary.is_file(),
        "version": str(stamp.get("version") or ""),
        "commit": str(stamp.get("commit") or ""),
        "build": str(stamp.get("build") or ""),
        "wanted": wanted,
        "stale": False,
        "reason": "",
    }
    if not state["exists"]:
        state.update(stale=True, reason="not built")
        return state
    if not stamp:
        state.update(stale=True, reason="no build stamp")
        return state
    if wanted and state["version"] != wanted:
        state.update(stale=True, reason="the version changed")
        return state
    try:
        built_at = binary.stat().st_mtime
    except OSError:
        built_at = 0.0
    if newest_source_mtime(repo) > built_at:
        state.update(stale=True, reason="sources are newer")
    return state


def local_client(config: dict) -> dict:
    """client_state() for the checkout this dashboard builds; empty without a checkout."""
    repo = resolve_repo(config)
    return client_state(repo) if repo else {}


def client_summary(state: dict) -> str:
    if not state:
        return "no checkout"
    if not state.get("exists"):
        return "not built"
    version = str(state.get("version") or state.get("wanted") or "?")
    commit = str(state.get("commit") or "")[:7]
    text = f"{version} @ {commit}" if commit else version
    if state.get("stale"):
        text += f" (stale — {state.get('reason') or 'sources changed'})"
    return text


def client_badge(state: dict) -> tuple[str, int]:
    """The status row's short form: text and a curses colour pair."""
    if not state:
        return "no checkout", 4
    if not state.get("exists"):
        return "not built", 3
    text = str(state.get("version") or state.get("wanted") or "?")
    commit = str(state.get("commit") or "")[:7]
    if commit:
        text += f" @{commit}"
    if state.get("stale"):
        return text + " · stale", 4
    return text, 2


def venv_python(repo: Path) -> Path:
    if os.name == "nt":
        return Path(repo) / ".venv" / "Scripts" / "python.exe"
    return Path(repo) / ".venv" / "bin" / "python"


def system_python() -> str:
    """The interpreter a fresh .venv is made from.

    The interpreter decides the architecture of everything clang builds under it, so on macOS
    prefer the native Homebrew python (as the launcher and tools/setup.py do): a python running
    under Rosetta builds the whole client x86_64. FANXI_PYTHON overrides the choice.
    """
    given = os.environ.get("FANXI_PYTHON")
    if given and given.strip():
        return given.strip()
    if sys.platform == "darwin":
        machine = os.uname().machine if hasattr(os, "uname") else ""
        homebrew = "/opt/homebrew/bin/python3" if machine == "arm64" else "/usr/local/bin/python3"
        for candidate in (homebrew, "/usr/bin/python3"):
            if os.path.isfile(candidate):
                return candidate
    return shutil.which("python3") or sys.executable or "python3"


def native_machine() -> str:
    """This Mac's own architecture, even when this process runs under Rosetta."""
    if sys.platform == "darwin":
        try:
            done = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True,
                                  text=True, timeout=5)
            if done.returncode == 0 and done.stdout.strip() == "1":
                return "arm64"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return os.uname().machine if hasattr(os, "uname") else ""


def running_translated() -> bool:
    """Whether this process is the x86_64 slice under Rosetta on Apple silicon."""
    if sys.platform != "darwin":
        return False
    try:
        done = subprocess.run(["sysctl", "-n", "sysctl.proc_translated"], capture_output=True,
                              text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0 and done.stdout.strip() == "1"


def python_machine(python: str) -> str:
    """The architecture an interpreter reports for itself (arm64, x86_64, ...)."""
    try:
        done = subprocess.run([python, "-c", "import platform; print(platform.machine())"],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def build_environment(python: str, progress: bool) -> dict:
    """Extra environment for the build driver.

    A universal binary such as /usr/bin/clang takes the architecture preference of the process
    that started the chain: a TUI run by an Intel/Anaconda python makes clang target x86_64 even
    when the build itself runs under the native .venv python, and the link then rejects the
    arm64 objects already on disk. Pin the compiler to this Mac's own architecture in that case,
    which also changes .flags, so build_posix.py drops the mixed objects and recompiles them.
    """
    env = {"FFXI_PROGRESS": "1"} if progress else {}
    if sys.platform == "darwin":
        arch = native_machine()
        if arch and (running_translated() or python_machine(python) not in ("", arch)):
            if not os.environ.get("XI_CC"):
                env["XI_CC"] = f"clang -arch {arch}"
            if not os.environ.get("XI_CXX"):
                env["XI_CXX"] = f"clang++ -arch {arch}"
    return env


def terminate_process(process: subprocess.Popen) -> None:
    """Stop a build and the compiler children it started, in one stroke."""
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()
    except OSError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()
        except OSError:
            pass


def local_run(command: list, cwd: Path, emit, env: dict | None = None, should_stop=None,
              log_path: Path | None = None) -> int:
    """Run one build step, handing its output to emit as it arrives.

    A reader thread feeds a queue, so the dashboard can draw (and cancel) while a compile runs;
    the child gets its own process group so a cancel takes the compiler's children with it.
    """
    environment = dict(os.environ)
    environment.setdefault("PYTHONUNBUFFERED", "1")
    if env:
        environment.update(env)
    log = None
    if log_path:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            log = open(log_path, "a", encoding="utf-8")
            log.write("# %s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"),
                                      " ".join(str(part) for part in command)))
        except OSError:
            log = None
    try:
        process = subprocess.Popen(
            [str(part) for part in command],
            cwd=str(cwd),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
            start_new_session=(os.name == "posix"),
        )
    except OSError as error:
        message = f"could not run {command[0]}: {error}"
        emit(message)
        if log:
            log.write(message + "\n")
            log.close()
        return 127
    lines: "queue.Queue[str | None]" = queue.Queue()

    def pump() -> None:
        stream = process.stdout
        try:
            if stream is not None:
                for line in stream:
                    lines.put(line.rstrip("\n"))
        finally:
            lines.put(None)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    cancelled = False
    try:
        while True:
            if should_stop is not None and should_stop():
                cancelled = True
                terminate_process(process)
                break
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                break
            if log:
                log.write(line + "\n")
                log.flush()
            emit(line)
    except BaseException:
        terminate_process(process)
        raise
    finally:
        if cancelled and process.poll() is None:
            terminate_process(process)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            terminate_process(process)
        reader.join(timeout=2)
        if process.stdout is not None:
            try:
                process.stdout.close()
            except OSError:
                pass
        if log:
            log.close()
    if cancelled:
        emit("cancelled")
        return 130
    return process.returncode or 0


def ensure_build_tools(repo: Path, emit, should_stop=None,
                       log_path: Path | None = None) -> str | None:
    """The checkout's .venv with capstone and pefile, made the way the launcher makes it."""
    python = venv_python(repo)
    if not python.is_file():
        system = system_python()
        emit(f"creating .venv with {system}…")
        code = local_run([system, "-m", "venv", str(Path(repo) / ".venv")], repo, emit,
                         should_stop=should_stop, log_path=log_path)
        if code != 0 or not python.is_file():
            emit("could not create .venv — is Python 3.9+ installed?")
            return None
    try:
        probe = subprocess.run(
            [str(python), "-c", "import capstone, pefile"],
            cwd=str(repo), capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        probe = None
    if probe is None or probe.returncode != 0:
        emit("installing the recompiler's Python packages (capstone, pefile)…")
        code = local_run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-q"]
                         + PACKAGES, repo, emit, should_stop=should_stop, log_path=log_path)
        if code != 0:
            emit("could not install capstone and pefile (the first build needs network)")
            return None
    return str(python)


def keep_client(repo: Path, binary: Path, emit) -> Path | None:
    """Copy the working client aside before a rebuild; returns the copy, or None.

    clang deletes its output when the link fails, and the output is the client the launcher
    starts, so a failed rebuild must not leave the player with nothing to run.
    """
    if not binary.is_file():
        return None
    previous = binary.with_name(binary.name + ".previous")
    try:
        shutil.copy2(binary, previous)
        stamp = Path(repo) / "build" / "runtime.json"
        if stamp.is_file():
            shutil.copy2(stamp, Path(repo) / "build" / "runtime.previous.json")
    except OSError as error:
        emit(f"could not keep a copy of the current client: {error}")
        return None
    emit(f"kept the current client as {previous}")
    return previous


def restore_client(repo: Path, binary: Path, previous: Path, emit) -> None:
    """Put the kept client back when a failed or cancelled build left none."""
    if binary.is_file() or not previous.is_file():
        return
    try:
        shutil.copy2(previous, binary)
        stamp = Path(repo) / "build" / "runtime.previous.json"
        if stamp.is_file():
            shutil.copy2(stamp, Path(repo) / "build" / "runtime.json")
    except OSError as error:
        emit(f"could not restore the previous client: {error}")
        return
    emit(f"the previous client is back at {binary}; the log says why the rebuild failed")


def build_client(config: dict, emit, *, progress: bool = False, should_stop=None,
                 game: Path | str | None = None, repo: Path | str | None = None) -> bool:
    """Rebuild build/fanxi the way the launcher's Build game does.

    ``progress`` asks the driver for @phase/@progress lines, which the curses pane renders;
    without it the build prints its ordinary output. ``game`` and ``repo`` skip discovery
    (the dashboard has already asked), and ``should_stop`` cancels the compile.
    """
    if os.name == "nt":
        emit("the local rebuild supports macOS and Linux; use the launcher's Build game on Windows")
        return False
    repository = Path(repo).resolve() if repo else resolve_repo(config)
    if repository is None:
        emit(f"no Fanxi checkout found: set \"repo\" in {CONFIG_PATH} or FANXI_REPO_ROOT")
        return False
    if not is_repo(repository):
        emit(f"{repository} is not a Fanxi checkout (tools/build_posix.py is missing)")
        return False
    origin = "chosen"
    if game:
        folder = Path(os.path.expanduser(str(game))).resolve()
    else:
        candidates = game_dir_candidates(config, repository)
        if not candidates:
            emit("no FINAL FANTASY XI folder found: pass --game or set FANXI_GAME_DIR")
            return False
        folder, origin = candidates[0]
    if not is_game_dir(folder):
        emit(f"{folder} is not a FINAL FANTASY XI folder "
             "(FFXiMain.dll, FFXi.dll and ROM are needed)")
        return False

    emit(f"checkout   {repository}")
    emit(f"game dir   {folder}  ({origin})")
    log_path = repository / "build" / BUILD_LOG
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log:
            log.write("\n# --- local client rebuild %s ---\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    except OSError:
        pass

    python = ensure_build_tools(repository, emit, should_stop=should_stop, log_path=log_path)
    if python is None:
        return False

    extra = build_environment(python, progress)
    if extra.get("XI_CC") and not os.environ.get("XI_CC"):
        reason = ("this dashboard runs under Rosetta" if running_translated()
                  else f"{python} is {python_machine(python)}")
        emit(f"pinning clang to {native_machine()} ({reason}, so plain clang would target that "
             "architecture)")
        emit("the first build after that recompiles every object; later ones are incremental")
    if needs_prepare(repository, folder):
        emit("reading the game build (tools/prepare.py)…")
        code = local_run([python, "tools/prepare.py", "--game", str(folder)], repository, emit,
                         env=extra, should_stop=should_stop, log_path=log_path)
        if code == 130:
            emit("rebuild cancelled")
            return False
        if code != 0:
            emit(f"could not read the game files — see {log_path}")
            return False
    else:
        emit("game files unchanged; skipping prepare")

    emit(f"translating and compiling ({CLIENT_TARGET})…")
    existing = client_binary(repository)
    previous = keep_client(repository, existing, emit)
    code = local_run([python, "tools/build_posix.py", CLIENT_TARGET, "--game", str(folder)],
                     repository, emit, env=extra, should_stop=should_stop, log_path=log_path)
    if code == 130:
        if previous:
            restore_client(repository, existing, previous, emit)
        emit("rebuild cancelled")
        return False
    if code != 0:
        if previous:
            restore_client(repository, existing, previous, emit)
        emit(f"the build failed — {log_path} has the whole log")
        return False
    binary = client_binary(repository)
    if not binary.is_file():
        if previous:
            restore_client(repository, existing, previous, emit)
        emit(f"the build finished but {binary} is missing")
        return False
    emit(f"built {binary} — {client_summary(client_state(repository))}")
    return True


# --- local launcher ----------------------------------------------------------------------------
#
# The other half of the same checkout: the Rust + Tauri launcher.  install.sh builds it with
# `npm ci && npm run tauri build -- --bundles app` on macOS (--no-bundle on Linux); this keeps
# that sequence in one place so the dashboard can rebuild the app it is looking at.

LAUNCHER_DIR = "launcher-rs"
LAUNCHER_APP = (Path("src-tauri") / "target" / "release" / "bundle" / "macos"
                / "Fanxi Launcher.app")
LAUNCHER_BIN = Path("src-tauri") / "target" / "release" / "fanxi-launcher"
LAUNCHER_LOG = "tui-launcher.log"
LAUNCHER_MIN_RUST = (1, 85)
LAUNCHER_MIN_NODE = 18


def launcher_root(repo: Path | None) -> Path | None:
    """The launcher-rs checkout inside *repo*, if this is a Fanxi checkout with one."""
    if not repo:
        return None
    root = Path(repo) / LAUNCHER_DIR
    if (root / "package.json").is_file() and (root / "src-tauri" / "Cargo.toml").is_file():
        return root
    return None


def launcher_artifact(root: Path) -> tuple[Path, str]:
    """Where the platform's build lands: the .app bundle on macOS, the binary elsewhere."""
    if sys.platform == "darwin":
        return Path(root) / LAUNCHER_APP, "app"
    return Path(root) / LAUNCHER_BIN, "binary"


def launcher_executable(root: Path, artifact: Path, kind: str) -> Path:
    if kind == "app":
        return Path(artifact) / "Contents" / "MacOS" / "fanxi-launcher"
    return Path(artifact)


def launcher_version(root: Path) -> str:
    return str(read_json(Path(root) / "src-tauri" / "tauri.conf.json").get("version") or "")


def newest_launcher_source(root: Path) -> float:
    """The newest file `npm run tauri build` reads; node_modules and dist are outputs."""
    newest = 0.0

    def visit(directory: Path, suffixes: tuple) -> None:
        nonlocal newest
        if not directory.is_dir():
            return
        try:
            entries = directory.rglob("*")
        except OSError:
            return
        for path in entries:
            if path.is_file() and path.suffix in suffixes:
                try:
                    newest = max(newest, path.stat().st_mtime)
                except OSError:
                    pass

    visit(Path(root) / "src", (".ts", ".tsx", ".js", ".jsx", ".css", ".html"))
    visit(Path(root) / "src-tauri" / "src", (".rs",))
    visit(Path(root) / "src-tauri" / "icons", (".png", ".icns", ".ico", ".svg"))
    for name in (
        "package.json", "package-lock.json", "index.html", "vite.config.ts", "vite.config.js",
        "tsconfig.json", "tsconfig.node.json", "src-tauri/Cargo.toml", "src-tauri/Cargo.lock",
        "src-tauri/build.rs", "src-tauri/tauri.conf.json",
    ):
        try:
            newest = max(newest, (Path(root) / name).stat().st_mtime)
        except OSError:
            pass
    return newest


def launcher_state(repo: Path | None) -> dict:
    """What the launcher build is, and whether the sources on disk have moved past it."""
    root = launcher_root(repo)
    if root is None:
        return {}
    artifact, kind = launcher_artifact(root)
    executable = launcher_executable(root, artifact, kind)
    state = {
        "root": root, "artifact": artifact, "kind": kind,
        "version": launcher_version(root),
        "exists": executable.is_file(),
        "stale": False, "reason": "",
    }
    if not state["exists"]:
        state.update(stale=True, reason="not built")
        return state
    try:
        built_at = executable.stat().st_mtime
    except OSError:
        built_at = 0.0
    if newest_launcher_source(root) > built_at:
        state.update(stale=True, reason="sources are newer")
    return state


def launcher_summary(state: dict) -> str:
    if not state:
        return "no launcher-rs"
    if not state.get("exists"):
        return "not built"
    version = str(state.get("version") or "?")
    if state.get("stale"):
        return f"{version} · stale — {state.get('reason') or 'sources changed'}"
    return f"{version} · built"


def ensure_launcher_tools(root: Path, emit, should_stop=None,
                          log_path: Path | None = None) -> str | None:
    """Check Node and Rust, and install the npm packages when node_modules is missing or old."""
    missing = [name for name in ("node", "npm", "cargo") if not shutil.which(name)]
    if missing:
        emit("missing " + ", ".join(missing)
             + " — install Node 18+ and Rust 1.85+ to build the launcher")
        return None
    node = shutil.which("node")
    try:
        check = subprocess.run(
            [node, "-e",
             "process.exit(Number(process.versions.node.split('.')[0]) >= 18 ? 0 : 1)"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        check = None
    if check is None or check.returncode != 0:
        emit(f"Node {LAUNCHER_MIN_NODE} or newer is required to build the launcher")
        return None
    cargo = shutil.which("cargo")
    try:
        version = subprocess.run([cargo, "--version"], capture_output=True, text=True, timeout=30)
        words = version.stdout.split()
        if len(words) >= 2:
            numbers = words[1].split(".")
            try:
                found = (int(numbers[0]), int(numbers[1]))
            except (IndexError, ValueError):
                found = LAUNCHER_MIN_RUST
            if found < LAUNCHER_MIN_RUST:
                emit(f"Rust {LAUNCHER_MIN_RUST[0]}.{LAUNCHER_MIN_RUST[1]} or newer is required "
                     f"(found {words[1]})")
                return None
    except (OSError, subprocess.TimeoutExpired):
        emit("could not run cargo — is Rust 1.85+ installed?")
        return None
    npm = shutil.which("npm") or "npm"
    lock = Path(root) / "package-lock.json"
    stamp = Path(root) / "node_modules" / ".package-lock.json"
    tauri = Path(root) / "node_modules" / ".bin" / "tauri"
    install = not tauri.is_file()
    if not install and lock.is_file() and stamp.is_file():
        try:
            install = lock.stat().st_mtime > stamp.stat().st_mtime
        except OSError:
            pass
    if install:
        if not lock.is_file():
            emit(f"{lock} is missing; cannot install the launcher's packages")
            return None
        emit("installing the launcher's packages (npm ci)…")
        code = local_run([npm, "ci"], Path(root), emit,
                         env={"NO_COLOR": "1", "npm_config_color": "false"},
                         should_stop=should_stop, log_path=log_path)
        if code == 130:
            emit("rebuild cancelled")
            return None
        if code != 0 or not tauri.is_file():
            emit("could not install the launcher's packages — see the log")
            return None
    return npm


def build_launcher(config: dict, emit, *, progress: bool = False, should_stop=None,
                   repo: Path | str | None = None) -> bool:
    """Build the Rust + Tauri launcher the way install.sh does.

    ``npm ci`` runs when node_modules is missing or older than package-lock.json, then
    ``npm run tauri build``: ``--bundles app`` on macOS (the app the launcher is run from)
    and ``--no-bundle`` on Linux (the release binary and desktop entry).  The build output
    goes to build/tui-launcher.log.
    """
    if os.name == "nt":
        emit("the local rebuild supports macOS and Linux; build on Windows with install.sh")
        return False
    repository = Path(repo).resolve() if repo else resolve_repo(config)
    if repository is None:
        emit(f"no Fanxi checkout found: set \"repo\" in {CONFIG_PATH} or FANXI_REPO_ROOT")
        return False
    root = launcher_root(repository)
    if root is None:
        emit(f"{repository} has no launcher-rs checkout")
        return False
    log_path = repository / "build" / LAUNCHER_LOG
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log:
            log.write("\n# --- local launcher rebuild %s ---\n"
                      % time.strftime("%Y-%m-%d %H:%M:%S"))
    except OSError:
        pass

    emit(f"checkout    {repository}")
    emit(f"launcher    {root}")
    emit(f"before      {launcher_summary(launcher_state(repository))}")
    npm = ensure_launcher_tools(root, emit, should_stop=should_stop, log_path=log_path)
    if npm is None:
        return False

    command = [npm, "run", "tauri", "build", "--"]
    if sys.platform == "darwin":
        command += ["--bundles", "app"]
    else:
        command += ["--no-bundle"]
    emit("building the launcher (npm run tauri build)…")
    code = local_run(command, root, emit,
                     env={"CARGO_TERM_COLOR": "never", "NO_COLOR": "1",
                          "npm_config_color": "false"},
                     should_stop=should_stop, log_path=log_path)
    if code == 130:
        emit("rebuild cancelled")
        return False
    if code != 0:
        emit(f"the launcher build failed — {log_path} has the whole log")
        return False
    state = launcher_state(repository)
    if not state.get("exists"):
        emit("the build finished but the launcher artifact is missing")
        return False
    emit(f"built {state['artifact']} — {launcher_summary(state)}")
    return True


# --- terminal UI -----------------------------------------------------------------------------


class Action:
    """One menu entry: what it does, what it risks, and whether it asks first."""

    __slots__ = ("key", "label", "desc", "risk", "confirm", "danger")

    def __init__(self, key, label, desc, risk="", confirm=False, danger=False):
        self.key = key
        self.label = label
        self.desc = desc
        self.risk = risk
        self.confirm = confirm
        self.danger = danger


ACTIONS = [
    Action(
        "d",
        "Deploy update",
        "Backs up the database, pulls origin/main, restarts the service (which applies any new "
        "database/migrations), then polls /health for 20 seconds and confirms every migration "
        "file is recorded in schema_migrations. If the service does not come back, it offers a "
        "rollback to the commit that was running.",
        "Players are disconnected while the service restarts (a few seconds). Only what is "
        "pushed to origin/main is pulled, so unpushed work stays on your machine. A deploy fails "
        "if a migration is left unapplied; the backup taken first is what restores the schema.",
        confirm=True,
        danger=True,
    ),
    Action(
        "B",
        "Rebuild client",
        "Rebuilds build/fanxi, the client the launcher starts, from this checkout and the game "
        "folder the launcher uses. It makes .venv with capstone and pefile if missing, runs "
        "tools/prepare.py when generated/build.json names another folder, then "
        "tools/build_posix.py host64, streaming the compile's progress here. The first build "
        "takes several minutes; later ones only recompile what changed. Fanxi.app is a different "
        "build (tools/setup.py).",
        "Replaces build/fanxi. Clients already running keep the old binary until they are "
        "restarted; the server is not touched. The first run may create .venv and download "
        "capstone and pefile, and a dashboard started under Rosetta pins clang to this Mac's "
        "architecture, which recompiles everything once. q cancels a build in progress.",
        confirm=True,
    ),
    Action(
        "L",
        "Rebuild launcher",
        "Builds the Rust + Tauri launcher from launcher-rs with the same commands as install.sh: "
        "npm ci when node_modules is missing or older than package-lock.json, then "
        "npm run tauri build -- --bundles app on macOS (--no-bundle on Linux). The first build "
        "compiles Rust and takes several minutes; later ones are incremental. The macOS app "
        "lands at launcher-rs/src-tauri/target/release/bundle/macos/Fanxi Launcher.app.",
        "Replaces the built launcher. A launcher that is already open keeps the old binary until "
        "it is restarted; build/fanxi and the server are not touched. Needs Node 18+, Rust 1.85+ "
        "and the Tauri build packages (Xcode command line tools on macOS, WebKitGTK 4.1 on "
        "Linux). The first run may execute npm ci and use the network. q cancels a build in "
        "progress.",
        confirm=True,
    ),
    Action(
        "R",
        "Restart server",
        "systemctl restart fanxi. Use it after editing /etc/fanxi.env or the unit file.",
        "Disconnects everyone for a few seconds and resets in-memory state (monster spawns, "
        "aggro, timers). Character data in the database is untouched.",
        confirm=True,
        danger=True,
    ),
    Action(
        "b",
        "Backup now",
        "Runs scripts/db-backup.sh on the server: SQLite's online backup API, safe while the "
        "server is running. The server keeps the newest 14 copies.",
        "Writes a copy into data/backups on the server. No downtime, no locks held.",
    ),
    Action(
        "p",
        "Pull backup home",
        "Runs the homelab job: takes a fresh backup, copies it here, checks SQLite's integrity, "
        "and keeps the newest seven days.",
        "Copies the database — password hashes and live session tokens included — to this "
        "machine in clear text. Keep ~/backups/fanxi on an encrypted disk.",
        confirm=True,
    ),
    Action(
        "l",
        "Server logs",
        "journalctl -u fanxi, the last 250 lines, with timestamps. Wheel or arrow keys scroll; "
        "q or a click returns.",
        "Read-only.",
    ),
    Action(
        "g",
        "Registration",
        "Toggles whether new accounts can be created from the launcher.",
        "While open, anyone with the server URL can make an account. Close it once your friends "
        "have registered.",
        confirm=True,
    ),
    Action(
        "a",
        "Admin account",
        "Creates an admin, or resets one's password, using the server's create-admin command "
        "over an interactive prompt.",
        "Replaces that account's password immediately. Existing sessions stay valid until they "
        "expire.",
        confirm=True,
    ),
    Action(
        "m",
        "Clone character",
        "Asks who to copy and searches the database for the target by part of its name, then "
        "runs tools/clone_character.py --force --apply on the server. The tool backs up the "
        "database first and prints the plan before it writes.",
        "Replaces the target's jobs, level, sub job, exp, gil, merits, Home Points, inventory, "
        "storage, locker and worn outfit with the source's. Log the target out first: --force "
        "only covers the server's unexpired game session row, which outlives a logout. Relog the "
        "target afterwards. The pre-clone backup is the only undo.",
        confirm=True,
        danger=True,
    ),
    Action(
        "c",
        "Server shell",
        "Opens an interactive bash on the server with your SSH key.",
        "Anything you do there bypasses this dashboard, including the database. The server is a "
        "live host with players on it.",
        confirm=True,
        danger=True,
    ),
    Action(
        "e",
        "Edit settings",
        "Edits ~/.fanxi-manager.json: ssh destination, checkout path, launcher URL, key path, "
        "and where backups land locally.",
        "Only this machine's settings file changes; the server is not touched.",
    ),
    Action(
        "r",
        "Refresh",
        "Re-reads service state, /health and /status right now instead of waiting for the "
        "15-second refresh.",
        "Read-only.",
    ),
    Action(
        "q",
        "Quit",
        "Leaves the dashboard. The server keeps running.",
        "Nothing on the server changes.",
    ),
]


class Dashboard:
    """Status on top, a menu of actions with an explanation beside it, output underneath."""

    def __init__(self, screen, config: dict):
        self.screen = screen
        self.config = config
        self.status: dict = {}
        self.client: dict = {}
        self.fetched_at = 0.0
        self.selected = 0
        self.lines: list[str] = ["ready"]
        self.message = ""
        self.scroll = 0
        self.mouse_ok = False
        self.previous_commit = ""
        self.last_click = (0.0, -1, -1)
        self.menu_rows: list[tuple[int, int, int, int]] = []
        self.building = False
        self.last_progress = 0.0
        self.colors = False
        self._init_colors()

    # -- colour ---------------------------------------------------------------------------

    def _init_colors(self) -> None:
        if not curses.has_colors():
            return
        try:
            curses.start_color()
            try:
                curses.use_default_colors()
                background = -1
            except curses.error:
                background = curses.COLOR_BLACK
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)  # header, selected
            curses.init_pair(2, curses.COLOR_GREEN, background)
            curses.init_pair(3, curses.COLOR_RED, background)
            curses.init_pair(4, curses.COLOR_YELLOW, background)
            curses.init_pair(5, curses.COLOR_CYAN, background)
            curses.init_pair(6, curses.COLOR_WHITE, background)
            curses.init_pair(7, curses.COLOR_MAGENTA, background)
            self.colors = True
        except curses.error:
            self.colors = False

    def pair(self, number: int, attr: int = 0) -> int:
        return (curses.color_pair(number) if self.colors else 0) | attr

    def put(self, y: int, x: int, text: str, attr: int = 0) -> None:
        _, width = self.screen.getmaxyx()
        if y < 0 or y >= self.screen.getmaxyx()[0] or x >= width:
            return
        try:
            self.screen.addnstr(y, x, text, max(0, width - x - 1), attr)
        except curses.error:
            pass

    # -- drawing --------------------------------------------------------------------------

    def draw(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        self.menu_rows = []
        self.draw_header(width)
        self.draw_status(width)
        try:
            self.screen.hline(4, 0, curses.ACS_HLINE, width)
        except curses.error:
            pass

        log_lines = 3 if height >= 22 else 1
        message_y = height - 2
        hint_y = height - 1
        log_bottom = height - 3
        log_top = log_bottom - log_lines + 1
        separator_y = log_top - 1
        menu_top = 6
        menu_bottom = separator_y - 1

        self.draw_menu(menu_top, menu_bottom, width)
        try:
            self.screen.hline(separator_y, 0, curses.ACS_HLINE, width)
        except curses.error:
            pass
        self.draw_output(log_top, log_bottom, width)
        self.put(message_y, 0, self.message, self.pair(4, curses.A_BOLD))
        hint = (
            "building — q cancels · the dashboard is busy until it finishes"
            if self.building
            else "↑↓ choose · Enter run · hotkey runs · click a row · q quits"
        )
        self.put(hint_y, 0, hint, self.pair(5))
        self.screen.refresh()

    def draw_header(self, width: int) -> None:
        attr = self.pair(1, curses.A_BOLD)
        self.put(0, 0, " " * width, attr)
        self.put(0, 1, "Fanxi", attr)
        self.put(0, 8, f"{self.config['host']}   {self.config['url']}", attr)

    def draw_status(self, width: int) -> None:
        status = self.status
        health = status.get("health") or {}
        server = status.get("status") or {}
        service = status.get("service") or "?"
        caddy = status.get("caddy") or "?"
        gateway = bool((server.get("features") or {}).get("game_gateway"))

        def value(y: int, x: int, label: str, text: str, color: int) -> int:
            self.put(y, x, label + " ", self.pair(6, curses.A_DIM))
            self.put(y, x + len(label) + 1, text, self.pair(color, curses.A_BOLD))
            return x + len(label) + len(text) + 4

        x = value(1, 1, "service", service, 2 if service == "active" else 3)
        x = value(1, x, "caddy", caddy, 2 if caddy == "active" else 4)
        x = value(1, x, "version", str(health.get("version") or "?"), 5)
        value(1, x, "commit", str(status.get("commit") or "?"), 5)

        x = value(2, 1, "online", str(server.get("online", "?")), 2)
        x = value(2, x, "accounts", f"{server.get('accounts', '?')} main / {server.get('sub_accounts', '?')} subs", 6)
        x = value(2, x, "characters", str(server.get("characters", "?")), 6)
        value(2, x, "gateway", "on" if gateway else "off", 2 if gateway else 3)

        x = value(3, 1, "db", str(status.get("db") or "?"), 6)
        x = value(3, x, "disk free", str(status.get("disk") or "?"), 6)
        backup = status.get("backup")
        if not backup:
            x = value(3, x, "backup", "none", 3)
        else:
            age = int(status.get("backup_age") or 0)
            x = value(3, x, "backup", human_age(age), 2 if age < 86400 else 4)
        badge, colour = client_badge(self.client)
        value(3, x, "client", badge, colour)

    def draw_menu(self, top: int, bottom: int, width: int) -> None:
        menu_width = min(38, max(26, width // 3))
        rows = max(1, bottom - top)
        self.put(top - 1, 1, "Actions", self.pair(5, curses.A_BOLD))
        self.put(top - 1, menu_width + 2, "What it does", self.pair(5, curses.A_BOLD))

        first = 0
        if self.selected >= rows:
            first = self.selected - rows + 1
        for offset, index in enumerate(range(first, min(len(ACTIONS), first + rows))):
            action = ACTIONS[index]
            selected = index == self.selected
            label = f" [{action.key}] {action.label} "
            if selected:
                attr = self.pair(1, curses.A_BOLD)
            elif action.danger:
                attr = self.pair(3)
            else:
                attr = 0
            self.put(top + offset, 1, label.ljust(menu_width)[:menu_width], attr)
            self.menu_rows.append((index, top + offset, 1, menu_width))
            if selected:
                self.draw_detail(top + offset, menu_width + 2, width, bottom)

    def draw_detail(self, y: int, x: int, width: int, bottom: int) -> None:
        action = ACTIONS[self.selected]
        text_width = max(16, width - x - 2)
        rows: list[tuple[str, int]] = []
        for line in textwrap.wrap(action.desc, text_width):
            rows.append((line, 0))
        if action.risk:
            rows.append(("", 0))
            rows.append(("Risk", self.pair(4, curses.A_BOLD)))
            for line in textwrap.wrap(action.risk, text_width):
                rows.append((line, self.pair(4)))
        rows.append(("", 0))
        rows.append(
            (
                "Asks for confirmation" if action.confirm else "Runs immediately",
                self.pair(6, curses.A_DIM),
            )
        )
        for offset, (text, attr) in enumerate(rows):
            if y + offset > bottom:
                break
            self.put(y + offset, x, text, attr)

    def draw_output(self, top: int, bottom: int, width: int) -> None:
        self.put(top - 1, 1, "Output", self.pair(5, curses.A_BOLD))
        visible = max(1, bottom - top + 1)
        end = max(0, len(self.lines) - self.scroll)
        start = max(0, end - visible)
        for offset, line in enumerate(self.lines[start:end]):
            self.put(top + offset, 1, line, self.pair(6, curses.A_DIM))

    # -- confirmations ------------------------------------------------------------------------

    def confirm(self, action: Action) -> bool:
        """A modal that states the risk and defaults to no."""
        self.draw()
        height, width = self.screen.getmaxyx()
        box_width = min(76, width - 4)
        body = textwrap.wrap(action.risk or action.desc, box_width - 4)
        box_height = min(height - 4, len(body) + 6)
        y0 = max(0, (height - box_height) // 2)
        x0 = max(0, (width - box_width) // 2)
        try:
            window = curses.newwin(box_height, box_width, y0, x0)
        except curses.error:
            return False
        window.erase()
        window.box()
        window.addnstr(0, 2, f" {action.label} ", box_width - 4, self.pair(4, curses.A_BOLD))
        row = 2
        for line in body:
            window.addnstr(row, 2, line, box_width - 4, self.pair(4))
            row += 1
        window.addnstr(
            box_height - 2, 2, "Run it?  [y] yes    [any other key] no", box_width - 4, curses.A_BOLD
        )
        window.refresh()
        self.screen.timeout(-1)
        key = self.screen.getch()
        self.screen.timeout(1000)
        del window
        self.screen.touchwin()  # the window's cells are stale in stdscr now; repaint all
        self.draw()
        return key in (ord("y"), ord("Y"))

    def choose(self, title: str, options: list[str]) -> int | None:
        """A modal list: arrows move, Enter chooses, q cancels."""
        if not options:
            return None
        self.draw()
        height, width = self.screen.getmaxyx()
        box_width = min(82, width - 4)
        visible = min(len(options), max(1, height - 8))
        box_height = visible + 4
        y0 = max(0, (height - box_height) // 2)
        x0 = max(0, (width - box_width) // 2)
        try:
            window = curses.newwin(box_height, box_width, y0, x0)
        except curses.error:
            return None
        selected = 0
        offset = 0
        try:
            while True:
                window.erase()
                window.box()
                window.addnstr(0, 2, f" {title} ", box_width - 4, self.pair(4, curses.A_BOLD))
                for row, index in enumerate(range(offset, offset + visible)):
                    attr = self.pair(1, curses.A_BOLD) if index == selected else 0
                    window.addnstr(1 + row, 2, options[index], box_width - 4, attr)
                first = offset + 1
                last = min(offset + visible, len(options))
                window.addnstr(
                    box_height - 2, 2,
                    f"{first}-{last} of {len(options)} · ↑↓ choose · Enter run · q cancels",
                    box_width - 4, curses.A_BOLD,
                )
                window.refresh()
                self.screen.timeout(-1)
                key = self.screen.getch()
                if key in (curses.KEY_UP, ord("k")):
                    selected = (selected - 1) % len(options)
                elif key in (curses.KEY_DOWN, ord("j")):
                    selected = (selected + 1) % len(options)
                elif key in (10, 13, curses.KEY_ENTER):
                    return selected
                elif key in (ord("q"), 27):
                    return None
                if selected < offset:
                    offset = selected
                elif selected >= offset + visible:
                    offset = selected - visible + 1
        finally:
            self.screen.timeout(1000)
            del window
            self.screen.touchwin()
            self.draw()

    # -- actions ------------------------------------------------------------------------------

    def execute(self, action: Action) -> None:
        handler = {
            "d": self.do_deploy,
            "B": self.do_rebuild,
            "L": self.do_rebuild_launcher,
            "R": self.do_restart,
            "b": self.do_backup,
            "p": self.do_pull,
            "l": self.show_logs,
            "g": self.do_registration,
            "m": self.do_clone,
            "a": self.do_admin,
            "c": self.do_console,
            "e": self.do_edit,
            "r": lambda: self.refresh(force=True),
            "q": None,
        }.get(action.key)
        if handler is None:
            return
        self.message = f"{action.label}…"
        self.draw()
        handler()
        self.refresh(force=True)

    def run_selected(self) -> bool:
        action = ACTIONS[self.selected]
        if action.key == "q":
            return False
        if action.confirm and not self.confirm(action):
            self.message = "cancelled"
            return True
        self.execute(action)
        return True

    def on_hotkey(self, key: int) -> bool:
        for index, action in enumerate(ACTIONS):
            if ord(action.key) == key:
                self.selected = index
                return self.run_selected()
        return True

    def do_deploy(self) -> None:
        self.say("— deploy —")
        ok, previous = deploy(self.config, self.say)
        self.previous_commit = previous or self.previous_commit
        self.say("deploy finished" if ok else "deploy FAILED — see the log (l) for the reason")
        self.message = "deploy ok — server restarted" if ok else "DEPLOY FAILED — old code still running"
        if not ok and self.previous_commit:
            rollback_action = Action(
                "y",
                "Roll back?",
                "Restore the previous commit and restart.",
                f"The service is not healthy. Checking out {self.previous_commit[:12]} and "
                "restarting returns to the code that was running before this deploy. The "
                "database backup taken at the start of the deploy is left in place.",
                confirm=False,
            )
            if self.confirm(rollback_action):
                self.say("— rollback —")
                rollback(self.config, self.previous_commit, self.say)

    def do_rebuild(self) -> None:
        repo = resolve_repo(self.config)
        if repo is None:
            self.say(f"no Fanxi checkout found: set \"repo\" in {CONFIG_PATH} or FANXI_REPO_ROOT")
            self.message = "rebuild cancelled"
            return
        candidates = game_dir_candidates(self.config, repo)
        strong = {"game_dir setting", "the launcher", "generated/build.json"}
        detected = bool(candidates and candidates[0][1] in strong)
        game = None
        if detected:
            game = candidates[0][0]
            self.say(f"game folder {game} ({candidates[0][1]})")
        elif len(candidates) == 1:
            game = candidates[0][0]
            self.say(f"game folder {game} ({candidates[0][1]})")
        elif candidates:
            labels = [f"{path}   ({origin})" for path, origin in candidates]
            choice = self.choose("which FINAL FANTASY XI folder?", labels)
            if choice is None:
                self.message = "cancelled"
                return
            game = candidates[choice][0]
        else:
            typed = self.prompt("FINAL FANTASY XI folder")
            if not typed:
                self.message = "cancelled"
                return
            game = Path(os.path.expanduser(typed)).resolve()
            if not is_game_dir(game):
                self.say(f"{game} is not a FINAL FANTASY XI folder "
                         "(FFXiMain.dll, FFXi.dll and ROM are needed)")
                self.message = "rebuild cancelled"
                return
        remembered = str(self.config.get("game_dir") or "")
        if game is not None and not detected and str(game) != remembered:
            # A folder the launcher or generated/build.json named stays that way; one picked by
            # hand is remembered so the next rebuild does not ask again.
            self.config["game_dir"] = str(game)
            save_config(self.config)

        self.say("— rebuild client —")
        self.building = True
        self.last_progress = 0.0
        self.screen.timeout(0)
        try:
            ok = build_client(self.config, self.build_line, progress=True,
                              should_stop=self.build_cancelled, game=game, repo=repo)
        finally:
            self.building = False
            self.screen.timeout(1000)
        if ok:
            self.say("restart each running client to pick up the new binary")
            self.message = "client rebuilt — restart clients to use it"
        else:
            self.message = "REBUILD FAILED — see the output (and build/tui-build.log)"

    def do_rebuild_launcher(self) -> None:
        repo = resolve_repo(self.config)
        if repo is None:
            self.say(f"no Fanxi checkout found: set \"repo\" in {CONFIG_PATH} or FANXI_REPO_ROOT")
            self.message = "rebuild cancelled"
            return
        state = launcher_state(repo)
        if not state:
            self.say(f"{repo} has no launcher-rs checkout")
            self.message = "rebuild cancelled"
            return
        self.say(f"launcher {launcher_summary(state)}")
        self.say(f"artifact {state['artifact']}")
        self.say("— rebuild launcher —")
        self.message = "rebuilding launcher…"
        self.building = True
        self.last_progress = 0.0
        self.screen.timeout(0)
        try:
            ok = build_launcher(self.config, self.build_line,
                                should_stop=self.build_cancelled, repo=repo)
        finally:
            self.building = False
            self.screen.timeout(1000)
        if ok:
            self.say("quit and reopen the launcher to use the new app")
            self.message = "launcher rebuilt — restart it to use the new app"
        else:
            self.message = "LAUNCHER BUILD FAILED — see the output (and build/tui-launcher.log)"

    def build_line(self, line: str) -> None:
        """One line of the build: progress markers update the message, the rest is output."""
        if line.startswith("@phase "):
            self.message = f"rebuilding client — {line.split(None, 1)[1].strip()}…"
            self.draw()
            return
        if line.startswith("@progress "):
            try:
                done, total = (int(part) for part in line.split()[1:3])
            except ValueError:
                return
            if total:
                percent = done * 100 // total
                self.message = f"rebuilding client — compiling {percent}% ({done}/{total})"
            now = time.time()
            if now - self.last_progress > 0.2:
                self.last_progress = now
                self.draw()
            return
        self.say(line)
        now = time.time()
        if now - self.last_progress > 0.2:
            self.last_progress = now
            self.draw()

    def build_cancelled(self) -> bool:
        """A key pressed while the build streams; q, Esc or Ctrl-C stops it."""
        return self.screen.getch() in (ord("q"), 27, 3)

    def do_restart(self) -> None:
        code, output = run_remote(self.config, "systemctl restart fanxi")
        self.say(f"restart exit {code}")
        if output.strip():
            self.say(output.strip())

    def do_backup(self) -> None:
        if backup_now(self.config, self.say):
            self.message = "backup taken"
        else:
            self.message = "backup failed"

    def do_pull(self) -> None:
        if pull_backup(self.config, self.say):
            self.message = "backup pulled home"
        else:
            self.message = "pull failed"

    def do_registration(self) -> None:
        if toggle_registration(self.config, self.say):
            self.message = "registration toggled"
        else:
            self.message = "registration toggle failed"

    def do_clone(self) -> None:
        source = self.prompt("source character", "Onedough")
        if not source:
            self.message = "cancelled"
            return
        query = self.prompt("target search (part of the name)")
        if not query:
            self.message = "cancelled"
            return

        found = search_characters(self.config, query)
        if not found.get("ok"):
            self.say("character search failed: " + found.get("error", "?"))
            self.message = "clone cancelled"
            return
        matches = found.get("characters") or []
        if not matches:
            self.say(f"no character name matches {query!r}")
            self.message = "clone cancelled"
            return
        if found.get("truncated"):
            self.say("showing the first 25 matches; a longer search narrows the list")

        if len(matches) == 1:
            target = matches[0]
        else:
            labels = [
                "%s — level %s  (id %s, account %s)%s" % (
                    row.get("name", "?"),
                    row.get("main_level", "?"),
                    row.get("id", "?"),
                    row.get("account_id", "?"),
                    "  [unexpired game session]" if row.get("session") else "",
                )
                for row in matches
            ]
            choice = self.choose(f"copy {source} onto which character?", labels)
            if choice is None:
                self.message = "cancelled"
                return
            target = matches[choice]

        target_name = str(target.get("name") or "")
        if not target_name:
            self.say("the search result had no name; nothing cloned")
            self.message = "clone cancelled"
            return
        if target_name.casefold() == source.casefold():
            self.say("source and target are the same character; nothing cloned")
            self.message = "clone cancelled"
            return

        session = ""
        if target.get("session"):
            session = (" That character has an unexpired game session row; make sure its "
                       "client is logged out.")
        confirmation = Action(
            "y",
            f"Clone {source} onto {target_name}?",
            "Runs tools/clone_character.py --force --apply on the server.",
            f"Replaces {target_name}'s jobs, level, sub job, exp, gil, merits, Home Points, "
            f"inventory, storage, locker and worn outfit with {source}'s. The tool backs up the "
            f"database first; relog {target_name} afterwards.{session}",
            confirm=False,
            danger=True,
        )
        if not self.confirm(confirmation):
            self.message = "cancelled"
            return

        self.say(f"cloning {source} → {target_name}…")
        self.draw()
        code, output = run_remote(
            self.config, clone_command(self.config, source, target_name), timeout=300
        )
        for line in output.strip().splitlines():
            self.say("  " + line)
        if code == 0:
            self.say(f"clone finished — relog {target_name}. If its client was at character "
                     "select, relaunch that client or restart the server.")
            self.message = f"clone ok — relog {target_name}"
        else:
            self.say("clone failed — see the log; the tool backs up before it writes")
            self.message = "CLONE FAILED — see the log"

    def do_admin(self) -> None:
        username = self.prompt("admin username")
        if not username:
            self.message = "cancelled"
            return
        curses.endwin()
        remote = shlex.quote(self.config["remote_dir"])
        try:
            subprocess.call(
                ssh_command(self.config, tty=True)
                + [
                    f"cd {remote}/server && sudo -u fanxi -H python3 -m fanxi_server "
                    f"create-admin {shlex.quote(username)}"
                ]
            )
        finally:
            curses.doupdate()
            self.screen.touchwin()
        self.say(f"admin {username} updated")

    def do_console(self) -> None:
        curses.endwin()
        try:
            subprocess.call(ssh_command(self.config, tty=True) + ["bash -l"])
        finally:
            curses.doupdate()
            self.screen.touchwin()

    def do_edit(self) -> None:
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
        curses.endwin()
        try:
            subprocess.call([editor, str(CONFIG_PATH)])
        finally:
            self.config = load_config()
            curses.doupdate()

    def prompt(self, label: str, default: str = "") -> str:
        height, width = self.screen.getmaxyx()
        curses.echo()
        curses.curs_set(1)
        self.put(height - 1, 0, " " * (width - 1), 0)
        self.put(height - 1, 0, f"{label}: ", self.pair(5, curses.A_BOLD))
        self.screen.refresh()
        prefix = len(label) + 2
        self.screen.timeout(-1)
        try:
            raw = self.screen.getstr(height - 1, prefix, max(1, width - prefix - 1))
        except curses.error:
            raw = b""
        self.screen.timeout(1000)
        curses.noecho()
        curses.curs_set(0)
        value = raw.decode("utf-8", "replace").strip()
        return value or default

    def show_logs(self) -> None:
        output = tail_logs(self.config)
        self.lines = output.splitlines()[-400:] or ["(no log lines)"]
        self.scroll = 0
        wheel_up = getattr(curses, "BUTTON4_PRESSED", 0) | getattr(curses, "BUTTON4_CLICKED", 0)
        wheel_down = getattr(curses, "BUTTON5_PRESSED", 0) | getattr(curses, "BUTTON5_CLICKED", 0)
        while True:
            self.draw_logs()
            key = self.screen.getch()
            if key == -1:
                continue
            if key in (ord("q"), 27):
                self.scroll = 0
                return
            if key == curses.KEY_MOUSE and self.mouse_ok:
                try:
                    _, _, _, _, state = curses.getmouse()
                except curses.error:
                    continue
                if state & wheel_up:
                    self.scroll = min(len(self.lines), self.scroll + 3)
                elif state & wheel_down:
                    self.scroll = max(0, self.scroll - 3)
                else:
                    self.scroll = 0
                    return
                continue
            if key in (curses.KEY_UP, ord("k")):
                self.scroll = min(len(self.lines), self.scroll + 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                self.scroll = max(0, self.scroll - 1)
            elif key == curses.KEY_PPAGE:
                self.scroll = min(len(self.lines), self.scroll + 10)
            elif key == curses.KEY_NPAGE:
                self.scroll = max(0, self.scroll - 10)

    def draw_logs(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        self.put(0, 0, " " * width, self.pair(1, curses.A_BOLD))
        self.put(0, 1, "Server log — journalctl -u fanxi", self.pair(1, curses.A_BOLD))
        visible = max(1, height - 2)
        end = max(0, len(self.lines) - self.scroll)
        start = max(0, end - visible)
        for offset, line in enumerate(self.lines[start:end]):
            self.put(1 + offset, 1, line, self.pair(6, curses.A_DIM))
        self.put(height - 1, 0, "wheel or ↑↓ scroll · q or a click returns", self.pair(5))
        self.screen.refresh()

    # -- data ---------------------------------------------------------------------------------

    def refresh(self, force: bool = False) -> None:
        if not force and time.time() - self.fetched_at < 15:
            return
        self.message = "reading status…"
        self.draw()
        self.status = collect_status(self.config)
        self.client = local_client(self.config)
        self.fetched_at = time.time()
        if self.status.get("error"):
            self.message = "status failed — is ssh working?"
            self.lines.extend(self.status["error"].splitlines()[:3])
            self.lines = self.lines[-400:]
        else:
            self.message = ""

    def say(self, text: str) -> None:
        for line in str(text).splitlines() or [""]:
            self.lines.append(line)
        self.lines = self.lines[-400:]

    # -- input --------------------------------------------------------------------------------

    def on_mouse(self) -> bool:
        try:
            _, x, y, _, state = curses.getmouse()
        except curses.error:
            return True
        wheel_up = getattr(curses, "BUTTON4_PRESSED", 0) | getattr(curses, "BUTTON4_CLICKED", 0)
        wheel_down = getattr(curses, "BUTTON5_PRESSED", 0) | getattr(curses, "BUTTON5_CLICKED", 0)
        if state & wheel_up:
            self.selected = max(0, self.selected - 1)
            return True
        if state & wheel_down:
            self.selected = min(len(ACTIONS) - 1, self.selected + 1)
            return True
        click = (
            getattr(curses, "BUTTON1_CLICKED", 0)
            | getattr(curses, "BUTTON1_PRESSED", 0)
            | getattr(curses, "BUTTON1_RELEASED", 0)
        )
        if state & click:
            now = time.time()
            when, last_x, last_y = self.last_click
            if now - when < 0.25 and (x, y) == (last_x, last_y):
                return True
            self.last_click = (now, x, y)
            for index, row_y, row_x, row_width in self.menu_rows:
                if y == row_y and row_x <= x < row_x + row_width:
                    self.selected = index
                    return self.run_selected()
        return True

    def run(self) -> None:
        curses.curs_set(0)
        self.screen.timeout(1000)
        try:
            mask, _ = curses.mousemask(curses.ALL_MOUSE_EVENTS)
            self.mouse_ok = bool(mask)
        except curses.error:
            self.mouse_ok = False
        if not self.mouse_ok:
            self.say("this terminal does not report mouse events; use the keys")
        self.refresh(force=True)
        while True:
            self.draw()
            key = self.screen.getch()
            if key == -1:
                self.refresh()
                continue
            if key == curses.KEY_MOUSE:
                if not self.on_mouse():
                    return
                continue
            if key in (curses.KEY_UP, ord("k")):
                self.selected = (self.selected - 1) % len(ACTIONS)
                continue
            if key in (curses.KEY_DOWN, ord("j")):
                self.selected = (self.selected + 1) % len(ACTIONS)
                continue
            if key in (10, 13, curses.KEY_ENTER):
                if not self.run_selected():
                    return
                continue
            if not self.on_hotkey(key):
                return

def setup(config: dict) -> dict:
    """First-run connection settings, asked once and saved mode-0600."""
    print("No settings yet — a few questions, saved to %s\n" % CONFIG_PATH)
    host = input(f"ssh destination [{config['host']}]: ").strip() or config["host"]
    remote = input(f"checkout on the server [{config['remote_dir']}]: ").strip() or config["remote_dir"]
    url = input(f"launcher URL [{config['url']}]: ").strip() or config["url"]
    key = input(f"ssh key [{config['key']}]: ").strip() or config["key"]
    config.update(host=host, remote_dir=remote, url=url, key=key)
    save_config(config)
    print(f"saved {CONFIG_PATH}\n")
    return config


def report(config: dict) -> int:
    status = collect_status(config)
    if status.get("error"):
        print("error: " + status["error"])
        return 1
    health = status.get("health") or {}
    server = status.get("status") or {}
    print(f"host       {config['host']}  {config['url']}")
    print(f"service    {status.get('service')}   caddy {status.get('caddy')}")
    print(f"version    {health.get('version', '?')}   commit {status.get('commit')} ({status.get('branch')})")
    print(
        f"players    online {server.get('online')}  main {server.get('accounts')}"
        f"  subs {server.get('sub_accounts')}  characters {server.get('characters')}"
    )
    print(f"storage    db {status.get('db')}  disk free {status.get('disk')}")
    if status.get("backup"):
        print(f"backup     {status['backup']} ({human_age(status.get('backup_age'))})")
    else:
        print("backup     none")
    client = local_client(config)
    path = f"  {client['path']}" if client.get("path") else ""
    print(f"client     {client_summary(client)}{path}")
    launcher = launcher_state(resolve_repo(config))
    artifact = f"  {launcher['artifact']}" if launcher.get("artifact") else ""
    print(f"launcher   {launcher_summary(launcher)}{artifact}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fanxi server dashboard over SSH")
    parser.add_argument("--status", action="store_true", help="print a report and exit")
    parser.add_argument("--deploy", action="store_true",
                        help="backup, pull, restart (applies migrations), verify")
    parser.add_argument("--rebuild", action="store_true",
                        help="rebuild the local client (build/fanxi), no curses")
    parser.add_argument("--rebuild-launcher", action="store_true",
                        help="rebuild the Rust + Tauri launcher in launcher-rs, no curses")
    parser.add_argument("--game", help="the FINAL FANTASY XI folder for --rebuild")
    parser.add_argument("--repo", help="the Fanxi checkout to build for --rebuild / --rebuild-launcher")
    parser.add_argument("--setup", action="store_true", help="write ~/.fanxi-manager.json")
    parser.add_argument("--config", help="path to the settings file")
    args = parser.parse_args(argv)

    if args.config:
        global CONFIG_PATH
        CONFIG_PATH = Path(args.config).expanduser()

    config = load_config()
    interactive = not (args.status or args.deploy or args.rebuild or args.rebuild_launcher)
    if args.setup or (interactive and not CONFIG_PATH.is_file()):
        config = setup(config)
    elif not CONFIG_PATH.is_file():
        print(f"no {CONFIG_PATH}: using defaults (run --setup to change)", file=sys.stderr)
    if args.game:
        config["game_dir"] = args.game
    if args.repo:
        config["repo"] = args.repo
    if args.status:
        return report(config)
    if args.deploy:
        ok, previous = deploy(config, print)
        return 0 if ok else 1
    if args.rebuild:
        return 0 if build_client(config, lambda line: print(line, flush=True)) else 1
    if args.rebuild_launcher:
        return 0 if build_launcher(config, lambda line: print(line, flush=True)) else 1
    try:
        curses.wrapper(lambda screen: Dashboard(screen, config).run())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
