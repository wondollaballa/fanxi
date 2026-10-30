#!/bin/sh
# Regression test for queued equipment coalescing (host/addons/hooks.c): two outgoing 0x050s for
# the same equipment slot must leave as one packet, carrying the newest piece.  Without the
# coalescing the client sees two changes for the slot in one buffer.  It needs the game image but
# not a running client.
#
#   tests/gear_queue_test.sh --game <FFXI folder>
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

data=$(mktemp -d "${TMPDIR:-/tmp}/gearqueue.XXXXXX")
trap 'rm -rf "$data"' EXIT
FFXI_CONTROL=54397 "$root/build/host64" --game "$game" --data-dir "$data" \
    --addon-harness "$here/gear_queue_test.txt" > "$data/raw.txt" 2>&1 || true
out=$(grep -E '^\[harness\] packet_out:' "$data/raw.txt" || true)

fail() { echo "gear_queue_test: FAIL - $1"; exit 1; }
printf '%s\n' "$out" | grep -q '5004000002040800' || fail 'the newest piece did not leave'
printf '%s\n' "$out" | grep -q '5004000001040000' && fail 'the superseded piece was sent too'
echo "gear_queue_test: PASS"
