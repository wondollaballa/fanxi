#!/usr/bin/env python3
"""Smoke-test every job ability in a live session and say what it actually changed.

This is a breadth-first companion to the retail deep dives.  It does not know every
ability's correct target or prerequisite, so a "no-op" is a lead, not a verdict: the
per-job test replaces it with an exact assertion.  It catches the abilities that only
play the animation, a big class the static audit cannot see.
"""
from __future__ import annotations

import argparse
import sqlite3
import struct
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "tests"))

from support import make_service  # noqa: E402
from fanxi_server.game import packets  # noqa: E402
from fanxi_server.game.world import World  # noqa: E402
from fanxi_server.game.zone import ZoneSession  # noqa: E402

# Abilities that are menu/resource entries with no standalone effect.  They are not
# failures; the client opens a roll/pet/stratagem menu and sends a real action later.
MENU_ABILITIES = {55, 97, 124, 223, 382}

EXCLUDE = {
    "queue", "char", "world", "service", "config", "db", "entities", "trust_entities",
    "effect_state", "status_effects", "ability_recasts", "pet_entity", "sockets",
    "_last_target_hp", "engaged_targid",
}


def chats(session) -> list[str]:
    out = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        out.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return out


def simple(session) -> dict:
    out = {}
    for key, value in session.__dict__.items():
        if key in EXCLUDE:
            continue
        if isinstance(value, (int, float, str, bool, type(None))):
            out[key] = value
    # Timers and cast state are dicts, so they do not fit the scalar map above.
    for key in ("meditate", "third_eye", "casting"):
        out[key] = repr(session.__dict__.get(key))
    # HP/MP/TP live in the char dict, which is excluded wholesale from the map.
    for key in ("hp_current", "mp_current", "tp"):
        out[key] = int(session.char.get(key, 0))
    return out


def effect_set(session) -> set[int]:
    return {int(key) for key in session.effect_state}


def pet_state(session):
    pet = getattr(session, "pet_entity", None)
    if pet is None:
        return None
    return (int(pet.id), int(pet.hp), str(getattr(pet, "pet_state", "")),
            int(getattr(pet, "damage_mult", 100)),
            int(getattr(pet, "burden", 0)),
            int(getattr(pet, "tp", 0)),
            {int(k) for k in getattr(pet, "effect_state", {})})


def target_state(target):
    return (int(target.hp), int(target.hp_max),
            {int(k) for k in getattr(target, "effect_state", {})},
            int(target.engaged_char_id or 0),
            tuple(sorted((int(k), int(v)) for k, v in target.enmity.items())),
            int(getattr(target, "animation", 0)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "fanxi.db"))
    parser.add_argument("--out", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--job", type=int, default=0)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        config, db, service = make_service(Path(tmp))
        account = service.register("smoke", "password123").account
        character = service.create_character(account["id"], {"name": "Smoke", "race": 1})
        world = World(config, service, None)
        all_rows = sqlite3.connect(args.db)
        all_rows.row_factory = sqlite3.Row
        query = "SELECT id,name,job,level FROM job_abilities"
        params = ()
        if args.job:
            query += " WHERE job=?"
            params = (int(args.job),)
        query += " ORDER BY job,level,id"
        rows = all_rows.execute(query, params).fetchall()
        if args.limit:
            rows = rows[:args.limit]

        results = []
        for index, row in enumerate(rows):
            ability_id = int(row["id"])
            name = str(row["name"])
            job = int(row["job"])

            def one_pass(with_pet: bool):
                record = service.character_record(service.character(character["id"]), "Smoke")
                record["main_job"] = job
                record["main_level"] = 99
                record["jobs"] = {job: (99, 0)}
                session = ZoneSession(world, None, record)
                session.set_key(bytes(20))
                session.logged_in = True
                world.sessions = {("127.0.0.1", 40000 + index): session}
                session.zone = 100
                session.pos = [0.0, 0.0, 0.0, 0]
                session.load_zone_entities()
                session.after_zone_in()
                session.queue.clear()
                session.zone_loaded = True
                # Give the ability something to act on: a damaged caster, a half-empty
                # MP pool, a damaged pet and a claimed monster.  Without this, heals,
                # Convert, Repair and Spirit Link all look like no-ops at full HP.
                session.char["hp_current"] = max(1, int(session.char["hp"]) * 2 // 5)
                session.char["mp_current"] = max(0, int(session.char.get("mp", 0)) * 7 // 10)
                session.char["tp"] = 3000
                session.add_effect(3, duration=60, tick=3)      # Poison, for cures
                session.effect_state.clear()
                session.status_effects.clear()
                session.ability_recasts.clear()
                session.char["main_job"] = job
                session.char["main_level"] = 99
                session.char["jobs"] = {job: (99, 0)}
                session.tamed_mob_id = 0
                mob = next((e for e in session.entities if e.kind == "mob" and e.alive), None)
                if mob is None:
                    return "error", "", "no mob"
                # A previous pass may have killed or debuffed the shared mob.
                mob.alive = True
                mob.hp = int(mob.hp_max)
                mob.effect_state.clear()
                mob.status_effects.clear()
                mob.enmity = {int(session.char["char_id"]): 1000}
                mob.enmity_ve = {}
                mob.engaged_char_id = int(session.char["char_id"])
                mob.claim_char_id = int(session.char["char_id"])
                mob.aggro_announced = False
                mob.animation = 0
                session.pos = [mob.x, mob.y, mob.z, 0]
                session.engaged_id = int(mob.id)
                pet = None
                if with_pet:
                    pet_key = {9: "beast", 14: "wyvern", 15: "ifrit",
                               18: "automaton", 21: "luopan"}.get(job, "wyvern")
                    pet = world.spawn_pet(session, pet_key, time.time())
                    if pet is not None:
                        pet.hp = max(1, int(pet.hp) // 2)
                        if job == 18:
                            pet.burden = 10
                before = (
                    simple(session), effect_set(session), pet_state(session),
                    target_state(mob), chats(session),
                )
                packet = bytearray(16)
                struct.pack_into("<IHH", packet, 0, int(session.char["char_id"]), 0,
                                 packets.ACTION_JOBABILITY)
                struct.pack_into("<I", packet, 12, ability_id)
                err = ""
                try:
                    session.job_ability(bytes(packet), int(mob.targid))
                except Exception as exc:
                    err = "%s: %s" % (type(exc).__name__, exc)
                after = (
                    simple(session), effect_set(session), pet_state(session),
                    target_state(mob), chats(session),
                )
                new_chats = [line for line in after[4] if line not in before[4]
                             and line != "You use %s." % name]
                if err:
                    return "error", "", err
                mechanic = []
                if after[0] != before[0]:
                    mechanic.append("session")
                if after[1] != before[1]:
                    mechanic.append("self effect")
                if after[2] != before[2]:
                    mechanic.append("pet")
                if after[3] != before[3]:
                    mechanic.append("target")
                if mechanic:
                    return "mechanic", "; ".join(mechanic + new_chats), ""
                if new_chats:
                    return "chat", "; ".join(new_chats), ""
                return "no-op", "", ""

            passes = [one_pass(False)]
            if job in (9, 14, 15, 18, 21):
                passes.append(one_pass(True))
            saw = [p for p in passes if p[0] != "no-op"]
            if any(p[0] == "mechanic" for p in passes):
                status, detail, err = next(p for p in passes if p[0] == "mechanic")
            elif any(p[0] == "effect" for p in passes):
                status, detail, err = next(p for p in passes if p[0] == "effect")
            elif any(p[0] == "chat" for p in passes):
                status, detail, err = next(p for p in passes if p[0] == "chat")
            elif any(p[0] == "error" for p in passes):
                status, detail, err = next(p for p in passes if p[0] == "error")
            else:
                status, detail, err = "no-op", "", ""
            if ability_id in MENU_ABILITIES:
                status, detail = "menu", "menu/resource entry; no standalone effect"
            results.append((job, ability_id, name, int(row["level"]), status,
                            detail, err))
            # Drop pets from this ability before the shared world is reused.
            for entity in list(world.entities_for_zone(100)):
                if entity.kind == "pet":
                    world.despawn_pet(entity, time.time(), "smoke")
            world.sessions = {}

    lines = ["# Job ability smoke test", "",
             "Generated by `tools/job_ability_smoke.py`.  `mechanic` means a session,",
             "pet or target value changed, including only a status icon; `chat` means only a",
             "message was produced; `no-op` means only the generic use animation/recast",
             "happened.  It is a lead, not a retail-correctness verdict.", "",
             "| Job | id | ability | lvl | smoke | detail |",
             "|---|---:|---|---:|---|---|"]
    for job, ability_id, name, level, status, detail, _ in results:
        lines.append("| %d | %d | %s | %d | %s | %s |" % (
            job, ability_id, name, level, status, detail.replace("|", "\\|")))
    text = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print("wrote %s" % args.out)
    counts = {}
    for result in results:
        counts[result[4]] = counts.get(result[4], 0) + 1
    print("tested %d: %s" % (len(results), "  ".join(
        "%s=%d" % item for item in sorted(counts.items()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
