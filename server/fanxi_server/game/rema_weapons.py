"""REMA weapons: the catalogue families and their final afterglow forms.

The Armory used to list every stage of a Relic, Empyrean, Mythic or Aeonic weapon
separately.  Masamune, for example, has nine catalogue rows from level 80 to iLvl
119, and the typeahead showed all of them under the same name, so the first one --
the weakest stage -- was what Enter selected.  The shop now sells one row per
family, always the final iLvl 119 III (afterglow) form, and a purchase of any
earlier stage is upgraded to that row.

The table below maps every stage id to its family and final id.  It is derived from
the item catalogue: a family is a group of rows with the same name (ignoring the
``119 III`` suffix used by a few hand-added final forms) that contains an iLvl 119
row whose ``item_weapon.ilvl_skill`` is the final 269.  The four REMA shields and
instruments (Aegis, Ochain, Gjallarhorn, Daurdabla) have no iLvl 119 row in this
catalogue, so their highest afterglow row is listed explicitly.  Prime weapons are
excluded; :mod:`prime_weapons` owns their families.

The final id is the row with the strongest stats, the afterglow model, and then the
lowest id.  A few families have two identical final duplicates (the GearSwap grant
and the catalogue row); both ids stay in the family so either grants the same item.
"""
from __future__ import annotations

from dataclasses import dataclass

# (family, final id, every stage id in the family)
REMA_FAMILIES: tuple[tuple[str, int, tuple[int, ...]], ...] = (
    ("Aegis", 16200, (15070, 16195, 16196, 16197, 16198, 11927, 16200)),
    ("Almace", 20689,
     (19399, 19458, 19536, 19634, 19807, 19855, 20653, 20654, 20689)),
    ("Amanomurakumo", 21954,
     (18318, 18319, 18646, 18660, 18674, 19755, 19848, 21015, 21016, 21954)),
    ("Annihilator", 21267,
     (18336, 18337, 18649, 18663, 18677, 19758, 19851, 21260, 21261, 22140,
      21267)),
    ("Apocalypse", 21808,
     (18306, 18307, 18644, 18658, 18672, 19753, 19846, 20880, 20881, 21808)),
    ("Armageddon", 21269,
     (19410, 19469, 19547, 19645, 19818, 19866, 21264, 21265, 22142, 21269)),
    ("Aymur", 21751,
     (18979, 18999, 19068, 19088, 19620, 19718, 19827, 19956, 20792, 20793,
      21751)),
    ("Bravura", 21756,
     (18294, 18295, 18642, 18656, 18670, 19751, 19844, 20835, 20836, 21756)),
    ("Burtgang", 20687,
     (18977, 18997, 19066, 19086, 19618, 19716, 19825, 19954, 20649, 20650,
      20687)),
    ("Caladbolg", 21684,
     (19400, 19459, 19537, 19635, 19808, 19856, 20747, 20748, 21684)),
    ("Carnwenhan", 20586,
     (18980, 19000, 19069, 19089, 19621, 19719, 19828, 19957, 20561, 20562,
      20586)),
    ("Claustrum", 22060,
     (18330, 18331, 18648, 18662, 18676, 19757, 19850, 21135, 21136, 22060)),
    ("Conqueror", 21757,
     (18971, 18991, 19060, 19080, 19612, 19710, 19819, 19948, 20837, 20838,
      21757)),
    ("Daurdabla", 18839, (18574, 18575, 18576, 18571, 18839)),
    ("Death Penalty", 21268,
     (18987, 19007, 19076, 19096, 19628, 19726, 19835, 19964, 21262, 21263,
      22141, 21268)),
    ("Epeolatry", 21685, (20753, 21685)),
    ("Excalibur", 20685,
     (18276, 18277, 18639, 18653, 18667, 19748, 19841, 20645, 20646, 20685)),
    ("Fail-Not", 22117, (22131, 22117)),
    ("Farsha", 21752,
     (19401, 19460, 19538, 19636, 19809, 19857, 20794, 20795, 21752)),
    ("Fomalhaut", 22143, (21485, 22143)),
    ("Gambanteinn", 21079,
     (19407, 19466, 19544, 19642, 19815, 19863, 21064, 21065, 21079)),
    ("Gandiva", 22116,
     (19409, 19468, 19546, 19644, 19817, 19865, 21212, 21213, 22130, 22116)),
    ("Gastraphetes", 21266,
     (18981, 19001, 19070, 19090, 19622, 19720, 19829, 19958, 21246, 21247,
      22139, 21266)),
    ("Gjallarhorn", 18840,
     (18342, 18577, 18578, 18579, 18580, 18572, 18840)),
    ("Glanzfaust", 20510,
     (18972, 18992, 19061, 19081, 19613, 19711, 19820, 19949, 20482, 20483,
      20510)),
    ("Gungnir", 21857,
     (18300, 18301, 18643, 18657, 18671, 19752, 19845, 20925, 20926, 21857)),
    ("Guttler", 21750,
     (18288, 18289, 18641, 18655, 18669, 19750, 19843, 20790, 20791, 21750)),
    ("Hvergelmir", 22064,
     (19408, 19467, 19545, 19643, 19816, 19864, 21143, 21144, 22064)),
    ("Idris", 21080, (21070, 21080)),
    ("Kannagi", 21908,
     (19405, 19464, 19542, 19640, 19813, 19861, 20974, 20975, 21908)),
    ("Kenkonken", 20511,
     (18988, 19008, 19077, 19097, 19629, 19727, 19836, 19965, 20484, 20485,
      20511)),
    ("Kikoku", 21906,
     (18312, 18313, 18645, 18659, 18673, 19754, 19847, 20970, 20971, 21906)),
    ("Kogarasumaru", 21955,
     (18982, 19002, 19071, 19091, 19623, 19721, 19830, 19959, 21017, 21018,
      21955)),
    ("Laevateinn", 22062,
     (18974, 18994, 19063, 19083, 19615, 19713, 19822, 19951, 21139, 21140,
      22062)),
    ("Liberator", 21809,
     (18978, 18998, 19067, 19087, 19619, 19717, 19826, 19955, 20882, 20883,
      21809)),
    ("Mandau", 20583,
     (18270, 18271, 18638, 18652, 18666, 19747, 19840, 20555, 20556, 20583)),
    ("Masamune", 21956,
     (19406, 19465, 19543, 19641, 19814, 19862, 21019, 21020, 21956)),
    ("Mjollnir", 21077,
     (18324, 18325, 18647, 18661, 18675, 19756, 19849, 21060, 21061, 21077)),
    ("Murgleis", 20686,
     (18975, 18995, 19064, 19084, 19616, 19714, 19823, 19952, 20647, 20648,
      20686)),
    ("Nagi", 21907,
     (18983, 19003, 19072, 19092, 19624, 19722, 19831, 19960, 20972, 20973,
      21907)),
    ("Nirvana", 22063,
     (18985, 19005, 19074, 19094, 19626, 19724, 19833, 19962, 21141, 21142,
      22063)),
    ("Ochain", 16199, (16192, 16193, 16194, 11926, 16199)),
    ("Ragnarok", 21683,
     (18282, 18283, 18640, 18654, 18668, 19749, 19842, 20745, 20746, 21683)),
    ("Redemption", 21810,
     (19403, 19462, 19540, 19638, 19811, 19859, 20884, 20885, 21810)),
    ("Rhongomiant", 21859,
     (19404, 19463, 19541, 19639, 19812, 19860, 20929, 20930, 21859)),
    ("Ryunohige", 21858,
     (18984, 19004, 19073, 19093, 19625, 19723, 19832, 19961, 20927, 20928,
      21858)),
    ("Spharai", 20509,
     (18264, 18265, 18637, 18651, 18665, 19746, 19839, 20480, 20481, 20509)),
    ("Terpsichore", 20584,
     (18969, 18989, 19078, 19098, 19630, 19728, 19837, 19966, 20557, 20558,
      20584)),
    ("Tizona", 20688,
     (18986, 19006, 19075, 19095, 19627, 19725, 19834, 19963, 20651, 20652,
      20688)),
    ("Tupsimati", 22061,
     (18970, 18990, 19079, 19099, 19631, 19729, 19838, 19967, 21137, 21138,
      22061)),
    ("Twashtar", 20587,
     (19398, 19457, 19535, 19633, 19806, 19854, 20563, 20564, 20587)),
    ("Ukonvasara", 21758,
     (19402, 19461, 19539, 19637, 19810, 19858, 20839, 20840, 21758)),
    ("Vajra", 20585,
     (18976, 18996, 19065, 19085, 19617, 19715, 19824, 19953, 20559, 20560,
      20585)),
    ("Verethragna", 20512,
     (19397, 19456, 19534, 19632, 19805, 19853, 20486, 20487, 20512)),
    ("Yagrush", 21078,
     (18973, 18993, 19062, 19082, 19614, 19712, 19821, 19950, 21062, 21063,
      21078)),
    ("Yoichinoyumi", 22115,
     (18348, 18349, 18650, 18664, 18678, 19759, 19852, 21210, 21211, 22129,
      22115)),
)


@dataclass(frozen=True)
class RemaForm:
    """One REMA catalogue row and the final form its family upgrades to."""

    family: str
    item_id: int
    final_id: int

    @property
    def is_final(self) -> bool:
        return self.item_id == self.final_id


def _index_forms() -> dict[int, RemaForm]:
    index: dict[int, RemaForm] = {}
    for family, final_id, item_ids in REMA_FAMILIES:
        if final_id not in item_ids:
            raise ValueError("%s final %d is not in its family" % (family, final_id))
        for item_id in item_ids:
            if item_id in index:
                raise ValueError("item %d is in two REMA weapon families" % item_id)
            index[item_id] = RemaForm(family=family, item_id=item_id, final_id=final_id)
    return index


_FORMS = _index_forms()
_FAMILY_IDS = {family: item_ids for family, _final_id, item_ids in REMA_FAMILIES}


def form(item_id: int) -> RemaForm | None:
    """The REMA family row for an item, or None when it is not a REMA weapon."""
    try:
        return _FORMS.get(int(item_id))
    except (TypeError, ValueError):
        return None


def final_item_id(item_id: int) -> int | None:
    """The afterglow/final form of *item_id*'s family, or None for a non-REMA item."""
    entry = form(item_id)
    return entry.final_id if entry else None


def family_item_ids(item_id: int) -> tuple[int, ...]:
    """Every catalogue id in *item_id*'s REMA family, or () for a non-REMA item."""
    entry = form(item_id)
    if entry is None:
        return ()
    return _FAMILY_IDS[entry.family]
