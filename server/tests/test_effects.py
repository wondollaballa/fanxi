"""Buffs, debuffs, /heal and the teleport spells.

These are the behaviours that used to print "hits itself for 0 damage": a self spell
resolved with the basic-attack message instead of an effect.  Each test drives the real
handlers and reads the 0x028 action packet the client will see.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server.game import effects, modifiers as mod, packets
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.bit = 0

    def read(self, count: int) -> int:
        value = 0
        for index in range(count):
            value |= ((self.data[self.bit >> 3] >> (self.bit & 7)) & 1) << index
            self.bit += 1
        return value


def action_result(message: bytes) -> dict:
    """Decode the fields the tests care about from a 0x028 body."""
    reader = BitReader(message[5:])
    fields = {
        "actor": reader.read(32), "targets": reader.read(6), "results": reader.read(4),
        "category": reader.read(4), "action": reader.read(32), "recast": reader.read(32),
        "target": reader.read(32), "n": reader.read(4), "resolution": reader.read(3),
        "kind": reader.read(2), "sub": reader.read(12), "info": reader.read(5),
        "distortion": reader.read(2), "knockback": reader.read(3), "value": reader.read(17),
        "message": reader.read(10),
    }
    return fields


def messages(session) -> list[dict]:
    return [action_result(message) for message in session.queue
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028]


def chats(session) -> list[str]:
    return [bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace")
            for message in session.queue
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x017]


def status_icon(session, slot: int = 0) -> int:
    """The full status id in a 0x037 slot (low byte plus its two high bits), or -1."""
    status = session.char_status()
    if status[4 + slot] == 0xFF:
        return -1
    high = (status[4 + 0x48 + slot // 4] >> (2 * (slot % 4))) & 3
    return status[4 + slot] | (high << 8)


class EffectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True
        self.session.char["main_job"] = 13

    def cast(self, spell_id: int, targid: int = 0, wait: float = 10.0) -> None:
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, targid, packets.ACTION_CAST_MAGIC, spell_id)
        self.session.cast_magic(bytes(packet), targid)
        self.session.queue.clear()
        self.session.tick(time.time() + wait)

    def enter(self, zone: int) -> None:
        self.session.zone = zone
        self.session.pos = list(self.world.zones.position(zone))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True

    def mob(self):
        return next(entity for entity in self.session.entities
                    if entity.kind == "mob" and entity.alive)

    def test_fast_cast_shortens_the_cast_bar(self):
        """Gear Fast Cast feeds the same cast timer the spell handler uses."""
        self.session.char["mp_current"] = 100
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0, packets.ACTION_CAST_MAGIC, 43)
        before = time.time()
        with mock.patch.object(self.session, "combat_mods", return_value={mod.FASTCAST: 50}):
            self.session.cast_magic(bytes(packet), 0)
        self.assertIsNotNone(self.session.casting)
        # Protect's data is 1000 ms; 50% Fast Cast halves it, and the 0.5s floor holds.
        self.assertLessEqual(self.session.casting["finish"] - before, 0.7)

    def test_monomi_lands_a_sneak_buff_on_the_caster(self):
        self.cast(318)
        self.assertEqual(self.session.status_effects, [effects.SNEAK])
        result = next(message for message in messages(self.session)
                      if message["category"] == packets.ACTION_CATEGORY_MAGIC_FINISH)
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_GAIN_EFFECT)
        self.assertEqual(result["value"], effects.SNEAK)
        self.assertEqual(result["target"], int(self.session.char["char_id"]))
        self.assertEqual(result["kind"], 0)
        self.assertEqual(result["sub"], 318)
        # The icon goes out in the status packet, not only in the action.
        status = next(message for message in self.session.queue
                      if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x037)
        self.assertIn(bytes([effects.SNEAK]), bytes(status[4:36]))

    def test_utsusemi_shadows_absorb_a_monster_hit(self):
        self.enter(100)
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, 0, 50, 2971, 99)",
            (int(self.character["id"]),))
        self.cast(338)
        self.assertEqual(self.session.effect_power(effects.COPY_IMAGE), 3)
        # The icon carries the shadow count: three shadows is Copy Image (3).
        self.assertEqual(status_icon(self.session), effects.COPY_IMAGE_3)
        mob = self.mob()
        mob.engaged_char_id = int(self.session.char["char_id"])
        mob.x, mob.y, mob.z = self.session.pos[0] + 1, self.session.pos[1], self.session.pos[2] + 1
        mob.next_attack_at = 0.0
        hp = int(self.session.char["hp_current"])
        self.session.queue.clear()
        with mock.patch.object(self.world, "mob_attack", return_value=(False, 10, False)):
            self.world._tick_mob(mob, [self.session], time.time())
        self.assertEqual(int(self.session.char["hp_current"]), hp)
        self.assertEqual(self.session.effect_power(effects.COPY_IMAGE), 2)
        self.assertEqual(status_icon(self.session), effects.COPY_IMAGE_2)
        result = next(message for message in messages(self.session)
                      if message["message"] == packets.MESSAGE_SHADOW_ABSORB)
        self.assertEqual(result["value"], 1)

    def test_utsusemi_icon_counts_down_with_each_shadow(self):
        self.session.add_effect(effects.COPY_IMAGE, duration=900, power=3)
        self.assertEqual(status_icon(self.session), effects.COPY_IMAGE_3)
        self.assertEqual(self.session.drop_shadow(), 2)
        self.assertEqual(status_icon(self.session), effects.COPY_IMAGE_2)
        self.assertEqual(self.session.drop_shadow(), 1)
        self.assertEqual(status_icon(self.session), effects.COPY_IMAGE)
        self.assertEqual(self.session.drop_shadow(), 0)
        self.assertEqual(status_icon(self.session), -1)
        self.assertNotIn(effects.COPY_IMAGE, self.session.status_effects)

    def test_utsusemi_ni_and_san_start_on_the_fourth_shadow_icon(self):
        for power in (4, 5):
            self.session.add_effect(effects.COPY_IMAGE, duration=900, power=power)
            self.assertEqual(status_icon(self.session), effects.COPY_IMAGE_4)
            self.session.remove_effect(effects.COPY_IMAGE, quiet=True)

    def test_recasting_a_weaker_utsusemi_does_not_lower_the_count(self):
        self.session.add_effect(effects.COPY_IMAGE, duration=900, power=4,
                                icon=effects.COPY_IMAGE_4)
        # Utsusemi: Ichi on top of Ni keeps the four shadows (and the (4) icon).
        self.session.add_effect(effects.COPY_IMAGE, duration=900, power=3,
                                icon=effects.COPY_IMAGE_3)
        self.assertEqual(self.session.effect_power(effects.COPY_IMAGE), 4)
        self.assertEqual(status_icon(self.session), effects.COPY_IMAGE_4)

    def test_kurayami_lands_blindness_on_the_monster(self):
        self.enter(100)
        mob = self.mob()
        self.session.pos = [mob.x, mob.y, mob.z, self.session.pos[3]]
        self.cast(347, mob.targid)
        self.assertIn(effects.BLINDNESS, mob.effect_state)
        self.assertGreater(mob.effect_state[effects.BLINDNESS]["potency"], 0)
        result = next(message for message in messages(self.session)
                      if message["category"] == packets.ACTION_CATEGORY_MAGIC_FINISH)
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_ENFEEB)
        self.assertEqual(result["value"], effects.BLINDNESS)
        self.assertEqual(result["target"], int(mob.id))

    def test_poison_ticks_and_wears_off(self):
        self.enter(100)
        mob = self.mob()
        self.session.pos = [mob.x, mob.y, mob.z, self.session.pos[3]]
        self.cast(350, mob.targid)
        self.assertIn(effects.POISON, mob.effect_state)
        hp = int(mob.hp)
        mob.effect_state[effects.POISON]["next_tick"] = 0.0
        self.session.queue.clear()
        self.world.tick_mob_effects(mob, [self.session], time.time())
        self.assertLess(int(mob.hp), hp)
        mob.effect_state[effects.POISON]["until"] = time.time() - 1
        self.session.queue.clear()
        self.world.tick_mob_effects(mob, [self.session], time.time())
        self.assertNotIn(effects.POISON, mob.effect_state)
        self.assertTrue(any(message["message"] == packets.MESSAGE_STATUS_WEARS_OFF
                            for message in messages(self.session)))

    def test_warp_returns_to_the_set_home_point(self):
        self.session.char.update({"home_zone": 235, "home_x": -344.0, "home_y": -10.0,
                                  "home_z": -155.0, "home_rot": 0})
        self.session.zone = 107
        self.session.pos = [231.0, 2.5, -223.0, 60]
        self.session.char["mp"] = 600
        self.session.char["mp_current"] = 600
        self.cast(261)
        self.assertEqual(self.session.zone, 235)
        self.assertEqual(self.session.pos[:3], [-344.0, -10.0, -155.0])
        self.assertTrue(any(message["message"] == packets.MESSAGE_MAGIC_TELEPORT
                            for message in messages(self.session)))

    def test_home_command_uses_the_set_home_point(self):
        self.session.char.update({"home_zone": 235, "home_x": -344.0, "home_y": -10.0,
                                  "home_z": -155.0, "home_rot": 0})
        self.session.zone = 107
        self.session.pos = [231.0, 2.5, -223.0, 60]
        self.session.command(["home"])
        self.assertEqual(self.session.zone, 235)
        self.assertEqual(self.session.pos[:3], [-344.0, -10.0, -155.0])

    def test_character_record_carries_the_home_point(self):
        self.db.execute(
            "UPDATE characters SET home_zone = 235, home_x = -344.0, home_y = -10.0, "
            "home_z = -155.0, home_rot = 0 WHERE id = ?", (int(self.character["id"]),))
        record = self.service.character_record(
            self.service.character(self.character["id"]), "Fanxi")
        self.assertEqual((record["home_zone"], record["home_x"], record["home_y"],
                          record["home_z"], record["home_rot"]),
                         (235, -344.0, -10.0, -155.0, 0))

    def test_heal_command_recovers_hp_and_mp_over_time(self):
        self.session.char["hp_current"] = 1
        self.session.char["mp_current"] = 0
        self.session.heal_command(struct.pack("<II", 0x0E8, 1))
        self.assertTrue(self.session.resting)
        self.assertIn("You begin resting.", chats(self.session))
        self.session.next_rest_tick = 0.0
        self.session.queue.clear()
        self.session.tick(time.time() + 4)
        self.assertGreater(int(self.session.char["hp_current"]), 1)
        self.session.heal_command(struct.pack("<II", 0x0E8, 2))
        self.assertFalse(self.session.resting)

    def test_sneak_keeps_a_mob_from_aggroing(self):
        self.enter(100)
        mob = self.mob()
        mob.aggro = True
        mob.level = 1
        mob.x, mob.y, mob.z = self.session.pos[0], self.session.pos[1], self.session.pos[2]
        self.session.add_effect(effects.SNEAK, duration=420)
        self.world._tick_mob(mob, [self.session], time.time())
        self.assertIsNone(mob.engaged_char_id)
        self.session.remove_effect(effects.SNEAK, quiet=True)
        self.world._tick_mob(mob, [self.session], time.time() + 1)
        self.assertEqual(mob.engaged_char_id, int(self.session.char["char_id"]))


if __name__ == "__main__":
    unittest.main()
