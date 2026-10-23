-- Prime weapons carry the relic weapon's model id in the item data, so the client drew the
-- relic look: Opashoro (22103-22106) came with Claustrum's 554, Laphria (21782-21785) with
-- Bravura's 548.  The client never maps an item id to a model by itself -- the main-hand entry
-- of the appearance array (0x051 / 0x00D, and the 0x00E spawns) is exactly what it draws -- so
-- the id has to be right here.
--
-- The Prime models sit in a block starting in the 900s that is neither sorted by weapon type nor
-- aligned with the item ids: 904 is a vanity wand, 905 a dagger-sized blade, and several ids
-- alias one asset (903/906/907/908 all drew the same steel crescent great axe while the block
-- was being mapped).  Verified in game, one id per weapon:
--
--   907  Mpu Gandring   dagger       (hip dagger)
--   909  Helheim        great sword  (back great sword)
--   910  Spalirisos     axe          (hip hand-axe)
--   911  Laphria        great axe    (back cleaver)
--   912  Gae Buide      polearm      (back trident spear)
--   913  Foenaria       scythe
--   914  Earp           gun
--   916  Loughnashade   horn
--   917  Opashoro       staff        (back banner staff)
--
-- Hand-to-hand, sword and shield are not pinned down yet.
UPDATE items SET model = 909 WHERE item_id BETWEEN 21696 AND 21699;  -- Helheim (great sword)
UPDATE items SET model = 912 WHERE item_id BETWEEN 21739 AND 21742;  -- Gae Buide (polearm)
UPDATE items SET model = 911 WHERE item_id BETWEEN 21782 AND 21785;  -- Laphria (great axe)
UPDATE items SET model = 913 WHERE item_id BETWEEN 21868 AND 21871;  -- Foenaria (scythe)
UPDATE items SET model = 917 WHERE item_id BETWEEN 22103 AND 22106;  -- Opashoro (staff)
UPDATE items SET model = 914 WHERE item_id BETWEEN 22189 AND 22192;  -- Earp (gun)
UPDATE items SET model = 916 WHERE item_id BETWEEN 22275 AND 22278;  -- Loughnashade (horn)
