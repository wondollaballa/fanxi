#!/usr/bin/env python3
"""Check the in-game Equip View's flush 4x4 grid and its in-box slot watermark.

The window used to spell every slot under its icon (`hud.equipview_labels[entry.key]` after each
image, in a text row the grid had to leave room for), and it never called ``api.End()``: the
addon guard closed the window after the fact.  The redesign makes the boxes touch like the
client's item picker and moves an empty slot's name *inside* the box.  This test pins both
properties, so a later layout change cannot quietly put the label rows back.

The geometry and the window live in marked regions so the real Lua runs without the game host:
the geometry is checked directly, then the window is run against a recording stand-in for the
IGuiManager.  It needs a Lua interpreter: lupa when installed, otherwise the vendored LuaJIT;
with neither it skips (exit 0), matching tests/hud_cool_test.py.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / 'host' / 'addons' / 'lua' / 'control.lua'
BEGIN = '-- BEGIN Equip View grid geometry'
END = '-- END Equip View grid geometry'
WINDOW_BEGIN = '-- BEGIN Equip View window'
WINDOW_END = '-- END Equip View window'
LUAJIT = ROOT / 'build' / 'third_party' / 'luajit-src' / 'src' / 'luajit'


def region(begin: str, end: str) -> str:
    source = CONTROL.read_text(encoding='utf-8')
    try:
        start = source.index(begin)
        stop = source.index(end, start) + len(end)
    except ValueError as error:
        raise SystemExit(f'{CONTROL}: missing {begin!r} markers: {error}')
    return source[start:stop]


LUA_TEST = r'''
local function eq(got, want, label)
  if got ~= want then
    error(string.format('%s: got %s, want %s', label, tostring(got), tostring(want)), 0)
  end
end

local cell = 51
local left, top = 100, 200

-- The four columns share an edge: column i starts exactly (i - 1) cells in.
for i = 1, 16 do
  local x, y = hud.equipview_cell_rect(i, left, top, cell)
  eq(x, left + ((i - 1) % 4) * cell, 'column ' .. i)
  eq(y, top + math.floor((i - 1) / 4) * cell, 'row ' .. i)
end

-- No gutter: cell 2 starts where cell 1's 51 px ends.  A gap here is the space the old label
-- row used, and it is the thing the redesign removes.
local x1 = hud.equipview_cell_rect(1, left, top, cell)
local x2 = hud.equipview_cell_rect(2, left, top, cell)
eq(x2, x1 + cell, 'columns are flush')

-- No label row: the second row starts exactly one cell below the first, not one cell plus a
-- line of text.
local _, y5 = hud.equipview_cell_rect(5, left, top, cell)
eq(y5, top + cell, 'rows are flush')

-- The whole 4x4 block is exactly four cells wide and tall.
local last_x, last_y = hud.equipview_cell_rect(16, left, top, cell)
eq(last_x + cell, left + 4 * cell, 'grid width')
eq(last_y + cell, top + 4 * cell, 'grid height')

-- An occupied slot draws no text: the icon is the label.  An empty slot carries its name as
-- the box's watermark.
eq(hud.equipview_cell_text(0, 'Main'), 'Main', 'empty slot watermark')
eq(hud.equipview_cell_text(nil, 'Sub'), 'Sub', 'nil id is empty')
eq(hud.equipview_cell_text(4096, 'Main'), nil, 'worn slot has no watermark')
'''

SOURCE_CHECKS = [
    # The window is closed by its own code again; the old version leaked it to the addon guard.
    ('api.End()', 'the Equip View window never calls api.End()'),
    ('api.PopStyleVar(2)', 'the window leaves the hub style vars pushed'),
    # Flush cells are positioned by hand; SameLine/ItemSpacing would put a gutter back.
    ('hud.equipview_cell_rect(i, cx, grid_top, cell)',
     'the grid no longer uses the flush cell rect'),
    # The empty box, not a row under the grid, is where the slot name goes.
    ('hud.equipview_cell_text(id, hud.equipview_labels[entry.key])',
     'the slot name is not drawn as the empty cell watermark'),
    # The game's own item icons (they carry the equip screen's coloured backgrounds).
    ('hud_item_texture(id)', 'the grid no longer draws the client item icon'),
    # The game's equip-menu chrome.
    ('AddRectFilledMultiColor', 'the title bar lost its blue gradient'),
    ('PushClipRect', 'the title-bar paint no longer widens the clip'),
]

FORBIDDEN = [
    ('api.SameLine', 'the cells are laid out in a row again'),
    ('api.BeginGroup', 'the old per-cell group layout is back'),
    # res.menu_icon_rgba is keyed by spell/ability icon ids, not item ids.
    ('hud_icon_texture(', 'the grid asks the spell/ability menu sheet for item art'),
]


def check_source(window: str) -> None:
    if 'local cell = 51' not in window:
        raise SystemExit(f'{CONTROL}: the flush grid cell size changed; check the source test')
    if 'local width, height = 216, 268' not in window:
        raise SystemExit(f'{CONTROL}: the window no longer fits four 51 px cells plus padding')
    # Four cells of 51 px and the 6 px padding on each side: 4 * 51 + 12 = 216.
    if 4 * 51 + 12 != 216:
        raise SystemExit('test arithmetic no longer matches the window width')
    if 'hub_text(api' in window:
        raise SystemExit(f'{CONTROL}: a slot label is submitted under the grid again')
    for needle, message in SOURCE_CHECKS:
        if needle not in window:
            raise SystemExit(f'{CONTROL}: {message}')
    for needle, message in FORBIDDEN:
        if needle in window:
            raise SystemExit(f'{CONTROL}: {message}')


def run_script(script: str) -> None:
    lupa = None
    try:
        import lupa  # noqa: F401
    except Exception:
        pass
    if lupa is not None:
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
        print('equipview_hud_test: no Lua interpreter (lupa or LuaJIT); skipped')
        return
    import tempfile

    with tempfile.NamedTemporaryFile('w', suffix='.lua', delete=False) as handle:
        handle.write(script)
        path = handle.name
    try:
        result = subprocess.run([interpreter, path], capture_output=True, text=True)
    finally:
        os.unlink(path)
    if result.returncode != 0:
        raise SystemExit(f'{CONTROL}: {result.stderr.strip() or result.stdout.strip()}')


MOCK = r'''
local hud = {}
-- A recording stand-in for the IGuiManager the window talks to.  It is enough to run the real
-- hud.equipview_window: the only thing it proves is the layout and the draw calls, not what
-- ImGui renders, but it catches a nil method, an unbalanced push and a label drawn in the wrong
-- place before they become an in-game error.
local draw = {}
local texts, images, buttons, tooltips = {}, {}, {}, {}
local font_size, font_depth = 18, 0
local clip_depth, color_depth, var_depth = 0, 0, 0
local sizes = {}
local cursor_x, cursor_y = 106, 130
local ended = 0
local gradient_bars = 0
local window = nil
local collapsed_mode = false

local function eq(got, want, label)
  if got ~= want then
    error(string.format('%s: got %s, want %s', label, tostring(got), tostring(want)), 0)
  end
end

function draw:AddText(pos, color, text)
  texts[#texts + 1] = { x = pos[1], y = pos[2], text = tostring(text), size = font_size }
end

function draw:AddImageRounded(tex, pmin, pmax, uv0, uv1, col, rounding, flags)
  images[#images + 1] = { x = pmin[1], y = pmin[2], x1 = pmax[1], y1 = pmax[2], tex = tex }
end

function draw:AddImage(tex, pmin, pmax, uv0, uv1, col)
  images[#images + 1] = { x = pmin[1], y = pmin[2], x1 = pmax[1], y1 = pmax[2], tex = tex }
end

function draw:AddRectFilled(pmin, pmax, col, rounding, flags) end

function draw:AddRect(pmin, pmax, col, rounding, flags, thickness) end

function draw:AddRectFilledMultiColor(pmin, pmax, a, b, c, d)
  gradient_bars = gradient_bars + 1
end

function draw:AddTriangleFilled(a, b, c) end

function draw:PushClipRect(pmin, pmax, intersect)
  clip_depth = clip_depth + 1
end

function draw:PopClipRect()
  clip_depth = clip_depth - 1
  if clip_depth < 0 then error('draw clip stack underflow', 0) end
end

local api = {}
local style = { FramePadding = { 4, 3 } }

function api.GetStyle() return style end
function api.GetFrameHeight() return 24 end
function api.GetFontSize() return font_size end
function api.GetWindowPos() return 100, 100 end
function api.GetWindowDrawList() return draw end
function api.GetCursorScreenPos() return cursor_x, cursor_y end
function api.SetCursorScreenPos(pos) cursor_x, cursor_y = pos[1], pos[2] end

function api.PushFont(font, size)
  sizes[#sizes + 1] = font_size
  font_depth = font_depth + 1
  font_size = size or font_size
end

function api.PopFont()
  font_depth = font_depth - 1
  if font_depth < 0 then error('font stack underflow', 0) end
  font_size = sizes[#sizes]
  sizes[#sizes] = nil
end

function api.CalcTextSize(text) return #text * font_size * 0.6, font_size end

function api.PushStyleColor(index, color) color_depth = color_depth + 1 end
function api.PopStyleColor(count) color_depth = color_depth - (count or 1) end
function api.PushStyleVar(index, value) var_depth = var_depth + 1 end
function api.PopStyleVar(count) var_depth = var_depth - (count or 1) end

function api.InvisibleButton(id, size)
  buttons[#buttons + 1] = { id = id, x = cursor_x, y = cursor_y, w = size[1], h = size[2] }
  cursor_x, cursor_y = cursor_x + size[1], cursor_y + size[2]
  return false
end

function api.IsItemHovered() return false end
function api.SetItemTooltip(text) tooltips[#tooltips + 1] = text end
function api.End() ended = ended + 1 end

function hud_color(r, g, b, a) return a * 16777216 + b * 65536 + g * 256 + r end
HUB_C = { gold = { 1.00, 0.79, 0.27, 1 } }

function hub_rgba(c)
  local a = c[4] or 1
  return hud_color(math.floor(c[1] * 255 + 0.5), math.floor(c[2] * 255 + 0.5),
    math.floor(c[3] * 255 + 0.5), math.floor(a * 255 + 0.5))
end

hud.state = { equipview = { x = -1, y = -1 }, opacity = 0.9 }
function hud.equipview_set() return 'no set', { lockedSlots = {} } end
function hud_screen_size(a) return 1920, 1080 end

local worn = {
  [0] = 4096, [1] = 4097, [2] = 0, [3] = 4098, [4] = 4099, [5] = 4100, [6] = 4101,
  [7] = 4102, [8] = 4103, [9] = 4104, [10] = 4105, [11] = 4106, [12] = 0, [13] = 4107,
  [14] = 0, [15] = 4108,
}
local worn_count = 0
for _, id in pairs(worn) do if id > 0 then worn_count = worn_count + 1 end end

function hud.equipview_worn(kind) return worn[kind] or 0 end
function hud_item_texture(id) return id end
function hud.equipview_name(id) return 'Item ' .. tostring(id) end

function hub_window_begin(a, title, id, x, y, width, height, opacity, summary, close, flags, skin)
  -- The real helper pushes the window padding and item spacing and leaves them for the caller
  -- on the open path; a collapsed window ends itself and pops them.
  api.PushStyleVar(2, { 6, 6 })
  api.PushStyleVar(14, { 5, 5 })
  window = { title = title, summary = summary, width = width, height = height }
  if collapsed_mode then
    if skin then skin(a, 100, 100, width, 24, true) end
    api.End()
    api.PopStyleVar(2)
    return nil
  end
  if skin then skin(a, 100, 100, width, height, false) end
  return true
end

hud.equipview_window(api)

local cell = 51
local left, top = 106, 130 + 27
eq(ended, 1, 'api.End called once')
eq(color_depth, 0, 'style colours balanced')
eq(var_depth, 0, 'style vars balanced')
eq(font_depth, 0, 'font stack balanced')
eq(clip_depth, 0, 'draw clip stack balanced')
eq(window.title, 'Equip View', 'window title')
eq(window.width, 216, 'window width')
eq(window.height, 268, 'window height')
eq(window.summary, 'no set', 'collapsed summary')
eq(hud.state.equipview.x, 100, 'window x saved')
eq(hud.state.equipview.y, 100, 'window y saved')
eq(#buttons, 16, 'one hit box per slot')
eq(#tooltips, 16, 'a tooltip per slot')
eq(#images, worn_count, 'an icon per worn slot')
eq(gradient_bars, 1, 'the title bar gradient is painted')

-- The boxes are one flush 4x4 block: 51 px apart on both axes, no gutter and no label row.
for i = 1, 16 do
  local b = buttons[i]
  local col, row = (i - 1) % 4, math.floor((i - 1) / 4)
  eq(b.x, left + col * cell, 'cell x ' .. i)
  eq(b.y, top + row * cell, 'cell y ' .. i)
  eq(b.w, cell, 'cell width ' .. i)
  eq(b.h, cell, 'cell height ' .. i)
end

-- Every slot name that is drawn is the watermark of its own empty box, never a caption under
-- that box.  "L.Ear" and friends also appear in tooltips; this checks only the draw list.
local label_slot = {}
for i, slot in ipairs(hud.equipview_slots) do label_slot[hud.equipview_labels[slot.key]] = i end
local seen_watermarks = {}
for _, t in ipairs(texts) do
  local index = label_slot[t.text]
  if index then
    local col, row = (index - 1) % 4, math.floor((index - 1) / 4)
    local x0, y0 = left + col * cell, top + row * cell
    if t.x < x0 or t.x >= x0 + cell or t.y < y0 or t.y >= y0 + cell then
      error(string.format('slot label %q is outside its box (%d, %d)', t.text, t.x, t.y), 0)
    end
    seen_watermarks[t.text] = true
  elseif t.text ~= 'Equip View' and t.text ~= 'no set' then
    error('unexpected text drawn: ' .. t.text, 0)
  end
end
local watermark_count = 0
for _ in pairs(seen_watermarks) do watermark_count = watermark_count + 1 end
eq(watermark_count, 3, 'only the three empty slots carry their name inside the box')

-- Nothing is drawn below the grid: the old layout's label row would be here.
local grid_bottom = top + 4 * cell
for _, t in ipairs(texts) do
  if t.y >= grid_bottom then error('text below the grid: ' .. t.text, 0) end
end

-- Collapsed, the same frame paints one bar and shows the set name there; no grid is drawn.
collapsed_mode = true
texts, images, buttons, tooltips = {}, {}, {}, {}
ended, gradient_bars, color_depth, var_depth, font_depth, clip_depth = 0, 0, 0, 0, 0, 0
hud.equipview_window(api)
eq(ended, 1, 'a collapsed window is ended by the hub helper, not the window')
eq(color_depth, 0, 'collapsed style colours balanced')
eq(var_depth, 0, 'collapsed style vars balanced')
eq(font_depth, 0, 'collapsed font stack balanced')
eq(clip_depth, 0, 'collapsed clip stack balanced')
eq(#buttons, 0, 'no cells while collapsed')
eq(gradient_bars, 1, 'the collapsed bar keeps the gradient')
local saw_title, saw_set = false, false
for _, t in ipairs(texts) do
  if label_slot[t.text] then error('a slot label is drawn while collapsed: ' .. t.text, 0) end
  if t.text == 'Equip View' then saw_title = true end
  if t.text == 'no set' then saw_set = true end
  if t.y < 100 or t.y >= 124 then
    error('collapsed title text outside the bar: ' .. t.text, 0)
  end
end
eq(saw_title, true, 'collapsed bar keeps the title')
eq(saw_set, true, 'collapsed bar keeps the set name')
print('equipview_hud_test: mock window OK')
'''


# The first hud.equipview_window(api) call ends the stubs; the assertions that follow become
# MOCK_TEST, so the real slots/labels/geometry/window can be spliced in before the call.
MOCK_PRELUDE, MOCK_TEST = MOCK.split('hud.equipview_window(api)\n', 1)


def slots_block() -> str:
    source = CONTROL.read_text(encoding='utf-8')
    start = source.index('hud.equipview_slots = {')
    stop = source.index(BEGIN, start)
    return source[start:stop]


def run_window(geometry: str, window: str) -> None:
    script = (
        MOCK_PRELUDE
        + slots_block()
        + geometry
        + window
        + '\nhud.equipview_window(api)\n'
        + MOCK_TEST
    )
    run_script(script)


def main() -> None:
    geometry = region(BEGIN, END)
    window = region(WINDOW_BEGIN, WINDOW_END)
    run_script('local hud = {}\n' + geometry + '\n' + LUA_TEST)
    check_source(window)
    run_window(geometry, window)
    print('equipview_hud_test: PASS')


if __name__ == '__main__':
    main()
