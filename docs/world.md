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

## Other players

Other characters arrive as `0x00D` packets. The local player is `0x400` in its own client; every
other player gets a targid from `0x401`–`0x6FF`, assigned once per online character and kept
across a zone change. A character is spawned when it comes within 45 yalms and despawned at 50.
Each client remembers which characters it currently draws in `seen_players`, keyed by character
id.

A session ends in one of three ways:

- **Logout** (`C2S 0x0E7`): the character is despawned, its targid freed, its position saved and
  `0x00B` sent.
- **Zone change**: the session is parked in `World.by_char` with its advanced cipher, despawned
  from the old zone, and picked up again by the next `0x00A` within thirty seconds.
- **Silence**: a zone session has no TCP connection, so a force-quit, crash or dead network is
  only visible as missing packets. After sixty seconds the session is treated as logged out and
  despawned from everyone. This is what stops a force-quit character from staying in another
  client's world as a frozen ghost.

A login only continues a session handed to it by the lobby or a recent zone change. It never
takes over the session at the same UDP address: the OS recycles local ports, and doing so gave
the new character the old occupant's name, looks, gear and database id — two different clients
drew the same character after a multi-box relog.

## NPCs and the quest

| NPC | Zone | Script | What it does |
|---|---|---|---|
| Cumetouflaix | Port Jeuno (246) | `Cumetouflaix` | starts, tracks and completes **Pest Control** |
| Gekko | Port Jeuno | `Gekko` | opens a shop |
| the imported NPCs | every zone | the NPC's own name | retail dialogue events, shops and Home Points |

Talking is `C2S 0x01A` with action id `0x00` and the NPC's targid. Fanxi checks the target is an
NPC and that the player is within 6 yalms, then calls the script.

**Pest Control** is stored in `quests` and `char_quests`:

1. Talk to Cumetouflaix, the NPC nearest the Port Jeuno arrival point. The quest becomes `active`.
2. Go to West Ronfaure with `!zone 100`; `!pos -376 -50 311` puts you at an Orcish Fodder camp.
3. Defeat three Orcish Fodder. Each kill increments `char_quests.progress`.
4. Return to Cumetouflaix. The server marks the quest `complete`, adds 300 gil and two Potions,
   and refuses to pay a second time.

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

## The Mog House

The city Mog House doors (`zmr?`/`zms?` zone lines) toggle the character's `moghouse` flag and
move it into the client's Mog House interior, where the resident Moogle stands. Entering is a
rest, as in retail:

- current HP and MP become their maxima and are written to `characters`;
- every status effect is dropped: the `0x037` status packet carries `0xFF` in all 32 buff slots,
  which is what removes the client's icons;
- the login packet's `0x7C` field flips the client into its Mog House state.

Logging back in inside the Mog House rests the character as well. Walking out does not heal.

The login packet's `MyroomMapNumber` chooses the city interior and its exit menu, and
`MyRoomExitBit` names the same city: San d'Oria `0x0121`/`1`, Bastok `0x0122`/`2`, Windurst
`0x0123`/`3` and Jeuno `0x0100`/`4`. A character visiting another nation's Mog House gets the
foreign interior (`0x0101`, `0x0102`, `0x0120`), but the exit menu still follows the city the
Mog House is in. Choosing an area sends `0x05E` with the universal `zmrq` rect; its
`MyRoomExitMode` picks that city's Southern/Northern/Port areas (and Windurst Woods or the four
Jeuno areas where they exist), and the character zones in at the chosen area's outdoor Mog House
door.

## Monsters and combat

West Ronfaure carries the imported spawn table — 480 spawns across 37 templates, from level-1
Wild Rabbits to the 94–95 Notorious Monster Lancing Lamorak. The quest targets the Orcish Fodder
that camp around the zone:

| Monster | Model | Level | HP | Behaviour |
|---|---:|---:|---:|---|
| Orcish Fodder | imported | 3–7 | imported | aggro, roam |
| Orcish Grappler | imported | 3–8 | imported | aggro, roam |
| Wild Rabbit | imported | 1 | imported | roam |

The gateway tick runs on the UDP receive timeout (about every 250 ms). Monster logic is simple and
deliberate:

- idle monsters roam within 5 yalms of their spawn point every few seconds and send `0x00E`
  position updates;
- a monster within 8 yalms of a living player engages, announces itself, and attacks every few
  seconds;
- a player attacks with `C2S 0x01A` action `0x02` while the target is within draw range
  (`ENGAGE_RANGE`, 30 yalms); `0x04` disengages. The client sends its own `0x04` as soon as the
  target leaves auto-attack reach (about four yalms); the server ignores that first
  distance-driven packet and re-asserts the stance, so the engagement survives out to 30 yalms.
  A second `0x04` within 1.5 seconds, `!disengage`, or the target going beyond 30 yalms ends it;
- engaging sends the `0x058` target acknowledgement and then re-sends the self `0x00D` with
  animation `0x1B = 1` (battle stance, weapon drawn); disengaging, target death or player death
  sets it back to 0 (sheathe). Without that byte the client stays in its idle pose and never
  plays the draw or swing animations. The same animation byte is set on a monster while it has
  a target;
- hit chance, damage and critical chance are server-side and follow retail's physical damage
  model (Attack/Defense ratio, fSTR, per-weapon pDIF caps, level correction);
  [combat-damage.md](combat-damage.md) is the reference;
- each swing sends a bit-packed `0x028` battle action: actor, target, basic-attack category,
  `atk0`, hit/miss, critical/defeated flags, animation, damage and the hit/critical/miss message;
- HP changes broadcast `0x00E` with the HP mask and refresh `0x037`/`0x061`/`0x0DF`.
- The gauges carry percentages (`0x037` HPP, `0x0DF` HPP/MPP, `0x00A` HPP), and every one divides
  by the character's current maximum HP/MP. A character at 7240/10149 shows a 71% bar, not a full
  one; only the Mog House rest fills it.

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
- container 2 is the client's Storage bag. The `!storage` command no longer uses it; migration
  `0067` moved its contents onto the server-side slips;
- container 4 is the Mog Locker. No command uses it, and migration `0067` emptied it too;
- containers 8 and 10–16 are Mog Wardrobes 1–8;
- containers 1, 5, 6, 7 and 9 are the Mog Safe, Satchel, Sack, Case and Safe 2;
- slot 0 is gil, stored as item id `65535`;
- slots 1–80 hold items;
- potions stack to 12; swords stack to 1.

The server sends `0x01C` capacities, one `0x020` per item (with the 24-byte attribute block),
per-container `0x01D` "loading" markers, an all-container `0x01D`, and `0x01E` when only a
quantity or gil total changed. `0x01F` is available for lighter updates.

`0x01D`'s `Flags` field is the client's whole container-ready mask, and the client replaces its
mask with whatever the packet carries. Item moves, shop refreshes and storage/locker changes send
all 18 container bits, not just the bags they touched; a partial mask would make every other bag
draw empty (a wardrobe would stay blank until an item was moved into it).

Sorting a bag sends `C2S 0x03A` with the container. The client arranges the slots; the server
merges any partial stacks of the same item in that bag (ammo, food, ninjutsu tools and so on),
filling the lowest-numbered slot first up to the item's stack limit. Emptied slots are cleared
with an `0x020` carrying item id `0`, and the update ends with the usual all-bag `0x01D`.
Different items, different bags, full stacks and rows with different augment extdata are left
alone.

Starter characters receive 1,000 gil, two Potions and an Onion Sword. Existing characters are
backfilled by migration `0003_world_content.sql`.

### Weapons and the sub slot

Equipping a two-handed main weapon (`skill` 4, 6, 7, 8, 10 or 12) clears any shield or off-hand
weapon in the sub slot; after that only a grip fits there. A grip is refused while the main
weapon is one-handed or empty. Hand-to-hand is neither one- nor two-handed for this rule, so a
shield can still share it.

A job change checks gear in **every** bag, not only the normal inventory, so a piece worn out of
a Mog Wardrobe is unequipped when the new job cannot use it. A weapon with no grap model clears
its slot's look instead of leaving the previous weapon on the character; without that, equipping
a model-less grip after a dagger left the dagger drawn on the hip.

## Storage Slips, from anywhere

Retail stores these items by trading a Storage Slip and the matching gear to a
[Porter Moogle](https://www.bg-wiki.com/ffxi/Porter_Moogle); withdrawn items come back from the
server when the slip is traded again. Fanxi keeps the same server-side record in `char_storage`,
keyed by the item's slip, but it does **not** put the item in any bag. `!storage` deletes the
`char_inventory` row and the item disappears from the client until it is grabbed. The Porter
Moogles are placed in the world, but their trade menu is not implemented yet; `!storage` is the
current interface to the same slip record:

```
!storage store nin        put storable NIN gear on its slips and out of every bag
!storage grab nin         take the NIN gear back off the slips
!storage grab all         take everything off the slips
!storage                  list how many items are on each slip
```

A job name, abbreviation or number is accepted (`nin`, `NIN`, `Ninja`, `13`). "Job-exclusive"
means the item's job mask is exactly that job's bit: all-jobs gear and pieces shared with another
job stay where they are (the starter Onion Sword is NIN-usable, but it is not NIN gear). "Storable"
means the item id is listed on one of the 33 Storage Slips in `item_storage`, seeded by migration
`0065_storage_slips.sql`.

Store only takes items a slip accepts. For the NIN reforged sets, Hachiya +4 is Storage Slip 32,
Mochizuki +4 is Slip 33 and Hattori +3 is Slip 30; Kikoku/Nagi/Kannagi/Dokoku, Yagyu Darkblade,
Ninja Nodowa and Hattori Earring are not on any slip, so they stay in the bags and the chat line
names them. Worn pieces stay equipped, and temporary items and the recycle bin are never swept.

Grab puts each item in the first free slot of the normal inventory, then the wardrobes, then the
other permanent bags, so a grabbed set is immediately wearable. If the bags are full the remaining
pieces stay on the slips and the chat line reports it. Neither direction cares where the character
is standing, and the client only sees the source slots clear (store) or the destination slots fill
(grab) through `0x020`/`0x01D`.

Migration `0067_slip_storage.sql` moves anything left in the old visible Storage/Locker containers
into `char_storage`, so the transition leaves no gear stranded in a bag the client shows.

## The 9999-item locker, from anywhere

The client's visible bag capacity is one byte, so a 9999-slot bag cannot be drawn. Fanxi's
`!locker` is a hidden server-side locker with room for 9999 items: storing deletes the item from
every permanent bag and keeps it in `char_locker`, so it disappears from the client until grabbed:

```
!locker store ammo       store every ammo-slot item
!locker store back       store capes and mantles
!locker store materials  store non-wearables: potions, crafting materials, etc.
!locker store Artio      store items whose name contains "Artio"
!locker store all        store every unequipped item
!locker grab ammo        return ammo (same selectors as store)
!locker grab all         return everything
!locker grab broth 12    return at most 12 of the matching item (one stack)
!locker list             list the locker's contents in chat
!locker                  show used/capacity and the selector list
```

Selectors are `all`, a slot (`main`, `sub`, `ranged`, `ammo`, `head`, `body`, `hands`, `legs`,
`feet`, `neck`, `waist`, `ear`, `ring`, `back`), `materials`, or any other word as a name
substring. `cape`, `capes` and `mantle` are aliases for `back`; `ear` covers both ear slots and
`ring` both ring slots. Grab accepts an optional trailing count, which is how a 99-item entry can
be taken one stack at a time. Worn pieces stay equipped, temporary items and the recycle bin are
never swept, and the 9999 limit counts stored quantities. This is independent of the Storage
Slips: `!storage` remains the slip-only store, and `!locker` is the catch-all.

## Working stock (auto-refill)

The client refuses to use an item it cannot see, so a hidden-only consumable can never be
auto-pulled at the moment of use: ninjutsu tools and medicines must be in the inventory, and a
jug must be equipped. Fanxi keeps a small working stack visible and refills it from the hidden
locker:

- **Inoshishinofuda / Shikanofuda / Chonofuda** — Utsusemi Ichi/San/Ni consume one tool and the
  stack is topped back up from the locker, so a cast never leaves the client without the tool.
- **Pet Food Theta** — one stack stays visible for Reward (the server still needs the Reward
  ability itself).
- **Dawn Mulsum** — three stay visible; a use restores 25–50% of the pet's maximum HP and
  pulls another from the locker. It has no effect on GEO Luopans. The server has no pet HP model
  yet, so it reports "no pet to heal" until Call Beast/pet logic exists.

```
!stock                    refill the visible working stacks and show current/target
```

Zone-in also runs the refill automatically. Call Beast jugs are the exception: they are bulk
stored in the locker and `!locker grab <jug> 12` is the current way to bring one out. Call Beast
and Reward themselves are not implemented in the zone server yet, so the items are ready but the
abilities still need their pet logic.

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
!storage store <job>      move that job's storable gear onto its slips
!storage grab <job|all>   take it back off the slips
!locker store|grab <sel>  use the hidden 9999-item locker (all, ammo, back, materials, name)
!locker list              list the locker's contents
!stock                    refill the visible working consumables from the locker
!ws <name>                use a weapon skill (needs 1000 TP and a target)
!ja <name>                use a job ability; quotes around multi-word names are optional
!job <job> [sub]          change job: slip the old set, pull the new one, tidy the bags
!character model <race> <1-48|random>
                          change race/face/hair colour/size; `face 2 hair a size m` and
                          `random` are accepted, and the live model repaints
!abilities                re-send the command data that fills the Abilities menu
!traits                   list the current job pair's job traits and their modifiers
!help                     list commands
```

`!job` is a self-contained swap. It takes the old outfit off, runs the same job store as
`!storage store <old job>`, pulls every item on the new job's slips into a cleared inventory,
wears the best gear it can find (including pieces in the Mog Wardrobes), and moves the
leftovers into the wardrobes. Working stock (ninjutsu tools, pet food, Dawn Mulsum) stays
visible so the client can still use it; equipped pieces stay on.

### Slash commands

The client parses its own slash commands; the server only has to answer the ones that need
world state. The commands that used to disappear are now covered:

```
/lockstyle on|off         lock the current appearance, so gear swaps change stats but not looks
/lockstyleset [n]         lock an equipment set's appearance (no argument: what is worn now)
/lockstyle                ask whether style lock is on
/wave /nod /bow /goodbye  emotes: animation and text, for the player and everyone in the zone
/bye                      host alias for /goodbye (the client's table has /goodbye and /farewell)
/dance /cheer /clap ...   the full emote list, including /dance1-4, /jobemote and /bell
```

An emote is the client's `C2S 0x05D`; Fanxi echoes `S2C 0x05A` back. Style lock is `C2S 0x053`
and is stored per character (the `style_*` columns from migration 0085), so it survives a
relog and a zone change. Locking a new appearance has the client's usual ~10-second cooldown;
a command typed sooner is ignored by the client, not by the server. A job change turns style
lock off. `/heal`, `/attack`, `/ma`, `/ja`, `/ws`, `/item` and `/equip` were already answered
through their own packets; `/shout`, `/tell`, party and linkshell commands still have no
channel in this world.

`!abilities` is the manual form of the automatic refresh: the client builds the Weapon Skills
menu before the zone-in `0x0AC` copy is read, so the server also sends the command data after
the `0x061` stats request and on two short timers, with `0x0AC` before the `0x062` skill packet.

The `0x0AC` Weapon Skills block follows the equipped weapon, not the whole table: it carries the
main-hand weapon's skill type (hand-to-hand when unarmed) plus archery/marksmanship for the
ranged slot, and only skills at or below the character's value for that weapon. Merit and gear
skill bonuses count. Quested/relic/empyrean/aeonic skills have no `skill_level`; they are offered
once that weapon skill is mastered (350+, the level-99 band). The server rejects a weapon skill
outside that list, so `!ws` and the advertised bitmap agree.

The 2025-07-03 client does not read the bitmap directly. It keeps a command-id list at
`[0x106323a8] + 0x160` (count at `+0x1760`) that it saves in `aix.dat`; old profiles kept the
all-weapon-skill list, and a fresh profile had an empty one. `host/addons/hooks.c` rebuilds that
list from every `0x0AC` packet on the game thread, so the Weapon Skills menu (in the field and
while engaged) shows exactly the advertised skills. The list is rebuilt at zone-in, after
`!abilities`, and after a weapon change. A client started before this patch keeps its old list
until it is restarted once. `!ws` still enforces the filtered list.

### Job traits

`0x0AC`'s fourth block (bytes 192..223) is the client's job-trait bitmap. The server serves the
game's trait ids, job/level gates and modifier values in
`server/fanxi_server/game/traits_data.py`, takes the highest rank reached by the main job and the
support job (an equal rank does not stack), and advertises every active id in that block.
`!traits` prints the same list, with the modifier values, and re-sends `0x0AC`.

The Abilities menu itself is built from the client's saved command-id list, not from the bitmap.
`host/addons/hooks.c` rebuilds that list from `0x0AC`; it now appends traits as `0x600 + trait
id` (the client's known-bit encoding) as well as weapon skills and job abilities. Without that
host hook the server's trait block is correct but the "Job Traits" page stays empty, so
`host64` has to be rebuilt after changing the hook. The log line reports both totals, e.g.
`command list rebuilt from 0x0AC: 53 entries (18 job traits)`.

Trait modifiers use the gear modifier ids, so they are merged into the equipment dict before
`stats.build_character()`. Attack, Defense, Accuracy, Evasion, maximum HP/MP, critical damage and
the damage limit therefore read traits and gear through the same path. `Max HP Boost` and
`Max MP Boost` are added to the sheet maximum, and a job change recomputes the stored maxima.

`!traits` lists every active trait, including the killer/resist, Fast Cast, Dual Wield and Store
TP families whose modifiers the current engine does not read yet. Those rows are kept for the
client's trait list and future combat work; only the modifiers named above and the two passive
ticks change behaviour today.

`Auto Regen` (White Mage 25/76, Rune Fencer 35/65/95) and `Auto Refresh` (Paladin 35, Summoner
25/90) are passive modifiers (`REGEN`/`REFRESH`), not status effects: they put no icon in the
client's status bar. The zone tick restores their value once every three seconds while the
character is alive, and gear with `Regen`/`Refresh` adds to the same modifiers. `Auto Refresh`
is not a Red Mage trait; Red Mage has the Refresh spell instead. Blue Mage gets both from its
set spells, which Fanxi does not track yet.

## Spells, buffs and debuffs

A cast is resolved by `cast_magic()` and `resolve_casting()` in `game/zone.py`.  The
effect table in `game/effects.py` maps a spell name to the client's status-effect id,
its duration and the numbers the engine reads:

- **Self buffs** (Utsusemi, Monomi, Tonko, Protect, Shell, Haste, Regen, Refresh,
  Stoneskin, Blink, Phalanx, ...) land on the caster.  The finished action carries the
  effect id in its value and message 230, and the `0x037` status packet puts the icon in
  the client's buff bar.
- **Debuffs** (Kurayami, Hojo, Dokumori, Jubaku, Sleep, Blind, Poison, Slow, Paralyze,
  Gravity, Bind, ...) land on the monster.  The action carries the effect id and message
  237; the server keeps the timer and the potency in the entity's `effect_state`.
- Utsusemi stores a shadow count (3/4/5 for Ichi/Ni/San).  A monster hit consumes one
  shadow and sends message 31 instead of damaging the player; at zero the icon goes away.
  The buff icon is the count itself (66, 444, 445, 446 for one to four or more), so it
  steps down as each shadow is used.
- Blind lowers the monster's accuracy, Slow lengthens its swing interval, Paralyze can
  skip a swing, Sleep/Stun stop it, Bind stops movement and Weight slows it, Attack Down
  lowers its damage, and Poison/Bio tick damage every three seconds.
- Sneak and Invisible keep a monster from aggroing.  Regen/Refresh and Poison tick on the
  player through the same three-second timer as the passive Auto Regen/Auto Refresh.
- A support spell with no entry in the table still finishes; it just does not put an icon
  on anything.  A spell's target flags decide whether it is aimed at the caster or a
  monster; enfeebles always require a live monster.

Rest is `C2S 0x0E8` (`/heal`).  While resting, the player recovers 5% of maximum HP and
MP every three seconds; taking damage, casting, attacking or moving stops it.

Warp, Warp II and Retrace send the character to the **one Home Point set in Profile**
(`characters.home_*`, updated by the crystal's "Set Home Point" choice), not to a crystal
registered in the current zone.  South Gustaberg has no Home Point crystal, so the old
current-zone lookup refused Warp there even though the character's set Home Point existed.
A K.O. without a Raise returns to the same set Home Point instead of reviving in place.
Home Point teleportation from a crystal uses the registered `char_home_points` list and
the client menu index (`home_points.hp_index`); opening the crystal menu requires the
`world_npcs.hp_index` column, which migration 0084 fills.

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
- ranged attacks, TP moves and skillchains (spells, weapon skills and job abilities are
  implemented, and the Abilities menu lists the weapon skills and job abilities the server
  advertises);
- linkshells, parties beyond the local player line, auctions, bazaars and mail;
- raise, and the status effects outside the spell table above (the engine tracks the
  ninjutsu, enfeebling and common enhancing families);
- navmesh pathing (monsters roam in a short radius);
- loot tables beyond the quest reward and shop stock;
- anti-cheat or client-position validation.

The client protocol details and the LandSandBoat study that informed the architecture are in
[protocol.md](protocol.md) and [landsandboat-study.md](landsandboat-study.md).
