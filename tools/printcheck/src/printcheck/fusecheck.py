"""fusecheck — deterministic separable-body count on a SLICED print STL.

A print-in-place mechanism that welds shut still exports watertight, and — for a
living hinge — as a single connected body, so printcheck cannot see it. A
hand-written interference fitcheck *can* see fusion, but only in the pose its
author intersects, and that pose can be the wrong one: the first
sweetheart-hamster shipped a fitcheck that intersected the CLOSED pose while CI
sliced the FLAT pose, and missed a 1378-facet weld at the hinge.

fusecheck answers the un-mis-aimable question. It takes the exact STL that gets
sliced — `build/<name>.stl` / `build/<name>-<part>.stl`, no ``-D`` override —
removes the declared thin-flexure zone(s), and counts how many separate bodies
remain. A living hinge that joins the two halves *only* through its flexure
splits into 2 once the flexure is removed; a large-area weld stays connected
(1). It reports the count and nothing else; ``scripts/gate.sh`` applies the
per-design thresholds and the mandatory-negative-control discipline, exactly as
it does for ``ci.fitchecks`` — so this tool stays a pure measurement like
``lineage facet-count``.

Frame: the mesh is rested so its lowest point is z=0 (printcheck's convention),
so ``--ignore-aabb`` coordinates are in printcheck's rested frame — the same
frame printcheck reports in.
"""

from __future__ import annotations

import argparse
import json
import sys

Aabb = "tuple[tuple[float, float, float], tuple[float, float, float]]"


def parse_aabb(spec: str):
    """Parse ``x0,y0,z0:x1,y1,z1`` into ((lo3), (hi3)), min/max-normalised."""
    try:
        lo_s, hi_s = spec.split(":")
        lo = tuple(float(v) for v in lo_s.split(","))
        hi = tuple(float(v) for v in hi_s.split(","))
    except ValueError as e:
        raise ValueError(
            f"--ignore-aabb wants x0,y0,z0:x1,y1,z1, got {spec!r}") from e
    if len(lo) != 3 or len(hi) != 3:
        raise ValueError(
            f"--ignore-aabb wants three numbers each side, got {spec!r}")
    return (tuple(min(a, b) for a, b in zip(lo, hi)),
            tuple(max(a, b) for a, b in zip(lo, hi)))


def separable_bodies(mesh, aabbs):
    """(bodies, dropped_faces) after removing faces whose CENTROID is in any AABB.

    Centroids, not any-vertex: a flexure zone should shave the thin bridge
    without nibbling the boundary faces of the parts it joins. The caller rests
    the mesh; connectivity is trimesh's ``body_count`` — the connected-component
    count over the face-adjacency graph — which is exactly what printcheck
    reports as ``bodies``, so a fused export reads identically here. (We use
    ``body_count`` rather than ``split()`` deliberately: ``split`` routes through
    watertight hole-filling that pulls in an optional dependency the printcheck
    environment does not ship, while ``body_count`` is pure scipy.)
    """
    import numpy as np

    n = len(mesh.faces)
    if n == 0:
        return 0, 0
    centroids = mesh.triangles.mean(axis=1)          # (F, 3) face centroids
    drop = np.zeros(n, dtype=bool)
    for lo, hi in aabbs:
        inside = (np.all(centroids >= np.asarray(lo), axis=1)
                  & np.all(centroids <= np.asarray(hi), axis=1))
        drop |= inside
    dropped = int(drop.sum())
    keep_idx = np.nonzero(~drop)[0]
    if len(keep_idx) == 0:
        return 0, dropped
    kept = mesh.submesh([keep_idx], only_watertight=False, append=True)
    if len(kept.faces) == 0:
        return 0, dropped
    return int(kept.body_count), dropped


def count_stl(path, aabbs):
    """Load the STL exactly as printcheck does, rest it, and count bodies."""
    from .analyzer import load_mesh

    mesh = load_mesh(path)
    if len(mesh.vertices):
        mesh.apply_translation([0, 0, -mesh.bounds[0][2]])   # rest on the plate
    return separable_bodies(mesh, aabbs)


def _selftest() -> int:
    """Prove the split fires: a flexure-bridged part splits, a weld stays one.

    Two boxes joined into ONE manifold by a thin neck inside the AABB must
    split into 2 when the neck is removed (positive); the same two boxes joined
    by a slab OUTSIDE the AABB must stay 1 (negative — the check can't be fooled
    by welds the flexure zone doesn't cover, and can't false-pass a design whose
    weld sits outside a too-small zone).
    """
    import trimesh

    def box(ext, at):
        m = trimesh.creation.box(extents=ext)
        m.apply_translation(at)
        return m

    a = box([10, 10, 10], [-7, 0, 5])
    b = box([10, 10, 10], [7, 0, 5])
    neck = box([6, 4, 4], [0, 0, 5])          # bridges the 4 mm gap, x∈[-3,3]
    weld = box([16, 4, 4], [0, 0, 9])         # a slab joining both, z∈[7,11]
    aabb = [parse_aabb("-3.2,-2.1,2.9:3.2,2.1,7.1")]   # covers the neck only

    bridged = trimesh.boolean.union([a, neck, b])
    bridged.merge_vertices()
    k, dropped = separable_bodies(bridged, aabb)
    if k != 2:
        print(f"FAIL  fusecheck selftest: bridged expected 2 bodies after "
              f"removing the flexure, got {k} (dropped {dropped} faces)",
              file=sys.stderr)
        return 1

    fused = trimesh.boolean.union([a, weld, b])
    fused.merge_vertices()
    k, dropped = separable_bodies(fused, aabb)
    if k != 1:
        print(f"FAIL  fusecheck selftest: weld outside the flexure expected 1 "
              f"body, got {k} (dropped {dropped} faces)", file=sys.stderr)
        return 1

    print("ok    fusecheck selftest: flexure-bridged splits into 2, "
          "weld stays 1 — the separation test fires")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="fusecheck",
        description="Count separable bodies of a sliced STL after removing "
                    "declared flexure zones (deterministic fuse detector).")
    ap.add_argument("stl", nargs="?",
                    help="the sliced STL to analyse (build/<name>.stl)")
    ap.add_argument("--ignore-aabb", action="append", default=[], metavar="BOX",
                    help="x0,y0,z0:x1,y1,z1 flexure zone to drop before "
                         "counting (repeatable); coords in printcheck's rested "
                         "frame (lowest point at z=0)")
    ap.add_argument("--json", action="store_true",
                    help="emit {stl, bodies, dropped_faces, aabbs} as JSON")
    ap.add_argument("--selftest", action="store_true",
                    help="run the built-in positive+negative fixtures and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.stl:
        ap.error("an STL path is required (or use --selftest)")

    try:
        aabbs = [parse_aabb(s) for s in args.ignore_aabb]
    except ValueError as e:
        print(f"fusecheck: {e}", file=sys.stderr)
        return 2
    try:
        bodies, dropped = count_stl(args.stl, aabbs)
    except (OSError, ValueError) as e:
        print(f"fusecheck: {args.stl}: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"stl": args.stl, "bodies": bodies,
                          "dropped_faces": dropped,
                          "aabbs": [list(lo) + list(hi) for lo, hi in aabbs]}))
    else:
        print(bodies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
