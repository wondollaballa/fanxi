#!/usr/bin/env python3
"""Build the item grap-model table and the migration that keeps it correct.

The client draws a character from the server's grap list, and every visible item
must carry the model id the client expects.  Fanxi's item imports came from two
different places: some rows hold the real grap id (Ignominy Cuirass 8270), others
hold LandSandBoat's small MId (Pummeler's Mask 64) or the placeholder 0 that
migration 66 wrote.  A zero model is skipped by ``ZoneSession._apply_equip_model``
and the slot keeps its previous look, so the gear is equipped with no visible
armour -- the RDM Atrophy set in migration 94 was one symptom, the other jobs'
reforged sets were the rest.

LandSandBoat's ``item_equipment.MId`` is the model within the slot's grap group:
the client's raw model is the slot base (0x1000 head, 0x2000 body, 0x3000 hands,
0x4000 legs, 0x5000 feet) plus that MId.  A reforged piece has MId 0 in its own
row because LandSandBoat marks it "not implemented"; its look is the tier it was
reforged from, so the tool falls back to the base reforged item's MId and then to
the original set (Warlock's for Atrophy, Duelist's for Vitiation, ...).  A few
sets are missing from LandSandBoat (the RDM empyrean hands/legs/feet) and come
from Windower's DressUp tables instead.  Weapons use the MId directly, and only
when the row has no model at all.

The output is two files, both checked in:

``tools/item_models.json``
    ``{item id: raw grap model}`` for every item the resolver knows.

``database/migrations/0095_item_models.sql``
    The same table as ``item_models``, the updates for the rows already in the
    database, and triggers that stamp a known model onto an item whenever a
    migration, a clone or a grant adds it.

    tools/gen_item_models.py \
        --db data/fanxi.db \
        --lsb /tmp/lsb/sql/item_equipment.sql \
        --dressup /tmp
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "fanxi.db"
DEFAULT_JSON = ROOT / "tools" / "item_models.json"
DEFAULT_MIGRATION = ROOT / "database" / "migrations" / "0095_item_models.sql"

# The grap list prefixes the client adds per equipment slot.  items.model stores
# the raw model (without the prefix); looks() adds 0x1000, 0x2000, ... itself.
ARMOR = {"head": 0x1000, "body": 0x2000, "hands": 0x3000, "legs": 0x4000, "feet": 0x5000}
ARMOR_MASK = {"head": 16, "body": 32, "hands": 64, "legs": 128, "feet": 256}

# Reforged set prefix -> the original set its look comes from.  Used when the
# reforged row and its base row both carry MId 0.
ALIAS = {
    "Pummeler's": "fighter", "Anchorite's": "temple", "Theophany": "healer",
    "Spaekona's": "wizard", "Atrophy": "warlock", "Pillager's": "rogue",
    "Reverence": "gallant", "Ignominy": "chaos", "Totemic": "beast",
    "Brioso": "choral", "Orion": "hunter", "Wakido": "myochin", "Hachiya": "ninja",
    "Vishap": "drachen", "Convoker's": "evoker", "Assimilator's": "magus",
    "Laksamana's": "corsair", "Foire": "puppetry", "Maxixi": "dancer",
    "Academic's": "scholar", "Geomancy": "geomancer", "Runeist": "runeist",
    "Agoge": "warrior", "Hesychast's": "melee", "Piety": "cleric",
    "Archmage's": "sorcerer", "Vitiation": "duelist", "Plunderer's": "assassin",
    "Caballarius": "valor", "Fallen's": "abyss", "Ankusa": "monster",
    "Bihu": "bard", "Arcadian": "scout", "Sakonji": "saotome", "Mochizuki": "koga",
    "Pteroslaver": "wyrm", "Glyphic": "summoner", "Luhlaza": "mirage",
    "Lanun": "commodore", "Pitre": "pantin", "Horos": "etoile", "Pedagogy": "argute",
    "Bagua": "bagua", "Futhark": "futhark", "Boii": "ravager", "Bhikku": "tantra",
    "Ebers": "orison", "Wicce": "goetia", "Lethargy": "estoqueur",
    "Skulker's": "charis", "Chevalier's": "creed", "Heathen's": "bale",
    "Nukumi": "ferine", "Fili": "aoidos", "Amini": "sylvan", "Kasuga": "unkai",
    "Hattori": "iga", "Peltast's": "lancer", "Beckoner's": "caller",
    "Hashishin": "mavi", "Chasseur's": "navarch", "Karagoz": "karagoz",
    "Maculele": "maculele", "Arbatel": "savant", "Azimuth": "azimuth",
    "Erilaz": "erilaz",
}

# Limbus Su5 armour: LandSandBoat's item_equipment rows still say MId 0 ("not
# implemented"), but the client model table (xi-tools' mv/lists/characters.json)
# labels the five families and gives them MIds 513-517.  Keep the raw grap model
# (slot base + MId) here so a regeneration cannot drop the new suits; migration
# 107 stamps the same values into a database.
EXTRA_MODELS = {
    # Revelation (Hope), MId 513
    24122: 4609, 24125: 8705, 24128: 12801, 24131: 16897, 24134: 20993,
    # Sworn (Trust), MId 514
    24137: 4610, 24140: 8706, 24143: 12802, 24146: 16898, 24149: 20994,
    # Indomitable (Bravery), MId 515
    24152: 4611, 24155: 8707, 24158: 12803, 24161: 16899, 24164: 20995,
    # Duty (Justice), MId 516
    24167: 4612, 24170: 8708, 24173: 12804, 24176: 16900, 24179: 20996,
    # Clemency (Mercy), MId 517
    24182: 4613, 24185: 8709, 24188: 12805, 24191: 16901, 24194: 20997,
}

# A few weapons' item_equipment rows carry another weapon's MId.  The client's model
# table (xi-tools' mv/lists/characters.json) has the real one, so pin it here: the
# weapon branch below only fills 0 or LSB's own MId, and a regeneration would otherwise
# bring the borrowed look back.  Migration 121 applies the Gleti value to a database;
# migration 125 applies the Prime block.
WEAPON_MID_FIXES = {
    # Gleti's Knife: LSB says 513, Kannagi's katana ("weap"/weap010).  877 is the
    # knife ("knif"/knif_bs0): ROM/366/48.DAT main, ROM/368/40.DAT sub on Hume female.
    21567: 877,

    # Prime weapons.  LSB stores the relic weapon's MId for every Prime form (Mpu
    # Gandring 544 = Mandau, Caliburnus 545 = Excalibur, Kusanagi 514 = Masamune,
    # Lorg Mor 553 = Mjollnir, Opashoro 554 = Claustrum, 0 on the bow/gun/horn/shield),
    # so the client draws a relic or nothing.  characters.json has the real Prime models:
    # the "Non AG" look for stages 2-4 (the black relic-style weapon with no particle
    # effect) and "Stage 5" for the iLvl 119 III form.  A Stage 5 DAT is the Non AG
    # weapon followed by the 12,688-byte `aura` block (fr00/gp00/.../flmy), the afterglow
    # that the Relic/Mythic/Empyrean/Aeonic "119 AG" models carry too.  Pin every named
    # form so the generator keeps the right stage's id.
    # Varga Purnikawa: Non AG 475, Stage 5 474.
    21532: 475, 21533: 475, 21534: 475, 21535: 474,
    # Mpu Gandring: Non AG 907, Stage 5 918.
    21587: 907, 21588: 907, 21589: 907, 21590: 918,
    # Caliburnus: Non AG 908, Stage 5 919.
    21643: 908, 21644: 908, 21645: 908, 21646: 919,
    # Helheim: Non AG 909, Stage 5 920.
    21649: 909, 21651: 909, 21652: 909, 21653: 920,
    # Spalirisos: Non AG 910, Stage 5 921.
    21727: 910, 21728: 910, 21729: 910, 21730: 921,
    # Laphria: Non AG 911, Stage 5 922.
    21782: 911, 21783: 911, 21784: 911, 21785: 922,
    # Foenaria: Non AG 913, Stage 5 924.
    21834: 913, 21835: 913, 21836: 913, 21837: 924,
    # Gae Buide: Non AG 912, Stage 5 923.
    21888: 912, 21889: 912, 21890: 912, 21891: 923,
    # Dokoku: Non AG 914, Stage 5 925.
    21929: 914, 21930: 914, 21931: 914, 21932: 925,
    # Kusanagi: Non AG 915, Stage 5 926.
    21983: 915, 21984: 915, 21985: 915, 21986: 926,
    # Lorg Mor: Non AG 916, Stage 5 927.
    21998: 916, 22000: 916, 22001: 916, 22002: 927,
    # Opashoro: Non AG 917, Stage 5 928.
    22103: 917, 22104: 917, 22105: 917, 22106: 928,
    # Pinaka: Non AG 148, Stage 5 151.
    22156: 148, 22157: 148, 22158: 148, 22163: 151,
    # Earp: Non AG 149, Stage 5 152.
    22160: 149, 22161: 149, 22162: 149, 22164: 152,
    # Loughnashade: Non AG 150, Stage 5 153.
    22304: 150, 22305: 150, 22306: 150, 22307: 153,
    # Duban: Non AG 675, Stage 5 676.
    26492: 675, 26493: 675, 26494: 675, 26495: 676,
}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def stem(text: str) -> str:
    value = norm(text)
    return value[:-1] if value.endswith("s") else value


def load_lsb(path: Path) -> dict[int, dict]:
    """item id -> {name, mid, mask} from LandSandBoat's item_equipment.sql."""
    rows: dict[int, dict] = {}
    pattern = re.compile(
        r"INSERT INTO `item_equipment` VALUES "
        r"\((\d+),'([^']*)',(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),"
    )
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            item_id, name, _level, _ilevel, _jobs, mid, _shield, _x, mask = match.groups()
            rows[int(item_id)] = {"name": name, "mid": int(mid), "mask": int(mask)}
    return rows


def load_dressup(directory: Path) -> dict[str, dict[str, int]]:
    """set stem -> slot -> raw grap model from Windower's DressUp tables."""
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for path in sorted(directory.glob("*.lua")):
        slot = path.stem.rsplit("_", 1)[-1]
        if slot not in ARMOR:
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.search(
                r'name = "([^"]+)".*?(?:enl = "([^"]*)")?.*?model = (\d+)', line)
            if match:
                enl = match.group(2) or match.group(1)
                out[stem(enl)][slot] = int(match.group(3))
    return out


def resolve(db: Path, lsb_path: Path, dressup_path: Path) -> tuple[dict[int, int], list]:
    lsb = load_lsb(lsb_path)
    dressup = load_dressup(dressup_path)
    by_stem: dict[str, list[dict]] = defaultdict(list)
    for row in lsb.values():
        by_stem[stem(row["name"].replace("_", " "))].append(row)

    def original_mid(prefix: str, slot: str) -> int:
        key = stem(prefix)
        mids: list[int] = []
        for name_stem, rows in by_stem.items():
            if name_stem == key or name_stem.startswith(key):
                mids += [row["mid"] for row in rows
                         if row["mid"] and row["mask"] & ARMOR_MASK[slot]]
        return max(set(mids), key=mids.count) if mids else 0

    def original_dress(prefix: str, slot: str) -> int:
        key = stem(prefix)
        for name_stem, slots in dressup.items():
            if name_stem == key or name_stem.startswith(key):
                if slot in slots:
                    return slots[slot]
        return 0

    connection = sqlite3.connect(str(db))
    connection.row_factory = sqlite3.Row
    # The catalogue has both spellings: older imports use "ranged", the full item
    # catalogue uses "range" (Pinaka, Earp and Loughnashade, for one).
    items = connection.execute(
        "SELECT item_id, name, equip_slot, model FROM items "
        "WHERE equip_slot IN ('head','body','hands','legs','feet','main','sub','ranged','range')"
    ).fetchall()
    connection.close()

    resolved: dict[int, int] = {}
    missing: list[tuple[int, str, str]] = []
    for item in items:
        item_id, name, slot = int(item["item_id"]), item["name"], item["equip_slot"]
        if item_id in EXTRA_MODELS:
            resolved[item_id] = EXTRA_MODELS[item_id]
            continue
        if slot in ARMOR:
            mid = lsb.get(item_id, {}).get("mid", 0)
            if not mid:
                base = re.sub(r" \+[0-9]+$", "", name)
                for row in by_stem.get(stem(base), []):
                    if row["mid"] and row["mask"] & ARMOR_MASK[slot]:
                        mid = row["mid"]
                        break
            if mid:
                resolved[item_id] = ARMOR[slot] + mid
                continue
            prefix = next((entry for entry in ALIAS if name.startswith(entry + " ")), None)
            if prefix:
                mid = original_mid(ALIAS[prefix], slot)
                if mid:
                    resolved[item_id] = ARMOR[slot] + mid
                    continue
                model = original_dress(ALIAS[prefix], slot)
                if model:
                    resolved[item_id] = model
                    continue
                mids = [original_mid(ALIAS[prefix], other) for other in ARMOR]
                mids = [value for value in mids if value]
                if mids:
                    resolved[item_id] = ARMOR[slot] + max(set(mids), key=mids.count)
                    continue
            # A set whose own rows share one MId (Gleti's Breeches has a 0 row):
            prefix = name.rsplit(" ", 1)[0]
            mids = [row["mid"] for row in lsb.values()
                    if row["mid"] and stem(row["name"]).startswith(stem(prefix))]
            if mids:
                resolved[item_id] = ARMOR[slot] + max(set(mids), key=mids.count)
                continue
            missing.append((item_id, name, slot))
        else:
            # A weapon's MId is the raw model.  Keep a special model a row already has
            # (the i119 REMA weapons carry a higher one) and fill only 0 or the MId.
            # A known-wrong MId is replaced even when the row already carries it.
            mid = WEAPON_MID_FIXES.get(item_id, lsb.get(item_id, {}).get("mid", 0))
            current = int(item["model"])
            if not mid:
                missing.append((item_id, name, slot))
            elif current in (0, mid) or item_id in WEAPON_MID_FIXES:
                resolved[item_id] = mid
    return resolved, missing


def migration_sql(resolved: dict[int, int], db: Path) -> str:
    connection = sqlite3.connect(str(db))
    connection.row_factory = sqlite3.Row
    names = {int(row["item_id"]): row["name"]
             for row in connection.execute("SELECT item_id, name FROM items")}
    connection.close()
    lines = [
        "-- Visible item look data (migration 95), generated by tools/gen_item_models.py.",
        "--",
        "-- items.model must be the grap model the client draws: the slot base plus LandSandBoat's",
        "-- MId for armour (a reforged piece uses its tier's MId), or the MId itself for a weapon.",
        "-- Migration 66 wrote 0 and several imports wrote the small MId instead, so the equipped",
        "-- pieces were skipped by _apply_equip_model and rendered as the previous/default look.",
        "--",
        "-- The table and the triggers keep the same mapping for gear added later: a migration, a",
        "-- grant or clone_character.py inserting an item or a character row stamps the model on it.",
        "-- Regenerate with tools/gen_item_models.py after a new item set is imported.",
        "",
        "CREATE TABLE IF NOT EXISTS item_models (",
        "    item_id INTEGER PRIMARY KEY,",
        "    model INTEGER NOT NULL",
        ");",
        "",
    ]
    values = ", ".join("(%d,%d)" % (item_id, model) for item_id, model in sorted(resolved.items()))
    lines.append("INSERT OR REPLACE INTO item_models (item_id, model) VALUES " + values + ";")
    lines.append("")
    lines.append("-- Existing rows: fix 0 and the MId placeholders.")
    for item_id, model in sorted(resolved.items()):
        lines.append("UPDATE items SET model=%d WHERE item_id=%d; -- %s"
                     % (model, item_id, names.get(item_id, "?")))
    lines += [
        "",
        "-- New items and gear grants: the lookup is authoritative for every known item, so a row",
        "-- inserted with 0 or a MId placeholder gets the real model before the client sees it.",
        "CREATE TRIGGER IF NOT EXISTS item_models_item_insert",
        "AFTER INSERT ON items",
        "BEGIN",
        "    UPDATE items SET model = (SELECT model FROM item_models WHERE item_id = NEW.item_id)",
        "    WHERE item_id = NEW.item_id",
        "      AND EXISTS (SELECT 1 FROM item_models WHERE item_id = NEW.item_id)",
        "      AND model IS NOT (SELECT model FROM item_models WHERE item_id = NEW.item_id);",
        "END;",
        "",
        "CREATE TRIGGER IF NOT EXISTS item_models_inventory_insert",
        "AFTER INSERT ON char_inventory",
        "BEGIN",
        "    UPDATE items SET model = (SELECT model FROM item_models WHERE item_id = NEW.item_id)",
        "    WHERE item_id = NEW.item_id",
        "      AND EXISTS (SELECT 1 FROM item_models WHERE item_id = NEW.item_id)",
        "      AND model IS NOT (SELECT model FROM item_models WHERE item_id = NEW.item_id);",
        "END;",
        "",
        "CREATE TRIGGER IF NOT EXISTS item_models_equip_insert",
        "AFTER INSERT ON char_equip",
        "BEGIN",
        "    UPDATE items SET model = (SELECT model FROM item_models WHERE item_id = NEW.item_id)",
        "    WHERE item_id = NEW.item_id",
        "      AND EXISTS (SELECT 1 FROM item_models WHERE item_id = NEW.item_id)",
        "      AND model IS NOT (SELECT model FROM item_models WHERE item_id = NEW.item_id);",
        "END;",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--lsb", type=Path, default=Path("/tmp/lsb/sql/item_equipment.sql"))
    parser.add_argument("--dressup", type=Path, default=Path("/tmp"),
                        help="directory with DressUp head.lua/body.lua/... tables")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--migration", type=Path, default=DEFAULT_MIGRATION)
    args = parser.parse_args()
    resolved, missing = resolve(args.db, args.lsb, args.dressup)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps({str(key): value for key, value in sorted(resolved.items())},
                                    indent=1) + "\n")
    args.migration.write_text(migration_sql(resolved, args.db))
    print("wrote %s (%d items)" % (args.json, len(resolved)))
    print("wrote %s" % args.migration)
    if missing:
        print("unresolved (no model source):")
        for item_id, name, slot in missing:
            print("  %6d %-28s %s" % (item_id, name, slot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
