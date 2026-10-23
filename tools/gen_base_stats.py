#!/usr/bin/env python3
"""Generate ``server/fanxi_server/game/base_stats.py`` from LandSandBoat's datasets.

A character's HP, MP and seven attributes come from a race grade, a job grade and a
subjob grade, each of which accumulates a per-level table.  Retail pools the three parts
in half points and rounds once for attributes, adds whole points for HP, and gives the
subjob half of its own MP.

The tables are LandSandBoat's ``data/stats.yaml`` (what a grade is worth per level) and
``data/grades.yaml`` (which grade each job and race holds).  Both are small, so they are
compiled into a Python module: no YAML parser and no data file is needed at runtime, and
the numbers are reviewable in a diff.

    tools/gen_base_stats.py --source /tmp/lsb

Writes the module and prints a few known characters as a sanity check.  Run it again
after updating the source datasets; the output is deterministic.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# Ranks in the order the growth arrays are indexed: none, A .. G.
RANKS = ("none", "a", "b", "c", "d", "e", "f", "g")

# The client's race field is 1-based; the grade tables index races 0..4.
RACES = ("hume", "elvaan", "tarutaru", "mithra", "galka")
RACE_FIELD = {"hume": (1, 2), "elvaan": (3, 4), "tarutaru": (5, 6), "mithra": (7,), "galka": (8,)}

JOBS = ("war", "mnk", "whm", "blm", "rdm", "thf", "pld", "drk", "bst", "brd", "rng",
        "sam", "nin", "drg", "smn", "blu", "cor", "pup", "dnc", "sch", "geo", "run")

ATTRIBUTES = ("str", "dex", "vit", "agi", "int", "mnd", "chr")
ATTRIBUTE_COLUMNS = ("a", "b", "c", "d", "e", "f", "g")
MP_COLUMNS = ("a", "b", "c", "d", "f")  # no job holds an E or G MP grade

LEVELS = 100  # level 0 (no subjob) plus 1..99
ATTRIBUTE_LAST_LEVEL = 75

# Retail halves what a subjob's own MP is worth.
SUBJOB_MP_DIVISOR = 2

ZERO_CURVE = [0] * LEVELS


def build_curve(table: dict, columns: tuple[str, ...], first: int, last: int):
    """Read a level-major table down its columns, accumulating by level.

    A row holds until the next level listed, and the last runs to *last*.
    """
    keys = sorted(int(k) for k in table)
    if not keys or keys[0] != first:
        raise SystemExit("table has to open at level %d" % first)
    if keys[-1] > last:
        raise SystemExit("table keys level %d, past the %d it covers" % (keys[-1], last))

    curves = {column: [0] * LEVELS for column in columns}
    running = {column: 0 for column in columns}
    for index, level in enumerate(keys):
        until = keys[index + 1] - 1 if index + 1 < len(keys) else last
        row = table[level]
        if not isinstance(row, dict):  # a single unnamed column, like the ungraded gain
            row = {columns[0]: row}
        for current in range(level, until + 1):
            for column in columns:
                running[column] += int(row[column])
                curves[column][current] = running[column]
    for column in columns:
        for current in range(last + 1, LEVELS):
            curves[column][current] = curves[column][last]
    return curves


def rank_of(grade: str) -> int:
    return RANKS.index(str(grade).strip().lower())


def read_dataset(source: Path, relative: str) -> dict:
    """Read one dataset, from the working tree or from git when the checkout is sparse."""
    path = source / relative
    if path.is_file():
        return yaml.safe_load(path.read_text())
    try:
        text = subprocess.run(["git", "-C", str(source), "show", "HEAD:" + relative],
                              check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("cannot read %s from %s (%s)" % (relative, source, exc)) from None
    return yaml.safe_load(text)


def curve_rows(curves: dict, key_of_column) -> list[str]:
    rows = ["    %d: (%s)," % (key_of_column(column), ", ".join(str(v) for v in curve))
            for column, curve in curves.items()]
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="/tmp/lsb",
                        help="LandSandBoat checkout (default /tmp/lsb)")
    parser.add_argument("--output", default=str(ROOT / "server/fanxi_server/game/base_stats.py"))
    args = parser.parse_args()

    source = Path(args.source)
    stats_doc = read_dataset(source, "data/stats.yaml")["stats"]
    grades_doc = read_dataset(source, "data/grades.yaml")["grades"]

    if not stats_doc.get("round_once", False):
        raise SystemExit("this generator implements the round-once model only")

    # Attributes: cumulative twentieths, floored to half points at every level.
    by_grade = build_curve(stats_doc["attributes"], ATTRIBUTE_COLUMNS, 1, ATTRIBUTE_LAST_LEVEL)
    half_points = [[0] * LEVELS for _ in RANKS]
    for column_index, column in enumerate(ATTRIBUTE_COLUMNS):
        for level in range(LEVELS):
            half_points[column_index + 1][level] = by_grade[column][level] // 10

    ungraded = build_curve(stats_doc["ungraded"], ("v",), ATTRIBUTE_LAST_LEVEL + 1, LEVELS - 1)
    points_over_75 = ungraded["v"]

    # HP is whole points per level; the subjob adds half of its own job HP.
    job_hp = build_curve(stats_doc["hp"]["graded"], ATTRIBUTE_COLUMNS, 1, LEVELS - 1)
    race_hp = build_curve(stats_doc["hp"]["racial"], RACES, 1, LEVELS - 1)

    # MP has no E or G grade, and the subjob contributes half of its own.
    job_mp = build_curve(stats_doc["mp"]["graded"], MP_COLUMNS, 1, LEVELS - 1)
    race_mp = build_curve(stats_doc["mp"]["racial"], RACES, 1, LEVELS - 1)

    race_grades = {race: {stat: rank_of(grades_doc["races"][race][stat])
                          for stat in ("hp", "mp") + ATTRIBUTES}
                   for race in RACES}
    job_grades = {job: {stat: rank_of(grades_doc["jobs"][job][stat])
                        for stat in ("hp", "mp") + ATTRIBUTES}
                  for job in JOBS}

    out: list[str] = []
    out.append('"""Base character HP, MP and attributes, generated from LandSandBoat\'s datasets.')
    out.append("")
    out.append("Do not edit by hand: regenerate with")
    out.append("    tools/gen_base_stats.py --source /tmp/lsb")
    out.append("")
    out.append("A character's STR (and every other attribute, and HP/MP) is a race grade, a")
    out.append("job grade and a subjob grade, each worth a per-level table.  Retail pools the")
    out.append("three in half points and rounds once for attributes, adds whole points for HP,")
    out.append("and gives the subjob half of its own MP.")
    out.append("")
    out.append("Source: LandSandBoat ``data/stats.yaml`` and ``data/grades.yaml``.")
    out.append('"""')
    out.append("")
    out.append("from __future__ import annotations")
    out.append("")
    out.append("RANKS = %r" % (RANKS,))
    out.append("")
    out.append("# Race index (the order the grade tables use) -> race key.")
    out.append("RACE_NAMES = %r" % (RACES,))
    out.append("")
    out.append("# Race key -> race index, for the race HP/MP tables.")
    out.append("RACES_INDEX = %r" % ({race: index for index, race in enumerate(RACES)},))
    out.append("")
    out.append("# Client race field 1..8 -> the race index the grade tables use.")
    out.append("RACE_OF_FIELD = %r" % ({field: RACES.index(race)
                                        for race, fields in RACE_FIELD.items()
                                        for field in fields},))
    out.append("")
    out.append("# Job id (1..22) -> the job key the grade tables use.")
    out.append("JOB_OF_ID = %r" % ({index + 1: job for index, job in enumerate(JOBS)},))
    out.append("")
    out.append("ATTRIBUTES = %r" % (ATTRIBUTES,))
    out.append("")
    out.append("# The subjob contributes a fraction of its own MP.")
    out.append("SUBJOB_MP_DIVISOR = %d" % SUBJOB_MP_DIVISOR)
    out.append("")
    out.append("# Half points each rank has accumulated by every level (level 0..99).")
    out.append("HALF_POINTS = (")
    for rank_index, row in enumerate(half_points):
        out.append("    # rank %d (%s)" % (rank_index, RANKS[rank_index]))
        out.append("    (%s)," % ", ".join(str(value) for value in row))
    out.append(")")
    out.append("")
    out.append("# Whole points every attribute has gained past level 75.")
    out.append("POINTS_OVER_75 = (%s)" % ", ".join(str(value) for value in points_over_75))
    out.append("")
    out.append("# Job HP by grade rank (0=none, 1=A .. 7=G), accumulated by level.")
    out.append("JOB_HP = {")
    out.append("    0: (%s)," % ", ".join(str(v) for v in ZERO_CURVE))
    out.extend(curve_rows(job_hp, lambda column: ATTRIBUTE_COLUMNS.index(column) + 1))
    out.append("}")
    out.append("")
    out.append("# Race HP by race index, accumulated by level.")
    out.append("RACE_HP = {")
    out.extend(curve_rows(race_hp, lambda column: RACES.index(column)))
    out.append("}")
    out.append("")
    out.append("# Job MP by grade rank (A, B, C, D, F), accumulated by level.")
    out.append("JOB_MP = {")
    out.append("    0: (%s)," % ", ".join(str(v) for v in ZERO_CURVE))
    out.extend(curve_rows(job_mp, lambda column: RANKS.index(column)))
    out.append("}")
    out.append("")
    out.append("# Race MP by race index, accumulated by level.")
    out.append("RACE_MP = {")
    out.extend(curve_rows(race_mp, lambda column: RACES.index(column)))
    out.append("}")
    out.append("")
    out.append("# A subjob the character does not have contributes nothing.")
    out.append("NONE_GRADES = %r" % ({stat: 0 for stat in ("hp", "mp") + ATTRIBUTES},))
    out.append("")
    out.append("# Race key -> stat -> rank.  Stats are hp, mp and the seven attributes.")
    out.append("RACE_GRADES = {")
    for race in RACES:
        out.append("    %r: %r," % (race, race_grades[race]))
    out.append("}")
    out.append("")
    out.append("# Job key -> stat -> rank.")
    out.append("JOB_GRADES = {")
    for job in JOBS:
        out.append("    %r: %r," % (job, job_grades[job]))
    out.append("}")
    out.append("")
    out.append("")
    out.append("def grades_for(race: int, job: int, sub_job: int) -> tuple[dict, dict, dict]:")
    out.append('    """(race grades, job grades, subjob grades) for a race field and job ids."""')
    out.append("    race_grades = RACE_GRADES[RACE_NAMES[RACE_OF_FIELD.get(int(race), 0)]]")
    out.append("    job_grades = JOB_GRADES[JOB_OF_ID.get(int(job), \"war\")]")
    out.append("    if int(sub_job):")
    out.append("        sub_grades = JOB_GRADES[JOB_OF_ID.get(int(sub_job), \"war\")]")
    out.append("    else:")
    out.append("        sub_grades = NONE_GRADES")
    out.append("    return race_grades, job_grades, sub_grades")
    out.append("")
    out.append("")
    out.append("def _clamp_level(level: int) -> int:")
    out.append("    return max(0, min(99, int(level)))")
    out.append("")
    out.append("")
    out.append("def _base_stat(race_rank: int, job_rank: int, level: int, sub_rank: int, sub_level: int) -> int:")
    out.append('    """One attribute before gear: the retail round-once pool."""')
    out.append("    level = _clamp_level(level)")
    out.append("    sub_level = _clamp_level(sub_level)")
    out.append("    pooled = (HALF_POINTS[race_rank][level]")
    out.append("              + HALF_POINTS[job_rank][level]")
    out.append("              + HALF_POINTS[sub_rank][sub_level] // 2)")
    out.append("    return pooled // 2 + POINTS_OVER_75[level]")
    out.append("")
    out.append("")
    out.append("def base_stats(race: int, job: int, level: int,")
    out.append("               sub_job: int = 0, sub_level: int = 0) -> dict[str, int]:")
    out.append('    """The seven base attributes for a race field, job id and level pair."""')
    out.append("    race_rank, job_rank, sub_rank = grades_for(race, job, sub_job)")
    out.append("    level = _clamp_level(level)")
    out.append("    sub_level = _clamp_level(sub_level) if int(sub_job) else 0")
    out.append("    return {")
    out.append("        stat: _base_stat(race_rank[stat], job_rank[stat], level,")
    out.append("                         sub_rank[stat], sub_level)")
    out.append("        for stat in ATTRIBUTES")
    out.append("    }")
    out.append("")
    out.append("")
    out.append("def base_hp(race: int, job: int, level: int, sub_job: int = 0,")
    out.append("            sub_level: int = 0) -> int:")
    out.append('    """Retail base HP: race + job whole points, plus half of the subjob\'s job HP."""')
    out.append("    race_rank, job_rank, sub_rank = grades_for(race, job, sub_job)")
    out.append("    level = _clamp_level(level)")
    out.append("    sub_level = _clamp_level(sub_level) if int(sub_job) else 0")
    out.append("    race_index = RACES_INDEX[RACE_NAMES[RACE_OF_FIELD.get(int(race), 0)]]")
    out.append("    return (RACE_HP[race_index][level]")
    out.append("            + JOB_HP[job_rank[\"hp\"]][level]")
    out.append("            + JOB_HP[sub_rank[\"hp\"]][sub_level] // 2)")
    out.append("")
    out.append("")
    out.append("def base_mp(race: int, job: int, level: int, sub_job: int = 0,")
    out.append("            sub_level: int = 0) -> int:")
    out.append('    """Retail base MP.')
    out.append("")
    out.append("    A job with an MP grade brings its racial MP with it.  One without (WAR, BST, ...)")
    out.append("    only gets MP from a subjob that has it, and then the racial part enters at the")
    out.append("    subjob's level, shared down like the subjob itself.")
    out.append('    """')
    out.append("    race_rank, job_rank, sub_rank = grades_for(race, job, sub_job)")
    out.append("    level = _clamp_level(level)")
    out.append("    sub_level = _clamp_level(sub_level) if int(sub_job) else 0")
    out.append("    race_index = RACES_INDEX[RACE_NAMES[RACE_OF_FIELD.get(int(race), 0)]]")
    out.append("    share = SUBJOB_MP_DIVISOR")
    out.append("    job_grade = job_rank[\"mp\"]")
    out.append("    sub_grade = sub_rank[\"mp\"]")
    out.append("    if job_grade > 0:")
    out.append("        total = RACE_MP[race_index][level] + JOB_MP[job_grade][level]")
    out.append("        if sub_grade > 0:")
    out.append("            total += JOB_MP[sub_grade][sub_level] // share")
    out.append("        return total")
    out.append("    if sub_grade > 0:")
    out.append("        return (RACE_MP[race_index][sub_level] // share")
    out.append("                + JOB_MP[sub_grade][sub_level] // share)")
    out.append("    return 0")
    out.append("")

    text = "\n".join(out)
    target = Path(args.output)
    target.write_text(text, encoding="utf-8")
    print("wrote %s (%d lines, %d bytes)" % (target, text.count("\n"), len(text)))

    import importlib.util
    spec = importlib.util.spec_from_file_location("base_stats", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for label, args_ in (("Hume WAR 1", (1, 1, 1, 0, 0)),
                         ("Hume WAR 99", (1, 1, 99, 0, 0)),
                         ("Hume BST 99/BLM 49", (1, 9, 99, 4, 49)),
                         ("Elvaan DRK 99/THF 49", (3, 8, 99, 6, 49)),
                         ("Tarutaru BLM 99", (5, 4, 99, 0, 0))):
        print("%-22s HP %5d  MP %4d  %s" % (label, module.base_hp(*args_),
                                            module.base_mp(*args_), module.base_stats(*args_)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
