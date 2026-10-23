CREATE TABLE IF NOT EXISTS character_jobs (
    character_id INTEGER NOT NULL,
    job          INTEGER NOT NULL,
    level        INTEGER NOT NULL DEFAULT 1,
    master_level INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, job)
);

INSERT OR REPLACE INTO character_jobs (character_id, job, level, master_level)
SELECT c.id, j.job, 99, 50
FROM characters c
JOIN (SELECT 1 AS job UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
      UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8
      UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12
      UNION ALL SELECT 13 UNION ALL SELECT 14 UNION ALL SELECT 15 UNION ALL SELECT 16
      UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19 UNION ALL SELECT 20
      UNION ALL SELECT 21 UNION ALL SELECT 22) j
WHERE c.name = 'Onedough';

UPDATE characters
SET main_level = 99, sub_level = 99, main_job = 1, sub_job = 1,
    hp = 9999, hp_current = 9999, mp = 9999, mp_current = 9999,
    exp = 0, gil = 999999999
WHERE name = 'Onedough';
