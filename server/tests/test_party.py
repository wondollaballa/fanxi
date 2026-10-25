"""Party and alliance rosters: packet layouts and the invite/leave/kick flow."""
from __future__ import annotations

import struct
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path

import support  # noqa: F401  (puts server/ on sys.path)

from fanxi_server.game import packets
from fanxi_server.game.party import (
    ALLIANCE_LEADER,
    PARTY_KIND_ALLIANCE,
    PARTY_LEADER,
    PARTY_SECOND,
    PartyMember,
)
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession, sub


def message_type(message) -> int:
    return struct.unpack_from("<H", message, 0)[0] & 0x1FF


def message_types(session) -> list[int]:
    return [message_type(message) for message in session.queue]


def make_world() -> World:
    """A World with only the group state; these tests never touch zones or SQLite."""
    world = World.__new__(World)
    world.sessions = {}
    world.by_char = {}
    world.party_by_char = {}
    world.parties = {}
    world.alliances = {}
    world.pending_invites = {}
    world.next_alliance_id = 1
    world.next_party_sync = 0.0
    world.lock = threading.RLock()
    world.service = None
    world.config = None
    return world


def add_session(world: World, char_id: int, name: str, targid: int,
                zone: int = 230, account_id: int | None = None) -> ZoneSession:
    char = {
        "id": char_id + 1000, "char_id": char_id, "name": name, "zone": zone,
        "account_id": char_id if account_id is None else account_id,
        "hp": 100, "mp": 50, "hp_current": 100, "mp_current": 50, "tp": 0,
        "main_job": 1, "main_level": 10, "sub_job": 0, "sub_level": 0, "moghouse": 0,
    }
    session = ZoneSession(world, None, char)
    session.logged_in = True
    session.zone_loaded = True
    session.key = b"k" * 20
    session.zone = zone
    session.targid = targid
    # The reset path also repaints the character's own vitals; those packets are not
    # what these tests are about, and the real ones need the stat sheet/database.
    session.char_status = lambda: sub(0x037, bytes(4))
    session.char_stats = lambda: sub(0x061, bytes(4))
    session.party_member = lambda: sub(0x0DF, bytes(4))
    world.sessions[("127.0.0.1", 50000 + char_id)] = session
    return session


class GroupPacketTest(unittest.TestCase):
    def test_invite_layout(self):
        body = packets.group_invite(0x01020304, 0x405, "Ally", PARTY_KIND_ALLIANCE, race=3)
        self.assertEqual(len(body), 0x1C)
        self.assertEqual(struct.unpack_from("<I", body, 0x00)[0], 0x01020304)
        self.assertEqual(struct.unpack_from("<H", body, 0x04)[0], 0x405)
        self.assertEqual(body[0x06], 0)                 # AnonFlag
        self.assertEqual(body[0x07], PARTY_KIND_ALLIANCE)
        self.assertEqual(bytes(body[0x08:0x0D]), b"Ally\x00")
        self.assertEqual(struct.unpack_from("<H", body, 0x18)[0], 3)

    def test_group_table_layout(self):
        body = packets.group_table([(1, 0x400, PARTY_LEADER, 230),
                                    (2, 0x401, PARTY_SECOND, 231)], PARTY_KIND_ALLIANCE)
        self.assertEqual(len(body), 4 + 20 * 12)
        self.assertEqual(body[0], PARTY_KIND_ALLIANCE)
        char_id, targid, flags, pad, zone, pad2 = struct.unpack_from("<IHBBHH", body, 4)
        self.assertEqual((char_id, targid, flags, pad, zone, pad2), (1, 0x400, 4, 0, 230, 0))
        self.assertEqual(struct.unpack_from("<IHBBHH", body, 16)[0], 2)

    def test_group_list_layout(self):
        member = PartyMember(2, "Friend", zone=230, targid=0x401, hp=50, mp=20, tp=1000,
                             hp_max=100, mp_max=50, main_job=1, main_level=10,
                             sub_job=2, sub_level=5)
        body = packets.group_list(member, 1, PARTY_LEADER, receiver_zone=230, targid=0x400)
        self.assertEqual(len(body), 0x38)
        self.assertEqual(struct.unpack_from("<I", body, 0x00)[0], 2)
        self.assertEqual(struct.unpack_from("<III", body, 0x04), (50, 20, 1000))
        self.assertEqual(struct.unpack_from("<I", body, 0x10)[0], PARTY_LEADER)
        self.assertEqual(struct.unpack_from("<H", body, 0x14)[0], 0x400)
        self.assertEqual(body[0x16], 1)                 # MemberNumber
        self.assertEqual(body[0x19], 50)                # HPP
        self.assertEqual(body[0x1A], 40)                # MPP
        self.assertEqual(struct.unpack_from("<H", body, 0x1C)[0], 0)
        self.assertEqual((body[0x1E], body[0x1F], body[0x20], body[0x21]),
                         (1, 10, 2, 5))
        self.assertEqual(bytes(body[0x24:0x2A]), b"Friend")

    def test_group_list_other_zone_reports_zone_only(self):
        member = PartyMember(2, "Friend", zone=231, targid=0x401, hp=50, mp=20, tp=1000,
                             hp_max=100, mp_max=50)
        body = packets.group_list(member, 1, 0, receiver_zone=230)
        self.assertEqual(struct.unpack_from("<III", body, 0x04), (0, 0, 0))
        self.assertEqual(struct.unpack_from("<H", body, 0x1C)[0], 231)
        self.assertEqual(body[0x19], 0)
        self.assertEqual(body[0x1A], 0)

    def test_group_attr_layout(self):
        member = PartyMember(2, "Friend", zone=230, targid=0x401, hp=50, mp=20, tp=1000,
                             hp_max=100, mp_max=50, main_job=1, main_level=10,
                             sub_job=2, sub_level=5)
        body = packets.group_attr(member)
        self.assertEqual(len(body), 0x24)
        self.assertEqual(struct.unpack_from("<IIIIH", body, 0x00),
                         (2, 50, 20, 1000, 0x401))
        self.assertEqual((body[0x12], body[0x13]), (50, 40))
        self.assertEqual(struct.unpack_from("<H", body, 0x16)[0], 230)
        self.assertEqual((body[0x1C], body[0x1D], body[0x1E], body[0x1F]),
                         (1, 10, 2, 5))

    def test_checkid_layout(self):
        self.assertEqual(packets.group_checkid(0x11223344),
                         struct.pack("<I", 0x11223344))


class PartyFlowTest(unittest.TestCase):
    def setUp(self):
        self.world = make_world()
        self.a = add_session(self.world, 1, "Ally", 0x401)
        self.b = add_session(self.world, 2, "Friend", 0x402)
        self.c = add_session(self.world, 3, "Third", 0x403)
        self.d = add_session(self.world, 4, "Fourth", 0x404)

    def make_party(self, first, second):
        self.assertEqual(self.world.invite(first, second.char["char_id"],
                                           second.targid, 0), "")
        second.queue.clear()
        self.assertEqual(self.world.respond_invite(second, True), "")
        for session in (first, second):
            session.queue.clear()

    def first_of(self, session, kind):
        for message in session.queue:
            if message_type(message) == kind:
                return message
        self.fail("no %03X in the queue: %s" % (kind, message_types(session)))

    def test_invite_prompt_goes_to_the_invitee(self):
        self.assertEqual(self.world.invite(self.a, 2, 0x402, 0), "")
        self.assertEqual(message_types(self.b), [0x0DC])
        body = self.b.queue[0]
        self.assertEqual(struct.unpack_from("<I", body, 4)[0], 1)
        self.assertEqual(struct.unpack_from("<H", body, 8)[0], 0x401)
        self.assertEqual(body[11], 0)
        self.assertEqual(bytes(body[12:17]), b"Ally\x00")

    def test_accept_sends_the_roster_to_both(self):
        self.assertEqual(self.world.invite(self.a, 2, 0x402, 0), "")
        self.b.queue.clear()
        self.assertEqual(self.world.respond_invite(self.b, True), "")
        for session in (self.a, self.b):
            self.assertEqual(message_types(session), [0x0C8, 0x0DD, 0x0DD])
        table = self.first_of(self.a, 0x0C8)
        self.assertEqual(table[4], 0)
        self.assertEqual(struct.unpack_from("<IHBBHH", table, 8),
                         (1, 0x400, PARTY_LEADER, 0, 230, 0))
        self.assertEqual(struct.unpack_from("<IHBBHH", table, 20),
                         (2, 0x402, 0, 0, 230, 0))
        rows = [message for message in self.a.queue if message_type(message) == 0x0DD]
        self.assertEqual(struct.unpack_from("<H", rows[0], 0x18)[0], 0x400)
        self.assertEqual(struct.unpack_from("<H", rows[1], 0x18)[0], 0x402)
        self.assertEqual(rows[1][0x1A], 1)              # MemberNumber

    def test_invite_to_someone_already_party(self):
        self.make_party(self.a, self.b)
        self.assertEqual(self.world.invite(self.a, 2, 0x402, 0),
                         "That player is already in a party.")

    def test_invite_requires_the_leader(self):
        self.make_party(self.a, self.b)
        self.assertEqual(self.world.invite(self.b, 3, 0x403, 0),
                         "Only the party leader can invite.")

    def test_decline_returns_no_roster(self):
        self.assertEqual(self.world.invite(self.a, 2, 0x402, 0), "")
        self.b.queue.clear()
        self.assertEqual(self.world.respond_invite(self.b, False), "")
        self.assertEqual(message_types(self.b), [])
        self.assertIsNone(self.world.party_of(1))
        self.assertIn(0x017, message_types(self.a))  # the decline line for the inviter

    def test_alliance_invite_needs_two_party_leaders(self):
        self.make_party(self.a, self.b)
        # C is solo: an alliance invite is refused.
        self.assertEqual(self.world.invite(self.a, 3, 0x403, PARTY_KIND_ALLIANCE),
                         "That player must be the leader of a party.")
        self.make_party(self.c, self.d)
        self.assertEqual(self.world.invite(self.a, 3, 0x403, PARTY_KIND_ALLIANCE), "")
        self.assertEqual(message_types(self.c), [0x0DC])
        self.c.queue.clear()
        self.assertEqual(self.world.respond_invite(self.c, True), "")
        alliance = self.world.party_of(1).alliance
        self.assertIsNotNone(alliance)
        self.assertEqual([party.number for party in alliance.parties], [0, 1])
        table = self.first_of(self.a, 0x0C8)
        self.assertEqual(table[4], PARTY_KIND_ALLIANCE)
        rows = [struct.unpack_from("<IHBBHH", table, 8 + i * 12) for i in range(4)]
        self.assertEqual([row[0] for row in rows], [1, 2, 3, 4])
        self.assertEqual(rows[0][2], PARTY_LEADER | ALLIANCE_LEADER)
        self.assertEqual(rows[2][2], PARTY_SECOND | PARTY_LEADER)
        self.assertEqual(rows[3][2], PARTY_SECOND)

    def test_zone_change_updates_the_other_rosters(self):
        self.make_party(self.a, self.b)
        self.b.zone = 231
        self.b.char["zone"] = 231
        self.world.party_zone_changed(self.b)
        rows = [message for message in self.a.queue if message_type(message) == 0x0DD]
        self.assertEqual(len(rows), 2)
        self.assertEqual(struct.unpack_from("<H", rows[1], 0x20)[0], 231)  # body 0x1C
        self.assertEqual(struct.unpack_from("<I", rows[1], 8)[0], 0)  # no HP cross-zone

    def test_vitals_change_sends_group_attr(self):
        self.make_party(self.a, self.b)
        self.a.queue.clear()
        self.b.char["hp_current"] = 25
        self.world.next_party_sync = 0.0
        self.world.sync_parties(now=10.0)
        attrs = [message for message in self.a.queue if message_type(message) == 0x0DF]
        self.assertTrue(attrs)
        self.assertEqual(struct.unpack_from("<I", attrs[-1], 4)[0], 2)
        self.assertEqual(struct.unpack_from("<I", attrs[-1], 8)[0], 25)

    def test_leader_leave_promotes_the_next_member(self):
        self.make_party(self.a, self.b)
        self.a.queue.clear()
        self.world.leave_party(self.a)
        self.assertIs(self.world.party_of(1), None)
        self.assertEqual(self.world.party_of(2).leader_id, 2)
        self.assertEqual(message_types(self.a)[0], 0x0C8)
        self.assertEqual(self.first_of(self.a, 0x0C8)[4], 0)
        self.assertEqual(struct.unpack_from("<IHBBHH", self.first_of(self.a, 0x0C8), 8)[0], 0)
        self.assertEqual(message_types(self.b), [0x0C8, 0x0DD])

    def test_kick_removes_the_member_and_resets_them(self):
        self.make_party(self.a, self.b)
        self.b.queue.clear()
        self.assertEqual(self.world.kick_member(self.a, 2, 0), "")
        self.assertIsNone(self.world.party_of(2))
        self.assertEqual(message_types(self.b)[0], 0x0C8)
        self.assertEqual(message_types(self.a), [0x0C8, 0x0DD])

    def test_disband_resets_everyone(self):
        self.make_party(self.a, self.b)
        self.a.queue.clear()
        self.b.queue.clear()
        self.world.disband_party(self.world.party_of(1))
        self.assertIsNone(self.world.party_of(1))
        self.assertIsNone(self.world.party_of(2))
        self.assertEqual(message_types(self.a), [0x0C8, 0x0DD, 0x037, 0x061, 0x0DF])
        self.assertEqual(message_types(self.b), [0x0C8, 0x0DD, 0x037, 0x061, 0x0DF])

    def test_checkid_reports_the_party_id(self):
        self.make_party(self.a, self.b)
        self.a.queue.clear()
        self.a.party_checkid(sub(0x078, bytes(4)))
        check = self.first_of(self.a, 0x0E1)
        self.assertEqual(struct.unpack_from("<I", check, 4)[0], 1)

    def test_checkid_is_silent_while_solo(self):
        # The retail client follows a null group pointer on 0x0E1 id 0 and crashes.
        self.a.queue.clear()
        self.a.party_checkid(sub(0x078, bytes(4)))
        self.assertEqual(self.a.queue, [])


class SubAccountInviteTest(unittest.TestCase):
    """A family sub answers its own invitation; everyone else still gets the prompt."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = support.make_service(Path(self.tmp.name))
        self.world = World(self.config, self.service, None)
        self.owner = self.service.register("owner", "password123").account
        self.main = self.make_session(self.service.create_character(
            self.owner["id"], {"name": "Mainchar", "race": 1}), 0x401)
        self.sub = self.service.create_sub_account(
            self.owner["id"], {"character": {"name": "Boxone", "race": 1}})
        self.box = self.make_session(self.sub["character"], 0x402)
        self.other = self.service.register("other", "password123").account
        self.other_main = self.make_session(self.service.create_character(
            self.other["id"], {"name": "Otherchar", "race": 1}), 0x403)

    def make_session(self, character, targid):
        row = self.service.character(int(character["id"]))
        session = ZoneSession(
            self.world, ("127.0.0.1", 9000 + targid),
            self.service.character_record(row, "Fanxi"))
        session.set_key(bytes(20))
        session.logged_in = True
        session.zone_loaded = True
        session.zone = int(session.char["zone"])
        session.targid = targid
        # The reset path repaints the character's own vitals; joining a party does not
        # call it, but these stubs keep a kick or disband test from needing the stat sheet.
        session.char_status = lambda: sub(0x037, bytes(4))
        session.char_stats = lambda: sub(0x061, bytes(4))
        session.party_member = lambda: sub(0x0DF, bytes(4))
        self.world.sessions[session.addr] = session
        return session

    def test_family_sub_accepts_without_a_prompt(self):
        self.assertEqual(self.world.invite(self.main, self.box.char["char_id"],
                                           self.box.targid, 0), "")
        self.assertIsNotNone(self.world.party_of(int(self.main.char["char_id"])))
        self.assertIsNotNone(self.world.party_of(int(self.box.char["char_id"])))
        self.assertEqual(self.world.pending_invites, {})
        self.assertNotIn(0x0DC, message_types(self.box))
        self.assertEqual(message_types(self.box), [0x0C8, 0x0DD, 0x0DD])
        self.assertEqual(message_types(self.main), [0x0C8, 0x0DD, 0x0DD])

    def test_sibling_sub_accepts_too(self):
        sibling = self.service.create_sub_account(
            self.owner["id"], {"character": {"name": "Boxtwo", "race": 1}})
        second = self.make_session(sibling["character"], 0x404)
        self.assertEqual(self.world.invite(second, self.box.char["char_id"],
                                           self.box.targid, 0), "")
        self.assertIsNotNone(self.world.party_of(int(self.box.char["char_id"])))
        self.assertNotIn(0x0DC, message_types(self.box))

    def test_alliance_invite_to_a_family_sub_is_automatic(self):
        sibling = self.service.create_sub_account(
            self.owner["id"], {"character": {"name": "Boxtwo", "race": 1}})
        second = self.make_session(sibling["character"], 0x404)
        third = self.service.create_sub_account(
            self.owner["id"], {"character": {"name": "Boxthree", "race": 1}})
        third_session = self.make_session(third["character"], 0x405)
        self.assertEqual(self.world.invite(second, third_session.char["char_id"],
                                           third_session.targid, 0), "")
        self.assertEqual(self.world.invite(self.main, self.box.char["char_id"],
                                           self.box.targid, 0), "")
        second.queue.clear()
        self.assertEqual(self.world.invite(
            self.main, second.char["char_id"], second.targid, PARTY_KIND_ALLIANCE), "")
        alliance = self.world.party_of(int(self.main.char["char_id"])).alliance
        self.assertIsNotNone(alliance)
        self.assertEqual(len(alliance.parties), 2)
        self.assertNotIn(0x0DC, message_types(second))

    def test_another_players_sub_still_gets_the_prompt(self):
        other_sub = self.service.create_sub_account(
            self.other["id"], {"character": {"name": "Otherbox", "race": 1}})
        box = self.make_session(other_sub["character"], 0x404)
        self.assertEqual(self.world.invite(self.main, box.char["char_id"],
                                           box.targid, 0), "")
        self.assertEqual(message_types(box), [0x0DC])
        self.assertIn(int(box.char["char_id"]), self.world.pending_invites)
        self.assertIsNone(self.world.party_of(int(self.main.char["char_id"])))

    def test_a_main_account_still_gets_the_prompt(self):
        self.assertEqual(self.world.invite(self.main, self.other_main.char["char_id"],
                                           self.other_main.targid, 0), "")
        self.assertEqual(message_types(self.other_main), [0x0DC])
        self.assertIn(int(self.other_main.char["char_id"]), self.world.pending_invites)
        self.assertIsNone(self.world.party_of(int(self.main.char["char_id"])))

    def test_the_prompt_can_be_required_by_configuration(self):
        self.world.config = replace(self.config, auto_accept_sub_invites=False)
        self.assertEqual(self.world.invite(self.main, self.box.char["char_id"],
                                           self.box.targid, 0), "")
        self.assertEqual(message_types(self.box), [0x0DC])
        self.assertIn(int(self.box.char["char_id"]), self.world.pending_invites)
        self.assertIsNone(self.world.party_of(int(self.main.char["char_id"])))

    def test_invite_command_parties_every_sub(self):
        sibling = self.service.create_sub_account(
            self.owner["id"], {"character": {"name": "Boxtwo", "race": 1}})
        second = self.make_session(sibling["character"], 0x404)
        self.main.command(["invite", "subs"])
        group = self.world.party_of(int(self.main.char["char_id"]))
        self.assertIsNotNone(group)
        self.assertEqual({member.name for member in group.members},
                         {"Mainchar", "Boxone", "Boxtwo"})
        self.assertNotIn(0x0DC, message_types(self.box))
        self.assertNotIn(0x0DC, message_types(second))

    def test_invite_command_takes_one_name(self):
        self.main.command(["invite", "Boxone"])
        self.assertIsNotNone(self.world.party_of(int(self.main.char["char_id"])))
        self.assertIsNotNone(self.world.party_of(int(self.box.char["char_id"])))
        self.assertNotIn(0x0DC, message_types(self.box))

    def test_invite_command_by_name_still_prompts_a_stranger(self):
        self.main.command(["invite", "Otherchar"])
        self.assertEqual(message_types(self.other_main), [0x0DC])
        self.assertIn(int(self.other_main.char["char_id"]), self.world.pending_invites)
        self.assertIsNone(self.world.party_of(int(self.main.char["char_id"])))

    def test_invite_command_needs_the_party_leader(self):
        self.main.command(["invite", "Boxone"])
        self.box.queue.clear()
        self.box.command(["invite", "subs"])
        self.assertIn(0x017, message_types(self.box))
        self.assertEqual(len(self.world.party_of(
            int(self.main.char["char_id"])).members), 2)


class FakeAccounts:
    """The two service calls the family recovery makes."""

    def __init__(self, families, kinds):
        self.families = {int(key): {int(value) for value in values}
                         for key, values in families.items()}
        self.kinds = {int(key): value for key, value in kinds.items()}

    def account_family_ids(self, account_id: int) -> set[int]:
        return set(self.families.get(int(account_id), {int(account_id)}))

    def account(self, account_id: int) -> dict:
        return {"id": int(account_id), "kind": self.kinds.get(int(account_id), "main")}


def chat_text(session) -> str:
    text = b""
    for message in session.queue:
        if message_type(message) == 0x017:
            text += bytes(message)
    return text.decode("ascii", "replace")


def first_message(session, kind: int):
    for message in session.queue:
        if message_type(message) == kind:
            return message
    raise AssertionError("no %03X in the queue: %s" % (kind, message_types(session)))


class FamilyRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.world = make_world()
        self.world.service = FakeAccounts(
            {1: {1, 3, 5, 7}}, {1: "main", 3: "sub", 5: "sub", 7: "sub"})
        self.main = add_session(self.world, 1, "Onedough", 0x401, account_id=1)
        self.sub1 = add_session(self.world, 3, "Twodough", 0x403, account_id=3)
        self.sub2 = add_session(self.world, 5, "Threedough", 0x405, account_id=5)

    def make_sub_party(self):
        group = self.world.create_party(self.sub1)
        self.world.join_party(group, self.sub2)
        group.leader_id = 3
        self.sub1.queue.clear()
        self.sub2.queue.clear()
        return group

    def test_main_rejoins_and_takes_the_lead(self):
        group = self.make_sub_party()
        message = self.world.recover_family_party(self.main)
        self.assertIn("Rejoined", message)
        self.assertIs(self.world.party_of(1), group)
        self.assertIs(self.world.party_of(3), group)
        self.assertEqual(group.leader_id, 1)
        self.assertEqual(message_types(self.main), [0x0C8, 0x0DD, 0x0DD, 0x0DD])
        table = first_message(self.sub1, 0x0C8)
        rows = [struct.unpack_from("<IHBBHH", table, 8 + index * 12) for index in range(3)]
        self.assertEqual([row[0] for row in rows], [3, 5, 1])
        self.assertEqual(rows[2][2], PARTY_LEADER)

    def test_zone_in_recovery_can_leave_the_roster_to_the_login_burst(self):
        group = self.make_sub_party()
        self.main.queue.clear()
        message = self.world.recover_family_party(self.main, exclude_self=True)
        self.assertIn("Rejoined", message)
        self.assertEqual(self.main.queue, [])
        self.assertEqual(message_types(self.sub1), [0x0C8, 0x0DD, 0x0DD, 0x0DD])
        self.assertIs(self.world.party_of(1), group)

    def test_a_party_with_an_outsider_is_not_taken_over(self):
        group = self.make_sub_party()
        friend = add_session(self.world, 9, "Friend", 0x409, account_id=9)
        self.world.join_party(group, friend)
        self.assertEqual(self.world.recover_family_party(self.main), "")
        self.assertIsNone(self.world.party_of(1))
        self.assertEqual(group.leader_id, 3)

    def test_a_sub_login_does_not_take_the_party(self):
        group = self.make_sub_party()
        other_sub = add_session(self.world, 7, "Fourdough", 0x407, account_id=7)
        self.assertEqual(self.world.recover_family_party(other_sub), "")
        self.assertIsNone(self.world.party_of(7))
        self.assertEqual(group.leader_id, 3)

    def test_a_main_already_grouped_is_left_alone(self):
        group = self.world.create_party(self.main)
        self.assertEqual(self.world.recover_family_party(self.main), "")
        self.assertIs(self.world.party_of(1), group)
        self.assertEqual(group.leader_id, 1)

    def test_invite_subs_recovers_the_kept_party(self):
        group = self.make_sub_party()
        self.main.queue.clear()
        self.main.invite_command(["subs"])
        self.assertIn("Rejoined", chat_text(self.main))
        self.assertIs(self.world.party_of(1), group)
        self.assertIs(self.world.party_of(3), group)
        self.assertEqual(group.leader_id, 1)
        self.assertIn(0x0C8, message_types(self.main))
        self.assertIn(0x0C8, message_types(self.sub1))

    def test_invite_subs_still_invites_a_missing_sub(self):
        group = self.make_sub_party()
        # Fourdough is online in the family but not in the kept party.
        add_session(self.world, 7, "Fourdough", 0x407, account_id=7)
        self.main.queue.clear()
        self.main.invite_command(["subs"])
        self.assertIn("Rejoined", chat_text(self.main))
        self.assertIn("Joined party: Fourdough", chat_text(self.main))
        self.assertIs(self.world.party_of(1), group)
        self.assertIsNotNone(self.world.party_of(7))

    def test_makeparty_drops_a_sub_from_another_party(self):
        friend = add_session(self.world, 9, "Friend", 0x409, account_id=9)
        old_party = self.world.create_party(self.sub1)
        self.world.join_party(old_party, friend)
        self.main.queue.clear()
        self.main.command(["makeparty"])
        self.assertIn("Left their old party: Twodough", chat_text(self.main))
        self.assertIn("Joined party:", chat_text(self.main))
        team = self.world.party_of(1)
        self.assertIsNotNone(team)
        self.assertIs(team, self.world.party_of(3))
        self.assertIs(team, self.world.party_of(5))
        self.assertIsNot(self.world.party_of(9), team)
        self.assertEqual(self.world.party_of(9).leader_id, 9)
        self.assertNotIn(0x0DC, message_types(self.sub1))

    def test_makeparty_requires_the_leader(self):
        group = self.world.create_party(self.sub1)
        self.world.join_party(group, self.main)
        self.main.queue.clear()
        self.main.command(["makeparty"])
        self.assertIn("Only the party leader can invite.", chat_text(self.main))
        self.assertIs(self.world.party_of(1), group)
        self.assertIs(self.world.party_of(3), group)
        self.assertIsNone(self.world.party_of(5))


class PartyCommandTest(unittest.TestCase):
    """The C2S side: the sync-0 invite packet has to reach the handler at all."""

    def setUp(self):
        self.world = make_world()
        self.a = add_session(self.world, 1, "Ally", 0x401)
        self.b = add_session(self.world, 2, "Friend", 0x402)
        self.hdr = bytearray(28)
        struct.pack_into("<HH", self.hdr, 0, 1, 0)
        self.a.client_id = 0

    def parse(self, message):
        self.a.parse(self.hdr, bytes(message))

    def test_sync_zero_invite_is_dispatched(self):
        self.parse(sub(0x06E, struct.pack("<IHBx", 2, 0x402, 0)))
        self.assertEqual(message_types(self.b), [0x0DC])

    def test_invite_by_targid_when_character_id_is_zero(self):
        self.parse(sub(0x06E, struct.pack("<IHBx", 0, 0x402, 0)))
        self.assertEqual(message_types(self.b), [0x0DC])

    def test_invite_response_accepts(self):
        self.parse(sub(0x06E, struct.pack("<IHBx", 2, 0x402, 0)))
        self.b.queue.clear()
        self.b.parse(self.hdr, bytes(sub(0x074, bytes([1, 0, 0, 0]))))
        self.assertEqual(message_types(self.b), [0x0C8, 0x0DD, 0x0DD])

    def test_leave_command_resets(self):
        self.parse(sub(0x06E, struct.pack("<IHBx", 2, 0x402, 0)))
        self.b.queue.clear()
        self.b.parse(self.hdr, bytes(sub(0x074, bytes([1, 0, 0, 0]))))
        self.b.queue.clear()
        self.b.parse(self.hdr, bytes(sub(0x06F, bytes([0, 0, 0, 0]))))
        self.assertEqual(message_types(self.b), [0x0C8, 0x0DD, 0x037, 0x061, 0x0DF])


if __name__ == "__main__":
    unittest.main()
