"""The assembly + verdict: whole-object checks on real STL fixtures, each
asserted against hand-derived physics.

The falsifiable pair the gate's --selftest and the issue's acceptance both
turn on: a stable configuration passes AND a configuration whose CoG falls
outside its footprint is flagged. Without the failing half the check is
worthless (issue #37) — it would report "stable" for everything, including
the two-heavy-spheres-on-thin-stalks shape it exists to catch.
"""

from pathlib import Path

import pytest

from cogcheck.conf import parse
from cogcheck.verdict import STABLE, TIP_RISK, AssemblyError, assemble
from conftest import write_ascii_stl, write_box


@pytest.fixture
def stl_dir(tmp_path: Path) -> Path:
    return tmp_path


MANIFEST_STABLE = (
    "# a 20x20x10 base centred on the origin: volume 4000 mm³ -> 4.96 g at\n"
    "# density 1.24, CoG at (0,0,5), footprint the full 20x20 square —\n"
    "# 10 mm of margin on every side.\n"
    "margin: 2\n"
    "part: base.stl | density: 1.24\n"
)


def _write_centred_base(d: Path) -> None:
    write_box(d / "base.stl", -10, -10, 0, 10, 10, 10)


def test_stable_configuration_passes(stl_dir: Path):
    _write_centred_base(stl_dir)
    m = parse(MANIFEST_STABLE)
    r = assemble(m, stl_dir=stl_dir)
    assert r.verdict == STABLE
    # Hand-derived: box volume 20*20*10 = 4000 mm³ = 4 cm³, density 1.24
    # g/cm³ -> 4.96 g.
    assert r.total_mass_g == pytest.approx(4.96)
    assert r.cog == pytest.approx((0.0, 0.0, 5.0), abs=1e-9)
    # Footprint is the full square: 400 mm², CoG projection dead centre.
    assert r.footprint_area_mm2 == pytest.approx(400.0)
    assert r.margin_left == pytest.approx(10.0)
    assert not r.footprint_degenerate


def test_tip_over_configuration_is_flagged(stl_dir: Path):
    """The negative control: a heavy cantilevered mass pulls the CoG outside
    the footprint, and the check MUST fire. Base 4.96 g at x=0; boom 19.84 g
    (4x) at x=15 -> CoG x = 297.6/24.8 = 12.0 > 10, i.e. 2 mm outside."""
    _write_centred_base(stl_dir)
    m = parse(
        "margin: 2\n"
        "part: base.stl | density: 1.24\n"
        "mass: boom | grams: 19.84 | at: 15,0,20\n"
    )
    r = assemble(m, stl_dir=stl_dir)
    assert r.verdict == TIP_RISK
    assert r.cog[0] == pytest.approx(12.0, abs=1e-9)
    assert r.margin_left == pytest.approx(-2.0, abs=1e-9)
    assert "OUTSIDE" in r.detail


def test_marginal_configuration_flags_under_margin(stl_dir: Path):
    """CoG inside the footprint but under the declared margin: still a risk
    (one desk bump from tipping). Equal 4.96 g masses at x=0 and x=10 put
    the CoG at x=5 -> 5 mm inside the footprint, under the 6 mm margin."""
    _write_centred_base(stl_dir)
    m = parse(
        "margin: 6\n"
        "part: base.stl | density: 1.24\n"
        "mass: boom | grams: 4.96 | at: 10,0,10\n"
    )
    r = assemble(m, stl_dir=stl_dir)
    assert r.cog[0] == pytest.approx(5.0, abs=1e-9)
    assert r.verdict == TIP_RISK
    assert "margin" in r.detail


def test_two_part_composite_cog_is_mass_weighted_mean(stl_dir: Path):
    """Two identical boxes, one translated +20 in x: equal masses put the
    assembly CoG exactly between them — the analytic two-body control."""
    write_box(stl_dir / "a.stl", 0, 0, 0, 10, 10, 10)
    write_box(stl_dir / "b.stl", 0, 0, 0, 10, 10, 10)  # same shape, placed by transform
    m = parse(
        "part: a.stl | density: 1.0\n"
        "part: b.stl | density: 1.0 | translate: 20,0,0\n"
    )
    r = assemble(m, stl_dir=stl_dir)
    assert r.cog == pytest.approx((15.0, 5.0, 5.0), abs=1e-9)
    assert r.verdict == STABLE  # footprint now spans x=0..30, CoG central


def test_point_mass_dominance_math(stl_dir: Path):
    """1.24 g at (5,5,5) plus 4.96 g at (5,5,30): CoG z = 155/6.2 = 25
    exactly — the arithmetic a non-printed mass exists to contribute."""
    write_box(stl_dir / "a.stl", 0, 0, 0, 10, 10, 10)
    m = parse(
        "part: a.stl | density: 1.24\n"
        "mass: ballast | grams: 4.96 | at: 5,5,30\n"
    )
    r = assemble(m, stl_dir=stl_dir)
    assert r.cog == pytest.approx((5.0, 5.0, 25.0), abs=1e-9)


def test_rotated_part_cog_and_contact_move(stl_dir: Path):
    """A part modelled flat but assembled on its side: a 90° z-rotation
    moves centroid and contact with it — the standing frame is the
    manifest's, never the print orientation's."""
    write_box(stl_dir / "a.stl", 0, 0, 0, 30, 10, 10)
    m = parse("part: a.stl | density: 1.0 | rotate: 0,0,90\n")
    r = assemble(m, stl_dir=stl_dir)
    # Centroid (15,5,5) rotated by Rz(90) -> (-5,15,5).
    assert r.cog == pytest.approx((-5.0, 15.0, 5.0), abs=1e-9)
    # Footprint: the 30x10 footprint rotates to 10x30.
    assert r.footprint_area_mm2 == pytest.approx(300.0)
    assert r.verdict == STABLE


def test_degenerate_footprint_flagged(stl_dir: Path):
    """A prism standing on one edge: the contact geometry is collinear, the
    hull degenerates to a segment, and the verdict says so instead of
    computing a distance along a line."""
    from conftest import box_triangles

    # A box rotated 45° about x stands on one edge: its lowest vertices are
    # the two ends of the former front-bottom edge, collinear along y.
    write_ascii_stl(stl_dir / "wedge.stl", box_triangles(-10, -10, 0, 10, 10, 10))
    m = parse("part: wedge.stl | density: 1.0 | rotate: 45,0,0\n")
    r = assemble(m, stl_dir=stl_dir)
    assert r.footprint_degenerate
    assert r.verdict == TIP_RISK
    assert "degenerate" in r.detail


def test_tilted_parts_share_one_ground(stl_dir: Path):
    """Two parts at different heights: the ground is the assembly's lowest
    vertex, and only the part that reaches it contributes contact."""
    write_box(stl_dir / "grounded.stl", -10, -10, 0, 10, 10, 10)
    write_box(stl_dir / "floating.stl", 0, 0, 0, 10, 10, 10)
    m = parse(
        "part: grounded.stl | density: 1.0\n"
        "part: floating.stl | density: 1.0 | translate: 0,0,50\n"
    )
    r = assemble(m, stl_dir=stl_dir)
    assert r.ground_z == pytest.approx(0.0, abs=1e-9)
    assert r.footprint_area_mm2 == pytest.approx(400.0)  # only grounded.stl


def test_missing_stl_fails_loudly(stl_dir: Path):
    m = parse("part: ghost.stl | density: 1.24\n")
    with pytest.raises(AssemblyError, match="ghost.stl"):
        assemble(m, stl_dir=stl_dir)


def test_garbage_stl_fails_loudly(stl_dir: Path):
    (stl_dir / "junk.stl").write_text("not an stl\n", encoding="utf-8")
    m = parse("part: junk.stl | density: 1.24\n")
    with pytest.raises(AssemblyError, match="junk.stl"):
        assemble(m, stl_dir=stl_dir)


def test_open_mesh_part_fails_loudly(stl_dir: Path):
    """A single triangle is not a measurable solid: refused by name."""
    write_ascii_stl(stl_dir / "open.stl", [((0, 0, 0), (10, 0, 0), (0, 10, 0))])
    m = parse("part: open.stl | density: 1.24\n")
    with pytest.raises(AssemblyError, match="open.stl"):
        assemble(m, stl_dir=stl_dir)
