-- The Chemist HUD against a mock ImGui API (tests/chm_hud_test.sh).  It installs the
-- real module, feeds it one server snapshot, draws the window and checks the ability
-- buttons send the //chm command the server route expects.  No client or game files
-- beyond the harness image are needed.

xi.game.player_index = function() return 1024 end
xi.game.entity = function(_, field)
    if field == 'Name' then return 'Tester' end
    if field == 'ServerId' then return 0x01000001 end
    return nil
end
xi.game.party_member = function(_, field)
    if field == 'MainJob' then return 23 end
    if field == 'MainJobLevel' then return 99 end
    if field == 'SubJob' then return 20 end
    if field == 'SubJobLevel' then return 49 end
    return 0
end

local commands = {}
local hidden = nil
local saved = nil
xi.chat.run = function(line) commands[#commands + 1] = tostring(line) return true end

local chm = require('xi.chm')
local failed = 0
local function check(label, condition, detail)
    if condition then
        print('ok ' .. label)
    else
        failed = failed + 1
        print('FAIL ' .. label .. ': ' .. tostring(detail))
    end
end

local ok, err = pcall(chm.install, {
    notify = function(text) print('[chm] ' .. tostring(text)) end,
    get_shown = function() return true end,
    on_hide = function(shown) hidden = shown end,
    get_window = function() return { x = 40, y = 60 } end,
    save_window = function(x, y) saved = { x = x, y = y } end,
    http_json = function() return {} end,
})
check('install', ok, err)
check('a Chemist main is active', chm.active() == true)

-- The snapshot the endpoint returns: a real Potion row, a depleted custom row, both
-- stances and the custom recast ids.
local ok_accept, accept_err = pcall(chm.accept, {
    main_job = 23,
    alchemy = 55,
    capacity = 20,
    used = 2,
    selected = 30000,
    bag = {
        { slot = 1, item_id = 4112, name = 'Potion', quantity = 5, kind = 'heal',
          stack = 99, depleted = false, selected = false, visible = true },
        { slot = 2, item_id = 30000, name = 'Aqua Regia', quantity = 0,
          kind = 'hostile', stack = 3, depleted = true, selected = true, visible = true },
        { slot = 21, item_id = 30001, name = 'Sludge Bomb', quantity = 3,
          kind = 'hostile', stack = 3, depleted = false, selected = false, visible = false },
    },
    stances = { catalyst = 42.5, amplify = 0, volatile = 0 },
    recasts = { toss = 0, mix = 0, catalyst = 12.4, amplify = 0, volatile = 350.2 },
})
check('snapshot accepted', ok_accept, accept_err)
local bag = chm.bag()
check('the visible bag rows are kept', #bag == 3, #bag)
check('the selected row is named', chm.selected_name() == 'Aqua Regia', chm.selected_name())
local snapshot = chm.snapshot()
check('snapshot alchemy', snapshot.alchemy == 55, snapshot.alchemy)
check('snapshot active stances', snapshot.stances == 1, snapshot.stances)
check('snapshot bag count', snapshot.bag == 3, snapshot.bag)
check('the depleted row is marked', bag[2] and bag[2].depleted == true)

-- Mock ImGui: enough of the API for one window, with a scripted click on Toss.
local click
local function noop() return false end
local function button(label)
    if click and tostring(label):find(click, 1, true) then
        click = nil
        return true
    end
    return false
end
local api = {
    GetIO = function() return { DisplaySize = { x = 1280, y = 720 } } end,
    SetNextWindowPos = function() end, SetNextWindowSize = function() end,
    SetNextWindowBgAlpha = function() end,
    Begin = function() return true end, End = function() end,
    BeginChild = function() return true end, EndChild = function() end,
    TextColored = function() end, Separator = function() end,
    SameLine = function() end, NewLine = function() end,
    Button = button, Selectable = noop,
    PushStyleColor = function() end, PopStyleColor = function() end,
    IsItemHovered = function() return false end, SetTooltip = function() end,
    GetWindowPos = function() return 40, 60 end,
    IsMouseReleased = function() return false end,
}
click = 'Toss'
local ok_draw, draw_err = pcall(chm.draw, api)
check('window draws', ok_draw, draw_err)
check('Toss sent //chm toss', commands[1] == '//chm toss', commands[1])

click = 'Catalyst'
local ok_draw2, draw_err2 = pcall(chm.draw, api)
check('second window draw', ok_draw2, draw_err2)
check('Catalyst sent //chm catalyst', commands[2] == '//chm catalyst', commands[2])

-- A non-Chemist main must hide the window and the section's data feed.
xi.game.party_member = function(_, field)
    if field == 'MainJob' then return 5 end
    if field == 'SubJob' then return 20 end
    return 99
end
check('a Red Mage main is not a Chemist HUD', chm.active() == false)

print('failures=' .. failed)
