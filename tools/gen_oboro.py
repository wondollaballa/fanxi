#!/usr/bin/env python3
"""Generate the Oboro Dynamis-Divergence weapon dataset, docs and migration.

Oboro (Port Jeuno E-6) augments the crafted JSE weapons from Dynamis -
Divergence.  The client stores the result in the same 24-byte ``AugmentBundle``
block Odyssey and Limbus use, so the launcher can cap a path exactly like the
RP card already does.  The bundle indices come from the client's augment table
(LandSandBoat's ``xi.data.augments.bundles``); the families below are in the
same order as the client's table, nine bundles per family:

    NQ  A/B/C, HQ1 A/B/C, HQ2 A/B/C

Three outputs, one dataset, so the card, the docs and the migration cannot
drift apart:

* ``data/oboro_r25.json``                      the items and all their paths;
* ``docs/oboro-r25.md``                        the wiki-facing table;
* ``database/migrations/0120_oboro_augments.sql``
  removes the old static Musa Path C lines and stamps the real R25 block onto
  every Musa copy, so the SCH Regen set keeps the same numbers.

Run ``python3 tools/gen_oboro.py`` after editing this file; ``--check`` exits
non-zero when an output is stale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import augments  # noqa: E402

DATA = ROOT / "data" / "oboro_r25.json"
DOCS = ROOT / "docs" / "oboro-r25.md"
SQL = ROOT / "database" / "migrations" / "0120_oboro_augments.sql"

SOURCE = "https://www.bg-wiki.com/ffxi/Dynamis_Divergence_Weapon_Augments"
RP_CURVE = 0  # curve A

QUALITIES = {
    "nq": {
        "label": "NQ",
        "rank": 15,
        "tier": 0,
        "rp": 1110,
        "total_rp": 5950,
        "double_damage": 30,
        "store_tp": 15,
        "follow_up": 30,
        "subtle_blow_ii": 15,
    },
    "hq1": {
        "label": "HQ1",
        "rank": 20,
        "tier": 1,
        "rp": 1960,
        "total_rp": 13060,
        "double_damage": 40,
        "store_tp": 20,
        "follow_up": 40,
        "subtle_blow_ii": 20,
    },
    "hq2": {
        "label": "HQ2",
        "rank": 25,
        "tier": 2,
        "rp": 3180,
        "total_rp": 25150,
        "double_damage": 50,
        "store_tp": 25,
        "follow_up": 50,
        "subtle_blow_ii": 25,
    },
}

# (job, weapon, slot, nq item/name/rows, hq1 item/name/rows,
#  hq2 item/name/rows, HQ2 A/B DMG, ranged A/B wording)
#
# The order is the client bundle order: MNK, PUP, THF, BRD, COR, DNC, RDM,
# PLD, BLU, RUN, BST, WAR, DRK, DRG, NIN, SAM, WHM, GEO, BLM, SMN, SCH, RNG.
WEAPONS = [
    ("MNK", "Hand-to-Hand", "main",
     21521, "Melee Fists", ["HP+200", '"Chakra"+20'],
     21522, "Hes. Fists", ["HP+300", '"Chakra"+35'],
     21523, "Sagitta", ["HP+400", '"Chakra"+50', "DMG:+12"], 12, False),
    ("PUP", "Hand-to-Hand", "main",
     21524, "Pantin Fists",
     ["Weapon skill damage +10%", "Automaton: Special attack damage +15%"],
     21525, "Pitre Fists",
     ["Weapon skill damage +12%", "Automaton: Special attack damage +20%"],
     21526, "Xiucoatl",
     ["Weapon skill damage +15%", "Automaton: Special attack damage +25%", "DMG:+12"],
     12, False),
    ("THF", "Dagger", "main",
     21573, "Assassin's Knife", ["Evasion+50", "TP during evasion +20"],
     21574, "Plun. Knife", ["Evasion+75", "TP during evasion +35"],
     21575, "Gandring", ["Evasion+100", "TP during evasion +50", "DMG:+5"],
     5, False),
    ("BRD", "Dagger", "main",
     21576, "Bard's Knife",
     ["Song spellcasting time -15%", 'Song effects: "Double Attack"+2%'],
     21577, "Bihu Knife",
     ["Song spellcasting time -20%", 'Song effects: "Double Attack"+3%'],
     21578, "Barfawc",
     ["Song spellcasting time -25%", 'Song effects: "Double Attack"+4%', "DMG:+5"],
     5, False),
    ("COR", "Dagger", "main",
     21579, "Comm. Knife",
     ['"Phantom Roll" effect duration +30',
      '"Phantom Roll XI": Recover HP and MP +10%', '"Phantom Roll"+6'],
     21580, "Lanun Knife",
     ['"Phantom Roll" effect duration +45',
      '"Phantom Roll XI": Recover HP and MP +12%', '"Phantom Roll"+7'],
     21581, "Rostam",
     ['"Phantom Roll" effect duration +60',
      '"Phantom Roll XI": Recover HP and MP +15%', '"Phantom Roll"+8'],
     5, False),
    ("DNC", "Dagger", "main",
     21582, "Etoile Knife", ['"Flourish" recast time -15%', '"Step" duration +30'],
     21583, "Horos Knife", ['"Flourish" recast time -20%', '"Step" duration +45'],
     21584, "Setan Kober",
     ['"Flourish" recast time -25%', '"Step" duration +60', "DMG:+5"],
     5, False),
    ("RDM", "Sword", "main",
     21625, "Duelist's Sword",
     ["Sword enhancement spell damage +300%", "Elemental weapon skill damage +50%"],
     21626, "Vitiation Sword",
     ["Sword enhancement spell damage +400%", "Elemental weapon skill damage +75%"],
     21627, "Crocea Mors",
     ["Sword enhancement spell damage +500%", "Elemental weapon skill damage +100%",
      "DMG:+7"],
     7, False),
    ("PLD", "Sword", "main",
     21628, "Valor Sword",
     ["HP+150", '"Cure" potency+15%', '"Refresh"+2'],
     21629, "Cabal. Sword",
     ["HP+200", '"Cure" potency+20%', '"Refresh"+3'],
     21630, "Moralltach",
     ["HP+250", '"Cure" potency+25%', '"Refresh"+4'],
     7, False),
    ("BLU", "Sword", "main",
     21631, "Mirage Sword",
     ['"Chain Affinity" recast time -15%', '"Burst Affinity" recast time -15%'],
     21632, "Luhlaza Sword",
     ['"Chain Affinity" recast time -20%', '"Burst Affinity" recast time -20%'],
     21633, "Zomorrodnegar",
     ['"Chain Affinity" recast time -25%', '"Burst Affinity" recast time -25%',
      "DMG:+7"],
     7, False),
    ("RUN", "Great Sword", "main",
     21667, "Futhark Claymore",
     ['Potency of "Regen" effects received +15', '"Vivacious Pulse" potency +20%'],
     21668, "Peord Claymore",
     ['Potency of "Regen" effects received +20', '"Vivacious Pulse" potency +25%'],
     21669, "Morgelai",
     ['Potency of "Regen" effects received +25', '"Vivacious Pulse" potency +30%',
      "DMG:+14"],
     14, False),
    ("BST", "Axe", "main",
     21715, "Monster Axe", ["Damage Taken -15%", "Pet: Damage Taken -10%"],
     21716, "Ankusa Axe", ["Damage Taken -20%", "Pet: Damage Taken -12%"],
     21717, "Pangu",
     ["Damage Taken -25%", "Pet: Damage Taken -15%", "DMG:+11"],
     11, False),
    ("WAR", "Great Axe", "main",
     21772, "War. Chopper",
     ["TP Gained when landing critical hits +30", "Crit. Hit Rate +6%"],
     21773, "Agoge Chopper",
     ["TP Gained when landing critical hits +40", "Crit. Hit Rate +8%"],
     21774, "Labraunda",
     ["TP Gained when landing critical hits +50", "Crit. Hit Rate +10%", "DMG:+14"],
     14, False),
    ("DRK", "Scythe", "main",
     21823, "Abyss Scythe", ['"Drain" potency +15%', "Weapon Skill Damage +10%"],
     21824, "Fallen's Scythe", ['"Drain" potency +20%', "Weapon Skill Damage +12%"],
     21825, "Father Time",
     ['"Drain" potency +25%', "Weapon Skill Damage +15%", "DMG:+15"],
     15, False),
    ("DRG", "Polearm", "main",
     21876, "Wyrm Lance", ["Wyvern: HP +150", "Wyvern: Damage Taken -10%"],
     21877, "Pteroslaver Lance", ["Wyvern: HP +200", "Wyvern: Damage Taken -12%"],
     21878, "Aram",
     ["Wyvern: HP +250", "Wyvern: Damage Taken -15%", "DMG:+14"],
     14, False),
    ("NIN", "Katana", "main",
     21915, "Koga Shin.", ["Ninjutsu recast time -15%", "Enmity+6 for each Utsusemi"],
     21916, "Mochi. Shin.", ["Ninjutsu recast time -20%", "Enmity+8 for each Utsusemi"],
     21917, "Fudo Masamune",
     ["Ninjutsu recast time -25%", "Enmity+10 for each Utsusemi", "DMG:+7"],
     7, False),
    ("SAM", "Great Katana", "main",
     21968, "Saotome-no-Tachi",
     ['"Sekkanoki" recast time -15%', '"Sekkanoki": Weapon Skill Damage +50%'],
     21969, "Sakonji-no-Tachi",
     ['"Sekkanoki" recast time -20%', '"Sekkanoki": Weapon Skill Damage +75%'],
     21970, "Fusenaikyo",
     ['"Sekkanoki" recast time -25%', '"Sekkanoki": Weapon Skill Damage +100%',
      "DMG:+13"],
     13, False),
    ("WHM", "Club", "main",
     22033, "Cleric's Wand",
     ['"Afflatus Misery" stored +150%', "Healing magic recast delay -15%",
      "Damage Taken -10%"],
     22034, "Piety Wand",
     ['"Afflatus Misery" stored +200%', "Healing magic recast delay -20%",
      "Damage Taken -12%"],
     22035, "Asclepius",
     ['"Afflatus Misery" stored +250%', "Healing magic recast delay -25%",
      "Damage Taken -15%"],
     8, False),
    ("GEO", "Club", "main",
     22036, "Bagua Wand",
     ["Magic burst damage II +6", "Magic burst accuracy +20",
      '"Drain" and "Aspir" potency +10'],
     22037, "Sifang Wand",
     ["Magic burst damage II +8", "Magic burst accuracy +25",
      '"Drain" and "Aspir" potency +15'],
     22038, "Bhima",
     ["Magic burst damage II +10", "Magic burst accuracy +30",
      '"Drain" and "Aspir" potency +20'],
     8, False),
    ("BLM", "Staff", "main",
     22091, "Sorcerer's Staff",
     ["MP+50", '"Mana Wall"+15%', "Damage Taken -10%"],
     22092, "Archmage's Staff",
     ["MP+75", '"Mana Wall"+20%', "Damage Taken -12%"],
     22093, "Kaumodaki",
     ["MP+100", '"Mana Wall"+25%', "Damage Taken -15%"],
     11, False),
    ("SMN", "Staff", "main",
     22094, "Summoner's Staff",
     ["Pet: Chance of double damage +20%",
      'Chance of doubling "Blood Pact" status +15%', "Blood Pact Dmg.+10"],
     22095, "Glyphic Staff",
     ["Pet: Chance of double damage +35%",
      'Chance of doubling "Blood Pact" status +20%', "Blood Pact Dmg.+12"],
     22096, "Draumstafir",
     ["Pet: Chance of double damage +50%",
      'Chance of doubling "Blood Pact" status +25%', "Blood Pact Dmg.+15"],
     11, False),
    ("SCH", "Staff", "main",
     22097, "Argute Staff",
     ['"Regen" potency +15', '"Cure" potency +15%', '"Fast Cast"+6%'],
     22098, "Pedagogy Staff",
     ['"Regen" potency +20', '"Cure" potency +20%', '"Fast Cast"+8%'],
     22099, "Musa",
     ['"Regen" potency +25', '"Cure" potency +25%', '"Fast Cast"+10%'],
     11, False),
    ("RNG", "Marksmanship", "range",
     22147, "Scout's Crossbow",
     ["Additional ammo damage: +200%", "Additional ammo accuracy +100"],
     22148, "Arke Crossbow",
     ["Additional ammo damage: +250%", "Additional ammo accuracy +125"],
     22149, "Sharanga",
     ["Additional ammo damage: +300%", "Additional ammo accuracy +150", "DMG:+6"],
     6, True),
]


def payload() -> dict:
    """The compact dataset the server expands into one entry per item."""
    weapons = []
    for index, weapon in enumerate(WEAPONS):
        (job, weapon_type, slot, nq_id, nq_name, nq_rows, hq1_id, hq1_name,
         hq1_rows, hq2_id, hq2_name, hq2_rows, dmg, ranged) = weapon
        start = 1 + index * 9
        tiers = {}
        for offset, (key, item_id, name, rows) in enumerate((
                ("nq", nq_id, nq_name, nq_rows),
                ("hq1", hq1_id, hq1_name, hq1_rows),
                ("hq2", hq2_id, hq2_name, hq2_rows))):
            base = start + offset * 3
            tiers[key] = {
                "item_id": item_id,
                "name": name,
                "bundles": {"A": base, "B": base + 1, "C": base + 2},
                "c": list(rows),
            }
        weapons.append({
            "job": job,
            "weapon": weapon_type,
            "slot": slot,
            "ranged": ranged,
            "dmg": dmg,
            "tiers": tiers,
        })
    return {
        "source": SOURCE,
        "rp_curve": RP_CURVE,
        "note": (
            "Oboro (Port Jeuno E-6) augments Dynamis-Divergence crafted JSE weapons. "
            "NQ caps at R15, HQ1 at R20 and HQ2 at R25; path choice is permanent in retail."
        ),
        "qualities": QUALITIES,
        "weapons": weapons,
    }


def entry_paths(weapon: dict, quality_key: str) -> list[dict]:
    quality = QUALITIES[quality_key]
    tier = weapon["tiers"][quality_key]
    bundles = tier["bundles"]
    ranged = bool(weapon.get("ranged"))
    double = "Chance of double ranged damage" if ranged else "Chance of double damage"
    follow = "Chance of ranged follow-up attack" if ranged else "Chance of follow-up attack"
    a_rows = [
        "%s +%d%%" % (double, quality["double_damage"]),
        '"Store TP"+%d' % quality["store_tp"],
    ]
    b_rows = [
        "%s +%d%%" % (follow, quality["follow_up"]),
        '"Subtle Blow II"+%d' % quality["subtle_blow_ii"],
    ]
    if quality_key == "hq2":
        a_rows.append("DMG:+%d" % weapon["dmg"])
        b_rows.append("DMG:+%d" % weapon["dmg"])
    paths = []
    for key, label, rows in (
            ("A", "Path A", a_rows),
            ("B", "Path B", b_rows),
            ("C", "Path C", tier["c"])):
        paths.append({
            "key": key,
            "label": label,
            "bundle": int(bundles[key]),
            "rank": quality["rank"],
            "tier": quality["tier"],
            "rp": quality["rp"],
            "total_rp": quality["total_rp"],
            "curve": RP_CURVE,
            "augments": list(rows),
        })
    return paths


def doc() -> str:
    out = [
        "# Oboro Dynamis-Divergence weapon augments",
        "",
        "Oboro, at Port Jeuno (E-6), augments the crafted JSE weapons that drop",
        "from Dynamis - Divergence.  The client stores the result in the same",
        "24-byte `AugmentBundle` block Odyssey and Limbus use:",
        "",
        "```",
        "03 83  00 00  <rank:5 | tier:2 | curve:2>  <bundle index:u32>  00 * 12",
        "```",
        "",
        "Each weapon has three paths, A/B/C.  Every HQ2 weapon's A and B path",
        "also carries a DMG row; path C is job-specific.  The quality sets the",
        "cap: **NQ R15 (tier 0), HQ1 R20 (tier 1), HQ2 R25 (tier 2)**.  The RP",
        "field uses curve A; the launcher writes the rank-bar maximum and shows",
        "the lifetime total separately (R15 5,950; R20 13,060; R25 25,150).",
        "",
        "The bundle indices come from the client's augment table (LandSandBoat's",
        "`xi.data.augments.bundles`, parsed from the MNC2 data).  The 22 families",
        "are listed in the table's own order, nine bundles per family: NQ A/B/C,",
        "HQ1 A/B/C, HQ2 A/B/C.",
        "",
        "## Path A and B",
        "",
        "| Quality | Rank | Path A | Path B |",
        "| --- | --- | --- | --- |",
    ]
    for key in ("nq", "hq1", "hq2"):
        q = QUALITIES[key]
        dm = "<br>DMG:+ weapon-specific" if key == "hq2" else ""
        out.append("| %s | %d | Chance of double damage +%d%%<br>Store TP+%d%s | "
                   "Chance of follow-up attack +%d%%<br>\"Subtle Blow II\"+%d%s |" % (
                       q["label"], q["rank"], q["double_damage"], q["store_tp"], dm,
                       q["follow_up"], q["subtle_blow_ii"], dm))
    out += [
        "",
        "Ranged weapons (RNG) use \"Chance of double ranged damage\" and",
        "\"Chance of ranged follow-up attack\".",
        "",
        "## Weapons",
        "",
        "| Family | NQ | HQ1 | HQ2 | Path C NQ | Path C HQ1 | Path C HQ2 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for weapon in payload()["weapons"]:
        def cell(tier_key: str) -> str:
            tier = weapon["tiers"][tier_key]
            return "**%s**<br>#%d<br>A/B/C %d/%d/%d" % (
                tier["name"], tier["item_id"], tier["bundles"]["A"],
                tier["bundles"]["B"], tier["bundles"]["C"])
        out.append("| %s (%s) | %s | %s | %s | %s | %s | %s |" % (
            weapon["job"], weapon["weapon"],
            cell("nq"), cell("hq1"), cell("hq2"),
            "<br>".join(weapon["tiers"]["nq"]["c"]),
            "<br>".join(weapon["tiers"]["hq1"]["c"]),
            "<br>".join(weapon["tiers"]["hq2"]["c"]),
        ))
    out += [
        "",
        "The HQ2 path C above is the R25 row.  Paths A and B add the weapon's",
        "DMG row at HQ2 (for example Musa is DMG:+11); the DMG row does not",
        "appear on the NQ or HQ1 two-row paths.",
        "",
        "One value follows the client bundle rather than the wiki table:",
        "Sharanga's HQ2 path C starts at **Additional ammo damage +300%** in",
        "bundle 198.  BG Wiki's table lists +250%, which is Arke Crossbow's HQ1",
        "value; the R15/R20/R25 bundle progression is 200/250/300.",
        "",
        "## In the launcher",
        "",
        "The Data page has a dedicated **Oboro** card.  It lists every family and",
        "quality, shows whether a copy is in a bag and which path/rank it carries,",
        "and caps the chosen path in one click.  An item that is not in a bag can",
        "be bought from the same card into the first free inventory slot (the",
        "Armory path, 141,610 gil), then capped.  Capping sends `//reload` when the",
        "client is running, so the tooltip and the stat sheet update immediately.",
        "",
        "`FanxiService.equipped_mods()` reads the block back through",
        "`augment_stats`: Musa Path C is `\"Regen\" potency +25`, `\"Cure\"`",
        "potency +25% and `\"Fast Cast\"+10%`, and Path A/B turn on Store TP or",
        "Subtle Blow II.  The chance-based rows (double damage, follow-up attack)",
        "are in the client table but not modelled by the server yet.",
        "",
        "Migration `0120_oboro_augments.sql` removes the old static Musa Path C",
        "`item_mods` rows and writes the real R25 Path C block onto every Musa",
        "copy, so the existing SCH Regen set keeps the same numbers while the",
        "block becomes the source of truth.",
        "",
        "`tools/gen_oboro.py --check` keeps this page, the data file and the",
        "migration in step with the generator.",
        "",
    ]
    return "\n".join(out)


def sql() -> str:
    block = augments.bundle("C", 25, 2, 189, rp=3180, curve=RP_CURVE).hex().upper()
    return "\n".join([
        "-- Oboro Dynamis-Divergence weapon augments (migration 120).",
        "--",
        "-- Musa (item 22099) used to carry Path C as three static item_mods rows",
        "-- because the Oboro bundle table was not wired into the launcher.  The",
        "-- client stores Oboro weapon augments in the same 24-byte bundle block",
        "-- Odyssey and Limbus use, so this migration removes the static rows and",
        "-- stamps the real R25 Path C block (bundle 189) onto every Musa copy.",
        "--",
        "-- Path C at R25 is \"Regen\" potency +25, \"Cure\" potency +25% and",
        "-- \"Fast Cast\"+10%.  The block uses rank 25 / tier 2 (the 25-rank unlock),",
        "-- curve A and the rank-bar maximum of 3,180 RP; the lifetime total is",
        "-- 25,150 RP.  Generated from data/oboro_r25.json by tools/gen_oboro.py.",
        "",
        "DELETE FROM item_mods WHERE item_id = 22099 AND mod_id IN (170, 374, 838, 1223);",
        "",
        "UPDATE char_inventory SET extra = X'%s' WHERE item_id = 22099;" % block,
        "UPDATE char_locker SET extra = X'%s' WHERE item_id = 22099;" % block,
        "",
        "-- The launcher's Oboro card owns every other weapon; no other Oboro item",
        "-- has a static path row to remove.",
        "",
    ])


def main(argv: list[str]) -> int:
    check = "--check" in argv
    outputs = (
        (DATA, json.dumps(payload(), indent=2) + "\n"),
        (DOCS, doc()),
        (SQL, sql()),
    )
    stale = False
    for path, want in outputs:
        if check:
            if not path.exists() or path.read_text() != want:
                print("%s is out of date; run tools/gen_oboro.py" % path.relative_to(ROOT))
                stale = True
            continue
        path.write_text(want)
        print("wrote %s" % path.relative_to(ROOT))
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
