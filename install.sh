#!/bin/bash
# Install the Fanxi launcher, and optionally this machine's own Fanxi server.
#
#   curl -fsSL https://raw.githubusercontent.com/wondollaballa/fanxi/main/install.sh | bash
#
# Fanxi is self-hosted: the launcher signs in to a Fanxi server you run (or one you trust). With
# no arguments this installs the launcher, creates data/fanxi.db and starter content, and prints
# the one command that starts the server. Run it again to update a source install.
#
# The launcher is a Rust + Tauri app; building it needs Node 18+ and Rust 1.85+ (on Linux also
# the WebKitGTK/Tauri packages). The server is Python 3.9+ only, so --server-only needs no
# JavaScript or Rust toolchain.

set -euo pipefail

usage() {
    cat <<'USAGE'
Install the Fanxi launcher and, optionally, this machine's own Fanxi server.

  install.sh                  launcher + server (default)
  install.sh --launcher-only  install just the launcher
  install.sh --server-only    install just the server (no .app / .desktop entry)

Environment:
  FANXI_SOURCE   checkout to install from (default: this checkout, else a clone)
  FANXI_REPO     git URL used when FANXI_SOURCE is not a checkout
  FANXI_HOME     where a downloaded checkout goes
  FANXI_APPS     macOS folder for Fanxi Launcher.app (default: ~/Applications, else /Applications)
  FANXI_OPEN=1   open the launcher when it is installed (the server is not started by this script)

On macOS the launcher becomes ~/Applications/Fanxi Launcher.app (or /Applications when writable).
On Linux it gets a desktop entry and a ~/.local/bin/fanxi-server helper. Either way the installer
records the checkout in launcher.json so the app can find tools/build_posix.py.
USAGE
}

LAUNCHER=1
SERVER=1
for arg in "$@"; do
    case "$arg" in
        --launcher-only) SERVER=0 ;;
        --server-only) LAUNCHER=0 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

case "$(uname -s)" in
    Darwin) PLATFORM=mac ;;
    Linux) PLATFORM=linux ;;
    *) die "Fanxi installs on macOS and Linux (found $(uname -s))" ;;
esac

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || die "python3 is required"

# --- where the sources are --------------------------------------------------------------------
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)"
if [ -n "${FANXI_SOURCE:-}" ]; then
    SRC="$FANXI_SOURCE"
elif [ -n "$HERE" ] && [ -f "$HERE/launcher-rs/src-tauri/Cargo.toml" ] && [ -f "$HERE/server/fanxi_server/__init__.py" ]; then
    SRC="$HERE"
else
    : "${FANXI_HOME:=}"
    if [ -z "$FANXI_HOME" ]; then
        if [ "$PLATFORM" = mac ]; then
            FANXI_HOME="$HOME/Library/Application Support/Fanxi"
        else
            FANXI_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/fanxi"
        fi
    fi
    SRC="$FANXI_HOME/source"
    REPO="${FANXI_REPO:-https://github.com/wondollaballa/fanxi.git}"
    if [ -d "$SRC/.git" ]; then
        say "Updating Fanxi in $SRC"
        git -C "$SRC" fetch --depth 1 origin main
        git -C "$SRC" checkout -q -B main FETCH_HEAD
    else
        say "Downloading Fanxi into $SRC"
        mkdir -p "$(dirname "$SRC")"
        git clone --depth 1 --branch main "$REPO" "$SRC"
    fi
fi

[ -f "$SRC/server/fanxi_server/__init__.py" ] || die "$SRC is not a Fanxi checkout"
if [ "$LAUNCHER" = 1 ]; then
    [ -f "$SRC/launcher-rs/src-tauri/Cargo.toml" ] || die "$SRC does not contain launcher-rs"
fi

# --- checks -----------------------------------------------------------------------------------
"$PYTHON" - <<'PY' || die "Python 3.9 or newer is required"
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
if [ "$LAUNCHER" = 1 ]; then
    command -v node >/dev/null 2>&1 || die "Node 18 or newer is required to build the launcher (install Node, or run with --server-only)"
    command -v npm >/dev/null 2>&1 || die "npm is required to build the launcher"
    command -v cargo >/dev/null 2>&1 || die "Rust 1.85 or newer is required to build the launcher (install Rust, or run with --server-only)"
    node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 18 ? 0 : 1)' \
        || die "Node 18 or newer is required to build the launcher"
fi

# --- server -----------------------------------------------------------------------------------
if [ "$SERVER" = 1 ]; then
    say "Preparing the Fanxi database in $SRC/data/fanxi.db"
    (cd "$SRC/server" && "$PYTHON" -m fanxi_server init)
fi

# --- launcher ---------------------------------------------------------------------------------
record_repo_root() {
    "$PYTHON" - "$SRC" "$PLATFORM" <<'PY'
import json
import os
import sys
import tempfile

src, platform = sys.argv[1], sys.argv[2]
if platform == "mac":
    data = os.path.expanduser("~/Library/Application Support/Fanxi")
else:
    data = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "fanxi")
path = os.path.join(data, "launcher.json")
os.makedirs(data, mode=0o700, exist_ok=True)
config = {}
if os.path.exists(path):
    try:
        with open(path, encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, ValueError):
        try:
            os.replace(path, path + ".bad")
        except OSError:
            pass
        config = {}
if not str(config.get("repo_root") or "").strip():
    config["repo_root"] = src
    fd, temp = tempfile.mkstemp(dir=data)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")
    os.chmod(temp, 0o600)
    os.replace(temp, path)
    print("Recorded the checkout in %s" % path)
PY
}

if [ "$LAUNCHER" = 1 ]; then
    say "Building the Fanxi Launcher (the first build compiles Rust and takes several minutes)"
    if [ "$PLATFORM" = mac ]; then
        (cd "$SRC/launcher-rs" && npm ci && npm run tauri build -- --bundles app)
    else
        (cd "$SRC/launcher-rs" && npm ci && npm run tauri build -- --no-bundle)
    fi
    if [ "$PLATFORM" = mac ]; then
        APP="$SRC/launcher-rs/src-tauri/target/release/bundle/macos/Fanxi Launcher.app"
        [ -d "$APP" ] || die "the launcher bundle was not produced at $APP"
        DEST="${FANXI_APPS:-$HOME/Applications}"
        if [ -z "${FANXI_APPS:-}" ] && [ -w /Applications ]; then
            DEST=/Applications
        fi
        mkdir -p "$DEST"
        rm -rf "$DEST/Fanxi Launcher.app"
        ditto "$APP" "$DEST/Fanxi Launcher.app"
        say "Installed $DEST/Fanxi Launcher.app"
        record_repo_root
        if [ "${FANXI_OPEN:-0}" = 1 ]; then
            open "$DEST/Fanxi Launcher.app" 2>/dev/null || true
        fi
    else
        BIN="$SRC/launcher-rs/src-tauri/target/release/fanxi-launcher"
        [ -x "$BIN" ] || die "the launcher binary was not produced at $BIN"
        DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
        mkdir -p "$DATA/applications" "$DATA/icons" "$HOME/.local/bin"
        cp "$SRC/assets/icon.png" "$DATA/icons/fanxi-launcher.png"
        cat > "$DATA/applications/fanxi-launcher.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Fanxi Launcher
Comment=Sign in and play FINAL FANTASY XI on Fanxi
Exec="$BIN"
Path=$SRC
Icon=$DATA/icons/fanxi-launcher.png
Terminal=false
Categories=Game;
StartupWMClass=fanxi-launcher
DESKTOP
        chmod +x "$DATA/applications/fanxi-launcher.desktop"
        cat > "$HOME/.local/bin/fanxi-server" <<SH
#!/bin/sh
cd "$SRC/server" && exec "$PYTHON" -m fanxi_server "\$@"
SH
        chmod +x "$HOME/.local/bin/fanxi-server"
        record_repo_root
        say "Installed the desktop entry and ~/.local/bin/fanxi-server"
    fi
fi

say ""
say "Fanxi is installed."
if [ "$SERVER" = 1 ]; then
    say "  1. Start the server:  cd \"$SRC/server\" && $PYTHON -m fanxi_server run"
    say "     (or use scripts/server.sh)"
    say "  2. Make an admin:      cd \"$SRC/server\" && $PYTHON -m fanxi_server create-admin"
    say "  3. Open the launcher and create a player account."
    say "  The default server address is http://127.0.0.1:8080."
else
    say "  Open the launcher and point it at your Fanxi server in Settings."
fi
