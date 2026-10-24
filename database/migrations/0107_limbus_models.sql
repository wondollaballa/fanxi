-- Limbus armour models (migration 107).
--
-- Migration 99 inserted the 25 Limbus pieces with model 0, so ZoneSession skipped
-- the grap update and the client kept whatever look the slot had before: the gear
-- equipped and its stats applied, but the character never showed it.  The client
-- model table (xi-tools' mv/lists/characters.json) maps the five families to
-- armour MIds 513-517: Revelation 513, Sworn 514, Indomitable 515, Duty 516 and
-- Clemency 517.  The raw grap model is the slot base (0x1000 head, 0x2000 body,
-- 0x3000 hands, 0x4000 legs, 0x5000 feet) plus that MId.
--
-- The item_models rows also feed migration 95's triggers, so a later grant of any
-- of these pieces gets the model even though LandSandBoat's item_equipment rows
-- still say MId 0 ("not implemented").

INSERT OR REPLACE INTO item_models (item_id, model) VALUES
 (24122,4609), -- Revelation Masque (Revelation, MId 513)
 (24125,8705), -- Revelation Plate. (Revelation, MId 513)
 (24128,12801), -- Revelation Gaunt. (Revelation, MId 513)
 (24131,16897), -- Revelation Brais (Revelation, MId 513)
 (24134,20993), -- Revelation Sab. (Revelation, MId 513)
 (24137,4610), -- Sworn Crown (Sworn, MId 514)
 (24140,8706), -- Sworn Platemail (Sworn, MId 514)
 (24143,12802), -- Sworn Gauntlets (Sworn, MId 514)
 (24146,16898), -- Sworn Brais (Sworn, MId 514)
 (24149,20994), -- Sworn Sabatons (Sworn, MId 514)
 (24152,4611), -- Indom. Petasos (Indomitable, MId 515)
 (24155,8707), -- Indomitable Coat (Indomitable, MId 515)
 (24158,12803), -- Indom. Gloves (Indomitable, MId 515)
 (24161,16899), -- Indom. Tonban (Indomitable, MId 515)
 (24164,20995), -- Indom. Sabots (Indomitable, MId 515)
 (24167,4612), -- Duty Crown (Duty, MId 516)
 (24170,8708), -- Duty Cyclas (Duty, MId 516)
 (24173,12804), -- Duty Gauntlets (Duty, MId 516)
 (24176,16900), -- Duty Flanchard (Duty, MId 516)
 (24179,20996), -- Duty Sollerets (Duty, MId 516)
 (24182,4613), -- Clemen. Somen (Clemency, MId 517)
 (24185,8709), -- Clemen. Hara. (Clemency, MId 517)
 (24188,12805), -- Clemency Kote (Clemency, MId 517)
 (24191,16901), -- Clem. Haidate (Clemency, MId 517)
 (24194,20997) -- Clem. Sune-Ate (Clemency, MId 517)
;

-- The rows migration 99 already inserted carry model 0; copy the table onto them.
UPDATE items
   SET model = (SELECT item_models.model FROM item_models
                 WHERE item_models.item_id = items.item_id)
 WHERE item_id IN (24122, 24125, 24128, 24131, 24134, 24137, 24140, 24143, 24146, 24149, 24152, 24155, 24158, 24161, 24164, 24167, 24170, 24173, 24176, 24179, 24182, 24185, 24188, 24191, 24194);
