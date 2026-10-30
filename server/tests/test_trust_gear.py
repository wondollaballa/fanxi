"""Trust loadouts: the weapons they carry and the gear they inherit from their owner."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import effects, modifiers as mod, trust_ai, trust_gear


class TrustGearTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))

    def character(self, name: str = "Fanxi") -> dict:
        account = self.service.register(name.lower(), "password123").account
        return self.service.create_character(account["id"], {"name": name, "race": 1})

    def test_sylvie_carries_idris_and_uses_its_geomancy_column(self):
        """Idris is Geomancy +10: her auras take BGWiki's Idris values."""
        gear = trust_gear.loadout(self.service, 981)
        self.assertEqual(gear.items, (21080,))
        self.assertTrue(gear.idris)
        self.assertEqual(gear.geomancy_plus, 10)

        precision = trust_ai.effect_of({"name": "Indi-precision"}, gear.geomancy_plus)
        self.assertEqual(precision.mods, {mod.ACC: 50})
        frailty = trust_ai.effect_of({"name": "Indi-frailty"}, gear.geomancy_plus)
        self.assertEqual(frailty.potency, 27)         # 27% Defense cut
        # The plain table is what a Geomancer without the mythic casts.
        plain = trust_ai.effect_of({"name": "Indi-precision"})
        self.assertEqual(plain.mods, {mod.ACC: 10})

    def test_joachim_carries_the_prime_loughnashade(self):
        """The final Loughnashade is Song+4 and two song slots in one horn."""
        gear = trust_gear.loadout(self.service, 911)
        self.assertEqual(gear.items, (22307,))        # iLvl 119 III Loughnashade
        self.assertEqual(gear.mods.get(mod.MAXIMUM_SONGS_BONUS), 2)
        self.assertEqual(gear.mods.get(mod.ALL_SONGS_EFFECT), 4)
        self.assertEqual(gear.mods.get(mod.CHR), 20)
        self.assertEqual(effects.song_slots(10, 41, gear.mods), 4)

        spec = effects.for_spell("Victory March")
        base_mods, _tick = effects.song_potency_values("Victory March", spec, {})
        gear_mods, _tick = effects.song_potency_values(
            "Victory March", spec, gear.mods)
        self.assertGreater(gear_mods[mod.HASTE_MAGIC], base_mods[mod.HASTE_MAGIC])
        # Song+4 alone is 40% more timer; the Daurdabla's 30% line is gone with the pair.
        self.assertGreater(effects.song_duration(
            spec, name="Victory March", mods=gear.mods), spec.duration * 1.3)

    def test_joachim_sings_what_the_owner_needs(self):
        """Songs by role: the March line, Attack or Aria, then Accuracy in the spare slot.

        The March slot is Victory March while its Haste is worth something and Honor March
        once magic haste is capped (they share the March status, so it is one or the
        other).  The Loughnashade's four slots only fill when Accuracy is short.  Paeon,
        Ballad and Elegy stay off a melee owner's plan.
        """
        kit = trust_ai.build_kit(self.service.trust_spells(911, 99), 99, 10, "Joachim")
        self.assertEqual(kit["buff"], [])            # songs left the buff rotation
        self.assertEqual(kit["debuff"], [])
        names = [spell["name"] for spell in kit["song"]]
        self.assertIn("Victory March", names)
        self.assertIn("Honor March", names)          # same status, its own plan entry
        self.assertNotIn("Valor Minuet IV", names)   # one Minuet line: the highest tier wins
        self.assertNotIn("Valor Minuet III", names)
        # The full tier list is still available so an explicit owner set can name Minuet IV.
        all_names = [spell["name"] for spell in kit["song_all"]]
        self.assertIn("Valor Minuet IV", all_names)
        self.assertIn("Valor Minuet V", all_names)
        self.assertIn("Armys Paeon VI", all_names)

        def planned(**need):
            return [spell["name"] for spell in trust_ai.choose_songs(kit, trust_ai.SongNeed(**need))]

        self.assertEqual(planned(), ["Victory March", "Valor Minuet V"])
        # Victory March's Haste fits only while the owner's own magic haste leaves room.
        self.assertEqual(planned(haste_percent=0.15), ["Victory March", "Valor Minuet V"])
        # Haste II alone (30%) plus a March already overshoots the 43.75% cap, so the
        # March slot is worth more as Honor March's Attack and Accuracy.
        self.assertEqual(planned(haste_percent=0.30), ["Honor March", "Valor Minuet V"])
        self.assertEqual(planned(haste_percent=0.4375), ["Honor March", "Valor Minuet V"])
        self.assertEqual(planned(haste_percent=0.4375, attack_capped=True),
                         ["Honor March", "Aria of Passion"])
        # A swing that lands under 95% earns the Madrigal line in the free slot.
        self.assertEqual(planned(hit_rate=0.80),
                         ["Victory March", "Valor Minuet V", "Blade Madrigal"])
        self.assertEqual(planned(haste_percent=0.4375, attack_capped=True, hit_rate=0.80),
                         ["Honor March", "Aria of Passion", "Blade Madrigal"])
        # A mage's role wins over the attack plan: the ballad is what it needs.
        self.assertEqual(planned(haste_percent=0.4375, attack_capped=True, caster=True),
                         ["Mages Ballad III"])
        self.assertEqual(planned(caster=True), ["Mages Ballad III"])
        self.assertEqual(planned(ranged=True),
                         ["Victory March", "Archers Prelude", "Valor Minuet V"])

        def at_level(level):
            low = trust_ai.build_kit(self.service.trust_spells(911, level), level, 10,
                                     "Joachim")
            return [spell["name"] for spell in
                    trust_ai.choose_songs(low, trust_ai.SongNeed())]

        # Below Valor Minuet V's level, the lower tiers are what he can give.
        self.assertEqual(at_level(70), ["Victory March", "Valor Minuet IV"])
        self.assertEqual(at_level(60), ["Victory March", "Valor Minuet III"])
        # Paeon and Elegy are never on any plan; Madrigal only when Accuracy is short.
        every = set()
        for need in ({}, {"caster": True}, {"ranged": True}, {"attack_capped": True}):
            every.update(planned(**need))
        self.assertFalse(every & {"Armys Paeon VI", "Carnage Elegy"})
        self.assertNotIn("Blade Madrigal", every)

    def test_joachim_plays_the_owners_explicit_set(self):
        """A saved set overrides the role plan, in the owner's order, including two Minuets.

        Minuet V and IV share the Minuet icon but are separate songs on the four-song bar;
        the explicit path keeps both because `song_all` retains every tier.
        """
        kit = trust_ai.build_kit(self.service.trust_spells(911, 99), 99, 10, "Joachim")
        by_name = {spell["name"]: int(spell["id"]) for spell in kit["song_all"]}
        chosen = [
            by_name["Aria of Passion"],
            by_name["Valor Minuet V"],
            by_name["Valor Minuet IV"],
            by_name["Honor March"],
        ]
        planned = trust_ai.choose_songs(
            kit, trust_ai.SongNeed(ranged=True, caster=True), chosen)
        self.assertEqual([spell["name"] for spell in planned], [
            "Aria of Passion", "Valor Minuet V", "Valor Minuet IV", "Honor March"])
        # A stored id the owner has outlevelled is skipped rather than crashing the plan.
        locked = [by_name["Aria of Passion"], 999999, by_name["Honor March"]]
        self.assertEqual(
            [spell["name"] for spell in trust_ai.choose_songs(kit, trust_ai.SongNeed(), locked)],
            ["Aria of Passion", "Honor March"])
        # The role plan still chooses only the highest Minuet.
        self.assertEqual(
            [spell["name"] for spell in trust_ai.choose_songs(kit, trust_ai.SongNeed())],
            ["Victory March", "Valor Minuet V"])

    def test_a_selected_spell_pool_restricts_the_rotation(self):
        """Only the chosen spells remain, in the owner's order, for the default AI."""
        kit = trust_ai.build_kit(
            self.service.trust_spells(952, 99), 99, 5, "Koru-moru")
        restricted = trust_ai.restrict_kit(kit, [511, 473])
        self.assertEqual([spell["name"] for spell in restricted["buff"]],
                         ["Haste II", "Refresh II"])
        self.assertEqual(restricted["cure"], [])
        self.assertEqual(restricted["debuff"], [])
        self.assertTrue(restricted["caster"])
        self.assertEqual(restricted["action_kind"], {511: "buff", 473: "buff"})

    def test_selected_rolls_are_a_priority_order(self):
        """The first selected roll wins; a roll another Corsair has up falls through."""
        chaos = trust_ai.ROLL_IDS["chaos"]
        samurai = trust_ai.ROLL_IDS["samurai"]
        self.assertEqual(
            trust_ai.choose_roll(trust_ai.RollNeed(melee=1), [samurai, chaos]),
            samurai)
        self.assertEqual(
            trust_ai.choose_roll(
                trust_ai.RollNeed(melee=1, active=frozenset(
                    {trust_ai.ROLL_STATUS["samurai"]})),
                [samurai, chaos]),
            chaos)

    def test_the_owner_gear_rating_scales_the_shared_stats(self):
        """A Master in endgame gear lends the Trust half of what that gear gives."""
        character = self.character()
        self.assertEqual(self.service.equipped_gear_rating(character["id"]), 0)
        self.assertEqual(trust_gear.share(self.service, character["id"]), {})

        pieces = self.db.all(
            "SELECT item_id FROM items WHERE item_level = 119 "
            "GROUP BY equip_slot ORDER BY item_id LIMIT 5")
        for kind, row in enumerate(pieces):
            self.db.execute(
                "INSERT OR REPLACE INTO char_equip "
                "(character_id, kind, container, slot, item_id) VALUES (?, ?, 0, ?, ?)",
                (int(character["id"]), 4 + kind, kind, int(row["item_id"])))

        self.assertEqual(self.service.equipped_gear_rating(character["id"]), 119)
        shared = trust_gear.share(self.service, character["id"])
        gear = self.service.equipped_mods(character["id"])
        self.assertEqual(shared.get(mod.HP, 0), int(int(gear.get(mod.HP, 0)) * 50 // 100))


if __name__ == "__main__":
    unittest.main()
