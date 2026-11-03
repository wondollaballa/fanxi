--[==[
The Scholar HUD: strategems, self-skillchain macros and magic bursts.

A Scholar's self-skillchain is two (or three) spells, each cast behind its own
Immanence.  The element of the spell decides the weapon-skill property it carries, so
Stone (Earth/Scission) then Pyrohelix (Fire/Liquefaction) forms Liquefaction, and
Aero (Wind/Detonation) then Noctohelix (Dark/Compression) forms Gravitation.  This
module draws that kit as one window:

* the strategem charges behind Immanence (and Ebullience), with the count left, the
  recharge progress and the clock to the next charge -- each spent charge has its own
  return time, so stratagems used back to back come back back to back;
* one tab per skillchain family (Liquefaction, Induration, ...), each holding the
  player's own named macros (up to three spells, an optional Ebullience in front of
  the burst, and an optional magic-burst list that fires after the chain closes);
* an editor for the macros and the tabs, and per-character persistence under
  ``<data>/sch/<name>-<id>.sch``;
* a macro that cannot be paid for is dimmed and shows the clock to the next time the
  chain could be run, instead of sending a sequence the strategems cannot cover.

The keyboard flow is the game's own: an action is an ordinary ``/ja`` or ``/ma`` line,
so the client still owns range, the cast bar, recast checks and the packets it sends.
The runner follows the server's action results instead of fixed sleeps: a job ability
is confirmed by its ABILITY_FINISH result, a spell by MAGIC_START and MAGIC_FINISH,
and the next step goes out as soon as the current result lands.  The shared stratagem
recast (Immanence and Ebullience share id 231) is the one server rule no action result
carries, so the recast table is read before each job ability.  A command the client
drops inside its own animation produces no result; it is retried as soon as the
recast is clear, which lets the action land the moment the client accepts it instead
of after a guessed beat.  Ebullience is used in front of the magic burst, never before
the opener, where the first spell would eat it.

Installed by ``control.lua`` (``hud.sch``), or standalone with ``install{standalone =
true}``, which is how the module is tried in a live client while it is still being
written.

-- The persistence format.  One item per line, TAB separated, ``#`` starts a comment.
-- Spell and tab names cannot contain a TAB, a newline or a comma, which the editor
-- strips, so no escaping is needed:
--
--   version <n>
--   window <x> <y> <w> <h>
--   selected <tab id>
--   charges <count> <next charge epoch or 0> <level> <max> <return times, comma separated>
--   group <tab id> <title>
--   macro <tab id> <macro id> <title> <ebullience 0|1> <spell1> <spell2> <spell3> <comma-separated bursts>
--]==]

local M = {}      -- the module: install, draw, command and the pieces control.lua uses
local S = {}      -- everything that only this module touches
local W = {}      -- the windows

-- ---------------------------------------------------------------------------------------------
-- constants

-- The whole charge pool refills in four minutes at level 10, so the per-charge rate
-- scales with the number of charges (48 s at 99, 60 s at 70, 80 s at 50, 120 s at 30).
-- Every Fanxi job carries the 2,100 JP that unlocks the 550-JP "Stratagem Recast Time"
-- gift; it takes 15 s off each charge, which is the 33 s the retail table shows at 99.
local RECHARGE_TOTAL = 240
local JP_RECHARGE_BONUS = 15
local VERSION = 2
local SPELL_SLOTS = 3
local MAX_BURSTS = 6
local SAVE_EVERY = 0.75

local JOB_SCHOLAR = 20

-- Scholar's stratagems.  Every one spends a charge; Tabula Rasa does not and is absent.
-- The ids are the ability ids the action packet carries (category 9, uuid at 0x0C).
local STRATAGEM = {
    [215] = true, [216] = true, [217] = true, [218] = true, [219] = true, [220] = true,
    [221] = true, [222] = true, [234] = true, [235] = true, [240] = true, [241] = true,
    [242] = true, [243] = true, [316] = true, [317] = true,
    -- Enlightenment (244) is not here: the server's row gives it its own recast id
    -- (235), not the shared stratagem id (231), so it does not spend a charge.
}

-- Status-effect ids for the arts line (effects.py).
local LIGHT_ARTS, DARK_ARTS = 358, 359
local ADDENDUM_WHITE, ADDENDUM_BLACK = 401, 402

-- Skillchain names and tiers, the same ids as the server (skillchain.py).
local SC_NAMES = {
    [0] = 'None', 'Transfixion', 'Compression', 'Liquefaction', 'Scission',
    'Reverberation', 'Detonation', 'Induration', 'Impaction', 'Gravitation',
    'Distortion', 'Fusion', 'Fragmentation', 'Light', 'Darkness', 'Light II',
    'Darkness II',
}
local SC_TIER = { [0] = 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 4, 4 }

-- (closing property, existing resonance) -> formed chain.  Mirrors TRANSITIONS in
-- server/fanxi_server/game/skillchain.py; the preview uses it to tell the player what
-- the spells they picked will actually make.  The server remains the authority.
local SC_PAIRS = {
    { 13, 13, 15 }, { 14, 14, 16 },
    { 10, 9, 14 }, { 12, 9, 12 }, { 9, 10, 14 }, { 11, 10, 11 }, { 9, 11, 9 },
    { 12, 11, 13 }, { 10, 12, 10 }, { 11, 12, 13 },
    { 4, 1, 10 }, { 8, 3, 11 }, { 2, 6, 9 }, { 5, 7, 12 },
    { 2, 1, 2 }, { 5, 1, 5 }, { 1, 2, 1 }, { 6, 2, 6 }, { 4, 3, 4 }, { 3, 4, 3 },
    { 5, 4, 5 }, { 6, 4, 6 }, { 7, 5, 7 }, { 8, 5, 8 }, { 4, 6, 4 }, { 2, 7, 2 },
    { 8, 7, 8 }, { 3, 8, 3 }, { 6, 8, 6 },
}
local SC_TRANS = {}
for _, row in ipairs(SC_PAIRS) do
    SC_TRANS[row[1]] = SC_TRANS[row[1]] or {}
    SC_TRANS[row[1]][row[2]] = row[3]
end

-- The client's spell element is 0-based (0 Fire .. 7 Dark); the server's is 1-based.
-- Immanence gives a spell the property of its element.
local ELEMENT_PROPERTY = {
    [0] = 3,   -- Fire      -> Liquefaction
    [1] = 7,   -- Ice       -> Induration
    [2] = 6,   -- Wind      -> Detonation
    [3] = 4,   -- Earth     -> Scission
    [4] = 8,   -- Thunder   -> Impaction
    [5] = 5,   -- Water     -> Reverberation
    [6] = 1,   -- Light     -> Transfixion
    [7] = 2,   -- Dark      -> Compression
}
local ELEMENT_NAME = { 'Fire', 'Ice', 'Wind', 'Earth', 'Thunder', 'Water', 'Light', 'Dark' }

-- The tabs a fresh character starts with: the level-1 chains first, then the level-2
-- ones.  Each carries the tested pair(s) from the old SCH library, which the player can
-- edit, duplicate or delete.  "helix" is a closer whose name ends in -helix, and is the
-- pair that was timed with the 5 s gap.
local GROUPS = {
    { id = 'transfixion', title = 'Transfixion',
      pairs = { { 'Noctohelix', 'Luminohelix' } } },
    { id = 'compression', title = 'Compression',
      pairs = { { 'Blizzard', 'Noctohelix' } } },
    { id = 'liquefaction', title = 'Liquefaction',
      pairs = { { 'Stone', 'Pyrohelix' }, { 'Stone', 'Fire' } } },
    { id = 'scission', title = 'Scission',
      pairs = { { 'Aero', 'Geohelix' }, { 'Aero', 'Stone' } } },
    { id = 'reverberation', title = 'Reverberation',
      pairs = { { 'Stone', 'Hydrohelix' }, { 'Stone', 'Water' } } },
    { id = 'detonation', title = 'Detonation',
      pairs = { { 'Thunder', 'Anemohelix' }, { 'Thunder', 'Aero' } } },
    { id = 'induration', title = 'Induration',
      pairs = { { 'Water', 'Cryohelix' }, { 'Water', 'Blizzard' } } },
    { id = 'impaction', title = 'Impaction',
      pairs = { { 'Water', 'Ionohelix' }, { 'Water', 'Thunder' } } },
    { id = 'gravitation', title = 'Gravitation',
      pairs = { { 'Aero', 'Noctohelix' } } },
    { id = 'distortion', title = 'Distortion',
      pairs = { { 'Luminohelix', 'Geohelix' }, { 'Luminohelix', 'Stone' } } },
    { id = 'fusion', title = 'Fusion',
      pairs = { { 'Fire', 'Ionohelix' }, { 'Fire', 'Thunder' } } },
    { id = 'fragmentation', title = 'Fragmentation',
      pairs = { { 'Blizzard', 'Hydrohelix' }, { 'Blizzard', 'Water' } } },
}

local COLORS = {
    text = { 0.93, 0.92, 0.89, 1 },
    dim = { 0.58, 0.64, 0.70, 1 },
    faint = { 0.40, 0.45, 0.50, 1 },
    gold = { 1.00, 0.79, 0.27, 1 },
    green = { 0.45, 0.95, 0.58, 1 },
    red = { 1.00, 0.42, 0.38, 1 },
    cyan = { 0.35, 0.85, 0.95, 1 },
    violet = { 0.76, 0.60, 1.00, 1 },
    panel = { 0.08, 0.10, 0.13, 1 },
    track = { 0.16, 0.19, 0.23, 1 },
}

-- ImGui style/draw-list colors are packed ImU32 values; TextColored takes a vec4.
local function u32(color)
    local function channel(value)
        value = tonumber(value) or 0
        if value < 0 then value = 0 elseif value > 1 then value = 1 end
        return math.floor(value * 255 + 0.5)
    end
    return channel(color[1]) + channel(color[2]) * 0x100 + channel(color[3]) * 0x10000
        + channel(color[4] or 1) * 0x1000000
end

-- ---------------------------------------------------------------------------------------------
-- small utilities

local function clock()
    local ok, value = pcall(xi.clock)
    return ok and tonumber(value) or os.clock()
end

local function now_epoch()
    return os.time()
end

local function trim(value)
    return tostring(value or ''):match('^%s*(.-)%s*$') or ''
end

local function clamp(value, low, high, fallback)
    value = tonumber(value)
    if not value or value ~= value then return fallback end
    if value < low then return low end
    if value > high then return high end
    return value
end

local function copy_array(source)
    local out = {}
    for i, value in ipairs(source or {}) do out[i] = value end
    return out
end

-- Names come out of the client's string table in SJIS, and some records carry a
-- language table instead of a string.
local function read_name(value)
    if type(value) == 'table' then value = value.en or value[2] or value[1] end
    if type(value) ~= 'string' then return nil end
    return value
end

local function clean_field(value, cap)
    local text = trim(value):gsub('[%c]', ' '):gsub('%s+', ' '):gsub('##', '# #')
    if cap and #text > cap then text = text:sub(1, cap) end
    return text
end

local function clock_text(seconds)
    seconds = math.max(0, math.floor((tonumber(seconds) or 0) + 0.5))
    if seconds >= 3600 then
        return string.format('%d:%02d:%02d', math.floor(seconds / 3600),
            math.floor((seconds % 3600) / 60), seconds % 60)
    end
    return string.format('%d:%02d', math.floor(seconds / 60), seconds % 60)
end

local function notify(text)
    if S.notify then S.notify(tostring(text)) return end
    pcall(xi.chat.write, tostring(text), 1)
end

-- A strategem count at a job level: one at 10, and one more every 20 levels
-- ((level + 10) / 20, floored -- five at 99).
local function max_charges(level)
    level = tonumber(level) or 0
    if level < 10 then return 0 end
    return math.max(1, math.floor((level + 10) / 20))
end

-- The seconds one charge takes at a job level.  The pool's four minutes are split
-- across the charges the level has, and the 550-JP gift shortens every charge by 15 s.
-- `gift` is only for the tests; a live Scholar main always has the gift.
local function recharge_seconds(level, gift)
    local cap = max_charges(level)
    if cap <= 0 then return 0 end
    local seconds = math.floor(RECHARGE_TOTAL / cap)
    if gift ~= false then seconds = seconds - JP_RECHARGE_BONUS end
    return math.max(1, seconds)
end

local function is_helix(name)
    return tostring(name or ''):lower():find('helix', 1, true) ~= nil
end

-- ---------------------------------------------------------------------------------------------
-- the player

local function identity()
    local ok, index = pcall(function() return xi.game.player_index() end)
    if not ok or not index or index < 0 then return nil, 0 end
    local ok_name, name = pcall(function() return xi.game.entity(index, 'Name') end)
    name = ok_name and read_name(name) or nil
    if not name or name == '' then return nil, 0 end
    local ok_id, id = pcall(function() return xi.game.entity(index, 'ServerId') end)
    return name, tonumber(id) or 0
end

local function jobs()
    local function get(field)
        local ok, value = pcall(function() return xi.game.party_member(0, field) end)
        return ok and tonumber(value) or 0
    end
    return get('MainJob'), get('MainJobLevel'), get('SubJob'), get('SubJobLevel')
end

local function data_dir()
    local ok, path = pcall(function() return xi.paths.data end)
    return ok and type(path) == 'string' and path or ''
end

local function file_stem(name, id)
    local stem = tostring(name or 'default'):gsub('[^%w_%-]', '_')
    if stem == '' then stem = 'default' end
    return string.format('%s-%d', stem, tonumber(id) or 0)
end

-- ---------------------------------------------------------------------------------------------
-- persisted state

local function new_macro(id, title, spells, bursts, ebullience)
    return {
        id = id,
        title = title,
        spells = spells or {},
        bursts = bursts or {},
        ebullience = ebullience == true,
    }
end

local function default_state()
    local groups = {}
    for _, def in ipairs(GROUPS) do
        local group = { id = def.id, title = def.title, macros = {} }
        for index, pair in ipairs(def.pairs) do
            local closer = pair[#pair]
            local title = (is_helix(closer) and 'Helix: ' or 'Nuke: ') .. closer
            group.macros[#group.macros + 1] = new_macro(
                index, title, copy_array(pair), {}, false)
        end
        groups[#groups + 1] = group
    end
    return {
        version = VERSION,
        selected = 'liquefaction',
        groups = groups,
        charges = { count = nil, next_at = nil, level = nil, max = nil, timers = nil },
        window = { x = 560, y = 40, w = 720, h = 486 },
    }
end

local function sanitize_macro(raw, fallback_id)
    if type(raw) ~= 'table' then return nil end
    local spells = {}
    for _, value in ipairs(raw.spells or {}) do
        local name = clean_field(value, 40)
        if name ~= '' and #spells < SPELL_SLOTS then spells[#spells + 1] = name end
    end
    local bursts = {}
    for _, value in ipairs(raw.bursts or {}) do
        local name = clean_field(value, 40)
        if name ~= '' and #bursts < MAX_BURSTS then bursts[#bursts + 1] = name end
    end
    local title = clean_field(raw.title, 48)
    if title == '' then title = table.concat(spells, ' > ') end
    if #spells == 0 then return nil end
    return new_macro(tonumber(raw.id) or fallback_id, title, spells, bursts,
                     raw.ebullience == true)
end

local function sanitize_state(raw)
    local state = default_state()
    if type(raw) ~= 'table' then return state end
    if type(raw.window) == 'table' then
        state.window.x = math.floor(clamp(raw.window.x, -4000, 8000, state.window.x))
        state.window.y = math.floor(clamp(raw.window.y, -4000, 8000, state.window.y))
        state.window.w = math.floor(clamp(raw.window.w, 460, 1200, state.window.w))
        state.window.h = math.floor(clamp(raw.window.h, 260, 900, state.window.h))
    end
    local groups, seen_groups = {}, {}
    for _, rawGroup in ipairs(raw.groups or {}) do
        if type(rawGroup) == 'table' then
            local id = clean_field(rawGroup.id, 24):lower():gsub('%s+', '_')
            if id == '' then id = string.format('tab%d', #groups + 1) end
            if not seen_groups[id] then
                seen_groups[id] = true
                local group = { id = id, title = clean_field(rawGroup.title, 32), macros = {} }
                if group.title == '' then group.title = 'New tab' end
                local seen_macros = {}
                for index, rawMacro in ipairs(rawGroup.macros or {}) do
                    local macro = sanitize_macro(rawMacro, index)
                    if macro then
                        while seen_macros[macro.id] do macro.id = macro.id + 1 end
                        seen_macros[macro.id] = true
                        group.macros[#group.macros + 1] = macro
                    end
                end
                groups[#groups + 1] = group
            end
        end
    end
    -- An empty list is a legitimate state (the player deleted every tab), so only a
    -- missing groups table falls back to the defaults.
    if type(raw.groups) == 'table' then state.groups = groups end
    local selected = clean_field(raw.selected, 24)
    local found = false
    for _, group in ipairs(state.groups) do
        if group.id == selected then found = true break end
    end
    if not found then state.selected = state.groups[1] and state.groups[1].id or '' end
    if type(raw.charges) == 'table' then
        state.charges.count = tonumber(raw.charges.count)
        state.charges.next_at = tonumber(raw.charges.next_at)
        state.charges.level = tonumber(raw.charges.level)
        state.charges.max = tonumber(raw.charges.max)
        if type(raw.charges.timers) == 'table' then
            local timers = {}
            for _, value in ipairs(raw.charges.timers) do
                local at = tonumber(value)
                if at and at > 0 then timers[#timers + 1] = at end
            end
            table.sort(timers)
            state.charges.timers = timers
        end
    end
    return state
end

-- The file: TAB-separated lines, see the header.  Everything the editor accepts is
-- stripped of control characters first, so a line never needs escaping.
local function parse_state(source)
    if type(source) ~= 'string' or source == '' then return nil end
    local raw = { groups = {}, charges = {}, window = {} }
    local by_id = {}
    for line in source:gmatch('[^\n]+') do
        line = line:gsub('\r$', '')
        if line ~= '' and line:sub(1, 1) ~= '#' then
            local fields = {}
            for field in (line .. '\t'):gmatch('([^\t]*)\t') do
                fields[#fields + 1] = field
            end
            local kind = fields[1]
            if kind == 'version' then
                raw.version = tonumber(fields[2])
            elseif kind == 'window' then
                raw.window.x, raw.window.y = tonumber(fields[2]), tonumber(fields[3])
                raw.window.w, raw.window.h = tonumber(fields[4]), tonumber(fields[5])
            elseif kind == 'selected' then
                raw.selected = fields[2] or ''
            elseif kind == 'charges' then
                raw.charges.count = tonumber(fields[2])
                raw.charges.next_at = tonumber(fields[3])
                raw.charges.level = tonumber(fields[4])
                raw.charges.max = tonumber(fields[5])
                -- Version 2: one return time per missing charge, comma separated.  A
                -- version-1 line stops after `max`; the caller migrates from next_at.
                if fields[6] and fields[6] ~= '' then
                    local timers = {}
                    for value in fields[6]:gmatch('[^,]+') do
                        local at = tonumber(trim(value))
                        if at and at > 0 then timers[#timers + 1] = at end
                    end
                    table.sort(timers)
                    raw.charges.timers = timers
                end
            elseif kind == 'group' then
                local group = { id = fields[2] or '', title = fields[3] or '', macros = {} }
                raw.groups[#raw.groups + 1] = group
                by_id[group.id] = group
            elseif kind == 'macro' then
                local group = by_id[fields[2] or '']
                if group then
                    local spells = {}
                    for index = 6, 8 do
                        if fields[index] and fields[index] ~= '' then
                            spells[#spells + 1] = fields[index]
                        end
                    end
                    local bursts = {}
                    if fields[9] and fields[9] ~= '' then
                        for name in fields[9]:gmatch('[^,]+') do
                            bursts[#bursts + 1] = trim(name)
                        end
                    end
                    group.macros[#group.macros + 1] = {
                        id = tonumber(fields[3]) or (#group.macros + 1),
                        title = fields[4] or '',
                        ebullience = fields[5] == '1',
                        spells = spells,
                        bursts = bursts,
                    }
                end
            end
        end
    end
    if not raw.version and #raw.groups == 0 then return nil end
    return sanitize_state(raw)
end

-- The charge timers are written as epochs in a sixth field.  `next_at` stays as the
-- earliest one so a version-1 reader still shows the next charge.
local function serialized_charge_timers(charges)
    local out = {}
    for _, at in ipairs(charges.timers or {}) do
        local value = math.floor(tonumber(at) or 0)
        if value > 0 then out[#out + 1] = tostring(value) end
    end
    return table.concat(out, ',')
end

local function serialize_state(state)
    local lines = {
        '# Fanxi Scholar skillchain sets. TAB separated; see host/addons/lua/sch.lua.',
        string.format('version\t%d', VERSION),
        string.format('window\t%d\t%d\t%d\t%d', state.window.x, state.window.y,
                      state.window.w, state.window.h),
        'selected\t' .. tostring(state.selected or ''),
        string.format('charges\t%d\t%d\t%d\t%d\t%s',
                      math.floor(tonumber(state.charges.count) or 0),
                      math.floor(tonumber(state.charges.next_at) or 0),
                      math.floor(tonumber(state.charges.level) or 0),
                      math.floor(tonumber(state.charges.max) or 0),
                      serialized_charge_timers(state.charges)),
    }
    for _, group in ipairs(state.groups) do
        lines[#lines + 1] = string.format('group\t%s\t%s', group.id, group.title)
        for _, macro in ipairs(group.macros) do
            local spells = {}
            for slot = 1, SPELL_SLOTS do spells[slot] = macro.spells[slot] or '' end
            lines[#lines + 1] = string.format(
                'macro\t%s\t%d\t%s\t%d\t%s\t%s\t%s\t%s', group.id,
                math.floor(tonumber(macro.id) or 0), macro.title,
                macro.ebullience and 1 or 0, spells[1], spells[2], spells[3],
                table.concat(macro.bursts or {}, ','))
        end
    end
    return table.concat(lines, '\n') .. '\n'
end

local function load_file(path)
    if not path or path == '' then return nil end
    local ok, file = pcall(io.open, path, 'rb')
    if not ok or not file then return nil end
    local source = file:read('*a')
    file:close()
    return parse_state(source)
end

local function save_state()
    if not S.path or not S.state then return false end
    local ok, err = pcall(function()
        if xi.fs and xi.fs.mkdir then xi.fs.mkdir(data_dir() .. 'sch') end
        local file = io.open(S.path, 'wb')
        if not file then error('cannot open ' .. S.path) end
        file:write(serialize_state(S.state))
        file:close()
    end)
    if not ok then
        if not S.save_warned then
            S.save_warned = true
            notify('Scholar: could not save sets (' .. tostring(err) .. ')')
        end
        return false
    end
    S.dirty = false
    S.last_save = clock()
    return true
end

local function mark_dirty()
    S.dirty = true
end

-- ---------------------------------------------------------------------------------------------
-- strategem charges

local function current_group()
    local state = S.state
    if not state then return nil end
    for _, group in ipairs(state.groups) do
        if group.id == state.selected then return group end
    end
    return state.groups[1]
end

local function find_group(id)
    for _, group in ipairs(S.state and S.state.groups or {}) do
        if group.id == id then return group end
    end
    return nil
end

local function find_macro(group, id)
    if not group then return nil end
    for _, macro in ipairs(group.macros) do
        if macro.id == tonumber(id) then return macro end
    end
    return nil
end

-- Bring the charge count up to date from one return time per missing charge.  The
-- invariant is `count + #timers == max`; the timers are sorted, earliest first.
--
-- A version-1 save stored only `next_at`, the first of what the old model assumed was
-- a serial queue.  The other spends are not in the file, so treat them as back-to-back
-- with it: those charges all return at `next_at`, which is what a player who spent them
-- together sees.  The old serialized clock made every later charge wait another full
-- interval (two back-to-back stratagems looked 66 s away instead of ~33 s).
local function normalize_charge_timers(charges, cap, now, recharge)
    local migrated = type(charges.timers) ~= 'table'
    local timers = {}
    if not migrated then
        for _, value in ipairs(charges.timers) do
            local at = tonumber(value)
            if at and at > 0 then timers[#timers + 1] = at end
        end
    end
    table.sort(timers)
    charges.count = tonumber(charges.count) or cap
    charges.count = math.max(0, math.min(cap, charges.count))
    local missing = cap - charges.count
    if #timers > missing then
        for index = #timers, missing + 1, -1 do timers[index] = nil end
    end
    if migrated then
        local at = tonumber(charges.next_at)
        if not at or at <= 0 then at = now + recharge end
        while #timers < missing do timers[#timers + 1] = at end
    else
        while #timers < missing do
            local at = (#timers > 0 and timers[#timers] or now) + recharge
            timers[#timers + 1] = at
        end
    end
    -- A rate change (or the old 240 s constant) can leave a timer further out than one
    -- charge now takes; pull it in so the gauge cannot stick for minutes.
    local limit = now + recharge
    for index = 1, #timers do
        if timers[index] > limit then timers[index] = limit end
    end
    table.sort(timers)
    charges.timers = timers
    charges.next_at = timers[1]
end

local function charge_level(charges)
    local level = tonumber(charges and charges.level)
    if level and level > 0 then return level end
    return select(2, jobs())
end

local function refresh_charges()
    local state = S.state
    if not state then return end
    local main, level = jobs()
    -- The HUD belongs to a Scholar main.  On another job leave the saved clock alone:
    -- its level has a different charge count, and charging it would either drop or
    -- invent charges for the Scholar the player comes back to.
    if main ~= JOB_SCHOLAR then return end
    local cap = max_charges(level)
    local charges = state.charges
    if charges.level ~= level or charges.max ~= cap then
        charges.level, charges.max = level, cap
        if charges.count == nil then charges.count = cap end
    end
    if cap <= 0 then
        charges.count, charges.timers, charges.next_at = 0, {}, nil
        return
    end
    local now = now_epoch()
    local recharge = recharge_seconds(level)
    local before_count = charges.count
    local before_next = charges.next_at
    local before_n = type(charges.timers) == 'table' and #charges.timers or -1
    normalize_charge_timers(charges, cap, now, recharge)
    local count = charges.count
    local timers = charges.timers
    local index = 1
    while index <= #timers and count < cap do
        -- A logout can be hours long: every timer in the past completes, not just the
        -- first, and each one adds a charge.
        if timers[index] <= now then
            count = count + 1
            table.remove(timers, index)
        else
            index = index + 1
        end
    end
    if count >= cap then
        charges.count, charges.timers, charges.next_at = cap, {}, nil
    else
        charges.count, charges.next_at = count, timers[1]
    end
    if charges.count ~= before_count or charges.next_at ~= before_next
            or (type(charges.timers) == 'table' and #charges.timers or -1) ~= before_n then
        mark_dirty()
    end
end

local function spend_charge(count)
    local state = S.state
    if not state then return end
    local charges = state.charges
    local level = charge_level(charges)
    local recharge = recharge_seconds(level)
    if recharge <= 0 then return end
    local cap = tonumber(charges.max) or max_charges(level)
    local now = now_epoch()
    normalize_charge_timers(charges, cap, now, recharge)
    local spent = 0
    for _ = 1, math.max(1, tonumber(count) or 1) do
        if (charges.count or 0) > 0 then
            charges.count = charges.count - 1
            -- Each spend starts its own recharge, so back-to-back abilities return
            -- back-to-back one interval later, not one interval per charge apart.
            charges.timers[#charges.timers + 1] = now + recharge
            spent = spent + 1
        end
    end
    table.sort(charges.timers)
    charges.next_at = charges.timers[1]
    if (charges.count or 0) >= cap then
        charges.timers, charges.next_at = {}, nil
    end
    if spent > 0 then mark_dirty() end
end

-- Ebullience raises the next black-magic spell's damage, so it belongs in front of the
-- magic burst, not the opener: checked off before the chain it would be spent on the
-- opener and the burst would get nothing.  A macro with no burst list has no burst to
-- raise, so the flag costs no charge.
local function needs_ebullience(macro)
    return macro.ebullience == true and #(macro.bursts or {}) > 0
end

local function charges_needed(macro)
    return #(macro.spells or {}) + (needs_ebullience(macro) and 1 or 0)
end

-- The wall-clock second at which `needed` charges are in hand.  Zero means now.  The
-- needed-th missing charge is its own timer, so two charges spent a second apart are
-- one second apart, not a full recharge interval.
local function ready_at(needed)
    local charges = S.state and S.state.charges or {}
    local count = tonumber(charges.count) or 0
    if count >= needed then return 0 end
    local index = needed - count
    local timer = type(charges.timers) == 'table' and tonumber(charges.timers[index]) or nil
    if timer then return timer end
    local recharge = recharge_seconds(charge_level(charges))
    if recharge <= 0 then return 0 end
    return now_epoch() + recharge + (index - 1) * recharge
end

-- ---------------------------------------------------------------------------------------------
-- spells

local function build_catalog()
    local main, main_level, sub, sub_level = jobs()
    local key = string.format('%d:%d:%d:%d', main, main_level, sub, sub_level)
    if S.catalog_key == key and S.catalog then return S.catalog end
    local list, seen = {}, {}
    local ok, ids = pcall(function() return xi.res.spell_ids() end)
    if not ok or type(ids) ~= 'table' then ids = {} end
    for _, raw in ipairs(ids) do
        local id = tonumber(raw)
        local ok_spell, spell = pcall(function() return xi.res.spell(id) end)
        if ok_spell and type(spell) == 'table' then
            local name = read_name(spell.name)
            local element = tonumber(spell.element) or 0
            local levels = spell.levels
            local usable = false
            -- ``type`` 8 is a Trust; the skill filter keeps buffs, songs, cures,
            -- enfeebles and the Dark Magic utility spells (Drain, Aspir, Stun) out of a
            -- picker meant for spells that actually open or close a chain.
            local skill = tonumber(spell.skill) or 0
            local castable_skill = skill == 32 or skill == 36 or skill == 39
            if name and name ~= '' and element >= 0 and element <= 7
                    and tonumber(spell.type) ~= 8 and castable_skill then
                if type(levels) == 'table' then
                    local main_level_needed = tonumber(levels[main]) or 0
                    local sub_level_needed = tonumber(levels[sub]) or 0
                    if main_level_needed > 0 and main_level_needed <= main_level then
                        usable = true
                    elseif sub_level_needed > 0 and sub_level_needed <= sub_level then
                        usable = true
                    end
                    -- Job-point spells carry a sentinel level and a per-job bit mask.
                    local mask = tonumber(spell.job_point_mask) or 0
                    if not usable and main > 0 and main_level >= 99 and mask > 0
                            and math.floor(mask / (2 ^ main)) % 2 == 1 then
                        usable = true
                    end
                end
            end
            if usable and not seen[name] then
                seen[name] = true
                list[#list + 1] = {
                    name = name, id = id, element = element,
                    prop = ELEMENT_PROPERTY[element] or 0,
                    cast = tonumber(spell.cast_time) or 0,
                    mp = tonumber(spell.mp) or 0,
                }
            end
        end
    end
    table.sort(list, function(a, b)
        local an, bn = a.name:lower(), b.name:lower()
        if an == bn then return a.id < b.id end
        return an < bn
    end)
    S.catalog_key, S.catalog = key, list
    S.catalog_by_name = S.catalog_by_name or {}
    for name in pairs(S.catalog_by_name) do S.catalog_by_name[name] = nil end
    for _, entry in ipairs(list) do S.catalog_by_name[entry.name:lower()] = entry end
    return list
end

local function spell_info(name)
    build_catalog()
    return S.catalog_by_name and S.catalog_by_name[tostring(name or ''):lower()] or nil
end

local function spell_prop(name)
    local info = spell_info(name)
    return info and info.prop or 0
end

local function cast_seconds(name)
    local info = spell_info(name)
    if not info or info.cast <= 0 then return 2.0 end
    -- The client's cast_time is in quarter seconds.
    return math.max(0.5, info.cast * 0.25)
end

-- ---------------------------------------------------------------------------------------------
-- what a sequence will form

-- Walk the spells as the server walks them: the first opens with its element property,
-- each later spell closes against the current resonance, and a spell that does not
-- match replaces the opening.  Returns the final chain id and one row per step.
local function preview_chain(spells)
    local rows = {}
    local props, tier, sc = nil, 0, 0
    for index, name in ipairs(spells or {}) do
        name = clean_field(name, 40)
        if name == '' then break end
        local prop = spell_prop(name)
        local formed = 0
        if prop == 0 then
            props, tier, sc = nil, 0, 0
        elseif not props then
            props, tier, sc = { prop, 0, 0 }, 0, 0
        else
            local resonance = tier > 0 and { sc } or props
            for _, value in ipairs(resonance) do
                if value > 0 and SC_TRANS[prop] and SC_TRANS[prop][value] then
                    formed = SC_TRANS[prop][value]
                    break
                end
            end
            if formed > 0 then
                props, tier, sc = { prop, 0, 0 }, SC_TIER[formed] or 0, formed
            else
                props, tier, sc = { prop, 0, 0 }, 0, 0
            end
        end
        rows[#rows + 1] = { name = name, prop = prop, formed = formed }
    end
    return sc, rows
end

local function sc_name(id)
    return SC_NAMES[tonumber(id) or 0] or 'None'
end

-- ---------------------------------------------------------------------------------------------
-- running a macro

local function run_phase(text)
    if S.run then S.run.phase = text end
end

local function stop_run(silent)
    local run = S.run
    if not run then return end
    run.cancelled = true
    if run.task and xi.tasks and xi.tasks.cancel then pcall(xi.tasks.cancel, run.task) end
    S.run = nil
    if not silent then notify('Scholar: sequence stopped.') end
end

local function run_macro(group, macro)
    if not S.state then return end
    if S.run then
        notify('Scholar: a skillchain is already running; stop it first.')
        return
    end
    refresh_charges()
    local needed = charges_needed(macro)
    local charges = S.state.charges
    if (charges.count or 0) < needed then
        local wait = ready_at(needed) - now_epoch()
        notify(string.format(
            'Scholar: %s needs %d strategems, %d left; next SC in %s.',
            macro.title, needed, charges.count or 0, clock_text(wait)))
        return
    end
    local _, level = jobs()
    if max_charges(level) <= 0 then
        notify('Scholar: a Scholar main job is needed to use Immanence.')
        return
    end
    local run = {
        group_id = group.id,
        macro_id = macro.id,
        title = macro.title,
        spells = copy_array(macro.spells),
        bursts = copy_array(macro.bursts),
        ebullience = needs_ebullience(macro),
        started = clock(),
        phase = 'starting',
        cancelled = false,
    }
    S.run = run
    run.task = xi.tasks.spawn(function()
        local function step(line, phase)
            if run.cancelled then return false end
            if phase then run_phase(phase) end
            local ok, err = pcall(xi.chat.run, line, 1)
            if not ok then notify('Scholar: ' .. tostring(err)) end
            return ok
        end
        -- Polling a state; the only "seconds" left are failure limits.  The sequence
        -- follows the server's own action results, not a guessed beat.
        local function wait_until(pred, timeout)
            local deadline = clock() + timeout
            while clock() < deadline do
                if run.cancelled then return false end
                if pred() then return true end
                coroutine.sleep(0.03)
            end
            return false
        end
        local function wait(seconds)
            if run.cancelled then return end
            coroutine.sleep(seconds)
        end

        -- Immanence and Ebullience share recast id 231.  This table is still useful
        -- for the one server rule that is not in a result: the shared recast.
        local stratagem_slot
        for slot = 0, 255 do
            local ok, _, rid = pcall(xi.game.ability_recast, slot)
            if ok and tonumber(rid) == 231 then
                stratagem_slot = slot
                break
            end
        end
        local function stratagem_timer()
            if not stratagem_slot then return nil end
            local ok, timer = pcall(xi.game.ability_recast, stratagem_slot)
            if not ok then return nil end
            return tonumber(timer) or 0
        end
        local function wait_stratagem_ready(timeout)
            local timer = stratagem_timer()
            if timer == nil then return true end
            local deadline = clock() + timeout
            while clock() < deadline do
                if timer <= 0 then return true end
                if run.cancelled then return false end
                coroutine.sleep(0.03)
                timer = stratagem_timer()
            end
            return timer ~= nil and timer <= 0
        end

        local function confirmed(before, category, id)
            local log = S.action_log
            if not log then return false end
            for index = 1, 16 do
                local action = log[index]
                if action and action.seq > before and action.category == category
                        and (not id or action.id == id) then
                    return true
                end
            end
            return false
        end

        -- The server's ABILITY_FINISH result (category 6) is the proof the ability
        -- really ran.  No result means the client dropped the /ja inside its own
        -- animation; try again, but only after the shared recast is clear.  Four
        -- attempts cover the two-second animation without any sleep standing in
        -- for it.
        local function use_stratagem(line, phase, ability_id)
            for attempt = 1, 4 do
                if not wait_stratagem_ready(3.0) then
                    notify('Scholar: ' .. phase .. ' is still on recast; sequence stopped.')
                    run.cancelled = true
                    return false
                end
                local before = S.action_seq or 0
                if not step(line, phase) then return false end
                if wait_until(function() return confirmed(before, 6, ability_id) end, 0.7) then
                    return true
                end
            end
            notify('Scholar: ' .. phase .. ' did not answer; sequence stopped.')
            run.cancelled = true
            return false
        end

        local function cast_count()
            local ok, count = pcall(function() return xi.game.castbar('Count') end)
            if not ok then return nil end
            return tonumber(count) or 0
        end
        local function cast_spell(name, phase)
            local info = spell_info(name)
            local spell_id = info and tonumber(info.id) or nil
            local before
            local function send()
                before = S.action_seq or 0
                step(string.format('/ma "%s" <t>', name), phase or name)
            end
            local function started()
                if (cast_count() or 0) > 0.001 then return true end
                return confirmed(before, 8, spell_id) or confirmed(before, 4, spell_id)
            end
            send()
            -- Four attempts cover the two-second ability animation: a /ma sent
            -- inside it is dropped, and the fourth goes out after it ends.
            for attempt = 2, 4 do
                if wait_until(started, 0.8) then break end
                send()
            end
            if not wait_until(started, 1.0) then
                if cast_count() == nil and (S.action_seq or 0) == (before or 0) then
                    -- A host with no cast bar and no action stream: the catalog's
                    -- cast time is the only information left.
                    wait(cast_seconds(name) + 0.8)
                    return true
                end
                notify('Scholar: ' .. name .. ' did not start; sequence stopped.')
                run.cancelled = true
                return false
            end
            -- The finished-spell result (category 4) is the real end of the cast,
            -- and it is the packet that carries a skillchain and opens the burst
            -- window.  The next step starts as soon as it lands.
            if not wait_until(function() return confirmed(before, 4, spell_id) end,
                              cast_seconds(name) + 5.0) then
                notify('Scholar: ' .. name .. ' did not finish; sequence stopped.')
                run.cancelled = true
                return false
            end
            return true
        end

        local ok, err = pcall(function()
            if run.cancelled then return end
            for index, name in ipairs(run.spells) do
                if run.cancelled then break end
                if not use_stratagem('/ja "Immanence" <me>', 'Immanence', 317) then break end
                if run.cancelled then break end
                cast_spell(name, name)
            end
            if run.cancelled then return end
            -- Ebullience belongs in front of the burst: used before the chain it is
            -- spent on the opener and the burst it was meant to raise gets nothing.
            if run.ebullience then
                if not use_stratagem('/ja "Ebullience" <me>', 'Ebullience', 221) then return end
            end
            for index, name in ipairs(run.bursts) do
                if run.cancelled then break end
                cast_spell(name, string.format('Magic Burst %d/%d: %s', index, #run.bursts, name))
            end
        end)
        if not ok then notify('Scholar: sequence error: ' .. tostring(err)) end
        if S.run == run then S.run = nil end
    end)
end

-- ---------------------------------------------------------------------------------------------
-- the editor, picker and confirmations

local function next_macro_id(group)
    local highest = 0
    for _, macro in ipairs(group.macros or {}) do
        highest = math.max(highest, tonumber(macro.id) or 0)
    end
    return highest + 1
end

local function open_editor(group, macro)
    group = group or current_group()
    if not group then return end
    local draft = {
        mode = macro and 'edit' or 'new',
        group_id = group.id,
        macro_id = macro and macro.id or nil,
        title = macro and macro.title or '',
        spells = { '', '', '' },
        bursts = copy_array(macro and macro.bursts or {}),
        ebullience = macro and macro.ebullience == true or false,
        focus = true,
        bufs = {},
    }
    for slot = 1, SPELL_SLOTS do
        draft.spells[slot] = macro and macro.spells[slot] or ''
    end
    draft.bufs.title = { draft.title }
    S.editor = draft
    S.picker = nil
end

local function close_editor()
    S.editor = nil
    S.picker = nil
end

local function editor_save()
    local draft = S.editor
    if not draft then return end
    local spells = {}
    for slot = 1, SPELL_SLOTS do
        local name = clean_field(draft.spells[slot], 40)
        if name ~= '' then spells[#spells + 1] = name end
    end
    if #spells < 2 then
        notify('Scholar: a skillchain macro needs at least two spells.')
        return
    end
    local title = clean_field(draft.title, 48)
    if title == '' then title = table.concat(spells, ' > ') end
    local bursts = {}
    for _, name in ipairs(draft.bursts or {}) do
        name = clean_field(name, 40)
        if name ~= '' and #bursts < MAX_BURSTS then bursts[#bursts + 1] = name end
    end
    local group = find_group(draft.group_id) or current_group()
    if not group then
        notify('Scholar: no tab to save this macro into.')
        return
    end
    if draft.mode == 'edit' then
        local target = find_macro(group, draft.macro_id)
        if target then
            target.title = title
            target.spells = spells
            target.bursts = bursts
            target.ebullience = draft.ebullience == true
        else
            group.macros[#group.macros + 1] = new_macro(
                next_macro_id(group), title, spells, bursts, draft.ebullience)
        end
    else
        group.macros[#group.macros + 1] = new_macro(
            next_macro_id(group), title, spells, bursts, draft.ebullience)
    end
    S.state.selected = group.id
    S.title_buf_key = nil
    close_editor()
    mark_dirty()
    save_state()
end

local function delete_macro(group, macro)
    if not group or not macro then return end
    for index, candidate in ipairs(group.macros) do
        if candidate.id == macro.id then
            table.remove(group.macros, index)
            break
        end
    end
    if S.run and S.run.macro_id == macro.id and S.run.group_id == group.id then
        stop_run(true)
    end
    mark_dirty()
    save_state()
end

local function open_group_editor()
    S.group_editor = { title = { 'New tab' }, focus = true }
end

local function group_editor_save()
    local draft = S.group_editor
    if not draft then return end
    local title = clean_field(draft.title[1], 32)
    if title == '' then title = 'New tab' end
    local id, base = title:lower():gsub('[^%w]+', '_'), 1
    if id == '' then id = 'tab' end
    while find_group(id) do
        base = base + 1
        id = string.format('%s_%d', title:lower():gsub('[^%w]+', '_'), base)
    end
    local group = { id = id, title = title, macros = {} }
    S.state.groups[#S.state.groups + 1] = group
    S.state.selected = id
    S.title_buf_key = nil
    S.group_editor = nil
    mark_dirty()
    save_state()
end

local function delete_group(group)
    if not group then return end
    for index, candidate in ipairs(S.state.groups) do
        if candidate.id == group.id then
            table.remove(S.state.groups, index)
            break
        end
    end
    if S.run and S.run.group_id == group.id then stop_run(true) end
    local next_group = S.state.groups[math.max(1, #S.state.groups)]
    S.state.selected = next_group and next_group.id or ''
    S.title_buf_key = nil
    mark_dirty()
    save_state()
end

-- ---------------------------------------------------------------------------------------------
-- window helpers

local function text(api, color, value)
    api.TextColored(color, tostring(value))
end

local function button(api, label, color, width, height)
    if api.PushStyleColor and color then
        api.PushStyleColor(21, u32(color))
        api.PushStyleColor(22, u32({ math.min(1, color[1] * 1.18 + 0.02),
                                     math.min(1, color[2] * 1.18 + 0.02),
                                     math.min(1, color[3] * 1.18 + 0.02), color[4] or 1 }))
        api.PushStyleColor(23, u32({ color[1] * 0.7, color[2] * 0.7, color[3] * 0.7,
                                     color[4] or 1 }))
        local clicked = api.Button(label, { width or 74, height or 22 })
        api.PopStyleColor(3)
        return clicked
    end
    return api.Button(label, { width or 74, height or 22 })
end

local function dim_button(api, label, width, height)
    api.PushStyleColor(21, u32({ 0.11, 0.13, 0.16, 1 }))
    api.PushStyleColor(22, u32({ 0.15, 0.17, 0.21, 1 }))
    api.PushStyleColor(23, u32({ 0.10, 0.12, 0.15, 1 }))
    api.PushStyleColor(0, u32(COLORS.faint))
    local clicked = api.Button(label, { width, height })
    api.PopStyleColor(4)
    return clicked
end

local function section(api, title)
    api.Dummy({ 0, 2 })
    text(api, COLORS.cyan, string.upper(title))
    api.Separator()
end

local function spell_button(api, id, name, width)
    local label = (name and name ~= '' and name or '[ choose spell ]') .. '##' .. id
    local clicked = api.Button(label, { width or 150, 22 })
    if name and name ~= '' then
        local info = spell_info(name)
        if info then
            if api.SetTooltip and api.IsItemHovered and api.IsItemHovered() then
                api.SetTooltip(string.format('%s  ·  %s  ·  %s property',
                    name, ELEMENT_NAME[info.element + 1] or '?', sc_name(info.prop)))
            end
        end
    end
    return clicked
end

local function pips(api, count, cap, next_at, max_width)
    local x, y = api.GetCursorScreenPos()
    local draw = api.GetWindowDrawList()
    local radius = 6
    local gap = 15
    for index = 1, cap do
        local cx = x + radius + (index - 1) * gap
        if index <= count then
            draw:AddCircleFilled({ cx, y + 9 }, radius - 1, u32(COLORS.green))
        else
            draw:AddCircleFilled({ cx, y + 9 }, radius - 1, u32(COLORS.track))
            draw:AddCircle({ cx, y + 9 }, radius - 1, u32(COLORS.dim), 16, 1.5)
        end
    end
    -- The next charge fills a dot in the first empty pip as its interval runs down.
    if count < cap and next_at then
        local recharge = recharge_seconds(charge_level(S.state and S.state.charges))
        local fraction = recharge > 0
            and (1 - math.max(0, next_at - now_epoch()) / recharge) or 0
        fraction = clamp(fraction, 0, 1, 0)
        local cx = x + radius + count * gap
        draw:AddCircleFilled({ cx, y + 9 }, math.max(0.5, (radius - 1) * fraction), u32(COLORS.gold))
    end
    api.Dummy({ math.min(max_width or (cap * gap + 4), cap * gap + 4), 18 })
end

local function arts_line()
    local ok, buffs = pcall(function() return xi.game.player('Buffs') end)
    if not ok or type(buffs) ~= 'table' then return 'None', false end
    local set = {}
    for _, id in ipairs(buffs) do set[tonumber(id) or 0] = true end
    if set[ADDENDUM_BLACK] then return 'Addendum: Black', true end
    if set[DARK_ARTS] then return 'Dark Arts', true end
    if set[ADDENDUM_WHITE] then return 'Addendum: White', false end
    if set[LIGHT_ARTS] then return 'Light Arts', false end
    return 'None', false
end

-- ---------------------------------------------------------------------------------------------
-- the main window

function W.header(api, charges)
    local main = jobs()
    text(api, COLORS.gold, 'STRATAGEMS')
    api.SameLine(0, 8)
    pips(api, charges.count or 0, charges.max or 0, charges.next_at)
    api.SameLine(0, 6)
    text(api, COLORS.text, string.format('%d / %d', charges.count or 0, charges.max or 0))
    if charges.count and charges.max and charges.count < charges.max and charges.next_at then
        api.SameLine(0, 10)
        text(api, COLORS.dim, 'next ' .. clock_text(charges.next_at - now_epoch()))
    elseif charges.max and charges.max > 0 then
        api.SameLine(0, 10)
        text(api, COLORS.green, 'FULL')
    end
    if main ~= JOB_SCHOLAR then
        api.SameLine(0, 14)
        text(api, COLORS.gold, 'main SCH required')
    end
    local arts, dark = arts_line()
    api.SameLine(0, 16)
    text(api, dark and COLORS.violet or COLORS.dim, arts)
    if not dark then
        text(api, COLORS.gold, 'Immanence wants Dark Arts (Addendum: Black works too)')
    end
    if S.run then
        api.Separator()
        text(api, COLORS.green, 'RUNNING')
        api.SameLine(0, 8)
        text(api, COLORS.text, S.run.title)
        api.SameLine(0, 10)
        text(api, COLORS.dim, tostring(S.run.phase or ''))
        api.SameLine(0, 12)
        if button(api, 'Stop', COLORS.red, 54) then stop_run() end
    end
end

function W.tabs(api, width)
    local state = S.state
    local selected = current_group()
    for _, group in ipairs(state.groups) do
        local label = group.title
        local is_selected = selected and selected.id == group.id
        if api.Selectable(label .. '##tab_' .. group.id, is_selected, 0, { width, 18 }) then
            if not is_selected then
                state.selected = group.id
                S.title_buf_key = nil
                mark_dirty()
            end
        end
    end
    if #state.groups == 0 then
        text(api, COLORS.dim, 'No tabs yet.')
    end
    api.Dummy({ 0, 6 })
    api.Separator()
    if button(api, '+ New tab', COLORS.cyan, width) then open_group_editor() end
end

function W.macro_card(api, group, macro, width)
    local charges = S.state.charges
    local needed = charges_needed(macro)
    local have = charges.count or 0
    local ready = have >= needed
    local running = S.run and S.run.group_id == group.id and S.run.macro_id == macro.id
    local title = macro.title
    if needs_ebullience(macro) then title = title .. ' (Ebullience)' end
    local second = table.concat(macro.spells, ' > ')
    second = second .. '  ·  ' .. needed .. ' strat'
    if #macro.bursts > 0 then second = second .. '  ·  MB x' .. #macro.bursts end
    if not ready then
        second = second .. '  ·  next ' .. clock_text(ready_at(needed) - now_epoch())
    end
    local label = title .. '\n' .. second .. '##run_' .. group.id .. '_' .. macro.id
    local card_width = math.max(160, width - 74)
    local clicked
    if running then
        clicked = button(api, 'RUNNING  ' .. macro.title .. '\nclick to stop##stop_' .. macro.id,
                         COLORS.green, card_width, 44)
    elseif ready then
        clicked = button(api, label, COLORS.cyan, card_width, 44)
    else
        clicked = dim_button(api, label, card_width, 44)
    end
    if clicked then
        if running then
            stop_run()
        elseif ready then
            run_macro(group, macro)
        else
            notify(string.format('Scholar: %s is ready in %s (%d/%d strategems).',
                macro.title, clock_text(ready_at(needed) - now_epoch()), have, needed))
        end
    end
    api.SameLine(0, 4)
    if api.Button('Edit##edit_' .. group.id .. '_' .. macro.id, { 44, 44 }) then
        open_editor(group, macro)
    end
    api.SameLine(0, 2)
    if api.Button('x##del_' .. group.id .. '_' .. macro.id, { 22, 44 }) then
        S.confirm = { kind = 'macro', group_id = group.id, macro_id = macro.id }
    end
    api.Dummy({ 0, 2 })
end

function W.content(api, width)
    local group = current_group()
    if not group then
        text(api, COLORS.dim, 'Create a tab to start.')
        return
    end
    if S.title_buf_key ~= group.id then
        S.title_buf_key = group.id
        S.title_buf = { group.title }
    end
    if api.SetNextItemWidth then api.SetNextItemWidth(math.max(160, width)) end
    if api.InputText('##tab_title', S.title_buf, 64) then
        local title = clean_field(S.title_buf[1], 32)
        if title ~= '' then
            group.title = title
            mark_dirty()
        end
    end
    if api.Button('+ Macro##new_macro', { 76, 22 }) then open_editor(group, nil) end
    api.SameLine(0, 6)
    if api.Button('Delete tab##delete_tab', { 92, 22 }) then
        S.confirm = { kind = 'group', group_id = group.id }
    end
    api.SameLine(0, 10)
    local sc, _ = preview_chain(group.macros[1] and group.macros[1].spells or {})
    if #group.macros > 0 and sc > 0 then
        text(api, COLORS.dim, 'first macro: ' .. sc_name(sc))
    else
        text(api, COLORS.faint, tostring(#group.macros) .. ' macros')
    end
    api.Separator()
    if api.BeginChild('sch_macros', { 0, 0 }, false) then
        if #group.macros == 0 then
            text(api, COLORS.dim, 'No macros in this tab yet.  Use "+ Macro" to add one.')
        end
        for _, macro in ipairs(group.macros) do
            local inner = select(1, api.GetContentRegionAvail())
            W.macro_card(api, group, macro,
                math.max(200, math.min(width, inner or width)))
        end
        api.EndChild()
    end
end

function W.footer(api)
    api.Separator()
    local charges = S.state.charges
    local recharge = recharge_seconds(charge_level(charges))
    text(api, COLORS.faint, string.format(
        'Charges: %d/%d  ·  %s  ·  1 every %s', charges.count or 0, charges.max or 0,
        charges.next_at and ('next ' .. clock_text(charges.next_at - now_epoch())) or 'full',
        clock_text(recharge)))
    api.SameLine(0, 12)
    text(api, COLORS.faint, '//hud sch hides  ·  //sch sets')
end

-- A small live banner while a Magic Burst window is open on the current target.  The
-- client has no Magic Burst status; control.lua reads the window off the chain's 0x028
-- action and hands the skillchain and the time left here.
function W.burst_window(api)
    if not S.burst_info then return end
    local ok, info = pcall(S.burst_info)
    if not ok or type(info) ~= 'table' then return end
    local screen = 1280
    local okio, io = pcall(api.GetIO)
    if okio and io and io.DisplaySize then
        screen = tonumber(io.DisplaySize.x) or screen
    end
    local width, height = 260, 74
    api.SetNextWindowPos({ math.max(4, (screen - width) / 2), 8 }, 1)
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(0.92)
    local open = api.Begin('Magic Burst###fanxi_sch_mb', nil, 15)
    if open then
        text(api, COLORS.gold, 'MAGIC BURST WINDOW')
        local name = SC_NAMES[tonumber(info.sc) or 0] or 'Skillchain'
        text(api, COLORS.text, name)
        api.SameLine(0, 10)
        text(api, COLORS.cyan, string.format('%.1f s', tonumber(info.remaining) or 0))
    end
    api.End()
end

function W.window(api)
    local width, height = 900, 700
    local ok, io = pcall(api.GetIO)
    if ok and io and io.DisplaySize then
        width, height = tonumber(io.DisplaySize.x) or width, tonumber(io.DisplaySize.y) or height
    end
    local win = S.state.window
    local x = math.max(4, math.min(win.x or 560, width - (win.w or 720) - 4))
    local y = math.max(4, math.min(win.y or 40, height - (win.h or 486) - 4))
    api.SetNextWindowPos({ x, y }, S.window_force and 1 or 4)
    api.SetNextWindowSize({ win.w or 720, win.h or 486 }, 1)
    api.SetNextWindowBgAlpha(0.95)
    S.window_force = false
    local close = { true }
    local open = api.Begin(string.format('Scholar %d/%d###fanxi_sch_hud',
        S.state.charges.count or 0, S.state.charges.max or 0), close, 0)
    if not close[1] then
        if S.standalone then S.standalone_show = false end
        if S.on_hide then S.on_hide(false) end
    end
    if open then
        W.header(api, S.state.charges)
        api.Separator()
        local nav_width = 176
        if api.BeginChild('sch_tabs', { nav_width, -26 }, true) then
            W.tabs(api, nav_width - 20)
            api.EndChild()
        end
        api.SameLine(0, 8)
        local content_width = math.max(220, (win.w or 720) - nav_width - 34)
        if api.BeginChild('sch_content', { 0, -26 }, false) then
            local okc, err = pcall(W.content, api, content_width)
            if not okc then
                text(api, COLORS.red, tostring(err))
            end
            api.EndChild()
        end
        W.footer(api)
        if api.IsMouseReleased and api.IsMouseReleased(0) then
            local px, py = api.GetWindowPos()
            local sx, sy = api.GetWindowSize()
            if px and py then win.x, win.y = math.floor(px), math.floor(py) end
            if sx and sy then win.w, win.h = math.floor(sx), math.floor(sy) end
            mark_dirty()
        end
    end
    api.End()
end

-- ---------------------------------------------------------------------------------------------
-- the editor

function W.spell_row(api, slot, label, value, width)
    text(api, COLORS.dim, label)
    api.SameLine(0, 8)
    if spell_button(api, 'pick_spell_' .. slot, value, width) then
        S.picker = { target = 'spell', slot = slot, search = { '' }, focus = true }
    end
    if slot == SPELL_SLOTS then
        api.SameLine(0, 4)
        if api.Button('Clear##clear_' .. slot, { 46, 22 }) and S.editor then
            S.editor.spells[3] = ''
        end
    end
end

function W.editor(api)
    local draft = S.editor
    if not draft then return end
    local width, height = 900, 700
    local ok, io = pcall(api.GetIO)
    if ok and io and io.DisplaySize then
        width, height = tonumber(io.DisplaySize.x) or width, tonumber(io.DisplaySize.y) or height
    end
    local w, h = 496, 470
    local x = math.max(4, math.floor((width - w) / 2))
    local y = math.max(4, math.floor((height - h) / 2))
    api.SetNextWindowPos({ x, y }, 1)
    api.SetNextWindowSize({ w, h }, 1)
    api.SetNextWindowBgAlpha(0.98)
    if draft.focus then
        if api.SetNextWindowFocus then api.SetNextWindowFocus() end
        draft.focus = false
        S.focus_title = true
    end
    -- 32 NoCollapse + 2 NoResize + 4 NoMove + 256 NoSavedSettings (64 would be
    -- AlwaysAutoResize, which let the content grow the dialog past the screen edge).
    local open = api.Begin('SC macro###fanxi_sch_editor', nil, 32 + 2 + 4 + 256)
    if open then
        section(api, draft.mode == 'edit' and 'Edit macro' or 'New macro')
        text(api, COLORS.dim, 'Tab  ')
        api.SameLine(0, 8)
        local values, labels, at = {}, {}, 0
        for index, group in ipairs(S.state.groups) do
            values[index] = group.id
            labels[index] = group.title
            if group.id == draft.group_id then at = index - 1 end
        end
        local buf = { at }
        if api.SetNextItemWidth then api.SetNextItemWidth(230) end
        if api.Combo('##editor_group', buf, labels, #labels) then
            draft.group_id = values[(tonumber(buf[1]) or 0) + 1] or draft.group_id
        end
        text(api, COLORS.dim, 'Title')
        api.SameLine(0, 8)
        if api.SetNextItemWidth then api.SetNextItemWidth(310) end
        if S.focus_title and api.SetKeyboardFocusHere then api.SetKeyboardFocusHere() end
        S.focus_title = false
        if api.InputText('##editor_title', draft.bufs.title, 64) then
            draft.title = draft.bufs.title[1]
        end
        api.Dummy({ 0, 2 })
        W.spell_row(api, 1, 'Spell 1 ', draft.spells[1], 240)
        W.spell_row(api, 2, 'Spell 2 ', draft.spells[2], 240)
        if draft.spells[3] == '' then
            text(api, COLORS.dim, 'Spell 3 ')
            api.SameLine(0, 8)
            if api.Button('+ optional third spell##add_third', { 240, 22 }) then
                S.picker = { target = 'spell', slot = 3, search = { '' }, focus = true }
            end
        else
            W.spell_row(api, 3, 'Spell 3 ', draft.spells[3], 240)
        end
        local box = { draft.ebullience == true }
        if api.Checkbox('Use Ebullience##ebullience', box) then
            draft.ebullience = box[1] == true
        end
        text(api, COLORS.faint, #draft.bursts > 0
            and '        +1 strategem before the burst; title shows (Ebullience)'
            or '        no burst yet: unused, and no charge')

        local sc, rows = preview_chain(draft.spells)
        local parts = {}
        for _, row in ipairs(rows) do
            parts[#parts + 1] = row.name
        end
        local needed = 0
        for slot = 1, SPELL_SLOTS do
            if clean_field(draft.spells[slot], 40) ~= '' then needed = needed + 1 end
        end
        if needs_ebullience(draft) then needed = needed + 1 end
        api.Dummy({ 0, 2 })
        local preview = #parts > 0 and (table.concat(parts, ' > ') .. '  =  ' ..
            (sc > 0 and sc_name(sc) or 'no chain')) or 'Pick an opener and a closer.'
        text(api, sc > 0 and COLORS.green or COLORS.gold, preview)
        api.SameLine(0, 8)
        text(api, COLORS.dim, string.format('(%d strat)', needed))
        local group = find_group(draft.group_id)
        if group and sc > 0 and group.title ~= sc_name(sc) then
            text(api, COLORS.gold, string.format('This forms %s (tab: %s)', sc_name(sc), group.title))
        end
        api.Separator()
        text(api, COLORS.cyan, 'MAGIC BURST SEQUENCE')
        text(api, COLORS.faint, 'After the closing spell, inside the ~11 s window.')
        if api.BeginChild('sch_bursts', { 0, 88 }, true) then
            if #draft.bursts == 0 then
                text(api, COLORS.dim, 'None')
            end
            for index, name in ipairs(draft.bursts) do
                local info = spell_info(name)
                local label = name
                if info then label = label .. '  ·  ' .. (ELEMENT_NAME[info.element + 1] or '') end
                text(api, COLORS.text, string.format('%d. %s', index, label))
                api.SameLine(0, 8)
                if api.Button('x##burst_' .. index, { 20, 20 }) then
                    table.remove(draft.bursts, index)
                    mark_dirty()
                    break
                end
            end
            if #draft.bursts < MAX_BURSTS then
                if api.Button('+ Add burst spell##add_burst', { 156, 22 }) then
                    S.picker = { target = 'burst', search = { '' }, focus = true }
                end
            end
            api.EndChild()
        end
        api.Separator()
        if button(api, 'Save', COLORS.green, 96) then editor_save() end
        api.SameLine(0, 8)
        if button(api, 'Cancel', COLORS.dim, 80) then close_editor() end
        api.SameLine(0, 14)
        text(api, COLORS.faint, '2-3 spells; spell 3 optional')
    end
    api.End()
end

-- ---------------------------------------------------------------------------------------------
-- the spell picker

function W.picker(api)
    local picker = S.picker
    if not picker or not S.editor then return end
    local width, height = 900, 700
    local ok, io = pcall(api.GetIO)
    if ok and io and io.DisplaySize then
        width, height = tonumber(io.DisplaySize.x) or width, tonumber(io.DisplaySize.y) or height
    end
    local w, h = 380, 440
    local x = math.max(4, math.floor((width - w) / 2 + 36))
    local y = math.max(4, math.floor((height - h) / 2 + 24))
    api.SetNextWindowPos({ x, y }, 1)
    api.SetNextWindowSize({ w, h }, 1)
    api.SetNextWindowBgAlpha(0.99)
    if picker.focus then
        if api.SetNextWindowFocus then api.SetNextWindowFocus() end
        picker.focus = false
        picker.focus_search = true
    end
    local heading = picker.target == 'burst' and 'Magic burst spell'
        or ('Spell ' .. tostring(picker.slot or 1))
    local open = api.Begin('Choose spell###fanxi_sch_picker', nil, 32 + 2 + 4 + 256)
    if open then
        text(api, COLORS.cyan, heading)
        api.SameLine(0, 8)
        if api.Button('Close##picker_close', { 50, 20 }) then S.picker = nil end
        api.Separator()
        if api.SetNextItemWidth then api.SetNextItemWidth(336) end
        if picker.focus_search and api.SetKeyboardFocusHere then api.SetKeyboardFocusHere() end
        picker.focus_search = false
        api.InputText('Search##picker_search', picker.search, 64)
        api.Separator()
        local needle = trim(picker.search[1]):lower()
        local list = build_catalog()
        if api.BeginChild('sch_picker_list', { 0, 0 }, true) then
            local shown = 0
            for _, entry in ipairs(list) do
                if needle == '' or entry.name:lower():find(needle, 1, true) then
                    shown = shown + 1
                    local label = entry.name .. '  ·  ' .. (ELEMENT_NAME[entry.element + 1] or '')
                        .. ' (' .. sc_name(entry.prop) .. ')'
                    if api.Selectable(label .. '##pick_' .. entry.id, false, 0, { 330, 19 }) then
                        if picker.target == 'burst' then
                            local duplicate = false
                            for _, name in ipairs(S.editor.bursts) do
                                if name:lower() == entry.name:lower() then duplicate = true end
                            end
                            if not duplicate and #S.editor.bursts < MAX_BURSTS then
                                S.editor.bursts[#S.editor.bursts + 1] = entry.name
                            end
                        else
                            S.editor.spells[tonumber(picker.slot) or 1] = entry.name
                        end
                        S.picker = nil
                        mark_dirty()
                    end
                end
            end
            if shown == 0 then
                text(api, COLORS.dim, 'No spell matches that.')
            end
            api.EndChild()
        end
    end
    api.End()
end

-- ---------------------------------------------------------------------------------------------
-- confirmations and the new-tab dialog

function W.confirm(api)
    local confirm = S.confirm
    if not confirm then return end
    local width, height = 900, 700
    local ok, io = pcall(api.GetIO)
    if ok and io and io.DisplaySize then
        width, height = tonumber(io.DisplaySize.x) or width, tonumber(io.DisplaySize.y) or height
    end
    local w, h = 340, 138
    local x = math.max(4, math.floor((width - w) / 2))
    local y = math.max(4, math.floor((height - h) / 2))
    api.SetNextWindowPos({ x, y }, 1)
    api.SetNextWindowSize({ w, h }, 1)
    api.SetNextWindowBgAlpha(1)
    local open = api.Begin('Confirm###fanxi_sch_confirm', nil, 32 + 64 + 256)
    if open then
        if confirm.kind == 'macro' then
            local group = find_group(confirm.group_id)
            local macro = find_macro(group, confirm.macro_id)
            text(api, COLORS.text, 'Delete the macro "' .. tostring(macro and macro.title or '?') .. '"?')
        else
            local group = find_group(confirm.group_id)
            text(api, COLORS.text, 'Delete the tab "' .. tostring(group and group.title or '?')
                .. '"' .. (group and #group.macros > 0 and (' and its ' .. #group.macros .. ' macros') or '') .. '?')
        end
        api.Dummy({ 0, 8 })
        if button(api, 'Delete', COLORS.red, 92) then
            if confirm.kind == 'macro' then
                delete_macro(find_group(confirm.group_id), find_macro(find_group(confirm.group_id), confirm.macro_id))
            else
                delete_group(find_group(confirm.group_id))
            end
            S.confirm = nil
        end
        api.SameLine(0, 8)
        if button(api, 'Cancel', COLORS.dim, 80) then S.confirm = nil end
    end
    api.End()
end

function W.group_editor(api)
    local draft = S.group_editor
    if not draft then return end
    local width, height = 900, 700
    local ok, io = pcall(api.GetIO)
    if ok and io and io.DisplaySize then
        width, height = tonumber(io.DisplaySize.x) or width, tonumber(io.DisplaySize.y) or height
    end
    local w, h = 340, 142
    local x = math.max(4, math.floor((width - w) / 2))
    local y = math.max(4, math.floor((height - h) / 2))
    api.SetNextWindowPos({ x, y }, 1)
    api.SetNextWindowSize({ w, h }, 1)
    api.SetNextWindowBgAlpha(0.99)
    if draft.focus then
        if api.SetNextWindowFocus then api.SetNextWindowFocus() end
        draft.focus = false
        draft.focus_field = true
    end
    local open = api.Begin('New tab###fanxi_sch_group', nil, 32 + 64 + 256)
    if open then
        text(api, COLORS.cyan, 'Name the tab')
        if api.SetNextItemWidth then api.SetNextItemWidth(300) end
        if draft.focus_field and api.SetKeyboardFocusHere then api.SetKeyboardFocusHere() end
        draft.focus_field = false
        api.InputText('##group_title', draft.title, 48)
        api.Dummy({ 0, 6 })
        if button(api, 'Create', COLORS.green, 92) then group_editor_save() end
        api.SameLine(0, 8)
        if button(api, 'Cancel', COLORS.dim, 80) then S.group_editor = nil end
    end
    api.End()
end

-- ---------------------------------------------------------------------------------------------
-- install, draw and commands

-- The server's own 0x028 for one of our actions is the edge the sequencer follows:
-- 6 = job ability finished, 8 = cast started, 4 = spell landed.  Reading the three
-- fields here keeps the wait off the clock: a command the client dropped produces
-- no result, and a result is the proof the server accepted the action.
local function on_action(e)
    if not S.installed or e.blocked or e.injected or e.id ~= 0x028 then return end
    local data = e.modified or e.data
    if type(data) ~= 'string' or #data < 32 then return end
    local function at(pos, n)
        local v, got, i, off = 0, 0, math.floor(pos / 8), pos % 8
        while got < n do
            local b = data:byte(i + 1) or 0
            local take = math.min(8 - off, n - got)
            v = v + (math.floor(b / 2 ^ off) % 2 ^ take) * 2 ^ got
            got, off, i = got + take, 0, i + 1
        end
        return v
    end
    local index = xi.game.player_index()
    if not index or index < 0 then return end
    local me = xi.game.entity(index, 'ServerId')
    if not me or at(40, 32) ~= tonumber(me) then return end
    S.action_seq = (S.action_seq or 0) + 1
    local category, id = at(82, 4), at(86, 32)
    S.action = { seq = S.action_seq, category = category, id = id, at = clock() }
    -- An auto-attack packet can follow the result we are waiting for before the
    -- sequencer next polls; keep a short ring, not just the latest action.
    local log = S.action_log
    if not log then log = {}; S.action_log = log end
    S.action_count = (S.action_count or 0) + 1
    log[(S.action_count - 1) % 16 + 1] = S.action
    if category == 6 and STRATAGEM[id] then
        -- The gauge follows the server's ABILITY_FINISH, not the outgoing request:
        -- a refused use spends nothing, and a retransmit cannot spend twice.
        M.ensure()
        spend_charge(1)
        save_state()
    end
end

local function on_command(e)
    if e.blocked then return end
    local line = e.data
    if type(line) ~= 'string' then return end
    local rest = line:match('^//sch%s*(.*)$') or line:match('^//scholar%s*(.*)$')
        or line:match('^/%!sch%s*(.*)$')
    if not rest then return end
    e.blocked = true
    M.command(rest)
end

local function on_present()
    if not S.standalone then return end
    if S.standalone_show == nil then
        if not M.active() then return end
    elseif not S.standalone_show then
        return
    end
    local ok, api = pcall(xi.ui.imgui)
    if ok and api then pcall(M.draw, api) end
end

function M.install(ctx)
    ctx = ctx or {}
    S.ctx = ctx
    S.notify = ctx.notify or S.notify
    S.on_hide = ctx.on_hide
    S.get_shown = ctx.get_shown
    S.burst_info = ctx.burst_info
    S.standalone = ctx.standalone == true
    if ctx.show ~= nil then S.standalone_show = ctx.show end
    local first = not S.installed
    S.installed = true
    if first and xi.events and xi.events.on then
        xi.events.on('packet_in', on_action)
        xi.events.on('command', on_command)
        if S.standalone then xi.events.on('present', on_present) end
    end
    M.ensure()
    return M
end

function M.ensure()
    local name, id = identity()
    if not name then return false end
    if S.character ~= name or S.character_id ~= id then
        S.character, S.character_id = name, id
        S.path = data_dir() .. 'sch/' .. file_stem(name, id) .. '.sch'
        S.state = load_file(S.path) or default_state()
        S.state = sanitize_state(S.state)
        S.window_force = true
        S.title_buf_key = nil
        S.dirty = true
        S.last_save = 0
    end
    refresh_charges()
    return true
end

-- Kept out of the draw path for the same reason the HUD's own tick is: a hidden
-- window still has to recharge and save.
function M.tick()
    if not S.state then M.ensure() end
    if not S.state then return end
    refresh_charges()
    if S.dirty and clock() - (S.last_save or 0) >= SAVE_EVERY then
        save_state()
    end
end

function M.draw(api)
    if not S.installed then return end
    if not api then
        local ok, got = pcall(xi.ui.imgui)
        if not ok or not got then return end
        api = got
    end
    if not M.ensure() then return end
    M.tick()
    local ok, err = pcall(W.window, api)
    if not ok and not S.warned then
        S.warned = true
        notify('Scholar HUD: ' .. tostring(err))
    end
    if S.burst_info then
        local okb, errb = pcall(W.burst_window, api)
        if not okb and not S.warned then
            S.warned = true
            notify('Scholar HUD: ' .. tostring(errb))
        end
    end
    if S.editor then
        local ok2, err2 = pcall(W.editor, api)
        if not ok2 and not S.warned then
            S.warned = true
            notify('Scholar editor: ' .. tostring(err2))
        end
    end
    if S.picker then pcall(W.picker, api) end
    if S.group_editor then pcall(W.group_editor, api) end
    if S.confirm then pcall(W.confirm, api) end
end

function M.active()
    local main = jobs()
    return main == JOB_SCHOLAR
end

function M.charges()
    refresh_charges()
    local charges = S.state and S.state.charges or {}
    return {
        count = charges.count or 0,
        max = charges.max or 0,
        next_in = charges.next_at and math.max(0, charges.next_at - now_epoch()) or 0,
        next_at = charges.next_at,
    }
end

function M.snapshot()
    local charges = M.charges()
    return {
        count = charges.count,
        max = charges.max,
        next_in = charges.next_in,
        running = S.run ~= nil,
        macro = S.run and S.run.title or nil,
        tab = current_group() and current_group().title or nil,
        tabs = S.state and #S.state.groups or 0,
    }
end

-- The hidden command surface: `//sch` (toggle), `//sch on|off`, `//sch charges [n]`,
-- `//sch reset` (restore the twelve default tabs) and `//sch save`.
function M.command(rest)
    M.ensure()
    if not S.state then return end
    rest = trim(rest):lower()
    if rest == '' or rest == 'toggle' then
        local shown
        if S.get_shown then shown = S.get_shown() == true
        elseif S.standalone_show ~= nil then shown = S.standalone_show
        else shown = M.active() end
        shown = not shown
        if S.standalone then
            S.standalone_show = shown
        elseif S.on_hide then
            S.on_hide(shown)
        end
        notify('Scholar HUD: ' .. (shown and 'shown' or 'hidden'))
    elseif rest == 'on' or rest == 'off' then
        local shown = rest == 'on'
        if S.standalone then
            S.standalone_show = shown
        elseif S.on_hide then
            S.on_hide(shown)
        end
        notify('Scholar HUD: ' .. (shown and 'shown' or 'hidden'))
    elseif rest == 'save' then
        save_state()
        notify('Scholar: sets saved.')
    elseif rest == 'reset' then
        S.state.groups = default_state().groups
        S.state.selected = S.state.groups[1].id
        S.confirm = nil
        S.editor = nil
        S.title_buf_key = nil
        mark_dirty()
        save_state()
        notify('Scholar: the twelve default tabs are back.')
    elseif rest:match('^charges') then
        local value = tonumber(rest:match('^charges%s+(%d+)$'))
        if value then
            local _, level = jobs()
            local cap = max_charges(level)
            local count = clamp(value, 0, cap, 0)
            local now = now_epoch()
            local recharge = recharge_seconds(level)
            -- A manual correction has no real spend times; give each missing charge its
            -- own slot one interval apart from now.
            local timers = {}
            for index = 1, cap - count do timers[index] = now + index * recharge end
            S.state.charges.count = count
            S.state.charges.level = level
            S.state.charges.max = cap
            S.state.charges.timers = timers
            S.state.charges.next_at = timers[1]
            mark_dirty()
            save_state()
        end
        local charges = M.charges()
        notify(string.format('Scholar: %d/%d strategems, next in %s.',
            charges.count, charges.max, clock_text(charges.next_in)))
    elseif rest == 'stop' then
        stop_run()
    elseif rest == 'position' or rest == 'pos' then
        S.state.window.x, S.state.window.y = 560, 40
        S.state.window.w, S.state.window.h = 720, 486
        S.window_force = true
        mark_dirty()
        notify('Scholar: window recentred.')
    else
        notify('Scholar: //sch [on|off|toggle|save|reset|position|charges [n]|stop]')
    end
end

-- ---------------------------------------------------------------------------------------------
-- the pieces the tests use

M._internal = {
    max_charges = max_charges,
    recharge_seconds = recharge_seconds,
    preview_chain = preview_chain,
    spend_charge = spend_charge,
    refresh_charges = refresh_charges,
    ready_at = ready_at,
    charges_needed = charges_needed,
    cast_seconds = cast_seconds,
    default_state = default_state,
    sanitize_state = sanitize_state,
    parse_state = parse_state,
    serialize_state = serialize_state,
    is_helix = is_helix,
    state = function() return S end,
    run_macro = run_macro,
    stop_run = stop_run,
    editor_open = open_editor,
    editor_save = editor_save,
    windows = W,
    save_state = save_state,
    set_state = function(state)
        S.state = state
        S.installed = true
        S.character = 'Test'
        S.character_id = 1
        S.path = nil
    end,
}

return M
