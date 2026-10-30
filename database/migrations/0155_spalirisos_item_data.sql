-- Spalirisos and the iLvl 119 off-hand axes were inserted by the hand-curated
-- Beastmaster grant without their item skill or stat blocks, so a 99 BST holding
-- Spalirisos had Axe skill 424 instead of 701 and no STR/DEX/accuracy from the weapon.
-- Blitz (its own skill) was taking the whole penalty: the opening hit's fTP 12.5 is
-- where most of the damage is, and its base was built from the lower Attack/accuracy.
--
-- BG-wiki, Spalirisos (Level 119 III): DMG:218 Delay:280 STR+35 DEX+35 CHR+35
-- Accuracy+35 Magic Accuracy+35 Axe skill +277 ... Critical hit rate +15%.
-- The item's "Axe skill +277" is the item_weapon.ilvl_skill column the stat sheet
-- adds to the job's skill cap.
UPDATE item_weapon SET ilvl_skill = 277 WHERE item_id = 21730;

-- BG-wiki, Ikenga's Axe: DMG:192 Delay:288 STR+15 DEX+15 Accuracy+40 Attack+30
-- Magic Accuracy+40 Axe skill +255 ... Critical hit rate +10% Weapon skill damage +5%.
UPDATE item_weapon SET ilvl_skill = 255 WHERE item_id = 21723;
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21723, 8, 15),      -- STR
 (21723, 9, 15),      -- DEX
 (21723, 23, 30),     -- Attack
 (21723, 25, 40),     -- Accuracy
 (21723, 30, 40),     -- Magic Accuracy
 (21723, 165, 1000),  -- Critical hit rate +10% (hundredths of a percent)
 (21723, 840, 5);     -- Weapon skill damage +5%

-- BG-wiki, Agwu's Axe: DMG:192 Delay:288 DEX+15 CHR+15 Accuracy+40 Attack+30
-- Magic Accuracy+40 Axe skill +255 ... "Store TP"+10 Weapon skill damage +5%.
UPDATE item_weapon SET ilvl_skill = 255 WHERE item_id = 21724;
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21724, 9, 15),      -- DEX
 (21724, 14, 15),     -- CHR
 (21724, 23, 30),     -- Attack
 (21724, 25, 40),     -- Accuracy
 (21724, 30, 40),     -- Magic Accuracy
 (21724, 73, 10),     -- Store TP
 (21724, 840, 5);     -- Weapon skill damage +5%

INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (21730, 8, 35),      -- STR
 (21730, 9, 35),      -- DEX
 (21730, 14, 35),     -- CHR
 (21730, 25, 35),     -- Accuracy
 (21730, 30, 35),     -- Magic Accuracy
 (21730, 165, 1500);  -- Critical hit rate +15% (hundredths of a percent)
