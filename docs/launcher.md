# Launcher

The Fanxi Launcher is the desktop app in `launcher/`. It is ordinary Python 3.9+ and Tkinter: no
Electron, no Node runtime, no compiled UI dependencies.

## Run it

From a checkout:

```bash
./launcher/fanxi-launcher
# or
python3 -m fanxi_launcher          # from launcher/
# or
./install.sh                       # builds and installs the .app / desktop entry
```

The launcher's own checks:

```bash
./launcher/fanxi-launcher --check
./launcher/fanxi-launcher --api http://192.0.2.10:8080
./launcher/fanxi-launcher --game ~/Games/FINAL\ FANTASY\ XI
./launcher/fanxi-launcher --sign-out
```

`--check` prints the settings file, data folder, detected game folder, `host64`, the server URL
and the server's health response.

## What it stores

One JSON file, mode `0600`, at:

- macOS: `~/Library/Application Support/Fanxi/launcher.json`
- Linux: `~/.local/share/fanxi/launcher.json` (or `$XDG_DATA_HOME/fanxi/launcher.json`)
- Windows: `%APPDATA%\Fanxi\launcher.json`

```json
{
  "api_url": "http://127.0.0.1:8080",
  "token": "…",
  "token_expires_at": "2026-11-19T…Z",
  "username": "aria",
  "character_id": 1,
  "game_dir": "/Users/aria/Games/FINAL FANTASY XI",
  "host64": "/…/fanxi/build/host64",
  "auto_login": true,
  "last_page": "home"
}
```

The **password is never stored**. The API token is the only credential, and signing out revokes it
on the server and deletes it locally. If the token expires or is revoked, the launcher shows the
sign-in screen again.

`FANXI_LAUNCHER_DIR` overrides the folder (useful for testing).

## Pages

| Page | What it does |
|---|---|
| **Sign in / Create account** | Server URL, username, password; registration creates a player account. The server URL is saved locally. |
| **Home** | Server status, character summary, Play, latest news. |
| **Character** | Create a character (name, race, nation, main job, face, size) or view the one you have. |
| **News** | Posts from `news` in the database. |
| **Settings** | Server URL, game folder, Save, Detect game, Build game, Open data folder, live build log. |

The default server is `http://127.0.0.1:8080`. For a server elsewhere, change it in Settings or
sign-in before you sign in; it is saved in `api_url`. If you terminate HTTPS with a self-signed
certificate, start the launcher with `FANXI_API_INSECURE=1` (it disables certificate checking for
that launcher process only).

## Building the game

The launcher builds the client from **your** FINAL FANTASY XI folder. It does not download game
binaries.

1. Settings → **Game folder** → Browse (the folder with `FFXiMain.dll`, `FFXi.dll` and `ROM`).
2. **Build game**.
3. The launcher:
   - creates `.venv/` in the repository if missing;
   - installs `capstone` and `pefile` into it (needs network once);
   - runs `.venv/bin/python tools/build_posix.py host64 --game <folder>`;
   - streams the phases, compile progress and errors into the build log.

The first build takes several minutes; later builds are incremental. Build requirements:
Python 3.9+, Clang (Xcode Command Line Tools on macOS), CMake/Ninja for the vendored SDL, and your
game files. The build writes `build/host64` (and `build/Fanxi.app` for the full bundle target).

If `host64` already exists, Play uses it. To rebuild after a game update, run Build game again.

## Playing

**Play**:

1. calls `POST /api/v1/launch` with the selected character;
2. receives a one-time `login_token` and the world's host/ports;
3. starts:

```bash
build/host64 --game <folder> --server <host> --user <name> --login-token <token> \
             --authport 54231 --dataport 54230 --viewport 54001
```

4. the game signs in to Fanxi's auth gateway; the launcher stays open and reports the process id.

The game's stdout/stderr goes to `…/Fanxi/logs/game.log`; build output also goes to
`…/Fanxi/logs/build.log`.

If Play says **host64 is not built**, use Settings → Build game. If it says the game folder is
missing, choose it in Settings or in the file dialog Play opens.

## Packaging

### macOS

```bash
python3 launcher/build_app.py
open "build/Fanxi Launcher.app"
```

The bundle is a shell stub plus the Python package and an icon; it runs `python3 -m fanxi_launcher`
from inside `Contents/Resources/app`. It records the checkout it was built from in
`FANXI_REPO_ROOT`, so **keep the checkout** (or rebuild the app after moving it) — the bundle
builds `host64` and finds the game through that checkout. It is ad-hoc code-signed; macOS may ask
for confirmation the first time.

`install.sh` copies it to `~/Applications/Fanxi Launcher.app` (or `/Applications` when writable).

### Linux

```bash
python3 launcher/build_app.py --desktop
```

This writes `build/Fanxi Launcher.desktop`. `install.sh` copies the entry to
`~/.local/share/applications/`, the icon to `~/.local/share/icons/`, and a `fanxi-server` helper
to `~/.local/bin/`. The entry runs `launcher/fanxi-launcher` from the checkout, which must remain
in place.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Window does not open | `python3 -c "import tkinter"` must succeed. macOS: install Command Line Tools. Linux: install `python3-tk`. |
| `cannot reach http://…: is the Fanxi server running?` | Start the server (`scripts/server.sh`) or fix the URL in Settings. |
| Sign-in says the session expired | Sign out and in again; the token may have been revoked by a server restart or admin action. |
| Build fails on `capstone`/`pefile` | The venv needs network access once. Delete `.venv/` and build again, or run `python3 -m pip install 'capstone>=5,<6' 'pefile>=2023'` in it. |
| Build fails on clang/CMake | Install Xcode Command Line Tools (macOS) or `build-essential cmake ninja-build` (Linux). |
| Play fails with auth error | The server's game gateway is off or `FANXI_PUBLIC_HOST` is not reachable. Check `python3 -m fanxi_server doctor` on the server. |
| Game starts and immediately exits | Read `~/Library/Application Support/Fanxi/logs/game.log` (macOS) or `~/.local/share/fanxi/logs/game.log` (Linux). |
| The `.app` cannot find the game/tools | The checkout used to build it moved. Rebuild with `python3 launcher/build_app.py`, or run `launcher/fanxi-launcher` from the checkout. |

## Tests

```bash
python3 -m unittest discover -s launcher/tests -v
```

The tests cover the settings file and permissions, the HTTP client against a local stand-in
server, game-folder detection, `host64` discovery and the exact launch command. The UI is
constructed in a smoke test during development but is not part of CI.
