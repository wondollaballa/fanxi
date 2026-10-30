#!/usr/bin/env python3
"""Check the Magic Bag row columns and the item-card augment/RP decoder.

The jumbled bag column was a layout overlap: the bag label started at x=310 and the
Pull button at x=410, while "Magic Bag (locker)" is wider than 100 px.  The card
decodes the client's 24-byte bundle block in Lua because the HUD only receives the
raw extdata hex from the server.

The test runs the extracted Lua region with lupa or the vendored LuaJIT; without
either it skips (exit 0), matching tests/hud_cool_test.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'
BEGIN = '-- BEGIN Magic Bag card helpers'
END = '-- END Magic Bag card helpers'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'


def helper_block() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(BEGIN)
        end = source.index(END) + len(END)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing Magic Bag card markers: {error}')
    return source[start:end]


def check_layout(source: str, block: str) -> None:
    """The action column must start beyond the bag label's widest exported text."""
    if 'api.BeginPopupModal' not in block:
        raise SystemExit(f'{CONTROL}: the item card is not a modal popup')
    if 'api.IsMouseDoubleClicked' not in source or 'hud.inv_state.card = row' not in source:
        raise SystemExit(f'{CONTROL}: a row double-click does not set the item card')
    if ('api.SameLine(hud.inv_layout.bag_x' not in source
            or 'api.SameLine(hud.inv_layout.action_x' not in source):
        raise SystemExit(f'{CONTROL}: the bag/action columns no longer use the layout table')
    if 'hud.inv_fit(api, row.bag_name' not in source:
        raise SystemExit(f'{CONTROL}: the bag label is not clipped to its column')


LUA_TEST = r'''
local function eq(got, want, label)
  if got ~= want then
    error(string.format('%s: got %s, want %s', label, tostring(got), tostring(want)), 0)
  end
end

local layout = hud.inv_layout
eq(type(layout), 'table', 'layout table')
eq(layout.action_x > layout.bag_x + layout.bag_width, true, 'action clears bag column')
eq(layout.bag_width >= 170, true, 'bag column fits "Magic Bag (locker)"')

-- An Oboro HQ2 path C: rank 25, tier 2 (max 25), 25,150 RP, bundle 480.
local meta = hud.inv_augment_meta('03830000fa886501e0010000000000000000000000000000')
eq(meta.path, 'C', 'path')
eq(meta.rank, 25, 'rank')
eq(meta.max_rank, 25, 'max rank')
eq(meta.rp, 25150, 'rp')
eq(meta.curve, 0, 'curve')
eq(meta.index, 480, 'bundle index')

-- A standard Ambuscade cape block is 02 03, not a bundle, so it has no RP.
eq(hud.inv_augment_meta('0203019A449817488E483648000000000000000000000000'), nil, 'cape no RP')
eq(hud.inv_augment_meta('0383'), nil, 'short hex')
eq(hud.inv_augment_meta('not hex'), nil, 'bad hex')

local cape = hud.inv_augment_lines(
  'DEX+20, Accuracy+20 Attack+20, Accuracy+10, "Store TP"+10, Phys. dmg. taken-10%')
eq(#cape, 5, 'cape slots')
eq(cape[1], 'DEX+20', 'cape first slot')
eq(cape[5], 'Phys. dmg. taken-10%', 'cape last slot')

local bundle = hud.inv_augment_lines(
  'Song spellcasting time -15% | Song effects: "Double Attack"+2%')
eq(#bundle, 2, 'bundle rows')
eq(bundle[2], 'Song effects: "Double Attack"+2%', 'bundle second row')
eq(#hud.inv_augment_lines('not augmented'), 0, 'empty cape text')
eq(#hud.inv_augment_lines(''), 0, 'empty text')
local status = hud.inv_augment_lines('Rank 15 (tier 3, path A), bundle 12')
eq(#status, 1, 'bundle status stays one line')
eq(status[1], 'Rank 15 (tier 3, path A), bundle 12', 'bundle status text')
eq(hud.inv_text({ en = 'English', ja = 'Japanese' }), 'English', 'localized text')

local fake_api = { CalcTextSize = function(text) return #text end }
eq(hud.inv_fit(fake_api, 'Magic Bag (locker)', 178), 'Magic Bag (locker)', 'fits bag label')
eq(hud.inv_fit(fake_api, 'Magic Bag (locker)', 10), 'Magic Ba..', 'clips long label')

return 'OK: Magic Bag columns and item card helpers'
'''


def run_lua(script: str) -> str:
    lupa = None
    if os.environ.get('MAGIC_BAG_TEST_LUAJIT') != '1':
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


def main() -> int:
    source = CONTROL.read_text(encoding='utf-8')
    block = helper_block()
    check_layout(source, block)
    print(run_lua('hud = {}\n' + block + LUA_TEST))
    return 0


if __name__ == '__main__':
    sys.exit(main())
