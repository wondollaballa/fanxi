-- Fanxi world content and character progression, migration 2.
-- The shape follows the concepts a full FINAL FANTASY XI world server needs: NPCs, monster templates,
-- spawn points, items/inventory and quest state. The rows themselves are Fanxi's own starter
-- content, not imported from another server.

ALTER TABLE characters ADD COLUMN hp_current INTEGER NOT NULL DEFAULT 1500;
ALTER TABLE characters ADD COLUMN mp_current INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN exp INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN gil INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN playtime_seconds INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN death_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN home_zone INTEGER NOT NULL DEFAULT 246;
ALTER TABLE characters ADD COLUMN home_x REAL NOT NULL DEFAULT -87.0;
ALTER TABLE characters ADD COLUMN home_y REAL NOT NULL DEFAULT 12.0;
ALTER TABLE characters ADD COLUMN home_z REAL NOT NULL DEFAULT 116.0;
ALTER TABLE characters ADD COLUMN home_rot INTEGER NOT NULL DEFAULT 128;

UPDATE characters SET hp_current = hp WHERE hp_current = 1500;
UPDATE characters SET mp_current = mp WHERE mp_current = 0;

-- A placed NPC: name, look, position, and the script that drives its interaction.
CREATE TABLE IF NOT EXISTS world_npcs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zone          INTEGER NOT NULL,
    name          TEXT    NOT NULL,
    pos_x         REAL    NOT NULL DEFAULT 0,
    pos_y         REAL    NOT NULL DEFAULT 0,
    pos_z         REAL    NOT NULL DEFAULT 0,
    rot           INTEGER NOT NULL DEFAULT 0,
    model         INTEGER NOT NULL DEFAULT 50,
    size          INTEGER NOT NULL DEFAULT 0,
    name_prefix   INTEGER NOT NULL DEFAULT 0,
    namevis       INTEGER NOT NULL DEFAULT 0,
    status        INTEGER NOT NULL DEFAULT 0,
    flags         INTEGER NOT NULL DEFAULT 0,
    speed         INTEGER NOT NULL DEFAULT 50,
    animation     INTEGER NOT NULL DEFAULT 0,
    triggerable   INTEGER NOT NULL DEFAULT 1 CHECK (triggerable IN (0, 1)),
    widescan      INTEGER NOT NULL DEFAULT 1 CHECK (widescan IN (0, 1)),
    script        TEXT    NOT NULL DEFAULT '',
    content_tag   TEXT
);
CREATE INDEX IF NOT EXISTS world_npcs_zone ON world_npcs(zone);

-- Default lines for an NPC with no scripted response.
CREATE TABLE IF NOT EXISTS npc_lines (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    npc_id   INTEGER NOT NULL REFERENCES world_npcs(id) ON DELETE CASCADE,
    line_no  INTEGER NOT NULL DEFAULT 0,
    text     TEXT    NOT NULL,
    UNIQUE (npc_id, line_no)
);

-- The shared stats/look/behaviour of a kind of monster.
CREATE TABLE IF NOT EXISTS monster_templates (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    model            INTEGER NOT NULL DEFAULT 0,
    size             INTEGER NOT NULL DEFAULT 0,
    level_min        INTEGER NOT NULL DEFAULT 1,
    level_max        INTEGER NOT NULL DEFAULT 1,
    hp               INTEGER NOT NULL DEFAULT 30,
    mp               INTEGER NOT NULL DEFAULT 0,
    attack           INTEGER NOT NULL DEFAULT 5,
    defense          INTEGER NOT NULL DEFAULT 0,
    accuracy         INTEGER NOT NULL DEFAULT 75,
    evasion          INTEGER NOT NULL DEFAULT 10,
    attack_delay_ms  INTEGER NOT NULL DEFAULT 3000,
    aggro            INTEGER NOT NULL DEFAULT 0 CHECK (aggro IN (0, 1)),
    links            INTEGER NOT NULL DEFAULT 0 CHECK (links IN (0, 1)),
    roam_radius      REAL    NOT NULL DEFAULT 0,
    respawn_seconds  INTEGER NOT NULL DEFAULT 30,
    name_prefix      INTEGER NOT NULL DEFAULT 0,
    behavior         TEXT    NOT NULL DEFAULT 'roam',
    content_tag      TEXT
);

-- One placed monster. Multiple spawn points can share a template.
CREATE TABLE IF NOT EXISTS monster_spawns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id         INTEGER NOT NULL REFERENCES monster_templates(id) ON DELETE CASCADE,
    zone            INTEGER NOT NULL,
    name            TEXT,
    pos_x           REAL    NOT NULL DEFAULT 0,
    pos_y           REAL    NOT NULL DEFAULT 0,
    pos_z           REAL    NOT NULL DEFAULT 0,
    rot             INTEGER NOT NULL DEFAULT 0,
    level           INTEGER,
    respawn_seconds INTEGER,
    enabled         INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
);
CREATE INDEX IF NOT EXISTS monster_spawns_zone ON monster_spawns(zone);

CREATE TABLE IF NOT EXISTS items (
    item_id      INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    stack        INTEGER NOT NULL DEFAULT 1,
    usable       INTEGER NOT NULL DEFAULT 1 CHECK (usable IN (0, 1)),
    equip_slot   TEXT    NOT NULL DEFAULT '',
    level        INTEGER NOT NULL DEFAULT 1,
    description  TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS char_inventory (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    container    INTEGER NOT NULL DEFAULT 0,
    slot         INTEGER NOT NULL DEFAULT 0,
    item_id      INTEGER NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (character_id, container, slot)
);

CREATE TABLE IF NOT EXISTS quests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_key       TEXT    NOT NULL UNIQUE,
    name            TEXT    NOT NULL,
    description     TEXT    NOT NULL DEFAULT '',
    reward_gil      INTEGER NOT NULL DEFAULT 0,
    reward_item_id  INTEGER,
    reward_item_qty INTEGER NOT NULL DEFAULT 0,
    required_template_id INTEGER REFERENCES monster_templates(id) ON DELETE SET NULL,
    required_kills  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS char_quests (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    quest_id     INTEGER NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    state        TEXT    NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'complete')),
    progress     INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT    NOT NULL,
    PRIMARY KEY (character_id, quest_id)
);

-- The NPC look block (the 20-byte GrapIDTbl the client draws an NPC with) is read by the
-- zone loader and written by later migrations; keep the column in the base schema.
ALTER TABLE world_npcs ADD COLUMN look_hex TEXT NOT NULL DEFAULT '';
