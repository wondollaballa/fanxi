# Mock GearSwap set libraries (one per job)

Twenty-two self-contained GearSwap-style `.lua` files. They are the launcher's
built-in defaults for each job as well as ordinary importable files. Each covers
the gear categories the Gear window can display and equip: idle/DT, max HP, max
PDT/MDT, TP (including accuracy, dual-wield and hybrid variants), fast cast,
Macc/MAB midcasts, weaponskills, job abilities, enmity, and the job-specific
pet/ranged sets.

These are **mock libraries**, not a claim of best-in-slot. Item names come from
retail gear (mostly iLvl 119); the numbers behind them are not modelled anywhere in Fanxi
yet. Treat each set as a realistic starting point to edit.

Every library also carries the full Odyssey Rank 30 block: `local odyssey` holds all four
Nyame paths, Sakpata's, Gleti's and Agwu's armour and the seven Odyssey weapons, and
`sets.Odyssey` lists the builds that job can wear. The data comes from
`data/odyssey_r30.json` through `tools/gen_odyssey_r30.py`; see
[../docs/odyssey-r30.md](../docs/odyssey-r30.md).

| File | Job | Role | Sets |
|---|---|---|---:|
| `WAR.lua` | Warrior | two-handed axe, off-tank | 30 |
| `MNK.lua` | Monk | hand-to-hand, counter/HP | 29 |
| `WHM.lua` | White Mage | healer, divine magic | 34 |
| `BLM.lua` | Black Mage | elemental nuker | 32 |
| `RDM.lua` | Red Mage | enfeebler/enspell hybrid | 35 |
| `THF.lua` | Thief | dual-wield dagger, TH | 34 |
| `PLD.lua` | Paladin | sword-and-shield tank | 39 |
| `DRK.lua` | Dark Knight | scythe, drain/aspir | 44 |
| `BST.lua` | Beastmaster | pet melee, axe | 33 |
| `BRD.lua` | Bard | songs, Macc support | 32 |
| `RNG.lua` | Ranger | marksmanship, snapshot | 35 |
| `SAM.lua` | Samurai | great katana, skillchains | 29 |
| `NIN.lua` | Ninja | dual-wield katana, ninjutsu | 32 |
| `DRG.lua` | Dragoon | polearm, jumps, wyvern | 32 |
| `SMN.lua` | Summoner | avatars, blood pacts | 31 |
| `BLU.lua` | Blue Mage | blue magic hybrid | 33 |
| `COR.lua` | Corsair | gun, rolls, quick draw | 32 |
| `PUP.lua` | Puppetmaster | hand-to-hand, automaton | 30 |
| `DNC.lua` | Dancer | dual-wield dagger, waltzes | 34 |
| `SCH.lua` | Scholar | healing/nuking, stratagems | 42 |
| `GEO.lua` | Geomancer | geomancy support/nukes | 31 |
| `RUN.lua` | Rune Fencer | great-sword tank, runes | 42 |

"Sets" is what the launcher lists after import (empty group tables are not
counted). Together the folder defines **745 importable sets**, counted with the
launcher's own flatten pass.

The same files also carry the five **Limbus** top-tier suits: a `local limbus`
build table (one copy per augment choice a set needs), a `sets.Limbus`
container, and — where the job community rates the suit — the pieces already
worn in `sets.engaged.tp` / `sets.engaged.hybrid` / `sets.precast.FC`. Duty
goes to MNK/THF/DNC/BST/PUP, Revelation to BRD/NIN, Sworn's fast-cast to
PLD/RUN/RDM, Clemency's head and feet to SAM/DRG, and SCH wears Indomitable:
head/body/legs in the free nuke and helix, body/hands/legs in enfeebling,
body/legs in fast cast, the full five in Elemental Macc, and the new
`sets.idle.dt_indom`. Arbatel Loafers +3 stays in the nuke/helix feet
(`"Klimaform"+25`), and the Enhancing Magic and Healing Magic sets are
untouched. See [../docs/limbus-r30.md](../docs/limbus-r30.md) for the table and
the reasoning.


## Quick start

1. Start a client from the Control room.
2. **Gear** in the sidebar (or **Gear & GearSwap** in the Control room).
3. The window detects the live main job and loads the matching `<JOB>.lua`
   automatically. Use the **Defaults** dropdown and **Load** to open another job,
   or **Import your own…** to pick any GearSwap `.lua` instead.
4. Fanxi status shows `Loaded N sets from …/WAR.lua`.
5. Select a set to see its slot → item list. **Wear set** sends every `0x050`
   for the set in the same frame, the way GearSwap's equip burst does, so a
   precast or midcast set lands all at once instead of arriving piece by piece.
   **New set…**, **Duplicate** and **Edit set…** open the 16-slot form;
   **Save version…** writes a timestamped copy where you choose (Downloads by
   default); the first change asks for that folder once, then later edits
   auto-save new versions there.

Importing only parses the file. **Wear set** additionally needs the items to
exist in the character's bags; see [Item coverage](#item-coverage) below.

## Precast and midcast

The Gear page's **Precast · Midcast · Idle** panel gives the library to the client's host, which
then does what GearSwap does with the action packet: a weaponskill or job ability's set is worn
*before* the packet is sent, a spell's fast-cast set before the cast is timed, the midcast set
immediately after the action, and the state set when the result arrives. **Idle modes** picks the
town, field and movement sets; the zone-in packet selects town or field, and the Lock button
holds the worn set as an override. Paths it reads:

| Path | Worn |
|---|---|
| `sets.WS.<name>` | before that weaponskill's action packet (fallback `sets.precast.WS`) |
| `sets.JA.<name>` | before that job ability's action packet (fallback `sets.precast.JA`) |
| `sets.precast.FC` or `sets.precast` | before any spell's action packet |
| `sets.midcast.<skill>` | right after a spell's action packet, keyed by the spell's skill |
| any `midcast.*` or `precast.*` set | a category override: enfeebles macc/duration (Enfeebling Magic), buff potency/duration (Enhancing Magic) or helix magic |
| `engaged.tp` | on `/attack` (the **Engaged set** dropdown) |
| `idle.town`, else `idle` | disengaged, standing still, in a city (**Town set**) |
| `idle.field`, else `idle.dt`/`idle.pdt` | disengaged, standing still, anywhere else (**Field set**) |
| `idle.movement` | disengaged and moving (**Movement set**) |

The Spells panel also offers category overrides. The host groups the current job pair's spells
the same way it sends them to the page: Enfeebling Magic fills **Enfeebles · Macc** and
**Enfeebles · Duration**, Enhancing Magic fills **Buff potency** and **Buff duration**, and a
spell whose name contains `helix` fills **Helix magic**. A category set applies to every spell in
the group; a per-spell card wins over it, and the midcast default and `sets.midcast.<skill>` are
only used when neither names a set. The two faces of a pair are alternatives (one set is worn per
cast), so picking one on the page releases the other.

The plan is built from static set tables; user functions (`precast`, `midcast`, `aftercast`,
`rule`) are still not run — see the note below.

## Where the requested categories live

Paths are exactly what the launcher displays (`sets.midcast.Enfeebling Magic`,
not `sets.midcast["Enfeebling Magic"]`).

| Category | Set path | Notes |
|---|---|---|
| Max HP | `sets.idle.maxhp` | Nyame/Sakpata's + HP accessories; MNK also has `sets.JA.Chakra` |
| Max PDT | `sets.idle.pdt` | Sakpata's for WAR/PLD/DRK, Nyame for the rest, plus Defending/Gelatinous rings |
| Max MDT | `sets.idle.mdt` | Nyame + magic-damage accessories; PLD keeps Aegis equipped |
| Balanced DT | `sets.idle.dt` | job AF/relic/empyrean pieces with DT accessories |
| Balanced DT, Indomitable | `sets.idle.dt_indom` | SCH only: five Indomitable R30 pieces with the DT accessories; max PDT/MDT stay on Nyame |
| TP | `sets.engaged.tp` | job AF/relic/empyrean + Windbuffet Belt +1, Cessance/Dedition, Rajas/Petrov |
| TP, accuracy | `sets.engaged.acc` | Nyame 5/5, Combatant's Torque, Telos Earring, Rajas/Petrov |
| TP, dual wield | `sets.engaged.dw` | NIN, THF, DNC only; Suppanomimi |
| TP, damage taken | `sets.engaged.hybrid` | TP weapons/armour with DT accessories |
| Fast cast | `sets.precast.FC` | job AF/relic pieces where a generic piece is job-locked, plus Orunmila/Kishar/Rahab; SCH adds Indomitable body/legs |
| Macc (enfeebling) | `sets.midcast.Enfeebling Magic` | SCH uses Indomitable body/hands/legs; Nyame Macc + Eschan Stone + Stikini/Kishar elsewhere |
| Macc (elemental resist) | `sets.midcast.Elemental Magic Macc` | BLM, SCH only; SCH wears the full Indomitable R30 set |
| Macc (dark/divine/ninjutsu) | `sets.midcast.Dark Magic`, `Divine Magic`, `Ninjutsu` | job-dependent |
| MAB (elemental) | `sets.midcast.Elemental Magic` | SCH free nuke: Indomitable head/body/legs + Arbatel Loafers +3; Nyame MAB + Eschan Stone + Friomisi/Crematio + Metamorph/Mujin elsewhere |
| Magic burst (elemental) | `sets.midcast.Elemental Magic MB` | SCH only: Nyame C keeps Magic Burst Damage II +5–7 |
| Helix | `sets.midcast.Helix` | SCH only: Indomitable head/body/legs, Arbatel Bracers +3 and Loafers +3 |
| Cure | `sets.midcast.Healing Magic` | WHM, RDM, PLD, SCH, RUN |
| Enmity+ | `sets.enmity.up` | PLD, RUN, WAR, DRK |
| Enmity− | `sets.enmity.down` | WHM, BRD, RNG, COR |
| Weaponskills | `sets.WS.<name>` | 3–6 per job, physical/hybrid/MAB variants |
| Job abilities | `sets.JA.<name>` | 4–11 per job, with AF/relic/empyrean piece swaps |
| Pets | `sets.pet.*`, `sets.avatar.*`, `sets.automaton.*`, `sets.wyvern.*` | BST, SMN, PUP, DRG |
| Ranged | `sets.ranged.tp`/`.acc`/`.snapshot` (RNG), `.tp`/`.acc`/`.mab` (COR) | RNG, COR |
| Treasure Hunter | `sets.TH` | THF |

## Why the files look like this

Fanxi's importer is intentionally a safe subset of GearSwap
(`host/addons/lua/control.lua`, documented in `docs/control-panel.md`):

- it reads the `.lua` with `io.open` and `loadstring`, `setfenv`s it into a table
  whose fallback is `_G`, then stubs `include`, `windower`, `ashita`,
  `gearswap`, `player`, `world`, `buffactive`, `T` and `S`;
- it calls `get_sets()` if present and returns `sets` cleaned of
  functions/userdata;
- the launcher flattens the tree: **a table containing any equipment-slot key is
  treated as one set, and the walker stops descending there.**

That last rule drives the layout:

```lua
sets.idle = {}             -- empty container, so the walker keeps descending
sets.idle.pdt = { ... }    -- leaf: only slot -> item pairs
sets.idle.mdt = { ... }
```

If `sets.idle` itself had a `head = "..."` entry, Fanxi would show only
`sets.idle` and hide `PDT`/`MDT`. So every group (`sets.idle`, `sets.engaged`,
`sets.midcast`, `sets.WS`, `sets.JA`, `sets.enmity`, `sets.pet`, …) is empty and
every variant is a leaf. The files also avoid:

- `include(...)` — not evaluated by the importer;
- `S{...}` — the sandbox sets `S = {}`, so calling it would error;
- `windower.ffxi.get_*`, `player.*` at load time, `set_combine` from GearSwap
  libraries — none are stubbed;
- functions inside sets — they are dropped by the JSON cleaning pass.

A local `combine(base, extra)` helper is defined in each file, so the source is
still readable without depending on GearSwap globals.

This is a set library, not a full GearSwap state machine: there are no `rule`
tables, `precast`/`midcast`/`aftercast` handlers, or `buffactive` branches. Real
GearSwap can still load these files for its `get_sets()` table, but it will not
equip anything by itself.

## Item coverage

The names follow retail FFXI: iLvl 119 reforged artifact/relic/empyrean sets,
Nyame, Sakpata's, JSE necks and capes, Odyssey/Limbus accessories and REMA-style
weapons, plus a few older all-jobs staples used to keep the generic sets legal
for every job (`Pole Grip`, `Windbuffet Belt +1`, `Rajas Ring`, `Petrov Ring`).
Per-job access for the generic pieces was checked against the wiki's `jobs=`
field; job-specific AF/relic/empyrean pieces are restricted to their job by
design. The sources were:

- [Reforged Armor](https://www.bg-wiki.com/ffxi/Reforged_Armor) — artifact,
  relic and empyrean set families per job;
- [Nyame Armor Set](https://www.bg-wiki.com/ffxi/Nyame_Armor_Set) — all jobs,
  base Damage taken −7/−9/−7/−8/−7% and Rank 30 Paths A–D;
- [Sakpata's Armor Set](https://www.bg-wiki.com/ffxi/Sakpata%27s_Armor_Set) —
  WAR/PLD/DRK, base Damage taken −7/−10/−8/−9/−6% and the Rank 30 tank row;
- [JSE Necks](https://www.bg-wiki.com/ffxi/JSE_Necks) — the +2 neck for every
  job;
- [JSE Capes](https://www.bg-wiki.com/ffxi/JSE_Capes) — the Ambuscade cape per
  job and its Thread/Dust/Dye/Sap/Resin augment categories;
- [Unity Accessories](https://www.bg-wiki.com/ffxi/Category:Unity_Accessories) —
  the fixed Odyssey augment path for `Unmoving Collar +1`, `Odnowa Earring +1`,
  `Gelatinous Ring +1` and `Ghastly Tathlum +1`;
- [Unity Armor](https://www.bg-wiki.com/ffxi/Category:Unity_Armor) —
  `Loess Barbuta +1`'s Enmity, damage-taken and All Attr. augments;
- the set-tagging conventions and DT/FC item naming in
  [grandivory/ffxi-gearswap](https://github.com/grandivory/ffxi-gearswap) and
  [ekrividus/GearSwap](https://github.com/ekrividus/GearSwap);
- the per-item `jobs=` field on each BG-wiki page (checked for every generic
  piece used here; 0 job-access mismatches across the 22 files).

Migration `0066_gearswap_grant.sql` resolves every name used in these libraries
to a real item id and grants the missing ones to the first character's
wardrobes (the other permanent bags are a fallback; the inventory stays free).
It also fixes the server's five `Academics` spellings to `Academic's`. If the
storage-slip migration (0067) has moved old Mog Storage gear into
`char_storage`, `0068_gearswap_storage_back.sql` returns any GearSwap target to
a free wardrobe slot. On the current database all 427 names are now owned; a
client that is already online sees them after it next zones or logs back in.

Consequences:

- **Import always works** — the importer never looks items up.
- **Wear set** finds every library item that is in a bag after migration 0066 and a
  zone/relog. The control addon searches containers 0–17, so wardrobe items are
  wearable. An item you deliberately put on a storage slip with `!storage store`
  must be returned with `!storage grab <job|all>` first.
- A database that has not run 0066 only has the seed slice (WAR, NIN, SCH, BST
  and a few weapons); there, Wear set reports the missing items as before.

### Augmented JSE capes and Unity gear

Every job now has a local `capes` table with several **augmented builds** of its
JSE cape: TP, weaponskill, PDT, MDT, DT, max HP and, where relevant, fast cast,
Macc, cure, pet, ranged, enmity or waltz. The sets point at the build their
category needs instead of using one unaugmented cape everywhere. Across the 22
jobs there are **198 cape builds** (same base item name, different Ambuscade
augment arrays). The five Unity items used by the libraries have their fixed
max-rank Odyssey augments:

| Item | Augments |
|---|---|
| `Unmoving Collar +1` | `DEF+30`, `HP+200` |
| `Odnowa Earring +1` | `DEF+30`, `Damage taken-3%` |
| `Gelatinous Ring +1` | `VIT+15`, `HP+100` |
| `Ghastly Tathlum +1` | `Magic Damage +10`, `INT+5` |
| `Loess Barbuta +1` | `Enmity+10`, `Damage taken-10%`, `All Attr.+10` |

Six Reive/Incursion capes that a few sets already used (`Weard Mantle`,
`Mending Cape`, `Rhapsode's Cape`, `Lutian Cape`, `Gunslinger's Cape`,
`Evasionist's Cape`) also carry their max Refractive Crystal augments.

### Odyssey Rank 30 armor

Every **Nyame** and **Sakpata's** piece used by a set now carries its Rank 30
augment row:

- **Nyame** (all 22 jobs): **Path A** for TP/idle accuracy, **Path B** for
  physical weaponskills, and **Path C** for magic/midcast and magic
  weaponskills. The tables contain **275 Nyame piece definitions** (15 unique
  path → piece builds); the Path D pet rows are not needed by the current sets.
- **Sakpata's** (WAR/PLD/DRK): the set's single Rank 30 tank row —
  Attack, DT/ailment/cure/STP/WS/block augments as printed on the set page.
  **15 piece definitions** (5 unique pieces).

The path choice follows the set's role, so the same Nyame Helm is a different
augmented table in `sets.idle.pdt`, `sets.WS.Upheaval` and
`sets.midcast.Elemental Magic`. Like the capes, these are separate
`{name, augments}` tables sharing the base item name, not new item ids.

This is the normal GearSwap representation: an augmented item is a
`{ name = "...", augments = {...} }` table, not a separate item id. The Gear
window now marks augmented items with `*` (Nyame/Sakpata's with `R30`) and shows the selected item's full
augment list (including the R30 values) below the item pane, but **Wear set**
still matches by base name and cannot pick between two builds of the same cape
or Odyssey piece. The launcher editor also writes flattened names, so a saved
version drops the augment lists. The files are meant for real GearSwap when the
exact build matters.

## Testing checklist

1. Open a client's Gear window; the live job's library loads automatically and
   the status says `Loaded N sets` with no `GearSwap parse error` /
   `GearSwap load error`. Repeat with the **Defaults** dropdown for other jobs.
2. Open `sets.idle.maxhp`, `sets.idle.pdt`, `sets.engaged.tp` and check the
   slot list. Most sets fill 14–15 slots; H2H jobs have no `sub`, and melee
   sets leave `range` empty on purpose.
3. Open `sets.WS.<a weaponskill>` and `sets.JA.<an ability>`; confirm the
   bracket-named paths render with spaces, e.g. `sets.WS.Savage Blade`.
4. Open an augmented set (for example `sets.idle.pdt`); items with an augment
   build are marked `*`, or `R30` for Nyame/Sakpata's, and the first one is selected so the augment line shows
   the R30 values. **Wear set** still equips by base name; items deliberately on
   a storage slip are reported missing until `!storage grab <job|all>` returns
   them.
5. **Save version…**; the `.lua` should appear in the chosen folder with a
   `-YYYYMMDD-HHMMSS` suffix, and a JSON copy under
   `<data dir>/gearswap/<version>.json`. The saved file is flattened: it keeps
   item names but not the cape augment arrays.
6. Re-import the same file; the file is read-only and unchanged.

## Extending a file

Add another leaf anywhere under a container group:

```lua
    sets.idle.regen = {
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        waist = "Plat. Mog. Belt",
        back = "Cichol's Mantle",
    }
```

Keep the slot keys lowercase and use only the launcher's slots: `main`, `sub`,
`range`, `ammo`, `head`, `body`, `hands`, `legs`, `feet`, `neck`, `waist`,
`ear1`, `ear2`, `ring1`, `ring2`, `back`. (`left_ear`/`right_ear`/
`left_ring`/`right_ring` also work, but `ear1`/`ear2`/`ring1`/`ring2` match
GearSwap convention.) Do not put slot keys on a group table, or the variants
under it disappear from the import.

## Files

- `WAR.lua` … `RUN.lua` — one library per job, alphabetically by three-letter
  job code; each is standalone and can be dropped into a GearSwap data folder.
- This README.
