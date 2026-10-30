-- Dispense pouches and quivers (RMEA waist gear).
--
-- These are charged equipment, not consumables: using one adds a stack of ammo and
-- starts its reuse timer while the piece stays equipped.  The client reads the charge
-- count and the next-use timestamp from the 24-byte extdata block on 0x020, so the
-- timer lives in char_inventory.extra on the pouch's own row.
--
-- Values are BG Wiki's: 1 charge, 10 s use delay, 3600 s reuse, 2 s activation.
-- The four bullet and four arrow/bolt pieces are the same item family.

CREATE TABLE IF NOT EXISTS item_dispense (
    item_id      INTEGER PRIMARY KEY REFERENCES items(item_id) ON DELETE CASCADE,
    ammo_id      INTEGER NOT NULL REFERENCES items(item_id),
    quantity     INTEGER NOT NULL DEFAULT 99 CHECK (quantity > 0),
    max_charges  INTEGER NOT NULL DEFAULT 1 CHECK (max_charges > 0),
    use_delay    INTEGER NOT NULL DEFAULT 10,
    reuse_delay  INTEGER NOT NULL DEFAULT 3600,
    cast_time    INTEGER NOT NULL DEFAULT 2,
    animation    INTEGER NOT NULL DEFAULT 0
);

UPDATE items SET usable = 1
 WHERE item_id IN (26343, 26344, 26345, 26346, 26347, 26348, 26349, 26350);

INSERT OR REPLACE INTO item_dispense
    (item_id, ammo_id, quantity, max_charges, use_delay, reuse_delay, cast_time, animation)
VALUES
    (26343, 21299, 99, 1, 10, 3600, 2, 0),  -- Yoichi's Quiver -> Yoichi's Arrow
    (26344, 21298, 99, 1, 10, 3600, 2, 0),  -- Artemis's Quiver -> Artemis's Arrow
    (26345, 21297, 99, 1, 10, 3600, 2, 0),  -- Chrono Quiver -> Chrono Arrow
    (26346, 21311, 99, 1, 10, 3600, 2, 0),  -- Quelling B. Quiver -> Quelling Bolt
    (26347, 21327, 99, 1, 10, 3600, 2, 0),  -- Era. Bul. Pouch -> Eradicating Bullet
    (26348, 21326, 99, 1, 10, 3600, 2, 0),  -- Liv. Bul. Pouch -> Living Bullet
    (26349, 21325, 99, 1, 10, 3600, 2, 0),  -- Dev. Bul. Pouch -> Devastating Bullet
    (26350, 21296, 99, 1, 10, 3600, 2, 0);  -- Chr. Bul. Pouch -> Chrono Bullet
