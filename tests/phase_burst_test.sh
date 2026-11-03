#!/bin/sh
# Regression test for the automatic Magic Burst midcast set (host/addons/phase.c): a rule may
# name a `burst` set, and the engine wears it instead of `mid` only while xi.phase.burst(true)
# is on; an action whose rule has no burst set keeps its ordinary midcast set either way.
# Runs tests/phase_burst_test.txt in the addon harness and compares the output with
# tests/phase_burst_test.expected.
#
#   tests/phase_burst_test.sh --game <FFXI folder> [--update]
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

data=$(mktemp -d "${TMPDIR:-/tmp}/phaseburst.XXXXXX")
trap 'rm -rf "$data"' EXIT

out="$data/out.txt"
FFXI_ADDONS_LUA="$root/host/addons/lua" FFXI_CONTROL=54397 "$root/build/fanxi" --game "$game" --data-dir "$data" \
    --addon-harness "$here/phase_burst_test.txt" > "$data/raw.txt" 2>&1 || true
grep -E '^\[harness\] =|^\[harness\] packet_out:|^--- |lua error|error' "$data/raw.txt" > "$out"

if [ $update -eq 1 ]; then
    cp "$out" "$here/phase_burst_test.expected"
    echo "updated phase_burst_test.expected"
    exit 0
fi
if diff -u "$here/phase_burst_test.expected" "$out"; then
    echo "phase_burst_test: PASS"
else
    echo "phase_burst_test: FAIL"
    exit 1
fi
