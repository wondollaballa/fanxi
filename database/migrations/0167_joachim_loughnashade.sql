-- Joachim's instrument is the Prime Loughnashade, and the last songs he had no row for.
--
-- The Gjallarhorn migration 159 gave him was Song +4; the final Loughnashade (iLvl 119
-- III, item 22307) is that same Song +4 in one horn and also carries Maximum Songs +2, so
-- the Daurdabla/Gjallarhorn pair becomes a single instrument.  Everything the plan reads
-- -- All Songs +4, the four-song bar, CHR +20 -- comes from this one item now.
DELETE FROM trust_gear WHERE trust_spell_id = 911;
INSERT INTO trust_gear (trust_spell_id, item_id) VALUES (911, 22307);

-- Honor March shares the March status with Victory March but is its own song (Attack,
-- Accuracy, Ranged Attack, Ranged Accuracy and a little Haste), so the plan can spend the
-- March slot on it once Victory's Haste would be redundant.  The lower Minuet tiers are
-- what a Master below 75 -- Valor Minuet V's level -- can still be given: IV at 63 and
-- III at 43, the same levels Ulmia's rows use.
INSERT OR REPLACE INTO trust_spells (trust_spell_id, spell_id, min_level, max_level) VALUES
    (911, 417, 75, 255),    -- Honor March
    (911, 397, 63, 255),    -- Valor Minuet IV
    (911, 396, 43, 255);    -- Valor Minuet III
