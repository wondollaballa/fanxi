"""Sinister Reign's augmented gear drops.

Sinister Reign's rewards are ordinary iL119 pieces that carry a random augment
block.  The client's tooltip reads the same **standard five-slot block** the
Ambuscade capes, Oseem glyptics and Skirmish gear use::

    02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12

Each slot is a little-endian u16 holding ``id:11 | value:5``; the client prints
``(value + offset) * multiplier`` for the id.  The ids live in
:mod:`skirmish` (the client's augment table), which is why this module encodes
through ``skirmish.slot_word`` instead of carrying a second copy of the table.

``data/sinister_reign.json`` holds every piece the BG Wiki category lists (37:
16 weapons/ranged and 21 armour pieces) and the highest value each row can roll.
FFXIclopedia phrases the same rows as ranges (Samnuha Tights: STR+1~10, DEX+1~10,
Double Attack+1~3%, Triple Attack+1~3%); the card writes the top of every range.

The launcher's Data page is the entry point: pick a piece (and the owned copy),
and one button writes all rows at their maximum.  Retail rolls them at random,
so this is a sandbox convenience, not an in-game NPC path.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from . import capes, skirmish

log = logging.getLogger("fanxi.sinister")

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "sinister_reign.json"

SLOT_NAMES = {
    "head": "Head",
    "body": "Body",
    "hands": "Hands",
    "legs": "Legs",
    "feet": "Feet",
    "main": "Weapon",
    "sub": "Weapon",
    "range": "Ranged",
    "ammo": "Ammo",
}

# The card's picker order: weapons, then armour top-down.
GROUP_ORDER = {"Weapons": 0, "Head": 1, "Body": 2, "Hands": 3, "Legs": 4, "Feet": 5}

_cache: dict | None = None


def missing() -> list[str]:
    """Dataset files this module needs but cannot read."""
    if PATH.is_file():
        return []
    try:
        return [str(PATH.relative_to(ROOT))]
    except ValueError:
        return [str(PATH)]


def data() -> dict:
    global _cache
    if _cache is None:
        absent = missing()
        if absent:
            log.warning("Sinister Reign dataset missing: %s; the card has no pieces",
                        ", ".join(absent))
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


def row_text(row: dict) -> str:
    """The tooltip text one row stands for."""
    return skirmish.stat_text(str(row["key"]), int(row["value"]))


def rows_of(item: dict) -> list[dict]:
    """The item's max rows, with the display text the card and client share."""
    out = []
    for row in item.get("rows") or ():
        out.append({
            "key": str(row["key"]),
            "value": int(row["value"]),
            "text": row_text(row),
        })
    return out


def _inventory_copy(service, character_id: int, container, slot):
    return next((row for row in service.inventory(int(character_id))
                 if int(row["container"]) == int(container)
                 and int(row["slot"]) == int(slot)), None)


def catalog(service, character_id: int) -> dict:
    """The Data page's Sinister Reign card: every piece and the owned copies."""
    known = {int(item["item_id"]) for item in entries()}
    owned: dict[int, list[dict]] = {}
    for row in service.inventory(int(character_id)):
        item_id = int(row["item_id"])
        if item_id not in known:
            continue
        picks = skirmish.decode_picks(row.get("extra"))
        owned.setdefault(item_id, []).append({
            "container": int(row["container"]),
            "container_name": capes.container_label(int(row["container"])),
            "slot": int(row["slot"]),
            "quantity": int(row.get("quantity") or 1),
            "current": skirmish.describe(row.get("extra")),
            "slots": [pick and skirmish.stat_text(pick["key"], pick["value"]) or ""
                      for pick in (picks or [])],
            "selection": picks,
        })
    items = []
    for item in entries():
        item_id = int(item["item_id"])
        slot = str(item.get("slot") or "")
        copies = owned.get(item_id, [])
        items.append({
            "item_id": item_id,
            "name": item["name"],
            "slot": slot,
            "slot_name": SLOT_NAMES.get(slot, slot.title() or "Gear"),
            "kind": item.get("kind") or "armor",
            "group": item.get("group") or SLOT_NAMES.get(slot, "Gear"),
            "rows": rows_of(item),
            "copies": copies,
            "owned": bool(copies),
        })
    items.sort(key=lambda row: (GROUP_ORDER.get(row["group"], 9),
                                row["name"].casefold()))
    return {
        "note": data().get("note", ""),
        "sources": list(data().get("sources") or ()),
        "items": items,
        "catalog_size": len(items),
    }


def apply_max(service, character_id: int, container, slot) -> dict:
    """Write every augment row of one owned piece at its maximum."""
    row = _inventory_copy(service, character_id, container, slot)
    if row is None:
        raise LookupError("no item in that container slot")
    item = entry(int(row["item_id"]))
    if item is None:
        raise ValueError("that item has no Sinister Reign augments")
    picks = [{"key": str(pick["key"]), "value": int(pick["value"])}
             for pick in item.get("rows") or ()]
    if not picks:
        raise ValueError("that item has no augment rows")
    block = skirmish.encode(picks)
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {
        "container": int(container),
        "slot": int(slot),
        "item_id": int(row["item_id"]),
        "name": item["name"],
        "augments": [row_text(pick) for pick in picks],
    }


def clear(service, character_id: int, container, slot) -> dict:
    """Write the empty standard block (no augments)."""
    row = _inventory_copy(service, character_id, container, slot)
    if row is None:
        raise LookupError("no item in that container slot")
    item = entry(int(row["item_id"]))
    if item is None:
        raise ValueError("that item has no Sinister Reign augments")
    block = skirmish.encode([])
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {
        "container": int(container),
        "slot": int(slot),
        "item_id": int(row["item_id"]),
        "name": item["name"],
    }
