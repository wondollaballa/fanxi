"""The engage/disengage contract, modelled on retail's /attack off.

`attack_off` is the one packet that used to be swallowed: a single /attack off while the
target stood outside melee reach was ignored, and because each swallow re-armed the timer,
a player pressing it again (seconds later) was ignored again.  The engagement then could
not be dropped at all -- the stuck stance from the 01:26 session.  These tests pin the
retail rule: the first press breaks the engagement, except for the one packet the client
emits by itself on a new engagement.
"""
from __future__ import annotations

import types
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from fanxi_server.game.zone import ZoneSession  # noqa: E402


class _Mob:
    def __init__(self, gap: float, alive: bool = True):
        self.gap = gap
        self.alive = alive

    def distance_to(self, *pos) -> float:
        return self.gap


class _World:
    def __init__(self, mob: _Mob):
        self.mob = mob

    def entity_by_id(self, zone, ident):
        return self.mob


def make_session(gap: float, *, engaged: bool = True,
                 client_range_drop: bool = True, alive: bool = True):
    """A ZoneSession with only the state attack_off/disengage touch.

    Real ZoneSession.__init__ builds a zone, a socket and a character; the handlers below
    read engaged_id, pos, world and queue, so the stub binds the real methods to those.
    """
    session = object.__new__(ZoneSession)
    session.zone = 1
    session.pos = [0.0, 0.0, 0.0, 0]
    session.engaged_id = 0x10BE063 if engaged else None
    session.engaged_targid = 0x63
    session.client_range_drop = client_range_drop
    session.next_attack_at = 0.0
    session.queue = []
    session.char = {"char_id": 1, "targid": 0x400}
    session.world = _World(_Mob(gap, alive))
    session.say = lambda *args, **kwargs: None
    session.char_update = lambda flag: b""
    session.stances = 0
    session.assert_stance = lambda: setattr(session, "stances", session.stances + 1)
    session.disengage = types.MethodType(ZoneSession.disengage, session)
    session.engaged_target = types.MethodType(ZoneSession.engaged_target, session)
    session.attack_off = types.MethodType(ZoneSession.attack_off, session)
    return session


class AttackOffTest(unittest.TestCase):
    def test_in_melee_disengages_on_the_first_press(self):
        session = make_session(gap=2.0)
        session.attack_off()
        self.assertIsNone(session.engaged_id)

    def test_out_of_range_press_disengages_when_the_client_drop_was_used(self):
        # The reported trap: engaged at ~10 yalms, the client's own range-drop already
        # consumed, a player pressing /attack off must get out on that press.
        session = make_session(gap=10.0, client_range_drop=False)
        session.attack_off()
        self.assertIsNone(session.engaged_id)

    def test_client_range_drop_is_absorbed_exactly_once(self):
        session = make_session(gap=10.0, client_range_drop=True)
        session.attack_off()
        self.assertEqual(session.engaged_id, 0x10BE063)
        self.assertFalse(session.client_range_drop)
        self.assertEqual(session.stances, 1)
        # The very next press is the player, and it lands.
        session.attack_off()
        self.assertIsNone(session.engaged_id)

    def test_absorption_never_rearms(self):
        session = make_session(gap=10.0)
        for _ in range(4):
            session.attack_off()
        self.assertIsNone(session.engaged_id)
        self.assertEqual(session.stances, 1)

    def test_dead_target_disengages_rather_than_absorbing(self):
        session = make_session(gap=10.0, client_range_drop=True, alive=False)
        session.attack_off()
        self.assertIsNone(session.engaged_id)

    def test_not_engaged_is_ignored(self):
        session = make_session(gap=10.0, engaged=False)
        session.attack_off()
        self.assertIsNone(session.engaged_id)
        self.assertEqual(session.queue, [])

    def test_disengage_clears_the_client_drop_allowance(self):
        session = make_session(gap=10.0)
        session.disengage()
        self.assertIsNone(session.engaged_id)
        self.assertFalse(session.client_range_drop)


if __name__ == "__main__":
    unittest.main()
