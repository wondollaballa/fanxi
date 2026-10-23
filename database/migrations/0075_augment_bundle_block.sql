-- Augment bundle block (migration 75).
--
-- Migration 73 wrote an older guess at the augmented-item extdata.  The real
-- layout is LandSandBoat's Exdata::AugmentBundle, confirmed against a retail
-- rank-25 JSE neck: kind 0x03 / subkind 0x83, a bitfield at offset 4 holding
-- type, RP, rank (bits 18-22), max rank tier (bits 23-24) and RP curve, then a
-- 32-bit augment bundle index and a 12-byte signature.
--
-- These rows are Rank 30 / tier 3 (the 30-rank unlock).  The bundle index is 0
-- until the per-item index is known; see docs/odyssey-r30.md and
-- server/fanxi_server/game/augments.py.
UPDATE char_inventory SET extra = X'038300000000f80100000000000000000000000000000000'
WHERE item_id IN (
    23761, 23768, 23775, 23782, 23789,   -- Nyame
    23757, 23764, 23771, 23778, 23785,   -- Sakpata's
    23756, 23763, 23770, 23777, 23784,   -- Gleti's
    23759, 23766, 23773, 23780, 23787,   -- Agwu's
    21527, 21637, 21567, 22150, 21724, 21675, 21832
);

-- The test copy of the Nyame Helm goes back to its wardrobe slot.
UPDATE char_inventory SET container = 10, slot = 36
WHERE character_id = 1 AND item_id = 23761 AND container = 0;
