-- Per-account GearSwap/phase configuration. The launcher used browser localStorage,
-- which is per WebView profile and not part of the game's data; keep the same JSON in
-- the game DB so a mode change survives a launcher or machine restart.
CREATE TABLE IF NOT EXISTS gearswap_settings (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    config     TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
