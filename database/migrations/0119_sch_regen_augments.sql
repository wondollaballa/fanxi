-- Correct the SCH Regen augment types (migration 119).
--
-- Migration 118 stored the guide's Telchine/Bookworm's Regen lines as static
-- percent mods.  The real augments are different:
--
--   * Telchine can carry both "Regen" potency +10 (flat HP/tick) and
--     Enhancing magic duration +10 (percent) on one piece: the stones roll the
--     two lines independently, so the 24-byte block has both slots filled.
--   * Bookworm's Cape carries the same two lines at +10 each.
--   * Musa Path C gives "Regen" potency +25 (flat), not +25%.
--
-- This migration removes the temporary static percent lines, writes the
-- two-line standard-augment block onto every Telchine and Bookworm's copy, and
-- leaves Musa's flat line as item_mods because Sortie weapon paths are not
-- standard augment blocks.
--
-- It runs after 118 on a fresh database and is safe to run again.

DELETE FROM item_mods WHERE (item_id, mod_id) IN (
 (22099, 838),
 (26736, 838), (26736, 1222),
 (26894, 838), (26894, 1222),
 (27048, 838), (27048, 1222),
 (27235, 838), (27235, 1222),
 (27405, 838), (27405, 1222),
 (28636, 838), (28636, 1222)
);

INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (22099, 1223, 25),      -- Musa Path C: flat "Regen" potency +25 HP/tick
 -- Migration 108's reforged lines.  The live database lost most of them when
 -- the reforged item rows were reimported; put them back so the percent piece
 -- (Arbatel Bonnet +3) is not silently inert.
 (23439, 838, 25),       -- Arbatel Bonnet +3: "Regen" potency +25%
 (23441, 890, 25),       -- Erilaz Galea +3: Enhancing magic duration +25%
 (23556, 339, 26),       -- Ebers Mitts +3: "Regen" duration +26
 (23573, 1221, 6500),    -- Arbatel Bracers +3: Perpetuance +65%
 (23692, 890, 40),       -- Lethargy Houseaux +3: Enhancing magic duration +40%
 (23917, 339, 27),       -- Runeist Bandeau +4: "Regen" duration +27
 (23965, 838, 52),       -- Piety Bliaut +4: "Regen" potency +52%
 (23967, 890, 15),       -- Vitiation Tabard +4: Enhancing magic duration +15%
 (23982, 890, 12),       -- Pedagogy Gown +4: Enhancing magic duration +12%
 (23989, 890, 20),       -- Atrophy Gloves +4: Enhancing magic duration +20%
 (24032, 339, 24),       -- Theophany Pantaloons +4: "Regen" duration +24
 (24074, 890, 30),       -- Futhark Trousers +4: Enhancing magic duration +30%
 (24077, 890, 10),       -- Theophany Duckbills +4: Enhancing magic duration +10%
 (26265, 339, 15);       -- Lugh's Cape: "Regen" effect duration +15

-- All five Telchine pieces and Bookworm's Cape: "Regen" potency +10
-- (id 0x173, value 9) and Enh. Mag. eff. dur. +10% (id 0x4E0, value 9).
UPDATE char_inventory SET extra = X'02037349E04C000000000000000000000000000000000000'
 WHERE item_id IN (26736, 26894, 27048, 27235, 27405, 28636);
UPDATE char_locker SET extra = X'02037349E04C000000000000000000000000000000000000'
 WHERE item_id IN (26736, 26894, 27048, 27235, 27405, 28636);
