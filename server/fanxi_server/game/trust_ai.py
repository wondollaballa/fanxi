"""Alter-ego tactics: the spells a Trust casts, the auras it radiates, the songs it sings
and the Corsair rolls it keeps up.

The data comes from the Trust's own ``mob_spell_lists`` rows (migration 117); this
module only decides what to do with it.  A Trust casts the highest spell in a family it
has unlocked, keeps its owner's buffs up, heals below the cure threshold, and either
nukes, debuffs or swings depending on its job.  A per-Trust tactic can also keep a whole
family out of the rotation (Koru-Moru does not cast Flurry, which only speeds up ranged
attacks, so Haste II is the attack-speed buff he keeps up).  The seven passive Trusts do
not fight: they carry an aura, and that aura has its own status icon (Cornelia's is GEO
Haste, a separate icon from ordinary Haste).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import effects, geomancy, modifiers as mod, packets, rolls

# Spell skills, matching packets.SKILL_*.  A Trust's list only needs these to tell a
# cure from a nuke from a buff.
SKILL_DIVINE = 32
SKILL_HEALING = 33
SKILL_ENHANCING = 34
SKILL_ELEMENTAL = 36

# The player path gives an Indi-/Geo- aura a flat 180 seconds; a Trust's aura uses the
# same window because the server has no Geomancy-skill duration term yet.
GEO_AURA_SECONDS = 180.0

# A Trust's Geomancy is not the player's: Sylvie (UC) is a level-99 alter ego with fixed
# published values (+37.5% Attack, +56 Accuracy, +28.8% Haste, Entrust Indi-Frailty for
# -12.5% Defense), not the weaker Geomancy+0 column the player's Indi- spells use.  These
# are the numbers BG-wiki's Trust: Sylvie (UC) page lists for her level-99 kit.
TRUST_AURA_EFFECTS: dict[str, dict[str, tuple[dict[int, int], int]]] = {
    "sylvie uc": {
        "fury": ({mod.ATT_PERCENT: 37, mod.RATT: 37}, 0),
        "precision": ({mod.ACC: 56}, 0),
        "haste": ({mod.HASTE_ABILITY: 2880}, 0),
        "frailty": ({}, 12),
        "acumen": ({mod.MATT: 21}, 0),
        "refresh": ({mod.REFRESH: 5}, 0),
        "regen": ({mod.REGEN: 30}, 0),
        # Her Geo-Malaise is the enemy-targeted Magic Defense Down hex.  The Trust
        # carries Idris, so the published hex value is 30%, not the player's 10%.
        "malaise": ({}, 30),
    },
}

# Sylvie's second aura: she puts Entrust on the monster, so the fight gets the
# Indi-Frailty defense cut even while her own Indi-Fury bubble stays on the owner.
ENTRUST_TRUSTS = frozenset({"sylvie uc"})


def is_entrust_trust(name: str) -> bool:
    """True for a Trust that keeps an owner aura and a separate Entrust on the mob."""
    return _key(name) in ENTRUST_TRUSTS

# Casters that should hold their distance instead of joining the melee.  Paladins,
# Dark Knights, Red Mages, Blue Mages and Rune Fencers have spells but still fight from
# the front; White/Black/Summoner/Scholar/Geomancer/Bard do not.
PURE_CASTERS = frozenset({3, 4, 10, 15, 20, 21})
CAST_RANGE = 18.0

# Buffs are put up in this order, before the long tail of songs, storms and spikes.
BUFF_PRIORITY = {
    effects.PROTECT: 0,
    effects.SHELL: 1,
    effects.HASTE: 2,
    effects.REFRESH: 3,
    effects.REGEN: 4,
    effects.PHALANX: 5,
    effects.STONESKIN: 6,
}

# --- songs ----------------------------------------------------------------------------------
# A Bard trust sings what the owner's role needs, not the whole list.  The March line is
# the haste that is missing -- Victory March while its Haste fits under the cap, Honor
# March once it would not -- the Minuet line is the Attack cap, and once Attack is capped
# there is nothing left for Minuet to buy -- Aria of Passion's Damage Limit is the play.
# The Madrigal line then fills the spare slot the horn's Song+4 opens up: Accuracy is the
# other thing a damage dealer caps, so a swing that lands under ACCURACY_SONG_SHORTFALL
# earns the song, and one that lands more often than that leaves the slot empty rather
# than spending it on a Paeon or a Ballad the owner never asked for.  A mage wants the MP
# ballad; a Ranger in the back line wants speed and the ranged lines (Prelude is their
# Accuracy, so Madrigal would be a wasted slot).  A Corsair owns ranged attacks but
# fights in melee too, so it gets the melee plan; the owner can still ask for Prelude by
# name with the per-character song set.
RANGED_JOBS = frozenset({11, 17})     # Ranger, Corsair: the rolls count them as ranged
#: The jobs whose default song plan is the ranged one.  A Corsair is not here: Prelude's
#: Ranged Accuracy is a wasted slot for the melee set, and `//trust joachim set songs`
#: is how a shooting Corsair asks for it.
RANGED_SONG_JOBS = frozenset({11})    # Ranger only
#: The Trusts whose songs are planned by role.  Joachim is the Bard the owner is
#: travelling with; other Bards (Ulmia) keep the plain buff rotation for now.
SONG_PLANNERS = frozenset({"joachim"})
HASTE_CAP_PERCENT = 0.4375            # the magic-haste cap the March line fills
#: The hit rate the Madrigal line tops up.  Retail's hit rate tops out around 95%, so a
#: swing below it still has Accuracy to buy; above it the slot is better left empty.
ACCURACY_SONG_SHORTFALL = 0.95
SONG_REFRESH_SECONDS = 20.0
#: The Loughnashade's bar: four songs.  The server enforces the same limit when the owner
#: asks for a specific set.
SONG_SET_MAX = 4

# --- configurable support trusts ------------------------------------------------------------
# The HUD lets the owner choose the actions one support Trust uses: songs for Joachim, spells
# for the casters, and roll priorities for the Corsairs.  The key is the Trust spell id, the
# same id the client's Trust window carries.  These ids are the switch the AI reads; keeping
# them here means the server and the HUD test agree on which Trusts have a Set button.
SUPPORT_TRUST_IDS = frozenset({911, 928, 952, 967, 981, 998})
#: How the selected ids are interpreted: a song order, a spell pool, or a roll priority list.
TRUST_ACTION_KIND: dict[int, str] = {
    911: "song",     # Joachim
    928: "roll",     # Luzaf
    952: "spell",    # Koru-Moru
    967: "roll",     # Qultada
    981: "spell",    # Sylvie (UC)
    998: "spell",    # Ygnas
}
#: How many actions one character may keep.  Songs are the horn's bar; the caster pool and the
#: Corsair priority list are longer because they are not simultaneous buff slots.
TRUST_ACTION_LIMIT: dict[int, int] = {
    911: 4, 928: 8, 952: 12, 967: 8, 981: 12, 998: 12,
}
#: The Trusts whose selected spells replace the whole cast rotation.
SPELL_ACTION_TRUSTS = frozenset({952, 981, 998})
#: The Trusts whose selected rolls replace the role-based roll choice.
ROLL_ACTION_TRUSTS = frozenset({928, 967})


@dataclass(frozen=True)
class SongNeed:
    """What the owner's role asks the Bard to sing."""

    caster: bool = False
    ranged: bool = False
    haste_percent: float = 0.0
    attack_capped: bool = False
    hit_rate: float = 1.0


def choose_songs(kit: dict, need: SongNeed,
                 selected: list[int] | tuple[int, ...] | None = None) -> list[dict]:
    """The songs this owner needs, best first; [] when there is nothing worth singing.

    ``selected`` is the owner's explicit ``//trust joachim set songs`` list (spell ids,
    in the order the owner gave them).  It overrides the role plan completely: the owner
    asked for these songs, not for the Bard's opinion.  Ids not in this kit are skipped,
    which is how a stored set survives a level change that locks one of its songs.
    """
    if not kit.get("song"):
        return []
    if selected:
        by_id = {int(spell["id"]): spell
                 for spell in (kit.get("song_all") or kit.get("song", []))}
        return [by_id[int(spell_id)] for spell_id in selected
                if int(spell_id) in by_id][:SONG_SET_MAX]
    if need.caster:
        ballad = _song(kit, "ballad")
        return [ballad] if ballad is not None else []
    march = _march(kit)
    honor = _named(kit, "honor march")
    minuet = _song(kit, "minuet")
    if need.ranged:
        prelude = _song(kit, "prelude")
        return [spell for spell in (march, prelude, minuet) if spell is not None]
    songs: list[dict] = []
    # Victory March is the Haste line, Honor March the Attack/Accuracy one.  They share
    # the March status, so the plan has to choose: Victory while its Haste still fits
    # under the cap, Honor once a March's Haste would be partly wasted anyway.
    if march is not None and (honor is None
                              or float(need.haste_percent) + march_haste(march)
                              <= HASTE_CAP_PERCENT):
        songs.append(march)
    elif honor is not None:
        songs.append(honor)
    if need.attack_capped:
        aria = _song(kit, "aria")
        if aria is not None:
            songs.append(aria)
    elif minuet is not None:
        songs.append(minuet)
    madrigal = _song(kit, "madrigal")
    if madrigal is not None and float(need.hit_rate) < ACCURACY_SONG_SHORTFALL:
        songs.append(madrigal)
    return songs


def _named(kit: dict, name: str) -> dict | None:
    """The kit's song with exactly this name.

    ``_song`` groups by status, and Honor March shares the March status with Victory
    March; this is how a plan asks for one of two songs that cannot both be up.
    """
    for spell in kit.get("song", []):
        if _name(spell) == name:
            return spell
    return None


def _march(kit: dict) -> dict | None:
    """The March line's Haste song, which is Victory March rather than Honor March."""
    best = None
    for spell in kit.get("song", []):
        if effects.song_family(_name(spell)) != "march" or _name(spell) == "honor march":
            continue
        if best is None or int(spell["id"]) > int(best["id"]):
            best = spell
    return best


def march_haste(spell: dict) -> float:
    """The magic haste a March song adds before Song+ potency, as a fraction of 1."""
    spec = effect_of(spell)
    if spec is None:
        return 0.0
    return max(0.0, int((spec.mods or {}).get(mod.HASTE_MAGIC, 0)) / 10000.0)


def _song(kit: dict, family: str) -> dict | None:
    """The highest tier of one song family, from the default (pruned) plan."""
    best = None
    for spell in kit.get("song", []):
        if effects.song_family(_name(spell)) != family:
            continue
        if best is None or int(spell["id"]) > int(best["id"]):
            best = spell
    return best


# --- corsair rolls ---------------------------------------------------------------------------
# Qultada and Luzaf are support, not damage: they roll and never swing.  Which roll is a
# party decision the way Joachim's songs are -- the party's composition and what it is
# short of, not the owner's job -- because a Corsair roll lands on everyone.
#   * casters running dry      Evoker's Roll    (Refresh)
#   * a caster-heavy party     Wizard's Roll    (Magic Attack)
#   * a ranged-heavy party     Hunter's Roll    (Ranged Accuracy)
#   * melee short of Attack    Chaos Roll       (Attack)
#   * melee at the pDIF cap    Samurai Roll     (Store TP: more weapon skills)
#   * any melee                Fighter's Roll   (Double Attack)
# A second Corsair sees the roll already on the party and takes the next line that is
# still useful, so Qultada and Luzaf together hold Chaos, Fighter's and Samurai rather
# than rolling the same one twice.
ROLL_PLANNERS = frozenset({"qultada", "luzaf"})
#: How many rolls one Trust Corsair keeps up.  Retail Qultada holds two at once (Chaos
#: and Fighter's are his standard pair), and an alter ego is a maxed-out Corsair.
MAX_TRUST_ROLLS = 2
#: How often a roll Trust checks the party while its rolls are still up.
ROLL_REFRESH_SECONDS = 8.0
#: Ability id and status id by ``rolls.RollSpec.key``: plans name a roll, not a number.
ROLL_IDS: dict[str, int] = {}
ROLL_KEYS: dict[int, str] = {}
ROLL_STATUS: dict[str, int] = {}
for _ability_id, _roll_spec in rolls.ROLLS.items():
    ROLL_IDS[_roll_spec.key] = int(_ability_id)
    ROLL_KEYS[int(_ability_id)] = _roll_spec.key
    ROLL_STATUS[_roll_spec.key] = int(_roll_spec.status)


@dataclass(frozen=True)
class RollNeed:
    """What the party is short of, for ``choose_roll``."""

    melee: int = 0
    mages: int = 0
    ranged: int = 0
    mp_percent: float = 100.0
    attack_capped: bool = False
    #: Rolls already on the party from another Corsair, by status id.
    active: frozenset[int] = frozenset()


def plans_rolls(name: str) -> bool:
    """Whether this Trust rolls for the party instead of fighting."""
    return " ".join(str(name or "").casefold().split()) in ROLL_PLANNERS


def roll_options(need: RollNeed) -> list[str]:
    """The rolls worth having for this party, best first.

    A party with as many melee as casters is treated as a melee party: the melee line is
    what makes the kills, and the caster line still follows before the list ends.  That
    is also what gives a solo Red Mage both lines instead of only Wizard's Roll.
    """
    options: list[str] = []
    if need.mages and float(need.mp_percent) < MP_LOW_PERCENT:
        options.append("evokers")
    if need.mages and need.mages > need.melee:
        options.append("wizards")
    if need.ranged:
        options.append("hunters")
    if need.melee:
        if need.attack_capped:
            options.extend(("samurai", "fighters", "chaos"))
        else:
            options.extend(("chaos", "fighters", "samurai"))
    if need.mages and need.mages <= need.melee:
        options.append("wizards")
    if not options:
        options.append("wizards" if need.mages else "chaos")
    return options


def choose_roll(need: RollNeed, selected: list[int] | tuple[int, ...] | None = None) -> int | None:
    """The roll this party still needs, skipping one another Corsair already keeps up.

    ``selected`` is the owner's explicit roll priority (ability ids).  The first selected
    roll whose status is not already on the party wins; when every selected status is up,
    the first one is refreshed.  With no selection the role plan above decides.
    """
    if selected:
        allowed = [int(ability) for ability in selected
                   if int(ability) in ROLL_KEYS]
        for ability in allowed:
            key = ROLL_KEYS[ability]
            if ROLL_STATUS[key] not in need.active:
                return ability
        return allowed[0] if allowed else None
    options = roll_options(need)
    for key in options:
        if ROLL_STATUS[key] not in need.active:
            return ROLL_IDS[key]
    return ROLL_IDS[options[0]]       # every option is up: refresh the best one


# A Trust's ``mob_spell_list`` is factual; this table is Fanxi's tactics on top of it.  A
# family listed for a Trust is left out of the kit, so the rotation spends its casts on
# buffs the owner can use.  Flurry and Flurry II share effect 581 and only speed up ranged
# attacks: Koru-Moru's owner fights in melee, so the Red Mage keeps Haste II up instead of
# wasting a cast on Flurry II.
NEVER_CAST: dict[str, frozenset[int]] = {
    "koru-moru": frozenset({effects.FLURRY}),
}


def never_cast(name: str) -> frozenset[int]:
    """The buff families this Trust should never cast, by its display name."""
    return NEVER_CAST.get(" ".join(str(name or "").casefold().split()), frozenset())


# --- geomancy -------------------------------------------------------------------------------
# A Geomancer keeps one aura up; the next Indi-/Geo- cast replaces it.  Which one is a
# per-beat decision, so the zone tick measures the owner and asks ``choose_aura``.  The
# thresholds are where the next +10 Accuracy or +10% Attack buys more than the other
# choices: a hit rate under 80% (the one-handed cap is well above it), an Attack/Defense
# ratio under 1.3, or a team that is down to its last half a mana bar.
MAGE_JOBS = frozenset({3, 4, 5, 15, 16, 20, 21})   # WHM BLM RDM SMN BLU SCH GEO
#: Melee-capable casters.  A Red Mage or Blue Mage counts on both sides of the roll plan,
#: so a solo one still gets the melee line next to Wizard's/Evoker's instead of one roll.
HYBRID_JOBS = frozenset({5, 16})                   # Red Mage, Blue Mage
ACCURACY_SHORTFALL = 0.80
ATTACK_SHORTFALL = 1.30
MP_LOW_PERCENT = 50.0
PARTY_MP_LOW_PERCENT = 40.0
# Aura swaps are cheap but not free: this floor stops her flapping between two needs
# that sit either side of a threshold.  An aura this close to falling off is refreshed
# rather than replaced.
AURA_SWAP_SECONDS = 8.0
AURA_REFRESH_SECONDS = 30.0


@dataclass(frozen=True)
class AuraNeed:
    """What the owner's situation asks for, measured once per beat by the zone tick."""

    mp_percent: float = 100.0
    party_mp_percent: float = 100.0
    caster: bool = False
    target: bool = False
    hit_rate: float = 1.0
    attack_ratio: float = 2.0
    party_melee: int = 1
    tp_ready: bool = False


def choose_aura(kit: dict, need: AuraNeed) -> dict | None:
    """The one Indi-/Geo- aura the owner needs now, or None to leave the bar alone.

    The order is the owner's own priority: an empty MP pool first, then the accuracy or
    attack that is holding the owner's damage back, then the group's damage.  Frailty
    cuts the monster's Defense for every physical hit the team lands, which is why it
    wins once the owner's accuracy and Attack are no longer the bottleneck, and why a
    ready weapon skill (TP) makes it the play.  Out of combat the choice falls back to
    Accuracy so the aura is up before the pull.
    """
    if not kit.get("aura"):
        return None
    if need.mp_percent < MP_LOW_PERCENT or need.party_mp_percent < PARTY_MP_LOW_PERCENT:
        spell = _aura(kit, "refresh")
        if spell is not None:
            return spell
    if need.caster:
        spell = _aura(kit, "acumen")
        if spell is not None:
            return spell
    if not need.target:
        # Nothing to measure yet -- on the pull, or between fights -- so keep a general
        # aura up rather than leaving the bar empty.  Accuracy is the safe physical
        # default (it moves every hit), then Attack, then the regen line.
        return (_aura(kit, "precision") or _aura(kit, "fury")
                or _aura(kit, "regen") or _aura(kit, "refresh"))
    if need.hit_rate < ACCURACY_SHORTFALL:
        spell = _aura(kit, "precision")
        if spell is not None:
            return spell
    if need.tp_ready and need.party_melee >= 2:
        spell = _aura(kit, "frailty")
        if spell is not None:
            return spell
    if need.attack_ratio < ATTACK_SHORTFALL:
        spell = _aura(kit, "fury")
        if spell is not None:
            return spell
    return _aura(kit, "frailty") or _aura(kit, "fury")


def _aura(kit: dict, family: str) -> dict | None:
    """The kit's Indi-/Geo- spell of one family, or None when the Trust has none."""
    for spell in kit.get("aura", []):
        if geomancy.family(_name(spell)) == family:
            return spell
    return None


@dataclass(frozen=True)
class Aura:
    """One passive Trust's COLURE_ACTIVE sub-effect."""

    effect: int
    icon: int
    mods: dict[int, int] = field(default_factory=dict)
    tick: int = 0
    label: str = ""


# The icons are the client's GEO_Haste/GEO_Regen/... status icons, which is what makes a
# Trust aura look like the Geomancy bubble it is.  The modifiers stack with ordinary
# spell buffs because ``effect_state`` is a separate id for each.
AURAS: dict[str, Aura] = {
    "cornelia": Aura(
        effects.TRUST_AURA_HASTE, 580,
        {mod.HASTE_MAGIC: 2000, mod.ACC: 30, mod.RACC: 30, mod.MACC: 30},
        label="Haste"),
    "sakura": Aura(effects.TRUST_AURA_REGEN, 539, tick=6, label="Regen"),
    "moogle": Aura(effects.TRUST_AURA_REFRESH, 541, tick=3, label="Refresh"),
    "star sibyl": Aura(
        effects.TRUST_AURA_MAGIC_ATTACK, 551,
        {mod.MATT: 19, mod.MACC: 19}, label="Magic Atk. Boost"),
    "kuyin hathdenna": Aura(
        effects.TRUST_AURA_ACC, 553,
        {mod.ACC: 24, mod.RACC: 24, mod.DEX: 5}, label="Accuracy Boost"),
    "brygid": Aura(
        effects.TRUST_AURA_CHR, 548,
        {mod.CHR: 5, mod.DEF_PERCENT: 10, mod.MDEF: 5}, label="CHR Boost"),
    # Kupofried's aura is experience/capacity-point dedication.  The icon is the point;
    # this server has no dedication modifier to read, so only the status is carried.
    "kupofried": Aura(effects.TRUST_AURA_EXP, 249, label="Dedication"),
}


def aura_for(name: str) -> Aura | None:
    return AURAS.get(" ".join(str(name).casefold().split()))


def _name(spell: dict) -> str:
    return " ".join(str(spell.get("name") or "").casefold().split())


def effect_of(spell: dict, geomancy_plus: int = 0, trust_name: str = ""):
    """The effect a spell applies, geomancy included.

    The Indi-/Geo- family is not in ``effects.SPELLS``: the zone server applies those
    auras from ``geomancy.INDI_EFFECTS`` by spell name.  Without this fallback the kit
    builder saw no effect for them and dropped every one -- Sylvie (UC), the only Trust
    that casts geomancy, was left with Cure and Haste and never put up an aura.

    ``geomancy_plus`` is the caster's Geomancy+ level from its weapons.  At Idris's +10 the
    aura takes the Idris column of BGWiki's table (stronger mods, and the hex potency the
    combat engine cuts with) instead of the plain one.
    """
    name = _name(spell)
    spec = effects.for_spell(name)
    if spec is not None:
        return spec
    aura = geomancy.indi_effect(name)
    if aura is None:
        return None
    status, mods, hostile = aura
    potency = 10
    if int(geomancy_plus) >= geomancy.IDRIS_GEOMANCY_PLUS:
        idris = geomancy.idris_effect(name)
        if idris is not None:
            mods, potency = idris
    trust_values = TRUST_AURA_EFFECTS.get(_key(trust_name))
    if trust_values is not None:
        fixed = trust_values.get(geomancy.family(name))
        if fixed is not None:
            mods, potency = fixed
    return effects.SpellEffect(status, "debuff" if hostile else "buff",
                               GEO_AURA_SECONDS, potency=potency, mods=dict(mods))


def _key(name: str) -> str:
    """Trust display names compare without case or extra whitespace."""
    return " ".join(str(name or "").casefold().split())


def opening_debuff_for(kit: dict, active: dict[int, dict], now: float,
                       refresh_within: float = 30.0) -> dict | None:
    """The damage-first debuff: Dia, before the buff rotation gets a turn.

    Koru-Moru carries Protect/Shell/Haste/Refresh/Phalanx and will otherwise spend
    every cast refreshing one of them; ``buff_for`` is checked before ``debuff_for`` in
    the zone tick, so his Dia -- a 10-30% Defense cut that raises every physical hit --
    never lands.  This returns Dia when it is missing or about to expire, so the cast
    order is Dia, then the owner's buffs, then the rest of the enfeebles.
    """
    for spell in kit.get("debuff", ()):
        spec = effect_of(spell)
        if spec is None or int(spec.effect) != effects.DIA:
            continue
        state = active.get(int(spec.effect))
        if state is None:
            return spell
        until = float(state.get("until") or 0.0)
        if until and until - now <= refresh_within:
            return spell
    return None


def entrust_debuff_for(name: str, kit: dict, active: dict[int, dict], now: float,
                       refresh_within: float = 30.0) -> dict | None:
    """The Entrust aura a Geomancer Trust puts on the monster, if it is missing.

    Sylvie (UC) does not have a Geo- frailty in her spell table; she keeps Indi-Fury on
    the owner and Entrusts Indi-Frailty onto the fight.  The server lands the entrusted
    cut as an ordinary ``DEFENSE_DOWN`` on the monster (the bubble is on the party, not
    the mob), so this checks that effect rather than the GEO aura id.
    """
    if _key(name) not in ENTRUST_TRUSTS:
        return None
    for spell in kit.get("aura", ()):
        spec = effect_of(spell)
        if spec is None or int(spec.effect) != geomancy.GEO_DEFENSE_DOWN:
            continue
        state = active.get(effects.DEFENSE_DOWN)
        if state is None:
            return spell
        until = float(state.get("until") or 0.0)
        if until and until - now <= refresh_within:
            return spell
    return None


def is_cure(spell: dict) -> bool:
    """Cure/Curaga/Cura, but not a status-removal spell that shares Healing Magic."""
    name = _name(spell)
    return (int(spell.get("skill") or 0) == SKILL_HEALING
            and (name.startswith("cure") or name.startswith("curaga")))


def is_nuke(spell: dict) -> bool:
    """A direct-damage divine/elemental spell, not an enfeeble or special spell."""
    if int(spell.get("skill") or 0) not in (SKILL_DIVINE, SKILL_ELEMENTAL):
        return False
    spec = effect_of(spell)
    if spec is not None and spec.kind in ("buff", "debuff", "special"):
        return False
    return int(spell.get("base") or 0) > 0


def build_kit(spells: list[dict], level: int, job: int = 0, name: str = "") -> dict:
    """Group a Trust's unlocked spells into the choices the AI asks for.

    The database already filters by ``min_level``; the level argument is kept so a
    caller can rebuild the kit when the owner levels up.  Only the highest tier of each
    buff/debuff family is kept -- a WHM with Protect V should not cast Protect first.
    Songs keep the same pruned list in ``song`` for the role plan, and every unlocked
    tier in ``song_all`` for an owner's explicit set (Minuet IV beside V).  ``name``
    applies the per-Trust tactic in ``NEVER_CAST`` so a family the owner never wants is
    dropped before the highest-tier choice is made.
    """
    level = max(1, int(level))
    skip = never_cast(name)
    plan_songs = " ".join(str(name or "").casefold().split()) in SONG_PLANNERS
    kit: dict = {"cure": [], "buff": [], "debuff": [], "aura": [], "song": [],
                 "song_all": [], "nuke": [], "caster": False, "pure_caster": False,
                 "level": level, "actions_all": [], "action_kind": {}}
    best_buff: dict[int, dict] = {}
    best_debuff: dict[int, dict] = {}
    best_song: dict[int, dict] = {}
    for spell in spells or []:
        if int(spell.get("min_level") or 0) > level:
            continue
        spec = effect_of(spell)
        if is_cure(spell):
            kit["cure"].append(spell)
            kit["action_kind"][int(spell["id"])] = "cure"
            kit["actions_all"].append(spell)
        elif plan_songs and int(spell.get("skill") or 0) in effects.SONG_SKILLS:
            # Songs are their own rotation (``choose_songs``).  ``song`` keeps one tier
            # per line for the default role plan: Victory March over Advancing, Minuet V
            # over IV.  Honor March is the exception: it shares the March status with
            # Victory March but is a different song (Attack/Accuracy instead of Haste),
            # so it gets its own key and both stay in the plan.  ``song_all`` keeps every
            # tier because an explicit owner set may ask for Minuet IV as well as V.
            if spec is not None and int(spec.effect) > 0:
                effect = int(spec.effect)
                key = -effect if _name(spell) == "honor march" else effect
                current = best_song.get(key)
                if current is None or int(spell["id"]) > int(current["id"]):
                    best_song[key] = spell
                kit["song_all"].append(spell)
                kit["action_kind"][int(spell["id"])] = "song"
                kit["actions_all"].append(spell)
        elif geomancy.indi_effect(_name(spell)) is not None:
            # Geomancy is its own rotation: exactly one aura is up at a time, and which
            # one is a decision the zone tick makes per beat (``choose_aura``), not a buff
            # the kit puts up in order.
            kit["aura"].append(spell)
            kit["action_kind"][int(spell["id"])] = "aura"
            kit["actions_all"].append(spell)
        elif spec is not None and spec.kind == "buff" and int(spec.effect) > 0:
            # The full action catalogue keeps the families the default rotation refuses
            # (Koru-Moru's Flurry): an explicit owner set may ask for them.
            kit["action_kind"][int(spell["id"])] = "buff"
            kit["actions_all"].append(spell)
            if int(spec.effect) in skip:
                continue
            current = best_buff.get(int(spec.effect))
            if current is None or int(spell["id"]) > int(current["id"]):
                best_buff[int(spec.effect)] = spell
        elif spec is not None and spec.kind == "debuff" and int(spec.effect) > 0:
            kit["action_kind"][int(spell["id"])] = "debuff"
            kit["actions_all"].append(spell)
            current = best_debuff.get(int(spec.effect))
            if current is None or int(spell["id"]) > int(current["id"]):
                best_debuff[int(spec.effect)] = spell
        elif is_nuke(spell):
            kit["nuke"].append(spell)
            kit["action_kind"][int(spell["id"])] = "nuke"
            kit["actions_all"].append(spell)
    kit["cure"].sort(key=lambda spell: (int(spell.get("mp") or 0), int(spell["id"])))
    kit["aura"].sort(key=lambda spell: int(spell["id"]))
    kit["song"] = sorted(best_song.values(), key=lambda spell: int(spell["id"]))
    kit["song_all"].sort(key=lambda spell: int(spell["id"]))
    kit["actions_all"].sort(key=lambda spell: int(spell["id"]))
    kit["buff"] = sorted(
        best_buff.values(),
        key=lambda spell: (BUFF_PRIORITY.get(int(effect_of(spell).effect), 50),
                           int(spell["id"])))
    kit["debuff"] = sorted(
        best_debuff.values(),
        key=lambda spell: (0 if effect_of(spell).damage else 1,
                           int(spell["id"])))
    kit["nuke"].sort(key=lambda spell: (int(spell.get("base") or 0), int(spell["id"])))
    kit["caster"] = bool(kit["cure"] or kit["buff"] or kit["debuff"] or kit["aura"]
                         or kit["song"] or kit["nuke"])
    kit["pure_caster"] = is_pure_caster(job)
    return kit


def restrict_kit(kit: dict, selected: list[int] | tuple[int, ...]) -> dict:
    """A kit containing only the owner's selected actions, in selection order.

    The default AI still decides *when* each selected spell is useful (cure when the
    owner is hurt, buff when it is missing, debuff when the monster lacks it), but it can
    no longer cast anything the owner did not choose.  Groups keep the owner's order so
    ``buff_for`` and the aura chooser read it as a priority list.
    """
    by_id = {int(spell["id"]): spell for spell in kit.get("actions_all", [])}
    kinds = kit.get("action_kind", {})
    out: dict = {"cure": [], "buff": [], "debuff": [], "aura": [], "song": [],
                 "song_all": [], "nuke": [], "actions_all": [], "action_kind": {},
                 "caster": False, "pure_caster": bool(kit.get("pure_caster")),
                 "level": int(kit.get("level", 1) or 1)}
    for spell_id in selected or ():
        spell = by_id.get(int(spell_id))
        kind = kinds.get(int(spell_id))
        if spell is None or kind not in ("cure", "buff", "debuff", "aura", "song", "nuke"):
            continue
        out[kind].append(spell)
        if kind == "song":
            out["song_all"].append(spell)
        out["actions_all"].append(spell)
        out["action_kind"][int(spell_id)] = kind
    out["caster"] = bool(out["cure"] or out["buff"] or out["debuff"] or out["aura"]
                         or out["song"] or out["nuke"])
    return out


def cure_for(kit: dict, level: int, mp: int, missing_hp: int) -> dict | None:
    """The cheapest Cure that covers ``missing_hp``, or the biggest affordable one."""
    candidates = [spell for spell in kit.get("cure", [])
                  if int(spell.get("mp") or 0) <= int(mp)]
    if not candidates:
        return None
    missing = max(0, int(missing_hp))

    def amount(spell: dict) -> int:
        # Same base the player path uses: MP cost x 3 + caster level.  Gear potency is
        # not part of a Trust's kit, so no modifiers enter this number.
        return int(spell.get("mp") or 0) * 3 + int(level)

    enough = [spell for spell in candidates if amount(spell) >= missing]
    if enough:
        return min(enough, key=lambda spell: (amount(spell), int(spell["id"])))
    return max(candidates, key=lambda spell: (amount(spell), int(spell["id"])))


def _stronger_buff(spec, state: dict) -> bool:
    """Whether this spell is a real upgrade over the copy already on the owner.

    Haste and Phalanx share one status id across their tiers.  If a party member's
    Haste I or Phalanx I is up, looking only at the status id makes a Red Mage skip the
    stronger tier for its whole duration.  Compare the effect value instead: Haste's
    magic-haste modifier and Phalanx's flat absorption.
    """
    mods = state.get("mods") or {}
    if int(spec.effect) == effects.HASTE:
        return (int(mods.get(mod.HASTE_MAGIC, 0))
                < int((spec.mods or {}).get(mod.HASTE_MAGIC, 0)))
    if int(spec.effect) == effects.PHALANX:
        return int(state.get("power", 0)) < int(spec.power)
    return False


def buff_for(kit: dict, active: dict[int, dict], now: float,
             refresh_within: float = 45.0) -> dict | None:
    """The next buff the owner is missing, or one about to wear off."""
    for spell in kit.get("buff", []):
        spec = effect_of(spell)
        if spec is None:
            continue
        state = active.get(int(spec.effect))
        if state is None:
            return spell
        if _stronger_buff(spec, state):
            return spell
        until = float(state.get("until") or 0.0)
        if until and until - now <= refresh_within:
            return spell
    return None


def debuff_for(kit: dict, active: dict[int, dict], now: float,
               refresh_within: float = 30.0) -> dict | None:
    """The next missing debuff on the monster, Dia first because it also does damage."""
    for spell in kit.get("debuff", []):
        spec = effect_of(spell)
        if spec is None:
            continue
        state = active.get(int(spec.effect))
        if state is None:
            return spell
        until = float(state.get("until") or 0.0)
        if until and until - now <= refresh_within:
            return spell
    return None


def nuke_for(kit: dict, mp: int) -> dict | None:
    """A nuke the Trust can pay for, preferring a short cast so the fight keeps moving."""
    affordable = [spell for spell in kit.get("nuke", [])
                  if int(spell.get("mp") or 0) <= int(mp)]
    if not affordable:
        return None
    short = [spell for spell in affordable
             if int(spell.get("cast_time") or 0) <= 3000] or affordable
    return max(short, key=lambda spell: (int(spell.get("base") or 0), int(spell["id"])))


def is_pure_caster(job: int) -> bool:
    return int(job or 0) in PURE_CASTERS


def cast_arg(spell: dict) -> int:
    """The Magic Start 4CC for a Trust's spell school."""
    return packets.magic_cast_arg(int(spell.get("skill") or 0))


def spell_animation(spell: dict) -> int:
    return int(spell.get("animation") or 0)
