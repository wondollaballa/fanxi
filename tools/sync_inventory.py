#!/usr/bin/env python3
"""Give several mules the same items as one source character.

This is the inventory-only sibling of ``tools/clone_character.py``.  It copies
the source's bags and wardrobes (``char_inventory``), storage slips
(``char_storage``) and hidden locker (``char_locker``), but leaves every
target's jobs, levels, exp, gil, merits, quests, Home Points, currencies and
purchase history alone.

Each target's gil row is kept from its own ``characters.gil`` value; the
source's gil row is never copied.  Worn equipment is cleared because the old
``char_equip`` container/slot values point into an inventory that no longer
exists.  The appearance model/style columns are cleared with it so a mule does
not draw a phantom outfit; the server rebuilds the models when the player
equips from the copied collection.

Targets must be logged out.  A ``game_sessions`` row can survive for twelve
hours after a logout and is not proof of a live client, so this tool does not
try to guess: relog (or relaunch a client sitting at character select)
afterwards.

    tools/sync_inventory.py --source Onedough \
        --targets Twodough,Threedough,Fourdough,Fivedough,Sixdough
    tools/sync_inventory.py --source Onedough --targets Twodough --apply
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import item_models

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "fanxi.db"

INVENTORY_COLUMNS = ("container", "slot", "item_id", "quantity", "extra", "dropped_at")
STORAGE_COLUMNS = ("item_id", "quantity", "slip", "stored_at")
LOCKER_COLUMNS = ("item_id", "extra", "quantity", "stored_at")
APPEARANCE_COLUMNS = (
    "head", "body", "hands", "legs", "feet", "main", "sub", "ranged",
    "style_lock", "style_head", "style_body", "style_hands", "style_legs",
    "style_feet", "style_main", "style_sub", "style_ranged",
)
GIL_ITEM = 65535


class SyncError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def character(conn: sqlite3.Connection, name: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM characters WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if row is None:
        raise SyncError("no character named %r" % name)
    return row


def backup(path: Path) -> Path:
    directory = path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("%s-%s-pre-inventory-sync.db"
                          % (path.stem, datetime.now().strftime("%Y%m%d-%H%M%S")))
    source = sqlite3.connect(str(path))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def counts(conn: sqlite3.Connection, character_id: int) -> dict[str, int]:
    return {
        table: int(conn.execute(
            "SELECT COUNT(*) FROM %s WHERE character_id = ?" % table, (character_id,)
        ).fetchone()[0])
        for table in ("char_inventory", "char_storage", "char_locker", "char_equip")
    }


def copy_rows(conn: sqlite3.Connection, table: str, columns: tuple[str, ...],
              source_id: int, target_id: int, where: str = "") -> int:
    conn.execute("DELETE FROM %s WHERE character_id = ?" % table, (target_id,))
    names = ", ".join(columns)
    rows = conn.execute(
        "SELECT %s FROM %s WHERE character_id = ?%s" % (names, table, where),
        (source_id,),
    ).fetchall()
    if rows:
        placeholders = ", ".join("?" for _ in range(len(columns) + 1))
        conn.executemany(
            "INSERT INTO %s (character_id, %s) VALUES (%s)" % (table, names, placeholders),
            [(target_id, *row) for row in rows],
        )
    return len(rows)


def verify_items(conn: sqlite3.Connection, source_id: int, target_id: int) -> None:
    checks = (
        ("char_inventory", "container, slot, item_id, quantity, extra",
         "item_id <> %d" % GIL_ITEM),
        ("char_storage", "item_id, quantity, slip", ""),
        ("char_locker", "item_id, extra, quantity", ""),
    )
    for table, columns, where in checks:
        suffix = (" AND " + where) if where else ""
        missing = conn.execute(
            "SELECT COUNT(*) FROM (SELECT %s FROM %s WHERE character_id = ?%s "
            "EXCEPT SELECT %s FROM %s WHERE character_id = ?%s)"
            % (columns, table, suffix, columns, table, suffix),
            (source_id, target_id),
        ).fetchone()[0]
        extra = conn.execute(
            "SELECT COUNT(*) FROM (SELECT %s FROM %s WHERE character_id = ?%s "
            "EXCEPT SELECT %s FROM %s WHERE character_id = ?%s)"
            % (columns, table, suffix, columns, table, suffix),
            (target_id, source_id),
        ).fetchone()[0]
        if missing or extra:
            raise SyncError("%s differs after copy (%d missing, %d extra)"
                            % (table, missing, extra))
    equipped = conn.execute(
        "SELECT COUNT(*) FROM char_equip WHERE character_id = ?", (target_id,)
    ).fetchone()[0]
    if equipped:
        raise SyncError("target still has equipped rows")


def sync_target(conn: sqlite3.Connection, source: sqlite3.Row, target: sqlite3.Row,
                *, keep_gil: bool = True) -> None:
    source_id, target_id = int(source["id"]), int(target["id"])
    if source_id == target_id:
        raise SyncError("source and target are the same character")
    gil = int(target["gil"] or 0) if keep_gil else int(source["gil"] or 0)

    copy_rows(conn, "char_inventory", INVENTORY_COLUMNS, source_id, target_id,
              where=" AND item_id <> %d" % GIL_ITEM)
    # Slot 0 is the client's gil row.  Put the target's own wallet back so a
    # copied inventory does not silently change the character's money.
    conn.execute(
        "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity, extra) "
        "VALUES (?, 0, 0, ?, ?, X'') "
        "ON CONFLICT(character_id, container, slot) DO UPDATE SET "
        "item_id = excluded.item_id, quantity = excluded.quantity, extra = excluded.extra",
        (target_id, GIL_ITEM, gil),
    )
    copy_rows(conn, "char_storage", STORAGE_COLUMNS, source_id, target_id)
    copy_rows(conn, "char_locker", LOCKER_COLUMNS, source_id, target_id)
    conn.execute("DELETE FROM char_equip WHERE character_id = ?", (target_id,))
    assignments = ", ".join("%s = 0" % column for column in APPEARANCE_COLUMNS)
    conn.execute(
        "UPDATE characters SET %s, updated_at = ? WHERE id = ?" % assignments,
        (now_iso(), target_id),
    )
    if not keep_gil:
        conn.execute("UPDATE characters SET gil = ? WHERE id = ?", (gil, target_id))
    verify_items(conn, source_id, target_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="character to copy items from")
    parser.add_argument("--targets", required=True,
                        help="comma-separated character names to overwrite")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="database file (default: %(default)s)")
    parser.add_argument("--apply", action="store_true",
                        help="write the copy; without this only the plan is printed")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the pre-sync database backup")
    parser.add_argument("--source-gil", action="store_true",
                        help="also replace the target's gil with the source's "
                             "(default: keep each target's own gil)")
    args = parser.parse_args()

    if not args.db.is_file():
        print("no database at %s" % args.db, file=sys.stderr)
        return 2
    names = [name.strip() for name in args.targets.split(",") if name.strip()]
    if not names:
        print("no target names given", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(args.db), isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        source = character(conn, args.source)
        targets = [character(conn, name) for name in names]
        source_id = int(source["id"])
        print("source: %s (id %d)" % (source["name"], source_id))
        for target in targets:
            before = counts(conn, int(target["id"]))
            after = counts(conn, source_id)
            print("target: %s (id %d) gil %d" % (
                target["name"], int(target["id"]), int(target["gil"] or 0)))
            for table in ("char_inventory", "char_storage", "char_locker"):
                print("  %-16s %5d -> %5d" % (table, before[table], after[table]))
            print("  %-16s %5d ->     0" % ("char_equip", before["char_equip"]))
        if not args.apply:
            print("dry run: pass --apply to write")
            return 0

        saved = None
        if not args.no_backup:
            saved = backup(args.db)
            print("backup: %s" % saved)

        conn.execute("BEGIN IMMEDIATE")
        try:
            for target in targets:
                sync_target(conn, source, target, keep_gil=not args.source_gil)
            repaired = item_models.repair(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        print("repaired %d item model(s)" % repaired)
        print("synced %d target(s) from %s" % (len(targets), source["name"]))
        return 0
    except SyncError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
