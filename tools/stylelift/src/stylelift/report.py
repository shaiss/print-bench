"""Human-readable rendering of a measurement and of a conformance run."""

from __future__ import annotations

from .spec import LINE_WIDTH_MM, Result, Status, StyleSpec, verdict

_MARK = {Status.PASS: "ok  ", Status.FAIL: "FAIL", Status.WARN: "warn",
         Status.SKIP: "skip"}


def _modes(modes: list[dict], label: str) -> list[str]:
    out = []
    for m in modes:
        fn, sweep = m.get("implied_fn"), m.get("sweep_deg")
        detail = []
        if sweep:
            detail.append(f"sweeps {sweep:g} deg")
        if fn:
            detail.append(f"~{fn:g} segments/turn")
        out.append(f"      {label} r = {m['r_mm']:>7.3f} mm  "
                   f"{m['share']:>5.0%} of curved edge length"
                   + (f"  ({', '.join(detail)})" if detail else ""))
    return out


def measurement_text(m: dict) -> str:
    """Render a measurement dict as a terminal report."""
    mesh, edges = m["mesh"], m["edges"]
    massing, walls = m["massing"], m["walls"]
    lines = [f"stylelift — {m['source']}", "=" * 60]
    extents = massing["extents_mm"]
    lines.append(f"  size:      {extents[0]:g} x {extents[1]:g} x {extents[2]:g} mm")
    lines.append(f"  triangles: {mesh['faces']:,}   bodies: {mesh['bodies']}   "
                 f"watertight: {mesh['watertight']}")
    if not edges.get("folds"):
        lines.append("\n  no measurable edges (empty or degenerate mesh)")
        return "\n".join(lines)

    rounding, chamfers = edges["rounding"], edges["chamfers"]
    grammar = edges["grammar"]
    lines += ["", "  EDGE TREATMENT",
              f"    softness: {edges['softness']:.2f}   "
              f"(1.0 = every edge curves, 0.0 = every edge is a corner)",
              f"    grammar:  rounded {grammar['rounded_share']:.0%} / "
              f"chamfered {grammar['chamfered_share']:.0%} / "
              f"sharp {grammar['sharp_share']:.0%}"]
    if rounding["convex"]:
        lines.append("    rounding vocabulary (outer):")
        lines += _modes(rounding["convex"], "outer")
    if rounding["concave"]:
        lines.append("    rounding vocabulary (inner fillets / bores):")
        lines += _modes(rounding["concave"], "inner")
    if not rounding["convex"] and not rounding["concave"]:
        lines.append("    no rounded edges found")
    if edges.get("tessellation") != "strip" and (rounding["convex"]
                                                 or rounding["concave"]):
        lines.append(
            f"    NOTE: {edges['tessellation']} mesh (only "
            f"{edges.get('strip_share', 0):.0%} of curved surface is quad "
            "strips). Radii here are approximate — a freely triangulated "
            "mesh reads roughly 1.4x high. Check them against the render "
            "before writing them into a style.")
    shape = edges.get("form", {})
    if shape.get("convex") or shape.get("concave"):
        lines.append("    form curvature (the shape itself, not an edge "
                     "treatment):")
        lines += _modes(shape.get("convex", []), "outer")
        lines += _modes(shape.get("concave", []), "bore ")
    if chamfers["bands"]:
        lines.append(f"    chamfers: {chamfers['count']} band(s), "
                     f"typical leg {chamfers['dominant_leg_mm']:g} mm")
        for b in chamfers["bands"][:3]:
            lines.append(f"      leg {b['leg_mm']:>6.3f} mm across a "
                         f"{b['turn_deg']:g} deg corner, "
                         f"{b['length_mm']:g} mm of edge")

    features = m["features"]["cylinders"]
    if features:
        lines += ["", "  ROUND FEATURES"]
        for f in features:
            lines.append(f"    {f['count']:>3} x {f['kind']:<4} "
                         f"d = {f['d_mm']:g} mm, axis {f['axis']}, "
                         f"~{f['implied_fn']:g} segments/turn")

    facet = edges.get("facetedness") or {}
    if facet.get("tessellation_turn_deg") is not None:
        lines += ["", "  FACETEDNESS"]
        if facet.get("fn_curve"):
            basis = (f"the mesh's finest curve draws ~{facet['fn_curve']:g} "
                     "segments/turn")
        else:
            fallback = int(m.get("config", {}).get("fn_curve_fallback", 48))
            basis = (f"no curve declared; the smooth-curve convention "
                     f"($fn={fallback}) stands in")
        lines.append(f"    sharpness: {facet['sharpness']:.2f} of shaped edge "
                     "length is design facet (0.0 = all tessellation)")
        lines.append(f"    tessellation: folds up to "
                     f"{facet['tessellation_turn_deg']:g} deg are curve "
                     f"segments — {basis}")
        bins = facet.get("histogram") or []
        if bins:
            cells = [f"{b['lo_deg']:g}-{b['hi_deg']:g}:{b['share']:.0%}"
                     + ("*" if b["facet"] else "")
                     for b in bins]
            lines.append("    histogram (share of shaped edge length, "
                         "* = mostly facet):")
            lines.append("      " + "  ".join(cells))

    openness = m.get("openness") or {}
    if openness and not openness.get("measured"):
        reason = openness.get("reason") or "mesh is not watertight"
        lines += ["", "  OPENNESS", f"    not measurable: {reason}"]
    elif openness.get("measured"):
        lines += ["", "  OPENNESS (solid-angle integral, "
                  f"{openness['directions']} views x "
                  f"{openness['rays_per_direction']} lines)"]
        lines.append(f"    void fraction: {openness['void_fraction']:.1%} of "
                     f"the silhouette is open "
                     f"({openness['views_with_void']} of "
                     f"{openness['directions']} views see void)")
        if openness.get("max_void_span_mm"):
            lines.append(f"    largest cut-through: "
                         f"{openness['max_void_span_mm']:g} mm "
                         f"({openness['max_void_span_fraction']:.0%} of the "
                         "part)")
        if openness.get("min_bridge_mm") is not None:
            widths = openness["min_bridge_mm"] / LINE_WIDTH_MM
            lines.append(f"    narrowest bridge: "
                         f"{openness['min_bridge_mm']:g} mm "
                         f"({widths:g} extrusion lines at "
                         f"{LINE_WIDTH_MM:g} mm)")

    lines += ["", "  MASSING"]
    aspect = massing["aspect"]
    lines.append(f"    proportion: {aspect[0]:g} : {aspect[1]:g} : {aspect[2]:g}"
                 "  (longest : mid : shortest)")
    if massing["bbox_fill"] is not None:
        lines.append(f"    fills {massing['bbox_fill']:.0%} of its bounding box"
                     f"; convexity {massing['convexity']:.2f}")
    orient = m["orientation"]
    if "up_share" in orient:
        lines.append(f"    surface: {orient['up_share']:.0%} up / "
                     f"{orient['down_share']:.0%} down / "
                     f"{orient['vertical_share']:.0%} vertical / "
                     f"{orient['sloped_share']:.0%} sloped")
        for s in orient.get("dominant_slopes", []):
            lines.append(f"      slope {s['angle_deg']:g} deg over "
                         f"{s['share']:.0%} of the surface")
    if walls.get("measured"):
        kind = "wall" if walls.get("shelled") else "solid section"
        lines.append(f"    {kind}: typical {walls['mode_mm']:g} mm "
                     f"(median {walls['median_mm']:g}, thinnest "
                     f"{walls['min_mm']:g})")
    sym = m.get("symmetry") or {}
    if sym:
        mirrors = [k for k, v in sym.items() if v >= 0.995]
        lines.append(f"    mirror symmetry: "
                     + (", ".join(f"{k}={sym[k]:.2f}" for k in sym))
                     + (f"  (clean mirrors: {'+'.join(mirrors)})" if mirrors else ""))
    return "\n".join(lines)


def conformance_text(model: str, spec: StyleSpec, results: list[Result]) -> str:
    """Render a conformance run as a terminal report."""
    lines = [f"stylelift conform — {model}",
             f"  style: {spec.name}" + (f" ({spec.title})" if spec.title else ""),
             "=" * 60]
    width = max((len(r.rule) for r in results), default=4)
    for r in results:
        measured = "-" if r.measured is None else f"{r.measured:g}"
        tag = "" if r.severity == "required" else " [advisory]"
        lines.append(f"  {_MARK[r.status]}  {r.rule:<{width}}  "
                     f"measured {measured:>9}  expected {r.expected}{tag}")
        if r.status in (Status.FAIL, Status.WARN) and r.why:
            lines.append(f"        why it matters: {r.why}")
        if r.status is Status.SKIP and r.detail:
            lines.append(f"        {r.detail}")
    counts = {s: sum(1 for r in results if r.status is s) for s in Status}
    lines += ["", f"  {verdict(results)} — {counts[Status.PASS]} pass, "
                  f"{counts[Status.FAIL]} fail, {counts[Status.WARN]} advisory, "
                  f"{counts[Status.SKIP]} not applicable"]
    return "\n".join(lines)
