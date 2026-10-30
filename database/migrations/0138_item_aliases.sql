-- Alternate item names for the Armory search.
--
-- The retail client caps item names at 15 characters, so several pieces use a
-- shortened name even though the set (and players) call them by the full name.
-- Keep the client name as the canonical `items.name` and put the long spelling in
-- this table; the Armory search matches either spelling but still returns one row.

CREATE TABLE IF NOT EXISTS item_aliases (
    item_id INTEGER NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    alias   TEXT    NOT NULL COLLATE NOCASE,
    PRIMARY KEY (item_id, alias)
);

CREATE INDEX IF NOT EXISTS item_aliases_alias
    ON item_aliases(alias COLLATE NOCASE);

-- Mousai +1 body/legs/feet use "Mou." in the client because the full name is
-- longer than the item-name field.  The head and hands already use "Mousai".
INSERT OR IGNORE INTO item_aliases (item_id, alias) VALUES
    (25969, 'Mousai Crackows +1'),
    (25902, 'Mousai Seraweels +1'),
    (26538, 'Mousai Manteel +1');

-- The other two pieces fit the client's field, so their abbreviated spellings are
-- the aliases.
INSERT OR IGNORE INTO item_aliases (item_id, alias) VALUES
    (25989, 'Mou. Gages +1'),
    (25562, 'Mou. Turban +1');
