--[==[
The control port: a built-in addon (xi kind) that lets another program drive the game. host64 loads
it on the first frame when FFXI_CONTROL is set (core.c): FFXI_CONTROL=1 listens on 127.0.0.1:54300,
FFXI_CONTROL=<port> on that port. tools/xi_mcp.py speaks it for MCP clients.

The protocol is JSON, one object per line each way:

  -> {"id": 1, "cmd": "state", "args": {...}}
  <- {"id": 1, "ok": true, "result": ...}    or    {"id": 1, "ok": false, "error": "..."}

Requests run as tasks on the game thread (one frame at a time, so a request may wait on frames:
key holds, frame captures, waits). Commands:

  state                      sign-in state, the player, zone, position, target, menu, chat input
  chat_send {line}           a line as if typed: /commands, //commands; other text is said (/say)
  chat_log {since, limit}    chat lines after sequence number `since`: what the chat log shows
                             (UTF-8, codes removed)
  chat_input {text, open}    the chat input line: read it, or set its text
  keys {keys, hold_ms, gap_ms}  key presses in order: "enter", "down", "numpad5", "ctrl+t",
                             "wait:500" (ms); down for hold_ms, then up, gap_ms between
  key {key, down}            one key down (true) or up (false), left as it is
  release_keys               every key this port pressed comes up
  capture {path}             the next frame to a file (see d3d8_capture); -> path, w, h, format
  entities {radius, limit}   entities near the player: index, id, name, type, distance, hp%
  target {index}             target an entity as the game does
  wait {ms | frames}         returns after that long
  lua {code}                 Lua run in this addon (xi.* available): what it returns, as JSON
  command {line}             run a line as if typed, without the /say fallback: !zone, !merits, /heal
  metrics                    state + EXP/hr, DPS, damage and the active gear of this client
  gear                       the item, count and encumbrance bit in every equipment slot
  equip {slot, item}         wear the named item from this character's bags
  equip_set {items}          wear a GearSwap-style set: [{slot="head", item="..."}, ...], every
                             0x050 in one frame (as GearSwap's equip burst does) and pieces
                             already worn left alone
  gearswap {path}            read a GearSwap Lua file and return its sets as data (read-only)
  phase {path|sets, enabled, engaged, idle_town, idle_field, move, kite, rest,
         precast, midcast, default_ws, default_ja, focus, ws_overrides, ja_overrides,
         spell_overrides, spell_category_overrides}
                             precast / midcast / state engine: the host holds the action packet,
                             wears the precast set, sends it, then wears the midcast set behind
                             it, and returns to the state set. spell_category_overrides keys
                             are enfeebles_macc, enfeebles_duration, buff_potency,
                             buff_duration and helix_magic; a spell uses its category's set
                             unless a per-spell override names one
  phase_status               the engine's rules, counters, state, active set and slot pins
  phase_lock {locked}        hold the set that is worn now (true) or resume auto-swaps (false)
  phase_kiting {on}          forced kiting state, on until switched off
  phase_resting {on}         manual resting state (this server has no rest packet)
  phase_focus {mode}         idle focus: auto, dt, pdt, mdt, eva or meva
  phase_lock_slots {mask}    pin equipment slots (bit 0 main .. bit 15 back) out of every set
  job_spells                 the current job pair's spell list for the override form, with the
                             override categories (enfeebles_macc, buff_duration, ...) of each
  job_abilities              the current main/sub job abilities the client's menu lists
  hud {show_abilities, show_spells, show_trusts, show_weapon_skills, edit, type,
       layout, columns, size, labels, font, tabs, group, custom_groups, assign_key,
       assign_group, opacity, menu_hide, reset_positions}
                             the four in-game HUD windows: toggle, per-type re-layout/grouping,
                             edit/drag mode, menu-side hiding and position reset; returns the
                             saved state (also in metrics.hud)
  weapons                    equipment in the bags for main/sub/ranged/ammo the main job can use
  bag_items {container}      every item in one client container (diagnostic; scans slots 1..80)
  icons {ids}                item icons as top-down RGBA hex, decoded from the game's DATs
  item_ids {names}           item name -> id, for launcher-side set previews
--]==]

local socket = require('socket.core')

local PORT = tonumber(os.getenv('FFXI_CONTROL') or '') or 1
if PORT <= 1 then PORT = 54300 end

local game, res, memory = xi.game, xi.res, xi.memory

-------------------------------------------------------------------------------- JSON

local json = {}

local escapes = { ['"'] = '\\"', ['\\'] = '\\\\', ['\b'] = '\\b', ['\f'] = '\\f', ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t' }

local function encode(v, out, depth)
    local t = type(v)
    if depth > 32 then out[#out + 1] = 'null' return end
    if t == 'nil' then
        out[#out + 1] = 'null'
    elseif t == 'boolean' then
        out[#out + 1] = v and 'true' or 'false'
    elseif t == 'number' then
        if v ~= v or v == math.huge or v == -math.huge then out[#out + 1] = 'null'
        elseif v == math.floor(v) and math.abs(v) < 2^53 then out[#out + 1] = string.format('%d', v)
        else out[#out + 1] = string.format('%.6g', v) end
    elseif t == 'string' then
        out[#out + 1] = '"' .. v:gsub('[%c"\\]', function(c) return escapes[c] or string.format('\\u%04x', c:byte()) end) .. '"'
    elseif t == 'table' then
        local n = #v
        local is_array = n > 0 or next(v) == nil
        if is_array then
            for k in pairs(v) do
                if type(k) ~= 'number' or k < 1 or k > n or k ~= math.floor(k) then is_array = false break end
            end
        end
        if is_array then
            out[#out + 1] = '['
            for i = 1, n do
                if i > 1 then out[#out + 1] = ',' end
                encode(v[i], out, depth + 1)
            end
            out[#out + 1] = ']'
        else
            out[#out + 1] = '{'
            local first = true
            for k, x in pairs(v) do
                if not first then out[#out + 1] = ',' end
                first = false
                encode(tostring(k), out, depth + 1)
                out[#out + 1] = ':'
                encode(x, out, depth + 1)
            end
            out[#out + 1] = '}'
        end
    else
        out[#out + 1] = '"' .. tostring(v) .. '"'
    end
end

function json.encode(v)
    local out = {}
    encode(v, out, 0)
    return table.concat(out)
end

local function utf8_char(c)
    if c < 0x80 then return string.char(c) end
    if c < 0x800 then return string.char(0xC0 + math.floor(c / 64), 0x80 + c % 64) end
    return string.char(0xE0 + math.floor(c / 4096), 0x80 + math.floor(c / 64) % 64, 0x80 + c % 64)
end

function json.decode(s)
    local i = 1
    local function ws() i = s:find('[^ \t\r\n]', i) or #s + 1 end
    local value
    local function str()
        local out = {}
        i = i + 1
        while true do
            local c = s:sub(i, i)
            if c == '' then error('unterminated string') end
            if c == '"' then i = i + 1 break end
            if c == '\\' then
                local e = s:sub(i + 1, i + 1)
                if e == 'u' then
                    out[#out + 1] = utf8_char(tonumber(s:sub(i + 2, i + 5), 16) or 63)
                    i = i + 6
                else
                    out[#out + 1] = ({ b = '\b', f = '\f', n = '\n', r = '\r', t = '\t' })[e] or e
                    i = i + 2
                end
            else
                out[#out + 1] = c
                i = i + 1
            end
        end
        return table.concat(out)
    end
    value = function()
        ws()
        local c = s:sub(i, i)
        if c == '{' then
            local t = {}
            i = i + 1
            ws()
            if s:sub(i, i) == '}' then i = i + 1 return t end
            while true do
                ws()
                local k = str()
                ws()
                if s:sub(i, i) ~= ':' then error('expected :') end
                i = i + 1
                t[k] = value()
                ws()
                local d = s:sub(i, i)
                i = i + 1
                if d == '}' then return t end
                if d ~= ',' then error('expected , or }') end
            end
        elseif c == '[' then
            local t = {}
            i = i + 1
            ws()
            if s:sub(i, i) == ']' then i = i + 1 return t end
            while true do
                t[#t + 1] = value()
                ws()
                local d = s:sub(i, i)
                i = i + 1
                if d == ']' then return t end
                if d ~= ',' then error('expected , or ]') end
            end
        elseif c == '"' then
            return str()
        elseif s:sub(i, i + 3) == 'true' then i = i + 4 return true
        elseif s:sub(i, i + 4) == 'false' then i = i + 5 return false
        elseif s:sub(i, i + 3) == 'null' then i = i + 4 return nil
        else
            local num = s:match('^-?%d+%.?%d*[eE]?[-+]?%d*', i)
            if not num or num == '' then error('unexpected ' .. c) end
            i = i + #num
            return tonumber(num)
        end
    end
    return value()
end

-------------------------------------------------------------------------------- the chat log

local log, log_seq, LOG_MAX = {}, 0, 500

local function plain(raw)
    local ok, s = pcall(res.to_utf8, raw)
    if not ok or not s then s = raw end
    return (s:gsub('[%z\1-\8\11-\31\127]', ''))
end

local function add_line(mode, text, sender)
    log_seq = log_seq + 1
    log[#log + 1] = { seq = log_seq, mode = mode, text = text, sender = sender }
    if #log > LOG_MAX then table.remove(log, 1) end
end

-- What the chat log shows: every line, through text_in. A build where text_in sees only the host's
-- lines (xi.chat.game_lines) adds the chat the server sends (0x017: kind, attributes, zone,
-- sender[15], message); the game's other lines (/echo, its system messages) are missing there.
xi.events.on('text_in', function(e)
    if not e.blocked then add_line(e.mode_modified or e.mode, plain(e.modified or e.data or '')) end
end)

xi.events.on('packet_in', function(e)
    if e.id ~= 0x017 or e.blocked or e.injected or xi.chat.game_lines() then return end
    local d = e.data or ''
    if #d < 24 then return end
    local sender = plain((d:sub(9, 23):gsub('%z.*', '')))
    add_line(d:byte(5), plain((d:sub(24):gsub('%z.*', ''))), sender ~= '' and sender or nil)
end)

-------------------------------------------------------------------------------- game state

local function zone_name(id)
    local ok, z = pcall(res.zone, id)
    if ok and type(z) == 'table' then
        local n = z.name_utf8 or z.name
        if type(n) == 'table' then n = n.en or n[2] or n[1] end
        if type(n) == 'string' then return n end
    end
    return nil
end

-- The menu on screen ("menu    charsel" .. "menu    inventor"), from the game's current menu object
local menu_ptr
local function menu_name()
    if menu_ptr == nil then
        local ok, p = pcall(memory.find, 'FFXiMain.dll', 0, '8B480C85C974??8B510885D274??3B05', 16, 0)
        menu_ptr = ok and p or 0
    end
    if not menu_ptr or menu_ptr == 0 then return nil end
    local ok, name = pcall(function()
        local p = memory.read_uint32(menu_ptr)
        if not p or p == 0 then return '' end
        local v = memory.read_uint32(p)
        if not v or v == 0 then return '' end
        local h = memory.read_uint32(v + 4)
        if not h or h == 0 then return '' end
        return memory.read_string(h + 0x46, 16)
    end)
    if not ok or not name then return nil end
    name = name:gsub('%z.*', ''):gsub('^menu%s+', ''):gsub('%s+$', '')
    return name
end

local function position(i)
    local x, z, y = game.entity(i, 'Movement.LocalPosition.X'), game.entity(i, 'Movement.LocalPosition.Z'),
        game.entity(i, 'Movement.LocalPosition.Y')
    if not x then return nil end
    return { x = x, y = y, z = z, heading = game.entity(i, 'Heading') }
end

local function state()
    local s = { login_status = game.login_status(), menu = menu_name() }
    local text = xi.chat.input()
    s.chat_input = text and plain(text) or nil
    local pi = game.player_index()
    if pi and pi >= 0 and game.entity(pi, 'Name') then
        local zone = game.party_member(0, 'Zone')
        s.player = {
            index = pi, id = game.entity(pi, 'ServerId'), name = game.entity(pi, 'Name'),
            hp = game.party_member(0, 'HP'), mp = game.party_member(0, 'MP'), tp = game.party_member(0, 'TP'),
            hpp = game.entity(pi, 'HPPercent'), status = game.entity(pi, 'Status'),
            hpmax = game.player('HPMax'), mpmax = game.player('MPMax'),
            exp = game.player('ExpCurrent'), exp_needed = game.player('ExpNeeded'),
            job = game.party_member(0, 'MainJob'), level = game.party_member(0, 'MainJobLevel'),
            position = position(pi),
        }
        s.zone = { id = zone, name = zone and zone_name(zone) or nil }
    end
    local ti = game.target('Targets[0].Index')
    if ti and ti > 0 and game.target('Targets[0].IsActive') ~= 0 then
        s.target = { index = ti, id = game.entity(ti, 'ServerId'), name = game.entity(ti, 'Name'),
            hpp = game.entity(ti, 'HPPercent'), distance = game.entity(ti, 'Distance') and math.sqrt(game.entity(ti, 'Distance')) }
    end
    return s
end

-------------------------------------------------------------------------------- EXP, DPS and gear

-- The control panel polls metrics(); the numbers live in this addon so one client's stats never
-- depend on another's.  Damage comes from the 0x028 action packets the server sends, EXP from the
-- player's live ExpCurrent/ExpNeeded fields.
local SLOT_NAMES = { 'main', 'sub', 'range', 'ammo', 'head', 'body', 'hands', 'legs', 'feet',
    'neck', 'waist', 'left_ear', 'right_ear', 'left_ring', 'right_ring', 'back' }
local SLOT_INDEX = {}
for i, name in ipairs(SLOT_NAMES) do SLOT_INDEX[name] = i - 1 end
SLOT_INDEX.ear1, SLOT_INDEX.ear2 = 11, 12
SLOT_INDEX.ring1, SLOT_INDEX.ring2 = 13, 14

local metrics_state = {
    started = nil, last_exp = nil, last_level = nil,
    exp_gained = 0, damage_total = 0, events = {},
}

-- Bits are LSB-first, as the client's action packets pack them. (No bit library in this state.)
local function bits(data, pos, count)
    local value, weight = 0, 1
    for i = 0, count - 1 do
        local byte = data:byte(math.floor((pos + i) / 8) + 1)
        if byte and math.floor(byte / 2 ^ ((pos + i) % 8)) % 2 == 1 then value = value + weight end
        weight = weight * 2
    end
    return value
end

local function parse_action_damage(data)
    local actor = bits(data, 40, 32)
    local targets = math.min(bits(data, 72, 10), 32)
    local pos, limit = 150, #data * 8
    local damage = 0
    for _ = 1, targets do
        if pos + 36 > limit then break end
        local actions = math.min(bits(data, pos + 32, 4), 32)
        pos = pos + 36
        for _ = 1, actions do
            if pos + 87 > limit then break end
            damage = damage + bits(data, pos + 27, 17)
            local add = bits(data, pos + 85, 1)
            pos = pos + 86
            if add == 1 then pos = pos + 37 end
            local spike = bits(data, pos, 1)
            pos = pos + 1
            if spike == 1 then pos = pos + 34 end
        end
    end
    return actor, damage
end

local function item_name(id)
    if not id or id == 0 then return nil end
    local ok, item = pcall(res.item, id)
    if not ok or not item then return nil end
    local name = item.name_utf8 or item.name
    if type(name) == 'table' then name = name.en or name[2] or name[1] end
    return type(name) == 'string' and name or nil
end

-- Windower's 0x01B "Encumbrance Flags" word, kept for the launcher's EquipViewer overlay.
-- 0x01B is sent when the job/equipment block is rebuilt; 0 means nothing is encumbered.
local encumbrance_flags = 0

-- The launcher's GearSwap slot keys differ from Windower's ffxi.get_items() keys only for the
-- paired slots. Return both spellings so either client can read the same payload.
local SLOT_ALIASES = {
    left_ear = 'ear1', right_ear = 'ear2',
    left_ring = 'ring1', right_ring = 'ring2',
}

local function gear()
    local slots = {}
    for i, name in ipairs(SLOT_NAMES) do
        local _, index = game.equipment(i - 1)
        index = index or 0
        local bag, slot = math.floor(index / 256), index % 256
        local id = slot > 0 and game.item(bag, slot, 'Id') or 0
        local count = slot > 0 and game.item(bag, slot, 'Count') or 0
        local item = {
            id = id or 0, bag = bag, index = slot, name = item_name(id), count = count or 0,
        }
        slots[name] = item
        local alias = SLOT_ALIASES[name]
        if alias then slots[alias] = item end
    end
    return { slots = slots, encumbrance = encumbrance_flags }
end

-- One walk over the bags, item id -> where its copies sit. GearSwap's unpack_equip_list() walks
-- the bags once per swap the same way; scanning every bag for every piece (with a resources
-- lookup per candidate item) was what made a Wear set cost a frame per slot.
local function bag_index()
    local by_id = {}
    for bag = 0, 17 do
        -- Every client bag has slots 1..80; do not trust container_max() to stop the scan.
        -- A server bag (or a wardrobe the client reports short) can hold gear at a higher
        -- slot, and a plan that cannot see it silently drops that piece.
        for slot = 1, 80 do
            local id = game.item(bag, slot, 'Id')
            if id and id ~= 0 then
                local copies = by_id[id]
                if not copies then copies = {} by_id[id] = copies end
                copies[#copies + 1] = {
                    bag = bag, slot = slot,
                    count = game.item(bag, slot, 'Count') or 1,
                }
            end
        end
    end
    return by_id
end

-- The first copy of `name` this set has not claimed yet, so a set listing the same earring in
-- both ears gets the two copies instead of the same one twice.
local function find_item(by_id, name, claimed)
    local wanted = tostring(name or '')
    if wanted == '' then return nil end
    local function take(copies, id)
        for _, at in ipairs(copies) do
            if not (claimed and claimed[at.bag * 256 + at.slot]) then
                return at.bag, at.slot, id
            end
        end
        return nil
    end
    local ok, by_name = pcall(res.item_by_name, wanted)
    local wanted_id = ok and by_name and tonumber(by_name.id) or nil
    if wanted_id and by_id[wanted_id] then
        local bag, slot = take(by_id[wanted_id], wanted_id)
        if bag then return bag, slot, wanted_id, item_name(wanted_id) or wanted end
    end
    -- resources has no line for it (a custom item, or a name only the log knows): match names.
    local lower = wanted:lower()
    for id, copies in pairs(by_id) do
        local actual = item_name(id)
        if actual and actual:lower() == lower then
            local bag, slot = take(copies, id)
            if bag then return bag, slot, id, actual end
        end
    end
    return nil
end

-- 0x050: inventory slot, equipment slot, bag, 0 - the four bytes GearSwap's equip_piece() builds,
-- with the size field the game writes (4 units of 4 bytes).
local function equip_packet(bag, slot, slot_number)
    return string.char(0x50, 4, 0, 0, slot % 256, slot_number % 256, bag % 256, 0)
end

-- The item id worn in each equipment slot right now.
local function worn_items()
    local worn = {}
    for slot_number = 0, #SLOT_NAMES - 1 do
        local _, index = game.equipment(slot_number)
        index = index or 0
        local bag, slot = math.floor(index / 256), index % 256
        worn[slot_number] = slot > 0 and (game.item(bag, slot, 'Id') or 0) or 0
    end
    return worn
end

local function equip_item(slot_number, name)
    local bag, slot, id, actual = find_item(bag_index(), name)
    if not bag then error('not in this character\'s bags: ' .. tostring(name)) end
    xi.packets.inject(true, equip_packet(bag, slot, slot_number))
    return { slot = slot_number, item = actual, id = id, bag = bag, index = slot }
end

-- The on-screen combat HUD is defined further down (it needs job_spells/job_abilities);
-- metrics carries its current switch/layout state so the launcher's toggles reflect the client.
local hud

local function metrics()
    local now = os.clock()
    local exp = game.player('ExpCurrent') or 0
    local needed = game.player('ExpNeeded') or 0
    local level = game.player('MainJobLevel') or 0
    if metrics_state.started == nil then
        metrics_state.started = now
        metrics_state.last_exp = exp
        metrics_state.last_level = level
    end
    if metrics_state.last_exp ~= nil then
        local delta = exp - metrics_state.last_exp
        if delta >= 0 then
            metrics_state.exp_gained = metrics_state.exp_gained + delta
        else
            -- a level-up resets ExpCurrent; the new value is the gain in the new level
            metrics_state.exp_gained = metrics_state.exp_gained + exp
        end
    end
    metrics_state.last_exp = exp
    metrics_state.last_level = level

    local cutoff, rolling = now - 60, 0
    local keep = {}
    for _, event in ipairs(metrics_state.events) do
        if event.t >= cutoff then
            keep[#keep + 1] = event
            rolling = rolling + event.damage
        end
    end
    metrics_state.events = keep
    local elapsed = math.max(0.001, now - metrics_state.started)
    local window = math.min(60, math.max(1, elapsed))
    return {
        state = state(),
        kpi = {
            exp = exp, exp_needed = needed,
            exp_percent = needed > 0 and math.floor(exp * 1000 / needed) / 10 or 0,
            exp_gained = metrics_state.exp_gained,
            exp_per_hour = math.floor(metrics_state.exp_gained / elapsed * 3600),
            dps = math.floor(rolling / window * 10) / 10,
            damage = rolling,
            damage_total = metrics_state.damage_total,
            session_seconds = math.floor(elapsed),
            level = level,
        },
        gear = gear(),
        hud = hud and hud.snapshot() or nil,
    }
end

if xi.events and xi.events.on then
    xi.events.on('packet_in', function(e)
        if e.blocked or e.injected then return end
        local data = e.modified or e.data
        if type(data) ~= 'string' then return end
        if e.id == 0x01B then
            -- Packet field "Encumbrance Flags" (Windower's packet_fields: 0x01B + 0x60). The
            -- client sends one bit per equipment slot, main first, back last.
            if #data >= 0x64 then
                local a, b, c, d = data:byte(0x61, 0x64)
                encumbrance_flags = a + b * 0x100 + c * 0x10000 + d * 0x1000000
            end
            return
        end
        if e.id ~= 0x028 then return end
        local ok, actor, damage = pcall(parse_action_damage, data)
        if not ok or damage <= 0 then return end
        local pi = game.player_index()
        local me = pi and game.entity(pi, 'ServerId')
        if me and actor == me then
            metrics_state.damage_total = metrics_state.damage_total + damage
            metrics_state.events[#metrics_state.events + 1] = { t = os.clock(), damage = damage }
        end
    end)
end

local ENTITY_TYPES = { [0] = 'pc', [1] = 'npc', [2] = 'npc', [3] = 'npc', [4] = 'elevator', [5] = 'ship' }

local function entities(a)
    local radius = tonumber(a.radius) or 50
    local limit = tonumber(a.limit) or 50
    local out = {}
    local count = game.entity_count() or 0
    for i = 0, count - 1 do
        local name = game.entity(i, 'Name')
        if name and name ~= '' then
            local d2 = game.entity(i, 'Distance') or 0
            local flags = game.entity(i, 'SpawnFlags') or 0
            local d = math.sqrt(d2)
            if d <= radius and (game.entity(i, 'Render.Flags0') or 0) ~= 0 then
                out[#out + 1] = { index = i, id = game.entity(i, 'ServerId'), name = name, distance = d,
                    hpp = game.entity(i, 'HPPercent'), spawn_flags = flags, type = ENTITY_TYPES[game.entity(i, 'Type') or -1],
                    position = position(i) }
            end
        end
    end
    table.sort(out, function(p, q) return p.distance < q.distance end)
    while #out > limit do out[#out] = nil end
    return out
end

-------------------------------------------------------------------------------- keys

local pressed = {} -- DIK -> true: what this port holds down

local MODS = { ctrl = 'lctrl', control = 'lctrl', shift = 'lshift', alt = 'lalt', cmd = 'lwin', win = 'lwin' }

local function key_code(name)
    local d = xi.input.code(name)
    if not d then error('no key "' .. tostring(name) .. '"') end
    return d
end

local function key(d, down)
    xi.input.inject(d, down)
    pressed[d] = down or nil
end

local function sleep_ms(ms)
    if ms and ms > 0 then coroutine.sleep(ms / 1000) else coroutine.sleepf(1) end
end

local function keys(a)
    local list = a.keys
    if type(list) == 'string' then list = { list } end
    if type(list) ~= 'table' then error('keys: a list of key names') end
    local hold, gap = tonumber(a.hold_ms) or 80, tonumber(a.gap_ms) or 120
    for _, k in ipairs(list) do
        local ms = tostring(k):match('^wait:(%d+)$')
        if ms then
            sleep_ms(tonumber(ms))
        else
            local parts = {}
            for p in tostring(k):lower():gmatch('[^+]+') do parts[#parts + 1] = p end
            local codes = {}
            for i, p in ipairs(parts) do
                codes[i] = key_code(i < #parts and MODS[p] or p)
            end
            for _, d in ipairs(codes) do key(d, true) coroutine.sleepf(1) end
            sleep_ms(hold)
            for i = #codes, 1, -1 do key(codes[i], false) coroutine.sleepf(1) end
            sleep_ms(gap)
        end
    end
    return { sent = #list }
end

local function release_keys()
    local n = 0
    for d in pairs(pressed) do xi.input.inject(d, false) n = n + 1 end
    pressed = {}
    return { released = n }
end

-------------------------------------------------------------------------------- the rest of the commands

local function capture(a)
    local path = a.path or (xi.paths.data .. 'control_frame.xif')
    local before = xi.ui.capture_result()
    xi.ui.capture(path)
    for _ = 1, 120 do
        coroutine.sleepf(1)
        local serial, ok, w, h, f = xi.ui.capture_result()
        if serial ~= before then
            if not ok then error('the frame capture failed') end
            return { path = path, width = w, height = h, format = f }
        end
    end
    error('no frame was drawn')
end

local function run_lua(a)
    local fn, err = loadstring(a.code or '', '=control')
    if not fn then
        fn, err = loadstring('return ' .. (a.code or ''), '=control')
        if not fn then error(err) end
    end
    local r = { pcall(fn) }
    if not r[1] then error(r[2]) end
    if #r <= 2 then return r[2] end
    table.remove(r, 1)
    return r
end

local GEAR_SWAP_SLOTS = { 'main', 'sub', 'range', 'ammo', 'head', 'body', 'hands', 'legs',
    'feet', 'neck', 'waist', 'ear1', 'ear2', 'ring1', 'ring2', 'back' }
local GEAR_SWAP_SLOT_SET = {}
for _, name in ipairs(GEAR_SWAP_SLOTS) do GEAR_SWAP_SLOT_SET[name] = true end
GEAR_SWAP_SLOT_SET.left_ear, GEAR_SWAP_SLOT_SET.right_ear = true, true
GEAR_SWAP_SLOT_SET.left_ring, GEAR_SWAP_SLOT_SET.right_ring = true, true

local function clean_value(value, depth)
    local t = type(value)
    if t == 'string' or t == 'number' or t == 'boolean' then return value end
    if t ~= 'table' or depth > 12 then return nil end
    local out = {}
    for key, item in pairs(value) do
        if type(key) == 'string' or type(key) == 'number' then
            out[key] = clean_value(item, depth + 1)
        end
    end
    return out
end

local function gearswap_sets(path)
    if type(path) ~= 'string' or path == '' then error('gearswap: path') end
    local file = io.open(path, 'rb')
    if not file then error('cannot read ' .. path) end
    local source = file:read('*a')
    file:close()
    local chunk, err = loadstring(source, '@' .. path)
    if not chunk then error('GearSwap parse error: ' .. tostring(err)) end
    local env = setmetatable({}, { __index = _G })
    env.sets = {}
    env.include = function() end
    env.add_to_chat = function() end
    env.print = function() end
    env.T = function(value) return value end
    env.S = {}
    env.buffactive = {}
    env.player = {
        name = game.entity(game.player_index() or 0, 'Name') or '',
        main_job = game.party_member(0, 'MainJob') or 0,
        main_job_id = game.party_member(0, 'MainJob') or 0,
        level = game.party_member(0, 'MainJobLevel') or 0,
    }
    env.world = { zone = game.party_member(0, 'Zone') or 0, weather = 0, time = 0, day = 0 }
    env.windower = { add_to_chat = function() end, info = {}, ffxi = {}, windower_path = '' }
    env.ashita = { print = function() end, GetCore = function() return nil end }
    env.gearswap = { commands = {}, helpers = {} }
    setfenv(chunk, env)
    local ok, load_error = pcall(chunk)
    if not ok then error('GearSwap load error: ' .. tostring(load_error)) end
    if type(env.get_sets) == 'function' then pcall(env.get_sets) end
    return clean_value(env.sets, 0) or {}
end

local function gearswap(a)
    local path = a.path
    return { path = path, sets = gearswap_sets(path) }
end

-------------------------------------------------------------------------------- phase engine

-- An outgoing 0x01A carries the action category at 0x0A and the action id at 0x0C. These are
-- the same numbers GearSwap maps /ma, /ws and /ja to; the skill ids are the client's own, named
-- the way GearSwap libraries key sets.midcast.
local PHASE_MAGIC, PHASE_WS, PHASE_JA = 3, 7, 9
local MIDCAST_SKILL = {
    [32] = 'Divine Magic', [33] = 'Healing Magic', [34] = 'Enhancing Magic',
    [35] = 'Enfeebling Magic', [36] = 'Elemental Magic', [37] = 'Dark Magic',
    [38] = 'Summoning Magic', [39] = 'Ninjutsu', [40] = 'Singing',
    [41] = 'String Instrument', [42] = 'Wind Instrument', [43] = 'Blue Magic',
    [44] = 'Geomancy', [45] = 'Handbell',
}

-- The Gear page's spell categories, in the order the host resolves them. A spell can be in both
-- faces of a group (every Enfeebling Magic spell is a macc target and a duration target, every
-- Enhancing Magic spell a potency and a duration target), so the first configured category wins
-- when a saved plan carries both. The launcher keeps the two faces of a group exclusive.
local SPELL_CATEGORY_ORDER = {
    'enfeebles_macc', 'enfeebles_duration', 'buff_potency', 'buff_duration', 'helix_magic',
}
local function spell_name(spell)
    local name = spell and spell.name
    if type(name) == 'table' then name = name.en or name[2] or name[1] end
    return type(name) == 'string' and name or ''
end

-- The switch the plan builder uses: which override categories a spell belongs to. The launcher
-- groups the same way in job_spells, so the cards and the rules cannot disagree.
local function spell_categories(spell)
    local out = {}
    local skill = spell and MIDCAST_SKILL[spell.skill]
    if skill == 'Enfeebling Magic' then
        out[#out + 1] = 'enfeebles_macc'
        out[#out + 1] = 'enfeebles_duration'
    elseif skill == 'Enhancing Magic' then
        out[#out + 1] = 'buff_potency'
        out[#out + 1] = 'buff_duration'
    end
    if spell_name(spell):lower():find('helix', 1, true) then out[#out + 1] = 'helix_magic' end
    return out
end

-- The action packet carries a job ability's id minus 0x200 (the resource id's low 9 bits).
-- Weapon skills are already 1..255, so the same expression leaves them alone.
local function action_id(ability)
    local id = ability and tonumber(ability.id) or 0
    if id <= 0 then return nil end
    return id >= 512 and (id % 512) or id
end

-- A dotted path in a set library ("engaged.tp", "midcast.Elemental Magic").
local function set_at(sets, path)
    local node = sets
    for part in tostring(path):gmatch('[^%.]+') do
        if type(node) ~= 'table' then return nil end
        node = node[part]
    end
    return type(node) == 'table' and node or nil
end

-- A slot is either an item name or GearSwap's {name = ..., augments = {...}} table.
local function item_name_of(value)
    if type(value) == 'string' then return value end
    if type(value) == 'table' and type(value.name) == 'string' then return value.name end
    return nil
end

local function is_equip_set(t)
    if type(t) ~= 'table' then return false end
    for _, name in ipairs(SLOT_NAMES) do
        if item_name_of(t[name]) then return true end
    end
    return false
end

-- One set -> the triples the engine turns into 0x050s: inventory slot, equipment slot, bag.
local function phase_equips(t, by_id)
    local out, claimed = {}, {}
    for i, name in ipairs(SLOT_NAMES) do
        -- The model names the paired slots left_ear/right_ear/left_ring/right_ring, while the
        -- gearswap libraries (and the launcher) use ear1/ear2/ring1/ring2.
        local value = t[name]
        if value == nil and SLOT_ALIASES[name] then value = t[SLOT_ALIASES[name]] end
        local item = item_name_of(value)
        if item and item ~= '' then
            local bag, at = find_item(by_id, item, claimed)
            if bag then
                claimed[bag * 256 + at] = true
                out[#out + 1] = { at, i - 1, bag }
            end
        end
    end
    return out
end

-- The idle state machine's zone list: every city and town (the zones that are not field).
-- GearSwap's idle.town is worn in these and idle.field in every other zone. Zone ids are the
-- client's own, the same numbers 0x00A carries.
local TOWN_ZONES = {
    [26] = true, [48] = true, [50] = true, [53] = true,
    [230] = true, [231] = true, [232] = true,               -- San d'Oria
    [234] = true, [235] = true, [236] = true,               -- Bastok
    [238] = true, [239] = true, [240] = true, [241] = true, -- Windurst
    [243] = true, [244] = true, [245] = true, [246] = true, -- Jeuno
    [247] = true, [248] = true, [249] = true, [250] = true, -- Rabao, Selbina, Mhaura, Kazham
    [252] = true,                                           -- Norg
    [256] = true, [257] = true,                             -- Adoulin
}
local function zone_town(id) return TOWN_ZONES[tonumber(id) or 0] and 1 or 0 end

local JOB_ABBR = { 'WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK', 'BST', 'BRD', 'RNG',
    'SAM', 'NIN', 'DRG', 'SMN', 'BLU', 'COR', 'PUP', 'DNC', 'SCH', 'GEO', 'RUN' }

-- Build the precast/midcast/idle plan from a GearSwap library and hand it to the host's packet
-- layer (xi.phase, phase.c). The host does the timing; this only decides what each action wears.
-- Idle states: engaged (TP), moving, idle in a town and idle in the field. The client's own
-- position is the only movement signal there is, so it is sampled a few frames apart: a step
-- wears the movement set, and half a second without a step goes back to the idle set. The 0x00A
-- zone-in packet picks town or field, and the server's own animation picks engaged or not.
local phase_watch = nil
local phase_plan = nil
local phase_job_seen, phase_job_at = nil, 0
local phase

local function inject_plan(equips)
    if type(equips) ~= 'table' then return 0 end
    local n = 0
    for _, e in ipairs(equips) do
        xi.packets.inject(true, equip_packet(e[3], e[1], e[2]))
        n = n + 1
    end
    return n
end

-- A job change reloads the job's own library when the plan came from a job-named default
-- (gearswap/NIN.lua). A custom library keeps its path; its sets are job-agnostic and a job
-- change only re-wears the idle state set. The launcher also reloads its library, but the
-- engine keeps working when the launcher window is closed.
local function reload_for_job(job)
    local abbr = JOB_ABBR[job]
    if not abbr or not phase_plan or not phase_plan.path then return end
    local path = phase_plan.path
    local dir, base = path:match('^(.*[/\\])([^/\\]+)$')
    if dir and base and base:match('^[A-Z][A-Z][A-Z]%.lua$') then path = dir .. abbr .. '.lua' end
    local plan = { enabled = true }
    for key, value in pairs(phase_plan) do plan[key] = value end
    plan.path = path
    local ok, err = pcall(phase, plan)
    if not ok then
        -- The bags are rebuilt on a job change and can still be empty; try again shortly.
        phase_job_at = os.clock()
        return
    end
    phase_job_seen = nil
end

local function watch_phase()
    local last, still_since, moving = nil, os.clock(), false
    while phase_watch do
        if phase_job_seen and os.clock() >= phase_job_at + 1.5 then reload_for_job(phase_job_seen) end
        local index = game.player_index() or 0
        local x = index > 0 and game.entity(index, 'Movement.LocalPosition.X') or nil
        local y = index > 0 and game.entity(index, 'Movement.LocalPosition.Y') or nil
        local z = index > 0 and game.entity(index, 'Movement.LocalPosition.Z') or nil
        if x and y and z then
            local now = os.clock()
            if last then
                local d = math.abs(x - last[1]) + math.abs(y - last[2]) + math.abs(z - last[3])
                -- A zone or a teleport moves the character far in one sample; that is not a step.
                if d > 0.01 and d < 20 then
                    still_since = now
                    moving = true
                elseif moving and now - still_since > 0.5 then
                    moving = false
                end
            end
            last = { x, y, z }
            inject_plan(xi.phase.moving(moving))
        else
            last = nil
        end
        -- The zone-in and job packets only set state; the set for it goes out here, once the
        -- client has had a moment to load the new zone or the new job's gear.
        inject_plan(xi.phase.pending())
        coroutine.sleep(0.04)
    end
    phase_watch = nil
end

local function start_watch()
    if phase_watch then return end
    phase_watch = true
    xi.tasks.spawn(watch_phase)
end

local function stop_watch()
    phase_watch = nil
end

-- The two packets the idle machine follows. They arrive on the network thread, so the handlers
-- only store atomics in the host; watch_phase wears the set from the game thread.
if xi.phase and xi.events and xi.events.on then
    xi.events.on('packet_in', function(e)
        if e.blocked or e.injected then return end
        local data = e.modified or e.data
        if type(data) ~= 'string' then return end
        if e.id == 0x00A then
            -- Zone-in: body offset 0x2C is the destination zone id (little-endian u16).
            if #data >= 4 + 0x2E then
                local zone = data:byte(4 + 0x2C + 1) + data:byte(4 + 0x2C + 2) * 256
                if zone > 0 then xi.phase.zone(zone, zone_town(zone)) end
            end
        elseif e.id == 0x01B then
            -- Job/equipment block: body offset 4 is the main job and offset 7 the support job.
            -- Both belong to the job pair the lock was taken for, so both can end it.
            if #data >= 4 + 0x08 then
                local job = data:byte(4 + 4 + 1)
                local sub = data:byte(4 + 7 + 1)
                if job and job > 0 then
                    xi.phase.job(job, sub or 0)
                    if phase_plan then
                        phase_job_seen, phase_job_at = job, os.clock()
                    end
                end
            end
        end
    end)
end

phase = function(a)
    if a.enabled == false then
        stop_watch()
        phase_plan = nil
        phase_job_seen = nil
        if xi.phase then xi.phase.clear() end
        return { enabled = false }
    end
    if not xi.phase then
        error('this host64 has no phase engine: rebuild it (tools/build_posix.py host64)')
    end
    local sets = a.sets
    if type(sets) ~= 'table' then sets = gearswap_sets(a.path) end
    local by_id, set_list, set_names, rules = bag_index(), {}, {}, {}
    if next(by_id) == nil then
        -- Pushed the moment the character reaches the world, the bags can still be empty; a
        -- plan built then would have nothing to wear. The launcher retries.
        error('phase: the bags are not loaded yet')
    end
    -- The job pair the plan is for. A category group only covers spells this pair can cast, the
    -- same list job_spells sends the launcher for its cards.
    local main_job = game.party_member(0, 'MainJob') or 0
    local main_level = game.party_member(0, 'MainJobLevel') or 0
    local sub_job = game.party_member(0, 'SubJob') or 0
    local sub_level = game.party_member(0, 'SubJobLevel') or 0
    local spell_jobs = { { main_job, main_level }, { sub_job, sub_level } }
    local function spell_is_known(spell)
        if not spell or type(spell.levels) ~= 'table' then return false end
        for _, pair in ipairs(spell_jobs) do
            local needed = pair[1] > 0 and spell.levels[pair[1]] or -1
            if needed and needed > 0 and needed <= pair[2] then return true end
        end
        return false
    end
    local function add_set(t, name)
        if not is_equip_set(t) then return nil end
        local equips = phase_equips(t, by_id)
        if #equips == 0 then return nil end
        set_list[#set_list + 1] = equips
        set_names[#set_names + 1] = name or ''
        return #set_list
    end
    local function path_set(path, label)
        if type(path) ~= 'string' or path == '' then return nil end
        local t = set_at(sets, path)
        if type(t) ~= 'table' then return nil end
        return add_set(t, label or path)
    end

    -- Weaponskills: a per-WS override wins over the library's sets.WS.<name>; the default set
    -- is the fallback for a WS with no card of its own.
    local ws_override = {}
    if type(a.ws_overrides) == 'table' then
        for name, path in pairs(a.ws_overrides) do
            local index = path_set(path, 'WS.' .. tostring(name))
            if index then ws_override[tostring(name)] = index end
        end
    end
    local ws_fallback = path_set(tostring(a.default_ws or ''), 'WS.default')
        or (sets.precast and add_set(sets.precast.WS, 'precast.WS'))
    local ws_seen = {}
    if type(sets.WS) == 'table' then
        for name, t in pairs(sets.WS) do
            local ws_name = tostring(name)
            local ability = res.ability_by_name(ws_name)
            local index = ws_override[ws_name] or add_set(t, 'WS.' .. ws_name)
            if ability and index then
                rules[#rules + 1] = { category = PHASE_WS, action = ability.id, pre = index }
                ws_seen[ws_name] = true
            end
        end
    end
    for name, index in pairs(ws_override) do
        if not ws_seen[name] then
            local ability = res.ability_by_name(name)
            if ability then
                rules[#rules + 1] = { category = PHASE_WS, action = ability.id, pre = index }
            end
        end
    end
    if ws_fallback then rules[#rules + 1] = { category = PHASE_WS, action = 0, pre = ws_fallback } end

    -- Job abilities: a per-ability override wins over the library's sets.JA.<name>; the default
    -- JA set is the fallback for any ability with no set of its own. Every 0x200+ ability uses
    -- its low 9 bits, which covers job abilities, sambas, waltzes and runes, not
    -- just the client's "JobAbility" type.
    local ja_override = {}
    if type(a.ja_overrides) == 'table' then
        for name, path in pairs(a.ja_overrides) do
            local index = path_set(path, 'JA.' .. tostring(name))
            local action = action_id(res.ability_by_name(tostring(name)))
            if action and index then ja_override[action] = index end
        end
    end
    local ja_fallback = path_set(tostring(a.default_ja or ''), 'JA.default')
        or (sets.precast and add_set(sets.precast.JA, 'precast.JA'))
    local ja_seen = {}
    if type(sets.JA) == 'table' then
        for name, t in pairs(sets.JA) do
            local action = action_id(res.ability_by_name(tostring(name)))
            local index = action and (ja_override[action] or add_set(t, 'JA.' .. tostring(name))) or nil
            if action and index then
                rules[#rules + 1] = { category = PHASE_JA, action = action, pre = index }
                ja_seen[action] = true
            end
        end
    end
    for action, index in pairs(ja_override) do
        if not ja_seen[action] then
            rules[#rules + 1] = { category = PHASE_JA, action = action, pre = index }
        end
    end
    if ja_fallback then rules[#rules + 1] = { category = PHASE_JA, action = 0, pre = ja_fallback } end

    -- Spells: the user's precast set, per-spell overrides, category overrides, a midcast
    -- default for every spell, then the library's skill sets. find_rule returns the first exact
    -- action match, so the order here is the priority the page promises:
    -- a per-spell card > the spell's category > the midcast default > the skill set.
    local precast = path_set(tostring(a.precast or ''), 'precast')
    if not precast and sets.precast then
        precast = add_set(sets.precast.FC, 'precast.FC') or add_set(sets.precast, 'precast')
    end
    local mid_default = path_set(tostring(a.midcast or ''), 'midcast.default')
    local spell_override = {}
    if type(a.spell_overrides) == 'table' then
        for id, path in pairs(a.spell_overrides) do
            local key = tonumber(id)
            local index = path_set(path, 'spell.' .. tostring(id))
            if key and index then spell_override[key] = index end
        end
    end
    -- A category rule is still a per-spell rule once the plan is built: the host looks up the
    -- action id and sees the set chosen for the category the spell belongs to. This is the
    -- switch the page's category cards configure.
    local category_override = {}
    if type(a.spell_category_overrides) == 'table' then
        for name, path in pairs(a.spell_category_overrides) do
            local index = path_set(path, 'spell.category.' .. tostring(name))
            if index then category_override[tostring(name)] = index end
        end
    end
    -- A spell gets at most one category rule and never a duplicate of a direct override.
    local claimed = {}
    for id in pairs(spell_override) do claimed[id] = true end
    for _, category in ipairs(SPELL_CATEGORY_ORDER) do
        local mid = category_override[category]
        if mid then
            for index = 0, 1023 do
                if not claimed[index] then
                    local spell = res.spell(index)
                    if spell_is_known(spell) then
                        for _, key in ipairs(spell_categories(spell)) do
                            if key == category then
                                rules[#rules + 1] = {
                                    category = PHASE_MAGIC, action = index, pre = precast, mid = mid,
                                }
                                claimed[index] = true
                                break
                            end
                        end
                    end
                end
            end
        end
    end
    for id, mid in pairs(spell_override) do
        rules[#rules + 1] = { category = PHASE_MAGIC, action = id, pre = precast, mid = mid }
    end
    if precast or mid_default then
        local fallback = { category = PHASE_MAGIC, action = 0 }
        if precast then fallback.pre = precast end
        if mid_default then fallback.mid = mid_default end
        rules[#rules + 1] = fallback
    end
    -- A default midcast replaces the library's skill sets; leaving it empty keeps the
    -- skill-based sets (midcast.Healing Magic, midcast.Ninjutsu, ...).
    if not mid_default and type(sets.midcast) == 'table' then
        local mid_cache = {}
        for index = 0, 1023 do
            if not claimed[index] then
                local spell = res.spell(index)
                if spell and (spell.id or 0) > 0 then
                    local skill = MIDCAST_SKILL[spell.skill]
                    if skill then
                        if mid_cache[skill] == nil then
                            mid_cache[skill] = add_set(sets.midcast[skill], 'midcast.' .. skill) or false
                        end
                        local mid = mid_cache[skill]
                        if mid then
                            -- The action packet carries the spell's table index (Cure is 1,
                            -- Monomi: Ichi is 318), not the recast id res.spell returns; the
                            -- two differ for every ninjutsu and most songs and blue magic.
                            rules[#rules + 1] = { category = PHASE_MAGIC, action = index, pre = precast, mid = mid }
                        end
                    end
                end
            end
        end
    end

    -- Idle and the forced states. /attack (0x01A category 2) wears the engaged set, /attack off
    -- (category 4) an idle set; 0x00A picks town or field, the position sampler picks movement,
    -- kiting and resting are manual, and the idle focus (dt/pdt/mdt/eva/meva) is manual too.
    local engaged_path = tostring(a.engaged or a['return'] or 'engaged.tp')
    local town_path = tostring(a.idle_town or a.idle or 'idle.town')
    local field_path = tostring(a.idle_field or 'idle.field')
    local move_path = tostring(a.move or 'idle.movement')
    local function state_path(path, fallback)
        local name = tostring(path or '')
        local index = name ~= '' and add_set(set_at(sets, name), name) or nil
        if not index and fallback then
            name = fallback
            index = add_set(set_at(sets, name), name)
        end
        return index, index and name or nil
    end
    local engage_set = state_path(engaged_path, 'engaged')
    local town_set = state_path(town_path, 'idle.town')
    local field_set, field_name = state_path(field_path, 'idle.field')
    if not field_set then field_set, field_name = town_set, town_path end
    local move_set = state_path(move_path, 'idle.movement')
    local kite_set = state_path(a.kite)
    local rest_set = state_path(a.rest)
    local focus_paths = type(a.focus) == 'table' and a.focus or {}
    local focus_sets = {}
    for i, key in ipairs({ 'dt', 'pdt', 'mdt', 'eva', 'meva' }) do
        local index, name = state_path(focus_paths[key])
        focus_sets[i] = { index = index, name = name }
    end
    local restore = engage_set or town_set
    local player = game.entity(game.player_index() or 0, 'ServerId') or 0
    if player == 0 then
        -- The launcher pushes this as soon as a client appears; before the character is in the
        -- world the bags are empty, which would build a plan that equips nothing.
        error('phase: the character is not in the world yet')
    end
    local zone = game.party_member(0, 'Zone') or 0
    local job = main_job
    xi.phase.set({
        enabled = true, player = player, sets = set_list, names = set_names, rules = rules,
        engage = engage_set, idle = town_set, idle_town = town_set, idle_field = field_set,
        move = move_set, kite = kite_set, rest = rest_set, restore = restore,
        focus = {
            dt = focus_sets[1].index, pdt = focus_sets[2].index, mdt = focus_sets[3].index,
            eva = focus_sets[4].index, meva = focus_sets[5].index,
        },
        zone = zone, town = zone_town(zone), job = job,
    })
    phase_plan = {
        path = a.path, engaged = engaged_path, idle_town = town_path,
        idle_field = field_path, move = move_path, kite = a.kite, rest = a.rest,
        precast = a.precast, midcast = a.midcast, default_ws = a.default_ws,
        default_ja = a.default_ja, ws_overrides = a.ws_overrides,
        ja_overrides = a.ja_overrides, spell_overrides = a.spell_overrides,
        spell_category_overrides = a.spell_category_overrides, focus = a.focus,
    }
    phase_job_seen = nil
    inject_plan(xi.phase.apply())
    start_watch()
    local counts = { ws = 0, ja = 0, magic = 0 }
    for _, rule in ipairs(rules) do
        if rule.category == PHASE_WS then counts.ws = counts.ws + 1
        elseif rule.category == PHASE_JA then counts.ja = counts.ja + 1
        else counts.magic = counts.magic + 1 end
    end
    return {
        enabled = true, path = a.path, player = player, sets = #set_list, rules = #rules,
        ws = counts.ws, ja = counts.ja, magic = counts.magic, rule_list = rules,
        engaged_set = engage_set and engaged_path or nil,
        idle_town_set = town_set and town_path or nil,
        idle_field_set = field_set and field_name or nil,
        movement_set = move_set and move_path or nil,
        kite_set = kite_set and tostring(a.kite) or nil,
        rest_set = rest_set and tostring(a.rest) or nil,
        focus_sets = {
            dt = focus_sets[1].name, pdt = focus_sets[2].name, mdt = focus_sets[3].name,
            eva = focus_sets[4].name, meva = focus_sets[5].name,
        },
        zone = zone, town = zone_town(zone), job = job,
    }
end

-- The Active gear card's lock: hold the set that is on now and stop every automatic swap.
-- Unlocking puts the current state's set back and returns the pieces it wore.
local function phase_lock(a)
    if not xi.phase then
        error('this host64 has no phase engine: rebuild it (tools/build_posix.py host64)')
    end
    local on = a.locked
    if on == nil then on = a.on end
    local equips = xi.phase.lock(on and true or false)
    local equipped = inject_plan(equips)
    if not on then start_watch() end
    local status = xi.phase.status()
    return { locked = status.locked, state = status.state, set = status.set, equipped = equipped }
end

local FOCUS_MODES = { auto = 0, dt = 1, pdt = 2, mdt = 3, eva = 4, meva = 5 }

local function slot_index(name)
    name = tostring(name or ''):lower()
    if name == 'ranged' then name = 'range' end
    return SLOT_INDEX[name]
end

local function locked_slots_mask()
    local st = xi.phase and xi.phase.status() or {}
    local mask = 0
    for _, index in ipairs(st.lockedSlots or {}) do mask = mask + 2 ^ index end
    return mask
end

local function phase_kiting(a)
    local on = a.on
    if on == nil then on = a.kiting end
    local equipped = inject_plan(xi.phase.kiting(on and true or false))
    if on then start_watch() end
    local status = xi.phase.status()
    return { kiting = status.kiting, state = status.state, set = status.set, equipped = equipped }
end

local function phase_resting(a)
    local on = a.on
    if on == nil then on = a.resting end
    local equipped = inject_plan(xi.phase.resting(on and true or false))
    local status = xi.phase.status()
    return { resting = status.resting, state = status.state, set = status.set, equipped = equipped }
end

local function phase_focus(a)
    local mode = a.mode
    if type(mode) == 'string' then mode = FOCUS_MODES[mode:lower()] or 0 end
    mode = tonumber(mode) or 0
    local equipped = inject_plan(xi.phase.focus(mode))
    local status = xi.phase.status()
    return { focus = status.focus, state = status.state, set = status.set, equipped = equipped }
end

local function phase_lock_slots(a)
    local mask = tonumber(a.mask)
    if not mask then
        mask = 0
        for _, name in ipairs(a.slots or {}) do
            local index = slot_index(name)
            if index then mask = mask + 2 ^ index end
        end
    end
    local equipped = inject_plan(xi.phase.lock_slots(mask))
    local status = xi.phase.status()
    return {
        lockedSlots = status.lockedSlots, state = status.state, set = status.set,
        equipped = equipped, mask = mask,
    }
end

-- /!gs: the in-game side of the launcher's state controls. The host sees the line before it is
-- sent, so a handled line is blocked and never reaches the server.
local function gs_slots(words, action)
    local mask = locked_slots_mask()
    local names = {}
    for i = 2, #words do
        local word = words[i]:lower()
        if word == 'all' then
            mask = action == 'lock' and 0xFFFF or 0
            names = { 'all' }
        else
            local index = slot_index(word)
            if index then
                local bit = 2 ^ index
                if action == 'lock' then
                    if math.floor(mask / bit) % 2 == 0 then mask = mask + bit end
                elseif math.floor(mask / bit) % 2 == 1 then
                    mask = mask - bit
                end
                names[#names + 1] = word
            end
        end
    end
    if #names == 0 then return nil, 'usage: lock|unlock main, sub, ranged, ammo, ... (or all)' end
    inject_plan(xi.phase.lock_slots(mask))
    return (action == 'lock' and 'locked ' or 'unlocked ') .. table.concat(names, ', ')
end

local function gs_command(body)
    local words = {}
    for word in tostring(body):gmatch('[^,%s]+') do words[#words + 1] = word end
    local action = (words[1] or ''):lower()
    if action == 'lock' or action == 'unlock' then
        return gs_slots(words, action)
    elseif action == 'rest' or action == 'kite' then
        local on = (words[2] or 'on'):lower() ~= 'off'
        inject_plan(action == 'rest' and xi.phase.resting(on) or xi.phase.kiting(on))
        return action .. (on and ' on' or ' off')
    elseif action == 'focus' then
        local mode = FOCUS_MODES[(words[2] or 'auto'):lower()] or 0
        inject_plan(xi.phase.focus(mode))
        return 'focus ' .. (words[2] or 'auto')
    elseif action == 'state' or action == 'status' then
        local status = xi.phase.status()
        return tostring(status.state) .. (status.set and (' - ' .. tostring(status.set)) or '')
    end
    return 'usage: /!gs lock|unlock <slots>, rest on|off, kite on|off, focus auto|dt|pdt|mdt|eva|meva'
end

if xi.phase and xi.events and xi.events.on then
    xi.events.on('command', function(e)
        if e.blocked then return end
        local line = e.data
        if type(line) ~= 'string' then return end
        local body = line:match('^/%!gs%s+(.+)$') or line:match('^%!gs%s+(.+)$')
        if not body then return end
        e.blocked = true
        local ok, result = pcall(gs_command, body)
        if ok and type(result) == 'string' then
            xi.chat.write('GS: ' .. result, 1)
        elseif not ok then
            xi.chat.write('GS: ' .. tostring(result), 1)
        end
    end)
end

local function equip_set(a)
    local items = a.items
    if type(items) ~= 'table' then error('equip_set: items') end
    local by_id, worn = bag_index(), worn_items()
    local locked = {}
    if xi.phase then
        for _, index in ipairs(xi.phase.status().lockedSlots or {}) do locked[index] = true end
    end
    local claimed, packets, errors, skipped = {}, {}, {}, 0
    for _, entry in ipairs(items) do
        local slot = SLOT_INDEX[tostring(entry.slot or ''):lower()]
        if slot == nil then
            errors[#errors + 1] = 'unknown slot ' .. tostring(entry.slot)
        elseif locked[slot] then
            skipped = skipped + 1 -- pinned by /!gs lock: no set may override it
        else
            local bag, at, id = find_item(by_id, entry.item, claimed)
            if not bag then
                errors[#errors + 1] = tostring(entry.item) .. ' is not in this character\'s bags'
            elseif worn[slot] == id then
                skipped = skipped + 1 -- already on; GearSwap leaves a matching piece alone too
            else
                claimed[bag * 256 + at] = true
                packets[#packets + 1] = equip_packet(bag, at, slot)
            end
        end
    end
    -- Every piece leaves in the same frame, the way GearSwap's 0x050/0x051 burst does. The old
    -- coroutine.sleepf(1) per piece put one slot in each frame, so a Wear set arrived in waves
    -- and could miss the precast or midcast window it was meant for.
    for _, packet in ipairs(packets) do
        xi.packets.inject(true, packet)
    end
    return { equipped = #packets, skipped = skipped, errors = errors }
end

-- EquipViewer's icons, straight from the game's resource DATs (res_lua.c item_icon_rgba). The
-- launcher caches these as PNGs, so a slot only asks again when the item changes. Hex avoids
-- JSON's control-character escaping and is cheap to decode on the Rust side.
local HEX_BYTE = {}
for i = 0, 255 do HEX_BYTE[string.char(i)] = string.format('%02x', i) end
local function hex(s)
    -- '.' skips newlines; the RGBA bytes are arbitrary, so match every byte.
    return (s:gsub('[%z\1-\255]', HEX_BYTE))
end

local function icons(a)
    local ids = a.ids
    if type(ids) ~= 'table' then error('icons: ids') end
    local out = {}
    for _, raw in ipairs(ids) do
        local id = tonumber(raw)
        if id and id > 0 then
            local ok, rgba, w, h = pcall(res.item_icon_rgba, id)
            if ok and type(rgba) == 'string' and w and h and #rgba == w * h * 4 then
                out[#out + 1] = { id = id, width = w, height = h, rgba = hex(rgba) }
            else
                out[#out + 1] = { id = id, width = 0, height = 0, rgba = '' }
            end
        end
    end
    return { items = out }
end

-- Set previews: a GearSwap set stores item names, while icons are keyed by item id.
local function item_ids(a)
    local names = a.names
    if type(names) ~= 'table' then error('item_ids: names') end
    local out = {}
    for _, raw in ipairs(names) do
        local name = tostring(raw or '')
        local id = 0
        if name ~= '' then
            local ok, item = pcall(res.item_by_name, name)
            if ok and item and item.id then id = item.id end
        end
        out[#out + 1] = { name = name, id = id }
    end
    return { items = out }
end

-- The current job pair's spell list, for the Gear page's per-spell overrides.
local function job_spells()
    local main = game.party_member(0, 'MainJob') or 0
    local main_level = game.party_member(0, 'MainJobLevel') or 0
    local sub = game.party_member(0, 'SubJob') or 0
    local sub_level = game.party_member(0, 'SubJobLevel') or 0
    local jobs = { { id = main, level = main_level }, { id = sub, level = sub_level } }
    local out, seen = {}, {}
    local ids = {}
    local ok, list = pcall(res.spell_ids)
    if ok and type(list) == 'table' then ids = list end
    for _, id in ipairs(ids) do
        local spell = res.spell(id)
        if spell and type(spell.levels) == 'table' then
            local name = spell.name
            if type(name) == 'table' then name = name.en or name[2] or name[1] end
            local skill = MIDCAST_SKILL[spell.skill]
            for _, job in ipairs(jobs) do
                local level = job.id > 0 and spell.levels[job.id] or -1
                if level and level > 0 and level <= job.level and not seen[id] then
                    seen[id] = true
                    -- The menu icon is `icon_hq` (the detailed one), with the simple list icon as
                    -- the fallback for records that predate it. Recast is the record's base value
                    -- in quarter seconds; the HUD learns the live value from game.spell_recast.
                    local icon = tonumber(spell.icon_hq) or 0
                    if icon <= 0 or icon == 65535 then icon = tonumber(spell.icon_nq) or 0 end
                    out[#out + 1] = {
                        id = id, name = type(name) == 'string' and name or tostring(id),
                        skill = skill or '', skill_id = tonumber(spell.skill) or 0,
                        magic = tonumber(spell.type) or 0, element = tonumber(spell.element) or 0,
                        level = level,
                        icon = icon, recast = (tonumber(spell.recast_delay) or 0) / 4,
                        targets = tonumber(spell.targets) or 0,
                        categories = spell_categories(spell),
                    }
                end
            end
        end
    end
    table.sort(out, function(a, b) return tostring(a.name) < tostring(b.name) end)
    return { spells = out }
end

-- Bit arithmetic without Lua 5.3+'s operators: the host embeds a recent Lua, but these helpers
-- also keep the file loadable in the older launcher test harness.
local function has_bit(value, bit)
    return bit > 0 and math.floor((tonumber(value) or 0) / bit) % 2 == 1
end

local function job_bit(job)
    -- res.item.jobs is a 1-based mask (bit 1 WAR, bit 12 SAM, bit 13 NIN); the server's item
    -- table uses 0-based bits, so shifting by job-1 here hides exactly the job's own weapons.
    return job > 0 and 2 ^ job or 0
end

-- The current main/sub job abilities. The client's Abilities command list is rebuilt from the
-- server's 0x0AC, so it is already narrowed to this job pair and their levels; the 0x200..0x3FF
-- block is the job-ability range (weapon skills and traits are skipped).
local function job_abilities()
    local main = game.party_member(0, 'MainJob') or 0
    local main_level = game.party_member(0, 'MainJobLevel') or 0
    local sub = game.party_member(0, 'SubJob') or 0
    local sub_level = game.party_member(0, 'SubJobLevel') or 0
    local ok, ids = pcall(game.ability_commands)
    if not ok or type(ids) ~= 'table' then ids = {} end
    local out, seen = {}, {}
    for _, raw in ipairs(ids) do
        local id = tonumber(raw) or 0
        if id >= 0x200 and id < 0x400 and not seen[id] then
            local ability = res.ability(id)
            if ability then
                local name = ability.name
                if type(name) == 'table' then name = name.en or name[2] or name[1] end
                if type(name) == 'string' and name ~= '' then
                    seen[id] = true
                    out[#out + 1] = {
                        id = id, name = name, type = ability.type_name or '',
                        recastId = ability.recast_id or 0,
                        icon = tonumber(ability.icon_id) or 0,
                        targets = tonumber(ability.targets) or 0,
                    }
                end
            end
        end
    end
    table.sort(out, function(a, b)
        local an, bn = tostring(a.name):lower(), tostring(b.name):lower()
        if an == bn then return a.id < b.id end
        return an < bn
    end)
    return {
        abilities = out, main = main, main_level = main_level,
        sub = sub, sub_level = sub_level,
    }
end

-------------------------------------------------------------------------------- combat HUD
local function hud_init()
-- The Control room's per-account switches drive four in-game ImGui windows: abilities, spells,
-- trusts and weapon skills. Each type has its own layout, grouping, tile/font size and screen
-- position; everything is saved per character in <data>/hud/<character>.json. A cell is a real
-- menu icon (res.menu_icon_rgba), a button that runs /ja, /ma or /ws, and a clock-face cooldown
-- for abilities and magic. Trust spells live in their own window so the spell list stays usable.

local HUD_FILE_VERSION = 2
local HUD_GRID_GAP = 6
local HUD_MAX_BODY_HEIGHT = 420

local HUD_COLOR_TEXT = 0
local HUD_COLOR_BG = 0
local HUD_COLOR_BORDER = 0
local HUD_COLOR_ACCENT = 0
local HUD_COLOR_SHADE = 0
local HUD_COLOR_WEDGE = 0
local HUD_COLOR_WHITE = 0

local function hud_color(r, g, b, a)
    return a * 16777216 + b * 65536 + g * 256 + r
end

HUD_COLOR_TEXT = hud_color(235, 230, 222, 255)
HUD_COLOR_BG = hud_color(18, 16, 14, 232)
HUD_COLOR_BORDER = hud_color(89, 216, 242, 92)
HUD_COLOR_ACCENT = hud_color(89, 216, 242, 255)
HUD_COLOR_SHADE = hud_color(0, 0, 0, 72)
HUD_COLOR_WEDGE = hud_color(0, 0, 0, 196)
HUD_COLOR_WHITE = hud_color(255, 255, 255, 255)

local HUD_TYPES = { 'abilities', 'spells', 'trusts', 'weapon_skills' }
local HUD_TYPE_INFO = {
    abilities = { title = 'Abilities', default_group = 'job', groups = { 'job', 'type', 'none', 'custom' } },
    spells = { title = 'Spells', default_group = 'type', groups = { 'type', 'skill', 'element', 'none', 'custom' } },
    trusts = { title = 'Trusts', default_group = 'job', groups = { 'job', 'none', 'custom' } },
    weapon_skills = { title = 'Weapon skills', default_group = 'skill', groups = { 'skill', 'none', 'custom' } },
}

local HUD_DEFAULT_POSITIONS = {
    abilities = { x = 48, y = 80 },
    spells = { x = 48, y = 400 },
    trusts = { x = 900, y = 80 },
    weapon_skills = { x = 900, y = 400 },
}

local HUD_JOB_ABBR = { 'WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK', 'BST', 'BRD', 'RNG',
    'SAM', 'NIN', 'DRG', 'SMN', 'BLU', 'COR', 'PUP', 'DNC', 'SCH', 'GEO', 'RUN' }

local HUD_SPELL_MAGIC = {
    [1] = 'White Magic', [2] = 'Black Magic', [3] = 'Summoning', [4] = 'Ninjutsu',
    [5] = 'Bard Song', [6] = 'Blue Magic', [7] = 'Geomancy', [8] = 'Trust',
}
local HUD_ELEMENTS = { 'Fire', 'Ice', 'Wind', 'Earth', 'Thunder', 'Water', 'Light', 'Dark' }

-- Weapon skill id bands. 224+ is the prime/extra table, which needs its own map.
local HUD_WS_RANGES = {
    { 1, 15, 'Hand-to-Hand' }, { 16, 31, 'Dagger' }, { 32, 47, 'Sword' },
    { 48, 63, 'Great Sword' }, { 64, 79, 'Axe' }, { 80, 95, 'Great Axe' },
    { 96, 111, 'Scythe' }, { 112, 127, 'Polearm' }, { 128, 143, 'Katana' },
    { 144, 159, 'Great Katana' }, { 160, 175, 'Club' }, { 176, 191, 'Staff' },
    { 192, 207, 'Archery' }, { 208, 223, 'Marksmanship' },
}

-- Weapon skill -> its three skillchain resonance ids (1..14; 0 none). Generated from
-- data/skillchains.json (LandSandBoat weapon_skills.sql and the BGWiki Prime pages).
local HUD_WS_SC = {
    [1] = { 8, 0, 0 },
    [2] = { 5, 8, 0 },
    [3] = { 2, 0, 0 },
    [4] = { 6, 0, 0 },
    [5] = { 8, 0, 0 },
    [6] = { 3, 8, 0 },
    [7] = { 1, 8, 0 },
    [8] = { 12, 0, 0 },
    [9] = { 9, 3, 0 },
    [10] = { 13, 11, 0 },
    [11] = { 11, 1, 0 },
    [12] = { 9, 3, 0 },
    [13] = { 7, 8, 6 },
    [14] = { 13, 12, 0 },
    [15] = { 11, 5, 0 },
    [16] = { 4, 0, 0 },
    [17] = { 4, 0, 0 },
    [18] = { 5, 0, 0 },
    [19] = { 6, 0, 0 },
    [20] = { 6, 8, 0 },
    [23] = { 4, 6, 0 },
    [24] = { 12, 0, 0 },
    [25] = { 9, 1, 0 },
    [26] = { 14, 9, 0 },
    [27] = { 11, 2, 0 },
    [28] = { 12, 10, 0 },
    [29] = { 10, 4, 0 },
    [30] = { 4, 6, 8 },
    [31] = { 14, 10, 0 },
    [32] = { 4, 0, 0 },
    [33] = { 3, 0, 0 },
    [34] = { 3, 6, 0 },
    [35] = { 8, 0, 0 },
    [36] = { 4, 0, 0 },
    [37] = { 4, 0, 0 },
    [38] = { 5, 8, 0 },
    [39] = { 0, 0, 0 },
    [40] = { 4, 8, 0 },
    [41] = { 9, 0, 0 },
    [42] = { 12, 4, 0 },
    [43] = { 13, 11, 0 },
    [44] = { 12, 10, 0 },
    [45] = { 11, 5, 0 },
    [46] = { 10, 4, 0 },
    [47] = { 0, 0, 0 },
    [48] = { 4, 0, 0 },
    [49] = { 1, 0, 0 },
    [50] = { 7, 0, 0 },
    [51] = { 7, 6, 0 },
    [52] = { 5, 0, 0 },
    [53] = { 4, 0, 0 },
    [54] = { 4, 8, 0 },
    [55] = { 12, 0, 0 },
    [56] = { 12, 10, 0 },
    [57] = { 13, 11, 0 },
    [58] = { 7, 8, 6 },
    [59] = { 13, 10, 0 },
    [60] = { 12, 4, 0 },
    [61] = { 13, 12, 0 },
    [62] = { 6, 2, 10 },
    [64] = { 6, 8, 0 },
    [65] = { 7, 5, 0 },
    [66] = { 6, 0, 0 },
    [67] = { 4, 8, 0 },
    [68] = { 3, 4, 8 },
    [69] = { 4, 0, 0 },
    [70] = { 4, 8, 0 },
    [71] = { 11, 0, 0 },
    [72] = { 11, 5, 0 },
    [73] = { 14, 9, 0 },
    [74] = { 9, 5, 0 },
    [75] = { 4, 6, 0 },
    [76] = { 14, 12, 0 },
    [77] = { 10, 6, 0 },
    [78] = { 3, 8, 12 },
    [80] = { 8, 0, 0 },
    [81] = { 4, 0, 0 },
    [82] = { 5, 4, 0 },
    [83] = { 8, 0, 0 },
    [84] = { 2, 0, 0 },
    [85] = { 8, 0, 0 },
    [86] = { 7, 5, 0 },
    [87] = { 10, 0, 0 },
    [88] = { 10, 6, 0 },
    [89] = { 13, 11, 0 },
    [90] = { 12, 4, 0 },
    [91] = { 4, 6, 8 },
    [92] = { 13, 12, 0 },
    [93] = { 11, 2, 0 },
    [94] = { 1, 4, 9 },
    [96] = { 4, 0, 0 },
    [97] = { 5, 0, 0 },
    [98] = { 7, 5, 0 },
    [99] = { 2, 4, 0 },
    [100] = { 5, 4, 0 },
    [101] = { 1, 4, 0 },
    [102] = { 7, 0, 0 },
    [103] = { 10, 0, 0 },
    [104] = { 10, 4, 0 },
    [105] = { 14, 9, 0 },
    [106] = { 11, 2, 0 },
    [107] = { 2, 5, 0 },
    [108] = { 14, 10, 0 },
    [109] = { 9, 5, 0 },
    [110] = { 7, 5, 11 },
    [112] = { 1, 0, 0 },
    [113] = { 1, 8, 0 },
    [114] = { 1, 8, 0 },
    [115] = { 8, 0, 0 },
    [116] = { 2, 0, 0 },
    [117] = { 5, 1, 0 },
    [118] = { 1, 8, 0 },
    [119] = { 11, 0, 0 },
    [120] = { 9, 7, 0 },
    [121] = { 13, 10, 0 },
    [122] = { 11, 1, 0 },
    [123] = { 1, 4, 0 },
    [124] = { 13, 12, 0 },
    [125] = { 9, 1, 0 },
    [126] = { 1, 4, 9 },
    [128] = { 1, 0, 0 },
    [129] = { 4, 0, 0 },
    [130] = { 5, 0, 0 },
    [131] = { 7, 6, 0 },
    [132] = { 1, 8, 0 },
    [133] = { 2, 0, 0 },
    [134] = { 6, 8, 0 },
    [135] = { 9, 0, 0 },
    [136] = { 9, 1, 0 },
    [137] = { 14, 12, 0 },
    [138] = { 12, 2, 0 },
    [139] = { 5, 4, 0 },
    [140] = { 14, 9, 0 },
    [141] = { 11, 8, 0 },
    [142] = { 7, 5, 11 },
    [144] = { 1, 4, 0 },
    [145] = { 7, 0, 0 },
    [146] = { 1, 8, 0 },
    [147] = { 3, 0, 0 },
    [148] = { 4, 6, 0 },
    [149] = { 5, 8, 0 },
    [150] = { 7, 6, 0 },
    [151] = { 10, 5, 0 },
    [152] = { 11, 2, 0 },
    [153] = { 13, 12, 0 },
    [154] = { 9, 7, 0 },
    [155] = { 2, 4, 0 },
    [156] = { 13, 10, 0 },
    [157] = { 12, 2, 0 },
    [158] = { 11, 0, 0 },
    [159] = { 6, 2, 10 },
    [160] = { 8, 0, 0 },
    [161] = { 8, 0, 0 },
    [162] = { 5, 0, 0 },
    [165] = { 7, 5, 0 },
    [166] = { 8, 6, 0 },
    [167] = { 8, 0, 0 },
    [168] = { 11, 0, 0 },
    [169] = { 12, 2, 0 },
    [170] = { 13, 12, 0 },
    [171] = { 0, 0, 0 },
    [172] = { 7, 5, 0 },
    [174] = { 11, 8, 0 },
    [175] = { 14, 12, 0 },
    [176] = { 8, 0, 0 },
    [177] = { 8, 0, 0 },
    [178] = { 6, 8, 0 },
    [179] = { 2, 5, 0 },
    [180] = { 2, 5, 0 },
    [181] = { 6, 0, 0 },
    [182] = { 3, 8, 0 },
    [183] = { 0, 0, 0 },
    [184] = { 9, 5, 0 },
    [185] = { 14, 10, 0 },
    [186] = { 12, 10, 0 },
    [187] = { 11, 5, 0 },
    [188] = { 9, 1, 0 },
    [189] = { 2, 5, 0 },
    [191] = { 9, 7, 0 },
    [192] = { 3, 1, 0 },
    [193] = { 5, 1, 0 },
    [194] = { 3, 1, 0 },
    [196] = { 5, 1, 6 },
    [197] = { 7, 1, 0 },
    [198] = { 11, 0, 0 },
    [199] = { 11, 1, 0 },
    [200] = { 13, 10, 0 },
    [201] = { 5, 1, 0 },
    [202] = { 13, 11, 0 },
    [203] = { 12, 1, 0 },
    [204] = { 1, 4, 9 },
    [208] = { 3, 1, 0 },
    [209] = { 5, 1, 0 },
    [210] = { 3, 1, 0 },
    [212] = { 5, 1, 6 },
    [213] = { 7, 1, 0 },
    [214] = { 11, 0, 0 },
    [215] = { 11, 1, 0 },
    [216] = { 14, 12, 0 },
    [217] = { 12, 4, 0 },
    [218] = { 9, 1, 0 },
    [219] = { 7, 6, 8 },
    [220] = { 14, 9, 0 },
    [221] = { 11, 5, 0 },
    [222] = { 7, 5, 11 },
    [224] = { 12, 4, 0 },
    [225] = { 13, 10, 0 },
    [226] = { 9, 4, 0 },
    [227] = { 13, 0, 0 },
    [228] = { 13, 0, 0 },
    [231] = { 6, 2, 10 },
    [232] = { 3, 8, 12 },
    [233] = { 6, 2, 10 },
    [235] = { 7, 5, 11 },
    [238] = { 13, 12, 0 },
    [239] = { 13, 11, 0 },
}

-- fTP anchors at 1000/2000/3000 TP and main-hand hits, from data/weapon_skills.json.
local HUD_WS_STATS = {
    [1] = { ftp = { 1, 2.4, 3.4 }, hits = 3 },
    [2] = { ftp = { 1, 1, 1 }, hits = 2 },
    [3] = { ftp = { 1, 1, 1 }, hits = 2 },
    [4] = { ftp = { 1, 1, 1 }, hits = 2 },
    [5] = { ftp = { 1, 2.188, 3.75 }, hits = 5 },
    [6] = { ftp = { 1, 1, 1 }, hits = 2 },
    [7] = { ftp = { 2.05, 3.55, 5.75 }, hits = 2 },
    [8] = { ftp = { 1.7, 3, 5 }, hits = 2 },
    [9] = { ftp = { 1.25, 1.25, 1.25 }, hits = 8 },
    [10] = { ftp = { 3, 3, 3 }, hits = 2 },
    [11] = { ftp = { 1, 1, 1 }, hits = 2 },
    [12] = { ftp = { 1, 1, 1 }, hits = 6 },
    [13] = { ftp = { 1.7, 2.8, 4.5 }, hits = 3 },
    [14] = { ftp = { 1.5, 1.5, 1.5 }, hits = 4 },
    [15] = { ftp = { 1.5, 1.5, 1.5 }, hits = 5 },
    [16] = { ftp = { 1, 1, 1 }, hits = 1 },
    [17] = { ftp = { 1, 1, 1 }, hits = 1 },
    [18] = { ftp = { 1, 1, 1 }, hits = 1 },
    [19] = { ftp = { 1, 2, 3 }, hits = 1 },
    [20] = { ftp = { 1, 2.375, 3.75 }, hits = 1 },
    [23] = { ftp = { 1.188, 1.188, 1.188 }, hits = 5 },
    [24] = { ftp = { 4.5, 6.8, 8.5 }, hits = 2 },
    [25] = { ftp = { 1.25, 1.25, 1.25 }, hits = 5 },
    [26] = { ftp = { 5, 5, 5 }, hits = 1 },
    [27] = { ftp = { 4, 6.09, 8.5 }, hits = 1 },
    [28] = { ftp = { 5, 5, 5 }, hits = 2 },
    [29] = { ftp = { 1.75, 1.75, 1.75 }, hits = 4 },
    [30] = { ftp = { 2, 3, 4.5 }, hits = 1 },
    [31] = { ftp = { 5, 10.19, 13 }, hits = 1 },
    [32] = { ftp = { 1, 3, 5 }, hits = 2 },
    [33] = { ftp = { 1, 2.1, 3.4 }, hits = 1 },
    [34] = { ftp = { 1, 2.38, 3.75 }, hits = 1 },
    [35] = { ftp = { 1, 1, 1 }, hits = 1 },
    [36] = { ftp = { 1.125, 2.222, 3.523 }, hits = 1 },
    [37] = { ftp = { 1.125, 2.625, 4.125 }, hits = 1 },
    [38] = { ftp = { 1, 1, 1 }, hits = 1 },
    [39] = { ftp = { 0.125, 0.5, 1 }, hits = 1 },
    [40] = { ftp = { 1.375, 1.375, 1.375 }, hits = 4 },
    [41] = { ftp = { 1.5, 1.5, 1.5 }, hits = 3 },
    [42] = { ftp = { 4, 10.3, 13.6 }, hits = 2 },
    [43] = { ftp = { 5, 5, 5 }, hits = 1 },
    [44] = { ftp = { 4, 4, 4 }, hits = 3 },
    [45] = { ftp = { 1, 1.5, 2 }, hits = 2 },
    [46] = { ftp = { 3.797, 9.391, 12.188 }, hits = 2 },
    [47] = { ftp = { 2.75, 2.75, 2.75 }, hits = 1 },
    [48] = { ftp = { 1.5, 2.5, 3.5 }, hits = 1 },
    [49] = { ftp = { 1, 1, 1 }, hits = 1 },
    [50] = { ftp = { 1.5, 3.25, 5 }, hits = 1 },
    [51] = { ftp = { 1.5, 3.5, 6 }, hits = 1 },
    [52] = { ftp = { 1, 1, 1 }, hits = 1 },
    [53] = { ftp = { 1, 2.25, 4 }, hits = 1 },
    [54] = { ftp = { 1.5, 3.5, 6.5 }, hits = 2 },
    [55] = { ftp = { 2.5, 5, 7.5 }, hits = 1 },
    [56] = { ftp = { 1.5, 3, 5 }, hits = 1 },
    [57] = { ftp = { 3, 3, 3 }, hits = 1 },
    [58] = { ftp = { 3.5, 3.5, 3.5 }, hits = 1 },
    [59] = { ftp = { 4.75, 7.5, 9.75 }, hits = 1 },
    [60] = { ftp = { 0.719, 1.5, 2.25 }, hits = 5 },
    [61] = { ftp = { 2.25, 4.5, 6.75 }, hits = 2 },
    [62] = { ftp = { 3.3, 6.6, 9.9 }, hits = 1 },
    [64] = { ftp = { 1, 3, 6 }, hits = 2 },
    [65] = { ftp = { 1, 1, 1 }, hits = 1 },
    [66] = { ftp = { 1, 1, 1 }, hits = 1 },
    [67] = { ftp = { 1.5, 3, 5.5 }, hits = 1 },
    [68] = { ftp = { 2, 4, 6.5 }, hits = 1 },
    [69] = { ftp = { 1, 1, 1 }, hits = 5 },
    [70] = { ftp = { 2.562, 6.469, 10.375 }, hits = 1 },
    [71] = { ftp = { 4, 10.3, 13.6 }, hits = 1 },
    [72] = { ftp = { 1.75, 1.75, 1.75 }, hits = 3 },
    [73] = { ftp = { 2.75, 2.75, 2.75 }, hits = 1 },
    [74] = { ftp = { 3.062, 4.688, 7.562 }, hits = 1 },
    [75] = { ftp = { 4.5, 4.5, 4.5 }, hits = 1 },
    [76] = { ftp = { 3.75, 5.5, 8.5 }, hits = 1 },
    [77] = { ftp = { 1.08, 1.08, 1.08 }, hits = 4 },
    [78] = { ftp = { 1.5, 7, 12.5 }, hits = 5 },
    [80] = { ftp = { 1, 1, 1 }, hits = 1 },
    [81] = { ftp = { 1, 1, 1 }, hits = 1 },
    [82] = { ftp = { 1, 1, 1 }, hits = 2 },
    [83] = { ftp = { 1, 1, 1 }, hits = 1 },
    [84] = { ftp = { 1, 1, 1 }, hits = 1 },
    [85] = { ftp = { 1, 1, 1 }, hits = 1 },
    [86] = { ftp = { 1, 1, 1 }, hits = 3 },
    [87] = { ftp = { 1, 1, 1 }, hits = 1 },
    [88] = { ftp = { 1.5, 2.5, 4 }, hits = 1 },
    [89] = { ftp = { 2.75, 2.75, 2.75 }, hits = 1 },
    [90] = { ftp = { 1, 3, 5 }, hits = 3 },
    [91] = { ftp = { 2.75, 2.75, 2.75 }, hits = 1 },
    [92] = { ftp = { 2, 2, 2 }, hits = 2 },
    [93] = { ftp = { 1, 3.5, 6.5 }, hits = 4 },
    [94] = { ftp = { 3.05, 9.15, 15.25 }, hits = 1 },
    [96] = { ftp = { 1, 2.5, 4 }, hits = 1 },
    [97] = { ftp = { 1, 3.54, 6.07 }, hits = 1 },
    [98] = { ftp = { 1, 4.17, 8.6 }, hits = 1 },
    [99] = { ftp = { 1, 1, 1 }, hits = 1 },
    [100] = { ftp = { 1, 1, 1 }, hits = 1 },
    [101] = { ftp = { 1, 1, 1 }, hits = 1 },
    [102] = { ftp = { 0.875, 0.875, 0.875 }, hits = 4 },
    [103] = { ftp = { 2, 4, 7 }, hits = 2 },
    [104] = { ftp = { 1.375, 2.75, 4.75 }, hits = 1 },
    [105] = { ftp = { 2.75, 2.75, 2.75 }, hits = 1 },
    [106] = { ftp = { 0.5, 3.25, 6 }, hits = 4 },
    [107] = { ftp = { 3.5, 3.5, 3.5 }, hits = 1 },
    [108] = { ftp = { 3, 3, 3 }, hits = 1 },
    [109] = { ftp = { 0.75, 1.25, 2 }, hits = 4 },
    [110] = { ftp = { 3, 6, 9 }, hits = 1 },
    [112] = { ftp = { 1, 1.5, 2 }, hits = 2 },
    [113] = { ftp = { 1.5, 2, 2.5 }, hits = 1 },
    [114] = { ftp = { 1, 2, 3 }, hits = 1 },
    [115] = { ftp = { 1, 1, 1 }, hits = 1 },
    [116] = { ftp = { 1, 1, 1 }, hits = 5 },
    [117] = { ftp = { 1, 1, 1 }, hits = 1 },
    [118] = { ftp = { 1, 1, 1 }, hits = 3 },
    [119] = { ftp = { 1.75, 1.75, 1.75 }, hits = 1 },
    [120] = { ftp = { 1, 3, 5.5 }, hits = 2 },
    [121] = { ftp = { 3, 3, 3 }, hits = 1 },
    [122] = { ftp = { 1, 1, 1 }, hits = 4 },
    [123] = { ftp = { 3, 3.7, 4.5 }, hits = 1 },
    [124] = { ftp = { 3, 3, 3 }, hits = 1 },
    [125] = { ftp = { 0.75, 1.25, 1.75 }, hits = 4 },
    [126] = { ftp = { 2.17, 5.36, 8.55 }, hits = 2 },
    [128] = { ftp = { 1, 1, 1 }, hits = 1 },
    [129] = { ftp = { 1, 1, 1 }, hits = 2 },
    [130] = { ftp = { 0.5, 1.5, 2.25 }, hits = 1 },
    [131] = { ftp = { 0.5, 1.5, 2.5 }, hits = 1 },
    [132] = { ftp = { 0.5, 1.5, 2.25 }, hits = 2 },
    [133] = { ftp = { 1, 3, 5 }, hits = 1 },
    [134] = { ftp = { 1.375, 1.375, 1.375 }, hits = 3 },
    [135] = { ftp = { 4.5, 11.5, 15.35 }, hits = 1 },
    [136] = { ftp = { 1.25, 1.25, 1.25 }, hits = 5 },
    [137] = { ftp = { 5, 5, 5 }, hits = 1 },
    [138] = { ftp = { 1, 1, 1 }, hits = 1 },
    [139] = { ftp = { 3, 3, 3 }, hits = 1 },
    [140] = { ftp = { 5, 5, 5 }, hits = 1 },
    [141] = { ftp = { 1, 1, 1 }, hits = 5 },
    [142] = { ftp = { 4, 11.357, 18.715 }, hits = 4 },
    [144] = { ftp = { 1, 1.5, 2 }, hits = 2 },
    [145] = { ftp = { 1, 1, 1 }, hits = 1 },
    [146] = { ftp = { 0.5, 1.5, 2.5 }, hits = 1 },
    [147] = { ftp = { 0.5, 1.5, 2.5 }, hits = 1 },
    [148] = { ftp = { 0.5, 1.5, 2.5 }, hits = 2 },
    [149] = { ftp = { 0.5, 1.5, 2.5 }, hits = 1 },
    [150] = { ftp = { 1.562, 2.688, 4.125 }, hits = 1 },
    [151] = { ftp = { 1.562, 2.688, 4.125 }, hits = 1 },
    [152] = { ftp = { 1.562, 2.688, 4.125 }, hits = 1 },
    [153] = { ftp = { 3, 3, 3 }, hits = 1 },
    [154] = { ftp = { 1, 1, 1 }, hits = 3 },
    [155] = { ftp = { 2.625, 2.625, 2.625 }, hits = 1 },
    [156] = { ftp = { 3.75, 5.75, 8 }, hits = 1 },
    [157] = { ftp = { 1.375, 2.188, 2.688 }, hits = 2 },
    [158] = { ftp = { 1, 1.5, 2 }, hits = 2 },
    [159] = { ftp = { 3.66, 7.33, 11 }, hits = 1 },
    [160] = { ftp = { 1.625, 3, 4.625 }, hits = 1 },
    [161] = { ftp = { 2.125, 3.625, 6.125 }, hits = 1 },
    [162] = { ftp = { 1, 1, 1 }, hits = 1 },
    [165] = { ftp = { 1, 1, 1 }, hits = 1 },
    [166] = { ftp = { 1, 1, 1 }, hits = 1 },
    [167] = { ftp = { 3.5, 8.75, 11.75 }, hits = 1 },
    [168] = { ftp = { 1.125, 1.125, 1.125 }, hits = 6 },
    [169] = { ftp = { 3, 7.2, 9.6 }, hits = 2 },
    [170] = { ftp = { 4.25, 4.25, 4.25 }, hits = 1 },
    [171] = { ftp = { 2.5, 4, 7 }, hits = 1 },
    [172] = { ftp = { 3, 3, 3 }, hits = 1 },
    [174] = { ftp = { 0.9, 0.9, 0.9 }, hits = 7 },
    [175] = { ftp = { 2.8, 2.8, 2.8 }, hits = 1 },
    [176] = { ftp = { 1, 1.25, 2.25 }, hits = 1 },
    [177] = { ftp = { 1, 2, 2.5 }, hits = 1 },
    [178] = { ftp = { 1, 2.312, 3.625 }, hits = 1 },
    [179] = { ftp = { 1, 2, 2.5 }, hits = 1 },
    [180] = { ftp = { 1, 2.5, 4 }, hits = 1 },
    [181] = { ftp = { 1, 1, 1 }, hits = 1 },
    [182] = { ftp = { 1, 3, 5 }, hits = 1 },
    [183] = { ftp = { 1, 1.5, 2 }, hits = 1 },
    [184] = { ftp = { 2, 2.5, 3 }, hits = 1 },
    [185] = { ftp = { 3, 3, 3 }, hits = 1 },
    [186] = { ftp = { 1.75, 1.75, 1.75 }, hits = 1 },
    [187] = { ftp = { 2.25, 2.25, 2.25 }, hits = 1 },
    [188] = { ftp = { 2, 2, 2 }, hits = 1 },
    [189] = { ftp = { 2.75, 4, 5 }, hits = 1 },
    [191] = { ftp = { 1.375, 1.375, 1.375 }, hits = 3 },
    [192] = { ftp = { 0.5, 0.75, 1 }, hits = 1 },
    [193] = { ftp = { 1, 1, 1 }, hits = 1 },
    [194] = { ftp = { 1, 1, 1 }, hits = 1 },
    [196] = { ftp = { 5, 5, 5 }, hits = 1 },
    [197] = { ftp = { 2, 2, 2 }, hits = 1 },
    [198] = { ftp = { 3.5, 3.5, 3.5 }, hits = 1 },
    [199] = { ftp = { 1.5, 2.5, 5 }, hits = 1 },
    [200] = { ftp = { 2.75, 2.75, 2.75 }, hits = 1 },
    [201] = { ftp = { 3, 4.25, 7 }, hits = 2 },
    [202] = { ftp = { 1.75, 1.75, 1.75 }, hits = 3 },
    [203] = { ftp = { 3, 3, 3 }, hits = 1 },
    [204] = { ftp = { 2.75, 5.5, 8.25 }, hits = 1 },
    [208] = { ftp = { 0.5, 1.55, 2.1 }, hits = 1 },
    [209] = { ftp = { 1, 1, 1 }, hits = 1 },
    [210] = { ftp = { 1, 1, 1 }, hits = 1 },
    [212] = { ftp = { 5, 5, 5 }, hits = 1 },
    [213] = { ftp = { 2, 2, 2 }, hits = 1 },
    [214] = { ftp = { 3.5, 3.5, 3.5 }, hits = 1 },
    [215] = { ftp = { 1.5, 2.5, 5 }, hits = 1 },
    [216] = { ftp = { 3, 3, 3 }, hits = 1 },
    [217] = { ftp = { 3.891, 6.391, 9.391 }, hits = 1 },
    [218] = { ftp = { 4, 6.7, 10 }, hits = 1 },
    [219] = { ftp = { 3, 3, 3 }, hits = 1 },
    [220] = { ftp = { 5.5, 5.5, 5.5 }, hits = 1 },
    [221] = { ftp = { 2, 3, 4 }, hits = 2 },
    [222] = { ftp = { 2.5, 5, 7.5 }, hits = 1 },
    [224] = { ftp = { 1.188, 1.188, 1.188 }, hits = 4 },
    [225] = { ftp = { 1.633, 1.633, 1.633 }, hits = 3 },
    [226] = { ftp = { 1, 1, 1 }, hits = 5 },
    [227] = { ftp = { 3, 3, 3 }, hits = 1 },
    [228] = { ftp = { 1, 2, 3 }, hits = 2 },
    [231] = { ftp = { 3.128, 7.273, 11.414 }, hits = 2 },
    [232] = { ftp = { 5.758, 14.516, 23.277 }, hits = 4 },
    [233] = { ftp = { 6.6, 13.35, 20.1 }, hits = 1 },
    [235] = { ftp = { 3.95, 7.89, 11.84 }, hits = 1 },
    [238] = { ftp = { 4.5, 6, 7.5 }, hits = 1 },
    [239] = { ftp = { 3, 4.5, 6 }, hits = 1 },
}

-- Skillchain resonance ids from the server enum (data/enums/skillchain_type.yaml).
local HUD_SC_NAMES = {
    'Transfixion', 'Compression', 'Liquefaction', 'Scission', 'Reverberation',
    'Detonation', 'Induration', 'Impaction', 'Gravitation', 'Distortion',
    'Fusion', 'Fragmentation', 'Light', 'Darkness',
}
local HUD_SC_TIER = { 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3 }
local HUD_SC_COLORS = {
    { 0.95, 0.90, 0.55 }, { 0.55, 0.35, 0.75 }, { 0.95, 0.50, 0.20 }, { 0.65, 0.42, 0.22 },
    { 0.25, 0.55, 0.95 }, { 0.35, 0.85, 0.35 }, { 0.35, 0.80, 0.90 }, { 0.65, 0.35, 0.95 },
    { 0.55, 0.30, 0.75 }, { 0.25, 0.65, 0.95 }, { 0.95, 0.30, 0.25 }, { 0.30, 0.85, 0.55 },
    { 0.98, 0.95, 0.65 }, { 0.35, 0.25, 0.75 },
}
local HUD_SC_LABELS = { 'Any' }
for id = 1, #HUD_SC_NAMES do
    HUD_SC_LABELS[#HUD_SC_LABELS + 1] = string.format('L%d %s', HUD_SC_TIER[id], HUD_SC_NAMES[id])
end
-- Representative item icons for weapon-skill group titles. The equipped main weapon's own icon
-- wins when its skill matches; these cover the other weapon tabs a job can still see.
local HUD_WS_TITLE_SKILL = {
    ['Hand-to-Hand'] = 1, ['Dagger'] = 2, ['Sword'] = 3, ['Great Sword'] = 4, ['Axe'] = 5,
    ['Great Axe'] = 6, ['Scythe'] = 7, ['Polearm'] = 8, ['Katana'] = 9, ['Great Katana'] = 10,
    ['Club'] = 11, ['Staff'] = 12, ['Archery'] = 25, ['Marksmanship'] = 26,
}
local HUD_WS_TITLE_ITEM = {
    ['Hand-to-Hand'] = 16385, ['Dagger'] = 16465, ['Sword'] = 16535, ['Great Sword'] = 16590,
    ['Axe'] = 16640, ['Great Axe'] = 16705, ['Scythe'] = 16774, ['Polearm'] = 16835,
    ['Katana'] = 16966, ['Great Katana'] = 16982, ['Club'] = 17034, ['Staff'] = 17088,
    ['Archery'] = 17152, ['Marksmanship'] = 19741,
}
local HUD_TP_COST = 1000
local HUD_SC_DELAY = 3.0
local HUD_SC_BASE = 10.0

local function hud_sc_name(id) return HUD_SC_NAMES[tonumber(id) or 0] or 'None' end
local function hud_sc_tier(id) return HUD_SC_TIER[tonumber(id) or 0] or 0 end
local function hud_sc_props(id) return HUD_WS_SC[tonumber(id) or 0] end
local function hud_ws_stats(id) return HUD_WS_STATS[tonumber(id) or 0] end
local function hud_sc_has(props, target)
    if not props or not target or target <= 0 then return false end
    for i = 1, 3 do
        if (props[i] or 0) == target then return true end
    end
    return false
end
local function hud_sc_primary(props)
    if not props then return 0 end
    local best, best_tier = 0, 0
    for i = 1, 3 do
        local id = props[i] or 0
        local tier = hud_sc_tier(id)
        if tier > best_tier then best, best_tier = id, tier end
    end
    return best
end

-- Job ability id -> job, generated from the server's job_abilities table. The client
-- list from 0x0AC gives the actions; this table only says which job owns each name.
local HUD_ABILITY_JOBS = {
    [1] = "Aggressor|Berserk|Blood Rage|Brazen Rush|Defender|Mighty Strikes|Provoke|Restraint|Retaliation|Tomahawk|Warcry|Warriors Charge", -- WAR
    [2] = "Boost|Chakra|Chi Blast|Counterstance|Dodge|Focus|Footwork|Formless Strikes|Hundred Fists|Impetus|Inner Strength|Mantra|Perfect Counter", -- MNK
    [3] = "Afflatus Misery|Afflatus Solace|Asylum|Benediction|Devotion|Divine Caress|Divine Seal|Martyr|Sacrosanctity", -- WHM
    [4] = "Cascade|Elemental Seal|Enmity Douse|Mana Wall|Manafont|Manawell|Subtle Sorcery", -- BLM
    [5] = "Chainspell|Composure|Convert|Saboteur|Spontaneity|Stymie", -- RDM
    [6] = "Accomplice|Assassins Charge|Bully|Collaborator|Conspirator|Despoil|Feint|Flee|Hide|Larceny|Mug|Perfect Dodge|Sneak Attack|Steal|Trick Attack", -- THF
    [7] = "Chivalry|Cover|Divine Emblem|Fealty|Holy Circle|Intervene|Invincible|Majesty|Palisade|Rampart|Sentinel|Sepulcher|Shield Bash", -- PLD
    [8] = "Arcane Circle|Arcane Crest|Blood Weapon|Consume Mana|Dark Seal|Diabolic Eye|Last Resort|Nether Void|Scarlet Delirium|Soul Enslavement|Souleater|Weapon Bash", -- DRK
    [9] = "Bestial Loyalty|Call Beast|Charm|Familiar|Feral Howl|Fight|Gauge|Heel|Killer Instinct|Leave|Pet Commands|Ready|Reward|Run Wild|Sic|Snarl|Spur|Stay|Tame|Unleash", -- BST
    [10] = "Clarion Call|Marcato|Nightingale|Pianissimo|Soul Voice|Tenuto|Troubadour", -- BRD
    [11] = "Barrage|Bounty Shot|Camouflage|Decoy Shot|Double Shot|Eagle Eye Shot|Flashy Shot|Overkill|Scavenge|Shadowbind|Sharpshot|Stealth Shot|Unlimited Shot|Velocity Shot", -- RNG
    [12] = "Blade Bash|Hagakure|Hamanoha|Hasso|Konzen-ittai|Meditate|Meikyo Shisui|Seigan|Sekkanoki|Sengikori|Shikikoyo|Third Eye|Warding Circle|Yaegasumi", -- SAM
    [13] = "Futae|Innin|Issekigan|Mijin Gakure|Mikage|Sange|Yonin", -- NIN
    [14] = "Ancient Circle|Angon|Call Wyvern|Deep Breathing|Dismiss|Dragon Breaker|Fly High|High Jump|Jump|Restoring Breath|Smiting Breath|Soul Jump|Spirit Bond|Spirit Jump|Spirit Link|Spirit Surge|Steady Wing|Super Jump", -- DRG
    [15] = "Apogee|Assault|Astral Conduit|Astral Flow|Avatars Favor|Blood Pact Rage|Blood Pact Ward|Elemental Siphon|Mana Cede|Release|Retreat", -- SMN
    [16] = "Azure Lore|Burst Affinity|Chain Affinity|Convergence|Diffusion|Efflux|Unbridled Learning|Unbridled Wisdom", -- BLU
    [17] = "Allies Roll|Avengers Roll|Beast Roll|Blitzers Roll|Bolters Roll|Casters Roll|Chaos Roll|Choral Roll|Companions Roll|Corsairs Roll|Coursers Roll|Crooked Cards|Cutting Cards|Dancers Roll|Dark Shot|Double-up|Drachen Roll|Earth Shot|Evokers Roll|Fighters Roll|Fire Shot|Fold|Gallants Roll|Healers Roll|Hunters Roll|Ice Shot|Light Shot|Maguss Roll|Misers Roll|Monks Roll|Naturalists Roll|Ninja Roll|Phantom Roll|Puppet Roll|Quick Draw|Random Deal|Rogues Roll|Runeists Roll|Samurai Roll|Scholars Roll|Snake Eye|Tacticians Roll|Thunder Shot|Triple Shot|Warlocks Roll|Water Shot|Wild Card|Wind Shot|Wizards Roll", -- COR
    [18] = "Activate|Cooldown|Dark Maneuver|Deactivate|Deploy|Deus Ex Automata|Earth Maneuver|Fire Maneuver|Heady Artifice|Ice Maneuver|Light Maneuver|Maintenance|Overdrive|Repair|Retrieve|Role Reversal|Tactical Switch|Thunder Maneuver|Ventriloquy|Water Maneuver|Wind Maneuver", -- PUP
    [19] = "Animated Flourish|Aspir Samba|Aspir Samba Ii|Box Step|Building Flourish|Chocobo Jig|Chocobo Jig Ii|Climactic Flourish|Contradance|Curing Waltz|Curing Waltz Ii|Curing Waltz Iii|Curing Waltz Iv|Curing Waltz V|Desperate Flourish|Divine Waltz|Divine Waltz Ii|Drain Samba|Drain Samba Ii|Drain Samba Iii|Fan Dance|Feather Step|Flourishes I|Flourishes Ii|Flourishes Iii|Grand Pas|Haste Samba|Healing Waltz|Jigs|No Foot Rise|Presto|Quickstep|Reverse Flourish|Saber Dance|Sambas|Spectral Jig|Steps|Striking Flourish|Stutter Step|Ternary Flourish|Trance|Violent Flourish|Waltzes|Wild Flourish", -- DNC
    [20] = "Accession|Addendum Black|Addendum White|Alacrity|Altruism|Caper Emissarius|Celerity|Dark Arts|Ebullience|Enlightenment|Equanimity|Focalization|Immanence|Libra|Light Arts|Manifestation|Modus Veritas|Parsimony|Penury|Perpetuance|Rapture|Stratagems|Sublimation|Tabula Rasa|Tranquility", -- SCH
    [21] = "Blaze Of Glory|Bolster|Collimated Fervor|Concentric Pulse|Dematerialize|Ecliptic Attrition|Entrust|Full Circle|Lasting Emanation|Life Cycle|Mending Halation|Radial Arcana|Theurgic Focus|Widened Compass", -- GEO
    [22] = "Battuta|Effusion|Elemental Sforzo|Embolden|Flabra|Gambit|Gelus|Ignis|Liement|Lunge|Lux|Odyllic Subterfuge|One For All|Pflug|Rayke|Rune Enchantment|Sulpor|Swipe|Swordplay|Tellus|Tenebrae|Unda|Valiance|Vallation|Vivacious Pulse|Ward", -- RUN
}

-- Trust main jobs, from BGWiki:Trusts. The client records trust spells without a job,
-- so the main job is the grouping key; unknown names fall back to Other.
local HUD_TRUST_JOBS = {
    ["Shantotto"] = "BLM",
    ["Naji"] = "WAR",
    ["Kupipi"] = "WHM",
    ["Excenmille"] = "PLD",
    ["Ayame"] = "SAM",
    ["Nanaa Mihgo"] = "THF",
    ["Curilla"] = "PLD",
    ["Volker"] = "WAR",
    ["Ajido-Marujido"] = "BLM",
    ["Trion"] = "PLD",
    ["Zeid"] = "DRK",
    ["Lion"] = "THF",
    ["Tenzen"] = "SAM",
    ["Mihli Aliapoh"] = "WHM",
    ["Valaineral"] = "PLD",
    ["Joachim"] = "BRD",
    ["Naja Salaheem"] = "MNK",
    ["Prishe"] = "MNK",
    ["Ulmia"] = "BRD",
    ["Shikaree Z"] = "DRG",
    ["Cherukiki"] = "WHM",
    ["Iron Eater"] = "WAR",
    ["Gessho"] = "NIN",
    ["Gadalar"] = "BLM",
    ["Rainemard"] = "RDM",
    ["Ingrid"] = "WHM",
    ["Lehko Habhoka"] = "THF",
    ["Nashmeira"] = "PUP",
    ["Zazarg"] = "MNK",
    ["Ovjang"] = "RDM",
    ["Mnejing"] = "PLD",
    ["Sakura"] = "GEO",
    ["Luzaf"] = "COR",
    ["Najelith"] = "RNG",
    ["Aldo"] = "THF",
    ["Moogle"] = "GEO",
    ["Fablinix"] = "THF",
    ["Maat"] = "MNK",
    ["D. Shantotto"] = "BLM",
    ["Star Sibyl"] = "GEO",
    ["Karaha-Baruha"] = "WHM",
    ["Cid"] = "WAR",
    ["Gilgamesh"] = "SAM",
    ["Areuhat"] = "WAR",
    ["Semih Lafihna"] = "RNG",
    ["Elivira"] = "RNG",
    ["Noillurie"] = "SAM",
    ["Lhu Mhakaracca"] = "BST",
    ["Ferreous Coffin"] = "WHM",
    ["Lilisette"] = "DNC",
    ["Mumor"] = "DNC",
    ["Uka Totlihn"] = "DNC",
    ["Klara"] = "WAR",
    ["Romaa Mihgo"] = "THF",
    ["Kuyin Hathdenna"] = "GEO",
    ["Rahal"] = "PLD",
    ["Koru-Moru"] = "RDM",
    ["Pieuje (UC)"] = "WHM",
    ["I. Shield (UC)"] = "WAR",
    ["Apururu (UC)"] = "WHM",
    ["Jakoh (UC)"] = "THF",
    ["Flaviria (UC)"] = "DRG",
    ["Babban"] = "MNK",
    ["Abenzio"] = "MNK",
    ["Rughadjeen"] = "PLD",
    ["Kukki-Chebukki"] = "BLM",
    ["Margret"] = "RNG",
    ["Chacharoon"] = "THF",
    ["Lhe Lhangavo"] = "MNK",
    ["Arciela"] = "RDM",
    ["Mayakov"] = "DNC",
    ["Qultada"] = "COR",
    ["Adelheid"] = "SCH",
    ["Amchuchu"] = "RUN",
    ["Brygid"] = "GEO",
    ["Mildaurion"] = "PLD",
    ["Halver"] = "PLD",
    ["Rongelouts"] = "WAR",
    ["Leonoyne"] = "BLM",
    ["Maximilian"] = "THF",
    ["Kayeel-Payeel"] = "BLM",
    ["Robel-Akbel"] = "BLM",
    ["Kupofried"] = "GEO",
    ["Selh'teus"] = "PLD",
    ["Yoran-Oran (UC)"] = "WHM",
    ["Sylvie (UC)"] = "GEO",
    ["Abquhbah"] = "WAR",
    ["Balamor"] = "DRK",
    ["August"] = "PLD",
    ["Rosulatia"] = "BLM",
    ["Teodor"] = "BLM",
    ["Ullegore"] = "BLM",
    ["Makki-Chebukki"] = "RNG",
    ["King of Hearts"] = "RDM",
    ["Morimar"] = "WAR",
    ["Darrcuiln"] = "WAR",
    ["AAHM"] = "NIN",
    ["AAEV"] = "PLD",
    ["AAMR"] = "BST",
    ["AATT"] = "BLM",
    ["AAGK"] = "SAM",
    ["Iroha"] = "SAM",
    ["Ygnas"] = "WHM",
    ["Monberaux"] = "PLD",
    ["Cornelia"] = "GEO",
    ["Matsui-P"] = "NIN",
    ["Excenmille [S]"] = "WAR",
    ["Ayame (UC)"] = "SAM",
    ["Maat (UC)"] = "MNK",
    ["Aldo (UC)"] = "THF",
    ["Naja (UC)"] = "MNK",
    ["Lion II"] = "THF",
    ["Zeid II"] = "DRK",
    ["Prishe II"] = "WHM",
    ["Nashmeira II"] = "WHM",
    ["Lilisette II"] = "DNC",
    ["Tenzen II"] = "SAM",
    ["Mumor II"] = "BLM",
    ["Ingrid II"] = "WHM",
    ["Arciela II"] = "RDM",
    ["Iroha II"] = "SAM",
    ["Shantotto II"] = "BLM",
}

-- Weapon skill id -> weapon type. The client lists weapon skills as action ids 1..255;
-- these are the id bands the game itself uses for the skill menu.
local HUD_WS_SKILL = {
    [224] = "Dagger", [225] = "Sword", [226] = "Sword", [227] = "Sword",
    [228] = "Hand-to-Hand", [231] = "Hand-to-Hand", [232] = "Dagger",
    [233] = "Sword", [235] = "Staff", [238] = "Sword", [239] = "Sword",
}
-- Invert the compact job table once. The client and the server spell some names differently
-- ("Addendum: White" vs "Addendum White", "One for All" vs "One For All"), so the lookup key is
-- case- and punctuation-insensitive.
local function hud_ability_key(name)
    return tostring(name or ''):lower():gsub('[^%w]', '')
end

local HUD_ABILITY_JOB = {}
for job, names in pairs(HUD_ABILITY_JOBS) do
    for name in tostring(names):gmatch('[^|]+') do HUD_ABILITY_JOB[hud_ability_key(name)] = job end
end

-- Scholar's stratagems split further than a job label: a SCH's useful buttons are the ones that
-- match the current Arts. Everything else stays in Other so the light/dark pages stay short.
local HUD_SCH_LIGHT = {
    ['Light Arts'] = true, ['Penury'] = true, ['Celerity'] = true, ['Rapture'] = true,
    ['Accession'] = true, ['Focalization'] = true, ['Perpetuance'] = true,
    ['Altruism'] = true, ['Tranquility'] = true,
}
local HUD_SCH_DARK = {
    ['Dark Arts'] = true, ['Parsimony'] = true, ['Alacrity'] = true, ['Ebullience'] = true,
    ['Manifestation'] = true, ['Equanimity'] = true, ['Enlightenment'] = true,
    ['Stormsurge'] = true,
}

-- Deliberately terse labels. At 42-48 px the stock spell names do not fit; the tooltip keeps the
-- full name, level and recast. These are the names the game's own menus abbreviate most often.
local HUD_SHORT = {
    ['Cure'] = 'CURE', ['Curaga'] = 'CURAGA', ['Cura'] = 'CURA',
    ['Protect'] = 'PROT', ['Shell'] = 'SHEL', ['Refresh'] = 'REFR', ['Regen'] = 'REGN',
    ['Haste'] = 'HAST', ['Dispel'] = 'DISP', ['Sleep'] = 'SLEP', ['Sleepga'] = 'SLEEP',
    ['Silence'] = 'SILN', ['Paralyze'] = 'PARA', ['Slow'] = 'SLOW', ['Gravity'] = 'GRAV',
    ['Bind'] = 'BIND', ['Blind'] = 'BLND', ['Poison'] = 'PSN', ['Bio'] = 'BIO',
    ['Dia'] = 'DIA', ['Banish'] = 'BAN', ['Holy'] = 'HOLY', ['Flare'] = 'FLAR',
    ['Freeze'] = 'FRZ', ['Tornado'] = 'TRND', ['Quake'] = 'QUAK', ['Burst'] = 'BRST',
    ['Flood'] = 'FLOD', ['Meteor'] = 'METR', ['Death'] = 'DEATH', ['Aspir'] = 'ASPR',
    ['Drain'] = 'DRAN', ['Stun'] = 'STUN', ['Utsusemi: Ichi'] = 'UTSU1',
    ['Utsusemi: Ni'] = 'UTSU2', ['Monomi: Ichi'] = 'MONO1', ['Tonko: Ichi'] = 'TONK1',
    ['Migawari: Ichi'] = 'MIGA1', ['Sneak'] = 'SNEAK', ['Invisible'] = 'INVS',
    ['Deodorize'] = 'DEOD', ['Spectral Jig'] = 'SPJIG', ['Chocobo Jig'] = 'CJIG',
    ['Mazurka'] = 'MAZU', ['March'] = 'MARCH', ['Minuet'] = 'MINU', ['Madrigal'] = 'MADR',
    ['Prelude'] = 'PREL', ['Ballad'] = 'BALL', ['Paeon'] = 'PAEO', ['Carol'] = 'CARL',
    ['Hymnus'] = 'HYMN', ['Etude'] = 'ETUD', ['Opera'] = 'OPRA', ['Requiem'] = 'REQM',
    ['Threnody'] = 'THRN', ['Lullaby'] = 'LULL', ['Elegy'] = 'ELEG', ['Finale'] = 'FINL',
    ['Mambo'] = 'MAMB', ['Light Arts'] = 'L.ART', ['Dark Arts'] = 'D.ART',
    ['Addendum: White'] = 'ADD.W', ['Addendum: Black'] = 'ADD.B',
    ['Mighty Strikes'] = 'MIGHTY', ['Hundred Fists'] = '100FIST', ['Benediction'] = 'BENED',
    ['Manafont'] = 'MANA', ['Chainspell'] = 'CHAIN', ['Perfect Dodge'] = 'PERF',
    ['Invincible'] = 'INVINC', ['Blood Weapon'] = 'BLDWP', ['Soul Voice'] = 'SOUL',
    ['Meikyo Shisui'] = 'MEIKYO', ['Mijin Gakure'] = 'MIJIN', ['Astral Flow'] = 'ASTRAL',
    ['Azure Lore'] = 'AZURE', ['Wild Card'] = 'WILD', ['Tabula Rasa'] = 'TABULA',
    ['D. Shantotto'] = 'D.SHAN', ['Nanaa Mihgo'] = 'NANAA', ['Mihli Aliapoh'] = 'MIHLI',
    ['Naja Salaheem'] = 'NAJA', ['Shikaree Z'] = 'SHIKA', ['Iron Eater'] = 'IRON',
    ['Star Sibyl'] = 'STAR', ['King of Hearts'] = 'KING', ['Babban Mheillea'] = 'BABBAN',
    ['Tachi: Yukikaze'] = 'YUKI', ['Tachi: Gekko'] = 'GEKKO', ['Tachi: Kasha'] = 'KASHA',
    ['Tachi: Mumei'] = 'MUMEI', ['Knights of Round'] = 'KNIGHT',
    ['Stringing Pummel'] = 'STRING', ['Asuran Fists'] = 'ASURAN',
}

local HUD_ROMAN = { I = '1', II = '2', III = '3', IV = '4', V = '5', VI = '6', VII = '7', VIII = '8', IX = '9', X = '10' }

local function hud_upper_first(word)
    if word == '' then return word end
    return word:sub(1, 1):upper() .. word:sub(2):lower()
end

-- A short label that fits a small tile and never ends in an ellipsis. The launcher's tooltip
-- shows item.name, so a clipped label is still discoverable.
local function hud_short_name(name)
    name = tostring(name or ''):gsub('^%s+', ''):gsub('%s+$', '')
    if name == '' then return '?', '?' end
    local exact = HUD_SHORT[name]
    if exact then return exact, exact:sub(1, 3) end

    local base, roman = name:match('^(.-)%s+([IVX]+)$')
    if base and HUD_ROMAN[roman] then
        local stem = HUD_SHORT[base] or base
        if #stem > 4 then stem = stem:sub(1, 4) end
        local short = stem:upper() .. HUD_ROMAN[roman]
        return short, short:sub(1, 3)
    end

    -- Ninjutsu and Tachi names use a colon. Elemental ninjutsu keeps the element prefix plus
    -- the tier digit ("Katon: Ichi" -> KATO1); a Tachi name keeps the technique half.
    local prefix, tail = name:match('^(.-):%s*(.+)$')
    local words = {}
    for word in (tail or name):gmatch('%S+') do words[#words + 1] = word end
    if prefix and prefix ~= '' and tail then
        local tier = tail == 'Ichi' and '1' or tail == 'Ni' and '2' or tail == 'San' and '3' or nil
        if tier and #prefix >= 3 then
            local short = prefix:sub(1, 5):upper() .. tier
            return short, short:sub(1, 3)
        end
    end
    if #words == 0 then return '?', '?' end

    if #words > 1 then
        if #words[1] <= 6 then
            local short = words[1]:upper()
            return short, short:sub(1, 3)
        end
        local initials = ''
        for _, word in ipairs(words) do initials = initials .. word:sub(1, 1) end
        initials = initials:upper():sub(1, 6)
        return initials, initials:sub(1, 3)
    end

    local word = words[1]
    if #word <= 6 then
        local short = word:upper()
        return short, short:sub(1, 3)
    end
    local short = word:sub(1, 5):upper()
    return short, short:sub(1, 3)
end

local function hud_copy_array(source)
    local out = {}
    if type(source) == 'table' then
        for _, value in ipairs(source) do out[#out + 1] = value end
    end
    return out
end

local function hud_copy_map(source)
    local out = {}
    if type(source) == 'table' then
        for key, value in pairs(source) do
            if type(key) == 'string' and type(value) == 'string' then out[key] = value end
        end
    end
    return out
end

local function hud_clamp(value, low, high, fallback)
    value = tonumber(value)
    if not value then return fallback end
    if value < low then return low end
    if value > high then return high end
    return value
end

local function hud_copy_positions(source)
    local out = {}
    for key, fallback in pairs(HUD_DEFAULT_POSITIONS) do
        local value = type(source) == 'table' and source[key] or nil
        out[key] = {
            x = type(value) == 'table' and tonumber(value.x) or fallback.x,
            y = type(value) == 'table' and tonumber(value.y) or fallback.y,
        }
    end
    return out
end

local function hud_default_type(key)
    local info = HUD_TYPE_INFO[key]
    return {
        layout = 'grid',
        columns = key == 'spells' and 7 or 6,
        size = 48,
        labels = 'always',
        font = 10,
        tabs = true,
        group = info.default_group,
        groups = {},
        assign = {},
    }
end

-- The two information hubs (Battle Info, Party Info) keep their own position and switches in the
-- same per-character file as the action HUD, so a character carries all of its overlay settings.
-- Their numbers are sanitized separately: a layout change here must not reset an action HUD.
local function hub_defaults()
    return {
        battle = {
            x = 470, y = 96, opacity = 0.94, auto_start = true, native_fps = false, advanced = true,
        },
        party = {
            x = 24, y = 96, opacity = 0.97, replace = false, buffs = true, names = true, tab = 'party',
        },
    }
end

local function hub_sanitize(raw)
    local defaults = hub_defaults()
    raw = type(raw) == 'table' and raw or {}
    local b = type(raw.battle) == 'table' and raw.battle or {}
    local battle = defaults.battle
    battle.x = math.floor(hud_clamp(b.x, -4000, 8000, battle.x))
    battle.y = math.floor(hud_clamp(b.y, -4000, 8000, battle.y))
    battle.opacity = hud_clamp(b.opacity, 0.45, 1, battle.opacity)
    if type(b.auto_start) == 'boolean' then battle.auto_start = b.auto_start end
    if type(b.native_fps) == 'boolean' then battle.native_fps = b.native_fps end
    if type(b.advanced) == 'boolean' then battle.advanced = b.advanced end
    local p = type(raw.party) == 'table' and raw.party or {}
    local party = defaults.party
    party.x = math.floor(hud_clamp(p.x, -4000, 8000, party.x))
    party.y = math.floor(hud_clamp(p.y, -4000, 8000, party.y))
    party.opacity = hud_clamp(p.opacity, 0.45, 1, party.opacity)
    if type(p.replace) == 'boolean' then party.replace = p.replace end
    if type(p.buffs) == 'boolean' then party.buffs = p.buffs end
    if type(p.names) == 'boolean' then party.names = p.names end
    if p.tab == 'alliance' then party.tab = 'alliance' else party.tab = 'party' end
    return battle, party
end

local function hud_defaults()
    local types = {}
    for _, key in ipairs(HUD_TYPES) do types[key] = hud_default_type(key) end
    local battle, party = hub_sanitize(nil)
    return {
        show_abilities = false,
        show_spells = false,
        show_trusts = false,
        show_weapon_skills = false,
        show_battle_info = false,
        show_party_info = false,
        edit = false,
        opacity = 0.9,
        menu_hide = true,
        sc_target = 0,
        types = types,
        positions = hud_copy_positions(nil),
        battle = battle,
        party = party,
    }
end

local function hud_sanitize_groups(source)
    local out, seen = {}, {}
    if type(source) == 'table' then
        for _, raw in ipairs(source) do
            local name = tostring(raw or ''):gsub('^%s+', ''):gsub('%s+$', '')
            if name ~= '' and name ~= 'Unsorted' and #name <= 24 and not seen[name] and #out < 12 then
                seen[name] = true
                out[#out + 1] = name
            end
        end
    end
    return out
end

local function hud_sanitize_type(key, raw)
    local spec = hud_default_type(key)
    if type(raw) ~= 'table' then return spec end
    if raw.layout == 'grid' or raw.layout == 'list' or raw.layout == 'bar' then spec.layout = raw.layout end
    spec.columns = math.floor(hud_clamp(raw.columns, 3, 12, spec.columns))
    spec.size = math.floor(hud_clamp(raw.size, 32, 72, spec.size))
    spec.font = math.floor(hud_clamp(raw.font, 7, 12, spec.font))
    if raw.labels == 'always' or raw.labels == 'hover' or raw.labels == 'off' then spec.labels = raw.labels end
    if type(raw.tabs) == 'boolean' then spec.tabs = raw.tabs end
    local valid_group = false
    for _, name in ipairs(HUD_TYPE_INFO[key].groups) do
        if raw.group == name then valid_group = true break end
    end
    if valid_group then spec.group = raw.group end
    spec.groups = hud_sanitize_groups(raw.groups)
    local allowed = {}
    for _, name in ipairs(spec.groups) do allowed[name] = true end
    if type(raw.assign) == 'table' then
        local count = 0
        for item_key, group in pairs(raw.assign) do
            if type(item_key) == 'string' and type(group) == 'string' and allowed[group] and count < 500 then
                spec.assign[item_key] = group
                count = count + 1
            end
        end
    end
    return spec
end

local function hud_place_new_positions(state, explicit)
    -- A version-1 file has only the ability and spell positions. Put trusts and weapon skills in
    -- the free quadrants instead of dropping them on top of an existing window; the user can still
    -- drag them anywhere afterwards. Missing positions are the only ones this touches.
    local placed = { abilities = true, spells = true }
    for _, key in ipairs(HUD_TYPES) do
        if explicit[key] then placed[key] = true end
    end
    local function taken(x, y)
        for key in pairs(placed) do
            local p = state.positions[key]
            if p and math.abs(p.x - x) < 320 and math.abs(p.y - y) < 300 then return true end
        end
        return false
    end
    local slots = {
        { x = 900, y = 80 }, { x = 900, y = 400 },
        { x = 48, y = 80 }, { x = 48, y = 400 },
    }
    for _, key in ipairs({ 'trusts', 'weapon_skills' }) do
        if not explicit[key] then
            for _, slot in ipairs(slots) do
                if not taken(slot.x, slot.y) then
                    state.positions[key] = { x = slot.x, y = slot.y }
                    placed[key] = true
                    break
                end
            end
        end
    end
end

local function hud_sanitize(raw)
    local state = hud_defaults()
    if type(raw) ~= 'table' then return state end
    if type(raw.show_abilities) == 'boolean' then state.show_abilities = raw.show_abilities end
    if type(raw.show_spells) == 'boolean' then state.show_spells = raw.show_spells end
    if type(raw.show_trusts) == 'boolean' then state.show_trusts = raw.show_trusts end
    if type(raw.show_weapon_skills) == 'boolean' then state.show_weapon_skills = raw.show_weapon_skills end
    if type(raw.show_battle_info) == 'boolean' then state.show_battle_info = raw.show_battle_info end
    if type(raw.show_party_info) == 'boolean' then state.show_party_info = raw.show_party_info end
    state.battle, state.party = hub_sanitize(raw)
    state.opacity = hud_clamp(raw.opacity, 0.45, 1, state.opacity)
    if type(raw.menu_hide) == 'boolean' then state.menu_hide = raw.menu_hide end
    state.sc_target = math.floor(hud_clamp(raw.sc_target, 0, #HUD_SC_NAMES, 0))
    state.positions = hud_copy_positions(raw.positions)
    local raw_positions = type(raw.positions) == 'table' and raw.positions or {}
    local explicit_positions = {}
    for _, key in ipairs(HUD_TYPES) do
        explicit_positions[key] = type(raw_positions[key]) == 'table'
    end
    hud_place_new_positions(state, explicit_positions)
    -- Version 1 only had the two ability/spell switches. Carry its layout into both old windows
    -- and give trusts/weapon skills the new defaults, so the first launch after the update does not
    -- reset anyone's carefully placed ability window.
    local old = nil
    if type(raw.layout) == 'string' or raw.columns ~= nil or raw.size ~= nil then
        old = {
            layout = raw.layout, columns = raw.columns, size = raw.size,
            labels = raw.labels, group = nil, groups = nil, assign = nil,
        }
    end
    local raw_types = type(raw.types) == 'table' and raw.types or nil
    for _, key in ipairs(HUD_TYPES) do
        local source = raw_types and raw_types[key] or nil
        if not source and old and (key == 'abilities' or key == 'spells') then source = old end
        state.types[key] = hud_sanitize_type(key, source)
    end
    -- A HUD saved mid-edit must not come back locked in drag mode.
    state.edit = false
    return state
end

local function hud_character()
    local index = game.player_index()
    if index and index >= 0 then
        local name = game.entity(index, 'Name')
        if type(name) == 'string' and name ~= '' then
            local id = game.entity(index, 'ServerId')
            return tostring(name), tonumber(id) or 0
        end
    end
    return nil, 0
end

local function hud_file_stem(name)
    local stem = tostring(name or 'default'):gsub('[^%w_%-]', '_')
    if stem == '' then stem = 'default' end
    return stem
end

local function hud_load_file(path)
    local file = io.open(path, 'rb')
    if not file then return nil end
    local source = file:read('*a')
    file:close()
    if not source or source == '' then return nil end
    local ok, decoded = pcall(json.decode, source)
    if not ok or type(decoded) ~= 'table' then return nil end
    return decoded
end

local function hud_save(state, path)
    if not path then return end
    if xi.fs and xi.fs.mkdir then xi.fs.mkdir(xi.paths.data .. 'hud') end
    local types = {}
    for _, key in ipairs(HUD_TYPES) do
        local spec = state.types[key]
        types[key] = {
            layout = spec.layout, columns = spec.columns, size = spec.size,
            labels = spec.labels, font = spec.font, tabs = spec.tabs, group = spec.group,
            groups = hud_copy_array(spec.groups), assign = hud_copy_map(spec.assign),
        }
    end
    local file = io.open(path, 'wb')
    if not file then return end
    file:write(json.encode({
        version = HUD_FILE_VERSION,
        show_abilities = state.show_abilities,
        show_spells = state.show_spells,
        show_trusts = state.show_trusts,
        show_weapon_skills = state.show_weapon_skills,
        show_battle_info = state.show_battle_info,
        show_party_info = state.show_party_info,
        opacity = state.opacity,
        menu_hide = state.menu_hide,
        sc_target = state.sc_target,
        types = types,
        positions = state.positions,
        battle = {
            x = state.battle.x, y = state.battle.y, opacity = state.battle.opacity,
            auto_start = state.battle.auto_start, native_fps = state.battle.native_fps,
            advanced = state.battle.advanced,
        },
        party = {
            x = state.party.x, y = state.party.y, opacity = state.party.opacity,
            replace = state.party.replace, buffs = state.party.buffs,
            names = state.party.names, tab = state.party.tab,
        },
    }))
    file:close()
end

local hud_icon_textures = {}

local function hud_icon_texture(id)
    id = tonumber(id) or 0
    if id <= 0 then return nil end
    local cached = hud_icon_textures[id]
    if cached ~= nil then return cached or nil end
    local ok, rgba, width, height = pcall(res.menu_icon_rgba, id)
    if ok and type(rgba) == 'string' and width and height and #rgba == width * height * 4 then
        local texture = xi.ui.texture_memory(rgba, width, height)
        if texture and texture ~= 0 then
            hud_icon_textures[id] = texture
            return texture
        end
    end
    hud_icon_textures[id] = false
    return nil
end

local hud_face_textures = {}

local function hud_face_texture(id)
    id = tonumber(id) or 0
    if id <= 0 then return nil end
    local cached = hud_face_textures[id]
    if cached ~= nil then return cached or nil end
    local ok, rgba, width, height = pcall(res.trust_face_rgba, id)
    if ok and type(rgba) == 'string' and width and height and #rgba == width * height * 4 then
        local texture = xi.ui.texture_memory(rgba, width, height)
        if texture and texture ~= 0 then
            hud_face_textures[id] = texture
            return texture
        end
    end
    hud_face_textures[id] = false
    return nil
end

local hud_item_textures = {}
local hud_sc_textures = {}

local function hud_item_texture(id)
    id = tonumber(id) or 0
    if id <= 0 then return nil end
    local cached = hud_item_textures[id]
    if cached ~= nil then return cached or nil end
    local ok, rgba, width, height = pcall(res.item_icon_rgba, id)
    if ok and type(rgba) == 'string' and width and height and #rgba == width * height * 4 then
        local texture = xi.ui.texture_memory(rgba, width, height)
        if texture and texture ~= 0 then
            hud_item_textures[id] = texture
            return texture
        end
    end
    hud_item_textures[id] = false
    return nil
end

local function hud_sc_texture(id)
    id = tonumber(id) or 0
    if id < 1 or id > #HUD_SC_NAMES then return nil end
    local cached = hud_sc_textures[id]
    if cached ~= nil then return cached or nil end
    local ok, rgba, width, height = pcall(res.sc_icon_rgba, id)
    if ok and type(rgba) == 'string' and width and height and #rgba == width * height * 4 then
        local texture = xi.ui.texture_memory(rgba, width, height)
        if texture and texture ~= 0 then
            hud_sc_textures[id] = texture
            return texture
        end
    end
    hud_sc_textures[id] = false
    return nil
end

local function hud_title_texture(title)
    if hud.main_item and hud.main_item > 0 and tonumber(hud.main_skill or 0) == (HUD_WS_TITLE_SKILL[title] or -1) then
        return hud_item_texture(hud.main_item)
    end
    local id = HUD_WS_TITLE_ITEM[title]
    if id then
        local texture = hud_item_texture(id)
        if texture then return texture end
    end
    if hud.main_item and hud.main_item > 0 then return hud_item_texture(hud.main_item) end
    return nil
end

local function hud_target()
    local index = game.target('Targets[0].Index')
    if index and index > 0 and game.target('Targets[0].IsActive') ~= 0 then return '<t>' end
    return '<me>'
end

-- A called alter ego is a client spawnable with Flags3's TrustFlag set.  The HUD keys its
-- buttons by spell name, so compare with case and punctuation stripped: the client spells
-- some names differently from the server ("D. Shantotto" / "D Shantotto", "Excenmille [S]" /
-- "Excenmille S").
local function hud_trust_key(name)
    return tostring(name or ''):lower():gsub('[^%w]', '')
end

local function hud_trust_entity_live(i)
    -- The entity is already known to carry TrustFlag; only the two stale-slot bits
    -- matter here.  Flags0 can legitimately be zero on a stationary spawn and is not a
    -- useful liveness test for a Trust.
    local f1 = game.entity(i, 'Render.Flags1') or 0
    local f3 = game.entity(i, 'Render.Flags3') or 0
    return math.floor(f1 / 0x1000) % 2 == 0 and math.floor(f3 / 0x8000) % 2 == 0
end

local function hud_refresh_trusts(now)
    now = now or os.clock()
    if now < (hud.next_trust_scan or 0) then return end
    hud.next_trust_scan = now + 0.4
    local pi = game.player_index() or -1
    local my_targid = pi >= 0 and (game.entity(pi, 'ServerId') or 0) % 0x1000 or 0
    local active = {}
    for i = 0, (game.entity_count() or 0) - 1 do
        local f3 = game.entity(i, 'Render.Flags3') or 0
        if f3 % 2 == 1 and hud_trust_entity_live(i) then
            -- 0x067 records the master's targid on the owner's client, so another
            -- player's Trust with the same name does not light up this player's tile.
            local owner = game.entity(i, 'TrustOwnerTargetIndex') or 0
            local name = game.entity(i, 'Name')
            if my_targid > 0 and owner == my_targid and name and name ~= '' then
                active[hud_trust_key(name)] = true
            end
        end
    end
    hud.active_trusts = active
end

local function hud_trust_active(item)
    local active = hud.active_trusts
    return type(active) == 'table' and active[hud_trust_key(item.name)] == true
end

local function hud_cooling(hud, item)
    return hud.cool and hud.cool[item.key] or nil
end

local function hud_click(hud, item)
    if item.kind == 'trust' then
        -- A click is the one moment the answer has to be current: rescan instead of
        -- trusting the 0.4 s cache, so a Trust that just landed is released rather than
        -- called a second time.
        hud.next_trust_scan = 0
        hud_refresh_trusts()
    end
    if item.kind == 'trust' and hud_trust_active(item) then
        -- The client's own Remove/Release menu is an entity action no chat command exposes;
        -- the server's !trust release finds the alter ego by its spell id and despawns it.
        local ok, err = pcall(xi.chat.run,
            string.format('/say !trust release %d', tonumber(item.id) or 0), 1)
        if not ok then
            xi.chat.write('HUD: ' .. tostring(err), 1)
            return
        end
        if type(hud.active_trusts) == 'table' then
            hud.active_trusts[hud_trust_key(item.name)] = nil
        end
        return
    end
    local target = item.kind == 'trust' and '<me>' or hud_target()
    local line
    if item.kind == 'weapon_skill' then
        line = string.format('/ws "%s" %s', item.name, target)
    elseif item.kind == 'spell' or item.kind == 'trust' then
        line = string.format('/ma "%s" %s', item.name, target)
    else
        line = string.format('/ja "%s" %s', item.name, target)
    end
    local ok, err = pcall(xi.chat.run, line, 1)
    if not ok then
        xi.chat.write('HUD: ' .. tostring(err), 1)
        return
    end
    if item.kind == 'weapon_skill' then return end
    local total = tonumber(item.recast) or 0
    -- Most spells and job abilities keep the client's recast table authoritative; the click only
    -- seeds the full bar until the first polling frame sees the real timer.
    hud.cool[item.key] = {
        start = os.clock(),
        total = total > 0 and total or 0,
        remaining = total > 0 and total or 1,
        pending = true,
        progress = 0,
    }
end

local function hud_update_cool(hud)
    local now = os.clock()
    local ability_recasts = nil
    for key, cool in pairs(hud.cool) do
        local item = hud.by_key[key]
        local pending_for = item and ((item.kind == 'spell' or item.kind == 'trust') and 8 or 3) or 3
        if not item then
            hud.cool[key] = nil
        else
            local remaining = nil
            if item.kind == 'spell' or item.kind == 'trust' then
                local ticks = game.spell_recast(item.id)
                remaining = ticks and ticks > 0 and ticks / 60 or 0
            else
                if not ability_recasts then
                    ability_recasts = {}
                    for slot = 0, 30 do
                        local ticks, recast_id = game.ability_recast(slot)
                        if ticks and recast_id and ticks > 0 then
                            local seconds = ticks / 60
                            if seconds > (ability_recasts[recast_id] or 0) then
                                ability_recasts[recast_id] = seconds
                            end
                        end
                    end
                end
                remaining = item.recastId and ability_recasts[item.recastId] or 0
            end
            if remaining and remaining > 0.02 then
                cool.remaining = remaining
                if cool.pending then
                    -- First live sample: the client's actual recast (after haste/gear) is the bar,
                    -- not the record's base value used while the command was still in flight.
                    cool.total = math.max(remaining, 0.05)
                    cool.pending = false
                elseif cool.total < remaining then
                    cool.total = remaining
                end
                cool.progress = cool.total > 0 and 1 - remaining / cool.total or 0
            elseif cool.pending and now - cool.start < pending_for then
                cool.remaining = cool.total > 0 and cool.total or 1
                cool.progress = 0
            else
                hud.cool[key] = nil
            end
        end
    end
end

hud = {
    character = nil,
    path = nil,
    state = hud_defaults(),
    abilities = {},
    spells = {},
    trusts = {},
    weapon_skills = {},
    by_key = {},
    cool = {},
    active_trusts = {},
    next_trust_scan = 0,
    page = {},
    textures = hud_icon_textures,
    faces = hud_face_textures,
    item_textures = hud_item_textures,
    sc_textures = hud_sc_textures,
    tp = 0,
    last_tp = nil,
    sc_start = nil,
    sc_step = nil,
    main_item = 0,
    main_skill = 0,
    job_signature = nil,
    main_job = 0,
    sub_job = 0,
    imgui = nil,
    warned = false,
    reposition = false,
}
hud.save = hud_save

function hud.ensure()
    local name = hud_character()
    local key = hud_file_stem(name)
    if hud.character == key then return end
    local previous = hud.character
    hud.character = key
    hud.path = xi.paths.data .. 'hud/' .. key .. '.json'
    local stored = hud_load_file(hud.path)
    if stored then
        hud.state = hud_sanitize(stored)
    elseif previous == 'default' then
        -- A switch flipped at the character-select screen belongs to the character that logs in
        -- next; carry the session state into its per-character file instead of dropping it.
        hud_save(hud.state, hud.path)
    else
        hud.state = hud_defaults()
    end
    hud.abilities, hud.spells, hud.trusts, hud.weapon_skills = {}, {}, {}, {}
    hud.by_key, hud.cool = {}, {}
    hud.active_trusts = {}
    hud.next_trust_scan = 0
    hud.page = {}
    hud.job_signature = nil
    hud.main_job, hud.sub_job = 0, 0
    hud.last_tp = nil
    hud.sc_start = nil
    hud.sc_step = nil
    hud.tp = 0
    hud.main_item = 0
    hud.main_skill = 0
end

local function hud_sort_name(list)
    table.sort(list, function(a, b)
        local an, bn = tostring(a.name):lower(), tostring(b.name):lower()
        if an == bn then return a.id < b.id end
        return an < bn
    end)
end

local function hud_ws_skill(id)
    for _, range in ipairs(HUD_WS_RANGES) do
        if id >= range[1] and id <= range[2] then return range[3] end
    end
    return HUD_WS_SKILL[id] or 'Other'
end

local function hud_sch_art(name)
    name = tostring(name or '')
    if HUD_SCH_LIGHT[name] then return 'Light Arts' end
    if HUD_SCH_DARK[name] then return 'Dark Arts' end
    if name:find('Addendum', 1, true) then
        local lower = name:lower()
        if lower:find('white', 1, true) then return 'Light Arts' end
        if lower:find('black', 1, true) then return 'Dark Arts' end
    end
    return 'Other'
end

function hud.rebuild(force)
    local main = game.party_member(0, 'MainJob') or 0
    local main_level = game.party_member(0, 'MainJobLevel') or 0
    local sub = game.party_member(0, 'SubJob') or 0
    local sub_level = game.party_member(0, 'SubJobLevel') or 0
    local signature = string.format('%d:%d:%d:%d', main, main_level, sub, sub_level)
    if not force and hud.job_signature == signature then return end
    hud.job_signature = signature
    hud.main_job, hud.sub_job = main, sub
    hud.abilities, hud.spells, hud.trusts, hud.weapon_skills = {}, {}, {}, {}
    hud.by_key, hud.cool = {}, {}

    local abilities = job_abilities().abilities or {}
    for _, ability in ipairs(abilities) do
        local kind = tostring(ability.type or '')
        local skip = kind:find('BloodPact') or kind:find('PetCommand')
        local aname = type(ability.name) == 'table' and (ability.name.en or ability.name[2] or ability.name[1]) or ability.name
        if not skip and type(aname) == 'string' and aname ~= '' and aname ~= '.' then
            local item = {
                key = 'a' .. tostring(ability.id), kind = 'ability', id = ability.id,
                name = aname, icon = ability.icon, recast = 0,
                recastId = ability.recastId, level = 0,
                job = HUD_ABILITY_JOB[hud_ability_key(aname)], ability_type = kind,
            }
            item.short, item.tiny = hud_short_name(item.name)
            hud.abilities[#hud.abilities + 1] = item
            hud.by_key[item.key] = item
        end
    end

    local spells = job_spells().spells or {}
    for _, spell in ipairs(spells) do
        local item = {
            key = (spell.magic == 8 and 't' or 's') .. tostring(spell.id),
            kind = spell.magic == 8 and 'trust' or 'spell', id = spell.id,
            name = spell.name, icon = spell.icon, recast = spell.recast or 0,
            level = spell.level or 0,
            magic = spell.magic, skill_id = spell.skill_id, skill = spell.skill,
            element = spell.element, targets = spell.targets,
            trust_job = spell.magic == 8 and HUD_TRUST_JOBS[spell.name] or nil,
        }
        item.short, item.tiny = hud_short_name(item.name)
        local list = spell.magic == 8 and hud.trusts or hud.spells
        list[#list + 1] = item
        hud.by_key[item.key] = item
    end

    -- Weapon skills are in the client's 0x0AC command list as action ids 1..255. The list is
    -- already narrowed to the character's skill levels, so it is the right HUD source.
    local ok, ids = pcall(game.ability_commands)
    if ok and type(ids) == 'table' then
        local seen = {}
        for _, raw in ipairs(ids) do
            local id = tonumber(raw) or 0
            if id >= 1 and id < 0x200 and not seen[id] then
                local ability = res.ability(id)
                if ability and ability.type_name == 'WeaponSkill' then
                    local name = ability.name
                    if type(name) == 'table' then name = name.en or name[2] or name[1] end
                    if type(name) == 'string' and name ~= '' and name ~= '.' then
                        seen[id] = true
                        local item = {
                            key = 'w' .. tostring(id), kind = 'weapon_skill', id = id,
                            name = name, icon = tonumber(ability.icon_id) or 0,
                            recast = 0, level = 0, ws_skill = hud_ws_skill(id),
                        }
                        item.short, item.tiny = hud_short_name(item.name)
                        hud.weapon_skills[#hud.weapon_skills + 1] = item
                        hud.by_key[item.key] = item
                    end
                end
            end
        end
    end

    hud_sort_name(hud.abilities)
    hud_sort_name(hud.spells)
    hud_sort_name(hud.trusts)
    hud_sort_name(hud.weapon_skills)
end

local function hud_contains_any(text, list)
    for _, needle in ipairs(list) do
        if text:find(needle, 1, true) then return true end
    end
    return false
end

local HUD_BLUE_BUFF = {
    'cocoon', 'metallic body', 'mighty guard', 'diamondhide', 'refueling', 'battery charge',
    'warm-up', 'saline coat', 'plenilune embrace', 'restoral', 'magic fruit', 'healing breeze',
    'wild carrot', 'regeneration', 'reactor cool', 'barrier tusk',
}
local HUD_BLUE_DEBUFF = {
    'filamented hold', 'frightful roar', 'geist wall', 'sheep song', 'soporific', 'sound blast',
    'acrid stream', 'blank gaze', 'cold wave', 'ice break', 'stinking gas', 'terror touch',
    'mp drainkiss', 'blood drain', 'digest', 'sandspin', 'sub-zero smash', 'mind blast',
    'death ray', 'petrifaction', 'regurgitation', 'temporal shift', 'rending deluge', 'entomb',
    'nuclear waste', 'morbid mold', 'memento mori', 'tenebrous mist', 'cimicine discharge',
    'fetid eddy', 'corrosive ooze', 'silent storm', 'dancing chains', 'frightful roar',
    'sweet breath', 'chaotic eye', 'auroral drape', 'venom shell', 'stinking gas',
}

local HUD_GEO_DEBUFF = {
    'frailty', 'malaise', 'slow', 'paralyze', 'silence', 'blind', 'poison', 'gravity',
    'attack down', 'defense down', 'acumen', 'precision', 'torpor', 'wilt', 'vex', 'languor',
    'fury', 'attrition', 'slip', 'dread', 'demoralize',
}

local function hud_spell_kind(item)
    local n = tostring(item.name or ''):lower()
    local magic = item.magic
    if magic == 8 then return 'Trust' end
    if magic == 3 then return 'Avatar' end
    if magic == 1 then
        if item.skill_id == 33 then return 'Healing' end
        if item.skill_id == 34 then return 'Buff' end
        if item.skill_id == 35 then return 'Debuff' end
        if item.skill_id == 32 then
            if n:find('holy', 1, true) or n:find('banish', 1, true) then return 'Nuke' end
            return 'Debuff'
        end
        return 'Buff'
    end
    if magic == 2 then
        if item.skill_id == 35 then return 'Debuff' end
        if item.skill_id == 36 then return 'Nuke' end
        if item.skill_id == 37 then
            if n:find('absorb', 1, true) or n:find('sleep', 1, true) or n:find('dispel', 1, true)
                or n:find('break', 1, true) or n:find('stun', 1, true) then return 'Debuff' end
            return 'Nuke'
        end
        return 'Nuke'
    end
    if magic == 4 then
        if n:find('utsusemi', 1, true) or n:find('tonko', 1, true) or n:find('monomi', 1, true)
            or n:find('migawari', 1, true) then return 'Buff' end
        if n:find('hojo', 1, true) or n:find('kurayami', 1, true) or n:find('dokumori', 1, true)
            or n:find('jubaku', 1, true) or n:find('aisha', 1, true) or n:find('yain', 1, true)
            or n:find('yurin', 1, true) or n:find('gekka', 1, true) or n:find('myoshu', 1, true)
            or n:find('kakka', 1, true) then return 'Debuff' end
        return 'Nuke'
    end
    if magic == 5 then
        if n:find('requiem', 1, true) or n:find('threnody', 1, true) or n:find('lullaby', 1, true)
            or n:find('elegy', 1, true) or n:find('finale', 1, true) then return 'Debuff' end
        return 'Buff'
    end
    if magic == 6 then
        if hud_contains_any(n, HUD_BLUE_BUFF) then return 'Buff' end
        if hud_contains_any(n, HUD_BLUE_DEBUFF) then return 'Debuff' end
        return 'Nuke'
    end
    if magic == 7 then
        if hud_contains_any(n, HUD_GEO_DEBUFF) then return 'Debuff' end
        if n:sub(1, 4) == 'indi' then return 'Buff' end
        if n:sub(1, 3) == 'geo' then return 'Nuke' end
        return 'Buff'
    end
    return 'Other'
end

local function hud_group_for(key, item)
    local spec = hud.state.types[key]
    local group = spec.group
    if key == 'abilities' then
        if group == 'type' then return item.ability_type or 'Other' end
        local job = item.job
        if not job and hud_sch_art(item.name) ~= 'Other' then job = 20 end
        local role = 'Other'
        if job == hud.main_job and job ~= 0 then role = 'Main'
        elseif job == hud.sub_job and job ~= 0 then role = 'Sub' end
        if job == 20 then
            return role .. ' — SCH · ' .. hud_sch_art(item.name)
        end
        local abbr = job and HUD_JOB_ABBR[job] or nil
        if abbr then return role .. ' — ' .. abbr end
        return 'Other'
    end
    if key == 'spells' then
        if group == 'type' then return hud_spell_kind(item) end
        if group == 'skill' then return HUD_SPELL_MAGIC[item.magic] or 'Other' end
        if group == 'element' then return HUD_ELEMENTS[(item.element or 0) + 1] or 'Other' end
        return 'Other'
    end
    if key == 'trusts' then return item.trust_job or 'Other' end
    if key == 'weapon_skills' then return item.ws_skill or 'Other' end
    return 'Other'
end

local HUD_GROUP_ORDER = {
    spells_type = { 'Healing', 'Buff', 'Debuff', 'Nuke', 'Avatar', 'Other' },
    spells_skill = { 'White Magic', 'Black Magic', 'Summoning', 'Ninjutsu', 'Bard Song', 'Blue Magic', 'Geomancy', 'Other' },
    elements = { 'Light', 'Dark', 'Fire', 'Ice', 'Wind', 'Earth', 'Thunder', 'Water', 'None' },
    ws_skill = { 'Hand-to-Hand', 'Dagger', 'Sword', 'Great Sword', 'Axe', 'Great Axe', 'Scythe',
        'Polearm', 'Katana', 'Great Katana', 'Club', 'Staff', 'Archery', 'Marksmanship', 'Other' },
}

local function hud_order_groups(key, spec, titles)
    local preferred = nil
    if key == 'spells' and spec.group == 'type' then preferred = HUD_GROUP_ORDER.spells_type
    elseif key == 'spells' and spec.group == 'skill' then preferred = HUD_GROUP_ORDER.spells_skill
    elseif key == 'spells' and spec.group == 'element' then preferred = HUD_GROUP_ORDER.elements
    elseif key == 'weapon_skills' and spec.group == 'skill' then preferred = HUD_GROUP_ORDER.ws_skill
    end
    local out, seen = {}, {}
    if preferred then
        for _, title in ipairs(preferred) do
            if titles[title] then out[#out + 1] = title; seen[title] = true end
        end
    end
    local rest = {}
    for title in pairs(titles) do
        if not seen[title] then rest[#rest + 1] = title end
    end
    if key == 'abilities' and spec.group == 'job' then
        local function rank(title)
            if title:sub(1, 4) == 'Main' then return 1 end
            if title:sub(1, 3) == 'Sub' then return 2 end
            return 3
        end
        table.sort(rest, function(a, b)
            local ar, br = rank(a), rank(b)
            if ar ~= br then return ar < br end
            return a < b
        end)
    else
        table.sort(rest)
    end
    for _, title in ipairs(rest) do out[#out + 1] = title end
    return out
end

local function hud_grouped(key)
    local items = hud[key]
    local spec = hud.state.types[key]
    if spec.group == 'none' then return { { title = nil, items = items } } end
    local buckets, order = {}, {}
    if spec.group == 'custom' then
        for _, name in ipairs(spec.groups) do buckets[name] = {} end
        local unsorted = {}
        for _, item in ipairs(items) do
            local name = spec.assign[item.key]
            if name and buckets[name] then
                buckets[name][#buckets[name] + 1] = item
            else
                unsorted[#unsorted + 1] = item
            end
        end
        for _, name in ipairs(spec.groups) do
            if #buckets[name] > 0 then order[#order + 1] = { title = name, items = buckets[name] } end
        end
        if #unsorted > 0 then order[#order + 1] = { title = 'Unsorted', items = unsorted } end
        if #order == 0 then order[1] = { title = nil, items = items } end
        return order
    end
    for _, item in ipairs(items) do
        local title = hud_group_for(key, item)
        if not buckets[title] then buckets[title] = {}; order[#order + 1] = title end
        buckets[title][#buckets[title] + 1] = item
    end
    local groups = {}
    local titles = {}
    for _, title in ipairs(order) do titles[title] = true end
    for _, title in ipairs(hud_order_groups(key, spec, titles)) do
        groups[#groups + 1] = { title = title, items = buckets[title] }
    end
    if #groups == 0 then groups[1] = { title = nil, items = items } end
    return groups
end

local function hud_copy_type(spec)
    return {
        layout = spec.layout, columns = spec.columns, size = spec.size,
        labels = spec.labels, font = spec.font, tabs = spec.tabs, group = spec.group,
        groups = hud_copy_array(spec.groups), assign = hud_copy_map(spec.assign),
    }
end

local function hud_snapshot_items(list)
    local out = {}
    for _, item in ipairs(list) do
        out[#out + 1] = { key = item.key, name = item.name, short = item.short }
    end
    return out
end

function hud.snapshot()
    hud.ensure()
    if hud.job_signature == nil and (game.player_index() or -1) >= 0 then hud.rebuild() end
    local types = {}
    for _, key in ipairs(HUD_TYPES) do types[key] = hud_copy_type(hud.state.types[key]) end
    return {
        show_abilities = hud.state.show_abilities,
        show_spells = hud.state.show_spells,
        show_trusts = hud.state.show_trusts,
        show_weapon_skills = hud.state.show_weapon_skills,
        show_battle_info = hud.state.show_battle_info,
        show_party_info = hud.state.show_party_info,
        edit = hud.state.edit,
        opacity = hud.state.opacity,
        menu_hide = hud.state.menu_hide,
        battle = {
            x = hud.state.battle.x, y = hud.state.battle.y, opacity = hud.state.battle.opacity,
            auto_start = hud.state.battle.auto_start, native_fps = hud.state.battle.native_fps,
            advanced = hud.state.battle.advanced,
        },
        party = {
            x = hud.state.party.x, y = hud.state.party.y, opacity = hud.state.party.opacity,
            replace = hud.state.party.replace, buffs = hud.state.party.buffs,
            names = hud.state.party.names, tab = hud.state.party.tab,
        },
        types = types,
        abilities = #hud.abilities,
        spells = #hud.spells,
        trusts = #hud.trusts,
        weapon_skills = #hud.weapon_skills,
        items = {
            abilities = hud_snapshot_items(hud.abilities),
            spells = hud_snapshot_items(hud.spells),
            trusts = hud_snapshot_items(hud.trusts),
            weapon_skills = hud_snapshot_items(hud.weapon_skills),
        },
        character = hud.character,
        main_item = hud.main_item,
        tp = hud.tp,
        sc_target = hud.state.sc_target,
    }
end

local function hud_apply_type(spec, key, args)
    if args.layout == 'grid' or args.layout == 'list' or args.layout == 'bar' then spec.layout = args.layout end
    if args.columns ~= nil then spec.columns = math.floor(hud_clamp(args.columns, 3, 12, spec.columns)) end
    if args.size ~= nil then spec.size = math.floor(hud_clamp(args.size, 32, 72, spec.size)) end
    if args.font ~= nil then spec.font = math.floor(hud_clamp(args.font, 7, 12, spec.font)) end
    if args.labels == 'always' or args.labels == 'hover' or args.labels == 'off' then spec.labels = args.labels end
    if type(args.tabs) == 'boolean' then spec.tabs = args.tabs end
    if type(args.group) == 'string' then
        for _, name in ipairs(HUD_TYPE_INFO[key].groups) do
            if args.group == name then spec.group = name break end
        end
    end
    if args.custom_groups ~= nil then
        spec.groups = hud_sanitize_groups(args.custom_groups)
        local allowed = {}
        for _, name in ipairs(spec.groups) do allowed[name] = true end
        for item_key, group in pairs(spec.assign) do
            if not allowed[group] then spec.assign[item_key] = nil end
        end
    end
    if type(args.assign_key) == 'string' then
        local group = type(args.assign_group) == 'string' and args.assign_group or ''
        local allowed = false
        if group ~= '' then
            for _, name in ipairs(spec.groups) do
                if name == group then allowed = true break end
            end
        end
        if allowed then spec.assign[args.assign_key] = group else spec.assign[args.assign_key] = nil end
    end
end

function hud.command(args)
    hud.ensure()
    local state = hud.state
    if type(args.show_abilities) == 'boolean' then state.show_abilities = args.show_abilities end
    if type(args.show_spells) == 'boolean' then state.show_spells = args.show_spells end
    if type(args.show_trusts) == 'boolean' then state.show_trusts = args.show_trusts end
    if type(args.show_weapon_skills) == 'boolean' then state.show_weapon_skills = args.show_weapon_skills end
    if type(args.show_battle_info) == 'boolean' then state.show_battle_info = args.show_battle_info end
    if type(args.show_party_info) == 'boolean' then state.show_party_info = args.show_party_info end
    if type(args.edit) == 'boolean' then state.edit = args.edit end
    if args.opacity ~= nil then state.opacity = hud_clamp(args.opacity, 0.45, 1, state.opacity) end
    if type(args.menu_hide) == 'boolean' then state.menu_hide = args.menu_hide end
    if args.reset_positions then
        state.positions = hud_copy_positions(nil)
        hud.reposition = true
    end

    local type_key = type(args.type) == 'string' and args.type or nil
    local has_type_fields = args.layout ~= nil or args.columns ~= nil or args.size ~= nil
        or args.labels ~= nil or args.font ~= nil or args.tabs ~= nil or args.group ~= nil
        or args.custom_groups ~= nil or args.assign_key ~= nil
    if type_key and HUD_TYPE_INFO[type_key] then
        hud_apply_type(state.types[type_key], type_key, args)
    elseif has_type_fields then
        -- Older launchers sent layout fields without a type. Apply them to every window so that
        -- build keeps working, while a new launcher always names the tab it is editing.
        for _, key in ipairs(HUD_TYPES) do hud_apply_type(state.types[key], key, args) end
    end

    if state.show_abilities or state.show_spells or state.show_trusts or state.show_weapon_skills then
        hud.rebuild(false)
    end
    hud_save(state, hud.path)
    return hud.snapshot()
end
local function hud_font_size(spec)
    -- The configured size is a ceiling: a 32 px tile gets a 7 px label even when the user asked
    -- for 12, otherwise the label would take more room than the icon.
    local configured = math.floor(hud_clamp(spec.font, 7, 12, 10))
    local cap = math.max(7, math.floor(spec.size * 0.25))
    return math.min(configured, cap)
end

local function hud_label_height(spec)
    if spec.labels ~= 'always' then return 0 end
    return hud_font_size(spec) + 4
end

local function hud_text_width(api, text)
    local width = api.CalcTextSize(text)
    return width or 0
end

local function hud_fit_label(api, item, max_width, font_size)
    local text = item.short or item.name or '?'
    if max_width <= 1 then return text:sub(1, 1) end
    api.PushFont(nil, font_size)
    if hud_text_width(api, text) <= max_width then
        api.PopFont()
        return text
    end
    text = item.tiny or text:sub(1, 3)
    while #text > 1 and hud_text_width(api, text) > max_width do
        text = text:sub(1, #text - 1)
    end
    api.PopFont()
    return text
end

local function hud_draw_group_header(api, key, title, font_size)
    if not title then return end
    local icon = key == 'weapon_skills' and hud_title_texture(title) or nil
    if icon then
        local draw = api.GetWindowDrawList()
        local x, y = api.GetCursorScreenPos()
        draw:AddImage(icon, { x, y + 1 }, { x + 14, y + 15 }, { 0, 0 }, { 1, 1 }, HUD_COLOR_WHITE)
        api.Dummy({ 14, 14 })
        api.SameLine(0, 5)
    end
    api.PushFont(nil, math.max(9, font_size))
    if api.TextColored then
        api.TextColored({ 0.35, 0.85, 0.95, 1 }, tostring(title):upper())
    else
        api.Text(tostring(title))
    end
    api.PopFont()
    api.Dummy({ 0, 1 })
end

local function hud_fade(color, alpha)
    local r = color % 256
    local g = math.floor(color / 256) % 256
    local b = math.floor(color / 65536) % 256
    return hud_color(r, g, b, math.floor(math.max(0, math.min(1, alpha)) * 255))
end

-- One cell. The cell is an invisible ImGui button; the artwork, label and cooldown are drawn on
-- the window's draw list so the clock sweep stays inside the button's rounded rectangle.
local function hud_draw_cell(api, spec, item, cell_width, cell_height, mode)
    local cooling = hud_cooling(hud, item)
    local trust_active = item.kind == 'trust' and hud_trust_active(item)
    local is_ws = item.kind == 'weapon_skill' or item.kind == 'ws'
    local props = is_ws and hud_sc_props(item.id) or nil
    local target = is_ws and (tonumber(hud.state.sc_target) or 0) or 0
    local match = is_ws and hud_sc_has(props, target)
    local sc_show = is_ws and (match and target or hud_sc_primary(props)) or 0
    local sc_level = sc_show > 0 and hud_sc_tier(sc_show) or 0
    local enabled = not is_ws or (tonumber(hud.tp) or 0) >= HUD_TP_COST
    local draw = api.GetWindowDrawList()
    local clicked = api.InvisibleButton('hud-' .. item.key, { cell_width, cell_height })
    local x, y = api.GetItemRectMin()
    local x1, y1 = api.GetItemRectMax()
    local w, h = x1 - x, y1 - y
    local hover_text = item.name
    if is_ws then
        local lines = { item.name }
        if not enabled then lines[#lines + 1] = 'Requires 1000 TP' end
        local stats = hud_ws_stats(item.id)
        if stats and stats.ftp and #stats.ftp > 0 then
            local tp = math.max(HUD_TP_COST, math.min(3000, tonumber(hud.tp) or HUD_TP_COST))
            local a, b, c = stats.ftp[1] or 1, stats.ftp[2] or stats.ftp[1] or 1, stats.ftp[3] or stats.ftp[2] or 1
            local ftp
            if tp <= 2000 then ftp = a + (b - a) * (tp - 1000) / 1000
            else ftp = b + (c - b) * (tp - 2000) / 1000 end
            lines[#lines + 1] = string.format('fTP %.2f at %d TP  ·  %d hit%s', ftp, tp, stats.hits,
                stats.hits == 1 and '' or 's')
        end
        local sc = {}
        for i = 1, 3 do
            local id = props and props[i] or 0
            if id > 0 then sc[#sc + 1] = string.format('%s L%d', hud_sc_name(id), hud_sc_tier(id)) end
        end
        if #sc > 0 then lines[#lines + 1] = 'SC: ' .. table.concat(sc, ', ') end
        if target > 0 then
            lines[#lines + 1] = (match and 'Finds ' or 'Not selected: ') .. hud_sc_name(target) ..
                string.format(' L%d', hud_sc_tier(target))
        end
        hover_text = table.concat(lines, '\n')
    elseif trust_active then
        hover_text = string.format('%s  (active — click again to release)', item.name)
    elseif cooling then
        hover_text = string.format('%s  (%.1fs)', item.name, cooling.remaining or 0)
    elseif (item.kind == 'spell' or item.kind == 'trust') and item.level > 0 then
        hover_text = string.format('%s  (Lv.%d)', item.name, item.level)
    end
    api.SetItemTooltip(hover_text)

    local edge = hud_color(255, 255, 255, 24)
    if is_ws then
        if match then
            local c = HUD_SC_COLORS[target] or { 0.35, 0.85, 0.95 }
            edge = hud_color(c[1] * 255, c[2] * 255, c[3] * 255, 255)
        elseif enabled then
            edge = hud_color(89, 216, 242, 70)
        else
            edge = hud_color(255, 90, 80, 55)
        end
    end
    if trust_active then edge = HUD_COLOR_ACCENT end
    draw:AddRectFilled({ x, y }, { x + w, y + h }, HUD_COLOR_BG, 6, 0)
    if trust_active then
        draw:AddRectFilled({ x + 1, y + 1 }, { x1 - 1, y1 - 1 }, hud_color(89, 216, 242, 30), 5, 0)
        draw:AddRectFilled({ x, y }, { x + 3, y + h }, HUD_COLOR_ACCENT, 2, 0)
    end
    if match then draw:AddRectFilled({ x + 1, y + 1 }, { x1 - 1, y1 - 1 }, hud_color(89, 216, 242, 18), 5, 0) end
    draw:AddRect({ x, y }, { x + w, y + h }, trust_active and HUD_COLOR_ACCENT or (cooling and HUD_COLOR_BORDER or edge),
        6, 0, trust_active and 2 or (match and 2 or 1))

    local pad = 4
    local font_size = hud_font_size(spec)
    local label_h = mode ~= 'list' and hud_label_height(spec) or 0
    local icon_size, icon_x, icon_y
    if mode == 'list' then
        icon_size = math.min(h - pad * 2, 28)
        icon_x = x + pad
        icon_y = y + (h - icon_size) / 2
    else
        icon_size = math.min(w - pad * 2, h - label_h - pad * 2)
        icon_size = math.max(8, icon_size)
        icon_x = x + (w - icon_size) / 2
        icon_y = y + (h - label_h - icon_size) / 2
    end
    local texture = nil
    if is_ws then
        if sc_show > 0 then texture = hud_sc_texture(sc_show)
        else texture = hud_title_texture(item.ws_skill) end
    end
    if not texture and item.kind == 'trust' then texture = hud_face_texture(item.id) end
    if not texture then texture = hud_icon_texture(item.icon) end
    local icon_alpha = 255
    if is_ws then
        if not enabled then icon_alpha = 70
        elseif target > 0 and not match then icon_alpha = 105 end
    end
    if texture then
        draw:AddImage(texture, { icon_x, icon_y }, { icon_x + icon_size, icon_y + icon_size },
            { 0, 0 }, { 1, 1 }, hud_color(255, 255, 255, icon_alpha))
    else
        draw:AddRectFilled({ icon_x, icon_y }, { icon_x + icon_size, icon_y + icon_size }, hud_color(52, 66, 78, 255), 4, 0)
        local initial = tostring(item.name or '?'):sub(1, 1):upper()
        api.PushFont(nil, font_size)
        local text_w, text_h = api.CalcTextSize(initial)
        draw:AddText({ icon_x + (icon_size - text_w) / 2, icon_y + (icon_size - text_h) / 2 },
            hud_fade(HUD_COLOR_TEXT, icon_alpha), initial)
        api.PopFont()
    end
    if is_ws and sc_level > 0 then
        local bw, bh = 15, 10
        local bx, by = icon_x + icon_size - bw - 1, icon_y + 1
        local level_colors = {
            hud_color(61, 122, 148, enabled and 242 or 140),
            hud_color(115, 77, 179, enabled and 242 or 140),
            hud_color(184, 133, 46, enabled and 242 or 140),
        }
        local lc = level_colors[sc_level] or level_colors[1]
        draw:AddRectFilled({ bx, by }, { bx + bw, by + bh }, lc, 2, 0)
        api.PushFont(nil, 8)
        local lw, lh = api.CalcTextSize('L' .. sc_level)
        draw:AddText({ bx + (bw - lw) / 2, by + (bh - lh) / 2 },
            hud_fade(HUD_COLOR_WHITE, enabled and 1 or 0.65), 'L' .. sc_level)
        api.PopFont()
    end

    if mode == 'list' then
        api.PushFont(nil, font_size)
        local text_h = api.GetTextLineHeight()
        draw:AddText({ icon_x + icon_size + 7, y + (h - text_h) / 2 }, HUD_COLOR_TEXT, tostring(item.name or ''))
        api.PopFont()
    elseif label_h > 0 then
        local text = hud_fit_label(api, item, w - 4, font_size)
        api.PushFont(nil, font_size)
        local text_w, text_h = api.CalcTextSize(text)
        local label_color = HUD_COLOR_TEXT
        if is_ws then
            if not enabled then label_color = hud_fade(HUD_COLOR_TEXT, 0.45)
            elseif target > 0 and not match then label_color = hud_fade(HUD_COLOR_TEXT, 0.60) end
        elseif trust_active then
            label_color = HUD_COLOR_WHITE
        end
        draw:AddText({ x + (w - text_w) / 2, y + h - label_h + 1 }, label_color, text)
        api.PopFont()
    end

    if trust_active and mode ~= 'list' and w > 26 and h > 18 then
        draw:AddCircleFilled({ x1 - 8, y + 8 }, 3.5, HUD_COLOR_ACCENT)
        draw:AddCircle({ x1 - 8, y + 8 }, 3.5, hud_color(8, 24, 30, 255), 8, 1)
    end

    if cooling then
        local remaining = tonumber(cooling.remaining) or 0
        local progress = hud_clamp(cooling.progress, 0, 1, 0)
        draw:AddRectFilled({ x, y }, { x + w, y + h }, HUD_COLOR_SHADE, 6, 0)
        local cx, cy = icon_x + icon_size / 2, icon_y + icon_size / 2
        local radius = math.max(2, icon_size / 2 - 1)
        local start = -math.pi / 2
        local sweep = progress * math.pi * 2
        -- The unrevealed part of the clock is the remaining sector. At progress 0 the whole disc is
        -- dark; as the recast finishes the sector closes and the icon is unveiled. A fan of
        -- triangles keeps the wedge filled for angles past 180 degrees, where a convex path fill
        -- would fold over itself.
        local remaining_angle = math.max(0, math.pi * 2 - sweep)
        local steps = math.max(2, math.ceil(remaining_angle / (math.pi / 12)))
        for step = 0, steps - 1 do
            local a0 = start + sweep + remaining_angle * step / steps
            local a1 = start + sweep + remaining_angle * (step + 1) / steps
            draw:AddTriangleFilled(
                { cx, cy },
                { cx + math.cos(a0) * radius, cy + math.sin(a0) * radius },
                { cx + math.cos(a1) * radius, cy + math.sin(a1) * radius },
                HUD_COLOR_WEDGE
            )
        end
        draw:AddLine({ cx, cy }, {
            cx + math.cos(start + sweep) * radius,
            cy + math.sin(start + sweep) * radius,
        }, HUD_COLOR_ACCENT, 2)
        local label_text = string.format('%.1f', math.max(0, remaining))
        api.PushFont(nil, math.max(8, font_size))
        local measured_w, measured_h = api.CalcTextSize(label_text)
        draw:AddText({ cx - measured_w / 2, cy - measured_h / 2 }, HUD_COLOR_WHITE, label_text)
        api.PopFont()
    end

    if clicked and not hud.state.edit and enabled and (not cooling or trust_active) then
        hud_click(hud, item)
    end
end

-- Skillchain window bookkeeping. A weapon skill consumes all of the player's TP, so a drop
-- through 1000 marks the opening swing. Retail's window is 10 s, with a 3 s delay before the next
-- weapon skill can link; each subsequent link shaves one second off the remaining window.
local function hud_sc_clock()
    if not hud.sc_start then return nil end
    local elapsed = xi.clock() - hud.sc_start
    local total = HUD_SC_BASE - ((hud.sc_step or 1) - 1)
    local remaining = total - elapsed
    if remaining <= 0 then return nil end
    return remaining, HUD_SC_DELAY - elapsed
end

local function hud_update_sc()
    local tp = math.floor(tonumber(game.party_member(0, 'TP')) or 0)
    local now = xi.clock()
    if hud.last_tp and hud.last_tp >= HUD_TP_COST and tp < HUD_TP_COST and hud.last_tp - tp >= 100 then
        local step = 1
        if hud.sc_start and now - hud.sc_start <= HUD_SC_BASE + 2 then
            step = math.min(5, (hud.sc_step or 1) + 1)
        end
        hud.sc_start, hud.sc_step = now, step
    end
    if hud.sc_start and now - hud.sc_start > HUD_SC_BASE + 2 then
        hud.sc_start, hud.sc_step = nil, nil
    end
    hud.last_tp, hud.tp = tp, tp
end

-- The menu-side hide is for the client's right-hand Commands/Status stack, not for combat.
-- `xi.phase` already tracks /attack engagement from the server animation; a live target is the
-- fallback while a fight is starting or after a target swap. Either one keeps the HUD visible.
local function hud_in_battle()
    if xi.phase and xi.phase.status then
        local ok, status = pcall(xi.phase.status)
        if ok and type(status) == 'table' and status.engaged then return true end
    end
    local index = game.target('Targets[0].Index')
    return index ~= nil and index > 0 and (game.target('Targets[0].IsActive') or 0) ~= 0
end

local function hud_update_main()
    local _, index = game.equipment(0)
    index = tonumber(index) or 0
    local bag, slot = math.floor(index / 256), index % 256
    hud.main_item = slot > 0 and (tonumber(game.item(bag, slot, 'Id')) or 0) or 0
    hud.main_skill = 0
    if hud.main_item > 0 then
        local ok, item = pcall(res.item, hud.main_item)
        if ok and item then hud.main_skill = tonumber(item.skill) or 0 end
    end
end

local function hud_screen_size(api)
    local width, height = 1280, 720
    local ok, io = pcall(api.GetIO)
    if ok and io then
        local size = io.DisplaySize
        if size then
            local w = tonumber(size.x) or tonumber(size[1])
            local h = tonumber(size.y) or tonumber(size[2])
            if w and w > 0 then width = w end
            if h and h > 0 then height = h end
        end
    end
    return width, height
end

local function hud_list_width(api, groups, font_size, icon_size)
    local max_text = 0
    api.PushFont(nil, font_size)
    for _, group in ipairs(groups) do
        if group.title then max_text = math.max(max_text, hud_text_width(api, tostring(group.title):upper())) end
        for _, item in ipairs(group.items) do max_text = math.max(max_text, hud_text_width(api, tostring(item.name or ''))) end
    end
    api.PopFont()
    return math.floor(max_text + icon_size + 31)
end

-- Folder tabs. The game window can hold one group per page, which keeps the common case (a
-- handful of spells in Buff, or one trust job) on screen without scrolling through every group.
local HUD_TAB_LABELS = {
    ['Healing'] = 'Heal', ['Buff'] = 'Buff', ['Debuff'] = 'Debuff', ['Nuke'] = 'Nuke',
    ['Avatar'] = 'Avatar', ['Other'] = 'Other',
    ['White Magic'] = 'WHM', ['Black Magic'] = 'BLM', ['Summoning'] = 'SMN',
    ['Ninjutsu'] = 'NIN', ['Bard Song'] = 'BRD', ['Blue Magic'] = 'BLU', ['Geomancy'] = 'GEO',
    ['Hand-to-Hand'] = 'H2H', ['Dagger'] = 'DAG', ['Sword'] = 'SWD', ['Great Sword'] = 'GSW',
    ['Axe'] = 'AXE', ['Great Axe'] = 'GAX', ['Scythe'] = 'SCY', ['Polearm'] = 'PLM',
    ['Katana'] = 'KAT', ['Great Katana'] = 'GKT', ['Club'] = 'CLB', ['Staff'] = 'STF',
    ['Archery'] = 'ARC', ['Marksmanship'] = 'MRK',
}

local function hud_tab_font(spec)
    return math.max(8, math.min(11, hud_font_size(spec)))
end

local function hud_tab_height(spec)
    return hud_tab_font(spec) + 8
end

local function hud_tab_label(title)
    title = tostring(title or '')
    local mapped = HUD_TAB_LABELS[title]
    if mapped then return mapped end
    local role = nil
    if title:sub(1, 4) == 'Main' then role = 'Main'
    elseif title:sub(1, 3) == 'Sub' then role = 'Sub' end
    if role then
        local rest = title:gsub('^Main%s*—%s*', ''):gsub('^Sub%s*—%s*', '')
        rest = rest:gsub('SCH%s*·%s*', 'SCH ')
        return role .. ' ' .. rest
    end
    return title
end

local function hud_tab_widths(api, key, groups, spec, width)
    local font = hud_tab_font(spec)
    local widths = {}
    api.PushFont(nil, font)
    for index, group in ipairs(groups) do
        local icon_w = key == 'weapon_skills' and hud_title_texture(group.title) and 18 or 0
        widths[index] = hud_text_width(api, hud_tab_label(group.title)) + 12 + icon_w
    end
    api.PopFont()
    local rows, cursor = 1, 0
    local avail = math.max(20, width - 8)
    for index = 1, #groups do
        local tab_w = widths[index]
        if cursor > 0 and cursor + tab_w > avail then rows, cursor = rows + 1, 0 end
        cursor = cursor + tab_w + 4
    end
    return widths, rows
end

local function hud_draw_tabs(api, key, groups, spec, width, active_title)
    local font = hud_tab_font(spec)
    local tab_h = hud_tab_height(spec)
    local widths = hud_tab_widths(api, key, groups, spec, width)
    local draw = api.GetWindowDrawList()
    local selected = active_title
    local start_x, start_y = api.GetCursorPos()
    start_x = tonumber(start_x) or 4
    start_y = tonumber(start_y) or 4
    local avail = math.max(20, width - 8)
    local x, row = start_x, 0
    for index, group in ipairs(groups) do
        local label = hud_tab_label(group.title)
        local tab_w = widths[index]
        if x > start_x and x + tab_w > start_x + avail then
            row = row + 1
            x = start_x
        end
        api.SetCursorPos({ x, start_y + row * (tab_h + 4) })
        local clicked = api.InvisibleButton('hud-tab-' .. key .. '-' .. index, { tab_w, tab_h })
        local rx, ry = api.GetItemRectMin()
        local rx1, ry1 = api.GetItemRectMax()
        local active = group.title == selected
        draw:AddRectFilled({ rx, ry }, { rx1, ry1 }, active and hud_color(89, 216, 242, 40) or hud_color(255, 255, 255, 14), 4, 0)
        draw:AddRect({ rx, ry }, { rx1, ry1 }, active and HUD_COLOR_ACCENT or hud_color(255, 255, 255, 30), 4, 0, 1)
        if active then draw:AddRectFilled({ rx, ry1 - 2 }, { rx1, ry1 }, HUD_COLOR_ACCENT, 0, 0) end
        local icon = key == 'weapon_skills' and hud_title_texture(title) or nil
        local icon_w = 0
        if icon then
            icon_w = 18
            draw:AddImage(icon, { rx + 5, ry + (tab_h - 14) / 2 }, { rx + 19, ry + (tab_h - 14) / 2 + 14 },
                { 0, 0 }, { 1, 1 }, active and HUD_COLOR_WHITE or hud_color(255, 255, 255, 150))
        end
        api.PushFont(nil, font)
        local text_w, text_h = api.CalcTextSize(label)
        draw:AddText({ rx + icon_w + (tab_w - icon_w - text_w) / 2, ry + (tab_h - text_h) / 2 },
            active and HUD_COLOR_ACCENT or HUD_COLOR_TEXT, label)
        api.PopFont()
        if clicked then selected = group.title end
        x = x + tab_w + 4
    end
    local total_h = (row + 1) * tab_h + row * 4 + HUD_GRID_GAP
    api.SetCursorPos({ start_x, start_y + total_h })
    return selected
end

-- The weapon-skill status strip: current TP, the skillchain window clock and the target chain
-- picker. Keeping it out of the body means the tiles below can stay square and compact.
local function hud_ws_header_height(width)
    return width >= 300 and 26 or 44
end

local function hud_ws_header(api, key, width, header_h)
    local local_x, local_y = api.GetCursorPos()
    local screen_x, screen_y = api.GetCursorScreenPos()
    local draw = api.GetWindowDrawList()
    local font = 11
    local tp = tonumber(hud.tp) or 0
    local tp_text = string.format('TP %d / %d', tp, HUD_TP_COST)
    local tp_color = tp >= HUD_TP_COST and hud_color(115, 242, 148, 255) or hud_color(255, 188, 92, 255)
    local remaining, gate = hud_sc_clock()
    local timer_text, timer_color
    if not remaining then
        timer_text, timer_color = 'SC --', hud_color(190, 202, 214, 255)
    elseif gate > 0 then
        timer_text, timer_color = string.format('WAIT %.1f', gate), hud_color(255, 150, 96, 255)
    else
        timer_text, timer_color = string.format('GO %.1f', remaining), hud_color(115, 242, 148, 255)
    end
    api.PushFont(nil, font)
    draw:AddText({ screen_x + 2, screen_y + 4 }, tp_color, tp_text)
    draw:AddText({ screen_x + 106, screen_y + 4 }, timer_color, timer_text)
    api.PopFont()

    local combo_w, combo_x, combo_y
    if header_h >= 40 then
        combo_w = math.max(90, math.min(180, width - 10))
        combo_x, combo_y = 2, 23
    else
        combo_w = math.max(70, math.min(150, width - 172))
        combo_x, combo_y = 160, 1
    end
    api.SetCursorPos({ local_x + combo_x, local_y + combo_y })
    api.SetNextItemWidth(combo_w)
    local cur = { tonumber(hud.state.sc_target) or 0 }
    local changed = api.Combo('##hud-sc-target', cur, HUD_SC_LABELS, #HUD_SC_LABELS)
    if changed then
        local target = math.floor(hud_clamp(cur[1], 0, #HUD_SC_NAMES, 0))
        if target ~= (tonumber(hud.state.sc_target) or 0) then
            hud.state.sc_target = target
            hud_save(hud.state, hud.path)
        end
    end
    api.SetCursorPos({ local_x, local_y + header_h })
    draw:AddLine({ screen_x, screen_y + header_h - 1 }, { screen_x + width - 8, screen_y + header_h - 1 },
        hud_color(255, 255, 255, 30), 1)
end

local function hud_layout(api, key, spec, groups)
    local font_size = hud_font_size(spec)
    local label_h = hud_label_height(spec)
    local cell_h = spec.size + label_h
    local list_row = math.max(26, math.min(spec.size, 34))
    local header_h = font_size + 9
    local tabs_on = spec.tabs and #groups > 1
    local active_index = 1
    if tabs_on then
        local page = hud.page[key]
        for index, group in ipairs(groups) do
            if group.title == page then active_index = index end
        end
        hud.page[key] = groups[active_index].title
    end
    local active = groups[active_index]
    local max_items = #active.items
    if not tabs_on then
        for _, group in ipairs(groups) do max_items = math.max(max_items, #group.items) end
    end
    local screen_w, screen_h = hud_screen_size(api)
    local visible_cap = math.min(24, math.max(4, math.floor((screen_w - 40) / (spec.size + HUD_GRID_GAP))))
    local width
    if spec.layout == 'list' then
        local measure = groups
        if tabs_on then measure = { { title = nil, items = active.items } } end
        width = math.max(150, hud_list_width(api, measure, font_size, math.min(28, spec.size)) + 8)
    elseif spec.layout == 'bar' then
        local visible = math.min(math.max(max_items, 1), visible_cap)
        width = math.max(180, visible * (spec.size + HUD_GRID_GAP) - HUD_GRID_GAP + 20)
    else
        width = spec.columns * (spec.size + HUD_GRID_GAP) - HUD_GRID_GAP + 12
    end

    local function measure(group)
        local natural = 0
        if not tabs_on and group.title then natural = natural + header_h end
        local count = #group.items
        if spec.layout == 'grid' then
            local rows = math.max(1, math.ceil(count / spec.columns))
            natural = natural + rows * cell_h + (rows - 1) * HUD_GRID_GAP
        elseif spec.layout == 'list' then
            natural = natural + count * list_row
        else
            natural = natural + cell_h
        end
        return natural
    end

    local natural = 0
    if tabs_on then
        natural = measure(active)
    else
        for _, group in ipairs(groups) do
            natural = natural + measure(group) + HUD_GRID_GAP
        end
        natural = math.max(28, natural - HUD_GRID_GAP)
    end
    natural = math.max(28, natural)

    local max_body
    if spec.tabs then
        -- Folder tabs: let the window grow tall enough for the usual job/type page instead of
        -- forcing a mouse-wheel scroll. Only genuinely large pages scroll. This also keeps a
        -- deliberately ungrouped list on one tall page.
        max_body = math.min(620, math.max(180, math.floor(screen_h * 0.85)))
    else
        max_body = math.min(HUD_MAX_BODY_HEIGHT, math.max(180, math.floor(screen_h * 0.36)))
    end
    -- One item's worth of item-spacing / final NewLine is not part of the row arithmetic; keep
    -- a few pixels of slack so ImGui does not grow a scrollbar for a page that visibly fits.
    local content_h = natural + 32
    local body_h = math.min(content_h, max_body)
    local scrollbar = content_h > body_h and 14 or 0
    width = width + scrollbar
    local scroll_x = spec.layout == 'bar' and max_items > visible_cap
    if scroll_x then
        body_h = math.min(body_h + 14, max_body + 14)
    end

    local tab_h = 0
    if tabs_on then
        local _, rows = hud_tab_widths(api, key, groups, spec, width)
        local th = hud_tab_height(spec)
        tab_h = rows * th + (rows - 1) * 4 + HUD_GRID_GAP
    end
    local ws_header_h = key == 'weapon_skills' and hud_ws_header_height(width) or 0
    local height = ws_header_h + tab_h + body_h + (hud.state.edit and 72 or 12)
    return width, height, body_h, cell_h, list_row, tabs_on, active_index, tab_h, scroll_x, ws_header_h
end

local function hud_window(api, key, title, groups)
    local state = hud.state
    local spec = state.types[key]
    local edit = state.edit
    local width, height, body_h, cell_h, list_row, tabs_on, active_index, tab_h, scroll_x, ws_header_h =
        hud_layout(api, key, spec, groups)
    local screen_w, screen_h = hud_screen_size(api)
    local position = state.positions[key] or HUD_DEFAULT_POSITIONS[key]
    if edit and hud.reposition then
        position.x = math.min(position.x, math.max(4, screen_w - width - 4))
        position.y = math.min(position.y, math.max(4, screen_h - height - 4))
    elseif not edit then
        -- A resolution change must not leave a window with its title bar off screen.
        if position.x + width > screen_w then position.x = math.max(4, screen_w - width - 4) end
        if position.y + height > screen_h then position.y = math.max(4, screen_h - height - 4) end
    end
    api.SetNextWindowPos({ position.x, position.y }, edit and not hud.reposition and 4 or 1)
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(state.opacity)
    local flags = edit and (2 + 32 + 256) or (1 + 2 + 4 + 32 + 256)
    local count = 0
    for _, group in ipairs(groups) do count = count + #group.items end
    local shown_title = title .. '  (' .. count .. ')'
    if edit then shown_title = shown_title .. ' - drag to move' end

    api.PushStyleVar(2, { 4, 4 })       -- ImGuiStyleVar_WindowPadding
    api.PushStyleVar(14, { HUD_GRID_GAP, HUD_GRID_GAP }) -- ImGuiStyleVar_ItemSpacing
    local open = api.Begin(shown_title, nil, flags)
    if not open then
        api.End()
        api.PopStyleVar(2)
        return
    end
    if edit then
        local px, py = api.GetWindowPos()
        local width_now, height_now = api.GetWindowSize()
        api.GetWindowDrawList():AddRect({ px, py }, { px + width_now, py + height_now }, HUD_COLOR_ACCENT, 0, 0, 2)
    end
    if ws_header_h > 0 then hud_ws_header(api, key, width, ws_header_h) end
    if count == 0 then
        api.Text('No ' .. title:lower() .. ' for this job pair yet.')
    else
        local active = groups[active_index]
        if tabs_on then
            local selected = hud_draw_tabs(api, key, groups, spec, width, active.title)
            if selected ~= active.title then
                for index, group in ipairs(groups) do
                    if group.title == selected then active_index = index; active = group break end
                end
                hud.page[key] = selected
            end
        end
        local child_flags = scroll_x and 2048 or 0
        api.PushStyleVar(2, { 0, 0 }) -- cell rows use the window's 4 px padding, not another 8
        api.BeginChild('hud-body-' .. key, { 0, body_h }, 0, child_flags)
        local list_groups = tabs_on and { { title = nil, items = active.items } } or groups
        if spec.layout == 'list' then
            local cell_width = width - 8
            for _, group in ipairs(list_groups) do
                if not tabs_on then hud_draw_group_header(api, key, group.title, hud_font_size(spec)) end
                for _, item in ipairs(group.items) do
                    hud_draw_cell(api, spec, item, cell_width, list_row, 'list')
                end
            end
        elseif spec.layout == 'bar' then
            for _, group in ipairs(list_groups) do
                if not tabs_on then hud_draw_group_header(api, key, group.title, hud_font_size(spec)) end
                for index, item in ipairs(group.items) do
                    if index > 1 then api.SameLine(0, HUD_GRID_GAP) end
                    hud_draw_cell(api, spec, item, spec.size, cell_h, 'bar')
                end
                if #group.items > 0 then api.NewLine() end
            end
        else
            for _, group in ipairs(list_groups) do
                if not tabs_on then hud_draw_group_header(api, key, group.title, hud_font_size(spec)) end
                for index, item in ipairs(group.items) do
                    if (index - 1) % spec.columns > 0 then api.SameLine(0, HUD_GRID_GAP) end
                    hud_draw_cell(api, spec, item, spec.size, cell_h, 'grid')
                end
                if #group.items > 0 then api.NewLine() end
            end
        end
        api.EndChild()
        api.PopStyleVar(1)
    end
    if edit then
        if api.TextColored then
            api.TextColored({ 0.35, 0.85, 0.95, 1 }, 'Drag the title bar; layout and position save automatically.')
        else
            api.Text('Drag the title bar to move.')
        end
    end
    if edit then
        local px, py = api.GetWindowPos()
        local current = state.positions[key]
        if current and (math.abs(px - current.x) > 0.5 or math.abs(py - current.y) > 0.5) then
            current.x, current.y = px, py
            if api.IsMouseReleased(0) then hud_save(state, hud.path) end
        end
    end
    api.End()
    api.PopStyleVar(2)
end

-------------------------------------------------------------------------------- battle info / party info

-- Two information windows drawn by the same overlay as the action HUD.
--
-- Battle Info measures the player's own outgoing damage from the client's 0x028 action packets:
-- every swing (hit or miss), every weapon-skill hit, spell and ability result, damage taken and
-- the TP cycle.  Its Start/Pause/Stop/Reset controls only govern the measurement: the game is never
-- touched.  A damage event is timestamped with the session's running clock, so pausing stops DPS
-- from sliding and resuming continues from the same window.
--
-- Party Info reads the client's party table every frame (the same one the game's party list uses)
-- and, for the player's own party, the status icons the client keeps in partystatusicons_t.  The
-- Alliance tab shows the other two parties; their status icons are not sent to the client (retail
-- does not draw them either), so those rows say so rather than inventing a list.

local HUB_C = {
    text = { 0.92, 0.91, 0.88, 1 },
    dim = { 0.58, 0.64, 0.70, 1 },
    cyan = { 0.35, 0.85, 0.95, 1 },
    gold = { 1.00, 0.79, 0.27, 1 },
    green = { 0.45, 0.95, 0.58, 1 },
    red = { 1.00, 0.42, 0.38, 1 },
    orange = { 1.00, 0.63, 0.25, 1 },
    purple = { 0.78, 0.57, 1.00, 1 },
    blue = { 0.45, 0.72, 1.00, 1 },
    white = { 1.00, 1.00, 1.00, 1 },
}
local HUB_TRACK = { 0.07, 0.09, 0.11, 0.95 }
local HUB_CARD = { 0.06, 0.08, 0.10, 0.94 }
local HUB_CARD_EDGE = { 0.35, 0.85, 0.95, 0.24 }
local HUB_HISTORY = 40

local function hub_rgba(c, alpha)
    local a = alpha or c[4] or 1
    return hud_color(math.floor(c[1] * 255 + 0.5), math.floor(c[2] * 255 + 0.5),
        math.floor(c[3] * 255 + 0.5), math.floor(a * 255 + 0.5))
end

local function hub_text(api, c, text)
    if api.TextColored then
        api.TextColored(c, tostring(text))
    else
        api.Text(tostring(text))
    end
end

local function hub_num(n)
    n = tonumber(n) or 0
    local value = math.floor(math.abs(n) + 0.5)
    local text = tostring(value):reverse():gsub('(%d%d%d)', '%1,'):reverse():gsub('^,', '')
    return n < 0 and ('-' .. text) or text
end

local function hub_time(seconds)
    seconds = math.max(0, math.floor((tonumber(seconds) or 0) + 0.5))
    local h = math.floor(seconds / 3600)
    local m = math.floor(seconds / 60) % 60
    local s = seconds % 60
    if h > 0 then return string.format('%d:%02d:%02d', h, m, s) end
    return string.format('%d:%02d', m, s)
end

local function hub_pct(part, total)
    total = tonumber(total) or 0
    if total <= 0 then return 0 end
    return math.floor((tonumber(part) or 0) * 1000 / total + 0.5) / 10
end

local function hub_clamp01(v)
    v = tonumber(v) or 0
    if v < 0 then return 0 end
    if v > 1 then return 1 end
    return v
end

local function hub_button(api, label, color, width)
    if not api.PushStyleColor then return api.Button(label, { width or 66, 22 }) end
    local base = { color[1], color[2], color[3], 1 }
    local hover = { math.min(1, color[1] * 1.18 + 0.02), math.min(1, color[2] * 1.18 + 0.02),
        math.min(1, color[3] * 1.18 + 0.02), 1 }
    local active = { color[1] * 0.72, color[2] * 0.72, color[3] * 0.72, 1 }
    api.PushStyleColor(21, base)
    api.PushStyleColor(22, hover)
    api.PushStyleColor(23, active)
    local clicked = api.Button(label, { width or 66, 22 })
    api.PopStyleColor(3)
    return clicked
end

local function hub_section(api, title)
    api.Dummy({ 0, 2 })
    hub_text(api, HUB_C.cyan, string.upper(tostring(title)))
    api.Separator()
end

local function hub_kv(api, label, value, color, same_line)
    if same_line then api.SameLine(0, 14) end
    api.PushFont(nil, 9)
    hub_text(api, HUB_C.dim, label)
    api.PopFont()
    api.SameLine(0, 6)
    hub_text(api, color or HUB_C.text, value)
end

local function hub_draw_bar(api, draw, x, y, width, height, fraction, color, label)
    fraction = hub_clamp01(fraction)
    draw:AddRectFilled({ x, y }, { x + width, y + height }, hub_rgba(HUB_TRACK), 3, 0)
    if fraction > 0 then
        draw:AddRectFilled({ x, y }, { x + math.max(2, width * fraction), y + height }, hub_rgba(color), 3, 0)
    end
    draw:AddRect({ x, y }, { x + width, y + height }, hub_rgba(HUB_CARD_EDGE), 3, 0, 1)
    if label and label ~= '' and height >= 10 then
        api.PushFont(nil, 9)
        local tw, th = api.CalcTextSize(label)
        draw:AddText({ x + math.max(4, (width - tw) / 2), y + (height - th) / 2 }, hub_rgba(HUB_C.white, 0.96), label)
        api.PopFont()
    end
end

local function hub_bar(api, fraction, width, height, color, label)
    local draw = api.GetWindowDrawList()
    local x, y = api.GetCursorScreenPos()
    api.Dummy({ width, height })
    hub_draw_bar(api, draw, x, y, width, height, fraction, color, label)
end

local function hub_sparkline(api, values, width, height, color)
    local draw = api.GetWindowDrawList()
    local x, y = api.GetCursorScreenPos()
    api.Dummy({ width, height })
    draw:AddRectFilled({ x, y }, { x + width, y + height }, hub_rgba(HUB_TRACK), 3, 0)
    local n = #values
    if n >= 2 then
        local peak = 1
        for i = 1, n do if values[i] > peak then peak = values[i] end end
        for i = 2, n do
            local x0 = x + (i - 2) / (n - 1) * width
            local x1 = x + (i - 1) / (n - 1) * width
            local y0 = y + height - (values[i - 1] / peak) * (height - 2) - 1
            local y1 = y + height - (values[i] / peak) * (height - 2) - 1
            draw:AddLine({ x0, y0 }, { x1, y1 }, hub_rgba(color), 1.5)
        end
    end
    draw:AddRect({ x, y }, { x + width, y + height }, hub_rgba(HUB_CARD_EDGE), 3, 0, 1)
end

local hub_force_pos = { fanxi_battle = true, fanxi_party = true }

local function hub_window_begin(api, title, id, x, y, width, height, opacity)
    local screen_w, screen_h = hud_screen_size(api)
    width = math.min(width, math.max(320, screen_w - 8))
    height = math.min(height, math.max(240, screen_h - 8))
    x = math.max(4, math.min(x or 24, screen_w - width - 4))
    y = math.max(4, math.min(y or 80, screen_h - height - 4))
    local cond = hub_force_pos[id] and 1 or 4 -- Always on a reset, FirstUseEver otherwise (drag stays)
    hub_force_pos[id] = nil
    api.SetNextWindowPos({ x, y }, cond)
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(opacity or 0.95)
    api.PushStyleVar(2, { 6, 6 })       -- WindowPadding
    api.PushStyleVar(14, { 5, 5 })      -- ItemSpacing
    local open = api.Begin(title .. '###' .. id, nil, 2 + 32 + 256) -- NoResize, NoCollapse, NoSavedSettings
    if not open then
        api.End()
        api.PopStyleVar(2)
        return nil
    end
    return open, width, height
end

-- --- frame-rate measurement --------------------------------------------------------------------

local hub_fps = { since = nil, last = nil, frames = 0, value = 0, ms = 0, low = 0, history = {}, deltas = {} }

local function hub_fps_tick()
    local now = xi.clock()
    if not hub_fps.since then
        hub_fps.since, hub_fps.last = now, now
        return
    end
    local dt = now - hub_fps.last
    hub_fps.last = now
    if dt > 0 and dt < 1.5 then
        hub_fps.deltas[#hub_fps.deltas + 1] = dt
        if #hub_fps.deltas > 180 then table.remove(hub_fps.deltas, 1) end
    end
    hub_fps.frames = hub_fps.frames + 1
    local span = now - hub_fps.since
    if span < 0.5 then return end
    hub_fps.value = hub_fps.frames / span
    hub_fps.ms = span * 1000 / hub_fps.frames
    local sorted = {}
    for i = 1, #hub_fps.deltas do sorted[i] = hub_fps.deltas[i] end
    table.sort(sorted)
    local p99 = sorted[math.max(1, math.floor(#sorted * 0.99))] or sorted[#sorted] or 0
    hub_fps.low = p99 > 0 and 1 / p99 or 0
    hub_fps.history[#hub_fps.history + 1] = hub_fps.value
    if #hub_fps.history > HUB_HISTORY then table.remove(hub_fps.history, 1) end
    hub_fps.since, hub_fps.frames = now, 0
end

-- The native overlay is a renderer setting ("fps").  Battle Info carries its own readout, so when
-- the window is shown and the user has not asked to keep the native one, turn that one off; when
-- the window goes away put back whatever was there.
local hub_native_fps_prior = nil
local function hub_native_fps_sync()
    if not xi.fx then return end
    local hide = hud.state.show_battle_info and not hud.state.battle.native_fps
    if hide then
        if hub_native_fps_prior == nil then
            local ok, value = pcall(xi.fx, 'fps')
            hub_native_fps_prior = ok and (tonumber(value) or 1) or 1
        end
        pcall(xi.fx, 'fps', 0)
    elseif hub_native_fps_prior ~= nil then
        pcall(xi.fx, 'fps', hub_native_fps_prior)
        hub_native_fps_prior = nil
    end
end

-- --- battle tracker ---------------------------------------------------------------------------

local BATTLE_DAMAGE_MESSAGES = {
    [1] = true, [2] = true, [67] = true, [185] = true, [187] = true,
    [227] = true, [228] = true, [264] = true,
}
for m = 287, 383 do BATTLE_DAMAGE_MESSAGES[m] = true end

local battle = {
    active = false, paused = false, stopped = false, suppressed = false,
    elapsed = 0, run_since = nil,
    total_damage = 0, melee_damage = 0, ws_damage = 0, magic_damage = 0, ability_damage = 0,
    skillchain_damage = 0, max_hit = 0, melee_max = 0, ws_max = 0,
    hits = 0, misses = 0, crits = 0, ws_hits = 0, ws_misses = 0, ws_crits = 0,
    ws_count = 0, spell_count = 0,
    damage_taken = 0, taken_max = 0, kills = 0,
    exp_gained = 0, exp_last = nil, exp_level = nil,
    damage_events = {}, taken_events = {}, peak_dps = 0,
    tp_current = 0, tp_last = nil, tp_zero_at = nil, tp_pending_hits = 0,
    tp_segment = nil, tp_last_complete = nil, tp_history = {},
    last_damage_at = nil,
}
local battle_character = nil

local function battle_clear()
    battle.total_damage = 0
    battle.melee_damage = 0
    battle.ws_damage = 0
    battle.magic_damage = 0
    battle.ability_damage = 0
    battle.skillchain_damage = 0
    battle.max_hit = 0
    battle.melee_max = 0
    battle.ws_max = 0
    battle.hits = 0
    battle.misses = 0
    battle.crits = 0
    battle.ws_hits = 0
    battle.ws_misses = 0
    battle.ws_crits = 0
    battle.ws_count = 0
    battle.spell_count = 0
    battle.damage_taken = 0
    battle.taken_max = 0
    battle.kills = 0
    battle.exp_gained = 0
    battle.exp_last = nil
    battle.exp_level = nil
    battle.damage_events = {}
    battle.taken_events = {}
    battle.peak_dps = 0
    battle.tp_pending_hits = 0
    battle.tp_segment = nil
    battle.tp_last_complete = nil
    battle.tp_history = {}
    battle.tp_zero_at = nil
    battle.last_damage_at = nil
end

local function battle_elapsed()
    if battle.active and not battle.paused and battle.run_since then
        return battle.elapsed + (xi.clock() - battle.run_since)
    end
    return battle.elapsed
end

local function battle_begin(fresh)
    if fresh then
        battle_clear()
        battle.elapsed = 0
    end
    battle.active = true
    battle.paused = false
    battle.stopped = false
    battle.suppressed = false
    battle.run_since = xi.clock()
    battle.tp_last = math.floor(tonumber(game.party_member(0, 'TP')) or 0)
    battle.tp_current = battle.tp_last
    battle.tp_zero_at = battle.tp_last <= 1 and battle_elapsed() or nil
    battle.exp_last = tonumber(game.player('ExpCurrent')) or 0
    battle.exp_level = tonumber(game.player('MainJobLevel')) or 0
end

local function battle_start()
    if battle.active and battle.paused then
        battle.paused = false
        battle.run_since = xi.clock()
        if (battle.tp_last or 0) <= 1 then battle.tp_zero_at = battle_elapsed() end
    elseif not battle.active then
        battle_begin(true)
    else
        battle.suppressed = false
    end
end

local function battle_pause()
    if battle.active and not battle.paused then
        battle.elapsed = battle_elapsed()
        battle.run_since = nil
        battle.paused = true
    end
end

local function battle_stop()
    if battle.active then
        battle.elapsed = battle_elapsed()
        battle.run_since = nil
        battle.active = false
        battle.paused = false
        battle.stopped = true
        battle.suppressed = true
    end
end

local function battle_reset()
    battle_begin(true)
end

local function battle_auto_start()
    if not battle.active and not battle.paused and not battle.suppressed and hud.state.battle.auto_start then
        battle_begin(true)
    end
end

local function battle_state()
    if battle.active and not battle.paused then return 'LIVE', HUB_C.green end
    if battle.active and battle.paused then return 'PAUSED', HUB_C.orange end
    if battle.stopped then return 'STOPPED', HUB_C.dim end
    return 'READY', HUB_C.blue
end

local function battle_window_sum(window)
    local now = battle_elapsed()
    local cutoff = now - window
    local sum = 0
    for i = 1, #battle.damage_events do
        local e = battle.damage_events[i]
        if e.t >= cutoff then sum = sum + e.v else break end
    end
    return sum
end

local function battle_taken_window(window)
    local now = battle_elapsed()
    local cutoff = now - window
    local sum = 0
    for i = 1, #battle.taken_events do
        local e = battle.taken_events[i]
        if e.t >= cutoff then sum = sum + e.v else break end
    end
    return sum
end

local function battle_peak_update()
    local elapsed = battle_elapsed()
    if elapsed <= 0 then return end
    local window = math.min(10, math.max(1, elapsed))
    local dps = battle_window_sum(window) / window
    if dps > battle.peak_dps then battle.peak_dps = dps end
end

local function battle_prune()
    local now = battle_elapsed()
    local cutoff = now - 60
    local damage, taken = {}, {}
    for i = 1, #battle.damage_events do
        local e = battle.damage_events[i]
        if e.t >= cutoff then damage[#damage + 1] = e else break end
    end
    for i = 1, #battle.taken_events do
        local e = battle.taken_events[i]
        if e.t >= cutoff then taken[#taken + 1] = e else break end
    end
    battle.damage_events, battle.taken_events = damage, taken
end

local function battle_count_tp_hit()
    if not battle.active or battle.paused then return end
    if battle.tp_segment then
        battle.tp_segment.hits = (battle.tp_segment.hits or 0) + 1
    elseif (battle.tp_last or 0) <= 1 then
        battle.tp_pending_hits = (battle.tp_pending_hits or 0) + 1
    end
end

local function battle_tp_poll(tp)
    if not battle.active or battle.paused then
        battle.tp_current = tp
        battle.tp_last = tp
        return
    end
    local now = battle_elapsed()
    local prev = battle.tp_last or 0
    battle.tp_current = tp
    if tp > prev then
        local gain = tp - prev
        if battle.tp_segment == nil and prev <= 1 then
            -- Time the combat cycle from the first TP gain, not from whenever the bar last
            -- reached zero: standing at 0 between fights must not inflate "time to 1000".
            battle.tp_segment = {
                start = now,
                hits = battle.tp_pending_hits or 0,
                gain = 0,
            }
            battle.tp_pending_hits = 0
        end
        if battle.tp_segment then
            battle.tp_segment.gain = battle.tp_segment.gain + gain
            if tp >= 1000 then
                local s = battle.tp_segment
                local seconds = math.max(0.01, now - s.start)
                local hits = math.max(0, s.hits or 0)
                local complete = {
                    seconds = seconds,
                    hits = hits,
                    gain = s.gain,
                    tp_per_hit = hits > 0 and s.gain / hits or 0,
                    tp_per_sec = s.gain / seconds,
                }
                battle.tp_last_complete = complete
                battle.tp_history[#battle.tp_history + 1] = complete
                if #battle.tp_history > 10 then table.remove(battle.tp_history, 1) end
                battle.tp_segment = nil
                battle.tp_pending_hits = 0
            end
        end
    elseif tp < prev then
        if prev - tp >= 100 or prev >= 1000 then
            battle.tp_segment = nil
            battle.tp_pending_hits = 0
            battle.tp_zero_at = tp <= 1 and now or nil
        end
    end
    if tp <= 1 and battle.tp_segment == nil then
        battle.tp_zero_at = battle.tp_zero_at or now
    elseif tp > 1 and battle.tp_segment == nil then
        battle.tp_zero_at = nil
    end
    battle.tp_last = tp
end

local function battle_exp_poll()
    if not battle.active or battle.paused then return end
    local exp = tonumber(game.player('ExpCurrent')) or 0
    local level = tonumber(game.player('MainJobLevel')) or 0
    if battle.exp_last == nil then
        battle.exp_last, battle.exp_level = exp, level
        return
    end
    local delta = exp - battle.exp_last
    if delta >= 0 then
        battle.exp_gained = battle.exp_gained + delta
    else
        -- A level-up resets ExpCurrent; the new value is the gain in the new level.
        battle.exp_gained = battle.exp_gained + exp
    end
    battle.exp_last, battle.exp_level = exp, level
end

local function battle_add_damage(kind, value)
    if value <= 0 then return end
    value = math.floor(value)
    battle.total_damage = battle.total_damage + value
    if kind == 'melee' then
        battle.melee_damage = battle.melee_damage + value
        if value > battle.melee_max then battle.melee_max = value end
    elseif kind == 'ws' then
        battle.ws_damage = battle.ws_damage + value
        if value > battle.ws_max then battle.ws_max = value end
    elseif kind == 'magic' then
        battle.magic_damage = battle.magic_damage + value
    elseif kind == 'ability' then
        battle.ability_damage = battle.ability_damage + value
    elseif kind == 'skillchain' then
        battle.skillchain_damage = battle.skillchain_damage + value
    end
    if value > battle.max_hit then battle.max_hit = value end
end

local function hub_u32(data, off)
    local a, b, c, d = data:byte(off + 1, off + 4)
    return (a or 0) + (b or 0) * 256 + (c or 0) * 65536 + (d or 0) * 16777216
end

local function hub_u16(data, off)
    local a, b = data:byte(off + 1, off + 2)
    return (a or 0) + (b or 0) * 256
end

local function battle_on_action(data, me)
    local actor = bits(data, 40, 32)
    local is_me = actor == me
    if is_me then battle_auto_start() end
    if not battle.active or battle.paused then return end

    local target_count = math.min(bits(data, 72, 10), 32)
    local category = bits(data, 82, 4)
    local pos, limit = 150, #data * 8
    local packet_damage, packet_taken = 0, 0
    local magic_seen = false
    local now = battle_elapsed()

    for _ = 1, target_count do
        if pos + 36 > limit then break end
        local target_id = bits(data, pos, 32)
        local actions = math.min(bits(data, pos + 32, 4), 32)
        pos = pos + 36
        for _ = 1, actions do
            if pos + 87 > limit then break end
            local resolution = bits(data, pos, 3)
            local info = bits(data, pos + 17, 5)
            local value = bits(data, pos + 27, 17)
            local message = bits(data, pos + 44, 10)
            local action_pos = pos
            pos = pos + 86
            local add_value, add_message = 0, 0
            if bits(data, action_pos + 85, 1) == 1 then
                add_value = bits(data, pos + 10, 17)
                add_message = bits(data, pos + 27, 10)
                pos = pos + 37
            end
            if bits(data, pos, 1) == 1 then pos = pos + 34 end
            pos = pos + 1

            if is_me and target_id ~= me then
                if category == 1 then
                    if resolution == 0 then
                        battle.hits = battle.hits + 1
                        if info % 4 >= 2 then battle.crits = battle.crits + 1 end
                        battle_add_damage('melee', value)
                        packet_damage = packet_damage + value
                        battle_count_tp_hit()
                    else
                        battle.misses = battle.misses + 1
                    end
                elseif category == 3 then
                    if resolution == 0 then
                        battle.ws_hits = battle.ws_hits + 1
                        if info % 4 >= 2 then battle.ws_crits = battle.ws_crits + 1 end
                        battle_add_damage('ws', value)
                        packet_damage = packet_damage + value
                    else
                        battle.ws_misses = battle.ws_misses + 1
                    end
                elseif value > 0 and BATTLE_DAMAGE_MESSAGES[message] then
                    if category == 4 then
                        battle.magic_damage = battle.magic_damage + value
                        magic_seen = true
                    else
                        battle.ability_damage = battle.ability_damage + value
                    end
                    battle.total_damage = battle.total_damage + value
                    if value > battle.max_hit then battle.max_hit = value end
                    packet_damage = packet_damage + value
                end
                if add_value > 0 and add_message >= 287 and add_message < 384 then
                    battle_add_damage('skillchain', add_value)
                    packet_damage = packet_damage + add_value
                end
            elseif me and target_id == me and actor ~= me then
                if value > 0 and BATTLE_DAMAGE_MESSAGES[message] then
                    battle.damage_taken = battle.damage_taken + value
                    if value > battle.taken_max then battle.taken_max = value end
                    packet_taken = packet_taken + value
                end
            end
        end
    end

    if is_me then
        if category == 3 then battle.ws_count = battle.ws_count + 1 end
        if category == 4 and magic_seen then battle.spell_count = battle.spell_count + 1 end
    end
    if packet_damage > 0 then
        battle.damage_events[#battle.damage_events + 1] = { t = now, v = packet_damage }
        battle.last_damage_at = now
        battle_peak_update()
    end
    if packet_taken > 0 then
        battle.taken_events[#battle.taken_events + 1] = { t = now, v = packet_taken }
    end
end

local function battle_on_message(data, me)
    if #data < 0x1C then return end
    local sender = hub_u32(data, 0x04)
    local message = hub_u16(data, 0x18)
    if sender == me and message == 6 then
        battle.kills = battle.kills + 1
    end
end

local function battle_on_packet(e)
    if e.blocked or e.injected then return end
    local data = e.modified or e.data
    if type(data) ~= 'string' then return end
    if e.id ~= 0x028 and e.id ~= 0x029 then return end
    local pi = game.player_index()
    if not pi or pi < 0 then return end
    local me = tonumber(game.entity(pi, 'ServerId')) or 0
    if me == 0 then return end
    if e.id == 0x028 then
        battle_on_action(data, me)
    else
        battle_on_message(data, me)
    end
end

local function battle_tick()
    if battle_character ~= hud.character then
        battle_character = hud.character
        battle_clear()
        battle.active, battle.paused, battle.stopped = false, false, false
        battle.elapsed, battle.run_since = 0, nil
        battle.suppressed = false
    end
    local live_tp = math.floor(tonumber(game.party_member(0, 'TP')) or 0)
    battle.tp_current = live_tp
    if not battle.active or battle.paused then
        battle.tp_last = live_tp
        return
    end
    battle_tp_poll(live_tp)
    battle_exp_poll()
    battle_prune()
    battle_peak_update()
end

local function battle_average_tp()
    local seconds, hits, gain = 0, 0, 0
    for _, s in ipairs(battle.tp_history) do
        seconds = seconds + (s.seconds or 0)
        hits = hits + (s.hits or 0)
        gain = gain + (s.gain or 0)
    end
    local n = #battle.tp_history
    if n == 0 then return nil end
    return {
        seconds = seconds / n,
        hits = hits / n,
        tp_per_hit = hits > 0 and gain / hits or 0,
        tp_per_sec = seconds > 0 and gain / seconds or 0,
        count = n,
    }
end

local function battle_snapshot()
    local elapsed = battle_elapsed()
    local state = battle_state()
    local dps = elapsed > 0 and battle.total_damage / elapsed or 0
    local window = math.min(60, math.max(1, elapsed))
    local dps60 = battle_window_sum(60) / window
    local dtps_window = math.min(60, math.max(1, elapsed))
    local dtps = battle_taken_window(60) / dtps_window
    local swings = battle.hits + battle.misses
    local ws_swings = battle.ws_hits + battle.ws_misses
    local avg_hit = battle.total_damage > 0 and battle.total_damage / math.max(1, battle.hits + battle.ws_hits) or 0
    local average = battle_average_tp()
    return {
        state = state,
        active = battle.active,
        paused = battle.paused,
        stopped = battle.stopped,
        elapsed = elapsed,
        show = hud.state.show_battle_info,
        auto_start = hud.state.battle.auto_start,
        native_fps = hud.state.battle.native_fps,
        advanced = hud.state.battle.advanced,
        dps = dps,
        dps60 = dps60,
        peak_dps = battle.peak_dps,
        damage = {
            total = battle.total_damage, melee = battle.melee_damage, ws = battle.ws_damage,
            magic = battle.magic_damage, ability = battle.ability_damage,
            skillchain = battle.skillchain_damage, max = battle.max_hit, average = avg_hit,
        },
        hits = {
            melee = battle.hits, misses = battle.misses, swings = swings,
            accuracy = hub_pct(battle.hits, swings),
            crits = battle.crits, crit_rate = hub_pct(battle.crits, battle.hits),
            ws = battle.ws_count, ws_hits = battle.ws_hits, ws_misses = battle.ws_misses,
            ws_accuracy = hub_pct(battle.ws_hits, ws_swings), ws_crits = battle.ws_crits,
            spells = battle.spell_count,
        },
        defense = {
            taken = battle.damage_taken, dtps = dtps, max = battle.taken_max, kills = battle.kills,
        },
        exp = {
            gained = battle.exp_gained,
            per_hour = elapsed > 0 and battle.exp_gained / elapsed * 3600 or 0,
        },
        tp = {
            current = battle.tp_current or 0,
            segment = battle.tp_segment,
            last = battle.tp_last_complete,
            average = average,
            history = #battle.tp_history,
        },
        fps = { value = hub_fps.value, ms = hub_fps.ms, low = hub_fps.low },
    }
end

-- --- battle info window -----------------------------------------------------------------------

local function battle_window(api)
    local state = hud.state.battle
    local screen_h = select(2, hud_screen_size(api))
    local width = 440
    local height = math.min(560, math.max(360, screen_h - 24))
    local open = hub_window_begin(api, 'Battle Info', 'fanxi_battle', state.x, state.y, width, height, state.opacity)
    if not open then return end
    local label, color = battle_state()
    local px, py = api.GetWindowPos()
    local ww = api.GetWindowSize()
    local old_x, old_y = state.x, state.y
    state.x, state.y = px, py

    if api.Button('Hide##battle-hide', { 44, 18 }) then
        hud.state.show_battle_info = false
        hud_save(hud.state, hud.path)
    end
    api.SameLine(0, 8)
    hub_text(api, color, '● ' .. label)
    api.SameLine(0, 10)
    hub_text(api, HUB_C.dim, 'session ' .. hub_time(battle_elapsed()))
    api.SameLine(0, 10)
    hub_text(api, HUB_C.text, string.format('%.0f FPS', hub_fps.value or 0))
    api.SameLine(0, 10)
    if hub_fps.low and hub_fps.low > 0 then
        hub_text(api, hub_fps.low >= 50 and HUB_C.green or hub_fps.low >= 30 and HUB_C.gold or HUB_C.red,
            string.format('1%% low %.0f', hub_fps.low))
    else
        hub_text(api, HUB_C.dim, '1% low --')
    end

    if battle.active and battle.paused then
        if hub_button(api, 'Resume##battle-start', HUB_C.green, 70) then
            battle_start()
            hud_save(hud.state, hud.path)
        end
    else
        if hub_button(api, 'Start##battle-start', HUB_C.green, 70) then
            battle_start()
            hud_save(hud.state, hud.path)
        end
    end
    api.SameLine(0, 5)
    if hub_button(api, 'Pause##battle-pause', HUB_C.orange, 70) then
        battle_pause()
        hud_save(hud.state, hud.path)
    end
    api.SameLine(0, 5)
    if hub_button(api, 'Stop##battle-stop', HUB_C.red, 70) then
        battle_stop()
        hud_save(hud.state, hud.path)
    end
    api.SameLine(0, 5)
    if hub_button(api, 'Reset##battle-reset', HUB_C.purple, 70) then
        battle_reset()
        hud_save(hud.state, hud.path)
    end
    api.SetItemTooltip('Clears DPS, accuracy, TP and every other counter and starts a fresh session.')

    local elapsed = battle_elapsed()
    local dps = elapsed > 0 and battle.total_damage / elapsed or 0
    local window = math.min(60, math.max(1, elapsed))
    local dps60 = battle_window_sum(60) / window
    local avg_hit = battle.total_damage > 0 and battle.total_damage / math.max(1, battle.hits + battle.ws_hits) or 0

    api.BeginChild('##battle-body', { 0, 0 }, 0, 0)
    hub_section(api, 'Damage')
    api.PushFont(nil, 22)
    hub_text(api, HUB_C.gold, string.format('%.1f', dps))
    api.PopFont()
    api.SameLine(0, 6)
    api.PushFont(nil, 10)
    hub_text(api, HUB_C.dim, 'DPS')
    api.PopFont()
    api.SameLine(0, 18)
    hub_kv(api, '60s', string.format('%.1f', dps60), HUB_C.cyan, false)
    api.SameLine(0, 18)
    hub_kv(api, 'peak', string.format('%.1f', battle.peak_dps), HUB_C.purple, false)

    hub_kv(api, 'total', hub_num(battle.total_damage), HUB_C.gold)
    hub_kv(api, 'melee', hub_num(battle.melee_damage), HUB_C.text, true)
    hub_kv(api, 'WS', hub_num(battle.ws_damage), HUB_C.orange, true)
    if battle.magic_damage > 0 then hub_kv(api, 'magic', hub_num(battle.magic_damage), HUB_C.blue, true) end
    if battle.ability_damage > 0 then hub_kv(api, 'ability', hub_num(battle.ability_damage), HUB_C.purple, true) end
    if battle.skillchain_damage > 0 then hub_kv(api, 'SC', hub_num(battle.skillchain_damage), HUB_C.cyan, true) end
    hub_kv(api, 'max hit', hub_num(battle.max_hit), HUB_C.red)
    hub_kv(api, 'avg hit', hub_num(avg_hit), HUB_C.text, true)

    hub_section(api, 'Melee')
    local swings = battle.hits + battle.misses
    local accuracy = hub_pct(battle.hits, swings)
    local accuracy_color = accuracy >= 90 and HUB_C.green or accuracy >= 75 and HUB_C.gold or HUB_C.red
    hub_kv(api, 'accuracy', string.format('%.1f%%', accuracy), accuracy_color)
    hub_kv(api, 'hits', hub_num(battle.hits), HUB_C.green, true)
    hub_kv(api, 'misses', hub_num(battle.misses), HUB_C.red, true)
    hub_bar(api, swings > 0 and battle.hits / swings or 0, math.min(360, ww - 28), 9, accuracy_color,
        string.format('%d / %d swings', battle.hits, swings))
    hub_kv(api, 'crit', string.format('%.1f%%', hub_pct(battle.crits, battle.hits)), HUB_C.orange)
    hub_kv(api, 'crits', hub_num(battle.crits), HUB_C.orange, true)

    if battle.ws_count > 0 then
        hub_section(api, 'Weapon skills')
        local ws_swings = battle.ws_hits + battle.ws_misses
        hub_kv(api, 'used', hub_num(battle.ws_count), HUB_C.cyan)
        hub_kv(api, 'damage', hub_num(battle.ws_damage), HUB_C.orange, true)
        hub_kv(api, 'avg', hub_num(battle.ws_damage / math.max(1, battle.ws_count)), HUB_C.gold, true)
        hub_kv(api, 'accuracy', string.format('%.1f%%', hub_pct(battle.ws_hits, ws_swings)),
            hub_pct(battle.ws_hits, ws_swings) >= 90 and HUB_C.green or HUB_C.gold)
        hub_kv(api, 'max', hub_num(battle.ws_max), HUB_C.red, true)
    end

    hub_section(api, 'TP to 1000')
    local tp = battle.tp_current or 0
    hub_bar(api, math.min(1, tp / 1000), math.min(360, ww - 28), 14, tp >= 1000 and HUB_C.gold or HUB_C.cyan,
        string.format('TP %d / 1000', tp))
    local last = battle.tp_last_complete
    if battle.tp_segment then
        local now = battle_elapsed()
        local segment = battle.tp_segment
        local seconds = math.max(0.01, now - segment.start)
        local rate = segment.gain / seconds
        local remaining = math.max(0, 1000 - tp)
        local eta = rate > 0.01 and remaining / rate or 0
        hub_kv(api, 'this cycle', string.format('%d TP in %s', tp, hub_time(seconds)), HUB_C.cyan)
        hub_kv(api, 'hits', hub_num(segment.hits or 0), HUB_C.green, true)
        hub_kv(api, 'TP/s', string.format('%.1f', rate), HUB_C.gold, true)
        if tp < 1000 and rate > 0.01 then
            hub_kv(api, 'ETA', hub_time(eta), HUB_C.dim)
        end
    elseif last then
        hub_kv(api, 'last', string.format('%s · %d hits · %s TP/hit', hub_time(last.seconds), last.hits,
            hub_num(last.tp_per_hit)), HUB_C.green)
        hub_kv(api, 'speed', string.format('%.1f TP/s', last.tp_per_sec), HUB_C.gold, true)
    else
        hub_text(api, HUB_C.dim, 'Start a session and let TP fall to 0; the next 1K cycle is timed here.')
    end
    local average = battle_average_tp()
    if average then
        hub_kv(api, 'average', string.format('%s · %d hits · %s TP/hit (%d cycles)', hub_time(average.seconds),
            math.floor(average.hits + 0.5), hub_num(average.tp_per_hit), average.count), HUB_C.text)
    end

    hub_section(api, 'Defense / progress')
    hub_kv(api, 'damage taken', hub_num(battle.damage_taken), HUB_C.red)
    hub_kv(api, 'DTPS', string.format('%.1f', battle_taken_window(60) / math.min(60, math.max(1, elapsed))),
        HUB_C.orange, true)
    hub_kv(api, 'kills', hub_num(battle.kills), HUB_C.green, true)
    hub_kv(api, 'EXP', hub_num(battle.exp_gained), HUB_C.purple)
    hub_kv(api, 'EXP/hr', hub_num(elapsed > 0 and battle.exp_gained / elapsed * 3600 or 0), HUB_C.purple, true)

    hub_section(api, 'Performance')
    hub_sparkline(api, hub_fps.history, math.min(360, ww - 28), 28,
        hub_fps.value >= 55 and HUB_C.green or hub_fps.value >= 30 and HUB_C.gold or HUB_C.red)
    hub_kv(api, 'frame', string.format('%.1f FPS · %.1f ms', hub_fps.value or 0, hub_fps.ms or 0),
        (hub_fps.value or 0) >= 55 and HUB_C.green or (hub_fps.value or 0) >= 30 and HUB_C.gold or HUB_C.red)
    if hub_fps.low and hub_fps.low > 0 then
        hub_kv(api, '1% low', string.format('%.1f FPS', hub_fps.low),
            hub_fps.low >= 50 and HUB_C.green or HUB_C.orange, true)
    end
    local native = { state.native_fps }
    if api.Checkbox('Native FPS overlay##battle-native-fps', native) then
        state.native_fps = native[1] and true or false
        hud_save(hud.state, hud.path)
    end
    local auto = { state.auto_start }
    api.SameLine(0, 12)
    if api.Checkbox('Auto-start on damage##battle-auto', auto) then
        state.auto_start = auto[1] and true or false
        hud_save(hud.state, hud.path)
    end
    if not xi.fx then
        hub_text(api, HUB_C.dim, 'This host64 cannot move the native overlay; update host64.')
    end
    api.EndChild()

    if api.IsMouseReleased(0) and (math.abs((old_x or px) - px) > 0.5 or math.abs((old_y or py) - py) > 0.5) then
        hud.state.battle.x, hud.state.battle.y = px, py
        hud_save(hud.state, hud.path)
    end
    api.End()
    api.PopStyleVar(2)
end

-- --- party info ------------------------------------------------------------------------------

local hub_status_cache = {}
local hub_status_tex = {}
local hub_zone_cache = {}

local function hub_status_record(id)
    id = tonumber(id) or 0
    if id <= 0 or id == 255 or id == 65535 then return nil end
    local cached = hub_status_cache[id]
    if cached ~= nil then return cached or nil end
    local ok, info = pcall(res.status, id)
    if ok and info then
        local name = info.name_utf8 or info.name
        if type(name) == 'table' then name = name.en or name.ja or '' end
        name = tostring(name or '')
        if name ~= '' then cached = { id = id, name = name, info = info } end
    end
    hub_status_cache[id] = cached or false
    return cached or nil
end

local function hub_status_texture(id)
    id = tonumber(id) or 0
    if id <= 0 or not xi.ui or not xi.ui.texture_memory then return nil end
    local cached = hub_status_tex[id]
    if cached ~= nil then return cached or nil end
    local ok, rgba, width, height = pcall(res.status_icon_rgba, id)
    if ok and type(rgba) == 'string' and width and height and #rgba == width * height * 4 then
        local texture = xi.ui.texture_memory(rgba, width, height)
        if texture and texture ~= 0 then
            hub_status_tex[id] = texture
            return texture
        end
    end
    hub_status_tex[id] = false
    return nil
end

local function hub_zone_name(id)
    id = tonumber(id) or 0
    if id <= 0 then return nil end
    local cached = hub_zone_cache[id]
    if cached ~= nil then return cached or nil end
    local ok, zone = pcall(res.zone, id)
    if ok and zone then
        local name = zone.name_utf8 or zone.name
        if type(name) == 'table' then name = name.en or name.ja or '' end
        cached = tostring(name or '')
    end
    hub_zone_cache[id] = cached or false
    return cached or nil
end

local HUB_JOB_COLOR = {
    WAR = HUB_C.red, MNK = HUB_C.orange, WHM = HUB_C.white, BLM = HUB_C.purple,
    RDM = { 1.0, 0.55, 0.62, 1 }, THF = HUB_C.gold, PLD = { 1.0, 0.88, 0.45, 1 },
    DRK = { 0.72, 0.28, 0.45, 1 }, BST = { 0.72, 0.55, 0.32, 1 }, BRD = { 0.95, 0.62, 0.85, 1 },
    RNG = HUB_C.green, SAM = { 0.45, 0.62, 1.0, 1 }, NIN = { 0.35, 0.88, 0.78, 1 },
    DRG = { 0.62, 0.55, 1.0, 1 }, SMN = { 0.45, 0.95, 0.72, 1 }, BLU = { 0.42, 0.62, 1.0, 1 },
    COR = { 0.98, 0.84, 0.35, 1 }, PUP = { 0.85, 0.68, 0.42, 1 }, DNC = { 1.0, 0.58, 0.72, 1 },
    SCH = { 0.78, 0.84, 0.95, 1 }, GEO = { 0.48, 0.92, 0.62, 1 }, RUN = { 0.45, 0.70, 0.95, 1 },
}

local function hub_job_color(job)
    local abbr = HUD_JOB_ABBR[job or 0]
    return HUB_JOB_COLOR[abbr] or HUB_C.cyan
end

local function hub_player_buffs()
    local out, seen = {}, {}
    local function add(list)
        if type(list) ~= 'table' then return end
        for _, raw in ipairs(list) do
            local id = tonumber(raw) or 0
            if id > 0 and id ~= 255 and id ~= 65535 and not seen[id] then
                seen[id] = true
                out[#out + 1] = id
            end
        end
    end
    local ok, buffs = pcall(function() return game.player('Buffs') end)
    if ok then add(buffs) end
    if #out == 0 then
        local ok2, icons = pcall(function() return game.player('StatusIcons') end)
        if ok2 then add(icons) end
    end
    return out
end

local function hub_party_icons()
    local map = {}
    for i = 0, 4 do
        local ok, sid = pcall(game.party_icons_field, i, 'ServerId')
        sid = tonumber(sid) or 0
        if sid ~= 0 then
            local ok2, ids = pcall(game.party_icons, i)
            if ok2 and type(ids) == 'table' then
                local list, seen = {}, {}
                for j = 1, 32 do
                    local id = tonumber(ids[j]) or 0
                    if id > 0 and id ~= 255 and id ~= 65535 and not seen[id] then
                        seen[id] = true
                        list[#list + 1] = id
                    end
                end
                map[sid] = list
            end
        end
    end
    return map
end

local function hub_party_snapshot()
    local members = {}
    local icons = hud.state.party.buffs and hub_party_icons() or {}
    local self_buffs = nil
    local pi = game.player_index()
    local me = pi and pi >= 0 and tonumber(game.entity(pi, 'ServerId')) or 0
    local my_zone = math.floor(tonumber(game.party_member(0, 'Zone')) or 0)

    for slot = 0, 17 do
        local active = tonumber(game.party_member(slot, 'IsActive')) or 0
        if active ~= 0 then
            local name = game.party_member(slot, 'Name')
            if type(name) == 'string' and name ~= '' then
                local id = tonumber(game.party_member(slot, 'ServerId')) or 0
                local buffs
                if slot == 0 then
                    self_buffs = self_buffs or hub_player_buffs()
                    buffs = self_buffs
                elseif icons[id] ~= nil then
                    buffs = icons[id]
                else
                    buffs = false
                end
                local max_hp, max_mp
                if slot == 0 then
                    max_hp = tonumber(game.player('HPMax'))
                    max_mp = tonumber(game.player('MPMax'))
                end
                members[#members + 1] = {
                    slot = slot,
                    is_me = slot == 0,
                    name = name,
                    id = id,
                    hp = tonumber(game.party_member(slot, 'HP')) or 0,
                    mp = tonumber(game.party_member(slot, 'MP')) or 0,
                    tp = tonumber(game.party_member(slot, 'TP')) or 0,
                    hpp = tonumber(game.party_member(slot, 'HPPercent')) or 0,
                    mpp = tonumber(game.party_member(slot, 'MPPercent')) or 0,
                    max_hp = max_hp, max_mp = max_mp,
                    zone = tonumber(game.party_member(slot, 'Zone')) or 0,
                    main_job = tonumber(game.party_member(slot, 'MainJob')) or 0,
                    main_level = tonumber(game.party_member(slot, 'MainJobLevel')) or 0,
                    sub_job = tonumber(game.party_member(slot, 'SubJob')) or 0,
                    sub_level = tonumber(game.party_member(slot, 'SubJobLevel')) or 0,
                    buffs = buffs,
                }
            end
        end
    end

    if #members == 0 and pi and pi >= 0 then
        local name = game.entity(pi, 'Name')
        if type(name) == 'string' and name ~= '' then
            members[1] = {
                slot = 0, is_me = true, name = name, id = me,
                hp = tonumber(game.party_member(0, 'HP')) or 0,
                mp = tonumber(game.party_member(0, 'MP')) or 0,
                tp = tonumber(game.party_member(0, 'TP')) or 0,
                hpp = tonumber(game.party_member(0, 'HPPercent')) or 0,
                mpp = tonumber(game.party_member(0, 'MPPercent')) or 0,
                max_hp = tonumber(game.player('HPMax')), max_mp = tonumber(game.player('MPMax')),
                zone = my_zone,
                main_job = tonumber(game.party_member(0, 'MainJob')) or 0,
                main_level = tonumber(game.party_member(0, 'MainJobLevel')) or 0,
                sub_job = tonumber(game.party_member(0, 'SubJob')) or 0,
                sub_level = tonumber(game.party_member(0, 'SubJobLevel')) or 0,
                buffs = hub_player_buffs(),
            }
        end
    end

    return { members = members, me = me, my_zone = my_zone }
end

local function hub_party_card(api, member, width, my_zone)
    local job = HUD_JOB_ABBR[member.main_job or 0] or '???'
    local sub = HUD_JOB_ABBR[member.sub_job or 0]
    local job_text = job
    if sub and sub ~= 'NON' then job_text = job .. '/' .. sub end
    if member.main_level and member.main_level > 0 then job_text = job_text .. ' ' .. member.main_level end
    local buffs = member.buffs
    local status_count = type(buffs) == 'table' and #buffs or 0
    local unavailable = hud.state.party.buffs and buffs == false
    local show_status = hud.state.party.buffs and buffs ~= false
    local show_names = hud.state.party.names and show_status and status_count > 0
    local status_h = (show_status or unavailable) and 20 or 0
    local names_h = show_names and 12 or 0
    local height = 58 + status_h + names_h
    local x, y = api.GetCursorScreenPos()
    api.Dummy({ width, height })
    local draw = api.GetWindowDrawList()
    draw:AddRectFilled({ x, y }, { x + width, y + height }, hub_rgba(HUB_CARD), 6, 0)
    draw:AddRect({ x, y }, { x + width, y + height }, hub_rgba(HUB_CARD_EDGE), 6, 0, 1)
    if member.is_me then
        draw:AddRectFilled({ x, y + 4 }, { x + 3, y + height - 4 }, hub_rgba(HUB_C.cyan, 0.85), 1, 0)
    end

    local name = tostring(member.name or '?')
    if #name > 20 then name = name:sub(1, 20) end
    api.PushFont(nil, 13)
    draw:AddText({ x + 8, y + 5 }, hub_rgba(member.is_me and HUB_C.cyan or HUB_C.text), name)
    local name_w = api.CalcTextSize(name)
    api.PopFont()

    local hpp = member.max_hp and member.max_hp > 0 and member.hp * 100 / member.max_hp or (member.hpp or 0)
    local mpp = member.max_mp and member.max_mp > 0 and member.mp * 100 / member.max_mp or (member.mpp or 0)
    local hp_color = hpp > 75 and HUB_C.green or hpp > 40 and HUB_C.gold or HUB_C.red
    local bar_w = width - 16
    local hp_label
    if member.max_hp and member.max_hp > 0 then
        hp_label = string.format('HP %s / %s  (%.0f%%)', hub_num(member.hp), hub_num(member.max_hp), hpp)
    else
        hp_label = string.format('HP %s  (%.0f%%)', hub_num(member.hp), hpp)
    end
    local mp_label = member.max_mp and member.max_mp > 0
        and string.format('MP %s / %s', hub_num(member.mp), hub_num(member.max_mp))
        or string.format('MP %s  (%.0f%%)', hub_num(member.mp), mpp)
    local tp_label = string.format('TP %s', hub_num(member.tp))

    hub_draw_bar(api, draw, x + 8, y + 23, bar_w, 10, hpp / 100, hp_color, hp_label)
    local half = math.floor((bar_w - 6) / 2)
    hub_draw_bar(api, draw, x + 8, y + 37, half, 9, mpp / 100, HUB_C.blue, mp_label)
    hub_draw_bar(api, draw, x + 8 + half + 6, y + 37, half, 9, math.min(1, member.tp / 1000),
        member.tp >= 1000 and HUB_C.gold or HUB_C.cyan, tp_label)

    local job_color = hub_job_color(member.main_job)
    api.PushFont(nil, 9)
    local jw = api.CalcTextSize(job_text)
    api.PopFont()
    local badge_w = jw + 10
    local badge_x = x + width - badge_w - 8
    draw:AddRectFilled({ badge_x, y + 5 }, { badge_x + badge_w, y + 19 }, hub_rgba(job_color, 0.18), 3, 0)
    draw:AddRect({ badge_x, y + 5 }, { badge_x + badge_w, y + 19 }, hub_rgba(job_color, 0.55), 3, 0, 1)
    api.PushFont(nil, 9)
    draw:AddText({ badge_x + 5, y + 7 }, hub_rgba(job_color), job_text)
    api.PopFont()

    if member.zone and member.zone ~= my_zone and member.zone ~= 0 then
        local zone = hub_zone_name(member.zone)
        if zone and zone ~= '' then
            local fit = badge_x - (x + 8 + name_w + 10)
            if fit > 48 then
                api.PushFont(nil, 8)
                while #zone > 1 and api.CalcTextSize(zone) > fit do zone = zone:sub(1, #zone - 1) end
                draw:AddText({ x + 8 + name_w + 8, y + 9 }, hub_rgba(HUB_C.dim, 0.9), zone)
                api.PopFont()
            end
        end
    end

    if show_status then
        local sx, sy = x + 8, y + 52
        if status_count == 0 then
            api.PushFont(nil, 8)
            draw:AddText({ sx, sy + 4 }, hub_rgba(HUB_C.dim), 'no status effects')
            api.PopFont()
        else
            local max_icons = math.min(status_count, show_names and 10 or 18)
            local names = {}
            local hover_x1 = sx
            for i = 1, max_icons do
                local id = buffs[i]
                local info = hub_status_record(id)
                if info then
                    names[#names + 1] = info.name
                    local ix = sx + (i - 1) * 18
                    local texture = hub_status_texture(id)
                    draw:AddRectFilled({ ix, sy }, { ix + 16, sy + 16 }, hub_rgba({ 0, 0, 0 }, 0.72), 2, 0)
                    draw:AddRect({ ix, sy }, { ix + 16, sy + 16 }, hub_rgba(HUB_C.cyan, 0.35), 2, 0, 1)
                    if texture then
                        draw:AddImage(texture, { ix, sy }, { ix + 16, sy + 16 }, { 0, 0 }, { 1, 1 },
                            hub_rgba(HUB_C.white))
                    else
                        api.PushFont(nil, 8)
                        draw:AddText({ ix + 4, sy + 4 }, hub_rgba(HUB_C.text), info.name:sub(1, 1))
                        api.PopFont()
                    end
                    hover_x1 = ix + 16
                end
            end
            if status_count > max_icons then
                api.PushFont(nil, 8)
                draw:AddText({ hover_x1 + 4, sy + 4 }, hub_rgba(HUB_C.dim), '+' .. (status_count - max_icons))
                api.PopFont()
            end
            if api.IsMouseHoveringRect({ sx, sy }, { hover_x1 + 30, sy + 16 }) then
                api.SetTooltip(table.concat(names, '\n'))
            end
            if show_names then
                local text = table.concat(names, ' · ')
                if #text > 0 then
                    api.PushFont(nil, 8)
                    while #text > 1 and api.CalcTextSize(text) > width - 16 do text = text:sub(1, #text - 1) end
                    draw:AddText({ x + 8, y + 70 }, hub_rgba(HUB_C.dim), text)
                    api.PopFont()
                end
            end
        end
    elseif unavailable then
        api.PushFont(nil, 8)
        draw:AddText({ x + 8, y + 56 }, hub_rgba(HUB_C.dim), 'status effects are not sent for this party')
        api.PopFont()
    end
    api.Dummy({ 0, 4 })
end

local function party_window(api)
    local state = hud.state.party
    local screen_h = select(2, hud_screen_size(api))
    local width = 492
    local height = math.min(620, math.max(360, screen_h - 24))
    local opacity = state.replace and 1 or state.opacity
    local open = hub_window_begin(api, 'Party Info', 'fanxi_party', state.x, state.y, width, height, opacity)
    if not open then return end
    local px, py = api.GetWindowPos()
    local ww, wh = api.GetWindowSize()
    local old_x, old_y = state.x, state.y
    state.x, state.y = px, py
    if state.replace then
        local bg = api.GetBackgroundDrawList()
        bg:AddRectFilled({ px - 6, py - 6 }, { px + ww + 6, py + wh + 6 },
            hub_rgba({ 0.01, 0.015, 0.02 }, 0.98), 8, 0)
        bg:AddRect({ px - 6, py - 6 }, { px + ww + 6, py + wh + 6 },
            hub_rgba(HUB_C.cyan, 0.35), 8, 0, 1)
    end

    if api.Button('Hide##party-hide', { 44, 18 }) then
        hud.state.show_party_info = false
        hud_save(hud.state, hud.path)
    end
    api.SameLine(0, 8)
    hub_text(api, HUB_C.cyan, '● PARTY INFO')
    api.SameLine(0, 16)
    local tab = state.tab or 'party'
    if hub_button(api, 'Party##party-tab', tab == 'party' and HUB_C.cyan or HUB_C.dim, 66) then
        if tab ~= 'party' then state.tab = 'party'; hud_save(hud.state, hud.path) end
    end
    api.SameLine(0, 4)
    if hub_button(api, 'Alliance##alliance-tab', tab == 'alliance' and HUB_C.cyan or HUB_C.dim, 78) then
        if tab ~= 'alliance' then state.tab = 'alliance'; hud_save(hud.state, hud.path) end
    end
    local snapshot = hub_party_snapshot()
    local groups = { {}, {}, {} }
    for _, member in ipairs(snapshot.members) do
        local group = math.min(3, math.floor((member.slot or 0) / 6) + 1)
        groups[group][#groups[group] + 1] = member
    end
    local total = #snapshot.members
    api.SameLine(0, 16)
    hub_text(api, HUB_C.dim, string.format('%d online', total))

    -- The switches go on their own row: six controls do not fit across the window.
    local replace = { state.replace }
    if api.Checkbox('Replace game list##party-replace', replace) then
        state.replace = replace[1] and true or false
        if state.replace then hud.state.show_party_info = true end
        hud_save(hud.state, hud.path)
    end
    api.SameLine(0, 12)
    local buffs_on = { state.buffs }
    if api.Checkbox('Status icons##party-buffs', buffs_on) then
        state.buffs = buffs_on[1] and true or false
        hud_save(hud.state, hud.path)
    end
    api.SameLine(0, 12)
    local names_on = { state.names }
    if api.Checkbox('Names##party-names', names_on) then
        state.names = names_on[1] and true or false
        hud_save(hud.state, hud.path)
    end
    if state.replace then
        hub_text(api, HUB_C.gold, "Replaces the game's party list while shown.")
    end

    api.BeginChild('##party-body', { 0, 0 }, 0, 0)
    if total == 0 then
        hub_text(api, HUB_C.dim, 'No character data yet.')
    elseif tab == 'party' then
        if #groups[1] == 0 then
            hub_text(api, HUB_C.dim, 'No party.')
        else
            for _, member in ipairs(groups[1]) do
                hub_party_card(api, member, math.min(ww - 28, 464), snapshot.my_zone)
            end
        end
        if #groups[2] + #groups[3] > 0 then
            hub_text(api, HUB_C.dim, 'Alliance members are in the Alliance tab.')
        end
    else
        local any = false
        for index = 1, 3 do
            if #groups[index] > 0 then
                any = true
                hub_section(api, index == 1 and 'Party A (yours)' or ('Party ' .. string.char(64 + index)))
                for _, member in ipairs(groups[index]) do
                    hub_party_card(api, member, math.min(ww - 28, 464), snapshot.my_zone)
                end
            end
        end
        if not any then hub_text(api, HUB_C.dim, 'No party or alliance.') end
    end
    api.EndChild()

    if api.IsMouseReleased(0) and (math.abs((old_x or px) - px) > 0.5 or math.abs((old_y or py) - py) > 0.5) then
        hud.state.party.x, hud.state.party.y = px, py
        hud_save(hud.state, hud.path)
    end
    api.End()
    api.PopStyleVar(2)
end

-- --- hub entry points -------------------------------------------------------------------------

local function hub_tick()
    hub_fps_tick()
    battle_tick()
    hub_native_fps_sync()
end

local function hub_draw(api, menu_open, screen_w)
    local function under_menu(x)
        return menu_open and (tonumber(x) or 0) >= (screen_w or 0) * 0.5
    end
    if hud.state.show_battle_info and not under_menu(hud.state.battle.x) then battle_window(api) end
    if hud.state.show_party_info and not under_menu(hud.state.party.x) then party_window(api) end
end

local function hub_battle_command(args)
    hud.ensure()
    local state = hud.state
    local changed = false
    if type(args.show) == 'boolean' then state.show_battle_info = args.show; changed = true end
    if args.toggle then state.show_battle_info = not state.show_battle_info; changed = true end
    if args.start then battle_start(); changed = true end
    if args.pause then battle_pause() end
    if args.stop then battle_stop() end
    if args.reset then battle_reset() end
    if type(args.auto_start) == 'boolean' then state.battle.auto_start = args.auto_start; changed = true end
    if type(args.native_fps) == 'boolean' then state.battle.native_fps = args.native_fps; changed = true end
    if type(args.advanced) == 'boolean' then state.battle.advanced = args.advanced; changed = true end
    if args.opacity then state.battle.opacity = hud_clamp(args.opacity, 0.45, 1, state.battle.opacity); changed = true end
    if args.x then state.battle.x = math.floor(hud_clamp(args.x, -4000, 8000, state.battle.x)); changed = true end
    if args.y then state.battle.y = math.floor(hud_clamp(args.y, -4000, 8000, state.battle.y)); changed = true end
    if args.reset_position then state.battle.x, state.battle.y = 470, 96; changed = true end
    if args.x or args.y or args.reset_position then hub_force_pos.fanxi_battle = true end
    if changed then hud_save(state, hud.path) end
    return battle_snapshot()
end

local function hub_party_command(args)
    hud.ensure()
    local state = hud.state
    local changed = false
    if type(args.show) == 'boolean' then state.show_party_info = args.show; changed = true end
    if args.toggle then state.show_party_info = not state.show_party_info; changed = true end
    if args.tab == 'party' or args.tab == 'alliance' then state.party.tab = args.tab; changed = true end
    if type(args.replace) == 'boolean' then state.party.replace = args.replace; changed = true end
    if type(args.buffs) == 'boolean' then state.party.buffs = args.buffs; changed = true end
    if type(args.names) == 'boolean' then state.party.names = args.names; changed = true end
    if args.opacity then state.party.opacity = hud_clamp(args.opacity, 0.45, 1, state.party.opacity); changed = true end
    if args.x then state.party.x = math.floor(hud_clamp(args.x, -4000, 8000, state.party.x)); changed = true end
    if args.y then state.party.y = math.floor(hud_clamp(args.y, -4000, 8000, state.party.y)); changed = true end
    if args.reset_position then state.party.x, state.party.y = 24, 96; changed = true end
    if args.x or args.y or args.reset_position then hub_force_pos.fanxi_party = true end
    if changed then hud_save(state, hud.path) end
    return {
        show = state.show_party_info,
        tab = state.party.tab,
        replace = state.party.replace,
        buffs = state.party.buffs,
        names = state.party.names,
        members = hub_party_snapshot().members,
    }
end

hud.battle_command = hub_battle_command
hud.party_command = hub_party_command
hud.battle_snapshot = battle_snapshot
hud.cleanup_hubs = function()
    if hub_native_fps_prior ~= nil and xi.fx then
        pcall(xi.fx, 'fps', hub_native_fps_prior)
    end
    hub_native_fps_prior = nil
    for _, texture in pairs(hub_status_tex) do
        if texture then pcall(xi.ui.texture_free, texture) end
    end
    hub_status_tex = {}
end

-- --- chat commands ----------------------------------------------------------------------------

if xi.events and xi.events.on then
    xi.events.on('packet_in', function(e)
        local ok, err = pcall(battle_on_packet, e)
        if not ok and not hud.warned then
            hud.warned = true
            xi.chat.write('Battle Info: ' .. tostring(err), 1)
        end
    end)
end

xi.events.on('command', function(e)
    if e.blocked then return end
    local line = e.data
    if type(line) ~= 'string' then return end
    local command, rest = line:match('^//([%w_]+)%s*(.*)$')
    if not command then command, rest = line:match('^%!([%w_]+)%s*(.*)$') end
    if not command then return end
    command = command:lower()
    if command ~= 'battleinfo' and command ~= 'battle' and command ~= 'info' and
        command ~= 'partyinfo' and command ~= 'party' then return end
    e.blocked = true
    rest = (rest or ''):lower()
    if command == 'battleinfo' or command == 'battle' or command == 'info' then
        if rest == '' or rest == 'toggle' then
            hud.state.show_battle_info = not hud.state.show_battle_info
            xi.chat.write('Battle Info: ' .. (hud.state.show_battle_info and 'shown' or 'hidden'), 1)
        elseif rest == 'on' or rest == 'show' then
            hud.state.show_battle_info = true
            xi.chat.write('Battle Info: shown', 1)
        elseif rest == 'off' or rest == 'hide' then
            hud.state.show_battle_info = false
            xi.chat.write('Battle Info: hidden', 1)
        elseif rest == 'start' then
            battle_start(); hud.state.show_battle_info = true
            xi.chat.write('Battle Info: session started', 1)
        elseif rest == 'pause' then
            battle_pause()
            xi.chat.write('Battle Info: paused', 1)
        elseif rest == 'stop' then
            battle_stop()
            xi.chat.write('Battle Info: stopped', 1)
        elseif rest == 'reset' then
            battle_reset(); hud.state.show_battle_info = true
            xi.chat.write('Battle Info: reset and started', 1)
        elseif rest == 'move' then
            hud.state.battle.x, hud.state.battle.y = 470, 96
            hub_force_pos.fanxi_battle = true
            xi.chat.write('Battle Info: position reset', 1)
        elseif rest == 'fps' then
            hud.state.battle.native_fps = not hud.state.battle.native_fps
            xi.chat.write('Battle Info: native FPS overlay ' ..
                (hud.state.battle.native_fps and 'shown' or 'moved into the hub'), 1)
        elseif rest == 'auto' then
            hud.state.battle.auto_start = not hud.state.battle.auto_start
            xi.chat.write('Battle Info: auto-start ' .. (hud.state.battle.auto_start and 'on' or 'off'), 1)
        else
            xi.chat.write('Battle Info: //battleinfo [on|off|start|pause|stop|reset|move|fps|auto]', 1)
        end
        hud_save(hud.state, hud.path)
    else
        if rest == '' or rest == 'toggle' then
            hud.state.show_party_info = not hud.state.show_party_info
            xi.chat.write('Party Info: ' .. (hud.state.show_party_info and 'shown' or 'hidden'), 1)
        elseif rest == 'on' or rest == 'show' then
            hud.state.show_party_info = true
            xi.chat.write('Party Info: shown', 1)
        elseif rest == 'off' or rest == 'hide' then
            hud.state.show_party_info = false
            xi.chat.write('Party Info: hidden', 1)
        elseif rest == 'party' then
            hud.state.party.tab = 'party'; hud.state.show_party_info = true
            xi.chat.write('Party Info: Party tab', 1)
        elseif rest == 'alliance' then
            hud.state.party.tab = 'alliance'; hud.state.show_party_info = true
            xi.chat.write('Party Info: Alliance tab', 1)
        elseif rest == 'replace' then
            hud.state.party.replace = not hud.state.party.replace
            xi.chat.write('Party Info: replace game list ' .. (hud.state.party.replace and 'on' or 'off'), 1)
        elseif rest == 'buffs' then
            hud.state.party.buffs = not hud.state.party.buffs
            xi.chat.write('Party Info: status icons ' .. (hud.state.party.buffs and 'on' or 'off'), 1)
        elseif rest == 'names' then
            hud.state.party.names = not hud.state.party.names
            xi.chat.write('Party Info: status names ' .. (hud.state.party.names and 'on' or 'off'), 1)
        elseif rest == 'move' then
            hud.state.party.x, hud.state.party.y = 24, 96
            hub_force_pos.fanxi_party = true
            xi.chat.write('Party Info: position reset', 1)
        else
            xi.chat.write('Party Info: //partyinfo [on|off|party|alliance|replace|buffs|names|move]', 1)
        end
        hud_save(hud.state, hud.path)
    end
end)


function hud.frame()
    if (game.player_index() or -1) < 0 then return end
    if not hud_character() then return end
    hud.ensure()
    hub_tick()
    if hud.imgui == nil then
        local ok, api = pcall(xi.ui.imgui)
        hud.imgui = ok and api or false
    end
    local api = hud.imgui
    if not api then return end
    local state = hud.state
    local action_on = state.show_abilities or state.show_spells or state.show_trusts or state.show_weapon_skills
    local hubs_on = state.show_battle_info or state.show_party_info
    if not action_on and not hubs_on then return end
    if action_on then
        hud_update_main()
        hud_update_sc()
        hud.rebuild(false)
        if state.show_trusts then hud_refresh_trusts() end
        if next(hud.cool) then hud_update_cool(hud) end
    end

    local menu_open = false
    if state.menu_hide and not state.edit and not hud_in_battle() then
        local name = menu_name()
        -- `battle`/`attack` are combat menus, not the right-hand Commands/Status stack; never let
        -- them hide the HUD even if the target dropped before the engagement flag did.
        local lower = type(name) == 'string' and name:lower() or ''
        menu_open = lower ~= '' and lower ~= 'battle' and lower ~= 'attack'
    end
    local screen_w = hud_screen_size(api)
    if action_on then
        for _, key in ipairs(HUD_TYPES) do
            if state['show_' .. key] then
                local display = HUD_TYPE_INFO[key].title
                local position = state.positions[key] or HUD_DEFAULT_POSITIONS[key]
                -- The client's main menu is the right-hand Commands/Status/Magic stack.
                -- Hiding the right half keeps that menu readable; a HUD moved to the left stays.
                if not (menu_open and position.x >= screen_w * 0.5) then
                    hud_window(api, key, display, hud_grouped(key))
                end
            end
        end
    end
    if hubs_on then hub_draw(api, menu_open, screen_w) end
    if hud.reposition then hud.reposition = false end
end

if xi.events and xi.events.on then
    xi.events.on('present', function()
        local ok, err = pcall(hud.frame)
        if not ok and not hud.warned then
            hud.warned = true
            xi.chat.write('HUD: ' .. tostring(err), 1)
        end
    end)
end
end
hud_init()

-- Equipment for the weapon slots that the character actually carries and the main job can use.
-- `count` is the number of inventory copies (two katanas = 2), `quantity` the sum of the stack
-- sizes (99 arrows), so the weapon editor can make a copy unavailable once Main/Sub claimed it.
local function weapons()
    local main = game.party_member(0, 'MainJob') or 0
    local level = game.party_member(0, 'MainJobLevel') or 0
    if main <= 0 then return { weapons = {}, main = main, level = level } end
    local out = {}
    for id, copies in pairs(bag_index()) do
        local ok, item = pcall(res.item, id)
        if ok and item then
            local slots = tonumber(item.slots) or 0
            local jobs = tonumber(item.jobs) or 0
            local need = tonumber(item.level) or 0
            local usable = slots % 16 ~= 0
                and (jobs == 0 or has_bit(jobs, job_bit(main)))
                and (need == 0 or need <= level)
            if usable then
                local name = item.name_utf8 or item.name
                if type(name) == 'table' then name = name.en or name[2] or name[1] end
                if type(name) == 'string' and name ~= '' then
                    local quantity = 0
                    for _, at in ipairs(copies) do
                        quantity = quantity + (tonumber(at.count) or 1)
                    end
                    out[#out + 1] = {
                        id = id, name = name, slots = slots, count = #copies,
                        quantity = quantity, level = need,
                        container = copies[1].bag, slot = copies[1].slot,
                        itemLevel = tonumber(item.item_level) or 0,
                        damage = tonumber(item.damage) or 0,
                        delay = tonumber(item.delay) or 0,
                        skill = tonumber(item.skill) or 0,
                        category = item.category or '',
                    }
                end
            end
        end
    end
    table.sort(out, function(a, b)
        local an, bn = tostring(a.name):lower(), tostring(b.name):lower()
        if an == bn then return a.id < b.id end
        return an < bn
    end)
    return { weapons = out, main = main, level = level }
end

-- Diagnostic: every item in one client container, regardless of the container's reported
-- capacity. `bag_index()` scans all 18 bags the same way; this shows what the client holds.
local function bag_items(a)
    local container = tonumber(a and a.container) or 0
    local out = {}
    for slot = 1, 80 do
        local id = game.item(container, slot, 'Id')
        if id and id ~= 0 then
            local ok, item = pcall(res.item, id)
            local name = item and (item.name_utf8 or item.name) or nil
            if type(name) == 'table' then name = name.en or name[2] or name[1] end
            out[#out + 1] = {
                slot = slot, id = id, name = (type(name) == 'string' and name) or tostring(id),
                slots = ok and tonumber(item.slots) or 0,
                jobs = ok and tonumber(item.jobs) or 0,
                level = ok and tonumber(item.level) or 0,
                skill = ok and tonumber(item.skill) or 0,
            }
        end
    end
    return { container = container, max = game.container_max(container) or 0, items = out }
end


-- ---------------------------------------------------------------------------------------------
-- Throw/ranged guard
-- The client's ranged action is 0x01A category 16. A valuable ammo piece (Tathlum, orb, ...)
-- is not a consumable throwable and must never leave the ammo slot. The client's item record
-- identifies throwables by weapon skill and stack size: 27 is Throwing, 25/26 are the ranged
-- ammo skills, and a stack of one is equipment, not ammunition.
local THROW_SKILL, ARCHERY_SKILL, MARKSMANSHIP_SKILL = 27, 25, 26
local THROW_RESTORE_SECONDS = 1.2

local function ammo_is_consumable(item)
    if not item then return false end
    local skill = tonumber(item.skill) or 0
    local stack = tonumber(item.stack) or 1
    local slots = tonumber(item.slots) or 0
    if stack <= 1 or not has_bit(slots, 8) then return false end
    return skill == THROW_SKILL or skill == ARCHERY_SKILL or skill == MARKSMANSHIP_SKILL
end

local function ammo_usable(item)
    local main = game.party_member(0, 'MainJob') or 0
    local level = game.party_member(0, 'MainJobLevel') or 0
    local jobs = tonumber(item and item.jobs) or 0
    return (jobs == 0 or has_bit(jobs, job_bit(main))) and
        ((tonumber(item and item.level) or 0) <= level)
end

local function worn_ammo()
    local ammo = gear().slots.ammo
    if not ammo or not ammo.id or ammo.id == 0 then return nil end
    local ok, item = pcall(res.item, ammo.id)
    if not ok or not item then return nil end
    return { id = ammo.id, name = item_name(ammo.id) or ammo.name or tostring(ammo.id), item = item }
end

-- Throwing actions use a skill-27 item; a ranged weapon uses arrows/bolts/bullets (25/26).
local function best_safe_ammo(want_throw)
    local best, best_rank, best_qty
    for id, copies in pairs(bag_index()) do
        local ok, item = pcall(res.item, id)
        if ok and item and ammo_usable(item) then
            local skill = tonumber(item.skill) or 0
            local stack = tonumber(item.stack) or 1
            local slots = tonumber(item.slots) or 0
            local kind = want_throw and skill == THROW_SKILL or
                (not want_throw and (skill == ARCHERY_SKILL or skill == MARKSMANSHIP_SKILL))
            if kind and stack > 1 and has_bit(slots, 8) then
                local name = item_name(id) or ''
                local qty = 0
                for _, at in ipairs(copies) do qty = qty + (tonumber(at.count) or 1) end
                local rank = want_throw and (name:lower():find('shuriken', 1, true) and 1 or 2) or 1
                if not best or rank < best_rank or (rank == best_rank and qty > best_qty) then
                    best = { id = id, name = name, bag = copies[1].bag, slot = copies[1].slot }
                    best_rank, best_qty = rank, qty
                end
            end
        end
    end
    return best
end

local throw_restore_at, throw_restore_name, throw_restore_active = 0, nil, false
local throw_replay = false

local function restore_ammo(name)
    for _ = 1, 3 do
        local bag, slot = find_item(bag_index(), name)
        if not bag then return end
        xi.packets.inject(true, equip_packet(bag, slot, 3))
        coroutine.sleep(0.3)
        local ammo = gear().slots.ammo
        if ammo and ammo.name == name then return end
    end
end

local function schedule_ammo_restore(name)
    if not name then return end
    throw_restore_name = name
    throw_restore_at = math.max(throw_restore_at, os.clock() + THROW_RESTORE_SECONDS)
    if throw_restore_active then return end
    throw_restore_active = true
    xi.tasks.spawn(function()
        while os.clock() < throw_restore_at do coroutine.sleep(0.15) end
        throw_restore_active = false
        local restore = throw_restore_name
        throw_restore_name = nil
        if restore then restore_ammo(restore) end
    end)
end

-- Returns true when it blocked the action (swapped or denied), false to let it through.
local function guard_throw(e, execute)
    local ammo = worn_ammo()
    if not ammo then return false end
    if ammo_is_consumable(ammo.item) then
        if throw_restore_active then
            throw_restore_at = math.max(throw_restore_at, os.clock() + THROW_RESTORE_SECONDS)
        end
        return false
    end
    local range = gear().slots.range
    local want_throw = not (range and range.id and range.id ~= 0)
    local swap = best_safe_ammo(want_throw)
    if not swap then
        e.blocked = true
        local want = want_throw and 'a shuriken or stone' or 'arrows, bolts or bullets'
        xi.chat.write('Throw blocked: ' .. ammo.name ..
            ' is not consumable ammo; equip ' .. want .. '.', 1)
        return true
    end
    e.blocked = true
    local old_name = ammo.name
    xi.tasks.spawn(function()
        xi.packets.inject(true, equip_packet(swap.bag, swap.slot, 3))
        -- Wait for the server's equipment echo: the client needs ~1-2 s before the new ammo
        -- is actually worn. Replaying the throw before that would still throw the old piece.
        local deadline = os.clock() + 3.0
        local ready = false
        while os.clock() < deadline do
            local worn = gear().slots.ammo
            if worn and (worn.id == swap.id or worn.name == swap.name) then
                ready = true
                break
            end
            coroutine.sleep(0.08)
        end
        if not ready then
            xi.chat.write('Throw blocked: could not equip ' .. swap.name .. '; nothing was thrown.', 1)
            return
        end
        xi.chat.write('Throw: using ' .. swap.name .. ' to protect ' .. old_name .. '.', 1)
        execute()
        schedule_ammo_restore(old_name)
    end)
    return true
end

local function is_throw_command(line)
    if type(line) ~= 'string' then return false end
    local cmd = line:match('^/([%a]+)')
    if not cmd then return false end
    cmd = cmd:lower()
    return cmd == 'ra' or cmd == 'throw' or cmd == 'shoot' or cmd == 'ranged'
end

xi.events.on('command', function(e)
    if e.blocked then return end
    if throw_replay then
        throw_replay = false
        return
    end
    local line = e.data
    if not is_throw_command(line) then return end
    guard_throw(e, function()
        throw_replay = true
        xi.chat.run(line, 1)
    end)
end)

xi.events.on('packet_out', function(e)
    if e.blocked or e.injected or e.id ~= 0x01A then return end
    local data = e.modified or e.data
    if type(data) ~= 'string' or #data < 14 then return end
    local category = data:byte(11) + data:byte(12) * 256
    if category ~= 16 then return end
    guard_throw(e, function() xi.packets.inject(true, data) end)
end)

-------------------------------------------------------------------------------- follow
-- One follower controller per client. The launcher sets a leader; this loop walks the
-- leader's recorded trail with the game's own auto-run, so collision, animation and the
-- position packets all stay the client's. Tightly stacked: the target point is only
-- `distance` yalms behind the leader along the path.
local follow = {
    enabled = false,
    leader = nil,
    distance = 1.0,
    trail = {},
    trail_max = 60,
    last_record = 0,
    leader_index = nil,
    next_find = 0,
    state = 'off',
    stuck = 0,
    last_check = 0,
    last_x = nil,
    last_y = nil,
    last_dir_x = nil,
    last_dir_y = nil,
    leader_found = false,
}
local follow_events = {}

local function follow_auto_off()
    game.set_autofollow('IsAutoRunning', 0)
    game.set_autofollow('FollowDeltaX', 0)
    game.set_autofollow('FollowDeltaY', 0)
    game.set_autofollow('FollowDeltaZ', 0)
end

-- A despawned client entity stays in the table until the slot is reused; Flags1 bit 0x1000
-- and Flags3 bit 0x8000 are how the client marks it gone. There is no bit library here.
local function entity_active(i)
    local f0 = game.entity(i, 'Render.Flags0') or 0
    if f0 == 0 then return false end
    local f1 = game.entity(i, 'Render.Flags1') or 0
    local f3 = game.entity(i, 'Render.Flags3') or 0
    return math.floor(f1 / 0x1000) % 2 == 0 and math.floor(f3 / 0x8000) % 2 == 0
end

local function follow_find(now)
    if not follow.leader then return nil end
    local me = game.player_index()
    if follow.leader_index and follow.leader_index ~= me
        and game.entity(follow.leader_index, 'Name') == follow.leader
        and entity_active(follow.leader_index) then
        return follow.leader_index
    end
    if now < follow.next_find then return nil end
    follow.next_find = now + 0.5
    follow.leader_index = nil
    for i = 0, (game.entity_count() or 0) - 1 do
        if i ~= me and game.entity(i, 'Name') == follow.leader and entity_active(i) then
            follow.leader_index = i
            return i
        end
    end
    return nil
end

local function follow_record(now, lp)
    if now - follow.last_record < 0.1 then return end
    follow.last_record = now
    local last = follow.trail[#follow.trail]
    if last and math.abs(lp.x - last.x) < 0.05 and math.abs(lp.y - last.y) < 0.05 then return end
    follow.trail[#follow.trail + 1] = { x = lp.x, y = lp.y }
    if #follow.trail > follow.trail_max then table.remove(follow.trail, 1) end
end

-- Walk backwards from the leader until `distance` yalms of path are behind it.
local function follow_target(lp)
    -- Aim slightly inside the configured distance; the stop margin then leaves the
    -- follower at or under one yalm instead of a yalm plus the margin.
    local need = follow.distance * 0.8
    local px, py = lp.x, lp.y
    for i = #follow.trail, 1, -1 do
        local p = follow.trail[i]
        local dx, dy = px - p.x, py - p.y
        local seg = math.sqrt(dx * dx + dy * dy)
        if seg >= need then
            local t = seg > 0 and (need / seg) or 1
            return px + dx * t, py + dy * t
        end
        need = need - seg
        px, py = p.x, p.y
    end
    local first = follow.trail[1]
    if first then return first.x, first.y end
    return lp.x, lp.y
end

local function follow_drive(pp, tx, ty)
    local dx, dy = tx - pp.x, ty - pp.y
    local distance = math.sqrt(dx * dx + dy * dy)
    if distance <= math.max(0.15, follow.distance * 0.2) then
        follow_auto_off()
        return distance, false
    end
    dx, dy = dx / distance, dy / distance
    local changed = not follow.last_dir_x
        or math.abs(dx - follow.last_dir_x) + math.abs(dy - follow.last_dir_y) > 0.02
    if changed or (game.autofollow('IsAutoRunning') or 0) == 0 then
        -- The auto-run object's X/Y are the horizontal world axes; Z is vertical.
        game.set_autofollow('FollowDeltaX', dx)
        game.set_autofollow('FollowDeltaY', dy)
        game.set_autofollow('FollowDeltaZ', 0)
        game.set_autofollow('IsAutoRunning', 1)
        follow.last_dir_x, follow.last_dir_y = dx, dy
    end
    return distance, true
end

local function follow_tick()
    if not follow.enabled then return end
    local now = xi.clock()
    local pi = game.player_index()
    if not pi or pi < 0 then
        follow.state = 'waiting'
        follow_auto_off()
        return
    end
    local li = follow_find(now)
    if not li then
        follow.leader_found = false
        follow.state = 'waiting'
        follow_auto_off()
        follow.trail = {}
        follow.last_dir_x, follow.last_dir_y = nil, nil
        return
    end
    follow.leader_found = true
    local lp, pp = position(li), position(pi)
    if not lp or not pp then return end
    follow_record(now, lp)
    local tx, ty = follow_target(lp)
    local distance, moving = follow_drive(pp, tx, ty)
    follow.state = moving and 'following' or 'close'

    if now - follow.last_check >= 1.0 then
        local moved = 0
        if follow.last_x then
            moved = math.sqrt((pp.x - follow.last_x) ^ 2 + (pp.y - follow.last_y) ^ 2)
        end
        if moving and moved < 0.2 then follow.stuck = follow.stuck + 1 else follow.stuck = 0 end
        follow.last_x, follow.last_y = pp.x, pp.y
        follow.last_check = now
        if follow.stuck >= 4 then follow.state = 'stuck' end
    end
end

local function follow_status()
    return {
        enabled = follow.enabled,
        leader = follow.leader,
        state = follow.state,
        distance = follow.distance,
        stuck = follow.stuck,
        leader_found = follow.leader_found,
        trail = #follow.trail,
    }
end

local function follow_config(a)
    follow.enabled = a.enabled ~= false
    if a.leader ~= nil then follow.leader = tostring(a.leader) end
    if a.distance ~= nil then
        follow.distance = math.max(0.3, math.min(5.0, tonumber(a.distance) or 1.0))
    end
    follow.trail = {}
    follow.stuck = 0
    follow.leader_index = nil
    follow.next_find = 0
    follow.last_dir_x, follow.last_dir_y = nil, nil
    follow.last_check = 0
    follow.last_x, follow.last_y = nil, nil
    if follow.enabled and follow.leader then follow.state = 'waiting' else follow.state = 'off' end
    if not follow.enabled or not follow.leader then follow_auto_off() end
    return follow_status()
end

local function follow_take_events()
    local out = follow_events
    follow_events = {}
    return out
end

-- `!follow` is ours: block it before the server sees an unknown command and queue it for
-- the launcher, which owns the graph. With no launcher the queue simply waits.
xi.events.on('command', function(e)
    if e.blocked then return end
    local line = e.data
    if type(line) ~= 'string' then return end
    local body = line:match('^/%!follow%s*(.*)$') or line:match('^%!follow%s*(.*)$')
    if body == nil then return end
    e.blocked = true
    follow_events[#follow_events + 1] = { line = body, at = xi.clock() }
    xi.chat.write('FOLLOW: ' .. (body ~= '' and body or 'status'), 1)
end)

xi.events.on('frame', follow_tick)

local commands = {
    state = function() return state() end,
    metrics = function() return metrics() end,
    gear = function() return gear() end,
    follow = follow_config,
    follow_status = follow_status,
    follow_events = follow_take_events,
    command = function(a)
        if type(a.line) ~= 'string' or a.line == '' then error('command: line') end
        if not a.line:match('^[/!]') then error('command: the line must start with / or !') end
        xi.chat.run(a.line, 1)
        return true
    end,
    equip = function(a)
        local slot = SLOT_INDEX[tostring(a.slot or ''):lower()]
        if slot == nil then error('equip: unknown slot ' .. tostring(a.slot)) end
        return equip_item(slot, a.item)
    end,
    equip_set = equip_set,
    gearswap = gearswap,
    phase = phase,
    phase_status = function() return xi.phase and xi.phase.status() or { enabled = false } end,
    phase_lock = phase_lock,
    phase_kiting = phase_kiting,
    phase_resting = phase_resting,
    phase_focus = phase_focus,
    phase_lock_slots = phase_lock_slots,
    job_spells = job_spells,
    job_abilities = job_abilities,
    hud = function(a) return hud.command(a or {}) end,
    battle_info = function(a) return hud.battle_command and hud.battle_command(a or {}) or nil end,
    party_info = function(a) return hud.party_command and hud.party_command(a or {}) or nil end,
    weapons = weapons,
    bag_items = bag_items,
    icons = icons,
    item_ids = item_ids,
    chat_send = function(a)
        if type(a.line) ~= 'string' then error('chat_send: line') end
        local line = a.line
        if not line:match('^/') then line = '/say ' .. line end -- the game sends a bare line nowhere
        xi.chat.run(line, tonumber(a.mode) or 1)
        return true
    end,
    chat_log = function(a)
        local since, limit = tonumber(a.since) or 0, tonumber(a.limit) or 100
        local out = {}
        for _, l in ipairs(log) do
            if l.seq > since then out[#out + 1] = l end
        end
        while #out > limit do table.remove(out, 1) end
        return { lines = out, last = log_seq }
    end,
    chat_input = function(a)
        if type(a.text) == 'string' then xi.chat.set_input(a.text) end
        local text = xi.chat.input()
        return { text = text and plain(text) or '' }
    end,
    keys = keys,
    key = function(a)
        key(type(a.key) == 'number' and a.key or key_code(a.key), a.down ~= false)
        return true
    end,
    release_keys = release_keys,
    capture = capture,
    entities = entities,
    target = function(a)
        local i = tonumber(a.index)
        if not i then error('target: index') end
        game.set_target_index(i)
        coroutine.sleepf(2)
        return state().target
    end,
    wait = function(a)
        if a.frames then coroutine.sleepf(tonumber(a.frames)) else sleep_ms(tonumber(a.ms) or 100) end
        return true
    end,
    lua = run_lua,
}

-------------------------------------------------------------------------------- the server

local server, clients = nil, {}

local function send(c, t)
    local line = json.encode(t) .. '\n'
    local i = 1
    while i <= #line do
        local n, err, part = c.sock:send(line, i)
        if n then i = n + 1
        elseif err == 'timeout' and coroutine.running() then
            i = (part or i - 1) + 1
            coroutine.sleepf(1)
        else
            c.closed = true
            return
        end
    end
end

local function handle(c, line)
    local ok, req = pcall(json.decode, line)
    if not ok or type(req) ~= 'table' then
        send(c, { ok = false, error = 'bad JSON: ' .. tostring(req) })
        return
    end
    local fn = commands[req.cmd]
    if not fn then
        send(c, { id = req.id, ok = false, error = 'no command "' .. tostring(req.cmd) .. '"' })
        return
    end
    xi.tasks.spawn(function()
        local ok2, r = pcall(fn, type(req.args) == 'table' and req.args or {})
        if ok2 then
            send(c, { id = req.id, ok = true, result = r })
        else
            send(c, { id = req.id, ok = false, error = tostring(r) })
        end
    end)
end

local function poll()
    if server then
        while true do
            local s = server:accept()
            if not s then break end
            s:settimeout(0)
            pcall(s.setoption, s, 'tcp-nodelay', true)
            clients[#clients + 1] = { sock = s, buf = '' }
            xi.log('control: a client connected')
        end
    end
    for i = #clients, 1, -1 do
        local c = clients[i]
        while not c.closed do
            local data, err, part = c.sock:receive(8192)
            data = data or part
            if data and #data > 0 then c.buf = c.buf .. data end
            if err == 'closed' then c.closed = true end
            if not data or #data == 0 or err then break end
        end
        while true do
            local nl = c.buf:find('\n', 1, true)
            if not nl then break end
            local line = c.buf:sub(1, nl - 1)
            c.buf = c.buf:sub(nl + 1)
            if line:match('%S') then handle(c, line) end
        end
        if c.closed then
            c.sock:close()
            table.remove(clients, i)
            xi.log('control: a client left')
        end
    end
end

local function listen()
    local s = socket.tcp()
    s:setoption('reuseaddr', true)
    local ok, err = s:bind('127.0.0.1', PORT)
    if not ok then
        xi.log('control: cannot listen on 127.0.0.1:' .. PORT .. ': ' .. tostring(err))
        s:close()
        return nil
    end
    s:listen(4)
    s:settimeout(0)
    xi.log('control: listening on 127.0.0.1:' .. PORT)
    return s
end

server = listen()
xi.events.on('frame', poll)
xi.events.on('unload', function()
    release_keys()
    if hud then
        if hud.cleanup_hubs then hud.cleanup_hubs() end
        hud.save(hud.state, hud.path)
        for _, texture in pairs(hud.textures) do
            if texture then pcall(xi.ui.texture_free, texture) end
        end
        hud.textures = {}
        for _, texture in pairs(hud.faces) do
            if texture then pcall(xi.ui.texture_free, texture) end
        end
        hud.faces = {}
        for _, texture in pairs(hud.item_textures) do
            if texture then pcall(xi.ui.texture_free, texture) end
        end
        hud.item_textures = {}
        for _, texture in pairs(hud.sc_textures) do
            if texture then pcall(xi.ui.texture_free, texture) end
        end
        hud.sc_textures = {}
    end
    for _, c in ipairs(clients) do c.sock:close() end
    if server then server:close() end
end)
