-- Per-account GearSwap libraries.  Until now the Gear page edited the checkout's
-- gearswap/<JOB>.lua directly, so one character's edit changed the defaults for every
-- account on the server.  Each account now owns its own copy of every job library; a
-- new account is seeded from the template account (Onedough by default), which in turn
-- falls back to gearswap/<JOB>.lua when it has no saved copy yet.
CREATE TABLE IF NOT EXISTS gearswap_libraries (
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    job        TEXT    NOT NULL,
    name       TEXT    NOT NULL DEFAULT '',
    source     TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    PRIMARY KEY (account_id, job)
);
CREATE INDEX IF NOT EXISTS gearswap_libraries_account ON gearswap_libraries(account_id);
