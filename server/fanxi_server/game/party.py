"""Party and alliance membership, as the client's group packets describe it.

The zone protocol keeps the roster on the server and only mirrors it to the clients:
``0x0C8`` (GROUP_TBL) says who is in which party, ``0x0DD`` (GROUP_LIST) carries one
member's row, and ``0x0DF`` (GROUP_ATTR) updates a member's vitals.  This module is the
data half; :mod:`fanxi_server.game.packets` builds the wire bodies and
:class:`fanxi_server.game.world.World` owns the live objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# PartyKind, the low nibble of the invite packet's Kind field.
PARTY_KIND_PARTY = 0
PARTY_KIND_ALLIANCE = 5

PARTY_MAX = 6
# Every client sees the local player as targid 0x400; other players get 0x401+.
SELF_TARGID = 0x400
ALLIANCE_MAX_PARTIES = 3

# PARTYFLAG, the same bits the client reads in GROUP_TBL/GROUP_LIST.
PARTY_SECOND = 0x0001
PARTY_THIRD = 0x0002
PARTY_LEADER = 0x0004
ALLIANCE_LEADER = 0x0008
PARTY_QUARTERMASTER = 0x0010
PARTY_SYNC = 0x0100
PARTY_MOGHOUSE = 0x0200


def party_number_flag(number: int) -> int:
    """The PARTY_SECOND/PARTY_THIRD bit for a party's slot in an alliance."""
    number = int(number)
    if number == 1:
        return PARTY_SECOND
    if number == 2:
        return PARTY_THIRD
    return 0


def gauge_percent(value: int, maximum: int) -> int:
    """A 0-100 HP/MP fill.  A zero maximum reads as full, as on the other packets."""
    value, maximum = int(value), int(maximum)
    if maximum <= 0:
        return 100
    return max(0, min(100, (value * 100 + maximum // 2) // maximum))


@dataclass
class PartyMember:
    """One player's party row.  It is a snapshot the World refreshes per session."""

    char_id: int
    name: str
    zone: int = 0
    targid: int = 0
    hp: int = 0
    mp: int = 0
    tp: int = 0
    hp_max: int = 1
    mp_max: int = 0
    main_job: int = 0
    main_level: int = 0
    sub_job: int = 0
    sub_level: int = 0
    moghouse: bool = False
    # The account that owns this character.  It is what lets a returning main account
    # recognise the party its subs kept while it was away.
    account_id: int = 0

    @classmethod
    def from_session(cls, session) -> "PartyMember":
        c = session.char
        return cls(
            char_id=int(c["char_id"]),
            name=str(c.get("name") or ""),
            zone=int(getattr(session, "zone", c.get("zone", 0)) or 0),
            targid=int(getattr(session, "targid", 0) or 0),
            hp=int(c.get("hp_current", c.get("hp", 0)) or 0),
            mp=int(c.get("mp_current", c.get("mp", 0)) or 0),
            tp=int(c.get("tp", 0) or 0),
            hp_max=max(1, int(c.get("hp", 1) or 1)),
            mp_max=max(0, int(c.get("mp", 0) or 0)),
            main_job=int(c.get("main_job", 0) or 0),
            main_level=int(c.get("main_level", 0) or 0),
            sub_job=int(c.get("sub_job", 0) or 0),
            sub_level=int(c.get("sub_level", 0) or 0),
            moghouse=bool(int(c.get("moghouse", 0) or 0)),
            account_id=int(c.get("account_id", 0) or 0),
        )

    def update_from_session(self, session) -> None:
        self.zone = int(getattr(session, "zone", self.zone) or self.zone)
        self.targid = int(getattr(session, "targid", self.targid) or self.targid)
        self.name = str(session.char.get("name") or self.name)
        self.hp = int(session.char.get("hp_current", session.char.get("hp", self.hp)) or 0)
        self.mp = int(session.char.get("mp_current", session.char.get("mp", self.mp)) or 0)
        self.tp = int(session.char.get("tp", self.tp) or 0)
        self.hp_max = max(1, int(session.char.get("hp", self.hp_max) or self.hp_max))
        self.mp_max = max(0, int(session.char.get("mp", self.mp_max) or self.mp_max))
        self.main_job = int(session.char.get("main_job", self.main_job) or self.main_job)
        self.main_level = int(session.char.get("main_level", self.main_level) or self.main_level)
        self.sub_job = int(session.char.get("sub_job", self.sub_job) or self.sub_job)
        self.sub_level = int(session.char.get("sub_level", self.sub_level) or self.sub_level)
        self.moghouse = bool(int(session.char.get("moghouse", 0) or 0))
        self.account_id = int(session.char.get("account_id", self.account_id) or self.account_id)

    @property
    def hpp(self) -> int:
        return gauge_percent(self.hp, self.hp_max)

    @property
    def mpp(self) -> int:
        return gauge_percent(self.mp, self.mp_max)

    def identity(self) -> tuple:
        """The fields that need a full GROUP_TBL/GROUP_LIST resend, not a 0x0DF tick."""
        return (self.zone, self.name, self.main_job, self.main_level,
                self.sub_job, self.sub_level, self.targid, self.moghouse)

    def vitals(self) -> tuple[int, int, int]:
        return (self.hp, self.mp, self.tp)


@dataclass
class Party:
    id: int
    leader_id: int
    members: list[PartyMember] = field(default_factory=list)
    number: int = 0
    alliance: "Alliance | None" = None

    def member(self, char_id: int) -> PartyMember | None:
        char_id = int(char_id)
        for member in self.members:
            if member.char_id == char_id:
                return member
        return None

    def is_full(self) -> bool:
        return len(self.members) >= PARTY_MAX

    def is_empty(self) -> bool:
        return not self.members

    def promote_leader(self) -> None:
        self.leader_id = self.members[0].char_id if self.members else 0

    def flags(self, member: PartyMember) -> int:
        flags = party_number_flag(self.number)
        if member.char_id == self.leader_id:
            flags |= PARTY_LEADER
        if self.alliance is not None and self.alliance.main is self \
                and member.char_id == self.leader_id:
            flags |= ALLIANCE_LEADER
        if member.moghouse:
            flags |= PARTY_MOGHOUSE
        return flags


@dataclass
class Alliance:
    id: int
    parties: list[Party] = field(default_factory=list)

    @property
    def main(self) -> Party | None:
        return self.parties[0] if self.parties else None

    @property
    def leader_id(self) -> int:
        main = self.main
        return main.leader_id if main else 0

    @property
    def full(self) -> bool:
        return len(self.parties) >= ALLIANCE_MAX_PARTIES

    def number_of(self, party: Party) -> int:
        try:
            return self.parties.index(party)
        except ValueError:
            return 0

    def used_numbers(self) -> set[int]:
        return {party.number for party in self.parties}


@dataclass
class PendingInvite:
    inviter_id: int
    inviter_targid: int
    kind: int
    expires: float
