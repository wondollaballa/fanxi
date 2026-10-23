DELETE FROM char_inventory WHERE character_id=1 AND item_id=16735;
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model)
VALUES (21757,'Conqueror',1,0,'main',99,'Warrior mythic great axe, iLvl 119.',555);
INSERT OR REPLACE INTO char_inventory (character_id,container,slot,item_id,quantity) SELECT 1,0,26,21757,1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);
