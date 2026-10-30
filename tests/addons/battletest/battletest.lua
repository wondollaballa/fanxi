-- The Battle hub against a mock ImGui API (tests/battle_hub_test.sh).  This is not a drawing
-- test: it calls every tab's widget code and fails on a Lua error, a nil field or a bad signature
-- before the hub ever reaches a real frame.
local battle = require('xi.battle')
local failed = 0

local function noop() return false end
local draw = {}
for _, name in ipairs({ 'AddRectFilled', 'AddRect', 'AddText', 'AddImage', 'AddCircle', 'AddLine',
    'AddCircleFilled', 'AddConvexPolyFilled', 'AddPolyline', 'AddTriangleFilled' }) do
    draw[name] = function() end
end
local api = {
    GetIO = function() return { DisplaySize = { x = 1280, y = 720 } } end,
    GetBackgroundDrawList = function() return draw end,
    GetForegroundDrawList = function() return draw end,
    GetForegroundDrawList = function() return draw end,
    GetWindowDrawList = function() return draw end,
    GetCursorScreenPos = function() return 20, 20 end,
    GetMousePos = function() return 640, 360 end,
    GetWindowPos = function() return 360, 80 end,
    GetWindowSize = function() return 780, 600 end,
    IsMouseReleased = noop,
    SetNextWindowPos = function() end, SetNextWindowSize = function() end,
    SetNextWindowBgAlpha = function() end, SetNextItemWidth = function() end,
    Begin = function() return true end, End = function() end,
    BeginChild = function() return true end, EndChild = function() end,
    Selectable = noop, Button = noop, SmallButton = noop, Checkbox = noop,
    InputText = noop, InputInt = noop, Combo = noop, SliderFloat = noop,
    DragInt = noop, DragFloat = noop,
    Text = function() end, TextColored = function() end, TextDisabled = function() end,
    Separator = function() end, Dummy = function() end, SameLine = function() end,
    PushStyleColor = function() end, PopStyleColor = function() end,
    PushStyleVar = function() end, PopStyleVar = function() end,
    PushID = function() end, PopID = function() end,
    PushFont = function() end, PopFont = function() end,
    CalcTextSize = function() return 20, 10 end,
}
local ctx = {
    json = { encode = function() return '{}' end, decode = function() return nil end },
    notify = function(text) print('[battle] ' .. tostring(text)) end,
    chat_open = function() return false end,
    edit = function() return false end,
}
local ok, err = pcall(battle.install, ctx)
if not ok then print('install failed: ' .. tostring(err)); return end
print('install ok')

local function check(label, result, err)
    if not result then
        failed = failed + 1
        print('FAIL ' .. label .. ': ' .. tostring(err))
    else
        print('ok ' .. label)
    end
end

local function request(args)
    local state, err = battle.request(args)
    return state, err
end

local first = select(1, request({ action = 'update', profile = {
    name = 'Harness UI', camp = { set = true, x = 1, y = 2, z = 3, radius = 10 },
    support_camp = { set = true, x = 8, y = 2, z = 3, radius = 8 },
    roster = { tank = 'Tester', support = { 'A' }, melee = { 'A' } },
    heal = { cures = { { spell = 'Cure', below = 70 } }, exclude = { 'A' } },
    pull = { find_distance = 45, mobs = { 'Crab', 'Bat' } },
    skillchain = { enabled = true, target = 13,
        steps = {
            { actor = 'Tester', ws = 'Tachi: Gekko' },
            { actor = 'A', ws = 'Tachi: Kasha', diamond = true },
            { actor = 'A', ws = 'Tachi: Shoha' },
        },
        bursters = { { name = 'A', spell = 'Thunder V' } } },
    buffs = { rows = { { spell = 'Haste', target = 'party', interval = 180, exclude = { 'A' } } } },
    enfeebles = { rows = { { spell = 'Dia II', interval = 120 } } },
} }))
check('profile update', first ~= nil, first)
local plan_state = request({ action = 'state' })
local plan = plan_state and plan_state.status and plan_state.status.skillchain
if plan then
    print('plan final=' .. tostring(plan.final) .. ' rows=' .. tostring(#plan.rows))
    check('skillchain final Light', plan.final == 13, plan.final)
    check('Diamond Aspis window', plan.rows[2] and plan.rows[2].window == 11, plan.rows[2] and plan.rows[2].window)
    local state_profile = plan_state and plan_state.profile
    local buff_row = state_profile and state_profile.buffs and state_profile.buffs.rows and state_profile.buffs.rows[1]
    check('buff exclusion saved', buff_row and buff_row.exclude and buff_row.exclude[1] == 'A', buff_row)
    check('heal exclusion saved', state_profile and state_profile.heal and state_profile.heal.exclude[1] == 'A', state_profile and state_profile.heal)
else
    failed = failed + 1
    print('FAIL plan missing')
end

-- A level-1 loop keeps the full 11 s window; only wider links shrink.  This is the
-- Savage Blade > Hot Shot > Savage Blade loop COR players expect to run forever.
local loop_update = request({ action = 'update', profile = {
    name = 'Level 1 loop',
    skillchain = { enabled = true, infinite = true, steps = {
        { actor = 'Tester', ws = 'Savage Blade' },
        { actor = 'Tester', ws = 'Hot Shot' },
        { actor = 'Tester', ws = 'Savage Blade' },
        { actor = 'Tester', ws = 'Hot Shot' },
    } },
} })
check('level-1 loop profile', loop_update ~= nil, loop_update)
local loop_state = request({ action = 'state' })
local loop_plan = loop_state and loop_state.status and loop_state.status.skillchain
if loop_plan then
    print('loop final=' .. tostring(loop_plan.final) .. ' rows=' .. tostring(#loop_plan.rows))
    check('level-1 loop reaches Liquefaction', loop_plan.final == 3, loop_plan.final)
    for index = 2, 4 do
        local row = loop_plan.rows[index]
        check('level-1 link ' .. index .. ' keeps 11 s',
            row and row.valid and row.window == 11, row and row.window)
    end
else
    failed = failed + 1
    print('FAIL level-1 loop plan missing')
end

for _, tab in ipairs({ 'roster', 'camp', 'engage', 'skillchain', 'pull', 'heal', 'buff', 'support', 'debuff', 'rules', 'profile' }) do
    local state, err = request({ action = 'tab', tab = tab })
    if not state then
        failed = failed + 1
        print('FAIL tab ' .. tab .. ': ' .. tostring(err))
    else
        local drawn, derr = xpcall(function() battle.draw(api) end, function(e)
            return debug.traceback(tostring(e), 2)
        end)
        check('tab ' .. tab, drawn, derr)
        if not drawn then
            local st = request({ action = 'state' })
            if st and st.status and st.status.notes then
                for _, n in ipairs(st.status.notes) do print('NOTE ' .. n.kind .. ': ' .. n.text) end
            end
        end
    end
end

-- A live party of three with a saved roster of six: the hub must count only the party, and it
-- must count however many are actually logged in.  The harness has no party table, so patch the
-- accessor the battle module reads.
local fake = {
    [0] = { Name = 'Twodough', ServerId = 1002, HP = 800, HPPercent = 80, MP = 200,
        MPPercent = 60, TP = 700, MainJob = 10, MainJobLevel = 99, SubJob = 1, SubJobLevel = 50,
        Zone = 100 },
    [1] = { Name = 'Threedough', ServerId = 1003, HP = 700, HPPercent = 70, MP = 100,
        MPPercent = 40, TP = 300, MainJob = 5, MainJobLevel = 99, SubJob = 4, SubJobLevel = 50,
        Zone = 100 },
    [2] = { Name = 'Onedough', ServerId = 1001, HP = 900, HPPercent = 90, MP = 300,
        MPPercent = 80, TP = 1200, MainJob = 17, MainJobLevel = 99, SubJob = 3, SubJobLevel = 49,
        Zone = 100 },
}
local patched = pcall(function()
    xi.game.party_member = function(slot, field)
        local row = fake[slot]
        if not row then return 0 end
        if field == 'IsActive' then return 1 end
        local value = row[field]
        return value ~= nil and value or 0
    end
end)
check('live party patch', patched, patched)
local live = select(1, request({ action = 'update', profile = {
    name = 'Live party',
    roster = {
        tank = 'Onedough',
        support = { 'Sixdough' },
        melee = { 'Twodough', 'Threedough', 'Fourdough', 'Fivedough' },
    },
    camp = { set = true, x = 1, y = 2, z = 3, radius = 10 },
} }))
check('live party profile', live ~= nil, live)
local melee_online = battle.roster_online('melee')
check('melee counts only the live party', #melee_online == 2 and melee_online[1] == 'Twodough'
    and melee_online[2] == 'Threedough', table.concat(melee_online, ','))
check('absent support is not counted', #battle.roster_online('support') == 0,
    #battle.roster_online('support'))
local tank_online = battle.roster_online('tank')
check('tank is in the party', #tank_online == 1 and tank_online[1] == 'Onedough',
    table.concat(tank_online, ','))
check('active melee is Twodough', battle.active_role_name('melee') == 'Twodough',
    battle.active_role_name('melee'))
local slot, total = battle.melee_slot()
check('formation spreads only two party melee', slot == 1 and total == 2,
    tostring(slot) .. '/' .. tostring(total))
for _, tab in ipairs({ 'roster', 'camp', 'engage', 'heal', 'buff' }) do
    request({ action = 'tab', tab = tab })
    local drawn, derr = xpcall(function() battle.draw(api) end, function(e)
        return debug.traceback(tostring(e), 2)
    end)
    check('live party tab ' .. tab, drawn, derr)
end

-- Nitro timing: the client's 0x119 table stores a timer by recast id.  The hub must read both
-- abilities, wait while either is down, and only start the pair when both are ready.
local fake_abilities = {
    [0x200 + 163] = { name = 'Nightingale', recast_id = 109 },
    [0x200 + 164] = { name = 'Troubadour', recast_id = 110 },
}
local fake_recasts = {}
local ability_patch = pcall(function()
    xi.game.ability_commands = function()
        return { 0x200 + 163, 0x200 + 164 }
    end
    xi.res.ability = function(id) return fake_abilities[id] end
    xi.game.ability_recast = function(slot)
        local row = fake_recasts[slot]
        if not row then return 0, 0 end
        return row[1], row[2]
    end
end)
check('ability patch', ability_patch, ability_patch)
-- The hub's BRD page may have read the ability table while the fake party was drawn; let that
-- short cache expire before checking the patched table.
local warm_until = os.clock() + 0.6
while os.clock() < warm_until do end
fake_recasts[0] = { 600 * 60, 109 }
local ability = battle.ability_state()
check('Nightingale recast is read', ability['nightingale']
    and ability['nightingale'].remaining == 600, ability['nightingale']
    and ability['nightingale'].remaining)
check('Nitro waits for both', battle.ability_ready('Troubadour')
    and not battle.ability_ready('Nightingale'),
    tostring(battle.ability_remaining('Nightingale')) .. '/'
        .. tostring(battle.ability_remaining('Troubadour')))
fake_recasts[0] = nil
local wait_until = os.clock() + 0.6
while os.clock() < wait_until do end
check('Nitro ready when both are up', battle.ability_ready('Nightingale')
    and battle.ability_ready('Troubadour'),
    tostring(battle.ability_remaining('Nightingale')) .. '/'
        .. tostring(battle.ability_remaining('Troubadour')))
request({ action = 'tab', tab = 'buff' })
local nitro_draw, nitro_err = xpcall(function() battle.draw(api) end, function(e)
    return debug.traceback(tostring(e), 2)
end)
check('Buffs page shows Nitro timing', nitro_draw, nitro_err)

-- The sequence itself: Nightingale, wait for its recast to appear, Troubadour, then hand back to
-- the song cycle.  Start resets the runtime so the sequence begins clean.
local before = request({ action = 'state' })
if before and before.profile then
    before.profile.support.brd.nitro = 'both'
    request({ action = 'update', profile = before.profile })
end
local started = select(1, request({ action = 'start' }))
check('nitro engine start', started ~= nil, started)
fake_recasts[0], fake_recasts[1] = nil, nil
check('Nitro starts clean', battle.nitro_state().step == nil, battle.nitro_state().step)
check('Nitro uses Nightingale first', battle.brd_maybe_nitro('tank') == true
    and battle.nitro_state().step == 'night', battle.nitro_state().step)
local busy_until = os.clock() + 2.3
while os.clock() < busy_until do end
fake_recasts[0] = { 600 * 60, 109 }
check('Nitro uses Troubadour second', battle.brd_maybe_nitro('tank') == true
    and battle.nitro_state().step == 'troub', battle.nitro_state().step)
busy_until = os.clock() + 2.3
while os.clock() < busy_until do end
fake_recasts[1] = { 600 * 60, 110 }
check('Nitro hands back to songs', battle.brd_maybe_nitro('tank') == false
    and battle.nitro_state().step == 'done', battle.nitro_state().step)

-- Zone maps: the placement table and the map DAT decoder.  The map image is the game's own
-- (5313 is West Ronfaure's map DAT in the shipped table), so this checks the whole path the HUD
-- uses with a real file.
local u, v = battle.map_place(100, 0, 0)
check('map placement west ronfaure', u and math.abs(u - 155.94 / 256) < 1e-4
    and math.abs(v - 123.797 / 256) < 1e-4, tostring(u) .. ',' .. tostring(v))
local mu, mv = battle.map_place(3, 0, 0)
check('map placement manaclipper centre', mu == 0.5 and mv == 0.5, tostring(mu) .. ',' .. tostring(mv))
check('map placement unknown zone', battle.map_place(9999, 0, 0) == nil)
local mok, mrgb, mw, mh = pcall(xi.res.map_rgba, 5313)
check('map image decodes', mok and type(mrgb) == 'string' and mw == 512 and mh == 512
    and #mrgb == mw * mh * 4, tostring(mw) .. 'x' .. tostring(mh))
-- The 8bpp map palette is A,B,G,R; reading it as A,R,G,B turns the parchment blue.  A zone map
-- is warm overall, so red must beat blue in a sample of the decoded image.
local warm = 0
for i = 1, #mrgb - 4, 4 * 257 do
    local r, b = mrgb:byte(i), mrgb:byte(i + 2)
    if r and b then warm = warm + (r - b) end
end
check('map colours are warm', warm > 0, tostring(warm))
local zoneok, zoneerr = pcall(battle.zone_map, 100)
check('zone_map does not raise', zoneok, zoneerr)
-- and the whole drawing layer with fake placement values (the real texture needs a GPU)
local mdraw = {}
for _, name in ipairs({ 'AddRectFilled', 'AddRect', 'AddImage', 'AddText', 'AddCircle', 'AddLine',
    'AddCircleFilled' }) do
    mdraw[name] = function() end
end
local fake_map = { texture = 1, w = 512, h = 512, zone = 100, scale = 0.1, ox = 155.94, oy = 123.797 }
local drawok, drawerr = pcall(battle.draw_zone_map, mdraw,
    fake_map, { x = -712, y = -40, heading = 1 }, true, true, 10, 8, 20, 20, 320, 320, 600)
check('draw zone map', drawok, drawerr)
local nearshow, nearerr = pcall(battle.draw_zone_map, mdraw,
    fake_map, { x = -712, y = -40, heading = 1 }, true, true, 10, 8, 20, 20, 320, 320, 150)
check('draw zone map near', nearshow, nearerr)
local zoneshow, zoneerr = pcall(battle.draw_zone_map, mdraw,
    fake_map, { x = -712, y = -40, heading = 1 }, true, true, 10, 8, 20, 20, 320, 320, 3000)
check('draw zone map whole zone', zoneshow, zoneerr)

local state = request({ action = 'state' })
local notes = state and state.status and state.status.notes or {}
for _, line in ipairs(notes) do
    if tostring(line.text):find('Battle hub:', 1, true) or tostring(line.text):find('Battle overlay:', 1, true) then
        failed = failed + 1
        print('FAIL hub note: ' .. tostring(line.text))
    end
end
print('failures=' .. tostring(failed))
