#!/usr/bin/env python3
"""Pin the action HUD windows' docking contract.

Trusts, Weapon Skills, Job Abilities and Spells used to be title-less, immovable windows:
they could not be dragged onto another HUD's tab bar the way Magic Bag, Chemist, Target
Debuffs and Stats can.  They now have a title bar, a stable per-character ### id (so ImGui
keeps their position and dock tab group) and a tab X that is the same switch as //hud.

This test checks the parts of control.lua that make that work, without the game:
  - the Begin flags no longer carry NoTitleBar/NoMove/NoSavedSettings;
  - the window id is stable across item counts and per character;
  - a floating window uses FirstUseEver (so it can be dragged) and only a reset forces;
  - the close button writes the same show_<type> flag as the commands;
  - the layout reserves the title bar / dock tab bar height;
  - selecting a tab fits the group (the ImGui side is tests/dock_tabs_test.cpp).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'

REQUIRED = [
    ("local flags = 2 + 8 + 32 + (edit and 8192 or 0)",
     'the action windows still ask ImGui for no title bar or no movement'),
    ("'###' .. tostring(hud.window_suffix or 'fanxi-hud') .. '-' .. key",
     'the action window id is not stable and per character'),
    ("hud.window_suffix = 'fanxi-hud-' .. key",
     'hud.ensure does not derive the per-character window id'),
    ("api.SetNextWindowPos({ position.x, position.y }, forced and 1 or 4)",
     'a floating action window cannot be dragged by its title bar'),
    ("local close = { shown }",
     'the action window has no tab/title-bar close button'),
    ("state[show_key] = close[1] == true",
     'closing an action tab does not update its show switch'),
    ("hud.docked[key] = docked_now",
     'the window does not remember that it was clipped into a tab group'),
    ("hud.frame_height(api) + 12",
     'the window height does not reserve the title bar / tab bar'),
    ("local docked = hud.docked[key] == true",
     'a forced position does not check whether the window is docked'),
    ("rest:match('^(.-)%s+(on)$')",
     '//hud <window> on cannot parse its on suffix'),
    ("rest:match('^(.-)%s+(off)$')",
     '//hud <window> off cannot parse its off suffix'),
]

FORBIDDEN = [
    ("%s+(on|off)",
     'Lua patterns have no alternation: the on/off suffix can never match'),
    ("local flags = edit and (2 + 8 + 32 + 256 + 8192) or (1 + 2 + 4 + 8 + 32 + 256)",
     'the old title-less action window flags came back'),
    ("api.Begin(shown_title, nil, flags)",
     'the action window lost its close button'),
    ("(snap or not edit) and 1 or 4",
     'the old always-forced position came back (it undocks a tab)'),
    ("local shown_title = title .. '  (' .. count .. ')'\n",
     'the window id is the item count again (docking state resets on a new spell)'),
]


def main() -> None:
    source = CONTROL.read_text(encoding='utf-8')
    for needle, message in REQUIRED:
        if needle not in source:
            raise SystemExit(f'{CONTROL}: {message}\n  missing: {needle}')
    for needle, message in FORBIDDEN:
        if needle in source:
            raise SystemExit(f'{CONTROL}: {message}\n  found: {needle}')

    # The four action windows all go through hud_window.
    for key in ('abilities', 'spells', 'trusts', 'weapon_skills'):
        if f"hud_window(api, key, HUD_TYPE_INFO[key].title, hud_grouped(key))" not in source:
            raise SystemExit(f'{CONTROL}: {key} is not drawn by hud_window')

    # Compile the file too: the source checks above would not catch a syntax error, and hud_init()
    # is already at LuaJIT's 200-local ceiling (control.lua would fail to load and take the HUD
    # and control port with it).
    compiled = False
    try:
        from lupa import LuaRuntime  # type: ignore
    except ImportError:
        LuaRuntime = None
    if LuaRuntime is not None:
        runtime = LuaRuntime()
        loader = runtime.eval(
            'function(src) local l = loadstring or load; local f, e = l(src, "control");'
            ' return f, e end')
        _function, error = loader(source)
        if error:
            raise SystemExit(f'{CONTROL}: does not compile: {error}')
        compiled = True
    else:
        luajit = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'
        if luajit.is_file():
            result = subprocess.run([str(luajit), '-bl', str(CONTROL), '/dev/null'],
                                    capture_output=True, text=True)
            if result.returncode != 0:
                raise SystemExit(f'{CONTROL}: does not compile:\n{result.stderr}')
            compiled = True
    if compiled:
        print('OK: control.lua compiles')


if __name__ == '__main__':
    main()
    print('hud_dock_test: PASS')
