"""Nolan mezzotint augments for Escha gear.

Nolan, at Norg (I-7), re-forges the Escha - Zi'Tah and Escha - Ru'Aun weapons, the
Zi'Tah armor sets and the NQ/HQ abjuration sets ("mezzotinting").  Every piece
picks one of four paths, A-D, then climbs fifteen ranks with Eschalixirs.  Paths
A/B/C are shared by all five pieces of an armor set; path D is per piece.

The client stores the result in the **mezzotint** exdata block, not the
five-slot standard block the capes use::

    offset 0   u8   kind       0x02  (has augments)
    offset 1   u8   subkind    0x20  (mezzotint flag)
    offset 2   u8   path:2 | rank:5 | padding:1
    offset 3   u8   padding
    offset 4   u16  accumulated RP inside the current rank
    offset 6   u8[3] (augment index, value) for the block's three rows
    offset 12  u8[12] signature

The layout matches LandSandBoat's ``Exdata::AugmentMezzotint``.  The rank-15
maximum for a path is three ``(index, value)`` rows; the value byte is one less
than the number the client prints (the table offset is 1), and reductions carry
a negative multiplier.  Ranking up is the client's own job in retail; this
server writes the top rank in one step, the same way the RP card caps a path.

``data/nolan_mezzotint.json`` is the BG Wiki Nolan page as data: every item's
item id, slot, set and four paths with their Rank 15 rows (captured 2026-10-27).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from .capes import container_label

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "nolan_mezzotint.json"

KIND = 0x02
SUBKIND = 0x20
PATHS = "ABCD"
MAX_RANK = 15
SLOTS = 3
# Total RP spent on the way to Rank 15 (BG Wiki's Escha table).
RP_TOTAL = 5980

# key -> (label, augment index, sign, percent)
#
# ``sign`` is the direction the stat always moves: -1 for the rows the client
# prints as a reduction ("Phys. dmg. taken-4%") and 0 for Enmity, which is the
# one stat that can be either.  ``percent`` only affects the tooltip.
STATS: dict[str, tuple[str, int, int, bool]] = {
    "hp": ("HP", 0x02, 1, False),
    "mp": ("MP", 0x04, 1, False),
    "attack": ("Attack", 0x08, 1, False),
    "ratt": ("Rng.Atk.", 0x0A, 1, False),
    "acc": ("Accuracy", 0x0C, 1, False),
    "racc": ("Rng.Acc.", 0x0E, 1, False),
    "def": ("DEF", 0x10, 1, False),
    "eva": ("Evasion", 0x12, 1, False),
    "mab": ("Mag.Atk.Bns.", 0x14, 1, False),
    "mdb": ("Mag.Def.Bns.", 0x16, 1, False),
    "macc": ("Mag. Acc.", 0x18, 1, False),
    "meva": ("Mag. Evasion", 0x1A, 1, False),
    "dmg": ("DMG", 0x1C, 1, False),
    "wsd": ("Weapon skill damage", 0x72, 1, True),
    "magic_damage": ("Magic damage", 0x73, 1, False),
    "bp_damage": ("Blood Pact Dmg.", 0x74, 1, False),
    "avatar_perp": ("Avatar perpetuation cost", 0x75, -1, False),
    "bp_delay": ("Blood Pact ability delay", 0x76, -1, False),
    "haste": ("Haste", 0x77, 1, True),
    "enmity": ("Enmity", 0x78, 0, False),
    "crit_rate": ("Crit. hit rate", 0x7A, 1, True),
    "cure_cast_time": ("Cure spellcasting time", 0x7B, -1, True),
    "cure_potency": ("Cure potency", 0x7C, 1, True),
    "refresh": ("Refresh", 0x7D, 1, False),
    "spell_interrupt": ("Spell interruption rate down", 0x7E, -1, True),
    "cure_received": ("Potency of Cure effect received", 0x7F, 1, True),
    "pet_mab": ('Pet: Mag.Atk.Bns.', 0x80, 1, False),
    "pet_macc": ("Pet: Mag. Acc.", 0x81, 1, False),
    "pet_attack": ("Pet: Attack", 0x82, 1, False),
    "pet_acc": ("Pet: Accuracy", 0x83, 1, False),
    "pet_enmity": ("Pet: Enmity", 0x84, 1, False),
    "pet_hp": ("Pet: HP", 0x86, 1, False),
    "pet_mp": ("Pet: MP", 0x87, 1, False),
    "pet_str": ("Pet: STR", 0x88, 1, False),
    "pet_dex": ("Pet: DEX", 0x89, 1, False),
    "pet_vit": ("Pet: VIT", 0x8A, 1, False),
    "pet_agi": ("Pet: AGI", 0x8B, 1, False),
    "pet_int": ("Pet: INT", 0x8C, 1, False),
    "pet_mnd": ("Pet: MND", 0x8D, 1, False),
    "pet_chr": ("Pet: CHR", 0x8E, 1, False),
    "pet_da": ('Pet: "Dbl. Atk."', 0x98, 1, True),
    "pet_dt": ("Pet: Damage taken", 0x99, -1, True),
    "pet_regen": ('Pet: "Regen"', 0x9A, 1, False),
    "pet_haste": ("Pet: Haste", 0x9B, 1, True),
    "automaton_cure_potency": ('Automaton: "Cure" potency', 0x9C, 1, True),
    "automaton_fast_cast": ('Automaton: "Fast Cast"', 0x9D, 1, True),
    "dw": ('"Dual Wield"', 0xAB, 1, False),
    "dt": ("Damage taken", 0xAC, -1, True),
    "all_songs": ("All songs", 0xAD, 1, False),
    "conserve_mp": ('"Conserve MP"', 0xB1, 1, False),
    "counter": ('"Counter"', 0xB2, 1, False),
    "ta": ('"Triple Atk."', 0xB3, 1, True),
    "fast_cast": ('"Fast Cast"', 0xB4, 1, True),
    "blood_boon": ('"Blood Boon"', 0xB5, 1, False),
    "subtle_blow": ('"Subtle Blow"', 0xB6, 1, False),
    "rapid_shot": ('"Rapid Shot"', 0xB7, 1, False),
    "recycle": ('"Recycle"', 0xB8, 1, False),
    "stp": ('"Store TP"', 0xB9, 1, False),
    "da": ('"Dbl.Atk."', 0xBA, 1, True),
    "snapshot": ('"Snapshot"', 0xBB, 1, False),
    "pdt": ("Phys. dmg. taken", 0xBC, -1, True),
    "mdt": ("Magic dmg. taken", 0xBD, -1, True),
    "breath_dt": ("Breath dmg. taken", 0xBE, -1, True),
    "str": ("STR", 0xBF, 1, False),
    "dex": ("DEX", 0xC0, 1, False),
    "vit": ("VIT", 0xC1, 1, False),
    "agi": ("AGI", 0xC2, 1, False),
    "int": ("INT", 0xC3, 1, False),
    "mnd": ("MND", 0xC4, 1, False),
    "chr": ("CHR", 0xC5, 1, False),
    "all_stats": ("All Stats", 0xCE, 1, False),
    "h2h_skill": ("Hand-to-Hand skill", 0xD0, 1, False),
    "dagger_skill": ("Dagger skill", 0xD1, 1, False),
    "sword_skill": ("Sword skill", 0xD2, 1, False),
    "great_sword_skill": ("Great Sword skill", 0xD3, 1, False),
    "axe_skill": ("Axe skill", 0xD4, 1, False),
    "great_axe_skill": ("Great Axe skill", 0xD5, 1, False),
    "scythe_skill": ("Scythe skill", 0xD6, 1, False),
    "polearm_skill": ("Polearm skill", 0xD7, 1, False),
    "katana_skill": ("Katana skill", 0xD8, 1, False),
    "great_katana_skill": ("Great Katana skill", 0xD9, 1, False),
    "club_skill": ("Club skill", 0xDA, 1, False),
    "staff_skill": ("Staff skill", 0xDB, 1, False),
    "automaton_melee_skill": ("Automaton: Melee skill", 0xE5, 1, False),
    "automaton_ranged_skill": ("Automaton: Ranged skill", 0xE6, 1, False),
    "automaton_magic_skill": ("Automaton: Magic skill", 0xE7, 1, False),
    "shield_skill": ("Shield skill", 0xED, 1, False),
    "divine_skill": ("Divine magic skill", 0xEF, 1, False),
    "healing_skill": ("Healing magic skill", 0xF0, 1, False),
    "enhancing_skill": ("Enhancing magic skill", 0xF1, 1, False),
    "enfeebling_skill": ("Enfeebling magic skill", 0xF2, 1, False),
    "elemental_skill": ("Elemental magic skill", 0xF3, 1, False),
    "dark_skill": ("Dark magic skill", 0xF4, 1, False),
    "summoning_skill": ("Summoning magic skill", 0xF5, 1, False),
    "ninjutsu_skill": ("Ninjutsu skill", 0xF6, 1, False),
    "singing_skill": ("Singing skill", 0xF7, 1, False),
    "string_skill": ("String instrument skill", 0xF8, 1, False),
    "wind_skill": ("Wind instrument skill", 0xF9, 1, False),
    "blue_skill": ("Blue Magic skill", 0xFA, 1, False),
    "geomancy_skill": ("Geomancy skill", 0xFB, 1, False),
    "handbell_skill": ("Handbell skill", 0xFC, 1, False),
}

BY_INDEX = {entry[1]: key for key, entry in STATS.items()}
BY_INDEX[0x79] = "enmity"  # the Enmity- row, chosen by value sign
MAX_RAW = 0xFF

_cache: dict | None = None


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


def stat_text(key: str, value: int) -> str:
    """The tooltip text one ``(key, value)`` row stands for."""
    label, _index, sign, percent = STATS[key]
    value = int(value)
    if key == "dmg":
        return "DMG:+%d" % value
    amount = value if sign in (0, 1) else -abs(value)
    if key == "enmity" and amount < 0:
        return "%s-%d" % (label, -amount)
    return "%s%s%d%s" % (label, "+" if amount >= 0 else "", amount,
                         "%" if percent else "")


def _raw(key: str, value: int) -> tuple[int, int]:
    """``(index, value byte)`` for one stat row."""
    label, index, sign, _percent = STATS[key]
    value = int(value)
    if key == "enmity":
        if value == 0:
            raise ValueError("Enmity must be positive or negative")
        index = 0x78 if value > 0 else 0x79
        return index, (abs(value) - 1) & 0xFF
    if sign < 0:
        if value > 0:
            value = -value
        raw = abs(value) - 1
    else:
        raw = value - 1
    if not 0 <= raw <= MAX_RAW:
        raise ValueError("%s value out of range: %r" % (label, value))
    return int(index), int(raw)


def encode(path: str, rows, rank: int = MAX_RANK, rp: int = 0) -> bytes:
    """A 24-byte mezzotint block: path A-D, rank, RP and three stat rows."""
    letter = str(path or "").strip().upper()[:1]
    if letter not in PATHS:
        raise ValueError("path must be one of A, B, C, D")
    rows = list(rows or ())
    if len(rows) > SLOTS:
        raise ValueError("mezzotint stores three augment rows")
    try:
        rank = int(rank)
        rp = int(rp)
    except (TypeError, ValueError):
        raise ValueError("rank and rp must be numbers") from None
    if not 1 <= rank <= MAX_RANK:
        raise ValueError("rank must be 1..%d" % MAX_RANK)
    if not 0 <= rp <= 0xFFFF:
        raise ValueError("rp must be 0..65535")
    data = bytearray(24)
    data[0] = KIND
    data[1] = SUBKIND
    data[2] = (PATHS.index(letter) & 0x03) | ((rank & 0x1F) << 2)
    struct.pack_into("<H", data, 4, rp)
    for slot, row in enumerate(rows):
        index, raw = _raw(str(row["key"]), int(row["value"]))
        data[6 + slot * 2] = index
        data[7 + slot * 2] = raw
    return bytes(data)


def decode(extra: bytes | None) -> dict | None:
    """Read a mezzotint block back into path, rank, RP and stat rows."""
    if not extra or len(extra) < 12:
        return None
    raw = bytes(extra)
    if raw[0] != KIND or not (raw[1] & SUBKIND):
        return None
    value = raw[2]
    path = PATHS[value & 0x03]
    rank = (value >> 2) & 0x1F
    rp = struct.unpack_from("<H", raw, 4)[0]
    rows = []
    for slot in range(SLOTS):
        index = raw[6 + slot * 2]
        stored = raw[7 + slot * 2]
        if not index:
            continue
        key = BY_INDEX.get(index)
        if key is None:
            rows.append({"key": "index_%d" % index, "label": "augment %d" % index,
                         "value": stored, "text": "augment %d value %d" % (index, stored)})
            continue
        label, _index, sign, percent = STATS[key]
        amount = (stored + 1) * (sign if sign else 1)
        if sign == 0:
            amount = (stored + 1) * (1 if index == 0x78 else -1)
        rows.append({"key": key, "label": label, "value": amount,
                     "text": stat_text(key, amount)})
    return {"path": path, "rank": rank, "rp": rp, "rows": rows,
            "text": ", ".join(row["text"] for row in rows)}


def describe(extra: bytes | None) -> str:
    decoded = decode(extra)
    if decoded is None:
        return "not augmented"
    if not decoded["rows"]:
        return "not augmented"
    return "Type %s/Rank %d · %s" % (
        decoded["path"], decoded["rank"],
        " | ".join(row["text"] for row in decoded["rows"]))


def copies(service, character_id: int) -> dict[int, list[dict]]:
    """item id -> inventory copies for every mezzotint catalog item."""
    known = {int(item["item_id"]) for item in entries()}
    out: dict[int, list[dict]] = {}
    for item in service.inventory(int(character_id)):
        item_id = int(item["item_id"])
        if item_id not in known:
            continue
        out.setdefault(item_id, []).append({
            "container": int(item["container"]),
            "container_name": container_label(int(item["container"])),
            "slot": int(item["slot"]),
            "quantity": int(item.get("quantity") or 1),
            "current": decode(item.get("extra")),
        })
    return out


def catalog(service, character_id: int) -> dict:
    """The Data page's Nolan card: owned pieces and their four paths."""
    owned = copies(service, character_id)
    rows = []
    for item in entries():
        found = owned.get(int(item["item_id"]), [])
        if not found:
            continue
        paths = {}
        for letter in PATHS:
            rows_in = item["paths"].get(letter) or ()
            paths[letter] = [
                {"key": str(row["key"]), "value": int(row["value"]),
                 "text": stat_text(str(row["key"]), int(row["value"]))}
                for row in rows_in
            ]
        rows.append({
            "item_id": int(item["item_id"]),
            "name": item["name"],
            "kind": item.get("kind") or "armor",
            "slot": item.get("slot") or "",
            "zone": item.get("zone") or "",
            "group": item.get("group") or "",
            "paths": paths,
            "copies": found,
        })
    rows.sort(key=lambda row: (row["group"], row["slot"], row["name"]))
    return {
        "note": data().get("note", ""),
        "levels": {"max_rank": MAX_RANK, "rp_total": RP_TOTAL, "slots": SLOTS},
        "items": rows,
        "catalog_size": len(entries()),
    }


def apply(service, character_id: int, container: int, slot: int, path: str) -> dict:
    """Write the Rank 15 block for one owned copy and path."""
    row = next((item for item in service.inventory(int(character_id))
                if int(item["container"]) == int(container)
                and int(item["slot"]) == int(slot)), None)
    if row is None:
        raise LookupError("no item in that container slot")
    item = entry(int(row["item_id"]))
    if item is None:
        raise ValueError("that item has no Nolan mezzotint paths")
    letter = str(path or "").strip().upper()[:1]
    rows = item["paths"].get(letter)
    if not rows:
        raise ValueError("that path is not offered by this item")
    block = encode(letter, rows)
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {"container": int(container), "slot": int(slot),
            "item_id": int(row["item_id"]), "name": item["name"],
            "path": letter, "rank": MAX_RANK, "augments": [
                stat_text(str(value["key"]), int(value["value"])) for value in rows]}
