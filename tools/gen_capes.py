#!/usr/bin/env python3
"""Write the Ambuscade cape locker migration and docs.

    python3 tools/gen_capes.py          # rewrite the generated files
    python3 tools/gen_capes.py --check  # fail if they are out of date
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import capes  # noqa: E402

MIGRATION = ROOT / "database/migrations/0116_all_capes_locker.sql"
DOC = ROOT / "docs/capes.md"

# The order a reader expects: the TP build first, then the defensive family,
# then the rest.
PREFERRED = ("tp", "ranged_tp", "dd", "pdt", "mdt", "maxhp", "dt")

# The build an equipped copy is re-encoded to.  Paladins and Rune Fencers have
# no plain ``tp`` build, and Ranger's TP build is ``ranged_tp``.
DEFAULT = {"PLD": "dd", "RNG": "ranged_tp", "RUN": "dd"}


def default_build(job: str) -> str:
    return DEFAULT.get(job, "tp")


def build_order(job: str) -> list[str]:
    names = list(capes.JOBS[job]["builds"])
    return sorted(names, key=lambda name: (
        PREFERRED.index(name) if name in PREFERRED else len(PREFERRED), name))


def sql() -> str:
    """The one migration: extend the locker, then store every build in it."""
    jobs = list(capes.JOBS)
    ids = ", ".join(str(capes.JOBS[job]["cape_id"]) for job in jobs)
    lines = [
        "-- Ambuscade JSE cape builds in the hidden locker (migration 116).",
        "--",
        "-- All 22 job capes share one item id per job, so each build is a copy",
        "-- distinguished only by its 24-byte standard-augment block.  The hidden",
        "-- locker (9999 items, not a client bag) is the only place they all fit:",
        "-- 198 builds against the 253 free capacity in the live character.",
        "--",
        "-- char_locker gains the block and a primary key that includes it, so the",
        "-- nine Taranus's Capes (or eleven Andartia's Mantles) can coexist.  The",
        "-- old rows (broths, tools, ammo) get an empty block and keep their data.",
        "--",
        "-- Old bag/wardrobe cape copies are removed so the locker is the one",
        "-- source of truth; an equipped cape stays and is re-encoded to its job's",
        "-- default build.  //job then grabs the capes from the locker into the",
        "-- wardrobes, and the normal job-change tidy puts the loose ones away.",
        "",
        "ALTER TABLE char_locker RENAME TO char_locker_old;",
        "CREATE TABLE char_locker (",
        "    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,",
        "    item_id      INTEGER NOT NULL,",
        "    extra        BLOB    NOT NULL DEFAULT X'',",
        "    quantity     INTEGER NOT NULL DEFAULT 1,",
        "    stored_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,",
        "    PRIMARY KEY (character_id, item_id, extra)",
        ");",
        "INSERT INTO char_locker (character_id, item_id, extra, quantity, stored_at)",
        "SELECT character_id, item_id, X'', quantity, stored_at FROM char_locker_old;",
        "DROP TABLE char_locker_old;",
        "",
        "DELETE FROM char_inventory",
        " WHERE character_id = 1",
        "   AND item_id IN (%s)" % ids,
        "   AND NOT EXISTS (",
        "     SELECT 1 FROM char_equip e",
        "      WHERE e.character_id = char_inventory.character_id",
        "        AND e.container = char_inventory.container",
        "        AND e.slot = char_inventory.slot);",
        "",
    ]
    for job in jobs:
        entry = capes.JOBS[job]
        block = capes.encode(default_build(job), job).hex().upper()
        lines.append(
            "UPDATE char_inventory SET extra = X'%s'" % block)
        lines.append(
            " WHERE character_id = 1 AND item_id = %d" % entry["cape_id"])
        lines.append(
            "   AND EXISTS (SELECT 1 FROM char_equip e"
            " WHERE e.character_id = char_inventory.character_id"
            " AND e.container = char_inventory.container"
            " AND e.slot = char_inventory.slot);  -- equipped %s"
            % job)
    lines.append("")
    for job in jobs:
        entry = capes.JOBS[job]
        for build in build_order(job):
            block = capes.encode(build, job).hex().upper()
            lines.append(
                "INSERT OR IGNORE INTO char_locker"
                " (character_id, item_id, extra, quantity)"
                " SELECT 1, %d, X'%s', 1"
                " WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- %s %s"
                % (entry["cape_id"], block, job, build))
    lines.append("")
    return "\n".join(lines)


def doc() -> str:
    jobs = list(capes.JOBS)
    total = sum(len(capes.JOBS[job]["builds"]) for job in jobs)
    lines = [
        "# Ambuscade JSE cape augments",
        "",
        "> This page covers the **Ambuscade** capes.  The Reive and Incursion capes",
        "> (Detrovio / Refractive Crystal) are in [reive-capes.md](reive-capes.md).",
        "",
        "All 22 jobs have one Ambuscade cape, and every cape build is a copy of the",
        "same job item with a five-slot standard augment block:",
        "",
        "```",
        "02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12",
        "```",
        "",
        "Each slot is a little-endian u16 holding `id:11 | value:5`.  The client",
        "prints `(value + offset) * multiplier` for the id, so `HP+60` is id 2",
        "(offset 33) with value 27 and `Enmity-10` is id 0x028 (multiplier -1) with",
        "value 9.  Empty slots are zero.  There are **%d builds** in total." % total,
        "",
        "All of them live in the hidden 9,999-slot locker (`char_locker`, migration",
        "`0116_all_capes_locker.sql`), not in a client bag.  `//job <job>` grabs that",
        "job's builds out of the locker, and the normal job-change tidy moves the loose",
        "copies into the Mog Wardrobes; the job's cape is then equipped from the",
        "wardrobe.  The other jobs' capes stay in the locker until their turn.",
        "`//locker grab jsecapes` takes all 198 out and `//locker store jsecapes` puts",
        "them back.",
        "",
        "`//cape <build> <item>` re-encodes one cape in place, `//cape list` prints the",
        "builds, and `tools/gen_capes.py --check` keeps this page and the migration",
        "in step with `server/fanxi_server/game/capes.py`.",
        "",
        "## Launcher augment editor",
        "",
        "The launcher's **Data** page has an **Ambuscade capes** card that edits the",
        "same block without a command.  Pick one of the 22 capes (or add a fresh copy",
        "to the inventory), then choose one row per BG Wiki material:",
        "",
        "| Material | Slot | Rows | Items to cap |",
        "| --- | --- | --- | --- |",
        "| Abdhaljs Thread | 0 | HP, MP, attributes, pet accuracy | 20 |",
        "| Abdhaljs Dust | 1 | Accuracy/attack, ranged, magic and evasion pairs | 20 |",
        "| Abdhaljs Dye | 2 | HP, MP, attributes and single combat stats | 10 |",
        "| Abdhaljs Sap | 3 | Store TP, Fast Cast, damage and job traits | 10 |",
        "| Abdhaljs Resin | 4 | DEF, evasion, damage taken, block and parry | 5 |",
        "",
        "Each row has a stage from 1 to its cap; **Finish augment** writes the five",
        "slots, and **Max selected** takes every chosen row to its cap.  A material",
        "left untouched keeps the word already on the copy, so the pet-focused builds",
        "below survive a partial edit; choosing `— none —` clears just that slot and",
        "**Clear augments** writes the empty block `//cape off` uses.  A live client",
        "receives `//reload`, so the new tooltip is visible without zoning.",
        "",
        "The stat sheet reads the block back: `FanxiService.equipped_mods()` passes",
        "each equipped cape through `augment_stats`, which renders the same text",
        "`//cape` prints and adds the modifiers, so a `tp` cape's DEX+20 /",
        "Accuracy+30 / Attack+20 / Store TP+10 / Phys. dmg. taken-10% counts in",
        "combat.",
        "",
    ]
    for job in jobs:
        entry = capes.JOBS[job]
        lines += [
            "## %s (%s, item %d)" % (_job_name(job), entry["cape_name"], entry["cape_id"]),
            "",
            "| Build | Augments | Block |",
            "| --- | --- | --- |",
        ]
        for build in build_order(job):
            names = " / ".join(entry["builds"][build])
            block = capes.encode(build, job).hex()
            lines.append("| `%s` | %s | `%s` |" % (build, names, block))
        lines.append("")
    return "\n".join(lines)


JOB_NAMES = {
    "WAR": "Warrior", "MNK": "Monk", "WHM": "White Mage", "BLM": "Black Mage",
    "RDM": "Red Mage", "THF": "Thief", "PLD": "Paladin", "DRK": "Dark Knight",
    "BST": "Beastmaster", "BRD": "Bard", "RNG": "Ranger", "SAM": "Samurai",
    "NIN": "Ninja", "DRG": "Dragoon", "SMN": "Summoner", "BLU": "Blue Mage",
    "COR": "Corsair", "PUP": "Puppetmaster", "DNC": "Dancer", "SCH": "Scholar",
    "GEO": "Geomancer", "RUN": "Rune Fencer",
}


def _job_name(job: str) -> str:
    return JOB_NAMES.get(job, job)


def main(argv: list[str]) -> int:
    want = doc()
    migration = sql()
    if "--check" in argv[1:]:
        problems = []
        if not MIGRATION.exists() or MIGRATION.read_text() != migration:
            problems.append(str(MIGRATION))
        if not DOC.exists() or DOC.read_text() != want:
            problems.append(str(DOC))
        for item in problems:
            print("out of date: %s" % item)
        return 1 if problems else 0
    MIGRATION.write_text(migration)
    DOC.write_text(want)
    print("wrote %s" % MIGRATION)
    print("wrote %s" % DOC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
