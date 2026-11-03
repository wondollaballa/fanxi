#!/usr/bin/env python3
"""Check the server's Reforged Bonanza names resolve to the client's stronger copies.

The client stores a Reforged weapon under the same display name as its base (21541 is
"Premium Hearts", not "Premium Heart"; 21732 is "Demonic Axe", not "Malefic Axe").  The
server names the upgrade "<base> (Reforged)" so GearSwap can tell them apart, but
`res.item_by_name` cannot resolve that name.  `control.lua` keeps the join in one marked
region; this runs the real lookup against a stub resource table and checks the table
covers every "(Reforged)" row migration 53 inserted.

The test needs a Lua interpreter: lupa when installed, otherwise the vendored LuaJIT;
with neither it skips (exit 0), matching the other HUD tests.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'
MIGRATION = ROOT / 'database' / 'migrations' / '0053_bonanza_reforged.sql'
BEGIN = '-- BEGIN Reforged item names'
END = '-- END Reforged item names'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'


def region() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(BEGIN)
        stop = source.index(END, start) + len(END)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing the Reforged item markers: {error}')
    return source[start:stop]


def migration_names() -> dict[str, int]:
    """lowercased server name -> id for every Reforged weapon migration 53 inserts."""
    text = MIGRATION.read_text(encoding='utf-8')
    out: dict[str, int] = {}
    for match in re.finditer(r"\((\d+),'((?:[^']|'')+)',1,0,'(?:main|ranged)'", text):
        name = match.group(2).replace("''", "'")
        if name.endswith(' (Reforged)'):
            out[name.lower()] = int(match.group(1))
    return out


def lua_table() -> dict[str, int]:
    """The same mapping as control.lua spells it."""
    out: dict[str, int] = {}
    for match in re.finditer(r'\["([^"]+)"\]\s*=\s*(\d+)', region()):
        out[match.group(1).lower()] = int(match.group(2))
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
    expected = migration_names()
    actual = lua_table()
    if not expected:
        raise SystemExit(f'{MIGRATION}: no Reforged Bonanza rows found')
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        wrong = sorted(name for name in expected.keys() & actual.keys()
                       if expected[name] != actual[name])
        raise SystemExit(
            f'{CONTROL}: Reforged item table does not match {MIGRATION.name}: '
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
    if name == "Wizard's Rod" then return { id = 21991 } end
    if name == 'Air Knife' then return { id = 21570 } end
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
