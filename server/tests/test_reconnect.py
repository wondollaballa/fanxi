"""A dropped link is a relog to the client: the server must hold what it was carrying.

Retail keeps a character's status effects and job-ability cooldowns on the server, so a
client that loses its connection and signs back in finds the same song list ticking and
the same abilities still recharging; only a deliberate logout takes the buffs with it.
Fanxi builds a fresh ``ZoneSession`` for every fresh login, so the session writes a
snapshot (``char_live_state``, migration 0144) and the next login restores it.

These tests drive the real write path (a login that replaces the ghost session), the real
read path (``on_login``) and the packets the client draws the restored state from.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import effects, live_state
from fanxi_server.game import modifiers as mod
from fanxi_server.game.world import World
from fanxi_server.game.zone import (
    LIVE_STATE_NOTICE_DELAY,
    LIVE_STATE_SAVE_INTERVAL,
    STATUS_ICON_NO_TIMER,
    VANA_EPOCH,
    ZoneSession,
)

SONG = "Valor Minuet V"
SONG_ID = 100


def chats(session) -> list[str]:
    return [bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace")
            for message in session.queue
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x017]


def status_icons(session) -> list[tuple[int, int]]:
    """The (icon, timer) pairs of the 0x063 timer packet, slot for slot."""
    body = bytes(session.status_icons()[4:])
    icons = struct.unpack_from("<32H", body, 4)
    timers = struct.unpack_from("<32I", body, 68)
    return list(zip(icons, timers))


def recast_rows(session) -> dict[int, int]:
    """recast id -> seconds left, from the 0x119 the client's ability menu reads."""
    body = bytes(session.abil_recast()[4:])
    rows: dict[int, int] = {}
    for slot in range(31):
        timer, _calc1, recast_id, _calc2, _pad = struct.unpack_from("<HBBHH", body, slot * 8)
        if recast_id:
            rows[int(recast_id)] = int(timer)
    return rows


def status_icon(session, slot: int) -> int:
    """The full status id in a 0x037 slot (low byte plus its two high bits), or -1."""
    status = session.char_status()
    if status[4 + slot] == 0xFF:
        return -1
    high = (status[4 + 0x48 + slot // 4] >> (2 * (slot % 4))) & 3
    return status[4 + slot] | (high << 8)


class SnapshotTest(unittest.TestCase):
    """game/live_state.py on its own: the payload shape and the expiry rules."""

    def setUp(self):
        self.now = time.time()

    def state(self, **overrides) -> dict:
        state = {
            "until": self.now + 120.0, "power": 0, "potency": 0, "tick": 0,
            "icon": 198, "mods": {7: 124}, "next_tick": self.now + 3.0,
        }
        state.update(overrides)
        return state

    def song(self, name: str = SONG, spell_id: int = SONG_ID, **overrides) -> tuple[int, dict]:
        state = self.state(
            song=True, song_base=120.0, song_name=name, song_cast_at=self.now,
            song_effect=198, mods={7: 124, 452: 4}, **overrides)
        return effects.song_key(spell_id), state

    def test_a_song_survives_the_round_trip(self):
        key, state = self.song()
        payload = live_state.snapshot({key: state}, [key], None, {}, self.now)
        restored = live_state.restore(payload, self.now)
        self.assertEqual(restored.status_effects, [key])
        self.assertEqual(restored.song_count, 1)
        self.assertEqual(restored.effect_count, 1)
        self.assertEqual(restored.effect_state[key]["song_name"], SONG)
        self.assertEqual(restored.effect_state[key]["song_base"], 120.0)
        self.assertEqual(restored.effect_state[key]["mods"], {7: 124, 452: 4})
        self.assertAlmostEqual(restored.effect_state[key]["until"], state["until"])

    def test_roll_metadata_round_trips(self):
        """A restored roll keeps its Double-Up window and its caster."""
        state = self.state(rolled_at=self.now, double_up_until=self.now + 45.0,
                           roll_owner=17)
        payload = live_state.snapshot({310: state}, [310], None, {}, self.now)
        restored = live_state.restore(payload, self.now)
        saved = restored.effect_state[310]
        self.assertAlmostEqual(saved["rolled_at"], self.now)
        self.assertAlmostEqual(saved["double_up_until"], self.now + 45.0)
        self.assertEqual(saved["roll_owner"], 17)

    def test_the_icon_order_is_the_saved_order(self):
        first, first_state = self.song("Victory March", 101)
        second, second_state = self.song("Advancing March", 102)
        third = effects.HASTE
        payload = live_state.snapshot(
            {first: first_state, second: second_state, third: self.state(icon=33)},
            [third, second, first], None, {}, self.now)
        restored = live_state.restore(payload, self.now)
        # The client pairs the 0x063 slots with the 0x037 list, so the order is the bar.
        self.assertEqual(restored.status_effects, [third, second, first])

    def test_effects_and_recasts_that_expired_offline_are_not_restored(self):
        key, state = self.song()
        payload = live_state.snapshot({key: state}, [key], None, {}, self.now)
        self.assertEqual(live_state.restore(payload, self.now + 60.0).effect_count, 1)
        self.assertEqual(live_state.restore(payload, self.now + 121.0).effect_count, 0)
        # A save that lands after the expiry does not put a dead timer in the row.
        late = live_state.snapshot({key: state}, [key], None, {}, self.now + 121.0)
        self.assertEqual(late["effects"], [])
        # A cooldown that ran out while the client was away has nothing left to send.
        payload = live_state.snapshot({}, [], None, {103: self.now + 90.0}, self.now)
        self.assertEqual(live_state.restore(payload, self.now + 91.0).recasts, {})

    def test_a_saved_cooldown_round_trips(self):
        payload = live_state.snapshot({}, [], None, {103: self.now + 90.0}, self.now)
        self.assertEqual(live_state.restore(payload, self.now).recasts,
                         {103: self.now + 90.0})

    def test_a_trust_aura_is_not_held(self):
        key = effects.TRUST_AURA_HASTE
        state = self.state(icon=580, trust_source=0x1234, trust_name="Cornelia")
        payload = live_state.snapshot({key: state}, [key], None, {}, self.now)
        self.assertEqual(payload["effects"], [])
        self.assertEqual(live_state.restore(payload, self.now).effect_count, 0)

    def test_food_and_its_icon_stay_together(self):
        food = {"item_id": 4413, "name": "Apple Pie", "until": self.now + 600.0,
                "mods": {5: 25, 12: 3}}
        # The icon is part of the effect list, so a normal save has both.
        payload = live_state.snapshot(
            {effects.FOOD: self.state(icon=effects.FOOD)}, [effects.FOOD], food, {}, self.now)
        restored = live_state.restore(payload, self.now)
        self.assertIn(effects.FOOD, restored.effect_state)
        self.assertEqual(restored.food["name"], "Apple Pie")
        self.assertEqual(restored.food["mods"], {5: 25, 12: 3})
        # A row where the modifiers outlived the icon (an older build) gets the icon back.
        payload = live_state.snapshot({}, [], food, {}, self.now)
        restored = live_state.restore(payload, self.now)
        self.assertIn(effects.FOOD, restored.effect_state)
        # And an icon with no modifiers behind it goes away: the bar must not lie.
        payload = live_state.snapshot(
            {effects.FOOD: self.state()}, [effects.FOOD], None, {}, self.now)
        self.assertNotIn(effects.FOOD, live_state.restore(payload, self.now).effect_state)

    def test_the_next_tick_restarts_at_login(self):
        key, state = self.song()
        payload = live_state.snapshot({key: state}, [key], None, {}, self.now)
        restored = live_state.restore(payload, self.now + 10.0)
        self.assertGreaterEqual(restored.effect_state[key]["next_tick"], self.now + 10.0)

    def test_the_signature_changes_only_when_the_state_does(self):
        key, state = self.song()
        one = live_state.snapshot({key: state}, [key], None, {}, self.now)
        two = live_state.snapshot({key: dict(state)}, [key], None, {}, self.now)
        self.assertEqual(live_state.signature(one), live_state.signature(two))
        state["power"] = 3
        three = live_state.snapshot({key: state}, [key], None, {}, self.now)
        self.assertNotEqual(live_state.signature(one), live_state.signature(three))

    def test_a_malformed_entry_is_skipped_not_fatal(self):
        key, state = self.song()
        payload = live_state.snapshot({key: state}, [key], None, {}, self.now)
        payload["effects"].insert(0, {"id": "not-a-number"})
        payload["effects"].insert(0, "junk")
        restored = live_state.restore(payload, self.now)
        self.assertEqual(restored.status_effects, [key])


class ReconnectTest(unittest.TestCase):
    """The whole trip: a live session's state, a dropped link, and the next login."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            self.account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = self.login("127.0.0.1", 5001)

    def record(self) -> dict:
        return self.service.character_record(
            self.service.character(self.character["id"]), "Fanxi")

    def login(self, host: str, port: int, *, restore: bool = True) -> ZoneSession:
        """A session on a fresh login, as 0x00A builds one."""
        session = ZoneSession(self.world, (host, port), self.record())
        session.set_key(bytes(20))
        session.char["char_id"] = int(session.char["char_id"])
        session.targid = self.world.assign_player_targid(int(session.char["char_id"]))
        session.zone = 246
        session.pos = list(self.world.zones.position(246))
        session.load_zone_entities()
        session.fresh_login = True
        if restore:
            session.on_login()
            session.after_zone_in()
        session.queue.clear()
        self.world.sessions[(host, port)] = session
        return session

    def add_song(self, session, name: str = SONG, spell_id: int = SONG_ID,
                 duration: float = 120.0, mods: dict | None = None) -> int:
        key = effects.song_key(spell_id)
        session.add_effect(
            key, duration=duration, icon=198, mods=mods or {7: 124, 452: 4},
            song_base=120.0, song_name=name, song_cast_at=time.time(),
            song_effect=198)
        return key

    def stored(self) -> dict:
        row = self.service.live_state(int(self.character["id"]))
        self.assertIsNotNone(row)
        return row

    def reconnect(self, port: int = 5002) -> ZoneSession:
        """Drop the old session and log in again through World.take_login."""
        record = self.record()
        session, continuing = self.world.take_login(
            ("127.0.0.1", port), record, int(record["char_id"]))
        self.assertFalse(continuing)
        session.set_key(bytes(20))
        session.fresh_login = True
        session.zone = 246
        session.pos = list(self.world.zones.position(246))
        session.load_zone_entities()
        session.on_login()
        session.after_zone_in()
        return session

    # --- the user-visible behaviour ---------------------------------------------------------

    def test_the_song_list_survives_a_dropped_link(self):
        self.add_song(self.session, "Victory March", 101, 150.0)
        self.add_song(self.session)
        self.add_song(self.session, "Advancing March", 102, 130.0)
        # The tick would have written this; do it explicitly so the test does not depend
        # on the five-second cadence.
        self.assertTrue(self.session.save_live_state())
        back = self.reconnect()
        names = [state["song_name"] for state in back.effect_state.values()
                 if state.get("song")]
        self.assertEqual(sorted(names), ["Advancing March", SONG, "Victory March"])
        self.assertEqual(back.live_state_restored, True)

    def test_the_restored_song_still_feeds_the_stat_sheet(self):
        """The point of holding the song list: the values it was giving must apply."""
        key = self.add_song(self.session, mods={mod.ATT: 124, mod.ACC: 30})
        self.session.save_live_state()
        back = self.reconnect()
        song = back.effect_state[key]
        self.assertTrue(song.get("song"))
        self.assertEqual(song["mods"], {mod.ATT: 124, mod.ACC: 30})
        with_song = back.combat_mods()
        back.remove_effect(key, quiet=True)
        without_song = back.combat_mods()
        self.assertEqual(with_song.get(mod.ATT, 0) - without_song.get(mod.ATT, 0), 124)
        self.assertEqual(with_song.get(mod.ACC, 0) - without_song.get(mod.ACC, 0), 30)

    def test_the_icons_come_back_in_the_order_the_client_drew_them(self):
        first = self.add_song(self.session, "Victory March", 101)
        self.session.add_effect(effects.HASTE, duration=120.0, icon=33)
        second = self.add_song(self.session)
        self.session.save_live_state()
        back = self.reconnect()
        self.assertEqual(back.status_effects, [first, effects.HASTE, second])
        self.assertEqual(status_icon(back, 0), 198)
        self.assertEqual(status_icon(back, 1), 33)

    def test_the_status_timers_are_the_remaining_time(self):
        self.add_song(self.session, duration=120.0)
        self.session.save_live_state()
        back = self.reconnect()
        icons = status_icons(back)
        icon, timer = icons[0]
        self.assertEqual(icon, 198)
        self.assertNotEqual(timer, STATUS_ICON_NO_TIMER)
        vana = int(time.time()) - VANA_EPOCH + int(self.world.clock)
        self.assertAlmostEqual(timer, ((vana + 120) * 60) & 0xFFFFFFFF, delta=180)

    def test_ability_recasts_come_back_on_the_timer_packet(self):
        ready_at = time.time() + 90.0
        self.session.ability_recasts[103] = ready_at
        self.session.save_live_state()
        back = self.reconnect()
        rows = recast_rows(back)
        self.assertIn(103, rows)
        self.assertAlmostEqual(rows[103], 90, delta=3)

    def test_bestial_loyalty_recast_is_in_the_zone_in_burst(self):
        """The HUD polls this table, so a relog must have it before it draws the tiles.

        Bestial Loyalty is recast id 94 with a 20-minute timer.  The zone-in burst now
        carries 0x119 itself; a client that has not sent its 0x061 stats request yet still
        has the server's remaining time.
        """
        ready_at = time.time() + 1100.0
        self.session.ability_recasts[94] = ready_at
        self.session.save_live_state()
        back = self.reconnect()
        rows = recast_rows(back)
        self.assertIn(94, rows)
        self.assertAlmostEqual(rows[94], 1100, delta=3)
        types = [struct.unpack_from("<H", message, 0)[0] & 0x1FF for message in back.queue]
        self.assertIn(0x119, types)
        self.assertLess(types.index(0x119), types.index(0x061))

    def test_food_survives_with_its_modifiers(self):
        item = self.service.item(4413)     # Apple Pie
        food = self.service.food_effect(4413)
        self.session.apply_food(4413, food)
        self.session.save_live_state()
        back = self.reconnect()
        self.assertEqual(back.food["item_id"], 4413)
        self.assertEqual(back.food["name"], item["name"])
        self.assertEqual(back.food["mods"], {5: 25, 11: -1, 12: 3})
        self.assertIn(effects.FOOD, back.status_effects)

    def test_a_buff_that_ran_out_offline_stays_gone(self):
        self.add_song(self.session, duration=1.0)
        self.session.effect_state[effects.song_key(SONG_ID)]["until"] = time.time() - 5.0
        self.session.save_live_state()
        back = self.reconnect()
        self.assertNotIn(effects.song_key(SONG_ID), back.effect_state)
        self.assertIsNone(back.live_state_notice)

    # --- the notice -------------------------------------------------------------------------

    def test_the_notice_waits_for_the_zone_in_and_names_what_came_back(self):
        self.add_song(self.session, duration=180.0)
        self.session.ability_recasts[103] = time.time() + 90.0
        self.session.save_live_state()
        back = self.reconnect()
        self.assertEqual(chats(back), [])       # never inside the zone-in burst
        back.tick(time.time() + LIVE_STATE_NOTICE_DELAY + 0.5)
        lines = chats(back)
        self.assertTrue(lines)
        self.assertIn("Welcome back", lines[0])
        self.assertIn("1 song(s)", lines[0])
        self.assertIn("1 ability recast(s)", lines[0])
        self.assertIn(SONG, lines[1])

    def test_a_recovers_only_login_still_reports_the_cooldowns(self):
        self.session.ability_recasts[103] = time.time() + 90.0
        self.session.save_live_state()
        back = self.reconnect()
        back.tick(time.time() + LIVE_STATE_NOTICE_DELAY + 0.5)
        self.assertIn("1 ability recast(s)", chats(back)[0])

    # --- the two logins that must not keep the buffs ----------------------------------------

    def test_a_deliberate_logout_keeps_the_recasts_but_not_the_buffs(self):
        self.add_song(self.session)
        self.session.ability_recasts[103] = time.time() + 90.0
        self.session.handle(0x0E7, bytes(16))       # /logout
        row = self.stored()
        self.assertEqual(row["effects"], [])
        self.assertIn("103", row["recasts"])
        # Nothing on the dead session may put the buffs back later.
        self.session.save_live_state()
        self.assertEqual(self.stored()["effects"], [])
        back = self.reconnect()
        self.assertEqual(len(back.status_effects), 0)
        self.assertIn(103, back.ability_recasts)

    def test_a_moghouse_login_keeps_the_recasts_only(self):
        self.add_song(self.session)
        self.session.ability_recasts[103] = time.time() + 90.0
        self.session.save_live_state()
        record = self.record()
        record["moghouse"] = 1
        session, _continuing = self.world.take_login(
            ("127.0.0.1", 5003), record, int(record["char_id"]))
        session.set_key(bytes(20))
        session.fresh_login = True
        session.zone = 246
        session.pos = [0.0, 0.0, 0.0, 192]
        session.load_zone_entities()
        session.on_login()
        self.assertEqual(len(session.status_effects), 0)
        self.assertIn(103, session.ability_recasts)

    def test_a_dead_login_keeps_the_recasts_only(self):
        self.add_song(self.session)
        self.session.ability_recasts[103] = time.time() + 90.0
        self.session.save_live_state()
        record = self.record()
        record["hp_current"] = 0
        session, _continuing = self.world.take_login(
            ("127.0.0.1", 5004), record, int(record["char_id"]))
        session.set_key(bytes(20))
        session.fresh_login = True
        session.zone = 246
        session.pos = list(self.world.zones.position(246))
        session.load_zone_entities()
        session.on_login()
        self.assertEqual(len(session.status_effects), 0)
        self.assertIn(103, session.ability_recasts)

    # --- the write path and the zone change -------------------------------------------------

    def test_reaping_a_silent_client_saves_the_state(self):
        self.add_song(self.session, duration=300.0)
        self.world.evict_session(self.session, save=True, reason="timed out")
        row = self.stored()
        self.assertTrue(row["effects"])
        self.assertEqual(row["effects"][0]["song_name"], SONG)

    def test_the_tick_writes_the_state_and_only_when_it_changed(self):
        self.add_song(self.session)
        self.assertIsNone(self.session.live_state_signature)
        now = time.time()
        self.session.tick(now)
        first = self.session.live_state_signature
        self.assertIsNotNone(first)
        self.db.execute("DELETE FROM char_live_state")
        # A second tick inside the interval leaves the row alone...
        self.session.tick(now + LIVE_STATE_SAVE_INTERVAL / 2)
        self.assertIsNone(self.service.live_state(int(self.character["id"])))
        # ...and one after it sees the payload unchanged and writes nothing.
        self.session.tick(now + LIVE_STATE_SAVE_INTERVAL + 0.1)
        self.assertIsNone(self.service.live_state(int(self.character["id"])))
        # A changed payload is written.
        self.session.add_effect(effects.HASTE, duration=60.0)
        self.session.tick(now + LIVE_STATE_SAVE_INTERVAL * 2 + 0.2)
        self.assertIsNotNone(self.service.live_state(int(self.character["id"])))

    def test_a_zone_change_keeps_the_live_state(self):
        self.add_song(self.session, duration=300.0)
        self.session.save_live_state()
        # The same session object continues through the zone change (World.take_login
        # keeps it), so the live timers are the truth, not the row.
        self.session.remove_effect(effects.song_key(SONG_ID), quiet=True)
        self.session.fresh_login = False
        self.session.on_login()
        self.assertNotIn(effects.song_key(SONG_ID), self.session.effect_state)

    def test_a_retried_zone_in_restores_only_once(self):
        self.add_song(self.session, duration=300.0)
        self.session.save_live_state()
        back = self.reconnect()
        self.assertTrue(back.live_state_restored)
        back.remove_effect(effects.song_key(SONG_ID), quiet=True)
        # The client retried 0x00A before its 0x00C: on_login runs again on the same object.
        back.fresh_login = True
        back.on_login()
        self.assertNotIn(effects.song_key(SONG_ID), back.effect_state)


if __name__ == "__main__":
    unittest.main()
