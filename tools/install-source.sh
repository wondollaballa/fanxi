#!/bin/bash
# Install Fanxi from source. This is a thin forwarding script: the launcher and the server are
# installed by install.sh, whether it is run from a checkout or downloaded with curl.
#
#   curl -fsSL https://raw.githubusercontent.com/wondochoung/fanxi/main/tools/install-source.sh | bash
#
# Options go to install.sh (--launcher-only, --server-only).
set -euo pipefail

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)"
if [ -n "$HERE" ] && [ -f "$HERE/../install.sh" ]; then
    exec bash "$HERE/../install.sh" "$@"
fi

REPO="${FANXI_REPO:-https://github.com/wondochoung/fanxi.git}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 --branch main "$REPO" "$TMP/fanxi"
bash "$TMP/fanxi/install.sh" "$@"
