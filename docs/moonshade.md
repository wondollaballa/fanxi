# Moonshade Earring augments

The **Moonshade Earring** (item 11697, level 90, earring, Rare/Ex) is the
Wings of the Goddess completion reward from *Lest We Forget*. When the mission
hands it over, the player chooses **one augment from Set 1 and one from Set 2**;
both live in the earring's 24-byte standard augment block, exactly like a cape
or Skirmish row. The Data page's **Moonshade Earring** card writes either pair
(or clears it) and the stat sheet reads it back.

## The two sets

The ids and values are LandSandBoat's, from
`scripts/missions/wotg/54_Lest_We_Forget.lua`, which passes two
`(augment id, value)` pairs to `addItem`. That is the block retail writes, so
the card does not guess.

| Set 1 | id | value | Tooltip |
| --- | ---: | ---: | --- |
| Accuracy | 23 | 3 | Accuracy+4 |
| Attack | 25 | 3 | Attack+4 |
| Ranged Accuracy | 27 | 3 | Rng.Acc.+4 |
| Ranged Attack | 29 | 3 | Rng.Atk.+4 |
| Magic Accuracy | 35 | 3 | Mag. Acc.+4 |
| "Magic Atk. Bonus" | 133 | 3 | "Mag.Atk.Bns."+4 |
| HP | 1 | 24 | HP+25 |
| MP | 9 | 24 | MP+25 |

| Set 2 | id | value | Tooltip |
| --- | ---: | ---: | --- |
| Latent "Regain" | 59 | 0 | Latent effect: "Regain"+10 |
| Latent "Refresh" | 60 | 0 | Latent effect: "Refresh"+1 |
| Occ. damage bonus by TP | 352 | 4 | Occ. grants dmg. bonus based on TP+5% |
| TP Bonus | 353 | 4 | TP Bonus+250 |
| Occ. max magic accuracy | 350 | 2 | Occ. maximizes magic accuracy+3% |
| Occ. quickens spellcasting | 351 | 2 | Occ. quickens spellcasting+3% |
| Counter | 145 | 2 | "Counter"+3 |
| Resist ailments | 61 | 4 | Occ. inc. resist. to stat. ailments+5 |

The tooltip text comes from `capes._text` (the ids 0x03B, 0x03C, 0x15E, 0x160
and 0x161 were added to `capes.TABLE` for these rows), so the card and the item
description agree. `augment_stats` applies the modelled rows: Accuracy 4,
Attack 4, HP 25, TP Bonus 250, Counter 3 and so on. The conditional rows
("Latent effect" Regain/Refresh, the three "Occ." procs and the ailment
resistance) are listed in `augment_stats.UNMODELLED` because the engine has no
pool for them yet; they still appear in the tooltip.

## The card

- The card lists every Moonshade Earring copy in any permanent bag or storage
  (`service.inventory` sees the wardrobe too). Rare/Ex means one per character,
  but a copy sitting in the wardrobe can be augmented without moving it.
- Two pickers, one per set; the current pair is preselected when the copy
  already has augments.
- **Apply augments** writes both words and the zone session sees them on
  `//reload`; **Clear augments** writes the empty block behind a confirmation.
- The inventory row records the block in `char_inventory.extra`, so the gear
  set viewer and the stat sheet show the same lines.

Retail's "toss the earring and replay the last missions" reaugment loop is not
modelled: the card can rewrite the pair at any time.

## Files

- `data/moonshade.json` — the two sets and their 16 options.
- `server/fanxi_server/game/moonshade.py` — catalogue, validation, block writer.
- `launcher-rs/src/components/MoonshadeEarring.tsx` — the card.
- `server/tests/test_moonshade.py` — the 16 tooltips, apply/reapply/clear,
  unknown choices, a wardrobe copy and the stat-sheet read.
