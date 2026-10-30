#!/usr/bin/env python3
"""Import LandSandBoat's monster TP moves into a Fanxi migration.

LandSandBoat keeps the monster abilities in ``sql/mob_skills.sql`` (one row per
ability) and ``sql/mob_skill_lists.sql`` (which abilities each family uses).  A
monster's list comes from ``skill_list_id`` in data/zones/<zone>/mobs.yaml; the
spawn importer dropped that field, so this tool re-reads the same tree and joins
each Fanxi ``monster_spawns`` row back to its LSB spawn by zone and targid.

    tools/import_lsb_mobskills.py --source /tmp/lsb_full --db data/fanxi.db \\
        --out database/migrations/0148_mob_skills.sql

The generated migration adds ``monster_templates.skill_list_id`` plus the two
data tables.  The database must already have migrations through 0147 applied (the
template ids 4306... are the ones migration 0057 wrote).
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sqlite3

import yaml

try:  # libyaml is much faster on the zone tree
    LOADER = yaml.CSafeLoader
except AttributeError:  # pragma: no cover - depends on the installed wheel
    LOADER = yaml.SafeLoader

SKILL_FLAGS = {
    "@SKILLFLAG_NONE": 0,
    "@SKILLFLAG_ASTRAL_FLOW": 2,
    "@SKILLFLAG_NO_TP_COST": 4,
    "@SKILLFLAG_NO_START_MSG": 16,
    "@SKILLFLAG_NO_FINISH_MSG": 32,
    "@SKILLFLAG_BLOODPACT_RAGE": 64,
    "@SKILLFLAG_BLOODPACT_WARD": 128,
    "@SKILLFLAG_ALWAYS_ANIMATE": 256,
}


def split_values(text: str) -> list[str]:
    """Split a SQL VALUES tuple, respecting single-quoted strings."""
    out: list[str] = []
    current: list[str] = []
    quoted = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            if quoted and index + 1 < len(text) and text[index + 1] == "'":
                current.append("'")
                index += 2
                continue
            quoted = not quoted
            current.append(char)
        elif char == "," and not quoted:
            out.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    out.append("".join(current).strip())
    return out


def sql_rows(path: str):
    """Yield the VALUES tuple of every executable INSERT in one LSB SQL file."""
    for line in open(path, encoding="utf-8", errors="replace"):
        stripped = line.lstrip()
        if stripped.startswith("--") or "INSERT INTO" not in line:
            continue
        end = line.find(");")
        if end < 0:
            continue
        match = re.search(r"VALUES \((.*)\)$", line[:end + 1], re.S)
        if match:
            yield split_values(match.group(1))


def sql_int(value: str) -> int:
    value = value.strip()
    if value in SKILL_FLAGS:
        return SKILL_FLAGS[value]
    total = 0
    for part in value.split("+"):
        part = part.strip()
        if part in SKILL_FLAGS:
            total += SKILL_FLAGS[part]
        else:
            try:
                total += int(part)
            except ValueError:
                return 0
    return total


def sql_text(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def read_skills(source: str) -> list[dict]:
    rows = []
    for values in sql_rows(os.path.join(source, "sql", "mob_skills.sql")):
        if len(values) < 15:
            continue
        try:
            rows.append({
                "id": int(values[0]),
                "animation": int(values[1]),
                "name": sql_text(values[2]),
                "aoe": int(values[3]),
                "aoe_radius": float(values[4]),
                "distance": float(values[5]),
                "animation_time": int(values[6]),
                "prepare_time": int(values[7]),
                "valid_targets": int(values[8]),
                "flag": sql_int(values[9]),
                "param": sql_int(values[10]),
                "knockback": int(values[11]),
                "primary_sc": int(values[12]),
                "secondary_sc": int(values[13]),
                "tertiary_sc": int(values[14]),
            })
        except (TypeError, ValueError):
            continue
    return rows


def read_skill_lists(source: str) -> list[dict]:
    rows = []
    for values in sql_rows(os.path.join(source, "sql", "mob_skill_lists.sql")):
        if len(values) < 3:
            continue
        try:
            rows.append({
                "name": sql_text(values[0]),
                "list_id": int(values[1]),
                "skill_id": int(values[2]),
            })
        except (TypeError, ValueError):
            continue
    return rows


def read_spawn_skill_lists(source: str) -> dict[tuple[int, int], int]:
    """(zone, targid) -> skill_list_id from the LSB zone tree.

    The importer masks the spawn's zone the same way: ``(id >> 12) & 0xFFF``.  The
    low 12 bits are the targid the client's entity table uses, and they are what
    monster_spawns stores.
    """
    out: dict[tuple[int, int], int] = {}
    pattern = os.path.join(source, "data", "zones", "*", "mobs.yaml")
    for path in glob.glob(pattern):
        try:
            doc = yaml.load(open(path, encoding="utf-8"), Loader=LOADER) or {}
        except Exception:
            continue
        spawns = doc.get("spawns") or {}
        if not spawns:
            continue
        templates = doc.get("templates") or {}
        for raw_id, spawn in spawns.items():
            if not isinstance(spawn, dict):
                continue
            definition = templates.get(spawn.get("template"))
            if not isinstance(definition, dict):
                continue
            spawn_id = int(raw_id)
            zone = (spawn_id >> 12) & 0xFFF
            targid = spawn_id & 0xFFF
            out[(zone, targid)] = int(definition.get("skill_list_id") or 0)
    return out


def template_skill_lists(db_path: str, spawn_skills: dict[tuple[int, int], int]):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT s.template_id, s.zone, s.targid FROM monster_spawns s").fetchall()
    finally:
        conn.close()
    by_template: dict[int, dict[int, int]] = {}
    for template_id, zone, targid in rows:
        skill_list = spawn_skills.get((int(zone), int(targid)))
        if skill_list:
            counts = by_template.setdefault(int(template_id), {})
            counts[skill_list] = counts.get(skill_list, 0) + 1
    resolved = {}
    conflicts = 0
    for template_id, counts in by_template.items():
        best = max(counts.items(), key=lambda item: item[1])[0]
        resolved[template_id] = best
        if len(counts) > 1:
            conflicts += 1
    return resolved, conflicts


def quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def chunked(rows, size=200):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def write_migration(path: str, skills: list[dict], lists: list[dict],
                    template_lists: dict[int, int]) -> None:
    lines: list[str] = []
    add = lines.append
    add("-- Monster TP moves, imported from LandSandBoat's sql/mob_skills.sql and")
    add("-- sql/mob_skill_lists.sql, with each template's skill_list_id read from the")
    add("-- zone's mobs.yaml (tools/import_lsb_mobskills.py).")
    add("--")
    add("-- A monster gains TP from its own swings and from being hit; at its threshold it")
    add("-- spends the bar on one of these moves (world._tick_mob).  The row's animation is")
    add("-- the client's mob-skill animation, and aoe 1/2 are self-/target-centred AoE.")
    add("ALTER TABLE monster_templates ADD COLUMN skill_list_id INTEGER NOT NULL DEFAULT 0;")
    add("")
    add("CREATE TABLE IF NOT EXISTS mob_skills (")
    add("  id INTEGER PRIMARY KEY,")
    add("  name TEXT NOT NULL,")
    add("  animation INTEGER NOT NULL DEFAULT 0,")
    add("  aoe INTEGER NOT NULL DEFAULT 0,")
    add("  aoe_radius REAL NOT NULL DEFAULT 0,")
    add("  distance REAL NOT NULL DEFAULT 6,")
    add("  animation_time INTEGER NOT NULL DEFAULT 2000,")
    add("  prepare_time INTEGER NOT NULL DEFAULT 1000,")
    add("  valid_targets INTEGER NOT NULL DEFAULT 4,")
    add("  flag INTEGER NOT NULL DEFAULT 0,")
    add("  param INTEGER NOT NULL DEFAULT 0,")
    add("  knockback INTEGER NOT NULL DEFAULT 0,")
    add("  primary_sc INTEGER NOT NULL DEFAULT 0,")
    add("  secondary_sc INTEGER NOT NULL DEFAULT 0,")
    add("  tertiary_sc INTEGER NOT NULL DEFAULT 0")
    add(");")
    add("")
    add("CREATE TABLE IF NOT EXISTS mob_skill_lists (")
    add("  skill_list_id INTEGER NOT NULL,")
    add("  mob_skill_id INTEGER NOT NULL,")
    add("  skill_list_name TEXT,")
    add("  PRIMARY KEY (skill_list_id, mob_skill_id)")
    add(");")
    add("")
    add("CREATE INDEX IF NOT EXISTS mob_skill_lists_by_skill ON mob_skill_lists (mob_skill_id);")
    add("")
    for group in chunked(skills):
        values = ",\n".join(
            "(%d,%s,%d,%d,%s,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d)" % (
                row["id"], quote(row["name"]), row["animation"], row["aoe"],
                row["aoe_radius"], row["distance"], row["animation_time"],
                row["prepare_time"], row["valid_targets"], row["flag"], row["param"],
                row["knockback"], row["primary_sc"], row["secondary_sc"],
                row["tertiary_sc"])
            for row in group)
        add("INSERT INTO mob_skills (id,name,animation,aoe,aoe_radius,distance,"
            "animation_time,prepare_time,valid_targets,flag,param,knockback,"
            "primary_sc,secondary_sc,tertiary_sc) VALUES")
        add(values + ";")
    add("")
    for group in chunked(lists):
        values = ",\n".join(
            "(%d,%d,%s)" % (row["list_id"], row["skill_id"], quote(row["name"]))
            for row in group)
        add("INSERT INTO mob_skill_lists (skill_list_id,mob_skill_id,skill_list_name) VALUES")
        add(values + ";")
    add("")
    # One UPDATE per list keeps the migration small and still binds every template id
    # explicitly; templates with no list keep the column's 0.
    grouped: dict[int, list[int]] = {}
    for template_id, skill_list in template_lists.items():
        grouped.setdefault(int(skill_list), []).append(int(template_id))
    for skill_list in sorted(grouped):
        ids = sorted(grouped[skill_list])
        add("UPDATE monster_templates SET skill_list_id = %d WHERE id IN (%s);"
            % (skill_list, ",".join(str(value) for value in ids)))
    add("")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="/tmp/lsb_full")
    parser.add_argument("--db", default="data/fanxi.db")
    parser.add_argument("--out", default="database/migrations/0148_mob_skills.sql")
    args = parser.parse_args()

    skills = read_skills(args.source)
    lists = read_skill_lists(args.source)
    spawn_skills = read_spawn_skill_lists(args.source)
    templates, conflicts = template_skill_lists(args.db, spawn_skills)
    print("skills %d  list rows %d  spawns mapped %d  templates %d  conflicts %d"
          % (len(skills), len(lists), len(spawn_skills), len(templates), conflicts))
    if not skills or not lists or not templates:
        raise SystemExit("nothing to import; check --source/--db")
    write_migration(args.out, skills, lists, templates)
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
