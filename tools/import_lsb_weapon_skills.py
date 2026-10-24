#!/usr/bin/env python3
"""Import LandSandBoat's weapon-skill scripts into ``data/weapon_skills.json``.

Every file in ``scripts/actions/weaponskills`` is a small Lua function that sets the
skill's fTP anchors, secondary-attribute modifiers (WSC), hit count and the
"varies with TP" tables.  The engine used to ignore all of that and give every skill a
single ``1.5 + 1.5 * TP / 3000`` curve with no WSC, which made Blade: Metsu (retail
fTP 5.0 and 80% DEX) do roughly twice an auto-attack instead of five times the base.

The importer reads the file names, maps them to the ``weapon_skills`` rows in the
database, and keeps the **Adoulin** branch (``USE_ADOULIN_WEAPON_SKILL_CHANGES``).
Fanxi is a level 119 server, so that is the branch retail uses for these values.

    tools/import_lsb_weapon_skills.py --source /tmp/lsb/scripts/actions/weaponskills

The output is deterministic, so re-running it after a checkout update produces a
reviewable diff.  A few newer Prime weapon skills have no player script in
LandSandBoat; ``EXTRA`` below carries the values BG-wiki publishes for them.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Weapon skills LandSandBoat only scripts as monster skills (the Prime weapons) or not
# at all.  Values from BG-wiki's weapon-skill pages.  The 2000 TP anchor of Disasters
# is not published; 15.25 continues its 1000 -> 2000 step.  Dagda publishes neither its
# fTP row nor its stat modifiers, so it is deliberately left to the generic fallback.
EXTRA = {
    62: {"name": "Fimbulvetr", "ftp": [3.3, 6.6, 9.9],
         "wsc": {"str": 0.6, "vit": 0.6}},
    78: {"name": "Blitz", "ftp": [1.5, 7.0, 12.5], "hits": 5,
         "wsc": {"str": 0.32, "dex": 0.32}},
    94: {"name": "Disaster", "ftp": [3.05, 9.15, 15.25],
         "wsc": {"str": 0.6, "vit": 0.6}},
    110: {"name": "Origin", "ftp": [3.0, 6.0, 9.0],
          "wsc": {"str": 0.6, "int": 0.6}},
    126: {"name": "Diarmuid", "ftp": [2.17, 5.36, 8.55], "hits": 2,
          "wsc": {"str": 0.55, "vit": 0.55}},
    142: {"name": "Zesho Meppo", "ftp": [4.0, 11.3575, 18.715], "hits": 4,
          "wsc": {"dex": 0.25, "agi": 0.25}, "multi_hit_ftp": True},
    159: {"name": "Tachi: Mumei", "ftp": [3.66, 7.33, 11.0],
          "wsc": {"str": 0.5, "dex": 0.5}},
    204: {"name": "Sarv", "ftp": [2.75, 5.5, 8.25],
          "wsc": {"str": 0.65, "agi": 0.65}},
    222: {"name": "Terminus", "ftp": [2.5, 5.0, 7.5],
          "wsc": {"dex": 0.7, "agi": 0.7}},
    233: {"name": "Imperator", "ftp": [6.6, 13.35, 20.1],
          "wsc": {"dex": 0.27, "mnd": 0.27}},
    235: {"name": "Oshala", "ftp": [3.95, 7.89, 11.84],
          "wsc": {"mnd": 0.45, "int": 0.45}},
}

ASSIGN = re.compile(r"params\.([A-Za-z_0-9]+)\s*=\s*")
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
TABLE = re.compile(r"\{([^{}]*)\}")
OPENERS = re.compile(r"\b(if|for|while|function)\b")
END = re.compile(r"\bend\b")


def slug(name: str) -> str:
    """The LandSandBoat file name for a weapon-skill name."""
    text = name.lower().replace(":", " ")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def without_comment(line: str) -> str:
    index = line.find("--")
    return line if index < 0 else line[:index]


def adoulin_block(lines: list[str]) -> tuple[int, int] | None:
    """The inner line range of the ``USE_ADOULIN_WEAPON_SKILL_CHANGES`` branch."""
    start = None
    for index, line in enumerate(lines):
        if "USE_ADOULIN_WEAPON_SKILL_CHANGES" in line and re.search(r"\bif\b", line):
            start = index
            break
    if start is None:
        return None
    depth = 0
    for index in range(start, len(lines)):
        body = without_comment(lines[index])
        depth += len(OPENERS.findall(body)) - len(END.findall(body))
        if index > start and depth <= 0:
            return start + 1, index
    return None


def assignment_value(match: re.Match[str], line: str,
                     following: list[re.Match[str]]) -> str:
    """The text assigned by ``match``, cut at the next ``params.`` on the same line."""
    end = len(line)
    for later in following:
        if later.start() > match.start():
            end = later.start()
            break
    value = line[match.end():end].strip()
    table = TABLE.search(value)
    return "{%s}" % table.group(1) if table else value


def parse_assignments(text: str) -> dict[str, str]:
    """The last value assigned to each ``params.`` key in this chunk."""
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = without_comment(raw)
        matches = list(ASSIGN.finditer(line))
        for index, match in enumerate(matches):
            result[match.group(1)] = assignment_value(match, line, matches[index + 1:])
    return result


def evaluate(expression: str) -> float:
    """A number, a simple fraction, or the leading literal of a merit expression."""
    expression = expression.strip()
    if not expression:
        return 0.0
    number = NUMBER.search(expression)
    if number is None:
        return 0.0
    if "getMerit" in expression:
        # ``0.7 + player:getMerit(...) * 0.03`` keeps 0.7 at zero merits; a bare
        # ``player:getMerit(...) * 0.17`` is zero until the merit is bought.
        base = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*\+", expression)
        return float(base.group(1)) if base else 0.0
    if re.fullmatch(r"-?\d+(?:\.\d+)?", expression):
        return float(expression)
    # LandSandBoat writes some fTP values as fractions (1474 / 256).  Evaluate only
    # arithmetic on literals; a merit lookup keeps its leading base coefficient.
    try:
        tree = ast.parse(expression, mode="eval")
        return float(_eval_arithmetic(tree.body))
    except Exception:
        return float(number.group(0))


def _eval_arithmetic(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_arithmetic(node.operand)
    if isinstance(node, ast.BinOp):
        left, right = _eval_arithmetic(node.left), _eval_arithmetic(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise ValueError("not arithmetic")


def table_values(value: str) -> tuple[float, ...]:
    match = TABLE.search(value)
    if match is None:
        return ()
    return tuple(evaluate(part) for part in match.group(1).split(",") if part.strip())


def parse_script(path: Path) -> dict:
    """One weapon-skill file -> its damage parameters."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    block = adoulin_block(lines)
    if block is None:
        parameters = parse_assignments(text)
    else:
        start, end = block
        # Assignments outside the Adoulin branch are the base values; some scripts put
        # one after the branch (Split Shot's ignoredDefense), so include both sides.
        parameters = parse_assignments("\n".join(lines[:start] + lines[end:]))
        parameters.update(parse_assignments("\n".join(lines[start:end])))

    row: dict = {}
    if "ftpMod" in parameters:
        ftp = table_values(parameters["ftpMod"])
        if len(ftp) >= 3:
            row["ftp"] = list(ftp[:3])
    if "numHits" in parameters:
        row["hits"] = max(1, int(evaluate(parameters["numHits"])))
    wsc = {}
    for stat in ("str", "dex", "vit", "agi", "int", "mnd", "chr"):
        key = stat + "_wsc"
        if key in parameters:
            wsc[stat] = evaluate(parameters[key])
    if wsc:
        row["wsc"] = wsc
    for key, name in (("critVaries", "crit_varies"), ("atkVaries", "attack_varies"),
                      ("ignoredDefense", "ignored_defense")):
        if key in parameters:
            values = table_values(parameters[key])
            if len(values) >= 3:
                row[name] = list(values[:3])
    if "multiHitfTP" in parameters and "true" in parameters["multiHitfTP"].lower():
        row["multi_hit_ftp"] = True
    if "hybridWS" in parameters and "true" in parameters["hybridWS"].lower():
        row["hybrid"] = True
    if "doMagicWeaponskill" in text:
        row["magic"] = True
    return row


def weapon_skill_rows(database: Path) -> dict[str, tuple[int, str, int]]:
    connection = sqlite3.connect(str(database))
    try:
        rows = connection.execute(
            "SELECT id, name, skill FROM weapon_skills").fetchall()
    finally:
        connection.close()
    return {slug(name): (int(ws_id), name, int(skill)) for ws_id, name, skill in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="/tmp/lsb/scripts/actions/weaponskills",
                        help="LandSandBoat scripts/actions/weaponskills directory")
    parser.add_argument("--db", default=str(ROOT / "data" / "fanxi.db"),
                        help="database holding the weapon_skills rows")
    parser.add_argument("--out", default=str(ROOT / "data" / "weapon_skills.json"))
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_dir():
        raise SystemExit("no weapon-skill scripts at %s" % source)
    by_name = weapon_skill_rows(Path(args.db))

    table: dict[str, dict] = {}
    missing: list[str] = []
    for path in sorted(source.glob("*.lua")):
        entry = by_name.get(path.stem)
        if entry is None:
            continue
        ws_id, name, skill = entry
        row = parse_script(path)
        if not row:
            continue
        row.update(id=ws_id, name=name, skill=skill)
        table[str(ws_id)] = row

    for ws_id, row in EXTRA.items():
        if str(ws_id) in table:
            continue
        known = by_name.get(slug(row["name"]))
        if known is None:
            known = (ws_id, row["name"], 0)
        table[str(ws_id)] = {**row, "id": int(known[0]), "name": known[1],
                             "skill": int(known[2])}

    for slug_name, (ws_id, name, _skill) in sorted(by_name.items()):
        if str(ws_id) not in table:
            missing.append(name)

    document = {
        "format": "fanxi-weapon-skills/1",
        "source": ("LandSandBoat scripts/actions/weaponskills (Adoulin branch) "
                   "and the BG-wiki Prime weapon-skill pages"),
        "weapon_skills": table,
    }
    target = Path(args.out)
    target.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    print("wrote %s" % target)
    print("  weapon skills:  %d" % len(table))
    print("  no damage data: %s" % (", ".join(sorted(missing)) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
