#!/usr/bin/env python3
"""Import the general-item store catalogue into a Fanxi migration.

The Armory (migration 111) only holds equipment.  This tool joins LandSandBoat's
``item_basic`` rows with the retail client names for the equipment-like items it
already has (jugs, pet food, ammunition) and writes the rest of the catalogue the
Data page's **Items** tab sells: ninja tools, jug pets, consumables, ingredients,
materials, crystals, scrolls, furnishings and other general items.

Inputs
------
``<lsb>/sql/item_basic.sql``
    Item id, internal name, type, stack size, retail flags, auction-house category
    and NPC resale value.
``<lsb>/sql/item_usable.sql``
    The ids the server can use with /item.  ``item_basic`` also carries the
    ``@FLAG_CANUSE`` bit; either source marks a row usable.
``tools/client_item_names.tsv``
    The retail client's English names for equipment, ammunition and the
    equipment-like consumables (jugs and pet food).  Rows missing from this file
    get a readable name built from LandSandBoat's internal name.
``data/jug_pets.json``
    The Call Beast jug ids.  They are ``@WEAPON_TYPE`` in LandSandBoat because the
    client draws them in an ammo slot, but the Items tab treats every one of them
    as a jug pet rather than as equipment.

Output
------
``database/migrations/0156_item_store.sql``
    Adds ``items.category`` and upserts the general-item catalogue.  Existing rows
    keep their hand-written display name, equip slot and stack size; the new
    columns and the price/flags are refreshed.  Price is deterministic::

        price = 10 * NPC resale, or 1,000 gil when the NPC resale value is zero

    Rows already in the equipment catalogue are included only when they are
    consumables (jugs, pet food, ammunition and similar), so a normal sword stays
    in the Armory and out of the Items tab.

    tools/import_lsb_store_items.py --lsb /tmp/lsb
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
DEFAULT_JUGS = ROOT / "data" / "jug_pets.json"
DEFAULT_OUTPUT = ROOT / "database" / "migrations" / "0156_item_store.sql"
DEFAULT_LSB = Path("/tmp/lsb")

CHUNK = 200
ZERO_RESALE_PRICE = 1000

# The auction-house category is the best retail grouping available for general
# items.  Several crafting categories collapse into "Materials", while the
# cooking ingredients stay separate so the Items filter reads the way a player
# thinks about them.
CATEGORY_BY_AH = {
    "@NINJA_TOOLS": "Ninja Tools",
    "@PET_ITEMS": "Pet Items",
    "@INGREDIENTS": "Ingredients",
    "@FISH": "Ingredients",
    "@MEAT_EGGS": "Ingredients",
    "@VEGETABLES": "Ingredients",
    "@SEAFOOD": "Ingredients",
    "@ALCHEMY": "Materials",
    "@ALCHEMY_2": "Materials",
    "@GOLDSMITHING": "Materials",
    "@CLOTHCRAFT": "Materials",
    "@WOODWORKING": "Materials",
    "@BONECRAFT": "Materials",
    "@LEATHERCRAFT": "Materials",
    "@SMITHING": "Materials",
    "@BEAST_MADE": "Materials",
    "@CURSED_ITEMS": "Materials",
    "@MEDICINES": "Consumables",
    "@BREADS_RICE": "Food & Drink",
    "@SWEETS": "Food & Drink",
    "@SOUPS": "Food & Drink",
    "@DRINKS": "Food & Drink",
    "@AMMUNITION": "Ammunition",
    "@CRYSTALS": "Crystals",
    "@WHITE_MAGIC": "Magic Scrolls",
    "@BLACK_MAGIC": "Magic Scrolls",
    "@SONGS": "Magic Scrolls",
    "@SUMMONING": "Magic Scrolls",
    "@GEOMANCER": "Magic Scrolls",
    "@NINJUTSU": "Magic Scrolls",
    "@AUTOMATON": "Automaton Attachments",
    "@FURNISHINGS": "Furnishings",
    "@FISHING_GEAR": "Fishing Gear",
    "@CARDS": "Miscellaneous",
    "@DICE": "Miscellaneous",
    "@INSTRUMENTS": "Miscellaneous",
    "@MISC": "Miscellaneous",
    "@MISC_2": "Miscellaneous",
    "@MISC_3": "Miscellaneous",
    "@NONE": "Miscellaneous",
}

# Weapon-type rows are equipment, except these auction categories.  Jugs and pet
# food are drawn in the ammo slot but are consumed by BST abilities; ammunition
# is a stack of consumable projectiles players expect to buy by the stack.
CONSUMABLE_WEAPON_AH = {"@AMMUNITION", "@PET_ITEMS", "@NINJA_TOOLS"}

# Only these non-weapon types hold general items.  Anything else is equipment or
# a system row that has no business in a shop.
GENERAL_TYPES = {
    "@GENERAL_TYPE",
    "@USABLE_TYPE",
    "@FURNISHING_TYPE",
    "@PUPPET_TYPE",
    "@FLOWERPOT_TYPE",
    "@LINKSHELL_TYPE",
    "@CURRENCY_TYPE",
}

QUANTITY_PREFIXES = (
    "jug_of_", "flask_of_", "bag_of_", "bunch_of_", "clump_of_", "sprig_of_",
    "pinch_of_", "pot_of_", "bottle_of_", "box_of_", "bar_of_", "sheet_of_",
    "square_of_", "piece_of_", "loaf_of_", "slice_of_", "plate_of_", "bowl_of_",
    "cup_of_", "chunk_of_", "lump_of_", "pile_of_", "set_of_", "pair_of_",
    "roll_of_", "stick_of_", "ear_of_", "pod_of_", "bulb_of_", "sack_of_",
    "cask_of_", "vial_of_", "onz_of_", "handful_of_", "serving_of_", "saucer_of_",
    "jar_of_", "block_of_", "ball_of_", "can_of_", "tube_of_", "cone_of_",
    "bundle_of_", "deck_of_", "sheaf_of_", "bale_of_", "tuft_of_", "wad_of_",
    "spool_of_", "strip_of_", "beaker_of_", "brick_of_", "log_of_",
)

# LandSandBoat drops apostrophes from internal names.  These are the common
# ones players will type in the search box; the search also ignores punctuation,
# so this is mainly about presenting the name the way the game does.
NAME_REPLACEMENTS = (
    ("nobles_", "noble's_"),
    ("drogarogas_", "drogaroga's_"),
    ("nidhoggs_", "nidhogg's_"),
    ("fools_", "fool's_"),
    ("marksmans_", "marksman's_"),
    ("hunters_", "hunter's_"),
    ("alchemists_", "alchemist's_"),
    ("thiefs_", "thief's_"),
    ("soldiers_", "soldier's_"),
    ("san_dorian", "san_d'orian"),
    ("gods_", "god's_"),
    ("kings_", "king's_"),
    ("queens_", "queen's_"),
    ("serpents_", "serpent's_"),
    ("wyverns_", "wyvern's_"),
    ("griffons_", "griffon's_"),
    ("behemoths_", "behemoth's_"),
    ("dhalmels_", "dhalmel's_"),
    ("corsairs_", "corsair's_"),
    ("pirates_", "pirate's_"),
    ("chocobos_", "chocobo's_"),
    ("moogles_", "moogle's_"),
    ("goblins_", "goblin's_"),
    ("quadavs_", "quadav's_"),
    ("yagudos_", "yagudo's_"),
    ("tonberrys_", "tonberry's_"),
    ("mamools_", "mamool's_"),
    ("autharchs_", "autharch's_"),
)
ROMAN = {"i": "I", "ii": "II", "iii": "III", "iv": "IV", "v": "V",
         "vi": "VI", "vii": "VII", "viii": "VIII", "ix": "IX", "x": "X",
         "xi": "XI", "xii": "XII", "xiii": "XIII", "xiv": "XIV", "xv": "XV"}

TOOLBAG_SUFFIX = {
    "uchitake": "Uchitake",
    "tsurara": "Tsurara",
    "kawahori-ogi": "Kawahori-Ogi",
    "makibishi": "Makibishi",
    "hiraishin": "Hiraishin",
    "mizu-deppo": "Mizu-Deppo",
    "shihei": "Shihei",
    "jusatsu": "Jusatsu",
    "kaginawa": "Kaginawa",
    "sairui-ran": "Sairui-Ran",
    "kodoku": "Kodoku",
    "shinobi-tabi": "Shinobi-Tabi",
    "sanjaku-tenugui": "Sanjaku-Tenugui",
    "soshi": "Soshi",
    "kabenro": "Kabenro",
    "jinko": "Jinko",
    "ryuno": "Ryuno",
    "mokujin": "Mokujin",
    "inoshishinofuda": "Inoshishinofuda",
    "shikanofuda": "Shikanofuda",
    "chonofuda": "Chonofuda",
    "ranka": "Ranka",
    "furusumi": "Furusumi",
}


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def has_flag(flags: str, name: str) -> bool:
    return name in {part.strip() for part in flags.split("|")}


def int_or_zero(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_client_names(path: Path) -> dict[int, str]:
    names: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item_id, _, name = line.partition("\t")
        try:
            names[int(item_id)] = name.strip()
        except ValueError:
            continue
    return names


def load_jug_ids(path: Path) -> set[int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {int(item_id) for item_id in payload.get("jugs", {})}


def load_usable_ids(source: Path) -> set[int]:
    return {
        int(fields[0])
        for fields in parse_rows(read_sql(source, "sql/item_usable.sql"), "item_usable")
        if fields and fields[0].isdigit()
    }


def title_word(word: str) -> str:
    if word in ROMAN:
        return ROMAN[word]
    if not word:
        return word
    pieces = word.split("-")
    return "-".join(piece[:1].upper() + piece[1:] for piece in pieces)


def display_name(internal: str) -> str:
    """``pinch_of_yuhtunga_sulfur`` -> ``Yuhtunga Sulfur``.

    General items are not in the client's equipment-name dump, so this is the
    fallback.  The client-name table wins whenever it has a row.
    """
    if internal.startswith("toolbag_"):
        suffix = internal[len("toolbag_"):]
        return "Toolbag (%s)" % TOOLBAG_SUFFIX.get(suffix, title_word(suffix))
    text = internal
    for prefix in sorted(QUANTITY_PREFIXES, key=len, reverse=True):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    for old, new in NAME_REPLACEMENTS:
        text = text.replace(old, new)
    words = [word for word in text.replace("_", " ").split() if word]
    out: list[str] = []
    for index, word in enumerate(words):
        if word in ("+1", "+2", "+3", "+4"):
            out.append(word)
            continue
        if index and word.lower() in {
                "of", "the", "and", "in", "on", "at", "to", "for", "with", "from"}:
            out.append(word.lower())
            continue
        out.append(title_word(word))
    name = " ".join(out)
    name = name.replace("'S", "'s").replace("'T", "'t").replace("'Re", "'re")
    name = name.replace("'Ve", "'ve").replace("'Ll", "'ll").replace("'D", "'d")
    # The client writes the nation's name with a lowercase d and a capital O,
    # unlike the title-cased internal name.
    name = name.replace("San D'orian", "San d'Orian").replace("San D'oria", "San d'Oria")
    return name


def category_for(item_id: int, ah: str, jug_ids: set[int]) -> str:
    if item_id in jug_ids:
        return "Jug Pets"
    return CATEGORY_BY_AH.get(ah, "Miscellaneous")


def price_for(base_sell: int) -> int:
    return max(1, base_sell * 10) if base_sell > 0 else ZERO_RESALE_PRICE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lsb", default=str(DEFAULT_LSB),
                        help="LandSandBoat checkout (default /tmp/lsb)")
    parser.add_argument("--names", default=str(DEFAULT_NAMES),
                        help="client English item names (default tools/client_item_names.tsv)")
    parser.add_argument("--jugs", default=str(DEFAULT_JUGS),
                        help="Call Beast jug ids (default data/jug_pets.json)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help="migration to write")
    args = parser.parse_args()

    source = Path(args.lsb)
    client_names = load_client_names(Path(args.names))
    jug_ids = load_jug_ids(Path(args.jugs))
    usable_ids = load_usable_ids(source)

    rows: list[tuple] = []
    for fields in parse_rows(read_sql(source, "sql/item_basic.sql"), "item_basic"):
        if len(fields) < 10 or not fields[0].isdigit():
            continue
        item_id = int(fields[0])
        internal = fields[2]
        item_type = fields[5].strip()
        stack = max(1, int_or_zero(fields[6]))
        flags = fields[7]
        ah = fields[8].strip()
        base_sell = max(0, int_or_zero(fields[9]))
        if not internal or internal in (".", ""):
            continue

        is_jug = item_id in jug_ids
        if not is_jug:
            if item_type in ("@EQUIPMENT_TYPE", "@WEAPON_TYPE"):
                # Keep ordinary gear in the Armory.  Ammunition, jugs and pet
                # food are the equipment-like rows the Items tab also sells.
                if item_type != "@WEAPON_TYPE" or ah not in CONSUMABLE_WEAPON_AH:
                    continue
            elif item_type not in GENERAL_TYPES:
                continue

        can_use = has_flag(flags, "@FLAG_CANUSE") or item_id in usable_ids
        excluded = has_flag(flags, "@FLAG_EX")
        if not is_jug and base_sell <= 0 and not (can_use and not excluded):
            # Zero-resale key items and furnishings are not a shop row.  Usable
            # items without an NPC resale price (Reraizer, quest spells, event
            # food) are still things a player may want to buy.
            continue

        name = client_names.get(item_id) or display_name(internal)
        category = category_for(item_id, ah, jug_ids)
        rare = 1 if has_flag(flags, "@FLAG_RARE") else 0
        ex = 1 if has_flag(flags, "@FLAG_EX") else 0
        equip_slot = "ammo" if item_type == "@WEAPON_TYPE" else ""
        slot_mask = 8 if equip_slot == "ammo" else 0
        rows.append((
            item_id, name, stack, 1 if can_use else 0, equip_slot, 1, "", 0,
            slot_mask, 0, 0, rare, ex, price_for(base_sell), base_sell, 0,
            category,
        ))

    rows.sort(key=lambda row: row[0])

    out: list[str] = []
    out.append("-- General-item store catalogue (migration 0156), generated by")
    out.append("-- tools/import_lsb_store_items.py from LandSandBoat's item_basic / item_usable")
    out.append("-- tables and the retail client names for equipment-like items.")
    out.append("--")
    out.append("-- The Armory (migration 111) only imports equipment.  This adds the other")
    out.append("-- things a character buys in bulk: ninja tools, Call Beast jugs, pet food,")
    out.append("-- potions, food, ingredients, crafting materials, crystals, scrolls, arrows")
    out.append("-- and furnishings.  `category` is the Items tab filter; equipment rows keep")
    out.append("-- an empty category and stay in the Armory.")
    out.append("--")
    out.append("-- Price is deterministic: 10 times the NPC resale value, or 1,000 gil when")
    out.append("-- the item has no resale value (Reraizer, quest spell scrolls, event food).")
    out.append("-- Existing rows keep their hand-written name, equip slot, model, stack size and")
    out.append("-- usable bit; only the category, price and Rare/Ex bits are refreshed.")
    out.append("")
    out.append("ALTER TABLE items ADD COLUMN category TEXT NOT NULL DEFAULT '';")
    out.append("")
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start:start + CHUNK]
        out.append("INSERT INTO items (")
        out.append("    item_id, name, stack, usable, equip_slot, level, description, model,")
        out.append("    slot_mask, jobs, skill, rare, ex, price, base_sell, item_level, category")
        out.append(") VALUES")
        values = ",\n".join(
            "    (%s)" % ", ".join(
                sql_text(value) if isinstance(value, str) else str(value)
                for value in row
            )
            for row in chunk
        )
        out.append(values + "")
        out.append("ON CONFLICT(item_id) DO UPDATE SET")
        out.append("    category = excluded.category,")
        out.append("    usable = MAX(items.usable, excluded.usable),")
        out.append("    price = excluded.price,")
        out.append("    base_sell = excluded.base_sell,")
        out.append("    rare = MAX(items.rare, excluded.rare),")
        out.append("    ex = MAX(items.ex, excluded.ex);")
        out.append("")
    out.append("CREATE INDEX IF NOT EXISTS items_category_name")
    out.append("    ON items(category, name COLLATE NOCASE);")
    out.append("")

    text = "\n".join(out)
    target = Path(args.output)
    target.write_text(text, encoding="utf-8")
    print("wrote %s" % target)
    print("  item rows: %d" % len(rows))
    print("  size:      %.1f KB" % (len(text) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
