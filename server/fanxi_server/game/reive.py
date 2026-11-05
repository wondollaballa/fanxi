"""Reive and Incursion JSE capes and Detrovio's Refractive Crystal augments.

The 22 capes below are the level-99 job capes that drop from Colonization and
Lair Reives in Marjami Ravine, Yorcia Weald, Kamihr Drifts and Ra'Kaznar; the
augmented versions also come from Incursion coffers.  Detrovio at the
Inventors' Coalition in Western Adoulin (J-10) augments one of them for a
Refractive Crystal and a Bayld fee, and Makel-Pakel at the Celennia Memorial
Library removes the augment again for free.

Retail rolls several of the cape's four rows in one trade, each at its own
random potency; a copy can carry all four at once.  A fully augmented
Pastoralist's Mantle, for example, shows ``STR+1 DEX+1 Accuracy+1 Pet: Damage
taken-5% Pet: Accuracy+20 Rng. Acc.+20``.  The launcher's Data page instead lets
the player choose which rows to write and at what value, the same way the
Ambuscade and Skirmish cards write their maxima.

The client stores the result in the **standard four-word augment block** the
Ambuscade capes and Skirmish gear use::

    02 03  <row 0> <row 1> <row 2> <row 3>  00 00 ...  (24 bytes)

Each word is the usual little-endian ``id:11 | value:5`` word, and the rows are
in BG Wiki's table order.  The editor leaves the fifth slot as-is (normally
zero).  The ids are the client's
packet-augment ids (the same ids :mod:`capes` prints and :mod:`augment_stats`
reads), so a Detrovio cape shows up in the tooltip and in the stat sheet
without a second decoder.

BG Wiki's ``STR/DEX`` row is the client's one combined word (id 0x226), not two
separate words: it prints ``STR+1 DEX+1`` from a single slot.  The page table is
``Category:JSE_Capes#Reive_and_Incursion_Capes`` captured 2026-11-04.
"""

from __future__ import annotations

from . import capes

# Four rows, one client word each; the fifth standard slot is preserved as-is.
SLOTS = 4


def container_label(container: int) -> str:
    return capes.container_label(container)


def _row(key: str, label: str, augment_id: int, minimum: int, maximum: int,
         *, step: int = 1, offset: int = 1, multiplier: int = 1) -> dict:
    """One word of a cape's BG Wiki augment table.

    ``minimum``/``maximum`` are the signed values the client prints, so a
    reduction runs from ``-5`` to ``-1``.  ``offset`` and ``step`` describe the
    client's five-bit word: ``stored = abs(value) // step - offset``.  The
    common row is offset 1 and step 1, which is why HP+1 is word 0.
    """
    return {
        "key": str(key),
        "label": str(label),
        "id": int(augment_id),
        "minimum": int(minimum),
        "maximum": int(maximum),
        "step": int(step),
        "offset": int(offset),
        "multiplier": int(multiplier),
    }


# Every cape has four rows, one client word each, in BG Wiki's table order.
# A trade may fill any subset of them.
JOBS = {
    "WAR": {
        "item_id": 28617,
        "name": "Mauler's Mantle",
        "rows": (
            _row("str", "STR", 0x200, 1, 5),
            _row("dex", "DEX", 0x201, 1, 5),
            _row("accuracy", "Accuracy", 0x017, 1, 7),
            _row("crit_damage", "Critical Hit Damage", 0x148, 1, 3),
        ),
    },
    "MNK": {
        "item_id": 28618,
        "name": "Anchoret's Mantle",
        "rows": (
            _row("str", "STR", 0x200, 1, 5),
            _row("dex", "DEX", 0x201, 1, 5),
            _row("counter", "Counter", 0x091, 1, 5),
            _row("subtle_blow", "Subtle Blow", 0x0C3, 1, 5),
        ),
    },
    "WHM": {
        "item_id": 28619,
        "name": "Mending Cape",
        "rows": (
            _row("macc", "Magic Accuracy", 0x023, 1, 10),
            _row("healing_skill", "Healing Magic Skill", 0x121, 1, 10),
            _row("enhancing_skill", "Enhancing Magic Skill", 0x122, 1, 10),
            _row("cure_potency", "Cure Potency", 0x149, 1, 5),
        ),
    },
    "BLM": {
        "item_id": 28620,
        "name": "Bane Cape",
        "rows": (
            _row("mab", "Magic Atk. Bonus", 0x085, 1, 5),
            _row("elemental_skill", "Elemental Magic Skill", 0x124, 1, 10),
            _row("dark_skill", "Dark Magic Skill", 0x125, 1, 10),
            _row("fast_cast", "Fast Cast", 0x08C, 1, 5),
        ),
    },
    "RDM": {
        "item_id": 28621,
        "name": "Ghostfyre Cape",
        "rows": (
            _row("macc", "Magic Accuracy", 0x023, 1, 10),
            _row("enfeebling_skill", "Enfeebling Magic Skill", 0x123, 1, 10),
            _row("enhancing_skill", "Enhancing Magic Skill", 0x122, 1, 10),
            _row("enhancing_duration", "Enhancing Magic Duration", 0x4E0, 10, 20),
        ),
    },
    "THF": {
        "item_id": 28622,
        "name": "Canny Cape",
        "rows": (
            _row("dex", "DEX", 0x201, 1, 5),
            _row("agi", "AGI", 0x203, 1, 5),
            _row("dual_wield", "Dual Wield", 0x092, 1, 5),
            _row("crit_damage", "Critical Hit Damage", 0x148, 1, 3),
        ),
    },
    "PLD": {
        "item_id": 28623,
        "name": "Weard Mantle",
        "rows": (
            _row("dex", "DEX", 0x201, 1, 5),
            _row("vit", "VIT", 0x202, 1, 5),
            _row("enmity", "Enmity", 0x027, 1, 7),
            _row("phalanx", "Phalanx", 0x170, 1, 5),
        ),
    },
    "DRK": {
        "item_id": 28624,
        "name": "Niht Mantle",
        "rows": (
            _row("attack", "Attack", 0x019, 5, 15),
            _row("dark_skill", "Dark Magic Skill", 0x125, 1, 10),
            _row("drain_aspir", "Drain/Aspir Potency", 0x157, 10, 25),
            _row("ws_damage", "Weaponskill Damage", 0x147, 1, 5),
        ),
    },
    "BST": {
        "item_id": 28625,
        "name": "Pastoralist's Mantle",
        "rows": (
            # One combined word: the client prints "STR+N DEX+N".
            _row("str_dex", "STR/DEX", 0x226, 1, 5),
            _row("accuracy", "Accuracy", 0x017, 1, 5),
            _row("pet_dt", "Pet: Damage Taken", 0x070, -5, -1, multiplier=-1),
            _row("pet_accuracy", "Pet: Accuracy/Ranged Accuracy", 0x06A, 5, 20),
        ),
    },
    "BRD": {
        "item_id": 28626,
        "name": "Rhapsode's Cape",
        "rows": (
            _row("hp", "HP", 0x001, 18, 30),
            _row("macc", "Magic Accuracy", 0x023, 1, 7),
            _row("enmity", "Enmity", 0x028, -10, -1, multiplier=-1),
            _row("dt", "Damage Taken", 0x047, -3, -1, multiplier=-1),
        ),
    },
    "RNG": {
        "item_id": 28627,
        "name": "Lutian Cape",
        "rows": (
            _row("str", "STR", 0x200, 1, 5),
            _row("agi", "AGI", 0x203, 1, 5),
            _row("store_tp", "Store TP", 0x08E, 1, 3),
            _row("snapshot", "Snapshot", 0x0D3, 1, 3),
        ),
    },
    "SAM": {
        "item_id": 28628,
        "name": "Takaha Mantle",
        "rows": (
            _row("str", "STR", 0x200, 1, 5),
            _row("store_tp", "Store TP", 0x08E, 1, 3),
            _row("zanshin", "Zanshin", 0x0C6, 1, 5),
            _row("meditate", "Meditate Duration", 0x4F0, 4, 8),
        ),
    },
    "NIN": {
        "item_id": 28629,
        "name": "Yokaze Mantle",
        "rows": (
            _row("str", "STR", 0x200, 1, 5),
            _row("dex", "DEX", 0x201, 1, 5),
            _row("skillchain", "Skillchain Damage", 0x14C, 1, 5),
            _row("ws_damage", "Weaponskill Damage", 0x147, 1, 5),
        ),
    },
    "DRG": {
        "item_id": 28630,
        "name": "Updraft Mantle",
        "rows": (
            _row("str", "STR", 0x200, 1, 5),
            _row("ws_damage", "Weaponskill Damage", 0x147, 1, 5),
            _row("pet_dt", "Pet: Damage Taken", 0x070, -5, -1, multiplier=-1),
            _row("breath", "Breath", 0x079, 1, 10),
        ),
    },
    "SMN": {
        "item_id": 28631,
        "name": "Conveyance Cape",
        "rows": (
            _row("summoning_skill", "Summoning Magic Skill", 0x126, 1, 5),
            _row("bp_damage", "Blood Pact Damage", 0x171, 1, 5),
            _row("bp_recast", "Blood Pact Recast II", 0x16E, -3, -1, multiplier=-1),
            _row("pet_enmity", "Pet: Enmity", 0x068, 5, 15),
        ),
    },
    "BLU": {
        "item_id": 28632,
        "name": "Cornflower Cape",
        "rows": (
            _row("mp", "MP", 0x009, 15, 30),
            _row("dex", "DEX", 0x201, 1, 5),
            _row("accuracy", "Accuracy", 0x017, 1, 7),
            _row("blue_skill", "Blue Magic Skill", 0x12B, 1, 10),
        ),
    },
    "COR": {
        "item_id": 28633,
        "name": "Gunslinger's Cape",
        "rows": (
            _row("mab", "Magic Atk. Bonus", 0x085, 1, 5),
            _row("enmity", "Enmity", 0x028, -5, -1, multiplier=-1),
            _row("phantom_roll", "Phantom Roll Delay", 0x154, -5, -1, multiplier=-1),
            _row("ws_damage", "Weaponskill Damage", 0x147, 1, 5),
        ),
    },
    "PUP": {
        "item_id": 28634,
        "name": "Dispersal Mantle",
        "rows": (
            _row("str", "STR", 0x200, 1, 5),
            _row("dex", "DEX", 0x201, 1, 5),
            _row("martial_arts", "Martial Arts", 0x097, 10, 20),
            _row("pet_tp_bonus", "Pet: TP Bonus", 0x07A, 100, 500, step=20),
        ),
    },
    "DNC": {
        "item_id": 28635,
        "name": "Toetapper Mantle",
        "rows": (
            _row("store_tp", "Store TP", 0x08E, 1, 5),
            _row("dual_wield", "Dual Wield", 0x092, 1, 5),
            _row("reverse_flourish", "Reverse Flourish", 0x172, 10, 30),
            _row("ws_damage", "Weaponskill Damage", 0x147, 1, 5),
        ),
    },
    "SCH": {
        "item_id": 28636,
        "name": "Bookworm's Cape",
        "rows": (
            _row("int", "INT", 0x204, 1, 5),
            _row("mnd", "MND", 0x205, 1, 5),
            _row("helix_duration", "Helix Duration", 0x4E1, 10, 20),
            _row("regen_potency", "Regen Potency", 0x173, 1, 10),
        ),
    },
    "GEO": {
        "item_id": 28637,
        "name": "Lifestream Cape",
        "rows": (
            _row("geomancy_skill", "Geomancy Skill", 0x12C, 1, 10),
            _row("indi_duration", "Indi Duration", 0x4E2, 10, 20),
            _row("dt", "Damage Taken", 0x047, -5, -1, multiplier=-1),
            _row("pet_dt", "Pet: Damage Taken", 0x070, -5, -1, multiplier=-1),
        ),
    },
    "RUN": {
        "item_id": 28638,
        "name": "Evasionist's Cape",
        "rows": (
            _row("double_attack", "Double Attack", 0x08F, 1, 5),
            _row("enmity", "Enmity", 0x027, 1, 7),
            _row("embolden", "Embolden", 0x174, 5, 15),
            _row("dt", "Damage Taken", 0x047, -5, -1, multiplier=-1),
        ),
    },
}

CAPE_IDS = frozenset(int(entry["item_id"]) for entry in JOBS.values())
CAPE_BY_ID = {int(entry["item_id"]): (job, entry) for job, entry in JOBS.items()}


def entry_for_item(item_id: int) -> tuple[str, dict] | None:
    """The (job, cape table entry) for an item id, or None."""
    return CAPE_BY_ID.get(int(item_id))


def entry_for_name(name: str) -> tuple[str, dict] | None:
    """The (job, cape table entry) whose name appears in *name*, or None."""
    want = str(name or "").casefold()
    for job, entry in JOBS.items():
        if str(entry["name"]).casefold() in want:
            return job, entry
    return None


def row_by_key(cape: dict, key: str) -> dict | None:
    """The named row a cape offers, or None."""
    wanted = str(key or "").strip().lower()
    for row in cape["rows"]:
        if str(row["key"]).lower() == wanted:
            return row
    return None


def row_values(row: dict) -> list[int]:
    """Every signed value the row can print, ascending."""
    step = int(row["step"])
    low = int(row["minimum"])
    high = int(row["maximum"])
    if step <= 0:
        raise ValueError("augment step must be positive")
    out = []
    value = low
    while value <= high:
        out.append(value)
        value += step
    if out and out[-1] != high:
        raise ValueError("%s range is not a multiple of its step" % row["key"])
    return out


def row_slot(row: dict, value) -> tuple[int, int]:
    """The ``(augment id, five-bit value)`` one row value writes."""
    try:
        if isinstance(value, float) and not value.is_integer():
            raise ValueError
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError("augment value must be a whole number") from None
    values = row_values(row)
    if value not in values:
        raise ValueError("%s must be one of %d..%d"
                         % (row["label"], values[0], values[-1]))
    if int(row["multiplier"]) < 0 and value > 0:
        raise ValueError("%s is a reduction" % row["label"])
    if int(row["multiplier"]) > 0 and value < 0:
        raise ValueError("%s is a bonus" % row["label"])
    amount = abs(value)
    step = int(row["step"])
    stored = amount // step - int(row["offset"])
    if not 0 <= stored <= 0x1F:
        raise ValueError("%s=%d does not fit the five-bit field"
                         % (row["key"], value))
    return int(row["id"]), int(stored)


def row_text(row: dict, value) -> str:
    """The client tooltip text one row value stands for."""
    augment_id, stored = row_slot(row, value)
    return capes.slot_text({"id": augment_id, "value": stored})


def selection_for_row(row: dict, slot: dict | None) -> int | None:
    """The value a decoded slot holds for a row, or None when it does not match."""
    if not slot or not int(slot.get("id") or 0):
        return None
    word = (int(slot["id"]), int(slot["value"]))
    for value in row_values(row):
        if row_slot(row, value) == word:
            return int(value)
    return None


def current_slots(extra: bytes | None) -> list[tuple[int, int]]:
    """The four row words plus the unused fifth slot of a standard block."""
    slots = capes.decode(extra)
    if slots is None:
        return [(0, 0)] * 5
    words = [(int(slot["id"]), int(slot["value"])) for slot in slots]
    words.extend([(0, 0)] * (5 - len(words)))
    return words


def merge_choices(cape: dict, choices, current=None) -> list[tuple[int, int]]:
    """Apply a ``{row_key: value | null}`` choice object over a cape block.

    A row that is absent keeps the word already in its slot; an explicit
    ``null`` clears it.  The fifth slot is not part of the BG Wiki table and is
    preserved, so a retail block carrying an unknown fifth word is not truncated
    by an edit of the four known rows.
    """
    if choices is None:
        choices = {}
    if not isinstance(choices, dict):
        raise ValueError("augment choices must be an object")
    words = list(current or ())
    words = [(int(augment_id), int(value)) for augment_id, value in words]
    words.extend([(0, 0)] * (5 - len(words)))
    words = words[:5]
    seen: set[str] = set()
    for raw_key, value in choices.items():
        key = str(raw_key or "").strip().lower()
        row = row_by_key(cape, key)
        if row is None:
            raise ValueError("%s does not offer %r" % (cape["name"], raw_key))
        if key in seen:
            raise ValueError("augment row listed twice: %s" % key)
        seen.add(key)
        index = list(cape["rows"]).index(row)
        if value is None:
            words[index] = (0, 0)
            continue
        words[index] = row_slot(row, value)
    return words


def encode(cape: dict, choices, current=None) -> bytes:
    """A standard block for one subset of a cape's four rows."""
    words = merge_choices(cape, choices, current)
    if not any(int(augment_id) for augment_id, _value in words[:SLOTS]):
        raise ValueError("choose at least one augment")
    return capes._encode_slots(words)


def _public_row(row: dict, index: int) -> dict:
    values = [{"value": value, "text": row_text(row, value)}
              for value in row_values(row)]
    # The strongest value: the most negative for a reduction, the top of the
    # range for a bonus.
    best = values[0] if int(row["maximum"]) < 0 else values[-1]
    return {
        "slot": int(index),
        "key": row["key"],
        "label": row["label"],
        "minimum": int(row["minimum"]),
        "maximum": int(row["maximum"]),
        "step": int(row["step"]),
        "best": int(best["value"]),
        "best_text": str(best["text"]),
        "values": values,
    }


def _inventory_copy(service, character_id: int, container, slot):
    try:
        container = int(container)
        slot = int(slot)
    except (TypeError, ValueError):
        raise ValueError("container and slot must be numbers") from None
    row = next((item for item in service.inventory(int(character_id))
                if int(item["container"]) == container
                and int(item["slot"]) == slot), None)
    if row is None:
        raise LookupError("no item in that container slot")
    found = entry_for_item(int(row["item_id"]))
    if found is None:
        raise ValueError("that item is not a Reive or Incursion job cape")
    return row, found[0], found[1]


def catalog(service, character_id: int) -> dict:
    """The Data page's Reive/Incursion card: every cape and its owned copies."""
    owned: dict[int, list[dict]] = {}
    for item in service.inventory(int(character_id)):
        found = entry_for_item(int(item["item_id"]))
        if found is None:
            continue
        _job, entry = found
        extra = bytes(item.get("extra") or b"")
        words = current_slots(extra)
        selection = {}
        for row in entry["rows"]:
            # Match the row anywhere in the four used slots: retail and the
            # launcher agree on BG Wiki's order, but a hand-built block may not.
            found = None
            for index in range(SLOTS):
                found = selection_for_row(
                    row, {"id": words[index][0], "value": words[index][1]})
                if found is not None:
                    break
            selection[row["key"]] = found
        owned.setdefault(int(item["item_id"]), []).append({
            "container": int(item["container"]),
            "slot": int(item["slot"]),
            "container_name": container_label(int(item["container"])),
            "current": {
                "text": capes.describe(extra) if extra else "not augmented",
                "selection": selection,
                "slots": [
                    {"id": int(word[0]), "value": int(word[1]),
                     "text": capes.slot_text({"id": int(word[0]),
                                              "value": int(word[1])})}
                    for word in words
                ],
            },
        })

    capes_out = []
    for job_number, (job, entry) in enumerate(JOBS.items(), start=1):
        item_id = int(entry["item_id"])
        copies = sorted(owned.get(item_id, []),
                        key=lambda copy: (copy["container"], copy["slot"]))
        capes_out.append({
            "job": job,
            "job_number": job_number,
            "item_id": item_id,
            "name": entry["name"],
            "owned": len(copies),
            "copies": copies,
            "rows": [_public_row(row, index)
                     for index, row in enumerate(entry["rows"])],
        })

    return {
        "source": ("https://www.bg-wiki.com/ffxi/"
                   "Category:JSE_Capes#Reive_and_Incursion_Capes"),
        "note": (
            "Trade a Refractive Crystal and Bayld to Detrovio at the Inventors' "
            "Coalition in Western Adoulin (J-10). A trade rolls several of the "
            "cape's four rows, each at its own random potency, so one cape can "
            "show all four at once. This card writes the rows and values you "
            "pick. Makel-Pakel removes every augment for free, and Clear here "
            "empties the same block."),
        "slots": SLOTS,
        "capes": capes_out,
    }


def apply(service, character_id: int, container, slot, choices) -> dict:
    """Write a chosen subset of a cape's four Detrovio rows."""
    if not isinstance(choices, dict) or not choices:
        raise ValueError("choose at least one augment")
    row, job, entry = _inventory_copy(service, character_id, container, slot)
    words = merge_choices(entry, choices, current_slots(row.get("extra") or b""))
    if not any(int(augment_id) for augment_id, _value in words[:SLOTS]):
        raise ValueError("choose at least one augment")
    block = capes._encode_slots(words)
    if not service.set_item_extra(int(character_id), int(row["container"]),
                                  int(row["slot"]), block):
        raise LookupError("the item row disappeared")
    chosen = {}
    for index, row_entry in enumerate(entry["rows"]):
        if row_entry["key"] in (choices or {}):
            chosen[row_entry["key"]] = choices[row_entry["key"]]
    return {
        "container": int(row["container"]),
        "slot": int(row["slot"]),
        "item_id": int(row["item_id"]),
        "name": entry["name"],
        "job": job,
        "choices": chosen,
        "block": block.hex().upper(),
        "text": capes.describe(block),
    }


def clear(service, character_id: int, container, slot) -> dict:
    """Remove a cape's augment block (Makel-Pakel leaves the same empty state)."""
    row, job, entry = _inventory_copy(service, character_id, container, slot)
    if not service.set_item_extra(int(character_id), int(row["container"]),
                                  int(row["slot"]), b""):
        raise LookupError("the item row disappeared")
    return {
        "container": int(row["container"]),
        "slot": int(row["slot"]),
        "item_id": int(row["item_id"]),
        "name": entry["name"],
        "job": job,
        "block": "",
        "text": "not augmented",
    }
