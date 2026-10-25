"""Ambuscade JSE cape augments.

All 22 jobs get one Ambuscade cape, and every cape is augmented with five
standard augment slots.  The job capes are ``Cichol's Mantle`` (WAR) through
``Ogma's Cape`` (RUN); each one is the same item id under every build, so the
build is the item's 24-byte ``extdata`` block:

```
02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12
```

where each slot is a little-endian u16 holding ``id:11 | value:5``.  The client
prints ``(value + offset) * multiplier`` for the id, so ``HP+60`` is id 2
(offset 33) with value 27 and ``Enmity-10`` is id 0x028 (multiplier -1) with
value 9.  Empty slots are zero.

``TABLE`` is the slice of the community extdata table the 198 cape builds use.
The blocks are stored in the hidden 9999-item locker (migration 116) rather
than in the bags: 198 cape copies would not fit in a wardrobe forever, and a
job change should only need the new job's capes visible.
"""

from __future__ import annotations

import struct

AUGMENT_KIND = 0x02
AUGMENT_SUBKIND = 0x03
SLOTS = 5

AUGMENTS = {
    # HP: ids 0x001-0x004 carry the +1/+33/+65/+97 offset blocks.
    "HP+20": (0x001, 19),
    "HP+60": (0x002, 27),
    # MP follows the same four-id block: 0x009-0x00C.
    "MP+20": (0x009, 19),
    "MP+60": (0x00A, 27),
    # Accuracy / attack family.
    "Accuracy+10": (0x017, 9),
    "Accuracy+20": (0x017, 19),
    "Accuracy+20 Attack+20": (0x044, 19),
    "Rng.Acc.+20 Rng.Atk.+20": (0x045, 19),
    "Evasion+10": (0x01F, 9),
    "Evasion+15": (0x01F, 14),
    "Mag. Acc.+10": (0x023, 9),
    "Mag. Evasion+10": (0x025, 9),
    "Enmity+10": (0x027, 9),
    "Enmity-10": (0x028, 9),
    "Eva.+20 /Mag. Eva.+20": (0x051, 19),
    "Mag. Acc+20 /Mag. Dmg.+20": (0x050, 19),
    '"Store TP"+10': (0x08E, 9),
    '"Fast Cast"+10': (0x08C, 9),
    '"Dual Wield"+10': (0x092, 9),
    '"Mag.Atk.Bns."+10': (0x085, 9),
    '"Snapshot"+10': (0x0D3, 9),
    '"Cure Potency"+10%': (0x149, 9),
    '"Waltz" potency+10%': (0x14A, 9),
    "Weapon skill damage +10%": (0x147, 9),
    "Chance of successful block +5": (0x16B, 4),
    "Parrying rate+5%": (0x5C0, 4),
    "Spell interruption rate down-10%": (0x035, 9),
    "Phys. dmg. taken-10%": (0x036, 9),
    "Magic dmg. taken-10%": (0x037, 9),
    "Damage taken-5%": (0x047, 4),
    # Stats: 0x200-0x206 are the positive stat block.
    "STR+10": (0x200, 9),
    "STR+20": (0x200, 19),
    "DEX+10": (0x201, 9),
    "DEX+20": (0x201, 19),
    "VIT+10": (0x202, 9),
    "VIT+20": (0x202, 19),
    "AGI+10": (0x203, 9),
    "AGI+20": (0x203, 19),
    "INT+10": (0x204, 9),
    "INT+20": (0x204, 19),
    "MND+10": (0x205, 9),
    "MND+20": (0x205, 19),
    "CHR+10": (0x206, 9),
    "CHR+20": (0x206, 19),
    # Pet family.
    "Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20": (0x07C, 19),
    "Pet: Attack+10 Pet: Rng.Atk.+10": (0x06B, 9),
    "Pet: Accuracy+20 Pet: Rng. Acc.+20": (0x06A, 19),
    "Pet: Mag. Acc.+10": (0x064, 9),
    "Pet: M.Acc.+20 Pet: M.Dmg.+20": (0x07D, 19),
    "Pet: Haste+10": (0x06F, 9),
    "Pet: Damage taken -5%": (0x070, 4),
}


# WAR — Cichol's Mantle
WAR_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "enmity": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity+10",
        "Phys. dmg. taken-10%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_vit": [
        "VIT+20",
        "Accuracy+20 Attack+20",
        "VIT+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# MNK — Segomo's Mantle
MNK_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# WHM — Alaunus's Cape
WHM_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "cure": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MND+10",
        "\"Cure Potency\"+10%",
        "Phys. dmg. taken-10%",
    ],
    "fc": [
        "MP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MP+20",
        "\"Fast Cast\"+10",
        "Phys. dmg. taken-10%",
    ],
    "macc": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "ws_mnd": [
        "MND+20",
        "Accuracy+20 Attack+20",
        "MND+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# BLM — Taranus's Cape
BLM_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "fcmp": [
        "MP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MP+20",
        "\"Fast Cast\"+10",
        "Phys. dmg. taken-10%",
    ],
    "mabws": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "macc": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "nuke": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "\"Mag.Atk.Bns.\"+10",
        "Phys. dmg. taken-10%",
    ],
}

# RDM — Sucellos's Cape
RDM_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "cure": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MND+10",
        "\"Cure Potency\"+10%",
        "Phys. dmg. taken-10%",
    ],
    "fc": [
        "MP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MP+20",
        "\"Fast Cast\"+10",
        "Phys. dmg. taken-10%",
    ],
    "mabws": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MND+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "macc": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "nuke": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "\"Mag.Atk.Bns.\"+10",
        "Phys. dmg. taken-10%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_mnd": [
        "MND+20",
        "Accuracy+20 Attack+20",
        "MND+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# THF — Toutatis's Cape
THF_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dw": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "\"Dual Wield\"+10",
        "Phys. dmg. taken-10%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# PLD — Rudianos's Mantle
PLD_BUILDS = {
    "block": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity+10",
        "Chance of successful block +5",
    ],
    "cure": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MND+10",
        "\"Cure Potency\"+10%",
        "Phys. dmg. taken-10%",
    ],
    "dd": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "fc": [
        "MP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MP+20",
        "\"Fast Cast\"+10",
        "Phys. dmg. taken-10%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_mnd": [
        "MND+20",
        "Accuracy+20 Attack+20",
        "MND+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# DRK — Ankou's Mantle
DRK_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "enmity": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity+10",
        "Phys. dmg. taken-10%",
    ],
    "fc": [
        "MP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MP+20",
        "\"Fast Cast\"+10",
        "Phys. dmg. taken-10%",
    ],
    "macc": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "ws_int": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# BST — Artio's Mantle
BST_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "mabws": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MND+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "pet_dt": [
        "Pet: M.Acc.+20 Pet: M.Dmg.+20",
        "Pet: Accuracy+20 Pet: Rng. Acc.+20",
        "Pet: Mag. Acc.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "pet_tp": [
        "Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20",
        "Pet: Attack+10 Pet: Rng.Atk.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# BRD — Intarabus's Cape
BRD_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "chrws": [
        "CHR+20",
        "Accuracy+20 Attack+20",
        "CHR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "dexws": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "maccfc": [
        "CHR+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "\"Fast Cast\"+10",
        "Damage taken-5%",
    ],
}

# RNG — Belenus's Cape
RNG_BUILDS = {
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "mabws": [
        "AGI+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "AGI+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "ranged_tp": [
        "AGI+20",
        "Rng.Acc.+20 Rng.Atk.+20",
        "AGI+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "snapshot": [
        "AGI+20",
        "Rng.Acc.+20 Rng.Atk.+20",
        "AGI+10",
        "\"Snapshot\"+10",
        "Phys. dmg. taken-10%",
    ],
    "ws_agi": [
        "AGI+20",
        "Accuracy+20 Attack+20",
        "AGI+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# SAM — Smertrios's Mantle
SAM_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# NIN — Andartia's Mantle
NIN_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dw": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "\"Dual Wield\"+10",
        "Phys. dmg. taken-10%",
    ],
    "fc": [
        "HP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Evasion+10",
        "\"Fast Cast\"+10",
        "Phys. dmg. taken-10%",
    ],
    "ninjutsu": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "\"Mag.Atk.Bns.\"+10",
        "Phys. dmg. taken-10%",
    ],
    "ws_agi": [
        "AGI+20",
        "Accuracy+20 Attack+20",
        "AGI+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# DRG — Brigantia's Mantle
DRG_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "pet_dt": [
        "Pet: M.Acc.+20 Pet: M.Dmg.+20",
        "Pet: Accuracy+20 Pet: Rng. Acc.+20",
        "Pet: Mag. Acc.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "pet_mab": [
        "Pet: M.Acc.+20 Pet: M.Dmg.+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Pet: Mag. Acc.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# SMN — Campestres's Cape
SMN_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "fc": [
        "MP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MP+20",
        "\"Fast Cast\"+10",
        "Phys. dmg. taken-10%",
    ],
    "mabws": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "macc": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "pet_dt": [
        "Pet: M.Acc.+20 Pet: M.Dmg.+20",
        "Pet: Accuracy+20 Pet: Rng. Acc.+20",
        "Pet: Mag. Acc.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "pet_mab": [
        "Pet: M.Acc.+20 Pet: M.Dmg.+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Pet: Mag. Acc.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "pet_tp": [
        "Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20",
        "Pet: Attack+10 Pet: Rng.Atk.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
}

# BLU — Rosmerta's Cape
BLU_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "evafc": [
        "AGI+20",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "\"Fast Cast\"+10",
        "Evasion+15",
    ],
    "mabws": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MND+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "macc": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "nuke": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "\"Mag.Atk.Bns.\"+10",
        "Phys. dmg. taken-10%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_mnd": [
        "MND+20",
        "Accuracy+20 Attack+20",
        "MND+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# COR — Camulus's Mantle
COR_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "mab_agi": [
        "AGI+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "AGI+10",
        "\"Mag.Atk.Bns.\"+10",
        "Phys. dmg. taken-10%",
    ],
    "mabws": [
        "AGI+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "AGI+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "ranged_tp": [
        "AGI+20",
        "Rng.Acc.+20 Rng.Atk.+20",
        "AGI+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "roll": [
        "CHR+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "CHR+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "snapshot": [
        "AGI+20",
        "Rng.Acc.+20 Rng.Atk.+20",
        "AGI+10",
        "\"Snapshot\"+10",
        "Phys. dmg. taken-10%",
    ],
    "ws_agi": [
        "AGI+20",
        "Accuracy+20 Attack+20",
        "AGI+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# PUP — Visucius's Mantle
PUP_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "pet_dt": [
        "Pet: M.Acc.+20 Pet: M.Dmg.+20",
        "Pet: Accuracy+20 Pet: Rng. Acc.+20",
        "Pet: Mag. Acc.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "pet_mab": [
        "Pet: M.Acc.+20 Pet: M.Dmg.+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Pet: Mag. Acc.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "pet_tp": [
        "Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20",
        "Pet: Attack+10 Pet: Rng.Atk.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# DNC — Senuna's Mantle
DNC_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dw": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "\"Dual Wield\"+10",
        "Phys. dmg. taken-10%",
    ],
    "waltz": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "\"Waltz\" potency+10%",
        "Phys. dmg. taken-10%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# SCH — Lugh's Cape
SCH_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "cure": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MND+10",
        "\"Cure Potency\"+10%",
        "Phys. dmg. taken-10%",
    ],
    "fc": [
        "MP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MP+20",
        "\"Fast Cast\"+10",
        "Phys. dmg. taken-10%",
    ],
    "mabws": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "macc": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "nuke": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "\"Mag.Atk.Bns.\"+10",
        "Phys. dmg. taken-10%",
    ],
}

# GEO — Nantosuelta's Cape
GEO_BUILDS = {
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "pdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "mdt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Mag. Evasion+10",
        "Enmity-10",
        "Magic dmg. taken-10%",
    ],
    "maxhp": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "HP+20",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "dt": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity-10",
        "Damage taken-5%",
    ],
    "fc": [
        "MP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MP+20",
        "\"Fast Cast\"+10",
        "Phys. dmg. taken-10%",
    ],
    "mabws": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "macc": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "nuke": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "\"Mag.Atk.Bns.\"+10",
        "Phys. dmg. taken-10%",
    ],
}

# RUN — Ogma's Cape
RUN_BUILDS = {
    "dd": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        "\"Store TP\"+10",
        "Phys. dmg. taken-10%",
    ],
    "sird": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity+10",
        "Spell interruption rate down-10%",
    ],
    "tank": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity+10",
        "Parrying rate+5%",
    ],
    "ws_dex": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_mnd": [
        "MND+20",
        "Accuracy+20 Attack+20",
        "MND+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
}

# Job -> the one cape item all of its builds are copies of, and the build list.
# The order is the client's job order, and every build name matches the key in
# that job's gearswap library.
JOBS = {
    "WAR": {"cape_id": 26246, "cape_name": "Cichol's Mantle", "builds": WAR_BUILDS},
    "MNK": {"cape_id": 26247, "cape_name": "Segomo's Mantle", "builds": MNK_BUILDS},
    "WHM": {"cape_id": 26248, "cape_name": "Alaunus's Cape", "builds": WHM_BUILDS},
    "BLM": {"cape_id": 26249, "cape_name": "Taranus's Cape", "builds": BLM_BUILDS},
    "RDM": {"cape_id": 26250, "cape_name": "Sucellos's Cape", "builds": RDM_BUILDS},
    "THF": {"cape_id": 26251, "cape_name": "Toutatis's Cape", "builds": THF_BUILDS},
    "PLD": {"cape_id": 26252, "cape_name": "Rudianos's Mantle", "builds": PLD_BUILDS},
    "DRK": {"cape_id": 26253, "cape_name": "Ankou's Mantle", "builds": DRK_BUILDS},
    "BST": {"cape_id": 26254, "cape_name": "Artio's Mantle", "builds": BST_BUILDS},
    "BRD": {"cape_id": 26255, "cape_name": "Intarabus's Cape", "builds": BRD_BUILDS},
    "RNG": {"cape_id": 26256, "cape_name": "Belenus's Cape", "builds": RNG_BUILDS},
    "SAM": {"cape_id": 26257, "cape_name": "Smertrios's Mantle", "builds": SAM_BUILDS},
    "NIN": {"cape_id": 26258, "cape_name": "Andartia's Mantle", "builds": NIN_BUILDS},
    "DRG": {"cape_id": 26259, "cape_name": "Brigantia's Mantle", "builds": DRG_BUILDS},
    "SMN": {"cape_id": 26260, "cape_name": "Campestres's Cape", "builds": SMN_BUILDS},
    "BLU": {"cape_id": 26261, "cape_name": "Rosmerta's Cape", "builds": BLU_BUILDS},
    "COR": {"cape_id": 26262, "cape_name": "Camulus's Mantle", "builds": COR_BUILDS},
    "PUP": {"cape_id": 26263, "cape_name": "Visucius's Mantle", "builds": PUP_BUILDS},
    "DNC": {"cape_id": 26264, "cape_name": "Senuna's Mantle", "builds": DNC_BUILDS},
    "SCH": {"cape_id": 26265, "cape_name": "Lugh's Cape", "builds": SCH_BUILDS},
    "GEO": {"cape_id": 26266, "cape_name": "Nantosuelta's Cape", "builds": GEO_BUILDS},
    "RUN": {"cape_id": 26267, "cape_name": "Ogma's Cape", "builds": RUN_BUILDS},
}

CAPE_IDS = frozenset(int(entry["cape_id"]) for entry in JOBS.values())

# The Beastmaster cape is the original default.
JOB = "BST"
CAPE_ID = JOBS[JOB]["cape_id"]
CAPE_NAME = JOBS[JOB]["cape_name"]
BUILDS = JOBS[JOB]["builds"]


def job_for_item(item_id: int) -> str | None:
    """The job whose Ambuscade cape is this item id, or None."""
    for job, entry in JOBS.items():
        if int(item_id) == int(entry["cape_id"]):
            return job
    return None


def job_for_name(name: str) -> str | None:
    """The job whose cape name appears in *name*, or None."""
    want = str(name or "").casefold()
    for job, entry in JOBS.items():
        if str(entry["cape_name"]).casefold() in want:
            return job
    return None


def pairs(build: str, job: str = JOB) -> list[tuple[int, int]]:
    """The five (id, value) words of a build, padded with empty slots."""
    try:
        names = JOBS[job]["builds"][build]
    except KeyError:
        raise ValueError("unknown %s cape build %r" % (job, build)) from None
    out = [AUGMENTS[name] for name in names]
    out.extend([(0, 0)] * (SLOTS - len(out)))
    return out


def encode(build: str, job: str = JOB) -> bytes:
    """A 24-byte ``AugmentStandard`` block for one cape build."""
    data = bytearray(24)
    data[0] = AUGMENT_KIND
    data[1] = AUGMENT_SUBKIND
    for slot, (augment_id, value) in enumerate(pairs(build, job)):
        if not 0 <= augment_id <= 0x7FF:
            raise ValueError("augment id out of range: %r" % (augment_id,))
        if not 0 <= value <= 0x1F:
            raise ValueError("augment value out of range: %r" % (value,))
        struct.pack_into("<H", data, 2 + slot * 2,
                         (augment_id & 0x7FF) | ((value & 0x1F) << 11))
    return bytes(data)


def decode(extra: bytes | None) -> list[dict] | None:
    """The five (id, value) slots of a standard block, or None."""
    if not extra or len(extra) < 12:
        return None
    raw = bytes(extra)
    if raw[0] != AUGMENT_KIND or raw[1] != AUGMENT_SUBKIND:
        return None
    slots = []
    for slot in range(SLOTS):
        word = struct.unpack_from("<H", raw, 2 + slot * 2)[0]
        slots.append({"id": word & 0x7FF, "value": word >> 11})
    return slots


def slot_text(slot: dict) -> str:
    """The tooltip text one decoded slot stands for.

    The stat sheet feeds this back through :mod:`augment_stats`, so the slot ids and
    the parser cannot drift apart: a slot describes itself with the same table the
    ``//cape`` command prints.
    """
    return _text(int(slot.get("id") or 0), int(slot.get("value") or 0))


def describe(extra: bytes | None) -> str:
    slots = decode(extra)
    if slots is None:
        return "not augmented"
    names = []
    for slot in slots:
        if slot["id"] == 0:
            continue
        names.append(_text(slot["id"], slot["value"]))
    return ", ".join(names) if names else "not augmented"


# id -> (text, offset, multiplier, percent).  This is the slice of the client
# table the 198 cape builds use, plus the two SCH Regen augments (0x173 and
# 0x4E0).  Tests assert every AUGMENTS entry resolves.
TABLE = {
    0x001: ("HP", 1, 1, False),
    0x002: ("HP", 33, 1, False),
    0x009: ("MP", 1, 1, False),
    0x00A: ("MP", 33, 1, False),
    0x017: ("Accuracy", 1, 1, False),
    0x019: ("Attack", 1, 1, False),
    0x01F: ("Evasion", 1, 1, False),
    0x023: ("Mag. Acc.", 1, 1, False),
    0x025: ("Mag. Evasion", 1, 1, False),
    0x027: ("Enmity", 1, 1, False),
    0x028: ("Enmity", 1, -1, False),
    0x035: ("Spell interruption rate down", 1, -1, True),
    0x036: ("Phys. dmg. taken", 1, -1, True),
    0x037: ("Magic dmg. taken", 1, -1, True),
    0x044: ("Accuracy", 1, 1, False),
    0x045: ("Rng.Acc.", 1, 1, False),
    0x047: ("Damage taken", 1, -1, True),
    0x050: ("Mag. Acc", 1, 1, False),
    0x051: ("Eva.", 1, 1, False),
    0x064: ("Pet: Mag. Acc.", 1, 1, False),
    0x06A: ("Pet: Accuracy", 1, 1, False),
    0x06B: ("Pet: Attack", 1, 1, False),
    0x06F: ("Pet: Haste", 1, 1, False),
    0x070: ("Pet: Damage taken", 1, -1, True),
    0x07C: ("Pet: Acc.", 1, 1, False),
    0x07D: ("Pet: M.Acc.", 1, 1, False),
    0x085: ("Mag.Atk.Bns.", 1, 1, False),
    0x08C: ("Fast Cast", 1, 1, False),
    0x08E: ('"Store TP"', 1, 1, False),
    0x092: ("Dual Wield", 1, 1, False),
    0x0D3: ('"Snapshot"', 1, 1, False),
    0x147: ("Weapon skill damage", 1, 1, True),
    0x149: ('"Cure Potency"', 1, 1, True),
    0x14A: ('"Waltz" potency', 1, 1, True),
    0x16B: ("Chance of successful block", 1, 1, False),
    0x173: ('"Regen" potency', 1, 1, False),
    0x200: ("STR", 1, 1, False),
    0x201: ("DEX", 1, 1, False),
    0x202: ("VIT", 1, 1, False),
    0x203: ("AGI", 1, 1, False),
    0x204: ("INT", 1, 1, False),
    0x205: ("MND", 1, 1, False),
    0x206: ("CHR", 1, 1, False),
    0x4E0: ("Enh. Mag. eff. dur.", 1, 1, True),
    0x5C0: ("Parrying rate", 1, 1, True),
}

# Slots whose single id renders two or more stats; describe() prints each.
EXTRA = {
    0x044: [("Attack", 1, 1, False)],
    0x045: [("Rng.Atk.", 1, 1, False)],
    0x050: [("/Mag. Dmg.", 1, 1, False)],
    0x051: [("/Mag. Eva.", 1, 1, False)],
    0x06A: [("Pet: Rng. Acc.", 1, 1, False)],
    0x06B: [("Pet: Rng.Atk.", 1, 1, False)],
    0x07C: [("Pet: R.Acc.", 1, 1, False), ("Pet: Atk.", 1, 1, False),
            ("Pet: R.Atk.", 1, 1, False)],
    0x07D: [("Pet: M.Dmg.", 1, 1, False)],
}


def _fmt(stat: str, offset: int, multiplier: int, percent: bool, value: int) -> str:
    amount = (value + offset) * multiplier
    sign = "+" if amount >= 0 else ""
    return "%s%s%d%s" % (stat, sign, amount, "%" if percent else "")


def _text(augment_id: int, value: int) -> str:
    try:
        stat, offset, multiplier, percent = TABLE[augment_id]
    except KeyError:
        return "id %d value %d" % (augment_id, value)
    parts = [_fmt(stat, offset, multiplier, percent, value)]
    for extra in EXTRA.get(augment_id, ()):
        parts.append(_fmt(*extra, value))
    return " ".join(parts)
