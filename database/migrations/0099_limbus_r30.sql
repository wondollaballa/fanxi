-- Limbus Rank 30 armour (migration 99).
--
-- Adds the top tier of all five Limbus families -- Duty, Revelation,
-- Sworn, Indomitable and Clemency -- then grants the 25 pieces to
-- characters 1 and 2 (Onedough and Twodough) with the Rank 30 augment
-- block in the item exdata.  Lower tiers are not added: they are the
-- same suit one and two steps down.
--
-- Item ids, slots, job masks and stat lines are factual game data from
-- BG Wiki (the set pages and each item page's ffxidb link).  The
-- 24-byte block is LandSandBoat's Exdata::AugmentBundle with rank 30 /
-- tier 3 and the piece's own augment bundle index; Limbus uses RP curve
-- B, whose rank-30 total is 55,800.  The bundle indices are the client's
-- own table (LandSandBoat's xi.data.augments.bundles, parsed from the
-- MNC2 data); they were matched to the Rank 30 rows in
-- docs/limbus-r30.md by content.
--
-- Generated from data/limbus_r30.json by tools/gen_limbus_r30.py.

INSERT OR IGNORE INTO items
 (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES
 (24167,'Duty Crown',1,0,'head',99,'Limbus Su5 armour (Duty Armor Set).',0,16,393506),
 (24170,'Duty Cyclas',1,0,'body',99,'Limbus Su5 armour (Duty Armor Set).',0,32,393506),
 (24173,'Duty Gauntlets',1,0,'hands',99,'Limbus Su5 armour (Duty Armor Set).',0,64,393506),
 (24176,'Duty Flanchard',1,0,'legs',99,'Limbus Su5 armour (Duty Armor Set).',0,128,393506),
 (24179,'Duty Sollerets',1,0,'feet',99,'Limbus Su5 armour (Duty Armor Set).',0,256,393506),
 (24122,'Revelation Masque',1,0,'head',99,'Limbus Su5 armour (Revelation Armor Set).',0,16,4609),
 (24125,'Revelation Plate.',1,0,'body',99,'Limbus Su5 armour (Revelation Armor Set).',0,32,4609),
 (24128,'Revelation Gaunt.',1,0,'hands',99,'Limbus Su5 armour (Revelation Armor Set).',0,64,4609),
 (24131,'Revelation Brais',1,0,'legs',99,'Limbus Su5 armour (Revelation Armor Set).',0,128,4609),
 (24134,'Revelation Sab.',1,0,'feet',99,'Limbus Su5 armour (Revelation Armor Set).',0,256,4609),
 (24137,'Sworn Crown',1,0,'head',99,'Limbus Su5 armour (Sworn Armor Set).',0,16,2130132),
 (24140,'Sworn Platemail',1,0,'body',99,'Limbus Su5 armour (Sworn Armor Set).',0,32,2130132),
 (24143,'Sworn Gauntlets',1,0,'hands',99,'Limbus Su5 armour (Sworn Armor Set).',0,64,2130132),
 (24146,'Sworn Brais',1,0,'legs',99,'Limbus Su5 armour (Sworn Armor Set).',0,128,2130132),
 (24149,'Sworn Sabatons',1,0,'feet',99,'Limbus Su5 armour (Sworn Armor Set).',0,256,2130132),
 (24152,'Indom. Petasos',1,0,'head',99,'Limbus Su5 armour (Indomitable Attire Set).',0,16,1589256),
 (24155,'Indomitable Coat',1,0,'body',99,'Limbus Su5 armour (Indomitable Attire Set).',0,32,1589256),
 (24158,'Indom. Gloves',1,0,'hands',99,'Limbus Su5 armour (Indomitable Attire Set).',0,64,1589256),
 (24161,'Indom. Tonban',1,0,'legs',99,'Limbus Su5 armour (Indomitable Attire Set).',0,128,1589256),
 (24164,'Indom. Sabots',1,0,'feet',99,'Limbus Su5 armour (Indomitable Attire Set).',0,256,1589256),
 (24182,'Clemen. Somen',1,0,'head',99,'Limbus Su5 armour (Clemency Armor Set).',0,16,76800),
 (24185,'Clemen. Hara.',1,0,'body',99,'Limbus Su5 armour (Clemency Armor Set).',0,32,76800),
 (24188,'Clemency Kote',1,0,'hands',99,'Limbus Su5 armour (Clemency Armor Set).',0,64,76800),
 (24191,'Clem. Haidate',1,0,'legs',99,'Limbus Su5 armour (Clemency Armor Set).',0,128,76800),
 (24194,'Clem. Sune-Ate',1,0,'feet',99,'Limbus Su5 armour (Clemency Armor Set).',0,256,76800);

-- Base modifiers from each piece's stat line.

INSERT OR REPLACE INTO item_mods (item_id,mod_id,value) VALUES
  (24122,1,155), (24122,2,107), (24122,8,41), (24122,9,38), (24122,10,29), (24122,11,33), (24122,12,31), (24122,13,20), (24122,14,29), (24122,23,42), (24122,24,42), (24122,25,42), (24122,26,42), (24122,29,7), (24122,30,42), (24122,31,89), (24122,68,109), (24122,73,6), (24122,160,-600), (24122,165,600), (24122,384,600),
  (24125,1,185), (24125,2,130), (24125,8,47), (24125,9,45), (24125,10,37), (24125,11,37), (24125,12,39), (24125,13,28), (24125,14,37), (24125,23,42), (24125,24,42), (24125,25,42), (24125,26,42), (24125,29,7), (24125,30,42), (24125,31,100), (24125,68,123), (24125,73,8), (24125,160,-800), (24125,165,800), (24125,384,400),
  (24128,1,143), (24128,2,96), (24128,8,28), (24128,9,52), (24128,10,41), (24128,11,25), (24128,12,26), (24128,13,32), (24128,14,34), (24128,23,42), (24128,24,42), (24128,25,42), (24128,26,42), (24128,29,4), (24128,30,42), (24128,31,73), (24128,68,93), (24128,73,4), (24128,160,-400), (24128,165,400), (24128,384,400),
  (24131,1,167), (24131,2,119), (24131,8,57), (24131,10,35), (24131,11,34), (24131,12,43), (24131,13,22), (24131,14,28), (24131,23,42), (24131,24,42), (24131,25,42), (24131,26,42), (24131,29,6), (24131,30,42), (24131,31,110), (24131,68,119), (24131,73,7), (24131,160,-700), (24131,165,700), (24131,384,900),
  (24134,1,125), (24134,2,84), (24134,8,36), (24134,9,40), (24134,10,26), (24134,11,43), (24134,13,14), (24134,14,37), (24134,23,42), (24134,24,42), (24134,25,42), (24134,26,42), (24134,29,6), (24134,30,42), (24134,31,110), (24134,68,140), (24134,73,5), (24134,160,-500), (24134,165,500), (24134,384,300),
  (24137,1,161), (24137,2,141), (24137,5,121), (24137,8,36), (24137,9,29), (24137,10,49), (24137,11,26), (24137,12,26), (24137,13,34), (24137,14,24), (24137,23,42), (24137,25,42), (24137,28,35), (24137,29,6), (24137,30,42), (24137,31,137), (24137,68,82), (24137,160,-700), (24137,170,7), (24137,311,32), (24137,384,500),
  (24140,1,191), (24140,2,187), (24140,5,106), (24140,8,45), (24140,9,34), (24140,10,51), (24140,11,30), (24140,12,31), (24140,13,39), (24140,14,29), (24140,23,42), (24140,25,42), (24140,28,35), (24140,29,8), (24140,30,42), (24140,31,142), (24140,68,87), (24140,160,-900), (24140,170,9), (24140,311,32), (24140,384,300),
  (24143,1,149), (24143,2,96), (24143,5,76), (24143,8,27), (24143,9,44), (24143,10,55), (24143,12,21), (24143,13,44), (24143,14,29), (24143,23,42), (24143,25,42), (24143,28,35), (24143,29,5), (24143,30,42), (24143,31,100), (24143,68,68), (24143,160,-500), (24143,170,5), (24143,311,32), (24143,384,500),
  (24146,1,173), (24146,2,164), (24146,5,91), (24146,8,51), (24146,10,43), (24146,11,28), (24146,12,39), (24146,13,32), (24146,14,20), (24146,23,42), (24146,25,42), (24146,28,35), (24146,29,7), (24146,30,42), (24146,31,169), (24146,68,73), (24146,160,-800), (24146,170,8), (24146,311,32), (24146,384,500),
  (24149,1,131), (24149,2,119), (24149,5,62), (24149,8,32), (24149,9,29), (24149,10,39), (24149,11,40), (24149,13,30), (24149,14,35), (24149,23,42), (24149,25,42), (24149,28,35), (24149,29,6), (24149,30,42), (24149,31,169), (24149,68,101), (24149,160,-600), (24149,170,6), (24149,311,32), (24149,384,300),
  (24152,1,135), (24152,2,84), (24152,5,106), (24152,8,27), (24152,9,25), (24152,10,28), (24152,11,18), (24152,12,38), (24152,13,31), (24152,14,30), (24152,27,-6), (24152,28,40), (24152,29,9), (24152,30,42), (24152,31,94), (24152,68,79), (24152,160,-400), (24152,170,6), (24152,311,22), (24152,384,600),
  (24155,1,165), (24155,2,107), (24155,5,91), (24155,8,34), (24155,9,31), (24155,10,36), (24155,11,33), (24155,12,52), (24155,13,42), (24155,14,40), (24155,27,-10), (24155,28,40), (24155,29,10), (24155,30,42), (24155,31,110), (24155,68,87), (24155,160,-600), (24155,170,10), (24155,311,22), (24155,384,300),
  (24158,1,123), (24158,2,73), (24158,5,62), (24158,8,15), (24158,9,39), (24158,10,40), (24158,11,19), (24158,12,38), (24158,13,45), (24158,14,30), (24158,27,-4), (24158,28,40), (24158,29,7), (24158,30,42), (24158,31,88), (24158,68,68), (24158,160,-200), (24158,170,4), (24158,311,22), (24158,384,300),
  (24161,1,147), (24161,2,96), (24161,5,76), (24161,8,44), (24161,10,25), (24161,11,30), (24161,12,54), (24161,13,37), (24161,14,30), (24161,27,-8), (24161,28,40), (24161,29,9), (24161,30,42), (24161,31,126), (24161,68,68), (24161,160,-500), (24161,170,8), (24161,311,22), (24161,384,500),
  (24164,1,105), (24164,2,62), (24164,5,47), (24164,8,22), (24164,9,26), (24164,10,25), (24164,11,43), (24164,12,35), (24164,13,31), (24164,14,44), (24164,27,-4), (24164,28,40), (24164,29,9), (24164,30,42), (24164,31,126), (24164,68,95), (24164,160,-300), (24164,170,4), (24164,311,22), (24164,384,300),
  (24167,1,144), (24167,2,119), (24167,8,36), (24167,9,39), (24167,10,35), (24167,11,30), (24167,12,22), (24167,13,28), (24167,14,28), (24167,23,42), (24167,25,42), (24167,29,5), (24167,30,42), (24167,31,115), (24167,68,90), (24167,160,-500), (24167,288,5), (24167,289,5), (24167,384,600),
  (24170,1,174), (24170,2,141), (24170,8,42), (24170,9,45), (24170,10,44), (24170,11,33), (24170,12,29), (24170,13,35), (24170,14,35), (24170,23,42), (24170,25,42), (24170,29,9), (24170,30,42), (24170,31,126), (24170,68,95), (24170,160,-700), (24170,288,7), (24170,289,7), (24170,384,400),
  (24173,1,132), (24173,2,107), (24173,8,23), (24173,9,53), (24173,10,48), (24173,11,22), (24173,12,17), (24173,13,39), (24173,14,33), (24173,23,42), (24173,25,42), (24173,29,5), (24173,30,42), (24173,31,100), (24173,68,85), (24173,160,-300), (24173,288,3), (24173,289,3), (24173,384,400),
  (24176,1,156), (24176,2,130), (24176,8,52), (24176,10,42), (24176,11,39), (24176,12,33), (24176,13,29), (24176,14,26), (24176,23,42), (24176,25,42), (24176,29,8), (24176,30,42), (24176,31,131), (24176,68,84), (24176,160,-600), (24176,288,6), (24176,289,6), (24176,384,600),
  (24179,1,114), (24179,2,96), (24179,8,31), (24179,9,40), (24179,10,31), (24179,11,40), (24179,13,21), (24179,14,35), (24179,23,42), (24179,25,42), (24179,29,8), (24179,30,42), (24179,31,131), (24179,68,118), (24179,160,-400), (24179,288,4), (24179,289,4), (24179,384,300),
  (24182,1,157), (24182,2,96), (24182,8,34), (24182,9,41), (24182,10,27), (24182,11,40), (24182,12,22), (24182,13,22), (24182,14,23), (24182,23,42), (24182,24,42), (24182,25,42), (24182,26,42), (24182,29,6), (24182,30,42), (24182,31,105), (24182,68,79), (24182,160,-600), (24182,165,600), (24182,384,600), (24182,1081,6),
  (24185,1,187), (24185,2,119), (24185,8,42), (24185,9,52), (24185,10,35), (24185,11,50), (24185,12,29), (24185,13,28), (24185,14,29), (24185,23,42), (24185,24,42), (24185,25,42), (24185,26,42), (24185,29,8), (24185,30,42), (24185,31,115), (24185,68,102), (24185,160,-800), (24185,165,800), (24185,384,300), (24185,1081,8),
  (24188,1,145), (24188,2,84), (24188,8,30), (24188,9,57), (24188,10,41), (24188,11,30), (24188,12,21), (24188,13,35), (24188,14,27), (24188,23,42), (24188,24,42), (24188,25,42), (24188,26,42), (24188,29,5), (24188,30,42), (24188,31,88), (24188,68,68), (24188,160,-400), (24188,165,400), (24188,384,300), (24188,1081,4),
  (24191,1,169), (24191,2,107), (24191,8,47), (24191,10,27), (24191,11,51), (24191,12,37), (24191,13,23), (24191,14,18), (24191,23,42), (24191,24,42), (24191,25,42), (24191,26,42), (24191,29,7), (24191,30,42), (24191,31,137), (24191,68,68), (24191,160,-700), (24191,165,700), (24191,384,500), (24191,1081,7),
  (24194,1,127), (24194,2,73), (24194,8,30), (24194,9,42), (24194,10,21), (24194,11,63), (24194,13,19), (24194,14,35), (24194,23,42), (24194,24,42), (24194,25,42), (24194,26,42), (24194,29,6), (24194,30,42), (24194,31,137), (24194,68,98), (24194,160,-500), (24194,165,500), (24194,384,300), (24194,1081,5);

-- Give every piece to both characters, into their first free wardrobe slots.
WITH RECURSIVE
  target(character_id) AS (
    SELECT id FROM characters WHERE id IN (1, 2)
  ),
  containers(container, ord) AS (
    VALUES (8,1),(10,2),(11,3),(12,4),(13,5),(14,6),(15,7),(16,8),(1,9),(5,10),(6,11),(7,12),(9,13)
  ),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  free AS (
    SELECT t.character_id, c.container, n.n AS slot,
           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY c.ord, n.n) AS rn
    FROM target t CROSS JOIN containers c CROSS JOIN nums n
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = t.character_id AND ci.container = c.container AND ci.slot = n.n
    )
  ),
  want AS (
    SELECT t.character_id, w.item_id,
           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY w.item_id) AS rn
    FROM target t CROSS JOIN (SELECT 24122 AS item_id UNION ALL SELECT 24125 AS item_id UNION ALL SELECT 24128 AS item_id UNION ALL SELECT 24131 AS item_id UNION ALL SELECT 24134 AS item_id UNION ALL SELECT 24137 AS item_id UNION ALL SELECT 24140 AS item_id UNION ALL SELECT 24143 AS item_id UNION ALL SELECT 24146 AS item_id UNION ALL SELECT 24149 AS item_id UNION ALL SELECT 24152 AS item_id UNION ALL SELECT 24155 AS item_id UNION ALL SELECT 24158 AS item_id UNION ALL SELECT 24161 AS item_id UNION ALL SELECT 24164 AS item_id UNION ALL SELECT 24167 AS item_id UNION ALL SELECT 24170 AS item_id UNION ALL SELECT 24173 AS item_id UNION ALL SELECT 24176 AS item_id UNION ALL SELECT 24179 AS item_id UNION ALL SELECT 24182 AS item_id UNION ALL SELECT 24185 AS item_id UNION ALL SELECT 24188 AS item_id UNION ALL SELECT 24191 AS item_id UNION ALL SELECT 24194 AS item_id) AS w
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = t.character_id AND ci.item_id = w.item_id
    )
  )
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT w.character_id, f.container, f.slot, w.item_id, 1
FROM want w JOIN free f ON f.character_id = w.character_id AND f.rn = w.rn;

-- Rank 30 augment block for every copy: rank 30, tier 3, 55,800 RP
-- (curve B), and the piece's own bundle index.  Updating by item id
-- covers both main characters and any later copy of the suit.
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
