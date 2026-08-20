"""End-to-end tests: build known-good and known-bad meshes, assert the
checker flags exactly the problems each one has."""

import numpy as np
import pytest
import trimesh

from printcheck import analyze
from printcheck.checks import Config
from printcheck.report import Severity


def _save(tmp_path, mesh, name):
    path = tmp_path / name
    mesh.export(str(path))
    return path


def _titles(report, severity=None):
    return [f.title for f in report.findings
            if severity is None or f.severity is severity]


def test_clean_cube_scores_high(tmp_path):
    cube = trimesh.creation.box(extents=(20, 20, 20))
    report = analyze(_save(tmp_path, cube, "cube.stl"))
    assert report.mesh_summary["watertight"]
    assert report.verdict == "PRINTABLE"
    assert report.score == 100


def test_open_mesh_is_critical(tmp_path):
    cube = trimesh.creation.box(extents=(20, 20, 20))
    cube.faces = cube.faces[:-2]  # rip a hole in it
    report = analyze(_save(tmp_path, cube, "open.stl"))
    assert report.verdict == "NOT PRINTABLE AS-IS"
    assert any("watertight" in t for t in _titles(report, Severity.CRITICAL))


def test_overhang_detected_and_orientation_fixes_it(tmp_path):
    # A 'table': flat slab on a thin center column — big ceiling overhang.
    slab = trimesh.creation.box(extents=(40, 40, 4))
    slab.apply_translation([0, 0, 20 + 2])
    leg = trimesh.creation.cylinder(radius=3, height=20)
    leg.apply_translation([0, 0, 10])
    table = trimesh.util.concatenate([slab, leg])
    report = analyze(_save(tmp_path, table, "table.stl"))
    assert any(f.check == "overhangs" for f in report.findings)
    # Flipping it upside down puts the slab on the plate: advisor should see it.
    assert report.orientation_hint["best"] != "current"


def _arch(gap, depth=10.0, h=12.0, foot=4.0, ceiling_z=6.0):
    """An inverted-U prism: two feet on the plate, a flat ceiling of width
    `gap` bridging between them at z=ceiling_z. The ceiling is the only
    unsupported downward face, so `gap` is exactly the unsupported span."""
    from shapely.geometry import Polygon
    w = gap + 2 * foot
    profile = [(-w / 2, 0), (-gap / 2, 0), (-gap / 2, ceiling_z),
               (gap / 2, ceiling_z), (gap / 2, 0), (w / 2, 0),
               (w / 2, h), (-w / 2, h)]
    # extrude_polygon lays the profile in XY and extrudes +Z; rotate so the
    # profile stands in XZ (ceiling faces -Z) and the extrusion runs along Y,
    # then rest it on the plate.
    mesh = trimesh.creation.extrude_polygon(Polygon(profile), depth)
    mesh.apply_transform(
        trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    mesh.apply_translation([0, 0, -mesh.bounds[0][2]])
    return mesh


def test_narrow_bridge_is_not_counted_as_overhang(tmp_path):
    # A 2 mm ceiling bridges without support: no overhang finding (score 100).
    arch = _arch(gap=2.0)
    report = analyze(_save(tmp_path, arch, "bridge.stl"))
    assert not any(f.check == "overhangs" for f in report.findings)
    assert report.score == 100


def test_wide_ceiling_is_counted_as_overhang(tmp_path):
    # The same shape with a 14 mm span is too wide to bridge: still flagged,
    # and the metrics report the full bridgeable split.
    arch = _arch(gap=14.0)
    report = analyze(_save(tmp_path, arch, "wide.stl"))
    oh = [f for f in report.findings if f.check == "overhangs"]
    assert oh, "a 14 mm unsupported ceiling must still need support"
    assert oh[0].metrics["overhang_area_mm2"] > 0
    assert "raw_overhang_area_mm2" in oh[0].metrics
    # nothing bridges here, and the bridge budget is reported for provenance
    assert oh[0].metrics["bridgeable_area_mm2"] == 0
    assert oh[0].metrics["bridge_max_mm"] == 5.0


def _tri_ceiling(side, h=8.0, thick=2.0):
    """An equilateral-triangle slab (side `side`) held at height h on a thin
    central column, so its whole triangular underside is one downward overhang
    region — a *solid* ceiling, unlike the thin strokes _arch builds."""
    from shapely.geometry import Polygon
    import math
    R = side / math.sqrt(3)  # circumradius; vertices of an equilateral triangle
    verts = [(R * math.cos(a), R * math.sin(a))
             for a in (math.pi / 2, math.pi / 2 + 2 * math.pi / 3,
                       math.pi / 2 + 4 * math.pi / 3)]
    slab = trimesh.creation.extrude_polygon(Polygon(verts), thick)
    slab.apply_translation([0, 0, h])
    col = trimesh.creation.cylinder(radius=0.8, height=h)
    col.apply_translation([0, 0, h / 2])
    return trimesh.util.concatenate([slab, col])


def test_solid_triangle_ceiling_needs_support(tmp_path):
    # An 8 mm equilateral solid ceiling: its inradius (2.31 mm) erodes away, but
    # its shortest straight bridge is ~6.9 mm — a plain erosion test would clear
    # it wrongly. The shape-aware (hull min-width) branch must still flag it.
    tri = _tri_ceiling(side=8.0)
    report = analyze(_save(tmp_path, tri, "tri8.stl"))
    assert any(f.check == "overhangs" for f in report.findings), \
        "a solid 8 mm triangular ceiling spans too far to bridge"


def test_small_triangle_ceiling_bridges(tmp_path):
    # A 3 mm equilateral ceiling spans < 5 mm in every direction: bridgeable,
    # so the shape-aware branch must not over-flag small solid features.
    tri = _tri_ceiling(side=3.0)
    report = analyze(_save(tmp_path, tri, "tri3.stl"))
    assert not any(f.check == "overhangs" for f in report.findings)


def _ring_ceiling(outer=8.0, width=1.4, h=8.0, thick=2.0):
    """A thin annular slab on a thin column — a downward ring whose stroke is
    `width` mm wide but whose overall diameter is large. It must stay bridgeable
    (short local bridges across the stroke), proving the compact-blob fix did
    not regress the thin-ring exemption."""
    from shapely.geometry import Point
    ring = Point(0, 0).buffer(outer).difference(Point(0, 0).buffer(outer - width))
    slab = trimesh.creation.extrude_polygon(ring, thick)
    slab.apply_translation([0, 0, h])
    col = trimesh.creation.cylinder(radius=0.6, height=h)
    col.apply_translation([outer - width / 2, 0, h / 2])  # under the stroke
    return trimesh.util.concatenate([slab, col])


def test_thin_ring_ceiling_bridges(tmp_path):
    # A wide-diameter but thin-stroked ring: erodes away, elongated (low
    # compactness), so it stays bridgeable — the case a naive min-width test
    # would wrongly flag.
    ring = _ring_ceiling()
    report = analyze(_save(tmp_path, ring, "ring.stl"))
    assert not any(f.check == "overhangs" for f in report.findings)


def test_bridge_threshold_is_configurable(tmp_path):
    # The same 8 mm ceiling flips from support-needing to bridgeable when the
    # bridge budget is raised past it — proving the knob drives the exemption.
    arch = _arch(gap=8.0)
    path = _save(tmp_path, arch, "arch8.stl")
    strict = analyze(path, Config(bridge_max_mm=5.0))
    lenient = analyze(path, Config(bridge_max_mm=12.0))
    assert any(f.check == "overhangs" for f in strict.findings)
    assert not any(f.check == "overhangs" for f in lenient.findings)


def test_thin_walls_flagged(tmp_path):
    shell = trimesh.creation.box(extents=(30, 30, 0.4))
    shell.apply_translation([0, 0, 5])
    base = trimesh.creation.box(extents=(30, 30, 2))
    wall = trimesh.util.concatenate([base, shell])
    report = analyze(_save(tmp_path, wall, "thin.stl"))
    assert any(f.check == "walls" for f in report.findings)


def test_oversize_and_tiny(tmp_path):
    big = trimesh.creation.box(extents=(300, 50, 50))
    r = analyze(_save(tmp_path, big, "big.stl"))
    assert any("build volume" in t for t in _titles(r))

    tiny = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    r = analyze(_save(tmp_path, tiny, "tiny.stl"))
    assert any("microscopic" in t for t in _titles(r, Severity.CRITICAL))


def test_sphere_contact_warned(tmp_path):
    # Sphere resting on the plate: tiny contact disc -> at least a warning.
    ball = trimesh.creation.icosphere(subdivisions=3, radius=10)
    report = analyze(_save(tmp_path, ball, "ball.stl"))
    assert any(f.check == "stability" for f in report.findings)


def test_point_contact_is_critical(tmp_path):
    # Cone balanced on its tip: genuine point contact -> critical.
    cone = trimesh.creation.cone(radius=10, height=20)
    cone.apply_transform(
        trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    report = analyze(_save(tmp_path, cone, "cone.stl"))
    assert any(f.check == "stability" and f.severity is Severity.CRITICAL
               for f in report.findings)


def test_json_roundtrip(tmp_path):
    cube = trimesh.creation.box(extents=(10, 10, 10))
    report = analyze(_save(tmp_path, cube, "cube.stl"))
    d = report.to_dict()
    assert d["score"] == report.score
    assert d["verdict"] == "PRINTABLE"
    assert isinstance(d["findings"], list)


def test_cli(tmp_path, capsys):
    from printcheck.cli import main
    cube = trimesh.creation.box(extents=(10, 10, 10))
    path = _save(tmp_path, cube, "cube.stl")
    assert main([str(path)]) == 0
    assert "SCORE: 100/100" in capsys.readouterr().out

    bad = trimesh.creation.box(extents=(10, 10, 10))
    bad.faces = bad.faces[:-2]
    badpath = _save(tmp_path, bad, "bad.stl")
    assert main([str(badpath)]) == 1


def test_invalid_numeric_args_rejected(tmp_path):
    from printcheck.cli import main
    cube = trimesh.creation.box(extents=(10, 10, 10))
    path = _save(tmp_path, cube, "cube.stl")
    for bad in (["--nozzle", "0"], ["--nozzle", "-0.4"],
                ["--layer-height", "nan"], ["--min-wall", "inf"],
                ["--overhang-angle", "95"]):
        with pytest.raises(SystemExit) as exc:
            main([str(path), *bad])
        assert exc.value.code == 2


def test_fail_under_gate(tmp_path):
    from printcheck.cli import main
    ball = trimesh.creation.icosphere(subdivisions=3, radius=10)
    path = _save(tmp_path, ball, "ball.stl")
    assert main([str(path), "--fail-under", "90", "--json"]) == 1


def test_repair_unions_overlapping_shells(tmp_path):
    # Two overlapping cubes concatenated without a union: the classic
    # "shells concatenated instead of boolean-unioned" export mistake.
    a = trimesh.creation.box(extents=(10, 10, 10))
    a.apply_translation((5, 5, 5))
    b = a.copy()
    b.apply_translation((5, 5, 0))
    bad = trimesh.util.concatenate([a, b])

    from printcheck.repair import repair
    bad.merge_vertices()
    result = repair(bad)
    assert result.mesh is not None, result.note
    assert result.mesh.is_watertight
    assert result.mesh.body_count == 1
    # union volume: 1000 + 1000 - (5*5*10 overlap) = 1750
    assert abs(float(result.mesh.volume) - 1750.0) < 1.0


def test_repair_cli_writes_artifact_and_keeps_exit_code(tmp_path, capsys):
    from printcheck.cli import main
    a = trimesh.creation.box(extents=(10, 10, 10))
    a.apply_translation((5, 5, 5))
    b = a.copy()
    b.apply_translation((5, 5, 0))
    # Duplicate overlapping shells trip the integrity checks (multi-body
    # overlap is reported non-INFO), so --repair kicks in.
    bad = trimesh.util.concatenate([a, b])
    path = _save(tmp_path, bad, "bad-union.stl")

    code = main([str(path), "--repair"])
    out = capsys.readouterr().out
    repaired = tmp_path / "bad-union.repaired.stl"
    assert "repair: wrote" in out
    assert repaired.exists()
    fixed = trimesh.load(str(repaired))
    fixed.merge_vertices()
    assert fixed.is_watertight
    assert fixed.body_count == 1
    # Exit code always reflects the ORIGINAL mesh, repaired or not.
    assert code == main([str(path)])


def test_repair_skips_clean_plate_of_parts(tmp_path, capsys):
    from printcheck.cli import main
    # Two separate, clean parts on a plate: INFO-level multi-body only —
    # --repair must NOT weld them together.
    a = trimesh.creation.box(extents=(10, 10, 10))
    b = trimesh.creation.box(extents=(10, 10, 10))
    b.apply_translation((30, 0, 0))
    plate = trimesh.util.concatenate([a, b])
    path = _save(tmp_path, plate, "plate.stl")
    main([str(path), "--repair"])
    assert not (tmp_path / "plate.repaired.stl").exists()


def test_nonmanifold_location_reported(tmp_path):
    # Two cubes sharing one full edge: 4 faces on the shared edge.
    a = trimesh.creation.box(extents=(10, 10, 10))
    a.apply_translation((5, 5, 5))
    b = a.copy()
    b.apply_translation((10, 10, 0))
    bad = trimesh.util.concatenate([a, b])
    report = analyze(_save(tmp_path, bad, "kiss.stl"))
    f = next(f for f in report.findings if "watertight" in f.title)
    assert "cluster at (mm)" in f.detail
    assert "near (10, 10," in f.detail
