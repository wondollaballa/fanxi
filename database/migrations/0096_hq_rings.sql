-- HQ rings on Onedough and Twodough (migration 96).
--
-- The GearSwap libraries named the NQ Chirich Ring and Shneddick Ring even though
-- the +1 versions exist; Stikini Ring was already +1 but each character had only
-- one.  Both mains should carry two of each +1 ring -- one for each ring slot,
-- with a spare pair -- so this migration:
--
--   1. adds the two catalogue rows the database was missing;
--   2. upgrades every NQ ring on Onedough and Twodough in place, which keeps an
--      equipped ring's char_equip container/slot pointer valid;
--   3. tops each character up to two copies of each +1 ring in free wardrobe
--      slots (the same wardrobe-first order as migrations 66/89/90);
--   4. removes any NQ rings still on those two characters.
--
-- NQ copies on other characters are left alone.  The item ids and slot/job
-- masks are LandSandBoat's item_equipment rows; the display names are Fanxi's own.

INSERT OR IGNORE INTO items
 (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES
 (26182,'Chirich Ring +1',1,0,'ring1',99,'GearSwap default library item.',0,24576,4194303),
 (26202,'Shneddick Ring +1',1,0,'ring1',99,'GearSwap default library item.',0,24576,4194303);

CREATE TEMP TABLE IF NOT EXISTS hq_ring_map96 (
  old_id INTEGER PRIMARY KEY,
  new_id INTEGER NOT NULL
);
DELETE FROM hq_ring_map96;
INSERT INTO hq_ring_map96 (old_id,new_id) VALUES
 (26181,26182),   -- Chirich Ring     -> Chirich Ring +1
 (26183,26184),   -- Stikini Ring     -> Stikini Ring +1
 (27590,26202);   -- Shneddick Ring   -> Shneddick Ring +1

CREATE TEMP TABLE IF NOT EXISTS hq_ring_chars96 (character_id INTEGER PRIMARY KEY);
DELETE FROM hq_ring_chars96;
INSERT INTO hq_ring_chars96 (character_id)
SELECT id FROM characters WHERE name IN ('Onedough','Twodough');

-- Upgrade the visible bags in place.  The primary key is (character,container,
-- slot), so an equipped ring keeps pointing at the same slot after its item id
-- changes; only char_equip's copy of the id needs the same update.
UPDATE char_inventory
   SET item_id = (SELECT new_id FROM hq_ring_map96 WHERE old_id = char_inventory.item_id)
 WHERE item_id IN (SELECT old_id FROM hq_ring_map96)
   AND character_id IN (SELECT character_id FROM hq_ring_chars96);

UPDATE char_equip
   SET item_id = (SELECT new_id FROM hq_ring_map96 WHERE old_id = char_equip.item_id)
 WHERE item_id IN (SELECT old_id FROM hq_ring_map96)
   AND character_id IN (SELECT character_id FROM hq_ring_chars96);

-- Slips and the hidden locker key by (character,item), so an HQ row can already
-- occupy the slot.  Upgrade only when it does not; the NQ leftovers are dropped
-- below.
UPDATE char_storage
   SET item_id = (SELECT new_id FROM hq_ring_map96 WHERE old_id = char_storage.item_id)
 WHERE item_id IN (SELECT old_id FROM hq_ring_map96)
   AND character_id IN (SELECT character_id FROM hq_ring_chars96)
   AND NOT EXISTS (
       SELECT 1 FROM char_storage s
        WHERE s.character_id = char_storage.character_id
          AND s.item_id = (SELECT new_id FROM hq_ring_map96 WHERE old_id = char_storage.item_id)
   );

UPDATE char_locker
   SET item_id = (SELECT new_id FROM hq_ring_map96 WHERE old_id = char_locker.item_id)
 WHERE item_id IN (SELECT old_id FROM hq_ring_map96)
   AND character_id IN (SELECT character_id FROM hq_ring_chars96)
   AND NOT EXISTS (
       SELECT 1 FROM char_locker l
        WHERE l.character_id = char_locker.character_id
          AND l.item_id = (SELECT new_id FROM hq_ring_map96 WHERE old_id = char_locker.item_id)
   );

DELETE FROM char_inventory
 WHERE item_id IN (SELECT old_id FROM hq_ring_map96)
   AND character_id IN (SELECT character_id FROM hq_ring_chars96);
DELETE FROM char_storage
 WHERE item_id IN (SELECT old_id FROM hq_ring_map96)
   AND character_id IN (SELECT character_id FROM hq_ring_chars96);
DELETE FROM char_locker
 WHERE item_id IN (SELECT old_id FROM hq_ring_map96)
   AND character_id IN (SELECT character_id FROM hq_ring_chars96);

-- Two copies of each +1 ring per character.  Rings do not stack, so copies are
-- separate rows; quantity is counted in case a hand-inserted row stacked them.
CREATE TEMP TABLE IF NOT EXISTS hq_ring_need96 (
  character_id INTEGER NOT NULL,
  item_id      INTEGER NOT NULL,
  need         INTEGER NOT NULL,
  PRIMARY KEY (character_id,item_id)
);
DELETE FROM hq_ring_need96;
INSERT INTO hq_ring_need96 (character_id,item_id,need)
SELECT c.character_id, w.item_id,
       2 - COALESCE((SELECT SUM(ci.quantity) FROM char_inventory ci
                      WHERE ci.character_id = c.character_id AND ci.item_id = w.item_id), 0)
  FROM hq_ring_chars96 c
  CROSS JOIN (SELECT 26182 AS item_id
              UNION ALL SELECT 26184
              UNION ALL SELECT 26202) w
 WHERE COALESCE((SELECT SUM(ci.quantity) FROM char_inventory ci
                  WHERE ci.character_id = c.character_id AND ci.item_id = w.item_id), 0) < 2;

WITH RECURSIVE
  bags(container, ord) AS (
    VALUES (8,1),(10,2),(11,3),(12,4),(13,5),(14,6),(15,7),(16,8),
           (1,9),(5,10),(6,11),(7,12),(9,13)
  ),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  copies(character_id,item_id,copy_no) AS (
    SELECT n.character_id, n.item_id, v.i
      FROM hq_ring_need96 n
      JOIN (SELECT 1 AS i UNION ALL SELECT 2) v ON v.i <= n.need
  ),
  free(character_id,container,slot,rn) AS (
    SELECT c.character_id, b.container, ns.n,
           ROW_NUMBER() OVER (PARTITION BY c.character_id ORDER BY b.ord, ns.n)
      FROM hq_ring_chars96 c
      CROSS JOIN bags b
      CROSS JOIN nums ns
     WHERE NOT EXISTS (
           SELECT 1 FROM char_inventory ci
            WHERE ci.character_id = c.character_id
              AND ci.container = b.container
              AND ci.slot = ns.n
     )
  ),
  wanted(character_id,item_id,copy_no,rn) AS (
    SELECT character_id, item_id, copy_no,
           ROW_NUMBER() OVER (PARTITION BY character_id ORDER BY item_id, copy_no)
      FROM copies
  )
INSERT INTO char_inventory (character_id,container,slot,item_id,quantity)
SELECT w.character_id, f.container, f.slot, w.item_id, 1
  FROM wanted w
  JOIN free f ON f.character_id = w.character_id AND f.rn = w.rn;
