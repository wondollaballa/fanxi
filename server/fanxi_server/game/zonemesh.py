"""Read the walkable collision mesh out of the player's own FINAL FANTASY XI install.

Fanxi ships no zone geometry.  The client already has it, so the server reads the same
``MZB`` block the client draws when a zone loads and turns its upward faces into floor
triangles.  Nothing here is content: a zone model is only read when the server has been
pointed at a game folder (``FANXI_GAME_DIR``), and the derived navigation grid is cached
next to the rest of Fanxi's runtime data.

The DAT container is a sequence of 16-byte headers: four ASCII bytes, then a word whose
low seven bits are the resource type and whose high 25 bits are the block's length in
16-byte units.  A zone's model file id is ``zone + 100`` for the original zones and
``zone + 83635`` for the later ones; the client's own VTABLE/FTABLE pair resolves that id
to a ``ROM*/x/y.DAT`` path.  The MZB block's mesh records are stored twice: once as a
flat list and once through a coarse world grid.  The grid entries carry the transforms
that place each small tile in the zone, so that is what is read here.

The geometry is kept in the client's own coordinates: X east, Y up, Z north.  A post
from a LandSandBoat-era tool negates Y, but that is a viewer convention: comparing the
mesh against every imported spawn point in East Ronfaure puts the raw Y within one yalm
of the spawn height for the overwhelming majority of them.
"""
from __future__ import annotations

import math
import struct
from array import array
from dataclasses import dataclass, field
from pathlib import Path

# Resource types from the DAT container.  Only the MZB matters here: buildings that
# a zone keeps in a separate sub-region are not walkable terrain, and the zone's grid
# entries include the collision for the objects placed on the base mesh.
TYPE_MZB = 0x1C

# The MZB header and the mesh grid are lightly obfuscated.  The key table is part of the
# file format, not zone content, so it is a constant here.
_MZB_KEY = bytes((
    0xE2, 0xE5, 0x06, 0xA9, 0xED, 0x26, 0xF4, 0x42, 0x15, 0xF4, 0x81, 0x7F, 0xDE, 0x9A, 0xDE, 0xD0,
    0x1A, 0x98, 0x20, 0x91, 0x39, 0x49, 0x48, 0xA4, 0x0A, 0x9F, 0x40, 0x69, 0xEC, 0xBD, 0x81, 0x81,
    0x8D, 0xAD, 0x10, 0xB8, 0xC1, 0x88, 0x15, 0x05, 0x11, 0xB1, 0xAA, 0xF0, 0x0F, 0x1E, 0x34, 0xE6,
    0x81, 0xAA, 0xCD, 0xAC, 0x02, 0x84, 0x33, 0x0A, 0x19, 0x38, 0x9E, 0xE6, 0x73, 0x4A, 0x11, 0x5D,
    0xBF, 0x85, 0x77, 0x08, 0xCD, 0xD9, 0x96, 0x0D, 0x79, 0x78, 0xCC, 0x35, 0x06, 0x8E, 0xF9, 0xFE,
    0x66, 0xB9, 0x21, 0x03, 0x20, 0x29, 0x1E, 0x27, 0xCA, 0x86, 0x82, 0xE6, 0x45, 0x07, 0xDD, 0xA9,
    0xB6, 0xD5, 0xA2, 0x03, 0xEC, 0xAD, 0x62, 0x45, 0x2D, 0xCE, 0x79, 0xBD, 0x8F, 0x2D, 0x10, 0x18,
    0xE6, 0x0A, 0x6F, 0xAA, 0x6F, 0x46, 0x84, 0x32, 0x9F, 0x29, 0x2C, 0xC2, 0xF0, 0xEB, 0x18, 0x6F,
    0xF2, 0x3A, 0xDC, 0xEA, 0x7B, 0x0C, 0x81, 0x2D, 0xCC, 0xEB, 0xA1, 0x51, 0x77, 0x2C, 0xFB, 0x49,
    0xE8, 0x90, 0xF7, 0x90, 0xCE, 0x5C, 0x01, 0xF3, 0x5C, 0xF4, 0x41, 0xAB, 0x04, 0xE7, 0x16, 0xCC,
    0x3A, 0x05, 0x54, 0x55, 0xDC, 0xED, 0xA4, 0xD6, 0xBF, 0x3F, 0x9E, 0x08, 0x93, 0xB5, 0x63, 0x38,
    0x90, 0xF7, 0x5A, 0xF0, 0xA2, 0x5F, 0x56, 0xC8, 0x08, 0x70, 0xCB, 0x24, 0x16, 0xDD, 0xD2, 0x74,
    0x95, 0x3A, 0x1A, 0x2A, 0x74, 0xC4, 0x9D, 0xEB, 0xAF, 0x69, 0xAA, 0x51, 0x39, 0x65, 0x94, 0xA2,
    0x4B, 0x1F, 0x1A, 0x60, 0x52, 0x39, 0xE8, 0x23, 0xEE, 0x58, 0x39, 0x06, 0x3D, 0x22, 0x6A, 0x2D,
    0xD2, 0x91, 0x25, 0xA5, 0x2E, 0x71, 0x62, 0xA5, 0x0B, 0xC1, 0xE5, 0x6E, 0x43, 0x49, 0x7C, 0x58,
    0x46, 0x19, 0x9F, 0x45, 0x49, 0xC6, 0x40, 0x09, 0xA2, 0x99, 0x5B, 0x7B, 0x98, 0x7F, 0xA0, 0xD0,
))

# A horizontal face is a floor.  The mesh's winding is not consistent (most faces are
# stored with a downward normal), so the test is on |ny|.  Faces steeper than this are
# walls and cliffs; they never become walkable cells.
FLOOR_MIN_UP = 0.55  # cos(56.6 degrees)
# Everything that is not a walkable floor is a barrier: a vertical wall, the face of a
# cliff, a fence rail.  Keeping these triangles lets the navigator stop a mob from
# walking through a wall that stands on otherwise flat ground, where a height-step test
# alone would see no difference.
WALL_MIN_SPAN = 0.15  # a barely tilted sliver is not a wall

# A vertex this far behind the near plane in the mesh's own Z is a known junk record.
_MIN_MESH_Z = -99329.0
_MAX_COORD = 100000.0


@dataclass
class FloorGeometry:
    """Upward faces of one zone, in the client's coordinates."""

    zone: int
    triangles: array = field(default_factory=lambda: array("f"))
    walls: array = field(default_factory=lambda: array("f"))
    min_x: float = 0.0
    max_x: float = 0.0
    min_y: float = 0.0
    max_y: float = 0.0
    min_z: float = 0.0
    max_z: float = 0.0
    source: Path | None = None
    source_size: int = 0
    source_mtime_ns: int = 0
    skipped: int = 0

    @property
    def triangle_count(self) -> int:
        return len(self.triangles) // 9

    @property
    def wall_count(self) -> int:
        return len(self.walls) // 9

    def signature(self) -> tuple[int, int]:
        return (int(self.source_size), int(self.source_mtime_ns))


def _u32(data, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _i32(data, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def _f32(data, offset: int) -> float:
    return struct.unpack_from("<f", data, offset)[0]


def _i16(data, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def iter_blocks(data) -> tuple[str, int, int, int]:
    """Yield ``(name, type, offset, size)`` for the DAT blocks in a file body."""
    pos = 0
    limit = len(data)
    while pos + 16 <= limit:
        name = bytes(data[pos:pos + 4]).decode("ascii", "replace")
        word = _u32(data, pos + 4)
        kind = word & 0x7F
        size = ((word >> 7) & 0x7FFFF) * 16 - 16
        if size < 0 or pos + 16 + size > limit:
            return
        yield name, kind, pos + 16, size
        if word == 0:
            return
        pos += 16 + size


class FileTable:
    """The client's ``VTABLE``/``FTABLE`` pairs: file id in, ``ROM/x/y.DAT`` out.

    The install keeps one pair per ROM folder: ``VTABLE.DAT``/``FTABLE.DAT`` at the root,
    then ``ROM2/VTABLE2.DAT``, ``ROM3/VTABLE3.DAT`` and so on.  A file id is searched in
    each pair; the table entry's version byte (1..9) names the ROM folder it lives in.
    """

    _DIRS = ("", "ROM2", "ROM3", "ROM4", "ROM5", "ROM6", "ROM7", "ROM8", "ROM9")

    def __init__(self, game_dir: Path):
        self.game_dir = Path(game_dir)
        self._tables: list[tuple[bytes, bytes]] | None = None

    def _load(self) -> list[tuple[bytes, bytes]]:
        if self._tables is None:
            tables = []
            for index, folder in enumerate(self._DIRS, start=1):
                base = self.game_dir / folder if folder else self.game_dir
                name = "" if not folder else str(index)
                vtable = base / f"VTABLE{name}.DAT"
                ftable = base / f"FTABLE{name}.DAT"
                if vtable.exists() and ftable.exists():
                    try:
                        tables.append((vtable.read_bytes(), ftable.read_bytes()))
                    except OSError:
                        continue
            self._tables = tables
        return self._tables

    def dat_path(self, file_id: int) -> Path | None:
        file_id = int(file_id)
        if file_id < 0:
            return None
        for vtable, ftable in self._load():
            if file_id >= len(vtable) or file_id * 2 + 2 > len(ftable):
                continue
            version = vtable[file_id]
            if version == 0:
                continue
            entry = struct.unpack_from("<H", ftable, file_id * 2)[0]
            folder = entry >> 7
            name = entry & 0x7F
            if version == 1:
                path = self.game_dir / "ROM" / str(folder) / f"{name}.DAT"
            else:
                path = self.game_dir / f"ROM{version}" / str(folder) / f"{name}.DAT"
            return path
        return None


def zone_model_file_id(zone: int) -> int:
    """The client's file id for a zone's model."""
    zone = int(zone)
    return zone + 100 if zone < 256 else zone + 83635


def zone_model_path(game_dir: Path, zone: int) -> Path | None:
    path = FileTable(game_dir).dat_path(zone_model_file_id(zone))
    if path is None or not path.exists():
        return None
    return path


def decode_mzb(body) -> bytearray:
    """Undo the MZB header/table obfuscation.

    There are two passes: the first one XORs runs whose length and presence come from a
    rolling key, the second one flips 16-byte chunks of the node table.
    """
    data = bytearray(body)
    if len(data) < 8 or data[3] < 0x1B:
        return data
    decode_length = min(len(data), _u32(data, 0) & 0xFFFFFF)
    key = _MZB_KEY[data[7] ^ 0xFF]
    count = 0
    pos = 8
    while pos < decode_length:
        width = ((key >> 4) & 7) + 16
        if (key & 1) and pos + width < decode_length:
            data[pos:pos + width] = bytes(value ^ 0xFF for value in data[pos:pos + width])
        count += 1
        key += count
        pos += width
    node_count = _u32(data, 4) & 0xFFFFFF
    node_count = min(node_count, max(0, (len(data) - 0x20) // 0x64))
    for index in range(node_count):
        start = 0x20 + index * 0x64
        data[start:start + 16] = bytes(value ^ 0x55 for value in data[start:start + 16])
    return data


def _matrix(data, offset: int) -> list[float] | None:
    try:
        values = list(struct.unpack_from("<16f", data, offset))
    except struct.error:
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    return values


def _mesh_triangles(data, matrix: list[float], offset: int,
                    out: array, walls: array, bounds: list[float]) -> int:
    """Append one mesh's floor triangles, transformed into zone coordinates.

    Returns the number of triangles appended; malformed geometry is skipped rather than
    allowed to poison the whole zone.
    """
    if offset <= 0 or offset + 0x10 > len(data):
        return 0
    vertices_at = _i32(data, offset)
    normals_at = _i32(data, offset + 4)
    triangles_at = _i32(data, offset + 8)
    triangle_count = _i16(data, offset + 0x0C)
    if (vertices_at <= 0 or normals_at <= vertices_at or triangles_at <= normals_at
            or triangle_count <= 0):
        return 0
    if triangle_count > 20000:
        return 0
    vertex_count = (normals_at - vertices_at) // 12
    if vertex_count <= 0 or vertex_count > 20000:
        return 0
    if triangles_at + triangle_count * 8 > len(data):
        return 0

    det = (matrix[0] * (matrix[5] * matrix[10] - matrix[6] * matrix[9])
           - matrix[1] * (matrix[4] * matrix[10] - matrix[6] * matrix[8])
           + matrix[2] * (matrix[4] * matrix[9] - matrix[5] * matrix[8]))
    points: list[tuple[float, float, float] | None] = []
    for index in range(vertex_count):
        base = vertices_at + index * 12
        if base + 12 > len(data):
            points.append(None)
            continue
        x, y, z = struct.unpack_from("<3f", data, base)
        depth = matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14]
        px = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12]
        py = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13]
        if (not all(math.isfinite(value) for value in (px, py, depth))
                or depth <= _MIN_MESH_Z
                or abs(px) > _MAX_COORD or abs(py) > _MAX_COORD or abs(depth) > _MAX_COORD):
            points.append(None)
            continue
        points.append((px, py, matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14]))

    appended = 0
    for index in range(triangle_count):
        base = triangles_at + index * 8
        a, b, c, _normal = struct.unpack_from("<4H", data, base)
        a &= 0x3FFF
        b &= 0x3FFF
        c &= 0x3FFF
        if max(a, b, c) >= vertex_count:
            continue
        pa, pb, pc = points[a], points[b], points[c]
        if pa is None or pb is None or pc is None:
            continue
        # A floor's normal points mostly along Y.  Most zone faces are wound the other
        # way from a renderer's camera-facing convention, so compare the magnitude.
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length <= 1e-6:
            continue
        up = abs(ny) / length
        # Degenerate slivers at a tile edge make noisy cells; drop them.
        if max(abs(pa[0] - pb[0]), abs(pa[0] - pc[0]), abs(pa[2] - pb[2]),
               abs(pa[2] - pc[2])) < 0.05:
            continue
        if up < FLOOR_MIN_UP:
            # A barrier.  Its own vertical span is what a walker's body has to clear;
            # a flat sliver is not worth the segment tests.
            span = max(pa[1], pb[1], pc[1]) - min(pa[1], pb[1], pc[1])
            if span >= WALL_MIN_SPAN:
                for point in (pa, pb, pc):
                    walls.extend((point[0], point[1], point[2]))
                for point in (pa, pb, pc):
                    bounds[0] = min(bounds[0], point[0])
                    bounds[1] = max(bounds[1], point[0])
                    bounds[2] = min(bounds[2], point[1])
                    bounds[3] = max(bounds[3], point[1])
                    bounds[4] = min(bounds[4], point[2])
                    bounds[5] = max(bounds[5], point[2])
            continue
        if det > 0:
            pb, pc = pc, pb
        for point in (pa, pb, pc):
            out.extend((point[0], point[1], point[2]))
        appended += 1
        for point in (pa, pb, pc):
            bounds[0] = min(bounds[0], point[0])
            bounds[1] = max(bounds[1], point[0])
            bounds[2] = min(bounds[2], point[1])
            bounds[3] = max(bounds[3], point[1])
            bounds[4] = min(bounds[4], point[2])
            bounds[5] = max(bounds[5], point[2])
    return appended


def parse_zone_geometry(game_dir: Path, zone: int) -> FloorGeometry | None:
    """Read a zone's model and return its walkable floor triangles."""
    path = zone_model_path(game_dir, zone)
    if path is None:
        return None
    try:
        raw = path.read_bytes()
        stat = path.stat()
    except OSError:
        return None
    block = None
    for _name, kind, offset, size in iter_blocks(raw):
        if kind == TYPE_MZB:
            block = memoryview(raw)[offset:offset + size]
            break
    if block is None:
        return None
    data = decode_mzb(block)

    mesh_offset = 0
    for position in range(8, min(0x40, len(data) - 3), 4):
        mesh_offset = _i32(data, position)
        if mesh_offset:
            break
    if mesh_offset <= 0 or mesh_offset + 0x18 > len(data):
        return None
    grid_offset = _i32(data, mesh_offset + 0x10)
    grid_width = data[0x0C] if len(data) > 0x0D else 0
    grid_height = data[0x0D] if len(data) > 0x0D else 0
    if grid_offset <= 0 or not (1 <= grid_width <= 512 and 1 <= grid_height <= 512):
        return None

    geometry = FloorGeometry(
        zone=int(zone), source=path, source_size=int(stat.st_size),
        source_mtime_ns=int(stat.st_mtime_ns))
    bounds = [math.inf, -math.inf, math.inf, -math.inf, math.inf, -math.inf]
    cells_w = grid_width * 10
    cells_h = grid_height * 10
    entries: list[int] = []
    for cell in range(cells_w * cells_h):
        entry_offset = _i32(data, grid_offset + cell * 4) if grid_offset + cell * 4 + 4 <= len(data) else 0
        if entry_offset <= 0 or entry_offset + 4 > len(data):
            continue
        entries.clear()
        position = entry_offset
        for _ in range(1024):
            if position + 4 > len(data):
                break
            value = _i32(data, position)
            position += 4
            if value == 0:
                break
            entries.append(value)
        if len(entries) < 3:
            continue
        for index in range(1, len(entries) - 1, 2):
            visual = entries[index]
            mesh = entries[index + 1]
            if visual <= 0 or mesh <= 0 or visual + 64 > len(data):
                continue
            matrix = _matrix(data, visual)
            if matrix is None:
                geometry.skipped += 1
                continue
            _mesh_triangles(data, matrix, mesh, geometry.triangles, geometry.walls, bounds)

    if not geometry.triangles:
        return None
    geometry.min_x, geometry.max_x = bounds[0], bounds[1]
    geometry.min_y, geometry.max_y = bounds[2], bounds[3]
    geometry.min_z, geometry.max_z = bounds[4], bounds[5]
    return geometry
