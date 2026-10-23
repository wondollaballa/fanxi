# Control panel, multibox and mules

The Fanxi Launcher doubles as a control panel for several running clients. It is still plain
Python/Tkinter; the only new moving parts are one extra thread that polls each client and the
in-game control addon that already existed for `tools/xi_mcp.py`.

## One account per online character

FINAL FANTASY XI's login, lobby and zone sessions are keyed by account. A second login on the same
account replaces the first, so multiboxing means **one account per client**. The launcher supports:

- **Mules** — unlimited characters on one account (`FANXI_MAX_CHARACTERS=0` by default). Only one of
  them can be online at a time.
- **Accounts** — any number of saved accounts, each with its own API token. Add them from
  **Accounts → Add account**.
- **Launch all** — starts one client per saved account that has a selected character.

The server's `POST /launch` now records the chosen character on the login token. `game_login`
copies it to the game session, and the lobby's `0x1F` character list contains only that character.
The client therefore opens the mule the launcher picked instead of the first one on the account.
A plain username/password login still sees every character.

## Processes and ports

`launcher/fanxi_launcher/control.py` owns:

| Concern | Behaviour |
|---|---|
| Control port | `54300`, `54301`, … one free loopback port per client, passed as `FFXI_CONTROL` |
| Log | `<data dir>/logs/game-<account>.log` |
| Duplicate protection | one live process per account |
| Stop | `/shutdown` through the control port, then `SIGTERM` to the process group, then `SIGKILL` |
| Polling | one short-lived thread per client every two seconds; results queued to Tk |

The launcher leaves the game running if the launcher itself is closed; the control port dies with
the game process. The control port is loopback-only and unauthenticated, like the existing
`tools/xi_mcp.py` port: any local process can drive the game. Do not expose it beyond `127.0.0.1`.

## Control protocol

The addon listens on `127.0.0.1:<port>`, one JSON object per line:

```text
-> {"id": 1, "cmd": "metrics", "args": {}}
<- {"id": 1, "ok": true, "result": {"state": {...}, "kpi": {...}, "gear": {...}}}
```

Commands the launcher uses:

| Command | Result |
|---|---|
| `state` | login status, player, zone, target, menu, chat input |
| `metrics` | state plus EXP/hr, rolling DPS, damage total, session seconds and active gear |
| `command {line}` | runs `!zone`, `!merits`, `/heal`, … as typed (no `/say` fallback) |
| `gear` | item id/name/bag/index, stack count and the encumbrance bitfield for all 16 equipment slots |
| `equip {slot, item}` | finds the item in the character's bags and sends `0x050` |
| `equip_set {items}` | finds every piece with one bag scan and injects the whole set of `0x050`s in a single frame |
| `gearswap {path}` | loads a GearSwap Lua file in a sandbox and returns its `sets` table |
| `phase {path, enabled, engaged, idle_town, idle_field, move, default_ws, default_ja, ws_overrides, ja_overrides, spell_overrides, focus}` | builds the precast/midcast/WS/JA/state plan from a GearSwap library and hands it to the host (see below) |
| `phase_status` | the engine's rules, sets, counters, `state`, `town`, `zone`, `job`, `kiting`, `resting`, `focus`, `locked` and `lockedSlots` |
| `phase_lock {locked}` | holds the set that is worn now (`true`) or resumes automatic swaps (`false`) |
| `phase_kiting {on}` | forced kiting state, on until switched off |
| `phase_resting {on}` | manual resting state (this server has no rest packet to follow) |
| `phase_focus {mode}` | idle focus: `auto`, `dt`, `pdt`, `mdt`, `eva` or `meva` |
| `phase_lock_slots {mask}` | pin equipment slots (bit 0 main … bit 15 back) out of every automatic set |
| `job_spells` | the current main/sub job's spell list for the override form |
| `job_abilities` | the main/sub job abilities the client's 0x0AC command list advertises, with action ids and types |
| `weapons` | main/sub/ranged/ammo items in all 18 client bags (slots 1-80) that the main job meets the level and job requirements for, with copy and stack counts |
| `bag_items {container}` | every item in one client container (diagnostic; scans slots 1-80, including slots past `container_max`) |
| `icons {ids}` | item icons as top-down RGBA hex, decoded from the game's DATs |
| `item_ids {names}` | item name -> id, for launcher-side GearSwap set previews |
| `follow {enabled, leader, distance}` | follow a character: replay its trail with native auto-run |
| `follow_status` | `enabled`, `leader`, `state`, `distance`, `stuck`, `leader_found`, `trail` |
| `follow_events` | drain the queued `!follow` commands the client's chat blocked |

In the launcher, the Gear window is under **Gear** in the sidebar (or **Gear & GearSwap** in the
Control room, or by double-clicking a live row). Its **Import GearSwap file…** button is the entry
point for a user's `.lua` sets.

### Follow

The **Follow** card in the Control room assigns line leaders by drag-and-drop or a per-box select.
The follower's client records the leader's horizontal trail and steers with the game's own
auto-run (`FollowDeltaX/Y`, `IsAutoRunning`), so the client still owns collision, animation and
position packets. The default spacing is one yalm; followers stop inside the trail point and
re-close when the leader stops. A follower with no leader in view reports `waiting`; after seven
seconds the launcher sends `!pos` (same zone) or `!zone <zone> <x> <y> <z>` (other zone) to
recover it. A follower that cannot make progress reports `stuck` after four seconds.

Chat commands are handled in the client addon and blocked from reaching the server:

```text
!follow me all                  every running box follows the sender
!follow p1 p2 p3 p4             p2-p4 follow p1
!follow stop p1                 p1 stops following, its own followers stay with it
!follow me p1                   p1 follows the sender again
!follow stopall                 everyone stops following
```

The launcher drains these with `follow_events` and applies the same graph as the Follow card. A
leader may itself follow another leader; cycles are rejected by the launcher.

### Precast, midcast and idle states

The host does what GearSwap does with the action packet. A `0x01A` (the client's action) whose
category and action id have a rule is **held out of its buffer**: the precast `0x050`s go out in
that buffer, the action and the midcast `0x050`s go out in the next one, in that order, and the
return set goes back on when the action's result (`0x028` categories 3, 4 and 6) arrives. A
result that never comes (an interrupted cast, a refused action) brings the return set after six
seconds. This is the same order whether the weapon is drawn or not: casting off a target and
casting from the field both go through it.

The client's outgoing `0x01A` carries the target at `0x04`, the target index at `0x08`, the
action **category** at `0x0A` and the **action id** at `0x0C`. Those last two are what the plan is
keyed by:

| category | the client is | plan |
|---|---|---|
| 2 | `/attack` | the engaged set |
| 3 | casting | precast, then `sets.midcast.<skill>` |
| 4 | `/attack off` | none — the server's `0x00D` decides whether the engagement really ended |
| 7 | a weaponskill | `sets.WS.<name>` (precast) |
| 9 | a job ability | `sets.JA.<name>` (precast) |

Everything else (talk 0, ranged 16, …) passes through untouched. Engaging is a whole-category
state rather than an action with an id — the client leaves the action id at zero.

A `/attack off` is not the state signal. The client sends one by itself whenever the target
leaves its roughly four-yalm auto-attack reach, even though the server keeps the engagement
alive out to draw range so the player can kite in TP gear. The engine therefore waits for the
server's own `0x00D` animation before it wears the idle set; a real disengage, a dead target or
a zone change still sheathes at once. `/!gs kite` and the **Kiting** card remain the manual
way to hold the kiting set.

Two ids need care. A spell's action id is its **spell-table index** (Cure 1, Monomi: Ichi 318),
not the `recast_id` the resource record also carries; the two differ for every ninjutsu, most
songs and blue magic, so a plan keyed by `recast_id` simply never matched. A job ability's action
id is the client's resource id minus `0x200` (Yonin 760 -> 248, Provoke 547 -> 35). That low-nine-
bit rule applies to every `0x200`+ ability type — sambas, waltzes, runes and similar
included — not only the client's "JobAbility" type. Weaponskills use their resource id
unchanged. The control addon builds the rules with those ids.


**Idle states.** Out of combat the engine follows four states and a lock:

| state | what selects it | set |
|---|---|---|
| engaged | the server's own animation for the player (`0x00D`, General block, byte `0x1B` = 1), or the `/attack` packet | Engaged set |
| movement | a step in the client's `Movement.LocalPosition` (a jump over 20 yalms — a zone or teleport — is not a step) | Movement set |
| idle.town | the zone-in packet (`0x00A`, zone id at body `0x2C`) names a city or town | Town set |
| idle.field | the zone-in packet names anything else | Field set |
| locked | the **Lock** button in the Active gear card | whatever was worn when it was locked |

The 0x00A packet is the same one Windower's `zone_change` comes from. It resets the engaged and
movement states (combat does not survive a zone) and schedules the new idle set for 1.5 seconds
later, once the client has loaded the area. The 0x00D animation is what the client actually
draws, so it corrects an engagement the client dropped on its own (a dead target, a target
change) without waiting for `/attack off`; the server also re-sends the attack stance after a
refused or finished cast, because casting sheathes the weapon on the client, and after an
ignored range disengage.

The **lock** is an override, not another state: while it is on, no precast, midcast, engage,
movement or zone swap goes out, and the status names the set it holds. Unlocking puts the current
state's set back in the same command. A **job change releases it** — main job or support job — so
the new job is not left wearing, or unable to wear, the old job's weapon; the new state's set goes
out once the client has settled, exactly as on a zone. The Active gear card shows the state, the
set name and the lock button; the Gear page's **Idle** group picks the town, field and movement
sets.

The control addon samples the player's position a few frames apart; a change calls
`xi.phase.moving()`, which hands back the set for the new state. An action's aftercast returns to
whichever state you are in, and pushing a plan wears the current state's set immediately.

**Stopping GearSwap.** The **Turn GearSwap off** switch on the Gear page's phase header and the
same switch in **Settings → GearSwap** are launcher-wide. Off sends `phase {enabled: false}` to
every running client: the command addon stops its watch loop, clears `phase_plan` and calls
`xi.phase.clear()`, which drops the rule table, pending state set, lock, pins, kiting, resting and
focus. From that point no `0x01A` is held and no automatic set is worn; manual `equip_set` and
**Wear set** still work. The setting is stored in the launcher, not in one client, so a client
launched while it is off gets the same stop, and it survives a launcher restart. It starts off on
a fresh profile, so GearSwap is opt-in rather than something a player has to notice and turn off.

The plan comes from a GearSwap library, the same one the Gear page loads:

| Library path | Becomes |
|---|---|
| `sets.WS.<name>` | a weaponskill rule (category 7, the ability's id): precast |
| `sets.JA.<name>` | a job-ability rule (category 9, the action id above): precast |
| `sets.precast.WS` / `sets.precast.JA` | the fallback for a skill or ability with no named set |
| `sets.precast.FC` (or `sets.precast`) | every spell's precast (category 3) |
| `sets.midcast.<skill>` | a spell's midcast, matched by the spell record's skill (`Healing Magic`,
  `Elemental Magic`, `Ninjutsu`, …) |
| `sets.engaged.tp` (the **TP set** dropdown) | on `/attack` |
| `sets.idle.town` (the **Town idle** dropdown) | disengaged, standing still, in a city |
| `sets.idle.field` (the **Field idle** dropdown) | disengaged, standing still, anywhere else |
| `sets.idle.movement` (the **Moving** dropdown) | disengaged and moving |
| the **Kiting** set | while kiting is on (wins over every other state) |
| the **Resting** set | while resting is on |
| the **DT/PDT/MDT/Eva/Meva** sets | when the idle focus selects one (focus wins over town/field) |
| a **Weaponset** | worn by hand; its pinned slots are filtered out of every automatic set |

The Gear page's **Default JA set** (`default_ja`) replaces `sets.precast.JA` as the fallback for
any job ability with no rule; a per-ability card (`ja_overrides`, keyed by ability name) wins over
both the default and the library's `sets.JA.<name>`. The WS card's `default_ws`/`ws_overrides` work
the same way. The client's `job_abilities` command returns the main/sub list from the 0x0AC command
list, so the cards match exactly the abilities the current job pair was given. `weapons` returns
the client's main/sub/ranged/ammo items filtered by the main job and level, with two counts:
copies (how many identical weapons can fill Main and Sub) and stack quantity (ammo). It scans
every client container's full 1-80 slot range and compares against the client's 1-based job mask
(bit 13 is NIN, not the server item table's 0-based bit 12). The UI hides grips unless Main is
two-handed and hides off-hand weapons/shields when Main is two-handed.

A library without an `idle.field` (the bundled libraries carry `idle.town` and a family of
`idle.dt`/`idle.pdt` sets) can point the Field dropdown at `idle.dt`; the launcher resolves the
choice against the loaded library before it pushes the plan.

That is the GearSwap ordering that matters: weaponskill and job-ability gear is worn *before*
the action packet, so the server rolls the damage and resolves the ability with it on, and a
spell's fast-cast gear is worn before the packet the server times the cast from, with the
midcast set following immediately.

The Gear page groups the plan the way the player thinks about it:

| Group | What it sets |
|---|---|
| **Engaged** | the TP set and the default WS set (used when a WS card has no set) |
| **Kiting** | a forced set that stays on until **Stop kiting** (or `/!gs kite off`), even while engaged or moving |
| **Weaponset** | a main/sub/ranged/ammo set picked from the client's own bags (a single copy can fill Main or Sub; a second copy unlocks the other), worn and optionally pinned; a main or support job change (or a logout) releases the pins and the gear lock |
| **Weaponskills** | a full-width card with a default and one card per `sets.WS.*` name; empty uses the library's WS set, then the default |
| **Job abilities** | a full-width card with a default JA set and one row per main/sub ability; empty uses the default, then the library's `precast.JA` |
| **Resting** | a manual resting set; this server has no rest packet, so it is a toggle |
| **Spells** | a precast set, a midcast default for every spell, and per-spell overrides (picked from the current job's spell list) |
| **Idle** | town, field and movement sets, the DT/PDT/MDT/Eva/Meva sets, and a manual focus selector |

A weaponskill's or job ability's gear is worn before the action, and the state set returns on
the result packet (land or miss), which is the same result path as the action timing above. A
spell default replaces the library's skill sets for every spell; an override is keyed by the
spell-table id and wins over the default. A per-WS or per-JA card wins over its library set; an
empty card uses the default JA/WS set, then the library fallback. The per-WS, per-JA and
per-spell choices ride in the `phase` command's options object (`ws_overrides`, `ja_overrides`,
`spell_overrides`), so the host builds exactly what the page shows.

**Weapon pins.** The host filters pinned slots out of every set it sends — precast, midcast,
engaged, idle, kiting, resting, focus. The Active gear card draws a red border on a pinned
EquipViewer cell. The same pins work from the game: `/!gs lock main, sub, ranged, ammo` and
`/!gs unlock main, sub` (or `all`); the control addon sees the command before it is sent, blocks
it from reaching the server, and confirms in the chat log. `/!gs rest on|off`, `/!gs kite on|off`,
`/!gs focus auto|dt|pdt|mdt|eva|meva`, and `/!gs state` are there too. A job change on either the
main or the support job releases the lock and clears the pins, kiting, resting and focus, wherever
it happens (Mog House, a Nomad Moogle, or `!job` in the field); so does a plan for a different
character. A logout ends the host.

**Throw protection.** The control addon also watches ranged/throw actions (outgoing `0x01A`
category 16). An ammo item is only safe to throw when it is stackable (`stack > 1`) and its
weapon skill is Throwing (27), Archery (25) or Marksmanship (26); a stack of one — a Tathlum,
orb or reusable throwing weapon — is equipment and is never thrown. If the equipped ammo is not
safe, the addon looks for a suitable consumable in the bags: a skill-27 shuriken/stone for a
throw, or skill-25/26 arrows/bolts/bullets when a ranged weapon is equipped. It equips that
item, waits for the equipment echo (up to three seconds), then lets the original action through.
The original ammo is put back about 1.2 seconds after the action, with retries. If no suitable
ammo is in the bags, the action is blocked and the chat log says why. Typed `/ra`, `/throw`,
`/shoot` and `/ranged` commands are guarded before they reach the client as well.

A job change reloads a job-named default library (`gearswap/NIN.lua` for NIN) in the host and in
the launcher, so the new job's sets are worn without reopening the page. The plan is rebuilt when
the library, the client, the job or a set choice changes; it is not re-resolved for every action,
so items moved out of the slot the plan recorded are simply not equipped.

### EquipViewer

The Rust launcher draws Windower's EquipViewer grid on the Home dashboard, in the Control room for
the selected client, and on the Gear page (active gear, selected-set preview and the set editor).
It keeps the addon's slot order and defaults: 32 px cells, alpha 230, a black background at alpha
72, the ammo count at the bottom of the ammo cell, and an X over a slot whose bit is set in the
client's `0x01B` Encumbrance Flags word. `gear` now returns `count` and that word as
`encumbrance`; `icons` supplies the 32×32 RGBA images, which the launcher caches as PNGs in
`<data dir>/icons/` and can clear again from **Settings → Clear icon cache**. The grid polls
`gear` (2 s on the Gear page; the existing 3 s party poll on Home and the Control room), so an
equip is visible on the next tick rather than at the exact `0x050` packet. Set previews resolve
their item names through `item_ids`; an unknown name renders a placeholder tile. Fanxi's server
rejects gear the character cannot use, so it sends a zero flags word today; the overlay is wired
and shows the X whenever the client reports a bit (another server, or future rules).

The rest of the original protocol (`chat_send`, `keys`, `target`, `entities`, `capture`, `lua`, …)
still works, so `tools/xi_mcp.py` is unaffected.

### KPI definitions

- **EXP/hr**: sum of positive `ExpCurrent` deltas since the first `metrics` call, multiplied to an
  hour. A level-up (negative delta) adds the new current value instead of a negative gain. This is
  a session average, not a rolling window.
- **DPS**: damage from incoming `0x028` action packets whose actor is the player, summed over the
  last 60 seconds and divided by the window (or the session length if shorter). Pet damage is not
  attributed to the player.
- **Damage total**: every point the player's actions dealt this session.
- **HP/MP/zone**: read live from the game's party/player structures, not from the database.

These numbers are sampled by the control panel's polling, so they start when the Control page (or
another client) first calls `metrics`. A client that is still signing in has no control port and
shows "starting".

## GearSwap import

The Gear window's **Import GearSwap file…** calls `control.gearswap(path)`. The addon:

1. reads the file with `io.open` (mapped by the addon host's path layer);
2. loads it with `loadstring` and `setfenv` into a table whose fallback is `_G`;
3. stubs `include`, `windower`, `ashita`, `gearswap`, `player`, `world`, `buffactive`, `T` and `S`;
4. runs `get_sets()` if the file defines it;
5. returns `sets`, cleaned of functions/userdata, as JSON.

The launcher flattens a table whose keys are equipment slots into one set. Nested tables become
paths such as `sets.precast.FC` or `sets.midcast.Enfeebling Magic`.

**Wear set** converts each `slot = "Item"` pair to `equip_set`. The item must be in the character's
bags; the panel reports every item it could not find. The host resolves the whole set against one
pass over the bags and injects every `0x050` in the same frame, the way GearSwap sends its equip
burst, so a set lands atomically instead of one slot per frame; pieces already worn are left
alone and the notice shows the round trip (for example `Wore 16 pieces in 31 ms`).

The window also loads the live client's main job from `state` (or the character's saved main job
while the client is still at the character-select screen) and its default `gearswap/<JOB>.lua`
library. **New set…** / **Duplicate** / **Edit set…** open a 16-slot editor, and
**Save version…** serializes the current `sets` table back to a GearSwap `.lua`. The version name is
`<character>-<JOB>-YYYYMMDD-HHMMSS.lua`, written where the user chooses (Downloads by default);
later edits auto-save another timestamped file in the same folder. A JSON copy is written to
`<data dir>/gearswap/<version>.json` for the Control room's versions list.

This is intentionally a safe subset:

- the source file is never written;
- included libraries are not evaluated;
- augments are carried as data and shown read-only in the Gear window (`*`, or `R30` for
  Odyssey armour and weapons); same-name cape and Nyame builds flatten to one base name for Wear
  set, and saving a version drops the augment arrays;
- `!r30 <item>` in the game's chat log prints that item's Odyssey Rank 30 rows (all four
  Nyame paths, or the single Sakpata's/Gleti's/Agwu's row); `!r30` alone lists the 27 items.
- GearSwap's rules, `aftercast`, `precast` hooks and state machine are not reimplemented here.
  Actual GearSwap can still run through the addon host if installed under
  `windower/addons/GearSwap`; the panel is a native inspector/equipper.

## Server/database changes

Restart the server once after updating the code so migration `0062_multibox.sql` runs. It only
adds nullable columns and an index; the launcher can keep using an older server for the single
account flow, but mule targeting and unlimited characters need the new server.

- `FANXI_MAX_CHARACTERS` defaults to `0` (unlimited); `max_characters()` returns `0` for no cap.
- Migration `0062_multibox.sql`: `login_tokens.character_id` and `game_sessions.character_id`.
- `FanxiService.launch()` stores the selected character on the token.
- `FanxiService.game_login()` copies it to the game session and returns it to the lobby.
- `Lobby` filters `0x1F` and `0x07` to that character.
- `create_character()` now returns the character it created (previously it returned the first
  character on the account when there were several).
- Character-specific item migrations no longer fail on a fresh database with no character 1.

## Failure modes

| Symptom | Meaning |
|---|---|
| `no free control port` | 200 ports in use; stop stale clients or change the base |
| `cannot reach the game on 127.0.0.1:…` | the client has not reached its first frame, or was built without the control addon |
| "already online" | the same account is already running in this launcher |
| session expired | that account's token was revoked; **Accounts → Sign in again** |
| GearSwap parse/load error | the file uses an include or a global the sandbox does not stub |
| `not in this character's bags` | the item name did not match an item in bags 0–17 |
| `No WAR default library found` | `gearswap/WAR.lua` is missing; set `FANXI_GEARSWAP_DIR` or use **Import your own…** |

## Next steps

- window placement/focus per client (macOS `osascript` / Win32 `SetForegroundWindow`);
- packet-level event stream and rolling KPI windows persisted to SQLite;
- round-tripping augments and GearSwap rules/event handlers in the set editor; the current editor
  saves flattened slot sets only;
- server-side `/launch` party presets and per-account hotkeys.
