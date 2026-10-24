-- Limbus Rank 30 exdata and the five Limbus jewel pairs (migration 104).
--
-- Migration 99 granted the 25 top-tier pieces with augment bundle index 0, so the
-- client had no bundle to read and the accumulated RP was zero: the tooltip showed
-- the base suit and no Rank 30 lines even though the rank field said 30.  Each
-- piece's own bundle index is below (the client's augment table, LandSandBoat's
-- xi.data.augments.bundles, parsed from the MNC2 data, matched to the Rank 30 row
-- in docs/limbus-r30.md by content).  The block now also carries the curve-B RP
-- total for rank 30, 55,800 (rank 1 is 1,600), so the client can print the rank.
--
-- The same migration grants the five Shard -> Jewel pairs the Limbus furnaces use
-- -- Justice -> Destiny, Hope -> Revelation, Trust -> Camaraderie, Bravery ->
-- Persistence, Mercy -> Affection -- to Onedough and Twodough as permanent Ex
-- items, 99 to a stack.  The Su5 *equip* gate is not a key item: it is the 2,100
-- JP job gift, which the server already maxes for every job.  The jewels are the
-- Rank 30 augmentation currency, not the wear requirement.

-- 1. Rank 30 exdata on every copy already in a bag.
UPDATE char_inventory SET extra = X'03830000E067FB05D8010000000000000000000000000000' WHERE item_id = 24122;
UPDATE char_inventory SET extra = X'03830000E067FB05D9010000000000000000000000000000' WHERE item_id = 24125;
UPDATE char_inventory SET extra = X'03830000E067FB05DA010000000000000000000000000000' WHERE item_id = 24128;
UPDATE char_inventory SET extra = X'03830000E067FB05DB010000000000000000000000000000' WHERE item_id = 24131;
UPDATE char_inventory SET extra = X'03830000E067FB05DC010000000000000000000000000000' WHERE item_id = 24134;
UPDATE char_inventory SET extra = X'03830000E067FB05E7010000000000000000000000000000' WHERE item_id = 24137;
UPDATE char_inventory SET extra = X'03830000E067FB05E8010000000000000000000000000000' WHERE item_id = 24140;
UPDATE char_inventory SET extra = X'03830000E067FB05E9010000000000000000000000000000' WHERE item_id = 24143;
UPDATE char_inventory SET extra = X'03830000E067FB05EA010000000000000000000000000000' WHERE item_id = 24146;
UPDATE char_inventory SET extra = X'03830000E067FB05EB010000000000000000000000000000' WHERE item_id = 24149;
UPDATE char_inventory SET extra = X'03830000E067FB05E2010000000000000000000000000000' WHERE item_id = 24152;
UPDATE char_inventory SET extra = X'03830000E067FB05E3010000000000000000000000000000' WHERE item_id = 24155;
UPDATE char_inventory SET extra = X'03830000E067FB05E4010000000000000000000000000000' WHERE item_id = 24158;
UPDATE char_inventory SET extra = X'03830000E067FB05E5010000000000000000000000000000' WHERE item_id = 24161;
UPDATE char_inventory SET extra = X'03830000E067FB05E6010000000000000000000000000000' WHERE item_id = 24164;
UPDATE char_inventory SET extra = X'03830000E067FB05DD010000000000000000000000000000' WHERE item_id = 24167;
UPDATE char_inventory SET extra = X'03830000E067FB05DE010000000000000000000000000000' WHERE item_id = 24170;
UPDATE char_inventory SET extra = X'03830000E067FB05DF010000000000000000000000000000' WHERE item_id = 24173;
UPDATE char_inventory SET extra = X'03830000E067FB05E0010000000000000000000000000000' WHERE item_id = 24176;
UPDATE char_inventory SET extra = X'03830000E067FB05E1010000000000000000000000000000' WHERE item_id = 24179;
UPDATE char_inventory SET extra = X'03830000E067FB05EC010000000000000000000000000000' WHERE item_id = 24182;
UPDATE char_inventory SET extra = X'03830000E067FB05ED010000000000000000000000000000' WHERE item_id = 24185;
UPDATE char_inventory SET extra = X'03830000E067FB05EE010000000000000000000000000000' WHERE item_id = 24188;
UPDATE char_inventory SET extra = X'03830000E067FB05EF010000000000000000000000000000' WHERE item_id = 24191;
UPDATE char_inventory SET extra = X'03830000E067FB05F0010000000000000000000000000000' WHERE item_id = 24194;

-- 2. The ten furnace items (Jewels: Ex, not Rare; Shards: neither).
INSERT OR IGNORE INTO items
 (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs,skill,rare,ex) VALUES
 (10001,'Jewel of Rev.',99,0,'',0,'A brilliant stone brimming with immense hope.',0,0,0,0,0,1),
 (10002,'Jewel of Cam.',99,0,'',0,'A brilliant stone brimming with immense trust.',0,0,0,0,0,1),
 (10003,'Jewel of Per.',99,0,'',0,'A brilliant stone brimming with immense bravery.',0,0,0,0,0,1),
 (10004,'Jewel of Des.',99,0,'',0,'A brilliant stone brimming with immense justice.',0,0,0,0,0,1),
 (10005,'Jewel of Aff.',99,0,'',0,'A brilliant stone brimming with immense mercy.',0,0,0,0,0,1),
 (10006,'Shard of Hope',99,0,'',0,'A soft sliver of condensed hope.',0,0,0,0,0,0),
 (10007,'Shard of Trust',99,0,'',0,'A soft sliver of condensed trust.',0,0,0,0,0,0),
 (10008,'Shard of Bravery',99,0,'',0,'A soft sliver of condensed bravery.',0,0,0,0,0,0),
 (10009,'Shard of Justice',99,0,'',0,'A soft sliver of condensed justice.',0,0,0,0,0,0),
 (10010,'Shard of Mercy',99,0,'',0,'A soft sliver of condensed mercy.',0,0,0,0,0,0);

-- 3. Give one stack of each to both mains, into their first free inventory slots.
--    Matched by name so the grant survives a database whose character ids differ.
WITH RECURSIVE
  target(character_id) AS (
    SELECT id FROM characters WHERE lower(name) IN ('onedough', 'twodough')
  ),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  free AS (
    SELECT t.character_id, n.n AS slot,
           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY n.n) AS rn
    FROM target t CROSS JOIN nums n
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = t.character_id AND ci.container = 0 AND ci.slot = n.n
    )
  ),
  want AS (
    SELECT t.character_id, w.item_id,
           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY w.item_id) AS rn
    FROM target t CROSS JOIN (SELECT 10001 AS item_id UNION ALL SELECT 10002 UNION ALL
      SELECT 10003 UNION ALL SELECT 10004 UNION ALL SELECT 10005 UNION ALL
      SELECT 10006 UNION ALL SELECT 10007 UNION ALL SELECT 10008 UNION ALL
      SELECT 10009 UNION ALL SELECT 10010) AS w
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = t.character_id AND ci.item_id = w.item_id
    )
  )
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT w.character_id, 0, f.slot, w.item_id, 99
FROM want w JOIN free f ON f.character_id = w.character_id AND f.rn = w.rn;
