"""Protocol pieces and a live gateway: auth over TLS, data, lobby and a zone login."""
from __future__ import annotations

import json
import socket
import ssl
import struct
import tempfile
import unittest
from pathlib import Path

from support import game_ports, make_huffman_dir, make_service

from fanxi_server.game.cipher import Blowfish, Huffman, lobby_packet, md5, zone_cipher
from fanxi_server.game.gateway import Gateway, character_record
from fanxi_server.game.zone import HDR, sub


class CipherTest(unittest.TestCase):
    def test_huffman_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = make_huffman_dir(Path(tmp))
            huff = Huffman.from_folder(folder)
            data = b"Fanxi zone packet" * 10
            packed, nbits = huff.compress(data)
            self.assertEqual(huff.decompress(packed, nbits), data)

    def test_blowfish_roundtrip(self):
        cipher = Blowfish(bytes(range(16)))
        left, right = 0x12345678, 0x9ABCDEF0
        enc_left, enc_right = cipher.encipher(left, right)
        self.assertNotEqual((enc_left, enc_right), (left, right))
        self.assertEqual(cipher.decipher(enc_left, enc_right), (left, right))

    def test_zone_cipher_is_deterministic(self):
        key = bytes(range(20))
        left, right = 1, 2
        self.assertEqual(zone_cipher(key).encipher(left, right), zone_cipher(key).encipher(left, right))

    def test_lobby_packet_checksum(self):
        packet = lobby_packet(0x20, b"hello", 40)
        self.assertEqual(packet[8], 0x20)
        self.assertEqual(len(packet), 40)
        zeroed = bytearray(packet)
        digest = zeroed[12:28]
        zeroed[12:28] = bytes(16)
        self.assertEqual(md5(bytes(zeroed)), digest)


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        self.huffman_dir = make_huffman_dir(tmp)
        ports = game_ports()
        self.config, self.db, self.service = make_service(
            tmp, ports=ports, huffman_dir=self.huffman_dir, bind="127.0.0.1", public_host="127.0.0.1"
        )
        self.huff = Huffman.from_folder(self.huffman_dir)
        self.gateway = Gateway(self.config, self.service, self.huff)
        self.addCleanup(self.gateway.stop)
        self.gateway.start()
        result = self.service.register("tester", "password123", ip="127.0.0.1")
        self.account = result.account
        self.character = self.service.create_character(self.account["id"], {
            "name": "Fanxi", "race": 1, "face": 1, "size": 1, "nation": 0, "main_job": 1,
        })
        self.launch = self.service.launch(self.account, None, ip="127.0.0.1")
        self.session_hash = None

    def auth(self, payload):
        context = ssl._create_unverified_context()
        with socket.create_connection(("127.0.0.1", self.config.ports["auth_port"]), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname="fanxi") as tls:
                tls.sendall(json.dumps(payload).encode())
                data = tls.recv(16384)
        self.assertTrue(data, "auth server sent nothing")
        return json.loads(data.decode())

    def test_auth_with_launch_token(self):
        reply = self.auth({"command": 16, "username": "tester", "password": "",
                           "login_token": self.launch["login_token"], "version": [2, 2, 0]})
        self.assertEqual(reply["result"], 1)
        self.assertEqual(reply["account_id"], self.account["id"])
        self.assertEqual(len(reply["session_hash"]), 16)
        self.session_hash = bytes(v & 0xFF for v in reply["session_hash"])

    def test_auth_with_password(self):
        reply = self.auth({"command": 16, "username": "tester", "password": "password123",
                           "version": [2, 2, 0]})
        self.assertEqual(reply["result"], 1)

    def test_bad_launch_token(self):
        reply = self.auth({"command": 16, "username": "tester", "password": "",
                           "login_token": "nope", "version": [2, 2, 0]})
        self.assertEqual(reply["result"], 0x14)

    def _signed_in(self):
        reply = self.auth({"command": 16, "username": "tester", "password": "",
                           "login_token": self.service.launch(self.account, None)["login_token"],
                           "version": [2, 2, 0]})
        self.assertEqual(reply["result"], 1)
        return bytes(v & 0xFF for v in reply["session_hash"])

    def _lobby(self, session_hash, command, body=b"", size=None):
        packet = bytearray(28 + len(body))
        packet[8] = command
        packet[12:28] = session_hash
        packet[28:] = body
        with socket.create_connection(("127.0.0.1", self.config.ports["view_port"]), timeout=10) as sock:
            sock.sendall(packet)
            data = sock.recv(65536)
        return data

    def test_lobby_character_list_and_zone_handoff(self):
        session_hash = self._signed_in()
        data = self._lobby(session_hash, 0x26)
        self.assertEqual(data[8], 0x05)
        data = self._lobby(session_hash, 0x1F)
        self.assertEqual(data[8], 0x20)
        self.assertEqual(struct.unpack_from("<I", data, 28)[0], 1)
        body = struct.pack("<I", self.character["char_id"])
        data = self._lobby(session_hash, 0x07, body)
        self.assertEqual(data[8], 0x0B)
        cid = struct.unpack_from("<I", data, 28)[0]
        self.assertEqual(cid, self.character["char_id"])

    def test_data_connection_and_zone_login(self):
        session_hash = self._signed_in()
        # The login-data connection: 0xFE + the session hash, then the zone key (0xA2).
        with socket.create_connection(("127.0.0.1", self.config.ports["data_port"]), timeout=10) as sock:
            first = bytearray(28)
            first[0] = 0xFE
            first[12:28] = session_hash
            sock.sendall(first)
            key = bytes(range(20))
            sock.sendall(b"\xA2" + key)
            sock.settimeout(0.3)
            try:
                sock.recv(28)
            except socket.timeout:
                pass
        # The lobby hands the character to its zone.
        self._lobby(session_hash, 0x07, struct.pack("<I", self.character["char_id"]))
        # A clear 0x00A login, with the content id where the zone looks for it and MD5 at the end.
        body = bytearray(0x100)
        struct.pack_into("<I", body, 8, self.character["char_id"])
        login = sub(0x00A, body)
        packet = bytearray(HDR + len(login) + 16)
        packet[HDR:HDR + len(login)] = login
        packet[-16:] = md5(bytes(packet[HDR:-16]))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(5)
            udp.sendto(packet, ("127.0.0.1", self.config.ports["zone_port"]))
            reply, _addr = udp.recvfrom(4096)
        self.assertGreater(len(reply), HDR + 20)


class CharacterRecordTest(unittest.TestCase):
    def test_record_is_140_bytes(self):
        record = character_record({
            "char_id": 0x01000001, "name": "Fanxi", "server_name": "Fanxi", "race": 1, "face": 1,
            "size": 1, "nation": 0, "main_job": 1, "sub_job": 0, "main_level": 1, "zone": 246,
            "head": 0, "body": 8, "hands": 8, "legs": 8, "feet": 8, "main": 0, "sub": 0,
        })
        self.assertEqual(len(record), 140)
        self.assertEqual(record[12:17], b"Fanxi")


if __name__ == "__main__":
    unittest.main()
