#!/bin/sh
# Regression test for the phase engine's session locks (host/addons/phase.c): runs
# tests/phase_job_test.txt in the addon harness with the built-in control addon and compares the
# output with tests/phase_job_test.expected.  A job change, on either the main or the support
# job, must release the full lock, the weapon pins, kiting, resting and the idle focus.
#
#   tests/phase_job_test.sh --game <FFXI folder> [--update]
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

data=$(mktemp -d "${TMPDIR:-/tmp}/phasejob.XXXXXX")
trap 'rm -rf "$data"' EXIT

out="$data/out.txt"
FFXI_CONTROL=54399 "$root/build/host64" --game "$game" --data-dir "$data" \
    --addon-harness "$here/phase_job_test.txt" > "$data/raw.txt" 2>&1 || true
grep -E '^\[harness\] =|^--- |lua error|error' "$data/raw.txt" > "$out"

if [ $update -eq 1 ]; then
    cp "$out" "$here/phase_job_test.expected"
    echo "updated phase_job_test.expected"
    exit 0
fi
if diff -u "$here/phase_job_test.expected" "$out"; then
    echo "phase_job_test: PASS"
else
    echo "phase_job_test: FAIL"
    exit 1
fi
