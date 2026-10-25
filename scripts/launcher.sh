#!/bin/sh
# Start the Fanxi Launcher from this checkout.
#
# A built release binary is used when there is one; otherwise the Tauri app runs in development
# mode (Vite + cargo), which is what a fresh checkout has.
set -e
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BIN="$ROOT/launcher-rs/src-tauri/target/release/fanxi-launcher"

if [ -x "$BIN" ]; then
    exec "$BIN"
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "The launcher is not built, and npm is not installed." >&2
    echo "Install Node 18+ and Rust 1.85+, then run:" >&2
    echo "  cd \"$ROOT/launcher-rs\" && npm ci && npm run tauri dev" >&2
    exit 1
fi

cd "$ROOT/launcher-rs"
if [ ! -d node_modules ]; then
    echo "Installing the launcher's packages (first run)..."
    npm ci
fi
exec npm run tauri dev
