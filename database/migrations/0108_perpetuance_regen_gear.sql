-- Perpetuance, Regen and enhancing-duration gear (migration 108).
--
-- The client tooltip already prints these lines; LandSandBoat's item tables and the
-- reforged import skipped them, so the server never saw the gear.  The ids are LSB's
-- where one exists:
--
--   339  REGEN_DURATION     flat seconds added to a Regen spell
--   838  REGEN_MULTIPLIER   "Regen" potency +x%, applied to the base tick
--   890  ENH_MAGIC_DURATION "Enhancing magic duration"+x%
--   1221 (LSB spare)        "Perpetuance"+x%, hundredths over the 2.0x base
--
-- Flat seconds belong inside the first sum of the duration formula; the percentage
-- terms multiply afterwards, and Perpetuance is last.

INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (23439, 838, 25),      -- Arbatel Bonnet +3: "Regen" potency +25%
 (23441, 890, 25),      -- Erilaz Galea +3: Enhancing magic duration +25%
 (23556, 339, 26),      -- Ebers Mitts +3: "Regen" duration +26
 (23573, 1221, 6500),   -- Arbatel Bracers +3: "Perpetuance"+65% -> 2.65x
 (23692, 890, 40),      -- Lethargy Houseaux +3: Enhancing magic duration +40%
 (23917, 339, 27),      -- Runeist Bandeau +4: "Regen" duration +27
 (23965, 838, 52),      -- Piety Bliaut +4: "Regen" potency +52%
 (23967, 890, 15),      -- Vitiation Tabard +4: Enhancing magic duration +15%
 (23982, 890, 12),      -- Pedagogy Gown +4: Enhancing magic duration +12%
 (23989, 890, 20),      -- Atrophy Gloves +4: Enhancing magic duration +20%
 (24032, 339, 24),      -- Theophany Pantaloons +4: "Regen" duration +24
 (24074, 890, 30),      -- Futhark Trousers +4: Enhancing magic duration +30%
 (24077, 890, 10),      -- Theophany Duckbills +4: Enhancing magic duration +10%
 (26265, 339, 15);      -- Lugh's Cape: "Regen" effect duration +15
