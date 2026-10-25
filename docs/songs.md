# Bard songs

Fanxi now has a basic playable bard-song layer.

## What exists

- The spell table already carried the bard songs; they now use their real family status
  icons and durations.
- Songs land on the caster and nearby party members (10-yalm party radius), each with
  its own action and status packet.
- Song values:
  - Minne: Defense, per tier
  - Minuet / Mambo: Attack, per tier
  - Madrigal: Accuracy
  - March: magic Haste
  - Ballad: Refresh
  - Paeon: Regen
  - Requiem: damage-over-time
  - Prelude: Ranged Accuracy
  - Carol: Magic Defense
- Job-point rows applied: Minne/Minuet potency (+20 at rank 20), Song Accuracy, Soul
  Voice and Pianissimo Fast Cast.
- **Valor Minuet** was verified in game: the cast finishes and the caster gains Minuet.

## Still missing

- Requiem potency, Lullaby duration, and the full song-accuracy/instrument model.
- Tenuto/Marcato/Clarion Call duration handling and the remaining BRD JP rows.
- Song recast/party-alliance nuances and instrument skill.
