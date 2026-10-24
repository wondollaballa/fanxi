"""Augmentable gear paths for the launcher's RP card.

Three datasets expose a 24-byte ``AugmentBundle`` block:

* Odyssey ("Nyame" has four paths A-D, every other set/weapon one Rank 30 row),
* Limbus (one Rank 30 row per piece, RP curve B),
* Unity +1 accessories (one Rank 15 row, RP curve A).

The client draws the augment lines from the bundle index.  The RP field is the
accumulated total for the client's curve; the caps are the curve maxima in
``scripts/data/augments.lua``: curve A tops out at 4,750, curve B at 55,800,
and Unity's rank-15 point on curve A is 1,110.  Capping a path writes rank,
tier, bundle and RP in one block; the item's 0x020 attribute packet carries it
back to the client on ``!reload``.
"""
from __future__ import annotations

from . import augments, limbus, odyssey, unity

RP_ODYSSEY = 4750
RP_LIMBUS = 55800
RP_UNITY = 1110


def _path(key: str, label: str, bundle: int, rank: int, tier: int,
          rp: int, curve: int, rows) -> dict:
    return {
        "key": key,
        "label": label,
        "bundle": int(bundle),
        "rank": int(rank),
        "tier": int(tier),
        "rp": int(rp),
        "curve": int(curve),
        "augments": [str(row) for row in (rows or [])],
    }


def entries() -> dict[int, dict]:
    """Item id -> its augment paths, merged from the three datasets."""
    out: dict[int, dict] = {}
    for entry in odyssey.entries():
        item_id = int(entry["id"])
        if item_id in out:
            continue
        paths: list[dict] = []
        if entry.get("bundles"):
            for letter in "ABCD":
                bundle = entry["bundles"].get(letter)
                if bundle is None:
                    continue
                paths.append(_path(
                    letter, "Path %s" % letter, int(bundle), 30, 3,
                    RP_ODYSSEY, 0, entry["paths"].get(letter)))
        else:
            bundle = entry.get("bundle")
            if bundle is None:
                continue
            rows = entry["paths"].get("Rank 30") or next(iter(entry["paths"].values()), [])
            paths.append(_path("A", "Rank 30", int(bundle), 30, 3,
                               RP_ODYSSEY, 0, rows))
        if not paths:
            continue
        out[item_id] = {
            "item_id": item_id,
            "name": entry["name"],
            "slot": entry.get("slot") or "",
            "set": entry.get("set") or "",
            "kind": "odyssey",
            "paths": paths,
        }
    for entry in limbus.entries():
        item_id = int(entry["id"])
        if item_id in out or entry.get("bundle") is None:
            continue
        out[item_id] = {
            "item_id": item_id,
            "name": entry["name"],
            "slot": entry.get("slot") or "",
            "set": entry.get("set") or "",
            "kind": "limbus",
            "paths": [_path("A", "Rank 30", int(entry["bundle"]), 30, 3,
                            RP_LIMBUS, 1, entry["paths"].get("Rank 30"))],
        }
    for item_id, item in unity.ITEMS.items():
        if int(item_id) in out:
            continue
        out[int(item_id)] = {
            "item_id": int(item_id),
            "name": item["name"],
            "slot": item.get("slot") or "",
            "set": "Unity +1",
            "kind": "unity",
            "paths": [_path("A", "Rank 15 (Unity)", int(item["bundle"]), 15, 0,
                            RP_UNITY, 0, item.get("augments"))],
        }
    return out


def _registry() -> dict[int, dict]:
    return entries()


def inventory_items(service, character_id: int) -> list[dict]:
    """The character's augmentable copies, with their current block and paths."""
    registry = _registry()
    rows = []
    for item in service.inventory(int(character_id)):
        entry = registry.get(int(item["item_id"]))
        if entry is None:
            continue
        rows.append({
            "container": int(item["container"]),
            "slot": int(item["slot"]),
            "item_id": int(item["item_id"]),
            "name": entry["name"],
            "slot_name": entry.get("slot") or str(item.get("equip_slot") or ""),
            "set": entry.get("set") or "",
            "kind": entry["kind"],
            "quantity": int(item.get("quantity") or 1),
            "current": augments.decode(item.get("extra")),
            "paths": entry["paths"],
        })
    rows.sort(key=lambda row: (row["name"].casefold(), row["container"], row["slot"]))
    return rows


def cap(service, character_id: int, container: int, slot: int, path_key: str) -> dict:
    """Write the maximum block for one inventory copy and path."""
    registry = _registry()
    row = next((item for item in service.inventory(int(character_id))
                if int(item["container"]) == int(container)
                and int(item["slot"]) == int(slot)), None)
    if row is None:
        raise LookupError("no item in that container slot")
    entry = registry.get(int(row["item_id"]))
    if entry is None:
        raise ValueError("that item has no known augment paths")
    path = next((candidate for candidate in entry["paths"]
                 if str(candidate["key"]).upper() == str(path_key).strip().upper()), None)
    if path is None:
        raise ValueError("that path is not offered by this item")
    block = augments.bundle(path["key"], path["rank"], path["tier"],
                            path["bundle"], rp=path["rp"], curve=path["curve"])
    if not service.set_item_extra(int(character_id), int(container), int(slot), block):
        raise LookupError("the item row disappeared")
    return {"container": int(container), "slot": int(slot),
            "item_id": int(row["item_id"]), "name": entry["name"],
            "path": path}
