"""Read an STL into triangles — the raw input every measurement here rests on.

Both dialects, detected by structure and never by filename or header text: a
binary STL is exactly ``84 + 50*n`` bytes where ``n`` is the little-endian
uint32 at offset 80, and an ASCII STL is text. The identity never holds for
text (bytes 80-83 of a text file are characters, so the count they encode is
on the order of a billion facets) and always holds for an intact binary file,
so the test discriminates cleanly. "solid" leading the file proves nothing
either way — some exporters emit it inside binary headers too.

The per-facet normal is read and discarded: it is derived from the vertices,
carries no information they do not, and is wrong often enough (exporters that
write 0 0 0) that trusting it would be measuring the exporter, not the mesh.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

#: One triangle: three vertices, each ``(x, y, z)`` in millimetres.
Triangle = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

_BINARY_HEADER = 80
_BINARY_COUNT = 4
_BINARY_FACET = 50  # 3 floats normal + 9 floats vertices + uint16 attribute


def read_triangles(path: str | Path) -> list[Triangle]:
    """Return every triangle in the STL at ``path``.

    Raises OSError (propagated) on an unreadable file and ValueError on a
    file that is neither dialect — the caller decides how loud that is.
    """
    data = Path(path).read_bytes()
    if _is_binary(data):
        return _read_binary(data, path)
    return _read_ascii(data.decode("utf-8", "replace"), path)


def _is_binary(data: bytes) -> bool:
    """True when the byte length is exactly the binary layout's length."""
    if len(data) < _BINARY_HEADER + _BINARY_COUNT:
        return False
    (count,) = struct.unpack_from("<I", data, _BINARY_HEADER)
    return len(data) == _BINARY_HEADER + _BINARY_COUNT + count * _BINARY_FACET


def _read_binary(data: bytes, path: str | Path = "<stl>") -> list[Triangle]:
    (count,) = struct.unpack_from("<I", data, _BINARY_HEADER)
    triangles: list[Triangle] = []
    off = _BINARY_HEADER + _BINARY_COUNT
    for _ in range(count):
        # 12 floats then the attribute count: skip the 3 normal floats by
        # starting the vertex unpack 12 bytes into the facet.
        values = struct.unpack_from("<9f", data, off + 12)
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"{path}: non-finite vertex coordinate in binary STL")
        triangles.append(
            (
                (values[0], values[1], values[2]),
                (values[3], values[4], values[5]),
                (values[6], values[7], values[8]),
            )
        )
        off += _BINARY_FACET
    return triangles


def _read_ascii(text: str, path: str | Path) -> list[Triangle]:
    """Parse ASCII STL with a facet state machine.

    Each facet must be ``facet`` → ``outer loop`` → exactly three ``vertex``
    lines → ``endloop`` → ``endfacet``. Counting facets and vertices globally
    would accept empty facets with stray vertices elsewhere.
    """
    triangles: list[Triangle] = []
    # ready | in_facet | in_loop | after_loop
    state = "ready"
    loop_vertices: list[tuple[float, float, float]] = []
    saw_solid = False

    for lineno, raw in enumerate(text.splitlines(), start=1):
        parts = raw.split()
        if not parts:
            continue
        tok = parts[0]

        if state == "ready":
            if tok == "solid":
                if saw_solid:
                    raise ValueError(f"{path}:{lineno}: unexpected second 'solid'")
                saw_solid = True
                continue
            if tok == "endsolid":
                break
            if tok == "facet":
                state = "in_facet"
                continue
            raise ValueError(
                f"{path}:{lineno}: expected 'facet' or 'endsolid', got {raw.strip()!r}"
            )

        if state == "in_facet":
            if tok == "outer" and len(parts) >= 2 and parts[1] == "loop":
                state = "in_loop"
                loop_vertices = []
                continue
            raise ValueError(
                f"{path}:{lineno}: expected 'outer loop' after facet, got {raw.strip()!r}"
            )

        if state == "in_loop":
            if tok == "vertex":
                if len(parts) != 4:
                    raise ValueError(
                        f"{path}: malformed vertex line: {raw.strip()!r}"
                    )
                try:
                    vertex = (float(parts[1]), float(parts[2]), float(parts[3]))
                except ValueError as e:
                    raise ValueError(
                        f"{path}: non-numeric vertex in {raw.strip()!r}"
                    ) from e
                if not all(math.isfinite(v) for v in vertex):
                    raise ValueError(
                        f"{path}: non-finite vertex in {raw.strip()!r}"
                    )
                loop_vertices.append(vertex)
                if len(loop_vertices) > 3:
                    raise ValueError(
                        f"{path}:{lineno}: facet has more than three vertices"
                    )
                continue
            if tok == "endloop":
                if len(loop_vertices) != 3:
                    raise ValueError(
                        f"{path}:{lineno}: a facet must carry exactly three "
                        f"vertices, got {len(loop_vertices)}"
                    )
                state = "after_loop"
                continue
            raise ValueError(
                f"{path}:{lineno}: expected 'vertex' or 'endloop', got {raw.strip()!r}"
            )

        if state == "after_loop":
            if tok == "endfacet":
                triangles.append(
                    (loop_vertices[0], loop_vertices[1], loop_vertices[2])
                )
                state = "ready"
                continue
            raise ValueError(
                f"{path}:{lineno}: expected 'endfacet' after endloop, got {raw.strip()!r}"
            )

    if state != "ready":
        raise ValueError(
            f"{path}: truncated ASCII STL — unfinished facet (state={state})"
        )
    if not triangles:
        raise ValueError(f"{path}: no facets found — not an STL?")
    return triangles
