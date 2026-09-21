"""STL reading: both dialects, and the malformed cases the gate must not
wave through.

Positive and negative controls per rule (the house suite discipline): every
parse rule here has a test that it reads what it should and a test that it
refuses what it must.
"""

from pathlib import Path

import pytest

from cogcheck.stl import read_triangles
from conftest import box_triangles, write_ascii_stl, write_binary_stl


def test_ascii_box_round_trip(tmp_path: Path):
    out = tmp_path / "box.stl"
    write_ascii_stl(out, box_triangles(0, 0, 0, 10, 10, 10))
    triangles = read_triangles(out)
    assert len(triangles) == 12
    # Every vertex inside the box, and the box's 8 corners all present.
    corners = {v for t in triangles for v in t}
    assert (0.0, 0.0, 0.0) in corners
    assert (10.0, 10.0, 10.0) in corners
    for v in corners:
        assert all(0.0 <= c <= 10.0 for c in v)


def test_binary_box_round_trip(tmp_path: Path):
    out = tmp_path / "box.stl"
    write_binary_stl(out, box_triangles(0, 0, 0, 10, 10, 10))
    triangles = read_triangles(out)
    assert len(triangles) == 12
    assert {v for t in triangles for v in t} == {
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0), (10.0, 0.0, 10.0), (10.0, 10.0, 10.0), (0.0, 10.0, 10.0),
    }


def test_binary_detection_not_fooled_by_solid_header(tmp_path: Path):
    """A binary file whose header text starts with 'solid' must still parse
    as binary — the length identity decides, not the first five bytes."""
    import struct

    out = tmp_path / "sneaky.stl"
    triangles = box_triangles(0, 0, 0, 5, 5, 5)
    blob = bytearray(b"solid sneaky".ljust(80, b"\0"))
    blob += struct.pack("<I", len(triangles))
    for p1, p2, p3 in triangles:
        blob += struct.pack("<12fH", 0.0, 0.0, 0.0, *p1, *p2, *p3, 0)
    out.write_bytes(bytes(blob))
    assert len(read_triangles(out)) == 12


def test_ascii_with_comments_and_blank_lines(tmp_path: Path):
    out = tmp_path / "spaced.stl"
    out.write_text(
        "solid x\n\n  facet normal 0 0 -1\n    outer loop\n"
        "      vertex 0 0 0\n      vertex 1 0 0\n      vertex 0 1 0\n"
        "    endloop\n  endfacet\n\nendsolid x\n",
        encoding="utf-8",
    )
    assert read_triangles(out) == [((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))]


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(OSError):
        read_triangles(tmp_path / "nope.stl")


def test_garbage_text_refused(tmp_path: Path):
    out = tmp_path / "garbage.stl"
    out.write_text("this is not an stl at all\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no vertices"):
        read_triangles(out)


def test_vertex_without_three_coords_refused(tmp_path: Path):
    out = tmp_path / "short.stl"
    out.write_text(
        "solid x\n facet normal 0 0 0\n  outer loop\n"
        "   vertex 1 2\n  endloop\n endfacet\nendsolid x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="malformed vertex"):
        read_triangles(out)


def test_non_numeric_vertex_refused(tmp_path: Path):
    out = tmp_path / "nan.stl"
    out.write_text(
        "solid x\n facet normal 0 0 0\n  outer loop\n"
        "   vertex 1 two 3\n   vertex 1 2 3\n   vertex 4 5 6\n"
        "  endloop\n endfacet\nendsolid x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-numeric"):
        read_triangles(out)


def test_incomplete_triangle_refused(tmp_path: Path):
    """Two vertices under one facet: a facet must carry exactly three."""
    out = tmp_path / "short.stl"
    out.write_text(
        "solid x\n facet normal 0 0 0\n  outer loop\n"
        "   vertex 0 0 0\n   vertex 1 0 0\n  endloop\n endfacet\nendsolid x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly three"):
        read_triangles(out)


def test_ascii_non_finite_vertex_refused(tmp_path: Path):
    out = tmp_path / "nan.stl"
    out.write_text(
        "solid x\n facet normal 0 0 0\n  outer loop\n"
        "   vertex 0 0 0\n   vertex 1 nan 0\n   vertex 0 1 0\n"
        "  endloop\n endfacet\nendsolid x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-finite"):
        read_triangles(out)


def test_binary_non_finite_vertex_refused(tmp_path: Path):
    import math
    import struct

    out = tmp_path / "nan-bin.stl"
    blob = bytearray(b"nan fixture".ljust(80, b"\0"))
    blob += struct.pack("<I", 1)
    coords = [0.0] * 9
    coords[4] = math.nan
    blob += struct.pack("<12fH", 0.0, 0.0, 0.0, *coords, 0)
    out.write_bytes(bytes(blob))
    with pytest.raises(ValueError, match="non-finite"):
        read_triangles(out)
