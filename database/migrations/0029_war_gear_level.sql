-- items.level is the required character level, not the item level.  The +4 armor
-- is item level 119 but only requires level 99.
UPDATE items SET level = 99 WHERE item_id IN
(23895,23940,23985,24030,24075,23918,23963,24008,24053,24098,11064,11084,11104,11124,11144);
