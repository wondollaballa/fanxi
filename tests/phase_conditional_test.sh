#!/bin/sh
# Regression test for conditional action sets (host/addons/phase.c): a set named
# "Victory Smite (Impetus)" is chosen only while every buff in the parentheses is up, the
# unconditional set is the fallback, and the most specific variant wins.  Runs
# tests/phase_conditional_test.txt in the addon harness and compares the output with
# tests/phase_conditional_test.expected.
#
#   tests/phase_conditional_test.sh --game <FFXI folder> [--update]
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

data=$(mktemp -d "${TMPDIR:-/tmp}/phaseconditional.XXXXXX")
trap 'rm -rf "$data"' EXIT

out="$data/out.txt"
FFXI_CONTROL=54396 "$root/build/fanxi" --game "$game" --data-dir "$data" \
    --addon-harness "$here/phase_conditional_test.txt" > "$data/raw.txt" 2>&1 || true
grep -E '^\[harness\] =|^--- |lua error|error' "$data/raw.txt" > "$out"

if [ $update -eq 1 ]; then
    cp "$out" "$here/phase_conditional_test.expected"
    echo "updated phase_conditional_test.expected"
    exit 0
fi
if diff -u "$here/phase_conditional_test.expected" "$out"; then
    echo "phase_conditional_test: PASS"
else
    echo "phase_conditional_test: FAIL"
    exit 1
fi
