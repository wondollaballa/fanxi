"""Limbus Rank 30 lookup and item exdata.

Two datasets carry Limbus gear:

* ``data/limbus_r30.json`` -- the top tier of the five Limbus armour families at
  Superior 5, with every Rank 30 augment row and the client augment bundle index
  for each piece.  The bundle names the four augment lines in the client's own
  table, so a piece with the block below prints its Rank 30 tooltip.
* ``data/limbus_weapons_r30.json`` -- the sixteen Telopanos weapons the furnaces
  build from an Auge Scintistone: the fourteen weapon skills, the shield and the
  grip.  They work the same way (bundle index, curve-B RP, Rank 30) but are kept
  apart because they are not part of an armour set.

``//r30`` is the chat view of the same rows and ``//rp30`` re-stamps every Limbus
piece a character is carrying, weapons included.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import augments

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "limbus_r30.json"
WEAPONS_PATH = ROOT / "data" / "limbus_weapons_r30.json"

# Curve B is the Limbus RP curve: 1,600 RP for rank 1 and 55,800 in total at
# rank 30 (the client's xi.data.augments.rpCurves table).
RP = 55800
CURVE = 1
# The block's "max rank tier" field: 3 is the 30-rank unlock.  (The armour
# dataset's own ``tier`` key is the Superior level -- "Su5" -- not this field.)
TIER = 3

_cache: dict | None = None
_weapons_cache: dict | None = None


def data() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(PATH.read_text())
        except (OSError, ValueError):
            _cache = {"families": {}}
    return _cache


def weapons_data() -> dict:
    """The Telopanos weapons dataset (an empty one when the file is unreadable)."""
    global _weapons_cache
    if _weapons_cache is None:
        try:
            _weapons_cache = json.loads(WEAPONS_PATH.read_text())
        except (OSError, ValueError):
            _weapons_cache = {"weapons": []}
    return _weapons_cache


def entries() -> list[dict]:
    """Every Limbus top-tier armour piece, with its Rank 30 rows and bundle."""
    out: list[dict] = []
    for family in data().get("families", {}).values():
        for slot, piece in family.get("pieces", {}).items():
            out.append({"name": piece["name"], "id": int(piece["item_id"]),
                        "set": family["set"], "slot": slot,
                        "paths": {"Rank 30": list(piece["augments"])},
                        "bundles": None, "bundle": piece.get("bundle")})
    return out


def weapon_entries() -> list[dict]:
    """Every Telopanos weapon, with its Rank 30 rows and bundle."""
    doc = weapons_data()
    out: list[dict] = []
    for weapon in doc.get("weapons", []):
        out.append({"name": weapon["name"], "id": int(weapon["item_id"]),
                    "set": doc.get("set", "Telopanos"),
                    "slot": weapon.get("slot") or "",
                    "weapon": True,
                    "paths": {"Rank 30": list(weapon.get("augments") or ())},
                    "bundles": None, "bundle": weapon.get("bundle")})
    return out


def all_entries() -> list[dict]:
    """The armour suits and the weapons: everything the RP card/``//r30`` lists."""
    return entries() + weapon_entries()


def _source(entry: dict) -> dict:
    """The dataset an entry came from (its rank/RP/curve live there)."""
    return weapons_data() if entry.get("weapon") else data()


def find(query: str) -> list[dict]:
    """Items whose name contains *query*; else items whose set name does."""
    want = " ".join(str(query or "").split()).casefold()
    if not want:
        return []
    items = all_entries()
    named = [entry for entry in items if want in entry["name"].casefold()]
    if named:
        return named
    return [entry for entry in items if want in entry["set"].casefold()]


def get(item_id: int) -> dict | None:
    """The entry for an item id, or None."""
    for entry in all_entries():
        if entry["id"] == int(item_id):
            return entry
    return None


def extra(entry: dict) -> bytes:
    """The 24-byte Rank 30 block for one entry (its bundle must be known)."""
    bundle = entry.get("bundle")
    if bundle is None:
        raise ValueError("no augment bundle for %s" % entry.get("name"))
    source = _source(entry)
    return augments.bundle("A", int(source.get("rank", 30)), TIER, int(bundle),
                           rp=int(source.get("rp", RP)),
                           curve=int(source.get("rp_curve", CURVE)))


def blocks() -> dict[int, bytes]:
    """item id -> its Rank 30 augment block, for every piece in either dataset."""
    return {entry["id"]: extra(entry) for entry in all_entries()
            if entry.get("bundle") is not None}
