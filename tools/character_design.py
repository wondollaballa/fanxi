#!/usr/bin/env python3
"""Change one character's race/face/hair colour/size in the database.

Use this when the game is not running, or when you want to script a change:

    tools/character_design.py --character Onedough --race hume --variant 8 --dry-run
    tools/character_design.py --character Onedough --race hume --face 2 --hair a --size m --apply
    tools/character_design.py --character Onedough --race mithra --random --apply
    tools/character_design.py --list hume

The in-game form is faster when the character is online::

    !character model hume 8          -- Face 2, Hair A, Medium
    !character model mithra random   -- random face/hair/size
    !character model random          -- random race too

Variants are numbered 1-48 per race: size fastest, then hair A/B, then face 1-8.
A change here is only read when the client next logs in or zones; the zone
command also repaints the live model immediately.
"""
from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "fanxi.db"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import design  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup(path: Path) -> Path:
    directory = path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("%s-%s-pre-design.db" % (
        path.stem, datetime.now().strftime("%Y%m%d-%H%M%S")))
    source = sqlite3.connect(str(path))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def character_row(conn: sqlite3.Connection, name: str | None, character_id: int | None):
    if character_id is not None:
        row = conn.execute("SELECT * FROM characters WHERE id = ?", (int(character_id),)).fetchone()
    elif name:
        row = conn.execute(
            "SELECT * FROM characters WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
    else:
        raise SystemExit("choose --character NAME or --id ID")
    if row is None:
        raise SystemExit("no character named %r" % (name if name else character_id))
    return row


def is_online(conn: sqlite3.Connection, character_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM game_sessions WHERE character_id = ? AND expires_at > ? LIMIT 1",
        (int(character_id), now_iso()),
    ).fetchone()
    return row is not None


def print_design(title: str, blueprint: dict) -> None:
    print("%s: %s" % (title, blueprint["label"]))
    print("  race %d  face %d  hair %s  size %s  variant %d/%d  look %d" % (
        blueprint["race"], blueprint["face"], blueprint["hair_label"][-1],
        blueprint["size_label"], blueprint["variant"], blueprint["variants"],
        blueprint["raw_face"]))


def list_variants(race_value: str | None) -> None:
    if race_value:
        chosen = [design.race(race_value)]
    else:
        chosen = list(design.RACES)
    for race in chosen:
        print("\n%s — %d designs" % (race.label, design.VARIANTS_PER_RACE))
        for blueprint in design.variants(race):
            print("  %2d  %-6s %-6s %-6s  look %2d" % (
                blueprint["variant"], blueprint["face_label"],
                blueprint["hair_label"], blueprint["size_label"], blueprint["raw_face"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database")
    who = parser.add_mutually_exclusive_group()
    who.add_argument("--character", help="character name (case-insensitive)")
    who.add_argument("--id", type=int, help="database character id")
    parser.add_argument("--race", help="hume, humef, elvaan, elvaanf, tarutaru, "
                                       "tarutaruf, mithra or galka")
    parser.add_argument("--face", type=int, help="face 1-8")
    parser.add_argument("--hair", help="hair colour A or B")
    parser.add_argument("--size", help="small, medium or large")
    parser.add_argument("--variant", help="design number 1-48, or 'random'")
    parser.add_argument("--random", action="store_true",
                        help="randomise face, hair and size (and race if --race is omitted)")
    parser.add_argument("--list", nargs="?", const="", metavar="RACE",
                        help="list the 48 designs for one race, or every race")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="show the change only")
    action.add_argument("--apply", action="store_true", help="write the change")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the automatic data/backups copy")
    args = parser.parse_args(argv)

    if args.list is not None:
        list_variants(args.list or None)
        return 0

    if not args.dry_run and not args.apply:
        parser.error("choose --dry-run or --apply")
    if not args.db.exists():
        raise SystemExit("no database at %s" % args.db)

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        row = character_row(conn, args.character, args.id)
        columns = {item[1] for item in conn.execute("PRAGMA table_info(characters)")}
        current = design.from_row(row)
        print_design("Current", current)

        if args.random:
            blueprint = design.random_design(args.race,
                                             random.SystemRandom())
        elif args.variant:
            if str(args.variant).casefold() == "random":
                chosen = args.race or current["race"]
                blueprint = design.random_design(chosen, random.SystemRandom())
            else:
                chosen = args.race or current["race"]
                blueprint = design.design_from_variant(chosen, args.variant)
        else:
            if args.race is None and args.face is None and args.hair is None and args.size is None:
                parser.error("choose --race/--face/--hair/--size, --variant or --random")
            blueprint = design.design(
                args.race or current["race"],
                args.face if args.face is not None else current["face"],
                args.hair if args.hair is not None else current["hair"],
                args.size if args.size is not None else current["size"],
            )

        print_design("New", blueprint)
        online = is_online(conn, int(row["id"]))
        if online:
            print("\nThis character has a live session. The database %s, but" % (
                "would be updated" if args.dry_run else "is updated now"))
            print("the client keeps the old model until it zones or logs in.  For an")
            print("immediate change use: !character model %s %d" % (
                {1: "hume", 2: "humef", 3: "elvaan", 4: "elvaanf",
                 5: "tarutaru", 6: "tarutaruf", 7: "mithra", 8: "galka"}[blueprint["race"]],
                blueprint["variant"]))
        if args.dry_run:
            print("\nDry run: no rows changed.")
            return 0
        if not args.no_backup:
            path = backup(args.db)
            print("\nBackup: %s" % path)

        conn.execute("BEGIN IMMEDIATE")
        if "hair" in columns:
            conn.execute(
                "UPDATE characters SET race = ?, face = ?, hair = ?, size = ?, updated_at = ? "
                "WHERE id = ?",
                (blueprint["race"], blueprint["face"], blueprint["hair"],
                 blueprint["size"], now_iso(), int(row["id"])),
            )
        else:
            # Pre-migration database: write the combined look byte the old schema used.
            conn.execute(
                "UPDATE characters SET race = ?, face = ?, size = ?, updated_at = ? WHERE id = ?",
                (blueprint["race"], blueprint["raw_face"], blueprint["size"],
                 now_iso(), int(row["id"])),
            )
        conn.commit()
        print("\nSaved. %s" % (
            "The client will pick it up on its next login or zone." if online
            else "Log in to see the new design."))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
