# Reive and Incursion JSE cape augments

The 22 level-99 job capes below drop from Colonization Reives, Lair Reives,
Wildskeeper Reives and Incursion coffers in Marjami Ravine, Yorcia Weald,
Kamihr Drifts and Ra'Kaznar.  Augmented copies also come from Incursion.
[Detrovio](https://www.bg-wiki.com/ffxi/Detrovio) at the Inventors' Coalition in
Western Adoulin (J-10) takes one
[Refractive Crystal](https://www.bg-wiki.com/ffxi/Refractive_Crystal) and a
Bayld fee for one augment roll; Makel-Pakel at the Celennia Memorial Library
removes the augments again for free.

Retail rolls several of the cape's four rows in one trade, each at its own
random potency, so a copy can carry all four at once.  The launcher's Data page
writes the rows and values the player picks instead, the same way the Ambuscade
and Skirmish cards write their maxima.

## Block format

A cape still carries the client's standard 24-byte augment block, with the four
rows in slots 0-3 and the unused fifth slot normally zero (the editor preserves
a word it finds there):

```
02 03  <row 0> <row 1> <row 2> <row 3>  00 00  00 * 12
```

Each row is one little-endian `id:11 | value:5` word.  The client prints
`(value + offset) * multiplier` for the id, so `Accuracy+7` is id 0x017
(offset 1) with word value 6, and `Enmity-10` is id 0x028 (multiplier -1,
offset 1) with word value 9.  A reduction keeps its magnitude in the value
field; the id carries the minus.  `Pet: TP Bonus` is the one row with a step:
id 0x07A is offset 1 and 20 points per stage, so `+500` stores 24.  BG Wiki's
`STR/DEX` row is one combined word (id 0x226), not two slots.

The ids are the client packet-augment ids the rest of `capes.TABLE` and
`augment_stats` already use.  A copy therefore shows the same line in the
client tooltip, the launcher item card and the stat sheet; the engine applies
the modifiers it models (STR, Accuracy, Store TP, damage taken, ...).  Rows the
engine has no pool for yet (Blood Pact recast, Helix/Meditate duration, Reverse
Flourish, Embolden) are listed in `augment_stats.UNMODELLED` and remain
client-visible.

## Rows

`server/fanxi_server/game/reive.py` is the source of truth; the launcher's
**Data → Augments → Reive & Incursion capes** card reads its rows from it.  A
negative range means the stronger value is the more negative one.

### WAR — Mauler's Mantle (item 28617)

| Row | Range | Client text at best |
| --- | --- | --- |
| STR | 1..5 | `STR+5` |
| DEX | 1..5 | `DEX+5` |
| Accuracy | 1..7 | `Accuracy+7` |
| Critical Hit Damage | 1..3 | `Crit. hit damage+3%` |

### MNK — Anchoret's Mantle (item 28618)

| Row | Range | Client text at best |
| --- | --- | --- |
| STR | 1..5 | `STR+5` |
| DEX | 1..5 | `DEX+5` |
| Counter | 1..5 | `"Counter"+5` |
| Subtle Blow | 1..5 | `Subtle Blow+5` |

### WHM — Mending Cape (item 28619)

| Row | Range | Client text at best |
| --- | --- | --- |
| Magic Accuracy | 1..10 | `Mag. Acc.+10` |
| Healing Magic Skill | 1..10 | `Healing magic skill+10` |
| Enhancing Magic Skill | 1..10 | `Enhancing magic skill+10` |
| Cure Potency | 1..5 | `"Cure Potency"+5%` |

### BLM — Bane Cape (item 28620)

| Row | Range | Client text at best |
| --- | --- | --- |
| Magic Atk. Bonus | 1..5 | `Mag.Atk.Bns.+5` |
| Elemental Magic Skill | 1..10 | `Elemental magic skill+10` |
| Dark Magic Skill | 1..10 | `Dark magic skill+10` |
| Fast Cast | 1..5 | `Fast Cast+5` |

### RDM — Ghostfyre Cape (item 28621)

| Row | Range | Client text at best |
| --- | --- | --- |
| Magic Accuracy | 1..10 | `Mag. Acc.+10` |
| Enfeebling Magic Skill | 1..10 | `Enfeebling magic skill+10` |
| Enhancing Magic Skill | 1..10 | `Enhancing magic skill+10` |
| Enhancing Magic Duration | 10..20 | `Enh. Mag. eff. dur.+20%` |

### THF — Canny Cape (item 28622)

| Row | Range | Client text at best |
| --- | --- | --- |
| DEX | 1..5 | `DEX+5` |
| AGI | 1..5 | `AGI+5` |
| Dual Wield | 1..5 | `Dual Wield+5` |
| Critical Hit Damage | 1..3 | `Crit. hit damage+3%` |

### PLD — Weard Mantle (item 28623)

| Row | Range | Client text at best |
| --- | --- | --- |
| DEX | 1..5 | `DEX+5` |
| VIT | 1..5 | `VIT+5` |
| Enmity | 1..7 | `Enmity+7` |
| Phalanx | 1..5 | `Phalanx+5` |

### DRK — Niht Mantle (item 28624)

| Row | Range | Client text at best |
| --- | --- | --- |
| Attack | 5..15 | `Attack+15` |
| Dark Magic Skill | 1..10 | `Dark magic skill+10` |
| Drain/Aspir Potency | 10..25 | `"Drain" and "Aspir" potency+25` |
| Weaponskill Damage | 1..5 | `Weapon skill damage+5%` |

### BST — Pastoralist's Mantle (item 28625)

| Row | Range | Client text at best |
| --- | --- | --- |
| STR/DEX | 1..5 | `STR+5 DEX+5` |
| Accuracy | 1..5 | `Accuracy+5` |
| Pet: Accuracy/Ranged Accuracy | 5..20 | `Pet: Accuracy+20 Pet: Rng. Acc.+20` |
| Pet: Damage Taken | -5..-1 | `Pet: Damage taken-5%` |

### BRD — Rhapsode's Cape (item 28626)

| Row | Range | Client text at best |
| --- | --- | --- |
| HP | 18..30 | `HP+30` |
| Magic Accuracy | 1..7 | `Mag. Acc.+7` |
| Enmity | -10..-1 | `Enmity-10` |
| Damage Taken | -3..-1 | `Damage taken-3%` |

### RNG — Lutian Cape (item 28627)

| Row | Range | Client text at best |
| --- | --- | --- |
| STR | 1..5 | `STR+5` |
| AGI | 1..5 | `AGI+5` |
| Store TP | 1..3 | `"Store TP"+3` |
| Snapshot | 1..3 | `"Snapshot"+3` |

### SAM — Takaha Mantle (item 28628)

| Row | Range | Client text at best |
| --- | --- | --- |
| STR | 1..5 | `STR+5` |
| Store TP | 1..3 | `"Store TP"+3` |
| Zanshin | 1..5 | `Zanshin+5` |
| Meditate Duration | 4..8 | `Meditate effect duration+8` |

### NIN — Yokaze Mantle (item 28629)

| Row | Range | Client text at best |
| --- | --- | --- |
| STR | 1..5 | `STR+5` |
| DEX | 1..5 | `DEX+5` |
| Skillchain Damage | 1..5 | `Skillchain dmg.+5%` |
| Weaponskill Damage | 1..5 | `Weapon skill damage+5%` |

### DRG — Updraft Mantle (item 28630)

| Row | Range | Client text at best |
| --- | --- | --- |
| STR | 1..5 | `STR+5` |
| Weaponskill Damage | 1..5 | `Weapon skill damage+5%` |
| Pet: Damage Taken | -5..-1 | `Pet: Damage taken-5%` |
| Breath | 1..10 | `Pet: Breath+10` |

### SMN — Conveyance Cape (item 28631)

| Row | Range | Client text at best |
| --- | --- | --- |
| Summoning Magic Skill | 1..5 | `Summoning magic skill+5` |
| Blood Pact Damage | 1..5 | `Blood Pact Dmg.+5` |
| Blood Pact Recast II | -3..-1 | `Blood Pact recast time II-3` |
| Pet: Enmity | 5..15 | `Pet: Enmity+15` |

### BLU — Cornflower Cape (item 28632)

| Row | Range | Client text at best |
| --- | --- | --- |
| MP | 15..30 | `MP+30` |
| DEX | 1..5 | `DEX+5` |
| Accuracy | 1..7 | `Accuracy+7` |
| Blue Magic Skill | 1..10 | `Blue Magic skill+10` |

### COR — Gunslinger's Cape (item 28633)

| Row | Range | Client text at best |
| --- | --- | --- |
| Magic Atk. Bonus | 1..5 | `Mag.Atk.Bns.+5` |
| Enmity | -5..-1 | `Enmity-5` |
| Phantom Roll Delay | -5..-1 | `"Phantom Roll" ability delay-5` |
| Weaponskill Damage | 1..5 | `Weapon skill damage+5%` |

### PUP — Dispersal Mantle (item 28634)

| Row | Range | Client text at best |
| --- | --- | --- |
| STR | 1..5 | `STR+5` |
| DEX | 1..5 | `DEX+5` |
| Martial Arts | 10..20 | `Martial Arts+20` |
| Pet: TP Bonus | 100..500 | `Pet: TP Bonus+500` |

### DNC — Toetapper Mantle (item 28635)

| Row | Range | Client text at best |
| --- | --- | --- |
| Store TP | 1..5 | `"Store TP"+5` |
| Dual Wield | 1..5 | `Dual Wield+5` |
| Reverse Flourish | 10..30 | `Reverse Flourish+30` |
| Weaponskill Damage | 1..5 | `Weapon skill damage+5%` |

### SCH — Bookworm's Cape (item 28636)

| Row | Range | Client text at best |
| --- | --- | --- |
| INT | 1..5 | `INT+5` |
| MND | 1..5 | `MND+5` |
| Helix Duration | 10..20 | `Helix effect duration+20` |
| Regen Potency | 1..10 | `"Regen" potency+10` |

### GEO — Lifestream Cape (item 28637)

| Row | Range | Client text at best |
| --- | --- | --- |
| Geomancy Skill | 1..10 | `Geomancy skill+10` |
| Indi Duration | 10..20 | `Indi Effect Duration+20` |
| Damage Taken | -5..-1 | `Damage taken-5%` |
| Pet: Damage Taken | -5..-1 | `Pet: Damage taken-5%` |

### RUN — Evasionist's Cape (item 28638)

| Row | Range | Client text at best |
| --- | --- | --- |
| Double Attack | 1..5 | `"Dbl.Atk."+5` |
| Enmity | 1..7 | `Enmity+7` |
| Embolden | 5..15 | `Embolden+15%` |
| Damage Taken | -5..-1 | `Damage taken-5%` |

## Launcher card

The Data page's **Reive & Incursion capes** card picks a cape and, when the
character owns more than one copy, the exact bag or wardrobe row.  It shows the
current decoded augments, offers all four rows and their full value ranges,
and writes the chosen rows with **Apply augments**.  A row set to `— none —` is
left empty; **Max all** puts every row at its strongest value, and **Clear
augments** writes an empty block, the same state Makel-Pakel returns.  A live
client receives `//reload`, so the tooltip and the stat sheet update
immediately.

The API exposes the card through `GET /api/v1/characters/<id>/data` as
`reive`, and the writes through the progress endpoint:

```json
{"op": "reive-augment", "container": 0, "slot": 5,
 "choices": {"dex": 5, "vit": 5, "enmity": 7, "phalanx": null}}
{"op": "reive-clear", "container": 0, "slot": 5}
```

`choices` maps a row key to a value or `null` (clear that row).  A row omitted
from `choices` keeps its current word, so a partial edit leaves the other rows
alone.  A cape that is not one of these 22 item ids is rejected with a 422, as
is a row the cape does not offer or a value outside its range.  Choosing no
rows at all is a 422; use `reive-clear` to empty the block.
