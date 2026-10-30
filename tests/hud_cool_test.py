#!/usr/bin/env python3
"""Check the action HUD learns job-ability cooldowns from the server's 0x119 table.

`host/addons/lua/control.lua` keeps the cooldown rules in a marked region so this test can
run the real Lua code without the game host.  The regression: Bestial Loyalty was used,
the client logged out and back in, the server restored the 20-minute recast on `0x119` --
and the Abilities hub still drew the tile ready because it only polled the client table
for timers the HUD itself had started.  A click then reached the server, which answered
"Bestial Loyalty is not ready yet."

The rules have to map the client's recast table (1/60 s timer + recast id) onto the HUD's
ability keys, add a cooldown for an ability the HUD never saw used, and leave a click's
pending bar alone until the live sample replaces it.

The test needs a Lua interpreter.  It uses lupa when installed, otherwise a built LuaJIT
from `build/third_party/luajit-src/src/luajit`; with neither it skips (exit 0).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'
BEGIN = '-- BEGIN HUD cooldown rules'
END = '-- END HUD cooldown rules'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'


def rules_block() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(BEGIN)
        end = source.index(END) + len(END)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing the HUD cooldown markers: {error}')
    # The bug was also the call site: hud_update_cool only ran when hud.cool was already
    # non-empty, so a relogin never polled the table it needed to learn from.
    if re.search(r'if\s+next\(hud\.cool\)\s+then\s+hud_update_cool', source):
        raise SystemExit(f'{CONTROL}: hud_update_cool is gated on hud.cool again')
    if not re.search(r'^\s+hud_update_cool\(hud\)\s*$', source, re.M):
        raise SystemExit(f'{CONTROL}: hud_update_cool is never called from the HUD frame')
    return source[start:end]


LUA_TEST = r'''
local function eq(got, want, label)
  if got ~= want then
    error(string.format('%s: got %s, want %s', label, tostring(got), tostring(want)), 0)
  end
end

-- 0x119 lists every known ability, with timer 0 on the ready ones.  Only running slots
-- matter, and the timer is in 1/60 s.
local live = hud_ability_recast_map(function(slot)
  if slot == 1 then return 1200 * 60, 94 end     -- Bestial Loyalty, 20 min
  if slot == 2 then return 300 * 60, 104 end     -- Call Beast, 5 min
  return 0, 0
end)
eq(live[94], 1200, 'Bestial Loyalty seconds')
eq(live[104], 300, 'Call Beast seconds')
local live_count = 0
for _ in pairs(live) do live_count = live_count + 1 end
eq(live_count, 2, 'ready slots ignored')

local cool = {}
local abilities = {
  { key = 'a387', recastId = 94 },    -- Bestial Loyalty
  { key = 'a85', recastId = 104 },    -- Call Beast
  { key = 'a16', recastId = 0 },      -- a two-hour has no recast id
  { key = 'a17' },
}
eq(hud_learn_live_cooldowns(cool, { abilities }, live, 100), true,
   'learns a cooldown the HUD never started')
eq(cool.a387.total, 1200, 'learned total')
eq(cool.a387.remaining, 1200, 'learned remaining')
eq(cool.a387.pending, false, 'learned timer is live')
eq(cool.a387.progress, 0, 'learned timer starts at the top')
eq(cool.a85.remaining, 300, 'learns a second ability')
eq(cool.a16, nil, 'a zero recast id adds nothing')
eq(cool.a17, nil, 'a missing recast id adds nothing')

-- A timer the HUD started belongs to the update loop; this pass only fills the gaps.
cool.a387 = { start = 1, total = 120, remaining = 50, pending = false, progress = 0.58 }
hud_learn_live_cooldowns(cool, { abilities }, live, 101)
eq(cool.a387.total, 120, 'existing total kept')
eq(cool.a387.remaining, 50, 'existing remaining kept')

-- A click's pending bar must survive an empty table until its own deadline.
local pending = { a387 = { start = 0, total = 1200, remaining = 1200,
                           pending = true, progress = 0 } }
eq(hud_learn_live_cooldowns(pending, { abilities }, {}, 102), false, 'empty table')
eq(pending.a387.remaining, 1200, 'pending bar kept')

-- The instant an ability expires the client still has a one-tick timer; that is not a
-- cooldown worth drawing.
local tiny = hud_ability_recast_map(function() return 1, 94 end)
eq(tiny[94], 1 / 60, 'one-tick timer')
local tcool = {}
hud_learn_live_cooldowns(tcool, { abilities }, tiny, 0)
eq(tcool.a387, nil, 'one-tick timer ignored')

-- A stale duplicate slot must not shorten the real recast.
local duplicate = hud_ability_recast_map(function(slot)
  if slot == 1 then return 30 * 60, 94 end
  if slot == 2 then return 45 * 60, 94 end
  return 0, 0
end)
eq(duplicate[94], 45, 'larger duplicate slot wins')

-- A reader that errors is an empty table, not a HUD crash.
local ok, map = pcall(hud_ability_recast_map, function() error('no game') end)
eq(ok, true, 'reader errors are contained')
eq(next(map), nil, 'no timers after a reader error')

-- No ability list yet (a fresh HUD before its first rebuild) learns nothing.
local none = {}
eq(hud_learn_live_cooldowns(none, nil, live, 0), false, 'nil lists')
eq(next(none), nil, 'nil lists add nothing')

return 'OK: restored cooldown, shared ids, pending and empty tables'
'''


def run_lua(script: str) -> str:
    lupa = None
    if os.environ.get('HUD_COOL_TEST_LUAJIT') != '1':
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
    print(run_lua(rules_block() + LUA_TEST))
    return 0


if __name__ == '__main__':
    sys.exit(main())
