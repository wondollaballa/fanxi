"""lldb probe for a frozen host64: dump the guest state and the CXiDollActor walks.

Run through tools/freeze_capture.py, not directly:

    lldb --batch -p <pid> \
        -o "script import sys; sys.path.insert(0,'tools'); import freeze_probe; freeze_probe.run('/path/out.txt')" \
        -o "detach"

The client is already wedged, so the probe only attaches, records and detaches; it never kills
or restarts it.  It writes:

  - the guest registers (Guest struct),
  - the [node+0x54] chain from the node each walk is holding,
  - phase A: the actors handed to f_10083d00 (its first argument) over consecutive calls,
  - phase B: the nodes handed to f_10085270 (the next-doll walker) over consecutive hops.

Phase A is the freeze itself: f_10158ca0 follows nearest-actor answers with no visited set, so
the sequence is the cycle.

  - two pointers alternating (A, B, A, B, ...) -> mutual nearest neighbours: A's nearest match is
    B and B's is A (the expected shape)
  - one pointer back-to-back (X, X, X, ...)     -> the search accepts the reference itself
  - a fresh pointer every time                  -> the chain is terminating and the freeze is
    elsewhere
"""
import struct
import threading

import lldb

A_HITS = 32
B_HITS = 24
B_MAX = 256
TOTAL_MAX = 2000

a_seen = []
b_seen = []
notes = []


def should_stop():
    """Stop once the hot loop has been sampled enough.  If the client is stuck inside the
    inner walk, f_10083d00 is never re-entered and phase B stops on its own budget."""
    if len(a_seen) >= A_HITS:
        return True
    if not a_seen and len(b_seen) >= B_HITS:
        return True
    return len(a_seen) + len(b_seen) >= TOTAL_MAX


def rd32(proc, addr):
    if not addr:
        return None
    err = lldb.SBError()
    data = proc.ReadMemory(addr, 4, err)
    if not err.Success() or data is None:
        return None
    if isinstance(data, bytes):
        return struct.unpack("<I", data)[0]
    return data.GetUnsignedInt32(err, 0)


def find_g(thread, depth=12):
    """The Guest* g argument, from the innermost frame that still has it."""
    for i in range(depth):
        frame = thread.GetFrameAtIndex(i)
        var = frame.FindVariable("g")
        if var and var.IsValid():
            return frame, var.GetValueAsUnsigned()
    return None, 0


def cb_a(frame, bp_loc, internal):
    """f_10083d00 entry: its first argument is in eax.  True stops the process."""
    try:
        proc = lldb.target.GetProcess()
        var = frame.FindVariable("g")
        if var and var.IsValid():
            a_seen.append(rd32(proc, var.GetValueAsUnsigned() + 0))
    except Exception as exc:
        notes.append("phase A: %s" % exc)
    return should_stop()


def cb_b(frame, bp_loc, internal):
    """f_10085270 entry: the node is in ecx.  True stops the process."""
    try:
        proc = lldb.target.GetProcess()
        var = frame.FindVariable("g")
        if var and var.IsValid() and len(b_seen) < B_MAX:
            b_seen.append(rd32(proc, var.GetValueAsUnsigned() + 4))
    except Exception as exc:
        notes.append("phase B: %s" % exc)
    return should_stop()


def run(out_path):
    t = lldb.target
    proc = t.GetProcess()
    thread = proc.GetSelectedThread()
    frame, g = find_g(thread)
    base_var = t.FindFirstGlobalVariable("rt_guest_base")
    base = base_var.GetValueAsUnsigned() if base_var and base_var.IsValid() else 0

    lines = []
    lines.append("frame: %s" % (frame.GetFunctionName() if frame else "?"))
    lines.append("g: %#x  rt_guest_base: %#x" % (g, base))
    if g:
        names = [(0, "eax"), (4, "ecx"), (8, "edx"), (12, "ebx"),
                 (16, "esp"), (20, "ebp"), (24, "esi"), (28, "edi")]
        regs = {name: rd32(proc, g + off) for off, name in names}
        lines.append("registers: " + " ".join(
            "%s=%s" % (k, ("%#x" % v) if v is not None else "?") for k, v in regs.items()))

    def rdg(addr):
        return rd32(proc, base + (addr & 0xFFFFFFFF))

    def fields(node):
        """The filter's own inputs for a doll: [node+0x70] is the entity, +0x1d0 its mask and
        +0x1ff its status byte (0x10083430/0x101cc220 test exactly these)."""
        actor = rdg(node + 0x70)
        if not actor:
            return "actor=0"
        return "actor=%#x mask=%#x status=%#x" % (actor, rdg(actor + 0x1D0) or 0, rdg(actor + 0x1FC) or 0)

    def walk(start, label):
        if not start:
            return
        chain = []
        seen = set()
        cur = start
        for _ in range(256):
            nxt = rdg(cur + 0x54)
            if len(chain) < 6:
                lines.append("  %s fields: %s" % (label, fields(cur)))
            chain.append("%#x" % cur)
            if nxt is None:
                lines.append("%s chain: %s -> unreadable" % (label, " -> ".join(chain)))
                return
            if nxt in seen or nxt == cur:
                lines.append("%s chain: %s -> CYCLE %#x" % (label, " -> ".join(chain), nxt))
                return
            if nxt == 0:
                lines.append("%s chain: %s -> 0 (%d nodes)" % (label, " -> ".join(chain), len(chain)))
                return
            seen.add(cur)
            cur = nxt
        lines.append("%s chain: more than 256 nodes from %#x" % (label, start))

    if g:
        walk(rd32(proc, g + 0), "eax")
        walk(rd32(proc, g + 4), "ecx")
        walk(rd32(proc, g + 24), "esi")

    def sequences(label, values):
        values = values[:256]
        if not values:
            lines.append("%s: no hits (the client may not be in the actor update)" % label)
            return
        pretty = ["%#x" % (n or 0) for n in values]
        lines.append("%s (%d): %s" % (label, len(values), " -> ".join(pretty)))
        counts = {}
        for n in values:
            counts[n] = counts.get(n, 0) + 1
        repeated = {k: v for k, v in counts.items() if v > 1}
        if repeated:
            lines.append("%s REPEATED: %s" % (label, ", ".join("%#x x%d" % (k, v) for k, v in repeated.items())))
        back_to_back = [values[i] for i in range(1, len(values)) if values[i] == values[i - 1]]
        if back_to_back:
            lines.append("%s SAME ACTOR returned again: %s" % (label, ", ".join("%#x" % v for v in set(back_to_back))))
        walk(values[-1], label + " last")

    # Both watches are armed before the first continue: a client stuck in the inner walk never
    # re-enters f_10083d00, and one stuck in the outer loop passes through both.
    watchdog = None
    bps = []
    try:
        bp_a = t.BreakpointCreateByName("f_10083d00")
        bp_a2 = t.BreakpointCreateByName("f_10083b40")
        bp_a2.SetScriptCallbackFunction("freeze_probe.cb_a")
        bps.append(bp_a2)
        bp_a.SetScriptCallbackFunction("freeze_probe.cb_a")
        bps.append(bp_a)
        bp_b = t.BreakpointCreateByName("f_10085270")
        bp_b.SetScriptCallbackFunction("freeze_probe.cb_b")
        bps.append(bp_b)
        # The breakpoints only exist in the actor chain; if the client is wedged somewhere
        # else, Continue would wait forever.  Interrupt it after a few seconds either way.
        watchdog = threading.Timer(10.0, lambda: proc.SendAsyncInterrupt())
        watchdog.daemon = True
        watchdog.start()
        proc.Continue()
    except Exception as exc:
        notes.append("breakpoints: %s" % exc)
    if watchdog is not None:
        watchdog.cancel()
    for bp in bps:
        try:
            t.BreakpointDelete(bp.GetID())
        except Exception:
            pass

    sequences("phase A (f_10083d00/f_10083b40 actor argument)", a_seen)
    sequences("phase B (f_10085270 walker node)", b_seen)
    lines.extend(notes)

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
