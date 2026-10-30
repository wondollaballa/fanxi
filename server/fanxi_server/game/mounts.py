"""Every mount the game knows, from the client's own mount table.

A mount is not an item and not an entity.  FINAL FANTASY XI added mounts in the April 2016
version update: the client owns the mount models and their menu, and the server only says
which ones are unlocked and which one a character is riding.

The table below is the client's `mounts.names` string table (NA file id 55681, JP 55561,
descriptions 55682/55562) — the same strings the game's Mount menu draws.  An entry's index
is its **mount id**, and the id is what the wire carries:

* `0x0AE` sends eight bytes of bits; bit *n* unlocks mount *n*.  Fanxi unlocks all of them.
* `0x037` (the local player's server status) has `mount_id` at body `0x6F`; `Chocobo_Index`
  (Flags0 bits 13-15) is 1 while a chocobo mount is out, which is how mount 0 is told apart
  from "not mounted".
* `0x00D` (other players) carries the same id in Flags6 bits 4-11 (body `0x40`).

The catalog is checked against `tools/client_mount_names.tsv` (the snapshot dumped from a
retail install by `tools/dump_client_mounts.c`) by `server/tests/test_mounts.py`, so a client
that adds a mount shows up as a test failure instead of a silent mismatch.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: The id of the personal chocobo.  Mount 0 is the one mount whose id doubles as "none", so
#: the client only shows it when 0x037's Chocobo_Index says a chocobo is out.
CHOCOBO_ID = 0

#: The mounts the client draws with its chocobo animation and its chocobo seat.  Noble
#: Chocobo (33) is a chocobo model too, but its index is its own (see chocobo_index).
CHOCOBO_IDS = (0, 33)

#: Noble Chocobo's own id, the one chocobo with a model hint in CustomProperties.
NOBLE_CHOCOBO_ID = 33

#: Ids the client's mount table has room for (0x0AE is eight bytes of bits).
MAX_MOUNT_ID = 63

#: The status effect the client knows a rider by (LandSandBoat's StatusEffect::Mounted).
#: It rides in 0x037's BufStatus next to the animation; without it the client will not
#: put the character on the mount model.
MOUNTED_EFFECT = 252

#: Weapon-stance-free entity animations (LandSandBoat's data/enums/animation.yaml).  The
#: animation is what tells the client to draw the rider on a mount; the id in
#: Flags6/mount_id picks which one.  85 is the generic mount, 5 is a chocobo.
MOUNT_ANIMATION = 85
CHOCOBO_ANIMATION = 5


@dataclass(frozen=True)
class Mount:
    """One mount: the client's id, its two-table name and the spelling people type."""

    id: int
    name: str
    description: str
    japanese: str
    aliases: tuple[str, ...] = field(default=())

    @property
    def key(self) -> str:
        """The name as a stable key: lower case, runs of punctuation folded to one space."""
        return _fold(self.name)

    def chocobo_index(self) -> int:
        """0x037/0x00D's Chocobo_Index while this mount is out.

        The index is mostly a chocobo-seat selector (1 is the ordinary chocobo, 2 a
        personalised one, 4 the Noble Chocobo); for every other mount the id and the mount
        animation pick the model, and 0 keeps the rider seated the normal way.  Mount 0 has
        to carry 1 or the client cannot tell the personal chocobo from standing on foot.
        """
        if self.id == CHOCOBO_ID:
            return 1
        if self.id == NOBLE_CHOCOBO_ID:
            return 4  # LandSandBoat's capture value: (34 % 8) + 2
        return 0

    def custom_properties(self) -> tuple[int, int]:
        """0x00D's CustomProperties while this mount is out.

        Ordinary mounts leave both words clear.  The Noble Chocobo is the one model the
        client needs a hint for: its second word must be 1 or it draws the plain chocobo.
        """
        if self.id == NOBLE_CHOCOBO_ID:
            return (0, 1)
        return (0, 0)

    def animation(self) -> int:
        """The entity animation while this mount is out: a chocobo or a mount."""
        return CHOCOBO_ANIMATION if self.id in CHOCOBO_IDS else MOUNT_ANIMATION


# id, name, description, Japanese name — tools/client_mount_names.tsv, in id order.
_TABLE = (
    (0, "Chocobo", "Calls forth your personal chocobo.", "マイチョコボ", ("choco", "personal chocobo")),
    (1, "Raptor", "Calls forth a raptor.", "ラプトル", ()),
    (2, "Tiger", "Calls forth a tiger.", "剣虎", ()),
    (3, "Crab", "Calls forth a crab.", "クラブ", ()),
    (4, "Red Crab", "Calls forth a red crab.", "赤クラブ", ()),
    (5, "Bomb", "Calls forth a bomb.", "ボム", ()),
    (6, "Sheep", "Calls forth a sheep.", "大羊", ()),
    (7, "Morbol", "Calls forth a morbol.", "モルボル", ()),
    (8, "Crawler", "Calls forth a crawler.", "クロウラー", ()),
    (9, "Fenrir", "Calls forth Fenrir.", "フェンリル", ()),
    (10, "Beetle", "Calls forth a beetle.", "甲虫", ()),
    (11, "Moogle", "Calls forth a moogle.", "モーグリ", ()),
    (12, "Magic Pot", "Calls forth a magic pot.", "マジックポット", ("pot",)),
    (13, "Tulfaire", "Calls forth a tulfaire.", "トゥルフェイア", ()),
    (14, "Warmachine", "Calls forth a warmachine.", "ウォーマシン", ("war machine",)),
    (15, "Xzomit", "Calls forth a xzomit.", "ゾミト", ()),
    (16, "Hippogryph", "Calls forth a hippogryph.", "ヒポグリフ", ("hippogriff",)),
    (17, "Spectral Chair", "Calls forth a spectral chair.", "悪霊の椅子", ("chair",)),
    (18, "Spheroid", "Calls forth a spheroid.", "スフィアロイド", ()),
    (19, "Omega", "Calls forth Omega.", "オメガ", ()),
    (20, "Coeurl", "Calls forth a coeurl.", "クァール", ()),
    (21, "Goobbue", "Calls forth a goobbue.", "グゥーブー", ()),
    (22, "Raaz", "Calls forth a raaz.", "ラズ", ()),
    (23, "Levitus", "Calls forth the Levitus.", "レヴィデイス", ()),
    (24, "Adamantoise", "Calls forth an adamantoise.", "アダマンタス", ("turtle",)),
    (25, "Dhalmel", "Calls forth a dhalmel.", "ダルメル", ()),
    (26, "Doll", "Calls forth a doll.", "ドール", ()),
    (27, "Golden Bomb", "Calls forth a golden bomb.", "ゴールデンボム", ("gold bomb",)),
    (28, "Buffalo", "Calls forth a buffalo.", "バッファロー", ()),
    (29, "Wivre", "Calls forth a wivre.", "ウィヴル", ()),
    (30, "Red Raptor", "Calls forth a red raptor.", "赤ラプトル", ()),
    (31, "Iron Giant", "Calls forth an iron giant.", "鉄巨人", ()),
    (32, "Byakko", "Calls forth Byakko.", "白虎", ()),
    (33, "Noble Chocobo", "Calls forth a noble chocobo.", "ノーブルチョコボ", ()),
    (34, "Ixion", "Calls forth an ixion.", "イクシオン", ()),
    (35, "Phuabo", "Calls forth a phuabo.", "フワボ", ()),
    (36, "Craklaw", "Calls forth a craklaw.", "クラックロー", ("cracklaw",)),
    (37, "Alicorn", "Calls forth an alicorn.", "アリコーン", ()),
    (38, "Bubble Crab", "Calls forth a bubble crab.", "バブルクラブ", ("bubblecrab",)),
)

MOUNTS: tuple[Mount, ...] = tuple(Mount(i, name, desc, ja, aliases)
                                 for i, name, desc, ja, aliases in _TABLE)
MOUNT_COUNT = len(MOUNTS)

BY_ID: dict[int, Mount] = {mount.id: mount for mount in MOUNTS}


def _fold(text: str) -> str:
    """A typed name as one lookup key: case, spaces, dashes and underscores do not matter."""
    out, space = [], False
    for ch in str(text or "").strip().casefold():
        if ch.isalnum():
            out.append(ch)
            space = False
        elif ch in " _-'\u2019\u266a":
            if out and not space:
                out.append(" ")
                space = True
        else:
            out.append(ch)
    return "".join(out).strip()


_KEYS: dict[str, Mount] = {}
for _mount in MOUNTS:
    _KEYS[_mount.key] = _mount
    for _alias in _mount.aliases:
        _KEYS.setdefault(_fold(_alias), _mount)
# The client table spells a few names its own way; accept the wiki spelling too.
_KEYS.setdefault("craklaw", BY_ID[36])
_KEYS.setdefault("cracklaw", BY_ID[36])


def all_mounts() -> tuple[Mount, ...]:
    return MOUNTS


def count() -> int:
    return MOUNT_COUNT


def by_id(mount_id: int) -> Mount | None:
    try:
        return BY_ID.get(int(mount_id))
    except (TypeError, ValueError):
        return None


def names() -> list[str]:
    return [mount.name for mount in MOUNTS]


def find(query: str) -> tuple[Mount | None, str]:
    """The mount a typed name or id means.

    Returns ``(mount, "")`` on a hit and ``(None, message)`` when the text is unknown or
    names more than one mount (``//mount red`` is both crabs, so say which).
    """
    text = str(query or "").strip()
    if not text:
        return None, "Which mount? Try //mount list."
    try:
        wanted = int(text, 0)
    except ValueError:
        wanted = None
    if wanted is not None:
        mount = by_id(wanted)
        if mount is not None:
            return mount, ""
        if 0 <= wanted < MAX_MOUNT_ID:
            return None, "Mount %d is not in this client's mount table (0-%d)." % (
                wanted, MOUNT_COUNT - 1)
        return None, "Mount ids run 0-%d." % (MOUNT_COUNT - 1)
    key = _fold(text)
    if key.endswith(" mount"):
        key = key[:-len(" mount")]
    mount = _KEYS.get(key)
    if mount is not None:
        return mount, ""
    prefix = [m for m in MOUNTS
              if m.key.startswith(key) or any(a.startswith(key) for a in map(_fold, m.aliases))]
    if len(prefix) == 1:
        return prefix[0], ""
    if len(prefix) > 1:
        return None, "%r matches %s; name one of them." % (
            text, ", ".join(m.name for m in prefix))
    return None, "There is no mount called %r. Try //mount list." % text


def bitfield(unlocked: list[int] | None = None) -> bytes:
    """0x0AE's eight-byte MountDataTbl: one bit per unlocked mount.

    ``unlocked=None`` unlocks every mount the client has, which is what a Fanxi character
    gets; a list is for a server that wants to hand them out one at a time.
    """
    bits = bytearray(8)
    ids = range(MOUNT_COUNT) if unlocked is None else unlocked
    for mount_id in ids:
        mid = int(mount_id)
        if 0 <= mid <= MAX_MOUNT_ID:
            bits[mid // 8] |= 1 << (mid % 8)
    return bytes(bits)


def unlocked_ids() -> list[int]:
    """Every mount id this client's table has, in id order."""
    return [mount.id for mount in MOUNTS]


def is_chocobo(mount: Mount | int | None) -> bool:
    if not isinstance(mount, Mount):
        mount = by_id(-1 if mount is None else mount)
    return bool(mount and mount.id == CHOCOBO_ID)
