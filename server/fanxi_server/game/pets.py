"""A minimal pet foundation for Beastmaster, Dragoon and Puppetmaster.

The world already knows how to spawn, follow and attack with a Trust entity.  A pet uses
the same entity and movement model with a different spawn flag: it belongs to its owner
and can be told to follow or fight.  The three launchable pets are the ones with a stable
client model in the retail data:

* BST Call Beast -> Tiger familiar
* DRG Call Wyvern -> player wyvern
* PUP Activate -> automaton

Summoner avatars use the same entity and are the next step in ``SUMMONS``.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import job_points


@dataclass(frozen=True)
class PetSpec:
    key: str
    name: str
    model: int
    hp_mult: int = 100
    attack_mult: int = 100
    delay_ms: int = 2400


def _look(model: int) -> bytes:
    """The client's 20-byte NPC look block with just the model set."""
    out = bytearray(20)
    out[2:4] = int(model).to_bytes(2, "little")
    return bytes(out)


SPECS: dict[str, PetSpec] = {
    # Pet_Tiger_Familiar look: 0x00003401 -> model 0x0134.
    "beast": PetSpec("beast", "Tiger", 0x0134, hp_mult=100, attack_mult=100),
    # Pet_Wyvern look: 0x00008E01 -> model 0x018E.
    "wyvern": PetSpec("wyvern", "Wyvern", 0x018E, hp_mult=110, attack_mult=95),
    # Automaton look: 0x0600B907 -> model 0x07B9.
    "automaton": PetSpec("automaton", "Automaton", 0x07B9, hp_mult=105, attack_mult=90),
    # Summoner avatars, from the Pet_* mob pools in the retail data.
    "carbuncle": PetSpec("carbuncle", "Carbuncle", 0x0010, hp_mult=90, attack_mult=90),
    "fenrir": PetSpec("fenrir", "Fenrir", 0x0011, hp_mult=110, attack_mult=110),
    "ifrit": PetSpec("ifrit", "Ifrit", 0x0012, hp_mult=110, attack_mult=115),
    "titan": PetSpec("titan", "Titan", 0x0013, hp_mult=120, attack_mult=105),
    "leviathan": PetSpec("leviathan", "Leviathan", 0x0014, hp_mult=110, attack_mult=105),
    "garuda": PetSpec("garuda", "Garuda", 0x0015, hp_mult=100, attack_mult=110),
    "shiva": PetSpec("shiva", "Shiva", 0x0016, hp_mult=100, attack_mult=110),
    "ramuh": PetSpec("ramuh", "Ramuh", 0x0017, hp_mult=105, attack_mult=110),
    "diabolos": PetSpec("diabolos", "Diabolos", 0x0019, hp_mult=105, attack_mult=115),
    "alexander": PetSpec("alexander", "Alexander", 0x001B, hp_mult=130, attack_mult=85),
    "odin": PetSpec("odin", "Odin", 0x001A, hp_mult=130, attack_mult=95),
    "luopan": PetSpec("luopan", "Luopan", 0x0B28, hp_mult=80, attack_mult=40),
}

SUMMONS: dict[str, str] = {
    "carbuncle": "carbuncle", "fenrir": "fenrir", "ifrit": "ifrit", "titan": "titan",
    "leviathan": "leviathan", "garuda": "garuda", "shiva": "shiva", "ramuh": "ramuh",
    "diabolos": "diabolos", "alexander": "alexander", "odin": "odin",
}


def summon_key(name: str) -> str | None:
    """The pet key for one Summon spell name, or None."""
    return SUMMONS.get(" ".join(str(name or "").casefold().split()))


def spec(key: str) -> PetSpec | None:
    return SPECS.get(str(key))


def look(spec: PetSpec) -> bytes:
    return _look(spec.model)


def pet_stats(owner_job: int, level: int, spec: PetSpec) -> dict:
    """The pet's HP/attack/accuracy/delay after the owner's job-point pet rows.

    Only the rows with a direct numeric meaning are used.  Pet-command systems (Sic,
    Ready, Repair, ...) are separate behaviours and stay in the ability handler.
    """
    level = max(1, int(level))
    hp = max(20, level * 30 + 200) * int(spec.hp_mult) // 100
    attack = max(1, level * 3 + 30)
    accuracy = level * 2 + 20
    damage = 100
    if int(owner_job) == 9:  # Beastmaster
        accuracy += job_points.category_total(9, "Pet Accuracy Bonus")
        familiar = job_points.category_total(9, "Familiar Effect")
        damage += familiar + job_points.category_total(9, "Ready Effect")
        accuracy += familiar
        hp += familiar
    elif int(owner_job) == 14:  # Dragoon
        hp += job_points.category_total(14, "Wyvern Max HP Bonus")
        wyvern = job_points.category_total(14, "Wyvern Attr. Increase Effect")
        hp += wyvern
        accuracy += wyvern
        breath = job_points.category_total(14, "Wyvern Breath Effect")
    elif int(owner_job) == 18:  # Puppetmaster
        hp += job_points.category_total(18, "Automaton Max HP and Automaton Max MP Bonus")
        accuracy += job_points.category_total(18, "Automaton Max HP and Automaton Max MP Bonus") // 20
    elif int(owner_job) == 15:  # Summoner, future avatars
        accuracy += job_points.category_total(15, "Avatar/Spirit Accuracy Bonus")
        accuracy += job_points.category_total(15, "Avatar/Spirit Magic Accuracy Bonus")
        damage += job_points.category_total(15, "Avatar/Spirit Physical Attack")
        damage += job_points.category_total(15, "Avatar/Spirit Mag. Damage")
    delay = int(spec.delay_ms)
    if int(owner_job) == 9:
        delay = delay * max(50, 100 - job_points.category_total(
            9, "Pet Attack Speed")) // 100
    return {
        "hp": hp,
        "attack": attack,
        "accuracy": accuracy,
        "damage_mult": max(50, min(300, damage)),
        "delay_ms": max(1200, delay),
        "breath_bonus": int(breath) if int(owner_job) == 14 else 0,
    }
