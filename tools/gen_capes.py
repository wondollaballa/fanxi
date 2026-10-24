#!/usr/bin/env python3
"""Write the Ambuscade cape augment migrations and docs.

    python3 tools/gen_capes.py          # rewrite the generated files
    python3 tools/gen_capes.py --check  # fail if they are out of date
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import capes  # noqa: E402

MIGRATIONS = {
    "BST": ROOT / "database/migrations/0078_bst_capes.sql",
    "NIN": ROOT / "database/migrations/0082_nin_capes.sql",
    "DRK": ROOT / "database/migrations/0088_drk_capes.sql",
    "BLM": ROOT / "database/migrations/0101_blm_capes.sql",
}
DOC = ROOT / "docs/capes.md"

# Which builds are new copies, and where.  The copy the character already owns takes
# ORDER[job][0]; the rest are new copies.
ORDER = {
    "BST": ["tp", "pdt", "mdt", "maxhp", "dt", "ws_str", "mabws", "pet_tp", "pet_dt"],
    "NIN": ["tp", "pdt", "mdt", "maxhp", "dt", "dw", "fc", "ninjutsu",
            "ws_agi", "ws_dex", "ws_str"],
    "DRK": ["tp", "pdt", "mdt", "maxhp", "dt", "fc", "macc", "ws_str", "ws_int",
            "enmity"],
    "BLM": ["tp", "pdt", "mdt", "maxhp", "dt", "fcmp", "macc", "nuke", "mabws"],
}

# Beastmaster: the bag copy at slot 80 and eight explicit free bag slots (the same
# layout migration 78 has used since it was written).
BST_EXISTING = (0, 80)
BST_SLOTS = [(0, 1), (0, 14), (0, 18), (0, 19), (0, 20), (0, 21), (0, 23), (0, 24)]

# Ninja: the wardrobe copy the default-library grant left is the only unaugmented
# one; the other ten go into the first free main-bag slots at migration time.
NIN_WHERE = "AND (extra IS NULL OR length(extra) = 0)"

# Dark Knight: the wardrobe copy at slot 21 is unaugmented; the other nine go into
# the first free wardrobe-3 slots.  The cape's job is read from its item name, so
# the same !cape command works for all four jobs.
DRK_WHERE = "AND (extra IS NULL OR length(extra) = 0)"
DRK_SLOTS = [(11, slot) for slot in range(1, 10)]

# Black Mage: the wardrobe copy is the same one the default-library grant left
# unaugmented.  The inventory and the first five wardrobes are full, so the eight
# new copies take the free slots at the end of wardrobe 6 (container 14).
BLM_WHERE = "AND (extra IS NULL OR length(extra) = 0)"
BLM_SLOTS = [(14, slot) for slot in range(66, 74)]


def _header(job: str) -> list[str]:
    entry = capes.JOBS[job]
    total = len(ORDER[job])
    if job == "BST":
        where = "already in the bag"
    else:
        where = "already in the wardrobe"
    return [
        "-- Ambuscade JSE cape augments (migration %s)." % (
            "78" if job == "BST" else "82"),
        "--",
        "-- Job capes are standard five-slot augments: kind 0x02, subkind 0x03,",
        "-- five little-endian words of {id:11, value:5}, then twelve zero bytes.",
        "-- The client renders each word as (value + offset) * multiplier using the",
        "-- per-id table in docs/capes.md; the ids come from the client's augment",
        "-- table (the same space LandSandBoat's Magian items use).",
        "--",
        "-- The %s %s takes the %s build; the other" % (
            entry["cape_name"], where, ORDER[job][0]),
        "-- %s builds are new copies in free bag slots." % _word(total - 1),
        "",
    ]


def _word(number: int) -> str:
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
             6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    return words.get(number, str(number))


def sql(job: str = "BST") -> str:
    if job == "DRK":
        return _drk_sql()
    if job == "BLM":
        return _blm_sql()
    entry = capes.JOBS[job]
    order = ORDER[job]
    lines = _header(job)
    if job == "BST":
        lines.append("UPDATE char_inventory SET extra = X'%s'" % capes.encode(order[0], job).hex().upper())
        lines.append(" WHERE character_id = 1 AND item_id = %d AND container = %d AND slot = %d;"
                     % (entry["cape_id"], BST_EXISTING[0], BST_EXISTING[1]))
        lines.append("")
        for build, (container, slot) in zip(order[1:], BST_SLOTS):
            lines.append(
                # Guarded on the character existing: a fresh database has no character 1 yet,
                # and the character_id foreign key would reject an unconditional row.
                "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra)"
                " SELECT 1, %d, %d, %d, 1, X'%s' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- %s"
                % (container, slot, entry["cape_id"], capes.encode(build, job).hex().upper(), build))
        lines.append("")
        return "\n".join(lines)

    # Ninja: re-encode the copy that exists, then allocate ten free bag slots.
    lines.append("UPDATE char_inventory SET extra = X'%s'"
                 % capes.encode(order[0], job).hex().upper())
    lines.append(" WHERE character_id = 1 AND item_id = %d %s;" % (entry["cape_id"], NIN_WHERE))
    lines.append("")
    lines += [
        "-- The ten remaining builds go into the first free main-bag slots.",
        "WITH RECURSIVE",
        "  target(character_id) AS (SELECT id FROM characters WHERE id = 1),",
        "  nums(n) AS (SELECT 0 UNION ALL SELECT n + 1 FROM nums WHERE n < 79),",
        "  free AS (",
        "    SELECT n AS slot, ROW_NUMBER() OVER (ORDER BY n) AS rn",
        "    FROM nums",
        "    WHERE NOT EXISTS (SELECT 1 FROM char_inventory ci",
        "                      WHERE ci.character_id = 1 AND ci.container = 0 AND ci.slot = n)",
        "      AND n < 80),",
        "  want(item_id, extra, rn) AS (VALUES",
    ]
    rows = []
    for build, rn in zip(order[1:], range(1, len(order))):
        rows.append("    (%d, X'%s', %d)" % (
            entry["cape_id"], capes.encode(build, job).hex().upper(), rn))
    lines.append(",\n".join(rows))
    lines += [
        "  )",
        "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra)",
        "SELECT t.character_id, 0, free.slot, want.item_id, 1, want.extra",
        "FROM want JOIN free ON free.rn = want.rn CROSS JOIN target t;",
        "",
    ]
    return "\n".join(lines)


def _drk_sql() -> str:
    """Dark Knight's ten Ankou's Mantle builds (migration 88)."""
    entry = capes.JOBS["DRK"]
    order = ORDER["DRK"]
    lines = [
        "-- Ambuscade JSE cape augments (migration 88).",
        "--",
        "-- Dark Knight capes: Ankou's Mantle (item 26253), ten builds.  The",
        "-- format is the same standard five-slot block as the Beastmaster and",
        "-- Ninja migrations: kind 0x02, subkind 0x03, five little-endian words",
        "-- of {id:11, value:5}, then twelve zero bytes.  The existing wardrobe",
        "-- copy becomes the tp build; the other nine are new copies in the",
        "-- first free wardrobe-3 slots.  The client reads the job from the",
        "-- item name, so !cape <build> <item> can rewrite any of them.",
        "",
        "UPDATE char_inventory SET extra = X'%s'"
        % capes.encode(order[0], "DRK").hex().upper(),
        " WHERE character_id = 1 AND item_id = %d %s;"
        % (entry["cape_id"], DRK_WHERE),
        "",
    ]
    for build, (container, slot) in zip(order[1:], DRK_SLOTS):
        lines.append(
            "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra)"
            " SELECT 1, %d, %d, %d, 1, X'%s' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- %s"
            % (container, slot, entry["cape_id"], capes.encode(build, "DRK").hex().upper(), build))
    lines.append("")
    return "\n".join(lines)


def _blm_sql() -> str:
    """Black Mage's nine Taranus's Cape builds (migration 101)."""
    entry = capes.JOBS["BLM"]
    order = ORDER["BLM"]
    lines = [
        "-- Ambuscade JSE cape augments (migration 101).",
        "--",
        "-- Black Mage capes: Taranus's Cape (item 26249), nine builds.  The",
        "-- format is the same standard five-slot block as the Beastmaster,",
        "-- Ninja and Dark Knight migrations: kind 0x02, subkind 0x03, five",
        "-- little-endian words of {id:11, value:5}, then twelve zero bytes.",
        "-- The existing wardrobe copy becomes the tp build; the other eight",
        "-- are new copies in wardrobe 6 slots 66-73 (the inventory and the",
        "-- earlier wardrobes are full).  The client reads the job from the",
        "-- item name, so !cape <build> <item> can rewrite any of them.",
        "",
        "UPDATE char_inventory SET extra = X'%s'"
        % capes.encode(order[0], "BLM").hex().upper(),
        " WHERE character_id = 1 AND item_id = %d %s;"
        % (entry["cape_id"], BLM_WHERE),
        "",
    ]
    for build, (container, slot) in zip(order[1:], BLM_SLOTS):
        lines.append(
            "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra)"
            " SELECT 1, %d, %d, %d, 1, X'%s' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- %s"
            % (container, slot, entry["cape_id"], capes.encode(build, "BLM").hex().upper(), build))
    lines.append("")
    return "\n".join(lines)


def _build_table(job: str) -> list[str]:
    out = ["| Build | Augments | Block |", "| --- | --- | --- |"]
    for build in ORDER[job]:
        names = " / ".join(capes.JOBS[job]["builds"][build])
        out.append("| `%s` | %s | `%s` |"
                   % (build, names, capes.encode(build, job).hex()))
    return out


def doc() -> str:
    out = [
        "# Ambuscade JSE cape augments",
        "",
        "Every job's Ambuscade cape (`Artio's Mantle` for Beastmaster, item 26254;",
        "`Andartia's Mantle` for Ninja, item 26258; `Ankou's Mantle` for Dark Knight,",
        "item 26253; `Taranus's Cape` for Black Mage, item 26249) is augmented with",
        "five standard augment slots.  The block is",
        "",
        "```",
        "02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12",
        "```",
        "",
        "where each slot is a little-endian u16 holding `id:11 | value:5`.  The",
        "client prints `(value + offset) * multiplier` for the id, so `HP+60` is",
        "id 2 (offset 33) with value 27 and `Enmity-10` is id 0x028 (multiplier",
        "-1) with value 9.  Empty slots are zero.",
        "",
        "## Beastmaster (Artio's Mantle)",
        "",
    ]
    out += _build_table("BST")
    out += [
        "",
        "## Ninja (Andartia's Mantle)",
        "",
    ]
    out += _build_table("NIN")
    out += [
        "",
        "## Dark Knight (Ankou's Mantle)",
        "",
    ]
    out += _build_table("DRK")
    out += [
        "",
        "## Black Mage (Taranus's Cape)",
        "",
    ]
    out += _build_table("BLM")
    out += [
        "",
        "## Slots",
        "",
        "All nine Beastmaster builds are copies of item 26254, so the client shows",
        "nine `Artio's Mantle` entries; hover each to see which build it is.  The bag",
        "copy that already existed is the `tp` build; the rest sit in bag slots 1-24.",
        "",
        "All eleven Ninja builds are copies of item 26258.  The wardrobe copy that",
        "already existed is the `tp` build; the other ten were placed in the first free",
        "main-bag slots by `0082_nin_capes.sql`.",
        "",
        "All ten Dark Knight builds are copies of item 26253.  The wardrobe copy that",
        "already existed is the `tp` build; the other nine were placed in wardrobe 3",
        "slots 1-9 by `0088_drk_capes.sql`.",
        "",
        "All nine Black Mage builds are copies of item 26249.  The wardrobe copy that",
        "already existed is the `tp` build; the other eight were placed in wardrobe 6",
        "slots 66-73 by `0101_blm_capes.sql`.",
        "",
        "`!cape <build> <item>` re-encodes a cape in place (it reads the item's job from",
        "the cape name), and `!cape list` prints the builds.  `tools/gen_capes.py --check`",
        "keeps this page and the migrations in step with `server/fanxi_server/game/capes.py`.",
        "",
        "The five-slot block is read back into the stat sheet: `FanxiService.equipped_mods()`",
        "passes each equipped cape's block through `augment_stats`, which renders the slots",
        "with the same table `!cape` prints and adds their modifiers, so a `tp` cape's",
        "DEX+20 / Accuracy+30 / Attack+20 / Store TP+10 / Phys. dmg. taken-10% counts in",
        "combat.",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    pairs = [(MIGRATIONS["BST"], sql("BST")), (MIGRATIONS["NIN"], sql("NIN")),
             (MIGRATIONS["DRK"], sql("DRK")), (MIGRATIONS["BLM"], sql("BLM")),
             (DOC, doc())]
    rc = 0
    for path, want in pairs:
        if check:
            if not path.exists() or path.read_text() != want:
                print("%s is out of date; run tools/gen_capes.py" % path.relative_to(ROOT))
                rc = 1
            continue
        path.write_text(want)
        print("wrote %s" % path.relative_to(ROOT))
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
