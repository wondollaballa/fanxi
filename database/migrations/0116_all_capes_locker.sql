-- Ambuscade JSE cape builds in the hidden locker (migration 116).
--
-- All 22 job capes share one item id per job, so each build is a copy
-- distinguished only by its 24-byte standard-augment block.  The hidden
-- locker (9999 items, not a client bag) is the only place they all fit:
-- 198 builds against the 253 free capacity in the live character.
--
-- char_locker gains the block and a primary key that includes it, so the
-- nine Taranus's Capes (or eleven Andartia's Mantles) can coexist.  The
-- old rows (broths, tools, ammo) get an empty block and keep their data.
--
-- Old bag/wardrobe cape copies are removed so the locker is the one
-- source of truth; an equipped cape stays and is re-encoded to its job's
-- default build.  //job then grabs the capes from the locker into the
-- wardrobes, and the normal job-change tidy puts the loose ones away.

ALTER TABLE char_locker RENAME TO char_locker_old;
CREATE TABLE char_locker (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_id      INTEGER NOT NULL,
    extra        BLOB    NOT NULL DEFAULT X'',
    quantity     INTEGER NOT NULL DEFAULT 1,
    stored_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (character_id, item_id, extra)
);
INSERT INTO char_locker (character_id, item_id, extra, quantity, stored_at)
SELECT character_id, item_id, X'', quantity, stored_at FROM char_locker_old;
DROP TABLE char_locker_old;

DELETE FROM char_inventory
 WHERE character_id = 1
   AND item_id IN (26246, 26247, 26248, 26249, 26250, 26251, 26252, 26253, 26254, 26255, 26256, 26257, 26258, 26259, 26260, 26261, 26262, 26263, 26264, 26265, 26266, 26267)
   AND NOT EXISTS (
     SELECT 1 FROM char_equip e
      WHERE e.character_id = char_inventory.character_id
        AND e.container = char_inventory.container
        AND e.slot = char_inventory.slot);

UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26246
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped WAR
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26247
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped MNK
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26248
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped WHM
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26249
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped BLM
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26250
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped RDM
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26251
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped THF
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26252
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped PLD
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26253
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped DRK
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26254
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped BST
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26255
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped BRD
UPDATE char_inventory SET extra = X'0203039A4598034A8E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26256
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped RNG
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26257
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped SAM
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26258
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped NIN
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26259
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped DRG
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26260
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped SMN
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26261
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped BLU
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26262
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped COR
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26263
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped PUP
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26264
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped DNC
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26265
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped SCH
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26266
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped GEO
UPDATE char_inventory SET extra = X'0203019A449817488E483648000000000000000000000000'
 WHERE character_id = 1 AND item_id = 26267
   AND EXISTS (SELECT 1 FROM char_equip e WHERE e.character_id = char_inventory.character_id AND e.container = char_inventory.container AND e.slot = char_inventory.slot);  -- equipped RUN

INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26246, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WAR tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26246, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WAR pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26246, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WAR mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26246, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WAR maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26246, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WAR dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26246, X'020302D851981F4827483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WAR enmity
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26246, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WAR ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26246, X'0203029A4498024A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WAR ws_vit
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26247, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- MNK tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26247, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- MNK pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26247, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- MNK mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26247, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- MNK maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26247, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- MNK dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26247, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- MNK ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26247, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- MNK ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26248, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WHM tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26248, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WHM pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26248, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WHM mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26248, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WHM maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26248, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WHM dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26248, X'0203059A5098054A49493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WHM cure
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26248, X'02030AD8509809988C483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WHM fc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26248, X'0203059A5098234828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WHM macc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26248, X'0203059A4498054A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- WHM ws_mnd
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26249, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLM tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26249, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLM pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26249, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLM mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26249, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLM maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26249, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLM dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26249, X'02030AD8509809988C483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLM fcmp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26249, X'0203049A5098044A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLM mabws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26249, X'0203049A5098234828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLM macc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26249, X'0203049A5098044A85483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLM nuke
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'0203059A5098054A49493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM cure
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'02030AD8509809988C483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM fc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'0203059A5098054A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM mabws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'0203049A5098234828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM macc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'0203049A5098044A85483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM nuke
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'0203059A4498054A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM ws_mnd
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26250, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RDM ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26251, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- THF tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26251, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- THF pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26251, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- THF mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26251, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- THF maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26251, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- THF dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26251, X'0203019A4498014A92483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- THF dw
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26251, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- THF ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26252, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PLD dd
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26252, X'020302D85198254827486B21000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PLD block
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26252, X'0203059A5098054A49493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PLD cure
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26252, X'02030AD8509809988C483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PLD fc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26252, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PLD ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26252, X'0203059A4498054A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PLD ws_mnd
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26252, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PLD ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'020302D851981F4827483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK enmity
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'02030AD8509809988C483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK fc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'0203049A5098234828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK macc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'0203049A5098044A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK ws_int
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26253, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRK ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26254, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BST tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26254, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BST pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26254, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BST mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26254, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BST maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26254, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BST dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26254, X'0203059A5098054A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BST mabws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26254, X'02037D986A9864486F487020000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BST pet_dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26254, X'02037C986B486F4870200000000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BST pet_tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26254, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BST ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26255, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BRD tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26255, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BRD pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26255, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BRD mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26255, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BRD maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26255, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BRD dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26255, X'0203069A4498064A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BRD chrws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26255, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BRD dexws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26255, X'0203069A509823488C484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BRD maccfc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26256, X'0203039A4598034A8E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RNG ranged_tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26256, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RNG pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26256, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RNG mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26256, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RNG maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26256, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RNG dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26256, X'0203039A5098034A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RNG mabws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26256, X'0203039A4598034AD3483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RNG snapshot
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26256, X'0203039A4498034A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RNG ws_agi
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26257, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SAM tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26257, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SAM pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26257, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SAM mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26257, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SAM maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26257, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SAM dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26257, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SAM ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'0203019A4498014A92483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN dw
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'020302D850981F488C483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN fc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'0203049A5098044A85483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN ninjutsu
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'0203039A4498034A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN ws_agi
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26258, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- NIN ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26259, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRG tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26259, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRG pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26259, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRG mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26259, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRG maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26259, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRG dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26259, X'02037D986A9864486F487020000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRG pet_dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26259, X'02037D98509864486F487020000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRG pet_mab
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26259, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRG ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26259, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DRG ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'02030AD8509809988C483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN fc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'0203049A5098044A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN mabws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'0203059A5098234828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN macc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'02037D986A9864486F487020000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN pet_dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'02037D98509864486F487020000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN pet_mab
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26260, X'02037C986B486F4870200000000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SMN pet_tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'0203039A51981F488C481F70000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU evafc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'0203059A5098054A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU mabws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'0203049A5098234828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU macc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'0203049A5098044A85483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU nuke
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'0203059A4498054A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU ws_mnd
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26261, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- BLU ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'0203039A4598034A8E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR ranged_tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'0203039A5098034A85483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR mab_agi
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'0203039A5098034A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR mabws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'0203069A5098064A28483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR roll
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'0203039A4598034AD3483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR snapshot
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26262, X'0203039A4498034A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- COR ws_agi
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'02037D986A9864486F487020000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP pet_dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'02037D98509864486F487020000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP pet_mab
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'02037C986B486F4870200000000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP pet_tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26263, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- PUP ws_str
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26264, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DNC tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26264, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DNC pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26264, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DNC mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26264, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DNC maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26264, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DNC dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26264, X'0203019A4498014A92483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DNC dw
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26264, X'0203019A4498014A4A493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DNC waltz
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26264, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- DNC ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'0203059A5098054A49493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH cure
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'02030AD8509809988C483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH fc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'0203049A5098044A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH mabws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'0203049A5098234828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH macc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26265, X'0203049A5098044A85483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- SCH nuke
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26266, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- GEO tp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26266, X'020302D851981F4828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- GEO pdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26266, X'020302D85198254828483748000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- GEO mdt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26266, X'020302D85198019828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- GEO maxhp
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26266, X'020302D851981F4828484720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- GEO dt
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26266, X'02030AD8509809988C483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- GEO fc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26266, X'0203049A5098044A47493648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- GEO mabws
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26266, X'0203049A5098234828483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- GEO macc
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26266, X'0203049A5098044A85483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- GEO nuke
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26267, X'0203019A449817488E483648000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RUN dd
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26267, X'020302D851981F4827483548000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RUN sird
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26267, X'020302D851981F482748C025000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RUN tank
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26267, X'0203019A4498014A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RUN ws_dex
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26267, X'0203059A4498054A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RUN ws_mnd
INSERT OR IGNORE INTO char_locker (character_id, item_id, extra, quantity) SELECT 1, 26267, X'0203009A4498004A47494720000000000000000000000000', 1 WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);  -- RUN ws_str
