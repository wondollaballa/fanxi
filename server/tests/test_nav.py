"""Collision-aware monster movement: grids, barriers, step rules and A*."""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game.nav import NavCache, NavGrid
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession
from fanxi_server.game.zonemesh import FileTable, iter_blocks, zone_model_file_id


def quad(x0, z0, x1, z1, y):
    """Two triangles for a horizontal rectangle."""
    return [
        (x0, y, z0, x1, y, z0, x1, y, z1),
        (x0, y, z0, x1, y, z1, x0, y, z1),
    ]


def wall_face(x, z0, z1, y0, y1):
    """Two triangles for one vertical rectangle at ``x``."""
    return [
        (x, y0, z0, x, y0, z1, x, y1, z1),
        (x, y0, z0, x, y1, z1, x, y1, z0),
    ]


def flat_grid(zone=1):
    return NavGrid.from_floor_triangles(zone, quad(0, 0, 40, 40, 0))


def dat_block(name, kind, payload):
    """One DAT block: a four-character name, a type/length word, then the body."""
    total = 16 + len(payload)
    padded = total + (-total % 16)
    word = (kind & 0x7F) | ((padded // 16) << 7)
    return (name.encode("ascii").ljust(4, b"\0")[:4] + struct.pack("<I", word)
            + bytes(8) + payload + bytes(padded - total))


class ZoneMeshTest(unittest.TestCase):
    def test_zone_model_ids(self):
        self.assertEqual(zone_model_file_id(101), 201)
        self.assertEqual(zone_model_file_id(300), 83935)

    def test_dat_block_walk(self):
        raw = dat_block("f_ro", 0x1C, b"mesh") + dat_block("end", 0, b"")
        found = list(iter_blocks(raw))
        self.assertEqual(found[0][0], "f_ro")
        self.assertEqual(found[0][1], 0x1C)
        body = bytes(raw[found[0][2]:found[0][2] + found[0][3]])
        self.assertTrue(body.startswith(b"mesh"))
        self.assertEqual(found[1][1], 0)

    def test_file_table_resolves_a_rom_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vtable = bytearray(8)
            vtable[3] = 1
            ftable = bytearray(16)
            struct.pack_into("<H", ftable, 6, (2 << 7) | 35)
            (root / "VTABLE.DAT").write_bytes(bytes(vtable))
            (root / "FTABLE.DAT").write_bytes(bytes(ftable))
            path = FileTable(root).dat_path(3)
        self.assertEqual(path, root / "ROM" / "2" / "35.DAT")

    def test_file_table_finds_the_numbered_rom2_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vtable = bytearray(8)
            vtable[3] = 2  # this file lives in ROM2
            ftable = bytearray(16)
            struct.pack_into("<H", ftable, 6, (1 << 7) | 9)
            (root / "ROM2").mkdir()
            (root / "ROM2" / "VTABLE2.DAT").write_bytes(bytes(vtable))
            (root / "ROM2" / "FTABLE2.DAT").write_bytes(bytes(ftable))
            path = FileTable(root).dat_path(3)
        self.assertEqual(path, root / "ROM2" / "1" / "9.DAT")

    def test_absent_zone_data_builds_no_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = NavCache(Path(tmp), None)
            self.assertIsNone(cache.grid(101))
            self.assertIsNone(cache.current(101))

    def test_a_cached_grid_loads_without_the_game_folder(self):
        grid = flat_grid(101)
        with tempfile.TemporaryDirectory() as tmp:
            cache = NavCache(Path(tmp), None)
            grid.save(cache._cache_path(101))
            loaded = cache.grid(101)
        self.assertIsNotNone(loaded)
        self.assertAlmostEqual(loaded.floor_near(12, 12, 0.0), 0.0, places=3)


class GridTest(unittest.TestCase):
    def test_flat_ground_is_walkable(self):
        grid = flat_grid()
        self.assertIsNotNone(grid)
        self.assertAlmostEqual(grid.floor_near(12, 12, 0.0), 0.0, places=3)
        self.assertIsNone(grid.floor_near(-10, 12, 0.0))

    def test_a_solid_wall_on_flat_ground_blocks_even_though_the_height_is_flat(self):
        """The case a height-step test cannot see: a wall standing on level ground."""
        walls = wall_face(20, 0, 30, 0, 6)
        grid = NavGrid.from_floor_triangles(1, quad(0, 0, 40, 40, 0), walls=walls)
        self.assertIsNone(grid.step_floor(18, 10, 0, 22, 10))
        self.assertFalse(grid.line_clear(18, 0, 10, 22, 0, 10))
        path = grid.find_path((5, 0, 10), (35, 0, 10), max_nodes=8000)
        self.assertIsNotNone(path)
        # The wall runs z=0..30, so the route has to come around one of its ends.
        for x, y, z in path:
            self.assertFalse(19 < x < 21 and 0 < z < 30,
                             "the route crossed the wall at (%.1f, %.1f, %.1f)" % (x, y, z))

    def test_a_cliff_has_no_route_to_its_top(self):
        floors = quad(0, 0, 20, 40, 0) + quad(20, 0, 40, 40, 6)
        # A vertical face between the two levels: the rasteriser would otherwise leave
        # a one-cell seam that a diagonal move could squeeze through.
        walls = wall_face(20, 0, 40, 0, 6)
        grid = NavGrid.from_floor_triangles(1, floors, walls=walls)
        self.assertIsNone(grid.step_floor(18, 20, 0, 22, 20))
        self.assertIsNone(grid.find_path((10, 0, 20), (30, 6, 20), max_nodes=8000))

    def test_flat_triangle_arrays_build_the_same_grid(self):
        from array import array
        flat = array("f")
        for triangle in quad(0, 0, 20, 20, 2.5):
            flat.extend(triangle)
        grid = NavGrid.from_floor_triangles(1, flat, bounds=(0, 20, 2.5, 2.5, 0, 20))
        self.assertIsNotNone(grid)
        self.assertAlmostEqual(grid.floor_near(10, 10, 2.5), 2.5, places=2)

    def test_a_floor_triangle_at_the_cell_edge_is_not_replaced_by_the_cell_centre(self):
        """The wall-top case: one cell, ground at its centre, a ledge at its corner.

        Sampling only the cell centre put ground under the mob and let it step onto the
        ledge; the point query has to see the ledge triangle at the mob's real position.
        """
        floors = (quad(0.4, 0.4, 5, 5, 0.0)
                  + [(0.0, -7.7, 0.0, 0.4, -7.7, 0.0, 0.0, -7.7, 0.4)])
        grid = NavGrid.from_floor_triangles(1, floors)
        self.assertAlmostEqual(grid.floor_near(0.75, 0.75, 0.0), 0.0, places=2)
        self.assertAlmostEqual(grid.floor_at(0.1, 0.1, 0.0), -7.7, places=2)
        self.assertIsNone(grid.floor_near(0.1, 0.1, 0.0, limit=4.0))
        self.assertIsNone(grid.step_floor(0.75, 0.75, 0.0, 0.1, 0.1))

    def test_a_ramp_carries_the_walker_up(self):
        floors = [
            # x=10 is 0, x=30 is 6: a 3/10 grade, which the step rule allows.
            (10, 0, 0, 30, 6, 0, 30, 6, 40),
            (10, 0, 0, 30, 6, 40, 10, 0, 40),
        ]
        grid = NavGrid.from_floor_triangles(1, floors)
        y = grid.step_floor(12, 20, 0.0, 28, 20)
        self.assertIsNotNone(y)
        self.assertAlmostEqual(y, 5.0, delta=0.8)
        path = grid.find_path((12, 0, 20), (28, 5, 20))
        self.assertIsNotNone(path)
        self.assertGreater(path[-1][1], 3.0)

    def test_a_drop_is_not_a_walkable_step(self):
        grid = flat_grid()
        # Stepping off the mesh is not a fall the navigator may take.
        self.assertIsNone(grid.step_floor(38, 10, 0, 42, 10))
        self.assertFalse(grid.line_clear(38, 0, 10, 42, 0, 10))

    def test_layers_keep_a_bridge_and_the_ground_below_apart(self):
        floors = (quad(0, 0, 40, 40, 0)          # ground
                  + quad(8, 0, 32, 40, 8)        # a bridge deck overhead
                  + quad(8, 0, 32, 4, 3)         # its near ramp
                  + quad(8, 36, 32, 40, 3))      # its far ramp
        grid = NavGrid.from_floor_triangles(1, floors)
        index = grid._cell_index(20, 20)
        self.assertGreaterEqual(grid.counts[index], 2)
        # A walker on the ground stays on the ground rather than snapping up to the deck.
        self.assertAlmostEqual(grid.floor_near(20, 20, 0.0), 0.0, places=2)
        self.assertAlmostEqual(grid.floor_near(20, 20, 8.0), 8.0, places=2)
        # The layer picker must choose by height, not by slot order: treating slot 0 as
        # "nearest" is what once made a path start on the ground under a bridge.
        upper = grid._nearest_state(index, 8.0)
        lower = grid._nearest_state(index, 0.0)
        self.assertAlmostEqual(upper[1], 8.0, places=2)
        self.assertAlmostEqual(lower[1], 0.0, places=2)
        path = grid.find_path((20, 8, 20), (20, 8, 30))
        self.assertIsNotNone(path)
        self.assertTrue(all(point[1] > 7.0 for point in path))

    def test_cache_round_trip_keeps_walls(self):
        walls = wall_face(20, 0, 30, 0, 6)
        grid = NavGrid.from_floor_triangles(101, quad(0, 0, 40, 40, 0), walls=walls,
                                            signature=(1234, 5678))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "101.nav"
            grid.save(path)
            loaded = NavGrid.load(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.signature, (1234, 5678))
        self.assertIsNone(loaded.step_floor(18, 10, 0, 22, 10))
        self.assertEqual(len(loaded.walls), len(grid.walls))


class WorldMobNavigationTest(unittest.TestCase):
    """A monster in the live world tick, driven through a synthetic navigator."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.zone(100)

    def zone(self, zone_id):
        self.session.zone = zone_id
        self.session.pos = list(self.world.zones.position(zone_id))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True

    class FakeCache:
        def __init__(self, grid):
            self.grid_obj = grid

        def grid(self, zone):
            return self.grid_obj

    def use_grid(self, grid):
        self.world.nav = self.FakeCache(grid)

    def mob(self):
        return next(entity for entity in self.session.entities
                    if entity.kind == "mob" and entity.alive)

    def place_mob(self, mob, x, z, y=0.0):
        mob.x, mob.y, mob.z = float(x), float(y), float(z)
        mob.spawn_x, mob.spawn_y, mob.spawn_z = float(x), float(y), float(z)
        mob.roam_radius = 0
        mob.aggro = False
        mob.moving = False
        mob.last_move_at = 0.0
        mob.nav_path.clear()
        mob.nav_goal = None
        mob.nav_blocked_until = 0.0

    def engage(self, mob, pos):
        self.session.pos = [float(pos[0]), float(pos[1]), float(pos[2]), 0]
        mob.engaged_char_id = int(self.session.char["char_id"])
        mob.claim_char_id = int(self.session.char["char_id"])
        mob.next_attack_at = time.time() + 100.0
        mob.aggro_announced = True

    def test_a_chasing_mob_goes_around_a_wall_instead_of_through_it(self):
        walls = wall_face(20, 0, 30, 0, 6)
        grid = NavGrid.from_floor_triangles(100, quad(0, 0, 40, 40, 0), walls=walls)
        self.use_grid(grid)
        mob = self.mob()
        self.place_mob(mob, 5, 10)
        self.engage(mob, (35, 0, 10))
        now = time.time()
        mob.last_move_at = now - 0.2
        crossed_badly = False
        northmost = mob.z
        for step in range(80):
            now += 0.2
            mob.last_move_at = max(mob.last_move_at, now - 0.2)
            self.world.advance(now)
            northmost = max(northmost, mob.z)
            if 19.5 < mob.x < 20.5 and 0 < mob.z < 30:
                crossed_badly = True
        self.assertFalse(crossed_badly, "the mob passed through the wall")
        # It found a way around the north end of the wall and is on the far side.
        self.assertGreater(mob.x, 20.0)
        self.assertGreater(northmost, 30.0)

    def test_a_mob_stops_at_a_cliff_instead_of_climbing_it(self):
        floors = quad(0, 0, 20, 40, 0) + quad(20, 0, 40, 40, 8)
        walls = wall_face(20, 0, 40, 0, 8)
        grid = NavGrid.from_floor_triangles(100, floors, walls=walls)
        self.use_grid(grid)
        mob = self.mob()
        self.place_mob(mob, 8, 20)
        self.engage(mob, (32, 8, 20))
        now = time.time()
        mob.last_move_at = now - 0.2
        for step in range(50):
            now += 0.2
            self.world.advance(now)
        # No route exists: the monster must stay on the low side and keep its feet down.
        self.assertLess(mob.x, 20.0)
        self.assertLess(mob.y, 2.0)

    def test_a_roaming_mob_follows_the_slope_and_stays_on_the_mesh(self):
        floors = [
            (0, 0, 0, 20, 0, 0, 20, 0, 40),
            (0, 0, 0, 20, 0, 40, 0, 0, 40),
            (20, 0, 0, 40, 4, 0, 40, 4, 40),
            (20, 0, 0, 40, 4, 40, 20, 0, 40),
        ]
        walls = wall_face(20, 0, 40, 0, 4)
        grid = NavGrid.from_floor_triangles(100, floors, walls=walls)
        self.use_grid(grid)
        mob = self.mob()
        self.place_mob(mob, 12, 20)
        mob.roam_radius = 12.0
        mob.roam_pause_until = 0.0
        self.session.pos = [12.0, 0.0, 20.0, 0]
        now = time.time()
        start_index = grid._cell_index(mob.x, mob.z)
        for step in range(40):
            now += 0.25
            self.world.advance(now)
            floor = grid.floor_near(mob.x, mob.z, mob.y, limit=3.0)
            self.assertIsNotNone(floor)
            self.assertAlmostEqual(mob.y, floor, delta=0.2)
            self.assertLessEqual(mob.y, 1.0)
            self.assertGreaterEqual(mob.x, 0.0)
            self.assertLessEqual(mob.x, 40.0)
        self.assertGreaterEqual(mob.x, 0.0)
        self.assertTrue(start_index >= 0)

    def test_a_mob_cannot_swing_through_a_wall(self):
        walls = wall_face(20, 0, 40, 0, 6)
        grid = NavGrid.from_floor_triangles(100, quad(0, 0, 40, 40, 0), walls=walls)
        self.use_grid(grid)
        mob = self.mob()
        self.place_mob(mob, 19.0, 20.0)
        self.engage(mob, (21.5, 0.0, 20.0))
        mob.next_attack_at = 0.0
        self.session.queue.clear()
        now = time.time()
        for step in range(8):
            now += 0.2
            mob.last_move_at = now - 0.2
            self.world.advance(now)
        types = [struct.unpack_from("<H", message, 0)[0] & 0x1FF
                 for message in self.session.queue]
        self.assertNotIn(0x028, types)
        self.assertLess(mob.x, 20.0)

    def test_aggro_does_not_reach_a_player_on_the_far_side_of_a_wall(self):
        walls = wall_face(20, 0, 40, 0, 6)
        grid = NavGrid.from_floor_triangles(100, quad(0, 0, 40, 40, 0), walls=walls)
        self.use_grid(grid)
        mob = self.mob()
        self.place_mob(mob, 16, 10)
        mob.aggro = True
        self.session.pos = [23.0, 0.0, 10.0, 0]
        self.session.char["main_level"] = 1
        now = time.time()
        for step in range(5):
            now += 0.2
            mob.last_move_at = now - 0.2
            self.world.advance(now)
        self.assertIsNone(mob.engaged_char_id)


if __name__ == "__main__":
    unittest.main()
