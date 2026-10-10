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
(1). It reports the count and nothing else on stdout; ``scripts/gate.sh``
applies the per-design thresholds and the mandatory-negative-control
discipline, exactly as it does for ``ci.fitchecks`` — so this tool stays a pure
measurement like ``lineage facet-count``.

The threshold itself is a **two-sided bound** (issue #612 part 2), owned here so
the gate and a hand run cannot drift: ``--bound MIN`` (the legacy one-sided
floor), ``--bound MIN:MAX`` or ``--bound =N`` (min = max = N). Too FEW bodies is
the fuse — a STRONG WARN a reviewer must consciously sign off (exit 3). Too MANY
bodies is a different defect entirely: an extra body is a freed counter island
(a stencil "0" whose tether never printed) or a dropped part, something no
reviewer should wave through, so it is a hard FAIL (exit 4). The count still
prints exactly as before; only the exit code carries the verdict, so a caller
that never passes ``--bound`` sees byte-identical output.

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


# Verdicts of ``verdict()`` and the exit codes ``main()`` maps them to. The
# fuse (too few bodies) is a WARN the reviewers sign off; an extra body (too
# many) is a FAIL nobody may wave through — the asymmetry is the whole point.
VERDICT_OK = "ok"
VERDICT_WARN = "warn"      # bodies < min: likely FUSED
VERDICT_FAIL = "FAIL"      # bodies > max: freed island / dropped part
EXIT_BELOW_MIN = 3
EXIT_ABOVE_MAX = 4


def parse_bound(spec: str):
    """Parse a body-count bound into ``(lo, hi)``; ``hi`` is None when open.

    Accepted shapes — the same three ``ci.fusecheck``'s ``assert`` line takes:

    - ``"3"``      → (3, None)   legacy one-sided floor: >= 3 bodies
    - ``"3:5"``    → (3, 5)      two-sided: 3 <= bodies <= 5
    - ``"=2"``     → (2, 2)      sugar for exactly N

    Anything else — a non-integer, a negative, an empty side, or a max below
    the min — is malformed and raises ValueError naming the spec, so a typo'd
    bound fails loudly instead of silently gating nothing.
    """
    text = spec.strip()
    if text.startswith("="):
        n = _bound_int(text[1:], spec)
        return n, n
    if ":" in text:
        lo_s, hi_s = text.split(":", 1)
        lo, hi = _bound_int(lo_s, spec), _bound_int(hi_s, spec)
        if hi < lo:
            raise ValueError(
                f"bound wants MIN <= MAX, got {spec!r} (max {hi} < min {lo})")
        return lo, hi
    return _bound_int(text, spec), None


def _bound_int(text: str, spec: str) -> int:
    text = text.strip()
    if not text.isdigit():
        raise ValueError(
            f"bound wants MIN, MIN:MAX or =N with non-negative integers, "
            f"got {spec!r}")
    return int(text)


def verdict(bodies: int, lo: int, hi=None) -> str:
    """Apply a bound to a body count: ``ok`` / ``warn`` (fused) / ``FAIL``.

    ``bodies < lo`` is the fuse case and stays what it always was — a STRONG
    WARN needing reviewer signoff. ``bodies > hi`` (only when a max is set) is
    a hard FAIL: the extra body is a freed island or a dropped part. With
    ``hi`` None the bound is one-sided and can never FAIL, which is exactly the
    legacy behaviour every existing manifest relies on.
    """
    if bodies < lo:
        return VERDICT_WARN
    if hi is not None and bodies > hi:
        return VERDICT_FAIL
    return VERDICT_OK


def format_bound(lo: int, hi=None) -> str:
    """Human form of a bound: ``>= 3``, ``= 2`` or ``3..5``."""
    if hi is None:
        return f">= {lo}"
    if hi == lo:
        return f"= {lo}"
    return f"{lo}..{hi}"


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
    ap.add_argument("--bound", metavar="MIN[:MAX]|=N", default=None,
                    help="judge the count: MIN (>= MIN, legacy), MIN:MAX or =N. "
                         "Output is unchanged; the exit code carries the "
                         "verdict — 0 within, 3 below MIN (likely FUSED: a "
                         "warn for reviewer signoff), 4 above MAX (extra body "
                         "= freed island / dropped part: a hard FAIL)")
    ap.add_argument("--json", action="store_true",
                    help="emit {stl, bodies, dropped_faces, aabbs} as JSON "
                         "(plus bound and verdict when --bound is given)")
    ap.add_argument("--selftest", action="store_true",
                    help="run the built-in positive+negative fixtures and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.stl:
        ap.error("an STL path is required (or use --selftest)")

    try:
        aabbs = [parse_aabb(s) for s in args.ignore_aabb]
        bound = parse_bound(args.bound) if args.bound is not None else None
    except ValueError as e:
        print(f"fusecheck: {e}", file=sys.stderr)
        return 2
    try:
        bodies, dropped = count_stl(args.stl, aabbs)
    except (OSError, ValueError) as e:
        print(f"fusecheck: {args.stl}: {e}", file=sys.stderr)
        return 2

    result = VERDICT_OK if bound is None else verdict(bodies, *bound)
    if args.json:
        out = {"stl": args.stl, "bodies": bodies, "dropped_faces": dropped,
               "aabbs": [list(lo) + list(hi) for lo, hi in aabbs]}
        if bound is not None:
            out["bound"] = list(bound)
            out["verdict"] = result
        print(json.dumps(out))
    else:
        print(bodies)
    if result == VERDICT_WARN:
        return EXIT_BELOW_MIN
    if result == VERDICT_FAIL:
        return EXIT_ABOVE_MAX
    return 0


if __name__ == "__main__":
    sys.exit(main())
