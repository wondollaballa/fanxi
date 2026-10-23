-- Ninja job-specific equipment, the same grant the Scholar got: the three reforged
-- sets, the four ultimate katanas, and the job's neck and earring.
--
-- Set models are item_equipment.MId (one number renders the whole set, like the
-- Warrior and Scholar sets): Hachiya 88, Mochizuki 89, Hattori 294.  The reforged
-- families carry no MId at +4, so the set's base MId is used, as before.
-- Kikoku 551, Nagi 565, Kannagi 578 are the 119 III MIds.  Dokoku's MId in
-- item_equipment is a clone of Kikoku's (548/551 style relic clone), so the prime
-- katana still wears the relic katana model until its real id is probed.

INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES
-- Artifact reforged (Hachiya) +4
 (23907,'Hachiya Hatsuburi +4',1,0,'head',99,'Ninja reforged artifact headgear, iLvl 119.',88,16,4096),
 (23952,'Hachiya Chainmail +4',1,0,'body',99,'Ninja reforged artifact body, iLvl 119.',88,32,4096),
 (23997,'Hachiya Tekko +4',1,0,'hands',99,'Ninja reforged artifact hands, iLvl 119.',88,64,4096),
 (24042,'Hachiya Hakama +4',1,0,'legs',99,'Ninja reforged artifact legs, iLvl 119.',88,128,4096),
 (24087,'Hachiya Kyahan +4',1,0,'feet',99,'Ninja reforged artifact feet, iLvl 119.',88,256,4096),
-- Relic reforged (Mochizuki) +4
 (23930,'Mochizuki Hatsuburi +4',1,0,'head',99,'Ninja reforged relic headgear, iLvl 119.',89,16,4096),
 (23975,'Mochizuki Chainmail +4',1,0,'body',99,'Ninja reforged relic body, iLvl 119.',89,32,4096),
 (24020,'Mochizuki Tekko +4',1,0,'hands',99,'Ninja reforged relic hands, iLvl 119.',89,64,4096),
 (24065,'Mochizuki Hakama +4',1,0,'legs',99,'Ninja reforged relic legs, iLvl 119.',89,128,4096),
 (24110,'Mochizuki Kyahan +4',1,0,'feet',99,'Ninja reforged relic feet, iLvl 119.',89,256,4096),
-- Empyrean reforged (Hattori) +3 -- the empyrean line has no +4 tier, as with Arbatel
 (23432,'Hattori Zukin +3',1,0,'head',99,'Ninja reforged empyrean headgear, iLvl 119.',294,16,4096),
 (23499,'Hattori Ningi +3',1,0,'body',99,'Ninja reforged empyrean body, iLvl 119.',294,32,4096),
 (23566,'Hattori Tekko +3',1,0,'hands',99,'Ninja reforged empyrean hands, iLvl 119.',294,64,4096),
 (23633,'Hattori Hakama +3',1,0,'legs',99,'Ninja reforged empyrean legs, iLvl 119.',294,128,4096),
 (23700,'Hattori Kyahan +3',1,0,'feet',99,'Ninja reforged empyrean feet, iLvl 119.',294,256,4096),
-- JSE neck and ear
 (25491,'Ninja Nodowa +2',1,0,'neck',99,'Ninja job-specific neck, iLvl 119.',0,512,4096),
 (25494,'Hattori Earring +2',1,0,'ear1',99,'Ninja job-specific earring, iLvl 119.',0,6144,4096),
-- Relic, mythic, empyrean and prime katana
 (21906,'Kikoku 119 III',1,0,'main',99,'Ninja relic katana, iLvl 119.',551,1,4096),
 (21907,'Nagi 119 III',1,0,'main',99,'Ninja mythic katana, iLvl 119.',565,1,4096),
 (21908,'Kannagi 119 III',1,0,'main',99,'Ninja empyrean katana, iLvl 119.',578,1,4096),
 (21932,'Dokoku 119 III',1,0,'main',99,'Ninja prime katana, iLvl 119.',551,1,4096);

INSERT OR REPLACE INTO char_inventory (character_id,container,slot,item_id,quantity)
SELECT * FROM (VALUES
 (1,0,20,21906,1),
 (1,0,21,21907,1),
 (1,0,22,21908,1),
 (1,0,23,21932,1),
 (1,0,24,23907,1),
 (1,0,25,23952,1),
 (1,0,26,23997,1),
 (1,0,27,24042,1),
 (1,0,28,24087,1),
 (1,0,29,23930,1),
 (1,0,30,23975,1),
 (1,0,32,24020,1),
 (1,0,33,24065,1),
 (1,0,34,24110,1),
 (1,0,35,23432,1),
 (1,0,36,23499,1),
 (1,0,37,23566,1),
 (1,0,38,23633,1),
 (1,0,42,23700,1),
 (1,0,43,25491,1),
 (1,0,44,25494,1)
) WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);
