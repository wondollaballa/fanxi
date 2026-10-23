-- Odyssey Rank 30 additions (migration 72).
--
-- Adds every Gleti's and Agwu's armour piece and every Odyssey weapon the
-- server did not know yet, then grants them to the first character's
-- wardrobes. Nyame and Sakpata's armour already exist from earlier
-- migrations. The Rank 30 rows themselves live in data/odyssey_r30.json
-- and in the gearswap libraries; the client tooltip cannot print them (see
-- docs/odyssey-r30.md) until the server learns retail's extdata augment
-- encoding, so !r30 is the in-game view for now.
--
-- Item ids, slots, job masks and the Rank 30 values are factual game data
-- cross-checked against BG Wiki. The SQL is Fanxi's own.

INSERT OR IGNORE INTO items
 (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES
 (21527,'Sakpata''s Fists',1,0,'main',99,'Odyssey Rank 30 weapon.',0,1,131074),
 (21567,'Gleti''s Knife',1,0,'main',99,'Odyssey Rank 30 weapon.',0,3,333360),
 (21637,'Sakpata''s Sword',1,0,'main',99,'Odyssey Rank 30 weapon.',0,3,32848),
 (21675,'Agwu''s Claymore',1,0,'main',99,'Odyssey Rank 30 weapon.',0,1,2097345),
 (21724,'Agwu''s Axe',1,0,'main',99,'Odyssey Rank 30 weapon.',0,3,256),
 (21832,'Agwu''s Scythe',1,0,'main',99,'Odyssey Rank 30 weapon.',0,1,128),
 (22150,'Gleti''s Crossbow',1,0,'range',99,'Odyssey Rank 30 weapon.',0,4,1024),
 (23756,'Gleti''s Mask',1,0,'head',99,'Odyssey Rank 30 armour (Ngai).',0,16,303392),
 (23759,'Agwu''s Cap',1,0,'head',99,'Odyssey Rank 30 armour (Ongo).',0,16,3670024),
 (23763,'Gleti''s Cuirass',1,0,'body',99,'Odyssey Rank 30 armour (Ngai).',0,32,303392),
 (23766,'Agwu''s Robe',1,0,'body',99,'Odyssey Rank 30 armour (Ongo).',0,32,3670024),
 (23770,'Gleti''s Gauntlets',1,0,'hands',99,'Odyssey Rank 30 armour (Ngai).',0,64,303392),
 (23773,'Agwu''s Gages',1,0,'hands',99,'Odyssey Rank 30 armour (Ongo).',0,64,3670024),
 (23777,'Gleti''s Breeches',1,0,'legs',99,'Odyssey Rank 30 armour (Ngai).',0,128,303392),
 (23780,'Agwu''s Slops',1,0,'legs',99,'Odyssey Rank 30 armour (Ongo).',0,128,3670024),
 (23784,'Gleti''s Boots',1,0,'feet',99,'Odyssey Rank 30 armour (Ngai).',0,256,303392),
 (23787,'Agwu''s Pigaches',1,0,'feet',99,'Odyssey Rank 30 armour (Ongo).',0,256,3670024);

-- Give the new pieces a home in the wardrobes, like migration 66 did.
WITH RECURSIVE
  target(character_id) AS (SELECT id FROM characters WHERE id = 1),
  containers(container, ord) AS (
    VALUES (8,1),(10,2),(11,3),(12,4),(13,5),(14,6),(15,7),(16,8),
           (1,9),(5,10),(6,11),(7,12),(9,13)
  ),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  free AS (
    SELECT c.container, n.n AS slot,
           ROW_NUMBER() OVER (ORDER BY c.ord, n.n) AS rn
    FROM containers c CROSS JOIN nums n
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = 1 AND ci.container = c.container AND ci.slot = n.n
    )
    AND n.n < 80
  ),
  want AS (
    SELECT w.item_id, ROW_NUMBER() OVER (ORDER BY w.item_id) AS rn
    FROM (SELECT 21527 AS item_id UNION ALL SELECT 21567 AS item_id UNION ALL SELECT 21637 AS item_id UNION ALL SELECT 21675 AS item_id UNION ALL SELECT 21724 AS item_id UNION ALL SELECT 21832 AS item_id UNION ALL SELECT 22150 AS item_id UNION ALL SELECT 23756 AS item_id UNION ALL SELECT 23759 AS item_id UNION ALL SELECT 23763 AS item_id UNION ALL SELECT 23766 AS item_id UNION ALL SELECT 23770 AS item_id UNION ALL SELECT 23773 AS item_id UNION ALL SELECT 23777 AS item_id UNION ALL SELECT 23780 AS item_id UNION ALL SELECT 23784 AS item_id UNION ALL SELECT 23787 AS item_id) AS w
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = 1 AND ci.item_id = w.item_id
    )
  )
INSERT OR IGNORE INTO char_inventory (character_id,container,slot,item_id,quantity)
SELECT t.character_id, free.container, free.slot, want.item_id, 1
FROM want JOIN free ON free.rn = want.rn CROSS JOIN target t;
