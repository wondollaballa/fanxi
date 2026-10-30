-- The rest of the Prime weapons' iLvl 119 III (afterglow) stat blocks.
--
-- Migration 87 put the new Prime weapons in the item table with only the "Adds weapon
-- skill" (355) row, and for Helheim and Lorg Mor it also left the iLvl 119 II damage
-- rating (318 / 227) instead of the 119 III one (336 / 240).  A stage-5 Prime is not a
-- complete item without the lines BG-wiki prints on its 119 III page, so every one of
-- these was fighting with a lower skill, no STR/DEX/INT, no Accuracy and no weapon
-- trait, exactly the gap that made Foenaria's Origin weak before migration 161.
--
-- The descriptions below are the BG-wiki (Level 119 III) item lines.  "Magic Accuracy
-- skill +277" is a magic-accuracy-only stat that no physical formula reads and "All
-- status ailment resistance" has no modifier in this engine, so both are left out
-- rather than guessed at.  Pet/Automaton/Avatar/Wyvern lines are the pet's stats, not
-- the player's, and are omitted.  The weapon's own "X skill +277" is the
-- item_weapon.ilvl_skill column; the secondary Parrying/Guarding/Shield lines are
-- item_skill_bonus rows.
--
-- Testers: server/tests/test_stats.py::PrimeAfterglowItemDataTest.

UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 21590;  -- Mpu Gandring (was 269, 119 II)
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 21646;  -- Caliburnus
UPDATE item_weapon SET ilvl_skill = 277, dmg = 336 WHERE item_id = 21653;  -- Helheim
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 21730;  -- Spalirisos
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 21785;  -- Laphria
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 21891;  -- Gae Buide
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 21986;  -- Kusanagi
UPDATE item_weapon SET ilvl_skill = 277, dmg = 240 WHERE item_id = 22002;  -- Lorg Mor
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 22106;  -- Opashoro
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 22163;  -- Pinaka
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 22164;  -- Earp

-- Varga Purnikawa: DMG:213 Delay:596 STR+35 DEX+35 Accuracy+35 Magic Accuracy+35
-- Hand-to-Hand skill +277 Guarding skill +277 Critical hit rate +15%
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21535, 8, 35),      -- STR
 (21535, 9, 35),      -- DEX
 (21535, 25, 35),     -- Accuracy
 (21535, 30, 35),     -- Magic Accuracy
 (21535, 165, 1500);  -- Critical hit rate +15% (hundredths of a percent)
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (21535, 28, 277);    -- Guarding skill +277

-- Mpu Gandring: DMG:137 Delay:176 DEX+35 AGI+35 CHR+35 Accuracy+35 Magic Accuracy+35
-- Dagger skill +277 Parrying skill +277 "Triple Attack"+6%
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21590, 9, 35),      -- DEX
 (21590, 11, 35),     -- AGI
 (21590, 14, 35),     -- CHR
 (21590, 25, 35),     -- Accuracy
 (21590, 30, 35),     -- Magic Accuracy
 (21590, 302, 6);     -- "Triple Attack"+6%
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (21590, 31, 277);    -- Parrying skill +277

-- Caliburnus: DMG:181 Delay:233 DEX+35 MND+35 Accuracy+35 Attack+70 Magic Accuracy+35
-- Magic Damage+263 Sword skill +277 Parrying skill +277 "Refresh"+4 Damage taken -10%
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21646, 9, 35),      -- DEX
 (21646, 13, 35),     -- MND
 (21646, 23, 70),     -- Attack
 (21646, 25, 35),     -- Accuracy
 (21646, 30, 35),     -- Magic Accuracy
 (21646, 311, 263),   -- Magic Damage
 (21646, 369, 4),     -- "Refresh"+4
 (21646, 160, -1000); -- Damage taken -10%
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (21646, 31, 277);    -- Parrying skill +277

-- Helheim: DMG:336 Delay:431 STR+35 VIT+35 Accuracy+35 Magic Accuracy+35
-- Great Sword skill +277 Parrying skill +277 "Store TP"+10
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21653, 8, 35),      -- STR
 (21653, 10, 35),     -- VIT
 (21653, 25, 35),     -- Accuracy
 (21653, 30, 35),     -- Magic Accuracy
 (21653, 73, 10);     -- "Store TP"+10
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (21653, 31, 277);    -- Parrying skill +277

-- Spalirisos: DMG:218 Delay:280 STR+35 DEX+35 CHR+35 Accuracy+35 Magic Accuracy+35
-- Axe skill +277 Parrying skill +277 Critical hit rate +15%
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21730, 8, 35),      -- STR
 (21730, 9, 35),      -- DEX
 (21730, 14, 35),     -- CHR
 (21730, 25, 35),     -- Accuracy
 (21730, 30, 35),     -- Magic Accuracy
 (21730, 165, 1500);  -- Critical hit rate +15%
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (21730, 31, 277);    -- Parrying skill +277

-- Laphria: DMG:380 Delay:488 STR+35 VIT+35 Accuracy+35 Magic Accuracy+35
-- Great Axe skill +277 Parrying skill +277 "Double Attack"+10%
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21785, 8, 35),      -- STR
 (21785, 10, 35),     -- VIT
 (21785, 25, 35),     -- Accuracy
 (21785, 30, 35),     -- Magic Accuracy
 (21785, 288, 10);    -- "Double Attack"+10%
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (21785, 31, 277);    -- Parrying skill +277

-- Gae Buide: DMG:383 Delay:492 STR+35 VIT+35 Accuracy+35 Magic Accuracy+35
-- Polearm skill +277 Parrying skill +277 "Double Attack"+10%
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21891, 8, 35),      -- STR
 (21891, 10, 35),     -- VIT
 (21891, 25, 35),     -- Accuracy
 (21891, 30, 35),     -- Magic Accuracy
 (21891, 288, 10);    -- "Double Attack"+10%
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (21891, 31, 277);    -- Parrying skill +277

-- Dokoku: DMG:163 Delay:210 DEX+35 AGI+35 Accuracy+35 Magic Accuracy+35
-- Magic Damage+263 Katana skill +277 Parrying skill +277 "Store TP"+10
-- Its Katana +277 and Parrying +277 already live in item_skill_bonus (migration 63),
-- so the weapon keeps ilvl_skill = 0 and this pass only fills the stat/Store TP rows.
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21932, 9, 35),      -- DEX
 (21932, 11, 35),     -- AGI
 (21932, 25, 35),     -- Accuracy
 (21932, 30, 35),     -- Magic Accuracy
 (21932, 73, 10),     -- "Store TP"+10
 (21932, 311, 263);   -- Magic Damage

-- Kusanagi: DMG:340 Delay:437 STR+35 DEX+35 Accuracy+35 Magic Accuracy+35
-- Great Katana skill +277 Parrying skill +277 "Double Attack"+10%
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21986, 8, 35),      -- STR
 (21986, 9, 35),      -- DEX
 (21986, 25, 35),     -- Accuracy
 (21986, 30, 35),     -- Magic Accuracy
 (21986, 288, 10);    -- "Double Attack"+10%
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (21986, 31, 277);    -- Parrying skill +277

-- Lorg Mor: DMG:240 Delay:308 STR+35 MND+35 Accuracy+35 Magic Accuracy+35
-- "Magic Atk. Bonus"+60 Magic Damage+263 Club skill +277 Parrying skill +277
-- "Regen"+7 Damage taken -10%
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (22002, 8, 35),      -- STR
 (22002, 13, 35),     -- MND
 (22002, 25, 35),     -- Accuracy
 (22002, 30, 35),     -- Magic Accuracy
 (22002, 28, 60),     -- "Magic Atk. Bonus"+60
 (22002, 311, 263),   -- Magic Damage
 (22002, 370, 7),     -- "Regen"+7
 (22002, 160, -1000); -- Damage taken -10%
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (22002, 31, 277);    -- Parrying skill +277

-- Opashoro: DMG:304 Delay:390 INT+35 MND+35 Accuracy+35 Magic Accuracy+35
-- "Magic Atk. Bonus"+80 Magic Damage+325 Staff skill +277 Parrying skill +277
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (22106, 12, 35),     -- INT
 (22106, 13, 35),     -- MND
 (22106, 25, 35),     -- Accuracy
 (22106, 30, 35),     -- Magic Accuracy
 (22106, 28, 80),     -- "Magic Atk. Bonus"+80
 (22106, 311, 325);   -- Magic Damage
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (22106, 31, 277);    -- Parrying skill +277

-- Pinaka: DMG:324 Delay:524 STR+35 AGI+35 Accuracy+35 Magic Accuracy+35
-- Archery skill +277 "Store TP"+10
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (22163, 8, 35),      -- STR
 (22163, 11, 35),     -- AGI
 (22163, 25, 35),     -- Accuracy
 (22163, 30, 35),     -- Magic Accuracy
 (22163, 73, 10);     -- "Store TP"+10

-- Earp: DMG:162 Delay:582 DEX+35 AGI+35 Accuracy+35 Magic Accuracy+35
-- Marksmanship skill +277 Critical hit rate +15%
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (22164, 9, 35),      -- DEX
 (22164, 11, 35),     -- AGI
 (22164, 25, 35),     -- Accuracy
 (22164, 30, 35),     -- Magic Accuracy
 (22164, 165, 1500);  -- Critical hit rate +15%

-- Loughnashade: the horn's CHR+20, All songs+4 and two extra song slots were already
-- on the row; only its item level never got set.
UPDATE items SET item_level = 119 WHERE item_id = 22307 AND item_level = 0;

-- Duban: DEF:155 VIT+35 MND+35 Evasion+35 Magic Evasion+35 Shield skill +134
-- Magic damage taken II -25%  ("All status ailment resistance +20" is not modelled.)
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (26495, 1, 155),     -- DEF
 (26495, 10, 35),     -- VIT
 (26495, 13, 35),     -- MND
 (26495, 68, 35),     -- Evasion
 (26495, 31, 35),     -- Magic Evasion
 (26495, 831, -2500); -- Magic damage taken II -25%
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (26495, 30, 134);    -- Shield skill +134
