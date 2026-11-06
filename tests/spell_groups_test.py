#!/usr/bin/env python3
"""Check the spell mode groups in the host and the launcher against the spell table.

`host/addons/lua/control.lua` keeps its group table and classifier in the marked region
(`BEGIN/END spell mode groups`) so this test can run the real Lua code without loading the
game host.  `launcher-rs/src/lib/phase.ts` repeats the same group, mode, kind and category
keys for the Spells panel, so the test compares the two lists and fails if either side grows
a group, mode or kind the other lacks.

Enfeebling Magic is split by what each spell actually reads (BG Wiki's Community Red Mage
Guide): Skill (Frazzle III, Distract III, Poison), Macc (Frazzle II, Dia, Sleep, Bind...),
Duration (Sleep, Bind, Break, Silence), MND (Slow II, Paralyze II, Addle II), INT (Blind II),
Macc + potency (Gravity) and non-scaling (Dispel, Inundation).  The test pins that split, the
Auto plan rule (a spell's own kind, a forced mode wins, Duration falls back to Macc) and the
`gearswap/RDM.lua` sets each kind binds to by name.  Enhancing Magic has the same
per-spell split now: Skill (Aquaveil), Stoneskin, Duration (Barspell, Blink, Haste,
Haste II, Flurry, Flurry II) and General, with Composure selecting the self duration
set while it is up; the Community Paladin Guide adds Phalanx and Reprisal as their own
kinds.  Divine Magic splits as well: Banish and Holy read Magic Attack, Flash reads
enmity (the Paladin guide's Flash build) and Repose reads landing, so Auto is the
default there and `gearswap/PLD.lua` carries one set per kind.  Enlight / Enlight II
stay in Enspells even though their skill is Divine Magic.

The group classifier also has to stay faithful to the spell table: every skill-37 spell in
`database/migrations/0058_spells.sql` is Dark Magic and must land in the `dark` group, and
every skill-32 spell is Divine Magic and must land in `divine`.  The two exceptions are the
self-enspells: Endark / Endark II and Enlight / Enlight II stay with Enfire in `enspells`.
A helix keeps winning over its skill because a helix is also an Elemental Magic spell.

The test needs a Lua interpreter.  It uses lupa when installed, otherwise a built LuaJIT from
`build/third_party/luajit-src/src/luajit`; with neither it skips (exit 0).  Set
SPELL_GROUPS_TEST_LUAJIT=1 to force the LuaJIT path.  Run it directly or through
`scripts/test.sh`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'
PHASE = ROOT / 'launcher-rs' / 'src' / 'lib' / 'phase.ts'
SPELLS = ROOT / 'database' / 'migrations' / '0058_spells.sql'
RDM = ROOT / 'gearswap' / 'RDM.lua'
BEGIN = '-- BEGIN spell mode groups'
END = '-- END spell mode groups'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'

# skill id -> (group key, spells that stay in Enspells because they are self-enspells).
SKILL_GROUPS = {
    37: ('dark', {'endark', 'endark ii'}),
    32: ('divine', {'enlight', 'enlight ii'}),
}
# group key -> (default mode, mode categories in card order, kind categories in card order).
EXPECTED_GROUPS = {
    'enfeebles': (
        'auto',
        ['enfeebles_skill', 'enfeebles_macc', 'enfeebles_duration', 'enfeebles_hybrid',
         'enfeebles_mnd', 'enfeebles_int', 'enfeebles_general'],
        ['enfeebles_skill', 'enfeebles_macc', 'enfeebles_duration', 'enfeebles_hybrid',
         'enfeebles_mnd', 'enfeebles_int', 'enfeebles_general'],
    ),
    'enhancing': (
        'auto',
        ['enhancing_skill', 'enhancing_stoneskin', 'enhancing_duration',
         'enhancing_general'],
        ['enhancing_skill', 'enhancing_stoneskin', 'enhancing_phalanx',
         'enhancing_reprisal', 'enhancing_duration', 'enhancing_general'],
    ),
    'enspells': ('damage', ['enspells', 'enspells_no_damage'], []),
    'dark': ('potency', ['dark_potency', 'dark_macc', 'dark_duration'], []),
    'divine': ('auto', ['divine_mab', 'divine_flash', 'divine_macc'],
               ['divine_mab', 'divine_flash', 'divine_macc']),
}
# group key -> the automatic (buff-conditional) rows, in table order.
EXPECTED_AUTOS = {
    'enfeebles': ['enfeebles_saboteur'],
    'enhancing': ['enhancing_duration_self'],
    'nuking': ['nuke_mb', 'nuke_immanence'],
    'helix': ['helix_immanence'],
}
# category (or category prefix) -> the conventional library set the launcher fills it from.
FALLBACKS = {
    'enfeebles_skill': 'midcast.Enfeebling Magic Skill',
    'enfeebles_macc': 'midcast.Enfeebling Magic Macc',
    'enfeebles_duration': 'midcast.Enfeebling Magic Duration',
    'enfeebles_hybrid': 'midcast.Enfeebling Magic Hybrid',
    'enfeebles_mnd': 'midcast.Enfeebling Magic MND',
    'enfeebles_int': 'midcast.Enfeebling Magic INT',
    'enfeebles_general': 'midcast.Enfeebling Magic General',
    'enfeebles_saboteur': 'midcast.Enfeebling Magic Saboteur',
    'enhancing_skill': 'midcast.Enhancing Magic SIRD',
    'enhancing_stoneskin': 'midcast.Enhancing Magic Stoneskin',
    'enhancing_phalanx': 'midcast.Phalanx',
    'enhancing_reprisal': 'midcast.Reprisal',
    'enhancing_duration': 'midcast.EnhancingDurationOthers',
    'enhancing_duration_self': 'midcast.EnhancingDuration',
    'enhancing_general': 'midcast.Enhancing Magic',
    'enspells_no_damage': 'midcast.EnspellNoDmg',
    'dark_': 'midcast.Dark Magic',
    'divine_flash': 'midcast.Flash',
    'divine_': 'midcast.Divine Magic',
}
# The enfeebling kind sets in gearswap/RDM.lua, and one piece that pins each build.
KIND_SETS = {
    'midcast.Enfeebling Magic Skill': 'Contemplator +1',
    'midcast.Enfeebling Magic Macc': 'Luminary Sash',
    'midcast.Enfeebling Magic Duration': 'Atrophy Tabard +4',
    'midcast.Enfeebling Magic Hybrid': 'Regal Gem',
    'midcast.Enfeebling Magic MND': 'Chironic Hose',
    'midcast.Enfeebling Magic INT': 'Marin Staff +1',
    'midcast.Enfeebling Magic General': 'Per. Lucky Egg',
}
EXTRA_SETS = ('midcast.EnhancingDuration', 'midcast.EnhancingDurationOthers',
              'midcast.Enhancing Magic Stoneskin', 'midcast.Enhancing Magic SIRD')
# The Paladin spell sets in gearswap/PLD.lua, and one piece that pins each build.  The
# divine/enhancing kinds above bind these by name; the SIRD variants are extra leaves the
# same row can be repointed at.
PLD = ROOT / 'gearswap' / 'PLD.lua'
PLD_SETS = {
    'midcast.Divine Magic': 'Pemphredo Tathlum',
    'midcast.Flash': "Loess Barbuta +1",
    'midcast.Flash SIRD': 'Souv. Schaller +1',
    'midcast.Enspell': 'Brilliance',
    'midcast.Healing Magic': "Egoist's Tathlum",
    'midcast.Cure SIRD': 'Macabre Gaunt. +1',
    'midcast.Enhancing Magic': 'Ajax +1',
    'midcast.Enhancing Magic SIRD': 'Eschite Breast.',
    'midcast.Enhancing Magic Stoneskin': 'Stone Gorget',
    'midcast.Phalanx': 'Hoxne Torque',
    'midcast.Phalanx SIRD': 'Founder\'s Hose',
    'midcast.Reprisal': 'Regal Gauntlets',
    'midcast.Reprisal SIRD': 'Shab. Cuirass +1',
}
# The Oseem-augmented Odyssean builds the sets reference, and one augment line that pins
# each roll (the guide's Phalanx / SIRD rolls are Dark Matter technique augments, the
# Cure Potency / Fast Cast rows are the standard stone ones).
OSEEM_SETS = {
    'helm_phalanx': ('Odyssean Helm', '"Phalanx"+5'),
    'chest_phalanx': ('Odyss. Chestplate', '"Phalanx"+5'),
    'feet_phalanx': ('Odyssean Greaves', '"Phalanx"+5'),
    'feet_cure': ('Odyssean Greaves', '"Cure Potency"+5%'),
    'feet_fastcast': ('Odyssean Greaves', '"Fast Cast"+6'),
    'feet_stoneskin': ('Odyssean Greaves', 'Spell interruption rate down-11%'),
}
# The set slots that must point at the oseem table instead of a bare item name.
OSEEM_REFS = {
    'midcast.Phalanx': {'head': 'oseem.helm_phalanx'},
    'midcast.Phalanx SIRD': {
        'body': 'oseem.chest_phalanx', 'feet': 'oseem.feet_phalanx'},
    'midcast.Enhancing Magic Stoneskin': {'feet': 'oseem.feet_stoneskin'},
    'midcast.Cure SIRD': {'feet': 'oseem.feet_cure'},
    'midcast.Reprisal SIRD': {'feet': 'oseem.feet_fastcast'},
}


def groups_block() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(BEGIN)
        end = source.index(END) + len(END)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing the spell-mode-group markers: {error}')
    return source[start:end]


def spells_with_skill(skill: int) -> list[str]:
    """The display names of every spell row whose skill column is `skill`."""
    pattern = re.compile(
        r"VALUES \((\d+),'((?:[^']|'')*)',([^,]+),([^,]+),([^,]+),([^,]+),([^,]+),(\d+),"
    )
    names: list[str] = []
    for line in SPELLS.read_text(encoding='utf-8').splitlines():
        match = pattern.search(line)
        if match and int(match.group(8)) == skill:
            names.append(match.group(2).replace("''", "'"))
    return names


def launcher_groups() -> list[dict]:
    """The group keys, defaults, mode categories and kind categories `phase.ts` declares.

    Each group object is `    key: "..."`, then `    defaultMode: "..."`, then the
    `    modes: [` array and, for Enfeebles, a `    kinds: [` array.  The arrays hold
    `category: "..."` lines in card order; a mode without a category (Auto) is skipped.
    The automatic rows (`autoMode`/`autoModes`, the Nuking Magic Burst and Immanence) are
    collected separately so the host's `group.auto`/`group.autos` can be compared too.
    """
    source = PHASE.read_text(encoding='utf-8')
    try:
        start = source.index('export const SPELL_GROUPS')
        end = source.index('\n];', start)
    except ValueError as error:
        raise SystemExit(f'{PHASE}: cannot find SPELL_GROUPS: {error}')
    out: list[dict] = []
    current: dict | None = None
    section = 'modes'
    for line in source[start:end].splitlines():
        key = re.match(r'^    key: "([^"]+)"', line)
        if key:
            current = {'key': key.group(1), 'default': '', 'modes': [], 'kinds': [],
                       'autos': []}
            out.append(current)
            section = 'modes'
            continue
        if current is None:
            continue
        if re.match(r'^    modes: \[', line):
            section = 'modes'
            continue
        if re.match(r'^    kinds: \[', line):
            section = 'kinds'
            continue
        if re.match(r'^    autoModes?: ', line):
            section = 'autos'
            continue
        default = re.match(r'^    defaultMode: "([^"]+)"', line)
        if default:
            current['default'] = default.group(1)
            continue
        category = re.search(r'category: "([^"]+)"', line)
        if category:
            current[section].append(category.group(1))
    return out


def lua_quote(text: str) -> str:
    return "'" + text.replace('\\', '\\\\').replace("'", "\\'") + "'"


def lua_script(cases: list[tuple[int, str, set[str], list[str]]]) -> str:
    tables = []
    for skill, group, enspells, names in cases:
        name_list = ',\n'.join('      ' + lua_quote(name) for name in names)
        enspell_list = ', '.join(f'[{lua_quote(name)}] = true' for name in sorted(enspells))
        tables.append(f'''  {{
    skill = {skill}, group = {lua_quote(group)},
    enspells = {{ {enspell_list} }},
    names = {{
{name_list}
    }},
  }},''')
    case_table = '\n'.join(tables)
    return groups_block() + f'''

local cases = {{
{case_table}
}}

local function find_mode(group, mode_key)
  for _, mode in ipairs(group.modes) do
    if mode.key == mode_key then return mode end
  end
  return nil
end

-- The armed mode of every group must exist, the group key must match its slot, and no two
-- groups may claim the same category: the plan gives a spell exactly one rule.  A mode and a
-- kind may share a category inside one group on purpose (the Mode dropdown forces the set the
-- kind row already owns for Enfeebles).
local owner = {{}}
for _, group_key in ipairs(SPELL_GROUP_ORDER) do
  local group = SPELL_GROUPS[group_key]
  if not group then error('missing group ' .. group_key, 0) end
  if group.key ~= group_key then
    error('group slot ' .. group_key .. ' holds ' .. tostring(group.key), 0)
  end
  if #group.modes == 0 then error('group ' .. group_key .. ' has no modes', 0) end
  if not find_mode(group, group.default) then
    error('group ' .. group_key .. ' default is not one of its modes', 0)
  end
  local seen_mode = {{}}
  for _, mode in ipairs(group.modes) do
    if mode.category then
      if seen_mode[mode.category] then
        error('mode category ' .. mode.category .. ' claimed twice in ' .. group_key, 0)
      end
      seen_mode[mode.category] = true
      if owner[mode.category] and owner[mode.category] ~= group_key then
        error('category ' .. mode.category .. ' claimed by ' .. owner[mode.category] ..
          ' and ' .. group_key, 0)
      end
      owner[mode.category] = group_key
    end
  end
  local seen_kind = {{}}
  for _, kind in ipairs(group.kinds or {{}}) do
    if seen_kind[kind.category] then
      error('kind category ' .. kind.category .. ' claimed twice in ' .. group_key, 0)
    end
    seen_kind[kind.category] = true
    if owner[kind.category] and owner[kind.category] ~= group_key then
      error('category ' .. kind.category .. ' claimed by ' .. owner[kind.category] ..
        ' and ' .. group_key, 0)
    end
    owner[kind.category] = group_key
  end
  -- Automatic rows own a category too: the Nuking card's Magic Burst window and every
  -- buff-conditional row (Immanence, Saboteur).
  if group.auto then
    if owner[group.auto.category] and owner[group.auto.category] ~= group_key then
      error('category ' .. group.auto.category .. ' claimed twice', 0)
    end
    owner[group.auto.category] = group_key
  end
  for _, auto in ipairs(group.autos or {{}}) do
    if owner[auto.category] and owner[auto.category] ~= group_key then
      error('category ' .. auto.category .. ' claimed twice', 0)
    end
    owner[auto.category] = group_key
  end
end

-- Every spell of the skill is in the skill's group, except the self-enspells.
for _, case in ipairs(cases) do
  for _, name in ipairs(case.names) do
    local want = case.enspells[name:lower()] and 'enspells' or case.group
    local got = spell_group({{ name = name, skill = case.skill }})
    if got ~= want then
      error(string.format('%s (skill %d) -> %s, want %s',
        name, case.skill, tostring(got), want), 0)
    end
  end
end

-- Adding the skill branches must not move the older groups.
local stays = {{
  {{ 'Sleep II', 35, 'enfeebles' }},
  {{ 'Haste', 34, 'enhancing' }},
  {{ 'Enfire', 34, 'enspells' }},
  {{ 'Enblizzard II', 34, 'enspells' }},
  {{ 'Curaga', 33, 'curing' }},
  {{ 'Fire', 36, 'nuking' }},
  {{ 'Pyrohelix', 36, 'helix' }},
  {{ 'Noctohelix', 37, 'helix' }},
  {{ "Mage's Ballad", 40, 'songs' }},
}}
for _, row in ipairs(stays) do
  local got = spell_group({{ name = row[1], skill = row[2] }})
  if got ~= row[3] then
    error(string.format('%s (skill %d) -> %s, want %s',
      row[1], row[2], tostring(got), row[3]), 0)
  end
end
if spell_group({{ name = 'Summoner Spell', skill = 38 }}) ~= nil then
  error('an unclassified skill gained a group', 0)
end
if spell_group(nil) ~= nil then error('a nil spell gained a group', 0) end

-- Enfeebling kinds: the BG Wiki Community Red Mage Guide split.
local kind_cases = {{
  {{ 'Frazzle III', 'skill' }}, {{ 'Distract III', 'skill' }},
  {{ 'Poison', 'skill' }}, {{ 'Poison II', 'skill' }},
  {{ 'Frazzle', 'macc' }}, {{ 'Frazzle II', 'macc' }},
  {{ 'Distract II', 'macc' }}, {{ 'Dia III', 'macc' }},
  {{ 'Sleep', 'duration' }}, {{ 'Sleep II', 'duration' }},
  {{ 'Bind', 'duration' }}, {{ 'Break', 'duration' }}, {{ 'Silence', 'duration' }},
  {{ 'Gravity', 'hybrid' }}, {{ 'Gravity II', 'hybrid' }},
  {{ 'Slow II', 'mnd' }}, {{ 'Paralyze II', 'mnd' }}, {{ 'Addle II', 'mnd' }},
  {{ 'Blind II', 'int' }},
  {{ 'Dispel', 'general' }}, {{ 'Inundation', 'general' }},
}}
for _, row in ipairs(kind_cases) do
  local got = spell_enfeebling_kind({{ name = row[1], skill = 35 }})
  if got ~= row[2] then
    error(string.format('%s kind -> %s, want %s', row[1], tostring(got), row[2]), 0)
  end
end
if spell_enfeebling_kind({{ name = 'Virus', skill = 35 }}) ~= 'macc' then
  error('an unlisted enfeebling spell did not fall back to macc', 0)
end
if spell_enfeebling_kind({{ name = 'Cure IV', skill = 33 }}) ~= nil then
  error('a healing spell gained an enfeebling kind', 0)
end
if spell_enfeebling_kind(nil) ~= nil then
  error('a nil spell gained an enfeebling kind', 0)
end

-- Saboteur is a live status (454), not an armed mode, and its set is a merge overlay.
local saboteur = nil
for _, auto in ipairs(SPELL_GROUPS.enfeebles.autos or {{}}) do
  if auto.key == 'saboteur' then saboteur = auto end
end
if not saboteur then error('Enfeebles has no Saboteur auto row', 0) end
if saboteur.category ~= 'enfeebles_saboteur' then
  error('Saboteur category is ' .. tostring(saboteur.category), 0)
end
if tonumber(saboteur.buff) ~= 454 then
  error('Saboteur status id is ' .. tostring(saboteur.buff) .. ', want 454', 0)
end
if not saboteur.merge then error('Saboteur does not merge over the kind set', 0) end

-- job_spells hands the page both the group and the kind category.
local cats = spell_categories({{ name = 'Blind II', skill = 35 }})
if #cats ~= 2 or cats[1] ~= 'enfeebles' or cats[2] ~= 'enfeebles_int' then
  error('Blind II categories: ' .. table.concat(cats, ','), 0)
end
local cure_cats = spell_categories({{ name = 'Cure', skill = 33 }})
if #cure_cats ~= 1 or cure_cats[1] ~= 'curing' then
  error('Cure categories: ' .. table.concat(cure_cats, ','), 0)
end

-- Enhancing kinds: the guide's per-spell split.
local enhancing_cases = {{
  {{ 'Aquaveil', 'skill' }},
  {{ 'Stoneskin', 'stoneskin' }},
  {{ 'Barfire', 'duration' }}, {{ 'Barsleepra', 'duration' }},
  {{ 'Haste', 'duration' }}, {{ 'Haste II', 'duration' }},
  {{ 'Hastega', 'duration' }}, {{ 'Flurry', 'duration' }},
  {{ 'Flurry II', 'duration' }}, {{ 'Blink', 'duration' }},
  {{ 'Protect V', 'general' }}, {{ 'Shell V', 'general' }},
  {{ 'Regen', 'general' }}, {{ 'Refresh', 'general' }},
  {{ 'Temper', 'general' }}, {{ 'Blaze Spikes', 'general' }},
  {{ 'Aurorastorm', 'general' }},
}}
for _, row in ipairs(enhancing_cases) do
  local got = spell_enhancing_kind({{ name = row[1], skill = 34 }})
  if got ~= row[2] then
    error(string.format('%s enhancing kind -> %s, want %s',
      row[1], tostring(got), row[2]), 0)
  end
end
if spell_enhancing_kind({{ name = 'Cure IV', skill = 33 }}) ~= nil then
  error('a healing spell gained an enhancing kind', 0)
end
if spell_enhancing_kind(nil) ~= nil then
  error('a nil spell gained an enhancing kind', 0)
end

-- Composure is a live status (419), scoped to the duration kind.
local composure = nil
for _, auto in ipairs(SPELL_GROUPS.enhancing.autos or {{}}) do
  if auto.key == 'composure' then composure = auto end
end
if not composure then error('Enhancing has no Composure auto row', 0) end
if composure.category ~= 'enhancing_duration_self' then
  error('Composure category is ' .. tostring(composure.category), 0)
end
if tonumber(composure.buff) ~= 419 then
  error('Composure status id is ' .. tostring(composure.buff) .. ', want 419', 0)
end
if composure.only_kind ~= 'duration' then
  error('Composure is not scoped to the duration kind', 0)
end

local enhance_cats = spell_categories({{ name = 'Haste', skill = 34 }})
if #enhance_cats ~= 2 or enhance_cats[1] ~= 'enhancing'
    or enhance_cats[2] ~= 'enhancing_duration' then
  error('Haste categories: ' .. table.concat(enhance_cats, ','), 0)
end
local enhance_all = {{
  enhancing_skill = 'SIRD', enhancing_stoneskin = 'Stone',
  enhancing_duration = 'Duration', enhancing_general = 'General',
}}
local enhance_auto = find_mode(SPELL_GROUPS.enhancing, 'auto')
local enhance_forced = find_mode(SPELL_GROUPS.enhancing, 'stoneskin')
if spell_cast_category('enhancing', {{ name = 'Haste', skill = 34 }},
    enhance_auto, enhance_all) ~= 'enhancing_duration' then
  error('Haste did not pick the duration set', 0)
end
if spell_cast_category('enhancing', {{ name = 'Aquaveil', skill = 34 }},
    enhance_auto, enhance_all) ~= 'enhancing_skill' then
  error('Aquaveil did not pick the SIRD set', 0)
end
if spell_cast_category('enhancing', {{ name = 'Protect V', skill = 34 }},
    enhance_auto, enhance_all) ~= 'enhancing_general' then
  error('Protect did not pick the general set', 0)
end
if spell_cast_category('enhancing', {{ name = 'Aquaveil', skill = 34 }},
    enhance_forced, enhance_all) ~= 'enhancing_stoneskin' then
  error('a forced enhancing mode did not win', 0)
end
if spell_cast_category('enhancing', {{ name = 'Haste', skill = 34 }},
    enhance_auto, {{}}) ~= nil then
  error('an unconfigured enhancing kind did not fall through to the library set', 0)
end

-- Phalanx and Reprisal own Enhancing Magic kinds now (the Paladin guide sets).
local phalanx_cats = spell_categories({{ name = 'Phalanx', skill = 34 }})
if #phalanx_cats ~= 2 or phalanx_cats[2] ~= 'enhancing_phalanx' then
  error('Phalanx categories: ' .. table.concat(phalanx_cats, ','), 0)
end
local phalanx_two = spell_categories({{ name = 'Phalanx II', skill = 34 }})
if #phalanx_two ~= 2 or phalanx_two[2] ~= 'enhancing_phalanx' then
  error('Phalanx II categories: ' .. table.concat(phalanx_two, ','), 0)
end
local reprisal_cats = spell_categories({{ name = 'Reprisal', skill = 34 }})
if #reprisal_cats ~= 2 or reprisal_cats[2] ~= 'enhancing_reprisal' then
  error('Reprisal categories: ' .. table.concat(reprisal_cats, ','), 0)
end
local enhance_pld = {{ enhancing_phalanx = 'Phalanx', enhancing_reprisal = 'Reprisal' }}
if spell_cast_category('enhancing', {{ name = 'Phalanx', skill = 34 }},
    enhance_auto, enhance_pld) ~= 'enhancing_phalanx' then
  error('Phalanx did not pick its own set', 0)
end
if spell_cast_category('enhancing', {{ name = 'Reprisal', skill = 34 }},
    enhance_auto, enhance_pld) ~= 'enhancing_reprisal' then
  error('Reprisal did not pick its own set', 0)
end

-- Divine Magic kinds: Banish/Holy read Magic Attack, Flash enmity, Repose landing.  The
-- self-enspell Enlight stays in Enspells even though its skill is Divine Magic.
local divine_auto = find_mode(SPELL_GROUPS.divine, 'auto')
local divine_all = {{
  divine_mab = 'MAB', divine_flash = 'Flash', divine_macc = 'Macc',
}}
for _, row in ipairs({{
  {{ 'Banish', 'divine_mab' }}, {{ 'Banishga', 'divine_mab' }}, {{ 'Holy', 'divine_mab' }},
  {{ 'Holy II', 'divine_mab' }}, {{ 'Flash', 'divine_flash' }}, {{ 'Repose', 'divine_macc' }},
}}) do
  local got = spell_cast_category('divine', {{ name = row[1], skill = 32 }}, divine_auto,
      divine_all)
  if got ~= row[2] then
    error(string.format('%s auto category -> %s, want %s',
      row[1], tostring(got), row[2]), 0)
  end
  local cats = spell_categories({{ name = row[1], skill = 32 }})
  if #cats ~= 2 or cats[2] ~= row[2] then
    error(row[1] .. ' categories: ' .. table.concat(cats, ','), 0)
  end
end
if spell_cast_category('divine', {{ name = 'Flash', skill = 32 }},
    find_mode(SPELL_GROUPS.divine, 'mab'), divine_all) ~= 'divine_mab' then
  error('a forced divine mode did not win', 0)
end
if spell_cast_category('divine', {{ name = 'Flash', skill = 32 }},
    divine_auto, {{}}) ~= nil then
  error('an unconfigured divine kind did not fall through to the library set', 0)
end
local enlight_cats = spell_categories({{ name = 'Enlight', skill = 32 }})
if #enlight_cats ~= 1 or enlight_cats[1] ~= 'enspells' then
  error('Enlight left Enspells: ' .. table.concat(enlight_cats, ','), 0)
end

-- Enspells has a second armed mode for a no-damage set, and the damage mode stays the
-- default so a saved config without a mode keeps the old build.
local enspell_damage = find_mode(SPELL_GROUPS.enspells, 'damage')
local enspell_none = find_mode(SPELL_GROUPS.enspells, 'nodamage')
if not enspell_damage or not enspell_none then
  error('Enspells is missing one of its two modes', 0)
end
if SPELL_GROUPS.enspells.default ~= 'damage' then
  error('Enspells default is ' .. tostring(SPELL_GROUPS.enspells.default), 0)
end
if enspell_none.category ~= 'enspells_no_damage' then
  error('Enspell no dmg category is ' .. tostring(enspell_none.category), 0)
end
local enspell_override = {{ enspells = 'Dmg', enspells_no_damage = 'NoDmg' }}
if spell_cast_category('enspells', {{ name = 'Enfire', skill = 34 }},
    enspell_none, enspell_override) ~= 'enspells_no_damage' then
  error('the no-damage enspell mode did not pick its own set', 0)
end
if spell_cast_category('enspells', {{ name = 'Enfire', skill = 34 }},
    enspell_damage, enspell_override) ~= 'enspells' then
  error('the damage enspell mode did not pick the damage set', 0)
end

-- Auto follows the spell's own kind; a forced mode wins; Duration falls back to Macc.
local auto = find_mode(SPELL_GROUPS.enfeebles, 'auto')
local forced = find_mode(SPELL_GROUPS.enfeebles, 'mnd')
local all = {{
  enfeebles_skill = 'Skill', enfeebles_macc = 'Macc', enfeebles_duration = 'Duration',
  enfeebles_hybrid = 'Hybrid', enfeebles_mnd = 'MND', enfeebles_int = 'INT',
  enfeebles_general = 'General',
}}
local want = {{
  {{ 'Frazzle III', 'enfeebles_skill' }}, {{ 'Frazzle II', 'enfeebles_macc' }},
  {{ 'Slow II', 'enfeebles_mnd' }}, {{ 'Blind II', 'enfeebles_int' }},
  {{ 'Gravity', 'enfeebles_hybrid' }}, {{ 'Dispel', 'enfeebles_general' }},
  {{ 'Sleep', 'enfeebles_duration' }},
}}
for _, row in ipairs(want) do
  local got = spell_cast_category('enfeebles', {{ name = row[1], skill = 35 }}, auto, all)
  if got ~= row[2] then
    error(string.format('%s auto category -> %s, want %s',
      row[1], tostring(got), row[2]), 0)
  end
end
if spell_cast_category('enfeebles', {{ name = 'Sleep', skill = 35 }}, auto,
    {{ enfeebles_macc = 'Macc' }}) ~= 'enfeebles_macc' then
  error('a duration spell did not fall back to the macc set', 0)
end
if spell_cast_category('enfeebles', {{ name = 'Sleep', skill = 35 }}, auto, {{}}) ~= nil then
  error('an unconfigured enfeebling kind did not fall through to the library set', 0)
end
if spell_cast_category('enfeebles', {{ name = 'Blind II', skill = 35 }}, forced, all)
    ~= 'enfeebles_mnd' then
  error('a forced enfeebling mode did not win', 0)
end
local dark_mode = find_mode(SPELL_GROUPS.dark, 'macc')
if spell_cast_category('dark', {{ name = 'Stun', skill = 37 }}, dark_mode,
    {{ dark_macc = 'Dark Magic' }}) ~= 'dark_macc' then
  error('an ordinary group lost its armed mode', 0)
end

local lines = {{}}
for _, group_key in ipairs(SPELL_GROUP_ORDER) do
  local group = SPELL_GROUPS[group_key]
  local modes, kinds = {{}}, {{}}
  for _, mode in ipairs(group.modes) do
    modes[#modes + 1] = mode.key .. ':' .. tostring(mode.category or '')
  end
  for _, kind in ipairs(group.kinds or {{}}) do
    kinds[#kinds + 1] = kind.key .. ':' .. kind.category
  end
  local autos = {{}}
  if group.auto then autos[#autos + 1] = group.auto.key .. ':' .. group.auto.category end
  for _, auto in ipairs(group.autos or {{}}) do
    autos[#autos + 1] = auto.key .. ':' .. auto.category
  end
  lines[#lines + 1] = group_key .. '|' .. group.default .. '|' ..
    table.concat(modes, ';') .. '|' .. table.concat(kinds, ';') .. '|' ..
    table.concat(autos, ';')
end
return table.concat(lines, '\\n')
'''


def run_lua(script: str) -> str:
    lupa = None
    if os.environ.get('SPELL_GROUPS_TEST_LUAJIT') != '1':
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


def parse_host_layout(lua: str) -> tuple[list[str], dict[str, dict]]:
    host_groups: list[str] = []
    layout: dict[str, dict] = {}
    for line in lua.splitlines():
        line = line.strip()
        if not line or '|' not in line:
            continue
        key, default, modes, kinds, autos = line.split('|')
        mode_categories = [entry.split(':', 1)[1] for entry in modes.split(';')
                           if entry and entry.split(':', 1)[1]]
        kind_categories = [entry.split(':', 1)[1] for entry in kinds.split(';')
                           if entry and entry.split(':', 1)[1]]
        auto_categories = [entry.split(':', 1)[1] for entry in autos.split(';')
                           if entry and entry.split(':', 1)[1]]
        host_groups.append(key)
        layout[key] = {
            'default': default,
            'modes': mode_categories,
            'kinds': kind_categories,
            'autos': auto_categories,
        }
    return host_groups, layout


def check_phase_fallbacks(host_categories: list[str]) -> None:
    source = PHASE.read_text(encoding='utf-8')
    for target, path in FALLBACKS.items():
        if target in host_categories:
            categories = [target]
        else:
            # A prefix sweep skips the categories that have their own exact entry:
            # `divine_` must not re-check `divine_flash` against midcast.Divine Magic.
            categories = [category for category in host_categories
                          if category.startswith(target) and category not in FALLBACKS]
        for category in categories:
            pattern = rf'{re.escape(category)}: \[\s*"{re.escape(path)}"'
            if not re.search(pattern, source):
                raise SystemExit(f'{PHASE}: {category} has no {path} fallback')


def check_group_jobs() -> None:
    """The Paladin's spell groups must be on the Spells panel for a PLD main job."""
    source = PHASE.read_text(encoding='utf-8')
    for group in ('enhancing', 'enspells', 'curing', 'divine'):
        match = re.search(rf'^  {group}: \[([^\]]*)\]', source, re.M)
        if not match:
            raise SystemExit(f'{PHASE}: no SPELL_GROUP_JOBS entry for {group}')
        jobs = {int(value) for value in match.group(1).replace(' ', '').split(',') if value}
        if 7 not in jobs:
            raise SystemExit(f'{PHASE}: PLD (7) is missing from the {group} spell group')


def lua_set_block(source: str, path: str, label: Path = RDM) -> str:
    """The `sets.<group>["<name>"] = { ... }` block for one dotted library path.

    The bracket form is the convention for names with spaces; a dotted `sets.group.name`
    is accepted too (GearSwap reads both, and the launcher flattens them the same way).
    """
    group, _, name = path.partition('.')
    start = -1
    for header in (f'sets.{group}["{name}"] = {{', f'sets.{path} = {{'):
        start = source.find(header)
        if start >= 0:
            break
    if start < 0:
        raise SystemExit(f'{label}: missing {path}')
    open_at = source.index('{', start)
    depth = 0
    for index in range(open_at, len(source)):
        char = source[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return source[open_at:index + 1]
    raise SystemExit(f'{label}: unterminated {path}')


def check_rdm_library() -> None:
    """Every enfeebling kind has its guide build, and the enhancing splits exist."""
    source = RDM.read_text(encoding='utf-8')
    # The host categories map to the library paths the launcher fills them from.
    for path, piece in KIND_SETS.items():
        block = lua_set_block(source, path)
        if piece not in block:
            raise SystemExit(f'{RDM}: {path} is missing {piece}')
        if 'back = capes.' not in block and path != 'midcast.Enfeebling Magic General':
            raise SystemExit(f'{RDM}: {path} has no augmented cape build')
    for path in EXTRA_SETS:
        group, _, name = path.partition('.')
        bracket = f'sets.{group}["{name}"]'
        dotted = f'sets.{path} ='
        if bracket not in source and dotted not in source:
            raise SystemExit(f'{RDM}: missing {path}')
    # The Saboteur auto row binds this one-piece overlay; the plan merges it over the kind set.
    overlay = lua_set_block(source, 'midcast.Enfeebling Magic Saboteur')
    if 'hands = "Lethargy Gantherots +3"' not in overlay:
        raise SystemExit(f'{RDM}: the Saboteur overlay must be the hands only')


def lua_braces(source: str, header: str, label: Path = PLD) -> str:
    """The `{ ... }` table that follows one text `header` (e.g. an oseem entry)."""
    start = source.find(header)
    if start < 0:
        raise SystemExit(f'{label}: missing {header.strip()}')
    open_at = source.index('{', start + len(header) - 1)
    depth = 0
    for index in range(open_at, len(source)):
        char = source[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return source[open_at:index + 1]
    raise SystemExit(f'{label}: unterminated {header.strip()}')


def check_pld_library() -> None:
    """The Paladin library carries one guide build per divine/enhancing kind."""
    source = PLD.read_text(encoding='utf-8')
    for path, piece in PLD_SETS.items():
        block = lua_set_block(source, path, PLD)
        if piece not in block:
            raise SystemExit(f'{PLD}: {path} is missing {piece}')
    # The Odyssean pieces are Oseem's Arcane Glyptics work: the local table carries the
    # guide's roll line and the set slot points at that entry, not at a bare item name.
    for key, (item, augment) in OSEEM_SETS.items():
        entry = lua_braces(source, f'{key} = ')
        if item not in entry or augment not in entry:
            raise SystemExit(f'{PLD}: oseem.{key} is not {item} with {augment}')
    for path, slots in OSEEM_REFS.items():
        block = lua_set_block(source, path, PLD)
        for slot, reference in slots.items():
            if not re.search(rf'^\s*{slot} = {re.escape(reference)},', block, re.M):
                raise SystemExit(f'{PLD}: {path} {slot} is not {reference}')


def main() -> int:
    cases = []
    for skill, (group, enspells) in SKILL_GROUPS.items():
        names = spells_with_skill(skill)
        if not names:
            raise SystemExit(f'{SPELLS}: no skill-{skill} spells found')
        cases.append((skill, group, enspells, names))
    lua = run_lua(lua_script(cases))
    if lua.startswith('SKIP:'):
        print(lua)
        return 0
    host_groups, host_layout = parse_host_layout(lua)
    launcher = launcher_groups()
    if host_groups != [group['key'] for group in launcher]:
        raise SystemExit(f'group order differs:\n  host:     {host_groups}\n'
                         f'  launcher: {[group["key"] for group in launcher]}')
    for group in launcher:
        host = host_layout[group['key']]
        if host['default'] != group['default']:
            raise SystemExit(f'{group["key"]} default is {host["default"]}, '
                             f'want {group["default"]}')
        if host['modes'] != group['modes']:
            raise SystemExit(f'{group["key"]} mode categories differ:\n'
                             f'  host:     {host["modes"]}\n  launcher: {group["modes"]}')
        if host['kinds'] != group['kinds']:
            raise SystemExit(f'{group["key"]} kind categories differ:\n'
                             f'  host:     {host["kinds"]}\n  launcher: {group["kinds"]}')
        if host['autos'] != group['autos']:
            raise SystemExit(f'{group["key"]} automatic categories differ:\n'
                             f'  host:     {host["autos"]}\n  launcher: {group["autos"]}')
    for group_key, expected in EXPECTED_GROUPS.items():
        got = host_layout.get(group_key) or {}
        if (got.get('default'), got.get('modes'), got.get('kinds')) != expected:
            raise SystemExit(f'{group_key} layout is {got}, want {expected}')
    for group_key, expected in EXPECTED_AUTOS.items():
        got = host_layout.get(group_key, {}).get('autos')
        if got != expected:
            raise SystemExit(f'{group_key} automatic categories are {got}, want {expected}')
    host_categories = [category for entry in host_layout.values()
                       for category in entry['modes'] + entry['kinds']]
    check_phase_fallbacks(host_categories)
    check_group_jobs()
    check_rdm_library()
    check_pld_library()
    counts = []
    for _skill, group, enspells, names in cases:
        classified = sum(1 for name in names if name.casefold() not in enspells)
        counts.append(f'{group} {classified}')
    print(f"OK: {len(host_groups)} spell mode groups; {len(host_layout['enfeebles']['kinds'])} "
          f"enfeebling kinds; {len(host_layout['enhancing']['kinds'])} enhancing kinds; "
          f"{len(host_layout['divine']['kinds'])} divine kinds; "
          f"classified {', '.join(counts)} (self-enspells stay in Enspells)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
