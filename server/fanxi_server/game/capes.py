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
The blocks are stored in the hidden 9,999-slot locker (migration 116) rather
than in the bags: 198 cape copies would not fit in a wardrobe forever, and a
job change should only need the new job's capes visible.

The launcher's Data page edits the same block directly.  ``MATERIALS`` is BG
Wiki's five-material table (Abdhaljs Thread, Dust, Dye, Sap and Resin) with
each row's per-stage amount and cap; the picker writes one row per material in
the order the standard block stores them.  A material the user leaves alone
keeps the word already on the copy, so a build that packs pet stats into an
off-category slot is not truncated by a partial edit.
"""

from __future__ import annotations

import struct
from functools import lru_cache

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


def _option(key: str, label: str, augment_id: int, *, step: int = 1,
            max_stage: int = 10, high_id: int = 0, multiplier: int = 1,
            percent: bool = False, raw_mode: str = "amount",
            alt_id: int = 0, alt_raw_mode: str = "stage") -> dict:
    """One ``Aug/Item`` row from BG Wiki's cape augment tables.

    ``step`` is the amount one trade adds and ``max_stage`` how many trades the
    row allows, so ``max_value`` is what a fully augmented cape shows.  The
    block only has five bits for the value: the Def row therefore writes the
    client's pre-multiplied 0x480 id (``raw_mode="stage"`` stores the stage),
    while the other Resin rows write the general stat id the 198 builds use and
    accept the dedicated 0x481-0x486 / 0x4DE / 0x4DF id as ``alt_id``.
    """
    amount = int(step)
    stages = int(max_stage)
    sign = "-" if int(multiplier) < 0 else "+"
    unit = "%" if percent else ""
    return {
        "key": key,
        "label": label,
        "id": int(augment_id),
        "high_id": int(high_id),
        "step": amount,
        "max_stage": stages,
        "max_value": amount * stages,
        "multiplier": int(multiplier),
        "percent": bool(percent),
        "raw_mode": raw_mode,
        # A few Resin rows have a dedicated client id (0x480-0x486, 0x4DE,
        # 0x4DF) as well as the general stat id the 198 builds use.  The picker
        # writes the general id so it round-trips those builds; the dedicated id
        # is still recognised when a retail copy carries it.
        "alt_id": int(alt_id),
        "alt_raw_mode": alt_raw_mode,
        "hint": "%s%d%s per stage" % (sign, amount, unit),
    }


# The five Abdhaljs materials, in the slot order the client's standard augment
# block stores them.  One cape carries at most one augment from each material.
MATERIALS = (
    {
        "key": "thread",
        "label": "Abdhaljs Thread",
        "slot": 0,
        "max_stage": 20,
        "items_to_max": 20,
        "hint": "HP, MP, attributes and pet accuracy",
        "options": (
            _option("hp", "HP", 0x001, step=3, max_stage=20, high_id=0x002),
            _option("mp", "MP", 0x009, step=3, max_stage=20, high_id=0x00A),
            _option("str", "STR", 0x200, max_stage=20),
            _option("dex", "DEX", 0x201, max_stage=20),
            _option("vit", "VIT", 0x202, max_stage=20),
            _option("agi", "AGI", 0x203, max_stage=20),
            _option("int", "INT", 0x204, max_stage=20),
            _option("mnd", "MND", 0x205, max_stage=20),
            _option("chr", "CHR", 0x206, max_stage=20),
            _option("pet_acc",
                    "Pet: Accuracy / Ranged Accuracy / Attack / Ranged Attack",
                    0x07C, max_stage=20),
            _option("pet_macc", "Pet: Magic Accuracy / Magic Damage", 0x07D,
                    max_stage=20),
        ),
    },
    {
        "key": "dust",
        "label": "Abdhaljs Dust",
        "slot": 1,
        "max_stage": 20,
        "items_to_max": 20,
        "hint": "Accuracy family pairs",
        "options": (
            _option("acc_attack", "Accuracy / Attack", 0x044, max_stage=20),
            _option("rng_acc_attack", "Ranged Accuracy / Ranged Attack", 0x045,
                    max_stage=20),
            _option("macc_mdmg", "Magic Accuracy / Magic Damage", 0x050,
                    max_stage=20),
            _option("eva_meva", "Evasion / Magic Evasion", 0x051, max_stage=20),
        ),
    },
    {
        "key": "dye",
        "label": "Abdhaljs Dye",
        "slot": 2,
        "max_stage": 10,
        "items_to_max": 10,
        "hint": "HP, MP, attributes and single combat stats",
        "options": (
            _option("hp", "HP", 0x001, step=2, max_stage=10),
            _option("mp", "MP", 0x009, step=2, max_stage=10),
            _option("str", "STR", 0x200, max_stage=10),
            _option("dex", "DEX", 0x201, max_stage=10),
            _option("vit", "VIT", 0x202, max_stage=10),
            _option("agi", "AGI", 0x203, max_stage=10),
            _option("int", "INT", 0x204, max_stage=10),
            _option("mnd", "MND", 0x205, max_stage=10),
            _option("chr", "CHR", 0x206, max_stage=10),
            _option("accuracy", "Accuracy", 0x017, max_stage=10),
            _option("attack", "Attack", 0x019, max_stage=10),
            _option("rng_acc", "Ranged Accuracy", 0x01B, max_stage=10),
            _option("rng_attack", "Ranged Attack", 0x01D, max_stage=10),
            _option("macc", "Magic Accuracy", 0x023, max_stage=10),
            _option("mdmg", "Magic Damage", 0x16A, max_stage=10),
            _option("evasion", "Evasion", 0x01F, max_stage=10),
            _option("meva", "Magic Evasion", 0x025, max_stage=10),
            _option("pet_acc", "Pet: Accuracy / Ranged Accuracy", 0x06A,
                    max_stage=10),
            _option("pet_attack", "Pet: Attack / Ranged Attack", 0x06B,
                    max_stage=10),
            _option("pet_macc", "Pet: Magic Accuracy", 0x064, max_stage=10),
            _option("pet_mdmg", "Pet: Magic Damage", 0x07E, max_stage=10),
        ),
    },
    {
        "key": "sap",
        "label": "Abdhaljs Sap",
        "slot": 3,
        "max_stage": 10,
        "items_to_max": 10,
        "hint": "Store TP, Fast Cast, damage and job traits",
        "options": (
            _option("ws_damage", "Weapon skill damage", 0x147, max_stage=10,
                    percent=True),
            _option("crit_rate", "Critical hit rate", 0x029, max_stage=10,
                    percent=True),
            _option("store_tp", "Store TP", 0x08E, max_stage=10),
            _option("double_attack", "Double Attack", 0x08F, max_stage=10,
                    percent=True),
            _option("haste", "Haste", 0x031, max_stage=10, percent=True),
            _option("dual_wield", "Dual Wield", 0x092, max_stage=10),
            _option("enmity_up", "Enmity", 0x027, max_stage=10),
            _option("enmity_down", "Enmity", 0x028, max_stage=10,
                    multiplier=-1),
            _option("snapshot", "Snapshot", 0x0D3, max_stage=10, percent=True),
            _option("mab", "Magic Atk. Bonus", 0x085, max_stage=10),
            _option("fast_cast", "Fast Cast", 0x08C, max_stage=10,
                    percent=True),
            _option("cure_potency", "Cure potency", 0x149, max_stage=10,
                    percent=True),
            _option("waltz_potency", "Waltz potency", 0x14A, max_stage=10,
                    percent=True),
            _option("pet_regen", "Pet: Regen", 0x06E, max_stage=10),
            _option("pet_haste", "Pet: Haste", 0x06F, max_stage=10,
                    percent=True),
        ),
    },
    {
        "key": "resin",
        "label": "Abdhaljs Resin",
        "slot": 4,
        "max_stage": 5,
        "items_to_max": 5,
        "hint": "DEF, evasion, damage taken and block/parry",
        "options": (
            _option("def", "DEF", 0x480, step=10, max_stage=5, multiplier=10,
                    raw_mode="stage"),
            _option("evasion", "Evasion", 0x01F, step=3, max_stage=5,
                    alt_id=0x481),
            _option("meva", "Magic Evasion", 0x025, step=3, max_stage=5,
                    alt_id=0x482),
            _option("pdt", "Physical damage taken", 0x036, step=2, max_stage=5,
                    multiplier=-1, percent=True, alt_id=0x483),
            _option("mdt", "Magic damage taken", 0x037, step=2, max_stage=5,
                    multiplier=-1, percent=True, alt_id=0x484),
            _option("dt", "Damage taken", 0x047, max_stage=5, multiplier=-1,
                    percent=True),
            _option("regen", "Regen", 0x089, max_stage=5),
            _option("counter", "Counter", 0x091, step=2, max_stage=5,
                    percent=True),
            _option("block", "Blocking rate", 0x16B, max_stage=5,
                    percent=True),
            _option("parry", "Parrying rate", 0x5C0, max_stage=5,
                    percent=True),
            _option("status_resist", "Status ailment resistance", 0x03D,
                    step=2, max_stage=5, alt_id=0x486),
            _option("interrupt", "Casting interruption rate", 0x035, step=2,
                    max_stage=5, multiplier=-1, percent=True, alt_id=0x485),
            _option("pet_pdt", "Pet: Physical damage taken", 0x076, step=2,
                    max_stage=5, multiplier=-1, percent=True, alt_id=0x4DE),
            _option("pet_mdt", "Pet: Magic damage taken", 0x07F, step=2,
                    max_stage=5, multiplier=-1, percent=True, alt_id=0x4DF),
            _option("pet_dt", "Pet: damage taken", 0x070, max_stage=5,
                    multiplier=-1, percent=True),
            _option("pet_regen", "Pet: Regen", 0x06E, max_stage=5),
        ),
    },
)

MATERIAL_BY_KEY = {material["key"]: material for material in MATERIALS}

# Client container ids, for the copy picker (the same labels the Gear page uses).
CONTAINER_LABELS = {
    0: "Inventory",
    1: "Temporary",
    2: "Storage",
    5: "Safe",
    6: "Satchel",
    7: "Sack",
    8: "Wardrobe 1",
    10: "Wardrobe 2",
    11: "Wardrobe 3",
    12: "Wardrobe 4",
    13: "Wardrobe 5",
    14: "Wardrobe 6",
    15: "Wardrobe 7",
    16: "Wardrobe 8",
}


def container_label(container: int) -> str:
    return CONTAINER_LABELS.get(int(container), "Bag %d" % int(container))


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


def _encode_slots(slots) -> bytes:
    """A 24-byte ``AugmentStandard`` block from up to five (id, value) words."""
    data = bytearray(24)
    data[0] = AUGMENT_KIND
    data[1] = AUGMENT_SUBKIND
    words = list(slots)[:SLOTS]
    words.extend([(0, 0)] * (SLOTS - len(words)))
    for slot, (augment_id, value) in enumerate(words):
        if not 0 <= int(augment_id) <= 0x7FF:
            raise ValueError("augment id out of range: %r" % (augment_id,))
        if not 0 <= int(value) <= 0x1F:
            raise ValueError("augment value out of range: %r" % (value,))
        struct.pack_into("<H", data, 2 + slot * 2,
                         (int(augment_id) & 0x7FF) | ((int(value) & 0x1F) << 11))
    return bytes(data)


def encode(build: str, job: str = JOB) -> bytes:
    """A 24-byte ``AugmentStandard`` block for one cape build."""
    return _encode_slots(pairs(build, job))


def encode_slots(slots) -> bytes:
    """A 24-byte ``AugmentStandard`` block from raw ``(id, value)`` words.

    The cape picker builds its block from named builds; the Shantotto Ascension
    editor writes the same block family directly from its two chosen rows.
    """
    return _encode_slots(slots)


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
    if not int(slot.get("id") or 0):
        return ""
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
    0x01B: ("Rng.Acc.", 1, 1, False),
    0x01D: ("Rng.Atk.", 1, 1, False),
    0x01F: ("Evasion", 1, 1, False),
    0x023: ("Mag. Acc.", 1, 1, False),
    0x025: ("Mag. Evasion", 1, 1, False),
    0x027: ("Enmity", 1, 1, False),
    0x028: ("Enmity", 1, -1, False),
    0x029: ("Crit.hit rate", 1, 1, False),
    0x031: ("Haste", 1, 1, False),
    0x035: ("Spell interruption rate down", 1, -1, True),
    0x036: ("Phys. dmg. taken", 1, -1, True),
    0x037: ("Magic dmg. taken", 1, -1, True),
    0x03B: ('Latent effect: "Regain"', 10, 1, False),
    0x03C: ('Latent effect: "Refresh"', 1, 1, False),
    0x03D: ("Occ. inc. resist. to stat. ailments", 1, 1, False),
    0x044: ("Accuracy", 1, 1, False),
    0x045: ("Rng.Acc.", 1, 1, False),
    0x047: ("Damage taken", 1, -1, True),
    0x050: ("Mag. Acc", 1, 1, False),
    0x051: ("Eva.", 1, 1, False),
    0x064: ("Pet: Mag. Acc.", 1, 1, False),
    0x06A: ("Pet: Accuracy", 1, 1, False),
    0x06B: ("Pet: Attack", 1, 1, False),
    0x06E: ('Pet: "Regen"', 1, 1, False),
    0x06F: ("Pet: Haste", 1, 1, False),
    0x070: ("Pet: Damage taken", 1, -1, True),
    0x071: ("Pet: Rng. Acc.", 1, 1, False),
    0x076: ("Pet: Phys. dmg. taken", 1, -1, True),
    0x07C: ("Pet: Acc.", 1, 1, False),
    0x07D: ("Pet: M.Acc.", 1, 1, False),
    0x07E: ("Pet: Magic Damage", 1, 1, False),
    0x07F: ("Pet: Magic dmg. taken", 1, -1, True),
    0x085: ("Mag.Atk.Bns.", 1, 1, False),
    0x089: ('"Regen"', 1, 1, False),
    0x08C: ("Fast Cast", 1, 1, False),
    0x08E: ('"Store TP"', 1, 1, False),
    0x08F: ('"Dbl.Atk."', 1, 1, False),
    0x091: ('"Counter"', 1, 1, False),
    0x092: ("Dual Wield", 1, 1, False),
    0x093: ("Treasure Hunter", 1, 1, False),
    0x0D3: ('"Snapshot"', 1, 1, False),
    0x147: ("Weapon skill damage", 1, 1, True),
    0x149: ('"Cure Potency"', 1, 1, True),
    0x14A: ('"Waltz" potency', 1, 1, True),
    0x16A: ("Magic Damage", 1, 1, False),
    0x16B: ("Chance of successful block", 1, 1, False),
    0x173: ('"Regen" potency', 1, 1, False),
    0x200: ("STR", 1, 1, False),
    0x201: ("DEX", 1, 1, False),
    0x202: ("VIT", 1, 1, False),
    0x203: ("AGI", 1, 1, False),
    0x204: ("INT", 1, 1, False),
    0x205: ("MND", 1, 1, False),
    0x206: ("CHR", 1, 1, False),
    0x02D: ("DMG:", 1, 1, False),
    0x039: ("Magic crit. hit rate", 1, 1, True),
    0x03E: ("Accuracy", 33, 1, False),
    0x03F: ("Rng.Acc.", 33, 1, False),
    0x040: ("Mag. Acc.", 33, 1, False),
    0x041: ("Attack", 33, 1, False),
    0x042: ("Rng.Atk.", 33, 1, False),
    0x046: ("Mag. Acc.", 33, 1, False),
    0x04C: ("DMG:", 33, 1, False),
    0x064: ("Pet: Mag. Acc.", 1, 1, False),
    0x065: ('Pet: "Mag.Atk.Bns."', 1, 1, False),
    0x06C: ("Pet: Mag. Acc.", 1, 1, False),
    0x073: ("Pet: Store TP", 1, 1, False),
    0x074: ("Pet: Subtle Blow", 1, 1, False),
    0x07B: ('Pet: "Dbl.Atk."', 1, 1, True),
    0x08A: ("Refresh", 1, 1, False),
    0x08B: ('"Rapid Shot"', 1, 1, False),
    0x08D: ('"Conserve MP"', 1, 1, False),
    0x090: ('"Triple Atk."', 1, 1, True),
    0x097: ("Martial Arts", 1, 1, False),
    0x0B2: ("Resist Paralyze", 1, 1, False),
    0x0B4: ("Resist Silence", 1, 1, False),
    0x0C3: ("Subtle Blow", 1, 1, False),
    0x0C6: ("Zanshin", 1, 1, False),
    0x0E9: ("Blood Boon", 1, 1, False),
    0x0ED: ("Occult Acumen", 1, 1, False),
    0x120: ("Divine magic skill", 1, 1, False),
    0x121: ("Healing magic skill", 1, 1, False),
    0x122: ("Enhancing magic skill", 1, 1, False),
    0x123: ("Enfeebling magic skill", 1, 1, False),
    0x124: ("Elemental magic skill", 1, 1, False),
    0x125: ("Dark magic skill", 1, 1, False),
    0x126: ("Summoning magic skill", 1, 1, False),
    0x127: ("Ninjutsu skill", 1, 1, False),
    0x128: ("Singing skill", 1, 1, False),
    0x129: ("String instrument skill", 1, 1, False),
    0x12A: ("Wind instrument skill", 1, 1, False),
    0x12B: ("Blue Magic skill", 1, 1, False),
    0x12C: ("Geomancy skill", 1, 1, False),
    0x12D: ("Handbell skill", 1, 1, False),
    0x140: ("Blood Pact ability delay", 1, -1, False),
    0x141: ("Avatar perpetuation cost", 1, -1, False),
    0x143: ('"Cure" spellcasting time', 1, -1, True),
    0x146: ("Weapon Skill Acc.", 1, 1, False),
    0x148: ("Crit. hit damage", 1, 1, True),
    0x14C: ("Skillchain dmg.", 1, 1, True),
    0x14E: ("Magic burst dmg.", 1, 1, True),
    0x14F: ("Mag. crit. hit dmg.", 1, 1, True),
    0x155: ("Repair potency", 1, 1, True),
    0x145: ('"Quick Draw" ability delay', 1, -1, False),
    0x14B: ('"Waltz" ability delay', 1, -1, False),
    0x14D: ('"Conserve TP"', 1, 1, False),
    0x150: ('"Sic" and "Ready" ability delay', 1, -1, False),
    0x152: ('"Barrage"', 1, 1, False),
    0x154: ('"Phantom Roll" ability delay', 1, -1, False),
    0x156: ('"Waltz" TP cost', 1, -10, False),
    0x157: ('"Drain" and "Aspir" potency', 1, 1, False),
    0x16E: ("Blood Pact recast time II", 1, -1, False),
    0x172: ("Reverse Flourish", 1, 1, False),
    0x174: ("Embolden", 1, 1, True),
    0x060: ("Pet: Accuracy/Rng.Acc.", 1, 1, False),
    0x061: ("Pet: Attack/Rng.Atk.", 1, 1, False),
    0xC2: ("Kick Attacks", 1, 1, False),
    0x391: ("Movement speed", 1, 1, True),
    0x164: ("Potency of Cure received", 1, 1, True),
    0x171: ("Blood Pact Dmg.", 1, 1, False),
    0x176: ("Enhancing Magic Duration", 0, 1, False),
    0x34C: ("Additional Effect: Stun", 0, 1, False),
    0x4E2: ("Indi Effect Duration", 1, 1, False),
    0x700: ("Pet: STR", 1, 1, False),
    0x701: ("Pet: DEX", 1, 1, False),
    0x702: ("Pet: VIT", 1, 1, False),
    0x703: ("Pet: AGI", 1, 1, False),
    0x704: ("Pet: INT", 1, 1, False),
    0x705: ("Pet: MND", 1, 1, False),
    0x706: ("Pet: CHR", 1, 1, False),
    0x480: ("DEF", 1, 10, False),
    0x481: ("Evasion", 1, 3, False),
    0x482: ("Mag. Evasion", 1, 3, False),
    0x483: ("Phys. dmg. taken", 1, -2, True),
    0x484: ("Magic dmg. taken", 1, -2, True),
    0x485: ("Spell interruption rate down", 1, -2, True),
    0x486: ("Occ. inc. resist. to stat. ailments", 1, 2, False),
    0x4DE: ("Pet: Phys. dmg. taken", 1, -2, True),
    0x4DF: ("Pet: Magic dmg. taken", 1, -2, True),
    0x4E0: ("Enh. Mag. eff. dur.", 1, 1, True),
    0x4E1: ("Helix effect duration", 1, 1, False),
    0x4F0: ("Meditate effect duration", 1, 1, False),
    0x5C0: ("Parrying rate", 1, 1, True),
    # --- Skirmish (Divainy-Gamainy) rows ------------------------------------------------
    0x003: ("HP", 65, 1, False),
    0x004: ("HP", 97, 1, False),
    0x00B: ("MP", 65, 1, False),
    0x00C: ("MP", 97, 1, False),
    0x011: ("HP", 1, 1, False),
    0x012: ("HP", 33, 1, False),
    0x021: ("DEF", 1, 1, False),
    0x02A: ("Enemy crit. hit rate", 1, -1, True),
    0x02B: ('"Charm"', 1, 1, False),
    0x034: ("MP recovered while healing", 1, 1, False),
    0x038: ("Breath dmg. taken", 1, -1, True),
    0x043: ("All Songs", 1, 1, False),
    0x062: ("Pet: Evasion", 1, 1, False),
    0x063: ("Pet: DEF", 1, 1, False),
    0x066: ("Pet: Crit.hit rate", 1, 1, True),
    0x068: ("Pet: Enmity", 1, 1, False),
    0x069: ("Pet: Enmity", 1, -1, False),
    0x06D: ('Pet: "Dbl. Atk."', 1, 1, True),
    0x075: ("Pet: Mag. Evasion", 1, 1, False),
    0x079: ("Pet: Breath", 1, 1, False),
    0x07A: ("Pet: TP Bonus", 1, 20, False),
    0x083: ("Mag. Acc.", 1, 1, False),
    0x086: ("Mag.Def.Bns.", 1, 1, False),
    0x099: ('"Shield Mastery"', 1, 1, False),
    0x0D4: ('"Recycle"', 1, 1, False),
    0x11E: ("Shield skill", 1, 1, False),
    0x142: ("Song spellcasting time", 1, -1, True),
    0x144: ('"Call Beast" ability delay', 1, -1, False),
    0x151: ("Song recast delay", 1, -1, False),
    0x153: ('"Elemental Siphon"', 1, 5, False),
    0x15E: ("Occ. maximizes magic accuracy", 1, 1, True),
    0x15F: ("Occ. quickens spellcasting", 1, 1, True),
    0x160: ("Occ. grants dmg. bonus based on TP", 1, 1, True),
    0x161: ("TP Bonus", 246, 1, False),
    0x162: ("Quadruple Attack", 1, 1, True),
    0x168: ("Save TP", 1, 10, False),
    0x170: ("Phalanx", 1, 1, False),
    0x226: ("STR", 1, 1, False),
    0x227: ("STR", 1, 1, False),
    0x228: ("STR", 1, 1, False),
    0x22A: ("INT", 1, 1, False),
    0x22B: ("MND", 1, 1, False),
    0x22D: ("STR", 1, 1, False),
    0x22E: ("STR", 1, 1, False),
    0x22F: ("STR", 1, 1, False),
    0x2E6: ("DMG:", 65, 1, False),
    0x2E7: ("DMG:", 97, 1, False),
    0x2EA: ("DMG:", 1, 1, False),
    0x2EB: ("DMG:", 33, 1, False),
    0x2EC: ("DMG:", 65, 1, False),
    0x2ED: ("DMG:", 97, 1, False),
    0x2F4: ("Delay:", 1, -1, False),
    0x2F5: ("Delay:", 33, -1, False),
    0x2F6: ("Delay:", 65, -1, False),
    0x2F7: ("Delay:", 97, -1, False),
    0x2FC: ("Delay:", 1, -1, False),
    0x2FD: ("Delay:", 33, -1, False),
    0x2FE: ("Delay:", 65, -1, False),
    0x2FF: ("Delay:", 97, -1, False),
    0x70E: ("Pet: STR", 1, 1, False),
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
    0x046: [("Mag.Atk.Bns.", 33, 1, False)],
0x06C: [("Mag.Atk.Bns.", 1, 1, False)],
    0x011: [("MP", 1, 1, False)],
    0x012: [("MP", 33, 1, False)],
    0x06D: [("Pet: Crit.hit rate", 1, 1, True)],
    0x083: [("Mag.Atk.Bns.", 1, 1, False)],
    0x226: [("DEX", 1, 1, False)],
    0x227: [("VIT", 1, 1, False)],
    0x228: [("AGI", 1, 1, False)],
    0x22A: [("MND", 1, 1, False)],
    0x22B: [("CHR", 1, 1, False)],
    0x22D: [("CHR", 1, 1, False)],
    0x22E: [("INT", 1, 1, False)],
    0x22F: [("MND", 1, 1, False)],
    0x70E: [("Pet: DEX", 1, 1, False), ("Pet: VIT", 1, 1, False)],
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


# --- BG Wiki cape augment picker -------------------------------------------------------------

def option_slot(option: dict, stage: int) -> tuple[int, int]:
    """The ``(augment id, value)`` word one BG Wiki option writes at *stage*."""
    try:
        stage = int(stage)
    except (TypeError, ValueError):
        raise ValueError("augment stage must be a number") from None
    if not 1 <= stage <= int(option["max_stage"]):
        raise ValueError("augment stage must be between 1 and %d"
                         % int(option["max_stage"]))
    amount = int(option["step"]) * stage
    high_id = int(option.get("high_id") or 0)
    if high_id and amount > 32:
        # HP+33..60 uses the second offset block (id 0x002 / 0x00A).
        augment_id = high_id
        value = amount - 33
    elif option.get("raw_mode") == "stage":
        # The client's 0x48x/0x4Dx ids already carry the multiplier, so the five
        # bits hold the stage (0 = first stage) rather than the stat amount.
        augment_id = int(option["id"])
        value = stage - 1
    else:
        augment_id = int(option["id"])
        value = amount - 1
    if not 0 <= value <= 0x1F:
        raise ValueError("%s at stage %d does not fit the five-bit value"
                         % (option["key"], stage))
    return augment_id, value


def option_text(option: dict, stage: int) -> str:
    """The tooltip text the client shows for one option at *stage*."""
    augment_id, value = option_slot(option, stage)
    return slot_text({"id": augment_id, "value": value})


@lru_cache(maxsize=None)
def _option_index(material_key: str) -> dict:
    material = MATERIAL_BY_KEY[str(material_key)]
    out: dict[tuple[int, int], dict] = {}
    for option in material["options"]:
        choice = {"option": str(option["key"])}
        for stage in range(1, int(option["max_stage"]) + 1):
            out[option_slot(option, stage)] = dict(choice, stage=int(stage))
            alt_id = int(option.get("alt_id") or 0)
            if alt_id:
                alt_value = stage - 1 if option.get("alt_raw_mode") == "stage" else (
                    int(option["step"]) * stage - 1)
                out[(alt_id, alt_value)] = dict(choice, stage=int(stage))
    return out


def selection_for_slot(material: dict, slot: dict | None) -> dict | None:
    """Which picker selection a decoded slot stands for, or None."""
    if not slot or not int(slot.get("id") or 0):
        return None
    hit = _option_index(str(material["key"])).get(
        (int(slot["id"]), int(slot["value"])))
    return dict(hit) if hit else None


def _current_slots(extra) -> list[tuple[int, int]]:
    decoded = decode(extra)
    if decoded is None:
        return [(0, 0)] * SLOTS
    return [(int(slot["id"]), int(slot["value"])) for slot in decoded]


def merge_choices(choices, current=None) -> list[tuple[int, int]]:
    """Apply a launcher choice object over an existing five-slot block.

    ``choices`` maps a material key (thread, dust, dye, sap, resin) to
    ``{"option": <option key>, "stage": <1..max>}``.  A material that is absent
    keeps the word already on the item: that is what lets a pet build's
    off-category slot survive an edit of the other four.  An explicit ``null``
    (or an empty option key) clears that material instead.
    """
    if choices is None:
        choices = {}
    if not isinstance(choices, dict):
        raise ValueError("augment choices must be an object")
    slots = list(current or ())
    slots = [(int(augment_id), int(value)) for augment_id, value in slots]
    slots.extend([(0, 0)] * (SLOTS - len(slots)))
    seen: set[str] = set()
    for raw_key, choice in choices.items():
        key = str(raw_key or "").strip().lower()
        if key not in MATERIAL_BY_KEY:
            raise ValueError("unknown augment material: %s" % (raw_key,))
        if key in seen:
            raise ValueError("augment material listed twice: %s" % key)
        seen.add(key)
        material = MATERIAL_BY_KEY[key]
        slot = int(material["slot"])
        if choice is None:
            slots[slot] = (0, 0)
            continue
        if not isinstance(choice, dict):
            raise ValueError("%s choice must be an object" % key)
        option_key = str(choice.get("option") or "").strip().lower()
        if not option_key:
            slots[slot] = (0, 0)
            continue
        option = next((candidate for candidate in material["options"]
                       if str(candidate["key"]).lower() == option_key), None)
        if option is None:
            raise ValueError("%s does not offer %r" % (material["label"], option_key))
        stage = choice.get("stage")
        if stage in (None, ""):
            stage = option["max_stage"]
        slots[slot] = option_slot(option, stage)
    return slots


def choices_slots(choices) -> list[tuple[int, int]]:
    """The five block words for a from-scratch selection (no current block)."""
    return merge_choices(choices, None)


def encode_choices(choices) -> bytes:
    """A standard augment block for the launcher's per-material selection."""
    slots = choices_slots(choices)
    if not any(int(augment_id) for augment_id, _value in slots):
        raise ValueError("choose at least one augment")
    return _encode_slots(slots)


def _inventory_copy(service, character_id: int, container, slot):
    try:
        container = int(container)
        slot = int(slot)
    except (TypeError, ValueError):
        raise ValueError("container and slot must be numbers") from None
    row = next((item for item in service.inventory(int(character_id))
                if int(item["container"]) == container
                and int(item["slot"]) == slot), None)
    if row is None:
        raise LookupError("no item in that container slot")
    job = job_for_item(int(row["item_id"]))
    if job is None:
        raise ValueError("that item is not an Ambuscade job cape")
    return row, job


def add(service, character_id: int, item_id) -> dict:
    """Put one unaugmented copy of a job cape in the character's inventory."""
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        raise ValueError("item id must be a number") from None
    job = job_for_item(item_id)
    if job is None:
        raise ValueError("that item is not an Ambuscade job cape")
    added = service.add_item(int(character_id), item_id, 1)
    added["job"] = job
    return added


def apply(service, character_id: int, container, slot, choices) -> dict:
    """Write the selected augment block onto one inventory copy.

    Materials the launcher did not list keep the word already on the copy, so a
    custom or pet-focused block is not silently truncated by a partial edit.
    Clearing every slot writes an empty block, the same state ``//cape off``
    leaves behind.
    """
    row, job = _inventory_copy(service, character_id, container, slot)
    words = merge_choices(choices, _current_slots(row.get("extra") or b""))
    block = _encode_slots(words) if any(int(a) for a, _value in words) else b""
    if not service.set_item_extra(int(character_id), int(row["container"]),
                                  int(row["slot"]), block):
        raise LookupError("the item row disappeared")
    return {
        "container": int(row["container"]),
        "slot": int(row["slot"]),
        "item_id": int(row["item_id"]),
        "name": str(row.get("name") or JOBS[job]["cape_name"]),
        "job": job,
        "block": block.hex().upper(),
        "text": describe(block),
    }


def clear(service, character_id: int, container, slot) -> dict:
    """Remove a cape's augment block (the same state ``//cape off`` writes)."""
    row, job = _inventory_copy(service, character_id, container, slot)
    if not service.set_item_extra(int(character_id), int(row["container"]),
                                  int(row["slot"]), b""):
        raise LookupError("the item row disappeared")
    return {
        "container": int(row["container"]),
        "slot": int(row["slot"]),
        "item_id": int(row["item_id"]),
        "name": str(row.get("name") or JOBS[job]["cape_name"]),
        "job": job,
        "block": "",
        "text": "not augmented",
    }


def _build_name(job: str, extra) -> str | None:
    raw = bytes(extra or b"")
    if not raw:
        return None
    for build in JOBS[job]["builds"]:
        if encode(build, job) == raw:
            return build
    return None


def catalog(service, character_id: int) -> dict:
    """The Data page's cape card: every job cape, its copies and BG Wiki choices."""
    copies_by_id: dict[int, list[dict]] = {}
    for item in service.inventory(int(character_id)):
        item_id = int(item["item_id"])
        job = job_for_item(item_id)
        if job is None:
            continue
        extra = bytes(item.get("extra") or b"")
        decoded = decode(extra) or [{"id": 0, "value": 0} for _ in range(SLOTS)]
        selection: dict[str, dict | None] = {}
        for material in MATERIALS:
            index = int(material["slot"])
            selection[material["key"]] = selection_for_slot(
                material, decoded[index] if index < len(decoded) else None)
        copies_by_id.setdefault(item_id, []).append({
            "container": int(item["container"]),
            "slot": int(item["slot"]),
            "container_name": container_label(item["container"]),
            "current": {
                "text": describe(extra),
                "build": _build_name(job, extra),
                "slots": [
                    {
                        "id": int(slot["id"]),
                        "value": int(slot["value"]),
                        "text": slot_text(slot),
                    }
                    for slot in decoded
                ],
            },
            "selection": selection,
        })

    ids = [int(entry["cape_id"]) for entry in JOBS.values()]
    locker: dict[int, int] = {}
    if ids:
        placeholders = ",".join("?" for _ in ids)
        for row in service.db.all(
                "SELECT item_id, COUNT(*) AS n FROM char_locker "
                "WHERE character_id = ? AND item_id IN (%s) GROUP BY item_id"
                % placeholders, (int(character_id), *ids)):
            locker[int(row["item_id"])] = int(row["n"])

    materials = []
    for material in MATERIALS:
        options = []
        for option in material["options"]:
            options.append(dict(
                option,
                max_text=option_text(option, int(option["max_stage"])),
            ))
        materials.append(dict(material, options=options))

    capes = []
    for job_number, (job, entry) in enumerate(JOBS.items(), start=1):
        item_id = int(entry["cape_id"])
        copies = sorted(copies_by_id.get(item_id, []),
                        key=lambda copy: (copy["container"], copy["slot"]))
        capes.append({
            "job": job,
            "job_number": job_number,
            "item_id": item_id,
            "name": entry["cape_name"],
            "owned": len(copies),
            "locker": int(locker.get(item_id, 0)),
            "copies": copies,
        })

    return {
        "source": "https://www.bg-wiki.com/ffxi/Category:JSE_Capes",
        "note": (
            "Trade a cape to Gorpa-Masorpa with an Abdhaljs Thread, Dust, Dye, Sap "
            "or Resin and pick the attribute that material offers. Each cape keeps "
            "one augment per material - five slots in the client block - and each "
            "further trade adds one stage up to the BG Wiki maximum. Changing a "
            "material's option replaces that slot and keeps the other four."),
        "slots": SLOTS,
        "materials": materials,
        "capes": capes,
    }
