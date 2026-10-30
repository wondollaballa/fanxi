"""The main-job table for the relic/mythic/empyrean and merit weapon skills.

These are the ids whose availability is not decided by the weapon skill value alone.
The checks are deliberately small: the server regression tests in ``test_world.py``
exercise the live 0x0AC list, while this pins the table's shape and the entries whose
job lists are easy to get wrong (the merit skills have wider lists than their names
suggest).
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  (puts the server package on sys.path for unittest discover)

from fanxi_server.game import skills, weapon_skill_jobs, weapon_skills


class WeaponSkillJobsTest(unittest.TestCase):
    def test_every_id_is_a_real_weapon_skill(self):
        # Dagan (173) and Myrkr (190) are in the weapon_skills table and in
        # weapon_skill_effects, but LandSandBoat has no damage-script row for them;
        # the server uses its generic fTP curve and the effect row instead.
        for ws_id in weapon_skill_jobs.WEAPON_SKILL_JOBS:
            if ws_id in (173, 190):
                continue
            self.assertIsNotNone(weapon_skills.for_id(ws_id), "unknown weapon skill %d" % ws_id)

    def test_masks_only_use_the_client_job_bits(self):
        all_jobs = 0
        for name, bit in weapon_skill_jobs.JOB_BITS.items():
            self.assertIn(name, {value.upper() for value in skills.JOB_KEYS.values()})
            all_jobs |= bit
        self.assertEqual(all_jobs, (1 << 22) - 1)
        for ws_id, mask in weapon_skill_jobs.WEAPON_SKILL_JOBS.items():
            self.assertTrue(mask > 0, "weapon skill %d has an empty mask" % ws_id)
            self.assertEqual(mask & ~all_jobs, 0,
                             "weapon skill %d has a bit past RUN" % ws_id)

    def test_merit_lists_are_wider_than_one_job(self):
        """The merit rows are character-wide, so several jobs may press the button."""
        self.assertTrue(weapon_skill_jobs.allowed(226, 17))   # Requiescat: COR
        self.assertTrue(weapon_skill_jobs.allowed(226, 7))    # Requiescat: PLD
        self.assertFalse(weapon_skill_jobs.allowed(226, 11))  # Requiescat: not RNG
        self.assertTrue(weapon_skill_jobs.allowed(224, 17))   # Exenterator: COR
        self.assertTrue(weapon_skill_jobs.allowed(221, 6))    # Last Stand: THF
        self.assertTrue(weapon_skill_jobs.allowed(221, 17))   # Last Stand: COR
        self.assertFalse(weapon_skill_jobs.allowed(60, 17))   # Resolution: not COR

    def test_relic_and_mythic_lists_follow_the_weapons(self):
        self.assertTrue(weapon_skill_jobs.allowed(220, 17))   # Wildfire: COR
        self.assertTrue(weapon_skill_jobs.allowed(220, 11))   # Wildfire: RNG
        self.assertFalse(weapon_skill_jobs.allowed(220, 7))   # Wildfire: not PLD
        self.assertFalse(weapon_skill_jobs.allowed(216, 17))  # Coronach: RNG only
        self.assertTrue(weapon_skill_jobs.allowed(45, 7))     # Atonement: PLD
        self.assertFalse(weapon_skill_jobs.allowed(45, 17))   # Atonement: not COR
        self.assertFalse(weapon_skill_jobs.allowed(43, 17))   # Knights of Round: not COR

    def test_unlisted_skills_and_custom_jobs_are_unrestricted(self):
        self.assertTrue(weapon_skill_jobs.allowed(42, 17))    # Savage Blade, ordinary
        self.assertTrue(weapon_skill_jobs.allowed(42, 0))     # job not known yet
        self.assertTrue(weapon_skill_jobs.allowed(220, 23))   # reserved custom-job slot


if __name__ == "__main__":
    unittest.main()
