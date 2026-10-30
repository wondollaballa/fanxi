-- Collapse the duplicate Opashoro 22106 that migration 164 leaves behind.
--
-- 164 converts the old 22103 (the GearSwap grant at container 8 slot 46) to the final
-- 22106 in place.  A box that already held the afterglow 22106 then has two:
--
--   characters 2-6: 22106 at container 8 slot 46 (converted) and container 10 slot 21
--   character 1:    22106 at container 8 slot 46 (converted) and in the Mog Locker
--
-- Keep the original afterglow copy and drop the converted duplicate; character 1 has no
-- other inventory copy, so there the converted bag slot is kept and the locker copy is
-- dropped.  Every character ends with exactly one 22106, and a re-run changes nothing.
DELETE FROM char_inventory
 WHERE item_id = 22106
   AND container = 8
   AND slot = 46
   AND EXISTS (SELECT 1 FROM char_inventory keep
                WHERE keep.character_id = char_inventory.character_id
                  AND keep.item_id = 22106
                  AND (keep.container <> 8 OR keep.slot <> 46));

DELETE FROM char_locker
 WHERE item_id = 22106
   AND EXISTS (SELECT 1 FROM char_inventory ci
                WHERE ci.character_id = char_locker.character_id
                  AND ci.item_id = 22106);
