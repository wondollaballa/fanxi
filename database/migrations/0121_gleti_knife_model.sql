-- Gleti's Knife was drawing Kannagi's katana.
--
-- LandSandBoat's item_equipment row gives item 21567 MId 513, which is Kannagi's
-- model: ROM/247/27.DAT (male) and ROM/247/40.DAT (female), both a "weap" model
-- whose texture is weap010.  The knife therefore hung on the hip as a katana,
-- with the katana's grip.
--
-- The client's own model table (xi-tools' mv/lists/characters.json, built by
-- walking FFXiMain's race/slot groups and resolving each MId through FTABLE)
-- puts Gleti's Knife at MId 877 for every race.  On Hume female that is
-- ROM/366/48.DAT in the main slot and ROM/368/40.DAT in the sub slot; both are
-- "knif" models with texture knif_bs0, and 877 is not used by any other item.
--
-- The other equipped dagger is already right: Mpu Gandring is 907, the Prime
-- dagger the same table lists as "Mpu Gandring (Non AG)" (ROM/375/9.DAT,
-- texture hf_knf5).
UPDATE items SET model = 877 WHERE item_id = 21567;
INSERT OR REPLACE INTO item_models (item_id, model) VALUES (21567, 877);
