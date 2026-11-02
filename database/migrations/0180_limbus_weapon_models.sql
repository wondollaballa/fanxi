-- Limbus weapon grap models (migration 0180).
--
-- Supersedes migration 176, which gave these weapons same-type stand-ins so
-- they would at least draw.  The 2026 wave ships no MId in any server data
-- (LandSandBoat marks the rows `TODO: MId`) and the client's item records
-- carry no model either, so the ids below were identified from the client's
-- own 2026 model additions by testing them in game: the Sword is 958, the
-- Claymore 959, the Scythe 962 and the H2H Knuckles 490 (which lives in the
-- Hand-to-hand model group, not the melee block).  The block itself follows
-- the client's skill-id order (Dagger, Sword, G.Sword, Axe, G.Axe, Scythe,
-- Polearm, Katana, G.Katana, Club, Staff).  The one-handed models carry a
-- main and a sub DAT, the two-handed ones main only -- every id below is
-- consistent with its weapon's handedness, which is the cross-check on the
-- derived ones.  H2H, Archery and the shield live in their own groups.
--
-- The Saber and the Shield are still tentative in the dataset note;
-- //model <item> <id> tests one copy and a dataset edit + regeneration bakes
-- the confirmed id in.
--
-- Generated from data/limbus_weapons_r30.json by tools/gen_limbus_weapons.py.

INSERT OR REPLACE INTO item_models (item_id,model) VALUES
  (21549,490), (21599,957), (21738,960), (21795,961), (21848,962), (21899,963), (21942,964), (21948,965), (22176,156), (22182,958), (22188,968), (22225,966), (22231,967), (22237,959), (26503,680);

-- The rows already in the catalogue keep their model too (item_models'
-- triggers only stamp rows inserted later).
UPDATE items SET model = CASE item_id
  WHEN 21549 THEN 490
  WHEN 21599 THEN 957
  WHEN 21738 THEN 960
  WHEN 21795 THEN 961
  WHEN 21848 THEN 962
  WHEN 21899 THEN 963
  WHEN 21942 THEN 964
  WHEN 21948 THEN 965
  WHEN 22176 THEN 156
  WHEN 22182 THEN 958
  WHEN 22188 THEN 968
  WHEN 22225 THEN 966
  WHEN 22231 THEN 967
  WHEN 22237 THEN 959
  WHEN 26503 THEN 680
  ELSE model END
 WHERE item_id IN (21549, 21599, 21738, 21795, 21848, 21899, 21942, 21948, 22176, 22182, 22188, 22225, 22231, 22237, 26503);
