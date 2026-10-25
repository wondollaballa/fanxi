"""Walking surfaces and pathfinding for zone entities.

A monster is not a free-flying actor: it stands on the zone's floor, it may only move to
a neighbouring cell whose floor it can step up to, and it may not cross a cliff edge or a
wall.  This module turns a zone's collision triangles into a small grid of floor heights,
answers "what is the ground here", and plans routes across it with A*.

The grid is deliberately separate from the visible mesh.  One cell holds up to four floor
layers, so a bridge over a canyon (or a tunnel under a rampart) can keep both surfaces and
a walker on one layer never silently jumps to the other.  A missing grid is not fatal: the
zone behaviour falls back to its older straight-line movement.
"""
from __future__ import annotations

import heapq
import logging
import math
import os
import struct
import sys
import threading
import time
import zlib
from array import array
from collections import OrderedDict
from pathlib import Path

from .zonemesh import FloorGeometry, parse_zone_geometry

log = logging.getLogger("fanxi.nav")

NAV_VERSION = 3
NAV_MAGIC = b"FXNAV3\0\0"
# 1.5 yalms: small enough to keep gateways and wall corners, large enough that a zone is
# a few hundred thousand cells rather than millions.
NAV_CELL = 1.5
# Four surfaces per cell covers the real overlaps in the world (a bridge deck, the ground
# under it, and the pair of approach ramps).
NAV_MAX_LAYERS = 4
NAV_HEIGHT_SCALE = 16.0  # cache stores heights as signed 1/16-yalm units
NAV_HEIGHT_LIMIT = 32000  # the int16 cache slot; zones are far inside this

# Steps.  A walker may rise/fall this much over a horizontal distance.  The bias lets a
# mob clear a kerb or a low rock that the rasteriser split across two cells; the grade
# stops it walking up a cliff face.  0.35 + 0.9 * 1.5 = 1.7 yalms per cardinal cell.
NAV_STEP_BIAS = 0.35
NAV_MAX_GRADE = 0.9
# A walker is not a point: its body has to clear a fence rail or a low overhang.  The
# barrier test therefore looks from the floor up to this height, not just at the feet.
NAV_BODY_HEIGHT = 1.5
NAV_WALL_BOTTOM_SLACK = 0.35

# Pathing limits.  Chase routes are short and only replanned a few times a second; a
# return-home route can be longer, so the world passes a larger budget for it.
NAV_DEFAULT_NODES = 18000
NAV_GOAL_SNAP_CELLS = 3
# Paths do not have to be the shortest possible route; a little greed makes A* explore
# far fewer cells in a cave full of pillars, which is what keeps a chase tick cheap.
NAV_HEURISTIC_WEIGHT = 1.6


class NavGrid:
    """A dense grid of floor layers with step-aware neighbours and A*."""

    def __init__(self, zone: int, cell: float, origin_x: float, origin_z: float,
                 width: int, height: int, counts: bytearray, heights: array,
                 walls=None, signature: tuple[int, int] = (0, 0),
                 max_layers: int = NAV_MAX_LAYERS, floors=None):
        self.zone = int(zone)
        self.cell = float(cell)
        self.origin_x = float(origin_x)
        self.origin_z = float(origin_z)
        self.width = int(width)
        self.height = int(height)
        self.counts = counts
        self.heights = heights
        self.walls = walls if isinstance(walls, array) else array("f", walls or ())
        self.floors = floors if isinstance(floors, array) else array("f", floors or ())
        self.signature = tuple(signature)
        self.max_layers = int(max_layers)
        self.wall_bins: dict[int, list[int]] = {}
        self.floor_bins: dict[int, list[int]] = {}
        self._index_walls()
        self._index_floors()

    def _index_walls(self) -> None:
        """Put every barrier triangle in the cell bins its footprint touches.

        The bins keep A* and the step validator from asking the whole 100k-triangle
        wall set about a half-yalm move.
        """
        for triangle in range(len(self.walls) // 9):
            base = triangle * 9
            values = self.walls[base:base + 9]
            if len(values) != 9:
                continue
            xs = (values[0], values[3], values[6])
            zs = (values[2], values[5], values[8])
            i0 = max(0, int((min(xs) - self.origin_x) // self.cell))
            i1 = min(self.width - 1, int((max(xs) - self.origin_x) // self.cell))
            j0 = max(0, int((min(zs) - self.origin_z) // self.cell))
            j1 = min(self.height - 1, int((max(zs) - self.origin_z) // self.cell))
            if i1 < i0 or j1 < j0:
                continue
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    self.wall_bins.setdefault(j * self.width + i, []).append(triangle)

    def _index_floors(self) -> None:
        """Bin floor triangles by the cells their footprint touches."""
        for triangle in range(len(self.floors) // 9):
            base = triangle * 9
            values = self.floors[base:base + 9]
            if len(values) != 9:
                continue
            xs = (values[0], values[3], values[6])
            zs = (values[2], values[5], values[8])
            i0 = max(0, int((min(xs) - self.origin_x) // self.cell))
            i1 = min(self.width - 1, int((max(xs) - self.origin_x) // self.cell))
            j0 = max(0, int((min(zs) - self.origin_z) // self.cell))
            j1 = min(self.height - 1, int((max(zs) - self.origin_z) // self.cell))
            if i1 < i0 or j1 < j0:
                continue
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    self.floor_bins.setdefault(j * self.width + i, []).append(triangle)

    # --- construction -------------------------------------------------------------------------
    @classmethod
    def from_floor_triangles(cls, zone: int, triangles, bounds=None,
                             cell: float = NAV_CELL, signature=(0, 0),
                             walls=()) -> "NavGrid | None":
        """Rasterise floor triangles into the grid.

        ``triangles`` is an iterable of nine-tuples
        ``(ax, ay, az, bx, by, bz, cx, cy, cz)`` in zone coordinates.  ``bounds`` is
        ``(min_x, max_x, min_y, max_y, min_z, max_z)``; it is computed when omitted.
        ``walls`` is the same shape for non-floor triangles: those are barriers, and
        they are tested when a walker crosses their footprint.
        """
        if not isinstance(triangles, (array, list, tuple)):
            # The source is read twice (bounds, then rasterisation); a one-shot
            # iterator has to be materialised first.
            triangles = list(triangles)

        def source():
            # The parser hands over a flat array; unpack it lazily so a zone with a
            # million triangles does not first become a million Python tuples.
            if isinstance(triangles, array):
                return struct.iter_unpack("<9f", triangles)
            return triangles

        if bounds is None:
            min_x = min_y = min_z = math.inf
            max_x = max_y = max_z = -math.inf
            found = False
            for values in source():
                if len(values) != 9 or not all(math.isfinite(value) for value in values):
                    continue
                found = True
                xs = values[0::3]
                ys = values[1::3]
                zs = values[2::3]
                min_x = min(min_x, *xs)
                max_x = max(max_x, *xs)
                min_y = min(min_y, *ys)
                max_y = max(max_y, *ys)
                min_z = min(min_z, *zs)
                max_z = max(max_z, *zs)
            if not found:
                return None
        else:
            min_x, max_x, min_y, max_y, min_z, max_z = (float(value) for value in bounds)
        origin_x = math.floor(min_x / cell) * cell - cell
        origin_z = math.floor(min_z / cell) * cell - cell
        width = max(1, int(math.ceil((max_x - origin_x) / cell)) + 2)
        height = max(1, int(math.ceil((max_z - origin_z) / cell)) + 2)
        cells: list[list[float] | None] = [None] * (width * height)

        found = False
        floor_array = array("f")
        for values in source():
            if len(values) != 9 or not all(math.isfinite(value) for value in values):
                continue
            found = True
            ax, ay, az, bx, by, bz, cx, cy, cz = (float(value) for value in values)
            floor_array.extend((ax, ay, az, bx, by, bz, cx, cy, cz))
            i0 = max(0, int((min(ax, bx, cx) - origin_x) // cell))
            i1 = min(width - 1, int((max(ax, bx, cx) - origin_x) // cell))
            j0 = max(0, int((min(az, bz, cz) - origin_z) // cell))
            j1 = min(height - 1, int((max(az, bz, cz) - origin_z) // cell))
            if i1 < i0 or j1 < j0:
                continue
            den = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
            if abs(den) < 1e-9:
                continue
            for j in range(j0, j1 + 1):
                pz = origin_z + (j + 0.5) * cell
                for i in range(i0, i1 + 1):
                    px = origin_x + (i + 0.5) * cell
                    l1 = ((bz - cz) * (px - cx) + (cx - bx) * (pz - cz)) / den
                    l2 = ((cz - az) * (px - cx) + (ax - cx) * (pz - cz)) / den
                    l3 = 1.0 - l1 - l2
                    if l1 < -1e-6 or l2 < -1e-6 or l3 < -1e-6:
                        continue
                    floor = l1 * ay + l2 * by + l3 * cy
                    if abs(floor) > NAV_HEIGHT_LIMIT:
                        continue
                    index = j * width + i
                    layers = cells[index]
                    if layers is None:
                        cells[index] = [floor]
                        continue
                    for slot, old in enumerate(layers):
                        if abs(old - floor) < 0.6:
                            # Keep the higher surface: overlapping floor triangles are
                            # usually a seam, and a slightly higher one is the ground the
                            # player is actually standing on.
                            if floor > old:
                                layers[slot] = floor
                            break
                    else:
                        if len(layers) < NAV_MAX_LAYERS:
                            layers.append(floor)
                        else:
                            # Too many surfaces: keep the four most distinct by replacing
                            # the one nearest to an existing duplicate.
                            layers.sort()
                            layers[-1] = max(layers[-1], floor)
        if not found:
            return None

        counts = bytearray(width * height)
        heights = array("h", bytes(width * height * NAV_MAX_LAYERS * 2))
        for index, layers in enumerate(cells):
            if not layers:
                continue
            layers.sort()
            # Drop layers that became closer than the deduplication threshold after the
            # cap above; a walker never needs two floors 0.2 yalms apart.
            kept: list[float] = []
            for floor in layers:
                if kept and abs(floor - kept[-1]) < 0.6:
                    kept[-1] = floor
                else:
                    kept.append(floor)
            keep = min(NAV_MAX_LAYERS, len(kept))
            counts[index] = keep
            base = index * NAV_MAX_LAYERS
            for slot in range(keep):
                heights[base + slot] = int(round(kept[slot] * NAV_HEIGHT_SCALE))
        wall_source = (struct.iter_unpack("<9f", walls)
                       if isinstance(walls, array) else walls)
        wall_array = array("f")
        for t in wall_source:
            values = tuple(float(value) for value in t)
            if len(values) != 9 or not all(math.isfinite(value) for value in values):
                continue
            wall_array.extend(values)
        return cls(int(zone), cell, origin_x, origin_z, width, height,
                   counts, heights, walls=wall_array, signature=signature,
                   floors=floor_array)

    @classmethod
    def from_geometry(cls, geometry: FloorGeometry, cell: float = NAV_CELL) -> "NavGrid | None":
        bounds = (geometry.min_x, geometry.max_x, geometry.min_y, geometry.max_y,
                  geometry.min_z, geometry.max_z)
        return cls.from_floor_triangles(geometry.zone, geometry.triangles, bounds,
                                        cell=cell, signature=geometry.signature(),
                                        walls=geometry.walls)

    # --- serialisation ------------------------------------------------------------------------
    def save(self, path: Path, signature: tuple[int, int] | None = None) -> None:
        signature = self.signature if signature is None else signature
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        header = struct.pack(
            "<8sHHffffIIQq",
            NAV_MAGIC, NAV_VERSION, self.zone, self.cell, self.origin_x, self.origin_z,
            0.0, self.width, self.height,
            int(signature[0]) & 0xFFFFFFFFFFFFFFFF, int(signature[1]),
        )
        payload = (bytes(self.counts) + self.heights.tobytes()
                   + struct.pack("<I", len(self.walls) // 9) + self.walls.tobytes()
                   + struct.pack("<I", len(self.floors) // 9) + self.floors.tobytes())
        raw = header + zlib.compress(payload, 6)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(raw)
        os.replace(temporary, path)

    @classmethod
    def load(cls, path: Path) -> "NavGrid | None":
        try:
            raw = Path(path).read_bytes()
            if len(raw) < struct.calcsize("<8sHHffffIIQq") or not raw.startswith(NAV_MAGIC):
                return None
            (magic, version, zone, cell, origin_x, origin_z, _reserved,
             width, height, sig_size, sig_mtime) = struct.unpack_from("<8sHHffffIIQq", raw, 0)
            if version != NAV_VERSION or width <= 0 or height <= 0:
                return None
            payload = zlib.decompress(raw[struct.calcsize("<8sHHffffIIQq"):])
            split = width * height
            heights_size = split * NAV_MAX_LAYERS * 2
            if len(payload) < split + heights_size + 4:
                return None
            counts = bytearray(payload[:split])
            if max(counts, default=0) > NAV_MAX_LAYERS:
                return None
            heights = array("h")
            heights.frombytes(payload[split:split + heights_size])
            if sys.byteorder != "little":
                heights.byteswap()
            wall_count = struct.unpack_from("<I", payload, split + heights_size)[0]
            wall_start = split + heights_size + 4
            wall_end = wall_start + wall_count * 9 * 4
            if wall_end + 4 > len(payload):
                return None
            walls = array("f")
            walls.frombytes(payload[wall_start:wall_end])
            if sys.byteorder != "little":
                walls.byteswap()
            floor_count = struct.unpack_from("<I", payload, wall_end)[0]
            floor_start = wall_end + 4
            floor_end = floor_start + floor_count * 9 * 4
            if floor_end != len(payload):
                return None
            floors = array("f")
            floors.frombytes(payload[floor_start:floor_end])
            if sys.byteorder != "little":
                floors.byteswap()
        except (OSError, zlib.error, struct.error, ValueError):
            return None
        return cls(zone, cell, origin_x, origin_z, width, height, counts, heights,
                   walls=walls, signature=(int(sig_size), int(sig_mtime)), floors=floors)

    # --- lookup -------------------------------------------------------------------------------
    def _cell_index(self, x: float, z: float) -> int:
        i = int((x - self.origin_x) // self.cell)
        j = int((z - self.origin_z) // self.cell)
        if i < 0 or j < 0 or i >= self.width or j >= self.height:
            return -1
        return j * self.width + i

    def _cell_center(self, index: int) -> tuple[float, float]:
        j, i = divmod(index, self.width)
        return (self.origin_x + (i + 0.5) * self.cell,
                self.origin_z + (j + 0.5) * self.cell)

    def _layers(self, index: int) -> tuple[int, int]:
        if index < 0 or index >= len(self.counts):
            return 0, index * self.max_layers
        return int(self.counts[index]), index * self.max_layers

    def layer_height(self, index: int, slot: int) -> float:
        return self.heights[index * self.max_layers + slot] / NAV_HEIGHT_SCALE

    def floor_at(self, x: float, z: float, y: float) -> float | None:
        """The floor triangle directly under ``(x, z)``, nearest to ``y``.

        The cell grid stores one height per triangle *at the cell centre*.  At a wall
        edge that is not the same thing: one cell can hold open ground at its centre and
        a wall top at its edge.  This query tests the actual point against the original
        floor triangles, so a walker cannot step onto a surface that exists only in the
        neighbouring half of the cell.  None means no floor triangle covers the point;
        callers then fall back to the rasterised layers.
        """
        index = self._cell_index(x, z)
        if index < 0:
            return None
        triangles = self.floor_bins.get(index)
        if not triangles:
            return None
        best: tuple[float, float] | None = None
        floors = self.floors
        for triangle in triangles:
            base = triangle * 9
            ax, ay, az, bx, by, bz, cx, cy, cz = floors[base:base + 9]
            if (x < min(ax, bx, cx) - 1e-6 or x > max(ax, bx, cx) + 1e-6
                    or z < min(az, bz, cz) - 1e-6 or z > max(az, bz, cz) + 1e-6):
                continue
            if not self._point_in_triangle(x, z, ax, az, bx, bz, cx, cz):
                continue
            den = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
            if abs(den) < 1e-9:
                continue
            l1 = ((bz - cz) * (x - cx) + (cx - bx) * (z - cz)) / den
            l2 = ((cz - az) * (x - cx) + (ax - cx) * (z - cz)) / den
            floor = l1 * ay + l2 * by + (1.0 - l1 - l2) * cy
            error = abs(floor - y)
            if best is None or error < best[0]:
                best = (error, floor)
        return None if best is None else best[1]

    def floor_near(self, x: float, z: float, y: float,
                   limit: float = 4.0) -> float | None:
        """The floor at this point closest to ``y``, or None when there is no floor."""
        point = self.floor_at(x, z, y)
        if point is not None:
            # A triangle covers the point, so its height is authoritative: if it is
            # outside the allowed band, returning a different cell layer would put the
            # walker back inside the wall.
            return point if abs(point - y) <= limit else None
        index = self._cell_index(x, z)
        if index < 0:
            return None
        count, base = self._layers(index)
        best = None
        for slot in range(count):
            floor = self.heights[base + slot] / NAV_HEIGHT_SCALE
            distance = abs(floor - y)
            if best is None or distance < best[0]:
                best = (distance, floor)
        if best is None or best[0] > limit:
            return None
        return best[1]

    def layer_at(self, x: float, z: float, y: float) -> tuple[float, float] | None:
        """``(floor, height error)`` for the surface nearest ``y``, without a limit."""
        index = self._cell_index(x, z)
        if index < 0:
            return None
        count, base = self._layers(index)
        best = None
        for slot in range(count):
            floor = self.heights[base + slot] / NAV_HEIGHT_SCALE
            error = abs(floor - y)
            if best is None or error < best[1]:
                best = (floor, error)
        return best

    def step_ok(self, current: float, target: float, distance: float) -> bool:
        return abs(target - current) <= NAV_STEP_BIAS + NAV_MAX_GRADE * max(0.0, distance)

    def has_floor(self, x: float, z: float) -> bool:
        index = self._cell_index(x, z)
        return index >= 0 and self.counts[index] > 0

    @staticmethod
    def _point_in_triangle(px: float, pz: float, ax: float, az: float,
                           bx: float, bz: float, cx: float, cz: float) -> bool:
        d1 = (px - bx) * (az - bz) - (ax - bx) * (pz - bz)
        d2 = (px - cx) * (bz - cz) - (bx - cx) * (pz - cz)
        d3 = (px - ax) * (cz - az) - (cx - ax) * (pz - az)
        negative = d1 < -1e-9 or d2 < -1e-9 or d3 < -1e-9
        positive = d1 > 1e-9 or d2 > 1e-9 or d3 > 1e-9
        return not (negative and positive)

    @staticmethod
    def _segments_cross(ax: float, az: float, bx: float, bz: float,
                        cx: float, cz: float, dx: float, dz: float) -> bool:
        def cross(ox, oz, px, pz, qx, qz):
            return (px - ox) * (qz - oz) - (pz - oz) * (qx - ox)
        d1 = cross(ax, az, bx, bz, cx, cz)
        d2 = cross(ax, az, bx, bz, dx, dz)
        d3 = cross(cx, cz, dx, dz, ax, az)
        d4 = cross(cx, cz, dx, dz, bx, bz)
        if ((d1 > 1e-9 and d2 < -1e-9) or (d1 < -1e-9 and d2 > 1e-9)) and \
           ((d3 > 1e-9 and d4 < -1e-9) or (d3 < -1e-9 and d4 > 1e-9)):
            return True
        return False

    def _wall_hit(self, ax: float, az: float, ay: float,
                  bx: float, bz: float, by: float) -> bool:
        """Does the body-height band of this move cross a barrier triangle?"""
        if not self.wall_bins:
            return False
        dist = math.hypot(bx - ax, bz - az)
        pieces = max(1, int(math.ceil(dist / (self.cell * 0.5))))
        candidates: set[int] = set()
        for piece in range(pieces + 1):
            fraction = piece / pieces
            i = int((ax + (bx - ax) * fraction - self.origin_x) // self.cell)
            j = int((az + (bz - az) * fraction - self.origin_z) // self.cell)
            if 0 <= i < self.width and 0 <= j < self.height:
                found = self.wall_bins.get(j * self.width + i)
                if found:
                    candidates.update(found)
        if not candidates:
            return False
        low = min(ay, by) - NAV_WALL_BOTTOM_SLACK
        high = max(ay, by) + NAV_BODY_HEIGHT
        walls = self.walls
        for triangle in candidates:
            base = triangle * 9
            ax1, ay1, az1, bx1, by1, bz1, cx1, cy1, cz1 = walls[base:base + 9]
            if max(ay1, by1, cy1) < low or min(ay1, by1, cy1) > high:
                continue
            if (max(ax1, bx1, cx1) < min(ax, bx) - 1e-6
                    or min(ax1, bx1, cx1) > max(ax, bx) + 1e-6
                    or max(az1, bz1, cz1) < min(az, bz) - 1e-6
                    or min(az1, bz1, cz1) > max(az, bz) + 1e-6):
                continue
            if (self._point_in_triangle(ax, az, ax1, az1, bx1, bz1, cx1, cz1)
                    or self._point_in_triangle(bx, bz, ax1, az1, bx1, bz1, cx1, cz1)):
                return True
            if (self._segments_cross(ax, az, bx, bz, ax1, az1, bx1, bz1)
                    or self._segments_cross(ax, az, bx, bz, bx1, bz1, cx1, cz1)
                    or self._segments_cross(ax, az, bx, bz, cx1, cz1, ax1, az1)):
                return True
        return False

    def step_floor(self, x0: float, z0: float, y0: float,
                   x1: float, z1: float, sample: float | None = None) -> float | None:
        """Walk a short straight segment and return the final floor height.

        The segment is sampled inside the grid so a 6 yalm/tick chase step cannot tunnel
        through a one-cell wall.  ``None`` means the move would leave the floor.
        """
        dx, dz = x1 - x0, z1 - z0
        distance = math.hypot(dx, dz)
        if distance < 1e-6:
            return y0
        pieces = max(1, int(math.ceil(distance / (sample or self.cell * 0.5))))
        step = distance / pieces
        y = y0
        previous_x, previous_z = x0, z0
        for piece in range(1, pieces + 1):
            fraction = piece / pieces
            sx = x0 + dx * fraction
            sz = z0 + dz * fraction
            index = self._cell_index(sx, sz)
            if index < 0:
                return None
            point = self.floor_at(sx, sz, y)
            if point is not None:
                if not self.step_ok(y, point, step):
                    return None
                floor = point
            else:
                count, base = self._layers(index)
                best = None
                for slot in range(count):
                    candidate = self.heights[base + slot] / NAV_HEIGHT_SCALE
                    if self.step_ok(y, candidate, step):
                        error = abs(candidate - y)
                        if best is None or error < best[0]:
                            best = (error, candidate)
                if best is None:
                    return None
                floor = best[1]
            if self._wall_hit(previous_x, previous_z, y, sx, sz, floor):
                return None
            y = floor
            previous_x, previous_z = sx, sz
        return y

    def line_clear(self, x0: float, y0: float, z0: float,
                   x1: float, y1: float, z1: float) -> bool:
        """Is there an unbroken walkable line between the two points?"""
        dx, dz = x1 - x0, z1 - z0
        distance = math.hypot(dx, dz)
        if distance < 1e-6:
            return abs(y1 - y0) <= NAV_STEP_BIAS + NAV_MAX_GRADE * self.cell
        pieces = max(1, int(math.ceil(distance / (self.cell * 0.5))))
        step = distance / pieces
        y = y0
        previous_x, previous_z = x0, z0
        for piece in range(1, pieces + 1):
            fraction = piece / pieces
            sx = x0 + dx * fraction
            sz = z0 + dz * fraction
            index = self._cell_index(sx, sz)
            if index < 0:
                return False
            point = self.floor_at(sx, sz, y)
            if point is not None:
                if not self.step_ok(y, point, step):
                    return False
                floor = point
            else:
                count, base = self._layers(index)
                best = None
                for slot in range(count):
                    candidate = self.heights[base + slot] / NAV_HEIGHT_SCALE
                    if self.step_ok(y, candidate, step):
                        error = abs(candidate - y)
                        if best is None or error < best[0]:
                            best = (error, candidate)
                if best is None:
                    return False
                floor = best[1]
            if self._wall_hit(previous_x, previous_z, y, sx, sz, floor):
                return False
            y = floor
            previous_x, previous_z = sx, sz
        # The two endpoints both have to be on (nearly) the same floor.  A fixed small
        # tolerance is the right test; scaling it by the segment length used to let a
        # point twenty yalms above the mesh pass as "clear".
        return abs(y - y1) <= NAV_STEP_BIAS + NAV_MAX_GRADE * max(self.cell * 0.5, step) + 0.25

    # --- pathing ------------------------------------------------------------------------------
    def _nearest_state(self, index: int, y: float) -> tuple[int, float] | None:
        count, base = self._layers(index)
        best = None  # (height error, slot, floor)
        for slot in range(count):
            floor = self.heights[base + slot] / NAV_HEIGHT_SCALE
            error = abs(floor - y)
            if best is None or error < best[0]:
                best = (error, slot, floor)
        if best is None:
            return None
        return (index * self.max_layers + best[1], best[2])

    def _state_cell(self, state: int) -> tuple[int, int]:
        return divmod(state, self.max_layers)

    def _state_height(self, state: int) -> float:
        return self.heights[state] / NAV_HEIGHT_SCALE

    def _goal_state(self, index: int, y: float) -> tuple[int, float] | None:
        state = self._nearest_state(index, y)
        if state is not None:
            return state
        # The player can stand where the rasteriser found no cell centre (a narrow ledge,
        # the lip of a wall, the seam of two tiles).  Look in the nearest rings before
        # giving up, so a monster walks to the bottom of the ledge instead of nowhere.
        j, i = divmod(index, self.width)
        for radius in range(1, NAV_GOAL_SNAP_CELLS + 1):
            best = None
            for ni in range(i - radius, i + radius + 1):
                for nj in range(j - radius, j + radius + 1):
                    if ni < 0 or nj < 0 or ni >= self.width or nj >= self.height:
                        continue
                    if max(abs(ni - i), abs(nj - j)) != radius:
                        continue
                    candidate = nj * self.width + ni
                    found = self._nearest_state(candidate, y)
                    if found is None:
                        continue
                    nx, nz = self._cell_center(candidate)
                    px, pz = self._cell_center(index)
                    distance = math.hypot(nx - px, nz - pz)
                    if best is None or (distance, found[1]) < best[0]:
                        best = ((distance, found[1]), found[0])
            if best is not None:
                state = best[1]
                return (state, self._state_height(state))
        return None

    def find_path(self, start, goal,
                  max_nodes: int = NAV_DEFAULT_NODES
                  ) -> list[tuple[float, float, float]] | None:
        """A* between two world points; a list of walkable waypoints or None.

        Each waypoint is ``(x, y, z)`` with the floor height already filled in.  An empty
        list is a valid result when the two points are already in the same place.
        """
        sx, sy, sz = float(start[0]), float(start[1]), float(start[2])
        gx, gy, gz = float(goal[0]), float(goal[1]), float(goal[2])
        start_index = self._cell_index(sx, sz)
        goal_index = self._cell_index(gx, gz)
        if start_index < 0 or goal_index < 0:
            return None
        start_state = self._nearest_state(start_index, sy)
        goal_state = self._goal_state(goal_index, gy)
        if start_state is None or goal_state is None:
            return None
        if start_state[0] == goal_state[0]:
            return [(gx, goal_state[1], gz)]

        goal_state_id = goal_state[0]
        goal_x, goal_z = self._cell_center(goal_index)
        costs: dict[int, float] = {start_state[0]: 0.0}
        previous: dict[int, int] = {}
        queue = [(0.0, 0, start_state[0])]
        counter = 1
        visited = 0
        while queue:
            estimate, _, state = heapq.heappop(queue)
            known = costs.get(state)
            if known is None:
                continue
            if state == goal_state_id:
                path: list[tuple[float, float, float]] = []
                while True:
                    index, slot = self._state_cell(state)
                    x, z = self._cell_center(index)
                    path.append((x, self._state_height(state), z))
                    if state not in previous:
                        break
                    state = previous[state]
                path.reverse()
                return self._finish_path((sx, sy, sz), path, (gx, gy, gz))
            visited += 1
            if visited > max_nodes:
                return None
            index, _slot = self._state_cell(state)
            current_height = self._state_height(state)
            x, z = self._cell_center(index)
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                ni = (index % self.width) + dx
                nj = (index // self.width) + dz
                if ni < 0 or nj < 0 or ni >= self.width or nj >= self.height:
                    continue
                nindex = nj * self.width + ni
                ncount, nbase = self._layers(nindex)
                if not ncount:
                    continue
                horizontal = self.cell * (math.sqrt(2.0) if dx and dz else 1.0)
                if dx and dz:
                    # No cutting a wall's corner: both cardinal cells must be steppable.
                    blocked = False
                    for ox, oz in ((dx, 0), (0, dz)):
                        oi = (index % self.width) + ox
                        oj = (index // self.width) + oz
                        if oi < 0 or oj < 0 or oi >= self.width or oj >= self.height:
                            blocked = True
                            break
                        oindex = oj * self.width + oi
                        ocount, obase = self._layers(oindex)
                        if not ocount or not any(
                                self.step_ok(current_height,
                                             self.heights[obase + slot] / NAV_HEIGHT_SCALE,
                                             self.cell) for slot in range(ocount)):
                            blocked = True
                            break
                    if blocked:
                        continue
                best = None
                for slot in range(ncount):
                    floor = self.heights[nbase + slot] / NAV_HEIGHT_SCALE
                    if not self.step_ok(current_height, floor, horizontal):
                        continue
                    error = abs(floor - current_height)
                    if best is None or error < best[0]:
                        best = (error, slot, floor)
                if best is None:
                    continue
                nx, nz = self._cell_center(nindex)
                if self._wall_hit(x, z, current_height, nx, nz, best[2]):
                    continue
                nstate = nindex * self.max_layers + best[1]
                cost = known + horizontal + best[0] * 0.35
                if cost >= costs.get(nstate, math.inf):
                    continue
                costs[nstate] = cost
                previous[nstate] = state
                nx, nz = self._cell_center(nindex)
                heuristic = math.hypot(nx - goal_x, nz - goal_z) * NAV_HEURISTIC_WEIGHT
                heapq.heappush(queue, (cost + heuristic, counter, nstate))
                counter += 1
        return None

    def _finish_path(self, start: tuple[float, float, float],
                     points: list[tuple[float, float, float]],
                     goal: tuple[float, float, float]) -> list[tuple[float, float, float]]:
        """Drop waypoints the walker can see past, and finish at the exact goal."""
        if not points:
            return []
        smoothed: list[tuple[float, float, float]] = [start]
        index = 0
        while index < len(points):
            furthest = index
            # A path is short (chase range or roam radius); this is at worst a few dozen
            # line tests, not a zone-wide sweep.
            for candidate in range(len(points) - 1, index - 1, -1):
                if candidate == len(points) - 1:
                    target = goal
                else:
                    target = points[candidate]
                if self.line_clear(smoothed[-1][0], smoothed[-1][1], smoothed[-1][2],
                                   target[0], target[1], target[2]):
                    furthest = candidate
                    break
            waypoint = points[furthest]
            if furthest == len(points) - 1 and self.line_clear(
                    smoothed[-1][0], smoothed[-1][1], smoothed[-1][2],
                    goal[0], goal[1], goal[2]):
                waypoint = goal
            elif furthest == len(points) - 1:
                waypoint = points[furthest]
            smoothed.append((float(waypoint[0]), float(waypoint[1]), float(waypoint[2])))
            index = furthest + 1
        # The first entry is the walker's own feet; the mover consumes the rest.
        return smoothed[1:]


class NavCache:
    """Build/load one navigation grid per zone, and keep a few of them in memory."""

    def __init__(self, cache_dir: Path, game_dir: Path | None,
                 enabled: bool = True, keep: int = 3):
        self.cache_dir = Path(cache_dir)
        self.game_dir = Path(game_dir) if game_dir else None
        self.enabled = bool(enabled)
        self.keep = max(1, int(keep))
        self._grids: OrderedDict[int, NavGrid | None] = OrderedDict()
        self._lock = threading.RLock()          # in-memory state only; never a build
        self._build_lock = threading.Lock()     # one CPU-heavy build at a time
        self._pending: set[int] = set()
        self._sources: dict[int, tuple[int, int] | None] = {}
        self._warned = False

    def prepare(self, zone: int) -> None:
        """Start building a zone's grid in the background, if it is not cached.

        The first monster tick should not hold up a zone-in for the several seconds the
        collision mesh takes to turn into floors.  Until the worker finishes,
        ``current`` returns None and the mob tick keeps its legacy movement.
        """
        if not self.enabled:
            return
        zone = int(zone)
        if self.game_dir is None and not self._cache_path(zone).exists():
            return
        with self._lock:
            if zone in self._grids or zone in self._pending:
                return
        if not self._cache_path(zone).exists() and self._source_signature(zone) is None:
            return
        with self._lock:
            if zone in self._grids or zone in self._pending:
                return
            self._pending.add(zone)
        thread = threading.Thread(target=self._prepare_worker, args=(zone,),
                                  name="fanxi-nav-%d" % zone, daemon=True)
        thread.start()

    def _remember(self, zone: int, grid: NavGrid | None) -> None:
        with self._lock:
            self._grids[zone] = grid
            self._grids.move_to_end(zone)
            while len(self._grids) > self.keep:
                self._grids.popitem(last=False)

    def _prepare_worker(self, zone: int) -> None:
        try:
            self.grid(zone)
        except Exception:  # never take a zone down because its mesh changed
            log.exception("zone %d navigation could not be prepared", zone)
            self._remember(zone, None)
        finally:
            with self._lock:
                self._pending.discard(zone)

    def grid(self, zone: int) -> NavGrid | None:
        """The grid, waiting for a build if necessary (prebuild commands use this)."""
        zone = int(zone)
        if not self.enabled:
            return None
        with self._lock:
            if zone in self._grids:
                self._grids.move_to_end(zone)
                return self._grids[zone]
        # Only one zone is rasterised at a time; a tick never waits on this lock
        # because it goes through ``current`` instead.
        with self._build_lock:
            with self._lock:
                if zone in self._grids:
                    self._grids.move_to_end(zone)
                    return self._grids[zone]
            grid = self._load_or_build(zone)
            self._remember(zone, grid)
            return grid

    def current(self, zone: int) -> NavGrid | None:
        """The grid if it is ready, without waiting for a build.

        The zone tick calls this: a monster uses the collision grid as soon as the
        background worker has one, and keeps its legacy movement until then.  A cache
        that is already on disk is loaded by the worker too, so this never blocks on a
        multi-second parse from the game thread.
        """
        zone = int(zone)
        if not self.enabled:
            return None
        with self._lock:
            if zone in self._grids:
                self._grids.move_to_end(zone)
                return self._grids[zone]
            if zone in self._pending:
                return None
        if self._cache_path(zone).exists():
            self.prepare(zone)
            return None
        if self._source_signature(zone) is None:
            # No model file and no cache: remember it instead of probing the file
            # table on every monster tick.
            self._remember(zone, None)
            if self.game_dir is None and not self._warned:
                with self._lock:
                    self._warned = True
                log.info("no FINAL FANTASY XI folder: monsters keep their old "
                         "straight-line movement (set FANXI_GAME_DIR to build zone "
                         "navigation)")
            return None
        self.prepare(zone)
        return None

    def pending(self, zone: int) -> bool:
        """Whether a background build for this zone is still running."""
        with self._lock:
            return int(zone) in self._pending

    def _cache_path(self, zone: int) -> Path:
        return self.cache_dir / ("%04d.nav" % int(zone))

    def _source_signature(self, zone: int) -> tuple[int, int] | None:
        if self.game_dir is None:
            return None
        with self._lock:
            if zone in self._sources:
                return self._sources[zone]
        try:
            from .zonemesh import zone_model_path
            path = zone_model_path(self.game_dir, zone)
            if path is None:
                signature = None
            else:
                stat = path.stat()
                signature = (int(stat.st_size), int(stat.st_mtime_ns))
        except OSError:
            signature = None
        with self._lock:
            self._sources[zone] = signature
        return signature

    def _load_or_build(self, zone: int) -> NavGrid | None:
        cache_path = self._cache_path(zone)
        signature = self._source_signature(zone)
        if cache_path.exists():
            grid = NavGrid.load(cache_path)
            if grid is not None:
                if signature is None or grid.signature == signature:
                    log.info("zone %d navigation: loaded cached grid %dx%d (%d barriers)",
                             zone, grid.width, grid.height, len(grid.walls) // 9)
                    return grid
                if self.game_dir is None:
                    return grid
                log.info("zone %d geometry changed; rebuilding its navigation grid", zone)
        if self.game_dir is None:
            if not self._warned:
                self._warned = True
                log.info("no FINAL FANTASY XI folder: monsters keep their old straight-line "
                         "movement (set FANXI_GAME_DIR to build zone navigation)")
            return None
        started = time.time()
        geometry = parse_zone_geometry(self.game_dir, zone)
        if geometry is None:
            log.info("zone %d has no collision mesh the reader can use", zone)
            return None
        with self._lock:
            self._sources[zone] = geometry.signature()
        grid = NavGrid.from_geometry(geometry)
        if grid is None:
            log.info("zone %d collision mesh has no walkable floors", zone)
            return None
        try:
            grid.save(cache_path, signature=geometry.signature())
        except OSError as exc:
            log.warning("zone %d navigation cache could not be written: %s", zone, exc)
        floor_cells = sum(1 for count in grid.counts if count)
        log.info("zone %d navigation: %d floors in %dx%d cells (%.0f%% walkable) in %.1fs",
                 zone, geometry.triangle_count, grid.width, grid.height,
                 100.0 * floor_cells / max(1, grid.width * grid.height), time.time() - started)
        return grid
