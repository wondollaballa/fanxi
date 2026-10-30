"""The weapon skills that only some jobs may use.

``weapon_skills.skill_level`` says when a skill becomes available, not who may use it.
Ordinary weapon skills are open to every job with the weapon type and skill value, so a
COR with Sword 350 can use Savage Blade.  The relic, mythic, empyrean and merit rows are
different: retail gates them on the **main job**, and the same rule also decides what the
client's Weapon Skills menu may list.  A Corsair with a gun can use Wildfire and Leaden
Salute but not Coronach or Trueflight; a Paladin with a sword can use Atonement and
Knights of Round but a Corsair cannot.

The server's 0x0AC list is built from ``ZoneSession.equipped_weapon_skills()`` and the
``/ws`` action handler checks that same list, so the table belongs on the server.  The
control addon's HUD is fed by the 0x0AC command list and therefore follows without a
second copy of these rules.

The value is the client's job bitmask: bit 0 WAR, bit 1 MNK, ... bit 21 RUN.  An id
that is absent is unrestricted.  That default covers the ordinary skill-value skills,
the custom all-job Prime skills (their weapon's own job mask already limits them) and
the Campaign Battle skills (dropped by ``equipped_weapon_skills`` separately).
"""
from __future__ import annotations

from . import skills

# The client's job ids are 1..22, in the same order as the item job bitmask.
JOB_BITS = {name.upper(): 1 << (job - 1) for job, name in skills.JOB_KEYS.items()}


def job_mask(*jobs: str) -> int:
    """The bitmask for a list of job abbreviations, e.g. ``job_mask("RNG", "COR")``."""
    mask = 0
    for job in jobs:
        mask |= JOB_BITS[job]
    return mask


# --- relic / mythic / empyrean / quested weapon skills ------------------------------------
#
# These rows carry skill_level 0 in the table because the skill is not learned from a
# skill value.  Fanxi still offers them once the weapon skill is mastered (350+), as the
# existing design promises, but only to a main job that can actually wield the weapon the
# skill belongs to.
WEAPON_SKILL_JOBS: dict[int, int] = {
    10: job_mask("MNK"),                         # Final Heaven (Spharai)
    11: job_mask("MNK"),                         # Ascetics Fury (Glanzfaust)
    12: job_mask("PUP"),                         # Stringing Pummel (Kenkonken)
    14: job_mask("MNK", "PUP"),                  # Victory Smite (Verethragna)
    26: job_mask("BRD", "RDM", "THF"),           # Mercy Stroke (Mandau)
    27: job_mask("THF"),                         # Mandalic Stab (Vajra)
    28: job_mask("BRD"),                         # Mordant Rime (Carnwenhan)
    29: job_mask("DNC"),                         # Pyrrhic Kleos (Terpsichore)
    31: job_mask("BRD", "DNC", "THF"),           # Rudra's Storm (Twashtar)
    43: job_mask("PLD", "RDM", "BLU"),           # Knights of Round (Excalibur/Corbenic)
    44: job_mask("RDM"),                         # Death Blossom (Murgleis)
    45: job_mask("PLD"),                         # Atonement (Burtgang)
    46: job_mask("BLU"),                         # Expiacion (Tizona)
    57: job_mask("DRK", "PLD", "WAR"),           # Scourge (Ragnarok)
    59: job_mask("DRK", "PLD"),                  # Torcleaver (Caladbolg)
    61: job_mask("RUN"),                         # Dimidiation (Epeolatry)
    73: job_mask("BST"),                         # Onslaught (Guttler)
    74: job_mask("BST"),                         # Primal Rend (Aymur)
    76: job_mask("BST", "WAR"),                  # Cloudsplitter (Farsha)
    89: job_mask("WAR"),                         # Metatron Torment (Bravura)
    90: job_mask("WAR"),                         # King's Justice (Conqueror)
    92: job_mask("WAR"),                         # Ukko's Fury (Ukonvasara)
    105: job_mask("DRK"),                        # Catastrophe (Apocalypse)
    106: job_mask("DRK"),                        # Insurgency (Liberator)
    108: job_mask("DRK"),                        # Quietus (Redemption)
    121: job_mask("DRG"),                        # Geirskogul (Gungnir)
    122: job_mask("DRG"),                        # Drakesbane (Ryunohige)
    124: job_mask("DRG"),                        # Camlann's Torment (Rhongomiant)
    137: job_mask("NIN"),                        # Blade: Metsu (Kikoku)
    138: job_mask("NIN"),                        # Blade: Kamu (Nagi)
    140: job_mask("NIN"),                        # Blade: Hi (Kannagi)
    153: job_mask("SAM"),                        # Tachi: Kaiten (Amanomurakumo)
    154: job_mask("SAM"),                        # Tachi: Rana (Kogarasumaru)
    156: job_mask("SAM"),                        # Tachi: Fudo (Masamune)
    170: job_mask("WHM"),                        # Randgrith (Mjollnir)
    171: job_mask("WHM"),                        # Mystic Boon (Yagrush)
    173: job_mask("WHM"),                        # Dagan (Yagrush)
    175: job_mask("GEO"),                        # Exudation (Idris)
    185: job_mask("BLM", "SMN"),                 # Gate of Tartarus (Claustrum)
    186: job_mask("BLM"),                        # Vidohunir (Laevateinn)
    187: job_mask("SMN"),                        # Garland of Bliss (Nirvana)
    188: job_mask("SCH"),                        # Omniscience (Tupsimati)
    190: job_mask("BLM", "SCH", "SMN"),           # Myrkr (Hvergelmir)
    200: job_mask("RNG", "SAM"),                 # Namas Arrow (Yoichinoyumi)
    202: job_mask("RNG"),                        # Jishnu's Radiance (Gandiva)
    216: job_mask("RNG"),                        # Coronach (Annihilator)
    217: job_mask("RNG"),                        # Trueflight (Gastraphetes)
    218: job_mask("COR"),                        # Leaden Salute (Death Penalty)
    220: job_mask("RNG", "COR"),                 # Wildfire (Armageddon)
    225: job_mask("BLU", "PLD", "RDM"),          # Chant du Cygne (Almace)

    # --- merit weapon skills -----------------------------------------------------------
    # These are not tied to one job's relic/mythic weapon: the merit ranks are
    # character-wide, and BGWiki lists a wider main-job set for each one.  The level-96
    # (357 skill) requirement is already in the weapon_skills row; this table adds the
    # jobs that may actually press the button.
    15: job_mask("MNK", "PUP"),                  # Shijin Spiral
    224: job_mask("WAR", "RDM", "THF", "BST", "BRD", "RNG", "NIN", "COR", "DNC"),
                                                 # Exenterator
    226: job_mask("WAR", "RDM", "PLD", "DRK", "SAM", "BLU", "COR", "RUN"),
                                                 # Requiescat
    60: job_mask("WAR", "PLD", "DRK", "RUN"),    # Resolution
    77: job_mask("WAR", "DRK", "BST", "RNG", "RUN"),
                                                 # Ruinator
    93: job_mask("WAR", "DRK", "RUN"),           # Upheaval
    109: job_mask("WAR", "DRK", "BST"),          # Entropy
    125: job_mask("WAR", "SAM", "DRG"),          # Stardiver
    141: job_mask("NIN"),                        # Blade: Shun
    157: job_mask("SAM"),                        # Tachi: Shoha
    174: job_mask("WAR", "MNK", "WHM", "BLM", "PLD", "SMN", "BLU", "SCH",
                  "GEO", "RUN"),                 # Realmrazer
    191: job_mask("WAR", "MNK", "WHM", "BLM", "PLD", "DRG", "SMN", "BRD",
                  "SCH", "GEO"),                 # Shattersoul
    203: job_mask("RNG", "SAM"),                 # Apex Arrow
    221: job_mask("THF", "RNG", "COR"),          # Last Stand
}


def mask_for(ws_id: int) -> int:
    """The job mask for one weapon skill; 0 means every job may use it."""
    try:
        return WEAPON_SKILL_JOBS.get(int(ws_id), 0)
    except (TypeError, ValueError):
        return 0


def allowed(ws_id: int, main_job: int) -> bool:
    """Whether the player's main job may use one weapon skill.

    A skill without a row is unrestricted.  A missing/zero main job is treated as
    unrestricted too, so a partial login record does not blank the whole menu before
    the job block arrives.
    """
    mask = mask_for(ws_id)
    try:
        job = int(main_job)
    except (TypeError, ValueError):
        return True
    # A custom job (the reserved id 23) has no retail restriction to apply; the client
    # only carries bits 0..21.
    if mask == 0 or job < 1 or job > 22:
        return True
    return bool(mask & (1 << (job - 1)))
