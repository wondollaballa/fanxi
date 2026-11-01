#!/bin/sh
# Regression test for the phase engine's one-shot pre-action gear (host/addons/phase.c):
# the jug picker hands the engine the chosen jug's slot and the held Call Beast/Bestial
# Loyalty action waits one buffer while that 0x050 goes out.  It needs the game image but
# not a running client.
#
#   tests/phase_precache_test.sh --game <FFXI folder>
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

data=$(mktemp -d "${TMPDIR:-/tmp}/phaseprecache.XXXXXX")
trap 'rm -rf "$data"' EXIT
FFXI_CONTROL=54396 "$root/build/fanxi" --game "$game" --data-dir "$data" \
    --addon-harness "$here/phase_precache_test.txt" > "$data/raw.txt" 2>&1 || true
out=$(grep -E '^\[harness\]|^--- ' "$data/raw.txt" || true)

fail() { echo "phase_precache_test: FAIL - $1"; exit 1; }
printf '%s\n' "$out" | grep -q '^\[harness\] = 1$' || fail 'the rule table did not load'
printf '%s\n' "$out" | grep -q '^\[harness\] = true$' || fail 'precache was not accepted'
# The first 0x01A must be held: only the jug's 0x050 leaves this buffer.
printf '%s\n' "$out" | grep -q '500400000d0300' \
    || fail 'the jug 0x050 was not in the held buffer'
# The held action is released on the next sequenced buffer.
printf '%s\n' "$out" | grep -q '09008301' || fail 'the held Bestial Loyalty action did not leave'
printf '%s\n' "$out" | grep -q '^\[harness\] = 387$' || fail 'the held action was not Bestial Loyalty'
echo "phase_precache_test: PASS"
