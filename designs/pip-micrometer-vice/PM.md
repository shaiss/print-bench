# pip-micrometer-vice — product charter

## The product, in one paragraph

A bench vice whose entire drivetrain — stationary trapezoidal screw, moving
jaw with its printed nut — comes off the bed as one working assembly: one
twist of the knob turns rotation into clamping travel, zero hardware, zero
post-print assembly. For anyone clamping small work at a bench (a PCB for
soldering, a dowel for sanding, a phone mid-repair). The one thing it must
do well: **turn a twist into real clamping force without the printed thread
welding to its nut** — that joint is the design's reason to exist, because
the catalog's print-in-place shelf has every prismatic and rotary joint
except the helical one.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Prints as one job, **no supports ever** — a support inside the thread welds the drivetrain, the exact failure under test | 0 support structures | brief #516 Printer row | never (the thesis) |
| N2 | Drivetrain is 100 % printed, zero fasteners/glue/assembly; the thread pair comes from `lib/threads-fdm.scad`'s one generator so male/female cannot drift | 0 hardware parts | brief #516 What-it-is | never |
| N3 | Screw stays horizontal and captive through the nut at every pose; the anti-rotation key (not the operator's hand) takes the reaction torque | 0 mm screw axial travel | brief #516; NOTES decision 1 | a field test shows the key cannot develop force |
| N4 | Opening 0–30 mm, jaw faces 40 × 20 mm, lead 2.0 mm/turn single-start, thread Ø12 | 30 / 40×20 / 2.0 / 12 mm | brief #516 Must-fit rows | the owner answers the travel open question (B2) |
| N5 | Base ≤ 80 × 60 mm with two M5 through-holes on a 40 mm grid | 80 × 60 mm; 2 × M5 | brief #516 Must-fit rows | the owner picks the clamp-edge mount instead (B5) |
| N6 | Gated by `ci.fusecheck` (`flexure` on the thread zone + `assert` separable bodies + the known-fused negative control) — a welded screw stays watertight and one body, invisible to printcheck | manifest present, control fires | brief #516 Printer row | never |
| N7 | Ships the two-station fit coupon (thread `tol`, key `clr_h`) before anyone prints the multi-hour body | 2 rows × 3 stations | brief #516 part breakdown | never |

## Out of scope

**Deferred** — see backlog. **Never:** metal inserts or any hardware in the
drivetrain (N2); an assembly step (the product is the anti-assembly);
orientations or variants that need supports (N1).

## v1 — definition of done

- [x] `render.sh` clean (no CGAL errors), bottom-iso inspected
- [x] `gate.sh --slice` exit 0 for vice + coupon, fusecheck ok with control firing
- [x] `readme-gate.sh` passes (hero shot is CI's `regen` to render)
- [x] Every Must-fit row measured on the exported mesh, not the parameter
- [ ] `/preflight` green
- [ ] Human reacts to the previews and merges (taste — theirs, not ours)
- [ ] Post-merge: a FIELD-TEST entry with the clamped-force measurement
      (~50 N target, kitchen scale — the `czs-slider` acceptance pattern)

## Product page & shots (art direction)

**Page promise:** "the whole working vice, off the bed in one print" — the
reader should understand the mechanism exists assembled and only needs
breaking in, and that the coupon tells them which fit to print.

**Mechanism honesty.** The as-printed pose (opening 12, exactly what CI
slices) is the page's spine: `contact-sheet` is embedded and every frozen
camera shoots the default pose. The one `-D` shot (`part="cutaway"` section)
removes half the body to *show* the inside — it adds information, and
`fusecheck` (N6) is the deterministic backstop behind it.

**Shot list — tier 1** (first = hero):

| Shot | What it sells | View | Look | Pose |
|---|---|---|---|---|
| product-hero | the vice as an object you want | 3/4 from working end, 30/25 | cast-steel satin, layer lines | as-printed |
| contact-sheet | the flat-bed no-support proof | 4-view incl. bottom-iso | OpenSCAD | as-printed (CI slices this) |
| section | the support story: screw never on air | cutaway 3/4 from +y | OpenSCAD | `part="cutaway"` (preview only) |
| vice-top | the gap, thread crossing the nut, M5 grid | straight down | OpenSCAD | as-printed |
| jaws | the working end close-up | 3/4 above | OpenSCAD | as-printed |
| coupon | which station to print | 3/4 thread-row side | OpenSCAD | as-printed |

No tier-1.5 / tier-2 AI shots in v1 — a mechanism whose whole claim is
"this really works printed" should not lead with approximate geometry.
Revisit after the first FIELD-TEST.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | 45° V on the fixed jaw for round stock | the most common vice feature request; cheap re-cut of one face | reprint (~44 g) + re-gate |
| B2 | 45 mm travel variant | PCB-with-fixture users; owner's open question | longer screw — printability of the span is the risk, needs its own render round |
| B3 | Multi-start lead (faster travel, coarser force) | annoyance-driven, only after real use | parameter flip + coupon re-sweep + re-gate |
| B4 | Replaceable jaw pads | sacrificial faces; brief deferred to v1+ | new part + plate question |
| B5 | Clamp-edge mount (18–20 mm bench lip) | drops the screw-hole dependency; owner's open question | base redesign, M5 row changes (N5) |
| B6 | Slim the coupon (3 h 31 m / 29.55 g today) | the brief promised "printable in minutes"; near-half the vice's cost defeats "print this first" | thin the plate, 1 station per row, re-gate |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| 30 vs 45+ mm travel | no | 30 (the stated default) |
| V-anvil on the fixed jaw | no | plain faces |
| M5 bolts vs clamp-edge mount | no — but the brief asked for the owner's call before the base froze | M5 through-holes (the *given* Must-fit row; clamp-edge is B5) |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-02 | Charter written from brief #516 | §5 PM checkpoint of the design run; every row transcribed from the brief, none invented — written after the geometry existed but sourced only from the brief thread |
| 2026-09-02 | Guideway = plain rails + saddle straddle + screw keying, not `slide_rail`/`slide_tab` lips | the lips occupy the y-band a 40 mm face sweeps (NOTES decision 3) — recorded as a brief-vocabulary deviation, accepted by gates |
| 2026-09-02 | M5 holes kept, clamp-edge not built | M5 is the given Must-fit row; the alternative is backlog B5 pending the owner |
| 2026-09-02 | Printability-review triage: bore-roof fix + seam note acted on now; coupon cost queued as B6 | the teardrop fix guards N1/N3 (a bridged bore roof is a designed weld); the coupon's 3.5 h is a real deviation from the brief's "minutes" prose but N7 (two-station coupon) ships first and honest — noted in the PR body |
