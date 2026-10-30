"""Charged item timers (Dispense pouches, quivers and enchantments).

The client stores a charged item's state in the 24-byte extdata block the server sends
with ``0x020``.  The layout is the one LandSandBoat calls ``ItemTimerInfo``:

    0      header      0x01 for a charged item
    1      charges     remaining charges
    2..3   flags       client flags; the server rebuilds these on every packet
    4..7   time1       Vana'diel timestamp (Unix seconds - the Vana'diel epoch)
    8..11  time2       use-delay timestamp
    12..23 signature   unused here

``time1`` is the item's last use.  ``0x020`` sends ``last use + reuse`` as the next-use
timestamp and leaves the timer fields zero when the charge is ready.  The block lives in
``char_inventory.extra`` on the pouch's own row, so the timer follows the item across
bags, logout and server restarts.
"""
from __future__ import annotations

import struct

ITEM_TIMER_HEADER = 0x01
ITEM_TIMER_SIZE = 24

# The high byte of Attr[2..3] on a charged item.  The client always expects 0x80; the
# other bits are its ready/empty/partial-charge indicators.
FLAG_BASE = 0x80
FLAG_READY = 0x40
FLAG_EMPTY = 0x20
FLAG_PARTIAL = 0x10


def read_timer(extra: bytes | None) -> tuple[int, int] | None:
    """Return ``(charges, last_use_vana)`` for a timer block, or None for other extdata."""
    raw = bytes(extra or b"")
    if len(raw) < ITEM_TIMER_SIZE or raw[0] != ITEM_TIMER_HEADER:
        return None
    return int(raw[1]), int(struct.unpack_from("<I", raw, 4)[0])


def encode_timer(charges: int, last_use_vana: int) -> bytes:
    """Pack a timer block for ``char_inventory.extra``."""
    body = bytearray(ITEM_TIMER_SIZE)
    body[0] = ITEM_TIMER_HEADER
    body[1] = max(0, min(255, int(charges)))
    struct.pack_into("<I", body, 4, max(0, int(last_use_vana)) & 0xFFFFFFFF)
    return bytes(body)


def cooldown_remaining(extra: bytes | None, *, now: float, reuse_delay: int,
                       vana_epoch: int) -> int:
    """Seconds left on the reuse timer; 0 when the charge is ready."""
    timer = read_timer(extra)
    if timer is None:
        return 0
    _, last_use = timer
    if last_use <= 0:
        return 0
    now_vana = int(now) - int(vana_epoch)
    return max(0, int(last_use) + max(0, int(reuse_delay)) - now_vana)


def charged_attr(extra: bytes | None, *, now: float, max_charges: int,
                 reuse_delay: int, use_delay: int, vana_epoch: int) -> bytes:
    """The 24-byte Attr block a charged item carries on its ``0x020``."""
    max_charges = max(1, int(max_charges))
    timer = read_timer(extra)
    if timer is None:
        charges, last_use = max_charges, 0
    else:
        charges, last_use = timer
    charges = max(0, min(max_charges, charges))
    now_vana = int(now) - int(vana_epoch)

    attr = bytearray(ITEM_TIMER_SIZE)
    attr[0] = ITEM_TIMER_HEADER
    attr[1] = charges
    flags = FLAG_BASE
    if charges <= 0:
        flags |= FLAG_EMPTY
    elif last_use <= 0 or now_vana >= last_use + max(0, int(reuse_delay)):
        flags |= FLAG_READY
    else:
        if charges < max_charges:
            flags |= FLAG_PARTIAL
        struct.pack_into("<I", attr, 4, (last_use + max(0, int(reuse_delay))) & 0xFFFFFFFF)
        struct.pack_into("<I", attr, 8,
                         (now_vana + max(0, int(use_delay))) & 0xFFFFFFFF)
    attr[3] = flags
    return bytes(attr)


def record_use(extra: bytes | None, *, now: float, max_charges: int,
               vana_epoch: int) -> bytes:
    """Return the timer block after one use.

    A one-charge dispenser keeps its charge (the reuse timer is the gate); a multi-charge
    item loses one charge.  The last-use timestamp starts the reuse timer.
    """
    max_charges = max(1, int(max_charges))
    timer = read_timer(extra)
    charges = max_charges if timer is None else max(0, min(max_charges, timer[0]))
    if max_charges > 1:
        charges = max(0, charges - 1)
    return encode_timer(charges, max(0, int(now) - int(vana_epoch)))
