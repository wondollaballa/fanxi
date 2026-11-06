--[==[
The control port: a built-in addon (xi kind) that lets another program drive the game. host64 loads
it on the first frame when FFXI_CONTROL is set (core.c): FFXI_CONTROL=1 listens on 127.0.0.1:54300,
FFXI_CONTROL=<port> on that port. tools/xi_mcp.py speaks it for MCP clients.

The protocol is JSON, one object per line each way:

  -> {"id": 1, "cmd": "state", "args": {...}}
  <- {"id": 1, "ok": true, "result": ...}    or    {"id": 1, "ok": false, "error": "..."}

Requests run as tasks on the game thread (one frame at a time, so a request may wait on frames:
key holds, frame captures, waits). Commands:

  state                      sign-in state, the player, zone, position, target, menu, chat input,
                              sleeping (parked, hidden from other clients)
  sleep / wake               park this box without logging out, or resume it in place
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
  command {line}             run a line as if typed, without the /say fallback: //zone, //merits, /heal
  metrics                    state + EXP/hr, DPS, damage and the active gear of this client
  gear                       the item, count and encumbrance bit in every equipment slot
  equip {slot, item}         wear the named item from this character's bags
  equip_set {items}          wear a GearSwap-style set: [{slot="head", item="..."}, ...], every
                             0x050 in one frame (as GearSwap's equip burst does) and pieces
                             already worn left alone
  gearswap {path, source}    parse a GearSwap Lua library and return its sets as data (read-only);
                             source is the library's text when it is not on this machine
  phase {path|source|sets, enabled, engaged, idle_town, idle_field, move, kite, rest,
         precast, precast_song, midcast, default_ws, default_ja, focus, ws_overrides,
         ja_overrides, spell_overrides, spell_category_overrides, spell_modes}
                             precast / midcast / state engine: the host holds the action packet,
                             wears the precast set, sends it, then wears the midcast set behind
                             it, and returns to the state set. spell_category_overrides holds one
                             set per mode (enfeebles_skill, enfeebles_macc, enfeebles_duration,
                             enfeebles_hybrid, enfeebles_mnd, enfeebles_int, enfeebles_general,
                             buff_potency, buff_duration, cure_potency, cure_cast, nuke_mab,
                             nuke_mdmg, nuke_mb, helix_magic, helix_duration, dark_potency,
                             dark_macc, dark_duration, divine_mab, divine_flash, divine_macc,
                             enhancing_skill, enhancing_stoneskin, enhancing_phalanx,
                             enhancing_reprisal, enhancing_duration, enhancing_general,
                             enspells);
                             spell_modes arms one mode per group (enfeebles, enhancing, enspells,
                             curing, nuking, helix, dark, divine, songs).
                             A spell uses its group's armed set unless a per-spell override names
                             one.  Enfeebles, Enhancing and Divine Magic default to auto and use
                             the set for the spell's own kind (enfeebles: skill / macc / duration /
                             hybrid / mnd / int / general; enhancing: skill / stoneskin / phalanx /
                             reprisal / duration / general; divine: mab / flash / macc); arming one
                             of the group's other modes forces that one set instead.  nuke_mb is
                             not armed: a nuke wears it while a magic burst window is open on the
                             player's target
  phase_status               the engine's rules, counters, state, the action set that is on and
                             the recent windows (actionSet/history), armed modes, slot pins and
                             whether a magic burst window is open (burst)
  phase_lock {locked}        hold the set that is worn now (true) or resume auto-swaps (false)
  phase_kiting {on}          forced kiting state, on until switched off
  phase_resting {on}         manual resting state (this server has no rest packet)
  phase_focus {mode}         idle focus: auto, dt, pdt, mdt, eva or meva
  phase_lock_slots {mask}    pin equipment slots (bit 0 main .. bit 15 back) out of every set
  job_spells                 the current job pair's spell list for the override form, with the
                             spell group (enfeebles, enhancing, enspells, curing, nuking,
                             helix, dark, divine or songs) of each; a level-99 main job also gets
                             its job-point spells
  job_abilities              the current main/sub job abilities the client's menu lists
  hud {show_hud, show_abilities, show_spells, show_trusts, show_weapon_skills, show_mounts,
       show_target, show_equipview, show_battle_hud, show_sch,
       edit, type, layout, columns, size, labels, font, tabs, group, custom_groups, assign_key,
       assign_group, target, target_tab, targets, opacity, menu_hide, reset_positions,
       center_positions, warp_marks, mounts}
                             the whole HUD (show_hud) and its in-game windows (the action windows,
                             the two info hubs and the Mount HUD): toggle,
                             per-type re-layout/grouping, move mode (edit: true draws the centred
                             Done box; false saves and leaves), menu-side hiding, the default
                             corner reset (reset_positions) or the move-mode reset that parks all
                             six windows in the middle (center_positions), per-tab spell target
                             modes (targets map, or target + target_tab; values selected, stnpc,
                             stpc or me), and the character's saved //warp places for the Zoning spell
                             page (warp_marks: [{slot, alias, zone_name}, ...]); returns the
                             saved state (also in metrics.hud).  show_mounts is the Mount HUD,
                             show_target is the Target Debuffs window, show_equipview is the
                             in-game EquipViewer (collapsed: the set being worn; expanded: the
                             4x4 equipment grid) and show_battle_hud is the
                             Battle automation HUD; show_sch is the Scholar HUD (strategems,
                             skillchain macros and magic bursts), unset by default so it follows
                             the main job (nil: shown for Scholar only); the
                             mounts map carries its prefs ({selected, columns, size, x, y}) and the
                             returned copy names the mount being ridden and the table's size.
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
    if e.blocked then return end
    local text = plain(e.modified or e.data or '')
    -- The HUD asks //trust <id> ui hud for a support Trust's action catalogue.  The answer
    -- is a set of data lines for this addon, not chat: swallow them before the log.
    if text:sub(1, 10) == 'TrustData|' then
        e.blocked = true
        if trust_data_hook then trust_data_hook(text:sub(11)) end
        return
    end
    add_line(e.mode_modified or e.mode, text)
end)

xi.events.on('packet_in', function(e)
    if e.id ~= 0x017 or e.blocked or e.injected or xi.chat.game_lines() then return end
    local d = e.data or ''
    if #d < 24 then return end
    local body = plain((d:sub(24):gsub('%z.*', '')))
    if body:sub(1, 10) == 'TrustData|' then
        e.blocked = true
        if trust_data_hook then trust_data_hook(body:sub(11)) end
        return
    end
    local sender = plain((d:sub(9, 23):gsub('%z.*', '')))
    add_line(d:byte(5), body, sender ~= '' and sender or nil)
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

-- Whether the player is looking at (and typing in) the game window. A HUD that hides for a menu or
-- a chat line does not need to step aside while the launcher is in front: that is when the player
-- is arranging the HUD, not reading the menu.
local function game_focused()
    if not (xi.ui and xi.ui.focused) then return true end
    local ok, focused = pcall(xi.ui.focused)
    return not ok or focused ~= false
end

-- The chat line is its own "menu" for the HUD. Hide only while it has text: an open but empty
-- line (or one the game left open in the background) must not make the HUD look gone.
local function hud_chat_input_open()
    if not xi.chat or not xi.chat.input then return false end
    local text, open = xi.chat.input()
    return open == true and type(text) == 'string' and text ~= ''
end

local function position(i)
    local x, z, y = game.entity(i, 'Movement.LocalPosition.X'), game.entity(i, 'Movement.LocalPosition.Z'),
        game.entity(i, 'Movement.LocalPosition.Y')
    if not x then return nil end
    return { x = x, y = y, z = z, heading = game.entity(i, 'Heading') }
end

local sleeping = false

local function state()
    local s = { login_status = game.login_status(), menu = menu_name(), sleeping = sleeping }
    local text, open = xi.chat.input()
    s.chat_input = text and plain(text) or nil
    s.chat_open = open == true
    s.focused = game_focused()
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
            sub_job = game.party_member(0, 'SubJob'),
            sub_level = game.party_member(0, 'SubJobLevel'),
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

-- BEGIN Item name aliases
-- The client's item names do not always match the server's.  The Reforged Bonanza
-- weapons append " (Reforged)" (and two use the other copy's spelling entirely:
-- Premium Hearts and Demonic Axe), while the final iLvl 119 III weapons keep the base
-- name but the client has several stage rows under it.  res.item_by_name cannot see the
-- suffix and returns the lowest (weakest) id for a base name, so a set that names one
-- of these drew an empty EquipViewer slot or the wrong stage's tooltip and stats.
--
-- Keep the server spellings here; item_id_for_name falls back to the client table for
-- every ordinary item.  item_ids, find_item and the launcher's stat query all use this
-- resolver so the set preview, the worn set and the item card agree.
local REFORGED_ITEM_IDS = {
    ['ice brand (reforged)'] = 20663,
    ['flametongue (reforged)'] = 20664,
    ['dragon fangs (reforged)'] = 21540,
    ['premium heart (reforged)'] = 21541,
    ['chocobo knife (reforged)'] = 21592,
    ['air knife (reforged)'] = 21593,
    ['onion sword iii (reforged)'] = 21602,
    ['save the queen iii (reforged)'] = 21603,
    ['brave blade iii (reforged)'] = 21677,
    ['malefic axe (reforged)'] = 21732,
    ['drastic axe (reforged)'] = 21789,
    ['final sickle (reforged)'] = 21842,
    ["hebo's spear (reforged)"] = 21893,
    ['yagyu darkblade (reforged)'] = 21936,
    ['zanmato +2 (reforged)'] = 21952,
    ['mutsu. yoshi. (reforged)'] = 21953,
    ["wizard's rod (reforged)"] = 21991,
    ["pandit's staff (reforged)"] = 22168,
    ["artemis's bow +2 (reforged)"] = 22169,
    ['exeter (reforged)'] = 22170,
}

-- The server's Prime and REMA family tables name the final form; these are their
-- base names plus the hand-added "119 III" spellings that GearSwap libraries may carry.
local FINAL_FORM_ITEM_IDS = {
    ['aegis'] = 16200,
    ['almace'] = 20689,
    ['amanomurakumo'] = 21954,
    ['annihilator'] = 21267,
    ['apocalypse'] = 21808,
    ['armageddon'] = 21269,
    ['aymur'] = 21751,
    ['bravura'] = 21756,
    ['burtgang'] = 20687,
    ['caladbolg'] = 21684,
    ['caliburnus'] = 21646,
    ['carnwenhan'] = 20586,
    ['claustrum'] = 22060,
    ['conqueror'] = 21757,
    ['daurdabla'] = 18839,
    ['death penalty'] = 21268,
    ['dokoku'] = 21932,
    ['duban'] = 26495,
    ['earp'] = 22164,
    ['epeolatry'] = 21685,
    ['excalibur'] = 20685,
    ['fail-not'] = 22117,
    ['farsha'] = 21752,
    ['foenaria'] = 21837,
    ['fomalhaut'] = 22143,
    ['gae buide'] = 21891,
    ['gambanteinn'] = 21079,
    ['gandiva'] = 22116,
    ['gastraphetes'] = 21266,
    ['gjallarhorn'] = 18840,
    ['glanzfaust'] = 20510,
    ['gungnir'] = 21857,
    ['guttler'] = 21750,
    ['helheim'] = 21653,
    ['hvergelmir'] = 22064,
    ['idris'] = 21080,
    ['kannagi'] = 21908,
    ['kenkonken'] = 20511,
    ['kikoku'] = 21906,
    ['kogarasumaru'] = 21955,
    ['kusanagi'] = 21986,
    ['laevateinn'] = 22062,
    ['laphria'] = 21785,
    ['liberator'] = 21809,
    ['lorg mor'] = 22002,
    ['loughnashade'] = 22307,
    ['mandau'] = 20583,
    ['masamune'] = 21956,
    ['mjollnir'] = 21077,
    ['mpu gandring'] = 21590,
    ['murgleis'] = 20686,
    ['nagi'] = 21907,
    ['nirvana'] = 22063,
    ['ochain'] = 16199,
    ['opashoro'] = 22106,
    ['pinaka'] = 22163,
    ['ragnarok'] = 21683,
    ['redemption'] = 21810,
    ['rhongomiant'] = 21859,
    ['ryunohige'] = 21858,
    ['spalirisos'] = 21730,
    ['spharai'] = 20509,
    ['terpsichore'] = 20584,
    ['tizona'] = 20688,
    ['tupsimati'] = 22061,
    ['twashtar'] = 20587,
    ['ukonvasara'] = 21758,
    ['vajra'] = 20585,
    ['varga purnikawa'] = 21535,
    ['verethragna'] = 20512,
    ['yagrush'] = 21078,
    ['yoichinoyumi'] = 22115,
    ['dokoku 119 iii'] = 21932,
    ['hvergelmir 119 iii'] = 22064,
    ['kannagi 119 iii'] = 21908,
    ['kikoku 119 iii'] = 21906,
    ['nagi 119 iii'] = 21907,
    ['opashoro 119 iii'] = 22106,
    ['tupsimati 119 iii'] = 22061,
}

local function item_id_for_name(name)
    local wanted = tostring(name or ''):match('^%s*(.-)%s*$')
    if wanted == '' then return 0 end
    local key = wanted:lower()
    local alias = REFORGED_ITEM_IDS[key] or FINAL_FORM_ITEM_IDS[key]
    if not alias then
        -- A version string is a description, not part of the item name: accept the
        -- server's "(Level 119 III)" spelling too.
        local base = key:gsub('%s*%(level%s*119%s*iii%)%s*$', '')
        base = base:gsub('%s*level%s*119%s*iii%s*$', '')
        base = base:gsub('%s+119%s*iii%s*$', ''):gsub('%s+$', '')
        alias = FINAL_FORM_ITEM_IDS[base]
    end
    if alias then return alias end
    local ok, item = pcall(res.item_by_name, wanted)
    if not ok or not item then return 0 end
    return tonumber(item.id) or 0
end

-- The generic `lua` command runs in its own chunk, so the launcher's stat query asks
-- this resolver instead of duplicating the tables.
xi.item_id_for_name = item_id_for_name
-- END Item name aliases

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
    local wanted_id = item_id_for_name(wanted)
    if wanted_id > 0 and by_id[wanted_id] then
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

-- Hand the phase engine the exact bag/index of the four weapon slots.  The worn table is
-- forgotten on a zone, and a TP set does not always name a weapon, so a lock taken from chat
-- would otherwise have no copy to put back.  Call this immediately before lock_slots().
local function remember_worn_weapons()
    if not (xi.phase and xi.phase.remember) then return end
    for kind = 0, 3 do
        local ok, _, index = pcall(game.equipment, kind)
        index = ok and tonumber(index) or 0
        local bag, slot = math.floor(index / 256), index % 256
        if slot > 0 then xi.phase.remember(kind, bag, slot) end
    end
end

local function equip_item(slot_number, name)
    local bag, slot, id, actual = find_item(bag_index(), name)
    if not bag then error('not in this character\'s bags: ' .. tostring(name)) end
    xi.packets.inject(true, equip_packet(bag, slot, slot_number))
    -- A hand equip the phase engine did not choose: it only sends the slots that differ, so
    -- forget the row or the next state set would leave this piece as the player left it.
    if xi.phase then xi.phase.forget_slot(slot_number) end
    return { slot = slot_number, item = actual, id = id, bag = bag, index = slot }
end

-- The on-screen combat HUD is defined further down (it needs job_spells/job_abilities);
-- metrics carries its current switch/layout state so the launcher's toggles reflect the client.
local hud

-- Ctrl+H toggles the whole HUD.  It is a global bind, including while the chat line is open: the
-- key is consumed, so it never types an H.  Declared out here so the unload handler can remove it.
local HUD_HOTKEY = '^h'

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

-- Parse a library in the sandbox. The launcher owns the GearSwap files, so a client on another
-- machine has none of them: it sends the library's text and `path` is only the name the errors and
-- the reply use. A caller on the same machine may keep sending the path alone, and the host reads
-- the file itself. (No new chunk-level locals here: control.lua is at the 200-local limit.)
local function gearswap_sets(a)
    local path = type(a.path) == 'string' and a.path ~= '' and a.path or nil
    local source = type(a.source) == 'string' and a.source ~= '' and a.source or nil
    if not source then
        if not path then error('gearswap: path') end
        local file = io.open(path, 'rb')
        if not file then error('cannot read ' .. path) end
        source = file:read('*a')
        file:close()
    end
    local chunk, err = loadstring(source, '@' .. (path or 'gearswap.lua'))
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
    return { path = a.path, sets = gearswap_sets(a) }
end

-------------------------------------------------------------------------------- phase engine

-- An outgoing 0x01A carries the action category at 0x0A and the action id at 0x0C. These are
-- the same numbers GearSwap maps /ma, /ws and /ja to; the skill ids are the client's own, named
-- the way GearSwap libraries key sets.midcast.
local PHASE_MAGIC, PHASE_WS, PHASE_JA = 3, 7, 9
-- BEGIN spell mode groups -- tests/spell_groups_test.py extracts this region and runs it.
local MIDCAST_SKILL = {
    [32] = 'Divine Magic', [33] = 'Healing Magic', [34] = 'Enhancing Magic',
    [35] = 'Enfeebling Magic', [36] = 'Elemental Magic', [37] = 'Dark Magic',
    [38] = 'Summoning Magic', [39] = 'Ninjutsu', [40] = 'Singing',
    [41] = 'String Instrument', [42] = 'Wind Instrument', [43] = 'Blue Magic',
    [44] = 'Geomancy', [45] = 'Handbell',
}

-- Enfeebling Magic is not one build.  BG Wiki's Community Red Mage Guide splits the spells
-- by what decides their value: Enfeebling Magic Skill (Frazzle III, Distract III, Poison),
-- landing / Magic Accuracy (Frazzle II, Distract II, Dia, Sleep, Bind, Break, Silence),
-- dMND (Slow II, Paralyze II, Addle II), dINT (Blind II), Macc + potency (Gravity) and the
-- non-scaling spells that cannot be resisted at all (Dispel, Inundation).  Each kind owns a
-- category, so the Gear page can bind one set per kind and the plan can wear the right one
-- for the spell being cast instead of one blanket "enfeebling" set.
local ENFEEBLE_KINDS = {
    skill = {
        key = 'skill', label = 'Skill', short = 'Skill', category = 'enfeebles_skill',
        detail = 'Enfeebling Magic Skill carries the potency: Frazzle III, Distract III, Poison, Poison II.',
    },
    macc = {
        key = 'macc', label = 'Macc / landing', short = 'Macc', category = 'enfeebles_macc',
        detail = 'All-or-nothing landing: Frazzle II, Distract II, Dia, Sleep, Bind, Break, Silence.',
    },
    duration = {
        key = 'duration', label = 'Duration', short = 'Dur', category = 'enfeebles_duration',
        detail = 'Crowd control where the timer matters: Sleep, Sleep II, Bind, Break, Silence.',
    },
    hybrid = {
        key = 'hybrid', label = 'Macc + potency', short = 'Hybrid', category = 'enfeebles_hybrid',
        detail = 'Magic Accuracy and Enfeebling potency together: Gravity and Gravity II.',
    },
    mnd = {
        key = 'mnd', label = 'MND', short = 'MND', category = 'enfeebles_mnd',
        detail = 'dMND sets the potency: Slow II, Paralyze II, Addle II.',
    },
    int = {
        key = 'int', label = 'INT', short = 'INT', category = 'enfeebles_int',
        detail = 'dINT sets the potency: Blind II.',
    },
    general = {
        key = 'general', label = 'General', short = 'Gen', category = 'enfeebles_general',
        detail = 'Nothing to scale and nothing to resist: Dispel, Dispelga, Inundation.',
    },
}
local ENFEEBLE_KIND_ORDER = {
    'skill', 'macc', 'duration', 'hybrid', 'mnd', 'int', 'general',
}
-- A duration spell still needs to land, so it uses the Macc set until a Duration set is
-- picked.  The guide's "MAcc. & Duration" build is exactly that: one set for both.
local ENFEEBLE_KIND_FALLBACK = { duration = 'macc' }

-- Spell name (lowercase) -> kind.  Spells not named here but in Enfeebling Magic fall back
-- to macc: landing is the one thing every debuff needs, and the guide publishes no other
-- build for them (Virus, for example).
local ENFEEBLE_KIND_SPELLS = {
    ['frazzle iii'] = 'skill', ['distract iii'] = 'skill',
    ['poison'] = 'skill', ['poison ii'] = 'skill', ['poison iii'] = 'skill',
    ['poison iv'] = 'skill', ['poison v'] = 'skill',
    ['poisonga'] = 'skill', ['poisonga ii'] = 'skill', ['poisonga iii'] = 'skill',
    ['poisonga iv'] = 'skill', ['poisonga v'] = 'skill',
    ['frazzle'] = 'macc', ['frazzle ii'] = 'macc',
    ['distract'] = 'macc', ['distract ii'] = 'macc',
    ['dia'] = 'macc', ['dia ii'] = 'macc', ['dia iii'] = 'macc',
    ['dia iv'] = 'macc', ['dia v'] = 'macc',
    ['diaga'] = 'macc', ['diaga ii'] = 'macc', ['diaga iii'] = 'macc',
    ['diaga iv'] = 'macc', ['diaga v'] = 'macc',
    ['virus'] = 'macc',
    ['sleep'] = 'duration', ['sleep ii'] = 'duration',
    ['sleepga'] = 'duration', ['sleepga ii'] = 'duration',
    ['bind'] = 'duration', ['bindga'] = 'duration',
    ['break'] = 'duration', ['breakga'] = 'duration',
    ['silence'] = 'duration', ['silencega'] = 'duration',
    ['gravity'] = 'hybrid', ['gravity ii'] = 'hybrid', ['graviga'] = 'hybrid',
    ['slow'] = 'mnd', ['slow ii'] = 'mnd', ['slowga'] = 'mnd',
    ['paralyze'] = 'mnd', ['paralyze ii'] = 'mnd', ['paralyga'] = 'mnd',
    ['addle'] = 'mnd', ['addle ii'] = 'mnd',
    ['blind'] = 'int', ['blind ii'] = 'int', ['blindga'] = 'int',
    ['dispel'] = 'general', ['dispelga'] = 'general', ['inundation'] = 'general',
}

-- Enhancing Magic kinds.  The guide splits the buffs by what the set is for: Aquaveil
-- wants spell-interruption gear, Stoneskin wants potency, the Bar- / Haste / Flurry /
-- Blink line wants duration (the party build, or the self build while Composure triples
-- self-cast duration), and the rest - Protect, Shell, Regen, Refresh, Temper, the storms,
-- the spikes, the travel spells - just needs the generic enhancing pieces.
local ENHANCING_KINDS = {
    skill = {
        key = 'skill', label = 'Skill (Aquaveil)', short = 'SIRD', category = 'enhancing_skill',
        detail = 'Aquaveil: spell interruption rate down, so the cast survives under fire.',
    },
    stoneskin = {
        key = 'stoneskin', label = 'Stoneskin', short = 'Stone', category = 'enhancing_stoneskin',
        detail = 'Stoneskin: Enhancing skill and MND push the absorb past its base cap.',
    },
    -- The Community Paladin Guide builds Phalanx and Reprisal as their own sets: Phalanx
    -- reads Enhancing Magic skill plus the Phalanx+ pieces, Reprisal enmity and duration.
    phalanx = {
        key = 'phalanx', label = 'Phalanx', short = 'Phalanx', category = 'enhancing_phalanx',
        jobs = { 5, 7, 22 },
        detail = "Phalanx: Enhancing skill and the Phalanx+ pieces, the guide's Max Self build.",
    },
    reprisal = {
        key = 'reprisal', label = 'Reprisal', short = 'Reprisal',
        category = 'enhancing_reprisal', jobs = { 7 },
        detail = 'Reprisal: enmity and duration first, with the block rate riding on the shield.',
    },
    duration = {
        key = 'duration', label = 'Duration', short = 'Dur', category = 'enhancing_duration',
        detail = 'Barspell, Blink, Haste, Haste II, Flurry and Flurry II: duration first.',
    },
    general = {
        key = 'general', label = 'General', short = 'Gen', category = 'enhancing_general',
        detail = 'Protect, Shell, Regen, Refresh, Temper and the rest: the generic enhancing set.',
    },
}
local ENHANCING_KIND_ORDER = {
    'skill', 'stoneskin', 'phalanx', 'reprisal', 'duration', 'general',
}

-- The Gear page's spell groups and the modes each can be in.  The launcher configures one
-- set per mode; the armed mode decides which one the plan wears.  A spell belongs to one
-- group, so the same category rule cannot be claimed twice.
local SPELL_GROUPS = {
    enfeebles = {
        key = 'enfeebles', label = 'Enfeebles', short = 'Enf', default = 'auto',
        -- Auto wears the set for the spell's own kind.  Arming another mode forces every
        -- Enfeebling Magic spell through that one set (the old macc / duration behaviour);
        -- //modes swaps the same list at the in-game HUD.
        modes = {
            {
                key = 'auto', label = 'Auto — by spell type', short = 'Auto',
                detail = 'Wear the kind row for each spell (Skill, Macc, MND, INT, Hybrid, General).',
            },
            {
                key = 'skill', label = 'Skill', short = 'Skill', category = 'enfeebles_skill',
                detail = 'Force every enfeebling spell through the Skill build.',
            },
            {
                key = 'macc', label = 'Macc / landing', short = 'Macc', category = 'enfeebles_macc',
                detail = 'Force every enfeebling spell through the Macc build.',
            },
            {
                key = 'duration', label = 'Duration', short = 'Dur', category = 'enfeebles_duration',
                detail = 'Force every enfeebling spell through the Duration build.',
            },
            {
                key = 'hybrid', label = 'Macc + potency', short = 'Hybrid', category = 'enfeebles_hybrid',
                detail = 'Force every enfeebling spell through the Macc + potency build.',
            },
            {
                key = 'mnd', label = 'MND', short = 'MND', category = 'enfeebles_mnd',
                detail = 'Force every enfeebling spell through the MND build.',
            },
            {
                key = 'int', label = 'INT', short = 'INT', category = 'enfeebles_int',
                detail = 'Force every enfeebling spell through the INT build.',
            },
            {
                key = 'general', label = 'General', short = 'Gen', category = 'enfeebles_general',
                detail = 'Force every enfeebling spell through the non-scaling build.',
            },
        },
        kinds = {
            ENFEEBLE_KINDS.skill, ENFEEBLE_KINDS.macc, ENFEEBLE_KINDS.duration,
            ENFEEBLE_KINDS.hybrid, ENFEEBLE_KINDS.mnd, ENFEEBLE_KINDS.int,
            ENFEEBLE_KINDS.general,
        },
        -- A live status, not an armed mode: while Saboteur is up the plan adds a conditional
        -- rule for every enfeebling spell.  merge = true keeps the spell's kind set and lays
        -- the overlay set (the hands) on top, so one small set covers all seven kinds.
        autos = {
            {
                key = 'saboteur', label = 'Saboteur', short = 'Sab',
                category = 'enfeebles_saboteur', buff = 454, merge = true,
                detail = 'While Saboteur is up, every enfeebling cast swaps the hands to Lethargy Gantherots.',
            },
        },
    },
    enhancing = {
        key = 'enhancing', label = 'Enhancing / buffs', short = 'Enh', default = 'auto',
        -- Auto wears the set for the spell's own kind.  Arming a kind forces every
        -- Enhancing Magic spell through that set, and //modes swaps the same list.
        modes = {
            {
                key = 'auto', label = 'Auto — by spell type', short = 'Auto',
                detail = 'Wear the kind row for each spell (Skill, Stoneskin, Duration, General).',
            },
            {
                key = 'skill', label = 'Skill (Aquaveil)', short = 'SIRD',
                category = 'enhancing_skill',
                detail = 'Force every enhancing spell through the Aquaveil SIRD build.',
            },
            {
                key = 'stoneskin', label = 'Stoneskin', short = 'Stone',
                category = 'enhancing_stoneskin',
                detail = 'Force every enhancing spell through the Stoneskin build.',
            },
            {
                key = 'duration', label = 'Duration', short = 'Dur',
                category = 'enhancing_duration',
                detail = 'Force every enhancing spell through the duration build.',
            },
            {
                key = 'general', label = 'General', short = 'Gen',
                category = 'enhancing_general',
                detail = 'Force every enhancing spell through the generic enhancing set.',
            },
        },
        kinds = {
            ENHANCING_KINDS.skill, ENHANCING_KINDS.stoneskin,
            ENHANCING_KINDS.phalanx, ENHANCING_KINDS.reprisal,
            ENHANCING_KINDS.duration, ENHANCING_KINDS.general,
        },
        -- A live status, not an armed mode: while Composure is up the duration spells wear
        -- the self build (Composure triples enhancing duration on self); the party build is
        -- the fallback.  only_kind keeps the rule off Aquaveil/Stoneskin/General.
        autos = {
            {
                key = 'composure', label = 'Composure', short = 'Comp',
                category = 'enhancing_duration_self', buff = 419, only_kind = 'duration',
                detail = 'While Composure is up, the duration spells wear the self duration set.',
            },
        },
    },
    enspells = {
        key = 'enspells', label = 'Enspells', short = 'Ensp', default = 'damage',
        modes = {
            {
                key = 'damage', label = 'Enspell damage', short = 'Dmg', category = 'enspells',
                detail = 'Enhancing Magic Skill / MND set for casting the six enspells.',
            },
            {
                key = 'nodamage', label = 'Enspell no dmg', short = 'NoDmg',
                category = 'enspells_no_damage',
                detail = 'The enspell set to wear when the damage build is not wanted.',
            },
        },
    },
    curing = {
        key = 'curing', label = 'Curing / healing', short = 'Cure', default = 'potency',
        modes = {
            { key = 'potency', label = 'Potency', short = 'Pot', category = 'cure_potency' },
            { key = 'cast', label = 'Cast time', short = 'Cast', category = 'cure_cast' },
        },
    },
    nuking = {
        key = 'nuking', label = 'Nuking', short = 'Nuke', default = 'mab',
        modes = {
            { key = 'mab', label = 'Magic Attack', short = 'MAB', category = 'nuke_mab' },
            { key = 'mdmg', label = 'Magic damage', short = 'M.Dmg', category = 'nuke_mdmg' },
        },
        -- Not an armed mode: the engine wears this set only while a magic burst window is
        -- open on the current target, and the armed mode's set otherwise.
        auto = {
            key = 'magic_burst', label = 'Magic Burst', short = 'Magic Burst', category = 'nuke_mb',
            detail = 'Worn for Elemental Magic while a Magic Burst window is open.',
        },
        autos = {
            {
                key = 'immanence', label = 'Immanence', short = 'Immanence',
                category = 'nuke_immanence', buff = 470,
                detail = 'Worn for Elemental Magic while Immanence is active.',
            },
        },
    },
    helix = {
        key = 'helix', label = 'Helixes', short = 'Helix', default = 'mab',
        modes = {
            { key = 'mab', label = 'Magic Attack', short = 'MAB', category = 'helix_magic' },
            { key = 'duration', label = 'Duration', short = 'Dur', category = 'helix_duration' },
        },
        autos = {
            {
                key = 'immanence', label = 'Immanence', short = 'Immanence',
                category = 'helix_immanence', buff = 470,
                detail = 'Worn for helix spells while Immanence is active.',
            },
        },
    },
    dark = {
        key = 'dark', label = 'Dark Magic', short = 'Dark', default = 'potency',
        modes = {
            { key = 'potency', label = 'Potency', short = 'Pot', category = 'dark_potency' },
            { key = 'macc', label = 'Macc / landing', short = 'Macc', category = 'dark_macc' },
            { key = 'duration', label = 'Duration', short = 'Dur', category = 'dark_duration' },
        },
    },
    divine = {
        key = 'divine', label = 'Divine Magic', short = 'Divine', default = 'auto',
        -- The Community Paladin Guide builds Flash as a magic-enmity set (Enmity and Fast
        -- Cast), not a nuke, so Divine Magic splits like Enfeebles: Auto follows each
        -- spell's own kind and arming a mode forces every Divine Magic spell through it.
        modes = {
            {
                key = 'auto', label = 'Auto — by spell type', short = 'Auto',
                detail = 'Wear the kind row for each spell (Banish/Holy, Flash, Macc).',
            },
            {
                key = 'mab', label = 'Magic Attack', short = 'MAB', category = 'divine_mab',
                detail = 'Force every Divine Magic spell through the Banish / Holy build.',
            },
            {
                key = 'flash', label = 'Flash (enmity)', short = 'Flash',
                category = 'divine_flash',
                detail = 'Force every Divine Magic spell through the Flash enmity build.',
            },
            {
                key = 'macc', label = 'Macc / landing', short = 'Macc', category = 'divine_macc',
                detail = 'Force every Divine Magic spell through the landing build.',
            },
        },
        -- A map so spell_categories can name the kind's category; the ordered kinds list is
        -- filled from it below and is what the Gear page renders.
        kind_map = {
            mab = {
                key = 'mab', label = 'Banish / Holy', short = 'MAB', category = 'divine_mab',
                detail = 'The Banish and Holy lines: Magic Attack and MND carry the damage.',
            },
            flash = {
                key = 'flash', label = 'Flash', short = 'Flash', category = 'divine_flash',
                detail = "Flash reads enmity: the guide's Enmity / Fast Cast build.",
            },
            macc = {
                key = 'macc', label = 'Macc / landing', short = 'Macc', category = 'divine_macc',
                detail = 'Repose and any Divine Magic spell whose landing has to win.',
            },
        },
        kinds = {},
    },
    songs = {
        key = 'songs', label = 'Bard songs', short = 'Song', default = 'duration',
        modes = {
            { key = 'duration', label = 'Song duration', short = 'Dur', category = 'song_duration' },
            { key = 'potency', label = 'Song potency', short = 'Pot', category = 'song_potency' },
        },
    },
    blue = {
        key = 'blue', label = 'Blue Magic', short = 'Blue', default = 'mab',
        modes = {
            { key = 'mab', label = 'Magic Attack', short = 'MAB', category = 'blue_mab' },
            { key = 'macc', label = 'Magic Accuracy', short = 'Macc', category = 'blue_macc' },
        },
    },
    ninjutsu = {
        key = 'ninjutsu', label = 'Ninjutsu', short = 'Nin', default = 'macc',
        modes = {
            { key = 'macc', label = 'Magic Accuracy', short = 'Macc', category = 'ninjutsu_macc' },
            { key = 'damage', label = 'Ninjutsu damage', short = 'Dmg', category = 'ninjutsu_damage' },
        },
    },
}
-- The Divine Magic card's rows, in order.  Filled here instead of in the literal above so
-- the kind table can stay a keyed map (spell_categories looks a kind up by key).
SPELL_GROUPS.divine.kinds = {
    SPELL_GROUPS.divine.kind_map.mab, SPELL_GROUPS.divine.kind_map.flash,
    SPELL_GROUPS.divine.kind_map.macc,
}
local SPELL_GROUP_ORDER = {
    'enfeebles', 'enhancing', 'enspells', 'curing', 'nuking', 'helix', 'dark', 'divine',
    'songs', 'blue', 'ninjutsu',
}
local function spell_name(spell)
    local name = spell and spell.name
    if type(name) == 'table' then name = name.en or name[2] or name[1] end
    return type(name) == 'string' and name or ''
end

-- The one group a spell belongs to.  Helix is checked first because a helix is also an
-- Elemental Magic spell.  Enspells (Enfire, Enblizzard, ... and their IIs) are Enhancing Magic
-- but cast from the Enhancing Magic Skill set, so they get their own group before the skill
-- fallback; Enlight and Endark stay there although their own skill is Divine / Dark Magic.
-- Everything else follows its skill.
local ENSPELL_BASE = {
    enfire = true, enblizzard = true, enaero = true, enstone = true, enthunder = true,
    enwater = true, enlight = true, endark = true,
}
local function spell_group(spell)
    if not spell then return nil end
    local name = spell_name(spell):lower()
    if name:find('helix', 1, true) then return 'helix' end
    local base = name:match('^(%a+)') or ''
    if ENSPELL_BASE[base] then return 'enspells' end
    local skill = MIDCAST_SKILL[spell.skill]
    if skill == 'Singing' or skill == 'String Instrument' or skill == 'Wind Instrument' then
        return 'songs'
    end
    if skill == 'Enfeebling Magic' then return 'enfeebles' end
    if skill == 'Enhancing Magic' then return 'enhancing' end
    if skill == 'Healing Magic' then return 'curing' end
    if skill == 'Elemental Magic' then return 'nuking' end
    if skill == 'Dark Magic' then return 'dark' end
    if skill == 'Divine Magic' then return 'divine' end
    if skill == 'Blue Magic' then return 'blue' end
    if skill == 'Ninjutsu' then return 'ninjutsu' end
    return nil
end

-- The enfeebling kind a spell belongs to, or nil when it is not Enfeebling Magic.  Unknown
-- enfeebles land on macc, the one build every debuff can use.
local function spell_enfeebling_kind(spell)
    if not spell or tonumber(spell.skill) ~= 35 then return nil end
    local name = spell_name(spell):lower()
    return ENFEEBLE_KIND_SPELLS[name] or 'macc'
end

-- The Enhancing Magic spell's kind.  Every skill-34 spell gets one; unknown ones are
-- General, which falls back to midcast.Enhancing Magic.
local function spell_enhancing_kind(spell)
    if not spell or tonumber(spell.skill) ~= 34 then return nil end
    local name = spell_name(spell):lower()
    if name:find('^aquaveil') then return 'skill' end
    if name:find('^stoneskin') then return 'stoneskin' end
    -- Phalanx / Phalanx II and Reprisal: the Community Paladin Guide builds these as their
    -- own sets; the launcher's rows for them are scoped to the jobs that learn the spell.
    if name == 'phalanx' or name == 'phalanx ii' then return 'phalanx' end
    if name:find('^reprisal') then return 'reprisal' end
    -- The guide's "Enhancing Duration Sets" line: Barspell (every Bar- and Bar-ra spell),
    -- Blink, Haste/Hastega and Flurry.  Protect/Shell/Reraise are not in it; they need
    -- neither duration nor the enhancing skill once capped.
    if name == 'blink' or name:find('^bar') or name:find('^haste')
        or name:find('^flurry') then
        return 'duration'
    end
    return 'general'
end

-- The category whose set should be worn for one spell's kind, walking the fallback chain
-- (Duration -> Macc) until a category has a set in the plan.  Returns nil when no kind set
-- is configured, which lets the library's plain midcast.Enfeebling Magic apply instead.
local function spell_enfeebling_category(spell, category_override)
    local kind = spell_enfeebling_kind(spell)
    local seen = {}
    while kind and not seen[kind] do
        seen[kind] = true
        local entry = ENFEEBLE_KINDS[kind]
        if entry and category_override[entry.category] then return entry.category end
        kind = ENFEEBLE_KIND_FALLBACK[kind]
    end
    return nil
end

-- The kind key a spell has in its group, for the mode/auto rules and the Gear page.
local function spell_kind_key(group_key, spell)
    if group_key == 'enfeebles' then return spell_enfeebling_kind(spell) end
    if group_key == 'enhancing' then return spell_enhancing_kind(spell) end
    -- Divine Magic: Flash owns the enmity set, Repose the landing set, and every damage
    -- spell (Banish, Banishga, Holy) the Magic Attack set.
    if group_key == 'divine' then
        if not spell or tonumber(spell.skill) ~= 32 then return nil end
        local name = spell_name(spell):lower()
        if name == 'flash' then return 'flash' end
        if name == 'repose' then return 'macc' end
        return 'mab'
    end
    return nil
end

-- The set for one enhancing spell's kind, or nil when the kind has no set in the plan
-- (the library's midcast.Enhancing Magic then applies through the skill fallback).
local function spell_enhancing_category(spell, category_override)
    local kind = spell_enhancing_kind(spell)
    local entry = kind and ENHANCING_KINDS[kind]
    if entry and category_override[entry.category] then return entry.category end
    return nil
end

-- The category the plan uses for a spell.  Enfeebles and Enhancing in Auto follow the
-- spell's kind; arming one of the group's modes forces that mode's set instead.  Every other
-- group keeps its single armed mode.
local function spell_cast_category(group_key, spell, mode, category_override)
    if group_key == 'enfeebles' then
        if mode and mode.key ~= 'auto' then return mode.category end
        return spell_enfeebling_category(spell, category_override)
    end
    if group_key == 'enhancing' then
        if mode and mode.key ~= 'auto' then return mode.category end
        return spell_enhancing_category(spell, category_override)
    end
    if group_key == 'divine' then
        if mode and mode.key ~= 'auto' then return mode.category end
        local kind = spell_kind_key('divine', spell)
        local entry = kind and SPELL_GROUPS.divine.kind_map[kind]
        if entry and category_override[entry.category] then return entry.category end
        return nil
    end
    return mode and mode.category or nil
end

-- Every category a spell claims, for job_spells and the Gear page's spell cards: the group
-- first, then the kind (`enfeebles_mnd`, `enhancing_duration`, ...) when it has one.
local function spell_categories(spell)
    local group = spell_group(spell)
    local out = {}
    if group then out[#out + 1] = group end
    local kind = spell_kind_key(group, spell)
    if kind then
        local entry = group == 'enfeebles' and ENFEEBLE_KINDS[kind]
            or group == 'enhancing' and ENHANCING_KINDS[kind]
            or group == 'divine' and SPELL_GROUPS.divine.kind_map[kind]
        if entry then out[#out + 1] = entry.category end
    end
    return out
end
-- END spell mode groups

local function group_mode(group_key, mode_key)
    local group = SPELL_GROUPS[group_key]
    if not group then return nil end
    for _, mode in ipairs(group.modes) do
        if mode.key == mode_key then return mode end
    end
    return nil
end

-- Old plans have only category picks.  Prefer the armed mode, then the one configured face of
-- a pair, then the group's default.  The launcher sends spell_modes; this keeps a hand-written
-- plan working too.
local function normalize_spell_modes(requested, category_override)
    local out = {}
    for _, group_key in ipairs(SPELL_GROUP_ORDER) do
        local group = SPELL_GROUPS[group_key]
        local chosen = type(requested) == 'table' and tostring(requested[group_key] or '') or ''
        if not group_mode(group_key, chosen) then chosen = nil end
        if not chosen then
            local configured = {}
            for _, mode in ipairs(group.modes) do
                if category_override[mode.category] then configured[#configured + 1] = mode.key end
            end
            chosen = #configured == 1 and configured[1] or group.default
        end
        out[group_key] = chosen
    end
    return out
end

local function mode_label(group_key, mode_key)
    local mode = group_mode(group_key, mode_key)
    return mode and mode.label or tostring(mode_key)
end

local function mode_short(group_key, mode_key)
    local mode = group_mode(group_key, mode_key)
    return mode and mode.short or tostring(mode_key)
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
    local worn = worn_items()
    local worn_ids = {}
    for _, id in pairs(worn) do
        if id and id ~= 0 then worn_ids[id] = true end
    end
    local n = 0
    for _, e in ipairs(equips) do
        -- The phase engine hands back the whole state set; sending a piece that is already
        -- in that slot (or the other ring/ear, where it is unique) makes the client print
        -- "That item is already equipped." once per piece, every time the movement/idle
        -- state laps.  Only send real changes.
        local item_id = game.item(e[3], e[1], 'Id') or 0
        if item_id ~= 0 and not worn_ids[item_id] then
            xi.packets.inject(true, equip_packet(e[3], e[1], e[2]))
            n = n + 1
        end
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
        phase_job_at = xi.clock()
        return
    end
    phase_job_seen = nil
end

-- Movement is read from the client's own position, which is noisy: a still character's
-- samples wobble by a fraction of a centimetre, and the movement set is a whole gear batch.
-- Require one yalm of horizontal travel from where the character last stood before the
-- movement set goes on, and only take it off after MOVE_STOP seconds without a real step.
-- The clock matters too: os.clock() is process CPU time, and with the render/network threads
-- busy it runs several times faster than wall time, which turned the 1.2 s stop into a few
-- hundred milliseconds and made a standing character flap in and out of the movement set.
local MOVE_STEP = 1.0       -- yalms of travel from the idle spot that mean "walking"
local MOVE_SAMPLE = 0.02    -- one sample (every 40 ms) at least this large is real motion
local MOVE_STOP = 1.2       -- seconds without motion before the idle set comes back

-- Nightingale (347) + Troubadour (348), the Bard's Nitro window.  A song may take its
-- instrument off a pinned weapon slot only while both are up; the host restores the locked
-- hand when the song resolves.  Read every fifth of a second: the buff list is a fresh table
-- and watch_phase runs at 25 Hz.
local NITRO_BUFFS = { 347, 348 }
local nitro_at, nitro_on = -1, false
local function brd_nitro_on()
    local now = xi.clock()
    if now - nitro_at < 0.2 then return nitro_on end
    nitro_at, nitro_on = now, false
    if (game.party_member(0, 'MainJob') or 0) ~= 10 then return false end
    local ok, buffs = pcall(function() return game.player('Buffs') end)
    if not ok or type(buffs) ~= 'table' then return false end
    local seen = {}
    for _, raw in ipairs(buffs) do seen[tonumber(raw) or 0] = true end
    nitro_on = seen[NITRO_BUFFS[1]] == true and seen[NITRO_BUFFS[2]] == true
    return nitro_on
end

-- phase_burst_open is defined below, beside the skillchain tables it reads: whether a magic burst
-- window is open on the player's current target.  watch_phase pushes it to the phase engine every
-- tick, so a nuke sent inside the window wears the Nuking card's Magic Burst set.  It is a
-- global (not a local) because the main chunk and hud_init are already near LuaJIT's 200-local
-- limit.

local function watch_phase()
    local moving, still_since = false, xi.clock()
    local last_x, last_z, origin_x, origin_z
    while phase_watch do
        if phase_job_seen and xi.clock() >= phase_job_at + 1.5 then reload_for_job(phase_job_seen) end
        if xi.phase.nitro then xi.phase.nitro(brd_nitro_on()) end
        if xi.phase.burst and phase_burst_open then
            xi.phase.burst(phase_burst_open())
        end
        -- Conditional gear sets ("Victory Smite (Impetus)"): the phase engine matches a rule
        -- against the player's live buff ids, but it cannot read guest memory on the network
        -- thread.  Push the list here every frame, and only when it actually changes: Impetus
        -- can be pressed and a WS sent in the same second.
        if xi.phase.buffs and phase_plan then
            local now = xi.clock()
            if now > (phase_plan.buff_at or -1) then
                phase_plan.buff_at = now
                local ok, buffs = pcall(function() return game.player('Buffs') end)
                if ok and type(buffs) == 'table' then
                    local ids = {}
                    for _, raw in ipairs(buffs) do
                        local id = tonumber(raw) or 0
                        if id > 0 and id ~= 255 and id ~= 0xFFFF then ids[#ids + 1] = id end
                    end
                    table.sort(ids)
                    local signature = table.concat(ids, ',')
                    if phase_plan.buff_sig ~= signature then
                        phase_plan.buff_sig = signature
                        xi.phase.buffs(ids)
                    end
                end
            end
        end
        local index = game.player_index() or 0
        local x = index > 0 and game.entity(index, 'Movement.LocalPosition.X') or nil
        local y = index > 0 and game.entity(index, 'Movement.LocalPosition.Y') or nil
        local z = index > 0 and game.entity(index, 'Movement.LocalPosition.Z') or nil
        if x and y and z then
            local now = xi.clock()
            if not last_x then
                last_x, last_z, origin_x, origin_z = x, z, x, z
                still_since = now
            else
                -- Horizontal travel only: Y is height, and a slope is not a step.
                local step = math.abs(x - last_x) + math.abs(z - last_z)
                last_x, last_z = x, z
                if step > 20 then
                    -- A zone line or a teleport moves the character far in one sample; the
                    -- engine resets the stance on zone-in, so do not count it as walking.
                    moving, origin_x, origin_z = false, x, z
                    still_since = now
                else
                    if step > MOVE_SAMPLE then still_since = now end
                    if not moving then
                        local dx, dz = x - origin_x, z - origin_z
                        if dx * dx + dz * dz >= MOVE_STEP * MOVE_STEP then
                            moving = true
                            still_since = now
                        end
                    elseif now - still_since > MOVE_STOP then
                        -- Moving gear goes on at the first real yalm, but comes off only
                        -- after the character has really stopped.  A following box stutters
                        -- in and out of a walk; each stutter used to cost a whole equipment
                        -- batch, and six boxes flapped in lockstep.
                        moving = false
                        origin_x, origin_z = x, z
                    end
                end
            end
            inject_plan(xi.phase.moving(moving))
        else
            last_x = nil
        end
        -- The zone-in and job packets only set state; the set for it goes out here, once the
        -- client has had a moment to load the new zone or the new job's gear.
        inject_plan(xi.phase.pending())
        -- A refused job ability (recast, range, no target) never sends 0x028, so the
        -- held action's set would otherwise stay on until another server packet.  Restore
        -- it from the watch loop once the category's timeout passes.
        if xi.phase.stale then inject_plan(xi.phase.stale()) end
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
                -- A zone-in is the last reliable moment before a logout: flush the
                -- dragged window positions so they survive the next login.
                if hud and hud.save_now then hud.save_now() end
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
                        phase_job_seen, phase_job_at = job, xi.clock()
                    end
                end
            end
        end
    end)
end

-- Per-family maximum song sets.  Loughnashade +4 and Mnbw. Whistle +1 +3 are
-- the common +7; these library sets add the last +1/+2 from JSE/Mousai pieces.
-- Ballad and Scherzo deliberately have no entry: their only family piece is on
-- legs/feet and would cost more raw 454 duration than the Song+ point returns.
local SONG_FAMILY_SETS = {
    paeon = 'midcast.SongPaeon',
    lullaby = 'midcast.SongLullaby',
    etude = 'midcast.SongEtude',
    carol = 'midcast.SongCarol',
    threnody = 'midcast.SongThrenody',
    minne = 'midcast.SongMinne',
    mambo = 'midcast.SongMambo',
    madrigal = 'midcast.SongMadrigal',
    minuet = 'midcast.SongMinuet',
    march = 'midcast.SongMarch',
}

local function song_family_set(name)
    local key = tostring(name or ''):lower()
    if key:find('honor march', 1, true) or key:find('aria of passion', 1, true) then
        return nil
    end
    for family, path in pairs(SONG_FAMILY_SETS) do
        if key:find(family, 1, true) then return path end
    end
    return nil
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
    if type(sets) ~= 'table' then sets = gearswap_sets(a) end
    local by_id, set_list, set_names, set_tables, rules = bag_index(), {}, {}, {}, {}
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
        -- Job-point spells do not have an ordinary level: the client stores 100/550/1200 and
        -- names the jobs that can learn them in job_point_mask. A level-99 main job sees them in
        -- its magic menu, so include them for the main job (never a support job).
        local main_job, main_level = spell_jobs[1][1], spell_jobs[1][2]
        if main_job > 0 and main_level >= 99 then
            local mask = tonumber(spell.job_point_mask) or 0
            if mask > 0 and math.floor(mask / (2 ^ main_job)) % 2 == 1 then return true end
        end
        return false
    end
    local function add_set(t, name)
        if not is_equip_set(t) then return nil end
        local equips = phase_equips(t, by_id)
        if #equips == 0 then return nil end
        set_list[#set_list + 1] = equips
        set_names[#set_names + 1] = name or ''
        set_tables[#set_tables + 1] = t
        return #set_list
    end
    local function path_set(path, label)
        if type(path) ~= 'string' or path == '' then return nil end
        local t = set_at(sets, path)
        if type(t) ~= 'table' then return nil end
        return add_set(t, label or path)
    end

    -- A buff-conditional overlay: the overlay set's slots win, the base set fills the rest.
    -- "Enfeebling Magic Saboteur" is only the hands, so one set covers every kind.  Identical
    -- (base, overlay) pairs share a plan set instead of one per spell.
    local merged_sets = {}
    local function merged_set(base_index, overlay_index, label)
        if not base_index or not overlay_index then return nil end
        local key = tostring(base_index) .. '|' .. tostring(overlay_index)
        if merged_sets[key] then return merged_sets[key] end
        local base, overlay = set_tables[base_index], set_tables[overlay_index]
        if type(overlay) ~= 'table' then return nil end
        local out = {}
        for slot, item in pairs(base or {}) do out[slot] = item end
        for slot, item in pairs(overlay) do out[slot] = item end
        local name = set_names[base_index] or 'set'
        if type(label) == 'string' and label ~= '' then name = name .. ' (' .. label .. ')' end
        local index = add_set(out, name)
        if index then merged_sets[key] = index end
        return index
    end

    -- Weaponskills: a per-WS override wins over the library's sets.WS.<name>; the default set
    -- is the fallback for a WS with no card of its own.  A trailing "(Buff, Buff)" in the set
    -- name makes the set conditional: Victory Smite (Impetus) is worn only while every named
    -- buff is up.  The phase engine picks the most specific matching rule, so a plain
    -- Victory Smite card stays the no-buff fallback.
    local ws_override = {}
    if type(a.ws_overrides) == 'table' then
        for name, path in pairs(a.ws_overrides) do
            local index = path_set(path, 'WS.' .. tostring(name))
            if index then ws_override[tostring(name)] = index end
        end
    end

    -- Buff names in the condition are the client's own status names, case-insensitive.  Cache
    -- the id table on xi: the plan is rebuilt on every library/config push, and control.lua is at
    -- Lua's chunk-local limit, so this cannot be another chunk-level local.
    if not xi.phase_buff_names then
        local names = {}
        local ok, ids = pcall(res.status_ids)
        if ok and type(ids) == 'table' then
            for _, id in ipairs(ids) do
                local status = res.status(id)
                if status then
                    local text = status.name_utf8 and status.name_utf8.en
                        or (type(status.name) == 'table' and status.name.en) or nil
                    for _, value in ipairs({ text or '', status.log_name or '' }) do
                        local key = tostring(value):lower():match('^%s*(.-)%s*$')
                        key = key and key:gsub('^"(.*)"$', '%1') or ''
                        if key ~= '' and not names[key] then names[key] = id end
                    end
                end
            end
        end
        if next(names) ~= nil then xi.phase_buff_names = names end
    end

    local function ws_split(raw)
        local text = tostring(raw or '')
        local base, condition = text:match('^(.-)%s*%(([^()]*)%)%s*$')
        if not base or base == '' then return text, {} end
        local labels = {}
        for part in condition:gmatch('[^,]+') do
            local label = part:match('^%s*(.-)%s*$'):gsub('^"(.*)"$', '%1')
            label = label:match('^%s*(.-)%s*$')
            if label ~= '' then labels[#labels + 1] = label end
        end
        if #labels == 0 then return text, {} end
        if #labels > 8 then
            xi.log('phase: WS set "' .. text .. '" names more than 8 buffs; ignored')
            return text, {}
        end
        return base, labels
    end

    local function ws_rule(raw, index)
        local base, labels = ws_split(raw)
        local ability = res.ability_by_name(base)
        if not ability or not index then return false end
        local buffs = {}
        for _, label in ipairs(labels) do
            local id = xi.phase_buff_names and xi.phase_buff_names[label:lower()]
            if not id then
                xi.log('phase: WS set "' .. tostring(raw) ..
                    '" names an unknown buff "' .. label .. '"')
                return false
            end
            buffs[#buffs + 1] = id
        end
        local rule = { category = PHASE_WS, action = ability.id, pre = index }
        if #buffs > 0 then rule.buffs = buffs end
        rules[#rules + 1] = rule
        return true
    end

    local ws_done, ws_names, ws_sets = {}, {}, {}
    if type(sets.WS) == 'table' then
        for name, value in pairs(sets.WS) do
            local raw = tostring(name)
            ws_names[#ws_names + 1] = raw
            ws_sets[raw] = value
        end
    end
    -- Sorted so two equally specific variants pick the same rule on every push.
    table.sort(ws_names)
    for _, raw in ipairs(ws_names) do
        ws_done[raw] = true
        ws_rule(raw, ws_override[raw] or add_set(ws_sets[raw], 'WS.' .. raw))
    end
    local override_names = {}
    for name in pairs(ws_override) do
        if not ws_done[name] then override_names[#override_names + 1] = name end
    end
    table.sort(override_names)
    for _, raw in ipairs(override_names) do ws_rule(raw, ws_override[raw]) end
    local ws_fallback = path_set(tostring(a.default_ws or ''), 'WS.default')
        or (sets.precast and add_set(sets.precast.WS, 'precast.WS'))
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
            local ja_name = tostring(name)
            local index = add_set(t, 'JA.' .. ja_name)
            local action = action_id(res.ability_by_name(ja_name))
            -- GearSwap writes one set under "Phantom Roll" for all 31 rolls.  The client
            -- never sends that action when a roll is picked; it sends the individual roll
            -- (Corsair's, Samurai, ...), so apply the same set to every roll action.
            if hud.cor_roll_names and ja_name:lower():gsub('[^%w]', '') == 'phantomroll' then
                for _, roll_name in ipairs(hud.cor_roll_names) do
                    local roll_action = action_id(res.ability_by_name(roll_name))
                    if roll_action and index then
                        rules[#rules + 1] = {
                            category = PHASE_JA, action = roll_action, pre = index,
                        }
                        ja_seen[roll_action] = true
                    end
                end
            elseif action and index then
                local pre = ja_override[action] or index
                rules[#rules + 1] = { category = PHASE_JA, action = action, pre = pre }
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
    if not precast then
        precast = path_set('precast.Spell', 'precast.spell')
            or (sets.precast and add_set(sets.precast.FC, 'precast.FC'))
            or (sets.precast and add_set(sets.precast, 'precast'))
    end
    -- Song-specific Fast Cast set (Fili head, Brioso body, Bihu feet).  The saved
    -- Song precast wins; otherwise fall back to the library's Song/FCBardSong set,
    -- then to the ordinary spell precast.
    local song_precast = path_set(tostring(a.precast_song or ''), 'precast.song.pick')
        or path_set('precast.Song', 'precast.song.library')
        or path_set('precast.FCBardSong', 'precast.song.fallback')
        or precast
    local mid_default = path_set(tostring(a.midcast or ''), 'midcast.default')
    local spell_override = {}
    if type(a.spell_overrides) == 'table' then
        for id, path in pairs(a.spell_overrides) do
            local key = tonumber(id)
            local index = path_set(path, 'spell.' .. tostring(id))
            if key and index then spell_override[key] = index end
        end
    end
    -- A group rule is a per-spell rule once the plan is built: the host looks up the action id
    -- and sees the set for the armed mode of the spell's group. Each spell belongs to one group,
    -- so the two modes never claim the same action.
    local category_override = {}
    if type(a.spell_category_overrides) == 'table' then
        for name, path in pairs(a.spell_category_overrides) do
            local index = path_set(path, 'spell.category.' .. tostring(name))
            if index then category_override[tostring(name)] = index end
        end
    end
    local spell_modes = normalize_spell_modes(a.spell_modes, category_override)
    -- A group's automatic set (the Nuking card's Magic Burst row) is not an armed mode.  It is
    -- attached to the group's rules, and the phase engine wears it instead of the ordinary
    -- midcast set only while the addon's burst window is open (watch_phase below).
    local auto_override = {}
    for group_key, group in pairs(SPELL_GROUPS) do
        local entry = {}
        local auto = group.auto
        if auto then
            local index = category_override[auto.category]
            if index then entry.burst = index end
        end
        local autos = {}
        for _, extra in ipairs(group.autos or {}) do
            local index = category_override[extra.category]
            local buff = tonumber(extra.buff) or 0
            if index and buff > 0 then
                autos[#autos + 1] = {
                    index = index, buff = buff, merge = extra.merge,
                    label = extra.label or extra.key, only_kind = extra.only_kind,
                }
            end
        end
        if #autos > 0 then entry.autos = autos end
        if next(entry) then auto_override[group_key] = entry end
    end
    -- Add the live-status rules for one action.  The engine prefers a rule that names more
    -- buffs, so these win while the status is up and the plain rule (no buffs) is the
    -- fallback; a merge overlay keeps the action's own set and swaps only the pieces it names.
    -- only_kind scopes an entry to one kind (Composure is only for the duration spells).
    local function add_auto_rules(group_key, kind_key, action, mid, pre, is_song)
        local auto = group_key and auto_override[group_key]
        for _, extra in ipairs(auto and auto.autos or {}) do
            if not extra.only_kind or extra.only_kind == kind_key then
                local cond_mid = extra.index
                if extra.merge then
                    cond_mid = merged_set(mid, extra.index, extra.label) or cond_mid
                end
                rules[#rules + 1] = {
                    category = PHASE_MAGIC, action = action, pre = pre, mid = cond_mid,
                    song = is_song, buffs = { extra.buff },
                }
            end
        end
    end
    local claimed = {}
    for id in pairs(spell_override) do claimed[id] = true end
    local song_override = {}
    if type(a.song_overrides) == 'table' then
        for id, entry in pairs(a.song_overrides) do
            local key = tonumber(id)
            if key and type(entry) == 'table' then
                local pre = path_set(tostring(entry.pre or ''), 'song.' .. key .. '.pre')
                local mid = path_set(tostring(entry.mid or ''), 'song.' .. key .. '.mid')
                if pre or mid then
                    song_override[key] = { pre = pre, mid = mid }
                    claimed[key] = true
                end
            end
        end
    end
    for index = 0, 1023 do
        if not claimed[index] then
            local spell = res.spell(index)
            if spell_is_known(spell) then
                local group_key = spell_group(spell)
                local mode = group_key and group_mode(group_key, spell_modes[group_key])
                local name = spell_name(spell):lower()
                local special = nil
                if name == 'honor march' then special = 'song_aeonic'
                elseif name == 'aria of passion' then special = 'song_prime' end
                local family_path = group_key == 'songs' and song_family_set(name)
                local family_mid = family_path and path_set(
                    family_path, 'song.family.' .. family_path)
                -- Enfeebles and Enhancing in Auto pick the category from the spell's own
                -- kind, so Frazzle III wears the Skill set, Slow II the MND set and Haste
                -- the duration set.
                local kind_key = spell_kind_key(group_key, spell)
                local cast_category = spell_cast_category(
                    group_key, spell, mode, category_override)
                local mid = family_mid
                    or (special and category_override[special])
                    or (cast_category and category_override[cast_category])
                    -- A configured midcast default covers songs too; tagging the rule song
                    -- keeps the Bard's Nitro instrument swap available for it.
                    or (group_key == 'songs' and mid_default)
                if not mid and special then
                    local fallback = special == 'song_aeonic'
                        and 'midcast.SongHonor' or 'midcast.SongAria'
                    mid = path_set(fallback, 'spell.special.' .. fallback)
                end
                if mid then
                    local rule = {
                        category = PHASE_MAGIC, action = index,
                        pre = (group_key == 'songs' and song_precast) or precast, mid = mid,
                        -- Only a Bard song may take an instrument off a pinned hand, and only
                        -- under Nitro; the host keys that exception off this flag.
                        song = group_key == 'songs',
                    }
                    local auto = group_key and auto_override[group_key]
                    if auto and auto.burst then rule.burst = auto.burst end
                    rules[#rules + 1] = rule
                    add_auto_rules(group_key, kind_key, index, mid,
                        (group_key == 'songs' and song_precast) or precast,
                        group_key == 'songs')
                    claimed[index] = true
                end
            end
        end
    end
    for id, mid in pairs(spell_override) do
        local spell = res.spell(id)
        local group_key = spell_group(spell)
        rules[#rules + 1] = {
            category = PHASE_MAGIC, action = id, pre = precast, mid = mid,
            song = group_key == 'songs',
        }
        -- A per-spell card still gets the live-status sets (the Saboteur hands overlay and
        -- the Composure self build): its set is the base they apply to.
        add_auto_rules(group_key, spell_kind_key(group_key, spell), id, mid, precast,
            group_key == 'songs')
    end
    for id, entry in pairs(song_override) do
        local spell = res.spell(id)
        local group_key = spell_group(spell)
        local mode = group_key and group_mode(group_key, spell_modes[group_key])
        local mid = entry.mid or (mode and category_override[mode.category])
        if mid then
            rules[#rules + 1] = {
                category = PHASE_MAGIC, action = id, pre = entry.pre or song_precast, mid = mid,
                song = true,
            }
        end
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
                            rules[#rules + 1] = {
                                category = PHASE_MAGIC, action = index, pre = precast, mid = mid,
                                song = (skill == 'Singing' or skill == 'String Instrument'
                                        or skill == 'Wind Instrument'),
                            }
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
    -- The host keeps as many sets as its table holds; it answers with that count. An older host
    -- answers true, so fall back to the plan's own length.
    local accepted = xi.phase.set({
        enabled = true, player = player, sets = set_list, names = set_names, rules = rules,
        engage = engage_set, idle = town_set, idle_town = town_set, idle_field = field_set,
        move = move_set, kite = kite_set, rest = rest_set, restore = restore,
        focus = {
            dt = focus_sets[1].index, pdt = focus_sets[2].index, mdt = focus_sets[3].index,
            eva = focus_sets[4].index, meva = focus_sets[5].index,
        },
        zone = zone, town = zone_town(zone), job = job,
    })
    if type(accepted) ~= 'number' then accepted = #set_list end
    phase_plan = {
        path = a.path, engaged = engaged_path, idle_town = town_path,
        idle_field = field_path, move = move_path, kite = a.kite, rest = a.rest,
        precast = a.precast, precast_song = a.precast_song, midcast = a.midcast, default_ws = a.default_ws,
        default_ja = a.default_ja, ws_overrides = a.ws_overrides,
        ja_overrides = a.ja_overrides, spell_overrides = a.spell_overrides,
        song_overrides = a.song_overrides,
        spell_category_overrides = a.spell_category_overrides, focus = a.focus,
        spell_modes = spell_modes, sets = sets,
        -- Force the watch loop to push the current buff list for this new rule table.  false is
        -- not a possible signature (an empty buff list is ''), so an empty list is pushed too.
        buff_at = -1, buff_sig = false,
    }
    phase_job_seen = nil
    -- A plan pushed during a zone or job load must not wear the whole outfit on top of the
    -- client's own zone-in equip. The settle is preserved by xi.phase.set; the watch loop sends
    -- the state set through xi.phase.pending when it is due.
    local settling = xi.phase.status().settling
    if not settling then inject_plan(xi.phase.apply()) end
    start_watch()
    local counts = { ws = 0, ja = 0, magic = 0 }
    for _, rule in ipairs(rules) do
        if rule.category == PHASE_WS then counts.ws = counts.ws + 1
        elseif rule.category == PHASE_JA then counts.ja = counts.ja + 1
        else counts.magic = counts.magic + 1 end
    end
    return {
        enabled = true, path = a.path, player = player, sets = accepted, built_sets = #set_list,
        rules = #rules,
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
        modes = spell_modes,
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
    if on then remember_worn_weapons() end
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
    remember_worn_weapons()
    local equipped = inject_plan(xi.phase.lock_slots(mask))
    local status = xi.phase.status()
    return {
        lockedSlots = status.lockedSlots, state = status.state, set = status.set,
        equipped = equipped, mask = mask,
    }
end

-- //gs: the in-game side of the launcher's state controls. The host sees the line before it is
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
    remember_worn_weapons()
    inject_plan(xi.phase.lock_slots(mask))
    return (action == 'lock' and 'locked ' or 'unlocked ') .. table.concat(names, ', ')
end

local MODE_GROUP_ALIASES = {
    enhancing = 'enhancing', enhance = 'enhancing', buff = 'enhancing', buffs = 'enhancing',
    enspells = 'enspells', enspell = 'enspells', sword = 'enspells',
    enfeebles = 'enfeebles', enfeeble = 'enfeebles', enfeebling = 'enfeebles',
    debuff = 'enfeebles', debuffs = 'enfeebles', enfeeb = 'enfeebles',
    curing = 'curing', cure = 'curing', healing = 'curing', heals = 'curing',
    nuking = 'nuking', nuke = 'nuking', nukes = 'nuking', elemental = 'nuking',
    helix = 'helix', helixes = 'helix',
    dark = 'dark', darkmagic = 'dark', darks = 'dark', drain = 'dark', aspir = 'dark',
    divine = 'divine', divinemagic = 'divine', holy = 'divine', banish = 'divine',
    songs = 'songs', song = 'songs', bard = 'songs', bards = 'songs',
}

local MODE_ALIASES = {
    accuracy = 'macc', acc = 'macc', skill = 'macc', landing = 'macc', macc = 'macc',
    duration = 'duration', time = 'duration', dur = 'duration',
    potency = 'potency', potent = 'potency', pot = 'potency',
    cast = 'cast', casttime = 'cast', fastcast = 'cast', speed = 'cast',
    mab = 'mab', magicattack = 'mab', attack = 'mab',
    mdmg = 'mdmg', magicdamage = 'mdmg', damage = 'mdmg', dmg = 'mdmg',
    enspell = 'damage', enspelldamage = 'damage',
    nodmg = 'nodamage', nodamage = 'nodamage',
}

local function current_spell_modes()
    return phase_plan and phase_plan.spell_modes or {}
end

local function spell_mode_summary()
    local parts = {}
    for _, group_key in ipairs(SPELL_GROUP_ORDER) do
        local mode = current_spell_modes()[group_key] or SPELL_GROUPS[group_key].default
        parts[#parts + 1] = SPELL_GROUPS[group_key].short .. ': ' .. mode_short(group_key, mode)
    end
    return table.concat(parts, ', ')
end

-- The //modes help reads the group list from the table, so a new group needs no second edit.
local function spell_group_names()
    local names = {}
    for _, group_key in ipairs(SPELL_GROUP_ORDER) do
        names[#names + 1] = SPELL_GROUPS[group_key].key
    end
    return table.concat(names, ', ')
end

local function resolve_mode_key(group_key, text)
    local group = SPELL_GROUPS[group_key]
    local key = tostring(text or ''):lower():gsub('[^%w]', '')
    if key == '' then return nil end
    for _, mode in ipairs(group.modes) do
        if mode.key == key then return mode.key end
        if mode.label:lower():gsub('[^%w]', '') == key then return mode.key end
        if mode.short:lower():gsub('[^%w]', '') == key then return mode.key end
    end
    local alias = MODE_ALIASES[key]
    if alias then
        for _, mode in ipairs(group.modes) do
            if mode.key == alias then return alias end
        end
    end
    return nil
end

local function set_spell_mode(group_key, mode_key)
    if not phase_plan or not phase_plan.spell_modes then
        return nil, 'GearSwap is off; turn it on in the launcher first'
    end
    local group = SPELL_GROUPS[group_key]
    if not group then return nil, 'unknown spell group: ' .. tostring(group_key) end
    if not group_mode(group_key, mode_key) then
        return nil, 'unknown ' .. group.label .. ' mode: ' .. tostring(mode_key)
    end
    local previous = phase_plan.spell_modes[group_key]
    phase_plan.spell_modes[group_key] = mode_key
    local ok, err = pcall(phase, phase_plan)
    if not ok then
        phase_plan.spell_modes[group_key] = previous
        return nil, tostring(err)
    end
    return true
end

local function modes_command(body)
    local words = {}
    for word in tostring(body or ''):gmatch('[^%s]+') do words[#words + 1] = word end
    if #words == 0 then
        if not phase_plan then return 'GearSwap is off; turn it on in the launcher first' end
        return spell_mode_summary() ..
            '  |  //modes <group> <mode>  (' .. spell_group_names() .. ')'
    end
    local group_key = MODE_GROUP_ALIASES[tostring(words[1]):lower()]
    if not group_key then
        return 'unknown group "' .. tostring(words[1]) ..
            '"; use one of: ' .. spell_group_names()
    end
    local group = SPELL_GROUPS[group_key]
    if #words < 2 then
        local options = {}
        for _, mode in ipairs(group.modes) do options[#options + 1] = mode.key end
        local current = current_spell_modes()[group_key] or group.default
        return group.label .. ' modes: ' .. table.concat(options, ', ') ..
            ' (current: ' .. current .. ')'
    end
    local mode_key = resolve_mode_key(group_key, words[2])
    if not mode_key then
        local options = {}
        for _, mode in ipairs(group.modes) do options[#options + 1] = mode.key end
        return 'unknown ' .. group.label .. ' mode "' .. tostring(words[2]) ..
            '"; use ' .. table.concat(options, ', ')
    end
    local ok, err = set_spell_mode(group_key, mode_key)
    if not ok then return tostring(err) end
    return spell_mode_summary()
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
        -- While an action holds its set (a weaponskill's, between the action and its result)
        -- that set is what is on, not the state set.
        local set = status.actionSet or status.set
        local line = tostring(status.state) .. (set and (' - ' .. tostring(set)) or '')
        if status.actionSet and status.actionMs then
            line = line .. string.format(' (%.1fs)', status.actionMs / 1000)
        end
        if status.burst then line = line .. ' - MB window' end
        return line
    end
    return 'usage: //gs lock|unlock <slots>, rest on|off, kite on|off, focus auto|dt|pdt|mdt|eva|meva'
end

if xi.phase and xi.events and xi.events.on then
    xi.events.on('command', function(e)
        if e.blocked then return end
        local line = e.data
        if type(line) ~= 'string' then return end
        local body = line:match('^//gs%s+(.+)$') or line:match('^/%!gs%s+(.+)$') or
            line:match('^%!gs%s+(.+)$')
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

if xi.phase and xi.events and xi.events.on then
    xi.events.on('command', function(e)
        if e.blocked then return end
        local line = e.data
        if type(line) ~= 'string' then return end
        local body = line:match('^//modes%s+(.+)$') or line:match('^/%!modes%s+(.+)$') or
            line:match('^%!modes%s+(.+)$')
        local bare = line:match('^//modes%s*$') or line:match('^/%!modes%s*$') or
            line:match('^%!modes%s*$')
        if not body and not bare then return end
        e.blocked = true
        local ok, result = pcall(modes_command, body or '')
        if ok and type(result) == 'string' then
            xi.chat.write('Modes: ' .. result, 1)
        elseif not ok then
            xi.chat.write('Modes: ' .. tostring(result), 1)
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
    local remembered = {}
    for _, entry in ipairs(items) do
        local slot = SLOT_INDEX[tostring(entry.slot or ''):lower()]
        if slot == nil then
            errors[#errors + 1] = 'unknown slot ' .. tostring(entry.slot)
        elseif locked[slot] then
            skipped = skipped + 1 -- pinned by //gs lock: no set may override it
        else
            local bag, at, id = find_item(by_id, entry.item, claimed)
            if not bag then
                errors[#errors + 1] = tostring(entry.item) .. ' is not in this character\'s bags'
            else
                -- Remember every piece the set names, including one already on.  A pinned
                -- weaponset lives outside the state sets, so without this the phase engine
                -- cannot restore it after a locked action's temporary KI/song/WS swap.
                remembered[#remembered + 1] = { slot, bag, at }
                if worn[slot] == id then
                    skipped = skipped + 1 -- already on; GearSwap leaves a matching piece alone
                else
                    claimed[bag * 256 + at] = true
                    packets[#packets + 1] = equip_packet(bag, at, slot)
                end
            end
        end
    end
    -- Every piece leaves in the same frame, the way GearSwap's 0x050/0x051 burst does. The old
    -- coroutine.sleepf(1) per piece put one slot in each frame, so a Wear set arrived in waves
    -- and could miss the precast or midcast window it was meant for.
    for _, packet in ipairs(packets) do
        xi.packets.inject(true, packet)
    end
    -- The engine keeps what each slot wears to send only the pieces that change.  A manual
    -- set is not a state set, so teach it the exact copies instead of forgetting the table:
    -- forgetting is what left a pinned Ikenga/Aspis unknown and stuck on the action's piece.
    if xi.phase then
        if xi.phase.remember then
            for _, piece in ipairs(remembered) do
                xi.phase.remember(piece[1], piece[2], piece[3])
            end
        else
            xi.phase.forget()
        end
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
            id = item_id_for_name(name)
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
                local normal = level and level > 0 and level <= job.level
                -- Job-point spells carry a level sentinel (100/550/1200) and the jobs that can
                -- learn them in job_point_mask. Include them for a level-99 main job only.
                local mask = tonumber(spell.job_point_mask) or 0
                local job_point = job == jobs[1] and job.id > 0 and job.level >= 99
                    and mask > 0 and math.floor(mask / (2 ^ job.id)) % 2 == 1
                if (normal or job_point) and not seen[id] then
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
                        level = normal and level or job.level,
                        icon = icon, recast = (tonumber(spell.recast_delay) or 0) / 4,
                        targets = tonumber(spell.targets) or 0,
                        -- The group plus the enfeebling kind (`enfeebles_mnd`, ...), so the
                        -- Spells panel can list each kind's spells under its own set row.
                        categories = spell_categories(spell),
                        job_point = job_point or nil,
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
        -- 182/183/198/199 are Dancer's Sambas/Waltzes/Jigs/Steps headers and 200/213/263
        -- are Flourishes I/II/III.  They are menu categories, not abilities: they have no
        -- animation and no effect, so a flat Abilities window showed them as broken
        -- buttons.  Migration 0147 drops them; skip them here too for a client whose
        -- command list was built before the server restarted.  The command list stores a
        -- job ability as 0x200 + its ability id, so compare the low part.
        local ability_id = id - 0x200
        local category = ability_id == 182 or ability_id == 183 or ability_id == 198
            or ability_id == 199 or ability_id == 200 or ability_id == 213
            or ability_id == 263
        if id >= 0x200 and id < 0x400 and not seen[id] and not category then
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
    [2] = { 8, 5, 0 },
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
    [15] = { 13, 11, 5 },
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
    [40] = { 4, 8, 0 },
    [41] = { 9, 0, 0 },
    [42] = { 12, 4, 0 },
    [43] = { 13, 11, 0 },
    [44] = { 12, 10, 0 },
    [45] = { 11, 5, 0 },
    [46] = { 10, 4, 0 },
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
    [60] = { 13, 12, 4 },
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
    [77] = { 14, 10, 6 },
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
    [93] = { 13, 11, 2 },
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
    [109] = { 14, 9, 5 },
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
    [125] = { 14, 9, 1 },
    [126] = { 1, 4, 9 },
    [128] = { 1, 0, 0 },
    [129] = { 4, 0, 0 },
    [130] = { 5, 0, 0 },
    [131] = { 7, 6, 0 },
    [132] = { 8, 1, 0 },
    [133] = { 2, 0, 0 },
    [134] = { 8, 6, 0 },
    [135] = { 9, 0, 0 },
    [136] = { 9, 1, 0 },
    [137] = { 14, 12, 0 },
    [138] = { 12, 2, 0 },
    [139] = { 5, 4, 0 },
    [140] = { 14, 9, 0 },
    [141] = { 13, 11, 8 },
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
    [157] = { 13, 12, 2 },
    [158] = { 11, 0, 0 },
    [159] = { 6, 2, 10 },
    [160] = { 8, 0, 0 },
    [161] = { 8, 0, 0 },
    [162] = { 5, 0, 0 },
    [165] = { 7, 5, 0 },
    [166] = { 6, 8, 0 },
    [167] = { 8, 0, 0 },
    [168] = { 11, 0, 0 },
    [169] = { 12, 2, 0 },
    [170] = { 13, 12, 0 },
    [172] = { 5, 7, 0 },
    [174] = { 13, 11, 8 },
    [175] = { 14, 12, 0 },
    [176] = { 8, 0, 0 },
    [177] = { 8, 0, 0 },
    [178] = { 6, 8, 0 },
    [179] = { 2, 5, 0 },
    [180] = { 2, 5, 0 },
    [181] = { 6, 0, 0 },
    [182] = { 3, 8, 0 },
    [184] = { 9, 5, 0 },
    [185] = { 14, 10, 0 },
    [186] = { 12, 10, 0 },
    [187] = { 11, 5, 0 },
    [188] = { 9, 1, 0 },
    [189] = { 2, 5, 0 },
    [191] = { 14, 9, 7 },
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
    [203] = { 13, 12, 1 },
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
    [221] = { 13, 11, 5 },
    [222] = { 7, 5, 11 },
    [224] = { 13, 12, 4 },
    [225] = { 13, 10, 0 },
    [226] = { 14, 9, 4 },
    [227] = { 13, 0, 0 },
    [228] = { 13, 0, 0 },
    [231] = { 6, 2, 10 },
    [232] = { 3, 8, 12 },
    [233] = { 6, 2, 10 },
    [234] = { 1, 4, 9 },
    [235] = { 7, 5, 11 },
    [238] = { 13, 12, 4 },
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
-- 0x028 skillchain proc id -> SC_* id (ActionProcSkillChain).  The tier of the chain a
-- weapon skill just formed decides the next window: a level-1 link keeps the full 11 s,
-- a wider link shrinks by one second.
local HUD_SC_PROC = {
    [1] = 13, [2] = 14, [3] = 9, [4] = 12, [5] = 10, [6] = 11, [7] = 2,
    [8] = 3, [9] = 7, [10] = 5, [11] = 1, [12] = 4, [13] = 6, [14] = 8,
}
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
-- The server's skillchain window: 11 s for the opener; a level-1 link keeps the full
-- 11 s (the Savage Blade / Hot Shot loop), while a level-2/3 link loses a second per
-- step.  That is one second longer than AutoSkillchains' 10 s base (see skillchain.py).
local HUD_SC_BASE = 15.0
-- The server accepts a close up to half a second after the window closes (the status
-- effect's tick).  The HUD uses the same allowance when deciding whether a new TP drop
-- continues the chain or starts a fresh opener.
local HUD_SC_GRACE = 0.5

-- The displayed window after the opener: 11 s, then one second less per formed link.
local function hud_sc_total(step)
    return HUD_SC_BASE - (math.max(1, tonumber(step) or 1) - 1)
end

-- The actual window for the step.  A level-1 link keeps the full 11 s, so the counter
-- must not shrink while the chain stays level 1.
local function hud_sc_window(step, tier)
    if tonumber(tier) == 1 then return HUD_SC_BASE end
    return hud_sc_total(step)
end

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

-- Magic Burst windows.  The client has no "Magic Burst" status (res.status_ids carries neither
-- Magic Burst nor Skillchain), so the window is read from the action that formed the chain: the
-- closing result's 0x028 additional-effect block carries message 287 + proc (384 + proc when the
-- chain was absorbed).  The server keeps the window on the target's Skillchain state: 11 s after
-- a level-1 link, one second less per link on a level-2/3 chain, and a landed weapon skill that
-- forms no chain replaces that state with a fresh opening and ends the window.
do
    -- A `do` block keeps the window state out of hud_init's locals: that function is at LuaJIT's
    -- 200-local limit, and these closures keep the state alive for the packet handler below.
    local MB_WINDOW_BASE = HUD_SC_BASE
    local mb_windows = {} -- target server id -> { expires = xi.clock() deadline, duration = seconds }

    local function mb_open_window(target, sc_id, now)
        for id, window in pairs(mb_windows) do
            if now > window.expires + 60 then mb_windows[id] = nil end
        end
        local prev = mb_windows[target]
        -- A link may land just inside the server's half-second close grace.
        local was_open = prev ~= nil and now <= prev.expires + HUD_SC_GRACE
        local duration
        if HUD_SC_TIER[sc_id] == 1 then
            duration = MB_WINDOW_BASE
        else
            -- The opener's 11 s state is the first link's predecessor; a formation with no window
            -- tracked yet (the opener was not a chain) is therefore the first link.
            duration = math.max(0, (was_open and prev.duration or MB_WINDOW_BASE) - 1)
        end
        mb_windows[target] = { expires = now + duration, duration = duration, sc = sc_id }
    end

    -- Every 0x028 action: a landed weapon skill that formed no chain ends the target's burst
    -- window; a formation opens or extends it.  Spells only form (an Immanence or Chain Affinity
    -- close), because an ordinary spell does not change a chain's resonance.
    local function mb_scan_action(data)
        local category = bits(data, 82, 4)
        if category ~= 3 and category ~= 4 then return end
        local action = bits(data, 86, 32)
        local props = HUD_WS_SC[action]
        local now = xi.clock()
        local targets = math.min(bits(data, 72, 10), 32)
        local pos, limit = 150, #data * 8
        for _ = 1, targets do
            if pos + 36 > limit then break end
            local target = bits(data, pos, 32)
            local count = math.min(bits(data, pos + 32, 4), 32)
            pos = pos + 36
            for _ = 1, count do
                if pos + 87 > limit then break end
                local resolution = bits(data, pos, 3)
                local has_add = bits(data, pos + 85, 1)
                pos = pos + 86
                local message = 0
                if has_add == 1 then
                    message = bits(data, pos + 27, 10)
                    pos = pos + 37
                end
                if bits(data, pos, 1) == 1 then pos = pos + 34 end
                pos = pos + 1
                local sc_id
                if message >= 287 and message < 287 + 16 then
                    sc_id = HUD_SC_PROC[message - 287]
                elseif message >= 384 and message < 384 + 16 then
                    sc_id = HUD_SC_PROC[message - 384]
                end
                if target > 0 then
                    if sc_id then
                        mb_open_window(target, sc_id, now)
                    elseif category == 3 and resolution == 0 and props then
                        -- A weapon skill that lands but does not link is a new opening.
                        mb_windows[target] = nil
                    end
                end
            end
        end
    end

    function phase_burst_open()
        local index = game.target('Targets[0].Index') or 0
        if index <= 0 or (game.target('Targets[0].IsActive') or 0) == 0 then return false end
        local target = game.entity(index, 'ServerId')
        local window = target and mb_windows[target] or nil
        return window ~= nil and xi.clock() <= window.expires
    end

    -- The Scholar HUD's small live banner: the chain that is bursting and the time
    -- left in its window.  Kept separate from phase_burst_open so the phase engine's
    -- boolean path does not have to carry the extra fields.
    function phase_burst_info()
        local index = game.target('Targets[0].Index') or 0
        if index <= 0 or (game.target('Targets[0].IsActive') or 0) == 0 then return nil end
        local target = game.entity(index, 'ServerId')
        local window = target and mb_windows[target] or nil
        if not window then return nil end
        local remaining = window.expires - xi.clock()
        if remaining <= 0 then return nil end
        return { sc = window.sc or 0, remaining = remaining, duration = window.duration }
    end

    if xi.events and xi.events.on then
        xi.events.on('packet_in', function(e)
            if e.blocked or e.injected or e.id ~= 0x028 then return end
            local data = e.modified or e.data
            if type(data) ~= 'string' or #data < 32 then return end
            local ok, err = pcall(mb_scan_action, data)
            if not ok then xi.log('phase: magic burst window: ' .. tostring(err)) end
        end)
    end
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

-- BEGIN HUD label rules -- tests/spell_names_test.py extracts this region and runs it.
-- Deliberately terse labels. At 42-48 px the stock spell names do not fit; the tooltip keeps the
-- full name, level and recast. These are the names the game's own menus abbreviate most often.
local HUD_SHORT = {
    ['Cure'] = 'CURE', ['Curaga'] = 'CURAG', ['Cura'] = 'CURA',
    ['Protect'] = 'PROT', ['Shell'] = 'SHEL', ['Refresh'] = 'REFR', ['Regen'] = 'REGN',
    ['Haste'] = 'HAST', ['Dispel'] = 'DISP', ['Sleep'] = 'SLEP', ['Sleepga'] = 'SLEPG',
    ['Silence'] = 'SILN', ['Paralyze'] = 'PARA', ['Slow'] = 'SLOW', ['Gravity'] = 'GRAV',
    ['Bind'] = 'BIND', ['Blind'] = 'BLND', ['Poison'] = 'PSN', ['Bio'] = 'BIO',
    ['Dia'] = 'DIA', ['Banish'] = 'BAN', ['Holy'] = 'HOLY', ['Flare'] = 'FLAR',
    ['Freeze'] = 'FRZ', ['Tornado'] = 'TRND', ['Quake'] = 'QUAK', ['Burst'] = 'BRST',
    ['Flood'] = 'FLOD', ['Meteor'] = 'METR', ['Death'] = 'DEATH', ['Aspir'] = 'ASPR',
    ['Drain'] = 'DRAN', ['Stun'] = 'STUN', ['Break'] = 'BREAK', ['Utsusemi: Ichi'] = 'UTSU1',
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
    -- Rudra's Storm and Ruthless Stroke are both a seven-letter first word plus a one-word
    -- second, so the initials rule below labels each one "RS" and the dagger row shows the
    -- same tile twice.  Keep the storm/stroke half of the name instead: RSTRM and RSTRK.
    ["Rudra's Storm"] = 'RSTRM', ['Ruthless Stroke'] = 'RSTRK',

    -- Spell lines whose first five letters are shared by a different line.  The suffix letter
    -- names the line (-ga G, -ra R, -ja J) and the rank digit is appended by hud_spell_parts:
    -- AEROG/AEROG2, BLIZG/BLIZG2, BARB/BARBL.  None of these is longer than six characters
    -- before the rank digit, so a ranked tile still fits at the stock 42-48 px.
    ['Barfire'] = 'BARF', ['Barfira'] = 'BARFR',
    ['Barblizzard'] = 'BARB', ['Barblizzara'] = 'BARBR',
    ['Baraero'] = 'BARA', ['Baraera'] = 'BARAR',
    ['Barstone'] = 'BARS', ['Barstonra'] = 'BARSR',
    ['Barthunder'] = 'BART', ['Barthundra'] = 'BARTR',
    ['Barwater'] = 'BARW', ['Barwatera'] = 'BARWR',
    ['Barsleep'] = 'BARSL', ['Barsleepra'] = 'BARSLR',
    ['Barpoison'] = 'BARPS', ['Barpoisonra'] = 'BARPSR',
    ['Barparalyze'] = 'BARPA', ['Barparalyzra'] = 'BARPAR',
    ['Barblind'] = 'BARBL', ['Barblindra'] = 'BARBLR',
    ['Barsilence'] = 'BARSI', ['Barsilencera'] = 'BARSIR',
    ['Barpetrify'] = 'BARPE', ['Barpetra'] = 'BARPER',
    ['Barvirus'] = 'BARV', ['Barvira'] = 'BARVR',
    ['Baramnesia'] = 'BARAM', ['Baramnesra'] = 'BARAMR',
    ['Firestorm'] = 'FSTRM', ['Windstorm'] = 'WSTRM', ['Sandstorm'] = 'SSTRM',
    ['Rainstorm'] = 'RSTRM', ['Thunderstorm'] = 'TSTRM', ['Hailstorm'] = 'HSTRM',
    ['Aurorastorm'] = 'ASTRM', ['Voidstorm'] = 'VSTRM',
    ['Firespit'] = 'FSPIT', ['Ice Spikes'] = 'ISPIK', ['Stoneskin'] = 'STNSK',
    ['Thunderbolt'] = 'TBOLT', ['Sandspin'] = 'SPIN', ['Sandspray'] = 'SPRAY',
    ['Blood Drain'] = 'BLDDR', ['Blood Saber'] = 'BLDSB', ['Bloodrake'] = 'BLDRK',
    ['Magic Finale'] = 'MGFIN', ['Magic Fruit'] = 'MGFRT',
}

-- The three-letter fallback a tile too narrow for the short label uses takes the first three
-- letters of that label, which would put RSTRM and RSTRK back to the same "RST".  These keep the
-- half that tells them apart instead.  A field of HUD_SHORT rather than a local of its own: the
-- chunk is within a few variables of the client Lua's 200-local limit.
HUD_SHORT.tiny = {
    ["Rudra's Storm"] = 'STM', ['Ruthless Stroke'] = 'STK',
}

-- Two light spells differ only after their fifth letter. Keep the four-letter word apart rather
-- than folding both onto "LIGH": Light Carol -> LGHTC, Lightning Carol -> LTNGC.
HUD_SHORT.words = { Lightning = 'LTNG', Light = 'LGHT' }

-- Bard songs are a spell family of their own: "Knights Minne" and its four ranks share the Minne
-- status, while the old first-word-plus-initial rule labelled them KNIGM, KNIGM2, ... and left
-- an 80-tile Buff page as unreadable consonant soup.  The families map each song line to the
-- effect group a player actually searches by (haste, attack, defense, accuracy, recovery, ...);
-- the group gives the page its colour band, note tint and tile border, and the family gives the
-- tile its readable label.  A rank keeps that label and puts the Roman rank on the icon badge
-- ("Army's Paeon IV" reads PAEON with a IV badge, not ARMYP4).
HUD_SHORT.song_roles = {
    haste = { title = 'Haste', hint = 'March, Mazurka',
      color = { 246, 196, 83 }, order = 10 },
    attack = { title = 'Attack', hint = 'Minuet, Mambo',
      color = { 239, 108, 108 }, order = 20 },
    defense = { title = 'Defense', hint = 'Minne, Protected Aria',
      color = { 111, 168, 220 }, order = 30 },
    mdefense = { title = 'Magic Defense', hint = 'Carol, Scherzo',
      color = { 183, 148, 244 }, order = 40 },
    accuracy = { title = 'Accuracy', hint = 'Madrigal, Prelude',
      color = { 126, 211, 137 }, order = 50 },
    recovery = { title = 'Recovery', hint = 'Ballad, Paeon, Hymnus',
      color = { 99, 179, 237 }, order = 60 },
    etude = { title = 'Etude', hint = 'Stat boost',
      color = { 214, 188, 250 }, order = 70 },
    support = { title = 'Support', hint = 'Resistance and utility',
      color = { 160, 174, 192 }, order = 80 },
    dot = { title = 'Damage', hint = 'Requiem',
      color = { 255, 120, 110 }, order = 100 },
    slow = { title = 'Slow', hint = 'Elegy',
      color = { 150, 148, 255 }, order = 110 },
    element = { title = 'Elemental', hint = 'Threnody',
      color = { 255, 186, 92 }, order = 120 },
    control = { title = 'Control', hint = 'Lullaby, Nocturne, Virelai, Finale',
      color = { 124, 210, 240 }, order = 130 },
}

HUD_SHORT.song_families = {
    { match = 'march', role = 'haste' },
    { match = 'mazurka', role = 'haste' },
    { match = 'minuet', role = 'attack' },
    { match = 'mambo', role = 'attack' },
    { match = 'minne', role = 'defense' },
    { match = 'passion', role = 'attack' },
    { match = 'aria', role = 'defense' },
    { match = 'carol', role = 'mdefense' },
    { match = 'scherzo', role = 'mdefense' },
    { match = 'madrigal', role = 'accuracy' },
    { match = 'prelude', role = 'accuracy' },
    { match = 'ballad', role = 'recovery' },
    { match = 'paeon', role = 'recovery' },
    { match = 'hymnus', role = 'recovery' },
    { match = 'etude', role = 'etude' },
    { match = 'requiem', role = 'dot' },
    { match = 'elegy', role = 'slow' },
    { match = 'threnody', role = 'element' },
    { match = 'lullaby', role = 'control' },
    { match = 'finale', role = 'control' },
    { match = 'nocturne', role = 'control' },
    { match = 'virelai', role = 'control' },
    { match = 'operetta', role = 'support' },
    { match = 'sirvente', role = 'support' },
    { match = 'serenade', role = 'support' },
    { match = 'aubade', role = 'support' },
    { match = 'fantasia', role = 'support' },
    { match = 'rhapsody', role = 'support' },
    { match = 'capriccio', role = 'support' },
    { match = 'fugue', role = 'support' },
    { match = 'gavotte', role = 'support' },
    { match = 'hum', role = 'support' },
    { match = 'pastoral', role = 'support' },
    { match = 'round', role = 'support' },
    { match = 'dirge', role = 'support' },
}

-- Names are normalised the same way song_info does it (lowercase letters only), so the DB's
-- "Armys Paeon" and the client's "Army's Paeon" are one key.  The value is the tile label; a
-- Roman rank is appended only to the icon badge, never to this label.
HUD_SHORT.song_names = {
    advancingmarch = 'ADVANCE', adventurersdirge = 'DIRGE', archersprelude = 'ARCHER',
    ariaofpassion = 'PASSION', honormarch = 'HONOR',
    armyspaeon = 'PAEON', battlefieldelegy = 'BATTLE', bewitchingetude = 'CHR+',
    blademadrigal = 'BLADE', cactuarfugue = 'FUGUE', carnageelegy = 'CARNAGE',
    chocobohum = 'HUM', chocobomazurka = 'CHOCOBO', darkcarol = 'DARK C',
    darkthrenody = 'DARK T', devoteeserenade = 'SEREN', dextrousetude = 'DEX',
    dragonfoemambo = 'DRAGON', earthcarol = 'EARTH C', earththrenody = 'EARTH T',
    enchantingetude = 'CHR', firecarol = 'FIRE C', firethrenody = 'FIRE T',
    foelullaby = 'FOE LUL', foerequiem = 'REQUIEM', foesirvente = 'SIRVENT',
    fowlaubade = 'AUBADE', goblingavotte = 'GAVOTTE', goddessshymnus = 'HYMNUS',
    goldcapriccio = 'CAPRIC', herbpastoral = 'PASTOR', herculeanetude = 'STR+',
    hordelullaby = 'HORDE', huntersprelude = 'HUNTER', icecarol = 'ICE C',
    icethrenody = 'ICE T', jestersoperetta = 'JESTER', knightsminne = 'MINNE',
    learnedetude = 'INT', lightcarol = 'LIGHT C', lightthrenody = 'LIGHT T',
    lightningcarol = 'LTNG C', lightningthrenody = 'LTNG T', ltngthrenody = 'LTNG T',
    logicaletude = 'MND+', magesballad = 'BALLAD', magicfinale = 'FINALE',
    maidensvirelai = 'VIRELAI', massacreelegy = 'MASSAC', mooglerhapsody = 'RHAPS',
    piningnocturne = 'NOCTUR', protectedaria = 'PROTECT', puppetsoperetta = 'PUPPET',
    quicketude = 'AGI', raptormazurka = 'RAPTOR', sageetude = 'INT+',
    scopsoperetta = 'SCOPS', sentinelsscherzo = 'SCHERZO', sheepfoemambo = 'SHEEP',
    shiningfantasia = 'FANTAS', sinewyetude = 'STR', spiritedetude = 'MND',
    swiftetude = 'AGI+', swordmadrigal = 'SWORD', uncannyetude = 'DEX+',
    valorminuet = 'MINUET', victorymarch = 'VICTORY', vitaletude = 'VIT+',
    vivaciousetude = 'VIT', wardinground = 'ROUND', watercarol = 'WATER C',
    waterthrenody = 'WATER T', windcarol = 'WIND C', windthrenody = 'WIND T',
}

-- The three-letter fallback is only used when a tile is too narrow for the full label.  Keep
-- the two halves of a line apart (FIRE C / FIRE T, MINNE / MINUET), since the tile and the
-- rank badge are tiny at that point.
HUD_SHORT.song_tinies = {
    advancingmarch = 'ADV', archersprelude = 'ARC', armyspaeon = 'PAE',
    ariaofpassion = 'PAS', honormarch = 'HON',
    battlefieldelegy = 'BAT', blademadrigal = 'BLD', carnageelegy = 'CAR',
    chocobomazurka = 'CHO', darkcarol = 'DKC', darkthrenody = 'DKT',
    dragonfoemambo = 'DRA', earthcarol = 'ERC', earththrenody = 'ERT',
    firecarol = 'FRC', firethrenody = 'FRT', foelullaby = 'FLL',
    hordelullaby = 'HOR', huntersprelude = 'HNT', icecarol = 'ICC',
    icethrenody = 'ICT', jestersoperetta = 'JES', knightsminne = 'MNN',
    lightcarol = 'LTC', lightthrenody = 'LTT', lightningcarol = 'LGC',
    lightningthrenody = 'LGT', ltngthrenody = 'LGT', magesballad = 'BAL',
    massacreelegy = 'MAS', puppetsoperetta = 'PUP', raptormazurka = 'RAP',
    scopsoperetta = 'SCO', sheepfoemambo = 'SHE', swordmadrigal = 'SWD',
    valorminuet = 'MNT', victorymarch = 'VIC', watercarol = 'WTC',
    waterthrenody = 'WTT', windcarol = 'WNC', windthrenody = 'WNT',
    -- Etudes: the label is the stat (Herculean/Uncanny/... are the stronger tier), so the
    -- tiny form needs a marker to keep the pair apart.
    herculeanetude = 'ST+', uncannyetude = 'DX+', vitaletude = 'VT+',
    swiftetude = 'AG+', sageetude = 'IN+', logicaletude = 'MN+',
    bewitchingetude = 'CH+',
}

HUD_SHORT.song_family = function(name)
    local key = tostring(name or ''):lower():gsub('%s+[ivx]+$', '')
    key = key:gsub('[^%a]', '')
    if key == '' then return nil end
    for _, family in ipairs(HUD_SHORT.song_families) do
        if key:find(family.match, 1, true) then return family end
    end
    return nil
end

HUD_SHORT.song_info = function(name)
    local base = tostring(name or ''):gsub('^%s+', ''):gsub('%s+$', '')
    if base == '' then return nil end
    base = base:gsub('%s+[IVX]+$', '')
    local key = base:lower():gsub('[^%a]', '')
    local family = HUD_SHORT.song_family(base)
    local role = family and HUD_SHORT.song_roles[family.role] or nil
    local label = HUD_SHORT.song_names[key]
    if not role or not label then return nil end
    return {
        short = label,
        tiny = HUD_SHORT.song_tinies[key] or label:gsub('%s', ''):sub(1, 3),
        family = family,
        role = role,
    }
end

-- Split one spell page into effect groups.  Non-songs join an "Other" section so a sub-job's
-- Protect/Shell do not disappear from a Bard page.  A page with one song or one group has
-- nothing to section and keeps the old single block.
HUD_SHORT.song_sections = function(items)
    local buckets, order, songs = {}, {}, 0
    for _, item in ipairs(items) do
        local info = HUD_SHORT.song_info(item.name)
        local role = info and info.role or nil
        local title = role and role.title or 'Other'
        local bucket = buckets[title]
        if not bucket then
            bucket = {
                title = title,
                hint = role and role.hint or '',
                color = role and role.color or { 160, 174, 192 },
                order = role and role.order or 900,
                items = {},
            }
            buckets[title] = bucket
            order[#order + 1] = bucket
        end
        bucket.items[#bucket.items + 1] = item
        if role then songs = songs + 1 end
    end
    if songs < 2 or #order < 2 then return nil end
    table.sort(order, function(a, b)
        if a.order == b.order then return a.title < b.title end
        return a.order < b.order
    end)
    return order
end

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
    if exact then return exact, HUD_SHORT.tiny[name] or exact:sub(1, 3) end

    -- The seven Gain-* spells all share their first five letters, so the generic fallback
    -- labeled every tile "GAIN-". Keep the stat suffix instead: Gain-MND -> G-MND (tiny GMND).
    local gain = name:match('^Gain%-(%a+)$')
    if gain then
        local suffix = gain:upper()
        return 'G-' .. suffix, 'G' .. suffix
    end

    -- Teleport-Holla and Teleport-Dem both used to clip to "TELEP", and the three Recall-*
    -- spells did the same; keep the destination half so the Zoning page is readable.
    local travel = name:match('^[Tt]eleport%-(.+)$') or name:match('^[Rr]ecall%-(.+)$')
    if travel then
        local prefix = name:sub(1, 1):upper()
        local tail = travel:gsub('[^%w]', ''):upper()
        local short = prefix .. '-' .. tail:sub(1, 4)
        if #short > 6 then short = short:sub(1, 6) end
        return short, short:sub(1, 3)
    end

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

-- Spell labels and rank.  The spell window needs two things the action labels above do not:
--   * two different lines must never share a label (Aero II and Aeroga II both read "AERO2"),
--     and the name has to stay short enough for a 42-48 px tile, so the suffix letter names the
--     line (-ga G, -ra R, -ja J) and the rank is the Arabic digit: AERO2 / AEROG2.
--   * a ranked spell keeps its line's tier-I art, with the Roman rank drawn small at the icon's
--     top-right, so the tile reads as "this element, this rank" instead of a generic numeral.
-- The launcher's tooltip still shows the exact English name.
local function hud_spell_parts(name, spell)
    name = tostring(name or ''):gsub('^%s+', ''):gsub('%s+$', '')
    if name == '' then return '?', '?', nil, nil, nil end

    -- A Bard song keeps its family name on the tile and its rank on the icon badge, so the
    -- label does not spend two of its six characters repeating the numeral: Army's Paeon IV
    -- reads PAEON + IV, not ARMYP4.  song_info also matches the client's apostrophes to the
    -- database's unpunctuated names.
    local song_base, song_rank = name:match('^(.-)%s+([IVX]+)$')
    if song_rank and not HUD_ROMAN[song_rank] then song_base, song_rank = nil, nil end
    local song = HUD_SHORT.song_info(song_base or name)
    if song then
        if song_rank then
            return song.short, song.tiny, song_base, song_rank, tonumber(HUD_ROMAN[song_rank])
        end
        return song.short, song.tiny, nil, nil, nil
    end

    local function base_short(n)
        local exact = HUD_SHORT[n]
        if exact then return exact end

        local gain = n:match('^Gain%-(%a+)$')
        if gain then return 'G-' .. gain:upper() end

        local travel = n:match('^[Tt]eleport%-(.+)$') or n:match('^[Rr]ecall%-(.+)$')
        if travel then
            local prefix = n:sub(1, 1):upper()
            local tail = travel:gsub('[^%w]', ''):upper()
            local short = prefix .. '-' .. tail:sub(1, 4)
            if #short > 6 then short = short:sub(1, 6) end
            return short
        end

        local absorb = n:match('^Absorb%-(%a+)$')
        if absorb then return 'ABS' .. absorb:sub(1, 3):upper() end
        local boost = n:match('^Boost%-(%a+)$')
        if boost then return 'BST' .. boost:sub(1, 3):upper() end
        local geo = n:match('^Geo%-(%a+)$')
        if geo then return 'GEO' .. geo:sub(1, 4):upper() end
        local indi = n:match('^Indi%-(%a+)$')
        if indi then return 'IND' .. indi:sub(1, 4):upper() end

        -- The -ga/-ra/-ja lines all share the first five letters with their base line.  Keep the
        -- line half plus one letter; Watera's WATE+R would be Water itself, so it falls to WATR.
        -- These are spell-line rules: a Trust called Nashmeira must not become NASHR.
        if spell then
            local suffix, letter = nil, nil
            if n:sub(-2) == 'ga' then suffix, letter = 'ga', 'G'
            elseif n:sub(-2) == 'ja' then suffix, letter = 'ja', 'J'
            elseif n:sub(-2) == 'ra' then suffix, letter = 'ra', 'R' end
            if suffix then
                local stem = n:sub(1, -3)
                if #stem >= 3 then
                    local code = HUD_SHORT[stem]
                    if not code or #code < 4 then code = stem:sub(1, 4) end
                    code = code:upper()
                    local short = code .. letter
                    if suffix == 'ra' and base_short(stem .. 'r') == short then
                        short = code:sub(1, 3) .. letter
                    end
                    return short
                end
            end
        end

        -- Ninjutsu names use "Katon: Ichi" in the client and "Katon Ichi" in some tables; the
        -- element half plus the tier digit reads the same either way (KATO1, UTSU2, DOTON3).
        local prefix, tail = n:match('^(.-)[:%s]+(Ichi)$')
        if not prefix then prefix, tail = n:match('^(.-)[:%s]+(Ni)$') end
        if not prefix then prefix, tail = n:match('^(.-)[:%s]+(San)$') end
        if prefix and prefix ~= '' and #prefix >= 3 then
            local tier = tail == 'Ichi' and '1' or tail == 'Ni' and '2' or '3'
            return prefix:sub(1, 5):upper() .. tier
        end

        local words = {}
        for word in n:gmatch("[%w']+") do words[#words + 1] = word end
        if #words == 0 then return '?' end
        if #words > 1 then
            local first = HUD_SHORT.words[words[1]] or words[1]:sub(1, 4)
            return (first .. words[2]:sub(1, 1)):upper()
        end
        local word = words[1]
        if #word <= 6 then return word:upper() end
        return word:sub(1, 5):upper()
    end

    local base, roman = name:match('^(.-)%s+([IVX]+)$')
    if base and HUD_ROMAN[roman] then
        local stem = base_short(base)
        local digit = HUD_ROMAN[roman]
        local short = stem .. digit
        -- Four characters keeps the line and the rank readable when the tile is too narrow for
        -- the full label; hud_fit_label trims it only when even that does not fit.
        local tiny = #stem >= 3 and (stem:sub(1, 1) .. stem:sub(-2) .. digit) or short:sub(1, 3)
        return short, tiny, base, roman, tonumber(digit)
    end

    local short = base_short(name)
    return short, short:sub(1, 3), nil, nil, nil
end

-- END HUD label rules

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
        targets = key == 'spells' and {
            Healing = 'stpc', Buff = 'stpc', Debuff = 'selected', Nuke = 'selected',
            Zoning = 'selected', Avatar = 'selected', Other = 'selected',
        } or nil,
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
        show_hud = true,
        show_abilities = false,
        show_spells = false,
        show_trusts = false,
        show_weapon_skills = false,
        show_battle_info = false,
        show_party_info = false,
        show_mounts = false,
        show_inventory = false,
        show_target = true,
        -- The in-game EquipViewer.  On by default: the collapsed bar names the set being worn,
        -- which is the piece of state the icons alone cannot show.
        show_equipview = true,
        edit = false,
        opacity = 0.9,
        menu_hide = true,
        sc_target = 0,
        types = types,
        positions = hud_copy_positions(nil),
        battle = battle,
        party = party,
        -- The Mount HUD's own strip of the character file: where it sits, the picture
        -- size, and which mount the player picked (-1: the one being ridden, if any).
        mounts = { x = 760, y = 120, selected = -1, columns = 4, size = 128 },
        -- The Target Debuffs window: on by default, dragged like the other windows, and
        -- placed just under the action windows on a 1280-wide screen.
        target = { x = 900, y = 100 },
        -- The Magic Bag window had a draggable ImGui title bar but no saved place.  It now
        -- keeps its own position like the other hubs.
        magic_bag = { x = 560, y = 120 },
        -- The Equip View window: the in-game EquipViewer.  Collapsed it names the set the
        -- phase engine is wearing; expanded it draws the 4x4 equipment grid.
        equipview = { x = -1, y = -1 },
        -- Native ImGui collapse is per-window state; remember it so a login lands on the
        -- same minimized bars.  Window IDs are the stable ### ids used by Begin.
        collapsed = {
            fanxi_battle = false, fanxi_party = false,
            ['fanxi-target'] = false, ['inventory-hud'] = false, ['fanxi-equipview'] = false,
        },
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
    if key == 'spells' then
        if type(raw.targets) == 'table' then
            local count = 0
            for tab, mode in pairs(raw.targets) do
                if type(tab) == 'string' and #tab <= 24 and count < 24
                    and (mode == 'selected' or mode == 'stnpc' or mode == 'stpc' or mode == 'me') then
                    spec.targets[tab] = mode
                    count = count + 1
                end
            end
        end
    end
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
    if type(raw.show_hud) == 'boolean' then state.show_hud = raw.show_hud end
    if type(raw.show_abilities) == 'boolean' then state.show_abilities = raw.show_abilities end
    if type(raw.show_spells) == 'boolean' then state.show_spells = raw.show_spells end
    if type(raw.show_trusts) == 'boolean' then state.show_trusts = raw.show_trusts end
    if type(raw.show_weapon_skills) == 'boolean' then state.show_weapon_skills = raw.show_weapon_skills end
    if type(raw.show_battle_info) == 'boolean' then state.show_battle_info = raw.show_battle_info end
    if type(raw.show_party_info) == 'boolean' then state.show_party_info = raw.show_party_info end
    if type(raw.show_mounts) == 'boolean' then state.show_mounts = raw.show_mounts end
    if type(raw.show_inventory) == 'boolean' then state.show_inventory = raw.show_inventory end
    if type(raw.show_target) == 'boolean' then state.show_target = raw.show_target end
    if type(raw.show_equipview) == 'boolean' then state.show_equipview = raw.show_equipview end
    -- The Scholar window is automatic when this is absent: a Scholar main job shows it,
    -- every other job hides it.  The launcher switch and //hud sch store true/false.
    if type(raw.show_sch) == 'boolean' then state.show_sch = raw.show_sch end
    do
        local target_pos = type(raw.target) == 'table' and raw.target or {}
        state.target.x = math.floor(hud_clamp(target_pos.x, -4000, 8000, state.target.x))
        state.target.y = math.floor(hud_clamp(target_pos.y, -4000, 8000, state.target.y))
        local bag_pos = type(raw.magic_bag) == 'table' and raw.magic_bag or {}
        state.magic_bag.x = math.floor(hud_clamp(bag_pos.x, -4000, 8000, state.magic_bag.x))
        state.magic_bag.y = math.floor(hud_clamp(bag_pos.y, -4000, 8000, state.magic_bag.y))
        local view_pos = type(raw.equipview) == 'table' and raw.equipview or {}
        state.equipview.x = math.floor(hud_clamp(view_pos.x, -4000, 8000, state.equipview.x))
        state.equipview.y = math.floor(hud_clamp(view_pos.y, -4000, 8000, state.equipview.y))
    end
    do
        local raw_collapsed = type(raw.collapsed) == 'table' and raw.collapsed or {}
        for _, key in ipairs({ 'fanxi_battle', 'fanxi_party', 'fanxi-target', 'inventory-hud',
                               'fanxi-equipview' }) do
            if type(raw_collapsed[key]) == 'boolean' then
                state.collapsed[key] = raw_collapsed[key]
            end
        end
    end
    state.battle, state.party = hub_sanitize(raw)
    do
        -- The Mount HUD: position, picture size, columns and the picked mount id.  The
        -- mount table is the client's, so the upper bound is just a sanity limit here;
        -- the window drops a selection the client cannot show.
        local picked = type(raw.mounts) == 'table' and raw.mounts or {}
        local mounts_prefs = state.mounts
        mounts_prefs.x = math.floor(hud_clamp(picked.x, -4000, 8000, mounts_prefs.x))
        mounts_prefs.y = math.floor(hud_clamp(picked.y, -4000, 8000, mounts_prefs.y))
        mounts_prefs.selected = math.floor(hud_clamp(picked.selected, -1, 63, mounts_prefs.selected))
        mounts_prefs.columns = math.floor(hud_clamp(picked.columns, 3, 6, mounts_prefs.columns))
        -- The card label is the mount's name: smaller cards make it unreadable, so an old
        -- saved 48-84 px thumbnail grows back to the legible floor.
        mounts_prefs.size = math.floor(hud_clamp(picked.size, 112, 180, mounts_prefs.size))
    end
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
            targets = hud_copy_map(spec.targets),
        }
    end
    local file = io.open(path, 'wb')
    if not file then return end
    file:write(json.encode({
        version = HUD_FILE_VERSION,
        show_hud = state.show_hud,
        show_abilities = state.show_abilities,
        show_spells = state.show_spells,
        show_trusts = state.show_trusts,
        show_weapon_skills = state.show_weapon_skills,
        show_battle_info = state.show_battle_info == true,
        show_party_info = state.show_party_info == true,
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
        show_mounts = state.show_mounts,
        show_inventory = state.show_inventory,
        show_target = state.show_target,
        show_equipview = state.show_equipview,
        show_sch = state.show_sch,
        equipview = { x = state.equipview.x, y = state.equipview.y },
        mounts = {
            x = state.mounts.x, y = state.mounts.y, selected = state.mounts.selected,
            columns = state.mounts.columns, size = state.mounts.size,
        },
        target = { x = state.target.x, y = state.target.y },
        magic_bag = { x = state.magic_bag.x, y = state.magic_bag.y },
        collapsed = {
            fanxi_battle = state.collapsed.fanxi_battle == true,
            fanxi_party = state.collapsed.fanxi_party == true,
            ['fanxi-target'] = state.collapsed['fanxi-target'] == true,
            ['inventory-hud'] = state.collapsed['inventory-hud'] == true,
            ['fanxi-equipview'] = state.collapsed['fanxi-equipview'] == true,
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
    -- The configurable support Trusts open a small menu (call/dismiss and Set actions)
    -- instead of casting immediately.  Every other Trust keeps the one-click call and the
    -- second-click release.
    if item.kind == 'trust' and hud.trust_configurable(item.id) then
        hud.trust_open(item)
        return
    end
    if item.kind == 'warp' then
        -- Saved places live on the server; //warp me is its own command path, not a spell cast, so
        -- the client's cast bar and target cursor are left alone.
        local ok, err = pcall(xi.chat.run,
            string.format('//warp me %d', math.floor(tonumber(item.slot) or 0)), 1)
        if not ok then xi.chat.write('HUD: ' .. tostring(err), 1) end
        return
    end
    if item.kind == 'ability' then
        local key = hud_ability_key(item.name)
        -- A row picked from the Phantom Roll / Quick Draw picker closes the picker first, then
        -- falls through to the normal /ja path below.
        if item.menu == 'cor' then hud.cor_menu.open = false end
        -- Phantom Roll and Quick Draw are menu doors, not the action itself: the client's
        -- list carries the 31 rolls and 8 shots as their own actions, and those live in the
        -- pickers rather than as a forty-tile page.
        if key == 'phantomroll' then
            hud.cor_open('roll')
            return
        elseif key == 'quickdraw' then
            hud.cor_open('shot')
            return
        end
        -- Call Beast and Bestial Loyalty both spend a jug in ammo.  The picker opens from
        -- either tile and calls with the tile the player used; Pet commands opens the
        -- command/Ready dialog instead of sending its no-op ability packet.
        if key == 'callbeast' or key == 'bestialloyalty' then
            hud.open_jug_picker(item)
            return
        elseif key == 'petcommands' then
            hud.pet_state.open = true
            hud.pet_state.at = os.clock()
            return
        end
    end
    if item.kind == 'trust' then
        -- A click is the one moment the answer has to be current: rescan instead of
        -- trusting the 0.4 s cache, so a Trust that just landed is released rather than
        -- called a second time.
        hud.next_trust_scan = 0
        hud_refresh_trusts()
    end
    if item.kind == 'trust' and hud_trust_active(item) then
        -- The client's own Remove/Release menu is an entity action no chat command exposes;
        -- the server's //trust release finds the alter ego by its spell id and despawns it.
        local ok, err = pcall(xi.chat.run,
            string.format('//trust release %d', tonumber(item.id) or 0), 1)
        if not ok then
            xi.chat.write('HUD: ' .. tostring(err), 1)
            return
        end
        if type(hud.active_trusts) == 'table' then
            hud.active_trusts[hud_trust_key(item.name)] = nil
        end
        return
    end
    local target
    if item.kind == 'trust' then
        target = '<me>'
    elseif item.kind == 'spell' then
        local spec = hud.state.types.spells
        local tab = hud.spell_tab or 'Other'
        local mode = spec.targets and spec.targets[tab] or 'selected'
        local flags = tonumber(item.targets) or 0
        -- Warp, Escape, Teleport-* and Recall-* are self-target travel spells, and Retrace is a
        -- self-cast party effect. Sending a monster target makes some clients refuse the cast, so
        -- the Zoning page casts those on <me> even when the player has one selected. Warp II is
        -- the one spell here that can name a party member, so it keeps the tab target.
        local namel = tostring(item.name or ''):lower()
        local party_target = has_bit(flags, 0x02) or has_bit(flags, 0x10)
        -- Match the names as well as the page: with folder tabs off the window has no Zoning
        -- title to compare with, and the travel spells still need <me>.
        local zoning = tab == 'Zoning' or namel:find('^warp') or namel:match('^escape$')
            or namel:find('^retrace') or namel:find('^teleport') or namel:find('^recall')
        local self_only = zoning and (not party_target or namel == 'retrace')
        if self_only then target = '<me>'
        elseif mode == 'stnpc' then target = '<stnpc>'
        elseif mode == 'stpc' then target = '<stpc>'
        elseif mode == 'me' then target = '<me>'
        else target = hud_target() end
    else
        target = hud_target()
    end
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
    local function seed_cool(key)
        hud.cool[key] = {
            start = os.clock(),
            total = total > 0 and total or 0,
            remaining = total > 0 and total or 1,
            pending = true,
            progress = 0,
        }
    end
    seed_cool(item.key)
    -- Steps share recast id 220, jigs 218, sambas 216 and every roll 193.  Seed every button
    -- in the same recast group so the clock appears on all of them, not just the one clicked;
    -- by_key also holds the rolls and shots that live in the pickers, not on the page.
    local recast_id = tonumber(item.recastId)
    if item.kind == 'ability' and recast_id and recast_id > 0 then
        for _, other in pairs(hud.by_key or {}) do
            if other.key ~= item.key and tonumber(other.recastId) == recast_id then
                seed_cool(other.key)
            end
        end
    end
end

-- BEGIN HUD cooldown rules
-- The client's ability recast table, written from the server's 0x119: slot -> u32 timer
-- (1/60 s) and u8 recast id.  A timer here is the server's own remaining time, so the HUD
-- can show a cooldown it did not start (a relogin restores them on the server).
local HUD_COOL_MIN = 0.02

local function hud_ability_recast_map(read)
    local out = {}
    if type(read) ~= 'function' then return out end
    for slot = 0, 30 do
        local ok, ticks, recast_id = pcall(read, slot)
        if ok and ticks and recast_id and ticks > 0 then
            local seconds = ticks / 60
            if seconds > (out[recast_id] or 0) then
                out[recast_id] = seconds
            end
        end
    end
    return out
end

-- Learn the cooldowns the server still has running when the HUD has no timer of its own.
-- The 0x119 table arrives on every login, before the client asks for its stats, so an
-- ability used before a logout comes back dark for its remaining time.  Without this the
-- tile looked ready and the server answered "not ready yet" when it was clicked.
local function hud_learn_live_cooldowns(cool, lists, live, now)
    local learned = false
    if type(live) ~= 'table' or next(live) == nil then return learned end
    for _, list in ipairs(lists or {}) do
        for _, item in ipairs(list or {}) do
            local recast_id = tonumber(item.recastId)
            local remaining = recast_id and recast_id > 0 and live[recast_id] or nil
            if remaining and remaining > HUD_COOL_MIN and not cool[item.key] then
                cool[item.key] = {
                    start = now,
                    total = remaining,
                    remaining = remaining,
                    pending = false,
                    progress = 0,
                }
                learned = true
            end
        end
    end
    return learned
end
-- END HUD cooldown rules

local function hud_update_cool(hud)
    local now = os.clock()
    -- Read the server's table every poll, not only while this HUD already has a timer: a
    -- relogin starts hud.cool empty and its restored cooldowns have to be learned from it.
    local ability_recasts = hud_ability_recast_map(game.ability_recast)
    hud_learn_live_cooldowns(hud.cool, { hud.abilities, hud.cor_rolls, hud.cor_shots },
        ability_recasts, now)
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
    -- The character's saved //warp places, pushed by the launcher through the hud command. They
    -- are not part of the character file: the server owns the rows, and a stale copy would
    -- outlive a rename or delete. Empty until the launcher has looked them up.
    warp_marks = {},
    -- Ranked spells reuse their line's tier-I menu icon (Aero II -> Aero's art), with the Roman
    -- rank drawn as a small badge.  The cache is by base spell name and lives for the session:
    -- the icons do not depend on the character.
    spell_base_icons = {},
    -- Every helix and every weather storm shares one generic icon in this client's menu icons
    -- (the helix ids 563..570 and the storm ids 555..562/648..655 all resolve to one picture),
    -- so those tiles borrow the element's tier-I nuke art instead: Pyrohelix/Firestorm read as
    -- Fire, Cryohelix/Hailstorm as Blizzard, and so on.
    element_icon_names = { 'Fire', 'Blizzard', 'Aero', 'Stone', 'Thunder', 'Water', 'Holy', 'Comet' },
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
    refresh_signature = nil, -- job pair plus the 0x0AC command-list fingerprint
    main_job = 0,
    sub_job = 0,
    -- Corsair's 0x0AC list carries every Phantom Roll and every elemental shot as its own
    -- action, which made the Abilities page a 39-tile scroll.  The page keeps Phantom Roll and
    -- Quick Draw as the two menu doors and these lists feed the pickers they open.
    -- `cor_roll_level` is the server's job_abilities level for the 31 rolls; the client's
    -- ability record has no level, so the picker's "level acquired" order comes from here.
    cor_rolls = {},
    cor_shots = {},
    cor_menu = { open = false, kind = 'roll', search = { '' }, sort = 'level' },
    cor_roll_level = {
        alliesroll = 89, avengersroll = 97, beastroll = 34, blitzersroll = 83,
        boltersroll = 76, castersroll = 79, chaosroll = 14, choralroll = 26,
        companionsroll = 95, corsairsroll = 5, corsairroll = 5, coursersroll = 81,
        dancersroll = 61, drachenroll = 23, evokersroll = 40, fightersroll = 49,
        gallantsroll = 55, healersroll = 20, huntersroll = 11, magussroll = 17,
        magusroll = 17, misersroll = 92, monksroll = 31, naturalistsroll = 67,
        ninjaroll = 8, puppetroll = 52, roguesroll = 43, runeistsroll = 70,
        samurairoll = 34, scholarsroll = 64, tacticiansroll = 86, warlocksroll = 46,
        wizardsroll = 58,
    },
    -- The elemental shots, in the order the client's ability ids already use
    -- (Fire, Ice, Wind, Earth, Thunder, Water, Light, Dark).
    cor_shot_order = {
        fireshot = 1, iceshot = 2, windshot = 3, earthshot = 4,
        thundershot = 5, watershot = 6, lightshot = 7, darkshot = 8,
    },
    imgui = nil,
    warned = false,
    reposition = false,
    -- Move mode's one-shot position requests.  `center[key]` parks that window in the middle of
    -- the back buffer the next time it draws (it can be hidden at reset time and shown later),
    -- and `clamp_positions` pulls every visible window back into a resolution that changed.
    center = {},
    clamp_positions = false,
    screen_width = 1280,
    screen_height = 720,
    -- Call Beast jugs.  `jugs` is the generated item id -> {item, pet, model, level, moves}
    -- catalogue (host/addons/lua/jugpets.lua); the two windows below are session state and
    -- never written to the character file.
    jugs = {},
    jug_order = {},
    jug_by_pet = {},
    jug_by_pet_short = {},
    -- Bags the client can equip from (the server's AUTO_EQUIP_BAGS): inventory and the
    -- eight Mog Wardrobes.  Storage bags can hold a jug but cannot put it in ammo.
    jug_bags = {
        [0] = true, [8] = true, [10] = true, [11] = true, [12] = true,
        [13] = true, [14] = true, [15] = true, [16] = true,
    },
    jug_state = {
        open = false, ability = '', action = 0, rows = {}, by_id = {}, at = 0,
    },
    pet_state = { open = false, at = 0 },
    pet_commands = {},
    pet_command_names = {
        fight = true, heel = true, leave = true, sic = true, stay = true,
        ready = true, reward = true, snarl = true, spur = true, runwild = true,
    },
    pet_last_jug = 0,
}
do
    local ok, data = pcall(require, 'xi.jugpets')
    hud.jugs = ok and type(data) == 'table' and data or {}
    for item_id, row in pairs(hud.jugs) do
        if type(row) == 'table' and type(row.pet) == 'string' then
            local key = row.pet:lower():gsub('%s+', ' ')
            hud.jug_by_pet[key] = item_id
            hud.jug_by_pet_short[key:sub(1, 15)] = item_id
            hud.jug_order[#hud.jug_order + 1] = item_id
        end
    end
    table.sort(hud.jug_order, function(a, b)
        return tostring(hud.jugs[a].item or '') < tostring(hud.jugs[b].item or '')
    end)
end
hud.save = hud_save

-- BEGIN COR roll menu
-- The Phantom Roll and Quick Draw pickers.  Both are plain lists on the `hud` table (no new
-- chunk-level locals: control.lua is at the Lua local limit), so this block also runs under the
-- standalone test in tests/cor_hud_test.py.
--
-- Lucky and unlucky totals by the same punctuation-stripped name as cor_roll_level.  The
-- picker prints them on every row and the tooltip spells them out; keep this table in sync
-- with server/fanxi_server/game/rolls.py (tests/cor_hud_test.py compares the two).
-- The client's own names for the 31 roll actions.  sets.JA["Phantom Roll"] is the
-- GearSwap convention for "every roll", but the client sends the individual roll's
-- action id, so the phase rule builder expands the door's set to all of these.
hud.cor_roll_names = {
    "Fighter's Roll", "Monk's Roll", "Healer's Roll", "Wizard's Roll",
    "Warlock's Roll", "Rogue's Roll", "Gallant's Roll", "Chaos Roll", "Beast Roll",
    "Choral Roll", "Hunter's Roll", "Samurai Roll", "Ninja Roll", "Drachen Roll",
    "Evoker's Roll", "Magus's Roll", "Corsair's Roll", "Puppet Roll",
    "Dancer's Roll", "Scholar's Roll", "Bolter's Roll", "Caster's Roll",
    "Courser's Roll", "Blitzer's Roll", "Tactician's Roll", "Naturalist's Roll",
    "Runeist's Roll", "Allies' Roll", "Miser's Roll", "Companion's Roll",
    "Avenger's Roll",
}
hud.cor_roll_lucky = {
    alliesroll = { 3, 10 }, avengersroll = { 4, 8 }, beastroll = { 4, 8 },
    blitzersroll = { 4, 9 }, boltersroll = { 3, 9 }, castersroll = { 2, 7 },
    chaosroll = { 4, 8 }, choralroll = { 2, 6 }, companionsroll = { 2, 10 },
    corsairsroll = { 5, 9 }, corsairroll = { 5, 9 }, coursersroll = { 3, 9 },
    dancersroll = { 3, 7 }, drachenroll = { 4, 8 }, evokersroll = { 5, 9 },
    fightersroll = { 5, 9 }, gallantsroll = { 3, 7 }, healersroll = { 3, 7 },
    huntersroll = { 4, 8 }, magussroll = { 2, 6 }, magusroll = { 2, 6 },
    misersroll = { 5, 7 }, monksroll = { 3, 7 }, naturalistsroll = { 3, 7 },
    ninjaroll = { 4, 8 }, puppetroll = { 3, 7 }, roguesroll = { 5, 9 },
    runeistsroll = { 4, 8 }, samurairoll = { 2, 6 }, scholarsroll = { 2, 6 },
    tacticiansroll = { 5, 8 }, warlocksroll = { 4, 8 }, wizardsroll = { 5, 9 },
}
-- Search matches either the raw name or the punctuation-stripped name, so "corsairs" finds
-- "Corsair's Roll" the same way the HUD's ability keys do.
function hud.cor_matches(item, needle)
    needle = needle ~= nil and tostring(needle):gsub('^%s+', ''):gsub('%s+$', '') or ''
    if needle == '' then return true end
    local name = tostring(item and item.name or '')
    if name:lower():find(needle:lower(), 1, true) then return true end
    local stripped = needle:lower():gsub('[^%w]', '')
    if stripped == '' then return true end
    return name:lower():gsub('[^%w]', ''):find(stripped, 1, true) ~= nil
end

-- Rolls sorted by the level they are learned at (the default, so a new Corsair sees the rolls
-- it can actually use first) or by name.  Ties fall back to the name, then the action id.
function hud.cor_roll_rows(search, sort)
    local rows = {}
    for _, item in ipairs(hud.cor_rolls or {}) do
        if hud.cor_matches(item, search) then rows[#rows + 1] = item end
    end
    table.sort(rows, function(a, b)
        local an, bn = tostring(a.name or ''):lower(), tostring(b.name or ''):lower()
        if sort ~= 'name' then
            local al, bl = tonumber(a.level) or 0, tonumber(b.level) or 0
            if al ~= bl then return al < bl end
        end
        if an == bn then return (tonumber(a.id) or 0) < (tonumber(b.id) or 0) end
        return an < bn
    end)
    return rows
end

-- The eight elemental shots, always in the client's own element order rather than the
-- alphabetical order the Abilities page used to show them in.
function hud.cor_shot_rows()
    local rows = {}
    for _, item in ipairs(hud.cor_shots or {}) do rows[#rows + 1] = item end
    table.sort(rows, function(a, b)
        local ao, bo = tonumber(a.order) or 0, tonumber(b.order) or 0
        if ao ~= bo then return ao < bo end
        return (tonumber(a.id) or 0) < (tonumber(b.id) or 0)
    end)
    return rows
end

function hud.cor_open(kind)
    local state = hud.cor_menu
    state.open = true
    state.kind = kind == 'shot' and 'shot' or 'roll'
    state.search[1] = ''
end
-- END COR roll menu

function hud.save_now()
    if hud.state and hud.path then hud_save(hud.state, hud.path) end
end

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
    -- Two flags can be absent in files written by an older build; normalise them before any
    -- window reads them, so an absent field means "off" rather than nil reaching the snapshot.
    hud.state.show_battle_info = hud.state.show_battle_info == true
    hud.state.show_party_info = hud.state.show_party_info == true
    hud.restore_collapsed = {}
    for _, key in ipairs({ 'fanxi_battle', 'fanxi_party', 'fanxi-target', 'inventory-hud',
                           'fanxi-equipview' }) do
        if hud.state.collapsed[key] == true then hud.restore_collapsed[key] = true end
    end
    hud.abilities, hud.spells, hud.trusts, hud.weapon_skills = {}, {}, {}, {}
    hud.cor_rolls, hud.cor_shots = {}, {}
    hud.warp_marks = {}
    hud.by_key, hud.cool = {}, {}
    hud.active_trusts = {}
    hud.next_trust_scan = 0
    hud.page = {}
    hud.center, hud.clamp_positions = {}, false
    hud.refresh_signature = nil
    hud.pet_commands = {}
    hud.pet_state.open = false
    hud.jug_state.open = false
    hud.cor_menu.open = false
    hud.trust_menu.open = false
    hud.trust_menu.mode = 'menu'
    hud.trust_menu.item = nil
    hud.trust_menu.trust_id = 0
    hud.trust_menu.actions = {}
    hud.trust_menu.by_id = {}
    hud.trust_menu.selected = {}
    hud.trust_menu.ids = {}
    hud.trust_menu.kinds = ''
    hud.trust_menu.main_job, hud.trust_menu.sub_job = 0, 0
    hud.trust_menu.auto = true
    hud.trust_menu.loading = false
    hud.trust_menu.notice = nil
    hud.pet_last_jug = 0
    hud.target_data, hud.target_error = nil, nil
    hud.target_at, hud.target_polling = 0, false
    hud.main_job, hud.sub_job = 0, 0
    hud.last_tp = nil
    hud.sc_start = nil
    hud.sc_step = nil
    hud.sc_tier = nil
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

-- The menu icon of the unranked spell that starts a line: Aero for Aero II, Blizzaga for
-- Blizzaga II, Cure for Cure V.  The game's own icon for a rank is only a Roman numeral tile;
-- drawing the line's art behind the rank makes a caster's element readable at a glance.
function hud.spell_base_icon(name)
    local cached = hud.spell_base_icons[name]
    if cached ~= nil then return cached or nil end
    local icon = 0
    local ok, spell = pcall(res.spell_by_name, name, 0)
    if ok and type(spell) == 'table' then
        icon = tonumber(spell.icon_hq) or 0
        if icon <= 0 or icon == 65535 then icon = tonumber(spell.icon_nq) or 0 end
    end
    hud.spell_base_icons[name] = icon > 0 and icon or false
    return icon > 0 and icon or nil
end

-- Element id (0 Fire ... 7 Dark) -> the menu art that names that element.  Used by the helix
-- and storm tiles, whose own client icons are all the same generic picture.
function hud.element_icon(element)
    local name = hud.element_icon_names[(tonumber(element) or 0) + 1]
    if not name then return nil end
    return hud.spell_base_icon(name)
end

-- A saved //warp tile uses the Warp spell's own menu icon so it reads as a travel action next to
-- the spells. The resource table knows the id even when this job pair cannot cast Warp.  Methods
-- on `hud` rather than new chunk-level locals: control.lua is at the Lua local limit.
function hud.warp_icon()
    if hud.warp_icon_cache ~= nil then return hud.warp_icon_cache end
    local icon = 0
    local ok, spell = pcall(res.spell, 261)
    if ok and type(spell) == 'table' then
        icon = tonumber(spell.icon_hq) or 0
        if icon <= 0 or icon == 65535 then icon = tonumber(spell.icon_nq) or 0 end
    end
    hud.warp_icon_cache = icon
    return icon
end

-- Rebuild the mark tiles among the spell tiles. Called after a job rebuild (which empties the
-- list) and whenever the launcher pushes a fresh list. A mark's key is m<slot>, so a slot keeps
-- its identity across a rename and a warp can never collide with a spell's s<id>.
function hud.apply_warps()
    for index = #hud.spells, 1, -1 do
        local item = hud.spells[index]
        if item.kind == 'warp' then
            table.remove(hud.spells, index)
            if hud.by_key[item.key] == item then hud.by_key[item.key] = nil end
        end
    end
    local marks = hud.warp_marks
    if type(marks) ~= 'table' then return end
    for _, mark in ipairs(marks) do
        local slot = math.floor(tonumber(mark.slot) or 0)
        if slot >= 1 and slot <= 1000 then
            local alias = tostring(mark.alias or ''):gsub('^%s+', ''):gsub('%s+$', '')
            local zone = tostring(mark.zone_name or ''):gsub('^%s+', ''):gsub('%s+$', '')
            -- A named mark reads best as its alias; an unnamed one is still useful as the zone
            -- name, with the slot in the tooltip (and in the server's own list).
            local name = alias ~= '' and alias or (zone ~= '' and zone or ('Warp ' .. slot))
            local item = {
                key = 'm' .. tostring(slot), kind = 'warp', id = slot, slot = slot,
                name = name, icon = hud.warp_icon(), recast = 0, level = 0,
                zone_name = zone ~= '' and zone or nil,
            }
            item.short, item.tiny = hud_short_name(item.name)
            hud.spells[#hud.spells + 1] = item
            hud.by_key[item.key] = item
        end
    end
    hud_sort_name(hud.spells)
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

-- The four windows are built from two sources: the job pair (abilities, spells, trusts) and
-- the client's 0x0AC command list (abilities and weapon skills).  A job change sends the new
-- 0x01B block before the final equipment, and the command list follows only once the new
-- weapon is on.  A signature of the job alone therefore rebuilt once, too early, and left the
-- old weapon's skills in the HUD until the next job change.  Fingerprint the command list as
-- well, so the rebuild that matters happens when the list actually settles; this covers both
-- `//job` and the Moogles' Change Job menu, which take different packet paths to the same pair.
local function hud_command_fingerprint()
    local ok, ids = pcall(game.ability_commands)
    if not ok or type(ids) ~= 'table' then return '0' end
    local count, hash = 0, 5381
    for i = 1, #ids do
        local id = tonumber(ids[i]) or 0
        if id > 0 then
            count = count + 1
            hash = (hash * 33 + id) % 4294967296
        end
    end
    return string.format('%d:%d', count, hash)
end

function hud.rebuild(force)
    local main = game.party_member(0, 'MainJob') or 0
    local main_level = game.party_member(0, 'MainJobLevel') or 0
    local sub = game.party_member(0, 'SubJob') or 0
    local sub_level = game.party_member(0, 'SubJobLevel') or 0
    local signature = string.format('%d:%d:%d:%d|%s', main, main_level, sub, sub_level,
                                    hud_command_fingerprint())
    if not force and hud.refresh_signature == signature then return end
    hud.refresh_signature = signature
    -- A roll picker left open across a job change would list the previous job's rolls.
    local job_changed = hud.main_job ~= main or hud.sub_job ~= sub
    if job_changed then hud.cor_menu.open = false end
    hud.main_job, hud.sub_job = main, sub
    -- A rebuild is often a weapon swap rather than a job change, and the abilities that
    -- survive it keep running recasts.  Move the timers to the new keys below instead of
    -- clearing them, so the bar does not reset to ready until the next poll.
    local previous_cool = hud.cool or {}
    hud.abilities, hud.spells, hud.trusts, hud.weapon_skills = {}, {}, {}, {}
    hud.cor_rolls, hud.cor_shots = {}, {}
    hud.by_key, hud.cool = {}, {}
    hud.pet_commands = {}

    local abilities = job_abilities().abilities or {}
    local pet_seen = {}
    for _, ability in ipairs(abilities) do
        local kind = tostring(ability.type or '')
        local aname = type(ability.name) == 'table' and (ability.name.en or ability.name[2] or ability.name[1]) or ability.name
        local key = type(aname) == 'string' and hud_ability_key(aname) or ''
        local pet_command = kind:find('PetCommand')
            or (hud.pet_command_names[key] and key ~= 'petcommands')
        if pet_command and type(aname) == 'string' and aname ~= '' and aname ~= '.'
            and not pet_seen[key] then
            pet_seen[key] = true
            local command = {
                key = 'p' .. tostring(ability.id),
                kind = kind:find('PetCommand') and 'pet_command' or 'ability',
                id = ability.id, name = aname, icon = ability.icon, recast = 0,
                recastId = ability.recastId, targets = ability.targets,
                ability_type = kind, command_key = key,
            }
            command.short, command.tiny = hud_short_name(command.name)
            hud.pet_commands[#hud.pet_commands + 1] = command
        end
        local skip = kind:find('BloodPact') or kind:find('PetCommand')
        if not skip and type(aname) == 'string' and aname ~= '' and aname ~= '.' then
            local item_key = hud_ability_key(aname)
            local item = {
                key = 'a' .. tostring(ability.id), kind = 'ability', id = ability.id,
                name = aname, icon = ability.icon, recast = 0,
                recastId = ability.recastId, level = 0,
                job = HUD_ABILITY_JOB[item_key], ability_type = kind,
            }
            item.short, item.tiny = hud_short_name(item.name)
            -- A COR's roll and shot actions become the two pickers' rows instead of tiles.
            -- Phantom Roll and Quick Draw themselves are the doors and stay on the page, so
            -- they are deliberately absent from both tables.
            local roll_level = hud.cor_roll_level[item_key]
            local shot_order = hud.cor_shot_order[item_key]
            if roll_level then
                item.level = roll_level
                item.menu = 'cor'
                local odds = hud.cor_roll_lucky[item_key]
                if odds then
                    item.lucky, item.unlucky = odds[1], odds[2]
                end
                hud.cor_rolls[#hud.cor_rolls + 1] = item
                hud.by_key[item.key] = item
            elseif shot_order then
                item.level = 40
                item.order = shot_order
                item.menu = 'cor'
                hud.cor_shots[#hud.cor_shots + 1] = item
                hud.by_key[item.key] = item
            else
                hud.abilities[#hud.abilities + 1] = item
                hud.by_key[item.key] = item
            end
        end
    end

    local spells = job_spells().spells or {}
    -- The client's spell table can carry two records with one name (the live table has Sleepga
    -- 273 and 363). The HUD casts by name, so a second tile would send the same /ma command;
    -- keep the first (lowest id, because job_spells sorts by name then id) and drop the rest.
    local seen_spell_names = {}
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
        local duplicate = item.kind == 'spell' and seen_spell_names[item.name]
        if item.kind == 'spell' then seen_spell_names[item.name] = true end
        if not duplicate then
            if item.kind == 'spell' then
                -- Kaustra is a two-hour-only spell: the client shows it in the normal list,
                -- but the server refuses it without Tabula Rasa.  Mark the tile so the grid
                -- can dim it and stop the click before it leaves the client.
                if item.id == 388 or item.name == 'Kaustra' then
                    item.requires_buff = 377 -- Tabula Rasa
                    item.requires_label = 'Tabula Rasa'
                    item.requires_tag = '2HR'
                end
                local lower = tostring(item.name):lower()
                if lower:find('helix', 1, true) then
                    item.helix = true
                    item.element_icon = hud.element_icon(item.element)
                end
                -- The weather storms are White Magic Enhancing spells; Blue Magic's
                -- "Feather Storm" and "Silent Storm" are a different school and stay put.
                if item.magic == 1 and item.skill_id == 34 and lower:find('storm', 1, true) then
                    item.element_icon = hud.element_icon(item.element)
                end
            end
            local short, tiny, base, roman, tier = hud_spell_parts(item.name, item.kind == 'spell')
            item.short, item.tiny = short, tiny
            -- Bard songs carry their family so the tile, its label and the page headings can
            -- share one colour without looking the family up every frame.
            if item.kind == 'spell' and item.magic == 5 then
                local song = HUD_SHORT.song_info(item.name)
                if song then item.song = song.role end
            end
            -- A ranked spell keeps the line's tier-I art and gets the Roman rank as a corner badge.
            -- Trusts are spells in the same table but draw their portrait, so only a real spell takes
            -- the menu art; a Trust whose name ends in II keeps its face.
            if item.kind == 'spell' and base then
                local icon = hud.spell_base_icon(base)
                if icon and icon > 0 then
                    item.original_icon = item.icon
                    item.icon = icon
                    item.tier = tier
                    item.tier_roman = roman
                end
                -- A song's label leaves the rank to the badge.  If this client has no
                -- unranked record for the line (some newer songs are rank-only), keep the
                -- badge anyway on the song's own note texture.
                if item.magic == 5 and tier then
                    item.tier = tier
                    item.tier_roman = roman
                end
            end
            local list = spell.magic == 8 and hud.trusts or hud.spells
            list[#list + 1] = item
            hud.by_key[item.key] = item
        end
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
    hud_sort_name(hud.pet_commands)
    hud.apply_warps()
    for key, cool in pairs(previous_cool) do
        if hud.by_key[key] then hud.cool[key] = cool end
    end
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
    -- Travel magic crosses several skills: Warp/Warp II are Divine, Escape/Retrace and the
    -- Teleport-*/Recall-* families are Enhancing. They share the one property that matters to
    -- the hub, a zone hand-off, so they group together before the skill fallback can call them a
    -- Buff or a Debuff. Saved //warp marks are not spells but ride the same Zoning page.
    if item.kind == 'warp' or n:find('^warp') or n:match('^escape$')
        or n:find('^retrace') or n:find('^teleport') or n:find('^recall') then
        return 'Zoning'
    end
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
            if n:find('klimaform', 1, true) then return 'Buff' end
            if n:match('^bio') then return 'Debuff' end
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
            or n:find('elegy', 1, true) or n:find('finale', 1, true)
            or n:find('nocturne', 1, true) or n:find('virelai', 1, true) then return 'Debuff' end
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
        -- A mark has no magic skill or element; keep it on the Zoning page whichever way the
        -- player groups the rest of the spell list.
        if item.kind == 'warp' then return 'Zoning' end
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
    spells_type = { 'Healing', 'Buff', 'Debuff', 'Nuke', 'Zoning', 'Avatar', 'Other' },
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
        targets = hud_copy_map(spec.targets),
    }
end

local function hud_snapshot_items(list)
    local out = {}
    for _, item in ipairs(list) do
        -- The launcher preview draws the same label as the game.  Songs keep their rank out
        -- of the label (the game tile shows it as an icon badge), so hand the preview the
        -- rank too, or a Paeon page would look like eight identical PAEON samples.
        out[#out + 1] = { key = item.key, name = item.name, short = item.short, tier = item.tier }
    end
    return out
end

-- The Scholar HUD is the one window whose default follows the job: shown for a Scholar
-- main or support job, absent on every other pair.  A plain "show" must not survive a job
-- change any more - the old rule kept the window on a RDM after a Scholar main - so the
-- job test comes first and only then the saved true/false.  The module scales a support
-- Scholar to level 49.  On the hud table rather than a local: hud_init() is at Lua's
-- 200-local limit.
hud.sch_visible = function()
    if not (hud.sch and hud.sch.active() == true) then return false end
    if hud.state.show_sch == true then return true end
    if hud.state.show_sch == false then return false end
    return true
end

function hud.snapshot()
    hud.ensure()
    -- The launcher's Control room reads the HUD counts even while the windows are off.
    -- Rebuild on a changed signature here too, so a job change at the Moogle (where no HUD
    -- frame runs because nothing is shown) still reaches the next metrics poll.
    if (game.player_index() or -1) >= 0 then hud.rebuild(false) end
    local types = {}
    for _, key in ipairs(HUD_TYPES) do types[key] = hud_copy_type(hud.state.types[key]) end
    return {
        show_hud = hud.state.show_hud,
        show_abilities = hud.state.show_abilities,
        show_spells = hud.state.show_spells,
        show_trusts = hud.state.show_trusts,
        show_weapon_skills = hud.state.show_weapon_skills,
        show_battle_info = hud.state.show_battle_info == true,
        show_party_info = hud.state.show_party_info == true,
        show_inventory = hud.state.show_inventory,
        show_target = hud.state.show_target,
        show_sch = hud.sch_visible(),
        sch = hud.sch and hud.sch.snapshot() or nil,
        show_battle_hud = (hud.battle and hud.battle.camp_hud_visible
            and hud.battle.camp_hud_visible()) == true,
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
        show_mounts = hud.state.show_mounts,
        show_equipview = hud.state.show_equipview == true,
        equipview = { x = hud.state.equipview.x, y = hud.state.equipview.y },
        mounts = {
            x = hud.state.mounts.x, y = hud.state.mounts.y,
            selected = hud.state.mounts.selected,
            columns = hud.state.mounts.columns, size = hud.state.mounts.size,
            riding = hud.mount_hud and hud.mount_hud.current() or nil,
            count = hud.mount_hud and hud.mount_hud.count() or 0,
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
    if key == 'spells' then
        if type(args.targets) == 'table' then
            local count = 0
            for tab, mode in pairs(args.targets) do
                if type(tab) == 'string' and #tab <= 24 and count < 24
                    and (mode == 'selected' or mode == 'stnpc' or mode == 'stpc' or mode == 'me') then
                    spec.targets[tab] = mode
                    count = count + 1
                end
            end
        end
        if type(args.target_tab) == 'string' and #args.target_tab <= 24
            and (args.target == 'selected' or args.target == 'stnpc' or args.target == 'stpc'
                 or args.target == 'me') then
            spec.targets[args.target_tab] = args.target
        end
    end
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

-- --- move mode --------------------------------------------------------------------------------

-- Enter move mode: every window can be dragged and an opaque Done box sits in the middle of the
-- screen.  `center` is `//hud move reset`: each window's next draw parks it in the middle of the
-- back buffer, the reliable place to find a window whose saved coordinate belongs to a larger
-- resolution (or a monitor that is gone).  A window that is hidden right now keeps its pending
-- centre, so switching it on later also brings it to the middle instead of an old off-screen pixel.
local function hud_battle_camp_hud(args)
    if hud.battle and hud.battle.request then
        pcall(hud.battle.request, args)
    end
end

local function hud_begin_edit(center)
    local state = hud.state
    state.edit = true
    state.show_hud = true
    hud_battle_camp_hud({ action = 'camp_hud', move = true, reset = center and true or false })
    if center then
        local x = math.floor((hud.screen_width or 1280) / 2)
        local y = math.floor((hud.screen_height or 720) / 2)
        for _, key in ipairs(HUD_TYPES) do
            state.positions[key] = { x = x, y = y }
            hud.center[key] = true
        end
        state.battle.x, state.battle.y = x, y
        state.party.x, state.party.y = x, y
        hud.center.battle, hud.center.party = true, true
    else
        -- Entering move mode is also a chance to pull a window from a larger resolution back in.
        hud.clamp_positions = true
    end
    hud_save(state, hud.path)
end

-- Leave move mode.  The drag handlers already write each new position into the state, so saving
-- here makes the in-game Done button and `//hud save` the same operation.
local function hud_finish_edit()
    local state = hud.state
    state.edit = false
    hud.clamp_positions = false
    hud_battle_camp_hud({ action = 'camp_hud', move = false })
    hud_save(state, hud.path)
end

function hud.command(args)
    hud.ensure()
    local state = hud.state
    if type(args.show_hud) == 'boolean' then state.show_hud = args.show_hud end
    if type(args.show_abilities) == 'boolean' then state.show_abilities = args.show_abilities end
    if type(args.show_spells) == 'boolean' then state.show_spells = args.show_spells end
    if type(args.show_trusts) == 'boolean' then state.show_trusts = args.show_trusts end
    if type(args.show_weapon_skills) == 'boolean' then state.show_weapon_skills = args.show_weapon_skills end
    if type(args.show_battle_info) == 'boolean' then state.show_battle_info = args.show_battle_info end
    if type(args.show_party_info) == 'boolean' then state.show_party_info = args.show_party_info end
    if type(args.show_inventory) == 'boolean' then state.show_inventory = args.show_inventory end
    if type(args.show_target) == 'boolean' then
        state.show_target = args.show_target
        if state.show_target then hud.target_at = 0 end
    end
    if type(args.show_equipview) == 'boolean' then state.show_equipview = args.show_equipview end
    if type(args.show_sch) == 'boolean' then
        state.show_sch = args.show_sch
        if args.show_sch then state.show_hud = true end
    end
    if type(args.show_battle_hud) == 'boolean' and hud.battle then
        -- The in-game Battle HUD is the camp radar/roster window; cfg.show is the same
        -- setting its title-bar X and the Battle profile page use.
        local ok, result, err = pcall(hud.battle.request,
            { action = 'camp_hud', show = args.show_battle_hud })
        if not ok then
            xi.chat.write('Battle HUD: ' .. tostring(result), 1)
        elseif result == nil and err then
            xi.chat.write('Battle HUD: ' .. tostring(err), 1)
        end
    end
    if type(args.inventory) == 'table' then
        hud.inventory_data = args.inventory
    end
    if type(args.show_mounts) == 'boolean' then
        state.show_mounts = args.show_mounts
        if state.show_mounts then
            hud.mount_hud.grid_epoch = (hud.mount_hud.grid_epoch or 0) + 1
        end
    end
    if type(args.mounts) == 'table' then
        -- The Mount HUD is also reachable from the launcher's Control page: selection,
        -- thumbnail size and column count travel the same way the other window prefs do.
        local prefs = state.mounts
        local picked = args.mounts
        if picked.selected ~= nil then
            prefs.selected = math.floor(hud_clamp(picked.selected, -1, 63, prefs.selected))
        end
        if picked.columns ~= nil then
            prefs.columns = math.floor(hud_clamp(picked.columns, 3, 6, prefs.columns))
        end
        if picked.size ~= nil then
            prefs.size = math.floor(hud_clamp(picked.size, 112, 180, prefs.size))
        end
        if picked.x ~= nil then prefs.x = math.floor(hud_clamp(picked.x, -4000, 8000, prefs.x)) end
        if picked.y ~= nil then prefs.y = math.floor(hud_clamp(picked.y, -4000, 8000, prefs.y)) end
    end
    if type(args.edit) == 'boolean' then
        if args.edit then hud_begin_edit(false) else hud_finish_edit() end
    end
    if args.opacity ~= nil then state.opacity = hud_clamp(args.opacity, 0.45, 1, state.opacity) end
    if type(args.menu_hide) == 'boolean' then state.menu_hide = args.menu_hide end
    if args.reset_positions then
        state.positions = hud_copy_positions(nil)
        hud.reposition = true
    end
    if args.center_positions then hud_begin_edit(true) end

    local type_key = type(args.type) == 'string' and args.type or nil
    local has_type_fields = args.layout ~= nil or args.columns ~= nil or args.size ~= nil
        or args.labels ~= nil or args.font ~= nil or args.tabs ~= nil or args.group ~= nil
        or args.custom_groups ~= nil or args.assign_key ~= nil
        or args.target ~= nil or args.targets ~= nil or args.target_tab ~= nil
    if type_key and HUD_TYPE_INFO[type_key] then
        hud_apply_type(state.types[type_key], type_key, args)
    elseif has_type_fields then
        -- Older launchers sent layout fields without a type. Apply them to every window so that
        -- build keeps working, while a new launcher always names the tab it is editing.
        for _, key in ipairs(HUD_TYPES) do hud_apply_type(state.types[key], key, args) end
    end

    -- The launcher owns the server lookup for //warp marks, so it pushes the rows here. They are
    -- deliberately not written into the character file: the server's table is the one copy that
    -- rename and delete edit, and a saved mark outliving those would be a stale destination.
    if type(args.warp_marks) == 'table' then
        local marks, seen = {}, {}
        for _, raw in ipairs(args.warp_marks) do
            if #marks >= 1000 then break end
            if type(raw) == 'table' then
                local slot = math.floor(tonumber(raw.slot) or 0)
                if slot >= 1 and slot <= 1000 and not seen[slot] then
                    seen[slot] = true
                    marks[#marks + 1] = {
                        slot = slot,
                        alias = type(raw.alias) == 'string' and raw.alias:sub(1, 48) or '',
                        zone_name = type(raw.zone_name) == 'string' and raw.zone_name:sub(1, 48) or '',
                    }
                end
            end
        end
        hud.warp_marks = marks
        hud.apply_warps()
    end

    if state.show_abilities or state.show_spells or state.show_trusts or state.show_weapon_skills then
        hud.rebuild(false)
    end
    -- A hidden HUD has no Done box to click, so it cannot stay in move mode.
    if not state.show_hud then
        state.edit = false
        hud.clamp_positions = false
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

-- Recast timers are read at a glance: 300 s -> "5m", 299 s -> "4m59s", 45 s -> "45s".
-- Round up so the clock never flashes "4m60s" just before it expires.
local function hud_recast_time(seconds)
    local total = math.max(0, math.ceil(tonumber(seconds) or 0))
    if total < 60 then return string.format('%ds', total) end
    local minutes = math.floor(total / 60)
    local rest = total % 60
    if rest == 0 then return string.format('%dm', minutes) end
    return string.format('%dm%ds', minutes, rest)
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

-- BEGIN HUD spell sections -- tests/spell_sections_test.py extracts this region and runs it.
-- Every spell page is split into named sections.  The tab still picks the broad kind
-- (Healing/Buff/Debuff/Nuke/Zoning); these sections give the page the smaller headings a
-- player scans by: Cures/Raises, Protect & Shell, Bars, each nuke element, and a Helix block.
-- The layout counts every heading before it draws the body, so no section is clipped.
hud.spell_section_order = {
    Nuke = { 'Helix', 'Fire', 'Ice', 'Wind', 'Earth', 'Thunder', 'Water', 'Light', 'Dark',
        'Blue Magic', 'Non-elemental' },
    Healing = { 'Cures', 'Raises', 'Status Removal', 'Healing' },
    Buff = { 'Protect & Shell', 'Regen & Refresh', 'Haste', 'Bars', 'Storms', 'Enspells',
        'Songs', 'Ninjutsu', 'Blue Magic', 'Geomancy', 'Utility', 'Enhancing' },
    Debuff = { 'Sleep', 'Bind & Gravity', 'Dispel', 'Slow', 'Paralyze', 'Poison',
        'Blind & Silence', 'Absorb', 'Songs', 'Ninjutsu', 'Blue Magic', 'Geomancy',
        'Enfeebling' },
    Zoning = { 'Warp Marks', 'Warp', 'Teleport', 'Recall', 'Escape & Retrace' },
    Avatar = { 'Avatars', 'Spirits' },
}

-- Section colours and hints.  Nuke sections carry the skillchain the element forms under
-- Immanence, which is the number a Scholar is actually looking for on that page.  The hint is
-- dropped by the header if the window is too narrow, so it never pushes the heading out.
hud.spell_section_style = {
    Helix = { color = { 110, 230, 230 }, hint = 'Elemental DoT' },
    Fire = { color = { 255, 112, 80 }, hint = 'Liquefaction' },
    Ice = { color = { 120, 200, 255 }, hint = 'Induration' },
    Wind = { color = { 120, 230, 150 }, hint = 'Detonation' },
    Earth = { color = { 214, 178, 108 }, hint = 'Scission' },
    Thunder = { color = { 196, 142, 255 }, hint = 'Impaction' },
    Water = { color = { 90, 160, 255 }, hint = 'Reverberation' },
    Light = { color = { 255, 240, 170 }, hint = 'Transfixion' },
    Dark = { color = { 170, 120, 220 }, hint = 'Compression' },
    ['Non-elemental'] = { color = { 190, 190, 200 }, hint = 'Meteor' },
    Cures = { color = { 130, 240, 160 }, hint = 'HP' },
    Raises = { color = { 255, 226, 140 }, hint = 'Revival' },
    ['Status Removal'] = { color = { 170, 220, 255 }, hint = 'Na spells' },
    Healing = { color = { 130, 240, 160 }, hint = '' },
    ['Protect & Shell'] = { color = { 170, 200, 255 }, hint = 'Defense' },
    ['Regen & Refresh'] = { color = { 140, 230, 170 }, hint = 'Over time' },
    Haste = { color = { 255, 220, 130 }, hint = 'Attack speed' },
    Bars = { color = { 150, 210, 255 }, hint = 'Resistance' },
    Storms = { color = { 200, 170, 255 }, hint = 'Weather' },
    Enspells = { color = { 255, 170, 110 }, hint = 'Added damage' },
    Songs = { color = { 240, 190, 230 }, hint = 'Bard' },
    Ninjutsu = { color = { 190, 210, 255 }, hint = 'Utsusemi' },
    ['Blue Magic'] = { color = { 120, 200, 220 }, hint = 'Blue' },
    Geomancy = { color = { 160, 220, 160 }, hint = 'Indi / Geo' },
    Utility = { color = { 170, 200, 210 }, hint = 'Utility' },
    Enhancing = { color = { 170, 210, 200 }, hint = '' },
    Sleep = { color = { 170, 150, 255 }, hint = 'Sleep' },
    ['Bind & Gravity'] = { color = { 200, 170, 140 }, hint = 'Bind / Gravity' },
    Dispel = { color = { 220, 170, 255 }, hint = 'Dispel' },
    Slow = { color = { 160, 200, 255 }, hint = 'Slow' },
    Paralyze = { color = { 255, 220, 120 }, hint = 'Paralyze' },
    Poison = { color = { 160, 220, 120 }, hint = 'Poison / Bio / Dia' },
    ['Blind & Silence'] = { color = { 180, 180, 190 }, hint = 'Blind / Silence' },
    Absorb = { color = { 200, 140, 160 }, hint = 'Absorb' },
    Enfeebling = { color = { 190, 160, 230 }, hint = '' },
    ['Warp Marks'] = { color = { 120, 220, 255 }, hint = 'Saved places' },
    Warp = { color = { 120, 220, 255 }, hint = 'Warp' },
    Teleport = { color = { 140, 200, 255 }, hint = 'Teleport' },
    Recall = { color = { 150, 220, 200 }, hint = 'Recall' },
    ['Escape & Retrace'] = { color = { 180, 180, 255 }, hint = 'Escape / Retrace' },
    Avatars = { color = { 200, 180, 255 }, hint = 'Summons' },
    Spirits = { color = { 160, 220, 255 }, hint = 'Elemental' },
    Other = { color = { 160, 174, 192 }, hint = '' },
}

hud.spell_section_rank = function(kind, title)
    local order = hud.spell_section_order[kind]
    if order then
        for index, name in ipairs(order) do
            if name == title then return index end
        end
    end
    return 900
end

-- One spell's section.  Nukes are elemental first and helix first of all; the other pages
-- use the effect the spell is actually cast for.  A spell with no better home falls to the
-- page's generic bucket instead of disappearing.
hud.spell_section = function(item, kind)
    local n = tostring(item.name or ''):lower()
    kind = kind or hud_spell_kind(item)
    if kind == 'Nuke' then
        if item.helix or n:find('helix', 1, true) then return 'Helix' end
        local element = tonumber(item.element) or 0
        if element >= 0 and element <= 7 then return HUD_ELEMENTS[element + 1] end
        -- Blue Magic's physical spells carry no element; keep them in one Blue block instead
        -- of dropping forty breath/charge attacks into Non-elemental.
        if item.magic == 6 then return 'Blue Magic' end
        return 'Non-elemental'
    end
    if kind == 'Healing' then
        if n:match('^cure') or n:match('^cura') then return 'Cures' end
        if n:match('^raise') or n == 'arise' or n:match('^reraise') then return 'Raises' end
        if n == 'esuna' or n == 'erase' or n == 'sacrifice' or n:match('na$') then
            return 'Status Removal'
        end
        return 'Healing'
    end
    if kind == 'Buff' then
        if item.magic == 5 then return 'Songs' end
        if item.magic == 4 then return 'Ninjutsu' end
        if item.magic == 6 then return 'Blue Magic' end
        if item.magic == 7 then return 'Geomancy' end
        if n:find('protect', 1, true) or n:find('shell', 1, true) then
            return 'Protect & Shell'
        end
        if n:find('regen', 1, true) or n:find('refresh', 1, true) then
            return 'Regen & Refresh'
        end
        if n:find('haste', 1, true) then return 'Haste' end
        if n:match('^bar') then return 'Bars' end
        if n:find('storm', 1, true) then return 'Storms' end
        if n:match('^en') and (n:find('fire', 1, true) or n:find('blizzard', 1, true)
            or n:find('aero', 1, true) or n:find('stone', 1, true)
            or n:find('thunder', 1, true) or n:find('water', 1, true)
            or n == 'enlight' or n == 'endark') then
            return 'Enspells'
        end
        if n:find('blink', 1, true) or n:find('sneak', 1, true)
            or n:find('invisible', 1, true) or n:find('deodorize', 1, true)
            or n:find('stoneskin', 1, true) or n:find('phalanx', 1, true)
            or n:find('aquaveil', 1, true) or n:find('adloquium', 1, true)
            or n:find('animus', 1, true) then
            return 'Utility'
        end
        return 'Enhancing'
    end
    if kind == 'Debuff' then
        if item.magic == 5 then return 'Songs' end
        if item.magic == 4 then return 'Ninjutsu' end
        if item.magic == 6 then return 'Blue Magic' end
        if item.magic == 7 then return 'Geomancy' end
        if n:find('sleep', 1, true) then return 'Sleep' end
        if n:find('bind', 1, true) or n:find('gravity', 1, true) then return 'Bind & Gravity' end
        if n:find('dispel', 1, true) then return 'Dispel' end
        if n:find('slow', 1, true) then return 'Slow' end
        if n:find('paralyze', 1, true) then return 'Paralyze' end
        if n:find('poison', 1, true) or n:find('bio', 1, true) or n:find('dia', 1, true) then
            return 'Poison'
        end
        if n:find('blind', 1, true) or n:find('silence', 1, true) then
            return 'Blind & Silence'
        end
        if n:find('absorb', 1, true) then return 'Absorb' end
        return 'Enfeebling'
    end
    if kind == 'Zoning' then
        if item.kind == 'warp' then return 'Warp Marks' end
        if n:find('^warp') then return 'Warp' end
        if n:find('^teleport') then return 'Teleport' end
        if n:find('^recall') then return 'Recall' end
        if n == 'escape' or n:find('^retrace') then return 'Escape & Retrace' end
        return 'Warp'
    end
    if kind == 'Avatar' then
        if n:find('spirit', 1, true) then return 'Spirits' end
        return 'Avatars'
    end
    return 'Other'
end

-- A spell that a buff gates (Kaustra / Tabula Rasa) returns nil while the buff is up and the
-- reason string while it is not.  `has_buff` is passed in so the grid and the test can use the
-- same rule with the HUD's cached reader or a stub.
hud.spell_gate = function(item, has_buff)
    local buff = tonumber(item and item.requires_buff)
    if not buff or buff <= 0 then return nil end
    if type(has_buff) == 'function' and has_buff(buff) then return nil end
    return item.requires_label or 'a required buff'
end

-- Build the headings for one page.  A page that is mostly Bard songs keeps the older
-- family split (Attack/Haste/...), and a mixed page still puts its non-song spells under
-- Protect/Regen/Bars after the song blocks.  Element and custom grouping are already the
-- user's own split, and a flat list stays flat.
hud.spell_page_sections = function(spec, group)
    if spec.group == 'custom' or spec.group == 'element' or spec.group == 'none' then
        return nil
    end
    local songs, others = {}, {}
    for _, item in ipairs(group.items) do
        if item.magic == 5 then songs[#songs + 1] = item else others[#others + 1] = item end
    end
    local list = {}
    local function add_generic(items, base_order)
        local buckets = {}
        for _, item in ipairs(items) do
            local kind = hud_spell_kind(item)
            local title = hud.spell_section(item, kind)
            local bucket = buckets[title]
            if not bucket then
                local style = hud.spell_section_style[title] or hud.spell_section_style.Other
                bucket = {
                    title = title,
                    hint = style.hint or '',
                    color = style.color or { 160, 174, 192 },
                    order = base_order + hud.spell_section_rank(kind, title),
                    rank = #list + 1,
                    items = {},
                }
                buckets[title] = bucket
                list[#list + 1] = bucket
            end
            bucket.items[#bucket.items + 1] = item
        end
    end
    if #songs > 1 then
        local song_sections = HUD_SHORT.song_sections(songs)
        if song_sections then
            for _, section in ipairs(song_sections) do
                section.rank = #list + 1
                list[#list + 1] = section
            end
            -- Non-song buffs follow the song families rather than interrupting them.
            add_generic(others, 900)
            if #list < 2 then return nil end
            table.sort(list, function(a, b)
                if a.order ~= b.order then return a.order < b.order end
                return a.rank < b.rank
            end)
            return list
        end
    end
    add_generic(group.items, 0)
    if #list < 2 then return nil end
    table.sort(list, function(a, b)
        if a.order ~= b.order then return a.order < b.order end
        return a.rank < b.rank
    end)
    return list
end
hud.song_page_sections = hud.spell_page_sections
-- END HUD spell sections

-- A section heading: a coloured band, the title, an optional effect hint, then the group's
-- tiles.  The heading is the place the player looks when scanning a long page, so it carries
-- the group colour in full while the tiles only tint their border.
hud.section_header_height = function(spec)
    local font = math.max(9, math.min(11, hud_font_size(spec)))
    return font + 6
end
hud.song_header_height = hud.section_header_height

hud.draw_section_header = function(api, section, width, spec)
    local font = math.max(9, math.min(11, hud_font_size(spec)))
    local height = hud.section_header_height(spec)
    local draw = api.GetWindowDrawList()
    local x, y = api.GetCursorScreenPos()
    x, y = tonumber(x) or 0, tonumber(y) or 0
    local color = section.color or { 160, 174, 192 }
    local band = hud_color(color[1], color[2], color[3], 24)
    local accent = hud_color(color[1], color[2], color[3], 255)
    local rule = hud_color(color[1], color[2], color[3], 70)
    draw:AddRectFilled({ x, y }, { x + math.max(20, width), y + height }, band, 3, 0)
    draw:AddRectFilled({ x, y + 3 }, { x + 3, y + height - 3 }, accent, 1, 0)
    api.PushFont(nil, font)
    local title = tostring(section.title or ''):upper()
    local title_w, title_h = api.CalcTextSize(title)
    draw:AddText({ x + 9, y + (height - title_h) / 2 }, accent, title)
    local hint = tostring(section.hint or '')
    local hint_w = 0
    local available = math.max(20, width) - 19 - title_w
    if hint ~= '' then
        local hw, hh = api.CalcTextSize(hint)
        -- A narrow bar/three-column window keeps the heading and drops the family hint rather
        -- than spilling it over the scrollbar.
        if hw <= available - 4 then
            hint_w = hw
            draw:AddText({ x + 13 + title_w, y + (height - hh) / 2 },
                hud_color(158, 168, 180, 238), hint)
        end
    end
    local line_x = x + 19 + title_w + hint_w
    if line_x < x + width - 8 then
        draw:AddLine({ line_x, y + height / 2 }, { x + width - 6, y + height / 2 }, rule, 1)
    end
    api.PopFont()
    api.Dummy({ 0, height })
end
hud.draw_song_header = hud.draw_section_header

local function hud_fade(color, alpha)
    local r = color % 256
    local g = math.floor(color / 256) % 256
    local b = math.floor(color / 65536) % 256
    return hud_color(r, g, b, math.floor(math.max(0, math.min(1, alpha)) * 255))
end

-- Dancer TP-affordability data and helpers.  They live on the existing `hud` table rather
-- than in new chunk-level locals: control.lua is right at the Lua/LuaJIT 200-local limit,
-- and adding a dozen locals here stops the whole addon from compiling.
hud.dnc = {
    -- Job ability name key -> base TP cost.  Dancer is the only job with TP-costed job
    -- abilities; the numbers mirror server/fanxi_server/game/dancer.py and the key is
    -- hud_ability_key(name).  A missing entry means recast-only.
    cost = {
        curingwaltz = 200, curingwaltzii = 350, curingwaltziii = 500,
        curingwaltziv = 650, curingwaltzv = 800,
        healingwaltz = 200, divinewaltz = 400, divinewaltzii = 800,
        drainsamba = 100, drainsambaii = 100, drainsambaiii = 100,
        aspirsamba = 100, aspirsambaii = 100, hastesamba = 350,
    },
    waltz = {
        curingwaltz = true, curingwaltzii = true, curingwaltziii = true,
        curingwaltziv = true, curingwaltzv = true, healingwaltz = true,
        divinewaltz = true, divinewaltzii = true,
    },
    samba = {
        drainsamba = true, drainsambaii = true, drainsambaiii = true,
        aspirsamba = true, aspirsambaii = true, hastesamba = true,
    },
    -- "Waltz TP Cost" gear, item id -> TP removed.  Mirrors LandSandBoat's waltz_cost
    -- modifier (139, 5-TP units); migration 130 gives Desultor Tassets -50 TP.
    gear = { [16370] = 50 },
    -- Status ids from LandSandBoat's status_effects.yaml.
    trance = 376, contradance = 582, saber_dance = 410, fan_dance = 411,
    buff_cache = { at = -1, ids = {} },
    gear_cache = { at = -1, total = 0 },
}

-- Current buff ids, cached for a fraction of a second: hud_draw_cell runs once per icon
-- and the ability grid can show forty of them.
function hud.has_buff(id)
    local cache = hud.dnc.buff_cache
    local now = os.clock()
    if now - (cache.at or -1) > 0.15 then
        local ids = {}
        local function add(list)
            if type(list) ~= 'table' then return end
            for _, raw in ipairs(list) do
                local value = tonumber(raw) or 0
                if value > 0 then ids[value] = true end
            end
        end
        local ok, buffs = pcall(function() return game.player('Buffs') end)
        if ok then add(buffs) end
        if not next(ids) then
            local ok2, icons = pcall(function() return game.player('StatusIcons') end)
            if ok2 then add(icons) end
        end
        cache.at, cache.ids = now, ids
    end
    return cache.ids[tonumber(id) or 0] == true
end

function hud.waltz_gear_reduction()
    local cache = hud.dnc.gear_cache
    local now = os.clock()
    if now - (cache.at or -1) < 0.5 then
        return cache.total
    end
    local total = 0
    for _, item_id in pairs(worn_items()) do
        total = total + (hud.dnc.gear[tonumber(item_id) or 0] or 0)
    end
    cache.at, cache.total = now, total
    return total
end

-- Effective TP cost for one ability.  Returns cost, blocked reason, blocked flag.  A
-- non-Dancer ability (or a recast-only dance) is 0 and never gated on TP.
function hud.ability_tp_cost(item)
    if not item or item.kind ~= 'ability' then return 0, nil, false end
    local key = hud_ability_key(item.name)
    local base = hud.dnc.cost[key]
    if not base or base <= 0 then return 0, nil, false end
    local waltz = hud.dnc.waltz[key] == true
    if waltz and hud.saber_dance then
        return base, 'Unavailable while Saber Dance is active', true
    end
    if hud.dnc.samba[key] and hud.fan_dance then
        return base, 'Unavailable while Fan Dance is active', true
    end
    local cost = math.max(0, base - (waltz and (tonumber(hud.waltz_tp_reduction) or 0) or 0))
    if hud.trance then
        cost = 0
    elseif waltz and hud.contradance and tonumber(hud.main_job) == 19 then
        -- Contradance Effect at rank 20 is 3% x 20 = 60% off.
        cost = math.floor(cost * 40 / 100 + 0.5)
    end
    return cost, nil, false
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
    local tp = tonumber(hud.tp) or 0
    local ability_tp, ability_reason, ability_blocked = hud.ability_tp_cost(item)
    local ability_short = ability_tp > 0 and tp < ability_tp
    -- A buff-gated spell (Kaustra / Tabula Rasa) cannot be clicked while the buff is down.
    local gate_reason = hud.spell_gate(item, hud.has_buff)
    local gated = gate_reason ~= nil
    local enabled = (not is_ws or tp >= HUD_TP_COST)
        and not ability_blocked and not ability_short and not gated
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
    elseif item.kind == 'warp' then
        local lines = { item.name }
        if item.zone_name and item.zone_name ~= item.name then lines[#lines + 1] = item.zone_name end
        lines[#lines + 1] = string.format('Warp mark %d — click to //warp me %d',
            item.slot, item.slot)
        hover_text = table.concat(lines, '\n')
    elseif trust_active then
        if hud.trust_configurable(item.id) then
            hover_text = string.format('%s  (out — click for Dismiss / Set %s)',
                item.name, hud.trust_label(item.id))
        else
            hover_text = string.format('%s  (active — click again to release)', item.name)
        end
    elseif item.kind == 'trust' and hud.trust_configurable(item.id) then
        hover_text = string.format('%s  (click for Call / Set %s)',
            item.name, hud.trust_label(item.id))
    elseif item.kind == 'ability' then
        local lines = { item.name }
        local key = hud_ability_key(item.name)
        if key == 'phantomroll' then
            lines[#lines + 1] = 'Click to open the roll picker'
        elseif key == 'quickdraw' then
            lines[#lines + 1] = 'Click to open the elemental shot picker'
        end
        if (tonumber(item.level) or 0) > 0 then
            lines[#lines + 1] = string.format('Learned at level %d', tonumber(item.level))
        end
        if ability_blocked and ability_reason then
            lines[#lines + 1] = ability_reason
        end
        if ability_tp > 0 then
            if ability_short then
                lines[#lines + 1] = string.format('Requires %d TP (have %d)', ability_tp, tp)
            else
                lines[#lines + 1] = string.format('%d TP', ability_tp)
            end
            if hud.trance and not ability_blocked then
                lines[#lines + 1] = 'No TP cost while Trance is active'
            end
            if hud.contradance and hud.dnc.waltz[key] and tonumber(hud.main_job) == 19 then
                lines[#lines + 1] = 'Contradance discount applied'
            end
            if hud.dnc.waltz[key] and (tonumber(hud.waltz_tp_reduction) or 0) > 0 then
                lines[#lines + 1] = string.format('Waltz TP cost gear -%d TP',
                    tonumber(hud.waltz_tp_reduction) or 0)
            end
        end
        if cooling then
            lines[#lines + 1] = string.format('Recast %s', hud_recast_time(cooling.remaining))
        end
        hover_text = table.concat(lines, '\n')
    elseif gated then
        hover_text = string.format('%s  (requires %s)', item.name, gate_reason)
    elseif cooling then
        hover_text = string.format('%s  (%s)', item.name, hud_recast_time(cooling.remaining))
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
    elseif ability_blocked or ability_short or gated then
        edge = hud_color(255, 90, 80, 55)
    elseif ability_tp > 0 then
        edge = hud_color(89, 216, 242, 70)
    end
    -- A song's family colour sits on its border and note, so a page of 80 songs reads as a
    -- handful of coloured bands instead of one wall of identical white notes.
    if item.song and not cooling and not is_ws and not trust_active
        and not ability_blocked and not ability_short and not gated then
        local c = item.song.color
        edge = hud_color(c[1], c[2], c[3], 96)
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
    if not texture and item.element_icon then texture = hud_icon_texture(item.element_icon) end
    if not texture then texture = hud_icon_texture(item.icon) end
    -- A ranked spell replaced its numeral tile with the line's art; if that art is missing from
    -- this client's DAT, the numeral tile is still better than a lettered fallback.
    if not texture and item.original_icon then texture = hud_icon_texture(item.original_icon) end
    local icon_alpha = 255
    if is_ws then
        if not enabled then icon_alpha = 70
        elseif target > 0 and not match then icon_alpha = 105 end
    elseif ability_blocked or ability_short or gated then
        icon_alpha = 70
    end
    if texture then
        local tint = hud_color(255, 255, 255, icon_alpha)
        if item.song and not gated then
            local c = item.song.color
            tint = hud_color(c[1], c[2], c[3], icon_alpha)
        end
        draw:AddImage(texture, { icon_x, icon_y }, { icon_x + icon_size, icon_y + icon_size },
            { 0, 0 }, { 1, 1 }, tint)
    else
        draw:AddRectFilled({ icon_x, icon_y }, { icon_x + icon_size, icon_y + icon_size }, hud_color(52, 66, 78, 255), 4, 0)
        local initial = tostring(item.name or '?'):sub(1, 1):upper()
        api.PushFont(nil, font_size)
        local text_w, text_h = api.CalcTextSize(initial)
        draw:AddText({ icon_x + (icon_size - text_w) / 2, icon_y + (icon_size - text_h) / 2 },
            hud_fade(HUD_COLOR_TEXT, icon_alpha), initial)
        api.PopFont()
    end
    -- A ranked spell's line art carries the rank as a small Roman badge in the top-right corner,
    -- the way the client's own numeral tile would have said it, but without hiding the element.
    if item.tier_roman and icon_size >= 18 then
        local badge = tostring(item.tier_roman)
        local badge_font = math.max(8, math.min(10, math.floor(icon_size / 5)))
        api.PushFont(nil, badge_font)
        local badge_w, badge_h = api.CalcTextSize(badge)
        local badge_x = icon_x + icon_size - badge_w - 2
        local badge_y = icon_y + 1
        local badge_edge = hud_color(89, 216, 242, 70)
        if item.song then
            local c = item.song.color
            badge_edge = hud_color(c[1], c[2], c[3], 110)
        end
        draw:AddRectFilled({ badge_x - 2, badge_y - 1 },
            { badge_x + badge_w + 2, badge_y + badge_h + 1 }, hud_color(4, 12, 18, 214), 2, 0)
        draw:AddRect({ badge_x - 2, badge_y - 1 },
            { badge_x + badge_w + 2, badge_y + badge_h + 1 }, badge_edge, 2, 0, 1)
        draw:AddText({ badge_x, badge_y }, hud_color(255, 255, 255, 255), badge)
        api.PopFont()
    end
    -- The TP number sits on the icon so an affordable waltz and an unaffordable one are
    -- distinguishable at a glance, not only on hover.
    if ability_tp > 0 and icon_size >= 20 then
        local badge = tostring(ability_tp)
        api.PushFont(nil, 8)
        local badge_w, badge_h = api.CalcTextSize(badge)
        local badge_x = icon_x + icon_size - badge_w - 2
        local badge_y = icon_y + icon_size - badge_h - 1
        draw:AddRectFilled({ badge_x - 2, badge_y - 1 },
            { badge_x + badge_w + 2, badge_y + badge_h + 1 }, hud_color(4, 12, 18, 190), 2, 0)
        draw:AddText({ badge_x, badge_y },
            ability_short and hud_color(255, 120, 110, 255) or hud_color(115, 242, 148, 255),
            badge)
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
        elseif ability_blocked or ability_short or gated then
            label_color = hud_fade(HUD_COLOR_TEXT, 0.45)
        elseif trust_active then
            label_color = HUD_COLOR_WHITE
        end
        draw:AddText({ x + (w - text_w) / 2, y + h - label_h + 1 }, label_color, text)
        api.PopFont()
    end

    -- A buff-gated spell carries a small 2HR tag; it turns red while the gate is down and
    -- green while the buff is up, so the tile never looks silently broken.
    if item.requires_buff and item.requires_buff > 0 and icon_size >= 16 then
        local tag = item.requires_tag or '2HR'
        api.PushFont(nil, 8)
        local tag_w, tag_h = api.CalcTextSize(tag)
        local bx, by = icon_x + 1, icon_y + 1
        local badge_bg = gated and hud_color(82, 24, 24, 214) or hud_color(18, 64, 54, 214)
        local badge_fg = gated and hud_color(255, 176, 166, 255) or hud_color(150, 255, 208, 255)
        draw:AddRectFilled({ bx - 1, by - 1 }, { bx + tag_w + 2, by + tag_h + 1 }, badge_bg, 2, 0)
        draw:AddText({ bx, by }, badge_fg, tag)
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
        local label_text = hud_recast_time(remaining)
        api.PushFont(nil, math.max(8, font_size))
        local measured_w, measured_h = api.CalcTextSize(label_text)
        draw:AddText({ cx - measured_w / 2, cy - measured_h / 2 }, HUD_COLOR_WHITE, label_text)
        api.PopFont()
    end

    -- A support Trust's menu also opens while the Trust spell itself is cooling: setting
    -- its actions is a configuration action, not a cast, and the menu disables the call.
    if clicked and not hud.state.edit then
        if gated then
            xi.chat.write('HUD: ' .. tostring(item.name) .. ' requires ' .. gate_reason .. '.', 1)
        elseif enabled and (not cooling or trust_active or hud.trust_configurable(item.id)) then
            hud_click(hud, item)
        end
    end
end

-- Skillchain window bookkeeping. A weapon skill consumes all of the player's TP, so a drop
-- through 1000 marks the opening swing. The server's window is 11 s, with a 3 s delay before
-- the next weapon skill can link; a level-1 link keeps the full 11 s and a wider link shaves
-- one second off the remaining window.
local function hud_sc_clock()
    if not hud.sc_start then return nil end
    local elapsed = xi.clock() - hud.sc_start
    local total = hud_sc_window(hud.sc_step, hud.sc_tier)
    local remaining = total - elapsed
    if remaining <= 0 then return nil end
    return remaining, HUD_SC_DELAY - elapsed
end

local function hud_update_sc()
    local tp = math.floor(tonumber(game.party_member(0, 'TP')) or 0)
    local now = xi.clock()
    if hud.last_tp and hud.last_tp >= HUD_TP_COST and tp < HUD_TP_COST and hud.last_tp - tp >= 100 then
        local step = 1
        -- Only a WS inside the previous link's own window continues the chain.  The old
        -- fixed 12 s allowance carried the step into a new chain: a WS fired 11 s after
        -- the previous chain's last link reset the server to a fresh 11 s opener, while
        -- this counter called it step 4 (7 s) and showed a window three seconds shorter
        -- than the server's.  Use the step's real duration plus the close grace instead.
        local window = hud.sc_start and hud_sc_window(hud.sc_step, hud.sc_tier) or 0
        -- A WS inside the three-second action lockout is a fresh opener on the server,
        -- not the next link, so the HUD must not advance the step for it either.
        if hud.sc_start and now - hud.sc_start > HUD_SC_DELAY
                and now - hud.sc_start <= window + HUD_SC_GRACE then
            step = math.min(5, (hud.sc_step or 1) + 1)
        else
            hud.sc_tier = nil
        end
        hud.sc_start, hud.sc_step = now, step
    end
    if hud.sc_start and now - hud.sc_start > hud_sc_window(hud.sc_step, hud.sc_tier) + HUD_SC_GRACE then
        hud.sc_start, hud.sc_step, hud.sc_tier = nil, nil, nil
    end
    hud.last_tp, hud.tp = tp, tp
    -- Dancer TP-affordability state.  The server applies the same three modifiers to
    -- the actual TP charge: Trance waives it, Contradance's job-point row discounts
    -- waltzes, and equipped "Waltz TP Cost" gear takes a flat amount off.
    hud.trance = hud.has_buff(hud.dnc.trance)
    hud.contradance = hud.has_buff(hud.dnc.contradance)
    hud.saber_dance = hud.has_buff(hud.dnc.saber_dance)
    hud.fan_dance = hud.has_buff(hud.dnc.fan_dance)
    hud.waltz_tp_reduction = hud.waltz_gear_reduction()
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
    -- Remember the last size for commands that run outside a draw frame (`//hud move reset`
    -- needs a middle to start from before the next frame has measured anything).
    hud.screen_width, hud.screen_height = width, height
    return width, height
end

local function hud_list_width(api, key, groups, spec, font_size, icon_size)
    local max_text = 0
    local header_font = math.max(9, math.min(11, font_size))
    api.PushFont(nil, font_size)
    for _, group in ipairs(groups) do
        if group.title then max_text = math.max(max_text, hud_text_width(api, tostring(group.title):upper())) end
        -- A spell list draws a section title and hint on its own row; measure them too or a
        -- narrow list clips "Magic Defense / Carol, Scherzo" even though the spell names fit.
        local sections = key == 'spells' and hud.spell_page_sections(spec, group) or nil
        if sections then
            api.PushFont(nil, header_font)
            for _, section in ipairs(sections) do
                local text = tostring(section.title):upper()
                if section.hint and section.hint ~= '' then text = text .. '  ' .. section.hint end
                max_text = math.max(max_text, hud_text_width(api, text) + 8)
            end
            api.PopFont()
            for _, section in ipairs(sections) do
                for _, item in ipairs(section.items) do
                    max_text = math.max(max_text, hud_text_width(api, tostring(item.name or '')))
                end
            end
        else
            for _, item in ipairs(group.items) do
                max_text = math.max(max_text, hud_text_width(api, tostring(item.name or '')))
            end
        end
    end
    api.PopFont()
    return math.floor(max_text + icon_size + 31)
end

-- Folder tabs. The game window can hold one group per page, which keeps the common case (a
-- handful of spells in Buff, or one trust job) on screen without scrolling through every group.
local HUD_TAB_LABELS = {
    ['Healing'] = 'Heal', ['Buff'] = 'Buff', ['Debuff'] = 'Debuff', ['Nuke'] = 'Nuke',
    ['Zoning'] = 'Zoning', ['Avatar'] = 'Avatar', ['Other'] = 'Other',
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
        width = math.max(150, hud_list_width(api, key, measure, spec, font_size, math.min(28, spec.size)) + 8)
    elseif spec.layout == 'bar' then
        local visible = math.min(math.max(max_items, 1), visible_cap)
        width = math.max(180, visible * (spec.size + HUD_GRID_GAP) - HUD_GRID_GAP + 20)
    else
        width = spec.columns * (spec.size + HUD_GRID_GAP) - HUD_GRID_GAP + 12
    end

    local function measure(group)
        local natural = 0
        if not tabs_on and group.title then natural = natural + header_h end
        -- A Bard page draws a coloured heading per effect group and every group starts a new
        -- grid row / bar row.  Count those rows here or the window opens a scrollbar short and
        -- clips the last group.
        local sections = nil
        if key == 'spells' then
            sections = hud.spell_page_sections(spec, group)
            if sections then natural = natural + #sections * hud.section_header_height(spec) end
        end
        local count = #group.items
        if spec.layout == 'grid' then
            local rows = 0
            if sections then
                for _, section in ipairs(sections) do
                    rows = rows + math.max(1, math.ceil(#section.items / spec.columns))
                end
            else
                rows = math.max(1, math.ceil(count / spec.columns))
            end
            natural = natural + rows * cell_h + math.max(0, rows - 1) * HUD_GRID_GAP
        elseif spec.layout == 'list' then
            natural = natural + count * list_row
        elseif sections then
            natural = natural + #sections * cell_h + math.max(0, #sections - 1) * HUD_GRID_GAP
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
    return width, height, body_h, cell_h, list_row, tabs_on, active_index, tab_h, scroll_x,
        ws_header_h, content_h <= body_h
end

local function hud_mode_strip_height(spec)
    local font = hud_font_size(spec)
    return math.max(18, font + 8) + 4 + (font + 4)
end

local function hud_spell_modes(api, width, spec, tab_key)
    local modes = phase_plan and phase_plan.spell_modes or nil
    local n = #SPELL_GROUP_ORDER
    local gap = 4
    local font = hud_font_size(spec)
    local button_h = math.max(18, font + 8)
    local caption_h = font + 4
    tab_key = tab_key or 'Other'
    spec.targets = spec.targets or {}
    local target = spec.targets[tab_key] == 'stnpc' and 'stnpc'
        or spec.targets[tab_key] == 'stpc' and 'stpc'
        or spec.targets[tab_key] == 'me' and 'me' or 'selected'
    local target_short = target == 'stnpc' and 'NPC' or target == 'stpc' and 'PC'
        or target == 'me' and 'Me' or 'Sel'
    local target_w = math.max(48, math.min(78, math.floor(width * 0.13)))
    local button_w = modes and math.max(40, math.floor((width - 8 - target_w - gap * n) / n)) or target_w
    api.PushFont(nil, font)
    if api.Button('Tgt:' .. target_short .. '##hud-spell-target', { target_w, button_h }) then
        local next_target = target == 'selected' and 'stnpc' or target == 'stnpc' and 'stpc'
            or target == 'stpc' and 'me' or 'selected'
        spec.targets[tab_key] = next_target
        hud_save(hud.state, hud.path)
        if next_target == 'stnpc' then
            xi.chat.write('HUD: ' .. tab_key .. ' spells use the NPC sub-cursor (<stnpc>)', 1)
        elseif next_target == 'stpc' then
            xi.chat.write('HUD: ' .. tab_key .. ' spells use the party sub-cursor (<stpc>)', 1)
        elseif next_target == 'me' then
            xi.chat.write('HUD: ' .. tab_key .. ' spells cast on <me>', 1)
        else
            xi.chat.write('HUD: ' .. tab_key .. ' spells use the selected target', 1)
        end
    end
    local target_x0, target_y0 = api.GetItemRectMin()
    local target_x1, target_y1 = api.GetItemRectMax()
    local caption
    if target == 'stnpc' then
        caption = 'Target: NPC sub-cursor (<stnpc>). Click for the party cursor.'
    elseif target == 'stpc' then
        caption = 'Target: party sub-cursor (<stpc>). Tab picks a party member.'
    elseif target == 'me' then
        caption = 'Target: <me> (self). Click for the selected target.'
    else
        caption = 'Target: selected (<t>/<me>). Click for the NPC cursor.'
    end
    if modes then
        api.SameLine(0, gap)
        for index, group_key in ipairs(SPELL_GROUP_ORDER) do
            local group = SPELL_GROUPS[group_key]
            local mode_key = modes[group_key] or group.default
            local label = group.short .. ':' .. mode_short(group_key, mode_key)
            if api.Button(label .. '##spell-mode-' .. group_key, { button_w, button_h }) then
                local mode_index = 1
                for i, mode in ipairs(group.modes) do
                    if mode.key == mode_key then mode_index = i break end
                end
                local next_mode = group.modes[(mode_index % #group.modes) + 1].key
                xi.tasks.spawn(function()
                    local ok, err = set_spell_mode(group_key, next_mode)
                    if ok then
                        xi.chat.write('Modes: ' .. spell_mode_summary(), 1)
                    else
                        xi.chat.write('Modes: ' .. tostring(err), 1)
                    end
                end)
            end
            if index < n then api.SameLine(0, gap) end
        end
    end
    api.NewLine()
    if api.IsMouseHoveringRect({ target_x0, target_y0 }, { target_x1, target_y1 }) then
        api.TextColored({ 0.72, 0.82, 0.86, 0.95 }, caption)
    end
    api.PopFont()
    return button_h + 4 + caption_h
end

local function hud_window(api, key, title, groups)
    local state = hud.state
    local spec = state.types[key]
    local edit = state.edit
    local width, height, body_h, cell_h, list_row, tabs_on, active_index, tab_h, scroll_x,
        ws_header_h, content_fits = hud_layout(api, key, spec, groups)
    -- The mode strip lives above the scrolling body. Grow the window by its height so the
    -- window itself never scrolls; only the spell body keeps its scrollbar.
    local mode_strip_h = 0
    if key == 'spells' then
        mode_strip_h = hud_mode_strip_height(spec)
        height = height + mode_strip_h + 4
    end
    local screen_w, screen_h = hud_screen_size(api)
    local position = state.positions[key] or HUD_DEFAULT_POSITIONS[key]
    local snap = hud.reposition or hud.clamp_positions or false
    if hud.center[key] then
        -- //hud move reset: park the window (not just its top-left) in the middle of the screen.
        position.x = math.floor((screen_w - width) / 2)
        position.y = math.floor((screen_h - height) / 2)
        hud.center[key] = nil
        snap = true
    end
    if edit or snap then
        -- The saved position may belong to a resolution that no longer exists; keep the whole
        -- window inside the back buffer while it is being placed, so it can always be grabbed.
        position.x = math.max(4, math.min(position.x, math.max(4, screen_w - width - 4)))
        position.y = math.max(4, math.min(position.y, math.max(4, screen_h - height - 4)))
    else
        -- A resolution change must not leave a window with its title bar off screen.
        if position.x + width > screen_w then position.x = math.max(4, screen_w - width - 4) end
        if position.y + height > screen_h then position.y = math.max(4, screen_h - height - 4) end
    end
    -- While the user drags, FirstUseEver lets ImGui own the window position; a reset snaps it.
    api.SetNextWindowPos({ position.x, position.y }, (snap or not edit) and 1 or 4)
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(state.opacity)
    -- The window is fixed-size; a window scrollbar would only duplicate the body's or show
    -- over empty space. Let the body own scrolling.
    -- NoBringToFrontOnFocus keeps the Done box above a window being dragged in move mode.
    local flags = edit and (2 + 8 + 32 + 256 + 8192) or (1 + 2 + 4 + 8 + 32 + 256)
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
        if key == 'spells' then
            hud.spell_tab = active.title or 'Other'
            hud_spell_modes(api, width, spec, hud.spell_tab)
        end
        local child_flags = scroll_x and 2048 or 0
        -- Content that already fits should not draw a scrollbar just because the child is one
        -- item-spacing taller than its contents.
        if content_fits and not scroll_x then child_flags = child_flags + 8 end
        api.PushStyleVar(2, { 0, 0 }) -- cell rows use the window's 4 px padding, not another 8
        api.BeginChild('hud-body-' .. key, { 0, math.max(40, body_h) }, 0, child_flags)
        local list_groups = tabs_on and { { title = nil, items = active.items } } or groups
        local body_width = math.max(20, width - 8)
        local mode = spec.layout == 'list' and 'list' or spec.layout == 'bar' and 'bar' or 'grid'
        local cell_width = mode == 'list' and body_width or spec.size
        local row_h = mode == 'list' and list_row or cell_h
        local function draw_cells(items)
            for index, item in ipairs(items) do
                if mode == 'grid' then
                    if (index - 1) % spec.columns > 0 then api.SameLine(0, HUD_GRID_GAP) end
                elseif mode == 'bar' and index > 1 then
                    api.SameLine(0, HUD_GRID_GAP)
                end
                hud_draw_cell(api, spec, item, cell_width, row_h, mode)
            end
            if mode ~= 'list' and #items > 0 then api.NewLine() end
        end
        local function draw_group(group, show_header)
            if show_header and group.title then
                hud_draw_group_header(api, key, group.title, hud_font_size(spec))
            end
            -- On a Bard page the flat list splits into effect groups.  The headings and their
            -- colours are the index into the page; the top-level Buff/Debuff tab still owns
            -- targeting and the mode strip.
            local sections = key == 'spells' and hud.spell_page_sections(spec, group) or nil
            if sections then
                for _, section in ipairs(sections) do
                    hud.draw_section_header(api, section, body_width, spec)
                    draw_cells(section.items)
                end
            else
                draw_cells(group.items)
            end
        end
        for _, group in ipairs(list_groups) do draw_group(group, not tabs_on) end
        api.EndChild()
        api.PopStyleVar(1)
    end
    if edit then
        if api.TextColored then
            api.TextColored({ 0.35, 0.85, 0.95, 1 },
                'Drag the title bar; click Done or type //hud save when finished.')
        else
            api.Text('Drag the title bar to move; click Done or //hud save to finish.')
        end
    end
    if edit then
        local px, py = api.GetWindowPos()
        local current = state.positions[key]
        -- Only a drag moves a window.  Reading the position on idle frames would turn an ImGui
        -- relocation the user did not ask for into a saved position.
        local dragging = api.IsMouseDown(0) or api.IsMouseReleased(0)
        if current and dragging and (math.abs(px - current.x) > 0.5 or math.abs(py - current.y) > 0.5) then
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

hud.force_pos = { fanxi_battle = true, fanxi_party = true }

local function hub_window_begin(api, title, id, x, y, width, height, opacity, summary, close,
                                extra_flags, skin)
    local screen_w, screen_h = hud_screen_size(api)
    local edit = hud.state.edit
    width = math.min(width, math.max(320, screen_w - 8))
    height = math.min(height, math.max(240, screen_h - 8))
    x = math.max(4, math.min(x or 24, screen_w - width - 4))
    y = math.max(4, math.min(y or 80, screen_h - height - 4))
    local center_key = id == 'fanxi_battle' and 'battle' or id == 'fanxi_party' and 'party' or nil
    local centered = center_key ~= nil and hud.center[center_key] == true
    if centered then
        hud.center[center_key] = nil
        x = math.floor((screen_w - width) / 2)
        y = math.floor((screen_h - height) / 2)
    end
    local force = centered or hud.force_pos[id] or hud.clamp_positions
    hud.force_pos[id] = nil
    api.SetNextWindowPos({ x, y }, force and 1 or 4) -- FirstUseEver otherwise, so a drag stays put
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(opacity or 0.95)
    api.PushStyleVar(2, { 6, 6 })       -- WindowPadding
    api.PushStyleVar(14, { 5, 5 })      -- ItemSpacing
    -- The summary rides on the title bar only while the window is collapsed.  Caching the
    -- state means the title changes on the next frame after the caret is clicked, which is
    -- exactly when ImGui reopens the title bar.
    local heading = title
    if hud.state.collapsed[id] and summary and summary ~= '' then
        heading = title .. '  ' .. summary
    end
    -- Once: the saved collapsed state sets the first appearance; the caret owns it afterwards.
    hud.collapse_prepare(api, id)
    -- NoBringToFrontOnFocus keeps the Done box above a hub that is being dragged in move mode.
    local open = api.Begin(heading .. '###' .. id, close,
        2 + 256 + (edit and 8192 or 0) + (extra_flags or 0))
    local wx, wy = api.GetWindowPos()
    local now_collapsed = hud.collapse_observe(api, id)
    -- A hub may paint its own frame over the ImGui title bar.  It runs after Begin (so the
    -- caption is hidden under the paint) and before the collapsed early-out (so a minimised
    -- bar keeps the same frame).  It gets the window rectangle and whether the window is
    -- collapsed, and is responsible for its own clip: the content clip starts below the bar.
    if skin then
        local ww, wh = api.GetWindowSize()
        skin(api, wx, wy, ww, wh, now_collapsed)
    end
    if not open then
        api.End()
        api.PopStyleVar(2)
        return nil, width, height, wx, wy
    end
    if edit then
        local ww, hh = api.GetWindowSize()
        api.GetWindowDrawList():AddRect({ wx, wy }, { wx + ww, wy + hh }, HUD_COLOR_ACCENT, 0, 0, 2)
    end
    return open, width, height, wx, wy
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
-- the window is shown and the user has not asked to keep the native one, turn that one off; the
-- whole HUD being hidden takes it down too.  Either way, put back whatever was there afterwards.
hud.native_fps_prior = nil
local function hub_native_fps_sync()
    if not xi.fx then return end
    local hide = not hud.state.show_hud
        or (hud.state.show_battle_info and not hud.state.battle.native_fps)
    if hide then
        if hud.native_fps_prior == nil then
            local ok, value = pcall(xi.fx, 'fps')
            hud.native_fps_prior = ok and (tonumber(value) or 1) or 1
        end
        pcall(xi.fx, 'fps', 0)
    elseif hud.native_fps_prior ~= nil then
        pcall(xi.fx, 'fps', hud.native_fps_prior)
        hud.native_fps_prior = nil
    end
end

-- --- battle tracker ---------------------------------------------------------------------------

hud.damage_messages = {
    [1] = true, [2] = true, [67] = true, [185] = true, [187] = true,
    [227] = true, [228] = true, [264] = true,
}
for m = 287, 383 do hud.damage_messages[m] = true end

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
                elseif value > 0 and hud.damage_messages[message] then
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
                    -- The tier of the chain just formed decides the next window: a
                    -- level-1 link keeps the full 11 s so the loop can continue.
                    local sc_id = HUD_SC_PROC[add_message - 287]
                    if sc_id then hud.sc_tier = HUD_SC_TIER[sc_id] end
                end
            elseif me and target_id == me and actor ~= me then
                if value > 0 and hud.damage_messages[message] then
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
    local summary = ''
    if hud.state.collapsed.fanxi_battle then
        local snap = battle_snapshot()
        local average = snap.tp.average
        summary = string.format('DPS %s  ·  TP/s %.1f  ·  %.0f FPS',
            hub_num(snap.dps60), average and average.tp_per_sec or 0, hub_fps.value or 0)
    end
    local screen_h = select(2, hud_screen_size(api))
    local width = 440
    local height = math.min(560, math.max(360, screen_h - 24))
    local open = hub_window_begin(api, 'Stats', 'fanxi_battle', state.x, state.y, width, height,
        state.opacity, summary)
    if not open then return end
    local label, color = battle_state()
    local px, py = api.GetWindowPos()
    local ww = api.GetWindowSize()
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

    api.End()
    api.PopStyleVar(2)
end

-- --- party info ------------------------------------------------------------------------------

hud.status_cache = {}
hud.status_tex = {}
hud.zone_cache = {}

local function hub_status_record(id)
    id = tonumber(id) or 0
    if id <= 0 or id == 255 or id == 65535 then return nil end
    local cached = hud.status_cache[id]
    if cached ~= nil then return cached or nil end
    local ok, info = pcall(res.status, id)
    if ok and info then
        local name = info.name_utf8 or info.name
        if type(name) == 'table' then name = name.en or name.ja or '' end
        name = tostring(name or '')
        if name ~= '' then cached = { id = id, name = name, info = info } end
    end
    hud.status_cache[id] = cached or false
    return cached or nil
end

local function hub_status_texture(id)
    id = tonumber(id) or 0
    if id <= 0 or not xi.ui or not xi.ui.texture_memory then return nil end
    local cached = hud.status_tex[id]
    if cached ~= nil then return cached or nil end
    local ok, rgba, width, height = pcall(res.status_icon_rgba, id)
    if ok and type(rgba) == 'string' and width and height and #rgba == width * height * 4 then
        local texture = xi.ui.texture_memory(rgba, width, height)
        if texture and texture ~= 0 then
            hud.status_tex[id] = texture
            return texture
        end
    end
    hud.status_tex[id] = false
    return nil
end

local function hub_zone_name(id)
    id = tonumber(id) or 0
    if id <= 0 then return nil end
    local cached = hud.zone_cache[id]
    if cached ~= nil then return cached or nil end
    local ok, zone = pcall(res.zone, id)
    if ok and zone then
        local name = zone.name_utf8 or zone.name
        if type(name) == 'table' then name = name.en or name.ja or '' end
        cached = tostring(name or '')
    end
    hud.zone_cache[id] = cached or false
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
    local summary = ''
    if hud.state.collapsed.fanxi_party then
        local snapshot = hub_party_snapshot()
        local count = #snapshot.members
        local low = 100
        for _, member in ipairs(snapshot.members) do
            if (tonumber(member.hpp) or 0) < low then low = tonumber(member.hpp) or 0 end
        end
        summary = count == 0 and 'No party members'
            or string.format('%d member%s  ·  low HP %d%%', count,
                count == 1 and '' or 's', low)
    end
    local busted = hud.has_buff(309)
    if busted then summary = summary .. '  ·  BUSTED' end
    local screen_h = select(2, hud_screen_size(api))
    local width = 492
    local height = math.min(620, math.max(360, screen_h - 24))
    local opacity = state.replace and 1 or state.opacity
    local open = hub_window_begin(api, 'Party Info', 'fanxi_party', state.x, state.y, width,
        height, opacity, summary)
    if not open then return end
    local px, py = api.GetWindowPos()
    local ww, wh = api.GetWindowSize()
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
    if busted then
        api.SameLine(0, 10)
        local bust_icon = hub_status_texture(309)
        if bust_icon then api.Image(bust_icon, { 16, 16 }) end
        api.SameLine(0, 4)
        hub_text(api, HUB_C.red, 'BUST')
    end

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
    -- One click: drop every online sub from any old party, then invite it here.
    api.SameLine(0, 12)
    if hub_button(api, 'Make party##party-make', HUB_C.green, 100) then
        xi.chat.run('//makeparty', 1)
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

    api.End()
    api.PopStyleVar(2)
end

-- --- the Mount HUD ----------------------------------------------------------------------------
-- Every mount the client knows, each with a picture.  Names and ids come from the game's own
-- mounts.names table (res), so a client update that adds a mount appears here without a change;
-- the pictures are <data>/mounts/<id>.jpg, captured from the client itself by
-- tools/capture_mount_previews.py.  What the character is riding is read back out of the last
-- 0x037 the server sent — mount_id at 0x73 and Chocobo_Index in Flags0 bits 13-15 — which is the
-- same pair the client's own Mount menu follows, so the HUD stays right when a mount was called
-- by another box's //mount all or from the game's menu.
hud.mount_hud = { list = nil, textures = {}, grid_epoch = 0 }

function hud.mount_hud.entries()
    local cache = hud.mount_hud
    if cache.list then return cache.list end
    local entries = {}
    local ok, count = pcall(res.string_count, 'mounts.names', 0)
    if ok and type(count) == 'number' and count > 0 then
        for id = 0, count - 1 do
            local name = nil
            local ok_name, value = pcall(res.string, 'mounts.names', id, 0, true)
            if ok_name and type(value) == 'string' and value ~= '' then name = value end
            local description = ''
            local ok_desc, text = pcall(res.string, 'mounts.descriptions', id, 0, true)
            if ok_desc and type(text) == 'string' then description = text end
            entries[#entries + 1] = {
                id = id,
                name = name or ('Mount ' .. tostring(id + 1)),
                description = description,
            }
        end
    end
    cache.list = entries
    return entries
end

function hud.mount_hud.count()
    return #hud.mount_hud.entries()
end

function hud.mount_hud.current()
    local ok, raw = pcall(xi.packets.last, false, 0x037)
    if not ok or type(raw) ~= 'string' or #raw < 0x78 then return nil end
    local function byte_at(offset) return raw:byte(offset + 1) or 0 end
    local mount_id = byte_at(0x73)
    local flags0 = byte_at(0x28) + byte_at(0x29) * 256
        + byte_at(0x2A) * 65536 + byte_at(0x2B) * 16777216
    if mount_id > 0 then return mount_id end
    -- Mount 0 is the personal chocobo, and 0 is also "on foot": the chocobo index in Flags0
    -- bits 13-15 is what tells the two apart.
    if math.floor(flags0 / 8192) % 8 > 0 then return 0 end
    return nil
end

function hud.mount_hud.texture(id)
    local cache = hud.mount_hud.textures
    local cached = cache[id]
    if cached ~= nil then return cached or nil end
    local handle = nil
    -- A picture the player put in <data>/mounts wins: it is the one they chose to see.
    if xi.ui and xi.ui.texture_file and xi.fs and xi.fs.path then
        local root = (xi.paths and xi.paths.data or '') .. 'mounts/'
        for _, path in ipairs({ root .. id .. '.jpg', root .. id .. '.png' }) do
            local ok, value = pcall(xi.ui.texture_file, xi.fs.path(path))
            if ok and type(value) == 'number' and value ~= 0 then
                handle = value
                break
            end
        end
    end
    -- Otherwise the gallery is the build's own: assets/mounts/<id>.jpg embedded as
    -- "mountart/<id>" (tools/embed_lua.py), so every client has a picture for every mount.
    if not handle and xi.embedded and xi.ui and xi.ui.texture_memory then
        local ok, bytes = pcall(xi.embedded, 'mountart/' .. tostring(id))
        if ok and type(bytes) == 'string' and #bytes > 0 then
            local decoded, value = pcall(xi.ui.texture_memory, bytes)
            if decoded and type(value) == 'number' and value ~= 0 then handle = value end
        end
    end
    cache[id] = handle or false
    return handle
end

function hud.mount_hud.call(id, team)
    local line
    if id == nil and team then
        -- No mount picked: the whole party gets a random one each.
        line = '//mount party'
    elseif id == nil then
        line = '//mount off'
    elseif team then
        line = '//mount party ' .. tostring(math.floor(id))
    else
        line = '//mount ' .. tostring(math.floor(id))
    end
    local ok, err = pcall(xi.chat.run, line, 1)
    if not ok then xi.chat.write('Mount HUD: ' .. tostring(err), 1) end
end

-- The strip under the picture: tall enough for a name at a readable size.
function hud.mount_hud.label_height(size)
    return math.max(24, math.floor(size * 0.21))
end

function hud.mount_hud.card(api, prefs, entry, size, riding)
    local label_h = hud.mount_hud.label_height(size)
    local card_h = size + label_h
    local clicked = api.InvisibleButton('mount-card-' .. tostring(entry.id), { size, card_h })
    local draw = api.GetWindowDrawList()
    local x0, y0 = api.GetItemRectMin()
    local x1, y1 = api.GetItemRectMax()
    local selected = prefs.selected == entry.id
    local is_riding = riding == entry.id
    local picture_y1 = y1 - label_h
    draw:AddRectFilled({ x0, y0 }, { x1, y1 }, HUB_CARD, 5)
    local texture = hud.mount_hud.texture(entry.id)
    if texture then
        draw:AddImage(texture, { x0 + 2, y0 + 2 }, { x1 - 2, picture_y1 - 2 }, { 0, 0 }, { 1, 1 },
            HUD_COLOR_WHITE)
    else
        api.PushFont(nil, math.max(14, math.floor(size * 0.36)))
        local initial = entry.name:gsub('[^%w]', ''):sub(1, 1):upper()
        if initial == '' then initial = tostring(entry.id + 1) end
        local lw, lh = api.CalcTextSize(initial)
        draw:AddText({ x0 + (size - lw) / 2, y0 + (picture_y1 - y0 - lh) / 2 },
            hud_fade(HUD_COLOR_TEXT, 0.5), initial)
        api.PopFont()
    end
    local label = entry.name
    local max_width = size - 4
    -- Start at a genuinely readable size and step down only for the longest names
    -- ("Spectral Chair", "Noble Chocobo"), never below the size that still reads.
    local font = math.max(15, math.floor(size * 0.15))
    api.PushFont(nil, font)
    local label_w, text_h = api.CalcTextSize(label)
    while font > 12 and api.CalcTextSize(label) > max_width do
        api.PopFont()
        font = font - 1
        api.PushFont(nil, font)
    end
    label_w, text_h = api.CalcTextSize(label)
    if label_w > max_width then
        while #label > 1 and api.CalcTextSize(label .. '..') > max_width do
            label = label:sub(1, #label - 1)
        end
        label = label:gsub('%s+$', '') .. '..'
        label_w, text_h = api.CalcTextSize(label)
    end
    draw:AddText({ x0 + (size - label_w) / 2, picture_y1 + (label_h - text_h) / 2 },
        is_riding and HUD_COLOR_WHITE or HUD_COLOR_TEXT, label)
    api.PopFont()
    local edge = is_riding and hub_rgba(HUB_C.green)
        or (selected and hub_rgba(HUB_C.cyan) or hub_rgba(HUB_CARD_EDGE))
    draw:AddRect({ x0, y0 }, { x1, y1 }, edge, 5, 0, (is_riding or selected) and 2 or 1)
    if is_riding then draw:AddCircleFilled({ x1 - 9, y0 + 9 }, 3.5, hub_rgba(HUB_C.green)) end
    if api.IsItemHovered() and entry.description ~= '' then
        api.SetItemTooltip(entry.description .. '\n//mount ' .. tostring(entry.id))
    end
    if clicked and not hud.state.edit then
        if prefs.selected ~= entry.id then
            prefs.selected = entry.id
            hud_save(hud.state, hud.path)
        end
        -- A double-click is the fast way to ride the card under the cursor.
        if api.IsMouseDoubleClicked(0) then hud.mount_hud.call(entry.id, false) end
    end
end

function hud.mount_hud.draw(api)
    local state = hud.state
    local prefs = state.mounts
    local entries = hud.mount_hud.entries()
    local riding = hud.mount_hud.current()
    local size = math.floor(hud_clamp(prefs.size, 112, 180, 128))
    local columns = math.floor(hud_clamp(prefs.columns, 3, 6, 4))
    local gap = 8
    local pad = 8
    local label_h = hud.mount_hud.label_height(size)
    local card_h = size + label_h
    -- Three rows fit on a 1080-tall screen with the enlarged cards; the grid scrolls.
    local rows = math.max(2, math.min(3, math.ceil(#entries / columns)))
    local body_h = rows * card_h + (rows - 1) * gap
    local width = pad * 2 + columns * size + (columns - 1) * gap
    local height = 96 + body_h + 34
    local open = hub_window_begin(api, 'Mounts  (' .. tostring(#entries) .. ')', 'fanxi_mounts',
        prefs.x, prefs.y, width, height, state.opacity)
    if not open then return end
    local px, py = api.GetWindowPos()
    local old_x, old_y = prefs.x, prefs.y
    prefs.x, prefs.y = px, py

    if #entries == 0 then
        hub_text(api, HUB_C.red, 'This client has no mount table (mounts.names).')
        api.End()
        api.PopStyleVar(2)
        return
    end
    if prefs.selected < 0 or prefs.selected > #entries - 1 then
        prefs.selected = riding or 0
    end
    local selected = entries[prefs.selected + 1]

    api.PushFont(nil, 13)
    hub_text(api, HUB_C.cyan, 'MOUNTS')
    api.PopFont()
    api.SameLine(0, 10)
    if riding then
        local current_entry = entries[riding + 1]
        hub_text(api, HUB_C.green,
            '● ' .. (current_entry and current_entry.name or ('Mount ' .. tostring(riding))))
    else
        hub_text(api, HUB_C.dim, 'on foot')
    end
    api.SameLine(0, 10)
    api.PushFont(nil, 12)
    hub_text(api, HUB_C.dim, 'pick one, then Mount or Mount party')
    api.PopFont()

    api.PushStyleVar(14, { gap, gap })  -- ImGuiStyleVar_ItemSpacing: the card grid's gutter
    -- A fresh child id per open: ImGui remembers a child's scroll, and reopening the window
    -- should start at the first mount rather than wherever the last visit left it.
    api.BeginChild('##mount-grid-' .. tostring(hud.mount_hud.grid_epoch), { 0, body_h }, 0, 0)
    for index, entry in ipairs(entries) do
        if (index - 1) % columns > 0 then api.SameLine(0, gap) end
        hud.mount_hud.card(api, prefs, entry, size, riding)
        if index % columns == 0 then api.NewLine() end
    end
    api.EndChild()
    api.PopStyleVar(1)

    if selected then
        hub_text(api, HUB_C.text, selected.name)
        if selected.description ~= '' then
            api.SameLine(0, 10)
            api.PushFont(nil, 9)
            hub_text(api, HUB_C.dim, selected.description)
            api.PopFont()
        end
    else
        hub_text(api, HUB_C.dim, 'Nothing selected.')
    end
    if hub_button(api, 'Mount', HUB_C.cyan, 74) then
        hud.mount_hud.call(prefs.selected, false)
    end
    api.SameLine(0, 6)
    if hub_button(api, 'Mount party', HUB_C.gold, 100) then
        hud.mount_hud.call(nil, true)
    end
    api.SameLine(0, 6)
    if hub_button(api, 'Dismount', HUB_C.orange, 82) then
        hud.mount_hud.call(nil, false)
    end
    api.SameLine(0, 6)
    if hub_button(api, 'Close', HUB_C.dim, 60) then
        state.show_mounts = false
        hud_save(state, hud.path)
    end

    if api.IsMouseReleased(0)
        and (math.abs((old_x or px) - px) > 0.5 or math.abs((old_y or py) - py) > 0.5) then
        hud_save(state, hud.path)
    end
    api.End()
    api.PopStyleVar(2)
end

-- --- the inventory / Magic Bag HUD ------------------------------------------------------------

hud.inv_bags = {
    { id = 0, name = 'Inventory' }, { id = 1, name = 'Mog Safe' },
    { id = 9, name = 'Mog Safe 2' }, { id = 2, name = 'Storage' },
    { id = 4, name = 'Mog Locker' }, { id = 5, name = 'Satchel' },
    { id = 6, name = 'Sack' }, { id = 7, name = 'Case' },
    { id = 8, name = 'Wardrobe 1' }, { id = 10, name = 'Wardrobe 2' },
    { id = 11, name = 'Wardrobe 3' }, { id = 12, name = 'Wardrobe 4' },
    { id = 13, name = 'Wardrobe 5' }, { id = 14, name = 'Wardrobe 6' },
    { id = 15, name = 'Wardrobe 7' }, { id = 16, name = 'Wardrobe 8' },
    { id = 17, name = 'Recycle Bin' },
}

-- The server sends a row's augment text plus the raw 24-byte extdata block.  The text is
-- what the item card lists; the block's bitfield is the only place the current rank and RP
-- live, and those are what tell two copies of the same cape apart.  This state has no bit
-- library, so the bitfield is decoded with plain division.
hud.inv_augment_text = function(value)
    if type(value) == 'table' then
        local lines = {}
        for _, line in ipairs(value) do lines[#lines + 1] = tostring(line) end
        return table.concat(lines, ' | ')
    end
    return tostring(value or '')
end

hud.inv_state = {
    search = { '' }, bag = 0, target = 0, tab = 'bags', sort = 'bag',
    selected = {}, pending = nil, scroll = 0,
    card = nil, card_open = nil,
}

hud.inv_name = function(id)
    local ok, item = pcall(res.item, id)
    if ok and item then
        local name = item.name_utf8 or item.name
        if type(name) == 'table' then name = name.en or name[1] end
        if type(name) == 'string' and name ~= '' then return name, item end
    end
    return tostring(id), nil
end

hud.inv_rows = function()
    local rows = {}
    local needle = tostring(hud.inv_state.search[1] or ''):lower()
    local only_recycle = hud.inv_state.tab == 'recycle'
    local wanted = nil
    if hud.inv_state.bag ~= 0 then wanted = hud.inv_bags[hud.inv_state.bag].id end
    local function bag_name(id)
        for _, bag in ipairs(hud.inv_bags) do
            if bag.id == id then return bag.name end
        end
        return 'Bag ' .. id
    end
    local function add(row)
        if needle == '' or row.name:lower():find(needle, 1, true) or
            row.bag_name:lower():find(needle, 1, true) then
            rows[#rows + 1] = row
        end
    end
    if hud.inventory_data and #hud.inventory_data > 0 then
        for _, item in ipairs(hud.inventory_data) do
            local source = item.source or 'bag'
            local container = tonumber(item.container) or 0
            local is_recycle = source == 'bag' and container == 17
            local visible = only_recycle and is_recycle or (not only_recycle and not is_recycle)
            if visible and (source ~= 'bag' or wanted == nil or wanted == container) then
                local name = tostring(item.name or ('Item ' .. tostring(item.item_id)))
                local extra = tostring(item.extra or '')
                add({
                    key = source == 'bag' and (container .. ':' .. tostring(item.slot))
                        or (source == 'claim'
                            and ('claim:' .. tostring(item.purchase_id)))
                        or (source .. ':' .. tostring(item.item_id) .. ':' .. extra),
                    source = source, bag = container,
                    bag_name = source == 'bag' and bag_name(container)
                        or (source == 'slip' and 'Magic Bag (slip)'
                            or (source == 'claim' and 'Claim Storage'
                                or 'Magic Bag (locker)')),
                    slot = tonumber(item.slot) or 0, id = tonumber(item.item_id) or 0,
                    count = tonumber(item.quantity) or 1, name = name,
                    slots = tonumber(item.slot_mask) or 0, extra = extra,
                    augments = hud.inv_augment_text(item.augments),
                    item_level = tonumber(item.item_level) or 0,
                    level = tonumber(item.level) or 0,
                    rare = tonumber(item.rare) or 0, ex = tonumber(item.ex) or 0,
                })
            end
        end
    else
        for _, bag in ipairs(hud.inv_bags) do
            if (only_recycle and bag.id == 17) or
                (not only_recycle and bag.id ~= 17 and (wanted == nil or wanted == bag.id)) then
                for slot = 1, 80 do
                    local id = tonumber(game.item(bag.id, slot, 'Id')) or 0
                    if id ~= 0 then
                        local count = tonumber(game.item(bag.id, slot, 'Count')) or 1
                        local name, item = hud.inv_name(id)
                        add({
                            key = bag.id .. ':' .. slot, source = 'bag', bag = bag.id,
                            bag_name = bag.name, slot = slot, id = id, count = count,
                            name = name, slots = item and tonumber(item.slots) or 0,
                            extra = '', augments = '',
                            item_level = item and tonumber(item.item_level) or 0,
                            level = item and tonumber(item.level) or 0,
                            rare = 0, ex = 0,
                        })
                    end
                end
            end
        end
    end
    table.sort(rows, function(a, b)
        if hud.inv_state.sort == 'name' then
            if a.name:lower() ~= b.name:lower() then return a.name:lower() < b.name:lower() end
        elseif hud.inv_state.sort == 'bag' then
            if a.bag ~= b.bag then return a.bag < b.bag end
        end
        if a.bag ~= b.bag then return a.bag < b.bag end
        return a.slot < b.slot
    end)
    return rows
end

hud.inv_run = function(line)
    local ok, err = pcall(xi.chat.run, line, 1)
    if not ok then xi.chat.write('Inventory: ' .. tostring(err), 1) end
end

-- BEGIN Magic Bag card helpers -- tests/magic_bag_test.py extracts this region and runs it.
-- Fixed columns for the row table.  The bag label column ends well before the action column:
-- "Magic Bag (locker)" is wider than the old 100 px gap and used to draw underneath the Pull
-- button.  The card button is inside the row, so keep its x clear of the label's max width.
-- These live as fields, not locals: the whole HUD is one function and is already at the
-- LuaJIT 200-local ceiling, so every new `local` here breaks the addon's compile.
hud.inv_layout = { name_width = 274, bag_x = 310, bag_width = 178, action_x = 500 }

hud.inv_close_card = function()
    hud.inv_state.card = nil
    hud.inv_state.card_open = nil
end

hud.inv_text = function(value)
    if type(value) == 'string' then return value end
    if type(value) == 'table' then return tostring(value.en or value[1] or '') end
    return ''
end

hud.inv_hex_bytes = function(hex)
    hex = tostring(hex or ''):gsub('%s+', '')
    if #hex < 24 or #hex % 2 ~= 0 or hex:find('[^%x]') then return nil end
    local bytes = {}
    for index = 1, #hex, 2 do
        bytes[#bytes + 1] = tonumber(hex:sub(index, index + 1), 16)
    end
    return bytes
end

-- 03 83 <pad u16> <bitfield u32> <bundle u32> <signature> is the client's bundled-augment
-- block (Odyssey, Limbus, Oboro, Unity).  Bits 2-17 are the accumulated RP, 18-22 the rank,
-- 23-24 the max-rank tier and 26-27 the RP curve; see server/fanxi_server/game/augments.py.
hud.inv_augment_meta = function(extra)
    local bytes = hud.inv_hex_bytes(extra)
    if not bytes or #bytes < 12 then return nil end
    if bytes[1] ~= 0x03 or bytes[2] ~= 0x83 then return nil end
    local value = bytes[5] + bytes[6] * 0x100 + bytes[7] * 0x10000 + bytes[8] * 0x1000000
    local path = math.floor(value % 4) + 1
    local tier = math.floor(value / 0x800000) % 4
    return {
        path = ('ABCD'):sub(path, path),
        rank = math.floor(value / 0x40000) % 0x20,
        max_rank = ({ 15, 20, 25, 30 })[tier + 1] or 30,
        rp = math.floor(value / 4) % 0x10000,
        curve = math.floor(value / 0x4000000) % 4,
        index = bytes[9] + bytes[10] * 0x100 + bytes[11] * 0x10000 + bytes[12] * 0x1000000,
    }
end

-- The server joins bundled rows with " | " and standard cape slots with ", ".  Split on the
-- separator the text actually uses so each augment gets its own line (a comma inside a stat
-- row, if one ever appears, stays put).
hud.inv_augment_lines = function(value)
    local out = {}
    if type(value) == 'table' then
        for _, entry in ipairs(value) do
            local line = tostring(entry):gsub('^%s+', ''):gsub('%s+$', '')
            if line ~= '' then out[#out + 1] = line end
        end
        return out
    end
    local text = tostring(value or '')
    if text == '' or text == 'not augmented' then return out end
    -- A bundle whose rank is below the row table's requirement is described as one
    -- status line: "Rank 15 (tier 3, path A), bundle 12".  Its commas are not slot
    -- separators; keep it intact so the card does not show three broken fragments.
    if text:match('^Rank %d+ %(tier %d+, path [A-D]%), bundle %d+$') then
        out[1] = text
        return out
    end
    local separator = text:find('|', 1, true) and '|' or ','
    for part in (text .. separator):gmatch('([^' .. separator .. ']*)' .. separator) do
        local line = part:gsub('^%s+', ''):gsub('%s+$', '')
        if line ~= '' then out[#out + 1] = line end
    end
    return out
end

hud.inv_fit = function(api, text, width)
    text = tostring(text or '')
    if text == '' or api.CalcTextSize(text) <= width then return text end
    local cut = text
    while #cut > 1 and api.CalcTextSize(cut .. '..') > width do
        cut = cut:sub(1, -2)
    end
    return cut:gsub('%s+$', '') .. '..'
end

-- The full item card: icon, description from the client's own DAT record, the server-decoded
-- augment rows and the block's current rank/RP.  It is modal so the table cannot act on the
-- wrong row while the card is open; Close returns to selection and Move/Pull/Recycle.
hud.inv_card = function(api)
    local state = hud.inv_state
    local row = state.card
    if not row then return end
    if not state.card_open then
        api.OpenPopup('Item card###inv-card')
        state.card_open = true
    end

    local screen_w, screen_h = hud_screen_size(api)
    local width = math.min(500, math.max(360, screen_w - 60))
    local height = math.min(560, math.max(320, screen_h - 80))
    local card_close = { false }
    -- Only stage a size while the popup is really open: SetNextWindowSize would otherwise
    -- leak onto the next HUD window's Begin() if the modal could not open this frame.
    if api.IsPopupOpen('Item card###inv-card') then
        api.SetNextWindowSize({ width, height }, 8) -- ImGuiCond_Appearing
    end
    if not api.BeginPopupModal('Item card###inv-card', card_close, 0) then
        -- Escape, a closed parent window or another popup can leave the card state
        -- behind; drop it instead of waiting forever for a popup that is not open.
        if state.card_open and not api.IsPopupOpen('Item card###inv-card') then
            hud.inv_close_card()
        end
        return
    end

    local ok, item = pcall(res.item, row.id)
    if not ok then item = nil end
    local name = row.name
    if item then
        local shown = hud.inv_text(item.name_utf8 or item.name)
        if shown ~= '' then name = shown end
    end
    local item_level = item and tonumber(item.item_level) or tonumber(row.item_level) or 0
    local level = item and tonumber(item.level) or tonumber(row.level) or 0

    local texture = hud_item_texture(row.id)
    if texture then api.Image(texture, { 52, 52 }) else api.Dummy({ 52, 52 }) end
    api.SameLine(0, 12)
    api.BeginGroup()
    api.PushFont(nil, 14)
    hub_text(api, HUB_C.text, name)
    api.PopFont()
    api.PushFont(nil, 10)
    local meta = { tostring(row.bag_name) }
    if row.source == 'bag' and tonumber(row.slot) and tonumber(row.slot) > 0 then
        meta[#meta + 1] = 'slot ' .. tostring(row.slot)
    end
    meta[#meta + 1] = 'x' .. tostring(row.count)
    if item_level > 0 then meta[#meta + 1] = 'iLvl ' .. tostring(item_level) end
    if level > 0 then meta[#meta + 1] = 'Lv ' .. tostring(level) end
    hub_text(api, HUB_C.dim, table.concat(meta, '  ·  '))
    local tags = {}
    if (tonumber(row.rare) or 0) ~= 0 then tags[#tags + 1] = 'RARE' end
    if (tonumber(row.ex) or 0) ~= 0 then tags[#tags + 1] = 'EX' end
    if #tags > 0 then hub_text(api, HUB_C.gold, table.concat(tags, '   ')) end
    api.PopFont()
    api.EndGroup()

    api.Separator()
    local _, avail = api.GetContentRegionAvail()
    local body_h = math.max(110, (tonumber(avail) or 300) - 48)
    api.BeginChild('##inv-card-body', { 0, body_h }, 1, 0)
    local description = item and hud.inv_text(item.description_utf8 or item.description) or ''
    description = description:gsub('\r', '')
    if description ~= '' then
        api.PushFont(nil, 11)
        for line in (description .. '\n'):gmatch('([^\n]*)\n') do
            if line == '' then api.Spacing() else api.TextWrapped(line) end
        end
        api.PopFont()
    else
        hub_text(api, HUB_C.dim, 'No item description available.')
    end

    api.Spacing()
    hub_text(api, HUB_C.gold, 'AUGMENTS')
    local lines = hud.inv_augment_lines(row.augments)
    local augment_meta = hud.inv_augment_meta(row.extra)
    if #lines == 0 and (not augment_meta or (augment_meta.rank or 0) <= 0) then
        hub_text(api, HUB_C.dim, 'No augment data for this copy.')
    else
        api.PushFont(nil, 11)
        for _, line in ipairs(lines) do
            api.PushTextWrapPos(0)
            api.TextWrapped('- ' .. line)
            api.PopTextWrapPos()
        end
        api.PopFont()
        if augment_meta and augment_meta.rank > 0 then
            local bits = { 'Path ' .. augment_meta.path }
            if augment_meta.rank == augment_meta.max_rank then
                bits[#bits + 1] = 'Rank ' .. tostring(augment_meta.rank)
            else
                bits[#bits + 1] = string.format('Rank %d / %d', augment_meta.rank,
                    augment_meta.max_rank)
            end
            bits[#bits + 1] = hub_num(augment_meta.rp) .. ' RP'
            hub_text(api, HUB_C.cyan, table.concat(bits, '  ·  '))
        end
    end
    api.EndChild()

    api.Separator()
    hub_text(api, HUB_C.dim, 'Close the card to select, move, pull or recycle the row.')
    if hub_button(api, 'Close', HUB_C.cyan, 100) then
        api.CloseCurrentPopup()
        hud.inv_close_card()
    end
    if card_close[1] then hud.inv_close_card() end
    api.EndPopup()
end
-- END Magic Bag card helpers

hud.inventory_window = function(api)
    local state = hud.state
    local summary = ''
    if hud.state.collapsed['inventory-hud'] then
        local rows = hud.inv_rows()
        local bag = 'All bags'
        if hud.inv_state.bag > 0 and hud.inv_bags[hud.inv_state.bag] then
            bag = hud.inv_bags[hud.inv_state.bag].name
        end
        summary = string.format('%d item%s  ·  %s', #rows, #rows == 1 and '' or 's', bag)
    end
    local pos = state.magic_bag or { x = 560, y = 120 }
    api.SetNextWindowPos({ pos.x, pos.y }, 4)
    api.SetNextWindowSize({ 780, 540 }, 1)
    local close = { state.show_inventory }
    hud.collapse_prepare(api, 'inventory-hud')
    local open = api.Begin('Magic Bag' .. (summary ~= '' and ('  ' .. summary) or '')
        .. '###inventory-hud', close, 0)
    local now_collapsed = hud.collapse_observe(api, 'inventory-hud')
    if not now_collapsed and close[1] ~= state.show_inventory then
        state.show_inventory = close[1]
        hud_save(state, hud.path)
    end
    if api.IsMouseReleased(0) then
        local wx, wy = api.GetWindowPos()
        if math.abs((wx or pos.x) - pos.x) > 0.5 or math.abs((wy or pos.y) - pos.y) > 0.5 then
            state.magic_bag.x, state.magic_bag.y = wx, wy
            hud_save(state, hud.path)
        end
    end
    if open then
        if api.Button('Bags##inv-tab', { 60, 20 }) then hud.inv_state.tab = 'bags' end
        api.SameLine(0, 5)
        if api.Button('Recycle##inv-tab', { 70, 20 }) then hud.inv_state.tab = 'recycle' end
        api.SameLine(0, 10)
        api.SetNextItemWidth(210)
        api.InputText('##inv-search', hud.inv_state.search, 64)
        api.SameLine(0, 8)
        local labels = { 'All bags' }
        for _, bag in ipairs(hud.inv_bags) do labels[#labels + 1] = bag.name end
        local pick = { hud.inv_state.bag }
        api.SetNextItemWidth(130)
        if api.Combo('##inv-bag', pick, labels) then
            hud.inv_state.bag = math.max(0, math.min(#hud.inv_bags,
                tonumber(pick[1]) or 0))
        end
        api.SameLine(0, 8)
        if api.Button('Sort: ' .. hud.inv_state.sort .. '##inv-sort', { 100, 20 }) then
            hud.inv_state.sort = hud.inv_state.sort == 'bag' and 'name' or
                (hud.inv_state.sort == 'name' and 'slot' or 'bag')
        end

        local rows = hud.inv_rows()
        api.Text(('%d item%s'):format(#rows, #rows == 1 and '' or 's'))
        api.SameLine(0, 10)
        if api.Button('Select all##inv-all', { 70, 20 }) then
            for _, row in ipairs(rows) do hud.inv_state.selected[row.key] = true end
        end
        api.SameLine(0, 4)
        if api.Button('Clear##inv-clear', { 50, 20 }) then hud.inv_state.selected = {} end
        if hud.inv_state.tab == 'bags' then
            api.SameLine(0, 10)
            if api.Button('Recycle selected##inv-bulk', { 120, 20 }) then
                local chosen = {}
                for _, row in ipairs(rows) do
                    if hud.inv_state.selected[row.key] and row.source == 'bag' then
                        chosen[#chosen + 1] = row
                    end
                end
                if #chosen > 0 then
                    local confirm = not (hud.inventory_data and #hud.inventory_data > 0)
                    for _, row in ipairs(chosen) do
                        if row.rare ~= 0 or row.ex ~= 0 then confirm = true end
                    end
                    if confirm then
                        hud.inv_state.pending = { rows = chosen }
                    else
                        for _, row in ipairs(chosen) do
                            hud.inv_run('//recycle drop ' .. row.bag .. ' ' .. row.slot ..
                                ' ' .. row.count)
                            hud.inv_state.selected[row.key] = nil
                        end
                    end
                end
            end
        end
        api.SameLine(0, 12)
        api.PushFont(nil, 9)
        hub_text(api, HUB_C.dim, 'Double-click a row for the full card')
        api.PopFont()

        api.PushFont(nil, 9)
        api.Dummy({ 18, 1 })
        api.SameLine(0, 5)
        hub_text(api, HUB_C.dim, 'ITEM')
        api.SameLine(hud.inv_layout.bag_x, 5)
        hub_text(api, HUB_C.dim, 'BAG / SOURCE')
        api.SameLine(hud.inv_layout.action_x, 5)
        hub_text(api, HUB_C.dim, 'ACTION')
        api.PopFont()

        api.BeginChild('##inv-rows', { 0, 356 }, 1, 0)
        for _, row in ipairs(rows) do
            local selected = hud.inv_state.selected[row.key] or false
            local row_x, row_y = api.GetCursorScreenPos()
            local texture = hud_item_texture(row.id)
            if texture then api.Image(texture, { 18, 18 }) else api.Dummy({ 18, 18 }) end
            api.SameLine(0, 5)
            -- The Selectable draws the highlight and owns hover, but selection and the
            -- card are driven from the click itself: ImGui reports a double-click on the
            -- second press, not on its release, so using the Selectable's return value
            -- would toggle twice before the card could open.
            api.Selectable((row.name .. ' x' .. row.count) .. '##row' .. row.key,
                selected, 0, { hud.inv_layout.name_width, 20 })
            local row_hover = api.IsWindowHovered()
                and api.IsMouseHoveringRect({ row_x, row_y },
                    { row_x + hud.inv_layout.action_x, row_y + 20 })
            if row_hover and api.IsMouseDoubleClicked(0) then
                -- The first click of the pair toggled the row; leave it selected so the
                -- table is ready for Move/Pull/Recycle once the card is closed.
                hud.inv_state.selected[row.key] = true
                hud.inv_state.card = row
            elseif row_hover and api.IsMouseClicked(0) then
                hud.inv_state.selected[row.key] = not selected
            end
            api.SameLine(hud.inv_layout.bag_x, 5)
            local bag_color = row.source == 'slip' and HUB_C.cyan
                or (row.source == 'locker' and HUB_C.purple)
                or (row.source == 'claim' and HUB_C.gold)
                or HUB_C.dim
            hub_text(api, bag_color, hud.inv_fit(api, row.bag_name, hud.inv_layout.bag_width))
            api.SameLine(hud.inv_layout.action_x, 5)
            if row.source == 'claim' then
                -- Purchase history: shown, but there is no bag action.
            elseif hud.inv_state.tab == 'bags' and row.source ~= 'bag' then
                if api.Button('Pull##pull' .. row.key, { 54, 18 }) then
                    local extra = row.extra ~= '' and (' ' .. row.extra) or ''
                    hud.inv_run('//item pull ' .. row.source .. ' ' .. row.id .. extra ..
                        ' ' .. row.count)
                end
            elseif hud.inv_state.tab == 'bags' then
                if row.source == 'bag' then
                    if api.Button('Move##m' .. row.key, { 54, 18 }) then
                        hud.inv_state.move = { row = row }
                    end
                    api.SameLine(0, 4)
                    if api.Button('X##r' .. row.key, { 24, 18 }) then
                        if (row.rare ~= 0 or row.ex ~= 0) or
                            not (hud.inventory_data and #hud.inventory_data > 0) then
                            hud.inv_state.pending = { rows = { row } }
                        else
                            hud.inv_run('//recycle drop ' .. row.bag .. ' ' ..
                                row.slot .. ' ' .. row.count)
                        end
                    end
                    if api.IsItemHovered() then api.SetTooltip('Recycle') end
                end
            else
                if api.Button('Restore##p' .. row.key, { 60, 18 }) then
                    hud.inv_run('//recycle restore ' .. row.slot)
                end
            end
        end
        api.EndChild()

        if hud.inv_state.move then
            local row = hud.inv_state.move.row
            api.Text('Move ' .. row.name .. ' to:')
            local targets = {
                { id = 0, name = 'Inventory' }, { id = 1, name = 'Mog Safe' },
                { id = 9, name = 'Mog Safe 2' }, { id = 2, name = 'Storage' },
                { id = 4, name = 'Mog Locker' }, { id = 5, name = 'Satchel' },
                { id = 6, name = 'Sack' }, { id = 7, name = 'Case' },
                { id = 8, name = 'Wardrobe 1' }, { id = 10, name = 'Wardrobe 2' },
                { id = 11, name = 'Wardrobe 3' }, { id = 12, name = 'Wardrobe 4' },
                { id = 13, name = 'Wardrobe 5' }, { id = 14, name = 'Wardrobe 6' },
                { id = 15, name = 'Wardrobe 7' }, { id = 16, name = 'Wardrobe 8' },
                { id = 'locker', name = 'Magic Bag (9999)' },
            }
            for index, target in ipairs(targets) do
                if index > 1 and (index - 1) % 4 ~= 0 then api.SameLine(0, 4) end
                if api.Button(target.name .. '##moveto' .. index, { 132, 20 }) then
                    if target.id == 'locker' then
                        hud.inv_run('//item store locker ' .. row.bag .. ' ' .. row.slot ..
                            ' ' .. row.count)
                    else
                        hud.inv_run('//item move ' .. row.bag .. ' ' .. row.slot .. ' ' ..
                            target.id .. ' ' .. row.count)
                    end
                    hud.inv_state.move = nil
                end
            end
            api.SameLine(0, 8)
            if api.Button('Cancel##movecancel', { 70, 20 }) then hud.inv_state.move = nil end
        end

        if hud.inv_state.pending then
            local pending = hud.inv_state.pending
            api.Text(('Recycle %d item%s? They stay in the Recycle Bin for 30 days.'):format(
                #pending.rows, #pending.rows == 1 and '' or 's'))
            if api.Button('Confirm recycle##inv-yes', { 120, 22 }) then
                for _, row in ipairs(pending.rows) do
                    hud.inv_run('//recycle drop ' .. row.bag .. ' ' .. row.slot .. ' ' .. row.count)
                    hud.inv_state.selected[row.key] = nil
                end
                hud.inv_state.pending = nil
            end
            api.SameLine(0, 8)
            if api.Button('Cancel##inv-no', { 80, 22 }) then hud.inv_state.pending = nil end
        end

        hud.inv_card(api)
    end
    api.End()
end

-- --- Call Beast jugs and pet commands ---------------------------------------------------------

-- The jug picker is fed by the generated catalogue, not by item descriptions: a jug is any
-- item the catalogue names in a bag the client can equip from.  Reading the bags at
-- open time and again while the window is up is what makes a consumed stack disappear from
-- the list without a restart.
function hud.scan_jugs()
    local rows, by_id = {}, {}
    for bag = 0, 17 do
        -- Only the bags the client can equip from count: a jug in Mog Safe/Storage/Satchel
        -- cannot go into ammo, and one in the Recycle Bin must not be offered at all.
        if hud.jug_bags[bag] then
            for slot = 1, 80 do
                local id = tonumber(game.item(bag, slot, 'Id')) or 0
                local data = id > 0 and hud.jugs[id] or nil
                if data then
                    local row = by_id[id]
                    if not row then
                        row = {
                            id = id, item = data.item, pet = data.pet,
                            level = tonumber(data.level) or 0, moves = data.moves or {},
                            count = 0, bag = bag, slot = slot,
                        }
                        by_id[id] = row
                        rows[#rows + 1] = row
                    end
                    row.count = row.count + (tonumber(game.item(bag, slot, 'Count')) or 1)
                end
            end
        end
    end
    -- Bestial Loyalty leaves the jug equipped; if its inventory copy was not in a scanned
    -- bag (a wardrobe, or a client that hides the source slot) it still has to be listed.
    local ammo = tonumber(worn_items()[3]) or 0
    local data = ammo > 0 and hud.jugs[ammo] or nil
    if data and not by_id[ammo] then
        local _, index = game.equipment(3)
        index = tonumber(index) or 0
        local row = {
            id = ammo, item = data.item, pet = data.pet,
            level = tonumber(data.level) or 0, moves = data.moves or {},
            count = 1, bag = math.floor(index / 256), slot = index % 256,
            equipped = true,
        }
        by_id[ammo] = row
        rows[#rows + 1] = row
    end
    table.sort(rows, function(a, b)
        local an, bn = tostring(a.item):lower(), tostring(b.item):lower()
        if an == bn then return a.id < b.id end
        return an < bn
    end)
    return rows
end

function hud.open_jug_picker(item)
    local state = hud.jug_state
    state.open = true
    state.ability = tostring(item and item.name or 'Bestial Loyalty')
    state.action = action_id(item) or 0
    state.rows = hud.scan_jugs()
    state.by_id = {}
    for _, row in ipairs(state.rows) do state.by_id[row.id] = row end
    state.at = os.clock()
end

-- The client validates the ammo before it sends the ability packet, so the jug is worn
-- first and the task waits for the client's equipment table to show it.  The phase engine's
-- one-shot precache then re-asserts the same jug in the held action batch, and its normal
-- restore puts the state set back; with the engine off the old ammo is restored here.
function hud.call_jug(row)
    local state = hud.jug_state
    local ability = state.ability ~= '' and state.ability or 'Bestial Loyalty'
    local action = tonumber(state.action) or 0
    local line = string.format('/ja "%s" <me>', ability)
    local before = tonumber(worn_items()[3]) or 0
    local bag, slot = tonumber(row.bag) or 0, tonumber(row.slot) or 0
    state.open = false
    hud.pet_last_jug = row.id

    local function restore_previous()
        if before ~= 0 and before ~= row.id then
            local name = item_name(before)
            if name then pcall(equip_item, 3, name) end
        end
    end

    -- The client validates the ammo before it sends the ability packet, so the jug has to be
    -- worn first.  The client's own equipment table only shows the new piece after the
    -- server's echo (the same reason guard_throw waits), so poll it instead of guessing a
    -- fixed delay.  Once it is on, the phase engine can hold the action and put the jug on
    -- again in the packet batch; the normal state set returns when the action resolves.
    xi.tasks.spawn(function()
        if (tonumber(worn_items()[3]) or 0) ~= row.id then
            if slot >= 1 and bag >= 0 and bag <= 17 then
                xi.packets.inject(true, equip_packet(bag, slot, 3))
                if xi.phase then xi.phase.forget_slot(3) end
            else
                local ok, err = pcall(equip_item, 3, row.item)
                if not ok then
                    xi.chat.write('HUD: ' .. tostring(err), 1)
                    restore_previous()
                    return
                end
            end
            local deadline = os.clock() + 3.0
            while os.clock() < deadline do
                if (tonumber(worn_items()[3]) or 0) == row.id then break end
                coroutine.sleep(0.05)
            end
        end
        if (tonumber(worn_items()[3]) or 0) ~= row.id then
            xi.chat.write('HUD: could not equip ' .. tostring(row.item) ..
                ' in the ammo slot.', 1)
            restore_previous()
            return
        end
        local phase_on, actions_before = false, nil
        if xi.phase and xi.phase.precache and xi.phase.status and action > 0 then
            local ok, status = pcall(xi.phase.status)
            if ok and type(status) == 'table' then
                local pinned = false
                for _, kind in ipairs(status.lockedSlots or {}) do
                    if tonumber(kind) == 3 then pinned = true break end
                end
                phase_on = status.enabled and not status.locked and not pinned
                actions_before = tonumber(status.actions) or 0
                if phase_on and slot >= 1 and bag >= 0 and bag <= 17 then
                    phase_on = pcall(xi.phase.precache, action, { { slot, 3, bag } })
                end
            end
        end
        local ok, err = pcall(xi.chat.run, line, 1)
        if not ok then
            xi.chat.write('HUD: ' .. tostring(err), 1)
            restore_previous()
            return
        end
        if phase_on then
            -- The action increments the engine's counter when its 0x01A is processed.  If
            -- the client refused the command (recast, no room), put the old ammo back; the
            -- one-shot piece is cleared by the next action either way.
            coroutine.sleep(0.6)
            local ok2, status2 = pcall(xi.phase.status)
            local acted = ok2 and type(status2) == 'table' and actions_before ~= nil
                and (tonumber(status2.actions) or 0) > actions_before
            if not acted then restore_previous() end
        else
            coroutine.sleep(1.8)
            restore_previous()
        end
    end)
end

function hud.current_pet()
    local ok, _mpp, _tp, index = pcall(function() return game.pet() end)
    index = ok and tonumber(index) or 0
    if index <= 0 then return nil end
    local name = game.entity(index, 'Name')
    if type(name) ~= 'string' or name == '' then return nil end
    return { index = index, name = name, id = tonumber(game.entity(index, 'ServerId')) or 0 }
end

function hud.pet_jug(pet)
    if not pet then return nil, 0 end
    local key = pet.name:lower():gsub('%s+', ' ')
    local item_id = hud.jug_by_pet[key]
    -- The client may truncate a long pet name in the entity block; match the first 15
    -- characters too (the generated names have no collision there).
    if not item_id then item_id = hud.jug_by_pet_short[key:sub(1, 15)] end
    if not item_id and hud.pet_last_jug > 0 then
        local row = hud.jugs[hud.pet_last_jug]
        local name_key = row and tostring(row.pet):lower():gsub('%s+', ' ') or ''
        if name_key == key or name_key:sub(1, 15) == key:sub(1, 15) then
            item_id = hud.pet_last_jug
        end
    end
    return item_id and hud.jugs[item_id] or nil, item_id or 0
end

function hud.pet_command_run(item)
    local key = item.command_key or hud_ability_key(item.name)
    local self_only = key == 'heel' or key == 'stay' or key == 'leave'
        or key == 'reward' or key == 'snarl' or key == 'spur' or key == 'runwild'
    local target = self_only and '<me>' or hud_target()
    local line
    if item.kind == 'pet_command' then
        line = string.format('/pet "%s" %s', item.name, target)
    else
        line = string.format('/ja "%s" %s', item.name, target)
    end
    local ok, err = pcall(xi.chat.run, line, 1)
    if not ok then xi.chat.write('HUD: ' .. tostring(err), 1) end
end

function hud.ready_move(move)
    local ok, err = pcall(xi.chat.run,
        string.format('/pet "%s" %s', tostring(move), hud_target()), 1)
    if not ok then xi.chat.write('HUD: ' .. tostring(err), 1) end
end

function hud.jug_window(api)
    local state = hud.jug_state
    if not state.open then return end
    local now = os.clock()
    if now - (state.at or 0) > 0.6 then
        state.rows = hud.scan_jugs()
        state.by_id = {}
        for _, row in ipairs(state.rows) do state.by_id[row.id] = row end
        state.at = now
    end
    local screen_w, screen_h = hud_screen_size(api)
    local width, height = math.min(620, math.max(300, screen_w - 8)),
        math.min(480, math.max(240, screen_h - 8))
    local x = math.max(4, math.floor((screen_w - width) / 2))
    local y = math.max(4, math.floor((screen_h - height) / 2))
    api.SetNextWindowPos({ x, y }, 1)
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(0.98)
    local open = api.Begin('Call Beast##fanxi-jug-picker', nil, 1 + 2 + 4 + 8 + 32 + 256)
    if open then
        api.PushFont(nil, 12)
        api.Text(state.ability)
        api.PopFont()
        api.Text('Pick a jug: it is worn as the ability precast, then the normal set returns.')
        api.Separator()
        if #state.rows == 0 then
            api.Text('No Call Beast jugs in an equippable bag.')
            api.Text('Only Inventory and the Mog Wardrobes can put a jug in ammo.')
            api.Text('Pull a stack with //locker grab <jug> 12, then Refresh.')
        else
            api.BeginChild('##fanxi-jug-list', { 0, math.max(80, height - 118) }, 1, 0)
            for _, row in ipairs(state.rows) do
                local texture = hud_item_texture(row.id)
                if texture then
                    api.Image(texture, { 32, 32 })
                    api.SameLine(0, 8)
                else
                    api.Dummy({ 32, 32 })
                    api.SameLine(0, 8)
                end
                local label = string.format('%s  —  %s  x%d##fanxi-jug-%d',
                    row.item, row.pet, row.count, row.id)
                if api.Button(label, { math.max(160, width - 100), 32 }) then
                    hud.call_jug(row)
                end
                if api.IsItemHovered() then
                    local moves = {}
                    for _, move in ipairs(row.moves or {}) do
                        moves[#moves + 1] = tostring(move)
                    end
                    api.SetTooltip(string.format('%s\nCalls %s (Lv %d)\nReady: %s',
                        row.item, row.pet, row.level,
                        #moves > 0 and table.concat(moves, ', ') or 'none'))
                end
            end
            api.EndChild()
        end
        if api.Button('Close##fanxi-jug-close', { 80, 22 }) then state.open = false end
        api.SameLine(0, 8)
        if api.Button('Refresh##fanxi-jug-refresh', { 90, 22 }) then state.at = 0 end
    end
    api.End()
end

function hud.pet_window(api)
    local state = hud.pet_state
    if not state.open then return end
    local pet = hud.current_pet()
    local jug = hud.pet_jug(pet)
    local screen_w, screen_h = hud_screen_size(api)
    local width, height = math.min(620, math.max(300, screen_w - 8)),
        math.min(440, math.max(220, screen_h - 8))
    local x = math.max(4, math.floor((screen_w - width) / 2))
    local y = math.max(4, math.floor((screen_h - height) / 2))
    api.SetNextWindowPos({ x, y }, 1)
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(0.98)
    local open = api.Begin('Pet Commands##fanxi-pet-commands', nil, 1 + 2 + 4 + 8 + 32 + 256)
    if open then
        api.PushFont(nil, 12)
        api.Text(pet and ('Pet: ' .. pet.name) or 'Pet Commands')
        api.PopFont()
        if not pet then
            api.Text('No pet is out.')
            api.Text('A Call Beast jug or a charmed pet is needed for these commands.')
            if api.Button('Call a jug...##fanxi-pet-call', { 140, 24 }) then
                state.open = false
                hud.open_jug_picker({ name = 'Call Beast', id = 0x200 + 85 })
            end
        else
            if jug then
                api.Text('Jug: ' .. tostring(jug.item) .. '  ->  ' .. tostring(jug.pet))
            else
                api.Text('Charmed pet: no jug Ready moves.')
            end
            api.Separator()
            api.BeginChild('##fanxi-pet-body', { 0, math.max(60, height - 92) }, 1, 0)
            api.Text('Commands')
            local shown = 0
            for index, command in ipairs(hud.pet_commands or {}) do
                local key = command.command_key or hud_ability_key(command.name)
                -- A jug pet uses Ready instead of Sic and cannot be released with Leave;
                -- both belong to a charmed pet.  Its Ready moves are the jug's, shown below.
                local skip
                if jug then
                    skip = key == 'leave' or key == 'sic'
                        or (key == 'ready' and #(jug.moves or {}) > 0)
                else
                    skip = key == 'ready'
                end
                if not skip then
                    if shown % 3 == 0 then
                        if shown > 0 then api.NewLine() end
                    else
                        api.SameLine(0, 6)
                    end
                    shown = shown + 1
                    local label = string.format('%s##fanxi-pet-%s', command.name,
                        tostring(command.key))
                    if api.Button(label, { 150, 26 }) then
                        hud.pet_command_run(command)
                    end
                end
            end
            if shown % 3 ~= 0 then api.NewLine() end
            if jug and #(jug.moves or {}) > 0 then
                api.Separator()
                api.PushFont(nil, 11)
                api.Text('Ready — ' .. tostring(jug.pet))
                api.PopFont()
                for index, move in ipairs(jug.moves) do
                    if (index - 1) % 3 > 0 then api.SameLine(0, 6) end
                    if api.Button(string.format('%s##fanxi-ready-%d', tostring(move), index),
                        { 150, 24 }) then
                        hud.ready_move(move)
                    end
                    if index % 3 == 0 then api.NewLine() end
                end
                if #jug.moves % 3 ~= 0 then api.NewLine() end
            end
            api.EndChild()
        end
        if api.Button('Close##fanxi-pet-close', { 80, 22 }) then state.open = false end
        api.SameLine(0, 8)
        if pet then
            if api.Button('Call a jug...##fanxi-pet-call2', { 120, 22 }) then
                state.open = false
                hud.open_jug_picker({ name = 'Call Beast', id = 0x200 + 85 })
            end
        end
    end
    api.End()
end

-- --- Corsair roll / Quick Draw pickers --------------------------------------------------------

-- The Abilities page keeps Phantom Roll and Quick Draw as the two doors; these windows are what
-- they open.  The roll list can be searched and sorted by the level the roll is learned at
-- (the default, so the rolls a levelling Corsair actually has sit at the top) or by name.  A
-- pick closes the window and runs the row's /ja through the same hud_click path as a tile, so
-- the shared 60-second roll recast and the shot recasts show up on both the row and the page.
function hud.cor_window(api)
    local state = hud.cor_menu
    if not state.open then return end
    local rolls = state.kind ~= 'shot'
    local rows = rolls and hud.cor_roll_rows(state.search[1], state.sort) or hud.cor_shot_rows()
    local screen_w, screen_h = hud_screen_size(api)
    local width
    local height
    if rolls then
        width = math.min(520, math.max(300, screen_w - 16))
        height = math.min(560, math.max(300, screen_h - 16))
    else
        width = math.min(440, math.max(280, screen_w - 16))
        height = math.min(400, math.max(260, screen_h - 16))
    end
    local x = math.max(4, math.floor((screen_w - width) / 2))
    local y = math.max(4, math.floor((screen_h - height) / 2))
    api.SetNextWindowPos({ x, y }, 1)
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(0.98)
    api.PushStyleVar(2, { 10, 8 })       -- ImGuiStyleVar_WindowPadding
    api.PushStyleVar(14, { 6, 6 })       -- ImGuiStyleVar_ItemSpacing
    local open = api.Begin((rolls and 'Phantom Roll##fanxi-cor-menu' or 'Quick Draw##fanxi-cor-menu'),
        nil, 1 + 2 + 4 + 8 + 32 + 256)
    if open then
        api.PushFont(nil, 13)
        hub_text(api, HUB_C.cyan, rolls and 'PHANTOM ROLL' or 'QUICK DRAW')
        api.PopFont()
        api.SameLine(0, 10)
        api.PushFont(nil, 9)
        hub_text(api, HUB_C.dim, string.format('%d of %d', #rows,
            rolls and #hud.cor_rolls or #hud.cor_shots))
        api.PopFont()
        if rolls then
            api.SetNextItemWidth(math.max(80, width - 20 - 60))
            api.InputTextWithHint('##fanxi-cor-search', 'Search rolls', state.search, 64)
            api.SameLine(0, 8)
            if api.Button('Clear##fanxi-cor-clear', { 52, 22 }) then state.search[1] = '' end
            api.Text('Sort')
            api.SameLine(0, 6)
            local level_label = state.sort == 'level' and '[Level acquired]' or 'Level acquired'
            if api.Button(level_label .. '##fanxi-cor-sort-level', { 112, 20 }) then
                state.sort = 'level'
            end
            api.SameLine(0, 4)
            local name_label = state.sort == 'name' and '[Name]' or 'Name'
            if api.Button(name_label .. '##fanxi-cor-sort-name', { 62, 20 }) then
                state.sort = 'name'
            end
        else
            api.PushFont(nil, 10)
            hub_text(api, HUB_C.dim,
                'Fire, Ice, Wind, Earth, Thunder, Water, Light and Dark.')
            api.PopFont()
        end
        api.Separator()
        api.BeginChild('##fanxi-cor-list', { 0, math.max(60, height - (rolls and 158 or 126)) }, 1, 0)
        if #rows == 0 then
            api.Text(rolls and 'No rolls match the search.'
                or 'No elemental shots are available for this job pair yet.')
        elseif rolls then
            local button_w = math.max(120, width - 20 - 28 - 8 - 8 - 62)
            for _, item in ipairs(rows) do
                local texture = hud_icon_texture(item.icon)
                if texture then api.Image(texture, { 28, 28 }) else api.Dummy({ 28, 28 }) end
                api.SameLine(0, 8)
                local cooling = hud.cool[item.key]
                local lucky, unlucky = tonumber(item.lucky), tonumber(item.unlucky)
                local label = item.name
                if lucky and unlucky then
                    label = label .. '   Lucky ' .. lucky .. ' / Unlucky ' .. unlucky
                end
                local clicked
                if cooling then
                    api.BeginDisabled(true)
                    clicked = api.Button(label .. '##fanxi-cor-' .. item.key, { button_w, 28 })
                    api.EndDisabled()
                else
                    clicked = api.Button(label .. '##fanxi-cor-' .. item.key, { button_w, 28 })
                end
                local hovered = api.IsItemHovered()
                api.SameLine(0, 8)
                if cooling then
                    api.TextColored({ 0.62, 0.70, 0.78, 1 }, hud_recast_time(cooling.remaining))
                else
                    api.TextColored({ 0.62, 0.70, 0.78, 1 }, 'Lv ' .. tostring(item.level))
                end
                if clicked then
                    hud_click(hud, item)
                elseif hovered then
                    local odds = lucky and unlucky and string.format(
                        '\nLucky number: %d\nUnlucky number: %d', lucky, unlucky) or ''
                    api.SetTooltip(string.format('%s\nLearned at level %d%s\nClick to use',
                        item.name, tonumber(item.level) or 0, odds))
                end
            end
        else
            -- A shot is an ability tile, so reuse the action HUD's cell: it draws the menu
            -- icon, the cooldown sweep and the same /ja click path as the main page.
            local spec = hud.state.types.abilities
            local cols = 4
            local gap = HUD_GRID_GAP
            local cell_w = math.floor((width - 20 - gap * (cols - 1)) / cols)
            cell_w = math.max(48, math.min(96, cell_w))
            local cell_h = cell_w + 20
            for index, item in ipairs(rows) do
                if (index - 1) % cols > 0 then api.SameLine(0, gap) end
                hud_draw_cell(api, spec, item, cell_w, cell_h, 'grid')
                if index % cols == 0 then api.NewLine() end
            end
            if #rows % cols ~= 0 then api.NewLine() end
        end
        api.EndChild()
        if api.Button('Close##fanxi-cor-close', { 80, 22 }) then state.open = false end
    end
    api.End()
    api.PopStyleVar(2)
end

-- --- support-trust action menu ---------------------------------------------------------------

-- Joachim, Luzaf, Qultada, Koru-Moru, Sylvie (UC) and Ygnas let the owner choose what they
-- do.  The server owns the catalogue and the saved selection; opening a tile asks
-- `//trust <id> ui hud` and the server answers with `TrustData|` lines the addon swallows.
-- A `Use default logic` checkbox is the escape hatch: checked, the Trust runs its built-in
-- rotation; unchecked, only the selected actions are used (in the order they were clicked).

-- BEGIN trust actions
-- Keep these ids and limits in step with trust_ai.SUPPORT_TRUST_IDS/TRUST_ACTION_LIMIT;
-- tests/trust_hud_test.py compares them with the server.
hud.trust_config = {
    [911] = { kind = 'song',  label = 'songs',  limit = 4,  title = 'Joachim' },
    [928] = { kind = 'roll',  label = 'rolls',  limit = 8,  title = 'Luzaf' },
    [952] = { kind = 'spell', label = 'spells', limit = 24, title = 'Koru-Moru' },
    [967] = { kind = 'roll',  label = 'rolls',  limit = 8,  title = 'Qultada' },
    [981] = { kind = 'spell', label = 'spells', limit = 24, title = 'Sylvie (UC)' },
    [998] = { kind = 'spell', label = 'spells', limit = 24, title = 'Ygnas' },
}
hud.trust_category = {
    cure = 'CURES', buff = 'BUFFS', debuff = 'DEBUFFS',
    aura = 'AURAS', nuke = 'NUKES', song = 'SONGS', roll = 'ROLLS',
}
-- The compact server catalogue carries one letter per action; keep in step with
-- TRUST_HUD_KIND_CHAR in server/fanxi_server/game/zone.py.
hud.trust_kind_letter = {
    c = 'cure', b = 'buff', d = 'debuff', a = 'aura', n = 'nuke',
    s = 'song', r = 'roll',
}
hud.trust_menu = {
    open = false,
    mode = 'menu',
    item = nil,
    trust_id = 0,
    name = '',
    kind = 'spell',
    label = 'spells',
    limit = 24,
    actions = {},
    by_id = {},
    selected = {},
    -- The compact catalogue (//trust <id> ui hud2): ids in display order, one
    -- category letter per id, and the Trust's job pair for the level column.
    ids = {},
    kinds = '',
    main_job = 0,
    sub_job = 0,
    auto = true,
    loading = false,
    notice = nil,
    at = 0,
}

function hud.trust_config_for(id)
    return hud.trust_config[tonumber(id) or 0]
end

function hud.trust_configurable(id)
    return hud.trust_config_for(id) ~= nil
end

function hud.trust_label(id)
    local config = hud.trust_config_for(id)
    return config and config.label or 'actions'
end

function hud.trust_key(kind)
    return tostring(kind or ''):lower():gsub('[^%w]', '')
end

function hud.trust_order(action_id)
    local wanted = tonumber(action_id) or 0
    for index, value in ipairs(hud.trust_menu.selected) do
        if tonumber(value) == wanted then return index end
    end
    return nil
end

function hud.trust_toggle(action_id)
    local state = hud.trust_menu
    local action = tonumber(action_id) or 0
    if action <= 0 or state.auto then return end
    local order = hud.trust_order(action)
    if order then
        table.remove(state.selected, order)
    elseif #state.selected >= state.limit then
        state.notice = string.format('You can select at most %d.', state.limit)
        return
    else
        state.selected[#state.selected + 1] = action
    end
    state.notice = nil
end

function hud.trust_selected_names()
    local state = hud.trust_menu
    local out = {}
    for _, action_id in ipairs(state.selected) do
        local row = state.by_id[tonumber(action_id) or 0]
        if row then out[#out + 1] = row.name end
    end
    return out
end

-- The compact catalogue sends four hex digits per id; parse them back to numbers.
function hud.trust_hex_ids(text)
    local out = {}
    for hex in tostring(text or ''):gmatch('%x%x%x%x') do
        local action_id = tonumber(hex, 16)
        if action_id and action_id > 0 then out[#out + 1] = action_id end
    end
    return out
end

-- The client's own spell/ability table names an id, so the compact catalogue does not
-- have to spend a chat line on every name.  `res` is the file-local alias of xi.res
-- (line 98) in the addon; the test block has no such local and supplies a global stub.
function hud.trust_res_record(kind, action_id)
    local lib = res
    if type(lib) ~= 'table' or type(lib[kind]) ~= 'function' then return nil end
    local ok, record = pcall(lib[kind], action_id)
    return ok and record or nil
end

function hud.trust_record_name(record)
    if type(record) ~= 'table' then return nil end
    local name = record.name_utf8 or record.name
    if type(name) == 'table' then name = name.en or name[2] or name[1] end
    if type(name) ~= 'string' then return nil end
    name = name:gsub('%z', ''):match('^%s*(.-)%s*$')
    if name == '' or name == '.' then return nil end
    return name
end

-- The name and unlock level of one catalogue id.  Rolls are job abilities, not spells;
-- their ids overlap the spell table, so the kind decides which table wins.
function hud.trust_action_info(action_id, kind)
    local spell, ability
    if kind == 'roll' then
        -- The client's ability table names a job ability as 0x200 + its id; the server's
        -- roll table carries the bare id (98 = Fighter's Roll, 105 = Chaos Roll).
        ability = hud.trust_res_record('ability', 0x200 + action_id)
            or hud.trust_res_record('ability', action_id)
    else
        spell = hud.trust_res_record('spell', action_id)
        if not spell then ability = hud.trust_res_record('ability', action_id) end
    end
    local name = hud.trust_record_name(spell) or hud.trust_record_name(ability)
    if not name then return nil, 0 end
    local level = 0
    local state = hud.trust_menu
    if spell and type(spell.levels) == 'table' then
        local main = tonumber(state.main_job) or 0
        if main > 0 then level = tonumber(spell.levels[main]) or 0 end
        if level <= 0 then
            local sub = tonumber(state.sub_job) or 0
            local sub_level = sub > 0 and tonumber(spell.levels[sub]) or 0
            if sub_level and sub_level > 0 and sub_level <= 49 then level = sub_level end
        end
        level = math.max(0, tonumber(level) or 0)
    end
    return name, level
end

-- Turn the compact id/letter streams into the same rows the legacy A lines carried.
function hud.trust_build_actions()
    local state = hud.trust_menu
    local actions, seen = {}, {}
    for index, action_id in ipairs(state.ids) do
        if not seen[action_id] then
            seen[action_id] = true
            local kind = hud.trust_kind_letter[state.kinds:sub(index, index)]
                or (state.kind == 'roll' and 'roll')
                or (state.kind == 'song' and 'song') or 'buff'
            local name, level = hud.trust_action_info(action_id, kind)
            if name then
                actions[#actions + 1] = {
                    id = action_id, name = name, level = level, kind = kind,
                }
            end
        end
    end
    state.actions = actions
    state.by_id = {}
    for _, row in ipairs(actions) do state.by_id[row.id] = row end
end

function hud.trust_data(text)
    local parts = {}
    for part in (tostring(text or '') .. '|'):gmatch('([^|]*)|') do
        parts[#parts + 1] = part
    end
    local trust_id = tonumber(parts[1]) or 0
    local state = hud.trust_menu
    if trust_id <= 0 or not state.open or state.trust_id ~= trust_id then return end
    local op = parts[2]
    if op == 'B' then
        state.name = parts[3] ~= '' and parts[3] or state.name
        state.kind = parts[4] ~= '' and parts[4] or state.kind
        state.label = (hud.trust_config_for(trust_id) or {}).label or state.label
        state.limit = tonumber(parts[5]) or state.limit
        state.auto = parts[6] == '1'
        state.actions, state.by_id, state.selected = {}, {}, {}
        state.ids, state.kinds = {}, ''
        state.main_job, state.sub_job = 0, 0
        if parts[8] ~= nil then
            -- Compact header: |main job|sub job[|selected ids, hex]
            state.main_job = tonumber(parts[7]) or 0
            state.sub_job = tonumber(parts[8]) or 0
            state.selected = hud.trust_hex_ids(parts[9] or '')
        else
            -- Legacy header: |selected,ids
            for part in (parts[7] or ''):gmatch('[^,]+') do
                local action_id = tonumber(part)
                if action_id and action_id > 0 then
                    state.selected[#state.selected + 1] = action_id
                end
            end
        end
        state.loading = true
        state.at = os.clock()
    elseif op == 'S' then
        -- The selection did not fit beside the header (24 ids on a long Trust name).
        state.selected = hud.trust_hex_ids(parts[3] or '')
    elseif op == 'I' then
        for _, action_id in ipairs(hud.trust_hex_ids(parts[3] or '')) do
            state.ids[#state.ids + 1] = action_id
        end
        -- Datagrams can overtake each other: if End already arrived, fold this chunk in
        -- now instead of leaving the picker with the rows it had at End.
        if not state.loading and #state.ids > 0 then hud.trust_build_actions() end
    elseif op == 'K' then
        state.kinds = state.kinds .. tostring(parts[3] or '')
        if not state.loading and #state.ids > 0 then hud.trust_build_actions() end
    elseif op == 'A' then
        local action_id = tonumber(parts[3]) or 0
        if action_id <= 0 or state.by_id[action_id] then return end
        local row = {
            id = action_id,
            level = tonumber(parts[4]) or 0,
            kind = parts[5] or state.kind,
            name = parts[6] or tostring(action_id),
        }
        state.actions[#state.actions + 1] = row
        state.by_id[action_id] = row
    elseif op == 'E' then
        if #state.ids > 0 then hud.trust_build_actions() end
        local selected, seen = {}, {}
        for _, action_id in ipairs(state.selected) do
            if state.by_id[action_id] and not seen[action_id] then
                seen[action_id] = true
                selected[#selected + 1] = action_id
            end
        end
        state.selected = selected
        if state.auto or #selected == 0 then
            state.auto = true
            state.selected = {}
        end
        state.loading = false
        state.at = os.clock()
    end
end

-- The chat handlers live above the `local hud` declaration, so they cannot see the local
-- table.  This global forwarder is their only entry point into the menu parser.
function trust_data_hook(text)
    hud.trust_data(text)
end

function hud.trust_command()
    local state = hud.trust_menu
    if state.auto or #state.selected == 0 then
        return string.format('//trust %d set default', state.trust_id)
    end
    local config = hud.trust_config_for(state.trust_id)
    local label = config and config.label or state.label
    local parts = { string.format('//trust %d set %s', state.trust_id, label) }
    for _, name in ipairs(hud.trust_selected_names()) do
        parts[#parts + 1] = string.format('%q', name)
    end
    return table.concat(parts, ' ')
end

function hud.trust_open(item)
    local config = hud.trust_config_for(item.id)
    if not config then return end
    local state = hud.trust_menu
    state.open = true
    state.mode = 'menu'
    state.item = item
    state.trust_id = tonumber(item.id) or 0
    state.name = tostring(item.name or config.title or 'Trust')
    state.kind = config.kind
    state.label = config.label
    state.limit = config.limit
    state.actions, state.by_id, state.selected = {}, {}, {}
    state.ids, state.kinds = {}, ''
    state.main_job, state.sub_job = 0, 0
    state.auto = true
    state.loading = true
    state.notice = nil
    state.at = os.clock()
    hud.next_trust_scan = 0
    hud_refresh_trusts()
    -- hud2 is the compact catalogue: ids and category letters only.  The legacy
    -- one-row-per-line form floods the chat pipe and the dialog opened empty after a
    -- relog, which made players re-pick every spell.
    local ok, err = pcall(xi.chat.run,
        string.format('//trust %d ui hud2', state.trust_id), 1)
    if not ok then
        state.loading = false
        state.notice = tostring(err)
    end
end

function hud.trust_save()
    local state = hud.trust_menu
    if state.loading then
        state.notice = 'Still reading the action list.'
        return
    end
    if not state.auto and #state.selected == 0 then
        state.notice = 'Pick at least one action, or tick Use default logic.'
        return
    end
    local ok, err = pcall(xi.chat.run, hud.trust_command(), 1)
    if not ok then
        state.notice = tostring(err)
        return
    end
    if state.auto then state.selected = {} end
    state.mode = 'menu'
    state.notice = state.auto and 'Using the default logic.'
        or string.format('Saved: %d %s.', #state.selected, state.label)
end

function hud.trust_call()
    local state = hud.trust_menu
    local item = state.item
    if not item then return end
    local line
    if hud_trust_active(item) then
        line = string.format('//trust release %d', tonumber(item.id) or 0)
        if type(hud.active_trusts) == 'table' then
            hud.active_trusts[hud_trust_key(item.name)] = nil
        end
    else
        line = string.format('/ma "%s" <me>', item.name)
    end
    local ok, err = pcall(xi.chat.run, line, 1)
    if not ok then state.notice = tostring(err) return end
    state.open = false
end

function hud.trust_window(api)
    local state = hud.trust_menu
    if not state.open then return end
    hud_refresh_trusts()
    -- The compact catalogue is eight short packets, but a slow link (or a busy zone)
    -- still needs room for a couple of missed flushes; the old five seconds fired before
    -- the legacy catalogue's first rows had even arrived.
    if state.loading and os.clock() - (state.at or 0) > 12 then
        state.loading = false
        state.notice = 'Could not read the action list; try again.'
    end
    local actions_mode = state.mode == 'actions'
    local screen_w, screen_h = hud_screen_size(api)
    local width = actions_mode and math.min(600, math.max(380, screen_w - 16))
        or math.min(420, math.max(320, screen_w - 16))
    local height = actions_mode and math.min(640, math.max(380, screen_h - 16))
        or math.min(310, math.max(240, screen_h - 16))
    local x = math.max(4, math.floor((screen_w - width) / 2))
    local y = math.max(4, math.floor((screen_h - height) / 2))
    api.SetNextWindowPos({ x, y }, 1)
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(0.98)
    api.PushStyleVar(2, { 10, 8 })       -- ImGuiStyleVar_WindowPadding
    api.PushStyleVar(14, { 6, 6 })       -- ImGuiStyleVar_ItemSpacing
    local title = actions_mode and ('Set ' .. state.label .. '###fanxi-trust')
        or (state.name .. '###fanxi-trust')
    local open = api.Begin(title, nil, 1 + 2 + 4 + 8 + 32 + 256)
    if open then
        api.PushFont(nil, 13)
        hub_text(api, HUB_C.cyan, actions_mode and string.upper('Set ' .. state.label)
            or string.upper(state.name))
        api.PopFont()
        api.SameLine(0, 10)
        api.PushFont(nil, 9)
        hub_text(api, HUB_C.dim, 'support trust')
        api.PopFont()
        api.Separator()

        if not actions_mode then
            local active = state.item ~= nil and hud_trust_active(state.item)
            local cooling = state.item ~= nil and hud_cooling(hud, state.item) or nil
            api.PushFont(nil, 10)
            if state.loading then
                hub_text(api, HUB_C.dim, 'Reading the action list...')
            elseif state.auto then
                hub_text(api, HUB_C.dim, 'Current: default logic (built-in).')
            else
                hub_text(api, HUB_C.dim,
                    string.format('Current: %d %s selected.', #state.selected, state.label))
                local names = hud.trust_selected_names()
                if #names > 0 then
                    hub_text(api, HUB_C.dim, table.concat(names, ', '))
                end
            end
            api.PopFont()
            if active then
                hub_text(api, HUB_C.green, state.name .. ' is out.')
            end
            if cooling then
                hub_text(api, HUB_C.dim, 'Recast ' .. hud_recast_time(cooling.remaining))
            end
            if state.notice then
                hub_text(api, HUB_C.gold, state.notice)
            end
            api.Dummy({ 0, 4 })
            if active then
                if hub_button(api, 'Dismiss ' .. state.name, HUB_C.red, 190) then
                    hud.trust_call()
                end
            elseif cooling then
                api.BeginDisabled(true)
                hub_button(api, 'Call ' .. state.name, HUB_C.green, 190)
                api.EndDisabled()
            elseif hub_button(api, 'Call ' .. state.name, HUB_C.green, 190) then
                hud.trust_call()
            end
            if hub_button(api, 'Set ' .. state.label, HUB_C.cyan, 190) then
                state.mode = 'actions'
                state.notice = nil
            end
            if hub_button(api, 'Release all', HUB_C.red, 120) then
                local ok, err = pcall(xi.chat.run, '//trust release all', 1)
                if not ok then state.notice = tostring(err) end
                if type(hud.active_trusts) == 'table' then hud.active_trusts = {} end
                state.notice = 'Released every alter ego.'
            end
            if hub_button(api, 'Close', HUB_C.dim, 80) then
                state.open = false
            end
        else
            local box = { state.auto }
            if api.Checkbox('Use default logic##fanxi-trust-default', box) then
                state.auto = box[1] and true or false
                if state.auto then state.selected = {} end
                state.notice = nil
            end
            api.SameLine(0, 10)
            api.PushFont(nil, 9)
            hub_text(api, HUB_C.dim, state.auto
                and 'Built-in rotation; the list is read-only.'
                or 'Only the ticked actions are used, in click order.')
            api.PopFont()
            api.Text(string.format('Selected %d / %d', #state.selected, state.limit))
            if state.notice then
                hub_text(api, HUB_C.gold, state.notice)
            end
            api.Separator()
            if state.auto then api.BeginDisabled(true) end
            api.BeginChild('##fanxi-trust-actions', { 0, math.max(80, height - 182) }, 1, 0)
            if #state.actions == 0 then
                hub_text(api, HUB_C.dim, state.loading and 'Reading actions...'
                    or 'No actions are available at this level.')
            else
                local last_kind = nil
                for _, row in ipairs(state.actions) do
                    if row.kind ~= last_kind then
                        last_kind = row.kind
                        api.Dummy({ 0, 2 })
                        hub_text(api, HUB_C.cyan,
                            hud.trust_category[row.kind] or string.upper(tostring(row.kind)))
                        api.Separator()
                    end
                    local order = hud.trust_order(row.id)
                    local included = order ~= nil
                    local full = #state.selected >= state.limit and not included
                    local prefix = included and (tostring(order) .. '. ') or ''
                    local level = tonumber(row.level) or 0
                    local label = string.format('%s%s%s##fanxi-trust-action-%d',
                        prefix, row.name,
                        level > 0 and string.format('  (Lv.%d)', level) or '',
                        row.id)
                    if full then api.BeginDisabled(true) end
                    local checked = { included }
                    if api.Checkbox(label, checked) then hud.trust_toggle(row.id) end
                    if full then api.EndDisabled() end
                end
            end
            api.EndChild()
            if state.auto then api.EndDisabled() end
            if not state.loading and hub_button(api, 'Save', HUB_C.green, 76) then
                hud.trust_save()
            elseif state.loading then
                api.BeginDisabled(true)
                hub_button(api, 'Save', HUB_C.green, 76)
                api.EndDisabled()
            end
            api.SameLine(0, 6)
            if hub_button(api, 'Clear', HUB_C.dim, 66) then
                state.auto = false
                state.selected = {}
                state.notice = nil
            end
            api.SameLine(0, 6)
            if hub_button(api, 'Back', HUB_C.cyan, 66) then
                state.mode = 'menu'
                state.notice = nil
            end
            api.SameLine(0, 6)
            if hub_button(api, 'Close', HUB_C.dim, 66) then
                state.open = false
            end
        end
    end
    api.End()
    api.PopStyleVar(2)
end
-- END trust actions

-- --- target debuffs ---------------------------------------------------------------------------

-- The client has no monster buff list.  The server knows every effect it put on the mob,
-- so the HUD asks the launcher API for the selected target's effects and draws them here.
-- The request carries the client's target ServerId (the world entity id) so the window
-- follows target changes immediately; without one the server falls back to its own
-- engaged/selected targid.
function hud.target_tick()
    if not hud.state.show_target then return end
    if hud.target_polling then return end
    local now = os.clock()
    if now < (hud.target_at or 0) then return end
    hud.target_at = now + 0.75
    local battle = hud.battle
    if not battle or not battle.http_json then
        hud.target_error = 'battle API unavailable'
        return
    end
    local pi = game.player_index() or -1
    if pi < 0 then return end
    local char_id = tonumber(game.entity(pi, 'ServerId')) or 0
    if char_id <= 0 then return end
    local entity_id = 0
    local ti = tonumber(game.target('Targets[0].Index')) or 0
    if ti > 0 and game.target('Targets[0].IsActive') ~= 0 then
        entity_id = tonumber(game.entity(ti, 'ServerId')) or 0
    end
    hud.target_polling = true
    xi.tasks.spawn(function()
        local path = string.format('/api/v1/characters/%d/target', char_id)
        if entity_id > 0 then path = path .. '?entity_id=' .. entity_id end
        local ok, data, err = pcall(function() return battle.http_json('GET', path) end)
        hud.target_polling = false
        if ok and type(data) == 'table' then
            hud.target_data, hud.target_error = data, nil
        else
            -- http_json hands back the server's error body, which is a table
            -- ({"error":{code,message}}); tostring on that is what drew
            -- "Server state: table: 0x..." in the window.
            local why = (ok and err) or data
            if type(why) == 'table' then
                why = why.message or why.code or 'the target API answered with an error'
            end
            hud.target_data = nil
            hud.target_error = tostring(why or 'no target data')
        end
    end)
end

function hud.target_window(api)
    local state = hud.state
    if not state.show_target then return end
    local data = hud.target_data
    local target = type(data) == 'table' and data.target or nil
    local effects = type(data) == 'table' and type(data.effects) == 'table' and data.effects or {}
    local summary = ''
    if hud.state.collapsed['fanxi-target'] then
        local count = 0
        for _, effect in ipairs(effects) do
            if not effect.hidden then count = count + 1 end
        end
        summary = 'No target'
        if target then
            summary = string.format('%s %.0f%%  ·  %d debuff%s', tostring(target.name),
                tonumber(target.hpp) or 0, count, count == 1 and '' or 's')
        end
    end
    local width = 360
    local height = target and math.min(380, 82 + math.max(1, #effects) * 28) or 96
    local screen_w, screen_h = hud_screen_size(api)
    local pos = state.target or { x = 900, y = 100 }
    local x = math.max(0, math.min(pos.x, math.max(0, screen_w - width - 4)))
    local y = math.max(0, math.min(pos.y, math.max(0, screen_h - height - 4)))
    -- Once: the saved position places it, then the title bar can drag it and the release
    -- below writes the new place back to the character file.
    api.SetNextWindowPos({ x, y }, 4)
    api.SetNextWindowSize({ width, height }, 1)
    api.SetNextWindowBgAlpha(0.92)
    -- The title-bar arrow collapses the window to its title (the same way the Battle HUD and
    -- Magic Bag minimise); the X and the Hide button switch it off entirely.
    local close = { state.show_target }
    local heading = 'Target Debuffs' .. (summary ~= '' and ('  ' .. summary) or '')
    hud.collapse_prepare(api, 'fanxi-target')
    local open = api.Begin(heading .. '###fanxi-target', close, 2 + 8 + 256)
    local now_collapsed = hud.collapse_observe(api, 'fanxi-target')
    if not now_collapsed and close[1] ~= state.show_target then
        state.show_target = close[1]
        hud_save(state, hud.path)
    end
    if api.IsMouseReleased(0) then
        local wx, wy = api.GetWindowPos()
        if math.abs((wx or pos.x) - pos.x) > 0.5 or math.abs((wy or pos.y) - pos.y) > 0.5 then
            state.target.x, state.target.y = wx, wy
            hud_save(state, hud.path)
        end
    end
    if open then
        if api.Button('Hide##fanxi-target-hide', { 44, 18 }) then
            state.show_target = false
            hud_save(state, hud.path)
        end
        api.SameLine(0, 8)
        if not target then
            api.Text(hud.target_error and ('Target info unavailable: ' .. tostring(hud.target_error))
                or 'No target selected.')
        else
            api.PushFont(nil, 11)
            api.Text(string.format('%s  %.1f%%', tostring(target.name),
                tonumber(target.hpp) or 0))
            api.PopFont()
            api.Separator()
            if #effects == 0 then
                api.Text('No active debuffs.')
            else
                api.BeginChild('##fanxi-target-list', { 0, math.max(24, height - 80) }, 1, 0)
                for _, effect in ipairs(effects) do
                    if not effect.hidden then
                        local icon = hub_status_texture(effect.icon or effect.id)
                        if icon then
                            api.Image(icon, { 24, 24 })
                            api.SameLine(0, 6)
                        end
                        local name = tostring(effect.name or '')
                        if name == '' then
                            local status = hub_status_record(effect.id)
                            name = status and status.name or ('Effect ' .. tostring(effect.id))
                        end
                        local detail = {}
                        if (tonumber(effect.potency) or 0) > 0 then
                            detail[#detail + 1] = string.format('-%d%%', tonumber(effect.potency))
                        end
                        if (tonumber(effect.tick) or 0) > 0 then
                            detail[#detail + 1] = string.format('%d/%ds', tonumber(effect.tick),
                                tonumber(effect.tick_interval) or 3)
                        end
                        api.Text(string.format('%s  %s  %s', name,
                            hub_time(effect.remaining), table.concat(detail, ' ')))
                    end
                end
                api.EndChild()
            end
        end
    end
    api.End()
end

-- --- hub entry points -------------------------------------------------------------------------

local function hub_tick()
    hub_fps_tick()
    battle_tick()
    hub_native_fps_sync()
end

-- --- Equip View ------------------------------------------------------------------------------
-- The in-game EquipViewer, wearing the client's own equip window: the blue title bar, the set
-- line under it, and a flush 4x4 grid of the game's item icons (which carry the coloured
-- background the equip screen shows). Every frame reads the worn pieces straight out of the
-- client (the same equipment indexes the launcher's gear command reads), so a swap draws the
-- instant it happens -- what the original addon bought with its 0x050 packet hook. The collapsed
-- title bar carries the set the phase engine is wearing, the one thing the icons alone cannot say.
-- There is no label row under the cells: the boxes touch, and an empty box carries its slot
-- name as a watermark inside it, the way the client's item picker labels an empty tile.
-- Everything lives on `hud` rather than in locals: hud_init is at LuaJIT's 200-local limit,
-- and these helpers are only ever called from hud.frame.

-- EquipViewer's exact grid (Windower's): main/sub/range/ammo, head/neck/ear1/ear2,
-- body/hands/ring1/ring2, back/waist/legs/feet.  kind is the client's equipment index.
hud.equipview_slots = {
    { key = 'main', kind = 0 }, { key = 'sub', kind = 1 }, { key = 'range', kind = 2 },
    { key = 'ammo', kind = 3 }, { key = 'head', kind = 4 }, { key = 'neck', kind = 9 },
    { key = 'ear1', kind = 11 }, { key = 'ear2', kind = 12 }, { key = 'body', kind = 5 },
    { key = 'hands', kind = 6 }, { key = 'ring1', kind = 13 }, { key = 'ring2', kind = 14 },
    { key = 'back', kind = 15 }, { key = 'waist', kind = 10 }, { key = 'legs', kind = 7 },
    { key = 'feet', kind = 8 },
}
hud.equipview_labels = {
    main = 'Main', sub = 'Sub', range = 'Range', ammo = 'Ammo', head = 'Head', neck = 'Neck',
    ear1 = 'L.Ear', ear2 = 'R.Ear', body = 'Body', hands = 'Hands', ring1 = 'L.Ring',
    ring2 = 'R.Ring', back = 'Back', waist = 'Waist', legs = 'Legs', feet = 'Feet',
}

-- BEGIN Equip View grid geometry
-- A cell's top-left in window-content pixels.  The four columns touch: there is no gutter and
-- no label row, so the 4x4 grid is one flush block like the client's item picker.
function hud.equipview_cell_rect(index, x, y, cell)
    local col = (index - 1) % 4
    local row = math.floor((index - 1) / 4)
    return x + col * cell, y + row * cell
end

-- The text inside a cell: none while the slot holds an item (the icon says it), and the slot
-- name while it is empty, drawn as the box's watermark.  It is never a label under the box.
function hud.equipview_cell_text(id, label)
    if (tonumber(id) or 0) > 0 then return nil end
    return label
end
-- END Equip View grid geometry

hud.equipview_names = {}

function hud.equipview_name(id)
    if not id or id <= 0 then return nil end
    local cached = hud.equipview_names[id]
    if cached ~= nil then return cached or nil end
    local name = item_name(id)
    hud.equipview_names[id] = name or false
    return name
end

-- The item id on one equipment slot.  game.equipment returns (slot, index): the packed
-- bag * 256 + slot is the SECOND value (gear() destructures `local _, index = ...` too);
-- taking the first read inventory slots 0..15 and drew unrelated items.  Slot 0 is empty.
function hud.equipview_worn(kind)
    local ok, _, index = pcall(game.equipment, kind)
    if not ok then return 0 end
    index = tonumber(index) or 0
    local bag, slot = math.floor(index / 256), index % 256
    if slot <= 0 then return 0 end
    local ok_item, id = pcall(game.item, bag, slot, 'Id')
    return ok_item and tonumber(id) or 0
end

function hud.equipview_set()
    if not xi.phase then return 'GearSwap off' end
    local ok, status = pcall(xi.phase.status)
    if not ok or type(status) ~= 'table' then return 'GearSwap off' end
    return status.actionSet or status.set or 'no set', status
end

-- BEGIN Equip View window
function hud.equipview_window(api)
    local set_name, status = hud.equipview_set()
    local action_set = status and status.actionSet or nil
    -- The collapsed title bar repeats this line, so the minimized bar says which set is on.
    local summary = set_name
    if action_set and status.actionMs then
        summary = set_name .. string.format('  %.1fs', status.actionMs / 1000)
    end
    local state = hud.state
    -- 4 cells of 51 px touch with no gutter: the game's item picker lays its boxes out the same
    -- way, which is what leaves no room for the old label row under each icon.
    local cell = 51
    local width, height = 216, 268
    -- A negative saved position means "not placed yet": park it in the top-right corner, out of
    -- the default action-window columns, and save the computed place after the first draw.
    local screen_w = select(1, hud_screen_size(api))
    local x, y = state.equipview.x, state.equipview.y
    if x < 0 or y < 0 then
        x = math.max(8, screen_w - width - 16)
        y = 80
    end

    -- The game's equip window: a blue title bar over a dark panel.  The window keeps ImGui's
    -- title bar (it is what drags and collapses); this paints the game's frame over it in the
    -- window's own draw list, so it stays under every window raised after this one.  The content
    -- clip starts below the title bar, so the paint pushes a clip for the full window.
    local title_height = api.GetFrameHeight and api.GetFrameHeight() or 24
    local function frame(a, wx, wy, ww, wh, collapsed)
        local draw = a.GetWindowDrawList()
        local bar_bottom = collapsed and wh or title_height
        local pad_x = 4
        if a.GetStyle then
            local ok, style = pcall(a.GetStyle)
            if ok and style and style.FramePadding and style.FramePadding[1] then
                pad_x = style.FramePadding[1]
            end
        end
        local clipped = draw.PushClipRect ~= nil
        if clipped then draw:PushClipRect({ wx, wy }, { wx + ww, wy + wh }, false) end
        if draw.AddRectFilledMultiColor then
            draw:AddRectFilledMultiColor({ wx, wy }, { wx + ww, wy + bar_bottom },
                hud_color(96, 130, 178, 255), hud_color(96, 130, 178, 255),
                hud_color(43, 68, 106, 255), hud_color(43, 68, 106, 255))
        else
            draw:AddRectFilled({ wx, wy }, { wx + ww, wy + bar_bottom },
                hud_color(62, 91, 134, 255))
        end
        -- Bevel: a lit top edge and a dark bottom edge, like the client's menu bars.
        draw:AddRectFilled({ wx, wy }, { wx + ww, wy + 1 }, hud_color(214, 230, 250, 46))
        draw:AddRectFilled({ wx, wy + bar_bottom - 1 }, { wx + ww, wy + bar_bottom },
            hud_color(0, 0, 0, 110))
        -- Caret, over ImGui's own collapse button so a click toggles the window like the game.
        local font_size = a.GetFontSize and a.GetFontSize() or 18
        local ax, ay = wx + pad_x + font_size * 0.5, wy + bar_bottom * 0.5
        local white = hud_color(242, 247, 253, 255)
        if collapsed then
            draw:AddTriangleFilled({ ax - 3, ay - 4 }, { ax - 3, ay + 4 }, { ax + 3, ay }, white)
        else
            draw:AddTriangleFilled({ ax - 4, ay - 3 }, { ax + 4, ay - 3 }, { ax, ay + 3 }, white)
        end
        local tx = wx + pad_x + font_size + 8
        local ty = wy + math.floor((bar_bottom - 16) / 2)
        a.PushFont(nil, 16)
        draw:AddText({ tx + 1, ty + 1 }, hud_color(0, 0, 0, 130), 'Equip View')
        draw:AddText({ tx, ty }, white, 'Equip View')
        local tw = a.CalcTextSize('Equip View')
        a.PopFont()
        if collapsed and summary ~= '' then
            a.PushFont(nil, 11)
            local sx = tx + tw + 9
            local sy = wy + math.floor((bar_bottom - 11) / 2) + 1
            draw:AddText({ sx + 1, sy + 1 }, hud_color(0, 0, 0, 110), summary)
            draw:AddText({ sx, sy }, hud_color(206, 221, 241, 235), summary)
            a.PopFont()
        end
        -- The client frames each menu window with a 1 px pale border.
        draw:AddRect({ wx + 0.5, wy + 0.5 }, { wx + ww - 0.5, wy + wh - 0.5 },
            hud_color(150, 163, 180, 66), 0, 0, 1)
        if clipped then draw:PopClipRect() end
    end

    -- Even if an old host cannot paint the frame, the title bar is still blue and the caption
    -- still white; the paint only replaces it when every primitive is there.
    local tinted = api.PushStyleColor ~= nil
    if tinted then
        api.PushStyleColor(2, hud_color(21, 24, 32, 255))   -- WindowBg
        api.PushStyleColor(10, hud_color(58, 88, 132, 255)) -- TitleBg
        api.PushStyleColor(11, hud_color(64, 96, 142, 255)) -- TitleBgActive
        api.PushStyleColor(12, hud_color(52, 80, 120, 255)) -- TitleBgCollapsed
    end
    -- NoScrollbar (8) + NoScrollWithMouse (16): the 4x4 block is sized to fit; the wheel must
    -- not shift a window that never shows a bar.
    local open = hub_window_begin(api, 'Equip View', 'fanxi-equipview',
        x, y, width, height, state.opacity, summary, nil, 24, frame)
    if not open then
        if tinted then api.PopStyleColor(4) end
        return
    end
    local px, py = api.GetWindowPos()
    state.equipview.x, state.equipview.y = px, py

    local draw = api.GetWindowDrawList()
    local cx, cy = api.GetCursorScreenPos()
    local content_w = cell * 4

    -- The set line, in the game's pale grey; gold while an action holds its own set.
    api.PushFont(nil, 16)
    local name_color = action_set and hub_rgba(HUB_C.gold) or hud_color(218, 223, 230, 255)
    draw:AddText({ cx + 1, cy + 2 }, hud_color(0, 0, 0, 120), set_name)
    draw:AddText({ cx, cy + 1 }, name_color, set_name)
    local name_w = api.CalcTextSize(set_name)
    api.PopFont()
    if action_set and status and status.actionMs then
        api.PushFont(nil, 11)
        draw:AddText({ cx + name_w + 9, cy + 4 },
            hud_color(152, 163, 178, 255), string.format('%.1fs', status.actionMs / 1000))
        api.PopFont()
    end
    -- The thin rule the client draws under the set line.
    draw:AddRectFilled({ cx, cy + 21 }, { cx + content_w, cy + 22 },
        hud_color(150, 162, 178, 58))

    local locked = {}
    if status and type(status.lockedSlots) == 'table' then
        for _, index in ipairs(status.lockedSlots) do locked[index] = true end
    end
    local grid_top = cy + 27
    local edge = hud_color(142, 155, 172, 155)
    local edge_hot = hud_color(232, 242, 253, 235)
    local tile = hud_color(10, 12, 17, 220)
    local slot = hud_color(38, 43, 54, 232)
    for i, entry in ipairs(hud.equipview_slots) do
        local x0, y0 = hud.equipview_cell_rect(i, cx, grid_top, cell)
        local x1, y1 = x0 + cell, y0 + cell
        -- An invisible button per box gives the tooltip and the hover edge without drawing a
        -- second copy of the cell over the icon.
        api.SetCursorScreenPos({ x0, y0 })
        api.InvisibleButton('##fanxi-equipview-' .. entry.key, { cell, cell })
        local hovered = api.IsItemHovered()
        local id = hud.equipview_worn(entry.kind)
        -- The client's item icons already carry the coloured background the equip screen shows
        -- (green/blue/white by item kind), so they are drawn edge to edge in the cell.
        local texture = id > 0 and hud_item_texture(id) or nil
        draw:AddRectFilled({ x0, y0 }, { x1, y1 }, texture and tile or slot)
        if texture then
            if draw.AddImageRounded then
                draw:AddImageRounded(texture, { x0 + 1, y0 + 1 }, { x1 - 1, y1 - 1 },
                    { 0, 0 }, { 1, 1 }, hud_color(255, 255, 255, 255), 2, 0)
            else
                draw:AddImage(texture, { x0 + 1, y0 + 1 }, { x1 - 1, y1 - 1 },
                    { 0, 0 }, { 1, 1 }, hud_color(255, 255, 255, 255))
            end
        else
            -- No label row under the grid any more: an empty box wears its slot name as the
            -- watermark the client's item picker puts in an empty tile.
            local label = hud.equipview_cell_text(id, hud.equipview_labels[entry.key])
            if label then
                draw:AddRectFilled({ x0 + 2, y0 + 1 }, { x1 - 2, y0 + 2 },
                    hud_color(255, 255, 255, 14))
                api.PushFont(nil, 13)
                local lw, lh = api.CalcTextSize(label)
                if lw > cell - 4 then
                    api.PopFont()
                    api.PushFont(nil, 11)
                    lw, lh = api.CalcTextSize(label)
                end
                local lx = x0 + (cell - lw) / 2
                local ly = y0 + (cell - lh) / 2
                draw:AddText({ lx + 1, ly + 1 }, hud_color(0, 0, 0, 120), label)
                draw:AddText({ lx, ly }, hud_color(228, 237, 248, 104), label)
                api.PopFont()
            end
        end
        local pinned = locked[entry.kind] == true
        draw:AddRect({ x0, y0 }, { x1, y1 },
            pinned and hud_color(228, 76, 84, 245) or (hovered and edge_hot or edge),
            2, 0, pinned and 2 or 1)
        local name = hud.equipview_name(id)
        api.SetItemTooltip((name or '(empty)') .. '\n' .. hud.equipview_labels[entry.key])
    end
    api.End()
    api.PopStyleVar(2)
    if tinted then api.PopStyleColor(4) end
end
-- END Equip View window

local function hub_draw(api)
    if hud.state.show_inventory then
        hud.inventory_window(api)
    elseif hud.inv_state.card then
        -- The window (and with it the modal card) is gone; do not make the card reappear
        -- the next time Magic Bag is opened.
        hud.inv_state.card = nil
        hud.inv_state.card_open = nil
    end
    if hud.state.show_battle_info then battle_window(api) end
    if hud.state.show_party_info then party_window(api) end
    if hud.state.show_mounts then hud.mount_hud.draw(api) end
end

-- The opaque box in the middle of the screen while move mode is on.  It is drawn after every
-- window and those windows cannot raise themselves above it (NoBringToFrontOnFocus), so it stays
-- readable and clickable no matter which window was grabbed last.  Clicking Done is the in-game
-- way out; the exact same save is available as `//hud save`.
local function hud_edit_box(api)
    local screen_w, screen_h = hud_screen_size(api)
    local width, height = 380, 58
    width = math.min(width, math.max(200, screen_w - 8))
    height = math.min(height, math.max(46, screen_h - 8))
    local x = math.max(4, math.floor((screen_w - width) / 2))
    local y = math.max(4, math.floor((screen_h - height) / 2))
    api.SetNextWindowPos({ x, y }, 1)
    api.SetNextWindowSize({ width, height }, 1)
    -- Put the box back in front after every drag.  Raising it while the mouse is up cannot
    -- interrupt a window being moved, and the windows cannot raise themselves above it.
    if api.SetNextWindowFocus and not (api.IsMouseDown and api.IsMouseDown(0)) then
        api.SetNextWindowFocus()
    end
    api.SetNextWindowBgAlpha(1) -- solid, also when the user lowered the HUD opacity
    local tinted = api.PushStyleColor ~= nil
    if tinted then
        api.PushStyleColor(2, hud_color(8, 10, 14, 255)) -- ImGuiCol_WindowBg
    end
    api.PushStyleVar(2, { 8, 5 })   -- WindowPadding
    api.PushStyleVar(14, { 4, 4 })  -- ItemSpacing
    -- NoTitleBar, NoResize, NoMove, NoScrollbar, NoCollapse, NoSavedSettings
    local open = api.Begin('HUD move###fanxi-hud-move', nil, 1 + 2 + 4 + 8 + 32 + 256)
    if not open then
        api.End()
        api.PopStyleVar(2)
        if tinted then api.PopStyleColor(1) end
        return
    end
    local px, py = api.GetWindowPos()
    local ww, hh = api.GetWindowSize()
    api.GetWindowDrawList():AddRect({ px, py }, { px + ww, py + hh }, HUD_COLOR_ACCENT, 4, 0, 2)
    api.PushFont(nil, 9)
    hub_text(api, HUB_C.dim, 'Drag each window by its title bar, then click Done.')
    api.PopFont()
    if hub_button(api, 'Done', HUB_C.green, width - 18) then
        hud_finish_edit()
        xi.chat.write('HUD: layout saved; move mode off', 1)
    end
    api.End()
    api.PopStyleVar(2)
    if tinted then api.PopStyleColor(1) end
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
    if args.x or args.y or args.reset_position then hud.force_pos.fanxi_battle = true end
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
    if args.x or args.y or args.reset_position then hud.force_pos.fanxi_party = true end
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
    if hud.native_fps_prior ~= nil and xi.fx then
        pcall(xi.fx, 'fps', hud.native_fps_prior)
    end
    hud.native_fps_prior = nil
    for _, texture in pairs(hud.status_tex) do
        if texture then pcall(xi.ui.texture_free, texture) end
    end
    hud.status_tex = {}
end

-- --- chat commands ----------------------------------------------------------------------------

if xi.events and xi.events.on then
    xi.events.on('packet_in', function(e)
        local ok, err = pcall(battle_on_packet, e)
        if not ok and not hud.warned then
            hud.warned = true
            xi.chat.write('Stats: ' .. tostring(err), 1)
        end
    end)
end

xi.events.on('command', function(e)
    if e.blocked then return end
    local line = e.data
    if type(line) ~= 'string' then return end
    local command, rest = line:match('^//([%w_]+)%s*(.*)$')
    if not command then command, rest = line:match('^%!([%w_]+)%s*(.*)$') end
    if not command then command, rest = line:match('^/!([%w_]+)%s*(.*)$') end
    if not command then return end
    command = command:lower()
    if command == 'battle' then
        e.blocked = true
        if hud.battle and hud.battle.command then
            local ok, err = pcall(hud.battle.command, rest or '')
            if not ok then xi.chat.write('Battle: ' .. tostring(err), 1) end
        else
            xi.chat.write('Battle: the battle hub is not loaded.', 1)
        end
        return
    end
    if command == 'hud' then
        e.blocked = true
        hud.ensure()
        rest = (rest or ''):lower():match('^%s*(.-)%s*$') or ''
        if rest == '' or rest == 'toggle' then
            hud.state.show_hud = not hud.state.show_hud
        elseif rest == 'on' or rest == 'show' then
            hud.state.show_hud = true
        elseif rest == 'off' or rest == 'hide' then
            hud.state.show_hud = false
        elseif rest == 'move' or rest == 'edit' then
            hud_begin_edit(false)
            xi.chat.write('HUD: move mode; drag a window by its title bar, then click Done or //hud save', 1)
            return
        elseif rest == 'move reset' or rest == 'reset move' then
            hud_begin_edit(true)
            xi.chat.write('HUD: every window moved to the middle; drag, then click Done or //hud save', 1)
            return
        elseif rest == 'save' then
            local editing = hud.state.edit
            hud_finish_edit()
            xi.chat.write(editing and 'HUD: layout saved; move mode off' or 'HUD: layout saved', 1)
            return
        elseif rest == 'jug' or rest == 'jugs' then
            hud.state.show_hud = true
            hud.open_jug_picker({ name = 'Call Beast', id = 0x200 + 85 })
            xi.chat.write('Call Beast: jug picker shown', 1)
            return
        elseif rest == 'pet' or rest == 'pets' then
            hud.state.show_hud = true
            hud.pet_state.open = true
            hud.pet_state.at = os.clock()
            xi.chat.write('Pet Commands: window shown', 1)
            return
        elseif rest == 'roll' or rest == 'rolls' then
            hud.state.show_hud = true
            hud.cor_open('roll')
            xi.chat.write('Phantom Roll: roll picker shown', 1)
            return
        elseif rest == 'quickdraw' or rest == 'shot' or rest == 'shots' then
            hud.state.show_hud = true
            hud.cor_open('shot')
            xi.chat.write('Quick Draw: shot picker shown', 1)
            return
        elseif rest == 'sch' or rest == 'scholar' or rest == 'sch on' or rest == 'sch off' then
            local shown
            if rest == 'sch on' then shown = true
            elseif rest == 'sch off' then shown = false
            elseif hud.sch and hud.sch.active() then
                shown = not hud.sch_visible()
            else
                -- No Scholar job: the window cannot show, so toggle the stored preference
                -- rather than always computing "on" from an always-hidden window.
                shown = hud.state.show_sch ~= true
            end
            hud.state.show_sch = shown
            if shown then hud.state.show_hud = true end
            hud_save(hud.state, hud.path)
            if hud.sch and hud.sch.active() then
                xi.chat.write('Scholar HUD: ' .. (shown and 'shown' or 'hidden'), 1)
            elseif shown then
                xi.chat.write('Scholar HUD: on, but it only shows on a Scholar main or '
                    .. 'sub job; a support Scholar is scaled to 49.', 1)
            else
                xi.chat.write('Scholar HUD: off', 1)
            end
            return
        elseif rest == 'target' or rest == 'target on' or rest == 'target off'
            or rest == 'debuffs' then
            if rest == 'target on' then
                hud.state.show_target = true
            elseif rest == 'target off' then
                hud.state.show_target = false
            else
                hud.state.show_target = not hud.state.show_target
            end
            hud.state.show_hud = true
            hud.target_at = 0
            hud_save(hud.state, hud.path)
            xi.chat.write('Target Debuffs: ' ..
                (hud.state.show_target and 'shown' or 'hidden'), 1)
            return
        else
            xi.chat.write('HUD: //hud [on|off|toggle|move|move reset|save|jug|pet|roll|quickdraw|target|sch] (Ctrl+H)', 1)
            return
        end
        -- A hidden HUD has no Done box; leave move mode when the HUD is switched off.
        if not hud.state.show_hud and hud.state.edit then hud_finish_edit() end
        hud_save(hud.state, hud.path)
        xi.chat.write('HUD: ' .. (hud.state.show_hud and 'shown' or 'hidden'), 1)
        return
    end
    if command == 'inventory' or command == 'magicbag' or command == 'bags' then
        e.blocked = true
        hud.ensure()
        rest = (rest or ''):lower():match('^%s*(.-)%s*$') or ''
        if rest == 'on' or rest == 'show' then
            hud.state.show_inventory = true
        elseif rest == 'off' or rest == 'hide' then
            hud.state.show_inventory = false
        else
            hud.state.show_inventory = not hud.state.show_inventory
        end
        if hud.state.show_inventory then hud.state.show_hud = true end
        hud_save(hud.state, hud.path)
        xi.chat.write('Magic Bag: ' .. (hud.state.show_inventory and 'shown' or 'hidden'), 1)
        return
    end
    if command == 'equipview' or command == 'equipv' then
        e.blocked = true
        hud.ensure()
        rest = (rest or ''):lower():match('^%s*(.-)%s*$') or ''
        if rest == 'reset' then
            hud.state.equipview.x, hud.state.equipview.y = -1, -1
            hud.force_pos['fanxi-equipview'] = true
            hud.state.show_equipview = true
        elseif rest == 'on' or rest == 'show' then
            hud.state.show_equipview = true
        elseif rest == 'off' or rest == 'hide' then
            hud.state.show_equipview = false
        elseif rest == '' or rest == 'toggle' then
            hud.state.show_equipview = not hud.state.show_equipview
        else
            xi.chat.write('Equip View: //equipview [on|off|toggle|reset]', 1)
            return
        end
        if hud.state.show_equipview then hud.state.show_hud = true end
        hud_save(hud.state, hud.path)
        xi.chat.write('Equip View: ' .. (hud.state.show_equipview and 'shown' or 'hidden'), 1)
        return
    end
    if command == 'mounts' then
        -- The Mount HUD is the client's: bare //mount and //mounts stay here.  Every other
        -- //mount line (a name, an id, "all", "off") is the server's and falls through.
        e.blocked = true
        hud.ensure()
        rest = (rest or ''):lower():match('^%s*(.-)%s*$') or ''
        if rest == '' or rest == 'toggle' then
            hud.state.show_mounts = not hud.state.show_mounts
        elseif rest == 'on' or rest == 'show' then
            hud.state.show_mounts = true
        elseif rest == 'off' or rest == 'hide' then
            hud.state.show_mounts = false
        else
            xi.chat.write('Mount HUD: //mounts [on|off|toggle]', 1)
            return
        end
        if hud.state.show_mounts then
            hud.mount_hud.grid_epoch = (hud.mount_hud.grid_epoch or 0) + 1
        end
        hud_save(hud.state, hud.path)
        xi.chat.write('Mount HUD: ' .. (hud.state.show_mounts and 'shown' or 'hidden'), 1)
        return
    end
    if command == 'mount' then
        rest = (rest or ''):lower():match('^%s*(.-)%s*$') or ''
        if rest == '' or rest == 'hud' or rest == 'window' then
            e.blocked = true
            hud.ensure()
            hud.state.show_mounts = not hud.state.show_mounts
            if hud.state.show_mounts then
                hud.mount_hud.grid_epoch = (hud.mount_hud.grid_epoch or 0) + 1
            end
            hud_save(hud.state, hud.path)
            xi.chat.write('Mount HUD: ' .. (hud.state.show_mounts and 'shown' or 'hidden')
                .. '  (//mount <name|id> calls one)', 1)
        end
        return
    end
    if command ~= 'battleinfo' and command ~= 'info' and
        command ~= 'partyinfo' and command ~= 'party' then return end
    e.blocked = true
    rest = (rest or ''):lower()
    if command == 'battleinfo' or command == 'info' then
        if rest == '' or rest == 'toggle' then
            hud.state.show_battle_info = not hud.state.show_battle_info
            xi.chat.write('Stats: ' .. (hud.state.show_battle_info and 'shown' or 'hidden'), 1)
        elseif rest == 'on' or rest == 'show' then
            hud.state.show_battle_info = true
            xi.chat.write('Stats: shown', 1)
        elseif rest == 'off' or rest == 'hide' then
            hud.state.show_battle_info = false
            xi.chat.write('Stats: hidden', 1)
        elseif rest == 'start' then
            battle_start(); hud.state.show_battle_info = true
            xi.chat.write('Stats: session started', 1)
        elseif rest == 'pause' then
            battle_pause()
            xi.chat.write('Stats: paused', 1)
        elseif rest == 'stop' then
            battle_stop()
            xi.chat.write('Stats: stopped', 1)
        elseif rest == 'reset' then
            battle_reset(); hud.state.show_battle_info = true
            xi.chat.write('Stats: reset and started', 1)
        elseif rest == 'move' then
            hud.state.battle.x, hud.state.battle.y = 470, 96
            hud.force_pos.fanxi_battle = true
            xi.chat.write('Stats: position reset', 1)
        elseif rest == 'fps' then
            hud.state.battle.native_fps = not hud.state.battle.native_fps
            xi.chat.write('Stats: native FPS overlay ' ..
                (hud.state.battle.native_fps and 'shown' or 'moved into the hub'), 1)
        elseif rest == 'auto' then
            hud.state.battle.auto_start = not hud.state.battle.auto_start
            xi.chat.write('Stats: auto-start ' .. (hud.state.battle.auto_start and 'on' or 'off'), 1)
        else
            xi.chat.write('Stats: //battleinfo [on|off|start|pause|stop|reset|move|fps|auto]', 1)
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
            hud.force_pos.fanxi_party = true
            xi.chat.write('Party Info: position reset', 1)
        else
            xi.chat.write('Party Info: //partyinfo [on|off|party|alliance|replace|buffs|names|move]', 1)
        end
        hud_save(hud.state, hud.path)
    end
end)

-- Ctrl+H is the same as //hud toggle, with the chat line open or closed.
if xi.input and xi.input.bind then xi.input.bind(HUD_HOTKEY, '//hud toggle') end

function hud.frame()
    if (game.player_index() or -1) < 0 then return end
    if not hud_character() then return end
    hud.ensure()
    hub_tick()
    if not hud.state.show_hud then return end
    if hud.imgui == nil then
        local ok, api = pcall(xi.ui.imgui)
        hud.imgui = ok and api or false
    end
    local api = hud.imgui
    if not api then return end
    local state = hud.state
    local battle_open = hud.battle and hud.battle.visible and hud.battle.visible() or false
    -- While the Battle hub is up it owns the screen: the action windows and the two information
    -- hubs step aside without changing their saved switches, so they return as soon as it closes.
    local action_on = (state.show_abilities or state.show_spells or state.show_trusts
        or state.show_weapon_skills) and not battle_open
    local battle_overlay = hud.battle and hud.battle.overlay_on and hud.battle.overlay_on() or false
    local hubs_on = ((state.show_battle_info or state.show_party_info or state.show_mounts)
        and not battle_open) or battle_overlay
    -- The pickers (Phantom Roll, Quick Draw, Call Beast) and Pet Commands keep drawing even
    -- when the action windows are off or the Battle hub is up; they are a direct response to a
    -- click.  Target Debuffs is its own switch and keeps its API poll going even when the
    -- other windows are off.
    local dialog_on = hud.jug_state.open or hud.pet_state.open or hud.cor_menu.open
        or hud.trust_menu.open
    local target_on = state.show_target == true
    -- Equip View is its own switch like Target Debuffs: it stays up in the Battle hub and when
    -- the action windows are off, because it is the readout for the gear system itself.
    local equipview_on = state.show_equipview == true
    -- The Scholar HUD is its own switch like Equip View.  It steps aside for the Battle
    -- hub's full editor, the same way the action windows do, so the two never fight.
    local sch_on = hud.sch_visible() and not battle_open
    -- Move mode still draws its Done box with no windows switched on, so the box is never a trap
    -- that cannot be dismissed and //hud save is not the only way out.
    if not action_on and not hubs_on and not state.edit and not dialog_on and not target_on
            and not equipview_on and not sch_on then
        return
    end
    if action_on or hud.pet_state.open or hud.cor_menu.open then
        hud_update_main()
        hud_update_sc()
        hud.rebuild(false)
        if state.show_trusts then hud_refresh_trusts() end
        -- Always poll: the server's table is the source for cooldowns this HUD never saw
        -- start (a relogin restores them into an empty hud.cool).
        hud_update_cool(hud)
    end
    if target_on then hud.target_tick() end

    -- Every window steps aside for a menu or the chat line when menu_hide is on, while the player
    -- is actually in the game. In combat the client's battle/ability menus are part of play, so the
    -- HUD stays up there; the chat line still hides it.
    local hide_hud = false
    if state.menu_hide and not state.edit and game_focused() then
        hide_hud = hud_chat_input_open()
        if not hide_hud and not hud_in_battle() then
            local name = menu_name()
            -- `battle`/`attack` are combat menus, not the right-hand Commands/Status stack; never let
            -- them hide the HUD even if the target dropped before the engagement flag did.
            local lower = type(name) == 'string' and name:lower() or ''
            hide_hud = lower ~= '' and lower ~= 'battle' and lower ~= 'attack'
        end
    end
    if action_on and not hide_hud then
        for _, key in ipairs(HUD_TYPES) do
            if state['show_' .. key] then
                hud_window(api, key, HUD_TYPE_INFO[key].title, hud_grouped(key))
            end
        end
    end
    if hubs_on and not hide_hud then
        if not battle_open then hub_draw(api) end
        if hud.battle and hud.battle.draw then hud.battle.draw(api) end
    end
    if hud.jug_state.open then hud.jug_window(api) end
    if hud.pet_state.open then hud.pet_window(api) end
    if hud.cor_menu.open then hud.cor_window(api) end
    if hud.trust_menu.open then hud.trust_window(api) end
    if target_on and not hide_hud then hud.target_window(api) end
    if equipview_on and not hide_hud then hud.equipview_window(api) end
    if sch_on and not hide_hud and hud.sch then
        local ok_sch, err_sch = pcall(hud.sch.draw, api)
        if not ok_sch and not hud.warned then
            hud.warned = true
            xi.chat.write('Scholar HUD: ' .. tostring(err_sch), 1)
        end
    end
    -- Last, and opaque: the Done box is the one control that must never be hidden by a window.
    if state.edit then hud_edit_box(api) end
    if hud.reposition then hud.reposition = false end
    if hud.clamp_positions then hud.clamp_positions = false end
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

-- The Battle hub owns its own frame tick (it keeps running when the action HUD is hidden) and
-- draws into this overlay.  Loading it inside hud_init keeps it out of the chunk's local limit.
do
    local ok, module = pcall(require, 'xi.battle')
    if ok and type(module) == 'table' then
        hud.battle = module
        local installed, err = pcall(module.install, {
            json = json,
            notify = function(text) xi.chat.write(tostring(text), 1) end,
            chat_open = hud_chat_input_open,
            edit = function() return hud.state.edit end,
        })
        if not installed then
            hud.battle = nil
            xi.chat.write('Battle: could not install (' .. tostring(err) .. ')', 1)
        end
    else
        xi.chat.write('Battle: the battle module is missing (' .. tostring(module) .. ')', 1)
    end
end
-- The Scholar HUD (strategems, self-skillchain macros, magic bursts) is a separate module
-- like the Battle hub: its sets are a file of its own, so it stays out of this chunk's
-- locals and out of the saved HUD layout.  It only needs the chat writer and a way to
-- remember that its title-bar X hid it.  A function keeps its locals off hud_init()'s
-- 200-local budget.
hud.install_sch = function()
    local ok, module = pcall(require, 'xi.sch')
    if not ok or type(module) ~= 'table' then
        xi.chat.write('Scholar: the module is missing (' .. tostring(module) .. ')', 1)
        return
    end
    hud.sch = module
    local installed, err = pcall(module.install, {
        notify = function(text) xi.chat.write(tostring(text), 1) end,
        on_hide = function(shown)
            hud.state.show_sch = shown == true
            if shown then hud.state.show_hud = true end
            hud_save(hud.state, hud.path)
        end,
        get_shown = hud.sch_visible,
        burst_info = phase_burst_info,
    })
    if not installed then
        hud.sch = nil
        xi.chat.write('Scholar: could not install (' .. tostring(err) .. ')', 1)
    end
end
hud.install_sch()
hud.rgba = hub_rgba
hud.colors = HUB_C
end
hud_init()



-- Collapse restore: keep forcing the saved state for the first frames until ImGui has
-- actually created/collapsed the window.  Once it matches, the caret owns the state again.
function hud.collapse_prepare(api, key)
    local want = hud.state.collapsed[key] == true
    api.SetNextWindowCollapsed(want, hud.restore_collapsed[key] and 1 or 4)
end

function hud.collapse_observe(api, key)
    local want = hud.state.collapsed[key] == true
    local now = api.IsWindowCollapsed()
    if hud.restore_collapsed[key] then
        if now == want then hud.restore_collapsed[key] = nil end
    elseif hud.state.collapsed[key] ~= now then
        hud.state.collapsed[key] = now
        hud.save(hud.state, hud.path)
    end
    return now
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
-- One follower controller per client. The launcher sets a leader; this loop replays the
-- path the leader actually ran through the game's own auto-run, so collision, animation
-- and the position packets all stay the client's.
--
-- The trail is a polyline of the leader's positions, and the follower has a cursor into
-- it. It steers at the next *unreached* waypoint, never at a point measured back from the
-- leader's current position: a target behind the leader cuts across the inside of a
-- corner, which is exactly what made a box clip walls. A dense trail (a point every 8 cm)
-- and an in-order cursor make the follower copy the run turn for turn.
local follow = {
    enabled = false,
    leader = nil,
    distance = 1.0,
    trail = {},          -- {x, y} of the leader's path, oldest first
    trail_max = 2400,    -- ~40 s at 60 fps; enough for a long lag, bounded memory
    cursor = 1,          -- index in trail of the next waypoint to reach
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
    last_leader_x = nil,
    last_leader_y = nil,
    lost_at = nil,
    follow_through = 3.0,
    last_self_x = nil,
    last_self_y = nil,
}
local follow_events = {}

-- A waypoint every 8 cm of the leader's path. The old recorder sampled at 10 Hz, which at
-- run speed is one point per ~0.6 yalms; the straight chords between those are what a box
-- cut a corner across. Recording at frame rate keeps the polyline on the path.
local FOLLOW_GAP = 0.08
-- A waypoint this close counts as reached.
local FOLLOW_ACCEPT = 0.15
-- At 30 fps a running character steps further than FOLLOW_ACCEPT in one frame, so a
-- waypoint also counts as reached once its segment has been passed.
local FOLLOW_PASSED = 0.9
-- A bigger single step is a zone change, warp or teleport, not a corner.
local FOLLOW_JUMP = 8.0
-- Stop within this much of the goal waypoint (which is 0.8 * distance behind the leader).
local FOLLOW_STOP = 0.15

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

local function follow_reset_trail()
    follow.trail = {}
    follow.cursor = 1
    follow.last_dir_x, follow.last_dir_y = nil, nil
end

-- Add the leader's position to the path when it has moved FOLLOW_GAP. A jump is a zone
-- change, a warp or a server move, not a corner: the next zone's path starts fresh.
local function follow_record(lp)
    local last = follow.trail[#follow.trail]
    if last then
        local dx, dy = lp.x - last.x, lp.y - last.y
        local moved = math.sqrt(dx * dx + dy * dy)
        if moved < FOLLOW_GAP then return end
        if moved > FOLLOW_JUMP then
            follow_reset_trail()
            last = nil
        end
    end
    follow.trail[#follow.trail + 1] = { x = lp.x, y = lp.y }
    if #follow.trail > follow.trail_max then
        table.remove(follow.trail, 1)
        if follow.cursor > 1 then follow.cursor = follow.cursor - 1 end
    end
end

-- The waypoint `distance * 0.8` yalms of path behind the leader's newest position. The
-- follower stops there: it copies the run without walking onto the leader.
local function follow_goal()
    local need = follow.distance * 0.8
    local index = #follow.trail
    if index < 2 then return index end
    local px, py = follow.trail[index].x, follow.trail[index].y
    while index > 1 do
        local point = follow.trail[index - 1]
        local seg = math.sqrt((px - point.x) ^ 2 + (py - point.y) ^ 2)
        if seg >= need then return index end
        need = need - seg
        px, py = point.x, point.y
        index = index - 1
    end
    return 1
end

-- Move the cursor over every waypoint reached or run past, in order. The passed test is
-- what stops a 30 fps client stepping over a 15 cm waypoint between two frames.
local function follow_advance(pp, goal)
    while follow.cursor < goal do
        local point = follow.trail[follow.cursor]
        local dx, dy = point.x - pp.x, point.y - pp.y
        local d = math.sqrt(dx * dx + dy * dy)
        if d <= FOLLOW_ACCEPT then
            follow.cursor = follow.cursor + 1
        elseif follow.cursor > 1 then
            local anchor = follow.trail[follow.cursor - 1]
            local abx, aby = point.x - anchor.x, point.y - anchor.y
            local seg2 = abx * abx + aby * aby
            if seg2 <= 1e-8 then break end
            local t = ((pp.x - anchor.x) * abx + (pp.y - anchor.y) * aby) / seg2
            if t >= 1.0 and d <= FOLLOW_PASSED then
                follow.cursor = follow.cursor + 1
            else
                break
            end
        else
            break
        end
    end
end

-- Forget the points already behind the follower but keep the last one: the passed test
-- needs the segment that ends at the next waypoint.
local function follow_trim()
    if follow.cursor <= 2 then return end
    for _ = 1, follow.cursor - 2 do table.remove(follow.trail, 1) end
    follow.cursor = 2
end

local function follow_drive(pp, tx, ty)
    local dx, dy = tx - pp.x, ty - pp.y
    local distance = math.sqrt(dx * dx + dy * dy)
    if distance <= math.max(0.08, follow.distance * 0.1) then
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
    local pp = position(pi)
    if pp then
        -- The follower itself being moved (zone-in, warp, //pos) invalidates the path just
        -- as the leader's jump does.
        if follow.last_self_x
            and math.abs(pp.x - follow.last_self_x) + math.abs(pp.y - follow.last_self_y)
                > FOLLOW_JUMP then
            follow_reset_trail()
        end
        follow.last_self_x, follow.last_self_y = pp.x, pp.y
    end
    local li = follow_find(now)
    if not li then
        follow.leader_found = false
        if not follow.lost_at then follow.lost_at = now end
        -- The leader may have just crossed a zone line and vanished from this zone. Keep
        -- walking through the last seen point for a few seconds so the client reaches the
        -- line and sends its own zone request instead of stopping one yalm short.
        if pp and follow.last_leader_x and now - follow.lost_at <= follow.follow_through then
            local dx, dy = follow.last_leader_x - pp.x, follow.last_leader_y - pp.y
            local span = math.sqrt(dx * dx + dy * dy)
            if span > 0.1 then
                local tx = follow.last_leader_x + dx / span * 2.5
                local ty = follow.last_leader_y + dy / span * 2.5
                local moving = follow_drive(pp, tx, ty)
                follow.state = moving and 'following' or 'close'
                return
            end
        end
        follow.state = 'waiting'
        follow_auto_off()
        follow_reset_trail()
        return
    end
    follow.lost_at = nil
    follow.leader_found = true
    local lp = position(li)
    if not lp or not pp then return end
    follow.last_leader_x, follow.last_leader_y = lp.x, lp.y
    follow_record(lp)
    follow_trim()

    local goal = follow_goal()
    follow_advance(pp, goal)
    local stop = follow.trail[goal]
    if stop and follow.cursor >= goal then
        local dx, dy = stop.x - pp.x, stop.y - pp.y
        if math.sqrt(dx * dx + dy * dy) <= FOLLOW_STOP then
            follow.state = 'close'
            follow_auto_off()
            follow.last_dir_x, follow.last_dir_y = nil, nil
            follow.last_x, follow.last_y = pp.x, pp.y
            return
        end
    end
    local target = follow.trail[follow.cursor] or follow.trail[#follow.trail]
    if not target then
        follow.state = 'waiting'
        follow_auto_off()
        return
    end
    local distance, moving = follow_drive(pp, target.x, target.y)
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
    local goal = 0
    if #follow.trail > 0 then goal = follow_goal() end
    return {
        enabled = follow.enabled,
        leader = follow.leader,
        state = follow.state,
        distance = follow.distance,
        stuck = follow.stuck,
        leader_found = follow.leader_found,
        trail = #follow.trail,
        points = #follow.trail,
        cursor = follow.cursor,
        goal = goal,
    }
end

local function follow_config(a)
    follow.enabled = a.enabled ~= false
    if a.leader ~= nil then follow.leader = tostring(a.leader) end
    if a.distance ~= nil then
        follow.distance = math.max(0.3, math.min(5.0, tonumber(a.distance) or 1.0))
    end
    follow_reset_trail()
    follow.stuck = 0
    follow.leader_index = nil
    follow.next_find = 0
    follow.last_check = 0
    follow.last_x, follow.last_y = nil, nil
    follow.last_self_x, follow.last_self_y = nil, nil
    if follow.enabled and follow.leader then follow.state = 'waiting' else follow.state = 'off' end
    if not follow.enabled or not follow.leader then follow_auto_off() end
    return follow_status()
end

local function follow_take_events()
    local out = follow_events
    follow_events = {}
    return out
end

-- `//follow` is ours: block it before the server sees an unknown command and queue it for
-- the launcher, which owns the graph. With no launcher the queue simply waits.
xi.events.on('command', function(e)
    if e.blocked then return end
    local line = e.data
    if type(line) ~= 'string' then return end
    local body = line:match('^//follow%s*(.*)$') or line:match('^/%!follow%s*(.*)$') or
        line:match('^%!follow%s*(.*)$')
    if body == nil then return end
    e.blocked = true
    follow_events[#follow_events + 1] = { line = body, at = xi.clock() }
    xi.chat.write('FOLLOW: ' .. (body ~= '' and body or 'status'), 1)
end)

-- Instrument-granted songs must have their instrument on before the cast packet.
-- The phase engine's midcast set is too late (the server checks at cast start), so
-- intercept the /ma and press the range swap first, then replay the cast.
local SONG_INSTRUMENTS = {
    ['honor march'] = 'Marsyas',
    ['aria of passion'] = 'Loughnashade',
}
local pending_song_cast = nil
local song_replay_line = nil
local function song_request_name(line)
    local body = tostring(line or ''):match('^/[%a]+%s+(.*)$')
    if not body then return nil end
    local name = body:match('^"([^"]+)"') or body:match('^([^%s]+)')
    return name and name:lower() or nil
end
xi.events.on('command', function(e)
    if e.blocked then return end
    if song_replay_line and e.data == song_replay_line then
        song_replay_line = nil
        return
    end
    local instrument = SONG_INSTRUMENTS[song_request_name(e.data) or '']
    if not instrument then return end
    local ok, err = pcall(equip_item, 2, instrument)
    if not ok then
        e.blocked = true
        xi.chat.write('Song: ' .. instrument .. ' is not in the bags', 1)
        return
    end
    e.blocked = true
    pending_song_cast = { line = e.data, at = xi.clock() + 0.35 }
end)
xi.events.on('frame', function()
    if pending_song_cast and xi.clock() >= pending_song_cast.at then
        local line = pending_song_cast.line
        pending_song_cast = nil
        song_replay_line = line
        local ok, err = pcall(xi.chat.run, line, 1)
        if not ok then xi.chat.write('Song: ' .. tostring(err), 1) end
    end
end)

xi.events.on('frame', follow_tick)

local commands = {
    state = function() return state() end,
    sleep = function()
        sleeping = true
        -- The server hides the character and parks its tick; the client and control socket
        -- stay alive, so wake is a command rather than a process launch.
        xi.chat.run("//sleep", 1)
        return state()
    end,
    wake = function()
        sleeping = false
        xi.chat.run("//wake", 1)
        return state()
    end,
    metrics = function() return metrics() end,
    gear = function() return gear() end,
    follow = follow_config,
    follow_status = follow_status,
    follow_events = follow_take_events,
    command = function(a)
        if type(a.line) ~= 'string' or a.line == '' then error('command: line') end
        if not a.line:match('^[/!]') then error('command: the line must start with / or //') end
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
    phase_status = function()
        local status = xi.phase and xi.phase.status() or { enabled = false }
        if phase_plan and phase_plan.spell_modes then status.modes = phase_plan.spell_modes end
        return status
    end,
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
    battle = function(a)
        if not hud.battle then error('the battle hub is not loaded') end
        local result, err = hud.battle.request(a or {})
        if result == nil then error(err or 'the battle hub refused the request') end
        return result
    end,
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
        elseif err == 'timeout' and (function() local co, main = coroutine.running(); return co ~= nil and not main end)() then
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
    if xi.input and xi.input.unbind then pcall(xi.input.unbind, HUD_HOTKEY) end
    if hud then
        if hud.battle and hud.battle.shutdown then pcall(hud.battle.shutdown) end
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
