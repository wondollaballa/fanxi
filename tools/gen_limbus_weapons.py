#!/usr/bin/env python3
"""Generate the Limbus weapon tables from ``data/limbus_weapons_r30.json``.

The sixteen Telopanos weapons are the Limbus furnaces' Su5 gear: an Auge
Scintistone plus zone units lifts the Telognophos base weapon to the Telopanos
form, and the same furnaces (Temenos and Apollyon) add the Rank 30 rows.  The
dataset holds one entry per weapon with its client stat line and its Rank 30
rows; this tool turns it into the two artefacts that must not drift from it:

* ``--sql``    write ``database/migrations/0175_limbus_weapons_r30.sql`` (the
                base modifiers, the client skill bonuses, the item descriptions
                and the grant for characters 1 and 2) and
                ``0178_limbus_weapon_models.sql`` (the grap model each weapon
                wears, identified from the client's 2026 block -- see
                :func:`render_models_sql`);
* ``--docs``   write ``docs/limbus-weapons-r30.md`` (every weapon, every Rank 30
                row and the bundle each copy carries);
* ``--check``  exit non-zero if either file is out of date.

Run ``python3 tools/gen_limbus_weapons.py --all`` after editing the JSON.

The stat lines come from BG Wiki verbatim, and the wiki phrase -> ``item_mods``
mapping is the reforged importer's parser (:mod:`import_reforged_item_data`),
not a second copy of it.  ``DMG:``/``Delay:`` are the client's weapon header and
live in ``item_weapon`` (migration 80 already carries them); the parser leaves
them in its leftover, which is why they do not appear in ``item_mods``.
``Magic Accuracy skill`` has no skill id in the client's 0x062 table, so it is
recorded here and not stored -- the same gap every iLvl 119 weapon has.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "limbus_weapons_r30.json"
DOCS = ROOT / "docs" / "limbus-weapons-r30.md"
SQL = ROOT / "database" / "migrations" / "0175_limbus_weapons_r30.sql"
MODELS_SQL = ROOT / "database" / "migrations" / "0178_limbus_weapon_models.sql"

# The two characters the award goes to: Onedough (account onedough) and
# Twodough (account onedough-2), the same pair migration 99 granted the suits to.
CHARACTERS = (1, 2)

# Wardrobes and storage, in the order migration 66/72 fill them.
CONTAINERS = (
    (8, 1), (10, 2), (11, 3), (12, 4), (13, 5), (14, 6), (15, 7), (16, 8),
    (1, 9), (5, 10), (6, 11), (7, 12), (9, 13),
)

# The reforged importer owns the description parser; import it by path the way
# server/tests/test_reforged_item_data.py does, so there is one set of rules.
_SPEC = importlib.util.spec_from_file_location(
    "import_reforged_item_data", ROOT / "tools" / "import_reforged_item_data.py")
REFORGED = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(REFORGED)

# Tokens the client puts in the header of a weapon tooltip; item_weapon carries
# them, and they are not modifiers.  "Magic Accuracy skill +N" has no id in the
# client's 0x062 skill table (it is LSB's separate ``ilvl_macc`` column), so it is
# claimed here and left un-stored -- the gap every iLvl 119 weapon has today.
HEADER = re.compile(r"\b(?:DMG|Delay):\s*[+-]?\d+|Magic Accuracy skill\s*\+\s*\d+")


def check_shipped() -> None:
    """Fail when the dataset is git-ignored, because a deploy would ship without it.

    ``data/*`` is ignored and every source dataset is whitelisted by name, so a new
    dataset that forgets its ``!data/...`` line is committed *without* its file: the
    code, the migration and the docs deploy, the migration grants the items, and the
    RP card still lists nothing because the server has no dataset to read.
    """
    try:
        result = subprocess.run(["git", "check-ignore", "-q", str(DATA)],
                                cwd=ROOT, capture_output=True)
    except (OSError, ValueError):
        return  # no git at all (a release tarball): nothing to check
    if result.returncode == 0:
        raise SystemExit(
            "%s is git-ignored: add '!%s' to .gitignore or a deploy ships without it"
            % (DATA.name, DATA.relative_to(ROOT)))


def load() -> dict:
    return json.loads(DATA.read_text())


def weapons(doc: dict) -> list[dict]:
    return list(doc.get("weapons", ()))


def description(weapon: dict) -> str:
    """The client's full tooltip line, pet/avatar clause included."""
    parts = list(weapon.get("stats") or ())
    if weapon.get("pet"):
        parts.append(weapon["pet"])
    return " ".join(parts)


def stat_text(weapon: dict) -> str:
    """The player's stat line, header tokens removed (the parser's input)."""
    return HEADER.sub(" ", " ".join(weapon.get("stats") or ()))


def base_rows(weapon: dict) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """(modifier rows, client skill rows) for one weapon's base stats."""
    mods, skill_rows, leftover = REFORGED.parse_description(stat_text(weapon))
    leftover = " ".join(leftover.split())
    if REFORGED.looks_like_stat(leftover):
        raise SystemExit("%s: unparsed stat text %r" % (weapon["name"], leftover))
    totals: dict[int, int] = {}
    for mod_id, value in mods:
        totals[int(mod_id)] = totals.get(int(mod_id), 0) + int(value)
    if not totals:
        raise SystemExit("no modifiers parsed for %s" % weapon["name"])
    skills: dict[int, int] = {}
    for skill_id, amount in skill_rows:
        skills[int(skill_id)] = skills.get(int(skill_id), 0) + int(amount)
    return sorted(totals.items()), sorted(skills.items())


def sql_description(text: str) -> str:
    return text.replace("'", "''")


def render_sql(doc: dict) -> str:
    items = weapons(doc)
    ids = ", ".join(str(int(weapon["item_id"])) for weapon in items)
    rank = int(doc.get("rank", 30))
    rp = int(doc.get("rp", 55800))

    base = {int(weapon["item_id"]): base_rows(weapon) for weapon in items}

    lines = [
        "-- Limbus Rank 30 weapons (migration %s)." % SQL.stem.split("_", 1)[0],
        "--",
        "-- The sixteen Telopanos weapons: the fourteen weapon skills, the shield",
        "-- and the grip.  An Auge Scintistone plus units from Temenos or Apollyon",
        "-- lifts the Telognophos base weapon to this form, and the same furnace adds",
        "-- the Rank %d rows.  The items themselves are already in the catalogue" % rank,
        "-- (migration 111) and their damage/delay in item_weapon (migration 80); this",
        "-- migration adds what the client's tooltip has and the server did not:",
        "-- the base modifiers, the client skill bonuses and a description.",
        "--",
        "-- The Rank 30 rows come from BG Wiki; each weapon's client augment bundle",
        "-- index is the client's own augment table (512 entries,",
        "-- 497-512 are this family), matched to those rows by content.  The grant",
        "-- hands both mains one unaugmented copy so the Data page's RP card can cap",
        "-- it; ``//rp30`` re-stamps anything already carried.",
        "--",
        "-- Generated from data/limbus_weapons_r30.json by tools/gen_limbus_weapons.py.",
        "",
        "DELETE FROM item_mods WHERE item_id IN (%s);" % ids,
        "",
        "-- Base modifiers from each weapon's stat line.",
        "INSERT INTO item_mods (item_id,mod_id,value) VALUES",
    ]
    rows = []
    for weapon in sorted(items, key=lambda entry: int(entry["item_id"])):
        mods, _skills = base[int(weapon["item_id"])]
        rows.append("  " + ", ".join("(%d,%d,%d)" % (int(weapon["item_id"]), mod_id, value)
                                     for mod_id, value in mods))
    lines.append(",\n".join(rows) + ";")

    lines += ["", "DELETE FROM item_skill_bonus WHERE item_id IN (%s);" % ids, "",
              "-- Client skill bonuses (0x062 skill ids): the weapon's own skill,",
              "-- Parrying (31), Guard (28) and Shield (30) where the tooltip lists them.",
              "INSERT INTO item_skill_bonus (item_id,skill_id,amount) VALUES"]
    rows = []
    for weapon in sorted(items, key=lambda entry: int(entry["item_id"])):
        _mods, skill_rows = base[int(weapon["item_id"])]
        for skill_id, amount in skill_rows:
            rows.append("  (%d,%d,%d)" % (int(weapon["item_id"]), skill_id, amount))
    lines.append(",\n".join(rows) + ";")

    lines += ["", "-- The client's own description line, for the catalogue and the Armory.",
              "UPDATE items SET description = CASE item_id"]
    for weapon in sorted(items, key=lambda entry: int(entry["item_id"])):
        lines.append("  WHEN %d THEN '%s'" % (int(weapon["item_id"]),
                                              sql_description(description(weapon))))
    lines.append("  ELSE description END")
    lines.append(" WHERE item_id IN (%s);" % ids)


    lines += [
        "",
        "-- Give both mains one copy of each weapon, into their first free slots.",
        "-- The copies are unaugmented: the RP card on the Data page caps a path in",
        "-- one click, which is the point of granting them.",
        "WITH RECURSIVE",
        "  target(character_id) AS (",
        "    SELECT id FROM characters WHERE id IN (%s)" % ", ".join(str(c) for c in CHARACTERS),
        "  ),",
        "  containers(container, ord) AS (",
        "    VALUES %s" % ",".join("(%d,%d)" % pair for pair in CONTAINERS),
        "  ),",
        "  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),",
        "  free AS (",
        "    SELECT t.character_id, c.container, n.n AS slot,",
        "           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY c.ord, n.n) AS rn",
        "    FROM target t CROSS JOIN containers c CROSS JOIN nums n",
        "    WHERE NOT EXISTS (",
        "      SELECT 1 FROM char_inventory ci",
        "      WHERE ci.character_id = t.character_id AND ci.container = c.container AND ci.slot = n.n",
        "    )",
        "  ),",
        "  want AS (",
        "    SELECT t.character_id, w.item_id,",
        "           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY w.item_id) AS rn",
        "    FROM target t CROSS JOIN (SELECT %s) AS w" % " AS item_id UNION ALL SELECT ".join(
            str(int(weapon["item_id"])) for weapon in sorted(items, key=lambda e: int(e["item_id"]))),
        "    WHERE NOT EXISTS (",
        "      SELECT 1 FROM char_inventory ci",
        "      WHERE ci.character_id = t.character_id AND ci.item_id = w.item_id",
        "    )",
        "  )",
        "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)",
        "SELECT w.character_id, f.container, f.slot, w.item_id, 1",
        "FROM want w JOIN free f ON f.character_id = w.character_id AND f.rn = w.rn;",
        "",
        "-- Both mains can re-check the dataset in chat: //r30 telopanos prints each",
        "-- weapon's Rank %d rows and //rp30 re-stamps the %d-RP block." % (rank, rp),
        "",
    ]
    return "\n".join(lines)



def render_models_sql(doc: dict) -> str:
    items = weapons(doc)
    modelled = [weapon for weapon in sorted(items, key=lambda entry: int(entry["item_id"]))
                if weapon.get("model")]
    if not modelled:
        raise SystemExit("no grap models in %s" % DATA)
    lines = [
        "-- Limbus weapon grap models (migration %s)." % MODELS_SQL.stem.split("_", 1)[0],
        "--",
        "-- Supersedes migration 176, which gave these weapons same-type stand-ins so",
        "-- they would at least draw.  The 2026 wave ships no MId in any server data",
        "-- (LandSandBoat marks the rows `TODO: MId`) and the client's item records",
        "-- carry no model either, so the ids below were identified from the client's",
        "-- own 2026 model block by testing them in game: the Claymore confirmed 959",
        "-- and the Sword 958, which fixes the block's weapon-group order (the same",
        "-- order the prime block uses: Dagger, Sword, G.Sword, Axe, G.Axe, Polearm,",
        "-- Scythe, Katana, G.Katana, Club, Staff).  The one-handed models carry a",
        "-- main and a sub DAT, the two-handed ones main only -- every id below is",
        "-- consistent with its weapon's handedness, which is the cross-check on the",
        "-- derived ones.  H2H, Archery and the shield live in their own groups.",
        "--",
        "-- The Saber and the Shield are still tentative in the dataset note;",
        "-- //model <item> <id> tests one copy and a dataset edit + regeneration bakes",
        "-- the confirmed id in.",
        "--",
        "-- Generated from data/limbus_weapons_r30.json by tools/gen_limbus_weapons.py.",
        "",
        "INSERT OR REPLACE INTO item_models (item_id,model) VALUES",
    ]
    lines.append("  " + ", ".join("(%d,%d)" % (int(weapon["item_id"]), int(weapon["model"]))
                                  for weapon in modelled) + ";")
    lines += [
        "",
        "-- The rows already in the catalogue keep their model too (item_models'",
        "-- triggers only stamp rows inserted later).",
        "UPDATE items SET model = CASE item_id",
    ]
    for weapon in modelled:
        lines.append("  WHEN %d THEN %d" % (int(weapon["item_id"]), int(weapon["model"])))
    lines.append("  ELSE model END")
    lines.append(" WHERE item_id IN (%s);"
                 % ", ".join(str(int(weapon["item_id"])) for weapon in modelled))
    lines.append("")
    return "\n".join(lines)


def render_docs(doc: dict) -> str:
    items = weapons(doc)
    rank = int(doc.get("rank", 30))
    rp = int(doc.get("rp", 55800))
    source = doc.get("source") or []

    lines = [
        "# Limbus Rank 30 weapons",
        "",
        "The Limbus furnaces (Temenos and Apollyon) build the **Telopanos** weapons",
        "from the **Telognophos** base weapon: one **Auge Scintistone** plus units from",
        "either zone lifts it to the Superior 5 form, and the same trade adds the",
        "weapon's **Rank %d** rows. There are sixteen pieces -- one for every weapon" % rank,
        "skill, the shield and the grip:",
        "",
        "| Weapon | Skill | Slot | Jobs | Item | Bundle |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for weapon in items:
        lines.append("| %s | %s | %s | %s | %d | %d |" % (
            weapon["name"], weapon.get("skill") or "-", weapon.get("slot") or "-",
            " / ".join(weapon.get("jobs") or ("All jobs",)),
            int(weapon["item_id"]), int(weapon["bundle"])))

    lines += [
        "",
        "Every piece carries its own client augment **bundle** index. The indices are",
        "the client's own augment table (the 512-entry table the augment block names,",
        "the same one the five Limbus suits use at 472-496); 497-512 are this family,",
        "and each was matched to the rows below by its Rank %d values." % rank,
        "",
        "The Data page's **RP** card lists every one of them that a character is",
        "carrying, with the same one-click **Cap path** the suits and Odyssey gear get:",
        "the click writes rank %d / tier 3 / %s RP (RP curve B) and the piece's bundle" % (
            rank, format(rp, ",")),
        "into the item's 24-byte exdata, so the client prints the rows on the tooltip.",
        "`//r30 telopanos <part>` prints the same rows in chat and `//rp30` re-stamps",
        "every Limbus piece in the bags, weapons included.",
        "",
        "## Rank %d rows" % rank,
        "",
    ]
    for weapon in items:
        lines.append("### %s" % weapon["name"])
        lines.append("")
        lines.append("- **Item:** %d, **slot:** %s, **bundle:** %d" % (
            int(weapon["item_id"]), weapon.get("slot") or "-", int(weapon["bundle"])))
        if weapon.get("model"):
            lines.append("- **Model:** %d -- %s" % (int(weapon["model"]),
                                                   weapon.get("model_note") or "from the 2026 block"))
        lines.append("- **Jobs:** %s" % " / ".join(weapon.get("jobs") or ("All jobs",)))
        if weapon.get("stats"):
            lines.append("- **Stats:** %s" % " ".join(weapon["stats"]))
        if weapon.get("pet"):
            lines.append("- **Pet line (client text, not stored):** %s" % weapon["pet"])
        lines.append("")
        lines.append("| [1] | [2] | [3] | [4] |")
        lines.append("| --- | --- | --- | --- |")
        rows = list(weapon.get("augments") or ())
        rows += [""] * (4 - len(rows))
        lines.append("| %s |" % " | ".join(rows[:4]))
        lines.append("")

    lines += [
        "## Grap models",
        "",
        "The 2026 wave shipped without a **grap model** in any server data: LandSandBoat",
        "marks each row `TODO: MId`, and the client's own item records carry no model",
        "(the model is server-side data that private servers curate by hand).  A copy",
        "equipped with model 0 was simply not drawn -- the server log said",
        "`equipped Telopanos Sword in slot 0 with no grap model: it will not show`.",
        "",
        "The ids come from the client's own 2026 model block, identified in game.  The",
        "Claymore confirmed **959** and the Sword **958**; that fixes the block's",
        "weapon-group order (Dagger, Sword, G.Sword, Axe, G.Axe, Polearm, Scythe, Katana,",
        "G.Katana, Club, Staff), and every derived id matches its weapon's handedness --",
        "the client gives one-handed models a main and a sub DAT, two-handed models a",
        "main DAT only.  H2H, Archery and the shield sit in their own groups.",
        "",
        "| Weapon | Group | Model | Note |",
        "| --- | --- | --- | --- |",
    ]
    for weapon in items:
        lines.append("| %s | %s | %s | %s |" % (
            weapon["name"], weapon.get("skill") or "-",
            weapon.get("model") if weapon.get("model") else "none (grips are invisible)",
            weapon.get("model_note") or "-"))
    lines += [
        "",
        "`//model <item> <id>` sets one copy's look in game; editing the dataset's",
        "`model` field and running the generator bakes a better id into the migration.",
        "The grip keeps model 0 on purpose: a grip is never drawn.",
        "",
        "## Where the data comes from",
        "",
        "- Item ids, slots, jobs and the stat lines are BG Wiki's item pages; the",
        "  base modifiers come from the same parser as the reforged gear",
        "  (`tools/import_reforged_item_data.py`), and the client skill ids are the",
        "  ones the 0x062 skill menu uses.",
        "- `data/limbus_weapons_r30.json` and `tools/gen_limbus_weapons.py` are the",
        "  single source for this page, the migration and the server's lookup, so the",
        "  card, `//r30` and the combat path cannot drift apart.",
        "- The `Damage+n` row raises the weapon's damage rating, not a modifier:",
        "  `augment_stats.weapon_damage` adds it to the `item_weapon.dmg` the attack",
        "  round and the weaponskill formula read.",
        "- `Magic Accuracy skill +255` has no client skill id; the client prints it,",
        "  and neither the server's skill table nor this dataset stores it (the same",
        "  gap every iLvl 119 weapon has today).",
        "- `Pet dmg+5%` and `\"Blood Pact\" Damage+10` are recorded and shown on the",
        "  card; the engine has no pet sheet to apply them to.",
        "- The items have no client grap model yet: LandSandBoat marks their",
        "  `item_equipment` rows `TODO: MId`, so an equipped copy is invisible until",
        "  a model is set (`//model <item> <model id>`).  The icon, the",
        "  stats and the augment tooltip do not depend on it.",
        "- Retouching the rows: edit the JSON, then run",
        "  `python3 tools/gen_limbus_weapons.py --all`.",
        "",
        "Sources: " + ", ".join(source),
        "",
        "## Client data",
        "",
        "The items exist in the client's item table from the 2026 updates; the build",
        "this page was checked against is the 2026-10-05 install (client version",
        "`30261006_0`), whose `ROM/118/114.DAT` carries augment bundles 1-512.",
        "`//r30 telopanos` works on any build, but the client only prints the tooltip",
        "rows when its own augment table has the bundle.",
        "",
    ]
    return "\n".join(lines)


def write(path: Path, text: str, check: bool) -> bool:
    """Write *text* unless *check*; return whether the file already matched."""
    current = path.read_text() if path.exists() else None
    if current == text:
        return True
    if check:
        return False
    path.write_text(text)
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql", action="store_true", help="write the migration")
    parser.add_argument("--docs", action="store_true", help="write the docs page")
    parser.add_argument("--all", action="store_true", help="write both")
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if either file is out of date")
    args = parser.parse_args(argv)
    if not (args.sql or args.docs or args.all or args.check):
        parser.print_help()
        return 2

    check_shipped()
    doc = load()
    if not weapons(doc):
        raise SystemExit("no weapons in %s" % DATA)

    wanted = []
    if args.sql or args.all or args.check:
        wanted.append((SQL, render_sql(doc)))
        wanted.append((MODELS_SQL, render_models_sql(doc)))
    if args.docs or args.all or args.check:
        wanted.append((DOCS, render_docs(doc)))
    stale = [path.name for path, text in wanted if not write(path, text, args.check)]
    if stale:
        print("out of date: %s (run with --all)" % ", ".join(stale))
        return 1
    if not args.check:
        print("wrote %s" % ", ".join(path.name for path, _text in wanted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
