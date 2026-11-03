# Protocol

Fanxi's game gateway speaks the FINAL FANTASY XI private-server protocol that `host64` already
implements. This document describes the subset Fanxi implements and where the boundaries are.
It is a developer reference, not a specification for the game.

## Ports and listeners

| Port | Socket | Purpose |
|---|---|---|
| 54231 | TCP + TLS | Auth exchange |
| 54230 | TCP | Login data connection |
| 54001 | TCP | Lobby |
| 54230 | UDP | Zone |
| 54002 | TCP | Search (`/sea all`, `/sea <name>`) |

These are configurable with `FANXI_*_PORT`; the launcher passes the same values to `host64`.

## 1. Auth (TLS, JSON)

The client opens TLS (it does not verify the server certificate), sends one JSON object, and
reads one JSON reply. The request, as `host/lsb_login.c` builds it:

```json
{
  "command": 16,
  "new_password": "",
  "otp": "",
  "password": "…",
  "trust_this_computer": false,
  "trust_token": "",
  "username": "aria",
  "version": [2, 2, 0],
  "login_token": "…"
}
```

`login_token` is present when `host64 --login-token` was used; it stands in for the password and
one-time code (the launcher flow). Fanxi ignores `command`, `trust_token`, `trust_this_computer`
and `version`, and does not implement one-time codes or trust tokens.

Success:

```json
{
  "result": 1,
  "account_id": 1,
  "session_hash": [-85, 12, 99, …]
}
```

`session_hash` is 16 numbers, signed bytes (`-128..127`), representing 16 random bytes. Fanxi
stores the raw bytes in `game_sessions`, replacing any previous session for the account.

Failures use the known result codes:

| `result` | Meaning |
|---|---|
| 0 | account suspended/banned, locked, or generic failure; `error_message` says why |
| 2 | invalid username or password |
| 0x0A | already signed in (Fanxi replaces the session instead, so it does not send this) |
| 0x13 | trust token invalid (Fanxi does not issue trust tokens) |
| 0x14 | launch token invalid, used or expired |

A launch token also carries the character id chosen in the launcher. The lobby lists only that
character for the session, so a multibox client opens the intended mule.

An `error_message` is shown by the client's sign-in screen/log.

## 2. Login data (TCP)

The client connects to 54230 and sends a 28-byte packet:

```
0xFE, 11 zero bytes, 16-byte session hash, 4 zero bytes
```

Fanxi looks up the session in `game_sessions` and keeps the connection open. Later:

- `0x01` (who is this) → Fanxi replies with `0xA1`: account id (LE u32 at offset 1), server IPv4
  (offset 5), session hash (offset 12). This mirrors what the client's data thread expects.
- `0x02` / `0x15` (the key) → `0xA2`: `md5(session_hash)` (offset 1), then the constant
  `58 E0 5D AD` (offset 17). The client's own zone key follows.
- `0xA2` + 20 bytes from the client → Fanxi records the account's zone key and uses it for the
  next zone session. (The client sends this on current servers.)

If the session is unknown or expired, the connection is closed.

## 3. Lobby (TCP)

Every lobby packet starts with a 28-byte header:

| Offset | Size | Meaning |
|---|---|---|
| 0 | 4 | packet size, little-endian |
| 4 | 4 | `IXFF` |
| 8 | 1 | command |
| 9–11 | 3 | padding |
| 12 | 16 | session hash |
| 28 | … | body |

Fanxi implements:

| Command | Reply | Meaning |
|---|---|---|
| `0x26` | `0x05` | version/expansions; returns view key `0xAD5DE04F` and expansion masks |
| `0x1F` | `0x20` | character list: count + 140-byte records |
| `0x24` | `0x23` | world list: world id/name |
| `0x07` | `0x0B` | choose character: returns content id, name, zone, IP, zone port, search port; prepares the zone hand-off |
| `0x14`, `0x21`, `0x22`, `0x28` | `0x03` | delete/create/name-check/rename: acknowledged (character management is in the launcher) |

Replies have a valid size and MD5 (the digest covers the whole packet with bytes 12–27 zeroed).
For `0x07`, Fanxi picks the character whose `char_id` appears in the packet body, else the
account's first character, and stores a `ZoneSession` in `world.by_char`. When the client sends
the zone login, the gateway finds that session.

## 4. Zone (UDP)

Zone packets are:

```
28-byte header | cipher/compressed body | padding | MD5(16) | nbits(4)
```

- Header: server packet id, client id, timestamps.
- Body: messages, each with a 4-byte header: a 16-bit word carrying a 9-bit type and a 7-bit
  size in **32-bit units**, followed by a 16-bit sync/sequence. The payload starts at byte 4.
- Compression: the fixed Huffman table in the player's `res/compress.dat` (2048 bytes).
- Encryption: the client's Blowfish variant over the body, keyed by:
  `md5(session_hash) + view_key_adjustment` (20 bytes). The client's `0xA2` key replaces the
  session key when present.

On the clear `0x00A` login Fanxi:

1. finds the character by content id or database id in the packet;
2. continues the prepared `ZoneSession` from the lobby or a recent zone change, and checks for an
   active `game_sessions` row; it never continues a session just because the UDP address matches
   (the OS recycles local ports);
3. despawns and releases any other session that still claims the character or the address;
4. loads the position from `characters`;
5. replies with equipment clear (`0x04F`), appearance (`0x051`), item capacities (`0x01C`) and the
   260-byte zone login (`0x00A`).

Zone sessions have no TCP connection to watch, so a client that sends nothing for three minutes
is treated as disconnected: its character is despawned from the other clients, its player targid
is freed and its last position is saved. A zone change gets a thirty-second window from the
change itself (not the last packet); see [world](world.md#other-players). `0x00C` is accepted
when it arrives with sync 0.

The client keeps sending `0x015` while it stands still, and about ninety seconds without a
server packet is enough for it to declare the link dead (`FFXI-4001`). A session in the world
that has had nothing to send for five seconds therefore gets a General-only `0x00D` (HP, MP and
TP; the model and name blocks are not re-sent, so the client does not reset the entity). It
resets that timer and acknowledges the client's packet stream. The three-minute silence rule
above still drops a client that has actually gone away; a live idle character never looks
silent to the server.

Other players are normally placed from the `0x00D` broadcast their movement causes, so a
stationary player sends nothing. A session that is in the world, has its zone, and is not
moving refreshes that `0x00D` position once a second to the clients that have it spawned. This
is what lets a box that finished loading after the leader's last step converge on the leader's
real position instead of keeping the warp-anchor copy until the leader moves again.

On `0x00B` the client moves its zone key on by 2 (the last word), and the zone-in must be
enciphered with that advanced key: the pre-change key decrypts to a packet the client ignores,
which it answers by retrying `0x00A` every two seconds — the "Downloading" screen that never
finishes. The server keeps the whole sequence of keys a hand-off has used, not just the newest
two, and sends the zone-in once under each of them; the client's MD5 check drops the copies it
cannot open and it acknowledges the one it did. A packet still in flight under the old key does
**not** mean the client kept it; only `0x00C` proves which key the client uses, and the server
switches to the matching key when that packet opens.

A repeated `0x00A` before `0x00C` rebuilds the zone-in instead of replaying the packet the client
is already ignoring, again sending a copy under every key in the sequence. If four rebuilds fail,
the session is dropped but its key sequence is parked for ten minutes: the next `0x00A` from the
same game session resumes it, because the client still holds the key it advanced to. Parking
merges with the sequence already on file instead of replacing it, so a shorter replacement login
cannot forget the advanced key. A client that signed in again (a new game session) starts from the
account's sign-in key as the primary cipher — but the parked sequence still travels as extra
sealed copies, so a client the player did not restart opens the zone-in under the key it kept — a
reset for a relogging client is what used to loop forever.

Box clients on one host open the socket for the new zone from the same local port range, so one
box's `0x00A` can arrive on an address another box has just released. A session at that address
that is still mid-hand-off is not evicted (its `0x00B` already went out and its own `0x00A` is
coming from a different port); treating the address as recycled dropped that box from the party
and from the advanced cipher it was about to prove.

A zone change requested while another is still in flight (a second `//warp call`, the launcher's
auto-warp, a zone line) is deferred instead of sending a second `0x00B`; it runs after the client
acknowledges the zone, and a duplicate call to the same spot is dropped.

When the client sends `0x00C` (game OK), Fanxi sends the rest of the zone state: zone bitmap
(`0x008`), jobs (`0x01B`), status/HP (`0x037`), stats/EXP (`0x061`), exact HP/MP (`0x0DF`), the
self `0x00D`, empty key-item/mission/magic/command blocks, the mount table (`0x0AE`, see
[mounts.md](mounts.md)), character sync (`0x067`),
inventory (`0x01C`, `0x020`, `0x01D`), blacklist and the MOTD.

A fresh login also reads the character's `char_live_state` row before that burst and puts the
saved status effects back on the session, so the `0x037` list draws the icons and the `0x063`
that always follows it carries their remaining time. `0x119` (the ability recast table, sent
with the command data) carries the cooldowns the character still had.  Slot 0 is retail's
two-hour ("Special") recast: the current main job's one-hour ability has recast id 0, so
its timer is sent there (with the Master gift's 15 minutes already deducted).  The
per-ability cooldowns are kept above the byte-sized ordinary recast ids, so changing jobs
does not block the new job's one-hour.  Expired entries are dropped on the way in; a
deliberate `/logout` saved the cooldowns without the buffs. See
[world](world.md#recovering-a-dropped-client).

**NPCs and monsters are not sent at `0x00A` or `0x00C`.** The client's first `0x015` (or
`0x01A SendResRdy`) is the trigger: Fanxi sends one `0x00E` per placed NPC/monster, then updates
them as they move or take damage.

Implemented client messages:

| Type | Meaning | Fanxi behavior |
|---|---|---|
| `0x00C` | zone fully loaded | sends the bulk zone/UI state |
| `0x015` | position update | stores position (throttled) and spawns nearby entities on first use |
| `0x01A` | target action | Talk, Attack, AttackOff, ChangeTarget, SendResRdy, Mount (0x1A, the id in ActionBuf[0]) and Dismount (0x12) |
| `0x00DD` | inspection (`/check`, `/checkname`, `/checkparam`) | Kind 0 answers a monster with `0x029` message 170–178 (its level and retail's difficulty/Defense/Evasion line); a checked player gets `0x009` 89 ("<name> examines you."). Kinds 1 and 2 are logged, not answered |
| `0x037` | item use | consumes the container/slot the packet names; food applies its `food_effects` row and its `0x028` ItemFinish action plays the eat/drink animation.  A charged dispense pouch instead grants its mapped ammo, keeps the piece, and starts its reuse timer (the `0x020` charged extdata) |
| `0x028` | item drop | removes `ItemNum` of the stack at the named `Category`/`ItemIndex`; replies `0x020` with the remaining quantity (item id `0` when the slot emptied) and one all-bag `0x01D`. Gil and a copy being worn are refused |
| `0x083` | shop buy | charges gil, adds item, replies `0x03F` and inventory |
| `0x016`, `0x017` | entity request | self `0x00D`/status, or re-sends an NPC/mob spawn.  A self request after the zone-in gets the General-only `0x00D` plus `0x037`; the full self spawn is reserved for the loading zone-in, because its name/model blocks reset the running client's player entity |
| `0x061` | status request | stats and exact HP/MP, including the eight elemental defences at body `0x30` that the equipment menu draws under Attack/Defense |
| `0x05E` | zone line | changes zone if `zone_lines` has the rect; the main account's online family boxes standing in the old zone get the same `0x00B` through the warp queue; `zmrq` is the Mog House exit menu, modes 1–4 naming a city area |
| `0x0B5` | chat | `//zone`, `//pos`, `//where`, `//entities`, `//heal`, `//hp`, `//warp`, `//invite`, `//makeparty`, `//time`, `//help` |
| `0x04B` | server message request | sends the MOTD in chunks |
| `0x05A` | conquest | zeroed standings |
| `0x03C` | blacklist | empty |
| `0x0E8` | `/heal` | toggles rest; HP/MP recover on the three-second tick |
| `0x0E7` | logout/shutdown | saves position, sends `0x00B` |
| `0x06E` | party/alliance invite | finds the target by char id or targid and sends `0x0DC`; Kind 0 is a party, 5 an alliance |
| `0x074` | invite answer | accept builds the party/alliance and reloads every member; decline tells the inviter |
| `0x06F` | leave | removes the member, or the party from its alliance |
| `0x070` | disband | leader-only; folds the party or the alliance |
| `0x071` | kick | leader-only; removes a member or an allied party |
| `0x076` | roster reload | re-sends `0x0C8` and its `0x0DD` rows |
| `0x077` | leader change | passes party leadership (Kind 0) or alliance leadership (Kind 5) |
| `0x078` | group id | replies with `0x0E1` while grouped or while a solo player has Trusts; silent for a plain solo, because id 0 crashes the client |

`0x00F` (CLSTAT) and `0x00D` (NETEND) are ignored; `0x00D` is also the server's player-entity
packet, so direction matters.

The group menu is server-owned: `0x0C8` (GROUP_TBL) carries up to twenty rows of
`char id, targid, flags, zone` and `0x0DD` (GROUP_LIST) one member's HP/MP/TP, job levels, name,
member number and flags. A member in another zone gets its zone number instead of vitals. Trusts
are rows too: the table has no leader/party flags for them, and one `0x0DD` follows the owner's
row with the Trust's id, targid, HP/MP/TP, job and level. HP/MP/TP changes are sent as the same
`0x0DF` the local player receives, so the client's native party bars and the Party Info hub both
follow the server's state.  A plain solo player still gets an empty `GROUP_TBL` plus its own
`GROUP_LIST` row at zone-in (and after a disband): the HUD reads its own job pair from that row,
so omitting it left `MainJob` 0 and emptied the spell and Trust windows.

### 4.1 Entities

NPC/mob identity follows the client's convention:

```
long id  = 0x01000000 | (zone << 12) | targid
targid   = static NPCs/mobs 0x000-0x3FF, players 0x400-0x6FF, pets 0x700-0x8FF
```

Fanxi places three NPCs at `0x100`–`0x102` and six monsters at `0x200`–`0x205` in their zones.
`0x00E` is 88 bytes total; its payload is x/y/z floats, rotation, speed, HP percentage, animation,
status, triggerable flag, model/size and a 16-byte name. `0x00D` is the equivalent for the player.

Trust alter egos are `0x00E` spawns in the pet range with Flags3's TrustFlag (`0x01`), PetNewFlag
(`0x04`) and PetFlag (`0x40`) set and player allegiance. The owner also receives `0x067` with the
Trust's id, targid and the owner's own targid; that is what makes the client offer the Trust
sub-menu. (`0x067` is shared with the player level block, which starts `0x02/0x09`; the entity
name variant starts `0x03/0x05`.) The spawnable name lives at packet offset `0x34` (body `0x30`),
where a static NPC has its one-byte name marker; the static NPC's string then starts at `0x35`.
The Trust look block is the factual model from the `trusts` table.

### 4.2 Combat

A player attacks with `C2S 0x01A`, action `0x02` (inside 30 yalms); `0x04` asks to disengage.
The client also sends `0x04` on its own when the target leaves auto-attack reach, so the server
ignores that first distance-driven packet and keeps the engagement out to 30 yalms. An attack
round sends one S2C `0x028` bit-packed battle action with:

- actor id and one target id;
- category `1` (basic attack) and action id `atk0` (`0x306B7461`);
- a result per swing: the main hand's base hit and its Double/Triple/Quadruple Attack
  extras (animation 0), then the off hand's (animation 1), each with its hit or miss
  resolution, critical/defeated flags, value and message id.

A dual-wielded or multi-attacking round is therefore still one action packet: the client
plays the results in order.  Two `0x028`s for the same actor and target in one update made
it drop the first.  A round is capped at eight results.

For a finished spell the sub-kind is the spell animation id and the value is the damage, the HP
healed, or the status effect id the spell lands; the message chooses the line
(`MAGIC_DMG` 2, `MAGIC_RECOVERS_HP` 7, `MAGIC_GAIN_EFFECT` 230, `MAGIC_ENFEEB` 237,
`MAGIC_TELEPORT` 93).  A Magic Start uses the school's four-character code as its action
id (`canj` for ninjutsu, `cawh`, `cabk`, ...) and the spell id as its value; its result
animation is the same spell animation id, so the cast begins with the spell's own motion
rather than the client's default (Cure's) one.  The result message is the client's start
line: 327 for a player (`<caster> starts casting <spell> on <target>.`) and 3 for a
monster or Trust (`<caster> starts casting <spell>.`).  Sending the message and a line of
our own printed it twice, so the server no longer writes that chat line itself.

An interrupted cast is the same category 8 with `sp`+school as the action id (`spwh`, `spbk`,
`spnj`, ...) and the spell id as its value: the client stops the cast bar instead of starting
one.  The action's own message stays 0; the line is a separate S2C `0x029` basic message 16,
"The <player>'s casting is interrupted."  This is the packet the phase engine reads as the
aftercast result when a cast ends without a Magic Finish.

`0x029` carries the defeat and gil lines; `0x02D` carries EXP and level-up. HP changes update
`0x00E`, `0x037`, `0x061` and `0x0DF`. See [world.md](world.md) for the full combat loop.

### 4.3 Inventory and shops

- Gil is item id `65535` in container `0`, slot `0`.
- `0x01C` advertises container capacities.
- `0x020` carries one item's quantity, id, container, slot and 24-byte attribute block.
- `0x01D` marks containers loaded. Its `Flags` field is the client's complete ready mask, not the
  set of containers named by this update: the client replaces the mask with the packet's value.
  Every Fanxi sync therefore carries all 18 container bits, even when only two bags changed.
- `0x01E` updates only a quantity (used for gil).
- `0x01F` is a lighter item list, available for future equipment changes.
- `C2S 0x037` uses an item. It names the container (`Category`, 0x10) and the slot
  (`PropertyItemIndex`, 0x0E), not the item id; 0x08 is `ItemNum` and is always 0. The reply is
  a `0x020` for that container/slot, one all-bag `0x01D`, and a `0x028` ItemFinish action
  (category 5) whose sub-kind is the item's animation; food adds its `0x037`/`0x063` status
  icon pair.
- `C2S 0x03A` names a container after the client sorts it. The server merges partial stacks of
  the same item (and same 24-byte extdata) in that container, then sends `0x020` for every
  changed slot and one all-bag `0x01D`.
- `C2S 0x028` is the item menu's Drop: `ItemNum` (0x04) is how many to throw away, `Category`
  (0x08) and `ItemIndex` (0x09) the slot. A partial count leaves the rest of the stack; the reply
  is a `0x020` with the remaining quantity (item id `0` when the slot emptied) and one all-bag
  `0x01D`. Gil (`0`/`0`) and a slot the character is wearing are refused, because deleting a bag
  row an equip entry points at would leave the character in gear the server no longer has.

`//storage` and `//locker` never expose a destination bag. Store sends an `0x020` with item id
`0` for each vacated bag slot and one all-bag `0x01D`; the item is then only in the server-side
`char_storage` or `char_locker` table. Grab sends an `0x020` for each returned item and one
all-bag `0x01D`. `//storage organize` and `//job` combine both: they queue every clear first
(vacated bag slots and tidy sources), then every write (wardrobe destinations and pulls), then a
single all-bag `0x01D`, so a slot that one move frees and another fills never draws the new item
before the old one leaves. Each affected Mog Wardrobe is reopened with a state-0 `0x01D` first
and sent its full current contents: the client only files `0x020` rows into a storage's item list
while that container's load window is open, and a bare `0x020` left the equipment window showing
the previous wardrobe's list.

The Moogle shop uses `0x03E` (open, item count), `0x03C` (price/item/index rows, final flag
`0x89`), `C2S 0x083` (buy) and `0x03F` (result), followed by an inventory refresh.

### 4.4 NPC dialogue and quests

`C2S 0x01A` action `0x00` is Talk. Fanxi requires an NPC within 6 yalms and calls an original
content function. Dialogue is sent as `0x017` chat lines. FINAL FANTASY XI event bodies and menus
are client DAT content; Fanxi does not open an event it cannot author, and does not copy retail
text. Quest state is persisted in `char_quests`, not in a client event.

Chat commands:

```
//zone <id> [x y z [rot]]   change zone, optional position
//pos <x> <y> <z> [rot]     reposition in the current zone
//where                     print zone and position
//warp mark [alias]         save this zone/position as the next numbered warp
//warp me|all <n|alias>     return, alone or with the account's online sub-characters
//warp all me               call those sub-characters to the sender's zone/position
//warp list [page]          print the saved places
//warp delete <n|alias>     delete one
//warp rename <n> <alias>   name or clear one
//invite [subs|all|<name>]  invite the online subs, or one player by name
//makeparty                 drop every online sub from its party, then invite it
//entities                  list live NPCs/monsters and targids
//heal                      restore HP/MP
//time <hour>               set Vana'diel hour (0-23, fractions allowed)
//storage organize          store every other job's gear and pull this job's set
//storage store <job|all>   store a job's gear, or everything this job cannot equip
//storage grab <job|all>    pull a job's gear, or everything, back into the bags
//storage list [job|all]    what is stored, by job
//locker store|grab <sel>   hidden 9,999-slot locker (all, ammo, back, materials, name)
//locker list               list the locker's contents
//help                      list commands
```

`//` lines are server chat commands, not client slash commands. The host turns a known
`//command` into the server's `!command` say line, so the wire keeps one `!` and the client's
own slash parser never sees the second slash. The old `/!command` and bare `!command` forms
still reach the same handler. Tab completion for the whole `//` command set is a host feature,
not a protocol change (see `docs/control-panel.md#command-completion`). The saved warps live in
`char_warps`, one row per character and slot 1-1000.

### 4.5 Emotes and style lock

An emote is `C2S 0x05D` (16 bytes): target server id, target index, emote id, mode
(0 both, 1 text, 2 motion) and parameter. Fanxi answers with `S2C 0x05A` (56 bytes: caster and
target ids/indexes, message id, parameter, mode, then the five Trust slots the client always
reads). The reply goes to the caster and every session in the zone, which is what draws the
animation and writes the text line. `/jobemote` is `MesNum 74 + (param - 0x1F)` with the job
index in the parameter; `/bell` is motion-only with `param - 6`; `/salute` carries the nation and
`/hurray` the main-hand item id.

Style lock is `C2S 0x053` (0x88 bytes): count, mode, flags, then 16 eight-byte entries
(item index, equip kind, category, item id). Modes are 0 off, 1 continue (the client asserts
that its own lock is on; sent on login and zoning, and by `/lockstyle on` when the client
already believes the lock is on), 2 query, 3 set, 4 enable. Fanxi persists the locked
models in the `characters.style_*` columns (migration 0085) and replies:

- `0x051` (grap list) and `0x067` (char sync) after off, set, enable or a continue that
  switched the lock on, so the client repaints;
- `0x009` with message 267/268 when the state changes, and 269/270 for a query;
- `0x11C` with the item ids a set could not lock.

Every later `0x051`, login `0x3C` look block and `0x00D` character update reads the locked
models while the lock is on, so an equipment change cannot repaint the character (the "blink").
Main and sub are the exception: they always follow the equipped weapon, so a two-hander
becoming a one-hander plus a shield (or any other weapon swap) draws the new graphics even
with the lock on; the armour keeps the locked look.
An H2H main hand is the one case where the sub look is not a sub item: retail writes the
same model with the `+0x1000` left-fist tag into the sub slot (wire value `model + 0x8000`),
and without it the client draws only the main-hand knuckle.  `_apply_equip_model` mirrors
an H2H main hand into the sub look and clears it when another main hand is equipped.
A job change clears the lock and forgets its models, as in retail, and sends message 268 when
the lock was on. The server-side `//job` command then locks the outfit it just dressed: it
snapshots the new models, sends message 267 with a fresh `0x051`, and replaces the character's
`0x00D` spawn for nearby clients, because an observer only re-reads another player's models when
it spawns the entity. `/lockstyle off` clears them too. The client keeps its own copy of the
flag, so mode 1 has to switch the lock on when the server has it off: the client sends that
packet instead of mode 4 once it believes the lock is on, and a server that ignored it left
`/lockstyle on` doing nothing forever. It cannot resurrect an old look, because turning the
lock off (or changing job) has already zeroed the stored models, so the continue locks the
appearance the character is wearing at that moment.

## 5. Search (TCP)

The lobby's `0x0B` reply carries two addresses: the zone server and the search server. The
client opens a separate TCP connection to the search address when the `/sea` window needs it.
Retail's search service is a TCP service; Fanxi advertises the same port and now binds it.

A search packet is:

```
u16 size | 2 bytes zero | "IXFF" | encrypted body | 16-byte MD5 | 4-byte nonce
```

The body is encrypted with the client's Blowfish variant. For a request the key is
`MD5(fixed 16-byte search key + nonce)`. A reply folds in the last four bytes of the request
body as well: `MD5(fixed key + nonce + tail4)`. The MD5 covers bytes 8 through the end of the
body, and does not cover the nonce. The fixed key is a protocol constant, the same one
LandSandBoat's search service uses; it is not a login credential.

The decrypted request has its type at `0x0B`, a one-byte packed-query length at `0x10`, and a
bit-packed query at `0x11`. Fanxi implements the two player searches:

| Type | Meaning |
|---|---|
| `0x00` | `/sea all` |
| `0x03` | `/sea <name>` |

Each query entry starts with a five-bit type, and most entries then carry a descending bit and
an "is present" bit. Fanxi reads the name, area, nation, job, level, race and rank entries,
which covers the filters the client's search window sends. Flag entries are parsed but not
applied: Fanxi does not model search comments, away/seek-party flags or linkshells yet. The
name entry is a five-bit length and seven-bit characters; matching is a case-insensitive
prefix, as in retail. A name search ignores the area entry the client adds from its own
current location, so `/sea twodough` still finds a character who has moved to another zone;
an unnamed area search keeps that filter. The other types (auction house, friend list,
linkshell and party lists, search comments) are ignored.

The reply is the packed search list the client draws: a 24-byte header, then one entry per
character. The header carries the packed-data size at `0x08`, a final-packet flag at `0x0A`,
`0x80` at `0x0B`, and the total number of matches at `0x0E`. Each entry has a one-byte size,
then name, area, nation, both jobs, both levels, race, rank, flags, the 20-bit character id, a
zero word where retail puts linkshell ranks, flags again and the language mask. At most 20
entries fit in a packet and at most 40 results are shown; more than that is reported in the
total.

Fanxi answers from its live zone sessions, so a result exists exactly while the character is
logged in and the area is the one the session is in right now. Sleeping boxes (`//sleep`) stay
logged in and remain listed. Fanxi sends no search comments, linkshell ranks or auction-house
replies yet, and the search result id is the low 20 bits of Fanxi's content id (content ids
are `0x01000000 + the database number`, so those bits are that number).

## Keys and secrets

The Blowfish S-boxes, the view key and the Huffman algorithm are protocol constants, not
secrets. The Huffman **table** is read from the player's own game install (`res/compress.dat`)
and is not shipped. Session hashes, launch tokens and passwords are generated per account and
never hardcoded.

## Debugging

- `FANXI_LOG_LEVEL=debug` enables lobby/data/search/zone debug logs.
- `FANXI_ZONE_DEBUG=1` logs every zone message type received.
- The launcher writes each client's output to `…/Fanxi/logs/game-<account>.log`.
- The server's `audit_log` records `game.login` and `game.token_login`.

## Known limits

- Search covers players only: `/sea all` and `/sea <name>` list online characters and their
  areas. Search comments, linkshell ranks, friend-list refreshes, party search and every
  auction-house request are ignored.
- No friends list, linkshell, bazaar, auction house or mail; party and alliance groups exist,
  but party chat, party search, level sync and treasure pools do not.
- Client event cutscenes and DAT menus are not implemented; NPC dialogue uses chat and the shop
  uses the dedicated shop packets.
- Combat is one melee target. Spells, weapon skills and the job-ability action (`0x01A` action
  `0x09`) are implemented. The `0x0AC` Weapon Skills block is filtered to the equipped weapon's
  skill type and the character's skill value, and `//ws` enforces the same list. The 2025-07-03
  client builds its Abilities submenu from a saved command-id list rather than the bitmap;
  host64 rebuilds that list from each `0x0AC` packet, so a restarted client shows the filtered
  Weapon Skills and its Job Abilities submenu lists the advertised abilities. `//ja` remains a
  shortcut. The fourth `0x0AC` block carries the current main/support job's trait ids, and the
  Auto Regen/Auto Refresh traits and gear Regain tick HP/MP/TP every three seconds. Still
  missing: ranged attacks, TP moves, skillchains, status effects, raise and an enmity list.
- Character creation and deletion in the client are acknowledged but not persisted; use the
  launcher.
- Unlimited characters per account by default (`FANXI_MAX_CHARACTERS=0`). Only one
  character per account can be online at a time; multiboxing uses one account per
  client. A launch token names the character the lobby should show.
- The gateway is not a full world server; it is a small original world that lets the client sign
  in, see and talk to NPCs, fight a camp, shop, take a quest and change zones against SQLite.
