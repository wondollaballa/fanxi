#!/bin/sh
# Create data/fanxi.db, starter news and an administrator account.
set -e
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT/server"
"${PYTHON:-python3}" -m fanxi_server init
"${PYTHON:-python3}" -m fanxi_server create-admin "$@"
