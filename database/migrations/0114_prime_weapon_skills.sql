-- The Prime weapons' own weapon skills, and the "Adds weapon skill" line that grants
-- them while the weapon is equipped (migration 114).
--
-- Retail gives each Prime weapon one unique weapon skill and unlocks it with
-- ADDS_WEAPONSKILL (item_mods mod 355) on the stage-three and later forms.  Migration
-- 87 copied that modifier for Varga Purnikawa and Mpu Gandring but the server had no
-- rows for the skills themselves, so the menu had nothing to advertise: equipping
-- Dokoku did not put Zesho Meppo in the Weapon Skills menu.
--
-- A negative skill_level is the table's "item-granted" marker.  These skills are not
-- learned at a combat-skill value: they are usable only while an item that carries the
-- 355 modifier is worn.  weapon_skill_ids_for() ignores negative rows, so no ordinary
-- katana ever advertises Zesho Meppo; ZoneSession.equipped_weapon_skills() adds the
-- rows granted by the current outfit.  The existing 0 means "quested/relic/empyrean",
-- which the server offers at 350 skill, and positive values are the normal skill gates.
--
-- The ids and English names come from the client's weapon-skill table (Windower's
-- resources_data/weapon_skills.lua).  The client, not the server, prints the name, so the
-- id is what matters for the menu.  Animation is the same weapon type's relic animation:
-- retail's Prime skills reuse the relic motion, and the client plays the field in the
-- 0x028 result.
--
-- The 119 III item ids are the forms migration 87 grants; Loughnashade's Prime song is
-- a bard song rather than a weapon skill, and Duban is a shield, so neither is here.

INSERT OR REPLACE INTO weapon_skills (id,name,skill,skill_level,element,animation) VALUES
 (62, 'Fimbulvetr',     4, -1, 0, 115),  -- Helheim, great sword
 (78, 'Blitz',          5, -1, 0, 55),   -- Spalirisos, axe
 (94, 'Disaster',       6, -1, 0, 100),  -- Laphria, great axe
 (110,'Origin',         7, -1, 0, 70),   -- Foenaria, scythe
 (126,'Diarmuid',       8, -1, 0, 130),  -- Gae Buide, polearm
 (142,'Zesho Meppo',    9, -1, 0, 160),  -- Dokoku, katana
 (159,'Tachi: Mumei',  10, -1, 0, 175),  -- Kusanagi, great katana
 (204,'Sarv',          25, -1, 0, 225),  -- Pinaka, archery
 (222,'Terminus',      26, -1, 0, 226),  -- Earp, marksmanship
 (231,'Maru Kala',      1, -1, 0, 25),   -- Varga Purnikawa, hand-to-hand
 (232,'Ruthless Stroke',2, -1, 0, 41),   -- Mpu Gandring, dagger
 (233,'Imperator',      3, -1, 0, 12),   -- Caliburnus, sword
 (234,'Dagda',         11, -1, 0, 86),   -- Lorg Mor, club
 (235,'Oshala',        12, -1, 0, 145);  -- Opashoro, staff

-- Varga Purnikawa (21535, 231) and Mpu Gandring (21590, 232) already carry their
-- modifier from migration 87; these are the other twelve 119 III Prime weapons.
INSERT OR REPLACE INTO item_mods (item_id,mod_id,value) VALUES
 (21646,355,233),  -- Caliburnus: Imperator
 (21653,355,62),   -- Helheim: Fimbulvetr
 (21785,355,94),   -- Laphria: Disaster
 (21730,355,78),   -- Spalirisos: Blitz
 (21837,355,110),  -- Foenaria: Origin
 (21891,355,126),  -- Gae Buide: Diarmuid
 (21932,355,142),  -- Dokoku: Zesho Meppo
 (21986,355,159),  -- Kusanagi: Tachi: Mumei
 (22002,355,234),  -- Lorg Mor: Dagda
 (22106,355,235),  -- Opashoro: Oshala
 (22163,355,204),  -- Pinaka: Sarv
 (22164,355,222);  -- Earp: Terminus
