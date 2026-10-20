# Architecture

Fanxi is four pieces that share one repository and one vocabulary:

```
┌──────────────────────────────┐        HTTP/JSON         ┌──────────────────────────────┐
│  Fanxi Launcher (Tkinter)    │ ───────────────────────► │  Fanxi HTTP API              │
│  account, character, Play    │ ◄─────────────────────── │  auth, characters, news,     │
└──────────────┬───────────────┘    launch token          │  releases, launch tokens     │
               │                                          └──────────────┬───────────────┘
               │ spawns host64 + login token                             │
               ▼                                                        ▼
┌──────────────────────────────┐   auth/TLS, data, lobby,  ┌──────────────────────────────┐
│  host64 (recompiled client)  │ ───────── zone ─────────► │  Fanxi game gateway          │
│  the player's own game files │ ◄─────────────────────── │  auth, data, lobby, zone     │
└──────────────────────────────┘                           └──────────────┬───────────────┘
                                                                          │
                                                                          ▼
                                                              ┌──────────────────────────┐
                                                              │ data/fanxi.db (SQLite)   │
                                                              │ accounts, characters,    │
                                                              │ sessions, inventory,     │
                                                              │ NPCs, mobs, quests       │
                                                              └──────────────────────────┘
```

## Components

### Launcher (`launcher/`)

A Python/Tkinter desktop app. It is the only piece a player normally touches:

- talks to the HTTP API with a Bearer token;
- stores its settings and token under the platform data folder;
- finds the player's FINAL FANTASY XI folder, builds `host64` from it if needed, and starts it;
- asks the API for a single-use launch token and passes it to `host64`.

It never writes into the game folder. The build scripts (`tools/prepare.py`,
`tools/build_posix.py`) read `FFXiMain.dll`, `FFXi.dll` and `ROM` and write only to `build/`,
`generated/` and `.venv/`.

### HTTP API (`server/fanxi_server/http_api.py`)

A JSON API for the launcher: registration, login, logout, account, characters, news, releases,
launch tokens, and admin endpoints. It runs on `http.server.ThreadingHTTPServer` with a small
router and no framework. Authentication is a 48-byte random Bearer token; only its SHA-256 is
stored in the database.

### Game gateway (`server/fanxi_server/game/`)

The FINAL FANTASY XI-facing side. Four listeners:

| Listener | Default | Protocol |
|---|---|---|
| auth | `54231/tcp` | TLS, one JSON request, one JSON reply |
| data | `54230/tcp` | 0xFE + session hash, then the zone key (0xA2) |
| lobby | `54001/tcp` | 28-byte size header, `IXFF`, command |
| zone | `54230/udp` | the zone packet format, Blowfish + Huffman |
| search | `54002/udp` | advertised in the lobby; reserved |

The gateway is a small world: one character per account by default, zone-in, movement,
zone changes, chat commands, NPCs, monsters, basic melee combat, inventory, a shop and a hunt
quest. It is a real subset of the client protocol, not a full retail simulation. The design and
limits are in [world.md](world.md); the LandSandBoat research notes are in
[landsandboat-study.md](landsandboat-study.md).

### Database (`database/`, `data/fanxi.db`)

SQLite, in WAL mode, with foreign keys on. Schema changes are numbered files in
`database/migrations/`; starter data is `database/seed.sql`. The server applies both on startup.
The database is the source of truth for accounts, characters, positions, inventory and quest
state; there is no hidden in-memory state that survives a restart. Live monster HP, aggro and
timers are per-process and reset on restart (their spawn definitions are durable).

### Client (`recomp/`, `runtime/`, `host/`)

A static recompiler for the game's 32-bit x86 DLLs and a platform layer that implements the
Win32, Direct3D 8, audio, input and socket surface the game expects. The recompiler runs on the
player's machine against the player's own game files. This code is ported from the earlier
MIT-licensed codebase and carries Fanxi's identity.

## Request flows

### Register and sign in

1. Launcher `POST /api/v1/auth/register` or `/auth/login`.
2. Server validates the password (minimum 8 characters), hashes it with PBKDF2-HMAC-SHA256
   (260,000 iterations, per-user salt), and creates a row in `accounts`.
3. Server creates `api_sessions` with `sha256(token)` and an expiry (30 days by default) and
   returns the raw token once.
4. Launcher stores the token in `launcher.json` (mode 0600). It never stores the password.

### Character

1. Launcher `POST /api/v1/characters` with a name, race, nation, job, face and size.
2. Server validates the name (3–15 letters), the ranges, and the per-account limit, and assigns a
   content id (`0x01000000 + row id`).
3. The character starts in Port Jeuno at the seeded position; positions are updated by the zone
   gateway as the player moves (at most every 5 seconds).

### Launch hand-off

1. Launcher `POST /api/v1/launch` (optionally with `character_id`).
2. Server invalidates the account's old unused tokens, inserts a `login_tokens` row with
   `sha256(token)` and a 120-second expiry, and returns the raw token plus the world's host and
   ports.
3. Launcher starts:
   ```
   host64 --game <folder> --server <host> --user <name> --login-token <token>
          --authport 54231 --dataport 54230 --viewport 54001
   ```
4. `host64` opens TLS to the auth port and sends its JSON request with `login_token`.
5. Server consumes the token in a transaction (single use), checks the account is active, makes a
   random 16-byte game session hash, stores it in `game_sessions`, and answers `result: 1`,
   `account_id`, `session_hash`.
6. `host64` opens the data connection (0xFE + hash), then the lobby. The lobby returns the
   character's 140-byte record and, on zone selection, the zone address and port.
7. The client logs in to the zone over UDP. The zone key starts from `md5(session_hash)` plus the
   view-key adjustment; the client's 0xA2 key (sent on the data connection) overrides it when
   present. The gateway creates a `ZoneSession`, sends the zone-in packets and persists movement.
8. On the client's first `0x015` position, the gateway sends `0x00E` spawns for the NPCs and
   monsters in the zone. From there it runs the 250 ms world tick: roaming, aggro, melee swings,
   rewards, death and respawn.

## Trust boundaries

| Boundary | Protection |
|---|---|
| Player → HTTP API | Bearer token (SHA-256 at rest), PBKDF2 passwords, per-IP login rate limit, lockout after 5 failures |
| Player → game auth | TLS (self-signed, as private servers use); launch token or password |
| Launch token | Single use, 120 s, invalidated by a new launch |
| Game session | 16 random bytes, 12 h, looked up for data/lobby/zone |
| Admin | `admin` role or `FANXI_ADMIN_KEY` |
| Database | File permissions; no network listener |
| Player's game files | Read-only from the build; never uploaded |

The launcher API is the trust boundary that matters. The game protocol is the game protocol: the
client tells the zone where it is, so positions are client-authoritative and there is no
anti-cheat. Run Fanxi for people you trust, or put the gateway behind a VPN/firewall.

## Scaling and deployment

SQLite and one Python process comfortably handle a friends-and-family world. For more:

- run the HTTP API behind a TLS reverse proxy (Caddy, nginx) and keep the game ports on a
  private network or VPN;
- move to PostgreSQL by replacing `fanxi_server/db.py`; the SQL is ordinary SQLite-flavoured SQL
  and the service layer is the only thing that talks to it;
- run one game gateway per world and point `worlds` rows at the advertised host/ports;
- run periodic `scripts/db-backup.sh` and keep the output off the machine.

The gateway's world state is per process (sessions, keys, pending zone hand-offs), so a restart
drops in-flight sessions; players sign in again. Everything durable is in SQLite.
