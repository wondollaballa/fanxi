#!/bin/sh
# Pull a fresh Fanxi database backup from the server to this machine (the homelab).
#
#   scripts/pull-offsite-backup.sh
#
# FANXI_SSH          ssh destination for the server, e.g. root@203.0.113.10   (required)
# FANXI_REMOTE_DIR   the Fanxi checkout on the server          (default /srv/fanxi)
# FANXI_BACKUP_DIR   where the copies land here                (default ~/backups/fanxi)
# FANXI_KEEP_DAYS    copies older than this many days are deleted (default 7; a daily job
#                    therefore keeps today plus the previous seven)
#
# Pull, don't push: the homelab already reaches the internet, so the server needs no route
# back and the homelab needs no open port. Run it daily from cron or a systemd timer.
#
# Every failure is loud and stops before anything is deleted: a night that copies nothing
# must not also prune the last good backup. Non-zero exit means "do not trust tonight".
set -eu

SSH=${FANXI_SSH:?set FANXI_SSH, e.g. FANXI_SSH=root@203.0.113.10}
REMOTE_DIR=${FANXI_REMOTE_DIR:-/srv/fanxi}
LOCAL_DIR=${FANXI_BACKUP_DIR:-$HOME/backups/fanxi}
KEEP_DAYS=${FANXI_KEEP_DAYS:-7}

command -v rsync >/dev/null 2>&1 || { echo "rsync is required" >&2; exit 2; }
mkdir -p "$LOCAL_DIR"

# 1. Ask the server for a snapshot. Its own script uses SQLite's online backup API, so this
#    is safe while the server runs -- no copying a live -wal file behind SQLite's back.
ssh "$SSH" "cd '$REMOTE_DIR' && ./scripts/db-backup.sh >/dev/null"

# 2. Copy only the database files (not the server's whole backups folder).
rsync -az --prune-empty-dirs \
    --include='fanxi-*.db' --exclude='*' \
    "$SSH:$REMOTE_DIR/data/backups/" "$LOCAL_DIR/"

# 3. Verify the copy that just arrived, on this disk. A backup that cannot be opened is not
#    a backup, and this is the cheapest moment to find out.
latest=$(ls -1t "$LOCAL_DIR"/fanxi-*.db 2>/dev/null | head -n 1 || true)
[ -n "$latest" ] || { echo "no backup arrived in $LOCAL_DIR" >&2; exit 1; }
python3 - "$latest" <<'PY'
import sqlite3
import sys

path = sys.argv[1]
with sqlite3.connect(path) as db:
    result = db.execute("PRAGMA integrity_check").fetchone()[0]
    tables = db.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
if result != "ok":
    raise SystemExit(f"{path}: integrity check failed: {result}")
if tables < 10:
    raise SystemExit(f"{path}: only {tables} tables, this does not look like fanxi.db")
print(f"{path}: ok ({tables} tables)")
PY

# 4. Keep FANXI_KEEP_DAYS of copies. Run the job daily; hourly runs keep 24x more files.
find "$LOCAL_DIR" -name 'fanxi-*.db' -type f -mtime +"$KEEP_DAYS" -print -delete
