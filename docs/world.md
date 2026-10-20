# The world: NPCs, monsters, combat and quests

Fanxi's game gateway is no longer just a place to stand. It now has a small, original world:

- three NPCs in Port Jeuno;
- six monsters in West Ronfaure (two family camps);
- click-to-talk dialogue and a one-quest story;
- a working Moogle shop;
- basic melee combat with hit/miss/critical results, HP updates, EXP, gil and level-ups;
- a persistent inventory (gil, potions and starter swords);
- monster aggro, roaming, death and respawn.

The world is intentionally data-light. It is a vertical slice of the real client protocol, not a
recreation of a retail zone.

## Where it lives

| Piece | File |
|---|---|
| Wire packets | `server/fanxi_server/game/packets.py` |
| Live NPC/mob instances | `server/fanxi_server/game/entities.py` |
| NPC behaviour and the quest | `server/fanxi_server/game/content.py` |
| AI, combat, rewards and respawn | `server/fanxi_server/game/world.py` |
| Zone session and packet dispatch | `server/fanxi_server/game/zone.py` |
| Content tables and starter rows | `database/migrations/0002_world_content.sql`, `0003_world_content.sql` |

Content is split the same way a larger world would split it: rows say **where** an NPC stands and
**which script** it uses; Python functions say **what it does**.

## Entering the world

The client does not receive NPCs and monsters during zone-in. The sequence is:

1. `C2S 0x00A` — the zone login. Fanxi replies with the 260-byte `0x00A` login packet.
2. `C2S 0x00C` — the client has the zone. Fanxi sends the UI/state packets and inventory.
3. `C2S 0x015` — the client's first position update. **This is the trigger**: Fanxi sends one
   `0x00E` spawn for every NPC and monster in the zone, then `0x00E` updates as they move or
   take damage.

`C2S 0x01A SendResRdy` does the same if the client asks that way. The server never sends NPCs on
its own timer before the client is ready.

Entity identity follows the client's rules:

- NPC/mob long id: `0x01000000 | (zone << 12) | targid`;
- static NPC targids: `0x100`–`0x1FF`; monsters: `0x200`–`0x2FF`;
- the player's targid: `0x400`;
- NPC/mob packets use `0x00E`; the player uses `0x00D`.

Spawn packets are 88 bytes (`0x58`), with type/size packed into the first 16-bit header word
(9-bit type, 7-bit size in 32-bit units) and a 16-bit sequence. The payload carries the long id,
targid, send flags, rotation, x/y/z, speed, HP percentage, animation, status, triggerable flag,
model/size and a null-terminated name.

## NPCs and the quest

| NPC | Zone | Script | What it does |
|---|---|---|---|
| Fanxi Guide | Port Jeuno (246) | `guide` | starts, tracks and completes **Pest Control** |
| Wandering Moogle | Port Jeuno | `moogle` | opens a shop |
| Chocobo Stablehand | Port Jeuno | `stablehand` | ambient dialogue |

Talking is `C2S 0x01A` with action id `0x00` and the NPC's targid. Fanxi checks the target is an
NPC and that the player is within 6 yalms, then calls the script.

**Pest Control** is stored in `quests` and `char_quests`:

1. Talk to the Fanxi Guide. The quest becomes `active`.
2. Go to West Ronfaure with `!zone 100`; `!pos -150 -62 250` puts you at the first Orcish
   Grunt camp.
3. Defeat three Orcish Grunts. Each kill increments `char_quests.progress`.
4. Return to the Guide. The server marks the quest `complete`, adds 300 gil and two Potions, and
   refuses to pay a second time.

Dialogue is sent as `0x017` chat lines rather than a client event. FINAL FANTASY XI event bodies
and menus live in the client's DAT files; a server can choose an event id but cannot author its
text. Using chat keeps Fanxi's dialogue original and avoids shipping or relying on retail DAT
content. The quest state machine is real and persists; only the presentation is modest.

## The Moogle shop

Talk to the Wandering Moogle to open a real shop window:

| Item | Price |
|---|---:|
| Potion | 50 gil |
| Onion Sword | 500 gil |
| Bronze Sword | 800 gil |

Packet flow:

```
C2S 0x01A Talk
S2C 0x03E shop open (item count)
S2C 0x03C shop list (price, item id, index; final flag 0x89)
C2S 0x083 buy (quantity, shop no, item index)
S2C 0x03F purchase result
S2C 0x020 item attributes + 0x01D container loaded
S2C 0x017 confirmation
```

The server charges gil, stacks the item into the first free inventory slot, updates the gil item
(row 0 of container 0, item id `65535`), and returns the client's inventory to a consistent state.

## Monsters and combat

West Ronfaure has two camps:

| Monster | Model | Level | HP | Behaviour |
|---|---:|---:|---:|---|
| Orcish Grunt | 612 | 3–4 | 80 | aggro, roam |
| Lambton Worm | 2027 | 2–3 | 45 | roam |

The gateway tick runs on the UDP receive timeout (about every 250 ms). Monster logic is simple and
deliberate:

- idle monsters roam within 5 yalms of their spawn point every few seconds and send `0x00E`
  position updates;
- a monster within 8 yalms of a living player engages, announces itself, and attacks every few
  seconds;
- a player attacks with `C2S 0x01A` action `0x02`; `0x04` disengages;
- hit chance, damage and an 8% critical chance are server-side;
- each swing sends a bit-packed `0x028` battle action: actor, target, basic-attack category,
  `atk0`, hit/miss, critical/defeated flags, animation, damage and the hit/critical/miss message;
- HP changes broadcast `0x00E` with the HP mask and refresh `0x037`/`0x061`/`0x0DF`.

When a monster reaches 0 HP:

- it is marked dead and stops attacking;
- the killer receives EXP and gil (stored on `characters` and in the gil inventory row);
- `0x029` reports the defeat and gil, `0x02D` reports EXP, and `0x029` reports a level-up;
- EXP-to-next is `max(100, 100 × level^1.5)`; each level adds 20 max HP and 10 max MP and heals;
- the quest hook advances if the monster belongs to the quest's template;
- after the spawn's respawn time the monster returns at full HP with a fresh `0x00E` spawn.

Player death is temporary: Fanxi records the death, disengages, and restores the player at half HP
and MP after six seconds. There is no home-point teleport or EXP loss yet.

## Inventory

Inventory is one row per slot in `char_inventory`:

- container 0 is the normal inventory;
- slot 0 is gil, stored as item id `65535`;
- slots 1–80 hold items;
- potions stack to 12; swords stack to 1.

The server sends `0x01C` capacities, one `0x020` per item (with the 24-byte attribute block),
per-container `0x01D` "loaded" markers, a final `0x01D`, and `0x01E` when only a quantity or gil
total changed. `0x01F` is available for lighter updates.

Starter characters receive 1,000 gil, two Potions and an Onion Sword. Existing characters are
backfilled by migration `0003_world_content.sql`.

## Commands

Chat commands remain the fastest way to exercise the world:

```
!zone 100                 West Ronfaure (the monster camps)
!zone 246                 Port Jeuno (NPCs and the shop)
!pos <x> <y> <z> [rot]    reposition
!where                    zone and position
!entities                 list live NPCs/monsters and their targids
!heal                     restore HP/MP
!time <hour>              set Vana'diel hour
!help                     list commands
```

## Content tables

| Table | Meaning |
|---|---|
| `world_npcs` | NPC instance: zone, script, display name, position, model, flags |
| `npc_lines` | ordered ambient lines per NPC |
| `monster_templates` | reusable monster template: name, model, level range, HP, combat stats |
| `monster_spawns` | placed monster: template, zone, position, respawn seconds |
| `items` | item id, name, stack size, usable flag, equip slot, level |
| `char_inventory` | per-character slots; slot 0 is gil (`65535`) |
| `quests` | quest key, reward, required template and kill count |
| `char_quests` | accepted/completed state and progress |

Original content is authored directly in `database/migrations/0003_world_content.sql`. A larger
world can move it to JSON/pack files and keep SQLite for state; the packet and entity layers do
not care where the rows came from.

## Limits

This slice deliberately omits:

- client event cutscenes and DAT-driven menus (NPC text uses chat);
- spells, job abilities, weapon skills, ranged attacks and skillchains;
- linkshells, parties beyond the local player line, auctions, bazaars and mail;
- status effects, raise, home points and zone-line walking;
- navmesh pathing (monsters roam in a short radius);
- loot tables beyond the quest reward and shop stock;
- anti-cheat or client-position validation.

The client protocol details and the LandSandBoat study that informed the architecture are in
[protocol.md](protocol.md) and [landsandboat-study.md](landsandboat-study.md).
