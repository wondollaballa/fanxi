-- Slot 9 was already occupied on the live character; put Slime Oil in the next
-- free Battle Bag slot so the fire coating is available too.
INSERT OR IGNORE INTO char_chemist_bag (character_id, slot, item_id, quantity)
SELECT id, 15, 637, 99 FROM characters WHERE main_job = 23;
