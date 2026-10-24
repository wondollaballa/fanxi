# Limbus Rank 30 armour

The five Limbus families at their **top tier** -- item level 119, Superior 5 --
with every **Rank 30** augment row. Each family climbs three tiers:

| Family | Base (Su4) | Middle (Su4) | Top (Su5) | Jobs |
| --- | --- | --- | --- | --- |
| Justice | Justice Armor Set | Magnificent Armor Set | **Duty Armor Set** | MNK / THF / BST / PUP / DNC |
| Hope | Hope Armor Set | Perfection Armor Set | **Revelation Armor Set** | WAR / BRD / NIN |
| Trust | Trust Armor Set | Prestige Armor Set | **Sworn Armor Set** | WHM / RDM / PLD / DRK / BLU / RUN |
| Bravery | Bravery Attire Set | Intrepid Attire Set | **Indomitable Attire Set** | BLM / SMN / SCH / GEO |
| Mercy | Mercy Armor Set | Grace Armor Set | **Clemency Armor Set** | RNG / SAM / DRG / COR |

All 25 top-tier pieces are granted at Rank 30 to characters 1 and 2
(Onedough/Twodough) by `database/migrations/0099_limbus_r30.sql`, and
migration `0104_limbus_rp30.sql` re-stamps any copy already in a bag.
The same data drives the script that writes that migration and this page:
`data/limbus_r30.json` and `tools/gen_limbus_r30.py`.

Every augment line on every piece is already at its Rank 30 value. The four
numbered columns are the four augment lines a piece carries, not a choice:
each line unlocks at a different rank, and all four are live at 30. The
item exdata also records 55,800 RP, the curve-B total for rank 30 (rank 1
costs 1,600), so the client reads the block at rank 30, not rank 0.

Each piece carries its own client augment **bundle** index. The indices
come from the client's bundle table (LandSandBoat's
`xi.data.augments.bundles`, parsed from the MNC2 data); every one was
matched to the Rank 30 row above by content. `!rp30` re-stamps the
pieces in a character's bags, and `!r30 <piece>` prints the rows.

The rows are **not only tooltips**: `FanxiService.equipped_mods()` joins each
equipped piece back to its inventory copy, `augment_stats` decodes the rank-30
block and adds the piece's four rows, so Revelation's five `"Double Attack"+7%`
style rows (34% total) reach the attack round's per-hand multi-attack roll.

## Duty Armor Set

- **Family:** Justice (Justice Armor Set -> Magnificent Armor Set -> Duty Armor Set)
- **Jobs:** MNK / THF / BST / PUP / DNC
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | Bundle | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Duty Crown | head | 24167 | 477 | Accuracy+30 Mag. Acc+30 | "Store TP"+7 | "Triple Attack"+4% | Pet: Accuracy+30 Mag. Acc+30 |
| Duty Cyclas | body | 24170 | 478 | Accuracy+30 Mag. Acc+30 | "Store TP"+8 | "Triple Attack"+5% | Pet: Accuracy+30 Mag. Acc+30 |
| Duty Gauntlets | hands | 24173 | 479 | Accuracy+30 Mag. Acc+30 | "Store TP"+6 | "Triple Attack"+3% | Pet: Accuracy+30 Mag. Acc+30 |
| Duty Flanchard | legs | 24176 | 480 | Accuracy+30 Mag. Acc+30 | "Store TP"+7 | "Triple Attack"+4% | Pet: Accuracy+30 Mag. Acc+30 |
| Duty Sollerets | feet | 24179 | 481 | Accuracy+30 Mag. Acc+30 | "Store TP"+6 | "Triple Attack"+3% | Pet: Accuracy+30 Mag. Acc+30 |

## Revelation Armor Set

- **Family:** Hope (Hope Armor Set -> Perfection Armor Set -> Revelation Armor Set)
- **Jobs:** WAR / BRD / NIN
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | Bundle | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Revelation Masque | head | 24122 | 472 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+7% | Physical Damage Limit+6% |  |
| Revelation Plate. | body | 24125 | 473 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+8% | Physical Damage Limit+7% |  |
| Revelation Gaunt. | hands | 24128 | 474 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+6% | Physical Damage Limit+5% |  |
| Revelation Brais | legs | 24131 | 475 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+7% | Physical Damage Limit+6% |  |
| Revelation Sab. | feet | 24134 | 476 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+6% | Physical Damage Limit+5% |  |

## Sworn Armor Set

- **Family:** Trust (Trust Armor Set -> Prestige Armor Set -> Sworn Armor Set)
- **Jobs:** WHM / RDM / PLD / DRK / BLU / RUN
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | Bundle | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sworn Crown | head | 24137 | 487 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+6% | "Phalanx" received +4 |  |
| Sworn Platemail | body | 24140 | 488 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+8% | "Phalanx" received +6 |  |
| Sworn Gauntlets | hands | 24143 | 489 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+7% | "Phalanx" received +5 |  |
| Sworn Brais | legs | 24146 | 490 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+6% | "Phalanx" received +4 |  |
| Sworn Sabatons | feet | 24149 | 491 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+7% | "Phalanx" received +5 |  |

## Indomitable Attire Set

- **Family:** Bravery (Bravery Attire Set -> Intrepid Attire Set -> Indomitable Attire Set)
- **Jobs:** BLM / SMN / SCH / GEO
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | Bundle | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Indom. Petasos | head | 24152 | 482 | Mag. Acc+30 | "Magic Atk. Bonus"+28 | "Blood Pact" damage+10 | Pet: Accuracy+30 Mag. Acc+30 |
| Indomitable Coat | body | 24155 | 483 | Mag. Acc+30 | "Magic Atk. Bonus"+32 | "Blood Pact" damage+12 | Pet: Accuracy+30 Mag. Acc+30 |
| Indom. Gloves | hands | 24158 | 484 | Mag. Acc+30 | "Magic Atk. Bonus"+30 | "Blood Pact" damage+11 | Pet: Accuracy+30 Mag. Acc+30 |
| Indom. Tonban | legs | 24161 | 485 | Mag. Acc+30 | "Magic Atk. Bonus"+28 | "Blood Pact" damage+10 | Pet: Accuracy+30 Mag. Acc+30 |
| Indom. Sabots | feet | 24164 | 486 | Mag. Acc+30 | "Magic Atk. Bonus"+30 | "Blood Pact" damage+11 | Pet: Accuracy+30 Mag. Acc+30 |

## Clemency Armor Set

- **Family:** Mercy (Mercy Armor Set -> Grace Armor Set -> Clemency Armor Set)
- **Jobs:** RNG / SAM / DRG / COR
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | Bundle | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Clemen. Somen | head | 24182 | 492 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-8 | "Quadruple Attack"+4% | Pet: Accuracy+30 Mag. Acc.+30 |
| Clemen. Hara. | body | 24185 | 493 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-10 | "Quadruple Attack"+6% | Pet: Accuracy+30 Mag. Acc.+30 |
| Clemency Kote | hands | 24188 | 494 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-9 | "Quadruple Attack"+5% | Pet: Accuracy+30 Mag. Acc.+30 |
| Clem. Haidate | legs | 24191 | 495 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-8 | "Quadruple Attack"+4% | Pet: Accuracy+30 Mag. Acc.+30 |
| Clem. Sune-Ate | feet | 24194 | 496 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-9 | "Quadruple Attack"+5% | Pet: Accuracy+30 Mag. Acc.+30 |

## Where they go in the libraries

The community read (a Japanese dragoon's January 2026 run-down of all five
suits, [tukaware.fc2.net](https://tukaware.fc2.net/blog-entry-547.html), and the
[FFXIAH Limbus 2025 thread](https://www.ffxiah.com/forum/topic/58447/limbus-2025/)) is:

- **Duty (Justice)** is the strongest of the five, and the one people wear outright.
  MNK/THF/DNC call it best-in-slot, BST/PUP a clear upgrade; WAR passes because
  Sakpata's already does the job. Double Attack + Subtle Blow base, Store TP /
  Triple Attack augments, and enough Accuracy/Attack to displace Odyssey and
  Malignance wherever the set is not there to cap Subtle Blow or stack DT.
- **Revelation (Hope)** is the melee-bard suit: BRD runs a 3/5 (body, legs, feet)
  and keeps Odyssey in head and hands, where Bunzi's and friends stay competitive.
  NIN takes it as a sidegrade with more Magic Evasion; WAR passes.
- **Sworn (Trust)** is PLD/RUN fast-cast and tank gear (the *Phalanx received* row
  is the draw), RDM's enspell/FC set, and DRK's hybrid head and feet once Triple
  Attack unlocks past R15. WHM/BLU skip it.
- **Indomitable (Bravery)** is SCH's raw-nuke, enfeebling and fast-cast suit.
  Every R30 piece carries Mag. Acc+42 and "Magic Atk. Bonus"+40 before the
  augment rows, plus Magic Damage+22, native Fast Cast and 2-6% Damage taken; the
  Rank 30 Mag. Acc+30 / "Magic Atk. Bonus"+28-32 rows take it to 72 M.Acc and
  68-72 MAB a piece. SCH wears head/body/legs for free nukes and helix,
  body/hands/legs for enfeebles, body/legs in fast cast, the full five in the
  elemental M.Acc set and a five-piece `sets.idle.dt_indom`. Arbatel Loafers +3
  stays in the free-nuke and helix feet ("Klimaform"+25 and Magic Burst Damage
  II +5), Arbatel Bracers +3 stays in helix, and the Enhancing Magic and Healing
  Magic sets are untouched.
- **Clemency (Mercy)** is the weakest of the five -- Enmity- sits where Store TP
  would have been -- but its head and feet beat what SAM/DRG otherwise have, its
  Physical damage limit helps multi-hit weaponskills, and the accuracy row is a
  reasonable Resolution/Torcleaver piece.

What the suits do **not** replace: Nyame Path B stays the weaponskill set (flat WSD
beats the new pieces for single-hit WS), Malignance/Sakpata's keep their Subtle Blow
slots, and an unaugmented Limbus piece loses to R30 Odyssey gear -- the multi-attack
and PDL only turn on past roughly Rank 15, which is why most melee players cherry-pick
one or two slots per job instead of building all five. The casters are the exception:
for SCH every Indomitable piece is 72 M.Acc and 22 Magic Damage, so the Elemental
Macc set takes all five, enfeebling and the damage sets take three, and fast cast two.

`tools/gen_limbus_r30.py --lua` writes a `local limbus` build table and a
`sets.Limbus` container into every library, then puts the pieces where the table
below says:

| Job | Set touched | Slots | Build |
| --- | --- | --- | --- |
| MNK | `sets.engaged.tp` | head, body, hands, legs, feet | Duty tp, R30 [2] |
| THF | `sets.engaged.tp` | head, body, hands, legs, feet | Duty tp, R30 [2] |
| THF | `sets.engaged.hybrid` | head, body, hands, legs, feet | Duty tp, R30 [2] |
| DNC | `sets.engaged.tp` | head, body, hands, legs, feet | Duty tp, R30 [2] |
| DNC | `sets.engaged.hybrid` | head, body, hands, legs, feet | Duty tp, R30 [2] |
| BST | `sets.engaged.tp` | head, body, hands, legs, feet | Duty tp, R30 [2] |
| PUP | `sets.engaged.tp` | head, body, hands, legs, feet | Duty tp, R30 [2] |
| NIN | `sets.engaged.tp` | head, body, hands, legs, feet | Revelation tp, R30 [2] |
| NIN | `sets.engaged.hybrid` | head, body, hands, legs, feet | Revelation tp, R30 [2] |
| BRD | `sets.engaged.tp` | body, legs, feet | Revelation tp, R30 [2] |
| PLD | `sets.precast.FC` | head, body, hands, legs, feet | Sworn phalanx, R30 [3] |
| RUN | `sets.precast.FC` | head, body, hands, legs, feet | Sworn phalanx, R30 [3] |
| RDM | `sets.precast.FC` | head, body, hands, legs, feet | Sworn ta, R30 [2] |
| SCH | `sets.midcast.Elemental Magic` | head, body, legs | Indomitable cast, R30 [2] |
| SCH | `sets.midcast.Elemental Magic Macc` | head, body, hands, legs, feet | Indomitable cast, R30 [2] |
| SCH | `sets.midcast.Helix` | head, body, legs | Indomitable cast, R30 [2] |
| SCH | `sets.midcast.Enfeebling Magic` | body, hands, legs | Indomitable cast, R30 [2] |
| SCH | `sets.precast.FC` | body, legs | Indomitable cast, R30 [2] |
| SCH | `sets.idle.dt_indom` | head, body, hands, legs, feet | Indomitable cast, R30 [2] |
| DRK | `sets.engaged.tp` | head, feet | Sworn ta, R30 [2] |
| DRK | `sets.engaged.hybrid` | head, feet | Sworn ta, R30 [2] |
| DRK | `sets.WS.Resolution` | head, feet | Sworn acc, R30 [1] |
| DRK | `sets.WS.Torcleaver` | head, feet | Sworn acc, R30 [1] |
| SAM | `sets.engaged.tp` | head, feet | Clemency tp, R30 [3] |
| DRG | `sets.engaged.tp` | head, feet | Clemency tp, R30 [3] |

On SCH the Magic Burst variant (`sets.midcast.Elemental Magic MB`) deliberately
stays on Nyame Path C for its Magic Burst Damage II rows, and the max PDT/MDT
idle sets stay on Nyame because its per-piece Damage taken (7-9%) is higher than
Indomitable's (2-6%). The new `sets.idle.dt_indom` is the balanced DT build.

Jobs not listed keep their defaults and only gain the `sets.Limbus` container;
the five-piece copy in every variant carries the same augment choice so a set can
be worn as a unit.

## Notes

- Item ids come from each item page's ffxidb link on BG Wiki; the names are the
  in-game ones, which are abbreviated where the 15-character limit bites
  (`Revelation Plate.`, `Clemen. Hara.`).
- The base stat lines are copied verbatim and turned into `item_mods` by the
  generator. Pet, avatar and wyvern rows are recorded here but not stored: the
  engine has no pet sheet yet, so nothing would read them.
- The 24-byte exdata block is rank 30 / tier 3 / 55,800 RP (curve B) with
  the piece's own augment bundle index, so the client prints the four rows
  on the tooltip. `!r30 <piece>` still prints them in chat, and `!rp30`
  re-stamps every Limbus piece a character is carrying.
- The bundle indices sit in the client table as 472-496: 477-481 Duty,
  472-476 Revelation, 487-491 Sworn, 482-486 Indomitable and 492-496
  Clemency. Bundles 458-471 are other Su5 entries this dataset does not grant.
- The pieces carry the client's own armour models: Revelation MId 513, Sworn
  514, Indomitable 515, Duty 516 and Clemency 517.  The raw grap model is the
  slot base (0x1000 head, 0x2000 body, 0x3000 hands, 0x4000 legs, 0x5000 feet)
  plus that MId.  The values come from xi-tools' `mv/lists/characters.json`;
  migration 107 writes them, and `tools/item_models.json` keeps them for new
  grants and cloned characters.
- Sources: https://www.bg-wiki.com/ffxi/Justice_Armor_Set, https://www.bg-wiki.com/ffxi/Hope_Armor_Set, https://www.bg-wiki.com/ffxi/Trust_Armor_Set, https://www.bg-wiki.com/ffxi/Bravery_Attire_Set, https://www.bg-wiki.com/ffxi/Mercy_Armor_Set

## Client data

These items only exist in the client's own item table from the 2026 updates.
A 2025-07-03 client (client version `30250704_0`, the build `meta/builds.json`
labels `2025-07-03`) has ids 24122-24194 unused, so it draws the null record --
no name, "All jobs", `Lv.127` -- no matter what the server sends. Check a folder
with `tools/newbuild.py identify --game <folder>`; `tools/prepare.py` only accepts
a build `meta/builds.json` lists. The build this page was checked against is the
2026-10-05 install, client version `30261006_0`, which `meta/builds.json` lists.
