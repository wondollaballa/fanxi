-- Reforged Mog Bonanza weapons: the client tooltip stats the server never had.
--
-- Migration 53 added the twenty stronger iLvl 119 Bonanza weapons, but only Final Sickle
-- had item_mods rows (migration 92) and only it and Yagyu Darkblade had weapon skill rows
-- (migrations 63 and 92).  The other nineteen had no item_mods and most had no weapon
-- skill bonus, so the live stat sheet and combat treated them as bare damage weapons.
-- The client's own DAT already has the real tooltips; this migration copies those
-- numbers into the server tables.
--
-- The client stores both the base weapon and its Reforged upgrade under one display name.
-- Two reforged ids use the other copy's spelling entirely: 21541 is "Premium Hearts" and
-- 21732 is "Demonic Axe".  The EquipViewer maps those names back to these ids in
-- host/addons/lua/control.lua; the stat rows below are the same item copies.
--
-- "Magic Accuracy skill +269" is a magic-accuracy-only weapon skill the combat formulas do
-- not model, and pet/avatar/weapon-skill-proc lines are conditional, so neither is copied.
-- Every weapon's <weapon> skill +269 goes to item_skill_bonus, matching migration 92's
-- Final Sickle rows; Parrying (and Guard on the two H2H weapons) are client skill ids 31/28.
-- "Cure" potency, "Cure" potency II, Fast Cast, Refresh and the damage-limit line are
-- regular modifiers and are included where the tooltip prints them.

INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (20663, 12, 40),  -- INT
 (20663, 25, 50),  -- Accuracy
 (20663, 28, 45),  -- "Magic Atk. Bonus"
 (20663, 30, 50),  -- Magic Accuracy
 (20663, 311, 257),  -- Magic Damage
 (20664, 8, 40),  -- STR
 (20664, 25, 50),  -- Accuracy
 (20664, 30, 50),  -- Magic Accuracy
 (20664, 1081, 5),  -- Physical damage limit
 (21540, 9, 40),  -- DEX
 (21540, 25, 50),  -- Accuracy
 (21541, 8, 40),  -- STR
 (21541, 25, 50),  -- Accuracy
 (21592, 11, 40),  -- AGI
 (21592, 25, 50),  -- Accuracy
 (21592, 30, 50),  -- Magic Accuracy
 (21592, 31, 50),  -- Magic Evasion
 (21592, 68, 50),  -- Evasion
 (21592, 384, 1000),  -- Haste
 (21593, 11, 40),  -- AGI
 (21593, 25, 50),  -- Accuracy
 (21593, 68, 50),  -- Evasion
 (21593, 384, 1000),  -- Haste
 (21602, 9, 40),  -- DEX
 (21602, 25, 50),  -- Accuracy
 (21603, 13, 40),  -- MND
 (21603, 25, 50),  -- Accuracy
 (21603, 27, 10),  -- Enmity
 (21603, 30, 50),  -- Magic Accuracy
 (21603, 260, 20),  -- "Cure" potency II
 (21677, 8, 40),  -- STR
 (21677, 25, 50),  -- Accuracy
 (21677, 29, 11),  -- "Magic Def. Bonus"
 (21677, 30, 50),  -- Magic Accuracy
 (21732, 8, 40),  -- STR
 (21732, 25, 50),  -- Accuracy
 (21789, 10, 40),  -- VIT
 (21789, 25, 50),  -- Accuracy
 (21842, 2, 250),  -- HP
 (21842, 25, 50),  -- Accuracy
 (21842, 30, 50),  -- Magic Accuracy
 (21893, 13, 40),  -- MND
 (21893, 25, 50),  -- Accuracy
 (21893, 30, 50),  -- Magic Accuracy
 (21936, 9, 40),  -- DEX
 (21936, 25, 50),  -- Accuracy
 (21936, 26, 50),  -- Ranged Accuracy
 (21936, 30, 50),  -- Magic Accuracy
 (21952, 8, 40),  -- STR
 (21952, 25, 50),  -- Accuracy
 (21953, 8, 40),  -- STR
 (21953, 25, 50),  -- Accuracy
 (21953, 26, 50),  -- Ranged Accuracy
 (21953, 30, 50),  -- Magic Accuracy
 (21991, 12, 40),  -- INT
 (21991, 28, 45),  -- "Magic Atk. Bonus"
 (21991, 30, 50),  -- Magic Accuracy
 (21991, 311, 272),  -- Magic Damage
 (22168, 13, 40),  -- MND
 (22168, 27, -20),  -- Enmity
 (22168, 28, 45),  -- "Magic Atk. Bonus"
 (22168, 30, 50),  -- Magic Accuracy
 (22168, 170, 20),  -- "Fast Cast"
 (22168, 311, 319),  -- Magic Damage
 (22168, 369, 2),  -- "Refresh"
 (22168, 374, 50),  -- "Cure" potency
 (22169, 11, 40),  -- AGI
 (22169, 24, 50),  -- Ranged Attack
 (22169, 26, 50),  -- Ranged Accuracy
 (22169, 73, 20),  -- "Store TP"
 (22170, 11, 40),  -- AGI
 (22170, 26, 50),  -- Ranged Accuracy
 (22170, 30, 50),  -- Magic Accuracy
 (22170, 73, 10); -- "Store TP"

INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (20663, 3, 269),
 (20663, 31, 269),
 (20664, 3, 269),
 (20664, 31, 269),
 (21540, 1, 269),
 (21540, 28, 269),
 (21541, 1, 269),
 (21541, 28, 269),
 (21592, 2, 269),
 (21592, 31, 269),
 (21593, 2, 269),
 (21593, 31, 269),
 (21602, 3, 269),
 (21602, 31, 269),
 (21603, 3, 269),
 (21603, 31, 269),
 (21677, 4, 269),
 (21677, 31, 269),
 (21732, 5, 269),
 (21732, 31, 269),
 (21789, 6, 269),
 (21789, 31, 269),
 (21842, 7, 269),
 (21842, 31, 269),
 (21893, 8, 269),
 (21893, 31, 269),
 (21936, 9, 269),
 (21936, 31, 269),
 (21952, 10, 269),
 (21952, 31, 269),
 (21953, 10, 269),
 (21953, 31, 269),
 (21991, 11, 269),
 (21991, 31, 269),
 (22168, 12, 269),
 (22168, 31, 269),
 (22169, 25, 269),
 (22170, 26, 269);
