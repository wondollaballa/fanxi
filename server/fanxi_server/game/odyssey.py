"""Odyssey Rank 30 lookup for the ``!r30`` chat command.

The dataset lives in ``data/odyssey_r30.json`` (the same file the gearswap
generator reads), so the server and the libraries cannot disagree about an
augment.  The client draws item tooltips from its own DAT files and cannot show
these rows yet -- that needs retail's 24-byte ``extdata`` augment encoding --
so ``!r30`` is the in-game view of the table.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "odyssey_r30.json"
_cache: dict | None = None


def data() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(PATH.read_text())
        except (OSError, ValueError):
            _cache = {"sets": {}, "weapons": {}}
    return _cache


def entries() -> list[dict]:
    """Every Odyssey item, with its Rank 30 rows keyed by path."""
    out: list[dict] = []
    for set_key in ("nyame", "sakpata", "gleti", "agwu"):
        group = data().get("sets", {}).get(set_key)
        if not group:
            continue
        for piece in group["pieces"].values():
            rows = piece["augments"]
            paths = {path: rows[path] for path in ("A", "B", "C", "D")} if "R30" not in rows \
                else {"Rank 30": rows["R30"]}
            out.append({"name": piece["name"], "id": int(piece["item_id"]),
                        "set": group["set"], "slot": piece["slot"], "paths": paths,
                        "bundles": piece.get("bundles"),
                        "bundle": piece.get("bundle")})
    for weapon in data().get("weapons", {}).values():
        out.append({"name": weapon["name"], "id": int(weapon["item_id"]),
                    "set": "Odyssey weapon", "slot": weapon["slot"],
                    "paths": {"Rank 30": weapon["augments"]},
                    "bundles": None, "bundle": weapon.get("bundle")})
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


def bundle_for(name: str, path: str = "A") -> int | None:
    """The augment bundle index for an item and (for Nyame) a path."""
    for entry in find(name):
        if entry["bundles"]:
            return entry["bundles"].get(str(path).strip().upper())
        if entry["bundle"]:
            return int(entry["bundle"])
    return None
