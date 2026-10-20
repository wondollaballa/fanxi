"""The Fanxi world: zone data and the small amount of state the game gateway shares.

One World is created per server process. It owns the cipher key each account's client agreed to,
the lobby-to-zone hand-off map, and the zone rows read from the database.
"""
from __future__ import annotations

import socket
import struct
import threading
from pathlib import Path

from ..config import Config
from ..service import FanxiService
from .cipher import M32, VIEW_KEY, Huffman, md5, zone_cipher

# Fallback positions for zones that are not in the database yet.
KNOWN_POSITIONS = {
    50: (-11.0, 2.0, -142.0, 192),   # Aht Urhgan Whitegate
    100: (-126.0, -62.0, 273.0, 99),  # West Ronfaure
    231: (0.0, 0.0, -13.0, 192),     # Northern San d'Oria
    232: (-1.0, 0.0, 44.0, 128),     # Port San d'Oria
    236: (-36.0, 7.0, -58.0, 194),   # Port Bastok
    246: (-87.0, 12.0, 116.0, 128),  # Port Jeuno
}


class Zones:
    def __init__(self, rows: dict[int, dict], lines: dict[int, tuple]):
        self.rows = rows
        self.lines = dict(lines)
        self.names = {int(zone): row["name"] for zone, row in rows.items()}
        self.music = {
            int(zone): (int(row["music_day"]), int(row["music_night"]),
                        int(row["music_solo"]), int(row["music_party"]))
            for zone, row in rows.items()
        }

    def position(self, zone: int):
        row = self.rows.get(int(zone))
        if row is not None:
            return (float(row["pos_x"]), float(row["pos_y"]), float(row["pos_z"]), int(row["rot"]))
        if int(zone) in KNOWN_POSITIONS:
            return KNOWN_POSITIONS[int(zone)]
        for to_zone, x, y, z, rot in self.lines.values():
            if to_zone == zone:
                return (x, y, z, rot)
        return (0.0, 0.0, 0.0, 0)

    def name(self, zone: int) -> str:
        return self.names.get(int(zone), "zone %d" % int(zone))

    def music_for(self, zone: int) -> tuple:
        return self.music.get(int(zone), (0, 0, 0, 0))


class World:
    def __init__(self, config: Config, service: FanxiService, huffman: Huffman | None,
                 bind: str | None = None):
        self.config = config
        self.service = service
        self.huff = huffman
        self.bind = bind or config.bind
        self.public_name = config.public_host
        try:
            self.host_ip = socket.gethostbyname(config.public_host)
        except OSError:
            # The launcher still gets the name in /launch; the lobby needs a literal IPv4.
            self.host_ip = "127.0.0.1"
        self.ports = dict(config.ports)
        self.zones = Zones(service.zones(), service.zone_lines())
        self.server_name = service.server_name()
        self.motd = service.motd()
        self.clock = 0
        self.sessions: dict[tuple, object] = {}  # (ip, port) -> ZoneSession
        self.by_char: dict[int, object] = {}      # char id -> ZoneSession waiting for its 0x00A
        self.keys: dict[int, bytes] = {}          # account id -> the 20-byte zone key the client sent
        self.lock = threading.RLock()
        self.sockets: list = []

    # --- data helpers --------------------------------------------------------------------------
    def character_record(self, row: dict) -> dict:
        return self.service.character_record(row, self.server_name)

    def characters_for(self, account_id: int) -> list[dict]:
        return [self.character_record(row) for row in self.service.characters_for_account(account_id)]

    def character_by_char_id(self, char_id: int) -> dict | None:
        row = self.service.character_by_char_id(char_id)
        return self.character_record(row) if row else None

    def key_from_hash(self, session_hash: bytes) -> bytearray:
        """The key the client's zone cipher starts from.

        md5(session hash), then the view key with the client's own adjustment (+9).
        """
        return bytearray(md5(bytes(session_hash)) + struct.pack("<I", (VIEW_KEY + 9) & M32))

    def prepare_zone_in(self, account_id: int, session_hash: bytes, character: dict):
        from .zone import ZoneSession

        key = self.keys.get(account_id) or self.key_from_hash(session_hash)
        session = ZoneSession(self, None, character)
        session.zone = int(character["zone"])
        session.pos = list(character["pos"]) if character.get("pos") else list(self.zones.position(session.zone))
        session.set_key(key)
        with self.lock:
            self.by_char[int(character["char_id"])] = session
        return session

    def save_position(self, character: dict, zone: int, pos) -> None:
        try:
            self.service.save_position(character["id"], int(zone), pos)
        except Exception:
            pass

    def zone_cipher_for(self, key: bytes):
        return zone_cipher(key)

    def close(self) -> None:
        for sock in self.sockets:
            try:
                sock.close()
            except OSError:
                pass
        self.sockets.clear()


def load_huffman(folder: str | Path | None) -> Huffman | None:
    if not folder:
        return None
    folder = Path(folder)
    if folder.name == "compress.dat":
        folder = folder.parent
    path = folder / "compress.dat"
    if not path.exists():
        return None
    return Huffman.from_folder(folder)
