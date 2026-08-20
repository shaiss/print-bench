# nuggs-y-splitter — product charter

## The product, in one paragraph

A first-party NUGGS junction module for the hamster-tunnel owner who already
runs NUGGS: one inlet, two symmetric outlets at a 60° included angle, that
branches an 80 mm-bore run into two paths while keeping every path a
continuous, smooth, unobstructed bore. It must do one thing well: **split the
run without ever putting a ledge, step, or support scar inside any bore** —
the fork an animal travels through, not a plumbing fitting. Branching was the
one topology the ecosystem could not do; that gap is the product.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Bore never necked below the welfare floor | ≥ 70 mm (target 80) | DTSchB entrance minimum, pouch-full (via `nuggs_cfg()` assert) | never — it is the welfare floor |
| N2 | Continuous smooth bore through the fork — no interior ledge | one cavity cut; blend sphere swallows every cap (asserted) | NUGGS welfare charter, brief #284 | never |
| N3 | No support inside any bore in the default print | every junction surface ≤ 45° from vertical in the print pose; 30° shipped | issue #34 overhang measurements; measured 0.000 mm² cavity overhang on the export | a bore-safe support strategy is proven |
| N4 | Coupling is the shared NUGGS standard, unmodified | `nuggs_cfg()` defaults; ring OD 96.8 mm | `lib/nuggs-coupling.scad` | never — a changed port stops mating every other module |
| N5 | Both outlets accept a mating module simultaneously | branch arms ≥ 2·r_out apart at the faces (asserted) | assembly sweep, measured ~16 mm clearance | the port standard changes |

## Out of scope

**Deferred** — see backlog.

**Never:**
- **Editing `lib/nuggs-coupling.scad` or its tolerances.** The splitter is a
  consumer; the port belongs to every module. A fit problem is tuned on this
  design's coupon (`port_tol`), not in the lib.
- **A T-junction (90° branch).** The brief excludes it; it needs bore support
  (N3) and is a different module.
- **A valve / gate / flow control.** The brief excludes it.
- **Windows / open-module variants.** A different module; this one is an
  enclosed fork.

## v1 — definition of done

- [x] Renders without CGAL errors; one watertight body.
- [x] `gate.sh --slice nuggs-y-splitter` exits 0 (printcheck no CRITICAL,
      test-slice on both parts).
- [x] Bore measured off the export ≥ 70 mm (measured 79.83 mm).
- [x] Coupling-ring OD = 96.80 mm (the standard) — mates by construction.
- [x] Zero interior-bore surface beyond 45° (measured 0.000 mm²).
- [x] Fits the target bed class: 94.9 × 192.9 × 191.0 mm print pose, under
      the stock 250 mm slicer height (asserted).
- [x] `readme-gate.sh` passes; product page has hero, bore cutaway, print
      settings, parameters, print-this-first coupon.
- [ ] Human approves the shape and merges (taste is the merge decision).

## Product page & shots (art direction)

**Page promise.** "The branch piece your NUGGS run was missing — one path
becomes two, printed in one piece, no supports, and your hamster travels the
fork as smoothly as the straight."

**Shot list — tier 1 (real studio renders).** None committed yet — the page
currently ships the frozen `previews/` cameras (hero, bottom-iso, bore
cutaway, contact sheet). When a product shot is wanted: the hero should show
the Y with the inlet down and both branch mouths toward the camera (the
branching is the product — both outlets visible in one glance), natural PETG
look, on the standard studio floor.

**AI tiers (1.5 stills, 2 lifestyle/motion).** None. The page's promise is
honesty about an animal's passage; the geometry-true previews carry it. Revisit
only if the family adopts AI tiers as a set.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Product shot (`shots.conf`) — a tier-1 hero for the page | The page's first image is currently a preview render; a studio shot sells the branch shape | one CI render cycle |
| B2 | Big-bed variant: `inlet_len = 80` behind a taller build-volume flag | The brief assumed ~80 mm; owners of ≥ 300 mm-tall beds can have it | parameter only; needs its own gate run |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Is 60 mm inlet length acceptable vs the brief's assumed ~80 mm? | No — shipped at 60 with the measured bed reason recorded in NOTES.md and on the PR | A bigger-bed owner raises it; the assert guards the 250 mm stock wall |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-17 | Ports + straight shells + one cavity, not `nuggs_neck()` per arm | Shared cylindrical surfaces between neighbouring arm shells — the class CGAL passes and CI's Manifold backend rejects (announced on #284 before geometry) |
| 2026-08-17 | `inlet_len = 60`, not the brief's ~80 | Measured: 211 mm print pose vs PrusaSlicer's stock 250 mm hard height (200 passes / 201 fails by probe); branch length is pinned by assembly clearance, so the inlet is the only free length |
| 2026-08-17 | Junction blend sphere R = ro − 3·nozzle | Flat cavity caps leave sub-mm exposed crescents (measured 0.45 mm) — an interior ledge; the sphere swallows every cap disc whole (asserted) |
| 2026-08-17 | Ship the coupon, unlike the elbow | The adopted contract says so, and this is the family's biggest single print — the worst place to discover a shrunken bore |
