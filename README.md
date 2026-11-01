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
| **Launcher** | A native Rust + Tauri 2 desktop app with a React front end | `launcher-rs/` |
| **Server** | Fanxi's HTTP API plus the FINAL FANTASY XI auth, lobby and zone gateway | `server/` |
| **Database** | SQLite: accounts, sessions, characters, zones, news, releases | `database/` |

> **Native launcher.** `launcher-rs/` is a Rust + Tauri 2 desktop app with a React front end: the
> accounts, characters, sub-account team, control room, GearSwap tools and build hand-off in one
> native window. The earlier Python/Tkinter launcher it grew from has been removed; an existing
> `launcher.json` carries over unchanged. See [launcher-rs/README.md](launcher-rs/README.md).

> **Project status.** The client is the mature part: the recompiler, renderer, audio, input and
> addon host are ported from a working native build. The Fanxi launcher, server and database are
> new and functional: sign-in, character creation, launch hand-off, lobby and zone-in work end to
> end. The world is now a small original vertical slice: NPCs, a shop, a hunt quest, roaming
> monsters, melee and monster TP-move combat, EXP/levels, inventory and respawns. It is not a full retail world
> yet; the boundary is documented in [docs/world.md](docs/world.md).

## Quick start

You need:

- Windows 10/11 (x64) or macOS on Apple silicon (M1 or later) to run the client; Windows is the
  player platform. The launcher runs on Windows, macOS and Linux; the server is Python 3.9+ only.
- On Windows, building the client needs a C toolchain. [`tools/build_mingw.py`](tools/build_mingw.py)
  builds `Fanxi.exe` with llvm-mingw and no Visual Studio; the player kit described in
  [Onboarding](docs/onboarding.md) will carry that toolchain, SDL3 and Python so a player installs
  nothing else. A developer checkout can use Visual Studio Build Tools with
  [`tools/build.py`](tools/build.py).
- Node 18+ and Rust 1.85+ if you build the launcher from source (`install.sh` drives both; on
  Linux also install the WebKitGTK/Tauri packages).
- Your own copy of FINAL FANTASY XI: a `FINAL FANTASY XI` folder containing `FFXiMain.dll`,
  `FFXi.dll` and `ROM`.

On Windows, install the launcher from the release's `-setup.exe`; `install.sh`, `setup.command` and
the helper scripts under `scripts/` are macOS and Linux only.

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
./scripts/launcher.sh
```

In the launcher:

1. Create a player account (or sign in). **Accounts → Add account** adds another account for
   multiboxing.
2. Create a character. **Characters → New mule** makes as many as you like.
3. Open **Settings**, point *Game folder* at your FINAL FANTASY XI folder, and press **Build
   game**. The first build translates the game and compiles `Fanxi`; it takes a few minutes.
4. Press **Play** (or open **Control** and press **Launch** / **Launch all**). The launcher asks
   the server for a single-use launch token, starts `Fanxi`, and the game signs in through
   Fanxi's auth gateway. Keep the launcher open: it is the control room for commands, live
   EXP/hr/DPS and gear.

You start in Port Jeuno. Cumetouflaix, the NPC beside the arrival point, starts **Pest
Control**; the port's merchants (Gekko sells Potions) open shops. Say `//zone 100` to visit the
West Ronfaure camp, fight three Orcish Fodder, then return to Cumetouflaix. `//entities`, `//heal`,
`//where`, `//mount` (and `//mount party` for the team) and `//help` are available in chat.

The launcher's default server is `http://127.0.0.1:8080`. Everything can live on one machine, or
the server can run elsewhere and the launcher can point at it in **Settings**.

## What is new here

### Our launcher

`launcher-rs/` is Fanxi's own desktop app: a Rust core behind a React front end, packaged as a
native window with Tauri 2. The Rust side owns the machine-facing work — tokens, builds, game
processes and control ports — and the UI never sees a stored token. It:

- signs in to one or more Fanxi accounts over the HTTP API and keeps each session token in a
  `0600` file (never a password);
- creates unlimited characters (mules) on an account and keeps them in a picker;
- creates server-owned sub-account boxes and launches the whole team, windowed or headless;
- opens a **Control room** that launches several clients, one per account, and shows each one's
  zone, HP/MP, EXP/hr and DPS;
- sends in-game commands such as `//zone`, `//merits` and `//heal` to any running client;
- saves `//warp` places and can mark, rename, delete and warp to them from the **Warps** page,
  alone or with every online character on the account and its sub-accounts, and has a **Warp
  team to me** button that calls the whole team to the selected character;
- has an in-game **Mount HUD** with a picture of every mount the client knows: pick one and press
  **Mount** or **Mount party**, or type `//mount <name>` / `//mount party`. *Mount party* gives
  every box in the sub team its own random mount; see [docs/mounts.md](docs/mounts.md);
- tells a live client from a live character: a box that lost its zone session shows **orphaned**
  or **logged out** with **Reconcile** / **Relaunch** instead of a green row, **Reconcile N**
  restarts every stale box after a server restart, and a box that comes back from a relog is
  pulled to the leader by itself (`//warp call <name>`);
- completes `//` commands in the game's chat line with Tab when the typed word is unique, and
  leaves an ambiguous prefix alone until another letter narrows it;
- reads the active gear of each client, detects its live main job, loads that job's default
  GearSwap library, and can import/edit/save timestamped versions from the **Gear** page, with a
  launcher-wide **GearSwap** on/off switch for players who do not want auto-swapping;
- stores the game folder and finds `Fanxi`;
- builds the client from your own game files (it creates `.venv`, installs `capstone` and
  `pefile`, and streams the build log);
- asks the server for a one-time launch token and starts `Fanxi` with the right ports and a
  per-client control port;
- shows server status and news, and packages itself for this OS:

```bash
cd launcher-rs
npm run tauri build          # .app/.dmg (macOS), AppImage/deb (Linux), MSI/NSIS (Windows)
```

No passwords are stored by the launcher. The token is the only credential on disk. The same app
is the multibox control panel: saved accounts, unlimited mules, a party launcher, live EXP/hr and
DPS, a command console, and a Gear/GearSwap window. See
[docs/control-panel.md](docs/control-panel.md).

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
cipher. The launcher never sees the game password and the client never sees the launcher token after
it is used.

The zone gateway implements the packets needed to sign in, stand in a zone, see the character,
move, change zones and talk/attack. Its small world adds:

- 126 imported NPCs in Port Jeuno (`//zone 246`), including the quest giver and five merchants;
- the imported West Ronfaure spawn table (`//zone 100`);
- monsters that walk the zone's own collision mesh: they roam and chase on the floor, path
  around walls and cliffs, and cannot aggro or swing through them
  ([details](docs/world.md#zone-navigation));
- click-to-talk dialogue and the persistent **Pest Control** hunt quest;
- basic melee combat with `0x028` action packets, HP updates, EXP, gil and level-ups;
- an 80-slot inventory with gil, Potions and starter swords;
- a job-aware storage command (`//storage organize | store <job|all> | grab <job|all> | list`)
  reachable from any zone: everything the current job cannot equip leaves the bags, a slip where
  one accepts the item and the hidden 9,999-slot locker where none does, and the job's own set is
  pulled back into the Mog Wardrobes. `//job` runs the same organizer, so only the active job's
  gear is out and no mule is needed;
- a hidden 9,999-slot locker (`//locker store|grab|list <all|ammo|back|jsecapes|materials|name>`) for the
  198 Ambuscade JSE cape builds, ammo, crafting materials and everything else a slip does
  not accept;
- working-stock auto-refill: `//stock` keeps a visible stack of ninjutsu tools, pet food and Dawn
  Mulsum in the inventory, pulling from the hidden locker when they are used;
- a dropped link keeps your buffs and ability cooldowns: the reconnect restores the song list
  and the recast timers from the server, then tells you what it held
  ([details](docs/world.md#recovering-a-dropped-client));
- monster death, rewards and respawn.

Server commands: `//zone`, `//warp`, `//invite`, `//makeparty`, `//pos`, `//where`, `//entities`,
`//trust`, `//heal`, `//time`, `//storage`, `//locker`, `//recycle`, `//bags`, `//stock`, `//help`. `//warp` marks your own
camps (`//warp mark [alias]`) and returns to them by number or alias (`//warp me 1`, `//warp all 1`
for your sub-account boxes); `//warp all me` calls the whole online team to your current spot, and
`//warp call <name>` calls one box — the launcher sends that by itself when a relogged box is back
in game.
`//invite subs` parties every online sub-account in one command, or `//invite <name>` one player;
`//makeparty` drops the subs out of any old parties first (the Party Info HUD has a **Make party**
button for it). The Control room's **Invite** button offers the same choices. The launcher's
**Warps** page edits the same list and has the same **Warp team to me** button. Positions are
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
├── launcher-rs/         Fanxi Launcher (Rust + Tauri 2, React)
│   ├── src/             React pages and components
│   └── src-tauri/       Rust core: API, config, game, control, gear, commands
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
| `FANXI_MAX_CHARACTERS` | `0` | Characters per account (`0` = unlimited) |
| `FANXI_MAX_SUBS` | `5` | Server-owned sub-accounts per main (`0` disables them) |
| `FANXI_AUTO_ACCEPT_SUB_INVITES` | `1` | A family sub joins a party/alliance without a prompt |
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
`54001/tcp` (lobby) and `54002/tcp` (search) on the firewall. Put the HTTP API behind TLS
(a reverse proxy such as Caddy or nginx) if it is on the public internet; the game auth port
already uses a generated self-signed certificate, and the client does not verify it (private
servers work that way). Set `FANXI_ADMIN_KEY` to a long random value, or leave it unset and use
an account with the `admin` role.

Do not expose the server without understanding the trust model in
[docs/architecture.md](docs/architecture.md): the launcher API is authenticated, but the game
protocol is the game protocol, and the world has no anti-cheat.

## Development

```bash
./scripts/test.sh          # server, launcher and tool tests
python3 -m fanxi_server doctor          # from server/: configuration in one screen
python3 -m unittest discover -s server/tests -v
cd launcher-rs && npm run check && cargo test --manifest-path src-tauri/Cargo.toml
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
- [Retail client data](docs/retail-data.md) — where the data comes from, patching it with PlayOnline, and importing the result
- [Launcher](docs/launcher.md) — settings, build, troubleshooting
- [Releases](docs/release.md) — tagging, the build matrix, signing, and what a release may not contain
- [Onboarding](docs/onboarding.md) — the player kit: how a download becomes a Play button with no toolchain install
- [Battle hub](docs/battle.md) — camps, formations, pulling, healing and the automation rules
- [Character design](docs/character-design.md) — in-game model changes, the Design page and preview captures
- [Server](docs/server.md) — API reference, deployment, admin operations
- [Database](docs/database.md) — schema, migrations, backup and restore
- [World](docs/world.md) — NPCs, monsters, combat, inventory, shop and quest
- [Custom jobs](docs/custom-jobs.md) — adding a job, the DAT boundary and a delivery plan
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
