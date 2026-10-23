-- Ambuscade JSE cape augments (migration 82).
--
-- Job capes are standard five-slot augments: kind 0x02, subkind 0x03,
-- five little-endian words of {id:11, value:5}, then twelve zero bytes.
-- The client renders each word as (value + offset) * multiplier using the
-- per-id table in docs/capes.md; the ids come from the client's augment
-- table (the same space LandSandBoat's Magian items use).
--
-- The Andartia's Mantle already in the wardrobe takes the tp build; the other
-- ten builds are new copies in free bag slots.

UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26258 AND (extra IS NULL OR length(extra) = 0);

-- The ten remaining builds go into the first free main-bag slots.
WITH RECURSIVE
  target(character_id) AS (SELECT id FROM characters WHERE id = 1),
  nums(n) AS (SELECT 0 UNION ALL SELECT n + 1 FROM nums WHERE n < 79),
  free AS (
    SELECT n AS slot, ROW_NUMBER() OVER (ORDER BY n) AS rn
    FROM nums
    WHERE NOT EXISTS (SELECT 1 FROM char_inventory ci
                      WHERE ci.character_id = 1 AND ci.container = 0 AND ci.slot = n)
      AND n < 80),
  want(item_id, extra, rn) AS (VALUES
    (26258, X'020302D851981F4828483648000000000000000000000000', 1),
    (26258, X'020302D85198254828483748000000000000000000000000', 2),
    (26258, X'020302D85198019828484720000000000000000000000000', 3),
    (26258, X'020302D851981F4828484720000000000000000000000000', 4),
    (26258, X'0203019A4498014A92483648000000000000000000000000', 5),
    (26258, X'020302D850981F488C483648000000000000000000000000', 6),
    (26258, X'0203049A5098044A85483648000000000000000000000000', 7),
    (26258, X'0203039A4498034A47494720000000000000000000000000', 8),
    (26258, X'0203019A4498014A47494720000000000000000000000000', 9),
    (26258, X'0203009A4498004A47494720000000000000000000000000', 10)
  )
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity, extra)
SELECT t.character_id, 0, free.slot, want.item_id, 1, want.extra
FROM want JOIN free ON free.rn = want.rn CROSS JOIN target t;
