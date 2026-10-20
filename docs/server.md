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

## HTTP API

Base path: `/api/v1`. Requests and responses are JSON unless noted. Errors look like:

```json
{"error": {"code": "invalid_credentials", "message": "invalid username or password"}}
```

### Public

| Method | Path | Body / query | Result |
|---|---|---|---|
| GET | `/health` | — | `{status, name, version}` |
| GET | `/status` | — | `{name, version, time, uptime_seconds, online, accounts, characters, registration_open, world, features}` |
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
| POST | `/characters` | `{name, race, face, size, nation, main_job, sub_job?}` | `201 {character}` |
| PATCH | `/characters/{id}` | `{name}` | `{character}` |
| POST | `/launch` | `{character_id?}` | `{login_token, expires_at, account, character, world, client}` |

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
- `face`: 1–8, `size`: 0–2, `nation`: 0–2 (San d'Oria, Bastok, Windurst).
- `main_job`: 1–22, `sub_job`: 0–22.

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
| `FANXI_REGISTRATION` | `1` | `0` closes registration |
| `FANXI_MAX_CHARACTERS` | `1` | Per account |
| `FANXI_SESSION_DAYS` | `30` | Launcher token lifetime |
| `FANXI_LOGIN_TOKEN_SECONDS` | `120` | Launch token lifetime |
| `FANXI_GAME_SESSION_HOURS` | `12` | Game session lifetime |
| `FANXI_AUTH_PORT` / `FANXI_DATA_PORT` / `FANXI_VIEW_PORT` / `FANXI_ZONE_PORT` / `FANXI_SEARCH_PORT` | 54231 / 54230 / 54001 / 54230 / 54002 | Must match what the launcher passes to `host64` |
| `FANXI_TLS_CERT` / `FANXI_TLS_KEY` | `data/tls/auth-cert.pem` / `...-key.pem` | Generated with `openssl` on first run; replace with your own certificate if you like |
| `FANXI_CORS_ORIGIN` | `*` | Set to your web origin if you build a browser front end |
| `FANXI_LOG_LEVEL` | `info` | `debug` for protocol logs |
| `FANXI_ZONE_DEBUG` | unset | `1` logs every zone message type received |

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
| `TLS` errors | Delete `data/tls/auth-cert.pem` and `auth-key.pem` and restart to regenerate; the client does not verify the certificate. |
| Character name rejected | 3–15 ASCII letters, unique across the world. |
