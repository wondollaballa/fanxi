-- Centovente's Trial of the Magians augment: TP Bonus +1000 (migration 144).
--
-- The Magian block is kind 0x02 with sub-kind 0x43 (standard | trial).  TP Bonus is
-- augment id 353 (0x161) and the Magian scale is (value + 1) * 50, so value 19 is
-- +1000.  The block is written only to copies that have no augment block yet, so a
-- Centovente already carrying the WSD or Store TP choice is left alone.

UPDATE char_inventory
   SET extra = X'024361990000000000000000000000000000000000000000'
 WHERE item_id = 19874
   AND (extra IS NULL OR extra = X'');
