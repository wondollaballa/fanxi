"""Unity Wanted iLvl 119+ gear: single-path Rank 15 augments.

A Unity +1 item is augmented at a Unity NPC with Lustreless items.  The client stores
the result in the same 24-byte ``AugmentBundle`` block Odyssey uses, but with Rank 15,
max-rank tier 0 (the 15-rank unlock) and one path.  The bundle index is the client's own
augment-table row for the item; every Unity piece is one of bundles 285-392, and the
rows below decode to the Rank 15 lines in ``data/unity_r15.json``.

The catalogue is the whole of BG Wiki's Unity Accessories, Unity Armor and Unity Weapons
categories -- 27 accessories, 32 armour pieces and 49 weapons/grips -- so the Data page's
RP card lists every Unity piece in the bags as soon as it is purchased, not just the
accessories the GearSwap libraries happen to carry.  The first five entries are still the
pieces the shared GearSwap ``local unity`` table defines: four accessories Ninja wears and
the ``Loess Barbuta +1``.  The block is what the client turns into tooltip text, and
``augment_stats`` also reads the Rank 15 rows into modifiers.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from . import augments

log = logging.getLogger("fanxi.unity")

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "data" / "unity_r15.json"

RANK = 15
TIER = 0  # 0 = the 15-rank unlock
PATH_LETTER = "A"
RP = 1110
CURVE = 0  # Unity uses RP curve A


def missing() -> list[str]:
    """Dataset files this module needs but cannot read."""
    try:
        relative = str(PATH.relative_to(ROOT))
    except ValueError:
        relative = str(PATH)
    return [] if PATH.is_file() else [relative]


def _load() -> dict[int, dict]:
    """item id -> (name, slot, category, bundle index, Rank 15 augment lines)."""
    absent = missing()
    if absent:
        log.warning("Unity augment dataset missing: %s; no Unity piece can be augmented",
                    ", ".join(absent))
        return {}
    try:
        payload = json.loads(PATH.read_text())
    except (OSError, ValueError):
        log.warning("Unity augment dataset unreadable: %s", PATH.name)
        return {}
    items: dict[int, dict] = {}
    for entry in payload.get("items", []):
        try:
            item_id = int(entry["item_id"])
            bundle = int(entry["bundle"])
        except (KeyError, TypeError, ValueError):
            continue
        items[item_id] = {
            "name": str(entry.get("name") or ""),
            "slot": str(entry.get("slot") or ""),
            "category": str(entry.get("category") or ""),
            "bundle": bundle,
            "augments": [str(row) for row in entry.get("augments") or []],
        }
    return items


ITEMS = _load()


def get(item_id: int) -> dict | None:
    """The Unity entry for an item id, or None."""
    return ITEMS.get(int(item_id))


def find(name: str) -> dict | None:
    """The Unity entry whose name contains *name* (case-insensitive), or None."""
    want = str(name or "").strip().casefold()
    if not want:
        return None
    for item_id, entry in ITEMS.items():
        if want in str(entry["name"]).casefold():
            return dict(entry, item_id=int(item_id))
    return None


def index_for(item_id: int) -> int | None:
    entry = ITEMS.get(int(item_id))
    return int(entry["bundle"]) if entry else None


def encode(item_id: int | None = None, index: int | None = None) -> bytes:
    """A 24-byte Rank 15 bundle block for a Unity item (or an explicit index)."""
    if index is None:
        index = index_for(int(item_id)) if item_id is not None else None
        if index is None:
            raise ValueError("no Unity augment bundle for item %r" % (item_id,))
    return augments.bundle(PATH_LETTER, RANK, TIER, int(index))


def describe(extra: bytes | None) -> str:
    return augments.describe(extra)
