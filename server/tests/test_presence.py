"""Player-to-player presence: 0x00D spawns, movement, despawns and targids.

Until this existed, two clients in the same zone were invisible to each other: the
server only streamed 0x00E NPC/mob entities. These tests drive two real ZoneSessions and
read the 0x00D packets the other client receives.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_huffman_dir, make_service

from fanxi_server.game import effects, packets
from fanxi_server.game.cipher import Huffman, md5
from fanxi_server.game.world import (
    PLAYER_TARGID_FIRST,
    PLAYER_TARGID_LAST,
    SESSION_IDLE_TIMEOUT,
    World,
)
from fanxi_server.game.zone import HDR, ZONE_IN_REBUILDS, ZoneSession, sub


def message_type(message) -> int:
    return struct.unpack_from("<H", message, 0)[0] & 0x1FF


def player_messages(session) -> list[bytes]:
    return [message for message in session.queue
            if message_type(message) == 0x00D and len(message) >= 4 + 0x40]


def player_fields(message) -> dict:
    body = message[4:]
    char_id, targid, mask = struct.unpack_from("<IHB", body, 0)
    if len(body) < 0x68:
        return {"char_id": char_id, "targid": targid, "mask": mask,
                "rot": 0, "x": 0.0, "y": 0.0, "z": 0.0, "walk": 0, "name": ""}
    rot, x, y, z = struct.unpack_from("<Bfff", body, 7)
    walk = struct.unpack_from("<H", body, 0x14)[0] & 0x1FFF
    name = body[0x56:0x66].split(b"\0")[0].decode("ascii", "replace")
    return {"char_id": char_id, "targid": targid, "mask": mask, "rot": rot,
            "x": x, "y": y, "z": z, "walk": walk, "name": name}


def position_packet(x: float, y: float, z: float, rot: int = 0) -> bytes:
    packet = bytearray(0x18)
    struct.pack_into("<fff", packet, 4, x, y, z)
    packet[20] = rot & 0xFF
    return bytes(packet)


class PresenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.world = World(self.config, self.service, None)
        self.a = self.session("Alpha", 5001, -87.0, 12.0, 116.0)
        self.b = self.session("Beta", 5002, -85.0, 12.0, 116.0)

    def session(self, name: str, port: int, x: float, y: float, z: float) -> ZoneSession:
        account = self.service.register(name.lower(), "password123").account
        character = self.service.create_character(
            account["id"], {"name": name, "race": 1, "face": 1, "size": 1,
                            "nation": 0, "main_job": 1})
        record = self.service.character_record(
            self.service.character(character["id"]), "Fanxi")
        session = ZoneSession(self.world, ("127.0.0.1", port), record)
        session.set_key(bytes(20))
        session.char["char_id"] = int(record["char_id"])
        session.targid = self.world.assign_player_targid(int(session.char["char_id"]))
        session.logged_in = True
        session.zone = 246
        session.pos = [x, y, z, 0]
        session.load_zone_entities()
        session.zone_loaded = True
        session.entities_sent = True
        session.queue.clear()
        self.world.sessions[("127.0.0.1", port)] = session
        return session

    def test_targids_are_in_the_player_range_and_unique(self):
        a, b = int(self.a.char["char_id"]), int(self.b.char["char_id"])
        self.assertNotEqual(self.a.targid, self.b.targid)
        for targid in (self.a.targid, self.b.targid):
            self.assertGreaterEqual(targid, PLAYER_TARGID_FIRST)
            self.assertLessEqual(targid, PLAYER_TARGID_LAST)

    def test_players_spawn_each_other_once(self):
        self.a.sync_players()
        self.b.sync_players()
        spawns = [player_fields(message) for message in player_messages(self.a)]
        self.assertEqual(len(spawns), 1)
        self.assertEqual(spawns[0]["char_id"], int(self.b.char["char_id"]))
        self.assertEqual(spawns[0]["targid"], self.b.targid)
        self.assertEqual(spawns[0]["mask"], packets.SEND_CHAR_SPAWN)
        self.assertEqual(spawns[0]["name"], "Beta")
        self.assertNotIn(int(self.a.char["char_id"]),
                         [fields["char_id"] for fields in spawns])
        # A second sweep does not duplicate the spawn.
        self.a.queue.clear()
        self.a.sync_players()
        self.assertEqual(player_messages(self.a), [])

    def test_movement_is_broadcast_and_stop_is_sent(self):
        self.a.sync_players()
        self.b.sync_players()
        self.b.queue.clear()
        self.a.last_player_update = 0.0
        self.a.handle(0x015, position_packet(-86.0, 12.0, 116.0, 64))
        updates = [player_fields(message) for message in player_messages(self.b)]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["mask"], packets.SEND_POSITION)
        self.assertAlmostEqual(updates[0]["x"], -86.0, places=2)
        self.assertEqual(updates[0]["walk"], 1)
        # The same position again means stopped: one final walk=0 update.
        self.b.queue.clear()
        self.a.handle(0x015, position_packet(-86.0, 12.0, 116.0, 64))
        updates = [player_fields(message) for message in player_messages(self.b)]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["walk"], 0)

    def test_invisible_reaches_the_observer_before_the_next_heartbeat(self):
        """0x00D Flags1 bit 29 is InvisFlag: the other client stops drawing the player.

        The effect's own refresh has to carry it.  A General block otherwise only rides
        an HP update, so an invisible character standing still stayed visible to every
        other client until something happened to their HP.
        """
        self.a.sync_players()
        self.b.sync_players()
        self.b.queue.clear()
        self.a.add_effect(effects.INVISIBLE, duration=420)
        updates = player_messages(self.b)
        self.assertTrue(updates)
        self.assertEqual(updates[-1][4 + 6], packets.SEND_HP)  # General block, not position
        flags1 = struct.unpack_from("<I", updates[-1], 4 + 0x1C)[0]
        self.assertTrue(flags1 & (1 << 29))
        # Wearing off clears the flag for the observers too.
        self.b.queue.clear()
        self.a.remove_effect(effects.INVISIBLE)
        updates = player_messages(self.b)
        self.assertTrue(updates)
        self.assertFalse(struct.unpack_from("<I", updates[-1], 4 + 0x1C)[0] & (1 << 29))

    def test_a_stationary_player_refreshes_its_position(self):
        """A late-loading observer converges without waiting for the leader to move again.

        A box that zoned in while its leader walked can miss every position packet the
        walk broadcast and keep the copy it spawned with.  The 1 Hz refresh is what puts
        the observer back on the leader where it actually stands.
        """
        self.a.sync_players()
        self.b.sync_players()
        self.a.queue.clear()
        now = time.time()
        self.b.moving = False
        self.b.next_position_refresh = 0.0
        self.b.next_player_sync = now + 100.0
        self.b.next_entity_sync = now + 100.0
        self.b.tick(now)
        updates = [player_fields(message) for message in player_messages(self.a)]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["mask"], packets.SEND_POSITION)
        self.assertAlmostEqual(updates[0]["x"], self.b.pos[0], places=2)

        # A moving player is already covered by the movement broadcasts.
        self.a.queue.clear()
        self.b.moving = True
        self.b.next_position_refresh = 0.0
        self.b.tick(now + 2.0)
        self.assertEqual(player_messages(self.a), [])

    def test_zone_change_despawns_player(self):
        self.a.sync_players()
        self.b.sync_players()
        self.b.queue.clear()
        self.a.change_zone(100, [-126.0, -62.0, 273.0, 99])
        despawns = [player_fields(message) for message in player_messages(self.b)]
        self.assertGreaterEqual(len(despawns), 1)
        self.assertEqual(despawns[0]["char_id"], int(self.a.char["char_id"]))
        self.assertEqual(despawns[0]["mask"], packets.SEND_PLAYER_DESPAWN)
        # LSB sends a despawn at the nonspecific size (0x40 body), not a full spawn body.
        self.assertTrue(any(len(message) == 4 + 0x40 for message in player_messages(self.b)))
        self.assertNotIn(int(self.a.char["char_id"]), self.b.seen_players)

    def test_moving_out_of_range_despawns(self):
        self.a.sync_players()
        self.b.sync_players()
        self.b.pos = [0.0, 0.0, 0.0, 0]
        self.a.queue.clear()
        self.a.sync_players()
        despawns = [player_fields(message) for message in player_messages(self.a)]
        self.assertGreaterEqual(len(despawns), 1)
        self.assertEqual(despawns[0]["mask"], packets.SEND_PLAYER_DESPAWN)

    def test_logout_despawns_and_frees_targid(self):
        self.a.sync_players()
        self.b.sync_players()
        self.b.queue.clear()
        char_id = int(self.a.char["char_id"])
        self.a.handle(0x0E7, b"")
        despawns = [player_fields(message) for message in player_messages(self.b)]
        self.assertGreaterEqual(len(despawns), 1)
        self.assertEqual(despawns[0]["mask"], packets.SEND_PLAYER_DESPAWN)
        self.assertTrue(self.a.gone)
        self.assertNotIn(char_id, self.world.player_targids)

    def test_sleep_leaves_party_and_wake_rejoins(self):
        group = self.world.create_party(self.a)
        self.assertTrue(self.world.join_party(group, self.b))
        group_id = group.id
        self.assertEqual(self.world.party_of(int(self.a.char["char_id"])).id, group_id)
        self.a.sleep()
        self.assertIsNone(self.world.party_of(int(self.a.char["char_id"])))
        self.assertEqual(self.world.party_of(int(self.b.char["char_id"])).id, group_id)
        self.a.wake()
        joined = self.world.party_of(int(self.a.char["char_id"]))
        self.assertIsNotNone(joined)
        self.assertEqual(joined.id, group_id)

    def test_sleep_hides_then_wake_restores_in_place(self):
        self.a.sync_players()
        self.b.sync_players()
        self.b.queue.clear()
        char_id = int(self.a.char["char_id"])

        self.a.sleep()
        self.assertTrue(self.a.sleeping)
        self.assertNotIn(self.a, self.world.sessions_in_zone(246))
        self.assertIsNone(self.world.session_by_char(char_id))
        despawns = [player_fields(message) for message in player_messages(self.b)]
        self.assertGreaterEqual(len(despawns), 1)
        self.assertEqual(despawns[0]["mask"], packets.SEND_PLAYER_DESPAWN)
        # A sleeping session is not the sixty-second silence path.
        self.a.last_packet_at = time.time() - SESSION_IDLE_TIMEOUT - 1
        self.world.advance(time.time())
        self.assertFalse(self.a.gone)
        self.assertIn(("127.0.0.1", 5001), self.world.sessions)

        self.a.queue.clear()
        self.a.wake()
        self.assertFalse(self.a.sleeping)
        self.assertIn(self.a, self.world.sessions_in_zone(246))
        self.assertEqual(self.world.session_by_char(char_id), self.a)
        self.assertTrue(any(message_type(message) == 0x00D for message in self.a.queue))
        self.b.queue.clear()
        self.b.sync_players()
        spawns = [player_fields(message) for message in player_messages(self.b)]
        self.assertTrue(any(fields["mask"] == packets.SEND_CHAR_SPAWN for fields in spawns))

    def test_silent_client_is_reaped_and_despawned(self):
        """A force-quit sends nothing. The session must not stay as a frozen twin."""
        self.a.sync_players()
        self.b.sync_players()
        self.b.queue.clear()
        char_id = int(self.a.char["char_id"])
        self.a.last_packet_at = time.time() - SESSION_IDLE_TIMEOUT - 1
        self.world.advance(time.time())
        despawns = [player_fields(message) for message in player_messages(self.b)]
        self.assertGreaterEqual(len(despawns), 1)
        self.assertEqual(despawns[0]["char_id"], char_id)
        self.assertEqual(despawns[0]["mask"], packets.SEND_PLAYER_DESPAWN)
        self.assertTrue(self.a.gone)
        self.assertNotIn(("127.0.0.1", 5001), self.world.sessions)
        self.assertNotIn(char_id, self.world.player_targids)
        self.assertNotIn(char_id, self.b.seen_players)
        # It does not reappear on the next sweep.
        self.b.queue.clear()
        self.b.sync_players()
        self.assertEqual(player_messages(self.b), [])


class LoginSessionTest(unittest.TestCase):
    """A 0x00A continues a hand-off, never the previous occupant of a recycled port."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        self.config, self.db, self.service = make_service(tmp)
        self.huff = Huffman.from_folder(make_huffman_dir(tmp))
        self.world = World(self.config, self.service, self.huff)

    def character(self, name: str):
        account = self.service.register(name.lower(), "password123").account
        row = self.service.create_character(account["id"], {
            "name": name, "race": 1, "face": 1, "size": 1, "nation": 0, "main_job": 1,
        })
        self.service.save_position(row["id"], 246, [-87.0, 12.0, 116.0, 0])
        return account, self.service.character(row["id"])

    def game_session(self, account) -> bytes:
        launch = self.service.launch(account, None, ip="127.0.0.1")
        _account, session_hash = self.service.game_login({
            "command": 16, "username": account["username"], "password": "",
            "login_token": launch["login_token"], "version": [2, 2, 0],
        }, "127.0.0.1")
        return session_hash

    def session(self, character, addr, zone: int = 246):
        record = self.world.character_record(character)
        session = ZoneSession(self.world, addr, record)
        session.set_key(bytes(20))
        session.char["char_id"] = int(record["char_id"])
        session.targid = self.world.assign_player_targid(int(session.char["char_id"]))
        session.logged_in = True
        session.zone = zone
        session.pos = [-87.0, 12.0, 116.0, 0]
        session.load_zone_entities()
        session.zone_loaded = True
        session.entities_sent = True
        session.queue.clear()
        self.world.sessions[addr] = session
        return session

    @staticmethod
    def login_packet(cid: int) -> bytearray:
        # A clear 0x00A: the client's id at message offset 8 and MD5 over the body.
        body = bytearray(0x100)
        struct.pack_into("<I", body, 8, int(cid))
        login = sub(0x00A, body)
        packet = bytearray(HDR + len(login) + 16)
        packet[HDR:HDR + len(login)] = login
        packet[-16:] = md5(bytes(packet[HDR:-16]))
        return packet

    def test_relogin_on_a_reused_port_keeps_its_own_character(self):
        """The live bug: six relogging mules reused the old UDP ports and inherited
        each other's character records, so two clients drew the same name."""
        addr = ("127.0.0.1", 54090)
        _a_account, a_row = self.character("Alpha")
        b_account, b_row = self.character("Beta")
        _o_account, o_row = self.character("Observer")
        old = self.session(a_row, addr)
        observer = self.session(o_row, ("127.0.0.1", 54091))
        observer.queue.clear()
        observer.sync_players()
        self.assertIn(int(old.char["char_id"]), observer.seen_players)
        observer.queue.clear()

        # The launcher prepared Beta's zone-in while the dead Alpha session still
        # occupied the address Beta's client is about to reuse.
        b_hash = self.game_session(b_account)
        prepared = self.world.prepare_zone_in(
            b_account["id"], b_hash, self.world.character_record(b_row))
        reply = ZoneSession.incoming(
            self.world, self.world.sessions[addr], addr, self.login_packet(b_row["id"]))

        self.assertIsNotNone(reply)
        new = self.world.sessions[addr]
        self.assertIs(new, prepared)
        self.assertEqual(int(new.char["id"]), int(b_row["id"]))
        self.assertEqual(new.char["name"], "Beta")
        self.assertEqual(int(new.char["char_id"]), int(b_row["id"]))
        # The force-quit Alpha session is gone, not left behind as a second character.
        self.assertNotIn(old, self.world.sessions.values())
        self.assertTrue(old.gone)
        self.assertNotIn(int(a_row["char_id"]), self.world.player_targids)
        despawns = [player_fields(message) for message in player_messages(observer)]
        self.assertGreaterEqual(len(despawns), 1)
        self.assertEqual(despawns[0]["char_id"], int(a_row["char_id"]))
        self.assertEqual(despawns[0]["mask"], packets.SEND_PLAYER_DESPAWN)

        # Once the new client is in the zone, the observer sees Beta exactly once --
        # carrying Beta's name and targid, not the old session's.
        new.zone_loaded = True
        new.entities_sent = True
        new.queue.clear()
        observer.queue.clear()
        observer.sync_players()
        spawns = [player_fields(message) for message in player_messages(observer)]
        self.assertEqual(len(spawns), 1)
        self.assertEqual(spawns[0]["char_id"], int(b_row["id"]))
        self.assertEqual(spawns[0]["name"], "Beta")
        self.assertEqual(spawns[0]["targid"], new.targid)
        observer.queue.clear()
        observer.sync_players()
        self.assertEqual(player_messages(observer), [])

    def test_zone_change_handoff_advances_the_key(self):
        addr = ("127.0.0.1", 54110)
        account, row = self.character("Gamma")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        self.game_session(account)

        # A box that was standing still has not sent a packet for minutes; the zone-change
        # window still starts when the warp is queued, not at that old packet.
        session.last_packet_at = time.time() - 60
        before = bytes(session.key)
        # A real zone change queues 0x00B; building it parks the session in by_char and
        # moves the cipher on by 2, which is what the client does with its own key. The
        # zone-in must go out under that advanced key: encrypting it under the old one is
        # what left the client on the "Downloading" screen.
        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        session.build(bytearray(HDR))
        after = bytes(session.key)
        self.assertIn(int(row["id"]), self.world.by_char)
        self.assertEqual(session.base_key, before)
        self.assertEqual(struct.unpack_from("<I", after, 16)[0],
                         (struct.unpack_from("<I", before, 16)[0] + 2) & 0xFFFFFFFF)

        reply = ZoneSession.incoming(self.world, session, addr, self.login_packet(row["char_id"]))

        self.assertIsNotNone(reply)
        self.assertIs(self.world.sessions[addr], session)
        self.assertFalse(session.zoning)
        self.assertEqual(int(session.zone), 100)
        self.assertEqual(bytes(session.key), after)
        self.assertEqual(int(session.char["id"]), int(row["id"]))

        # The client that advanced opens the reply under the advanced key.
        body = bytearray(reply[HDR:])
        self.world.zone_cipher_for(after).run(body, 0, (len(body) // 4) & ~1, False)
        nbits = struct.unpack_from("<I", body, len(body) - 20)[0]
        plain = self.world.huff.decompress(bytes(body[:len(body) - 20]), nbits)
        self.assertIn(0x00A, [message_type(plain[off:off + 4])
                              for off in range(0, len(plain) - 3, 4)])

    def sealed(self, message: bytes, key: bytes, ack: int) -> bytearray:
        """One client packet: compressed body, nbits and MD5, then enciphered."""
        compressed, nbits = self.world.huff.compress(message)
        data = compressed + struct.pack("<I", nbits)
        data += md5(data)
        packet = bytearray(HDR + len(data))
        struct.pack_into("<HH", packet, 0, 7, ack)
        packet[HDR:] = data
        self.world.zone_cipher_for(key).run(packet, HDR, (len(data) // 4) & ~1, True)
        return packet

    def test_a_late_old_key_packet_does_not_change_the_reply_key(self):
        """A packet sent before the client saw 0x00B is not proof that it kept its key.

        Following it used to pin every reply to the pre-change key, so the zone-in was
        enciphered with a key the client had already moved past and it never loaded.
        """
        addr = ("127.0.0.1", 54114)
        account, row = self.character("Eta")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        self.game_session(account)
        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        session.build(bytearray(HDR))
        advanced, old = bytes(session.key), bytes(session.base_key)
        self.assertNotEqual(advanced, old)

        ZoneSession.incoming(self.world, session, addr,
                             self.sealed(sub(0x015, bytes(0x1C) + struct.pack("<fff", 1, 2, 3)),
                                         old, session.server_id))
        self.assertEqual(bytes(session.key), advanced)

        reply = ZoneSession.incoming(self.world, session, addr,
                                     self.login_packet(row["char_id"]))
        body = bytearray(reply[HDR:])
        self.world.zone_cipher_for(advanced).run(body, 0, (len(body) // 4) & ~1, False)
        nbits = struct.unpack_from("<I", body, len(body) - 20)[0]
        plain = self.world.huff.decompress(bytes(body[:len(body) - 20]), nbits)
        self.assertIsNotNone(plain)
        self.assertIn(0x00A, [message_type(plain[off:off + 4])
                              for off in range(0, len(plain) - 3, 4)])

    def test_a_client_that_kept_the_old_key_is_followed_at_0x00C(self):
        """0x00C is the packet that proves which key the client is using."""
        addr = ("127.0.0.1", 54115)
        account, row = self.character("Theta")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        self.game_session(account)
        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        session.build(bytearray(HDR))
        old = bytes(session.base_key)
        self.assertNotEqual(bytes(session.key), old)
        ZoneSession.incoming(self.world, session, addr,
                             self.sealed(sub(0x00C, bytes(8)), old, session.server_id))
        self.assertEqual(bytes(session.key), old)

    def zone_change_reply(self, name: str, addr, drift: int):
        """A zone change queued and built, and the client's login that follows it."""
        account, row = self.character(name)
        session = self.session(row, addr)
        session.set_key(bytes(20))
        self.game_session(account)
        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        zone_out = session.build(bytearray(HDR))
        ack = struct.unpack_from("<H", zone_out, 0)[0]
        login = self.login_packet(row["char_id"])
        struct.pack_into("<H", login, 2, ack)                       # the id we sent last
        struct.pack_into("<H", login, HDR + 2, (ack + drift) & 0xFFFF)  # the client's counter
        login[-16:] = md5(bytes(login[HDR:-16]))
        return session, login, ack

    def test_fast_same_zone_reconnect_continues_the_handoff(self):
        """A same-zone warp reconnects inside the retry window; it is not a failed zone-in.

        The 0x00A after 0x00B used to look like a client retrying the zone-in because the
        previous packet was recent.  That replay path rebuilt a zone-in the client was
        already about to acknowledge, and some boxes looped on it forever.
        """
        addr = ("127.0.0.1", 54111)
        account, row = self.character("Zeta")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        self.game_session(account)
        session.last_packet_at = time.time()  # fast reconnect, not an old idle packet

        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        session.build(bytearray(HDR))
        self.assertEqual(session.zone_in_tries, 0)

        reply = ZoneSession.incoming(self.world, session, addr, self.login_packet(row["char_id"]))

        self.assertIsNotNone(reply)
        self.assertEqual(session.zone_in_tries, 0)
        self.assertFalse(session.zoning)
        self.assertEqual(int(session.zone), 100)
        self.assertEqual(int(session.char["id"]), int(row["id"]))

    def test_zone_change_reply_answers_the_acked_packet(self):
        """The zone-in id is the ack + 1, not the client's body counter.

        The body sync word is the client's own packet number. It drifts ahead of the
        server's sequence when a client packet goes unanswered, and using it as the
        reply id handed the client a packet id it had already passed: it ignored the
        zone-in and retried the login every two seconds (stuck on "Downloading").
        """
        addr = ("127.0.0.1", 54111)
        session, login, ack = self.zone_change_reply("Delta", addr, -6)
        reply = ZoneSession.incoming(self.world, session, addr, login)
        self.assertIsNotNone(reply)
        self.assertEqual(struct.unpack_from("<H", reply, 0)[0], (ack + 1) & 0xFFFF)

    def test_retried_login_rebuilds_the_zone_in(self):
        addr = ("127.0.0.1", 54112)
        session, login, ack = self.zone_change_reply("Epsilon", addr, 3)
        first = ZoneSession.incoming(self.world, session, addr, login)
        self.assertIsNotNone(first)
        self.assertEqual(session.zone_in_tries, 0)

        # The client repeats the login; the burst is rebuilt under the same next id
        # rather than the already-ignored packet being replayed byte for byte.
        again = ZoneSession.incoming(self.world, session, addr, login)
        self.assertIsNotNone(again)
        self.assertEqual(session.zone_in_tries, 1)
        self.assertEqual(struct.unpack_from("<H", again, 0)[0], (ack + 1) & 0xFFFF)
        body = bytearray(again[HDR:])
        # The first retry goes out under the pre-change key (the other cipher).
        session.world.zone_cipher_for(bytes(session.base_key)).run(
            body, 0, (len(body) // 4) & ~1, False)
        nbits = struct.unpack_from("<I", body, len(body) - 20)[0]
        plain = session.world.huff.decompress(bytes(body[:len(body) - 20]), nbits)
        self.assertIn(0x00A, [message_type(plain[off:off + 4])
                              for off in range(0, len(plain) - 3, 4)])

    def test_login_that_is_never_acknowledged_starts_over(self):
        addr = ("127.0.0.1", 54113)
        session, login, _ack = self.zone_change_reply("Zeta", addr, 2)
        for _ in range(ZONE_IN_REBUILDS + 2):
            ZoneSession.incoming(self.world, session, addr, login)
        self.assertTrue(session.gone)
        self.assertIsNone(self.world.session_by_char(int(session.char["char_id"])))

    def opened_body(self, packet: bytes, key: bytes):
        """The plaintext of a server packet under ``key``, or None if it does not open."""
        body = bytearray(packet[HDR:])
        self.world.zone_cipher_for(key).run(body, 0, (len(body) // 4) & ~1, False)
        if md5(bytes(body[:-16])) != bytes(body[-16:]):
            return None
        nbits = struct.unpack_from("<I", body, len(body) - 20)[0]
        return self.world.huff.decompress(bytes(body[:len(body) - 20]), nbits)

    def test_zone_in_copies_cover_keys_the_client_may_have_kept(self):
        """A client can be several 0x00B bumps behind; one copy must always open.

        The old retry alternated only the newest key and the one before it, so a client
        that missed two hand-offs was on a key the server no longer sent under: it sat on
        "Downloading" and the only recovery was a relaunch.
        """
        addr = ("127.0.0.1", 54116)
        account, row = self.character("Iota")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        self.game_session(account)
        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        session.build(bytearray(HDR))        # the hand-off the client did receive
        client_key = bytes(session.key)
        session.bump_key()                   # ...and these two never reached it
        session.bump_key()
        newest = bytes(session.key)

        reply = ZoneSession.incoming(self.world, session, addr,
                                     self.login_packet(row["char_id"]))
        self.assertIsNotNone(reply)
        self.assertEqual(bytes(session.key), newest)
        self.assertIsNotNone(self.opened_body(reply, newest))
        self.assertTrue(session.extra_packets)
        opened = [self.opened_body(packet, client_key) for packet in session.extra_packets]
        self.assertTrue(any(body is not None for body in opened),
                        "no zone-in copy opens under the key the client kept")
        self.assertTrue(any(0x00A in [message_type(body[off:off + 4])
                                      for off in range(0, len(body) - 3, 4)]
                            for body in opened if body))

    def test_a_relog_after_a_failed_handoff_resumes_the_clients_key(self):
        """The drop-after-four-retries path must not reset to the sign-in key.

        The client keeps the key it advanced to when it relogs on the same game session;
        sending the zone-in under the sign-in key is exactly the permanent loop the live
        boxes showed (ack 0, start over, repeat forever).
        """
        addr = ("127.0.0.1", 54117)
        account, row = self.character("Kappa")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        session.session_hash = self.game_session(account)
        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        session.build(bytearray(HDR))
        advanced = bytes(session.key)
        login = self.login_packet(row["char_id"])
        for _ in range(ZONE_IN_REBUILDS + 2):
            ZoneSession.incoming(self.world, session, addr, login)
        self.assertTrue(session.gone)

        reply = ZoneSession.incoming(self.world, session, addr,
                                     self.login_packet(row["char_id"]))
        self.assertIsNotNone(reply)
        relogged = self.world.sessions[addr]
        self.assertEqual(bytes(relogged.key), advanced)
        self.assertNotEqual(bytes(relogged.key), bytes(20))
        self.assertIsNotNone(self.opened_body(reply, advanced))

    def test_a_relog_that_replaces_a_live_session_keeps_the_advanced_key(self):
        """A reconnect can replace a box that was already in the world.

        The old session was not mid-hand-off, so its key was never parked; the next login
        then reset to the sign-in key and looped forever.  The live session's sequence has
        to be parked even though it had finished its zone-in.
        """
        addr = ("127.0.0.1", 54119)
        account, row = self.character("Muon")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        session.session_hash = self.game_session(account)
        session.bump_key()                 # the client processed an earlier 0x00B
        advanced = bytes(session.key)
        self.assertTrue(session.zone_loaded)

        self.world.evict_session(session, save=True, reason="replaced by a login")
        self.assertTrue(session.gone)

        reply = ZoneSession.incoming(self.world, None, addr,
                                     self.login_packet(row["char_id"]))
        self.assertIsNotNone(reply)
        relogged = self.world.sessions[addr]
        self.assertEqual(bytes(relogged.key), advanced)
        self.assertIsNotNone(self.opened_body(reply, advanced))

    def test_a_boxes_handoff_survives_another_login_taking_its_old_port(self):
        """Two boxes on one host can be handed each other's ports after a zone change.

        The live log showed a box cross a line, then another box log in from the address
        the first had just given up.  Clearing that "recycled port" evicted the first
        box's prepared hand-off: it left the party and lost the advanced cipher it was
        about to prove.  The hand-off must survive and its own login must continue it.
        """
        old_addr = ("127.0.0.1", 54602)
        new_addr = ("127.0.0.1", 54858)
        one_account, one_row = self.character("Fourdough")
        _two_account, two_row = self.character("Fivedough")
        one = self.session(one_row, old_addr)
        one.session_hash = self.game_session(one_account)
        one.change_zone(100, [-126.0, -62.0, 273.0, 99])
        one.build(bytearray(HDR))                  # the 0x00B the client received
        advanced = bytes(one.key)

        # Fivedough's client reconnects on the port Fourdough just released.
        other, _continuing = self.world.take_login(
            old_addr, self.world.character_record(two_row), int(two_row["char_id"]))
        self.world.sessions[old_addr] = other

        self.assertFalse(one.gone)
        self.assertIn(one, self.world.by_char.values())

        # Fourdough's own login then resumes the hand-off from its new port, under the
        # key its client advanced to.
        reply = ZoneSession.incoming(self.world, None, new_addr,
                                     self.login_packet(one_row["char_id"]))
        self.assertIsNotNone(reply)
        resumed = self.world.sessions[new_addr]
        self.assertIs(resumed, one)
        self.assertFalse(resumed.zoning)
        self.assertEqual(bytes(resumed.key), advanced)
        self.assertIsNotNone(self.opened_body(reply, advanced))
        self.assertFalse(other.gone)

    def test_a_shorter_parked_sequence_does_not_forget_the_advanced_key(self):
        """A fresh replacement login can know fewer keys than the hand-off it replaced.

        Parking its one key over the longer sequence is what left a live box retrying the
        same zone-in forever: the server kept sending copies under a key the client had
        already advanced past.
        """
        addr = ("127.0.0.1", 54120)
        account, row = self.character("Nuon")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        session.session_hash = self.game_session(account)
        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        session.build(bytearray(HDR))
        advanced = bytes(session.key)
        self.world.evict_session(session, save=True, reason="replaced by a login")

        fresh = self.session(self.service.character(row["id"]), addr)
        fresh.set_key(bytes(20))
        fresh.session_hash = session.session_hash
        self.world.evict_session(fresh, save=True, reason="zone-in never acknowledged")

        history = self.world.parked_history(row)
        self.assertIn(advanced, history)
        self.assertIn(bytes(20), history)

    def test_a_fresh_login_gets_a_dropped_handoffs_keys_as_copies(self):
        """The game session that parked a sequence can be gone by the next login.

        A relaunch creates a new game session, so the hash check cannot resume the entry.
        The client the player did not restart still holds the advanced key: the parked
        sequence has to ride along as extra copies while the sign-in key stays primary.
        """
        addr = ("127.0.0.1", 54121)
        account, row = self.character("Xion")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        session.session_hash = self.game_session(account)
        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        session.build(bytearray(HDR))
        advanced = bytes(session.key)
        self.world.evict_session(session, save=True, reason="replaced by a login")

        self.game_session(account)          # a relaunch: a different game session hash
        reply = ZoneSession.incoming(self.world, None, addr,
                                     self.login_packet(row["char_id"]))
        self.assertIsNotNone(reply)
        relogged = self.world.sessions[addr]
        self.assertNotEqual(bytes(relogged.key), advanced)
        self.assertTrue(relogged.extra_packets)
        opened = [self.opened_body(packet, advanced)
                  for packet in relogged.extra_packets]
        self.assertTrue(any(body is not None for body in opened),
                        "no copy opens under the key the client still holds")

    def test_a_zone_change_during_a_handoff_is_deferred_not_bumped(self):
        """A second warp mid-load used to send another 0x00B and advance the key again."""
        addr = ("127.0.0.1", 54118)
        account, row = self.character("Lambda")
        session = self.session(row, addr)
        session.set_key(bytes(20))
        self.game_session(account)
        session.change_zone(100, [-126.0, -62.0, 273.0, 99])
        session.build(bytearray(HDR))
        first_key = bytes(session.key)

        session.change_zone(101, [1.0, 2.0, 3.0, 4.0])

        self.assertEqual(bytes(session.key), first_key)
        self.assertEqual(session.pending_zone[0], 101)
        self.assertEqual(len([m for m in session.queue if message_type(m) == 0x00B]), 0)

        ZoneSession.incoming(self.world, session, addr, self.login_packet(row["char_id"]))
        self.assertFalse(session.zoning)
        session.handle(0x00C, bytes(8))

        # The deferred move runs only now that the client has acknowledged the zone.
        self.assertTrue(session.zoning)
        self.assertEqual(int(session.zone), 101)
        zone_outs = [m for m in session.queue if message_type(m) == 0x00B]
        self.assertEqual(len(zone_outs), 1)
        # The next packet carries the 0x00B; that is what moves the cipher on.  The
        # zone-in burst queued ahead of it may take more than one packet.
        for _ in range(10):
            session.build(bytearray(HDR))
            if bytes(session.key) != first_key:
                break
        self.assertNotEqual(bytes(session.key), first_key)


if __name__ == "__main__":
    unittest.main()
