-- Steal needs a per-monster item table.  This is deliberately small: only the
-- common starter families have a steal entry, so Steal succeeds where retail data is
-- known and reports a failed steal elsewhere instead of inventing loot.
CREATE TABLE IF NOT EXISTS monster_steal_items (
    monster_template_id INTEGER NOT NULL REFERENCES monster_templates(id) ON DELETE CASCADE,
    item_id             INTEGER NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    weight              INTEGER NOT NULL DEFAULT 1 CHECK (weight > 0),
    PRIMARY KEY (monster_template_id, item_id)
);

INSERT OR IGNORE INTO monster_steal_items (monster_template_id, item_id, weight)
SELECT id, 4358, 1 FROM monster_templates WHERE name = 'Wild Rabbit';   -- Hare Meat
INSERT OR IGNORE INTO monster_steal_items (monster_template_id, item_id, weight)
SELECT id, 640, 1 FROM monster_templates WHERE name = 'Tunnel Worm';    -- Copper Ore
