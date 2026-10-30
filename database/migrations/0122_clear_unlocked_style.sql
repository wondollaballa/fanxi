-- Drop style-lock models saved while the lock was off (migration 121).
--
-- A job change used to clear only `style_lock` and leave the locked model columns
-- behind.  The client re-asserts its own lock state when logging in or zoning (C2S
-- 0x053 mode 1), so the next zone could flip the lock back on with the previous job's
-- clothing: a Dancer wearing the Scholar's look.  The server now forgets the models
-- whenever the lock turns off; this clears the leftovers already on disk.  Rows whose
-- lock is on keep their models, because that appearance is still in use.
UPDATE characters
   SET style_main = 0, style_sub = 0, style_ranged = 0,
       style_head = 0, style_body = 0, style_hands = 0,
       style_legs = 0, style_feet = 0
 WHERE style_lock = 0
   AND (style_main <> 0 OR style_sub <> 0 OR style_ranged <> 0
        OR style_head <> 0 OR style_body <> 0 OR style_hands <> 0
        OR style_legs <> 0 OR style_feet <> 0);
