-- Prime weapons wear their afterglow (migration 125).
--
-- Every Prime weapon has two client looks.  Stages 2-4 use the "Non AG" (no afterglow)
-- model: the black relic-style weapon with no particle system.  Stage 5, the iLvl 119 III
-- form, uses the "Stage 5" model: the same weapon DAT followed by the client's `aura`
-- chunk (fr00/gp00/aukl/auon/f0ca/g0ca/pi1/flm/flmy), which is the afterglow particle
-- aura.  The other ultimate weapons already show it: their iLvl 119 rows carry the
-- "119 AG" models and those DATs carry the same aura block (Spharai 497, Excalibur 545,
-- Mandau 544, Verethragna 494, Idris 834, ...).
--
-- The Prime rows did not.  Migration 87 pinned some final forms to the Non AG ids (Mpu
-- Gandring 907, Helheim 909, ...) and left the rest on the relic MId LandSandBoat stores
-- (Caliburnus 545 = Excalibur, Kusanagi 514 = Masamune, Lorg Mor 553 = Mjollnir,
-- Opashoro 554), or on 0 for the bow, gun, horn and shield.  The client therefore drew
-- an auraless weapon, or a relic look, even on the 119 III form.
--
-- The ids come from the client's own model table (xi-tools' mv/lists/characters.json,
-- built by walking FFXiMain's race/slot groups and resolving each MId through FTABLE):
--
--   family              Non AG (2-4)  Stage 5 / afterglow (119 III)
--   Varga Purnikawa            475     474
--   Mpu Gandring               907     918
--   Caliburnus                 908     919
--   Helheim                    909     920
--   Spalirisos                 910     921
--   Laphria                    911     922
--   Gae Buide                  912     923
--   Foenaria                   913     924
--   Dokoku                     914     925
--   Kusanagi                   915     926
--   Lorg Mor                   916     927
--   Opashoro                   917     928
--   Pinaka                     148     151
--   Earp                       149     152
--   Loughnashade               150     153
--   Duban                      675     676
--
-- The last five families are not in the 900s block: the H2H and ranged groups put their
-- afterglow next to their own normal models.  Every Stage 5 DAT above is the Non AG
-- weapon's bytes followed by the 12,688-byte aura block, so switching to it changes only
-- the aura; the weapon mesh and texture stay the same.  The 119 III rows are the last
-- item id of each family, the ones migration 87 grants; the other ids are stages 2-4.
--
-- `item_models` gets the same mapping so the insert triggers and
-- `tools/item_models.py --apply` keep it.  The final UPDATE retargets Onedough's style
-- lock, which saved the old auraless Mpu Gandring model instead of an item id.

-- Stages 2-4: the Non AG look.
UPDATE items SET model = 475 WHERE item_id IN (21532, 21533, 21534);  -- Varga Purnikawa
UPDATE items SET model = 907 WHERE item_id IN (21587, 21588, 21589);  -- Mpu Gandring
UPDATE items SET model = 908 WHERE item_id IN (21643, 21644, 21645);  -- Caliburnus
UPDATE items SET model = 909 WHERE item_id IN (21649, 21651, 21652);  -- Helheim
UPDATE items SET model = 910 WHERE item_id IN (21727, 21728, 21729);  -- Spalirisos
UPDATE items SET model = 911 WHERE item_id IN (21782, 21783, 21784);  -- Laphria
UPDATE items SET model = 913 WHERE item_id IN (21834, 21835, 21836);  -- Foenaria
UPDATE items SET model = 912 WHERE item_id IN (21888, 21889, 21890);  -- Gae Buide
UPDATE items SET model = 914 WHERE item_id IN (21929, 21930, 21931);  -- Dokoku
UPDATE items SET model = 915 WHERE item_id IN (21983, 21984, 21985);  -- Kusanagi
UPDATE items SET model = 916 WHERE item_id IN (21998, 22000, 22001);  -- Lorg Mor
UPDATE items SET model = 917 WHERE item_id IN (22103, 22104, 22105);  -- Opashoro
UPDATE items SET model = 148 WHERE item_id IN (22156, 22157, 22158);  -- Pinaka
UPDATE items SET model = 149 WHERE item_id IN (22160, 22161, 22162);  -- Earp
UPDATE items SET model = 150 WHERE item_id IN (22304, 22305, 22306);  -- Loughnashade
UPDATE items SET model = 675 WHERE item_id IN (26492, 26493, 26494);  -- Duban

-- Stage 5 (iLvl 119 III): the same weapon plus the afterglow aura.
UPDATE items SET model = 474 WHERE item_id = 21535;  -- Varga Purnikawa
UPDATE items SET model = 918 WHERE item_id = 21590;  -- Mpu Gandring
UPDATE items SET model = 919 WHERE item_id = 21646;  -- Caliburnus
UPDATE items SET model = 920 WHERE item_id = 21653;  -- Helheim
UPDATE items SET model = 921 WHERE item_id = 21730;  -- Spalirisos
UPDATE items SET model = 922 WHERE item_id = 21785;  -- Laphria
UPDATE items SET model = 924 WHERE item_id = 21837;  -- Foenaria
UPDATE items SET model = 923 WHERE item_id = 21891;  -- Gae Buide
UPDATE items SET model = 925 WHERE item_id = 21932;  -- Dokoku
UPDATE items SET model = 926 WHERE item_id = 21986;  -- Kusanagi
UPDATE items SET model = 927 WHERE item_id = 22002;  -- Lorg Mor
UPDATE items SET model = 928 WHERE item_id = 22106;  -- Opashoro
UPDATE items SET model = 151 WHERE item_id = 22163;  -- Pinaka
UPDATE items SET model = 152 WHERE item_id = 22164;  -- Earp
UPDATE items SET model = 153 WHERE item_id = 22307;  -- Loughnashade
UPDATE items SET model = 676 WHERE item_id = 26495;  -- Duban

-- Keep the lookup table in step: the triggers stamp these models on a later item,
-- inventory or equipment insert, and tools/item_models.py --apply repairs from it.
INSERT OR REPLACE INTO item_models (item_id, model) VALUES
 (21532,475), (21533,475), (21534,475), (21535,474),
 (21587,907), (21588,907), (21589,907), (21590,918),
 (21643,908), (21644,908), (21645,908), (21646,919),
 (21649,909), (21651,909), (21652,909), (21653,920),
 (21727,910), (21728,910), (21729,910), (21730,921),
 (21782,911), (21783,911), (21784,911), (21785,922),
 (21834,913), (21835,913), (21836,913), (21837,924),
 (21888,912), (21889,912), (21890,912), (21891,923),
 (21929,914), (21930,914), (21931,914), (21932,925),
 (21983,915), (21984,915), (21985,915), (21986,926),
 (21998,916), (22000,916), (22001,916), (22002,927),
 (22103,917), (22104,917), (22105,917), (22106,928),
 (22156,148), (22157,148), (22158,148), (22163,151),
 (22160,149), (22161,149), (22162,149), (22164,152),
 (22304,150), (22305,150), (22306,150), (22307,153),
 (26492,675), (26493,675), (26494,675), (26495,676);

-- A style lock stores model ids, not items, and this character's saved main is the old
-- Non AG Mpu Gandring (907) that the 119 III item used before this migration.  Without
-- the retarget the lock would keep drawing the auraless dagger.  Character 1 is the only
-- row whose lock is on; 907 is also the real stage 2-4 model, so a deliberate lock of
-- that look on another character is left alone.
UPDATE characters SET style_main = 918 WHERE id = 1 AND style_main = 907;
