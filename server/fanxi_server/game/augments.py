"""The 24-byte item ``extdata`` block the client decodes into augment lines.

Retail packs augments into the ``0x020`` item-attribute block.  For Odyssey gear
(and Dynamis-D JSE necks, Unity belts) the block is LandSandBoat's
``Exdata::AugmentBundle`` -- one augment "bundle" shared by several items, with
the rank and the bundle index in the block:

    offset 0   u8   kind       3   (bundled augments)
    offset 1   u8   subkind    0x83 (standard | evolith)
    offset 2   u16  padding
    offset 4   u32  bitfield
                    bits  0-1   type          (2 bits)
                    bits  2-17  accumulated RP
                    bits 18-22  rank          (0-30)
                    bits 23-24  max rank tier (0=15, 1=20, 2=25, 3=30)
                    bit  25     padding
                    bits 26-27  RP curve
                    bits 28-31  padding
    offset 8   u32  augment index   (which bundle of effects)
    offset 12  u8[12] signature

This layout is confirmed against a retail rank-25 JSE neck,
``03 83 00 00 78 2D 64 03 CC 00 00 00``: the bitfield decodes to type 0,
rank 25, max tier 2 (25), and bundle 204 -- exactly that item's build.

The one value Fanxi does not have yet is the per-item *augment index*: retail's
server carries it in its item data, LandSandBoat leaves Odyssey augmentation
unimplemented, and the client's bundle table lives in a DAT file Fanxi has not
parsed.  Until the index is known the block is well formed but names no effects,
so the client has nothing to print.
"""

from __future__ import annotations

import struct

PATHS = "ABCD"
RANK_MAX = 30
TIERS = {15: 0, 20: 1, 25: 2, 30: 3}


def bundle(path: str = "A", rank: int = RANK_MAX, tier: int = 3,
           index: int = 0, rp: int = 0, curve: int = 0) -> bytes:
    """A 24-byte ``AugmentBundle`` block.  *tier* 3 is the 30-rank unlock."""
    letter = str(path or "A").strip().upper()[:1]
    if letter not in PATHS:
        raise ValueError("path must be one of A, B, C, D")
    try:
        rank = int(rank)
        tier = int(tier)
        index = int(index)
    except (TypeError, ValueError):
        raise ValueError("rank, tier and index must be numbers") from None
    if not 1 <= rank <= RANK_MAX:
        raise ValueError("rank must be 1..%d" % RANK_MAX)
    if tier not in TIERS.values():
        raise ValueError("tier must be 0..3")
    value = ((PATHS.index(letter) & 0x03)
             | ((int(rp) & 0xFFFF) << 2)
             | ((rank & 0x1F) << 18)
             | ((tier & 0x03) << 23)
             | ((int(curve) & 0x03) << 26))
    data = bytearray(24)
    data[0] = 0x03
    data[1] = 0x83
    struct.pack_into("<I", data, 4, value)
    struct.pack_into("<I", data, 8, index & 0xFFFFFFFF)
    return bytes(data)


def decode(extra: bytes | None) -> dict | None:
    """Read back a bundle block (used by ``!augment`` and the tests)."""
    if not extra or len(extra) < 12:
        return None
    raw = bytes(extra)
    if raw[0] != 0x03 or raw[1] != 0x83:
        return None
    value = struct.unpack_from("<I", raw, 4)[0]
    return {
        "path": PATHS[value & 0x03],
        "rank": (value >> 18) & 0x1F,
        "tier": (value >> 23) & 0x03,
        "rp": (value >> 2) & 0xFFFF,
        "curve": (value >> 26) & 0x03,
        "index": struct.unpack_from("<I", raw, 8)[0],
    }


def describe(extra: bytes | None) -> str:
    build = decode(extra)
    if build is None:
        return "not augmented"
    return "Rank %d (tier %d, path %s), bundle %d" % (
        build["rank"], build["tier"], build["path"], build["index"])
