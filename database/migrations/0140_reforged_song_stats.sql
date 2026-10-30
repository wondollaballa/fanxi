-- Reforged +3/+4 song stats (migration 140).
--
-- tools/import_reforged_item_data.py had no rule for "Song spellcasting time",
-- "Song casting time", "Song effect duration", "Song duration" or "Song recast
-- delay", so the +3 empyrean and +4 relic pieces stored every other tooltip line
-- and none of their bard stats.  The client still draws the real tooltip from its
-- DAT, so a Bard's song precast set (Fili Calot +3, Brioso Justaucorps +4, Bihu
-- Slippers +4) read 0% song spellcasting time on the server while retail shortens
-- the cast by 41%.
--
-- The generator now parses all three families, so a future regeneration of 0092
-- carries these rows too.  This migration backfills every database built from the
-- older 0092 (including a fresh install, which applies 0092 and then this file).
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
    (23429, 455, 16),   -- Fili Calot +3: Song spellcasting time -16%
    (23496, 454, 14),   -- Fili Hongreline +3: Song effect duration +14%
    (23630, 833, 10),   -- Fili Rhingrave +3: Song recast delay -10
    (23949, 455, 15),   -- Brioso Justaucorps +4: Song casting time -15%
    (24084, 454, 15),   -- Brioso Slippers +4: Song duration +15%
    (24107, 455, 10);   -- Bihu Slippers +4: Song casting time -10%
