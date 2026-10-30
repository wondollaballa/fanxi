# Oseem Arcane Glyptics

Oseem, at Norg (I-7), engraves **Reisenjima** gear with Arcane Glyptics:
Pellucid, Fern and Taupe stones roll up to five augment slots on the Chironic,
Herculean, Merlinic, Odyssean and Valorous armor sets and on the fourteen
Reisenjima weapons.  Retail rolls the slots at random; the player rerolls until
the piece is worth keeping.

The launcher's Data page has an **Oseem · Arcane Glyptics** card that goes the
other way: for each of the five slots, pick the stat the table offers that path
and write its maximum.  Lower a value if wanted; **Max all** puts every slot back
at its cap.

## The block

Arcane Glyptics uses the **standard five-slot augment block** the Ambuscade
capes use:

```
02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12
```

Each slot is `id:11 | value:5`; the client prints `(value + offset) * multiplier`
for the id.  Values above 32 use the client's second id block (Accuracy is
`0x017` for 1-32 and `0x03E` for 33-64, and so on).  Magic Atk. Bns. has no
offset-33 row of its own, so values above 32 use the combined Mag. Acc. /
Mag. Atk. Bns. id `0x046`; the card says so when that id is written.

`server/fanxi_server/game/glyptics.py` holds the stat table (label, sign,
percent, id/offset rows), the encoder and decoder, the inventory catalogue and
apply/clear.  `data/oseem_glyptics.json` is the BG Wiki category page as data:
every armor set and weapon, each path column as a list of `{key, max}` rows.
`max` is the highest value the table lists, including the Fern (F) and Taupe (T)
bonus.

## Paths and slots

The wiki's path columns become path keys:

| Set | Paths |
| --- | --- |
| Chironic | Melee, Healing |
| Herculean | Melee, Ranged, Magic, Familiar |
| Merlinic | Magic, Familiar |
| Odyssean | Melee, Magic |
| Valorous | Melee, Familiar |
| Reisenjima weapons | Melee, Ranged, Magic, Pet |

Every path offers its own stat pool.  The card starts each slot from the path's
primary rows (main offence, a special, a base stat, Accuracy, Attack) and lets
the player replace any of them from the full pool.  Slots left empty are
written as empty.

Two rows are capped by the client's five-bit field rather than the wiki:
`Pet: Magic Attack Bonus` and `Pet: Magic Accuracy` have no offset-33 id, so the
card offers 32 and marks the truncated value.

## The stat sheet

`augment_stats` decodes the standard block through `capes.decode` and the
shared id table, so an equipped Reisenjima piece carries the chosen rows into
combat.  The Oseem ids were added to `capes.TABLE` (including the combined
`0x046` row) so the same decoder serves both systems.  Pet rows are still client
text only.

## In the launcher

- Pick a piece (grouped by set), a path if the piece has more than one, and a
  copy.
- Five slot panels: stat selector, value field, and the maximum that stat can
  hold.  The value defaults to the maximum.
- **Apply augments** writes the block and reloads a live client; **Clear
  augments** writes the empty block.

## Tests

`server/tests/test_glyptics.py` pins the catalogue (25 armor pieces, 14 weapons,
the five sets' paths), every offered stat's encodability, the extended-id
layout, the combined Mag. Acc. / Mag. Atk. Bns. row, the round trip of every
path, the stat-sheet decode and apply/clear.
