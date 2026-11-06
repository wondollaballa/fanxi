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

from support import make_huffman_dir, make_service

from fanxi_server.game import effects, merits, modifiers as mod, packets
from fanxi_server.game.cipher import Huffman
from fanxi_server.game.entities import ZoneEntity
from fanxi_server.game.world import World
from fanxi_server.game.spell_effects import STATUS_SPELLS
from fanxi_server.game.zone import VANA_EPOCH, ZoneSession, sub


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


def battle_messages(session) -> list[dict]:
    """Decode the chat-only 0x029 lines (DoT ticks, wear-offs) that carry no action."""
    out = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x029:
            continue
        sender, target, param, value, starg, ttarg, msg, kind = struct.unpack_from(
            "<IIIIHHHB", message, 4)
        out.append({"sender": sender, "target": target, "param": param, "value": value,
                    "sender_targid": starg, "target_targid": ttarg,
                    "message": msg, "kind": kind})
    return out


def chats(session) -> list[str]:
    return [bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace")
            for message in session.queue
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x017]


def item_use_packet(slot: int, container: int = 0, item_num: int = 0,
                    char_id: int = 0) -> bytes:
    """A C2S 0x037 item-use request with the client's real field layout.

    The client names the container and the slot; the four bytes at 0x08 are ItemNum
    (the count) and are always zero, never the item id.
    """
    body = struct.pack("<IIHBBI", int(char_id), int(item_num), 0x400,
                       int(slot) & 0xFF, 0, int(container))
    return bytes(sub(0x037, body))


def status_icon(session, slot: int = 0) -> int:
    """The full status id in a 0x037 slot (low byte plus its two high bits), or -1."""
    status = session.char_status()
    if status[4 + slot] == 0xFF:
        return -1
    high = (status[4 + 0x48 + slot // 4] >> (2 * (slot % 4))) & 3
    return status[4 + slot] | (high << 8)


def effect_seconds(state: dict) -> float:
    """The time left on an effect, measured from the wall clock the session uses."""
    return float(state["until"]) - time.time()


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

    def claim_mob(self):
        """A live monster to put hate on; the effects fixture's zone may have none."""
        return ZoneEntity(kind="mob", id=0x01000100, targid=0x210, zone=self.session.zone,
                          name="Test Mob", level=99, hp=50000, hp_max=50000)

    def test_another_party_cannot_take_a_claimed_monster(self):
        """A cross-party hit must not move the claim.

        The client draws a monster claimed by another party pink and refuses to attack
        it, but the server used to give the claim to whoever had the most hate: a box's
        Trust could flip a live fight pink and leave the first player unable to swing or
        disengage while the server kept swinging for them.
        """
        mob = self.claim_mob()
        mine = int(self.session.char["char_id"])
        mob.claim_char_id = mine
        mob.engaged_char_id = mine
        self.world.add_damage_hate(mob, 0x0100FFEE, 1_000_000, time.time())
        self.assertEqual(int(mob.claim_char_id), mine)
        self.assertEqual(int(mob.engaged_char_id), mine)

    def test_a_party_member_may_take_the_claim(self):
        other = self.party_with()
        mob = self.claim_mob()
        mine = int(self.session.char["char_id"])
        mob.claim_char_id = mine
        mob.engaged_char_id = mine
        theirs = int(other.char["char_id"])
        self.world.add_damage_hate(mob, theirs, 1_000_000, time.time())
        self.assertEqual(int(mob.claim_char_id), theirs)

    def slot_of(self, item_id: int, container: int = 0) -> tuple[int, int]:
        """(container, slot) where a granted item actually landed."""
        row = self.db.one(
            "SELECT container, slot FROM char_inventory "
            "WHERE character_id = ? AND container = ? AND item_id = ? "
            "ORDER BY slot LIMIT 1",
            (int(self.session.char["id"]), int(container), int(item_id)))
        self.assertIsNotNone(row, "item %d is not in container %d" % (item_id, container))
        return int(row["container"]), int(row["slot"])

    def as_caster(self, spell_id: int) -> None:
        """Borrow a job that learns the spell; the job gate has its own tests."""
        if not self.session.can_cast_spell(spell_id):
            job, level = self.service.spell_levels(spell_id)[0]
            self.session.char["main_job"] = int(job)
            self.session.char["main_level"] = max(99, int(level))

    def cast(self, spell_id: int, targid: int = 0, wait: float = 10.0) -> None:
        self.as_caster(spell_id)
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, targid, packets.ACTION_CAST_MAGIC, spell_id)
        self.session.cast_magic(bytes(packet), targid)
        self.session.queue.clear()
        self.session.tick(time.time() + wait)

    def ability(self, ability_id: int) -> list[int]:
        """Use a job ability the way the Job Abilities menu sends it (0x01A action 9).

        Returns the packet types the session queued, so a test can prove the 0x037 went
        out and not only that the state changed.
        """
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, ability_id)
        self.session.job_ability(bytes(packet), 0)
        types = [struct.unpack_from("<H", message, 0)[0] & 0x1FF
                 for message in self.session.queue]
        self.session.queue.clear()
        return types

    def packed(self) -> list[tuple[int, bytes]]:
        """The sub-messages pack() puts on the wire, in order."""
        if self.world.huff is None:
            self.world.huff = Huffman.from_folder(
                make_huffman_dir(Path(self.tmp.name) / "huff"))
        data, bits, _zone_out = self.session.pack()
        body = self.world.huff.decompress(data, bits)
        out = []
        offset = 0
        while offset < len(body):
            head = struct.unpack_from("<H", body, offset)[0]
            size = (head >> 9) * 4
            out.append((head & 0x1FF, bytes(body[offset:offset + size])))
            offset += size
        return out

    def enter(self, zone: int) -> None:
        self.session.zone = zone
        self.session.pos = list(self.world.zones.position(zone))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True

    def party_with(self, name: str = "Ally", *, offset: float = 0.0):
        """A second real character in the caster's party, ``offset`` yalms to the east."""
        account = self.service.register(name.casefold(), "password123").account
        row = self.service.create_character(account["id"], {"name": name, "race": 1})
        other = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(row["id"]), name))
        other.set_key(bytes(20))
        other.logged_in = True
        other.zone = self.session.zone
        other.targid = 0x401
        other.pos = list(self.session.pos)
        other.pos[0] = float(other.pos[0]) + float(offset)
        other.zone_loaded = True
        self.world.sessions[("127.0.0.1", 4321)] = other
        party = self.world.party_of(int(self.session.char["char_id"]))
        if party is None:
            party = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(party, other))
        return other

    def mob(self):
        return next(entity for entity in self.session.entities
                    if entity.kind == "mob" and entity.alive)

    def at_mob(self):
        """Stand on the first live monster with enough MP for a level 99 spell."""
        mob = self.mob()
        self.session.pos = [mob.x, mob.y, mob.z, self.session.pos[3]]
        self.session.char["mp"] = 1000
        self.session.char["mp_current"] = 1000
        return mob

    def last_magic(self) -> dict:
        return next(message for message in messages(self.session)
                    if message["category"] == packets.ACTION_CATEGORY_MAGIC_FINISH)

    def test_fast_cast_shortens_the_cast_bar(self):
        """Gear Fast Cast feeds the same cast timer the spell handler uses."""
        self.session.char["mp_current"] = 100
        self.as_caster(43)
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
        # The result's sub-kind is the client animation (356), not the spell id (318).
        self.assertEqual(result["sub"], 356)
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
        with mock.patch.object(self.world, "mob_attack", return_value=(False, 10, False, None)):
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
                            for message in battle_messages(self.session)))

    def test_breakga_petrifies_without_dealing_damage(self):
        """Breakga is a pure petrification; it used to print a 233-damage hit."""
        self.enter(100)
        mob = self.at_mob()
        hp = int(mob.hp)
        self.cast(365, mob.targid)
        self.assertIn(effects.PETRIFICATION, mob.effect_state)
        self.assertGreater(float(mob.effect_state[effects.PETRIFICATION]["until"]), time.time())
        self.assertEqual(int(mob.hp), hp)
        result = self.last_magic()
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_ENFEEB)
        self.assertEqual(result["value"], effects.PETRIFICATION)
        # The result's sub-kind is the client animation (271), not the spell id (365).
        self.assertEqual(result["sub"], 271)

    def test_dia_lands_a_small_hit_and_a_damage_over_time(self):
        """Dia is 1 HP/tick for a minute, not a 1,475-damage nuke."""
        self.enter(100)
        mob = self.at_mob()
        hp = int(mob.hp)
        self.cast(23, mob.targid)
        state = mob.effect_state[effects.DIA]
        self.assertEqual(int(state["tick"]), 1)
        self.assertEqual(int(state["potency"]), 10)  # -10% defence
        result = self.last_magic()
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_DMG)
        self.assertLess(result["value"], 100)
        self.assertEqual(int(mob.hp), hp - result["value"])
        before = int(mob.hp)
        state["next_tick"] = 0.0
        self.session.queue.clear()
        self.world.tick_mob_effects(mob, [self.session], time.time())
        self.assertEqual(int(mob.hp), before - 1)
        # The HP update is the feedback; no chat line for the tick.
        self.assertFalse(any(message["message"] == packets.MESSAGE_TARGET_TAKES_DAMAGE
                             for message in messages(self.session)))
        self.assertFalse(any(message["message"] == packets.MESSAGE_TARGET_TAKES_DAMAGE
                             for message in battle_messages(self.session)))

    def test_frazzle_lowers_magic_evasion_and_shows_in_the_target_report(self):
        """Frazzle used to land effect 404 with potency 0, so it did nothing."""
        self.enter(100)
        mob = self.at_mob()
        row = self.db.one("SELECT id FROM spells WHERE name = 'Frazzle'")
        self.cast(int(row["id"]), mob.targid)
        state = mob.effect_state[effects.MAGIC_EVASION_DOWN]
        self.assertEqual(str(state["name"]), "Frazzle")
        self.assertEqual(int(state["potency"]), 35)
        self.assertGreater(float(state["until"]) - time.time(), 100.0)
        base = int(self.world.monster_sheet(mob).fighter.mods.get(mod.MEVA, 0))
        debuffed = self.world.monster_debuff_mods(mob)
        self.assertEqual(int(debuffed.get(mod.MEVA, 0)), base - 35)
        report = self.session.target_effect_report(entity_id=int(mob.id))
        self.assertEqual(report["target"]["name"], mob.name)
        effect = next(row for row in report["effects"] if row["id"] == effects.MAGIC_EVASION_DOWN)
        self.assertEqual(effect["name"], "Frazzle")
        self.assertEqual(effect["potency"], 35)

    def test_impact_nukes_and_leaves_its_stat_down(self):
        self.enter(100)
        mob = self.at_mob()
        mob.hp = mob.hp_max = 100_000
        before = mob.hp
        self.cast(503, mob.targid, wait=22)
        self.assertGreater(before - mob.hp, 0)
        state = mob.effect_state.get(effects.INT_DOWN)
        self.assertIsNotNone(state)
        self.assertEqual(str(state["name"]), "Impact")
        self.assertEqual(int(state["potency"]), 20)

    def test_target_report_lists_dia_and_the_evasion_debuff(self):
        self.enter(100)
        mob = self.at_mob()
        now = time.time()
        self.world.apply_mob_effect(
            mob, effects.for_spell("Dia V"), self.session, now,
            duration=180, potency=30, tick=5, name="Dia V")
        self.world.apply_mob_effect(
            mob, effects.for_spell("Distract II"), self.session, now,
            duration=300, potency=50, name="Distract II")
        report = self.session.target_effect_report(entity_id=int(mob.id))
        by_name = {row["name"]: row for row in report["effects"]}
        self.assertIn("Dia V", by_name)
        self.assertEqual(by_name["Dia V"]["potency"], 30)
        self.assertEqual(by_name["Dia V"]["tick"], 5)
        self.assertIn("Distract II", by_name)
        self.assertEqual(by_name["Distract II"]["potency"], 50)
        base_defense = int(self.world.monster_sheet(mob).fighter.defense)
        self.assertEqual(int(self.world.debuffed_monster(mob).defense),
                         int(base_defense * 70 / 100))
        self.assertLess(int(self.world.debuffed_monster(mob).evasion),
                        int(self.world.monster_sheet(mob).fighter.evasion))

    def test_a_spell_pull_claims_an_idle_monster(self):
        """Casting on a monster gives it enmity and makes it fight the caster."""
        self.enter(100)
        mob = self.at_mob()
        self.assertIsNone(mob.engaged_char_id)
        self.cast(23, mob.targid)
        char_id = int(self.session.char["char_id"])
        self.assertEqual(mob.engaged_char_id, char_id)
        self.assertEqual(int(mob.animation), 1)
        self.assertIn(char_id, mob.enmity)
        self.assertGreaterEqual(float(mob.next_attack_at), time.time())

    def test_cast_start_is_the_retail_line_with_the_spell_id_and_no_animation(self):
        """A Magic Start carries the spell id in its value; the result animation is 0.

        Retail leaves sub_kind 0 on a start (LandSandBoat's 0x028 capture test encodes the
        same), and the client picks the casting pose from the spell id in the value.  The
        old code wrote the spell's finish animation here, which made Refresh (109) play a
        summon/trust pose while it cast.
        """
        self.enter(100)
        mob = self.at_mob()
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, mob.targid,
                         packets.ACTION_CAST_MAGIC, 23)
        self.session.queue.clear()
        self.as_caster(23)
        self.session.cast_magic(bytes(packet), mob.targid)
        start = next(message for message in messages(self.session)
                     if message["category"] == packets.ACTION_CATEGORY_MAGIC_START)
        self.assertEqual(start["message"], packets.MESSAGE_MAGIC_STARTS_CASTING)
        self.assertEqual(start["value"], 23)
        self.assertEqual(start["sub"], 0)
        self.assertNotIn("You start casting Dia.", chats(self.session))

    def test_refresh_cast_starts_without_its_finish_animation(self):
        """Refresh (109) must not play its finish animation on the cast bar.

        The reported regression: writing the finish animation into the Magic Start
        made Refresh's cast pose look like a trust summon.
        """
        self.enter(100)
        self.session.char["main_job"] = 5
        self.session.char["main_level"] = 99
        self.session.char["mp"] = 1000
        self.session.char["mp_current"] = 1000
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0, packets.ACTION_CAST_MAGIC, 109)
        self.session.queue.clear()
        self.session.cast_magic(bytes(packet), 0)
        start = next(message for message in messages(self.session)
                     if message["category"] == packets.ACTION_CATEGORY_MAGIC_START)
        self.assertEqual(start["value"], 109)
        self.assertEqual(start["sub"], 0)
        self.session.queue.clear()
        self.session.tick(time.time() + 10)
        finish = self.last_magic()
        self.assertEqual(finish["sub"], 109)

    def test_invisible_breaks_when_a_spell_cast_starts(self):
        """Casting is an action: Invisible drops, Sneak stays (retail)."""
        self.enter(100)
        mob = self.at_mob()
        self.session.add_effect(effects.INVISIBLE, duration=600)
        self.session.add_effect(effects.SNEAK, duration=600)
        self.session.queue.clear()
        self.as_caster(23)
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, mob.targid,
                         packets.ACTION_CAST_MAGIC, 23)
        self.session.cast_magic(bytes(packet), mob.targid)
        self.assertFalse(self.session.has_effect(effects.INVISIBLE))
        self.assertTrue(self.session.has_effect(effects.SNEAK))

    def test_a_missed_swing_still_breaks_sneak_and_invisible(self):
        """A miss is still an attack, so both stealth effects drop."""
        self.session.add_effect(effects.SNEAK, duration=600)
        self.session.add_effect(effects.INVISIBLE, duration=600)
        mob = self.claim_mob()
        self.session.queue.clear()
        self.session._apply_swing(mob, None, time.time(), {"miss": True, "damage": 0})
        self.assertFalse(self.session.has_effect(effects.INVISIBLE))
        self.assertFalse(self.session.has_effect(effects.SNEAK))

    def test_invisible_breaks_when_a_job_ability_is_used(self):
        """Activating an ability is an action too; Sneak is untouched."""
        self.enter(100)
        self.session.char["main_job"] = 5
        self.session.char["main_level"] = 99
        self.session.add_effect(effects.INVISIBLE, duration=600)
        self.session.add_effect(effects.SNEAK, duration=600)
        self.session.queue.clear()
        self.ability(247)  # Composure
        self.assertFalse(self.session.has_effect(effects.INVISIBLE))
        self.assertTrue(self.session.has_effect(effects.SNEAK))

    def test_invisible_breaks_when_the_player_is_hit(self):
        """Being attacked also drops Invisible; Sneak is not removed by damage."""
        self.session.add_effect(effects.INVISIBLE, duration=600)
        self.session.add_effect(effects.SNEAK, duration=600)
        self.session.queue.clear()
        mob = self.claim_mob()
        self.session.take_damage(10, mob)
        self.assertFalse(self.session.has_effect(effects.INVISIBLE))
        self.assertTrue(self.session.has_effect(effects.SNEAK))

    def test_an_interrupted_cast_does_not_break_invisible_before_it_starts(self):
        """A cast the server refuses (no MP) is not an action, so Invisible survives."""
        self.enter(100)
        mob = self.at_mob()
        self.session.add_effect(effects.INVISIBLE, duration=600)
        self.session.add_effect(effects.SNEAK, duration=600)
        self.session.queue.clear()
        self.as_caster(23)
        self.session.char["mp_current"] = 0
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, mob.targid,
                         packets.ACTION_CAST_MAGIC, 23)
        self.session.cast_magic(bytes(packet), mob.targid)
        self.assertIsNone(self.session.casting)
        self.assertTrue(self.session.has_effect(effects.INVISIBLE))
        self.assertTrue(self.session.has_effect(effects.SNEAK))

    def test_cast_finish_keeps_the_spell_animation(self):
        """The stopping motion is still the spell's client animation."""
        self.enter(100)
        mob = self.at_mob()
        self.cast(23, mob.targid)
        result = self.last_magic()
        self.assertEqual(result["sub"], 23)

    def test_petrified_monster_stops_walking_and_swinging(self):
        self.enter(100)
        mob = self.at_mob()
        mob.engaged_char_id = int(self.session.char["char_id"])
        mob.x, mob.z = self.session.pos[0] + 12, self.session.pos[2]  # out of reach
        mob.moving = True
        self.world.apply_mob_effect(
            mob, effects.for_spell("Breakga"), self.session, time.time())
        hp = int(mob.hp)
        with mock.patch.object(self.world, "mob_attack",
                               side_effect=AssertionError("petrified monsters cannot swing")):
            self.world._tick_mob(mob, [self.session], time.time())
        self.assertFalse(mob.moving)
        self.assertEqual(int(mob.hp), hp)

    def test_fire_still_nukes_from_its_spell_base(self):
        """The no-fake-damage rule must not turn real nukes back into 0."""
        self.enter(100)
        mob = self.at_mob()
        self.cast(144, mob.targid)
        result = self.last_magic()
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_DMG)
        self.assertGreater(result["value"], 0)
        self.assertEqual(result["sub"], 144)

    def test_a_swept_enfeebling_lands_without_inventing_damage(self):
        """Virus is in the generated table: it puts Plague up and still does 0 damage."""
        self.enter(100)
        mob = self.at_mob()
        hp = int(mob.hp)
        self.cast(256, mob.targid)  # Virus -> Plague
        result = self.last_magic()
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_ENFEEB)
        self.assertEqual(int(result["value"]), effects.PLAGUE)
        self.assertEqual(int(mob.hp), hp)

    def test_an_unimplemented_enfeebling_does_not_invent_damage(self):
        """A spell the effect table does not know still finishes without fake damage."""
        # Blue magic is outside the sweep (its durations are script variables, not table
        # columns), so it is the reliable source of an enemy spell with no effect entry.
        unmodelled = [row for row in self.db.all(
            "SELECT * FROM spells WHERE skill = ? AND (valid_targets & 4) != 0",
            (packets.SKILL_BLUE,)) if effects.for_spell(row["name"]) is None]
        self.assertTrue(unmodelled, "every blue spell is modelled; pick another path")
        self.enter(100)
        mob = self.at_mob()
        hp = int(mob.hp)
        self.cast(int(unmodelled[0]["id"]), mob.targid)
        result = self.last_magic()
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_NO_EFFECT)
        self.assertEqual(int(mob.hp), hp)

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

    def test_zero_hp_waits_for_a_raise_instead_of_returning_home(self):
        """A K.O. has no timer: six seconds (the old recovery) changes nothing."""
        self.session.char["hp_current"] = 0
        self.session.hit_zero_hp(time.time())
        self.assertEqual(float("inf"), self.session.dead_until)
        self.assertEqual(int(self.session.char["hp_current"]), 0)
        self.session.tick(time.time() + 6.5)
        self.session.tick(time.time() + 60.0)
        self.assertEqual(int(self.session.char["hp_current"]), 0)
        self.assertEqual(float("inf"), self.session.dead_until)
        self.assertIn("Wait for a raise", "\n".join(chats(self.session)))

    def test_raise_revives_a_fallen_party_member_at_ten_percent_hp(self):
        """Raise lands on a dead session, restores 10% HP and leaves it where it fell."""
        self.session.char.update({"mp": 1000, "mp_current": 1000})
        other = self.party_with(offset=4.0)
        other.char["hp"] = 1000
        other.char["hp_current"] = 0
        other.hit_zero_hp(time.time())
        self.assertEqual(float("inf"), other.dead_until)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Raise'")
        self.cast(int(row["id"]), other.targid, wait=16.0)
        self.assertEqual(int(other.char["hp_current"]), 100)
        self.assertEqual(other.dead_until, 0.0)
        self.assertIn("You have been raised", "\n".join(chats(other)))
        result = next(message for message in messages(other)
                      if message["category"] == packets.ACTION_CATEGORY_MAGIC_FINISH)
        self.assertEqual(result["target"], int(other.char["char_id"]))
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_RECOVERS_HP)
        self.assertEqual(result["value"], 100)

    def test_arise_restores_full_hp_and_grants_reraise(self):
        self.session.char.update({"mp": 1000, "mp_current": 1000})
        other = self.party_with(offset=4.0)
        other.char["hp"] = 1000
        other.char["hp_current"] = 0
        other.hit_zero_hp(time.time())
        row = self.db.one("SELECT * FROM spells WHERE name = 'Arise'")
        self.cast(int(row["id"]), other.targid, wait=13.0)
        self.assertEqual(int(other.char["hp_current"]), 1000)
        self.assertEqual(other.dead_until, 0.0)
        self.assertIn(effects.RERAISE, other.effect_state)
        self.assertGreater(float(other.effect(effects.RERAISE)["until"]), time.time())

    def test_a_poison_tick_cannot_count_a_death_twice(self):
        """A body on the ground takes no more DoT ticks, so death_count stays at one."""
        self.session.char.update({"hp": 100, "hp_current": 1})
        self.session.add_effect(effects.POISON, duration=60, tick=10)
        self.session.effect(effects.POISON)["next_tick"] = 0.0
        self.session.tick_player_effects(time.time())
        self.assertEqual(float("inf"), self.session.dead_until)
        self.session.tick_player_effects(time.time() + 3.0)
        row = self.db.one("SELECT death_count FROM characters WHERE id = ?",
                          (int(self.character["id"]),))
        self.assertEqual(int(row["death_count"]), 1)
        self.assertEqual(int(self.session.char["hp_current"]), 0)
        self.assertEqual(int(self.session.char["mp_current"]), 0)

    def test_home_point_return_revives_a_fallen_character(self):
        """Giving up on the raise is a zone change; it comes back at half vitals."""
        self.session.char.update({"home_zone": 235, "home_x": -344.0, "home_y": -10.0,
                                  "home_z": -155.0, "home_rot": 0,
                                  "hp": 1000, "hp_current": 0})
        self.session.zone = 107
        self.session.pos = [231.0, 2.5, -223.0, 60]
        self.session.hit_zero_hp(time.time())
        self.session.command(["home"])
        self.assertEqual(self.session.zone, 235)
        self.assertEqual(self.session.dead_until, 0.0)
        self.assertEqual(int(self.session.char["hp_current"]), 500)
        self.assertEqual(int(self.session.char["mp_current"]), int(self.session.char["mp"]) // 2)

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
        # The mob roamed for one beat while Sneak hid the player; put it back in range
        # for the second check (the original test assumed it stayed still).
        mob.x, mob.y, mob.z = self.session.pos[0], self.session.pos[1], self.session.pos[2]
        self.world._tick_mob(mob, [self.session], time.time() + 1)
        self.assertEqual(mob.engaged_char_id, int(self.session.char["char_id"]))

    def test_light_arts_puts_its_icon_on_the_bar(self):
        """A job ability's icon rides in 0x037, the same list the spell buffs use."""
        types = self.ability(211)
        self.assertIn(0x037, types)
        self.assertEqual(status_icon(self.session), effects.LIGHT_ARTS)

    def test_dark_arts_takes_the_light_arts_icon_down(self):
        """The two arts cancel each other, so only one icon is ever on the bar."""
        self.ability(211)
        self.ability(212)
        self.assertEqual(status_icon(self.session), effects.DARK_ARTS)
        self.assertNotIn(effects.LIGHT_ARTS, self.session.status_effects)

    def test_sublimation_puts_its_charging_icon_up(self):
        self.ability(233)
        self.assertEqual(status_icon(self.session), effects.SUBLIMATION)
        state = self.session.effect(effects.SUBLIMATION)
        self.assertGreater(float(state["until"]), time.time() + 7000)

    def test_a_stratagem_icon_wears_off_after_its_minute(self):
        self.ability(215)                                   # Penury
        self.assertEqual(status_icon(self.session), effects.PENURY)
        self.session.tick_player_effects(time.time() + 61)
        self.assertEqual(status_icon(self.session), -1)

    def test_grimoire_recast_merit_shortens_light_and_dark_arts(self):
        """5/5 Grimoire Recast takes 10 s off the arts' 60 s recast."""
        self.session.char.update(main_job=20, main_level=99)
        self.session._merit_counts = {merits.SCH_GRIMOIRE_RECAST: 5}
        started = time.time()
        self.ability(211)                                   # Light Arts, recast id 228
        self.assertAlmostEqual(self.session.ability_recasts[228] - started, 50.0,
                               delta=1.5)
        self.ability(212)                                   # Dark Arts, recast id 232
        self.assertAlmostEqual(self.session.ability_recasts[232] - started, 50.0,
                               delta=1.5)

    def test_max_sublimation_merit_raises_the_storage_cap(self):
        """300 base + 60 from the JP row + 50 from 5/5 Max Sublimation."""
        self.session.char.update(main_job=20, main_level=99)
        self.session._merit_counts = {merits.SCH_MAX_SUBLIMATION: 5}
        self.ability(233)
        state = self.session.effect(effects.SUBLIMATION)
        state["power"] = 409
        state["next_tick"] = 0.0
        self.session.char["hp"] = 2000
        self.session.char["hp_current"] = 2000
        self.session.tick_player_effects(time.time() + 1)
        self.assertEqual(int(state["power"]), 410)

    def test_group2_abilities_need_at_least_one_merit_rank(self):
        self.session.char.update(main_job=20, main_level=99)
        self.session._merit_counts = {}
        self.assertNotIn(240, self.session._job_ability_ids())
        self.ability(240)                                   # Altruism
        self.assertNotIn(effects.ALTRUISM, self.session.status_effects)
        self.session._merit_counts = {merits.SCH_ALTRUISM: 1}
        self.assertIn(240, self.session._job_ability_ids())
        self.ability(240)
        self.assertIn(effects.ALTRUISM, self.session.status_effects)

    def test_altruism_and_focalization_boost_the_matching_colour_only(self):
        """+10 at 1/5 and +5 a rank after that; the other colour does not spend it."""
        self.session.char.update(main_job=20, main_level=99)
        self.session._merit_counts = {merits.SCH_ALTRUISM: 5}
        self.ability(240)
        black = self.session._sch_next_spell_bonuses(
            {"name": "Stone", "skill": packets.SKILL_ELEMENTAL})
        self.assertEqual(black["macc"], 0)
        self.assertIn(effects.ALTRUISM, self.session.status_effects)
        white = self.session._sch_next_spell_bonuses(
            {"name": "Banish", "skill": packets.SKILL_DIVINE})
        self.assertEqual(white["macc"], 30)
        self.assertNotIn(effects.ALTRUISM, self.session.status_effects)
        self.session._merit_counts = {merits.SCH_FOCALIZATION: 5}
        self.session.ability_recasts.clear()      # the shared 1 s strategem recast
        self.ability(241)
        black = self.session._sch_next_spell_bonuses(
            {"name": "Stone", "skill": packets.SKILL_ELEMENTAL})
        self.assertEqual(black["macc"], 30)
        self.assertNotIn(effects.FOCALIZATION, self.session.status_effects)

    def test_a_cast_stores_the_next_spell_merit_bonus(self):
        """The cast path consumes Altruism/Tranquility and carries both onto the spell."""
        self.session.char.update(main_job=20, main_level=99, mp=1000, mp_current=1000)
        self.session._merit_counts = {merits.SCH_ALTRUISM: 5,
                                      merits.SCH_TRANQUILITY: 5}
        self.ability(240)
        self.session.ability_recasts.clear()
        self.ability(242)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Cure'")
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0, packets.ACTION_CAST_MAGIC,
                         int(row["id"]))
        self.session.cast_magic(bytes(packet), 0)
        self.assertIsNotNone(self.session.casting)
        self.assertEqual(self.session.casting["sch_macc"], 30)
        self.assertEqual(self.session.casting["sch_enmity"], 50)
        self.assertNotIn(effects.ALTRUISM, self.session.status_effects)
        self.assertNotIn(effects.TRANQUILITY, self.session.status_effects)

    def test_tranquility_and_equanimity_relieve_the_next_spell_enmity(self):
        self.session.char.update(main_job=20, main_level=99)
        self.session._merit_counts = {merits.SCH_TRANQUILITY: 5,
                                      merits.SCH_EQUANIMITY: 5}
        mob = self.claim_mob()
        mob.engaged_char_id = 0
        mine = int(self.session.char["char_id"])
        mob.enmity[mine] = 1000
        mob.enmity_ve[mine] = 400
        self.ability(242)                                   # Tranquility
        white = self.session._sch_next_spell_bonuses(
            {"name": "Banish", "skill": packets.SKILL_DIVINE})
        self.assertEqual(white["enmity"], 50)
        self.session._sch_relieve_hate(mob, {"sch_enmity": white["enmity"]})
        self.assertEqual(int(mob.enmity[mine]), 950)
        self.session.ability_recasts.clear()      # the shared 1 s strategem recast
        self.ability(243)                                   # Equanimity
        black = self.session._sch_next_spell_bonuses(
            {"name": "Stone", "skill": packets.SKILL_ELEMENTAL})
        self.assertEqual(black["enmity"], 50)
        self.session._sch_relieve_hate(mob, {"sch_enmity": black["enmity"]})
        self.assertEqual(int(mob.enmity[mine]), 900)

    def test_enlightenment_gives_int_mnd_and_is_spent_by_the_first_spell(self):
        self.session.char.update(main_job=20, main_level=99)
        self.session._merit_counts = {merits.SCH_ENLIGHTENMENT: 5}
        self.ability(244)
        state = self.session.effect(effects.ENLIGHTENMENT)
        self.assertEqual(int(state["mods"].get(mod.INT, 0)), 25)
        self.assertEqual(int(state["mods"].get(mod.MND, 0)), 25)
        bonus = self.session._sch_next_spell_bonuses(
            {"name": "Stone", "skill": packets.SKILL_ELEMENTAL})
        self.assertEqual((bonus["int"], bonus["mnd"]), (25, 25))
        self.assertNotIn(effects.ENLIGHTENMENT, self.session.status_effects)

    def test_group2_merit_values_at_rank_one(self):
        """The 1/5 values: Altruism +10, Tranquility -10, Enlightenment +5, storm +3."""
        self.session.char.update(main_job=20, main_level=99)
        self.session._merit_counts = {merits.SCH_ALTRUISM: 1,
                                      merits.SCH_TRANQUILITY: 1,
                                      merits.SCH_ENLIGHTENMENT: 1,
                                      merits.SCH_STORMSURGE: 1}
        self.ability(240)
        self.session.ability_recasts.clear()
        self.ability(242)
        self.session.ability_recasts.clear()
        self.ability(244)
        white = self.session._sch_next_spell_bonuses(
            {"name": "Banish", "skill": packets.SKILL_DIVINE})
        self.assertEqual(white["macc"], 10)
        self.assertEqual(white["enmity"], 10)
        self.assertEqual((white["int"], white["mnd"]), (5, 5))
        self.assertEqual(self.session._storm_mods("Firestorm"), {mod.STR: 3})
        self.assertEqual(self.session._storm_mods("Voidstorm"),
                         {mod.STR: 1, mod.DEX: 1, mod.VIT: 1, mod.AGI: 1,
                          mod.INT: 1, mod.MND: 1, mod.CHR: 1})

    def test_stormsurge_adds_the_storm_element_stat(self):
        self.session.char.update(main_job=20, main_level=99, mp=1000,
                                 mp_current=1000)
        self.session._merit_counts = {merits.SCH_STORMSURGE: 5}
        row = self.db.one("SELECT * FROM spells WHERE name = 'Firestorm'")
        self.cast(int(row["id"]))
        fire = effects.for_spell("Firestorm")
        state = self.session.effect(fire.effect)
        self.assertEqual(int(state["mods"].get(mod.STR, 0)), 7)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Voidstorm II'")
        self.cast(int(row["id"]))
        void = effects.for_spell("Voidstorm II")
        state = self.session.effect(void.effect)
        for stat in (mod.STR, mod.DEX, mod.VIT, mod.AGI, mod.INT, mod.MND, mod.CHR):
            self.assertEqual(int(state["mods"].get(stat, 0)), 3)

    def test_the_timer_packet_follows_the_icon_list(self):
        """0x063 type 9 is what the client counts down from; 0x037 alone leaves it blank."""
        self.ability(211)                                   # Light Arts, two hours
        self.session.queue.append(self.session.char_status())
        packed = self.packed()
        kinds = [kind for kind, _ in packed]
        self.assertIn(0x037, kinds)
        at = kinds.index(0x037)
        self.assertEqual(kinds[at + 1], 0x063)
        timers = packed[at + 1][1][4:]                     # skip the 4-byte sub-header
        # type 9, data size 196, then the icon and the timestamp in the first slot.
        self.assertEqual(struct.unpack_from("<HH", timers, 0), (9, 196))
        self.assertEqual(struct.unpack_from("<H", timers, 4)[0], effects.LIGHT_ARTS)
        stamp = struct.unpack_from("<I", timers, 68)[0]
        vana = int(time.time()) - VANA_EPOCH + int(self.world.clock)
        # The timestamp overflows 32 bits, which is what retail sends: the client expects
        # the wrapped value and corrects it.
        expected = ((vana + 7200) * 60) & 0xFFFFFFFF
        self.assertAlmostEqual(stamp, expected, delta=300)   # within five seconds

    def test_an_effect_that_never_wears_off_has_no_countdown(self):
        self.session.add_effect(effects.SNEAK)              # no duration
        self.session.queue.append(self.session.char_status())
        timers = next(payload for kind, payload in self.packed() if kind == 0x063)[4:]
        self.assertEqual(struct.unpack_from("<H", timers, 4)[0], effects.SNEAK)
        self.assertEqual(struct.unpack_from("<I", timers, 68)[0], 0x7FFFFFFF)

    def test_every_generated_spell_still_resolves_to_its_icon(self):
        """The sweep: the merge must not drop a single spell from the generated table."""
        for name, (effect_id, _kind, duration, _tick) in STATUS_SPELLS.items():
            spec = effects.for_spell(name)
            self.assertIsNotNone(spec, name)
            if name in effects.SWEPT_EXTRAS:
                continue                    # the long-tail table deliberately overrides it
            self.assertEqual(spec.effect, effect_id, name)
            self.assertNotEqual(effect_id, 0, name)
            self.assertGreater(duration, 0, name)

    def test_the_long_tail_spells_have_icons_too(self):
        """Retail spells newer than LandSandBoat's tables still get their icon."""
        for name, effect_id in (("Poison IV", effects.POISON), ("Poison V", effects.POISON),
                                ("Endark", effects.ENDARK), ("Klimaform", effects.KLIMAFORM),
                                ("Foe Requiem VIII", effects.REQUIEM),
                                ("Armys Paeon VII", effects.PAEON)):
            spec = effects.for_spell(name)
            self.assertIsNotNone(spec, name)
            self.assertEqual(spec.effect, effect_id, name)
            self.assertGreater(spec.duration, 0, name)

    def test_the_second_tier_buffs_have_their_icons(self):
        """The tier-II/merit lines LSB's spell tables never listed still put icons up."""
        expected = {
            "Windstorm II": 591, "Firestorm II": 589, "Hailstorm II": 590,
            "Sandstorm II": 592, "Thunderstorm II": 593, "Rainstorm II": 594,
            "Aurorastorm II": 595, "Voidstorm II": 596,
            "Fire Carol II": 216, "Ice Carol II": 216, "Wind Carol II": 216,
            "Earth Carol II": 216, "Lightning Carol II": 216, "Water Carol II": 216,
            "Light Carol II": 216, "Dark Carol II": 216,
            "Ltng Threnody II": 217,
            "Enlight": 274, "Enlight II": 274, "Endark II": 288,
            "Reraise II": 113, "Reraise III": 113, "Reraise IV": 113,
            "Adloquium": 170, "Animus Augeo": 289, "Animus Minuo": 291,
            "Chocobo Hum": 204, "Jesters Operetta": 206, "Devotee Serenade": 208,
            "Cactuar Fugue": 211, "Moogle Rhapsody": 212, "Protected Aria": 213,
        }
        for name, effect_id in expected.items():
            spec = effects.for_spell(name)
            self.assertIsNotNone(spec, name)
            self.assertEqual(spec.effect, effect_id, name)
            self.assertGreater(spec.duration, 0, name)

    def test_every_self_or_party_buff_spell_puts_an_icon_up(self):
        """No enhancing, divine, healing or song buff may finish with no status icon.

        Heals, status cures and teleports are the only self/party spells that carry no
        icon in retail; anything else in these schools has to resolve to a SpellEffect.
        This catches the next Windstorm II: a spell the client can cast but the generated
        LSB table does not list.
        """
        no_icon = {
            "Cure", "Cure II", "Cure III", "Cure IV", "Cure V", "Cure VI",
            "Curaga", "Curaga II", "Curaga III", "Curaga IV", "Curaga V",
            "Cura", "Cura II", "Cura III", "Full Cure",
            "Poisona", "Paralyna", "Blindna", "Silena", "Stona", "Viruna", "Cursna",
            "Erase", "Sacrifice", "Esuna",
            "Recall-jugner", "Recall-pashh", "Recall-meriph",
            "Teleport-yhoat", "Teleport-altep", "Teleport-holla", "Teleport-dem",
            "Teleport-mea", "Teleport-vahzl", "Escape",
        }
        rows = self.db.all(
            "SELECT name FROM spells WHERE skill IN (?, ?, ?, ?) "
            "AND (valid_targets & 3) != 0",
            (packets.SKILL_DIVINE, packets.SKILL_HEALING,
             packets.SKILL_ENHANCING, packets.SKILL_SINGING))
        missing = [row["name"] for row in rows
                   if row["name"] not in no_icon
                   and effects.for_spell(row["name"]) is None]
        self.assertEqual(missing, [])

    def test_windstorm_ii_puts_an_icon_up_and_counts_down(self):
        """Windstorm II is the screenshot's bug: the cast finished with no icon or timer."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Windstorm II'")
        self.cast(int(row["id"]))
        self.assertEqual(status_icon(self.session), 591)
        state = self.session.effect(591)
        self.assertIsNotNone(state)
        self.assertGreater(effect_seconds(state), 160.0)     # 180 s minus the 10 s wait
        # The icon list alone draws an icon with an empty countdown; 0x063 type 9 must
        # follow it with this slot's Vanadiel timestamp.
        self.session.queue.clear()
        self.session.queue.append(self.session.char_status())
        packed = self.packed()
        kinds = [kind for kind, _ in packed]
        at = kinds.index(0x037)
        self.assertEqual(kinds[at + 1], 0x063)
        timers = packed[at + 1][1][4:]
        self.assertEqual(struct.unpack_from("<HH", timers, 0), (9, 196))
        self.assertEqual(struct.unpack_from("<H", timers, 4)[0], 591)
        stamp = struct.unpack_from("<I", timers, 68)[0]
        self.assertNotEqual(stamp, 0x7FFFFFFF)

    def test_regen_v_puts_its_icon_up_and_ticks(self):
        """Regen IV and V used to fall through: no icon, no ticks."""
        self.session.char["mp_current"] = 600
        row = self.db.one("SELECT * FROM spells WHERE name = 'Regen V'")
        self.cast(int(row["id"]))
        self.assertEqual(status_icon(self.session), effects.REGEN)
        state = self.session.effect(effects.REGEN)
        self.assertEqual(int(state["tick"]), 40)
        # Give the tick somewhere to go and run the timer just past its next beat.
        self.session.char["hp"] = 1200
        self.session.char["hp_current"] = 800
        self.session.tick_player_effects(float(state["next_tick"]) + 0.1)
        self.assertEqual(int(self.session.char["hp_current"]), 840)

    def test_light_arts_extends_regen_v_and_its_tick(self):
        """Regen V is 60 s + 48 s Light Arts + 60 s maxed JP, at 40 + 24 HP per tick."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        self.ability(211)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Regen V'")
        self.cast(int(row["id"]))
        state = self.session.effect(effects.REGEN)
        self.assertAlmostEqual(effect_seconds(state), 168.0, delta=1.0)
        self.assertEqual(int(state["tick"]), 64)

    def test_perpetuance_extends_regen_v_and_is_consumed(self):
        """The stratagem doubles the next white enhancing spell, then comes down."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        self.ability(211)
        self.ability(316)
        self.assertIn(effects.PERPETUANCE, self.session.status_effects)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Regen V'")
        self.cast(int(row["id"]))
        state = self.session.effect(effects.REGEN)
        self.assertAlmostEqual(effect_seconds(state), 336.0, delta=1.0)
        self.assertNotIn(effects.PERPETUANCE, self.session.status_effects)

    def test_stpc_refresh_lands_on_the_selected_party_member(self):
        """The client's party sub-target must reach the server's cast, not fall back to self."""
        self.session.char.update(main_job=5, main_level=99, mp_current=600)
        other = self.party_with(offset=4.0)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Refresh III'")
        self.cast(int(row["id"]), other.targid)
        self.assertIn(effects.REFRESH, other.effect_state)
        self.assertNotIn(effects.REFRESH, self.session.effect_state)
        result = next(message for message in messages(other)
                      if message["category"] == packets.ACTION_CATEGORY_MAGIC_FINISH)
        self.assertEqual(result["target"], int(other.char["char_id"]))
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_GAIN_EFFECT)
        self.assertEqual(result["value"], effects.REFRESH)
        self.assertLess(int(self.session.char["mp_current"]), 600)

    def test_stpc_cure_heals_the_selected_party_member(self):
        """Cure selected on a teammate heals them and leaves the caster's HP alone."""
        self.session.char.update(main_job=5, main_level=99, mp_current=600)
        self.session.char["hp_current"] = 300
        other = self.party_with(offset=4.0)
        other.char["hp"] = 500
        other.char["hp_current"] = 50
        row = self.db.one("SELECT * FROM spells WHERE name = 'Cure IV'")
        self.cast(int(row["id"]), other.targid)
        self.assertGreater(int(other.char["hp_current"]), 50)
        self.assertEqual(int(self.session.char["hp_current"]), 300)
        result = next(message for message in messages(other)
                      if message["category"] == packets.ACTION_CATEGORY_MAGIC_FINISH)
        self.assertEqual(result["target"], int(other.char["char_id"]))
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_RECOVERS_HP)

    def test_hastega_reaches_nearby_party_members(self):
        """Hastega is self-centered in the client data but must spread to the party."""
        self.session.char.update(main_job=5, main_level=99, mp_current=600)
        other = self.party_with(offset=4.0)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Hastega'")
        self.cast(int(row["id"]))
        for session in (self.session, other):
            self.assertIn(effects.HASTE, session.effect_state)
        targets = [message["target"] for message in messages(self.session)
                   if message["message"] == packets.MESSAGE_MAGIC_GAIN_EFFECT]
        self.assertIn(int(other.char["char_id"]), targets)
        self.assertIn(mod.HASTE_MAGIC, effects.for_spell("Hastega").mods)

    def test_hastega_skips_a_party_member_out_of_range(self):
        self.session.char.update(main_job=5, main_level=99, mp_current=600)
        other = self.party_with(offset=20.0)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Hastega'")
        self.cast(int(row["id"]))
        self.assertIn(effects.HASTE, self.session.effect_state)
        self.assertNotIn(effects.HASTE, other.effect_state)

    def test_accession_spreads_regen_v_across_the_party(self):
        """Accession turns the next white enhancing spell into a party-wide buff."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        other = self.party_with(offset=4.0)
        self.ability(211)
        self.ability(218)
        self.assertIn(effects.ACCESSION, self.session.status_effects)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Regen V'")
        self.cast(int(row["id"]))
        for session in (self.session, other):
            self.assertIn(effects.REGEN, session.effect_state)
            state = session.effect(effects.REGEN)
            self.assertAlmostEqual(effect_seconds(state), 168.0, delta=1.0)
            self.assertEqual(int(state["tick"]), 64)
        self.assertIn(effects.REGEN, self.session.status_effects)
        self.assertEqual(status_icon(other), effects.REGEN)
        self.assertNotIn(effects.ACCESSION, self.session.status_effects)
        # Each recipient's client gets a gain-effect result addressed to it.
        targets = [message["target"] for message in messages(self.session)
                   if message["message"] == packets.MESSAGE_MAGIC_GAIN_EFFECT]
        self.assertIn(int(other.char["char_id"]), targets)

    def test_regen_v_without_accession_stays_on_the_caster(self):
        """The party-wide result is Accession's doing, not every Regen's."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        other = self.party_with(offset=4.0)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Regen V'")
        self.cast(int(row["id"]))
        self.assertIn(effects.REGEN, self.session.effect_state)
        self.assertNotIn(effects.REGEN, other.effect_state)

    def test_accession_skips_a_party_member_out_of_range(self):
        """Only the party inside the spell's area gets the buff."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        other = self.party_with(offset=20.0)
        self.ability(211)
        self.ability(218)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Regen V'")
        self.cast(int(row["id"]))
        self.assertIn(effects.REGEN, self.session.effect_state)
        self.assertNotIn(effects.REGEN, other.effect_state)
        self.assertNotIn(effects.ACCESSION, self.session.status_effects)

    def test_a_black_enhancing_spell_does_not_spend_accession(self):
        """Only a white enhancing spell consumes the stratagem."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        self.ability(211)
        self.ability(218)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Blaze Spikes'")
        self.cast(int(row["id"]))
        self.assertIn(effects.ACCESSION, self.session.status_effects)

    def test_accession_leaves_haste_alone(self):
        """Retail's exception: Haste keeps the stratagem and does not spread."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        other = self.party_with(offset=4.0)
        self.ability(211)
        self.ability(218)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Haste'")
        self.cast(int(row["id"]))
        self.assertIn(effects.HASTE, self.session.effect_state)
        self.assertNotIn(effects.HASTE, other.effect_state)
        self.assertIn(effects.ACCESSION, self.session.status_effects)

    def test_tabula_rasa_replaces_the_light_arts_regen_bonus(self):
        """Tabula Rasa's +36 HP/tick and +72 s overwrite Light Arts, they do not stack."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        self.ability(210)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Regen V'")
        self.cast(int(row["id"]))
        state = self.session.effect(effects.REGEN)
        self.assertAlmostEqual(effect_seconds(state), 192.0, delta=1.0)
        self.assertEqual(int(state["tick"]), 76)

    def test_regen_duration_gear_feeds_the_timer(self):
        """The cape's flat seconds and enhancing-duration percent both land."""
        self.session.char.update(main_job=20, main_level=99, mp_current=600)
        self.ability(211)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Regen V'")
        gear = {mod.ENH_MAGIC_DURATION: 20, mod.REGEN_DURATION: 15}
        with mock.patch.object(self.session, "combat_mods", return_value=gear):
            self.cast(int(row["id"]))
        state = self.session.effect(effects.REGEN)
        self.assertAlmostEqual(effect_seconds(state), (60 + 15 + 48 + 60) * 1.2, delta=1.0)

    def test_food_mods_reach_the_stat_sheet_and_expire(self):
        """Food is a modifier source, not just an icon: INT/MP move the same sheet."""
        self.service.add_item(int(self.session.char["id"]), 4413, 1)  # Apple Pie
        container, slot = self.slot_of(4413)
        before = self.session.stat_sheet()
        self.session.queue.clear()
        self.session.item_use(item_use_packet(slot, container))
        self.assertEqual(int(self.session.food["item_id"]), 4413)
        self.assertIn(effects.FOOD, self.session.status_effects)
        self.assertEqual(status_icon(self.session), effects.FOOD)
        during = self.session.stat_sheet()
        self.assertEqual(during.attributes["int"], before.attributes["int"] + 3)
        self.assertEqual(during.max_mp, before.max_mp + 25)
        self.assertIn("You eat the Apple Pie.", chats(self.session))
        # The consumed slot is emptied for the client, which redraws it from 0x020.
        self.assertIsNone(self.db.one(
            "SELECT 1 FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
            (int(self.session.char["id"]), container, slot)))
        item_updates = [message for message in self.session.queue
                        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x020]
        self.assertEqual(struct.unpack_from("<H", item_updates[0], 4 + 8)[0], 0)
        self.assertEqual(item_updates[0][4 + 10], container)
        self.assertEqual(item_updates[0][4 + 11], slot)
        self.session.tick_player_effects(time.time() + 1801)
        self.assertEqual(int(self.session.food["item_id"]), 0)
        self.assertNotIn(effects.FOOD, self.session.status_effects)
        after = self.session.stat_sheet()
        self.assertEqual(after.attributes["int"], before.attributes["int"])
        self.assertEqual(after.max_mp, before.max_mp)

    def test_eating_plays_the_item_finish_animation(self):
        """The eat motion is an S2C 0x028 ItemFinish; no action meant no animation."""
        self.service.add_item(int(self.session.char["id"]), 4413, 1)
        container, slot = self.slot_of(4413)
        self.session.queue.clear()
        self.session.item_use(item_use_packet(slot, container))
        results = [message for message in messages(self.session)
                   if message["category"] == packets.ACTION_CATEGORY_ITEM_FINISH]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], 4413)
        self.assertEqual(results[0]["kind"], 1)   # retail's item-finish result kind
        self.assertEqual(results[0]["sub"], 26)  # Apple Pie's eating animation
        self.assertEqual(results[0]["target"], int(self.session.char["char_id"]))

    def test_item_use_reads_the_slot_not_the_item_num(self):
        """0x037 carries the slot; 0x08 is ItemNum, which the client always sends as 0."""
        self.service.add_item(int(self.session.char["id"]), 4413, 1)
        self.service.add_item(int(self.session.char["id"]), 2971, 1)  # a ninja tool
        container, slot = self.slot_of(2971)
        self.session.queue.clear()
        # The item id in the ItemNum field must not turn the tool into an apple pie.
        self.session.item_use(item_use_packet(slot, container, item_num=4413))
        self.assertEqual(int(self.session.food["item_id"]), 0)
        self.assertNotIn(effects.FOOD, self.session.status_effects)
        row = self.db.one(
            "SELECT quantity FROM char_inventory WHERE character_id = ? "
            "AND container = ? AND slot = ?",
            (int(self.session.char["id"]), container, slot))
        self.assertEqual(int(row["quantity"]), 1)

    def test_item_use_consumes_the_clicked_slot(self):
        """Two stacks: the one the player clicked loses one, the other is untouched."""
        for slot, quantity in ((70, 5), (71, 7)):
            self.db.execute(
                "INSERT OR REPLACE INTO char_inventory "
                "(character_id, container, slot, item_id, quantity) VALUES (?, 0, ?, 4413, ?)",
                (int(self.session.char["id"]), slot, quantity))
        self.session.queue.clear()
        self.session.item_use(item_use_packet(71, 0))
        stacks = {int(row["slot"]): int(row["quantity"]) for row in self.db.all(
            "SELECT slot, quantity FROM char_inventory "
            "WHERE character_id = ? AND container = 0 AND item_id = 4413",
            (int(self.session.char["id"]),))}
        self.assertEqual(stacks, {70: 5, 71: 6})

    def test_item_use_works_from_a_wardrobe(self):
        """Category can be a wardrobe, not only inventory 0."""
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, 8, 1, 4413, 1)",
            (int(self.session.char["id"]),))
        self.session.queue.clear()
        self.session.item_use(item_use_packet(1, 8))
        self.assertEqual(int(self.session.food["item_id"]), 4413)
        item_update = next(message for message in self.session.queue
                           if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x020)
        self.assertEqual(item_update[4 + 10], 8)
        self.assertEqual(item_update[4 + 11], 1)

    def test_item_use_from_the_menu_without_sync_is_dispatched(self):
        """A bag-menu request can arrive with sync 0; 0x037 must not be dropped."""
        self.service.add_item(int(self.session.char["id"]), 4413, 1)
        container, slot = self.slot_of(4413)
        header = bytearray(28)
        struct.pack_into("<H", header, 0, 0x037)
        self.session.client_id = 0
        self.session.queue.clear()
        self.session.parse(header, item_use_packet(slot, container))
        self.assertEqual(int(self.session.food["item_id"]), 4413)
        self.assertIn(effects.FOOD, self.session.status_effects)

    def test_enfeebling_duration_and_potency_gear_land_on_the_mob(self):
        self.enter(100)
        mob = self.at_mob()
        row = self.db.one("SELECT * FROM spells WHERE name = 'Dia'")
        gear = {mod.ENF_MAG_DURATION: 50, mod.ENF_MAG_POTENCY: 50}
        with mock.patch.object(self.session, "combat_mods", return_value=gear):
            self.cast(int(row["id"]), targid=int(mob.targid))
        state = mob.effect_state[effects.DIA]
        started = float(state["next_tick"]) - 3.0
        self.assertAlmostEqual(float(state["until"]) - started, 90.0, delta=1.0)
        self.assertEqual(int(state["potency"]), 15)

    def test_noctohelix_hits_once_then_repeats_that_hit_every_ten_seconds(self):
        """The old table read HELIX's ten-second interval as ten damage per tick."""
        self.enter(100)
        mob = self.at_mob()
        mob.hp_max = mob.hp = 5000
        self.session.char.update(main_job=20, main_level=99)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Noctohelix'")
        started = time.time()
        self.cast(int(row["id"]), mob.targid)
        state = mob.effect_state[effects.HELIX]
        result = self.last_magic()
        damage = int(result["value"])
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_DMG)
        self.assertGreater(damage, 10)                  # a real opening nuke
        self.assertEqual(int(state["tick"]), damage)    # the DoT repeats it
        self.assertEqual(float(state["tick_interval"]), 10.0)
        self.assertEqual(int(state["tier"]), 1)
        # 99 Scholar: the DoT lasts 90 s, and cast() resolved the spell 10 s in.
        self.assertAlmostEqual(float(state["until"]) - started, 100.0, delta=1.5)
        # The first tock is 1-10 s after the cast, not on the next three-second beat.
        first_tock = float(state["next_tick"]) - started
        self.assertGreaterEqual(first_tock, 10.9)
        self.assertLessEqual(first_tock, 20.5)
        before = int(mob.hp)
        state["next_tick"] = 0.0
        self.session.queue.clear()
        self.world.tick_mob_effects(mob, [self.session], time.time())
        self.assertEqual(int(mob.hp), before - damage)
        # DoT ticks are silent: the HP update carries the damage, and no 0x028 action
        # means the caster never plays a casting animation for a tick.
        self.assertFalse(any(message["message"] == packets.MESSAGE_TARGET_TAKES_DAMAGE
                             for message in messages(self.session)))
        self.assertFalse(any(message["message"] == packets.MESSAGE_TARGET_TAKES_DAMAGE
                             for message in battle_messages(self.session)))
        self.assertAlmostEqual(float(state["next_tick"]) - time.time(), 10.0, delta=1.0)

    def test_a_scholar_subjob_helix_lasts_sixty_seconds(self):
        """/SCH caps at level 49, so it reaches the 60 s tier and no further."""
        self.enter(100)
        mob = self.at_mob()
        mob.hp_max = mob.hp = 5000
        self.session.char.update(main_job=1, main_level=99, sub_job=20, sub_level=49)
        started = time.time()
        row = self.db.one("SELECT * FROM spells WHERE name = 'Noctohelix'")
        self.cast(int(row["id"]), mob.targid)
        state = mob.effect_state[effects.HELIX]
        self.assertAlmostEqual(float(state["until"]) - started, 70.0, delta=1.5)

    def test_helix_magic_merit_raises_only_helix_damage(self):
        """Helix Magic Acc./Atk. is +3 M.Acc and +2 MAB a rank, Helix only."""
        self.enter(100)
        mob = self.at_mob()
        self.session.char.update(main_job=20, main_level=99)
        row = dict(self.db.one("SELECT * FROM spells WHERE name = 'Noctohelix'"))
        spec = effects.for_spell("Noctohelix")
        base = self.session._cast_numbers(row, spec, mob, healing=False)
        self.session._merit_counts = {merits.SCH_HELIX_MAGIC: 5}
        boosted = self.session._cast_numbers(row, spec, mob, healing=False)
        self.assertGreater(int(boosted["amount"]), int(base["amount"]))
        self.assertGreaterEqual(float(boosted["resist"]), float(base["resist"]))
        # A non-Helix spell does not inherit the row.
        nuke = dict(self.db.one("SELECT * FROM spells WHERE name = 'Stone'"))
        stone = effects.for_spell("Stone")
        plain = self.session._cast_numbers(nuke, stone, mob, healing=False)
        self.session._merit_counts = {}
        unmerited = self.session._cast_numbers(nuke, stone, mob, healing=False)
        self.assertEqual(int(plain["amount"]), int(unmerited["amount"]))

    def test_modus_veritas_doubles_the_helix_tick_and_halves_its_life(self):
        self.enter(100)
        mob = self.at_mob()
        mob.hp_max = mob.hp = 50000
        self.session.char.update(main_job=20, main_level=99)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Noctohelix'")
        self.cast(int(row["id"]), mob.targid)
        state = mob.effect_state[effects.HELIX]
        tick = int(state["tick"])
        before = float(state["until"])
        self.session.engaged_id = int(mob.id)
        self.session._merit_counts = {}
        self.ability(214)
        self.assertEqual(int(state["tick"]), tick * 2 + 60)
        now = time.time()
        self.assertAlmostEqual(float(state["until"]) - now, (before - now) * 0.5,
                               delta=1.5)

    def test_modus_veritas_duration_merit_softens_the_penalty(self):
        self.enter(100)
        mob = self.at_mob()
        mob.hp_max = mob.hp = 50000
        self.session.char.update(main_job=20, main_level=99)
        row = self.db.one("SELECT * FROM spells WHERE name = 'Noctohelix'")
        self.cast(int(row["id"]), mob.targid)
        state = mob.effect_state[effects.HELIX]
        before = float(state["until"])
        self.session.engaged_id = int(mob.id)
        self.session._merit_counts = {merits.SCH_MODUS_VERITAS_DURATION: 5}
        self.ability(214)
        now = time.time()
        self.assertAlmostEqual(float(state["until"]) - now, (before - now) * 0.75,
                               delta=1.5)

    def test_a_tier_one_helix_does_not_replace_a_tier_two_helix(self):
        """Retail: Helix II overwrites any Helix, but Helix 1 only overwrites Helix 1."""
        self.enter(100)
        mob = self.at_mob()
        mob.hp_max = mob.hp = 5000
        self.session.char.update(main_job=20, main_level=99)
        two = self.db.one("SELECT * FROM spells WHERE name = 'Noctohelix II'")
        one = self.db.one("SELECT * FROM spells WHERE name = 'Noctohelix'")
        self.cast(int(two["id"]), mob.targid)
        state = mob.effect_state[effects.HELIX]
        power = int(state["tick"])
        self.assertEqual(int(state["tier"]), 2)
        hp = int(mob.hp)
        self.cast(int(one["id"]), mob.targid)
        # The tier-1 opening hit still lands, but the stronger DoT stays.
        self.assertLess(int(mob.hp), hp)
        self.assertIs(mob.effect_state[effects.HELIX], state)
        self.assertEqual(int(state["tick"]), power)
        self.assertEqual(int(state["tier"]), 2)


class DarkKnightAbilityTest(unittest.TestCase):
    """The two DRK abilities that were icons only but carry real combat mods."""

    def test_last_resort_is_attack_up_defense_down(self):
        entry = effects.ABILITY_EFFECTS[51]
        self.assertEqual(entry.effect, effects.LAST_RESORT)
        self.assertEqual(entry.duration, 180.0)
        self.assertEqual(entry.mods[mod.ATT_PERCENT], 25)
        self.assertEqual(entry.mods[mod.DEF_PERCENT], -25)

    def test_souleater_adds_accuracy_while_the_hit_bonus_is_in_player_attack(self):
        entry = effects.ABILITY_EFFECTS[49]
        self.assertEqual(entry.effect, effects.SOULEATER)
        self.assertEqual(entry.duration, 60.0)
        self.assertEqual(entry.mods[mod.ACC], 25)


class EnhancingDurationTest(unittest.TestCase):
    """The duration formula itself, away from the session and the database."""

    def spec(self, name: str = "Regen V"):
        spec = effects.for_spell(name)
        self.assertIsNotNone(spec, name)
        return spec

    def test_light_arts_is_forty_eight_seconds_at_ninety_nine(self):
        self.assertEqual(
            effects.buff_duration(self.spec(), main_job=20, main_level=99, mods={},
                                  light_arts=True, enhancing=True),
            108.0)
        self.assertEqual(
            effects.regen_tick(self.spec(), main_job=20, main_level=99, mods={},
                               light_arts=True),
            64)

    def test_light_arts_scales_with_level(self):
        for level, seconds, tick in ((10, 0.0, 0), (49, 18.0, 9), (50, 24.0, 12),
                                     (89, 42.0, 21), (90, 48.0, 24), (99, 48.0, 24)):
            spec = self.spec()
            self.assertEqual(
                effects.buff_duration(spec, main_job=20, main_level=level, mods={},
                                      light_arts=True, enhancing=True),
                60.0 + seconds, level)
            self.assertEqual(
                effects.regen_tick(spec, main_job=20, main_level=level, mods={},
                                   light_arts=True),
                40 + tick, level)

    def test_a_scholar_sub_job_gets_no_light_arts_regen_bonus(self):
        self.assertEqual(
            effects.buff_duration(self.spec(), main_job=3, main_level=99, mods={},
                                  light_arts=True, enhancing=True),
            60.0)

    def test_flat_seconds_and_percent_gear_apply_before_perpetuance(self):
        spec = self.spec()
        mods = {mod.REGEN_DURATION: 15, mod.ENH_MAGIC_DURATION: 20}
        self.assertAlmostEqual(
            effects.buff_duration(spec, main_job=20, main_level=99, mods=mods,
                                  light_arts=True, enhancing=True),
            147.6)
        self.assertAlmostEqual(
            effects.buff_duration(spec, main_job=20, main_level=99, mods=mods,
                                  light_arts=True, enhancing=True,
                                  perpetuance=True, white_enhancing=True),
            147.6 * 2.0)

    def test_listed_and_augment_duration_are_separate_multipliers(self):
        """BG-wiki's formula multiplies listed gear and augments, it does not add them."""
        spec = self.spec()
        mods = {mod.ENH_MAGIC_DURATION: 20, mod.ENH_MAGIC_DURATION_AUGMENT: 30}
        self.assertAlmostEqual(
            effects.buff_duration(spec, main_job=20, main_level=99, mods=mods,
                                  light_arts=True, enhancing=True),
            (60 + 48) * 1.20 * 1.30)

    def test_light_arts_job_points_add_duration_but_not_potency(self):
        spec = self.spec()
        self.assertEqual(
            effects.buff_duration(spec, main_job=20, main_level=99, mods={},
                                  light_arts=True, light_arts_jp_rank=20,
                                  enhancing=True),
            168.0)
        self.assertEqual(
            effects.buff_duration(spec, main_job=20, main_level=99, mods={},
                                  tabula_rasa=True, light_arts_jp_rank=20,
                                  enhancing=True),
            192.0)
        self.assertEqual(
            effects.regen_tick(spec, main_job=20, main_level=99, mods={},
                               light_arts=True),
            64)

    def test_flat_regen_potency_adds_after_the_multiplier(self):
        """Bookworm's and the Telchine augments are flat HP, not a second percent."""
        spec = self.spec()
        mods = {mod.REGEN_MULTIPLIER: 25, mod.REGEN_POTENCY: 75}
        self.assertEqual(
            effects.regen_tick(spec, main_job=20, main_level=99, mods=mods,
                               light_arts=True),
            149)  # ceil(40 * 1.25) + 75 + 24

    def test_the_retail_max_duration_set(self):
        """The Community Scholar Guide's max set: Musa, four Telchine slots, Lugh."""
        spec = self.spec()
        mods = {
            mod.REGEN_DURATION: 27,             # Lugh 15 + Telchine body 12
            mod.ENH_MAGIC_DURATION: 30,         # Musa 20 + Embla 10
            mod.ENH_MAGIC_DURATION_AUGMENT: 40,  # four Telchine +10 augments
            mod.PERPETUANCE: 6500,              # Arbatel Bracers +3
        }
        common = dict(main_job=20, main_level=99, mods=mods,
                      light_arts_jp_rank=20, enhancing=True,
                      perpetuance=True, white_enhancing=True)
        self.assertAlmostEqual(
            effects.buff_duration(spec, light_arts=True, **common), 940.485, places=2)
        self.assertAlmostEqual(
            effects.buff_duration(spec, tabula_rasa=True, **common), 1056.237, places=2)

    def test_bracers_raise_the_perpetuance_multiplier(self):
        spec = self.spec()
        mods = {mod.PERPETUANCE: 6500}
        self.assertAlmostEqual(
            effects.buff_duration(spec, main_job=20, main_level=99, mods=mods,
                                  light_arts=True, enhancing=True,
                                  perpetuance=True, white_enhancing=True),
            108.0 * 2.65)

    def test_black_enhancing_spikes_ignore_perpetuance(self):
        self.assertFalse(effects.is_white_enhancing("Blaze Spikes"))
        self.assertTrue(effects.is_white_enhancing("Regen V"))

    def test_ninjutsu_ignores_enhancing_duration_and_perpetuance(self):
        spec = self.spec("Utsusemi Ichi")
        mods = {mod.ENH_MAGIC_DURATION: 50}
        self.assertEqual(
            effects.buff_duration(spec, main_job=20, main_level=99, mods=mods,
                                  enhancing=False, perpetuance=True,
                                  white_enhancing=False),
            spec.duration)

    def test_tabula_rasa_overwrites_light_arts(self):
        spec = self.spec()
        self.assertEqual(
            effects.buff_duration(spec, main_job=20, main_level=99, mods={},
                                  light_arts=True, tabula_rasa=True, enhancing=True),
            132.0)
        self.assertEqual(
            effects.regen_tick(spec, main_job=20, main_level=99, mods={},
                               light_arts=True, tabula_rasa=True),
            76)

    def test_regen_line_base_durations_and_ticks(self):
        expected = {
            "Regen": (75.0, 5), "Regen II": (60.0, 12), "Regen III": (60.0, 20),
            "Regen IV": (60.0, 30), "Regen V": (60.0, 40),
        }
        for name, (duration, tick) in expected.items():
            spec = self.spec(name)
            self.assertEqual(float(spec.duration), duration, name)
            self.assertEqual(int(spec.tick), tick, name)

    def test_perpetuance_gear_requires_the_hands(self):
        """No bracers means the base 2.0x, not the client's 2.65x tooltip."""
        self.assertEqual(effects.perpetuance_multiplier({}), 2.0)
        self.assertEqual(effects.perpetuance_multiplier({mod.PERPETUANCE: 6500}), 2.65)

    def test_enfeebling_duration_and_potency_gear(self):
        slow = self.spec("Slow")
        self.assertEqual(
            effects.debuff_duration(slow, skill=effects.ENFEEBLING_SKILL,
                                    mods={mod.ENF_MAG_DURATION: 50}),
            270.0)
        paralyze = self.spec("Paralyze")
        self.assertEqual(
            effects.debuff_potency(paralyze, skill=effects.ENFEEBLING_SKILL,
                                   mods={mod.ENF_MAG_POTENCY: 50}),
            30)
        # Dark Magic has its own duration line and does not use the enfeebling one.
        self.assertEqual(
            effects.debuff_duration(slow, skill=effects.DARK_MAGIC_SKILL,
                                    mods={mod.ENF_MAG_DURATION: 50}),
            float(slow.duration))
        self.assertEqual(
            effects.debuff_duration(slow, skill=effects.NINJUTSU_SKILL,
                                    mods={mod.NINJUTSU_DURATION: 60}),
            float(slow.duration) + 60.0)

    def test_cure_potency_gear(self):
        self.assertEqual(effects.healing_amount(100, {mod.CURE_POTENCY: 50}), 150)
        self.assertEqual(effects.healing_amount(100, {mod.CURE_POTENCY_II: 30}), 130)
        self.assertEqual(effects.healing_amount(100, {mod.CURE_POTENCY_BONUS: 15}), 115)
        self.assertEqual(
            effects.healing_amount(100, {}, {mod.CURE_POTENCY_RCVD: 10}), 110)
        # Both gear caps apply: 60% is clamped to 50% and 40% to 30%.
        self.assertEqual(
            effects.healing_amount(100, {mod.CURE_POTENCY: 60, mod.CURE_POTENCY_II: 40}),
            180)

    def test_refresh_and_stoneskin_gear(self):
        refresh = self.spec("Refresh")
        self.assertEqual(
            effects.buff_tick(refresh, main_job=20, main_level=99,
                              mods={mod.ENHANCES_REFRESH: 2}),
            5)
        stoneskin = self.spec("Stoneskin")
        self.assertEqual(effects.buff_power(stoneskin, {mod.STONESKIN_BONUS_HP: 50}), 150)

    def test_ninjutsu_and_song_duration_gear(self):
        utsusemi = self.spec("Utsusemi Ichi")
        self.assertEqual(
            effects.buff_duration(utsusemi, main_job=20, main_level=99,
                                  mods={mod.NINJUTSU_DURATION: 60},
                                  skill=effects.NINJUTSU_SKILL),
            960.0)
        song = self.spec("Armys Paeon")
        self.assertEqual(
            effects.buff_duration(song, main_job=20, main_level=99,
                                  mods={mod.SONG_DURATION_BONUS: 50},
                                  skill=40),
            float(song.duration) * 1.5)

    def test_song_plus_gear_adds_ten_percent_duration_a_point(self):
        """All Songs and the family row are duration, not just potency.

        BG-wiki's Song page: "Song+ potency gear increases duration by 10% per 1
        Song+".  Loughnashade (All songs +4) is therefore +40% and Mnbw. Whistle +1
        (+3) +30%, which is what carries a retail bard past eleven minutes.
        """
        paeon = self.spec("Armys Paeon")
        base = float(paeon.duration)
        self.assertEqual(
            effects.song_duration(paeon, name="Armys Paeon",
                                  mods={mod.ALL_SONGS_EFFECT: 4,
                                        mod.PAEON_EFFECT: 2}),
            base * 1.6)
        # Only the song's own family row counts: Minuet+1 does nothing for a March.
        march = self.spec("Victory March")
        self.assertEqual(
            effects.song_duration(march, name="Victory March",
                                  mods={mod.ALL_SONGS_EFFECT: 4,
                                        mod.MINUET_EFFECT: 1}),
            float(march.duration) * 1.4)
        # The 454 lines and the Song+ points are additive, and Troubadour doubles
        # the lot after they are added.
        self.assertEqual(
            effects.song_duration(march, name="Victory March", troubadour=True,
                                  mods={mod.SONG_DURATION_BONUS: 50,
                                        mod.ALL_SONGS_EFFECT: 4}),
            float(march.duration) * 1.9 * 2.0)

    def test_drain_and_aspir_potency_gear(self):
        self.assertEqual(effects.drain_amount(100, {mod.DRAIN_ASPIR: 20}), 120)


class HelixTest(unittest.TestCase):
    """The Helix line's numbers and its generated-table regression, without a session."""

    def test_duration_tiers_follow_the_scholar_level(self):
        self.assertEqual(effects.helix_duration(20), 30.0)
        self.assertEqual(effects.helix_duration(39), 30.0)
        self.assertEqual(effects.helix_duration(40), 60.0)
        self.assertEqual(effects.helix_duration(59), 60.0)
        self.assertEqual(effects.helix_duration(60), 90.0)
        self.assertEqual(effects.helix_duration(99), 90.0)

    def test_scholar_level_reads_the_support_job(self):
        self.assertEqual(effects.scholar_level(20, 75, 0, 0), 75)
        self.assertEqual(effects.scholar_level(1, 99, 20, 49), 49)
        self.assertEqual(effects.scholar_level(1, 99, 0, 0), 0)

    def test_helix_is_a_nuke_dot_not_a_flat_ten_damage_effect(self):
        """The generated icon table no longer carries helix's interval as damage."""
        for name in ("Geohelix", "Hydrohelix", "Anemohelix", "Pyrohelix", "Cryohelix",
                     "Ionohelix", "Noctohelix", "Luminohelix"):
            for label in (name, name + " II"):
                spec = effects.for_spell(label)
                self.assertIsNotNone(spec, label)
                self.assertTrue(spec.helix, label)
                self.assertEqual(spec.effect, effects.HELIX, label)
                self.assertEqual(int(spec.tick), 0, label)
                self.assertNotIn(label.casefold(), STATUS_SPELLS)


if __name__ == "__main__":
    unittest.main()
