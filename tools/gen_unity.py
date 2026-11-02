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

from server.fanxi_server.game import unity  # noqa: E402

MIGRATION = ROOT / "database/migrations/0083_unity_augments.sql"
DOC = ROOT / "docs/unity-augments.md"

# The dataset lists the pieces the shared GearSwap `local unity` table carries
# first (see gearswap/MNK.lua); the docs keep them in their own table.
GEARSWAP = 5

CATEGORY_ORDER = ("Accessories", "Armor", "Weapons")


def _split() -> tuple[list[tuple[int, dict]], dict[str, list[tuple[int, dict]]]]:
    entries = list(unity.ITEMS.items())
    first, rest = entries[:GEARSWAP], entries[GEARSWAP:]
    grouped: dict[str, list[tuple[int, dict]]] = {name: [] for name in CATEGORY_ORDER}
    for item_id, entry in rest:
        grouped.setdefault(entry.get("category") or "Other", []).append((item_id, entry))
    return first, grouped


def sql() -> str:
    lines = [
        "-- Unity +1 gear augments (migration 83).",
        "--",
        "-- Unity Wanted iLvl 119+ equipment is augmented at a Unity NPC.  The client",
        "-- stores the result in the same 24-byte AugmentBundle block Odyssey uses, at",
        "-- Rank 15 and max-rank tier 0 (the 15-rank unlock), one path.  The bundle index",
        "-- selects the item's row in the client's augment table; every Unity piece is one",
        "-- of bundles 285-392, and the rows below are the Rank 15 lines from the item pages.",
        "--",
        "-- Generated from data/unity_r15.json by tools/gen_unity.py.",
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


def _table(out: list[str], entries: list[tuple[int, dict]]) -> None:
    out.append("| Item | Slot | Item ID | Bundle | Rank 15 augments |")
    out.append("| --- | --- | --- | --- | --- |")
    for item_id, entry in entries:
        out.append("| %s | %s | %d | %d | %s |" % (
            entry["name"], entry["slot"], item_id, entry["bundle"],
            "<br>".join(entry["augments"])))


def doc() -> str:
    first, grouped = _split()
    total = len(unity.ITEMS)
    out = [
        "# Unity augments",
        "",
        "iLvl 119+ Unity Wanted +1 equipment is augmented at a Unity NPC with",
        "Lustreless items.  The client stores the result in the same 24-byte",
        "`AugmentBundle` block Odyssey uses, but at **Rank 15** with max-rank",
        "tier 0 (the 15-rank unlock) and one path.  The bundle index selects the",
        "item's row in the client's augment table:",
        "",
        "```",
        "03 83  00 00  <rank:5 | tier:2 | curve:2>  <bundle index:u32>  00 * 12",
        "```",
        "",
        "The dataset is `data/unity_r15.json`: **%d pieces**, the whole of BG Wiki's" % total,
        "[Unity Accessories](https://www.bg-wiki.com/ffxi/Category:Unity_Accessories),",
        "[Unity Armor](https://www.bg-wiki.com/ffxi/Category:Unity_Armor) and",
        "[Unity Weapons](https://www.bg-wiki.com/ffxi/Category:Unity_Weapons)",
        "categories.  The bundle indices come from the client's augment table",
        "(LandSandBoat's `xi.data.augments.bundles`); every Unity piece is one of",
        "bundles 285-392, matched to its Rank 15 row, and every item has its own",
        "bundle.  The rows are from each item's BG Wiki page.",
        "",
        "## The five GearSwap pieces",
        "",
        "These are the pieces the shared `local unity` table in",
        "[gearswap/MNK.lua](../gearswap/MNK.lua) defines: Unmoving Collar +1,",
        "Odnowa Earring +1, Gelatinous Ring +1 and Ghastly Tathlum +1 are the four",
        "accessories Ninja wears, and Loess Barbuta +1 is PLD/DRK/SAM/DRG gear.",
        "",
    ]
    _table(out, first)
    out.append("")
    for category in CATEGORY_ORDER:
        entries = grouped.get(category) or []
        if not entries:
            continue
        count = len(entries) + sum(1 for _, entry in first
                                   if entry.get("category") == category)
        out += [
            "## %s (%d pieces)" % (category, count),
            "",
        ]
        _table(out, entries)
        out.append("")
    out += [
        "## In game",
        "",
        "`database/migrations/0083_unity_augments.sql` writes each block into",
        "`char_inventory.extra` for the first character.  `//augment A <item>` rewrites",
        "a copy, `//augment off <item>` clears it, and `//augment list` shows the builds.",
        "The block is not only a tooltip any more: `FanxiService.equipped_mods()` joins",
        "each equipped item back to its inventory copy and `augment_stats` turns the",
        "Rank 15 rows into modifiers, so Unmoving Collar +1's `DEF+30 HP+200` reaches",
        "the stat sheet and combat.  The Data page's RP card marks the path a copy",
        "already carries: a capped path is highlighted and its button reads **Capped**,",
        "a partial one offers **Finish path**, and picking another path overwrites the",
        "block.",
        "",
        "Two rows disagree between the item pages and LandSandBoat's bundle values:",
        "Buramgh +1's third row is `Accuracy/Magic Accuracy +35` on the page and 25 in",
        "the bundle table, and Kunimune +1's `TP Bonus +500` is 50 there.  The dataset",
        "keeps the page text, so the RP card lists what the wiki documents.",
        "",
        "`tools/gen_unity.py --check` keeps this page and the migration in step with",
        "`data/unity_r15.json`.",
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
