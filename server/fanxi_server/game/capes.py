"""Ambuscade JSE cape augments.

Job-specific capes (``Artio's Mantle`` for Beastmaster, ``Andartia's Mantle`` for
Ninja, ``Ankou's Mantle`` for Dark Knight) are standard five-slot augments: every
slot is a 16-bit word holding an 11-bit augment id and a 5-bit augment value.  The
client turns the pair into a line of text with a fixed per-id rule:
``shown = (value + offset) * multiplier``.  ``TABLE`` is the slice of the
community extdata table these builds use: every id here has offset 1 except the
HP and MP blocks (1, 33, 65, 97) and the negative variants, which have multiplier
-1 and render with a minus.

The block itself is ``kind=0x02`` (standard augments), ``subkind=0x03``
(no trial, no mezzotint, no evolith), five words, then a 12-byte signature.
LandSandBoat stores the same layout as ``Exdata::AugmentStandard``.
"""

from __future__ import annotations

import struct

AUGMENT_KIND = 0x02
AUGMENT_SUBKIND = 0x03
SLOTS = 5


# Canonical augment text -> (client augment id, stored value).  The text is the
# same string the GearSwap library uses, so the builds below read exactly like
# the Lua tables.
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
    "Attack+?": (0x019, 0),  # placeholder, not used by a build
    "Accuracy+20 Attack+20": (0x044, 19),
    "Evasion+10": (0x01F, 9),
    "Mag. Evasion+10": (0x025, 9),
    "Enmity+10": (0x027, 9),
    "Enmity-10": (0x028, 9),
    "Eva.+20 /Mag. Eva.+20": (0x051, 19),
    "Mag. Acc+20 /Mag. Dmg.+20": (0x050, 19),
    "Mag. Acc.+10": (0x023, 9),
    '"Store TP"+10': (0x08E, 9),
    '"Fast Cast"+10': (0x08C, 9),
    '"Dual Wield"+10': (0x092, 9),
    '"Mag.Atk.Bns."+10': (0x085, 9),
    "Weapon skill damage +10%": (0x147, 9),
    "Phys. dmg. taken-10%": (0x036, 9),
    "Magic dmg. taken-10%": (0x037, 9),
    "Damage taken-5%": (0x047, 4),
    # Stats: 0x200-0x206 are the positive stat block.
    "STR+10": (0x200, 9),
    "STR+20": (0x200, 19),
    "DEX+10": (0x201, 9),
    "DEX+20": (0x201, 19),
    "AGI+10": (0x203, 9),
    "AGI+20": (0x203, 19),
    "INT+10": (0x204, 9),
    "INT+20": (0x204, 19),
    "MND+10": (0x205, 9),
    "MND+20": (0x205, 19),
    # Pet family.
    "Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20": (0x07C, 19),
    "Pet: Attack+10 Pet: Rng.Atk.+10": (0x06B, 9),
    "Pet: Accuracy+20 Pet: Rng. Acc.+20": (0x06A, 19),
    "Pet: Mag. Acc.+10": (0x064, 9),
    "Pet: M.Acc.+20 Pet: M.Dmg.+20": (0x07D, 19),
    "Pet: Haste+10": (0x06F, 9),
    "Pet: Damage taken -5%": (0x070, 4),
}

# Beastmaster's nine Artio's Mantle builds, in the same order as gearswap/BST.lua.
BST_BUILDS = {
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
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        '"Store TP"+10',
        "Phys. dmg. taken-10%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "mabws": [
        "MND+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MND+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "pet_tp": [
        "Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20",
        "Pet: Attack+10 Pet: Rng.Atk.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
    "pet_dt": [
        "Pet: M.Acc.+20 Pet: M.Dmg.+20",
        "Pet: Accuracy+20 Pet: Rng. Acc.+20",
        "Pet: Mag. Acc.+10",
        "Pet: Haste+10",
        "Pet: Damage taken -5%",
    ],
}

# Ninja's eleven Andartia's Mantle builds, in the same order as gearswap/NIN.lua.
NIN_BUILDS = {
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
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        '"Store TP"+10',
        "Phys. dmg. taken-10%",
    ],
    "dw": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "DEX+10",
        '"Dual Wield"+10',
        "Phys. dmg. taken-10%",
    ],
    "fc": [
        "HP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Evasion+10",
        '"Fast Cast"+10',
        "Phys. dmg. taken-10%",
    ],
    "ninjutsu": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        '"Mag.Atk.Bns."+10',
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

# Dark Knight's ten Ankou's Mantle builds, in the same order as gearswap/DRK.lua.
DRK_BUILDS = {
    "fc": [
        "MP+60",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "MP+20",
        '"Fast Cast"+10',
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
    "tp": [
        "DEX+20",
        "Accuracy+20 Attack+20",
        "Accuracy+10",
        '"Store TP"+10',
        "Phys. dmg. taken-10%",
    ],
    "macc": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "Mag. Acc.+10",
        "Enmity-10",
        "Phys. dmg. taken-10%",
    ],
    "ws_str": [
        "STR+20",
        "Accuracy+20 Attack+20",
        "STR+10",
        "Weapon skill damage +10%",
        "Damage taken-5%",
    ],
    "ws_int": [
        "INT+20",
        "Mag. Acc+20 /Mag. Dmg.+20",
        "INT+10",
        "Weapon skill damage +10%",
        "Phys. dmg. taken-10%",
    ],
    "enmity": [
        "HP+60",
        "Eva.+20 /Mag. Eva.+20",
        "Evasion+10",
        "Enmity+10",
        "Phys. dmg. taken-10%",
    ],
}

# Job -> the one cape item all of its builds are copies of.
JOBS = {
    "BST": {"cape_id": 26254, "cape_name": "Artio's Mantle", "builds": BST_BUILDS},
    "NIN": {"cape_id": 26258, "cape_name": "Andartia's Mantle", "builds": NIN_BUILDS},
    "DRK": {"cape_id": 26253, "cape_name": "Ankou's Mantle", "builds": DRK_BUILDS},
}

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


# id -> (text, offset, multiplier, percent).  Kept small on purpose: it is the
# slice of the client table these capes use.  Tests assert every AUGMENTS entry
# resolves through it.
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
    0x036: ("Phys. dmg. taken", 1, -1, True),
    0x037: ("Magic dmg. taken", 1, -1, True),
    0x044: ("Accuracy", 1, 1, False),
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
    0x147: ("Weapon skill damage", 1, 1, True),
    0x200: ("STR", 1, 1, False),
    0x201: ("DEX", 1, 1, False),
    0x203: ("AGI", 1, 1, False),
    0x204: ("INT", 1, 1, False),
    0x205: ("MND", 1, 1, False),
}

# Slots whose single id renders two or more stats; describe() prints each.
EXTRA = {
    0x044: [("Attack", 1, 1, False)],
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
