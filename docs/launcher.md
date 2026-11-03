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
  "monitor": "Monitor #29451",
  "host64": "/…/fanxi/build/fanxi",
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

`monitor` is the display the launcher window and every visible client open on: the id Settings
writes for the chosen display (its OS name, or `width×height@x,y` when the OS has no name for it).
Empty, the default, is the main display. A display that is no longer attached falls back to the
main display.

`FANXI_LAUNCHER_DIR` overrides the folder (useful for testing).

## Pages

| Page | What it does |
|---|---|
| **Sign in / Create account** | Server URL, username, password; registration creates a player account. The server URL is saved locally. |
| **Home** | Server status, the selected tenant character (with its main and support job), Play, Control room, latest news. |
| **Characters** | Every character on the active account, each with its main/support job pair. **New mule** creates another; Select chooses the one Play uses. **Design** opens that character in the tenant context. |
| **Design** | Race, face, hair colour and size for the selected tenant. Applying writes to that character only; a running client repaints immediately. |
| **Accounts** | Every saved account. **Add account** signs in a second account for multiboxing; Use switches the active one; Remove forgets only the local token. |
| **Team** | The main account and its boxes: create, suspend, delete, launch one box or the whole team, and the whole-party **Team jobs** roster of main and support jobs. |
| **Control** | The party roster with each account's job pair, Launch / Launch all, the live KPI table (including a **Job** column) and its **Party jobs** roster, Stop, the command console, and **Invite** to party the whole sub team or one running character. A client whose zone session died shows **orphaned** (the server has no session although the client still answers) or **logged out**, with **Reconcile** / **Relaunch**; **Reconcile N** restarts every stale box, and a relogged or relaunched box is pulled to the leader automatically. |
| **Warps** | Saved `//warp` places for the selected tenant: mark the live position, rename aliases, delete rows, warp just that character or every online box in the account family, and **Warp team to me** to call the team to the live character. Works for main and sub-account characters. Even when the team is already in that zone the server hands each box a short `0x00B` re-zone: the client ignores its own position update, so this is what actually moves it to the leader. |
| **Data** | The assignment page, split into **Overview** (merits, job points, Mastery Rank, gil, Home Points, currencies, key items and mounts), **Merits** (the six general menus and every job's Group 1/2 as editable form groups), **Progression** (mission/fame/Mog Garden ranks, jobs and Master Levels, Exemplar Points, crafts, Trusts with their max-all alter-ego upgrade, augment RP paths over Odyssey, Limbus, Temenos and Unity gear — the five Limbus suits and all sixteen Telopanos weapons included — and Oboro weapon paths), **Augments** (the Ambuscade cape augment editor, Nolan mezzotints, Oseem Arcane Glyptics, Skirmish, Sinister Reign, Moonshade, Magian trials and Shantotto's Ascension gear), **Armory** (gear search and purchase history) and **Items** (ninja tools, jug pets, consumables, ingredients and the rest of the general-item store), applied to the selected tenant. The tab you were last on is remembered. |
| **Gear / GearSwap** | The selected tenant's live gear and GearSwap library, plus job defaults, imports and versioned set libraries. The **Live job** card shows the main and support job pair. The tab and the last set browsed are remembered per account and job. |
| **Battle** | The selected tenant's Battle profile: roster roles, camp/engage, formation, pull/sleep, healing, buffs, enfeebles, dispel, death/kiting/loot rules and saved profiles. Save/Apply live/Start/Stop/Show hub talk to the same in-game `battle` module as `//battle`. |
| **News** | Posts from `news` in the database. |
| **Settings** | Server URL, game folder, headless game folder, remote Linux host, 30 fps main cap, **game window** (display, mode, resolution, interface scale), Save, Detect game, Build game, Open data folder, live build log. |

The **Game window** card in Settings controls where and how every visible client opens:

- **Display**: the main display, or any attached display by number and resolution (two displays
  with the same resolution are told apart by their number). The launcher window opens here too,
  and moves here as soon as the choice is saved. The game's sign-in window and its game window
  open here; the default, **Main display**, is where they have always opened.
- **Window mode**: Windowed, Borderless window, Full screen, or Borderless full screen. The two
  full-screen modes follow the chosen display's own resolution; the windowed modes use the
  resolution below.
- **Resolution**: width × height, or **Fit this display** to use 92% of the chosen display's
  usable area. The quick presets are filtered to sizes that fit that area.
- **Interface scale**: the game's menus are rendered at the window resolution divided by this, so
  they stay legible on a large display. 2× matches the sign-in screen's default.

The launcher writes the chosen values to `display.reg` in its data folder and passes that file to
`host64` with `--reg-final`. The overlay is loaded after the game's saved registry, so it wins for
that launch without the launcher editing the game folder. Changes apply the next time a client
starts; a running client keeps its current window. The display travels as
`FANXI_DISPLAY=x,y,w,h` in the window API's units (screen points on macOS, pixels elsewhere):
`host64` puts its sign-in and game windows in the middle of that display (at its top left for the
full-screen modes) instead of on the main one. A chosen display that is not attached leaves the
game where it has always opened.


The **Merits** tab is the whole merit menu in the client's order: the six general categories
(HP/MP, Attributes, Combat Skills, Magic Skills, Other and Weapon Skills) and every job's
Group 1 and Group 2. Pick General or a job in the left rail; the character's current main job is
selected when the tab opens. Each menu is a form group: one row per merit with a 0-to-cap
stepper, a badge for the menu's total upgrades, and **Clear menu** to empty that menu. Ranks are
kept in a draft until **Apply ranks**, which sends only the rows that changed and refreshes a
running client. The summary shows the cost of the pending layout, the unspent pool, and the
number of changed rows.

**Spend points** is off by default, so **Apply ranks** assigns ranks directly like the other
assignment cards. Tick it to use the game's rule: the net point difference is charged to the
unspent pool and lowering a rank refunds it. Every row is validated against its individual cap,
and every menu against the category cap the client enforces (75/105/152/112/10/15 upgrades for
the six general menus, 10 for each job group). A character assigned before this editor existed
can still be lowered if its old layout is over a cap; the server refuses only a layout that
pushes the menu further over.

The data is in `GET /characters/{id}/data` as `merits.categories` (50 menus, 274 rows).
`POST /characters/{id}/merits` accepts `{"upgrades": {"384": 5}, "spend": false}` alongside the
older `{"top_off": true}` and `{"points": n}` forms.

The **Shantotto's Ascension** card covers the add-on's three leg pieces — Blitzer Poleyn,
Desultor Tassets and Tatsumaki Sitagoromo. Each bag copy shows its current augment text and
offers the add-on's full 33-row table as two dropdowns (the same row cannot be chosen twice).
Applying writes the standard 24-byte augment block the Ambuscade capes use. **Phantom Roll -5**
is the Corsair choice: the client prints it as a five-second recast reduction, and the server
reads `(0x154, 4)` as mod 1076 and subtracts five seconds from the ability. The effect needs the
piece equipped; the card only changes the copy's block. `POST /characters/{id}/ascension` takes
`{container, slot, choices: ["phantom_roll_5"]}` (or `choices: []` to clear), and the refreshed
Data snapshot lists every copy under `ascension.items`.

The **Armory** is a typeahead over migration 111's full equipment catalogue: it starts
suggesting as soon as a name is typed, draws each item's BG Wiki icon, and shows the slot,
level, item level, job count and gil price. Selecting a piece opens a purchase card. Only a
**Rare** piece the character already holds says **Currently owned** and cannot be bought again;
an Ex-only piece can be bought in multiples (Ex stops trading and selling, not holding two), and
any other owned piece can be bought again. The price is charged against the character's wallet
and recorded in the purchase history. Search matches both the client's 15-character item name and
the longer BG Wiki name for the 2,068 abbreviated equipment rows that have one (for example
`Mou. Crackows +1` and `Mousai Crackows +1`); a match is still returned as one item. The
purchase history is paginated at **20 rows by default**; the **Rows per page** picker offers
10, 20, 50 or 100, and the choice is kept for the next visit.

Prime weapons are sold only in their final iLvl 119 III form. A family's four upgraded rows
share one name, so the typeahead collapses them into a single **Final** row and maps the
stage-1 `Prime ...` item to the same row: `Foenaria` and `Prime Scythe` both offer the one
#21837 form. The purchase card says **Prime final** and **Stage 5 of 5**, and the purchase
history carries the same badge. A Prime id that reaches the Armory through another client is
upgraded at purchase, and migration 0164 retargets any earlier-stage copy already in the bags,
storage, locker, equipped set or purchase history. Prime weapons are Rare, so a family is one
item: holding any stage blocks the purchase, and the migration keeps a single copy (the
equipped bag row first, then an existing final, then the highest stage).

REMA weapons work the same way. The typeahead collapses every Relic, Empyrean, Mythic and Aeonic
stage to the family's final iLvl 119 III afterglow row: **Masamune** is one #21956 row instead of
nine, and final rows whose names carry a `119 III` suffix are matched under the base name too
(`Kikoku 119 III` is the one Kikoku row). The purchase card says **REMA final**; an earlier stage
id sent by another client is upgraded at purchase, and a REMA family is Rare, so holding any
stage counts as owning the final. The family table lives in
`server/fanxi_server/game/rema_weapons.py`.

The **Items** tab is the general-item shop beside the Armory. It reads migration 0156's
non-equipment catalogue: **Ninja Tools** (shihei, kaginawa, toolbags), **Jug Pets** (every Call
Beast broth), **Consumables**, **Ingredients**, **Materials**, **Food & Drink**, **Magic
Scrolls**, **Ammunition**, **Crystals**, **Pet Items**, **Automaton Attachments**, **Furnishings**
and **Miscellaneous**. Type a name to search that shelf, or click a category chip to browse it;
**All items** shows the first 80 alphabetically. Search ignores apostrophes, so `nobles bed` and
`noble's bed` both find **Noble's Bed**. Selecting a row shows the BG Wiki icon, unit price, stack
size and how many the character already holds in bags, storage or the locker. **Buy 1** purchases
a single unit; **Buy stack** purchases the item's full stack size (shihei is 99, a jug is 12),
charging the unit price times the quantity. A **Rare** item the character already holds cannot be
bought again, and a Rare item is always one copy at a time. Purchases are recorded in the same
history the Armory shows.

The **Ambuscade capes** card edits the same five-slot augment block the `//cape` command
writes. Pick any of the 22 job capes (or **Get this cape** to add an unaugmented copy to
the inventory), then choose one row in each BG Wiki material panel — Thread, Dust, Dye,
Sap and Resin — and a stage from 1 to the row's cap (20/20/10/10/5 items, the same counts
as a fully augmented retail cape). **Finish augment** writes the block and sends
`//reload` to a live client; **Max selected** sets each chosen row to its cap, and **Clear
augments** writes the empty block. A material left untouched keeps the word already on
that copy, so the pet-focused preset builds are not truncated by a partial edit. The
catalogue and caps live in `server/fanxi_server/game/capes.py`; [docs/capes.md](capes.md)
lists the 198 preset builds.

The **Nolan · Escha mezzotint** card covers the 183 Escha - Zi'Tah, Escha -
Ru'Aun and abjuration pieces from BG Wiki's Nolan page. Pick an owned piece and
a copy, then **Apply path** for A-D: the card shows each path's three Rank 15
rows and writes the matching mezzotint block in one step (retail would climb
the fifteen ranks with Eschalixirs). Paths A/B/C repeat across an armor set and
path D differs per piece; switching paths overwrites the block.
[docs/nolan-mezzotint.md](nolan-mezzotint.md) has the layout.

The **Oseem · Arcane Glyptics** card covers the five Reisenjima armor sets and
the fourteen Reisenjima weapons. Choose a piece, a path (Melee, Ranged, Magic,
Familiar, Healing, Pet) and a copy, then set each of the five slots: the stat
select offers every row of that path's wiki table and the value box starts at
its maximum. **Max all** restores the caps and **Apply augments** writes the
standard block; **Clear augments** empties it. Values above 32 use the client's
offset-33 ids, and Magic Atk. Bns. above 32 shares the combined Mag. Acc. line.
[docs/oseem-glyptics.md](oseem-glyptics.md) has the details.

The **Divainy-Gamainy · Skirmish** card covers all 138 Skirmish items from the
four BG Wiki categories: the 16 Alluvion weapons, the 25 Alluvion armor pieces,
the 45 old Skirmish weapons (15 families in NQ/+1/+2) and the 52 old Skirmish
armor pieces (five sets in NQ/+1 plus both Beatific Shields). Alluvion gear takes
a Snow, Leaf and Dusk stone; old weapons roll DMG plus two bonus pools; old
armor rolls Physical Damage Taken plus one or two bonus rows. Every row starts at
its strongest value, **Max all** restores them, and **Apply augments** writes the
same standard block the capes use. [docs/skirmish.md](skirmish.md) has the layout.

The **Sinister Reign** card covers the 37 drops from the Sinister Reign wave
bosses (Arciela, Darrcuiln, Ingrid, Teodor, Morimar, Rosulatia, Sajj'aka and
August), grouped by slot. Pick an owned copy and **Give max augments** writes
every row the wiki lists at its maximum in one standard block; **Clear augments**
empties it. Samnuha Tights, the worked example, becomes STR+10 DEX+10
`"Dbl.Atk."+3%` and `"Triple Atk."+3%` from FFXIclopedia's STR+1~10 / DEX+1~10 /
DA+1~3% / TA+1~3% ranges.
[docs/sinister-reign.md](sinister-reign.md) has the catalogue and the id table.

The **Moonshade Earring** card writes the Wings of the Goddess reward's two
augments: pick one row from Set 1 (Accuracy, HP, Magic Accuracy, ...) and one
from Set 2 ("Regain", TP Bonus, "Counter", ...) and **Apply augments** writes
both words into the earring's standard block; **Clear augments** empties it. The
card finds copies in the wardrobe and storage too. The ids and values are the
ones the mission itself uses, so the client tooltip matches retail.
[docs/moonshade.md](moonshade.md) lists all 16 choices.

The **Magian Moogle** card lists the Trial of the Magians catalogue with each
item's immediate trials. A trial card shows its number, the reward it produces
and the augment rows; **Complete trial** replaces the copy with the reward and
writes the Magian block (four augment words plus the trial id). The i119 augment
weapons (Centovente and the other finals) keep their item and take the chosen
block. Filter by name, Weapons/Armor and **Owned only**; copies in the wardrobe
and storage work too. [docs/magian.md](magian.md) has the data sources and the
current coverage.

## Tenants

The bar above the page area names the **tenant** the character pages are looking at. A tenant is one
character: any character on the main account, or the single character of a sub-account box. The bar
is visible on every page, and switching it changes **Home**, **Design**, **Data**, **Gear /
GearSwap** and **Warps** together without changing the signed-in account. The bar also shows the
tenant's main and support job (for example `WAR 99 / NIN 49`), taken from the running client when
it is in game and from the saved character otherwise. The choice is stored as
`tenant_character_id` in `launcher.json` (separate from `character_id`, which is the main account's
Play character), so it survives page changes and restarts. A tenant that is not running still has
Design, Data and Warps; Gear shows its live client only while it is up. Create and launch boxes from
the **Team** page: each box card has **Launch client** for a visible window and **Launch headless**
for a windowless client, and **Launch all clients** starts the main account plus every active box.
Headless boxes are persistent: **Sleep** parks the character (hidden, no actions) without stopping
the process or tunnel, and **Wake** / **Launch headless** resumes it in place. The sleeping flag is
saved in the box registry.

### Team jobs

The **Team** page has a **Team jobs** card under the main-account card, and the Control room has
the same roster as **Party jobs** under its party list. Both list one row per team slot — the main
account and every box — with the character name, `@account` and slot label, the main job and
level, the support job and level, and its live state (`In game`, `Sleeping`, `Logged out`,
`Offline`, `Suspended` or `No character`). Rows for the current tenant are highlighted. The strip
at the top of the card names every distinct job the team covers, with a `×2` badge when two
members bring the same job.

The roster is built from the same data every other page uses: a running client's control state
wins (so a `//job` change in the Mog House or at a Nomad Moogle shows up on the next poll), and an
offline box falls back to its saved character row. A missing support job renders as `No support
job` instead of a fake pair. The Team card is a whole-party view independent of which box is
currently selected in the tenant bar; a box card's **View** button still changes the tenant.

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
warp when the client stops reporting a character block **and the server roster says the character
is offline** (a normal zone change does not count) and, once that account has been
`login_status == 2` for two polls, sends `//warp call <name>` from the leader's client. Only that
box moves, so a team that is already in place is not snapped around. The same box is never pulled
twice inside 90 seconds: a second hand-off while it is still loading moves its zone key under it,
which is what used to leave a box on "Downloading". A warp that arrives on the server while a
zone-in is in flight is likewise deferred until that zone-in is acknowledged (see
[protocol](protocol.md)).

A server restart or a batch relaunch arms the whole team at once. The launcher does **not** pull
each armed box in that case: five `//warp call` commands inside one second used to send five
separate zone changes and lose one mid-hand-off. With more than one box armed the arms are
dropped; use **Warp team to me** (or `//warp all me`), which zones every box in the same tick.
Measured live: five boxes from command to all-in-world in 8.3 s (the first at 4.2 s), against
~19 s with the old three-second hand-out. The remaining time is each client loading its own zone
assets; the server no longer serializes the hand-offs.

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
   - runs `tools/prepare.py --game <folder>` when `generated/build.json` is missing or names
     another folder, so a fresh checkout builds without a manual prepare;
   - runs `.venv/bin/python tools/build_posix.py host64 --game <folder>` on macOS and Linux, or
     `.venv\Scripts\python.exe tools/build.py host64` on Windows;
   - streams the phases, compile progress and errors into the build log.

The first build takes several minutes; later builds are incremental. Build requirements:

| | macOS | Linux | Windows |
| --- | --- | --- | --- |
| Compiler | Xcode Command Line Tools (clang) | `build-essential`, CMake, Ninja | llvm-mingw (what [`tools/build_mingw.py`](../tools/build_mingw.py) drives; the player kit will carry it), or Visual Studio Build Tools with the C++ workload for [`tools/build.py`](../tools/build.py) |
| Python | 3.9+ | 3.9+ | 3.9+ on `PATH` as `python` (the player kit ships its own) |
| SDL3 | built from `third_party/` | built from `third_party/` | the SDL3 development package — the kit carries it; otherwise `SDL3_DIR` or `%APPDATA%\Fanxi\tools\SDL3` |

The build writes `build/fanxi` (`build\Fanxi.exe` on Windows), with `SDL3.dll` copied beside it.
On Windows the Build button checks for a compiler and SDL3 first and names whichever is missing
instead of failing inside the compiler. The player kit — the toolchain, SDL3 and Python in one
download — is described in [Onboarding](onboarding.md).

If `host64` already exists, Play uses it. To rebuild after a game update, run Build game again.

## Playing

**Play**:

1. calls `POST /api/v1/launch` with the selected character;
2. receives a one-time `login_token` and the world's host/ports;
3. starts:

```bash
build/fanxi --game <folder> --server <host> --user <name> --login-token <token> \
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

The admin dashboard's **Clone character** action (`m` in `tools/fanxi_tui.py`) does the same over
SSH: it asks for the source (Onedough is the default), searches the database by part of the target's
name and lets you pick from the matches, then runs `clone_character.py --force --apply` after a
confirmation.

If only the **items** should match — keeping each mule's jobs, gil, merits and progression — use
the inventory-only tool:

```bash
tools/sync_inventory.py --source Onedough \
    --targets Twodough,Threedough,Fourdough,Fivedough,Sixdough
tools/sync_inventory.py --source Onedough --targets Twodough --apply
```

It copies the source's bags and wardrobes (`char_inventory`), storage slips (`char_storage`) and
locker (`char_locker`) in one transaction after a database backup. Each target keeps its own gil
(the gil row is rebuilt from `characters.gil`), and its worn outfit is cleared because the old
`char_equip` container/slot values do not point into the new inventory; the appearance model
columns are cleared with it. Log the targets out first, and relog them afterwards. A target that
was already in a zone when the copy ran still has the old item slots in its client and can write
those stale slots back, so relog it before using or equipping anything.

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

On open the window asks the client for its `state`, shows the live **main and support job** pair
(with both levels) in the **Live job** header, and loads **this account's saved library** for the
main job from the game database. A new account is seeded on its first read: every job's copy comes
from the template account (`FANXI_GEARSWAP_TEMPLATE_ACCOUNT`, Onedough by default), or from the
server's `gearswap/<JOB>.lua` (`FANXI_GEARSWAP_DIR` on the server; the launcher's bundled copy is
only the fallback when that server route is unavailable) when the template account has no saved
row yet. That is how a new account starts from Onedough's current set without sharing a file with
anyone. While the client is still at the character-select screen there is no live job, so the
character's saved main and support jobs are used instead and
the header says **saved job**; press **Refresh** after entering the world for the live one. The
launcher reads the saved Lua itself and sends its text to the client, so the same window works for a
box on another machine (see [headless-multibox.md](headless-multibox.md)): that host never needs a
copy of the checkout's `gearswap/` folder.

The window is split into two tabs. **Sets** holds the live gear, the live job and the state groups.
**Manage** holds the GearSwap library browser, the set editor and the saved versions. The tab last
used is remembered, and the set last opened in an account's job library reopens when you come back
from another page; if an import or **Restore template** replaces that library the page falls back
to its first set. Its **Job libraries** dropdown loads the account's saved library for any of the
22 jobs, **Import .lua** reads a GearSwap file with the same sandbox as before and saves it to the
account for the current job, and **Restore template** replaces that job's copy with a fresh one
from the template account.
The strip at the top names the loaded library and its set count, marks **Sets** while auto-swap is
on, and jumps to **Manage** after an import.

Sets can be managed without leaving the window:

- **New set…** opens a 16-slot form (the path plus main/sub/range/ammo/armour/accessories).
- **Duplicate** copies the selected set into the same form with a new default path.
- **Edit set…** opens the whole set; double-clicking an item edits just that slot.
- **Delete** removes the set from this library.
- **Wear set** sends every `0x050` for the set in one frame (the GearSwap equip burst), and skips
  the pieces already worn. Items must be in the character's bags; the panel reports every item it
  could not find and the measured round trip.
- **Worn gear is changed in Manage.** The Manage tab's **Worn now** grid is the one place a live
  slot is a picker: clicking a cell opens every copy in the character's bags that fits that slot
  and the live main/support job pair (both levels are checked). The list shows the bag, iLv/Lv,
  stack count and augment rows, searches by item name or augment, marks the copy currently
  **worn**, and equips the row you click immediately.
- **The Sets tab is for looking.** Its live grid, the legend rows under it and the selected set's
  preview are read-only, so a stray click while reading a set cannot re-equip the character or
  rewrite the library. Editing a piece happens in Manage's set editor (its item rows are the same
  bag picker); **Wear set** stays an explicit button on the Sets tab.
- **Every EquipViewer slot has the game's item card on hover.** Hovering a cell in any grid — the
  Sets tab, Manage's set editor, the Home page and the Control page — draws the card the game
  puts over an item: the client tooltip verbatim, `Set:`/`Unity Ranking:` blocks included, then
  the copy's augment rows (from the GearSwap set, or the equipped bag row), `iLv`, `Lv.` and the
  jobs that can wear it. It is a hover card only: it never blocks the pointer and nothing in it
  is clickable.

The selected set's preview is more than icons. Hovering a slot draws the full card above; the
inline list under the preview also keeps the item's own tooltip (the base stats the client draws)
next to the augment lines stored on that slot in the GearSwap file. Under the EquipViewer, **Set
totals** adds every numeric stat from both sources, keeping flat values and percentages apart, so
changing a cape, ring or earring and reading the same column is a quick best-in-slot check. Known
hard caps are marked on the total: blue means the set is at or past the cap (Fast Cast at 93
reads `13 excess`), and gold reads `2 needed` while it is short (equipment Haste at 23). The
capped stats are Fast Cast, equipment Haste, Quick Magic, Skillchain Bonus, Cure potency and
Cure potency II, capped Magic Burst damage, the Damage Taken family, Spell interruption rate,
Snapshot, Subtle Blow and Subtle Blow II, Conserve MP, and Casting time; an uncapped stat stays
plain. Tiered bonuses from the modern +1 armor sets are counted too: the preview shows a green
`Kaykaus Attire Set +1 (4 pieces): Cure potency II 8%` line and adds the reached tier to the
totals.  The server reads the same shared table, so the live sheet and the set preview agree.
The descriptions are read from the running client's item resources
through the control port's `lua` command; an item the client cannot resolve still shows its
augment lines and their totals. A name the server spells differently — the Reforged Bonanza
weapons' `(Reforged)` suffix, or a final weapon's `119 III` stage — is resolved through
`control.lua`'s alias table first, so its icon and the final copy's tooltip load instead of
disappearing. The library's spelling stays on the card — `119 III` and `(Reforged)` are the
stage labels, not noise — while the alias is only the lookup key for the image and tooltip.
Conditional `Set:` and `Unity Ranking:`
blocks and the pet/avatar/automaton lines are left out of the totals because they do not describe
the player's own piece — the hover card still prints them, the way the game's tooltip does.
`Aftermath:`, `Latent effect:` and `Additional effect:` lines stay on the card but are not added
to the totals.

The **Sets** tab shows the server's own sheet for the gear the client is actually wearing. **Live
set stats** under the EquipViewer is deliberately compact: one **Stat** and its **Total**, using the
same two-column layout as the old totals but with no Base/Aug/Slots columns. The numbers are built
by the game server from the live zone session, so they include gear and augments, food, job traits
(JT), job abilities (JA), job points, buffs and merits. They are the same values `combat_mods()` and
`stat_sheet()` give the attack, magic and defence paths — the launcher is not re-totalling tooltips.
Attack, Accuracy, Defense, Evasion, HP/MP, the attributes and the combat modifiers are all there;
the card pools the less common modifiers into **Other modifiers** in the full sheet.

Clicking a stat (or **All sources**) opens a full-window sheet. Its left rail lists every stat; the
right panel shows the selected total and every source that produced it: **Base & skill**, each
equipped item, **Food**, **Job traits (JT)**, **Job abilities (JA)**, **Job points & gifts**,
**Buffs** and **Merits**. Each source has its own contribution and the individual items, traits,
abilities or buffs underneath it, and the rows add up to the exact total. Food and Attack/Defense
percentages and fractional STR/DEX rounding are shown as their own lines rather than being folded
silently into the base. The panel follows the server while it stays open.

The sheet comes from `GET /characters/<id>/stats`, a read-only endpoint on the server. Buffs, food
and the ability layer live only in the game process, which is why this is not computed in the
launcher. The character has to be in a zone and the **server must be running the new code**; until
then the card says it is waiting for the live sheet. The refresh button re-reads the report. The
Manage tab's **Set totals** remain the client-tooltip/augment view for a GearSwap set; they are a
set preview, not the live character sheet.  They normally agree once the set is worn, because the
server reads `item_mods` instead of the tooltip.  A live total lower than the tooltip total usually
means the server's item table has no row for that piece (some client-only gear is absent from the
LandSandBoat dump); the live sheet is the authoritative one, and the fix belongs in a migration.

Editing any library saves the sets back to the account's row for that job as soon as they change,
so a new weaponset or an edited idle set survives a logout, a relaunch and a job change. The
checkout's `gearswap/<JOB>.lua` files are only templates now and are never written by the Gear
page, so a change on one account cannot affect another. An imported GearSwap file is stored as the
account's library for the current job; later edits are saved over it. The editor round-trips the
flattened set table only (includes and event code are not evaluated), so a file with custom
functions is preserved on import until the first edit and **Save version…** remains the way to keep
a timestamped export outside the account row.

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
  draws a red border on a pinned cell. A pinned weapon is the hand the engine must keep: a
  weaponskill keeps it (only the WS armour set goes on), the lock re-arms when the weapon is
  drawn, and a cast while disengaged or a Bard's Nitro song may take the hand only for that
  action's window before the lock puts it back. Pins are session-only, and a main or support job
  change releases them with the gear lock; `//gs lock main, sub, …` / `//gs unlock …` work in game.
  Ranged/throw actions are guarded: a Tathlum, orb or other
  stack-1 ammo is never thrown; the addon swaps in a stackable shuriken/stone (or arrows/bolts/
  bullets with a ranged weapon), waits for the equipment echo, then restores the original ammo.
  With no suitable ammo in the bags the throw is blocked and explained in chat.
- **Weaponskills** — a full-width card with a default plus one group per WS action. A library set
  named `sets.WS.<name> (Buff, Buff)` appears as a conditional row under that action, with its own
  set picker; the host wears it only while every listed buff is up and falls back to the plain set
  otherwise. The TP set returns when the WS result lands or misses.
- **Job abilities** — a full-width card with a default JA set and one row for every ability the
  client's current main/sub job pair lists. A row's set wins over the library's `sets.JA.<name>`;
  an empty row uses the default JA set, then the library's `precast.JA`. The action is matched by
  its low-nine-bit id, so sambas, waltzes, runes and similar non-`JobAbility` types work too.
- **Resting** — a manual resting set and toggle.
- **Spells** — a precast set, a midcast default for every spell, category override cards, and
  per-spell override cards picked from the current job's spell list (macc/mab/magic-skill sets
  included). A category card gives one set to every spell in its host-classified group — enfeebles
  macc or duration (Enfeebling Magic), buff potency or duration (Enhancing Magic), enspell damage
  (Enfire/Enblizzard/Enaero/Enstone/Enthunder/Enwater and their IIs), curing potency or cast,
  nuking magic attack or magic damage and helix magic — and a per-spell card still wins over its
  category. The Nuking card's third, automatic **Magic Burst** row is worn for Elemental Magic while a
  Magic Burst window is open on the target and falls back to the armed mode otherwise; the row
  lights an `open` badge while the client reports the window, and the same flag is
  `phase_status().burst`.
- **Idle** — field, town, movement, DT/PDT/MDT/Eva/Meva sets and a manual idle focus.

Phase settings are stored in the game database, not only in the WebView's localStorage. The
`gearswap_settings` row is keyed by account; the launcher hydrates the localStorage cache from it
during bootstrap, writes the account row back after a short debounce, and folds in-game `//modes`
changes through `phase_status`. An existing localStorage config is migrated to the DB on the first
signed-in bootstrap. The Lua itself lives in `gearswap_libraries`, one row per account and job, so
it is separate from the shared templates and from every other account's copy.

The phase header shows the live state and set (`Kiting · idle.pdt`), the rule counts and the
launcher-wide **Turn GearSwap off/on** switch. The same switch is in **Settings → GearSwap**. It
is a master stop, not a per-window pause: off sends `phase {enabled: false}` to every running
client, which clears its precast/midcast/idle plan, pending state set and session locks, so the
host stops holding action packets. Manual **Wear set** and the set editor keep working while it is
off, and the choice is remembered for the next launch. It starts off on a fresh profile. The
**Lock** button in the Active gear card is the narrower override: it holds whatever is worn and
suppresses every automatic swap until **Unlock** or **a job change** — the new main or support job
releases the lock and the session pins, so the new job's weapon is worn instead of the old one's.
Its action windows may still wear their own armour, and the four weapon slots stay as locked
except for the two sanctioned swaps (a cast while disengaged, a Bard's Nitro song), which are
restored when the action resolves. A job change reloads the account's saved library for the new job
(each account has one copy per job) and re-pushes the plan, from the gear page or the launcher's
own poll, so a box on another machine gets the new job's sets too; the Home dashboard and Live job
card follow the running client's own job and zone. The launcher fetches the library for the live
job from the server and sends its Lua text with the plan, so the phase engine follows the same
per-account copy the Gear page edits. See
[control-panel.md](control-panel.md#precast-midcast-and-idle-states) for the mapping and timing.

**Save version…** asks where to write the file (the OS Downloads folder by default) and saves a
new GearSwap `.lua` named `<character>-<JOB>-YYYYMMDD-HHMMSS.lua`. The name is a timestamped
version: the previous files are never overwritten. A JSON copy is written to
`<data dir>/gearswap/<version>.json` for the Control room's **Saved Gear Versions** list. This is
an export, separate from the account row that already holds the current sets.

Migration `0066_gearswap_grant.sql` resolves the names in the default libraries to real item ids
and grants the missing ones to the first character's wardrobes; `0089_gearswap_reforged_grant.sql`
grants the 255 library items that were appended after migration 66 had already run, and
`0090_gearswap_full_sets.sql` completes every job's 15-piece reforged AF/relic/empyrean sets.
`0118_sch_regen_gear.sql` adds the Scholar Regen pieces and their augment lines to Onedough's
inventory.
**Wear set** can find every library item that is in a bag after the client next zones or logs back
in. Items put into storage with `//storage store` need `//storage grab <job|all>` (or
`//storage organize`) first.

If no job can be read yet (the client has not reached its first frame), the window says so;
**Refresh** retries, or pick a job in Manage's **Job libraries** dropdown.

Limitations:

- an imported GearSwap file is stored as the account's library for the current job; the first edit
  re-renders it from the flattened set table, so custom functions and comments from the original
  file are not round-tripped. The shared `gearswap/<JOB>.lua` templates are never modified by the
  Gear page, so no character can change another account's library;
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
| Build fails on `vswhere`/`cl`/`link` | Install Visual Studio Build Tools with the **Desktop development with C++** workload (Windows), then build again. |
| Build fails on SDL3 | Unpack the SDL3 VC development package into `%APPDATA%\Fanxi\tools\SDL3` so it holds `include\SDL3\SDL.h` and `lib\x64\SDL3.lib`, or set `SDL3_DIR`. |
| Game starts and immediately exits | Read `~/Library/Application Support/Fanxi/logs/game-<account>.log` (macOS), `~/.local/share/fanxi/logs/game-<account>.log` (Linux) or `%APPDATA%\Fanxi\logs\game-<account>.log` (Windows). |
| Play fails with auth error | The server's game gateway is off or `FANXI_PUBLIC_HOST` is not reachable. Check `python3 -m fanxi_server doctor` on the server. |
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
