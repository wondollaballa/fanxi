"""Shantotto's Ascension gear and the two augments each copy can carry.

The add-on's three leg pieces (Blitzer Poleyn, Desultor Tassets and Tatsumaki
Sitagoromo) are Rare/Ex and share one reward table: on obtaining a piece the player
picks two different rows from the list below, and the client stores them in the
same 24-byte ``AugmentStandard`` block the Ambuscade capes use.  The block holds
``(augment id, value)`` words, so the two rows are written in one ``0x02 0x03``
block.

The ids and values are the client's packet-augment ids; :mod:`capes` owns the
value-to-text table.  ``Phantom Roll`` is augment 0x154; its block value is one
less than the displayed seconds, exactly like the other ability-delay rows in the
shared table, so -5 seconds is ``(0x154, 4)``.
"""
from __future__ import annotations

from . import capes

# The three rewards, with the full names the UI shows.  The item table abbreviates
# Tatsumaki Sitagoromo to the client's 15-character name.
ITEMS = (
    {"item_id": 16369, "name": "Blitzer Poleyn", "slot": "Legs"},
    {"item_id": 16370, "name": "Desultor Tassets", "slot": "Legs"},
    {"item_id": 16371, "name": "Tatsumaki Sitagoromo", "slot": "Legs"},
)
ITEM_IDS = frozenset(int(item["item_id"]) for item in ITEMS)
ITEM_BY_ID = {int(item["item_id"]): item for item in ITEMS}

# One row per choice in the add-on's table.  ``slots`` is the list of
# (augment id, block value) words the choice writes; almost every row is one word,
# and the combined pet Store TP/Subtle Blow row is two.
OPTIONS = (
    {"key": "hp_25", "label": "HP +25",
     "slots": ((0x001, 24),)},
    {"key": "enmity_4", "label": "Enmity +4",
     "slots": ((0x027, 3),)},
    {"key": "crit_dmg_3", "label": "Critical hit damage +3%",
     "slots": ((0x148, 2),)},
    {"key": "song_recast_3", "label": "Song recast -3",
     "slots": ((0x151, 2),)},
    {"key": "mp_25", "label": "MP +25",
     "slots": ((0x009, 24),)},
    {"key": "enmity_minus_4", "label": "Enmity -4",
     "slots": ((0x028, 3),)},
    {"key": "skillchain_5", "label": "Skillchain damage +5%",
     "slots": ((0x14C, 4),)},
    {"key": "rapid_shot_1", "label": "Rapid Shot +1",
     "slots": ((0x08B, 0),)},
    {"key": "accuracy_7", "label": "Accuracy +7",
     "slots": ((0x017, 6),)},
    {"key": "conserve_tp_5", "label": "Conserve TP +5",
     "slots": ((0x14D, 4),)},
    {"key": "elemental_siphon_20", "label": "Elemental Siphon +20",
     "slots": ((0x153, 3),)},
    {"key": "attack_7", "label": "Attack +7",
     "slots": ((0x019, 6),)},
    {"key": "phys_taken_4", "label": "Physical damage taken -4%",
     "slots": ((0x036, 3),)},
    {"key": "phantom_roll_5", "label": "Phantom Roll -5",
     "slots": ((0x154, 4),)},
    {"key": "ranged_accuracy_7", "label": "Ranged Accuracy +7",
     "slots": ((0x01B, 6),)},
    {"key": "magic_crit_dmg_10", "label": "Magic critical hit damage +10%",
     "slots": ((0x14F, 9),)},
    {"key": "repair_10", "label": "Repair potency +10%",
     "slots": ((0x155, 9),)},
    {"key": "ranged_attack_7", "label": "Ranged Attack +7",
     "slots": ((0x01D, 6),)},
    {"key": "magic_burst_10", "label": "Magic burst damage +10%",
     "slots": ((0x14E, 9),)},
    {"key": "waltz_tp_50", "label": "Waltz TP cost -50",
     "slots": ((0x156, 4),)},
    {"key": "evasion_7", "label": "Evasion +7",
     "slots": ((0x01F, 6),)},
    {"key": "kick_5", "label": "Kick Attacks +5",
     "slots": ((0xC2, 4),)},
    {"key": "pet_acc_7", "label": "Pet: Accuracy +7 / Ranged Accuracy +7",
     "slots": ((0x060, 6),)},
    {"key": "magic_accuracy_4", "label": "Magic Accuracy +4",
     "slots": ((0x023, 3),)},
    {"key": "cure_potency_5", "label": "Cure potency +5%",
     "slots": ((0x149, 4),)},
    {"key": "pet_attack_7", "label": "Pet: Attack +7 / Ranged Attack +7",
     "slots": ((0x061, 6),)},
    {"key": "magic_attack_4", "label": "Magic Attack Bonus +4",
     "slots": ((0x085, 3),)},
    {"key": "sic_ready_5", "label": "Sic / Ready recast -5",
     "slots": ((0x150, 4),)},
    {"key": "pet_store_tp_8", "label": "Pet: Store TP +8 / Subtle Blow +8",
     "slots": ((0x073, 7), (0x074, 7))},
    {"key": "haste_3", "label": "Haste +3%",
     "slots": ((0x031, 2),)},
    {"key": "pet_magic_accuracy_7", "label": "Pet: Magic Accuracy +7",
     "slots": ((0x064, 6),)},
    {"key": "double_attack_2", "label": "Double Attack +2%",
     "slots": ((0x08F, 1),)},
    {"key": "movement_speed_8", "label": "Movement speed +8%",
     "slots": ((0x391, 7),)},
)
OPTION_BY_KEY = {str(option["key"]): option for option in OPTIONS}


def option_text(option: dict) -> str:
    """The server text for one option, built from the same table the client uses."""
    return " · ".join(capes.slot_text({"id": augment_id, "value": value})
                      for augment_id, value in option["slots"])


def block_for(choices) -> bytes:
    """Encode up to two chosen rows into the item's 24-byte standard block."""
    if choices is None:
        choices = []
    if isinstance(choices, str):
        choices = [choices]
    keys = [str(key) for key in choices if str(key)]
    if len(keys) > 2:
        raise ValueError("choose at most two augments")
    if len(set(keys)) != len(keys):
        raise ValueError("each augment can only be chosen once")
    words: list[tuple[int, int]] = []
    for key in keys:
        option = OPTION_BY_KEY.get(key)
        if option is None:
            raise ValueError("unknown Shantotto's Ascension augment: %s" % key)
        words.extend(option["slots"])
    if len(words) > 5:
        raise ValueError("that pair needs more augment slots than the item has")
    return capes.encode_slots(words) if words else b""


def current_keys(extra: bytes | None) -> list[str]:
    """The option keys already in a copy's block, in table order."""
    slots = capes.decode(extra)
    if slots is None:
        return []
    remaining = [(int(slot["id"]), int(slot["value"]))
                 for slot in slots if int(slot.get("id") or 0)]
    keys: list[str] = []
    for option in OPTIONS:
        if all(word in remaining for word in option["slots"]):
            keys.append(str(option["key"]))
            for word in option["slots"]:
                remaining.remove(word)
    return keys


def catalog(service, character_id: int) -> dict:
    """Every Ascension item with its bag copies, plus the shared option table."""
    by_item: dict[int, list[dict]] = {item_id: [] for item_id in ITEM_IDS}
    for row in service.inventory(int(character_id)):
        item_id = int(row["item_id"])
        if item_id not in by_item:
            continue
        extra = bytes(row.get("extra") or b"")
        by_item[item_id].append({
            "container": int(row["container"]),
            "slot": int(row["slot"]),
            "container_name": capes.container_label(int(row["container"])),
            "text": capes.describe(extra) if extra else "not augmented",
            "choices": current_keys(extra),
        })
    items = []
    for item_id, spec in ITEM_BY_ID.items():
        copies = sorted(by_item[item_id], key=lambda copy: (copy["container"], copy["slot"]))
        params = {"item_id": item_id, "name": spec["name"], "slot": spec["slot"],
                  "copies": copies}
        items.append(params)
    return {
        "items": items,
        "options": [{"key": str(option["key"]), "label": option["label"],
                     "text": option_text(option)} for option in OPTIONS],
    }
