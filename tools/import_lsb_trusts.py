#!/usr/bin/env python3
"""Import the factual alter-ego data behind Trust magic into Fanxi.

The client has the Trust spells and their menus; it has no idea what an alter ego
looks like or which job it fights as.  LandSandBoat keeps one ``mob_pools`` row per
Trust at ``poolid = spellid + 5000``: the 20-byte look block, main/sub job, combat
skill, attack delay and damage multiplier.  It also reads each Trust's row in
``mob_spell_lists`` so an alter ego knows the spells its job can actually cast.  This
tool reads only those factual fields and writes ``database/migrations/0115_trusts.sql``
and ``0117_trust_spells.sql``; the schema, names and comments are Fanxi's own.

    tools/import_lsb_trusts.py --source /tmp/lsb
    tools/import_lsb_trusts.py --source /tmp/lsb --check   # exit 1 if stale

The display name comes from Fanxi's own spell table, not LandSandBoat's, because the
client's Trust menu is keyed on the spell name.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "database" / "migrations" / "0115_trusts.sql"
SPELL_LISTS = ROOT / "database" / "migrations" / "0117_trust_spells.sql"
SPELLS = ROOT / "database" / "migrations" / "0058_spells.sql"

# Trusts that are walking Geomancy bubbles rather than fighters.  The client allows
# them to be called, but they cannot be targeted and do not auto-attack.
PASSIVE = {
    "Sakura", "Moogle", "Star Sibyl", "Kuyin Hathdenna", "Brygid", "Kupofried",
    "Cornelia",
}


def split_values(text: str) -> list[str]:
    """Split one SQL VALUES row, keeping quoted commas and escaped quotes intact."""
    parts: list[str] = []
    current = ""
    quoted = False
    escaped = False
    for char in text:
        if escaped:
            current += char
            escaped = False
        elif char == "\\":
            current += char
            escaped = True
        elif char == "'":
            quoted = not quoted
            current += char
        elif char == "," and not quoted:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    parts.append(current.strip())
    return parts


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def read_all_spells() -> dict[int, str]:
    """spell id -> Fanxi's display name, from the committed spell migration."""
    names: dict[int, str] = {}
    pattern = re.compile(
        r"INSERT INTO spells \([^)]*\) VALUES \((\d+),'((?:[^']|'')*)'")
    for line in SPELLS.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            names[int(match.group(1))] = match.group(2).replace("''", "'")
    return names


def read_spells() -> dict[int, str]:
    """spell id -> name for the Trust summoning spells (896 and up)."""
    return {spell_id: name for spell_id, name in read_all_spells().items()
            if spell_id >= 896}


def read_spell_lists(source: Path) -> dict[int, dict[int, tuple[int, int]]]:
    """mob_spell_list id -> {spell id: (minimum caster level, maximum)}."""
    path = source / "sql" / "mob_spell_lists.sql"
    if not path.exists():
        raise SystemExit("missing %s (point --source at a LandSandBoat checkout)" % path)
    lists: dict[int, dict[int, tuple[int, int]]] = {}
    pattern = re.compile(
        r"VALUES \('([^']+)',(\d+),(\d+),(\d+),(\d+)\)")
    for match in pattern.finditer(path.read_text(encoding="utf-8")):
        lists.setdefault(int(match.group(2)), {})[int(match.group(3))] = (
            int(match.group(4)), int(match.group(5)))
    return lists


def read_pools(source: Path) -> dict[int, dict]:
    """poolid -> the factual Trust fields out of ``sql/mob_pools.sql``."""
    path = source / "sql" / "mob_pools.sql"
    if not path.exists():
        raise SystemExit("missing %s (point --source at a LandSandBoat checkout)" % path)
    pools: dict[int, dict] = {}
    pattern = re.compile(r"INSERT INTO `mob_pools` VALUES \((.*?)\);")
    for match in pattern.finditer(path.read_text(encoding="utf-8")):
        fields = split_values(match.group(1))
        if len(fields) < 27:
            continue
        try:
            poolid = int(fields[0])
        except ValueError:
            continue
        if not 5896 <= poolid <= 6019:
            continue
        look_hex = fields[4]
        if look_hex.startswith("0x"):
            look_hex = look_hex[2:]
        look = bytes.fromhex(look_hex)
        pools[poolid] = {
            "pool": poolid,
            "job": int(fields[5]),
            "sub_job": int(fields[6]),
            "look": look,
            # The look block is size, model id/race+face, then eight equipment
            # models.  Trusts in this dataset are fixed-model NPCs (size 0), so the
            # model id is the second uint16.
            "model": int.from_bytes(look[2:4], "little"),
            "delay": int(fields[8]),
            "damage_mult": int(fields[9]),
            "name_prefix": int(fields[16]),
            "spell_list": int(fields[21]),
        }
    return pools


def build(source: Path) -> tuple[str, int]:
    spells = read_spells()
    pools = read_pools(source)
    rows = []
    for spell_id in sorted(spells):
        pool = pools.get(spell_id + 5000)
        if pool is None:
            continue
        name = spells[spell_id]
        rows.append(
            "(%d,%s,%d,%d,'%s',%d,%d,%d,%d,%d,%d,%d)"
            % (spell_id, sql_string(name), pool["job"], pool["sub_job"],
               pool["look"].hex(), pool["model"], pool["delay"],
               pool["damage_mult"], pool["name_prefix"], pool["spell_list"],
               int(name in PASSIVE), pool["pool"]))
    if len(rows) != 122:
        raise SystemExit("expected 122 Trusts, found %d" % len(rows))

    text = """\
-- Trust alter egos: the factual look/job/combat data behind the client's Trust spells.
--
-- Generated by tools/import_lsb_trusts.py from LandSandBoat's mob_pools table (poolid
-- = spellid + 5000) and Fanxi's own spell names.  Only numbers, model ids and game
-- names are stored; the schema and this file are Fanxi's own.
CREATE TABLE IF NOT EXISTS trusts (
    spell_id    INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    job         INTEGER NOT NULL DEFAULT 1,
    sub_job     INTEGER NOT NULL DEFAULT 0,
    look_hex    TEXT NOT NULL,
    model       INTEGER NOT NULL DEFAULT 0,
    delay       INTEGER NOT NULL DEFAULT 240,
    damage_mult INTEGER NOT NULL DEFAULT 100,
    name_prefix INTEGER NOT NULL DEFAULT 0,
    spell_list  INTEGER NOT NULL DEFAULT 0,
    passive     INTEGER NOT NULL DEFAULT 0,
    pool_id     INTEGER NOT NULL DEFAULT 0
);

DELETE FROM trusts;
INSERT INTO trusts
    (spell_id, name, job, sub_job, look_hex, model, delay, damage_mult,
     name_prefix, spell_list, passive, pool_id)
VALUES
    %s;
""" % ",\n    ".join(rows)
    return text, len(rows)


def build_trust_spells(source: Path) -> tuple[str, int]:
    """The joined spell list behind every Trust that has one.

    A Trust row carries the LandSandBoat ``mob_spell_lists`` id it was built from.  The
    list says which spells the job may cast and the level at which each unlocks; storing
    the join per Trust avoids every session having to read a 4,600-row table to find the
    handful of rows for one alter ego.
    """
    spells = read_all_spells()
    trust_ids = read_spells()
    pools = read_pools(source)
    lists = read_spell_lists(source)
    rows = []
    for trust_id in sorted(trust_ids):
        pool = pools.get(trust_id + 5000)
        if pool is None or not pool["spell_list"]:
            continue
        for spell_id, (min_level, max_level) in sorted(
                lists.get(pool["spell_list"], {}).items()):
            if spell_id not in spells:
                continue
            rows.append("(%d,%d,%d,%d)" % (trust_id, spell_id, min_level, max_level))
    if len(rows) != 1259:
        raise SystemExit("expected 1259 Trust spell rows, found %d" % len(rows))

    text = """\
-- The spells each Trust can cast, from LandSandBoat's mob_spell_lists rows.
--
-- Generated by tools/import_lsb_trusts.py.  ``trust_spell_id`` is the Trust spell the
-- player casts (not the mob_spell_lists id); min_level is the job level at which the
-- alter ego unlocks that spell.  Only factual ids and levels are stored; the behaviour
-- that chooses a spell is Fanxi's own.
CREATE TABLE IF NOT EXISTS trust_spells (
    trust_spell_id INTEGER NOT NULL,
    spell_id       INTEGER NOT NULL,
    min_level      INTEGER NOT NULL DEFAULT 1,
    max_level      INTEGER NOT NULL DEFAULT 255,
    PRIMARY KEY (trust_spell_id, spell_id)
);

DELETE FROM trust_spells;
INSERT INTO trust_spells (trust_spell_id, spell_id, min_level, max_level)
VALUES
    %s;
""" % ",\n    ".join(rows)
    return text, len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=Path("/tmp/lsb"),
                        help="LandSandBoat checkout (default /tmp/lsb)")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the committed migration is stale")
    args = parser.parse_args()
    text, count = build(args.source)
    spells_text, spell_count = build_trust_spells(args.source)
    outputs = ((OUT, text, "database/migrations/0115_trusts.sql"),
               (SPELL_LISTS, spells_text, "database/migrations/0117_trust_spells.sql"))
    if args.check:
        for path, expected, label in outputs:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != expected:
                print("%s is stale" % label, file=sys.stderr)
                return 1
        return 0
    for path, content, _label in outputs:
        path.write_text(content, encoding="utf-8")
    print("wrote %s (%d Trusts)" % (OUT.relative_to(ROOT), count))
    print("wrote %s (%d spell rows)" % (SPELL_LISTS.relative_to(ROOT), spell_count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
