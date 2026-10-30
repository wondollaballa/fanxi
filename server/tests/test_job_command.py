"""``//job``: the self form and the box form that changes a sub-account character."""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import effects
from fanxi_server.game.entities import ZoneEntity
from fanxi_server.game.world import World
from fanxi_server.game.zone import (
    MSG_STYLE_LOCK_OFF, MSG_STYLE_LOCK_ON, ZoneSession,
)


def chats(session):
    lines = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        lines.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return lines


def msg_types(session):
    return [struct.unpack_from("<H", message, 0)[0] & 0x1FF for message in session.queue]


def group_row(session, char_id):
    """The 0x0DD party row for that character, or None if the roster was not resent."""
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x0DD:
            continue
        if struct.unpack_from("<I", message, 4)[0] == int(char_id):
            return message
    return None


def system_ids(session):
    """The 0x009 system-message ids queued for the client."""
    return [struct.unpack_from("<H", message, 10)[0] for message in session.queue
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x009]


def party_tp(session):
    """The TP in the last 0x0DF party row, in tenths (0 when the roster was not sent)."""
    for message in reversed(session.queue):
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x0DF:
            return struct.unpack_from("<I", message, 16)[0]
    return None


BLM_SET = (23898, 23943, 23988, 24033)
RUN_SET = (23917, 23962, 24007, 24052, 24097)


class JobCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            self.account["id"], {"name": "Onedough", "race": 1})
        self.sub = self.service.create_sub_account(
            self.account["id"], {"character": {"name": "Threedough", "race": 1}})
        self.world = World(self.config, self.service, None)
        self.session = self.make_session(self.character, ("127.0.0.1", 1201), 100)
        self.sub_session = self.make_session(self.sub["character"], ("127.0.0.1", 1202), 246)
        self.set_jobs(self.session, {1: (99, 0), 12: (99, 0), 13: (99, 0)}, main=1)
        self.set_jobs(self.sub_session, {4: (99, 0), 13: (99, 0), 22: (99, 0)}, main=4)
        self.session.queue.clear()
        self.sub_session.queue.clear()

    def make_session(self, character, addr, zone):
        session = ZoneSession(
            self.world, addr,
            self.service.character_record(self.service.character(character["id"]),
                                          self.world.server_name))
        session.set_key(bytes(20))
        session.logged_in = True
        session.zone = int(zone)
        session.pos = list(self.world.zones.position(int(zone)))
        session.load_zone_entities()
        session.zone_loaded = True
        session.last_packet_at = time.time()
        self.world.sessions[addr] = session
        return session

    def set_jobs(self, session, jobs, *, main):
        session.char["jobs"] = dict(jobs)
        session.char["main_job"] = int(main)
        session.char["main_level"] = 99
        session.char["sub_job"] = 0
        session.char["sub_level"] = 0

    def give(self, session, container, slot, item_id, quantity=1):
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, ?, ?, ?, ?)",
            (int(session.char["id"]), int(container), int(slot), int(item_id), int(quantity)))

    def inventory_ids(self, session, container=0):
        return {int(row["item_id"]) for row in self.db.all(
            "SELECT item_id FROM char_inventory WHERE character_id = ? AND container = ?",
            (int(session.char["id"]), int(container)))}

    def stored_ids(self, session):
        return {int(row["item_id"]) for row in self.db.all(
            "SELECT item_id FROM char_storage WHERE character_id = ?",
            (int(session.char["id"]),))}

    def test_three_words_change_the_named_sub_account_character(self):
        # The old BLM outfit is loose in Threedough's bag; the RUN set is on its slips.
        for offset, item_id in enumerate(BLM_SET):
            self.give(self.sub_session, 0, 10 + offset, item_id)
        for item_id in RUN_SET:
            self.db.execute(
                "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
                "VALUES (?, ?, 1, 32)", (int(self.sub_session.char["id"]), item_id))
        self.sub_session.queue.clear()
        self.session.queue.clear()

        self.session.command("job threedough run nin".split())

        # Both halves of the pair land on the named box, not on the sender.
        self.assertEqual(int(self.sub_session.char["main_job"]), 22)
        self.assertEqual(int(self.sub_session.char["main_level"]), 99)
        self.assertEqual(int(self.sub_session.char["sub_job"]), 13)
        self.assertEqual(int(self.sub_session.char["sub_level"]), 49)
        self.assertEqual(int(self.session.char["main_job"]), 1)
        saved = self.service.character(int(self.sub_session.char["id"]))
        self.assertEqual(int(saved["main_job"]), 22)
        self.assertEqual(int(saved["sub_job"]), 13)
        self.assertEqual(int(saved["sub_level"]), 49)

        # The same gear swap runs on the target: the old set is slipped, the new pulled.
        self.assertTrue(set(BLM_SET).issubset(self.stored_ids(self.sub_session)))
        self.assertFalse(set(BLM_SET) & self.inventory_ids(self.sub_session, 0))
        bag = {int(row["item_id"]) for row in self.db.all(
            "SELECT item_id FROM char_inventory WHERE character_id = ?",
            (int(self.sub_session.char["id"]),))}
        self.assertTrue(set(RUN_SET).issubset(bag))
        self.assertTrue(set(RUN_SET).isdisjoint(self.stored_ids(self.sub_session)))
        # Nothing was stored or pulled for the sender.
        self.assertEqual(self.stored_ids(self.session), set())
        self.assertFalse(set(RUN_SET) & self.inventory_ids(self.session, 0))

        # The job bundle goes to the target client, and only chat comes back to the caller.
        target_types = msg_types(self.sub_session)
        self.assertIn(0x01B, target_types)
        self.assertIn(0x0AC, target_types)
        info = next(message for message in self.sub_session.queue
                    if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x01B)
        self.assertEqual(int(info[4 + 4]), 22)
        self.assertEqual(set(msg_types(self.session)), {0x017})

        target_chat = "\n".join(chats(self.sub_session))
        self.assertIn("Onedough changes your job to RUN/NIN.", target_chat)
        self.assertIn("You are now a level 99 Rune Fencer with a level 49 Ninja support job.",
                      target_chat)
        self.assertIn("Stored 4 items RUN cannot equip (4 on slips).", target_chat)
        self.assertIn("Pulled 5 RUN items into the wardrobes (5 on slips).", target_chat)
        self.assertEqual(chats(self.session), ["Threedough is now RUN/NIN."])

    def test_two_words_still_change_the_sender_only(self):
        self.sub_session.queue.clear()

        self.session.command("job sam war".split())

        self.assertEqual(int(self.session.char["main_job"]), 12)
        self.assertEqual(int(self.session.char["sub_job"]), 1)
        self.assertEqual(int(self.session.char["sub_level"]), 49)
        # The sub-account is untouched and hears nothing.
        self.assertEqual(int(self.sub_session.char["main_job"]), 4)
        self.assertEqual(chats(self.sub_session), [])
        self.assertIn("You are now a level 99 Samurai with a level 49 Warrior support job.",
                      chats(self.session))

    def test_two_words_naming_a_box_explain_the_three_word_form(self):
        self.session.queue.clear()

        self.session.command("job threedough sam".split())

        lines = "\n".join(chats(self.session))
        self.assertIn("Unknown job 'threedough'", lines)
        self.assertIn("To change another character use //job <character> <job> <sub>.",
                      lines)
        self.assertEqual(int(self.sub_session.char["main_job"]), 4)

    def test_an_unknown_support_job_is_an_error(self):
        self.session.queue.clear()

        self.session.command("job war bogus".split())

        self.assertIn("Unknown support job 'bogus'. Try NIN, Ninja or 13.",
                      chats(self.session))
        self.assertEqual(int(self.session.char["main_job"]), 1)

    def test_another_accounts_character_is_refused(self):
        other = self.service.register("other", "password123").account
        other_character = self.service.create_character(
            other["id"], {"name": "Notmine", "race": 1})
        other_session = self.make_session(
            other_character, ("127.0.0.1", 1203), 246)
        self.set_jobs(other_session, {1: (99, 0), 12: (99, 0)}, main=1)
        other_session.queue.clear()

        self.session.command("job Notmine sam war".split())

        self.assertIn("Notmine is not on your account or a sub-account.",
                      chats(self.session))
        self.assertEqual(int(other_session.char["main_job"]), 1)
        self.assertEqual(chats(other_session), [])

    def test_unknown_and_parked_characters_are_reported(self):
        self.session.queue.clear()
        self.session.command("job Twodough sam war".split())
        self.assertIn("No online character called Twodough. //job <job> [sub] changes your "
                      "own job; //job <character> <job> <sub> changes a box.",
                      chats(self.session))

        self.sub_session.sleeping = True
        self.session.queue.clear()
        self.session.command("job Threedough sam war".split())
        self.assertIn("Threedough is asleep; //wake it first.", chats(self.session))
        self.assertEqual(int(self.sub_session.char["main_job"]), 4)

        self.sub_session.sleeping = False
        self.sub_session.zoning = True
        self.session.queue.clear()
        self.session.command("job Threedough sam war".split())
        self.assertIn("Threedough is still zoning; try again in a moment.",
                      chats(self.session))
        self.assertEqual(int(self.sub_session.char["main_job"]), 4)

    def test_the_party_roster_shows_the_new_job(self):
        # A group row carries the job pair only while both are in the same zone.
        self.sub_session.zone = 100
        group = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(group, self.sub_session))
        self.session.queue.clear()
        self.sub_session.queue.clear()

        self.session.command("job Threedough run nin".split())

        row = group_row(self.session, int(self.sub_session.char["char_id"]))
        self.assertIsNotNone(row)
        self.assertEqual(row[4 + 0x1E], 22)   # main job
        self.assertEqual(row[4 + 0x1F], 99)   # main level
        self.assertEqual(row[4 + 0x20], 13)   # sub job
        self.assertEqual(row[4 + 0x21], 49)   # sub level
        # The leader's own row and the target's client are refreshed too.
        self.assertIsNotNone(group_row(self.session, int(self.session.char["char_id"])))
        self.assertIsNotNone(group_row(self.sub_session, int(self.sub_session.char["char_id"])))

    def test_job_change_clears_the_old_lock_and_locks_the_new_outfit(self):
        old_style = {4: 1001, 5: 1002, 6: 1003, 7: 1004, 8: 1005}
        self.sub_session._apply_style(True, old_style)
        self.assertTrue(self.sub_session.style_locked())
        for item_id in RUN_SET:
            self.db.execute(
                "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
                "VALUES (?, ?, 1, 32)", (int(self.sub_session.char["id"]), item_id))
        self.session.queue.clear()
        self.sub_session.queue.clear()

        self.session.command("job Threedough run nin".split())

        # The previous job's locked models are gone and the new outfit is locked.
        self.assertTrue(self.sub_session.style_locked())
        models = self.sub_session._style_models()
        current = self.sub_session._current_models()
        self.assertFalse(set(old_style.values()) & set(models.values()))
        for kind in (4, 5, 6, 7, 8):
            self.assertEqual(models[kind], current[kind])
        saved = self.service.character(int(self.sub_session.char["id"]))
        self.assertEqual(int(saved["style_lock"]), 1)
        self.assertEqual(int(saved["style_head"]), current[4])
        self.assertEqual(int(saved["style_body"]), current[5])
        # The client sees the old lock go off, then the new one come on.
        ids = system_ids(self.sub_session)
        self.assertIn(MSG_STYLE_LOCK_OFF, ids)
        self.assertIn(MSG_STYLE_LOCK_ON, ids)
        # The final 0x051 carries the locked new models, not the old job's.
        grap = [message for message in self.sub_session.queue
                if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x051][-1]
        self.assertEqual(list(struct.unpack_from("<9H", grap, 4)),
                         list(self.sub_session.looks()))

    def test_observers_respawn_the_character_with_the_locked_outfit(self):
        self.sub_session.zone = 100
        self.session.entities_sent = True
        self.session.seen_players[int(self.sub_session.char["char_id"])] = self.sub_session
        self.session.queue.clear()
        self.sub_session.queue.clear()

        self.session.command("job Threedough run nin".split())

        bodies = [message for message in self.session.queue
                  if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x00D]
        self.assertGreaterEqual(len(bodies), 2)   # despawn, then spawn
        looks = struct.unpack_from("<9H", bodies[-1], 4 + 0x44)
        self.assertEqual(list(looks), self.sub_session.looks())

    def test_unlocked_job_check_reads_the_target(self):
        # WAR is unlocked on the sender, not on Threedough.
        self.session.queue.clear()
        self.session.command("job Threedough war nin".split())

        self.assertIn("Threedough has not unlocked that job.", chats(self.session))
        self.assertEqual(int(self.sub_session.char["main_job"]), 4)
        self.assertEqual(chats(self.sub_session), [])

        # RUN is unlocked on Threedough; SAM is not.
        self.session.queue.clear()
        self.session.command("job Threedough run sam".split())
        self.assertIn("Threedough has not unlocked that support job.", chats(self.session))
        self.assertEqual(int(self.sub_session.char["main_job"]), 4)
        self.assertEqual(chats(self.sub_session), [])

    def test_city_job_change_refills_hp_mp_and_resets_tp(self):
        self.session.zone = 245                 # Lower Jeuno
        self.session.char["jobs"][7] = (99, 0)  # PLD
        self.session.char["hp_current"] = 1
        self.session.char["mp_current"] = 1
        self.session.char["tp"] = 1500
        self.session.queue.clear()

        self.session.command("job pld nin".split())

        self.assertEqual(int(self.session.char["main_job"]), 7)
        self.assertEqual(int(self.session.char["hp_current"]), int(self.session.char["hp"]))
        self.assertEqual(int(self.session.char["mp_current"]), int(self.session.char["mp"]))
        self.assertEqual(int(self.session.char["tp"]), 0)
        self.assertEqual(party_tp(self.session), 0)

    def test_field_job_change_keeps_hp_mp_and_resets_tp(self):
        self.session.zone = 100                 # West Ronfaure
        self.session.char["jobs"][7] = (99, 0)  # PLD
        self.session.char["hp_current"] = 1
        self.session.char["mp_current"] = 1
        self.session.char["tp"] = 1200
        self.session.queue.clear()

        self.session.command("job pld nin".split())

        self.assertEqual(int(self.session.char["main_job"]), 7)
        # The maximum moved with the job, but the bars did not: the player has to heal.
        self.assertEqual(int(self.session.char["hp_current"]), 1)
        self.assertEqual(int(self.session.char["mp_current"]), 1)
        self.assertEqual(int(self.session.char["tp"]), 0)
        self.assertEqual(party_tp(self.session), 0)

    def test_job_change_clears_buffs_but_keeps_conquest_effects(self):
        now = time.time()
        self.session.status_effects = [
            effects.PROTECT, effects.SIGNET, effects.SANCTION,
            effects.FOOD, effects.SIGIL, effects.IONIS,
        ]
        self.session.effect_state = {
            effects.PROTECT: {"until": now + 300, "icon": effects.PROTECT},
            effects.SIGNET: {"until": now + 600, "icon": effects.SIGNET},
        }
        self.session.food = {
            "item_id": 4384, "name": "Rice Ball", "until": now + 600,
            "mods": {1: 5},
        }
        self.session.queue.clear()

        self.session.command("job sam war".split())

        self.assertEqual(self.session.status_effects,
                         [effects.SIGNET, effects.SANCTION, effects.SIGIL, effects.IONIS])
        self.assertIn(effects.SIGNET, self.session.effect_state)
        self.assertNotIn(effects.PROTECT, self.session.effect_state)
        self.assertEqual(int(self.session.food["item_id"]), 0)
        self.assertEqual(self.session.food["mods"], {})

    def test_job_change_is_refused_during_an_event(self):
        self.session.in_event = True
        self.session.queue.clear()

        self.session.command("job sam war".split())

        self.assertIn("You cannot change jobs during an event.", chats(self.session))
        self.assertEqual(int(self.session.char["main_job"]), 1)

    def test_job_change_is_refused_in_a_fight(self):
        self.session.engaged_id = 0x01000001
        self.session.queue.clear()

        self.session.command("job sam war".split())

        self.assertIn("You cannot change jobs while in a fight.", chats(self.session))
        self.assertEqual(int(self.session.char["main_job"]), 1)

    def test_job_change_is_refused_while_knocked_out(self):
        self.session.dead_until = time.time() + 5.0
        self.session.char["hp_current"] = 0
        self.session.queue.clear()

        self.session.command("job sam war".split())

        self.assertIn("You cannot change jobs while knocked out.", chats(self.session))
        self.assertEqual(int(self.session.char["main_job"]), 1)

    def test_a_mob_claiming_the_character_also_blocks_the_change(self):
        mob = ZoneEntity(kind="mob", id=0x01000002, targid=0x300,
                         zone=self.session.zone, name="Orcish Fodder",
                         claim_char_id=int(self.session.char["char_id"]),
                         engaged_char_id=int(self.session.char["char_id"]))
        self.session.entities.append(mob)
        self.session.queue.clear()

        self.session.command("job sam war".split())

        self.assertIn("You cannot change jobs while in a fight.", chats(self.session))
        self.assertEqual(int(self.session.char["main_job"]), 1)

    def test_job_change_is_refused_in_dynamis_divergence(self):
        self.session.zone = 296                 # Dynamis - Windurst [D]
        self.session.queue.clear()

        self.session.command("job sam war".split())

        self.assertIn("You cannot change jobs in this area.", chats(self.session))
        self.assertEqual(int(self.session.char["main_job"]), 1)

    def test_remote_job_change_uses_the_targets_zone(self):
        self.sub_session.zone = 294             # Dynamis - San d'Oria [D]
        self.session.queue.clear()

        self.session.command("job Threedough run nin".split())

        self.assertIn("Threedough cannot change jobs in this area.", chats(self.session))
        self.assertEqual(int(self.sub_session.char["main_job"]), 4)
        self.assertEqual(chats(self.sub_session), [])

    def test_moogles_menu_applies_the_same_rules(self):
        self.session.zone = 245
        self.session.char["moghouse"] = 1
        self.session.char["jobs"][7] = (99, 0)  # PLD
        self.session.char["hp_current"] = 1
        self.session.char["mp_current"] = 1
        self.session.char["tp"] = 1500
        self.session.status_effects = [effects.PROTECT]
        self.session.effect_state = {
            effects.PROTECT: {"until": time.time() + 60, "icon": effects.PROTECT},
        }
        self.session.queue.clear()

        self.session.myroom_job(bytes(4) + bytes((7, 0)))

        self.assertEqual(int(self.session.char["main_job"]), 7)
        self.assertEqual(self.session.status_effects, [])
        self.assertEqual(int(self.session.char["hp_current"]), int(self.session.char["hp"]))
        self.assertEqual(int(self.session.char["mp_current"]), int(self.session.char["mp"]))
        self.assertEqual(int(self.session.char["tp"]), 0)


if __name__ == "__main__":
    unittest.main()
