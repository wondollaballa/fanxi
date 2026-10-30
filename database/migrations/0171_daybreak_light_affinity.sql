-- Daybreak's "Light elemental damage +50" is elemental affinity, not a second Magic
-- Attack Bonus line.
--
-- The item import kept MP, MND, Magic Accuracy, MAB, Magic Damage, Magic Evasion,
-- "Cure" potency and Refresh, but the client text "Light elemental damage +50" had no
-- row in item_mods.  Retail applies it as the light-affinity multiplier (LSB's
-- light_mab, modifier 38), which is a separate term from MAB in the magic damage
-- pipeline.  Without it Seraph Blade -- a light-elemental magical weapon skill -- loses
-- half of Daybreak's contribution even when the rest of the formula is right.
--
-- BG-wiki, Daybreak: "Light elemental damage +50".  See Magic Damage#Affinity: the
-- caster's elemental affinity is a multiplier in the magical WS damage chain.

INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (22040, 38, 50);       -- Light affinity +50% (mod.LIGHT_MAB)
