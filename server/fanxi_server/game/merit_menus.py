"""The merit menu the launcher draws, organised the way the client does.

`merits` owns the ids, upgrade ladders and category caps.  This module adds the
human labels and the menu order: the six general categories first, then Group 1 and
Group 2 for every job in the client's job order.  The launcher reads this through
``service.character_data`` and writes changes back through the same merits endpoint.

The labels are functional game facts (the merit menu's own wording); the grouping,
schema and lookup code are Fanxi's own.
"""
from __future__ import annotations

from . import merits

# The six menus above the job list, in the client's order.  The third item is the
# one-line hint the launcher shows under the menu title.
GENERAL_CATEGORIES = (
    (0x0040, "HP/MP", "Maximum HP, maximum MP and the size of the merit pool."),
    (0x0080, "Attributes", "STR, DEX, VIT, AGI, INT, MND and CHR."),
    (0x00C0, "Combat Skills", "Weapon and defensive combat skills."),
    (0x0100, "Magic Skills", "Magic, song and ninjutsu skills."),
    (0x0140, "Other", "Enmity, critical hit rate and spell interruption."),
    (0x0680, "Weapon Skills", "The merit weapon skills."),
)

JOB_NAMES = {
    1: "Warrior", 2: "Monk", 3: "White Mage", 4: "Black Mage", 5: "Red Mage",
    6: "Thief", 7: "Paladin", 8: "Dark Knight", 9: "Beastmaster", 10: "Bard",
    11: "Ranger", 12: "Samurai", 13: "Ninja", 14: "Dragoon", 15: "Summoner",
    16: "Blue Mage", 17: "Corsair", 18: "Puppetmaster", 19: "Dancer",
    20: "Scholar", 21: "Geomancer", 22: "Rune Fencer",
}
JOB_ABBRS = {
    1: "WAR", 2: "MNK", 3: "WHM", 4: "BLM", 5: "RDM", 6: "THF", 7: "PLD",
    8: "DRK", 9: "BST", 10: "BRD", 11: "RNG", 12: "SAM", 13: "NIN", 14: "DRG",
    15: "SMN", 16: "BLU", 17: "COR", 18: "PUP", 19: "DNC", 20: "SCH",
    21: "GEO", 22: "RUN",
}

# job id -> (Group 1 category, Group 2 category)
JOB_GROUPS = {
    1: (0x0180, 0x0800), 2: (0x01C0, 0x0840), 3: (0x0200, 0x0880),
    4: (0x0240, 0x08C0), 5: (0x0280, 0x0900), 6: (0x02C0, 0x0940),
    7: (0x0300, 0x0980), 8: (0x0340, 0x09C0), 9: (0x0380, 0x0A00),
    10: (0x03C0, 0x0A40), 11: (0x0400, 0x0A80), 12: (0x0440, 0x0AC0),
    13: (0x0480, 0x0B00), 14: (0x04C0, 0x0B40), 15: (0x0500, 0x0B80),
    16: (0x0540, 0x0BC0), 17: (0x0580, 0x0C00), 18: (0x05C0, 0x0C40),
    19: (0x0600, 0x0C80), 20: (0x0640, 0x0CC0), 21: (0x06C0, 0x0D40),
    22: (0x0700, 0x0D80),
}

# merit id -> the row label.  Kept by id rather than by position so a category
# whose rows the wiki lists out of order (Geomancer Group 2) still lands correctly.
MERIT_NAMES = {
    0x0040: "Max HP",
    0x0042: "Max MP",
    0x0044: "Maximum Merit Points",
    0x0080: "STR",
    0x0082: "DEX",
    0x0084: "VIT",
    0x0086: "AGI",
    0x0088: "INT",
    0x008A: "MND",
    0x008C: "CHR",
    0x00C0: "Hand-to-Hand Skill",
    0x00C2: "Dagger Skill",
    0x00C4: "Sword Skill",
    0x00C6: "Great Sword Skill",
    0x00C8: "Axe Skill",
    0x00CA: "Great Axe Skill",
    0x00CC: "Scythe Skill",
    0x00CE: "Polearm Skill",
    0x00D0: "Katana Skill",
    0x00D2: "Great Katana Skill",
    0x00D4: "Club Skill",
    0x00D6: "Staff Skill",
    0x00D8: "Archery Skill",
    0x00DA: "Marksmanship Skill",
    0x00DC: "Throwing Skill",
    0x00DE: "Guarding Skill",
    0x00E0: "Evasion Skill",
    0x00E2: "Shield Skill",
    0x00E4: "Parrying Skill",
    0x0100: "Divine Magic Skill",
    0x0102: "Healing Magic Skill",
    0x0104: "Enhancing Magic Skill",
    0x0106: "Enfeebling Magic Skill",
    0x0108: "Elemental Magic Skill",
    0x010A: "Dark Magic Skill",
    0x010C: "Summoning Magic Skill",
    0x010E: "Ninjutsu Skill",
    0x0110: "Singing Skill",
    0x0112: "String Instrument Skill",
    0x0114: "Wind Instrument Skill",
    0x0116: "Blue Magic Skill",
    0x0118: "Geomancy Skill",
    0x011A: "Handbell Skill",
    0x0140: "Enmity Increase",
    0x0142: "Enmity Decrease",
    0x0144: "Critical Hit Rate",
    0x0146: "Enemy Critical Hit Rate",
    0x0148: "Spell Interruption Rate",
    0x0680: "Shijin Spiral",
    0x0682: "Exenterator",
    0x0684: "Requiescat",
    0x0686: "Resolution",
    0x0688: "Ruinator",
    0x068A: "Upheaval",
    0x068C: "Entropy",
    0x068E: "Stardiver",
    0x0690: "Blade: Shun",
    0x0692: "Tachi: Shoha",
    0x0694: "Realmrazer",
    0x0696: "Shattersoul",
    0x0698: "Apex Arrow",
    0x069A: "Last Stand",
    0x0180: "Berserk Recast",
    0x0182: "Defender Recast",
    0x0184: "Warcry Recast",
    0x0186: "Aggressor Recast",
    0x0188: "Double Attack Rate",
    0x0800: "Warrior's Charge",
    0x0802: "Tomahawk",
    0x0804: "Savagery",
    0x0806: "Aggressive Aim",
    0x01C0: "Focus Recast",
    0x01C2: "Dodge Recast",
    0x01C4: "Chakra Recast",
    0x01C6: "Counter Rate",
    0x01C8: "Kick Attack Rate",
    0x0840: "Mantra",
    0x0842: "Formless Strikes",
    0x0844: "Invigorate",
    0x0846: "Penance",
    0x0200: "Divine Seal Recast",
    0x0202: "Cure Cast Time",
    0x0204: "Barspell Effect",
    0x0206: "Banish Effect",
    0x0208: "Regen Effect",
    0x0880: "Martyr",
    0x0882: "Devotion",
    0x0888: "Animus Solace",
    0x088A: "Animus Misery",
    0x0240: "Elemental Seal Recast",
    0x0242: "Fire Magic Potency",
    0x0244: "Ice Magic Potency",
    0x0246: "Wind Magic Potency",
    0x0248: "Earth Magic Potency",
    0x024A: "Lightning Magic Potency",
    0x024C: "Water Magic Potency",
    0x08CC: "Ancient Magic Attack Bonus",
    0x08CE: "Ancient Magic Burst Damage",
    0x08D0: "Elemental Magic Accuracy",
    0x08D2: "Elemental Debuff Duration",
    0x08D4: "Elemental Debuff Effect",
    0x08D6: "Aspir Absorption Amount",
    0x0280: "Convert Recast",
    0x0282: "Fire Magic Accuracy",
    0x0284: "Ice Magic Accuracy",
    0x0286: "Wind Magic Accuracy",
    0x0288: "Earth Magic Accuracy",
    0x028A: "Lightning Magic Accuracy",
    0x028C: "Water Magic Accuracy",
    0x090C: "Enfeebling Magic Duration",
    0x090E: "Magic Accuracy",
    0x0910: "Enhancing Magic Duration",
    0x0912: "Immunobreak Chance",
    0x0914: "Enspell Damage",
    0x0916: "Accuracy",
    0x02C0: "Flee Recast",
    0x02C2: "Hide Recast",
    0x02C4: "Sneak Attack Recast",
    0x02C6: "Trick Attack Recast",
    0x02C8: "Triple Attack Rate",
    0x0940: "Assassin's Charge",
    0x0942: "Feint",
    0x0944: "Aura Steal",
    0x0946: "Ambush",
    0x0300: "Shield Bash Recast",
    0x0302: "Holy Circle Recast",
    0x0304: "Sentinel Recast",
    0x0306: "Cover Effect Length",
    0x0308: "Rampart Recast",
    0x0980: "Fealty",
    0x0982: "Chivalry",
    0x0984: "Iron Will",
    0x0986: "Guardian",
    0x0340: "Souleater Recast",
    0x0342: "Arcane Circle Recast",
    0x0344: "Last Resort Recast",
    0x0346: "Last Resort Effect",
    0x0348: "Weapon Bash Recast",
    0x09C0: "Dark Seal",
    0x09C2: "Diabolic Eye",
    0x09C4: "Muted Soul",
    0x09C6: "Desperate Blows",
    0x0380: "Killer Effects",
    0x0382: "Reward Recast",
    0x0384: "Call Beast Recast",
    0x0386: "Sic/Ready Recast",
    0x0388: "Tame Recast",
    0x0A00: "Feral Howl",
    0x0A02: "Killer Instinct",
    0x0A04: "Beast Affinity",
    0x0A06: "Beast Healer",
    0x03C0: "Lullaby Recast",
    0x03C2: "Finale Recast",
    0x03C4: "Minne Effect",
    0x03C6: "Minuet Effect",
    0x03C8: "Madrigal Effect",
    0x0A40: "Nightingale",
    0x0A42: "Troubadour",
    0x0A48: "Con Anima",
    0x0A4A: "Con Brio",
    0x0400: "Scavenge Effect",
    0x0402: "Camouflage Recast",
    0x0404: "Sharpshot Recast",
    0x0406: "Unlimited Shot Recast",
    0x0408: "Rapid Shot Rate",
    0x0A80: "Stealth Shot",
    0x0A82: "Flashy Shot",
    0x0A84: "Snapshot",
    0x0A86: "Recycle Rate",
    0x0440: "Third Eye Recast",
    0x0442: "Warding Circle Recast",
    0x0444: "Store TP Effect",
    0x0446: "Meditate Recast",
    0x0448: "Zanshin Attack Rate",
    0x0AC0: "Shikikoyo",
    0x0AC2: "Blade Bash",
    0x0AC4: "Ikishoten",
    0x0AC6: "Overwhelm",
    0x0480: "Subtle Blow Effect",
    0x0482: "Katon Effect",
    0x0484: "Hyoton Effect",
    0x0486: "Huton Effect",
    0x0488: "Doton Effect",
    0x048A: "Raiton Effect",
    0x048C: "Suiton Effect",
    0x0B00: "Sange",
    0x0B02: "Ninja Tool Expertise",
    0x0B10: "Yonin Effect",
    0x0B12: "Innin Effect",
    0x0B14: "Ninjutsu Magic Accuracy",
    0x0B16: "Ninjutsu Magic Attack Bonus",
    0x04C0: "Ancient Circle Recast",
    0x04C2: "Jump Recast",
    0x04C4: "High Jump Recast",
    0x04C6: "Super Jump Recast",
    0x04C8: "Spirit Link Recast",
    0x0B40: "Deep Breathing",
    0x0B42: "Angon",
    0x0B44: "Empathy",
    0x0B46: "Strafe",
    0x0500: "Avatar Physical Accuracy",
    0x0502: "Avatar Physical Attack",
    0x0504: "Avatar Magical Accuracy",
    0x0506: "Avatar Magical Attack",
    0x0508: "Summoning Magic Cast Time",
    0x0B80: "Meteor Strike",
    0x0B82: "Heavenly Strike",
    0x0B84: "Wind Blade",
    0x0B86: "Geocrush",
    0x0B88: "Thunderstorm",
    0x0B8A: "Grand Fall",
    0x0540: "Chain Affinity Recast",
    0x0542: "Burst Affinity Recast",
    0x0544: "Monster Correlation",
    0x0546: "Physical Potency",
    0x0548: "Magical Accuracy",
    0x0BC0: "Convergence",
    0x0BC2: "Diffusion",
    0x0BC4: "Enchainment",
    0x0BC6: "Assimilation",
    0x0580: "Phantom Roll Recast",
    0x0582: "Quick Draw Recast",
    0x0584: "Quick Draw Accuracy",
    0x0586: "Random Deal Recast",
    0x0588: "Bust Duration",
    0x0C00: "Snake Eye",
    0x0C02: "Fold",
    0x0C04: "Winning Streak",
    0x0C06: "Loaded Deck",
    0x05C0: "Automaton Skills",
    0x05C2: "Maintenance Recast",
    0x05C4: "Repair Effect",
    0x05C6: "Activate Recast",
    0x05C8: "Repair Recast",
    0x0C40: "Role Reversal",
    0x0C42: "Ventriloquy",
    0x0C44: "Fine-Tuning",
    0x0C46: "Optimization",
    0x0600: "Step Accuracy",
    0x0602: "Haste Samba Effect",
    0x0604: "Reverse Flourish Effect",
    0x0606: "Building Flourish Effect",
    0x0C80: "Saber Dance",
    0x0C82: "Fan Dance",
    0x0C84: "No Foot Rise",
    0x0C86: "Closed Position",
    0x0640: "Grimoire Recast",
    0x0642: "Modus Veritas Duration",
    0x0644: "Helix Magic Acc./Atk.",
    0x0646: "Max Sublimation",
    0x0CC0: "Altruism",
    0x0CC2: "Focalization",
    0x0CC4: "Tranquility",
    0x0CC6: "Equanimity",
    0x0CC8: "Enlightenment",
    0x0CCA: "Stormsurge",
    0x06C0: "Full Circle Effect",
    0x06C2: "Ecliptic Attunement Recast",
    0x06C4: "Life Cycle Recast",
    0x06C6: "Blaze of Glory Recast",
    0x06C8: "Dematerialize Recast",
    0x0D40: "Mending Halation",
    0x0D42: "Radial Arcana",
    0x0D44: "Curative Recantation",
    0x0D46: "Primeval Zeal",
    0x0700: "Rune Enhancement Effect",
    0x0702: "Vallation Effect",
    0x0704: "Lunge Effect",
    0x0706: "Pflug Effect",
    0x0708: "Gambit Effect",
    0x0D80: "Battuta",
    0x0D82: "Rayke",
    0x0D84: "Inspiration",
    0x0D86: "Sleight of Sword",
}

# The client's menu order: the general categories, then each job's two groups.
def _category_order() -> tuple[int, ...]:
    order = [category for category, _, _ in GENERAL_CATEGORIES]
    for group_1, group_2 in JOB_GROUPS.values():
        order += [group_1, group_2]
    return tuple(order)


CATEGORY_ORDER = _category_order()

# A category id the client knows but this module forgot would silently disappear
# from the editor, so refuse to import instead of shipping a partial menu.
if set(CATEGORY_ORDER) != set(merits.CATEGORY_MAX):
    raise RuntimeError("merit menu categories do not match the merit table")
if set(MERIT_NAMES) != set(merits.MERITS):
    raise RuntimeError("merit menu labels do not match the merit table")


# category id -> the static part of its catalog row
CATEGORY_INFO: dict[int, dict] = {}
for category_id, name, hint in GENERAL_CATEGORIES:
    CATEGORY_INFO[category_id] = {
        "name": name,
        "hint": hint,
        "kind": "general",
        "job": 0,
        "job_name": "",
        "job_abbr": "",
        "group": 0,
    }
for job, (group_1, group_2) in JOB_GROUPS.items():
    job_name = JOB_NAMES[job]
    CATEGORY_INFO[group_1] = {
        "name": f"{job_name} Group 1",
        "hint": "Recast timers, accuracy, potency and rates.",
        "kind": "job",
        "job": job,
        "job_name": job_name,
        "job_abbr": JOB_ABBRS[job],
        "group": 1,
    }
    CATEGORY_INFO[group_2] = {
        "name": f"{job_name} Group 2",
        "hint": "Merit abilities, spells and traits.",
        "kind": "job",
        "job": job,
        "job_name": job_name,
        "job_abbr": JOB_ABBRS[job],
        "group": 2,
    }


def catalog(counts: dict[int, int] | None = None) -> list[dict]:
    """Every menu and merit row for one character, in the client's order.

    Each row carries its static data (max ranks, value, cost ladder) and the
    character's current rank, spent points and next cost.  The launcher uses the
    same payload to draw the forms and to preview an unsaved layout.
    """
    counts = {int(merit_id): max(0, int(upgrades))
              for merit_id, upgrades in (counts or {}).items()}
    by_category: dict[int, list[int]] = {}
    for merit_id, entry in merits.MERITS.items():
        by_category.setdefault(int(entry[0]), []).append(int(merit_id))

    menus: list[dict] = []
    for category_id in CATEGORY_ORDER:
        info = CATEGORY_INFO[category_id]
        rows: list[dict] = []
        used = 0
        spent = 0
        for merit_id in by_category.get(category_id, []):
            _, cost_key, max_upgrades, value = merits.MERITS[merit_id]
            upgrades = max(0, min(int(counts.get(merit_id, 0)), int(max_upgrades)))
            row_spent = merits.merit_cost(merit_id, upgrades)
            rows.append({
                "id": merit_id,
                "name": MERIT_NAMES[merit_id],
                "max": int(max_upgrades),
                "value": int(value),
                "costs": [int(cost) for cost in merits.COSTS[cost_key]],
                "upgrades": upgrades,
                "spent": int(row_spent),
                "next_cost": int(merits.next_cost(merit_id, upgrades)),
            })
            used += upgrades
            spent += row_spent
        menus.append({
            "id": int(category_id),
            **info,
            "max": int(merits.CATEGORY_MAX[category_id]),
            "used": int(used),
            "spent": int(spent),
            "merits": rows,
        })
    return menus
