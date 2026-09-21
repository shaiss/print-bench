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
    EXIT_ABOVE_MAX,
    EXIT_BELOW_MIN,
    VERDICT_FAIL,
    VERDICT_OK,
    VERDICT_WARN,
    count_stl,
    format_bound,
    main,
    parse_aabb,
    parse_bound,
    separable_bodies,
    verdict,
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


# --- two-sided bound (issue #612 part 2) ------------------------------------
#
# The fixture is the case the upper bound exists for: a plate carrying a
# stencil-style "0" — an annular slot whose inner disc (the counter) is held
# only by ONE bridge across the slot. Tethered, the plate is one body; with the
# bridge removed the counter is a freed island and the same plate reads two.
# Too FEW bodies is the fuse (a STRONG WARN a reviewer signs off); too MANY is
# the freed island / dropped part (a hard FAIL) — and the legacy one-sided
# floor every existing manifest uses can never FAIL, whatever the count.


def _stencil_plate(tethered):
    """30x20x2 plate minus a stencil '0' (annulus r 4..6); ``tethered`` keeps
    a 3x2 bridge across the slot so the counter stays attached."""
    plate = trimesh.creation.box(extents=[30, 20, 2])
    plate.apply_translation([0, 0, 1])
    ring = trimesh.creation.annulus(r_min=4, r_max=6, height=4)
    ring.apply_translation([0, 0, 1])
    if tethered:
        bridge = trimesh.creation.box(extents=[3, 2, 4])
        bridge.apply_translation([5, 0, 1])
        ring = trimesh.boolean.difference([ring, bridge])
    out = trimesh.boolean.difference([plate, ring])
    out.merge_vertices()
    return out


def test_stencil_fixture_is_one_body_tethered_two_freed():
    """The fixture itself: the tether is the only thing holding the counter."""
    assert separable_bodies(_stencil_plate(True), []) == (1, 0)
    assert separable_bodies(_stencil_plate(False), []) == (2, 0)


def test_exact_bound_passes_tethered_and_fails_freed():
    """`=1` (positive + negative control): the tethered plate is within the
    bound, the freed-island plate is OVER it — a FAIL, not the fuse's warn."""
    lo, hi = parse_bound("=1")
    tethered, _ = separable_bodies(_stencil_plate(True), [])
    freed, _ = separable_bodies(_stencil_plate(False), [])
    assert verdict(tethered, lo, hi) == VERDICT_OK
    assert verdict(freed, lo, hi) == VERDICT_FAIL


def test_parse_bound_accepts_the_three_shapes():
    assert parse_bound("3") == (3, None)        # legacy one-sided floor
    assert parse_bound("3:5") == (3, 5)         # two-sided
    assert parse_bound("=2") == (2, 2)          # exactly-N sugar
    assert parse_bound("2:2") == (2, 2)         # the sugar's long form
    assert parse_bound(" =1 ") == (1, 1)        # a manifest's stray whitespace


def test_parse_bound_rejects_malformed():
    """A max below the min is malformed (the negative control the two-sided
    grammar needs), as is anything that is not a non-negative integer."""
    for bad in ("5:3", "x", "=", "1:", ":1", "-1", "=a", "", "1:2:3", "1.5"):
        try:
            parse_bound(bad)
        except ValueError:
            continue
        raise AssertionError(f"parse_bound accepted malformed bound {bad!r}")


def test_one_sided_bound_warns_never_fails():
    """Legacy `assert <stl> <min>`: a low count is the fuse WARN exactly as
    before, and no count — however large — can ever FAIL a one-sided bound."""
    lo, hi = parse_bound("3")
    assert verdict(1, lo, hi) == VERDICT_WARN
    assert verdict(3, lo, hi) == VERDICT_OK
    assert verdict(100, lo, hi) == VERDICT_OK
    assert all(verdict(n, lo, hi) != VERDICT_FAIL for n in range(0, 50))


def test_two_sided_bound_orders_warn_below_fail_above():
    lo, hi = parse_bound("2:4")
    assert [verdict(n, lo, hi) for n in (1, 2, 3, 4, 5)] == [
        VERDICT_WARN, VERDICT_OK, VERDICT_OK, VERDICT_OK, VERDICT_FAIL]


def test_format_bound():
    assert format_bound(3) == ">= 3"
    assert format_bound(2, 2) == "= 2"
    assert format_bound(3, 5) == "3..5"


def test_cli_bound_exit_codes_keep_stdout_identical(tmp_path, capsys):
    """--bound carries the verdict in the EXIT CODE only: stdout stays the bare
    count, so a caller that never passes --bound sees byte-identical output."""
    t = tmp_path / "tethered.stl"
    f = tmp_path / "freed.stl"
    _stencil_plate(True).export(str(t))
    _stencil_plate(False).export(str(f))

    assert main([str(f)]) == 0                                # no bound: legacy
    assert capsys.readouterr().out == "2\n"
    assert main([str(t), "--bound", "=1"]) == 0               # within
    assert capsys.readouterr().out == "1\n"
    assert main([str(f), "--bound", "=1"]) == EXIT_ABOVE_MAX  # freed island
    assert capsys.readouterr().out == "2\n"
    assert main([str(f), "--bound", "3"]) == EXIT_BELOW_MIN   # the fuse case
    assert capsys.readouterr().out == "2\n"
    assert main([str(f), "--bound", "1"]) == 0                # legacy floor: ok
    assert capsys.readouterr().out == "2\n"


def test_cli_bound_json_carries_verdict(tmp_path, capsys):
    f = tmp_path / "freed.stl"
    _stencil_plate(False).export(str(f))
    rc = main([str(f), "--bound", "1:1", "--json"])
    assert rc == EXIT_ABOVE_MAX
    out = json.loads(capsys.readouterr().out)
    assert out["bodies"] == 2 and out["bound"] == [1, 1]
    assert out["verdict"] == VERDICT_FAIL
    rc = main([str(f), "--json"])                             # no bound: unchanged
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "bound" not in out and "verdict" not in out


def test_cli_malformed_bound_is_usage_error(tmp_path, capsys):
    p = tmp_path / "part.stl"
    trimesh.creation.box(extents=(10, 10, 10)).export(str(p))
    assert main([str(p), "--bound", "5:3"]) == 2
    assert "bound" in capsys.readouterr().err
