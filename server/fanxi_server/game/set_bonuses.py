"""The tiered bonuses modern iLvl 119 +1 armor sets grant as pieces are worn.

Retail's Escha/Ru'Aun and Zi'Tah abjuration sets only print ``Set: ...`` on each piece;
the actual scaling is on the set page, not in the client item row.  The shared
``data/armor_set_bonuses.json`` table is the one source of truth for both the server and
the launcher's Set totals.

A set counts only its own +1 piece ids, and a tier applies when at least that many
distinct pieces are equipped; the highest reached tier wins.  The stats are ordinary
modifier ids, so the combat path, the live stat sheet and the passive ticks all read
them through ``equipped_mods``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from . import modifiers as mod

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "armor_set_bonuses.json"

# Shared stat key -> (modifier id, item_mods value per displayed point).  Critical hit
# rate and damage taken are stored in hundredths; the rest are already in their engine
# units.  Keep this table in step with the launcher's labels in lib/setbonuses.ts.
MODIFIERS: dict[str, tuple[int, int]] = {
    "critical hit rate": (mod.CRIT_HIT_RATE, 100),
    "magic atk. bonus": (mod.MATT, 1),
    "blood pact damage": (mod.BLOOD_PACT_DAMAGE, 1),
    "double attack": (mod.DOUBLE_ATTACK, 1),
    "accuracy": (mod.ACC, 1),
    "weapon skill damage": (mod.WSD_ALL_HITS, 1),
    "martial arts": (mod.MARTIAL_ARTS, 1),
    "attack": (mod.ATT, 1),
    "damage taken": (mod.DMG, 100),
    "cure potency ii": (mod.CURE_POTENCY_II, 1),
}


@dataclass(frozen=True)
class SetBonus:
    """One set's reached tier: the pieces worn, its modifiers, and a display label."""

    name: str
    pieces: int
    mods: tuple[tuple[int, int], ...]

    @property
    def label(self) -> str:
        return f"{self.name} ({self.pieces} pieces)"


@dataclass(frozen=True)
class SetTier:
    pieces: int
    mods: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ArmorSet:
    name: str
    piece_ids: frozenset[int]
    tiers: tuple[SetTier, ...]


@lru_cache(maxsize=1)
def sets() -> tuple[ArmorSet, ...]:
    """The parsed dataset, or an empty tuple when it is missing or malformed."""
    try:
        document = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        out = []
        for entry in document.get("sets", ()):
            piece_ids = frozenset(int(piece["id"]) for piece in entry.get("pieces", ()))
            tiers = tuple(
                SetTier(
                    pieces=int(tier["pieces"]),
                    mods=tuple((str(key), int(value))
                               for key, value in (tier.get("mods") or {}).items()),
                )
                for tier in entry.get("tiers", ())
            )
            if piece_ids and tiers:
                out.append(ArmorSet(str(entry["name"]), piece_ids, tiers))
        return tuple(out)
    except (OSError, ValueError, KeyError, TypeError):
        return ()


def for_item_ids(item_ids: Iterable[int]) -> list[SetBonus]:
    """The highest reached bonus for every set represented in *item_ids*."""
    worn = {int(item_id) for item_id in item_ids}
    out: list[SetBonus] = []
    for armor_set in sets():
        count = len(worn & armor_set.piece_ids)
        if count < 2:
            continue
        tier = next((tier for tier in reversed(armor_set.tiers)
                     if count >= tier.pieces), None)
        if tier is None:
            continue
        mods = tuple((MODIFIERS[key][0], value * MODIFIERS[key][1])
                     for key, value in tier.mods if key in MODIFIERS)
        if mods:
            out.append(SetBonus(armor_set.name, count, mods))
    return out


def for_character(db, character_id: int) -> list[SetBonus]:
    """The set bonuses on one character's equipped pieces."""
    rows = db.all(
        "SELECT item_id FROM char_equip WHERE character_id = ?", (int(character_id),))
    return for_item_ids(int(row["item_id"]) for row in rows)
