"""Measure shapes whose geometry we chose, and assert the numbers come back.

Every probe mesh is built from exact arcs and lines (examples/make_probe_models.py),
so these are truth comparisons, not snapshots: a 3 mm fillet has to measure 3 mm,
at any tessellation, in any pose, at any scale.
"""

import json
import math

import numpy as np
import pytest
import shapely
import trimesh

from make_probe_models import (chamfered_prism, chamfered_slab, drilled_plate,
                               pierced_rounded_box, rounded_prism, rounded_slab,
                               sharp_prism, shelled_tube, smooth_ball,
                               stencil_plate, tapered_boss_plate)
from stylelift import measure
from stylelift.cli import main
from stylelift.emit import lift, render_style_md, render_tokens, sync
from stylelift.measure import Config
from stylelift.report import measurement_text
from stylelift.spec import (BRIDGE_MIN_WIDTHS, GLYPH_MIN_FRACTION,
                            LINE_WIDTH_MM, Status, StyleSpec, conform, derive,
                            snap_fn, verdict)


def save(tmp_path, mesh, name):
    """Export a probe mesh and return its path."""
    path = tmp_path / name
    mesh.export(str(path))
    return str(path)


def prism(profile, depth, lift=0.0):
    """Stand a 2D (across, up) profile upright and extrude it `depth` deep.

    Every face is then either vertical, or a plane whose inclination the
    profile chose, so the expected areas are arithmetic on the profile rather
    than a number read off a previous run. `lift` raises the result clear of
    z=0 when a test needs its downward faces counted rather than treated as
    footprint.
    """
    mesh = trimesh.creation.extrude_polygon(shapely.geometry.Polygon(profile),
                                            height=depth)
    mesh.apply_transform(trimesh.transformations.rotation_matrix(
        math.radians(90), [1, 0, 0]))
    mesh.apply_translation([0, 0, lift - mesh.bounds[0][2]])
    return mesh


def dominant(report):
    """The report's dominant outer radius, or None."""
    return report["edges"]["rounding"]["dominant_r_mm"]


# --------------------------------------------------------------------------
# Edge treatment
# --------------------------------------------------------------------------

def test_sharp_box_has_no_rounding(tmp_path):
    r = measure(save(tmp_path, sharp_prism(), "sharp.stl"))
    assert r["edges"]["softness"] == 0.0
    assert r["edges"]["rounding"]["convex"] == []
    assert r["edges"]["grammar"]["sharp_share"] == pytest.approx(1.0)


def test_rounded_box_recovers_its_radius(tmp_path):
    r = measure(save(tmp_path, rounded_prism(radius=3.0), "round.stl"))
    assert dominant(r) == pytest.approx(3.0, abs=0.01)
    assert r["edges"]["rounding"]["dominant_share"] > 0.9
    assert r["edges"]["rounding"]["implied_fn"] == pytest.approx(64, abs=1)
    assert r["edges"]["softness"] > 0.6
    assert r["edges"]["grammar"]["rounded_share"] > 0.6


@pytest.mark.parametrize("segments,expected_fn", [(4, 16), (8, 32), (32, 128)])
def test_radius_is_independent_of_tessellation(tmp_path, segments, expected_fn):
    # The whole method rests on this: a coarse export and a fine export of the
    # same design must report the same radius, only a different segment count.
    mesh = rounded_prism(radius=3.0, quarter_segments=segments)
    r = measure(save(tmp_path, mesh, f"round{segments}.stl"))
    assert dominant(r) == pytest.approx(3.0, abs=0.02)
    assert r["edges"]["rounding"]["implied_fn"] == pytest.approx(expected_fn, abs=1)


def test_measurements_survive_an_arbitrary_pose(tmp_path):
    # A downloaded STL is in whatever pose it was exported in.
    mesh = rounded_prism(radius=3.0)
    upright = measure(save(tmp_path, mesh, "upright.stl"))
    tumbled = mesh.copy()
    for angle, axis in ((37, [1, 0, 0]), (22, [0, 1, 0]), (61, [0, 0, 1])):
        tumbled.apply_transform(
            trimesh.transformations.rotation_matrix(np.radians(angle), axis))
    tumbled.apply_translation([123.0, -45.0, 7.5])
    rotated = measure(save(tmp_path, tumbled, "tumbled.stl"))
    assert dominant(rotated) == pytest.approx(dominant(upright), abs=0.02)
    assert rotated["edges"]["softness"] == pytest.approx(
        upright["edges"]["softness"], abs=0.01)


def test_radius_scales_with_the_part_but_softness_does_not(tmp_path):
    mesh = rounded_prism(radius=3.0)
    base = measure(save(tmp_path, mesh, "base.stl"))
    big = mesh.copy()
    big.apply_scale(2.5)
    scaled = measure(save(tmp_path, big, "big.stl"))
    assert dominant(scaled) == pytest.approx(7.5, abs=0.05)
    assert scaled["edges"]["softness"] == pytest.approx(
        base["edges"]["softness"], abs=0.01)


def test_chamfer_is_measured_as_a_chamfer_not_a_fillet(tmp_path):
    r = measure(save(tmp_path, chamfered_prism(leg=1.0), "chamfer.stl"))
    assert r["edges"]["chamfers"]["dominant_leg_mm"] == pytest.approx(1.0, abs=0.02)
    assert r["edges"]["chamfers"]["bands"][0]["turn_deg"] == pytest.approx(90, abs=1)
    # a chamfered box is not a soft box: nothing here curves
    assert r["edges"]["rounding"]["convex"] == []
    assert r["edges"]["softness"] == 0.0
    assert r["edges"]["grammar"]["chamfered_share"] > 0.15


@pytest.mark.parametrize("height", [2.0, 3.0, 8.0, 20.0])
def test_a_chamfer_reads_the_same_however_thin_the_plate(tmp_path, height):
    # Regression: chamfer-vs-curve used to be decided by comparing the band
    # against its neighbour's size, so the *same* 0.6 mm chamfer on a thinner
    # plate stopped looking like a chamfer once the wall above it got short —
    # and the part then reported a corner radius (2.12 mm) and a curve
    # resolution ($fn=8) that exist nowhere in it.
    r = measure(save(tmp_path, chamfered_slab(height=height, leg=0.6),
                     f"slab{height}.stl"))
    assert r["edges"]["chamfers"]["dominant_leg_mm"] == pytest.approx(0.6, abs=0.02)
    assert r["edges"]["chamfers"]["count"] == 4
    assert r["edges"]["rounding"]["dominant_r_mm"] is None


def test_a_coarse_curve_is_not_mistaken_for_chamfers(tmp_path):
    # The other side of that coin: an 8-sided cylinder has the same topology as
    # a chamfered box — eight faces meeting at eight 45-degree folds. What
    # separates them is that a chamfer is narrow between wide faces, while a
    # coarse curve's facets are all the same width. Read as chamfers, this
    # would report a 7.6 mm "chamfer leg" and lose the radius entirely.
    for sections in (8, 12, 20):
        barrel = trimesh.creation.cylinder(radius=10.0, height=20.0,
                                           sections=sections)
        r = measure(save(tmp_path, barrel, f"barrel{sections}.stl"))
        assert r["edges"]["chamfers"]["count"] == 0
        assert r["edges"]["form"]["dominant_r_mm"] == pytest.approx(10.0, abs=0.05)


def test_a_tapered_boss_is_not_a_corner_radius(tmp_path):
    # A bar with one plain draft-angled boss contains no fillet at all. The
    # radius identity assumes a cylinder's parallel-sided strip; a cone's strip
    # is a trapezoid, and applying the identity to it reported a 12.7 mm corner
    # radius over 95% of the curved length — a number belonging to no feature
    # of the part.
    r = measure(save(tmp_path, tapered_boss_plate(), "frustum.stl"))
    assert r["edges"]["rounding"]["dominant_r_mm"] is None
    assert r["edges"]["rounding"]["convex"] == []


def test_a_coarse_arc_reports_only_the_radius_it_has(tmp_path):
    # At $fn=8 a 3 mm fillet's strips are wide enough that the tangent fold
    # where the arc meets the flat face passes the width test, and each such
    # fold contributes twice the true radius. The dominant mode was 8.07 mm on
    # a part whose only radius is 3.
    mesh = rounded_prism(width=10, depth=10, height=40, radius=3.0,
                         quarter_segments=2)
    r = measure(save(tmp_path, mesh, "coarse.stl"))
    assert r["edges"]["rounding"]["dominant_r_mm"] == pytest.approx(3.0, abs=0.05)
    assert r["edges"]["rounding"]["dominant_share"] > 0.9


def test_grammar_shares_partition_the_shaped_edges(tmp_path):
    # rounded / chamfered / sharp are shares of one quantity, so they must sum
    # to 1. Adding chamfer length to hard length counted every chamfer's own
    # 45-degree bounding folds twice.
    for name, mesh in (("chamfer", chamfered_prism(leg=1.0)),
                       ("round", rounded_prism(radius=3.0)),
                       ("slab", chamfered_slab(height=8.0, leg=0.6))):
        g = measure(save(tmp_path, mesh, f"{name}.stl"))["edges"]["grammar"]
        assert sum(g.values()) == pytest.approx(1.0, abs=1e-6)


def test_shelled_does_not_depend_on_the_pose_of_the_file(tmp_path):
    # Everything else this tool measures is invariant under rotation; deciding
    # "is this a shell?" from the axis-aligned bounding box made this one metric
    # depend on how the exporter happened to orient the part, and a rotated
    # solid could mint a wall-thickness token for a style.
    for name, mesh, expected in (("tube", shelled_tube(wall=2.4), True),
                                 ("solid", sharp_prism(), False)):
        tumbled = mesh.copy()
        for angle, axis in ((17, [1, 0, 0]), (29, [0, 1, 0]), (41, [0, 0, 1])):
            tumbled.apply_transform(
                trimesh.transformations.rotation_matrix(np.radians(angle), axis))
        upright = measure(save(tmp_path, mesh, f"{name}.stl"))
        rotated = measure(save(tmp_path, tumbled, f"{name}-rot.stl"))
        assert upright["walls"]["shelled"] is expected
        assert rotated["walls"]["shelled"] is expected


def test_edge_rounding_is_kept_apart_from_bores(tmp_path):
    # A part rounded at 6 mm that also has 3.4 mm holes: the corner radius is
    # 6 mm and the holes are features. Averaging the two into "4.7 mm rounding"
    # would hand the next design in the family a radius nothing here uses.
    plate = drilled_plate(height=6.0)
    body = rounded_prism(width=40, depth=30, height=6, radius=6.0)
    r = measure(save(tmp_path, trimesh.util.concatenate([plate, body]), "two.stl"))
    assert r["edges"]["rounding"]["dominant_r_mm"] == pytest.approx(6.0, abs=0.05)
    assert not any(m["r_mm"] == pytest.approx(1.7, abs=0.1)
                   for m in r["edges"]["rounding"]["concave"])
    assert any(f["d_mm"] == pytest.approx(3.4, abs=0.05)
               for f in r["features"]["cylinders"])


def test_a_barrel_is_form_not_a_corner_radius(tmp_path):
    # A plain cylinder has no corner radius to inherit: its 10 mm is the shape
    # itself. A style lifted from it must not claim style_corner_r = 10.
    barrel = trimesh.creation.cylinder(radius=10.0, height=25.0, sections=64)
    r = measure(save(tmp_path, barrel, "barrel.stl"))
    assert r["edges"]["rounding"]["dominant_r_mm"] is None
    assert r["edges"]["form"]["dominant_r_mm"] == pytest.approx(10.0, abs=0.05)
    assert r["edges"]["form"]["convex"][0]["sweep_deg"] == pytest.approx(360, abs=1)


def test_tessellation_style_is_reported(tmp_path):
    # The radius identity is exact on quad strips (what CAD and OpenSCAD
    # export) and reads high on a freely triangulated mesh (what sculpting and
    # remeshing produce). The tool cannot fix the second case, so it has to say
    # which one it is looking at.
    strips = measure(save(tmp_path, rounded_prism(), "strips.stl"))
    assert strips["edges"]["tessellation"] == "strip"

    blob = trimesh.creation.icosphere(subdivisions=3, radius=6.0)
    soup = measure(save(tmp_path, blob, "soup.stl"))
    assert soup["edges"]["tessellation"] == "triangulated"
    # ...and the radius it reports is the known-biased one, not silently
    # "corrected" into a number with no defensible derivation
    assert soup["edges"]["form"]["dominant_r_mm"] == pytest.approx(8.3, abs=0.3)


def test_sweep_tells_an_edge_fillet_from_a_body(tmp_path):
    r = measure(save(tmp_path, rounded_prism(radius=3.0), "round.stl"))
    # four quarter-round vertical edges: each band sweeps about 90 degrees
    assert r["edges"]["rounding"]["convex"][0]["sweep_deg"] == pytest.approx(85, abs=8)


# --------------------------------------------------------------------------
# Features, walls, massing
# --------------------------------------------------------------------------

def test_holes_are_found_with_their_diameter_and_axis(tmp_path):
    r = measure(save(tmp_path, drilled_plate(hole_d=3.4), "plate.stl"))
    holes = [f for f in r["features"]["cylinders"] if f["kind"] == "hole"]
    assert len(holes) == 1                      # one entry, four instances
    assert holes[0]["d_mm"] == pytest.approx(3.4, abs=0.02)
    assert holes[0]["count"] == 4
    assert holes[0]["axis"] == "z"


def test_wall_thickness_of_a_shell(tmp_path):
    r = measure(save(tmp_path, shelled_tube(wall=2.4), "tube.stl"))
    assert r["walls"]["shelled"] is True
    assert r["walls"]["mode_mm"] == pytest.approx(2.4, abs=0.05)


def test_a_solid_block_reports_no_wall(tmp_path):
    # Rays through a solid part measure the part, not a wall; calling that a
    # 15 mm "wall thickness" would poison every style lifted from a solid.
    r = measure(save(tmp_path, sharp_prism(), "solid.stl"))
    assert r["walls"]["shelled"] is False
    assert "radius_to_wall" not in r["ratios"]


def test_a_solid_part_with_a_boss_is_still_not_shelled(tmp_path):
    # A boss makes the bounding box taller than the body, so the rays crossing
    # it return the boss's width as the commonest thickness. Judging "shelled"
    # on that number alone called a 100% solid block a shell and fed its boss
    # diameter into styles as a wall thickness.
    solid = trimesh.util.concatenate([
        trimesh.creation.box(extents=(40, 30, 15)),
        trimesh.creation.cylinder(radius=4, height=20).apply_translation(
            [0, 0, 15])])
    r = measure(save(tmp_path, solid, "boss.stl"))
    assert r["walls"]["shelled"] is False
    assert "radius_to_wall" not in r["ratios"]


def test_massing_and_symmetry(tmp_path):
    r = measure(save(tmp_path, rounded_prism(), "round.stl"))
    assert r["massing"]["bbox_fill"] == pytest.approx(0.99, abs=0.02)
    assert r["massing"]["aspect"][0] == 1.0
    assert all(r["symmetry"][axis] > 0.99 for axis in "xyz")

    lopsided = trimesh.util.concatenate(
        [sharp_prism(), sharp_prism(width=10, depth=10, height=10)])
    asym = measure(save(tmp_path, lopsided, "asym.stl"))
    assert asym["symmetry"]["x"] < 0.95


# --------------------------------------------------------------------------
# Spec: tokens, rules, conformance
# --------------------------------------------------------------------------

@pytest.fixture
def soft_style(tmp_path):
    """A style lifted from the 40x30x15 r=3 reference box."""
    reference = save(tmp_path, rounded_prism(radius=3.0), "reference.stl")
    result = lift([reference], "soft-test", tmp_path / "style",
                  title="Soft Test")
    return result["spec"], tmp_path / "style"


def test_lift_writes_a_usable_pack(soft_style):
    spec, directory = soft_style
    assert (directory / "style.json").exists()
    assert (directory / "style.scad").exists()
    assert (directory / "STYLE.md").exists()
    assert spec.tokens["corner_r"] == pytest.approx(3.0, abs=0.01)
    assert spec.tokens["fn"] == 64
    assert {r["id"] for r in spec.rules} >= {"corner-radius", "soft-edges"}
    scad = (directory / "style.scad").read_text()
    assert "style_corner_r = 3;" in scad
    assert "style_fn = 64;" in scad


def test_lift_refuses_to_clobber_a_tuned_spec(soft_style, tmp_path):
    _, directory = soft_style
    reference = save(tmp_path, rounded_prism(radius=3.0), "ref2.stl")
    with pytest.raises(FileExistsError):
        lift([reference], "soft-test", directory)


def test_a_different_part_in_the_same_language_passes(soft_style, tmp_path):
    spec, _ = soft_style
    # less than half the size, same radius and resolution
    part = save(tmp_path, rounded_slab(), "slab.stl")
    results = conform(measure(part), spec)
    assert verdict(results) in ("IN STYLE", "IN STYLE (with advisories)")
    assert not [r for r in results if r.status is Status.FAIL]


def test_an_off_style_part_fails_with_a_reason(soft_style, tmp_path):
    spec, _ = soft_style
    part = save(tmp_path, rounded_prism(radius=8.0), "fat.stl")
    results = conform(measure(part), spec)
    failed = [r for r in results if r.status is Status.FAIL]
    assert [r.rule for r in failed] == ["corner-radius"]
    assert failed[0].why                      # the report says why it matters
    assert verdict(results) == "OFF-STYLE"


def test_a_coarse_export_fails_the_smoothness_rule(soft_style, tmp_path):
    spec, _ = soft_style
    part = save(tmp_path, rounded_prism(radius=3.0, quarter_segments=3),
                "coarse.stl")
    results = conform(measure(part), spec)
    assert "curve-smoothness" in [r.rule for r in results
                                  if r.status is Status.FAIL]


def test_a_rule_that_cannot_apply_is_skipped_not_failed(soft_style, tmp_path):
    # The sharp box has no rounded edges at all. "Your 3 mm radius is wrong" is
    # a lie about a part that has no radius; the radius rules must skip. The
    # softness rule has no precondition and *should* fail — that is the finding.
    spec, _ = soft_style
    part = save(tmp_path, sharp_prism(), "sharp.stl")
    results = conform(measure(part), spec)
    by_rule = {r.rule: r for r in results}
    assert by_rule["corner-radius"].status is Status.SKIP
    assert by_rule["corner-radius"].detail
    assert by_rule["curve-smoothness"].status is Status.SKIP
    # ...and the softness advisory does flag it, without pretending the radius
    # rules judged anything: with no required rule evaluable, the honest
    # verdict is that the two parts cannot be compared at all.
    assert by_rule["soft-edges"].status is Status.WARN
    assert verdict(results).startswith("NOT COMPARABLE")


def test_advisory_rules_warn_but_do_not_fail(soft_style, tmp_path):
    spec, _ = soft_style
    spec.rules = [
        {"id": "identity", "metric": "edges.rounding.dominant_r_mm",
         "op": "near", "value": 3.0, "tol": 0.35, "severity": "required",
         "why": "the family radius"},
        {"id": "advice", "metric": "edges.softness", "op": "min",
         "value": 0.99, "severity": "advisory", "why": "just saying"},
    ]
    results = conform(measure(save(tmp_path, rounded_prism(), "r.stl")), spec)
    by_rule = {r.rule: r for r in results}
    assert by_rule["identity"].status is Status.PASS
    assert by_rule["advice"].status is Status.WARN
    assert verdict(results) == "IN STYLE (with advisories)"


def test_verdict_when_nothing_is_comparable(soft_style, tmp_path):
    spec, _ = soft_style
    spec.rules = [{"id": "n/a", "metric": "edges.softness", "op": "min",
                   "value": 0.5, "when": {"metric": "edges.rounding."
                                          "dominant_share", "op": "min",
                                          "value": 0.9}}]
    results = conform(measure(save(tmp_path, sharp_prism(), "s.stl")), spec)
    assert verdict(results).startswith("NOT COMPARABLE")


# --------------------------------------------------------------------------
# Pack plumbing
# --------------------------------------------------------------------------

def test_style_scad_is_generated_and_drift_is_caught(soft_style):
    spec, directory = soft_style
    ok, _ = sync(directory, check=True)
    assert ok
    (directory / "style.scad").write_text("style_corner_r = 99;\n")
    ok, message = sync(directory, check=True)
    assert not ok and "stale" in message
    ok, _ = sync(directory)                       # rewrite from style.json
    assert ok
    assert sync(directory, check=True)[0]


def test_spec_roundtrips_through_json(soft_style):
    spec, directory = soft_style
    again = StyleSpec.load(directory / "style.json")
    assert again.tokens == spec.tokens
    assert again.rules == spec.rules
    assert render_tokens(again) == render_tokens(spec)


def test_unknown_schema_is_rejected(tmp_path):
    path = tmp_path / "style.json"
    path.write_text(json.dumps({"schema": "stylelift/style@99", "name": "x"}))
    with pytest.raises(ValueError, match="unsupported schema"):
        StyleSpec.load(path)


# style.json is the one file people hand-edit, so a typo in it is ordinary.
# Every one of these must come back as a ValueError naming the offending rule —
# which cli.main turns into exit 2. Anything that escapes as KeyError,
# AttributeError or TypeError exits 1 instead, and exit 1 is the code that
# means "this part is off-style": the gate would blame the part for a mistake
# in the spec.
BAD_SPECS = {
    "missing name": (lambda d: d.pop("name"), "name"),
    "name not a string": (lambda d: d.update(name=42), "name"),
    "rules not a list": (lambda d: d.update(rules={}), "rules"),
    "rule not an object": (lambda d: d["rules"].append("oops"), "must be an object"),
    "rule missing metric": (lambda d: d["rules"].append({"value": 1}), "metric"),
    "unknown op": (lambda d: d["rules"].append(
        {"metric": "edges.softness", "op": "sideways", "value": 1}), "unknown op"),
    "value not a number": (lambda d: d["rules"].append(
        {"metric": "edges.softness", "value": "lots"}), "must be a number"),
    "range wants two": (lambda d: d["rules"].append(
        {"metric": "edges.softness", "op": "range", "value": [1]}), "low, high"),
    "tol not a number": (lambda d: d["rules"].append(
        {"metric": "edges.softness", "value": 1, "tol": "wide"}), "tol"),
    "when not an object": (lambda d: d["rules"].append(
        {"metric": "edges.softness", "value": 1, "when": "always"}), "when"),
    "when missing value": (lambda d: d["rules"].append(
        {"metric": "edges.softness", "value": 1,
         "when": {"metric": "features.hole_count"}}), "value"),
    "when value not a number": (lambda d: d["rules"].append(
        {"metric": "edges.softness", "value": 1,
         "when": {"metric": "features.hole_count", "value": "some"}}),
        "must be a number"),
    "bad severity": (lambda d: d["rules"].append(
        {"metric": "edges.softness", "value": 1, "severity": "vital"}), "severity"),
    "tokens not an object": (lambda d: d.update(tokens=[1, 2]), "tokens"),
}


@pytest.mark.parametrize("case", sorted(BAD_SPECS))
def test_a_hand_edit_mistake_is_a_named_error_not_a_traceback(soft_style, tmp_path,
                                                              case):
    _, directory = soft_style
    doc = json.loads((directory / "style.json").read_text())
    break_it, expected = BAD_SPECS[case]
    break_it(doc)
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match=expected):
        StyleSpec.load(path)


def test_a_broken_spec_exits_2_not_1(soft_style, tmp_path, capsys):
    # Exit 1 already means "off-style". A spec that cannot be read must not
    # borrow that code, or CI reports a verdict on a part it never judged.
    _, directory = soft_style
    doc = json.loads((directory / "style.json").read_text())
    doc["rules"][0]["when"] = {"metric": "edges.softness", "value": "lots"}
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(doc))
    model = save(tmp_path, rounded_prism(radius=3.0), "part.stl")
    assert main(["check", model, "--style", str(path)]) == 2
    assert "stylelift:" in capsys.readouterr().err


def test_snap_fn_rounds_to_values_a_design_would_write():
    assert snap_fn(63.2) == 64
    assert snap_fn(64.0) == 64
    assert snap_fn(65.0) == 64          # 8% slack absorbs measurement noise
    assert snap_fn(90.0) == 96
    assert snap_fn(None) is None


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_cli_measure_json(tmp_path, capsys):
    path = save(tmp_path, rounded_prism(), "r.stl")
    assert main(["measure", path, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["edges"]["rounding"]["dominant_r_mm"] == pytest.approx(3.0, abs=0.01)


def test_cli_check_exit_codes(tmp_path, capsys):
    reference = save(tmp_path, rounded_prism(radius=3.0), "ref.stl")
    assert main(["lift", reference, "--name", "cli-test",
                 "--out", str(tmp_path / "s")]) == 0
    capsys.readouterr()

    good = save(tmp_path, rounded_slab(), "good.stl")
    assert main(["check", good, "--style", str(tmp_path / "s")]) == 0

    bad = save(tmp_path, rounded_prism(radius=8.0), "bad.stl")
    assert main(["check", bad, "--style", str(tmp_path / "s")]) == 1
    assert "OFF-STYLE" in capsys.readouterr().out

    # --advisory-only reports the same finding without failing a pipeline
    assert main(["check", bad, "--style", str(tmp_path / "s"),
                 "--advisory-only"]) == 0


def test_cli_reports_a_missing_file_without_a_traceback(tmp_path, capsys):
    assert main(["measure", str(tmp_path / "nope.stl")]) == 2
    assert "stylelift:" in capsys.readouterr().err


# --------------------------------------------------------------------------
# orientation.unsupported_share — the share of surface a printer would have to
# support. Truth comparisons: every expected value below is worked out from the
# probe's own dimensions, not copied from a previous run.

def test_a_cube_on_the_bed_needs_no_support(tmp_path):
    """Its one flat downward face is the footprint, which the bed carries."""
    r = measure(save(tmp_path, trimesh.creation.box(extents=[10, 10, 10]),
                     "cube.stl"))
    assert r["orientation"]["unsupported_share"] == pytest.approx(0.0, abs=1e-6)
    assert r["orientation"]["overhang_limit_deg"] == 45.0


def test_a_flat_shoulder_is_measured_as_unsupported(tmp_path):
    """A T-prism overhangs by exactly the two shoulders its cap hangs over.

    Extruded from a T profile rather than unioned from two boxes: a boolean
    needs manifold3d or blender, which the test environment deliberately does
    not carry (see examples/make_probe_models.py). The expected share is
    derived from the profile, not from a previous run.
    """
    post_w, cap_w, post_h, cap_h, depth = 4.0, 12.0, 10.0, 2.0, 8.0
    profile = [(-post_w / 2, 0.0), (post_w / 2, 0.0),
               (post_w / 2, post_h), (cap_w / 2, post_h),
               (cap_w / 2, post_h + cap_h), (-cap_w / 2, post_h + cap_h),
               (-cap_w / 2, post_h), (-post_w / 2, post_h)]
    tee = prism(profile, depth)
    shoulder = (cap_w - post_w) * depth             # two ledges under the cap
    # total from the profile, not from the mesh: a prism's surface is its
    # perimeter swept plus its two ends
    poly = shapely.geometry.Polygon(profile)
    total = poly.length * depth + 2 * poly.area
    assert tee.area == pytest.approx(total, rel=1e-6)
    r = measure(save(tmp_path, tee, "tee.stl"))
    assert r["orientation"]["unsupported_share"] == pytest.approx(
        shoulder / total, abs=1e-4)


@pytest.mark.parametrize("slope_deg,supported", [(60.0, True), (30.0, False)])
def test_the_limit_falls_between_a_steep_and_a_shallow_roof(tmp_path, slope_deg,
                                                            supported):
    """A roof steeper than 45 deg from the bed prints; a shallower one does not.

    Built as a prism whose downward faces sit at a chosen angle, so the pass and
    the fail come from the same generator with one number changed.
    """
    run, rise = 10.0, 10.0 * math.tan(math.radians(slope_deg))
    # a tent: two downward-facing roof planes at slope_deg from horizontal,
    # raised clear of the bed so nothing is excluded as footprint
    tent = prism([(-run, rise), (0.0, 0.0), (run, rise),
                  (run, rise + 5.0), (-run, rise + 5.0)], 8.0, lift=1.0)
    share = measure(save(tmp_path, tent, "tent.stl"))["orientation"][
        "unsupported_share"]
    if supported:
        assert share == pytest.approx(0.0, abs=1e-6)
    else:
        assert share > 0.1


def test_unsupported_share_is_addressable_by_a_rule(tmp_path):
    """dominant_slopes is a list, so a style cannot point a rule at it.

    unsupported_share exists to be that scalar; this fails if it stops being
    one, which would silently turn any rule using it into NOT COMPARABLE.
    """
    from stylelift.spec import dig
    r = measure(save(tmp_path, trimesh.creation.box(extents=[8, 8, 8]),
                     "b.stl"))
    assert isinstance(dig(r, "orientation.unsupported_share"), float)
    assert dig(r, "orientation.dominant_slopes.0.angle_deg") is None


# --------------------------------------------------------------------------
# The faceted, cut-through look: dihedral sharpness, openness, legibility
# --------------------------------------------------------------------------

def test_the_smooth_solid_fixture_earns_no_facet_and_no_void(tmp_path):
    """Negative control for both new metrics at once.

    A sphere has no decided edge and no cut-through: every fold it has is one
    segment of its own tessellation, and its coarsest folds still turn 11.25
    degrees. A sharpness metric that credits those folds is reading angles
    rather than design; a void metric that finds openness here is reading
    noise.
    """
    r = measure(save(tmp_path, smooth_ball(), "ball.stl"))
    facet, open_ = r["edges"]["facetedness"], r["openness"]
    assert facet["sharpness"] == pytest.approx(0.0, abs=1e-6)
    assert facet["fn_curve"] == pytest.approx(32, abs=2)
    assert all(not b["facet"] for b in facet["histogram"])
    assert open_["measured"] is True
    assert open_["void_fraction"] == pytest.approx(0.0, abs=1e-6)
    assert open_["views_with_void"] == 0
    assert open_["max_void_span_mm"] == pytest.approx(0.0, abs=1e-6)


def test_the_stencil_plate_is_all_facet_and_open(tmp_path):
    """Positive control: the faceted, cut-through look, with every number
    arithmetic on the builder's arguments."""
    r = measure(save(tmp_path, stencil_plate(), "stencil.stl"))
    facet, open_ = r["edges"]["facetedness"], r["openness"]
    # Nothing curved was drawn, so nothing is explained as tessellation: the
    # 45-degree outline chamfers and the 90-degree slot corners are all design.
    assert facet["fn_curve"] is None
    assert facet["tessellation_turn_deg"] == pytest.approx(
        1.1 * 360.0 / 48.0, abs=0.1)
    assert facet["sharpness"] == pytest.approx(1.0, abs=0.05)
    facet_share = sum(b["share"] for b in facet["histogram"] if b["facet"])
    assert facet_share > 0.9
    assert open_["void_fraction"] > 0.05
    assert open_["views_with_void"] > 0
    assert open_["min_bridge_mm"] == pytest.approx(4.0, abs=0.05)


def test_sharpness_normalizes_against_the_meshs_own_fn(tmp_path):
    """The coarse-$fn negative control: the same 45-degree folds, opposite
    verdicts.

    A rounded box whose corners are drawn at $fn=8 turns 45-degree curve
    folds — exactly the turn the stencil plate's outline makes. Here they are
    tessellation, because the mesh's finest curve explains every one of them,
    and the facet length is the top and bottom rims alone. Pierce the same
    box with a $fn=64 bore and the finest curve is finer than the fold, so
    those very folds become design facets. A fixed shallow-angle cutoff
    cannot produce this flip; normalizing against declared $fn can.
    """
    coarse = measure(save(tmp_path, pierced_rounded_box(bore_d=0.0),
                          "coarse.stl"))["edges"]["facetedness"]
    assert coarse["fn_curve"] == pytest.approx(8.0, abs=0.5)
    assert coarse["tessellation_turn_deg"] == pytest.approx(1.1 * 45.0, abs=1.0)
    # rims only: 2 x the rounded rectangle's perimeter, 2*(w-2r) + 2*(d-2r)
    # + 2*pi*r, is the arithmetic the builder's arguments predict
    perimeter = 2 * (40.0 - 6.0) + 2 * (30.0 - 6.0) + 2 * math.pi * 3.0
    assert coarse["facet_length_mm"] == pytest.approx(2 * perimeter, rel=0.01)
    assert next(b for b in coarse["histogram"]
                if b["lo_deg"] == 35)["facet"] is False

    pierced = measure(save(tmp_path, pierced_rounded_box(),
                           "pierced.stl"))["edges"]["facetedness"]
    assert pierced["fn_curve"] == pytest.approx(64.0, abs=2.0)
    assert next(b for b in pierced["histogram"]
                if b["lo_deg"] == 35)["facet"] is True
    assert pierced["facet_length_mm"] > coarse["facet_length_mm"]


def test_void_fraction_is_pose_stable_and_the_estimate_knows_it(tmp_path):
    """Rotating the part permutes the view directions and changes nothing.

    The tolerance is the Fibonacci lattice's sampling error, not pose
    dependence — and the second half proves that reading: growing the
    direction count shrinks the spread, which a pose-dependent measurement
    would not.
    """
    paths = []
    for k, rot in enumerate([(30, 40, 50), (77, 13, 201), (111, 227, 64),
                             (255, 255, 0), (7, 333, 17)]):
        mesh = stencil_plate()
        axis = np.array(rot, float)
        mesh.apply_transform(trimesh.transformations.rotation_matrix(
            math.radians(float(np.linalg.norm(axis))),
            axis / np.linalg.norm(axis)))
        paths.append(save(tmp_path, mesh, f"rot{k}.stl"))
    vals = [measure(p)["openness"]["void_fraction"] for p in paths]
    assert max(vals) - min(vals) <= 0.03

    fine = [measure(p, Config(void_dirs=192))["openness"]["void_fraction"]
            for p in paths]
    assert max(fine) - min(fine) <= 0.01
    assert max(fine) - min(fine) < max(vals) - min(vals)


def test_glyphs_too_small_to_read_measure_below_the_legibility_bound(tmp_path):
    """The glyph half of the legibility rule, as a measurement.

    A 2 mm slot on a 60 mm part is a mark nobody reads; its largest open
    channel stays under 15% of the part even though a ray threads the slot's
    depth. (The span is the longest chord of a void region, so a deep slot
    measures its depth — the rule bounds read scale, and a pack wanting the
    aperture too has `min_bridge_mm` beside it.)
    """
    r = measure(save(tmp_path, stencil_plate(slot_w=2.0, slot_h=2.0),
                     "tiny.stl"))
    assert r["openness"]["max_void_span_fraction"] < GLYPH_MIN_FRACTION


def test_a_web_too_thin_to_print_measures_as_one(tmp_path):
    """The bridge half of the legibility rule, as a measurement: the same
    plate with the web dropped below two extrusion lines."""
    r = measure(save(tmp_path, stencil_plate(web=0.5), "thin.stl"))
    assert r["openness"]["min_bridge_mm"] == pytest.approx(0.5, abs=0.02)


def test_openness_declares_itself_unmeasured_on_a_leaky_mesh(tmp_path):
    """A non-watertight mesh has no inside, so line crossing counts mean
    nothing; the metric says so instead of reporting a number."""
    box = trimesh.creation.box(extents=[10, 10, 10])
    box.update_faces(np.arange(len(box.faces)) != 0)
    r = measure(save(tmp_path, box, "leaky.stl"))
    assert r["openness"]["measured"] is False
    assert r["openness"]["reason"]
    assert "void_fraction" not in r["openness"]
    # ...and a rule over the metric skips rather than fails the part
    spec = StyleSpec(name="s", rules=[{
        "id": "openness", "metric": "openness.void_fraction",
        "op": "min", "value": 0.05, "severity": "required"}])
    result = conform(r, spec)[0]
    assert result.status is Status.SKIP


def test_a_cut_through_reference_proposes_the_legibility_pair(tmp_path):
    """A style lifted from a cut-through reference carries the legibility rule
    as required rules, with the constants the issue states."""
    r = measure(save(tmp_path, stencil_plate(), "ref.stl"))
    tokens, rules = derive(r, "stencil-test")
    by_id = {rule["id"]: rule for rule in rules}

    glyph = by_id["legible-glyph"]
    assert glyph["metric"] == "openness.max_void_span_fraction"
    assert glyph["value"] == GLYPH_MIN_FRACTION
    assert glyph["severity"] == "required"
    assert glyph["when"] == {"metric": "openness.max_void_span_mm",
                             "op": "min", "value": 0.01}
    bridge = by_id["bridge-width"]
    assert bridge["metric"] == "openness.min_bridge_mm"
    assert bridge["value"] == pytest.approx(BRIDGE_MIN_WIDTHS * LINE_WIDTH_MM)
    assert bridge["severity"] == "required"
    assert by_id["facet-sharpness"]["metric"] == "edges.facetedness.sharpness"
    assert tokens["void_fraction"] == pytest.approx(
        r["openness"]["void_fraction"], abs=5e-4)


def test_a_solid_reference_proposes_no_legibility_rules(tmp_path):
    """A smooth solid family gets the mirrored proposals — a facet ceiling and
    a closed form — and never rules about glyphs it does not have."""
    r = measure(save(tmp_path, smooth_ball(), "ball.stl"))
    tokens, rules = derive(r, "smooth-test")
    ids = {rule["id"] for rule in rules}
    assert "legible-glyph" not in ids
    assert "bridge-width" not in ids
    assert "closed-form" in ids
    assert "no-design-facets" in ids
    # and the mirrored family holds its own reference to it — though only
    # advisory and when-gated rules apply, so the verdict is honestly "there
    # is nothing required here to compare" rather than a pass
    results = conform(r, StyleSpec(name="smooth-test", tokens=tokens,
                                   rules=rules))
    assert verdict(results).startswith("NOT COMPARABLE")


def test_check_separates_the_fixtures_by_the_new_rules(tmp_path, capsys):
    """AC3 end to end: one pack lifted from the stencil reference passes the
    conforming fixture and fails each breaker for its own reason."""
    ref = save(tmp_path, stencil_plate(), "ref.stl")
    pack = tmp_path / "pack"
    lift([ref], "stencil-test", pack)

    expect = {"ok.stl": (0, "IN STYLE"),
              "tiny.stl": (1, "OFF-STYLE"),
              "thin.stl": (1, "OFF-STYLE"),
              "ball.stl": (1, "NOT COMPARABLE")}
    meshes = {"ok.stl": stencil_plate(),
              "tiny.stl": stencil_plate(slot_w=2.0, slot_h=2.0),
              "thin.stl": stencil_plate(web=0.5),
              "ball.stl": smooth_ball()}
    for name, mesh in meshes.items():
        path = save(tmp_path, mesh, name)
        rc = main(["check", path, "--style", str(pack)])
        out = capsys.readouterr().out
        want_rc, want_verdict = expect[name]
        assert rc == want_rc, f"{name}: exit {rc}, wanted {want_rc}\n{out}"
        assert want_verdict in out, f"{name}: verdict missing\n{out}"

    # and the JSON surface names which rule broke, for the two real failures
    assert main(["check", save(tmp_path, meshes["tiny.stl"], "tiny2.stl"),
                 "--style", str(pack), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    broken = {r["rule"] for r in payload["results"] if r["status"] == "fail"}
    assert broken == {"legible-glyph"}
    assert main(["check", save(tmp_path, meshes["thin.stl"], "thin2.stl"),
                 "--style", str(pack), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    broken = {r["rule"] for r in payload["results"] if r["status"] == "fail"}
    assert broken == {"bridge-width"}


def test_the_new_metrics_reach_the_report_and_pack_surfaces(tmp_path):
    """measure + report + emit are the surfaces the issue names: the numbers
    must be legible in the text report and carried into a lifted pack."""
    path = save(tmp_path, stencil_plate(), "stencil.stl")
    text = measurement_text(measure(path))
    assert "FACETEDNESS" in text and "sharpness" in text
    assert "OPENNESS" in text and "void fraction" in text
    assert "narrowest bridge" in text

    pack = tmp_path / "pack"
    spec = lift([path], "stencil-test", pack)["spec"]
    markdown = render_style_md(spec)
    assert "Facet sharpness" in markdown
    assert "Void fraction" in markdown
    assert "Narrowest bridge" in markdown
    # both are targets the checker compares against, not numbers to build with
    assert "style_sharpness" not in render_tokens(spec)
