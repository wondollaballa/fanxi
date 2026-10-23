"""The item extdata block the client decodes into augment lines."""

import unittest

from server.fanxi_server.game import augments


class AugmentTest(unittest.TestCase):
    def test_retail_rank_25_neck_decodes(self):
        # A real Assassin's Gorget +2 at rank 25: path/type 0, rank 25, max tier 25, bundle 204.
        build = augments.decode(bytes.fromhex("03830000782D6403CC00000000"))
        self.assertEqual(build["path"], "A")
        self.assertEqual(build["rank"], 25)
        self.assertEqual(build["tier"], 2)
        self.assertEqual(build["index"], 204)

    def test_rank_30_block_round_trips(self):
        for path in "ABCD":
            block = augments.bundle(path, 30, 3, 7)
            self.assertEqual(len(block), 24)
            self.assertEqual(block[0], 0x03)
            self.assertEqual(block[1], 0x83)
            build = augments.decode(block)
            self.assertEqual(build["path"], path)
            self.assertEqual(build["rank"], 30)
            self.assertEqual(build["tier"], 3)
            self.assertEqual(build["index"], 7)

    def test_bad_input_is_rejected(self):
        with self.assertRaises(ValueError):
            augments.bundle("E", 30, 3)
        with self.assertRaises(ValueError):
            augments.bundle("A", 31, 3)
        with self.assertRaises(ValueError):
            augments.bundle("A", 30, 4)

    def test_unsigned_blocks_are_ignored(self):
        self.assertIsNone(augments.decode(b"\0" * 24))
        self.assertIsNone(augments.decode(b""))


if __name__ == "__main__":
    unittest.main()
