-- CHM test access to everything SCH can wear.
--
-- Job 20 (SCH) is bit 19, 524288; job 23 (CHM) is bit 22, 4194304.  Every item whose
-- mask includes SCH, including the all-job mask and SCH JSE/accessories, gets the CHM
-- bit.  This is explicitly a test pass: it lets GearSwap equip SCH gear on CHM while
-- the real Chemist set is being designed.
UPDATE items
   SET jobs = jobs | 4194304
 WHERE (jobs & 524288) != 0
    OR jobs = 0;
