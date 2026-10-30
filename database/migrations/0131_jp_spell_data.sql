-- The RDM job-point spells were seeded from a self-only stub: 0 MP, a 2 s cast and
-- valid_targets=1.  The client records say Distract III / Frazzle III / Addle II are
-- enemy enfeebles, and Refresh III is self-or-party.  Without these values a party
-- member selected with <stpc> cannot receive Refresh III, and the enfeebles never
-- reach a monster.
UPDATE spells SET valid_targets = 4, mp = 84, cast_time = 3000 WHERE id = 882; -- Distract III
UPDATE spells SET valid_targets = 4, mp = 90, cast_time = 3000 WHERE id = 883; -- Frazzle III
UPDATE spells SET valid_targets = 4, mp = 63, cast_time = 2000 WHERE id = 884; -- Addle II
UPDATE spells SET valid_targets = 3, mp = 80, cast_time = 5000 WHERE id = 894; -- Refresh III
UPDATE spells SET cast_time = 3000 WHERE id = 895;                              -- Temper II
