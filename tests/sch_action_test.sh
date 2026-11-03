#!/bin/sh
# Regression test for the Scholar sequencer's 0x028 hooks (host/addons/lua/sch.lua): an
# ABILITY_FINISH confirms the stratagem and spends a charge, while MAGIC_START and
# MAGIC_FINISH confirm the spell and spend nothing.  Runs tests/sch_action_test.txt in the
# addon harness with the real server-built packets.
#
#   tests/sch_action_test.sh --game <FFXI folder>
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

data=$(mktemp -d "${TMPDIR:-/tmp}/schact.XXXXXX")
trap 'rm -rf "$data"' EXIT
mkdir -p "$data/xi/addons"
cp -R "$here/addons/schtest" "$data/xi/addons/"

out="$data/out.txt"
FFXI_ADDONS_LUA="$root/host/addons/lua" "$root/build/fanxi" --game "$game" --data-dir "$data" \
    --addon-harness "$here/sch_action_test.txt" > "$data/raw.txt" 2>&1 || true
grep -E '^\[harness\] =' "$data/raw.txt" > "$out" || true
if diff -u "$here/sch_action_test.expected" "$out"; then
    echo "sch_action_test: PASS"
else
    echo "sch_action_test: FAIL"
    exit 1
fi
