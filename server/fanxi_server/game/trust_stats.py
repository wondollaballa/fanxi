"""Retail-like HP and MP for Trust alter egos.

A Trust is a player-shaped NPC, but its stat block is not the player character's:
LandSandBoat gives it the owner's level, half that level as a subjob, and the same
race/job grade tables the player sheet uses.  This module is the one place that
turns those facts into the two bars the party list draws.

The only deliberate departure from the player curve is the MP bonus.  Retail alter
egos are measured at roughly 31% above a player's base racial MP, and many carry
further `MP+%` traits on top.  A 75% bonus puts a level-99 healer or nuker
clearly above an ungeared player of the same race and job without turning every
Trust into an endless caster.
"""
from __future__ import annotations

from . import base_stats

#: Alter egos get this percentage of the player MP curve.
TRUST_MP_PERCENT = 175

#: LandSandBoat player-race species ids -> the client race field (1..8) the base
#: tables use.  Anything else (Moogles, beasts, Ark Angels, ...) falls back to Hume.
SPECIES_RACES = {
    293: 3,   # Elvaan
    294: 8,   # Galka
    295: 1,   # Hume
    296: 7,   # Mithra
    297: 5,   # Tarutaru
}
HUME_RACE = 1


def race_for_species(species: int | str | None) -> int:
    """The base-table race field for one LSB species id."""
    try:
        return SPECIES_RACES.get(int(species), HUME_RACE)
    except (TypeError, ValueError):
        return HUME_RACE


def vitals(race: int, job: int, sub_job: int, level: int) -> tuple[int, int]:
    """(max HP, max MP) for a Trust of this race, job pair and level.

    A Trust's subjob is half its main level, matching LandSandBoat's
    ``CTrustEntity::SetSLevel(floor(masterLevel / 2))``.  The player base tables
    already halve the subjob's contribution, so the two halves do not compound.
    """
    level = max(1, min(99, int(level)))
    sub_job = int(sub_job or 0)
    sub_level = level // 2 if sub_job else 0
    hp = base_stats.base_hp(race, job, level, sub_job, sub_level)
    mp = base_stats.base_mp(race, job, level, sub_job, sub_level)
    return max(1, int(hp)), max(0, int(mp) * TRUST_MP_PERCENT // 100)
