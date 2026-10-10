# gridfinity-starter — product charter

## The product, in one paragraph

A Gridfinity **starter set**: one screw-down 3×3 baseplate plus the three open
bins that drop into it (1×1×3U, 2×1×3U, 1×1 low tray). The customer is someone
with a drawer or shelf and a 0.4 mm-nozzle FDM printer who wants organized
storage in one print session. The one thing it must do well is
**interoperate**: every bin printed here drops into any community Gridfinity
plate, and every community bin drops into this plate — wrong-by-0.5 mm breaks
that, which is the entire point.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Grid pitch | 42 × 42 mm | kennetek `standard.scad` (MIT, numbers only) | the standard itself changes |
| N2 | Bin top per cell | 41.5 × 41.5 (42 − 0.5/side); multi-cell n×42 − 0.5 | same | the standard itself changes |
| N3 | Boss / socket profiles | 0.8↗/1.8↑/2.15↗ boss; socket +0.25/side wall, +0.35/side floor; heights 4.75 / 4.65 | kennetek profiles (NOTES spec table) | the standard itself changes |
| N4 | Print orientation | plate grid-down, bins opening-down | brief #733 mandate | owner decision on the issue |
| N5 | Repo FDM defaults | walls ≥ 1.2 mm, no slicer supports, 0.4 nozzle | CLAUDE.md + brief | repo convention change |
| N6 | Style | workshop-utility tokens (corner r 4, fn 96); **M4 mounts override the style's M3 hole vocabulary** — brief wins over style | brief + `style.conf`; exception recorded in NOTES.md | owner changes the brief |

## Out of scope

**Deferred** — ranked in the backlog below.

**Never** — bundling or including a GPL Gridfinity library (license boundary
#160; the clean-room numbers-only implementation is the design).

## v1 — definition of done

The frozen gate contract on issue #733 (all green; iteration 5, 2026-09-29,
is the shipped geometry — iteration 2's dimensions plus the tray-recess fix
and the contract's divider option, both from the pre-ship audit):

- [x] G1 — `render.sh gridfinity-starter` clean, bottom-iso inspected
- [x] G2 — `gate.sh --slice gridfinity-starter` exit 0, all 5 `ci.parts` (incl. the gated `bin-2x1-div` divider proof) + coupon
- [x] G3 — `readme-gate.sh gridfinity-starter` passes (product-hero from CI regen)
- [x] G4 — every Must-fit/hold dimension measured on the export (NOTES gate-evidence table)
- [x] G5 — `/preflight` green

Plus: the human approves the previews and merges. That approval **is** the
decision this charter does not make.

## Product page & shots (art direction)

**Page promise.** "One print turns a drawer into a Gridfinity system — and
everything mates with the community's parts."

No mechanism (nothing folds, snaps, slides or prints in place), so no
pose-hiding risk class; the as-printed faces that matter are shown anyway:
`contact-sheet` (assembled 4-view) and `plate-bedface` (the grid-down bed face,
square-on — see CAMERAS.md for why oblique fails there).

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the system, ready to drop in | hero | 8a919e satin | assembled (`part=""`) |
| contact-sheet | honest 4-view of what CI slices | contact sheet | default | assembled |
| iso | bins seated, one column empty | iso | default | assembled |
| top | grid alignment | straight down | default | assembled |
| plate-bedface | the print-critical bed face | square-on bed face | default | `part="baseplate"` |

No tier 1.5 / tier 2 shots yet — none owed by the brief.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Magnet pockets in bin bases | most-requested Gridfinity upgrade; drops-in without touching any mating surface | geometry + coupon re-tune + re-gate |
| B2 | Baseplate interconnect (join plates side-by-side) | turns one plate into a system; the starter's natural growth | new part + fit coupon |
| B3 | Weighted / skeletonized baseplate variant | savings/stability option; changes nothing users see | variant + printcheck re-run |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| none | — | — |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-29 | Clean-room, numbers-only implementation (MIT reference read for numbers, no code) | license boundary #160 |
| 2026-09-29 | Bin wall 1.2 mm, not community 0.95 | repo FDM floor; every mating surface is outside the wall |
| 2026-09-29 | M4 mounts override the style pack's M3 vocabulary | brief is the frozen contract; exception recorded in NOTES.md |
| 2026-09-29 | printcheck support-flags adjudicated WARN, orientation stands | brief's explicit orientation mandate + clean PrusaSlicer no-support test-slice |
| 2026-09-29 | Baseplate drawn at 4× style_fn (sampling only; dimensions unchanged — identical printcheck scores) | stylelift curve-smoothness floor 44: CGAL crease strips between zero-web sockets out-share the drawn arcs below fn 256 (matrix in NOTES.md) |
| 2026-09-29 | Tray recess fixed to actually cut (`difference` in `gf_bin`) — it had shipped as a solid cap | pre-ship audit: an additive "cutter" buries harmlessly and every gate stays green (watertight, sliceable, 76/100); only mesh measurement caught it — cavity evidence in NOTES.md iteration 5 |
| 2026-09-29 | Dividers: even spacing, cell-boundary aligned, ≥8 mm compartments; gated `bin-2x1-div` proof; tray interior = recess mouth | the frozen contract names "optional dividers"; tray walls are drafted, so a wall-based span would poke through |
