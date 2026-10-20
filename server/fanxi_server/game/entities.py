"""State for a placed NPC or monster.

The rows in ``world_npcs`` / ``monster_spawns`` are content definitions; a ``ZoneEntity`` is the live
instance a zone session sees. Mobs keep their health, position and combat timers here.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


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
    # mob fields
    template_id: int = 0
    level: int = 1
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
    engaged_char_id: int | None = None
    next_attack_at: float = 0.0
    last_move_at: float = 0.0
    aggro_announced: bool = False
    dialogue_index: int = 0

    def hpp(self) -> int:
        if self.hp_max <= 0:
            return 0
        return max(0, min(100, int(round(self.hp * 100.0 / self.hp_max))))

    def distance_to(self, x: float, y: float, z: float) -> float:
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2 + (self.z - z) ** 2)

    def is_mob(self) -> bool:
        return self.kind == "mob"

    def reset_mob(self, now: float) -> None:
        self.alive = True
        self.hp = self.hp_max
        self.mp = self.mp_max
        self.x, self.y, self.z = self.spawn_x, self.spawn_y, self.spawn_z
        self.engaged_char_id = None
        self.next_attack_at = 0.0
        self.last_move_at = now
        self.aggro_announced = False
        self.respawn_at = 0.0


def npc_from_row(row: dict, targid: int, dialogue: list[str]) -> ZoneEntity:
    zone = int(row["zone"])
    return ZoneEntity(
        kind="npc",
        id=0x01000000 | (zone << 12) | (targid & 0xFFF),
        targid=targid,
        zone=zone,
        name=str(row["name"]),
        x=float(row["pos_x"]), y=float(row["pos_y"]), z=float(row["pos_z"]),
        rot=int(row["rot"]), model=int(row["model"]), size=int(row["size"]),
        name_prefix=int(row["name_prefix"]), namevis=int(row["namevis"]),
        status=int(row["status"]), flags=int(row["flags"]), speed=int(row["speed"]),
        animation=int(row["animation"]), triggerable=bool(row["triggerable"]),
        widescan=bool(row["widescan"]), script=str(row["script"] or ""),
        dialogue=list(dialogue or []),
    )


def mob_from_row(row: dict, targid: int, rng: random.Random | None = None) -> ZoneEntity:
    rng = rng or random.Random()
    zone = int(row["zone"])
    level = int(row["level"] or rng.randint(int(row["level_min"]), int(row["level_max"])))
    hp_max = int(row["template_hp"] or level * 24)
    return ZoneEntity(
        kind="mob",
        id=0x01000000 | (zone << 12) | (targid & 0xFFF),
        targid=targid,
        zone=zone,
        name=str(row["name"] or row["template_name"]),
        x=float(row["pos_x"]), y=float(row["pos_y"]), z=float(row["pos_z"]),
        rot=int(row["rot"]), model=int(row["model"]), size=int(row["size"]),
        name_prefix=int(row["name_prefix"]),
        speed=50, animation=0, triggerable=True, widescan=True,
        template_id=int(row["template_id"]), level=level, hp_max=max(1, hp_max), hp=max(1, hp_max),
        mp_max=int(row["template_mp"] or 0), mp=int(row["template_mp"] or 0),
        attack=int(row["attack"] or 1), defense=int(row["defense"] or 0),
        accuracy=int(row["accuracy"] or 75), evasion=int(row["evasion"] or 10),
        attack_delay_ms=int(row["attack_delay_ms"] or 3000),
        aggro=bool(row["aggro"]), links=bool(row["links"]),
        roam_radius=float(row["roam_radius"] or 0),
        respawn_seconds=int(row["respawn_seconds"] or row["template_respawn"] or 30),
        behavior=str(row["behavior"] or "roam"),
        spawn_x=float(row["pos_x"]), spawn_y=float(row["pos_y"]), spawn_z=float(row["pos_z"]),
        last_move_at=0.0,
    )
