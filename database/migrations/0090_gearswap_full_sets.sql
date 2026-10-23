-- Complete the reforged AF/relic/empyrean sets (migration 90).
--
-- Migration 89 put every item the 22 gearswap libraries name into Onedough's
-- bags. The libraries use only some pieces of each job's 15-piece reforged
-- AF (+4), relic (+4) and empyrean (+3) sets, so a wardrobe could still show
-- four Fallen's pieces and three Heathen's pieces for Dark Knight. This pass
-- fills the remaining set pieces, including the 55 rows the server did not
-- have yet (LandSandBoat marks the +4 sets 'not implemented' but has the ids,
-- names, slots and job masks).
--
-- Existing rows are left alone. New rows carry model 0 (the client draws the
-- wearer's own gear from the item id; other clients and /lockstyle need a real
-- grap model, which is not published for these sets) and no item_mods yet.
-- The grant is the same wardrobe-first allocation as migrations 66/89.

INSERT OR IGNORE INTO items
 (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES
 (23422,'Ebers Cap +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,4),
 (23423,'Wicce Petasos +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,8),
 (23424,'Lethargy Chappel +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,16),
 (23426,'Chevalier''s Armet +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,64),
 (23427,'Heathen''s Burgeonet +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,128),
 (23429,'Fili Calot +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,512),
 (23431,'Kasuga Kabuto +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,2048),
 (23438,'Maculele Tiara +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,262144),
 (23440,'Azimuth Hood +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,1048576),
 (23441,'Erilaz Galea +3',1,0,'head',99,'Reforged empyrean armour, iLvl 119.',0,16,2097152),
 (23555,'Bhikku Gloves +3',1,0,'hands',99,'Reforged empyrean armour, iLvl 119.',0,64,2),
 (23558,'Lethargy Gantherots +3',1,0,'hands',99,'Reforged empyrean armour, iLvl 119.',0,64,16),
 (23560,'Chevalier''s Gauntlets +3',1,0,'hands',99,'Reforged empyrean armour, iLvl 119.',0,64,64),
 (23563,'Fili Manchettes +3',1,0,'hands',99,'Reforged empyrean armour, iLvl 119.',0,64,512),
 (23564,'Amini Glovelettes +3',1,0,'hands',99,'Reforged empyrean armour, iLvl 119.',0,64,1024),
 (23569,'Hashishin Bazubands +3',1,0,'hands',99,'Reforged empyrean armour, iLvl 119.',0,64,32768),
 (23572,'Maculele Bangles +3',1,0,'hands',99,'Reforged empyrean armour, iLvl 119.',0,64,262144),
 (23623,'Ebers Pantaloons +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,4),
 (23624,'Wicce Chausses +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,8),
 (23625,'Lethargy Fuseau +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,16),
 (23626,'Skulker''s Culottes +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,32),
 (23627,'Chevalier''s Cuisses +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,64),
 (23628,'Heathen''s Flanchard +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,128),
 (23630,'Fili Rhingrave +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,512),
 (23631,'Amini Bragues +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,1024),
 (23632,'Kasuga Haidate +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,2048),
 (23636,'Hashishin Tayt +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,32768),
 (23637,'Chasseur''s Culottes +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,65536),
 (23639,'Maculele Tights +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,262144),
 (23641,'Azimuth Tights +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,1048576),
 (23642,'Erilaz Leg Guards +3',1,0,'legs',99,'Reforged empyrean armour, iLvl 119.',0,128,2097152),
 (23689,'Bhikku Gaiters +3',1,0,'feet',99,'Reforged empyrean armour, iLvl 119.',0,256,2),
 (23692,'Lethargy Houseaux +3',1,0,'feet',99,'Reforged empyrean armour, iLvl 119.',0,256,16),
 (23697,'Fili Cothurnes +3',1,0,'feet',99,'Reforged empyrean armour, iLvl 119.',0,256,512),
 (23706,'Maculele Toe Shoes +3',1,0,'feet',99,'Reforged empyrean armour, iLvl 119.',0,256,262144),
 (23708,'Azimuth Gaiters +3',1,0,'feet',99,'Reforged empyrean armour, iLvl 119.',0,256,1048576),
 (23923,'Plunderer''s Bonnet +4',1,0,'head',99,'Reforged relic armour, iLvl 119.',0,16,32),
 (23927,'Bihu Roundlet +4',1,0,'head',99,'Reforged relic armour, iLvl 119.',0,16,512),
 (23928,'Arcadian Beret +4',1,0,'head',99,'Reforged relic armour, iLvl 119.',0,16,1024),
 (23929,'Sakonji Kabuto +4',1,0,'head',99,'Reforged relic armour, iLvl 119.',0,16,2048),
 (23933,'Luhlaza Keffiyeh +4',1,0,'head',99,'Reforged relic armour, iLvl 119.',0,16,32768),
 (23934,'Lanun Tricorne +4',1,0,'head',99,'Reforged relic armour, iLvl 119.',0,16,65536),
 (23936,'Horos Tiara +4',1,0,'head',99,'Reforged relic armour, iLvl 119.',0,16,262144),
 (23938,'Bagua Galero +4',1,0,'head',99,'Reforged relic armour, iLvl 119.',0,16,1048576),
 (23964,'Hesychast''s Cyclas +4',1,0,'body',99,'Reforged relic armour, iLvl 119.',0,32,2),
 (24100,'Piety Duckbills +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,4),
 (24101,'Archmage''s Sabots +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,8),
 (24103,'Plunderer''s Poulaines +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,32),
 (24105,'Fallen''s Sollerets +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,128),
 (24107,'Bihu Slippers +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,512),
 (24108,'Arcadian Socks +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,1024),
 (24109,'Sakonji Sune-ate +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,2048),
 (24113,'Luhlaza Charuqs +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,32768),
 (24114,'Lanun Bottes +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,65536),
 (24119,'Futhark Boots +4',1,0,'feet',99,'Reforged relic armour, iLvl 119.',0,256,2097152);

-- The 64 unowned reforged pieces: the 55 new rows plus 9 that existed.
CREATE TEMP TABLE IF NOT EXISTS gearswap_full90 (item_id INTEGER PRIMARY KEY);
DELETE FROM gearswap_full90;
INSERT INTO gearswap_full90 (item_id) VALUES
 (23420),
 (23422),
 (23423),
 (23424),
 (23426),
 (23427),
 (23429),
 (23431),
 (23432),
 (23438),
 (23439),
 (23440),
 (23441),
 (23554),
 (23555),
 (23558),
 (23560),
 (23563),
 (23564),
 (23569),
 (23572),
 (23621),
 (23623),
 (23624),
 (23625),
 (23626),
 (23627),
 (23628),
 (23630),
 (23631),
 (23632),
 (23633),
 (23636),
 (23637),
 (23639),
 (23641),
 (23642),
 (23689),
 (23692),
 (23697),
 (23700),
 (23706),
 (23707),
 (23708),
 (23923),
 (23927),
 (23928),
 (23929),
 (23933),
 (23934),
 (23936),
 (23938),
 (23964),
 (24100),
 (24101),
 (24103),
 (24105),
 (24107),
 (24108),
 (24109),
 (24110),
 (24113),
 (24114),
 (24119);

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
    SELECT g.item_id, ROW_NUMBER() OVER (ORDER BY g.item_id) AS rn
    FROM gearswap_full90 g
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = 1 AND ci.item_id = g.item_id
    )
  )
INSERT OR IGNORE INTO char_inventory (character_id,container,slot,item_id,quantity)
SELECT t.character_id, free.container, free.slot, want.item_id, 1
FROM want JOIN free ON free.rn = want.rn CROSS JOIN target t;

DROP TABLE gearswap_full90;
