"""The hull predicates the verdict rests on — each pinned against
hand-computed geometry, with the degenerate cases the verdict must not
quietly arithmetic its way through."""

import pytest

from cogcheck.hull import (
    convex_hull,
    distance_to_boundary,
    hull_is_degenerate,
    point_in_hull,
    polygon_area,
    signed_margin,
)


def test_square_hull_from_noisy_interior_points():
    """Interior points drop out; collinear edge points drop out too."""
    pts = [(0, 0), (10, 0), (10, 10), (0, 10), (5, 5), (5, 0), (2, 3), (9, 1)]
    hull = convex_hull(pts)
    assert len(hull) == 4
    assert polygon_area(hull) == pytest.approx(100.0)
    assert {tuple(p) for p in hull} == {(0, 0), (10, 0), (10, 10), (0, 10)}


def test_hull_is_counter_clockwise():
    hull = convex_hull([(0, 0), (10, 0), (10, 10), (0, 10)])
    assert hull == [(0, 0), (10, 0), (10, 10), (0, 10)]


def test_collinear_points_collapse_to_segment():
    hull = convex_hull([(0, 0), (5, 5), (10, 10), (2, 2)])
    assert len(hull) == 2
    assert hull_is_degenerate(hull)


def test_single_point_is_degenerate():
    hull = convex_hull([(3, 4)])
    assert hull == [(3, 4)]
    assert hull_is_degenerate(hull)


def test_point_in_hull():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_hull((5, 5), square)
    assert point_in_hull((0, 0), square)  # on the boundary counts
    assert not point_in_hull((11, 5), square)
    assert not point_in_hull((-0.1, -0.1), square)


def test_distance_to_boundary_inside_square():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert distance_to_boundary((5, 5), square) == pytest.approx(5.0)
    assert distance_to_boundary((2, 3), square) == pytest.approx(2.0)
    # A corner-nearest point measures to the corner, not either edge's line.
    assert distance_to_boundary((12, 12), square) == pytest.approx(2 * 2**0.5)


def test_distance_to_segment_clamps():
    """Distance to a segment, not its infinite line: a perpendicular foot
    beyond the endpoint clamps to the endpoint (what an
    outside-the-corner projection must measure)."""
    seg = [(0, 0), (10, 0)]  # a degenerate two-point "hull"
    assert distance_to_boundary((5, 7), seg) == pytest.approx(7.0)
    assert distance_to_boundary((12, 5), seg) == pytest.approx((2**2 + 5**2) ** 0.5)


def test_signed_margin_signs():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert signed_margin((5, 5), square) == pytest.approx(5.0)
    assert signed_margin((15, 5), square) == pytest.approx(-5.0)
    assert signed_margin((5, 0), square) == pytest.approx(0.0)


def test_hull_of_many_contact_vertices():
    """A tessellated lowest ring (36 vertices on a circle) keeps every vertex
    on the hull, whose area is the inscribed 36-gon's — the shape class real
    contact geometry arrives in, converging on the circle as n grows."""
    import math

    ring = [(10 * math.cos(a / 36 * 2 * math.pi), 10 * math.sin(a / 36 * 2 * math.pi))
            for a in range(36)]
    hull = convex_hull(ring)
    assert len(hull) == 36
    # Inscribed regular n-gon area: n/2 · r² · sin(2π/n).
    assert polygon_area(hull) == pytest.approx(18 * 100 * math.sin(2 * math.pi / 36), rel=1e-9)
    # ... and it sits under the circle's area, converging to it.
    assert polygon_area(hull) < math.pi * 100
