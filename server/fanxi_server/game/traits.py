"""Job traits: the passive job/level bonuses a character carries.

Retail job traits are not status effects.  They are permanent modifiers earned at a
job level, and a character receives the highest rank of each trait from their main job
and their support job.  The two jobs do not stack the same trait: a Warrior 30 with a
Dragoon 30 support job gets Attack Bonus I once, not twice.

The data in :mod:`fanxi_server.game.traits_data` is the game's own trait table.  The
ids are the client's job-trait ids, which is what the fourth block of the 0x0AC
command packet advertises.  Values are modifier ids from
:mod:`fanxi_server.game.modifiers`; this module turns them into the same dict the
equipment loader produces, so the stat sheet and the zone tick read trait bonuses and
gear bonuses through one path.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import modifiers as mod
from .traits_data import ROWS

# The two traits that restore something on a timer.  Their modifiers are REFRESH and
# REGEN, and both tick once every three seconds in retail.
AUTO_REGEN = 9
AUTO_REFRESH = 10
TICK_SECONDS = 3.0

# Human labels for the !traits command.  Unknown modifier ids still print their id so a
# missing label never hides a trait row.
MOD_LABELS = {
    mod.DEF: "Defense",
    mod.ATT: "Attack",
    24: "Ranged Attack",
    mod.ACC: "Accuracy",
    26: "Ranged Accuracy",
    28: "Magic Attack",
    29: "Magic Defense",
    mod.EVA: "Evasion",
    mod.STORETP: "Store TP",
    mod.FASTCAST: "Fast Cast",
    mod.DUAL_WIELD: "Dual Wield",
    mod.MARTIAL_ARTS: "Martial Arts",
    71: "MP while healing",     # the base resting recovery the trait raises
    mod.CLEAR_MIND: "Clear Mind",
    mod.REFRESH: "Refresh",
    mod.REGEN: "Regen",
    mod.MAX_HP_BOOST: "Max HP",
    mod.MAX_MP_BOOST: "Max MP",
    mod.CRIT_DMG_INCREASE: "Critical damage",
    mod.CRIT_DEF_BONUS: "Critical defense",
    mod.DAMAGE_LIMIT: "Damage limit",
    174: "Skillchain Bonus",
    271: "Tandem Strike",
    272: "Tandem Blow",
    274: "Magic Burst Bonus",
    288: "Double Attack",
    289: "Subtle Blow",
    291: "Counter",
    292: "Kick Attacks",
    296: "Conserve MP",
    302: "Triple Attack",
    303: "Treasure Hunter",
    305: "Recycle",
    306: "Zanshin",
    359: "Rapid Shot",
    485: "Shield Mastery",
    486: "Tactical Parry",
    840: "WS Damage",
    897: "Gilfinder",
    898: "Smite",
    899: "Tactical Guard",
    901: "Elemental Celerity",
    902: "Occult Acumen",
    903: "Fencer",
    904: "Fencer",
    905: "Shield Defense",
    906: "Desperate Blows",
    907: "Stalwart Soul",
    910: "Divine Benison",
    911: "Daken",
    913: "Blood Boon",
    944: "Conserve TP",
    959: "Cardinal Chant",
    963: "Inquartata",
    964: "Ranged Critical Damage",
    970: "Curative Recantation",
    971: "Primeval Zeal",
    986: "Strafe",
    1082: "Shield Barrier",
}

# Killer and resist traits use one modifier id per family; name them so !traits reads
# like the client's trait menu instead of printing raw modifier numbers.
MOD_LABELS.update({
    224: "Vermin Killer", 225: "Bird Killer", 226: "Amorph Killer",
    227: "Lizard Killer", 228: "Aquan Killer", 229: "Plantoid Killer",
    230: "Beast Killer", 231: "Undead Killer", 232: "Arcana Killer",
    233: "Dragon Killer", 234: "Demon Killer",
    240: "Resist Sleep", 241: "Resist Poison", 242: "Resist Paralyze",
    243: "Resist Blind", 244: "Resist Silence", 245: "Resist Virus",
    246: "Resist Petrify", 247: "Resist Bind", 248: "Resist Curse",
    249: "Resist Gravity", 250: "Resist Slow", 251: "Resist Stun",
    252: "Resist Charm", 253: "Resist Amnesia",
})

_NAME_WORDS = {"hp": "HP", "mp": "MP", "tp": "TP", "ws": "WS",
               "mob": "Mob", "atk.": "Atk.", "def.": "Def.", "mag.": "Mag."}


def _pretty(name: str) -> str:
    """Title-case a trait name while keeping the game's abbreviations uppercase."""
    return " ".join(_NAME_WORDS.get(word, word.capitalize()) for word in name.split())


@dataclass(frozen=True)
class Trait:
    """One active trait and the modifiers its highest reached rank grants."""

    id: int
    name: str
    rank: int
    level: int
    mods: tuple[tuple[int, int], ...] = ()

    def describe(self) -> str:
        """The name plus its tier and effects, for ``!traits``."""
        parts = ["%s+%d" % (MOD_LABELS.get(mod_id, "mod %d" % mod_id), value)
                 for mod_id, value in self.mods]
        detail = ", ".join(parts) if parts else "no direct stat change"
        return "%s (rank %d, level %d): %s" % (
            _pretty(self.name), self.rank, self.level, detail)


def _index() -> dict[int, dict[int, list[tuple]]]:
    """job -> trait id -> the rows for that trait, sorted by level/rank."""
    index: dict[int, dict[int, list[tuple]]] = {}
    for row in ROWS:
        _trait_id, _name, job, _level, _rank, _modifier, _value = row
        index.setdefault(job, {}).setdefault(_trait_id, []).append(row)
    for traits in index.values():
        for rows in traits.values():
            rows.sort(key=lambda row: (row[3], row[4]))
    return index


_INDEX = _index()


def _rank_for(rows: list[tuple], level: int) -> list[tuple] | None:
    """The rows of the highest rank at or below *level*, or None if none is reached."""
    eligible = [row for row in rows if row[3] <= level]
    if not eligible:
        return None
    rank = max(row[4] for row in eligible)
    return [row for row in eligible if row[4] == rank]


def active(main_job: int, main_level: int, sub_job: int = 0,
           sub_level: int = 0) -> list[Trait]:
    """Every trait the character has, one entry per trait id.

    A support job contributes at its own (already halved) level.  When both jobs have
    the same trait, the higher rank wins and an equal rank is only counted once.
    """
    chosen: dict[int, list[tuple]] = {}
    for job, level in ((main_job, main_level), (sub_job, sub_level)):
        try:
            job, level = int(job or 0), int(level or 0)
        except (TypeError, ValueError):
            continue
        if job <= 0 or level <= 0:
            continue
        for trait_id, rows in _INDEX.get(job, {}).items():
            selected = _rank_for(rows, level)
            if selected is None:
                continue
            rank = selected[0][4]
            current = chosen.get(trait_id)
            if current is None or rank > current[0][4]:
                chosen[trait_id] = selected
            # Same trait at the same or a lower rank from the other job: no stack.

    out: list[Trait] = []
    for trait_id, rows in chosen.items():
        mods: dict[int, int] = {}
        for row in rows:
            mod_id, value = int(row[5]), int(row[6])
            if mod_id:
                mods[mod_id] = mods.get(mod_id, 0) + value
        out.append(Trait(id=trait_id, name=str(rows[0][1]), rank=int(rows[0][4]),
                         level=int(rows[0][3]), mods=tuple(sorted(mods.items()))))
    out.sort(key=lambda trait: trait.id)
    return out


def modifiers_for(main_job: int, main_level: int, sub_job: int = 0,
                  sub_level: int = 0) -> dict[int, int]:
    """The summed trait modifiers, ready to merge with gear modifiers."""
    mods: dict[int, int] = {}
    for trait in active(main_job, main_level, sub_job, sub_level):
        for mod_id, value in trait.mods:
            mods[mod_id] = mods.get(mod_id, 0) + value
    return mods


def ids_for(main_job: int, main_level: int, sub_job: int = 0,
            sub_level: int = 0) -> list[int]:
    """The client trait ids to set in 0x0AC's fourth block."""
    return [trait.id for trait in active(main_job, main_level, sub_job, sub_level)]
