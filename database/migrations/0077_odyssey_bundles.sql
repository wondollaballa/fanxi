-- Odyssey augment bundle indices (migration 77).
--
-- Every Odyssey armour piece and weapon now carries its real Rank 30 augment
-- bundle in the item exdata, so the client can draw the augment lines. The
-- indices come from LandSandBoat's Exdata::AugmentBundle table (scripts/data/
-- augments.lua) matched against each item's Rank 30 row from BG Wiki; the
-- method is validated by Assassin's Gorget +2, whose bundle 204 decodes to
-- DEX/AGI+15, Evasion+25, Triple Attack+4% - exactly its known R25 row.
--
-- Nyame has one bundle per path, so each piece gets Path A in place plus three
-- extra copies for Paths B/C/D. `!augment <index> <item>` rewrites a copy.

UPDATE char_inventory SET extra = X'038300000000F801B6010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23761;  -- Nyame Helm Path A, bundle 438
UPDATE char_inventory SET extra = X'038300000000F801B7010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23768;  -- Nyame Mail Path A, bundle 439
UPDATE char_inventory SET extra = X'038300000000F801B8010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23775;  -- Nyame Gauntlets Path A, bundle 440
UPDATE char_inventory SET extra = X'038300000000F801B9010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23782;  -- Nyame Flanchard Path A, bundle 441
UPDATE char_inventory SET extra = X'038300000000F801BA010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23789;  -- Nyame Sollerets Path A, bundle 442
UPDATE char_inventory SET extra = X'038300000000F801A2010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23757;  -- Sakpata's Helm, bundle 418
UPDATE char_inventory SET extra = X'038300000000F801A3010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23764;  -- Sakpata's Breastplate, bundle 419
UPDATE char_inventory SET extra = X'038300000000F801A4010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23771;  -- Sakpata's Gauntlets, bundle 420
UPDATE char_inventory SET extra = X'038300000000F801A5010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23778;  -- Sakpata's Cuisses, bundle 421
UPDATE char_inventory SET extra = X'038300000000F801A6010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23785;  -- Sakpata's Leggings, bundle 422
UPDATE char_inventory SET extra = X'038300000000F8019D010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23756;  -- Gleti's Mask, bundle 413
UPDATE char_inventory SET extra = X'038300000000F8019E010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23763;  -- Gleti's Cuirass, bundle 414
UPDATE char_inventory SET extra = X'038300000000F8019F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23770;  -- Gleti's Gauntlets, bundle 415
UPDATE char_inventory SET extra = X'038300000000F801A0010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23777;  -- Gleti's Breeches, bundle 416
UPDATE char_inventory SET extra = X'038300000000F801A1010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23784;  -- Gleti's Boots, bundle 417
UPDATE char_inventory SET extra = X'038300000000F801AC010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23759;  -- Agwu's Cap, bundle 428
UPDATE char_inventory SET extra = X'038300000000F801AD010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23766;  -- Agwu's Robe, bundle 429
UPDATE char_inventory SET extra = X'038300000000F801AE010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23773;  -- Agwu's Gages, bundle 430
UPDATE char_inventory SET extra = X'038300000000F801AF010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23780;  -- Agwu's Slops, bundle 431
UPDATE char_inventory SET extra = X'038300000000F801B0010000000000000000000000000000' WHERE character_id = 1 AND item_id = 23787;  -- Agwu's Pigaches, bundle 432
UPDATE char_inventory SET extra = X'038300000000F80189010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21527;  -- Sakpata's Fists, bundle 393
UPDATE char_inventory SET extra = X'038300000000F8018B010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21637;  -- Sakpata's Sword, bundle 395
UPDATE char_inventory SET extra = X'038300000000F8018A010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21567;  -- Gleti's Knife, bundle 394
UPDATE char_inventory SET extra = X'038300000000F80196010000000000000000000000000000' WHERE character_id = 1 AND item_id = 22150;  -- Gleti's Crossbow, bundle 406
UPDATE char_inventory SET extra = X'038300000000F8018E010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21724;  -- Agwu's Axe, bundle 398
UPDATE char_inventory SET extra = X'038300000000F8018C010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21675;  -- Agwu's Claymore, bundle 396
UPDATE char_inventory SET extra = X'038300000000F80190010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21832;  -- Agwu's Scythe, bundle 400

-- Path B/C/D copies of the five Nyame pieces, in free wardrobe slots.
WITH RECURSIVE
  target(character_id) AS (SELECT id FROM characters WHERE id = 1),
  containers(container, ord) AS (VALUES (8,1),(10,2),(11,3),(12,4),(13,5),(14,6),(15,7),(16,8)),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  free AS (
    SELECT c.container, n.n AS slot, ROW_NUMBER() OVER (ORDER BY c.ord, n.n) AS rn
    FROM containers c CROSS JOIN nums n
    WHERE NOT EXISTS (SELECT 1 FROM char_inventory ci
                      WHERE ci.character_id = 1 AND ci.container = c.container AND ci.slot = n.n)
      AND n.n < 80),
  want(item_id, extra, rn) AS (VALUES
    (23761, X'038300000100F801BB010000000000000000000000000000', 1),
    (23761, X'038300000200F801C0010000000000000000000000000000', 2),
    (23761, X'038300000300F801C5010000000000000000000000000000', 3),
    (23768, X'038300000100F801BC010000000000000000000000000000', 4),
    (23768, X'038300000200F801C1010000000000000000000000000000', 5),
    (23768, X'038300000300F801C6010000000000000000000000000000', 6),
    (23775, X'038300000100F801BD010000000000000000000000000000', 7),
    (23775, X'038300000200F801C2010000000000000000000000000000', 8),
    (23775, X'038300000300F801C7010000000000000000000000000000', 9),
    (23782, X'038300000100F801BE010000000000000000000000000000', 10),
    (23782, X'038300000200F801C3010000000000000000000000000000', 11),
    (23782, X'038300000300F801C8010000000000000000000000000000', 12),
    (23789, X'038300000100F801BF010000000000000000000000000000', 13),
    (23789, X'038300000200F801C4010000000000000000000000000000', 14),
    (23789, X'038300000300F801C9010000000000000000000000000000', 15)
  )
INSERT OR IGNORE INTO char_inventory (character_id,container,slot,item_id,quantity,extra)
SELECT t.character_id, free.container, free.slot, want.item_id, 1, want.extra
FROM want JOIN free ON free.rn = want.rn CROSS JOIN target t;

-- The two test copies go back to their wardrobe slots.
UPDATE char_inventory SET container = 10, slot = 36 WHERE character_id = 1 AND item_id = 23761 AND container = 0;
UPDATE char_inventory SET container = 12, slot = 67 WHERE character_id = 1 AND item_id = 25449 AND container = 0;
