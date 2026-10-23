-- Diamond Aspis (Mog Bonanza shield), item 26488.
--
-- The Gear window's set editor accepts any item name, so a saved set can name a
-- Bonanza piece the catalogue never carried.  The client's own item resource gives
-- the real fields: shield (sub) slot, level 99, item level 119, jobs
-- WAR/WHM/RDM/THF/PLD/BST (bit mask 373, the same value as LSB item_equipment).
-- LSB's item_equipment still has MId 0 for the Aspis; its lockstyle twin, the Diamond
-- Buckler (26410), uses shield model 659, so that is the model the client draws here.
--
-- Grant one copy to the first character only when it is not in the bags already, in
-- the first free inventory slot, so a fresh database and an existing one both work
-- and a moved item is never overwritten.

INSERT OR REPLACE INTO items
 (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs)
VALUES (26488,'Diamond Aspis',1,0,'sub',99,'Mog Bonanza shield, iLvl 119.',659,2,373);

WITH RECURSIVE
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  free(slot) AS (
    SELECT n FROM nums
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory
      WHERE character_id = 1 AND container = 0 AND slot = n
    )
    ORDER BY n
    LIMIT 1
  )
INSERT INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT 1, 0, free.slot, 26488, 1
FROM free
WHERE NOT EXISTS (
  SELECT 1 FROM char_inventory WHERE character_id = 1 AND item_id = 26488
)
  -- A fresh database has no character 1 yet: grant nothing rather than a row the
  -- character_id foreign key would reject.
  AND EXISTS (SELECT 1 FROM characters WHERE id = 1);
