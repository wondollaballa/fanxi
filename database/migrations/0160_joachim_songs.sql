-- The songs Joachim needs to be a Bard the owner asks for rather than a jukebox.
--
-- His imported `mob_spell_list` row carries the Paeon/Ballad/Madrigal/March/Elegy lines
-- and nothing else, so he could not keep Attack up or answer a capped attacker.  With
-- the Daurdabla and Gjallarhorn from migration 159 he can hold four songs, which is
-- exactly the set the new rotation keeps.
INSERT OR REPLACE INTO trust_spells (trust_spell_id, spell_id, min_level, max_level) VALUES
    (911, 398, 75, 255),    -- Valor Minuet V   (+Attack, the Attack the owner is short on)
    (911, 402, 55, 255),    -- Archer's Prelude (+Ranged Accuracy)
    (911, 418, 99, 255);    -- Aria of Passion  (+Damage Limit once Attack is capped)
