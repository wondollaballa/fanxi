#!/bin/sh
# Copy the SQLite database (with WAL) to a timestamped file. Safe while the server runs.
#
#   scripts/db-backup.sh [output folder]
#
# FANXI_DB            the database (default: <repo>/data/fanxi.db)
# FANXI_BACKUP_KEEP   how many backups to keep (default 14; 0 keeps all)
#
# The retention matters more than the copy: an unattended daily backup of a 16 MB database is
# 6 GB a year, and the database itself grows by kilobytes per character, not megabytes.
set -e
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DB=${FANXI_DB:-$ROOT/data/fanxi.db}
case "$DB" in /*) ;; *) DB="$ROOT/$DB" ;; esac
OUT=${1:-$ROOT/data/backups}
KEEP=${FANXI_BACKUP_KEEP:-14}
case "$KEEP" in
    ''|*[!0-9]*) echo "FANXI_BACKUP_KEEP must be a number, not '$KEEP'" >&2; exit 2 ;;
esac
mkdir -p "$OUT"
STAMP=$(date +%Y%m%d-%H%M%S)
python3 - "$DB" "$OUT/fanxi-$STAMP.db" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
with sqlite3.connect(src) as a, sqlite3.connect(dst) as b:
    a.backup(b)
print(dst)
PY
# Newest first, so everything after the first $KEEP is the oldest and goes.
if [ "$KEEP" -gt 0 ]; then
    ls -1t "$OUT"/fanxi-*.db 2>/dev/null \
        | sed -n "$((KEEP + 1)),\$p" \
        | while IFS= read -r old; do
            rm -f "$old"
            echo "pruned $old"
        done
fi
