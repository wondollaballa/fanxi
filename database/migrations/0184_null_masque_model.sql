-- Null Masque's masque model (migration 184).
--
-- Migration 111 gave every item in the full client catalogue a grap model.  Null
-- Masque (24270) comes from The Orb's Radiance II, and LandSandBoat's item_equipment
-- row is still `MId 0 / TODO: verify model`, so the importer's related-set guess
-- used the Rogue's Bonnet: 4170 (0x1000 + 74).  On Onedough the all-jobs head then
-- drew as the THF artifact bonnet instead of the masque its icon shows.
--
-- The client's 2025 head model 522 is the masque (ROM/387/6.DAT, texture hm_mts1);
-- it is the only face mask among the five new head models 518-522.  The raw grap id
-- is 0x1000 + 522 = 4618, the same "slot base + MId" form every other armour row
-- uses.  Keep item_models in step so a grant or clone re-stamps it.

INSERT OR REPLACE INTO item_models (item_id, model) VALUES (24270, 4618);
UPDATE items SET model = 4618 WHERE item_id = 24270;
