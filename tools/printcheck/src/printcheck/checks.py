"""Geometric printability heuristics.

Each check takes a trimesh.Trimesh (already positioned with its lowest
point at z=0) plus a config, and yields Finding objects. Conventions:
+Z is the build direction, units are millimeters.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh

from .report import Finding, Severity


@dataclass
class Config:
    # mm, extruder nozzle diameter; sets the minimum printable feature width
    nozzle_mm: float = 0.4
    # mm, print layer height; faces within ~1.5 layers of the bed count as
    # plate contact
    layer_height_mm: float = 0.2
    # mm, thinnest wall considered printable — 2 extrusion widths with a
    # 0.4 nozzle (the printability floor; a *design* target is usually 1.2+)
    min_wall_mm: float = 0.8
    # degrees from vertical; faces steeper than this need support
    overhang_deg: float = 45.0
    # mm, the widest unsupported span FDM bridges cleanly without support. A
    # downward region whose straight span stays under this is self-supporting
    # (a bridge), so it is NOT counted as needing support — this is what keeps
    # a debossed letter's ceiling, a thin relief chamfer, or a print-in-place
    # socket roof from scoring as an overhang the way a wide flat shelf does.
    # 5 mm is conservative (most printers bridge 5-10 mm). The region test is
    # shape-aware (see _bridgeable_mask): thin strokes/rings by erosion, solid
    # blobs by hull min-width, so a filled triangular ceiling is not mistaken
    # for a bridgeable ring.
    bridge_max_mm: float = 5.0
    # mm, printer build volume (X, Y, Z)
    build_volume_mm: tuple = (250.0, 210.0, 220.0)
    # count, face samples for the wall-thickness ray casts
    thickness_samples: int = 2000
    # mm², minimum near-horizontal down-facing area stranded just above the
    # bed before the floating-first-layer check (check_bed_contact) speaks.
    # Below this it is sliver noise, not an intended print surface.
    bed_float_min_mm2: float = 10.0
    # the floating-first-layer check fires when the area truly touching z=0 is
    # below this fraction of the area stranded one-to-three layers above it —
    # i.e. the intended contact surface is mostly in the air, not on the plate.
    # A flat slab lifted whole drives this to ~0; a curved or angled real
    # contact keeps comparable area in both bands and stays well above it.
    bed_float_ratio: float = 0.2


# --------------------------------------------------------------------------
# Shared geometry masks (also used by the orientation advisor)
# --------------------------------------------------------------------------

def plate_contact_faces(mesh: trimesh.Trimesh, cfg: Config) -> np.ndarray:
    """Boolean mask of down-facing faces resting on the build plate."""
    face_z = mesh.triangles[:, :, 2].max(axis=1)
    down_facing = mesh.face_normals[:, 2] < -0.5
    return (face_z < cfg.layer_height_mm * 1.5) & down_facing


def overhang_faces(mesh: trimesh.Trimesh, cfg: Config) -> np.ndarray:
    """Boolean mask of faces steeper than the support threshold, excluding
    faces near enough to the plate to be supported by the bed."""
    down = -mesh.face_normals[:, 2]          # 1.0 = facing straight down
    threshold = np.cos(np.radians(cfg.overhang_deg))
    face_z = mesh.triangles[:, :, 2].max(axis=1)
    on_plate = face_z < (cfg.layer_height_mm * 1.5)
    return (down > threshold) & ~on_plate


# --------------------------------------------------------------------------
# Mesh integrity
# --------------------------------------------------------------------------

def _nonmanifold_edge_clusters(mesh: trimesh.Trimesh, top: int = 5) -> str:
    """Locate edges shared by >2 faces and summarize where they sit.

    Groups the offending edge midpoints onto a 1 mm grid and returns the
    `top` densest locations as "N edges near (x, y, z)" — enough to find
    the responsible feature in the source model without a mesh viewer.
    """
    edges = mesh.edges_sorted
    groups = trimesh.grouping.group_rows(edges)
    bad = [g for g in groups if len(g) > 2]
    if not bad:
        return ""
    mids = np.array([mesh.vertices[edges[g[0]]].mean(axis=0) for g in bad])
    cells, counts = np.unique(np.round(mids), axis=0, return_counts=True)
    order = np.argsort(-counts)[:top]
    spots = ", ".join(
        f"{int(counts[i])}x near ({cells[i][0]:g}, {cells[i][1]:g}, "
        f"{cells[i][2]:g})" for i in order)
    more = len(bad) - int(counts[order].sum())
    return spots + (f" (+{more} elsewhere)" if more > 0 else "")


def check_integrity(mesh: trimesh.Trimesh, cfg: Config):
    """Report topology problems: holes, non-manifold edges, bad normals,
    duplicate/degenerate faces, and stray disconnected shells."""
    if mesh.is_empty or len(mesh.faces) == 0:
        yield Finding(
            "integrity", Severity.CRITICAL, "Empty mesh",
            "The file contains no triangles.",
        )
        return

    open_edges = int((trimesh.grouping.group_rows(
        mesh.edges_sorted, require_count=1)).shape[0])
    if not mesh.is_watertight:
        if open_edges > 0:
            detail = (
                f"{open_edges} boundary (naked) edges — the surface has "
                "holes, so the slicer cannot tell inside from outside. "
                "Repair with e.g. trimesh.repair.fill_holes, Blender "
                "3D-Print Toolbox, or PrusaSlicer's Netfabb repair."
            )
        else:
            detail = (
                "No open holes, but some edges are shared by more than two "
                "triangles (non-manifold) — typically overlapping shells "
                "that were concatenated instead of boolean-unioned. Most "
                "slicers repair this, but a proper union is safer."
            )
            where = _nonmanifold_edge_clusters(mesh)
            if where:
                detail += " Non-manifold edges cluster at (mm): " + where
        yield Finding(
            "integrity", Severity.CRITICAL, "Mesh is not watertight",
            detail, {"open_edges": open_edges},
        )
    if not mesh.is_winding_consistent:
        yield Finding(
            "integrity", Severity.CRITICAL, "Inconsistent triangle winding",
            "Adjacent triangles disagree on which side is 'outside'; "
            "normals are unreliable. Run a normals-repair pass.",
        )
    elif mesh.is_watertight and mesh.volume < 0:
        yield Finding(
            "integrity", Severity.CRITICAL, "Inverted normals",
            "The mesh is watertight but inside-out (negative volume). "
            "Flip normals before slicing.",
            {"volume_mm3": float(mesh.volume)},
        )

    dup = int(len(mesh.faces) - len(trimesh.grouping.unique_rows(
        np.sort(mesh.faces, axis=1))[0]))
    if dup > 0:
        yield Finding(
            "integrity", Severity.WARNING, "Duplicate faces",
            f"{dup} duplicate triangles found; most slicers tolerate a few "
            "but they can cause artifacts.",
            {"duplicate_faces": dup},
        )

    degenerate = int((mesh.area_faces < 1e-10).sum())
    if degenerate > 0:
        yield Finding(
            "integrity", Severity.WARNING, "Degenerate faces",
            f"{degenerate} zero-area triangles. Usually harmless after "
            "slicer repair, but a sign of a sloppy export.",
            {"degenerate_faces": degenerate},
        )

    bodies = mesh.body_count
    if bodies > 1:
        yield Finding(
            "integrity", Severity.INFO, "Multiple bodies",
            f"The file contains {bodies} disconnected shells. Fine if "
            "intentional (a plate of parts); a problem if fragments were "
            "left behind by the modeling tool.",
            {"bodies": int(bodies)},
        )


# --------------------------------------------------------------------------
# Overhangs / support need
# --------------------------------------------------------------------------

def _hull_min_width(poly) -> float:
    """Minimum width (smallest distance between two parallel supporting lines)
    of a polygon's convex hull — the shortest span a straight bridge across the
    solid shape must cover. Rotating-calipers via each hull edge's normal."""
    hull = poly.convex_hull
    xy = np.asarray(hull.exterior.coords)[:-1]  # drop repeated closing vertex
    if len(xy) < 3:
        return 0.0
    edges = np.roll(xy, -1, axis=0) - xy               # (E, 2)
    lens = np.hypot(edges[:, 0], edges[:, 1])
    keep = lens > 1e-9
    if not keep.any():
        return 0.0
    normals = np.stack([-edges[keep, 1], edges[keep, 0]], axis=1) / lens[keep, None]
    proj = xy @ normals.T                               # (V, E) vertex·normal
    widths = proj.max(axis=0) - proj.min(axis=0)        # extent along each normal
    return float(widths.min())


def _bridgeable_mask(mesh: trimesh.Trimesh, oh: np.ndarray, cfg: Config) -> np.ndarray:
    """Of the overhang faces `oh`, return a mask of those that are BRIDGEABLE
    — part of a connected downward region FDM spans without support.

    Bridgeability is shape-aware, because a *thin* region and a *solid* region
    fail in different ways and one test cannot catch both:

    - A thin region (a debossed letter's stroke, a thin annular relief chamfer,
      a print-in-place socket roof, a ring) is spanned by short local bridges
      across its width, so the test is a morphological erosion by half the
      bridge width: if the footprint erodes to nothing it is everywhere
      narrower than `bridge_max_mm`. A ring erodes away here even though it is
      geometrically wide — which is why a plain inradius/erosion test alone was
      chosen — but that same erosion wrongly clears a *solid* acute blob (an
      equilateral triangle of side 8 mm has inradius 2.31 < 2.5 mm yet its
      shortest straight bridge is 6.9 mm).

    - A solid/compact region must be crossed by full straight bridges, so the
      binding span is its convex-hull minimum width, not its local thinness.

    The two are told apart by Polsby-Popper compactness (4π·area / perimeter²):
    a stroke or ring is elongated (low), a filled blob is compact (high). A
    compact region is bridgeable only if its hull min-width ≤ `bridge_max_mm`;
    a thin region is bridgeable if it erodes away. Either way a wide flat shelf
    (survives erosion, compact, min-width huge) stays support-needing.

    Falls back to "nothing is bridgeable" if shapely is unavailable or a
    region's geometry defeats the union — never exempts on error, so the check
    can only get stricter, not weaker, when it degrades.
    """
    idx = np.where(oh)[0]
    if idx.size == 0:
        return np.zeros(len(mesh.faces), dtype=bool)
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except Exception:
        return np.zeros(len(mesh.faces), dtype=bool)

    # Connected components of the overhang subset (faces adjacent across a
    # shared edge, both in `oh`). Isolated overhang faces are their own region.
    adj = mesh.face_adjacency
    both = oh[adj[:, 0]] & oh[adj[:, 1]]
    try:
        comps = trimesh.graph.connected_components(adj[both], nodes=idx)
    except Exception:
        comps = [np.array([i]) for i in idx]

    tri = mesh.triangles  # (F, 3, 3)
    r = cfg.bridge_max_mm / 2.0
    # Above this Polsby-Popper value a region is treated as a compact blob
    # (equilateral triangle ≈ 0.60, disc = 1.0) rather than a thin stroke/ring
    # (elongated, well below 0.4).
    compact_pp = 0.4
    bridgeable = np.zeros(len(mesh.faces), dtype=bool)
    for comp in comps:
        comp = np.asarray(comp)
        if comp.size == 0:
            continue
        try:
            polys = [Polygon(tri[f][:, :2]) for f in comp]
            foot = unary_union([p for p in polys if p.is_valid and p.area > 0])
            if foot.is_empty:
                continue
            if not foot.buffer(-r).is_empty:
                continue                       # fat core survives → needs support
            # Erodes away, so it is locally thin. Distinguish a genuinely thin
            # stroke/ring (bridge it) from a solid acute blob whose straight
            # span still exceeds the budget (support it).
            per = foot.length
            pp = 4 * np.pi * foot.area / (per * per) if per > 1e-9 else 1.0
            if pp > compact_pp and _hull_min_width(foot) > cfg.bridge_max_mm:
                continue                       # compact blob, span too wide
            bridgeable[comp] = True
        except Exception:
            continue  # unresolvable region stays support-needing (conservative)
    return bridgeable


def check_overhangs(mesh: trimesh.Trimesh, cfg: Config):
    """Quantify downward-facing surface that would need support material.

    Counts only overhang that a bridge cannot span: a downward region wider
    than `bridge_max_mm` everywhere. Narrow regions (debossed text ceilings,
    thin relief chamfers, print-in-place socket roofs) are self-supporting and
    excluded — so the score reflects support NEED, not raw downward area.
    """
    if len(mesh.faces) == 0:
        return
    oh = overhang_faces(mesh, cfg)
    raw_area = float(mesh.area_faces[oh].sum())
    bridgeable = _bridgeable_mask(mesh, oh, cfg)
    support = oh & ~bridgeable
    area = float(mesh.area_faces[support].sum())
    bridge_area = raw_area - area
    total = float(mesh.area)
    frac = area / total if total else 0.0
    if frac > 0.001:
        sev = Severity.WARNING if frac < 0.25 else Severity.CRITICAL
        extra = (f" ({bridge_area:.0f} mm² more is downward-facing but bridgeable "
                 "and self-supporting.)") if bridge_area > 0.5 else ""
        yield Finding(
            "overhangs", sev,
            f"{frac:.0%} of surface needs support (unbridgeable overhang beyond "
            f"{cfg.overhang_deg:.0f}°)",
            f"{area:.0f} mm² of downward-facing surface is too wide to bridge and "
            f"will need support material or a better orientation.{extra}",
            {"overhang_area_mm2": area, "overhang_fraction": frac,
             "raw_overhang_area_mm2": raw_area,
             "bridgeable_area_mm2": bridge_area,
             "bridge_max_mm": cfg.bridge_max_mm,
             "threshold_deg": cfg.overhang_deg},
        )


# --------------------------------------------------------------------------
# Wall thickness (ray-cast sampling)
# --------------------------------------------------------------------------

def check_walls(mesh: trimesh.Trimesh, cfg: Config):
    """Estimate wall thickness by casting rays inward from sampled faces."""
    if len(mesh.faces) == 0 or not mesh.is_watertight:
        return  # thickness rays are meaningless on an open surface
    areas = mesh.area_faces
    total_area = float(areas.sum())
    if total_area <= 0.0:
        return  # all faces degenerate; integrity check reports that
    # replace=False can only draw faces with nonzero probability
    n = min(cfg.thickness_samples, int((areas > 0).sum()))
    rng = np.random.default_rng(0)
    idx = rng.choice(len(mesh.faces), size=n, replace=False,
                     p=areas / total_area)
    origins = mesh.triangles_center[idx]
    directions = -mesh.face_normals[idx]
    # Nudge inward so the ray doesn't hit the source triangle.
    origins = origins + directions * 1e-4

    hits, ray_idx, _ = mesh.ray.intersects_location(
        origins, directions, multiple_hits=False)
    if len(hits) == 0:
        return
    thickness = np.linalg.norm(hits - origins[ray_idx], axis=1)
    thin = thickness < cfg.min_wall_mm
    frac = float(thin.mean())
    if frac > 0.02:
        sev = Severity.WARNING if frac < 0.2 else Severity.CRITICAL
        yield Finding(
            "walls", sev,
            f"Thin walls: {frac:.0%} of sampled surface under "
            f"{cfg.min_wall_mm} mm",
            f"Thinnest sampled wall ≈ {float(thickness.min()):.2f} mm; "
            f"with a {cfg.nozzle_mm} mm nozzle, walls below "
            f"{cfg.min_wall_mm} mm print weak or not at all.",
            {"thin_fraction": frac,
             "min_thickness_mm": float(thickness.min()),
             "sampled": int(n)},
        )


# --------------------------------------------------------------------------
# Bed contact & stability
# --------------------------------------------------------------------------

def check_stability(mesh: trimesh.Trimesh, cfg: Config):
    """Check first-layer bed adhesion and tip-over risk."""
    if len(mesh.faces) == 0:
        return
    on_plate = plate_contact_faces(mesh, cfg)
    contact = float(mesh.area_faces[on_plate].sum())
    footprint = mesh.extents[0] * mesh.extents[1]

    if contact < 1.0:
        yield Finding(
            "stability", Severity.CRITICAL, "Almost no bed contact",
            f"First-layer contact ≈ {contact:.2f} mm². The part touches the "
            "plate at a point or edge and will detach. Reorient, add a "
            "brim/raft, or flatten the base.",
            {"contact_area_mm2": contact},
        )
    elif footprint > 0 and contact / footprint < 0.05:
        yield Finding(
            "stability", Severity.WARNING, "Small bed contact patch",
            f"Contact area {contact:.0f} mm² is under 5% of the part's "
            f"footprint ({footprint:.0f} mm²). Consider a brim.",
            {"contact_area_mm2": contact, "footprint_mm2": float(footprint)},
        )

    # Tip-over: center of mass outside the convex hull of the contact patch,
    # approximated by the contact faces' XY bounding box.
    height = mesh.extents[2]
    if contact >= 1.0 and height > 3 * max(np.sqrt(contact), 1e-6):
        com = mesh.center_mass if mesh.is_watertight else mesh.centroid
        verts = mesh.triangles[on_plate].reshape(-1, 3)[:, :2]
        if len(verts):
            lo, hi = verts.min(axis=0), verts.max(axis=0)
            outside = np.any(com[:2] < lo - 1e-6) or np.any(com[:2] > hi + 1e-6)
            if outside:
                yield Finding(
                    "stability", Severity.WARNING, "Tip-over risk",
                    "Center of mass sits outside the bed-contact region on a "
                    "tall part; the print may topple mid-way. Add a brim or "
                    "reorient.",
                    {"height_mm": float(height),
                     "contact_area_mm2": contact},
                )


def check_bed_contact(mesh: trimesh.Trimesh, cfg: Config):
    """Catch a 'floating first layer': a large, near-horizontal down-facing
    surface hovering one-to-three layers above the bed while almost nothing
    truly touches z=0.

    This is the failure mode plate_contact_faces (used by check_stability)
    cannot see. That mask keys plate contact on each face's *highest* vertex
    (< 1.5 layers), so a flat face sitting whole at a uniform 0.25 mm reads as
    "on the plate" — its area is counted as contact and it is exempted from the
    overhang check — when in fact its entire area is a layer up in the air. The
    slicer then lays the intended first-layer surface down over nothing and the
    part never adheres. sweetheart-hamster v0.2 shipped exactly this: both
    hamster halves' ~47 cm² of cut faces floated at 0.25 mm while only a 0.7 mm
    hinge web touched the bed, and every gate passed it green (issue: the fuse
    work's floating-first-layer sibling).

    We key on each face's *lowest* vertex instead, so a uniformly-lifted face
    no longer counts as contact, and compare the area that genuinely reaches
    the bed against the area stranded just above it. A flat slab lifted whole
    puts ~all of its area in the "just above" band and ~none at the bed
    (ratio -> 0); a curved or angled real contact transitions smoothly and
    keeps comparable area in both bands (ratio well above the threshold), so it
    does not fire. Deliberately left separate from plate_contact_faces, whose
    1.5-layer leniency is intended for socket roofs and debossed ceilings —
    this check must not weaken that band, only add a signature it misses.
    """
    if len(mesh.faces) == 0:
        return
    lh = cfg.layer_height_mm
    down = -mesh.face_normals[:, 2]          # 1.0 = facing straight down
    near_horiz = down > 0.9                  # within ~26° of straight down: a
                                             # flat-ish face meant to lie down
    face_min_z = mesh.triangles[:, :, 2].min(axis=1)   # lowest vertex, not max
    areas = mesh.area_faces

    # Area that genuinely reaches the bed: a near-horizontal down-face whose
    # lowest vertex is within one layer (first-layer squish closes a sub-layer
    # gap, so a face under one layer up still adheres).
    real_mask = near_horiz & (face_min_z < lh)
    real_contact = float(areas[real_mask].sum())

    # Area stranded just above the bed: near-horizontal down-faces whose lowest
    # vertex sits one-to-three layers up. Under one layer is contact (above);
    # over three layers is a genuine recess/gap, not an accidentally-lifted
    # contact surface.
    band_hi = 3.0 * lh
    float_mask = near_horiz & (face_min_z >= lh) & (face_min_z < band_hi)
    floating = float(areas[float_mask].sum())

    if floating < cfg.bed_float_min_mm2:
        return                               # no substantial lifted surface
    if real_contact >= cfg.bed_float_ratio * floating:
        return                               # enough of the intended surface
                                             # reaches the bed (normal contact)

    fz = face_min_z[float_mask]
    yield Finding(
        "bed_contact", Severity.CRITICAL, "Floating first layer",
        f"{floating:.0f} mm² of near-horizontal down-facing surface hovers "
        f"{fz.min():.2f}–{fz.max():.2f} mm above the bed while only "
        f"{real_contact:.0f} mm² truly reaches z=0. The intended first-layer "
        "surface floats a layer up, so it would print over air and not "
        "adhere. Drop the geometry so the flat faces land on the plate (or "
        "reorient).",
        {"floating_area_mm2": floating,
         "real_contact_mm2": real_contact,
         "float_height_min_mm": float(fz.min()),
         "float_height_max_mm": float(fz.max()),
         "layer_height_mm": lh},
    )


# --------------------------------------------------------------------------
# Size: build volume and fine detail
# --------------------------------------------------------------------------

def check_size(mesh: trimesh.Trimesh, cfg: Config):
    """Check build-volume fit and flag unit mix-ups / sub-nozzle features."""
    if len(mesh.faces) == 0:
        return
    ext = mesh.extents
    bv = np.array(cfg.build_volume_mm)
    if np.any(ext > bv):
        # An oversize part might fit rotated: compare sorted dims.
        fits_rotated = np.all(np.sort(ext) <= np.sort(bv))
        sev = Severity.WARNING if fits_rotated else Severity.CRITICAL
        note = ("It would fit rotated." if fits_rotated
                else "It does not fit at any axis-aligned rotation.")
        yield Finding(
            "size", sev, "Exceeds build volume",
            f"Part is {ext[0]:.0f}×{ext[1]:.0f}×{ext[2]:.0f} mm; build "
            f"volume is {bv[0]:.0f}×{bv[1]:.0f}×{bv[2]:.0f} mm. {note}",
            {"extents_mm": [float(x) for x in ext],
             "build_volume_mm": [float(x) for x in bv]},
        )
    if float(ext.max()) < cfg.nozzle_mm * 4:
        yield Finding(
            "size", Severity.CRITICAL, "Model is microscopic",
            f"Largest dimension is {ext.max():.2f} mm — likely a unit "
            "mix-up (file in meters or inches interpreted as mm).",
            {"extents_mm": [float(x) for x in ext]},
        )
    elif float(ext.min()) < cfg.nozzle_mm * 2:
        yield Finding(
            "size", Severity.WARNING, "Sub-nozzle features",
            f"Smallest overall dimension is {ext.min():.2f} mm, near the "
            f"{cfg.nozzle_mm} mm nozzle width; detail at this scale will "
            "be lost.",
            {"extents_mm": [float(x) for x in ext]},
        )


ALL_CHECKS = [check_integrity, check_size, check_overhangs,
              check_walls, check_stability, check_bed_contact]
