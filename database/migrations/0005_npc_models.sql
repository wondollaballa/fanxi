-- Model 50 is a common invisible/trigger placeholder.  The only guaranteed-visible
-- static model we have a reference for is the Moogle (0x52 = 82).
UPDATE world_npcs SET model = 82 WHERE zone = 246;
