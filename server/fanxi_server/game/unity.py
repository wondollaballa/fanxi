"""Unity Wanted iLvl 119 +1 gear: single-path Rank 15 augments.

A Unity +1 item is augmented at a Unity NPC with Lustreless items.  The client stores
the result in the same 24-byte ``AugmentBundle`` block Odyssey uses, but with Rank 15,
max-rank tier 0 (the 15-rank unlock) and one path.  The bundle index is the client's own
augment-table row for the item; the rows below decode to the Rank 15 lines in
``ITEMS`` (the values the GearSwap libraries carry, and the rows on each item's BG Wiki
page).

The four accessories are the Unity pieces Ninja wears (``gearswap/NIN.lua``); the
``Loess Barbuta +1`` is the fifth Unity item that library defines.  The block is what the
client turns into tooltip text; the server does not read it back into combat stats yet.
"""

from __future__ import annotations

from . import augments

RANK = 15
TIER = 0  # 0 = the 15-rank unlock
PATH = "A"

# item id -> (name, bundle index, Rank 15 augment lines, jobs that can wear it)
ITEMS = {
    27509: {
        "name": "Unmoving Collar +1",
        "slot": "neck",
        "bundle": 305,
        "augments": ["DEF+30", "HP+200"],
    },
    27549: {
        "name": "Odnowa Earring +1",
        "slot": "ear",
        "bundle": 367,
        "augments": ["DEF+30", "Damage taken-3%"],
    },
    10769: {
        "name": "Gelatinous Ring +1",
        "slot": "ring",
        "bundle": 316,
        "augments": ["VIT+15", "HP+100"],
    },
    21344: {
        "name": "Ghastly Tathlum +1",
        "slot": "ammo",
        "bundle": 343,
        "augments": ["Magic Damage +10", "INT+5"],
    },
    25636: {
        "name": "Loess Barbuta +1",
        "slot": "head",
        "bundle": 376,
        "augments": ["Enmity+10", "Damage taken-10%", "All Attr.+10"],
    },
}


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
    return augments.bundle(PATH, RANK, TIER, int(index))


def describe(extra: bytes | None) -> str:
    return augments.describe(extra)
