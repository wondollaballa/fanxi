-- Put the new coatings in the Battle Bag so they are usable immediately after
-- login.  They still load from the inventory through //chm load if removed.
INSERT OR IGNORE INTO char_chemist_bag (character_id, slot, item_id, quantity)
SELECT id, 9, 637, 99 FROM characters WHERE main_job = 23;
INSERT OR IGNORE INTO char_chemist_bag (character_id, slot, item_id, quantity)
SELECT id, 10, 947, 99 FROM characters WHERE main_job = 23;
INSERT OR IGNORE INTO char_chemist_bag (character_id, slot, item_id, quantity)
SELECT id, 11, 4509, 99 FROM characters WHERE main_job = 23;
INSERT OR IGNORE INTO char_chemist_bag (character_id, slot, item_id, quantity)
SELECT id, 12, 18228, 99 FROM characters WHERE main_job = 23;
INSERT OR IGNORE INTO char_chemist_bag (character_id, slot, item_id, quantity)
SELECT id, 13, 4164, 99 FROM characters WHERE main_job = 23;
INSERT OR IGNORE INTO char_chemist_bag (character_id, slot, item_id, quantity)
SELECT id, 14, 17313, 99 FROM characters WHERE main_job = 23;
