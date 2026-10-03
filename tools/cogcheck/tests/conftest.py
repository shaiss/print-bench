"""Import the package from src/ without needing it installed, and share the
STL fixture builders every test here measures.

The point of cogcheck being stdlib-only is that gate.sh runs it wherever the
gate runs, installed or not; the tests hold themselves to the same bar, so
`python -m pytest tools/cogcheck/tests` works from a bare checkout.

The fixture builders write REAL STL files (ASCII and binary), not in-memory
meshes: the tool's contract is to measure an exported STL, and a suite that
skipped the file layer would restate the algebra instead of testing the
path the gate actually exercises.
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def box_triangles(
    x0: float, y0: float, z0: float, x1: float, y1: float, z1: float
) -> list:
    """The 12 triangles of an axis-aligned box, outward normals, CCW seen
    from outside — the winding the tetrahedron decomposition needs for a
    positive volume. Verified by the mass-properties tests landing on the
    exact analytic volume and centroid."""
    a, b, c = (x0, y0, z0), (x1, y0, z0), (x1, y1, z0)
    d, e, f = (x0, y1, z0), (x0, y0, z1), (x1, y0, z1)
    g, h = (x1, y1, z1), (x0, y1, z1)
    return [
        (a, d, c), (a, c, b),  # bottom, -z
        (e, f, g), (e, g, h),  # top, +z
        (a, b, f), (a, f, e),  # front, -y
        (d, h, g), (d, g, c),  # back, +y
        (a, e, h), (a, h, d),  # left, -x
        (b, c, g), (b, g, f),  # right, +x
    ]


def write_ascii_stl(path: Path, triangles: list, name: str = "fixture") -> None:
    """Write triangles as an ASCII STL (normals computed, matching what a
    real exporter emits)."""
    lines = [f"solid {name}"]
    for p1, p2, p3 in triangles:
        ux, uy, uz = (p2[i] - p1[i] for i in range(3))
        vx, vy, vz = (p3[i] - p1[i] for i in range(3))
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        lines.append(f"  facet normal {nx:.6f} {ny:.6f} {nz:.6f}")
        lines.append("    outer loop")
        for p in (p1, p2, p3):
            lines.append(f"      vertex {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_binary_stl(path: Path, triangles: list) -> None:
    """Write triangles as a binary STL (80-byte header, count, 50-byte
    facets with zero normals — the common exporter behaviour)."""
    blob = bytearray(b"cogcheck binary fixture".ljust(80, b"\0"))
    blob += struct.pack("<I", len(triangles))
    for p1, p2, p3 in triangles:
        blob += struct.pack("<12fH", 0.0, 0.0, 0.0, *p1, *p2, *p3, 0)
    path.write_bytes(bytes(blob))


def write_box(path: Path, x0: float, y0: float, z0: float,
              x1: float, y1: float, z1: float) -> None:
    """Convenience: an ASCII STL holding one axis-aligned box."""
    write_ascii_stl(path, box_triangles(x0, y0, z0, x1, y1, z1))
