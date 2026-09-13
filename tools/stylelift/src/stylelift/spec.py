"""The style spec itself: tokens, conformance rules, and how a part is judged.

A measurement describes one mesh. A *spec* is the reusable part: the numbers a
new design should adopt (tokens) and the conditions it must meet to belong to
the family (rules). Rules are evaluated against a fresh measurement of a
different part, which is the whole point — and the reason every rule carries an
applicability precondition. A cable clip with no filleted edges is not "failing"
the family's 3 mm corner radius, it simply has nothing to measure, and a checker
that cannot tell those apart trains people to ignore it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

SCHEMA = "stylelift/style@1"

# Segment counts a design would actually write for $fn. Measured smoothness is
# snapped up to this ladder so a spec never asks for $fn = 83.
FN_LADDER = (16, 24, 32, 48, 64, 96, 128, 180, 256)

# Legibility of cut-through marks. These are the numbers a style pack's rules
# quote when its parts carry stencil glyphs or windows: a mark smaller than
# this fraction of the part cannot be read at the distance a mark is read
# from, and a web thinner than this many extrusion lines will not print as
# the line the design drew. When the reference itself is cut through, derive()
# proposes both as required rules; a hand-written pack copies the same shape.
GLYPH_MIN_FRACTION = 0.15   # glyph height >= 0.15 x part diameter
BRIDGE_MIN_WIDTHS = 2.0     # bridge width >= 2 x line width
LINE_WIDTH_MM = 0.4         # the extrusion width the bridge bound assumes


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


def dig(data: dict, path: str):
    """Fetch a dotted path out of a measurement dict, or None if absent."""
    node = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


@dataclass
class Result:
    rule: str
    status: Status
    measured: float | None
    expected: str
    severity: str
    why: str
    detail: str = ""

    def to_dict(self) -> dict:
        """Return the rule result as a JSON-serializable dict."""
        return {"rule": self.rule, "status": self.status.value,
                "measured": self.measured, "expected": self.expected,
                "severity": self.severity, "why": self.why,
                "detail": self.detail}


def _evaluate(op: str, measured: float, value, tol: float) -> tuple[bool, str]:
    """Apply one comparator; returns (ok, human-readable expectation)."""
    if op == "min":
        return measured >= value, f">= {value:g}"
    if op == "max":
        return measured <= value, f"<= {value:g}"
    if op == "near":
        lo, hi = value * (1 - tol), value * (1 + tol)
        return lo <= measured <= hi, f"{value:g} +-{tol:.0%} ({lo:.3g}..{hi:.3g})"
    if op == "range":
        lo, hi = value
        return lo <= measured <= hi, f"{lo:g}..{hi:g}"
    raise ValueError(f"unknown rule op {op!r}")


@dataclass
class StyleSpec:
    name: str
    title: str = ""
    summary: str = ""
    tokens: dict = field(default_factory=dict)
    rules: list = field(default_factory=list)
    asserted: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    measured: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "StyleSpec":
        """Read a style.json, rejecting a malformed one before it is used.

        style.json is hand-edited, so a typo in a rule is ordinary. Checking the
        shape here turns it into a named error on the file; letting it through
        would raise somewhere inside evaluation instead, and the process would
        exit 1 — the code that means "this part is off-style". The gate would
        then blame the part for a mistake in the spec.
        """
        doc = json.loads(Path(path).read_text())
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: a style must be a JSON object")
        schema = doc.get("schema")
        if schema != SCHEMA:
            raise ValueError(f"{path}: unsupported schema {schema!r} "
                             f"(this build reads {SCHEMA!r})")
        name = doc.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{path}: 'name' must be a non-empty string")
        rules = doc.get("rules", [])
        if not isinstance(rules, list):
            raise ValueError(f"{path}: 'rules' must be a list")

        def check_condition(cond: dict, where: str) -> None:
            """Validate a comparator triple — a rule, or a rule's 'when' gate.

            Both sides need this: an unvalidated `when` fails later inside
            conform() instead, where a non-numeric bound raises TypeError,
            escapes cli.main's except clause, and exits 1 — the code that means
            "this part is off-style". A typo in the spec must never be
            reported as a verdict on the part.
            """
            for key in ("metric", "value"):
                if key not in cond:
                    raise ValueError(f"{where}: missing {key!r}")
            if not isinstance(cond["metric"], str):
                raise ValueError(f"{where}: 'metric' must be a string")
            op = cond.get("op", "near")
            if op not in ("min", "max", "near", "range"):
                raise ValueError(f"{where}: unknown op {op!r} "
                                 "(min, max, near or range)")
            value = cond["value"]
            if op == "range":
                if (not isinstance(value, (list, tuple)) or len(value) != 2
                        or not all(isinstance(v, (int, float)) for v in value)):
                    raise ValueError(
                        f"{where}: op 'range' wants value [low, high]")
            elif not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{where}: 'value' must be a number")
            tol = cond.get("tol", 0.0)
            if not isinstance(tol, (int, float)) or isinstance(tol, bool):
                raise ValueError(f"{where}: 'tol' must be a number")

        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise ValueError(f"{path}: rule {i} must be an object")
            where = f"{path}: rule {rule.get('id', i)!r}"
            check_condition(rule, where)
            when = rule.get("when")
            if when is not None:
                if not isinstance(when, dict):
                    raise ValueError(f"{where}: 'when' must be an object")
                check_condition(when, f"{where} 'when'")
            if rule.get("severity", "required") not in ("required", "advisory"):
                raise ValueError(f"{where}: severity must be required or advisory")

        def mapping(key: str) -> dict:
            value = doc.get(key, {})
            if not isinstance(value, dict):
                raise ValueError(f"{path}: {key!r} must be an object")
            return value

        return cls(name=name, title=doc.get("title", ""),
                   summary=doc.get("summary", ""), tokens=mapping("tokens"),
                   rules=rules, asserted=mapping("asserted"),
                   provenance=mapping("provenance"),
                   measured=mapping("measured"))

    def to_dict(self) -> dict:
        """Return the whole spec as the JSON document that gets committed."""
        return {"schema": SCHEMA, "name": self.name, "title": self.title,
                "summary": self.summary, "provenance": self.provenance,
                "tokens": self.tokens, "asserted": self.asserted,
                "rules": self.rules, "measured": self.measured}

    def to_json(self, indent: int = 2) -> str:
        """Render the spec as pretty-printed JSON."""
        return json.dumps(self.to_dict(), indent=indent)


def conform(measurement: dict, spec: StyleSpec) -> list[Result]:
    """Judge one measured part against a style's rules."""
    results: list[Result] = []
    for rule in spec.rules:
        rid = rule.get("id", rule.get("metric", "?"))
        severity = rule.get("severity", "required")
        why = rule.get("why", "")
        when = rule.get("when")
        if when:
            gate = dig(measurement, when["metric"])
            if gate is None:
                results.append(Result(rid, Status.SKIP, None, "-", severity, why,
                                      f"{when['metric']} not measurable here"))
                continue
            ok, _ = _evaluate(when.get("op", "min"), float(gate),
                              when["value"], when.get("tol", 0.0))
            if not ok:
                results.append(Result(
                    rid, Status.SKIP, None, "-", severity, why,
                    f"does not apply: {when['metric']}={float(gate):.4g}"))
                continue
        value = dig(measurement, rule["metric"])
        if value is None:
            results.append(Result(rid, Status.SKIP, None, "-", severity, why,
                                  f"{rule['metric']} not present in measurement"))
            continue
        measured = float(value)
        ok, expected = _evaluate(rule.get("op", "near"), measured,
                                 rule["value"], rule.get("tol", 0.0))
        if ok:
            status = Status.PASS
        else:
            status = Status.FAIL if severity == "required" else Status.WARN
        results.append(Result(rid, status, round(measured, 4), expected,
                              severity, why))
    return results


def verdict(results: list[Result]) -> str:
    """One-line summary of a conformance run.

    "Nothing to check" must not read as "passed". Every rule that carries a
    family's identity is gated on the feature it measures — a corner radius
    rule cannot judge a part with no rounded edges — so a part sharing none of
    the family's features skips all of them and would otherwise sail through on
    the advisories alone. A plain turned knob is not in the same family as a
    chamfered utility box; it is simply not comparable, and saying so is the
    only honest answer.
    """
    if any(r.status is Status.FAIL for r in results):
        return "OFF-STYLE"
    judged = [r for r in results
              if r.severity == "required" and r.status is not Status.SKIP]
    if not judged:
        return "NOT COMPARABLE (no required rule could be evaluated)"
    if any(r.status is Status.WARN for r in results):
        return "IN STYLE (with advisories)"
    return "IN STYLE"


def snap_fn(measured_fn: float | None) -> int | None:
    """Snap a measured segment count up to a value a design would write."""
    if not measured_fn or measured_fn <= 0:
        return None
    for step in FN_LADDER:
        if measured_fn <= step * 1.08:      # 8% slack: 60 measured means 64
            return step
    return FN_LADDER[-1]


def _mm(value: float) -> float:
    """Round a measured length to a number a designer would actually type.

    A measurement of 0.5996 mm is a 0.6 mm chamfer; carrying the fourth decimal
    into a style token invites everyone downstream to copy noise.
    """
    return round(float(value), 2)


def derive(measurement: dict, name: str) -> tuple[dict, list]:
    """Derive starting tokens and rules from a reference measurement.

    Deliberately a *starting point*: the numbers are measured, but which of them
    define the family is a judgement call a human (or the /style-spec skill)
    makes afterwards by editing style.json. Tolerances here are wide enough that
    a differently-sized part in the same family passes.
    """
    tokens: dict = {}
    rules: list = []

    rounding = dig(measurement, "edges.rounding") or {}
    chamfers = dig(measurement, "edges.chamfers") or {}
    grammar = dig(measurement, "edges.grammar") or {}
    walls = measurement.get("walls", {})
    softness = dig(measurement, "edges.softness")

    corner = rounding.get("dominant_r_mm")
    share = rounding.get("dominant_share") or 0.0
    if corner and share >= 0.12:
        corner = _mm(corner)
        tokens["corner_r"] = corner
        rules.append({
            "id": "corner-radius",
            "metric": "edges.rounding.dominant_r_mm",
            "op": "near", "value": corner, "tol": 0.35,
            "severity": "required",
            "when": {"metric": "edges.rounding.dominant_share",
                     "op": "min", "value": 0.12},
            "why": f"the family reuses one radius ({corner:g} mm) on its "
                   "rounded edges; a part that rounds at a different scale "
                   "reads as a different family",
        })

    fn = snap_fn(rounding.get("implied_fn"))
    if fn:
        tokens["fn"] = fn
        rules.append({
            "id": "curve-smoothness",
            "metric": "edges.rounding.implied_fn",
            "op": "min", "value": max(8, int(fn * 0.7)),
            "severity": "required",
            "when": {"metric": "edges.rounding.dominant_share",
                     "op": "min", "value": 0.12},
            "why": f"curves in this family are drawn at about $fn={fn}; "
                   "visibly faceted curves break the family look",
        })

    leg = chamfers.get("dominant_leg_mm")
    if leg and (chamfers.get("count") or 0) >= 2:
        leg = _mm(leg)
        tokens["edge_chamfer"] = leg
        rules.append({
            "id": "chamfer-size",
            "metric": "edges.chamfers.dominant_leg_mm",
            "op": "near", "value": leg, "tol": 0.4,
            "severity": "advisory",
            "when": {"metric": "edges.chamfers.count", "op": "min", "value": 1},
            "why": f"chamfers in the reference are cut at about {leg:g} mm",
        })

    if softness is not None:
        softness = round(float(softness), 3)
        tokens["softness"] = softness
        if softness >= 0.5:
            rules.append({
                "id": "soft-edges",
                "metric": "edges.softness",
                "op": "min", "value": round(max(0.25, softness * 0.6), 3),
                # Advisory, not required: this is a share of edge *length*, and
                # at a fixed corner radius it falls as the part grows — a tray
                # built from these very tokens measures 0.47 where the small
                # swatch measures 0.81. A rule that fails a part for being big
                # is a rule people learn to ignore.
                "severity": "advisory",
                "why": "this is a soft family: most of its edge length curves "
                       "rather than turning a corner (falls as a part grows, "
                       "so advisory)",
            })
        elif softness <= 0.2:
            rules.append({
                "id": "crisp-edges",
                "metric": "edges.softness",
                "op": "max", "value": round(min(0.45, softness * 2 + 0.15), 3),
                "severity": "advisory",      # a length share; see soft-edges
                "why": "this is a crisp family: edges meet at a corner and are "
                       "broken by chamfers, not rounded away",
            })

    # Whichever grammar dominates the reference has to keep dominating: it is
    # the single most recognisable thing about a design language.
    ranked = sorted((("rounded_share", grammar.get("rounded_share", 0.0)),
                     ("chamfered_share", grammar.get("chamfered_share", 0.0)),
                     ("sharp_share", grammar.get("sharp_share", 0.0))),
                    key=lambda kv: -kv[1])
    top, top_value = ranked[0]
    if top_value >= 0.4:
        rules.append({
            "id": f"grammar-{top.split('_')[0]}",
            "metric": f"edges.grammar.{top}",
            "op": "min", "value": round(top_value * 0.6, 3),
            "severity": "advisory",          # a length share; see soft-edges
            "why": f"the reference treats {top_value:.0%} of its shaped edge "
                   f"length as {top.split('_')[0]}; that is the family's "
                   "dominant edge grammar",
        })

    # Facetedness is the axis softness cannot see: a stencil-cut plate and a
    # coarsely drawn smooth one both turn steep folds everywhere, and only the
    # share of that edge length which the mesh's own curves do NOT explain as
    # tessellation is design. Whichever side the reference sits on is the
    # family's look, so a smooth reference proposes a ceiling, a faceted one
    # a floor.
    facet = dig(measurement, "edges.facetedness") or {}
    sharpness = facet.get("sharpness")
    if sharpness is not None:
        sharpness = round(float(sharpness), 3)
        tokens["sharpness"] = sharpness
        if sharpness >= 0.5:
            rules.append({
                "id": "facet-sharpness",
                "metric": "edges.facetedness.sharpness",
                "op": "min", "value": round(max(0.25, sharpness * 0.6), 3),
                "severity": "advisory",      # a length share; see soft-edges
                "when": {"metric": "edges.facetedness.shaped_length_mm",
                         "op": "min", "value": 1.0},
                "why": "this is a faceted family: most of its shaped edge "
                       "length is decided angle above what its own curve "
                       "resolution explains as tessellation",
            })
        elif sharpness <= 0.2:
            rules.append({
                "id": "no-design-facets",
                "metric": "edges.facetedness.sharpness",
                "op": "max", "value": round(max(0.3, sharpness * 2 + 0.15), 3),
                "severity": "advisory",      # a length share; see soft-edges
                "when": {"metric": "edges.facetedness.shaped_length_mm",
                         "op": "min", "value": 1.0},
                "why": "this is a smooth family: its edges are curve "
                       "tessellation, and folds that steep but undeclared "
                       "would read as unwanted facets",
            })

    if walls.get("shelled"):
        wall = walls.get("mode_mm")
        if wall:
            wall = _mm(wall)
            tokens["wall"] = wall
            rules.append({
                "id": "wall-thickness",
                "metric": "walls.mode_mm",
                "op": "min", "value": round(wall * 0.75, 3),
                "severity": "advisory",
                # A solid part has no wall to compare: skip rather than fail it.
                "when": {"metric": "walls.shelled", "op": "min", "value": 1},
                "why": f"the family builds at about {wall:g} mm of material; "
                       "thinner walls change how solid the part feels",
            })

    # How airy the form is, pose-stably, and — when the family really is cut
    # through — the legibility pair: a glyph big enough to read and webs wide
    # enough to print. Those two are required, not advisory: a stencil that
    # fails them does not merely look off-style, it cannot do its job.
    openness = measurement.get("openness") or {}
    if openness.get("measured"):
        void = float(openness.get("void_fraction") or 0.0)
        tokens["void_fraction"] = round(void, 3)
        measured_gate = {"metric": "openness.measured", "op": "min", "value": 1}
        if void >= 0.05:
            rules.append({
                "id": "openness",
                "metric": "openness.void_fraction",
                "op": "min", "value": round(void * 0.6, 3),
                "severity": "advisory",
                "when": measured_gate,
                "why": f"the reference is cut through ({void:.0%} of its "
                       "silhouette is open); a solid part reads as a "
                       "different family entirely",
            })
            rules.append({
                "id": "legible-glyph",
                "metric": "openness.max_void_span_fraction",
                "op": "min", "value": GLYPH_MIN_FRACTION,
                "severity": "required",
                # Gated on "a cut-through measurably exists", not on the void
                # fraction: a plate of tiny glyphs has almost no open area but
                # is exactly the part the legibility rule exists for. A solid
                # part spans nothing, so it skips.
                "when": {"metric": "openness.max_void_span_mm",
                         "op": "min", "value": 0.01},
                "why": f"the family's cut-throughs are legible marks: the "
                       f"largest must span at least {GLYPH_MIN_FRACTION:.0%} "
                       "of the part, or it cannot be read at the distance a "
                       "mark is read from",
            })
            bridge = _mm(BRIDGE_MIN_WIDTHS * LINE_WIDTH_MM)
            rules.append({
                "id": "bridge-width",
                "metric": "openness.min_bridge_mm",
                "op": "min", "value": bridge,
                "severity": "required",
                "when": {"metric": "openness.max_void_span_mm",
                         "op": "min", "value": 0.01},
                "why": f"the webs between cut-throughs must print as the "
                       f"lines the design drew: at least "
                       f"{BRIDGE_MIN_WIDTHS:g} extrusion widths of "
                       f"{LINE_WIDTH_MM:g} mm, i.e. {bridge:g} mm",
            })
        else:
            rules.append({
                "id": "closed-form",
                "metric": "openness.void_fraction",
                "op": "max", "value": 0.02,
                "severity": "advisory",
                "when": measured_gate,
                "why": "the family is solid: cut-throughs would change how "
                       "it reads more than any edge treatment could",
            })

    hole = dig(measurement, "features.dominant_hole_d_mm")
    if hole:
        hole = _mm(hole)
        tokens["hole_d"] = hole
        rules.append({
            "id": "hole-vocabulary",
            "metric": "features.dominant_hole_d_mm",
            "op": "near", "value": hole, "tol": 0.12,
            "severity": "advisory",
            # A part with nothing to bolt is not off-style for having no holes.
            "when": {"metric": "features.hole_count", "op": "min", "value": 1},
            "why": f"the family's fastener vocabulary is a {hole:g} mm hole; "
                   "mixing fastener sizes across a family is what makes a set "
                   "of parts feel unrelated",
        })

    ratio = dig(measurement, "ratios.radius_to_wall")
    if ratio:
        ratio = round(float(ratio), 3)
        tokens["radius_to_wall"] = ratio
        rules.append({
            "id": "radius-to-wall",
            "metric": "ratios.radius_to_wall",
            "op": "near", "value": ratio, "tol": 0.5,
            "severity": "advisory",
            "why": "scale-free check that rounding and material thickness stay "
                   "in the same proportion as the reference",
        })

    massing = measurement.get("massing", {})
    if massing.get("bbox_fill"):
        fill = round(float(massing["bbox_fill"]), 3)
        tokens["bbox_fill"] = fill
        rules.append({
            "id": "massing",
            "metric": "massing.bbox_fill",
            "op": "near", "value": fill, "tol": 0.45,
            "severity": "advisory",
            "why": "how much of its bounding box the form fills — blocky "
                   "versus carved-away",
        })
    return tokens, rules
