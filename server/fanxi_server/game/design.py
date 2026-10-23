"""Character designs: race, face, hair colour and body size.

The client packs a player's face and hair colour into one look byte::

    look = (face - 1) * 2 + hair

where ``face`` is 1-8 and ``hair`` is 0 for colour A or 1 for colour B.  Face 2,
Hair A is therefore look 2.  The old ``characters.face`` column stored that
combined value; migration 0093 splits it into ``face`` + ``hair`` while keeping
every existing character's appearance unchanged.

A *variant* is the number the in-game command takes: the 48 designs of one race
(8 faces x 2 hair colours x 3 sizes), numbered with size fastest::

    1-3   Face 1, Hair A, Small/Medium/Large
    4-6   Face 1, Hair B, Small/Medium/Large
    7-9   Face 2, Hair A, ...
    ...
    46-48 Face 8, Hair B, ...

This module is shared by the server, the HTTP API, the launcher-facing tools and
``tools/character_design.py``, so there is exactly one definition of the wire
value and the labels.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Race:
    id: int
    key: str
    name: str
    gender: str
    label: str
    female: bool = False


RACES: tuple[Race, ...] = (
    Race(1, "hume", "Hume", "male", "Hume male"),
    Race(2, "hume", "Hume", "female", "Hume female", True),
    Race(3, "elvaan", "Elvaan", "male", "Elvaan male"),
    Race(4, "elvaan", "Elvaan", "female", "Elvaan female", True),
    Race(5, "tarutaru", "Tarutaru", "male", "Tarutaru male"),
    Race(6, "tarutaru", "Tarutaru", "female", "Tarutaru female", True),
    Race(7, "mithra", "Mithra", "female", "Mithra", True),
    Race(8, "galka", "Galka", "male", "Galka"),
)

RACE_BY_ID = {race.id: race for race in RACES}

FACE_COUNT = 8
HAIR_COUNT = 2
SIZE_COUNT = 3
VARIANTS_PER_RACE = FACE_COUNT * HAIR_COUNT * SIZE_COUNT  # 48
TOTAL_VARIANTS = len(RACES) * VARIANTS_PER_RACE  # 384

SIZE_LABELS = {0: "Small", 1: "Medium", 2: "Large"}
HAIR_LABELS = {0: "A", 1: "B"}

_RACE_ALIASES = {
    "hume": 1,
    "humemale": 1,
    "humem": 1,
    "malehume": 1,
    "humefemale": 2,
    "humef": 2,
    "femalehume": 2,
    "elvaan": 3,
    "elvaanmale": 3,
    "elvaanm": 3,
    "maleelvaan": 3,
    "elvaanfemale": 4,
    "elvaanf": 4,
    "femaleelvaan": 4,
    "tarutaru": 5,
    "tarutarumale": 5,
    "tarutaruf": 5,
    "tarum": 5,
    "taru": 5,
    "maletarutaru": 5,
    "tarutarufemale": 6,
    "taruf": 6,
    "femaletarutaru": 6,
    "mithra": 7,
    "mith": 7,
    "galka": 8,
    "gal": 8,
}

_HAIR_ALIASES = {"a": 0, "0": 0, "b": 1, "1": 1}
_SIZE_ALIASES = {
    "s": 0, "small": 0, "0": 0,
    "m": 1, "medium": 1, "med": 1, "1": 1,
    "l": 2, "large": 2, "big": 2, "2": 2,
}


class DesignError(ValueError):
    """A race/face/hair/size value outside the client's character creator."""


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def race(value: int | str | None) -> Race:
    """Look up a race by id, name or a launcher-friendly alias.

    ``hume`` and ``elvaan`` mean the male model, because that is the order the
    client lists them; use ``hume female`` / ``humef`` for the other one.
    """
    if isinstance(value, Race):
        return value
    if isinstance(value, int):
        race_id = value
    else:
        text = str(value or "").strip()
        if not text:
            raise DesignError("choose a race: hume, humef, elvaan, elvaanf, "
                              "tarutaru, tarutaruf, mithra or galka")
        if text.isdigit():
            race_id = int(text)
        else:
            race_id = _RACE_ALIASES.get(_key(text), 0)
    if race_id not in RACE_BY_ID:
        raise DesignError("unknown race %r (1 Hume male .. 8 Galka)" % (value,))
    return RACE_BY_ID[race_id]


def parse_face(value: int | str) -> int:
    try:
        face = int(value)
    except (TypeError, ValueError):
        raise DesignError("face must be 1-8") from None
    if not 1 <= face <= FACE_COUNT:
        raise DesignError("face must be 1-8")
    return face


def parse_hair(value: int | str) -> int:
    if isinstance(value, int):
        hair = value
    else:
        hair = _HAIR_ALIASES.get(_key(value), -1)
    if hair not in HAIR_LABELS:
        raise DesignError("hair must be A or B (colours)")
    return hair


def parse_size(value: int | str) -> int:
    if isinstance(value, int):
        size = value
    else:
        size = _SIZE_ALIASES.get(_key(value), -1)
    if size not in SIZE_LABELS:
        raise DesignError("size must be small, medium or large")
    return size


def encode_face(face: int, hair: int) -> int:
    """The single client look byte for a face and hair colour."""
    return (parse_face(face) - 1) * 2 + parse_hair(hair)


def decode_face(raw: int) -> tuple[int, int]:
    """Split a client look byte into (face 1-8, hair 0-1)."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 0
    value = max(0, min(FACE_COUNT * HAIR_COUNT - 1, value))
    return value // 2 + 1, value % 2


def variant_index(face: int, hair: int, size: int) -> int:
    """The 1-48 variant number for a face/hair/size triple."""
    return ((parse_face(face) - 1) * 2 + parse_hair(hair)) * 3 + parse_size(size) + 1


def design(race_id: int | str | Race, face: int, hair: int, size: int) -> dict:
    """A fully labelled design dict, the shape the API and preview use."""
    chosen = race(race_id)
    face = parse_face(face)
    hair = parse_hair(hair)
    size = parse_size(size)
    raw = encode_face(face, hair)
    variant = variant_index(face, hair, size)
    label = "%s, Face %d, Hair %s, %s" % (
        chosen.label, face, HAIR_LABELS[hair], SIZE_LABELS[size])
    return {
        "race": chosen.id,
        "race_key": chosen.key,
        "race_name": chosen.name,
        "gender": chosen.gender,
        "race_label": chosen.label,
        "face": face,
        "hair": hair,
        "size": size,
        "raw_face": raw,
        "variant": variant,
        "variants": VARIANTS_PER_RACE,
        "face_label": "Face %d" % face,
        "hair_label": "Hair %s" % HAIR_LABELS[hair],
        "size_label": SIZE_LABELS[size],
        "label": label,
    }


def design_from_variant(race_id: int | str | Race, variant: int) -> dict:
    """One of a race's 48 designs, numbered 1-48."""
    try:
        number = int(variant)
    except (TypeError, ValueError):
        raise DesignError("variant must be 1-%d" % VARIANTS_PER_RACE) from None
    if not 1 <= number <= VARIANTS_PER_RACE:
        raise DesignError("variant must be 1-%d" % VARIANTS_PER_RACE)
    value = number - 1
    size = value % SIZE_COUNT
    pair = value // SIZE_COUNT
    hair = pair % HAIR_COUNT
    face = pair // HAIR_COUNT + 1
    return design(race_id, face, hair, size)


def random_design(race_id: int | str | Race | None = None,
                  rng: random.Random | random.SystemRandom | None = None) -> dict:
    """A random design, optionally inside one race."""
    generator = rng or random.SystemRandom()
    chosen = race(race_id) if race_id is not None else generator.choice(RACES)
    return design(chosen, generator.randint(1, FACE_COUNT),
                  generator.randint(0, HAIR_COUNT - 1), generator.randint(0, SIZE_COUNT - 1))


def from_row(row: Mapping | object) -> dict:
    """A design from a ``characters`` row, including pre-migration saves.

    Rows written before migration 0093 have no ``hair`` column; their ``face``
    is the combined look byte.  Reading them this way means a tool can inspect
    and convert an old database before the migration runs.
    """
    def value(name, default=None):
        try:
            return row[name]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return default

    face_value = value("face", 1)
    face = int(face_value) if face_value is not None else 1
    size_value = value("size", 1)
    size = int(size_value) if size_value is not None else 1
    hair = value("hair")
    if hair is None:
        face, hair = decode_face(face)
    return design(int(value("race", 1) or 1), face, int(hair), size)


def raw_face(row_or_design: Mapping | object) -> int:
    """The client look byte for a row or a design dict."""
    if isinstance(row_or_design, Mapping) and "raw_face" in row_or_design:
        return int(row_or_design["raw_face"])
    item = from_row(row_or_design)
    return int(item["raw_face"])


def variants(race_id: int | str | Race) -> Iterable[dict]:
    """All 48 designs of a race, in command order."""
    chosen = race(race_id)
    for number in range(1, VARIANTS_PER_RACE + 1):
        yield design_from_variant(chosen, number)
