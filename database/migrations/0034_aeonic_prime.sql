INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model)
VALUES (20843,'Chango',1,0,'main',99,'Warrior Aeonic great axe, iLvl 119.',764);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model)
VALUES (21782,'Laphria',1,0,'main',99,'Warrior Prime great axe, iLvl 119.',548);
INSERT OR REPLACE INTO char_inventory (character_id,container,slot,item_id,quantity) SELECT 1,0,29,20843,1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);
INSERT OR REPLACE INTO char_inventory (character_id,container,slot,item_id,quantity) SELECT 1,0,30,21782,1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);
