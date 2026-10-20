#!/bin/sh
# Local development: one terminal, the server and the launcher.
set -e
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT/server"
"${PYTHON:-python3}" -m fanxi_server init >/dev/null
"${PYTHON:-python3}" -m fanxi_server run "$@" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT INT TERM
sleep 1
"$ROOT/launcher/fanxi-launcher"
