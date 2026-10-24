# Unity augments

iLvl 119 Unity Wanted +1 equipment is augmented at a Unity NPC with
Lustreless items.  The client stores the result in the same 24-byte
`AugmentBundle` block Odyssey uses, but at **Rank 15** with max-rank
tier 0 (the 15-rank unlock) and one path.  The bundle index selects the
item's row in the client's augment table:

```
03 83  00 00  <rank:5 | tier:2 | curve:2>  <bundle index:u32>  00 * 12
```

The Rank 15 row is what the GearSwap libraries list for these items:

| Item | Slot | Item ID | Bundle | Rank 15 augments |
| --- | --- | --- | --- | --- |
| Unmoving Collar +1 | neck | 27509 | 305 | DEF+30<br>HP+200 |
| Odnowa Earring +1 | ear | 27549 | 367 | DEF+30<br>Damage taken-3% |
| Gelatinous Ring +1 | ring | 10769 | 316 | VIT+15<br>HP+100 |
| Ghastly Tathlum +1 | ammo | 21344 | 343 | Magic Damage +10<br>INT+5 |
| Loess Barbuta +1 | head | 25636 | 376 | Enmity+10<br>Damage taken-10%<br>All Attr.+10 |

The four accessories are the Unity pieces Ninja wears in
[gearswap/NIN.lua](../gearswap/NIN.lua): Unmoving Collar +1, Odnowa Earring +1,
Gelatinous Ring +1 and Ghastly Tathlum +1.  Loess Barbuta +1 is the fifth
Unity item that library defines (it is PLD/DRK/SAM/DRG gear, not a Ninja set
piece) and is augmented here too.

## In game

`database/migrations/0083_unity_augments.sql` writes each block into
`char_inventory.extra` for the first character.  `!augment A <item>` rewrites
a copy, `!augment off <item>` clears it, and `!augment list` shows the builds.
The block is not only a tooltip any more: `FanxiService.equipped_mods()` joins
each equipped item back to its inventory copy and `augment_stats` turns the
Rank 15 rows into modifiers, so Unmoving Collar +1's `DEF+30 HP+200` reaches
the stat sheet and combat.

`tools/gen_unity.py --check` keeps this page and the migration in step with
`server/fanxi_server/game/unity.py`.
