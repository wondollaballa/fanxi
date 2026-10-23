-- Prime weapons and the missing Dark Knight gear (migration 87).
--
-- Migration 66 grants every item referenced by the GearSwap libraries, but the
-- Dark Knight AF/relic/empyrean pieces were appended to its list after this
-- database had already run it.  Character 1 therefore has none of them.  The
-- same pass adds the twelve Prime weapons the server did not know yet.
--
-- Prime weapons are the sixteen Sortie weapons introduced in 2022.  Stages two
-- through five share a name; the last item id is the iLvl 119 III form that the
-- other Prime entries use.  Item ids, job masks, slots and weapon stats are
-- factual game data from LandSandBoat's item_equipment/item_weapon tables and
-- the FFXIclopedia Prime Weapons page.  Models 907-917 are the client's Prime
-- models where they have been verified; the remaining ids fall back to the
-- REMA model so the weapon still draws, and can be corrected with !model.
--
-- Existing Prime weapons (Laphria, Spalirisos, Dokoku, Opashoro) keep their
-- rows; only their weapon stats are refreshed.  The new weapons go to the
-- weapon wardrobe and the Dark Knight pieces to the first free slots of the
-- second wardrobe, the same way migrations 66, 72 and 77 allocated gear.

INSERT OR IGNORE INTO items
 (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs,skill) VALUES
 (21535,'Varga Purnikawa',1,0,'main',99,'Monk and puppetmaster Prime hand-to-hand weapon, iLvl 119 III.',474,1,131074,1),
 (21590,'Mpu Gandring',1,0,'main',99,'Red mage, thief, bard and dancer Prime dagger, iLvl 119 III.',907,3,262704,2),
 (21646,'Caliburnus',1,0,'main',99,'Red mage, paladin and blue mage Prime sword, iLvl 119 III.',545,3,32848,3),
 (21653,'Helheim',1,0,'main',99,'Warrior, paladin, dark knight and rune fencer Prime great sword, iLvl 119 III.',909,1,2097345,4),
 (21837,'Foenaria',1,0,'main',99,'Dark knight Prime scythe, iLvl 119 III.',913,1,128,7),
 (21891,'Gae Buide',1,0,'main',99,'Dragoon Prime polearm, iLvl 119 III.',912,1,8192,8),
 (21986,'Kusanagi',1,0,'main',99,'Samurai Prime great katana, iLvl 119 III.',514,1,2048,10),
 (22002,'Lorg Mor',1,0,'main',99,'White mage and geomancer Prime club, iLvl 119 III.',553,3,1048580,11),
 (22163,'Pinaka',1,0,'range',99,'Ranger Prime bow, iLvl 119 III.',0,4,1024,25),
 (22164,'Earp',1,0,'range',99,'Ranger and corsair Prime gun, iLvl 119 III.',915,4,66560,26),
 (22307,'Loughnashade',1,0,'range',99,'Bard Prime horn, iLvl 119 III.',916,4,512,0),
 (26495,'Duban',1,0,'sub',99,'Paladin Prime shield, iLvl 119 III.',0,2,64,0);

INSERT OR REPLACE INTO item_weapon (item_id,skill,ilvl_skill,delay,dmg,dmg_type) VALUES
 (21535,1,277,596,213,4),   -- Varga Purnikawa
 (21590,2,269,176,137,1),   -- Mpu Gandring
 (21646,3,0,233,181,2),     -- Caliburnus
 (21653,4,0,431,318,2),     -- Helheim
 (21785,6,0,488,380,2),     -- Laphria (existing)
 (21730,5,0,280,218,2),     -- Spalirisos (existing)
 (21837,7,0,513,400,2),     -- Foenaria
 (21891,8,0,492,383,1),     -- Gae Buide
 (21932,9,0,210,163,2),     -- Dokoku (existing)
 (21986,10,0,437,340,2),    -- Kusanagi
 (22002,11,0,308,227,3),    -- Lorg Mor
 (22106,12,0,390,304,3),    -- Opashoro (existing)
 (22163,25,0,524,324,1),    -- Pinaka
 (22164,26,0,582,162,1),    -- Earp
 (22307,42,0,240,1,0);      -- Loughnashade

INSERT OR IGNORE INTO item_mods (item_id,mod_id,value) VALUES
 (21535,8,35),    -- STR
 (21535,9,35),    -- DEX
 (21535,25,35),   -- Accuracy
 (21535,30,35),   -- Magic Accuracy
 (21535,165,15),  -- Critical hit rate
 (21535,355,231), -- Adds weapon skill: Maru Kala
 (21590,9,35),    -- DEX
 (21590,11,35),   -- AGI
 (21590,14,35),   -- CHR
 (21590,25,35),   -- Accuracy
 (21590,30,35),   -- Magic Accuracy
 (21590,302,6),   -- Triple Attack
 (21590,355,232); -- Adds weapon skill: Merciless Strike

-- Duban is a size-6 shield, the largest category; without this row the server
-- treats it as a normal sub item and never rolls a block.
INSERT OR REPLACE INTO item_shield (item_id,size,level,ilevel) VALUES (26495,6,99,119);

-- The twelve Prime weapons Onedough does not own, into free weapon-wardrobe slots.
WITH RECURSIVE
  target(character_id) AS (SELECT id FROM characters WHERE id = 1),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  free AS (
    SELECT n AS slot, ROW_NUMBER() OVER (ORDER BY n) AS rn
    FROM nums
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = 1 AND ci.container = 14 AND ci.slot = n
    )
    AND n < 80
  ),
  want(item_id, rn) AS (VALUES
    (21535,1), (21590,2), (21646,3), (21653,4), (21837,5), (21891,6),
    (21986,7), (22002,8), (22163,9), (22164,10), (22307,11), (26495,12)
  )
INSERT OR IGNORE INTO char_inventory (character_id,container,slot,item_id,quantity)
SELECT t.character_id, 14, free.slot, want.item_id, 1
FROM want JOIN free ON free.rn = want.rn CROSS JOIN target t
WHERE NOT EXISTS (
  SELECT 1 FROM char_inventory ci
  WHERE ci.character_id = 1 AND ci.item_id = want.item_id
);

-- The Dark Knight AF/relic/empyrean pieces, into free wardrobe-2 slots.
WITH RECURSIVE
  target(character_id) AS (SELECT id FROM characters WHERE id = 1),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  free AS (
    SELECT n AS slot, ROW_NUMBER() OVER (ORDER BY n) AS rn
    FROM nums
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = 1 AND ci.container = 10 AND ci.slot = n
    )
    AND n < 80
  ),
  want(item_id, rn) AS (VALUES
    (23494,1), (23561,2), (23695,3),
    (23902,4), (23925,5),
    (23947,6), (23970,7),
    (23992,8), (24015,9),
    (24037,10), (24060,11),
    (24082,12)
  )
INSERT OR IGNORE INTO char_inventory (character_id,container,slot,item_id,quantity)
SELECT t.character_id, 10, free.slot, want.item_id, 1
FROM want JOIN free ON free.rn = want.rn CROSS JOIN target t
WHERE NOT EXISTS (
  SELECT 1 FROM char_inventory ci
  WHERE ci.character_id = 1 AND ci.item_id = want.item_id
);
