#!/usr/bin/env python3
"""Check the HUD spell labels and Bard song groups against every spell in the database.

`host/addons/lua/control.lua` keeps its spell-label rules in the marked region
(`BEGIN/END HUD label rules`) precisely so this test can run the real Lua code without
loading the game host.  Every named spell must get a short, non-empty label, and two
different lines must not read the same (Aero II and Aeroga II both used to show
"AERO2").  A Bard song carries its rank on the icon badge and its family name on the
tile, so a song's uniqueness key is label + rank; "Foe Requiem" and "Foe Requiem II"
may both read REQUIEM.  The test also requires every skill-40 song to have a group
and a colour, and checks the effect-section split.

The test needs a Lua interpreter.  It uses lupa when installed, otherwise a built
LuaJIT from `build/third_party/luajit-src/src/luajit`; with neither it skips (exit 0).
Set SPELL_NAMES_TEST_LUAJIT=1 to force the LuaJIT path.  Run it directly or through
`scripts/test.sh`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'
SPELLS = ROOT / 'database' / 'migrations' / '0058_spells.sql'
BEGIN = '-- BEGIN HUD label rules'
END = '-- END HUD label rules'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'


def spell_rows() -> list[tuple[str, int]]:
    """(display name, skill id) for every spell row, with '' unescaped."""
    rows: list[tuple[str, int]] = []
    pattern = re.compile(
        r"VALUES \(\d+,'((?:[^']|'')*)',(\d+),(\d+),(\d+),(-?\d+),([0-9.]+),(\d+),(\d+),(\d+)\)"
    )
    for line in SPELLS.read_text(encoding='utf-8').splitlines():
        match = pattern.search(line)
        if match:
            rows.append((match.group(1).replace("''", "'"), int(match.group(7))))
    return rows


def spell_names() -> list[str]:
    """The display names from the spell migration, in one case and with '' unescaped."""
    return [name for name, _skill in spell_rows()]


def song_names() -> list[str]:
    """The bard songs: skill 40 is Singing in the spell migration."""
    return [name for name, skill in spell_rows() if skill == 40]


def label_block() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(BEGIN)
        end = source.index(END) + len(END)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing the spell-label markers: {error}')
    return source[start:end]


def lua_source(names: list[str], songs: list[str]) -> str:
    table = ',\n'.join('  ' + json.dumps(name) for name in names)
    song_table = ',\n'.join('  ' + json.dumps(name) for name in songs)
    return label_block() + f'''

local names = {{
{table}
}}

local songs = {{
{song_table}
}}

local seen, bad = {{}}, {{}}
local longest = ''
for _, name in ipairs(names) do
  local short, tiny, base, roman, tier = hud_spell_parts(name, true)
  if type(short) ~= 'string' or short == '' then
    bad[#bad + 1] = name .. ': empty label'
  elseif #short > 7 then
    bad[#bad + 1] = name .. ': label too long (' .. short .. ')'
  end
  if type(tiny) ~= 'string' or tiny == '' or #tiny > 4 then
    bad[#bad + 1] = name .. ': bad tiny label'
  end
  if #short > #longest then longest = short end
  -- A song rank is drawn as a badge, not in the label, so uniqueness is label + rank.  Every
  -- other spell keeps the rank in its label and has tier ~= nil only for its line art.
  local key = short .. '|' .. tostring(tier or '')
  local other = seen[key]
  if other and other ~= name then
    local shown = tier and (short .. ' ' .. tostring(tier)) or short
    bad[#bad + 1] = other .. ' and ' .. name .. ' both read ' .. shown
  end
  seen[key] = name
end

-- Every bard song has a group and a label, or the page falls back to the old consonant soup
-- for that tile.
for _, name in ipairs(songs) do
  local info = HUD_SHORT.song_info(name)
  if not info then
    bad[#bad + 1] = name .. ': no song group or label'
  else
    if type(info.role.title) ~= 'string' or info.role.title == '' then
      bad[#bad + 1] = name .. ': song group has no title'
    end
    local c = info.role.color
    if type(c) ~= 'table' or #c ~= 3 then
      bad[#bad + 1] = name .. ': song group has no RGB colour'
    end
    if type(info.family.role) ~= 'string' or info.family.role == '' then
      bad[#bad + 1] = name .. ': song family has no group'
    end
  end
end

local function role_of(name, want)
  local info = HUD_SHORT.song_info(name)
  local got = info and info.role.title or 'nil'
  if got ~= want then
    bad[#bad + 1] = name .. ': group ' .. got .. ', want ' .. want
  end
end
role_of('Valor Minuet', 'Attack')
role_of('Armys Paeon', 'Recovery')
role_of('Fire Carol II', 'Magic Defense')
role_of('Pining Nocturne', 'Control')
role_of('Foe Requiem', 'Damage')
role_of('Jesters Operetta', 'Support')
role_of("Knight's Minne", 'Defense')
role_of("Maiden's Virelai", 'Control')
role_of('Honor March', 'Haste')
role_of('Aria of Passion', 'Attack')
role_of('Protected Aria', 'Defense')

local sections = HUD_SHORT.song_sections({{
  {{ name = 'Valor Minuet' }}, {{ name = 'Armys Paeon' }},
  {{ name = 'Armys Paeon II' }}, {{ name = 'Protect' }},
}})
if not sections or #sections ~= 3 then
  bad[#bad + 1] = 'song sections: want Attack, Recovery, Other'
else
  if sections[1].title ~= 'Attack' or sections[1].hint ~= 'Minuet, Mambo' then
    bad[#bad + 1] = 'song sections: Minuet should lead the Attack group'
  end
  if sections[2].title ~= 'Recovery' or #sections[2].items ~= 2 then
    bad[#bad + 1] = 'song sections: Recovery should hold both Paeon ranks'
  end
  if sections[3].title ~= 'Other' then
    bad[#bad + 1] = 'song sections: Protect should fall into Other'
  end
end

local instrument = HUD_SHORT.song_sections({{
  {{ name = 'Honor March' }}, {{ name = 'Aria of Passion' }},
  {{ name = 'Advancing March' }}, {{ name = 'Valor Minuet' }},
}})
if not instrument or #instrument ~= 2
    or instrument[1].title ~= 'Haste' or #instrument[1].items ~= 2
    or instrument[2].title ~= 'Attack' or #instrument[2].items ~= 2 then
  bad[#bad + 1] = 'song sections: Honor March should join Haste and Aria of Passion should join Attack'
end

local debuffs = HUD_SHORT.song_sections({{
  {{ name = 'Foe Requiem' }}, {{ name = 'Foe Lullaby' }}, {{ name = 'Magic Finale' }},
}})
if not debuffs or #debuffs ~= 2 or debuffs[1].title ~= 'Damage'
    or debuffs[2].title ~= 'Control' then
  bad[#bad + 1] = 'song sections: Requiem (Damage) should precede Lullaby/Finale (Control)'
end

-- All songs together are the twelve effect groups: eight buff groups and four debuff groups.
local all, all_sections = {{}}, nil
for _, name in ipairs(songs) do all[#all + 1] = {{ name = name }} end
all_sections = HUD_SHORT.song_sections(all)
if not all_sections or #all_sections ~= 12 then
  bad[#bad + 1] = 'song sections: want 12 effect groups for every song'
else
  for _, section in ipairs(all_sections) do
    if section.title == 'Other' then
      bad[#bad + 1] = 'song sections: a song fell into Other'
    end
    if #section.items == 0 then
      bad[#bad + 1] = 'song sections: ' .. section.title .. ' is empty'
    end
  end
end

local function want(name, flag, short, base, roman, tier)
  local got, _, got_base, got_roman, got_tier = hud_spell_parts(name, flag)
  if got ~= short or got_base ~= base or got_roman ~= roman or got_tier ~= tier then
    bad[#bad + 1] = string.format(
      '%s -> %s / %s / %s / %s, want %s / %s / %s / %s',
      name, got, tostring(got_base), tostring(got_roman), tostring(got_tier),
      short, tostring(base), tostring(roman), tostring(tier))
  end
end

-- The two lines that shared AERO2 in the spell window.
want('Aero II', true, 'AERO2', 'Aero', 'II', 2)
want('Aeroga II', true, 'AEROG2', 'Aeroga', 'II', 2)
want('Blizzard II', true, 'BLIZZ2', 'Blizzard', 'II', 2)
want('Blizzaga II', true, 'BLIZG2', 'Blizzaga', 'II', 2)
want('Blizzard', true, 'BLIZZ', nil, nil, nil)
want('Blizzaga', true, 'BLIZG', nil, nil, nil)
want('Blizzara', true, 'BLIZR', nil, nil, nil)
want('Blizzaja', true, 'BLIZJ', nil, nil, nil)
want('Watera', true, 'WATR', nil, nil, nil)
want('Watera II', true, 'WATR2', 'Watera', 'II', 2)
want('Curaga II', true, 'CURAG2', 'Curaga', 'II', 2)
want('Cura II', true, 'CURA2', 'Cura', 'II', 2)
want('Sleepga II', true, 'SLEPG2', 'Sleepga', 'II', 2)
want('Magic Finale', true, 'FINALE', nil, nil, nil)
want('Magic Fruit', true, 'MGFRT', nil, nil, nil)
want('Foe Requiem II', true, 'REQUIEM', 'Foe Requiem', 'II', 2)
want('Lightning Carol II', true, 'LTNG C', 'Lightning Carol', 'II', 2)
want('Light Carol II', true, 'LIGHT C', 'Light Carol', 'II', 2)
want('Knights Minne IV', true, 'MINNE', 'Knights Minne', 'IV', 4)
want('Armys Paeon VIII', true, 'PAEON', 'Armys Paeon', 'VIII', 8)
want('Mages Ballad III', true, 'BALLAD', 'Mages Ballad', 'III', 3)
want('Valor Minuet V', true, 'MINUET', 'Valor Minuet', 'V', 5)
want('Fire Threnody II', true, 'FIRE T', 'Fire Threnody', 'II', 2)
want('Horde Lullaby II', true, 'HORDE', 'Horde Lullaby', 'II', 2)
want("Knight's Minne II", true, 'MINNE', "Knight's Minne", 'II', 2)
want("Army's Paeon IV", true, 'PAEON', "Army's Paeon", 'IV', 4)
want("Mage's Ballad III", true, 'BALLAD', "Mage's Ballad", 'III', 3)
want('Advancing March', true, 'ADVANCE', nil, nil, nil)
want('Sword Madrigal', true, 'SWORD', nil, nil, nil)
want('Hunters Prelude', true, 'HUNTER', nil, nil, nil)
want('Chocobo Mazurka', true, 'CHOCOBO', nil, nil, nil)
want('Honor March', true, 'HONOR', nil, nil, nil)
want('Aria of Passion', true, 'PASSION', nil, nil, nil)
want('Protected Aria', true, 'PROTECT', nil, nil, nil)
want('Sinewy Etude', true, 'STR', nil, nil, nil)
want('Herculean Etude', true, 'STR+', nil, nil, nil)
want('Vivacious Etude', true, 'VIT', nil, nil, nil)
want('Bewitching Etude', true, 'CHR+', nil, nil, nil)
want('Katon Ichi', true, 'KATON1', nil, nil, nil)
want('Utsusemi: Ni', true, 'UTSU2', nil, nil, nil)
want('Teleport-mea', true, 'T-MEA', nil, nil, nil)
want('Barblizzard', true, 'BARB', nil, nil, nil)
want('Barblind', true, 'BARBL', nil, nil, nil)
want('Geo-attunement', true, 'GEOATTU', nil, nil, nil)
want('Absorb-attri', true, 'ABSATT', nil, nil, nil)
want('Gain-MND', true, 'G-MND', nil, nil, nil)
want('Reraise IV', true, 'RERAI4', 'Reraise', 'IV', 4)
want('Sandstorm II', true, 'SSTRM2', 'Sandstorm', 'II', 2)
want('Silencega', true, 'SILNG', nil, nil, nil)
want('Dispelga', true, 'DISPG', nil, nil, nil)
want('Hastega', true, 'HASTG', nil, nil, nil)
want('Paralyga', true, 'PARAG', nil, nil, nil)
want('Poisonga', true, 'POISG', nil, nil, nil)
want('Slowga', true, 'SLOWG', nil, nil, nil)
want('Sleepga', true, 'SLEPG', nil, nil, nil)
want('Breakga', true, 'BREAKG', nil, nil, nil)
want('Graviga', true, 'GRAVG', nil, nil, nil)
want('Banishga', true, 'BANIG', nil, nil, nil)
want('Stoneskin', true, 'STNSK', nil, nil, nil)
want('Blaze Spikes', true, 'BLAZS', nil, nil, nil)
want('Shock Spikes', true, 'SHOCS', nil, nil, nil)

-- A Trust is not a spell line: Nashmeira must not become NASHR just because it ends in
-- "ra", and the Unity version must still read differently from the base Trust.
want('Nashmeira', false, 'NASHM', nil, nil, nil)
want('Nashmeira II', false, 'NASHM2', 'Nashmeira', 'II', 2)
want('Elivira', false, 'ELIVI', nil, nil, nil)
want('Sakura', false, 'SAKURA', nil, nil, nil)
want('Aldo (UC)', false, 'ALDOU', nil, nil, nil)
want('Apururu (UC)', false, 'APURU', nil, nil, nil)
want('Excenmille [S]', false, 'EXCES', nil, nil, nil)
want('I. Shield (UC)', false, 'IS', nil, nil, nil)
want('Yoran-Oran (UC)', false, 'YORAO', nil, nil, nil)
want('Arciela II', false, 'ARCIE2', 'Arciela', 'II', 2)

if #bad > 0 then
  error(string.format('%d label problem(s):\\n%s', #bad, table.concat(bad, '\\n')))
end
return 'OK: ' .. #names .. ' spell names, longest label ' .. longest
'''


def run_lua(script: str) -> str:
    lupa = None
    if os.environ.get('SPELL_NAMES_TEST_LUAJIT') != '1':
        try:
            import lupa  # noqa: F401  (the module, so the test can also force LuaJIT)
            from lupa import LuaRuntime  # type: ignore
        except ImportError:
            lupa = None
    if lupa is not None:
        runtime = LuaRuntime(unpack_returned_tuples=True)
        return str(runtime.execute(script))
    if LUAJIT.is_file():
        # The LuaJIT CLI drops a chunk's return value; wrap the test so its return becomes the
        # printed result and an assertion failure still exits non-zero.
        wrapped = ('local ok, result = pcall(function()\n' + script
                   + '\nend)\nif not ok then error(result) end\nprint(result)\n')
        result = subprocess.run(
            [str(LUAJIT), '-'], input=wrapped, text=True, capture_output=True, cwd=ROOT)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()
    return 'SKIP: install lupa or build the vendored LuaJIT to run this test'


def main() -> int:
    names = spell_names()
    songs = song_names()
    if not names:
        raise SystemExit(f'{SPELLS}: no spell names found')
    if not songs:
        raise SystemExit(f'{SPELLS}: no bard songs found (skill 40)')
    message = run_lua(lua_source(names, songs))
    print(message)
    return 0


if __name__ == '__main__':
    sys.exit(main())
