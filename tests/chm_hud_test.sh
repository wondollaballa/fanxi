#!/bin/sh
# Regression test for the Chemist HUD's Lua (host/addons/lua/chm.lua): runs
# tests/addons/chmtest in the addon harness with a mock ImGui API.  It checks the
# server snapshot is accepted and summarised, that a Chemist main is active and a
# Red Mage is not, and that the ability buttons send the //chm commands the server
# route understands.  It needs the game image for the harness, not a running client.
#
#   tests/chm_hud_test.sh --game <FFXI folder>
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(dirname "$here")
game=""
while [ $# -gt 0 ]; do
    case "$1" in
        --game) game="$2"; shift 2 ;;
        *) echo "usage: $0 --game <FFXI folder>"; exit 2 ;;
    esac
done
[ -n "$game" ] || { echo "usage: $0 --game <FFXI folder>"; exit 2; }

data=$(mktemp -d "${TMPDIR:-/tmp}/chmtest.XXXXXX")
trap 'rm -rf "$data"' EXIT
mkdir -p "$data/xi/addons"
cp -R "$here/addons/chmtest" "$data/xi/addons/"

cat > "$data/script.txt" <<'TXT'
frames 2
load chmtest xi
frames 6
TXT
FFXI_ADDONS_LUA="$root/host/addons/lua" "$root/build/fanxi" --game "$game" --data-dir "$data" \
    --addon-harness "$data/script.txt" > "$data/out.txt" 2>&1 || true
grep -E '^\[chat 1\] (install|ok|FAIL|failures=)' "$data/out.txt" \
    | sed 's/^\[chat 1\] //' > "$data/result.txt" || true
cat "$data/result.txt"
if grep -q '^FAIL' "$data/result.txt" || ! grep -q '^failures=0$' "$data/result.txt"; then
    echo "chm_hud_test: FAIL"
    exit 1
fi
echo "chm_hud_test: PASS"
