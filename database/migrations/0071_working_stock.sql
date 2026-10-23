-- Working-stock auto-refill for the consumables the client must see in inventory.
-- The bulk stays in char_locker; after a use, refill_working_stock() tops the visible
-- stack back up.  Dawn Mulsum is item 5411 (stack 1); the rest are already catalogued.
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs)
VALUES (5411,'Dawn Mulsum',1,1,'',1,'Medicine that restores HP.',0,0,0);

-- Refill stock in the hidden locker: one full stack of each ninjutsu tool, two
-- stacks of pet food, and 33 Dawn Mulsums.  This stays under the 9999 locker cap.
WITH stock(item_id, quantity) AS (
    VALUES (2971,33),(2972,33),(2973,33),(17023,24),(5411,33)
)
INSERT INTO char_locker (character_id, item_id, quantity)
SELECT 1, item_id, quantity FROM stock
WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1)
ON CONFLICT(character_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity;

-- Three Dawn Mulsums in the bags so the first use works without a grab.
WITH free AS (
    SELECT slot, ROW_NUMBER() OVER (ORDER BY slot) AS rn
    FROM (WITH RECURSIVE nums(n) AS (SELECT 0 UNION ALL SELECT n + 1 FROM nums WHERE n < 80)
          SELECT n AS slot FROM nums)
    WHERE slot NOT IN (SELECT slot FROM char_inventory WHERE character_id = 1 AND container = 0)
)
INSERT INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT 1, 0, free.slot, 5411, 1
FROM free
WHERE free.rn <= 3
  AND EXISTS (SELECT 1 FROM characters WHERE id = 1);
