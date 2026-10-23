# Launcher

The Fanxi Launcher is the desktop app in `launcher/`. It is ordinary Python 3.9+ and Tkinter: no
Electron, no Node runtime, no compiled UI dependencies.

> **Rust/Tauri preview.** `launcher-rs/` contains a native rebuild of this app in Rust + Tauri 2.
> It uses the same `launcher.json` and control protocol, and is being brought to parity alongside
> the Python launcher. This document covers the Python app until the Rust one becomes the default;
> see [launcher-rs/README.md](../launcher-rs/README.md) for its own run and build instructions.

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
  "username": "aria",
  "token": "…",
  "token_expires_at": "2026-11-19T…Z",
  "character_id": 1,
  "game_dir": "/Users/aria/Games/FINAL FANTASY XI",
  "host64": "/…/fanxi/build/host64",
  "auto_login": true,
  "last_page": "control",
  "accounts": [
    {
      "username": "aria",
      "token": "…",
      "token_expires_at": "2026-11-19T…Z",
      "character_id": 1,
      "characters": [{"id": 1, "name": "Aria", "main_job": 1, "main_level": 99}]
    },
    {
      "username": "ariamule",
      "token": "…",
      "token_expires_at": "2026-11-19T…Z",
      "character_id": 4,
      "characters": [{"id": 4, "name": "Mule", "main_job": 3, "main_level": 99}]
    }
  ]
}
```

The **password is never stored**. Each account keeps only its API token; the active account's
token is also mirrored in the top-level `token` field for older launchers. Signing out revokes that
account's token on the server and removes it locally; other saved accounts stay. If a token expires
or is revoked, use **Accounts → Sign in again**.

`FANXI_LAUNCHER_DIR` overrides the folder (useful for testing).

## Pages

| Page | What it does |
|---|---|
| **Sign in / Create account** | Server URL, username, password; registration creates a player account. The server URL is saved locally. |
| **Home** | Server status, the active character, Play, Control room, latest news. |
| **Characters** | Every character on the active account. **New mule** creates another; Select chooses the one Play uses. |
| **Accounts** | Every saved account. **Add account** signs in a second account for multiboxing; Use switches the active one; Remove forgets only the local token. |
| **Control** | The party roster, Launch / Launch all, the live KPI table, Stop, and the command console. |
| **Gear / GearSwap** | Every running client with an **Open Gear & GearSwap** button; job defaults, imports and versioned set libraries. |
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

The launcher starts every client with `FFXI_CONTROL=<port>` (ports `54300`, `54301`, …). That
loads the built-in control addon, which the Control room and Gear window talk to. Each client also
gets its own log: `…/Fanxi/logs/game-<account>.log`; build output goes to
`…/Fanxi/logs/build.log`.

If Play says **host64 is not built**, use Settings → Build game. If it says the game folder is
missing, choose it in Settings or in the file dialog Play opens.

## Multiboxing

FINAL FANTASY XI permits **one online character per account**. To play Onedough and a mule at the
same time, the mule needs its own account:

1. **Accounts → Add account**, sign in as the second account.
2. On **Characters**, create a character on that account if it has none.
3. Open **Control**. Each saved account has a character picker and a **Launch** button.
4. **Launch all** starts one client for every signed-in account, sequentially. Each client gets a
   separate control port and log.

The launcher refuses to start a second client for the same account because the server replaces that
account's game session. Stopping a client sends `/shutdown`, then terminates its process group if
the game does not exit.

A new mule can start from another character's progress instead of levelling and gearing it again:

```bash
tools/clone_character.py --source Onedough --target Twodough --force --dry-run
tools/clone_character.py --source Onedough --target Twodough --force --apply
```

It replaces the target's jobs, level, sub job, exp, gil, merits, Home Points, inventory, storage,
locker and worn outfit with the source's, in one transaction and after a database backup. Log the
target out first; `--force` acknowledges that the server still holds the session row for up to 12
hours after a logout. After the copy, relog it; if the client was already sitting at character
select when the copy ran, relaunch that client or restart the server. A prepared lobby hand-off or
a parked zone-change session keeps its old character dict through the next login, so the first
login can still show level 1 and fail every equip check even though the database row is correct.

## Control room and KPIs

The Control page polls each running client's control port through the built-in `control` addon:
the party rows every three seconds and the follow state every two seconds. Every poll is one
request/response line on a loopback TCP connection to the client; the Fanxi server API is not
polled. Per client it shows:

- account and character;
- current zone, HP/MP;
- EXP/hr (from the player's `ExpCurrent`/`ExpNeeded` fields, sampled over the session);
- rolling 60-second DPS and total damage (from incoming `0x028` action packets);
- whether the client is online, signing in, or has no control port yet.

Double-click a row to open its **Gear** window. The command console sends a line to the selected
client: `!zone 100`, `!merits 5`, `!heal`, `!where`, `!help`, or any other server command. The
control addon executes it as if typed, without the launcher's `/say` fallback.

The same protocol is available to scripts: see `tools/xi_mcp.py` and `host/addons/lua/control.lua`.
It is JSON, one object per line over `127.0.0.1:<port>`.

## Gear and GearSwap

The Gear window reads the active item in every slot from the running client. Open it from
**Gear** in the sidebar, from the **Gear & GearSwap** link in the Control room, by double-clicking a
LIVE PARTY row, or with **Gear / GearSwap** beside the command console. **change** asks for an item
name and sends the client's own `0x050` equip packet if the item is in one of its bags.

On open the window asks the client for its `state`, shows the live **main job and level** in the
header, and loads that job's default library from the checkout's `gearswap/<JOB>.lua` (bundled into
the macOS app; `FANXI_GEARSWAP_DIR` overrides the folder). While the client is still at the
character-select screen there is no live job, so the character's saved main job is used instead and
the header says **saved job**; press **Refresh** after entering the world for the live one.

The window is split into two tabs. **Sets** holds the live gear, the live job and the state groups.
**Manage** holds the GearSwap library browser, the set editor and the saved versions. Its **Job
defaults** dropdown loads any of the 22 bundled job libraries, and **Import .lua** reads a GearSwap
file with the same sandbox as before. The strip at the top names the loaded library and its set
count, marks **Sets** while auto-swap is on, and jumps to **Manage** after an import.

Sets can be managed without leaving the window:

- **New set…** opens a 16-slot form (the path plus main/sub/range/ammo/armour/accessories).
- **Duplicate** copies the selected set into the same form with a new default path.
- **Edit set…** opens the whole set; double-clicking an item edits just that slot.
- **Delete** removes the set from this library.
- **Wear set** sends every `0x050` for the set in one frame (the GearSwap equip burst), and skips
  the pieces already worn. Items must be in the character's bags; the panel reports every item it
  could not find and the measured round trip.

Editing a bundled job library writes the sets back to `gearswap/<JOB>.lua` as soon as they
change, so a new weaponset or an edited idle set survives a logout, a relaunch and a job change.
The first write keeps the previous file as `gearswap/<JOB>.lua.bak`. An imported GearSwap file is
still never modified: an edit there lives in the window until **Save version…** writes a
timestamped copy (includes and event code are not evaluated, so that copy holds only the sets the
launcher showed).

On the Sets tab, the phase engine is split into the groups the player thinks in:

- **Engaged** — the TP set and the default WS set.
- **Kiting** — a forced set with a Start/Stop toggle; it stays on until stopped.
- **Weaponset** — **New set** opens a weapon-only form whose Main/Sub/Ranged/Ammo pickers list
  the actual items in the character's 18 client bags (inventory, Mog Safe, Storage, wardrobes,
  satchel/sack/case; slots 1-80) that the main job can use. The job filter uses the client's
  own 1-based job mask, so a NIN sees Dokoku/Kikoku/Nagi and does not see SAM-only great katanas.
  One copy of a weapon can fill Main *or* Sub; a second copy unlocks the other (dual wield).
  Grips are offered only when Main is a two-handed weapon; off-hand weapons and shields only
  when Main is one-handed or empty, and an incompatible saved Sub is cleared. Ranged and ammo
  are in the same form, with stack counts for ammo. The hidden `!locker` is not a client bag, so
  `!locker grab <name>` first. **Edit** reopens the selected set, **Wear** equips it and
  **Wear & lock** pins its slots. The weapon slot chips pin individual slots; the EquipViewer
  draws a red border on a pinned cell. Pins are session-only, and a main or support job change
  releases them with the gear lock; `/!gs lock main, sub, …` / `/!gs unlock …` work in game.
  Ranged/throw actions are guarded: a Tathlum, orb or other
  stack-1 ammo is never thrown; the addon swaps in a stackable shuriken/stone (or arrows/bolts/
  bullets with a ranged weapon), waits for the equipment echo, then restores the original ammo.
  With no suitable ammo in the bags the throw is blocked and explained in chat.
- **Weaponskills** — a full-width card with a default plus one row per `sets.WS.*` WS, each with
  its own set. The TP set returns when the WS result lands or misses.
- **Job abilities** — a full-width card with a default JA set and one row for every ability the
  client's current main/sub job pair lists. A row's set wins over the library's `sets.JA.<name>`;
  an empty row uses the default JA set, then the library's `precast.JA`. The action is matched by
  its low-nine-bit id, so sambas, waltzes, runes and similar non-`JobAbility` types work too.
- **Resting** — a manual resting set and toggle.
- **Spells** — a precast set, a midcast default for every spell, and per-spell override cards
  picked from the current job's spell list (macc/mab/magic-skill sets included).
- **Idle** — field, town, movement, DT/PDT/MDT/Eva/Meva sets and a manual idle focus.

The phase header shows the live state and set (`Kiting · idle.pdt`), the rule counts and the
launcher-wide **Turn GearSwap off/on** switch. The same switch is in **Settings → GearSwap**. It
is a master stop, not a per-window pause: off sends `phase {enabled: false}` to every running
client, which clears its precast/midcast/idle plan, pending state set and session locks, so the
host stops holding action packets. Manual **Wear set** and the set editor keep working while it is
off, and the choice is remembered for the next launch. It starts off on a fresh profile. The
**Lock** button in the Active gear card is the narrower override: it holds whatever is worn and
suppresses every automatic swap until **Unlock** or **a job change** — the new main or support job
releases the lock and the session pins, so the new job's weapon is worn instead of the old one's.
A job change reloads the job-named default library and re-pushes the plan; the Home dashboard and
Live job card follow the running client's own job and zone. See
[control-panel.md](control-panel.md#precast-midcast-and-idle-states) for the mapping and timing.

**Save version…** asks where to write the file (the OS Downloads folder by default) and saves a
new GearSwap `.lua` named `<character>-<JOB>-YYYYMMDD-HHMMSS.lua`. The name is a timestamped
version: the previous files are never overwritten. A JSON copy is written to
`<data dir>/gearswap/<version>.json` for the Control room's **Saved Gear Versions** list. This is
an export, separate from the in-place save of the bundled job library.

Migration `0066_gearswap_grant.sql` resolves the names in the default libraries to real item ids
and grants the missing ones to the first character's wardrobes; `0089_gearswap_reforged_grant.sql`
grants the 255 library items that were appended after migration 66 had already run, and
`0090_gearswap_full_sets.sql` completes every job's 15-piece reforged AF/relic/empyrean sets.
**Wear set** can find every library item that is in a bag after the client next zones or logs back
in. Items put on a storage slip with `!storage store` need `!storage grab <job|all>` first.

If no job can be read yet (the client has not reached its first frame), the window says so;
**Refresh** retries, or pick a job in Manage's **Job defaults** dropdown.

Limitations:

- an imported GearSwap file is read, never modified; edits are saved to a new version. A bundled
  job library is the launcher's own mock library and is rewritten in place (first copy as
  `.lua.bak`) so the sets survive a relog;
- the reforged set rows were placeholders: migration 92 fills their `item_mods` and skill
  bonuses from the client's stat lines, so the stats are real. Migration 95 fills every visible
  item's grap model (the reforged sets get their original tier's look) and installs triggers that
  stamp the model when a grant or a clone adds gear; `tools/gen_item_models.py` regenerates the
  table and `tools/item_models.py` repairs/reports an existing database;
- `include()`d libraries are not evaluated, so sets defined in an included file are not visible;
- augments are preserved in the imported JSON and **shown read-only**: augmented items get a
  `*` (Odyssey armour and weapons get `R30`) and the selected item's full augment list appears
  below the item pane. `Wear set` still matches the base item name, so it cannot choose between
  two builds of the same JSE cape or Nyame piece; the editor and saved versions flatten the set to
  names and drop the augment arrays. The default libraries use 198 augmented JSE cape builds, the
  five Unity items' fixed augments, and every Odyssey Rank 30 build — Nyame Paths A-D, Sakpata's,
  Gleti's, Agwu's and their weapons. See [odyssey-r30.md](odyssey-r30.md);
- GearSwap's rules/functions (`sets.precast`, `rule`, `aftercast`) run only through the normal
  addon host if you install GearSwap itself; the Gear window is a set viewer/editor/equipper, not a
  full replacement for GearSwap's event engine;
- the editor only reads and writes the flattened set table; functions and rules in a hand-written
  file are not round-tripped.

The repository's addon host already runs Windower/Ashita addons; `tools/addons_fetch.py` installs
the upstream libraries. GearSwap itself can be dropped into `windower/addons/GearSwap` and loaded
like any other addon; the Control room's Gear panel is the native, scriptable view.

## Packaging

### macOS

```bash
python3 launcher/build_app.py
open "build/Fanxi Launcher.app"
```

The bundle is a shell stub plus the Python package, the bundled `gearswap/` default libraries and
an icon; it runs `python3 -m fanxi_launcher` from inside `Contents/Resources/app`. It records the checkout it was built from in
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
| Game starts and immediately exits | Read `~/Library/Application Support/Fanxi/logs/game-<account>.log` (macOS) or `~/.local/share/fanxi/logs/game-<account>.log` (Linux). |
| Control page says "starting" forever | Rebuild `host64` after updating the repository; the control addon is embedded in the client. Check the game log for `control: listening`. |
| `command: the line must start with / or !` | The console only runs commands; to say something use `chat_send` (or start with `/say`). |
| GearSwap import says a set is missing | The file builds that set in an `include()`d library; this pass does not evaluate includes. |
| The `.app` cannot find the game/tools | The checkout used to build it moved. Rebuild with `python3 launcher/build_app.py`, or run `launcher/fanxi-launcher` from the checkout. |

## Tests

```bash
python3 -m unittest discover -s launcher/tests -v
```

The tests cover the settings file and permissions, the HTTP client against a local stand-in
server, game-folder detection, `host64` discovery and the exact launch command. The UI is
constructed in a smoke test during development but is not part of CI.
