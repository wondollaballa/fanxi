-- Style lock (/lockstyle on|off, /lockstyleset).  The appearance models are the ones the
-- client would otherwise take from the equipped gear; keeping them on the character row
-- is what stops the gear-swap "blinking" surviving a relog.
ALTER TABLE characters ADD COLUMN style_lock INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN style_head INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN style_body INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN style_hands INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN style_legs INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN style_feet INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN style_main INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN style_sub INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN style_ranged INTEGER NOT NULL DEFAULT 0;
