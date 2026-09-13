# stylelift — turn a model you like into a design spec you can check against

Point it at an STL. It measures how the object is *shaped* and writes that out
as a reusable style: numbers to build with, and rules that later parts are held
to.

```
$ stylelift measure reference.stl

stylelift — reference.stl
============================================================
  size:      76 x 33 x 16 mm
  triangles: 2,980   bodies: 5   watertight: True

  EDGE TREATMENT
    softness: 0.79   (1.0 = every edge curves, 0.0 = every edge is a corner)
    grammar:  rounded 74% / chamfered 5% / sharp 21%
    rounding vocabulary (outer):
      outer r =   4.000 mm    98% of curved edge length  (sweeps 84.4 deg, ~64 segments/turn)
    chamfers: 196 band(s), typical leg 0.6 mm
      leg  0.600 mm across a 90 deg corner, 32 mm of edge

  ROUND FEATURES
      2 x hole d = 3.4 mm, axis z, ~64 segments/turn
```

Everything is deterministic geometry: no AI, no network, no sampling without a
fixed seed. Re-running on the same mesh gives the same numbers.

## Install & use

```bash
pip install -e .                      # from this repo

stylelift measure model.stl           # what is this shape's design language?
stylelift measure model.stl --json    # machine-readable

# lift a style pack from reference mesh(es)
stylelift lift ref.stl --name workshop-utility \
    --source https://example.com/thing/123 --license CC-BY-4.0

# hold a new part to it — exit 1 if a required rule fails
stylelift check build/bracket.stl --style styles/workshop-utility

# regenerate style.scad + STYLE.md's tables from style.json (--check to verify)
stylelift sync styles/workshop-utility
```

In this repo, `./scripts/style-lift.sh` and `./scripts/style-check.sh` wrap
these with rendering and the repo's layout conventions.

## How it measures a radius

A tessellated cylinder of radius `r` folds by the same angle `θ` between every
pair of neighbouring strips, and each strip is a chord of width
`w = 2r·sin(θ/2)`. Read backwards, any fold gives the local radius of the
surface it sits on:

```
r = w / (2·sin(θ/2))
```

The estimate is exact for an inscribed tessellation and — the useful part —
**independent of how finely the model was tessellated**. The same design
exported at `$fn=24` and `$fn=64` measures the same radius; only the segment
count differs, which is itself reported as `implied_fn`. It is invariant under
rotation and covariant under scale, so a downloaded mesh in an arbitrary pose
measures the same as one resting on the bed.

**Where it is exact, and where it is not.** On quad-strip tessellation — what
OpenSCAD, Fusion and every other CAD exporter emits — measured error is under
0.5%. On a freely triangulated mesh (sculpted, or remeshed in Blender) there
are no strips: consecutive folds turn about non-parallel axes, and the same
estimator reads about 1.38x high on an equilateral triangulation. stylelift
reports which kind of mesh it is looking at (`edges.tessellation`) and flags
the radii as approximate rather than applying a correction factor that is only
stable at one extreme. For a sculpted reference, treat the radii as indicative
and confirm against the render.

Two guards make it trustworthy on real meshes:

- **Comparable strips only.** Where a curve meets a large flat face the fold is
  half-sized, which would report double the radius. A fold only counts when the
  surfaces on both sides are of comparable width across it.
- **Length-weighted modes, not averages.** A design language reuses a *small
  set* of radii. On a box rounded at 3 mm whose corners are spherical, the
  sphere's polar tessellation drags the median to 4.2 mm while the 3 mm mode
  still carries 30× more folded edge length. The reported vocabulary is the set
  of modes, each refined off the histogram grid so the value doesn't inherit
  the bin width.

## What it measures

| Property | Method | Reported as |
|---|---|---|
| Edge softness | fold angle vs edge length: does the surface curve or turn a corner? | `edges.softness` 0..1 |
| Edge grammar | which of rounded / chamfered / sharp owns the shaped edge length | `edges.grammar.*` |
| Rounding vocabulary | length-weighted modes of the per-fold radius, convex and concave | `edges.rounding.*` with share, sweep and implied `$fn` |
| Chamfers | narrow faces bridging two wider ones across two decisive folds; leg from `w = 2c·cos(T/2)` | `edges.chamfers.*` |
| Form curvature | curvature that closes on itself, or spans a third of the part: the shape, not a treatment of its edges | `edges.form.*` |
| Round features | closed curved bands — bores and pillars — grouped by size and axis | `features.cylinders`, `features.dominant_hole_d_mm` |
| Curve resolution | segments per full turn, snapped to a value a design would write | `implied_fn` |
| Facetedness (dihedral sharpness) | share of shaped edge length turning more than the mesh's own tessellation — normalized against the finest `$fn` the mesh declares, so a tessellated-smooth curve earns no credit for its tessellation edges | `edges.facetedness.*` with `sharpness`, `fn_curve`, `tessellation_turn_deg` and the `histogram` |
| Openness (projected void fraction) | open share of the silhouette, integrated over the sphere as a fan of parallel lines per view direction — pose-stable by construction, no favored projection | `openness.void_fraction`, `max_void_span_mm`, `min_bridge_mm` |
| Material thickness | inward ray casts from area-weighted samples; solid parts say so | `walls.*` with `shelled` |
| Massing | bbox fill, convexity, proportion | `massing.*` |
| Surface direction | area shares up / down / vertical / sloped, with dominant slopes (measured from the build direction, not the bed) | `orientation.*` |
| Overhang discipline | share of surface facing downward and shallower than 45° from the bed, excluding the footprint the bed carries | `orientation.unsupported_share`, `orientation.overhang_limit_deg` |
| Mirror symmetry | mirrored surface samples measured against the real surface | `symmetry.{x,y,z}` |

**Not** printability — that is [printcheck](../printcheck)'s job, and it stays
there. stylelift measures wall thickness because "this family builds at 2.4 mm"
is a style choice, not because thin walls are a defect.

`unsupported_share` sits closest to that line, so it is worth being precise
about which side it is on. printcheck asks *will this part print* and answers
per part, weighing overhang against orientation, bridging and material.
stylelift asks *did this designer refuse to place a face below 45 degrees*, and
answers as a number you can hold a family to. A part can be perfectly printable
with a 20° roof and supports; it is simply not in a family whose whole grammar
is the 45° cut. The metric reports the share and nothing else — no verdict, no
advice, no orientation search.

## How it tells a design facet from tessellation

`softness` cannot see a faceted design language. A stencil-cut plate and a
smooth box exported at `$fn=8` both turn steep folds everywhere; the angle
alone cannot separate them, because what separates them is whether the fold is
a *decision* or a *segment*. So the sharpness metric normalizes against the
curve resolution the mesh itself declares:

- A part that draws its curves at `$fn=64` has declared 5.6° to be
  tessellation — so its 45° folds must be design, and they count.
- A part whose finest curve is an 8-sided barrel has declared 45° to be one
  segment of that curve — so the same 45° fold there is tessellation, and it
  does not count.

The declared resolution (`edges.facetedness.fn_curve`) is the finest
`implied_fn` reported by the **edge rounding vocabulary and the cylindrical
features**. Form curvature is deliberately not consulted: a barrel or a sphere
is a parameterized surface whose fold angle varies across it, so a mode's
median turn there describes where the surface happens to sample, not a
resolution the author wrote — a uv sphere of `$fn=64` compresses to sub-degree
folds at its poles, which would drag the median to `$fn≈126` and set a
threshold finer than the author's own sampling. The latitude rings of that same
sphere are detected as cylinders at `$fn=64`, which is the truth the surface
mode buries. A mesh that draws no curve at all is held to the smooth-curve
convention (`fn_curve_fallback`, `$fn=48`).

`tessellation_turn_deg` is `1.1 × 360 / fn_curve` — the slack absorbs a
measured segment count wobbling by about a segment. `sharpness` is the share
of *shaped* edge length (folds of `flat_deg` or more, the same denominator
`softness` uses) that turns more than that. The `histogram` bins that edge
length by fold angle, each bin flagged by whichever kind owns most of it, so a
style can be written against the *shape* of the distribution and not only the
total.

## How it measures openness, and the legibility rule

A single projection cannot answer "how open is this part": face-on, a stencil
plate is mostly void; edge-on it is nearly all material. Any *chosen* view
smuggles the answer in with the choice. So `openness` integrates over the
sphere: `void_dirs` near-uniform view directions (a Fibonacci lattice —
deterministic, no RNG), a fan of `void_rays_per_dir` parallel lines through
each, and the open share of that view's silhouette is the fraction of lines
that cross the convex hull but never meet material. The mean over views is a
solid-angle integral, so rotating the part permutes the directions and changes
nothing — the pose stability is in the construction, not the sampling luck.
(The estimate still carries the lattice's sampling error, which shrinks as
`void_dirs` grows; the tests pin that directly.)

The convex hull is the reference silhouette, so deep concavities count as
openness alongside true cut-throughs: the honest reading of the number is "how
airy is the form". Alongside the fraction it reports the largest gap any line
threads (`max_void_span_mm`, as `max_void_span_fraction` of the part's largest
dimension — the glyph) and the narrowest material span (`min_bridge_mm`,
measured by inward normal rays the way `walls` measures — the web between two
cut-outs). Non-watertight meshes report `openness.measured: false` with the
reason, and every rule over these metrics skips rather than fails.

When a reference really is cut through, `stylelift lift` proposes the
legibility pair as **required** rules, and a hand-written pack copies the same
shape (constants `GLYPH_MIN_FRACTION`, `BRIDGE_MIN_WIDTHS`, `LINE_WIDTH_MM` in
`spec.py`):

```json
{"id": "legible-glyph", "metric": "openness.max_void_span_fraction",
 "op": "min", "value": 0.15, "severity": "required",
 "when": {"metric": "openness.max_void_span_mm", "op": "min", "value": 0.01},
 "why": "the largest cut-through must span at least 15% of the part, or it
         cannot be read at the distance a mark is read from"}

{"id": "bridge-width", "metric": "openness.min_bridge_mm",
 "op": "min", "value": 0.8, "severity": "required",
 "when": {"metric": "openness.max_void_span_mm", "op": "min", "value": 0.01},
 "why": "webs between cut-throughs print as lines: 2 extrusion widths of
         0.4 mm"}
```

The `when` gate is what keeps the pair honest, in both directions: a solid part
spans nothing, so the rules skip instead of failing it — while a plate of tiny
glyphs has almost no open area yet is exactly the part the legibility rule
exists for, so the gate is the *existence of a cut-through* (the largest span),
not the open-area fraction.

## Conformance

A style's rules are evaluated against a fresh measurement of a *different*
part, so every rule can declare a precondition. A cable clip with no rounded
edges is not violating a 4 mm corner radius — it has nothing to measure, and
the checker says `skip`, not `fail`:

```
  ok    corner-radius     measured    4.0001  expected 4 +-35% (2.6..5.4)
  ok    curve-smoothness  measured        64  expected >= 44
  skip  hole-vocabulary   measured         -  expected -
        does not apply: features.hole_count=0

  IN STYLE — 2 pass, 0 fail, 0 advisory, 1 not applicable
```

Rules are `required` (a failure exits 1) or `advisory` (reported, never fails).
Comparators are `min`, `max`, `near` (relative tolerance) and `range`. A rule
naming a metric the mesh doesn't carry is skipped rather than assumed.

## Tests

```bash
pip install -e '.[test]'
python -m pytest tests -q
```

The probe meshes in `examples/make_probe_models.py` are built from exact arcs
and lines, so the tests compare against known truth rather than a previous run:
a 3 mm fillet has to measure 3 mm, at any tessellation, in any pose, at any
scale. `python examples/make_probe_models.py probes/` writes them out to play
with.
