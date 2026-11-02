# Unity augments

iLvl 119+ Unity Wanted +1 equipment is augmented at a Unity NPC with
Lustreless items.  The client stores the result in the same 24-byte
`AugmentBundle` block Odyssey uses, but at **Rank 15** with max-rank
tier 0 (the 15-rank unlock) and one path.  The bundle index selects the
item's row in the client's augment table:

```
03 83  00 00  <rank:5 | tier:2 | curve:2>  <bundle index:u32>  00 * 12
```

The dataset is `data/unity_r15.json`: **108 pieces**, the whole of BG Wiki's
[Unity Accessories](https://www.bg-wiki.com/ffxi/Category:Unity_Accessories),
[Unity Armor](https://www.bg-wiki.com/ffxi/Category:Unity_Armor) and
[Unity Weapons](https://www.bg-wiki.com/ffxi/Category:Unity_Weapons)
categories.  The bundle indices come from the client's augment table
(LandSandBoat's `xi.data.augments.bundles`); every Unity piece is one of
bundles 285-392, matched to its Rank 15 row, and every item has its own
bundle.  The rows are from each item's BG Wiki page.

## The five GearSwap pieces

These are the pieces the shared `local unity` table in
[gearswap/MNK.lua](../gearswap/MNK.lua) defines: Unmoving Collar +1,
Odnowa Earring +1, Gelatinous Ring +1 and Ghastly Tathlum +1 are the four
accessories Ninja wears, and Loess Barbuta +1 is PLD/DRK/SAM/DRG gear.

| Item | Slot | Item ID | Bundle | Rank 15 augments |
| --- | --- | --- | --- | --- |
| Unmoving Collar +1 | neck | 27509 | 305 | DEF+30<br>HP+200 |
| Odnowa Earring +1 | ear | 27549 | 367 | DEF+30<br>Damage taken-3% |
| Gelatinous Ring +1 | ring | 10769 | 316 | VIT+15<br>HP+100 |
| Ghastly Tathlum +1 | ammo | 21344 | 343 | Magic Damage +10<br>INT+5 |
| Loess Barbuta +1 | head | 25636 | 376 | Enmity+10<br>Damage taken-10%<br>All Attr.+10 |

## Accessories (27 pieces)

| Item | Slot | Item ID | Bundle | Rank 15 augments |
| --- | --- | --- | --- | --- |
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

## Armor (32 pieces)

| Item | Slot | Item ID | Bundle | Rank 15 augments |
| --- | --- | --- | --- | --- |
| Adorned Helm +1 | head | 26715 | 325 | Accuracy/Magic Accuracy +45<br>Attack +50<br>All Attr. +10 |
| Agony Jerkin +1 | body | 26943 | 314 | Attack +60<br>"Store TP" +10<br>All Attr. +10 |
| Alhazen Hat +1 | head | 26787 | 345 | All Attr. +30<br>Evasion +50<br>Accuracy/Ranged Accuracy/Magic Accuracy +25 |
| Assid. Pants +1 | legs | 28135 | 289 | Avatar: Accuracy/Magic Accuracy +35<br>Avatar: All Attr. +20<br>MP +20 |
| Asteria Mitts +1 | hands | 27107 | 352 | MP +45<br>Avatar: Accuracy/Magic Accuracy +40<br>Avatar: Magic Burst Bonus +10% |
| Augury Cuisses +1 | legs | 28137 | 291 | Attack +60<br>Magic Attack Bonus +30<br>All Attr. +10 |
| Blistering Sallet +1 | head | 25602 | 359 | Accuracy/Magic Accuracy +45<br>Critical Hit Rate +10%<br>STR/DEX +25 |
| Cohort Cloak +1 | body | 25681 | 354 | Magic Accuracy +100<br>Magic Attack Bonus +100<br>All Attr. +20 |
| Emet Harness +1 | body | 26871 | 323 | Evasion +30<br>Accuracy +40<br>All Attr. +10 |
| Gazu Bracelets +1 | hands | 27151 | 366 | Accuracy +50<br>Haste +10%<br>All Attr. +10 |
| Hike Khat +1 | head | 26785 | 341 | Physical Damage Taken -10%<br>Pet: Damage Taken -5%<br>All Attr. +10 |
| Hime Domaru +1 | body | 26873 | 326 | Accuracy +45<br>"Double Attack" +5%<br>All Attr. +10 |
| Hippomenes Socks +1 | feet | 27410 | 309 | "Resist Bind" +45<br>Evasion +20<br>All Attr. +10 |
| Hygieia Clogs +1 | feet | 27408 | 335 | "Cure" Potency +15%<br>Healing Magic Skill +10<br>All Attr. +10 |
| Imp. Wing Hair. +1 | head | 26710 | 286 | Accuracy +35<br>Magic Evasion +100<br>Critical Hit Rate +10% |
| Jute Boots +1 | feet | 28276 | 317 | DEX/AGI +15<br>Magic Evasion +30<br>All Attr. +10 |
| Kachi. Kote +1 | hands | 27051 | 331 | Attack +45<br>Accuracy/Magic Accuracy +30<br>All Attr. +10 |
| Lamassu Mitts +1 | hands | 27109 | 353 | Avatar: All Attr. +30<br>Avatar: Accuracy/Magic Accuracy +40<br>Avatar Perpetuation Cost -5 |
| Lugra Cloak +1 | body | 26897 | 311 | Magic Accuracy +60<br>Spell Interruption Rate -20%<br>All Attr. +20 |
| Macabre Gaunt. +1 | hands | 27994 | 287 | Magic Evasion +75<br>Occasionally Resist Status Ailments +10<br>All Attr. +10 |
| Obviat. Cuirass +1 | body | 25710 | 380 | Magic Evasion+60<br>Enmity+5<br>All Attr. +10 |
| Regal Pumps +1 | feet | 28274 | 285 | Healing Magic Skill +10<br>Enhancing Magic Skill +10<br>All Attr. +10 |
| Ros. Jaseran +1 | body | 26869 | 304 | Magic Accuracy +45<br>Damage Taken -5%<br>All Attr. +10 |
| Shigure Tekko +1 | hands | 27996 | 297 | Evasion +90<br>Magic Evasion +80<br>All Attr. +10 |
| Shomonjijoe +1 | body | 26888 | 328 | Avatar: TP Bonus +300<br>Avatar: Accuracy/Magic Accuracy +30<br>Avatar: All Attr. +10 |
| Stinger Helm +1 | head | 26732 | 329 | Accuracy/Magic Accuracy +30<br>Physical Damage Limit +5%<br>All Attr. +10 |
| Tatena. Gote +1 | hands | 27149 | 389 | Accuracy+40<br>All Attr.+10<br>"Triple Attack" +4% |
| Tatena. Haidate +1 | legs | 25856 | 382 | Accuracy+60<br>All Attr.+10<br>"Triple Attack" +3% |
| Tatena. Harama. +1 | body | 25733 | 392 | Accuracy+30<br>All Attr.+10<br>"Triple Attack" +5% |
| Tatena. Sune. +1 | feet | 25924 | 386 | Accuracy+60<br>All Attr.+10<br>"Triple Attack" +3% |
| Zoar Subligar +1 | legs | 27231 | 308 | Accuracy +30<br>Critical Hit Rate +5%<br>All Attr. +10 |

## Weapons (49 pieces)

| Item | Slot | Item ID | Bundle | Rank 15 augments |
| --- | --- | --- | --- | --- |
| Ababinili +1 | main | 21165 | 321 | Healing Magic Skill +10<br>Enhancing Magic Skill +10<br>Damage Taken -10% |
| Aizkora +1 | main | 20852 | 344 | Accuracy/Magic Accuracy +45<br>"Triple Attack" +3%<br>"Quadruple Attack" +3% |
| Ajax +1 | sub | 27639 | 339 | Shield Block Rate +10%<br>Enhancing Magic Received Duration +10% |
| Anathema Harpe +1 | main | 20607 | 330 | DMG +20<br>Accuracy/Magic Accuracy +40<br>Critical Hit Rate +10% |
| Antitail +1 | range | 22267 | 373 | Magic Evasion+15<br>"Double Attack"+3 |
| Beheader +1 | main | 20854 | 347 | DMG +53<br>Accuracy/Magic Accuracy +40<br>Haste +10% |
| Buramgh +1 | main | 20807 | 299 | DMG +30<br>Pet: Accuracy/Magic Accuracy +30<br>Accuracy/Magic Accuracy +35 |
| Combuster +1 | main | 20697 | 377 | DMG:+19<br>Accuracy/Magic Accuracy +40<br>"Store TP"+10 |
| Comeuppances +1 | main | 20508 | 390 | DEX+20<br>Accuracy/Magic Accuracy +40<br>"Store TP"+10<br>Pet: Accuracy/Magic Accuracy +40 |
| Contemplator +1 | main | 22058 | 391 | Magic Accuracy +70<br>Enfeebling Magic Skill +20<br>MND +10 |
| Deliverance +1 | sub | 27641 | 348 | Accuracy/Magic Accuracy +30<br>Shield Skill +10 |
| Demers. Degen +1 | main | 20709 | 351 | Accuracy/Magic Accuracy +45<br>DEX +10<br>Sword Enhancement Spell Damage +50% |
| Emeici +1 | main | 20522 | 315 | DMG +30<br>Accuracy/Magic Accuracy +30<br>Critical Hit Rate +10% |
| Evalach +1 | sub | 27637 | 300 | HP +150<br>Shield Skill +10<br>Accuracy/Magic Accuracy +20 |
| Fists of Fury +1 | main | 20528 | 346 | DMG +14<br>Accuracy/Magic Accuracy +40<br>"Regen" +5 |
| Flyssa +1 | main | 20682 | 387 | DMG:+10<br>Accuracy/Magic Accuracy +40<br>Damage taken -5% |
| Forfend +1 | sub | 26402 | 379 | Accuracy+15<br>Magic Accuracy+15<br>Enhancing Magic Skill +10 |
| Gae Derg +1 | main | 20943 | 338 | DMG +62<br>Accuracy/Magic Accuracy +40<br>"Store TP" +8 |
| Habilitator +1 | main | 21749 | 381 | DMG:+21<br>Accuracy/Magic Accuracy +40<br>STR/DEX/CHR+10<br>Pet: Accuracy/Magic Accuracy +40 |
| Imati +1 | range | 22121 | 371 | DMG +17<br>Ranged Accuracy +40<br>"Snapshot" +10% |
| Jugo Kukri +1 | main | 20609 | 332 | DMG +13<br>Accuracy/Magic Accuracy +40<br>Evasion +20 |
| Kladenets +1 | main | 21703 | 342 | DMG +50<br>Accuracy/Magic Accuracy +40<br>"Fast Cast" +10% |
| Kunimune +1 | main | 21035 | 307 | TP Bonus +500<br>Accuracy/Magic Accuracy +30<br>STR +10 |
| Kustawi +1 | main | 20581 | 368 | Ranged Attack +20<br>Ranged Accuracy/Magic Accuracy +40<br>Enmity -5 |
| Loxotic Mace +1 | main | 21091 | 365 | DMG +33<br>Accuracy/Magic Accuracy +40<br>Weapon Skill Damage +10% |
| Magesmasher +1 | main | 21100 | 318 | DMG +45<br>Accuracy/Magic Accuracy +30<br>Weapon Skill Damage +15% |
| Malison +1 | range | 21484 | 378 | Ranged Attack+45<br>Ranged Accuracy/Magic Accuracy +40<br>DMG:+5 |
| Marin Staff +1 | main | 21160 | 333 | Magic Attack Bonus +40<br>Accuracy/Magic Accuracy +40<br>INT/MND +10 |
| Mdomo Axe +1 | main | 20800 | 356 | DMG +24<br>Accuracy/Magic Accuracy +40<br>Pet: Accuracy/Magic Accuracy +50 |
| Mengado +1 | range | 21223 | 301 | "Snapshot" +15<br>DMG +10<br>Ranged Accuracy +20 |
| Montante +1 | main | 21689 | 385 | DMG:+20<br>Accuracy/Magic Accuracy +40<br>HP+100 |
| Norifusa +1 | main | 21030 | 362 | DMG +10<br>Accuracy/Magic Accuracy +40<br>Skillchain Damage +20% |
| Nullis +1 | main | 21696 | 375 | DMG:+33<br>Accuracy/Magic Accuracy +40<br>Dark magic skill +10 |
| Paloma Bow +1 | range | 21220 | 349 | DMG +9<br>Ranged Accuracy +40<br>"Rapid Shot" +15% |
| Perun +1 | main | 20805 | 340 | Ranged Attack +45<br>Ranged Accuracy/Magic Accuracy +30<br>"Snapshot" +5% |
| Pixquizpan +1 | main | 21806 | 370 | DMG +36<br>Accuracy/Magic Accuracy +40<br>Magic Attack Bonus +50 |
| Pouwhenua +1 | main | 21163 | 303 | DMG +45<br>Accuracy/Magic Accuracy +30<br>"Store TP" +10 |
| Pukulatmuj +1 | main | 20614 | 322 | DMG +38<br>Accuracy/Magic Accuracy +30<br>Sword Enhancement Spell Damage +150% |
| Raicho +1 | main | 20981 | 361 | DMG +20<br>Accuracy/Magic Accuracy +40<br>Magic Defense Bonus +5 |
| Refined Grip +1 | sub | 21417 | 313 | DEF +20<br>Parrying Skill +10 |
| Rigorous Grip +1 | sub | 21419 | 327 | Attack +30<br>STR +15 |
| Sangarius +1 | main | 20612 | 319 | DMG +35<br>Accuracy/Magic Accuracy +30<br>"Quadruple Attack" +3% |
| Septoptic +1 | main | 21076 | 388 | DMG:+10<br>Accuracy/Magic Accuracy +40<br>Magic Attack Bonus +30 |
| Tancho +1 | main | 20988 | 293 | DMG +25<br>Accuracy/Ranged Accuracy/Magic Accuracy +20<br>Magic Attack Bonus +20 |
| Tanmogayi +1 | main | 20680 | 384 | DMG+11<br>Accuracy/Magic Accuracy +40<br>Attack+40 |
| Ternion Dagger +1 | main | 20604 | 336 | DMG +17<br>Accuracy/Magic Accuracy +40<br>Weapon Skill Damage +5% |
| Triska Scythe +1 | main | 20899 | 334 | DMG +56<br>Accuracy/Magic Accuracy +40<br>Critical Hit Rate +10% |
| Ushenzi +1 | main | 21691 | 369 | DMG +28<br>Accuracy/Magic Accuracy +40<br>"Cure" Potency Received +10% |
| Wingcutter +1 | range | 21350 | 288 | Accuracy +10<br>Evasion +10 |

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

Two rows disagree between the item pages and LandSandBoat's bundle values:
Buramgh +1's third row is `Accuracy/Magic Accuracy +35` on the page and 25 in
the bundle table, and Kunimune +1's `TP Bonus +500` is 50 there.  The dataset
keeps the page text, so the RP card lists what the wiki documents.

`tools/gen_unity.py --check` keeps this page and the migration in step with
`data/unity_r15.json`.
