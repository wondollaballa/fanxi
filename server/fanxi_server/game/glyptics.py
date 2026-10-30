"""Oseem's Arcane Glyptics: Reisenjima armor and weapon augments.

Oseem, at Norg (I-7), engraves Reisenjima gear with Pellucid, Fern and Taupe
stones.  The result is the **standard** five-slot augment block the Ambuscade
capes use::

    02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12

Each slot is ``id:11 | value:5`` and the client prints
``(value + offset) * multiplier`` for the id.  The table below is the slice of
the client's augment table these augments use; the offset-33 variants are the
client's own second block for values above 32 (Accuracy +33..64 and so on).

Retail rolls the five slots at random and the player keeps or rerolls the
item.  This editor goes the other way: pick the stat for every slot and write
its maximum, which is what the launcher's Data page is for.  The path columns
of the BG Wiki Arcane Glyptics tables (Melee, Ranged, Magic, Familiar, Healing)
decide which stats are offered for a piece.

``data/oseem_glyptics.json`` is that page as data: every Reisenjima armor piece
and weapon with each path's ``(stat, max)`` rows (captured 2026-10-27).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import capes

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "oseem_glyptics.json"

KIND = capes.AUGMENT_KIND
SUBKIND = capes.AUGMENT_SUBKIND
SLOTS = capes.SLOTS
MAX_VALUE = 32  # five-bit field: offset-1 rows carry values 1..32
MAX_EXT = 64  # offset-33 rows carry values 33..64

# key -> (label, sign, percent, rows)
#
# ``rows`` is ``(offset, id)`` for the client's value blocks, smallest first;
# the encoder picks the first row that can hold the requested number.  ``sign``
# -1 marks the rows the client prints as a reduction; the stored value is the
# magnitude.  Enmity is sign 0 and switches between ids 0x027 and 0x028.
STATS: dict[str, tuple[str, int, bool, tuple[tuple[int, int], ...]]] = {
    "hp": ("HP", 1, False, ((1, 0x001), (33, 0x002), (65, 0x003), (97, 0x004))),
    "mp": ("MP", 1, False, ((1, 0x009), (33, 0x00A), (65, 0x00B), (97, 0x00C))),
    "acc": ("Accuracy", 1, False, ((1, 0x017), (33, 0x03E))),
    "attack": ("Attack", 1, False, ((1, 0x019), (33, 0x041))),
    "racc": ("Ranged Accuracy", 1, False, ((1, 0x01B), (33, 0x03F))),
    "ratt": ("Ranged Attack", 1, False, ((1, 0x01D), (33, 0x042))),
    "evasion": ("Evasion", 1, False, ((1, 0x01F),)),
    "def": ("DEF", 1, False, ((1, 0x021),)),
    "macc": ("Magic Accuracy", 1, False, ((1, 0x023), (33, 0x040))),
    "meva": ("Magic Evasion", 1, False, ((1, 0x025),)),
    "enmity": ("Enmity", 0, False, ((1, 0x027), (1, 0x028))),
    "crit_rate": ("Critical Hit Rate", 1, True, ((1, 0x029),)),
    "haste": ("Haste", 1, True, ((1, 0x031),)),
    "spell_interrupt": ("Spell Interruption Rate Down", -1, True, ((1, 0x035),)),
    "pdt": ("Physical Damage Taken", -1, True, ((1, 0x036),)),
    "mdt": ("Magic Damage Taken", -1, True, ((1, 0x037),)),
    "magic_crit_rate": ("Magic Critical Hit Rate", 1, True, ((1, 0x039),)),
    "dt": ("Damage Taken", -1, True, ((1, 0x047),)),
    "mab": ("Magic Attack Bonus", 1, False, ((1, 0x085), (33, 0x046))),
    "rapid_shot": ("Rapid Shot", 1, False, ((1, 0x08B),)),
    "fast_cast": ("Fast Cast", 1, True, ((1, 0x08C),)),
    "conserve_mp": ("Conserve MP", 1, False, ((1, 0x08D),)),
    "stp": ("Store TP", 1, False, ((1, 0x08E),)),
    "da": ("Double Attack", 1, True, ((1, 0x08F),)),
    "ta": ("Triple Attack", 1, True, ((1, 0x090),)),
    "counter": ("Counter", 1, False, ((1, 0x091),)),
    "dw": ("Dual Wield", 1, True, ((1, 0x092),)),
    "repair": ("Repair Potency", 1, True, ((1, 0x155),)),
    "martial_arts": ("Martial Arts", 1, False, ((1, 0x097),)),
    "subtle_blow": ("Subtle Blow", 1, False, ((1, 0x0C3),)),
    "zanshin": ("Zanshin", 1, False, ((1, 0x0C6),)),
    "snapshot": ("Snapshot", 1, False, ((1, 0x0D3),)),
    "blood_boon": ("Blood Boon", 1, False, ((1, 0x0E9),)),
    "regen": ("Regen", 1, False, ((1, 0x089),)),
    "refresh": ("Refresh", 1, False, ((1, 0x08A),)),
    "occult": ("Occult Acumen", 1, False, ((1, 0x0ED),)),
    "wsa": ("Weapon Skill Accuracy", 1, False, ((1, 0x146),)),
    "wsd": ("Weapon Skill Damage", 1, True, ((1, 0x147),)),
    "crit_damage": ("Critical Hit Damage", 1, True, ((1, 0x148),)),
    "cure_potency": ("Cure Potency", 1, True, ((1, 0x149),)),
    "waltz": ("Waltz Potency", 1, True, ((1, 0x14A),)),
    "skillchain": ("Skillchain Damage", 1, True, ((1, 0x14C),)),
    "magic_burst": ("Magic Burst Damage", 1, True, ((1, 0x14E),)),
    "magic_crit_damage": ("Magic Critical Hit Damage", 1, True, ((1, 0x14F),)),
    "bp_delay": ("Blood Pact Ability Delay", -1, False, ((1, 0x140),)),
    "avatar_perp": ("Avatar Perpetuation Cost", -1, False, ((1, 0x141),)),
    "cure_cast_time": ("Cure Spellcasting Time", -1, True, ((1, 0x143),)),
    "drain": ('"Drain" and "Aspir" Potency', 1, False, ((1, 0x157),)),
    "cure_received": ("Cure Potency Received", 1, True, ((1, 0x164),)),
    "magic_damage": ("Magic Damage", 1, False, ((1, 0x16A),)),
    "block": ("Chance of Successful Block", 1, False, ((1, 0x16B),)),
    "bp_damage": ("Blood Pact Damage", 1, False, ((1, 0x171),)),
    "enhancing_duration": ("Enhancing Magic Duration", 1, False, ((0, 0x176),)),
    "indi_duration": ("Indi Effect Duration", 1, False, ((1, 0x4E2),)),
    "resist_paralyze": ("Resist Paralyze", 1, False, ((1, 0x0B2),)),
    "stun": ("Additional Effect: Stun", 1, False, ((0, 0x34C),)),
    "resist_silence": ("Resist Silence", 1, False, ((1, 0x0B4),)),
    "dmg": ("DMG", 1, False, ((1, 0x02D), (33, 0x04C))),
    "str": ("STR", 1, False, ((1, 0x200),)),
    "dex": ("DEX", 1, False, ((1, 0x201),)),
    "vit": ("VIT", 1, False, ((1, 0x202),)),
    "agi": ("AGI", 1, False, ((1, 0x203),)),
    "int": ("INT", 1, False, ((1, 0x204),)),
    "mnd": ("MND", 1, False, ((1, 0x205),)),
    "chr": ("CHR", 1, False, ((1, 0x206),)),
    "pet_acc": ("Pet: Accuracy", 1, False, ((1, 0x06A),)),
    "pet_attack": ("Pet: Attack", 1, False, ((1, 0x06B),)),
    "pet_crit": ("Pet: Critical Hit Rate", 1, True, ((1, 0x066),)),
    "pet_mab": ("Pet: Magic Attack Bonus", 1, False, ((1, 0x065),)),
    "pet_macc": ("Pet: Magic Accuracy", 1, False, ((1, 0x064),)),
    "pet_macc_mab": ("Pet: Magic Accuracy & Magic Attack Bonus", 1, False, ((1, 0x06C),)),
    "pet_regen": ("Pet: Regen", 1, False, ((1, 0x06E),)),
    "pet_haste": ("Pet: Haste", 1, True, ((1, 0x06F),)),
    "pet_dt": ("Pet: Damage Taken", -1, True, ((1, 0x070),)),
    "pet_pdt": ("Pet: Physical Damage Taken", -1, True, ((1, 0x076),)),
    "pet_stp": ("Pet: Store TP", 1, False, ((1, 0x073),)),
    "pet_sb": ("Pet: Subtle Blow", 1, False, ((1, 0x074),)),
    "pet_da": ("Pet: Double Attack", 1, True, ((1, 0x07B),)),
    "pet_str": ("Pet: STR", 1, False, ((1, 0x700),)),
    "pet_dex": ("Pet: DEX", 1, False, ((1, 0x701),)),
    "pet_vit": ("Pet: VIT", 1, False, ((1, 0x702),)),
    "pet_agi": ("Pet: AGI", 1, False, ((1, 0x703),)),
    "pet_int": ("Pet: INT", 1, False, ((1, 0x704),)),
    "pet_mnd": ("Pet: MND", 1, False, ((1, 0x705),)),
    "pet_chr": ("Pet: CHR", 1, False, ((1, 0x706),)),
    "enfeebling_skill": ("Enfeebling Magic Skill", 1, False, ((1, 0x123),)),
    "enhancing_skill": ("Enhancing Magic Skill", 1, False, ((1, 0x122),)),
    "elemental_skill": ("Elemental Magic Skill", 1, False, ((1, 0x124),)),
    "dark_skill": ("Dark Magic Skill", 1, False, ((1, 0x125),)),
    "summoning_skill": ("Summoning Magic Skill", 1, False, ((1, 0x126),)),
    "ninjutsu_skill": ("Ninjutsu Skill", 1, False, ((1, 0x127),)),
    "singing_skill": ("Singing Skill", 1, False, ((1, 0x128),)),
    "string_skill": ("String Instrument Skill", 1, False, ((1, 0x129),)),
    "wind_skill": ("Wind Instrument Skill", 1, False, ((1, 0x12A),)),
    "blue_skill": ("Blue Magic Skill", 1, False, ((1, 0x12B),)),
    "geomancy_skill": ("Geomancy Skill", 1, False, ((1, 0x12C),)),
    "handbell_skill": ("Handbell Skill", 1, False, ((1, 0x12D),)),
}

# ids that render two stats from one slot, keyed by id.
EXTRA = {
    0x046: [("macc", 33, 1)],
}

# id -> (key, offset)
BY_ID: dict[int, tuple[str, int]] = {}
for _key, (_label, _sign, _percent, _rows) in STATS.items():
    for _offset, _id in _rows:
        BY_ID.setdefault(int(_id), (_key, int(_offset)))

# The rows that are not part of the client's value blocks but are useful
# labels for the picker.
OFFENCE = ("dmg", "acc", "macc", "racc", "attack", "ratt", "mab")
BASE_STATS = ("str", "dex", "vit", "agi", "int", "mnd", "chr")

_cache: dict | None = None
_path_sets_cache: dict | None = None


def data() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(PATH.read_text())
        except (OSError, ValueError):
            _cache = {"items": []}
    return _cache


def entries() -> list[dict]:
    return list(data().get("items", ()))


def entry(item_id: int) -> dict | None:
    for item in entries():
        if int(item["item_id"]) == int(item_id):
            return item
    return None


def max_value(key: str) -> int:
    """The largest value this table can write for one stat."""
    _label, _sign, _percent, rows = STATS[key]
    offset, _id = rows[-1]
    return min(MAX_EXT, offset + 31)


def stat_text(key: str, value: int) -> str:
    label, sign, percent, _rows = STATS[key]
    value = int(value)
    if key == "dmg":
        return "DMG:+%d" % value
    if sign < 0 or (key == "enmity" and value < 0):
        amount = -abs(value)
        return "%s-%d%s" % (label, -amount, "%" if percent else "")
    return "%s+%d%s" % (label, value, "%" if percent else "")


def slot_word(key: str, value: int) -> tuple[int, int]:
    """``(id, five-bit value)`` for one stat at one number."""
    if key not in STATS:
        raise ValueError("unknown augment %r" % (key,))
    label, sign, _percent, rows = STATS[key]
    value = int(value)
    amount = abs(value) if sign < 0 else value
    if key == "enmity":
        if value == 0:
            return 0, 0
        index = 0x027 if value > 0 else 0x028
        return index, (abs(value) - 1) & 0x1F
    if amount <= 0:
        raise ValueError("%s value must be positive or negative, not %r" % (label, value))
    for offset, index in rows:
        stored = amount - offset
        if 0 <= stored <= 0x1F:
            return int(index), int(stored)
    raise ValueError("%s cannot hold %r (max %d)" % (label, value, max_value(key)))


def encode(choices) -> bytes:
    """A 24-byte standard block from five ``(key, value)`` picks.

    ``choices`` is a list of five entries; ``None`` (or an entry whose value is
    zero) leaves that slot empty.
    """
    words = []
    for choice in list(choices or ())[:SLOTS]:
        if not choice:
            words.append((0, 0))
            continue
        words.append(slot_word(str(choice["key"]), int(choice["value"])))
    words.extend([(0, 0)] * (SLOTS - len(words)))
    return capes._encode_slots(words)


def decode_slot(word: int) -> dict | None:
    augment_id = int(word) & 0x7FF
    stored = (int(word) >> 11) & 0x1F
    if not augment_id:
        return None
    rows = []
    found = BY_ID.get(augment_id)
    if found is None:
        rows.append({"key": "id_%d" % augment_id, "value": stored,
                     "text": "id %d value %d" % (augment_id, stored)})
    else:
        key, offset = found
        label, sign, percent, _table = STATS[key]
        if key == "enmity":
            amount = (stored + offset) * (1 if augment_id == 0x027 else -1)
        elif sign < 0:
            amount = -(stored + offset)
        else:
            amount = stored + offset
        rows.append({"key": key, "value": amount, "text": stat_text(key, amount)})
        for extra_key, extra_offset, extra_sign in EXTRA.get(augment_id, ()):
            extra_label, _s, extra_percent, _t = STATS[extra_key]
            extra_amount = (stored + extra_offset) * extra_sign
            rows.append({"key": extra_key, "value": extra_amount,
                         "text": stat_text(extra_key, extra_amount)})
    return {"id": augment_id, "stored": stored, "rows": rows,
            "text": " ".join(row["text"] for row in rows)}


def decode(extra: bytes | None) -> list[dict]:
    """The five slots of a standard block, with their text."""
    slots = capes.decode(extra)
    if slots is None:
        return []
    out = []
    for slot in slots:
        decoded = decode_slot((int(slot["value"]) << 11) | int(slot["id"]))
        out.append(decoded or {"id": 0, "rows": [], "text": ""})
    return out


def describe(extra: bytes | None) -> str:
    texts = [slot["text"] for slot in decode(extra) if slot["text"]]
    return " | ".join(texts) if texts else "not augmented"


def _capped_stats(item: dict, path_key: str) -> list[dict]:
    path = (item.get("paths") or {}).get(path_key) or {}
    out = []
    for row in path.get("stats") or ():
        key = str(row["key"])
        if key not in STATS:
            continue
        limit = max_value(key)
        value = int(row["max"])
        value = max(-limit, min(limit, value))
        if value == 0:
            continue
        out.append({"key": key, "max": value, "primary": bool(row.get("primary")),
                    "text": stat_text(key, value),
                    "clamped": abs(int(row["max"])) > limit})
    return out


SPECIAL_ORDER = (
    "wsd", "da", "ta", "stp", "crit_rate", "crit_damage", "fast_cast",
    "skillchain", "magic_burst", "magic_damage", "magic_crit_damage", "drain",
    "snapshot", "rapid_shot", "cure_potency", "cure_cast_time", "cure_received",
    "haste", "waltz", "subtle_blow", "dw", "conserve_mp", "occult",
    "counter", "block", "wsa", "zanshin", "martial_arts", "repair", "regen",
    "refresh", "blood_boon", "avatar_perp", "bp_delay", "bp_damage",
    "enhancing_duration", "indi_duration", "pet_da", "pet_stp", "pet_sb",
    "pet_haste", "pet_crit", "pet_regen", "resist_paralyze", "resist_silence",
    "stun",
)
PATH_OFFENCE = {
    "melee": ("dmg", "acc", "attack"),
    "ranged": ("dmg", "racc", "ratt"),
    "magic": ("dmg", "macc", "mab"),
    "healing": ("macc", "mab", "acc"),
    "familiar": ("dmg", "pet_acc", "pet_mab", "pet_attack", "acc"),
    "pet": ("dmg", "pet_acc", "pet_mab", "pet_attack", "acc"),
}
PET_BASE = ("pet_str", "pet_dex", "pet_vit", "pet_agi", "pet_int", "pet_mnd", "pet_chr")


def _defaults(stats: list[dict], path_key: str) -> list[dict]:
    """Five starting picks: the path's main offence then sensible fillers."""
    by_key = {row["key"]: row for row in stats}

    def take(*keys):
        for key in keys:
            row = by_key.get(key)
            if row is not None:
                return row
        return None

    def special():
        order = SPECIAL_ORDER
        if path_key in ("familiar", "pet"):
            order = (tuple(key for key in SPECIAL_ORDER if key.startswith("pet_"))
                     + tuple(key for key in SPECIAL_ORDER if not key.startswith("pet_")))
        preferred = [by_key[key] for key in order if key in by_key]
        if preferred:
            return preferred[0]
        for row in stats:
            if (row["key"] not in OFFENCE and row["key"] not in BASE_STATS
                    and row["key"] not in PET_BASE):
                return row
        return None

    picks = [
        take(*PATH_OFFENCE.get(path_key, ("dmg", "acc", "macc", "attack")))
        or take("dmg", "acc", "macc", "pet_acc", "attack"),
        special(),
        take(*(PET_BASE + BASE_STATS)),
        take("acc", "pet_acc", "macc", "racc", "pet_mab", "pet_attack"),
        take("attack", "ratt", "mab", "pet_attack", "pet_mab", "acc"),
    ]
    return [{"key": pick["key"], "value": pick["max"]} for pick in picks if pick is not None]


def _path_sets() -> dict[str, dict]:
    """The augment tables, built once: they depend on the data file, not the character."""
    global _path_sets_cache
    if _path_sets_cache is not None:
        return _path_sets_cache
    out: dict[str, dict] = {}
    for item in entries():
        key = (item["set"] if item.get("kind") == "armor"
               else "weapon:%d" % int(item["item_id"]))
        if key in out:
            continue
        paths = {}
        for path_key, path in (item.get("paths") or {}).items():
            stats = _capped_stats(item, path_key)
            paths[path_key] = {
                "label": path.get("label") or path_key.title(),
                "stats": stats,
                "defaults": _defaults(stats, path_key),
            }
        out[key] = {"label": item.get("set") or item["name"], "paths": paths}
    _path_sets_cache = out
    return out


def catalog(service, character_id: int) -> dict:
    """The Data page's Oseem card: owned pieces, paths and slot options."""
    known = {int(item["item_id"]) for item in entries()}
    owned: dict[int, list[dict]] = {}
    for row in service.inventory(int(character_id)):
        item_id = int(row["item_id"])
        if item_id not in known:
            continue
        decoded = decode(row.get("extra"))
        owned.setdefault(item_id, []).append({
            "container": int(row["container"]),
            "container_name": capes.container_label(int(row["container"])),
            "slot": int(row["slot"]),
            "quantity": int(row.get("quantity") or 1),
            "current": describe(row.get("extra")),
            "slots": [slot["text"] for slot in decoded],
            "selection": [
                ({"key": slot["rows"][0]["key"], "value": slot["rows"][0]["value"]}
                 if slot.get("rows") else None)
                for slot in decoded
            ],
        })
    # Every piece of an armor set shares one augment table, so the path data
    # lives once per set (or once per weapon) and the items point at it.  That
    # keeps the whole 39-item catalogue in the payload without repeating the
    # same five rows twenty-five times.
    path_sets = _path_sets()
    rows = []
    for item in entries():
        item_id = int(item["item_id"])
        copies = owned.get(item_id, [])
        key = (item["set"] if item.get("kind") == "armor"
               else "weapon:%d" % item_id)
        rows.append({
            "item_id": item_id,
            "name": item["name"],
            "kind": item.get("kind") or "armor",
            "slot": item.get("slot") or "",
            "set": item.get("set") or "",
            "zone": item.get("zone") or "",
            "path_key": key,
            "copies": copies,
            "owned": bool(copies),
        })
    rows.sort(key=lambda row: (row["kind"], row["set"], row["slot"], row["name"]))
    return {
        "note": data().get("note", ""),
        "slots": SLOTS,
        "path_sets": path_sets,
        "items": rows,
        "catalog_size": len(entries()),
    }


def _inventory_copy(service, character_id: int, container, slot):
    return next((row for row in service.inventory(int(character_id))
                 if int(row["container"]) == int(container)
                 and int(row["slot"]) == int(slot)), None)


def _checked_choices(item: dict, path_key: str, choices) -> list[dict]:
    path = (item.get("paths") or {}).get(path_key)
    if not path:
        raise ValueError("that path is not offered by this item")
    allowed = {str(row["key"]): int(row["max"]) for row in path.get("stats") or ()}
    out = []
    for choice in list(choices or ())[:SLOTS]:
        if not choice:
            out.append(None)
            continue
        if not isinstance(choice, dict):
            raise ValueError("each augment choice must be an object")
        key = str(choice.get("key") or "").strip()
        if key not in allowed:
            raise ValueError("%s is not a %s augment" % (key, path_key))
        value = int(choice.get("value") or 0)
        if value == 0:
            out.append(None)
            continue
        if not 0 < abs(value) <= max_value(key):
            raise ValueError("%s out of range: %r" % (key, value))
        if value > 0 and STATS[key][1] < 0:
            value = -value
        out.append({"key": key, "value": value})
    if not any(out):
        raise ValueError("pick at least one augment")
    out.extend([None] * (SLOTS - len(out)))
    return out


def apply(service, character_id: int, container, slot, path_key: str,
          choices) -> dict:
    """Write the five chosen slots to one owned copy."""
    row = _inventory_copy(service, character_id, container, slot)
    if row is None:
        raise LookupError("no item in that container slot")
    item = entry(int(row["item_id"]))
    if item is None:
        raise ValueError("that item has no Arcane Glyptics paths")
    path = next((key for key in (item.get("paths") or {})
                 if key.casefold() == str(path_key or "").strip().casefold()), None)
    if path is None:
        raise ValueError("that path is not offered by this item")
    picks = _checked_choices(item, path, choices)
    block = encode([pick for pick in picks])
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {"container": int(container), "slot": int(slot),
            "item_id": int(row["item_id"]), "name": item["name"], "path": path,
            "augments": [stat_text(pick["key"], pick["value"]) for pick in picks if pick]}


def clear(service, character_id: int, container, slot) -> dict:
    """Write the empty standard block (no augments)."""
    row = _inventory_copy(service, character_id, container, slot)
    if row is None:
        raise LookupError("no item in that container slot")
    if entry(int(row["item_id"])) is None:
        raise ValueError("that item has no Arcane Glyptics paths")
    block = capes._encode_slots([])
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {"container": int(container), "slot": int(slot),
            "item_id": int(row["item_id"]), "name": entry(int(row["item_id"]))["name"]}
