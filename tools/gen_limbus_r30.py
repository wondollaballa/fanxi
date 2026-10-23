#!/usr/bin/env python3
"""Generate the Limbus Rank 30 tables from ``data/limbus_r30.json``.

Each Limbus family ships in three tiers and only the top one -- Superior 5 -- is
worth handing out: Justice -> Magnificent -> **Duty**, Hope -> Perfection ->
**Revelation**, Trust -> Prestige -> **Sworn**, Bravery -> Intrepid ->
**Indomitable**, Mercy -> Grace -> **Clemency**.  The dataset holds that top
tier only, with every Rank 30 augment row.

Four outputs, one dataset, so the libraries, the docs, the items and the grants
cannot drift apart:

* ``--sql``    write ``database/migrations/0099_limbus_r30.sql`` (the items the
                server does not know yet, their base modifiers, and the Rank 30
                grant for characters 1 and 2);
* ``--docs``   write ``docs/limbus-r30.md`` (every piece, every Rank 30 row, and
                where the suit goes in the libraries);
* ``--lua``    rewrite ``gearswap/*.lua``: the ``local limbus`` build table, the
                ``sets.Limbus`` container, and the pieces the ``PLACEMENT`` table
                wears in the existing TP / hybrid / fast-cast sets;
* ``--check``  exit non-zero if the SQL or the docs are out of date.

Run ``python3 tools/gen_limbus_r30.py --all`` after editing the JSON.

The stat lines come from BG Wiki verbatim, so the modifier table below is the
only place that knows how a wiki phrase becomes a LandSandBoat ``item_mods``
row.  Percentages follow the server's own conventions (``modifiers.py``):
haste, damage taken and critical hit rate are hundredths of a percent, while
Store TP, Fast Cast, Double Attack and Physical damage limit are whole
percents.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "limbus_r30.json"
DOCS = ROOT / "docs" / "limbus-r30.md"
SQL = ROOT / "database" / "migrations" / "0099_limbus_r30.sql"
GEARSWAP = ROOT / "gearswap"

# The two characters the award goes to: Onedough (account onedough) and
# Twodough (account onedough-2).
CHARACTERS = (1, 2)

# Wardrobes and storage, in the order migration 66/72 fill them.
CONTAINERS = (
    (8, 1), (10, 2), (11, 3), (12, 4), (13, 5), (14, 6), (15, 7), (16, 8),
    (1, 9), (5, 10), (6, 11), (7, 12), (9, 13),
)

SLOT_MASK = {"head": 16, "body": 32, "hands": 64, "legs": 128, "feet": 256}

SLOTS = ("head", "body", "hands", "legs", "feet")

# The gearswap copy of each family, one build per augment choice a set needs.
# The number is the 0-based Rank 30 row the build carries: Duty's Store TP row
# for TP, its accuracy row for weaponskills; Revelation's Double Attack for TP
# and its physical-damage-limit row for weaponskills; Sworn's Phalanx-received
# row for the tank fast-cast set and its Triple Attack row elsewhere; etc.
VARIANTS = {
    "justice": {"tp": 1, "ws": 0},
    "hope": {"tp": 1, "ws": 2},
    "trust": {"ta": 1, "phalanx": 2, "acc": 0},
    "bravery": {"cast": 1},
    "mercy": {"tp": 2, "ws": 0},
}

# Where each family goes in the existing libraries.  Weighted by how the job
# community rates the suit (see docs/limbus-r30.md): Duty is the one worn
# outright, Revelation is a 3/5 bard TP set (head and hands keep their Odyssey
# pieces), Sworn is fast-cast/tank gear plus DRK's hybrid head and feet, and
# Clemency only beats the defaults in the head and feet slots of the
# two-handers.  Bravery stays a container: casters rate it below their AF/relic
# pieces.  Nyame Path B is deliberately untouched -- it is still the
# weaponskill set -- and so are the Subtle Blow sets Malignance owns.
#
# The rewrite is additive per slot: only the slots named here are replaced, so
# dropping a slot from the table leaves the item the library had (or the last
# generated value, which then has to be restored by hand).
PLACEMENT = {
    "MNK": {"sets.engaged.tp": {slot: ("justice", "tp") for slot in SLOTS}},
    "THF": {"sets.engaged.tp": {slot: ("justice", "tp") for slot in SLOTS},
            "sets.engaged.hybrid": {slot: ("justice", "tp") for slot in SLOTS}},
    "DNC": {"sets.engaged.tp": {slot: ("justice", "tp") for slot in SLOTS},
            "sets.engaged.hybrid": {slot: ("justice", "tp") for slot in SLOTS}},
    "BST": {"sets.engaged.tp": {slot: ("justice", "tp") for slot in SLOTS}},
    "PUP": {"sets.engaged.tp": {slot: ("justice", "tp") for slot in SLOTS}},
    "NIN": {"sets.engaged.tp": {slot: ("hope", "tp") for slot in SLOTS},
            "sets.engaged.hybrid": {slot: ("hope", "tp") for slot in SLOTS}},
    "BRD": {"sets.engaged.tp": {slot: ("hope", "tp") for slot in ("body", "legs", "feet")}},
    "PLD": {"sets.precast.FC": {slot: ("trust", "phalanx") for slot in SLOTS}},
    "RUN": {"sets.precast.FC": {slot: ("trust", "phalanx") for slot in SLOTS}},
    "RDM": {"sets.precast.FC": {slot: ("trust", "ta") for slot in SLOTS}},
    "DRK": {"sets.engaged.tp": {"head": ("trust", "ta"), "feet": ("trust", "ta")},
            "sets.engaged.hybrid": {"head": ("trust", "ta"), "feet": ("trust", "ta")},
            "sets.WS.Resolution": {"head": ("trust", "acc"), "feet": ("trust", "acc")},
            "sets.WS.Torcleaver": {"head": ("trust", "acc"), "feet": ("trust", "acc")}},
    "SAM": {"sets.engaged.tp": {"head": ("mercy", "tp"), "feet": ("mercy", "tp")}},
    "DRG": {"sets.engaged.tp": {"head": ("mercy", "tp"), "feet": ("mercy", "tp")}},
}

# (wiki phrase, modifier id, value multiplier).  Longer phrases first so that
# "Magic Accuracy" wins over "Accuracy" and "Ranged Attack" over "Attack".
MODS = (
    ("Physical damage limit", 1081, 1),
    ("Magic Atk. Bonus", 28, 1),
    ("Magic Def. Bonus", 29, 1),
    ("Magic Accuracy", 30, 1),
    ("Magic Evasion", 31, 1),
    ("Ranged Accuracy", 26, 1),
    ("Ranged Attack", 24, 1),
    ("Critical hit rate", 165, 100),
    ("Double Attack", 288, 1),
    ("Triple Attack", 302, 1),
    ("Subtle Blow", 289, 1),
    ("Store TP", 73, 1),
    ("Fast Cast", 170, 1),
    ("Magic Damage", 311, 1),
    ("Damage taken", 160, 100),
    ("Enmity", 27, 1),
    ("Haste", 384, 100),
    ("Evasion", 68, 1),
    ("Accuracy", 25, 1),
    ("Attack", 23, 1),
    ("Regen", 370, 1),
    ("DEF", 1, 1),
    ("HP", 2, 1),
    ("MP", 5, 1),
    ("STR", 8, 1),
    ("DEX", 9, 1),
    ("VIT", 10, 1),
    ("AGI", 11, 1),
    ("INT", 12, 1),
    ("MND", 13, 1),
    ("CHR", 14, 1),
)

# 24-byte Exdata::AugmentBundle, rank 30 / tier 3 (the 30-rank unlock), index 0.
# Mirrors server/fanxi_server/game/augments.py; the per-item bundle index is not
# known yet, so the block names no effects and !r30 prints the rows instead.
R30_EXDATA = bytes([0x03, 0x83, 0x00, 0x00, 0x00, 0x00, 0xF8, 0x01]
                   + [0x00] * 4 + [0x00] * 12)

PHRASE = re.compile(
    r"(?P<name>%s)\"?\s*(?:[:+])?\s*(?P<sign>[+-])?\s*(?P<num>\d+)\s*%%?"
    % "|".join(re.escape(name) for name, _, _ in sorted(MODS, key=lambda m: len(m[0]), reverse=True))
)


def load() -> dict:
    return json.loads(DATA.read_text())


def families(data: dict) -> list[dict]:
    """Every family, in dataset order, with its top-tier pieces sorted by slot."""
    order = ("head", "body", "hands", "legs", "feet")
    out = []
    for key, family in data["families"].items():
        pieces = [family["pieces"][slot] for slot in order if slot in family["pieces"]]
        out.append({"key": key, **family, "pieces": pieces})
    return out


def jobs_mask(data: dict, family: dict) -> int:
    bits = data["job_bit"]
    mask = 0
    for job in family["jobs"]:
        mask |= 1 << (int(bits[job]) - 1)
    return mask


def lua_string(value: str) -> str:
    if '"' in value:
        return "'%s'" % value
    return '"%s"' % value


def lua_name(data: dict, key: str) -> str:
    """``justice`` -> ``duty``: the table and set names use the top-tier suit."""
    return data["families"][key]["set"].split()[0].lower()


def lua_item(piece: dict, index: int) -> str:
    rows = piece["augments"]
    augment = rows[index] if index < len(rows) else rows[0]
    return "{ name = %s, augments = {%s} }" % (
        lua_string(piece["name"]), lua_string(augment))


def lua_table(data: dict) -> str:
    """The ``local limbus`` table every library carries."""
    lines = [
        "-- Limbus Rank 30 builds: the top tier of all five families, one copy",
        "-- per augment choice a set needs (TP, weaponskill, fast cast, tank).",
        "-- Generated from data/limbus_r30.json by tools/gen_limbus_r30.py.",
        "local limbus = {",
    ]
    for key, family in data["families"].items():
        lines.append("    %s = {" % lua_name(data, key))
        for variant, index in VARIANTS[key].items():
            lines.append("        %s = {" % variant)
            for slot in SLOTS:
                lines.append("            %s = %s," % (slot, lua_item(family["pieces"][slot], index)))
            lines.append("        },")
        lines.append("    },")
    lines.append("}")
    return "\n".join(lines)


def families_for(job: str, data: dict) -> list[str]:
    return [key for key, family in data["families"].items() if job in family["jobs"]]


def lua_sets(job: str, data: dict) -> str:
    """The ``sets.Limbus`` container for one job."""
    lines = [
        "    -- ===== Limbus Rank 30 sets =================================",
        "    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear",
    ]
    for key in families_for(job, data):
        name = lua_name(data, key)
        for variant in VARIANTS[key]:
            slots = ", ".join("%s = limbus.%s.%s.%s" % (slot, name, variant, slot)
                              for slot in SLOTS)
            lines.append("    sets.Limbus.%s_%s = { %s }" % (name, variant, slots))
    return "\n".join(lines) + "\n"


def replace_table(text: str, header: str, table: str) -> str:
    """Swap (or insert) a whole ``local <name> = {...}`` block."""
    start = text.find(header)
    if start >= 0:
        end = text.find("\n}\n", start)
        if end < 0:
            raise SystemExit("unterminated %r table" % header)
        head = text[:start].rstrip("\n").split("\n")
        while head and (head[-1].startswith("-- Limbus Rank 30") or not head[-1].strip()):
            head.pop()
        return "\n".join(head) + "\n\n" + table + text[end + 2:]
    anchor = text.find("function get_sets()")
    if anchor < 0:
        raise SystemExit("no get_sets() anchor for %r" % header)
    return text[:anchor] + table + "\n\n" + text[anchor:]


def replace_sets_block(text: str, block: str) -> str:
    marker = "    -- ===== Limbus Rank 30 sets"
    if marker in text:
        start = text.index(marker)
        end = text.find("    -- ===== ", start + len(marker))
        if end < 0:
            raise SystemExit("cannot find the end of the Limbus sets")
        return text[:start] + block + "\n" + text[end:]
    anchor = text.find("    -- ===== idle")
    if anchor < 0:
        raise SystemExit("no idle set anchor")
    return text[:anchor] + block + "\n" + text[anchor:]


def replace_set_items(text: str, path: str, items: dict, data: dict) -> str:
    """Rewrite the armour slots of one ``sets.<path> = {...}`` literal."""
    opener = "    %s = {\n" % path
    start = text.find(opener)
    if start < 0:
        raise SystemExit("set %s not found (or not a literal table)" % path)
    end = text.find("\n    }\n", start)
    if end < 0:
        raise SystemExit("set %s has no closing brace" % path)
    block = text[start:end].split("\n")
    for slot, (key, variant) in items.items():
        line = "        %s = limbus.%s.%s.%s," % (slot, lua_name(data, key), variant, slot)
        for index, existing in enumerate(block):
            if existing.startswith("        %s = " % slot):
                block[index] = line
                break
        else:
            block.insert(len(block) - 1, line)
    return text[:start] + "\n".join(block) + text[end:]


def apply_lua(data: dict) -> list[str]:
    """Rewrite every ``gearswap/*.lua`` library: build table, sets, placements."""
    table = lua_table(data)
    changed = []
    for path in sorted(GEARSWAP.glob("*.lua")):
        job = path.stem.upper()
        text = path.read_text()
        original = text
        text = replace_table(text, "local limbus = {", table)
        text = replace_sets_block(text, lua_sets(job, data))
        for set_path, items in PLACEMENT.get(job, {}).items():
            text = replace_set_items(text, set_path, items, data)
        if text != original:
            path.write_text(text)
            changed.append(str(path.relative_to(ROOT)))
    return changed


def modifiers(piece: dict) -> list[tuple[int, int]]:
    """(modifier id, value) rows for one piece's base stats.

    Pet, avatar and wyvern lines are dropped: the engine has no pet sheet yet,
    so their numbers would never be read.
    """
    text = " ".join(piece["stats"])
    text = re.split(r"\b(?:Pet|Avatar|Wyvern|Summoned Pet):", text)[0]
    totals: dict[int, int] = {}
    for match in PHRASE.finditer(text):
        name = match.group("name")
        value = int(match.group("num"))
        if match.group("sign") == "-":
            value = -value
        for phrase, mod_id, scale in MODS:
            if phrase == name:
                totals[mod_id] = totals.get(mod_id, 0) + value * scale
                break
    return sorted(totals.items())


def sql_item(piece: dict, family: dict, mask: int) -> str:
    name = piece["name"].replace("'", "''")
    return " (%d,'%s',1,0,'%s',99,'Limbus Su5 armour (%s).',0,%d,%d)," % (
        piece["item_id"], name, piece["slot"], family["set"], SLOT_MASK[piece["slot"]], mask)


def render_sql(data: dict) -> str:
    fams = families(data)
    pieces = [piece for family in fams for piece in family["pieces"]]
    piece_ids = ", ".join(str(piece["item_id"]) for piece in sorted(pieces, key=lambda p: p["item_id"]))
    ids = [piece["item_id"] for piece in pieces]

    lines = [
        "-- Limbus Rank 30 armour (migration 99).",
        "--",
        "-- Adds the top tier of all five Limbus families -- Duty, Revelation,",
        "-- Sworn, Indomitable and Clemency -- then grants the 25 pieces to",
        "-- characters 1 and 2 (Onedough and Twodough) with the Rank 30 augment",
        "-- block in the item exdata.  Lower tiers are not added: they are the",
        "-- same suit one and two steps down.",
        "--",
        "-- Item ids, slots, job masks and stat lines are factual game data from",
        "-- BG Wiki (the set pages and each item page's ffxidb link).  The",
        "-- 24-byte block is LandSandBoat's Exdata::AugmentBundle with rank 30 /",
        "-- tier 3, the shape migration 75 wrote for Odyssey; the per-item",
        "-- augment bundle index is not known yet, so it stays 0 and !r30 is",
        "-- the in-game view of the rows (docs/limbus-r30.md).",
        "--",
        "-- Generated from data/limbus_r30.json by tools/gen_limbus_r30.py.",
        "",
        "INSERT OR IGNORE INTO items",
        " (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES",
    ]
    lines += [sql_item(piece, family, jobs_mask(data, family)).rstrip(",") + ","
              for family in fams for piece in family["pieces"]]
    lines[-1] = lines[-1].rstrip(",") + ";"

    lines += ["", "-- Base modifiers from each piece's stat line.", "",
              "INSERT OR REPLACE INTO item_mods (item_id,mod_id,value) VALUES"]
    rows = []
    for piece in sorted(pieces, key=lambda p: p["item_id"]):
        mods = modifiers(piece)
        if not mods:
            raise SystemExit("no modifiers parsed for %s" % piece["name"])
        rows.append("  " + ", ".join("(%d,%d,%d)" % (piece["item_id"], mod_id, value)
                                     for mod_id, value in mods))
    lines.append(",\n".join(rows) + ";")

    lines += [
        "",
        "-- Give every piece to both characters, into their first free wardrobe slots.",
        "WITH RECURSIVE",
        "  target(character_id) AS (",
        "    SELECT id FROM characters WHERE id IN (%s)" % ", ".join(str(c) for c in CHARACTERS),
        "  ),",
        "  containers(container, ord) AS (",
        "    VALUES " + ",".join("(%d,%d)" % pair for pair in CONTAINERS),
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
        "    FROM target t CROSS JOIN (" + " UNION ALL ".join(
            "SELECT %d AS item_id" % i for i in sorted(ids)) + ") AS w",
        "    WHERE NOT EXISTS (",
        "      SELECT 1 FROM char_inventory ci",
        "      WHERE ci.character_id = t.character_id AND ci.item_id = w.item_id",
        "    )",
        "  )",
        "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)",
        "SELECT w.character_id, f.container, f.slot, w.item_id, 1",
        "FROM want w JOIN free f ON f.character_id = w.character_id AND f.rn = w.rn;",
        "",
        "-- Rank 30 augment block (rank 30, tier 3, bundle index 0).",
        "UPDATE char_inventory SET extra = X'%s'" % R30_EXDATA.hex().upper(),
        "WHERE character_id IN (%s)" % ", ".join(str(c) for c in CHARACTERS),
        "  AND item_id IN (%s);" % piece_ids,
        "",
    ]
    return "\n".join(lines)


def render_docs(data: dict) -> str:
    fams = families(data)
    lines = [
        "# Limbus Rank 30 armour",
        "",
        "The five Limbus families at their **top tier** -- item level 119, Superior 5 --",
        "with every **Rank 30** augment row. Each family climbs three tiers:",
        "",
        "| Family | Base (Su4) | Middle (Su4) | Top (Su5) | Jobs |",
        "| --- | --- | --- | --- | --- |",
    ]
    for family in fams:
        base, middle, top = family["chain"]
        lines.append("| %s | %s | %s | **%s** | %s |" % (
            family["key"].capitalize(), base, middle, top, " / ".join(family["jobs"])))

    lines += [
        "",
        "All 25 top-tier pieces are granted at Rank 30 to characters 1 and 2",
        "(Onedough/Twodough) by `database/migrations/0099_limbus_r30.sql`.",
        "The same data drives the script that writes that migration and this page:",
        "`data/limbus_r30.json` and `tools/gen_limbus_r30.py`.",
        "",
        "Augments are chosen at the Limbus furnaces with a *Jewel of Des.*; a piece",
        "picks **one** of the four numbered rows below, and Rank 30 is the maximum",
        "rank for each.",
    ]

    for family in fams:
        base, middle, top = family["chain"]
        lines += [
            "",
            "## %s" % family["set"],
            "",
            "- **Family:** %s (%s -> %s -> %s)" % (
                family["key"].capitalize(), base, middle, top),
            "- **Jobs:** %s" % " / ".join(family["jobs"]),
            "- **Item level:** 119, Superior %d" % family["su"],
            "",
            "| Piece | Slot | Item ID | [1] | [2] | [3] | [4] |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for piece in family["pieces"]:
            rows = list(piece["augments"]) + [""] * (4 - len(piece["augments"]))
            cells = [cell.replace("|", "\\|") for cell in rows]
            lines.append("| %s | %s | %d | %s |" % (
                piece["name"], piece["slot"], piece["item_id"], " | ".join(cells)))

    lines += [
        "",
        "## Where they go in the libraries",
        "",
        "The community read (a Japanese dragoon's January 2026 run-down of all five",
        "suits, [tukaware.fc2.net](https://tukaware.fc2.net/blog-entry-547.html), and the",
        "[FFXIAH Limbus 2025 thread](https://www.ffxiah.com/forum/topic/58447/limbus-2025/)) is:",
        "",
        "- **Duty (Justice)** is the strongest of the five, and the one people wear outright.",
        "  MNK/THF/DNC call it best-in-slot, BST/PUP a clear upgrade; WAR passes because",
        "  Sakpata's already does the job. Double Attack + Subtle Blow base, Store TP /",
        "  Triple Attack augments, and enough Accuracy/Attack to displace Odyssey and",
        "  Malignance wherever the set is not there to cap Subtle Blow or stack DT.",
        "- **Revelation (Hope)** is the melee-bard suit: BRD runs a 3/5 (body, legs, feet)",
        "  and keeps Odyssey in head and hands, where Bunzi's and friends stay competitive.",
        "  NIN takes it as a sidegrade with more Magic Evasion; WAR passes.",
        "- **Sworn (Trust)** is PLD/RUN fast-cast and tank gear (the *Phalanx received* row",
        "  is the draw), RDM's enspell/FC set, and DRK's hybrid head and feet once Triple",
        "  Attack unlocks past R15. WHM/BLU skip it.",
        "- **Indomitable (Bravery)** is rated below the casters' AF/relic pieces in every",
        "  slot; it ships here as a container, not as a default.",
        "- **Clemency (Mercy)** is the weakest of the five -- Enmity- sits where Store TP",
        "  would have been -- but its head and feet beat what SAM/DRG otherwise have, its",
        "  Physical damage limit helps multi-hit weaponskills, and the accuracy row is a",
        "  reasonable Resolution/Torcleaver piece.",
        "",
        "What the suits do **not** replace: Nyame Path B stays the weaponskill set (flat WSD",
        "beats the new pieces for single-hit WS), Malignance/Sakpata's keep their Subtle Blow",
        "slots, and an unaugmented Limbus piece loses to R30 Odyssey gear -- the multi-attack",
        "and PDL only turn on past roughly Rank 15, which is why most players cherry-pick",
        "one or two slots per job instead of building all five.",
        "",
        "`tools/gen_limbus_r30.py --lua` writes a `local limbus` build table and a",
        "`sets.Limbus` container into every library, then puts the pieces where the table",
        "below says:",
        "",
        "| Job | Set touched | Slots | Build |",
        "| --- | --- | --- | --- |",
    ]
    for job, placement in PLACEMENT.items():
        for set_path, items in placement.items():
            key, variant = next(iter(items.values()))
            row = VARIANTS[key][variant] + 1
            family = data["families"][key]["set"].split()[0]
            lines.append("| %s | `%s` | %s | %s %s, R30 [%d] |" % (
                job, set_path, ", ".join(slot for slot in SLOTS if slot in items),
                family, variant, row))

    lines += [
        "",
        "Jobs not listed keep their defaults and only gain the `sets.Limbus` container;",
        "the five-piece copy in every variant carries the same augment choice so a set can",
        "be worn as a unit.",
        "",
        "## Notes",
        "",
        "- Item ids come from each item page's ffxidb link on BG Wiki; the names are the",
        "  in-game ones, which are abbreviated where the 15-character limit bites",
        "  (`Revelation Plate.`, `Clemen. Hara.`).",
        "- The base stat lines are copied verbatim and turned into `item_mods` by the",
        "  generator. Pet, avatar and wyvern rows are recorded here but not stored: the",
        "  engine has no pet sheet yet, so nothing would read them.",
        "- The 24-byte exdata block says rank 30 / tier 3, but its augment bundle index",
        "  is still unknown (LandSandBoat has no Limbus augment table), so the client",
        "  cannot print the four rows on a tooltip. `!r30 <piece>` prints them in game,",
        "  the same way `!r30` covers Odyssey.",
        "- Sources: " + ", ".join(data["source"]),
        "",
        "## Client data",
        "",
        "These items only exist in the client's own item table from the 2026 updates.",
        "A 2025-07-03 client (client version `30250704_0`, the build `meta/builds.json`",
        "labels `2025-07-03`) has ids 24122-24194 unused, so it draws the null record --",
        "no name, \"All jobs\", `Lv.127` -- no matter what the server sends. Check a folder",
        "with `tools/newbuild.py identify --game <folder>`; `tools/prepare.py` only accepts",
        "a build `meta/builds.json` lists. The 2026-10-05 install used to check this was",
        "client version `30261006_0` and is not in that list yet.",
        "",
    ]
    return "\n".join(lines)


def write(path: Path, text: str, check: bool) -> bool:
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if current == text:
        return True
    if check:
        print("out of date: %s" % path.relative_to(ROOT), file=sys.stderr)
        return False
    path.write_text(text, encoding="utf-8")
    print("wrote %s" % path.relative_to(ROOT))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sql", action="store_true", help="write the migration")
    parser.add_argument("--docs", action="store_true", help="write the docs page")
    parser.add_argument("--lua", action="store_true", help="rewrite gearswap/*.lua")
    parser.add_argument("--all", action="store_true", help="write everything")
    parser.add_argument("--check", action="store_true", help="fail if anything is stale")
    args = parser.parse_args()
    if not (args.sql or args.docs or args.lua or args.all or args.check):
        parser.print_help()
        return 2

    data = load()
    ok = True
    if args.sql or args.all or args.check:
        ok &= write(SQL, render_sql(data), args.check)
    if args.docs or args.all or args.check:
        ok &= write(DOCS, render_docs(data), args.check)
    if args.lua or args.all:
        for relative in apply_lua(data):
            print("wrote %s" % relative)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
