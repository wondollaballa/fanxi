"""Chemist (CHM): Battle Bag, Chemistry restock and ability calculations.

The job is server-side here: a virtual bag stored in ``char_chemist_bag``, a
content table for the items and recipes, and the rules the zone's ability
handler calls.  The client only sees action packets and chat; the Fanxi HUD
owns the bag presentation.

The first pass deliberately keeps the formulas small and data-driven.  Recipes,
stack caps and potency bands live in SQLite so balance changes do not need a
Python change.  The only hard-coded content is the effect identity (name,
borrowed retail icon and stacking key), because those are protocol semantics.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from . import combat, effects, modifiers as mod, packets, stats

log = logging.getLogger("fanxi.chemist")

CHEMIST_JOB = 23

# Job ability ids.  The client's 0x0AC block has room to 511; these are above the
# retail player table's current end (394) and below the block limit.
TOSS = 395
MIX = 396
CATALYST = 397
AMPLIFY = 398
VOLATILE = 399
ABILITY_IDS = frozenset({TOSS, MIX, CATALYST, AMPLIFY, VOLATILE})
ABILITY_NAMES = {
    TOSS: "Toss",
    MIX: "Mix",
    CATALYST: "Catalyst",
    AMPLIFY: "Amplify",
    VOLATILE: "Volatile Synthesis",
}
RECAST_IDS = {TOSS: 200, MIX: 201, CATALYST: 202, AMPLIFY: 203, VOLATILE: 204}
ABILITY_KEYS = {TOSS: "toss", MIX: "mix", CATALYST: "catalyst",
                AMPLIFY: "amplify", VOLATILE: "volatile"}

# Custom hostile effects.  These are server-side keys, not client status ids.
# The action packet borrows a retail icon so the client plays something sensible.
AQUA_REGIA = 2001
SLUDGE_BOMB = 2002
AETHER_SPORE = 2003
VITRIOL = 2010

# The first item id used for bag-only chemistry items.  They are not real
# char_inventory rows, so the client never needs an item record for them.
CUSTOM_ITEM_BASE = 30000

# A universal consumable reagent: one toolkit replaces a recipe's elemental bill.
# It uses the client-known Alchemy Kit 55 rather than a custom id, so opening the
# inventory or equipment screen cannot meet an item record the client does not have.
TOOLKIT_ITEM_ID = 8899  # Alchemy Kit 55: a client-known stackable reagent

# The client's synthesis pose (LandSandBoat's xi::Animation::Synth).  Mix uses the
# same animation so the ability visibly reads as preparation, and the synthesis
# start/finish packets use it as the result sub-kind.
CRAFT_ANIMATION = 44


@dataclass(frozen=True)
class EffectInfo:
    """Protocol-facing identity for one Chemist effect."""

    name: str
    icon: int
    kind: str = "debuff"


EFFECTS: dict[int, EffectInfo] = {
    AQUA_REGIA: EffectInfo("Aqua Regia", effects.DEFENSE_DOWN),
    SLUDGE_BOMB: EffectInfo("Sludge Bomb", effects.EVASION_DOWN),
    AETHER_SPORE: EffectInfo("Aether Spore", effects.MAGIC_DEF_DOWN),
    VITRIOL: EffectInfo("Vitriol", effects.BIO),
    effects.PETRIFICATION: EffectInfo("Gorgon's Trap", effects.PETRIFICATION, "status"),
    effects.BIND: EffectInfo("Tangle-Vine", effects.BIND, "status"),
}


@dataclass(frozen=True)
class BagSlot:
    slot: int
    item_id: int
    quantity: int
    name: str = ""
    kind: str = ""
    bag_stack: int = 1


def capacity_for_level(level: int) -> int:
    """Base Battle Bag slots by main-job level."""
    level = max(1, min(99, int(level)))
    if level >= 99:
        return 20
    if level >= 75:
        return 15
    if level >= 50:
        return 10
    if level >= 25:
        return 7
    return 5


def capacity(service, character: dict) -> int:
    """Active bag capacity: level bands plus gear (the Empyrean body, later)."""
    base = capacity_for_level(int(character.get("main_level", 1) or 1))
    try:
        mods = service.equipped_mods(int(character["id"]))
        base += max(0, int(mods.get(mod.CHEMISTRY_BAG_SLOTS, 0)))
    except Exception:
        log.debug("bag capacity modifiers unavailable", exc_info=True)
    return max(1, min(26, base))


def alchemy_skill(service, character_id: int) -> int:
    """The Chemist's Alchemy skill (craft id 55), including gear."""
    try:
        craft = service.db.one(
            "SELECT value FROM char_craft WHERE character_id = ? AND skill_id = 55",
            (int(character_id),))
    except Exception:
        craft = None
    value = int(craft["value"]) if craft is not None else 0
    try:
        value += int(service.equipped_mods(int(character_id)).get(mod.ALCHEMY_SKILL, 0))
    except Exception:
        log.debug("Alchemy gear modifiers unavailable", exc_info=True)
    return max(0, min(100, value))


def bag(service, character_id: int) -> list[BagSlot]:
    """Every bag row, including depleted rows (quantity 0).

    A depleted row keeps its item id so the HUD can show the slot and Toss/Mix
    know which recipe to run.  Capacity is checked by callers; the table itself
    allows the full 26 so a level down does not delete anything.
    """
    rows = service.db.all(
        "SELECT b.slot, b.item_id, b.quantity, COALESCE(i.name, 'Item') AS name, "
        "       COALESCE(ci.kind, '') AS kind, COALESCE(ci.bag_stack, 1) AS bag_stack "
        "FROM char_chemist_bag b "
        "LEFT JOIN items i ON i.item_id = b.item_id "
        "LEFT JOIN chemist_items ci ON ci.item_id = b.item_id "
        "WHERE b.character_id = ? ORDER BY b.slot",
        (int(character_id),))
    return [BagSlot(
        slot=int(row["slot"]), item_id=int(row["item_id"]),
        quantity=int(row["quantity"]), name=str(row["name"] or "Item"),
        kind=str(row["kind"] or ""), bag_stack=int(row["bag_stack"] or 1),
    ) for row in rows]


def bag_slot(service, character_id: int, item_id: int) -> BagSlot | None:
    for slot in bag(service, character_id):
        if int(slot.item_id) == int(item_id):
            return slot
    return None


def item_spec(service, item_id: int) -> dict | None:
    """One chemistry item's row, or None when it is not a bag item."""
    try:
        row = service.db.one(
            "SELECT i.item_id, i.name, i.stack AS inventory_stack, ci.* "
            "FROM items i JOIN chemist_items ci ON ci.item_id = i.item_id "
            "WHERE i.item_id = ?", (int(item_id),))
    except Exception:
        log.warning("chemist item lookup failed for %s", item_id, exc_info=True)
        return None
    return dict(row) if row is not None else None


def find_item(service, text: str) -> dict | None:
    """Resolve an item by exact name, case-insensitive prefix, or numeric id."""
    key = str(text or "").strip()
    if not key:
        return None
    if key.isdigit():
        return service.item(int(key))
    row = service.db.one(
        "SELECT * FROM items WHERE lower(name) = lower(?) ORDER BY item_id LIMIT 1",
        (key,))
    if row is None:
        row = service.db.one(
            "SELECT * FROM items WHERE lower(name) LIKE lower(?) ORDER BY item_id LIMIT 1",
            (key + "%",))
    return dict(row) if row is not None else None


def recipe(service, item_id: int) -> dict | None:
    """A custom item's restock recipe, with reagent names and quantities."""
    try:
        row = service.db.one(
            "SELECT r.*, i.name FROM chemist_recipes r "
            "JOIN items i ON i.item_id = r.item_id WHERE r.item_id = ?",
            (int(item_id),))
        if row is None:
            return None
        reagents = service.db.all(
            "SELECT rr.reagent_id, rr.quantity, COALESCE(i.name, 'reagent') AS name "
            "FROM chemist_recipe_reagents rr "
            "LEFT JOIN items i ON i.item_id = rr.reagent_id "
            "WHERE rr.item_id = ? ORDER BY rr.reagent_id",
            (int(item_id),))
    except Exception:
        log.warning("chemist recipe lookup failed for %s", item_id, exc_info=True)
        return None
    result = dict(row)
    result["reagents"] = [dict(reagent) for reagent in reagents]
    return result


def toolkit_count(service, character_id: int) -> int:
    """How many universal Chemistry Toolkits the character carries."""
    return inventory_quantity(service, character_id, TOOLKIT_ITEM_ID)


def learned_recipes(service, character_id: int) -> list[dict]:
    """The recipes this character has learned, in item-name order."""
    rows = service.db.all(
        "SELECT r.item_id, i.name, r.yield, r.cast_ms, r.alchemy_req "
        "FROM char_chemist_recipes cr "
        "JOIN chemist_recipes r ON r.item_id = cr.item_id "
        "JOIN items i ON i.item_id = r.item_id "
        "WHERE cr.character_id = ? ORDER BY i.name",
        (int(character_id),))
    return [dict(row) for row in rows]


def recipe_book(service, character_id: int) -> dict:
    """Everything the HUD needs to draw the Mix recipe picker.

    A recipe is craftable when the character knows it, has the Alchemy requirement,
    and can pay either one Chemistry Toolkit or the elemental reagent bill.
    """
    toolkits = toolkit_count(service, character_id)
    alchemy = alchemy_skill(service, character_id)
    recipes = []
    for row in learned_recipes(service, character_id):
        recipe_row = recipe(service, int(row["item_id"])) or {}
        reagents = []
        missing = []
        for reagent in recipe_row.get("reagents", []):
            have = inventory_quantity(service, character_id, int(reagent["reagent_id"]))
            need = int(reagent["quantity"])
            reagents.append({
                "item_id": int(reagent["reagent_id"]),
                "name": reagent["name"],
                "quantity": need,
                "have": have,
            })
            if toolkits <= 0 and have < need:
                missing.append({"item_id": int(reagent["reagent_id"]),
                                "name": reagent["name"], "need": need, "have": have})
        required = max(int(row.get("alchemy_req") or 0),
                       int(recipe_row.get("alchemy_req") or 0))
        recipes.append({
            "item_id": int(row["item_id"]),
            "name": str(row["name"]),
            "yield": int(row["yield"]),
            "cast_ms": int(row["cast_ms"]),
            "alchemy_req": required,
            "reagents": reagents,
            "missing": missing,
            "toolkits": toolkits,
            "craftable": alchemy >= required and (toolkits > 0 or not missing),
        })
    return {
        "alchemy": alchemy,
        "toolkits": toolkits,
        "toolkit_item_id": TOOLKIT_ITEM_ID,
        "recipes": recipes,
    }


def ensure_bag_slot(service, character: dict, item_id: int) -> dict:
    """Make sure a recipe has a bag row (quantity 0) before its synthesis starts."""
    item_id = int(item_id)
    spec = item_spec(service, item_id)
    if spec is None:
        return {"ok": False, "message": "That item is not a Chemist recipe product."}
    character_id = int(character["id"])
    existing = bag_slot(service, character_id, item_id)
    if existing is not None:
        return {"ok": True, "slot": int(existing.slot), "item_id": item_id}
    active = capacity(service, character)
    used = {int(row.slot) for row in bag(service, character_id) if int(row.slot) <= active}
    slot = next((index for index in range(1, active + 1) if index not in used), None)
    if slot is None:
        return {"ok": False, "message": "The Battle Bag is full."}
    with service.db.transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO char_chemist_bag "
            "(character_id, slot, item_id, quantity) VALUES (?, ?, ?, 0)",
            (character_id, slot, item_id))
    return {"ok": True, "slot": slot, "item_id": item_id}


def _toolkit_available(conn, character_id: int) -> bool:
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS quantity FROM char_inventory "
        "WHERE character_id = ? AND container = 0 AND item_id = ?",
        (int(character_id), TOOLKIT_ITEM_ID)).fetchone()
    return bool(row is not None and int(row["quantity"] or 0) > 0)


def _take_reagents(conn, character_id: int, reagents: list[dict]) -> None:
    """Consume an exact reagent bill inside the caller's transaction."""
    for reagent in reagents:
        item_id = int(reagent["reagent_id"])
        need = int(reagent["quantity"])
        rows = conn.execute(
            "SELECT slot, quantity FROM char_inventory "
            "WHERE character_id = ? AND container = 0 AND item_id = ? ORDER BY slot",
            (int(character_id), item_id)).fetchall()
        have = sum(int(row["quantity"]) for row in rows)
        if have < need:
            raise ValueError("not enough %s" % reagent.get("name", "reagent"))
        left = need
        for row in rows:
            take = min(left, int(row["quantity"]))
            if take <= 0:
                continue
            remaining = int(row["quantity"]) - take
            if remaining:
                conn.execute(
                    "UPDATE char_inventory SET quantity = ? "
                    "WHERE character_id = ? AND container = 0 AND slot = ?",
                    (remaining, int(character_id), int(row["slot"])))
            else:
                conn.execute(
                    "DELETE FROM char_inventory "
                    "WHERE character_id = ? AND container = 0 AND slot = ?",
                    (int(character_id), int(row["slot"])))
            left -= take
            if left <= 0:
                break


def _take_inventory(conn, character_id: int, item_id: int, quantity: int) -> int:
    """Consume up to *quantity* from the normal inventory; return the amount taken."""
    rows = conn.execute(
        "SELECT slot, quantity FROM char_inventory "
        "WHERE character_id = ? AND container = 0 AND item_id = ? ORDER BY slot",
        (int(character_id), int(item_id))).fetchall()
    left = max(0, int(quantity))
    taken = 0
    for row in rows:
        if left <= 0:
            break
        take = min(left, int(row["quantity"]))
        remaining = int(row["quantity"]) - take
        if remaining:
            conn.execute(
                "UPDATE char_inventory SET quantity = ? "
                "WHERE character_id = ? AND container = 0 AND slot = ?",
                (remaining, int(character_id), int(row["slot"])))
        else:
            conn.execute(
                "DELETE FROM char_inventory "
                "WHERE character_id = ? AND container = 0 AND slot = ?",
                (int(character_id), int(row["slot"])))
        left -= take
        taken += take
    return taken


def inventory_quantity(service, character_id: int, item_id: int) -> int:
    row = service.db.one(
        "SELECT COALESCE(SUM(quantity), 0) AS quantity FROM char_inventory "
        "WHERE character_id = ? AND container = 0 AND item_id = ?",
        (int(character_id), int(item_id)))
    return int(row["quantity"] or 0) if row is not None else 0


def missing_reagents(service, character_id: int, item_id: int) -> list[dict]:
    """The reagents still needed for one restock, for a useful refusal message.

    A Chemistry Toolkit pays the whole bill, so its presence means nothing is
    missing even when the elemental crystals are gone.
    """
    recipe_row = recipe(service, item_id)
    if recipe_row is None:
        return []
    if toolkit_count(service, character_id) > 0:
        return []
    missing = []
    for reagent in recipe_row["reagents"]:
        have = inventory_quantity(service, character_id, int(reagent["reagent_id"]))
        need = int(reagent["quantity"])
        if have < need:
            missing.append({"item_id": int(reagent["reagent_id"]),
                            "name": reagent["name"], "need": need, "have": have})
    return missing


def load_item(service, character: dict, item_id: int, quantity: int = 1) -> dict:
    """Move a real item into the virtual Battle Bag.

    Loading is the only way a standard item enters the bag.  Custom chemistry
    items are crafted instead.  The caller gets a result dict rather than an
    exception for the ordinary "you do not have that" cases; database failures
    still raise.
    """
    item_id = int(item_id)
    quantity = max(1, int(quantity))
    character_id = int(character["id"])
    spec = item_spec(service, item_id)
    if spec is None:
        return {"ok": False, "message": "That item cannot go in the Battle Bag."}
    if item_id >= CUSTOM_ITEM_BASE:
        return {"ok": False, "message": "That item has to be synthesized first."}
    alchemy = alchemy_skill(service, character_id)
    required = int(spec.get("alchemy_req") or 0)
    if alchemy < required:
        return {"ok": False, "message": "%s needs Alchemy %d (you have %d)." % (
            spec["name"], required, alchemy)}
    cap = int(spec.get("bag_stack") or 1)
    active = capacity(service, character)
    rows = bag(service, character_id)
    existing = next((row for row in rows if int(row.item_id) == item_id), None)
    if existing is not None and int(existing.slot) > active:
        return {"ok": False, "message": "That bag slot is dormant until your level rises."}
    if existing is not None:
        room = cap - int(existing.quantity)
        slot = int(existing.slot)
    else:
        used = {int(row.slot) for row in rows if int(row.slot) <= active}
        slot = next((index for index in range(1, active + 1) if index not in used), None)
        if slot is None:
            return {"ok": False, "message": "The Battle Bag is full."}
        room = cap
    take = min(quantity, max(0, room), inventory_quantity(service, character_id, item_id))
    if take <= 0:
        if room <= 0:
            return {"ok": False, "message": "%s is already full in the Battle Bag." % spec["name"]}
        return {"ok": False, "message": "You do not have %s." % spec["name"]}

    with service.db.transaction() as conn:
        taken = _take_inventory(conn, character_id, item_id, take)
        if taken <= 0:
            raise ValueError("inventory changed during load")
        conn.execute(
            "INSERT INTO char_chemist_bag (character_id, slot, item_id, quantity) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(character_id, item_id) "
            "DO UPDATE SET quantity = char_chemist_bag.quantity + excluded.quantity",
            (character_id, slot, item_id, taken))
    return {"ok": True, "item_id": item_id, "name": spec["name"],
            "quantity": taken, "slot": slot, "message": "Loaded %d %s." % (taken, spec["name"])}


def consume_slot(service, character_id: int, item_id: int) -> dict | None:
    """Take one charge from a bag slot; return the new state, or None when empty."""
    with service.db.transaction() as conn:
        row = conn.execute(
            "SELECT slot, quantity FROM char_chemist_bag "
            "WHERE character_id = ? AND item_id = ?", (int(character_id), int(item_id))).fetchone()
        if row is None or int(row["quantity"]) <= 0:
            return None
        left = int(row["quantity"]) - 1
        conn.execute(
            "UPDATE char_chemist_bag SET quantity = ? "
            "WHERE character_id = ? AND item_id = ?",
            (left, int(character_id), int(item_id)))
        return {"slot": int(row["slot"]), "item_id": int(item_id), "quantity": left}


def craft(service, character_id: int, item_id: int) -> dict:
    """Consume a recipe's reagents and refill one depleted slot.

    Reagents are checked and consumed in the same transaction as the bag update,
    so a partial craft cannot exist.  The slot must be empty: Chemistry is the
    restock action, not a way to top up a partially used stack.
    """
    recipe_row = recipe(service, item_id)
    spec = item_spec(service, item_id)
    if recipe_row is None or spec is None:
        return {"ok": False, "message": "There is no synthesis recipe for that item."}
    alchemy = alchemy_skill(service, character_id)
    required = max(int(recipe_row.get("alchemy_req") or 0),
                   int(spec.get("alchemy_req") or 0))
    if alchemy < required:
        return {"ok": False, "message": "That synthesis needs Alchemy %d (you have %d)." % (
            required, alchemy)}
    with service.db.transaction() as conn:
        row = conn.execute(
            "SELECT quantity FROM char_chemist_bag WHERE character_id = ? AND item_id = ?",
            (int(character_id), int(item_id))).fetchone()
        if row is None:
            raise ValueError("the bag slot disappeared")
        if int(row["quantity"]) > 0:
            return {"ok": False, "message": "That bag slot is not empty."}
        toolkit_used = _toolkit_available(conn, character_id)
        if toolkit_used:
            taken = _take_inventory(conn, character_id, TOOLKIT_ITEM_ID, 1)
            if taken < 1:
                toolkit_used = False
        if not toolkit_used:
            try:
                _take_reagents(conn, character_id, recipe_row["reagents"])
            except ValueError as exc:
                return {"ok": False, "message": "You are missing a reagent: %s." % exc}
        yield_value = max(1, min(int(spec.get("bag_stack") or 1),
                                 int(recipe_row.get("yield") or 1)))
        conn.execute(
            "UPDATE char_chemist_bag SET quantity = ? "
            "WHERE character_id = ? AND item_id = ?",
            (yield_value, int(character_id), int(item_id)))
    return {"ok": True, "item_id": int(item_id), "name": spec["name"],
            "quantity": yield_value, "toolkit_used": bool(toolkit_used),
            "message": "Synthesized %d %s%s." % (
                yield_value, spec["name"],
                " with a Chemistry Toolkit" if toolkit_used else "")}


def craft_cast_ms(service, character_id: int, item_id: int) -> int:
    """Synthesis cast time after the ultimate shield's flat reduction."""
    recipe_row = recipe(service, item_id)
    base = int(recipe_row.get("cast_ms") or 12000) if recipe_row else 12000
    try:
        reduction = int(service.equipped_mods(int(character_id)).get(mod.CHEMISTRY_CAST, 0))
    except Exception:
        reduction = 0
    # CHEMISTRY_CAST is a signed millisecond adjustment (the shield is -10000).
    return max(1000, base + min(0, reduction))


def scale(base: int, cap: int, alchemy: int) -> int:
    """Linear Alchemy scaling from a base to a cap, rounded down."""
    base, cap = int(base), int(cap)
    if cap <= 0:
        cap = base
    alchemy = max(0, min(100, int(alchemy)))
    if cap <= base:
        return max(0, base)
    return max(0, base + (cap - base) * alchemy // 100)


def item_values(spec: dict, alchemy: int, *, volatile: bool = False,
                potency_bonus: int = 0) -> dict:
    """The potency/tick/duration one use of an item resolves with.

    ``potency_bonus`` is ``CHEMISTRY_POTENCY`` in hundredths of a percent.  It is
    applied after the Alchemy curve so relic armor can push past the native cap;
    a tick gets the same percentage applied to its damage.
    """
    potency = scale(spec.get("potency_base", 0), spec.get("potency_cap", 0), alchemy)
    power = scale(spec.get("power_base", 0), spec.get("power_cap", 0), alchemy)
    tick = scale(spec.get("tick_base", 0), spec.get("tick_cap", 0), alchemy)
    bonus = max(0, int(potency_bonus))
    if bonus:
        potency += bonus // 100
        power += bonus // 100
        tick += tick * bonus // 10000
    if volatile:
        potency = max(potency, int(spec.get("potency_cap") or spec.get("potency_base") or 0))
        power = max(power, int(spec.get("power_cap") or spec.get("power_base") or 0))
        tick = max(tick, int(spec.get("tick_cap") or spec.get("tick_base") or 0))
        if bonus:
            potency += bonus // 100
            power += bonus // 100
            tick += tick * bonus // 10000
    return {
        "potency": potency,
        "power": power,
        "tick": tick,
        "duration": max(0.0, float(spec.get("duration") or 0.0)),
        "tick_interval": max(0.1, float(spec.get("tick_interval") or 3.0)),
        "tier": int(spec.get("tier") or 0),
    }


def toss_accuracy(session, target) -> float:
    """Physical ranged hit chance for one Toss.

    Throwing skill is the weapon skill; R.Accuracy, DEX and the target's
    (debuffed) Evasion follow the normal ranged formula.  Magic Evasion is not
    part of the roll.
    """
    try:
        sheet = session.stat_sheet()
        caps, _base = session.effective_skills()
        throwing = int(caps.get(27, 0))
        accuracy = stats.ranged_accuracy(
            session.combat_mods(), int(sheet.attributes.get("dex", 0)), throwing)
        enemy = session.world.debuffed_monster(target)
        rate = combat.hit_rate(
            accuracy=accuracy, evasion=int(enemy.evasion),
            attacker_level=int(sheet.fighter.level), target_level=int(enemy.level),
            is_pc=True, corrected=combat.level_corrected(int(session.zone)))
    except Exception as exc:
        log.warning("%s Toss accuracy unavailable: %s", session.addr, exc)
        return 0.95
    return max(0.05, min(0.99, float(rate)))


def apply_hostile(session, target, spec: dict, *, volatile: bool = False,
                  now: float | None = None) -> dict:
    """Apply one hostile chemistry item.  The caller has already rolled the hit."""
    effect_id = int(spec.get("effect_key") or 0)
    info = EFFECTS.get(effect_id)
    if info is None:
        return {"ok": False, "message": "That item has no effect."}
    now = time.time() if now is None else float(now)
    service = session.world.service
    character_id = int(session.char["id"])
    try:
        potency_bonus = int(service.equipped_mods(character_id).get(
            mod.CHEMISTRY_POTENCY, 0))
    except Exception:
        potency_bonus = 0
    values = item_values(spec, alchemy_skill(service, character_id),
                         volatile=volatile, potency_bonus=potency_bonus)
    effect = effects.SpellEffect(
        effect_id, "debuff", values["duration"], power=values["power"],
        potency=values["potency"], tick=values["tick"], icon=info.icon)
    applied = session.world.apply_mob_effect(
        target, effect, session, now, duration=values["duration"],
        potency=values["potency"], tick=values["tick"],
        tick_interval=values["tick_interval"], tier=values["tier"],
        name=info.name)
    if not applied:
        return {"ok": False, "message": "%s has no effect." % info.name}
    return {"ok": True, "name": info.name, "effect_id": effect_id,
            "icon": info.icon, "values": values,
            "message": "%s: %s." % (info.name, _effect_summary(info, values))}


def _effect_summary(info: EffectInfo, values: dict) -> str:
    if values["tick"]:
        return "%d damage every %gs for %gs" % (
            values["tick"], values["tick_interval"], values["duration"])
    if info.name == "Aether Spore":
        return "Magic Defense -%d, Magic Evasion -%d for %gs" % (
            values["potency"], values["power"], values["duration"])
    if values["potency"]:
        return "potency %d for %gs" % (values["potency"], values["duration"])
    return "%gs" % values["duration"]


def apply_mix(session, target, spec: dict) -> dict:
    """Apply one friendly chemistry item.  Returns ok=False before any spend."""
    kind = str(spec.get("kind") or "")
    alchemy = alchemy_skill(session.world.service, int(session.char["id"]))
    if kind == "heal":
        amount = max(0, int(spec.get("amount") or 0)
                     + int(spec.get("alchemy_scale") or 0) * alchemy)
        current = int(target.char.get("hp_current", 0))
        maximum = max(1, int(target.char.get("hp", 1) or 1))
        healed = min(amount, max(0, maximum - current))
        if healed <= 0:
            return {"ok": False, "message": "The target is already at full health."}
        target.char["hp_current"] = current + healed
        target.queue += [target.char_status(), target.char_update(packets.SEND_HP),
                         target.party_member()]
        try:
            target.world.broadcast_player(target, packets.SEND_HP)
        except Exception:
            log.debug("player HP refresh failed", exc_info=True)
        _save_vitals(session, target)
        return {"ok": True, "kind": "heal", "amount": healed,
                "message": "%s recovers %d HP." % (
                    target.char.get("name", "The target"), healed)}
    if kind == "mp":
        amount = max(0, int(spec.get("amount") or 0)
                     + int(spec.get("alchemy_scale") or 0) * alchemy)
        current = int(target.char.get("mp_current", 0))
        maximum = max(0, int(target.char.get("mp", 0) or 0))
        restored = min(amount, max(0, maximum - current))
        if restored <= 0:
            return {"ok": False, "message": "The target already has full MP."}
        target.char["mp_current"] = current + restored
        target.queue += [target.char_status(), target.char_update(packets.SEND_HP),
                         target.party_member()]
        try:
            target.world.broadcast_player(target, packets.SEND_HP)
        except Exception:
            log.debug("player MP refresh failed", exc_info=True)
        _save_vitals(session, target)
        return {"ok": True, "kind": "mp", "amount": restored,
                "message": "%s recovers %d MP." % (
                    target.char.get("name", "The target"), restored)}
    if kind == "status":
        wanted = _status_ids(spec.get("statuses") or "")
        removed = []
        for effect_id in wanted:
            if target.remove_effect(int(effect_id)):
                removed.append(int(effect_id))
        if not removed:
            return {"ok": False, "message": "There is no matching status to remove."}
        target.queue.append(target.char_status())
        return {"ok": True, "kind": "status", "removed": removed,
                "message": "Removed %d status effect%s." % (
                    len(removed), "" if len(removed) == 1 else "s")}
    return {"ok": False, "message": "That item cannot be mixed."}


def apply_mix_entity(session, target, spec: dict) -> dict:
    """Apply a friendly item to a Trust/alter ego entity rather than a player."""
    kind = str(spec.get("kind") or "")
    alchemy = alchemy_skill(session.world.service, int(session.char["id"]))
    name = str(getattr(target, "name", "The target"))
    if kind == "heal":
        amount = max(0, int(spec.get("amount") or 0)
                     + int(spec.get("alchemy_scale") or 0) * alchemy)
        current = int(getattr(target, "hp", 0) or 0)
        maximum = max(1, int(getattr(target, "hp_max", 1) or 1))
        healed = min(amount, max(0, maximum - current))
        if healed <= 0:
            return {"ok": False, "message": "%s is already at full health." % name}
        target.hp = current + healed
        try:
            session.world._queue_mob_hp(target)
        except Exception:
            log.debug("trust HP refresh failed", exc_info=True)
        return {"ok": True, "kind": "heal", "amount": healed,
                "message": "%s recovers %d HP." % (name, healed)}
    if kind == "mp":
        amount = max(0, int(spec.get("amount") or 0)
                     + int(spec.get("alchemy_scale") or 0) * alchemy)
        current = int(getattr(target, "mp", 0) or 0)
        maximum = max(0, int(getattr(target, "mp_max", 0) or 0))
        restored = min(amount, max(0, maximum - current))
        if restored <= 0:
            return {"ok": False, "message": "%s already has full MP." % name}
        target.mp = current + restored
        try:
            session.world._queue_mob_hp(target)
        except Exception:
            log.debug("trust MP refresh failed", exc_info=True)
        return {"ok": True, "kind": "mp", "amount": restored,
                "message": "%s recovers %d MP." % (name, restored)}
    if kind == "status":
        removed = []
        for effect_id in _status_ids(spec.get("statuses") or ""):
            if int(effect_id) in getattr(target, "effect_state", {}):
                target.effect_state.pop(int(effect_id), None)
                try:
                    target.status_effects.remove(int(effect_id))
                except (AttributeError, ValueError):
                    pass
                removed.append(int(effect_id))
        if not removed:
            return {"ok": False, "message": "%s has no matching status." % name}
        return {"ok": True, "kind": "status", "removed": removed,
                "message": "Removed %d status effect%s from %s." % (
                    len(removed), "" if len(removed) == 1 else "s", name)}
    return {"ok": False, "message": "That item cannot be mixed."}


def apply_friendly(session, target, spec: dict) -> dict:
    """Dispatch a friendly item to a player session or a Trust entity."""
    if hasattr(target, "char"):
        return apply_mix(session, target, spec)
    return apply_mix_entity(session, target, spec)


def target_id(target) -> int:
    """The action-result id for a player session or world entity."""
    if hasattr(target, "char"):
        return int(target.char["char_id"])
    return int(getattr(target, "id", 0))


def target_name(target) -> str:
    if hasattr(target, "char"):
        return str(target.char.get("name", "Target"))
    return str(getattr(target, "name", "Target"))


def target_pos(target) -> tuple[float, float, float]:
    if hasattr(target, "pos"):
        return tuple(float(value) for value in target.pos[:3])
    return (float(getattr(target, "x", 0.0)), float(getattr(target, "y", 0.0)),
            float(getattr(target, "z", 0.0)))


def _status_ids(raw) -> list[int]:
    if isinstance(raw, (list, tuple)):
        values = raw
    else:
        values = str(raw or "").replace(";", ",").split(",")
    out = []
    for value in values:
        try:
            effect_id = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if effect_id > 0:
            out.append(effect_id)
    return out


def _save_vitals(session, target) -> None:
    try:
        session.world.service.save_vitals(
            int(target.char["id"]), int(target.char.get("hp_current", 0)),
            int(target.char.get("mp_current", 0)))
    except Exception as exc:
        log.warning("%s Chemist vitals save failed: %s", session.addr, exc)


def choose_bag_item(session, hostile: bool) -> tuple[BagSlot | None, dict | None]:
    """Pick the selected bag item, or the first matching one.

    Toss/Mix carry no item id in the client's action packet.  The HUD (or
    ``//chm select``) sets ``session.chemist_selected_item``; without a selection
    the first matching slot is used.  A depleted slot is still returned so the
    ability starts Chemistry instead of silently doing nothing.
    """
    service = session.world.service
    rows = bag(service, int(session.char["id"]))
    if not rows:
        return None, None
    selected = int(getattr(session, "chemist_selected_item", 0) or 0)
    wanted = []
    if selected:
        wanted = [row for row in rows if int(row.item_id) == selected]
    wanted += [row for row in rows if int(row.item_id) != selected]
    for row in wanted:
        spec = item_spec(service, int(row.item_id))
        if spec is None:
            continue
        is_hostile = str(spec.get("kind") or "") == "hostile"
        if is_hostile == bool(hostile):
            return row, spec
    return None, None


def stances(session) -> dict:
    """The three one-shot Chemist windows, for the HUD and status lines."""
    now = time.time()
    return {
        "catalyst": max(0.0, float(getattr(session, "_chemist_catalyst_until", 0.0)) - now),
        "amplify": max(0.0, float(getattr(session, "_chemist_amplify_until", 0.0)) - now),
        "volatile": max(0.0, float(getattr(session, "_chemist_volatile_until", 0.0)) - now),
    }


def clear_stances(session) -> None:
    session._chemist_catalyst_until = 0.0
    session._chemist_amplify_until = 0.0
    session._chemist_volatile_until = 0.0


_ROMAN = {"I": "II", "II": "III", "III": "IV", "IV": "V"}
_TIER_RE = re.compile(r"^(.*?)(?:\s+)(I|II|III|IV)$")


def upgrade_spell(service, spell: dict) -> dict | None:
    """The next tier of a tiered spell, for Amplify.  None when there is none."""
    name = str(spell.get("name") or "").strip()
    match = _TIER_RE.match(name)
    if match is None:
        return None
    base, tier = match.group(1), match.group(2)
    next_tier = _ROMAN.get(tier)
    if not next_tier:
        return None
    upgraded = service.spell_by_name("%s %s" % (base, next_tier))
    if upgraded is None or int(upgraded["id"]) == int(spell["id"]):
        return None
    return upgraded


def amplified_spell(original: dict, upgraded: dict) -> dict:
    """Use the higher tier's numbers but keep the cast the client actually made.

    ``id``/``animation`` drive the client action; ``mp`` and ``cast_time`` are
    the lower tier's cost.  Everything the effect engine reads (name, base,
    multiplier, skill, targets, element) comes from the higher tier.
    """
    result = dict(upgraded)
    for key in ("id", "mp", "cast_time", "animation"):
        if key in original:
            result[key] = original[key]
    return result


def spell_upgrade_name(service, spell: dict) -> str | None:
    upgraded = upgrade_spell(service, spell)
    return str(upgraded["name"]) if upgraded is not None else None


def craft_reagent_summary(service, item_id: int) -> str:
    recipe_row = recipe(service, item_id)
    if recipe_row is None:
        return ""
    return ", ".join("%s x%d" % (reagent["name"], int(reagent["quantity"]))
                     for reagent in recipe_row["reagents"])


def synthesis_packet_values(item_id: int) -> tuple[int, int]:
    """(action id, animation) for a synthesis action.

    The client has no spell record for a synthetic synthesis, so use the
    synthesis pose; the HUD reads the real progress from the server state.
    """
    return int(item_id), CRAFT_ANIMATION


def is_chemist(session) -> bool:
    return int(session.char.get("main_job") or 0) == CHEMIST_JOB


def cast_radius(session) -> float:
    """Catalyst radius; relic armor can raise this later."""
    base = 10.0
    try:
        mods = session.world.service.equipped_mods(int(session.char["id"]))
        base += max(0.0, float(mods.get(mod.CHEMISTRY_RADIUS, 0)))
    except Exception:
        pass
    return base
