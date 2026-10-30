#!/bin/sh
# Regression test for the Battle hub's widget code (host/addons/lua/battle.lua): runs
# tests/addons/battletest in the addon harness with a mock ImGui API and calls every hub tab.
# It needs the game image for the harness, but not a running client.
#
#   tests/battle_hub_test.sh --game <FFXI folder>
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

data=$(mktemp -d "${TMPDIR:-/tmp}/battletest.XXXXXX")
trap 'rm -rf "$data"' EXIT
mkdir -p "$data/xi/addons"
cp -R "$here/addons/battletest" "$data/xi/addons/"

cat > "$data/script.txt" <<'TXT'
frames 2
load battletest xi
frames 3
TXT
FFXI_ADDONS_LUA="$root/host/addons/lua" "$root/build/host64" --game "$game" --data-dir "$data" \
    --addon-harness "$data/script.txt" > "$data/out.txt" 2>&1 || true
grep -E '^\[chat 1\] (install|ok|FAIL|failures=)' "$data/out.txt" \
    | sed 's/^\[chat 1\] //' > "$data/result.txt" || true
cat "$data/result.txt"
if grep -q '^FAIL' "$data/result.txt" || ! grep -q '^failures=0$' "$data/result.txt"; then
    echo "battle_hub_test: FAIL"
    exit 1
fi
echo "battle_hub_test: PASS"
