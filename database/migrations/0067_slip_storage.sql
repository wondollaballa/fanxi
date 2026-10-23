-- Storage Slips keep their contents off the character entirely.  The old !locker
-- experiment used container 4, and the first !storage version used container 2; both
-- showed up as bags in the client.  Move whatever is left in those two containers into
-- char_storage, keyed by the slip that accepts the item.  Slip 0 means the item has no
-- slip (a legacy row); it is kept so !storage grab all can still return it.
CREATE TABLE IF NOT EXISTS char_storage (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_id      INTEGER NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    slip         INTEGER NOT NULL DEFAULT 0,
    stored_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (character_id, item_id)
);
CREATE INDEX IF NOT EXISTS char_storage_slip ON char_storage(character_id, slip);

INSERT INTO char_storage (character_id, item_id, quantity, slip)
SELECT ci.character_id, ci.item_id, SUM(ci.quantity), COALESCE(st.slip, 0)
FROM char_inventory ci
LEFT JOIN item_storage st ON st.item_id = ci.item_id
WHERE ci.container IN (2, 4)
GROUP BY ci.character_id, ci.item_id, COALESCE(st.slip, 0)
ON CONFLICT(character_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity;

DELETE FROM char_inventory WHERE container IN (2, 4);
