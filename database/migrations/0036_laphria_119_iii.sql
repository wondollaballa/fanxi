DELETE FROM char_inventory WHERE character_id=1 AND item_id=21782;
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model)
VALUES (21785,'Laphria',1,0,'main',99,'Warrior Prime great axe, Item Level 119 III.',548);
INSERT OR REPLACE INTO char_inventory (character_id,container,slot,item_id,quantity) SELECT 1,0,2,21785,1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);
