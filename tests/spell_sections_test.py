#!/usr/bin/env python3
"""Check the spell window's section headings and the Kaustra buff gate.

`host/addons/lua/control.lua` keeps the spell-section rules in the marked region
(`BEGIN/END HUD spell sections`) so this test can run the real Lua code without loading
the game host.  The Nuke page must split into a Helix block, one block per element,
and a non-elemental block; the other pages must put Protect & Shell, Regen & Refresh,
Bars, Cures, Raises, Sleep and the travel spells under their own headings.  The same
region carries the rule that keeps Kaustra unclickable until Tabula Rasa is up.

The test needs a Lua interpreter.  It uses lupa when installed, otherwise a built
LuaJIT from `build/third_party/luajit-src/src/luajit`; with neither it skips (exit 0).
Set SPELL_SECTIONS_TEST_LUAJIT=1 to force the LuaJIT path.  Run it directly or through
`scripts/test.sh`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'
BEGIN = '-- BEGIN HUD spell sections'
END = '-- END HUD spell sections'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'


def sections_block() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(BEGIN)
        end = source.index(END) + len(END)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing the spell-section markers: {error}')
    return source[start:end]


LUA_TEST = r'''
local function want(name, kind, element, magic, title)
  local item = { name = name, kind = kind, element = element, magic = magic }
  local got = hud.spell_section(item, kind)
  if got ~= title then
    error(string.format('%s -> %s, want %s', name, tostring(got), tostring(title)), 0)
  end
end

-- Nuke: each element gets its own heading, helixes get their own, and Meteor has no element.
want('Pyrohelix', 'Nuke', 0, 2, 'Helix')
want('Noctohelix', 'Nuke', 7, 2, 'Helix')
want('Fire', 'Nuke', 0, 2, 'Fire')
want('Blizzard', 'Nuke', 1, 2, 'Ice')
want('Aero', 'Nuke', 2, 2, 'Wind')
want('Stone', 'Nuke', 3, 2, 'Earth')
want('Thunder', 'Nuke', 4, 2, 'Thunder')
want('Water', 'Nuke', 5, 2, 'Water')
want('Holy', 'Nuke', 6, 2, 'Light')
want('Comet', 'Nuke', 7, 2, 'Dark')
want('Meteor', 'Nuke', 15, 2, 'Non-elemental')
want('Screwdriver', 'Nuke', 15, 6, 'Blue Magic')

-- Healing and buffs.
want('Cure II', 'Healing', nil, 1, 'Cures')
want('Curaga', 'Healing', nil, 1, 'Cures')
want('Raise', 'Healing', nil, 1, 'Raises')
want('Reraise', 'Healing', nil, 1, 'Raises')
want('Poisona', 'Healing', nil, 1, 'Status Removal')
want('Esuna', 'Healing', nil, 1, 'Status Removal')
want('Protect II', 'Buff', nil, 1, 'Protect & Shell')
want('Shell', 'Buff', nil, 1, 'Protect & Shell')
want('Regen II', 'Buff', nil, 1, 'Regen & Refresh')
want('Refresh', 'Buff', nil, 1, 'Regen & Refresh')
want('Haste', 'Buff', nil, 1, 'Haste')
want('Barblizzard', 'Buff', nil, 1, 'Bars')
want('Barsilence', 'Buff', nil, 1, 'Bars')
want('Firestorm', 'Buff', nil, 1, 'Storms')
want('Firestorm II', 'Buff', nil, 1, 'Storms')
want('Aurorastorm II', 'Buff', nil, 1, 'Storms')
want('Feather Storm', 'Buff', nil, 6, 'Blue Magic')
want('Enfire', 'Buff', nil, 1, 'Enspells')
want('Endark', 'Buff', nil, 1, 'Enspells')
want("Mage's Ballad", 'Buff', nil, 5, 'Songs')
want('Utsusemi: Ichi', 'Buff', nil, 4, 'Ninjutsu')
want('Cocoon', 'Buff', nil, 6, 'Blue Magic')
want('Indi-Refresh', 'Buff', nil, 7, 'Geomancy')
want('Blink', 'Buff', nil, 1, 'Utility')
want('Adloquium', 'Buff', nil, 1, 'Utility')

-- Debuffs.
want('Sleep II', 'Debuff', nil, 2, 'Sleep')
want('Bind', 'Debuff', nil, 2, 'Bind & Gravity')
want('Gravity II', 'Debuff', nil, 2, 'Bind & Gravity')
want('Dispel', 'Debuff', nil, 2, 'Dispel')
want('Slow II', 'Debuff', nil, 2, 'Slow')
want('Paralyze', 'Debuff', nil, 2, 'Paralyze')
want('Bio II', 'Debuff', nil, 2, 'Poison')
want('Dia III', 'Debuff', nil, 2, 'Poison')
want('Blind', 'Debuff', nil, 2, 'Blind & Silence')
want('Silence', 'Debuff', nil, 2, 'Blind & Silence')
want('Absorb-INT', 'Debuff', nil, 2, 'Absorb')
want('Addle', 'Debuff', nil, 2, 'Enfeebling')

-- Travel, avatars and saved warp marks.
want('Warp', 'Zoning', nil, 1, 'Warp')
want('Teleport-Holla', 'Zoning', nil, 1, 'Teleport')
want('Recall-Jugner', 'Zoning', nil, 1, 'Recall')
want('Escape', 'Zoning', nil, 1, 'Escape & Retrace')
want('Retrace', 'Zoning', nil, 1, 'Escape & Retrace')
want('Carbuncle', 'Avatar', nil, 3, 'Avatars')
want('Fire Spirit', 'Avatar', nil, 3, 'Spirits')
local mark = { name = 'Mog House', kind = 'warp' }
if hud.spell_section(mark, 'Zoning') ~= 'Warp Marks' then
  error('saved warp mark did not join Warp Marks', 0)
end

-- A whole Nuke page sorts Helix first, then elements in client order, then Meteor.
local page = { items = {
  { name = 'Meteor', kind = 'Nuke', element = 15 },
  { name = 'Fire', kind = 'Nuke', element = 0 },
  { name = 'Pyrohelix', kind = 'Nuke', element = 0, helix = true },
  { name = 'Blizzard', kind = 'Nuke', element = 1 },
  { name = 'Stone', kind = 'Nuke', element = 3 },
  { name = 'Water', kind = 'Nuke', element = 5 },
} }
local sections = hud.spell_page_sections({ group = 'type' }, page)
local titles = {}
for _, section in ipairs(sections or {}) do titles[#titles + 1] = section.title end
if table.concat(titles, ',') ~= 'Helix,Fire,Ice,Earth,Water,Non-elemental' then
  error('Nuke section order: ' .. table.concat(titles, ','), 0)
end
if sections[1].hint ~= 'Elemental DoT' then
  error('Helix hint: ' .. tostring(sections[1].hint), 0)
end
if hud.spell_page_sections({ group = 'custom' }, page) ~= nil then
  error('custom grouping should keep the player split', 0)
end
if hud.spell_page_sections({ group = 'none' }, page) ~= nil then
  error('a flat list should stay flat', 0)
end

-- A one-section page needs no heading of its own.
local single = hud.spell_page_sections({ group = 'type' },
  { items = { { name = 'Cure', kind = 'Healing' } } })
if single ~= nil then error('single-section page grew a heading', 0) end

-- A page that is entirely Bard songs keeps the older family split.
local old_song_sections = HUD_SHORT.song_sections
HUD_SHORT.song_sections = function(items)
  return {
    { title = 'Attack', hint = 'Minuet', color = { 255, 100, 100 }, order = 100,
      items = { items[1] } },
    { title = 'Recovery', hint = 'Paeon', color = { 100, 255, 100 }, order = 200,
      items = { items[2] } },
  }
end
local song_page = { items = {
  { name = 'Valor Minuet', kind = 'Buff', magic = 5 },
  { name = 'Army\'s Paeon', kind = 'Buff', magic = 5 },
} }
local songs = hud.spell_page_sections({ group = 'type' }, song_page)
if not songs or #songs ~= 2 or songs[1].title ~= 'Attack' or songs[2].title ~= 'Recovery' then
  error('Bard family sections were not preserved', 0)
end
-- A mixed page keeps the song families and puts the non-song buffs after them.
local mixed_page = { items = {
  { name = 'Valor Minuet', kind = 'Buff', magic = 5 },
  { name = 'Army\'s Paeon', kind = 'Buff', magic = 5 },
  { name = 'Protect', kind = 'Buff', magic = 1 },
} }
local mixed = hud.spell_page_sections({ group = 'type' }, mixed_page)
if not mixed or #mixed ~= 3 or mixed[3].title ~= 'Protect & Shell' then
  error('mixed song/buff page lost a section', 0)
end
HUD_SHORT.song_sections = old_song_sections

-- Kaustra is clickable only while Tabula Rasa is up; every other spell is ungated.
local kaustra = { name = 'Kaustra', requires_buff = 377, requires_label = 'Tabula Rasa' }
local down = hud.spell_gate(kaustra, function(id) return id ~= 377 end)
if down ~= 'Tabula Rasa' then
  error('Kaustra should be gated without Tabula Rasa, got ' .. tostring(down), 0)
end
if hud.spell_gate(kaustra, function(id) return id == 377 end) ~= nil then
  error('Kaustra should cast under Tabula Rasa', 0)
end
if hud.spell_gate({ name = 'Fire' }, function() return false end) ~= nil then
  error('a normal spell should not be gated', 0)
end

return 'OK: spell sections, Nuke order, Bard families and the Tabula Rasa gate'
'''


def run_lua(script: str) -> str:
    lupa = None
    if os.environ.get('SPELL_SECTIONS_TEST_LUAJIT') != '1':
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
    stubs = '''
local hud = {}
local HUD_ELEMENTS = { 'Fire', 'Ice', 'Wind', 'Earth', 'Thunder', 'Water', 'Light', 'Dark' }
local HUD_SHORT = { song_sections = function() return nil end }
local function hud_spell_kind(item) return item.kind or 'Other' end
'''
    print(run_lua(stubs + sections_block() + LUA_TEST))
    return 0


if __name__ == '__main__':
    sys.exit(main())
