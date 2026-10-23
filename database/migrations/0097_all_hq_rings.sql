-- Every +1 ring on Onedough and Twodough (migration 97).
--
-- Migration 96 handled the three rings the GearSwap libraries use and the
-- Adoulin/Shneddick question.  This pass grants the whole set: every ring
-- with a +1 variant in LandSandBoat's item_equipment table (94 items), two
-- copies each on both mains, in the same wardrobe-first order as migrations
-- 66/89/90/96.
--
-- Names are the client's English item names (xi.res.item(id).name.en);
-- levels, job masks and slot masks are LSB's item_equipment rows.  Item
-- rows the database does not know yet are added; existing rows are left
-- alone so a hand-edited name survives.  The grant tops each ring up to two
-- copies, so a re-run only fills what is missing.

INSERT OR IGNORE INTO items
 (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES
 (10769,'Gelatinous Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (10771,'Cacoethic Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (10795,'Blenmot''s Ring +1',1,0,'ring1',96,'All +1 rings grant.',0,24576,4194303),
 (11059,'Hajduk Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (11645,'Arewe Ring +1',1,0,'ring1',80,'All +1 rings grant.',0,24576,4194303),
 (11665,'Phrygian Ring +1',1,0,'ring1',80,'All +1 rings grant.',0,24576,4194303),
 (13281,'Sniper''s Ring +1',1,0,'ring1',40,'All +1 rings grant.',0,24576,4194303),
 (13283,'Saintly Ring +1',1,0,'ring1',10,'All +1 rings grant.',0,24576,4194303),
 (13285,'Eremite''s Ring +1',1,0,'ring1',10,'All +1 rings grant.',0,24576,4194303),
 (13492,'Copper Ring +1',1,0,'ring1',1,'All +1 rings grant.',0,24576,4194303),
 (13493,'Brass Ring +1',1,0,'ring1',7,'All +1 rings grant.',0,24576,4194303),
 (13494,'Shell Ring +1',1,0,'ring1',11,'All +1 rings grant.',0,24576,4194303),
 (13498,'Platinum Ring +1',1,0,'ring1',60,'All +1 rings grant.',0,24576,4194303),
 (13499,'Leather Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (13500,'Bone Ring +1',1,0,'ring1',16,'All +1 rings grant.',0,24576,4194303),
 (13501,'Beetle Ring +1',1,0,'ring1',21,'All +1 rings grant.',0,24576,4194303),
 (13502,'Horn Ring +1',1,0,'ring1',35,'All +1 rings grant.',0,24576,4194303),
 (13503,'Carapace Ring +1',1,0,'ring1',45,'All +1 rings grant.',0,24576,4194303),
 (13513,'Scorpion Ring +1',1,0,'ring1',55,'All +1 rings grant.',0,24576,4194303),
 (13518,'Silver Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (13519,'Mythril Ring +1',1,0,'ring1',24,'All +1 rings grant.',0,24576,4194303),
 (13520,'Gold Ring +1',1,0,'ring1',45,'All +1 rings grant.',0,24576,4194303),
 (13545,'Demon''s Ring +1',1,0,'ring1',60,'All +1 rings grant.',0,24576,4194303),
 (13556,'Behemoth Ring +1',1,0,'ring1',70,'All +1 rings grant.',0,24576,4194303),
 (14592,'Reflex Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (14593,'Courage Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (14594,'Kldg. Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (14595,'Balance Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (14596,'Trq. Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (14597,'Stamina Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (14598,'Energy Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (14599,'Hope Ring +1',1,0,'ring1',14,'All +1 rings grant.',0,24576,4194303),
 (14600,'Alacrity Ring +1',1,0,'ring1',36,'All +1 rings grant.',0,24576,4194303),
 (14601,'Puissance Ring +1',1,0,'ring1',36,'All +1 rings grant.',0,24576,4194303),
 (14602,'Wisdom Ring +1',1,0,'ring1',36,'All +1 rings grant.',0,24576,4194303),
 (14603,'Deft Ring +1',1,0,'ring1',36,'All +1 rings grant.',0,24576,4194303),
 (14604,'Solace Ring +1',1,0,'ring1',36,'All +1 rings grant.',0,24576,4194303),
 (14605,'Verve Ring +1',1,0,'ring1',36,'All +1 rings grant.',0,24576,4194303),
 (14606,'Aura Ring +1',1,0,'ring1',36,'All +1 rings grant.',0,24576,4194303),
 (14607,'Loyalty Ring +1',1,0,'ring1',36,'All +1 rings grant.',0,24576,4194303),
 (14608,'Celerity Ring +1',1,0,'ring1',54,'All +1 rings grant.',0,24576,4194303),
 (14609,'Victory Ring +1',1,0,'ring1',54,'All +1 rings grant.',0,24576,4194303),
 (14610,'Genius Ring +1',1,0,'ring1',54,'All +1 rings grant.',0,24576,4194303),
 (14611,'Grace Ring +1',1,0,'ring1',54,'All +1 rings grant.',0,24576,4194303),
 (14612,'Serenity Ring +1',1,0,'ring1',54,'All +1 rings grant.',0,24576,4194303),
 (14613,'Vigor Ring +1',1,0,'ring1',54,'All +1 rings grant.',0,24576,4194303),
 (14614,'Mystic Ring +1',1,0,'ring1',54,'All +1 rings grant.',0,24576,4194303),
 (14615,'Allure Ring +1',1,0,'ring1',54,'All +1 rings grant.',0,24576,4194303),
 (14617,'Nimble Ring +1',1,0,'ring1',72,'All +1 rings grant.',0,24576,4194303),
 (14618,'Triumph Ring +1',1,0,'ring1',72,'All +1 rings grant.',0,24576,4194303),
 (14619,'Omn. Ring +1',1,0,'ring1',72,'All +1 rings grant.',0,24576,4194303),
 (14620,'Adroit Ring +1',1,0,'ring1',72,'All +1 rings grant.',0,24576,4194303),
 (14621,'Cmn. Ring +1',1,0,'ring1',72,'All +1 rings grant.',0,24576,4194303),
 (14622,'Robust Ring +1',1,0,'ring1',72,'All +1 rings grant.',0,24576,4194303),
 (14623,'Hades Ring +1',1,0,'ring1',72,'All +1 rings grant.',0,24576,4194303),
 (14624,'Heavens Ring +1',1,0,'ring1',72,'All +1 rings grant.',0,24576,4194303),
 (14627,'Dragon Ring +1',1,0,'ring1',73,'All +1 rings grant.',0,24576,4194303),
 (15781,'Cerberus Ring +1',1,0,'ring1',75,'All +1 rings grant.',0,24576,4194303),
 (15789,'Marid Ring +1',1,0,'ring1',67,'All +1 rings grant.',0,24576,4194303),
 (15812,'Wivre Ring +1',1,0,'ring1',61,'All +1 rings grant.',0,24576,4194303),
 (15816,'Ladybug Ring +1',1,0,'ring1',65,'All +1 rings grant.',0,24576,4194303),
 (15837,'Smilodon Ring +1',1,0,'ring1',32,'All +1 rings grant.',0,24576,4194303),
 (15855,'Krousis Ring +1',1,0,'ring1',66,'All +1 rings grant.',0,24576,4194303),
 (26180,'Varar Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26182,'Chirich Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26184,'Stikini Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26192,'Adoulin Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26193,'Woltaris Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26194,'Weather. Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26195,'Jann. Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26196,'Renaye Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26197,'Gorney Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26198,'Haverton Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26199,'Karieyh Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26200,'Vocane Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26201,'Thur. Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26202,'Shneddick Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (26203,'Orvail Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27559,'Mephitas''s Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27561,'Apeile Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,65),
 (27563,'Metamor. Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27565,'Ifrit Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27567,'Levia. Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27569,'Ramuh Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27571,'Titan Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27573,'Garuda Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27575,'Shiva Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27577,'Carb. Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (27579,'Fenrir Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (28536,'Arvina Ringlet +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (28537,'Lunette Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (28543,'Rhodium Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (28545,'Yacuruna Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303),
 (28584,'Vexer Ring +1',1,0,'ring1',99,'All +1 rings grant.',0,24576,4194303);

CREATE TEMP TABLE IF NOT EXISTS hq_rings97 (item_id INTEGER PRIMARY KEY);
DELETE FROM hq_rings97;
INSERT INTO hq_rings97 (item_id) VALUES
 (10769),
 (10771),
 (10795),
 (11059),
 (11645),
 (11665),
 (13281),
 (13283),
 (13285),
 (13492),
 (13493),
 (13494),
 (13498),
 (13499),
 (13500),
 (13501),
 (13502),
 (13503),
 (13513),
 (13518),
 (13519),
 (13520),
 (13545),
 (13556),
 (14592),
 (14593),
 (14594),
 (14595),
 (14596),
 (14597),
 (14598),
 (14599),
 (14600),
 (14601),
 (14602),
 (14603),
 (14604),
 (14605),
 (14606),
 (14607),
 (14608),
 (14609),
 (14610),
 (14611),
 (14612),
 (14613),
 (14614),
 (14615),
 (14617),
 (14618),
 (14619),
 (14620),
 (14621),
 (14622),
 (14623),
 (14624),
 (14627),
 (15781),
 (15789),
 (15812),
 (15816),
 (15837),
 (15855),
 (26180),
 (26182),
 (26184),
 (26192),
 (26193),
 (26194),
 (26195),
 (26196),
 (26197),
 (26198),
 (26199),
 (26200),
 (26201),
 (26202),
 (26203),
 (27559),
 (27561),
 (27563),
 (27565),
 (27567),
 (27569),
 (27571),
 (27573),
 (27575),
 (27577),
 (27579),
 (28536),
 (28537),
 (28543),
 (28545),
 (28584);

CREATE TEMP TABLE IF NOT EXISTS hq_ring_chars97 (character_id INTEGER PRIMARY KEY);
DELETE FROM hq_ring_chars97;
INSERT INTO hq_ring_chars97 (character_id)
SELECT id FROM characters WHERE name IN ('Onedough','Twodough');

-- Two copies of each ring per character.  Rings do not stack, so copies
-- are separate rows; quantity is counted in case a hand-inserted row
-- stacked them.
CREATE TEMP TABLE IF NOT EXISTS hq_ring_need97 (
  character_id INTEGER NOT NULL,
  item_id      INTEGER NOT NULL,
  need         INTEGER NOT NULL,
  PRIMARY KEY (character_id,item_id)
);
DELETE FROM hq_ring_need97;
INSERT INTO hq_ring_need97 (character_id,item_id,need)
SELECT c.character_id, r.item_id,
       2 - COALESCE((SELECT SUM(ci.quantity) FROM char_inventory ci
                      WHERE ci.character_id = c.character_id AND ci.item_id = r.item_id), 0)
  FROM hq_ring_chars97 c
  CROSS JOIN hq_rings97 r
 WHERE COALESCE((SELECT SUM(ci.quantity) FROM char_inventory ci
                  WHERE ci.character_id = c.character_id AND ci.item_id = r.item_id), 0) < 2;

WITH RECURSIVE
  bags(container, ord) AS (
    VALUES (8,1),(10,2),(11,3),(12,4),(13,5),(14,6),(15,7),(16,8),
           (1,9),(5,10),(6,11),(7,12),(9,13)
  ),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  copies(character_id,item_id,copy_no) AS (
    SELECT n.character_id, n.item_id, v.i
      FROM hq_ring_need97 n
      JOIN (SELECT 1 AS i UNION ALL SELECT 2) v ON v.i <= n.need
  ),
  free(character_id,container,slot,rn) AS (
    SELECT c.character_id, b.container, ns.n,
           ROW_NUMBER() OVER (PARTITION BY c.character_id ORDER BY b.ord, ns.n)
      FROM hq_ring_chars97 c
      CROSS JOIN bags b
      CROSS JOIN nums ns
     WHERE NOT EXISTS (
           SELECT 1 FROM char_inventory ci
            WHERE ci.character_id = c.character_id
              AND ci.container = b.container
              AND ci.slot = ns.n
     )
  ),
  wanted(character_id,item_id,copy_no,rn) AS (
    SELECT character_id, item_id, copy_no,
           ROW_NUMBER() OVER (PARTITION BY character_id ORDER BY item_id, copy_no)
      FROM copies
  )
INSERT INTO char_inventory (character_id,container,slot,item_id,quantity)
SELECT w.character_id, f.container, f.slot, w.item_id, 1
  FROM wanted w
  JOIN free f ON f.character_id = w.character_id AND f.rn = w.rn;
