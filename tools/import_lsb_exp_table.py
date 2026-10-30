"""Convert LandSandBoat's base-experience table into Fanxi's ``data/exp_table.json``.

The table is the server-side EXP curve behind the client's Check line: base EXP is
indexed by ``mob level - player level`` (row) and the player's five-level bracket
(column).  LandSandBoat publishes it in ``scripts/data/experience_table.lua``,
traceable to the Japanese ffo.jp wiki.  This tool reads only the numbers and writes
Fanxi's own JSON schema; no LandSandBoat Lua, comments or names are copied.

Usage::

    python3 tools/import_lsb_exp_table.py --source /tmp/lsb/scripts/data/experience_table.lua
    python3 tools/import_lsb_exp_table.py --source ... --check   # fail if the file drifts

``--check`` is what the test suite uses, so a changed upstream table is noticed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "exp_table.json"

# The table is keyed by the level difference and has one column per five-level bracket.
FIRST_DIFFERENCE = -44
LAST_DIFFERENCE = 15
BRACKET_SIZE = 5
BRACKETS = 20

_ROW = re.compile(r"\[\s*(-?\d+)\s*\]\s*=\s*\{([^}]*)\}")


def parse(source: Path) -> dict:
    text = source.read_text(encoding="utf-8")
    rows = {}
    for match in _ROW.finditer(text):
        values = [int(value) for value in match.group(2).split(",") if value.strip()]
        rows[int(match.group(1))] = values
    expected = list(range(FIRST_DIFFERENCE, LAST_DIFFERENCE + 1))
    if sorted(rows) != expected:
        raise SystemExit("source has level differences %s, expected %d..%d"
                         % (sorted(rows)[:3] + sorted(rows)[-3:],
                            FIRST_DIFFERENCE, LAST_DIFFERENCE))
    for difference in expected:
        if len(rows[difference]) != BRACKETS:
            raise SystemExit("difference %+d has %d brackets, expected %d"
                             % (difference, len(rows[difference]), BRACKETS))
    return {
        "base_exp": {
            "comment": "Base EXP by mob level - player level and the player's five-level "
                       "bracket; the row is imported, the schema and code are Fanxi's.",
            "source": "LandSandBoat/server scripts/data/experience_table.lua (ffo.jp); "
                      "numeric values only",
            "first_difference": FIRST_DIFFERENCE,
            "last_difference": LAST_DIFFERENCE,
            "bracket_size": BRACKET_SIZE,
            "brackets": BRACKETS,
            "rows": [rows[difference] for difference in expected],
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, type=Path,
                        help="LandSandBoat's scripts/data/experience_table.lua")
    parser.add_argument("--check", action="store_true",
                        help="verify data/exp_table.json instead of writing it")
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args(argv)

    document = parse(args.source)
    text = json.dumps(document, indent=1) + "\n"
    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError as exc:
            print("cannot read %s: %s" % (args.output, exc), file=sys.stderr)
            return 2
        if current != text:
            print("%s is out of date; re-run without --check" % args.output, file=sys.stderr)
            return 1
        print("%s is up to date" % args.output)
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print("wrote %s (%d rows x %d brackets)" % (args.output, LAST_DIFFERENCE - FIRST_DIFFERENCE + 1,
                                                BRACKETS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
