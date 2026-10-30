--[==[
The Battle hub and its automation engine.

A battle profile is a persisted, per-character description of how one client should fight: the
roster (tank, puller, kiter, support, melee, ranged), the camp and its radius, when that client may
engage, the melee formation around the tank, pull/sleep rules, healing, buffs, enfeebles, dispels,
status removal, death handling and kiting.  The hub is drawn by this module in the same ImGui
overlay as the action HUD; `//battle save` writes the profile as JSON under
`<data>/battle/<character>/`, so the launcher can edit the same file later through the control
port.

Everything here goes through APIs the client already has.  Actions are ordinary client commands
(`/attack`, `/ra`, `/ma`, `/ja`), so the client still owns range checks, cast bars, recast tables
and the packets it sends.  Movement uses the game's own auto-run (`IsAutoRunning`,
`FollowDelta*`), exactly like the follow controller, so collision and position packets stay the
client's.  Claims are read from `ClaimStatus`, which is the claiming character's server id; that is
what lets a melee wait for the tank or puller to claim before it engages.

The server this build talks to has no item drops or treasure pool yet, so the loot policy is saved
and shown but cannot lot anything; the hub says so instead of pretending.
--]==]

local M = {}   -- the installed module (control.lua keeps it as hud.battle)
local C = {}   -- profile: defaults, sanitize, persistence
local B = {}   -- the automation engine
local G = {}   -- world-to-screen projection for the camp circle (guarded: optional)
local H = {}   -- the ImGui hub

local S = {
    installed = false,
    ctx = nil,
    game = nil,
    res = nil,
    character = nil,
    root = nil,
    file = nil,
    profile = nil,
    profiles = {},
    running = false,
    visible = false,
    tab = 'roster',
    notes = {},
    next_tick = 0,
    busy_until = 0,
    pending = nil,
    ui = { x = 360, y = 80, opacity = 0.95 },
    camp_hud_apply = true,
    camp_hud_edit = false,
    camp_hud_restore = false,
    song_groups_open = false,
    song_group_edit = nil,
    song_new_name = '',
    buffers = {},
    profile_seq = 0,
    place = nil,
    last_save = nil,
    runtime = {},
    -- False when the server could not report a live zone roster (an older server, or the game
    -- gateway is off).  The hub then keeps showing every team character instead of guessing that
    -- they are all offline.
    team_online_known = false,
}

local socket_ok, socket = pcall(require, 'socket.core')

local VERSION = 1
local TICK = 0.15
local MAX_ROWS = 24
local ROLES = { 'tank', 'puller', 'kiter', 'support', 'melee', 'ranged' }
local ROLE_LABELS = {
    tank = 'Tank', puller = 'Puller', kiter = 'Kiter', support = 'Support',
    melee = 'Melee', ranged = 'Ranged',
}
local PRIORITIES = { 'heal', 'buff', 'enfeeble', 'dispel' }
local PRIORITY_LABELS = {
    heal = 'Healing', buff = 'Buffs', enfeeble = 'Enfeebling', dispel = 'Dispelling',
}
local ENGAGE_MODES = { 'tank', 'puller', 'player', 'leader', 'always', 'none' }
local ENGAGE_LABELS = {
    tank = 'When the tank has claim',
    puller = 'When the puller has claim',
    player = 'When a named player has claim',
    leader = 'When the party leader has claim',
    always = 'On any party claim',
    none = 'Never',
}
local PULL_METHODS = { 'ranged', 'spell', 'ability', 'melee' }
local PULL_LABELS = {
    ranged = 'Ranged attack', spell = 'Spell', ability = 'Job ability', melee = 'Melee pull',
}
local PULL_LABEL_LIST = { 'Ranged attack', 'Spell', 'Job ability', 'Melee pull' }
local ENGAGE_LABEL_LIST = {
    'When the tank has claim', 'When the puller has claim', 'When a named player has claim',
    'When the party leader has claim', 'On any party claim', 'Never',
}
local OBSERVE_MODES = { 'party', 'alliance' }
local OBSERVE_LABELS = { 'Party only', 'Party + alliance' }
local DEATH_MODES = { 'raise', 'homepoint' }
local LOOT_MODES = { 'free', 'lot', 'pass', 'leader' }

-- Weapon-skill skillchain properties, keyed by weapon-skill id.  Copied from the
-- client's generated table (data/skillchains.json); battle.lua cannot see control.lua's
-- locals.  The planner uses these ids to walk the directional skillchain map.
local SC_WS_PROPS = {
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

local SC_NAMES = {
    [0] = 'none', 'Transfixion', 'Compression', 'Liquefaction', 'Scission', 'Reverberation',
    'Detonation', 'Induration', 'Impaction', 'Gravitation', 'Distortion',
    'Fusion', 'Fragmentation', 'Light', 'Darkness', 'Light II', 'Darkness II',
}
local SC_TIER = { [0] = 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 4, 4 }
local SC_LABELS = { 'Any' }
for id = 1, 16 do SC_LABELS[#SC_LABELS + 1] = string.format('L%d %s', SC_TIER[id], SC_NAMES[id]) end

-- Directional (closing skill, existing resonance) -> formed chain, from skillchain.py.
local SC_TRANS = {}
local SC_PAIRS = {
    { 13, 13, 15 }, { 14, 14, 16 },
    { 10, 9, 14 }, { 12, 9, 12 }, { 9, 10, 14 }, { 11, 10, 11 }, { 9, 11, 9 },
    { 12, 11, 13 }, { 10, 12, 10 }, { 11, 12, 13 },
    { 4, 1, 10 }, { 8, 3, 11 }, { 2, 6, 9 }, { 5, 7, 12 },
    { 2, 1, 2 }, { 5, 1, 5 }, { 1, 2, 1 }, { 6, 2, 6 }, { 4, 3, 4 }, { 3, 4, 3 },
    { 5, 4, 5 }, { 6, 4, 6 }, { 7, 5, 7 }, { 8, 5, 8 }, { 4, 6, 4 }, { 2, 7, 2 },
    { 8, 7, 8 }, { 3, 8, 3 }, { 6, 8, 6 },
}
for _, row in ipairs(SC_PAIRS) do
    SC_TRANS[row[1]] = SC_TRANS[row[1]] or {}
    SC_TRANS[row[1]][row[2]] = row[3]
end
local SC_OPEN_SECONDS = 11.0
local SC_CHAIN_DELAY = 3.0
local SC_MAX_STEPS = 12
local SC_MAX_BURSTERS = 4
local SC_DIAMOND_ASPIS = 26488

local function sc_name(id) return SC_NAMES[tonumber(id) or 0] or 'none' end
local function sc_tier(id) return SC_TIER[tonumber(id) or 0] or 0 end

local KITE_MODES = { 'circle', 'away', 'camp' }

local HUB_TABS = {
    { key = 'roster', label = 'Roster', group = 'Shared settings' },
    { key = 'camp', label = 'Camp', group = 'Shared settings' },
    { key = 'rules', label = 'Rules', group = 'Shared settings' },
    { key = 'engage', label = 'Engage', group = 'Player settings' },
    { key = 'skillchain', label = 'Skillchain', group = 'Player settings' },
    { key = 'pull', label = 'Pulling', group = 'Player settings' },
    { key = 'heal', label = 'Healing', group = 'Player settings' },
    { key = 'buff', label = 'Buffs', group = 'Player settings' },
    { key = 'support', label = 'Support', group = 'Player settings' },
    { key = 'debuff', label = 'Debuffs', group = 'Player settings' },
    { key = 'profile', label = 'Profile', group = 'Player settings' },
}


local function clock()
    local ok, value = pcall(xi.clock)
    return ok and tonumber(value) or os.clock()
end

local function clamp(value, low, high, fallback)
    value = tonumber(value)
    if not value or value ~= value then return fallback end
    if value < low then return low end
    if value > high then return high end
    return value
end

local function whole(value, low, high, fallback)
    return math.floor(clamp(value, low, high, fallback) + 0.5)
end

local function text(value, cap)
    if type(value) == 'table' then
        value = value.en or value[1] or ''
    end
    value = type(value) == 'string' and value or ''
    value = value:gsub('^%s+', ''):gsub('%s+$', '')
    cap = cap or 64
    if #value > cap then value = value:sub(1, cap) end
    return value
end

local function truth(value, fallback)
    if type(value) == 'boolean' then return value end
    return fallback and true or false
end

local function copy(value)
    if type(value) ~= 'table' then return value end
    local out = {}
    for key, item in pairs(value) do out[key] = copy(item) end
    return out
end

local function contains(list, value)
    for _, item in ipairs(list or {}) do
        if item == value then return true end
    end
    return false
end

local function remove_value(list, value)
    for index = #list, 1, -1 do
        if list[index] == value then table.remove(list, index) end
    end
end

local function split_words(line)
    local words = {}
    line = tostring(line or '')
    local index = 1
    while index <= #line do
        while index <= #line and line:sub(index, index):match('%s') do index = index + 1 end
        if index > #line then break end
        local word = {}
        local quote = false
        if line:sub(index, index) == '"' then
            quote = true
            index = index + 1
        end
        while index <= #line do
            local char = line:sub(index, index)
            if quote then
                if char == '"' then index = index + 1 break end
            elseif char:match('%s') then
                break
            end
            word[#word + 1] = char
            index = index + 1
        end
        if not quote then
            while index <= #line and line:sub(index, index):match('%s') do index = index + 1 end
        end
        words[#words + 1] = table.concat(word)
    end
    return words
end

local function slug(value)
    local out = tostring(value or ''):lower():gsub('[^%w%-_]+', '-'):gsub('%-+', '-'):gsub('^%-', ''):gsub('%-$', '')
    if out == '' then out = 'battle' end
    return out:sub(1, 80)
end

local function join_path(folder, name)
    folder = tostring(folder or '')
    if folder ~= '' and folder:sub(-1) ~= '/' and folder:sub(-1) ~= '\\' then folder = folder .. '/' end
    return folder .. tostring(name or '')
end

local function read_file(path)
    local file = io.open(path, 'rb')
    if not file then return nil end
    local data = file:read('*a')
    file:close()
    return data
end

local function write_file(path, data)
    if xi.fs and xi.fs.mkdir then
        local folder = path:match('^(.*)[/\\][^/\\]*$')
        if folder then pcall(xi.fs.mkdir, folder) end
    end
    local file = io.open(path, 'wb')
    if not file then return false end
    local ok = file:write(data)
    file:close()
    return ok ~= nil
end

local function decode(data)
    if type(data) ~= 'string' or data == '' then return nil end
    local ok, value = pcall(S.ctx.json.decode, data)
    if ok and type(value) == 'table' then return value end
    return nil
end

local function encode(value)
    local ok, data = pcall(S.ctx.json.encode, value)
    return ok and data or nil
end

-- --- central team rules -----------------------------------------------------------------------
-- The server owns one Battle profile per character.  The launcher passes the HTTP endpoint and
-- the main account's token in FANXI_API_URL / FANXI_API_TOKEN; a local development client can also
-- read them from the launcher's config file.  Clients apply the profile they receive, which is the
-- server's instruction for that box.
local function api_config()
    if S.api_url and S.api_token then return S.api_url, S.api_token end
    local url = os.getenv('FANXI_API_URL') or ''
    local token = os.getenv('FANXI_API_TOKEN') or ''
    if url == '' or token == '' then
        local home = os.getenv('HOME') or ''
        local path = home .. '/Library/Application Support/Fanxi/launcher.json'
        local raw = read_file(path)
        local data = raw and decode(raw) or nil
        if type(data) == 'table' then
            url = tostring(data.api_url or '')
            token = tostring(data.token or '')
        end
    end
    url = tostring(url):gsub('/+$', '')
    S.api_url, S.api_token = url, token
    return url, token
end

local function http_json(method, path, body)
    if not socket_ok or not socket then return nil, 'LuaSocket is not available' end
    local base, token = api_config()
    local host, port = tostring(base):match('^http://([^/:]+):?(%d*)$')
    if not host then return nil, 'no HTTP API configured' end
    port = tonumber(port) or 80
    if token == '' then return nil, 'no API token' end
    local data = body and encode(body) or nil
    if body and not data then return nil, 'could not encode the request' end
    local sock = socket.tcp()
    if not sock then return nil, 'no socket' end
    sock:settimeout(1.0)
    local ok, err = sock:connect(host, port)
    if not ok then sock:close(); return nil, tostring(err or 'connect failed') end
    local head = string.format('%s %s HTTP/1.1\r\nHost: %s:%d\r\nAuthorization: Bearer %s\r\nConnection: close\r\n',
        method, path, host, port, token)
    if data then
        head = head .. string.format('Content-Type: application/json\r\nContent-Length: %d\r\n', #data)
    end
    sock:send(head .. '\r\n' .. (data or ''))
    local chunks = {}
    while true do
        local chunk, recv_err, partial = sock:receive(4096)
        if chunk and #chunk > 0 then chunks[#chunks + 1] = chunk end
        if not chunk and partial and #partial > 0 then chunks[#chunks + 1] = partial end
        if recv_err then break end
    end
    sock:close()
    local response = table.concat(chunks)
    local split = response:find('\r\n\r\n', 1, true)
    if not split then return nil, 'bad HTTP response' end
    local status = tonumber(response:match('^HTTP/%d+%.%d+%s+(%d+)')) or 0
    local payload = response:sub(split + 4)
    local decoded = decode(payload)
    if status < 200 or status >= 300 then
        return nil, (decoded and decoded.error) or ('HTTP ' .. status)
    end
    return decoded
end

-- The action HUD's Target Debuffs window uses the same authenticated client; keep one
-- HTTP implementation in the addon rather than a second socket client in control.lua.
-- M is what require('xi.battle') returns; B is the automation engine.
B.http_json = http_json
M.http_json = http_json

function B.team_poll()
    local now = clock()
    if now < (S.team_poll_at or 0) then return end
    S.team_poll_at = now + 6
    local data = http_json('GET', '/api/v1/battle/team')
    if type(data) ~= 'table' or type(data.characters) ~= 'table' then
        S.team_poll_at = now + 30
        return
    end
    S.team = data.characters
    S.team_online_known = data.online_known == true
    -- Keep the list (and its live flags) fresh while editing another character, but do not
    -- apply the local profile or seed it: the hub is showing the remote draft.
    if S.remote_edit then return end
    local self = B.self()
    local me = self and self.name or ''
    for _, character in ipairs(S.team) do
        if character.name == me and type(character.profile) == 'table' then
            local incoming = tonumber(character.profile.updated) or 0
            if incoming > (tonumber(S.profile.updated) or 0) then
                local applied = C.sanitize(character.profile)
                if applied and applied.name ~= '' then
                    local wanted_run = applied.engine and applied.engine.running
                    S.profile = applied
                    S.dirty = false
                    if wanted_run ~= nil and wanted_run ~= S.running then
                        if wanted_run then B.start() else B.stop() end
                    end
                    B.note('info', 'Battle: applied server rules for ' .. me .. '.')
                end
            end
        elseif character.name == me and not S.team_seeded then
            local saved = B.team_save_profile()
            if saved then S.team_seeded = true end
        end
    end
end

function B.team_save_profile(name, shared)
    if not S.profile then return nil, 'no profile' end
    local target_name = text(name, 32)
    if target_name == '' then
        local self = B.self()
        target_name = self and self.name or ''
    end
    local id = nil
    for _, character in ipairs(S.team or {}) do
        if character.name == target_name then id = character.character_id break end
    end
    if not id then return nil, 'server team list has no ' .. target_name end
    local data, err = http_json('PUT', '/api/v1/battle/team/' .. tostring(id), { profile = S.profile, shared = shared == true })
    if not data then return nil, err end
    if data.profile then S.profile.updated = data.profile.updated end
    S.dirty = false
    B.note('info', 'Battle: saved server rules for ' .. target_name .. '.')
    return data
end

function B.team_switch(name)
    name = text(name, 32)
    local self = B.self()
    local me = self and self.name or ''
    if name == '' or name == me then B.team_restore(); return true end
    local character = nil
    for _, row in ipairs(S.team or {}) do
        if row.name == name then character = row break end
    end
    if not character then B.note('error', 'Battle: ' .. name .. ' is not in the server team list.'); return false end
    if not S.remote_edit then S.self_profile = S.profile end
    S.remote_edit = { name = name, character_id = character.character_id }
    S.running = false
    B.stop_move()
    local draft = character.profile
    if type(draft) ~= 'table' then draft = C.default_profile(name) end
    S.profile = C.sanitize(draft)
    S.profile.name = name
    S.dirty = false
    B.note('info', 'Battle: editing server rules for ' .. name .. '; this box is paused.')
    return true
end

function B.team_restore()
    if S.self_profile then
        S.profile = S.self_profile
        S.self_profile = nil
    end
    S.remote_edit = nil
    S.dirty = false
    if S.profile then
        S.ui.x, S.ui.y = S.profile.ui.x or S.ui.x, S.profile.ui.y or S.ui.y
        S.ui.opacity = S.profile.ui.opacity or S.ui.opacity
    end
end

local function note(kind, message)
    local line = { at = clock(), kind = kind or 'info', text = tostring(message or '') }
    table.insert(S.notes, line)
    while #S.notes > 40 do table.remove(S.notes, 1) end
    if kind == 'error' then
        S.last_error = line.text
    end
    if S.ctx and S.ctx.notify and (kind == 'error' or kind == 'action') then
        pcall(S.ctx.notify, line.text)
    end
end

local function character_info()
    local index = S.game.player_index()
    if not index or index < 0 then return nil end
    local name = tonumber(S.game.entity(index, 'Name')) or S.game.entity(index, 'Name')
    if type(name) ~= 'string' or name == '' then return nil end
    return name, tonumber(S.game.entity(index, 'ServerId')) or 0
end

local function zone_info()
    local zone = math.floor(tonumber(S.game.party_member(0, 'Zone')) or 0)
    local name = ''
    if zone > 0 then
        local ok, record = pcall(S.res.zone, zone)
        if ok and record then
            name = record.name_utf8 or record.name or ''
            if type(name) == 'table' then name = name.en or name[1] or '' end
        end
    end
    return zone, text(name, 40)
end

-- The zone the player is in, without building the res.zone record zone_info does.
function B.zone()
    return math.floor(tonumber(S.game.party_member(0, 'Zone')) or 0)
end

-------------------------------------------------------------------------------- zone maps

--[[ The Battle HUD's background is the game's own zone map: the map DAT the in-game map screen
(the Minimap plugin draws the same file) decoded by xi.res.map_rgba and uploaded as a texture.
`xi.mapdata` (generated by tools/gen_map_data.py) holds one row per zone:

    [100] = { dat = 5313, scale = 0.1, ox = 155.94, oy = 123.797 }

`scale`, `ox` and `oy` place the map: a world position is the normalized texel

    u = (ox + scale * x) / 256        v = (oy - scale * y) / 256

(the client's X/Y are the ground plane and its +Y is map-north, so v grows downward on screen).
Only the zone's first floor is listed, so a dungeon with several maps shows its lowest floor
until a floor table exists.  The texture is freed when the zone changes: one map is 1 MiB (or
4 MiB for an HD 1024 map pack), and a session visits many zones. ]]

do
    local MAPDATA = nil
    local map_current = nil

    local function map_table()
        if MAPDATA == nil then
            local ok, data = pcall(require, 'xi.mapdata')
            MAPDATA = ok and type(data) == 'table' and data or false
        end
        return MAPDATA or nil
    end

    local function forget()
        if map_current and map_current.texture and xi.ui and xi.ui.texture_free then
            pcall(xi.ui.texture_free, map_current.texture)
        end
        map_current = nil
    end

    function B.map_place(zone, x, y)
        local table_ = map_table()
        local entry = table_ and table_[math.floor(tonumber(zone) or 0)]
        if not entry or not entry.scale or not x or not y then return nil end
        return (entry.ox + entry.scale * x) / 256, (entry.oy - entry.scale * y) / 256
    end

    -- The current zone's map as a texture: { texture, w, h, scale, ox, oy, zone }, or nil when the
    -- zone has no map, the game has no such DAT, or the overlay cannot make textures (the addon
    -- harness).  Callers fall back to the drawn camp radar.
    function B.zone_map(zone)
        zone = math.floor(tonumber(zone) or 0)
        if zone <= 0 then return nil end
        if map_current and map_current.zone == zone then return map_current end
        forget()
        local table_ = map_table()
        local entry = table_ and table_[zone]
        if not entry or not xi.res or not xi.res.map_rgba or not xi.ui or not xi.ui.texture_memory then
            return nil
        end
        local ok, rgba, w, h = pcall(xi.res.map_rgba, entry.dat)
        if not ok or type(rgba) ~= 'string' or not w or not h or w <= 0 or h <= 0 then return nil end
        local tok, texture = pcall(xi.ui.texture_memory, rgba, w, h)
        if not tok or type(texture) ~= 'number' or texture == 0 then return nil end
        map_current = { zone = zone, texture = texture, w = w, h = h,
            scale = entry.scale, ox = entry.ox, oy = entry.oy }
        return map_current
    end

    function B.forget_map()
        forget()
    end

    -- The hub's public surface (M) carries the map helpers the tests and other modules use.
    M.map_place = B.map_place
    M.zone_map = B.zone_map
end

-------------------------------------------------------------------------------- profile schema

local function row_id()
    S.profile_seq = (S.profile_seq or 0) + 1
    return S.profile_seq
end

local function row(value)
    return { id = row_id(), spell = text(value and value.spell, 40) }
end

function C.default_profile(name, zone, zone_name)
    return {
        version = VERSION,
        name = text(name, 80),
        zone = math.floor(tonumber(zone) or 0),
        zone_name = text(zone_name, 40),
        updated = 0,
        roster = { tank = '', puller = '', kiter = '', support = {}, melee = {}, ranged = {} },
        camp = { set = false, x = 0, y = 0, z = 0, radius = 10, show = true,
            mobile = false, tank_enabled = true, follow_distance = 12 },
        support_camp = { set = false, x = 0, y = 0, z = 0, radius = 10, show = true },
        camp_hud = { show = true, map = true, range = 800, x = 16, y = 0, w = 380, h = 320,
            collapsed = false },
        camp_assign = {},
        combat_style = {},
        engine = { running = false },
        skillchain = {
            enabled = false, target = 0, mode = 'chain', infinite = false, goal = 0,
            steps = {
                { actor = '', ws = '', diamond = false },
                { actor = '', ws = '', diamond = false },
                { actor = '', ws = '', diamond = false },
                { actor = '', ws = '', diamond = false },
            },
            bursters = {
                { name = '', spell = '' }, { name = '', spell = '' },
            },
        },
        support = {
            geo = {
                enabled = true, indi = 'Indi-haste', geo = 'Geo-frailty',
                indi_interval = 120, geo_interval = 120, anchor = '', range = 20,
            },
            abilities = {},
            brd = {
                enabled = true,
                song_groups = {
                    { name = 'Melee', songs = { 'Victory March', 'Valor Minuet V', 'Blade Madrigal' } },
                    { name = 'Support', songs = { 'Mages Ballad III', 'Advancing March' } },
                },
                tank_group = 'Melee', support_group = 'Support', mobile_group = 'Melee',
                pianissimo_target = '', pianissimo_song = '',
                nitro = 'both',
            },
        },
        engage = {
            mode = 'puller', player = '', wait_claim = true, camp_only = true,
            max_distance = 30, switch_at = 50, weapon_skill = '',
        },
        formation = { enabled = true, style = 'tank', arc = 180, spacing = 2.4, side = 'auto', follow_tank = true },
        pull = {
            enabled = false, method = 'ranged', spell = '', ability = '', max_mobs = 3,
            at_hp = 50, leash = 28, find_distance = 40, mobs = {},
            sleep_spell = '', bind_spell = '', sleep_extras = true,
        },
        heal = {
            enabled = true, observe = 'party', emergency = 25, mp_reserve = 15,
            waltz = true, waltz_status = true, waltz_below = 75, waltz_tp_reserve = 0,
            cures = {
                { id = row_id(), spell = 'Cure', below = 80 },
                { id = row_id(), spell = 'Cure II', below = 60 },
                { id = row_id(), spell = 'Cure III', below = 40 },
                { id = row_id(), spell = 'Cure IV', below = 25 },
            },
            status = true, erase = true, raise_spell = '', avoid = '', exclude = {},
        },
        buffs = { enabled = true, rows = {} },
        enfeebles = { enabled = true, rows = {}, max_tries = 3 },
        dispel = { enabled = false, spell = 'Dispel', interval = 45 },
        death = { mode = 'raise', wait = 30, home_point = 1 },
        kiting = { enabled = false, mode = 'circle', radius = 18, below = 60 },
        loot = { mode = 'free' },
        priority = { 'heal', 'buff', 'enfeeble', 'dispel' },
        paused = { melee = false, ranged = false, tank = false, support = false },
        ui = { x = 360, y = 80, opacity = 0.95, show = false },
    }
end

local function sanitize_row(raw, fields)
    local out = {}
    out.ability = type(raw) == 'table' and raw.ability == true or false
    out.exclude = {}
    if type(raw) == 'table' and type(raw.exclude) == 'table' then
        for _, name in ipairs(raw.exclude) do
            name = text(name, 32)
            if name ~= '' and #out.exclude < 12 then
                local found = false
                for _, old in ipairs(out.exclude) do if old:lower() == name:lower() then found = true break end end
                if not found then out.exclude[#out.exclude + 1] = name end
            end
        end
    end
    for _, field in ipairs(fields) do
        local value = type(raw) == 'table' and raw[field] or nil
        if field == 'spell' then
            out.spell = text(value, 40)
        elseif field == 'target' then
            out.target = (value == 'party' or value == 'alliance') and value or 'self'
        elseif field == 'below' or field == 'interval' then
            out[field] = whole(value, 1, field == 'below' and 100 or 3600, field == 'below' and 50 or 120)
        end
    end
    out.id = row_id()
    return out
end

local function sanitize_list(source, fields, fallback)
    local out = {}
    if type(source) == 'table' then
        for _, raw in ipairs(source) do
            if #out >= MAX_ROWS then break end
            local row = sanitize_row(raw, fields)
            if row.spell and row.spell ~= '' then out[#out + 1] = row end
        end
    end
    if #out == 0 and fallback and type(source) ~= 'table' then
        for _, raw in ipairs(fallback) do out[#out + 1] = sanitize_row(raw, fields) end
    end
    return out
end

function C.sanitize(raw)
    local defaults = C.default_profile()
    raw = type(raw) == 'table' and raw or {}
    local profile = C.default_profile(text(raw.name, 80), raw.zone, raw.zone_name)
    profile.updated = math.floor(tonumber(raw.updated) or 0)
    profile.zone = math.floor(clamp(raw.zone, 0, 10000, defaults.zone))
    profile.zone_name = text(raw.zone_name, 40)

    local roster = type(raw.roster) == 'table' and raw.roster or {}
    local used = {}
    local function single(key)
        local name = text(roster[key], 32)
        if name ~= '' and not used[name] then
            profile.roster[key] = name
            used[name] = true
        end
    end
    single('tank'); single('puller'); single('kiter')
    for _, key in ipairs({ 'support', 'melee', 'ranged' }) do
        local list = {}
        if type(roster[key]) == 'table' then
            for _, value in ipairs(roster[key]) do
                local name = text(value, 32)
                if name ~= '' and #list < 18 and not contains(list, name) and not used[name] then
                    list[#list + 1] = name
                    used[name] = true
                end
            end
        end
        profile.roster[key] = list
    end

    local camp = type(raw.camp) == 'table' and raw.camp or {}
    profile.camp.set = truth(camp.set, false)
    profile.camp.x = clamp(camp.x, -100000, 100000, 0)
    profile.camp.y = clamp(camp.y, -100000, 100000, 0)
    profile.camp.z = clamp(camp.z, -100000, 100000, 0)
    profile.camp.radius = clamp(camp.radius, 1, 50, 10)
    profile.camp.show = truth(camp.show, true)
    profile.camp.mobile = truth(camp.mobile, false)
    profile.camp.tank_enabled = truth(camp.tank_enabled, true)
    profile.camp.follow_distance = clamp(camp.follow_distance, 5, 30, 12)

    local support_camp = type(raw.support_camp) == 'table' and raw.support_camp or {}
    profile.support_camp.set = truth(support_camp.set, false)
    profile.support_camp.x = clamp(support_camp.x, -100000, 100000, 0)
    profile.support_camp.y = clamp(support_camp.y, -100000, 100000, 0)
    profile.support_camp.z = clamp(support_camp.z, -100000, 100000, 0)
    profile.support_camp.radius = clamp(support_camp.radius, 1, 50, 10)
    profile.support_camp.show = truth(support_camp.show, true)

    local camp_hud = type(raw.camp_hud) == 'table' and raw.camp_hud or {}
    profile.camp_hud.show = truth(camp_hud.show, true)
    profile.camp_hud.map = truth(camp_hud.map, true)
    -- `range` is the map's width across the HUD panel, in yalms.  Older profiles stored a
    -- whole zone / 2x / 4x `zoom`; keep those views roughly.
    local range = tonumber(camp_hud.range)
    if not range then
        local zoom = tonumber(camp_hud.zoom)
        if zoom == 4 then range = 600
        elseif zoom == 2 then range = 1200
        elseif zoom == 1 then range = 2400 end
    end
    profile.camp_hud.range = clamp(range, 150, 4000, 800)
    profile.camp_hud.x = clamp(camp_hud.x, -4000, 8000, 16)
    profile.camp_hud.y = clamp(camp_hud.y, -4000, 8000, 0)
    profile.camp_hud.w = clamp(camp_hud.w, 180, 500, 300)
    profile.camp_hud.h = clamp(camp_hud.h, 180, 600, 290)
    profile.camp_hud.collapsed = truth(camp_hud.collapsed, false)
    profile.camp_assign = {}
    if type(raw.camp_assign) == 'table' then
        for name, kind in pairs(raw.camp_assign) do
            name = text(name, 32)
            if name ~= '' and (kind == 'tank' or kind == 'support') and #profile.camp_assign < 32 then
                profile.camp_assign[name] = kind
            end
        end
    end
    profile.combat_style = {}
    if type(raw.combat_style) == 'table' then
        for name, mode in pairs(raw.combat_style) do
            name = text(name, 32)
            if name ~= '' and (mode == 'melee' or mode == 'ranged') and #profile.combat_style < 32 then
                profile.combat_style[name] = mode
            end
        end
    end

    local skillchain = type(raw.skillchain) == 'table' and raw.skillchain or {}
    local engine = type(raw.engine) == 'table' and raw.engine or {}
    profile.engine.running = truth(engine.running, false)

    profile.skillchain.enabled = truth(skillchain.enabled, false)
    profile.skillchain.target = whole(skillchain.target, 0, 16, 0)
    profile.skillchain.mode = skillchain.mode == 'spam' and 'spam' or 'chain'
    profile.skillchain.infinite = truth(skillchain.infinite, false)
    profile.skillchain.goal = whole(skillchain.goal, 0, SC_MAX_STEPS - 1, 0)
    profile.skillchain.steps = {}
    local raw_steps = type(skillchain.steps) == 'table' and skillchain.steps or {}
    for index = 1, math.min(#raw_steps, SC_MAX_STEPS) do
        local row = type(raw_steps[index]) == 'table' and raw_steps[index] or {}
        profile.skillchain.steps[index] = {
            actor = text(row.actor, 32),
            ws = text(row.ws, 40),
            diamond = truth(row.diamond, false),
        }
    end
    while #profile.skillchain.steps < 2 do
        profile.skillchain.steps[#profile.skillchain.steps + 1] = { actor = '', ws = '', diamond = false }
    end
    profile.skillchain.bursters = {}
    if type(skillchain.bursters) == 'table' then
        for index = 1, SC_MAX_BURSTERS do
            local row = type(skillchain.bursters[index]) == 'table' and skillchain.bursters[index] or {}
            profile.skillchain.bursters[index] = { name = text(row.name, 32), spell = text(row.spell, 40) }
        end
    else
        for index = 1, SC_MAX_BURSTERS do
            profile.skillchain.bursters[index] = { name = '', spell = '' }
        end
    end

    local support = type(raw.support) == 'table' and raw.support or {}
    local geo = type(support.geo) == 'table' and support.geo or {}
    profile.support.geo.enabled = truth(geo.enabled, true)
    profile.support.geo.indi = text(geo.indi, 40)
    if profile.support.geo.indi == '' then profile.support.geo.indi = 'Indi-haste' end
    profile.support.geo.geo = text(geo.geo, 40)
    if profile.support.geo.geo == '' then profile.support.geo.geo = 'Geo-frailty' end
    profile.support.geo.indi_interval = whole(geo.indi_interval, 30, 600, 120)
    profile.support.geo.geo_interval = whole(geo.geo_interval, 30, 600, 120)
    profile.support.geo.anchor = text(geo.anchor, 32)
    profile.support.geo.range = clamp(geo.range, 5, 40, 20)
    local brd = type(support.brd) == 'table' and support.brd or {}
    profile.support.brd.enabled = truth(brd.enabled, true)
    profile.support.brd.song_groups = {}
    if type(brd.song_groups) == 'table' then
        for _, raw in ipairs(brd.song_groups) do
            if #profile.support.brd.song_groups >= 12 then break end
            local name = text(type(raw) == 'table' and raw.name or '', 32)
            if name ~= '' then
                local songs, seen = {}, {}
                for _, song in ipairs(type(raw) == 'table' and raw.songs or {}) do
                    song = text(song, 40)
                    if song ~= '' and not seen[song:lower()] then
                        seen[song:lower()] = true
                        songs[#songs + 1] = song
                    end
                    if #songs >= 12 then break end
                end
                profile.support.brd.song_groups[#profile.support.brd.song_groups + 1] = {
                    name = name, songs = songs,
                }
            end
        end
    end
    if #profile.support.brd.song_groups == 0 then
        profile.support.brd.song_groups = {
            { name = 'Melee', songs = { 'Victory March', 'Valor Minuet V', 'Blade Madrigal' } },
            { name = 'Support', songs = { 'Mages Ballad III', 'Advancing March' } },
        }
    end
    local group_names = {}
    for _, group in ipairs(profile.support.brd.song_groups) do group_names[group.name] = true end
    local function group_or(value, fallback)
        value = text(value, 32)
        if group_names[value] then return value end
        if group_names[fallback] then return fallback end
        return profile.support.brd.song_groups[1].name
    end
    profile.support.brd.tank_group = group_or(brd.tank_group, 'Melee')
    profile.support.brd.support_group = group_or(brd.support_group, 'Support')
    profile.support.brd.mobile_group = group_or(brd.mobile_group, profile.support.brd.tank_group)
    profile.support.brd.pianissimo_target = text(brd.pianissimo_target, 32)
    profile.support.brd.pianissimo_song = text(brd.pianissimo_song, 40)
    if brd.nitro ~= 'tank' and brd.nitro ~= 'support' and brd.nitro ~= 'off' then brd.nitro = 'both' end
    profile.support.brd.nitro = brd.nitro
    profile.support.abilities = {}
    if type(support.abilities) == 'table' then
        for _, raw in ipairs(support.abilities) do
            if #profile.support.abilities >= 16 then break end
            local name = text(type(raw) == 'table' and raw.name or raw, 40)
            if name ~= '' then
                profile.support.abilities[#profile.support.abilities + 1] = {
                    name = name,
                    enabled = truth(type(raw) == 'table' and raw.enabled, true),
                    interval = whole(type(raw) == 'table' and raw.interval, 30, 600, 300),
                }
            end
        end
    end

    local engage = type(raw.engage) == 'table' and raw.engage or {}
    if not contains(ENGAGE_MODES, engage.mode) then engage.mode = 'puller' end
    profile.engage.mode = engage.mode
    profile.engage.player = text(engage.player, 32)
    profile.engage.wait_claim = truth(engage.wait_claim, true)
    profile.engage.camp_only = truth(engage.camp_only, true)
    profile.engage.max_distance = clamp(engage.max_distance, 5, 100, 30)
    profile.engage.switch_at = whole(engage.switch_at, 1, 100, 50)
    profile.engage.weapon_skill = text(engage.weapon_skill, 40)

    local formation = type(raw.formation) == 'table' and raw.formation or {}
    profile.formation.enabled = truth(formation.enabled, true)
    if formation.style ~= 'behind' and formation.style ~= 'side' then formation.style = 'tank' end
    profile.formation.style = formation.style
    profile.formation.arc = clamp(formation.arc, 40, 300, 180)
    profile.formation.spacing = clamp(formation.spacing, 1.4, 6, 2.4)
    if formation.side ~= 'left' and formation.side ~= 'right' then formation.side = 'auto' end
    profile.formation.side = formation.side
    profile.formation.follow_tank = truth(formation.follow_tank, true)

    local pull = type(raw.pull) == 'table' and raw.pull or {}
    profile.pull.enabled = truth(pull.enabled, false)
    if not contains(PULL_METHODS, pull.method) then pull.method = 'ranged' end
    profile.pull.method = pull.method
    profile.pull.spell = text(pull.spell, 40)
    profile.pull.ability = text(pull.ability, 40)
    profile.pull.max_mobs = whole(pull.max_mobs, 1, 12, 3)
    profile.pull.at_hp = whole(pull.at_hp, 1, 100, 50)
    profile.pull.leash = clamp(pull.leash, 5, 100, 28)
    profile.pull.find_distance = whole(pull.find_distance, 5, 100, 40)
    profile.pull.mobs = {}
    if type(pull.mobs) == 'table' then
        local seen = {}
        for _, raw in ipairs(pull.mobs) do
            local name = text(raw, 40)
            local key = name:lower()
            if name ~= '' and not seen[key] and #profile.pull.mobs < 40 then
                seen[key] = true
                profile.pull.mobs[#profile.pull.mobs + 1] = name
            end
        end
    end
    profile.pull.sleep_spell = text(pull.sleep_spell, 40)
    profile.pull.bind_spell = text(pull.bind_spell, 40)
    profile.pull.sleep_extras = truth(pull.sleep_extras, true)

    local heal = type(raw.heal) == 'table' and raw.heal or {}
    profile.heal.enabled = truth(heal.enabled, true)
    profile.heal.observe = heal.observe == 'alliance' and 'alliance' or 'party'
    profile.heal.emergency = whole(heal.emergency, 1, 100, 25)
    profile.heal.mp_reserve = whole(heal.mp_reserve, 0, 100, 15)
    profile.heal.waltz = truth(heal.waltz, true)
    profile.heal.waltz_status = truth(heal.waltz_status, true)
    profile.heal.waltz_below = whole(heal.waltz_below, 1, 100, 75)
    profile.heal.waltz_tp_reserve = whole(heal.waltz_tp_reserve, 0, 3000, 0)
    profile.heal.cures = sanitize_list(heal.cures,
        { 'spell', 'below' }, defaults.heal.cures)
    profile.heal.status = truth(heal.status, true)
    profile.heal.erase = truth(heal.erase, true)
    profile.heal.raise_spell = text(heal.raise_spell, 40)
    profile.heal.avoid = text(heal.avoid, 160)
    profile.heal.exclude = {}
    if type(heal.exclude) == 'table' then
        for _, raw in ipairs(heal.exclude) do
            local name = text(raw, 32)
            if name ~= '' and #profile.heal.exclude < 12 then
                local found = false
                for _, old in ipairs(profile.heal.exclude) do
                    if old:lower() == name:lower() then found = true break end
                end
                if not found then profile.heal.exclude[#profile.heal.exclude + 1] = name end
            end
        end
    end

    local buffs = type(raw.buffs) == 'table' and raw.buffs or {}
    profile.buffs.enabled = truth(buffs.enabled, true)
    profile.buffs.rows = sanitize_list(buffs.rows, { 'spell', 'target', 'interval' })

    local enfeebles = type(raw.enfeebles) == 'table' and raw.enfeebles or {}
    profile.enfeebles.enabled = truth(enfeebles.enabled, true)
    profile.enfeebles.rows = sanitize_list(enfeebles.rows, { 'spell', 'interval' })
    profile.enfeebles.max_tries = whole(enfeebles.max_tries, 1, 10, 3)

    local dispel = type(raw.dispel) == 'table' and raw.dispel or {}
    profile.dispel.enabled = truth(dispel.enabled, false)
    profile.dispel.spell = text(dispel.spell, 40)
    profile.dispel.interval = whole(dispel.interval, 1, 3600, 45)

    local death = type(raw.death) == 'table' and raw.death or {}
    profile.death.mode = death.mode == 'homepoint' and 'homepoint' or 'raise'
    profile.death.wait = whole(death.wait, 0, 600, 30)
    profile.death.home_point = whole(death.home_point, 1, 128, 1)

    local kiting = type(raw.kiting) == 'table' and raw.kiting or {}
    profile.kiting.enabled = truth(kiting.enabled, false)
    if not contains(KITE_MODES, kiting.mode) then kiting.mode = 'circle' end
    profile.kiting.mode = kiting.mode
    profile.kiting.radius = clamp(kiting.radius, 5, 60, 18)
    profile.kiting.below = whole(kiting.below, 0, 100, 60)

    local loot = type(raw.loot) == 'table' and raw.loot or {}
    profile.loot.mode = contains(LOOT_MODES, loot.mode) and loot.mode or 'free'

    local priority = {}
    if type(raw.priority) == 'table' then
        for _, item in ipairs(raw.priority) do
            if contains(PRIORITIES, item) and not contains(priority, item) then
                priority[#priority + 1] = item
            end
        end
    end
    for _, item in ipairs(PRIORITIES) do
        if not contains(priority, item) then priority[#priority + 1] = item end
    end
    profile.priority = priority

    local paused = type(raw.paused) == 'table' and raw.paused or {}
    for _, key in ipairs({ 'melee', 'ranged', 'tank', 'support' }) do
        profile.paused[key] = truth(paused[key], false)
    end

    local ui = type(raw.ui) == 'table' and raw.ui or {}
    profile.ui.x = whole(ui.x, -4000, 8000, 360)
    profile.ui.y = whole(ui.y, -4000, 8000, 80)
    profile.ui.opacity = clamp(ui.opacity, 0.45, 1, 0.95)
    profile.ui.show = truth(ui.show, false)
    return profile
end

function C.copy(profile)
    return copy(profile)
end

function C.default_name()
    local _, zone_name = zone_info()
    if zone_name == '' then zone_name = 'Battle' end
    return string.format('%s %s', zone_name, os.date('%Y-%m-%d %H:%M:%S'))
end

-------------------------------------------------------------------------------- persistence

function C.root()
    if S.root then return S.root end
    local data = xi.paths and xi.paths.data or ''
    S.root = join_path(data, 'battle')
    return S.root
end

function C.folder()
    local name = S.character or (character_info() or 'character')
    return join_path(C.root(), slug(name))
end

function C.folder_for(name)
    return join_path(C.root(), slug(name))
end

function C.refresh_character()
    local name = character_info()
    if not name then return false end
    if S.character ~= name then
        S.character = name
        S.profiles = {}
    end
    return true
end

function C.profile_path(name)
    return join_path(C.folder(), slug(name) .. '.json')
end

function C.list()
    C.refresh_character()
    local folder = C.folder()
    local out = {}
    local names = xi.fs and xi.fs.list and xi.fs.list(folder, false) or {}
    for _, file in ipairs(names or {}) do
        if type(file) == 'string' and file:sub(-5) == '.json' then
            local data = decode(read_file(join_path(folder, file)))
            if data and type(data.name) == 'string' and data.name ~= '' then
                out[#out + 1] = {
                    file = file, name = data.name,
                    zone = math.floor(tonumber(data.zone) or 0),
                    zone_name = text(data.zone_name, 40),
                    updated = math.floor(tonumber(data.updated) or 0),
                }
            end
        end
    end
    table.sort(out, function(a, b) return (a.updated or 0) > (b.updated or 0) end)
    S.profiles = out
    return out
end

function C.load(name)
    C.refresh_character()
    local wanted = text(name, 80)
    if wanted == '' then return nil, 'profile name?' end
    local list = C.list()
    local entry = nil
    for _, item in ipairs(list) do
        if item.name == wanted then entry = item break end
    end
    if not entry then return nil, 'no battle profile called ' .. wanted end
    local raw = decode(read_file(join_path(C.folder(), entry.file)))
    if not raw then return nil, 'that battle profile could not be read' end
    S.profile = C.sanitize(raw)
    S.file = join_path(C.folder(), entry.file)
    S.camp_hud_restore = S.profile.camp_hud.collapsed == true
    S.buffers = {}
    S.profile_seq = S.profile_seq + 1
    S.ui.x, S.ui.y = S.profile.ui.x, S.profile.ui.y
    S.ui.opacity = S.profile.ui.opacity
    S.dirty = false
    note('info', 'Loaded battle profile "' .. S.profile.name .. '".')
    return S.profile
end

function C.shared_tab()
    return S.tab == 'roster' or S.tab == 'camp' or S.tab == 'rules'
end

function C.save(name)
    C.refresh_character()
    if S.remote_edit then
        local ok, err = B.team_save_profile(S.remote_edit.name, C.shared_tab())
        if not ok then return nil, err end
        B.team_restore()
        return S.profile
    end
    if not S.profile then return nil, 'there is no battle profile to save' end
    local wanted = text(name, 80)
    if wanted ~= '' then S.profile.name = wanted end
    if S.profile.name == '' then S.profile.name = C.default_name() end
    local zone, zone_name = zone_info()
    S.profile.zone, S.profile.zone_name = zone, zone_name
    S.profile.updated = math.floor(os.time())
    S.profile.engine.running = S.running
    S.profile.ui.x, S.profile.ui.y = S.ui.x, S.ui.y
    S.profile.ui.opacity = S.ui.opacity
    -- Saving is the "done" action: the next login starts with the hub closed.  //battle show is
    -- one command away if the player wants it up.
    S.profile.ui.show = false

    local path = C.profile_path(S.profile.name)
    local data = encode(S.profile)
    if not data then return nil, 'could not encode the battle profile' end
    if not write_file(path, data) then return nil, 'could not write ' .. path end
    local previous = S.file
    S.file = path
    if previous and previous ~= path then pcall(os.remove, previous) end
    S.last_save = clock()
    C.list()
    note('info', 'Saved battle profile "' .. S.profile.name .. '".')
    if S.team and #S.team > 0 then
        local ok, err = B.team_save_profile(nil, C.shared_tab())
        if not ok then note('error', 'Battle: server rules not saved: ' .. tostring(err)) end
    end
    return S.profile
end

function C.delete(name)
    C.refresh_character()
    local wanted = text(name, 80)
    if wanted == '' then return false, 'profile name?' end
    for _, item in ipairs(C.list()) do
        if item.name == wanted then
            local path = join_path(C.folder(), item.file)
            pcall(os.remove, path)
            if S.file == path then
                S.file = nil
                if S.profile and S.profile.name == wanted then S.profile.name = '' end
            end
            C.list()
            note('info', 'Deleted battle profile "' .. wanted .. '".')
            return true
        end
    end
    return false, 'no battle profile called ' .. wanted
end

function C.new_profile(name)
    local zone, zone_name = zone_info()
    local wanted = text(name, 80)
    if wanted == '' then wanted = C.default_name() end
    S.profile = C.default_profile(wanted, zone, zone_name)
    S.file = nil
    S.buffers = {}
    S.profile_seq = S.profile_seq + 1
    S.ui.x, S.ui.y = S.profile.ui.x, S.profile.ui.y
    S.ui.opacity = S.profile.ui.opacity
    S.dirty = false
    note('info', 'New battle profile "' .. wanted .. '".')
    return S.profile
end

-- Load the profile this character used last, or start an unsaved one.  A client restart must not
-- start fighting on its own: `running` stays false until //battle start.
function C.resume()
    C.refresh_character()
    local list = C.list()
    if #list > 0 then
        local ok = select(1, C.load(list[1].name))
        if ok then return end
    end
    C.new_profile(nil)
end

-------------------------------------------------------------------------------- the role and party view

local function active_member(slot)
    local active = tonumber(S.game.party_member(slot, 'IsActive')) or 0
    if active == 0 then return nil end
    local name = S.game.party_member(slot, 'Name')
    if type(name) ~= 'string' or name == '' then return nil end
    return {
        slot = slot,
        name = name,
        id = tonumber(S.game.party_member(slot, 'ServerId')) or 0,
        hp = tonumber(S.game.party_member(slot, 'HP')) or 0,
        hpp = tonumber(S.game.party_member(slot, 'HPPercent')) or 0,
        mp = tonumber(S.game.party_member(slot, 'MP')) or 0,
        mpp = tonumber(S.game.party_member(slot, 'MPPercent')) or 0,
        tp = tonumber(S.game.party_member(slot, 'TP')) or 0,
        job = tonumber(S.game.party_member(slot, 'MainJob')) or 0,
        level = tonumber(S.game.party_member(slot, 'MainJobLevel')) or 0,
        sub = tonumber(S.game.party_member(slot, 'SubJob')) or 0,
        sub_level = tonumber(S.game.party_member(slot, 'SubJobLevel')) or 0,
        zone = tonumber(S.game.party_member(slot, 'Zone')) or 0,
    }
end

function B.members(observe)
    local out, has_self = {}, false
    local last = observe == 'alliance' and 17 or 5
    for slot = 0, last do
        local member = active_member(slot)
        if member then
            if slot == 0 then has_self = true end
            out[#out + 1] = member
        end
    end
    -- A solo client's party table can have no active slot 0; the player is still a party of one.
    if not has_self then
        local me = B.self()
        if me then table.insert(out, 1, me) end
    end
    return out
end

-- The roster is shared across the account, so it keeps a role for a character that is not in
-- the live party.  The party is the authority for what the hub counts, draws and moves:
-- assignments for absent characters stay saved for the next time they group, but they are not
-- part of the active roster.  That is what lets the same profile run a three-box party today and
-- all six after the others log in.  These helpers are table fields (not chunk locals) because
-- the file already sits at LuaJIT's 200-local limit.
function B.party_set(scope)
    local set = {}
    for _, member in ipairs(B.members(scope or 'alliance')) do
        local name = type(member.name) == 'string' and member.name or ''
        if name ~= '' then set[name:lower()] = member end
    end
    return set
end

function B.in_party(name)
    name = text(name or '', 32)
    if name == '' then return false end
    if B.party_set('alliance')[name:lower()] then return true end
    local me = B.self()
    return me ~= nil and tostring(me.name or ''):lower() == name:lower()
end

-- A role's names that are in the live party/alliance, in roster order.
function B.roster_online(role)
    local out = {}
    if not S.profile or not role then return out end
    local roster = S.profile.roster
    local set = B.party_set('alliance')
    if role == 'support' or role == 'melee' or role == 'ranged' then
        for _, name in ipairs(roster[role] or {}) do
            if set[name:lower()] then out[#out + 1] = name end
        end
    else
        local name = roster[role]
        if type(name) == 'string' and name ~= '' and set[name:lower()] then
            out[1] = name
        end
    end
    return out
end

function B.active_role_name(role)
    return B.roster_online(role)[1] or ''
end

-- The server team list carries live flags.  Older servers (or a server whose game gateway is
-- off) do not know who is online; the hub then keeps the old "show the whole team" behaviour.
function B.team_online(name)
    name = text(name or '', 32)
    if name == '' then return false end
    if not S.team_online_known then return true end
    for _, character in ipairs(S.team or {}) do
        if tostring(character.name or ''):lower() == name:lower() then
            return character.online == true
        end
    end
    return false
end

function B.member(slot)
    return active_member(slot)
end

function B.self()
    local member = active_member(0)
    if member then return member end
    local name, id = character_info()
    if not name then return nil end
    local index = S.game.player_index() or -1
    local hpp = index >= 0 and (tonumber(S.game.entity(index, 'HPPercent')) or 0) or 0
    local mpp = tonumber(S.game.party_member(0, 'MPPercent')) or 0
    local hp_max = tonumber(S.game.player('HPMax')) or 0
    local mp_max = tonumber(S.game.player('MPMax')) or 0
    local mp = tonumber(S.game.party_member(0, 'MP')) or 0
    if mpp <= 0 and mp_max > 0 and mp > 0 then mpp = math.floor(mp * 100 / mp_max + 0.5) end
    if mpp <= 0 then mpp = 100 end
    local hp = tonumber(S.game.party_member(0, 'HP')) or 0
    if hp <= 0 and hp_max > 0 and hpp > 0 then hp = math.floor(hp_max * hpp / 100 + 0.5) end
    if mp <= 0 and mp_max > 0 and mpp > 0 then mp = math.floor(mp_max * mpp / 100 + 0.5) end
    return { slot = 0, name = name, id = id or 0, hp = hp, hpp = hpp, mp = mp, mpp = mpp,
        tp = tonumber(S.game.party_member(0, 'TP')) or 0,
        job = tonumber(S.game.party_member(0, 'MainJob')) or 0,
        level = tonumber(S.game.party_member(0, 'MainJobLevel')) or 0,
        sub = tonumber(S.game.party_member(0, 'SubJob')) or 0,
        sub_level = tonumber(S.game.party_member(0, 'SubJobLevel')) or 0,
        zone = tonumber(S.game.party_member(0, 'Zone')) or 0 }
end

function B.role_of(name)
    if not S.profile or not name then return nil end
    local roster = S.profile.roster
    if roster.tank == name then return 'tank' end
    if roster.puller == name and not contains(roster.support, name) then return 'puller' end
    if roster.kiter == name then return 'kiter' end
    for _, key in ipairs({ 'support', 'melee', 'ranged' }) do
        if contains(roster[key], name) then return key end
    end
    return nil
end

function B.self_role()
    local me = B.self()
    return me and B.role_of(me.name) or nil
end

function B.has_diamond_aspis()
    local ok, _, index = pcall(S.game.equipment, 1)
    index = ok and tonumber(index) or 0
    if index <= 0 then return false end
    local bag, slot = math.floor(index / 256), index % 256
    local id = tonumber(S.game.item(bag, slot, 'Id')) or 0
    return id == SC_DIAMOND_ASPIS
end

local function weapon_skill_props(name)
    name = text(name, 40)
    if name == '' then return nil, false end
    local ok, ability = pcall(S.res.ability_by_name, name)
    if not ok or type(ability) ~= 'table' then return nil, false end
    local id = tonumber(ability.id) or 0
    local props = SC_WS_PROPS[id]
    if not props then return { 0, 0, 0 }, true end
    return { tonumber(props[1]) or 0, tonumber(props[2]) or 0, tonumber(props[3]) or 0 }, true
end

local function form_chain(closing, resonance)
    if not closing or not resonance then return 0 end
    for _, cl in ipairs(closing) do
        cl = tonumber(cl) or 0
        if cl > 0 and SC_TRANS[cl] then
            for _, res in ipairs(resonance) do
                res = tonumber(res) or 0
                local formed = res > 0 and SC_TRANS[cl][res] or nil
                if formed then return formed end
            end
        end
    end
    return 0
end

function B.skillchain_plan()
    local cfg = S.profile and S.profile.skillchain
    if not cfg then return { rows = {}, bursters = {}, valid = false } end
    local source = {}
    for index, step in ipairs(cfg.steps) do
        if index == 1 or step.actor ~= '' or step.ws ~= '' then
            source[#source + 1] = step
        end
    end
    local goal = tonumber(cfg.goal) or 0
    local looping = cfg.infinite == true
    -- The planner shows the configured cycle once; the loop marker and the goal are the
    -- instruction to repeat it.  Expanding it automatically would pretend the chain still
    -- forms after the opener resets.
    local spam = cfg.mode == 'spam'
    local rows, state, count = {}, nil, 0
    -- The window the next close has to land in.  A level-1 link keeps the full
    -- SC_OPEN_SECONDS (the Savage Blade / Hot Shot loop); wider links lose a second.
    local window = SC_OPEN_SECONDS
    local self = B.self()
    local me = self and self.name or ''
    for index, step in ipairs(source) do
        local actor = text(step.actor, 32)
        local ws = text(step.ws, 40)
        local props, known = weapon_skill_props(ws)
        local self_shield = actor ~= '' and me ~= '' and actor:lower() == me:lower() and B.has_diamond_aspis()
        local diamond = step.diamond == true or self_shield
        local row = {
            index = index, actor = actor, ws = ws, known = known, props = props,
            diamond = diamond, self_shield = self_shield,
            kind = index == 1 and 'open' or 'close', sc = 0, count = 0,
            window = SC_OPEN_SECONDS, valid = known and props ~= nil and (props[1] + props[2] + props[3] > 0),
            spam = spam,
        }
        if spam then
            row.window = 0
            if index > 1 and (actor == '' or ws == '') then row.optional = true; row.valid = false end
        elseif index > 1 and (actor == '' or ws == '') then
            row.optional = true
            row.valid = false
        elseif index == 1 then
            if known and props then
                state = { props = props, sc = 0, tier = 0 }
                window = SC_OPEN_SECONDS
                row.valid = true
            end
        elseif state and props then
            local resonance = state.sc > 0 and { state.sc } or state.props
            local formed = form_chain(props, resonance)
            if formed > 0 then
                count = math.min(5, count + 1)
                state = { props = props, sc = formed, tier = sc_tier(formed) }
                row.sc, row.count = formed, count
                local base = sc_tier(formed) == 1 and SC_OPEN_SECONDS
                    or math.max(0, window - 1)
                window = base
                row.window = diamond and SC_OPEN_SECONDS or base
                row.diamond_saved = diamond and math.max(0, SC_OPEN_SECONDS - base) or 0
                row.valid = true
            else
                state = { props = props, sc = 0, tier = 0 }
                window = SC_OPEN_SECONDS
                row.sc, row.window = 0, SC_OPEN_SECONDS
            end
        end
        rows[index] = row
    end
    local bursters = {}
    for _, row in ipairs(cfg.bursters) do
        local name, spell = text(row.name, 32), text(row.spell, 40)
        if name ~= '' or spell ~= '' then bursters[#bursters + 1] = { name = name, spell = spell } end
    end
    local final = 0
    for _, row in ipairs(rows) do if row.sc and row.sc > 0 then final = row.sc end end
    local target = tonumber(cfg.target) or 0
    local target_ok = spam or target == 0 or final == target
    return { rows = rows, bursters = bursters, target = target, final = final,
        target_ok = target_ok, valid = not spam and final > 0 and target_ok,
        spam = spam, infinite = cfg.infinite == true, looping = looping,
        goal = goal, self_diamond = B.has_diamond_aspis() }
end

function B.import_party()
    if not S.profile then return 0 end
    local p = S.profile
    local assigned = {}
    for _, key in ipairs({ 'tank', 'puller', 'kiter' }) do
        if p.roster[key] ~= '' then assigned[p.roster[key]:lower()] = true end
    end
    for _, key in ipairs({ 'support', 'melee', 'ranged' }) do
        for _, name in ipairs(p.roster[key]) do assigned[name:lower()] = true end
    end
    local tank_jobs = { [1] = true, [7] = true, [8] = true, [22] = true }
    local support_jobs = { [3] = true, [5] = true, [10] = true, [15] = true, [17] = true, [20] = true, [21] = true }
    local ranged_jobs = { [11] = true, [17] = true }
    local added = 0
    for _, member in ipairs(B.members('alliance')) do
        local name = member.name
        if name and name ~= '' and not assigned[name:lower()] then
            local job = tonumber(member.job) or 0
            local placed = false
            if p.roster.tank == '' and tank_jobs[job] then
                p.roster.tank = name
                placed = true
            elseif ranged_jobs[job] and #p.roster.ranged < 18 then
                p.roster.ranged[#p.roster.ranged + 1] = name
                placed = true
            elseif support_jobs[job] and #p.roster.support < 18 then
                p.roster.support[#p.roster.support + 1] = name
                placed = true
            elseif #p.roster.melee < 18 then
                p.roster.melee[#p.roster.melee + 1] = name
                placed = true
            end
            if placed then assigned[name:lower()] = true; added = added + 1 end
        end
    end
    if added > 0 then S.dirty = true end
    note('info', string.format('Battle: imported %d unassigned party member(s) from their jobs.', added))
    return added
end

function B.paused(role)
    return S.profile and S.profile.paused[role] == true
end

-------------------------------------------------------------------------------- entity helpers

-- A despawned client entity stays in the table until the slot is reused; Flags1 bit 0x1000 and
-- Flags3 bit 0x8000 are how the client marks it gone (the same test the follow controller uses).
local function entity_live(index)
    if not index or index < 0 then return false end
    local f0 = S.game.entity(index, 'Render.Flags0') or 0
    if f0 == 0 then return false end
    local f1 = S.game.entity(index, 'Render.Flags1') or 0
    local f3 = S.game.entity(index, 'Render.Flags3') or 0
    return math.floor(f1 / 0x1000) % 2 == 0 and math.floor(f3 / 0x8000) % 2 == 0
end

local function position(index)
    if not index or index < 0 then return nil end
    local x = S.game.entity(index, 'Movement.LocalPosition.X')
    local y = S.game.entity(index, 'Movement.LocalPosition.Y')
    local z = S.game.entity(index, 'Movement.LocalPosition.Z')
    if not x or not y or not z then return nil end
    -- The client's LocalPosition uses X/Y as the ground plane and Z as height.  The follow
    -- controller in control.lua steers with the same pair, so the engine and camps share it.
    return { x = x, y = y, z = z, heading = S.game.entity(index, 'Heading') or 0 }
end

local function distance2(a, b)
    if not a or not b then return math.huge end
    local dx, dy = a.x - b.x, a.y - b.y
    return dx * dx + dy * dy
end

local function distance(a, b)
    return math.sqrt(distance2(a, b))
end

local function party_ids()
    local ids = {}
    for slot = 0, 17 do
        local member = active_member(slot)
        if member and member.id > 0 then ids[member.id] = member end
    end
    return ids
end

local function claim_of(index)
    local claim = tonumber(S.game.entity(index, 'ClaimStatus')) or 0
    if claim <= 0 then return nil end
    local ids = party_ids()
    return ids[claim], claim
end

-- SpawnFlags: 0x01 PC, 0x02 NPC, 0x10 Mob (the client's own spawn flags; a claimed mob keeps the
-- mob bit).  Type 2 is the fallback for a client that has not filled SpawnFlags yet.
local function is_mob(index)
    local spawn = tonumber(S.game.entity(index, 'SpawnFlags')) or 0
    if math.floor(spawn / 0x10) % 2 == 1 then return true end
    if math.floor(spawn / 0x01) % 2 == 0 and math.floor(spawn / 0x02) % 2 == 0 then
        local claim = tonumber(S.game.entity(index, 'ClaimStatus')) or 0
        if claim > 0 then return true end
        local kind = tonumber(S.game.entity(index, 'Type')) or -1
        if kind == 2 then return true end
    end
    return false
end

local function entity_by_name(name)
    if not name or name == '' then return nil end
    local count = S.game.entity_count() or 0
    for index = 0, count - 1 do
        if entity_live(index) and S.game.entity(index, 'Name') == name then return index end
    end
    return nil
end

function B.entity_by_name(name)
    return entity_by_name(name)
end

function B.self_pos()
    local me = S.game.player_index()
    if not me or me < 0 then return nil end
    return position(me)
end

function B.target_pos()
    local index = B.self_target()
    return index and position(index) or nil
end

-------------------------------------------------------------------------------- world projection for the camp circle

do
    local ok, ffi = pcall(require, 'ffi')
    if not ok or not ffi then
        G.ready = false
        G.unavailable = 'LuaJIT ffi is not available'
    else
        local cdef = [[
            typedef struct { int32_t x, y; uint32_t w, h; float minz, maxz; } XiBattleViewport;
            typedef struct {
                void* pad[38];
                int32_t (*GetTransform)(void* self, uint32_t state, float* out);
                void* pad2[2];
                int32_t (*GetViewport)(void* self, XiBattleViewport* out);
            } XiBattleVtbl;
            typedef struct { void* lpVtbl; } XiBattleDevice;
        ]]
        local okc = pcall(ffi.cdef, cdef)
        if not okc then
            G.ready = false
            G.unavailable = 'the camera declarations were rejected'
        else
            G.ffi = ffi
            G.ready = true
            G.next_try = 0
        end
    end
end

local function mat_mul(a, b)
    local r = {}
    for i = 0, 3 do
        for j = 0, 3 do
            r[i * 4 + j] = a[i * 4] * b[j] + a[i * 4 + 1] * b[4 + j]
                + a[i * 4 + 2] * b[8 + j] + a[i * 4 + 3] * b[12 + j]
        end
    end
    return r
end

-- 0-based Gauss-Jordan inverse, matching the m[0]..m[15] tables the camera read produces.
local function mat_inverse(m)
    local a, inv = {}, {}
    for i = 0, 15 do a[i] = m[i] end
    for i = 0, 15 do inv[i] = (i % 5 == 0) and 1 or 0 end
    for col = 0, 3 do
        local pivot = col
        for row = col + 1, 3 do
            if math.abs(a[row * 4 + col]) > math.abs(a[pivot * 4 + col]) then pivot = row end
        end
        if math.abs(a[pivot * 4 + col]) < 1e-9 then return nil end
        if pivot ~= col then
            for j = 0, 3 do
                a[col * 4 + j], a[pivot * 4 + j] = a[pivot * 4 + j], a[col * 4 + j]
                inv[col * 4 + j], inv[pivot * 4 + j] = inv[pivot * 4 + j], inv[col * 4 + j]
            end
        end
        local d = a[col * 4 + col]
        for j = 0, 3 do
            a[col * 4 + j] = a[col * 4 + j] / d
            inv[col * 4 + j] = inv[col * 4 + j] / d
        end
        for row = 0, 3 do
            if row ~= col then
                local f = a[row * 4 + col]
                if f ~= 0 then
                    for j = 0, 3 do
                        a[row * 4 + j] = a[row * 4 + j] - f * a[col * 4 + j]
                        inv[row * 4 + j] = inv[row * 4 + j] - f * inv[col * 4 + j]
                    end
                end
            end
        end
    end
    return inv
end

-- View*projection (and world, when the game has one).  The stored matrices are multiplied as
-- M = W * V * P and applied to a column vector, the convention verified against a live client's
-- own transform values (the player projects to the centre of the screen).
function G.camera(now)
    if G.matrix and now < (G.cache_until or 0) then return G.matrix end
    if now < (G.retry_after or 0) then return nil end

    local pos = B.self_pos()
    local sw, sh = 1920, 1080
    local oks, sw1, sh1 = pcall(xi.ui.screen)
    if oks then
        sw = tonumber(sw1) or sw
        sh = tonumber(sh1) or sh
    end
    local function project(m, wx, wy, wz)
        local cx = m[0] * wx + m[1] * wy + m[2] * wz + m[3]
        local cy = m[4] * wx + m[5] * wy + m[6] * wz + m[7]
        local cw = m[12] * wx + m[13] * wy + m[14] * wz + m[15]
        if not cw or math.abs(cw) < 1e-6 then return nil end
        return (cx / cw * 0.5 + 0.5) * sw, (0.5 - cy / cw * 0.5) * sh
    end
    -- A candidate is the world camera if the player is on screen and a ground step has a
    -- sensible screen size.  The ring holds every perspective camera the frame drew with: the
    -- main one is the only close one, while the minimap, shadow and background views project the
    -- player far away or make 5 yalms a pixel.
    local function candidate(world, view, proj)
        local mvp = mat_mul(mat_mul(world, view), proj)
        local inv = mat_inverse(mvp)
        if not inv then return nil end
        local sx, sy = project(mvp, pos.x, pos.z, pos.y)
        if not sx or sx < -8 or sx > sw + 8 or sy < -8 or sy > sh + 8 then return nil end
        local ax, ay = project(mvp, pos.x + 5, pos.z, pos.y)
        local bx, by = project(mvp, pos.x, pos.z, pos.y + 5)
        local scale = 0
        if ax then scale = math.max(scale, math.sqrt((ax - sx) ^ 2 + (ay - sy) ^ 2)) end
        if bx then scale = math.max(scale, math.sqrt((bx - sx) ^ 2 + (by - sy) ^ 2)) end
        if scale < 2 then return nil end
        return { mvp = mvp, inv = inv, axis = 'xzy', scale = scale, sx = sx, sy = sy }
    end
    local function table_of(t)
        if type(t) ~= 'table' or t[15] == nil then return nil end
        local out = {}
        for i = 0, 15 do out[i] = tonumber(t[i]) end
        return out
    end

    local best = nil
    local okc, list = pcall(xi.cameras)
    if okc and type(list) == 'table' then
        for _, entry in ipairs(list) do
            local world, view, proj = table_of(entry.world), table_of(entry.view), table_of(entry.projection)
            if world and view and proj then
                local c = candidate(world, view, proj)
                if c and c.scale <= 700 and (not best or c.scale > best.scale) then best = c end
            end
        end
        if not best then
            for _, entry in ipairs(list) do
                local world, view, proj = table_of(entry.world), table_of(entry.view), table_of(entry.projection)
                if world and view and proj then
                    local c = candidate(world, view, proj)
                    if c and (not best or c.scale > best.scale) then best = c end
                end
            end
        end
    end
    if not best then
        local okc2, cw, cv, cp = pcall(xi.camera)
        if okc2 and type(cw) == 'table' and type(cv) == 'table' and type(cp) == 'table' then
            local world, view, proj = table_of(cw), table_of(cv), table_of(cp)
            if world and view and proj then best = candidate(world, view, proj) end
        end
    end
    if not best and G.ready then
        local okdev, dev = pcall(xi.d3d8_device)
        if okdev and dev and dev ~= 0 then
            local success, c = pcall(function()
                local ffi = G.ffi
                local ptr = ffi.cast('XiBattleDevice*', dev)
                local w, v, p = ffi.new('float[16]'), ffi.new('float[16]'), ffi.new('float[16]')
                local vtable = ptr.lpVtbl
                if not vtable then return nil end
                local vt = ffi.cast('XiBattleVtbl*', vtable)
                if vt.GetTransform(ptr, 256, w) ~= 0 then return nil end
                if vt.GetTransform(ptr, 2, v) ~= 0 then return nil end
                if vt.GetTransform(ptr, 3, p) ~= 0 then return nil end
                local wm, vm, pm = {}, {}, {}
                for i = 0, 15 do wm[i] = w[i]; vm[i] = v[i]; pm[i] = p[i] end
                return candidate(wm, vm, pm)
            end)
            if success then best = c end
        end
    end
    if not best then
        G.retry_after = now + 5
        return nil
    end
    G.matrix = best
    G.cache_until = now + 0.1
    if best.axis then G.axis_value = best.axis end
    return best
end

function G.screen(api)
    local w, h = 1280, 720
    if api then
        local ok, io = pcall(api.GetIO)
        if ok and io and io.DisplaySize then
            w = tonumber(io.DisplaySize.x) or w
            h = tonumber(io.DisplaySize.y) or h
        end
    else
        local ok, sw, sh = pcall(xi.ui.screen)
        if ok and sw and sh then w, h = sw, sh end
    end
    return w, h
end

local function project_point(matrix, x, y, z, width, height)
    local m = matrix.mvp
    -- The client stores its transforms for column-vector multiplication (the view's translation
    -- sits in row 3, and V*P*[x,y,z,1] lands the player at the screen centre); the host's own
    -- addon draws use the row-vector form, which is why this is spelled out here.
    local cx = m[0] * x + m[1] * y + m[2] * z + m[3]
    local cy = m[4] * x + m[5] * y + m[6] * z + m[7]
    local cw = m[12] * x + m[13] * y + m[14] * z + m[15]
    -- The game's projection makes w negative for points in front of the camera depending on the
    -- pass; the perspective divide is still valid.  Only w == 0 (at infinity) is unusable.
    if not cw or math.abs(cw) < 1e-6 then return nil end
    local sx = (cx / cw * 0.5 + 0.5) * width
    local sy = (0.5 - cy / cw * 0.5) * height
    return sx, sy
end

function G.project(x, y, z, api)
    local matrix = G.camera(clock())
    if not matrix then return nil end
    local width, height = G.screen(api)
    return project_point(matrix, x, y, z, width, height)
end

local function unproject(matrix, sx, sy, ndc_z, width, height)
    local m = matrix.inv
    local x = sx / width * 2 - 1
    local y = 1 - sy / height * 2
    local px = m[0] * x + m[1] * y + m[2] * ndc_z + m[3]
    local py = m[4] * x + m[5] * y + m[6] * ndc_z + m[7]
    local pz = m[8] * x + m[9] * y + m[10] * ndc_z + m[11]
    local pw = m[12] * x + m[13] * y + m[14] * ndc_z + m[15]
    if math.abs(pw) < 1e-9 then return nil end
    return px / pw, py / pw, pz / pw
end

-- Screen cursor -> the point on the horizontal plane at ground_y.  This is the camera ray for the
-- cursor, so the circle really follows the mouse (and the arrow keys nudge it afterwards).
function G.unproject(sx, sy, ground_y, api)
    local matrix = G.camera(clock())
    if not matrix then return nil end
    local width, height = G.screen(api)
    if not sx or not sy or sx < 0 or sy < 0 or sx > width or sy > height then return nil end
    local ax, ay, az = unproject(matrix, sx, sy, 0.0, width, height)
    local bx, by, bz = unproject(matrix, sx, sy, 1.0, width, height)
    if not ax or not bx then return nil end
    local dy = by - ay
    if math.abs(dy) < 1e-6 then return nil end
    local t = (ground_y - ay) / dy
    if t < 0 then return nil end
    return ax + (bx - ax) * t, ay + (by - ay) * t, az + (bz - az) * t
end

function G.available()
    return G.ready and G.camera(clock()) ~= nil
end

-------------------------------------------------------------------------------- the engine

local R = S.runtime

function B.self_target()
    return S.runtime.target_index
end
function B.note(kind, message)
    note(kind, message)
end


local function reset_runtime()
    S.runtime = {
        dead = false, dead_at = 0, home_sent = false, revived_at = 0,
        target_index = nil, target_id = nil, attack_index = nil, attack_at = 0,
        ranged_at = 0, busy_until = 0, last_action = '', last_action_at = 0,
        last_heal = {}, last_status = {}, last_buff = {}, last_enfeeble = {},
        last_waltz = {}, ability_map = nil, ability_map_at = 0,
        ability_state = nil, ability_state_at = 0,
        last_dispel = 0, last_raise = {}, failed = {}, support_last = {},
        enf_tries = {}, enf_due = {},
        pull = { state = 'idle', mob = nil, at = 0, tries = 0 },
        kite = { angle = nil, dir = 1, at = 0, center = nil },
        move = { x = nil, y = nil, active = false },
        icons = nil, icons_at = 0, sleep_until = {},
        geo = { last_indi = 0, last_geo = 0, pet_index = nil, stayed = false },
        brd = { phase = 'support', sung = {}, nitro_at = 0, nitro_step = nil,
            nitro_issued_at = 0, piano_pending = nil },
        loot = { seen = 0, at = 0 },
    }
    R = S.runtime
end

reset_runtime()

function B.log_action(message)
    R.last_action = tostring(message or '')
    R.last_action_at = clock()
end

local function self_name()
    local me = B.self()
    return me and me.name or ''
end

local function spell_name(spell)
    if not spell then return '' end
    local name = spell.name
    if type(name) == 'table' then name = name.en or name[2] or name[1] end
    return type(name) == 'string' and name or ''
end

function B.spell(value)
    if type(value) == 'table' then return value end
    local name = text(value, 40)
    if name == '' then return nil end
    local ok, spell = pcall(S.res.spell_by_name, name)
    if ok and spell then return spell end
    -- The server's spell table drops apostrophes ("Mages Ballad III"), while the
    -- client's resource table keeps them ("Mage's Ballad III").  Try the possessive
    -- spelling before giving up; the Battle song groups use the server names.
    local possessive = name:gsub("(%a)s(%s)", "%1's%2"):gsub("(%a)s$", "%1's")
    if possessive ~= name then
        ok, spell = pcall(S.res.spell_by_name, possessive)
        if ok and spell then return spell end
    end
    return nil
end

local function spell_known(spell)
    if not spell then return false end
    local id = tonumber(spell.index) or tonumber(spell.id) or 0
    local ok, known = pcall(S.game.spell_known, id)
    if ok and known == false then return false end
    return true
end

local function spell_recast(spell)
    if not spell then return math.huge end
    local id = tonumber(spell.id) or tonumber(spell.index) or 0
    local ok, ticks = pcall(S.game.spell_recast, id)
    if ok and ticks and tonumber(ticks) > 0 then return tonumber(ticks) / 60 end
    return 0
end

local function spell_busy(spell)
    local ms = tonumber(spell and spell.cast_time) or 0
    return clamp(ms / 1000, 0.6, 12) + 1.1
end

function B.is_casting()
    local ok, count = pcall(S.game.castbar, 'Count')
    if ok and count and tonumber(count) > 0.001 then return true end
    return false
end

function B.can_act()
    if not S.running then return false end
    if R.dead then return false end
    if S.ctx and S.ctx.chat_open and S.ctx.chat_open() then return false end
    if B.is_casting() then return false end
    if clock() < (R.busy_until or 0) then return false end
    return true
end

local function issue(line, busy, label)
    if not B.can_act() then return false end
    local ok, err = pcall(xi.chat.run, line, 1)
    if not ok then
        note('error', 'Battle: ' .. tostring(err))
        return false
    end
    R.busy_until = clock() + (tonumber(busy) or 1.0)
    B.log_action(label or line)
    return true
end

function B.cast_on_member(value, slot)
    local spell = B.spell(value)
    if not spell or not spell_known(spell) then return false end
    if spell_recast(spell) > 0.05 then return false end
    local target = B.placeholder(slot)
    local member = active_member(slot)
    return issue(string.format('/ma "%s" %s', spell_name(spell), target),
        spell_busy(spell), 'cast ' .. spell_name(spell) .. ' on ' .. (member and member.name or 'self'))
end

function B.cast_on_enemy(value, index)
    local spell = B.spell(value)
    if not spell or not spell_known(spell) then return false end
    if spell_recast(spell) > 0.05 then return false end
    if index and index ~= R.target_index then B.set_target(index) end
    return issue(string.format('/ma "%s" <t>', spell_name(spell)),
        spell_busy(spell), 'cast ' .. spell_name(spell))
end

function B.use_ability_on(value, slot)
    local name = text(value, 40)
    if name == '' then return false end
    local key = 'ja:' .. name:lower()
    if clock() < (R.failed[key] or 0) then return false end
    local target = B.placeholder(slot)
    local ok = issue(string.format('/ja "%s" %s', name, target), 2.2, 'ability ' .. name)
    if ok then R.failed[key] = clock() + 5 end
    return ok
end

function B.use_ability(value, index)
    local name = text(value, 40)
    if name == '' then return false end
    local key = 'ja:' .. name:lower()
    if clock() < (R.failed[key] or 0) then return false end
    if index and index ~= R.target_index then B.set_target(index) end
    local ok = issue(string.format('/ja "%s" <t>', name), 2.2, 'ability ' .. name)
    if ok then R.failed[key] = clock() + 5 end
    return ok
end

function B.placeholder(slot)
    slot = tonumber(slot) or 0
    if slot <= 0 then return '<me>' end
    if slot <= 5 then return '<p' .. slot .. '>' end
    local group = math.floor(slot / 6)
    local member = slot % 6
    return string.format('<a%d%d>', group, member)
end

local function party_status_map()
    local now = clock()
    if R.icons ~= nil and now < (R.icons_at or 0) then return R.icons end
    local map = {}
    for index = 0, 4 do
        local ok, id = pcall(S.game.party_icons_field, index, 'ServerId')
        id = tonumber(id) or 0
        if id > 0 then
            local ok2, list = pcall(S.game.party_icons, index)
            if ok2 and type(list) == 'table' then map[id] = list end
        end
    end
    R.icons = map
    R.icons_at = now + 0.3
    return map
end

function B.member_statuses(slot)
    if slot == 0 then
        local ok, list = pcall(function() return S.game.player('Buffs') end)
        if ok and type(list) == 'table' then return list end
        return {}
    end
    local member = active_member(slot)
    if not member or slot > 5 then return nil end
    local map = party_status_map()
    return map[member.id] or {}
end

function B.has_status(slot, ids)
    if type(ids) ~= 'table' or #ids == 0 then return false end
    local list = B.member_statuses(slot)
    if not list then return nil end
    for _, raw in ipairs(list) do
        local id = tonumber(raw) or 0
        for _, wanted in ipairs(ids) do
            if id == wanted then return true end
        end
    end
    return false
end

local BUFF_IDS = {
    protect = { 40 }, shell = { 41 }, haste = { 33 }, regen = { 42 }, refresh = { 43 },
    phalanx = { 116 }, stoneskin = { 37 }, aquaveil = { 39 }, blink = { 36 },
    utsusemi = { 66 }, reraise = { 113 }, invisible = { 69 }, sneak = { 71 },
    deodorize = { 70 }, regain = { 170 }, enlight = { 274 }, endark = { 288 },
    enfire = { 94, 277 }, enblizzard = { 95, 278 }, enaero = { 96, 279 },
    enstone = { 97, 280 }, enthunder = { 98, 281 }, enwater = { 99, 282 },
    migawari = { 471 },
}

local function buff_key(value)
    local name = text(value, 40):lower()
    if name == '' then return nil end
    name = name:gsub('%s+[ivx]+$', ''):gsub('%s+[0-9]+$', '')
    if name:sub(-2) == 'ra' then name = name:sub(1, -3) end
    if BUFF_IDS[name] then return name end
    if name:sub(1, 7) == 'protect' then return 'protect' end
    if name:sub(1, 5) == 'shell' then return 'shell' end
    if name:sub(1, 5) == 'haste' then return 'haste' end
    if name:sub(1, 5) == 'regen' then return 'regen' end
    if name:sub(1, 7) == 'refresh' then return 'refresh' end
    if name:sub(1, 7) == 'phalanx' then return 'phalanx' end
    if name:sub(1, 8) == 'stoneski' then return 'stoneskin' end
    if name:sub(1, 8) == 'aquaveil' then return 'aquaveil' end
    if name:sub(1, 4) == 'blin' then return 'blink' end
    if name:sub(1, 5) == 'utsus' then return 'utsusemi' end
    if name:sub(1, 6) == 'reraise' then return 'reraise' end
    return nil
end

function B.has_buff(slot, spell)
    local key = buff_key(spell)
    if not key then return nil end
    return B.has_status(slot, BUFF_IDS[key])
end

local NA_SPELL = {
    [3] = 'Poisona', [4] = 'Paralyna', [5] = 'Blindna', [6] = 'Silena',
    [7] = 'Stona', [8] = 'Viruna', [9] = 'Cursna', [31] = 'Viruna',
}
local NA_SAFE = { [2] = true, [10] = true, [11] = true, [12] = true, [13] = true, [31] = true }

local function avoid_set()
    local out = {}
    for name in tostring(S.profile.heal.avoid or ''):gmatch('[^,]+') do
        name = text(name, 40):lower()
        if name ~= '' then out[name] = true end
    end
    return out
end

function B.member_slot(name)
    name = text(name, 32)
    if name == '' then return nil end
    for _, member in ipairs(B.members('alliance')) do
        if member.name == name then return member.slot end
    end
    return nil
end

function B.member(name)
    local slot = B.member_slot(name)
    return slot and active_member(slot) or nil
end

-------------------------------------------------------------------------------- movement and camp

local function camp_table(kind)
    if not S.profile then return nil end
    if kind == 'support' then return S.profile.support_camp end
    return S.profile.camp
end

function B.tank_follow_pos()
    if not S.profile then return nil end
    local name = S.profile.roster.tank
    local index = name ~= '' and entity_by_name(name) or nil
    if index and entity_live(index) then
        local pos = position(index)
        if pos then return pos, index end
    end
    return nil
end

function B.mobile_support_pos(tank, tank_index)
    if not tank then return nil end
    local target = R.target_index
    local mob = target and position(target) or nil
    local dx, dy
    if mob then
        dx, dy = tank.x - mob.x, tank.y - mob.y
    else
        local heading = tonumber(tank.heading) or 0
        dx, dy = -math.sin(heading), -math.cos(heading)
    end
    local span = math.sqrt(dx * dx + dy * dy)
    if span > 0.05 then dx, dy = dx / span, dy / span else dx, dy = 0, -1 end
    local follow = tonumber(S.profile.camp.follow_distance) or 12
    return { x = tank.x + dx * follow, y = tank.y + dy * follow, z = tank.z }
end

function B.camp_pos(kind)
    kind = kind or 'tank'
    local camp = camp_table(kind)
    local mobile = S.profile and S.profile.camp.mobile
    local tank_enabled = not S.profile or S.profile.camp.tank_enabled ~= false
    if mobile then
        local tank, index = B.tank_follow_pos()
        if tank then
            if kind == 'support' then return B.mobile_support_pos(tank, index) end
            return { x = tank.x, y = tank.y, z = tank.z }
        end
    end
    if kind == 'tank' and not tank_enabled then
        local tank = B.tank_follow_pos()
        if tank then return { x = tank.x, y = tank.y, z = tank.z } end
    end
    if not camp or not camp.set then
        if kind == 'support' then return B.camp_pos('tank') end
        return nil
    end
    return { x = camp.x, y = camp.y, z = camp.z }
end

function B.camp_radius(kind)
    kind = kind or 'tank'
    local camp = camp_table(kind)
    if not camp or not camp.set then
        if kind == 'support' then return B.camp_radius('tank') end
        return 10
    end
    return tonumber(camp.radius) or 10
end

function B.support_camp_pos()
    if S.profile and S.profile.camp.mobile then return B.camp_pos('support') end
    local camp = S.profile and S.profile.support_camp
    if camp and camp.set then return { x = camp.x, y = camp.y, z = camp.z } end
    return B.camp_pos('tank')
end

function B.ensure_camp()
    local camp = S.profile.camp
    if camp.set then return true end
    local pos = B.self_pos()
    if not pos then return false end
    camp.set, camp.x, camp.y, camp.z = true, pos.x, pos.y, pos.z
    note('info', 'No camp was set; the current spot is now the camp.')
    return true
end

function B.inside_camp(pos, margin, kind)
    local camp = B.camp_pos(kind)
    if not camp then return true end
    if not pos then return false end
    local dx, dy = pos.x - camp.x, pos.y - camp.y
    local radius = B.camp_radius(kind) + (tonumber(margin) or 0)
    return dx * dx + dy * dy <= radius * radius
end

function B.stop_move()
    if not S.game then return end
    pcall(S.game.set_autofollow, 'IsAutoRunning', 0)
    pcall(S.game.set_autofollow, 'FollowDeltaX', 0)
    pcall(S.game.set_autofollow, 'FollowDeltaY', 0)
    pcall(S.game.set_autofollow, 'FollowDeltaZ', 0)
    R.move.active = false
    R.move.x, R.move.y = nil, nil
end

function B.move_to(target, stop_distance)
    if not target then B.stop_move(); return false end
    local pos = B.self_pos()
    if not pos then return false end
    local dx, dy = target.x - pos.x, target.y - pos.y
    local span = math.sqrt(dx * dx + dy * dy)
    local stop = tonumber(stop_distance) or 0.6
    if span <= stop then
        B.stop_move()
        return false
    end
    dx, dy = dx / span, dy / span
    local running = S.game.autofollow('IsAutoRunning') or 0
    local changed = not R.move.active
        or math.abs(dx - (R.move.x or 99)) + math.abs(dy - (R.move.y or 99)) > 0.02
    if changed or running == 0 then
        pcall(S.game.set_autofollow, 'FollowDeltaX', dx)
        pcall(S.game.set_autofollow, 'FollowDeltaY', dy)
        pcall(S.game.set_autofollow, 'FollowDeltaZ', 0)
        pcall(S.game.set_autofollow, 'IsAutoRunning', 1)
        R.move.active = true
        R.move.x, R.move.y = dx, dy
    end
    return true
end

function B.camp_for_role(role, name)
    name = name or self_name()
    local assigned = S.profile.camp_assign and S.profile.camp_assign[name]
    if assigned == 'tank' or assigned == 'support' then return assigned end
    if role == 'support' or role == 'ranged' then return 'support' end
    if not role then
        local own = B.self_role()
        if own == 'support' or own == 'ranged' then return 'support' end
    end
    return 'tank'
end

function B.combat_style_for(role, name)
    name = name or self_name()
    local mode = S.profile.combat_style and S.profile.combat_style[name]
    if mode == 'melee' or mode == 'ranged' then return mode end
    return role == 'ranged' and 'ranged' or 'melee'
end

function B.return_to_camp(role)
    local kind = B.camp_for_role(role)
    local camp = B.camp_pos(kind)
    if not camp then return false end
    local pos = B.self_pos()
    if not pos then return false end
    local dx, dy = pos.x - camp.x, pos.y - camp.y
    local radius = B.camp_radius(kind) * 0.55
    if dx * dx + dy * dy <= radius * radius then
        B.stop_move()
        return false
    end
    B.move_to(camp, math.max(0.8, radius * 0.5))
    return true
end

-------------------------------------------------------------------------------- targets and claims

local function client_target()
    local ok, index = pcall(function() return S.game.target('Targets[0].Index') end)
    index = ok and tonumber(index) or 0
    if index and index > 0 and entity_live(index) and is_mob(index) then return index end
    return nil
end

function B.set_target(index)
    if not index or index < 0 then return false end
    local id = tonumber(S.game.entity(index, 'ServerId')) or 0
    pcall(S.game.set_target_index, index)
    R.target_index = index
    R.target_id = id
    R.attack_index = nil
    R.attack_at = 0
    return true
end

function B.clear_target()
    R.target_index = nil
    R.target_id = nil
    R.attack_index = nil
    R.attack_at = 0
end

function B.target_valid()
    local index = R.target_index
    if not index then return false end
    if not entity_live(index) then B.clear_target(); return false end
    if not is_mob(index) then B.clear_target(); return false end
    local hpp = tonumber(S.game.entity(index, 'HPPercent')) or 0
    if hpp <= 0 then B.clear_target(); return false end
    local id = tonumber(S.game.entity(index, 'ServerId')) or 0
    if R.target_id and id ~= R.target_id then B.clear_target(); return false end
    local pos = position(index)
    local mine = B.self_pos()
    if pos and mine and distance(pos, mine) > 70 then B.clear_target(); return false end
    return true
end

function B.target_member()
    if not B.target_valid() then return nil end
    return claim_of(R.target_index)
end

function B.target_name()
    if not B.target_valid() then return nil end
    return S.game.entity(R.target_index, 'Name')
end

function B.target_hpp()
    if not B.target_valid() then return 0 end
    return tonumber(S.game.entity(R.target_index, 'HPPercent')) or 0
end

local function mob_list(kind)
    local out = {}
    local count = S.game.entity_count() or 0
    local camp = B.camp_pos(kind)
    local me = B.self_pos()
    for index = 0, count - 1 do
        if entity_live(index) and is_mob(index) then
            local hpp = tonumber(S.game.entity(index, 'HPPercent')) or 0
            if hpp > 0 then
                local pos = position(index)
                if pos then
                    local claim, claim_id = claim_of(index)
                    local item = {
                        index = index,
                        id = tonumber(S.game.entity(index, 'ServerId')) or 0,
                        name = S.game.entity(index, 'Name') or '',
                        hpp = hpp, pos = pos, claim = claim, claim_id = claim_id,
                        dist_camp = camp and distance(pos, camp) or 999,
                        dist_self = me and distance(pos, me) or 999,
                    }
                    local failed = R.failed['mob:' .. tostring(item.id)]
                    if not failed or clock() >= failed then out[#out + 1] = item end
                end
            end
        end
    end
    return out
end

function B.mobs()
    return mob_list()
end

local function claim_allowed(mob, role)
    local p = S.profile
    local mode = p.engage.mode
    if role == 'tank' or role == 'puller' then return true end
    if not mob.claim then
        if not p.engage.wait_claim and mode == 'always' then return true end
        return false
    end
    if mode == 'always' then return true end
    if mode == 'none' then return false end
    if mode == 'tank' then return p.roster.tank ~= '' and mob.claim.name == p.roster.tank end
    if mode == 'puller' then return p.roster.puller ~= '' and mob.claim.name == p.roster.puller end
    if mode == 'player' then return p.engage.player ~= '' and mob.claim.name == p.engage.player end
    if mode == 'leader' then
        local leader = active_member(1)
        return leader ~= nil and mob.claim.slot == leader.slot
    end
    return false
end

function B.claim_allowed(mob, role)
    return claim_allowed(mob, role)
end

local function pick_mob(role, allow_unclaimed)
    local p = S.profile
    local list = mob_list()
    local best, best_score = nil, math.huge
    for _, mob in ipairs(list) do
        local allowed = false
        if allow_unclaimed and role ~= 'support' then
            if not mob.claim then
                allowed = true
            elseif role == 'tank' or role == 'puller' then
                allowed = true
            else
                allowed = claim_allowed(mob, role)
            end
        else
            allowed = claim_allowed(mob, role)
        end
        if allowed then
            if role ~= 'tank' and role ~= 'puller' and p.engage.camp_only then
                if mob.dist_camp > (tonumber(p.camp.radius) or 10) + 5 then allowed = false end
            end
            local reach = (tonumber(p.engage.max_distance) or 30)
            if role == 'puller' then reach = (tonumber(p.pull.find_distance) or 40) end
            if allowed and mob.dist_self > reach then allowed = false end
            if allowed and role == 'puller' then
                -- The puller's search is a radius from camp, and an optional name whitelist.
                if mob.dist_camp > reach then allowed = false end
                if allowed and #p.pull.mobs > 0 then
                    local matches = false
                    local name = tostring(mob.name or ''):lower()
                    for _, wanted in ipairs(p.pull.mobs) do
                        if wanted:lower() == name then matches = true break end
                    end
                    if not matches then allowed = false end
                end
            end
            if allowed and role ~= 'tank' and role ~= 'puller'
                and mob.dist_camp > (tonumber(p.pull.leash) or 28) then
                allowed = false
            end
            if allowed then
                local score = mob.dist_camp
                if mob.claim and role ~= 'tank' and role ~= 'puller' then
                    if p.roster.tank ~= '' and mob.claim.name == p.roster.tank then score = score - 30 end
                end
                if role == 'tank' and mob.claim and p.roster.puller ~= ''
                    and mob.claim.name == p.roster.puller then score = score - 20 end
                if score < best_score then best, best_score = mob, score end
            end
        end
    end
    if best then return best.index end
    return nil
end

function B.pick_target(role)
    return pick_mob(role, false)
end

function B.count_claimed()
    local camp = B.camp_pos()
    local radius = (tonumber(S.profile.camp.radius) or 10) + 4
    local count = 0
    for _, mob in ipairs(mob_list()) do
        if mob.claim and (not camp or mob.dist_camp <= radius * 1.6) then count = count + 1 end
    end
    return count
end

-------------------------------------------------------------------------------- combat entry

function B.engage(index, role)
    if not index or not S.running then return false end
    if not entity_live(index) then return false end
    local pos = position(index)
    if not pos then return false end
    local mine = B.self_pos()
    if not mine then return false end
    local range = role == 'ranged' and 22 or 3.0
    if distance(pos, mine) > range then
        B.move_to(pos, role == 'ranged' and 18 or 2.2)
        if role == 'ranged' then return false end
    else
        B.stop_move()
    end

    if role == 'ranged' then
        if index ~= R.target_index then B.set_target(index) end
        if clock() >= (R.ranged_at or 0) then
            if issue('/ra <t>', 2.4, 'ranged attack') then
                R.ranged_at = clock() + 4.2
            end
        end
        return true
    end

    if R.attack_index ~= index or clock() > (R.attack_at or 0) + 30 then
        if index ~= R.target_index then B.set_target(index) end
        if issue('/attack <t>', 1.2, 'engage') then
            R.attack_index = index
            R.attack_at = clock()
            return true
        end
    end
    return false
end

function B.disengage()
    if R.attack_index or R.target_index then
        pcall(xi.chat.run, '/attack off', 1)
        B.log_action('disengage')
    end
    B.clear_target()
    B.stop_move()
end

function B.use_weaponskill()
    local ws = text(S.profile.engage.weapon_skill, 40)
    if ws == '' or not B.target_valid() then return false end
    local pos = position(R.target_index)
    local mine = B.self_pos()
    if pos and mine and distance(pos, mine) > 3.6 then return false end
    local tp = tonumber(S.game.party_member(0, 'TP')) or 0
    if tp < 1000 then return false end
    return issue(string.format('/ws "%s" <t>', ws), 3.2, 'weapon skill ' .. ws)
end

-------------------------------------------------------------------------------- healing and status removal

-- Dancer waltzes are job abilities, not spells: a BRD/DNC has no Cure or -na spells at all,
-- so the healing engine has to reach the client's ability menu for its sub job.  The ability
-- list function is defined further down (it needs the job/suggest helpers); this forward
-- declaration lets the waltz helpers and heal_tick use it.
local known_abilities

local WALTZ_TIERS = {
    { name = 'Curing Waltz V', cost = 800, recast = 14 },
    { name = 'Curing Waltz IV', cost = 650, recast = 12 },
    { name = 'Curing Waltz III', cost = 500, recast = 10 },
    { name = 'Curing Waltz II', cost = 350, recast = 8 },
    { name = 'Curing Waltz', cost = 200, recast = 6 },
}
local WALTZ_HEALING = { name = 'Healing Waltz', cost = 200, recast = 8 }

-- The statuses Healing Waltz may remove, mirrored from server/fanxi_server/game/dancer.py
-- (LandSandBoat's waltzable statuses).  A status that is not here must use -na or Erase.
local WALTZABLE = {
    [3] = true, [4] = true, [5] = true, [6] = true, [8] = true, [9] = true,
    [11] = true, [12] = true, [13] = true, [21] = true, [30] = true, [31] = true,
    [128] = true, [129] = true, [130] = true, [131] = true, [132] = true, [133] = true,
    [134] = true, [135] = true,
    [136] = true, [137] = true, [138] = true, [139] = true, [140] = true, [141] = true,
    [142] = true, [144] = true, [145] = true,
    [146] = true, [147] = true, [148] = true, [149] = true, [156] = true,
    [167] = true, [174] = true, [175] = true, [189] = true,
    [291] = true, [298] = true, [404] = true,
}
local WALTZ_SABER_DANCE = 410
local WALTZ_TRANCE = 376

local function ability_key(name)
    return tostring(name or ''):lower():gsub('%s+', ' '):gsub('^%s+', ''):gsub('%s+$', '')
end

-- The client's ability list is the authority (it already includes the sub job).  Cache it
-- for a second so the 60 fps editor does not re-read the whole action list every frame.
local function ability_map()
    local now = clock()
    if R.ability_map and now < (R.ability_map_at or 0) then return R.ability_map end
    local map = {}
    for _, name in ipairs(known_abilities()) do
        local key = ability_key(name)
        if key ~= '' and not map[key] then map[key] = name end
    end
    R.ability_map = map
    R.ability_map_at = now + 1.0
    return map
end

-- The client's ability recast table, matched to the current job's ability commands.  The 0x119
-- table is indexed by a recast slot and carries the recast id; res.ability gives that id for a
-- command.  Cached for half a second because the engine ticks about seven times a second.
function B.ability_state()
    local now = clock()
    if R.ability_state and now < (R.ability_state_at or 0) then return R.ability_state end
    local recasts = {}
    for slot = 0, 30 do
        local ok, ticks, recast_id = pcall(S.game.ability_recast, slot)
        ticks = ok and tonumber(ticks) or 0
        recast_id = ok and tonumber(recast_id) or 0
        if ticks > 0 and recast_id > 0 then
            local seconds = ticks / 60
            if seconds > (recasts[recast_id] or 0) then recasts[recast_id] = seconds end
        end
    end
    local out = {}
    local ok, ids = pcall(S.game.ability_commands)
    if ok and type(ids) == 'table' then
        for _, raw in ipairs(ids) do
            local id = tonumber(raw) or 0
            if id >= 0x200 and id < 0x400 then
                local ok2, ability = pcall(S.res.ability, id)
                if ok2 and type(ability) == 'table' then
                    local name = ability.name
                    if type(name) == 'table' then name = name.en or name[2] or name[1] end
                    local key = type(name) == 'string' and ability_key(name) or ''
                    if key ~= '' then
                        local recast_id = tonumber(ability.recast_id) or 0
                        out[key] = {
                            name = name,
                            recast_id = recast_id,
                            remaining = recast_id > 0 and (recasts[recast_id] or 0) or 0,
                        }
                    end
                end
            end
        end
    end
    R.ability_state = out
    R.ability_state_at = now + 0.5
    return out
end

function B.ability_remaining(name)
    local state = B.ability_state()[ability_key(name)]
    if not state then return nil end
    return tonumber(state.remaining) or 0
end

function B.ability_ready(name)
    local remaining = B.ability_remaining(name)
    return remaining ~= nil and remaining <= 0.05
end

local function waltz_map()
    local map = ability_map()
    local out = {}
    for _, def in ipairs(WALTZ_TIERS) do
        local name = map[ability_key(def.name)]
        if name then out[#out + 1] = { name = name, def = def } end
    end
    local healing = map[ability_key(WALTZ_HEALING.name)]
    if healing then out[#out + 1] = { name = healing, def = WALTZ_HEALING } end
    return out
end

function B.detected_waltzes()
    local out = {}
    for _, entry in ipairs(waltz_map()) do out[#out + 1] = entry.def.name end
    return out
end

local function waltz_casting_blocked()
    return B.has_status(0, { WALTZ_SABER_DANCE }) == true
end

local function waltz_affordable(def, me, p, emergency)
    if B.has_status(0, { WALTZ_TRANCE }) == true then return true end
    local reserve = emergency and 0 or (tonumber(p.waltz_tp_reserve) or 0)
    return (tonumber(me and me.tp) or 0) - (tonumber(def.cost) or 0) >= reserve
end

local function waltz_ready(def, now)
    return now >= (R.last_waltz[ability_key(def.name)] or 0)
end

local function pick_curing_waltz(me, p, emergency, avoid)
    if not p.waltz or waltz_casting_blocked() then return nil end
    local now = clock()
    for _, entry in ipairs(waltz_map()) do
        if entry.def ~= WALTZ_HEALING and waltz_ready(entry.def, now)
            and waltz_affordable(entry.def, me, p, emergency)
            and not (avoid and avoid[ability_key(entry.name)]) then
            return entry.name, entry.def
        end
    end
    return nil
end

local function healing_waltz(p, emergency)
    if not p.waltz_status or waltz_casting_blocked() then return nil end
    local name = ability_map()[ability_key(WALTZ_HEALING.name)]
    if not name or not waltz_ready(WALTZ_HEALING, clock())
        or not waltz_affordable(WALTZ_HEALING, B.self(), p, emergency) then
        return nil
    end
    return name, WALTZ_HEALING
end

local function use_waltz(name, def, slot)
    local ok = B.use_ability_on(name, slot)
    local key = ability_key(def.name)
    if ok then
        R.last_waltz[key] = clock() + (tonumber(def.recast) or 8)
        B.log_action('waltz ' .. name)
    else
        R.last_waltz[key] = clock() + 2
    end
    return ok
end

local function observe_slots()
    return B.members(S.profile.heal.observe == 'alliance' and 'alliance' or 'party')
end

local function heal_excluded(name)
    name = tostring(name or ''):lower()
    for _, excluded in ipairs(S.profile.heal.exclude or {}) do
        if tostring(excluded):lower() == name then return true end
    end
    return false
end

local function cure_for(hpp)
    local rows = {}
    for _, row in ipairs(S.profile.heal.cures) do
        if row.spell ~= '' then rows[#rows + 1] = row end
    end
    table.sort(rows, function(a, b) return (tonumber(a.below) or 0) < (tonumber(b.below) or 0) end)
    for _, row in ipairs(rows) do
        if hpp <= (tonumber(row.below) or 0) then return row end
    end
    return nil
end

local function status_removal()
    local p = S.profile.heal
    if not (p.status or p.waltz_status) then return false end
    local now = clock()
    local avoid = avoid_set()
    for _, member in ipairs(observe_slots()) do
        if member.slot <= 5 and member.hp > 0 then
            local excluded = heal_excluded(member.name)
            local list = B.member_statuses(member.slot)
            if list then
                for _, raw in ipairs(list) do
                    local id = tonumber(raw) or 0
                    local spell = NA_SPELL[id]
                    local emergency = excluded and member.hpp <= p.emergency
                    local allowed = not excluded or (id == 6 and not emergency)
                    if spell and allowed and p.status then
                        local key = 'na:' .. tostring(member.slot) .. ':' .. tostring(id)
                        if now >= (R.last_status[key] or 0) then
                            local data = B.spell(spell)
                            if data and spell_known(data) and spell_recast(data) <= 0.05 then
                                if B.cast_on_member(spell, member.slot) then
                                    R.last_status[key] = now + 8
                                    return true
                                end
                                R.last_status[key] = now + 3
                            end
                        end
                    end
                    -- BRD/DNC has no -na spells at all; Healing Waltz is the sub-job's
                    -- answer to the same statuses.  It cleanses one status per 200 TP.
                    if allowed and p.waltz_status and WALTZABLE[id] then
                        local key = 'waltz:' .. tostring(member.slot) .. ':' .. tostring(id)
                        if now >= (R.last_status[key] or 0) then
                            local name, def = healing_waltz(p, member.hpp <= p.emergency)
                            if name and not avoid[ability_key(name)] then
                                if use_waltz(name, def, member.slot) then
                                    R.last_status[key] = now + 8
                                    return true
                                end
                                R.last_status[key] = now + 3
                            end
                        end
                    end
                end
                if p.erase and not excluded and now >= (R.last_status['erase:' .. member.slot] or 0) then
                    local erase = B.spell('Erase')
                    local dirty = false
                    if erase and spell_known(erase) and spell_recast(erase) <= 0.05 then
                        for _, raw in ipairs(list) do
                            local id = tonumber(raw) or 0
                            if id > 0 and id ~= 255 and id ~= 65535 and not NA_SPELL[id] and not NA_SAFE[id] then
                                dirty = true
                                break
                            end
                        end
                    end
                    if dirty and B.cast_on_member('Erase', member.slot) then
                        R.last_status['erase:' .. member.slot] = now + 10
                        return true
                    end
                end
            end
        end
    end
    return false
end

function B.heal_tick()
    local p = S.profile.heal
    if not p.enabled then return false end
    local me = B.self()
    if not me then return false end
    if status_removal() then return true end

    local worst, rule, worst_waltz = nil, nil, nil
    local avoid = avoid_set()
    local waltz_below = tonumber(p.waltz_below) or 75
    for _, member in ipairs(observe_slots()) do
        if member.slot ~= nil and member.hp > 0 and member.zone == me.zone and member.hpp <= 100 then
            local emergency = member.hpp <= p.emergency
            local excluded = heal_excluded(member.name)
            if not excluded or emergency then
                -- Spell cures obey the MP reserve; a waltz spends TP instead and is handled
                -- separately below.  Emergency breaks both reserves.
                if emergency or (tonumber(me.mpp) or 0) >= p.mp_reserve then
                    local candidate = cure_for(member.hpp)
                    if not candidate and emergency then candidate = cure_for(100) end
                    if candidate and not avoid[candidate.spell:lower()] then
                        local spell = B.spell(candidate.spell)
                        if spell and spell_known(spell) and spell_recast(spell) <= 0.05 then
                            if not worst or member.hpp < worst.hpp then worst, rule = member, candidate end
                        end
                    end
                end
                if p.waltz and (emergency or member.hpp <= waltz_below) then
                    if not worst_waltz or member.hpp < worst_waltz.hpp then worst_waltz = member end
                end
            end
        end
    end
    if worst and rule and B.cast_on_member(rule.spell, worst.slot) then
        R.last_heal[worst.slot] = clock()
        return true
    end
    if worst_waltz then
        local name, def = pick_curing_waltz(me, p, worst_waltz.hpp <= p.emergency, avoid)
        if name then
            if use_waltz(name, def, worst_waltz.slot) then
                R.last_heal[worst_waltz.slot] = clock()
                return true
            end
        end
    end
    return false
end

-------------------------------------------------------------------------------- buffs, enfeebles, dispels

local function buff_targets(scope)
    if scope == 'self' then
        local me = B.self()
        return me and { me } or {}
    end
    local out = {}
    local list = B.members(scope == 'alliance' and 'alliance' or 'party')
    for _, member in ipairs(list) do
        if member.hp > 0 then out[#out + 1] = member end
    end
    return out
end

local function buff_excluded(row, name)
    name = tostring(name or ''):lower()
    for _, excluded in ipairs(row.exclude or {}) do
        if tostring(excluded):lower() == name then return true end
    end
    return false
end

local function is_area_buff(spell)
    local name = spell_name(spell):lower()
    if name:sub(-2) == 'ra' then return true end
    local area = tonumber(spell.area_range) or 0
    return area > 0
end

function B.buff_tick()
    local p = S.profile.buffs
    if not p.enabled then return false end
    if B.target_valid() or B.is_casting() then return false end
    local now = clock()
    local me = B.self()
    if not me then return false end
    for _, row in ipairs(p.rows) do
        local spell = B.spell(row.spell)
        local ability = nil
        if row.ability then
            local ok, found = pcall(S.res.ability_by_name, row.spell)
            if ok then ability = found end
        end
        local usable = (spell and spell_known(spell) and spell_recast(spell) <= 0.05) or (ability ~= nil)
        if usable then
            local area = spell and is_area_buff(spell) or false
            local targets = buff_targets(row.target or 'self')
            for _, member in ipairs(targets) do
                if not buff_excluded(row, member.name) then
                local key = row.spell:lower() .. ':' .. tostring(member.slot)
                local interval = tonumber(row.interval) or 120
                local present = spell and B.has_buff(member.slot, row.spell) or nil
                local due = present == false
                    or (present == nil and now >= (R.last_buff[key] or 0) + interval)
                if due and now >= (R.last_buff[key] or 0) + 5 then
                    if me.mpp < S.profile.heal.mp_reserve and member.slot ~= 0 and spell then return false end
                    local ok
                    if ability then
                        ok = B.use_ability_on(row.spell, member.slot)
                    elseif area then
                        ok = B.cast_on_member(spell_name(spell), 0)
                    else
                        ok = B.cast_on_member(spell_name(spell), member.slot)
                    end
                    if ok then
                        R.last_buff[key] = now
                        if area then
                            for _, other in ipairs(targets) do
                                R.last_buff[row.spell:lower() .. ':' .. tostring(other.slot)] = now
                            end
                        end
                        return true
                    end
                    R.last_buff[key] = now + 2
                    return false
                end
                end
            end
        end
    end
    return false
end

function B.enfeeble_tick()
    local p = S.profile.enfeebles
    if not p.enabled or not B.target_valid() then return false end
    if S.profile.engage.mode == 'none' then return false end
    if not claim_allowed({ claim = B.target_member() }, 'support') then return false end
    if clock() < (R.sleep_until[B.target_name()] or 0) then return false end
    local now = clock()
    for _, row in ipairs(p.rows) do
        local spell = B.spell(row.spell)
        local key = 'enf:' .. row.spell:lower()
        local tries = tonumber(R.enf_tries[key]) or 0
        if tries >= (tonumber(p.max_tries) or 3) then
            -- stopped until the wear-off/landing log or the Reset button clears the count
        elseif spell and spell_known(spell) and spell_recast(spell) <= 0.05 then
            local interval = tonumber(row.interval) or 120
            local due = R.enf_due[key] == true
            if due or now >= (R.last_enfeeble[key] or 0) + interval then
                if B.cast_on_enemy(row.spell, R.target_index) then
                    R.last_enfeeble[key] = now
                    R.enf_due[key] = nil
                    return true
                end
                R.last_enfeeble[key] = now + 5
            end
        end
    end
    return false
end

function B.dispel_tick()
    local p = S.profile.dispel
    if not p.enabled or not B.target_valid() then return false end
    if not claim_allowed({ claim = B.target_member() }, 'support') then return false end
    local now = clock()
    if now < (R.last_dispel or 0) + (tonumber(p.interval) or 45) then return false end
    if p.spell == '' then return false end
    local spell = B.spell(p.spell)
    if not spell or not spell_known(spell) or spell_recast(spell) > 0.05 then return false end
    if B.cast_on_enemy(p.spell, R.target_index) then
        R.last_dispel = now
        return true
    end
    R.last_dispel = now + 5
    return false
end

-------------------------------------------------------------------------------- support jobs (GEO/BRD)

local function self_job()
    local me = B.self()
    return me and tonumber(me.job) or 0
end

local function pet_position()
    local ok, _mpp, _tp, index = pcall(S.game.pet)
    index = ok and tonumber(index) or nil
    if not index or index < 0 then return nil end
    local pos = position(index)
    return pos, index
end

local function use_self_ability(name)
    name = text(name, 40)
    if name == '' then return false end
    local key = 'ja:' .. name:lower()
    if clock() < (R.failed[key] or 0) then return false end
    local ok = issue(string.format('/ja "%s" <me>', name), 2.2, 'ability ' .. name)
    if ok then R.failed[key] = clock() + 5 end
    return ok
end

local function cast_self_spell(value)
    local spell = B.spell(value)
    if not spell or not spell_known(spell) or spell_recast(spell) > 0.05 then return false end
    return issue(string.format('/ma "%s" <me>', spell_name(spell)),
        spell_busy(spell), 'cast ' .. spell_name(spell) .. ' on self')
end

local function cast_pet_spell(value)
    local spell = B.spell(value)
    if not spell or not spell_known(spell) or spell_recast(spell) > 0.05 then return false end
    return issue(string.format('/ma "%s" <pet>', spell_name(spell)),
        spell_busy(spell), 'cast ' .. spell_name(spell) .. ' on Luopan')
end

local function cast_song(value, slot)
    local spell = B.spell(value)
    if not spell or not spell_known(spell) or spell_recast(spell) > 0.05 then return false end
    local target = B.placeholder(slot or 0)
    return issue(string.format('/song "%s" %s', spell_name(spell), target),
        spell_busy(spell), 'song ' .. spell_name(spell))
end

local function csv_list(value)
    local out = {}
    for part in tostring(value or ''):gmatch('[^,]+') do
        local name = text(part, 40)
        if name ~= '' then out[#out + 1] = name end
    end
    return out
end

local function role_slot(role)
    local name = B.active_role_name(role)
    if name == '' then return nil end
    for _, member in ipairs(B.members('alliance')) do
        if member.name and member.name:lower() == name:lower() then return member.slot end
    end
    return nil
end

local function geo_anchor()
    local cfg = S.profile.support.geo
    local wanted = text(cfg.anchor, 32)
    local fallback = nil
    for _, member in ipairs(B.members('alliance')) do
        if member.hp > 0 then
            if wanted ~= '' and member.name:lower() == wanted:lower() then return member end
            if not fallback and member.slot > 0 then fallback = member end
        end
    end
    local tank = text(S.profile.roster.tank, 32)
    if tank ~= '' then
        for _, member in ipairs(B.members('alliance')) do
            if member.hp > 0 and member.name:lower() == tank:lower() then return member end
        end
    end
    for _, member in ipairs(B.members('party')) do
        if member.hp > 0 and member.slot > 0 then return member end
    end
    return fallback
end

local function geo_tick(me)
    local cfg = S.profile.support.geo
    if not cfg.enabled then return false end
    local now = clock()
    local geo = R.geo
    local anchor = geo_anchor()
    if not anchor then return false end
    local dist = distance(me, anchor)
    local range = tonumber(cfg.range) or 20
    local need_geo = now >= (geo.last_geo or 0) + (tonumber(cfg.geo_interval) or 120)
    local need_indi = now >= (geo.last_indi or 0) + (tonumber(cfg.indi_interval) or 120)
    if need_geo and dist <= range then
        local ok
        if anchor.slot == 0 then
            ok = cast_self_spell(cfg.geo)
        else
            ok = B.cast_on_member(cfg.geo, anchor.slot)
        end
        if ok then
            geo.last_geo = now
            return true
        end
    end
    if need_geo and dist > range and now >= (geo.warn_at or 0) + 30 then
        geo.warn_at = now
        note('action', string.format('Battle: GEO anchor %s is %.1f yalms away; Geo range is %.1f.',
            anchor.name, dist, range))
    end
    if need_indi and cast_self_spell(cfg.indi) then
        geo.last_indi = now
        return true
    end
    return false
end

function B.brd_group_name(camp)
    local cfg = S.profile.support.brd
    if S.profile.camp.mobile then return cfg.mobile_group end
    return camp == 'support' and cfg.support_group or cfg.tank_group
end

function B.brd_group_songs(camp)
    local name = B.brd_group_name(camp)
    for _, group in ipairs(S.profile.support.brd.song_groups or {}) do
        if group.name == name then return group.songs end
    end
    return {}
end

local function brd_song_due(name, key)
    key = key or name
    local sung = R.brd.sung[key]
    return not sung or clock() >= sung + B.song_duration(name)
end

local function brd_camp_due(camp)
    for _, song in ipairs(B.brd_group_songs(camp)) do
        if brd_song_due(song) then return true end
    end
    return false
end

function B.brd_piano_due()
    local cfg = S.profile.support.brd
    if cfg.pianissimo_target == '' or cfg.pianissimo_song == '' then return false end
    local slot = B.member_slot(cfg.pianissimo_target)
    if slot == nil then return false end
    return brd_song_due(cfg.pianissimo_song, 'piano:' .. cfg.pianissimo_target .. ':' .. cfg.pianissimo_song)
end

function B.brd_cast_piano()
    local cfg = S.profile.support.brd
    if cfg.pianissimo_target == '' or cfg.pianissimo_song == '' then return false end
    local slot = B.member_slot(cfg.pianissimo_target)
    if slot == nil then return false end
    local key = 'piano:' .. cfg.pianissimo_target .. ':' .. cfg.pianissimo_song
    if not brd_song_due(cfg.pianissimo_song, key) then return false end
    local pending = R.brd.piano_pending
    if pending then
        if pending.key == key and cast_song(pending.song, pending.slot) then
            R.brd.sung[key] = clock()
            R.brd.piano_pending = nil
            return true
        end
        R.brd.piano_pending = nil
    end
    if use_self_ability('Pianissimo') then
        R.brd.piano_pending = { key = key, song = cfg.pianissimo_song, slot = slot }
        return true
    end
    return false
end

local function brd_cast_camp(camp)
    for _, song in ipairs(B.brd_group_songs(camp)) do
        if brd_song_due(song) then
            if cast_song(song, 0) then
                R.brd.sung[song] = clock()
                return true
            end
            R.brd.sung[song] = clock()  -- unknown or on recast: do not spin on it
        end
    end
    return false
end

local function brd_maybe_nitro(camp)
    local cfg = S.profile.support.brd
    if cfg.nitro == 'off' then
        R.brd.nitro_step = nil
        return false
    end
    if camp == 'tank' and cfg.nitro == 'support' then return false end
    if camp == 'support' and cfg.nitro == 'tank' then return false end
    local now = clock()
    if R.brd.nitro_step == 'done' then
        if now < (R.brd.nitro_at or 0) + 590 then return false end
        R.brd.nitro_step = nil
    end
    -- The 590 s gate only spaces out completed cycles; an in-progress Nightingale/Troubadour
    -- sequence must be allowed to finish even if the client's clock started recently.
    if R.brd.nitro_step ~= 'night' and R.brd.nitro_step ~= 'troub'
        and now < (R.brd.nitro_at or 0) + 590 then return false end
    local night = B.ability_remaining('Nightingale')
    local troub = B.ability_remaining('Troubadour')
    if R.brd.nitro_step == 'night' then
        -- Nightingale was issued.  Wait for the client to put it on its recast table (the
        -- ability actually fired), then use Troubadour.  The timeout keeps a rejected command
        -- from blocking the song set forever.
        if (night ~= nil and night > 0.05) or now - (R.brd.nitro_issued_at or 0) >= 3 then
            if use_self_ability('Troubadour') then
                R.brd.nitro_step = 'troub'
                R.brd.nitro_issued_at = now
            end
        end
        return true
    end
    if R.brd.nitro_step == 'troub' then
        if (troub ~= nil and troub > 0.05) or now - (R.brd.nitro_issued_at or 0) >= 3 then
            R.brd.nitro_step = 'done'
            R.brd.nitro_at = now
            return false
        end
        return true
    end
    -- Wait until *both* are actually ready before starting, so a set is never sung with only
    -- one half of Nitro.  Songs still refresh normally while the pair is down.
    if night == nil or troub == nil or night > 0.05 or troub > 0.05 then return false end
    if use_self_ability('Nightingale') then
        R.brd.nitro_step = 'night'
        R.brd.nitro_issued_at = now
        return true
    end
    return false
end

local function brd_tick(me)
    local cfg = S.profile.support.brd
    if not cfg.enabled then return false end
    local tank = B.camp_pos('tank')
    local support = B.camp_pos('support')
    if not tank then return false end
    local same_group = B.brd_group_name('tank') == B.brd_group_name('support')
    local support_distinct = support and not S.profile.camp.mobile
        and distance(support, tank) > 2 and not same_group
    local support_due = support_distinct and brd_camp_due('support')
    local tank_due = brd_camp_due('tank')
    local piano_due = B.brd_piano_due()
    if not support_due and not tank_due and not piano_due then
        B.return_to_camp('support')
        return true
    end
    local phase = R.brd.phase or 'support'
    if not support_distinct then phase = 'tank' end
    if support_due and not tank_due then phase = 'support' end
    if tank_due and not support_due then phase = 'tank' end
    if support_due and tank_due and cfg.nitro ~= 'off' then phase = 'tank' end
    local camp = phase == 'support' and support or tank
    if not camp then return false end
    local at = distance(me, camp) <= math.max(1.5, B.camp_radius(phase) * 0.55)
    if not at then
        B.move_to(camp, math.max(0.8, B.camp_radius(phase) * 0.45))
        return true
    end
    B.stop_move()
    if (support_due or tank_due) and brd_maybe_nitro(phase) then return true end
    if brd_cast_camp(phase) then return true end
    if B.brd_cast_piano() then return true end
    if phase == 'support' and tank_due then
        R.brd.phase = 'tank'
        return true
    end
    if phase == 'tank' and support_due then
        R.brd.phase = 'support'
        return true
    end
    B.return_to_camp('support')
    return true
end

function B.support_ability_tick()
    local now = clock()
    for _, row in ipairs(S.profile.support.abilities or {}) do
        if row.enabled and row.name ~= '' then
            local key = row.name:lower()
            -- Nitro has its own sequence on the Buffs page.  A stale "Keep Nightingale" or
            -- "Keep Troubadour" row from an older profile must not use either half on its own.
            if key ~= 'nightingale' and key ~= 'troubadour' then
                local interval = tonumber(row.interval) or 300
                if now >= (R.support_last[key] or 0) + interval then
                    if use_self_ability(row.name) then
                        R.support_last[key] = now
                        return true
                    end
                end
            end
        end
    end
    return false
end

function B.support_tick(role)
    if role ~= 'support' then return false end
    if B.is_casting() or clock() < (R.busy_until or 0) then return true end
    if B.support_ability_tick() then return true end
    local job = self_job()
    local me = B.self_pos()
    if not me then return false end
    if job == 21 then return geo_tick(me) end
    if job == 10 then return brd_tick(me) end
    return false
end

-------------------------------------------------------------------------------- pulling

local function claimed_near_camp(except_index, kind)
    local camp = B.camp_pos(kind)
    local radius = (tonumber(S.profile.camp.radius) or 10) + 6
    local out = 0
    for _, mob in ipairs(mob_list(kind)) do
        if mob.claim and mob.index ~= except_index and (not camp or mob.dist_camp <= radius) then
            out = out + 1
        end
    end
    return out
end

function B.pull_tick(role)
    if role ~= 'puller' then return false end
    local p = S.profile.pull
    if not p.enabled then return false end
    local now = clock()
    local pull = R.pull
    local camp = B.camp_pos(B.camp_for_role('puller'))
    local me = B.self()
    if not camp or not me then return false end

    if pull.mob then
        local index = pull.mob
        if not entity_live(index) or (tonumber(S.game.entity(index, 'HPPercent')) or 0) <= 0 then
            pull.mob, pull.state, pull.tries = nil, 'idle', 0
        else
            local claim = claim_of(index)
            if claim then
                if pull.state ~= 'returning' then
                    pull.state = 'returning'
                    B.log_action('pull claimed; returning to camp')
                end
                B.return_to_camp()
                return true
            end
            if now - (pull.at or 0) > 8 then
                R.failed['mob:' .. tostring(tonumber(S.game.entity(index, 'ServerId')) or index)] = now + 12
                pull.mob, pull.state, pull.tries = nil, 'idle', 0
            elseif pull.state == 'melee' then
                local pos = position(index)
                if pos and B.self_pos() and distance(pos, B.self_pos()) <= 3.0 then
                    B.engage(index, 'puller')
                else
                    B.move_to(pos, 2.2)
                end
                return true
            end
            if B.is_casting() or clock() < (R.busy_until or 0) then return true end
            B.return_to_camp()
            return true
        end
    end

    if claimed_near_camp(nil, B.camp_for_role('puller')) >= (tonumber(p.max_mobs) or 3) then
        B.return_to_camp()
        return true
    end

    -- Crowd control: any extra claim that has reached the camp gets the configured sleep/bind,
    -- while the main target stays awake.  The client sees no monster buff list, so the sleep
    -- clock is our own and is also what keeps enfeebles off the sleeping mob.
    if p.sleep_extras and (p.sleep_spell ~= '' or p.bind_spell ~= '') and B.can_act() then
        local main = R.target_index
        for _, mob in ipairs(mob_list(B.camp_for_role('puller'))) do
            if mob.claim and mob.index ~= main
                and mob.dist_camp <= (tonumber(S.profile.camp.radius) or 10) + 1
                and clock() >= (R.sleep_until[mob.name] or 0) then
                local spell = p.sleep_spell ~= '' and p.sleep_spell or p.bind_spell
                B.set_target(mob.index)
                local slept = B.cast_on_enemy(spell, mob.index)
                if main and entity_live(main) then B.set_target(main) end
                if slept then
                    R.sleep_until[mob.name] = clock() + 45
                    B.log_action('sleep/bind ' .. mob.name)
                end
                break
            end
        end
    end

    local current = R.target_index
    local current_hpp = (current and entity_live(current)) and (tonumber(S.game.entity(current, 'HPPercent')) or 0) or 0
    local want_next = current == nil or current_hpp <= 0 or current_hpp <= (tonumber(p.at_hp) or 50)
    if not want_next then
        B.return_to_camp()
        return true
    end
    if B.is_casting() or clock() < (R.busy_until or 0) then return true end

    local best = nil
    for _, mob in ipairs(mob_list(B.camp_for_role('puller'))) do
        if not mob.claim and mob.dist_camp <= (tonumber(p.leash) or 28) and mob.dist_camp > 1.5 then
            if not best or mob.dist_camp < best.dist_camp then best = mob end
        end
    end
    if not best then
        B.return_to_camp()
        return true
    end

    if p.method == 'melee' then
        pull.mob, pull.state, pull.at = best.index, 'melee', now
        B.set_target(best.index)
        B.move_to(best.pos, 2.2)
        return true
    end

    B.set_target(best.index)
    local ok = false
    if p.method == 'ranged' then
        ok = issue('/ra <t>', 2.4, 'pull (ranged)')
    elseif p.method == 'spell' then
        ok = B.cast_on_enemy(p.spell ~= '' and p.spell or 'Dia', best.index)
    elseif p.method == 'ability' then
        ok = B.use_ability(p.ability, best.index)
    end
    if ok then
        pull.mob, pull.state, pull.at, pull.tries = best.index, 'pulling', clock(), 0
    else
        R.failed['mob:' .. tostring(best.id)] = clock() + 8
    end
    return true
end

-------------------------------------------------------------------------------- formation and combat movement

local function tank_pos()
    local name = S.profile.roster.tank
    local index = name ~= '' and entity_by_name(name) or nil
    if index and entity_live(index) then
        local pos = position(index)
        if pos then return pos, index end
    end
    return nil
end

local function behind_vector(anchor_pos)
    local tank = tank_pos()
    local mob = anchor_pos
    if tank and mob then
        local dx, dy = tank.x - mob.x, tank.y - mob.y
        local span = math.sqrt(dx * dx + dy * dy)
        if span > 0.05 then return -dx / span, -dy / span end
    end
    local heading = mob and tonumber(mob.heading) or 0
    return -math.sin(heading or 0), -math.cos(heading or 0)
end

-- One melee slot from the mob->tank line.  `bx,by` is the unit vector from the mob away from the
-- tank ("behind"); the same numbers drive the live world markers and the hub's diagram.
function B.formation_slot_from(mob, bx, by, slot, total)
    local p = S.profile.formation
    total = math.max(1, tonumber(total) or 1)
    local base = math.atan2(by, bx)
    if p.side == 'left' then
        base = base - math.rad(32)
    elseif p.side == 'right' then
        base = base + math.rad(32)
    end
    if p.style == 'side' then
        base = base + (slot % 2 == 0 and 1 or -1) * math.pi / 2
    end
    local spread = math.rad(p.arc or 180)
    if p.style == 'behind' then spread = math.min(spread, math.rad(70)) end
    local offset = 0
    if total > 1 then offset = (slot - (total + 1) / 2) * (spread / math.max(1, total - 1)) end
    local angle = base + offset
    local spacing = tonumber(p.spacing) or 2.4
    return { x = mob.x + math.cos(angle) * spacing, y = mob.y + math.sin(angle) * spacing,
        z = mob.z, angle = angle }
end

-- The melee formation spreads the *online* melee around the arc.  A saved roster can name
-- three boxes that are logged out; counting them would push the one online melee to an edge
-- slot meant for a full party.
function B.melee_slot()
    local names = B.roster_online('melee')
    local me = self_name()
    for slot, name in ipairs(names) do
        if name == me then return slot, #names end
    end
    return 1, math.max(1, #names)
end

function B.formation_point(index)
    local mob = position(index)
    if not mob then return nil end
    local slot, total = B.melee_slot()
    if S.profile.formation.follow_tank then
        local tank = tank_pos()
        if tank then
            local dx, dy = mob.x - tank.x, mob.y - tank.y
            local span = math.sqrt(dx * dx + dy * dy)
            if span > 0.05 then dx, dy = dx / span, dy / span
            else dx, dy = -math.sin(tank.heading or 0), -math.cos(tank.heading or 0) end
            return B.formation_slot_from(tank, dx, dy, slot, total)
        end
    end
    local bx, by = behind_vector(mob)
    return B.formation_slot_from(mob, bx, by, slot, total)
end

local function maintain_formation(role)
    local index = R.target_index
    if not index or not B.target_valid() then return false end
    if S.profile.formation.enabled and role == 'melee' then
        local point = B.formation_point(index)
        if point then
            B.move_to(point, 0.7)
            return true
        end
    end
    if role == 'tank' then
        local pos = position(index)
        if pos then
            local mine = B.self_pos()
            if mine and distance(pos, mine) > 2.2 then B.move_to(pos, 2.0) else B.stop_move() end
            return true
        end
    end
    return false
end

function B.ranged_position()
    local index = R.target_index
    if not index or not B.target_valid() then return false end
    local mob = position(index)
    local camp = B.camp_pos(B.camp_for_role(B.self_role()))
    local me = B.self_pos()
    if not mob or not me then return false end
    local span = camp and distance(mob, camp) or distance(mob, me)
    if span <= 20 then
        B.return_to_camp()
        return true
    end
    B.move_to(mob, 18)
    return true
end

function B.kite_tick(role)
    if role ~= 'kiter' then return false end
    local p = S.profile.kiting
    if not p.enabled then return false end
    local me = B.self_pos()
    local camp = B.camp_pos()
    if not me then return false end
    if not B.target_valid() then
        B.return_to_camp()
        return true
    end
    local mob = position(R.target_index)
    local hpp = B.target_hpp()
    if mob and hpp > 0 and me.hpp > p.below then
        B.return_to_camp()
        return true
    end
    if not camp then return false end
    local now = clock()
    if p.mode == 'camp' then
        B.return_to_camp()
        return true
    end
    if p.mode == 'circle' then
        local dx, dy = me.x - camp.x, me.y - camp.y
        if not R.kite.angle then R.kite.angle = math.atan2(dy, dx) end
        if mob then
            local mdx, mdy = mob.x - me.x, mob.y - me.y
            local gap = math.sqrt(mdx * mdx + mdy * mdy)
            if gap < 7 then
                local cross = mdx * (-math.sin(R.kite.angle)) + mdy * math.cos(R.kite.angle)
                R.kite.dir = cross > 0 and -1 or 1
            end
        end
        if now >= (R.kite.at or 0) then
            R.kite.at = now + 0.25
            R.kite.angle = R.kite.angle + 0.20 * (R.kite.dir or 1)
        end
        local radius = tonumber(p.radius) or 18
        local point = { x = camp.x + math.cos(R.kite.angle) * radius,
            y = camp.y + math.sin(R.kite.angle) * radius, z = me.z }
        B.move_to(point, 1.0)
        return true
    end
    if p.mode == 'away' and mob then
        local dx, dy = me.x - mob.x, me.y - mob.y
        local span = math.sqrt(dx * dx + dy * dy)
        if span > 0.01 then
            local point = { x = me.x + dx / span * 8, y = me.y + dy / span * 8, z = me.z }
            B.move_to(point, 0.5)
            return true
        end
    end
    B.return_to_camp()
    return true
end

-------------------------------------------------------------------------------- death

function B.is_dead()
    local me = B.self()
    if not me then return false end
    return me.hpp <= 0 and me.hp <= 0
end

function B.death_tick()
    local now = clock()
    local dead = B.is_dead()
    if dead and not R.dead then
        R.dead, R.dead_at, R.home_sent = true, now, false
        B.stop_move()
        B.disengage()
        note('action', 'Battle: you are down; waiting for the raise or the Home Point.')
    elseif not dead and R.dead then
        R.dead, R.revived_at = false, now
        R.busy_until = now + 1.5
        note('action', 'Battle: back on your feet; resuming.')
    end
    if R.dead then
        if S.profile.death.mode == 'homepoint' and not R.home_sent and now - R.dead_at >= 1.0 then
            R.home_sent = true
            pcall(xi.chat.run, '//hp ' .. tostring(S.profile.death.home_point or 1), 1)
            B.log_action('home point')
        end
        return true
    end
    return false
end

-------------------------------------------------------------------------------- the main tick

local function combat_tick(role)
    if role == 'support' then
        B.return_to_camp(role)
        return
    end
    if role == 'kiter' and B.kite_tick(role) then return end

    if not B.target_valid() then
        local index = nil
        if role == 'puller' then
            -- Pulling off: the puller falls back to an ordinary claimed-target melee.
            if not S.profile.pull.enabled then index = pick_mob(role, false) end
        elseif role == 'tank' then
            index = pick_mob(role, not S.profile.pull.enabled)
        else
            index = pick_mob(role, false)
        end
        if index then B.set_target(index) end
    end

    if B.target_valid() then
        local hpp = B.target_hpp()
        local index = R.target_index
        local member = B.target_member()
        local allowed = role == 'tank' or role == 'puller' or claim_allowed({ claim = member }, role)
        if hpp <= 0 then
            B.clear_target()
        elseif not allowed then
            B.return_to_camp()
        else
            local style = B.combat_style_for(role)
            if style == 'ranged' then
                B.engage(index, 'ranged')
                B.ranged_position()
            else
                if B.can_act() then
                    if not B.use_weaponskill() then B.engage(index, 'melee') end
                end
                maintain_formation('melee')
            end
        end
        return
    end

    if role == 'puller' then
        B.return_to_camp()
    elseif role == 'kiter' and S.profile.kiting.enabled then
        B.kite_tick(role)
    else
        B.return_to_camp(role)
    end
end

function B.tick()
    if not S.installed then return end
    local now = clock()
    if now < (S.next_tick or 0) then return end
    S.next_tick = now + TICK
    if not S.game or (S.game.player_index() or -1) < 0 then
        B.stop_move()
        return
    end
    local okz, zoning = pcall(function() return S.game.player('IsZoning') end)
    if okz and zoning and tonumber(zoning) ~= 0 then
        B.stop_move()
        return
    end
    local zone = math.floor(tonumber(S.game.party_member(0, 'Zone')) or 0)
    if S.last_zone ~= zone then
        G.axis_value, G.matrix, G.cache_until = nil, nil, 0
        S.last_zone = zone
        B.stop_move()
    end
    local character = character_info()
    if character and character ~= S.character then
        if S.character then
            S.running = false
            B.stop_move()
        end
        S.character = nil
        S.profile = nil
        C.resume()
        S.visible = S.profile and S.profile.ui.show == true
    end
    if not S.profile then C.resume() end
    B.team_poll()
    if not S.running then return end
    if B.death_tick() then return end

    local role = B.self_role()
    if not role then
        B.return_to_camp()
        return
    end
    if B.paused(role) then
        B.stop_move()
        return
    end

    for _, step in ipairs(S.profile.priority) do
        local done = false
        if step == 'heal' then done = B.heal_tick()
        elseif step == 'buff' then done = B.buff_tick()
        elseif step == 'enfeeble' then done = B.enfeeble_tick()
        elseif step == 'dispel' then done = B.dispel_tick() end
        if done then
            if role == 'puller' then B.return_to_camp() end
            return
        end
    end

    if role == 'puller' then B.pull_tick(role) end
    if role == 'support' and S.profile.roster.puller == self_name()
        and S.profile.pull.enabled and B.pull_tick('puller') then
        return
    end
    if role == 'support' and B.support_tick(role) then return end
    if B.is_casting() or now < (R.busy_until or 0) then return end
    combat_tick(role)
end

function B.start()
    if not S.profile then C.new_profile(nil) end
    local needs_camp = not (S.profile.camp.mobile or not S.profile.camp.tank_enabled)
    if needs_camp and not B.ensure_camp() then
        note('error', 'Battle: set a camp first (//battle camp set here).')
        return false, 'set a camp first'
    end
    reset_runtime()
    S.running = true
    S.visible = true
    S.profile.ui.show = true
    local role = B.self_role()
    if not role then
        note('error', 'Battle: this character is not assigned to a role; it will wait.')
    else
        note('action', 'Battle: started as ' .. ROLE_LABELS[role] .. '.')
    end
    return true
end

function B.stop()
    S.running = false
    B.stop_move()
    B.disengage()
    note('action', 'Battle: stopped; waiting for the next instruction.')
end

function B.toggle_pause(role)
    role = tostring(role or ''):lower()
    if not contains({ 'melee', 'ranged', 'tank', 'support' }, role) then
        return false, 'pause melee|ranged|tank|support'
    end
    S.profile.paused[role] = not S.profile.paused[role]
    return true, role .. (S.profile.paused[role] and ' paused' or ' resumed')
end

function B.status()
    local role = S.remote_edit and B.role_of(S.remote_edit.name) or B.self_role()
    local member = B.self()
    local target = nil
    if B.target_valid() then
        local claim = B.target_member()
        target = {
            name = S.game.entity(R.target_index, 'Name') or '?',
            hpp = B.target_hpp(),
            claimed_by = claim and claim.name or nil,
        }
    end
    local camp = S.profile and S.profile.camp
    local paused = {}
    for _, key in ipairs({ 'melee', 'ranged', 'tank', 'support' }) do
        if S.profile.paused[key] then paused[#paused + 1] = key end
    end
    return {
        running = S.running,
        visible = S.visible,
        role = role,
        role_label = role and ROLE_LABELS[role] or nil,
        paused = paused,
        dead = R.dead,
        busy = clock() < (R.busy_until or 0) or B.is_casting(),
        camp = camp and camp.set and {
            x = camp.x, y = camp.y, z = camp.z, radius = camp.radius, show = camp.show,
        } or nil,
        support_camp = S.profile.support_camp.set and {
            x = S.profile.support_camp.x, y = S.profile.support_camp.y,
            z = S.profile.support_camp.z, radius = S.profile.support_camp.radius,
            show = S.profile.support_camp.show,
        } or nil,
        in_camp = B.inside_camp(member and B.self_pos() or nil, 0),
        in_support_camp = B.inside_camp(member and B.self_pos() or nil, 0, 'support'),
        target = target,
        last_action = R.last_action,
        last_action_at = R.last_action_at,
        name = S.profile and S.profile.name or nil,
        role_names = S.profile and S.profile.roster or nil,
        members = (function()
            local out = {}
            for _, member in ipairs(B.members('alliance')) do
                out[#out + 1] = { slot = member.slot, name = member.name, job = member.job,
                    level = member.level, sub = member.sub, sub_level = member.sub_level,
                    hpp = member.hpp, mpp = member.mpp, zone = member.zone }
            end
            return out
        end)(),
        notes = S.notes,
        projection = G.available(),
        skillchain = S.profile and B.skillchain_plan() or nil,
        mobs = (function()
            local out = {}
            for _, mob in ipairs(B.mobs()) do
                out[#out + 1] = {
                    name = mob.name,
                    hpp = mob.hpp,
                    distance = math.floor((mob.dist_camp or 999) + 0.5),
                    claimed = mob.claim and mob.claim.name or nil,
                }
            end
            table.sort(out, function(a, b)
                if a.distance == b.distance then return a.name < b.name end
                return a.distance < b.distance
            end)
            return out
        end)(),
    }
end

-------------------------------------------------------------------------------- suggestions

local JOB_ABBR = {
    [0] = 'NON', 'WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK', 'BST', 'BRD',
    'RNG', 'SAM', 'NIN', 'DRG', 'SMN', 'BLU', 'COR', 'PUP', 'DNC', 'SCH', 'GEO', 'RUN',
}

local BUFF_SUGGEST = {
    'Protect', 'Shell', 'Haste', 'Regen', 'Refresh', 'Phalanx', 'Stoneskin',
    'Aquaveil', 'Blink', 'Reraise', 'Utsusemi: Ichi', 'Utsusemi: Ni',
    'Enfire', 'Enblizzard', 'Enaero', 'Enstone', 'Enthunder', 'Enwater',
    'Enfire II', 'Enblizzard II', 'Enaero II', 'Enstone II', 'Enthunder II', 'Enwater II',
    'Sneak', 'Invisible', 'Deodorize',
}

local function tenant_entry()
    if S.remote_edit and S.team then
        for _, character in ipairs(S.team) do
            if character.name == S.remote_edit.name then return character end
        end
    end
    local me = B.self()
    if not me then return nil end
    if S.team then
        for _, character in ipairs(S.team) do
            if character.name == me.name and type(character.profile) == 'table' then return character end
        end
    end
    return {
        name = me.name, main_job = me.job, sub_job = me.sub,
        main_level = me.level,
        sub_level = tonumber(S.game.party_member(0, 'SubJobLevel')) or 0,
    }
end

local function tenant_name()
    local entry = tenant_entry()
    return entry and entry.name or ''
end

local function tenant_job()
    local entry = tenant_entry()
    return tonumber(entry and entry.main_job) or 0
end

local function tenant_level()
    local entry = tenant_entry()
    return tonumber(entry and entry.main_level) or 0
end

local function tenant_label()
    local entry = tenant_entry()
    if not entry then return 'this character' end
    return string.format('%s %s %d', entry.name or '?', JOB_ABBR[tonumber(entry.main_job) or 0] or '???',
        tonumber(entry.main_level) or 0)
end

function B.tenant_songs()
    local entry = tenant_entry()
    return type(entry and entry.songs) == 'table' and entry.songs or {}
end

function B.tenant_song_bonus()
    local entry = tenant_entry()
    return tonumber(entry and entry.song_duration_bonus) or 0
end

local function song_key(name)
    return tostring(name or ''):lower():gsub("[^%a0-9]", "")
end

function B.song_duration(name)
    local key = song_key(name)
    for _, song in ipairs(B.tenant_songs()) do
        if song_key(song.name) == key then
            return tonumber(song.duration) or 120
        end
    end
    return 120
end

function B.song_duration_text(name)
    local seconds = B.song_duration(name)
    return string.format('%d:%02d', math.floor(seconds / 60), math.floor(seconds % 60))
end

function B.tenant_song_names()
    local out = {}
    for _, song in ipairs(B.tenant_songs()) do
        if song.name and song.name ~= '' then out[#out + 1] = song.name end
    end
    return out
end

-- Lists on the hub follow the live party/alliance, not the account family.  A shared roster
-- can name six characters while only three clients are logged in; the absent ones keep their
-- role in the profile but do not appear in pickers or exclusion lists.
local function tenant_members()
    return B.members('alliance')
end

local function roster_names()
    local out = {}
    for _, member in ipairs(B.members('alliance')) do out[#out + 1] = member.name end
    return out
end

local function job_spells(job, level)
    job, level = tonumber(job) or 0, tonumber(level) or 0
    if job <= 0 or level <= 0 then return {} end
    S.spell_cache = S.spell_cache or {}
    local key = tostring(job) .. ':' .. tostring(level)
    if S.spell_cache[key] then return S.spell_cache[key] end
    local out = {}
    local ok, ids = pcall(S.res.spell_ids)
    if ok and type(ids) == 'table' then
        for _, raw in ipairs(ids) do
            local id = tonumber(raw) or 0
            local ok2, spell = pcall(S.res.spell, id)
            if ok2 and spell then
                local levels = spell.levels
                local needed = type(levels) == 'table' and tonumber(levels[job]) or nil
                if needed and needed > 0 and needed <= level then out[#out + 1] = spell end
                if #out >= 900 then break end
            end
        end
    end
    S.spell_cache[key] = out
    return out
end

local function known_spells()
    local entry = tenant_entry()
    if not entry then return {} end
    local out, seen = {}, {}
    local jobs = {
        { tonumber(entry.main_job) or 0, tonumber(entry.main_level) or 0 },
        { tonumber(entry.sub_job) or 0, tonumber(entry.sub_level) or 0 },
    }
    for _, pair in ipairs(jobs) do
        for _, spell in ipairs(job_spells(pair[1], pair[2])) do
            local name = spell_name(spell)
            if name ~= '' and not seen[name:lower()]
                and (S.remote_edit or spell_known(spell)) then
                seen[name:lower()] = true
                out[#out + 1] = spell
            end
        end
    end
    return out
end

function B.brd_song_choices()
    local known, out, seen = {}, {}, {}
    local trust = {
        ['cactuar fugue'] = true, ['chocobo hum'] = true, ['jesters operetta'] = true,
        ['devotee serenade'] = true, ['moogle rhapsody'] = true, ['protected aria'] = true,
    }
    for _, spell in ipairs(known_spells()) do
        local skill = tonumber(spell.skill) or 0
        local name = spell_name(spell)
        if (skill == 40 or skill == 41 or skill == 42) and name ~= ''
            and not trust[name:lower()] and not seen[name:lower()] then
            seen[name:lower()] = true
            known[name:lower()] = name
            out[#out + 1] = name
        end
    end
    local catalog = {}
    for _, name in ipairs(B.tenant_song_names()) do
        if known[name:lower()] then catalog[#catalog + 1] = name end
    end
    if #catalog > 0 then return catalog end
    return out
end

known_abilities = function()
    if S.remote_edit then
        local entry = tenant_entry()
        local out, seen = {}, {}
        for _, ability in ipairs(entry and entry.abilities or {}) do
            local name = type(ability) == 'table' and ability.name or tostring(ability)
            if name and name ~= '' and not seen[name:lower()] then
                seen[name:lower()] = true
                out[#out + 1] = name
            end
        end
        return out
    end
    local out = {}
    local ok, ids = pcall(S.game.ability_commands)
    if not ok or type(ids) ~= 'table' then return out end
    for _, raw in ipairs(ids) do
        local id = tonumber(raw) or 0
        if id >= 0x200 and id < 0x400 then
            local ok2, ability = pcall(S.res.ability, id)
            if ok2 and type(ability) == 'table' then
                local name = ability.name
                if type(name) == 'table' then name = name.en or name[2] or name[1] end
                if type(name) == 'string' and name ~= '' then out[#out + 1] = name end
            end
        end
    end
    return out
end

local BUFF_MAGIC_SKILL = { [34] = true, [40] = true, [43] = true, [44] = true }
local function buff_options()
    local seen, out = {}, {}
    for _, spell in ipairs(known_spells()) do
        local name = spell_name(spell)
        local skill = tonumber(spell.skill) or 0
        local targets = tonumber(spell.targets) or tonumber(spell.valid_targets) or 0
        local lower = name:lower()
        local suggested = false
        for _, want in ipairs(BUFF_SUGGEST) do
            local base = want:lower():gsub('%s+[ivx]+$', '')
            if lower == want:lower() or lower:gsub('%s+[ivx]+$', '') == base then suggested = true break end
        end
        local enemy_only = targets == 4 or targets == 8 or targets == 32
        if name ~= '' and (BUFF_MAGIC_SKILL[skill] or suggested)
            and (not enemy_only or suggested) and not seen[lower] then
            seen[lower] = true
            out[#out + 1] = { name = name, kind = 'spell' }
        end
    end
    for _, name in ipairs(known_abilities()) do
        local lower = name:lower()
        if not seen[lower] then
            seen[lower] = true
            out[#out + 1] = { name = name, kind = 'ability' }
        end
    end
    table.sort(out, function(a, b) return a.name:lower() < b.name:lower() end)
    return out
end

local function spell_level(spell)
    local job, level
    if S.remote_edit then
        job, level = tenant_job(), tenant_level()
    else
        job = tonumber(S.game.party_member(0, 'MainJob')) or 0
        level = tonumber(S.game.party_member(0, 'MainJobLevel')) or 0
    end
    local levels = spell.levels
    if type(levels) == 'table' and job > 0 then
        local needed = tonumber(levels[job]) or 0
        if needed > 0 and needed <= level then return needed end
    end
    return 0
end

local function add_unique(list, value, field)
    field = field or 'spell'
    for _, row in ipairs(list) do
        if row[field]:lower() == value:lower() then return false end
    end
    return true
end

function C.suggest(scope)
    if not S.profile then return 0 end
    local spells = known_spells()
    local changed = 0
    local main_job = S.remote_edit and tenant_job() or tonumber(S.game.party_member(0, 'MainJob')) or 0
    local main_level = S.remote_edit and tenant_level() or tonumber(S.game.party_member(0, 'MainJobLevel')) or 0
    if scope == 'heal' or scope == 'all' then
        local cures = {}
        for _, spell in ipairs(spells) do
            local name = spell_name(spell):lower()
            local skill = tonumber(spell.skill) or 0
            if skill == 33 and (name == 'cure' or name:match('^cure%s+[ivx]+$')) then
                cures[#cures + 1] = spell
            end
        end
        table.sort(cures, function(a, b) return spell_level(a) > spell_level(b) end)
        local thresholds = { 30, 45, 60, 75, 90 }
        local rows = {}
        for index, spell in ipairs(cures) do
            if index > #thresholds then break end
            rows[#rows + 1] = {
                id = row_id(), spell = spell_name(spell), below = thresholds[index],
            }
        end
        if #rows > 0 then
            S.profile.heal.cures = rows
            changed = changed + #rows
        end
        -- A BRD/DNC has no Cure spells at all; detect the sub job's waltzes and turn the
        -- fallback on with the same Suggest button.
        if #B.detected_waltzes() > 0 then
            S.profile.heal.waltz = true
            S.profile.heal.waltz_status = true
            changed = changed + 2
        end
        -- The -na list comes from the same known-spell table: the engine already maps status
        -- ids to these names, so there is nothing else to configure.
        if S.profile.heal.raise_spell == '' then
            for _, name in ipairs({ 'Raise', 'Raise II', 'Arise', 'Reraise' }) do
                local spell = B.spell(name)
                if spell then S.profile.heal.raise_spell = spell_name(spell) break end
            end
        end
    end
    if scope == 'buff' or scope == 'all' then
        local rows = S.profile.buffs.rows
        local best = {}
        for _, want in ipairs(BUFF_SUGGEST) do
            local wanted = want:lower():gsub('%s+[ivx]+$', '')
            for _, spell in ipairs(spells) do
                local name = spell_name(spell)
                local lower = name:lower()
                local base = lower:gsub('%s+[ivx]+$', '')
                if (base == wanted or lower == want:lower())
                    and (not best[wanted] or spell_level(spell) >= spell_level(best[wanted])) then
                    best[wanted] = spell
                end
            end
        end
        for _, spell in pairs(best) do
            local name = spell_name(spell)
            if add_unique(rows, name) then
                local scope_name = 'self'
                local lower = name:lower()
                if lower:sub(-2) == 'ra' or lower:find('^protect') or lower:find('^shell')
                    or lower:find('^haste') or lower:find('^regen') then
                    scope_name = 'party'
                end
                rows[#rows + 1] = { id = row_id(), spell = name, target = scope_name, interval = 300 }
                changed = changed + 1
            end
        end
    end
    if scope == 'enfeeble' or scope == 'all' then
        local rows = S.profile.enfeebles.rows
        local candidates = {}
        for _, spell in ipairs(spells) do
            local skill = tonumber(spell.skill) or 0
            local magic = tonumber(spell.type) or 0
            local name = spell_name(spell)
            local lower = name:lower()
            local kind = (magic == 1 or magic == 2) and (skill == 35)
                or (magic == 4 and (lower:find('^hojo') or lower:find('^kurayami')
                    or lower:find('^dokumori') or lower:find('^jubaku')))
            local skip = lower:find('^sleep') or lower:find('^bind') or lower:find('^break')
                or lower:find('^stun') or lower:find('^repose') or lower:find('^lullaby')
            if kind and lower ~= 'dispel' and lower ~= 'erase' and not skip then
                candidates[#candidates + 1] = spell
            end
        end
        table.sort(candidates, function(a, b) return spell_level(a) < spell_level(b) end)
        for _, spell in ipairs(candidates) do
            local name = spell_name(spell)
            if add_unique(rows, name) and #rows < MAX_ROWS then
                rows[#rows + 1] = { id = row_id(), spell = name, interval = 120 }
                changed = changed + 1
            end
        end
        if S.profile.dispel.spell == '' then
            local dispel = B.spell('Dispel')
            if dispel then S.profile.dispel.spell = spell_name(dispel) end
        end
    end
    if changed > 0 then
        S.dirty = true
        S.buffers = {}
        note('info', 'Battle: suggested ' .. tostring(changed) .. ' ' .. scope .. ' setting(s) from the current job.')
    end
    return changed
end

-------------------------------------------------------------------------------- chat command

local function show_hub(value)
    if not value and S.remote_edit then B.team_restore() end
    S.visible = value and true or false
    if S.profile then S.profile.ui.show = S.visible end
    if S.visible and S.profile then
        S.ui.x, S.ui.y = S.profile.ui.x or S.ui.x, S.profile.ui.y or S.ui.y
        S.ui.opacity = S.profile.ui.opacity or S.ui.opacity
        S.ui.force = true
        S.team_poll_at = 0
        pcall(B.team_poll)
    end
end

local function assign_role(role, names)
    local p = S.profile
    if role == 'support' or role == 'melee' or role == 'ranged' then
        local list = {}
        for _, name in ipairs(names) do
            name = text(name, 32)
            if name ~= '' and not contains(list, name) then
                -- A character has one job in the battle; remove it from every other list.
                for _, key in ipairs({ 'tank', 'puller', 'kiter' }) do
                    if p.roster[key] == name then p.roster[key] = '' end
                end
                for _, key in ipairs({ 'support', 'melee', 'ranged' }) do
                    if key ~= role then remove_value(p.roster[key], name) end
                end
                list[#list + 1] = name
            end
        end
        p.roster[role] = list
        return true
    end
    if role == 'tank' or role == 'puller' or role == 'kiter' then
        local name = text(names[1], 32)
        if name == '' then return false, 'name?' end
        for _, key in ipairs({ 'tank', 'puller', 'kiter' }) do
            if key ~= role and p.roster[key] == name then p.roster[key] = '' end
        end
        for _, key in ipairs({ 'support', 'melee', 'ranged' }) do remove_value(p.roster[key], name) end
        p.roster[role] = name
        return true
    end
    return false, 'assign tank|puller|kiter|support|melee|ranged'
end

local function place_start(kind)
    if not S.profile then C.new_profile(nil) end
    kind = kind == 'support' and 'support' or 'tank'
    local pos = B.self_pos()
    if not pos then note('error', 'Battle: not in the world yet.'); return false end
    local camp = kind == 'support' and S.profile.support_camp or S.profile.camp
    S.place = {
        kind = kind,
        x = camp.set and camp.x or pos.x,
        y = camp.set and camp.y or pos.y,
        z = camp.set and camp.z or pos.z,
        ground_z = pos.z,
        radius = tonumber(camp.radius) or 10,
        from_mouse = false,
        manual_at = 0,
        started = clock(),
    }
    S.visible = true
    S.tab = 'camp'
    note('info', string.format('Battle: aim the %s camp with the mouse (or arrow keys), Enter drops it, Escape cancels.', kind))
    return true
end

local function place_commit()
    if not S.place then return false end
    local kind = S.place.kind == 'support' and 'support' or 'tank'
    local camp = kind == 'support' and S.profile.support_camp or S.profile.camp
    camp.set, camp.x, camp.y, camp.z = true, S.place.x, S.place.y, S.place.z
    camp.radius = S.place.radius
    S.place = nil
    S.dirty = true
    note('action', string.format('Battle: %s camp set to %.1f, %.1f at %.0f yalms.',
        kind, camp.x, camp.y, camp.radius))
    return true
end

local function place_cancel()
    S.place = nil
    note('info', 'Battle: camp placement cancelled.')
end

local function help()
    local lines = {
        '//battle [toggle|show|hide] - the Battle hub',
        '//battle assign tank|puller|kiter <name>',
        '//battle assign support|melee|ranged <name> <name> ...',
        '//battle engage when <name> | tank | puller | leader | always | none',
        '//battle camp [tank|support] set here|there | camp [tank|support] radius <n> | camp clear',
        '//battle rally | invite | import',
        '//battle save [name] | new [name] | load <name> | list | delete <name>',
        '//battle start | stop | pause melee|ranged|tank|support',
        '//battle heal|buff|enfeeble|dispel|pull|formation|kite on|off',
        '//battle cure add <spell> <hp%> | cure remove <spell>',
        '//battle buff add <spell> [self|party|alliance] [seconds] | buff remove <spell>',
        '//battle enfeeble add <spell> [seconds] | enfeeble remove <spell>',
        '//battle dispel add <spell> [seconds] | dispel off',
        '//battle ws <weaponskill|off> | death raise|homepoint [wait]',
        '//battle suggest heal|buff|enfeeble|all | status',
        '//battle pull mob add|remove <name> | pull distance <n>',
        '//battle skillchain on|off | skillchain focus <chain>',
    }
    for _, line in ipairs(lines) do note('info', line) end
end

function M.command(rest)
    if not S.installed then return false end
    if not S.profile then C.resume() end
    local words = split_words(rest or '')
    local first = (words[1] or 'toggle'):lower()
    local p = S.profile
    if first == 'toggle' then
        show_hub(not S.visible)
    elseif first == 'show' or first == 'on' then
        show_hub(true)
    elseif first == 'hide' or first == 'off' then
        show_hub(false)
    elseif first == 'assign' then
        local role = (words[2] or ''):lower()
        local names = {}
        for index = 3, #words do names[#names + 1] = words[index] end
        local ok, err = assign_role(role, names)
        if not ok then note('error', 'Battle: ' .. tostring(err)); return false end
        S.dirty = true
        note('action', 'Battle: ' .. role .. ' = ' .. table.concat(names, ', '))
    elseif first == 'engage' then
        local second = (words[2] or ''):lower()
        if second == 'when' and words[3] then
            p.engage.mode = 'player'
            p.engage.player = text(words[3], 32)
        elseif contains(ENGAGE_MODES, second) then
            p.engage.mode = second
        else
            note('error', 'Battle: //battle engage when <name> | tank | puller | leader | always | none')
            return false
        end
        S.dirty = true
        note('action', 'Battle: engage mode ' .. p.engage.mode
            .. (p.engage.mode == 'player' and (' (' .. p.engage.player .. ')') or ''))
    elseif first == 'camp' then
        local second = (words[2] or ''):lower()
        local kind = 'tank'
        if second == 'tank' or second == 'support' then
            kind = second
            second = (words[3] or ''):lower()
        end
        local camp = kind == 'support' and p.support_camp or p.camp
        if second == 'set' then
            local third = (words[4] or words[3] or ''):lower()
            if third == 'here' or third == 'me' then
                local pos = B.self_pos()
                if not pos then note('error', 'Battle: not in the world yet.'); return false end
                camp.set, camp.x, camp.y, camp.z = true, pos.x, pos.y, pos.z
                S.dirty = true
                note('action', 'Battle: ' .. kind .. ' camp set here.')
            elseif third == 'there' then
                place_start(kind)
            else
                note('error', 'Battle: //battle camp [tank|support] set here|there')
            end
        elseif second == 'radius' then
            camp.radius = clamp(words[4] or words[3], 1, 50, camp.radius)
            if S.place and S.place.kind == kind then S.place.radius = camp.radius end
            S.dirty = true
            note('action', string.format('Battle: %s camp radius %.1f yalms.', kind, camp.radius))
        elseif second == 'clear' then
            camp.set = false
            S.dirty = true
            note('action', 'Battle: ' .. kind .. ' camp cleared.')
        elseif second == 'show' then
            camp.show = not camp.show
            S.dirty = true
        else
            note('error', 'Battle: //battle camp [tank|support] set here|there | camp [tank|support] radius <n> | camp [tank|support] clear')
        end
    elseif first == 'import' then
        B.import_party()
    elseif first == 'skillchain' then
        local second = (words[2] or 'toggle'):lower()
        if second == 'on' or second == 'off' or second == 'toggle' then
            p.skillchain.enabled = second ~= 'off'
            S.dirty = true
            note('action', 'Battle: skillchain planner ' .. (p.skillchain.enabled and 'on' or 'off'))
        elseif second == 'focus' then
            local wanted = text(table.concat(words, ' ', 3), 40)
            local target = nil
            for id = 1, 16 do
                if wanted ~= '' and (SC_NAMES[id]:lower() == wanted:lower()
                    or (SC_NAMES[id]:lower():find(wanted:lower(), 1, true) ~= nil)) then
                    target = id
                    break
                end
            end
            if target then
                p.skillchain.target = target
                S.dirty = true
                note('action', 'Battle: skillchain focus ' .. sc_name(target))
            else
                note('error', 'Battle: focus must be a skillchain name, e.g. Light, Darkness, Fragmentation.')
                return false
            end
        else
            note('error', 'Battle: //battle skillchain on|off | skillchain focus <chain>')
        end
    elseif first == 'rally' then
        local ok, err = pcall(xi.chat.run, '//warp all me', 1)
        if not ok then note('error', 'Battle: ' .. tostring(err)); return false end
        note('action', 'Battle: calling the team to this character (//warp all me).')
    elseif first == 'invite' then
        local ok, err = pcall(xi.chat.run, '//invite subs', 1)
        if not ok then note('error', 'Battle: ' .. tostring(err)); return false end
        note('action', 'Battle: inviting the online sub-accounts (//invite subs).')
    elseif first == 'save' then
        local name = text(table.concat(words, ' ', 2), 80)
        -- No name is the spec's default: a fresh <zone> <timestamp> profile, so a second save
        -- does not silently overwrite the first.  The hub's Save button keeps the current name.
        if name == '' then name = C.default_name() end
        local ok, err = C.save(name)
        if not ok then note('error', 'Battle: ' .. tostring(err)); return false end
        show_hub(false)
        note('action', 'Battle: saved "' .. S.profile.name .. '".')
    elseif first == 'new' then
        C.new_profile(text(table.concat(words, ' ', 2), 80))
        S.dirty = true
        show_hub(true)
    elseif first == 'load' then
        local name = text(table.concat(words, ' ', 2), 80)
        local ok, err = C.load(name)
        if not ok then note('error', 'Battle: ' .. tostring(err)); return false end
        show_hub(true)
    elseif first == 'list' then
        local list = C.list()
        if #list == 0 then note('info', 'Battle: no saved profiles for this character.')
        else
            for _, item in ipairs(list) do
                note('info', string.format('%s  (%s)', item.name, item.zone_name ~= '' and item.zone_name or ('zone ' .. item.zone)))
            end
        end
    elseif first == 'delete' then
        local ok, err = C.delete(text(table.concat(words, ' ', 2), 80))
        if not ok then note('error', 'Battle: ' .. tostring(err)); return false end
    elseif first == 'start' then
        local ok, err = B.start()
        if not ok then note('error', 'Battle: ' .. tostring(err)); return false end
        show_hub(true)
    elseif first == 'stop' then
        B.stop()
    elseif first == 'pause' then
        local roles = {}
        for index = 2, #words do
            for role in words[index]:lower():gmatch('[^,]+') do roles[#roles + 1] = role end
        end
        if #roles == 0 then
            note('error', 'Battle: pause melee|ranged|tank|support')
            return false
        end
        for _, role in ipairs(roles) do
            local ok, err = B.toggle_pause(role)
            if not ok then note('error', 'Battle: ' .. tostring(err)) else note('action', 'Battle: ' .. err) end
        end
        S.dirty = true
    elseif first == 'status' then
        local status = B.status()
        note('info', string.format('Battle: %s as %s; camp %s; target %s; %s',
            status.running and 'running' or 'stopped', status.role_label or 'unassigned',
            status.camp and string.format('%.1f, %.1f r%.0f', status.camp.x, status.camp.y, status.camp.radius) or 'none',
            status.target and (status.target.name .. ' ' .. status.target.hpp .. '%') or 'none',
            status.paused[1] and ('paused ' .. table.concat(status.paused, ',')) or 'no role paused'))
    elseif first == 'suggest' then
        C.suggest((words[2] or 'all'):lower())
    elseif first == 'pull' then
        local second = (words[2] or 'toggle'):lower()
        if second == 'mob' then
            local third = (words[3] or ''):lower()
            if third == 'add' then
                local name = text(table.concat(words, ' ', 4), 40)
                if name == '' then note('error', 'Battle: //battle pull mob add <name>'); return false end
                for _, selected in ipairs(p.pull.mobs) do
                    if selected:lower() == name:lower() then
                        note('info', 'Battle: ' .. name .. ' is already in the pull list.')
                        return true
                    end
                end
                if #p.pull.mobs >= 40 then note('error', 'Battle: the pull list is full (40).'); return false end
                p.pull.mobs[#p.pull.mobs + 1] = name
                S.dirty = true
                note('action', 'Battle: pull ' .. name .. '.')
            elseif third == 'remove' then
                local name = text(table.concat(words, ' ', 4), 40):lower()
                for index, selected in ipairs(p.pull.mobs) do
                    if selected:lower() == name then
                        table.remove(p.pull.mobs, index)
                        S.dirty = true
                        note('action', 'Battle: no longer pulling ' .. name .. '.')
                        return true
                    end
                end
                note('info', 'Battle: ' .. name .. ' is not in the pull list.')
            elseif third == 'clear' then
                p.pull.mobs = {}
                S.dirty = true
                note('action', 'Battle: pull list cleared; any mob may be pulled.')
            else
                note('error', 'Battle: //battle pull mob add|remove <name> | pull mob clear')
            end
        elseif second == 'distance' then
            p.pull.find_distance = whole(words[3], 5, 100, p.pull.find_distance)
            S.dirty = true
            note('action', string.format('Battle: puller search distance %d yalms.', p.pull.find_distance))
        else
            local value = second ~= 'off'
            p.pull.enabled = value
            S.dirty = true
            note('action', 'Battle: pulling ' .. (value and 'on' or 'off'))
        end
    elseif first == 'heal' or first == 'formation' or first == 'kite' then
        local second = (words[2] or 'toggle'):lower()
        local key = first == 'heal' and 'heal'
            or first == 'formation' and 'formation' or 'kiting'
        local value = true
        if second == 'off' then value = false end
        p[key].enabled = value
        S.dirty = true
        note('action', 'Battle: ' .. first .. ' ' .. (value and 'on' or 'off'))
    elseif first == 'cure' then
        local second = (words[2] or ''):lower()
        if second == 'add' then
            local spell = B.spell(words[3])
            if not spell then note('error', 'Battle: no spell called ' .. tostring(words[3])); return false end
            local below = whole(words[4], 1, 100, 50)
            local rows = p.heal.cures
            for _, row in ipairs(rows) do
                if row.spell:lower() == spell_name(spell):lower() then row.below = below; S.dirty = true; return true end
            end
            rows[#rows + 1] = { id = row_id(), spell = spell_name(spell), below = below }
            S.dirty = true
        elseif second == 'remove' then
            local name = text(words[3], 40):lower()
            for index = #p.heal.cures, 1, -1 do
                if p.heal.cures[index].spell:lower() == name then table.remove(p.heal.cures, index) end
            end
            S.dirty = true
        else
            note('error', 'Battle: cure add <spell> <hp%> | cure remove <spell>')
        end
    elseif first == 'buff' or first == 'enfeeble' then
        local second = (words[2] or ''):lower()
        local list = first == 'buff' and p.buffs.rows or p.enfeebles.rows
        if second == 'on' or second == 'off' or second == 'toggle' then
            p[first == 'buff' and 'buffs' or 'enfeebles'].enabled = second ~= 'off'
            S.dirty = true
            note('action', 'Battle: ' .. first .. ' ' .. (second == 'off' and 'off' or 'on'))
        elseif second == 'add' then
            local spell = B.spell(words[3])
            if not spell then note('error', 'Battle: no spell called ' .. tostring(words[3])); return false end
            if first == 'buff' then
                local target = (words[4] or 'self'):lower()
                if target ~= 'self' and target ~= 'party' and target ~= 'alliance' then target = 'self' end
                list[#list + 1] = { id = row_id(), spell = spell_name(spell), target = target,
                    interval = whole(words[5], 1, 3600, 300) }
            else
                list[#list + 1] = { id = row_id(), spell = spell_name(spell),
                    interval = whole(words[4], 1, 3600, 120) }
            end
            S.dirty = true
        elseif second == 'remove' then
            local name = text(words[3], 40):lower()
            for index = #list, 1, -1 do
                if list[index].spell:lower() == name then table.remove(list, index) end
            end
            S.dirty = true
        end
    elseif first == 'dispel' then
        local second = (words[2] or ''):lower()
        if second == 'on' or second == 'off' or second == 'toggle' then
            p.dispel.enabled = second ~= 'off'
            S.dirty = true
        elseif second == 'add' then
            local spell = B.spell(words[3])
            if spell then
                p.dispel.spell = spell_name(spell)
                p.dispel.interval = whole(words[4], 1, 3600, p.dispel.interval)
                p.dispel.enabled = true
                S.dirty = true
            end
        end
    elseif first == 'ws' then
        local value = text(words[2], 40)
        p.engage.weapon_skill = value:lower() == 'off' and '' or value
        S.dirty = true
    elseif first == 'death' then
        local mode = (words[2] or ''):lower()
        if mode == 'raise' or mode == 'homepoint' then p.death.mode = mode end
        p.death.wait = whole(words[3], 0, 600, p.death.wait)
        S.dirty = true
    elseif first == 'loot' then
        local mode = (words[2] or ''):lower()
        if contains(LOOT_MODES, mode) then p.loot.mode = mode; S.dirty = true end
    elseif first == 'priority' then
        local order = {}
        for index = 2, #words do
            local item = words[index]:lower()
            if contains(PRIORITIES, item) and not contains(order, item) then order[#order + 1] = item end
        end
        if #order > 0 then
            for _, item in ipairs(PRIORITIES) do if not contains(order, item) then order[#order + 1] = item end end
            p.priority = order
            S.dirty = true
        end
    elseif first == 'help' or first == '?' then
        help()
    else
        note('error', 'Battle: unknown "' .. first .. '"; //battle help lists the commands.')
        return false
    end
    return true
end

-------------------------------------------------------------------------------- control-port API

local function snapshot()
    return {
        profile = C.copy(S.profile),
        profiles = C.list(),
        status = B.status(),
        file = S.file,
        dirty = S.dirty == true,
        character = S.character,
        visible = S.visible,
    }
end

function M.request(args)
    args = type(args) == 'table' and args or {}
    if not S.installed then return nil, 'battle is not installed' end
    if not S.profile then C.resume() end
    local action = tostring(args.action or 'state'):lower()
    if action == 'state' or action == 'status' then
        return snapshot()
    elseif action == 'profiles' then
        return { profiles = C.list(), character = S.character }
    elseif action == 'update' then
        if type(args.profile) ~= 'table' then return nil, 'battle update: profile' end
        S.profile = C.sanitize(args.profile)
        S.camp_hud_restore = S.profile.camp_hud.collapsed == true
        S.buffers = {}
        S.profile_seq = (S.profile_seq or 0) + 1
        S.dirty = true
        if S.profile.ui then
            S.ui.x, S.ui.y = S.profile.ui.x, S.profile.ui.y
            S.ui.opacity = S.profile.ui.opacity
        end
        return snapshot()
    elseif action == 'save' then
        if type(args.profile) == 'table' then
            S.profile = C.sanitize(args.profile)
            S.buffers = {}
        end
        local ok, err = C.save(args.name)
        if not ok then return nil, err end
        S.dirty = false
        show_hub(false)
        return snapshot()
    elseif action == 'load' then
        local ok, err = C.load(args.name)
        if not ok then return nil, err end
        return snapshot()
    elseif action == 'delete' then
        local ok, err = C.delete(args.name)
        if not ok then return nil, err end
        return snapshot()
    elseif action == 'new' then
        C.new_profile(args.name)
        S.dirty = true
        return snapshot()
    elseif action == 'start' then
        local ok, err = B.start()
        if not ok then return nil, err end
        return snapshot()
    elseif action == 'stop' then
        B.stop()
        return snapshot()
    elseif action == 'pause' then
        local ok, err = B.toggle_pause(args.role)
        if not ok then return nil, err end
        return snapshot()
    elseif action == 'tab' then
        local wanted = tostring(args.tab or ''):lower()
        for _, item in ipairs(HUB_TABS) do
            if item.key == wanted then
                S.tab = wanted
                show_hub(true)
                return snapshot()
            end
        end
        return nil, 'battle: unknown tab ' .. wanted
    elseif action == 'show' then
        show_hub(true)
        return snapshot()
    elseif action == 'hide' then
        show_hub(false)
        return snapshot()
    elseif action == 'team_switch' then
        return B.team_switch(args.name)
    elseif action == 'team_restore' then
        B.team_restore()
        return snapshot()
    elseif action == 'team_save' then
        local data, err = B.team_save_profile(args.name)
        if not data then return nil, err end
        return snapshot()
    elseif action == 'camp_hud' then
        local cfg = S.profile.camp_hud
        if type(args.show) == 'boolean' then
            cfg.show = args.show
            if cfg.show then S.camp_hud_apply = true end
        end
        if args.x ~= nil then
            cfg.x = clamp(args.x, -4000, 8000, cfg.x)
            S.camp_hud_apply = true
        end
        if args.y ~= nil then
            cfg.y = clamp(args.y, -4000, 8000, cfg.y)
            S.camp_hud_apply = true
        end
        if args.reset then
            local ok, sw, sh = pcall(xi.ui.screen)
            if ok and sw and sh then
                cfg.x = math.max(0, math.floor((sw - cfg.w) / 2))
                cfg.y = math.max(0, math.floor((sh - cfg.h) / 2))
            else
                cfg.x, cfg.y = 200, 200
            end
            S.camp_hud_apply = true
            cfg.show = true
        end
        if args.move ~= nil then
            S.camp_hud_edit = args.move and true or false
            if args.move then cfg.show = true; S.camp_hud_apply = true end
            if not args.move then C.save(S.profile.name) end
        end
        S.dirty = true
        return snapshot()
    elseif action == 'camp_here' then
        local pos = B.self_pos()
        if not pos then return nil, 'not in the world yet' end
        S.profile.camp.set, S.profile.camp.x, S.profile.camp.y, S.profile.camp.z = true, pos.x, pos.y, pos.z
        S.dirty = true
        return snapshot()
    elseif action == 'camp_radius' then
        S.profile.camp.radius = clamp(args.radius, 1, 50, S.profile.camp.radius)
        if S.place then S.place.radius = S.profile.camp.radius end
        S.dirty = true
        return snapshot()
    elseif action == 'camp_clear' then
        S.profile.camp.set = false
        S.dirty = true
        return snapshot()
    elseif action == 'place_there' then
        place_start('tank')
        return snapshot()
    elseif action == 'support_camp_here' then
        local pos = B.self_pos()
        if not pos then return nil, 'not in the world yet' end
        local camp = S.profile.support_camp
        camp.set, camp.x, camp.y, camp.z = true, pos.x, pos.y, pos.z
        S.dirty = true
        return snapshot()
    elseif action == 'support_camp_radius' then
        local camp = S.profile.support_camp
        camp.radius = clamp(args.radius, 1, 50, camp.radius)
        if S.place and S.place.kind == 'support' then S.place.radius = camp.radius end
        S.dirty = true
        return snapshot()
    elseif action == 'support_camp_clear' then
        S.profile.support_camp.set = false
        S.dirty = true
        return snapshot()
    elseif action == 'support_place_there' then
        place_start('support')
        return snapshot()
    elseif action == 'import_party' then
        B.import_party()
        return snapshot()
    elseif action == 'rally' then
        local ok, err = pcall(xi.chat.run, '//warp all me', 1)
        if not ok then return nil, tostring(err) end
        return snapshot()
    elseif action == 'invite_team' then
        local ok, err = pcall(xi.chat.run, '//invite subs', 1)
        if not ok then return nil, tostring(err) end
        return snapshot()
    elseif action == 'suggest' then
        C.suggest(tostring(args.scope or 'all'))
        return snapshot()
    elseif action == 'command' then
        M.command(tostring(args.line or ''))
        return snapshot()
    elseif action == 'projection' then
        local now = clock()
        local camera = G.camera(now)
        local device = nil
        local okdev, dev = pcall(xi.d3d8_device)
        if okdev then device = dev end
        return {
            ready = G.ready, unavailable = G.unavailable, axis = G.axis_value,
            has_camera = camera ~= nil, has_matrix = G.matrix ~= nil,
            retry_in = math.max(0, (G.retry_after or 0) - now),
            device = device,
        }
    end
    return nil, 'battle: unknown action ' .. action
end

-------------------------------------------------------------------------------- the hub

local HUB = {
    start = { 0.40, 0.95, 0.55, 1 },
    stop = { 1.00, 0.42, 0.38, 1 },
    cyan = { 0.35, 0.85, 0.95, 1 },
    dim = { 0.58, 0.64, 0.70, 1 },
    gold = { 1.00, 0.79, 0.27, 1 },
    red = { 1.00, 0.42, 0.38, 1 },
    green = { 0.45, 0.95, 0.58, 1 },
    white = { 0.92, 0.91, 0.88, 1 },
    track = { 0.07, 0.09, 0.11, 0.95 },
    card = { 0.06, 0.08, 0.10, 0.94 },
}

local function rgba(c, alpha)
    local a = alpha or c[4] or 1
    return math.floor(c[1] * 255 + 0.5) + math.floor(c[2] * 255 + 0.5) * 0x100
        + math.floor(c[3] * 255 + 0.5) * 0x10000 + math.floor(a * 255 + 0.5) * 0x1000000
end

local function hud_text(api, color, value)
    if api.TextColored then api.TextColored(color, tostring(value))
    else api.Text(tostring(value)) end
end

local function button(api, label, color, width)
    if api.PushStyleColor and color then
        api.PushStyleColor(21, { color[1], color[2], color[3], 1 })
        api.PushStyleColor(22, { math.min(1, color[1] * 1.15 + 0.02),
            math.min(1, color[2] * 1.15 + 0.02), math.min(1, color[3] * 1.15 + 0.02), 1 })
        api.PushStyleColor(23, { color[1] * 0.75, color[2] * 0.75, color[3] * 0.75, 1 })
        local clicked = api.Button(label, { width or 68, 22 })
        api.PopStyleColor(3)
        return clicked
    end
    return api.Button(label, { width or 68, 22 })
end

local function section(api, title)
    api.Dummy({ 0, 2 })
    hud_text(api, HUB.cyan, string.upper(tostring(title)))
    api.Separator()
end

local function touched()
    S.dirty = true
end

local function text_field(api, id, value, width)
    local key = 't:' .. id
    local buf = S.buffers[key]
    if type(buf) ~= 'table' then
        buf = { tostring(value or '') }
        S.buffers[key] = buf
    end
    if width and api.SetNextItemWidth then api.SetNextItemWidth(width) end
    if api.InputText('##' .. id, buf, 96) then
        return buf[1]
    end
    return nil
end

local function int_field(api, id, value, width, low, high, fmt)
    local key = 'i:' .. id
    local buf = S.buffers[key]
    if type(buf) ~= 'table' then
        buf = { math.floor(tonumber(value) or low or 0) }
        S.buffers[key] = buf
    end
    if width and api.SetNextItemWidth then api.SetNextItemWidth(width) end
    -- DragInt, not InputInt: the +/- steppers ate the number at the narrow widths this hub
    -- uses.  A drag box always shows the value and still allows click-to-type.
    if api.DragInt('##' .. id, buf, 1, math.floor(low or 0), math.floor(high or 100), fmt or '%d') then
        return whole(buf[1], low, high, value)
    end
    return nil
end

local function float_field(api, id, value, width, low, high, step, fmt)
    local key = 'f:' .. id
    local buf = S.buffers[key]
    if type(buf) ~= 'table' then
        buf = { tonumber(value) or low or 0 }
        S.buffers[key] = buf
    end
    if width and api.SetNextItemWidth then api.SetNextItemWidth(width) end
    if api.DragFloat('##' .. id, buf, step or 0.1, low or 0, high or 100, fmt or '%.1f') then
        return clamp(buf[1], low or 0, high or 100, value)
    end
    return nil
end

local function yalm_field(api, id, value, width, low, high, step, fmt, label)
    local key = 'y:' .. id
    local buf = S.buffers[key]
    if type(buf) ~= 'table' then
        buf = { string.format(fmt or '%.1f', tonumber(value) or low or 0), tonumber(value) or low or 0 }
        S.buffers[key] = buf
    end
    local current = tonumber(value) or low or 0
    if tonumber(buf[2]) ~= current then
        buf[1], buf[2] = string.format(fmt or '%.1f', current), current
    end
    local result = nil
    if button(api, '-##' .. id, HUB.cyan, 22) then
        result = clamp(current - (step or 1), low or 0, high or 100, current)
    end
    api.SameLine(0, 2)
    if api.SetNextItemWidth then api.SetNextItemWidth(width or 64) end
    if api.InputText('##' .. id, buf, 96) then
        local typed = tonumber(buf[1])
        if typed then result = clamp(typed, low or 0, high or 100, current) end
    end
    api.SameLine(0, 2)
    if button(api, '+##' .. id, HUB.cyan, 22) then
        result = clamp(current + (step or 1), low or 0, high or 100, current)
    end
    if result then
        buf[1], buf[2] = string.format(fmt or '%.1f', result), result
    end
    api.SameLine(0, 4)
    hud_text(api, HUB.dim, label or 'yalms')
    return result
end

local function check(api, id, label, value, sync)
    local key = 'b:' .. id
    local buf = S.buffers[key]
    if type(buf) ~= 'table' or type(buf[1]) ~= 'boolean' then
        buf = { value and true or false }
        S.buffers[key] = buf
    elseif sync then
        -- A value another page can change (the Support page's Nitro set) must not leave a
        -- stale checkbox behind when the user comes back to this tab.
        buf[1] = value and true or false
    end
    if api.Checkbox(label .. '##' .. id, buf) then return buf[1] end
    return nil
end

local function combo(api, id, values, labels, current, width)
    local key = 'c:' .. id
    local buf = S.buffers[key]
    if type(buf) ~= 'table' then buf = { 0 }; S.buffers[key] = buf end
    local at = 0
    for i, value in ipairs(values) do if value == current then at = i - 1 break end end
    buf[1] = at
    if width and api.SetNextItemWidth then api.SetNextItemWidth(width) end
    if api.Combo('##' .. id, buf, labels or values, #values) then
        return values[(tonumber(buf[1]) or 0) + 1]
    end
    return nil
end

local function member_names()
    local out = {}
    for _, member in ipairs(B.members('alliance')) do out[#out + 1] = member.name end
    return out
end

local function role_name(role)
    return ROLE_LABELS[role] or role
end

local function role_assigned(role, name)
    local roster = S.profile.roster
    if role == 'support' or role == 'melee' or role == 'ranged' then
        return contains(roster[role], name)
    end
    return roster[role] == name
end

local function toggle_role(role, name)
    local p = S.profile
    local active = role_assigned(role, name)
    if role == 'support' or role == 'melee' or role == 'ranged' then
        if active then
            remove_value(p.roster[role], name)
        else
            for _, key in ipairs({ 'tank', 'kiter' }) do
                if p.roster[key] == name then p.roster[key] = '' end
            end
            if role ~= 'support' and p.roster.puller == name then p.roster.puller = '' end
            for _, key in ipairs({ 'support', 'melee', 'ranged' }) do
                if key ~= role then remove_value(p.roster[key], name) end
            end
            if #p.roster[role] < 18 then p.roster[role][#p.roster[role] + 1] = name end
        end
    else
        for _, key in ipairs({ 'tank', 'puller', 'kiter' }) do
            if p.roster[key] == name then p.roster[key] = '' end
        end
        for _, key in ipairs({ 'support', 'melee', 'ranged' }) do remove_value(p.roster[key], name) end
        p.roster[role] = active and '' or name
    end
    touched()
end

function H.roster(api)
    local p = S.profile
    section(api, 'Assignments')
    if not S.remote_edit then
        if button(api, 'Import party', HUB.cyan, 106) then B.import_party() end
        api.SameLine(0, 8)
        api.TextDisabled('Adds unassigned names by job.')
        api.TextDisabled('Tank and puller stay manual.')
    else
        api.TextDisabled('Editing ' .. tenant_label() .. ' on the server.')
    end
    local names = roster_names()
    if #names > 0 then
        api.TextDisabled(string.format('%d in the live party; only these count.', #names))
    else
        api.TextDisabled('No live party members; saved roles wait for their next login.')
    end
    local single = {
        { key = 'tank', label = 'Tank', hint = 'anchors the formation' },
        { key = 'puller', label = 'Puller', hint = 'claims; may be support' },
        { key = 'kiter', label = 'Kiter', hint = 'runs the kite' },
    }
    for _, item in ipairs(single) do
        local current = p.roster[item.key]
        local present = current ~= '' and B.in_party(current)
        hud_text(api, HUB.dim, item.label)
        api.SameLine(66, 6)
        local shown = current ~= '' and current or '(unassigned)'
        if current ~= '' and not present then shown = shown .. ' (not in party)' end
        hud_text(api, current == '' and HUB.dim or (present and HUB.white or HUB.gold), shown)
        api.SameLine(220, 6)
        local values, labels = { '' }, { '(none)' }
        local listed = {}
        for _, name in ipairs(names) do
            values[#values + 1] = name
            labels[#labels + 1] = name
            listed[name:lower()] = true
        end
        -- An assigned character who is not in the live party stays visible so the profile can
        -- be changed without pretending the name vanished; it is labelled and not offered as
        -- a new pick.
        if current ~= '' and not listed[current:lower()] then
            values[#values + 1] = current
            labels[#labels + 1] = current .. ' (not in party)'
        end
        local picked = combo(api, 'roster-' .. item.key, values, labels, current, 150)
        if picked ~= nil then
            p.roster[item.key] = picked
            if picked ~= '' then
                for _, key in ipairs({ 'tank', 'puller', 'kiter' }) do
                    if key ~= item.key and p.roster[key] == picked then p.roster[key] = '' end
                end
                if item.key ~= 'puller' then
                    for _, key in ipairs({ 'support', 'melee', 'ranged' }) do remove_value(p.roster[key], picked) end
                end
            end
            touched()
        end
        api.SameLine(0, 8)
        api.TextDisabled(item.hint)
    end
    for _, key in ipairs({ 'support', 'melee', 'ranged' }) do
        hud_text(api, HUB.dim, role_name(key))
        api.SameLine(66, 6)
        local live, absent = {}, {}
        for _, name in ipairs(p.roster[key]) do
            if B.in_party(name) then live[#live + 1] = name else absent[#absent + 1] = name end
        end
        hud_text(api, #live > 0 and HUB.white or HUB.dim,
            #live > 0 and table.concat(live, ', ') or '(none in party)')
        if #absent > 0 then
            hud_text(api, HUB.dim, '  not in party: ' .. table.concat(absent, ', '))
        end
    end

    section(api, 'Party')
    local party = B.members('alliance')
    local remote_name = S.remote_edit and S.remote_edit.name or ''
    local remote_in_party = false
    for _, member in ipairs(party) do
        if member.name == remote_name then remote_in_party = true break end
    end
    if remote_name ~= '' and not remote_in_party then
        api.TextDisabled(remote_name .. ' is not in this party; its saved profile is being edited.')
    end
    for index, member in ipairs(party) do
        local name = member.name
        local job_id = tonumber(member.main_job or member.job) or 0
        local job = JOB_ABBR[job_id] or '???'
        local level = tonumber(member.main_level or member.level) or 0
        local label = string.format('%s  %s %d', name, job, level)
        local member_color = HUB.white
        if member.slot == 0 then member_color = HUB.cyan end
        if S.remote_edit and name == remote_name then member_color = HUB.gold end
        hud_text(api, member_color, label)
        api.SameLine(230, 6)
        local slot = tonumber(member.slot) or index
        for _, role in ipairs({ 'tank', 'puller', 'kiter', 'support', 'melee', 'ranged' }) do
            local on = role_assigned(role, name)
            local text = role == 'tank' and 'T' or role == 'puller' and 'P'
                or role == 'kiter' and 'K' or role == 'support' and 'S'
                or role == 'melee' and 'M' or 'R'
            if on and api.PushStyleColor then
                local c = role == 'tank' and HUB.gold or role == 'puller' and HUB.cyan
                    or role == 'kiter' and HUB.green or role == 'support' and HUB.white or HUB.dim
                api.PushStyleColor(21, { c[1] * 0.55, c[2] * 0.55, c[3] * 0.55, 1 })
            end
            if api.SmallButton(text .. '##' .. role .. slot) then toggle_role(role, name) end
            if on and api.PopStyleColor then api.PopStyleColor(1) end
            if role ~= 'ranged' then api.SameLine(0, 2) end
        end
    end

    section(api, 'Role pauses')
    for _, role in ipairs({ 'tank', 'support', 'melee', 'ranged' }) do
        local value = check(api, 'pause-' .. role, role_name(role), p.paused[role])
        if value ~= nil then p.paused[role] = value; touched() end
        if role ~= 'ranged' then api.SameLine(0, 18) end
    end
    api.TextDisabled('Paused roles hold still; the rest of the party keeps fighting.')
end

-------------------------------------------------------------------------------- camp tab

local function radar(api)
    local width, height = 300, 176
    local x, y = api.GetCursorScreenPos()
    api.Dummy({ width, height })
    local draw = api.GetWindowDrawList()
    draw:AddRectFilled({ x, y }, { x + width, y + height }, rgba(HUB.card), 6, 0)
    draw:AddRect({ x, y }, { x + width, y + height }, rgba(HUB.cyan, 0.28), 6, 0, 1)
    local tank = B.camp_pos('tank')
    local support = B.support_camp_pos()
    local support_set = S.profile.support_camp.set
    local me = B.self_pos()
    local center = S.place or tank or support or me
    if not center then return end
    local scale = 1.35
    local cx, cy = x + width / 2, y + height / 2
    local function at(pos)
        return cx + (pos.x - center.x) * scale, cy - (pos.y - center.y) * scale
    end
    if tank then
        draw:AddCircle({ at(tank) }, B.camp_radius('tank') * scale, rgba(HUB.cyan, 0.8), 48, 1.5)
        local sx, sy = at(tank)
        draw:AddLine({ sx - 4, sy }, { sx + 4, sy }, rgba(HUB.cyan, 0.9), 1)
        draw:AddLine({ sx, sy - 4 }, { sx, sy + 4 }, rgba(HUB.cyan, 0.9), 1)
    end
    if support_set and support then
        draw:AddCircle({ at(support) }, B.camp_radius('support') * scale, rgba(HUB.gold, 0.85), 48, 1.5)
        local sx, sy = at(support)
        draw:AddLine({ sx - 3, sy - 3 }, { sx + 3, sy + 3 }, rgba(HUB.gold, 0.9), 1)
        draw:AddLine({ sx - 3, sy + 3 }, { sx + 3, sy - 3 }, rgba(HUB.gold, 0.9), 1)
    end
    if S.place then
        local sx, sy = at(S.place)
        local pr = (tonumber(S.place.radius) or 10) * scale
        local color = S.place.kind == 'support' and HUB.gold or HUB.cyan
        draw:AddCircle({ sx, sy }, pr, rgba(color, 0.95), 48, 1.5)
        draw:AddLine({ sx - 6, sy }, { sx + 6, sy }, rgba(color, 1), 1.5)
        draw:AddLine({ sx, sy - 6 }, { sx, sy + 6 }, rgba(color, 1), 1.5)
    end
    for _, mob in ipairs(B.mobs()) do
        local sx, sy = at(mob.pos)
        if math.abs(sx - cx) < width / 2 - 4 and math.abs(sy - cy) < height / 2 - 4 then
            draw:AddCircleFilled({ sx, sy }, 3, rgba(mob.claim and HUB.gold or HUB.red, 0.95))
        end
    end
    for _, member in ipairs(B.members('alliance')) do
        if member.slot ~= 0 then
            local index = entity_by_name(member.name)
            local pos = index and position(index)
            if pos then
                local sx, sy = at(pos)
                if math.abs(sx - cx) < width / 2 - 4 and math.abs(sy - cy) < height / 2 - 4 then
                    draw:AddCircleFilled({ sx, sy }, 2.5, rgba(HUB.green, 0.9))
                end
            end
        end
    end
    if me then
        local sx, sy = at(me)
        draw:AddCircleFilled({ sx, sy }, 4, rgba(HUB.cyan, 1))
        draw:AddCircle({ sx, sy }, 6, rgba(HUB.cyan, 0.5), 12, 1)
    end
    api.PushFont(nil, 9)
    draw:AddText({ x + 8, y + height - 16 }, rgba(HUB.dim, 0.9),
        string.format('T %.0f  ·  S %s', B.camp_radius('tank'),
            support_set and string.format('%.0f', B.camp_radius('support')) or 'uses T'))
    api.PopFont()
end

local function camp_set_here(kind)
    local pos = B.self_pos()
    if not pos then note('error', 'Battle: not in the world yet.'); return end
    local camp = kind == 'support' and S.profile.support_camp or S.profile.camp
    camp.set, camp.x, camp.y, camp.z = true, pos.x, pos.y, pos.z
    touched()
    note('action', 'Battle: ' .. kind .. ' camp set here.')
end

local function camp_clear(kind)
    local camp = kind == 'support' and S.profile.support_camp or S.profile.camp
    camp.set = false
    touched()
    note('action', 'Battle: ' .. kind .. ' camp cleared.')
end

function H.camp(api)
    local p = S.profile
    section(api, 'Camps')
    api.TextDisabled('Tank camp holds the mob and anchors pull/leash.')
    api.TextDisabled('Support camp is where healers, GEO/BRD and ranged stand.')
    hud_text(api, HUB.cyan, 'Tank camp: tank, puller, kiter, melee')
    hud_text(api, HUB.gold, 'Support camp: support/healers, GEO/BRD, ranged')
    local mobile = check(api, 'camp-mobile', 'Mobile camp — follow the tank (Sortie/Odyssey/Dynamis)', p.mobile)
    if mobile ~= nil then p.mobile = mobile; touched() end
    local tank_on = check(api, 'camp-tank-enabled', 'Use a tank camp (on by default)', p.tank_enabled)
    if tank_on ~= nil then p.tank_enabled = tank_on; touched() end
    if p.mobile then
        local follow = yalm_field(api, 'camp-follow-distance', p.follow_distance, 54, 5, 30, 1, '%d', 'yalms behind tank')
        if follow then p.follow_distance = follow; touched() end
        api.TextDisabled('Mobile: melee follows the tank; support follows the tank')
        api.TextDisabled('at the distance above. Static camp points are ignored.')
    else
        api.TextDisabled('Static camps are for EXP/CP/EP parties. Only the puller')
        api.TextDisabled('leaves camp; the puller may be a support member.')
    end

    section(api, 'Camp assignments')
    api.TextDisabled('Auto uses the role. A person assignment overrides the role;')
    api.TextDisabled('Combat chooses melee or ranged behavior independently.')
    local members = tenant_members()
    for index, member in ipairs(members) do
        local name = member.name
        local slot = tonumber(member.slot) or tonumber(member.character_id) or index
        local assigned = p.camp_assign[name] or 'auto'
        local style = p.combat_style[name] or 'auto'
        local role = B.role_of(name)
        hud_text(api, HUB.white, name)
        api.SameLine(116, 4)
        local camp = combo(api, 'camp-person-' .. slot, { 'auto', 'tank', 'support' },
            { 'Auto camp', 'Tank camp', 'Support camp' }, assigned, 118)
        if camp then
            if camp == 'auto' then p.camp_assign[name] = nil else p.camp_assign[name] = camp end
            touched()
        end
        api.SameLine(0, 4)
        local mode = combo(api, 'combat-person-' .. slot, { 'auto', 'melee', 'ranged' },
            { 'Auto combat', 'Melee', 'Ranged' }, style, 112)
        if mode then
            if mode == 'auto' then p.combat_style[name] = nil else p.combat_style[name] = mode end
            touched()
        end
        api.SameLine(0, 6)
        hud_text(api, HUB.dim, role and role_name(role) or 'no role')
    end
    local hudshow = check(api, 'camp-hud-show', 'Show the movable Battle HUD', p.camp_hud.show)
    if hudshow ~= nil then
        p.camp_hud.show = hudshow
        if hudshow then S.camp_hud_apply = true end
        touched()
    end
    local hudmap = check(api, 'camp-hud-map', 'Zone map behind the Battle HUD', p.camp_hud.map)
    if hudmap ~= nil then
        p.camp_hud.map = hudmap
        S.camp_hud_apply = true
        touched()
    end
    if p.camp_hud.map then
        api.SameLine(0, 10)
        local range = yalm_field(api, 'camp-hud-range', p.camp_hud.range, 72, 150, 4000, 50, '%d',
            'yalms across')
        if range then p.camp_hud.range = range; touched() end
    end
    hud_text(api, HUB.cyan, 'Tank camp')
    if button(api, 'Set here##tank-camp', HUB.cyan, 82) then camp_set_here('tank') end
    api.SameLine(0, 6)
    if button(api, 'Set there##tank-camp', HUB.gold, 82) then place_start('tank') end
    api.SameLine(0, 6)
    if button(api, 'Clear##tank-camp', HUB.red, 62) then camp_clear('tank') end
    api.SameLine(0, 12)
    local radius = yalm_field(api, 'camp-radius', p.camp.radius, 58, 1, 50, 0.1, '%.1f', 'yalms')
    if radius then
        p.camp.radius = radius
        if S.place and S.place.kind == 'tank' then S.place.radius = radius end
        touched()
    end
    if p.camp.set then
        hud_text(api, HUB.white, string.format('Tank %.1f, %.1f  (height %.1f)', p.camp.x, p.camp.y, p.camp.z))
    else
        hud_text(api, HUB.red, 'No tank camp set. Start uses the current spot.')
    end
    local show_t = check(api, 'camp-show', 'Show the tank camp radar while playing', p.camp.show)
    if show_t ~= nil then p.camp.show = show_t; touched() end

    hud_text(api, HUB.gold, 'Support camp')
    if button(api, 'Set here##support-camp', HUB.gold, 82) then camp_set_here('support') end
    api.SameLine(0, 6)
    if button(api, 'Set there##support-camp', HUB.gold, 82) then place_start('support') end
    api.SameLine(0, 6)
    if button(api, 'Clear##support-camp', HUB.red, 62) then camp_clear('support') end
    api.SameLine(0, 12)
    local sradius = yalm_field(api, 'support-camp-radius', p.support_camp.radius, 58, 1, 50, 0.1, '%.1f', 'yalms')
    if sradius then
        p.support_camp.radius = sradius
        if S.place and S.place.kind == 'support' then S.place.radius = sradius end
        touched()
    end
    if p.support_camp.set then
        hud_text(api, HUB.white, string.format('Support %.1f, %.1f  (height %.1f)', p.support_camp.x, p.support_camp.y, p.support_camp.z))
    else
        hud_text(api, HUB.dim, 'Not set: support uses the tank camp until you place this one.')
    end
    local show_s = check(api, 'support-camp-show', 'Show the support camp radar while playing', p.support_camp.show)
    if show_s ~= nil then p.support_camp.show = show_s; touched() end
    if p.support_camp.set then
        local tank = B.camp_pos('tank')
        local support = B.support_camp_pos()
        if tank and support then
            local span = distance(tank, support)
            hud_text(api, span > 20 and HUB.red or HUB.dim,
                string.format('Camps are %.1f yalms apart%s', span,
                    span > 20 and ' — support may be out of cure/song range.' or '.'))
            local geo = p.support.geo
            if geo.enabled then
                local cast_range = tonumber(geo.range) or 20
                local covered = span <= cast_range
                hud_text(api, covered and HUB.green or HUB.red,
                    string.format('Geo: cast range %.1f y, bubble radius ~10 y; %s',
                        cast_range, covered and 'anchor is in range.' or 'move the camps closer.'))
            end
        end
    end
    api.Dummy({ 0, 2 })
    radar(api)
    if S.place then
        api.Dummy({ 0, 2 })
        if button(api, 'Drop', HUB.start, 60) then place_commit() end
        api.SameLine(0, 4)
        if button(api, 'Cancel', HUB.stop, 66) then place_cancel() end
        api.SameLine(0, 8)
        hud_text(api, HUB.gold, string.format('%s camp: mouse/arrows aim; Enter drops; Esc cancels.', S.place.kind))
    else
        api.TextDisabled('Set there follows the mouse and arrow keys over this map; Enter applies it.')
    end
    api.Dummy({ 0, 4 })
    if button(api, 'Rally team', HUB.start, 110) then
        local ok, err = pcall(xi.chat.run, '//warp all me', 1)
        if not ok then note('error', 'Battle: ' .. tostring(err)) else note('action', 'Battle: rallying the team (//warp all me).') end
    end
    api.SameLine(0, 6)
    if button(api, 'Invite subs', HUB.cyan, 100) then
        local ok, err = pcall(xi.chat.run, '//invite subs', 1)
        if not ok then note('error', 'Battle: ' .. tostring(err)) else note('action', 'Battle: inviting online sub-accounts.') end
    end
end

-------------------------------------------------------------------------------- engage tab

local function formation_preview(api)
    local width, height = 380, 190
    local x, y = api.GetCursorScreenPos()
    api.Dummy({ width, height })
    local draw = api.GetWindowDrawList()
    draw:AddRectFilled({ x, y }, { x + width, y + height }, rgba(HUB.card), 6, 0)
    draw:AddRect({ x, y }, { x + width, y + height }, rgba(HUB.cyan, 0.25), 6, 0, 1)
    local p = S.profile.formation
    local scale = 18
    local cx, cy = x + width * 0.5, y + 88
    local mob = { x = 0, y = 0, z = 0 }
    local tank = { x = 0, y = -2.8 }
    local function place(point)
        return cx + point.x * scale, cy + point.y * scale
    end
    local tx, ty = place(tank)
    local mx, my = place(mob)
    draw:AddLine({ mx, my }, { tx, ty }, rgba(HUB.dim, 0.7), 1.2)
    -- Facing arrow
    local ax, ay = mx + (tx - mx) * 0.28, my + (ty - my) * 0.28
    draw:AddTriangleFilled({ ax, ay - 5 }, { ax - 4, ay + 3 }, { ax + 4, ay + 3 }, rgba(HUB.gold, 0.8))
    draw:AddCircleFilled({ tx, ty }, 8, rgba(HUB.gold, 0.85))
    draw:AddCircle({ tx, ty }, 11, rgba(HUB.gold, 0.45), 20, 1)
    draw:AddCircleFilled({ mx, my }, 12, rgba(HUB.cyan, 0.85))
    draw:AddCircle({ mx, my }, 16, rgba(HUB.cyan, 0.35), 24, 1)
    api.PushFont(nil, 12)
    draw:AddText({ math.min(tx + 12, x + width - 44), ty - 7 }, rgba(HUB.gold, 0.95), 'TANK')
    draw:AddText({ math.min(mx + 15, x + width - 40), my - 7 }, rgba(HUB.cyan, 0.95), 'MOB')
    local names = B.roster_online('melee')
    local ghosts = #names == 0
    local total = ghosts and 3 or math.max(1, #names)
    local bx, by = 0, 1 -- the tank is above the mob, so "behind" is down the diagram
    for slot = 1, total do
        local point = B.formation_slot_from(mob, bx, by, slot, total)
        local sx, sy = place(point)
        local alpha = ghosts and 0.45 or 0.85
        draw:AddCircleFilled({ sx, sy }, 6, rgba(HUB.green, alpha))
        draw:AddCircle({ sx, sy }, 9, rgba(HUB.green, alpha * 0.5), 16, 1)
        local label = names[slot] and names[slot]:sub(1, 8) or ('M' .. slot)
        draw:AddText({ math.min(sx + 9, x + width - 52), sy - 7 }, rgba(HUB.green, ghosts and 0.55 or 0.95), label)
    end
    api.PopFont()
    api.TextDisabled(string.format('Diagram: %s, %d° arc, %.1f-yalm spacing.', p.style, math.floor(p.arc), p.spacing))
    api.TextDisabled('The mob faces the tank; numbered discs are melee slots.')
    if ghosts then api.TextDisabled('No melee online: M1-M3 are examples.') end
end

function H.engage(api)
    local p = S.profile
    section(api, 'When to engage')
    local mode = combo(api, 'engage-mode', ENGAGE_MODES, ENGAGE_LABEL_LIST, p.engage.mode, 250)
    if mode then p.engage.mode = mode; touched() end
    if p.engage.mode == 'player' then
        local name = text_field(api, 'engage-player', p.engage.player, 160)
        if name then p.engage.player = text(name, 32); touched() end
    end
    api.TextDisabled(ENGAGE_LABELS[p.engage.mode] or '')
    local wait = check(api, 'engage-wait', 'Wait for a party claim (never steal another party\'s mob)', p.engage.wait_claim)
    if wait ~= nil then p.engage.wait_claim = wait; touched() end
    local only = check(api, 'engage-camp', 'Only engage targets inside the camp', p.engage.camp_only)
    if only ~= nil then p.engage.camp_only = only; touched() end
    local maxd = yalm_field(api, 'engage-distance', p.engage.max_distance, 54, 5, 100, 1, '%d', 'yalms')
    if maxd then p.engage.max_distance = maxd; touched() end
    api.SameLine(0, 6); hud_text(api, HUB.dim, 'max distance')

    section(api, 'Melee formation')
    local formation = p.formation
    local on = check(api, 'formation-on', 'Use the tank-anchored formation', formation.enabled)
    if on ~= nil then formation.enabled = on; touched() end
    local follow = check(api, 'formation-follow-tank', 'Melee slots follow the tank', formation.follow_tank)
    if follow ~= nil then formation.follow_tank = follow; touched() end
    local style = combo(api, 'formation-style', { 'tank', 'behind', 'side' },
        { 'Tank-anchored arc', 'Behind the mob', 'Flanks' }, formation.style, 210)
    if style then formation.style = style; touched() end
    local side = combo(api, 'formation-side', { 'auto', 'left', 'right' },
        { 'Auto', 'Prefer left', 'Prefer right' }, formation.side, 120)
    if side then formation.side = side; touched() end
    local arc = int_field(api, 'formation-arc', formation.arc, 100, 40, 300, '%d deg')
    if arc then formation.arc = arc; touched() end
    local spacing = yalm_field(api, 'formation-space', formation.spacing, 54, 1.4, 6, 0.1, '%.1f', 'yalms')
    if spacing then formation.spacing = spacing; touched() end
    api.Dummy({ 0, 2 })
    formation_preview(api)
    api.TextDisabled('The tank is the anchor; the mob faces it.')
    api.TextDisabled('The arc is computed from mob→tank.')
    api.TextDisabled('Melee slots sit behind/side at the spacing.')
end

-------------------------------------------------------------------------------- skillchain tab

local function cut(value, n)
    value = tostring(value or '')
    if #value > n then return value:sub(1, n - 1) .. '…' end
    return value
end

local function skillchain_diagram(api, plan)
    local width, row_h, mb_h, gap = 620, 44, 24, 8
    local visible = {}
    for _, row in ipairs(plan.rows) do
        if not row.optional then visible[#visible + 1] = row end
    end
    local height = 8
    for _, row in ipairs(visible) do
        height = height + row_h + gap
        if not plan.spam and row.kind == 'close' and row.sc > 0 then height = height + mb_h end
    end
    if plan.looping then height = height + 20 end
    height = math.max(60, height)
    local x, y = api.GetCursorScreenPos()
    api.Dummy({ width, height })
    local draw = api.GetWindowDrawList()
    draw:AddRectFilled({ x, y }, { x + width, y + height }, rgba(HUB.card), 6, 0)
    draw:AddRect({ x, y }, { x + width, y + height }, rgba(HUB.cyan, 0.22), 6, 0, 1)
    local cy = y + 6
    api.PushFont(nil, 14)
    for index, row in ipairs(visible) do
        local ok = row.valid and (plan.spam or plan.target == 0 or plan.target_ok)
        local border = ok and HUB.cyan or HUB.red
        local label
        if plan.spam then
            label = string.format('WS %d', row.index)
        else
            label = row.kind == 'open' and 'OPEN' or ('CLOSE ' .. (row.sc > 0 and sc_name(row.sc) or ('SC' .. (row.index - 1))))
        end
        draw:AddRectFilled({ x + 6, cy }, { x + width - 6, cy + row_h }, rgba(HUB.track, 0.85), 4, 0)
        draw:AddRect({ x + 6, cy }, { x + width - 6, cy + row_h }, rgba(border, 0.65), 4, 0, 1)
        draw:AddText({ x + 12, cy + 7 }, rgba((not plan.spam and row.kind == 'open') and HUB.gold or HUB.cyan, 0.95), label)
        local actor = row.actor ~= '' and row.actor or 'unassigned'
        local ws = row.ws ~= '' and row.ws or 'no weapon skill'
        draw:AddText({ x + 132, cy + 7 }, rgba(HUB.white, 0.95), cut(actor, 13) .. '  ·  ' .. cut(ws, 22))
        local result, color
        if plan.spam then
            result, color = 'SPAM — no SC / MB', HUB.gold
        elseif row.kind == 'open' then
            result, color = (row.valid and string.format('opens %.1f s', SC_OPEN_SECONDS)
                or 'no chain opener'), HUB.dim
        elseif row.sc > 0 then
            result, color = string.format('→ %s', sc_name(row.sc)), HUB.green
        else
            result, color = 'no link (resets opening)', HUB.dim
        end
        draw:AddText({ x + 420, cy + 7 }, rgba(color, 0.95), result)
        if not plan.spam then
            draw:AddText({ x + 545, cy + 7 }, rgba(HUB.dim, 0.95), string.format('%.1fs', row.window or SC_OPEN_SECONDS))
        end
        cy = cy + row_h
        if not plan.spam and row.kind == 'close' and row.sc > 0 then
            local mb = {}
            for _, buster in ipairs(plan.bursters or {}) do
                mb[#mb + 1] = buster.spell ~= '' and (buster.name .. ' ' .. buster.spell) or buster.name
            end
            local text = #mb > 0 and table.concat(mb, '; ') or 'unassigned'
            draw:AddRectFilled({ x + 24, cy }, { x + width - 24, cy + mb_h }, rgba(HUB.gold, 0.10), 3, 0)
            draw:AddRect({ x + 24, cy }, { x + width - 24, cy + mb_h }, rgba(HUB.gold, 0.28), 3, 0, 1)
            local bonus = row.diamond and string.format(' (Diamond %.0fs)', SC_OPEN_SECONDS) or ''
            draw:AddText({ x + 30, cy + 3 }, rgba(HUB.gold, 0.95),
                string.format('MB %.1fs%s · %s', row.window or 0, bonus, cut(text, 48)))
            cy = cy + mb_h
        end
        if index < #visible then
            draw:AddLine({ x + width / 2, cy + 1 }, { x + width / 2, cy + gap - 1 }, rgba(HUB.dim, 0.5), 1)
        end
        cy = cy + gap
    end
    if plan.looping then
        draw:AddText({ x + 18, cy + 2 }, rgba(HUB.gold, 0.95), '↻ repeats the configured cycle')
    end
    api.PopFont()
end

function H.skillchain(api)
    local p = S.profile.skillchain
    section(api, 'Skillchain style')
    local on = check(api, 'sc-on', 'Plan and follow a skillchain', p.enabled)
    if on ~= nil then p.enabled = on; touched() end
    local mode = combo(api, 'sc-mode', { 'chain', 'spam' },
        { 'Make a skillchain', 'No skillchain — spam WS' }, p.mode or 'chain', 210)
    if mode then p.mode = mode; touched() end
    if p.mode ~= 'spam' then
        local target = combo(api, 'sc-target', { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 },
            SC_LABELS, tonumber(p.target) or 0, 210)
        if target then p.target = target; touched() end
        local infinite = check(api, 'sc-infinite', 'Infinite / repeat', p.infinite)
        if infinite ~= nil then p.infinite = infinite; touched() end
        if p.infinite then
            api.SameLine(0, 10)
            local goal = int_field(api, 'sc-goal', p.goal, 86, 0, SC_MAX_STEPS - 1, '%d steps')
            if goal then p.goal = goal; touched() end
            api.SameLine(0, 4); hud_text(api, HUB.dim, p.goal > 0 and (tostring(p.goal) .. ' links') or 'loop symbol')
        end
        api.TextDisabled('11 s open; a level-1 link keeps 11 s; wider links −1 s; Diamond Aspis keeps every step at 11 s.')
        api.TextDisabled('The server accepts a close up to 0.5 s after the window.')
    else
        api.TextDisabled('Spam mode: weapon skills fire in this order; no skillchain or Magic Burst windows.')
    end

    section(api, 'Weapon skill order')
    local names = roster_names()
    local remove_at = nil
    for index, row in ipairs(p.steps) do
        local label = index == 1 and 'OPEN' or ('SC' .. (index - 1))
        hud_text(api, index == 1 and HUB.gold or HUB.cyan, label)
        api.SameLine(54, 4)
        local values, labels = { '' }, { '(none)' }
        local found_actor = row.actor == ''
        for _, name in ipairs(names) do
            values[#values + 1] = name; labels[#labels + 1] = name
            if name == row.actor then found_actor = true end
        end
        if not found_actor then values[#values + 1] = row.actor; labels[#labels + 1] = row.actor end
        local actor = combo(api, 'sc-actor-' .. index, values, labels, row.actor, 126)
        if actor then row.actor = actor; touched() end
        api.SameLine(0, 4)
        local ws = text_field(api, 'sc-ws-' .. index, row.ws, 160)
        if ws then row.ws = text(ws, 40); touched() end
        if p.mode ~= 'spam' then
            api.SameLine(0, 4)
            local diamond = check(api, 'sc-diamond-' .. index, 'Diamond', row.diamond)
            if diamond ~= nil then row.diamond = diamond; touched() end
            if row.actor ~= '' and self_name() ~= '' and row.actor:lower() == self_name():lower() and B.has_diamond_aspis() then
                api.SameLine(0, 4)
                hud_text(api, HUB.gold, '(equipped)')
            end
        end
        if #p.steps > 2 then
            api.SameLine(0, 6)
            if button(api, 'x##sc-step-rm-' .. index, HUB.red, 22) then remove_at = index end
        end
    end
    if remove_at then table.remove(p.steps, remove_at); touched() end
    if #p.steps < SC_MAX_STEPS and button(api, 'Add step', HUB.cyan, 84) then
        p.steps[#p.steps + 1] = { actor = '', ws = '', diamond = false }
        touched()
    end
    api.SameLine(0, 8)
    hud_text(api, HUB.dim, string.format('%d of %d steps', #p.steps, SC_MAX_STEPS))

    if p.mode ~= 'spam' then
        section(api, 'Magic Burst')
        local remove_burst = nil
        local filled = 0
        for _, row in ipairs(p.bursters) do
            if row.name ~= '' or row.spell ~= '' then filled = filled + 1 end
        end
        local shown_limit = math.min(#p.bursters, math.max(2, filled + 1))
        for index, row in ipairs(p.bursters) do
            if index <= shown_limit then
                api.PushID(index)
                local values, labels = { '' }, { '(none)' }
                local found_burst = row.name == ''
                for _, candidate in ipairs(names) do
                    values[#values + 1] = candidate; labels[#labels + 1] = candidate
                    if candidate == row.name then found_burst = true end
                end
                if not found_burst then values[#values + 1] = row.name; labels[#labels + 1] = row.name end
                local name = combo(api, 'sc-burst-name-' .. index, values, labels, row.name, 132)
                if name then row.name = name; touched() end
                api.SameLine(0, 4)
                local spell = text_field(api, 'sc-burst-spell-' .. index, row.spell, 170)
                if spell then row.spell = text(spell, 40); touched() end
                api.SameLine(0, 4)
                if button(api, 'x##sc-burst-rm-' .. index, HUB.red, 24) then remove_burst = index end
                api.PopID()
            end
        end
        if remove_burst then table.remove(p.bursters, remove_burst); touched() end
        if #p.bursters < SC_MAX_BURSTERS and button(api, 'Add burster', HUB.gold, 100) then
            p.bursters[#p.bursters + 1] = { name = '', spell = '' }
            touched()
        end
    end

    section(api, 'Diagram')
    local plan = B.skillchain_plan()
    skillchain_diagram(api, plan)
    if p.mode == 'spam' then
        api.TextDisabled('Spam mode: no chain validation and no MB windows.')
    elseif plan.target ~= 0 then
        api.TextDisabled(plan.target_ok and ('Plan reaches ' .. sc_name(plan.target) .. '.')
            or ('Plan ends at ' .. sc_name(plan.final) .. ', not ' .. sc_name(plan.target) .. '.'))
    elseif plan.final > 0 then
        api.TextDisabled('Plan ends at ' .. sc_name(plan.final) .. '.')
    end
end


-------------------------------------------------------------------------------- pulling tab

local function pull_mob_nearby()
    local out, seen = {}, {}
    for _, mob in ipairs(B.mobs()) do
        local name = text(mob.name, 40)
        local key = name:lower()
        if name ~= '' then
            if not seen[key] then
                local row = { name = name, distance = mob.dist_camp or 999 }
                seen[key] = row
                out[#out + 1] = row
            elseif mob.dist_camp and mob.dist_camp < seen[key].distance then
                seen[key].distance = mob.dist_camp
            end
        end
    end
    table.sort(out, function(a, b)
        if a.distance == b.distance then return a.name < b.name end
        return a.distance < b.distance
    end)
    return out
end

local function pull_mob_selected(name)
    local key = tostring(name or ''):lower()
    for _, selected in ipairs(S.profile.pull.mobs) do
        if selected:lower() == key then return true end
    end
    return false
end

local function add_pull_mob(name)
    name = text(name, 40)
    if name == '' or #S.profile.pull.mobs >= 40 or pull_mob_selected(name) then return false end
    S.profile.pull.mobs[#S.profile.pull.mobs + 1] = name
    touched()
    return true
end

local function remove_pull_mob(name)
    local key = tostring(name or ''):lower()
    for index, selected in ipairs(S.profile.pull.mobs) do
        if selected:lower() == key then
            table.remove(S.profile.pull.mobs, index)
            touched()
            return true
        end
    end
    return false
end

function H.pull(api)
    local p = S.profile.pull
    section(api, 'Pulling')
    local on = check(api, 'pull-on', 'Pull for the party', p.enabled)
    if on ~= nil then p.enabled = on; touched() end
    hud_text(api, HUB.dim, 'Method')
    api.SameLine(80, 6)
    local method = combo(api, 'pull-method', PULL_METHODS, PULL_LABEL_LIST, p.method, 180)
    if method then p.method = method; touched() end
    if p.method == 'spell' then
        local spell = text_field(api, 'pull-spell', p.spell, 180)
        if spell then p.spell = text(spell, 40); touched() end
        api.SameLine(0, 6); hud_text(api, HUB.dim, 'pull spell')
    elseif p.method == 'ability' then
        local ability = text_field(api, 'pull-ability', p.ability, 180)
        if ability then p.ability = text(ability, 40); touched() end
        api.SameLine(0, 6); hud_text(api, HUB.dim, 'pull ability')
    end
    local maxm = int_field(api, 'pull-max', p.max_mobs, 80, 1, 12, '%d mobs')
    if maxm then p.max_mobs = maxm; touched() end
    local at = int_field(api, 'pull-at', p.at_hp, 96, 1, 100, '%d%% target HP')
    if at then p.at_hp = at; touched() end
    api.SameLine(0, 6)
    hud_text(api, HUB.dim, 'when the puller starts looking for the next mob')
    local leash = yalm_field(api, 'pull-leash', p.leash, 54, 5, 100, 1, '%d', 'yalms')
    if leash then p.leash = leash; touched() end
    local range = yalm_field(api, 'pull-range', p.find_distance, 54, 5, 100, 1, '%d', 'yalms')
    if range then p.find_distance = range; touched() end
    api.TextDisabled('Search distance is from camp; the puller will not travel farther.')
    local sleep = text_field(api, 'pull-sleep', p.sleep_spell, 180)
    if sleep then p.sleep_spell = text(sleep, 40); touched() end
    api.SameLine(0, 6); hud_text(api, HUB.dim, 'sleep spell')
    local bind = text_field(api, 'pull-bind', p.bind_spell, 180)
    if bind then p.bind_spell = text(bind, 40); touched() end
    api.SameLine(0, 6); hud_text(api, HUB.dim, 'bind spell')
    local extras = check(api, 'pull-extras', 'Sleep/bind extra mobs that reach the camp', p.sleep_extras)
    if extras ~= nil then p.sleep_extras = extras; touched() end

    section(api, 'Mobs to pull')
    if #p.mobs == 0 then
        hud_text(api, HUB.green, 'Any mob (no name filter set).')
    else
        hud_text(api, HUB.gold, string.format('%d selected; the puller only picks these names.', #p.mobs))
    end
    local nearby = pull_mob_nearby()
    local nearby_seen = {}
    if #nearby == 0 then
        api.TextDisabled('No live mobs are visible right now; the list refreshes as you move.')
    else
        for index, row in ipairs(nearby) do
            nearby_seen[row.name:lower()] = true
            local selected = pull_mob_selected(row.name)
            local box = { selected }
            if api.Checkbox(row.name .. '##pull-mob-' .. index, box) then
                if box[1] then add_pull_mob(row.name) else remove_pull_mob(row.name) end
            end
            api.SameLine(0, 6)
            hud_text(api, HUB.dim, string.format('%.0fy', row.distance))
        end
    end
    if #p.mobs > 0 then
        api.Dummy({ 0, 2 })
        hud_text(api, HUB.dim, 'Selected:')
        api.SameLine(0, 6)
        for index, name in ipairs(p.mobs) do
            hud_text(api, HUB.white, name)
            api.SameLine(0, 4)
            if api.SmallButton('x##pull-rm-' .. index) then remove_pull_mob(name) end
            api.SameLine(0, 8)
        end
    end
    api.Dummy({ 0, 2 })
    local added = text_field(api, 'pull-new-mob', '', 180)
    if added and add_pull_mob(added) then
        S.buffers['t:pull-new-mob'] = { '' }
    end
    api.SameLine(0, 6)
    if button(api, 'Add name', HUB.cyan, 82) then
        local buf = S.buffers['t:pull-new-mob']
        if buf and add_pull_mob(buf[1]) then buf[1] = '' end
    end
    api.SameLine(0, 8)
    hud_text(api, HUB.dim, 'or pick from the nearby list above')
    api.TextDisabled('Puller returns to camp; sleep/bind only extras, never the main target.')
end

-------------------------------------------------------------------------------- healing tab

local function remove_row_button(api, id, width)
    if api.PushStyleColor then api.PushStyleColor(21, { 0.45, 0.10, 0.10, 1 }) end
    local clicked = api.Button('x##' .. id, { width or 22, 22 })
    if api.PopStyleColor then api.PopStyleColor(1) end
    return clicked
end

function H.heal(api)
    local p = S.profile.heal
    local allowed = {}
    for _, spell in ipairs(known_spells()) do allowed[spell_name(spell):lower()] = true end
    if next(allowed) ~= nil then
        for index = #p.cures, 1, -1 do
            local name = tostring(p.cures[index].spell or ''):lower()
            if name ~= '' and not allowed[name] then
                table.remove(p.cures, index)
                touched()
            end
        end
    end
    section(api, 'Healing for ' .. tenant_label())
    local on = check(api, 'heal-on', 'Heal the party', p.enabled)
    if on ~= nil then p.enabled = on; touched() end
    api.SameLine(0, 16)
    hud_text(api, HUB.dim, 'Observe')
    api.SameLine(0, 6)
    local observe = combo(api, 'heal-observe', OBSERVE_MODES,
        OBSERVE_LABELS, p.observe, 150)
    if observe then p.observe = observe; touched() end
    local emergency = int_field(api, 'heal-emergency', p.emergency, 128, 1, 100, '%d%% emergency')
    if emergency then p.emergency = emergency; touched() end
    local reserve = int_field(api, 'heal-reserve', p.mp_reserve, 138, 0, 100, '%d%% MP reserve')
    if reserve then p.mp_reserve = reserve; touched() end

    section(api, 'Cures (first row whose HP% is not exceeded wins)')
    local remove_at = nil
    for index, row in ipairs(p.cures) do
        api.PushID(row.id)
        local spell = text_field(api, 'cure-spell-' .. row.id, row.spell, 170)
        if spell then row.spell = text(spell, 40); touched() end
        api.SameLine(0, 6)
        local below = int_field(api, 'cure-below-' .. row.id, row.below, 86, 1, 100, '%d%% HP')
        if below then row.below = below; touched() end
        api.SameLine(0, 8)
        if remove_row_button(api, 'cure-remove-' .. row.id) then remove_at = index end
        api.PopID()
    end
    if remove_at then table.remove(p.cures, remove_at); touched() end
    if #p.cures < MAX_ROWS and button(api, 'Add cure', HUB.cyan, 88) then
        p.cures[#p.cures + 1] = { id = row_id(), spell = '', below = 50 }
        touched()
    end
    api.SameLine(0, 6)
    if button(api, 'Suggest from job', HUB.gold, 146) then C.suggest('heal') end
    local detected = B.detected_waltzes()
    if #p.cures == 0 then
        if #detected > 0 then
            api.TextDisabled('No Cure rows; Curing Waltz below can handle HP for this job pair.')
        else
            api.TextDisabled('No Cure rows. Add one above or use a job with Cure spells.')
        end
    end

    section(api, 'Dancer waltzes (DNC main or sub job)')
    local waltz = check(api, 'heal-waltz', 'Use Curing Waltz for HP', p.waltz)
    if waltz ~= nil then p.waltz = waltz; touched() end
    local waltz_status = check(api, 'heal-waltz-status', 'Use Healing Waltz for status effects', p.waltz_status)
    if waltz_status ~= nil then p.waltz_status = waltz_status; touched() end
    local waltz_below = int_field(api, 'heal-waltz-below', p.waltz_below, 122, 1, 100, '%d%% HP or less')
    if waltz_below then p.waltz_below = waltz_below; touched() end
    api.SameLine(0, 10)
    local waltz_tp = int_field(api, 'heal-waltz-tp', p.waltz_tp_reserve, 122, 0, 3000, 'keep %d TP')
    if waltz_tp then p.waltz_tp_reserve = waltz_tp; touched() end
    if #detected == 0 then
        api.TextDisabled('No Dancer waltzes available for this job pair.')
    else
        hud_text(api, HUB.dim, 'Detected: ' .. table.concat(detected, ', '))
    end
    api.TextDisabled('Waltzes spend TP, never MP. Emergency heals ignore the TP reserve.')

    section(api, 'Status effects')
    local status = check(api, 'heal-status', 'Remove status effects with -na spells', p.status)
    if status ~= nil then p.status = status; touched() end
    local erase = check(api, 'heal-erase', 'Use Erase for anything the -na list cannot name', p.erase)
    if erase ~= nil then p.erase = erase; touched() end
    local raise = text_field(api, 'heal-raise', p.raise_spell, 160)
    if raise then p.raise_spell = text(raise, 40); touched() end
    api.SameLine(0, 6); hud_text(api, HUB.dim, 'raise spell')
    local avoid = text_field(api, 'heal-avoid', p.avoid, 300)
    if avoid then p.avoid = text(avoid, 160); touched() end
    api.SameLine(0, 6); hud_text(api, HUB.dim, 'never cast (comma separated)')
    section(api, 'Healing exclusions')
    api.TextDisabled('Excluded players are not cured or watched.')
    api.TextDisabled('If silenced they get Silena first, so a self-curing PLD can cure again;')
    api.TextDisabled('an emergency cure still applies at the emergency limit.')
    for index, member in ipairs(tenant_members()) do
        local name = member.name
        local slot = tonumber(member.slot) or tonumber(member.character_id) or index
        local excluded = heal_excluded(name)
        local value = check(api, 'heal-exclude-' .. slot, 'Exclude ' .. name, excluded)
        if value ~= nil then
            if value and not excluded then
                p.exclude[#p.exclude + 1] = name
            elseif not value then
                for index = #p.exclude, 1, -1 do
                    if p.exclude[index]:lower() == name:lower() then table.remove(p.exclude, index) end
                end
            end
            touched()
        end
    end
end

-------------------------------------------------------------------------------- buffs and debuffs tabs

local BUFF_PAGE = 1
local BUFF_SELF_ONLY = {
    ['utsusemi: ichi'] = true, ['utsusemi: ni'] = true, ['blink'] = true,
    ['stoneskin'] = true, ['aquaveil'] = true, ['reraise'] = true,
    ['third eye'] = true, ['seigan'] = true, ['hasso'] = true,
    ['berserk'] = true, ['aggressor'] = true, ['defender'] = true,
}

local function buff_row_for(name)
    for _, row in ipairs(S.profile.buffs.rows) do
        if row.spell:lower() == name:lower() then return row end
    end
    return nil
end

local function buff_toggle(name, kind, value)
    local row = buff_row_for(name)
    if value and not row then
        if #S.profile.buffs.rows >= MAX_ROWS then return end
        local lower = name:lower()
        S.profile.buffs.rows[#S.profile.buffs.rows + 1] = {
            id = row_id(), spell = name, ability = kind == 'ability',
            target = BUFF_SELF_ONLY[lower] and 'self' or 'party',
            interval = 300, exclude = {},
        }
    elseif not value and row then
        for index = #S.profile.buffs.rows, 1, -1 do
            if S.profile.buffs.rows[index] == row then table.remove(S.profile.buffs.rows, index) end
        end
    end
end

function H.buff(api)
    local p = S.profile.buffs
    section(api, 'Rules for ' .. tenant_label())
    local on = check(api, 'buffs-on', 'Maintain these buffs', p.enabled)
    if on ~= nil then p.enabled = on; touched() end
    api.TextDisabled('Each character has its own profile. Choose buffs here;')
    api.TextDisabled('the next page sets per-member exclusions.')

    if tenant_job() == 10 then
        local brd = S.profile.support.brd
        section(api, 'Bard: Nitro')
        local maintain = check(api, 'brd-maintain-nitro',
            'Maintain Nitro (Nightingale + Troubadour)', brd.nitro ~= 'off', true)
        if maintain ~= nil then
            if maintain then
                if brd.nitro == 'off' then brd.nitro = 'both' end
            else
                brd.nitro = 'off'
            end
            touched()
        end
        api.TextDisabled('Waits for both to be ready, uses them, then sings the next set.')
        api.TextDisabled('Songs still refresh while Nitro is down.')
        api.TextDisabled('Requires the BRD song cycle on the Support page.')
        if not S.remote_edit and brd.nitro ~= 'off' then
            local function timer(name)
                local remaining = B.ability_remaining(name)
                if remaining == nil then return 'not learned' end
                if remaining <= 0.05 then return 'ready' end
                return string.format('%ds', math.ceil(remaining))
            end
            hud_text(api, HUB.dim, 'Nightingale: ' .. timer('Nightingale')
                .. '  ·  Troubadour: ' .. timer('Troubadour'))
        end
        if brd.nitro == 'tank' or brd.nitro == 'support' then
            hud_text(api, HUB.gold, 'Using the ' .. brd.nitro .. ' camp set only (Support page).')
        end
    end

    if BUFF_PAGE == 1 then
        if button(api, 'Common buffs', HUB.gold, 120) then
            C.suggest('buff')
            for _, row in ipairs(p.rows) do
                local lower = row.spell:lower()
                row.target = BUFF_SELF_ONLY[lower] and 'self' or 'party'
                row.exclude = row.exclude or {}
            end
            touched()
        end
        api.SameLine(0, 6)
        if button(api, 'Next: exclusions >', HUB.cyan, 150) then BUFF_PAGE = 2 end
        api.SameLine(0, 8)
        hud_text(api, HUB.dim, string.format('%d selected', #p.rows))
        hud_text(api, HUB.dim, 'Search')
        api.SameLine(0, 6)
        text_field(api, 'buff-search', '', 220)
        local search_buf = S.buffers['t:buff-search']
        local needle = tostring(search_buf and search_buf[1] or ''):lower()
        if #p.rows > 0 then
            local chosen = {}
            for _, row in ipairs(p.rows) do chosen[#chosen + 1] = row.spell end
            hud_text(api, HUB.gold, 'Selected: ' .. table.concat(chosen, ', '))
        end
        local options = buff_options()
        if api.BeginChild('buff-picker', { 0, 300 }, true) then
            for index, option in ipairs(options) do
                local name = option.name
                if needle == '' or name:lower():find(needle, 1, true) then
                    local row = buff_row_for(name)
                    local value = check(api, 'buff-pick-' .. index,
                        string.format('[%s] %s', option.kind == 'ability' and 'JA' or 'Spell', name),
                        row ~= nil)
                    if value ~= nil then buff_toggle(name, option.kind, value); touched() end
                end
            end
            api.EndChild()
        end
        api.TextDisabled('Known buff spells and job abilities; use Search.')
        api.TextDisabled('Common buffs fills Protect/Shell/Haste/Refresh/Regen and self buffs.')
    else
        if button(api, '< Back to spells', HUB.cyan, 150) then BUFF_PAGE = 1 end
        api.SameLine(0, 6)
        hud_text(api, HUB.dim, 'Included by default; check a name to exclude.')
        local remove_at = nil
        for index, row in ipairs(p.rows) do
            api.PushID(row.id)
            hud_text(api, row.ability and HUB.gold or HUB.white,
                string.format('%s%s', row.ability and '[JA] ' or '', row.spell))
            api.SameLine(0, 8)
            local target = combo(api, 'buff-target-' .. row.id, { 'self', 'party', 'alliance' },
                { 'Self', 'Party', 'Alliance' }, row.target or 'self', 92)
            if target then row.target = target; touched() end
            api.SameLine(0, 6)
            local interval = int_field(api, 'buff-interval-' .. row.id, row.interval, 78, 1, 3600, '%d s')
            if interval then row.interval = interval; touched() end
            api.SameLine(0, 6)
            if button(api, 'x##buff-row-rm-' .. row.id, HUB.red, 22) then remove_at = index end
            if api.NewLine then api.NewLine() end
            if row.target ~= 'self' then
                hud_text(api, HUB.dim, 'exclude:')
                api.SameLine(0, 8)
                for _, member in ipairs(B.members(row.target == 'alliance' and 'alliance' or 'party')) do
                    local excluded = false
                    for _, name in ipairs(row.exclude or {}) do
                        if name:lower() == member.name:lower() then excluded = true break end
                    end
                    local value = check(api, 'buff-ex-' .. row.id .. '-' .. member.slot,
                        member.name, excluded)
                    if value ~= nil then
                        if value and not excluded then
                            row.exclude[#row.exclude + 1] = member.name
                        elseif not value then
                            for at = #row.exclude, 1, -1 do
                                if row.exclude[at]:lower() == member.name:lower() then table.remove(row.exclude, at) end
                            end
                        end
                        touched()
                    end
                    api.SameLine(0, 4)
                end
            end
            if api.NewLine then api.NewLine() end
            api.PopID()
        end
        if remove_at then table.remove(p.rows, remove_at); touched() end
        api.TextDisabled('AoE songs/rolls still affect everyone in range.')
        api.TextDisabled('Exclusion is exact for single-target spells and abilities.')
    end
end

function H.support(api)
    local p = S.profile.support
    local job = tenant_job()
    section(api, 'Support for ' .. tenant_label())
    local function ability_row(name)
        for _, row in ipairs(p.abilities) do
            if row.name:lower() == name:lower() then return row end
        end
        return nil
    end
    if job == 5 and not ability_row('Composure') then
        p.abilities[#p.abilities + 1] = { name = 'Composure', enabled = true, interval = 300 }
        touched()
    end
    if job ~= 10 then
        section(api, 'Job abilities')
        local abilities = known_abilities()
        for index, name in ipairs(abilities) do
            if index > 20 then break end
            local row = ability_row(name)
            local value = check(api, 'support-ability-' .. index, 'Keep ' .. name, row and row.enabled or false)
            if value ~= nil then
                if value and not row then
                    p.abilities[#p.abilities + 1] = { name = name, enabled = true, interval = 300 }
                elseif not value and row then
                    for at = #p.abilities, 1, -1 do
                        if p.abilities[at] == row then table.remove(p.abilities, at) end
                    end
                elseif value and row then
                    row.enabled = true
                end
                touched()
            end
        end
        api.TextDisabled('Checked abilities are used while this character supports;')
        api.TextDisabled('Composure is on by default for RDM.')
    end
    if job ~= 21 and job ~= 10 then
        api.TextDisabled('This job has no Geomancer or Bard support settings.')
        return
    end
    if job == 21 then
        section(api, 'Geomancer')
        local geo_on = check(api, 'geo-on', 'Run the GEO support loop', p.geo.enabled)
        if geo_on ~= nil then p.geo.enabled = geo_on; touched() end
        api.TextDisabled('Indi- stays around the GEO at support.')
        api.TextDisabled('Geo- is thrown on the tank/anchor by subtarget, so the bubble is')
        api.TextDisabled('centered in the tank camp and the GEO never runs.')
        local indi = text_field(api, 'geo-indi', p.geo.indi, 170)
        if indi then p.geo.indi = text(indi, 40); touched() end
        api.SameLine(0, 6); hud_text(api, HUB.dim, 'Indi at support')
        local geospell = text_field(api, 'geo-geo', p.geo.geo, 170)
        if geospell then p.geo.geo = text(geospell, 40); touched() end
        api.SameLine(0, 6); hud_text(api, HUB.dim, 'Geo on tank anchor')
        local values, labels = { '' }, { '(tank)' }
        for _, name in ipairs(roster_names()) do values[#values + 1] = name; labels[#labels + 1] = name end
        local anchor = combo(api, 'geo-anchor', values, labels, p.geo.anchor, 150)
        if anchor then p.geo.anchor = anchor; touched() end
        api.SameLine(0, 6); hud_text(api, HUB.dim, 'Geo anchor')
        local grange = yalm_field(api, 'geo-range', p.geo.range, 54, 5, 40, 1, '%d', 'cast range')
        if grange then p.geo.range = grange; touched() end
        local gi = int_field(api, 'geo-indi-int', p.geo.indi_interval, 100, 30, 600, '%d s Indi')
        if gi then p.geo.indi_interval = gi; touched() end
        local gg = int_field(api, 'geo-geo-int', p.geo.geo_interval, 100, 30, 600, '%d s Geo')
        if gg then p.geo.geo_interval = gg; touched() end
    elseif job == 10 then
        section(api, 'Bard')
        local brd = p.brd
        local brd_on = check(api, 'brd-on', 'Run the BRD song cycle', brd.enabled)
        if brd_on ~= nil then brd.enabled = brd_on; touched() end
        api.TextDisabled('Pick a song group for each camp; no song names are typed.')
        api.TextDisabled('Song durations come from the server using the BRD gear.')
        if button(api, 'Song groups...', HUB.gold, 170) then
            S.song_groups_open = true
            S.song_group_edit = brd.tank_group
        end
        api.SameLine(0, 6)
        hud_text(api, HUB.dim, string.format('server +%d%% duration · %d songs',
            B.tenant_song_bonus(), #B.tenant_songs()))
        local groups = {}
        for _, group in ipairs(brd.song_groups or {}) do groups[#groups + 1] = group.name end
        local tank = combo(api, 'brd-tank-group', groups, groups, brd.tank_group, 170)
        if tank then brd.tank_group = tank; touched() end
        api.SameLine(0, 6); hud_text(api, HUB.dim, 'Tank camp group')
        local support = combo(api, 'brd-support-group', groups, groups, brd.support_group, 170)
        if support then brd.support_group = support; touched() end
        api.SameLine(0, 6); hud_text(api, HUB.dim, 'Support camp group')
        local mobile = combo(api, 'brd-mobile-group', groups, groups, brd.mobile_group, 170)
        if mobile then brd.mobile_group = mobile; touched() end
        api.SameLine(0, 6); hud_text(api, HUB.dim, 'Mobile group')
        api.TextDisabled('Mobile camp keeps one group; support and melee hear the same songs.')
        local piano_names = { '' }
        for _, name in ipairs(roster_names()) do piano_names[#piano_names + 1] = name end
        hud_text(api, HUB.dim, 'Pianissimo player')
        api.SameLine(0, 6)
        local target = combo(api, 'brd-piano-target', piano_names, piano_names, brd.pianissimo_target, 150)
        if target then brd.pianissimo_target = target; touched() end
        local songs = { '' }
        for _, name in ipairs(B.brd_song_choices()) do songs[#songs + 1] = name end
        hud_text(api, HUB.dim, 'Pianissimo song')
        api.SameLine(0, 6)
        local piano_song = combo(api, 'brd-piano-song', songs, songs, brd.pianissimo_song, 210)
        if piano_song then brd.pianissimo_song = piano_song; touched() end
        api.TextDisabled('Pianissimo is a player target, not a camp.')
        hud_text(api, HUB.dim, 'Nitro set')
        api.SameLine(0, 6)
        local nitro = combo(api, 'brd-nitro', { 'both', 'tank', 'support', 'off' },
            { 'Both sets', 'Tank set only', 'Support set only', 'Never' }, brd.nitro, 200)
        if nitro then brd.nitro = nitro; touched() end
        api.TextDisabled('The Buffs page has the Maintain Nitro switch; this picks the set.')
    end
end

function H.song_groups(api)
    if not S.song_groups_open or not S.profile then return end
    local p = S.profile.support.brd
    local groups = p.song_groups
    if #groups == 0 then S.song_groups_open = false; return end
    local current = nil
    for _, group in ipairs(groups) do
        if group.name == S.song_group_edit then current = group end
    end
    if not current then current = groups[1]; S.song_group_edit = current.name end
    local sw, sh = G.screen(api)
    api.SetNextWindowPos({ math.max(8, sw / 2 - 380), math.max(8, sh / 2 - 280) }, 1)
    api.SetNextWindowSize({ math.min(760, sw - 16), math.min(560, sh - 16) }, 1)
    local close = { true }
    local open = api.Begin('Song groups###fanxi_song_groups', close, 0)
    if close[1] ~= true then S.song_groups_open = false end
    if not open then api.End(); return end
    api.TextDisabled('Create named song groups from the BRD job songs. Assign a group per camp.')
    api.TextDisabled(string.format('Durations are server-computed; gear bonus +%d%%.', B.tenant_song_bonus()))
    api.Separator()
    if api.BeginChild('song-group-list', { 190, -46 }, true) then
        for _, group in ipairs(groups) do
            if api.Selectable(group.name, group.name == S.song_group_edit, 0, { 0, 20 }) then
                S.song_group_edit = group.name
            end
        end
        api.Dummy({ 0, 6 })
        local name = text_field(api, 'song-new-name', S.song_new_name, 148)
        if name then S.song_new_name = text(name, 32) end
        if button(api, 'New group', HUB.cyan, 148) then
            local wanted = text(S.song_new_name, 32)
            if wanted == '' then wanted = 'Group ' .. tostring(#groups + 1) end
            local exists = false
            for _, group in ipairs(groups) do if group.name:lower() == wanted:lower() then exists = true end end
            if not exists and #groups < 12 then
                groups[#groups + 1] = { name = wanted, songs = {} }
                S.song_group_edit = wanted
                S.song_new_name = ''
                touched()
            end
        end
        if #groups > 1 and button(api, 'Delete group', HUB.red, 148) then
            for at = #groups, 1, -1 do
                if groups[at].name == current.name then table.remove(groups, at) end
            end
            S.song_group_edit = groups[1].name
            touched()
        end
        api.EndChild()
    end
    api.SameLine(0, 10)
    if api.BeginChild('song-group-songs', { 0, -46 }, false) then
        hud_text(api, HUB.gold, current.name)
        local choices = B.brd_song_choices()
        if #choices == 0 then
            api.TextDisabled('No server song catalogue for this character yet.')
        else
            for index, name in ipairs(choices) do
                local included = false
                for _, song in ipairs(current.songs) do
                    if song:lower() == name:lower() then included = true break end
                end
                local label = name .. '  ' .. B.song_duration_text(name)
                local value = check(api, 'song-group-song-' .. index, label, included)
                if value ~= nil then
                    if value and not included and #current.songs < 12 then
                        current.songs[#current.songs + 1] = name
                    elseif not value then
                        for at = #current.songs, 1, -1 do
                            if current.songs[at]:lower() == name:lower() then table.remove(current.songs, at) end
                        end
                    end
                    touched()
                end
                if #current.songs >= 12 and not included then
                    api.TextDisabled('12-song limit for this group.')
                    break
                end
            end
        end
        api.Separator()
        local selected = {}
        for _, name in ipairs(current.songs) do selected[#selected + 1] = name end
        hud_text(api, HUB.white, 'Keep: ' .. (#selected > 0 and table.concat(selected, ', ') or '(none)'))
        api.EndChild()
    end
    api.Separator()
    if button(api, 'Close', HUB.cyan, 100) then S.song_groups_open = false end
    api.End()
end

function H.debuff(api)
    local p = S.profile.enfeebles
    section(api, 'Enfeebles for ' .. tenant_label())
    local on = check(api, 'enf-on', 'Land these enfeebles', p.enabled)
    if on ~= nil then p.enabled = on; touched() end
    local max_tries = int_field(api, 'enf-max-tries', p.max_tries, 74, 1, 10, '%d resists')
    if max_tries then p.max_tries = max_tries; touched() end
    api.SameLine(0, 4)
    if button(api, 'Reset tries', HUB.cyan, 88) then
        R.enf_tries = {}
        touched()
    end
    if button(api, 'Suggest from job', HUB.gold, 146) then C.suggest('enfeeble') end
    api.SameLine(0, 6)
    if #p.rows < MAX_ROWS and button(api, 'Add enfeeble', HUB.cyan, 104) then
        p.rows[#p.rows + 1] = { id = row_id(), spell = '', interval = 120 }
        touched()
    end
    local available = {}
    for _, spell in ipairs(known_spells()) do
        local skill = tonumber(spell.skill) or 0
        local name = spell_name(spell)
        local lower = name:lower()
        if skill == 35 and lower ~= 'dispel' and lower ~= 'erase' then
            available[#available + 1] = name
        end
    end
    api.TextDisabled('Chat log watches landing/wear-off; a wear-off makes the next cast immediate.')
    api.TextDisabled('After the resist limit the row stops until you press Reset tries.')
    api.TextDisabled('Job: ' .. tenant_label() .. '; enfeebling spells available:')
    if #available == 0 then
        api.TextDisabled('none — add ability/spell rows manually.')
    else
        for index = 1, math.min(#available, 12), 4 do
            local line = {}
            for at = index, math.min(index + 3, #available) do line[#line + 1] = available[at] end
            api.TextDisabled(table.concat(line, ', '))
        end
    end
    local remove_at = nil
    for index, row in ipairs(p.rows) do
        api.PushID(row.id)
        local spell = text_field(api, 'enf-spell-' .. row.id, row.spell, 180)
        if spell then row.spell = text(spell, 40); touched() end
        api.SameLine(0, 6)
        local interval = int_field(api, 'enf-interval-' .. row.id, row.interval, 92, 1, 3600, '%d s')
        if interval then row.interval = interval; touched() end
        api.SameLine(0, 8)
        if remove_row_button(api, 'enf-remove-' .. row.id) then remove_at = index end
        api.PopID()
    end
    if remove_at then table.remove(p.rows, remove_at); touched() end
    api.TextDisabled('The client does not expose active monster effects.')
    api.TextDisabled('The interval is the re-application clock.')
    api.TextDisabled('A sleeping target is left alone until it wakes.')

    section(api, 'Dispelling')
    local d = S.profile.dispel
    local den = check(api, 'dispel-on', 'Dispel the current target', d.enabled)
    if den ~= nil then d.enabled = den; touched() end
    local spell = text_field(api, 'dispel-spell', d.spell, 170)
    if spell then d.spell = text(spell, 40); touched() end
    api.SameLine(0, 4); hud_text(api, HUB.dim, 'spell')
    local interval = int_field(api, 'dispel-interval', d.interval, 92, 1, 3600, '%d s')
    if interval then d.interval = interval; touched() end
end

-------------------------------------------------------------------------------- rules tab

function H.rules(api)
    local p = S.profile
    section(api, 'Priority')
    api.TextDisabled('Each tick asks the steps in this order; the first one ready acts.')
    for index, key in ipairs(p.priority) do
        api.PushID('prio-' .. index)
        hud_text(api, HUB.white, string.format('%d. %s', index, PRIORITY_LABELS[key] or key))
        api.SameLine(150, 8)
        if api.SmallButton('Up##prio-up' .. index) and index > 1 then
            p.priority[index], p.priority[index - 1] = p.priority[index - 1], p.priority[index]
            touched()
        end
        api.SameLine(0, 4)
        if api.SmallButton('Dn##prio-dn' .. index) and index < #p.priority then
            p.priority[index], p.priority[index + 1] = p.priority[index + 1], p.priority[index]
            touched()
        end
        api.PopID()
    end

    section(api, 'Death')
    local mode = combo(api, 'death-mode', DEATH_MODES,
        { 'Wait for raise / recovery', 'Return to home point' }, p.death.mode, 230)
    if mode then p.death.mode = mode; touched() end
    local wait = int_field(api, 'death-wait', p.death.wait, 94, 0, 600, '%d s wait')
    if wait then p.death.wait = wait; touched() end
    local hp = int_field(api, 'death-hp', p.death.home_point, 92, 1, 128, 'HP %d')
    if hp then p.death.home_point = hp; touched() end
    api.TextDisabled('This server recovers a K.O.\'d character after six seconds.  Home point mode sends')
    api.TextDisabled('//hp <number> as soon as the death is seen; wait mode leaves it to the recovery.')

    section(api, 'Kiting')
    local k = p.kiting
    local ken = check(api, 'kite-on', 'Kiter runs the kite', k.enabled)
    if ken ~= nil then k.enabled = ken; touched() end
    local kmode = combo(api, 'kite-mode', KITE_MODES, { 'Circle the camp', 'Run away', 'Hold camp' }, k.mode, 180)
    if kmode then k.mode = kmode; touched() end
    local radius = yalm_field(api, 'kite-radius', k.radius, 54, 5, 60, 1, '%d', 'yalms')
    if radius then k.radius = radius; touched() end
    local below = int_field(api, 'kite-below', k.below, 98, 0, 100, '%d%% player HP')
    if below then k.below = below; touched() end

    section(api, 'Loot')
    local loot = combo(api, 'loot-mode', LOOT_MODES,
        { 'Free lot', 'Lot everything', 'Pass everything', 'Leader distributes' }, p.loot.mode, 200)
    if loot then p.loot.mode = loot; touched() end
    api.TextDisabled('This build\'s server has no item drops or treasure pool.  The policy is saved with')
    api.TextDisabled('the profile for when the pool exists; the engine never sends a blind /lot.')

    section(api, 'Window')
    local opacity = S.buffers['f:opacity']
    if type(opacity) ~= 'table' then opacity = { S.ui.opacity or 0.95 }; S.buffers['f:opacity'] = opacity end
    opacity[1] = S.ui.opacity or opacity[1]
    if api.SliderFloat('Opacity##battle-opacity', opacity, 0.45, 1, '%.2f') then
        S.ui.opacity = opacity[1]
        if S.profile then S.profile.ui.opacity = S.ui.opacity end
        touched()
    end
    if button(api, 'Reset position', HUB.cyan, 110) then
        S.ui.x, S.ui.y = 360, 80
        S.ui.force = true
        touched()
    end
end

-------------------------------------------------------------------------------- profile tab

function H.profile(api)
    local p = S.profile
    section(api, 'Profile')
    local name = text_field(api, 'profile-name', p.name, 340)
    if name then p.name = text(name, 80); touched() end
    api.SameLine(0, 8)
    if button(api, 'Save', HUB.start, 66) then
        local ok, err = C.save(p.name)
        if ok then S.dirty = false; show_hub(false) else note('error', 'Battle: ' .. tostring(err)) end
    end
    api.SameLine(0, 4)
    if button(api, 'New', HUB.cyan, 58) then
        C.new_profile(nil)
        S.dirty = true
    end
    api.SameLine(0, 4)
    if button(api, 'Refresh', HUB.dim, 70) then C.list() end
    api.TextDisabled('The default name is the zone and a timestamp; //battle save writes this file under')
    api.TextDisabled(xi.paths and (xi.paths.data .. 'battle') or 'the data folder')

    section(api, 'Saved')
    if #S.profiles == 0 then
        api.TextDisabled('No saved battle profiles for this character yet.')
    else
        for _, item in ipairs(S.profiles) do
            api.PushID('profile-' .. item.file)
            hud_text(api, HUB.white, item.name)
            api.SameLine(330, 6)
            hud_text(api, HUB.dim, item.zone_name ~= '' and item.zone_name or ('zone ' .. tostring(item.zone)))
            api.SameLine(470, 6)
            if api.SmallButton('Load##load-' .. item.file) then
                C.load(item.name)
                show_hub(true)
            end
            api.SameLine(0, 4)
            if api.SmallButton('Delete##del-' .. item.file) then
                local ok = C.delete(item.name)
                if ok then S.dirty = false end
            end
            api.PopID()
        end
    end

    section(api, 'Activity')
    local first = math.max(1, #S.notes - 7)
    for index = first, #S.notes do
        local line = S.notes[index]
        local color = line.kind == 'error' and HUB.red or line.kind == 'action' and HUB.green or HUB.dim
        hud_text(api, color, line.text)
    end
end

-------------------------------------------------------------------------------- drawing

local function screen_size(api)
    local width, height = 1280, 720
    local ok, io = pcall(api.GetIO)
    if ok and io and io.DisplaySize then
        width = tonumber(io.DisplaySize.x) or width
        height = tonumber(io.DisplaySize.y) or height
    end
    return width, height
end

-- Returns the memory-space axes that match the camera.  FFXI client positions use X/Y as the
-- ground plane and Z as height, while the renderer's world may use either Y-up (memory x, z, y)
-- or Z-up (memory x, y, z).  Projecting the player's own position through the camera and taking
-- whichever mapping lands near the centre tells the two apart without a data table.
function G.choose_axis(api)
    if G.axis_value then return G.axis_value end
    local matrix = G.camera(clock())
    if not matrix then return nil end
    local pos = B.self_pos()
    if not pos then return nil end
    local width, height = screen_size(api)
    local function candidate(axis)
        local wx, wy, wz
        if axis == 'xzy' then wx, wy, wz = pos.x, pos.z, pos.y
        else wx, wy, wz = pos.x, pos.y, pos.z end
        local sx, sy = project_point(matrix, wx, wy, wz, width, height)
        if not sx or sx < -8 or sx > width + 8 or sy < -8 or sy > height + 8 then return nil end
        -- Use both ground axes: looking almost along one of them makes that axis's screen step
        -- tiny even though the camera is fine, so the maximum step is the meaningful scale.
        local ax, ay, bx, by
        if axis == 'xzy' then
            ax, ay = project_point(matrix, pos.x + 5, pos.z, pos.y, width, height)
            bx, by = project_point(matrix, pos.x, pos.z, pos.y + 5, width, height)
        else
            ax, ay = project_point(matrix, pos.x + 5, pos.y, pos.z, width, height)
            bx, by = project_point(matrix, pos.x, pos.y + 5, pos.z, width, height)
        end
        local scale = 0
        if ax then scale = math.max(scale, math.sqrt((ax - sx) ^ 2 + (ay - sy) ^ 2)) end
        if bx then scale = math.max(scale, math.sqrt((bx - sx) ^ 2 + (by - sy) ^ 2)) end
        if scale <= 2 then return nil end
        return sx, sy, scale
    end
    -- The client's memory X/Y are the ground plane and Z is height; the main camera maps that as
    -- world (X, Z, Y).  This was measured against the live main camera: xzy put the player at
    -- (942, 544) in a 1920x1080 frame, xyz at (1048, 679).  Only fall back to xyz if xzy is not
    -- on screen at all (a different renderer), never choose it by a centre-distance score.
    local sx, sy, scale = candidate('xzy')
    if sx then
        G.axis_value = 'xzy'
        return 'xzy'
    end
    sx, sy, scale = candidate('xyz')
    if sx then
        G.axis_value = 'xyz'
        return 'xyz'
    end
    return nil
end

function G.world_of(pos, axis)
    if not pos then return nil end
    axis = axis or 'xzy'
    if axis == 'xyz' then return pos.x, pos.y, pos.z end
    return pos.x, pos.z, pos.y
end

function G.memory_of(wx, wy, wz, axis)
    if axis == 'xyz' then return { x = wx, y = wy, z = wz } end
    return { x = wx, y = wz, z = wy }
end

function G.project_mem(pos, api)
    local axis = G.choose_axis(api)
    if not axis then return nil end
    local matrix = G.camera(clock())
    if not matrix then return nil end
    local width, height = screen_size(api)
    local wx, wy, wz = G.world_of(pos, axis)
    return project_point(matrix, wx, wy, wz, width, height)
end

function G.unproject_mem(sx, sy, ground_z, api)
    local axis = G.choose_axis(api)
    if not axis then return nil end
    local matrix = G.camera(clock())
    if not matrix then return nil end
    local width, height = screen_size(api)
    if axis == 'xzy' then
        local wx, wy, wz = G.unproject(sx, sy, ground_z, api)
        if not wx then return nil end
        return G.memory_of(wx, wy, wz, axis)
    end
    local ax, ay, az = unproject(matrix, sx, sy, 0.0, width, height)
    local bx, by, bz = unproject(matrix, sx, sy, 1.0, width, height)
    if not ax or not bx then return nil end
    local dz = bz - az
    if math.abs(dz) < 1e-6 then return nil end
    local t = (ground_z - az) / dz
    if t < 0 then return nil end
    local wx, wy = ax + (bx - ax) * t, ay + (by - ay) * t
    return G.memory_of(wx, wy, ground_z, axis)
end

local function ring_points(api, center, radius, height)
    local points = {}
    for index = 0, 47 do
        local angle = index / 48 * math.pi * 2
        local point = {
            x = center.x + math.cos(angle) * radius,
            y = center.y + math.sin(angle) * radius,
            z = (center.z or 0) + (height or 0.12),
        }
        local sx, sy = G.project_mem(point, api)
        if not sx then return nil end
        points[#points + 1] = { sx, sy }
    end
    return points
end

-- A persistent camp radar for play, because the world is drawn through shader cameras the host's
-- fixed-function state does not expose reliably.  The big top-down map stays in the hub's Camp tab;
-- this small one is the always-on "where is camp / where am I / is the mob inside" view.
--[[ The zone map behind the camp view: the image is fitted into the drawing area, and the camp,
support camp, party, mobs and the player are placed with the map's own placement values.  A camp
radius is 1..50 yalms, which is a couple of pixels at whole-zone scale, so the ring keeps a visible
minimum while the text row below still states the real radius. ]]
do
function H.draw_zone_map(draw, map, self, tank_on, support_on, tr, sr, x, y, w, h, range)
    -- A player-centred window on the map, FFXIDB-style: `range` is how many yalms fit across the
    -- panel.  The window is clamped to the image, so near a zone edge the view stops there
    -- instead of showing empty space, and it falls back to the whole map when the range is
    -- larger than the map itself.
    local tex_per_yalm = map.scale * map.w / 256
    local vw = math.min(map.w, math.max(16, (tonumber(range) or 800) * tex_per_yalm))
    local vh = math.min(map.h, vw * (map.h / map.w))
    local ax = (map.ox + map.scale * self.x) / 256 * map.w
    local ay = (map.oy - map.scale * self.y) / 256 * map.h
    local left = clamp(ax - vw * 0.5, 0, math.max(0, map.w - vw))
    local top = clamp(ay - vh * 0.5, 0, math.max(0, map.h - vh))
    local s = math.min(w / vw, h / vh)
    local mw, mh = vw * s, vh * s
    local mx, my = x + (w - mw) * 0.5, y + (h - mh) * 0.5
    draw:AddRectFilled({ x, y }, { x + w, y + h }, rgba({ 0, 0, 0, 1 }, 0.6), 5)
    draw:AddImage(map.texture, { mx, my }, { mx + mw, my + mh },
        { left / map.w, top / map.h }, { (left + vw) / map.w, (top + vh) / map.h },
        rgba(HUB.white, 0.97))
    draw:AddRect({ mx, my }, { mx + mw, my + mh }, rgba(HUB.cyan, 0.22), 4, 0, 1)
    local function at(pos)
        if not pos then return nil end
        local u = (map.ox + map.scale * pos.x) / 256 * map.w - left
        local v = (map.oy - map.scale * pos.y) / 256 * map.h - top
        if u < -2 or u > vw + 2 or v < -2 or v > vh + 2 then return nil end
        return mx + u * s, my + v * s
    end
    local yalm = map.scale * map.w / 256 * s
    if tank_on then
        local px, py = at(B.camp_pos('tank'))
        if px then
            draw:AddCircle({ px, py }, math.max(5, tr * yalm), rgba(HUB.cyan, 0.75), 48, 1.5)
            draw:AddLine({ px - 4, py }, { px + 4, py }, rgba(HUB.cyan, 0.9), 1)
            draw:AddLine({ px, py - 4 }, { px, py + 4 }, rgba(HUB.cyan, 0.9), 1)
        end
    end
    if support_on then
        local px, py = at(B.camp_pos('support'))
        if px then
            draw:AddCircle({ px, py }, math.max(4, sr * yalm), rgba(HUB.gold, 0.85), 48, 1.2)
            draw:AddLine({ px - 3, py - 3 }, { px + 3, py + 3 }, rgba(HUB.gold, 0.9), 1)
            draw:AddLine({ px - 3, py + 3 }, { px + 3, py - 3 }, rgba(HUB.gold, 0.9), 1)
        end
    end
    for _, mob in ipairs(B.mobs()) do
        local px, py = at(mob.pos)
        if px then
            draw:AddCircleFilled({ px, py }, 3, rgba(mob.claim and HUB.gold or HUB.red, 0.95))
        end
    end
    local target = B.self_target()
    if target and target >= 0 then
        local pos = position(target)
        local px, py = at(pos)
        if px then draw:AddCircle({ px, py }, 5, rgba(HUB.gold, 0.95), 16, 1.5) end
    end
    for _, member in ipairs(B.members('alliance')) do
        if member.slot ~= 0 then
            local index = entity_by_name(member.name)
            local pos = index and position(index) or nil
            local px, py = nil, nil
            if pos then px, py = at(pos) end
            if px then draw:AddCircleFilled({ px, py }, 2.5, rgba(HUB.green, 0.9)) end
        end
    end
    local px, py = at(self)
    if px then
        local hx, hy = math.sin(self.heading or 0), -math.cos(self.heading or 0)
        draw:AddLine({ px, py }, { px + hx * 11, py + hy * 11 }, rgba(HUB.green, 0.95), 2)
        draw:AddCircleFilled({ px, py }, 4, rgba(HUB.green, 0.95))
        -- FFXIDB's target line: where the current target is, when it is in the window.
        local target = B.self_target()
        local tx, ty = nil, nil
        if target and target >= 0 then
            local tpos = position(target)
            if tpos then tx, ty = at(tpos) end
        end
        if tx then draw:AddLine({ px, py }, { tx, ty }, rgba(HUB.red, 0.55), 1) end
    end
    -- A camp outside the local window keeps a dot on the panel edge, so its direction is never
    -- lost while the range is short.
    local function edge(pos, color)
        if not pos then return end
        local tx = (map.ox + map.scale * pos.x) / 256 * map.w
        local ty = (map.oy - map.scale * pos.y) / 256 * map.h
        if tx >= left and tx <= left + vw and ty >= top and ty <= top + vh then return end
        local ex = clamp(mx + (tx - left) * s, mx + 8, mx + mw - 8)
        local ey = clamp(my + (ty - top) * s, my + 8, my + mh - 8)
        draw:AddCircleFilled({ ex, ey }, 3, color)
        draw:AddCircle({ ex, ey }, 5, color, 12, 1)
    end
    if tank_on then edge(B.camp_pos('tank'), rgba(HUB.cyan, 0.85)) end
    if support_on then edge(B.camp_pos('support'), rgba(HUB.gold, 0.85)) end
end
end


function H.camp_radar(api)
    local p = S.profile
    local cfg = p and p.camp_hud
    if not cfg or not cfg.show then return end
    local tank = p.camp
    local support = p.support_camp
    local tank_on = tank.set and tank.show
    local support_on = support.set and support.show
    local self = B.self_pos()
    if not self then return end
    local center = (tank_on and B.camp_pos('tank')) or (support_on and B.camp_pos('support')) or self
    local zone = B.zone()
    local map = cfg.map ~= false and B.zone_map(zone) or nil
    local sw, sh = G.screen(api)
    local width = clamp(cfg.w, 380, 520, 380)
    -- With a map the drawing area is square, so the window has to be tall enough for it plus the
    -- three button rows below; without one the old 176px radar strip keeps its old minimum.
    local min_h = 320
    if map then
        min_h = math.min(math.max(120, width - 18), 420) + 170
        if min_h > 600 then min_h = 600 end
    end
    local height = clamp(cfg.h, min_h, 600, min_h)
    if cfg.w < 380 then cfg.w = 380; S.camp_hud_apply = true end
    if width < 380 then width = 380; cfg.w = width; S.camp_hud_apply = true end
    if map then S.map_height = min_h end
    if cfg.h < min_h then cfg.h = min_h; S.camp_hud_apply = true end
    -- Leaving a mapped zone (or switching the map off) gives back the height the map needed, but
    -- only when the height is still the one the map forced: a size the player picked is kept.
    if not map and S.map_height and math.abs((cfg.h or 0) - S.map_height) < 1 then
        cfg.h = 320
        S.map_height = nil
        S.camp_hud_apply = true
        height = clamp(cfg.h, min_h, 600, min_h)
    end
    local applying = S.camp_hud_apply
    if applying then
        cfg.x = clamp(cfg.x, 0, math.max(0, sw - width), 16)
        -- A taller window (the map) must still fit above the bottom edge when it starts in the
        -- lower half of the screen.
        cfg.y = cfg.y > 0 and clamp(cfg.y, 0, math.max(0, sh - height), sh * 0.52)
            or math.max(0, math.floor(math.min(sh * 0.52, sh - height)))
        api.SetNextWindowPos({ cfg.x, cfg.y }, 1)
        api.SetNextWindowSize({ width, height }, 1)
        S.camp_hud_apply = false
    end
    local heading = 'Battle HUD'
    if cfg.collapsed then
        local status = B.status()
        local summary = S.running and 'RUNNING' or 'STOPPED'
        if status.target then
            summary = string.format('%s  ·  %s %.0f%%', summary, status.target.name,
                status.target.hpp)
        end
        heading = heading .. '  ' .. summary
    end
    local close = { cfg.show }
    api.SetNextWindowCollapsed(cfg.collapsed == true, S.camp_hud_restore and 1 or 4)
    local open = api.Begin(heading .. '###fanxi_camp_hud', close, 256)
    local wx, wy = api.GetWindowPos()
    S.camp_hud_collapsed = api.IsWindowCollapsed()
    if S.camp_hud_restore then
        if S.camp_hud_collapsed == (cfg.collapsed == true) then S.camp_hud_restore = false end
    elseif cfg.collapsed ~= S.camp_hud_collapsed then
        cfg.collapsed = S.camp_hud_collapsed
        touched()
    end
    if not S.camp_hud_collapsed and close[1] ~= cfg.show then cfg.show = close[1]; touched() end
    if not applying and wx and wy
        and (math.abs((wx or cfg.x) - cfg.x) > 0.5 or math.abs((wy or cfg.y) - cfg.y) > 0.5) then
        cfg.x, cfg.y = math.floor(wx or cfg.x), math.floor(wy or cfg.y)
        touched()
    end
    if not open then api.End(); return end
    local ww, wh = api.GetWindowSize()
    if not applying
        and (math.abs((ww or width) - width) > 0.5 or math.abs((wh or height) - height) > 0.5) then
        cfg.w, cfg.h = math.floor(ww or width), math.floor(wh or height)
        touched()
    end
    local content_w = math.max(120, (ww or width) - 18)
    local radar_h = map and math.min(content_w, 420) or 176
    local x, y = api.GetCursorScreenPos()
    api.Dummy({ content_w, radar_h })
    local draw = api.GetWindowDrawList()
    local tr = math.max(1, B.camp_radius('tank'))
    local sr = math.max(1, B.camp_radius('support'))
    if map then
        -- Mouse wheel over the map zooms the local window (FFXIDB's wheel zoom).
        local _, io = pcall(api.GetIO)
        local wheel = io and tonumber(io.MouseWheel) or 0
        if wheel and wheel ~= 0 and api.IsMouseHoveringRect({ x, y }, { x + content_w, y + radar_h }) then
            cfg.range = clamp((cfg.range or 800) * (wheel > 0 and 0.85 or 1.18), 150, 4000, 800)
            touched()
        end
        H.draw_zone_map(draw, map, self, tank_on, support_on, tr, sr, x, y, content_w, radar_h, cfg.range)
    else
        local size = math.min(content_w, radar_h)
        local cx, cy = x + content_w * 0.5, y + radar_h * 0.52
        local span = math.max(math.max(tr, sr) * 1.5, 22)
        local scale = (size * 0.38) / span
        local function place(pos)
            return cx + (pos.x - center.x) * scale, cy - (pos.y - center.y) * scale
        end
        if tank_on then
            local sx, sy = place(center)
            draw:AddCircle({ sx, sy }, tr * scale, rgba(HUB.cyan, 0.7), 64, 1.5)
            draw:AddCircleFilled({ sx, sy }, 2.5, rgba(HUB.cyan, 0.9))
        end
        if support_on then
            local pos = B.camp_pos('support')
            if pos then
                local sx, sy = place(pos)
                draw:AddCircle({ sx, sy }, sr * scale, rgba(HUB.gold, 0.8), 64, 1.2)
                draw:AddCircleFilled({ sx, sy }, 2, rgba(HUB.gold, 0.9))
            end
        end
        local dx, dy = self.x - center.x, self.y - center.y
        local px, py = dx * scale, -dy * scale
        local limit = size * 0.42
        local plen = math.sqrt(px * px + py * py)
        local ex, ey = cx + px, cy + py
        if plen > limit and plen > 0 then
            ex, ey = cx + px / plen * limit, cy + py / plen * limit
        end
        local hx, hy = math.sin(self.heading or 0), -math.cos(self.heading or 0)
        draw:AddLine({ ex, ey }, { ex + hx * 11, ey + hy * 11 }, rgba(HUB.green, 0.95), 2)
        draw:AddCircleFilled({ ex, ey }, 4, rgba(HUB.green, 0.95))
        local tindex = B.self_target()
        if tindex and tindex >= 0 then
            local mob = position(tindex)
            if mob then
                local mx, my = (mob.x - center.x) * scale, -(mob.y - center.y) * scale
                local mlen = math.sqrt(mx * mx + my * my)
                if mlen > limit and mlen > 0 then mx, my = mx / mlen * limit, my / mlen * limit end
                draw:AddCircleFilled({ cx + mx, cy + my }, 3.5, rgba(HUB.gold, 0.95))
            end
        end
    end
    api.PushFont(nil, 10)
    if map then
        draw:AddRectFilled({ x, y }, { x + 56, y + 15 }, rgba({ 0, 0, 0, 1 }, 0.42), 3)
    end
    draw:AddText({ x + 4, y + 4 }, rgba(HUB.cyan, 0.9), 'CAMPS')
    if map then
        draw:AddText({ x + content_w - 42, y + 4 }, rgba(HUB.dim, 0.9),
            string.format('%dy', math.floor((cfg.range or 800) + 0.5)))
    end
    local tank_dist = math.sqrt((self.x - tank.x) ^ 2 + (self.y - tank.y) ^ 2)
    local support_dist = support.set and math.sqrt((self.x - support.x) ^ 2 + (self.y - support.y) ^ 2) or nil
    local inside = (tank.set and tank_dist <= tr) or (support.set and support_dist and support_dist <= sr)
    if map then
        draw:AddRectFilled({ x, y + radar_h - 17 }, { x + content_w, y + radar_h }, rgba({ 0, 0, 0, 1 }, 0.55), 0)
    end
    draw:AddText({ x + 4, y + radar_h - 16 }, rgba(inside and HUB.green or HUB.dim, 0.95),
        string.format('T%.0f %s  ·  S%s', tr,
            tank.set and string.format('%.0fy', tank_dist) or '-',
            support.set and string.format('%.0f %.0fy', sr, support_dist) or ' uses T'))
    api.PopFont()
    api.Separator()
    local bw = math.max(46, (content_w - 14) / 4)
    if button(api, 'Start##camp-hud', HUB.start, bw) then B.start() end
    api.SameLine(0, 4)
    if button(api, 'Stop##camp-hud', HUB.stop, bw) then B.stop() end
    api.SameLine(0, 4)
    if button(api, 'Follow##camp-hud', HUB.cyan, bw) then
        B.stop()
        local ok, err = pcall(xi.chat.run, '//follow me all', 1)
        if not ok then note('error', 'Battle: ' .. tostring(err))
        else note('action', 'Battle: stopped; team ordered to follow me.') end
    end
    api.SameLine(0, 4)
    if button(api, 'Menu##camp-hud', HUB.gold, bw) then show_hub(true) end
    local bw3 = math.max(44, (content_w - 12) / 4)
    if button(api, 'Set tank##camp-hud', HUB.cyan, bw3) then camp_set_here('tank') end
    api.SameLine(0, 4)
    if button(api, 'Set support##camp-hud', HUB.gold, bw3) then camp_set_here('support') end
    api.SameLine(0, 4)
    if button(api, 'Clear camps##camp-hud', HUB.red, bw3) then
        camp_clear('tank')
        camp_clear('support')
    end

    if S.camp_hud_edit then
        api.TextDisabled('MOVE: drag title bar; Done.')
    else
        api.TextDisabled('Follow me stops Battle.')
        api.TextDisabled('The team follows you.')
    end
    api.End()
end

function H.overlay(api)
    if not S.visible or S.camp_hud_edit then H.camp_radar(api) end
    if S.song_groups_open then H.song_groups(api) end
end

local function tab_content(api)
    local tab = S.tab
    if tab == 'camp' then return H.camp(api) end
    if tab == 'engage' then return H.engage(api) end
    if tab == 'skillchain' then return H.skillchain(api) end
    if tab == 'pull' then return H.pull(api) end
    if tab == 'heal' then return H.heal(api) end
    if tab == 'buff' then return H.buff(api) end
    if tab == 'support' then return H.support(api) end
    if tab == 'debuff' then return H.debuff(api) end
    if tab == 'rules' then return H.rules(api) end
    if tab == 'profile' then return H.profile(api) end
    return H.roster(api)
end

function H.window(api)
    local width, height = screen_size(api)
    local w = math.min(800, math.max(560, width - 16))
    local h = math.min(820, math.max(380, height - 16))
    local x = math.max(4, math.min(S.ui.x or 360, width - w - 4))
    local y = math.max(4, math.min(S.ui.y or 80, height - h - 4))
    -- FirstUseEver normally keeps a drag, but a show/reset must move the window back to the
    -- profile's saved spot even though ImGui still remembers the last screen position.
    api.SetNextWindowPos({ x, y }, S.ui.force and 1 or 4)
    api.SetNextWindowSize({ w, h }, 1)
    api.SetNextWindowBgAlpha(S.ui.opacity or 0.95)
    S.ui.force = false
    local open = api.Begin('Battle###fanxi_battle_hub', nil, 32 + 256)
    if open then
        local status = B.status()
        local running = S.running
        hud_text(api, running and HUB.green or HUB.dim,
            running and 'RUNNING' or 'STOPPED')
        api.SameLine(0, 10)
        hud_text(api, HUB.white, S.profile.name ~= '' and S.profile.name or 'unsaved profile')
        if S.dirty then
            api.SameLine(0, 6)
            hud_text(api, HUB.gold, '•')
        end
        api.SameLine(0, 12)
        hud_text(api, HUB.dim, status.role_label and ('role: ' .. status.role_label) or 'role: unassigned')
        if status.target then
            api.SameLine(0, 10)
            hud_text(api, HUB.white, string.format('%s %.0f%%%s', status.target.name, status.target.hpp,
                status.target.claimed_by and (' (' .. status.target.claimed_by .. ')') or ''))
        end
        api.SameLine(0, 12)
        if not S.remote_edit then
            if button(api, running and 'Stop' or 'Start', running and HUB.stop or HUB.start, 62) then
                if running then B.stop() else B.start() end
            end
        else
            local remote_running = S.profile.engine and S.profile.engine.running
            if button(api, remote_running and 'Stop on box' or 'Start on box', remote_running and HUB.stop or HUB.start, 112) then
                S.profile.engine.running = not remote_running
                touched()
            end
        end
        api.SameLine(0, 5)
        if button(api, 'Save', HUB.cyan, 58) then
            local ok, err = C.save(S.profile.name)
            if ok then S.dirty = false; show_hub(false) else note('error', 'Battle: ' .. tostring(err)) end
        end
        api.SameLine(0, 5)
        if button(api, 'Hide', HUB.dim, 56) then show_hub(false) end
        if not status.camp then
            api.SameLine(0, 10)
            hud_text(api, HUB.gold, 'set a camp')
        end
        if #status.paused > 0 then
            api.SameLine(0, 8)
            hud_text(api, HUB.gold, 'paused: ' .. table.concat(status.paused, ','))
        end
        if S.team and #S.team > 0 then
            local current = S.remote_edit and S.remote_edit.name or self_name()
            local values, labels = {}, {}
            local found = false
            for _, character in ipairs(S.team) do
                -- The team list is every character the account owns.  The selector follows the
                -- live roster: a three-box night lists three names, and the other three stay
                -- editable (with their saved profiles) only after they log in.  A server
                -- without a live roster reports online_known = false, so show the whole team.
                local live = character.name == current or B.team_online(character.name)
                if live then
                    values[#values + 1] = character.name
                    local label = character.name .. (character.profile and '' or ' (new)')
                    if S.team_online_known and not B.team_online(character.name) then
                        label = label .. ' (offline)'
                    end
                    labels[#labels + 1] = label
                    if character.name == current then found = true end
                end
            end
            if not found and current ~= '' then values[#values + 1] = current; labels[#labels + 1] = current end
            if #values > 0 then
                hud_text(api, HUB.dim, 'EDITING')
                api.SameLine(0, 6)
                local picked = combo(api, 'team-edit', values, labels, current, 150)
                if picked then B.team_switch(picked) end
                if S.remote_edit then
                    api.SameLine(0, 8)
                    hud_text(api, HUB.gold, 'engine paused; Save writes to the server')
                end
            elseif S.team_online_known then
                hud_text(api, HUB.dim, 'No team characters are online.')
            end
        end
        api.Separator()
        if api.BeginChild('battle-nav', { 160, 0 }, true) then
            local group = nil
            for _, item in ipairs(HUB_TABS) do
                if item.group ~= group then
                    group = item.group
                    if group ~= HUB_TABS[1].group then api.Dummy({ 0, 6 }) end
                    hud_text(api, HUB.gold, group)
                end
                local selected = S.tab == item.key
                if api.Selectable(item.label, selected, 0, { 0, 20 }) then S.tab = item.key end
            end
            api.Dummy({ 0, 8 })
            api.Separator()
            api.TextDisabled('//battle help')
            api.EndChild()
        end
        api.SameLine(0, 8)
        if api.BeginChild('battle-content', { 0, 0 }, false) then
            local ok, err = pcall(tab_content, api)
            if not ok then
                note('error', 'Battle hub: ' .. tostring(err))
                hud_text(api, HUB.red, tostring(err))
            end
            api.EndChild()
        end
        local now = clock()
        if api.IsMouseReleased(0) then
            local px, py = api.GetWindowPos()
            local sx, sy = api.GetWindowSize()
            if px and py then S.ui.x, S.ui.y = math.floor(px), math.floor(py) end
            if sx and sy then S.ui.w, S.ui.h = math.floor(sx), math.floor(sy) end
        end
    end
    api.End()
end

function M.visible()
    return S.visible
end

-- The in-game "Battle HUD" is the camp radar/roster window (H.camp_radar), not the full
-- Battle editor opened by //battle.  The Control room switch mirrors its cfg.show.
function M.camp_hud_visible()
    return S.profile ~= nil and S.profile.camp_hud ~= nil
        and S.profile.camp_hud.show == true
end

function M.overlay_on()
    if S.place or S.visible or S.camp_hud_edit then return true end
    if not S.profile then return false end
    -- The HUD has its own show toggle. Clearing camps must not close it; only the X (or the
    -- Camp page toggle) changes cfg.show.
    return S.profile.camp_hud.show == true
end

function M.draw(api)
    if not S.installed or not S.profile then return end
    if api == nil then return end
    local ok, err = pcall(H.overlay, api)
    if not ok and not S.ui.warned then
        S.ui.warned = true
        note('error', 'Battle overlay: ' .. tostring(err))
    end
    if not S.visible then return end
    local ok2, err2 = pcall(H.window, api)
    if not ok2 and not S.ui.warned then
        S.ui.warned = true
        note('error', 'Battle hub: ' .. tostring(err2))
    end
end

-------------------------------------------------------------------------------- keyboard placement

local function key_code(name)
    local ok, code = pcall(xi.input.code, name)
    return ok and tonumber(code) or -1
end

local function place_key(code, down)
    if not S.place or not down then return false end
    if S.ctx and S.ctx.chat_open and S.ctx.chat_open() then return false end
    if code == key_code('enter') then
        place_commit()
        return true
    end
    if code == key_code('escape') then
        place_cancel()
        return true
    end
    local step = 0.5
    local x, y = S.place.x, S.place.y
    if code == key_code('up') then
        y = y + step
    elseif code == key_code('down') then
        y = y - step
    elseif code == key_code('left') then
        x = x - step
    elseif code == key_code('right') then
        x = x + step
    else
        return false
    end
    S.place.x, S.place.y = x, y
    S.place.manual_at = clock() + 1.0
    S.place.from_mouse = false
    return true
end

-------------------------------------------------------------------------------- lifecycle

function M.install(ctx)
    S.ctx = ctx
    S.game = xi.game
    S.res = xi.res
    S.installed = true
    S.ui.opacity = 0.95
    S.notes = {}
    C.refresh_character()
    local ok = select(1, C.resume())
    if ok and S.profile then
        S.visible = S.profile.ui.show == true
        S.ui.x, S.ui.y = S.profile.ui.x or 360, S.profile.ui.y or 80
        S.ui.opacity = S.profile.ui.opacity or 0.95
        S.ui.force = true
    end
    xi.events.on('key', function(e)
        local ok2, handled = pcall(place_key, e.key, e.down)
        if ok2 and handled then e.blocked = true end
    end)
    xi.events.on('text_in', function(e)
        local text = tostring(e.modified or e.data or ''):lower()
        if text == '' or not S.profile then return end
        for _, row in ipairs(S.profile.enfeebles.rows) do
            local name = tostring(row.spell or ''):lower()
            if name ~= '' and text:find(name, 1, true) then
                local key = 'enf:' .. name
                if text:find('resist', 1, true) or text:find('no effect', 1, true) then
                    R.enf_tries[key] = (tonumber(R.enf_tries[key]) or 0) + 1
                elseif text:find('wears off', 1, true) or text:find('no longer', 1, true)
                    or text:find('fades', 1, true) then
                    R.enf_tries[key] = 0
                    R.enf_due[key] = true
                elseif text:find('lands', 1, true) or text:find('inflicts', 1, true) then
                    R.enf_tries[key] = 0
                end
            end
        end
    end)
    xi.events.on('frame', function()
        local ok2, err = pcall(B.tick)
        if not ok2 and not S.ui.warned then
            S.ui.warned = true
            note('error', 'Battle: ' .. tostring(err))
        end
    end)
    xi.events.on('unload', function()
        S.running = false
        pcall(B.stop_move)
        pcall(B.forget_map)
    end)
    note('info', 'Battle: //battle opens the hub; //battle help lists the commands.')
    return true
end

function M.shutdown()
    S.running = false
    pcall(B.stop_move)
    pcall(B.forget_map)
    if S.profile then
        S.profile.ui.x, S.profile.ui.y = S.ui.x, S.ui.y
        S.profile.ui.opacity = S.ui.opacity
        S.profile.ui.show = S.visible
    end
end

-- The map layer is exercised by tests/addons/battletest without a logged-in client.
M.draw_zone_map = H.draw_zone_map
-- Read-only roster views: a role's saved names that are in the live party/alliance.  The addon
-- harness uses this to prove the hub does not count logged-out boxes; the UI uses the same
-- helpers through B.
M.roster_online = B.roster_online
M.active_role_name = B.active_role_name
M.melee_slot = B.melee_slot
-- Read-only ability timing: the hub's Nitro status line and the harness use these.
M.ability_state = B.ability_state
M.ability_ready = B.ability_ready
M.ability_remaining = B.ability_remaining
-- The harness drives the Nitro sequence directly; the engine calls the same function.
M.brd_maybe_nitro = brd_maybe_nitro
M.nitro_state = function()
    return { step = R.brd.nitro_step, at = R.brd.nitro_at, issued_at = R.brd.nitro_issued_at }
end

return M
