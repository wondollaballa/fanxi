"""Temenos Furnace Rank 30 augments (Alabaster Matter and Murky Matter).

The four Furnace pieces -- Alabaster Mantle, Alabaster Earring, Murky Mantle and
Murky Ring -- are Limbus gear.  Their Rank 30 rows are fixed, but they do not use
the five Limbus armour sets' bundles:

* Alabaster Mantle, Murky Mantle and Murky Ring map onto ordinary standard
  augment ids, so a copy carries the same 24-byte ``AugmentStandard`` block an
  Ambuscade cape or a Skirmish piece does:

      Alabaster Mantle   Accuracy/Attack+25, Ranged Accuracy/Attack+25,
                         STR/DEX+15, Enmity-10
      Murky Mantle       Mag. Acc./Mag. Dmg.+25, INT+15, Enmity-10
      Murky Ring         Accuracy/Rng.Acc./Mag.Acc+15, Evasion/Mag.Eva.+10,
                         Critical hit rate+5%

  The picks are the client's own augment ids and five-bit values, so the block
  round-trips through :func:`capes.describe` (the RP card's rows and the stat
  sheet) and through :func:`augment_stats.item_mods` (combat).  ``rows`` in the
  dataset is the wiki's grouping; the client prints the ids' own text, which
  splits the two-stat rows (Accuracy+Attack and Ranged Accuracy+Attack) because
  there is no combined Accuracy+Ranged Accuracy id.

* Alabaster Earring's ``All Attr.+10`` row has no standard augment id.  Client
  bundle 468 carries exactly its three Rank 30 rows (Accuracy/Rng.Acc./Mag.Acc
  +15, All Attr.+10, Store TP+5), so the earring carries a bundle block instead.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import augments, capes

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "temenos_r30.json"

RP = 55800      # curve B's rank-30 RP total, the same Limbus uses
CURVE = 1

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
    """Every dataset piece, with its fixed Rank 30 block and display rows."""
    rank = int(data().get("rank", 30))
    rp = int(data().get("rp", RP))
    curve = int(data().get("curve", CURVE))
    out: list[dict] = []
    for item in data().get("items", []):
        bundle = int(item.get("bundle") or 0)
        if bundle:
            picks: list[tuple[int, int]] = []
            block = augments.bundle("A", rank, 3, bundle, rp=rp, curve=curve)
            rows = [str(line) for line in item.get("rows", [])]
        else:
            picks = [(int(pick[0]), int(pick[1])) for pick in item.get("picks", [])]
            block = capes._encode_slots(picks)
            rows = [line for line in capes.describe(block).split(", ") if line]
        out.append({
            "item_id": int(item["item_id"]),
            "name": item["name"],
            "slot": item.get("slot") or "",
            "set": "Temenos Furnace",
            "kind": "temenos",
            "block": block,
            "bundle": bundle,
            "picks": picks,
            "rows": rows,
            "paths": [{
                "key": "A",
                "label": "Rank 30",
                "bundle": bundle,
                "rank": rank,
                "tier": 3,
                "rp": rp,
                "curve": curve,
                "augments": rows,
                "picks": picks,
            }],
        })
    return out


def get(item_id: int) -> dict | None:
    for entry in entries():
        if int(entry["item_id"]) == int(item_id):
            return entry
    return None


def current(entry: dict, extra: bytes | None) -> dict | None:
    """The rank the copy already carries, when its block is this piece's."""
    raw = bytes(extra or b"")
    bundle = int(entry.get("bundle") or 0)
    path = entry["paths"][0]
    if bundle:
        build = augments.decode(raw)
        if build is None or int(build["index"]) != bundle:
            return None
        if int(build["rank"]) < int(path["rank"]):
            return None
        return {"path": path["key"], "rank": build["rank"], "tier": build["tier"],
                "rp": build["rp"], "curve": build["curve"], "bundle": bundle}
    if raw != entry["block"]:
        return None
    return {"path": path["key"], "rank": path["rank"], "tier": path["tier"],
            "rp": path["rp"], "curve": path["curve"], "bundle": 0}
