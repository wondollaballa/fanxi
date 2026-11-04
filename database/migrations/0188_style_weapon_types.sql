-- Style lock keeps a weapon's appearance only while the equipped weapon is the same
-- type as the one that was locked (retail's rule).  The model columns alone cannot tell
-- a same-type swap from a different-type one, so the locked type is stored beside them.
-- Zero means an older lock or an unknown item: those keep the pre-type behavior rather
-- than freezing a weapon the character has since put away.
ALTER TABLE characters ADD COLUMN style_main_type INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN style_sub_type INTEGER NOT NULL DEFAULT 0;
