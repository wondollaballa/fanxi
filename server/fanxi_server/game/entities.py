"""State for a placed NPC or monster.

The rows in ``world_npcs`` / ``monster_spawns`` are content definitions; a ``ZoneEntity`` is the live
instance a zone session sees. Mobs keep their health, position and combat timers here.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field

from . import trust_stats


@dataclass
class ZoneEntity:
    kind: str                    # "npc" or "mob"
    id: int                      # 32-bit entity id the client uses
    targid: int                  # 12-bit index in the zone
    zone: int
    name: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rot: int = 0
    model: int = 50
    size: int = 0
    door_id: int = 0
    # A door's role from world_npcs.door_kind: "" for a normal door, "drawbridge" for a
    # moving bridge that the world times instead of a player opening it.
    door_kind: str = ""
    look: bytes = b""
    name_prefix: int = 0
    namevis: int = 0
    status: int = 0
    flags: int = 0
    speed: int = 50
    animation: int = 0
    triggerable: bool = True
    widescan: bool = True
    script: str = ""
    dialogue: list[str] = field(default_factory=list)
    hp_index: int = -1
    # trust fields (a Trust is an NPC-sized ally owned by one player)
    owner_char_id: int = 0
    trust_spell: int = 0
    job: int = 1
    sub_job: int = 0
    race: int = 1
    damage_mult: int = 100
    passive: bool = False
    # Live spell state: the spells this Trust unlocked, the grouped kit the AI reads,
    # the cast in progress, and the aura a passive Trust keeps on its owner.
    spells: list[dict] = field(default_factory=list)
    kit: dict = field(default_factory=dict)
    casting: dict | None = None
    next_cast_at: float = 0.0
    next_mp_tick: float = 0.0
    trust_has_acted: bool = False
    aura_effect: int = 0
    # mob fields
    template_id: int = 0
    level: int = 1
    # Retail Locus spawns roll their level in this range and interpolate HP between
    # the published level_min and level_max values; fixed-level mobs leave level_rolls
    # false and keep the old single template HP.
    level_min: int = 0
    level_max: int = 0
    level_rolls: bool = False
    hp_min: int = 0
    hp_high: int = 0
    # Per-level retail rows: {"135": {"hp": 289900, "defense": 1346, "evasion": 1224}}.
    # The Defense/Evasion values replace the 99-capped build_monster curve for the
    # Locus camps whose tables have been published; empty for everything else.
    level_stats: dict[int, dict] = field(default_factory=dict)
    defense_override: int = 0
    evasion_override: int = 0
    hp_max: int = 1
    hp: int = 1
    mp_max: int = 0
    mp: int = 0
    attack: int = 1
    defense: int = 0
    accuracy: int = 75
    evasion: int = 10
    attack_delay_ms: int = 3000
    aggro: bool = False
    links: bool = False
    roam_radius: float = 0.0
    respawn_seconds: int = 30
    behavior: str = "roam"
    spawn_x: float = 0.0
    spawn_y: float = 0.0
    spawn_z: float = 0.0
    # live state
    alive: bool = True
    respawn_at: float = 0.0
    corpse_until: float = 0.0
    engaged_char_id: int | None = None
    # Who the client should show as the claimer (the red name).  Kept after death so the
    # corpse stays red until it despawns; the hate target (engaged_char_id) is cleared.
    claim_char_id: int | None = None
    next_attack_at: float = 0.0
    # Enmity per character id.  ``enmity`` is the combined CE + VE total the target
    # picker reads; ``enmity_ve`` is the volatile half, which decays and is the part that
    # lets a tank lose the monster again.  The first source of hate on a mob also gets
    # retail's 200 CE + 900 VE claim bonus, which is why a single spell pulls.
    enmity: dict[int, int] = field(default_factory=dict)
    enmity_ve: dict[int, int] = field(default_factory=dict)
    enmity_decay_at: float = 0.0
    last_move_at: float = 0.0
    roam_target: tuple[float, float] | None = None
    roam_pause_until: float = 0.0
    moving: bool = False
    roam_heading: float = 0.0
    last_sync_at: float = 0.0
    # A turn is the one correction the client cannot interpolate; the next position
    # packet must bypass the ambient budget instead of waiting behind other mobs.
    pending_turn: bool = False
    # Navigation state.  ``nav_goal`` is the point the current path was planned to;
    # a moving target (the player a monster is chasing) invalidates it.  The cooldown
    # stops an unreachable player from costing an A* search every tick.
    nav_path: list[tuple[float, float, float]] = field(default_factory=list)
    nav_goal: tuple[float, float, float] | None = None
    nav_planned_at: float = 0.0
    nav_blocked_until: float = 0.0
    aggro_announced: bool = False
    dialogue_index: int = 0
    # Debuffs a player has landed.  The client draws them from the action result; the
    # server keeps the timer and the numbers the AI reads.
    status_effects: list[int] = field(default_factory=list)
    effect_state: dict[int, dict] = field(default_factory=dict)
    # A monster's live skillchain state (opening properties or the formed chain).
    skillchain: object = None
    # TP moves.  ``skill_list_id`` is the LandSandBoat family list (migration 0148),
    # ``tp`` is 0..3000 and ``tp_threshold`` is the random bar the controller waits for
    # after each move.  ``pending_skill`` holds the readied move while its prepare time
    # runs, so the start and finish packets are one action rather than two swings.
    skill_list_id: int = 0
    tp: int = 0
    tp_threshold: int = 0
    pending_skill: dict | None = None

    def hpp(self) -> int:
        if self.hp_max <= 0:
            return 0
        return max(0, min(100, int(round(self.hp * 100.0 / self.hp_max))))

    def distance_to(self, x: float, y: float, z: float) -> float:
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2 + (self.z - z) ** 2)

    def is_mob(self) -> bool:
        return self.kind == "mob"

    def is_trust(self) -> bool:
        return self.kind == "trust"

    def is_pet(self) -> bool:
        return self.kind == "pet"

    def reset_mob(self, now: float, rng: random.Random | None = None) -> None:
        self.alive = True
        if self.level_rolls and self.level_max > self.level_min:
            rng = rng or random
            self.level = rng.randint(self.level_min, self.level_max)
            exact = self.level_stats.get(self.level) or {}
            if exact:
                self.hp_max = int(exact.get("hp") or self.hp_max)
                self.defense_override = int(exact.get("defense") or 0)
                self.evasion_override = int(exact.get("evasion") or 0)
            else:
                self.hp_max = mob_hp_for_level(
                    self.level, self.level_min, self.level_max,
                    self.hp_high or self.hp_max, self.hp_min)
        self.hp = self.hp_max
        self.mp = self.mp_max
        self.x, self.y, self.z = self.spawn_x, self.spawn_y, self.spawn_z
        self.engaged_char_id = None
        self.claim_char_id = None
        self.enmity.clear()
        self.enmity_ve.clear()
        self.enmity_decay_at = 0.0
        self.animation = 0
        self.speed = 12
        self.next_attack_at = 0.0
        self.last_move_at = now
        self.roam_target = None
        self.moving = False
        self.roam_pause_until = now + 2.0
        self.nav_path.clear()
        self.nav_goal = None
        self.nav_planned_at = 0.0
        self.nav_blocked_until = 0.0
        self.aggro_announced = False
        self.respawn_at = 0.0
        self.status_effects.clear()
        self.effect_state.clear()
        self.tp = 0
        self.pending_skill = None
        # A respawn is a new monster: a chain state from its previous life would let
        # the first weapon skill of the next fight close a skillchain nobody opened.
        self.skillchain = None


def npc_from_row(row: dict, targid: int, dialogue: list[str]) -> ZoneEntity:
    zone = int(row["zone"])
    door_kind = str(row.get("door_kind") or "")
    # A drawbridge is spawned lowered and stays that way until a real airship arrival
    # drives it.  The stored animation is not trusted here because an old import left it
    # at 0, which the door spawn turns into 9 (closed/raised).
    animation = 8 if door_kind == "drawbridge" else int(row["animation"])
    return ZoneEntity(
        kind="npc",
        id=0x01000000 | (zone << 12) | (targid & 0xFFF),
        targid=targid,
        zone=zone,
        name=str(row["name"]),
        x=float(row["pos_x"]), y=float(row["pos_y"]), z=float(row["pos_z"]),
        rot=int(row["rot"]), model=int(row["model"]), size=int(row["size"]),
        door_id=int(row.get("door_id", 0) or 0),
        door_kind=door_kind,
        look=bytes.fromhex(row.get("look_hex") or ""),
        name_prefix=int(row["name_prefix"]), namevis=int(row["namevis"]),
        status=int(row["status"]), flags=int(row["flags"]), speed=int(row["speed"]),
        animation=animation, triggerable=bool(row["triggerable"]),
        widescan=bool(row["widescan"]), script=str(row["script"] or ""),
        dialogue=list(dialogue or []),
        hp_index=(int(row["hp_index"]) if row.get("hp_index") is not None else -1),
    )


def mob_hp_for_level(level: int, level_min: int, level_max: int,
                     hp_max: int, hp_min: int = 0) -> int:
    """A monster's max HP at its rolled level.

    Retail prints a level range with a matching HP range (Locus Camelopard:
    135-137 / 289,900-308,300).  ``monster_templates.hp`` is the value at
    ``level_max`` and the optional ``hp_min`` is the value at ``level_min``; a table
    without ``hp_min`` keeps its old flat HP.  The interpolation is linear, which is
    within a few hundred HP of the published per-level rows.
    """
    low = int(level_min)
    high = int(level_max)
    level = max(low, min(high, int(level)))
    hp_max = max(1, int(hp_max))
    hp_min = int(hp_min or 0)
    if hp_min <= 0 or high <= low:
        return hp_max
    ratio = (level - low) / float(high - low)
    return max(1, int(hp_min + (hp_max - hp_min) * ratio))


def mob_from_row(row: dict, targid: int, rng: random.Random | None = None) -> ZoneEntity:
    rng = rng or random.Random()
    zone = int(row["zone"])
    level_min = int(row["level_min"])
    level_max = int(row["level_max"])
    level_rolls = not bool(row.get("level"))
    level = int(row["level"] or rng.randint(level_min, level_max))
    hp_high = max(1, int(row["template_hp"] or level * 24))
    hp_min = int(row.get("template_hp_min") or 0)
    try:
        raw_stats = json.loads(row.get("level_stats") or "{}")
        level_stats = {int(key): dict(value) for key, value in raw_stats.items()
                       if str(key).isdigit()}
    except (TypeError, ValueError, AttributeError):
        level_stats = {}
    exact = level_stats.get(level) or {}
    if exact:
        hp_max = int(exact.get("hp") or hp_high)
    else:
        hp_max = mob_hp_for_level(level, level_min, level_max, hp_high, hp_min)
    return ZoneEntity(
        kind="mob",
        id=0x01000000 | (zone << 12) | (targid & 0xFFF),
        targid=targid,
        zone=zone,
        name=str(row["name"] or row["template_name"]),
        x=float(row["pos_x"]), y=float(row["pos_y"]), z=float(row["pos_z"]),
        rot=int(row["rot"]), model=int(row["model"]), size=int(row["size"]),
        name_prefix=int(row["name_prefix"]),
        # The client uses this byte to predict a moving entity between position updates;
        # at 50 (retail's run speed) it outran our walk and snapped back each packet.
        speed=12, animation=0, triggerable=True, widescan=True,
        template_id=int(row["template_id"]), level=level,
        level_min=level_min, level_max=level_max, level_rolls=level_rolls,
        hp_min=hp_min, hp_high=hp_high, level_stats=level_stats,
        defense_override=int(exact.get("defense") or 0),
        evasion_override=int(exact.get("evasion") or 0),
        hp_max=max(1, hp_max), hp=max(1, hp_max),
        mp_max=int(row["template_mp"] or 0), mp=int(row["template_mp"] or 0),
        attack=int(row["attack"] or 1), defense=int(row["defense"] or 0),
        accuracy=int(row["accuracy"] or 75), evasion=int(row["evasion"] or 10),
        attack_delay_ms=int(row["attack_delay_ms"] or 3000),
        aggro=bool(row["aggro"]), links=bool(row["links"]),
        roam_radius=float(row["roam_radius"] or 0),
        respawn_seconds=int(row["respawn_seconds"] or row["template_respawn"] or 30),
        behavior=str(row["behavior"] or "roam"),
        spawn_x=float(row["pos_x"]), spawn_y=float(row["pos_y"]), spawn_z=float(row["pos_z"]),
        skill_list_id=int(row.get("skill_list_id") or 0),
        # The first move waits for 1000 TP; after it the world picks a fresh
        # 1000-3000 threshold.  Avoid consuming the spawn RNG here: the zone's
        # roaming and level rolls use the same generator and must stay stable.
        tp_threshold=1000,
        last_move_at=0.0,
    )


def trust_from_row(row: dict, targid: int, zone: int, owner_char_id: int,
                   level: int) -> ZoneEntity:
    """One alter ego from the factual ``trusts`` row.

    The look block is the client's 20-byte NPC model (size, model id, then eight
    equipment models).  Every Trust in the imported data is a fixed-model NPC, so the
    second uint16 is the model id the spawn packet carries.  Level tracks the owner's
    main job, as retail does; HP/MP come from the race/job/subjob table in
    ``trust_stats``, with the species the client-data import put on the row.
    """
    level = max(1, int(level))
    look = bytes.fromhex(row.get("look_hex") or "")
    if len(look) < 20:
        look = bytes(20)
    model = int(row.get("model") or int.from_bytes(look[2:4], "little"))
    delay = max(1, int(row.get("delay") or 240))
    job = int(row.get("job") or 1)
    sub_job = int(row.get("sub_job") or 0)
    race = trust_stats.race_for_species(row.get("species"))
    hp_max, mp_max = trust_stats.vitals(race, job, sub_job, level)
    return ZoneEntity(
        kind="trust", id=0x01000000 | (int(zone) << 12) | (int(targid) & 0xFFF),
        targid=int(targid) & 0xFFF, zone=int(zone), name=str(row["name"]),
        model=model, size=0, look=look, speed=62, animation=0,
        triggerable=False, widescan=True, name_prefix=int(row.get("name_prefix") or 0),
        namevis=0, level=level, hp_max=hp_max, hp=hp_max, mp_max=mp_max, mp=mp_max,
        attack_delay_ms=max(1500, delay * 1000 // 60),
        owner_char_id=int(owner_char_id), trust_spell=int(row["spell_id"]),
        job=job, sub_job=sub_job, race=race,
        damage_mult=int(row.get("damage_mult") or 100),
        passive=bool(int(row.get("passive") or 0)),
        last_move_at=0.0,
    )
