"""The Moonshade Earring's two augment choices.

The Wings of the Goddess reward picks one option from each of two sets; both
words live in the earring's standard five-slot block.  ``data/moonshade.json``
holds the 16 fixed choices, and the ids and values are exactly the ones
LandSandBoat's ``54_Lest_We_Forget.lua`` passes to ``addItem`` (23/3 is
Accuracy+4, 353/4 is TP Bonus+250, ... so the block the card writes is the one
retail writes).  Every copy of the earring -- inventory, wardrobe, storage --
can carry a block; the card lists them all and writes the one you pick.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import capes

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "moonshade.json"

ITEM = 11697

_cache: dict | None = None


def data() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(PATH.read_text())
        except (OSError, ValueError):
            _cache = {"item_id": ITEM, "name": "Moonshade Earring", "sets": []}
    return _cache


def sets() -> list[dict]:
    """The two choice sets, each option carrying the tooltip it writes."""
    out = []
    for group in data().get("sets", []):
        options = []
        for option in group.get("options", []):
            option = {"key": str(option["key"]),
                      "id": int(option["id"]),
                      "value": int(option["value"])}
            option["text"] = capes._text(option["id"], option["value"])
            options.append(option)
        out.append({"key": str(group["key"]),
                    "label": str(group.get("label") or group["key"]),
                    "options": options})
    return out


def _option(sets_: list[dict], set_key: str, option_key: str) -> dict | None:
    group = next((item for item in sets_ if item["key"] == set_key), None)
    if group is None:
        return None
    return next((item for item in group["options"] if item["key"] == option_key), None)


def current(extra: bytes | None) -> dict | None:
    """What the block currently names, by choice key, plus its tooltip rows."""
    slots = capes.decode(extra)
    if slots is None:
        return None
    picked: dict[str, dict] = {}
    for slot in slots:
        if not int(slot["id"]):
            continue
        for group in sets():
            found = next((item for item in group["options"]
                          if item["id"] == int(slot["id"])
                          and item["value"] == int(slot["value"])), None)
            if found is not None:
                picked[group["key"]] = found
                break
    if not picked:
        return None
    text = [line for line in capes.describe(extra).split(", ") if line]
    return {
        "first": picked.get("first", {}).get("key"),
        "second": picked.get("second", {}).get("key"),
        "text": text,
    }


def _copy(service, character_id: int, container: int, slot: int) -> dict:
    row = next((item for item in service.inventory(int(character_id))
                if int(item["container"]) == int(container)
                and int(item["slot"]) == int(slot)), None)
    if row is None:
        raise LookupError("no item in that container slot")
    if int(row["item_id"]) != ITEM:
        raise ValueError("that item is not a Moonshade Earring")
    return row


def catalog(service, character_id: int) -> dict:
    copies = []
    for item in service.inventory(int(character_id)):
        if int(item["item_id"]) != ITEM:
            continue
        copies.append({"container": int(item["container"]),
                       "container_name": capes.container_label(int(item["container"])),
                       "slot": int(item["slot"]),
                       "current": current(item.get("extra"))})
    copies.sort(key=lambda row: (row["container"], row["slot"]))
    return {
        "item_id": ITEM,
        "name": data().get("name") or "Moonshade Earring",
        "note": data().get("note") or "",
        "sets": sets(),
        "copies": copies,
    }


def apply(service, character_id: int, container: int, slot: int,
          first: str, second: str) -> dict:
    """Write the chosen Set 1 and Set 2 option to one earring copy."""
    row = _copy(service, character_id, container, slot)
    groups = sets()
    picks = []
    for set_key, option_key in (("first", first), ("second", second)):
        option = _option(groups, set_key, option_key)
        if option is None:
            raise ValueError("%r is not an option from %s" % (option_key, set_key))
        picks.append((option["id"], option["value"]))
    block = capes._encode_slots(picks)
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {"container": int(container), "slot": int(slot),
            "item_id": int(row["item_id"]), "name": data().get("name"),
            "current": current(block)}


def clear(service, character_id: int, container: int, slot: int) -> dict:
    """Write the empty standard block."""
    row = _copy(service, character_id, container, slot)
    block = capes._encode_slots([])
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {"container": int(container), "slot": int(slot),
            "item_id": int(row["item_id"]), "name": data().get("name"),
            "current": None}
