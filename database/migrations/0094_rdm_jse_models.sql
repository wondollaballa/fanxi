-- Red Mage JSE looks (migration 94).
--
-- Migrations 66 and 92 inserted the reforged RDM sets with model = 0.  The server
-- copies items.model into the character's grap list when a piece is equipped
-- (zone.py _apply_equip_model), and a zero model leaves that slot at its previous
-- look: the armour is on (stats, icon, tooltip, EquipViewer) but the head, body,
-- hands, legs or feet render as if bare.  This is why Twodough's Atrophy set did
-- not show after the RDM job change.
--
-- A reforged set reuses the look of the original tier, the same mapping migration
-- 91 applied to Dark Knight.  The grap ids are Windower's DressUp item -> model
-- entries for the original sets:
--   Atrophy   (AF +4)       = Warlock's     4168  8264 12360 16456 20552
--   Vitiation (relic +4)    = Duelist's     4169  8265 12361 16457 20553
--   Lethargy  (empyrean +3) = Estoqueur's   4382  8478 12574 16670 20766
--
-- The other jobs' reforged pieces still carry 0 (or an LSB placeholder) until the
-- same mapping is applied to them.
UPDATE items SET model=4168  WHERE item_id=23899; -- Atrophy Chapeau +4
UPDATE items SET model=8264  WHERE item_id=23944; -- Atrophy Tabard +4
UPDATE items SET model=12360 WHERE item_id=23989; -- Atrophy Gloves +4
UPDATE items SET model=16456 WHERE item_id=24034; -- Atrophy Tights +4
UPDATE items SET model=20552 WHERE item_id=24079; -- Atrophy Boots +4
UPDATE items SET model=4169  WHERE item_id=23922; -- Vitiation Chapeau +4
UPDATE items SET model=8265  WHERE item_id=23967; -- Vitiation Tabard +4
UPDATE items SET model=12361 WHERE item_id=24012; -- Vitiation Gloves +4
UPDATE items SET model=16457 WHERE item_id=24057; -- Vitiation Tights +4
UPDATE items SET model=20553 WHERE item_id=24102; -- Vitiation Boots +4
UPDATE items SET model=4382  WHERE item_id=23424; -- Lethargy Chappel +3
UPDATE items SET model=8478  WHERE item_id=23491; -- Lethargy Sayon +3
UPDATE items SET model=12574 WHERE item_id=23558; -- Lethargy Gantherots +3
UPDATE items SET model=16670 WHERE item_id=23625; -- Lethargy Fuseau +3
UPDATE items SET model=20766 WHERE item_id=23692; -- Lethargy Houseaux +3
