-- Reforged Mog Bonanza weapons (bg-wiki Category:Bonanza Weapons, the "(Reforged)" pages).
--
-- Each Bonanza weapon has two iLvl 119 items sharing one display name: the original
-- 119 version with a model, and the Reforged upgrade, which the database carries with
-- MId 0.  Reforged is the stronger of the pair (Air Knife 114 vs 103, Flametongue 201
-- vs 187, Zanmato +2 354 vs 320, and so on), so those ids are the ones granted here.
-- Because item_equipment has no model for them, each wears its base weapon's MId, the
-- same substitution used for the reforged armour +4 tiers.  Exeter has no model in any
-- version, so it stays at 0.

INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES
 (20663,'Ice Brand (Reforged)',1,0,'main',99,'Reforged Bonanza sword, iLvl 119.',782,3,32848),
 (20664,'Flametongue (Reforged)',1,0,'main',99,'Reforged Bonanza sword, iLvl 119.',783,3,32849),
 (21540,'Dragon Fangs (Reforged)',1,0,'main',99,'Reforged Bonanza hand-to-hand, iLvl 119.',482,1,131074),
 (21541,'Premium Heart (Reforged)',1,0,'main',99,'Reforged Bonanza hand-to-hand, iLvl 119.',481,1,131074),
 (21592,'Chocobo Knife (Reforged)',1,0,'main',99,'Reforged Bonanza dagger, iLvl 119.',784,3,263728),
 (21593,'Air Knife (Reforged)',1,0,'main',99,'Reforged Bonanza dagger, iLvl 119.',785,3,262176),
 (21602,'Onion Sword III (Reforged)',1,0,'main',99,'Reforged Bonanza sword, iLvl 119.',787,3,4194303),
 (21603,'Save the Queen III (Reforged)',1,0,'main',99,'Reforged Bonanza sword, iLvl 119.',790,3,64),
 (21677,'Brave Blade III (Reforged)',1,0,'main',99,'Reforged Bonanza great sword, iLvl 119.',792,1,2097344),
 (21732,'Malefic Axe (Reforged)',1,0,'main',99,'Reforged Bonanza axe, iLvl 119.',793,3,256),
 (21789,'Drastic Axe (Reforged)',1,0,'main',99,'Reforged Bonanza great axe, iLvl 119.',794,1,1),
 (21842,'Final Sickle (Reforged)',1,0,'main',99,'Reforged Bonanza scythe, iLvl 119.',795,1,128),
 (21893,'Hebo''s Spear (Reforged)',1,0,'main',99,'Reforged Bonanza polearm, iLvl 119.',786,1,8192),
 (21936,'Yagyu Darkblade (Reforged)',1,0,'main',99,'Reforged Bonanza katana, iLvl 119.',789,3,4096),
 (21952,'Zanmato +2 (Reforged)',1,0,'main',99,'Reforged Bonanza great katana, iLvl 119.',788,1,2048),
 (21953,'Mutsu. Yoshi. (Reforged)',1,0,'main',99,'Reforged Bonanza great katana, iLvl 119.',791,1,2048),
 (21991,'Wizard''s Rod (Reforged)',1,0,'main',99,'Reforged Bonanza club, iLvl 119.',845,3,1572888),
 (22168,'Pandit''s Staff (Reforged)',1,0,'main',99,'Reforged Bonanza staff, iLvl 119.',797,1,16388),
 (22169,'Artemis''s Bow +2 (Reforged)',1,0,'ranged',99,'Reforged Bonanza bow, iLvl 119.',138,4,1024),
 (22170,'Exeter (Reforged)',1,0,'ranged',99,'Reforged Bonanza gun, iLvl 119.',0,4,66560);

INSERT OR REPLACE INTO char_inventory (character_id,container,slot,item_id,quantity)
SELECT * FROM (VALUES
 (1,0,45,20663,1),
 (1,0,46,20664,1),
 (1,0,47,21540,1),
 (1,0,48,21541,1),
 (1,0,49,21592,1),
 (1,0,50,21593,1),
 (1,0,51,21602,1),
 (1,0,52,21603,1),
 (1,0,53,21677,1),
 (1,0,54,21732,1),
 (1,0,55,21789,1),
 (1,0,56,21842,1),
 (1,0,57,21893,1),
 (1,0,58,21936,1),
 (1,0,59,21952,1),
 (1,0,60,21953,1),
 (1,0,61,21991,1),
 (1,0,62,22168,1),
 (1,0,63,22169,1),
 (1,0,64,22170,1)
) WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);
