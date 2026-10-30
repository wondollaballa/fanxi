# Unity augments

iLvl 119+ Unity Wanted +1 equipment is augmented at a Unity NPC with
Lustreless items.  The client stores the result in the same 24-byte
`AugmentBundle` block Odyssey uses, but at **Rank 15** with max-rank
tier 0 (the 15-rank unlock) and one path.  The bundle index selects the
item's row in the client's augment table:

```
03 83  00 00  <rank:5 | tier:2 | curve:2>  <bundle index:u32>  00 * 12
```

The Rank 15 row is from each item's BG Wiki page; the first five are also
the rows the GearSwap libraries carry:

| Item | Slot | Item ID | Bundle | Rank 15 augments |
| --- | --- | --- | --- | --- |
| Unmoving Collar +1 | neck | 27509 | 305 | DEF+30<br>HP+200 |
| Odnowa Earring +1 | ear | 27549 | 367 | DEF+30<br>Damage taken-3% |
| Gelatinous Ring +1 | ring | 10769 | 316 | VIT+15<br>HP+100 |
| Ghastly Tathlum +1 | ammo | 21344 | 343 | Magic Damage +10<br>INT+5 |
| Loess Barbuta +1 | head | 25636 | 376 | Enmity+10<br>Damage taken-10%<br>All Attr.+10 |
| Blistering Sallet +1 | head | 25602 | 359 | Accuracy/Magic Accuracy +45<br>Critical Hit Rate +10%<br>STR/DEX +25 |
| Rigorous Grip +1 | sub | 21419 | 327 | Attack +30<br>STR +15 |
| Acuity Belt +1 | waist | 28430 | 295 | Magic Accuracy +15<br>INT +10 |
| Apeile Ring +1 | ring | 27561 | 310 | DEF +20<br>Magic Defense Bonus +5 |
| Arete del Luna +1 | ear | 28487 | 302 | Resist Sleep +15<br>Resist Charm +15 |
| Aurist's Cape +1 | back | 27620 | 363 | Accuracy/Magic Accuracy +25<br>INT/MND +25 |
| Bathy Choker +1 | neck | 27518 | 350 | Evasion +15<br>Counter +10 |
| Cacoethic Ring +1 | ring | 10771 | 358 | DEX +10<br>AGI +10 |
| Canto Necklace +1 | neck | 28353 | 296 | Magic Accuracy +15<br>CHR +10 |
| Domin. Earring +1 | ear | 27543 | 374 | Accuracy +10<br>DEX +6 |
| Fi Follet Cape +1 | back | 27610 | 360 | Fast Cast +10%<br>Spell Interruption Rate -5% |
| Ground. Mantle +1 | back | 27602 | 320 | Accuracy +15<br>DEX +10 |
| Handler's Earring +1 | ear | 28491 | 298 | Pet: Accuracy/Magic Accuracy +15<br>Accuracy +10 |
| Kentarch Belt +1 | waist | 28413 | 355 | STR+10<br>DEX+10 |
| Loricate Torque +1 | neck | 26002 | 372 | DEF +45<br>Spell Interruption Rate -5% |
| Lugra Earring +1 | ear | 28482 | 312 | DEF +20<br>STR/DEX/VIT/INT +8 |
| Mephitas's Ring +1 | ring | 27559 | 337 | Conserve MP +15<br>INT +5 |
| Metamorph Ring +1 | ring | 27563 | 306 | Magic Accuracy +10<br>INT/MND/CHR +10 |
| Nourishing Earring +1 | ear | 28485 | 290 | Resist Silence +15<br>Spell Interruption Rate -5% |
| Sailfi Belt +1 | waist | 28428 | 292 | STR +15<br>Double Attack +5% |
| Seeth. Bomblet +1 | ammo | 22255 | 364 | STR +10<br>Haste +5% |
| Shinjutsu-no-Obi +1 | waist | 28424 | 294 | Conserve MP +15<br>Fast Cast +5% |
| Vim Torque +1 | neck | 26022 | 383 | Accuracy +15<br>Store TP +10 |
| Warder's Charm +1 | neck | 27505 | 324 | Skillchain Damage +15%<br>Magic Burst Bonus +10% |
| Zwazo Earring +1 | ear | 27533 | 357 | HP +45<br>Shield Block Rate +3% |

The first five entries are the Unity pieces the shared `local unity` table
in [gearswap/MNK.lua](../gearswap/MNK.lua) defines: Unmoving Collar +1,
Odnowa Earring +1, Gelatinous Ring +1 and Ghastly Tathlum +1 are the four
accessories Ninja wears, and Loess Barbuta +1 is PLD/DRK/SAM/DRG gear.
The rest of the Unity accessory, armour and grip catalogue follows,
including the four belts, Blistering Sallet +1 and Rigorous Grip +1, so the
Data page's RP card lists every Unity piece in the bags as soon as it is
purchased.

## In game

`database/migrations/0083_unity_augments.sql` writes each block into
`char_inventory.extra` for the first character.  `//augment A <item>` rewrites
a copy, `//augment off <item>` clears it, and `//augment list` shows the builds.
The block is not only a tooltip any more: `FanxiService.equipped_mods()` joins
each equipped item back to its inventory copy and `augment_stats` turns the
Rank 15 rows into modifiers, so Unmoving Collar +1's `DEF+30 HP+200` reaches
the stat sheet and combat.  The Data page's RP card marks the path a copy
already carries: a capped path is highlighted and its button reads **Capped**,
a partial one offers **Finish path**, and picking another path overwrites the
block.

`tools/gen_unity.py --check` keeps this page and the migration in step with
`server/fanxi_server/game/unity.py`.
