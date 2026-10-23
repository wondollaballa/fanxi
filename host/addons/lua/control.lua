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
         spell_overrides}
                             precast / midcast / state engine: the host holds the action packet,
                             wears the precast set, sends it, then wears the midcast set behind
                             it, and returns to the state set
  phase_status               the engine's rules, counters, state, active set and slot pins
  phase_lock {locked}        hold the set that is worn now (true) or resume auto-swaps (false)
  phase_kiting {on}          forced kiting state, on until switched off
  phase_resting {on}         manual resting state (this server has no rest packet)
  phase_focus {mode}         idle focus: auto, dt, pdt, mdt, eva or meva
  phase_lock_slots {mask}    pin equipment slots (bit 0 main .. bit 15 back) out of every set
  job_spells                 the current job pair's spell list for the override form
  job_abilities              the current main/sub job abilities the client's menu lists
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

    -- Spells: the user's precast set, then a midcast default for every spell, then per-spell
    -- overrides. A default midcast replaces the library's skill sets; leaving it empty keeps
    -- the skill-based sets (midcast.Healing Magic, midcast.Ninjutsu, ...).
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
    if precast and mid_default then
        rules[#rules + 1] = { category = PHASE_MAGIC, action = 0, pre = precast, mid = mid_default }
    elseif precast then
        rules[#rules + 1] = { category = PHASE_MAGIC, action = 0, pre = precast }
    elseif mid_default then
        rules[#rules + 1] = { category = PHASE_MAGIC, action = 0, mid = mid_default }
    end
    if not mid_default and type(sets.midcast) == 'table' then
        local mid_cache = {}
        for index = 0, 1023 do
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
    for id, mid in pairs(spell_override) do
        rules[#rules + 1] = { category = PHASE_MAGIC, action = id, pre = precast, mid = mid }
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
    local job = game.party_member(0, 'MainJob') or 0
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
        ja_overrides = a.ja_overrides, spell_overrides = a.spell_overrides, focus = a.focus,
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
                    out[#out + 1] = {
                        id = id, name = type(name) == 'string' and name or tostring(id),
                        skill = skill or '', level = level,
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
    for _, c in ipairs(clients) do c.sock:close() end
    if server then server:close() end
end)
