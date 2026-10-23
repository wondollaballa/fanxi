-- Beastmaster job-specific equipment, the same grant the Ninja got: the three reforged
-- sets at their top tiers, the five ultimate axes, and the job's neck/ear/cape plus the
-- classic Beastmaster accessories.
--
-- Set models are item_equipment.MId (one number renders the whole set, like the Warrior,
-- Scholar and Ninja sets): Totemic 80, Ankusa 81, Nukumi 290.  The reforged families carry
-- no MId at +4, so the set's base MId is used, as before.  Nukumi is empyrean and tops out
-- at +3 (there is no +4 tier, the same as Hattori).
--
-- Weapons: Guttler 547, Aymur 562, Farsha 574, Tri-edge 763.  Spalirisos is a Prime weapon
-- whose item data clones Guttler's 547 model; the client probe puts the Prime axe at 910,
-- the same way 0054 corrected the Prime katana.
--
-- Item names are the server-side full names.  The client displays its own shortened names
-- (e.g. "Tot. Jackcoat +4", "Bst. Collar +2"); res.item_by_name accepts both.
--
-- Slots: weapons and the reforged sets go in the main bag (free slots 3-9 and 65-80 in a
-- fresh database, clear of the Warrior/Ninja/Bonanza grants).  The classic accessories go
-- into wardrobe 11, clear of the Ninja set.

INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES
-- Relic, mythic, empyrean, Aeonic and Prime axes
 (21750,'Guttler',1,0,'main',99,'Beastmaster relic axe, iLvl 119 III.',547,1,256),
 (21751,'Aymur',1,0,'main',99,'Beastmaster mythic axe, iLvl 119 III.',562,1,256),
 (21752,'Farsha',1,0,'main',99,'Beastmaster empyrean axe, iLvl 119 III.',574,1,257),
 (21753,'Tri-edge',1,0,'main',99,'Beastmaster Aeonic axe, iLvl 119.',763,1,256),
 (21730,'Spalirisos',1,0,'main',99,'Beastmaster Prime axe, iLvl 119 III.',910,1,256),
-- Artifact reforged (Totemic) +4
 (23903,'Totemic Helm +4',1,0,'head',99,'Beastmaster reforged artifact headgear, iLvl 119.',80,16,256),
 (23948,'Totemic Jackcoat +4',1,0,'body',99,'Beastmaster reforged artifact body, iLvl 119.',80,32,256),
 (23993,'Totemic Gloves +4',1,0,'hands',99,'Beastmaster reforged artifact hands, iLvl 119.',80,64,256),
 (24038,'Totemic Trousers +4',1,0,'legs',99,'Beastmaster reforged artifact legs, iLvl 119.',80,128,256),
 (24083,'Totemic Gaiters +4',1,0,'feet',99,'Beastmaster reforged artifact feet, iLvl 119.',80,256,256),
-- Relic reforged (Ankusa) +4
 (23926,'Ankusa Helm +4',1,0,'head',99,'Beastmaster reforged relic headgear, iLvl 119.',81,16,256),
 (23971,'Ankusa Jackcoat +4',1,0,'body',99,'Beastmaster reforged relic body, iLvl 119.',81,32,256),
 (24016,'Ankusa Gloves +4',1,0,'hands',99,'Beastmaster reforged relic hands, iLvl 119.',81,64,256),
 (24061,'Ankusa Trousers +4',1,0,'legs',99,'Beastmaster reforged relic legs, iLvl 119.',81,128,256),
 (24106,'Ankusa Gaiters +4',1,0,'feet',99,'Beastmaster reforged relic feet, iLvl 119.',81,256,256),
-- Empyrean reforged (Nukumi) +3 -- the empyrean line has no +4 tier, as with Hattori
 (23428,'Nukumi Cabasset +3',1,0,'head',99,'Beastmaster reforged empyrean headgear, iLvl 119.',290,16,256),
 (23495,'Nukumi Gausape +3',1,0,'body',99,'Beastmaster reforged empyrean body, iLvl 119.',290,32,256),
 (23562,'Nukumi Manoplas +3',1,0,'hands',99,'Beastmaster reforged empyrean hands, iLvl 119.',290,64,256),
 (23629,'Nukumi Quijotes +3',1,0,'legs',99,'Beastmaster reforged empyrean legs, iLvl 119.',290,128,256),
 (23696,'Nukumi Ocreae +3',1,0,'feet',99,'Beastmaster reforged empyrean feet, iLvl 119.',290,256,256),
-- JSE neck, ear and cape
 (25467,'Beastmaster Collar +2',1,0,'neck',99,'Beastmaster job-specific neck, iLvl 119.',0,512,256),
 (25470,'Nukumi Earring +2',1,0,'ear1',99,'Beastmaster job-specific earring, iLvl 119.',0,6144,256),
 (26254,'Artio''s Mantle',1,0,'back',99,'Beastmaster job-specific cape, iLvl 119.',0,32768,256),
-- Classic Beastmaster-only accessories
 (13294,'Tamer''s Ring',1,0,'ring1',50,'Beastmaster job-specific ring.',0,24576,256),
 (14658,'Atlaua''s Ring',1,0,'ring1',67,'Beastmaster job-specific ring.',0,24576,256),
 (14680,'Pacifist Ring',1,0,'ring1',61,'Beastmaster job-specific ring.',0,24576,256),
 (11617,'Ferine Necklace',1,0,'neck',84,'Beastmaster job-specific neck.',0,512,256),
 (11711,'Ferine Earring',1,0,'ear1',90,'Beastmaster job-specific earring.',0,6144,256),
 (11555,'Ferine Mantle',1,0,'back',80,'Beastmaster job-specific cape.',0,32768,256),
 (11996,'Beast Torque',1,0,'neck',30,'Beastmaster job-specific neck.',0,512,256),
 (13110,'Beast Whistle',1,0,'neck',24,'Beastmaster job-specific neck.',0,512,256),
 (10299,'Sabong Earring',1,0,'ear1',99,'Beastmaster job-specific earring.',0,6144,256),
 (13427,'Tamer''s Earring',1,0,'ear1',70,'Beastmaster job-specific earring.',0,6144,256),
 (27527,'Hija Earring',1,0,'ear1',99,'Beastmaster job-specific earring.',0,6144,256),
 (28625,'Pastoralist''s Mantle',1,0,'back',99,'Beastmaster job-specific cape.',0,32768,256);

INSERT OR REPLACE INTO char_inventory (character_id,container,slot,item_id,quantity)
SELECT * FROM (VALUES
 (1,0,3,21750,1),
 (1,0,4,21751,1),
 (1,0,5,21752,1),
 (1,0,6,21753,1),
 (1,0,7,21730,1),
 (1,0,8,23903,1),
 (1,0,9,23948,1),
 (1,0,65,23993,1),
 (1,0,66,24038,1),
 (1,0,67,24083,1),
 (1,0,68,23926,1),
 (1,0,69,23971,1),
 (1,0,70,24016,1),
 (1,0,71,24061,1),
 (1,0,72,24106,1),
 (1,0,73,23428,1),
 (1,0,74,23495,1),
 (1,0,75,23562,1),
 (1,0,76,23629,1),
 (1,0,77,23696,1),
 (1,0,78,25467,1),
 (1,0,79,25470,1),
 (1,0,80,26254,1),
 (1,11,23,13294,1),
 (1,11,24,14658,1),
 (1,11,25,14680,1),
 (1,11,26,11617,1),
 (1,11,27,11711,1),
 (1,11,28,11555,1),
 (1,11,29,11996,1),
 (1,11,30,13110,1),
 (1,11,31,10299,1),
 (1,11,32,13427,1),
 (1,11,33,27527,1),
 (1,11,34,28625,1)
) WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);
