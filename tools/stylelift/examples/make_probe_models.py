"""Probe meshes with exactly known style geometry.

Every shape here is built from arcs and lines whose radius, chamfer and wall
thickness we chose, so a measurement can be compared against the truth rather
than against a previous run. The test suite imports these builders; running the
file writes the meshes to disk to play with by hand:

    python examples/make_probe_models.py [outdir]
    stylelift measure probes/*.stl
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon


def rounded_prism(width=40.0, depth=30.0, height=15.0, radius=3.0,
                  quarter_segments=16) -> trimesh.Trimesh:
    """Box with vertical edges rounded to exactly `radius`.

    shapely's round join draws true circular arcs, so the corner vertices sit on
    the circle of radius `radius` — an inscribed tessellation, which is what the
    radius identity in measure.py assumes. quarter_segments=16 is a full-circle
    resolution of 64, i.e. what OpenSCAD calls $fn=64.
    """
    core = Polygon([(radius, radius), (width - radius, radius),
                    (width - radius, depth - radius), (radius, depth - radius)])
    return trimesh.creation.extrude_polygon(
        core.buffer(radius, quad_segs=quarter_segments, join_style=1), height)


def chamfered_prism(width=40.0, depth=30.0, height=15.0, leg=1.0) -> trimesh.Trimesh:
    """Box whose vertical edges are cut by a 45-degree chamfer of `leg` mm."""
    outline = Polygon([
        (leg, 0), (width - leg, 0), (width, leg), (width, depth - leg),
        (width - leg, depth), (leg, depth), (0, depth - leg), (0, leg)])
    return trimesh.creation.extrude_polygon(outline, height)


def sharp_prism(width=40.0, depth=30.0, height=15.0) -> trimesh.Trimesh:
    """Plain box: every edge is a corner."""
    return trimesh.creation.extrude_polygon(
        Polygon([(0, 0), (width, 0), (width, depth), (0, depth)]), height)


def drilled_plate(width=40.0, depth=30.0, height=4.0, hole_d=3.4,
                  quarter_segments=16) -> trimesh.Trimesh:
    """Flat plate with four vertical clearance holes of exactly `hole_d`."""
    plate = Polygon([(0, 0), (width, 0), (width, depth), (0, depth)])
    for x in (8.0, width - 8.0):
        for y in (8.0, depth - 8.0):
            plate = plate.difference(
                Point(x, y).buffer(hole_d / 2, quad_segs=quarter_segments))
    return trimesh.creation.extrude_polygon(plate, height)


def shelled_tube(width=40.0, depth=30.0, height=15.0, wall=2.4) -> trimesh.Trimesh:
    """Rectangular tube: a part whose material thickness really is `wall`."""
    outer = Polygon([(0, 0), (width, 0), (width, depth), (0, depth)])
    inner = Polygon([(wall, wall), (width - wall, wall),
                     (width - wall, depth - wall), (wall, depth - wall)])
    return trimesh.creation.extrude_polygon(outer.difference(inner), height)


def chamfered_slab(width=60.0, depth=40.0, height=3.0, leg=0.6) -> trimesh.Trimesh:
    """A plate whose bottom edges are cut back at 45 degrees — the repo's own
    `bottom_chamfer`, on a plate thin enough that the wall above the chamfer is
    only a few times its width.

    Built as the convex hull of an inset bottom rectangle and the full-size
    rectangle above it, which is exactly a 45-degree chamfer and needs no
    boolean engine. The point of the probe is the *proportion*: measuring this
    must not depend on how tall the wall above the chamfer happens to be.
    """
    w, d, c = width / 2, depth / 2, leg
    points = ([[x, y, 0.0] for x in (-w + c, w - c) for y in (-d + c, d - c)]
              + [[x, y, z] for x in (-w, w) for y in (-d, d)
                 for z in (c, height)])
    return trimesh.PointCloud(np.array(points)).convex_hull


def tapered_boss_plate(width=120.0, depth=20.0, height=6.0, r_low=9.0,
                       r_high=4.0, boss_h=5.0, segments=64) -> trimesh.Trimesh:
    """A flat bar carrying one plain draft-angled boss — a part with no fillet,
    no rounded edge and no arc except the two circular rims.

    The boss is the convex hull of two circles at different heights, which is
    exactly a frustum. Nothing here has a corner radius, and a measurement that
    reports one is reading the taper as curvature.
    """
    # Built face by face rather than as a convex hull, because the lateral
    # quads of a frustum are planar and every CAD exporter emits them that way:
    # a hull triangulates them with a zigzag that no real STL of a cone has.
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    cx, cy = width / 2, depth / 2
    low = np.array([[cx + r_low * np.cos(a), cy + r_low * np.sin(a), height]
                    for a in angles])
    high = np.array([[cx + r_high * np.cos(a), cy + r_high * np.sin(a),
                      height + boss_h] for a in angles])
    verts = np.vstack([low, high, [[cx, cy, height + boss_h]]])
    top_centre = 2 * segments
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        # the planar quad between two generators, split along one diagonal
        faces += [[i, j, segments + j], [i, segments + j, segments + i]]
        faces.append([segments + i, segments + j, top_centre])
    boss = trimesh.Trimesh(vertices=verts, faces=np.array(faces),
                           process=False)
    bar = trimesh.creation.box(extents=(width, depth, height))
    bar.apply_translation([width / 2, depth / 2, height / 2])
    return trimesh.util.concatenate([bar, boss])


def rounded_slab(**kw) -> trimesh.Trimesh:
    """A different *part* in the same language as rounded_prism: same radius and
    the same curve resolution, less than half the size. A style check has to
    accept this one — if it does not, the spec is measuring size, not style."""
    return rounded_prism(**{"width": 18.0, "depth": 12.0, "height": 6.0,
                            "radius": 3.0, **kw})


def smooth_ball(radius=10.0, count=(32, 16)) -> trimesh.Trimesh:
    """A solid with no decided edge anywhere: every fold is one segment of the
    sphere's own tessellation, and every join is tangent so not one corner
    exists.

    The smooth-and-solid half of the faceted/open pair — the counterfactual a
    sharpness or openness metric has to score zero on. count=(32, 16) draws it
    the way OpenSCAD's `sphere($fn=32)` does, so the coarsest folds (the
    equator) turn 360/32 = 11.25 degrees — steep, but tessellation all the
    same, which is the whole point: the sharpness metric must read the
    mesh's own resolution, not the fold angle.
    """
    return trimesh.creation.uv_sphere(radius=radius, count=list(count))


def pierced_rounded_box(width=40.0, depth=30.0, height=15.0, radius=3.0,
                        quarter_segments=2, bore_d=8.0, bore_segments=64
                        ) -> trimesh.Trimesh:
    """A coarse-$fn rounded box carrying one fine cylindrical bore.

    The $fn-normalization control. With `quarter_segments=2` the corner arcs
    are 45-degree folds — the same turn the stencil plate's chamfers make —
    but here they are segments of 8-sided curves, so the sharpness metric
    must treat them as tessellation: the mesh's finest curve is the 8-sided
    corner, and it explains every 45-degree fold it has. Pierce it with a
    $fn=64 bore and nothing else moves, yet the finest curve is now the bore,
    the threshold drops below 45 degrees, and those same folds are design
    facets. One mesh, one extra hole, opposite verdicts — that is the proof
    the metric separates on declared resolution rather than on a lucky
    shallow-angle cutoff.
    """
    core = Polygon([(radius, radius), (width - radius, radius),
                    (width - radius, depth - radius), (radius, depth - radius)])
    shape = core.buffer(radius, quad_segs=quarter_segments, join_style=1)
    if bore_d > 0:
        shape = shape.difference(
            Point(width / 2, depth / 2).buffer(
                bore_d / 2, quad_segs=max(4, bore_segments // 4)))
    return trimesh.creation.extrude_polygon(shape, height)


def stencil_plate(width=60.0, depth=40.0, height=8.0, chamfer=3.0, web=4.0,
                  cols=3, rows=2, slot_w=10.0, slot_h=14.0) -> trimesh.Trimesh:
    """A faceted, cut-through probe: a chamfered plate carrying a grid of
    rectangular through-slots — the stencil-glyph look, with every number
    chosen.

    The outline corners are cut at 45 degrees (`chamfer` legs), so the part
    owns decisive facets, and the slots are plain rectangles, so essentially
    all of its shaped edge length is facet. Slot size, count and the web
    between them are parameters, which makes the open-area fraction, the
    largest through-void span and the narrowest bridge arithmetic on the
    arguments: slots cover `cols*rows*slot_w*slot_h` of the chamfered face,
    the longest straight line a slot can be threaded by is its space
    diagonal, and the narrowest material anywhere is `web` (the rim margins
    are wider). Drop `web` below two extrusion widths and the same probe
    becomes the negative control for a bridge rule.
    """
    grid_w = cols * slot_w + (cols - 1) * web
    grid_d = rows * slot_h + (rows - 1) * web
    if grid_w > width - 2 * chamfer or grid_d > depth - 2 * chamfer:
        raise ValueError("slot grid does not fit inside the chamfered outline")
    outline = [
        (chamfer, 0), (width - chamfer, 0), (width, chamfer),
        (width, depth - chamfer), (width - chamfer, depth),
        (chamfer, depth), (0, depth - chamfer), (0, chamfer)]
    holes = []
    x0 = (width - grid_w) / 2
    y0 = (depth - grid_d) / 2
    for i in range(cols):
        for j in range(rows):
            lx = x0 + i * (slot_w + web)
            ly = y0 + j * (slot_h + web)
            holes.append([(lx, ly), (lx + slot_w, ly),
                          (lx + slot_w, ly + slot_h), (lx, ly + slot_h)])
    return trimesh.creation.extrude_polygon(
        Polygon(outline, holes=holes), height)


BUILDERS = {
    "sharp-box": sharp_prism,
    "rounded-box": rounded_prism,
    "rounded-slab": rounded_slab,
    "chamfered-box": chamfered_prism,
    "drilled-plate": drilled_plate,
    "shelled-tube": shelled_tube,
    "smooth-ball": smooth_ball,
    "stencil-plate": stencil_plate,
    "pierced-rounded-box": pierced_rounded_box,
}


def main(outdir: str = "probes") -> None:
    """Write every probe mesh to `outdir` as STL."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for name, build in BUILDERS.items():
        mesh = build()
        path = out / f"{name}.stl"
        mesh.export(str(path))
        print(f"{path}  {len(mesh.faces):5d} faces  "
              f"{np.round(mesh.extents, 2)} mm")


if __name__ == "__main__":
    main(*sys.argv[1:2])
