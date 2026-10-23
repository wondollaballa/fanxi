-- Ninjutsu are paid for with tools, not MP.  The imported spell_list column carried the
-- client's tool/cost field (2553, 1179, ...), which made every ninjutsu uncastable for a
-- level 99 ninja with 404 MP.  Retail charges 0 MP for the whole skill.
UPDATE spells SET mp = 0 WHERE skill = 39;
