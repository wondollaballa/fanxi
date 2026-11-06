"""Weapon-slot rules: TP resets, two-handed hands and ranged ammunition compatibility."""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession

# Low-level, all-job items so the tests are about the hand/ammo rules and not the
# catalogue's job masks.  The setup relaxes any job/level bits the rows still carry.
ONION_SWORD = 16534       # one-handed sword
BRONZE_SWORD = 16535      # a second one-handed sword
EPEOLATRY = 21685         # great sword
GREAT_AXE = 20843         # great axe
SAKPATAS_FISTS = 21527    # hand-to-hand
UTU_GRIP = 22212          # grip
POLE_GRIP = 19025         # a second grip
GENBUS_SHIELD = 12296     # shield
ACHERON_SHIELD = 12385    # a second shield
SHORTBOW = 17152          # archery, skill 25
CROSSBOW = 17217          # marksmanship, skill 26, subskill 0
MARTIAL_GUN = 17210       # marksmanship, skill 26, subskill 1
WOODEN_ARROW = 17318      # ammo, skill 25
BONE_ARROW = 17319        # a second arrow
CROSSBOW_BOLT = 17336     # ammo, skill 26, subskill 0
BULLET = 17340            # ammo, skill 26, subskill 1
SHURIKEN = 17301          # throwing ammo, skill 27
STAUNCH_TATHLUM = 22279   # non-weapon ammo, skill 0

TEST_ITEMS = (ONION_SWORD, BRONZE_SWORD, EPEOLATRY, GREAT_AXE, SAKPATAS_FISTS,
              UTU_GRIP, POLE_GRIP, GENBUS_SHIELD, ACHERON_SHIELD, SHORTBOW, CROSSBOW,
              MARTIAL_GUN, WOODEN_ARROW, BONE_ARROW, CROSSBOW_BOLT, BULLET, SHURIKEN,
              STAUNCH_TATHLUM)


def chats(session):
    lines = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        lines.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return lines


class EquipmentRulesTest(unittest.TestCase):
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
        self.session.zone = 246
        self.session.char.update(main_job=11, main_level=99, sub_job=0, sub_level=0)
        # The catalogue rows are real, but their job/level gates would hide the hand
        # and ammo rules.  Make these test copies wearable by the RNG above.
        self.db.execute(
            "UPDATE items SET jobs = 0, level = 1 WHERE item_id IN (%s)"
            % ",".join("?" for _ in TEST_ITEMS), TEST_ITEMS)

    def give(self, slot: int, item_id: int, container: int = 0) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, ?, ?, ?, 1)",
            (int(self.character["id"]), int(container), int(slot), int(item_id)))

    def equip(self, slot: int, kind: int, category: int = 0) -> None:
        self.session.equip(bytes((0x50, 4, 0, 0, slot, kind, category, 0)))

    def last_tp(self):
        """The TP in the most recent 0x0DF party row, in tenths."""
        for message in reversed(self.session.queue):
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x0DF:
                return struct.unpack_from("<I", message, 16)[0]
        return None

    # --- TP -------------------------------------------------------------------------------
    def test_changing_main_resets_tp(self):
        self.give(1, ONION_SWORD)
        self.give(2, BRONZE_SWORD)
        self.equip(1, 0)
        self.session.char["tp"] = 1500
        self.session.queue.clear()

        self.equip(2, 0)

        self.assertEqual(int(self.session.char["tp"]), 0)
        self.assertEqual(self.last_tp(), 0)

    def test_changing_a_sub_weapon_resets_tp(self):
        self.give(1, ONION_SWORD)
        self.give(2, BRONZE_SWORD)
        self.give(3, ONION_SWORD)  # a second copy for the off hand
        self.equip(1, 0)
        self.equip(2, 1)
        self.session.char["tp"] = 1500
        self.session.queue.clear()

        self.equip(3, 1)

        self.assertEqual(int(self.session.char["tp"]), 0)
        self.assertEqual(self.last_tp(), 0)

    def test_swapping_grips_shields_ranged_and_ammo_keeps_tp(self):
        self.give(1, EPEOLATRY)
        self.give(2, UTU_GRIP)
        self.give(3, POLE_GRIP)
        self.give(4, ONION_SWORD)
        self.give(5, GENBUS_SHIELD)
        self.give(6, ACHERON_SHIELD)
        self.give(7, SHORTBOW)
        self.give(8, CROSSBOW)
        self.give(9, WOODEN_ARROW)
        self.give(10, BONE_ARROW)

        # Grip on a two-handed main.
        self.equip(1, 0)
        self.equip(2, 1)
        self.session.char["tp"] = 1200
        self.session.queue.clear()
        self.equip(3, 1)
        self.assertEqual(int(self.session.char["tp"]), 1200)
        self.assertIsNone(self.last_tp())

        # Shield on a one-handed main.
        self.equip(4, 0)
        self.equip(5, 1)
        self.session.char["tp"] = 1100
        self.session.queue.clear()
        self.equip(6, 1)
        self.assertEqual(int(self.session.char["tp"]), 1100)
        self.assertIsNone(self.last_tp())

        # Ranged weapon.
        self.equip(7, 2)
        self.session.char["tp"] = 1000
        self.session.queue.clear()
        self.equip(8, 2)
        self.assertEqual(int(self.session.char["tp"]), 1000)
        self.assertIsNone(self.last_tp())

        # Ammo, with a bow again so both arrows are legal.
        self.equip(7, 2)
        self.equip(9, 3)
        self.session.char["tp"] = 900
        self.session.queue.clear()
        self.equip(10, 3)
        self.assertEqual(int(self.session.char["tp"]), 900)
        self.assertIsNone(self.last_tp())

    def test_re_sending_the_same_copy_keeps_tp(self):
        self.give(1, ONION_SWORD)
        self.equip(1, 0)
        self.session.char["tp"] = 1234
        self.session.queue.clear()

        self.equip(1, 0)  # a gear burst re-sends the worn weapon

        self.assertEqual(int(self.session.char["tp"]), 1234)
        self.assertIsNone(self.last_tp())

    def test_removing_a_weapon_resets_tp_but_removing_ammo_does_not(self):
        self.give(1, ONION_SWORD)
        self.give(2, WOODEN_ARROW)
        self.equip(1, 0)
        self.session.char["tp"] = 900
        self.session.queue.clear()
        self.equip(0, 0)  # slot 0 form: remove main
        self.assertEqual(int(self.session.char["tp"]), 0)
        self.assertEqual(self.last_tp(), 0)

        self.equip(2, 3)
        self.session.char["tp"] = 700
        self.session.queue.clear()
        self.equip(0, 3)  # removing ammo keeps the bar
        self.assertEqual(int(self.session.char["tp"]), 700)
        self.assertIsNone(self.last_tp())

    def test_removing_a_sub_weapon_resets_tp_but_a_grip_does_not(self):
        self.give(1, ONION_SWORD)
        self.give(2, BRONZE_SWORD)
        self.give(3, EPEOLATRY)
        self.give(4, UTU_GRIP)
        self.equip(1, 0)
        self.equip(2, 1)
        self.session.char["tp"] = 800
        self.session.queue.clear()
        self.equip(0, 1)  # remove the off-hand weapon
        self.assertEqual(int(self.session.char["tp"]), 0)

        self.equip(3, 0)  # two-handed main
        self.equip(4, 1)  # grip
        self.session.char["tp"] = 600
        self.session.queue.clear()
        self.equip(0, 1)  # removing a grip keeps the bar
        self.assertEqual(int(self.session.char["tp"]), 600)
        self.assertIsNone(self.last_tp())

    # --- two-handed hands ----------------------------------------------------------------
    def test_a_two_handed_main_leaves_only_a_grip_in_the_sub_slot(self):
        self.give(1, ONION_SWORD)
        self.give(2, BRONZE_SWORD)
        self.give(3, EPEOLATRY)
        self.give(4, UTU_GRIP)
        self.give(5, GENBUS_SHIELD)

        self.equip(1, 0)
        self.equip(2, 1)
        self.assertIn(1, self.session.equipped)

        self.equip(3, 0)  # a great sword fills both hands
        self.assertNotIn(1, self.session.equipped)

        self.session.queue.clear()
        self.equip(2, 1)  # another weapon cannot be dual-wielded with it
        self.assertNotIn(1, self.session.equipped)
        self.assertTrue(any("two-handed" in line for line in chats(self.session)))

        self.session.queue.clear()
        self.equip(5, 1)  # a shield is not a sub item for a two-hander either
        self.assertNotIn(1, self.session.equipped)
        self.assertTrue(any("two-handed" in line for line in chats(self.session)))

        self.equip(4, 1)  # the grip is the one legal sub item
        self.assertEqual(self.session.equipped[1], (0, 4, UTU_GRIP))

    def test_a_two_handed_weapon_cannot_be_worn_in_the_off_hand(self):
        self.give(1, ONION_SWORD)
        self.give(2, GREAT_AXE)
        # Prove the rule does not depend on the catalogue's slot mask: a missing mask
        # must not turn a great axe into a legal off-hand weapon.
        self.db.execute("UPDATE items SET slot_mask = 0 WHERE item_id = ?", (GREAT_AXE,))
        self.equip(1, 0)
        self.session.queue.clear()

        self.equip(2, 1)

        self.assertNotIn(1, self.session.equipped)
        self.assertTrue(any("off hand" in line for line in chats(self.session)))

    def test_hand_to_hand_leaves_only_a_shield_in_the_sub_slot(self):
        self.give(1, SAKPATAS_FISTS)
        self.give(2, BRONZE_SWORD)
        self.give(3, GENBUS_SHIELD)
        self.equip(1, 0)
        self.session.queue.clear()

        self.equip(2, 1)
        self.assertNotIn(1, self.session.equipped)
        self.assertTrue(any("hand-to-hand" in line for line in chats(self.session)))

        self.equip(3, 1)
        self.assertEqual(self.session.equipped[1][2], GENBUS_SHIELD)

    def test_a_one_handed_main_can_still_dual_wield(self):
        self.give(1, ONION_SWORD)
        self.give(2, BRONZE_SWORD)
        self.equip(1, 0)
        self.equip(2, 1)
        self.assertEqual(self.session.equipped[0][2], ONION_SWORD)
        self.assertEqual(self.session.equipped[1][2], BRONZE_SWORD)

    # --- ranged ammunition ---------------------------------------------------------------
    def test_a_bow_takes_arrows_and_refuses_bullets(self):
        self.give(1, SHORTBOW)
        self.give(2, WOODEN_ARROW)
        self.give(3, BULLET)
        self.equip(1, 2)
        self.equip(2, 3)
        self.assertEqual(self.session.equipped[3][2], WOODEN_ARROW)

        self.session.queue.clear()
        self.equip(3, 3)
        self.assertEqual(self.session.equipped[3][2], WOODEN_ARROW)
        self.session.flush_equipment()
        self.assertEqual(self.session.equipped[3][2], WOODEN_ARROW)
        self.assertTrue(any("not compatible" in line for line in chats(self.session)))

    def test_a_crossbow_takes_bolts_and_refuses_bullets(self):
        self.give(1, CROSSBOW)
        self.give(2, CROSSBOW_BOLT)
        self.give(3, BULLET)
        self.equip(1, 2)
        self.equip(2, 3)
        self.assertEqual(self.session.equipped[3][2], CROSSBOW_BOLT)

        self.session.queue.clear()
        self.equip(3, 3)
        self.assertEqual(self.session.equipped[3][2], CROSSBOW_BOLT)
        self.session.flush_equipment()
        self.assertEqual(self.session.equipped[3][2], CROSSBOW_BOLT)
        self.assertTrue(any("not compatible" in line for line in chats(self.session)))

    def test_a_gun_takes_bullets_and_refuses_bolts(self):
        self.give(1, MARTIAL_GUN)
        self.give(2, BULLET)
        self.give(3, CROSSBOW_BOLT)
        self.equip(1, 2)
        self.equip(2, 3)
        self.assertEqual(self.session.equipped[3][2], BULLET)

        self.session.queue.clear()
        self.equip(3, 3)
        self.assertEqual(self.session.equipped[3][2], BULLET)
        self.session.flush_equipment()
        self.assertEqual(self.session.equipped[3][2], BULLET)
        self.assertTrue(any("not compatible" in line for line in chats(self.session)))

    def test_changing_the_ranged_weapon_clears_incompatible_ammo(self):
        self.give(1, CROSSBOW)
        self.give(2, CROSSBOW_BOLT)
        self.give(3, MARTIAL_GUN)
        self.equip(1, 2)
        self.equip(2, 3)
        self.assertIn(3, self.session.equipped)

        self.equip(3, 2)  # crossbow -> gun in the range slot
        self.assertNotIn(3, self.session.equipped)

        self.give(4, BULLET)
        self.equip(4, 3)
        self.assertEqual(self.session.equipped[3][2], BULLET)

    def test_throwing_ammo_needs_an_empty_ranged_slot(self):
        self.give(1, MARTIAL_GUN)
        self.give(2, SHURIKEN)
        self.equip(1, 2)
        self.session.queue.clear()

        self.equip(2, 3)
        self.assertNotIn(3, self.session.equipped)
        self.session.flush_equipment()
        self.assertNotIn(3, self.session.equipped)
        self.assertTrue(any("throwing ammunition" in line for line in chats(self.session)))

        self.equip(0, 2)  # remove the gun
        self.equip(2, 3)
        self.assertEqual(self.session.equipped[3][2], SHURIKEN)

    def test_a_wear_set_can_send_ammo_before_the_ranged_weapon(self):
        """The launcher's BTreeMap sends ammo first; the later range pick still applies it."""
        self.give(1, CROSSBOW)
        self.give(2, CROSSBOW_BOLT)
        self.equip(1, 2)
        self.equip(2, 3)
        self.assertEqual(self.session.equipped[3][2], CROSSBOW_BOLT)

        self.give(3, MARTIAL_GUN)
        self.give(4, BULLET)
        self.session.queue.clear()
        self.equip(4, 3)  # ammo first: it waits for the gun
        self.assertEqual(self.session.equipped[3][2], CROSSBOW_BOLT)
        self.assertIsNotNone(self.session._pending_ammo)

        self.equip(3, 2)  # the gun arrives, clears the bolt and accepts the bullet
        self.assertEqual(self.session.equipped[2][2], MARTIAL_GUN)
        self.assertEqual(self.session.equipped[3][2], BULLET)
        self.assertIsNone(self.session._pending_ammo)

    def test_deferred_ammo_is_rejected_when_no_ranged_weapon_makes_it_legal(self):
        self.give(1, SHORTBOW)
        self.give(2, WOODEN_ARROW)
        self.give(3, BULLET)
        self.equip(1, 2)
        self.equip(2, 3)
        self.session.queue.clear()

        self.equip(3, 3)
        self.assertEqual(self.session.equipped[3][2], WOODEN_ARROW)
        self.assertIsNotNone(self.session._pending_ammo)
        self.session.flush_equipment()
        self.assertEqual(self.session.equipped[3][2], WOODEN_ARROW)
        self.assertIsNone(self.session._pending_ammo)
        self.assertTrue(any("not compatible" in line for line in chats(self.session)))

    def test_ammo_still_has_to_be_for_the_main_job(self):
        # The gun is all-job in this fixture; the bullet stays Ranger-only.
        self.db.execute("UPDATE items SET jobs = ? WHERE item_id = ?",
                        (1 << 10, BULLET))  # RNG is job 11, bit 10
        self.give(1, MARTIAL_GUN)
        self.give(2, BULLET)
        self.session.char.update(main_job=1, main_level=99)  # WAR
        self.equip(1, 2)
        self.session.queue.clear()

        self.equip(2, 3)

        self.assertNotIn(3, self.session.equipped)
        self.assertIsNone(self.session._pending_ammo)
        self.assertTrue(any("not for your job" in line for line in chats(self.session)))

    def test_non_weapon_ammo_is_legal_with_a_ranged_weapon(self):
        self.give(1, MARTIAL_GUN)
        self.give(2, STAUNCH_TATHLUM)
        self.equip(1, 2)
        self.equip(2, 3)
        self.assertEqual(self.session.equipped[3][2], STAUNCH_TATHLUM)

        # Fishing bait is skill 48, not a ranged ammo family; it stays legal.
        self.db.execute("UPDATE items SET jobs = 0, level = 1 WHERE item_id = 17405")
        self.give(3, 17405)  # Fly Lure
        self.equip(3, 3)
        self.assertEqual(self.session.equipped[3][2], 17405)

    def test_ranged_subtypes_came_through_the_catalogue(self):
        expected = {SHORTBOW: 0, CROSSBOW: 0, MARTIAL_GUN: 1, WOODEN_ARROW: 0,
                    CROSSBOW_BOLT: 0, BULLET: 1, SHURIKEN: 3}
        for item_id, subskill in expected.items():
            row = self.db.one("SELECT subskill FROM items WHERE item_id = ?", (item_id,))
            self.assertEqual(int(row["subskill"]), subskill, item_id)


if __name__ == "__main__":
    unittest.main()
