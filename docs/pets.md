# Pets

Fanxi has a small pet foundation on top of the entity model the Trusts already use.

## What exists

- **Call Beast** (BST) spawns a Tiger familiar.
- **Call Wyvern** (DRG) spawns a wyvern.
- **Activate** (PUP) spawns an automaton.
- **Summon** spells spawn their avatar server-side (Carbuncle, Fenrir, Ifrit, Titan,
  Leviathan, Garuda, Shiva, Ramuh, Diabolos, Alexander, Odin).  Carbuncle and Ifrit are
  verified in the client, including the Summoner main-job UI.
- **Release / Dismiss / Deactivate** remove the active pet.
- **Fight / Sic / Ready** put the pet into fight mode; **Heel** follows; **Stay** holds position.
- Pets follow their owner, close on the owner's engaged target, swing with the existing
  combat roll, and pass half their damage as owner hate.
- The three models come from the retail pet pools: Tiger familiar, player wyvern and
  automaton.  The spawnable name/model block is the same one Trusts use, so the client
  renders the pet and its name correctly.
- Job-point rows feeding pet stats: BST Pet Accuracy/Familiar/Pet Attack Speed/Ready,
  DRG Wyvern Max HP/Attr Increase, PUP Automaton Max HP/MP, SMN avatar accuracy/magic
  accuracy/physical and magic damage.
- **Reward/Repair/Spirit Link** heal the active pet; **Elemental Siphon** and **Mana Cede**
  restore MP; **Blood Pact Rage/Ward** act through the avatar.
- Pet support statuses: Unleash, Spur, Overdrive, Astral Flow, Astral Conduit, Avatar's
  Favor.

## Not yet built

- Astral Flow/Astral Conduit, Avatar's Favor, Elemental Siphon, Mana Cede and Blood Pact
  damage; avatars currently follow and auto-attack only.
- BST charm/charm-success, Reward, Ready/Sic ability damage, pet enmity and Run Wild.
- Wyvern breath/restoring breath, Spirit Link and Deep Breathing.
- Automaton frames, attachments, maneuver burden, Repair and Overdrive.
- Pet status icons and the full pet-command submenu.

Those systems are required before the remaining pet-specific job-point rows can be
applied. This foundation is deliberately limited to the shared follow/attack model.
