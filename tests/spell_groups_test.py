#!/usr/bin/env python3
"""Check the spell mode groups in the host and the launcher against the spell table.

`host/addons/lua/control.lua` keeps its group table and classifier in the marked region
(`BEGIN/END spell mode groups`) so this test can run the real Lua code without loading the
game host.  `launcher-rs/src/lib/phase.ts` repeats the same group, mode and category keys for
the Spells panel, so the test compares the two lists and fails if either side grows a group
the other lacks.

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
BEGIN = '-- BEGIN spell mode groups'
END = '-- END spell mode groups'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'

# skill id -> (group key, spells that stay in Enspells because they are self-enspells).
SKILL_GROUPS = {
    37: ('dark', {'endark', 'endark ii'}),
    32: ('divine', {'enlight', 'enlight ii'}),
}
# group key -> (default mode, the group's categories in card order).
EXPECTED_GROUPS = {
    'dark': ('potency', ['dark_potency', 'dark_macc', 'dark_duration']),
    'divine': ('mab', ['divine_mab', 'divine_macc']),
}
# category prefix -> the conventional library set the launcher fills it from.
FALLBACKS = {'dark_': 'midcast.Dark Magic', 'divine_': 'midcast.Divine Magic'}


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


def launcher_groups() -> tuple[list[str], list[str]]:
    """The group keys and the flattened mode/category keys `phase.ts` declares, in order."""
    source = PHASE.read_text(encoding='utf-8')
    try:
        start = source.index('export const SPELL_GROUPS')
        end = source.index('\n];', start)
    except ValueError as error:
        raise SystemExit(f'{PHASE}: cannot find SPELL_GROUPS: {error}')
    block = source[start:end]
    keys = re.findall(r'^    key: "([^"]+)"', block, re.MULTILINE)
    categories = re.findall(r'category: "([^"]+)"', block)
    return keys, categories


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

-- The armed mode of every group must exist, the group key must match its slot, and no two
-- groups may claim the same category: the plan gives a spell exactly one rule.
local seen = {{}}
for _, group_key in ipairs(SPELL_GROUP_ORDER) do
  local group = SPELL_GROUPS[group_key]
  if not group then error('missing group ' .. group_key, 0) end
  if group.key ~= group_key then
    error('group slot ' .. group_key .. ' holds ' .. tostring(group.key), 0)
  end
  local default = false
  if #group.modes == 0 then error('group ' .. group_key .. ' has no modes', 0) end
  for _, mode in ipairs(group.modes) do
    if mode.key == group.default then default = true end
    if seen[mode.category] then
      error('category ' .. mode.category .. ' claimed twice', 0)
    end
    seen[mode.category] = group_key
  end
  -- The Nuking card's Magic Burst row is not an armed mode but it owns a category too.
  if group.auto then
    if seen[group.auto.category] then
      error('category ' .. group.auto.category .. ' claimed twice', 0)
    end
    seen[group.auto.category] = group_key
  end
  if not default then
    error('group ' .. group_key .. ' default is not one of its modes', 0)
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

local lines = {{}}
for _, group_key in ipairs(SPELL_GROUP_ORDER) do
  local group = SPELL_GROUPS[group_key]
  local modes = {{}}
  for _, mode in ipairs(group.modes) do
    modes[#modes + 1] = mode.key .. ':' .. mode.category
  end
  if group.auto then modes[#modes + 1] = group.auto.key .. ':' .. group.auto.category end
  lines[#lines + 1] = group_key .. '|' .. group.default .. '|' .. table.concat(modes, ',')
end
return table.concat(lines, ';')
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
    host_groups, host_categories = [], []
    host_layout: dict[str, tuple[str, list[str]]] = {}
    for line in lua.split(';'):
        key, default, modes = line.split('|')
        categories = [entry.split(':')[1] for entry in modes.split(',')]
        host_groups.append(key)
        host_categories.extend(categories)
        host_layout[key] = (default, categories)
    launcher_keys, launcher_categories = launcher_groups()
    if host_groups != launcher_keys:
        raise SystemExit(f'group order differs:\n  host:     {host_groups}\n'
                         f'  launcher: {launcher_keys}')
    if host_categories != launcher_categories:
        raise SystemExit(f'categories differ:\n  host:     {host_categories}\n'
                         f'  launcher: {launcher_categories}')
    for group, expected in EXPECTED_GROUPS.items():
        if host_layout.get(group) != expected:
            raise SystemExit(f'{group} layout is {host_layout.get(group)}, want {expected}')
    source = PHASE.read_text(encoding='utf-8')
    for prefix, path in FALLBACKS.items():
        for category in host_categories:
            if not category.startswith(prefix):
                continue
            if not re.search(rf'{category}: \["{re.escape(path)}"\]', source):
                raise SystemExit(f'{PHASE}: {category} has no {path} fallback')
    counts = []
    for _skill, group, enspells, names in cases:
        classified = sum(1 for name in names if name.casefold() not in enspells)
        counts.append(f'{group} {classified}')
    print(f"OK: {len(host_groups)} spell mode groups; classified {', '.join(counts)} "
          f'(self-enspells stay in Enspells)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
