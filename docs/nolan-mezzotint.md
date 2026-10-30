# Nolan mezzotint augments

Nolan, at Norg (I-7), mezzotints the gear that drops in **Escha - Zi'Tah**,
**Escha - Ru'Aun** and the abjuration sets: every weapon on his page, the seven
Zi'Tah armor sets, and the eleven NQ/HQ abjuration sets.  Trading a piece by
itself opens the four paths **A-D**; Eschalixirs then add rank points until
**Rank 15**.  Paths A/B/C are shared by all five pieces of an armor set, path D
is per piece.

The launcher's Data page has a **Nolan · Escha mezzotint** card.  It lists the
Escha pieces the character holds (the catalogue behind it is the 183 items on
the wiki page), shows each path's Rank 15 rows, and writes the chosen path in
one step.  A live client reloads and draws the new tooltip.

## The block

The client keeps the result in the mezzotint exdata block, not in the five-slot
standard block the Ambuscade capes use:

```
offset 0   u8    kind        0x02  (has augments)
offset 1   u8    subkind     0x20  (mezzotint flag)
offset 2   u8    path:2 | rank:5 | padding:1
offset 3   u8    padding
offset 4   u16   accumulated RP inside the current rank
offset 6   u8[3] (augment index, value) — the block's three rows
offset 12  u8[12] signature
```

This is LandSandBoat's `Exdata::AugmentMezzotint` layout.  The `index` names a
row in the client's mezzotint table (HP, Accuracy, "Store TP", pet rows, weapon
skills, ...); `value` is one less than the printed number, and reductions carry
a negative multiplier.  The editor always writes rank 15 and RP 0 (nothing left
to the next rank), the same "cap it now" model the RP and Oboro cards use.

`server/fanxi_server/game/mezzotint.py` holds the stat table, the encoder and
decoder, the inventory catalogue and the apply call.  `data/nolan_mezzotint.json`
is the BG Wiki page as data:

```json
{
  "item_id": 25618,
  "name": "Kaykaus Mitra +1",
  "kind": "armor",
  "slot": "head",
  "zone": "Escha - Ru'Aun",
  "group": "Kaykaus Attire Set +1",
  "paths": {
    "A": [{"key": "mp", "value": 80}, {"key": "mnd", "value": 12},
          {"key": "macc", "value": 20}]
  }
}
```

The values are the **Rank 15 maximums** from the wiki's "max rank augments"
tables, captured in one place so the card and the stat sheet cannot disagree.

## The stat sheet

`augment_stats.item_mods` treats a `0x02/0x20` block as mezzotint and renders
each row back to text (`MP+80`, `Phys. dmg. taken-4%`, ...) before running it
through the same parser the RP, Unity and cape rows use.  An equipped Kaykaus
Bliaut with path B therefore actually carries its MP, Cure cast time and Enmity
into combat, not just the tooltip.

Pet rows and a handful of job-specific rows are still client text only; they
are listed in `augment_stats.UNMODELLED` so a new row cannot slip through
unnoticed.

## In the launcher

- Pick a piece from the grouped selector (group = Escha zone or set name).
- If more than one copy is owned, pick the copy by bag and slot.
- The current line reads `Type B/Rank 15 · MP+80 | ...`, or "not augmented".
- **Apply path** writes that path's three Rank 15 rows; the active path is
  highlighted and its button says **Re-apply path**.  Switching paths overwrites
  the old block.

The card appears empty until an Escha piece is in the bags; the Armory card on
the same page can buy one.

## Tests

`server/tests/test_nolan.py` pins the catalogue (183 items, four paths, three
rows each), the block layout (kind/subkind/path/rank), a round trip over every
item and path, the negative signs, the stat-sheet decode and the service calls.
