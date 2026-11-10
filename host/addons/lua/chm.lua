--[==[
The Chemist HUD: the Battle Bag, the five abilities and the three stance windows.

The server owns the bag.  This window polls
``GET /api/v1/characters/<ServerId>/chemist`` through the launcher's API (the same
HTTP client the Target Debuffs window uses), so the rows, quantities, selection,
stances and recasts are the server's live state and no packet has to be invented
for them.  The spell page's Chemistry section reads the same snapshot.

Buttons send ordinary ``//chm`` commands.  Toss needs the selected mob; Mix and the
three stances are self-targeted.  The server enforces the CHM main job, the level
gate, the Battle Bag, range and every recast, so a click the server refuses just
says why in chat; the client's own action packet is not faked here.

The window is automatic for a Chemist main job.  ``//hud chm`` (or its title-bar X)
remembers the choice in the per-character HUD file, next to the other windows.
--]==]

local M = {}      -- the module: install, tick, draw, accept and the data control.lua reads
local game = xi.game  -- the addon's game namespace (control.lua keeps it local, not global)
local S = {}      -- the state only this module touches
local W = {}      -- the window

-- ---------------------------------------------------------------------------------------------
-- constants

local POLL_SECONDS = 1.0
local WIDTH, HEIGHT = 356, 392
local BAG_HEIGHT = 190
local JOB_CHEMIST = 23

local COLORS = {
    text = { 0.92, 0.90, 0.86, 1 },
    dim = { 0.62, 0.70, 0.78, 1 },
    faint = { 0.44, 0.50, 0.58, 1 },
    cyan = { 0.35, 0.85, 0.95, 1 },
    green = { 0.52, 0.92, 0.62, 1 },
    yellow = { 0.95, 0.82, 0.42, 1 },
    red = { 0.95, 0.45, 0.40, 1 },
    violet = { 0.72, 0.62, 0.95, 1 },
    white = { 1, 1, 1, 1 },
}

-- The five job abilities.  The ids are the server's (chemist.py): 395..399.  The
-- command is how the HUD reaches them, because the native Ability menu has no name
-- or icon for a post-retail id yet.
local ABILITIES = {
    { key = 'toss', name = 'Toss', command = '//chm toss', color = 'violet',
      hint = 'Throw the selected hostile item at the target' },
    { key = 'mix', name = 'Mix', command = '//chm mix', color = 'green',
      hint = 'Mix the selected friendly item (self target here)' },
    { key = 'catalyst', name = 'Catalyst', command = '//chm catalyst', color = 'yellow',
      hint = 'The next Toss or Mix covers nearby targets' },
    { key = 'amplify', name = 'Amplify', command = '//chm amplify', color = 'cyan',
      hint = 'The next sub-job spell resolves one tier higher' },
    { key = 'volatile', name = 'Volatile', command = '//chm volatile', color = 'red',
      hint = 'The next hostile Toss lands at maximum potency' },
}

-- ---------------------------------------------------------------------------------------------
-- small helpers

local function u32(color)
    local a = color[4] or 1
    return math.floor(a * 255) * 16777216 + math.floor((color[3] or 1) * 255) * 65536
        + math.floor((color[2] or 1) * 255) * 256 + math.floor((color[1] or 1) * 255)
end

local function clock()
    return os.clock()
end

local function trim(value)
    return tostring(value or ''):match('^%s*(.-)%s*$') or ''
end

local function ceil_seconds(value)
    value = tonumber(value) or 0
    if value <= 0 then return 0 end
    return math.ceil(value)
end

local function notify(text)
    if S.ctx and S.ctx.notify then S.ctx.notify(text) return end
    if xi and xi.chat and xi.chat.write then xi.chat.write(tostring(text), 1) end
end

local function run(command)
    local ok, err = pcall(xi.chat.run, command, 1)
    if not ok then
        notify('Chemist HUD: ' .. tostring(err))
        return false
    end
    return true
end

local function text(api, color, value)
    -- The binding takes the {r,g,b,a} table (u32() is only for PushStyleColor).
    api.TextColored(color or COLORS.text, tostring(value))
end

local function button(api, label, color, width, height)
    api.PushStyleColor(21, u32(color or COLORS.cyan))
    api.PushStyleColor(22, u32({
        math.min(1, (color or COLORS.cyan)[1] * 1.18 + 0.02),
        math.min(1, (color or COLORS.cyan)[2] * 1.18 + 0.02),
        math.min(1, (color or COLORS.cyan)[3] * 1.18 + 0.02), 1 }))
    api.PushStyleColor(23, u32({
        (color or COLORS.cyan)[1] * 0.70, (color or COLORS.cyan)[2] * 0.70,
        (color or COLORS.cyan)[3] * 0.70, 1 }))
    local clicked = api.Button(label, { width or 96, height or 24 })
    api.PopStyleColor(3)
    return clicked
end

local function dim_button(api, label, width, height)
    api.PushStyleColor(21, u32({ 0.11, 0.13, 0.16, 1 }))
    api.PushStyleColor(22, u32({ 0.15, 0.17, 0.21, 1 }))
    api.PushStyleColor(23, u32({ 0.10, 0.12, 0.15, 1 }))
    api.PushStyleColor(0, u32(COLORS.faint))
    local clicked = api.Button(label, { width or 96, height or 24 })
    api.PopStyleColor(4)
    return clicked
end

-- ---------------------------------------------------------------------------------------------
-- data

local function main_job()
    local ok, value = pcall(function() return game.party_member(0, 'MainJob') end)
    return ok and tonumber(value) or 0
end

function M.active()
    return main_job() == JOB_CHEMIST
end

local function normalize_row(raw)
    raw = type(raw) == 'table' and raw or {}
    local quantity = tonumber(raw.quantity) or 0
    return {
        slot = tonumber(raw.slot) or 0,
        item_id = tonumber(raw.item_id) or 0,
        name = tostring(raw.name or 'Item'),
        quantity = quantity,
        kind = tostring(raw.kind or ''),
        stack = tonumber(raw.stack) or 1,
        depleted = raw.depleted == true or quantity <= 0,
        selected = raw.selected == true,
        visible = raw.visible ~= false,
    }
end

local function bag_signature(data)
    local parts = {
        tostring(tonumber(data.capacity) or 0),
        tostring(tonumber(data.used) or 0),
        tostring(tonumber(data.selected) or 0),
    }
    for _, row in ipairs(data.bag or {}) do
        parts[#parts + 1] = string.format('%d:%d:%d:%d:%s:%s', row.slot, row.item_id,
            row.quantity, row.visible and 1 or 0, row.selected and '*' or '', row.name)
    end
    return table.concat(parts, '|')
end

function M.accept(raw)
    if type(raw) ~= 'table' or type(raw.bag) ~= 'table' then
        S.error = 'the server sent no Battle Bag'
        return false
    end
    local data = {
        main_job = tonumber(raw.main_job) or 0,
        alchemy = tonumber(raw.alchemy) or 0,
        capacity = tonumber(raw.capacity) or 0,
        used = tonumber(raw.used) or 0,
        selected = tonumber(raw.selected) or 0,
        bag = {},
        stances = {},
        recasts = {},
    }
    for _, row in ipairs(raw.bag) do
        data.bag[#data.bag + 1] = normalize_row(row)
    end
    for key, value in pairs(type(raw.stances) == 'table' and raw.stances or {}) do
        data.stances[tostring(key)] = tonumber(value) or 0
    end
    for key, value in pairs(type(raw.recasts) == 'table' and raw.recasts or {}) do
        data.recasts[tostring(key)] = tonumber(value) or 0
    end
    local signature = bag_signature(data)
    S.data = data
    S.error = nil
    S.polled = true
    if signature ~= S.signature then
        S.signature = signature
        if S.ctx and S.ctx.on_bag_changed then
            pcall(S.ctx.on_bag_changed)
        end
    end
    return true
end

function M.bag()
    return S.data and S.data.bag or {}
end

function M.selected_name()
    local selected = S.data and tonumber(S.data.selected) or 0
    for _, row in ipairs(M.bag()) do
        if row.item_id == selected then return row.name end
    end
    return nil
end

function M.snapshot()
    local data = S.data
    local active = 0
    for _, seconds in pairs(data and data.stances or {}) do
        if seconds > 0 then active = active + 1 end
    end
    return {
        shown = M.active(),
        alchemy = data and data.alchemy or 0,
        used = data and data.used or 0,
        capacity = data and data.capacity or 0,
        selected = data and data.selected or 0,
        bag = data and #data.bag or 0,
        stances = active,
        error = S.error,
    }
end

-- ---------------------------------------------------------------------------------------------
-- polling

local function request_state()
    local ctx = S.ctx or {}
    if not ctx.http_json then
        S.error = 'the launcher API is unavailable; start the client from the launcher'
        return
    end
    local ok, pi = pcall(game.player_index)
    pi = ok and tonumber(pi) or -1
    if pi < 0 then return end
    local ok_id, char_id = pcall(function() return game.entity(pi, 'ServerId') end)
    char_id = ok_id and tonumber(char_id) or 0
    if char_id <= 0 then
        S.error = 'no character id yet'
        return
    end
    if not (xi.tasks and xi.tasks.spawn) then return end
    S.polling = true
    xi.tasks.spawn(function()
        local ok_http, data, err = pcall(function()
            return ctx.http_json('GET', string.format('/api/v1/characters/%d/chemist', char_id))
        end)
        S.polling = false
        if ok_http and type(data) == 'table' and type(data.bag) == 'table' then
            M.accept(data)
            return
        end
        local why = (ok_http and err) or data
        if type(why) == 'table' then
            why = why.message or why.code or 'the server refused the request'
        end
        S.error = tostring(why or 'no Chemist state')
    end)
end

function M.tick()
    if not S.installed or not M.active() then return end
    local now = clock()
    if S.polling or now < (S.next_poll or 0) then return end
    S.next_poll = now + POLL_SECONDS
    request_state()
end

-- ---------------------------------------------------------------------------------------------
-- the window

function W.header(api)
    local data = S.data
    if not data then
        text(api, COLORS.dim, 'Chemist: waiting for the server…')
        if S.error then text(api, COLORS.red, S.error) end
        return
    end
    text(api, COLORS.cyan, string.format('Alchemy %d   Bag %d/%d',
        tonumber(data.alchemy) or 0, tonumber(data.used) or 0, tonumber(data.capacity) or 0))
    local selected = M.selected_name()
    text(api, selected and COLORS.green or COLORS.dim,
        'Selected: ' .. tostring(selected or 'none'))
end

function W.abilities(api)
    local data = S.data or { recasts = {} }
    local recasts = data.recasts or {}
    local width = 104
    for index, ability in ipairs(ABILITIES) do
        local remaining = tonumber(recasts[ability.key]) or 0
        local label = ability.name
        local cooling = remaining > 0
        if cooling then
            label = string.format('%s %ds', ability.name, ceil_seconds(remaining))
        end
        local clicked
        if cooling then
            clicked = dim_button(api, label, width, 24)
        else
            clicked = button(api, label, COLORS[ability.color] or COLORS.cyan, width, 24)
        end
        if api.IsItemHovered and api.IsItemHovered() then
            api.SetTooltip(ability.hint .. (cooling and '\nRecast ' .. ceil_seconds(remaining)
                .. 's' or '\nReady'))
        end
        if clicked then run(ability.command) end
        if index % 3 ~= 0 and index < #ABILITIES then
            api.SameLine(0, 6)
        end
    end
end

function W.bag(api)
    local data = S.data
    text(api, COLORS.cyan, 'Battle Bag')
    api.Separator()
    if not data then
        text(api, COLORS.dim, 'No bag state yet.')
        return
    end
    local rows = {}
    for _, row in ipairs(data.bag) do
        if row.visible then rows[#rows + 1] = row end
    end
    if #rows == 0 then
        text(api, COLORS.dim, 'Empty — //chm load <item>, or Toss a depleted slot to synthesize.')
        return
    end
    if api.BeginChild('chm_bag', { 0, BAG_HEIGHT }, true) then
        for _, row in ipairs(rows) do
            local label = string.format('%s%d. %s  x%d%s', row.selected and '*' or ' ',
                row.slot, row.name, row.quantity, row.depleted and ' (depleted)' or '')
            local chosen = api.Selectable(label .. '##chm_bag_' .. tostring(row.item_id),
                row.selected == true, 0, { 0, 18 })
            if api.IsItemHovered and api.IsItemHovered() then
                api.SetTooltip(string.format('%s\n%s · x%d\nClick to select for Toss/Mix',
                    row.name, row.kind ~= '' and row.kind or 'chemistry', row.quantity))
            end
            if chosen and not row.selected then
                run(string.format('//chm select %s', row.name))
                row.selected = true
                for _, other in ipairs(data.bag) do
                    if other ~= row then other.selected = false end
                end
                data.selected = row.item_id
            end
        end
        api.EndChild()
    end
end

function W.stances(api)
    local data = S.data or { stances = {} }
    local stances = data.stances or {}
    for _, ability in ipairs(ABILITIES) do
        if ability.key ~= 'toss' and ability.key ~= 'mix' then
            local remaining = tonumber(stances[ability.key]) or 0
            if remaining > 0 then
                api.SameLine(0, 10)
                text(api, COLORS[ability.color] or COLORS.cyan,
                    string.format('%s %ds', ability.name, ceil_seconds(remaining)))
            end
        end
    end
    local any = false
    for _, seconds in pairs(stances) do
        if seconds > 0 then any = true break end
    end
    if not any then text(api, COLORS.dim, 'Stances: none') end
end

function W.window(api)
    local ctx = S.ctx or {}
    local win = ctx.get_window and ctx.get_window() or { x = 560, y = 40 }
    local ok, io = pcall(api.GetIO)
    if ok and io and io.DisplaySize then
        local sw, sh = tonumber(io.DisplaySize.x) or 1280, tonumber(io.DisplaySize.y) or 720
        win.x = math.max(4, math.min(tonumber(win.x) or 16, sw - WIDTH - 4))
        win.y = math.max(4, math.min(tonumber(win.y) or 300, sh - HEIGHT - 4))
    end
    api.SetNextWindowPos({ win.x or 560, win.y or 40 }, S.window_force and 1 or 4)
    api.SetNextWindowSize({ WIDTH, HEIGHT }, 1)
    api.SetNextWindowBgAlpha(0.95)
    S.window_force = false
    local close = { true }
    local data = S.data
    local title = data
        and string.format('Chemist  %d/%d###fanxi_chm_hud', tonumber(data.used) or 0,
            tonumber(data.capacity) or 0)
        or 'Chemist###fanxi_chm_hud'
    local open = api.Begin(title, close, 0)
    if not close[1] and ctx.on_hide then ctx.on_hide(false) end
    if open then
        W.header(api)
        api.Separator()
        W.abilities(api)
        W.bag(api)
        api.Separator()
        W.stances(api)
        if S.error then text(api, COLORS.red, 'Server: ' .. S.error) end
        text(api, COLORS.faint, '//chm load <item> · //hud chm hides · //chm status in chat')
        if api.IsMouseReleased and api.IsMouseReleased(0) then
            local px, py = api.GetWindowPos()
            if px and py and ctx.save_window then
                ctx.save_window(math.floor(px), math.floor(py))
            end
        end
    end
    api.End()
end

-- ---------------------------------------------------------------------------------------------
-- public

function M.install(ctx)
    S.ctx = type(ctx) == 'table' and ctx or {}
    S.installed = true
    S.window_force = true
    M.tick()
    return M
end

function M.draw(api)
    if not S.installed then return end
    if not api then
        local ok, got = pcall(xi.ui.imgui)
        if not ok or not got then return end
        api = got
    end
    local ok, err = pcall(W.window, api)
    if not ok and not S.warned then
        S.warned = true
        notify('Chemist HUD: ' .. tostring(err))
    end
end

return M
