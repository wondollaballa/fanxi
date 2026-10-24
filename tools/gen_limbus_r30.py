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
                wears in the existing sets (including bracket-named midcast sets);
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
import struct
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
# two-handers.  Bravery is SCH's raw-nuke/enfeebling/FC suit: every R30 piece
# carries Mag. Acc+42 and "Magic Atk. Bonus"+40 before the augment rows, so it
# takes the Elemental/Helix/Enfeebling bodies, the FC body and legs, the
# Elemental Macc five-piece and a dedicated idle/DT build.  The job's functional
# pieces stay where they are: Arbatel Loafers +3 in the free-nuke and helix
# feet ("Klimaform"+25), Arbatel Bracers +3 in helix, and the whole Enhancing
# Magic and Healing Magic sets.  Nyame Path C keeps the Magic Burst variant,
# which is where the Magic Burst Damage II rows live.
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
    "SCH": {
        # Free nuke: Indomitable head/body/legs, Nyame C hands and Arbatel
        # Loafers +3 feet (the "+25 Klimaform" and Magic Burst terms).
        "sets.midcast.Elemental Magic": {
            "head": ("bravery", "cast"), "body": ("bravery", "cast"),
            "legs": ("bravery", "cast")},
        # Landing set: the same M.Acc logic as Enfeebling, all five pieces.
        "sets.midcast.Elemental Magic Macc": {
            slot: ("bravery", "cast") for slot in SLOTS},
        # Helix landing/DoT: Indomitable head/body/legs, Arbatel hands and feet.
        "sets.midcast.Helix": {
            "head": ("bravery", "cast"), "body": ("bravery", "cast"),
            "legs": ("bravery", "cast")},
        # Enfeebling: the INT/MND body, hands and legs; head and feet keep the
        # duration/M.Acc pieces the live file already has.
        "sets.midcast.Enfeebling Magic": {
            "body": ("bravery", "cast"), "hands": ("bravery", "cast"),
            "legs": ("bravery", "cast")},
        # Fast cast: the suit's own 10% body and 8% legs, with the FC accessories.
        "sets.precast.FC": {
            "body": ("bravery", "cast"), "legs": ("bravery", "cast")},
        # Balanced idle/DT: five pieces plus the DT accessories.  Max PDT/MDT
        # stay on Nyame, whose per-piece DT (7-9%) is higher than Bravery's.
        "sets.idle.dt_indom": {
            slot: ("bravery", "cast") for slot in SLOTS},
    },
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

# 24-byte Exdata::AugmentBundle: rank 30 / tier 3 (the 30-rank unlock) and the
# piece's own bundle index in the client's augment table.  Limbus RP uses curve
# B, whose rank-30 total is 55,800 (rank 1 costs 1,600 -- the number the FFXIAH
# thread quotes).  Mirrors server/fanxi_server/game/augments.py.
R30_RP = 55800
R30_CURVE = 1


def exdata(data: dict, piece: dict) -> bytes:
    """The 24-byte augment block for one piece: rank 30, 55,800 RP, its bundle."""
    rank = int(data.get("rank", 30))
    tier = 3
    rp = int(data.get("rp", R30_RP))
    curve = int(data.get("rp_curve", R30_CURVE))
    bundle = piece.get("bundle")
    if bundle is None:
        raise SystemExit("no augment bundle for %s" % piece["name"])
    value = ((rank & 0x1F) << 18) | ((tier & 0x03) << 23) | ((curve & 0x03) << 26) \
        | ((rp & 0xFFFF) << 2)
    block = bytearray(24)
    block[0] = 0x03
    block[1] = 0x83
    struct.pack_into("<I", block, 4, value)
    struct.pack_into("<I", block, 8, int(bundle) & 0xFFFFFFFF)
    return bytes(block)

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


LUA_KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for", "function",
    "if", "in", "local", "nil", "not", "or", "repeat", "return", "then",
    "true", "until", "while",
}
LUA_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def lua_set_expression(path: str) -> str:
    """``sets.midcast.Elemental Magic`` -> the Lua table constructor expression."""
    expression = "sets"
    for segment in path.split(".")[1:]:
        if LUA_IDENTIFIER.match(segment) and segment not in LUA_KEYWORDS:
            expression += "." + segment
        else:
            expression += "[%s]" % lua_string(segment)
    return expression


def lua_set_alternatives(path: str) -> list[str]:
    """The expression plus its bracketed last segment (``[...]`` is optional there).

    The libraries quote every midcast name -- ``sets.midcast["Helix"]`` even
    where ``sets.midcast.Helix`` would parse -- so a placement has to accept
    both spellings for a one-word set.
    """
    expression = lua_set_expression(path)
    head, _, last = path.rpartition(".")
    if head and LUA_IDENTIFIER.match(last) and last not in LUA_KEYWORDS:
        expression_bracketed = "%s[%s]" % (lua_set_expression(head), lua_string(last))
        if expression_bracketed != expression:
            return [expression, expression_bracketed]
    return [expression]


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
        while head and (
            not head[-1].strip()
            or head[-1].startswith("-- Limbus Rank 30")
            or head[-1].startswith("-- per augment choice")
            or head[-1].startswith("-- Generated from data/limbus_r30.json")
        ):
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
    opener = next(("    %s = {\n" % expression
                   for expression in lua_set_alternatives(path)
                   if "    %s = {\n" % expression in text), None)
    if opener is None:
        raise SystemExit("set %s not found (or not a literal table)" % path)
    start = text.find(opener)
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
        "-- tier 3 and the piece's own augment bundle index; Limbus uses RP curve",
        "-- B, whose rank-30 total is 55,800.  The bundle indices are the client's",
        "-- own table (LandSandBoat's xi.data.augments.bundles, parsed from the",
        "-- MNC2 data); they were matched to the Rank 30 rows in",
        "-- docs/limbus-r30.md by content.",
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
        "-- Rank 30 augment block for every copy: rank 30, tier 3, 55,800 RP",
        "-- (curve B), and the piece's own bundle index.  Updating by item id",
        "-- covers both main characters and any later copy of the suit.",
    ]
    lines += [
        "UPDATE char_inventory SET extra = X'%s' WHERE item_id = %d;" % (
            exdata(data, piece).hex().upper(), int(piece["item_id"]))
        for piece in sorted(pieces, key=lambda p: p["item_id"])
    ]
    lines.append("")
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
        "(Onedough/Twodough) by `database/migrations/0099_limbus_r30.sql`, and",
        "migration `0104_limbus_rp30.sql` re-stamps any copy already in a bag.",
        "The same data drives the script that writes that migration and this page:",
        "`data/limbus_r30.json` and `tools/gen_limbus_r30.py`.",
        "",
        "Every augment line on every piece is already at its Rank 30 value. The four",
        "numbered columns are the four augment lines a piece carries, not a choice:",
        "each line unlocks at a different rank, and all four are live at 30. The",
        "item exdata also records 55,800 RP, the curve-B total for rank 30 (rank 1",
        "costs 1,600), so the client reads the block at rank 30, not rank 0.",
        "",
        "Each piece carries its own client augment **bundle** index. The indices",
        "come from the client's bundle table (LandSandBoat's",
        "`xi.data.augments.bundles`, parsed from the MNC2 data); every one was",
        "matched to the Rank 30 row above by content. `!rp30` re-stamps the",
        "pieces in a character's bags, and `!r30 <piece>` prints the rows.",
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
            "| Piece | Slot | Item ID | Bundle | [1] | [2] | [3] | [4] |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for piece in family["pieces"]:
            rows = list(piece["augments"]) + [""] * (4 - len(piece["augments"]))
            cells = [cell.replace("|", "\\|") for cell in rows]
            lines.append("| %s | %s | %d | %d | %s |" % (
                piece["name"], piece["slot"], piece["item_id"], int(piece["bundle"]),
                " | ".join(cells)))

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
        "- **Indomitable (Bravery)** is SCH's raw-nuke, enfeebling and fast-cast suit.",
        "  Every R30 piece carries Mag. Acc+42 and \"Magic Atk. Bonus\"+40 before the",
        "  augment rows, plus Magic Damage+22, native Fast Cast and 2-6% Damage taken; the",
        "  Rank 30 Mag. Acc+30 / \"Magic Atk. Bonus\"+28-32 rows take it to 72 M.Acc and",
        "  68-72 MAB a piece. SCH wears head/body/legs for free nukes and helix,",
        "  body/hands/legs for enfeebles, body/legs in fast cast, the full five in the",
        "  elemental M.Acc set and a five-piece `sets.idle.dt_indom`. Arbatel Loafers +3",
        "  stays in the free-nuke and helix feet (\"Klimaform\"+25 and Magic Burst Damage",
        "  II +5), Arbatel Bracers +3 stays in helix, and the Enhancing Magic and Healing",
        "  Magic sets are untouched.",
        "- **Clemency (Mercy)** is the weakest of the five -- Enmity- sits where Store TP",
        "  would have been -- but its head and feet beat what SAM/DRG otherwise have, its",
        "  Physical damage limit helps multi-hit weaponskills, and the accuracy row is a",
        "  reasonable Resolution/Torcleaver piece.",
        "",
        "What the suits do **not** replace: Nyame Path B stays the weaponskill set (flat WSD",
        "beats the new pieces for single-hit WS), Malignance/Sakpata's keep their Subtle Blow",
        "slots, and an unaugmented Limbus piece loses to R30 Odyssey gear -- the multi-attack",
        "and PDL only turn on past roughly Rank 15, which is why most melee players cherry-pick",
        "one or two slots per job instead of building all five. The casters are the exception:",
        "for SCH every Indomitable piece is 72 M.Acc and 22 Magic Damage, so the Elemental",
        "Macc set takes all five, enfeebling and the damage sets take three, and fast cast two.",
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
        "On SCH the Magic Burst variant (`sets.midcast.Elemental Magic MB`) deliberately",
        "stays on Nyame Path C for its Magic Burst Damage II rows, and the max PDT/MDT",
        "idle sets stay on Nyame because its per-piece Damage taken (7-9%) is higher than",
        "Indomitable's (2-6%). The new `sets.idle.dt_indom` is the balanced DT build.",
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
        "- The 24-byte exdata block is rank 30 / tier 3 / 55,800 RP (curve B) with",
        "  the piece's own augment bundle index, so the client prints the four rows",
        "  on the tooltip. `!r30 <piece>` still prints them in chat, and `!rp30`",
        "  re-stamps every Limbus piece a character is carrying.",
        "- The bundle indices sit in the client table as 472-496: 477-481 Duty,",
        "  472-476 Revelation, 487-491 Sworn, 482-486 Indomitable and 492-496",
        "  Clemency. Bundles 458-471 are other Su5 entries this dataset does not grant.",
        "- The pieces carry the client's own armour models: Revelation MId 513, Sworn",
        "  514, Indomitable 515, Duty 516 and Clemency 517.  The raw grap model is the",
        "  slot base (0x1000 head, 0x2000 body, 0x3000 hands, 0x4000 legs, 0x5000 feet)",
        "  plus that MId.  The values come from xi-tools' `mv/lists/characters.json`;",
        "  migration 107 writes them, and `tools/item_models.json` keeps them for new",
        "  grants and cloned characters.",
        "- Sources: " + ", ".join(data["source"]),
        "",
        "## Client data",
        "",
        "These items only exist in the client's own item table from the 2026 updates.",
        "A 2025-07-03 client (client version `30250704_0`, the build `meta/builds.json`",
        "labels `2025-07-03`) has ids 24122-24194 unused, so it draws the null record --",
        "no name, \"All jobs\", `Lv.127` -- no matter what the server sends. Check a folder",
        "with `tools/newbuild.py identify --game <folder>`; `tools/prepare.py` only accepts",
        "a build `meta/builds.json` lists. The build this page was checked against is the",
        "2026-10-05 install, client version `30261006_0`, which `meta/builds.json` lists.",
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
