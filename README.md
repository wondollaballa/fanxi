<p align="center"><img src="assets/icon.png" width="112" alt="Fanxi"></p>

<h1 align="center">Fanxi</h1>

<p align="center"><strong>FINAL FANTASY XI, on your own terms.</strong><br>
A native client, a desktop launcher, a self-hosted world server and its database — one project,
no third-party launcher, no borrowed keys.</p>

---

Fanxi is a from-the-ground-up home for **FINAL FANTASY XI**. It recompiles the game's own
`FFXiMain.dll` for your machine, wraps it in a native platform layer, and gives it a launcher and
a server that belong to the same project:

| Piece | What it is | Where |
|---|---|---|
| **Client** | The game, statically recompiled from *your* install and run natively (no Wine, no Rosetta) | `recomp/`, `runtime/`, `host/` |
| **Launcher** | A dependency-free desktop app: account, character, Play, settings, builds | `launcher/` |
| **Server** | Fanxi's HTTP API plus the FINAL FANTASY XI auth, lobby and zone gateway | `server/` |
| **Database** | SQLite: accounts, sessions, characters, zones, news, releases | `database/` |

> **Project status.** The client is the mature part: the recompiler, renderer, audio, input and
> addon host are ported from a working native build. The Fanxi launcher, server and database are
> new and functional: sign-in, character creation, launch hand-off, lobby and zone-in work end to
> end. The world is now a small original vertical slice: NPCs, a shop, a hunt quest, roaming
> monsters, basic melee combat, EXP/levels, inventory and respawns. It is not a full retail world
> yet; the boundary is documented in [docs/world.md](docs/world.md).

## Quick start

You need:

- macOS on Apple silicon (M1 or later) for the client. The launcher and server run on macOS and
  Linux; the server is Python 3.9+ only.
- Python 3.9+ with `tkinter` (the Command Line Tools on macOS include both).
- Your own copy of FINAL FANTASY XI: a `FINAL FANTASY XI` folder containing `FFXiMain.dll`,
  `FFXi.dll` and `ROM`.

```bash
# 1. Install (launcher + local database + starter content)
./install.sh                 # or double-click setup.command on macOS

# 2. Make an administrator (once)
./scripts/init.sh            # prompts for a username and password

# 3. Start the server
./scripts/server.sh
#    HTTP API   http://127.0.0.1:8080/api/v1
#    game       auth 54231/tcp, data 54230/tcp, lobby 54001/tcp, zone 54230/udp

# 4. In another terminal, start the launcher
./launcher/fanxi-launcher
```

In the launcher:

1. Create a player account (or sign in).
2. Create a character.
3. Open **Settings**, point *Game folder* at your FINAL FANTASY XI folder, and press **Build
   game**. The first build translates the game and compiles `host64`; it takes a few minutes.
4. Press **Play**. The launcher asks the server for a single-use launch token, starts `host64`,
   and the game signs in through Fanxi's auth gateway.

You start in Port Jeuno. Target the Fanxi Guide and use the action button to start **Pest
Control**; the Wandering Moogle opens a shop. Say `!zone 100` to visit the West Ronfaure camp,
fight three Orcish Grunts, then return to the Guide. `!entities`, `!heal`, `!where` and `!help`
are available in chat.

The launcher's default server is `http://127.0.0.1:8080`. Everything can live on one machine, or
the server can run elsewhere and the launcher can point at it in **Settings**.

## What is new here

### Our launcher

`launcher/` is Fanxi's own desktop app. It is plain Python + Tkinter, so it has no Electron, no
downloaded runtime and no third-party UI framework to audit. It:

- signs in to Fanxi over the HTTP API and keeps the session token in a `0600` file;
- creates and shows your character;
- stores the game folder and finds `host64`;
- builds the client from your own game files (it creates `.venv`, installs `capstone` and
  `pefile`, and streams the build log);
- asks the server for a one-time launch token and starts `host64` with the right ports;
- shows server status and news, and can package itself as a macOS `.app` or a Linux desktop entry:

```bash
python3 launcher/build_app.py             # build/Fanxi Launcher.app (macOS)
python3 launcher/build_app.py --desktop   # build/Fanxi Launcher.desktop (Linux)
```

No passwords are stored by the launcher. The token is the only credential on disk.

### Our server

`server/` is a Python standard-library service with two faces:

- **HTTP API** for the launcher: registration, sign-in, account, characters, news, releases and
  launch tokens. It is a normal JSON API with Bearer tokens.
- **Game gateway** for the recompiled client: the auth JSON exchange over TLS on 54231, the login
  data connection on 54230, the lobby on 54001, and the zone protocol on 54230/udp. It speaks the
  protocol the client already knows, but every account, character and position comes from the
  Fanxi database.

A launch is deliberately short-lived: the launcher gets a single-use token that expires in two
minutes; the game gateway consumes it, creates a 16-byte session, and that session keys the zone
cipher. The launcher never sees the game password and host64 never sees the launcher token after
it is used.

The zone gateway implements the packets needed to sign in, stand in a zone, see the character,
move, change zones and talk/attack. Its small world adds:

- three original NPCs in Port Jeuno (`!zone 246`), including the Fanxi Guide and a Moogle shop;
- six roaming/aggro monsters in West Ronfaure (`!zone 100`);
- click-to-talk dialogue and the persistent **Pest Control** hunt quest;
- basic melee combat with `0x028` action packets, HP updates, EXP, gil and level-ups;
- an 80-slot inventory with gil, Potions and starter swords;
- monster death, rewards and respawn.

Servers commands: `!zone`, `!pos`, `!where`, `!entities`, `!heal`, `!time`, `!help`. Positions are
persisted to the database (throttled to a few writes a second at most). See
[docs/world.md](docs/world.md) for content, packet flow and limits.

### Our database

`data/fanxi.db` is SQLite, created from `database/migrations/` and seeded from
`database/seed.sql`. It is one file to back up, inspect or move. Tables:

`accounts`, `api_sessions`, `game_sessions`, `login_tokens`, `characters`, `worlds`, `zones`,
`zone_lines`, `news`, `releases`, `settings`, `audit_log`, `schema_migrations`, plus the world
tables `world_npcs`, `npc_lines`, `monster_templates`, `monster_spawns`, `items`, `char_inventory`, `quests`
and `char_quests`.

There is no default password and no shipped secret. Create the first administrator yourself:

```bash
cd server
python3 -m fanxi_server create-admin
```

### No borrowed identity

This project was ported from an MIT-licensed codebase and then rebuilt around its own identity.
The old product name, repository URLs, bundle identifiers, third-party presence integration and
its application ID, screenshots, installer and launcher references are gone. Everything user-facing,
every path, every environment prefix and every bundle ID now says **Fanxi**:

| Thing | Fanxi value |
|---|---|
| Product / window name | `Fanxi` |
| Launcher bundle ID | `com.fanxi.launcher` |
| Game bundle ID | `com.fanxi.game` |
| Linux app id | `fanxi` |
| Data folder | `~/Library/Application Support/Fanxi` (macOS), `~/.local/share/fanxi` (Linux) |
| Settings prefix | `FANXI_*` |
| Web / API | `Fanxi/<version>` |
| Database | `data/fanxi.db` |

The upstream MIT copyright notice is retained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md),
as the license requires. No upstream name, URL or key is used at runtime.

## Layout

```
fanxi/
├── launcher/            Fanxi Launcher (Python/Tkinter)
│   ├── fanxi_launcher/  config, API client, game build/launch, UI
│   └── build_app.py     .app / .desktop packager
├── server/              Fanxi server (stdlib HTTP + game sockets)
│   └── fanxi_server/
│       ├── http_api.py  /api/v1 router
│       ├── service.py   accounts, characters, sessions, inventory, quests
│       ├── db.py        SQLite connections + migrations
│       └── game/        ciphers, world, lobby, auth, zone,
│                        packets, entities, content
├── database/            schema migrations and seed data
├── data/                fanxi.db, TLS certificate (git-ignored)
├── host/ runtime/ recomp/ tools/   the native client and its build
├── tests/               the client's game-free checks
└── docs/                architecture, launcher, server, database, protocol
```

## Server configuration

All settings are optional; the defaults are for a local install. Read them from the environment
or pass the matching command-line flag.

| Variable | Default | Purpose |
|---|---|---|
| `FANXI_BIND` | `127.0.0.1` | Address for HTTP and game sockets (`0.0.0.0` to serve a LAN) |
| `FANXI_HTTP_PORT` | `8080` | Launcher API |
| `FANXI_PUBLIC_HOST` | `127.0.0.1` | Address the game client is told to connect to |
| `FANXI_DB` | `data/fanxi.db` | SQLite file |
| `FANXI_GAME_DIR` | auto-detected | Folder with `res/compress.dat` for the zone gateway |
| `FANXI_HUFFMAN` | — | Folder holding `compress.dat` |
| `FANXI_ADMIN_KEY` | empty | Key for `X-Admin-Key` calls; empty means admin accounts only |
| `FANXI_REGISTRATION` | `1` | Allow new accounts |
| `FANXI_MAX_CHARACTERS` | `1` | Characters per account |
| `FANXI_SESSION_DAYS` | `30` | Launcher session lifetime |
| `FANXI_LOGIN_TOKEN_SECONDS` | `120` | Launch-token lifetime |
| `FANXI_GAME_SESSION_HOURS` | `12` | In-game session lifetime |
| `FANXI_TLS_CERT` / `FANXI_TLS_KEY` | `data/tls/...` | Auth gateway certificate |
| `FANXI_CORS_ORIGIN` | `*` | CORS origin for the HTTP API |

Ports: `FANXI_AUTH_PORT` 54231, `FANXI_DATA_PORT` 54230, `FANXI_VIEW_PORT` 54001,
`FANXI_ZONE_PORT` 54230, `FANXI_SEARCH_PORT` 54002.

### Running it for friends

The server is intentionally simple to host:

```bash
cd server
FANXI_BIND=0.0.0.0 \
FANXI_PUBLIC_HOST=203.0.113.10 \
FANXI_ADMIN_KEY="$(openssl rand -hex 24)" \
python3 -m fanxi_server run
```

Open `8080/tcp` (API), `54231/tcp` (auth), `54230/tcp` and `54230/udp` (data and zone),
`54001/tcp` (lobby) and `54002/udp` (search) on the firewall. Put the HTTP API behind TLS
(a reverse proxy such as Caddy or nginx) if it is on the public internet; the game auth port
already uses a generated self-signed certificate, and the client does not verify it (private
servers work that way). Set `FANXI_ADMIN_KEY` to a long random value, or leave it unset and use
an account with the `admin` role.

Do not expose the server without understanding the trust model in
[docs/architecture.md](docs/architecture.md): the launcher API is authenticated, but the game
protocol is the game protocol, and the world has no anti-cheat.

## Development

```bash
./scripts/test.sh          # server + launcher unit/integration tests, then byte-compile
python3 -m fanxi_server doctor          # from server/: configuration in one screen
python3 -m unittest discover -s server/tests -v
python3 -m unittest discover -s launcher/tests -v
python3 tools/build_posix.py vfstest    # game-free client check
```

The server tests include a live TLS auth exchange, lobby character-list and zone hand-off, and a
zone login packet. No game files are needed for any of them; the tests use a synthetic Huffman
table.

The client's own game-free checks live in `tests/` and are described in
[docs/development.md](docs/development.md). Building the actual client needs your game files and
is done by the launcher (or `python3 tools/setup.py` for the full macOS app bundle).

## Documentation

- [Architecture](docs/architecture.md) — components, data flow, ports, trust boundaries
- [Launcher](docs/launcher.md) — settings, build, troubleshooting
- [Server](docs/server.md) — API reference, deployment, admin operations
- [Database](docs/database.md) — schema, migrations, backup and restore
- [World](docs/world.md) — NPCs, monsters, combat, inventory, shop and quest
- [Protocol](docs/protocol.md) — the auth, lobby and zone subset
- [LandSandBoat study](docs/landsandboat-study.md) — clean-room research notes and license boundary
- [Development](docs/development.md) — repository layout, tests, conventions
- [Identity](docs/identity.md) — naming, bundle IDs and removed integrations
- [Security](SECURITY.md) — reporting, secrets and the trust model

## License and legal

Fanxi is MIT-licensed. Portions of the client are derived from an MIT-licensed project; the
required notice is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Vendored libraries
(SDL3, mbedTLS, LuaJIT, SQLite, Dear ImGui and others) keep their own licenses under
`third_party/`.

FINAL FANTASY XI and SQUARE ENIX are trademarks of Square Enix Holdings Co., Ltd. Fanxi is an
unofficial, non-commercial project, not affiliated with or endorsed by Square Enix. It ships no
game data and no game binaries. You must own FINAL FANTASY XI and provide your own installation;
the build reads your `FFXiMain.dll`, `FFXi.dll` and `ROM` and never redistributes them.
