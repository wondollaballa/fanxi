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

`FANXI_GAME_DIR` (or `--game-dir`) tells the gateway where `res/compress.dat` is. The gateway
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
| 54002 | UDP | Search (advertised, reserved) |

The data and zone ports share `54230` on TCP and UDP, as the client expects.

## The world

The zone gateway hosts a small original world. Its design, packet flow and limits are in
[world.md](world.md). In short:

- **Port Jeuno (246):** the Fanxi Guide (quest), the Wandering Moogle (shop), the Chocobo
  Stablehand (dialogue);
- **West Ronfaure (100):** three Orcish Grunts and three Lambton Worms, with roam, aggro, combat,
  EXP/gil and respawn;
- **Quest:** Pest Control — defeat three Orcish Grunts and return to the Guide for 300 gil and two
  Potions;
- **Inventory:** 1,000 starter gil, two Potions and an Onion Sword, stored in SQLite.

NPCs and monsters are sent only after the client's first position (`0x015`), not during zone-in.
In game, use `!entities` to see targids, `!zone 100` for the camp and `!zone 246` for town.

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
| GET | `/me` | — | `{account, characters}` |
| GET | `/characters` | — | `{characters: [...]}` |
| POST | `/characters` | `{name, race, face, hair, size, nation, main_job, sub_job?}` | `201 {character}` |
| PATCH | `/characters/{id}` | `{name}` | `{character}` |
| PATCH | `/characters/{id}/design` | `{race?, face?, hair?, size?}` | `{character}` |
| POST | `/launch` | `{character_id?}` | `{login_token, expires_at, account, character, world, client}` |
| GET | `/accounts/sub` | — | `{subs: [...], limit}` |
| POST | `/accounts/sub` | `{character?: {...}}` | `201 {sub, limit}` |
| POST | `/accounts/sub/{id}/launch` | `{character_id?}` | same shape as `/launch` |
| POST | `/accounts/sub/{id}/characters` | `{name?, race?, ...}` | `201 {character}` |
| DELETE | `/accounts/sub/{id}` | `purge=1` query | suspend, or purge |

Sub-accounts are server-owned. A main account creates up to `FANXI_MAX_SUBS` (default 5) of
them; each is created with exactly one character. They have no password and no API session, and
the main's Bearer token is the only key: `POST /accounts/sub/{id}/launch` checks `parent_id` and
mints a normal single-use game launch token for the sub. Another account cannot list, launch or
delete them (the answer is `404`), and a sub cannot sign in on its own. Without `purge=1`,
`DELETE` suspends the sub and keeps its character; `purge=1` deletes both and frees the slot.

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
| `FANXI_ADMIN_KEY` | empty | If empty, only `role = admin` accounts can use admin endpoints |
| `FANXI_REGISTRATION` | `1` | `0` closes registration (also `settings.registration_open`) |
| `FANXI_MAX_CHARACTERS` | `0` | Per account; `0` means unlimited |
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

### Firewall

Open only what players need: `8080/tcp` (or 443 if proxied), `54231/tcp`, `54230/tcp`,
`54230/udp`, `54001/tcp`, `54002/udp`. Keep SSH and the database file private.

### Backups

```bash
./scripts/db-backup.sh                 # data/backups/fanxi-YYYYmmdd-HHMMSS.db
```

The script uses SQLite's online backup API, so it is safe while the server runs. Keep a copy
off-machine. The TLS private key and `launcher.json` (on a player machine) are separate secrets.

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
