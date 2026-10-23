-- Ambuscade JSE cape augments (migration 88).
--
-- Dark Knight capes: Ankou's Mantle (item 26253), ten builds.  The
-- format is the same standard five-slot block as the Beastmaster and
-- Ninja migrations: kind 0x02, subkind 0x03, five little-endian words
-- of {id:11, value:5}, then twelve zero bytes.  The existing wardrobe
-- copy becomes the tp build; the other nine are new copies in the
-- first free wardrobe-3 slots.  The client reads the job from the
-- item name, so !cape <build> <item> can rewrite any of them.

UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26253 AND (extra IS NULL OR length(extra) = 0);

INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 11, 1, 26253, 1, X'020302D851981F4828483648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- pdt
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 11, 2, 26253, 1, X'020302D85198254828483748000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- mdt
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 11, 3, 26253, 1, X'020302D85198019828484720000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- maxhp
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 11, 4, 26253, 1, X'020302D851981F4828484720000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- dt
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 11, 5, 26253, 1, X'02030AD8509809988C483648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- fc
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 11, 6, 26253, 1, X'0203049A5098234828483648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- macc
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 11, 7, 26253, 1, X'0203009A4498004A47494720000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- ws_str
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 11, 8, 26253, 1, X'0203049A5098044A47493648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- ws_int
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 11, 9, 26253, 1, X'020302D851981F4827483648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- enmity
