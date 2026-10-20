#!/bin/sh
# Copy the SQLite database (with WAL) to a timestamped file. Safe while the server runs.
set -e
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DB=${FANXI_DB:-$ROOT/data/fanxi.db}
OUT=${1:-$ROOT/data/backups}
mkdir -p "$OUT"
STAMP=$(date +%Y%m%d-%H%M%S)
python3 - "$DB" "$OUT/fanxi-$STAMP.db" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
with sqlite3.connect(src) as a, sqlite3.connect(dst) as b:
    a.backup(b)
print(dst)
PY
