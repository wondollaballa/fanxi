#!/usr/bin/env python3
"""Capture one picture of every mount from a running FFXI client.

The Mount HUD shows a picture per mount, and the only renderer that can draw a mount is the
game client itself.  This tool borrows one: it asks the control port for a frame while the
character is riding each mount in turn, crops the character, and writes a square JPEG.

How the mount is called
-----------------------
By default it uses the real command: `//mount off`, then `//mount <id>` through the control
port, so the server drives the client exactly the way a player does (0x037 with the Mounted
effect and the mount animation, plus the entity update).  The client has to be logged in to a
server that has the mount commands.

`--how inject` instead sends the client the same 0x037 by hand; that works on a client whose
server has never heard of mounts, which is what the first pictures were taken with.

    # a client on the default control port, writing assets/mounts/0.jpg .. 36.jpg
    tools/capture_mount_previews.py

    # the six-box team's second box, only the three mounts that changed
    tools/capture_mount_previews.py --port 54301 --ids 1,2,3

    # a scratch client, bigger pictures, and no install into the client data folder
    tools/capture_mount_previews.py --port 54301 --size 320 --no-install

The pictures land in ``assets/mounts/<id>.jpg`` (the repo's source copy) and, unless
--no-install, in ``<data folder>/mounts/<id>.jpg`` so the client's Mount HUD can load them.
--keep-raw keeps the full frames beside them for re-cropping.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import tempfile
import time
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - the tool is for development machines
    print("Pillow is needed: python3 -m pip install pillow", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = Path.home() / "Library" / "Application Support" / "Fanxi" / "FFXI"


class ControlError(RuntimeError):
    pass


class Control:
    """The control port's JSON lines, one request and one reply per connection."""

    def __init__(self, port: int):
        self.port = int(port)

    def call(self, command: str, args: dict | None = None, timeout: float = 30.0):
        with socket.create_connection(("127.0.0.1", self.port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((json.dumps({"id": 1, "cmd": command, "args": args or {}}) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(1 << 20)
                if not chunk:
                    break
                buf += chunk
        try:
            message = json.loads(buf.split(b"\n")[0])
        except ValueError as exc:
            raise ControlError("the control port returned %r" % (buf[:200],)) from exc
        if not message.get("ok"):
            raise ControlError(str(message.get("error") or command + " failed"))
        return message.get("result")

    def state(self) -> dict:
        return self.call("state")

    def lua(self, code: str):
        return self.call("lua", {"code": code})

    def capture(self, path: str) -> dict:
        return self.call("capture", {"path": path})

    def command(self, line: str):
        return self.call("command", {"line": line})


def read_frame(result: dict) -> Image.Image:
    """A capture result and its file as an RGBA image (the host writes a 16-byte header)."""
    width, height = int(result["width"]), int(result["height"])
    fmt = int(result.get("format") or 0)
    raw = Path(result["path"]).read_bytes()
    body = raw[16:16 + width * height * 4]
    if len(body) < width * height * 4:
        raise ControlError("short frame: %d bytes for %dx%d" % (len(body), width, height))
    # The capture is D3DFMT_A8R8G8B8 (21) or X8R8G8B8 (22): BGRA bytes either way.
    return Image.frombytes("RGBA", (width, height), body, "raw", "BGRA" if fmt in (21, 22) else "RGBA")


def mount_packet_lua(mount_id: int, chocobo_index: int | None = None) -> str:
    """Lua that re-sends the last 0x037 with one mount id in it.

    ``chocobo_index`` defaults to 1 for mount 0 and 0 for everything else: the personal
    chocobo is the one mount the client cannot tell from standing still by mount id alone.
    A dismount is mount id 0 with index 0.
    """
    index = (1 if int(mount_id) == 0 else 0) if chocobo_index is None else int(chocobo_index)
    return """
local b = xi.packets.last(false, 0x037)
if type(b) ~= 'string' or #b < 0x60 then return false end
local out = { string.byte(b, 1, -1) }
while #out < 0x78 do out[#out + 1] = 0 end
local head = 0x37 + 30 * 512
out[1] = math.fmod(head, 256)
out[2] = math.floor(head / 256)
out[1 + 0x73] = %d
local flags0 = out[0x29] + out[0x2A] * 256 + out[0x2B] * 65536 + out[0x2C] * 16777216
flags0 = flags0 - math.fmod(flags0, 8192) + %d * 8192
out[0x29] = math.fmod(flags0, 256)
out[0x2A] = math.fmod(math.floor(flags0 / 256), 256)
out[0x2B] = math.fmod(math.floor(flags0 / 65536), 256)
out[0x2C] = math.fmod(math.floor(flags0 / 16777216), 256)
xi.packets.inject(false, string.char(table.unpack(out)))
return true
""" % (int(mount_id), index)


def mount_count(control: Control) -> int:
    value = control.lua("""
local ok, n = pcall(xi.res.string_count, 'mounts.names', 0)
if ok and type(n) == 'number' and n > 0 then return n end
return 0
""")
    return int(value or 0)


def mount_name(control: Control, mount_id: int) -> str:
    value = control.lua("""
local ok, s = pcall(xi.res.string, 'mounts.names', %d, 0, true)
if ok and type(s) == 'string' then return s end
return 'Mount %d'
""" % (int(mount_id), int(mount_id) + 1))
    return str(value or ("Mount %d" % (int(mount_id) + 1)))


def mount_status(control: Control) -> int:
    """The client's current entity animation: 0 on foot, 5 chocobo, 85 mount."""
    value = control.lua("return xi.game.entity(1024, 'StatusServer')")
    return int(value or 0)


def wait_status(control: Control, wanted: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if mount_status(control) == int(wanted):
            return True
        time.sleep(0.2)
    return mount_status(control) == int(wanted)


def crop_frame(image: Image.Image, center_x: float, center_y: float, source: int, size: int) -> Image.Image:
    """A square around the character (the crop centre is a fraction of the frame)."""
    width, height = image.size
    side = int(min(source, width, height))
    x = int(round(center_x * width - side / 2))
    y = int(round(center_y * height - side / 2))
    x = max(0, min(width - side, x))
    y = max(0, min(height - side, y))
    return image.crop((x, y, x + side, y + side)).convert("RGB").resize((size, size), Image.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=54300, help="the client's control port (FFXI_CONTROL)")
    parser.add_argument("--out", type=Path, default=ROOT / "assets" / "mounts", help="where the pictures go")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="the client data folder to install into")
    parser.add_argument("--no-install", action="store_true", help="leave <data>/mounts alone")
    parser.add_argument("--ids", default="", help="only these mount ids, comma separated (default: all)")
    parser.add_argument("--size", type=int, default=256, help="output picture size in pixels")
    parser.add_argument("--how", choices=("server", "inject"), default="server",
                        help="call the mount with //mount (server) or a hand-sent 0x037 (inject)")
    parser.add_argument("--settle", type=float, default=4.5, help="seconds to wait after a mount call")
    parser.add_argument("--center", default="0.5,0.5", help="crop centre as a fraction of the frame")
    parser.add_argument("--crop", type=int, default=700, help="source pixels around that centre")
    parser.add_argument("--keep-raw", action="store_true", help="keep the full frames next to the pictures")
    parser.add_argument("--leave-mounted", action="store_true", help="do not dismount at the end")
    args = parser.parse_args(argv)

    control = Control(args.port)
    state = control.state()
    player = state.get("player") or {}
    if int(player.get("id") or 0) <= 0:
        print("the client is not in the world (no player); log a character in first", file=sys.stderr)
        return 2
    count = mount_count(control)
    if count <= 0:
        print("the client's mount table is empty (mounts.names)", file=sys.stderr)
        return 2
    wanted = [int(part) for part in args.ids.split(",") if part.strip()] if args.ids else list(range(count))
    center_x, center_y = (float(part) for part in args.center.split(","))
    args.out.mkdir(parents=True, exist_ok=True)
    install = None
    if not args.no_install:
        install = args.data / "mounts"
        install.mkdir(parents=True, exist_ok=True)
    raw_dir = args.out / "raw"
    if args.keep_raw:
        raw_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="fanxi-mounts-"))
    print("client: %s in %s; %d mounts" % (
        player.get("name"), (state.get("zone") or {}).get("name"), count))

    # A clean portrait: the HUD's own windows out of the way, and the camera a few wheel
    # notches back so even the biggest mount fits the frame.  Both are put back at the end.
    zoomed = 0
    hud_hidden = False
    try:
        control.command("//hud off")
        hud_hidden = True
        control.lua("xi.input.wheel(8) return 1")
        zoomed = 4
        time.sleep(1.0)
    except ControlError:
        pass

    failures = 0
    for index, mount_id in enumerate(wanted, 1):
        if not 0 <= mount_id < count:
            print("  %2d: no such mount" % mount_id, file=sys.stderr)
            failures += 1
            continue
        name = mount_name(control, mount_id)
        frame_path = scratch / ("mount-%02d.raw" % mount_id)
        expected = 5 if mount_id in (0, 33) else 85  # chocobo animation, or mount animation
        image = None
        reason = "the mount call did not take"
        for attempt in range(3):
            try:
                if args.how == "server":
                    # One command: the server dismounts, waits out the model rebuild and
                    # calls the new mount on its own tick (set_mount/MOUNT_SWITCH_DELAY).
                    control.command("//mount %d" % mount_id)
                    time.sleep(0.8)
                else:
                    control.lua(mount_packet_lua(0, chocobo_index=0))
                    time.sleep(1.2)
                    if control.lua(mount_packet_lua(mount_id)) is not True:
                        raise ControlError("no 0x037 to ride on yet (zone in first)")
                # The animation is the reliable "the client is mounted" signal; the wait
                # covers the server's switch delay, and a retry covers a lost command.
                if not wait_status(control, expected, 8.0):
                    reason = "the client never mounted (status %r)" % (mount_status(control),)
                    continue
                ridden = control.lua("return xi.game.entity(1024, 'MountId')")
                if ridden is None or int(ridden) != int(mount_id):
                    # MountId is informational: a few models report another id while their
                    # art is on screen, so a mismatch is a note, not a lost picture.
                    print("    (client MountId is %r, capturing anyway)" % (ridden,),
                          file=sys.stderr)
                time.sleep(2.0)
                image = read_frame(control.capture(str(frame_path)))
                break
            except ControlError as exc:
                reason = str(exc)
                continue
        if image is None:
            print("  %2d %-16s failed: %s" % (mount_id, name, reason), file=sys.stderr)
            failures += 1
            continue
        picture = crop_frame(image, center_x, center_y, args.crop, args.size)
        target = args.out / ("%d.jpg" % mount_id)
        picture.save(target, "JPEG", quality=90, optimize=True)
        if install is not None:
            picture.save(install / ("%d.jpg" % mount_id), "JPEG", quality=90, optimize=True)
        if args.keep_raw:
            image.save(raw_dir / ("%d.png" % mount_id))
        print("  %2d/%d %-16s %s" % (index, len(wanted), name, target))

    if not args.leave_mounted:
        if args.how == "server":
            control.command("//mount off")
        else:
            control.lua(mount_packet_lua(0, chocobo_index=0))
    # Put the player's own HUD and camera distance back the way they were.
    if zoomed:
        try:
            control.lua("xi.input.wheel(%d) return 1" % -zoomed)
        except ControlError:
            pass
    if hud_hidden:
        try:
            control.command("//hud on")
        except ControlError:
            pass
    for leftover in scratch.iterdir():
        leftover.unlink()
    scratch.rmdir()
    print("%d picture(s) written, %d failed" % (len(wanted) - failures, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
