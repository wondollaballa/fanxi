-- Unity +1 gear augments (migration 83).
--
-- Unity Wanted iLvl 119 +1 equipment is augmented at a Unity NPC.  The client
-- stores the result in the same 24-byte AugmentBundle block Odyssey uses, at
-- Rank 15 and max-rank tier 0 (the 15-rank unlock), one path.  The bundle index
-- selects the item's row in the client's augment table; the rows below are the
-- Rank 15 lines from the GearSwap libraries and the item pages.
--
-- Generated from server/fanxi_server/game/unity.py by tools/gen_unity.py.

-- 27509 Unmoving Collar +1: DEF+30 / HP+200 (bundle 305)
-- 27549 Odnowa Earring +1: DEF+30 / Damage taken-3% (bundle 367)
-- 10769 Gelatinous Ring +1: VIT+15 / HP+100 (bundle 316)
-- 21344 Ghastly Tathlum +1: Magic Damage +10 / INT+5 (bundle 343)
-- 25636 Loess Barbuta +1: Enmity+10 / Damage taken-10% / All Attr.+10 (bundle 376)

UPDATE char_inventory SET extra = X'0383000000003C0031010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27509;
UPDATE char_inventory SET extra = X'0383000000003C006F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27549;
UPDATE char_inventory SET extra = X'0383000000003C003C010000000000000000000000000000' WHERE character_id = 1 AND item_id = 10769;
UPDATE char_inventory SET extra = X'0383000000003C0057010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21344;
UPDATE char_inventory SET extra = X'0383000000003C0078010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25636;
