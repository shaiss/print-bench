# nuggs-probe-cap — product charter

## The product, in one paragraph

A sealed sensor end-cap for NUGGS tube-system owners who want a temperature
probe inside the habitat (or storage tube) without opening the bore to
bedding, seed husks or drafts. The customer is the person already running a
NUGGS build who just added a DS18B20 and found every end-cap either open or
breathing. The one thing it must do well: **pass the probe and its cable
through a closed wall** — the seal is printed split-finger grips, dust-and-
draft tight, explicitly not rated airtight.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Mates any NUGGS module: standard port, no redefinition | bore 80, wall 2.4, `port_tol` 0.30 | the standard (`lib/nuggs-coupling.scad`), via brief | the port standard itself changes |
| N2 | Prints with **no slicer supports** | every surface ≤ 50° or bridge < 5 mm | brief (given) | a feature can't be corrugated/chamfered into compliance |
| N3 | Port face down, grips in-plane, print pose = use pose | sector tips = bed contact | brief (given) | a future variant inverts orientation |
| N4 | No flat internal ceiling over an enclosed bore | 50° V-grooves, root ≥ 1.2 mm (3 perimeters) | issue #34 family rule; measured 84→92 | printcheck evidence contradicts #34's 45° ceiling |
| N5 | Every fit tunable on a ≤ 20-min coupon | `grip_clearance` ladder 0.05/0.10/0.20 | repo coupon convention | a fit changes that the coupon can't reach |
| N6 | Walls ≥ 1.2 mm everywhere; finger wall 1.6 mm | ≥ 3 perimeters at 0.4 nozzle | repo FDM rule (CLAUDE.md) | a probe size forces a thinner boss |
| N7 | The page never claims airtight | "not rated airtight" stated in README | the seal is printed fingers, untested | a gasketed variant ships (backlog B1) |

## Out of scope

**Deferred** — backlog below: gasketed/airtight variant; combined probe +
vent/filter cap (#592 follow-up); tool-mount sibling (the mandate's other
half).

**Never** — redefining or parameterizing the NUGGS port standard from this
design (it consumes `nuggs_cfg()`, it does not fork it); active sealing with
hardware (hose clamps, screw glands) — this is a printed-fingers design by
mandate.

## v1 — definition of done

- [x] Gate contract G1–G5 all green (issue #732 claim comment): render clean,
      `gate.sh --slice` exit 0 incl. coupon, readme-gate, measured-mesh
      dimension evidence, `/preflight`
- [x] Fitchecks prove both grips: nominal proxy seats (0 interference), +0.8
      jam negative controls fire
- [x] Print pose supportless — printcheck 92/100 cap, 100/100 coupon, slice
      plan 3 h 22 m, no supports
- [x] Coupon + tuning ladder documented (NOTES "Print this first")
- [x] Product page names the gap it fills and states the seal's limits

## Product page & shots (art direction)

**Page promise.** "Closes the tube — and still passes the sensor." A stranger
sees the three-boss grip face and understands both halves in one image: it's
a cap, the cylinders take probes.

**Mechanism honesty.** The as-printed `contact-sheet` (default pose, no
`-D`) is embedded beside the hero, and `print-pose` shows the underside as it
actually prints — the corrugated ceiling is visible there, so the
supportless claim is checkable on the page, not asserted. No posed view is
the only geometry-true view.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the grip face — the product itself | hero 35°/22° | graphite `4a4f54` matte (PETG reads matte; neutral keeps eyes on layout) | — |
| contact-sheet | as-printed truth, 4-view | default sheet | neutral | none (default) |
| hero (cameras.conf) | keeper face detail | 62° | preview | `part="cap"` |
| print-pose | supportless underside | 235° underside | preview | `part="cap"` |
| pair | it mates — the ecosystem claim | 62° mated | preview | `part="pair"` |
| cutaway | bores are through-tunnels | half-section | preview render | `part="cutaway"` |

**AI product stills — tier 1.5.** None for v1 — the studio render plus
preview set covers every angle that matters; a still would restyle a part
whose selling feature (the grip layout) is already legible.

**Lifestyle scenes — tier 2.** None for v1.

**Motion clips — tier 2.** None for v1 — the mechanism (quarter-turn mate) is
every NUGGS module's, not this design's novelty.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Gasketed (O-ring groove) variant for humid/washable habitats | The most-asked upgrade once seals exist; N7 currently limits claims | geometry + new gate surface, ~1 session |
| B2 | Probe + vent/filter combo cap (#592 sibling) | #592's breathing and this sealing are complements; owners will want both in one | new layout, coupon |
| B3 | Tool-mount end-cap (mandate's other half) | Named in the NUGGS mandate; smaller audience than sensing | new brief |
| B4 | Mouse-slot gland option (`gland_kind` param) | Only if a real cable squirms past the round grip — DECISION pending coupon | param + assert, small |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Owner's actual probe dimensions (Ø and length) | No — ships parametric | Ø 6.0 × 30 assumed (brief's band); README + coupon say "caliper before freezing" |
| Round gland vs mouse-slot | No | Round bore + fingers covers Ø 3.4–5; mouse-slot only if a real cable escapes (B4) |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-28 | Print pose = use pose, port-down on sector tips | Every NUGGS module's pose; grips print as in-plane vertical arcs; model frame is print frame so printcheck sees the real thing |
| 2026-09-28 | Corrugated 50° V-groove ceiling — the one deviation from the brief's "flat cap plate 2.4" | Flat = 5027 mm² unbridgeable overhang (84/100); #34 family rule; plate stays 2.4 at every tooth, keeper face stays flat, root ≥ 3 perimeters asserted |
| 2026-09-28 | Fitcheck proxies at nominal, never bore-size | Bore-size proxy shares boundary faces → CGAL zero-volume shell → 656 false interference facets; nominal + jam negative control is falsifiable |
| 2026-09-28 | Round gland, not mouse-slotted | Brief left it to the coupon; round + split fingers already spans Ø 3.4–5 and keeps round-probe compatibility |
| 2026-09-28 | Sealing claim = "keeps out bedding/husks/drafts, not rated airtight" | Printed-finger seal is untested against pressure; N7 makes the page say so rather than imply a rating |
