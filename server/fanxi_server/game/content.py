"""Fanxi's small content layer: what an NPC says and how a quest advances.

This is the clean-room equivalent of a scripted content system: the database stores where an NPC
stands and which script it uses, while the behaviour lives in ordinary Python functions here.
It is intentionally tiny — three city NPCs and one hunt quest — but the shape is the same one a
larger world grows into.
"""
from __future__ import annotations

import logging

log = logging.getLogger("fanxi.content")

GUIDE_QUEST = "pest_control"

# Fanxi's own shop stock. Prices are in gil; item ids are client item ids.
SHOPS = {
    "moogle": [
        {"item_id": 4112, "price": 50},    # Potion
        {"item_id": 16534, "price": 500},  # Onion Sword
        {"item_id": 16535, "price": 800},  # Bronze Sword
    ],
}


def _say(session, entity, text: str) -> None:
    session.say_from(entity.name, text)


def npc_talk(session, entity) -> None:
    service = session.world.service
    character = session.char
    if entity.script == "guide":
        quest = service.quest_by_key(GUIDE_QUEST)
        if quest is None:
            _say(session, entity, "The Fanxi Guide has nothing to say yet.")
            return
        state = service.quest_state(character["id"], quest["id"])
        if state is None:
            service.start_quest(character["id"], quest["id"])
            _say(session, entity, "You look capable. Orcish Grunts are troubling the west road.")
            _say(session, entity, "Go to West Ronfaure with !zone 100 and defeat three of them. Return to me after.")
            session.say("Quest started: %s." % quest["name"])
            return
        if state.get("state") == "complete":
            _say(session, entity, "The road is safer thanks to you. Safe travels, adventurer.")
            return
        progress = int(state.get("progress", 0))
        required = int(quest["required_kills"])
        if progress < required:
            _say(session, entity, "You have defeated %d of %d Orcish Grunts. Keep at it." % (progress, required))
            return
        service.complete_quest(character["id"], quest["id"])
        _say(session, entity, "You did it. Take this for your trouble.")
        session.say("Quest complete: %s." % quest["name"])
        session.refresh_character()
        session.refresh_inventory()
        return

    if entity.script == "moogle":
        _say(session, entity, "Kupo! Potions and starter blades, cheap for a new adventurer.")
        session.open_shop("moogle", SHOPS["moogle"])
        return
    if entity.script == "stablehand":
        _say(session, entity, "Chocobos are resting today. The west gate is still open.")
        return

    lines = entity.dialogue or ["..."]
    _say(session, entity, lines[entity.dialogue_index % len(lines)])
    entity.dialogue_index += 1


def mob_killed(session, entity) -> None:
    """Called after a mob dies, before its respawn timer starts."""
    service = session.world.service
    quest = service.quest_for_template(entity.template_id)
    if quest is None:
        return
    state = service.quest_state(session.char["id"], quest["id"])
    if not state or state.get("state") != "active":
        return
    updated = service.advance_quest(session.char["id"], quest["id"], 1)
    progress, required = int(updated.get("progress", 0)), int(quest["required_kills"])
    session.say("Quest: %s (%d/%d)." % (quest["name"], min(progress, required), required))
    if progress >= required:
        session.say("Return to the Fanxi Guide in Port Jeuno to claim your reward.")
