#!/usr/bin/env python3
"""Import weapon-skill skillchain properties into ``data/skillchains.json``.

LandSandBoat stores the three resonance properties of every weapon skill in
``sql/weapon_skills.sql`` (``primary_sc``, ``secondary_sc``, ``tertiary_sc``).  The
values are ``SC_*`` ids from ``data/enums/skillchain_type.yaml``:

    0 none, 1 transfixion, 2 compression, 3 liquefaction, 4 scission,
    5 reverberation, 6 detonation, 7 induration, 8 impaction, 9 gravitation,
    10 distortion, 11 fusion, 12 fragmentation, 13 light, 14 darkness,
    15 light II, 16 darkness II

A few Prime weapon skills are commented out or absent in the reference SQL because
LandSandBoat only scripts them as monster skills; Exudation is also absent.  ``PRIME``
below carries the Skillchain line BG-wiki publishes for those pages.  The ids match
Fanxi's ``data/weapon_skills.json`` (which uses the client's weapon-skill ids).

    tools/import_lsb_skillchains.py --sql /tmp/lsb/sql/weapon_skills.sql

The output is deterministic, so a checkout update produces a reviewable diff.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The reference SQL has these skills commented out; BG-wiki's Skillchain lines.
# (id, name, (primary, secondary, tertiary))
PRIME = {
    62: ("Fimbulvetr", (6, 2, 10)),          # Detonation / Compression / Distortion
    78: ("Blitz", (3, 8, 12)),               # Liquefaction / Impaction / Fragmentation
    94: ("Disaster", (1, 4, 9)),             # Transfixion / Scission / Gravitation
    110: ("Origin", (7, 5, 11)),             # Induration / Reverberation / Fusion
    126: ("Diarmuid", (1, 4, 9)),            # Transfixion / Scission / Gravitation
    142: ("Zesho Meppo", (7, 5, 11)),        # Induration / Reverberation / Fusion
    159: ("Tachi: Mumei", (6, 2, 10)),       # Detonation / Compression / Distortion
    204: ("Sarv", (1, 4, 9)),                # Transfixion / Scission / Gravitation
    222: ("Terminus", (7, 5, 11)),           # Induration / Reverberation / Fusion
    231: ("Maru Kala", (6, 2, 10)),          # Detonation / Compression / Distortion
    232: ("Ruthless Stroke", (3, 8, 12)),    # Liquefaction / Impaction / Fragmentation
    233: ("Imperator", (6, 2, 10)),          # Detonation / Compression / Distortion
    235: ("Oshala", (7, 5, 11)),             # Induration / Reverberation / Fusion
    175: ("Exudation", (14, 12, 0)),          # Darkness / Fragmentation
}

# id, name, jobs blob, type, skilllevel, element, animation, animationTime,
# range, aoe, radius, primary_sc, secondary_sc, tertiary_sc, main_only, unlock_id.
ROW = re.compile(
    r"INSERT INTO `weapon_skills` VALUES \((\d+),'([^']*)',0x[0-9A-Fa-f]+,"
    r"(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),"
    r"(\d+),(\d+)\);")


def parse_sql(path: Path) -> dict[int, tuple[int, int, int]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[int, tuple[int, int, int]] = {}
    for match in ROW.finditer(text):
        ws_id = int(match.group(1))
        # group 11 = primary_sc, 12 = secondary_sc, 13 = tertiary_sc.
        out[ws_id] = (int(match.group(11)), int(match.group(12)),
                      int(match.group(13)))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql", default="/tmp/lsb/sql/weapon_skills.sql",
                        help="LandSandBoat sql/weapon_skills.sql")
    parser.add_argument("--weapon-skills", default=str(ROOT / "data" / "weapon_skills.json"),
                        help="the existing weapon-skill table (ids and names)")
    parser.add_argument("--out", default=str(ROOT / "data" / "skillchains.json"),
                        help="the output JSON")
    args = parser.parse_args()

    sql_path = Path(args.sql)
    if not sql_path.is_file():
        raise SystemExit("no weapon-skill SQL at %s" % sql_path)
    document = json.loads(Path(args.weapon_skills).read_text(encoding="utf-8"))
    known = {int(key): row.get("name", "") for key, row in document["weapon_skills"].items()}

    properties = parse_sql(sql_path)
    missing: list[str] = []
    for ws_id, (_name, sc) in PRIME.items():
        properties[int(ws_id)] = tuple(int(value) for value in sc)

    table: dict[str, list[int]] = {}
    for ws_id in sorted(known):
        if ws_id not in properties:
            missing.append("%d %s" % (ws_id, known[ws_id]))
            continue
        table[str(ws_id)] = list(properties[ws_id])

    output = {
        "format": "fanxi-skillchains/1",
        "source": ("LandSandBoat sql/weapon_skills.sql (primary_sc, secondary_sc, "
                   "tertiary_sc) and BG-wiki for the Prime skills missing from that "
                   "file"),
        "weapon_skills": table,
    }
    target = Path(args.out)
    target.write_text(json.dumps(output, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("wrote %s" % target)
    print("  weapon skills with skillchain properties: %d" % len(table))
    print("  missing: %s" % (", ".join(sorted(missing)) or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
