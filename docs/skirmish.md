# Divainy-Gamainy Skirmish augments

Divainy-Gamainy, at **Western Adoulin (J-10)**, is the Inventors' Coalition
Skirmish NPC. The launcher's Data page has a **Divainy-Gamainy · Skirmish**
card that covers every item the four BG Wiki Skirmish categories list:

* [Alluvion Skirmish Weapons](https://www.bg-wiki.com/ffxi/Category:Alluvion_Skirmish_Weapons) — 16
* [Alluvion Skirmish Armor](https://www.bg-wiki.com/ffxi/Category:Alluvion_Skirmish_Armor) — 25
* [Skirmish Weapon](https://www.bg-wiki.com/ffxi/Category:Skirmish_Weapon) — 45 (15 families × NQ/+1/+2)
* [Skirmish Armor](https://www.bg-wiki.com/ffxi/Category:Skirmish_Armor) — 52 (5 sets × NQ/+1 plus the two Beatific Shields)

138 items in all.  Retail rolls the rows at random and the player keeps or
rerolls the piece; the card writes a chosen stat per row at its maximum.  The
dataset was captured from those pages on 2026-10-27.

## The block

All three families use the **standard five-slot augment block** the Ambuscade
capes and Oseem use:

```
02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12
```

Each slot is a little-endian u16 holding `id:11 | value:5`; the client prints
`(value + offset) * multiplier` for the id.  Skirmish uses at most three slots.

## The rows

| Family | Rows |
| --- | --- |
| Alluvion Skirmish weapons and armor | one Snow stone, one Leaf stone, one Dusk stone |
| Skirmish weapons | DMG, plus up to one stat from each of two pools |
| Skirmish armor | Physical Damage Taken, plus one (NQ) or two (+1) stats from one pool |

The Beatific Shields' single row that can be HP or MP is offered as two separate
options; the wiki's `HP and/or MP` on the +1 shield is the same row.

An Alluvion stone slot is optional: an item can carry one, two or all three
stones.  A clean copy starts with all three suggested; an already augmented one
only seeds the rows it actually carries, so Apply cannot add a stone the player
never used.  The DMG row (Skirmish weapons, and the Dusk stone on Alluvion
weapons) comes from the weapon's own base table — Ohrmazd caps at +29, Inanna at
+39.  The Dusk tip is Delay- on melee weapons; on Archery and Marksmanship it is
+Snapshot instead, and the card offers the right one for the selected weapon.

## The stat table

`server/fanxi_server/game/skirmish.py` holds the client ids.  Each stat has one
or more `(offset, id, multiplier)` rows from the client table, plus a sign:

* **Reductions** (`Phys. dmg. taken`, `Delay`, `Song recast delay`, ...) are
  stored as a magnitude and printed with a minus.
* **Enmity** is the one row that can go either way; the two ends use ids
  `0x027` (positive) and `0x028` (negative).
* **Combined ids** print two stats from one word: `0x083` is Mag. Acc. +
  Mag. Atk. Bns. (offset 1), `0x046` the offset-33 block, `0x226`/`0x227`/`0x228`
  are STR with DEX/VIT/AGI, and so on.
* **Scaled ids** multiply the five-bit value: Save TP `0x168` is ×10,
  Pet: TP Bonus `0x07A` is ×20, Elemental Siphon `0x153` is ×5.
* **Value blocks** pick the smallest offset that can hold the number (HP+70 uses
  the offset-65 id with stored 5, DMG+39 the offset-33 id with stored 6).

The values in `data/skirmish.json` are the highest the BG Wiki tables list for
each row, across every stone quality (`+2` stones included for the old Skirmish
sets).  `snap_bounds` clamps a wiki range to the values the chosen id can
actually print: a ×10 row starts at 10 and moves in tens.

## The card

- Pick a piece (grouped by family: Alluvion weapons, each Alluvion armor set,
  the Skirmish weapons, each Skirmish armor set) and a copy.
- Each row has a stat select and a value box; DMG and Physical Damage Taken
  are fixed labels because they are the one option. The box starts at the row's
  strongest value, and every non-guaranteed row has an **— empty —** choice.
- **Max all** restores every chosen row to its strongest value.
- **Apply augments** writes the block and reloads a live client; **Clear
  augments** writes the empty block.
- A piece that is not in the bags is previewed only.

## The stat sheet

`augment_stats` decodes the block through `capes.decode` and the shared id
table, so an equipped Skirmish piece feeds its Accuracy, Store TP, Haste,
damage-taken and remaining stat rows into combat.  Weapon DMG and Delay rows are
client text only: the engine reads both from the item's base `item_weapon` row.
Pet rows are skipped by the stat parser.

## Tests

`server/tests/test_skirmish.py` pins the catalogue (138 items, 36 tables), the
three stone layouts, the wiki maxima, the DMG cap per weapon, the ranged DMG and
Snapshot swap, every option's encodability and round trip, the stat-sheet read,
apply/clear and the validation errors.  `test_api.py` pins the HTTP card and the
`skirmish` / `skirmish-clear` progress ops.
