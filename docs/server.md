# Server

The Fanxi server is a Python 3.9+ standard-library service. It has two halves that start together:

- the **HTTP API** the launcher uses (default `127.0.0.1:8080`);
- the **game gateway** the recompiled client uses (auth, data, lobby, zone).

The only state is SQLite (`data/fanxi.db` by default). There is no Redis, no message queue and no
external service to install.

## Run it

From the repository:

```bash
cd server
python3 -m fanxi_server init            # create the database and starter data
python3 -m fanxi_server create-admin    # prompt for an administrator
python3 -m fanxi_server run             # HTTP + game gateway
```

Or use the helpers at the repository root:

```bash
./scripts/init.sh      # init + create-admin
./scripts/server.sh    # run
./scripts/dev.sh       # server and launcher together
```

`FANXI_GAME_DIR` (or `--game-dir`) tells the gateway where `res/compress.dat` is, and is also
where the collision meshes for monster navigation are read from. The gateway
needs it to compress zone packets; without it the server still runs the HTTP API, but the game
cannot enter a zone. If you press Play and the server has no gateway, the launcher reports the
auth failure; fix the game folder or `FANXI_HUFFMAN`.

### Check configuration

```bash
python3 -m fanxi_server doctor
```

It prints the repository, database, HTTP address, public host, game ports, game folder,
`compress.dat`, registration state and whether an admin key is set.

### Ports

| Port | Protocol | Purpose |
|---|---|---|
| 8080 | TCP | Launcher HTTP API |
| 54231 | TCP + TLS | Game sign-in (JSON) |
| 54230 | TCP | Login data connection |
| 54001 | TCP | Lobby |
| 54230 | UDP | Zone |
| 54002 | TCP | Search (`/sea all`, `/sea <name>`) |

The data and zone ports share `54230` on TCP and UDP, as the client expects.

## The world

The zone gateway hosts the imported world. Its design, packet flow and limits are in
[world.md](world.md). In short:

- **Port Jeuno (246):** 126 NPCs imported from the retail zone data — Cumetouflaix (the quest
  giver), the merchants Challoux, Gekko, Kindlix, Leyla and Pyropox, and the Home Points;
- **West Ronfaure (100):** the imported spawn table, with roam, aggro, combat, EXP/gil and respawn;
- **Quest:** Pest Control — defeat three Orcish Fodder and return to Cumetouflaix for 300 gil and
  two Potions;
- **Inventory:** 1,000 starter gil, two Potions and an Onion Sword, stored in SQLite.

NPCs and monsters are sent only after the client's first position (`0x015`), not during zone-in.
In game, use `//entities` to see targids, `//zone 100` for the camp and `//zone 246` for town.

Content lives in `world_npcs`, `npc_lines`, `monster_templates`, `monster_spawns`, `items`, `quests` and
`char_inventory`/`char_quests`; behaviour is in `server/fanxi_server/game/content.py`. The data is
durable; live monster HP/aggro/timers are in memory and reset on restart.

## HTTP API

Base path: `/api/v1`. Requests and responses are JSON unless noted. Errors look like:

```json
{"error": {"code": "invalid_credentials", "message": "invalid username or password"}}
```

### Public

| Method | Path | Body / query | Result |
|---|---|---|---|
| GET | `/health` | — | `{status, name, version}` |
| GET | `/status` | — | `{name, version, time, uptime_seconds, online, accounts, sub_accounts, characters, registration_open, world, features}` |
| GET | `/news` | `limit` (1–50) | `{news: [...]}` |
| GET | `/releases` | `platform`, `channel` | `{releases: [...]}` |
| POST | `/auth/register` | `{username, password, email?}` | `201 {token, expires_at, account}` |
| POST | `/auth/login` | `{username, password}` | `{token, expires_at, account, characters}` |

Registration creates a player account and an API session in one step. It returns the raw token
once.

### Authenticated

`Authorization: Bearer <token>` is required.

| Method | Path | Body | Result |
|---|---|---|---|
| POST | `/auth/logout` | — | `204` |
| GET | `/world/online` | — | `{gateway, characters: [{id, char_id, name, zone, zone_name}], count}` |
| GET | `/me` | — | `{account, characters}` |
| GET | `/characters` | — | `{characters: [...]}` |
| GET | `/characters/{id}/stats` | — | live stat sheet with every source (see below) |
| GET | `/characters/{id}/target` | — | selected mob's live effects for the Target Debuffs HUD; optional `?entity_id=<ServerId>` |
| GET | `/characters/{id}/chemist` | — | live Battle Bag, selection, stances and recasts for the Chemist HUD; also accepts the client's `ServerId` |
| POST | `/characters` | `{name, race, face, hair, size, nation, main_job, sub_job?}` | `201 {character}` |
| PATCH | `/characters/{id}` | `{name}` | `{character}` |
| PATCH | `/characters/{id}/design` | `{race?, face?, hair?, size?}` | `{character}` |
| GET | `/characters/{id}/gearswap/library` | `?job=WAR` | `{library: {job, name, source, updated_at}}` |
| PUT | `/characters/{id}/gearswap/library` | `{job, source, name?}` | `{library}` |
| DELETE | `/characters/{id}/gearswap/library` | `?job=WAR` query | `{library}` reseeded from the template |
| POST | `/launch` | `{character_id?}` | `{login_token, expires_at, account, character, world, client}` |
| GET | `/accounts/sub` | — | `{subs: [...], limit}` |
| POST | `/accounts/sub` | `{character?: {...}}` | `201 {sub, limit}` |
| POST | `/accounts/sub/{id}/launch` | `{character_id?}` | same shape as `/launch` |
| POST | `/accounts/sub/{id}/characters` | `{name?, race?, ...}` | `201 {character}` |
| DELETE | `/accounts/sub/{id}` | `purge=1` query | suspend, or purge |

`GET /characters/{id}/gearswap/library` reads the library owned by the character's account,
not by the character. `?job=` is the three-letter job (`WAR`, `RDM`, …); the first read for an
account copies the template account's current row for that job (`FANXI_GEARSWAP_TEMPLATE_ACCOUNT`,
default `onedough`) or, when that account has no row yet, the server's
`FANXI_GEARSWAP_DIR/<JOB>.lua`. `PUT` replaces only that account's row, so a character editing or
importing a library never changes another account. `DELETE` replaces that account's row with a
fresh template copy; the old row stays if the template cannot be read, so a reset cannot destroy a
library when the bundled file is missing. The main account's token may use any character it owns,
including its sub-accounts' characters; another account's character id returns `404`. Libraries are
capped at 512 KB and the HTTP body limit is 2 MB so a full hand-written GearSwap file fits.

`GET /characters/{id}/data` is the launcher's one-round-trip Data snapshot; its
`merits.categories` list carries all 50 merit menus and 274 rows in the client's order, with
each row's cap, cost ladder and the character's current rank. `POST /characters/{id}/merits`
still accepts `{"top_off": true}` and `{"points": n}`, and also
`{"upgrades": {"384": 5}, "spend": false}` for a merit layout. The layout form validates each
row's cap and each menu's category cap; `spend: true` charges the net cost to the unspent pool
and refunds a lower layout.

`POST /characters/{id}/ascension` writes or clears the two augment rows on one Shantotto's
Ascension copy: `{container, slot, choices: ["phantom_roll_5"]}`, with an empty `choices` list
to clear. The Data snapshot carries `ascension.items` (each bag copy and its current rows) and
`ascension.options` (the add-on's 33-row table). The Phantom Roll row is the same mod 1076 the
ability recast path reads.

`GET /world/online` is the authoritative online roster (the same one `/sea all` reads). It lists
live zone sessions, not `game_sessions` login rows: after a server restart the rows still exist
for clients the world has forgotten, so they are not proof that a character is online. `gateway` is false when the game gateway is not attached (API-only server),
in which case `characters` is empty and the launcher must not treat that as "everyone is offline".
The public `/status` `online` count uses the same roster while the gateway is attached.

`GET /characters/{id}/target` returns `{target: {id, name, hpp, distance} | null, effects: [...]}`.
Each effect carries its status id, icon id, name (when the cast recorded it), remaining seconds,
potency/power, damage tick and interval, and the hidden flag for a secondary song row. It is read
from the live session's target, or from `entity_id` (the client's target `ServerId`) so a target
change does not wait for the server's own target packet.

`GET /characters/{id}/stats` is the launcher's checkparam-style sheet. It resolves the live
zone session through the gateway, so it includes the equipment the character is actually wearing,
food, active buffs, job abilities, job traits, job-point gifts and merits. Each statistic carries
its final value and a source list (gear per slot, food, JT, JA, job points, buffs, merits, base and
skill); the source contributions add up to the same number `combat_mods()`/`stat_sheet()` use for
damage and magic. It answers `404` while the character is not in a zone (or when the gateway is
detached); the launcher shows a waiting state until a live session exists.

Sub-accounts are server-owned. A main account creates up to `FANXI_MAX_SUBS` (default 5) of
them; each is created with exactly one character. They have no password and no API session, and
the main's Bearer token is the only key: `POST /accounts/sub/{id}/launch` checks `parent_id` and
mints a normal single-use game launch token for the sub. Another account cannot list, launch or
delete them (the answer is `404`), and a sub cannot sign in on its own. Without `purge=1`,
`DELETE` suspends the sub and keeps its character; `purge=1` deletes both and frees the slot.
A party or alliance invitation to a sub from its own account family is accepted by the server
without the `0x0DC` prompt, so a headless box joins as soon as it is invited;
`FANXI_AUTO_ACCEPT_SUB_INVITES=0` restores the prompt.

`client` is ready for `host64`:

```json
{
  "server": "127.0.0.1",
  "auth_port": 54231,
  "data_port": 54230,
  "view_port": 54001,
  "username": "aria"
}
```

The `login_token` is single-use and expires after 120 seconds by default.

Character fields:

- `name`: 3–15 ASCII letters, unique.
- `race`: 1–8 (Hume M/F, Elvaan M/F, Tarutaru M/F, Mithra, Galka).
- `face`: 1–8, `hair`: 0 (A) or 1 (B), `size`: 0–2, `nation`: 0–2 (San d'Oria, Bastok,
  Windurst).  Face 2, Hair A is the client look byte `2`; the API returns both fields plus a
  `variant` 1–48 and a labelled `design` object.
- `PATCH /characters/{id}/design` changes one character's appearance and repaints its live zone
  session immediately.  The body may name only the fields that change.
- `main_job`: 1–22, `sub_job`: 0–22.

Character responses also include `hp`, `mp`, `hp_current`, `mp_current`, `exp`, `exp_next` and
`gil`. They are updated by the zone gateway as the player fights, shops and completes quests.

### Admin

Admin calls need either `X-Admin-Key: <FANXI_ADMIN_KEY>` or a Bearer token for an account whose
`role` is `admin`.

| Method | Path | Body |
|---|---|---|
| GET | `/admin/stats` | — (status plus the last 50 audit rows) |
| POST | `/admin/news` | `{slug, title, body}` |
| POST | `/admin/releases` | `{platform, version, url, sha256, channel?, size?, notes?, mandatory?}` |
| POST | `/admin/accounts/{id}/status` | `{status: "active"|"suspended"|"banned"}` |

Releases are metadata for the launcher (where an update would come from and its SHA-256); the
server does not host files itself. Put the artifacts behind a normal static host/CDN.

### Examples

```bash
curl -s http://127.0.0.1:8080/api/v1/status | python3 -m json.tool

TOKEN=$(curl -s -X POST http://127.0.0.1:8080/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"aria","password":"correct horse battery staple"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')

curl -s -X POST http://127.0.0.1:8080/api/v1/characters \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Aria","race":2,"nation":2,"main_job":3,"face":1,"size":1}'

curl -s -X POST http://127.0.0.1:8080/api/v1/launch \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
```

## Configuration

Everything is environment-driven. The command line for `run` can override the main ones.

| Variable | Default | Notes |
|---|---|---|
| `FANXI_BIND` | `127.0.0.1` | `0.0.0.0` for a LAN/public server |
| `FANXI_HTTP_PORT` | `8080` | Launcher API |
| `FANXI_PUBLIC_HOST` | `127.0.0.1` | The address written into the lobby replies and `/launch`; must be reachable from the player's machine |
| `FANXI_DB` | `data/fanxi.db` | SQLite file |
| `FANXI_GAME_DIR` | auto-detect | Folder containing `FFXiMain.dll` and `res/compress.dat` |
| `FANXI_HUFFMAN` | — | Folder containing `compress.dat` (wins over game dir) |
| `FANXI_GEARSWAP_DIR` | `gearswap` | Template folder for new account libraries (`<JOB>.lua`) |
| `FANXI_NAV_DIR` | `data/nav` | Walkable zone grids built from the game's collision meshes |
| `FANXI_NAV` | `1` | `0` disables collision-aware monster movement (legacy straight-line chase) |
| `FANXI_ADMIN_KEY` | empty | If empty, only `role = admin` accounts can use admin endpoints |
| `FANXI_REGISTRATION` | `1` | `0` closes registration (also `settings.registration_open`) |
| `FANXI_MAX_CHARACTERS` | `0` | Per account; `0` means unlimited |
| `FANXI_MAX_SUBS` | `5` | Server-owned sub-accounts per main; `0` disables them |
| `FANXI_AUTO_ACCEPT_SUB_INVITES` | `1` | Accept a party/alliance invite to a family sub without the `0x0DC` prompt |
| `FANXI_GEARSWAP_TEMPLATE_ACCOUNT` | `onedough` | New account libraries copy this account's current saved set |
| `FANXI_SESSION_DAYS` | `30` | Launcher token lifetime |
| `FANXI_LOGIN_TOKEN_SECONDS` | `120` | Launch token lifetime |
| `FANXI_GAME_SESSION_HOURS` | `12` | Game session lifetime |
| `FANXI_AUTH_PORT` / `FANXI_DATA_PORT` / `FANXI_VIEW_PORT` / `FANXI_ZONE_PORT` / `FANXI_SEARCH_PORT` | 54231 / 54230 / 54001 / 54230 / 54002 | Must match what the launcher passes to `host64` |
| `FANXI_TLS_CERT` / `FANXI_TLS_KEY` | `data/tls/auth-cert.pem` / `...-key.pem` | Generated with `openssl` on first run; replace with your own certificate if you like |
| `FANXI_CORS_ORIGIN` | `*` | Set to your web origin if you build a browser front end |
| `FANXI_LOG_LEVEL` | `info` | `debug` for protocol logs |
| `FANXI_ZONE_DEBUG` | unset | `1` logs every zone message type received |
| `FANXI_LAUNCHER_DIR` | platform data dir | Overrides the launcher's settings/token folder (development) |

## Deploying

### systemd

```ini
[Unit]
Description=Fanxi server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=fanxi
Group=fanxi
WorkingDirectory=/srv/fanxi/server
Environment=FANXI_BIND=0.0.0.0
Environment=FANXI_PUBLIC_HOST=203.0.113.10
Environment=FANXI_ADMIN_KEY=replace-with-a-long-random-value
Environment=FANXI_GAME_DIR=/srv/fanxi/game
ExecStart=/usr/bin/python3 -m fanxi_server run
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/srv/fanxi/data

[Install]
WantedBy=multi-user.target
```

`ProtectSystem=strict` needs `ReadWritePaths` for `data/`; the source tree is only read.

### TLS in front of the API

The launcher can speak HTTPS. Terminate TLS with Caddy:

```caddy
fanxi.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Then set the launcher's server to `https://fanxi.example.com`. The game auth port keeps its own
TLS (self-signed by default); the client does not verify it, as is normal for private servers.

A client that sends no SNI — Apple's `/usr/bin/python3` drops it for a name that begins with an
IPv4 literal, so `https://1.2.3.4.sslip.io` is one — gets Caddy's `internal error` alert instead
of a certificate. Name a fallback in the global block when anything but the launcher talks to
this host:

```caddy
{
    default_sni fanxi.example.com
}
```

### Firewall

Open only what players need: `8080/tcp` (or 443 if proxied), `54231/tcp`, `54230/tcp`,
`54230/udp`, `54001/tcp`, `54002/tcp`. Keep SSH and the database file private.

### Deploying an update

The server runs from a git checkout, so an update is a pull and a restart. Migrations in
`database/migrations/` are applied by the service at startup, in version order — which is why the
backup comes before the pull. The dashboard's deploy reads `schema_migrations` after the restart
and fails if any migration file in the checkout is still unapplied, so "healthy" cannot hide a
schema that is behind the code.

```bash
cd /srv/fanxi
git rev-parse HEAD > /tmp/fanxi-previous        # for a code rollback
sudo -u fanxi ./scripts/db-backup.sh            # before a migration touches the schema
git pull --ff-only
systemctl restart fanxi
sleep 2
systemctl is-active fanxi
curl -s http://127.0.0.1:8080/api/v1/health
journalctl -u fanxi -n 30 --no-pager
```

`/health` returns the server's `version`, so a bumped version in that response is the simplest
proof the new code is live.

If it does not come up, restore the data first, then the code:

```bash
systemctl stop fanxi
cp data/backups/fanxi-<newest>.db data/fanxi.db
rm -f data/fanxi.db-wal data/fanxi.db-shm
git checkout "$(cat /tmp/fanxi-previous)"
systemctl start fanxi
```

Two constraints worth knowing:

- The server's clone is shallow. A commit that is not on `origin/main` cannot be checked out, so
  push before deploying. If you copy files over with `rsync` instead, the checkout no longer
  matches the repository and the next `git pull` will fight you.
- Uncommitted changes on a development machine are not in `origin/main`, and therefore not in a
  `git pull`. Commit and push first.

The launcher is a separate artifact. A server update needs no launcher release unless the HTTP API
changed; a launcher release needs no server restart.

### Local dashboard

`tools/fanxi_tui.py` is a terminal dashboard you run on the machine you administer from, not on the
server. It drives the steps above over SSH and shows the state between them; it also reads the
client and launcher built on that machine and rebuilds them.

```bash
./tools/fanxi_tui.py
```

| Key | Action |
| --- | --- |
| `d` | deploy: backup, `git pull`, restart (applies migrations), verify `schema_migrations`, health check, offer rollback |
| `B` | rebuild the local client: `.venv` when missing, `tools/prepare.py` when the game folder changed, `tools/build_posix.py host64`, with the compile's progress in the output pane (`q` cancels) |
| `L` | rebuild the Rust + Tauri launcher: `npm ci` when the packages are missing or stale, then `npm run tauri build -- --bundles app` (macOS) or `--no-bundle` (Linux), streaming into the output pane (`q` cancels) |
| `O` | launch the launcher from the latest checkout: `git pull --ff-only`, rebuild it when the sources moved, quit the running copy and open the app |
| `R` | restart the service |
| `b` | take a backup on the server |
| `p` | pull the latest backup home (the homelab job, run by hand) |
| `l` | scroll the journal |
| `g` | toggle registration on/off |
| `a` | create or reset an admin (interactive, over a tty) |
| `m` | clone a character: asks for the source, searches the database for the target, confirms, then runs `tools/clone_character.py --force --apply` |
| `c` | open a shell on the server |
| `e` | edit `~/.fanxi-manager.json` |
| `r` | refresh now |

Clone character is destructive: it replaces the target's jobs, level, sub job, exp, gil, merits,
Home Points, inventory, storage, locker and worn outfit with the source's. The target must be
logged out; `--force` only covers the server's still-unexpired launch row for a client that is
already back at the lobby. `clone_character.py` takes a pre-clone database backup, and the target
needs a relog afterwards.

The status row's **client** is `build/fanxi` on this machine, the binary the launcher starts. It is
green when the build stamp (`build/runtime.json`) matches `runtime.json`, yellow when the version
changed or a client source is newer than the binary, and red when there is no build yet. Rebuild
it with `B` (or `--rebuild`): the dashboard uses the game folder and checkout from the launcher's
`launcher.json` when it finds them, so the same folder both tools build from; `game_dir` and
`repo` in `~/.fanxi-manager.json`, or `FANXI_GAME_DIR` and `FANXI_REPO_ROOT`, override that.
The flow is the launcher's Build game, not a different one: it creates `.venv` and installs
`capstone` and `pefile` when they are missing, runs `tools/prepare.py` when `generated/build.json`
is missing or names another folder, then runs `tools/build_posix.py host64`. The first build takes
several minutes and needs network once; later ones are incremental. Every line is kept in
`build/tui-build.log`, and the binary that was there is copied to `build/fanxi.previous` first, so
a failed link puts the client the launcher starts back instead of leaving none. Clients already
running keep the old binary until they are restarted, and `Fanxi.app` (the bundle
`tools/setup.py` makes) is a separate build.

The launcher half is **Rebuild launcher** (`L`, or `--rebuild-launcher`): it builds
`launcher-rs` with install.sh's own steps — `npm ci` when `node_modules` is missing or older
than `package-lock.json`, then `npm run tauri build -- --bundles app` on macOS (the app the
launcher is run from, at `launcher-rs/src-tauri/target/release/bundle/macos/Fanxi Launcher.app`)
or `--no-bundle` on Linux. The output streams into the pane, cancelling with `q`, and goes to
`build/tui-launcher.log`. It does not copy the app to `~/Applications` or restart a running
launcher; `--status` reports the build's version and whether the sources are newer.

**Launch launcher** (`O`, or `--launch-launcher`) is the one-button version: it runs
`git pull --ff-only`, rebuilds only when the pulled sources are newer than the built app, then
stops any launcher running from this checkout and opens the new app. The game clients the
launcher started keep running; the launcher itself is the thing that restarts.

If the dashboard was started by an Intel or Anaconda python, it runs under Rosetta on Apple
silicon. A universal binary such as `/usr/bin/clang` then takes the caller's architecture
preference and would build the whole client x86_64 — including a link against the native objects
already on disk. The dashboard detects this and pins `XI_CC`/`XI_CXX` to this Mac's own
architecture (`clang -arch arm64` on Apple silicon, unless you set them yourself), which changes
the recorded build flags so `build_posix.py` drops the mixed objects and recompiles them. That
first build is a full one; later ones are incremental again. Starting the dashboard with a native
`python3` (`/opt/homebrew/bin/python3`) avoids it.

The menu is navigable three ways — ↑↓ and Enter, a mouse click, or the hotkey in the label — and
the pane beside it explains the selected action and states its risk. Anything that changes the
server asks for confirmation first, with the risk repeated in the dialog and "no" as the default,
so a stray key cannot restart the box. Colour marks state: green for healthy, yellow for stale,
red for broken or destructive.

The first run asks for the ssh destination, the checkout path and the launcher URL, and writes
`~/.fanxi-manager.json` mode 0600. `FANXI_SSH`, `FANXI_REMOTE_DIR`, `FANXI_URL` and
`FANXI_SSH_KEY` override it; `FANXI_GAME_DIR` and `FANXI_REPO_ROOT` override the local client
paths described above.

Five non-interactive modes use the same code, so they can be scripted:

```bash
./tools/fanxi_tui.py --status            # the report, no curses
./tools/fanxi_tui.py --deploy            # the deploy sequence, exit 1 on failure
./tools/fanxi_tui.py --rebuild           # the local client build, no curses
./tools/fanxi_tui.py --rebuild-launcher  # the launcher build, no curses
./tools/fanxi_tui.py --launch-launcher   # pull, rebuild if needed, open the launcher
```

`--rebuild` takes `--game <FINAL FANTASY XI folder>` and `--repo <checkout>` when discovery would
pick the wrong one; `--rebuild-launcher` and `--launch-launcher` take `--repo`, and `--status`
accepts the same two.

It uses `ssh -o BatchMode=yes` with your existing key, so it fails fast instead of prompting, and it
only writes the database through the server's own commands (`db-backup.sh`, `create-admin`,
`clone_character.py`); the character search is a read-only query.

### Backups

```bash
./scripts/db-backup.sh                 # data/backups/fanxi-YYYYmmdd-HHMMSS.db
```

The script uses SQLite's online backup API, so it is safe while the server runs. It keeps the
newest 14 copies and deletes the rest (`FANXI_BACKUP_KEEP=30` to change that, `0` keeps
everything); without retention a daily backup of a small database fills the disk within a year.
A daily cron entry is enough for a friend server:

```cron
15 4 * * * /srv/fanxi/scripts/db-backup.sh >/dev/null
```

Keep a copy off-machine. The TLS private key and `launcher.json` (on a player machine) are
separate secrets.

### Off-site copy to a homelab

`scripts/pull-offsite-backup.sh` runs **on the machine that keeps the copies** (a homelab, a NAS,
a desktop), not on the server. It asks the server for a fresh snapshot over SSH, copies it down,
checks the copy with SQLite's `integrity_check`, and deletes local copies older than a week.

Pull rather than push on purpose: the homelab already reaches the internet, so the server needs no
route back and the homelab exposes no port. A failed night exits non-zero **before** pruning, so a
broken transfer never removes the last good backup.

```bash
# once: the homelab's key, so the cron job is unattended
ssh-keygen -t ed25519 -f ~/.ssh/fanxi-backup -N ''
ssh-copy-id -i ~/.ssh/fanxi-backup.pub root@203.0.113.10   # or append to authorized_keys

# daily, from the homelab
FANXI_SSH=root@203.0.113.10 \
FANXI_BACKUP_DIR=$HOME/backups/fanxi \
  /path/to/fanxi/scripts/pull-offsite-backup.sh
```

```cron
30 4 * * * FANXI_SSH=root@203.0.113.10 FANXI_BACKUP_DIR=/srv/backups/fanxi /srv/tools/pull-offsite-backup.sh >>/var/log/fanxi-backup.log 2>&1
```

`FANXI_REMOTE_DIR` defaults to `/srv/fanxi` and `FANXI_KEEP_DAYS` to `7`. Run it once a day; an
hourly timer keeps 24× as many files for the same seven days.

The copy on the homelab is the raw database: password hashes and live session tokens included.
Either keep it on an encrypted volume or encrypt it (`age -r <key> fanxi-*.db`), and treat the
homelab disk as a secret of the same weight as `data/tls/`.

**Restore it once, before you need it.** A backup you have never restored is a hypothesis:

```bash
systemctl stop fanxi
install -m 600 -o fanxi -g fanxi fanxi-20261101-043000.db /srv/fanxi/data/fanxi.db
rm -f /srv/fanxi/data/fanxi.db-wal /srv/fanxi/data/fanxi.db-shm   # the old write-ahead log
systemctl start fanxi
python3 -m fanxi_server doctor
```

Dropping the `-wal` and `-shm` files matters: leaving them next to a replaced database applies the
old log to the new file.

### Closing registration without restarting

```bash
sqlite3 data/fanxi.db "update settings set value='0' where key='registration_open';"
```

Set it back to `'1'` to reopen. With `FANXI_REGISTRATION` at its default (`1`), the database
setting decides; `FANXI_REGISTRATION=0` closes registration regardless of the database.

## Security checklist

- [ ] Set `FANXI_ADMIN_KEY` to a long random value, or create an admin account and leave the key
      unset. Never ship a default key.
- [ ] Change `FANXI_PUBLIC_HOST` to a reachable address; do not leave `127.0.0.1` on a remote
      server (players would be told to connect to themselves).
- [ ] Put the HTTP API behind TLS if it is public.
- [ ] Restrict the game ports to your community (firewall, VPN, or a private network) if you do
      not want the protocol exposed.
- [ ] Back up `data/fanxi.db` and `data/tls/`.
- [ ] Review `audit_log` for unexpected admin actions.
- [ ] Keep Python and the OS patched; there are no Python package dependencies.

## Troubleshooting

| Symptom | Check |
|---|---|
| `Address already in use` | Another Fanxi is running, or another service owns 8080/54231/54230/54001. Change `FANXI_HTTP_PORT` and the game ports together (the launcher gets them from the API). |
| Launcher says the server is unreachable | `python3 -m fanxi_server doctor`, then `curl http://127.0.0.1:8080/api/v1/health`. |
| Sign-in works, Play fails with auth error | The game gateway is off: set `FANXI_GAME_DIR` or `FANXI_HUFFMAN` so `res/compress.dat` is found. `doctor` shows it. |
| Client connects to the wrong address | `FANXI_PUBLIC_HOST` must be the address reachable from the client; the lobby and `/launch` both use it. |
| `database is locked` | SQLite WAL should prevent it; check for a stale process or a network filesystem (SQLite does not support network filesystems). |
| Zone login rejected | The launch token was already used or expired. Press Play again. Check the server log for `without an active session`. |
| Zone loads but no NPCs/monsters appear | The client has not sent its first `0x015` position yet, or `FANXI_ZONE_DEBUG=1` shows no `0x00E` replies. Check that the content migration ran (`sqlite3 data/fanxi.db "select count(*) from world_npcs"`). |
| Inventory looks empty or gil is wrong | The gil slot must be item id `65535` in container 0 slot 0. Migration `0003_world_content.sql` backfills old rows. |
| `TLS` errors | Delete `data/tls/auth-cert.pem` and `auth-key.pem` and restart to regenerate; the client does not verify the certificate. |
| Character name rejected | 3–15 ASCII letters, unique across the world. |
