-- The 0x028 action animation field uses *spell* animation ids; 44 is Protect, not
-- the entity's Synth pose.  Mix's direct friendly action should not play a Protect
-- cast.  Recipe synthesis uses the 0x00D/0x037 entity animation 44 instead.
UPDATE job_abilities SET animation = 0 WHERE id = 396;
