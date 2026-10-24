-- One copy of every Rare item on Onedough and Twodough (migration 103).
--
-- The GearSwap grants (migrations 66, 72, 77, 87, 89, 90, 96 and 97) filled the
-- wardrobes without consulting retail's Rare flag.  Some deliberately granted two
-- ring-slot copies or one copy per augment path; the older ones only checked the
-- visible bags.  The two mains therefore held several copies of the same Rare/Ex
-- piece: four Nyame pieces, two of each Rare +1 ring, two Wicce pieces, and quantity
-- two of many stored suits.  Retail allows one copy per character; this migration
-- keeps one and drops the rest.
--
-- The keeper is chosen per character and item:
--   1. the equipped copy, so char_equip keeps pointing at a real bag row;
--   2. an augmented copy over a plain one, and Path A (the lowest bundle) over B/C/D;
--   3. the wardrobe-first container order the grants use, then the lowest slot.
-- Storage and the hidden locker yield to a visible bag row.  A row that says
-- quantity 2 (the storage slip aggregation did this) is cut back to one.
--
-- Characters are matched by name rather than id so the cleanup survives a database
-- whose ids differ.  Other characters keep their rows: this is about the two mains.

CREATE TEMP TABLE IF NOT EXISTS rare_targets (character_id INTEGER PRIMARY KEY);
DELETE FROM rare_targets;
INSERT INTO rare_targets (character_id)
SELECT id FROM characters WHERE lower(name) IN ('onedough', 'twodough');

-- Duplicate rows in the visible bags; the first row in the ranking survives.
DELETE FROM char_inventory
WHERE rowid IN (
  SELECT rid FROM (
    SELECT ci.rowid AS rid,
           ROW_NUMBER() OVER (
             PARTITION BY ci.character_id, ci.item_id
             ORDER BY
               CASE WHEN EXISTS (
                 SELECT 1 FROM char_equip e
                 WHERE e.character_id = ci.character_id
                   AND e.container = ci.container
                   AND e.slot = ci.slot
                   AND e.item_id = ci.item_id
               ) THEN 0 ELSE 1 END,
               CASE WHEN length(ci.extra) > 0 THEN 0 ELSE 1 END,
               hex(ci.extra),
               CASE ci.container
                 WHEN 8 THEN 1 WHEN 10 THEN 2 WHEN 11 THEN 3 WHEN 12 THEN 4
                 WHEN 13 THEN 5 WHEN 14 THEN 6 WHEN 15 THEN 7 WHEN 16 THEN 8
                 WHEN 0 THEN 9 WHEN 1 THEN 10 WHEN 5 THEN 11 WHEN 6 THEN 12
                 WHEN 7 THEN 13 WHEN 9 THEN 14 ELSE 99 END,
               ci.slot,
               ci.rowid
           ) AS rn
      FROM char_inventory ci
      JOIN rare_targets t ON t.character_id = ci.character_id
      JOIN items i ON i.item_id = ci.item_id
     WHERE i.rare = 1
  )
  WHERE rn > 1
);

-- A visible row never stacks a Rare item.
UPDATE char_inventory
   SET quantity = 1
 WHERE quantity > 1
   AND character_id IN (SELECT character_id FROM rare_targets)
   AND item_id IN (SELECT item_id FROM items WHERE rare = 1);

-- Storage yields to the bag, and the locker yields to both.  Without a bag row,
-- storage keeps the item; without either, the locker does.
DELETE FROM char_storage
 WHERE character_id IN (SELECT character_id FROM rare_targets)
   AND item_id IN (SELECT item_id FROM items WHERE rare = 1)
   AND EXISTS (
       SELECT 1 FROM char_inventory ci
        WHERE ci.character_id = char_storage.character_id
          AND ci.item_id = char_storage.item_id);

DELETE FROM char_locker
 WHERE character_id IN (SELECT character_id FROM rare_targets)
   AND item_id IN (SELECT item_id FROM items WHERE rare = 1)
   AND (EXISTS (
           SELECT 1 FROM char_inventory ci
            WHERE ci.character_id = char_locker.character_id
              AND ci.item_id = char_locker.item_id)
        OR EXISTS (
           SELECT 1 FROM char_storage cs
            WHERE cs.character_id = char_locker.character_id
              AND cs.item_id = char_locker.item_id));

UPDATE char_storage
   SET quantity = 1
 WHERE quantity > 1
   AND character_id IN (SELECT character_id FROM rare_targets)
   AND item_id IN (SELECT item_id FROM items WHERE rare = 1);

UPDATE char_locker
   SET quantity = 1
 WHERE quantity > 1
   AND character_id IN (SELECT character_id FROM rare_targets)
   AND item_id IN (SELECT item_id FROM items WHERE rare = 1);

-- A removed duplicate may have been the second ring in an equip pair; drop the
-- pointer rather than leave the client asking for a row that is gone.
DELETE FROM char_equip
 WHERE character_id IN (SELECT character_id FROM rare_targets)
   AND NOT EXISTS (
       SELECT 1 FROM char_inventory ci
        WHERE ci.character_id = char_equip.character_id
          AND ci.container = char_equip.container
          AND ci.slot = char_equip.slot
          AND ci.item_id = char_equip.item_id);

DROP TABLE IF EXISTS rare_targets;
