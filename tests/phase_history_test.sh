#!/bin/sh
# Regression test for the phase engine's action-set history (host/addons/phase.c): runs
# tests/phase_history_test.txt in the addon harness with the built-in control addon and compares
# the output with tests/phase_history_test.expected.  The gear page reads the action set and the
# windows from phase_status so a weaponskill's set is shown even when its poll missed it.
#
#   tests/phase_history_test.sh --game <FFXI folder> [--update]
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

data=$(mktemp -d "${TMPDIR:-/tmp}/phasehistory.XXXXXX")
trap 'rm -rf "$data"' EXIT

out="$data/out.txt"
FFXI_CONTROL=54397 "$root/build/fanxi" --game "$game" --data-dir "$data" \
    --addon-harness "$here/phase_history_test.txt" > "$data/raw.txt" 2>&1 || true
grep -E '^\[harness\] =|^--- |lua error|error' "$data/raw.txt" > "$out"

if [ $update -eq 1 ]; then
    cp "$out" "$here/phase_history_test.expected"
    echo "updated phase_history_test.expected"
    exit 0
fi
if diff -u "$here/phase_history_test.expected" "$out"; then
    echo "phase_history_test: PASS"
else
    echo "phase_history_test: FAIL"
    exit 1
fi
