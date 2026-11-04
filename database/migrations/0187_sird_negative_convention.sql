-- Spell interruption rate: the item data carries the reduction as a positive
-- percentage (an item's description reads "Spell interruption rate down 20%"), but
-- the server's modifier convention is negative for a reduction, the same as the
-- "Spell Interruption Rate" merit, Choral Roll and the cape augments.  Normalize the
-- item rows once so the interrupt roll, the stat sheet and the capes all read the
-- same sign.  A positive SPELL_INTERRUPT in the roll made gear increase the chance.
UPDATE item_mods SET value = -value WHERE mod_id = 168 AND value > 0;
