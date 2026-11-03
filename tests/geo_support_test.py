#!/usr/bin/env python3
"""Check the Battle hub's GEO loop targets hexes and buffs correctly.

The 2026-11 regression: the support loop sent Geo-Frailty/Geo-Malaise to the tank by
subtarget, but those are enemy-target spells, so the client rejected every cast.  The
loop also kept the GEO in a support camp forty yalms from the anchor, outside the
12-yalm Geocolure range.  This test pins the two branches and the walk-to-anchor step.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATTLE = ROOT / "host" / "addons" / "lua" / "battle.lua"


def block(source: str, start: str, end: str) -> str:
    first = source.index(start)
    last = source.index(end, first)
    return source[first:last]


def main() -> int:
    source = BATTLE.read_text(encoding="utf-8")
    cast = block(source, "function B.geo_cast", "local function geo_tick")
    tick = block(source, "local function geo_tick", "function B.brd_group_name")

    if "is_enemy(spell)" not in cast or "B.cast_on_enemy(cfg.geo" not in cast:
        raise SystemExit("GEO hex branch does not cast on the monster")
    if "B.cast_on_member(cfg.geo" not in cast:
        raise SystemExit("GEO buff branch lost its party-anchor cast")
    if not re.search(r"if need_geo and dist > reach then\s+B\.move_to\(anchor", tick):
        raise SystemExit("GEO loop never walks into Geocolure range")
    if "B.geo_cast(cfg, me, anchor, dist, range, now, geo)" not in tick:
        raise SystemExit("GEO loop does not call B.geo_cast")
    anchor = block(source, "local function geo_anchor", "function B.geo_cast")
    if "member.x, member.y, member.z = pos.x, pos.y, pos.z" not in anchor:
        raise SystemExit("GEO anchor has no position; distance() would error")
    print("OK: GEO hexes target monsters, buffs target the anchor, and the loop walks in")
    return 0


if __name__ == "__main__":
    sys.exit(main())
