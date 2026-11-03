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

from fanxi_server.game import effects, modifiers as mod, trust_ai
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
        # Keep Indi-Fury up on the owner so the next beat is the Entrust cast.
        self.session.add_effect(549, duration=180.0)      # GEO_ATTACK / Indi-Fury
        self.assertTrue(self.world._try_trust_cast(
            sylvie, self.session, [self.session], self.mob, self.now))
        self.assertEqual("Indi-frailty", sylvie.casting["spell"]["name"])
        self.assertEqual("debuff", sylvie.casting["kind"])
        sylvie.casting["finish"] = self.now - 1.0
        self.world._finish_trust_cast(sylvie, self.session, self.now)
        state = self.mob.effect_state.get(effects.DEFENSE_DOWN)
        self.assertIsNotNone(state)
        self.assertEqual(12, int(state.get("potency", 0)))

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
