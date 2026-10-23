-- Weapon skill type for the weapon items Fanxi knows, so the server can advertise only
-- the weapon skills the equipped weapon can actually use.  `skill` is the client's
-- xi.skill value: 1 h2h, 2 dagger, 3 sword, 4 great sword, 5 axe, 6 great axe, 7 scythe,
-- 8 polearm, 9 katana, 10 great katana, 11 club, 12 staff, 25 archery, 26 marksmanship,
-- 27 throwing.  Ids and skill types are functional game data cross-checked against
-- LandSandBoat's item_weapon.sql; shields and instruments stay at 0 (no weapon skill).
ALTER TABLE items ADD COLUMN skill INTEGER NOT NULL DEFAULT 0;
UPDATE items SET skill = 3 WHERE item_id = 16534;  -- Onion Sword
UPDATE items SET skill = 3 WHERE item_id = 16535;  -- Bronze Sword
UPDATE items SET skill = 6 WHERE item_id = 16735;  -- Axe of Trials
UPDATE items SET skill = 0 WHERE item_id = 19025;  -- Pole Grip
UPDATE items SET skill = 1 WHERE item_id = 20511;  -- Kenkonken
UPDATE items SET skill = 1 WHERE item_id = 20515;  -- Godhands
UPDATE items SET skill = 2 WHERE item_id = 20583;  -- Mandau
UPDATE items SET skill = 2 WHERE item_id = 20584;  -- Terpsichore
UPDATE items SET skill = 2 WHERE item_id = 20585;  -- Vajra
UPDATE items SET skill = 2 WHERE item_id = 20586;  -- Carnwenhan
UPDATE items SET skill = 3 WHERE item_id = 20663;  -- Ice Brand (Reforged)
UPDATE items SET skill = 3 WHERE item_id = 20664;  -- Flametongue (Reforged)
UPDATE items SET skill = 3 WHERE item_id = 20685;  -- Excalibur
UPDATE items SET skill = 3 WHERE item_id = 20686;  -- Murgleis
UPDATE items SET skill = 3 WHERE item_id = 20687;  -- Burtgang
UPDATE items SET skill = 3 WHERE item_id = 20688;  -- Tizona
UPDATE items SET skill = 6 WHERE item_id = 20843;  -- Chango
UPDATE items SET skill = 11 WHERE item_id = 21080;  -- Idris
UPDATE items SET skill = 1 WHERE item_id = 21527;  -- Sakpata's Fists
UPDATE items SET skill = 1 WHERE item_id = 21540;  -- Dragon Fangs (Reforged)
UPDATE items SET skill = 1 WHERE item_id = 21541;  -- Premium Heart (Reforged)
UPDATE items SET skill = 2 WHERE item_id = 21565;  -- Tauret
UPDATE items SET skill = 2 WHERE item_id = 21567;  -- Gleti's Knife
UPDATE items SET skill = 2 WHERE item_id = 21592;  -- Chocobo Knife (Reforged)
UPDATE items SET skill = 2 WHERE item_id = 21593;  -- Air Knife (Reforged)
UPDATE items SET skill = 3 WHERE item_id = 21602;  -- Onion Sword III (Reforged)
UPDATE items SET skill = 3 WHERE item_id = 21603;  -- Save the Queen III (Reforged)
UPDATE items SET skill = 3 WHERE item_id = 21621;  -- Naegling
UPDATE items SET skill = 3 WHERE item_id = 21637;  -- Sakpata's Sword
UPDATE items SET skill = 4 WHERE item_id = 21675;  -- Agwu's Claymore
UPDATE items SET skill = 4 WHERE item_id = 21677;  -- Brave Blade III (Reforged)
UPDATE items SET skill = 4 WHERE item_id = 21683;  -- Ragnarok
UPDATE items SET skill = 4 WHERE item_id = 21685;  -- Epeolatry
UPDATE items SET skill = 5 WHERE item_id = 21724;  -- Agwu's Axe
UPDATE items SET skill = 5 WHERE item_id = 21730;  -- Spalirisos
UPDATE items SET skill = 5 WHERE item_id = 21732;  -- Malefic Axe (Reforged)
UPDATE items SET skill = 5 WHERE item_id = 21750;  -- Guttler
UPDATE items SET skill = 5 WHERE item_id = 21751;  -- Aymur
UPDATE items SET skill = 5 WHERE item_id = 21752;  -- Farsha
UPDATE items SET skill = 5 WHERE item_id = 21753;  -- Tri-edge
UPDATE items SET skill = 6 WHERE item_id = 21757;  -- Conqueror
UPDATE items SET skill = 6 WHERE item_id = 21758;  -- Ukonvasara
UPDATE items SET skill = 6 WHERE item_id = 21782;  -- Laphria
UPDATE items SET skill = 6 WHERE item_id = 21785;  -- Laphria
UPDATE items SET skill = 6 WHERE item_id = 21789;  -- Drastic Axe (Reforged)
UPDATE items SET skill = 7 WHERE item_id = 21808;  -- Apocalypse
UPDATE items SET skill = 7 WHERE item_id = 21832;  -- Agwu's Scythe
UPDATE items SET skill = 7 WHERE item_id = 21842;  -- Final Sickle (Reforged)
UPDATE items SET skill = 8 WHERE item_id = 21857;  -- Gungnir
UPDATE items SET skill = 8 WHERE item_id = 21893;  -- Hebo's Spear (Reforged)
UPDATE items SET skill = 9 WHERE item_id = 21906;  -- Kikoku 119 III
UPDATE items SET skill = 9 WHERE item_id = 21907;  -- Nagi 119 III
UPDATE items SET skill = 9 WHERE item_id = 21908;  -- Kannagi 119 III
UPDATE items SET skill = 9 WHERE item_id = 21932;  -- Dokoku 119 III
UPDATE items SET skill = 9 WHERE item_id = 21936;  -- Yagyu Darkblade (Reforged)
UPDATE items SET skill = 10 WHERE item_id = 21952;  -- Zanmato +2 (Reforged)
UPDATE items SET skill = 10 WHERE item_id = 21953;  -- Mutsu. Yoshi. (Reforged)
UPDATE items SET skill = 10 WHERE item_id = 21955;  -- Kogarasumaru
UPDATE items SET skill = 11 WHERE item_id = 21991;  -- Wizard's Rod (Reforged)
UPDATE items SET skill = 11 WHERE item_id = 22040;  -- Daybreak
UPDATE items SET skill = 12 WHERE item_id = 22061;  -- Tupsimati 119 III
UPDATE items SET skill = 12 WHERE item_id = 22063;  -- Nirvana
UPDATE items SET skill = 12 WHERE item_id = 22064;  -- Hvergelmir 119 III
UPDATE items SET skill = 12 WHERE item_id = 22097;  -- Argute Staff
UPDATE items SET skill = 12 WHERE item_id = 22103;  -- Opashoro 119 III
UPDATE items SET skill = 12 WHERE item_id = 22104;  -- Opashoro 119 III
UPDATE items SET skill = 12 WHERE item_id = 22105;  -- Opashoro 119 III
UPDATE items SET skill = 12 WHERE item_id = 22106;  -- Opashoro 119 III
UPDATE items SET skill = 12 WHERE item_id = 22168;  -- Pandit's Staff (Reforged)
UPDATE items SET skill = 25 WHERE item_id = 22169;  -- Artemis's Bow +2 (Reforged)
UPDATE items SET skill = 26 WHERE item_id = 22170;  -- Exeter (Reforged)
UPDATE items SET skill = 0 WHERE item_id = 22212;  -- Utu Grip
