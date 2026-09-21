#!/usr/bin/env python3
"""tumble_stops.py — derivation of the ovodyo tumble-to-index stop table (charter N2).

The design's soul is that a fresh flat face LANDS UPRIGHT at each stop. The
mechanism is an epicyclic bevel differential inside the ball: a fixed bevel sun
(n_sun teeth) on the stator stalk, a yoke turned about the world vertical by the
yoke angle phi, and the ball's pole-to-pole hub axle mounted horizontal in the
yoke carrying a bevel crown (n_crown teeth) that rolls around the fixed sun, so
the ball spins about its own axle by -rho*phi with rho = n_sun/n_crown.

This script is the single source of the numbers tumble.scad carries: it builds
the 12 plaque normals exactly as the design does (gb_icosa_verts() order, then
the design's pole-up rotation), poses them with the mount M and Q(phi), sweeps
the yoke over one full cycle, finds every plaque's landing events, picks the
12-stop table, and derives the per-face in-plane numeral rotation that makes
each numeral read upright at its own stop.

Frames (all right-handed; rotations follow OpenSCAD's rotate() convention):
  WORLD     +x points at the viewer (the presenting direction F), +z up.
  BALL      the pole-up frame of ovodyo.scad: the generator's output rotated by
            rotate([_pole_up,0,0]) so a pentagon plaque sits at each +-z pole;
            ball +z is the hub axle (the 5-fold axis).
  MOUNT M   rotate([-90,0,0]) — carries ball +z (the pole axis) onto world +y.
  Q(phi)    Rz(phi) * Ry(-rho*phi) * M   (world <- ball) — the yoke turns +phi
            about world +z while the crown spins the ball -rho*phi about its
            own axle (see tumble.scad's header for the physical sign).

Regenerate / verify the baked block in tumble.scad:
    python3 designs/ovodyo/tumble_stops.py            # print the block + report
    python3 designs/ovodyo/tumble_stops.py --check    # exit 1 if tumble.scad drifted
    python3 designs/ovodyo/tumble_stops.py --write    # splice the block into tumble.scad

stdlib + numpy only.
"""
import math
import os
import sys

import numpy as np

# ---- constants (mirror tumble.scad) -----------------------------------------
PHI = (1 + math.sqrt(5)) / 2
N_SUN = 12
N_CROWN = 20
RHO = N_SUN / N_CROWN          # 3/5: crown turns per yoke turn
TOL_DEG = 3.0                  # a plaque "lands" when its normal is within this of +x
EVENT_DEG = 6.0                # candidate landing events: local minima below this
SWEEP_STEP = 0.25              # yoke sweep resolution (deg)
CYCLE_TURNS = 5                # Q(phi + 5*360) == Q(phi): Rz(1800)=I, Ry(-1080)=I
CYCLE_DEG = CYCLE_TURNS * 360
POLE_UP_DEG = math.degrees(math.atan2(1, PHI))   # ovodyo.scad's _pole_up

HERE = os.path.dirname(os.path.abspath(__file__))
TUMBLE_SCAD = os.path.join(HERE, "tumble.scad")
BAKED_BEGIN = "// ---- BAKED by tumble_stops.py"
BAKED_END = "// ---- end BAKED"


# ---- rotations (OpenSCAD conventions) ---------------------------------------
def Rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


def Ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)


def Rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def Raxis(a, v):
    """OpenSCAD rotate(a=..., v=...): right-hand rotation by a degrees about v."""
    v = np.asarray(v, dtype=float)
    v = v / np.linalg.norm(v)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    t = math.radians(a)
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * (K @ K)


def align_z_to(d):
    """geodesic-ball.scad's _gb_align_z_to(dir): the rotation taking +z to d."""
    d = np.asarray(d, dtype=float)
    d = d / np.linalg.norm(d)
    ax = np.array([-d[1], d[0], 0.0])              # cross([0,0,1], d)
    if np.linalg.norm(ax) < 1e-9:
        return np.eye(3) if d[2] >= 0 else Rx(180)
    return Raxis(math.degrees(math.acos(max(-1.0, min(1.0, d[2])))), ax)


def gb_icosa_verts():
    """geodesic-ball.scad's gb_icosa_verts(): the 12 plaque normals, in order."""
    P = PHI
    return np.array([
        [0, 1, P], [0, 1, -P], [0, -1, P], [0, -1, -P],
        [1, P, 0], [1, -P, 0], [-1, P, 0], [-1, -P, 0],
        [P, 0, 1], [P, 0, -1], [-P, 0, 1], [-P, 0, -1],
    ], dtype=float)


M = Rx(-90)                                        # ball +z (pole) -> world +y
F = np.array([1.0, 0.0, 0.0])                      # presenting direction
UP = np.array([0.0, 0.0, 1.0])


def Q(phi):
    return Rz(phi) @ Ry(-RHO * phi) @ M


def angle_deg(a, b):
    # atan2 form: exact near 0 where acos(dot) loses every digit (the pole
    # plaques land at exactly 0 deg and must tie exactly across their events).
    return math.degrees(math.atan2(float(np.linalg.norm(np.cross(a, b))), float(np.dot(a, b))))


# ---- the derivation ---------------------------------------------------------
def face_normals_ball():
    """The 12 plaque normals in the pole-up BALL frame, gb_icosa_verts() order."""
    V = gb_icosa_verts()
    V = V / np.linalg.norm(V, axis=1)[:, None]
    return (Rx(POLE_UP_DEG) @ V.T).T


def numeral_up_ball(rot_deg=None):
    """Each numeral's in-plane 'up' (its 2D +y) in the BALL frame, as gb_numbers
    places it: _gb_align_z_to(dir) [rotate rot about the face normal] then the
    pole-up rotation. rot_deg=None means the un-rotated placement."""
    V = gb_icosa_verts()
    ups = []
    for i, v in enumerate(V):
        r = 0.0 if rot_deg is None else rot_deg[i]
        u = align_z_to(v) @ Rz(r) @ np.array([0.0, 1.0, 0.0])
        ups.append(Rx(POLE_UP_DEG) @ u)
    return np.array(ups)


def landing_angle(phi, n_ball):
    return angle_deg(Q(phi) @ n_ball, F)


def refine_min(f, lo, hi, iters=80):
    """Ternary search for the minimum of a unimodal f on [lo, hi]."""
    for _ in range(iters):
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3
        if f(m1) < f(m2):
            hi = m2
        else:
            lo = m1
    x = (lo + hi) / 2
    return x, f(x)


def landing_events(n_ball):
    """All local minima of the angle to F below EVENT_DEG over one cycle, refined."""
    phis = np.arange(0.0, CYCLE_DEG, SWEEP_STEP)
    ang = np.array([landing_angle(p, n_ball) for p in phis])
    n = len(ang)
    events = []
    for j in range(n):
        a, b, c = ang[j - 1], ang[j], ang[(j + 1) % n]
        if b < a and b <= c and b < EVENT_DEG:
            phi_r, err = refine_min(lambda p: landing_angle(p, n_ball),
                                    phis[j] - SWEEP_STEP, phis[j] + SWEEP_STEP)
            events.append((phi_r % CYCLE_DEG, err))
    return sorted(events)


def derive():
    N = face_normals_ball()
    U0 = numeral_up_ball()
    all_events = [landing_events(N[i]) for i in range(12)]
    for i, ev in enumerate(all_events):
        assert ev, f"face {i} never lands within {EVENT_DEG} deg of +x in one cycle"

    # The 12-stop table with the smallest max error: every face must appear
    # once, so choosing each face's best event minimises the max (ties: the
    # earliest yoke angle); sorting by yoke angle makes the table monotone.
    picked = []
    for i, ev in enumerate(all_events):
        best = min(ev, key=lambda e: (round(e[1], 4), round(e[0], 4)))   # ties at the baked precision
        picked.append((best[0], i, best[1]))
    picked.sort()
    stops = [p[0] for p in picked]
    face_order = [p[1] for p in picked]
    errors = [p[2] for p in picked]
    max_err = max(errors)

    # Per-face in-plane numeral rotation: at its own stop, rotate the numeral
    # about the face normal so its 'up' maps onto world +z (projected into the
    # plaque plane — the residual is the landing tilt itself).
    rots = [0.0] * 12
    up_err = [0.0] * 12
    for k in range(12):
        f, phi = face_order[k], stops[k]
        Qk = Q(phi)
        n_w = Qk @ N[f]
        u0_w = Qk @ U0[f]
        t = UP - float(np.dot(UP, n_w)) * n_w
        t = t / np.linalg.norm(t)
        rot = math.degrees(math.atan2(float(np.dot(np.cross(u0_w, t), n_w)),
                                      float(np.dot(u0_w, t))))
        rots[f] = rot
    # verify the rotations exactly the way the geometry applies them
    U1 = numeral_up_ball(rots)
    for k in range(12):
        f, phi = face_order[k], stops[k]
        up_err[k] = angle_deg(Q(phi) @ U1[f], UP)

    crown = [-RHO * p for p in stops]
    return dict(stops=stops, face_order=face_order, errors=errors, max_err=max_err,
                rots=rots, up_err=up_err, crown=crown, events=all_events, N=N)


# ---- output -----------------------------------------------------------------
def fmt(x):
    s = f"{x:.4f}"
    return "0.0000" if s == "-0.0000" else s


def baked_block(d):
    lines = [
        BAKED_BEGIN + " — do not edit by hand. Regenerate + verify with:",
        "// ----   python3 designs/ovodyo/tumble_stops.py --write   (then --check)",
        "// Yoke angle (deg) of stop k; stop k presents numeral k (0 = \"12\"/\"00\").",
        "function tumble_stops() = [" + ", ".join(fmt(x) for x in d["stops"]) + "];",
        "// Face (gb_icosa_verts() index) presented at stop k — numeral k lives there.",
        "function tumble_face_order() = [" + ", ".join(str(x) for x in d["face_order"]) + "];",
        "// Landing error (deg) of stop k: the presented normal's angle off +x.",
        "function tumble_errors() = [" + ", ".join(fmt(x) for x in d["errors"]) + "];",
        "// Per-FACE in-plane numeral rotation (deg, CCW seen from outside) so the",
        "// numeral on face f reads upright at its own stop.",
        "function tumble_rots() = [" + ", ".join(fmt(x) for x in d["rots"]) + "];",
        BAKED_END,
    ]
    return "\n".join(lines) + "\n"


def report(d):
    numerals = ["12", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
    out = []
    out.append(f"# ovodyo tumble stops: rho = {N_SUN}/{N_CROWN} = {RHO:g}, tol {TOL_DEG:g} deg, "
               f"sweep {SWEEP_STEP:g} deg over {CYCLE_TURNS} yoke turns ({CYCLE_DEG} deg)")
    out.append("# M = Rx(-90): ball +z (pole) -> world +y; Q(phi) = Rz(phi) Ry(-rho phi) M; F = +x")
    out.append("#")
    out.append("# landing events per face (yoke deg : error deg):")
    for i, ev in enumerate(d["events"]):
        out.append(f"#   face {i:2d}: " + "  ".join(f"{p:8.3f}:{e:.3f}" for p, e in ev))
    out.append("#")
    out.append("# stop  numeral  face   yoke(deg)   step(deg)  error(deg)  numeral-up err(deg)  rot(deg)  crown(deg)")
    for k in range(12):
        step = d["stops"][k] - d["stops"][k - 1] if k else d["stops"][0] + CYCLE_DEG - d["stops"][11]
        f = d["face_order"][k]
        out.append(f"#  {k:3d}    {numerals[k]:>3}    {f:3d}   {d['stops'][k]:9.4f}   {step:8.4f}   "
                   f"{d['errors'][k]:7.4f}      {d['up_err'][k]:7.4f}        {d['rots'][f]:9.4f}  {d['crown'][k]:9.4f}")
    span = d["stops"][11] - d["stops"][0]
    out.append(f"# max landing error {d['max_err']:.4f} deg (tol {TOL_DEG:g}); stops span {span:.1f} deg of yoke;")
    out.append(f"# cycle closes after {CYCLE_TURNS} yoke turns ({CYCLE_DEG} deg) = {CYCLE_TURNS * RHO:g} crown turns")
    cmin, cmax = min(d["crown"]), max(d["crown"])
    out.append(f"# crown-angle range over the table (stalk-gap sweep): [{cmin:.4f}, {cmax:.4f}] deg, "
               f"span {cmax - cmin:.1f} deg{' (> 360: the stalk sweeps the whole equator)' if cmax - cmin > 360 else ''}")
    stop_of_face = [d["face_order"].index(f) for f in range(12)]
    out.append("# numerals by face (gb_numbers order): [" +
               ", ".join(f'"{numerals[stop_of_face[f]]}"' for f in range(12)) + "]")
    upper = [numerals[stop_of_face[f]] for f in range(12) if d["N"][f][2] > 1e-6]
    lower = [numerals[stop_of_face[f]] for f in range(12) if d["N"][f][2] < -1e-6]
    out.append(f"# hemispheres of the pole-up split: top (+z) carries {upper}; bottom (-z) carries {lower}")
    return "\n".join(out) + "\n"


def read_baked(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    i = text.find(BAKED_BEGIN)
    j = text.find(BAKED_END)
    if i < 0 or j < 0:
        return text, None
    j_end = text.find("\n", j) + 1
    return text, (i, j_end)


def main(argv):
    d = derive()
    block = baked_block(d)
    rep = report(d)
    if "--write" in argv:
        text, span = read_baked(TUMBLE_SCAD)
        if span is None:
            sys.exit(f"tumble_stops.py: no baked block markers in {TUMBLE_SCAD}")
        with open(TUMBLE_SCAD, "w", encoding="utf-8") as fh:
            fh.write(text[:span[0]] + block + text[span[1]:])
        print(f"wrote baked block into {TUMBLE_SCAD}")
    elif "--check" in argv:
        text, span = read_baked(TUMBLE_SCAD)
        if span is None:
            sys.exit(f"tumble_stops.py: no baked block markers in {TUMBLE_SCAD}")
        if text[span[0]:span[1]] != block:
            sys.stdout.write(rep)
            sys.stdout.write(block)
            sys.exit(f"tumble_stops.py: {TUMBLE_SCAD} baked block DRIFTED from the derivation — "
                     "rerun with --write")
        print(f"ok    tumble_stops.py: {TUMBLE_SCAD} carries exactly the derived block "
              f"(max landing error {d['max_err']:.4f} deg <= {TOL_DEG:g})")
    else:
        sys.stdout.write(rep)
        sys.stdout.write(block)
    assert d["max_err"] <= TOL_DEG, f"max landing error {d['max_err']:.4f} deg exceeds tol {TOL_DEG}"
    assert max(d["up_err"]) <= TOL_DEG, f"numeral-up error {max(d['up_err']):.4f} deg exceeds tol {TOL_DEG}"
    assert sorted(d["face_order"]) == list(range(12)), "every face must be presented exactly once"
    assert all(b > a for a, b in zip(d["stops"], d["stops"][1:])), "stops must be monotone in yoke angle"


if __name__ == "__main__":
    main(sys.argv[1:])
