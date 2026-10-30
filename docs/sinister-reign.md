# Sinister Reign augments

Sinister Reign, added in the August 2015 update, drops iL119 gear from its
waves of Seekers of Adoulin characters.  Every piece is augmented with the
standard **five-slot augment block** the Ambuscade capes, Oseem Arcane Glyptics
and Skirmish gear use:

```
02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12
```

Each slot is a little-endian u16 holding `id:11 | value:5`; the client prints
`(value + offset) * multiplier` for the id.  Retail rolls the rows at random and
the player keeps or rerolls the piece.  The launcher's Data page goes the other
way: pick an owned copy and **Give max augments** writes every row the wiki
lists at the top of its range in one step.

[Samnuha Tights](https://ffxiclopedia.fandom.com/wiki/Samnuha_Tights) is the
worked example: FFXIclopedia lists STR+1~10, DEX+1~10, Double Attack+1~3% and
Triple Attack+1~3%; the card writes STR+10, DEX+10, `"Dbl.Atk."+3%` and
`"Triple Atk."+3%`.

## The catalogue

`data/sinister_reign.json` holds the 37 pieces from the
[BG Wiki Sinister Reign category](https://www.bg-wiki.com/ffxi/Category:Sinister_Reign):
16 weapons and ranged pieces plus 21 armour pieces across head, body, hands, legs
and feet.  Each row is `{key, value}`; `key` is a stat in
`server/fanxi_server/game/skirmish.py` and `value` is the highest number the
wiki table lists.  The file was captured from the category page on 2026-10-29
and the Samnuha Tights page from FFXIclopedia.

| Source | Pieces |
| --- | --- |
| Arciela and Ygnas (wave 1) | Himetsuruichimonji, Humility, Lengo Pants, Leyline Gloves |
| Darrcuiln (wave 1) | Amm Greaves, Fleshcarvers, Koresuke, Ta'lab Trousers |
| Ingrid (wave 1) | Dampening Tam, Fanatic Gloves, Malevolence, Purgation |
| Teodor (wave 2) | Rubicundity, Samnuha Coat, Samnuha Tights, Vampirism |
| Morimar (wave 2) | Brutality, Ferocity, Lilitu Headpiece, Loyalist Sabatons, Floral Gauntlets, Medium's Sabots |
| Rosulatia (wave 2) | Nobility, Serenity, Enticer's Pants |
| Arciela (wave 3) | Ochu, Taming Sari, Witching Robe |
| Sajj'aka (wave 3) | Brilliance, Divinity, Jumalik Helm, Jumalik Mail |
| August (wave 3) | Founder's Corona, Founder's Breastplate, Founder's Gauntlets, Founder's Hose, Founder's Greaves |

The wiki's spot tables are the source for the rows; the launcher card groups the
catalogue by slot so a piece is easy to find.

## The card

- Pick a piece (grouped by **Weapons**, **Head**, **Body**, **Hands**, **Legs**
  and **Feet**) and, when the character owns several, the copy to edit.
- The card shows the maximum rows as chips; a selected piece that is not in the
  bags is previewed with a pointer to the Armory.
- **Give max augments** writes every row at its maximum and reloads a live
  client, so the in-game tooltip and the stat sheet update.  It replaces any
  values already on the copy.
- **Clear augments** writes the empty block.
- A live client reload is the same `//reload` the other augment cards use; with
  the client closed the change applies on the next zone-in.

## The stat sheet

`augment_stats` decodes the standard block through `capes.decode` and the shared
id table, so an equipped Sinister Reign piece feeds its STR/DEX, attack, magic,
haste, damage-taken and remaining modelled rows into combat.  The new ids used
by this catalogue are:

| Id | Text |
| --- | --- |
| `0x071` | Pet: Rng. Acc. |
| `0x093` | Treasure Hunter |
| `0x120`–`0x122`, `0x125`, `0x127` | Divine / Healing / Enhancing / Dark Magic / Ninjutsu skill |
| `0x06A` | Pet: Accuracy + Pet: Rng. Acc. (one combined word) |

Magic skills and Treasure Hunter are client text only for now; they are listed
in `augment_stats.UNMODELLED` so a new row cannot slip through the coverage
test.  Pet rows are deliberately not applied to the player.

## Tests

`server/tests/test_sinister.py` pins 37 pieces, the slot groups, the Samnuha
Tights rows and their exact block words (`0x200:9`, `0x201:9`, `0x08F:2`,
`0x090:2`), the combined Enticer's Pants pet row, every row's encode/decode
round trip, apply/clear through a temporary database and the rejection paths.
`server/tests/test_api.py` pins the HTTP card and the `sinister` /
`sinister-clear` progress ops, and `test_augment_stats.py` walks every maximum
row through the tooltip parser.
