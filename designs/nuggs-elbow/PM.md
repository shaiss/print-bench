# nuggs-elbow — product charter

## The product, in one paragraph

A first-party NUGGS corner module for the hamster-tunnel owner who already runs
NUGGS: a curved tube that turns an 80 mm-bore run through 45° (two coupled make
90°) while keeping the animal's path a continuous, smooth, unobstructed bore. It
must do one thing well: **route the run around a corner without ever putting a
ledge, step, or support scar inside the bore** — the corner an animal travels,
not a plumbing fitting.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Bore never necked below the welfare floor | ≥ 70 mm (target 80) | DTSchB entrance minimum, pouch-full (via `nuggs_cfg()` assert) | never — it is the welfare floor |
| N2 | Continuous smooth bore through the bend | no interior ledge/step; one bore cut | NUGGS welfare charter, brief #116 | never |
| N3 | No support *inside* the bore in the default print | `bend_angle` ≤ 45° prints supportless | issue #34 overhang measurements | a bore-safe support strategy is proven |
| N4 | Coupling is the shared NUGGS standard, unmodified | `nuggs_cfg()` defaults; ring OD 96.8 mm | `lib/nuggs-coupling.scad` | never — a changed port stops mating every other module |

## Out of scope

**Deferred** — see backlog.

**Never:**
- **Editing `lib/nuggs-coupling.scad` or its tolerances.** The elbow is a
  consumer; the port belongs to every module. A fit problem is tuned on the
  `nuggs` coupon's `port_tol`, not in this design.
- **A single-piece 90° elbow as the default.** It needs bore support (N3). It
  stays reachable via `bend_angle=90` for someone who accepts that, but the
  product is the 45° part and the two-elbow corner.
- **Windows / open-module variants.** That is a different module; this one is an
  enclosed bend.

## v1 — definition of done

- [x] Renders without CGAL errors; one watertight body (`Volumes: 2`).
- [x] `gate.sh --slice nuggs-elbow` exits 0 (printcheck no CRITICAL, test-slice).
- [x] Worst-point bore ø ≥ 70 mm measured off the export (measured 79.99).
- [x] Coupling-ring OD = 96.8 mm (the standard) — mates by construction.
- [x] `readme-gate.sh` passes; product page has the hero, bore cutaway, print
      settings and parameters.
- [ ] Human approves the shape and merges (taste is the merge decision).

## Product page & shots (art direction)

**Page promise.** "The corner piece for your NUGGS run that your hamster travels
through as smoothly as the straight — printed in one piece, no supports."

**Shot list — tier 1 (real studio renders).** None committed yet — the page
currently ships the deterministic OpenSCAD previews (`hero`, `bore`,
`bottom-iso`, contact sheet). A path-traced `product-hero` is a nice-to-have
(backlog B1); it needs `bpy`/CI, so it was not hand-faked.

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the smooth 45° corner, both ports | hero | warm PLA / satin | `part="elbow"` |

**Lifestyle scenes — tier 2 (AI, cosmetic, disclosed).** None.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Path-traced `product-hero` studio shot (`shots.conf`) | Hero image sells the page; low risk | CI `bpy` render |
| B2 | Turntable GIF of the elbow | Shows the 3D form; nice for the gallery | CI render |
| B3 | `pair` assembled shot (two elbows = 90°) | Communicates the two-elbow corner story | one render |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Is 45° the right default vs offering a 60° "accepts light bore overhang" middle? | No | 45° default; 60° reachable via `bend_angle` and documented |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-10 | `bend_angle` default 45°, 90° = two coupled elbows | Supportless enclosed-bore ceiling (#34); protects N2/N3 |
| 2026-08-10 | Tube built as one BOSL2 `path_sweep`; ports fuse to a 16 mm `port_stub` | Three hand-rolled builds (hull loft, cylinder+rotate_extrude, overlapping cylinders) passed CGAL but failed CI's Manifold backend (19 shells / non-manifold). A single swept polyhedron has no junction to fail. |
| 2026-08-10 | Brief's ~30 mm lead-in dropped to a 16 mm port stub | Non-material, non-blocking assumption; the Manifold-clean single-sweep construction has no straight leg fused to the bend. Amended on #116. |
| 2026-08-10 | No new coupon | No new mating clearance; the port fit is the standard's, gated by the lib |
