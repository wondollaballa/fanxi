#!/usr/bin/env python3
"""Check the Corsair roll and Quick Draw pickers in the action HUD.

The Abilities page used to draw every Phantom Roll and every elemental shot as its own tile:
the client's 0x0AC list carries 31 roll actions and 8 shot actions for a level 99 Corsair, so
the page was a forty-tile scroll.  It now keeps Phantom Roll and Quick Draw as two menu doors
and opens a picker for the rest.

The picker's filtering and ordering live in a marked region of `host/addons/lua/control.lua`
so this test can run the real Lua code without the game host.  The checks are:

1. the static wiring: rebuild splits rolls/shots out of the page, hud_click opens the two
   doors, the cooldown poll includes the picker rows, and hud.frame draws the window;
2. the pure list helpers: search normalisation, level/name ordering, shot element order.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'
BEGIN = '-- BEGIN COR roll menu'
END = '-- END COR roll menu'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'


def helper_block() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(BEGIN)
        end = source.index(END) + len(END)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing the COR roll menu markers: {error}')
    return source[start:end]


def check_wiring(source: str, block: str) -> None:
    """The page must keep the two doors and the picker must be part of the draw/live loops."""
    if 'hud.cor_roll_level[item_key]' not in source or 'hud.cor_shot_order[item_key]' not in source:
        raise SystemExit(f'{CONTROL}: rebuild no longer splits rolls/shots into the pickers')
    if "key == 'phantomroll'" not in source or "hud.cor_open('roll')" not in source:
        raise SystemExit(f'{CONTROL}: Phantom Roll does not open the roll picker')
    if "key == 'quickdraw'" not in source or "hud.cor_open('shot')" not in source:
        raise SystemExit(f'{CONTROL}: Quick Draw does not open the shot picker')
    if 'hud_learn_live_cooldowns(hud.cool, { hud.abilities, hud.cor_rolls, hud.cor_shots }' not in source:
        raise SystemExit(f'{CONTROL}: the cooldown poll does not cover the picker rows')
    if 'if hud.cor_menu.open then hud.cor_window(api) end' not in source:
        raise SystemExit(f'{CONTROL}: hud.frame never draws the picker')
    if 'local dialog_on = hud.jug_state.open or hud.pet_state.open or hud.cor_menu.open' not in source:
        raise SystemExit(f'{CONTROL}: the picker does not keep the HUD frame alive')
    if "rest == 'roll'" not in source or "rest == 'quickdraw'" not in source:
        raise SystemExit(f'{CONTROL}: //hud roll and //hud quickdraw are missing')
    for label in ('Search rolls', 'Level acquired', 'Sort'):
        if label not in source:
            raise SystemExit(f'{CONTROL}: the roll picker lost its {label!r} control')
    if 'function hud.cor_shot_rows' not in block or 'function hud.cor_roll_rows' not in block:
        raise SystemExit(f'{CONTROL}: the picker list helpers are missing')
    if 'hud.cor_roll_names' not in source or "action = roll_action" not in source:
        raise SystemExit(f'{CONTROL}: Phantom Roll is not expanded to the 31 roll actions')
    if 'local worn_ids = {}' not in source or "not worn_ids[item_id]" not in source:
        raise SystemExit(f'{CONTROL}: inject_plan still sends already-equipped pieces')
    if 'xi.phase.stale' not in source:
        raise SystemExit(f'{CONTROL}: the phase watch does not restore refused abilities')
    check_action_coverage(source)


def action_key(name: str) -> str:
    return ''.join(ch for ch in name.lower() if ch.isalnum())


def check_action_coverage(source: str) -> None:
    """Every COR roll and shot the client's list names must have a picker row.

    The tables are keyed by the same punctuation-stripped names the HUD uses, so a typo
    (say, `corsairroll` for `corsairsroll`) would silently leave that roll on the page.
    """
    import re

    job_line = re.search(r'\[17\]\s*=\s*"([^"]+)"', source)
    if job_line is None:
        raise SystemExit(f'{CONTROL}: HUD_ABILITY_JOBS[17] is missing')
    names = job_line.group(1).split('|')
    rolls = [name for name in names
             if name.lower().endswith('roll') and action_key(name) != 'phantomroll']
    shots = [name for name in names
             if name.lower().endswith('shot') and action_key(name) != 'tripleshot']
    if len(rolls) != 31:
        raise SystemExit(f'{CONTROL}: expected 31 COR rolls in HUD_ABILITY_JOBS, found {len(rolls)}')
    if len(shots) != 8:
        raise SystemExit(f'{CONTROL}: expected 8 COR shots in HUD_ABILITY_JOBS, found {len(shots)}')

    def table_keys(field: str) -> set[str]:
        match = re.search(rf'{field}\s*=\s*\{{(.*?)\n\s*\}}', source, re.S)
        if match is None:
            raise SystemExit(f'{CONTROL}: {field} is missing')
        return set(re.findall(r'([a-z0-9]+)\s*=\s*\d+', match.group(1)))

    levels = table_keys('cor_roll_level')
    orders = table_keys('cor_shot_order')
    missing_rolls = [name for name in rolls if action_key(name) not in levels]
    missing_shots = [name for name in shots if action_key(name) not in orders]
    if missing_rolls:
        raise SystemExit(f'{CONTROL}: cor_roll_level has no row for {", ".join(missing_rolls)}')
    if missing_shots:
        raise SystemExit(f'{CONTROL}: cor_shot_order has no row for {", ".join(missing_shots)}')
    if 'phantomroll' in levels:
        raise SystemExit(f'{CONTROL}: Phantom Roll is the menu door, not a roll row')
    for door in ('quickdraw', 'tripleshot'):
        if door in orders:
            raise SystemExit(f'{CONTROL}: {door} stays on the page, not in the shot picker')


LUA_TEST = r'''
local function eq(got, want, label)
  if got ~= want then
    error(string.format('%s: got %s, want %s', label, tostring(got), tostring(want)), 0)
  end
end

local function names(rows)
  local out = {}
  for index, row in ipairs(rows) do out[index] = row.name end
  return table.concat(out, '|')
end

hud.cor_rolls = {
    { name = "Miser's Roll", level = 92, id = 303 },
    { name = 'Monk\'s Roll', level = 31, id = 99 },
    { name = 'Beast Roll', level = 34, id = 106 },
    { name = 'Samurai Roll', level = 34, id = 109 },
    { name = 'Chaos Roll', level = 14, id = 105 },
    { name = "Corsair's Roll", level = 5, id = 114 },
}
hud.cor_shots = {
    { name = 'Dark Shot', order = 8, id = 132 },
    { name = 'Fire Shot', order = 1, id = 125 },
    { name = 'Wind Shot', order = 3, id = 127 },
    { name = 'Light Shot', order = 7, id = 131 },
    { name = 'Ice Shot', order = 2, id = 126 },
    { name = 'Earth Shot', order = 4, id = 128 },
    { name = 'Water Shot', order = 6, id = 130 },
    { name = 'Thunder Shot', order = 5, id = 129 },
}

-- Level acquired is the default order; the tie at 34 breaks by name.
eq(names(hud.cor_roll_rows('', 'level')),
   "Corsair's Roll|Chaos Roll|Monk's Roll|Beast Roll|Samurai Roll|Miser's Roll",
   'level order')
eq(names(hud.cor_roll_rows('', 'name')),
   "Beast Roll|Chaos Roll|Corsair's Roll|Miser's Roll|Monk's Roll|Samurai Roll",
   'name order')

-- Search is case-insensitive and ignores the apostrophe, so a player can type the name
-- without punctuation.
eq(names(hud.cor_roll_rows('chaos', 'level')), 'Chaos Roll', 'plain search')
eq(names(hud.cor_roll_rows('CORSAIRS', 'level')), "Corsair's Roll", 'punctuation-stripped search')
eq(#hud.cor_roll_rows('no such roll', 'level'), 0, 'no match')
eq(#hud.cor_roll_rows(nil, 'level'), 6, 'nil search lists everything')
eq(#hud.cor_roll_rows('  ', 'level'), 6, 'blank search lists everything')

-- A fresh picker is empty; the shot door is not a text search either.
hud.cor_menu.search[1] = 'stale'
hud.cor_open('roll')
eq(hud.cor_menu.open, true, 'roll picker opens')
eq(hud.cor_menu.kind, 'roll', 'roll kind')
eq(hud.cor_menu.search[1], '', 'search clears')
hud.cor_open('shot')
eq(hud.cor_menu.kind, 'shot', 'shot kind')
hud.cor_open('bogus')
eq(hud.cor_menu.kind, 'roll', 'unknown kind falls back to rolls')

-- Shots always come back in the client's element order, not insertion or alphabetical order.
eq(names(hud.cor_shot_rows()),
   'Fire Shot|Ice Shot|Wind Shot|Earth Shot|Thunder Shot|Water Shot|Light Shot|Dark Shot',
   'shot element order')

-- A row without a name or level must not crash the picker.
hud.cor_rolls = { { id = 1 } }
eq(#hud.cor_roll_rows('', 'level'), 1, 'nameless row still listed')
eq(#hud.cor_roll_rows('x', 'level'), 0, 'nameless row does not match')
hud.cor_shots = {}
eq(#hud.cor_shot_rows(), 0, 'no shots')

-- The picker's lucky/unlucky table is keyed like cor_roll_level and carries both numbers.
eq(hud.cor_roll_lucky.fightersroll[1], 5, 'Fighter lucky V')
eq(hud.cor_roll_lucky.fightersroll[2], 9, 'Fighter unlucky IX')
eq(hud.cor_roll_lucky.samurairoll[1], 2, 'Samurai lucky II')
eq(hud.cor_roll_lucky.samurairoll[2], 6, 'Samurai unlucky VI')
eq(#hud.cor_roll_names, 31, 'all 31 roll actions are named')

return 'OK: COR roll search, sort, shot order and lucky numbers'
'''


def run_lua(script: str) -> str:
    lupa = None
    if os.environ.get('COR_HUD_TEST_LUAJIT') != '1':
        try:
            import lupa  # noqa: F401
            from lupa import LuaRuntime  # type: ignore
        except ImportError:
            lupa = None
    if lupa is not None:
        runtime = LuaRuntime(unpack_returned_tuples=True)
        return str(runtime.execute(script))
    if LUAJIT.is_file():
        wrapped = ('local ok, result = pcall(function()\n' + script
                   + '\nend)\nif not ok then error(result) end\nprint(result)\n')
        result = subprocess.run(
            [str(LUAJIT), '-'], input=wrapped, text=True, capture_output=True, cwd=ROOT)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()
    return 'SKIP: install lupa or build the vendored LuaJIT to run this test'


def check_lucky_table(source: str) -> None:
    """The HUD's lucky/unlucky rows must match the server's roll tables."""
    import re
    import sys

    sys.path.insert(0, str(ROOT / 'server'))
    from fanxi_server.game import rolls  # noqa: PLC0415

    match = re.search(r'cor_roll_lucky\s*=\s*\{(.*?)\n\}', source, re.S)
    if match is None:
        raise SystemExit(f'{CONTROL}: cor_roll_lucky is missing')
    hud_odds = {
        key: (int(lucky), int(unlucky))
        for key, lucky, unlucky in re.findall(
            r'([a-z0-9]+)\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}', match.group(1))
    }
    server_odds = {
        action_key(spec.name): (spec.lucky, spec.unlucky)
        for spec in rolls.ROLLS.values()
    }
    # ``cor_roll_level`` also carries two aliases for the client's alternate spellings.
    for alias, canonical in (('corsairroll', 'corsairsroll'),
                             ('magusroll', 'magussroll')):
        if hud_odds.get(alias) != hud_odds.get(canonical):
            raise SystemExit(f'{CONTROL}: cor_roll_lucky alias {alias} disagrees')
        server_odds.pop(alias, None)
    hud_odds = {key: value for key, value in hud_odds.items()
                if key not in ('corsairroll', 'magusroll')}
    if hud_odds != server_odds:
        missing = sorted(set(server_odds) - set(hud_odds))
        extra = sorted(set(hud_odds) - set(server_odds))
        wrong = sorted(key for key in set(hud_odds) & set(server_odds)
                       if hud_odds[key] != server_odds[key])
        raise SystemExit(f'{CONTROL}: cor_roll_lucky mismatch'
                         f' missing={missing} extra={extra} wrong={wrong}')
    for label in ('Lucky ', 'Unlucky ', 'Lucky number:', 'Unlucky number:'):
        if label not in source:
            raise SystemExit(f'{CONTROL}: the picker does not draw {label!r}')


def main() -> int:
    source = CONTROL.read_text(encoding='utf-8')
    block = helper_block()
    check_wiring(source, block)
    check_lucky_table(source)
    stub = ("hud = { cor_menu = { open = false, kind = 'roll', search = { '' }, "
            "sort = 'level' } }\n")
    print(run_lua(stub + block + LUA_TEST))
    return 0


if __name__ == '__main__':
    sys.exit(main())
