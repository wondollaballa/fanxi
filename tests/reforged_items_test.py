#!/usr/bin/env python3
"""Check server-only item names resolve to the client's real item ids.

The server and the client spell certain weapons differently.  The Reforged Bonanza
weapons append " (Reforged)" (and two use the other copy's spelling entirely: Premium
Hearts and Demonic Axe), while the final iLvl 119 III weapons keep the base name but the
client has several stage rows under it.  `res.item_by_name` cannot see the suffix and
returns the lowest (weakest) stage for a base name, which left the EquipViewer slot blank
or showed the wrong stage's tooltip and stats.

`control.lua` keeps the joins in one marked region.  This test runs the real lookup
against a stub resource table, checks the Reforged table against migration 53, and checks
the final-form table against the server's Prime and REMA family tables plus every
``119 III`` spelling the migrations use.

The test needs a Lua interpreter: lupa when installed, otherwise the vendored LuaJIT;
with neither it skips (exit 0), matching the other HUD tests.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'
MIGRATION = ROOT / 'database' / 'migrations' / '0053_bonanza_reforged.sql'
MIGRATIONS = ROOT / 'database' / 'migrations'
BEGIN = '-- BEGIN Item name aliases'
END = '-- END Item name aliases'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'


def region() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(BEGIN)
        stop = source.index(END, start) + len(END)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing the item-name alias markers: {error}')
    return source[start:stop]


def reforged_names() -> dict[str, int]:
    """lowercased server name -> id for every Reforged weapon migration 53 inserts."""
    text = MIGRATION.read_text(encoding='utf-8')
    out: dict[str, int] = {}
    for match in re.finditer(r"\((\d+),'((?:[^']|'')+)',1,0,'(?:main|ranged)'", text):
        name = match.group(2).replace("''", "'")
        if name.endswith(' (Reforged)'):
            out[name.lower()] = int(match.group(1))
    return out


def final_form_names() -> dict[str, int]:
    """lowercased base name and "119 III" spelling -> the family's final client id."""
    sys.path.insert(0, str(ROOT / 'server'))
    from fanxi_server.game import prime_weapons, rema_weapons  # noqa: PLC0415

    out: dict[str, int] = {}
    for family, stages in prime_weapons.PRIME_FAMILIES:
        out[family.lower()] = stages[-1][1]
    for family, final_id, _ids in rema_weapons.REMA_FAMILIES:
        out[family.lower()] = final_id

    # The hand-added final rows carry "119 III" in their name.  Every one must name a
    # family the tables above know; otherwise the alias table would silently miss it.
    suffixes = {'Dokoku 119 III', 'Hvergelmir 119 III', 'Kannagi 119 III',
                'Kikoku 119 III', 'Nagi 119 III', 'Opashoro 119 III',
                'Tupsimati 119 III'}
    for path in MIGRATIONS.glob('*.sql'):
        suffixes.update(re.findall(r"'([^']+ 119 III)'", path.read_text(encoding='utf-8')))
    for name in suffixes:
        base = name[:-len(' 119 III')].lower()
        if base not in out:
            raise SystemExit(f'{CONTROL}: no final form for the suffixed name {name!r}')
        out[name.lower()] = out[base]
    return out


def lua_tables() -> dict[str, int]:
    """Both alias tables as control.lua spells them."""
    out: dict[str, int] = {}
    for pattern in (r'\["([^"]+)"\]\s*=\s*(\d+)', r"\['([^']+)'\]\s*=\s*(\d+)"):
        for match in re.finditer(pattern, region()):
            key = match.group(1).lower()
            if key in out:
                raise SystemExit(f'{CONTROL}: duplicate item-name alias {key!r}')
            out[key] = int(match.group(2))
    return out


def run_script(script: str) -> None:
    try:
        import lupa  # noqa: F401
    except Exception:
        pass
    else:
        from lupa import LuaRuntime  # type: ignore

        lua = LuaRuntime(unpack_returned_tuples=True)
        runner = lua.eval(
            'function(source) local f, err = (loadstring or load)(source);'
            ' if not f then error(err) end; return f() end'
        )
        try:
            runner(script)
        except Exception as error:  # lupa raises LuaError
            raise SystemExit(f'{CONTROL}: {error}')
        return
    interpreter = str(LUAJIT) if LUAJIT.exists() else None
    if not interpreter:
        for candidate in ('luajit', 'lua'):
            for directory in os.environ.get('PATH', '').split(os.pathsep):
                path = Path(directory) / candidate
                if path.is_file() and os.access(path, os.X_OK):
                    interpreter = str(path)
                    break
            if interpreter:
                break
    if not interpreter:
        print('reforged_items_test: no Lua interpreter (lupa or LuaJIT); skipped')
        return
    with tempfile.NamedTemporaryFile('w', suffix='.lua', delete=False) as handle:
        handle.write(script)
        path = handle.name
    try:
        result = subprocess.run([interpreter, path], capture_output=True, text=True)
    finally:
        os.unlink(path)
    if result.returncode != 0:
        raise SystemExit(f'{CONTROL}: {result.stderr.strip() or result.stdout.strip()}')


def main() -> int:
    expected = reforged_names()
    if not expected:
        raise SystemExit(f'{MIGRATION}: no Reforged Bonanza rows found')
    expected.update(final_form_names())
    actual = lua_tables()
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        wrong = sorted(name for name in expected.keys() & actual.keys()
                       if expected[name] != actual[name])
        raise SystemExit(
            f'{CONTROL}: item-name aliases do not match the server tables: '
            f'missing={missing} extra={extra} wrong_ids={wrong}')

    source = CONTROL.read_text(encoding='utf-8')
    if re.search(r'find_item\(.*?res\.item_by_name', source, re.S):
        raise SystemExit(f'{CONTROL}: find_item still resolves the name through the client')
    if re.search(r'local function item_ids.*?res\.item_by_name', source, re.S):
        raise SystemExit(f'{CONTROL}: item_ids still resolves the name through the client')

    lua = r'''
xi = {}
res = {
  item_by_name = function(name)
    -- The client's own answer for every base name is the lowest (weakest) stage or the
    -- base weapon; the alias table must win before this fallback.
    if name == "Wizard's Rod" then return { id = 21991 } end
    if name == 'Air Knife' then return { id = 21570 } end
    if name == 'Opashoro' then return { id = 22103 } end
    if name == 'Excalibur' then return { id = 18276 } end
    return nil
  end,
}

''' + region() + r'''

local function eq(got, want, label)
  if got ~= want then
    error(string.format('%s: got %s, want %s', label, tostring(got), tostring(want)), 0)
  end
end

eq(item_id_for_name("Wizard's Rod (Reforged)"), 21991, 'Wizard Rod suffix')
eq(item_id_for_name('  Wizard\'s Rod (Reforged)  '), 21991, 'surrounding spaces')
eq(item_id_for_name('Premium Heart (Reforged)'), 21541, 'Premium Hearts client spelling')
eq(item_id_for_name('Malefic Axe (Reforged)'), 21732, 'Demonic Axe client spelling')

-- The final form is picked even though the client's base-name lookup returns an early
-- stage (Opashoro 22103, Excalibur 18276) or a weaker duplicate.
eq(item_id_for_name('Opashoro 119 III'), 22106, 'Opashoro server suffix')
eq(item_id_for_name('Opashoro (Level 119 III)'), 22106, 'Level 119 III spelling')
eq(item_id_for_name('Opashoro Level 119 III'), 22106, 'Level 119 III without parens')
eq(item_id_for_name('Opashoro'), 22106, 'Opashoro base name')
eq(item_id_for_name('Excalibur'), 20685, 'Excalibur final form')
eq(item_id_for_name('Fail-Not'), 22117, 'Fail-Not server final id')
eq(item_id_for_name('Dokoku 119 III'), 21932, 'Dokoku server suffix')
eq(item_id_for_name('Kikoku'), 21906, 'Kikoku final form')

eq(item_id_for_name("Wizard's Rod"), 21991, 'base name still uses the client')
eq(item_id_for_name('Air Knife'), 21570, 'plain weapon still uses the client')
eq(item_id_for_name('Not an item'), 0, 'unknown name')
eq(item_id_for_name(''), 0, 'empty name')
eq(item_id_for_name(nil), 0, 'nil name')
eq(xi.item_id_for_name('Exeter (Reforged)'), 22170, 'the lua command sees the resolver')
'''
    run_script(lua)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
