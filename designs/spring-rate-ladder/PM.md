# spring-rate-ladder — product charter

## The product, in one paragraph

A **measured spring constant to design against**. The customer is anyone
designing a compliant mechanism in printed plastic who today models against a
literature G that is wrong by ±20 % on their filament (the pop-fidget-card
field test found PLA flexures printing stiffer than modeled; #675 deferred a
whole PLA pawl variant on the same surprise). The one thing it must do well:
let that person press on a coupon with a kitchen scale and leave with a
number — their filament's effective G — plus a ladder of three springs whose
embossed predictions the measurement validates.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Wire at or above the FDM wall floor | d ≥ 1.2 mm | repo printability convention | a measured field test shows 1.6 mm faceting shifts k (then 2.0, never below) |
| N2 | Coil prints support-free | lead ≤ 45° | brief (given, `lib/threads-fdm.scad` argument) | a field test reports sagging wraps — actual lead is 5–10°, a tenth of the budget |
| N3 | Free length leaves measurable travel | l_free ≥ solid + 2 mm | brief acceptance | never in v1 |
| N4 | Embossed numbers come from the same parameters as the geometry | always | issue #734 brief ("derived k") | never — a hand-typed number on the plate is the one thing this product cannot ship |
| N5 | Cap seats without shaving the spring or binding the post | 0.6 / 0.3 mm radial clearance | design (ci.fitchecks gate) | coupon field-test reports binding at the defaults |

N1–N3 are `assert`s in `helix_spring()`; N5 is gated by `ci.fitchecks`
(`fitcheck` empty + `fitcheck_neg` interferes). All five fail the render, not
the reviewer.

## Out of scope

**Deferred** — in the backlog below.

**Never:**

- A fourth station varying wire Ø (k ∝ d⁴): breaks the ladder's one-variable
  comparison *and* changes the wire the coupon tunes. The brief left it as a
  non-blocking question; it is declined for v1 and named as a follow-up.
- Replacing machine springs: printed PLA/PETG springs live at ~1 N and low
  cycle counts. No load-class claims.
- Wire below 1.2 mm: not printable at a 0.4 nozzle.

## v1 — definition of done

- [x] Three stations N = 4/6/8 on one plate, predictions embossed (computed
      in-render, echoed by the gate log)
- [x] Coupon + guided cap measure k and back out G (procedure in README)
- [x] `gate.sh --slice` green for ladder / coupon / cap, both fitcheck verbs
- [ ] A field test validating predicted vs measured k on a real printer
      (owner's print; the FIELD-TEST convention records it)

## Product page & shots (art direction)

**Page promise.** "This plate turns your filament's stiffness from a guess
into a number you measured."

**Mechanism honesty.** The springs are the mechanism. The as-printed
`contact-sheet` (plate down, springs up — exactly what CI slices) is embedded
alongside the hero, and `station-close` resolves individual coils so a
reviewer can see the helix is open, not welded. The cap's *print pose*
(disc-down) is shown, not just its working pose.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the whole ladder as one honest object | 3/4, rotz 30 / elev 25 | teal `2a9d8f`, satin | none |
| contact-sheet | what actually goes on the bed | 4-view | — | none |
| layout-top | the embossed table reads as a table | ortho top | — | none |
| station-close | real open coils, closed ends | close 3/4 | — | none |
| coupon / cap | the measurement rig and its print pose | 3/4 | — | `part="cap"` for the cap |

**AI product stills — tier 1.5.** None in v1; the geometry-true tier-1 set
sells a measurement instrument best.

**Lifestyle scenes — tier 2.** None in v1.

**Motion clips — tier 2.** None in v1 (compressing the spring on camera is
the field test's job, not an AI clip).

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | FIELD-TEST entry: measured k + back-out G on PLA and PETG | the product's whole claim, first proof | one coupon + cap print, ~3.6 g + scale |
| B2 | `d_wire = 2.0` variant if faceting shifts k | k ∝ d⁴ makes wire fidelity the dominant error | re-render, re-emboss is automatic |
| B3 | G write-back into `printer.conf` via the print-feedback loop | closes the loop #101 was built for | one FIELD-TEST entry once opted in |
| B4 | Fourth station varying D (k ∝ 1/D³) | second-order once N-comparison exists | plate grows ~36 mm |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| none | — | — |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-28 | Decline the d-varying fourth station | the ladder's identity is "differ only in N"; named follow-up (B4), not scope |
| 2026-09-29 | Cap seats on the wire's top *surface* + 0.2 mm gap, not the centerline | iter-1 fitcheck FAIL: centerline seating put the disc 0.8 mm inside the wire |
| 2026-09-29 | `end_gap = 0.2` between closed end coils | a self-tangent polyhedron is non-manifold; 0.2 mm is under one extrusion width so the dead coils weld in print, as a real closed end behaves |
