#!/usr/bin/env python3
"""Clone one character's save onto another, for two-box testing.

A character's progress is spread over several tables, not just ``characters``:
the job levels live in ``character_jobs``, the worn outfit and its inventory
locations in ``char_equip``/``char_inventory``, and the mule storage, locker,
merits and Home Points in tables of their own.  Granting gear to a second
character by hand leaves the levels, merits or storage behind, so this copies
the whole set in one transaction.

The destination keeps its id, account, name and ``char_id``; everything else --
jobs, level, sub job, exp, gil, merits, Home Points, inventory, storage, locker
and the worn outfit -- is replaced with the source's.  That includes the
source's current job, so the destination can wear the copied outfit instead of
having ``equip_initial`` reject it for the wrong job.

The source may be online: the copy is one SQLite read snapshot.  The destination
must be offline, because a live session would write its own state back on logout.
Relog the destination afterwards.  A lobby hand-off prepared before the copy, or
a parked zone-change session, keeps the old character dict through the next
login; if the client was already at character select, relaunch that client (or
restart the server) instead of only signing back in.

A visible item with ``items.model = 0`` is equipped but invisible.  The copy
repairs every known item from ``tools/item_models.json`` (migration 95's
triggers do the same as the inventory rows go in) and reports any worn or owned
piece that still has no model.  ``--strict-models`` rolls the copy back instead.

    tools/clone_character.py --source Onedough --target Twodough --force --dry-run
    tools/clone_character.py --source Onedough --target Twodough --force --apply
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

# Every table keyed by character_id, with the columns that are copied.  The
# character_id itself is replaced with the destination's id.
CHARACTER_TABLES = {
    "character_jobs": ("job", "level", "master_level"),
    "char_equip": ("kind", "container", "slot", "item_id"),
    "char_inventory": ("container", "slot", "item_id", "quantity", "extra"),
    "char_storage": ("item_id", "quantity", "slip", "stored_at"),
    "char_locker": ("item_id", "quantity", "stored_at"),
    "char_merits": ("merit_id", "upgrades"),
    "char_quests": ("quest_id", "state", "progress", "updated_at"),
    "char_home_points": ("hp_index", "registered_at"),
}

# The progression columns on characters.  Identity (name, race, face, size,
# nation, account) and derived model columns (head/body/...) stay behind.
CHARACTER_COLUMNS = (
    "main_job", "sub_job", "main_level", "sub_level",
    "hp", "mp", "hp_current", "mp_current",
    "exp", "gil", "merit_points", "limit_points", "merit_mode",
    "zone", "pos_x", "pos_y", "pos_z", "rot", "moghouse",
    "home_zone", "home_x", "home_y", "home_z", "home_rot",
    "style_lock", "style_head", "style_body", "style_hands", "style_legs",
    "style_feet", "style_main", "style_sub", "style_ranged",
)


class CloneError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def character(conn: sqlite3.Connection, name: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM characters WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if row is None:
        raise CloneError("no character named %r" % name)
    return row


def is_online(conn: sqlite3.Connection, character_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM game_sessions WHERE character_id = ? AND expires_at > ? LIMIT 1",
        (int(character_id), now_iso()),
    ).fetchone()
    return row is not None


def backup(path: Path) -> Path:
    directory = path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("%s-%s-pre-clone.db" % (path.stem, datetime.now().strftime("%Y%m%d-%H%M%S")))
    source = sqlite3.connect(str(path))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def table_counts(conn: sqlite3.Connection, character_id: int) -> dict[str, int]:
    return {
        table: int(conn.execute(
            "SELECT COUNT(*) FROM %s WHERE character_id = ?" % table, (character_id,)
        ).fetchone()[0])
        for table in CHARACTER_TABLES
    }


def copy_table_rows(conn: sqlite3.Connection, table: str, columns: tuple[str, ...],
                    source_id: int, target_id: int) -> int:
    conn.execute("DELETE FROM %s WHERE character_id = ?" % table, (target_id,))
    names = ", ".join(columns)
    select = conn.execute(
        "SELECT %s FROM %s WHERE character_id = ?" % (names, table), (source_id,)
    ).fetchall()
    if select:
        placeholders = ", ".join("?" for _ in range(len(columns) + 1))
        conn.executemany(
            "INSERT INTO %s (character_id, %s) VALUES (%s)" % (table, names, placeholders),
            [(target_id, *row) for row in select],
        )
    return len(select)


def verify(conn: sqlite3.Connection, table: str, columns: tuple[str, ...],
           source_id: int, target_id: int) -> None:
    names = ", ".join(columns)
    missing = conn.execute(
        "SELECT COUNT(*) FROM (SELECT %s FROM %s WHERE character_id = ? "
        "EXCEPT SELECT %s FROM %s WHERE character_id = ?)" % (names, table, names, table),
        (source_id, target_id),
    ).fetchone()[0]
    extra = conn.execute(
        "SELECT COUNT(*) FROM (SELECT %s FROM %s WHERE character_id = ? "
        "EXCEPT SELECT %s FROM %s WHERE character_id = ?)" % (names, table, names, table),
        (target_id, source_id),
    ).fetchone()[0]
    if missing or extra:
        raise CloneError("%s differs after copy (%d missing, %d extra)" % (table, missing, extra))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="character to copy from")
    parser.add_argument("--target", required=True, help="character to overwrite")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="database file (default: %(default)s)")
    parser.add_argument("--apply", action="store_true",
                        help="write the copy; without this only the plan is printed")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the pre-clone database backup")
    parser.add_argument("--keep-position", action="store_true",
                        help="leave the target's zone, position and Mog House flag alone")
    parser.add_argument("--force", action="store_true",
                        help="copy even when a game session row still says the target is online; "
                             "the server keeps that row for 12 hours after a logout, so a normal "
                             "clone needs this once the client is back at the lobby")
    parser.add_argument("--strict-models", action="store_true",
                        help="roll the copy back if a worn item still has no grap model; without "
                             "this the clone reports the item and continues")
    args = parser.parse_args()

    if not args.db.is_file():
        print("no database at %s" % args.db, file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(args.db), isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        source = character(conn, args.source)
        target = character(conn, args.target)
        source_id, target_id = int(source["id"]), int(target["id"])
        if source_id == target_id:
            raise CloneError("source and target are the same character")
        if is_online(conn, target_id) and not args.force:
            raise CloneError(
                "%s still has an unexpired game session; log it out first (or pass --force "
                "after confirming the client is at the lobby)" % target["name"])

        before = table_counts(conn, target_id)
        print("source: %s (id %d, account %d)" % (source["name"], source_id, source["account_id"]))
        print("target: %s (id %d, account %d)" % (target["name"], target_id, target["account_id"]))
        print("  %-20s %5s -> %5s" % ("table", "now", "after"))
        for table in CHARACTER_TABLES:
            after = int(conn.execute(
                "SELECT COUNT(*) FROM %s WHERE character_id = ?" % table, (source_id,)
            ).fetchone()[0])
            print("  %-20s %5d -> %5d" % (table, before[table], after))
        for column in CHARACTER_COLUMNS:
            left, right = source[column], target[column]
            if left != right:
                print("  %-20s %r -> %r" % (column, right, left))
        if not args.apply:
            print("dry run: pass --apply to write")
            return 0

        saved = None
        if not args.no_backup:
            saved = backup(args.db)
            print("backup: %s" % saved)

        columns = [column for column in CHARACTER_COLUMNS if not (
            args.keep_position and column in ("zone", "pos_x", "pos_y", "pos_z", "rot", "moghouse")
        )]
        assignments = ", ".join("%s = ?" % column for column in columns)
        values = [source[column] for column in columns]

        conn.execute("BEGIN IMMEDIATE")
        try:
            for table, table_columns in CHARACTER_TABLES.items():
                copy_table_rows(conn, table, table_columns, source_id, target_id)
            conn.execute(
                "UPDATE characters SET %s, updated_at = ? WHERE id = ?" % assignments,
                (*values, now_iso(), target_id),
            )
            for table, table_columns in CHARACTER_TABLES.items():
                verify(conn, table, table_columns, source_id, target_id)
            # Migration 95 installs triggers that do this as the inventory rows go in;
            # calling it here also covers a database that has not run that migration yet.
            repaired = item_models.repair(conn)
            missing_worn = item_models.missing(conn, target_id, equipped=True)
            if missing_worn and args.strict_models:
                names = ", ".join(item["name"] for item in missing_worn)
                raise CloneError(
                    "the copy would leave worn gear without a model: %s; fill it in "
                    "tools/item_models.json (or drop --strict-models)" % names)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        missing_owned = item_models.missing(conn, target_id, equipped=False)
        print("repaired %d item model(s)" % repaired)
        if missing_worn:
            print("warning: worn gear with no model: %s"
                  % ", ".join(item["name"] for item in missing_worn), file=sys.stderr)
        if missing_owned:
            print("warning: owned gear with no model: %s"
                  % ", ".join(item["name"] for item in missing_owned[:12])
                  + (" ..." if len(missing_owned) > 12 else ""), file=sys.stderr)
        print("copied %s -> %s" % (source["name"], target["name"]))
        return 0
    except CloneError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
