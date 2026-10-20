#!/bin/bash
# Install the Fanxi launcher, and optionally this machine's own Fanxi server.
#
#   curl -fsSL https://raw.githubusercontent.com/wondochoung/fanxi/main/install.sh | bash
#
# Fanxi is self-hosted: the launcher signs in to a Fanxi server you run (or one you trust). With
# no arguments this installs the launcher, creates data/fanxi.db and starter content, and prints
# the one command that starts the server. Run it again to update a source install.
#
#   --launcher-only   install just the launcher
#   --server-only     install just the server (no .app / .desktop entry)
#
# Environment:
#   FANXI_SOURCE      checkout to install from (default: this checkout, else a clone)
#   FANXI_REPO        git URL used when FANXI_SOURCE is not a checkout
#   FANXI_HOME        where a downloaded checkout goes
#   FANXI_OPEN=1      open the launcher when it is installed (the server is not started by this script)
#
# On macOS the launcher becomes ~/Applications/Fanxi Launcher.app (or /Applications when writable).
# On Linux it gets a desktop entry and a ~/.local/bin/fanxi-server helper. Python 3.9+ with
# tkinter is required; macOS's Command Line Tools include both.

set -euo pipefail

LAUNCHER=1
SERVER=1
for arg in "$@"; do
    case "$arg" in
        --launcher-only) SERVER=0 ;;
        --server-only) LAUNCHER=0 ;;
        -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
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
elif [ -n "$HERE" ] && [ -f "$HERE/launcher/build_app.py" ] && [ -f "$HERE/server/fanxi_server/__init__.py" ]; then
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
    REPO="${FANXI_REPO:-https://github.com/wondochoung/fanxi.git}"
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

# --- checks -----------------------------------------------------------------------------------
"$PYTHON" - <<'PY' || die "Python 3.9 or newer is required"
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
if [ "$LAUNCHER" = 1 ]; then
    "$PYTHON" - <<'PY' || die "tkinter is missing. On macOS install the Command Line Tools (xcode-select --install); on Linux install python3-tk."
import tkinter
PY
fi

# --- server -----------------------------------------------------------------------------------
if [ "$SERVER" = 1 ]; then
    say "Preparing the Fanxi database in $SRC/data/fanxi.db"
    (cd "$SRC/server" && "$PYTHON" -m fanxi_server init)
fi

# --- launcher ---------------------------------------------------------------------------------
if [ "$LAUNCHER" = 1 ]; then
    say "Building the launcher"
    (cd "$SRC" && "$PYTHON" launcher/build_app.py)
    if [ "$PLATFORM" = mac ]; then
        APP="$SRC/build/Fanxi Launcher.app"
        DEST="${FANXI_APPS:-$HOME/Applications}"
        if [ -z "${FANXI_APPS:-}" ] && [ -w /Applications ]; then
            DEST=/Applications
        fi
        mkdir -p "$DEST"
        rm -rf "$DEST/Fanxi Launcher.app"
        ditto "$APP" "$DEST/Fanxi Launcher.app"
        say "Installed $DEST/Fanxi Launcher.app"
        if [ "${FANXI_OPEN:-0}" = 1 ]; then
            open "$DEST/Fanxi Launcher.app" 2>/dev/null || true
        fi
    else
        DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
        mkdir -p "$DATA/applications" "$DATA/icons" "$HOME/.local/bin"
        cp "$SRC/assets/icon.png" "$DATA/icons/fanxi-launcher.png"
        cat > "$DATA/applications/fanxi-launcher.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Fanxi Launcher
Comment=Sign in and play FINAL FANTASY XI on Fanxi
Exec=$SRC/launcher/fanxi-launcher
Icon=$DATA/icons/fanxi-launcher.png
Terminal=false
Categories=Game;
StartupWMClass=fanxi
DESKTOP
        chmod +x "$DATA/applications/fanxi-launcher.desktop"
        cat > "$HOME/.local/bin/fanxi-server" <<SH
#!/bin/sh
cd "$SRC/server" && exec "$PYTHON" -m fanxi_server "\$@"
SH
        chmod +x "$HOME/.local/bin/fanxi-server"
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
