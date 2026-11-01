#!/bin/sh
# Regression test for the locked-action override (host/addons/phase.c): while the full lock or
# slot locks are on, a job ability still gets its armour precast/midcast set, then the original
# armour and the original lock state are restored.  A locked main/sub/ranged/ammo slot is the one
# exception: it stays on through the ability (the DRK Last Resort scythe bug), while a
# weaponskill still wears the weapon its own set names.
#
#   tests/phase_lock_override_test.sh --game <FFXI folder>
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

data=$(mktemp -d "${TMPDIR:-/tmp}/phaselock.XXXXXX")
trap 'rm -rf "$data"' EXIT
FFXI_CONTROL=54397 "$root/build/fanxi" --game "$game" --data-dir "$data" \
    --addon-harness "$here/phase_lock_override_test.txt" > "$data/raw.txt" 2>&1 || true
out=$(grep -E '^\[harness\]|^--- ' "$data/raw.txt" || true)

fail() { echo "phase_lock_override_test: FAIL - $1"; exit 1; }
# The lines between "--- start" and "--- stop", so the same byte string in a later section does
# not satisfy or break a check here.
section() {
    printf '%s\n' "$out" | awk -v start="$1" -v stop="$2" '
        $0 == "--- " start { on = 1; next }
        $0 == "--- " stop  { on = 0 }
        on'
}
has() { section "$1" "$2" | grep -q "$3"; }
hasnt() { ! has "$1" "$2" "$3"; }

printf '%s\n' "$out" | grep -q '^\[harness\] = 3$' || fail 'the rule table did not load'
printf '%s\n' "$out" | grep -q '^\[harness\] = true$' || fail 'the full lock did not engage'

# Full lock: head 11 must go despite the lock, but the locked main 10 must stay off.
has 'a locked job ability gets its armour pre set, but not the locked weapon' \
    'the next buffer releases the action with its armour mid set' '500400000b040000' \
    || fail 'locked head precast was not sent'
hasnt 'a locked job ability gets its armour pre set, but not the locked weapon' \
      'the next buffer releases the action with its armour mid set' '500400000a000000' \
    || fail 'a locked main was swapped by the ability'
has 'the next buffer releases the action with its armour mid set' \
    'the result restores the armour and keeps the lock' '0900c800' \
    || fail 'the locked ability was not released'
has 'the next buffer releases the action with its armour mid set' \
    'the result restores the armour and keeps the lock' '500401000d040000' \
    || fail 'locked head midcast was not sent'
hasnt 'the next buffer releases the action with its armour mid set' \
      'the result restores the armour and keeps the lock' '500401000c000000' \
    || fail 'a locked main midcast was swapped in'
has 'the result restores the armour and keeps the lock' \
    'slot locks: the pinned main stays, the head still swaps and comes back' '5004020003040000' \
    || fail 'the original head was not restored'
hasnt 'the result restores the armour and keeps the lock' \
      'slot locks: the pinned main stays, the head still swaps and comes back' '5004020001000000' \
    || fail 'the original main was restored over a locked one'
printf '%s\n' "$out" | grep -q '^\[harness\] = true$' || fail 'the full lock was not kept'

# Slot locks: the mask must survive the action, the pinned main must stay, the head must swap.
printf '%s\n' "$out" | grep -q '^\[harness\] = 2:0:4$' || fail 'the slot mask was not restored'
has 'slot locks: the pinned main stays, the head still swaps and comes back' \
    'a manual pinned sub stays on through a job ability' '500402000b040000' \
    || fail 'the unlocked head precast was not sent'
hasnt 'slot locks: the pinned main stays, the head still swaps and comes back' \
      'a manual pinned sub stays on through a job ability' '500402000a000000' \
    || fail 'a pinned main was swapped by the ability'
has 'slot locks: the pinned main stays, the head still swaps and comes back' \
    'a manual pinned sub stays on through a job ability' '5004030003040000' \
    || fail 'the unlocked head was not restored'

# A manually worn, pinned sub outside the state sets stays on through a job ability.
has 'a manual pinned sub stays on through a job ability' \
    'a weaponskill keeps the pinned sub and wears only its armour' '5004030018040800' \
    || fail 'the unlocked head was not swapped in'
hasnt 'a manual pinned sub stays on through a job ability' \
      'a weaponskill keeps the pinned sub and wears only its armour' '5004..0016010800' \
    || fail 'a pinned sub was swapped by the job ability'
has 'a manual pinned sub stays on through a job ability' \
    'a weaponskill keeps the pinned sub and wears only its armour' '5004020003040000' \
    || fail 'the original head was not restored after the ability'
printf '%s\n' "$out" | grep -q '^\[harness\] = 1:1$' || fail 'the single sub pin was not restored'

# A weaponskill is not an exception any more: the pinned hand stays on and the WS is rolled with
# it, so only the armour set goes on and comes back.
ws='a weaponskill keeps the pinned sub and wears only its armour'
hasnt "$ws" '' '5004..0016010800' || fail 'the weaponskill swapped the pinned sub'
has "$ws" '' '5004..0018040800' || fail 'the weaponskill head was not swapped in'
has "$ws" '' '5004..0003040000' || fail 'the original head was not restored after the weaponskill'
printf '%s\n' "$out" | grep -q '^\[harness\] = 1:1$' || fail 'the single sub pin was not restored after the weaponskill'
echo "phase_lock_override_test: PASS"
