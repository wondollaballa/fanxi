-- Chemist clubs and the Data-page name for the universal toolkit.
--
-- CHM already has the club skill rank in game/skills.py.  The retail club rows
-- carry the job mask for the jobs that had club skill before job 23 existed, so
-- add the Chemist bit (job 23 = 1 << 22) to every one-handed club.  That covers
-- Wizard's Rod (Reforged), Maxentius and Bunzi's Rod without naming one item.
UPDATE items
   SET jobs = jobs | 4194304
 WHERE skill = 11
   AND equip_slot IN ('main', 'sub')
   AND (jobs & 4194304) = 0;

-- The Chemistry Toolkit is the client-known Alchemy Kit 55.  Give it a shop
-- alias so the launcher's Data -> Items search finds it by the name the HUD and
-- the recipes use.
INSERT OR IGNORE INTO item_aliases (item_id, alias)
VALUES (8899, 'chemistry toolkit');
