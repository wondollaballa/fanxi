# Development

## Requirements

- Python 3.9+ (the launcher and server use only the standard library; `tkinter` for the UI).
- macOS with Apple silicon and Clang for the client build.
- `capstone` and `pefile` (installed into `.venv` by the launcher/build).
- CMake and Ninja for the vendored SDL build.
- The tests do **not** need game files. Building the actual client does.

## Layout

| Path | What lives there |
|---|---|
| `launcher/fanxi_launcher/` | `config.py` (settings), `api.py` (HTTP client), `game.py` (find/build/launch), `app.py` (Tk UI), `__main__.py` |
| `launcher/tests/` | settings, HTTP client, game-folder and command-line tests |
| `launcher/build_app.py` | macOS `.app` / Linux `.desktop` packaging |
| `server/fanxi_server/` | `config.py`, `db.py`, `security.py`, `service.py`, `http_api.py`, `cli.py` |
| `server/fanxi_server/game/` | `cipher.py`, `world.py`, `zone.py`, `gateway.py`, `packets.py`, `entities.py`, `content.py` |
| `server/tests/` | service, API, packet, world/combat/quest and live-gateway tests |
| `database/` | migrations and seed SQL |
| `host/`, `runtime/`, `recomp/`, `tools/` | the recompiled client, its platform layer and build tools |
| `tests/` | the client's game-free tests (replay, VFS, geometry, addons, Android) |
| `docs/` | this documentation |

## Tests

```bash
./scripts/test.sh

python3 -m unittest discover -s server/tests -v
python3 -m unittest discover -s launcher/tests -v

# game-free client checks
python3 tools/build_posix.py vfstest
python3 tests/replay_test.py -v
python3 tests/geometry_simd_test.py
```

The server tests start the real TLS auth listener on free ports, exchange a launch token, open
the lobby, request the character list and zone hand-off, and send a synthetic zone login packet.
They use a generated 8-bit Huffman table, so they run without `compress.dat`.

World tests build a scratch database, create a character, load the seeded Port Jeuno/West
Ronfaure content, exercise the first-`0x015` spawn trigger, talk to the Guide, buy from the
Moogle, fight a monster to death, check the reward packets and quest progress, and verify that a
dead monster respawns. Packet tests decode the bit-packed `0x028` action and check the fixed
sizes of the login, job, status and inventory packets.

## Adding world content

Static content lives in SQL migrations:
`database/migrations/0002_world_content.sql` defines the tables and
`0003_world_content.sql` seeds the starter slice. Add a new numbered migration; do not edit an
applied one.

- NPC instance: `world_npcs` (zone, script, position, model, flags), optional `npc_lines` lines.
- Monster template: `monster_templates`; placement: `monster_spawns`.
- Item: `items`; starter inventory and gil are rows in `char_inventory`.
- Quest: `quests` + `char_quests`.

Behaviour is ordinary Python in `server/fanxi_server/game/content.py`. An NPC script key is matched
in `npc_talk`; a monster kill can advance a quest through `mob_killed`. Keep content original:
do not paste retail dialogue, event scripts or another server's data. See
[landsandboat-study.md](landsandboat-study.md) for the clean-room boundary.

Packet and entity layout notes are in `game/packets.py` and `game/entities.py`; the protocol
reference is [protocol.md](protocol.md) and the world design is [world.md](world.md).

## Conventions

- **Standard library only** on the Python side. If a dependency is unavoidable, make it optional
  and document the fallback. The launcher and server must run from a fresh checkout with nothing
  installed.
- **No secrets in the tree.** Passwords are hashed, tokens are stored hashed, certificates are
  generated into `data/tls/` (git-ignored), admin keys come from the environment.
- **Brand new things say Fanxi.** New UI strings, paths, environment variables and bundle IDs use
  the Fanxi names in [identity.md](identity.md). Do not add references to the upstream project.
- **The database is the source of truth.** The gateway may cache a session, but a restart must
  not lose accounts, characters or positions.
- **Errors are JSON in the API** (`{"error": {"code", "message"}}`) and plain messages in the
  launcher; never let a traceback reach the player.
- **Timestamps are ISO-8601 UTC.**
- **SQL migrations are append-only.** Add `0002_*.sql`; never edit an applied file.

## Adding an API endpoint

1. Add a method to `FanxiService` that does the work and raises `ApiError` with a stable code.
2. Add a handler to `Api` in `http_api.py`; register it with `route(METHOD, pattern)`.
3. Decide whether the path is public, authenticated or admin. The current router treats
   `/api/v1/health`, `/status`, `/news`, `/releases`, `/auth/register` and `/auth/login` as
   public; `/api/v1/admin/*` as admin; everything else as authenticated.
4. Add a test in `server/tests/test_api.py` (route/status/body) and, for behaviour, in
   `test_service.py`.
5. Add the endpoint to `docs/server.md`.

Example:

```python
@route("GET", r"/api/v1/characters/(?P<character_id>\d+)/position")
def character_position(self, request):
    assert request.account
    character = self.service.character_for_account(request.account["id"],
                                                   int(request.params["character_id"]))
    return json_response(200, {"position": self.service.public_character(character)["position"]})
```

## Changing the schema

```sql
-- database/migrations/0002_add_mounts.sql
ALTER TABLE characters ADD COLUMN mount INTEGER NOT NULL DEFAULT 0;
```

Then update the table in `docs/database.md`, the seed if it needs defaults, and any service code
that selects `*` (SQLite returns the new column automatically; dicts are forgiving). Run
`python3 -m fanxi_server init` on a scratch DB and `python3 -m unittest discover -s server/tests`.

## Launcher changes

The UI is built fresh on every `show_view`; there are no long-lived widget references except
`build_log` (the settings log text). Long work uses `run_bg()`, which queues results back to the
Tk main loop; callbacks run on the main thread. Keep it that way: never touch Tk widgets from a
worker thread.

The launch command is a pure function (`build_launch_command`) so it stays testable without
spawning `host64`. If you add a client argument, add it there and to the test.

## Client build

```bash
# Full macOS app bundle (the original setup path)
python3 tools/setup.py --game ~/Games/FINAL\ FANTASY\ XI --no-install

# host64 only, with the launcher's venv
.venv/bin/python tools/build_posix.py host64 --game ~/Games/FINAL\ FANTASY\ XI

# game-free checks
python3 tools/build_posix.py vfstest
python3 tools/build_posix.py gfxtest     # needs a display/GPU, not game files
```

The recompiler reads `meta/builds.json` to match the player's `FFXiMain.dll` hash, then
`tools/prepare.py` extracts the retail files and `recomp/recomp.py` emits C. `build/`,
`generated/`, `.venv/` and `data/` are git-ignored.

## Running locally

```bash
./scripts/dev.sh                 # server + launcher
./scripts/server.sh --no-game    # API only
./scripts/init.sh                # init + admin
./scripts/db-backup.sh
```

Useful environment for development:

```bash
FANXI_LOG_LEVEL=debug FANXI_ZONE_DEBUG=1 ./scripts/server.sh
FANXI_LAUNCHER_DIR=/tmp/fanxi-test ./launcher/fanxi-launcher
```

## Pull requests

- Run `./scripts/test.sh` before opening one.
- Keep the client and the new services in separate commits when practical (client rebrand vs.
  launcher/server/database).
- Never add game binaries, `compress.dat`, DATs, `generated/`, `build/` or `data/fanxi.db`.
- Update the relevant doc in `docs/` with behaviour changes.

## Release checklist

1. Bump `server/fanxi_server/__init__.py`, `launcher/fanxi_launcher/__init__.py` and
   `launcher/build_app.py` together.
2. Run the full test suite.
3. Build `python3 launcher/build_app.py` and launch it once.
4. Run `python3 -m fanxi_server run` against a fresh database and play a full launch.
5. Publish the launcher artifact and a `releases` row (platform, version, URL, SHA-256).
6. Tag the repository (`v0.2.0` for the world slice); keep `data/` and certificates out of the
   artifact.
