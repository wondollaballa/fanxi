# Limbus Rank 30 weapons

The Limbus furnaces (Temenos and Apollyon) build the **Telopanos** weapons
from the **Telognophos** base weapon: one **Auge Scintistone** plus units from
either zone lifts it to the Superior 5 form, and the same trade adds the
weapon's **Rank 30** rows. There are sixteen pieces -- one for every weapon
skill, the shield and the grip:

| Weapon | Skill | Slot | Jobs | Item | Bundle |
| --- | --- | --- | --- | --- | --- |
| Telopanos Grip | Grips | sub | All jobs | 18800 | 511 |
| Telopanos Knuckles | Hand-to-Hand | main | MNK / PUP | 21549 | 497 |
| Telopanos Knife | Dagger | main | RDM / THF / BRD / DNC | 21599 | 498 |
| Telopanos Axe | Axe | main | BST | 21738 | 502 |
| Telopanos Chopper | Great Axe | main | WAR | 21795 | 503 |
| Telopanos Scythe | Scythe | main | DRK | 21848 | 504 |
| Telopanos Halberd | Polearm | main | DRG | 21899 | 505 |
| Telopanos Shin. | Katana | main | NIN | 21942 | 506 |
| Telopanos Katana | Great Katana | main | SAM | 21948 | 507 |
| Telopanos Bow | Archery | range | RNG | 22176 | 510 |
| Telopanos Sword | Sword | main | WAR / PLD / DRK | 22182 | 499 |
| Telopanos Saber | Sword | main | RDM / BLU / COR | 22188 | 500 |
| Telopanos Maul | Club | main | WHM / GEO | 22225 | 508 |
| Telopanos Staff | Staff | main | BLM / SMN / SCH | 22231 | 509 |
| Telopanos Claymore | Great Sword | main | WAR / PLD / DRK / RUN | 22237 | 501 |
| Telopanos Shield | Shield | sub | PLD | 26503 | 512 |

Every piece carries its own client augment **bundle** index. The indices are
the client's own augment table (the 512-entry table the augment block names,
the same one the five Limbus suits use at 472-496); 497-512 are this family,
and each was matched to the rows below by its Rank 30 values.

The Data page's **RP** card lists every one of them that a character is
carrying, with the same one-click **Cap path** the suits and Odyssey gear get:
the click writes rank 30 / tier 3 / 55,800 RP (RP curve B) and the piece's bundle
into the item's 24-byte exdata, so the client prints the rows on the tooltip.
`//r30 telopanos <part>` prints the same rows in chat and `//rp30` re-stamps
every Limbus piece in the bags, weapons included.

## Rank 30 rows

### Telopanos Grip

- **Item:** 18800, **slot:** sub, **bundle:** 511
- **Jobs:** All jobs
- **Stats:** Accuracy+31 Ranged Accuracy+31 Magic Accuracy+31 Haste+4% Physical damage limit +9% Damage taken -4%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Attack+30 | Magic Damage+20 | HP+100 |  |

### Telopanos Knuckles

- **Item:** 21549, **slot:** main, **bundle:** 497
- **Model:** 951 -- derived — H2H opens the block (skill order)
- **Jobs:** MNK / PUP
- **Stats:** DMG:173 Delay:91 Accuracy+32 Magic Accuracy+32 Hand-to-Hand skill +255 Guard skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%
- **Pet line (client text, not stored):** Automaton: Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Lv.+2

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+19 | Attack+100 | HP+300 | Pet dmg+5% |

### Telopanos Knife

- **Item:** 21599, **slot:** main, **bundle:** 498
- **Model:** 957 -- derived — Dagger follows H2H
- **Jobs:** RDM / THF / BRD / DNC
- **Stats:** DMG:128 Delay:189 Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Dagger skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+14 | Attack+50 | HP+150 |  |

### Telopanos Axe

- **Item:** 21738, **slot:** main, **bundle:** 502
- **Model:** 960 -- derived — Axe in skill order
- **Jobs:** BST
- **Stats:** DMG:181 Delay:268 Accuracy+32 Magic Accuracy+32 Axe skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%
- **Pet line (client text, not stored):** Main hand: Pet: Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Lv.+2

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+20 | Attack+50 | HP+150 | Pet dmg+5% |

### Telopanos Chopper

- **Item:** 21795, **slot:** main, **bundle:** 503
- **Model:** 961 -- derived — G.Axe two-hand, main-only
- **Jobs:** WAR
- **Stats:** DMG:330 Delay:489 Accuracy+32 Magic Accuracy+32 Great Axe skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+37 | Attack+70 | HP+200 |  |

### Telopanos Scythe

- **Item:** 21848, **slot:** main, **bundle:** 504
- **Model:** 962 -- confirmed in game (Onedough)
- **Jobs:** DRK
- **Stats:** DMG:345 Delay:513 Accuracy+32 Magic Accuracy+32 Scythe skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+39 | Attack+70 | HP+200 |  |

### Telopanos Halberd

- **Item:** 21899, **slot:** main, **bundle:** 505
- **Model:** 963 -- derived — Polearm follows Scythe in the skill order
- **Jobs:** DRG
- **Stats:** DMG:259 Delay:385 Accuracy+32 Magic Accuracy+32 Polearm skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%
- **Pet line (client text, not stored):** Wyvern: Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Lv.+2

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+29 | Attack+70 | HP+200 |  |

### Telopanos Shin.

- **Item:** 21942, **slot:** main, **bundle:** 506
- **Model:** 964 -- derived — Katana one-hand, main+sub
- **Jobs:** NIN
- **Stats:** DMG:149 Delay:222 Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Katana skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+17 | Attack+50 Ranged Attack+50 | HP+150 |  |

### Telopanos Katana

- **Item:** 21948, **slot:** main, **bundle:** 507
- **Model:** 965 -- derived — G.Katana two-hand, main-only
- **Jobs:** SAM
- **Stats:** DMG:294 Delay:435 Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Great Katana skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+33 | Attack+70 | HP+200 |  |

### Telopanos Bow

- **Item:** 22176, **slot:** range, **bundle:** 510
- **Model:** 156 -- derived — the only new ranged model in ROM/386
- **Jobs:** RNG
- **Stats:** DMG:316 Delay:582 Ranged Accuracy+32 Magic Accuracy+32 Archery skill +255 Snapshot +5 Physical damage limit +10% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+35 | Ranged Attack+100 | HP+300 |  |

### Telopanos Sword

- **Item:** 22182, **slot:** main, **bundle:** 499
- **Model:** 958 -- confirmed in game (Onedough)
- **Jobs:** WAR / PLD / DRK
- **Stats:** DMG:173 Delay:258 Accuracy+32 Magic Accuracy+32 Sword skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+19 | Attack+50 | HP+150 |  |

### Telopanos Saber

- **Item:** 22188, **slot:** main, **bundle:** 500
- **Model:** 968 -- tentative — compare with the Sword (958); try 956, 955, 954, 953, 952
- **Jobs:** RDM / BLU / COR
- **Stats:** DMG:157 Delay:233 Accuracy+32 Magic Accuracy+32 Magic Attack Bonus +52 Magic damage +250 Sword skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +5% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+18 | Magic Damage+25 | HP+150 |  |

### Telopanos Maul

- **Item:** 22225, **slot:** main, **bundle:** 508
- **Model:** 966 -- derived — Club one-hand, main+sub
- **Jobs:** WHM / GEO
- **Stats:** DMG:223 Delay:334 Accuracy+32 Magic Accuracy+32 Magic Attack Bonus +52 Magic damage +250 Club skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +5% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+25 | Magic Damage+25 | HP+150 |  |

### Telopanos Staff

- **Item:** 22231, **slot:** main, **bundle:** 509
- **Model:** 967 -- derived — Staff closes the block
- **Jobs:** BLM / SMN / SCH
- **Stats:** DMG:240 Delay:356 Accuracy+32 Magic Accuracy+32 Magic Attack Bonus +72 Magic damage +312 Staff skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +5% Damage taken -5%
- **Pet line (client text, not stored):** Avatar: Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Lv.+2

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+27 | Magic Damage+30 | HP+200 | "Blood Pact" Damage+10 |

### Telopanos Claymore

- **Item:** 22237, **slot:** main, **bundle:** 501
- **Model:** 959 -- confirmed in game (Onedough)
- **Jobs:** WAR / PLD / DRK / RUN
- **Stats:** DMG:314 Delay:466 Accuracy+32 Magic Accuracy+32 Great Sword skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Damage+35 | Attack+70 | HP+200 |  |

### Telopanos Shield

- **Item:** 26503, **slot:** sub, **bundle:** 512
- **Model:** 680 -- tentative — try 681 (large) or 1181 (buckler) if wrong
- **Jobs:** PLD
- **Stats:** DEF:152 Accuracy+32 Magic Accuracy+32 Shield skill +121 Haste+5% Damage taken II -5%

| [1] | [2] | [3] | [4] |
| --- | --- | --- | --- |
| Attack+50 | HP+150 | VIT+30 |  |

## Grap models

The 2026 wave shipped without a **grap model** in any server data: LandSandBoat
marks each row `TODO: MId`, and the client's own item records carry no model
(the model is server-side data that private servers curate by hand).  A copy
equipped with model 0 was simply not drawn -- the server log said
`equipped Telopanos Sword in slot 0 with no grap model: it will not show`.

The ids come from the client's own 2026 model block, identified in game.  The
Claymore confirmed **959** and the Sword **958**; that fixes the block's
weapon-group order (Dagger, Sword, G.Sword, Axe, G.Axe, Polearm, Scythe, Katana,
G.Katana, Club, Staff), and every derived id matches its weapon's handedness --
the client gives one-handed models a main and a sub DAT, two-handed models a
main DAT only.  H2H, Archery and the shield sit in their own groups.

| Weapon | Group | Model | Note |
| --- | --- | --- | --- |
| Telopanos Grip | Grips | none (grips are invisible) | - |
| Telopanos Knuckles | Hand-to-Hand | 951 | derived — H2H opens the block (skill order) |
| Telopanos Knife | Dagger | 957 | derived — Dagger follows H2H |
| Telopanos Axe | Axe | 960 | derived — Axe in skill order |
| Telopanos Chopper | Great Axe | 961 | derived — G.Axe two-hand, main-only |
| Telopanos Scythe | Scythe | 962 | confirmed in game (Onedough) |
| Telopanos Halberd | Polearm | 963 | derived — Polearm follows Scythe in the skill order |
| Telopanos Shin. | Katana | 964 | derived — Katana one-hand, main+sub |
| Telopanos Katana | Great Katana | 965 | derived — G.Katana two-hand, main-only |
| Telopanos Bow | Archery | 156 | derived — the only new ranged model in ROM/386 |
| Telopanos Sword | Sword | 958 | confirmed in game (Onedough) |
| Telopanos Saber | Sword | 968 | tentative — compare with the Sword (958); try 956, 955, 954, 953, 952 |
| Telopanos Maul | Club | 966 | derived — Club one-hand, main+sub |
| Telopanos Staff | Staff | 967 | derived — Staff closes the block |
| Telopanos Claymore | Great Sword | 959 | confirmed in game (Onedough) |
| Telopanos Shield | Shield | 680 | tentative — try 681 (large) or 1181 (buckler) if wrong |

`//model <item> <id>` sets one copy's look in game; editing the dataset's
`model` field and running the generator bakes a better id into the migration.
The grip keeps model 0 on purpose: a grip is never drawn.

## Where the data comes from

- Item ids, slots, jobs and the stat lines are BG Wiki's item pages; the
  base modifiers come from the same parser as the reforged gear
  (`tools/import_reforged_item_data.py`), and the client skill ids are the
  ones the 0x062 skill menu uses.
- `data/limbus_weapons_r30.json` and `tools/gen_limbus_weapons.py` are the
  single source for this page, the migration and the server's lookup, so the
  card, `//r30` and the combat path cannot drift apart.
- The `Damage+n` row raises the weapon's damage rating, not a modifier:
  `augment_stats.weapon_damage` adds it to the `item_weapon.dmg` the attack
  round and the weaponskill formula read.
- `Magic Accuracy skill +255` has no client skill id; the client prints it,
  and neither the server's skill table nor this dataset stores it (the same
  gap every iLvl 119 weapon has today).
- `Pet dmg+5%` and `"Blood Pact" Damage+10` are recorded and shown on the
  card; the engine has no pet sheet to apply them to.
- The items have no client grap model yet: LandSandBoat marks their
  `item_equipment` rows `TODO: MId`, so an equipped copy is invisible until
  a model is set (`//model <item> <model id>`).  The icon, the
  stats and the augment tooltip do not depend on it.
- Retouching the rows: edit the JSON, then run
  `python3 tools/gen_limbus_weapons.py --all`.

Sources: https://www.bg-wiki.com/ffxi/Telopanos_Knuckles, https://www.bg-wiki.com/ffxi/Telopanos_Knife, https://www.bg-wiki.com/ffxi/Telopanos_Axe, https://www.bg-wiki.com/ffxi/Telopanos_Chopper, https://www.bg-wiki.com/ffxi/Telopanos_Scythe, https://www.bg-wiki.com/ffxi/Telopanos_Halberd, https://www.bg-wiki.com/ffxi/Telopanos_Shin., https://www.bg-wiki.com/ffxi/Telopanos_Katana, https://www.bg-wiki.com/ffxi/Telopanos_Bow, https://www.bg-wiki.com/ffxi/Telopanos_Sword, https://www.bg-wiki.com/ffxi/Telopanos_Saber, https://www.bg-wiki.com/ffxi/Telopanos_Maul, https://www.bg-wiki.com/ffxi/Telopanos_Staff, https://www.bg-wiki.com/ffxi/Telopanos_Claymore, https://www.bg-wiki.com/ffxi/Telopanos_Shield, https://www.bg-wiki.com/ffxi/Telopanos_Grip

## Client data

The items exist in the client's item table from the 2026 updates; the build
this page was checked against is the 2026-10-05 install (client version
`30261006_0`), whose `ROM/118/114.DAT` carries augment bundles 1-512.
`//r30 telopanos` works on any build, but the client only prints the tooltip
rows when its own augment table has the bundle.
