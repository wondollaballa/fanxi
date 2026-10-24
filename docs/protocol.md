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
| 54002 | UDP | Search (advertised; not implemented) |

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

Zone sessions have no TCP connection to watch, so a client that sends nothing for sixty seconds
is treated as disconnected: its character is despawned from the other clients, its player targid
is freed and its last position is saved. A zone change gets a thirty-second window and keeps its
advanced cipher; see [world](world.md#other-players).

When the client sends `0x00C` (game OK), Fanxi sends the rest of the zone state: zone bitmap
(`0x008`), jobs (`0x01B`), status/HP (`0x037`), stats/EXP (`0x061`), exact HP/MP (`0x0DF`), the
self `0x00D`, empty key-item/mission/magic/mount/command blocks, character sync (`0x067`),
inventory (`0x01C`, `0x020`, `0x01D`), blacklist and the MOTD.

**NPCs and monsters are not sent at `0x00A` or `0x00C`.** The client's first `0x015` (or
`0x01A SendResRdy`) is the trigger: Fanxi sends one `0x00E` per placed NPC/monster, then updates
them as they move or take damage.

Implemented client messages:

| Type | Meaning | Fanxi behavior |
|---|---|---|
| `0x00C` | zone fully loaded | sends the bulk zone/UI state |
| `0x015` | position update | stores position (throttled) and spawns nearby entities on first use |
| `0x01A` | target action | Talk, Attack, AttackOff, ChangeTarget, SendResRdy |
| `0x037` | item use | consumes the container/slot the packet names; food applies its `food_effects` row and its `0x028` ItemFinish action plays the eat/drink animation |
| `0x083` | shop buy | charges gil, adds item, replies `0x03F` and inventory |
| `0x016`, `0x017` | entity request | self `0x00D`/status, or re-sends an NPC/mob spawn |
| `0x061` | status request | stats and exact HP/MP |
| `0x05E` | zone line | changes zone if `zone_lines` has the rect; `zmrq` is the Mog House exit menu, modes 1–4 naming a city area |
| `0x0B5` | chat | `!zone`, `!pos`, `!where`, `!entities`, `!heal`, `!hp`, `!warp`, `!time`, `!help` |
| `0x04B` | server message request | sends the MOTD in chunks |
| `0x05A` | conquest | zeroed standings |
| `0x03C` | blacklist | empty |
| `0x0E8` | `/heal` | toggles rest; HP/MP recover on the three-second tick |
| `0x0E7` | logout/shutdown | saves position, sends `0x00B` |

`0x00F` (CLSTAT) and `0x00D` (NETEND) are ignored; `0x00D` is also the server's player-entity
packet, so direction matters.

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
name variant starts `0x03/0x05`.) The spawnable name lives at packet offset `0x38` rather than the
static-NPC `0x35`, and the Trust look block is the factual model from the `trusts` table.

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

For a finished spell the sub-kind is the spell id and the value is the damage, the HP
healed, or the status effect id the spell lands; the message chooses the line
(`MAGIC_DMG` 2, `MAGIC_RECOVERS_HP` 7, `MAGIC_GAIN_EFFECT` 230, `MAGIC_ENFEEB` 237,
`MAGIC_TELEPORT` 93).  A Magic Start uses the school's four-character code as its action
id (`canj` for ninjutsu, `cawh`, `cabk`, ...) and the spell id as its value.

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

`!storage store|grab` and `!locker store|grab` never expose a destination bag. Store sends an
`0x020` with item id `0` for each vacated bag slot and one all-bag `0x01D`; the item is then only
in the server-side `char_storage` or `char_locker` table. Grab sends an `0x020` for each returned
item and one all-bag `0x01D`.

The Moogle shop uses `0x03E` (open, item count), `0x03C` (price/item/index rows, final flag
`0x89`), `C2S 0x083` (buy) and `0x03F` (result), followed by an inventory refresh.

### 4.4 NPC dialogue and quests

`C2S 0x01A` action `0x00` is Talk. Fanxi requires an NPC within 6 yalms and calls an original
content function. Dialogue is sent as `0x017` chat lines. FINAL FANTASY XI event bodies and menus
are client DAT content; Fanxi does not open an event it cannot author, and does not copy retail
text. Quest state is persisted in `char_quests`, not in a client event.

Chat commands:

```
!zone <id> [x y z [rot]]   change zone, optional position
!pos <x> <y> <z> [rot]     reposition in the current zone
!where                     print zone and position
!warp mark [alias]         save this zone/position as the next numbered warp
!warp me|all <n|alias>     return, alone or with the account's online sub-characters
!warp list [page]          print the saved places
!warp delete <n|alias>     delete one
!warp rename <n> <alias>   name or clear one
!entities                  list live NPCs/monsters and targids
!heal                      restore HP/MP
!time <hour>               set Vana'diel hour (0-23, fractions allowed)
!storage store <job>       move that job's storable gear onto its slips
!storage grab <job|all>    take it back off the slips
!locker store|grab <sel>   hidden 9999-item locker (all, ammo, back, materials, name)
!locker list               list the locker's contents
!help                      list commands
```

`/!` lines are server chat commands, not client slash commands; the host sends them to the
server as say lines. Tab completion for the whole `/!` command set is a host feature, not a
protocol change (see `docs/control-panel.md#command-completion`). The saved warps live in
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
(item index, equip kind, category, item id). Modes are 0 off, 1 keepalive (sent while zoning
with the lock on), 2 query, 3 set, 4 enable. Fanxi persists the locked models in the
`characters.style_*` columns (migration 0085) and replies:

- `0x051` (grap list) and `0x067` (char sync) after off, set or enable, so the client repaints;
- `0x009` with message 267/268 when the state changes, and 269/270 for a query;
- `0x11C` with the item ids a set could not lock.

Every later `0x051`, login `0x3C` look block and `0x00D` character update reads the locked
models while the lock is on, so an equipment change cannot repaint the character (the "blink").
A job change clears the lock, as in retail.

## Keys and secrets

The Blowfish S-boxes, the view key and the Huffman algorithm are protocol constants, not
secrets. The Huffman **table** is read from the player's own game install (`res/compress.dat`)
and is not shipped. Session hashes, launch tokens and passwords are generated per account and
never hardcoded.

## Debugging

- `FANXI_LOG_LEVEL=debug` enables lobby/data/zone debug logs.
- `FANXI_ZONE_DEBUG=1` logs every zone message type received.
- The launcher writes each client's output to `…/Fanxi/logs/game-<account>.log`.
- The server's `audit_log` records `game.login` and `game.token_login`.

## Known limits

- No search server (`54002/udp` is advertised but not bound).
- No friends list, linkshell, bazaar, auction house, mail, party or chat channels.
- Client event cutscenes and DAT menus are not implemented; NPC dialogue uses chat and the shop
  uses the dedicated shop packets.
- Combat is one melee target. Spells, weapon skills and the job-ability action (`0x01A` action
  `0x09`) are implemented. The `0x0AC` Weapon Skills block is filtered to the equipped weapon's
  skill type and the character's skill value, and `!ws` enforces the same list. The 2025-07-03
  client builds its Abilities submenu from a saved command-id list rather than the bitmap;
  host64 rebuilds that list from each `0x0AC` packet, so a restarted client shows the filtered
  Weapon Skills and its Job Abilities submenu lists the advertised abilities. `!ja` remains a
  shortcut. The fourth `0x0AC` block carries the current main/support job's trait ids, and the
  Auto Regen/Auto Refresh traits tick their HP/MP every three seconds. Still missing: ranged
  attacks, TP moves, skillchains, status effects, raise and an enmity list.
- Character creation and deletion in the client are acknowledged but not persisted; use the
  launcher.
- Unlimited characters per account by default (`FANXI_MAX_CHARACTERS=0`). Only one
  character per account can be online at a time; multiboxing uses one account per
  client. A launch token names the character the lobby should show.
- The gateway is not a full world server; it is a small original world that lets the client sign
  in, see and talk to NPCs, fight a camp, shop, take a quest and change zones against SQLite.
