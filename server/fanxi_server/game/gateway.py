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
            characters = world.characters_for(account["id"])
            body = struct.pack("<I", len(characters))
            for character in characters:
                body += character_record(character)
            return lobby_packet(0x20, body)
        if command == 0x24:  # the world list
            return lobby_packet(0x23, struct.pack("<II", 1, 0x20) + cstr(world.server_name, 16))
        if command == 0x07:  # this character: where its zone is
            characters = world.characters_for(account["id"])
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


def character_record(character: dict) -> bytes:
    """The character's lobby record (lpkt_chr_info_sub2, 140 bytes)."""
    c = character
    record = bytearray(140)
    cid = int(c["char_id"])
    struct.pack_into("<IHHHBB", record, 0, cid, cid & 0xFFFF, 0, 1, 0, (cid >> 16) & 0xFF)
    record[12:28] = cstr(c["name"], 16)
    record[28:44] = cstr(c["server_name"], 16)
    m = 44
    struct.pack_into("<HBBHBBBBH", record, m, c["race"], c["main_job"], c["sub_job"], c["face"],
                     c["nation"], 0, c["face"], c["size"], 0)
    looks = [c["face"], c["head"], c["body"], c["hands"], c["legs"], c["feet"], c["main"], c["sub"]]
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
        account = None
        session_hash = b""
        try:
            conn.settimeout(30)
            first = conn.recv(256)
            if not first:
                return
            if first[0] == 0xFE and len(first) >= 28:
                session_hash = first[12:28]
                account = self.service.game_account_by_hash(session_hash)
                if account is None:
                    log.warning("data: %s sent a session the server does not know", addr[0])
                    return
            conn.settimeout(None)  # the login data connection lives as long as the game does
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                if data[0] == 0xA2 and len(data) >= 21 and account is not None:
                    self.world.keys[account["id"]] = bytes(data[1:21])
                    log.info("data: zone key from %s", addr[0])
                elif data[0] == 0x01 and account is not None:
                    reply = bytearray(28)
                    reply[0] = 0xA1
                    struct.pack_into("<I", reply, 1, account["id"])
                    reply[5:9] = socket.inet_aton(self.world.host_ip)
                    reply[12:28] = session_hash
                    conn.sendall(bytes(reply))
                elif data[0] in (0x02, 0x15) and account is not None:
                    from .cipher import md5
                    reply = bytearray(28)
                    reply[0] = 0xA2
                    reply[1:17] = md5(session_hash)
                    reply[17:21] = b"\x58\xe0\x5d\xad"
                    conn.sendall(bytes(reply))
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
                self.world.flush()
            except Exception as exc:  # one bad packet must not stop the zone
                log.warning("zone %s: %s: %s", addr, type(exc).__name__, exc)
