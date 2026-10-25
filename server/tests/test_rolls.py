"""Corsair roll values and job-point duration."""
from __future__ import annotations

import unittest

from fanxi_server.game import modifiers as mod, rolls


class FakeRng:
    def __init__(self, value):
        self.value = value

    def randint(self, _a, _b):
        return self.value


class FakeSession:
    def __init__(self, job=17):
        self.char = {"main_job": job, "char_id": 1, "hp": 100, "mp": 100}
        self.effects = {}
        self.queue = []
        self.messages = []

    def say(self, text):
        self.messages.append(text)

    def add_effect(self, effect, **kw):
        self.effects[effect] = dict(kw)

    def effect(self, effect):
        return self.effects.get(effect)

    def remove_effect(self, effect, quiet=False):
        self.effects.pop(effect, None)

    def char_status(self):
        return b"\0"

    def char_stats(self):
        return b"\0"

    def party_member(self):
        return b"\0"


class RollTest(unittest.TestCase):
    def test_fighters_roll_scales_with_value(self):
        spec = rolls.spec(98)
        self.assertEqual(spec.status, 310)
        self.assertEqual(spec.mods(6), {mod.DOUBLE_ATTACK: 6})

    def test_roll_duration_gets_the_cor_row(self):
        self.assertEqual(rolls.duration(17), 100.0)
        self.assertEqual(rolls.duration(1), 60.0)

    def test_apply_uses_the_roll_value(self):
        session = FakeSession()
        self.assertTrue(rolls.apply(session, 98, FakeRng(5), 0.0))
        state = session.effect(310)
        self.assertEqual(state["power"], 5)
        self.assertEqual(state["mods"], {mod.DOUBLE_ATTACK: 5})
        self.assertIn("Fighter's Roll: 5", session.messages)

    def test_snake_eye_makes_an_eleven(self):
        session = FakeSession()
        session.snake_eye = True
        rolls.apply(session, 98, FakeRng(1), 0.0)
        self.assertEqual(session.effect(310)["power"], 11)
        self.assertFalse(session.snake_eye)


if __name__ == "__main__":
    unittest.main()
