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
(Onedough/Twodough) by `database/migrations/0099_limbus_r30.sql`.
The same data drives the script that writes that migration and this page:
`data/limbus_r30.json` and `tools/gen_limbus_r30.py`.

Augments are chosen at the Limbus furnaces with a *Jewel of Des.*; a piece
picks **one** of the four numbered rows below, and Rank 30 is the maximum
rank for each.

## Duty Armor Set

- **Family:** Justice (Justice Armor Set -> Magnificent Armor Set -> Duty Armor Set)
- **Jobs:** MNK / THF / BST / PUP / DNC
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- |
| Duty Crown | head | 24167 | Accuracy+30 Mag. Acc+30 | "Store TP"+7 | "Triple Attack"+4% | Pet: Accuracy+30 Mag. Acc+30 |
| Duty Cyclas | body | 24170 | Accuracy+30 Mag. Acc+30 | "Store TP"+8 | "Triple Attack"+5% | Pet: Accuracy+30 Mag. Acc+30 |
| Duty Gauntlets | hands | 24173 | Accuracy+30 Mag. Acc+30 | "Store TP"+6 | "Triple Attack"+3% | Pet: Accuracy+30 Mag. Acc+30 |
| Duty Flanchard | legs | 24176 | Accuracy+30 Mag. Acc+30 | "Store TP"+7 | "Triple Attack"+4% | Pet: Accuracy+30 Mag. Acc+30 |
| Duty Sollerets | feet | 24179 | Accuracy+30 Mag. Acc+30 | "Store TP"+6 | "Triple Attack"+3% | Pet: Accuracy+30 Mag. Acc+30 |

## Revelation Armor Set

- **Family:** Hope (Hope Armor Set -> Perfection Armor Set -> Revelation Armor Set)
- **Jobs:** WAR / BRD / NIN
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- |
| Revelation Masque | head | 24122 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+7% | Physical Damage Limit+6% |  |
| Revelation Plate. | body | 24125 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+8% | Physical Damage Limit+7% |  |
| Revelation Gaunt. | hands | 24128 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+6% | Physical Damage Limit+5% |  |
| Revelation Brais | legs | 24131 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+7% | Physical Damage Limit+6% |  |
| Revelation Sab. | feet | 24134 | Accuracy+30 Ranged Accuracy+30 Mag. Acc+30 | "Double Attack"+6% | Physical Damage Limit+5% |  |

## Sworn Armor Set

- **Family:** Trust (Trust Armor Set -> Prestige Armor Set -> Sworn Armor Set)
- **Jobs:** WHM / RDM / PLD / DRK / BLU / RUN
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- |
| Sworn Crown | head | 24137 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+6% | "Phalanx" received +4 |  |
| Sworn Platemail | body | 24140 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+8% | "Phalanx" received +6 |  |
| Sworn Gauntlets | hands | 24143 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+7% | "Phalanx" received +5 |  |
| Sworn Brais | legs | 24146 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+6% | "Phalanx" received +4 |  |
| Sworn Sabatons | feet | 24149 | Accuracy+30 Mag. Acc+30 | "Triple Attack"+7% | "Phalanx" received +5 |  |

## Indomitable Attire Set

- **Family:** Bravery (Bravery Attire Set -> Intrepid Attire Set -> Indomitable Attire Set)
- **Jobs:** BLM / SMN / SCH / GEO
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- |
| Indom. Petasos | head | 24152 | Mag. Acc+30 | "Magic Atk. Bonus"+28 | "Blood Pact" damage+10 | Pet: Accuracy+30 Mag. Acc+30 |
| Indomitable Coat | body | 24155 | Mag. Acc+30 | "Magic Atk. Bonus"+32 | "Blood Pact" damage+12 | Pet: Accuracy+30 Mag. Acc+30 |
| Indom. Gloves | hands | 24158 | Mag. Acc+30 | "Magic Atk. Bonus"+30 | "Blood Pact" damage+11 | Pet: Accuracy+30 Mag. Acc+30 |
| Indom. Tonban | legs | 24161 | Mag. Acc+30 | "Magic Atk. Bonus"+28 | "Blood Pact" damage+10 | Pet: Accuracy+30 Mag. Acc+30 |
| Indom. Sabots | feet | 24164 | Mag. Acc+30 | "Magic Atk. Bonus"+30 | "Blood Pact" damage+11 | Pet: Accuracy+30 Mag. Acc+30 |

## Clemency Armor Set

- **Family:** Mercy (Mercy Armor Set -> Grace Armor Set -> Clemency Armor Set)
- **Jobs:** RNG / SAM / DRG / COR
- **Item level:** 119, Superior 5

| Piece | Slot | Item ID | [1] | [2] | [3] | [4] |
| --- | --- | --- | --- | --- | --- | --- |
| Clemen. Somen | head | 24182 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-8 | "Quadruple Attack"+4% | Pet: Accuracy+30 Mag. Acc.+30 |
| Clemen. Hara. | body | 24185 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-10 | "Quadruple Attack"+6% | Pet: Accuracy+30 Mag. Acc.+30 |
| Clemency Kote | hands | 24188 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-9 | "Quadruple Attack"+5% | Pet: Accuracy+30 Mag. Acc.+30 |
| Clem. Haidate | legs | 24191 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-8 | "Quadruple Attack"+4% | Pet: Accuracy+30 Mag. Acc.+30 |
| Clem. Sune-Ate | feet | 24194 | Accuracy+30 Rng. Acc.+30 Mag. Acc.+30 | Enmity-9 | "Quadruple Attack"+5% | Pet: Accuracy+30 Mag. Acc.+30 |

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
- **Indomitable (Bravery)** is rated below the casters' AF/relic pieces in every
  slot; it ships here as a container, not as a default.
- **Clemency (Mercy)** is the weakest of the five -- Enmity- sits where Store TP
  would have been -- but its head and feet beat what SAM/DRG otherwise have, its
  Physical damage limit helps multi-hit weaponskills, and the accuracy row is a
  reasonable Resolution/Torcleaver piece.

What the suits do **not** replace: Nyame Path B stays the weaponskill set (flat WSD
beats the new pieces for single-hit WS), Malignance/Sakpata's keep their Subtle Blow
slots, and an unaugmented Limbus piece loses to R30 Odyssey gear -- the multi-attack
and PDL only turn on past roughly Rank 15, which is why most players cherry-pick
one or two slots per job instead of building all five.

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
| DRK | `sets.engaged.tp` | head, feet | Sworn ta, R30 [2] |
| DRK | `sets.engaged.hybrid` | head, feet | Sworn ta, R30 [2] |
| DRK | `sets.WS.Resolution` | head, feet | Sworn acc, R30 [1] |
| DRK | `sets.WS.Torcleaver` | head, feet | Sworn acc, R30 [1] |
| SAM | `sets.engaged.tp` | head, feet | Clemency tp, R30 [3] |
| DRG | `sets.engaged.tp` | head, feet | Clemency tp, R30 [3] |

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
- The 24-byte exdata block says rank 30 / tier 3, but its augment bundle index
  is still unknown (LandSandBoat has no Limbus augment table), so the client
  cannot print the four rows on a tooltip. `!r30 <piece>` prints them in game,
  the same way `!r30` covers Odyssey.
- Sources: https://www.bg-wiki.com/ffxi/Justice_Armor_Set, https://www.bg-wiki.com/ffxi/Hope_Armor_Set, https://www.bg-wiki.com/ffxi/Trust_Armor_Set, https://www.bg-wiki.com/ffxi/Bravery_Attire_Set, https://www.bg-wiki.com/ffxi/Mercy_Armor_Set

## Client data

These items only exist in the client's own item table from the 2026 updates.
A 2025-07-03 client (client version `30250704_0`, the build `meta/builds.json`
labels `2025-07-03`) has ids 24122-24194 unused, so it draws the null record --
no name, "All jobs", `Lv.127` -- no matter what the server sends. Check a folder
with `tools/newbuild.py identify --game <folder>`; `tools/prepare.py` only accepts
a build `meta/builds.json` lists. The 2026-10-05 install used to check this was
client version `30261006_0` and is not in that list yet.
