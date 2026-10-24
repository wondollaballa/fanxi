"""Per-weapon-skill damage data: fTP anchors, WSC and the hit list.

Retail does not resolve every weapon skill with one fTP curve.  Each skill has its own
three fTP anchors (1000/2000/3000 TP), its own secondary-attribute modifiers (WSC),
and its own hit count.  ``data/weapon_skills.json`` is LandSandBoat's
``scripts/actions/weaponskills/*.lua`` table converted to JSON; the numbers are the
Adoulin-era branch (``USE_ADOULIN_WEAPON_SKILL_CHANGES``), which is what a level 119
character uses.

The old engine used one generic ``1.5 + 1.5 * tp / 3000`` curve and no WSC for every
skill.  That is why a Blade: Metsu did about twice an auto-attack instead of the
five-times-damage fTP the skill actually has.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import weapon_skill_effects

log = logging.getLogger("fanxi.weapon_skills")

_DATA = Path(__file__).resolve().parents[3] / "data" / "weapon_skills.json"
_SC_DATA = Path(__file__).resolve().parents[3] / "data" / "skillchains.json"

# The stats WSC can use, in the order the table names them.
WSC_STATS = ("str", "dex", "vit", "agi", "int", "mnd", "chr")


@dataclass(frozen=True)
class WeaponSkillData:
    """The damage half of one weapon skill, apart from its extra effects."""

    id: int
    name: str
    skill: int = 0
    # fTP at 1000 / 2000 / 3000 TP.  Empty means the skill has no physical damage.
    ftp: tuple[float, ...] = ()
    # Main-hand hits.  Retail rolls each one separately.
    hits: int = 1
    # The skill's secondary attribute modifiers: stat -> fraction.
    wsc: dict[str, float] = field(default_factory=dict)
    # True when fTP applies to every hit (``multiHitfTP`` in LandSandBoat).
    multi_hit_ftp: bool = False
    # Extra critical-hit rate by TP (a fraction added to the normal rate).
    crit_varies: tuple[float, ...] = ()
    # Attack multiplier by TP (LandSandBoat's ``atkVaries``).
    attack_varies: tuple[float, ...] = ()
    # Fraction of the target's Defense ignored by TP (``ignoredDefense``).
    ignored_defense: tuple[float, ...] = ()
    # A magic-damage skill; the physical path is still used until that path exists.
    magic: bool = False
    # A hybrid physical/magic skill (its magic component is not modelled yet).
    hybrid: bool = False
    # The three resonance properties, in LandSandBoat's order:
    # (primary, secondary, tertiary), each an SC_* id (0 = none).
    sc: tuple[int, int, int] = (0, 0, 0)

    @property
    def primary_sc(self) -> int:
        return int(self.sc[0])

    def ftp_at(self, tp: int) -> float:
        """Interpolated fTP at ``tp``; 1000 TP is the floor and 3000 the ceiling."""
        if not self.ftp:
            return 0.0
        return weapon_skill_effects.at_tp(int(tp), self.ftp)

    def crit_at(self, tp: int) -> float:
        return weapon_skill_effects.at_tp(int(tp), self.crit_varies) if self.crit_varies else 0.0

    def attack_at(self, tp: int) -> float:
        if not self.attack_varies:
            return 1.0
        return weapon_skill_effects.at_tp(int(tp), self.attack_varies)

    def ignored_defense_at(self, tp: int) -> float:
        if not self.ignored_defense:
            return 0.0
        return max(0.0, min(1.0, weapon_skill_effects.at_tp(int(tp), self.ignored_defense)))

    def wsc_for(self, attributes: dict[str, int]) -> int:
        """The secondary-attribute bonus for these stats.

        LandSandBoat floors each stat's contribution and then sums them.  Its
        ``calculateAlpha`` is 1.0 with the Adoulin weapon-skill changes (there is no
        level-based alpha any more), so there is no second multiplier here.
        """
        total = 0
        for stat in WSC_STATS:
            coefficient = float(self.wsc.get(stat, 0.0))
            if coefficient:
                total += int(int(attributes.get(stat, 0)) * coefficient)
        return total


@lru_cache(maxsize=1)
def _skillchain_table() -> dict[int, tuple[int, int, int]]:
    """Weapon-skill id -> (primary, secondary, tertiary) resonance ids."""
    try:
        document = json.loads(_SC_DATA.read_text(encoding="utf-8"))["weapon_skills"]
        return {int(key): tuple(int(value) for value in row[:3])
                for key, row in document.items() if len(row) >= 3}
    except Exception as exc:
        log.warning("skillchain property table unavailable (%s)", exc)
        return {}


@lru_cache(maxsize=1)
def _table() -> dict[int, WeaponSkillData]:
    try:
        document = json.loads(_DATA.read_text(encoding="utf-8"))["weapon_skills"]
    except Exception as exc:
        log.warning("weapon skill table unavailable (%s); using the generic fTP curve", exc)
        return {}
    properties = _skillchain_table()
    table: dict[int, WeaponSkillData] = {}
    for key, row in document.items():
        try:
            table[int(key)] = WeaponSkillData(
                id=int(key),
                name=str(row.get("name", "")),
                skill=int(row.get("skill", 0)),
                ftp=tuple(float(value) for value in row.get("ftp", ())),
                hits=max(1, int(row.get("hits", 1) or 1)),
                wsc={stat: float(value) for stat, value in (row.get("wsc") or {}).items()},
                multi_hit_ftp=bool(row.get("multi_hit_ftp", False)),
                crit_varies=tuple(float(value) for value in row.get("crit_varies", ())),
                attack_varies=tuple(float(value) for value in row.get("attack_varies", ())),
                ignored_defense=tuple(float(value) for value in row.get("ignored_defense", ())),
                magic=bool(row.get("magic", False)),
                hybrid=bool(row.get("hybrid", False)),
                sc=properties.get(int(key), (0, 0, 0)),
            )
        except (TypeError, ValueError) as exc:
            log.warning("weapon skill row %s is unusable: %s", key, exc)
    return table


def for_id(ws_id: int) -> WeaponSkillData | None:
    """The data for one weapon skill id, or None when the table has no row."""
    return _table().get(int(ws_id))


def names() -> dict[str, WeaponSkillData]:
    """Lookup by lower-case skill name, for tests and tools."""
    return {row.name.lower(): row for row in _table().values()}
