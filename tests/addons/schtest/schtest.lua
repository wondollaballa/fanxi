-- The Scholar HUD against a mock ImGui API (tests/sch_hud_test.sh).  This is not a
-- drawing test: it runs the real module's windows and widget code, checks every tab's
-- preset actually forms the chain it is named after, and exercises the saved format,
-- the strategem arithmetic and the macro CRUD without a running client.

-- The harness has no player.  The module reads the live job pair and character name
-- through the same xi.game calls a real client answers, so lend it one.
xi.game.player_index = function() return 1024 end
xi.game.entity = function(_, field)
    if field == 'Name' then return 'Tester' end
    if field == 'ServerId' then return 1 end
    return nil
end
xi.game.party_member = function(_, field)
    if field == 'MainJob' then return 20 end
    if field == 'MainJobLevel' then return 99 end
    if field == 'SubJob' then return 5 end
    if field == 'SubJobLevel' then return 49 end
    return 0
end
xi.game.player = function(field)
    if field == 'Buffs' then return { 359, 470 } end
    return nil
end

local sch = require('xi.sch')
local failed = 0

local function check(label, condition, detail)
    if condition then
        print('ok ' .. label)
    else
        failed = failed + 1
        print('FAIL ' .. label .. ': ' .. tostring(detail))
    end
end

local ok, err = pcall(sch.install, {
    notify = function(text) print('[sch] ' .. tostring(text)) end,
})
check('install', ok, err)

local internal = sch._internal
local S = internal.state()
check('twelve default tabs', S.state and #S.state.groups == 12, S.state and #S.state.groups)
check('liquefaction selected', S.state and S.state.selected == 'liquefaction',
      S.state and S.state.selected)
local liquefaction = S.state and S.state.groups[3]
check('liquefaction has two presets', liquefaction and #liquefaction.macros == 2,
      liquefaction and #liquefaction.macros)
check('stone to pyrohelix preset',
      liquefaction and liquefaction.macros[1].spells[1] == 'Stone'
      and liquefaction.macros[1].spells[2] == 'Pyrohelix',
      liquefaction and table.concat(liquefaction.macros[1].spells, ','))
check('macro is a scholar', sch.active() == true)

-- Every tab's default pair must form the skillchain the tab is named after.
local chains = {
    { 'Transfixion', 1, { 'Noctohelix', 'Luminohelix' } },
    { 'Compression', 2, { 'Blizzard', 'Noctohelix' } },
    { 'Liquefaction', 3, { 'Stone', 'Pyrohelix' } },
    { 'Liquefaction', 3, { 'Stone', 'Fire' } },
    { 'Scission', 4, { 'Aero', 'Geohelix' } },
    { 'Scission', 4, { 'Aero', 'Stone' } },
    { 'Reverberation', 5, { 'Stone', 'Hydrohelix' } },
    { 'Reverberation', 5, { 'Stone', 'Water' } },
    { 'Detonation', 6, { 'Thunder', 'Anemohelix' } },
    { 'Detonation', 6, { 'Thunder', 'Aero' } },
    { 'Induration', 7, { 'Water', 'Cryohelix' } },
    { 'Induration', 7, { 'Water', 'Blizzard' } },
    { 'Impaction', 8, { 'Water', 'Ionohelix' } },
    { 'Impaction', 8, { 'Water', 'Thunder' } },
    { 'Gravitation', 9, { 'Aero', 'Noctohelix' } },
    { 'Distortion', 10, { 'Luminohelix', 'Geohelix' } },
    { 'Distortion', 10, { 'Luminohelix', 'Stone' } },
    { 'Fusion', 11, { 'Fire', 'Ionohelix' } },
    { 'Fusion', 11, { 'Fire', 'Thunder' } },
    { 'Fragmentation', 12, { 'Blizzard', 'Hydrohelix' } },
    { 'Fragmentation', 12, { 'Blizzard', 'Water' } },
}
for _, row in ipairs(chains) do
    local formed = internal.preview_chain(row[3])
    check('forms ' .. row[1] .. ' from ' .. table.concat(row[3], '>'), formed == row[2],
          formed)
end
check('three spells chain Fusion', internal.preview_chain({ 'Stone', 'Fire', 'Thunder' }) == 11,
      internal.preview_chain({ 'Stone', 'Fire', 'Thunder' }))
check('blank third slot ignored', internal.preview_chain({ 'Stone', 'Pyrohelix', '' }) == 3)
check('a non-elemental reset leaves no chain',
      internal.preview_chain({ 'Stone', 'Cure' }) == 0)

-- Charges: (level + 10) / 20, five at 99.
check('five at 99', internal.max_charges(99) == 5, internal.max_charges(99))
check('four at 75', internal.max_charges(75) == 4, internal.max_charges(75))
check('three at 50', internal.max_charges(50) == 3, internal.max_charges(50))
check('two at 30', internal.max_charges(30) == 2, internal.max_charges(30))
check('one at 10', internal.max_charges(10) == 1, internal.max_charges(10))
check('none below 10', internal.max_charges(9) == 0, internal.max_charges(9))

-- Saved format round trip, including the optional pieces.
local state = internal.default_state()
state.groups[3].macros[1].ebullience = true
state.groups[3].macros[1].bursts = { 'Fire II', 'Fire III' }
local text = internal.serialize_state(state)
local parsed = internal.parse_state(text)
check('round trip keeps twelve tabs', parsed and #parsed.groups == 12)
check('round trip keeps window', parsed and parsed.window.w == state.window.w,
      parsed and parsed.window.w)
local saved = parsed and parsed.groups[3].macros[1]
check('round trip keeps spells', saved and saved.spells[1] == 'Stone' and saved.spells[2] == 'Pyrohelix',
      saved and table.concat(saved.spells, ','))
check('round trip keeps ebullience', saved and saved.ebullience == true)
check('round trip keeps bursts', saved and saved.bursts[1] == 'Fire II' and saved.bursts[2] == 'Fire III',
      saved and table.concat(saved.bursts, ','))
check('a tab-free file is still a state',
      internal.parse_state('version\t1\nselected\t\n') ~= nil)

-- Spend, readiness and the next-charge clock.
internal.set_state(internal.default_state())
local T = internal.state()
T.state.charges = { count = 5, max = 5, level = 99, next_at = nil }
internal.spend_charge(2)
check('spending two leaves three', T.state.charges.count == 3, T.state.charges.count)
check('spending starts the clock', T.state.charges.next_at ~= nil)
local now = os.time()
T.state.charges = { count = 0, max = 5, level = 99, next_at = now + 240 }
check('two charges are eight minutes away', internal.ready_at(2) == now + 480,
      internal.ready_at(2) - now)
T.state.charges = { count = 1, max = 5, level = 99, next_at = now + 240 }
check('one short waits for the next charge', internal.ready_at(2) == now + 240,
      internal.ready_at(2) - now)
check('a full macro is ready now', internal.ready_at(1) == 0, internal.ready_at(1))
check('a helix cast is five seconds', internal.cast_seconds('Pyrohelix') == 5,
      internal.cast_seconds('Pyrohelix'))
check('a nuke cast is half a second', internal.cast_seconds('Stone') == 0.5,
      internal.cast_seconds('Stone'))
check('helix detection', internal.is_helix('Pyrohelix') and not internal.is_helix('Fire'))

-- Editing: a new macro with Ebullience and a burst list, then a delete.
local group = T.state.groups[3]
internal.editor_open(group, nil)
local draft = T.editor
check('editor opens', draft ~= nil and draft.mode == 'new')
draft.title = 'My SC'
draft.spells = { 'Aero', 'Noctohelix' }
draft.ebullience = true
draft.bursts = { 'Fire', 'Fire II' }
internal.editor_save()
check('macro saved', #group.macros == 3, #group.macros)
local added = group.macros[3]
check('macro title', added.title == 'My SC', added.title)
check('macro spells', added.spells[1] == 'Aero' and added.spells[2] == 'Noctohelix')
check('macro ebullience', added.ebullience == true)
check('macro bursts', #added.bursts == 2, #added.bursts)
check('cost counts ebullience', internal.charges_needed(added) == 3,
      internal.charges_needed(added))

-- Running: no charges refuses before a task starts; enough charges starts one.
T.state.charges = { count = 0, max = 5, level = 99, next_at = os.time() + 240 }
internal.run_macro(group, added)
check('no strategems means no run', T.run == nil)
T.state.charges = { count = 5, max = 5, level = 99, next_at = nil }
internal.run_macro(group, added)
check('enough strategems starts a run', T.run ~= nil, T.run and T.run.title)
if T.run then internal.stop_run(true) end
check('stop clears the run', T.run == nil)

-- Every window against the mock API.
local draw = {
    AddCircle = function() end,
    AddCircleFilled = function() end,
    AddRect = function() end,
    AddRectFilled = function() end,
    AddText = function() end,
}
local function noop() return false end
local api = {
    GetIO = function() return { DisplaySize = { x = 1280, y = 720 } } end,
    GetContentRegionAvail = function() return 420, 300 end,
    GetCursorScreenPos = function() return 10, 10 end,
    GetWindowDrawList = function() return draw end,
    GetWindowPos = function() return 560, 40 end,
    GetWindowSize = function() return 720, 486 end,
    IsMouseReleased = noop,
    IsItemHovered = noop,
    SetNextWindowPos = function() end,
    SetNextWindowSize = function() end,
    SetNextWindowBgAlpha = function() end,
    SetNextWindowFocus = function() end,
    SetNextItemWidth = function() end,
    SetKeyboardFocusHere = function() end,
    SetTooltip = function() end,
    Begin = function() return true end, End = function() end,
    BeginChild = function() return true end, EndChild = function() end,
    Selectable = noop, Button = noop, SmallButton = noop, Checkbox = noop,
    InputText = noop, InputInt = noop, Combo = noop, DragInt = noop,
    Text = function() end, TextColored = function() end, TextDisabled = function() end,
    Separator = function() end, Dummy = function() end, SameLine = function() end,
    PushStyleColor = function() end, PopStyleColor = function() end,
    PushStyleVar = function() end, PopStyleVar = function() end,
}
local windows = internal.windows
T.state.charges = { count = 3, max = 5, level = 99, next_at = os.time() + 120 }
local okw, errw = pcall(windows.window, api)
check('main window draws', okw, errw)
internal.editor_open(group, added)
local oke, erre = pcall(windows.editor, api)
check('editor draws', oke, erre)
T.picker = { target = 'spell', slot = 1, search = { '' }, focus = false }
local okp, errp = pcall(windows.picker, api)
check('spell picker draws', okp, errp)
T.confirm = { kind = 'macro', group_id = group.id, macro_id = added.id }
local okc, errc = pcall(windows.confirm, api)
check('delete confirmation draws', okc, errc)
T.group_editor = { title = { 'Test tab' }, focus = false }
local okg, errg = pcall(windows.group_editor, api)
check('new-tab dialog draws', okg, errg)

-- Commands and reset.
T.editor, T.picker, T.confirm, T.group_editor = nil, nil, nil, nil
sch.command('position')
check('recentre', T.state.window.x == 560 and T.state.window.w == 720,
      tostring(T.state.window.x) .. ',' .. tostring(T.state.window.w))
sch.command('charges 2')
check('charges command', T.state.charges.count == 2, T.state.charges.count)
sch.command('reset')
check('reset restores the default tabs', #T.state.groups == 12, #T.state.groups)

print('failures=' .. failed)
