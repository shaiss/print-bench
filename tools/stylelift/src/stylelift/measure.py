"""Geometric measurement of a mesh's *style*: how the form is shaped.

The whole tool rests on one identity. Tessellate a cylinder of radius r as an
inscribed prism and every fold between neighbouring strips turns by the same
angle theta, while each strip is a chord of width w = 2 r sin(theta/2). Read
backwards, a fold with turn theta between two strips of width w sits on a
surface of local radius

    r = w / (2 sin(theta / 2))

That estimate is *exact* for an inscribed tessellation, and — the useful part —
independent of how finely the curve was tessellated: a cylinder exported at
$fn=24 and the same cylinder at $fn=64 both measure r to the last decimal. It
is also invariant under rotation and covariant under scale, so a downloaded STL
in an arbitrary pose measures the same as one resting on the bed.

Everything here is deterministic: no sampling without a fixed seed, no AI, no
network.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import trimesh


@dataclass
class Config:
    """Thresholds separating tessellation noise from deliberate shaping."""

    # A fold below this is the mesher's rounding error, not a design edge.
    flat_deg: float = 0.5
    # A single fold turning more than this reads as a hard edge, not a curve.
    soft_max_deg: float = 40.0
    # Beyond this no band interpretation is attempted at all.
    band_max_deg: float = 75.0
    # A chamfer's bounding folds turn at least this much.
    chamfer_min_deg: float = 15.0
    # ...and cuts back at least this far. Shallower than an extrusion width
    # nobody designed it and nobody could print it: on an organic mesh those
    # slivers are where the tessellation crosses a curvature change.
    min_chamfer_mm: float = 0.3
    # A curve wider than the part is not an edge treatment (it gets filed as
    # form); wider than this multiple of the part it is not a curve at all,
    # just a nominally flat surface tessellated with sub-degree folds.
    noise_radius_multiple: float = 5.0
    # Two strips of a common curved band have comparable width; a curve meeting
    # a large flat face does not. Guards the radius estimate at tangent joins.
    width_ratio: float = 3.0
    # How much narrower than its neighbours a band must be to read as a chamfer
    # rather than one facet of a coarsely drawn curve. Deliberately separate
    # from width_ratio above: that one guards an arithmetic estimate, this one
    # answers a question about design intent.
    chamfer_width_ratio: float = 1.6
    # A band whose two ends differ in width by more than this is tapered: a
    # cone's strip, not a cylinder's, and the radius identity does not apply.
    taper_tol: float = 1.15
    # A fold turning less than this fraction of what the folds around it turn
    # is where an arc runs tangent into a flat face, not part of the arc.
    turn_consistency: float = 0.7
    # Radius modes: half-width of the refinement window, and the share of
    # folded length below which a mode is noise rather than vocabulary.
    mode_tol: float = 0.12
    mode_min_share: float = 0.05
    # A curved band whose folds sum to this much has closed on itself.
    closed_turn_deg: float = 350.0
    thickness_samples: int = 2000
    symmetry_samples: int = 1500
    # Faces within this of the build direction count as vertical walls.
    vertical_tol_deg: float = 5.0
    # A downward surface shallower than this (measured from horizontal) will
    # not print without support. 45 deg is the FDM convention.
    overhang_limit_deg: float = 45.0
    # A face this close to the lowest point counts as sitting on the bed.
    bed_tol_mm: float = 0.01
    # --- the faceted, cut-through look -------------------------------------
    # What separates a design facet from the mesh's own tessellation is the
    # curve resolution the mesh itself declares: a fold turning no more than
    # one segment of the finest curve the part draws is that curve's
    # tessellation, whatever its absolute angle. When a part draws no curve at
    # all there is nothing to normalise against, so the smooth-curve
    # convention stands in (a curve a design means to be smooth is drawn at
    # $fn >= 48, i.e. folds of 7.5 degrees or less).
    fn_curve_fallback: int = 48
    # Absorbs the spread in a measured segment count (the mode's median turn
    # wobbles by about a segment) without letting a genuinely steeper fold
    # through.
    tessellation_slack: float = 1.1
    # Edges of the sharpness histogram, in degrees of fold turn. A readable
    # ladder rather than even bins: the interesting action is between "finest
    # drawn curve" (~5 deg at $fn=64) and "corner" (90).
    histogram_bins_deg: tuple = (0.5, 2, 5, 10, 20, 35, 55, 90, 180)
    # --- openness (projected void fraction) ---------------------------------
    # Directions sampled on the sphere, and parallel lines sampled per
    # direction, for the pose-stable void integral. Deterministic: a Fibonacci
    # lattice for the directions, a golden-spiral disc for the offsets, no
    # randomness anywhere.
    void_dirs: int = 48
    void_rays_per_dir: int = 32


def load_mesh(path: str | Path) -> trimesh.Trimesh:
    """Load a mesh and merge duplicate vertices so folds are measurable.

    STL stores every triangle with its own copy of each vertex; without the
    merge there is no face adjacency at all and every edge looks like a
    boundary.
    """
    loaded = trimesh.load(str(path), force="mesh", process=False)
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"{path}: no triangle mesh found in file")
    loaded.merge_vertices()
    return loaded


def _facet_groups(mesh: trimesh.Trimesh):
    """Coplanar face groups, plus the group index of every face (-1 = alone)."""
    groups = [np.asarray(g) for g in mesh.facets]
    index = -np.ones(len(mesh.faces), dtype=np.int64)
    for i, g in enumerate(groups):
        index[g] = i
    return groups, index


def _strip_widths(mesh: trimesh.Trimesh, groups, index):
    """Per adjacency, how wide each side's facet is *across* the shared fold.

    Measured perpendicular to the fold and inside the facet's own plane, which
    is what the radius identity wants: for a tapering band (a cone, a sphere's
    polar cap) the across-fold extent is still the chord that turned, where a
    bounding-box or minor-extent measure would pick up the band's length
    instead. Returns (widths[n, 2], facet_key[n, 2]) — the key identifies the
    facet on each side so callers can group folds by the facet they bound.
    """
    pairs = mesh.face_adjacency
    edges = mesh.face_adjacency_edges
    verts = mesh.vertices
    widths = np.zeros((len(pairs), 2))
    taper = np.ones((len(pairs), 2))
    keys = np.zeros((len(pairs), 2), dtype=np.int64)
    cache: dict[int, np.ndarray] = {}

    def facet_vertices(face: int) -> tuple[np.ndarray, int]:
        g = int(index[face])
        # faces in no coplanar group get a private key that cannot collide
        # with a group index
        key = g if g >= 0 else -1 - int(face)
        if key not in cache:
            faces = groups[g] if g >= 0 else np.array([face])
            cache[key] = verts[np.unique(mesh.faces[faces].ravel())]
        return cache[key], key

    for k in range(len(pairs)):
        edge = verts[edges[k, 1]] - verts[edges[k, 0]]
        length = np.linalg.norm(edge)
        if length == 0:
            continue
        edge = edge / length
        for side in (0, 1):
            face = int(pairs[k, side])
            v, key = facet_vertices(face)
            keys[k, side] = key
            across = np.cross(mesh.face_normals[face], edge)
            n = np.linalg.norm(across)
            if n == 0:
                continue
            span = v @ (across / n)
            widths[k, side] = float(np.ptp(span))
            # Is the band parallel-sided, or does it converge? A cylinder's
            # strip is a rectangle; a cone's is a trapezoid. The radius
            # identity assumes the first, so measure the across-fold width at
            # both ends of the shared edge and let the caller drop the folds
            # where the two disagree — otherwise a plain tapered boss reports
            # a "corner radius" nothing in the model has.
            along = v @ edge
            # Is the band parallel-sided, or does it converge? A cylinder's
            # strip is a rectangle, a cone's a trapezoid, and the identity
            # above assumes the first. Which way the trapezoid narrows depends
            # on how the cone was tessellated: with the folds running up the
            # generators the chords shrink along the band, with the folds
            # running around the rim the band's length shrinks across it.
            # Measure both and keep the stronger — checking only one axis finds
            # cones in one tessellation and misses them in the other.
            if len(v) >= 4:
                for axis, other in ((along, span), (span, along)):
                    if float(np.ptp(axis)) <= 0:
                        continue
                    middle = float(np.median(axis))
                    near, far = axis <= middle, axis > middle
                    if near.sum() < 2 or far.sum() < 2:
                        continue
                    a, b = float(np.ptp(other[near])), float(np.ptp(other[far]))
                    if min(a, b) > 1e-9:
                        taper[k, side] = max(taper[k, side],
                                             max(a, b) / min(a, b))
    return widths, taper, keys


def radius_modes(radii: np.ndarray, weights: np.ndarray, cfg: Config) -> list[dict]:
    """The radii a shape actually reuses, as length-weighted modes.

    A design language is a *small* set of reused radii, so the useful statistic
    is the mode, not the mean or median: on a part whose edges are all r=3 but
    whose corners are spherical, the sphere's polar tessellation smears the
    median while the r=3 mode still carries the overwhelming majority of folded
    length. Peaks are found in a log-spaced histogram (radii span decades) and
    then refined off the histogram grid by the weighted median of the folds
    inside the peak, so the reported value does not inherit the bin width.
    """
    ok = np.isfinite(radii) & (radii > 0)
    radii, weights = radii[ok], weights[ok]
    if not len(radii) or weights.sum() <= 0:
        return []
    total = float(weights.sum())
    lo, hi = float(radii.min()) * 0.98, float(radii.max()) * 1.02
    if not np.isfinite(lo) or lo <= 0 or hi <= lo:
        return [{"r_mm": round(float(np.median(radii)), 4), "share": 1.0,
                 "length_mm": round(total, 3)}]
    counts, edges = np.histogram(radii, bins=np.geomspace(lo, hi, 64),
                                 weights=weights)
    modes: list[dict] = []
    claimed = np.zeros(len(radii), dtype=bool)
    for i in np.argsort(counts)[::-1]:
        if counts[i] <= 0:
            break
        centre = float(np.sqrt(edges[i] * edges[i + 1]))
        window = ((~claimed) & (radii > centre * (1 - cfg.mode_tol))
                  & (radii < centre * (1 + cfg.mode_tol)))
        if not window.any():
            continue
        claimed |= window
        w, r = weights[window], radii[window]
        order = np.argsort(r)
        cumulative = np.cumsum(w[order])
        value = float(r[order][np.searchsorted(cumulative, cumulative[-1] / 2)])
        share = float(w.sum() / total)
        if share >= cfg.mode_min_share:
            modes.append({"r_mm": round(value, 4), "share": round(share, 4),
                          "length_mm": round(float(w.sum()), 3)})
    return sorted(modes, key=lambda m: -m["share"])


def _edge_treatment(mesh: trimesh.Trimesh, cfg: Config) -> dict:
    """Fold-by-fold analysis: what the shape does at every change of direction."""
    angles = np.asarray(mesh.face_adjacency_angles, dtype=float)
    pairs = mesh.face_adjacency
    edges = mesh.face_adjacency_edges
    convex = np.asarray(mesh.face_adjacency_convex, dtype=bool)
    verts = mesh.vertices
    if not len(angles):
        return {"folds": 0}
    lengths = np.linalg.norm(verts[edges[:, 0]] - verts[edges[:, 1]], axis=1)

    groups, index = _facet_groups(mesh)
    widths, taper, keys = _strip_widths(mesh, groups, index)

    flat = angles < np.radians(cfg.flat_deg)
    soft = (~flat) & (angles <= np.radians(cfg.soft_max_deg))
    hard = (~flat) & (angles > np.radians(cfg.soft_max_deg))
    soft_len, hard_len = float(lengths[soft].sum()), float(lengths[hard].sum())
    shaped = soft_len + hard_len

    # --- pass 1: chamfer bands -------------------------------------------
    # A chamfer is a single flat band that bridges two faces across a decisive
    # fold. What separates it from one strip of a coarsely tessellated curve is
    # *topology, not size*: a chamfer stands alone between two ordinary faces,
    # while a curve's strip continues into another strip just like it.
    #
    # Deciding this by comparing the band's width against its neighbour's is
    # what an earlier version did, and it broke on exactly the parts this tool
    # exists to measure: put the same 0.6 mm chamfer on a 3 mm plate instead of
    # an 8 mm one and the neighbouring wall becomes short enough to look
    # "comparable", after which the chamfer is read as a curve and the part
    # reports a corner radius it does not have.
    band = (~flat) & (angles <= np.radians(cfg.band_max_deg))
    candidate = band & (angles > np.radians(cfg.chamfer_min_deg))

    # Both sides of every decisive fold, so each facet's own width and its
    # neighbours' are known together.
    by_facet: dict[int, dict[int, list]] = {}
    for k in np.where(candidate)[0]:
        for side in (0, 1):
            facet, other = int(keys[k, side]), int(keys[k, 1 - side])
            by_facet.setdefault(facet, {}).setdefault(other, []).append(
                (float(angles[k]), float(widths[k, side]),
                 float(widths[k, 1 - side]), float(lengths[k]), bool(convex[k])))

    chamfer_facets: set[int] = set()
    bands: list[dict] = []
    for facet, sides in by_facet.items():
        if len(sides) < 2:
            continue
        # The band's two long sides are the folds carrying the most edge
        # length. A chamfer running along a box edge also meets the little
        # mitre pieces at each end, so demanding exactly two neighbours would
        # miss every chamfer on a part with square corners.
        principal = sorted(sides.values(),
                           key=lambda entries: -sum(e[3] for e in entries))[:2]
        turn = 0.0
        length_total = 0.0
        widths_seen = []
        neighbour_widths = []
        convexity = []
        for entries in principal:
            w = np.array([e[3] for e in entries])
            a = np.degrees([e[0] for e in entries])
            turn += float(np.average(a, weights=w) if w.sum() else a.mean())
            length_total += float(w.sum())
            widths_seen += [e[1] for e in entries]
            neighbour_widths.append(float(np.median([e[2] for e in entries])))
            convexity += [e[4] for e in entries]
        width = float(np.median(widths_seen))
        # A chamfer is *narrow between wide*. An octagonal prism and a cylinder
        # drawn at $fn=8 have identical topology — both are eight faces meeting
        # at eight 45-degree folds — and the only thing that says "these four
        # are chamfers on a box" rather than "this is a coarse circle" is that
        # they are much narrower than what they sit between. Compared against
        # the *narrower* neighbour, so a chamfer next to a short wall still
        # reads as a chamfer.
        if width <= 0 or min(neighbour_widths) < cfg.chamfer_width_ratio * width:
            continue
        # A symmetric chamfer cutting a corner of total turn T with equal legs
        # c presents a face of width w = 2 c cos(T/2).
        half = np.radians(min(turn, 179.0)) / 2
        leg = width / (2 * np.cos(half)) if np.cos(half) > 1e-6 else width
        if leg < cfg.min_chamfer_mm:
            continue
        chamfer_facets.add(facet)
        bands.append({"leg_mm": round(leg, 4), "width_mm": round(width, 4),
                      "turn_deg": round(turn, 2),
                      "length_mm": round(length_total, 3),
                      "convex": bool(np.mean(convexity) >= 0.5)})

    # --- pass 2: rounding vocabulary --------------------------------------
    # Any fold touching a chamfer band is chamfer geometry and has already been
    # accounted as such: its own bounding folds, and — where a chamfer is swept
    # around a corner or a bore, making it a cone or a torus slice — the folds
    # within it. Letting either kind through would invent a radius the designer
    # never chose.
    on_chamfer = np.array([
        (int(keys[k, 0]) in chamfer_facets) or (int(keys[k, 1]) in chamfer_facets)
        for k in range(len(angles))]) if chamfer_facets else np.zeros(len(angles), bool)

    # `comparable` still guards the radius estimate itself: where a curve meets
    # a large flat face the fold is half-sized, which would report twice the
    # true radius. That is a different job from telling a chamfer from a curve,
    # which pass 1 now decides on topology.
    wmin = np.minimum(widths[:, 0], widths[:, 1])
    wmax = np.maximum(widths[:, 0], widths[:, 1])
    comparable = (wmin > 0) & (wmax <= cfg.width_ratio * wmin)

    # Both sides converging means the surface is a cone, not a cylinder, and it
    # has no single radius to report. Without this a plain tapered boss claims
    # a corner radius — and one measured off the taper angle, so it belongs to
    # no feature of the part at all.
    # Both guards below read the shape of a *strip*, so they only apply where
    # the mesh actually has strips: a facet key of -1 is a lone triangle, whose
    # width necessarily narrows to a point and whose fold angles carry no strip
    # ordering. On triangle soup they would filter folds arbitrarily and shift
    # the very radii the tessellation note already warns are approximate.
    strip_fold = (keys[:, 0] >= 0) & (keys[:, 1] >= 0)
    # Either side converging is enough: a fold between a flat plate and the
    # side of a tapered boss is not a cylinder fold on anybody's reading, and
    # letting it through is what made a bar with one plain draft-angled boss
    # report a corner radius.
    conical = strip_fold & (np.maximum(taper[:, 0], taper[:, 1]) > cfg.taper_tol)

    # A tessellated arc turns by the same angle at every interior fold, and by
    # half that where it runs tangent into the flat face it joins. On a coarse
    # curve those tangent folds pass the width test — the strips are wide
    # enough to look comparable — and each one contributes a radius twice the
    # true one. Compare every fold against the folds around it: a fold turning
    # much less than its own neighbours is a joint, not part of the arc.
    turn_ref = np.zeros(len(angles))
    facet_turn: dict[int, list] = {}
    for k in np.where(band)[0]:
        for side in (0, 1):
            facet_turn.setdefault(int(keys[k, side]), []).append(float(angles[k]))
    medians = {f: float(np.median(v)) for f, v in facet_turn.items()}
    for k in np.where(band)[0]:
        turn_ref[k] = max(medians.get(int(keys[k, 0]), 0.0),
                          medians.get(int(keys[k, 1]), 0.0))
    consistent = (~strip_fold) | (angles >= cfg.turn_consistency * turn_ref)

    usable = band & comparable & consistent & (~conical) & (~on_chamfer)
    radii = np.full(len(angles), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        radii[usable] = ((widths[usable, 0] + widths[usable, 1]) / 2
                         / (2 * np.sin(angles[usable] / 2)))

    def modes_for(selection: np.ndarray, sweeps=None) -> list[dict]:
        out = radius_modes(radii[selection], lengths[selection], cfg)
        for mode in out:
            window = (selection & np.isfinite(radii)
                      & (radii > mode["r_mm"] * (1 - cfg.mode_tol))
                      & (radii < mode["r_mm"] * (1 + cfg.mode_tol)))
            if not window.any():
                continue
            turn = float(np.median(np.degrees(angles[window])))
            mode["implied_fn"] = round(360.0 / turn, 1) if turn > 0 else None
            if sweeps is not None:
                # How far the band this mode lives on actually goes around:
                # ~90 degrees is an edge being broken, 180+ is the body of the
                # part curving. The number a reader needs to tell a 15 mm
                # fillet from a 15 mm barrel.
                arcs = sweeps[window]
                arcs = arcs[arcs > 0]
                if len(arcs):
                    mode["sweep_deg"] = round(float(np.median(arcs)), 1)
        return out

    # --- pass 3: edge rounding vs form curvature --------------------------
    # A 15 mm radius can be a generous fillet or it can be the barrel of a
    # capsule, and a style spec that confuses the two hands the next design a
    # 15 mm "corner radius". Curvature counts as FORM when the surface closes
    # on itself (a full barrel or bore) or when its radius is a sizeable
    # fraction of the part — at which point the curve is the shape, not a
    # treatment applied to its edges.
    regions, closed = _regions(mesh, usable, angles, lengths, radii, convex, cfg)
    # Measured against the part's LONGEST dimension, so that rounding the
    # corners of a thin plate stays edge treatment: against the shortest
    # dimension a 3 mm radius on a 4 mm plate would score 0.75 and be
    # misfiled as form, taking the plate's real corner radius with it.
    longest = float(np.max(mesh.extents)) if len(mesh.vertices) else 0.0
    form = np.zeros(len(angles), dtype=bool)
    if longest > 0:
        with np.errstate(invalid="ignore"):
            scale = np.nan_to_num(radii) / longest
            # Bigger than the whole part: cannot be an edge treatment. Far
            # bigger: not a curve at all, just a flat face whose triangles
            # disagree by a fraction of a degree — drop it before it becomes
            # 80% of a "rounding vocabulary".
            form = usable & (scale >= 0.35)
            usable &= scale <= cfg.noise_radius_multiple
            form &= usable
    sweeps = np.zeros(len(angles))
    for root, folds in regions.items():
        idx = np.array(folds)
        # Only a band that stops somewhere has an arc worth quoting. A region
        # that keeps turning is a continuous surface network (every edge of a
        # fully-rounded box joins its neighbours), and reporting "sweeps 51953
        # degrees" would be noise dressed as a measurement.
        turn = float(np.degrees(angles[idx]).sum())
        sweeps[idx] = turn if turn <= 400.0 else 0.0
        if closed.get(root):
            form[idx] = True

    outer = modes_for(usable & convex & ~form, sweeps)
    inner = modes_for(usable & ~convex & ~form, sweeps)
    form_outer = modes_for(usable & convex & form, sweeps)
    form_inner = modes_for(usable & ~convex & form, sweeps)

    # The three grammar buckets must PARTITION the shaped folds, not overlap.
    # Summing "hard length" and "chamfer length" double-counted every chamfer's
    # own bounding folds — they turn 45 degrees, so they are hard edges *and*
    # chamfer edges — inflating the denominator and quietly shrinking every
    # share below what it should be.
    chamfer_mask = (~flat) & on_chamfer
    round_mask = usable & (~chamfer_mask)
    sharp_mask = (~flat) & (~chamfer_mask) & (~round_mask)
    chamfer_len = float(lengths[chamfer_mask].sum())
    round_len = float(lengths[round_mask].sum())
    sharp_len = float(lengths[sharp_mask].sum())
    grammar_total = chamfer_len + round_len + sharp_len

    # How the curved surfaces are tessellated, because it bounds how far the
    # radii can be trusted. CAD and OpenSCAD emit quad strips (two coplanar
    # triangles per strip) and the radius identity is then exact — measured
    # error under half a percent. A mesh of free-standing triangles (sculpted,
    # or remeshed in Blender) has no strips: consecutive folds turn about
    # non-parallel axes, and the same estimator reads high by a factor of
    # about 1.38 on an equilateral triangulation. That is reported, not
    # silently corrected: the factor is only stable at the isotropic extreme,
    # and a confident wrong number is worse than a flagged approximate one.
    stripped = 0.0
    if band.any():
        # Judged over the *curved* folds and requiring strips on both sides:
        # this is a statement about how the curved surfaces are tessellated,
        # and a part whose flat faces are quads but whose cone is triangle soup
        # should not be able to claim otherwise.
        paired = np.array([(keys[k, 0] >= 0) and (keys[k, 1] >= 0)
                           for k in np.where(band)[0]])
        stripped = float(lengths[band][paired].sum() / lengths[band].sum())
    tessellation = ("strip" if stripped > 0.6
                    else "triangulated" if stripped < 0.15 else "mixed")
    return {
        "folds": int(len(angles)),
        "soft_length_mm": round(soft_len, 3),
        "hard_length_mm": round(hard_len, 3),
        "softness": round(soft_len / shaped, 4) if shaped > 0 else 0.0,
        "tessellation": tessellation,
        "strip_share": round(stripped, 4),
        "rounding": {
            "convex": outer,
            "concave": inner,
            "dominant_r_mm": outer[0]["r_mm"] if outer else None,
            "dominant_share": outer[0]["share"] if outer else 0.0,
            "implied_fn": outer[0].get("implied_fn") if outer else None,
        },
        # Curvature that *is* the shape rather than a treatment of its edges:
        # barrels, domes, bores. Reported so a style can say "bodies are
        # cylindrical", but deliberately kept out of the corner-radius token.
        "form": {
            "convex": form_outer,
            "concave": form_inner,
            "dominant_r_mm": form_outer[0]["r_mm"] if form_outer else None,
        },
        "chamfers": {
            "bands": sorted(bands, key=lambda b: -b["length_mm"])[:8],
            "count": len(bands),
            "length_mm": round(chamfer_len, 3),
            "dominant_leg_mm": (
                round(float(np.median([b["leg_mm"] for b in bands])), 4)
                if bands else None),
        },
        "grammar": {
            "rounded_share": round(round_len / grammar_total, 4) if grammar_total else 0.0,
            "chamfered_share": round(chamfer_len / grammar_total, 4) if grammar_total else 0.0,
            "sharp_share": round(sharp_len / grammar_total, 4) if grammar_total else 0.0,
        },
        # handed to the feature pass so the regions are grown only once
        "_internal": {"radii": radii, "usable": usable, "lengths": lengths,
                      "angles": angles, "convex": convex,
                      "regions": regions, "closed": closed},
    }


def _regions(mesh: trimesh.Trimesh, usable: np.ndarray, angles: np.ndarray,
             lengths: np.ndarray, radii: np.ndarray, convex: np.ndarray,
             cfg: Config) -> tuple[dict, dict]:
    """Group folds into continuous curved surfaces, and say which ones close.

    Union-find over the folds that carry a usable radius. A region is *closed*
    when its folds sum to one full turn and its radius holds steady across
    them: that is a barrel or a bore. Summing past a full turn means several
    features grew together — the unbroken shell of a box rounded on all twelve
    edges, say — which is not one cylinder and must not be reported as one.
    """
    pairs = mesh.face_adjacency
    parent = np.arange(len(mesh.faces))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return int(a)

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Coplanar faces first: a tessellated strip is two triangles sharing a
    # diagonal, and without joining them the chain of strips around a hole
    # breaks at every strip and no band ever closes.
    for group in mesh.facets:
        group = np.asarray(group)
        for face in group[1:]:
            union(int(group[0]), int(face))
    members: dict[int, list[int]] = {}
    for k in np.where(usable)[0]:
        union(int(pairs[k, 0]), int(pairs[k, 1]))
    for k in np.where(usable)[0]:
        root = find(int(pairs[k, 0]))
        members.setdefault(root, []).append(int(k))

    closed: dict[int, bool] = {}
    for root, folds in members.items():
        idx = np.array(folds)
        turn = float(np.degrees(angles[idx]).sum())
        if not cfg.closed_turn_deg <= turn <= 400.0:
            continue
        sign = float(convex[idx].mean())
        if 0.15 < sign < 0.85:          # mixed curvature: not one clean barrel
            continue
        r = _weighted_median(radii[idx], lengths[idx])
        if r <= 0 or float(np.std(radii[idx]) / r) > 0.15:
            continue                    # radius wanders: not a cylinder
        closed[root] = True
    return members, closed


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """Median of `values` weighted by `weights` (edge length, everywhere here)."""
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    if not len(cumulative) or cumulative[-1] <= 0:
        return 0.0
    return float(values[order][np.searchsorted(cumulative, cumulative[-1] / 2)])


def _cylindrical_features(mesh: trimesh.Trimesh, internal: dict, cfg: Config) -> dict:
    """The holes, bosses and barrels: curved bands that close on themselves.

    Concave means a bore, convex a round pillar. Instances of the same size and
    axis are reported once with a count, because "four M3 clearance holes" is
    the fact worth carrying into a style, not four near-identical entries.
    """
    radii, angles = internal["radii"], internal["angles"]
    lengths, convex = internal["lengths"], internal["convex"]
    regions, closed = internal["regions"], internal["closed"]
    pairs = mesh.face_adjacency

    features = []
    for root in closed:
        idx = np.array(regions[root])
        r = _weighted_median(radii[idx], lengths[idx])
        normals = mesh.face_normals[np.unique(pairs[idx].ravel())]
        axis = np.abs(np.linalg.svd(normals, full_matrices=False)[2][-1])
        features.append({
            "d_mm": round(2 * r, 3),
            "kind": "boss" if float(convex[idx].mean()) >= 0.85 else "hole",
            "along": ("z" if axis[2] > 0.95
                      else ("xy" if axis[2] < 0.05 else "oblique")),
            "implied_fn": round(
                360.0 / float(np.median(np.degrees(angles[idx]))), 1),
        })

    grouped: dict[tuple, dict] = {}
    for f in features:
        key = (round(f["d_mm"], 2), f["kind"], f["along"])
        entry = grouped.setdefault(key, {"d_mm": key[0], "kind": key[1],
                                         "axis": key[2], "count": 0,
                                         "implied_fn": f["implied_fn"]})
        entry["count"] += 1
    cylinders = sorted(grouped.values(),
                       key=lambda c: (-c["count"], c["d_mm"]))[:12]
    # The fastener vocabulary as a plain number a rule can compare against:
    # "this family drills M3 clearance" is one of the most portable things a
    # style carries, and it survives into parts of any size.
    holes = [c for c in cylinders if c["kind"] == "hole"]
    return {"cylinders": cylinders,
            "count": len(features),
            "hole_count": sum(h["count"] for h in holes),
            "dominant_hole_d_mm": holes[0]["d_mm"] if holes else None}


def _massing(mesh: trimesh.Trimesh) -> dict:
    """Overall proportion and how much of the bounding box the form fills."""
    extents = np.asarray(mesh.extents, dtype=float)
    ordered = np.sort(extents)[::-1]
    bbox_volume = float(np.prod(extents)) if np.all(extents > 0) else 0.0
    volume = float(mesh.volume) if mesh.is_watertight else float("nan")
    try:
        hull_volume = float(mesh.convex_hull.volume)
    except Exception:                                  # degenerate hull
        hull_volume = float("nan")
    return {
        "extents_mm": [round(float(e), 3) for e in extents],
        "aspect": [round(float(o / ordered[0]), 4) for o in ordered]
        if ordered[0] > 0 else [0, 0, 0],
        "volume_mm3": round(volume, 3) if np.isfinite(volume) else None,
        "bbox_fill": round(volume / bbox_volume, 4)
        if bbox_volume > 0 and np.isfinite(volume) else None,
        "convexity": round(volume / hull_volume, 4)
        if np.isfinite(hull_volume) and hull_volume > 0 and np.isfinite(volume) else None,
        "surface_area_mm2": round(float(mesh.area), 3),
    }


def _orientation(mesh: trimesh.Trimesh, cfg: Config) -> dict:
    """Area shares by face direction, in the mesh's own frame (+Z assumed up).

    Style-bearing because design families differ in how they meet the build
    plate: a family of flat-topped boxes with vertical walls reads differently
    from one whose surfaces all slope. Meaningless if the file was exported in
    an arbitrary pose, hence `assumes_z_up` in the output.
    """
    areas = np.asarray(mesh.area_faces, dtype=float)
    total = float(areas.sum())
    if total <= 0:
        return {"assumes_z_up": True}
    nz = np.clip(np.asarray(mesh.face_normals)[:, 2], -1.0, 1.0)
    tilt = np.degrees(np.arccos(nz))                    # 0 = up, 180 = down
    vertical = np.abs(tilt - 90.0) <= cfg.vertical_tol_deg
    up = tilt <= cfg.vertical_tol_deg
    down = tilt >= 180.0 - cfg.vertical_tol_deg
    sloped = ~(vertical | up | down)
    slopes = []
    if sloped.any():
        # dominant slope angles, area-weighted. NOTE: measured from the build
        # direction (vertical), not from the bed — a 45 deg chamfer and a 45
        # deg roof both read 45, but a shallow 20 deg roof reads 70. Kept as-is
        # because the field is published; unsupported_share below is the one
        # that speaks in printing terms.
        angle = np.abs(90.0 - tilt[sloped])
        counts, edges = np.histogram(angle, bins=np.arange(0, 91, 2.5),
                                     weights=areas[sloped])
        for i in np.argsort(counts)[::-1][:3]:
            if counts[i] <= 0.02 * total:
                continue
            sel = sloped.copy()
            sel[sloped] = (angle >= edges[i]) & (angle < edges[i + 1])
            slopes.append({
                "angle_deg": round(float(np.average(np.abs(90.0 - tilt[sel]),
                                                    weights=areas[sel])), 2),
                "share": round(float(areas[sel].sum() / total), 4)})
    # Share of surface that would need support: facing downward and shallower
    # than the support-free limit. A scalar, unlike dominant_slopes, so a style
    # can hold a new part to it — "this family never places a face below 45
    # degrees" is a design rule, and dominant_slopes is a list a rule cannot
    # address. Pose-dependent like everything else here (see assumes_z_up):
    # it describes the part as exported, which for a printable part is the
    # orientation it prints in.
    # tilt is measured from +Z, so abs(90 - tilt) is the angle from VERTICAL;
    # the angle a printer cares about is from the bed, which is its complement.
    from_horizontal = 90.0 - np.abs(90.0 - tilt)
    unsupported = (tilt > 90.0) & (from_horizontal < cfg.overhang_limit_deg)
    # ...except the footprint. A face lying in the bed plane is carried by the
    # build plate, not by support material, and every part has one; counting it
    # would make this metric mostly "how wide is your base" and would punish a
    # flat part for being flat.
    if unsupported.any():
        z_min = float(mesh.bounds[0][2])
        face_z = np.asarray(mesh.triangles)[:, :, 2]
        on_bed = np.all(np.abs(face_z - z_min) <= cfg.bed_tol_mm, axis=1)
        unsupported &= ~on_bed
    return {
        "assumes_z_up": True,
        "up_share": round(float(areas[up].sum() / total), 4),
        "down_share": round(float(areas[down].sum() / total), 4),
        "vertical_share": round(float(areas[vertical].sum() / total), 4),
        "sloped_share": round(float(areas[sloped].sum() / total), 4),
        "unsupported_share": round(float(areas[unsupported].sum() / total), 4),
        "overhang_limit_deg": cfg.overhang_limit_deg,
        "dominant_slopes": slopes,
    }


def _walls(mesh: trimesh.Trimesh, cfg: Config) -> dict:
    """Material thickness by inward ray casting from area-weighted samples.

    printcheck asks whether a wall is too thin to print; this asks what
    thickness the family *chose*, which is a style token — a design language
    that always builds 2.4 mm walls looks different from one at 1.2 mm.
    """
    if not mesh.is_watertight or len(mesh.faces) == 0:
        return {"measured": False, "reason": "mesh is not watertight"}
    areas = np.asarray(mesh.area_faces, dtype=float)
    total = float(areas.sum())
    if total <= 0:
        return {"measured": False, "reason": "degenerate faces"}
    n = min(cfg.thickness_samples, int((areas > 0).sum()))
    rng = np.random.default_rng(0)                      # fixed: results repeat
    idx = rng.choice(len(mesh.faces), size=n, replace=False, p=areas / total)
    directions = -np.asarray(mesh.face_normals)[idx]
    origins = np.asarray(mesh.triangles_center)[idx] + directions * 1e-4
    hits, ray_idx, _ = mesh.ray.intersects_location(origins, directions,
                                                    multiple_hits=False)
    if not len(hits):
        return {"measured": False, "reason": "no interior ray hits"}
    thickness = np.linalg.norm(hits - origins[ray_idx], axis=1)
    counts, edges = np.histogram(thickness, bins=64)
    peak = int(np.argmax(counts))
    centre = float((edges[peak] + edges[peak + 1]) / 2)
    # Refine off the histogram grid, as radius_modes does: the bin only has to
    # find the peak, and a bin wide enough to span a whole part is far too
    # coarse to report as "this family builds at 2.5 mm".
    window = thickness[(thickness >= centre * 0.88) & (thickness <= centre * 1.12)]
    mode = float(np.median(window)) if len(window) else centre
    # On a solid part these rays measure the part, not a wall, and the answer
    # must not become a "wall thickness" token in somebody's style.
    #
    # Two things have to hold. Most of the surface must sit at the same
    # thickness, because a shell is *mostly* wall — that alone rules out a
    # solid block with a boss, whose rays cross the boss and return its width.
    # And that thickness must agree with the part's own volume-to-area ratio:
    # material of thickness t bounded on both sides gives 2V/A ≈ t, while a
    # solid block's commonest chord is far larger than its 2V/A.
    #
    # Neither term looks at the bounding box, deliberately. A box-based test
    # made the answer depend on how the file happened to be rotated, which
    # would have been the one place this tool contradicted itself: everything
    # else it measures is invariant under pose.
    area = float(mesh.area)
    volume = float(mesh.volume) if mesh.is_watertight else 0.0
    implied = 2.0 * volume / area if area > 0 else 0.0
    at_mode = float(((thickness >= mode * 0.88) & (thickness <= mode * 1.12)
                     ).mean())
    shelled = bool(at_mode >= 0.5 and 0 < implied and mode <= 1.5 * implied)
    return {
        "measured": True,
        "shelled": shelled,
        "samples": int(len(thickness)),
        "p05_mm": round(float(np.percentile(thickness, 5)), 3),
        "median_mm": round(float(np.median(thickness)), 3),
        "mode_mm": round(mode, 3),
        "min_mm": round(float(thickness.min()), 3),
    }


def _symmetry(mesh: trimesh.Trimesh, cfg: Config) -> dict:
    """Mirror symmetry about each bounding-box mid-plane, as a 0..1 score.

    Points are sampled on the surface, mirrored, and measured against the real
    surface — not against the sample set, so the score does not degrade with
    sampling density.
    """
    if len(mesh.faces) == 0:
        return {}
    diagonal = float(np.linalg.norm(mesh.extents))
    if diagonal <= 0:
        return {}
    points, _ = trimesh.sample.sample_surface(mesh, cfg.symmetry_samples, seed=0)
    centre = mesh.bounds.mean(axis=0)
    tolerance = 0.005 * diagonal
    out = {}
    for i, name in enumerate("xyz"):
        mirrored = np.array(points)
        mirrored[:, i] = 2 * centre[i] - mirrored[:, i]
        distance = trimesh.proximity.closest_point(mesh, mirrored)[1]
        out[name] = round(float((np.abs(distance) <= tolerance).mean()), 4)
    return out


def _curve_resolution(edges: dict, features: dict) -> float | None:
    """The finest curve resolution the mesh itself draws, in segments/turn.

    The honest evidence is the *edge* rounding vocabulary and the cylindrical
    features: a rounding mode is one edge band drawn at one resolution (every
    fold in it turns the same amount), and a cylindrical feature is a uniform
    circle — both carry an `implied_fn` a design actually chose. Form
    curvature is deliberately excluded: a barrel or a sphere is a
    parameterized surface whose fold angle varies across it, so a mode's
    median turn there describes where the surface's own parameterization
    happens to sample, not a resolution the author wrote. A uv sphere of
    $fn=64 compresses to 0.7-degree folds at its poles, which drags the
    median to ~2.9 degrees and would report $fn=126 — a threshold finer than
    the author's own sampling, calling their equator folds design facets. The
    latitude rings of that same sphere are detected as cylinders at $fn=64,
    which is the truth the surface mode buried.

    The finest reported resolution is what the sharpness metric normalises
    against: a part that draws its curves at $fn=64 has declared 5.6 degrees
    to be tessellation, so its 45-degree folds must be design; a part whose
    finest curve is an 8-sided barrel has declared 45 degrees to be a curve's
    segment, so the same fold there is tessellation.
    """
    reported = []
    for side in ("convex", "concave"):
        for mode in (edges.get("rounding") or {}).get(side, []):
            if mode.get("implied_fn"):
                reported.append(float(mode["implied_fn"]))
    for cyl in features.get("cylinders", []):
        if cyl.get("implied_fn"):
            reported.append(float(cyl["implied_fn"]))
    return max(reported) if reported else None


def _facetedness(mesh: trimesh.Trimesh, edges: dict, features: dict,
                 cfg: Config) -> dict:
    """Dihedral-sharpness histogram: how much of the shaped edge length is
    *design facet* rather than tessellation.

    A style built from flat facets meeting at decided angles — a low-poly
    solid, stencil-cut glyphs, a truss — is the opposite of the smoothed
    vocabulary above, and `softness` cannot see it: a fully faceted part and
    a coarsely drawn smooth one both turn steep folds everywhere. What tells
    them apart is not the angle but the resolution the mesh claims for its
    own curves. A fold turning one segment of the finest curve the part
    actually draws is that curve's tessellation; a fold turning decisively
    more than that is a corner somebody drew. The threshold is therefore
    derived per mesh (`tessellation_turn_deg` = 360/$fn, with a little slack)
    rather than fixed, which is why a coarse export of a smooth part earns no
    facetedness credit for its tessellation edges: its own curves are its
    coarsest evidence, and they explain every fold it has.

    Shares are of *shaped* edge length — folds turning at least `flat_deg`,
    the same denominator `softness` uses — so the coplanar diagonals every
    quad strip is made of never dilute the count.
    """
    angles = np.asarray(mesh.face_adjacency_angles, dtype=float)
    edges_arr = mesh.face_adjacency_edges
    verts = mesh.vertices
    if not len(angles):
        return {"fn_curve": None, "tessellation_turn_deg": None,
                "sharpness": 0.0, "shaped_length_mm": 0.0,
                "facet_length_mm": 0.0, "histogram": []}
    lengths = np.linalg.norm(verts[edges_arr[:, 0]] - verts[edges_arr[:, 1]],
                             axis=1)
    shaped = angles >= np.radians(cfg.flat_deg)

    fn_curve = _curve_resolution(edges, features)
    floor = cfg.fn_curve_fallback if fn_curve is None else fn_curve
    tess_turn = cfg.tessellation_slack * 360.0 / floor
    facet = shaped & (np.degrees(angles) > tess_turn)

    shaped_len = float(lengths[shaped].sum())
    facet_len = float(lengths[facet].sum())
    bins = []
    bounds = cfg.histogram_bins_deg
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        inside = shaped & (angles > np.radians(lo)) & (angles <= np.radians(hi))
        length = float(lengths[inside].sum())
        bins.append({
            "lo_deg": lo, "hi_deg": hi,
            "length_mm": round(length, 3),
            "share": round(length / shaped_len, 4) if shaped_len > 0 else 0.0,
            # A bin straddling the tessellation threshold carries both kinds;
            # flag it by whichever kind owns more of its length.
            "facet": bool(lengths[inside & facet].sum() > length / 2),
        })
    return {
        "fn_curve": round(fn_curve, 1) if fn_curve else None,
        "tessellation_turn_deg": round(tess_turn, 2),
        "sharpness": round(facet_len / shaped_len, 4) if shaped_len > 0 else 0.0,
        "shaped_length_mm": round(shaped_len, 3),
        "facet_length_mm": round(facet_len, 3),
        "histogram": bins,
    }


def _fibonacci_sphere(n: int) -> np.ndarray:
    """N near-uniform directions: a Fibonacci lattice, deterministic."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1.0 - 2.0 * i / n)          # uniform in cos: uniform on sphere
    golden = np.pi * (1 + 5 ** 0.5)
    theta = golden * i
    return np.stack([np.sin(phi) * np.cos(theta),
                     np.sin(phi) * np.sin(theta),
                     np.cos(phi)], axis=1)


def _openness(mesh: trimesh.Trimesh, cfg: Config) -> dict:
    """Projected-void-fraction: how much of the form is open, pose-stably.

    A single projection cannot answer "how open is this part" — face-on, a
    stencil plate is mostly void; edge-on it is almost all material — and any
    *chosen* projection smuggles the answer in with the choice. So integrate
    over the sphere instead: for each of `void_dirs` near-uniform directions,
    cast a fan of parallel lines through the part and measure the open share
    of that view's silhouette — lines that cross the convex hull but never
    meet material. The mean of the per-view open fractions is a solid-angle
    integral, so rotating the part permutes the directions and changes
    nothing: the pose stability is in the construction, not the sampling
    luck.

    The convex hull is the reference silhouette, so deep concavities count as
    openness alongside true cut-throughs — the honest reading of this number
    is "how airy is the form", and a lattice or a stencil scores high for the
    same reason a solid block scores zero.

    The largest gap a line threads through (`max_void_span_mm`) is the size
    of the biggest cut-through — for a stencilled part, the glyph — reported
    as a fraction of the part's largest dimension so a rule can demand
    legible marks (`glyph height >= 0.15 x part diameter`). The narrowest
    material span (`min_bridge_mm`) is measured the way `walls` measures
    thickness — inward normal rays from area-weighted surface samples, fixed
    seed — because a thin web between two cut-outs is the thinnest wall the
    part has, and a bridge under two extrusion widths will not print clean.
    """
    if not mesh.is_watertight or len(mesh.faces) == 0:
        return {"measured": False, "reason": "mesh is not watertight"}
    hull = mesh.convex_hull
    centre = hull.bounds.mean(axis=0)
    radius = float(np.linalg.norm(hull.vertices - centre, axis=1).max())
    if radius <= 0:
        return {"measured": False, "reason": "degenerate part"}

    directions = _fibonacci_sphere(cfg.void_dirs)
    # Golden-spiral disc offsets: even coverage of each view, no randomness.
    j = np.arange(cfg.void_rays_per_dir)
    discs = radius * np.sqrt((j + 0.5) / len(j))
    angles = j * np.pi * (3 - 5 ** 0.5)
    offsets = np.stack([discs * np.cos(angles), discs * np.sin(angles)], axis=1)

    span = 4.0 * radius          # far enough that every line crosses everything
    eps = 1e-6 * radius          # merge numerical double-hits, ignore dust
    per_view = []
    void_spans: list[float] = []
    for w in directions:
        helper = np.array([0.0, 0.0, 1.0]) if abs(w[2]) < 0.9 \
            else np.array([1.0, 0.0, 0.0])
        u = np.cross(w, helper)
        u /= np.linalg.norm(u)
        v = np.cross(w, u)
        origins = (centre + offsets[:, 0, None] * u + offsets[:, 1, None] * v
                   - w * span / 2)
        ray_dirs = np.tile(w, (len(origins), 1))
        solid, solid_ray, _ = mesh.ray.intersects_location(
            origins, ray_dirs, multiple_hits=True)
        outline, outline_ray, _ = hull.ray.intersects_location(
            origins, ray_dirs, multiple_hits=True)
        solid_d = _distances_by_ray(solid, solid_ray, origins)
        hull_d = _distances_by_ray(outline, outline_ray, origins)
        votes = solid_votes = 0
        for ray, chord in hull_d.items():
            # A convex body gives exactly an entry and an exit; a ray with
            # less is a numerical grazing and costs only itself.
            if len(chord) < 2:
                continue
            h0, h1 = chord[0], chord[-1]
            votes += 1
            merged: list[float] = []
            for d in solid_d.get(ray, []):
                if h0 - eps <= d <= h1 + eps:
                    if not merged or d - merged[-1] > eps:
                        merged.append(d)
            if not merged:
                gap = h1 - h0            # threads the form without meeting it
                if gap > eps:
                    void_spans.append(gap)
                continue
            solid_votes += 1
            if len(merged) % 2:
                continue        # unfinished entry/exit pair: no span stats
            bounds = [h0] + merged + [h1]
            for k in range(0, len(bounds) - 1, 2):
                gap = bounds[k + 1] - bounds[k]
                if gap > eps:
                    void_spans.append(gap)
        if votes:
            per_view.append(1.0 - solid_votes / votes)

    longest = float(np.max(mesh.extents))
    thinnest = _thinnest_span(mesh, cfg)
    return {
        "measured": True,
        "void_fraction": round(float(np.mean(per_view)), 4) if per_view else 0.0,
        "directions": int(cfg.void_dirs),
        "rays_per_direction": int(cfg.void_rays_per_dir),
        "views_with_void": int(sum(1 for v in per_view if v > 0)),
        "max_void_span_mm": round(max(void_spans), 3) if void_spans else 0.0,
        "max_void_span_fraction": (round(max(void_spans) / longest, 4)
                                   if void_spans and longest > 0 else 0.0),
        "min_bridge_mm": round(thinnest, 3) if thinnest is not None else None,
    }


def _distances_by_ray(locations: np.ndarray, index_ray: np.ndarray,
                      origins: np.ndarray) -> dict[int, list[float]]:
    """Hit distances along each ray of a batched intersect_location call."""
    out: dict[int, list[float]] = {}
    if len(locations):
        dist = np.linalg.norm(locations - origins[index_ray], axis=1)
        for ray, d in zip(index_ray, dist):
            out.setdefault(int(ray), []).append(float(d))
    for ray in out:
        out[ray].sort()
    return out


def _thinnest_span(mesh: trimesh.Trimesh, cfg: Config) -> float | None:
    """The narrowest material span, measured the way `walls` measures.

    Inward normal rays from area-weighted surface samples: a web between two
    cut-outs is bounded by exactly such walls, and the ray from one crosses
    the web to the next, so the minimum over samples is the bridge a rule
    about printing clean needs. Faces carry area, so — unlike chord sampling
    — no grazing near a cut-out's corner can mint a sliver-thickness that
    exists nowhere on the part.
    """
    areas = np.asarray(mesh.area_faces, dtype=float)
    total = float(areas.sum())
    if total <= 0:
        return None
    n = min(cfg.thickness_samples, int((areas > 0).sum()))
    rng = np.random.default_rng(0)                      # fixed: results repeat
    idx = rng.choice(len(mesh.faces), size=n, replace=False, p=areas / total)
    directions = -np.asarray(mesh.face_normals)[idx]
    origins = np.asarray(mesh.triangles_center)[idx] + directions * 1e-4
    hits, ray_idx, _ = mesh.ray.intersects_location(origins, directions,
                                                    multiple_hits=False)
    if not len(hits):
        return None
    return float(np.linalg.norm(hits - origins[ray_idx], axis=1).min())


def measure(path: str | Path, cfg: Config | None = None) -> dict:
    """Measure every style-bearing property of a mesh file."""
    cfg = cfg or Config()
    mesh = load_mesh(path)
    edges = _edge_treatment(mesh, cfg)
    internal = edges.pop("_internal", None)
    features = (_cylindrical_features(mesh, internal, cfg) if internal
                else {"cylinders": [], "count": 0})
    # Reads the curve resolutions the passes above measured, so it must run
    # after them — but it only adds a key, it changes nothing they reported.
    edges["facetedness"] = _facetedness(mesh, edges, features, cfg)
    walls = _walls(mesh, cfg)
    massing = _massing(mesh)

    ratios = {}
    r = edges.get("rounding", {}).get("dominant_r_mm")
    chamfer = edges.get("chamfers", {}).get("dominant_leg_mm")
    # Only a shelled part has a wall to be in proportion with.
    wall = walls.get("mode_mm") if walls.get("shelled") else None
    if r and wall:
        ratios["radius_to_wall"] = round(r / wall, 3)
    if chamfer and wall:
        ratios["chamfer_to_wall"] = round(chamfer / wall, 3)
    longest = max(massing["extents_mm"]) if massing["extents_mm"] else 0
    if r and longest:
        ratios["radius_to_size"] = round(r / longest, 4)

    return {
        "source": str(path),
        "mesh": {
            "faces": int(len(mesh.faces)),
            "vertices": int(len(mesh.vertices)),
            "watertight": bool(mesh.is_watertight),
            "bodies": int(mesh.body_count) if len(mesh.faces) else 0,
        },
        "massing": massing,
        "edges": edges,
        "features": features,
        "orientation": _orientation(mesh, cfg),
        "walls": walls,
        "openness": _openness(mesh, cfg),
        "symmetry": _symmetry(mesh, cfg),
        "ratios": ratios,
        "config": asdict(cfg),
    }
