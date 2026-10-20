#!/bin/bash
# Fanxi on this Mac: double-click this file in Finder, or run ./setup.command.
#
# It starts this checkout's Fanxi server if one is not already answering on the launcher's
# address, then opens the launcher. The launcher builds host64 from your own FINAL FANTASY XI
# folder the first time you press Play.
#
# Nothing to install: macOS's Command Line Tools provide python3 and tkinter, and the build brings
# its own SDL, mbedTLS and LuaJIT. If the tools are missing, this asks macOS to install them.
cd "$(dirname "$0")" || exit 1

if ! xcode-select -p >/dev/null 2>&1 || ! xcrun --find clang >/dev/null 2>&1; then
    echo "Fanxi needs Xcode's command line tools (free, from Apple)."
    echo "A dialog opens: click Install, and setup carries on when they are in."
    xcode-select --install >/dev/null 2>&1
    until xcode-select -p >/dev/null 2>&1 && xcrun --find clang >/dev/null 2>&1; do
        sleep 5
    done
    echo "Command line tools installed."
fi

PYTHON="${PYTHON:-/usr/bin/python3}"
[ -x "$PYTHON" ] || PYTHON=python3

health() {
    "$PYTHON" - "$1" <<'PY' >/dev/null 2>&1
import json, sys, urllib.request
url = sys.argv[1].rstrip('/') + '/api/v1/health'
with urllib.request.urlopen(url, timeout=2) as response:
    json.load(response)
PY
}

API="${FANXI_API_URL:-http://127.0.0.1:8080}"
SERVER_PID=""
if health "$API"; then
    echo "Fanxi server is already running at $API"
else
    echo "Starting the Fanxi server at $API"
    (cd server && "$PYTHON" -m fanxi_server init >/dev/null && exec "$PYTHON" -m fanxi_server run) &
    SERVER_PID=$!
    for _ in $(seq 40); do
        health "$API" && break
        sleep 0.5
    done
    if ! health "$API"; then
        echo "The server did not come up. Run scripts/server.sh to see why." >&2
    fi
fi

cleanup() {
    if [ -n "$SERVER_PID" ]; then
        kill "$SERVER_PID" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT INT TERM

./launcher/fanxi-launcher
status=$?
if [ -t 0 ] && [ -z "$FANXI_SETUP_NO_WAIT" ]; then
    echo
    read -r -p "Press Return to close this window." _
fi
exit $status
