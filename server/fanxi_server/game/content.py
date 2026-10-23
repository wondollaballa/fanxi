"""Fanxi's small content layer: what an NPC says and how a quest advances.

This is the clean-room equivalent of a scripted content system: the database stores where an NPC
stands and which script it uses, while the behaviour lives in ordinary Python functions here.
It is intentionally tiny — three city NPCs and one hunt quest — but the shape is the same one a
larger world grows into.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("fanxi.content")

GUIDE_QUEST = "pest_control"

# What an NPC with no shop or script of its own says.  Never a placeholder.
GENERIC_LINES = (
    "Good day, adventurer.",
    "Welcome to {zone}.",
    "The roads are dangerous. Stay sharp.",
    "If you need supplies, look for a merchant.",
    "May the crystal guide you.",
)


def _shop_line(entity, count: int) -> str:
    return "Have a look at what I have for sale."


def _say(session, entity, text: str) -> None:
    session.say_from(entity.name, text)


def npc_talk(session, entity) -> None:
    service = session.world.service
    character = session.char
    script = str(entity.script or "")

    # Home Point crystals: open the client's own "Set Home Point / Teleport" menu.
    # Scripts are named HomePoint#N (a few old rows use Home_Point_#N), and the
    # client's event for crystal N is 8700 + N - 1.
    if script.replace("_", "").startswith("HomePoint"):
        # The menu is built from the Home Points this character has registered; the
        # "new home point" announcement is only sent the first time an index is added.
        # Index 0 (Southern San d'Oria #1 and several other zones) is a real index, so
        # only a missing/negative value may take the old no-menu fallback.
        raw_index = getattr(entity, "hp_index", None)
        index = -1 if raw_index is None else int(raw_index)
        if index < 0:
            x, y, z, rot = session.pos
            service.set_home(int(character["id"]), int(session.zone), x, y, z, rot)
            _say(session, entity, "Your home point has been set here.")
            return
        number = 1
        match = re.search(r"#(\d+)", script) or re.search(r"#(\d+)", str(entity.name))
        if match:
            number = int(match.group(1))
        is_new = service.register_home_point(int(character["id"]), index)
        registered = service.home_point_indexes(int(character["id"]))
        access = [0, 0, 0, 0]
        for hp in registered:
            if 0 <= hp < 128:
                access[hp // 32] |= 1 << (hp % 32)
        params = [1, access[0], access[1], access[2], access[3],
                  int(character.get("gil", 0)) & 0xFFFFFFFF, 4095,
                  (index & 0xFF) | ((1 if is_new else 0) << 16)]
        session.start_event(entity, 8700 + max(0, number - 1), params)
        return

    # Survival Guides: event 8500 is the client's own guide teleport menu.
    if script in ("Survival_Guide", "SurvivalGuide"):
        guides = service.survival_guides()
        current = next((g for g in guides if int(g["zone"]) == int(session.zone)), None)
        table_index = int(current["idx"]) if current is not None else 0
        # The client binds this menu to its own Survival Guide entity (0x010EA165 in
        # zone 234).  Our NPC must sit on that same targid or the client rejects the
        # event outright.  Event ids come from the retail event table: 8500/8501.
        param = (table_index & 0xFF) | 0x4000
        params = [0, param, int(character.get("gil", 0)) & 0xFFFFFFFF,
                  0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 2079]
        session.start_event(entity, 8500, params)
        return

    # Hunt Registry: event 1500 with the zone's hunt menu table.
    if script == "Hunt_Registry":
        menu = service.hunt_menu(int(session.zone), 1)
        if menu is not None:
            session.start_event(entity, 1500, [0, menu & 0xFFFFFFFF])
            return

    # The Mog House Moogle: its own menu, drawn by the client (change job, delivery box,
    # furnishings, exit).  The job pick comes back on the 0x0100 packet.
    if script.lower() in ("moogle", "moghouse_moogle"):
        session.open_mog_menu()
        return

    # Merchant NPCs: real stock parsed from the zone scripts.
    stock = service.npc_shop(int(session.zone), script)
    if stock:
        _say(session, entity, _shop_line(entity, len(stock)))
        session.open_shop(script, stock)
        return

    # Real dialogue: the client renders the NPC's own event text for (zone, event id),
    # so replaying the event id from LandSandBoat's scripts shows the retail lines.
    mapped = service.npc_event(int(session.zone), script)
    if mapped is None and script != entity.name:
        mapped = service.npc_event(int(session.zone), entity.name)
    if mapped is not None:
        event_id, params = mapped
        session.start_event(entity, event_id, params)
        return

    # Objects, signs and NPCs that only print a zone text: the client resolves the id
    # from its own data, so the wording is the retail one.
    message = service.npc_message(int(session.zone), script)
    if message is None and script != entity.name:
        message = service.npc_message(int(session.zone), entity.name)
    if message is not None:
        text_id, params = message
        session.talk_message(entity, text_id, params)
        return

    airship = {"airship_san": 223, "airship_kaz": 226,
               "airship_bas": 225, "airship_win": 224}.get(script)
    if airship is not None:
        _say(session, entity, "The airship is boarding.")
        session.change_zone(airship, [0.0, 0.0, 0.0, 0])
        return
    if entity.script == "zone_lower":
        session.change_zone(245)
        return
    if entity.script == "exit_west":
        _say(session, entity, "The gate swings open toward West Ronfaure.")
        session.change_zone(100)
        return
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

    if entity.script == "stablehand":
        _say(session, entity, "Chocobos are resting today. The west gate is still open.")
        return

    if entity.dialogue:
        line = entity.dialogue[entity.dialogue_index % len(entity.dialogue)]
        entity.dialogue_index += 1
        _say(session, entity, line)
        return
    zone_name = session.world.zones.name(session.zone)
    line = GENERIC_LINES[entity.dialogue_index % len(GENERIC_LINES)]
    entity.dialogue_index += 1
    _say(session, entity, line.format(zone=zone_name))


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
