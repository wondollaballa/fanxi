-- The weapons a Trust carries.
--
-- A Trust's gear is part of its design, not a drop: Sylvie (UC) is drawn with Idris, and
-- Joachim is the Bard alter ego built around the Daurdabla/Gjallarhorn pair.  The rows
-- are factual, like the Trust rows themselves; `game/trust_gear.py` turns their item
-- modifiers into the numbers the AI reads.
CREATE TABLE IF NOT EXISTS trust_gear (
    trust_spell_id INTEGER NOT NULL REFERENCES trusts(spell_id) ON DELETE CASCADE,
    item_id        INTEGER NOT NULL REFERENCES items(item_id),
    PRIMARY KEY (trust_spell_id, item_id)
);

INSERT OR REPLACE INTO trust_gear (trust_spell_id, item_id) VALUES
    (981, 21080),   -- Sylvie (UC): Idris (iL119 III)
    (911, 18839),   -- Joachim: Daurdabla (+2 song slots, +30% song duration)
    (911, 18840);   -- Joachim: Gjallarhorn (All Songs +4)
