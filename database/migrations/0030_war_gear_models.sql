-- Armor model families from item_equipment.MId: Pummeler 64, Agoge 65, Ravager 282.
UPDATE items SET model = 64  WHERE item_id IN (23895,23940,23985,24030,24075);
UPDATE items SET model = 65  WHERE item_id IN (23918,23963,24008,24053,24098);
UPDATE items SET model = 282 WHERE item_id IN (11064,11084,11104,11124,11144);
