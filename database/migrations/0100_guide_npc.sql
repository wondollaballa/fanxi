-- The content import replaced Port Jeuno's hand-made NPCs and the monster templates, so the
-- quest giver is now the real NPC nearest the arrival point (GUIDE_NPC in
-- server/fanxi_server/game/content.py) and the target is a mob that actually spawns in West
-- Ronfaure.  The old Orcish Grunt template is gone from the imported table, and the foreign
-- key cleared required_template_id, which silently stopped kills from counting.
UPDATE quests
SET description = 'Cumetouflaix wants the Orcish Fodder around the West Ronfaure camp thinned out.',
    required_template_id = (
        SELECT t.id FROM monster_templates t
        JOIN monster_spawns s ON s.template_id = t.id
        WHERE t.name = 'Orcish Fodder' AND s.zone = 100
        LIMIT 1)
WHERE quest_key = 'pest_control';
