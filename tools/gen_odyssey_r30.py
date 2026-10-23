#!/usr/bin/env python3
"""Generate the Odyssey Rank 30 tables from ``data/odyssey_r30.json``.

One dataset, four outputs, so the libraries, the docs and the database cannot
drift apart:

* ``--lua``    rewrite the ``local odyssey`` table in every ``gearswap/*.lua``
               library and add the ``sets.Odyssey`` container for that job;
* ``--docs``   write ``docs/odyssey-r30.md`` (every item, every Rank 30 row);
* ``--sql``    write ``database/migrations/0072_odyssey_r30.sql`` (the items the
               server does not know yet, plus the wardrobe grant);
* ``--check``  exit non-zero if any file is out of date (used by the tests).

Run ``python3 tools/gen_odyssey_r30.py --all`` after editing the JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "odyssey_r30.json"
GEARSWAP = ROOT / "gearswap"
DOCS = ROOT / "docs" / "odyssey-r30.md"
SQL = ROOT / "database" / "migrations" / "0072_odyssey_r30.sql"

SET_KEYS = ("nyame", "sakpata", "gleti", "agwu")

# Which Odyssey weapon each job builds first.  Jobs without an Odyssey weapon
# of their own simply get no weapon set.
JOB_WEAPON = {
    "MNK": "fists", "PUP": "fists",
    "RDM": "sword", "PLD": "sword", "BLU": "sword",
    "THF": "knife", "BRD": "knife", "RNG": "knife", "NIN": "knife",
    "COR": "knife", "DNC": "knife",
    "BST": "axe",
    "WAR": "claymore", "RUN": "claymore",
    "DRK": "scythe",
}

# Item ids that already exist in the database (seeded by earlier migrations).
KNOWN = {
    23761, 23768, 23775, 23782, 23789,  # Nyame
    23757, 23764, 23771, 23778, 23785,  # Sakpata's
}


def load() -> dict:
    return json.loads(DATA.read_text())


def lua_string(value: str) -> str:
    if '"' in value:
        return "'%s'" % value
    return '"%s"' % value


def lua_item(name: str, augments: list[str]) -> str:
    body = ", ".join(lua_string(a) for a in augments)
    return '{ name = %s, augments = {%s} }' % (lua_string(name), body)


def lua_table(data: dict) -> str:
    lines = [
        "-- Odyssey Rank 30 builds: every Odyssey armour piece and weapon at Rank 30.",
        "-- Nyame has four paths (A accuracy/TP, B physical WS, C magic, D pet);",
        "-- Sakpata's, Gleti's and Agwu's each have one Rank 30 row.",
        "-- Generated from data/odyssey_r30.json by tools/gen_odyssey_r30.py.",
        "local odyssey = {",
    ]
    for path in ("A", "B", "C", "D"):
        lines.append("    %s = {" % path)
        for key, piece in data["sets"]["nyame"]["pieces"].items():
            lines.append("        %s = %s," % (key, lua_item(piece["name"], piece["augments"][path])))
        lines.append("    },")
    for set_key in ("sakpata", "gleti", "agwu"):
        lines.append("    %s = {" % set_key)
        for key, piece in data["sets"][set_key]["pieces"].items():
            lines.append("        %s = %s," % (key, lua_item(piece["name"], piece["augments"]["R30"])))
        lines.append("    },")
    lines.append("    weapons = {")
    for key, weapon in data["weapons"].items():
        lines.append("        %s = %s," % (key, lua_item(weapon["name"], weapon["augments"])))
    lines.append("    },")
    lines.append("}")
    return "\n".join(lines)


def jobs_for(job: str, data: dict) -> list[str]:
    """The Odyssey armour sets this job can actually wear."""
    out = ["nyame"]
    for set_key in ("sakpata", "gleti", "agwu"):
        if job in data["sets"][set_key]["jobs"]:
            out.append(set_key)
    return out


def lua_sets(job: str, data: dict) -> str:
    lines = [
        "    -- ===== Odyssey Rank 30 sets =================================",
        "    sets.Odyssey = {}  -- container: every Odyssey build this job can wear",
    ]
    for set_key in jobs_for(job, data):
        if set_key == "nyame":
            for path in ("a", "b", "c", "d"):
                slots = data["sets"]["nyame"]["pieces"]
                keys = list(slots)
                lines.append(
                    "    sets.Odyssey.nyame_%s = { head = odyssey.%s.%s, body = odyssey.%s.%s, "
                    "hands = odyssey.%s.%s, legs = odyssey.%s.%s, feet = odyssey.%s.%s }"
                    % (path, path.upper(), keys[0], path.upper(), keys[1], path.upper(), keys[2],
                       path.upper(), keys[3], path.upper(), keys[4]))
        else:
            slots = data["sets"][set_key]["pieces"]
            keys = list(slots)
            lines.append(
                "    sets.Odyssey.%s = { head = odyssey.%s.%s, body = odyssey.%s.%s, "
                "hands = odyssey.%s.%s, legs = odyssey.%s.%s, feet = odyssey.%s.%s }"
                % (set_key, set_key, keys[0], set_key, keys[1], set_key, keys[2],
                   set_key, keys[3], set_key, keys[4]))
    weapon = JOB_WEAPON.get(job)
    if weapon:
        lines.append("    sets.Odyssey.weapon = { main = odyssey.weapons.%s }" % weapon)
    if job == "RNG":
        lines.append("    sets.Odyssey.weapon_ranged = { range = odyssey.weapons.crossbow }")
    return "\n".join(lines) + "\n"


def apply_lua(data: dict) -> list[str]:
    changed = []
    table = lua_table(data)
    for path in sorted(GEARSWAP.glob("*.lua")):
        job = path.stem.upper()
        text = path.read_text()
        original = text
        start = text.find("local odyssey = {")
        if start < 0:
            raise SystemExit("%s: no 'local odyssey' table" % path)
        end = text.find("\n}\n", start)
        if end < 0:
            raise SystemExit("%s: unterminated odyssey table" % path)
        rest = text[end + 2:]
        # Drop every comment line the old table carried; the generated table has its own.
        head = text[:start].rstrip("\n").split("\n")
        stale = ("-- Odyssey Rank 30", "-- Nyame has four paths",
                 "-- Sakpata's, Gleti's and Agwu's", "-- Generated from data/odyssey_r30.json")
        while head and (head[-1].startswith(stale) or not head[-1].strip()):
            head.pop()
        text = "\n".join(head) + "\n\n" + table + rest
        sets = lua_sets(job, data)
        marker = "    -- ===== Odyssey Rank 30 sets"
        if marker in text:
            m_start = text.index(marker)
            m_end = text.find("    -- ===== ", m_start + len(marker))
            if m_end < 0:
                raise SystemExit("%s: cannot find the end of the Odyssey sets" % path)
            text = text[:m_start] + sets + "\n" + text[m_end:]
        else:
            anchor = text.find("    -- ===== idle")
            if anchor < 0:
                raise SystemExit("%s: no idle set anchor" % path)
            text = text[:anchor] + sets + "\n" + text[anchor:]
        text = text.replace("Nyame/Sakpata's Rank 30 Odyssey augments",
                            "Nyame, Sakpata's, Gleti's and Agwu's Rank 30 Odyssey augments")
        if text != original:
            path.write_text(text)
            changed.append(str(path.relative_to(ROOT)))
    return changed


def md_augments(row: list[str]) -> str:
    return "<br>".join(row)


def docs(data: dict) -> str:
    out = [
        "# Odyssey Rank 30 gear",
        "",
        "Every Odyssey Sheol: Gaol reward at **Rank 30**, as sold by the Pilgrim Moogle",
        "in Rabao after the matching `Information on ...` key item. Values are the",
        "Rank 30 rows from [BG Wiki's Odyssey page](https://www.bg-wiki.com/ffxi/Odyssey)",
        "and each item's page.",
        "",
        "The same data drives `gearswap/*.lua` (`local odyssey` and the `sets.Odyssey`",
        "container), `data/odyssey_r30.json`, and the server's `!r30` chat command.",
        "",
    ]
    titles = {"nyame": "Nyame", "sakpata": "Sakpata's", "gleti": "Gleti's", "agwu": "Agwu's"}
    for set_key in SET_KEYS:
        s = data["sets"][set_key]
        out += [
            "## %s" % s["set"],
            "",
            "- **Jobs:** %s" % ("All jobs" if len(s["jobs"]) == 22 else " / ".join(s["jobs"])),
            "- **Source:** %s" % s["source"],
            "",
        ]
        if set_key == "nyame":
            out += ["| Piece | Slot | Item ID | Bundle A/B/C/D | Path A | Path B | Path C | Path D |",
                    "| --- | --- | --- | --- | --- | --- | --- | --- |"]
            for piece in s["pieces"].values():
                a = piece["augments"]
                b = piece.get("bundles", {})
                out.append("| %s | %s | %d | %s | %s | %s | %s | %s |" % (
                    piece["name"], piece["slot"], piece["item_id"],
                    "/".join(str(b[p]) for p in "ABCD" if p in b),
                    md_augments(a["A"]), md_augments(a["B"]),
                    md_augments(a["C"]), md_augments(a["D"])))
        else:
            out += ["| Piece | Slot | Item ID | Bundle | Rank 30 augments |",
                    "| --- | --- | --- | --- | --- |"]
            for piece in s["pieces"].values():
                out.append("| %s | %s | %d | %s | %s |" % (
                    piece["name"], piece["slot"], piece["item_id"],
                    piece.get("bundle", ""), md_augments(piece["augments"]["R30"])))
        out.append("")
    out += ["## Weapons", "",
            "| Weapon | Type | Slot | Jobs | Item ID | Bundle | Rank 30 augments |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for w in data["weapons"].values():
        out.append("| %s | %s | %s | %s | %d | %s | %s |" % (
            w["name"], w["weapon"], w["slot"], " / ".join(w["jobs"]), w["item_id"],
            w.get("bundle", ""), md_augments(w["augments"])))
    out += ["",
            "## In game", "",
            "The armour pieces are granted to the character's wardrobes by",
            "`database/migrations/0072_odyssey_r30.sql`. Use `!r30 <item>` in the chat",
            "log to print an item's Rank 30 rows, and `!r30` alone to list every",
            "Odyssey item the server knows.",
            "",
            "Each item's `extdata` now carries its real **augment bundle index**",
            "(third column above). The index names a bundle in the client's augment",
            "table; the table was extracted from LandSandBoat's `Exdata::AugmentBundle`",
            "data and matched to the Rank 30 rows above by content. The method is",
            "validated end to end by Assassin's Gorget +2: its bundle 204 decodes to",
            "DEX/AGI+15, Evasion+25, Triple Attack+4% — exactly its known R25 row.",
            "",
            "Nyame gets one copy per path: the original piece carries Path A and",
            "migration `0077_odyssey_bundles.sql` adds Path B/C/D copies, each with",
            "its own bundle, so all four tooltips are distinct. `!augment <index>",
            "<item>` rewrites a copy; `!augment <A-D> <item>` looks the index up.",
            ""]
    return "\n".join(out)


def sql(data: dict) -> str:
    rows = []
    descriptions = {
        "nyame": "Odyssey Rank 30 armour (Bumba).",
        "sakpata": "Odyssey Rank 30 armour (Kalunga).",
        "gleti": "Odyssey Rank 30 armour (Ngai).",
        "agwu": "Odyssey Rank 30 armour (Ongo).",
    }
    armor_mask = {"head": 16, "body": 32, "hands": 64, "legs": 128, "feet": 256}
    for set_key in ("gleti", "agwu"):
        for piece in data["sets"][set_key]["pieces"].values():
            if piece["item_id"] in KNOWN:
                continue
            rows.append((piece["item_id"], piece["name"], piece["slot"], data["sets"][set_key]["jobs"],
                         descriptions[set_key], armor_mask[piece["slot"]]))
    for w in data["weapons"].values():
        if w["item_id"] in KNOWN:
            continue
        rows.append((w["item_id"], w["name"], w["slot"], w["jobs"],
                     "Odyssey Rank 30 weapon.", int(w["slot_mask"])))

    def job_mask(jobs: list[str]) -> int:
        mask = 0
        for job in jobs:
            mask |= 1 << (data["job_bit"][job] - 1)
        return mask

    values = []
    for item_id, name, slot, jobs, desc, slot_mask in sorted(rows):
        values.append(" (%d,'%s',1,0,'%s',99,'%s',0,%d,%d)" % (
            item_id, name.replace("'", "''"), slot, desc, slot_mask, job_mask(jobs)))
    ids = " UNION ALL ".join("SELECT %d AS item_id" % r[0] for r in sorted(rows))
    return "\n".join([
        "-- Odyssey Rank 30 additions (migration 72).",
        "--",
        "-- Adds every Gleti's and Agwu's armour piece and every Odyssey weapon the",
        "-- server did not know yet, then grants them to the first character's",
        "-- wardrobes. Nyame and Sakpata's armour already exist from earlier",
        "-- migrations. The Rank 30 rows themselves live in data/odyssey_r30.json",
        "-- and in the gearswap libraries; the client tooltip cannot print them (see",
        "-- docs/odyssey-r30.md) until the server learns retail's extdata augment",
        "-- encoding, so !r30 is the in-game view for now.",
        "--",
        "-- Item ids, slots, job masks and the Rank 30 values are factual game data",
        "-- cross-checked against BG Wiki. The SQL is Fanxi's own.",
        "",
        "INSERT OR IGNORE INTO items",
        " (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES",
        ",\n".join(values) + ";",
        "",
        "-- Give the new pieces a home in the wardrobes, like migration 66 did.",
        "WITH RECURSIVE",
        "  target(character_id) AS (SELECT id FROM characters WHERE id = 1),",
        "  containers(container, ord) AS (",
        "    VALUES (8,1),(10,2),(11,3),(12,4),(13,5),(14,6),(15,7),(16,8),",
        "           (1,9),(5,10),(6,11),(7,12),(9,13)",
        "  ),",
        "  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),",
        "  free AS (",
        "    SELECT c.container, n.n AS slot,",
        "           ROW_NUMBER() OVER (ORDER BY c.ord, n.n) AS rn",
        "    FROM containers c CROSS JOIN nums n",
        "    WHERE NOT EXISTS (",
        "      SELECT 1 FROM char_inventory ci",
        "      WHERE ci.character_id = 1 AND ci.container = c.container AND ci.slot = n.n",
        "    )",
        "    AND n.n < 80",
        "  ),",
        "  want AS (",
        "    SELECT w.item_id, ROW_NUMBER() OVER (ORDER BY w.item_id) AS rn",
        "    FROM (%s) AS w" % ids,
        "    WHERE NOT EXISTS (",
        "      SELECT 1 FROM char_inventory ci",
        "      WHERE ci.character_id = 1 AND ci.item_id = w.item_id",
        "    )",
        "  )",
        "INSERT OR IGNORE INTO char_inventory (character_id,container,slot,item_id,quantity)",
        "SELECT t.character_id, free.container, free.slot, want.item_id, 1",
        "FROM want JOIN free ON free.rn = want.rn CROSS JOIN target t;",
        "",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lua", action="store_true", help="rewrite gearswap/*.lua")
    ap.add_argument("--docs", action="store_true", help="write docs/odyssey-r30.md")
    ap.add_argument("--sql", action="store_true", help="write the migration")
    ap.add_argument("--all", action="store_true", help="all three")
    ap.add_argument("--check", action="store_true", help="verify the outputs are current")
    args = ap.parse_args()
    data = load()
    outputs = {}
    if args.docs or args.all or args.check:
        outputs[DOCS] = docs(data)
    if args.sql or args.all or args.check:
        outputs[SQL] = sql(data)
    stale = [str(p.relative_to(ROOT)) for p, text in outputs.items()
             if not p.exists() or p.read_text() != text]
    if args.check:
        if stale:
            print("out of date: " + ", ".join(stale))
            return 1
        return 0
    for path, text in outputs.items():
        path.write_text(text)
    if args.lua or args.all:
        for name in apply_lua(data):
            print("updated", name)
    for path in outputs:
        print("wrote", path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
