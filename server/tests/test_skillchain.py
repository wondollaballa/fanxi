"""Skillchains and Magic Bursts: the window, the chain hit and the burst bonus."""
from __future__ import annotations

import json
import re
import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server.game import effects, modifiers as mod, packets, skillchain
from fanxi_server.game.entities import ZoneEntity
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


def action_messages(session) -> list[int]:
    """The 0x028 message ids the session queued (the chain/burst lines)."""
    out = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x028:
            continue
        # The message is the last 10 bits of the result block; decode the family
        # loosely: the chain message sits in 287..303, the burst at 252.
        out.append(bytes(message))
    return out


class SkillchainTest(unittest.TestCase):
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
        self.session.char["main_job"] = 1
        self.session.char["main_level"] = 99

    def mob(self):
        mob = ZoneEntity(kind="mob", id=0x7FFF0001, targid=0x300, zone=self.session.zone,
                         name="Testmob", level=75)
        mob.alive = True
        mob.hp_max = 5000
        mob.hp = 5000
        return mob

    def test_fast_blade_opens_and_burning_blade_forms_liquefaction(self):
        now = time.time()
        state, formed = skillchain.advance(None, (4, 0, 0), now)   # Fast Blade: Scission
        self.assertEqual(int(skillchain.SC.NONE), int(formed))
        self.assertTrue(state.is_opening(now))
        state, formed = skillchain.advance(state, (3, 0, 0), now + 5)  # Burning Blade
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))
        self.assertEqual(1, state.count)
        self.assertEqual(1, int(skillchain.TIER[formed]))
        # A level-1 link keeps the full 11 s window (Fanxi rule).
        self.assertAlmostEqual(now + 5 + skillchain.OPEN_SECONDS, state.until, delta=0.1)

    def test_the_level_one_loop_keeps_the_full_window(self):
        """Savage Blade > Hot Shot > Savage Blade ... stays level 1 and never times out.

        This is the loop COR players expect: 4 = Fragmentation/Scission on Savage Blade,
        3 = Liquefaction/Transfixion on Hot Shot.  A 10 s cadence breaks it under the
        retail one-second shrink (the third link only has 9 s), so a level-1 link has to
        keep the full 11 s window.
        """
        now = time.time()
        state = None
        opened = 0
        for index in range(8):
            props = (12, 4, 0) if index % 2 == 0 else (3, 1, 0)
            state, formed = skillchain.advance(state, props, now + index * 10.0)
            if index == 0:
                self.assertEqual(int(skillchain.SC.NONE), int(formed))
                continue
            opened += 1
            expected = (skillchain.SC.LIQUEFACTION if index % 2
                        else skillchain.SC.SCISSION)
            self.assertEqual(int(expected), int(formed), index)
            self.assertEqual(1, int(skillchain.TIER[formed]))
            self.assertAlmostEqual(now + index * 10.0 + skillchain.OPEN_SECONDS,
                                   state.until, delta=0.1)
        self.assertEqual(7, opened)
        self.assertEqual(skillchain.MAX_CHAIN_COUNT, state.count)

    def test_a_level_two_link_still_shrinks_the_window(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)      # Scission
        state, formed = skillchain.advance(state, (3, 0, 0), now + 5)  # Liquefaction
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))
        self.assertAlmostEqual(now + 5 + skillchain.OPEN_SECONDS,
                               state.until, delta=0.1)
        # Impaction closes the level-1 Liquefaction into Fusion (tier 2); that wider
        # chain still loses one second per link as in retail.
        state, formed = skillchain.advance(state, (8, 0, 0), now + 15)
        self.assertEqual(int(skillchain.SC.FUSION), int(formed))
        self.assertEqual(2, int(skillchain.TIER[formed]))
        self.assertAlmostEqual(now + 15 + skillchain.OPEN_SECONDS - 1.0,
                               state.until, delta=0.1)
        state, formed = skillchain.advance(state, (12, 0, 0), now + 25)
        self.assertEqual(int(skillchain.SC.LIGHT), int(formed))
        self.assertAlmostEqual(now + 25 + skillchain.OPEN_SECONDS - 2.0,
                               state.until, delta=0.1)

    def test_a_skill_inside_the_delay_does_not_chain(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        _state, formed = skillchain.advance(state, (3, 0, 0), now + 1.0)
        self.assertEqual(int(skillchain.SC.NONE), int(formed))

    def test_a_close_just_after_the_exact_window_still_lands(self):
        """The half-second tick grace keeps an 11.3 s close from losing the chain."""
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        state, formed = skillchain.advance(state, (3, 0, 0),
                                           now + 11.0 + 0.3)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))

    def test_the_second_link_accepts_a_close_at_the_exact_ten_second_mark(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        state, formed = skillchain.advance(state, (3, 0, 0), now + 5.0)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))
        # The first link's state is 11 s long and starts at now+5; a Fusion close
        # arriving at now+15 (the ten-second mark) must still chain.
        state, formed = skillchain.advance(state, (8, 0, 0), now + 5.0 + 10.0)
        self.assertEqual(int(skillchain.SC.FUSION), int(formed))

    def test_a_close_beyond_the_grace_opens_a_new_window(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        state, formed = skillchain.advance(state, (3, 0, 0),
                                           now + 11.0 + 0.6)
        self.assertEqual(int(skillchain.SC.NONE), int(formed))
        self.assertEqual(0, state.tier)

    def test_diamond_aspis_keeps_the_full_window_at_every_step(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        state, formed = skillchain.advance(state, (3, 0, 0), now + 5,
                                           diamond=True)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))
        self.assertAlmostEqual(now + 5 + skillchain.DIAMOND_ASPIS_SECONDS,
                               state.until, delta=0.1)
        state, formed = skillchain.advance(state, (8, 0, 0), now + 10,
                                           diamond=True)
        self.assertEqual(int(skillchain.SC.FUSION), int(formed))
        self.assertAlmostEqual(now + 10 + skillchain.DIAMOND_ASPIS_SECONDS,
                               state.until, delta=0.1)

    def test_diamond_aspis_detection_reads_the_sub_slot(self):
        self.assertFalse(self.session.has_diamond_aspis())
        self.session.equipped[1] = (0, 0, skillchain.DIAMOND_ASPIS_ITEM_ID)
        self.assertTrue(self.session.has_diamond_aspis())
        self.session.equipped[1] = (0, 0, 12345)
        self.assertFalse(self.session.has_diamond_aspis())

    def test_the_chain_hit_uses_the_closing_damage_and_the_multiplier(self):
        self.assertAlmostEqual(0.50, skillchain.chain_multiplier(1, 1))
        self.assertAlmostEqual(0.60, skillchain.chain_multiplier(2, 1))
        self.assertEqual(500, skillchain.skillchain_damage(1000, 1, 1))
        self.assertEqual(600, skillchain.skillchain_damage(1000, 2, 1))
        self.assertEqual(750, skillchain.skillchain_damage(1000, 2, 2))

    def test_the_chain_hit_stops_at_99999(self):
        # A capped 99,999 closing WS times a tier-3 link would print six digits; the
        # chain hit shares the weapon skill's ceiling.
        self.assertEqual(99999, skillchain.DAMAGE_CAP)
        self.assertEqual(99999, skillchain.skillchain_damage(99999, 3, 3))
        self.assertEqual(99999, skillchain.skillchain_damage(10 ** 6, 4, 5))

    def test_sengikori_cannot_lift_a_chain_past_the_cap(self):
        now = time.time()
        mob = self.mob()
        mob.hp_max = 500000
        mob.hp = 500000
        self.assertIsNone(self.session._advance_skillchain(mob, {"id": 32}, 800, now))
        self.session._sengikori_until = now + 60.0
        # The chain formula returns its own 99,999 ceiling; Sengikori's +25% is applied
        # afterwards and must be clipped again before the HP is spent.
        with mock.patch.object(skillchain, "skillchain_damage", return_value=99999):
            chain = self.session._advance_skillchain(mob, {"id": 33}, 99999, now + 5)
        self.assertIsNotNone(chain)
        self.assertEqual(99999, chain["damage"])
        self.assertEqual(500000 - 99999, mob.hp)

    def test_maru_kala_self_chains_gravitation_then_darkness(self):
        """Maru Kala (Detonation/Compression/Distortion) can close its own chain.

        First Maru Kala opens with all three properties; the second matches
        Compression against Detonation (Gravitation); the third matches Distortion
        against Gravitation (Darkness).  This is the Varga Purnikawa self-chain the
        Battle hub planner shows, and it is the same property order as
        data/weapon_skill_properties.json entry 231.
        """
        now = time.time()
        mob = self.mob()
        mob.hp = mob.hp_max = 50000
        self.assertIsNone(self.session._advance_skillchain(mob, {"id": 231}, 800, now))
        self.assertEqual(0, mob.skillchain.tier)
        chain = self.session._advance_skillchain(mob, {"id": 231}, 800, now + 5.0)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.GRAVITATION), mob.skillchain.sc)
        self.assertEqual(1, mob.skillchain.count)
        # Gravitation's window is 11 - 1 = 10 s; the third cast at +5 s must close it.
        chain = self.session._advance_skillchain(mob, {"id": 231}, 800, now + 10.0)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.DARKNESS), mob.skillchain.sc)
        self.assertEqual(2, mob.skillchain.count)

    def test_a_landed_pair_forms_the_chain_and_damages_the_mob(self):
        now = time.time()
        mob = self.mob()
        # Fast Blade (32) opens, Burning Blade (33) closes five seconds later.  The
        # closing skill returns the additional-effect block its action carries: the
        # client plays the skillchain from that block, not from a second action.
        self.assertIsNone(self.session._advance_skillchain(mob, {"id": 32}, 800, now))
        self.assertEqual(0, mob.skillchain.tier)
        chain = self.session._advance_skillchain(mob, {"id": 33}, 800, now + 5)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), mob.skillchain.sc)
        # Tier 1, link 1: 800 x 0.50 = 400 off the monster.
        self.assertEqual(5000 - 400, mob.hp)
        self.assertEqual(400, chain["damage"])
        self.assertEqual(int(skillchain.proc_kind(mob.skillchain.sc)), chain["proc"])
        self.assertEqual(skillchain.proc_message(mob.skillchain.sc), chain["message"])

    def test_savage_blade_and_hot_shot_keep_chaining_at_ten_seconds(self):
        """The real handler keeps the level-1 loop alive past the old window.

        Savage Blade (42) opens; Hot Shot (208) ten seconds later forms Liquefaction.
        That link must leave the full 11 s window, so the next Savage Blade at +20 s
        forms Scission instead of opening a new chain.
        """
        now = time.time()
        mob = self.mob()
        self.assertIsNone(self.session._advance_skillchain(mob, {"id": 42}, 800, now))
        chain = self.session._advance_skillchain(mob, {"id": 208}, 800, now + 10)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), mob.skillchain.sc)
        self.assertAlmostEqual(now + 10 + skillchain.OPEN_SECONDS,
                               mob.skillchain.until, delta=0.1)
        chain = self.session._advance_skillchain(mob, {"id": 42}, 800, now + 20)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.SCISSION), mob.skillchain.sc)
        self.assertEqual(2, mob.skillchain.count)
        self.assertAlmostEqual(now + 20 + skillchain.OPEN_SECONDS,
                               mob.skillchain.until, delta=0.1)
        chain = self.session._advance_skillchain(mob, {"id": 208}, 800, now + 30)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), mob.skillchain.sc)
        self.assertEqual(3, mob.skillchain.count)

    def test_a_matching_spell_inside_the_window_is_a_magic_burst(self):
        now = time.time()
        mob = self.mob()
        mob.skillchain = skillchain.SkillchainState(
            props=(3, 0, 0), tier=1, sc=int(skillchain.SC.LIQUEFACTION), count=1,
            started=now, until=now + 8.0)
        spell = self.service.spell_by_name("Fire")
        spec = effects.for_spell("Fire")
        burst = self.session._cast_numbers(spell, spec, mob, healing=False)
        self.assertEqual(1, burst["magic_burst"])
        mob.skillchain = None
        plain = self.session._cast_numbers(spell, spec, mob, healing=False)
        self.assertEqual(0, plain["magic_burst"])
        self.assertGreater(burst["amount"], plain["amount"])
        self.assertAlmostEqual(1.85, skillchain.magic_burst_multiplier(1), places=3)

    def test_red_mage_mag_burst_bonus_trait_scales_the_burst(self):
        """The RDM Mag. Burst Bonus trait (274) belongs in the burst multiplier.

        The trait is 5 at 85 and 7 at 95.  It was in the trait table but no damage path
        read it, so a Red Mage's bursts were only the base multiplier.
        """
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        now = time.time()
        mob = self.mob()
        mob.level = 1
        spell = self.service.spell_by_name("Fire")
        spec = effects.for_spell("Fire")
        plain = self.session._cast_numbers(spell, spec, mob, healing=False)["amount"]
        self.assertGreater(plain, 0)
        mob.skillchain = skillchain.SkillchainState(
            props=(3, 0, 0), tier=1, sc=int(skillchain.SC.LIQUEFACTION), count=1,
            started=now, until=now + 8.0)
        burst = self.session._cast_numbers(spell, spec, mob, healing=False)["amount"]
        # Base 1.85 x (1 + 0.07).  A level-1 target caps the resist roll at 1.0 in
        # both calls, so the extra +100 Magic Accuracy does not change the ratio.
        self.assertAlmostEqual(
            burst, int(plain * skillchain.magic_burst_multiplier(1) * 1.07), delta=1)

    def test_a_spell_outside_the_window_is_not_a_burst(self):
        mob = self.mob()
        now = time.time()
        mob.skillchain = skillchain.SkillchainState(
            props=(3, 0, 0), tier=1, sc=int(skillchain.SC.LIQUEFACTION), count=1,
            started=now - 20, until=now - 10)
        spell = self.service.spell_by_name("Fire")
        numbers = self.session._cast_numbers(spell, effects.for_spell("Fire"), mob,
                                             healing=False)
        self.assertEqual(0, numbers["magic_burst"])


    def spell(self, name):
        spell = self.service.spell_by_name(name)
        self.assertIsNotNone(spell, name)
        return spell

    def test_the_element_to_chain_map_covers_every_element(self):
        self.assertEqual(int(skillchain.SC.LIQUEFACTION),
                         skillchain.immanence_props(1)[0])   # Fire
        self.assertEqual(int(skillchain.SC.INDURATION),
                         skillchain.immanence_props(2)[0])   # Ice
        self.assertEqual(int(skillchain.SC.DETONATION),
                         skillchain.immanence_props(3)[0])   # Wind
        self.assertEqual(int(skillchain.SC.SCISSION),
                         skillchain.immanence_props(4)[0])   # Earth
        self.assertEqual(int(skillchain.SC.IMPACTION),
                         skillchain.immanence_props(5)[0])   # Thunder
        self.assertEqual(int(skillchain.SC.REVERBERATION),
                         skillchain.immanence_props(6)[0])   # Water
        self.assertEqual(int(skillchain.SC.TRANSFIXION),
                         skillchain.immanence_props(7)[0])   # Light
        self.assertEqual(int(skillchain.SC.COMPRESSION),
                         skillchain.immanence_props(8)[0])   # Dark
        self.assertEqual((0, 0, 0), skillchain.immanence_props(0))
        self.assertEqual((0, 0, 0), skillchain.immanence_props(99))

    def test_immanence_spell_opens_and_the_next_closes_liquefaction(self):
        """Stone is Earth (Scission); Fire closes it into Liquefaction."""
        now = time.time()
        mob = self.mob()
        self.session.add_effect(effects.IMMANENCE, duration=60)
        self.assertIsNone(
            self.session._magic_skillchain(mob, self.spell("Stone"), 1000, now))
        self.assertEqual(0, mob.skillchain.tier)
        self.assertIsNone(self.session.effect(effects.IMMANENCE))
        self.session.add_effect(effects.IMMANENCE, duration=60)
        chain = self.session._magic_skillchain(
            mob, self.spell("Fire"), 1000, now + 5.0)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), mob.skillchain.sc)
        self.assertEqual(1, mob.skillchain.count)
        # Tier 1, link 1: 1000 x 0.50 off the monster.
        self.assertEqual(5000 - 500, mob.hp)
        self.assertEqual(500, chain["damage"])
        self.assertEqual(int(skillchain.proc_kind(mob.skillchain.sc)), chain["proc"])
        self.assertEqual(int(skillchain.proc_message(mob.skillchain.sc)),
                         chain["message"])
        self.assertIsNone(self.session.effect(effects.IMMANENCE))

    def test_a_helix_closes_the_chain_too(self):
        """A Helix is a damaging elemental spell, so Immanence chains through it."""
        now = time.time()
        mob = self.mob()
        self.session.add_effect(effects.IMMANENCE, duration=60)
        self.assertIsNone(
            self.session._magic_skillchain(mob, self.spell("Stone"), 900, now))
        self.session.add_effect(effects.IMMANENCE, duration=60)
        chain = self.session._magic_skillchain(
            mob, self.spell("Pyrohelix"), 900, now + 5.0)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), mob.skillchain.sc)

    def test_immanence_is_spent_by_a_killing_spell(self):
        mob = self.mob()
        mob.hp = 100
        self.session.add_effect(effects.IMMANENCE, duration=60)
        self.assertIsNone(self.session._magic_skillchain(
            mob, self.spell("Fire"), 1000, time.time(), defeated=True))
        self.assertIsNone(self.session.effect(effects.IMMANENCE))
        # Nothing to chain into: the lethal hit only spends the charge.
        self.assertIsNone(getattr(mob, "skillchain", None))

    def test_a_zero_damage_spell_does_not_spend_immanence(self):
        mob = self.mob()
        self.session.add_effect(effects.IMMANENCE, duration=60)
        self.assertIsNone(self.session._magic_skillchain(
            mob, self.spell("Fire"), 0, time.time()))
        self.assertIsNotNone(self.session.effect(effects.IMMANENCE))

    def test_resolve_casting_puts_the_chain_block_on_the_closing_spell(self):
        """The client plays the chain from the finished spell's own result."""
        from test_packets import decode_battle, decode_battle_results

        mob = self.mob()
        mob.targid = 0x300
        mob.x, mob.y, mob.z = self.session.pos[0], self.session.pos[1], self.session.pos[2]
        self.world.content.setdefault(self.session.zone, []).append(mob)
        self.session.entities.append(mob)
        self.session.char.update(main_job=20, main_level=99, sub_job=5, sub_level=49)
        self.session.char["mp_current"] = 9999

        base = time.time()

        def finish(name, at):
            spell = self.spell(name)
            packet = bytearray(16)
            struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                             packets.ACTION_CAST_MAGIC)
            struct.pack_into("<I", packet, 12, int(spell["id"]))
            self.session.queue.clear()
            self.session.cast_magic(bytes(packet), mob.targid)
            self.assertIsNotNone(self.session.casting, name)
            self.session.resolve_casting(at)
            return spell

        self.session.add_effect(effects.IMMANENCE, duration=60)
        finish("Stone", base + 10)
        self.assertEqual(0, mob.skillchain.tier)
        self.session.add_effect(effects.IMMANENCE, duration=60)
        # Six seconds after the opener: past the 3 s lockout, inside the 11 s window.
        fire = finish("Fire", base + 16)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), mob.skillchain.sc)

        closing = []
        for message in self.session.queue:
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x028:
                continue
            body = bytes(message[4:])
            action = decode_battle(body)
            if action["category"] != packets.ACTION_CATEGORY_MAGIC_FINISH:
                continue
            for row in decode_battle_results(body):
                if row.get("add_effect"):
                    closing.append((action["action"], row))
        self.assertEqual(1, len(closing), closing)
        self.assertEqual(int(fire["id"]), closing[0][0])
        self.assertEqual(int(skillchain.proc_kind(mob.skillchain.sc)),
                         closing[0][1]["add_kind"])
        self.assertEqual(int(skillchain.proc_message(mob.skillchain.sc)),
                         closing[0][1]["add_message"])
        self.assertGreater(closing[0][1]["add_value"], 0)


class AddonSkillchainTableTest(unittest.TestCase):
    """The Battle hub planner must know every weapon skill the server does.

    ``battle.lua`` used to carry a hand-copied subset (ids 1-16 and 239), so a Prime
    weapon skill such as Maru Kala (231) was "unknown" in the in-game planner even
    though the server chained it.  Compare both addon tables to the generated
    ``data/weapon_skill_properties.json`` instead of trusting a hand-maintained list.
    """

    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        cls.data = {
            int(key): tuple(int(value) for value in values)
            for key, values in json.loads(
                (root / "data" / "weapon_skill_properties.json").read_text(
                    encoding="utf-8"))["weapon_skills"].items()}

        def table(path: Path, name: str) -> dict[int, tuple[int, int, int]]:
            text = path.read_text(encoding="utf-8")
            match = re.search(r"local %s = \{\n(.*?)\n\}" % re.escape(name),
                              text, re.S)
            if match is None:
                raise AssertionError("%s not found in %s" % (name, path))
            out = {}
            for key, a, b, c in re.findall(
                    r"\[(\d+)\] = \{ (\d+), (\d+), (\d+) \}", match.group(1)):
                out[int(key)] = (int(a), int(b), int(c))
            return out

        cls.battle = table(root / "host" / "addons" / "lua" / "battle.lua",
                           "SC_WS_PROPS")
        cls.control = table(root / "host" / "addons" / "lua" / "control.lua",
                            "HUD_WS_SC")

    def test_the_battle_hub_table_matches_the_server_properties(self):
        for ws_id, values in self.data.items():
            padded = tuple(values) + (0,) * (3 - len(values))
            self.assertIn(ws_id, self.battle, "battle.lua is missing WS %d" % ws_id)
            self.assertEqual(padded, self.battle[ws_id], ws_id)
        # Extra zero-only rows (a skill the reference SQL lists with no properties)
        # are harmless; a non-zero property the server does not have is not.
        for ws_id, values in self.battle.items():
            if ws_id not in self.data:
                self.assertEqual((0, 0, 0), values, ws_id)

    def test_the_control_hud_table_matches_the_battle_hub_table(self):
        for ws_id, values in self.battle.items():
            self.assertEqual(values, self.control.get(ws_id), ws_id)
        for ws_id, values in self.control.items():
            if ws_id not in self.battle:
                self.assertEqual((0, 0, 0), values, ws_id)


if __name__ == "__main__":
    unittest.main()
