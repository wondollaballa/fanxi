#!/bin/sh
# Regression test for the control addon's Magic Burst window (host/addons/lua/control.lua): the
# closing action's 0x028 skillchain proc opens the window on the target, a landed weapon skill
# that forms no chain closes it, a weapon skill with no resonance properties does not, and the
# duration follows the server (11 s after a level-1 link, one second less per level-2/3 link).
# Runs tests/phase_mb_test.txt in the addon harness and compares the output with
# tests/phase_mb_test.expected.
#
#   tests/phase_mb_test.sh --game <FFXI folder> [--update]
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(dirname "$here")
game=""
update=0
while [ $# -gt 0 ]; do
    case "$1" in
        --game) game="$2"; shift 2 ;;
        --update) update=1; shift ;;
        *) echo "usage: $0 --game <FFXI folder> [--update]"; exit 2 ;;
    esac
done
[ -n "$game" ] || { echo "usage: $0 --game <FFXI folder> [--update]"; exit 2; }

data=$(mktemp -d "${TMPDIR:-/tmp}/phasemb.XXXXXX")
trap 'rm -rf "$data"' EXIT

out="$data/out.txt"
FFXI_ADDONS_LUA="$root/host/addons/lua" FFXI_CONTROL=54399 "$root/build/fanxi" --game "$game" --data-dir "$data" \
    --addon-harness "$here/phase_mb_test.txt" > "$data/raw.txt" 2>&1 || true
grep -E '^\[harness\] =|^--- |lua error|error' "$data/raw.txt" > "$out"

if [ $update -eq 1 ]; then
    cp "$out" "$here/phase_mb_test.expected"
    echo "updated phase_mb_test.expected"
    exit 0
fi
if diff -u "$here/phase_mb_test.expected" "$out"; then
    echo "phase_mb_test: PASS"
else
    echo "phase_mb_test: FAIL"
    exit 1
fi
