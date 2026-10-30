#!/usr/bin/env python3
"""Check the configurable support-Trust action menu in the in-game HUD.

The support Trusts the owner can configure are Joachim, Luzaf, Qultada, Koru-Moru,
Sylvie (UC) and Ygnas.  Their tiles open a menu with Call/Dismiss and a Set songs/spells/
rolls dialog.  The server owns the catalogue and the saved list; the dialog reads them
from hidden `TrustData|` lines and writes them with `//trust <id> set ...`.  A **Use
default logic** checkbox switches the Trust back to its built-in rotation.

The picker helpers live in a marked region of `host/addons/lua/control.lua`, so this test
runs the real Lua without the game host.  It checks the ids/limits against the server, the
data-line parser, ordered selection and the command it sends, plus the live server's
catalogue for the six focused Trusts.
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
BEGIN = '-- BEGIN trust actions'
END = '-- END trust actions'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'

sys.path.insert(0, str(ROOT / 'server'))
sys.path.insert(0, str(ROOT / 'server' / 'tests'))


def helper_block() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(BEGIN)
        end = source.index(END) + len(END)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing the trust action markers: {error}')
    return source[start:end]


def hud_config(block: str) -> dict[int, tuple[str, str, int]]:
    rows = re.findall(
        r'\[(\d+)\]\s*=\s*\{\s*kind\s*=\s*\'([^\']+)\'\s*,\s*label\s*=\s*\'([^\']+)\''
        r'\s*,\s*limit\s*=\s*(\d+)', block)
    return {int(sid): (kind, label, int(limit)) for sid, kind, label, limit in rows}


def check_server_constants(block: str) -> None:
    from fanxi_server.game import trust_ai  # noqa: PLC0415

    hud = hud_config(block)
    if set(hud) != set(trust_ai.SUPPORT_TRUST_IDS):
        raise SystemExit(f'{CONTROL}: trust ids disagree with trust_ai.SUPPORT_TRUST_IDS')
    for trust_id, (kind, label, limit) in hud.items():
        if kind != trust_ai.TRUST_ACTION_KIND[trust_id]:
            raise SystemExit(f'{CONTROL}: trust {trust_id} kind is {kind}')
        if limit != trust_ai.TRUST_ACTION_LIMIT[trust_id]:
            raise SystemExit(f'{CONTROL}: trust {trust_id} limit is {limit}')
        expected = {'song': 'songs', 'spell': 'spells', 'roll': 'rolls'}[kind]
        if label != expected:
            raise SystemExit(f'{CONTROL}: trust {trust_id} label is {label}')


def check_wiring(source: str) -> None:
    if 'hud.trust_configurable(item.id)' not in source or 'hud.trust_open(item)' not in source:
        raise SystemExit(f'{CONTROL}: a support Trust tile no longer opens its menu')
    if 'or hud.trust_menu.open' not in source:
        raise SystemExit(f'{CONTROL}: the trust menu does not keep the HUD frame alive')
    if 'if hud.trust_menu.open then hud.trust_window(api) end' not in source:
        raise SystemExit(f'{CONTROL}: hud.frame never draws the trust menu')
    if "'//trust %d ui hud'" not in source:
        raise SystemExit(f'{CONTROL}: the HUD does not ask for the action catalogue')
    if "text:sub(1, 10) == 'TrustData|'" not in source:
        raise SystemExit(f'{CONTROL}: the HUD does not swallow TrustData lines')
    if "body:sub(1, 10) == 'TrustData|'" not in source:
        raise SystemExit(f'{CONTROL}: the 0x017 path does not swallow TrustData lines')
    if 'trust_data_hook(text:sub(11))' not in source or \
            'trust_data_hook(body:sub(11))' not in source:
        raise SystemExit(f'{CONTROL}: the chat path does not forward to the local HUD')
    if 'function trust_data_hook(text)' not in source:
        raise SystemExit(f'{CONTROL}: trust_data_hook is not defined')
    for label in ('Use default logic', 'Set ', 'Dismiss ', 'Call ', 'Selected ',
                  'Built-in rotation', 'Only the ticked actions'):
        if label not in source:
            raise SystemExit(f'{CONTROL}: the trust menu lost {label!r}')
    if 'hud.trust_config' not in source or 'hud.trust_save()' not in source:
        raise SystemExit(f'{CONTROL}: the trust action helpers are missing')


LUA_TEST = r'''
local function eq(got, want, label)
  if got ~= want then
    error(string.format('%s: got %s, want %s', label, tostring(got), tostring(want)), 0)
  end
end

local function names()
  return table.concat(hud.trust_selected_names(), '|')
end

eq(hud.trust_configurable(911), true, 'Joachim configurable')
eq(hud.trust_configurable(952), true, 'Koru-Moru configurable')
eq(hud.trust_configurable(950), false, 'ordinary Trust not configurable')
eq(hud.trust_label(911), 'songs', 'song label')
eq(hud.trust_label(928), 'rolls', 'roll label')
eq(hud.trust_label(998), 'spells', 'spell label')

-- A catalogue arrives as Begin, one Action line per row, then End.  The saved set is in
-- the Begin line; the parser maps ids to rows and keeps the order.
hud.trust_menu.open = true
hud.trust_menu.trust_id = 952
hud.trust_menu.loading = true
hud.trust_data('952|B|Koru-moru|spell|12|0|511,473')
hud.trust_data('952|A|4|48|cure|Cure IV')
hud.trust_data('952|A|511|96|buff|Haste II')
hud.trust_data('952|A|473|82|buff|Refresh II')
hud.trust_data('952|A|846|96|buff|Flurry II')
hud.trust_data('952|E')
eq(hud.trust_menu.loading, false, 'end ends loading')
eq(#hud.trust_menu.actions, 4, 'action count')
eq(hud.trust_menu.selected[1], 511, 'first saved id')
eq(hud.trust_menu.selected[2], 473, 'second saved id')
eq(names(), 'Haste II|Refresh II', 'saved names')

-- Toggling appends in click order; a duplicate removes it; the limit blocks the extra.
hud.trust_toggle(4)
eq(names(), 'Haste II|Refresh II|Cure IV', 'append')
hud.trust_toggle(473)
eq(names(), 'Haste II|Cure IV', 'remove keeps order')
hud.trust_toggle(473)
eq(names(), 'Haste II|Cure IV|Refresh II', 're-add goes last')
hud.trust_menu.selected = {}
for id = 1, 12 do
  hud.trust_menu.selected[#hud.trust_menu.selected + 1] = 1000 + id
end
hud.trust_toggle(4)
eq(#hud.trust_menu.selected, 12, 'twelve-action cap')
eq(hud.trust_menu.notice, 'You can select at most 12.', 'cap notice')

-- The command quotes the display names, in selection order.
hud.trust_menu.by_id[4] = { id = 4, name = 'Cure IV' }
hud.trust_menu.by_id[1001] = { id = 1001, name = 'Haste II' }
hud.trust_menu.selected = { 1001, 4 }
eq(hud.trust_command(), '//trust 952 set spells "Haste II" "Cure IV"', 'spell command')

-- An automatic set is the default logic; the Use default checkbox is driven from it.
hud.trust_data('952|B|Koru-moru|spell|12|1|')
hud.trust_data('952|E')
eq(hud.trust_menu.auto, true, 'auto flag')
eq(#hud.trust_menu.selected, 0, 'auto clears selected')
eq(hud.trust_command(), '//trust 952 set default', 'default command')

-- The chat handler lives above the local hud, so it reaches the parser through the
-- global forwarder; a real data line must update the open menu through that path too.
hud.trust_menu.trust_id = 952
hud.trust_data('952|B|Koru-moru|spell|12|0|')
trust_data_hook('952|A|473|82|buff|Refresh II')
trust_data_hook('952|E')
eq(#hud.trust_menu.actions, 1, 'hook forwards action rows')
eq(hud.trust_menu.actions[1].name, 'Refresh II', 'hook row name')

-- Songs use the singular label in the command; rolls do too, for the Corsairs.
hud.trust_menu.trust_id = 911
hud.trust_menu.by_id[418] = { id = 418, name = 'Aria of Passion' }
hud.trust_menu.selected = { 418 }
hud.trust_menu.auto = false
eq(hud.trust_command(), '//trust 911 set songs "Aria of Passion"', 'song command')
hud.trust_menu.trust_id = 928
hud.trust_menu.by_id[105] = { id = 105, name = 'Chaos Roll' }
hud.trust_menu.selected = { 105 }
eq(hud.trust_command(), '//trust 928 set rolls "Chaos Roll"', 'roll command')

-- Unknown or stale action ids are dropped at End, and a set with nothing valid becomes
-- the default logic again.
hud.trust_menu.trust_id = 952
hud.trust_data('952|B|Koru-moru|spell|12|0|511,999999')
hud.trust_data('952|A|511|96|buff|Haste II')
hud.trust_data('952|E')
eq(names(), 'Haste II', 'stale id dropped')
eq(hud.trust_menu.auto, false, 'valid set stays custom')

-- Both views draw with the host's ImGui API.  A metatable stands in for every method the
-- window calls; Begin opens and Checkbox never clicks.
HUB_C = { text = {1,1,1,1}, dim = {1,1,1,1}, cyan = {1,1,1,1}, gold = {1,1,1,1},
          green = {1,1,1,1}, red = {1,1,1,1} }
local function noop() end
hub_text = noop
hub_button = function() return false end
hud_screen_size = function() return 1280, 720 end
hud_refresh_trusts = noop
hud_trust_active = function() return false end
hud_trust_key = function(name) return tostring(name):lower() end
hud_cooling = function() return nil end
hud_recast_time = function() return '0s' end
game = { player = function() return 99 end }
local api = setmetatable({}, { __index = function(_, key)
    if key == 'Begin' then return function() return true end end
    if key == 'Checkbox' then return function() return false end end
    return noop
end })
hud.trust_menu.open = true
hud.trust_menu.item = { name = 'Koru-Moru', id = 952 }
hud.trust_menu.trust_id = 952
hud.trust_menu.actions = {
    { id = 511, name = 'Haste II', kind = 'buff', level = 96 },
    { id = 473, name = 'Refresh II', kind = 'buff', level = 82 },
}
hud.trust_menu.by_id = { [511] = hud.trust_menu.actions[1], [473] = hud.trust_menu.actions[2] }
hud.trust_menu.selected = { 511 }
hud.trust_menu.auto = false
hud.trust_menu.loading = false
hud.trust_menu.mode = 'menu'
hud.trust_window(api)
hud.trust_menu.mode = 'actions'
hud.trust_window(api)
hud.trust_menu.auto = true
hud.trust_window(api)
hud.trust_menu.mode = 'menu'

-- Opening sends the hidden catalogue request; calling sends /ma or the release command.
xi = { chat = { run = function() return true end } }
hud.active_trusts = {}
hud.next_trust_scan = 0
hud.trust_menu.open = false
hud.trust_menu.loading = false
hud.trust_open({ name = 'Koru-Moru', id = 952 })
eq(hud.trust_menu.open, true, 'menu opens from the tile helper')
eq(hud.trust_menu.loading, true, 'opening asks for the catalogue')
hud.trust_call()
eq(hud.trust_menu.open, false, 'call closes the menu')

return 'OK: trust ids, data parsing, order, limits, commands and both views'
'''


def run_lua(script: str) -> str:
    lupa = None
    if os.environ.get('TRUST_HUD_TEST_LUAJIT') != '1':
        try:
            from lupa import LuaRuntime  # type: ignore  # noqa: F401
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


def chat_lines(session) -> list[str]:
    import struct
    out = []
    for message in session.queue:
        if (struct.unpack_from('<H', message, 0)[0] & 0x1FF) != 0x017:
            continue
        out.append(bytes(message[4:])[19:].split(b'\0')[0].decode('ascii', 'replace'))
    return out


def check_live_server() -> None:
    """The catalogues the HUD will actually receive for the six focused Trusts."""
    from support import make_service  # noqa: PLC0415

    from fanxi_server.game.world import World  # noqa: PLC0415
    from fanxi_server.game.zone import ZoneSession  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        config, _db, service = make_service(Path(tmp))
        account = service.register('tester', 'password123').account
        character = service.create_character(account['id'], {'name': 'Fanxi', 'race': 1})
        world = World(config, service, None)
        session = ZoneSession(
            world, None,
            service.character_record(service.character(character['id']), 'Fanxi'))
        session.char.update(main_job=17, main_level=99, sub_job=19, sub_level=49)

        def names(trust_id: int) -> set[str]:
            return {row['name'] for row in session._trust_action_catalog(trust_id)}

        if len(names(911)) != 21 or 'Aria of Passion' not in names(911):
            raise SystemExit('Joachim catalogue is missing songs')
        if not {'Haste II', 'Refresh II', 'Cure IV', 'Flurry II'} <= names(952):
            raise SystemExit('Koru-Moru catalogue is missing spells')
        if not {'Cure IV', 'Haste', 'Indi-frailty', 'Indi-haste', 'Geo-malaise'} <= names(981):
            raise SystemExit('Sylvie catalogue is missing spells/auras')
        if not {'Cure VI', 'Protect V', 'Shell V', 'Haste'} <= names(998):
            raise SystemExit('Ygnas catalogue is missing spells')
        for trust_id in (928, 967):
            catalog = names(trust_id)
            if len(catalog) != 31 or 'Chaos Roll' not in catalog or "Samurai Roll" not in catalog:
                raise SystemExit(f'trust {trust_id} roll catalogue is incomplete')

        session.queue.clear()
        session.command(['trust', '952', 'ui', 'hud'])
        lines = chat_lines(session)
        if not any(line.startswith('TrustData|952|B|') for line in lines):
            raise SystemExit('Koru-Moru UI data has no Begin line')
        if not any(line == 'TrustData|952|A|511|96|buff|Haste II' for line in lines):
            raise SystemExit('Koru-Moru UI data has no Haste II row')
        if not any(line == 'TrustData|952|E' for line in lines):
            raise SystemExit('Koru-Moru UI data has no End line')

        session.queue.clear()
        session.command(['trust', '952', 'set', 'spells', '"Haste', 'II"', '"Refresh', 'II"'])
        if session.trust_actions.get(952) != [511, 473]:
            raise SystemExit(f'Koru-Moru set did not persist: {session.trust_actions}')
        if not any('Koru-moru spells: Haste II, Refresh II' in line
                   for line in chat_lines(session)):
            raise SystemExit('Koru-Moru set did not report its names')

        session.queue.clear()
        session.command(['trust', '952', 'set', 'default'])
        if 952 in session.trust_actions:
            raise SystemExit('Koru-Moru default did not clear the set')


def main() -> int:
    source = CONTROL.read_text(encoding='utf-8')
    block = helper_block()
    check_server_constants(block)
    check_wiring(source)
    check_live_server()
    print(run_lua('hud = {}\n' + block + LUA_TEST))
    return 0


if __name__ == '__main__':
    sys.exit(main())
