-- Ambuscade JSE cape augments (migration 78).
--
-- Job capes are standard five-slot augments: kind 0x02, subkind 0x03,
-- five little-endian words of {id:11, value:5}, then twelve zero bytes.
-- The client renders each word as (value + offset) * multiplier using the
-- per-id table in docs/capes.md; the ids come from the client's augment
-- table (the same space LandSandBoat's Magian items use).
--
-- The Artio's Mantle already in the bag takes the tp build; the other
-- eight builds are new copies in free bag slots.

UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26254 AND container = 0 AND slot = 80;

INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 0, 1, 26254, 1, X'020302D851981F4828483648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- pdt
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 0, 14, 26254, 1, X'020302D85198254828483748000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- mdt
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 0, 18, 26254, 1, X'020302D85198019828484720000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- maxhp
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 0, 19, 26254, 1, X'020302D851981F4828484720000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- dt
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 0, 20, 26254, 1, X'0203009A4498004A47494720000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- ws_str
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 0, 21, 26254, 1, X'0203059A5098054A47493648000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- mabws
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 0, 23, 26254, 1, X'02037C986B486F4870200000000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- pet_tp
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra) SELECT 1, 0, 24, 26254, 1, X'02037D986A9864486F487020000000000000000000000000' WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- pet_dt
