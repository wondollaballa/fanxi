"""Call Beast jugs: which pet a jug summons, and the Ready moves that pet knows.

The catalogue is generated from LandSandBoat by ``tools/gen_jug_pets.py``; the zone
server reads ``data/jug_pets.json`` and the in-game HUD reads the same data as Lua
(``host/addons/lua/jugpets.lua``).  Keeping one source means the jug the server
spawns is the pet whose moves the HUD offers.

The server's pet model is deliberately small: it knows the pet's display name and
look, which is what the client renders for Call Beast/Bestial Loyalty.  The Ready
move list is carried for the HUD and for the later Ready implementation; using a
move still goes through the client's own pet-command action.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .pets import PetSpec

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "jug_pets.json"


@lru_cache(maxsize=1)
def catalogue() -> dict[int, dict]:
    """Item id -> {item, pet, pet_id, model, level, moves}."""
    try:
        document = json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = document.get("jugs") or {}
    return {int(item_id): row for item_id, row in rows.items()
            if isinstance(row, dict) and int(row.get("model") or 0) > 0}


def for_item(item_id: int) -> dict | None:
    return catalogue().get(int(item_id or 0))


def spec(row: dict) -> PetSpec:
    """The PetSpec the world's ``spawn_pet`` builds the entity from."""
    return PetSpec(
        key="jug:%d" % int(row.get("pet_id") or 0),
        name=str(row.get("pet") or "Familiar"),
        model=int(row.get("model") or 0),
        hp_mult=100,
        attack_mult=100,
    )


def ready_moves(item_id: int) -> list[str]:
    row = for_item(item_id) or {}
    return [str(move.get("name") or "") for move in row.get("moves") or []
            if str(move.get("name") or "")]


def for_pet_name(name: str) -> dict | None:
    """The jug record for a rendered pet name, for diagnostics and tests."""
    key = " ".join(str(name or "").casefold().split())
    if not key:
        return None
    for row in catalogue().values():
        if " ".join(str(row.get("pet") or "").casefold().split()) == key:
            return row
    return None
