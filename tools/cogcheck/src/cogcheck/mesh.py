"""Mesh measurement: mass properties, transforms, and ground contact.

The centre of gravity comes from the standard signed tetrahedron
decomposition: every triangle with the origin forms a tetrahedron whose
signed volume is ``dot(v1, cross(v2, v3)) / 6`` and whose centroid is the
mean of its four corners, and summing volume-weighted centroids over a
closed, consistently-outward mesh yields the exact polyhedron volume and
centroid — no sampling, no meshing assumptions, exact for the analytic
cases the test suite pins (a unit cube lands on its centre; a two-body
composite lands on the mass-weighted mean of the bodies).

That exactness is why a broken mesh fails loudly instead of judging anyway:
a (near-)zero total volume means the mesh is not closed (or is degenerate),
a negative one means the normals point inward, and either makes every
downstream number fiction — the tool refuses rather than emits it.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from cogcheck.stl import Triangle

Vec3 = tuple[float, float, float]

#: Contact vertices this far (mm) above the lowest vertex count as touching
#: the ground. Prints rest on their lowest features, but a tessellated curved
#: bottom (a sphere's lowest ring, a chamfer's inner edge) sits its neighbours
#: microns above the true minimum, and a contact set of one vertex would make
#: every footprint degenerate. 0.05 mm is under one FDM layer's thickness —
#: features the print actually rests on — while never pulling in a feature
#: the design lifted clear of the ground.
CONTACT_EPS = 0.05

#: Below this volume (mm³) a mesh's tetrahedron sum reads as degenerate.
MIN_VOLUME_MM3 = 1e-6


class MeshError(Exception):
    """The mesh cannot be measured: not closed, inverted, or empty."""


def mass_properties(triangles: Sequence[Triangle]) -> tuple[float, Vec3]:
    """Return ``(volume_mm3, centroid_mm)`` by signed tetrahedron
    decomposition. Raises MeshError on a mesh the decomposition cannot trust
    (empty, near-zero volume, or inward normals)."""
    if not triangles:
        raise MeshError("mesh has no triangles")
    volume6 = 0.0
    cx = cy = cz = 0.0
    for (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) in triangles:
        signed6 = x1 * (y2 * z3 - y3 * z2) - y1 * (x2 * z3 - x3 * z2) + z1 * (x2 * y3 - x3 * y2)
        volume6 += signed6
        # Tetrahedron (origin, v1, v2, v3): centroid is the mean of the four
        # corners, so the origin contributes 0 and each vertex 1/4.
        cx += signed6 * (x1 + x2 + x3)
        cy += signed6 * (y1 + y2 + y3)
        cz += signed6 * (z1 + z2 + z3)
    volume = volume6 / 6.0
    if volume < -MIN_VOLUME_MM3:
        raise MeshError(
            f"mesh volume measures {volume:.3f} mm³ (negative): normals point "
            "inward or the mesh is not a closed surface — fix the source model"
        )
    if volume <= MIN_VOLUME_MM3:
        raise MeshError(
            f"mesh volume measures {volume:.6f} mm³ (effectively zero): the "
            "mesh is not closed (or is a zero-thickness shell), so it has no "
            "centre of gravity to compute"
        )
    # volume6 (not volume): the 1/6 and the 1/4 fold into one division.
    return volume, (cx / volume6 / 4.0, cy / volume6 / 4.0, cz / volume6 / 4.0)


def rotation_matrix(rotate_deg: Vec3) -> tuple[Vec3, Vec3, Vec3]:
    """Rotation matrix for ``rotate_deg = (rx, ry, rz)`` in the OpenSCAD
    ``rotate([x, y, z])`` convention: X first, then Y, then Z (M = Rz·Ry·Rx).
    Matching OpenSCAD matters because the manifest's transforms are written
    by people modelling in it; a different order would silently place parts
    elsewhere for the same numbers."""
    rx, ry, rz = (math.radians(a) for a in rotate_deg)
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    # Rz @ Ry @ Rx, rows written out once so the product stays checkable.
    return (
        (cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
        (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
        (-sy, cy * sx, cy * cx),
    )


def apply_rotation(matrix: tuple[Vec3, Vec3, Vec3], point: Vec3) -> Vec3:
    """Matrix-vector product, spelled out for three dimensions of tuples."""
    r1, r2, r3 = matrix
    x, y, z = point
    return (
        r1[0] * x + r1[1] * y + r1[2] * z,
        r2[0] * x + r2[1] * y + r2[2] * z,
        r3[0] * x + r3[1] * y + r3[2] * z,
    )


def transform_point(point: Vec3, rotate_deg: Vec3, translate: Vec3) -> Vec3:
    """Rotate about the part's origin, then translate — the assembled-part
    placement convention the manifest documents."""
    x, y, z = apply_rotation(rotation_matrix(rotate_deg), point)
    return (x + translate[0], y + translate[1], z + translate[2])


def transform_triangles(
    triangles: Iterable[Triangle], rotate_deg: Vec3, translate: Vec3
) -> list[Triangle]:
    """Every vertex of every triangle through the part placement."""
    return [
        (
            transform_point(v, rotate_deg, translate),
            transform_point(w, rotate_deg, translate),
            transform_point(u, rotate_deg, translate),
        )
        for v, w, u in triangles
    ]


def ground_contact(triangles: Iterable[Triangle], eps: float = CONTACT_EPS) -> list[tuple[float, float]]:
    """The ``(x, y)`` of every vertex resting on the ground: the lowest
    vertex's z, plus everything within ``eps`` of it. Rotations are exactly
    what make this non-trivial — a part modelled flat but assembled tilted
    rests on the corner the tilt raises the others above."""
    vertices = [v for tri in triangles for v in tri]
    if not vertices:
        return []
    z_min = min(v[2] for v in vertices)
    return [(v[0], v[1]) for v in vertices if v[2] <= z_min + eps]
