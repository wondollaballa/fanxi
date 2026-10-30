-- Foenaria's stat block, and with it Origin's base damage.
--
-- Migration 87 inserted the Prime weapons with only the "Adds weapon skill" (355)
-- row.  Foenaria therefore had no Scythe skill, no STR/INT and no Triple Attack, so a
-- Dark Knight was swinging Origin at 424 skill instead of 701 and with a WSC built
-- from 35 less STR and INT.  That is a direct damage loss on every hit and every
-- weapon skill; the item is otherwise complete (DMG 400, Delay 513).
--
-- BG-wiki, Foenaria (Level 119 III): DMG:400 Delay:513 STR+35 INT+35 Accuracy+35
-- Magic Accuracy+35 Scythe skill +277 Parrying skill +277 Magic Accuracy skill +277
-- "Triple Attack"+6% Origin Aftermath: Physical damage limit+.
--
-- "Scythe skill +277" is the item_weapon.ilvl_skill column the stat sheet adds to the
-- job's skill cap, the same way migration 155 handles Spalirisos's Axe skill.  Parrying
-- is a normal item_skill_bonus row (client skill id 31).  "Magic Accuracy skill" is a
-- magic-accuracy-only stat that no physical formula reads, so it is not modelled here.
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 21837;

INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21837, 8, 35),      -- STR
 (21837, 12, 35),     -- INT
 (21837, 25, 35),     -- Accuracy
 (21837, 30, 35),     -- Magic Accuracy
 (21837, 302, 6);     -- "Triple Attack"+6%

INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES
 (21837, 31, 277);    -- Parrying skill +277
