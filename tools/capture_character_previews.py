#!/usr/bin/env python3
"""Capture real character-select previews from the game client.

The launcher's design page cannot host the client's skinned DAT renderer, so
this tool borrows a real client: it parks one sub-account at the character
select screen, writes one design into that character's row, restarts the
client, and captures the model the client builds from its own DATs.  The
crops are what the design page shows; the client is back at the select screen
in about ten seconds, so a full race takes a few minutes.

Requirements:
  * the Fanxi server is running and the launcher is signed in
    (its token is read from launcher.json);
  * the client's existing USER folder has accepted the FFXI user agreement
    once (open the game normally before running this);
  * a spare sub-account/character that may be rewritten.  The tool snapshots
    the character row and puts it back when it stops.

    tools/capture_character_previews.py --races 1 --resume
    tools/capture_character_previews.py --races 2,3,4 --sizes 1 --resume
    tools/capture_character_previews.py --verify --races 1

The output is ``launcher-rs/public/design/<race>-<face>-<hair>-<size>.jpg``.
The design page scales a medium capture for small/large when no per-size
capture exists, so ``--sizes 1`` is enough for the first pass.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "fanxi.db"
DEFAULT_OUT = ROOT / "launcher-rs" / "public" / "design"
DEFAULT_LAUNCHER = Path.home() / "Library" / "Application Support" / "Fanxi" / "launcher.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import design  # noqa: E402
from tools.replay import png as xif_png  # noqa: E402


class CaptureError(RuntimeError):
    pass


class Control:
    def __init__(self, port: int):
        self.port = int(port)

    def call(self, command: str, args: dict | None = None, timeout: float = 30.0):
        with socket.create_connection(("127.0.0.1", self.port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((json.dumps({"id": 1, "cmd": command, "args": args or {}}) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        message = json.loads(buf.split(b"\n")[0])
        if not message.get("ok"):
            raise CaptureError(str(message.get("error") or command + " failed"))
        return message.get("result")

    def state(self) -> dict:
        return self.call("state")

    def key(self, name: str) -> None:
        self.call("key", {"key": name, "down": True})
        self.call("key", {"key": name, "down": False})
        time.sleep(0.3)

    def wait_menu(self, names: set[str], timeout: float = 45.0) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                state = self.state()
                if state.get("menu") in names:
                    return state
            except (OSError, CaptureError, json.JSONDecodeError):
                pass
            time.sleep(0.5)
        return None

    def wait_port(self, timeout: float = 45.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.3)
        raise CaptureError("the client did not open control port %d" % self.port)


class Previewer:
    def __init__(self, args):
        self.args = args
        self.control = Control(args.control_port)
        self.pid_file = Path("/tmp/fanxi-preview-client.pid")
        self.log = Path("/tmp/fanxi-preview-client.log")
        self.launcher = json.loads(Path(args.launcher).read_text())
        self.token = self.launcher["token"]
        self.api = args.api_url.rstrip("/")
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(args.db))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA ignore_check_constraints=ON")
        self.original = None
        self.hair_column = any(
            row[1] == "hair" for row in self.connection.execute("PRAGMA table_info(characters)"))

    def close(self) -> None:
        self.kill_client()
        if self.original is not None:
            self.restore()
        self.connection.close()

    # --- the database row ---------------------------------------------------------------
    def load_character(self):
        row = self.connection.execute(
            "SELECT * FROM characters WHERE id = ?", (int(self.args.character_id),)
        ).fetchone()
        if row is None:
            raise CaptureError("character id %s is not in %s" % (self.args.character_id, self.args.db))
        return dict(row)

    def snapshot(self) -> None:
        row = self.load_character()
        self.original = {key: row[key] for key in
                         ("race", "face", "size") + (("hair",) if self.hair_column else ())}
        print("will restore %s to %s" % (row["name"], self.original))

    def restore(self) -> None:
        fields = ["race = ?", "face = ?", "size = ?"]
        values = [self.original["race"], self.original["face"], self.original["size"]]
        if self.hair_column:
            fields.append("hair = ?")
            values.append(self.original.get("hair", 0))
        values.append(int(self.args.character_id))
        self.connection.execute(
            "UPDATE characters SET %s, updated_at = datetime('now') WHERE id = ?" % ", ".join(fields),
            values)
        self.connection.commit()
        print("restored %s" % self.original)

    def apply_design(self, race: int, face: int, hair: int, size: int) -> None:
        if self.hair_column:
            self.connection.execute(
                "UPDATE characters SET race = ?, face = ?, hair = ?, size = ?, "
                "updated_at = datetime('now') WHERE id = ?",
                (race, face, hair, size, int(self.args.character_id)))
        else:
            # The old schema's face column is the combined client look byte.
            raw = (face - 1) * 2 + hair
            self.connection.execute(
                "UPDATE characters SET race = ?, face = ?, size = ?, "
                "updated_at = datetime('now') WHERE id = ?",
                (race, raw, size, int(self.args.character_id)))
        self.connection.commit()

    # --- the client ---------------------------------------------------------------------
    def kill_client(self) -> None:
        if self.pid_file.exists():
            try:
                os.kill(int(self.pid_file.read_text().strip()), signal.SIGKILL)
            except (OSError, ValueError):
                pass
            self.pid_file.unlink(missing_ok=True)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.control.port), timeout=0.3):
                    time.sleep(0.3)
            except OSError:
                return

    def launch_client(self) -> None:
        request = urllib.request.Request(
            "%s/api/v1/accounts/sub/%d/launch" % (self.api, int(self.args.sub_id)),
            data=json.dumps({"character_id": int(self.args.character_id)}).encode(),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.load(response)
        except Exception as exc:
            raise CaptureError("could not mint a launch token: %s" % exc) from exc
        token = payload["login_token"]
        env = dict(os.environ, FFXI_CONTROL=str(self.control.port))
        handle = open(self.log, "wb")
        process = subprocess.Popen([
            str(self.args.host64), "--game", str(self.args.game),
            "--server", self.args.server, "--user", payload["account"]["username"],
            "--login-token", token,
            "--authport", str(self.args.auth_port),
            "--dataport", str(self.args.data_port),
            "--viewport", str(self.args.view_port),
        ], stdout=handle, stderr=handle, env=env)
        self.pid_file.write_text(str(process.pid))
        self.control.wait_port()

    def ensure_select(self) -> None:
        state = self.control.wait_menu({"ptc8lice", "loby2win", "dbnamese"}, timeout=45)
        if state is None:
            raise CaptureError("the client never reached a known menu")
        if state.get("menu") == "ptc8lice":
            self.control.key("enter")
            state = self.control.wait_menu({"loby2win", "dbnamese"}, timeout=30)
        if state and state.get("menu") == "loby2win":
            self.control.key("enter")
            state = self.control.wait_menu({"dbnamese"}, timeout=30)
        if not state or state.get("menu") != "dbnamese":
            raise CaptureError("the client never reached character select")

    def capture(self, destination: Path) -> None:
        raw = destination.with_suffix(".xif")
        self.control.call("capture", {"path": str(raw)}, timeout=30)
        deadline = time.monotonic() + 20
        while not raw.exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        if not raw.exists():
            raise CaptureError("no frame was written")
        frame = destination.with_suffix(".png")
        if not xif_png(str(raw), str(frame)):
            raw.unlink(missing_ok=True)
            raise CaptureError("the frame is not an XIF1 capture")
        command = [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(frame),
            "-vf", "crop=%s,eq=brightness=0.04:contrast=1.02:saturation=1.05" % self.args.crop,
            "-q:v", "3", str(destination),
        ]
        try:
            subprocess.run(command, check=True)
        finally:
            raw.unlink(missing_ok=True)
            frame.unlink(missing_ok=True)

    # --- one design ---------------------------------------------------------------------
    def one(self, race: int, face: int, hair: int, size: int) -> Path:
        destination = self.out / ("%d-%d-%d-%d.jpg" % (race, face, hair, size))
        if self.args.resume and destination.exists() and destination.stat().st_size > 2000:
            return destination
        self.apply_design(race, face, hair, size)
        self.kill_client()
        for attempt in (1, 2):
            try:
                self.launch_client()
                self.ensure_select()
                time.sleep(0.8)
                self.capture(destination)
                print("  %s  %s" % (destination.name, design.design(
                    race, face, hair, size)["label"]))
                return destination
            except (CaptureError, OSError, subprocess.CalledProcessError) as exc:
                self.kill_client()
                if attempt == 2:
                    raise
                print("  retry %s: %s" % (destination.name, exc), file=sys.stderr)
                time.sleep(1)
        raise CaptureError("unreachable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER,
                        help="launcher.json with a signed-in main-account token")
    parser.add_argument("--api-url", default="http://127.0.0.1:8080")
    parser.add_argument("--host64", type=Path, default=ROOT / "build" / "host64")
    parser.add_argument("--game", type=Path, default=Path("/Users/wondochoung/Games/FFXI2507"))
    parser.add_argument("--server", default="127.0.0.1")
    parser.add_argument("--auth-port", type=int, default=54231)
    parser.add_argument("--data-port", type=int, default=54230)
    parser.add_argument("--view-port", type=int, default=54001)
    parser.add_argument("--control-port", type=int, default=54303)
    parser.add_argument("--sub-id", type=int, default=5, help="sub-account to rewrite")
    parser.add_argument("--character-id", type=int, default=3,
                        help="character on that sub-account")
    parser.add_argument("--races", default="1,2,3,4,5,6,7,8",
                        help="comma-separated race ids, or 'hume' etc.")
    parser.add_argument("--faces", default="1,2,3,4,5,6,7,8")
    parser.add_argument("--hairs", default="0,1")
    parser.add_argument("--sizes", default="1", help="0 small, 1 medium, 2 large")
    parser.add_argument("--crop", default="430:610:425:40",
                        help="ffmpeg crop W:H:X:Y around the character (default 430:610:425:40)")
    parser.add_argument("--resume", action="store_true", help="keep existing images")
    parser.add_argument("--verify", action="store_true",
                        help="only list which requested images exist")
    args = parser.parse_args(argv)

    races = [design.race(value.strip()).id for value in args.races.split(",") if value.strip()]
    faces = [int(value) for value in args.faces.split(",") if value.strip()]
    hairs = [int(value) for value in args.hairs.split(",") if value.strip()]
    sizes = [int(value) for value in args.sizes.split(",") if value.strip()]

    if args.verify:
        missing = 0
        for race in races:
            for face in faces:
                for hair in hairs:
                    for size in sizes:
                        path = args.out / ("%d-%d-%d-%d.jpg" % (race, face, hair, size))
                        if not path.exists():
                            missing += 1
        print("%d requested previews; %d missing" % (
            len(races) * len(faces) * len(hairs) * len(sizes), missing))
        return 0 if missing == 0 else 1

    previewer = Previewer(args)
    try:
        previewer.snapshot()
        total = len(races) * len(faces) * len(hairs) * len(sizes)
        done = 0
        for race in races:
            for face in faces:
                for hair in hairs:
                    for size in sizes:
                        done += 1
                        print("[%d/%d] race %d face %d hair %d size %d" % (
                            done, total, race, face, hair, size), flush=True)
                        previewer.one(race, face, hair, size)
    finally:
        previewer.close()
    print("done: %d previews in %s" % (total, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
