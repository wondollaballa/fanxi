"""Kill chains: the window counter and the Master chain's +2% per link."""
from __future__ import annotations

import unittest

import support  # noqa: F401  (puts server/ on sys.path)

from fanxi_server.game import chain


class ChainStateTest(unittest.TestCase):
    def test_the_first_kill_arms_the_window_and_the_second_starts_the_chain(self):
        state = chain.ChainState()
        self.assertEqual(0, state.advance(100.0, window=30.0))
        self.assertTrue(state.active(110.0))
        self.assertEqual(1, state.advance(110.0, window=30.0))
        self.assertEqual(2, state.advance(120.0, window=30.0))
        self.assertAlmostEqual(1.04, state.bonus(0.02))

    def test_a_kill_outside_the_window_restarts_the_chain(self):
        state = chain.ChainState()
        state.advance(100.0, window=30.0)
        state.advance(110.0, window=30.0)
        self.assertEqual(1, state.number)
        self.assertEqual(0, state.advance(141.0, window=30.0))
        self.assertTrue(state.active(150.0))
        self.assertEqual(1, state.advance(150.0, window=30.0))

    def test_the_chain_caps_but_the_window_keeps_refreshing(self):
        state = chain.ChainState()
        state.advance(0.0, window=30.0)
        for index in range(1, 60):
            state.advance(float(index), window=30.0, cap=5)
        self.assertEqual(5, state.number)
        self.assertTrue(state.active(60.0))
        self.assertAlmostEqual(1.10, state.bonus(0.02))

    def test_master_chain_constants_match_the_reward(self):
        self.assertEqual(30.0, chain.EXEMPLAR_CHAIN_SECONDS)
        self.assertEqual(50, chain.EXEMPLAR_CHAIN_MAX)
        self.assertAlmostEqual(2.0, chain.ChainState(number=50).bonus(
            chain.EXEMPLAR_CHAIN_BONUS_PER_LINK))

    def test_the_window_starts_at_sixty_and_shrinks_to_the_thirty_second_floor(self):
        """A solo kill pace of 35-40 s must chain; a flat 30 s window never did.

        Retail's first Master chain window is longer than 30 s and the timer shortens
        with each link until it reaches 30 s (the 2024 live logs put the floor around
        chain #25).  The old constant applied 30 s from chain #0, so a 35-45 s kill
        cadence reported "no chain, not even chain 1".
        """
        self.assertEqual(60.0, chain.window_for(0))
        self.assertLess(chain.window_for(1), chain.window_for(0))
        self.assertGreater(chain.window_for(1), 30.0)
        self.assertEqual(30.0, chain.window_for(chain.EXEMPLAR_CHAIN_FLOOR_LINK))
        self.assertEqual(30.0, chain.window_for(50))

    def test_a_kill_forty_five_seconds_later_still_chains(self):
        state = chain.ChainState()
        next_chain = state.number + 1 if state.active(100.0) else 0
        self.assertEqual(0, state.advance(100.0, window=chain.window_for(next_chain)))
        self.assertTrue(state.active(140.0))
        next_chain = state.number + 1 if state.active(140.0) else 0
        self.assertEqual(1, state.advance(145.0, window=chain.window_for(next_chain)))
        self.assertAlmostEqual(1.02, state.bonus(chain.EXEMPLAR_CHAIN_BONUS_PER_LINK))


if __name__ == "__main__":
    unittest.main()
