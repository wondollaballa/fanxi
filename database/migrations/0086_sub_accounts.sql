-- Server-owned sub-accounts.
--
-- A main account can own up to FANXI_MAX_SUBS (default 5) sub-accounts. Subs have no
-- password and no API sessions: the main account's bearer token is the only key. The
-- launcher creates them with their one character and launches them through the main.
ALTER TABLE accounts ADD COLUMN parent_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE;
ALTER TABLE accounts ADD COLUMN kind TEXT NOT NULL DEFAULT 'main'
    CHECK (kind IN ('main', 'sub'));
CREATE INDEX IF NOT EXISTS accounts_parent ON accounts(parent_id);
CREATE INDEX IF NOT EXISTS accounts_kind ON accounts(kind);

-- Keep kind and parent_id consistent even if a future writer forgets the service layer.
CREATE TRIGGER IF NOT EXISTS accounts_kind_parent_insert
BEFORE INSERT ON accounts
WHEN (NEW.kind = 'sub' AND NEW.parent_id IS NULL)
  OR (NEW.kind = 'main' AND NEW.parent_id IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'account kind and parent_id disagree');
END;

CREATE TRIGGER IF NOT EXISTS accounts_kind_parent_update
BEFORE UPDATE OF kind, parent_id ON accounts
WHEN (NEW.kind = 'sub' AND NEW.parent_id IS NULL)
  OR (NEW.kind = 'main' AND NEW.parent_id IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'account kind and parent_id disagree');
END;
