#!/bin/sh
# Regression test for the weapon lock (host/addons/phase.c): a pinned main/sub/ranged/ammo slot
# is a lock, not just a filter.  A weaponskill keeps the pinned hand instead of wearing the
# weapon its sets.WS.<name> names, the lock re-arms when the weapon is drawn (the TP set may not
# name a weapon at all), a cast while disengaged may swap it for the cast and puts it back, and a
# Bard's Nitro song is the one exception while engaged.  Run with:
#
#   tests/phase_weapon_lock_test.sh --game <FFXI folder>
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

data=$(mktemp -d "${TMPDIR:-/tmp}/phaseweaplock.XXXXXX")
trap 'rm -rf "$data"' EXIT
FFXI_CONTROL=54396 "$root/build/fanxi" --game "$game" --data-dir "$data" \
    --addon-harness "$here/phase_weapon_lock_test.txt" > "$data/raw.txt" 2>&1 || true
out=$(grep -E '^\[harness\]|^--- ' "$data/raw.txt" || true)

fail() { echo "phase_weapon_lock_test: FAIL - $1"; exit 1; }
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

# The plan loaded and all four weapon slots were pinned (from the idle set's exact copies).
section 'wear the TP set and pin all four weapon slots' 'draw the weapon' \
    | grep -q '^\[harness\] = 0:3$' || fail 'the four weapon slots were not pinned'
has 'draw the weapon' 'a weaponskill keeps the pinned main and sub' '^\[harness\] = true$' \
    || fail 'the weapon was not drawn'

# A weaponskill keeps the pinned hand and only wears its armour set (head 12).
ws='a weaponskill keeps the pinned main and sub, and wears only its armour'
has "$ws" 'the result restores the WS armour' '500400000c040000' \
    || fail 'the weaponskill did not wear its armour'
hasnt "$ws" 'the result restores the WS armour' '500400000a000000' \
    || fail 'the weaponskill swapped the pinned main'
hasnt "$ws" 'the result restores the WS armour' '500400000b010000' \
    || fail 'the weaponskill swapped the pinned sub'
has 'the result restores the WS armour' 'a spell while engaged keeps the pinned hands too' \
    '5004010003040000' || fail 'the weaponskill armour was not restored'

# A spell while engaged is protected exactly like the ability case.
has 'a spell while engaged keeps the pinned hands too' \
    'the result restores the spell armour' '5004020016040000' \
    || fail 'the engaged spell did not wear its armour'
hasnt 'a spell while engaged keeps the pinned hands too' \
      'the result restores the spell armour' '5004020014000000' \
    || fail 'the engaged spell swapped the pinned main'
hasnt 'a spell while engaged keeps the pinned hands too' \
      'the result restores the spell armour' '5004020015010000' \
    || fail 'the engaged spell swapped the pinned sub'
has 'the result restores the spell armour' \
    'a spell id in the Phantom Roll range is still a spell, not a roll' '5004030003040000' \
    || fail 'the engaged spell armour was not restored'

# A spell whose table index is in the Corsair roll range (100) is still a spell: the roll
# exception must not open a pinned hand for it.
roll='a spell id in the Phantom Roll range is still a spell, not a roll'
has "$roll" 'sheathed, the cast may take the casting hand for its window' '5004040016040000' \
    || fail 'the roll-range spell did not wear its armour'
hasnt "$roll" 'sheathed, the cast may take the casting hand for its window' '5004040014000000' \
    || fail 'a spell id in the roll range was treated as a Phantom Roll'

# Sheathed, a cast may take the casting hand for its window...
cast='sheathed, the cast may take the casting hand for its window'
has "$cast" 'and the result puts the locked hand back' '5004060014000000' \
    || fail 'the disengaged cast did not take its main hand'
has "$cast" 'and the result puts the locked hand back' '5004060015010000' \
    || fail 'the disengaged cast did not take its sub hand'
# ...and the result puts the locked hand back.
restore='and the result puts the locked hand back'
has "$restore" 'drawing the weapon re-arms the lock even when the worn table forgot the hand' \
    '5004070001000000' || fail 'the locked main was not restored after the disengaged cast'

# Drawing again re-arms the lock even when the engine forgot what was worn.
redraw='drawing the weapon re-arms the lock even when the worn table forgot the hand'
has "$redraw" 'a Bard under Nitro may take the instrument through the lock' '5004080001000000' \
    || fail 'the lock did not re-arm the main hand on /attack'
has "$redraw" 'a Bard under Nitro may take the instrument through the lock' '5004080002010000' \
    || fail 'the lock did not re-arm the sub hand on /attack'

# The BRD plan and Nitro flag.
brd='a Bard under Nitro may take the instrument through the lock'
section "$brd" 'the result puts the locked instruments back' \
    | grep -q '^\[harness\] = 10$' || fail 'the Bard job did not reach the plan'
section "$brd" 'the result puts the locked instruments back' \
    | grep -q '^\[harness\] = true$' || fail 'Nitro was not armed'
has "$brd" 'the result puts the locked instruments back' '500409001e000000' \
    || fail 'the Nitro song did not take its main hand'
has "$brd" 'the result puts the locked instruments back' '500409001f010000' \
    || fail 'the Nitro song did not take its sub hand'
has "$brd" 'the result puts the locked instruments back' '5004090020020000' \
    || fail 'the Nitro song did not take its instrument'
has "$brd" 'the result puts the locked instruments back' '5004090021030000' \
    || fail 'the Nitro song did not take its ammo'
has "$brd" 'the result puts the locked instruments back' '5004090022040000' \
    || fail 'the Nitro song did not take its song armour'

# Without Nitro the same song is back under the lock: only its armour (head 34) may move.
plain='without Nitro the same song keeps every pinned weapon'
has 'the result puts the locked instruments back' "$plain" '50040a0001000000' \
    || fail 'the Nitro instrument swap was not put back'
has "$plain" '' '50040b0022040000' || fail 'the plain song did not wear its armour'
hasnt "$plain" '' '50040b001e000000' || fail 'the plain song swapped the pinned main'
hasnt "$plain" '' '50040b001f010000' || fail 'the plain song swapped the pinned sub'
hasnt "$plain" '' '50040b0020020000' || fail 'the plain song swapped the pinned instrument'
hasnt "$plain" '' '50040b0021030000' || fail 'the plain song swapped the pinned ammo'
# A TP set that names no weapon (the weaponset outside the state sets owns it) still re-arms
# the pinned copy when /attack is pressed: that is the user-visible case the old filter missed.
tp='a TP set with no weapon still re-arms the locked hand on /attack'
section "$tp" '' | grep -q '^\[harness\] = 5$' || fail 'the no-weapon TP plan did not load'
section "$tp" '' | grep -q '^\[harness\] = 0:1$' || fail 'the remembered main/sub were not pinned'
has "$tp" '' '5004..0001000000' || fail 'the locked main was not re-armed by /attack'
has "$tp" '' '5004..0002010000' || fail 'the locked sub was not re-armed by /attack'
echo "phase_weapon_lock_test: PASS"
