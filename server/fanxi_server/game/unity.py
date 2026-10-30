"""Unity Wanted iLvl 119+ gear: single-path Rank 15 augments.

A Unity +1 item is augmented at a Unity NPC with Lustreless items.  The client stores
the result in the same 24-byte ``AugmentBundle`` block Odyssey uses, but with Rank 15,
max-rank tier 0 (the 15-rank unlock) and one path.  The bundle index is the client's own
augment-table row for the item; the rows below decode to the Rank 15 lines in
``ITEMS`` (the values the GearSwap libraries carry, and the rows on each item's BG Wiki
page).

The first five entries are the Unity pieces the shared GearSwap ``local unity``
table defines: four accessories Ninja wears and the ``Loess Barbuta +1``.  The
rest of the Unity accessory catalogue follows, including the four belts, plus
the armour and grip pieces such as ``Blistering Sallet +1`` and ``Rigorous Grip
+1``, so the Data page's RP card lists every Unity piece in the bags as soon as
it is purchased.  The block is what the client turns into tooltip text, and
``augment_stats`` also reads the Rank 15 rows into modifiers.
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
    # Unity armour is augmented through the same Rank 15 Lustreless path as
    # the accessories; Blistering Sallet +1 used to be absent because this
    # registry only carried accessories.  Bundle 359 is the client row whose
    # rank-15 values are the item page's Accuracy/M.Acc.+45, Crit.+10% and
    # STR/DEX+25.
    25602: {
        "name": "Blistering Sallet +1",
        "slot": "head",
        "bundle": 359,
        "augments": [
            "Accuracy/Magic Accuracy +45",
            "Critical Hit Rate +10%",
            "STR/DEX +25",
        ],
    },
    # Unity grips are weapons, but they take the same Rank 15 Lustreless path.
    # Bundle 327 is the client row whose rank-15 values are Attack+30 / STR+15.
    21419: {
        "name": "Rigorous Grip +1",
        "slot": "sub",
        "bundle": 327,
        "augments": ["Attack +30", "STR +15"],
    },
    # The rest of the Unity accessories, so every Unity piece in the bags
    # reaches the Data page's RP card.  Each bundle is the client
    # augment-table row whose Rank 15 values match the item's BG Wiki row.
    28430: {
        "name": "Acuity Belt +1",
        "slot": "waist",
        "bundle": 295,
        "augments": ["Magic Accuracy +15", "INT +10"],
    },
    27561: {
        "name": "Apeile Ring +1",
        "slot": "ring",
        "bundle": 310,
        "augments": ["DEF +20", "Magic Defense Bonus +5"],
    },
    28487: {
        "name": "Arete del Luna +1",
        "slot": "ear",
        "bundle": 302,
        "augments": ["Resist Sleep +15", "Resist Charm +15"],
    },
    27620: {
        "name": "Aurist's Cape +1",
        "slot": "back",
        "bundle": 363,
        "augments": ["Accuracy/Magic Accuracy +25", "INT/MND +25"],
    },
    27518: {
        "name": "Bathy Choker +1",
        "slot": "neck",
        "bundle": 350,
        "augments": ["Evasion +15", "Counter +10"],
    },
    10771: {
        "name": "Cacoethic Ring +1",
        "slot": "ring",
        "bundle": 358,
        "augments": ["DEX +10", "AGI +10"],
    },
    28353: {
        "name": "Canto Necklace +1",
        "slot": "neck",
        "bundle": 296,
        "augments": ["Magic Accuracy +15", "CHR +10"],
    },
    27543: {
        "name": "Domin. Earring +1",
        "slot": "ear",
        "bundle": 374,
        "augments": ["Accuracy +10", "DEX +6"],
    },
    27610: {
        "name": "Fi Follet Cape +1",
        "slot": "back",
        "bundle": 360,
        "augments": ["Fast Cast +10%", "Spell Interruption Rate -5%"],
    },
    27602: {
        "name": "Ground. Mantle +1",
        "slot": "back",
        "bundle": 320,
        "augments": ["Accuracy +15", "DEX +10"],
    },
    28491: {
        "name": "Handler's Earring +1",
        "slot": "ear",
        "bundle": 298,
        "augments": ["Pet: Accuracy/Magic Accuracy +15", "Accuracy +10"],
    },
    28413: {
        "name": "Kentarch Belt +1",
        "slot": "waist",
        "bundle": 355,
        "augments": ["STR+10", "DEX+10"],
    },
    26002: {
        "name": "Loricate Torque +1",
        "slot": "neck",
        "bundle": 372,
        "augments": ["DEF +45", "Spell Interruption Rate -5%"],
    },
    28482: {
        "name": "Lugra Earring +1",
        "slot": "ear",
        "bundle": 312,
        "augments": ["DEF +20", "STR/DEX/VIT/INT +8"],
    },
    27559: {
        "name": "Mephitas's Ring +1",
        "slot": "ring",
        "bundle": 337,
        "augments": ["Conserve MP +15", "INT +5"],
    },
    27563: {
        "name": "Metamorph Ring +1",
        "slot": "ring",
        "bundle": 306,
        "augments": ["Magic Accuracy +10", "INT/MND/CHR +10"],
    },
    28485: {
        "name": "Nourishing Earring +1",
        "slot": "ear",
        "bundle": 290,
        "augments": ["Resist Silence +15", "Spell Interruption Rate -5%"],
    },
    28428: {
        "name": "Sailfi Belt +1",
        "slot": "waist",
        "bundle": 292,
        "augments": ["STR +15", "Double Attack +5%"],
    },
    22255: {
        "name": "Seeth. Bomblet +1",
        "slot": "ammo",
        "bundle": 364,
        "augments": ["STR +10", "Haste +5%"],
    },
    28424: {
        "name": "Shinjutsu-no-Obi +1",
        "slot": "waist",
        "bundle": 294,
        "augments": ["Conserve MP +15", "Fast Cast +5%"],
    },
    26022: {
        "name": "Vim Torque +1",
        "slot": "neck",
        "bundle": 383,
        "augments": ["Accuracy +15", "Store TP +10"],
    },
    27505: {
        "name": "Warder's Charm +1",
        "slot": "neck",
        "bundle": 324,
        "augments": ["Skillchain Damage +15%", "Magic Burst Bonus +10%"],
    },
    27533: {
        "name": "Zwazo Earring +1",
        "slot": "ear",
        "bundle": 357,
        "augments": ["HP +45", "Shield Block Rate +3%"],
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
