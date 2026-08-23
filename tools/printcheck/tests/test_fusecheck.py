"""fusecheck: deterministic separable-body detection on a sliced print STL.

The unit under test is ``separable_bodies`` — remove the declared flexure
zone(s), count what remains. Two claims must hold, and their negative controls
prove the check can actually fail:

- a part joined ONLY through a thin bridge that sits inside the flexure AABB
  splits into two once the AABB is dropped (a working living hinge);
- the SAME two lobes joined by a weld OUTSIDE the AABB stay one (a fuse the
  flexure zone does not cover — the sweetheart-hamster failure class), so a
  design that welds beyond its hinge reads as fused no matter how the AABB is
  drawn.

Everything is built in-memory from boolean unions so the fixtures are genuinely
one connected manifold, exactly like a sliced STL.
"""

import json
import subprocess
import sys

import trimesh

from printcheck.fusecheck import (
    count_stl,
    main,
    parse_aabb,
    separable_bodies,
)


def _box(ext, at):
    m = trimesh.creation.box(extents=ext)
    m.apply_translation(at)
    return m


def _two_lobes(bridge):
    """Two 10 mm cubes 4 mm apart (x∈[-12,-2] and [2,12]), joined by ``bridge``.

    The bridge is a caller-supplied box; boolean-union everything into one
    connected manifold.
    """
    a = _box([10, 10, 10], [-7, 0, 5])
    b = _box([10, 10, 10], [7, 0, 5])
    fused = trimesh.boolean.union([a, bridge, b])
    fused.merge_vertices()
    return fused


# the flexure zone covers only the neck, x∈[-3,3], up to z≈7
_NECK_AABB = [parse_aabb("-3.2,-2.1,2.9:3.2,2.1,7.1")]


def test_bridge_in_flexure_splits_into_two():
    neck = _box([6, 4, 4], [0, 0, 5])           # spans the gap, inside the AABB
    k, dropped = separable_bodies(_two_lobes(neck), _NECK_AABB)
    assert k == 2, f"a hinge bridged only through the flexure must split, got {k}"
    assert dropped > 0, "the flexure AABB must actually drop the bridge faces"


def test_weld_outside_flexure_stays_one():
    weld = _box([16, 4, 4], [0, 0, 9])          # slab over the top, z∈[7,11]
    k, _ = separable_bodies(_two_lobes(weld), _NECK_AABB)
    assert k == 1, f"a weld the flexure zone does not cover must read fused, got {k}"


def test_no_aabb_leaves_the_hinge_fused():
    """With no flexure declared, a living hinge is legitimately one body — which
    is exactly why raw body-count cannot see a fuse and the AABB is required."""
    neck = _box([6, 4, 4], [0, 0, 5])
    k, dropped = separable_bodies(_two_lobes(neck), [])
    assert k == 1 and dropped == 0


def test_aabb_too_small_misses_the_bridge():
    """A flexure AABB that misses the bridge drops nothing and reads fused — the
    zero-drop signal (surfaced by --json) that the zone was mis-placed."""
    neck = _box([6, 4, 4], [0, 0, 5])
    tiny = [parse_aabb("100,100,100:101,101,101")]   # nowhere near the part
    k, dropped = separable_bodies(_two_lobes(neck), tiny)
    assert k == 1 and dropped == 0


def test_empty_mesh_is_zero_bodies():
    empty = trimesh.Trimesh()
    assert separable_bodies(empty, _NECK_AABB) == (0, 0)


def test_parse_aabb_normalises_and_validates():
    lo, hi = parse_aabb("3,2,7:-3,-2,-1")            # given hi<lo on every axis
    assert lo == (-3.0, -2.0, -1.0) and hi == (3.0, 2.0, 7.0)
    for bad in ("1,2,3", "1,2:3,4", "a,b,c:d,e,f"):
        try:
            parse_aabb(bad)
        except ValueError:
            continue
        raise AssertionError(f"parse_aabb accepted malformed spec {bad!r}")


def test_count_stl_rests_before_counting(tmp_path):
    """count_stl loads and rests to z=0, so AABBs are in the rested frame even
    when the exported mesh floats above the plate."""
    neck = _box([6, 4, 4], [0, 0, 5])
    mesh = _two_lobes(neck)
    mesh.apply_translation([0, 0, 40])               # float it 40 mm up
    p = tmp_path / "floated.stl"
    mesh.export(str(p))
    k, dropped = count_stl(str(p), _NECK_AABB)       # AABB still in rested frame
    assert k == 2 and dropped > 0


def test_cli_prints_body_count(tmp_path, capsys):
    neck = _box([6, 4, 4], [0, 0, 5])
    p = tmp_path / "part.stl"
    _two_lobes(neck).export(str(p))
    rc = main([str(p), "--ignore-aabb=-3.2,-2.1,2.9:3.2,2.1,7.1"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "2"


def test_cli_json_surfaces_dropped_faces(tmp_path, capsys):
    neck = _box([6, 4, 4], [0, 0, 5])
    p = tmp_path / "part.stl"
    _two_lobes(neck).export(str(p))
    rc = main([str(p), "--ignore-aabb=-3.2,-2.1,2.9:3.2,2.1,7.1", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["bodies"] == 2 and out["dropped_faces"] > 0


def test_cli_bad_aabb_is_error(tmp_path, capsys):
    p = tmp_path / "part.stl"
    trimesh.creation.box(extents=(10, 10, 10)).export(str(p))
    assert main([str(p), "--ignore-aabb=not-an-aabb"]) == 2


def test_selftest_entry_point_passes():
    """The built-in --selftest (also wired into scripts/check.sh) must pass."""
    rc = subprocess.call([sys.executable, "-m", "printcheck.fusecheck",
                          "--selftest"])
    assert rc == 0
