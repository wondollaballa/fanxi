"""Limbus Rank 30 lookup and item exdata.

The dataset lives in ``data/limbus_r30.json`` -- the top tier of the five
Limbus families at Superior 5, with every Rank 30 augment row and the client
augment bundle index for each piece.  The bundle names the four augment lines
in the client's own table, so a piece with the block below prints its Rank 30
tooltip; ``!r30`` remains the chat view of the same rows, and ``!rp30``
re-stamps the pieces a character is carrying.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import augments

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "limbus_r30.json"

# Curve B is the Limbus RP curve: 1,600 RP for rank 1 and 55,800 in total at
# rank 30 (the client's xi.data.augments.rpCurves table).
RP = 55800
CURVE = 1

_cache: dict | None = None


def data() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(PATH.read_text())
        except (OSError, ValueError):
            _cache = {"families": {}}
    return _cache


def entries() -> list[dict]:
    """Every Limbus top-tier piece, with its Rank 30 rows and bundle."""
    out: list[dict] = []
    for family in data().get("families", {}).values():
        for slot, piece in family.get("pieces", {}).items():
            out.append({"name": piece["name"], "id": int(piece["item_id"]),
                        "set": family["set"], "slot": slot,
                        "paths": {"Rank 30": list(piece["augments"])},
                        "bundles": None, "bundle": piece.get("bundle")})
    return out


def find(query: str) -> list[dict]:
    """Items whose name contains *query*; else items whose set name does."""
    want = " ".join(str(query or "").split()).casefold()
    if not want:
        return []
    named = [entry for entry in entries() if want in entry["name"].casefold()]
    if named:
        return named
    return [entry for entry in entries() if want in entry["set"].casefold()]


def get(item_id: int) -> dict | None:
    """The entry for an item id, or None."""
    for entry in entries():
        if entry["id"] == int(item_id):
            return entry
    return None


def extra(entry: dict) -> bytes:
    """The 24-byte Rank 30 block for one entry (its bundle must be known)."""
    bundle = entry.get("bundle")
    if bundle is None:
        raise ValueError("no augment bundle for %s" % entry.get("name"))
    return augments.bundle("A", int(data().get("rank", 30)), 3, int(bundle),
                           rp=int(data().get("rp", RP)),
                           curve=int(data().get("rp_curve", CURVE)))


def blocks() -> dict[int, bytes]:
    """item id -> its Rank 30 augment block, for every piece in the dataset."""
    return {entry["id"]: extra(entry) for entry in entries()
            if entry.get("bundle") is not None}
