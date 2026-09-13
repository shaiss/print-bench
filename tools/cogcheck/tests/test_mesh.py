"""The CoG math, verified against analytic cases — measurement, not
restatement (the issue #37 discipline).

Every value asserted here is hand-derived from the geometry, never from
running the code under test: the decomposition's answers for a box are the
box's volume and centre by inspection, composites land on mass-weighted
means, and transforms move centroids affinely. A test that re-derived the
tetrahedron algebra would only prove the formula equals itself.
"""

import pytest

from cogcheck.mesh import (
    CONTACT_EPS,
    MeshError,
    apply_rotation,
    ground_contact,
    mass_properties,
    rotation_matrix,
    transform_point,
)
from conftest import box_triangles


def test_unit_cube_volume_and_centre():
    """The analytic control: a 10 mm cube measures exactly 1000 mm³ centred
    at (5,5,5) — off-origin on purpose, so the origin-tetrahedron sums have
    to cancel correctly rather than trivially."""
    volume, centroid = mass_properties(box_triangles(0, 0, 0, 10, 10, 10))
    assert volume == pytest.approx(1000.0, abs=1e-9)
    assert centroid == pytest.approx((5.0, 5.0, 5.0), abs=1e-9)


def test_asymmetric_box_centre():
    """A box from (-20,-5,3) to (10,25,9): centre is the midpoint of each
    span, nothing symmetric to hide behind."""
    volume, centroid = mass_properties(box_triangles(-20, -5, 3, 10, 25, 9))
    assert volume == pytest.approx(30 * 30 * 6)
    assert centroid == pytest.approx((-5.0, 10.0, 6.0), abs=1e-9)


def test_inverted_normals_refused():
    """Reversed winding reads as negative volume: refused, not judged."""
    flipped = [(t[0], t[2], t[1]) for t in box_triangles(0, 0, 0, 10, 10, 10)]
    with pytest.raises(MeshError, match="negative"):
        mass_properties(flipped)


def test_empty_mesh_refused():
    with pytest.raises(MeshError, match="no triangles"):
        mass_properties([])


def test_open_shell_refused():
    """A single triangle is not a closed surface: effectively-zero volume,
    refused rather than a fiction of a centroid."""
    with pytest.raises(MeshError, match="effectively zero"):
        mass_properties([((0, 0, 0), (10, 0, 0), (0, 10, 0))])


def test_rotation_follows_openscad_convention():
    """rotate: 0,0,90 maps (x,y,z) -> (-y,x,z) — the OpenSCAD convention the
    manifest documents; a different order would move parts elsewhere for the
    same numbers."""
    m = rotation_matrix((0.0, 0.0, 90.0))
    assert apply_rotation(m, (5.0, 0.0, 0.0)) == pytest.approx((0.0, 5.0, 0.0), abs=1e-12)
    assert apply_rotation(m, (5.0, 5.0, 0.0)) == pytest.approx((-5.0, 5.0, 0.0), abs=1e-12)


def test_rotation_preserves_length():
    """Any rotation matrix must be orthogonal: a point's distance from the
    origin survives it (checked at an untidy compound angle)."""
    m = rotation_matrix((30.0, -45.0, 60.0))
    p = (3.0, -7.0, 11.0)
    q = apply_rotation(m, p)
    assert sum(c * c for c in q) == pytest.approx(sum(c * c for c in p), rel=1e-12)


def test_transform_point_rotates_then_translates():
    assert transform_point((1.0, 2.0, 3.0), (0.0, 0.0, 0.0), (10.0, 20.0, 30.0)) == (
        11.0, 22.0, 33.0
    )
    # rotate 0,0,90 maps (1,0,0) -> (0,1,0), then +translate lands there.
    assert transform_point((1.0, 0.0, 0.0), (0.0, 0.0, 90.0), (10.0, 0.0, 0.0)) == (
        pytest.approx(10.0, abs=1e-12), pytest.approx(1.0, abs=1e-12), 0.0
    )


def test_ground_contact_picks_lowest_features():
    tris = box_triangles(0, 0, 5, 10, 10, 15)
    contact = ground_contact(tris)
    # Every contact point is a bottom corner; the set is the square's four
    # corners (a triangulated box repeats corners across triangles — 18
    # instances here — so the SET is the meaningful assertion).
    assert set(contact) == {(0.0, 0.0), (0.0, 10.0), (10.0, 0.0), (10.0, 10.0)}
    assert all(-1e-9 <= x <= 10 + 1e-9 and -1e-9 <= y <= 10 + 1e-9 for x, y in contact)


def test_ground_contact_epsilon_pulls_in_nearby_ring():
    """Vertices within CONTACT_EPS of the lowest count as touching — a
    tessellated curved bottom rests on its whole lowest ring, not one
    vertex — while a feature lifted clear of it does not."""
    tris = box_triangles(0, 0, 0, 10, 10, 10)
    # A shallow pyramid apex 0.02 mm above the ground (inside the epsilon)…
    tris = tris + [
        ((0, 0, 0), (10, 0, 0), (5, 5, 0.02)),
        ((10, 0, 0), (10, 10, 0), (5, 5, 0.02)),
        ((10, 10, 0), (0, 10, 0), (5, 5, 0.02)),
        ((0, 10, 0), (0, 0, 0), (5, 5, 0.02)),
        # …and one 1 mm up (outside it), at a distinguishable (x, y).
        ((0, 0, 0), (10, 0, 0), (7, 7, 1.0)),
    ]
    contact = ground_contact(tris)
    xs_ys = [
        (pytest.approx(x, abs=1e-9), pytest.approx(y, abs=1e-9)) for x, y in contact
    ]
    assert (5.0, 5.0) in xs_ys
    assert (7.0, 7.0) not in xs_ys
