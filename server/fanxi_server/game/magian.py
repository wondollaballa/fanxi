"""Trial of the Magians equipment blocks (standard augments plus a trial id).

A Magian weapon carries the same 24-byte ``kind 0x02`` block as a standard
augment, with the TRIAL bit set in the sub-kind (``0x03 | 0x40``) and up to four
``(id, value)`` slots:

    offset 0   u8   kind        0x02
    offset 1   u8   sub-kind    0x43 (standard | trial)
    offset 2   4 x u16          11-bit augment id | 5-bit value << 11
    offset 10  u16  trial id
    offset 12  ...               trial-complete bit and padding

The ids use the client's Magian scaling rather than the cape table, which is why
``0x161`` value 19 is TP Bonus +1000 here (``(19 + 1) * 50``) while the
Moonshade Earring's standard block uses a different offset for +250.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from . import modifiers as mod

KIND = 0x02
STANDARD = 0x03
TRIAL = 0x40
SUBKIND = STANDARD | TRIAL
SLOTS = 4

# id -> (label, offset, multiplier, percent, modifier id or None)
TABLE = {
    0x161: ("TP Bonus", 1, 50, False, mod.TP_BONUS),
    0x147: ("Weapon skill damage", 1, 1, True, mod.WSD_ALL_HITS),
    0x08E: ("Store TP", 1, 1, False, mod.STORETP),
    0x019: ("Attack", 1, 1, False, mod.ATT),
    0x02D: ("DMG", 1, 1, False, None),
    0x2E4: ("DMG", 1, 1, False, None),
    0x2EA: ("Rng.DMG", 1, 1, False, None),
    0x2F9: ("Delay", 33, 1, False, None),
    0x2FC: ("Delay", 1, 1, False, None),
    0x2F5: ("Delay", 33, -1, False, None),
    0x434: ("Weapon skill damage", 9, 1, True, None),
    0x435: ("Weapon skill damage", 9, 1, True, None),
    0x436: ("Weapon skill damage", 9, 1, True, None),
    0x437: ("Weapon skill damage", 9, 1, True, None),
}


def encode(picks, trial_id: int = 0) -> bytes:
    """A 24-byte Magian block from ``(augment id, value)`` pairs."""
    data = bytearray(24)
    data[0] = KIND
    data[1] = SUBKIND
    for slot, (augment_id, value) in enumerate(list(picks)[:SLOTS]):
        if not 0 <= int(augment_id) <= 0x7FF:
            raise ValueError("augment id out of range: %r" % (augment_id,))
        if not 0 <= int(value) <= 0x1F:
            raise ValueError("augment value out of range: %r" % (value,))
        struct.pack_into("<H", data, 2 + slot * 2,
                         (int(augment_id) & 0x7FF) | ((int(value) & 0x1F) << 11))
    struct.pack_into("<H", data, 10, int(trial_id) & 0x7FFF)
    return bytes(data)


def decode(extra: bytes | None) -> dict | None:
    """The slots and trial id of a Magian block, or None for another block."""
    raw = bytes(extra or b"")
    if len(raw) < 12 or raw[0] != KIND or not (raw[1] & TRIAL):
        return None
    slots = []
    for slot in range(SLOTS):
        word = struct.unpack_from("<H", raw, 2 + slot * 2)[0]
        slots.append({"id": word & 0x7FF, "value": word >> 11})
    return {"slots": slots, "trial": struct.unpack_from("<H", raw, 10)[0]}


def _amount(entry, value: int) -> int:
    _, offset, multiplier, _, _ = entry
    return (int(value) + int(offset)) * int(multiplier)


def item_mods(extra: bytes | None) -> dict[int, int]:
    """The combat modifiers a Magian block contributes."""
    decoded = decode(extra)
    if decoded is None:
        return {}
    out: dict[int, int] = {}
    for slot in decoded["slots"]:
        entry = TABLE.get(int(slot["id"]))
        if entry is None or entry[4] is None:
            continue
        out[int(entry[4])] = out.get(int(entry[4]), 0) + _amount(entry, slot["value"])
    return out


def describe(extra: bytes | None) -> str:
    """The tooltip rows one Magian block contributes."""
    decoded = decode(extra)
    if decoded is None:
        return ""
    rows = []
    for slot in decoded["slots"]:
        entry = TABLE.get(int(slot["id"]))
        if entry is None:
            continue
        label, _, _, percent, _ = entry
        amount = _amount(entry, slot["value"])
        if not amount:
            continue
        rows.append("%s%s%d%s" % (label, "+" if amount > 0 else "", amount,
                                  "%" if percent else ""))
    return ", ".join(rows)


# --- trial catalogue (data/magian.json) -------------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "magian.json"

_cache: dict | None = None


def data() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(PATH.read_text())
        except (OSError, ValueError):
            _cache = {"items": {}, "note": "", "sources": [], "catalog_size": 0}
    return _cache


def entry(item_id: int) -> dict | None:
    return data().get("items", {}).get(str(int(item_id)))


def trial_text(trial: dict) -> list[str]:
    """The tooltip rows a trial reward carries (wiki text first, else decoded)."""
    if trial.get("text"):
        return list(trial["text"])
    block = encode(trial.get("augments") or (), int(trial["id"]))
    return [line for line in describe(block).split(", ") if line]


def catalog(service, character_id: int) -> dict:
    """Every trial item with its immediate trials and the character's copies."""
    inventory = service.inventory(int(character_id))
    by_item: dict[int, list[dict]] = {}
    for row in inventory:
        by_item.setdefault(int(row["item_id"]), []).append(row)
    items = []
    for key, item in data().get("items", {}).items():
        item_id = int(key)
        copies = []
        for row in by_item.get(item_id, ()):
            copies.append({
                "container": int(row["container"]),
                "slot": int(row["slot"]),
                "container_name": _container_name(int(row["container"])),
                "current": describe(row.get("extra")) or "no trial",
            })
        trials = []
        for trial in item.get("trials", ()):
            reward = int(trial.get("reward") or item_id)
            reward_item = data().get("items", {}).get(str(reward), {})
            trials.append({
                "id": int(trial["id"]),
                "reward": reward,
                "reward_name": reward_item.get("name") or "Item",
                "num": int(trial.get("num") or 0),
                "text": trial_text(trial),
            })
        if not trials and not copies:
            continue
        items.append({
            "item_id": item_id,
            "name": item["name"],
            "slot": item.get("slot") or "",
            "level": int(item.get("level") or 0),
            "kind": "weapon" if (item.get("slot") or "") in
                    ("main", "sub", "range") else "armor",
            "trials": trials,
            "copies": copies,
        })
    items.sort(key=lambda row: (row["kind"], row["slot"], row["name"].casefold()))
    return {
        "note": data().get("note") or "",
        "sources": data().get("sources") or [],
        "catalog_size": len(items),
        "items": items,
    }


def _container_name(container: int) -> str:
    from . import capes
    return capes.container_label(container)


def apply(service, character_id: int, container: int, slot: int, trial_id: int) -> dict:
    """Complete one trial on a bag copy: the reward item and its augment block."""
    row = next((item for item in service.inventory(int(character_id))
                if int(item["container"]) == int(container)
                and int(item["slot"]) == int(slot)), None)
    if row is None:
        raise LookupError("no item in that container slot")
    item = entry(int(row["item_id"]))
    if item is None:
        raise ValueError("that item has no Magian trials")
    trial = next((candidate for candidate in item.get("trials", ())
                  if int(candidate["id"]) == int(trial_id)), None)
    if trial is None:
        raise ValueError("that trial is not offered by this item")
    block = encode(trial.get("augments") or (), int(trial_id))
    reward = int(trial.get("reward") or row["item_id"])
    if reward != int(row["item_id"]):
        if not service.set_item_and_extra(int(character_id), int(container), int(slot),
                                          reward, block):
            raise LookupError("the item row disappeared")
    elif not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {"container": int(container), "slot": int(slot),
            "item_id": reward, "trial": int(trial_id), "augments": trial.get("augments") or []}
