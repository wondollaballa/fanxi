-- item_equipment.MId is authoritative: Laphria 119 III is model 548, Chango is model 764.
-- 0037 swapped them, which made the equipped Laphria render as the Aeonic great axe.
UPDATE items SET model = 548 WHERE item_id = 21785; -- Laphria (Level 119 III)
UPDATE items SET model = 548 WHERE item_id = 21782; -- Laphria (Prime base entry)
UPDATE items SET model = 764 WHERE item_id = 20843; -- Chango
