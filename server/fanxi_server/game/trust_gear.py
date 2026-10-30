"""Trust loadouts, and the stats a Trust shares with the player who called it.

Two things live here.

The **loadout** is factual: ``trust_gear`` names the weapons a Trust is designed with
(Sylvie (UC) carries Idris, Joachim the Prime Loughnashade).  Their ``item_mods``
rows are what the AI reads -- the song slots and Song+ lines for a Bard, and Idris's
Geomancy +10, which LandSandBoat scripts rather than storing as a modifier and so is
added here by item id.

The **gear share** is Fanxi's own rule: a Trust's sheet comes from the level curve in
``stats.build_monster``, and a well-geared owner lends it part of what that gear gives
the owner.  The share is 50% of the owner's gear modifiers at item level 119 and scales
down with the owner's average item level, so a Master in sparks gear gets a Trust that
fights like one, and an endgame set lifts the Trust with it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import geomancy, modifiers as mod

#: The item level a full endgame set sits at.  The share is full at this rating.
ENDGAME_ITEM_LEVEL = 119
#: How much of the owner's gear a Trust inherits at that rating.
GEAR_SHARE_PERCENT = 50
#: The modifiers a Trust shares.  Attack, accuracy and the attributes move its swings and
#: its spells; HP/MP move its bars; Defense and Evasion are kept for a future pet model.
SHARED_MODS = (
    mod.ATT, mod.ACC, mod.HP, mod.MP, mod.DEF, mod.EVA,
    mod.STR, mod.DEX, mod.VIT, mod.AGI, mod.INT, mod.MND, mod.CHR,
)
#: Idris's "Geomancy +10" (LandSandBoat scripts it; there is no item_mods row).
IDRIS_ITEM_IDS = frozenset({21070, 21080})


@dataclass(frozen=True)
class Loadout:
    """The weapons one Trust carries and what they grant."""

    items: tuple[int, ...] = ()
    mods: dict[int, int] = field(default_factory=dict)
    geomancy_plus: int = 0

    @property
    def idris(self) -> bool:
        return self.geomancy_plus >= geomancy.IDRIS_GEOMANCY_PLUS

    @property
    def song_slots(self) -> int:
        """Extra songs the loadout's instrument adds (Maximum Songs +N: Daurdabla or
        Loughnashade, two apiece)."""
        return int(self.mods.get(mod.MAXIMUM_SONGS_BONUS, 0))


def loadout(service, trust_spell_id: int) -> Loadout:
    """The weapons a Trust carries, and every modifier they grant."""
    try:
        items = tuple(int(item) for item in service.trust_gear(int(trust_spell_id)))
    except Exception:                                  # an un-migrated database
        items = ()
    mods: dict[int, int] = {}
    for item_id in items:
        try:
            for mod_id, value in service.item_mods(item_id).items():
                mods[int(mod_id)] = mods.get(int(mod_id), 0) + int(value)
        except Exception:
            continue
    plus = geomancy.IDRIS_GEOMANCY_PLUS if IDRIS_ITEM_IDS.intersection(items) else 0
    return Loadout(items=items, mods=mods, geomancy_plus=plus)


def share(service, character_id: int) -> dict[int, int]:
    """The owner's gear modifiers a Trust inherits, scaled by the owner's gear rating.

    ``equipped_mods`` already counts augments, so a Rank 30 set lends the Trust more than
    the same pieces un-augmented.  An owner wearing nothing with an item level shares
    nothing.
    """
    rating = int(service.equipped_gear_rating(int(character_id)) or 0)
    percent = GEAR_SHARE_PERCENT * max(0, min(ENDGAME_ITEM_LEVEL, rating)) // ENDGAME_ITEM_LEVEL
    if percent <= 0:
        return {}
    gear = service.equipped_mods(int(character_id))
    return {mod_id: int(int(gear.get(mod_id, 0)) * percent // 100)
            for mod_id in SHARED_MODS}
