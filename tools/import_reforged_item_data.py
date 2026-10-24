#!/usr/bin/env python3
"""Import the reforged armour and the missing worn-piece stats into a migration.

LandSandBoat has no rows for the +3 empyrean and +4 artifact/relic armour sets (it
marks them "Not implemented"), and the custom prime weapon and belt rows added by
earlier migrations carry no modifiers either.  The client still draws the real
tooltip from its DAT, so the server and the client disagreed: the status menu
showed base attributes plus a handful of accessory bonuses while the gear was
wearing nothing.

The input is a snapshot of the client's own item-description lines
(``tools/data/reforged_item_stats.json``), keyed by item id.  This tool parses the
lines the server models and writes two tables:

``item_mods``
    ``(item id, modifier id, value)``.  Attack, Defence, the attributes, Accuracy,
    Evasion, the magic stats, Haste and -- the reason this matters for combat --
    the damage-taken family (DT, PDT, MDT, BDT and the uncapped II variants).

``item_skill_bonus``
    ``(item id, client skill id, amount)`` for "Scythe skill +269" style lines.
    The client skill ids are the ones the 0x062 skill menu uses, not the modifier
    ids: ``server/fanxi_server/game/skills.py`` is the table.

Pet/avatar/automaton lines, "Set:" bonuses and unnamed job-ability procs are not
player stats and are deliberately left out; the engine does not model them yet.
The parser reports anything stat-like it did not understand, so a new item
template shows up as review output instead of silently contributing nothing.

    tools/import_reforged_item_data.py
    tools/import_reforged_item_data.py --source other.json --output /tmp/x.sql
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "tools" / "data" / "reforged_item_stats.json"
DEFAULT_OUTPUT = ROOT / "database" / "migrations" / "0092_reforged_item_data.sql"

CHUNK = 400  # rows per INSERT: the migration runner reads statements line by line
ITEM_COLUMNS = ("item_id", "name", "stack", "usable", "equip_slot", "level",
                "description", "model", "slot_mask", "jobs", "skill")

# LandSandBoat's xi::Mod ids; the engine names the ones it reads in modifiers.py.
MOD = {
    "DEF": 1, "HP": 2, "HPP": 3, "MP": 5, "STR": 8, "DEX": 9, "VIT": 10, "AGI": 11,
    "INT": 12, "MND": 13, "CHR": 14, "ATT": 23, "RATT": 24, "ACC": 25, "RACC": 26,
    "ENMITY": 27, "MATT": 28, "MDEF": 29, "MACC": 30, "MEVA": 31, "WSACC": 48,
    "EVA": 68, "STORETP": 73, "SOULEATER": 96, "DARK_CAST": 1071, "FASTCAST": 170,
    "SKILLCHAINBONUS": 174, "DUAL_WIELD": 259, "DOUBLE_ATTACK": 288,
    "SUBTLE_BLOW": 289, "TRIPLE_ATTACK": 302, "QUADRUPLE_ATTACK": 430,
    "DRAIN_ASPIR": 315, "MAGIC_DAMAGE": 311,
    "RAPID_SHOT": 359, "SNAPSHOT": 365, "REFRESH": 369, "REGEN": 370,
    "HASTE_GEAR": 384, "WEAPON_BASH": 392, "CRIT_DMG_INCREASE": 421,
    "SKILLCHAINDMG": 175, "MAGIC_BURST": 487, "MAGIC_BURST_II": 274,
    "DREAD_SPIKES": 998, "ARCANE_CIRCLE": 1069, "DAMAGE_LIMITP": 1081,
    "NETHR": 1083, "ABSORB_DUR": 1138, "ABSORB_TP": 1153, "OCCULT": 902,
    "WS_DMG": 840, "DMG": 160, "DMGPHYS": 161, "DMGBREATH": 162,
    "DMGMAGIC": 163, "DMGRANGE": 164, "DMGPHYS_II": 190, "DMGMAGIC_II": 831,
    "ENH_MAGIC_DURATION": 890, "REGEN_DURATION": 339, "REGEN_MULTIPLIER": 838,
    "PERPETUANCE": 1221,
}

# Client skill ids (0x062 block) -> the words the item description uses.
SKILL = {
    "Hand-to-Hand": 1, "Dagger": 2, "Sword": 3, "Great Sword": 4, "Axe": 5,
    "Great Axe": 6, "Scythe": 7, "Polearm": 8, "Katana": 9, "Great Katana": 10,
    "Club": 11, "Staff": 12, "Archery": 25, "Marksmanship": 26, "Throwing": 27,
    "Guard": 28, "Evasion": 29, "Shield": 30, "Parrying": 31, "Divine Magic": 32,
    "Healing Magic": 33, "Enhancing Magic": 34, "Enfeebling Magic": 35,
    "Elemental Magic": 36, "Dark Magic": 37, "Summoning Magic": 38, "Ninjutsu": 39,
    "Singing": 40, "String Instrument": 41, "Wind Instrument": 42, "Blue Magic": 43,
    "Geomancy": 44, "Handbell": 45,
}
SKILL_ORDER = sorted(SKILL.items(), key=lambda entry: -len(entry[0]))


def parse_description(description: str):
    """(mods, skills, leftover) for one client item-description line.

    ``mods`` and ``skills`` are lists of ``(id, value)`` pairs; ``leftover`` is the
    text no rule claimed, which the caller reports when it still looks like a stat.
    """
    text = description
    text = re.sub(r"^\[[^\]]+\]\s*All Races\s*", "", text)
    text = re.sub(r"\bLV\s*\d+.*$", "", text)
    # Pet/avatar/automaton stats and conditional "Set:" bonuses are not the player's.
    text = re.split(r"\bSet\b|\bPet:|\bAvatar:|\bAutomaton:|\bWyvern:|\bLuopan:|\bFellow:",
                    text)[0]
    mods: list[tuple[int, int]] = []
    skills: list[tuple[int, int]] = []

    def take(pattern: str, mod: int | None = None, transform=None, skill: int | None = None,
             flags: int = 0):
        nonlocal text
        regex = re.compile(pattern, flags)

        def replace(match: re.Match) -> str:
            value = int(match.group(1))
            if transform:
                value = transform(value)
            if skill is not None:
                skills.append((skill, value))
            else:
                mods.append((int(mod), value))
            return " "

        text = regex.sub(replace, text)

    # Magic and ranged names first: "Magic Accuracy" must not be read as "Accuracy".
    take(r'"Magic Atk\. Bonus"\s*\+\s*(\d+)', MOD["MATT"])
    take(r'"M\. Atk\. B\."\s*\+\s*(\d+)', MOD["MATT"])
    take(r'"Magic Def\. Bonus"\s*\+\s*(\d+)', MOD["MDEF"])
    take(r'"M\. Def\. B\."\s*\+\s*(\d+)', MOD["MDEF"])
    take(r"Magic Accuracy\s*\+\s*(\d+)", MOD["MACC"])
    take(r"Mag\. Acc\.\s*\+\s*(\d+)", MOD["MACC"])
    take(r"Magic Evasion\s*\+\s*(\d+)", MOD["MEVA"])
    take(r"Mag\. Eva\.\s*\+\s*(\d+)", MOD["MEVA"])
    take(r"Ranged Accuracy\s*\+\s*(\d+)", MOD["RACC"])
    take(r"Rng\. Acc\.\s*\+\s*(\d+)", MOD["RACC"])
    take(r"Ranged Attack\s*\+\s*(\d+)", MOD["RATT"])
    take(r"Rng\. Atk\.\s*\+\s*(\d+)", MOD["RATT"])
    take(r"Weapon ?[Ss]kill Accuracy\s*\+\s*(\d+)", MOD["WSACC"])
    take(r"Accuracy\s*\+\s*(\d+)", MOD["ACC"])
    take(r"Acc\.\s*\+\s*(\d+)", MOD["ACC"])
    take(r"Attack\s*\+\s*(\d+)", MOD["ATT"])
    take(r"Atk\.\s*\+\s*(\d+)", MOD["ATT"])

    # Base values.  HP% precedes flat HP so "HP+10%" is not read as ten HP.
    take(r"DEF:(\d+)", MOD["DEF"])
    take(r"HP\s*\+\s*(\d+)%", MOD["HPP"])
    take(r"HP\s*\+\s*(\d+)", MOD["HP"])
    take(r"MP\s*\+\s*(\d+)%", 6)
    take(r"MP\s*\+\s*(\d+)", MOD["MP"])
    for name, mod_id in (("STR", 8), ("DEX", 9), ("VIT", 10), ("AGI", 11),
                         ("INT", 12), ("MND", 13), ("CHR", 14)):
        take(r"\b%s\s*\+\s*(\d+)" % name, mod_id)
    take(r"Evasion\s*\+\s*(\d+)", MOD["EVA"])
    take(r"Eva\.\s*\+\s*(\d+)", MOD["EVA"])

    # Percent bonuses: hundredths where the engine stores hundredths.
    take(r"Haste\s*\+\s*(\d+)%", MOD["HASTE_GEAR"], lambda value: value * 100)
    take(r'"Store TP"\s*\+\s*(\d+)', MOD["STORETP"])
    take(r'"Subtle Blow"\s*\+\s*(\d+)', MOD["SUBTLE_BLOW"])
    take(r'"Double Attack"\s*\+\s*(\d+)%?', MOD["DOUBLE_ATTACK"])
    take(r'"Triple Attack"\s*\+\s*(\d+)%?', MOD["TRIPLE_ATTACK"])
    take(r'"Quadruple Attack"\s*\+\s*(\d+)%?', MOD["QUADRUPLE_ATTACK"])
    take(r'"Dual Wield"\s*\+\s*(\d+)%?', MOD["DUAL_WIELD"])
    take(r'"Fast Cast"\s*\+\s*(\d+)%?', MOD["FASTCAST"])
    take(r"Critical hit rate\s*\+\s*(\d+)%?", 165)
    take(r"Critical hit damage\s*\+\s*(\d+)%?", MOD["CRIT_DMG_INCREASE"])
    take(r'"Skillchain Bonus"\s*\+\s*(\d+)', MOD["SKILLCHAINBONUS"])
    take(r'"Weapon Bash"\s*\+\s*(\d+)', MOD["WEAPON_BASH"])
    take(r'"Souleater"\s*\+\s*(\d+)', MOD["SOULEATER"])
    take(r'"Dread Spikes" potency\s*\+\s*(\d+)%?', MOD["DREAD_SPIKES"])
    take(r'"Nether Void"\s*\+\s*(\d+)', MOD["NETHR"])
    take(r'"Occult Acumen"\s*\+\s*(\d+)', MOD["OCCULT"])
    take(r'"Arcane Circle"\s*\+\s*(\d+)', MOD["ARCANE_CIRCLE"])
    take(r'"Absorb" (?:effect )?duration\s*\+\s*(\d+)%?', MOD["ABSORB_DUR"])
    take(r'"Drain" and "Aspir" (?:absorption|potency)\s*\+\s*(\d+)', MOD["DRAIN_ASPIR"])
    take(r'"Absorb-TP" effect\s*\+\s*(\d+)%?', MOD["ABSORB_TP"])
    take(r"Weapon ?[Ss]kill damage\s*\+\s*(\d+)%?", MOD["WS_DMG"])
    take(r"Physical damage limit\s*\+\s*(\d+)%?", MOD["DAMAGE_LIMITP"])
    take(r"Magic Damage\s*\+\s*(\d+)", MOD["MAGIC_DAMAGE"])
    take(r"Mag\. Dmg\.\s*\+\s*(\d+)", MOD["MAGIC_DAMAGE"])
    take(r"Magic burst damage II\s*\+\s*(\d+)", MOD["MAGIC_BURST_II"])
    take(r"Magic burst damage\s*\+\s*(\d+)", MOD["MAGIC_BURST"])
    take(r'"Refresh"\s*\+\s*(\d+)', MOD["REFRESH"])
    take(r'"Regen" effect duration\s*\+\s*(\d+)', MOD["REGEN_DURATION"])
    take(r'"Regen" duration\s*\+\s*(\d+)', MOD["REGEN_DURATION"])
    take(r'"Regen" potency\s*\+\s*(\d+)%', MOD["REGEN_MULTIPLIER"])
    take(r'"Regen"\s*\+\s*(\d+)', MOD["REGEN"])
    take(r'"Perpetuance"\s*\+\s*(\d+)%', MOD["PERPETUANCE"], lambda value: value * 100)
    take(r"Enhancing magic duration\s*\+\s*(\d+)%", MOD["ENH_MAGIC_DURATION"])
    take(r'"Snapshot"\s*\+\s*(\d+)', MOD["SNAPSHOT"])
    take(r'"Rapid Shot"\s*\+\s*(\d+)', MOD["RAPID_SHOT"])
    take(r"Dark magic casting time\s*-\s*(\d+)%", MOD["DARK_CAST"], lambda value: -value)

    # Damage taken: the II variants first, then the specific types, then DT.
    take(r"Physical damage taken II\s*-\s*(\d+)%", MOD["DMGPHYS_II"],
         lambda value: -value * 100)
    take(r"Magic damage taken II\s*-\s*(\d+)%", MOD["DMGMAGIC_II"],
         lambda value: -value * 100)
    take(r"Physical damage taken\s*-\s*(\d+)%", MOD["DMGPHYS"],
         lambda value: -value * 100)
    take(r"Magic damage taken\s*-\s*(\d+)%", MOD["DMGMAGIC"],
         lambda value: -value * 100)
    take(r"Breath damage taken\s*-\s*(\d+)%", MOD["DMGBREATH"],
         lambda value: -value * 100)
    take(r"Ranged damage taken\s*-\s*(\d+)%", MOD["DMGRANGE"],
         lambda value: -value * 100)
    take(r"Damage taken\s*-\s*(\d+)%", MOD["DMG"], lambda value: -value * 100)
    take(r"Enmity\s*\+\s*(\d+)", MOD["ENMITY"])
    take(r"Enmity\s*-\s*(\d+)", MOD["ENMITY"], lambda value: -value)

    # Skill bonuses go to their own table, with the client's skill ids.
    for name, skill_id in SKILL_ORDER:
        take(r"%s skill\s*\+\s*(\d+)" % re.escape(name), skill=skill_id, flags=re.I)

    return mods, skills, text


def looks_like_stat(leftover: str) -> bool:
    """Whether unclaimed text still carries a stat-shaped token."""
    return bool(re.search(r"[A-Za-z][A-Za-z .'\"\-]{2,}\s*[+-]\s*\d", leftover))


def build_rows(documents: dict[str, dict]):
    """(per-item mods, per-item skills, warnings) from the id -> description map."""
    mods: dict[int, dict[int, int]] = {}
    skills: dict[int, dict[int, int]] = {}
    warnings: list[str] = []
    for raw_id, entry in sorted(documents.items(), key=lambda item: int(item[0])):
        item_id = int(raw_id)
        description = entry.get("description") or ""
        item_mods, item_skills, leftover = parse_description(description)
        if not item_mods:
            warnings.append("%d %s: no stats parsed" % (item_id, entry.get("name", "?")))
            continue
        mod_table = mods.setdefault(item_id, {})
        for mod_id, value in item_mods:
            mod_table[mod_id] = mod_table.get(mod_id, 0) + value
        skill_table = skills.setdefault(item_id, {})
        for skill_id, value in item_skills:
            skill_table[skill_id] = skill_table.get(skill_id, 0) + value
        leftover = re.sub(r"\s+", " ", leftover).strip()
        if looks_like_stat(leftover):
            warnings.append("%d %s: unparsed %r" % (item_id, entry.get("name", "?"),
                                                    leftover[:100]))
    return mods, skills, warnings


def quote(value) -> str:
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(int(value))


def emit_rows(lines: list[str], table: str, columns: tuple[str, ...],
              rows: list[tuple], *, verb: str = "INSERT") -> None:
    head = "%s INTO %s (%s) VALUES " % (verb, table, ", ".join(columns))
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start:start + CHUNK]
        lines.append(head + ", ".join(
            "(%s)" % ", ".join(quote(value) for value in row) for row in chunk) + ";")
        lines.append("")


def render(documents: dict[str, dict]) -> tuple[str, list[str], int, int]:
    mods, skills, warnings = build_rows(documents)
    item_ids = sorted(mods)
    mod_rows = [(item_id, mod_id, value)
                for item_id in item_ids
                for mod_id, value in sorted(mods[item_id].items())]
    skill_rows = [(item_id, skill_id, value)
                  for item_id in sorted(skills)
                  for skill_id, value in sorted(skills[item_id].items())]

    lines: list[str] = []
    lines.append("-- Reforged armour and worn-piece stats (migration 92), generated by")
    lines.append("-- tools/import_reforged_item_data.py from tools/data/reforged_item_stats.json.")
    lines.append("--")
    lines.append("-- LandSandBoat leaves the +3 empyrean and +4 artifact/relic armour sets as")
    lines.append("-- \"Not implemented\" placeholders with no item_mods rows, and the prime weapon")
    lines.append("-- and belt added by earlier Fanxi migrations had none either.  The client drew")
    lines.append("-- the real tooltip from its DAT while the server saw bare slots, so the status")
    lines.append("-- menu showed only accessory bonuses and combat used no gear Attack, Defence,")
    lines.append("-- Accuracy or damage taken.  The rows below are the client's own stat lines.")
    lines.append("--")
    lines.append("-- Item ids: %s" % ", ".join(str(item_id) for item_id in item_ids))
    lines.append("")
    # A fresh database did not get every reforged item row from the earlier grants
    # (the Scholar +3/+4 sets were added to the live database by hand), and
    # item_skill_bonus has a foreign key to items.  Re-state the catalogue rows so the
    # migration stands on its own; OR IGNORE leaves existing rows untouched.
    item_rows = []
    for item_id in item_ids:
        item = documents[str(item_id)].get("item")
        if item:
            item_rows.append(tuple(item[column] for column in ITEM_COLUMNS))
    if item_rows:
        emit_rows(lines, "items", ITEM_COLUMNS, item_rows, verb="INSERT OR IGNORE")
    lines.append("DELETE FROM item_mods WHERE item_id IN (%s);"
                 % ", ".join(str(item_id) for item_id in item_ids))
    lines.append("DELETE FROM item_skill_bonus WHERE item_id IN (%s);"
                 % ", ".join(str(item_id) for item_id in item_ids))
    lines.append("")
    emit_rows(lines, "item_mods", ("item_id", "mod_id", "value"), mod_rows)
    emit_rows(lines, "item_skill_bonus", ("item_id", "skill_id", "amount"), skill_rows)
    return "\n".join(lines), warnings, len(mod_rows), len(skill_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help="JSON map of item id -> {name, description}")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="migration file to write (default: %(default)s)")
    parser.add_argument("--check", action="store_true",
                        help="only report unparsed stat-shaped text")
    args = parser.parse_args()

    documents = json.loads(args.source.read_text(encoding="utf-8"))
    text, warnings, mod_count, skill_count = render(documents)
    for warning in warnings:
        print(warning)
    if args.check:
        return 0
    args.output.write_text(text + "\n", encoding="utf-8")
    print("wrote %s (%d items, %d stat rows, %d skill rows)"
          % (args.output, len(documents), mod_count, skill_count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
