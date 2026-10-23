"""Sockets for the game client: auth (TLS), login data, lobby and zone.

The wire formats are the ones host/lsb_login.c and the recompiled game already speak to a
LandSandBoat-compatible server. Ports default to the client's own defaults, so a player only has to
point host64 at this machine.
"""
from __future__ import annotations

import json
import logging
import socket
import ssl
import struct
import subprocess
import threading
import time

from ..config import Config
from ..security import signed_bytes
from ..service import ApiError, FanxiService
from . import design as character_design
from .cipher import VIEW_KEY, lobby_packet
from .world import World
from .zone import cstr, ZoneSession

log = logging.getLogger("fanxi.game")


def ensure_certificate(config: Config) -> tuple[str, str] | None:
    """A self-signed certificate for the auth port, made once with the openssl command."""
    cert, key = config.tls_cert, config.tls_key
    if cert.exists() and key.exists():
        return str(cert), str(key)
    config.ensure_dirs()
    try:
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3650",
             "-subj", "/CN=Fanxi Server", "-keyout", str(key), "-out", str(cert)],
            check=True, capture_output=True,
        )
        key.chmod(0o600)
        return str(cert), str(key)
    except (OSError, subprocess.CalledProcessError) as exc:
        log.error("cannot make the auth certificate: %s", exc)
        return None


def tls_context(config: Config) -> ssl.SSLContext | None:
    pair = ensure_certificate(config)
    if pair is None:
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(*pair)
    return ctx


def _listen(bind: str, port: int, handler, wrap: ssl.SSLContext | None = None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind, port))
    sock.listen(16)

    def loop():
        while True:
            try:
                conn, addr = sock.accept()
            except OSError:
                return
            if wrap is not None:
                try:
                    conn = wrap.wrap_socket(conn, server_side=True)
                except (ssl.SSLError, OSError) as exc:
                    log.warning("TLS handshake from %s: %s", addr[0], exc)
                    conn.close()
                    continue
            threading.Thread(target=handler, args=(conn, addr), daemon=True).start()

    threading.Thread(target=loop, name="fanxi-listen-%d" % port, daemon=True).start()
    return sock


def _recv_json(conn, limit: int = 64 * 1024):
    conn.settimeout(20)
    data = b""
    while len(data) < limit:
        chunk = conn.recv(8192)
        if not chunk:
            break
        data += chunk
        try:
            value = json.loads(data.decode("utf-8"))
            if isinstance(value, dict):
                return value
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return None


class _DataFrames:
    """The login data connection is a stream of 28-byte packets, sometimes coalesced by TCP."""

    def __init__(self, conn):
        self.conn = conn
        self.buf = b""

    def read(self, timeout=None):
        self.conn.settimeout(timeout)
        while len(self.buf) < 28:
            chunk = self.conn.recv(4096)
            if not chunk:
                return None
            self.buf += chunk
        frame, self.buf = self.buf[:28], self.buf[28:]
        return frame


def _data_a1(account: dict, session_hash: bytes, host_ip: str) -> bytes:
    reply = bytearray(28)
    reply[0] = 0xA1
    struct.pack_into("<I", reply, 1, account["id"])
    reply[5:9] = socket.inet_aton(host_ip)
    reply[12:28] = session_hash
    return bytes(reply)


def _data_a2(session_hash: bytes) -> bytes:
    from .cipher import md5
    reply = bytearray(28)
    reply[0] = 0xA2
    reply[1:17] = md5(session_hash)
    reply[17:21] = b"\x58\xe0\x5d\xad"
    return bytes(reply)


class Lobby:
    def __init__(self, world: World):
        self.world = world
        self.service = world.service

    def serve(self, conn, addr):
        log.info("lobby: %s connected", addr[0])
        buf = b""
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data
                while len(buf) >= 28:
                    size = struct.unpack_from("<I", buf)[0]
                    if size < 28 or size > 0x10000:
                        size = len(buf)
                    if len(buf) < size:
                        break
                    packet, buf = buf[:size], buf[size:]
                    command = packet[8]
                    session_hash = packet[12:28]
                    account = self.service.game_account_by_hash(session_hash)
                    if account is None:
                        log.warning("lobby: %s without a live session", addr[0])
                        return
                    reply = self.view_reply(account, session_hash, command, packet)
                    log.debug("lobby 0x%02X -> %s", command,
                              ("0x%02X" % reply[8]) if reply else "nothing")
                    if reply:
                        conn.sendall(reply)
                    if command == 0x07:
                        return  # the client waits for the lobby to close
        except OSError as exc:
            log.debug("lobby: %s", exc)
        finally:
            conn.close()

    def view_reply(self, account: dict, session_hash: bytes, command: int, packet: bytes):
        world = self.world
        if command == 0x26:  # version and expansions -> the key
            return lobby_packet(0x05, struct.pack("<III", VIEW_KEY, 0x0FFF, 0x00FC), 0x28)
        if command == 0x1F:  # the character list
            characters = self._characters_for_session(account, session_hash)
            body = struct.pack("<I", len(characters))
            for character in characters:
                body += character_record(character, equipped_looks(self.service, character))
            return lobby_packet(0x20, body)
        if command == 0x24:  # the world list
            return lobby_packet(0x23, struct.pack("<II", 1, 0x20) + cstr(world.server_name, 16))
        if command == 0x07:  # this character: where its zone is
            characters = self._characters_for_session(account, session_hash)
            character = self._choose(characters, packet)
            if character is None:
                log.warning("lobby: account %s has no character", account["username"])
                return None
            cid = int(character["char_id"])
            ip = socket.inet_aton(world.host_ip)
            body = struct.pack("<II", cid, cid & 0xFFFF) + cstr(character["name"], 16) + struct.pack(
                "<I4sI4sI", (cid >> 16) & 0xFF, ip, world.ports["zone_port"], ip, world.ports["search_port"])
            world.prepare_zone_in(account["id"], session_hash, character)
            return lobby_packet(0x0B, body, 0x48)
        if command in (0x14, 0x21, 0x22, 0x28):  # delete, create, name check, rename: all fine
            return lobby_packet(0x03, b"", 0x20)
        return None

    def _characters_for_session(self, account: dict, session_hash: bytes) -> list[dict]:
        """The characters this login may choose.

        A launcher launch names its character; the client then sees only that mule on the
        character-select screen.  A plain password login (or an older launch token) sees all of
        them.  One character per account can be online at a time, so two clients on the same
        account still replace each other -- multiboxing uses one account per client.
        """
        characters = self.world.characters_for(account["id"])
        wanted = self.service.game_session_character(session_hash)
        if wanted:
            only = [c for c in characters if int(c["id"]) == int(wanted)]
            if only:
                return only
        return characters

    @staticmethod
    def _choose(characters: list[dict], packet: bytes):
        if not characters:
            return None
        for offset in range(28, len(packet) - 3, 4):
            value = struct.unpack_from("<I", packet, offset)[0]
            for character in characters:
                if int(character["char_id"]) == value:
                    return character
        return characters[0]


def equipped_looks(service, character: dict) -> dict[int, int]:
    """Model ids of what the character is wearing, keyed by equip kind.

    The character-select screen draws the same appearance block the zone does, so filling it
    from char_equip makes the lobby show the real outfit instead of creation defaults.
    """
    looks: dict[int, int] = {}
    try:
        rows = service.equipment(int(character.get("id") or character["char_id"]))
    except Exception:
        return looks
    for row in rows:
        item = service.item(int(row["item_id"]))
        if not item:
            continue
        model = int(item.get("model") or 0)
        if model:
            looks[int(row["kind"])] = model
    return looks


def character_record(character: dict, gear: dict[int, int] | None = None) -> bytes:
    """The character's lobby record (lpkt_chr_info_sub2, 140 bytes)."""
    c = character
    record = bytearray(140)
    cid = int(c["char_id"])
    raw_face = character_design.raw_face(c)
    struct.pack_into("<IHHHBB", record, 0, cid, cid & 0xFFFF, 0, 1, 0, (cid >> 16) & 0xFF)
    record[12:28] = cstr(c["name"], 16)
    record[28:44] = cstr(c["server_name"], 16)
    m = 44
    struct.pack_into("<HBBHBBBBH", record, m, c["race"], c["main_job"], c["sub_job"], raw_face,
                     c["nation"], 0, raw_face, c["size"], 0)
    looks = [raw_face, c["head"], c["body"], c["hands"], c["legs"], c["feet"], c["main"], c["sub"]]
    if gear:
        # face, head, body, hands, legs, feet, main, sub
        for index, kind in ((1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (6, 0), (7, 1)):
            if gear.get(kind):
                looks[index] = gear[kind]
    struct.pack_into("<8H", record, m + 12, *looks)
    record[m + 28] = c["zone"] & 255
    record[m + 29] = c["main_level"]
    record[m + 35] = (c["zone"] >> 8) & 1
    struct.pack_into("<I", record, m + 52, 0xFFFFFFFF)  # every job unlocked
    record[m + 56 + c["main_job"]] = c["main_level"]
    return bytes(record)


class Gateway:
    def __init__(self, config: Config, service: FanxiService, huffman):
        self.config = config
        self.service = service
        self.huffman = huffman
        self.world = World(config, service, huffman)
        self.lobby = Lobby(self.world)
        self.auth_ctx = tls_context(config)
        self._udp = None

    def start(self) -> None:
        if self.huffman is None:
            raise RuntimeError("the zone gateway needs the game's res/compress.dat; set FANXI_HUFFMAN")
        ports = self.config.ports
        bind = self.config.bind
        sockets = []
        if self.auth_ctx is None:
            raise RuntimeError("the auth gateway needs a TLS certificate (openssl)")
        sockets.append(_listen(bind, ports["auth_port"], self.auth, self.auth_ctx))
        sockets.append(_listen(bind, ports["data_port"], self.data))
        sockets.append(_listen(bind, ports["view_port"], self.lobby.serve))
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind((bind, ports["zone_port"]))
        udp.settimeout(0.25)
        sockets.append(udp)
        self._udp = udp
        self.world.udp = udp
        self.world.sockets.extend(sockets)
        threading.Thread(target=self.zone_loop, args=(udp,), name="fanxi-zone", daemon=True).start()
        log.info("game gateway: auth %d/tcp, data %d/tcp, lobby %d/tcp, zone %d/udp",
                 ports["auth_port"], ports["data_port"], ports["view_port"], ports["zone_port"])

    def stop(self) -> None:
        self.world.close()

    # --- auth ----------------------------------------------------------------------------------
    def auth(self, conn, addr):
        try:
            payload = _recv_json(conn)
            if payload is None:
                log.warning("auth: %s sent no JSON", addr[0])
                return
            try:
                account, session_hash = self.service.game_login(payload, addr[0])
            except ApiError as exc:
                reply = {
                    "result": exc.game_result if exc.game_result is not None else 0,
                    "error_message": exc.message.replace("\n", " "),
                }
                log.info("auth: %s refused: %s", addr[0], exc.code)
            else:
                self.world.keys.pop(account["id"], None)
                reply = {
                    "result": 1,
                    "account_id": account["id"],
                    "session_hash": signed_bytes(session_hash),
                }
                log.info("auth: %s signed in as %s", addr[0], account["username"])
            conn.sendall(json.dumps(reply).encode("utf-8"))
        except (OSError, ssl.SSLError) as exc:
            log.warning("auth: %s", exc)
        except Exception as exc:  # a broken auth request must not take the listener down
            log.exception("auth: %s", exc)
            try:
                conn.sendall(json.dumps({"result": 0, "error_message": "server error"}).encode("utf-8"))
            except OSError:
                pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    # --- login data ----------------------------------------------------------------------------
    def data(self, conn, addr):
        """The login data channel.

        The client sends 0xFE + its session hash, then answers two questions: 0x01 -> 0xA1
        (account id, server address, hash) and 0x02/0x15 -> 0xA2 (the 20-byte zone key).  Some
        clients ask those questions themselves instead; both directions are accepted.  The key
        from 0xA2 is what the zone cipher needs, so ask for it here and keep it.
        """
        account = None
        session_hash = b""
        frames = _DataFrames(conn)
        try:
            first = frames.read(timeout=30)
            if not first:
                return
            if first[0] == 0xFE:
                session_hash = first[12:28]
                account = self.service.game_account_by_hash(session_hash)
                if account is None:
                    log.warning("data: %s sent a session the server does not know", addr[0])
                    return
            else:
                log.warning("data: %s sent 0x%02X, not the 0xFE session packet", addr[0], first[0])
                return

            have_account = have_key = False
            # The client's data thread answers 0x01 with 0xA1 and 0x02 with 0xA2.  Do not send
            # both at once: a client that reads them together would answer only the first.
            for ask in (0x01, 0x02):
                if ask == 0x01 and have_account:
                    continue
                if ask == 0x02 and have_key:
                    continue
                conn.sendall(bytes([ask]))
                for _ in range(4):
                    frame = frames.read(timeout=1.0)
                    if frame is None:
                        break
                    kind = frame[0]
                    if kind == 0x01:
                        conn.sendall(_data_a1(account, session_hash, self.world.host_ip))
                    elif kind in (0x02, 0x15):
                        conn.sendall(_data_a2(session_hash))
                    elif kind == 0xA1:
                        have_account = True
                    elif kind == 0xA2:
                        self.world.keys[account["id"]] = bytes(frame[1:21])
                        have_key = True
                        log.info("data: zone key from %s: %s", addr[0], bytes(frame[1:21]).hex())
                    if (ask == 0x01 and (have_account or have_key)) or (ask == 0x02 and have_key):
                        break

            conn.settimeout(None)  # the login data connection lives as long as the game does
            while True:
                frame = frames.read()
                if frame is None:
                    break
                kind = frame[0]
                if kind == 0xA2:
                    self.world.keys[account["id"]] = bytes(frame[1:21])
                    log.info("data: zone key from %s: %s", addr[0], bytes(frame[1:21]).hex())
                elif kind == 0x01:
                    conn.sendall(_data_a1(account, session_hash, self.world.host_ip))
                elif kind in (0x02, 0x15):
                    conn.sendall(_data_a2(session_hash))
        except (OSError, ssl.SSLError) as exc:
            log.debug("data: %s", exc)
        finally:
            conn.close()

    # --- zone ----------------------------------------------------------------------------------
    def zone_loop(self, udp: socket.socket):
        while True:
            try:
                data, addr = udp.recvfrom(4096)
            except socket.timeout:
                try:
                    self.world.tick(time.time())
                except Exception as exc:
                    log.warning("world tick: %s: %s", type(exc).__name__, exc)
                continue
            except OSError:
                return
            try:
                session = self.world.sessions.get(addr)
                out = ZoneSession.incoming(self.world, session, addr, bytearray(data))
                if out:
                    udp.sendto(out, addr)
            except Exception as exc:  # one bad packet must not stop the zone
                log.warning("zone %s: %s: %s", addr, type(exc).__name__, exc)
