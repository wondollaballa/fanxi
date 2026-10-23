"""Skill ids, per-job ranks and the retail caps each rank reaches at every level.

The table is LandSandBoat's skills.yaml (skill ranks per job, and the cap per rank per level,
referenced from ffo.jp), converted to data/skills.json so the server and its tests need no YAML
parser.  Reading it means a Ninja no longer shows Great Sword 424 just because 424 is the A+ cap
-- every skill gets the value its own job rank earns.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("fanxi.skills")

# The level 99 A+ cap: what a skill reaches when the table cannot say better.
SKILL_CAP = 424

# Skill ids the client's 0x062 block actually has names for.  Ids 13-21 and 46-47 are
# gaps in its table; filling those made the skills menu show blank rows carrying 424.
SKILL_IDS = (
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,          # hand-to-hand .. staff
    25, 26, 27,                                       # archery, marksmanship, throwing
    28, 29, 30, 31,                                   # guard, evasion, shield, parry
    32, 33, 34, 35, 36, 37, 38, 39,                   # divine .. ninjutsu
    40, 41, 42, 43, 44, 45,                           # singing .. handbell
)

# Skill id -> key used by the rank table.
SKILL_KEYS = {
    1: "hand_to_hand", 2: "dagger", 3: "sword", 4: "great_sword", 5: "axe",
    6: "great_axe", 7: "scythe", 8: "polearm", 9: "katana", 10: "great_katana",
    11: "club", 12: "staff", 25: "archery", 26: "marksmanship", 27: "throwing",
    28: "guard", 29: "evasion", 30: "shield", 31: "parry",
    32: "divine_magic", 33: "healing_magic", 34: "enhancing_magic",
    35: "enfeebling_magic", 36: "elemental_magic", 37: "dark_magic",
    38: "summoning_magic", 39: "ninjutsu", 40: "singing", 41: "string_instrument",
    42: "wind_instrument", 43: "blue_magic", 44: "geomancy", 45: "handbell",
}

# Job ids as the client numbers them.
JOB_KEYS = {
    1: "war", 2: "mnk", 3: "whm", 4: "blm", 5: "rdm", 6: "thf", 7: "pld", 8: "drk",
    9: "bst", 10: "brd", 11: "rng", 12: "sam", 13: "nin", 14: "drg", 15: "smn",
    16: "blu", 17: "cor", 18: "pup", 19: "dnc", 20: "sch", 21: "geo", 22: "run",
}

_DATA = Path(__file__).resolve().parents[3] / "data" / "skills.json"


@lru_cache(maxsize=1)
def _table():
    """(ranks, caps) from data/skills.json, or (None, None) when it is unavailable."""
    try:
        doc = json.loads(_DATA.read_text(encoding="utf-8"))["skills"]
        ranks = doc["ranks"]
        caps = {int(level): {str(rank): int(value) for rank, value in row.items()}
                for level, row in doc["caps"].items()}
        return ranks, caps
    except Exception as exc:  # missing file or bad JSON: fall back to a flat A+ cap
        log.warning("skill table unavailable (%s); every skill uses the A+ cap", exc)
        return None, None


def rank_for(skill_id: int, job_id: int) -> str | None:
    ranks, _caps = _table()
    if not ranks:
        return None
    key = SKILL_KEYS.get(int(skill_id))
    job = JOB_KEYS.get(int(job_id))
    if not key or not job:
        return None
    return ranks.get(key, {}).get(job)


def cap_for(skill_id: int, job_id: int, level: int) -> int | None:
    rank = rank_for(skill_id, job_id)
    _ranks, caps = _table()
    if rank is None or not caps:
        return None
    return caps.get(max(1, min(99, int(level))), {}).get(rank)


def rank_cap(rank: str, level: int) -> int:
    """The skill value a rank reaches at a level, ignoring which job holds it.

    Monsters use this: their attack and accuracy come from a skill rank at their own
    level rather than from a job.  Past 99 every skill keeps growing at the item-level
    rate of 5 per level, which is the same slope `item_weapon.ilvl_skill` uses.
    """
    _ranks, caps = _table()
    level = max(1, int(level))
    if not caps:
        return SKILL_CAP + max(0, level - 99) * 5
    top = max(caps)
    value = caps.get(min(level, top), {}).get(rank)
    if value is None:
        return SKILL_CAP + max(0, level - 99) * 5
    return int(value) + max(0, level - top) * 5


def caps_for(main_job: int, main_level: int, sub_job: int, sub_level: int) -> dict[int, int]:
    """Skill id -> value for the current job pair.

    A skill is the better of the main job at its level and the sub job at its level, the
    way retail lets a subjob carry a skill you are better at on the other job.
    """
    out: dict[int, int] = {}
    for skill_id in SKILL_IDS:
        best = cap_for(skill_id, main_job, main_level) or 0
        sub = cap_for(skill_id, sub_job, sub_level) or 0
        if sub > best:
            best = sub
        if best:
            out[skill_id] = best
    return out
