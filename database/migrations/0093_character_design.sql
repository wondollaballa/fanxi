-- Character designs: keep the face and hair colour apart.
--
-- Before this migration `characters.face` held the client's combined look byte:
--
--     look = (face - 1) * 2 + hair          -- hair 0 = colour A, 1 = colour B
--
-- so a launcher "Face 2" could be Face 2 Hair A while "Face 1" was Face 1 Hair B.
-- The character designer needs both values by name.  The UPDATE below recovers
-- them from the old byte; it is lossless for every value 0-15, including rows
-- that were written before the CHECK constraint was in place.
--
-- This runs in migration order before seed.sql, so a fresh database has no rows
-- to convert and just gets the new column.

ALTER TABLE characters ADD COLUMN hair INTEGER NOT NULL DEFAULT 0 CHECK (hair IN (0, 1));

UPDATE characters SET hair = face % 2, face = (face / 2) + 1;
