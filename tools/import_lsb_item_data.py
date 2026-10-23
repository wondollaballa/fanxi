#!/usr/bin/env python3
"""Import LandSandBoat's item combat data into a Fanxi migration.

Two tables come out of this, both keyed by the item id the client already uses:

``item_weapon``
    damage rating, delay, weapon skill type, item-level skill and damage type for
    every weapon, shield and instrument LandSandBoat knows.

``item_mods``
    ``(item id, modifier id, value)`` for every item.  This is what makes gear do
    something: Attack+, Defense+, STR+, and the damage-taken family (PDT, MDT, DT,
    PDT-II) that the combat engine applies after damage is rolled.

``item_shield``
    shield size by item id.  The size sets the base shield-block rate, and only the
    items in this table count as shields.

The modifier ids are LandSandBoat's ``xi::Mod`` values (``data/enums/mod.yaml``);
the ones the engine reads are named in ``server/fanxi_server/game/modifiers.py``.

    tools/import_lsb_item_data.py --source /tmp/lsb

The output is deterministic, so re-running it after updating the source checkout
produces a reviewable diff.  It writes ``database/migrations/0080_item_combat_data.sql``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHUNK = 400  # rows per INSERT statement: keeps statements sane and the file small

WEAPON_COLUMNS = ("item_id", "skill", "ilvl_skill", "delay", "dmg", "dmg_type")


def read_sql(source: Path, relative: str) -> str:
    """Read a dump, from the working tree or from git when the checkout is sparse."""
    path = source / relative
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        return subprocess.run(["git", "-C", str(source), "show", "HEAD:" + relative],
                              check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("cannot read %s from %s (%s)" % (relative, source, exc)) from None


def split_fields(body: str) -> list[str]:
    """Split a SQL VALUES tuple body on commas outside single quotes."""
    fields: list[str] = []
    current: list[str] = []
    quoted = False
    index = 0
    while index < len(body):
        char = body[index]
        if quoted:
            if char == "\\" and index + 1 < len(body):  # MySQL's \' inside a name
                current.append(body[index + 1])
                index += 2
                continue
            if char == "'":
                if index + 1 < len(body) and body[index + 1] == "'":
                    current.append("'")
                    index += 2
                    continue
                quoted = False
                index += 1
                continue
            current.append(char)
        else:
            if char == "'":
                quoted = True
            elif char == ",":
                fields.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        index += 1
    fields.append("".join(current).strip())
    return fields


def parse_rows(text: str, table: str) -> list[list[str]]:
    rows = []
    pattern = re.compile(r"INSERT INTO `%s` VALUES \((.*?)\);" % re.escape(table))
    for match in pattern.finditer(text):
        rows.append(split_fields(match.group(1)))
    return rows


def int_or_zero(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="/tmp/lsb",
                        help="LandSandBoat checkout (default /tmp/lsb)")
    parser.add_argument("--output",
                        default=str(ROOT / "database/migrations/0080_item_combat_data.sql"))
    args = parser.parse_args()

    source = Path(args.source)

    # item_weapon: itemId, name, skill, subskill, ilvl_skill, ilvl_parry, ilvl_macc,
    #              dmgType, hit, delay, dmg, unlock_points
    weapon_rows = []
    for fields in parse_rows(read_sql(source, "sql/item_weapon.sql"), "item_weapon"):
        if len(fields) < 12:
            continue
        item_id = int_or_zero(fields[0])
        if item_id <= 0:
            continue
        weapon_rows.append((item_id, int_or_zero(fields[2]), int_or_zero(fields[4]),
                            int_or_zero(fields[9]), int_or_zero(fields[10]),
                            int_or_zero(fields[7])))
    weapon_rows.sort()

    # item_equipment: itemId, name, level, ilevel, jobs, MId, shieldSize, ...
    shield_rows = []
    equipment_text = read_sql(source, "sql/item_equipment.sql")
    shield_pattern = re.compile(
        r"INSERT INTO `item_equipment` VALUES \((\d+),'([^']*)',(\d+),(\d+),(\d+),(\d+),(\d+),")
    for match in shield_pattern.finditer(equipment_text):
        item_id, _name, level, ilevel, _jobs, _mid, shield_size = match.groups()
        if int(shield_size) > 0:
            shield_rows.append((int(item_id), int(shield_size), int(level), int(ilevel)))
    shield_rows.sort()

    # item_mods: itemId, modId, value
    mod_rows = []
    for fields in parse_rows(read_sql(source, "sql/item_mods.sql"), "item_mods"):
        if len(fields) < 3:
            continue
        item_id, mod_id, value = (int_or_zero(fields[0]), int_or_zero(fields[1]),
                                  int_or_zero(fields[2]))
        if item_id <= 0 or mod_id <= 0:
            continue
        mod_rows.append((item_id, mod_id, value))
    mod_rows.sort()

    out: list[str] = []
    out.append("-- Item combat data (migration 80), generated by tools/import_lsb_item_data.py.")
    out.append("--")
    out.append("-- `item_weapon` carries the damage rating, delay, skill type and damage type of")
    out.append("-- every weapon; `item_mods` carries every item's stat modifiers as")
    out.append("-- (item id, modifier id, value).  Both are LandSandBoat's tables verbatim.")
    out.append("--")
    out.append("-- Item ids are the client's own, so a row here is meaningful for any item Fanxi")
    out.append("-- grants, whether or not it is in the `items` catalogue yet.  Neither table has a")
    out.append("-- foreign key for that reason.")
    out.append("")
    out.append("CREATE TABLE IF NOT EXISTS item_weapon (")
    out.append("    item_id    INTEGER PRIMARY KEY,")
    out.append("    skill      INTEGER NOT NULL DEFAULT 0,")
    out.append("    ilvl_skill INTEGER NOT NULL DEFAULT 0,")
    out.append("    delay      INTEGER NOT NULL DEFAULT 0,")
    out.append("    dmg        INTEGER NOT NULL DEFAULT 0,")
    out.append("    dmg_type   INTEGER NOT NULL DEFAULT 0")
    out.append(");")
    out.append("")
    out.append("CREATE TABLE IF NOT EXISTS item_shield (")
    out.append("    item_id INTEGER PRIMARY KEY,")
    out.append("    size    INTEGER NOT NULL,")
    out.append("    level   INTEGER NOT NULL DEFAULT 0,")
    out.append("    ilevel  INTEGER NOT NULL DEFAULT 0")
    out.append(");")
    out.append("")
    out.append("CREATE TABLE IF NOT EXISTS item_mods (")
    out.append("    item_id INTEGER NOT NULL,")
    out.append("    mod_id  INTEGER NOT NULL,")
    out.append("    value   INTEGER NOT NULL,")
    out.append("    PRIMARY KEY (item_id, mod_id)")
    out.append(");")
    out.append("")

    def emit(table: str, columns: tuple[str, ...], rows: list[tuple]) -> None:
        head = "INSERT INTO %s (%s) VALUES " % (table, ", ".join(columns))
        for start in range(0, len(rows), CHUNK):
            chunk = rows[start:start + CHUNK]
            # One statement per line: the migration runner completes statements line by
            # line, and a wrapped 400-row INSERT costs far more than a long one.
            values = ", ".join("(%s)" % ", ".join(str(value) for value in row)
                               for row in chunk)
            out.append(head + values + ";")
            out.append("")

    emit("item_weapon", WEAPON_COLUMNS, weapon_rows)
    emit("item_shield", ("item_id", "size", "level", "ilevel"), shield_rows)
    emit("item_mods", ("item_id", "mod_id", "value"), mod_rows)
    out.append("CREATE INDEX IF NOT EXISTS item_mods_mod ON item_mods(mod_id);")
    out.append("")

    text = "\n".join(out)
    target = Path(args.output)
    target.write_text(text, encoding="utf-8")
    print("wrote %s" % target)
    print("  item_weapon rows: %d" % len(weapon_rows))
    print("  item_shield rows: %d" % len(shield_rows))
    print("  item_mods rows:   %d" % len(mod_rows))
    print("  size:             %.1f MB" % (len(text) / (1024 * 1024)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
