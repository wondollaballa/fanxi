"""Trust support: the damage-first enfeebles and Sylvie's retail aura values.

The reported case: Koru-Moru spent every cast refreshing Protect/Shell/Haste/Refresh/
Phalanx and never put Dia on the monster, and Sylvie's entrusted Defense Down was not
modelled at all.  A MNK's damage then sat well below retail even though the server's
own WS formula was right.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import effects, geomancy, modifiers as mod, trust_ai, trust_stats
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


class TrustSupportTest(unittest.TestCase):
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
        self.session.char.update(main_job=2, main_level=99, sub_job=19, sub_level=49)
        self.session.zone = 100
        self.session.pos = list(self.world.zones.position(100))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True
        self.session.char["hp_current"] = int(self.session.char["hp"])
        self.mob = next(entity for entity in self.session.entities
                        if entity.kind == "mob" and entity.alive)
        self.mob.hp = self.mob.hp_max = 100_000
        self.now = time.time()

    def spawn(self, trust_spell_id: int):
        entity = self.world.spawn_trust(
            self.session, self.service.trust(trust_spell_id), self.now)
        self.assertIsNotNone(entity)
        entity.next_cast_at = 0.0
        entity.mp = entity.mp_max
        return entity

    def test_koru_moru_opens_with_dia_not_a_buff_refresh(self):
        koru = self.spawn(952)
        self.assertTrue(self.world._try_trust_cast(
            koru, self.session, [self.session], self.mob, self.now))
        self.assertEqual("Dia III", koru.casting["spell"]["name"])
        self.assertEqual("debuff", koru.casting["kind"])
        # The effect carries the 20% Defense cut the physical path reads.
        self.assertEqual(effects.DIA, int(koru.casting["effect"].effect))
        self.assertEqual(20, int(koru.casting["effect"].potency))

    def test_sylvie_entrust_lands_defense_down(self):
        sylvie = self.spawn(981)
        # Keep Indi-Fury up on the owner so the next beats are her two monster
        # effects: the Geo-Malaise bubble first, then the entrusted Frailty.
        self.session.add_effect(549, duration=180.0)      # GEO_ATTACK / Indi-Fury
        self.assertTrue(self.world._try_trust_cast(
            sylvie, self.session, [self.session], self.mob, self.now))
        self.assertEqual("Geo-malaise", sylvie.casting["spell"]["name"])
        self.assertEqual("debuff", sylvie.casting["kind"])
        sylvie.casting["finish"] = self.now - 1.0
        self.world._finish_trust_cast(sylvie, self.session, self.now)
        self.assertEqual(
            int(self.mob.effect_state[geomancy.GEO_MAGIC_DEF_DOWN]["potency"]), 30)

        sylvie.next_cast_at = 0.0
        self.assertTrue(self.world._try_trust_cast(
            sylvie, self.session, [self.session], self.mob, self.now + 2))
        self.assertEqual("Indi-frailty", sylvie.casting["spell"]["name"])
        self.assertEqual("debuff", sylvie.casting["kind"])
        sylvie.casting["finish"] = self.now - 1.0
        self.world._finish_trust_cast(sylvie, self.session, self.now)
        state = self.mob.effect_state.get(effects.DEFENSE_DOWN)
        self.assertIsNotNone(state)
        self.assertEqual(12, int(state.get("potency", 0)))
        # The next beat must see the ordinary Defense Down, not look for a GEO aura
        # id that never landed on the monster and recast Entrust forever.
        self.assertIsNone(trust_ai.entrust_debuff_for(
            sylvie.name, sylvie.kit, self.mob.effect_state, self.now + 3))

    def test_sylvie_catalog_has_every_indi_and_geo_spell(self):
        rows = self.service.trust_action_spells(981, 99)
        names = {str(row["name"]) for row in rows}
        indi = {str(row["name"]) for row in self.db.all(
            "SELECT name FROM spells WHERE lower(name) LIKE 'indi-%'")}
        geo = {str(row["name"]) for row in self.db.all(
            "SELECT name FROM spells WHERE lower(name) LIKE 'geo-%'")}
        self.assertEqual(indi - names, set())
        self.assertEqual(geo - names, set())
        # The catalogue is the expanded picker, not just the 20 curated rows.
        self.assertGreaterEqual(len(indi | geo), 60)
        self.assertIn("Geo-frailty", names)
        self.assertIn("Indi-malaise", names)

    def test_the_hud_catalog_uses_the_expanded_spellbook(self):
        rows = self.session._trust_action_catalog(981)
        names = {str(row["name"]) for row in rows}
        self.assertIn("Geo-frailty", names)
        self.assertIn("Indi-malaise", names)
        self.assertIn("Geo-malaise", names)
        self.assertGreater(len(rows), 100)

    def test_every_support_spell_catalog_lists_its_job_spells(self):
        koru = {row["name"] for row in self.service.trust_action_spells(952, 99)}
        self.assertIn("Haste II", koru)
        self.assertIn("Phalanx II", koru)
        self.assertIn("Temper II", koru)          # RDM job-point spell, not curated
        self.assertIn("Refresh III", koru)
        self.assertIn("Flurry", koru)
        ygnas = {row["name"] for row in self.service.trust_action_spells(998, 99)}
        self.assertIn("Cure VI", ygnas)
        joachim = {row["name"] for row in self.service.trust_action_spells(911, 99)}
        self.assertIn("Honor March", joachim)

    def test_a_custom_sylvie_can_cast_geo_frailty(self):
        # 818 is a Geo- hex that is not in her curated 20-spell default list.
        self.session.trust_actions[981] = [818]
        sylvie = self.spawn(981)
        self.assertTrue(self.world._try_trust_cast(
            sylvie, self.session, [self.session], self.mob, self.now))
        self.assertEqual("Geo-frailty", sylvie.casting["spell"]["name"])
        self.assertEqual("debuff", sylvie.casting["kind"])
        sylvie.casting["finish"] = self.now - 1.0
        self.world._finish_trust_cast(sylvie, self.session, self.now)
        state = self.mob.effect_state.get(geomancy.GEO_DEFENSE_DOWN)
        self.assertIsNotNone(state)
        self.assertEqual(27, int(state.get("potency", 0)))

    def test_trust_upgrades_raise_bars_and_stats(self):
        cid = int(self.character["id"])
        self.assertEqual(0, self.service.trust_upgrade_level(cid))
        self.assertEqual(50, self.service.max_trust_upgrades(cid))
        self.assertEqual(50, self.service.trust_upgrade_level(cid))
        summary = self.service.trust_summary(cid)
        self.assertEqual(50, summary["upgrade_level"])
        self.assertEqual(50, summary["upgrade_max"])

        trust = self.spawn(952)
        base_hp, base_mp = trust_stats.vitals(
            trust.race, trust.job, trust.sub_job, int(trust.level))
        self.assertEqual(int(base_hp) + 250, int(trust.hp_max))
        self.assertEqual(int(base_mp) + 100, int(trust.mp_max))
        self.assertGreaterEqual(int(trust.shared_mods.get(mod.STR, 0)), 50)
        self.assertGreaterEqual(int(trust.shared_mods.get(mod.ACC, 0)), 50)
        self.assertEqual(50, int(trust.trust_upgrade_level))

    def test_sylvie_uses_the_retail_trust_aura_values(self):
        fury = trust_ai.effect_of({"name": "Indi-Fury"}, trust_name="Sylvie Uc")
        self.assertEqual(37, fury.mods.get(mod.ATT_PERCENT))
        self.assertEqual(37, fury.mods.get(mod.RATT))
        precision = trust_ai.effect_of({"name": "Indi-Precision"},
                                       trust_name="Sylvie Uc")
        self.assertEqual(56, precision.mods.get(mod.ACC))
        haste = trust_ai.effect_of({"name": "Indi-Haste"}, trust_name="Sylvie Uc")
        self.assertEqual(2880, haste.mods.get(mod.HASTE_ABILITY))
        # The player's own Geomancy+0 column is unchanged.
        player = trust_ai.effect_of({"name": "Indi-Fury"})
        self.assertEqual(10, player.mods.get(mod.ATT_PERCENT))

    def test_koru_upgrades_haste_and_phalanx_tiers(self):
        """A tier-I status must not hide the stronger tier the Trust carries."""
        kit = trust_ai.build_kit(
            self.service.trust_spells(952, 99), 99, 5, "Koru-Moru")
        now = time.time()
        self.session.add_effect(effects.HASTE, duration=600,
                                mods={mod.HASTE_MAGIC: 1500})
        self.session.add_effect(effects.PHALANX, duration=600, power=20)
        for name in ("Protect V", "Shell V", "Refresh II"):
            spec = effects.for_spell(name)
            self.session.add_effect(spec.effect, duration=600, mods=spec.mods)
        self.assertEqual("Haste II", trust_ai.buff_for(
            kit, self.session.effect_state, now)["name"])
        haste = effects.for_spell("Haste II")
        self.session.add_effect(haste.effect, duration=600, mods=haste.mods)
        self.assertEqual("Phalanx II", trust_ai.buff_for(
            kit, self.session.effect_state, now)["name"])

    def test_phalanx_ii_has_its_flat_absorption(self):
        """The generated icon row has no power; the RDM tier is 240 s at -35/hit."""
        phalanx = effects.for_spell("Phalanx II")
        self.assertEqual(effects.PHALANX, phalanx.effect)
        self.assertEqual(240, int(phalanx.duration))
        self.assertEqual(35, int(phalanx.power))

    def test_koru_kit_and_opening_debuff(self):
        kit = trust_ai.build_kit(
            self.service.trust_spells(952, 99), 99, 5, "Koru-Moru")
        names = [spell["name"] for spell in kit.get("debuff", [])]
        self.assertIn("Dia III", names)
        self.assertIn("Slow II", names)
        opening = trust_ai.opening_debuff_for(kit, {}, self.now)
        self.assertEqual("Dia III", opening["name"])


if __name__ == "__main__":
    unittest.main()
