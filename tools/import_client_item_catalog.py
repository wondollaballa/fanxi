#!/usr/bin/env python3
"""Import the client's full equipment catalogue into a Fanxi migration.

The server's `items` table started as a hand-curated set of the pieces the server
actually used.  That made the launcher's Armory miss most of the game: a search for
an ordinary low-level sword or a piece of endgame armour found nothing because the
row was never added.  The client already carries a name for every item it can draw,
and LandSandBoat carries the equipment fields.  This tool joins the two and writes
one migration with every weapon, shield, armour, accessory and ammunition item.

Inputs
------
``tools/client_item_names.tsv``
    ``item id <TAB> English name`` for every equippable item in the retail client.
    Regenerate it with ``tools/dump_client_items.c`` (see that file's header) and
    keep the id order sorted, so this tool's output stays deterministic.

``<lsb>/sql/item_basic.sql``, ``item_equipment.sql``, ``item_weapon.sql``
    The public LandSandBoat item tables.  They supply the slot mask, level, item
    level, job mask, model id, stack size, Rare/Ex flags and NPC resale value.

``tools/item_model_overrides.json``
    Optional raw grap models for armour pieces LandSandBoat leaves MId 0 on.  The
    table was generated from the DressUp set tables; without an override the item
    gets its slot's base+1 placeholder, so no armour row keeps model 0.

``database/migrations/0111_full_item_catalog.sql`` (output)
    Adds ``items.price``, ``items.base_sell`` and ``items.item_level`` plus
    ``char_purchases.price``, then upserts every equipment row.  Existing rows keep
    their hand-written name, model and slot; only the catalogue columns and the
    Rare/Ex bits are refreshed.

    The Armory price is deterministic and deliberately simple::

        price = 10 * (item level, or level when the item has no item level) ** 2
        price = max(price, npc resale * 10)
        price = price * 2 for Rare or Ex

    That gives a level 1 item 10 gil, a level 99 item 98,010 gil and an i119 item
    141,610 gil (283,220 when Rare/Ex).  Keeping the formula here means the
    database, the API and the launcher show the same number.

``database/migrations/0113_armour_models.sql`` (output)
    Repairs the 496 catalogue armour pieces whose LSB MId was 0 when an earlier
    revision of 0111 ran.  A fresh database gets the same models from 0111; the
    follow-up exists so an already-migrated database does not keep the previous
    slot's look for those pieces.

    tools/import_client_item_catalog.py --lsb /tmp/lsb
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from import_lsb_item_data import parse_rows, read_sql  # noqa: E402

DEFAULT_NAMES = ROOT / "tools" / "client_item_names.tsv"
DEFAULT_OVERRIDES = ROOT / "tools" / "item_model_overrides.json"
DEFAULT_OUTPUT = ROOT / "database" / "migrations" / "0111_full_item_catalog.sql"
DEFAULT_MODELS_OUTPUT = ROOT / "database" / "migrations" / "0113_armour_models.sql"
DEFAULT_LSB = Path("/tmp/lsb")

CHUNK = 200
PRICE_CAP = 99_999_999

# The client's equipment slot bits, in the order a multi-slot item should pick its
# home slot (a sword that fits main and sub is stored as a main-hand weapon; a ring
# that fits both ring slots is stored as ring1).
SLOTS = (
    (0x0001, "main"),
    (0x0002, "sub"),
    (0x0004, "range"),
    (0x0008, "ammo"),
    (0x0010, "head"),
    (0x0020, "body"),
    (0x0040, "hands"),
    (0x0080, "legs"),
    (0x0100, "feet"),
    (0x0200, "neck"),
    (0x0400, "waist"),
    (0x0800, "ear1"),
    (0x2000, "ring1"),
    (0x8000, "back"),
)
ARMOR_BASE = {"head": 0x1000, "body": 0x2000, "hands": 0x3000,
              "legs": 0x4000, "feet": 0x5000}


def slot_for(mask: int) -> str:
    for bit, name in SLOTS:
        if mask & bit:
            return name
    return ""


def has_flag(flags: str, name: str) -> bool:
    return name in {part.strip() for part in flags.split("|")}


def int_or_zero(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_names(path: Path) -> dict[int, str]:
    names: dict[int, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != 2:
            raise SystemExit("%s:%d: expected <id><TAB><name>" % (path, number))
        try:
            item_id = int(fields[0])
        except ValueError:
            raise SystemExit("%s:%d: item id is not a number" % (path, number)) from None
        if item_id <= 0 or item_id > 0xFFFF:
            raise SystemExit("%s:%d: item id %d is out of range" % (path, number, item_id))
        if fields[1] in ("", "."):
            continue
        names[item_id] = fields[1]
    return names


def load_basic(source: Path) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for fields in parse_rows(read_sql(source, "sql/item_basic.sql"), "item_basic"):
        if len(fields) < 10 or not fields[0].isdigit():
            continue
        item_id = int(fields[0])
        rows[item_id] = {
            "stack": max(1, int_or_zero(fields[6])),
            "flags": fields[7],
            "base_sell": max(0, int_or_zero(fields[9])),
        }
    return rows


def load_equipment(source: Path) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for fields in parse_rows(read_sql(source, "sql/item_equipment.sql"), "item_equipment"):
        if len(fields) < 9 or not fields[0].isdigit():
            continue
        item_id = int(fields[0])
        rows[item_id] = {
            "level": max(1, int_or_zero(fields[2])),
            "item_level": max(0, int_or_zero(fields[3])),
            "jobs": int_or_zero(fields[4]),
            "model": int_or_zero(fields[5]),
            "mask": int_or_zero(fields[8]),
        }
    return rows


def load_weapons(source: Path) -> dict[int, int]:
    """item id -> the client skill id a weapon trains."""
    rows: dict[int, int] = {}
    for fields in parse_rows(read_sql(source, "sql/item_weapon.sql"), "item_weapon"):
        if len(fields) < 3 or not fields[0].isdigit():
            continue
        rows[int(fields[0])] = int_or_zero(fields[2])
    return rows


def armory_price(level: int, item_level: int, rare: int, ex: int, base_sell: int) -> int:
    tier = item_level if item_level > 0 else max(1, level)
    price = 10 * tier * tier
    if base_sell > 0:
        price = max(price, base_sell * 10)
    if rare or ex:
        price *= 2
    return max(1, min(PRICE_CAP, price))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--names", default=str(DEFAULT_NAMES),
                        help="client item names TSV (default tools/client_item_names.tsv)")
    parser.add_argument("--overrides", default=str(DEFAULT_OVERRIDES),
                        help="raw grap models for armour LSB has no MId for")
    parser.add_argument("--lsb", default=str(DEFAULT_LSB),
                        help="LandSandBoat checkout (default /tmp/lsb)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help="migration to write")
    parser.add_argument("--models-output", default=str(DEFAULT_MODELS_OUTPUT),
                        help="follow-up migration that repairs armour models on databases "
                             "that already applied an earlier revision of 0111")
    args = parser.parse_args()

    names = load_names(Path(args.names))
    basic = load_basic(Path(args.lsb))
    equipment = load_equipment(Path(args.lsb))
    weapons = load_weapons(Path(args.lsb))
    overrides_path = Path(args.overrides)
    overrides = ({int(key): int(value) for key, value in
                  json.loads(overrides_path.read_text(encoding="utf-8")).items()}
                 if overrides_path.is_file() else {})

    missing_equipment = sorted(set(names) - set(equipment))
    missing_basic = sorted(set(names) - set(basic))
    missing_names = sorted(set(equipment) - set(names))
    for label, missing in (("no item_equipment row", missing_equipment),
                           ("no item_basic row", missing_basic),
                           ("no client name", missing_names)):
        if missing:
            print("%d equipment items have %s: %s" % (len(missing), label, missing[:12]),
                  file=sys.stderr)

    rows: list[tuple] = []
    model_fixes: list[tuple[int, str, int]] = []
    for item_id in sorted(names):
        if item_id not in equipment or item_id not in basic:
            continue
        name = names[item_id]
        item = equipment[item_id]
        base = basic[item_id]
        slot = slot_for(item["mask"])
        if not slot:
            print("item %d (%s) has no equipment slot" % (item_id, name), file=sys.stderr)
            continue
        rare = 1 if has_flag(base["flags"], "@FLAG_RARE") else 0
        ex = 1 if has_flag(base["flags"], "@FLAG_EX") else 0
        item_level = item["item_level"]
        price = armory_price(item["level"], item_level, rare, ex, base["base_sell"])
        model = item["model"]
        if slot in ARMOR_BASE:
            if model:
                model = ARMOR_BASE[slot] + model
            else:
                # LSB leaves MId 0 on a few hundred event/old pieces.  The override
                # table carries the raw look DressUp or a related set supplies; the
                # slot's base+1 is the last resort so no armour row keeps model 0
                # (which would make the client retain the previous slot's look).
                model = int(overrides.get(item_id) or (ARMOR_BASE[slot] + 1))
                model_fixes.append((item_id, name, model))
        rows.append((
            item_id,
            name,
            base["stack"],
            0,
            slot,
            item["level"],
            "",
            model & 0xFFFF,
            item["mask"] & 0xFFFF,
            item["jobs"] & 0xFFFFFFFF,
            weapons.get(item_id, 0),
            rare,
            ex,
            price,
            base["base_sell"],
            item_level,
        ))

    lines: list[str] = []
    lines.append("-- The full item catalogue (migration 111), generated by")
    lines.append("-- tools/import_client_item_catalog.py from the retail client's item names")
    lines.append("-- and LandSandBoat's item_basic / item_equipment / item_weapon tables.")
    lines.append("--")
    lines.append("-- Before this migration the Armory searched the hand-curated items table:")
    lines.append("-- a few hundred pieces the server had needed so far.  This adds every")
    lines.append("-- equippable item the client names (weapons, shields, armour, accessories and")
    lines.append("-- ammunition), with its slot, level, item level, jobs, model, Rare/Ex flags")
    lines.append("-- and an Armory price.")
    lines.append("--")
    lines.append("-- Existing rows keep their hand-written display name, model, slot and")
    lines.append("-- description.  The upsert only refreshes price, base_sell, item_level and")
    lines.append("-- the Rare/Ex bits (ORed, so a custom row cannot lose a flag).")
    lines.append("--")
    lines.append("-- Armour with no LSB MId uses tools/item_model_overrides.json where known,")
    lines.append("-- otherwise the slot's base+1 placeholder, so every armour row has a grap")
    lines.append("-- model instead of the invisible 0.")
    lines.append("--")
    lines.append("-- price = 10 * (item level, or level) ^ 2, at least 10 * NPC resale,")
    lines.append("-- doubled for Rare/Ex.  The API charges this price when the Armory grants")
    lines.append("-- the item and records it in char_purchases.price.")
    lines.append("")
    lines.append("ALTER TABLE items ADD COLUMN base_sell INTEGER NOT NULL DEFAULT 0;")
    lines.append("ALTER TABLE items ADD COLUMN price INTEGER NOT NULL DEFAULT 0;")
    lines.append("ALTER TABLE items ADD COLUMN item_level INTEGER NOT NULL DEFAULT 0;")
    lines.append("ALTER TABLE char_purchases ADD COLUMN price INTEGER NOT NULL DEFAULT 0;")
    lines.append("")

    columns = ("item_id,name,stack,usable,equip_slot,level,description,model,"
               "slot_mask,jobs,skill,rare,ex,price,base_sell,item_level")
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start:start + CHUNK]
        values = []
        for row in chunk:
            values.append("(%d,%s,%d,%d,%s,%d,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d)" % (
                row[0], sql_text(row[1]), row[2], row[3], sql_text(row[4]), row[5],
                sql_text(row[6]), row[7], row[8], row[9], row[10], row[11], row[12],
                row[13], row[14], row[15]))
        lines.append("INSERT INTO items (%s) VALUES" % columns)
        lines.append(",\n".join(values))
        lines.append("ON CONFLICT(item_id) DO UPDATE SET")
        lines.append("    price = excluded.price,")
        lines.append("    base_sell = excluded.base_sell,")
        lines.append("    item_level = excluded.item_level,")
        lines.append("    rare = CASE WHEN rare = 1 OR excluded.rare = 1 THEN 1 ELSE 0 END,")
        lines.append("    ex = CASE WHEN ex = 1 OR excluded.ex = 1 THEN 1 ELSE 0 END;")
        lines.append("")

    lines.append("CREATE INDEX IF NOT EXISTS items_equip_slot_name")
    lines.append("    ON items(equip_slot, name COLLATE NOCASE);")
    lines.append("")

    output = Path(args.output)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote %s: %d equipment items, %d statements, %d bytes" % (
        output, len(rows), len(range(0, len(rows), CHUNK)) * 2 + 6,
        output.stat().st_size))

    model_lines = [
        "-- Armour grap models for the full catalogue (migration 113), generated by",
        "-- tools/import_client_item_catalog.py.",
        "--",
        "-- Migration 111's first revision added the catalogue rows whose LandSandBoat",
        "-- item_equipment MId is 0, leaving items.model 0; the server then kept the",
        "-- previous look when the piece was equipped.  This stamps the same override",
        "-- or slot-base+1 fallback that the current 0111 writes, so a database that",
        "-- already applied the earlier revision is repaired in place.",
        "--",
        "-- Only rows still at model 0 are touched, so a hand-written model already on",
        "-- an existing row survives.  The override models come from",
        "-- tools/item_model_overrides.json (DressUp and related-set lookups); the rest",
        "-- use the slot's first grap model.",
        "",
    ]
    for item_id, name, model in model_fixes:
        model_lines.append(
            "UPDATE items SET model = %d WHERE item_id = %d AND model = 0; -- %s" % (
                model, item_id, name))
    model_lines.append("")
    models_output = Path(args.models_output)
    models_output.write_text("\n".join(model_lines) + "\n", encoding="utf-8")
    print("wrote %s: %d armour model candidates, %d bytes" % (
        models_output, len(model_fixes), models_output.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
