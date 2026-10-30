-- The Armory sells every Prime weapon in its final iLvl 119 III form (migration 164).
--
-- A Prime family stores up to five rows, and the four upgraded forms share one name:
-- Foenaria is item 21833 (the "Prime Scythe" stage-1 row) plus 21834-21837, and 21837
-- is the stage-5 form with the afterglow model.  The Armory used to list all four
-- upgraded rows as identical "Foenaria" entries, so the first one -- the weakest stage
-- -- was the row Enter selected.  The service now collapses each family to its final
-- row and upgrades any earlier stage id at purchase time.
--
-- This migration repairs what was bought before that change.  Every earlier stage id
-- in the bags, storage slips, locker, equipped set and purchase history becomes the
-- family's final id.  Prime weapons are Rare, so a family is one item: a character
-- that bought several stages keeps a single copy.  The keeper is the equipped bag row
-- first, then an existing final form, then the highest stage; storage yields to a bag
-- row and the locker yields to both, the same precedence migration 103 used.
--
-- The pairs are the same table prime_weapons.PRIME_FAMILIES holds; Dokoku and Kusanagi
-- have no stage-1 row in this catalogue, so their families start at stage 2.

CREATE TEMP TABLE prime_stage_map (
    stage_id INTEGER PRIMARY KEY,
    final_id INTEGER NOT NULL,
    stage_no INTEGER NOT NULL
);

INSERT INTO prime_stage_map (stage_id, final_id, stage_no) VALUES
    (21531, 21535, 1),  -- Varga Purnikawa
    (21532, 21535, 2), (21533, 21535, 3), (21534, 21535, 4), (21535, 21535, 5),
    (21586, 21590, 1),  -- Mpu Gandring
    (21587, 21590, 2), (21588, 21590, 3), (21589, 21590, 4), (21590, 21590, 5),
    (21642, 21646, 1),  -- Caliburnus
    (21643, 21646, 2), (21644, 21646, 3), (21645, 21646, 4), (21646, 21646, 5),
    (21650, 21653, 1),  -- Helheim (the base row is between the stage ids)
    (21649, 21653, 2), (21651, 21653, 3), (21652, 21653, 4), (21653, 21653, 5),
    (21726, 21730, 1),  -- Spalirisos
    (21727, 21730, 2), (21728, 21730, 3), (21729, 21730, 4), (21730, 21730, 5),
    (21781, 21785, 1),  -- Laphria
    (21782, 21785, 2), (21783, 21785, 3), (21784, 21785, 4), (21785, 21785, 5),
    (21833, 21837, 1),  -- Foenaria
    (21834, 21837, 2), (21835, 21837, 3), (21836, 21837, 4), (21837, 21837, 5),
    (21887, 21891, 1),  -- Gae Buide
    (21888, 21891, 2), (21889, 21891, 3), (21890, 21891, 4), (21891, 21891, 5),
    (21929, 21932, 2),  -- Dokoku (no stage-1 row in this catalogue)
    (21930, 21932, 3), (21931, 21932, 4), (21932, 21932, 5),
    (21983, 21986, 2),  -- Kusanagi (no stage-1 row in this catalogue)
    (21984, 21986, 3), (21985, 21986, 4), (21986, 21986, 5),
    (21999, 22002, 1),  -- Lorg Mor (the base row is between the stage ids)
    (21998, 22002, 2), (22000, 22002, 3), (22001, 22002, 4), (22002, 22002, 5),
    (22102, 22106, 1),  -- Opashoro
    (22103, 22106, 2), (22104, 22106, 3), (22105, 22106, 4), (22106, 22106, 5),
    (22155, 22163, 1),  -- Pinaka
    (22156, 22163, 2), (22157, 22163, 3), (22158, 22163, 4), (22163, 22163, 5),
    (22159, 22164, 1),  -- Earp
    (22160, 22164, 2), (22161, 22164, 3), (22162, 22164, 4), (22164, 22164, 5),
    (22303, 22307, 1),  -- Loughnashade
    (22304, 22307, 2), (22305, 22307, 3), (22306, 22307, 4), (22307, 22307, 5),
    (26491, 26495, 1),  -- Duban
    (26492, 26495, 2), (26493, 26495, 3), (26494, 26495, 4), (26495, 26495, 5);

-- The bags: one copy per family per character, chosen before the ids change.
DELETE FROM char_inventory
 WHERE rowid IN (
   SELECT rid FROM (
     SELECT ci.rowid AS rid,
            ROW_NUMBER() OVER (
              PARTITION BY ci.character_id, map.final_id
              ORDER BY
                CASE WHEN EXISTS (
                  SELECT 1 FROM char_equip e
                   WHERE e.character_id = ci.character_id
                     AND e.container = ci.container
                     AND e.slot = ci.slot
                     AND e.item_id = ci.item_id
                ) THEN 0 ELSE 1 END,
                CASE WHEN ci.item_id = map.final_id THEN 0 ELSE 1 END,
                map.stage_no DESC,
                ci.container, ci.slot, ci.rowid
            ) AS rn
       FROM char_inventory ci
       JOIN prime_stage_map map ON map.stage_id = ci.item_id
   )
   WHERE rn > 1
 );

UPDATE char_inventory
   SET item_id = (SELECT final_id FROM prime_stage_map
                   WHERE stage_id = char_inventory.item_id)
 WHERE item_id IN (SELECT stage_id FROM prime_stage_map WHERE stage_id <> final_id);

UPDATE char_inventory
   SET quantity = 1
 WHERE quantity > 1
   AND item_id IN (SELECT final_id FROM prime_stage_map);

UPDATE char_equip
   SET item_id = (SELECT final_id FROM prime_stage_map
                   WHERE stage_id = char_equip.item_id)
 WHERE item_id IN (SELECT stage_id FROM prime_stage_map WHERE stage_id <> final_id);

-- A removed duplicate may have been the equipped row in a stale database; drop the
-- pointer rather than leave the client asking for an item the bags no longer hold.
DELETE FROM char_equip
 WHERE item_id IN (SELECT final_id FROM prime_stage_map)
   AND NOT EXISTS (
       SELECT 1 FROM char_inventory ci
        WHERE ci.character_id = char_equip.character_id
          AND ci.container = char_equip.container
          AND ci.slot = char_equip.slot
          AND ci.item_id = char_equip.item_id);

-- Storage slips have a (character, item) primary key, so collapse before the ids
-- change.  Storage yields to a bag copy, as it does in migration 103.
DELETE FROM char_storage
 WHERE rowid IN (
   SELECT rid FROM (
     SELECT cs.rowid AS rid,
            ROW_NUMBER() OVER (
              PARTITION BY cs.character_id, map.final_id
              ORDER BY CASE WHEN cs.item_id = map.final_id THEN 0 ELSE 1 END,
                       map.stage_no DESC,
                       cs.slip, cs.rowid
            ) AS rn
       FROM char_storage cs
       JOIN prime_stage_map map ON map.stage_id = cs.item_id
   )
   WHERE rn > 1
 );

UPDATE char_storage
   SET item_id = (SELECT final_id FROM prime_stage_map
                   WHERE stage_id = char_storage.item_id)
 WHERE item_id IN (SELECT stage_id FROM prime_stage_map WHERE stage_id <> final_id);

UPDATE char_storage
   SET quantity = 1
 WHERE quantity > 1
   AND item_id IN (SELECT final_id FROM prime_stage_map);

DELETE FROM char_storage
 WHERE item_id IN (SELECT final_id FROM prime_stage_map)
   AND EXISTS (SELECT 1 FROM char_inventory ci
                WHERE ci.character_id = char_storage.character_id
                  AND ci.item_id = char_storage.item_id);

-- The locker has the augment blob in its key, but Prime weapons are not augmentable,
-- so one row per family is enough; the locker yields to both the bag and storage.
DELETE FROM char_locker
 WHERE rowid IN (
   SELECT rid FROM (
     SELECT cl.rowid AS rid,
            ROW_NUMBER() OVER (
              PARTITION BY cl.character_id, map.final_id
              ORDER BY CASE WHEN cl.item_id = map.final_id THEN 0 ELSE 1 END,
                       map.stage_no DESC,
                       cl.stored_at, cl.rowid
            ) AS rn
       FROM char_locker cl
       JOIN prime_stage_map map ON map.stage_id = cl.item_id
   )
   WHERE rn > 1
 );

UPDATE char_locker
   SET item_id = (SELECT final_id FROM prime_stage_map
                   WHERE stage_id = char_locker.item_id)
 WHERE item_id IN (SELECT stage_id FROM prime_stage_map WHERE stage_id <> final_id);

UPDATE char_locker
   SET quantity = 1
 WHERE quantity > 1
   AND item_id IN (SELECT final_id FROM prime_stage_map);

DELETE FROM char_locker
 WHERE item_id IN (SELECT final_id FROM prime_stage_map)
   AND (EXISTS (SELECT 1 FROM char_inventory ci
                 WHERE ci.character_id = char_locker.character_id
                   AND ci.item_id = char_locker.item_id)
        OR EXISTS (SELECT 1 FROM char_storage cs
                    WHERE cs.character_id = char_locker.character_id
                      AND cs.item_id = char_locker.item_id));

-- The purchase history keeps its rows and prices, pointing at the final item now.
UPDATE char_purchases
   SET item_id = (SELECT final_id FROM prime_stage_map
                   WHERE stage_id = char_purchases.item_id)
 WHERE item_id IN (SELECT stage_id FROM prime_stage_map WHERE stage_id <> final_id);

DROP TABLE prime_stage_map;
