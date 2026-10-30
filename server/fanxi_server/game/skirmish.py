"""Divainy-Gamainy's Skirmish augments (Arcane Glyptics).

Divainy-Gamainy, at Western Adoulin (J-10), augments every Skirmish item with
Arcane Glyptics.  Three families share the same **standard five-slot augment
block** the Ambuscade capes and Oseem use::

    02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12

Each slot is a little-endian u16 holding ``id:11 | value:5``; the client prints
``(value + offset) * multiplier`` for the id.

* **Alluvion Skirmish weapons and armor** (Yorcia Weald) take one Snow, one
  Leaf and one Dusk stone, each stone offering its own stat table.  A weapon
  adds the Dusk stone's DMG row; a two-hander's Dusk tip is Delay- (Snapshot
  on Archery/Marksmanship).
* **Skirmish weapons** (Cirdas Caverns / Rala Waterways) always roll DMG, then
  up to one stat from each of two pools.
* **Skirmish armor** (Yorcia Weald / Outer Ra'Kaznar) always rolls Physical
  Damage Taken, then one (NQ) or two (+1) stats from one pool.

Retail rolls the rows at random and the player keeps or rerolls the piece.  The
launcher's Data page goes the other way: pick the stat for every row and write
its maximum, which is what ``data/skirmish.json`` records from BG Wiki.

``data/skirmish.json`` holds every item and its table.  The augment ids below
are the client's packet ids (the same table the capes and Oseem use); the
comment on each row names the client text.  ``0x083``/``0x046`` are the
offset-1 and offset-33 combined Magic Accuracy / Magic Atk. Bns. rows.
"""

from __future__ import annotations

import json
from pathlib import Path

from .capes import container_label

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "skirmish.json"

KIND = 0x02
SUBKIND = 0x03
SLOTS = 5
MAX_STORED = 0x1F

# key -> (labels, sign, rows).  ``labels`` is one or two client tooltip names;
# a two-label row is the client's combined id (Accuracy+20 Attack+20).
# ``sign`` -1 marks a reduction the client prints with a minus, 0 is Enmity
# (positive id 0x027 or negative 0x028).  ``rows`` is (offset, id, multiplier)
# from the client's table, smallest value block first.
STATS: dict[str, dict] = {
    "hp": {"labels": (("HP", False),), "sign": 1,
           "rows": ((1, 0x001, 1), (33, 0x002, 1), (65, 0x003, 1), (97, 0x004, 1))},
    "mp": {"labels": (("MP", False),), "sign": 1,
           "rows": ((1, 0x009, 1), (33, 0x00A, 1), (65, 0x00B, 1), (97, 0x00C, 1))},
    "hp_mp": {"labels": (("HP", False), ("MP", False)), "sign": 1,
              "rows": ((1, 0x011, 1), (33, 0x012, 1))},
    "str": {"labels": (("STR", False),), "sign": 1, "rows": ((1, 0x200, 1),)},
    "dex": {"labels": (("DEX", False),), "sign": 1, "rows": ((1, 0x201, 1),)},
    "vit": {"labels": (("VIT", False),), "sign": 1, "rows": ((1, 0x202, 1),)},
    "agi": {"labels": (("AGI", False),), "sign": 1, "rows": ((1, 0x203, 1),)},
    "int": {"labels": (("INT", False),), "sign": 1, "rows": ((1, 0x204, 1),)},
    "mnd": {"labels": (("MND", False),), "sign": 1, "rows": ((1, 0x205, 1),)},
    "chr": {"labels": (("CHR", False),), "sign": 1, "rows": ((1, 0x206, 1),)},
    "str_dex": {"labels": (("STR", False), ("DEX", False)), "sign": 1,
                "rows": ((1, 0x226, 1),)},
    "str_vit": {"labels": (("STR", False), ("VIT", False)), "sign": 1,
                "rows": ((1, 0x227, 1),)},
    "str_agi": {"labels": (("STR", False), ("AGI", False)), "sign": 1,
                "rows": ((1, 0x228, 1),)},
    "str_chr": {"labels": (("STR", False), ("CHR", False)), "sign": 1,
                "rows": ((1, 0x22D, 1),)},
    "str_int": {"labels": (("STR", False), ("INT", False)), "sign": 1,
                "rows": ((1, 0x22E, 1),)},
    "str_mnd": {"labels": (("STR", False), ("MND", False)), "sign": 1,
                "rows": ((1, 0x22F, 1),)},
    "int_mnd": {"labels": (("INT", False), ("MND", False)), "sign": 1,
                "rows": ((1, 0x22A, 1),)},
    "mnd_chr": {"labels": (("MND", False), ("CHR", False)), "sign": 1,
                "rows": ((1, 0x22B, 1),)},
    "acc": {"labels": (("Accuracy", False),), "sign": 1,
            "rows": ((1, 0x017, 1), (33, 0x03E, 1))},
    "attack": {"labels": (("Attack", False),), "sign": 1,
               "rows": ((1, 0x019, 1), (33, 0x041, 1))},
    "racc": {"labels": (("Rng.Acc.", False),), "sign": 1,
             "rows": ((1, 0x01B, 1), (33, 0x03F, 1))},
    "ratt": {"labels": (("Rng.Atk.", False),), "sign": 1,
             "rows": ((1, 0x01D, 1), (33, 0x042, 1))},
    "macc": {"labels": (("Mag. Acc.", False),), "sign": 1,
             "rows": ((1, 0x023, 1), (33, 0x040, 1))},
    "mab": {"labels": (("Mag.Atk.Bns.", False),), "sign": 1,
            "rows": ((1, 0x085, 1),)},
    "mdef": {"labels": (("Mag.Def.Bns.", False),), "sign": 1,
             "rows": ((1, 0x086, 1),)},
    "meva": {"labels": (("Mag. Evasion", False),), "sign": 1,
             "rows": ((1, 0x025, 1),)},
    "evasion": {"labels": (("Evasion", False),), "sign": 1,
                "rows": ((1, 0x01F, 1),)},
    "def": {"labels": (("DEF", False),), "sign": 1, "rows": ((1, 0x021, 1),)},
    "acc_attack": {"labels": (("Accuracy", False), ("Attack", False)), "sign": 1,
                   "rows": ((1, 0x044, 1),)},
    "racc_ratt": {"labels": (("Rng.Acc.", False), ("Rng.Atk.", False)), "sign": 1,
                  "rows": ((1, 0x045, 1),)},
    "macc_mab": {"labels": (("Mag. Acc.", False), ("Mag.Atk.Bns.", False)), "sign": 1,
                 "rows": ((1, 0x083, 1), (33, 0x046, 1))},
    "enmity": {"labels": (("Enmity", False),), "sign": 0,
               "rows": ((1, 0x027, 1), (1, 0x028, 1))},
    "crit_rate": {"labels": (("Crit.hit rate", True),), "sign": 1,
                  "rows": ((1, 0x029, 1),)},
    "crit_damage": {"labels": (("Crit. hit damage", True),), "sign": 1,
                    "rows": ((1, 0x148, 1),)},
    "da": {"labels": (("Dbl.Atk.", True),), "sign": 1, "rows": ((1, 0x08F, 1),)},
    "ta": {"labels": (("Triple Atk.", True),), "sign": 1, "rows": ((1, 0x090, 1),)},
    "qa": {"labels": (("Quadruple Attack", True),), "sign": 1,
           "rows": ((1, 0x162, 1),)},
    "haste": {"labels": (("Haste", True),), "sign": 1, "rows": ((1, 0x031, 1),)},
    "stp": {"labels": (("Store TP", False),), "sign": 1,
            "rows": ((1, 0x08E, 1),)},
    "waltz": {"labels": (("Waltz potency", True),), "sign": 1,
              "rows": ((1, 0x14A, 1),)},
    "wsd": {"labels": (("Weapon skill damage", True),), "sign": 1,
            "rows": ((1, 0x147, 1),)},
    "wsa": {"labels": (("Weapon Skill Acc.", False),), "sign": 1,
            "rows": ((1, 0x146, 1),)},
    "subtle_blow": {"labels": (("Subtle Blow", False),), "sign": 1,
                    "rows": ((1, 0x0C3, 1),)},
    "snapshot": {"labels": (("Snapshot", False),), "sign": 1,
                 "rows": ((1, 0x0D3, 1),)},
    "rapid_shot": {"labels": (("Rapid Shot", False),), "sign": 1,
                   "rows": ((1, 0x08B, 1),)},
    "fast_cast": {"labels": (("Fast Cast", True),), "sign": 1,
                  "rows": ((1, 0x08C, 1),)},
    "refresh": {"labels": (("Refresh", False),), "sign": 1,
                "rows": ((1, 0x08A, 1),)},
    "regen": {"labels": (("Regen", False),), "sign": 1, "rows": ((1, 0x089, 1),)},
    "regen_potency": {"labels": (("Regen potency", False),), "sign": 1,
                      "rows": ((1, 0x173, 1),)},
    "cure_potency": {"labels": (("Cure Potency", True),), "sign": 1,
                     "rows": ((1, 0x149, 1),)},
    "cure_received": {"labels": (("Cure Potency Received", True),), "sign": 1,
                      "rows": ((1, 0x164, 1),)},
    "cure_cast_time": {"labels": (("Cure Spellcasting Time", True),), "sign": -1,
                       "rows": ((1, 0x143, 1),)},
    "song_cast_time": {"labels": (("Song Spellcasting Time", True),), "sign": -1,
                       "rows": ((1, 0x142, 1),)},
    "song_recast": {"labels": (("Song Recast Delay", False),), "sign": -1,
                    "rows": ((1, 0x151, 1),)},
    "conserve_mp": {"labels": (("Conserve MP", False),), "sign": 1,
                    "rows": ((1, 0x08D, 1),)},
    "magic_burst": {"labels": (("Magic burst dmg.", True),), "sign": 1,
                    "rows": ((1, 0x14E, 1),)},
    "magic_damage": {"labels": (("Magic Damage", False),), "sign": 1,
                     "rows": ((1, 0x16A, 1),)},
    "magic_crit_rate": {"labels": (("Magic crit. hit rate", True),), "sign": 1,
                        "rows": ((1, 0x039, 1),)},
    "magic_crit_damage": {"labels": (("Mag. crit. hit dmg.", True),), "sign": 1,
                          "rows": ((1, 0x14F, 1),)},
    "skillchain": {"labels": (("Sklchn.dmg.", True),), "sign": 1,
                   "rows": ((1, 0x14C, 1),)},
    "drain_aspir": {"labels": (('"Drain" and "Aspir" potency', False),), "sign": 1,
                    "rows": ((1, 0x157, 1),)},
    "occult": {"labels": (("Occult Acumen", False),), "sign": 1,
               "rows": ((1, 0x0ED, 1),)},
    "repair": {"labels": (("Repair potency", True),), "sign": 1,
               "rows": ((1, 0x155, 1),)},
    "quick_magic": {"labels": (("Occ. quickens spellcasting", True),), "sign": 1,
                    "rows": ((1, 0x15F, 1),)},
    "phalanx": {"labels": (("Phalanx", False),), "sign": 1,
                "rows": ((1, 0x170, 1),)},
    "shield_mastery": {"labels": (('"Shield Mastery"', False),), "sign": 1,
                       "rows": ((1, 0x099, 1),)},
    "shield_skill": {"labels": (("Shield skill", False),), "sign": 1,
                     "rows": ((1, 0x11E, 1),)},
    "block": {"labels": (("Chance of successful block", False),), "sign": 1,
              "rows": ((1, 0x16B, 1),)},
    "enemy_crit": {"labels": (("Enemy crit. hit rate", True),), "sign": -1,
                   "rows": ((1, 0x02A, 1),)},
    "recycle": {"labels": (('"Recycle"', False),), "sign": 1,
                "rows": ((1, 0x0D4, 1),)},
    "all_songs": {"labels": (("All Songs", False),), "sign": 1,
                  "rows": ((1, 0x043, 1),)},
    "charm": {"labels": (('"Charm"', False),), "sign": 1,
              "rows": ((1, 0x02B, 1),)},
    "singing_skill": {"labels": (("Singing skill", False),), "sign": 1,
                      "rows": ((1, 0x128, 1),)},
    "elemental_skill": {"labels": (("Elem. magic skill", False),), "sign": 1,
                        "rows": ((1, 0x124, 1),)},
    "summoning_skill": {"labels": (("Summoning magic skill", False),), "sign": 1,
                        "rows": ((1, 0x126, 1),)},
    # The five magic-skill rows Sinister Reign's drops carry (the same ids the
    # Oseem glyptic table uses).  They are unmapped on the stat sheet, like the
    # other skill rows, but the block still has to encode them for the tooltip.
    "divine_skill": {"labels": (("Divine magic skill", False),), "sign": 1,
                     "rows": ((1, 0x120, 1),)},
    "healing_skill": {"labels": (("Healing magic skill", False),), "sign": 1,
                      "rows": ((1, 0x121, 1),)},
    "enhancing_skill": {"labels": (("Enhancing magic skill", False),), "sign": 1,
                        "rows": ((1, 0x122, 1),)},
    "dark_skill": {"labels": (("Dark magic skill", False),), "sign": 1,
                   "rows": ((1, 0x125, 1),)},
    "ninjutsu_skill": {"labels": (("Ninjutsu skill", False),), "sign": 1,
                       "rows": ((1, 0x127, 1),)},
    "enhancing_duration": {"labels": (("Enhancing Magic duration", False),),
                           "sign": 1, "rows": ((0, 0x176, 1),)},
    "blood_boon": {"labels": (('"Blood Boon"', False),), "sign": 1,
                   "rows": ((1, 0x0E9, 1),)},
    "counter": {"labels": (('"Counter"', True),), "sign": 1,
                "rows": ((1, 0x091, 1),)},
    "dw": {"labels": (('"Dual Wield"', False),), "sign": 1,
           "rows": ((1, 0x092, 1),)},
    "th": {"labels": (("Treasure Hunter", False),), "sign": 1,
           "rows": ((1, 0x093, 1),)},
    "avatar_perp": {"labels": (('"Avatar perpetuation cost"', False),), "sign": -1,
                    "rows": ((1, 0x141, 1),)},
    "bp_delay": {"labels": (('"Blood Pact" ability delay', False),), "sign": -1,
                 "rows": ((1, 0x140, 1),)},
    "bp_damage": {"labels": (("Blood Pact Dmg.", False),), "sign": 1,
                  "rows": ((1, 0x171, 1),)},
    "elemental_siphon": {"labels": (('"Elemental Siphon"', False),), "sign": 1,
                         "rows": ((1, 0x153, 5),)},
    "save_tp": {"labels": (("Save TP", False),), "sign": 1,
                "rows": ((1, 0x168, 10),)},
    "pet_tp_bonus": {"labels": (("Pet: TP Bonus", False),), "sign": 1,
                     "rows": ((1, 0x07A, 20),)},
    "pet_acc_racc": {"labels": (("Pet: Accuracy", False), ("Pet: Rng. Acc.", False)),
                     "sign": 1, "rows": ((1, 0x06A, 1),)},
    "pet_racc": {"labels": (("Pet: Rng. Acc.", False),), "sign": 1,
                 "rows": ((1, 0x071, 1),)},
    "pet_attack_ratt": {"labels": (("Pet: Attack", False), ("Pet: Rng.Atk.", False)),
                        "sign": 1, "rows": ((1, 0x06B, 1),)},
    "pet_macc": {"labels": (("Pet: Mag. Acc.", False),), "sign": 1,
                 "rows": ((1, 0x064, 1),)},
    "pet_mab": {"labels": (('Pet: "Mag.Atk.Bns."', False),), "sign": 1,
                "rows": ((1, 0x065, 1),)},
    "pet_def": {"labels": (("Pet: DEF", False),), "sign": 1,
                "rows": ((1, 0x063, 1),)},
    "pet_evasion": {"labels": (("Pet: Evasion", False),), "sign": 1,
                    "rows": ((1, 0x062, 1),)},
    "pet_meva": {"labels": (("Pet: Mag. Evasion", False),), "sign": 1,
                 "rows": ((1, 0x075, 1),)},
    "pet_pdt": {"labels": (("Pet: Phys. dmg. taken", True),), "sign": -1,
                "rows": ((1, 0x076, 1),)},
    "pet_dt": {"labels": (("Pet: Damage taken", True),), "sign": -1,
               "rows": ((1, 0x070, 1),)},
    "pet_regen": {"labels": (('Pet: "Regen"', False),), "sign": 1,
                  "rows": ((1, 0x06E, 1),)},
    "pet_haste": {"labels": (("Pet: Haste", True),), "sign": 1,
                  "rows": ((1, 0x06F, 1),)},
    "pet_crit": {"labels": (("Pet: Crit.hit rate", True),), "sign": 1,
                 "rows": ((1, 0x066, 1),)},
    "pet_da": {"labels": (('Pet: "Dbl. Atk."', True),), "sign": 1,
               "rows": ((1, 0x07B, 1),)},
    "pet_da_crit": {"labels": (('Pet: "Dbl. Atk."', True), ("Pet: Crit.hit rate", True)),
                    "sign": 1, "rows": ((1, 0x06D, 1),)},
    "pet_stp": {"labels": (('Pet: "Store TP"', False),), "sign": 1,
                "rows": ((1, 0x073, 1),)},
    "pet_subtle": {"labels": (('Pet: "Subtle Blow"', False),), "sign": 1,
                   "rows": ((1, 0x074, 1),)},
    "pet_enmity": {"labels": (("Pet: Enmity", False),), "sign": 0,
                   "rows": ((1, 0x068, 1), (1, 0x069, 1))},
    "pet_str_dex_vit": {"labels": (("Pet: STR", False), ("Pet: DEX", False),
                                    ("Pet: VIT", False)), "sign": 1,
                        "rows": ((1, 0x70E, 1),)},
    "pet_breath": {"labels": (("Pet: Breath", False),), "sign": 1,
                   "rows": ((1, 0x079, 1),)},
    "dmg": {"labels": (("DMG", False),), "sign": 1,
            "rows": ((1, 0x02D, 1), (33, 0x04C, 1), (65, 0x2E6, 1), (97, 0x2E7, 1)),
            "ranged_rows": ((1, 0x2EA, 1), (33, 0x2EB, 1), (65, 0x2EC, 1),
                            (97, 0x2ED, 1))},
    "pdt": {"labels": (("Phys. dmg. taken", True),), "sign": -1,
            "rows": ((1, 0x036, 1),)},
    "mdt": {"labels": (("Magic dmg. taken", True),), "sign": -1,
            "rows": ((1, 0x037, 1),)},
    "bdt": {"labels": (("Breath dmg. taken", True),), "sign": -1,
            "rows": ((1, 0x038, 1),)},
    "dt": {"labels": (("Damage taken", True),), "sign": -1,
           "rows": ((1, 0x047, 1),)},
    "mp_heal": {"labels": (("MP recovered while healing", False),), "sign": 1,
                "rows": ((1, 0x034, 1),)},
    "spell_interrupt": {"labels": (("Spell interruption rate down", True),),
                        "sign": -1, "rows": ((1, 0x035, 1),)},
    "call_beast": {"labels": (('"Call Beast" ability delay', False),), "sign": -1,
                   "rows": ((1, 0x144, 1),)},
    "delay": {"labels": (("Delay", False),), "sign": -1,
              "rows": ((1, 0x2F4, 1), (33, 0x2F5, 1), (65, 0x2F6, 1),
                       (97, 0x2F7, 1)),
              "ranged_rows": ((1, 0x2FC, 1), (33, 0x2FD, 1), (65, 0x2FE, 1),
                              (97, 0x2FF, 1))},
}

# id -> (key, offset, multiplier, sign) for reading a block back.  A combined
# id maps to its one combined key; the first row wins.
BY_ID: dict[int, tuple[str, int, int, int]] = {}
for _key, _spec in STATS.items():
    for _index, (_offset, _id, _mult) in enumerate(_spec["rows"]):
        _row_sign = _spec["sign"]
        if _row_sign == 0:
            _row_sign = 1 if _index == 0 else -1
        BY_ID.setdefault(int(_id), (_key, int(_offset), int(_mult), int(_row_sign)))
    for _offset, _id, _mult in _spec.get("ranged_rows", ()):
        BY_ID.setdefault(int(_id), (_key, int(_offset), int(_mult), int(_spec["sign"])))

_cache: dict | None = None


# --- data file -------------------------------------------------------------------------------
def data() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(PATH.read_text())
        except (OSError, ValueError):
            _cache = {"items": [], "tables": {}}
    return _cache


def entries() -> list[dict]:
    return list(data().get("items", ()))


def entry(item_id: int) -> dict | None:
    for item in entries():
        if int(item["item_id"]) == int(item_id):
            return item
    return None


def tables() -> dict[str, dict]:
    return dict(data().get("tables", {}))


# --- stat helpers ----------------------------------------------------------------------------
def _rows(key: str, ranged: bool = False) -> tuple:
    spec = STATS[key]
    if ranged and spec.get("ranged_rows"):
        return spec["ranged_rows"]
    return spec["rows"]


def label_of(key: str) -> str:
    return " / ".join(text for text, _percent in STATS[key]["labels"])


def stat_text(key: str, value: int) -> str:
    """The tooltip text one ``(key, value)`` pick stands for."""
    spec = STATS[key]
    value = int(value)
    labels = spec["labels"]
    if key == "dmg":
        return "DMG:+%d" % value
    amount = -abs(value) if spec["sign"] < 0 else value
    sign = "+" if amount >= 0 else ""
    return " ".join("%s%s%d%s" % (label, sign, amount, "%" if percent else "")
                    for label, percent in labels)


def value_bounds(key: str, ranged: bool = False) -> tuple[int, int]:
    """The numeric ``(minimum, maximum)`` the stat's ids can print."""
    spec = STATS[key]
    rows = _rows(key, ranged)
    lowest = max(1, min(int(offset) * int(mult) for offset, _id, mult in rows))
    highest = max(int(offset + MAX_STORED) * int(mult) for offset, _id, mult in rows)
    if spec["sign"] < 0:
        return -highest, -lowest
    if spec["sign"] == 0:
        return -highest, highest
    return lowest, highest


def min_value(key: str, ranged: bool = False) -> int:
    return value_bounds(key, ranged)[0]


def max_value(key: str, ranged: bool = False) -> int:
    return value_bounds(key, ranged)[1]


def step_value(key: str) -> int:
    return max(int(mult) for _offset, _id, mult in STATS[key]["rows"])


def slot_word(key: str, value: int, ranged: bool = False) -> tuple[int, int]:
    """``(id, five-bit value)`` for one stat at one number."""
    if key not in STATS:
        raise ValueError("unknown augment %r" % (key,))
    spec = STATS[key]
    value = int(value)
    if value == 0:
        raise ValueError("%s needs a non-zero value" % label_of(key))
    if spec["sign"] == 0:
        index = 0 if value > 0 else 1
        offset, augment_id, mult = spec["rows"][index]
        amount = abs(value)
        if amount % mult:
            raise ValueError("%s must be a multiple of %d" % (label_of(key), mult))
        stored = amount // mult - offset
        if not 0 <= stored <= MAX_STORED:
            raise ValueError("%s cannot hold %r" % (label_of(key), value))
        return int(augment_id), int(stored)
    amount = abs(value) if spec["sign"] < 0 else value
    for offset, augment_id, mult in _rows(key, ranged):
        if amount % mult:
            continue
        stored = amount // mult - offset
        if 0 <= stored <= MAX_STORED:
            return int(augment_id), int(stored)
    low, high = value_bounds(key, ranged)
    raise ValueError("%s cannot hold %r (%d..%d)" % (label_of(key), value, low, high))


def snap_bounds(key: str, low: int, high: int, ranged: bool = False) -> tuple[int, int]:
    """Clamp a wiki range to values this client id can actually print.

    Returns the numeric ``(minimum, maximum)`` pair, so a reduction comes back
    as ``(-4, -1)`` and Enmity can keep a negative and a positive end.
    """
    mult = step_value(key)
    low, high = sorted((int(low), int(high)))
    floor = ((low + mult - 1) // mult) * mult
    ceiling = (high // mult) * mult
    lowest, highest = value_bounds(key, ranged)
    floor = max(floor, lowest)
    ceiling = min(ceiling, highest)
    if floor > ceiling:
        middle = max(lowest, min(highest, high))
        floor = ceiling = middle
    return floor, ceiling


def encode(picks, ranged: bool = False) -> bytes:
    """A 24-byte standard block from up to five ``(key, value)`` picks."""
    from . import capes

    words = []
    for pick in list(picks or ())[:SLOTS]:
        if not pick:
            words.append((0, 0))
            continue
        words.append(slot_word(str(pick["key"]), int(pick["value"]), ranged))
    words.extend([(0, 0)] * (SLOTS - len(words)))
    return capes._encode_slots(words)


def decode_picks(extra: bytes | None) -> list[dict | None]:
    """The five picks a standard block carries, in slot order."""
    from . import capes

    slots = capes.decode(extra)
    if slots is None:
        return []
    picks: list[dict | None] = []
    for slot in slots:
        augment_id = int(slot["id"])
        if not augment_id:
            picks.append(None)
            continue
        found = BY_ID.get(augment_id)
        if found is None:
            picks.append(None)
            continue
        key, offset, mult, sign = found
        amount = (int(slot["value"]) + offset) * mult
        if sign < 0:
            amount = -amount
        picks.append({"key": key, "value": amount})
    return picks


def describe(extra: bytes | None) -> str:
    """The block as the launcher shows it, or ``not augmented``."""
    from . import capes

    slots = capes.decode(extra)
    if slots is None:
        return "not augmented"
    texts = []
    for slot in slots:
        augment_id = int(slot["id"])
        if not augment_id:
            continue
        found = BY_ID.get(augment_id)
        if found is not None:
            key, offset, mult, sign = found
            amount = (int(slot["value"]) + offset) * mult
            if sign < 0:
                amount = -amount
            texts.append(stat_text(key, amount))
        else:
            text = capes.slot_text(slot)
            if text:
                texts.append(text)
    return " | ".join(texts) if texts else "not augmented"


# --- item slots ------------------------------------------------------------------------------
def resolved_slots(item: dict) -> list[dict]:
    """The pickable slots for one item, with its own DMG maximum."""
    table = tables().get(str(item.get("table") or ""))
    if table is None:
        return []
    out = []
    for slot_index, slot in enumerate(table.get("slots") or ()):
        options = []
        for raw in slot.get("options") or ():
            key = str(raw["key"])
            low = int(raw["min"])
            high = int(raw["max"])
            percent = bool(raw.get("percent"))
            if raw.get("from_item"):
                high = int(item.get("dmg_max") or 0)
                low = 1
                if high <= 0:
                    continue
            ranged = bool(item.get("ranged"))
            if raw.get("alt") and ranged:
                key = str(raw["alt"])
                low = int(raw.get("alt_max", low))
                high = int(raw.get("alt_min", high))
                percent = False
            low, high = snap_bounds(key, low, high, ranged)
            spec = STATS[key]
            # A reduction defaults to its strongest value; a positive row to its
            # cap; an Enmity row offers both signs, so start at the negative end
            # (the roll most jobs keep) and let the card move it up.
            default = low if (spec["sign"] < 0 or low < 0) else high
            options.append({
                "key": key,
                "label": label_of(key),
                "text": stat_text(key, default),
                "minimum": low,
                "maximum": high,
                "step": step_value(key),
                "percent": percent,
                "default": default,
            })
        out.append({
            "key": str(slot.get("key") or "slot%d" % slot_index),
            "label": str(slot.get("label") or "Row %d" % (slot_index + 1)),
            "required": bool(slot.get("required")),
            "default_on": bool(slot.get("default_on")),
            "options": options,
        })
    return out


def _checked_picks(item: dict, picks) -> list[dict | None]:
    slots = resolved_slots(item)
    if not slots:
        raise ValueError("that item has no Skirmish augment table")
    picks = list(picks or ())
    if len(picks) > len(slots):
        raise ValueError("this item has only %d augment rows" % len(slots))
    out: list[dict | None] = []
    ranged = bool(item.get("ranged"))
    for index, slot in enumerate(slots):
        raw = picks[index] if index < len(picks) else None
        if not raw:
            if slot["required"]:
                raise ValueError("%s always keeps its %s row"
                                 % (item["name"], slot["label"]))
            out.append(None)
            continue
        if not isinstance(raw, dict):
            raise ValueError("each augment pick must be an object")
        key = str(raw.get("key") or "").strip()
        allowed = {option["key"]: option for option in slot["options"]}
        if key not in allowed:
            raise ValueError("%s is not offered by this %s" % (key, slot["label"]))
        value = int(raw.get("value") or 0)
        option = allowed[key]
        if not option["minimum"] <= value <= option["maximum"]:
            raise ValueError("%s out of range: %r" % (key, value))
        slot_word(key, value, ranged)
        out.append({"key": key, "value": value})
    if not any(out):
        raise ValueError("pick at least one augment row")
    out.extend([None] * (SLOTS - len(out)))
    return out


# --- inventory -------------------------------------------------------------------------------
def _inventory_copy(service, character_id: int, container, slot):
    return next((row for row in service.inventory(int(character_id))
                 if int(row["container"]) == int(container)
                 and int(row["slot"]) == int(slot)), None)


def catalog(service, character_id: int) -> dict:
    """The Data page's Skirmish card: every item and the own copies."""
    known = {int(item["item_id"]) for item in entries()}
    owned: dict[int, list[dict]] = {}
    for row in service.inventory(int(character_id)):
        item_id = int(row["item_id"])
        if item_id not in known:
            continue
        picks = decode_picks(row.get("extra"))
        owned.setdefault(item_id, []).append({
            "container": int(row["container"]),
            "container_name": container_label(int(row["container"])),
            "slot": int(row["slot"]),
            "quantity": int(row.get("quantity") or 1),
            "current": describe(row.get("extra")),
            "slots": [pick and stat_text(pick["key"], pick["value"]) or ""
                      for pick in (picks or [])],
            "selection": picks,
        })
    rows = []
    slot_sets: dict[str, list[dict]] = {}
    for item in entries():
        item_id = int(item["item_id"])
        copies = owned.get(item_id, [])
        slot_key = "%s|%d|%d" % (item.get("table") or "",
                                 int(item.get("dmg_max") or 0),
                                 1 if item.get("ranged") else 0)
        if slot_key not in slot_sets:
            slot_sets[slot_key] = resolved_slots(item)
        rows.append({
            "item_id": item_id,
            "name": item["name"],
            "kind": item.get("kind") or "armor",
            "slot": item.get("slot") or "",
            "group": item.get("group") or "",
            "family": item.get("family") or "",
            "quality": item.get("quality") or "",
            "table": item.get("table") or "",
            "ranged": bool(item.get("ranged")),
            "dmg_max": int(item.get("dmg_max") or 0),
            "slot_set": slot_key,
            "copies": copies,
            "owned": bool(copies),
        })
    order = {"alluvion": 0, "skirmish": 1}
    rows.sort(key=lambda row: (order.get(row["family"], 9), row["group"],
                               row["kind"], row["name"]))
    return {
        "note": data().get("note", ""),
        "sources": list(data().get("sources") or ()),
        "slot_sets": slot_sets,
        "items": rows,
        "catalog_size": len(entries()),
    }


def apply(service, character_id: int, container, slot, picks) -> dict:
    """Write the chosen rows to one owned copy."""
    from . import capes

    row = _inventory_copy(service, character_id, container, slot)
    if row is None:
        raise LookupError("no item in that container slot")
    item = entry(int(row["item_id"]))
    if item is None:
        raise ValueError("that item has no Skirmish augments")
    checked = _checked_picks(item, picks)
    block = capes._encode_slots([
        slot_word(pick["key"], pick["value"], bool(item.get("ranged"))) if pick
        else (0, 0) for pick in checked])
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {"container": int(container), "slot": int(slot),
            "item_id": int(row["item_id"]), "name": item["name"],
            "augments": [stat_text(pick["key"], pick["value"])
                         for pick in checked if pick]}


def clear(service, character_id: int, container, slot) -> dict:
    """Write the empty standard block (no augments)."""
    from . import capes

    row = _inventory_copy(service, character_id, container, slot)
    if row is None:
        raise LookupError("no item in that container slot")
    item = entry(int(row["item_id"]))
    if item is None:
        raise ValueError("that item has no Skirmish augments")
    block = capes._encode_slots([])
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {"container": int(container), "slot": int(slot),
            "item_id": int(row["item_id"]), "name": item["name"]}
