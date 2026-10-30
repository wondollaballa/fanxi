-- Desultor Tassets' "Waltz" TP cost -50 TP was missing from item_mods.
--
-- LandSandBoat's modifier enum calls this `waltz_cost` (id 139) and stores it in
-- 5-TP units: scripts/globals/job_utils/dancer.lua subtracts `mod * 10` from the
-- waltz's base cost, so value 5 is the tassets' -50 TP.  The HUD carries the same
-- item-to-reduction table for its pre-click affordability check.
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES (16370, 139, 5);
