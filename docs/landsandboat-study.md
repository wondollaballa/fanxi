# LandSandBoat study: real-game flows for Fanxi

Fanxi's world layer was designed after a read-only study of
[LandSandBoat/server](https://github.com/LandSandBoat/server), a GPL-3.0 FINAL FANTASY XI
server emulator. This note records what was learned, what Fanxi implemented, and where the
license boundary is.

- **Reference:** `LandSandBoat/server`, commit `475efcc9` (2026-10-19), cloned under `/tmp` and
  never vendored, imported or copied into this repository.
- **Purpose:** understand the behaviour behind the packets Fanxi already speaks, then write a
  small original implementation for Fanxi's own content.
- **Method:** read the reference's packet builders, zone/entity code, AI controllers, content
  loaders and data layout; write behavioural notes; implement from those notes and from
  independent protocol documentation (notably the XiPackets packet reference); test Fanxi's
  implementation against its own synthetic client and database.

No LandSandBoat source, SQL, Lua, YAML, comments, schema or transcribed game dialogue is included
in Fanxi. See [Provenance and license](#provenance-and-license) below.

## 1. The server is several services, not one program

The most useful architectural lesson is the split of responsibilities:

| Service | Owns | Fanxi equivalent |
|---|---|---|
| `xi_connect` | TLS auth, lobby view, lobby data, character selection and zone hand-off | `game/auth.py`, `game/data.py`, `game/lobby.py` |
| `xi_world` | Cross-zone routing and character cache over IPC | not needed at Fanxi's scale |
| `xi_map` | One zone process: all in-game UDP packets, entities, AI, combat | `game/zone.py`, `game/world.py` |
| SQL database | Accounts, characters, content, persistent state | SQLite (`database/`) |
| Lua scripts + data modules | NPC/mob/quest behaviour and authored content | Python content functions + SQLite rows |

Retail runs many map processes; Fanxi runs one process that serves every zone a player can reach.
The packet ownership boundary is still the same: auth/lobby are TCP, gameplay is UDP, and the
zone process is the only place that decides what an entity is doing.

## 2. What actually populates a zone

This was the single most important discovery. A client does **not** receive NPCs and monsters as
part of the zone login:

1. `C2S 0x00A` gets the zone login reply (`0x00A`), equipment clear (`0x04F`), appearance list
   (`0x051`), item capacities (`0x01C`) and equipment list (`0x050`).
2. `C2S 0x00C` (game OK) gets the bulk UI state: zone bitmap, config, jobs, status, magic,
   commands, inventory, party/treasure state. It does **not** get normal NPC/mob spawns.
3. `C2S 0x015` (position) is the trigger. It runs the NPC/mob/pet/trust visibility sweep and
   emits `0x00E` spawns for nearby entities. `C2S 0x01A SendResRdy` does the same.

Fanxi implements this sequence. `ZoneSession.after_zone_in()` sends the UI/inventory state;
`ZoneSession.sync_entities()` is called from the first `0x015` (or `SendResRdy`) and sends one
`0x00E` per entity. This avoids the classic "empty zone" bug where a server sends spawns before
the client is ready and the client drops them.

Other facts that matter:

- NPC/mob long id is `0x01000000 | (zone << 12) | targid`.
- Static NPC/mob targids are `0x000`–`0x3FF`; players are `0x400`–`0x6FF`; pets/trusts are
  `0x700`–`0x8FF`.
- `0x00E` is for NPC/mob/pet/trust; `0x00D` is for players.
- Spawn uses the "all mob" update mask (`0x0F`), and position/HP/status updates use smaller masks.
- The 4-byte sub-message header packs a 9-bit type and a 7-bit size in 32-bit units; the second
  `uint16` is the sequence.
- Entity updates are coalesced to roughly 250 ms, while the AI/logic heartbeat is around 400 ms.
- Visibility is roughly 50 yalms horizontal (45 for player spawns, 50 for despawn) and ±20 yalms
  vertical for mobs; NPCs do not use the vertical check.

Fanxi uses the same IDs, targid ranges and spawn trigger, but a much simpler visibility model:
all entities in the zone are sent once, then updated on movement/damage.

## 3. How a monster behaves

The reference separates the **controller** (the brain: idle, roam, engage, disengage, combat) from
the **state stack** (the body: attack, cast, skill, death, despawn). Fanxi keeps a compact version
of the same separation in `ZoneEntity` + `World._tick_mob`:

```
idle/roam --(player nearby / attacked)--> engaged --(target gone/far/dead)--> idle/roam
   |                                          |
   | HP <= 0                                  | HP <= 0
   v                                          v
 dead --(respawn timer)--> idle/roam
```

Useful behaviours from the study:

- **Aggro is player-driven in the reference.** The mob does not scan every tick; the player's
  spawn/position sync taps nearby mobs, which then decide whether to engage.
- Detection has several senses (sight, hearing, low HP, magic, ability, scent). Sight is roughly
  15 yalms with a facing cone and line of sight; hearing is shorter.
- After disengaging, a mob has a neutral window before it can aggro again; deaggro has a grace
  period. Notorious monsters do not deaggro.
- Roaming picks a point near home and moves toward it; the client dead-reckons from position
  updates and a moving counter.
- Claim is applied on the first swing/damage, not on the engage packet. A second player attacking
  a claimed monster is rejected.
- Enmity is CE + VE per player; damage adds both, VE decays each tick, and the highest enmity
  becomes the target. Links can pull nearby family members.
- A basic attack round is built from main hand, offhand, hand-to-hand, kick and multi-attack
  procs. Hit rate, critical rate, fSTR, pDIF, subtarget defenses and damage type all modify the
  result before one `0x028` action packet goes out.
- Death is a state: the monster stays dead for a while, rewards are distributed at a delay,
  then it fades/despawns and registers a respawn.

Fanxi implements the shape, not the full simulation: a single melee swing, a simple hit/crit
roll, one target, 8-yalm aggro, 30-yalm disengage, 5-yalm roam, 20–25 s respawn, no enmity list,
claim, linking, TP moves or spells. The packet flow is real; the combat math is deliberately
small.

## 4. The action packet

`0x028` is the packet that makes combat look real. It is not a struct; it is a bitstream:

```
actor id (32) | target count (6) | res_sum (4) | category (4) | action id (32) | recast (32)
for each target:
  target id (32) | result count (4)
  for each result:
    resolution (3) | kind (2) | animation (12) | info (5) | hit distortion (2) |
    knockback (3) | damage (17) | message (10) | modifier (31)
    optional proc block | optional reaction block
```

For a basic attack the category is 1, the action id is the FourCC `atk0` (`0x306B7461`), the
resolution is hit/miss, and the message is hit/critical/miss. The client uses this to play the
swing animation and display the damage number. Fanxi's builder packs those fields least-
significant-bit first, matching the client's bit reader, and sends a `0x028` per swing.

The reference also uses `0x029` for standalone battle messages (defeat, gil) and `0x02D` for
end-of-combat messages (EXP, chains, level up). Fanxi sends both for kills and level-ups.

## 5. NPC interaction and quests

The reference's interaction path is:

```
C2S 0x01A Talk -> AI Trigger -> Lua OnTrigger -> quest/mission/NPC handler
               -> event id + params -> S2C 0x033/0x034/0x032
               -> client plays its own event script
               -> C2S 0x05B event end (option)
               -> OnEventFinish -> rewards/state
```

The critical constraint is that **event bodies, menu text and most message text live in the
client's DAT files**. The server chooses an event id and numeric/string parameters; it does not
send dialogue. This is why a retail-compatible server cannot author arbitrary new cutscenes
without client data work.

Fanxi takes the practical clean-room route:

- the quest is a real persistent state machine (`quests` + `char_quests`);
- NPC talk is `C2S 0x01A` with a 6-yalm range check;
- dialogue is sent as original `0x017` chat lines from Fanxi's own content, not retail DAT text;
- the Moogle uses the real shop protocol (`0x03E` + `0x03C` + `0x083` + `0x03F`), which needs no
  client event and is therefore a fully working piece of authored content;
- events/cutscenes are left for later, when there is a content strategy for their client-side text.

Quest persistence in the reference is a bitset plus key/value variables; Fanxi uses one row per
character/quest with a state and progress counter. Both are valid designs; Fanxi's is easier to
inspect and migrate.

## 6. Content is layered

The reference's legacy model has four layers:

| Layer | What it answers |
|---|---|
| pool/template | What is this species? model, jobs, stats, behaviour, aggro, immunities, skills |
| group | How does this family spawn in this zone? respawn time, drop table, HP/MP modifiers |
| spawn point | Where is this individual? position, level range, day/night window |
| drop list | What can it drop, at what rate, and is it normal/grouped/steal/despoil? |

Newer revisions move zone NPCs and mobs to YAML modules with templates, spawns and slots, while
items and zone settings remain SQL. Fanxi keeps a deliberately smaller version of the same layering:

- `world_npcs` + `npc_lines` for NPC instances and lines;
- `monster_templates` (template) + `monster_spawns` (placement);
- `items` + `char_inventory`;
- `quests` + `char_quests`.

This is enough to add new NPCs, camps and quests without touching the packet code.

## 7. What Fanxi adopted, and what it did not

Adopted:

- the login → game-OK → first-position spawn sequence;
- static targid ranges and `(zone << 12)` entity ids;
- `0x00E`/`0x00D` entity packet layouts and update masks;
- the 400 ms/250 ms tick/update rhythm;
- the `0x028`/`0x029`/`0x02D` combat message flow;
- the `0x03E`/`0x03C`/`0x083`/`0x03F` shop flow;
- the layer separation between content rows and behaviour;
- the quest-state/persistent-reward idea;
- the clean-room content boundary.

Deliberately skipped for this slice:

- client event cutscenes and DAT menus;
- full enmity/claim/link/party combat;
- spells, job abilities, weapon skills, ranged attacks, skillchains;
- status effects, raise, home points, zone-line walking;
- navmesh/pathfinding and collision;
- auctions, bazaars, mail, linkshells, parties;
- loot tables and treasure pools;
- the reference's Lua scripting API and SQL/YAML content formats.

The point was not to clone LandSandBoat. It was to make Fanxi's small world behave like a real
FINAL FANTASY XI world at the packet and state-machine level, while keeping Fanxi's code and
content its own.

## Provenance and license

- **Fanxi code:** MIT. See `LICENSE`.
- **Fanxi content:** original names, dialogue, quest text and numbers authored for this project.
  No retail dialogue, event scripts, DAT files, models, music or zone geometry are shipped.
- **LandSandBoat:** GPL-3.0. It was read as a reference only. No files, code, SQL rows, Lua,
  YAML, schema definitions, comments or transcribed dialogue were copied into Fanxi.
- **Protocol facts:** packet ids, field layouts and state-machine behaviour are functional facts;
  the implementation here was written independently and is tested against Fanxi's own fixtures.
- **FINAL FANTASY XI:** trademarks and game content belong to Square Enix. Fanxi is unofficial,
  non-commercial and requires the player's own game installation.

If you contribute content, keep it original. Do not paste LandSandBoat Lua/SQL/YAML, retail
dialogue, or extracted DAT content into this repository.
