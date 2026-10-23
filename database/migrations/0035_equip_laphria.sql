-- Put Laphria in the first main-hand inventory slot so auto-equip selects it.
UPDATE char_inventory SET slot = 31 WHERE character_id = 1 AND item_id = 16534;
UPDATE char_inventory SET slot = 2  WHERE character_id = 1 AND item_id = 21782;
