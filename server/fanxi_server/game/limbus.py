"""Limbus Rank 30 lookup for the ``!r30`` chat command.

The dataset lives in ``data/limbus_r30.json`` -- the top tier of the five
Limbus families at Superior 5, with every Rank 30 augment row.  The client
draws item tooltips from its own DAT files and cannot show these rows yet
(the augment bundle index for Limbus is still unknown), so ``!r30`` is the
in-game view of the table.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "limbus_r30.json"
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
    """Every Limbus top-tier piece, with its Rank 30 rows."""
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
