-- Augmented-item extdata (migration 73).
--
-- `char_inventory.extra` is the 24-byte attribute block the 0x020 packet carries;
-- the client decodes it into the augment lines on the item tooltip.  The layout
-- is Windower's `extdata.lua` "augment system 4", verified against a retail
-- sample (`03 83 00 00 78 2D 64 03 CC 00 00 00` decodes as Path A, Rank 25):
--
--   byte 1   3      augmented equipment
--   byte 2   0x83   augment system 4: path + rank
--   byte 5   path   low two bits, 0 = A, 1 = B, 2 = C, 3 = D
--   byte 7   rank   rank << 2 (Rank 30 = 0x78)
--   bytes 13-24     signature, zero for Fanxi items
--
-- This is exactly Odyssey's Rank 30 row, so the client can draw the augment
-- lines from the item id, path and rank alone.  Nyame has four paths; the
-- single-row sets (Sakpata's, Gleti's, Agwu's) and the seven weapons use Path A.
-- `!augment <A-D|off> <item>` changes a copy in game.  See docs/odyssey-r30.md.
ALTER TABLE char_inventory ADD COLUMN extra BLOB NOT NULL DEFAULT X'';

UPDATE char_inventory
SET extra = X'038300000000f80100000000000000000000000000000000'
WHERE item_id IN (
    23761, 23768, 23775, 23782, 23789,   -- Nyame, Path A
    23757, 23764, 23771, 23778, 23785,   -- Sakpata's
    23756, 23763, 23770, 23777, 23784,   -- Gleti's
    23759, 23766, 23773, 23780, 23787,   -- Agwu's
    21527, 21637, 21567, 22150, 21724, 21675, 21832   -- Odyssey weapons
);
