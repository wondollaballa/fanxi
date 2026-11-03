"""Spell gating: retail learns a spell at a job and a level, and so does Fanxi."""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import modifiers as mod, packets
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


def chat(session) -> list[str]:
    out = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        out.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return out


class SpellLevelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.session.fresh_login = False
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True
        self.session.char["main_job"] = 1   # WAR
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 0
        self.session.char["sub_level"] = 0

    def cast(self, spell_id: int) -> None:
        pkt = bytearray(16)
        struct.pack_into("<IHHI", pkt, 4, 0, 0, packets.ACTION_CAST_MAGIC, int(spell_id))
        self.session.casting = None
        # The client sends the target's targid; a self-target spell needs its own.
        self.session.cast_magic(bytes(pkt), int(self.session.targid))

    def test_the_table_carries_every_job_level(self):
        self.assertEqual(((3, 1), (5, 3), (7, 5), (20, 5)),
                         self.service.spell_levels(1))        # Cure
        self.assertEqual(((10, 33),), self.service.spell_levels(462))  # Magic Finale
        self.assertEqual((), self.service.spell_levels(4982))  # a Trust is not gated

    def test_a_warrior_cannot_cast_cure(self):
        self.assertFalse(self.session.can_cast_spell(1))
        self.assertFalse(self.session.spell_bits()[1 // 8] & (1 << (1 % 8)))
        self.cast(1)
        self.assertIsNone(self.session.casting)
        self.assertIn("You cannot cast that spell.", chat(self.session))

    def test_a_white_mage_can(self):
        self.session.char["main_job"] = 3
        self.session.char["mp_current"] = 500
        self.assertTrue(self.session.can_cast_spell(1))
        self.assertTrue(self.session.spell_bits()[0] & (1 << 1))
        self.cast(1)
        self.assertIsNotNone(self.session.casting)

    def spell_id(self, name: str) -> int:
        row = self.service.spell_by_name(name)
        self.assertIsNotNone(row, name)
        return int(row["id"])

    def test_the_sub_job_levels_count(self):
        self.session.char["sub_job"] = 5   # RDM learns Cure at 3
        self.session.char["sub_level"] = 49
        self.assertTrue(self.session.can_cast_spell(1))
        self.assertTrue(self.session.spell_bits()[0] & (1 << 1))
        # A level above the sub job's is still refused: Fire V is BLM 86 / SCH 91.
        self.assertFalse(self.session.can_cast_spell(self.spell_id("Fire V")))

    def test_red_mage_job_point_spells_are_granted(self):
        """The RDM "New Spell(s)" gifts unlock the Fire V line and the tier-III spells."""
        self.session.char.update(main_job=5, main_level=99, sub_job=20, sub_level=49)
        grants = ("Fire V", "Blizzard V", "Aero V", "Stone V", "Thunder V",
                  "Water V", "Addle II", "Distract III", "Frazzle III",
                  "Refresh III", "Temper II")
        bits = self.session.spell_bits()
        for name in grants:
            spell_id = self.spell_id(name)
            self.assertTrue(self.session.can_cast_spell(spell_id), name)
            self.assertTrue(bits[spell_id // 8] & (1 << (spell_id % 8)), name)

    def test_scholar_job_point_spells_are_granted(self):
        """The SCH storm II line and Helix IIs are gift spells, not open rows."""
        self.session.char.update(main_job=20, main_level=99, sub_job=0, sub_level=0)
        bits = self.session.spell_bits()
        for name in ("Sandstorm II", "Aurorastorm II", "Geohelix II",
                     "Pyrohelix II"):
            spell_id = self.spell_id(name)
            self.assertTrue(self.session.can_cast_spell(spell_id), name)
            self.assertTrue(bits[spell_id // 8] & (1 << (spell_id % 8)), name)
        # The storm IIs have no ordinary level row; only the Scholar gift opens them.
        self.session.char.update(main_job=1, main_level=99)
        storm = self.spell_id("Sandstorm II")
        self.assertFalse(self.session.can_cast_spell(storm))
        self.assertFalse(self.session.spell_bits()[storm // 8] & (1 << (storm % 8)))

    def test_a_job_point_spell_stays_closed_to_other_jobs(self):
        fire5 = self.spell_id("Fire V")
        addle2 = self.spell_id("Addle II")
        # A Warrior has neither the BLM/SCH level row nor the RDM gift.
        self.assertFalse(self.session.can_cast_spell(fire5))
        self.assertFalse(self.session.can_cast_spell(addle2))
        bits = self.session.spell_bits()
        self.assertFalse(bits[fire5 // 8] & (1 << (fire5 % 8)))
        self.assertFalse(bits[addle2 // 8] & (1 << (addle2 % 8)))
        # Fire V is still a normal Black Mage spell by level.
        self.session.char.update(main_job=4, main_level=99)
        self.assertTrue(self.session.can_cast_spell(fire5))
        # Addle II is a gift only; a Black Mage does not get the RDM row.
        self.assertFalse(self.session.can_cast_spell(addle2))


if __name__ == "__main__":
    unittest.main()
