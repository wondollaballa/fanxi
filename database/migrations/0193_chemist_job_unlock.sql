-- Chemist (job 23) for characters that already exist (migration 193).
--
-- 0192 widened the job columns in `characters`, but a job change reads
-- `character_jobs`, and every existing character has rows for jobs 1..22 only.
-- `//job chm` (and the `!job` form the host sends) therefore answered
-- "That job is not available yet."  A new character is given the row for the job
-- it picks in `_insert_character()`, so this is only the backfill.
--
-- This server caps the jobs it grants: migration 0027 inserted every job at 99 with
-- Master Level 50.  Give the Chemist the same level and Master Level as the best
-- job the character already has; a character with no job rows at all gets the cap,
-- which matches that policy.

INSERT OR IGNORE INTO character_jobs (character_id, job, level, master_level)
SELECT c.id, 23, COALESCE(MAX(j.level), 99), COALESCE(MAX(j.master_level), 50)
FROM characters c
LEFT JOIN character_jobs j ON j.character_id = c.id
GROUP BY c.id;
