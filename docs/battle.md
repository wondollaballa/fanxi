# Battle hub and automation

The Battle feature is a per-character, client-side combat controller with an in-game ImGui hub.
It is not a server AI: every action is an ordinary client command (`/attack`, `/ra`, `/ma`,
`/ja`, `/ws`), so the client keeps its own range checks, cast bar, recast tables and packets.
Movement uses the game's auto-run (`IsAutoRunning`, `FollowDelta*`), the same mechanism the Follow
controller uses, so collision, animation and position packets stay the client's.

The module is `host/addons/lua/battle.lua`, loaded by the built-in control addon. It shares the
per-character JSON format with the launcher's **Battle** page and saves under
`<data dir>/battle/<character>/<name>.json`.

## Command reference

```text
//battle [toggle|show|hide]                 the hub window (no argument toggles)
//battle assign tank <name>
//battle assign puller <name>
//battle assign kiter <name>
//battle assign support <name> <name> ...
//battle assign melee <name> <name> ...
//battle assign ranged <name> <name> ...
//battle engage when <name>                 only join a mob that player has claimed
//battle engage tank|puller|leader|always|none
//battle camp set here
//battle camp set there                     mouse/arrow placement; Enter drops, Escape cancels
//battle camp radius <1-50>
//battle camp clear
//battle save [name]                        default: new <zone> <timestamp> profile
//battle new [name]
//battle load <name>
//battle list
//battle delete <name>
//battle start
//battle stop
//battle pause melee|ranged|tank|support    toggles that role (commas and several roles allowed)
//battle heal|pull|formation|kite|dispel on|off
//battle buff|enfeeble on|off
//battle cure add <spell> <hp%> | cure remove <spell>
//battle buff add <spell> [self|party|alliance] [seconds] | buff remove <spell>
//battle enfeeble add <spell> [seconds] | enfeeble remove <spell>
//battle camp [tank|support] set here|there | camp [tank|support] radius <n> | camp [tank|support] clear
//battle rally | invite | import
//battle skillchain on|off | skillchain focus <chain>
//battle pull mob add|remove <name> | pull mob clear | pull distance <yalms>
//battle dispel add <spell> [seconds]
//battle ws <weaponskill|off>
//battle death raise|homepoint [wait]
//battle loot free|lot|pass|leader
//battle suggest heal|buff|enfeeble|all
//battle priority heal,buff,enfeeble,dispel
//battle status
//battle help
```

`//battleinfo` (and `//info`) remain the Battle Info statistics window; `//partyinfo` / `//party`
remain Party Info. That is a deliberate split: the old `//battle` alias now belongs to this hub.

## Profiles

One profile contains the roster, camp, engage gate, formation, pull rules, healing, buffs,
enfeebles, dispel, death, kiting, loot policy, priority and window state. The roster is exclusive:
a character is in one role. A role saved for a character who is not in the live party stays in
the profile but does not count toward the live party; see [Live party, not the whole
account](#live-party-not-the-whole-account). `//battle save` with no name creates a fresh
`<zone> <YYYY-MM-DD HH:MM:SS>` profile (the spec's default), while the hub's **Save** button keeps
the current profile's name. `save <name>` writes that name. The launcher's **Battle** page edits
the same object and can load or delete saved profiles.

`assign` and the hub buttons only edit the profile. `start` is what runs it. `stop` ends every
action and releases auto-run; the hub and saved file are untouched.

## How the engine decides

The tick is throttled to roughly seven decisions a second. It first handles K.O., then walks the
**priority** list (`healing`, `buffs`, `enfeebling`, `dispelling`) and executes the first ready
step. A cast or ability then owns the client until the busy window or the client's cast bar ends;
movement during a cast is suppressed.

- **Claims.** `ClaimStatus` is the claiming character's server id. The tank/puller may engage an
  unclaimed mob; everyone else waits for `engage.when` (tank, puller, a named player, the party
  leader, or any party claim). `wait_claim` prevents stealing another party's mob.
- **Puller.** Picks an unclaimed mob within `pull.find_distance` of camp, pulls with ranged
  attack, a spell, a job ability or melee, returns to camp, and looks for the next mob when the
  current target falls to the switch HP. `pull.mobs` is an optional name whitelist (empty = any
  mob); the hub and launcher list the live mobs nearby so names can be clicked, and
  `//battle pull mob add|remove <name>` edits it from chat. `max_mobs` limits claims at camp.
  Sleep/bind are applied only to extra claims that reach camp; the main target is left awake.
- **Tank and melee.** The tank holds the claimed mob. Melee slots are computed from the line
  mob→tank: behind is the opposite direction, then the configured arc is distributed across the
  melee list in roster order. The tank is the anchor, so a marked tank is enough; no separate
  marker bit is needed. Ranged members stay at camp/range and use `/ra`; support returns to camp.
- **Healing.** Observes **party only** or **party + alliance** HP/MP. A cure row fires when the member is at or below
  its HP% (the first eligible row is the tier selected), subject to MP reserve, recast and the
  never-cast list. A job with no Cure spells (BRD/DNC) can fall back to Dancer waltzes; see
  [Dancer waltzes](#dancer-waltzes). Status removal comes first unless the member is already in
  the emergency band. Party status icons are available for slots 0-5; alliance status icons are
  not sent to the client, so -na/Erase/Healing Waltz only see the player party even in Party +
  alliance mode.
- **Buffs.** Known icon buffs are checked directly against `player.Buffs` and the party status
  icons; songs/rolls/barspells without a known icon are interval-driven. Area buffs are cast on
  the caster (Protectra, Hastera, songs, …); single-target buffs use `<pN>`/`<aNN>`.
- **Enfeebles/dispel.** The interval is the re-application clock because the client does not
  expose a monster's active-effect list. A mob we just slept is skipped until the sleep clock
  expires.
- **Death.** The server this build talks to recovers a K.O.'d character after six seconds. `raise`
  waits for that recovery; `homepoint` sends `//hp <number>` as soon as death is seen. The saved
  raise-spell field is reserved for a server that implements Raise.
- **Kiting.** The assigned kiter runs a circle around the camp, away from the mob, or holds camp,
  once player HP is at or below `kiting.below`. Other roles never leave camp except the tank,
  puller and melee formation.
- **Loot.** The server currently has no item drops or treasure pool. The policy is saved and
  shown, but the engine never sends a blind `/lot` or pretends to distribute items.

## Camps and the two groups

The profile has two camps:

- **Tank camp** (`camp`) — where the tank holds the mob, the puller brings it, and melee
  formation is anchored.
- **Support camp** (`support_camp`) — support/healers, GEO/BRD and ranged.

The Camp page has two modes:

- **Static** (default) — EXP/CP/EP camps. Only the puller leaves camp.
- **Mobile camp** — Sortie/Odyssey/Dynamis. Melee follows the tank, and the support camp follows
  the tank at a configurable distance. Static camp points are ignored.

**Use a tank camp** is on by default. Turning it off leaves melee on the tank instead of a fixed
tank camp; starting does not require a camp point in mobile mode or with the tank camp off.

The puller may be a support member: selecting the puller does not remove support, and the support
role still runs its abilities while pulling.

The Camp page's **Camp assignments** section assigns people, not roles. Each character has:

- **Camp** — Auto, Tank or Support. Auto uses the role; an explicit choice overrides it.
- **Combat** — Auto, Melee or Ranged. This is independent of camp: a RNG can stand in the tank
  camp and melee, or stand in the support camp and shoot from 18 yalms out.

**Melee slots follow the tank** is on by default in the melee formation. When off, slots anchor to
the mob as before.

Roster, Camp and Rules are **Shared settings** in the nav. Saving from one of those pages
propagates those shared fields to every character profile in the family; each player keeps their
own player-settings fields. The engine reads the person's camp and combat choice, so the same
character can be a melee RNG in one setup and a support-camp ranged RNG in another.

If the support camp is unset it falls back to the tank camp, so a single-camp setup still works.
Set them independently with the Camp page's **Tank camp** and **Support camp** rows, or:

```
//battle camp tank set here|there
//battle camp support set here|there
//battle camp tank radius <1-50>
//battle camp support radius <1-50>
//battle camp support clear
```

`//battle rally` calls every other online character in the account family to the sender
(`//warp all me`), `//battle invite` invites the online sub-accounts to the party, and
`//battle import` adds currently unassigned party members to the roster by job (tank/job
heuristics, support/melee/ranged; puller stays manual). The same rally/invite/import buttons are
on the Camp and Roster pages and the launcher's Battle page.

The tank and support camps should be roughly 10–20 yalms apart: heals reach about 20 yalms,
while bard songs and many support auras cover about 10. The Camp page warns when they are farther
than 20 yalms apart.

## Healing and buffs

### Healing exclusions

The Healing page has an **Excluded from healing** list. An excluded player is skipped by the cure
watcher and by the normal -na/Erase pass. The exception is a silenced excluded player: the healer
casts **Silena** first so a self-curing PLD can cure again, and an **emergency cure** still
happens when the player reaches the emergency threshold. A player who is silenced and already at
the emergency threshold gets the cure first, then Silena on the next pass. When the healer has no
-na spell (BRD/DNC), the same silence exception uses **Healing Waltz** instead.

### Dancer waltzes

The Healing page has a **Dancer waltzes** section. It reads the client's ability menu, so a Dancer
**main or sub job** both work; the line under the controls lists the waltzes the current job pair
actually has. **Use Curing Waltz for HP** picks the highest-tier Curing Waltz the character knows
and can pay for after the TP reserve, and fires it when a member is at or below **Waltz below %**.
**Use Healing Waltz for status effects** spends 200 TP to remove one waltzable status; a known
-na spell is preferred when it can handle the same status, so a DNC/WHM does not burn TP on a
Poisona. **Keep TP** defaults to 0, so the waltzes are available immediately; raise it to reserve TP for a
weapon skill. Emergency healing ignores the reserve, and Trance makes a waltz free. Saber Dance blocks both waltzes, since the server
refuses them while it is up. **Suggest from job** turns both options on when it finds Dancer
abilities.

The waltzable status list mirrors `server/fanxi_server/game/dancer.py`: Poison, Paralysis,
Blindness, Silence, Disease, Curse, Bind, Weight, Slow, Plague, the elemental DoTs, Dia/Bio, the
stat-downs, max HP/MP down, accuracy/attack/evasion/defense down, Flash and the magic
attack/defense/evasion down family. A status outside that list still needs -na or Erase.

### Buff wizard

The Buffs page is two steps:

1. **Choose buffs.** Select from the known buff spells and known job abilities (search filters the
   list). **Common buffs** fills the usual Protect/Shell/Haste/Refresh/Regen/self-buff set.
2. **Exclusions.** Every selected buff lists the party members. Everyone is included by default;
   check a name to exclude that person from that buff. This is per buff, so a PLD can be excluded
   from Protect/Shell while still receiving Haste.

The profile is per character: open that character's hub to set their rules. A row remembers its
spell/ability, target scope (`self`, `party`, `alliance`), interval and exclude list. Exclusions
are exact for single-target spells and targeted abilities; area songs/rolls still affect everyone
in range.

### Debuff logs and retries

Enfeebles are limited to the tenant's main/sub job spells. The hub also watches the chat log for
the debuff's name:

- A wear-off line marks it due; the next tick reapplies it immediately instead of waiting for the
  full interval.
- A resist/no-effect line increments that debuff's resist count.
- **Stop after N resists** (Pulling-style field on the Debuffs page) stops attempts once the count
  is reached. **Reset tries** clears the counts.

## Server-owned team control

The Battle profile is no longer only a local file. The server is the source of truth for the
team:

- `GET /api/v1/battle/team` returns every character in the account family with its server-side
  profile, revision and `online` flag (`online_known` says whether the live roster was available).
- `PUT /api/v1/battle/team/{character_id}` saves one character's profile. The main account's
  token can write any character in its family; a sub account can write its own.
- Profiles are stored in `char_settings` (`battle_profile`) and survive relogging/restarts.
- The launcher passes `FANXI_API_URL` and `FANXI_API_TOKEN` to every local/remote client. A
  development client also falls back to the launcher's `launcher.json`. The client speaks
  plain HTTP with LuaSocket and HTTPS with libcurl through LuaJIT FFI, so a live launcher's
  `https://...` endpoint works without a local proxy.
- Each client polls the team route (every six seconds) and **applies its own server profile**.
  If the profile's `engine.running` changed, the client starts or stops its Battle engine.
- The team response includes each character's main/sub job, levels and job abilities, so the
  selected tenant drives the UI instead of the local character.
- The hub header has an **EDITING** selector. Selecting another logged-in character pauses this
  box's engine, loads that character's server profile into the full hub, and lets every page edit
  it. **Save** writes it back to the server and restores the local profile; **Hide** cancels.
  The header's **Start on box / Stop on box** sets the server instruction for that character.
- A remote character applies the update on its next poll, including the start/stop instruction.

### Live party, not the whole account

The account family can own six characters while a session runs only some of them. The hub uses
the **live party/alliance** as the active roster, so the same shared profile works for a small
party tonight and all six when the others log in:

- Assignment pickers list only live party/alliance members. A role saved for a character who is
  not in the live party stays in the profile, is labelled `(not in party)` and is not counted by
  the formation, the support anchor or the role lookups.
- The Party rows and the camp, healing and buff exclusion lists use the live party. **Import
  party** adds only unassigned live members.
- The EDITING selector lists only family characters the live zone roster reports online. If the
  character being edited logs out, they stay selectable as `(offline)` so the edit can be saved.
- When the server cannot report a live roster (game gateway off, or an older server), the
  selector falls back to the whole family instead of treating everyone as offline.

Assignments are never pruned automatically: the next time the missing boxes log in and group,
the same profile puts them back in their saved roles.

### Tenant-specific pages

When the editor is on Fivedough, the pages are Fivedough's:

- The header role is derived from Fivedough's roster assignment (Tank), not from the local box.
- Roster shows the live party with each member's main job and level, and highlights the tenant
  when it is in this party (otherwise it says the saved profile is being edited).
- **Healing for Fivedough PLD 99** uses Fivedough's job spells for suggestions and the live party
  list for exclusions; Fivedough is the "me" of the page.
- **Buffs — Rules for Fivedough PLD 99** lists only Fivedough's job buff spells and job
  abilities (PLD plus its sub job), not every spell in the game.
- **Support** shows only the tenant's support job section: GEO for a GEO, Bard for a BRD, and
  a "no support job" message for PLD/RDM/etc.
- **Debuffs** lists only the tenant's enfeebling spells and suggests from that job.
- Skillchain actor pickers use the live party names; the weapon-skill text field remains free text.
- Long hints are split so they do not run past the hub; the formation preview uses a larger
  font and full melee names, and the skillchain diagram is drawn at 14 px with shorter MB text.

The server owns the rules, the per-character revisions and the run/stop instruction. The actual
game action packets (movement, cast, attack, weapon skill) still originate from each client; this
emulator has no server-side player-action injector. If you mean a server bot that produces those
actions itself, that is a larger executor port rather than a rules-sync change.

## Skillchain planner

The hub's **Skillchain** page plans a weapon-skill sequence and its Magic Burst windows:

- **Focus** — any chain, or a specific one (`Light`, `Darkness`, `Fragmentation`, ...). The
  diagram turns red when the sequence's last formed chain does not match the focus.
- **Weapon skill order** — the opener and any number of closers (up to 12 rows; **Add step**). Each
  row names the actor and the client's weapon-skill name (`Tachi: Gekko`, `Tachi: Kasha`,
  `Tachi: Shoha`, ...).
- **Diamond Aspis** — a checkbox per closer. It is detected automatically when the row's actor is
  the local character and the shield (item `26488`) is worn. A closer holding it keeps the
  skillchain and Magic Burst window at the full **11 s** instead of the normal level-2/3 10/9/8… s.
- **Infinite / repeat** — shows the configured cycle with a loop marker and a target link count
  (`0` means loop until stopped). Add more rows for longer finite chains.
- **No skillchain — spam WS** — a style option for Sortie-style fights where a skillchain must be
  avoided. The page then shows only the weapon-skill order, with no focus, MB windows or chain
  validation.
- **Magic Burst** — the bursters and their spells. They are shown in every MB window.
- **Diagram** — `OPEN → CLOSE SC1 → MB window → CLOSE SC2 → MB window → CLOSE SC3 → MB window`,
  with actor, weapon skill, resulting chain and the window duration at each step. A blank later
  row is optional and is left out of the diagram.

The window rules are AutoSkillchains' plus one second: the opener starts an **11 s** window,
a **level-1 link keeps 11 s** (so a `Savage Blade → Hot Shot → Savage Blade` loop is infinite),
and a level-2/3 link leaves **10 s**, then **9 s**, then **8 s**.  A closer wearing the
**Diamond Aspis** keeps every step at **11 s**.  The server accepts a close up to 0.5 s after
the boundary (its status-effect tick), and the Magic Burst window is the same remaining time.

The planner computes the chain from `data/skillchains.json` properties and the directional
transition table. The server runtime uses the same state machine (`skillchain.advance`); the
planner validates the sequence and windows but does not issue the actions itself.

The diagram is drawn at a readable size and can grow; the hub is taller now and the content scrolls
when a long chain or a full Magic Burst list exceeds the window.

## Geomancer and Bard

Both jobs run only for a character assigned to the **support** role. Their settings are on the
hub's **Support** page and the launcher's Battle → Healing & spells page.

### Job support abilities

Every Support page starts with the tenant's **job abilities** (main and sub job). Check
**Keep <ability>** to have the support loop use it while supporting. RDM starts with **Composure**
checked by default; GEO can check Bolster and the rest of its ability list.

### Geomancer

- **At support:** maintains the configured **Indi-** spell around the GEO (default `Indi-haste`).
- **Geo- buffs** (`Geo-haste`, `Geo-refresh`, ...) are cast on the tank/anchor by subtarget.
  The Luopan is placed at that member and the bubble is centered in the tank camp.  If the
  support camp is outside the 12-yalm Geocolure range (the live Bibiki camp is ~40 yalms),
  the loop walks the GEO to the anchor for the cast, then returns to camp.
- **Geo- hexes** (`Geo-frailty`, `Geo-malaise`, ...) are enemy-target spells. The Battle loop
  casts them on the claimed monster nearest the anchor, and the Luopan is placed at that
  monster. Casting a hex on the tank was rejected by both the client and the server, which is
  why support GEO hexes used to do nothing.  The same walk-to-anchor step applies before a
  hex, because the cast still has to be in range of its monster.
- The **Geo anchor** can be any party member; the default is the tank. It is the anchor for
  Geo- buffs and the search point for a hex target. Keep it inside the `cast range` (default
  12 yalms, the Geocolure range). The Camp page prints the camp span, Geo cast range and
  bubble radius, and warns when the camps are too far apart.
- A Geo bubble has a roughly 10-yalm radius. With the anchor in the tank camp and a 6-yalm tank
  camp, the melee group is covered; the support group stays in the Indi aura. A hex lands on
  every monster inside the Luopan's radius.
- Common alternatives: `Indi-refresh`/`Indi-acumen` at support; `Geo-malaise` (magic damage),
  `Geo-torpor` (slow), or `Geo-frailty` (defense down) on the monster.

### Bard

BRD settings are server-driven and song names are never typed. The BRD has one or more
**song groups**, created in the **Song groups** modal (checkboxes for the BRD job songs). Each
group is a named set of songs to keep.

- **Tank camp group** and **Support camp group** choose which group each camp hears.
- **Mobile group** is used when the camp is mobile: everyone follows the tank, so the BRD keeps
  one set and support/melee hear the same songs.
- With two static camps, the BRD runs between them and replenishes the group assigned to each
  camp. **Maintain Nitro** on the Buffs page waits until both Nightingale and Troubadour are
  ready, uses them, and then lets the song cycle cast the set under Troubadour. Songs still
  refresh while the pair is down, and the Support page's **Nitro set** limits the ability pair to
  the tank or support camp group.
- **Pianissimo** is a player target, not a camp: choose the player and the song from the
  combos. It is cast as a single-target extra and is independent of the camp groups.
- Song durations are not configured. The server computes each song's duration from the BRD's
  equipped gear (the `Song Duration Bonus` lines plus 10% per Song+ point); the hub shows the
  bonus and each song's computed duration in the Song groups modal. That figure is the gear timer alone: Troubadour, Clarion
  Call, Tenuto and Marcato are job abilities, so a song can land at more than twice the number
  the modal shows.
- The old free-text song fields and `brd.interval` are gone. The engine refreshes each song when
  the server-computed duration expires.

The Support page shows the BRD as its own section (no empty generic ability list), with the
**Song groups** button and the group selectors.


## Hub

`//battle show` (or `toggle`) draws the window; `Hide`, `//battle hide` or a successful save
closes it. The nav is grouped:

- **Shared settings** — Roster, Camp, Rules.
- **Player settings** — Engage, Skillchain, Pulling, Healing, Buffs, Support, Debuffs, Profile. While it is open the action windows and the Battle Info/Party Info hubs step aside; their
switches are not changed, so they come back as soon as the hub closes.

Camp placement uses the hub's top-down camp map: **Set there** starts the cursor, the arrow keys
nudge it, the mouse moves it over the map, and Enter applies it. Yalm values (camp radius, support
radius, pull leash/search, formation spacing, kite radius, Geo cast range) use a visible
`-  value  +  yalms` stepper; the middle box is editable, so a value can be typed directly or
nudged by one step. The Melee Formation section draws a diagram of the tank, the mob's facing line and
the numbered melee slots for the current style/arc/spacing; with no melee assigned it shows three
example slots.

The hub is part of the HUD master switch: `//hud off` / Ctrl+H / the launcher's **Show HUD**
switch hides it too, while the script keeps running. The launcher's **Battle** page edits the same
profile live and offers Save, Apply live, Start/Stop and Show/Hide.

### Battle HUD while playing

When enabled, a compact, movable **Battle HUD** stays in play with the zone map and the camp
radar. It is a real ImGui window:

- Drag its **title bar** to move it.
- Resize it from the corner.
- Click the **X** to close it. The Camp page has **Show the movable Battle HUD** to bring it back.
- It remembers its position and size in the profile.
- `//hud move` includes it in the global HUD move mode and shows the same **Done** box;
  `//hud move reset` centers it; `//hud save` (or **Done**) saves the layout.
- The drawing area is the zone's own map: the map DAT the in-game map screen (and the Minimap
  plugin) draws, read from the player's FINAL FANTASY XI install at run time. It shows a
  **local window centred on you** (FFXIDB's minimap does the same), not the whole zone: the
  Camps page sets how many yalms fit across it (default 800 yalms), and the mouse wheel over the map
  zooms in and out. The tank and support camps, their radii, the party, nearby mobs and your
  heading arrow sit on it, placed with the map's own scale and offset; a camp outside the window
  keeps a dot on the panel edge, and the footer states the real radii and distances.
- The window is clamped to the map image, so near a zone border it stops rather than showing
  empty space, and a range larger than the zone falls back to the whole map.
- The Camps page has **Zone map behind the Battle HUD** to switch it off and the yalm range.
  Zones without a map keep the plain, camp-centred radar; a dungeon with several floors shows
  its lowest floor.
- The map image is never shipped: it is decoded from the game's DAT when the zone changes, one
  texture at a time. An HD map pack (1024 texel map DATs) is picked up automatically and is what
  makes the tighter ranges crisp.

Below the map (or the fallback radar) is the battle menu:

- **Start** — starts the Battle engine on this character.
- **Stop** — stops it.
- **Follow** — stops Battle on this character, asks the launcher to stop Battle on every
  running box, sends `//follow me all`, and makes the team follow this character. With the
  launcher's follow controller running, everyone runs to you rather than being warped. If the
  launcher is not running the follow command has no controller to act on it.
- **Menu** — opens the full Battle hub without using a chat command.
- **Set tank** — sets the tank camp at the character's current position.
- **Set support** — sets the support camp at the character's current position.
- **Clear camps** — clears both tank and support camps without closing the HUD; only the X or
the Camp page toggle hides it.

The HUD is available when either camp is set, while the hub is hidden, or in `//hud move` mode;
support-only and mobile groups do not need a tank camp just to see it.

The fallback radar is the reliable in-play view because the client's shader cameras are not
exposed as a stable world camera; a true ground-projected 3D ring would need a renderer hook. The
hub's Camp page and formation diagram need no camera.

The zone map's placement values (how a world position becomes a texel) come from the community
FFXI Atlas zone table; `tools/gen_map_data.py` regenerates `host/addons/lua/mapdata.lua` and
`THIRD_PARTY_NOTICES.md` records the provenance. A zone with several maps (a dungeon, or an
island pair like Bibiki Bay) is listed with its lowest floor: the HUD does not switch floors yet.


## Control port

The launcher uses one command:

```json
{"id": 1, "cmd": "battle", "args": {"action": "state"}}
```

| `action` | Result |
|---|---|
| `state` | profile, saved profiles, live status and member list |
| `update {profile}` | sanitize and apply a whole profile live (not saved) |
| `save {name, profile}` | save the profile (and apply `profile` first when supplied) |
| `load {name}` / `delete {name}` / `new {name}` | profile files |
| `start` / `stop` / `pause {role}` | engine state |
| `show` / `hide` / `tab {tab}` | hub window |
| `camp_here` / `camp_radius {radius}` / `camp_clear` / `place_there` | camp |
| `camp_hud {show?, move?, reset?}` | movable Battle HUD visibility/layout |
| `team_switch {name}` / `team_restore` / `team_save {name?}` | central-team editor |
| `suggest {scope}` | fill known job spells into heal/buff/enfeeble lists |
| `command {line}` | the same text as `//battle <line>` |

## Tests

`tests/battle_hub_test.sh --game <FFXI folder>` loads the hub in the addon harness with a mock
ImGui API and calls every tab; it catches a nil field or a widget signature before the hub reaches
a real frame. It also fakes a three-box party against a six-name roster and checks that the
filtered role lists and the melee formation count only the live members. The launcher's TypeScript
check and Rust tests cover the control-port bridge. The in-game path still needs a live client for
camera/claims, which the harness intentionally lacks.
