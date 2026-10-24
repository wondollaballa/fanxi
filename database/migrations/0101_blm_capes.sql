-- Ambuscade JSE cape augments (migration 101).
--
-- Black Mage capes: Taranus's Cape (item 26249), nine builds.  The
-- format is the same standard five-slot block as the Beastmaster,
-- Ninja and Dark Knight migrations: kind 0x02, subkind 0x03, five
-- little-endian words of {id:11, value:5}, then twelve zero bytes.
-- The existing wardrobe copy becomes the tp build; the other eight
-- are new copies in wardrobe 6 slots 66-73 (the inventory and the
-- earlier wardrobes are full).  The client reads the job from the
-- item name, so !cape <build> <item> can rewrite any of them.

UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26249 AND (extra IS NULL OR length(extra) = 0);

INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 14, 66, 26249, 1, X'020302D851981F4828483648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- pdt
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 14, 67, 26249, 1, X'020302D85198254828483748000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- mdt
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 14, 68, 26249, 1, X'020302D85198019828484720000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- maxhp
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 14, 69, 26249, 1, X'020302D851981F4828484720000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- dt
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 14, 70, 26249, 1, X'02030AD8509809988C483648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- fcmp
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 14, 71, 26249, 1, X'0203049A5098234828483648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- macc
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 14, 72, 26249, 1, X'0203049A5098044A85483648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- nuke
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 14, 73, 26249, 1, X'0203049A5098044A47493648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- mabws
