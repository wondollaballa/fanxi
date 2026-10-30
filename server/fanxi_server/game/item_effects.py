"""Item modifiers that depend on character state instead of a row in ``item_mods``.

Almost every item's stats are fixed data.  The Hoxne Earring is the exception in this
checkout: its help text reads ``Mastery Rank: All BP -30 to +30`` and it has no
``item_mods`` rows at all, so its seven attribute bonuses have to be worked out from the
character's Mastery Rank whenever the outfit is read.

The rank table is the one on the item's BG Wiki page
(https://www.bg-wiki.com/ffxi/Hoxne_Earring): ranks 1-3 are the penalty side
(-30, -20, -10), rank 4 is zero, and every rank above that adds five up to +30 at rank 10.
A character whose stored byte is still 0 (the column default before the Data page sets a
rank) uses the item's -30 floor; retail's Mastery Rank itself starts at rank 1.
"""
from __future__ import annotations

from . import modifiers as mod

HOXNE_EARRING = 26120

#: The seven attributes "All BP" means.  HP, MP, Attack and Accuracy are not part of it;
#: they move only through the attributes' own formulas.
ALL_STATS = (mod.STR, mod.DEX, mod.VIT, mod.AGI, mod.INT, mod.MND, mod.CHR)

#: Mastery Rank -> the earring's bonus to each of the seven attributes.
HOXNE_ALL_STATS_BY_RANK = {
    1: -30,
    2: -20,
    3: -10,
    4: 0,
    5: 5,
    6: 10,
    7: 15,
    8: 20,
    9: 25,
    10: 30,
}
HOXNE_MIN_RANK = min(HOXNE_ALL_STATS_BY_RANK)
HOXNE_MAX_RANK = max(HOXNE_ALL_STATS_BY_RANK)
HOXNE_FLOOR = HOXNE_ALL_STATS_BY_RANK[HOXNE_MIN_RANK]


def hoxne_all_stats(mastery_rank: int) -> int:
    """The earring's per-attribute value at *mastery_rank*, clamped to the item's range."""
    try:
        rank = int(mastery_rank)
    except (TypeError, ValueError):
        rank = HOXNE_MIN_RANK
    if rank <= HOXNE_MIN_RANK:
        return HOXNE_FLOOR
    if rank >= HOXNE_MAX_RANK:
        return HOXNE_ALL_STATS_BY_RANK[HOXNE_MAX_RANK]
    return HOXNE_ALL_STATS_BY_RANK[rank]


def item_mods(item_id: int, mastery_rank: int) -> dict[int, int]:
    """The modifiers one equipped copy of *item_id* adds for this character.

    Only the Hoxne Earring needs a character-state lookup today.  The function returns an
    empty dict for every other item and for rank 4, where the earring's bonus is zero.
    """
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return {}
    if item_id != HOXNE_EARRING:
        return {}
    value = hoxne_all_stats(mastery_rank)
    if value == 0:
        return {}
    return {mod_id: value for mod_id in ALL_STATS}


def add_item_mods(target: dict[int, int], item_id: int, mastery_rank: int) -> None:
    """Merge one equipped copy's dynamic modifiers into *target*."""
    for mod_id, value in item_mods(item_id, mastery_rank).items():
        target[int(mod_id)] = target.get(int(mod_id), 0) + int(value)
