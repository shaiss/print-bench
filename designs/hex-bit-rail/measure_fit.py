#!/usr/bin/env python3
"""Measure the EXPORTED hex-bit-rail meshes against the brief's numbers.

G4 discipline (issue #37's lesson): the parameters say nothing on their own —
this re-derives every Must fit / hold dimension from the STL geometry and
fails loudly if the mesh drifted from the brief. Run after a gate:

    python3 designs/hex-bit-rail/measure_fit.py

Exits 0 when every measurement is inside tolerance, 1 otherwise.

Method (no networkx needed):
  pitch   — scan downward rays at y=+0.3 (off the hex corners, which sit on
            the pocket axis) across the rail's length; a ray whose first hit
            is well below the top face is inside a pocket. Pocket spans give
            centres, centre spacing gives pitch.
  af      — cast a ray along +y at each pocket centre, mid-depth (below the
            mouth break): the middle crossing pair spans the across-flats —
            hex flats are normal to Y by design, so this reads the wall
            planes directly.
  depth   — a downward ray at the pocket centre lands on the floor; depth is
            the drop from the top face. The floor sits 0.01 low (the pocket
            cutter overshoots to avoid a coplanar face), hence depth_tol.
"""
import sys
import os
import numpy as np
import trimesh

BUILD = os.path.join(os.path.dirname(__file__), "..", "..", "build")

# Expected values — from the BRIEF and the design's parameters (issue #594):
# what the mesh must measure, not what the .scad happens to type.
BIT_AF = 6.35
RAIL_W = 40.0
FLOOR_T = 2.4
MOUTH_BREAK = 0.6
PARTS = {
    "hex-bit-rail-rail-short.stl": dict(
        pockets=12, pitch=16.0, depth=12.0, fits=[0.1] * 12, label_w=0.0),
    "hex-bit-rail-rail-long.stl": dict(
        pockets=12, pitch=16.0, depth=18.0, fits=[0.1] * 12, label_w=0.0),
    "hex-bit-rail-coupon.stl": dict(
        pockets=6, pitch=24.0, depth=12.0,
        fits=[-0.15, -0.15, 0, 0, 0.15, 0.15], label_w=0.4),
}
AF_TOL = 0.02        # hex flats are planar: tessellation-exact
DEPTH_TOL = 0.05     # + the 0.01 floor-overshoot
# pitch comes from pocket-span midpoints, and the span scan steps 0.25 mm —
# a midpoint quantizes to ±0.125, so the tolerance must be looser than the
# method's own resolution (a real pitch drift moves it by ≥ 1 mm)
PITCH_TOL = 0.2
FAILS = []


def fail(msg):
    FAILS.append(msg)
    print(f"  FAIL  {msg}")


def pocket_spans(mesh, top_z, y=0.3):
    """X-spans of the pockets, from downward rays strafing the rail axis."""
    x0, x1 = mesh.bounds[0][0] + 0.2, mesh.bounds[1][0] - 0.2
    xs = np.arange(x0, x1, 0.25)
    origins = np.column_stack([xs, np.full_like(xs, y),
                               np.full_like(xs, top_z + 10.0)])
    hits, _, _ = mesh.ray.intersects_location(
        origins, np.tile([0, 0, -1], (len(xs), 1)), multiple_hits=False)
    # every ray hits something (top face or pocket floor), one hit each; map
    # each hit back to its ray by exact x
    hit_z = np.full(len(xs), np.nan)
    idx = np.abs(hits[:, 0][:, None] - xs[None, :]).argmin(axis=1)
    hit_z[idx] = hits[:, 2]
    inside = hit_z < top_z - 0.5  # first hit well below the top face
    spans, start = [], None
    for i, is_in in enumerate(inside):
        if is_in and start is None:
            start = xs[i]
        elif not is_in and start is not None:
            spans.append((start, xs[i - 1]))
            start = None
    if start is not None:
        spans.append((start, xs[-1]))
    return spans


def y_crossings(mesh, x, z):
    origins = np.array([[x, mesh.bounds[0][1] - 5.0, z]])
    dirs = np.array([[0.0, 1.0, 0.0]])
    hits, _, _ = mesh.ray.intersects_location(origins, dirs,
                                              multiple_hits=True)
    return np.sort(hits[:, 1])


def main():
    for fname, exp in PARTS.items():
        path = os.path.join(BUILD, fname)
        if not os.path.exists(path):
            fail(f"{fname}: not built — run scripts/gate.sh hex-bit-rail first")
            continue
        mesh = trimesh.load(path)
        print(f"== {fname} ==")
        if mesh.body_count != 1 or not mesh.is_watertight:
            fail(f"{fname}: bodies={mesh.body_count} "
                 f"watertight={mesh.is_watertight} (need 1 / True)")
        ext = mesh.extents
        # footprint: rails 200 x 40; coupon 152 x (18 + label protrusion)
        if "coupon" in fname:
            ok_w = (18.0 - 0.01) <= ext[1] <= (18.0 + exp["label_w"] + 0.05)
        else:
            ok_w = abs(ext[1] - RAIL_W) <= 0.1
        print(f"  footprint {ext[0]:.2f} x {ext[1]:.2f} x {ext[2]:.2f} mm")
        if not ok_w:
            fail(f"{fname}: width {ext[1]:.2f} outside expectation")
        top_z = mesh.bounds[1][2]
        floor_z = FLOOR_T - 0.01  # the pocket cutter overshoots 0.01 low
        spans = pocket_spans(mesh, top_z)
        print(f"  pockets found: {len(spans)} (expected {exp['pockets']})")
        if len(spans) != exp["pockets"]:
            fail(f"{fname}: {len(spans)} pockets in mesh, "
                 f"expected {exp['pockets']}")
            continue
        centres = [(a + b) / 2 for a, b in spans]
        pitch = np.diff(centres)
        print(f"  pitch {pitch.min():.3f}..{pitch.max():.3f} "
              f"(expected {exp['pitch']})")
        if np.any(np.abs(pitch - exp["pitch"]) > PITCH_TOL):
            fail(f"{fname}: pitch off — {sorted(set(pitch.round(3)))}")
        # mid-depth: below the mouth break. On a labelled part (the coupon)
        # the embossed glyphs at the pocket centres top out near
        # floor_t + 1.5 + cap height + offset ≈ 8.4 — exactly where the
        # mid-depth ray sits — so lift the ray above the glyph band while
        # staying under the break region (h - mouth_break - 0.5 = 13.3).
        z_mid = top_z - 3.5 if exp["label_w"] else (top_z + floor_z) / 2
        for cx, fit in zip(centres, exp["fits"]):
            cr = y_crossings(mesh, cx, z_mid)
            tag = f"pocket@x={cx:7.2f}"
            if len(cr) != 4:
                fail(f"{fname}: {tag} y-ray crossings={len(cr)} (need 4)")
                continue
            af = cr[2] - cr[1]
            wall_f, wall_b = cr[1] - cr[0], cr[3] - cr[2]
            want_af = BIT_AF + fit
            ok = abs(af - want_af) <= AF_TOL
            print(f"  {tag}  af={af:.3f} (expected {want_af:.3f})  "
                  f"walls {wall_f:.2f}/{wall_b:.2f}"
                  + ("" if ok else "  <-- OFF"))
            if not ok:
                fail(f"{fname}: {tag} af {af:.3f} != {want_af:.3f}")
            if abs(wall_f - wall_b) > 0.1:
                fail(f"{fname}: {tag} pocket not centred "
                     f"({wall_f:.2f} vs {wall_b:.2f})")
        # depth at the first pocket centre
        origins = np.array([[centres[0], 0.3, top_z + 10.0]])
        hits, _, _ = mesh.ray.intersects_location(
            origins, np.array([[0, 0, -1.0]]), multiple_hits=False)
        depth = top_z - hits[0][2]
        print(f"  depth {depth:.3f} (expected {exp['depth']:.3f})")
        if abs(depth - exp["depth"]) > DEPTH_TOL:
            fail(f"{fname}: depth {depth:.3f} != {exp['depth']:.3f}")

    print()
    if FAILS:
        print(f"measure_fit: {len(FAILS)} measurement(s) OUT of tolerance")
        return 1
    print("measure_fit: every measurement inside tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
