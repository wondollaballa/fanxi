"""Prime Weapons: the catalogue families and the physical damage-limit aftermath.

The catalogue side below maps every Sortie Prime weapon row to its family's final
iLvl 119 III form.  The Armory uses it so one search result represents the whole
family instead of four identically named stages, and so a purchase of any stage is
granted as the final form.

Retail Prime weapons grant an aftermath when their own weapon skill is used.  For every
melee and ranged Prime weapon it is a Physical Damage Limit+ buff: the pDIF cap rises by
2-8% (stage 3), 4-10% (stage 4) or 6-12% (stage 5) from 1,000 to 3,000 TP.  The potency
is linear with the TP spent, while the duration and tier are fixed by the 1,000/2,000/
3,000 TP bands:

    1,000-1,999 TP -> tier 1, 60 s
    2,000-2,999 TP -> tier 2, 120 s
    3,000 TP       -> tier 3, 180 s

TP Bonus gear and Fencer do not change either the tier or the potency: retail's aftermath
uses the TP actually spent, not the TP the skill scaled from.

Overwriting follows the same rule as Mythic/Empyrean aftermath (BG-wiki Aftermath): level
1 can overwrite itself, level 2 overwrites level 1 but not itself, and level 3 overwrites
levels 1 and 2 but not itself.  :func:`can_overwrite` encodes that rule.

Staff (Oshala) and club (Dagda) use different aftermaths (Magic Attack/Magic Damage and
Cure potency/Magic Damage).  Their full TP scaling is not published, so they are not part
of the physical table here; they keep their normal damage and no PDL buff.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import effects, modifiers as mod

TP_FLOOR = 1000
TP_MAX = 3000

# The weapon skills that belong to Prime weapons.  The item's 355 modifier names one of
# these; a relic/mythic/empyrean 355 row names a different skill and is ignored.
PRIME_WEAPON_SKILLS = frozenset({
    62,   # Fimbulvetr, Helheim
    78,   # Blitz, Spalirisos
    94,   # Disaster, Laphria
    110,  # Origin, Foenaria
    126,  # Diarmuid, Gae Buide
    142,  # Zesho Meppo, Dokoku
    159,  # Tachi: Mumei, Kusanagi
    204,  # Sarv, Pinaka
    222,  # Terminus, Earp
    231,  # Maru Kala, Varga Purnikawa
    232,  # Ruthless Stroke, Mpu Gandring
    233,  # Imperator, Caliburnus
    234,  # Dagda, Lorg Mor (special aftermath)
    235,  # Oshala, Opashoro (special aftermath)
})

# The Prime skills whose aftermath is Physical Damage Limit+.  Staff and club are the
# two exceptions described in the module docstring.
PHYSICAL_WEAPON_SKILLS = PRIME_WEAPON_SKILLS - {234, 235}

# --- catalogue families -------------------------------------------------------------------
#
# The Sortie Prime weapon upgrades in stage order.  Stage 1 is the "Prime ..." item the
# quest hands out; stages 2-5 share the final's name, and stage 5 is the iLvl 119 III
# form with the afterglow model.  Dokoku and Kusanagi have no stage-1 row in this
# catalogue, so their families start at stage 2.  The ids come from migration 125.
PRIME_STAGE_COUNT = 5

PRIME_FAMILIES: tuple[tuple[str, tuple[tuple[int, int], ...]], ...] = (
    ("Varga Purnikawa", ((1, 21531), (2, 21532), (3, 21533), (4, 21534), (5, 21535))),
    ("Mpu Gandring", ((1, 21586), (2, 21587), (3, 21588), (4, 21589), (5, 21590))),
    ("Caliburnus", ((1, 21642), (2, 21643), (3, 21644), (4, 21645), (5, 21646))),
    # The "Prime Blade" base row sits between the Helheim stage ids.
    ("Helheim", ((1, 21650), (2, 21649), (3, 21651), (4, 21652), (5, 21653))),
    ("Spalirisos", ((1, 21726), (2, 21727), (3, 21728), (4, 21729), (5, 21730))),
    ("Laphria", ((1, 21781), (2, 21782), (3, 21783), (4, 21784), (5, 21785))),
    ("Foenaria", ((1, 21833), (2, 21834), (3, 21835), (4, 21836), (5, 21837))),
    ("Gae Buide", ((1, 21887), (2, 21888), (3, 21889), (4, 21890), (5, 21891))),
    ("Dokoku", ((2, 21929), (3, 21930), (4, 21931), (5, 21932))),
    ("Kusanagi", ((2, 21983), (3, 21984), (4, 21985), (5, 21986))),
    # The "Prime Maul" base row sits between the Lorg Mor stage ids.
    ("Lorg Mor", ((1, 21999), (2, 21998), (3, 22000), (4, 22001), (5, 22002))),
    ("Opashoro", ((1, 22102), (2, 22103), (3, 22104), (4, 22105), (5, 22106))),
    ("Pinaka", ((1, 22155), (2, 22156), (3, 22157), (4, 22158), (5, 22163))),
    ("Earp", ((1, 22159), (2, 22160), (3, 22161), (4, 22162), (5, 22164))),
    ("Loughnashade", ((1, 22303), (2, 22304), (3, 22305), (4, 22306), (5, 22307))),
    ("Duban", ((1, 26491), (2, 26492), (3, 26493), (4, 26494), (5, 26495))),
)


@dataclass(frozen=True)
class PrimeForm:
    """One Prime weapon row and the final form its family upgrades to."""

    family: str
    stage: int
    item_id: int
    final_id: int

    @property
    def is_final(self) -> bool:
        return self.item_id == self.final_id


def _index_forms() -> dict[int, PrimeForm]:
    index: dict[int, PrimeForm] = {}
    for family, stages in PRIME_FAMILIES:
        final_stage, final_id = stages[-1]
        if final_stage != PRIME_STAGE_COUNT:
            raise ValueError("%s ends at stage %d, not %d"
                             % (family, final_stage, PRIME_STAGE_COUNT))
        for stage, item_id in stages:
            if item_id in index:
                raise ValueError("item %d is in two Prime weapon families" % item_id)
            index[item_id] = PrimeForm(
                family=family, stage=stage, item_id=item_id, final_id=final_id)
    return index


_FORMS = _index_forms()


def form(item_id: int) -> PrimeForm | None:
    """The Prime family row for an item, or None when it is not a Prime weapon."""
    try:
        return _FORMS.get(int(item_id))
    except (TypeError, ValueError):
        return None


def final_item_id(item_id: int) -> int | None:
    """The iLvl 119 III form of *item_id*'s family, or None for a non-Prime item."""
    entry = form(item_id)
    return entry.final_id if entry else None


def family_item_ids(item_id: int) -> tuple[int, ...]:
    """Every catalogue id in *item_id*'s Prime family, or () for a non-Prime item."""
    entry = form(item_id)
    if entry is None:
        return ()
    return tuple(other.item_id for other in _FORMS.values()
                 if other.final_id == entry.final_id)


# --- aftermath ----------------------------------------------------------------------------

# Stage -> (PDL at 1,000 TP, PDL at 3,000 TP), in percent.
PDL_RANGE = {
    3: (2, 8),
    4: (4, 10),
    5: (6, 12),
}

# The aftermath status effect is one buff id; the 1/2/3 tier only changes its icon.
AFTERMATH_ICONS = (effects.AFTERMATH_LV1, effects.AFTERMATH_LV2, effects.AFTERMATH_LV3)


@dataclass(frozen=True)
class PrimeWeapon:
    """A Prime weapon that is carrying its own weapon skill."""

    item_id: int
    ws_id: int
    # 3 = iL119, 4 = iL119 II, 5 = iL119 III.
    stage: int


@dataclass(frozen=True)
class Aftermath:
    """One aftermath grant, ready for the effect store."""

    ws_id: int
    stage: int
    tp: int
    tier: int
    potency: int
    duration: int
    icon: int

    @property
    def mods(self) -> dict[int, int]:
        return {mod.DAMAGE_LIMITP: self.potency}


def clamp_tp(tp: int) -> int:
    """The TP an aftermath reads: what was spent, not TP Bonus or Fencer."""
    return max(TP_FLOOR, min(TP_MAX, int(tp)))


def tier_at(tp: int) -> int:
    """1 for 1,000-1,999 TP, 2 for 2,000-2,999, 3 at 3,000."""
    return min(3, clamp_tp(tp) // 1000)


def potency_at(stage: int, tp: int) -> int | None:
    """The PDL percent at this stage and TP, or None for a stage with no table."""
    bounds = PDL_RANGE.get(int(stage))
    if bounds is None:
        return None
    low, high = bounds
    tp = clamp_tp(tp)
    # Linear from the 1,000 anchor to the 3,000 anchor.  Retail reports whole percents
    # and the FFXIAH 1,611-TP sample read 3%, which is the floor of the stage-3 value.
    return int(low + (high - low) * (tp - TP_FLOOR) // (TP_MAX - TP_FLOOR))


def aftermath_for(weapon: PrimeWeapon, tp: int) -> Aftermath | None:
    """The aftermath a use of this weapon's skill grants, or None if it has none."""
    if int(weapon.ws_id) not in PHYSICAL_WEAPON_SKILLS:
        return None
    potency = potency_at(weapon.stage, tp)
    if potency is None:
        return None
    tp = clamp_tp(tp)
    tier = tier_at(tp)
    return Aftermath(
        ws_id=int(weapon.ws_id), stage=int(weapon.stage), tp=tp, tier=tier,
        potency=int(potency), duration=60 * tier, icon=AFTERMATH_ICONS[tier - 1])


def can_overwrite(existing_tier: int, new_tier: int) -> bool:
    """Retail's tier lock: level 1 refreshes, levels 2 and 3 do not overwrite themselves."""
    existing_tier = int(existing_tier)
    new_tier = int(new_tier)
    if new_tier > existing_tier:
        return True
    # Level 1 can and will overwrite itself; a higher level only yields to a new level.
    return existing_tier <= 1
