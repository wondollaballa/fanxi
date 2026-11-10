# Chemist (CHM): Fanxi design translation and implementation plan

Status: proposal · 2026-11-09

This is the Fanxi version of the Chemist master design. The source document describes a
LandSandBoat server: Lua globals under `scripts/globals`, `spell_list` rows, and character
variables. Fanxi is not that server. It is a Python/SQLite world behind a recompiled
client, with its own packet builders, item model and addon HUD.

The *job fantasy* survives intact: a preparation-heavy, MP-free support/debuffer whose
combat loop is a small Battle Bag, a crafting restock, and debuffs that stack beside the
existing spell lines. The implementation has to be rebuilt around Fanxi's actual
boundaries. This document does that and gives a four-phase delivery plan.

**Recommendation:** build the Chemist as **job 23**, server-first and HUD-first. Do not
replace Geomancer or Rune Fencer. Do not start with a DAT rewrite.

## Implementation status

Server slice landed 2026-11-09:

- job 23 character slot (`characters` check, `character_jobs`, `0x01B`, job names/abbr);
- the five core abilities: Toss, Mix, Catalyst, Amplify, Volatile Synthesis, with level
  gates and recasts;
- the persistent Battle Bag, load caps, Alchemy gates and atomic Chemistry restock;
- Alchemy-scaled potency/tick/duration, Toss hit rolls, stacking debuffs (Aqua Regia,
  Sludge Bomb, Aether Spore, Vitriol) and the custom effect keys;
- a learned recipe book, the Chemistry Toolkit universal reagent and a Mix recipe picker;
- the Brewer's Escutcheon craft-skill shield (`CRAFT_SKILL`/`ALCHEMY_SKILL` and a 2,000 ms
  synthesis cast);
- Mix and synthesis use the client's synthesis pose (animation 44), held on the
  `0x00D`/`0x037` entity animation for the whole cast (the MagicStart result's animation
  field is ignored by the client);
- server tests in `server/tests/test_chemist.py`.

The Fanxi HUD page landed with the same slice: a Chemist window with the Battle Bag, the
five abilities and the stance clocks, and a Chemistry tab in the Spells window, both fed by
`GET /api/v1/characters/{id}/chemist`. The chat path is
`//chm status|load|select|use|recipes|craft|toss|mix|catalyst|amplify|volatile`.

Not yet implemented: native ability names/icons, traps, AF/relic/Empyrean sets, job-point
gifts and the client content pack. The native Ability menu still shows placeholder rows until
the content pack lands; the HUD draws its own names for ids 395-399.

---

## 1. What changes from the source design

| Source design | Fanxi reality | Translation |
|---|---|---|
| `scripts/globals/chemist.lua` | Server logic is Python under `server/fanxi_server/game/` | New `chemist.py` module plus small hooks in `zone.py` and `world.py` |
| Lua `onSpellPrecast` / `onMagicCastingFinish` | `ZoneSession.cast_magic()` and `resolve_casting()` | Python hook functions called from those two methods |
| `spell_list` hijack for crafting | Client spell list comes from its DAT; the server's `spells` table only gates casts | Start synthesis server-side and use the existing `0x028` cast start/finish actions. Do not fake a spell row |
| SQLite `CharVars` (`CHM_Bag_*`) | There is no generic char-var table | A normalized `char_chemist_bag` table. Scalars go in `char_settings` only if they are genuinely settings |
| Custom SQLite status-effect IDs | Status effects are Python integers, not database rows | Internal effect keys in a content table/module. Client icon IDs are a packet-boundary concern only |
| Replace GEO or RUN | Both jobs are fully implemented and have content | Use the reserved **job 23** slot, which the 24-entry job protocol already carries |
| PolUtils DAT strings/menus | Fanxi builds its own client from the player's install and supports `--dats` overlays | Phase 0–2 use the Fanxi HUD and `//chm` commands. A content pack handles native names/icons/gear masks in Phase 3 |
| Standard item stacks of 99 | `items.stack` is retail data: Potion 12, Hi-Potion 1, crystals 12, tools 99 | The Battle Bag has its own per-slot caps; it does not rewrite the item economy |
| "Without Alchemy you cannot use Hi-Potions" | Normal item use is global and currently only handles food/Dawn Mulsum | Gate **loading into the Battle Bag** and **Mix** on Alchemy, not ordinary `/item` use |
| Instant job abilities | A custom ability id has no native name/icon without client content | The HUD sends the normal `0x01A` job-ability action for a reserved id. Native menu entries are Phase 3 |
| "Stacks with Dia/Armor Break" | Reusing effect 149 would overwrite Armor Break's Defense Down | Give Chemist debuffs their own internal keys and apply them as separate multiplicative layers |
| Amplify keeps the lower recast | The client owns spell recasts | The client casts the lower tier and pays its MP/recast; the server resolves the higher tier's effect |
| Job points grant 25 bag slots | Every job currently gets rank 20 in every category | Add a CHM entry to the custom job-point data. The existing "everyone is maxed" policy means CHM starts at the cap unless that policy changes |

Two consequences are worth stating plainly:

1. **No server-side Lua.** The source's Lua architecture cannot be copied. The same logic
   belongs in Python and SQLite.
2. **A custom job is a client-content project too.** Server-only gets a working job, but
   native job names, ability names, icons, the Moogle job-change menu and some equip
   checks are client-side until the Phase 3 content pack lands.

---

## 2. Locked design decisions

These are the assumptions the rest of the plan uses. They are deliberately conservative.

1. **Job id 23, abbreviation `CHM`.** GEO and RUN stay untouched.
2. **Main job only.** The Battle Bag, Toss, Mix and Chemistry are main-job features. A
   CHM support job contributes stats and normal subjob spells, not the bag.
3. **HUD-first, not DAT-first.** Phase 0–2 work with the current client. Native menu
   integration is a later content-pack deliverable.
4. **The Battle Bag is virtual.** Its contents are not `char_inventory` rows and are never
   visible to other systems. Loading a real item removes it from the real inventory;
   restocking a custom item consumes real reagents. This prevents dupe paths.
5. **The bag survives logout, zoning and job changes.** It is character progression, not
   combat state.
6. **One action, one resource spend.** A Toss consumes one bag charge or one real item. A
   failed hit still consumes it. A craft consumes reagents only when it completes.
7. **Custom effects do not reuse retail effect ids for their state.** They may borrow a
   retail icon id for the action packet and HUD.
8. **Reuse existing assets first.** The Alchemist's crafting gear already exists and is a
   natural AF look. Existing throw/ability animations and item icons cover the first
   playable version.

---

## 3. Job 23 scaffold

### 3.1 Identity and combat shape

Chemist is a throwing-skill support/debuffer with no native MP pool dependency. Its
damage is incidental; its value is accuracy debuffs, defense/magic-defense shred, and
unresistable damage-over-time.

Proposed starting grades (tune before implementation):

| Stat | Grade | Reason |
|---|---|---|
| HP | C | Mid-line survivability |
| MP | C | Only subjob spells use it |
| STR | D | Not a melee job |
| DEX | C | Throwing accuracy |
| VIT | C | Mid-line |
| AGI | C | Evasion |
| INT | C | Subjob magic |
| MND | B | Potions/Mix potency |
| CHR | B | Support identity |

Proposed combat skill ranks:

| Skill | Rank | Note |
|---|---|---|
| Throwing (27) | A- | The Toss accuracy stat |
| Evasion (29) | C+ | Tactical support, not a tank |
| Parry (31) | D | |
| Shield (30) | D | The ultimate shield is a sub-slot item |
| Dagger (2) | D | Backup melee |
| Club (11) | C | Backup melee |
| Marksmanship (26) | E | Not a gun job |
| Healing Magic (33) | E | Subjob only |

Alchemy is **not** a combat skill. It is the existing crafting skill id **55** in
`char_craft`, read through `service.crafts_for_character()` and sent in `0x062`. The
Chemist's native cap is 100, with gear and job points on top.

### 3.2 Server changes required for job 23

The job slot is not wired everywhere yet. These are the concrete places:

| Area | File | Change |
|---|---|---|
| Job grades | `server/fanxi_server/game/base_stats.py` | `JOB_OF_ID[23] = "chm"`, `JOB_GRADES["chm"]` |
| Skill ranks | `server/fanxi_server/game/skills.py` | `JOB_KEYS[23] = "chm"` and a custom-rank overlay |
| Skill data | `data/skills.json` is generated from LSB | Do not hand-edit generated data. Put CHM ranks in `data/chemist.json` and have `skills.rank_for()` consult it first |
| Job names | `server/fanxi_server/game/zone.py` | Add 23 to `JOB_NAMES` / `JOB_ABBREVIATIONS` |
| Job points names | `server/fanxi_server/game/job_points.py` | Add 23 to `JOB_KEYS`, `JOB_NAMES`; custom gift rows |
| `0x01B` job arrays | `zone.py::dancer()` | Loop jobs 1..23, not 1..22. The packet has room at `0x44 + job` and `0x68 + job` |
| Job progress | `service.character_jobs_progress()` | Iterate 1..23 |
| Unlock all jobs | `service.set_all_jobs()` | Iterate 1..23 |
| Master level | `service.set_job_master_level()` | Accept 1..23 |
| Character creation | `service._character_fields()` | Accept `main_job`/`sub_job` 23 |
| Job change | `zone.job_id()` | Accept `chm` / `23` |
| Command tests | `server/tests/test_world.py` | The existing assertion that `job_id("23") is None` must change |
| Job-point packet | `zone.job_points()` | Already loops 1..23; verify the payload after the data change |
| Launcher | `launcher-rs/src/lib/format.ts`, `src/components/CharactersPage.tsx`, `src-tauri/src/gear.rs` | Add CHM to job/abbr arrays and GearSwap mapping |
| HUD | `host/addons/lua/control.lua`, `battle.lua` | Add `CHM` to job abbreviation/color tables |
| GearSwap | `gearswap/CHM.lua` | Seed a template file; the launcher can then load it |

One existing gap to verify while doing this: new characters do not appear to get a
`character_jobs` row for their selected job in `_insert_character()`. The live character
still uses `characters.main_job`, but `_change_job()` and the job menu read
`character_jobs`. Phase 0 should test a fresh CHM creation end to end (create, zone, job
change, relog) rather than assume the row exists.

---

## 4. The Battle Bag

### 4.1 Data model

The bag is a new table, not `char_inventory` and not `char_settings` blobs:

```sql
CREATE TABLE IF NOT EXISTS char_chemist_bag (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    slot         INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 26),
    item_id      INTEGER NOT NULL REFERENCES items(item_id),
    quantity     INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    PRIMARY KEY (character_id, slot),
    UNIQUE (character_id, item_id)
);
```

A depleted slot keeps its `item_id` with `quantity = 0`. That is how the engine knows
which recipe to use when the player tries to throw an empty slot. It also makes the HUD
show the slot as empty rather than forgetting the loadout.

Capacity is computed, not stored:

| Main job level | Slots |
|---|---:|
| 1–24 | 5 |
| 25–49 | 7 |
| 50–74 | 10 |
| 75–98 | 15 |
| 99 | 20 |
| Job-point gift (up to 5 ranks) | +5 |
| Empyrean body | +1, capped at 26 |

If capacity ever shrinks, slots above the cap become **dormant**, not deleted. They are
not usable and are not shown as active until capacity grows again.

### 4.2 Loading and stacking

Loading is an out-of-combat action (no cast bar, but a short reuse timer):

- **Standard items** (Potion, Hi-Potion, Ether, Echo Drops, Remedy, Panacea): the bag cap
  is 99 per slot, independent of `items.stack`. Loading consumes the same number from the
  real inventory, so a stack of 12 Potions can only fill 12.
- **Custom chemistry items** (Aqua Regia, Sludge Bomb, Aether Spore, Vitriol, traps): the
  bag cap is 3 per slot. These items exist only in the bag and the database; they are
  never client-visible inventory rows.
- A recipe's yield restocks the slot to 3, not by 3. A slot at 2 after a throw goes back
  to 3; a slot at 0 goes to 3.
- Loading a depleted slot with the same item is allowed if the player has the item.
- `UNIQUE(character_id, item_id)` keeps one slot per item type. Two stacks of the same
  custom item in one bag is not a meaningful choice.

### 4.3 Persistence and lifecycle

- Bag rows are written in the same transaction as the inventory change that loads or
  consumes items.
- Bag contents persist through logout, zoning and job changes.
- The bag is not dropped, traded, sold or mailed. It has no client container.
- A character that changes away from CHM keeps the bag. It is hidden and inert until CHM
  is main again.
- On character deletion, `ON DELETE CASCADE` removes it.
- On reconnect, the HUD requests a bag snapshot; no combat state is restored beyond the
  normal `char_live_state` effects.

### 4.4 HUD snapshot

The Chemist window and the Chemistry tab poll `GET /api/v1/characters/{id}/chemist`, which
returns the bag rows (slot, item, quantity, kind, selected, depleted), Alchemy, capacity,
the three stance windows and the five recast clocks. It is the same launcher-API path
Target Debuffs uses; the client only needs the `FANXI_API_URL` and `FANXI_API_TOKEN` the
launcher already passes when it starts `host64`. This kept the miscdata `0x063` idea for
later and needed no new server-to-client packet.

---

## 5. Combat resolution

### 5.1 Toss

Toss is a job ability with a 20-yalm range, zero cast time and no MP. A hostile target
takes the hostile item path below; a party/alliance member, a Trust, or the Chemist
themself takes a friendly item and resolves exactly like Mix (so "Toss on me" is a
potion). It does not use `/ra`, does not require a ranged weapon, and does not grant TP.

Hostile resolution order:

1. The player must be CHM main, alive, not zoning, and not already casting.
2. Resolve the bag slot or the real inventory item.
3. If the slot is empty, start Chemistry (section 6) instead of throwing. The craft
   restocks the slot; it does not also apply the effect.
4. Consume one charge.
5. Roll physical ranged accuracy:
   - throwing skill (id 27) from `skills.caps_for()`,
   - DEX and `RACC` from the stat sheet,
   - target Evasion from `world.debuffed_monster()`, so a Sludge Bomb makes the next
     Toss more likely to land,
   - `combat.hit_rate()`, one-handed cap, level correction only in corrected zones.
6. On a miss: show the miss action and consume the charge. No effect. Magic Evasion is
   never consulted.
7. On a hit: apply the effect at the Alchemy-scaled potency, with no magic resist roll.

The low-level helper currently lives as `stats._ranged_accuracy_value()`. Phase 0 should
expose a public `stats.ranged_accuracy()` wrapper rather than import a private function
from `zone.py`, so Toss and future ranged abilities use one formula.

### 5.2 Mix

Mix is the friendly mirror:

- Party/alliance player, Trust, or self from the client's act index; self when none.
  Alliance members are valid, not only the Chemist's own party. `//chm mix <name>`
  (and `//chm toss <name>`) resolves a named ally or Trust when the client target is
  not the intended one.
- Consumes one bag charge or one real standard item.
- Applies the item's `chemist_items` effect: heal, MP restore, status removal or a timed
  buff.
- No accuracy roll, no Magic Evasion.
- If the slot is empty, starts Chemistry and ends without applying the effect.
- A heal uses the existing `MESSAGE_SKILL_RECOVERS_HP` result so the target's client
  prints the number and redraws the HP bar.

Fanxi currently has no general potion effect registry: `ZoneSession.item_use()` only
handles food, Dawn Mulsum and dispense pouches. Chemist therefore needs an item-effect
table (section 7.2). That table can later be reused to make ordinary potions work
world-wide, but wiring global item use is a separate change and is not required for CHM.

### 5.3 Potency

`Alchemy` is the crafting skill, not a combat skill:

```python
alchemy = clamp(char_craft[55] + mods.get(mod.ALCHEMY_SKILL, 0), 0, 100)

def scaled_potency(base: int, cap: int, alchemy: int) -> int:
    return base + (cap - base) * alchemy // 100
```

`mod.CHEMISTRY_POTENCY` is added in hundredths of a percent, matching the repository's
modifier convention. Relic armor can raise the cap; the native cap stays 15% Defense Down
for Aqua Regia, for example.

Suggested first-pass values (data, not code):

| Item | Stat | Base | Native cap | Duration |
|---|---|---:|---:|---:|
| Aqua Regia | Defense down | 10% | 15% | 60 s |
| Sludge Bomb | Evasion down | 20% | 25% | 60 s |
| Aether Spore | Magic Defense down | 10% | 15% | 60 s |
| Aether Spore | Magic Evasion down | 15 | 20 | 60 s |
| Vitriol I/II/III | DoT per 3 s | 10/15/20 | +50% at cap | 30 s |

Sludge Bomb's source line says "-25 Evasion"; this plan uses a **percentage** cut because
Fanxi's Evasion is a large derived number and a flat 25 is negligible at item level. If
flat is intended, change one column in `chemist_items` and leave the rest of the engine
alone.

### 5.4 Actions and feedback

- Toss sends a normal `0x028` ability-finish action with the throw animation; Mix and
  synthesis use the client's synthesis pose (animation 44).
- The effect result carries a retail effect id as its visible value so the client plays a
  sensible icon; the server stores its own internal key.
- Chat lines are server-authored: "You toss an Aqua Regia. Defense down: 13%."
- The HUD shows the real Chemist name and remaining time from `target_effect_report()`,
  not the borrowed retail label.

---

## 6. Chemistry: the crafting engine

### 6.1 Trigger

Chemistry starts when a Toss or Mix targets a bag slot whose quantity is 0. It is a
restock action, not a second effect. The player must use Toss/Mix again after the craft.

### 6.2 Recipes

```sql
CREATE TABLE IF NOT EXISTS chemist_recipes (
    item_id      INTEGER PRIMARY KEY REFERENCES items(item_id),
    yield        INTEGER NOT NULL DEFAULT 3,
    cast_ms      INTEGER NOT NULL DEFAULT 12000,
    alchemy_req  INTEGER NOT NULL DEFAULT 0,
    kind         TEXT NOT NULL CHECK (kind IN ('hostile', 'friendly'))
);

CREATE TABLE IF NOT EXISTS chemist_recipe_reagents (
    item_id    INTEGER NOT NULL REFERENCES chemist_recipes(item_id) ON DELETE CASCADE,
    reagent_id INTEGER NOT NULL REFERENCES items(item_id),
    quantity   INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (item_id, reagent_id)
);
```

The eight elemental reagents are **real stackable inventory items**, because the player
must carry them and the client must show them. They reuse the eight elemental crystals
already in `items` (Fire 4096, Ice 4097, Wind 4098, Earth 4099, Lightning 4100, Water
4101, Light 4102, Dark 4103). Their retail stack is 12, not 99.

`char_chemist_recipes` is the learned book. Every character is seeded with all eight
recipes in the current build, and a new character gets the same rows on creation.

The **Chemistry Toolkit** is the client-known **Alchemy Kit 55** (item 8899), so the
inventory and equipment screens never meet a custom item record. The HUD labels the
stack "Chemistry Toolkit"; one kit pays one recipe's entire crystal bill. The launcher's
Data -> Items tab finds it through the `chemistry toolkit` alias. The old custom item
30008 is still accepted for characters who received a stack before the switch; a craft
with neither kit falls back to the elemental reagents.

### 6.3 Cast and interruption

- Base cast: 12,000 ms (inside the requested 10–15 s band).
- `mod.CHEMISTRY_CAST` is a flat millisecond reduction.
- The ultimate alchemy shield in the sub slot carries `-10,000`, leaving **2,000 ms**.
- Floor: 1,000 ms.
- The cast uses the existing `self.casting` state and interrupt path, but with an
  Alchemy-based skill ratio rather than a combat magic skill:
  - `level_ratio` from the attacker's level vs the Chemist's level,
  - `alchemy_ratio = cap / max(1, alchemy)` clamped to 10, so low Alchemy is punished,
  - SIRD from gear and merits,
  - Aquaveil can absorb one interruption if it is up.
- Reagents are consumed **on completion**, not on start, and rechecked at completion. An
  interrupt therefore costs time and the action, not the reagents. This keeps the
  punishment meaningful without creating a "server ate my crystals" failure.
- No Fast Cast, Chainspell or Manafont shortcut applies. Those are spell mechanics; the
  shield is the intended crafting shortcut.

The client does not need a `spells` row. Send the same `0x028` magic-start/finish pair the
spell path uses, with a reserved synthetic action id and a "Synthesis" chat line. Phase 1
must verify on the current client build that this draws a cast bar; if it does not, keep
the server timer and draw the progress in the Fanxi HUD. Do not add a fake `spells` row
just to satisfy the client, and do not rely on `spell_list` — Fanxi does not have one.

### 6.4 The Ultimate Alchemy Shield

The current item is the **Brewer's Escutcheon** (item 26457, client name `Br.
Escutcheon`). Its `item_mods` carry `CRAFT_SKILL +100` (every craft skill, shown by the
client's craft page), `ALCHEMY_SKILL +100` (the Chemist gate) and `CHEMISTRY_CAST -10000`
(synthesis drops from 12 s to 2 s). It is snapshotted at cast start; swapping it in
mid-cast does not help. This is deliberately not `FASTCAST`, which would also speed every
subjob spell.

CHM has the club skill at rank C in `game/skills.py`; migration 0195 adds the job-23
bit to every one-handed club, including **Wizard's Rod (Reforged)**, Maxentius and
Bunzi's Rod. A club and a sub-slot shield are a legal pair, so the Brewer's Escutcheon
can be worn with the Wizard's Rod.

The retail client's item records still carry the 22-job mask, so the native equipment
menu does not list job-23-only gear. Use the server `//equip` command or the launcher's
Gear page for now; the server validates the migrated `items.jobs` mask and sends the
normal `0x050`/grap update. A native-menu patch is the Phase 3 item-mask work.

### 6.5 Empyrean "Augments Chemistry"

At 5/5 Spagyric pieces, a restock has a chance to complete instantly with no reagents and
no cast. Proposed: 5% per piece, 25% at five pieces. The proc is checked before the cast
starts; on a proc the HUD prints "Augments Chemistry!" and the slot refills to its yield.
The body piece adds **+1 bag slot**, capped at 26.

---

## 7. Abilities, items and effects

### 7.1 Job abilities

Use reserved ids **395–401**; no current `job_abilities` row uses that range, and the
`0x0AC` job-ability block is 512 bits wide. Before reserving the range, check the client's
`comm` table: if one of these ids has a retail name or icon, pick another free id below
512 rather than shadowing it. Ids above 159 are not in `0x0AB`, so the `0x1A5` incremental
command update must carry them (the current `char_commands()` already does this for ids
below 512).

| Id | Ability | Lv | Target | Recast | Recast id | Animation | Effect |
|---:|---|---:|---|---:|---:|---:|---|
| 395 | Toss | 1 | enemy | 0 s | 200 | 186 | Throw a hostile bag item |
| 396 | Mix | 15 | party | 0 s | 201 | 84 | Apply a friendly bag item |
| 397 | Catalyst | 35 | self | 60 s | 202 | 171 | Next Toss/Mix becomes AoE |
| 398 | Amplify | 50 | self | 120 s | 203 | 175 | Next subjob spell resolves one tier higher |
| 399 | Volatile Synthesis | 75 | self | 180 s | 204 | 188 | Next hostile Toss auto-hits at max potency |
| 400 | Reload | 1 | self | 30 s | 255 | 83 | Open the bag loadout (out of combat) |
| 401 | Reserve | — | — | — | — | — | Spare id for a later two-hour |

`Toss` and `Mix` have no recast because the bag charge is the cost. Add a 1-second global
throw lock to stop packet spam, not a full recast. `Reload` is optional in Phase 0; the
HUD and `//chm load` can cover loading.

Native ability records for the reserved ids may be blank or may carry a retail placeholder;
verify with `res.ability`/the `comm` table before shipping. The Fanxi HUD can draw the
names and icons from its own table and inject the `0x01A` action. The native Abilities
menu will show blank/placeholder rows until Phase 3. That is the correct trade: a working
job now, native polish later.

### 7.2 Item-effect registry

A new table, loaded by a `chemist.py` helper:

```sql
CREATE TABLE IF NOT EXISTS chemist_items (
    item_id       INTEGER PRIMARY KEY REFERENCES items(item_id),
    kind          TEXT NOT NULL,       -- heal, mp, status, buff, hostile
    amount        INTEGER NOT NULL DEFAULT 0,
    alchemy_scale INTEGER NOT NULL DEFAULT 0,
    alchemy_req   INTEGER NOT NULL DEFAULT 0,
    bag_stack     INTEGER NOT NULL DEFAULT 99,
    effect_key    TEXT,
    potency_base  INTEGER NOT NULL DEFAULT 0,
    potency_cap   INTEGER NOT NULL DEFAULT 0,
    duration      REAL NOT NULL DEFAULT 0,
    tick          INTEGER NOT NULL DEFAULT 0,
    tick_interval REAL NOT NULL DEFAULT 3,
    radius        REAL NOT NULL DEFAULT 0,
    max_targets   INTEGER NOT NULL DEFAULT 1
);
```

First-pass standard items:

| Item | Effect | Alchemy req | Bag cap |
|---|---|---:|---:|
| Potion | Heal 50 + Alchemy | 0 | 99 |
| Hi-Potion | Heal 100 + 2×Alchemy | 20 | 99 |
| X-Potion | Heal 200 + 3×Alchemy | 40 | 99 |
| Ether | MP 20 + Alchemy/2 | 10 | 99 |
| Hi-Ether | MP 40 + Alchemy | 30 | 99 |
| Echo Drops | Remove Silence | 0 | 99 |
| Remedy | Remove Poison/Blind/Paralysis/Silence | 30 | 99 |
| Panacea | Remove all removable debuffs | 50 | 99 |

These values are deliberately simple and testable. They are not a claim about retail
potion formulas.

### 7.3 Hostile arsenal

| Item | Internal effect key | Retail icon used on the action | Stack rules |
|---|---|---|---|
| Aqua Regia | `CHEM_AQUA_REGIA` (2001) | Defense Down 149 | Separate multiplicative layer; stacks with Dia 134, Armor Break 149 and GEO Frailty |
| Sludge Bomb | `CHEM_SLUDGE` (2002) | Evasion Down 148 | Separate percentage cut; stacks with flat Distract/Evasion Down |
| Aether Spore | `CHEM_AETHER_MDEF` (2003) | Magic Defense Down 167 | Separate from existing MDEF down |
| Aether Spore | `CHEM_AETHER_MEVA` (2004) | Magic Evasion Down 404 | Separate from Frazzle/Threnody |
| Vitriol I/II/III | `CHEM_VITRIOL` (2010) | Poison 3 or Bio 135 | One Vitriol at a time; higher tier replaces lower |
| Gorgon's Trap | retail Petrification 7 | Petrification 7 | 15 s; one trap per Chemist |
| Tangle-Vine | retail Bind 11 | Bind 11 | 20 s, 5-yalm AoE, max 4 |

Why custom keys: `world.debuffed_monster()` already applies `DIA`, `DEFENSE_DOWN` and
`GEO_DEFENSE_DOWN` as separate multiplicative cuts. If Chemist reused 149, it would
overwrite Armor Break rather than stack with it. Internal keys 2000+ are stable and
cannot collide with client effect ids; monsters have no `0x037` buff bar, so there is no
packet problem. `target_effect_report()` already returns each effect's `name` for the
HUD.

The action result still carries a retail icon id so the client plays a familiar effect.
The HUD reads the server's real name and timer. If native icons for these debuffs are
required later, that is a client content-pack task, not a server redesign.

### 7.4 Traps

Traps are world state, not bag items once placed:

- `ChemistTrap`: owner, zone, position, radius, trigger effect, arm/finish time.
- The zone tick checks living mobs entering the radius; the first trigger consumes the
  trap and applies the effect to every mob in the radius (or one, for Gorgon's Trap).
- Max one Gorgon's Trap and one Tangle-Vine per Chemist; a new trap replaces the old.
- 60-second arming delay is optional; start with immediate arm and a 300-second lifetime.
- V1 uses a HUD marker and a chat/action line. A visible ground model can reuse a bomb or
  NPC model in Phase 2; no new art is required for the mechanic.

---

## 8. Catalyst, Amplify and Volatile Synthesis

### 8.1 Catalyst

- Applies a self flag with a 60-second window (not a native status icon in v1; the HUD
  shows it).
- The next Toss or Mix becomes AoE, centered on its target:
  - Toss: every living mob within 10 yalms, max 8, each gets its own hit roll.
  - Mix: every party/alliance member within 10 yalms, max 8.
- Relic armor raises the radius (proposed +2 yalms at 5/5).
- Consumed when the Toss/Mix resolves, even if the target list is empty. This prevents
  "Catalyst fishing" with no valid targets.

### 8.2 Amplify

Amplify is a server-side upgrade of the next spell's **resolution**, not a new client
spell:

1. The client casts the lower-tier spell and pays its MP and recast as normal.
2. At cast start/resolution the server checks an explicit upgrade table, for example
   Protect III → Protect IV, Shell III → Shell IV, Fire III → Fire IV, Cure IV → Cure V.
3. The upgraded row supplies base, multiplier, status effect, duration and potency. The
   original spell's MP and recast are kept; the client never sees the higher tier's cost.
4. `Accession` is evaluated against the **upgraded** spec. Protect III → Protect IV then
   spreads as Protect IV, which is the requested Scholar synergy.
5. If no upgrade exists, the spell resolves normally and Amplify stays up with a chat
   hint. Do not silently waste it.
6. Amplify is consumed at successful resolution. Relic armor has a chance to keep it.

This is why the source's "lower recast" is naturally true in Fanxi: the client made the
lower-tier cast, so its recast timer is already the lower-tier one. The server must not
charge the upgraded spell's MP.

Important implementation seam: `cast_magic()` computes `spec`, `healing`, `accession`,
`_cast_numbers()` and the cast record before the finish. The upgrade must happen before
`_cast_numbers()` and before the `accession` decision, or the cast will show the old tier.
`resolve_casting()` then uses the stored upgraded values. Add a focused test for
Protect III + Accession + Amplify to protect this ordering.

### 8.3 Volatile Synthesis

- The next **hostile Toss** automatically hits and applies maximum potency.
- It does not affect Mix, spells or traps.
- It is consumed only by a hostile Toss. If the Toss triggers Chemistry instead, it stays
  up.
- With Catalyst, every target in the AoE gets max potency. That is a deliberate ultimate
  combo; its 180-second recast and the 3-per-slot bomb cap are the brakes.

---

## 9. Equipment and progression

### 9.1 Reuse first

The existing "Alchemist's" gear is a ready-made AF silhouette and is already in the item
catalogue:

- Alchemist's Smock (11335)
- Alchemist's Apron (14398)
- Alchemist's Cuffs (15049)
- Alchemist's Belt (15450)
- Alchemist's Ring (15825)

They are all-job crafting pieces today. Phase 2 can add the CHM job bit and Chemist
modifiers to these rows, then treat them as the AF set. No new model is needed for v1.
Relic and Empyrean can reuse other existing models; unique art is a later content-pack
deliverable.

### 9.2 New modifiers

Add a small block to `server/fanxi_server/game/modifiers.py`. Ids 1300+ are unused in the
current item data.

| Constant | Id | Meaning |
|---|---:|---|
| `ALCHEMY_SKILL` | 1300 | Flat Alchemy skill |
| `CHEMISTRY_CAST` | 1301 | Flat ms reduction to synthesis cast |
| `CHEMISTRY_POTENCY` | 1302 | Hundredths of a percent added to debuff potency |
| `CHEMISTRY_BAG_SLOTS` | 1303 | Extra Battle Bag slots |
| `CHEMISTRY_RESTOCK_CHANCE` | 1304 | Empyrean instant-restock chance |

`CHEMISTRY_POTENCY` and `CHEMISTRY_CAST` are read by `chemist.py`; they should not be
folded into generic `FASTCAST` or `MACC`.

### 9.3 Set plan

| Set | Pieces | Mechanics |
|---|---|---|
| Alchemist's Attire (AF) | 5 | Ranged Accuracy, Alchemy skill, Chemistry cast reduction; Mix duration +; Toss RAcc + |
| Hermetic Attire (Relic) | 5 | Catalyst radius +2; Volatile recast −30 s; Amplify retention 10%; debuff potency cap +2% |
| Spagyric Attire (Empyrean) | 5 | "Augments Chemistry" 5% per piece instant restock; body +1 bag slot |
| JSE cape/neck | 1 each | Pure stat sticks: HP, RAcc, Alchemy, Enmity− |

The exact per-piece numbers belong in the item data, not this document. The important
architecture is that every set bonus is read from `set_bonuses.py`/item mods at the same
point the Chemist action is resolved, so the HUD and server cannot disagree.

### 9.4 Job points

Add a `chm` entry to the custom job-point data (not to the generated LSB table):

- Bag Capacity +1 per rank, 5 ranks.
- Alchemy Skill +1 per rank, 20 ranks.
- Toss Accuracy +1 per rank, 20 ranks.
- Chemistry Cast −100 ms per rank, 20 ranks.
- Potion Potency +1% per rank, 20 ranks.

The current server sends every job at rank 20 with 2,100 JP spent, so CHM receives all
five gifts immediately. If that global "all jobs maxed" policy changes later, the bag
capacity table already reads the gift total and needs no new code.

Job points do not grant native merit labels for job 23 yet; the client table has
placeholders. The HUD can show the Chemist categories without them.

---

## 10. Architecture and modules

### 10.1 New server module

Create `server/fanxi_server/game/chemist.py`:

- `BagSlot` / `BagSnapshot` dataclasses.
- `capacity(character, job_points)` and `stack_cap(item_id)`.
- `loadout()` / `load()` / `consume()` with SQL transactions.
- `toss()` / `mix()` resolution helpers (pure functions where possible).
- `potency()` / `alchemy()` / `craft_cast_ms()`.
- `start_synthesis()` returns a cast state for `ZoneSession`.
- `finish_synthesis()` rechecks reagents and restocks atomically.
- `apply_effect()` wrappers for custom keys.
- `catalyst_radius()`, `amplify_upgrade()`, `volatile_active()`.
- `trap_tick()`.

`zone.py` should stay the packet/state owner; `chemist.py` should be the rules/data owner.
That keeps the new job testable without a socket.

### 10.2 Hooks into existing code

| Existing code | Hook |
|---|---|
| `zone.job_ability()` | Dispatch 395–401 to `_chemist_ability()` before generic fallback |
| `zone.cast_magic()` | Call `chemist.on_spell_precast()` for Amplify upgrade and Accession ordering |
| `zone.resolve_casting()` | Call `chemist.on_spell_finish()` for Amplify consumption and retention |
| `zone.interrupt_chance()` | Branch for synthesis state; use Alchemy ratio |
| `world.debuffed_monster()` | Add `CHEM_AQUA_REGIA` defense cut and `CHEM_SLUDGE` evasion cut |
| `world.monster_debuff_mods()` | Add `CHEM_AETHER_*` deltas |
| `world.tick_mob_effects()` | Generic already; ensure `tick_interval` and `source` are set |
| `service.inventory`/`add_item`/`consume_inventory_item` | Use existing atomic helpers; add only bag queries |
| `zone.char_commands()` / `abil_recast()` | No change beyond including 23's rows; verify 0x1A5 carries 395+ |
| `control.lua` / `battle.lua` | HUD action bar, bag panel, custom names/icons |

### 10.3 Why not a fake spell for crafting

The source design wants the client to own the cast bar through `spell_list`. In Fanxi:

- the client's spell table is a DAT resource, not the server's `spells` table;
- the server's `0x0AA` packet only tells the client which ids are known;
- `cast_magic()` already sends a `0x028` magic-start action, so the server can drive a
  cast without a client spell row;
- the interrupt path is server-side.

Use the server-driven cast. It is less coupled to a client DAT and gives the designer
control over the Alchemy interruption ratio. If the client build refuses to draw a cast
bar for an unknown action id, the HUD draws the progress; the mechanic still works.

---

## 11. Client integration

### 11.1 What works in Phase 0 without client content

- Create a CHM character through the launcher/API (`main_job = 23`).
- `//job chm` and `//job 23` on the server.
- Toss/Mix/Catalyst/Amplify/Volatile via HUD buttons or `//chm` commands, which inject
  the normal `0x01A` job-ability action.
- Server action packets, chat lines, and HUD bag/status.
- Existing Alchemist's gear and existing item icons, if the equip mask is handled.

### 11.2 What needs a small client patch

- **Equip job mask.** The client's item records currently carry `0x3FFFFF` (jobs 1–22).
  Job 23's bit is `1 << 22 = 4194304`. Server-side `items.jobs` can be updated, but the
  client also validates the mask.
  - First spike: try server-driven auto-equip of an all-job piece on a CHM. If the client
    displays it and keeps it equipped, no patch is needed for the first slice.
  - If it refuses, add a targeted runtime patch that ORs bit 22 into item records whose
    mask is `0x3FFFFF`. This makes all-job gear CHM-usable and is enough for the
    Alchemist's set. Record the finder in `tools/` and `meta/builds.json`.
- **Native job name/abbr/icon.** The client still shows `???`/blank for job 23. The Fanxi
  HUD uses `CHM`; native UI waits for Phase 3.
- **Native ability names/icons.** The HUD supplies names; the native Ability menu is
  blank until Phase 3.
- **Native job-change menu.** 22 rows. Use `//job`; Phase 3 can patch the menu.

### 11.3 Phase 3 content pack

When native integration matters, add a content pack rather than hand-editing DATs:

```
content/jobs/chm.toml
content/abilities/chm.toml
content/items/chm.toml
content/art/icons/...
tools/build_content.py
```

It should generate:

- job 23 name/abbr in `jobs.names` / `jobs.names_abbr`;
- ability records in unused `comm` slots 395–401, with names, descriptions, icons and
  animations;
- item records for Chemist gear, including the job-23 bit;
- generated DAT overlays under `build/content/dats`, applied with `--dats`;
- a per-build finder and `meta/builds.json` entry for every patch site.

Do not commit retail-derived assets. The content pack is built from the player's own
install; original art goes under `content/`.

---

## 12. Delivery plan

### Phase 0 — playable scaffold (the first vertical slice)

Goal: a CHM can be created, changed to, equipped, throw one debuff, heal one ally, and
restock, with no native UI and no DAT rewrite.

- Job 23 in `base_stats`, `skills` overlay, `zone` maps, `service` validation, launcher
  and HUD maps.
- `char_chemist_bag` migration and `chemist.py` bag service.
- Toss and Mix for three items: Potion (friendly), Aqua Regia (hostile), Fire Crystal
  (reagent).
- Depleted-slot Chemistry placeholder with a fixed 12 s server timer and no shield yet.
- HUD button palette and `//chm status`, `//chm load`, `//chm toss`, `//chm mix`.
- Equip-mask spike; if required, the targeted all-job mask patch.

Exit criteria:

- create CHM, `//job 23`, zone, relog;
- load 5 Potions and 3 Aqua Regia;
- Toss lands and shows Defense Down in the HUD;
- Mix heals a party member;
- empty slot triggers a 12 s restock, consumes a Fire Crystal, refills to 3;
- 22 existing jobs still build, zone and use abilities.

### Phase 1 — the Chemistry loop and the first stack

- Full recipe/reagent tables, atomic restock, interrupt handling with Alchemy ratio.
- Ultimate Alchemy Shield and `CHEMISTRY_CAST`.
- Catalyst, Amplify, Volatile Synthesis.
- Aqua Regia, Sludge Bomb, Aether Spore, Vitriol I.
- Stacking tests against Dia, Armor Break, Distract and Frazzle.
- HUD bag panel, craft progress and stance indicators.

Exit criteria:

- a 2,000 ms shield craft is possible and a no-shield craft is interruptible;
- Aqua Regia and Dia both appear and both reduce defense;
- Amplify turns Protect III into Protect IV and Accession spreads it;
- Volatile Synthesis makes the next Toss auto-hit at cap;
- reconnect restores the bag and not the one-shot stances.

### Phase 2 — arsenal, traps and gear

- Vitriol II/III, Gorgon's Trap, Tangle-Vine.
- AF/Relic/Empyrean set bonuses, JSE accessories, job points.
- Trap visuals (reused model) and HUD markers.
- Gear job masks for the Alchemist's set and custom Chemist pieces.

Exit criteria:

- all six hostile items and three friendly tiers work;
- traps trigger on monsters and not on party members;
- 5/5 Empyrean can proc a free restock;
- Relic Amplify retention and Catalyst radius are visible in the HUD;
- item-level 119 test against a high-evasion target is stable.

### Phase 3 — native client content

- Content pack for job strings, ability records, icons and item job masks.
- Native Ability menu, job-change entry and status display.
- Optional custom status icons for Catalyst/Amplify/Volatile.
- Per-build finders and `meta/builds.json` entries.

Exit criteria:

- job 23 displays as `CHM` in native menus;
- Toss/Mix have native names and icons;
- Alchemist's gear can be equipped through the client UI;
- all client edits survive a client build re-run.

---

## 13. Test plan

Add `server/tests/test_chemist.py` and extend the existing job/regression suites.

Unit tests:

- capacity at each level and with JP gifts/body;
- bag stack caps (99 standard, 3 custom), depleted slot retention;
- load consumes real inventory exactly once;
- craft consumes exactly the recipe quantities; a missing reagent fails atomically;
- interrupt does not consume reagents;
- Toss miss consumes the charge and applies nothing;
- Alchemy scaling hits base and cap; `CHEMISTRY_POTENCY` is additive in hundredths;
- Aqua Regia + Dia + existing Defense Down all apply (multiplicative);
- Sludge Bomb raises the next Toss's hit chance;
- Aether Spore reaches `monster_debuff_mods()`;
- Vitriol ticks at its interval and does not overwrite Poison/Bio;
- Catalyst hits the radius and max targets, and is consumed;
- Volatile auto-hits and caps, and is not consumed by Mix;
- Amplify upgrade table, MP/recast preservation, Accession ordering, no-upgrade refund;
- shield cast time and snapshot at start;
- Empyrean proc rate and no-reagent path;
- trap trigger, ownership and expiry.

Integration/regression:

- `job_id("23")`, `job_id("chm")`, `//job 23`, job change packet;
- `0x01B` carries job 23's level/master level in the 24-slot arrays;
- `0x0AC` / `0x1A5` carry 395–401; `0x0AB` unchanged for <160;
- `0x063` job-point payload for job 23;
- `0x037` does not receive out-of-range custom effect ids for player buffs;
- 22-job regression: create/zone/job change/ability for a sample of existing jobs;
- launcher builds with 23 jobs; GearSwap maps CHM;
- client smoke: HUD action, chat feedback, relog, zone change.

Manual client checks (required because the client is the other half):

- does a server-driven equip of an all-job item work on job 23?
- does an unknown `0x028` magic-start draw a cast bar?
- does the native party list render job 23 without breaking?
- does a blank native ability row crash the menu or simply show blank?

---

## 14. Risks and guardrails

| Risk | Impact | Guardrail |
|---|---|---|
| Client refuses job-23 gear | No visible gear | Phase 0 equip spike; targeted all-job mask patch; custom item records in Phase 3 |
| Native ability menu shows blank | UI looks unfinished | HUD-first, native content pack later; never block gameplay on DAT work |
| Craft cast bar does not draw | No native feedback | HUD progress bar; server timer is authoritative |
| Infinite bag/reagent dupe | Economy break | All mutations in one SQLite transaction; virtual bag only; no trade/drop path |
| Debuffs overwrite retail lines | Lost stacking | Internal keys 2000+; never reuse 149/148/167/404 for Chemist state |
| Catalyst/Volatile too strong | Trivializes NMs | 60/180 s recasts, 3-per-slot bombs, max 8 targets, consume on resolution |
| Amplify + Accession ordering bug | Wrong tier or no AoE | Upgrade before `_cast_numbers()`/Accession; focused test |
| Job 23 breaks packet packing | Corrupt job menu/party | 24-slot tests; only use the reserved slot, never replace GEO/RUN |
| Job-point data missing | No bag growth/gifts | Custom overlay, not generated LSB data; test rank totals |
| Client build drift | Patch breaks | Finder-based patch and `meta/builds.json`; no hardcoded addresses |

Additional rules:

- Do not add a global `items.stack = 99` migration for Chemist.
- Do not add the CHM bit to every item server-side without the client side; that would
  make the server and client disagree about equip legality.
- Do not put one-shot stances in `0x037` with ids above the client's status table. Use
  server flags and the HUD until custom status icons exist.
- Do not make the Battle Bag a real inventory container "for convenience"; that creates
  trade/sell/drop paths and a second source of truth.

---

## 15. Open decisions

These need a product call before Phase 0, but none blocks the architecture:

1. **Bag stack abstraction.** Is 99 per standard slot intentional even when the real item
   stacks to 1 or 12? This plan says yes; it is a balance lever, not an item-table change.
2. **Sludge Bomb scale.** Percent Evasion down (this plan) or flat −25 (the literal
   source line)? Percent is meaningful at iLvl 119; flat is closer to Distract.
3. **Alchemy gating.** Does Alchemy gate only bag loading/Mix, or should ordinary
   `/item` use also require it on CHM? This plan gates the job systems only, so a CHM can
   still use a Potion outside the bag.
4. **Native UI appetite.** Is a HUD-first job acceptable for the first release, or is the
   ability/job name DAT work a launch blocker? The estimate changes substantially.
5. **Reagent identity.** Reuse the eight elemental crystals (stack 12) or add eight
   custom 99-stack reagents with a small item overlay? Reuse is faster; custom is closer
   to the source's 99-stack fantasy.
6. **Job-point policy.** Every job is currently maxed at rank 20. Should CHM also start
   maxed (25 slots immediately), or should the Chemist be the first job with real JP
   progression? The latter is a broader server change.

---

## 16. One-page summary

- **Job:** 23, `CHM`, main-job only, throwing/Alchemy support-debuffer.
- **No DAT rewrite for v1:** HUD/commands drive the custom abilities; native names/icons
  are Phase 3.
- **No Lua:** `server/fanxi_server/game/chemist.py` plus hooks in `zone.py`/`world.py`.
- **Bag:** `char_chemist_bag`, virtual, persistent, 5→25 slots, 99/3 stack caps.
- **Craft:** server-timed 12 s, shield 2 s, Alchemy-based interrupt, reagents on
  completion, Empyrean free-restock proc.
- **Stacking:** custom internal keys 2000+, retail icons only at the packet boundary.
- **Abilities:** Toss, Mix, Catalyst, Amplify, Volatile Synthesis; explicit Amplify
  upgrade table; Accession applies to the upgraded buff.
- **Gear:** reuse Alchemist's models, add CHM mods and set bonuses; one targeted client
  item-mask patch if server-driven equip is refused.
- **First milestone:** a CHM can create, equip, Toss Aqua Regia, Mix a Potion, restock
  from a crystal, and relog with the bag intact — without breaking any retail job.
