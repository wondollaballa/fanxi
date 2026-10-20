-- Fanxi database schema, migration 1.
-- SQLite 3.35+ (the Python standard library's sqlite3 is fine).
-- Times are ISO-8601 UTC strings, written by the server.

CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL COLLATE NOCASE UNIQUE,
    email           TEXT    COLLATE NOCASE,
    password_hash   TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'suspended', 'banned')),
    role            TEXT    NOT NULL DEFAULT 'player'
                            CHECK (role IN ('player', 'admin')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    last_login_at   TEXT
);

CREATE TABLE IF NOT EXISTS api_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    token_hash  TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL,
    expires_at  TEXT    NOT NULL,
    revoked_at  TEXT,
    ip          TEXT,
    user_agent  TEXT
);
CREATE INDEX IF NOT EXISTS api_sessions_account ON api_sessions(account_id);

-- One row per in-game login. session_hash is the 16 bytes the client uses for the
-- login-data and lobby connections; it is never stored in plaintext anywhere else.
CREATE TABLE IF NOT EXISTS game_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    session_hash BLOB    NOT NULL UNIQUE,
    created_at   TEXT    NOT NULL,
    expires_at   TEXT    NOT NULL,
    last_seen_at TEXT,
    ip           TEXT
);
CREATE INDEX IF NOT EXISTS game_sessions_account ON game_sessions(account_id);

-- Single-use hand-off from the launcher's HTTP session to host64's auth exchange.
CREATE TABLE IF NOT EXISTS login_tokens (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    token_hash TEXT    NOT NULL UNIQUE,
    created_at TEXT    NOT NULL,
    expires_at TEXT    NOT NULL,
    used_at    TEXT,
    ip         TEXT
);
CREATE INDEX IF NOT EXISTS login_tokens_account ON login_tokens(account_id);

CREATE TABLE IF NOT EXISTS worlds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    host        TEXT    NOT NULL,
    auth_port   INTEGER NOT NULL DEFAULT 54231,
    data_port   INTEGER NOT NULL DEFAULT 54230,
    view_port   INTEGER NOT NULL DEFAULT 54001,
    zone_port   INTEGER NOT NULL DEFAULT 54230,
    search_port INTEGER NOT NULL DEFAULT 54002,
    status      TEXT    NOT NULL DEFAULT 'online'
                        CHECK (status IN ('online', 'maintenance', 'offline')),
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id     INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    slot           INTEGER NOT NULL DEFAULT 1,
    char_id        INTEGER NOT NULL UNIQUE,
    name           TEXT    NOT NULL COLLATE NOCASE UNIQUE,
    race           INTEGER NOT NULL CHECK (race BETWEEN 1 AND 8),
    face           INTEGER NOT NULL DEFAULT 1 CHECK (face BETWEEN 1 AND 8),
    size           INTEGER NOT NULL DEFAULT 1 CHECK (size BETWEEN 0 AND 2),
    nation         INTEGER NOT NULL DEFAULT 0 CHECK (nation BETWEEN 0 AND 2),
    main_job       INTEGER NOT NULL DEFAULT 1 CHECK (main_job BETWEEN 1 AND 22),
    sub_job        INTEGER NOT NULL DEFAULT 0 CHECK (sub_job BETWEEN 0 AND 22),
    main_level     INTEGER NOT NULL DEFAULT 1 CHECK (main_level BETWEEN 1 AND 99),
    sub_level      INTEGER NOT NULL DEFAULT 0 CHECK (sub_level BETWEEN 0 AND 99),
    hp             INTEGER NOT NULL DEFAULT 1500,
    mp             INTEGER NOT NULL DEFAULT 0,
    speed          INTEGER NOT NULL DEFAULT 50,
    zone           INTEGER NOT NULL DEFAULT 246,
    pos_x          REAL    NOT NULL DEFAULT -87.0,
    pos_y          REAL    NOT NULL DEFAULT 12.0,
    pos_z          REAL    NOT NULL DEFAULT 116.0,
    rot            INTEGER NOT NULL DEFAULT 128,
    head           INTEGER NOT NULL DEFAULT 0,
    body           INTEGER NOT NULL DEFAULT 8,
    hands          INTEGER NOT NULL DEFAULT 8,
    legs           INTEGER NOT NULL DEFAULT 8,
    feet           INTEGER NOT NULL DEFAULT 8,
    main           INTEGER NOT NULL DEFAULT 0,
    sub            INTEGER NOT NULL DEFAULT 0,
    ranged         INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    last_played_at TEXT,
    UNIQUE (account_id, slot)
);
CREATE INDEX IF NOT EXISTS characters_account ON characters(account_id);

CREATE TABLE IF NOT EXISTS zones (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    pos_x       REAL    NOT NULL DEFAULT 0,
    pos_y       REAL    NOT NULL DEFAULT 0,
    pos_z       REAL    NOT NULL DEFAULT 0,
    rot         INTEGER NOT NULL DEFAULT 0,
    music_day   INTEGER NOT NULL DEFAULT 0,
    music_night INTEGER NOT NULL DEFAULT 0,
    music_solo  INTEGER NOT NULL DEFAULT 0,
    music_party INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS zone_lines (
    id      INTEGER PRIMARY KEY,
    rect    INTEGER NOT NULL UNIQUE,
    to_zone INTEGER NOT NULL,
    x       REAL    NOT NULL,
    y       REAL    NOT NULL,
    z       REAL    NOT NULL,
    rot     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS news (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    slug         TEXT    NOT NULL UNIQUE,
    title        TEXT    NOT NULL,
    body         TEXT    NOT NULL,
    published_at TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS releases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    channel      TEXT    NOT NULL DEFAULT 'stable',
    platform     TEXT    NOT NULL,
    version      TEXT    NOT NULL,
    url          TEXT    NOT NULL,
    sha256       TEXT    NOT NULL,
    size         INTEGER NOT NULL DEFAULT 0,
    notes        TEXT    NOT NULL DEFAULT '',
    mandatory    INTEGER NOT NULL DEFAULT 0 CHECK (mandatory IN (0, 1)),
    published_at TEXT    NOT NULL,
    UNIQUE (channel, platform, version)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    action     TEXT    NOT NULL,
    detail     TEXT    NOT NULL DEFAULT '',
    ip         TEXT,
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_log_created ON audit_log(created_at);
