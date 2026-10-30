"""Corsair roll tables, Double-Up, Bust and the client status packets.

The expected tables are BG-wiki's Roll Total tables, stored here as the values the
engine reads: percent points for Attack/Defense/Fast Cast/Crit, hundredths for
haste, flat points for accuracy/evasion/Save TP, and the percent chance numbers for
the pet and EXP rolls.
"""
from __future__ import annotations

import struct
import unittest

from fanxi_server.game import effects, modifiers as mod, rolls


class FakeRng:
    def __init__(self, *values):
        self.values = list(values) or [1]

    def randint(self, _a, _b):
        if len(self.values) > 1:
            return self.values.pop(0)
        return self.values[0]


class FakePet:
    alive = True


class FakeWorld:
    def __init__(self, *members):
        self.members = list(members)

    def _trust_party_sessions(self, owner):
        return [member for member in self.members if member is not owner]


class FakeSession:
    def __init__(self, job=17, char_id=1):
        self.char = {"main_job": job, "char_id": char_id, "hp": 100, "mp": 100}
        self.effects = {}
        self.queue = []
        self.messages = []
        self.ability_recasts = {}
        self.world = None
        self.pet_entity = None
        self.snake_eye = False
        self.crooked_cards = False
        self.pos = [0.0, 0.0, 0.0, 0]
        self.merits = {}
        self.extra_mods = {}

    def distance_to(self, x, y, z):
        return 0.0

    def combat_mods(self):
        return dict(self.extra_mods)

    def say(self, text):
        self.messages.append(text)

    def add_effect(self, effect, *, duration=0.0, power=0, tick=0, mods=None, **kw):
        self.effects[effect] = {"until": duration, "power": power, "tick": tick,
                                "icon": kw.get("icon", effect),
                                "mods": dict(mods or {}), "rolled_at": 0.0}

    def effect(self, effect):
        return self.effects.get(effect)

    def has_effect(self, effect):
        return effect in self.effects

    def remove_effect(self, effect, quiet=False):
        self.effects.pop(effect, None)

    def merit_counts(self):
        return dict(self.merits)

    def char_status(self):
        return b"\x37\0"

    def char_stats(self):
        return b"\x61\0"

    def party_member(self):
        return b"\0"


EXPECTED = {
    98: {mod.DOUBLE_ATTACK: (1, 2, 3, 4, 10, 5, 6, 6, 1, 7, 15)},
    99: {mod.SUBTLE_BLOW: (8, 10, 32, 12, 14, 16, 4, 20, 22, 24, 40)},
    100: {mod.CURE_POTENCY_RCVD: (3, 4, 12, 5, 6, 7, 1, 8, 9, 10, 16)},
    101: {mod.MATT: (4, 6, 8, 10, 25, 12, 14, 17, 2, 20, 30)},
    102: {mod.MACC: (10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)},
    103: {mod.CRIT_HIT_RATE: (100, 200, 300, 400, 1000, 500, 600, 700, 100, 800, 1400)},
    104: {mod.DEF_PERCENT: (5, 6, 20, 7, 9, 10, 3, 12, 14, 16, 23)},
    105: {mod.ATT_PERCENT: (6, 8, 9, 25, 11, 12, 16, 3, 17, 19, 31),
          mod.RATT_PERCENT: (6, 8, 9, 25, 11, 12, 16, 3, 17, 19, 31)},
    106: {mod.ATT_PERCENT: (6, 8, 9, 25, 11, 12, 16, 3, 17, 19, 31),
          mod.RATT_PERCENT: (6, 8, 9, 25, 11, 12, 16, 3, 17, 19, 31)},
    107: {mod.SPELL_INTERRUPT: (-8, -42, -11, -15, -19, -4, -23, -27, -31, -35, -50)},
    108: {mod.ACC: (10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50),
          mod.RACC: (10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)},
    109: {mod.STORETP: (8, 32, 10, 12, 14, 4, 16, 20, 22, 24, 40)},
    110: {mod.EVA: (10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)},
    111: {mod.ACC: (10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50),
          mod.RACC: (10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)},
    112: {mod.REFRESH: (1, 1, 1, 1, 3, 2, 2, 2, 1, 3, 4)},
    113: {mod.MDEF: (5, 20, 6, 8, 9, 3, 10, 13, 14, 15, 25)},
    114: {mod.EXP_BONUS: (10, 11, 11, 12, 20, 13, 15, 16, 8, 17, 24),
          mod.CAPACITY_BONUS: (10, 11, 11, 12, 20, 13, 15, 16, 8, 17, 24)},
    115: {mod.MACC: (5, 8, 35, 11, 14, 18, 2, 22, 26, 30, 40),
          mod.MATT: (5, 8, 35, 11, 14, 18, 2, 22, 26, 30, 40)},
    116: {mod.REGEN: (3, 4, 12, 5, 6, 7, 1, 8, 9, 10, 16)},
    117: {mod.CONSERVE_MP: (2, 10, 3, 4, 4, 1, 5, 6, 7, 7, 12)},
    118: {mod.MOVE_SPEED_BOLTERS_ROLL: (6, 6, 16, 8, 8, 10, 10, 12, 4, 14, 20)},
    119: {mod.FASTCAST: (6, 15, 7, 8, 9, 10, 5, 11, 12, 13, 20)},
    120: {mod.SNAPSHOT: (2, 3, 11, 4, 5, 6, 7, 8, 1, 10, 12)},
    121: {mod.HASTE_ABILITY: (200, 300, 400, 1100, 500, 600, 700, 800, 100, 1000, 1200)},
    122: {mod.REGAIN: (10, 10, 10, 10, 30, 10, 10, 0, 20, 20, 40)},
    302: {mod.SKILLCHAIN_BONUS: (2, 3, 20, 5, 7, 9, 11, 13, 15, 1, 25)},
    303: {mod.SAVETP: (30, 50, 70, 90, 200, 110, 20, 130, 150, 170, 250)},
    304: {mod.REGAIN: (20, 50, 20, 20, 30, 30, 30, 40, 40, 10, 60),
          mod.REGEN: (4, 20, 6, 8, 10, 12, 14, 16, 18, 3, 25)},
    305: {mod.COUNTER: (3, 4, 5, 14, 6, 7, 8, 1, 9, 10, 16)},
    390: {mod.ENH_MAGIC_DURATION: (6, 7, 15, 8, 9, 10, 5, 11, 12, 13, 20)},
    391: {mod.MEVA: (10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)},
}


class RollTableTest(unittest.TestCase):
    def test_every_roll_has_the_wiki_table(self):
        self.assertEqual(set(EXPECTED), set(rolls.ROLLS))
        for ability_id, table in EXPECTED.items():
            spec = rolls.ROLLS[ability_id]
            for value in range(1, 12):
                expected = {modifier: values[value - 1]
                            for modifier, values in table.items()}
                self.assertEqual(expected, spec.mods(value),
                                 "%s at %d" % (spec.name, value))
            self.assertEqual(spec.mods(0), spec.mods(1))
            self.assertEqual(spec.mods(12), spec.mods(11))

    def test_every_roll_has_an_icon_and_a_real_modifier(self):
        for spec in rolls.ROLLS.values():
            self.assertGreater(spec.status, 0, spec.name)
            self.assertTrue(spec.mods(1), spec.name)
            self.assertTrue(spec.mods(11), spec.name)
            self.assertNotEqual(spec.mods(1), spec.mods(11), spec.name)

    def test_roll_duration_is_retail_five_minutes_plus_job_points(self):
        self.assertEqual(rolls.duration(17), 340.0)
        self.assertEqual(rolls.duration(1), 300.0)

    def test_roll_duration_stacks_merits_and_phantom_duration_gear(self):
        session = FakeSession()
        session.merits[rolls.WINNING_STREAK] = 5
        session.extra_mods = {mod.PHANTOM_DURATION: 90}
        self.assertEqual(530.0, rolls.duration_for(session))
        # Retail caps the duration at 11:00.
        session.extra_mods = {mod.PHANTOM_DURATION: 400}
        self.assertEqual(660.0, rolls.duration_for(session))
        rolls.apply(session, 98, FakeRng(1), 0.0)
        self.assertEqual(660.0, session.effect(310)["until"])


class RollApplyTest(unittest.TestCase):
    def test_apply_uses_the_value_and_reports_it(self):
        session = FakeSession()
        self.assertTrue(rolls.apply(session, 98, FakeRng(5), 100.0))
        state = session.effect(310)
        self.assertEqual(5, state["power"])
        self.assertEqual({mod.DOUBLE_ATTACK: 10}, state["mods"])
        self.assertEqual(100.0, state["rolled_at"])
        self.assertEqual(145.0, state["double_up_until"])
        self.assertIn("Fighter's Roll: 5 (Lucky!)", session.messages)
        self.assertTrue(any(message.startswith(b"\x37") for message in session.queue))

    def test_snake_eye_forces_a_fresh_roll_to_eleven(self):
        session = FakeSession()
        session.snake_eye = True
        rolls.apply(session, 114, FakeRng(2), 0.0)
        self.assertEqual(11, int(session.effect(326)["power"]))
        self.assertFalse(getattr(session, "snake_eye", False))
        self.assertIn("Corsair's Roll: 11", session.messages)

    def test_lucky_and_unlucky_totals_are_announced(self):
        session = FakeSession()
        rolls.apply(session, 98, FakeRng(5), 0.0)        # Fighter's lucky 5
        self.assertIn("Fighter's Roll: 5 (Lucky!)", session.messages)
        rolls.apply(session, 109, FakeRng(6), 1.0)       # Samurai unlucky 6
        self.assertIn("Samurai Roll: 6 (Unlucky!)", session.messages)
        # Double-Up that lands on the special total says so too.
        session.effects[321]["power"] = 1
        self.assertTrue(rolls.double_up(session, FakeRng(1), 2.0))
        self.assertIn("Samurai Roll: 2 (Lucky!)", session.messages)

    def test_every_roll_has_lucky_and_unlucky_numbers(self):
        for ability_id, spec in rolls.ROLLS.items():
            self.assertGreaterEqual(spec.lucky, 1, spec.name)
            self.assertLessEqual(spec.lucky, 11, spec.name)
            self.assertGreaterEqual(spec.unlucky, 1, spec.name)
            self.assertLessEqual(spec.unlucky, 11, spec.name)
            self.assertNotEqual(spec.lucky, spec.unlucky, spec.name)
            self.assertEqual((spec.lucky, spec.unlucky),
                             rolls.LUCKY_NUMBERS[spec.status], spec.name)

    def test_a_lower_reroll_replaces_the_higher_value(self):
        session = FakeSession()
        rolls.apply(session, 98, FakeRng(6), 1.0)
        rolls.apply(session, 98, FakeRng(1), 2.0)
        self.assertEqual(1, session.effect(310)["power"])
        self.assertEqual({mod.DOUBLE_ATTACK: 1}, session.effect(310)["mods"])

    def test_every_roll_applies_its_own_status(self):
        for ability_id, spec in rolls.ROLLS.items():
            session = FakeSession()
            self.assertTrue(rolls.apply(session, ability_id, FakeRng(6), 0.0))
            state = session.effect(spec.status)
            self.assertIsNotNone(state, spec.name)
            self.assertEqual(6, state["power"], spec.name)
            self.assertEqual(spec.mods(6), state["mods"], spec.name)

    def test_pet_rolls_write_the_pet(self):
        session = FakeSession()
        session.pet_entity = FakePet()
        rolls.apply(session, 111, FakeRng(6), 0.0)      # Drachen
        self.assertEqual(20, session.pet_entity.roll_accuracy)
        rolls.apply(session, 115, FakeRng(6), 1.0)      # Puppet
        self.assertEqual(18, session.pet_entity.roll_macc)
        self.assertEqual(18, session.pet_entity.roll_matt)
        rolls.apply(session, 304, FakeRng(11), 2.0)     # Companion's
        self.assertEqual(60, session.pet_entity.roll_regain)
        self.assertEqual(25, session.pet_entity.roll_regen)

    def test_exp_and_refresh_rolls_carry_their_tick(self):
        session = FakeSession()
        rolls.apply(session, 112, FakeRng(5), 0.0)      # Evoker's V = 3 MP/tick
        self.assertEqual(3, session.effect(324)["tick"])
        rolls.apply(session, 122, FakeRng(5), 1.0)      # Tactician's V = 30 TP/tick
        self.assertEqual(30, session.effect(334)["tick"])
        self.assertEqual(30, session.effect(334)["regain"])


class DoubleUpTest(unittest.TestCase):
    def test_double_up_advances_the_newest_roll(self):
        session = FakeSession()
        rolls.apply(session, 98, FakeRng(1), 100.0)
        rolls.apply(session, 118, FakeRng(2), 101.0)
        self.assertTrue(rolls.double_up(session, FakeRng(1), 102.0))
        self.assertEqual(3, session.effect(330)["power"])
        self.assertEqual(1, session.effect(310)["power"])

    def test_snake_eye_is_consumed_by_double_up(self):
        """Snake Eye makes the next roll *or* Double-Up an 11, then goes away."""
        session = FakeSession()
        rolls.apply(session, 113, FakeRng(6), 0.0)      # Magus's Roll: 6
        session.snake_eye = True
        self.assertTrue(rolls.double_up(session, FakeRng(1), 1.0))
        self.assertEqual(11, int(session.effect(325)["power"]))
        self.assertFalse(getattr(session, "snake_eye", False))
        self.assertEqual({"ability_id": 0, "animation": 0, "info": 5,
                          "value": 11, "message": 424}, session.roll_action)
        # The next fresh roll is ordinary again.
        rolls.apply(session, 114, FakeRng(4), 2.0)      # Corsair's Roll: 4
        self.assertEqual(4, int(session.effect(326)["power"]))
        self.assertIn("Corsair's Roll: 4", session.messages)

    def test_double_up_adds_a_die_and_queues_the_increase(self):
        """Retail Double-Up adds 1-6, and the result's info is that increase."""
        session = FakeSession()
        rolls.apply(session, 118, FakeRng(2), 100.0, animation=118)
        self.assertEqual({"ability_id": 118, "animation": 118, "info": 2,
                          "value": 2, "message": 420}, session.roll_action)
        session.roll_action = None
        self.assertTrue(rolls.double_up(session, FakeRng(5), 101.0,
                                        animation=118, ability_id=118))
        self.assertEqual(7, session.effect(330)["power"])
        self.assertEqual({"ability_id": 118, "animation": 118, "info": 5,
                          "value": 7, "message": 424}, session.roll_action)

    def test_double_up_has_a_45_second_window(self):
        session = FakeSession()
        rolls.apply(session, 118, FakeRng(2), 100.0)
        self.assertFalse(rolls.double_up(session, FakeRng(1), 146.0))
        self.assertEqual(2, session.effect(330)["power"])
        self.assertIn("Too much time has passed to double up.", session.messages)

    def test_bust_adds_the_bust_status_and_blocks_rolls(self):
        session = FakeSession()
        rolls.apply(session, 118, FakeRng(11), 0.0)
        self.assertEqual(11, session.effect(330)["power"])
        session.queue.clear()
        # The delta is 1, then Bust Evasion rolls 100 and fails.
        self.assertTrue(rolls.double_up(session, FakeRng(1, 100), 2.0))
        self.assertIsNone(session.effect(330))
        bust = session.effect(effects.BUST)
        self.assertIsNotNone(bust)
        self.assertEqual(300.0, bust["until"])
        self.assertEqual(309, bust["icon"])
        self.assertIn("Bolter's Roll busts!", session.messages)
        self.assertTrue(any(message.startswith(b"\x37") for message in session.queue))
        self.assertFalse(rolls.apply(session, 105, FakeRng(3), 3.0))
        self.assertIn("You cannot roll while busted.", session.messages)

    def test_bust_evasion_keeps_the_roll_alive(self):
        session = FakeSession()
        rolls.apply(session, 98, FakeRng(11), 0.0)
        self.assertTrue(rolls.double_up(session, FakeRng(1), 1.0))
        self.assertEqual(11, session.effect(310)["power"])
        self.assertIsNone(session.effect(effects.BUST))

    def test_an_eleven_roll_is_bust_immune_for_the_other_roll(self):
        session = FakeSession()
        session.ability_recasts[rolls.PHANTOM_ROLL_RECAST_ID] = 999.0
        rolls.apply(session, 105, FakeRng(11), 0.0)      # Chaos XI
        self.assertEqual(11, session.effect(317)["power"])
        self.assertNotIn(rolls.PHANTOM_ROLL_RECAST_ID, session.ability_recasts)
        rolls.apply(session, 118, FakeRng(11), 1.0)      # Bolter's XI
        self.assertTrue(rolls.double_up(session, FakeRng(1), 2.0))
        self.assertIsNone(session.effect(330))
        self.assertIsNotNone(session.effect(317))
        self.assertIsNone(session.effect(effects.BUST))
        self.assertIn("Your XI roll nullifies the bust; Bolter's Roll wears off.",
                      session.messages)

    def test_fold_removes_rolls_and_bust(self):
        session = FakeSession()
        rolls.apply(session, 98, FakeRng(3), 0.0)
        session.add_effect(effects.BUST, duration=100.0, power=1)
        self.assertTrue(rolls.fold(session))
        self.assertIsNone(session.effect(310))
        self.assertIsNone(session.effect(effects.BUST))
        self.assertIn("You fold your roll.", session.messages)

    def test_two_roll_cap_replaces_the_oldest(self):
        session = FakeSession()
        rolls.apply(session, 98, FakeRng(1), 100.0)
        rolls.apply(session, 118, FakeRng(2), 101.0)
        rolls.apply(session, 105, FakeRng(3), 102.0)
        self.assertIsNone(session.effect(310))
        self.assertIsNotNone(session.effect(330))
        self.assertIsNotNone(session.effect(317))
        self.assertEqual(2, len(rolls.active(session)))

    def test_party_rolls_are_owned_by_the_caster(self):
        caster = FakeSession()
        ally = FakeSession(char_id=2)
        caster.world = ally.world = FakeWorld(caster, ally)
        rolls.apply(caster, 118, FakeRng(5), 100.0)
        self.assertEqual(5, caster.effect(330)["power"])
        self.assertEqual(5, ally.effect(330)["power"])
        self.assertEqual(1, ally.effect(330)["roll_owner"])
        # The ally cannot double up a roll the caster owns.
        self.assertFalse(rolls.double_up(ally, FakeRng(1), 101.0))
        self.assertIn("You have no active roll to double up.", ally.messages)
        # The caster's Double-Up moves every party copy.
        self.assertTrue(rolls.double_up(caster, FakeRng(1), 101.0))
        self.assertEqual(6, caster.effect(330)["power"])
        self.assertEqual(6, ally.effect(330)["power"])
        # A bust removes the ally's copy too, but only the caster gets Bust.
        caster.effect(330)["power"] = 11
        ally.effect(330)["power"] = 11
        self.assertTrue(rolls.double_up(caster, FakeRng(100), 102.0))
        self.assertIsNone(ally.effect(330))
        self.assertIsNone(ally.effect(effects.BUST))
        self.assertIsNotNone(caster.effect(effects.BUST))

    def test_corsair_support_job_gets_one_roll(self):
        session = FakeSession(job=1)
        rolls.apply(session, 98, FakeRng(1), 100.0)
        rolls.apply(session, 118, FakeRng(2), 101.0)
        self.assertIsNone(session.effect(310))
        self.assertIsNotNone(session.effect(330))
        self.assertEqual(1, len(rolls.active(session)))


if __name__ == "__main__":
    unittest.main()
