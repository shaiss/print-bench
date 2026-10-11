"""Assemble the manifest's parts and masses into the tip-over verdict.

The physics is the support-polygon rule every stability textbook opens with:
an object standing on a surface tips exactly when the ground projection of
its centre of gravity leaves the convex hull of its contact geometry — the
support footprint — and it is *marginal* before that, which is what the
tunable margin encodes (a CoG projection barely inside a footprint is one
desk bump from outside it).

Everything before the verdict is arithmetic on measured mesh properties:
each part's tetrahedron-decomposed volume times its manifest density (mm³ ·
g/cm³ ÷ 1000 = grams), placed by its manifest transform (the centroid moves
affinely, so it transforms as a point — no need to re-run the decomposition
on the placed mesh); each non-printed mass lands whole at its position. The
footprint is the 2D convex hull of the contact vertices of all PLACED
PRINTED parts — brass stalks and PCBs hang in the air by construction, and a
mass that touched the ground would be a foot, which a manifest would model
as a zero-height part.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from cogcheck import hull
from cogcheck.conf import Manifest
from cogcheck.mesh import (
    MeshError,
    Vec3,
    ground_contact,
    mass_properties,
    transform_point,
    transform_triangles,
)
from cogcheck.stl import Triangle, read_triangles

STABLE = "STABLE"
TIP_RISK = "TIP-RISK"


class AssemblyError(Exception):
    """The manifest's parts could not be assembled into a measurable object."""


@dataclass(frozen=True)
class PartResult:
    """One printed part's measured contribution to the assembly."""

    stl: str
    volume_mm3: float
    mass_g: float
    cog: Vec3  # in the assembled standing frame
    contact_points: int


@dataclass(frozen=True)
class CheckResult:
    verdict: str  # STABLE | TIP-RISK
    detail: str
    cog: Vec3
    total_mass_g: float
    ground_z: float
    footprint: tuple[tuple[float, float], ...]
    footprint_area_mm2: float
    footprint_degenerate: bool
    margin: float
    margin_left: float  # signed distance (mm) from CoG projection to boundary
    parts: tuple[PartResult, ...] = field(default_factory=tuple)
    point_masses: tuple[tuple[str, float, Vec3], ...] = field(default_factory=tuple)


def assemble(
    manifest: Manifest,
    stl_dir: str | Path = "build",
    read: Callable[[Path], list[Triangle]] = read_triangles,
) -> CheckResult:
    """Measure every part, assemble, and return the verdict. Raises
    AssemblyError (wrapping the underlying reason) when a part's STL cannot
    be read or measured, or the assembled object has no mass."""
    stl_dir = Path(stl_dir)
    stl_root = stl_dir.resolve()
    part_results: list[PartResult] = []
    placed_triangles: list[Triangle] = []
    moment_x = moment_y = moment_z = 0.0
    total_mass = 0.0

    for spec in manifest.parts:
        # Basename-only names are enforced by conf.py; resolve under stl_dir
        # so a caller that bypasses the parser still cannot escape the tree.
        path = (stl_dir / spec.stl).resolve()
        if path != stl_root and not path.is_relative_to(stl_root):
            raise AssemblyError(
                f"part '{spec.stl}' resolves outside stl dir {stl_root}"
            )
        try:
            triangles = read(path)
        except (OSError, ValueError) as e:
            raise AssemblyError(f"cannot read part '{spec.stl}' from {path}: {e}") from e
        try:
            volume, centroid = mass_properties(triangles)
        except MeshError as e:
            raise AssemblyError(f"part '{spec.stl}': {e}") from e
        # mm³ × g/cm³ ÷ 1000 = grams.
        mass = spec.density * volume / 1000.0
        cog_world = transform_point(centroid, spec.rotate, spec.translate)
        placed = transform_triangles(triangles, spec.rotate, spec.translate)
        contact = ground_contact(placed)
        part_results.append(
            PartResult(
                stl=spec.stl,
                volume_mm3=volume,
                mass_g=mass,
                cog=cog_world,
                contact_points=len(contact),
            )
        )
        placed_triangles.extend(placed)
        moment_x += mass * cog_world[0]
        moment_y += mass * cog_world[1]
        moment_z += mass * cog_world[2]
        total_mass += mass

    placed_masses: list[tuple[str, float, Vec3]] = []
    for mass_spec in manifest.masses:
        placed_masses.append((mass_spec.label, mass_spec.grams, mass_spec.at))
        moment_x += mass_spec.grams * mass_spec.at[0]
        moment_y += mass_spec.grams * mass_spec.at[1]
        moment_z += mass_spec.grams * mass_spec.at[2]
        total_mass += mass_spec.grams

    if total_mass <= 0:
        raise AssemblyError("assembled object has no mass — nothing to judge")

    cog: Vec3 = (moment_x / total_mass, moment_y / total_mass, moment_z / total_mass)

    contact = ground_contact(placed_triangles)
    if not contact:
        raise AssemblyError("no contact geometry — the assembly touches nothing")
    ground_z = min(v[2] for tri in placed_triangles for v in tri)
    footprint = hull.convex_hull(contact)
    degenerate = hull.hull_is_degenerate(footprint)
    area = hull.polygon_area(footprint)
    projection = (cog[0], cog[1])
    margin_left = hull.signed_margin(projection, footprint)

    if degenerate:
        verdict = TIP_RISK
        detail = (
            "support footprint is degenerate (line/point contact) — it cannot "
            "stabilise a centre of gravity at any margin"
        )
    elif margin_left < manifest.margin:
        verdict = TIP_RISK
        if margin_left < 0:
            detail = (
                f"CoG ground projection is {abs(margin_left):.2f} mm OUTSIDE the "
                f"support footprint (margin {manifest.margin:.2f} mm) — the object tips"
            )
        else:
            detail = (
                f"CoG ground projection only {margin_left:.2f} mm inside the support "
                f"footprint, under the {manifest.margin:.2f} mm margin — marginal, "
                "one bump from tipping"
            )
    else:
        verdict = STABLE
        detail = (
            f"CoG ground projection clears the support footprint boundary by "
            f"{margin_left:.2f} mm (margin {manifest.margin:.2f} mm)"
        )

    return CheckResult(
        verdict=verdict,
        detail=detail,
        cog=cog,
        total_mass_g=total_mass,
        ground_z=ground_z,
        footprint=tuple(footprint),
        footprint_area_mm2=area,
        footprint_degenerate=degenerate,
        margin=manifest.margin,
        margin_left=margin_left,
        parts=tuple(part_results),
        point_masses=tuple(placed_masses),
    )
