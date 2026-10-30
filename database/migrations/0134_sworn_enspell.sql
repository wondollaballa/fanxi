-- The Sworn (Limbus Rank 30) suit is the Red Mage en-spell set: every piece carries
-- "Sword enhancement spell damage"+n -- +8 crown, +10 body, +7 hands, +9 legs,
-- +7 feet, 41 in total.  tools/gen_limbus_r30.py had no mapping for that phrase, so
-- the rows were never generated and the set added nothing to an en-spell hit.
--
-- Migration 99 now writes them for a fresh database; this one backfills databases
-- that already ran it.  The item ids are the same five pieces migration 99 grants.
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
    (24137, 432, 8),
    (24140, 432, 10),
    (24143, 432, 7),
    (24146, 432, 9),
    (24149, 432, 7);
