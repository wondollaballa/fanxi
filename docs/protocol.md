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
- Body: messages, each 4-byte header (9-bit type, 4-bit size in 2-byte units, sync) plus payload.
- Compression: the fixed Huffman table in the player's `res/compress.dat` (2048 bytes).
- Encryption: the client's Blowfish variant over the body, keyed by:
  `md5(session_hash) + view_key_adjustment` (20 bytes). The client's `0xA2` key replaces the
  session key when present.

On the clear `0x00A` login Fanxi:

1. finds the character by content id in the packet;
2. finds the prepared `ZoneSession` from the lobby, or an active `game_sessions` row;
3. loads the position from `characters`;
4. sends the zone-in sequence: zone id, position, clock, music, character looks/jobs, HP/MP,
   item containers (empty), quest/mission logs (empty), blacklist (empty), and the server message.

Implemented client messages:

| Type | Meaning | Fanxi behavior |
|---|---|---|
| `0x00C` | zone fully loaded | sends the rest of the zone-in state |
| `0x015` | position update | stores position (throttled) |
| `0x05E` | zone line | changes zone if `zone_lines` has the rect |
| `0x0B5` | chat | `!zone`, `!pos`, `!where`, `!time`, `!help` |
| `0x04B` | server message request | sends the MOTD in chunks |
| `0x016`, `0x061` | character asks about itself | status, stats, party line |
| `0x05A` | conquest | zeroed standings |
| `0x03C` | blacklist | empty |
| `0x0E7` | logout/shutdown | saves position, sends 0x00B |

Everything else is ignored (logged once at debug level). There are no entities, NPCs, monsters,
items, combat, quests or chat channels other than the command replies.

Chat commands:

```
!zone <id> [x y z [rot]]   change zone, optional position
!pos <x> <y> <z> [rot]     reposition in the current zone
!where                     print zone and position
!time <hour>               set Vana'diel hour (0-23, fractions allowed)
!help                      list commands
```

## Keys and secrets

The Blowfish S-boxes, the view key and the Huffman algorithm are protocol constants, not
secrets. The Huffman **table** is read from the player's own game install (`res/compress.dat`)
and is not shipped. Session hashes, launch tokens and passwords are generated per account and
never hardcoded.

## Debugging

- `FANXI_LOG_LEVEL=debug` enables lobby/data/zone debug logs.
- `FANXI_ZONE_DEBUG=1` logs every zone message type received.
- The launcher writes the client's output to `…/Fanxi/logs/game.log`.
- The server's `audit_log` records `game.login` and `game.token_login`.

## Known limits

- No search server (`54002/udp` is advertised but not bound).
- No friends list, linkshell, bazaar, auction house, mail, party or chat channels.
- Character creation and deletion in the client are acknowledged but not persisted; use the
  launcher.
- One character per account by default (`FANXI_MAX_CHARACTERS`).
- The gateway is not a full world server; it is the smallest world that lets the client sign in,
  stand in a zone, move and change zones against the Fanxi database.
