-- Limbus weapon grap models (migration 0176).
--
-- The 2026 wave carries no MId in any server data: LandSandBoat marks these
-- rows `TODO: MId`, and the client's own item records hold no model at all
-- (the model is server-side data private servers curate by hand).  An
-- equipped copy therefore had model 0 and the client drew nothing -- the
-- server logged "equipped Telopanos Sword in slot 0 with no grap model: it
-- will not show".
--
-- Each weapon takes the client model of its own weapon type -- the 2026
-- Ethereal block (929-938, one model per weapon group) where it names the
-- type, the type's Stage 5 afterglow otherwise.  These are stand-ins, not
-- the Telopanos skins: //model <item> <id> overrides one copy's look, and a
-- dataset edit plus regeneration bakes a better id in.
--
-- Generated from data/limbus_weapons_r30.json by tools/gen_limbus_weapons.py.

INSERT OR REPLACE INTO item_models (item_id,model) VALUES
  (21549,474), (21599,929), (21738,931), (21795,932), (21848,934), (21899,933), (21942,935), (21948,936), (22176,151), (22182,930), (22188,930), (22225,937), (22231,938), (22237,920), (26503,676);

-- The rows already in the catalogue keep their model too (item_models'
-- triggers only stamp rows inserted later).
UPDATE items SET model = CASE item_id
  WHEN 21549 THEN 474
  WHEN 21599 THEN 929
  WHEN 21738 THEN 931
  WHEN 21795 THEN 932
  WHEN 21848 THEN 934
  WHEN 21899 THEN 933
  WHEN 21942 THEN 935
  WHEN 21948 THEN 936
  WHEN 22176 THEN 151
  WHEN 22182 THEN 930
  WHEN 22188 THEN 930
  WHEN 22225 THEN 937
  WHEN 22231 THEN 938
  WHEN 22237 THEN 920
  WHEN 26503 THEN 676
  ELSE model END
 WHERE item_id IN (21549, 21599, 21738, 21795, 21848, 21899, 21942, 21948, 22176, 22182, 22188, 22225, 22231, 22237, 26503);
