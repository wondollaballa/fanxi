-- Fixed-model NPCs use the exact model id in their SQL look, not a race guess.
UPDATE world_npcs SET model=810 WHERE zone=246 AND size=0 AND name='Zuah Lepahnyu';
UPDATE world_npcs SET model=99  WHERE zone=246 AND size=0 AND name='Shami';
UPDATE world_npcs SET model=85  WHERE zone=246 AND size=0 AND name='Pyropox';
UPDATE world_npcs SET model=85  WHERE zone=246 AND size=0 AND name='Squintrox Dryeyes';
UPDATE world_npcs SET model=860 WHERE zone=246 AND size=0 AND name='Garridan';
UPDATE world_npcs SET model=206 WHERE zone=246 AND size=0 AND name='Caffie';
UPDATE world_npcs SET model=85  WHERE zone=246 AND size=0 AND name='Kindlix';
