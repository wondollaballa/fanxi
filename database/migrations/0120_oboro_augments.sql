-- Oboro Dynamis-Divergence weapon augments (migration 120).
--
-- Musa (item 22099) used to carry Path C as three static item_mods rows
-- because the Oboro bundle table was not wired into the launcher.  The
-- client stores Oboro weapon augments in the same 24-byte bundle block
-- Odyssey and Limbus use, so this migration removes the static rows and
-- stamps the real R25 Path C block (bundle 189) onto every Musa copy.
--
-- Path C at R25 is "Regen" potency +25, "Cure" potency +25% and
-- "Fast Cast"+10%.  The block uses rank 25 / tier 2 (the 25-rank unlock),
-- curve A and the rank-bar maximum of 3,180 RP; the lifetime total is
-- 25,150 RP.  Generated from data/oboro_r25.json by tools/gen_oboro.py.

DELETE FROM item_mods WHERE item_id = 22099 AND mod_id IN (170, 374, 838, 1223);

UPDATE char_inventory SET extra = X'03830000B2316401BD000000000000000000000000000000' WHERE item_id = 22099;
UPDATE char_locker SET extra = X'03830000B2316401BD000000000000000000000000000000' WHERE item_id = 22099;

-- The launcher's Oboro card owns every other weapon; no other Oboro item
-- has a static path row to remove.
