# Oboro Dynamis-Divergence weapon and JSE neck augments

Oboro, at Port Jeuno (E-6), augments the crafted JSE weapons that drop
from Dynamis - Divergence and all 22 **JSE necks**.  The client stores
the result in the same
24-byte `AugmentBundle` block Odyssey and Limbus use:

```
03 83  00 00  <rank:5 | tier:2 | curve:2>  <bundle index:u32>  00 * 12
```

Each weapon has three paths, A/B/C.  Every HQ2 weapon's A and B path
also carries a DMG row; path C is job-specific.  The quality sets the
cap: **NQ R15 (tier 0), HQ1 R20 (tier 1), HQ2 R25 (tier 2)**.  The RP
field uses curve A; the launcher writes the rank-bar maximum and shows
the lifetime total separately (R15 5,950; R20 13,060; R25 25,150).

The bundle indices come from the client's augment table (LandSandBoat's
`xi.data.augments.bundles`, parsed from the MNC2 data).  The 22 weapon
families are listed in the table's own order, nine bundles per family:
NQ A/B/C, HQ1 A/B/C, HQ2 A/B/C.  The 22 JSE necks follow them as
bundles 199-220, one bundle per job in the same order; all three
qualities share the job's bundle and the block's rank/tier selects the
row values.  Assassin's Gorget +2 (bundle 204) is the copy the block
layout was verified against.

## Path A and B

| Quality | Rank | Path A | Path B |
| --- | --- | --- | --- |
| NQ | 15 | Chance of double damage +30%<br>Store TP+15 | Chance of follow-up attack +30%<br>"Subtle Blow II"+15 |
| HQ1 | 20 | Chance of double damage +40%<br>Store TP+20 | Chance of follow-up attack +40%<br>"Subtle Blow II"+20 |
| HQ2 | 25 | Chance of double damage +50%<br>Store TP+25<br>DMG:+ weapon-specific | Chance of follow-up attack +50%<br>"Subtle Blow II"+25<br>DMG:+ weapon-specific |

Ranged weapons (RNG) use "Chance of double ranged damage" and
"Chance of ranged follow-up attack".

## Weapons

| Family | NQ | HQ1 | HQ2 | Path C NQ | Path C HQ1 | Path C HQ2 |
| --- | --- | --- | --- | --- | --- | --- |
| MNK (Hand-to-Hand) | **Melee Fists**<br>#21521<br>A/B/C 1/2/3 | **Hes. Fists**<br>#21522<br>A/B/C 4/5/6 | **Sagitta**<br>#21523<br>A/B/C 7/8/9 | HP+200<br>"Chakra"+20 | HP+300<br>"Chakra"+35 | HP+400<br>"Chakra"+50<br>DMG:+12 |
| PUP (Hand-to-Hand) | **Pantin Fists**<br>#21524<br>A/B/C 10/11/12 | **Pitre Fists**<br>#21525<br>A/B/C 13/14/15 | **Xiucoatl**<br>#21526<br>A/B/C 16/17/18 | Weapon skill damage +10%<br>Automaton: Special attack damage +15% | Weapon skill damage +12%<br>Automaton: Special attack damage +20% | Weapon skill damage +15%<br>Automaton: Special attack damage +25%<br>DMG:+12 |
| THF (Dagger) | **Assassin's Knife**<br>#21573<br>A/B/C 19/20/21 | **Plun. Knife**<br>#21574<br>A/B/C 22/23/24 | **Gandring**<br>#21575<br>A/B/C 25/26/27 | Evasion+50<br>TP during evasion +20 | Evasion+75<br>TP during evasion +35 | Evasion+100<br>TP during evasion +50<br>DMG:+5 |
| BRD (Dagger) | **Bard's Knife**<br>#21576<br>A/B/C 28/29/30 | **Bihu Knife**<br>#21577<br>A/B/C 31/32/33 | **Barfawc**<br>#21578<br>A/B/C 34/35/36 | Song spellcasting time -15%<br>Song effects: "Double Attack"+2% | Song spellcasting time -20%<br>Song effects: "Double Attack"+3% | Song spellcasting time -25%<br>Song effects: "Double Attack"+4%<br>DMG:+5 |
| COR (Dagger) | **Comm. Knife**<br>#21579<br>A/B/C 37/38/39 | **Lanun Knife**<br>#21580<br>A/B/C 40/41/42 | **Rostam**<br>#21581<br>A/B/C 43/44/45 | "Phantom Roll" effect duration +30<br>"Phantom Roll XI": Recover HP and MP +10%<br>"Phantom Roll"+6 | "Phantom Roll" effect duration +45<br>"Phantom Roll XI": Recover HP and MP +12%<br>"Phantom Roll"+7 | "Phantom Roll" effect duration +60<br>"Phantom Roll XI": Recover HP and MP +15%<br>"Phantom Roll"+8 |
| DNC (Dagger) | **Etoile Knife**<br>#21582<br>A/B/C 46/47/48 | **Horos Knife**<br>#21583<br>A/B/C 49/50/51 | **Setan Kober**<br>#21584<br>A/B/C 52/53/54 | "Flourish" recast time -15%<br>"Step" duration +30 | "Flourish" recast time -20%<br>"Step" duration +45 | "Flourish" recast time -25%<br>"Step" duration +60<br>DMG:+5 |
| RDM (Sword) | **Duelist's Sword**<br>#21625<br>A/B/C 55/56/57 | **Vitiation Sword**<br>#21626<br>A/B/C 58/59/60 | **Crocea Mors**<br>#21627<br>A/B/C 61/62/63 | Sword enhancement spell damage +300%<br>Elemental weapon skill damage +50% | Sword enhancement spell damage +400%<br>Elemental weapon skill damage +75% | Sword enhancement spell damage +500%<br>Elemental weapon skill damage +100%<br>DMG:+7 |
| PLD (Sword) | **Valor Sword**<br>#21628<br>A/B/C 64/65/66 | **Cabal. Sword**<br>#21629<br>A/B/C 67/68/69 | **Moralltach**<br>#21630<br>A/B/C 70/71/72 | HP+150<br>"Cure" potency+15%<br>"Refresh"+2 | HP+200<br>"Cure" potency+20%<br>"Refresh"+3 | HP+250<br>"Cure" potency+25%<br>"Refresh"+4 |
| BLU (Sword) | **Mirage Sword**<br>#21631<br>A/B/C 73/74/75 | **Luhlaza Sword**<br>#21632<br>A/B/C 76/77/78 | **Zomorrodnegar**<br>#21633<br>A/B/C 79/80/81 | "Chain Affinity" recast time -15%<br>"Burst Affinity" recast time -15% | "Chain Affinity" recast time -20%<br>"Burst Affinity" recast time -20% | "Chain Affinity" recast time -25%<br>"Burst Affinity" recast time -25%<br>DMG:+7 |
| RUN (Great Sword) | **Futhark Claymore**<br>#21667<br>A/B/C 82/83/84 | **Peord Claymore**<br>#21668<br>A/B/C 85/86/87 | **Morgelai**<br>#21669<br>A/B/C 88/89/90 | Potency of "Regen" effects received +15<br>"Vivacious Pulse" potency +20% | Potency of "Regen" effects received +20<br>"Vivacious Pulse" potency +25% | Potency of "Regen" effects received +25<br>"Vivacious Pulse" potency +30%<br>DMG:+14 |
| BST (Axe) | **Monster Axe**<br>#21715<br>A/B/C 91/92/93 | **Ankusa Axe**<br>#21716<br>A/B/C 94/95/96 | **Pangu**<br>#21717<br>A/B/C 97/98/99 | Damage Taken -15%<br>Pet: Damage Taken -10% | Damage Taken -20%<br>Pet: Damage Taken -12% | Damage Taken -25%<br>Pet: Damage Taken -15%<br>DMG:+11 |
| WAR (Great Axe) | **War. Chopper**<br>#21772<br>A/B/C 100/101/102 | **Agoge Chopper**<br>#21773<br>A/B/C 103/104/105 | **Labraunda**<br>#21774<br>A/B/C 106/107/108 | TP Gained when landing critical hits +30<br>Crit. Hit Rate +6% | TP Gained when landing critical hits +40<br>Crit. Hit Rate +8% | TP Gained when landing critical hits +50<br>Crit. Hit Rate +10%<br>DMG:+14 |
| DRK (Scythe) | **Abyss Scythe**<br>#21823<br>A/B/C 109/110/111 | **Fallen's Scythe**<br>#21824<br>A/B/C 112/113/114 | **Father Time**<br>#21825<br>A/B/C 115/116/117 | "Drain" potency +15%<br>Weapon Skill Damage +10% | "Drain" potency +20%<br>Weapon Skill Damage +12% | "Drain" potency +25%<br>Weapon Skill Damage +15%<br>DMG:+15 |
| DRG (Polearm) | **Wyrm Lance**<br>#21876<br>A/B/C 118/119/120 | **Pteroslaver Lance**<br>#21877<br>A/B/C 121/122/123 | **Aram**<br>#21878<br>A/B/C 124/125/126 | Wyvern: HP +150<br>Wyvern: Damage Taken -10% | Wyvern: HP +200<br>Wyvern: Damage Taken -12% | Wyvern: HP +250<br>Wyvern: Damage Taken -15%<br>DMG:+14 |
| NIN (Katana) | **Koga Shin.**<br>#21915<br>A/B/C 127/128/129 | **Mochi. Shin.**<br>#21916<br>A/B/C 130/131/132 | **Fudo Masamune**<br>#21917<br>A/B/C 133/134/135 | Ninjutsu recast time -15%<br>Enmity+6 for each Utsusemi | Ninjutsu recast time -20%<br>Enmity+8 for each Utsusemi | Ninjutsu recast time -25%<br>Enmity+10 for each Utsusemi<br>DMG:+7 |
| SAM (Great Katana) | **Saotome-no-Tachi**<br>#21968<br>A/B/C 136/137/138 | **Sakonji-no-Tachi**<br>#21969<br>A/B/C 139/140/141 | **Fusenaikyo**<br>#21970<br>A/B/C 142/143/144 | "Sekkanoki" recast time -15%<br>"Sekkanoki": Weapon Skill Damage +50% | "Sekkanoki" recast time -20%<br>"Sekkanoki": Weapon Skill Damage +75% | "Sekkanoki" recast time -25%<br>"Sekkanoki": Weapon Skill Damage +100%<br>DMG:+13 |
| WHM (Club) | **Cleric's Wand**<br>#22033<br>A/B/C 145/146/147 | **Piety Wand**<br>#22034<br>A/B/C 148/149/150 | **Asclepius**<br>#22035<br>A/B/C 151/152/153 | "Afflatus Misery" stored +150%<br>Healing magic recast delay -15%<br>Damage Taken -10% | "Afflatus Misery" stored +200%<br>Healing magic recast delay -20%<br>Damage Taken -12% | "Afflatus Misery" stored +250%<br>Healing magic recast delay -25%<br>Damage Taken -15% |
| GEO (Club) | **Bagua Wand**<br>#22036<br>A/B/C 154/155/156 | **Sifang Wand**<br>#22037<br>A/B/C 157/158/159 | **Bhima**<br>#22038<br>A/B/C 160/161/162 | Magic burst damage II +6<br>Magic burst accuracy +20<br>"Drain" and "Aspir" potency +10 | Magic burst damage II +8<br>Magic burst accuracy +25<br>"Drain" and "Aspir" potency +15 | Magic burst damage II +10<br>Magic burst accuracy +30<br>"Drain" and "Aspir" potency +20 |
| BLM (Staff) | **Sorcerer's Staff**<br>#22091<br>A/B/C 163/164/165 | **Archmage's Staff**<br>#22092<br>A/B/C 166/167/168 | **Kaumodaki**<br>#22093<br>A/B/C 169/170/171 | MP+50<br>"Mana Wall"+15%<br>Damage Taken -10% | MP+75<br>"Mana Wall"+20%<br>Damage Taken -12% | MP+100<br>"Mana Wall"+25%<br>Damage Taken -15% |
| SMN (Staff) | **Summoner's Staff**<br>#22094<br>A/B/C 172/173/174 | **Glyphic Staff**<br>#22095<br>A/B/C 175/176/177 | **Draumstafir**<br>#22096<br>A/B/C 178/179/180 | Pet: Chance of double damage +20%<br>Chance of doubling "Blood Pact" status +15%<br>Blood Pact Dmg.+10 | Pet: Chance of double damage +35%<br>Chance of doubling "Blood Pact" status +20%<br>Blood Pact Dmg.+12 | Pet: Chance of double damage +50%<br>Chance of doubling "Blood Pact" status +25%<br>Blood Pact Dmg.+15 |
| SCH (Staff) | **Argute Staff**<br>#22097<br>A/B/C 181/182/183 | **Pedagogy Staff**<br>#22098<br>A/B/C 184/185/186 | **Musa**<br>#22099<br>A/B/C 187/188/189 | "Regen" potency +15<br>"Cure" potency +15%<br>"Fast Cast"+6% | "Regen" potency +20<br>"Cure" potency +20%<br>"Fast Cast"+8% | "Regen" potency +25<br>"Cure" potency +25%<br>"Fast Cast"+10% |
| RNG (Marksmanship) | **Scout's Crossbow**<br>#22147<br>A/B/C 190/191/192 | **Arke Crossbow**<br>#22148<br>A/B/C 193/194/195 | **Sharanga**<br>#22149<br>A/B/C 196/197/198 | Additional ammo damage: +200%<br>Additional ammo accuracy +100 | Additional ammo damage: +250%<br>Additional ammo accuracy +125 | Additional ammo damage: +300%<br>Additional ammo accuracy +150<br>DMG:+6 |

The HQ2 path C above is the R25 row.  Paths A and B add the weapon's
DMG row at HQ2 (for example Musa is DMG:+11); the DMG row does not
appear on the NQ or HQ1 two-row paths.

One value follows the client bundle rather than the wiki table:
Sharanga's HQ2 path C starts at **Additional ammo damage +300%** in
bundle 198.  BG Wiki's table lists +250%, which is Arke Crossbow's HQ1
value; the R15/R20/R25 bundle progression is 200/250/300.

## JSE necks

A JSE neck has one path (Path A) and three qualities, and its bundle is
shared by NQ, +1 and +2.  Capping writes rank 15/20/25 with the item's
tier, so the same bundle prints the R15, R20 or R25 row.  The reward is
the neck's three augment lines in `data/oboro_r25.json`; the launcher's
Oboro card lists all 66 copies.

| Job | NQ | +1 | +2 | Bundle | Augments (R15 / R20 / R25) |
| --- | --- | --- | --- | ---: | --- |
| WAR | **Warrior's Beads**<br>#25417 | **War. Beads +1**<br>#25418 | **Warrior's Bead Necklace +2**<br>#25419 | 199 | NQ: HP+50, STR/DEX +10, "Dbl. Atk."+5%<br>HQ1: HP+75, STR/DEX +12, "Dbl. Atk."+6%<br>HQ2: HP+100, STR/DEX +15, "Dbl. Atk."+7% |
| MNK | **Monk's Nodowa**<br>#25423 | **Mnk. Nodowa +1**<br>#25424 | **Monk's Nodowa +2**<br>#25425 | 200 | NQ: DEX/MND +10, Kick Attacks+15, Physical Damage Limit+6%<br>HQ1: DEX/MND +12, Kick Attacks+20, Physical Damage Limit+8%<br>HQ2: DEX/MND +15, Kick Attacks+25, Physical Damage Limit+10% |
| WHM | **Cleric's Torque**<br>#25429 | **Clr. Torque +1**<br>#25430 | **Cleric's Torque +2**<br>#25431 | 201 | NQ: INT/MND +10, Enmity-15, "Fast Cast"+6%<br>HQ1: INT/MND +12, Enmity-20, "Fast Cast"+8%<br>HQ2: INT/MND +15, Enmity-25, "Fast Cast"+10% |
| BLM | **Sorcerer's Stole**<br>#25435 | **Src. Stole +1**<br>#25436 | **Sorcerer's Stole +2**<br>#25437 | 202 | NQ: INT/MND +10, Magic Burst DMG+6%, Magic Burst ACC+15<br>HQ1: INT/MND +12, Magic Burst DMG+8%, Magic Burst ACC+20<br>HQ2: INT/MND +15, Magic Burst DMG+10%, Magic Burst ACC+25 |
| RDM | **Duelist's Torque**<br>#25441 | **Dls. Torque +1**<br>#25442 | **Duelist's Torque +2**<br>#25443 | 203 | NQ: INT/MND +10, Enh. Mag. eff. dur.+15%, Enf. Mag. eff. dur.+15%<br>HQ1: INT/MND +12, Enh. Mag. eff. dur.+20%, Enf. Mag. eff. dur.+20%<br>HQ2: INT/MND +15, Enh. Mag. eff. dur.+25%, Enf. Mag. eff. dur.+25% |
| THF | **Assassin's Gorget**<br>#25447 | **Asn. Gorget +1**<br>#25448 | **Assassin's Gorget +2**<br>#25449 | 204 | NQ: DEX/AGI +10, Evasion+15, "Trip. Atk."+2%<br>HQ1: DEX/AGI +12, Evasion+20, "Trip. Atk."+3%<br>HQ2: DEX/AGI +15, Evasion+25, "Trip. Atk."+4% |
| PLD | **Knight's Beads**<br>#25453 | **Kgt. Beads +1**<br>#25454 | **Knight's Bead Necklace +2**<br>#25455 | 205 | NQ: HP+30, VIT/MND +10, Damage taken-5%<br>HQ1: HP+45, VIT/MND +12, Damage taken-6%<br>HQ2: HP+60, VIT/MND +15, Damage taken-7% |
| DRK | **Abyssal Beads**<br>#25459 | **Abyssal Beads +1**<br>#25460 | **Abyssal Bead Necklace +2**<br>#25461 | 206 | NQ: STR+15, "Store TP"+5, Physical Damage Limit+6%<br>HQ1: STR+20, "Store TP"+6, Physical Damage Limit+8%<br>HQ2: STR+25, "Store TP"+7, Physical Damage Limit+10% |
| BST | **Beastmaster Collar**<br>#25465 | **Bst. Collar +1**<br>#25466 | **Beastmaster Collar +2**<br>#25467 | 207 | NQ: STR/DEX +10, Physical Damage Limit+6%, Pet: "Double Attack"+15%<br>HQ1: STR/DEX +12, Physical Damage Limit+8%, Pet: "Double Attack"+20%<br>HQ2: STR/DEX +15, Physical Damage Limit+10%, Pet: "Double Attack"+25% |
| BRD | **Bard's Charm**<br>#25471 | **Bard's Charm +1**<br>#25472 | **Bard's Charm +2**<br>#25473 | 208 | NQ: DEX/CHR +15, "Store TP"+5, Physical Damage Limit+6%<br>HQ1: DEX/CHR +20, "Store TP"+6, Physical Damage Limit+8%<br>HQ2: DEX/CHR +25, "Store TP"+7, Physical Damage Limit+10% |
| RNG | **Scout's Gorget**<br>#25477 | **Scout's Gorget +1**<br>#25478 | **Scout's Gorget +2**<br>#25479 | 209 | NQ: AGI+15, "Store TP"+5, Physical Damage Limit+6%<br>HQ1: AGI+20, "Store TP"+6, Physical Damage Limit+8%<br>HQ2: AGI+25, "Store TP"+7, Physical Damage Limit+10% |
| SAM | **Samurai's Nodowa**<br>#25483 | **Sam. Nodowa +1**<br>#25484 | **Samurai's Nodowa +2**<br>#25485 | 210 | NQ: STR+15, "Store TP"+5, Physical Damage Limit+6%<br>HQ1: STR+20, "Store TP"+6, Physical Damage Limit+8%<br>HQ2: STR+25, "Store TP"+7, Physical Damage Limit+10% |
| NIN | **Ninja Nodowa**<br>#25489 | **Ninja Nodowa +1**<br>#25490 | **Ninja Nodowa +2**<br>#25491 | 211 | NQ: DEX/AGI +10, Daken+15, Physical Damage Limit+6%<br>HQ1: DEX/AGI +12, Daken+20, Physical Damage Limit+8%<br>HQ2: DEX/AGI +15, Daken+25, Physical Damage Limit+10% |
| DRG | **Dragoon's Collar**<br>#25495 | **Dgn. Collar +1**<br>#25496 | **Dragoon's Collar +2**<br>#25497 | 212 | NQ: STR/VIT +10, Physical Damage Limit+6%, Wyvern: Damage Taken-15%<br>HQ1: STR/VIT +12, Physical Damage Limit+8%, Wyvern: Damage Taken-20%<br>HQ2: STR/VIT +15, Physical Damage Limit+10%, Wyvern: Damage Taken-25% |
| SMN | **Summoner's Collar**<br>#25501 | **Smn. Collar +1**<br>#25502 | **Summoner's Collar +2**<br>#25503 | 213 | NQ: MP+30, Avatar: All Base Stats+15, Blood Pact Damage+6%<br>HQ1: MP+40, Avatar: All Base Stats+20, Blood Pact Damage+8%<br>HQ2: MP+50, Avatar: All Base Stats+25, Blood Pact Damage+10% |
| BLU | **Mirage Stole**<br>#25507 | **Mirage Stole +1**<br>#25508 | **Mirage Stole +2**<br>#25509 | 214 | NQ: STR/DEX +15, "Store TP"+5, Crit Rate+3%<br>HQ1: STR/DEX +20, "Store TP"+6, Crit Rate+4%<br>HQ2: STR/DEX +25, "Store TP"+7, Crit Rate+5% |
| COR | **Commodore Charm**<br>#25513 | **Comm. Charm +1**<br>#25514 | **Commodore Charm +2**<br>#25515 | 215 | NQ: STR/AGI +10, Magic Damage+15, "Magic Attack Bonus"+5<br>HQ1: STR/AGI +12, Magic Damage+20, "Magic Attack Bonus"+6<br>HQ2: STR/AGI +15, Magic Damage+25, "Magic Attack Bonus"+7 |
| PUP | **Pup. Collar**<br>#25519 | **Pup. Collar +1**<br>#25520 | **Puppetmaster's Collar +2**<br>#25521 | 216 | NQ: DEX/AGI +10, Physical Damage Limit+6%, Automaton: "Mag. Atk. Bns."+15<br>HQ1: DEX/AGI +12, Physical Damage Limit+8%, Automaton: "Mag. Atk. Bns."+20<br>HQ2: DEX/AGI +15, Physical Damage Limit+10%, Automaton: "Mag. Atk. Bns."+25 |
| DNC | **Etoile Gorget**<br>#25525 | **Etoile Gorget +1**<br>#25526 | **Etoile Gorget +2**<br>#25527 | 217 | NQ: DEX/CHR +15, "Store TP"+5, Physical Damage Limit+6%<br>HQ1: DEX/CHR +20, "Store TP"+6, Physical Damage Limit+8%<br>HQ2: DEX/CHR +25, "Store TP"+7, Physical Damage Limit+10% |
| SCH | **Argute Stole**<br>#25531 | **Argute Stole +1**<br>#25532 | **Argute Stole +2**<br>#25533 | 218 | NQ: INT/MND +10, Magic Damage+15, Helix eff. Duration+6%<br>HQ1: INT/MND +12, Magic Damage+20, Helix eff. Duration+8%<br>HQ2: INT/MND +15, Magic Damage+25, Helix eff. Duration+10% |
| GEO | **Bagua Charm**<br>#25537 | **Bagua Charm +1**<br>#25538 | **Bagua Charm +2**<br>#25539 | 219 | NQ: MP+30, Luopan Duration+15%, Luopan: Absorbs Damage+6%<br>HQ1: MP+40, Luopan Duration+20%, Luopan: Absorbs Damage+8%<br>HQ2: MP+50, Luopan Duration+25%, Luopan: Absorbs Damage+10% |
| RUN | **Futhark Torque**<br>#25543 | **Futhark Torque +1**<br>#25544 | **Futhark Torque +2**<br>#25545 | 220 | NQ: HP+30, STR/MND +10, Damage taken-5%<br>HQ1: HP+45, STR/MND +12, Damage taken-6%<br>HQ2: HP+60, STR/MND +15, Damage taken-7% |

The RDM neck (Duelist's Torque) is the one the enfeebling sets use:
R25 is INT/MND +15, enhancing magic duration +25% and enfeebling magic
duration +25%.  `augment_stats` maps those rows to INT, MND,
`ENH_MAGIC_DURATION_AUGMENT` and `ENF_MAG_DURATION`, so both timers move
on the server as well as on the client tooltip.

## In the launcher

The Data page has a dedicated **Oboro** card.  It lists every weapon
family and quality plus all 22 JSE necks, shows whether a copy is in a
bag and which path/rank it carries, and caps the chosen path in one
click.  Necks have one path, so their card shows a single Cap button
instead of the three-path row.  An item that is not in a bag can be
bought from the same card into the first free inventory slot (the
Armory path; weapons are 141,610 gil and necks 98,010 gil), then
capped.  Capping sends `//reload` when the client is running, so the
tooltip and the stat sheet update immediately.

`FanxiService.equipped_mods()` reads the block back through
`augment_stats`: Musa Path C is `"Regen" potency +25`, `"Cure"`
potency +25% and `"Fast Cast"+10%`, and Path A/B turn on Store TP or
Subtle Blow II.  The chance-based rows (double damage, follow-up attack)
are in the client table but not modelled by the server yet.

Migration `0120_oboro_augments.sql` removes the old static Musa Path C
`item_mods` rows and writes the real R25 Path C block onto every Musa
copy, so the existing SCH Regen set keeps the same numbers while the
block becomes the source of truth.

`tools/gen_oboro.py --check` keeps this page, the data file and the
migration in step with the generator.
