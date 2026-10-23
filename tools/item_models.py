#!/usr/bin/env python3
"""Repair the grap model of the gear a character owns or wears.

``items.model`` is what the client draws for a visible slot; a zero (or a
LandSandBoat MId) renders the previous/default look, so the piece is equipped
but invisible.  ``tools/gen_item_models.py`` writes the catalogue in
``tools/item_models.json`` and migration 95 installs the same table plus
triggers for newly added gear; this module is the runtime side used by
``clone_character.py`` and by hand after a grant.

    tools/item_models.py --db data/fanxi.db --character Twodough
    tools/item_models.py --db data/fanxi.db --apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "fanxi.db"
DEFAULT_JSON = ROOT / "tools" / "item_models.json"
VISIBLE = ("head", "body", "hands", "legs", "feet", "main", "sub", "ranged")


def catalog(path: Path = DEFAULT_JSON) -> dict[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(item_id): int(model) for item_id, model in data.items()}


def repair(conn: sqlite3.Connection, path: Path = DEFAULT_JSON) -> int:
    """Set every known item to its catalogue model; return how many rows changed."""
    updated = 0
    for item_id, model in catalog(path).items():
        cursor = conn.execute(
            "UPDATE items SET model = ? WHERE item_id = ? AND model IS NOT ?",
            (model, item_id, model),
        )
        updated += cursor.rowcount
    return updated


def missing(conn: sqlite3.Connection, character_id: int, *, equipped: bool) -> list[dict]:
    """Visible items the character wears (or owns) that still have no model."""
    table = "char_equip" if equipped else "char_inventory"
    rows = conn.execute(
        "SELECT DISTINCT i.item_id, i.name, i.equip_slot FROM %s row "
        "JOIN items i ON i.item_id = row.item_id "
        "WHERE row.character_id = ? AND i.equip_slot IN (%s) AND i.model = 0 "
        "AND NOT (i.equip_slot = 'sub' AND i.name LIKE '%%Grip%%') "
        "ORDER BY i.name" % (table, ",".join("?" for _ in VISIBLE)),
        (int(character_id), *VISIBLE),
    ).fetchall()
    return [dict(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--character", help="report this character's missing gear too")
    parser.add_argument("--apply", action="store_true", help="write the catalogue models")
    args = parser.parse_args()
    if not args.db.is_file():
        print("no database at %s" % args.db, file=sys.stderr)
        return 2
    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        if args.apply:
            print("updated %d item(s)' model" % repair(conn, args.catalog))
            conn.commit()
        if args.character:
            row = conn.execute(
                "SELECT id FROM characters WHERE name = ? COLLATE NOCASE", (args.character,)
            ).fetchone()
            if row is None:
                print("no character named %r" % args.character, file=sys.stderr)
                return 2
            for label, equipped in (("worn", True), ("owned", False)):
                missing_rows = missing(conn, int(row["id"]), equipped=equipped)
                print("%s: %d visible item(s) without a model" % (label, len(missing_rows)))
                for item in missing_rows:
                    print("  %6d %-28s %s" % (item["item_id"], item["name"], item["equip_slot"]))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
