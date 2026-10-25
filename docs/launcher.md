# Launcher

The Fanxi Launcher is the native desktop app in `launcher-rs/`: Rust and Tauri 2 behind a React
front end. It keeps its settings in the same `launcher.json` the earlier Python/Tkinter app used —
that app has been removed — so an existing install keeps its accounts, characters, game folder and
tenants.

The Rust core owns everything that touches the machine: saved tokens, the game build, `host64`
processes and their control ports. The React app is the view; it calls typed Tauri commands and
never sees a stored token. See [launcher-rs/README.md](../launcher-rs/README.md) for the module
layout.

## Run it

From a checkout:

```bash
cd launcher-rs
npm ci
npm run tauri dev
```

`./scripts/launcher.sh` does that (or starts the last release build), `make launcher` is the short
form, and `./install.sh` builds and installs the `.app` / desktop entry for this OS.

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
  "tenant_character_id": 1,
  "game_dir": "/Users/aria/Games/FINAL FANTASY XI",
  "game_display": {
    "mode": "windowed",
    "width": 1280,
    "height": 720,
    "ui_scale": 2.0
  },
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
| **Home** | Server status, the selected tenant character, Play, Control room, latest news. |
| **Characters** | Every character on the active account. **New mule** creates another; Select chooses the one Play uses. **Design** opens that character in the tenant context. |
| **Design** | Race, face, hair colour and size for the selected tenant. Applying writes to that character only; a running client repaints immediately. |
| **Accounts** | Every saved account. **Add account** signs in a second account for multiboxing; Use switches the active one; Remove forgets only the local token. |
| **Control** | The party roster, Launch / Launch all, the live KPI table, Stop, the command console, and **Invite** to party the whole sub team or one running character. A client whose zone session died shows **orphaned** (the server has no session although the client still answers) or **logged out**, with **Reconcile** / **Relaunch**; **Reconcile N** restarts every stale box, and a relogged or relaunched box is pulled to the leader automatically. |
| **Warps** | Saved `//warp` places for the selected tenant: mark the live position, rename aliases, delete rows, warp just that character or every online box in the account family, and **Warp team to me** to call the team to the live character. Works for main and sub-account characters. Even when the team is already in that zone the server hands each box a short `0x00B` re-zone: the client ignores its own position update, so this is what actually moves it to the leader. |
| **Data** | The assignment page: merits, job points, Mastery Rank, gil, Home Points, currencies, key items, the Armory, mission/fame/Mog Garden ranks, jobs and Master Levels, Exemplar Points, crafts, Trusts, augment RP paths and Oboro weapon paths, applied to the selected tenant. |
| **Gear / GearSwap** | The selected tenant's live gear and GearSwap library, plus job defaults, imports and versioned set libraries. |
| **News** | Posts from `news` in the database. |
| **Settings** | Server URL, game folder, headless game folder, remote Linux host, 30 fps main cap, **game window** (mode, resolution, interface scale), Save, Detect game, Build game, Open data folder, live build log. |

The **Game window** card in Settings controls how every visible client opens:

- **Window mode**: Windowed, Borderless window, Full screen, or Borderless full screen. The two
  full-screen modes follow the primary display's own resolution; the windowed modes use the
  resolution below.
- **Resolution**: width × height, or **Fit this display** to use 92% of the primary display's
  usable area. The quick presets are filtered to sizes that fit that area.
- **Interface scale**: the game's menus are rendered at the window resolution divided by this, so
  they stay legible on a large display. 2× matches the sign-in screen's default.

The launcher writes the chosen values to `display.reg` in its data folder and passes that file to
`host64` with `--reg-final`. The overlay is loaded after the game's saved registry, so it wins for
that launch without the launcher editing the game folder. Changes apply the next time a client
starts; a running client keeps its current window.


The **Armory** is a typeahead over migration 111's full equipment catalogue: it starts
suggesting as soon as a name is typed, draws each item's BG Wiki icon, and shows the slot,
level, item level, job count and gil price. Selecting a piece opens a purchase card. A Rare or
Ex piece the character already holds says **Currently owned** and cannot be bought again; any
other owned piece can be bought again. The price is charged against the character's wallet and
recorded in the purchase history.

## Tenants

The bar above the page area names the **tenant** the character pages are looking at. A tenant is one
character: any character on the main account, or the single character of a sub-account box. The bar
is visible on every page, and switching it changes **Home**, **Design**, **Data**, **Gear /
GearSwap** and **Warps** together without changing the signed-in account. The choice is stored as
`tenant_character_id` in `launcher.json` (separate from `character_id`, which is the main account's
Play character), so it survives page changes and restarts. A tenant that is not running still has
Design, Data and Warps; Gear shows its live client only while it is up. Create and launch boxes from
the **Team** page: each box card has **Launch client** for a visible window and **Launch headless**
for a windowless client, and **Launch all clients** starts the main account plus every active box.
Headless boxes are persistent: **Sleep** parks the character (hidden, no actions) without stopping
the process or tunnel, and **Wake** / **Launch headless** resumes it in place. The sleeping flag is
saved in the box registry.

When **Remote Linux host (SSH)** is set, **Launch headless team** starts the main on this Mac and
restarts only the boxes on that host that are not already in game, through
`scripts/linux_boxes.py`; healthy boxes are left alone. If a remote operation is stuck and a box
reports **a remote box operation is already running**, use that box's **Force relaunch**: it
stops the stuck helper and that account's session (even if it still answers in game), clears its
registry row/tunnel, and starts a fresh client with a new token. Before any headless launch the launcher
runs a conservative reaper: tracked clients, visible clients, anything in game
(`login_status == 2`) and processes younger than two minutes are kept, while old untracked
headless clients and dead tunnels are removed. A box
that is already in game is attached instead of restarted. **Launch headless** uses the same remote
path for one box; with the setting empty it stops any stale local/remote process, starts locally,
and waits until the character reaches a zone before reporting success. A timeout stops it and names
the log. Boxes that need an older install can use the separate **Headless game folder** in Settings.
Characters on a different saved account are not tenants here: use **Accounts → Use**
to make that account the main one first.

The default server is `http://127.0.0.1:8080`. For a server elsewhere, change it in Settings or
sign-in before you sign in; it is saved in `api_url`. If you terminate HTTPS with a self-signed
certificate, start the launcher with `FANXI_API_INSECURE=1` (it disables certificate checking for
that launcher process only).

**Warps** reads and edits the same `char_warps` rows as the in-game command. The tenant bar's
selection is the character it manages (switching the tenant changes Home, Data, Gear and Warps
together); it can be a mule on a sub-account because the main account's token is allowed to manage
its whole family. The row's **Warp** button sends `//warp me <slot>` (or `//warp all <slot>` when
**Everyone** is selected) to the selected character's running client. **Warp team to me** sends
`//warp all me` from that client, which calls every other online box in the account family to the
character's current zone and position. The Control room's **Live party** header has the same
button, using the highlighted row. **Mark** reads the client's current `state` first, so a spot
saved from the page is the position the client is actually standing on, not a polling snapshot. The
**Control room** button makes the round trip easy when a client is offline.

A box that comes back from a relog is pulled to its leader without a button: the launcher arms the
warp when the client stops reporting a character block (or when **Relaunch** is pressed) and, once
that account has been `login_status == 2` for two polls, sends `//warp call <name>` from the
leader's client. Only that box moves, so a team that is already in place is not snapped around.

**Invite** in the Control room's **Live party** header opens a picker for the highlighted client:
**Invite all online subs** runs `//invite subs` on the server (the boxes need not be near the
inviter), while the list of running characters offers one **Invite** per member. The server
auto-accepts the family subs and still sends the normal prompt to anyone else.

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
             --authport 54231 --dataport 54230 --viewport 54001 \
             --reg-final <launcher data dir>/display.reg
```

The last argument is the **Game window** overlay from Settings; without it `host64` would read
whatever display settings the game saved last.

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
account's game session. **Stop** on a headless or remote box parks it with `//sleep` and keeps the
process, tunnel and session; **Force relaunch** is the path that actually kills and replaces it.
A visible local client still stops with `/shutdown`, then its process group is terminated.

A new mule can start from another character's progress instead of levelling and gearing it again:

```bash
tools/clone_character.py --source Onedough --target Twodough --force
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
client: `//zone 100`, `//warp list`, `//merits 5`, `//heal`, `//where`, `//help`, or any other server
command. The control addon executes it as if typed, without the launcher's `/say` fallback. In the
game's chat line, **Tab** completes `//` commands when the prefix is unique and leaves an ambiguous
one alone until another letter is typed; the **Warps** page is the point-and-click equivalent for
saved places.

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
  are in the same form, with stack counts for ammo. The hidden `//locker` is not a client bag, so
  `//locker grab <name>` first. **Edit** reopens the selected set, **Wear** equips it and
  **Wear & lock** pins its slots. The weapon slot chips pin individual slots; the EquipViewer
  draws a red border on a pinned cell. Pins are session-only, and a main or support job change
  releases them with the gear lock; `//gs lock main, sub, …` / `//gs unlock …` work in game.
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
- **Spells** — a precast set, a midcast default for every spell, category override cards, and
  per-spell override cards picked from the current job's spell list (macc/mab/magic-skill sets
  included). A category card gives one set to every spell in its host-classified group — enfeebles
  macc or duration (Enfeebling Magic), buff potency or duration (Enhancing Magic) and helix
  magic — and a per-spell card still wins over its category.
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
`0118_sch_regen_gear.sql` adds the Scholar Regen pieces and their augment lines to Onedough's
inventory.
**Wear set** can find every library item that is in a bag after the client next zones or logs back
in. Items put on a storage slip with `//storage store` need `//storage grab <job|all>` first.

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
  `*` (Odyssey and Limbus Rank 30 builds get `R30`) and the selected item's full augment list
  appears below the item pane. `Wear set` still matches the base item name, so it cannot choose
  between two builds of the same JSE cape or Nyame piece; the editor and saved versions flatten
  the set to names and drop the augment arrays. The default libraries use 198 augmented JSE cape
  builds, the five Unity items' fixed augments, every Odyssey Rank 30 build — Nyame Paths A-D,
  Sakpata's, Gleti's, Agwu's and their weapons — and the five Limbus top tiers. See
  [odyssey-r30.md](odyssey-r30.md) and [limbus-r30.md](limbus-r30.md);
- GearSwap's rules/functions (`sets.precast`, `rule`, `aftercast`) run only through the normal
  addon host if you install GearSwap itself; the Gear window is a set viewer/editor/equipper, not a
  full replacement for GearSwap's event engine;
- the editor only reads and writes the flattened set table; functions and rules in a hand-written
  file are not round-tripped.

The repository's addon host already runs Windower/Ashita addons; `tools/addons_fetch.py` installs
the upstream libraries. GearSwap itself can be dropped into `windower/addons/GearSwap` and loaded
like any other addon; the Control room's Gear panel is the native, scriptable view.

## Packaging

```bash
npm run tauri build          # .app/.dmg (macOS), AppImage/deb (Linux), MSI/NSIS (Windows)
```

The macOS app lands in `launcher-rs/src-tauri/target/release/bundle/macos/Fanxi Launcher.app`
(with a `.dmg` beside it); the Linux bundles and the raw binary land under
`launcher-rs/src-tauri/target/release/`. The bundle carries the `gearswap/` default libraries in
its Resources folder. `install.sh` builds with `--bundles app` on macOS and `--no-bundle` on Linux,
then copies the app to `~/Applications` (or `/Applications` when writable) or writes a desktop
entry that runs the release binary from the checkout.

The installer records the checkout in `launcher.json` (`repo_root`), because the app builds
`host64` through `tools/build_posix.py` and reads the game folder through that checkout. If the
checkout moves, set **Fanxi checkout** in Settings to the new path.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Window does not open | The app needs a WebView: current macOS and Windows include one; Linux needs WebKitGTK 4.1. Run `npm run tauri dev` in `launcher-rs/` to see the startup error. |
| `cannot reach http://…: is the Fanxi server running?` | Start the server (`scripts/server.sh`) or fix the URL in Settings. |
| Sign-in says the session expired | Sign out and in again; the token may have been revoked by a server restart or admin action. |
| Build fails on `capstone`/`pefile` | The venv needs network access once. Delete `.venv/` and build again, or run `python3 -m pip install 'capstone>=5,<6' 'pefile>=2023'` in it. |
| Build fails on clang/CMake | Install Xcode Command Line Tools (macOS) or `build-essential cmake ninja-build` (Linux). |
| Play fails with auth error | The server's game gateway is off or `FANXI_PUBLIC_HOST` is not reachable. Check `python3 -m fanxi_server doctor` on the server. |
| Game starts and immediately exits | Read `~/Library/Application Support/Fanxi/logs/game-<account>.log` (macOS) or `~/.local/share/fanxi/logs/game-<account>.log` (Linux). |
| Control page says "starting" forever | Rebuild `host64` after updating the repository; the control addon is embedded in the client. Check the game log for `control: listening`. |
| `command: the line must start with / or !` | The console only runs commands; to say something use `chat_send` (or start with `/say`). |
| GearSwap import says a set is missing | The file builds that set in an `include()`d library; this pass does not evaluate includes. |
| The `.app` cannot find the game/tools | Set **Fanxi checkout** in Settings to this checkout, or re-run `install.sh` (it records the path in `launcher.json`). |

## Tests

```bash
cd launcher-rs
npm run check
cargo test --manifest-path src-tauri/Cargo.toml
```

`npm run check` type-checks the React front end. The Rust tests cover the HTTP client and URL
normalisation, the settings file and permissions, the control-port protocol, checkout and
game-folder detection, the launch command, item icons and GearSwap set handling.
