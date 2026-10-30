-- The style lock stores model ids, not items.  Onedough's saved look is the Mpu
-- Gandring / Gleti's Knife pair (907 / 513), captured before the knife's item model
-- was corrected; with the lock on, the locked sub still draws Kannagi's katana even
-- after migration 121 fixes items.model.  Retarget that saved look to 877.
--
-- Only character 1's lock is touched: 513 is also Kannagi's real model, so a
-- character who deliberately locked a Kannagi keeps it.
UPDATE characters SET style_sub = 877 WHERE id = 1 AND style_sub = 513;
