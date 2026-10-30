-- Bard song rules: the instrument-granted songs, Loughnashade's song stats, and
-- Soul Voice's recast id.
--
-- Honor March and Aria of Passion share the client's March/Aria status icons with
-- Victory March and Protected Aria.  The two instrument-granted spells were missing
-- from the base spell migration even though the client already knows them.

UPDATE spells
   SET name = 'Honor March', skill = 40, cast_time = 8000, valid_targets = 129,
       element = 7, animation = 417
 WHERE id = 417;

UPDATE spells
   SET name = 'Aria of Passion', skill = 40, cast_time = 8000, valid_targets = 129,
       element = 7, animation = 418
 WHERE id = 418;

-- Loughnashade (Level 119 III): CHR+20, All songs +4, two additional song effects.
-- The lower advanced stages carry the same song lines.
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
    (22305, 14, 20), (22305, 452, 4), (22305, 453, 2),
    (22306, 14, 20), (22306, 452, 4), (22306, 453, 2),
    (22307, 14, 20), (22307, 452, 4), (22307, 453, 2);

-- Soul Voice was the only Bard two-hour with recast_id 0, which made it spammable.
-- 111 is the free slot after Nightingale (109), Troubadour (110) and Pianissimo (112).
UPDATE job_abilities SET recast_id = 111 WHERE id = 25;
