-- Grant the bard song BiS pieces the new GearSwap song sets name.
--
-- Onedough already owns the shared accessories and Loughnashade; this pass adds the
-- Aeonic instrument and the Song+/duration armour that the SongDuration, SongPotency,
-- SongHonor and SongAria sets use.  Twodough gets a copy so a cloned BRD can use the
-- same library.

CREATE TEMP TABLE IF NOT EXISTS bard_song_gear137 (item_id INTEGER PRIMARY KEY);
DELETE FROM bard_song_gear137;
INSERT INTO bard_song_gear137 (item_id) VALUES
 (21398),  -- Marsyas, Aeonic instrument (Honor March)
 (25882),  -- Inyanga Shalwar +2, Song duration +17%
 (23161),  -- Fili Hongreline +2, Song duration +13%, Minuet +1
 (23652),  -- Brioso Slippers +3, Song duration +15%
 (11618),  -- Aoidos' Matinee, Song duration +10%
 (26033),  -- Mnbw. Whistle +1, All songs +3
 (23094),  -- Fili Calot +2, Song cast time -15%, Madrigal +1
 (23518),  -- Brioso Cuffs +3, Lullaby +2
 (23295),  -- Fili Rhingrave +2, Ballad +1, song recast -9
 (23362);  -- Fili Cothurnes +2, Scherzo +1

WITH RECURSIVE
  target(character_id) AS (
    SELECT id FROM characters WHERE lower(name) IN ('onedough', 'twodough')
  ),
  containers(container, ord) AS (
    VALUES (8,1),(10,2),(11,3),(12,4),(13,5),(14,6),(15,7),(16,8),
           (1,9),(5,10),(6,11),(7,12),(9,13)
  ),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  free AS (
    SELECT t.character_id, c.container, n.n AS slot,
           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY c.ord, n.n) AS rn
    FROM target t CROSS JOIN containers c CROSS JOIN nums n
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = t.character_id
        AND ci.container = c.container AND ci.slot = n.n
    )
    AND n.n < 80
  ),
  want AS (
    SELECT t.character_id, g.item_id,
           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY g.item_id) AS rn
    FROM target t CROSS JOIN bard_song_gear137 g
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = t.character_id AND ci.item_id = g.item_id
    )
  )
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT want.character_id, free.container, free.slot, want.item_id, 1
FROM want JOIN free
  ON free.character_id = want.character_id AND free.rn = want.rn;

DROP TABLE bard_song_gear137;
