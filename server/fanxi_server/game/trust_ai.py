"""Alter-ego tactics: the spell kit a Trust uses and the auras it radiates.

The data comes from the Trust's own ``mob_spell_lists`` rows (migration 117); this
module only decides what to do with it.  A Trust casts the highest spell in a family it
has unlocked, keeps its owner's buffs up, heals below the cure threshold, and either
nukes, debuffs or swings depending on its job.  The seven passive Trusts do not fight:
they carry an aura, and that aura has its own status icon (Cornelia's is GEO Haste, a
separate icon from ordinary Haste).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import effects, modifiers as mod, packets

# Spell skills, matching packets.SKILL_*.  A Trust's list only needs these to tell a
# cure from a nuke from a buff.
SKILL_DIVINE = 32
SKILL_HEALING = 33
SKILL_ENHANCING = 34
SKILL_ELEMENTAL = 36

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
        {mod.HASTE_GEAR: 2000, mod.ACC: 30, mod.RACC: 30, mod.MACC: 30},
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


def effect_of(spell: dict):
    return effects.for_spell(_name(spell))


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


def build_kit(spells: list[dict], level: int, job: int = 0) -> dict:
    """Group a Trust's unlocked spells into the choices the AI asks for.

    The database already filters by ``min_level``; the level argument is kept so a
    caller can rebuild the kit when the owner levels up.  Only the highest tier of each
    buff/debuff family is kept -- a WHM with Protect V should not cast Protect first.
    """
    level = max(1, int(level))
    kit: dict = {"cure": [], "buff": [], "debuff": [], "nuke": [], "caster": False,
                 "pure_caster": False, "level": level}
    best_buff: dict[int, dict] = {}
    best_debuff: dict[int, dict] = {}
    for spell in spells or []:
        if int(spell.get("min_level") or 0) > level:
            continue
        spec = effect_of(spell)
        if is_cure(spell):
            kit["cure"].append(spell)
        elif spec is not None and spec.kind == "buff" and int(spec.effect) > 0:
            current = best_buff.get(int(spec.effect))
            if current is None or int(spell["id"]) > int(current["id"]):
                best_buff[int(spec.effect)] = spell
        elif spec is not None and spec.kind == "debuff" and int(spec.effect) > 0:
            current = best_debuff.get(int(spec.effect))
            if current is None or int(spell["id"]) > int(current["id"]):
                best_debuff[int(spec.effect)] = spell
        elif is_nuke(spell):
            kit["nuke"].append(spell)
    kit["cure"].sort(key=lambda spell: (int(spell.get("mp") or 0), int(spell["id"])))
    kit["buff"] = sorted(
        best_buff.values(),
        key=lambda spell: (BUFF_PRIORITY.get(int(effect_of(spell).effect), 50),
                           int(spell["id"])))
    kit["debuff"] = sorted(
        best_debuff.values(),
        key=lambda spell: (0 if effect_of(spell).damage else 1,
                           int(spell["id"])))
    kit["nuke"].sort(key=lambda spell: (int(spell.get("base") or 0), int(spell["id"])))
    kit["caster"] = bool(kit["cure"] or kit["buff"] or kit["debuff"] or kit["nuke"])
    kit["pure_caster"] = is_pure_caster(job)
    return kit


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
