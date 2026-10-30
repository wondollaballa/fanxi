"""Every Caliburnus job's set library has an Imperator weapon-skill set.

The server grants Imperator (233) only while Caliburnus is in the main hand.  A job
library without ``sets.WS["Imperator"]`` therefore has no way to wear the WS set: the
skill can appear in the in-game HUD while Caliburnus is on, but the next equip swap
takes it away and the action runs with whatever weapon is left.  RDM had the Caliburnus
weaponsets but not the WS set, so the set picker and any GearSwap rule keyed on the WS
name had nothing to equip.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMP = re.compile(
    r'sets\.WS(?:\["Imperator"\]|\.Imperator)\s*=\s*\{(.*?)\n\s*\}', re.DOTALL)


class PrimeWeaponSkillSetTest(unittest.TestCase):
    def test_caliburnus_jobs_have_an_imperator_set(self):
        # Caliburnus's item job mask: RDM, PLD, BLU.
        for job in ("RDM", "PLD", "BLU"):
            with self.subTest(job=job):
                text = (ROOT / "gearswap" / f"{job}.lua").read_text(encoding="utf-8")
                match = IMP.search(text)
                self.assertIsNotNone(match, f"{job}.lua has no Imperator WS set")
                self.assertIn('main = "Caliburnus"', match.group(1))


if __name__ == "__main__":
    unittest.main()
