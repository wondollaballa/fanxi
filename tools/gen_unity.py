#!/usr/bin/env python3
"""Write the Unity augment migration and docs.

    python3 tools/gen_unity.py          # rewrite the generated files
    python3 tools/gen_unity.py --check  # fail if they are out of date
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import augments, unity  # noqa: E402

MIGRATION = ROOT / "database/migrations/0083_unity_augments.sql"
DOC = ROOT / "docs/unity-augments.md"


def sql() -> str:
    lines = [
        "-- Unity +1 gear augments (migration 83).",
        "--",
        "-- Unity Wanted iLvl 119 +1 equipment is augmented at a Unity NPC.  The client",
        "-- stores the result in the same 24-byte AugmentBundle block Odyssey uses, at",
        "-- Rank 15 and max-rank tier 0 (the 15-rank unlock), one path.  The bundle index",
        "-- selects the item's row in the client's augment table; the rows below are the",
        "-- Rank 15 lines from the GearSwap libraries and the item pages.",
        "--",
        "-- Generated from server/fanxi_server/game/unity.py by tools/gen_unity.py.",
        "",
    ]
    for item_id, entry in unity.ITEMS.items():
        lines.append("-- %d %s: %s (bundle %d)" % (
            item_id, entry["name"], " / ".join(entry["augments"]), entry["bundle"]))
    lines.append("")
    for item_id in unity.ITEMS:
        lines.append("UPDATE char_inventory SET extra = X'%s'"
                     " WHERE character_id = 1 AND item_id = %d;"
                     % (unity.encode(item_id).hex().upper(), item_id))
    lines.append("")
    return "\n".join(lines)


def doc() -> str:
    out = [
        "# Unity augments",
        "",
        "iLvl 119 Unity Wanted +1 equipment is augmented at a Unity NPC with",
        "Lustreless items.  The client stores the result in the same 24-byte",
        "`AugmentBundle` block Odyssey uses, but at **Rank 15** with max-rank",
        "tier 0 (the 15-rank unlock) and one path.  The bundle index selects the",
        "item's row in the client's augment table:",
        "",
        "```",
        "03 83  00 00  <rank:5 | tier:2 | curve:2>  <bundle index:u32>  00 * 12",
        "```",
        "",
        "The Rank 15 row is what the GearSwap libraries list for these items:",
        "",
        "| Item | Slot | Item ID | Bundle | Rank 15 augments |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item_id, entry in unity.ITEMS.items():
        out.append("| %s | %s | %d | %d | %s |" % (
            entry["name"], entry["slot"], item_id, entry["bundle"],
            "<br>".join(entry["augments"])))
    out += [
        "",
        "The four accessories are the Unity pieces Ninja wears in",
        "[gearswap/NIN.lua](../gearswap/NIN.lua): Unmoving Collar +1, Odnowa Earring +1,",
        "Gelatinous Ring +1 and Ghastly Tathlum +1.  Loess Barbuta +1 is the fifth",
        "Unity item that library defines (it is PLD/DRK/SAM/DRG gear, not a Ninja set",
        "piece) and is augmented here too.",
        "",
        "## In game",
        "",
        "`database/migrations/0083_unity_augments.sql` writes each block into",
        "`char_inventory.extra` for the first character.  `!augment A <item>` rewrites",
        "a copy, `!augment off <item>` clears it, and `!augment list` shows the builds.",
        "The tooltip is what changes: the server still reads base gear from",
        "`item_mods`, not from `extra`.",
        "",
        "`tools/gen_unity.py --check` keeps this page and the migration in step with",
        "`server/fanxi_server/game/unity.py`.",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    for path, want in ((MIGRATION, sql()), (DOC, doc())):
        if check:
            if not path.exists() or path.read_text() != want:
                print("%s is out of date; run tools/gen_unity.py" % path.relative_to(ROOT))
                return 1
            continue
        path.write_text(want)
        print("wrote %s" % path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
