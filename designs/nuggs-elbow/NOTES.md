# nuggs-elbow — engineering log

Design brief: issue #116 (`design-brief`). This is the resume-cold record;
README.md is the product page, PM.md the charter.

## Goal

A first-party NUGGS module: a curved (elbow) tube that routes an 80 mm-bore run
around a corner, carrying the genderless quarter-turn NUGGS port
(`nuggs_neck()`/`nuggs_port()` from `lib/nuggs-coupling.scad`) on each end,
joined by a bent tube shell with a **continuous, smooth bore through the bend**
(welfare non-negotiable). It is a consumer of the port standard, exactly like
`designs/nuggs`: it builds one `cfg` with `nuggs_cfg()` defaults and never
redefines a coupling number.

## Given measurements (all from the NUGGS standard / brief)

Inherited from `nuggs_cfg()` defaults so it mates with `designs/nuggs` and
`nuggs-yard`: bore 80, wall 2.4, lug_r 6, port_proj 10, collar_t 3, n_lug 3,
lug_deg 40, rib_h 1.0, rib_w 2.4, rib_deg 12, twist_deg 14, bite 0.8,
port_tol 0.30, nozzle 0.4 (mm/deg). Derived: tube OD 84.8, coupling-ring OD 96.8.

Bend (from the intake decision, parameterized): `bend_angle` default **45°**,
`bend_radius` 120 mm (~1.5× bore), `lead_in` 30 mm per end.

## Key decision — the 45° default (the brief's flagged printability crux)

The brief handed print orientation / support / split-variant to the session and
held *continuous smooth bore* as a welfare non-negotiable. Issue #34 measured
this exact case: a vertically-printed enclosed bore has a **~45° overhang
ceiling** (45° → 92/100 with no overhang flag; 60° → 9 % overhang; 90° → 11 %),
and `designs/nuggs/NOTES.md` records the same 45° cap as an accepted port
property. A single-piece 90° elbow would need support **inside the bore** to
hold its ceiling up — which violates the smooth-bore rule even though 11 %
overhang still passes printcheck (CRITICAL only escalates at ≥ 25 %).

So the elbow is **parametric `bend_angle`, default 45°** — the supportless,
welfare-clean maximum — printed standing on the inlet flange. A 90° corner is
**two 45° elbows coupled** (genderless quarter-turn → any 0–90° turn in any
plane is a pair). `bend_angle` stays tunable to 90° for a one-piece corner,
documented as needing bore support. This is the NUGGS founder's design (#34),
adopted into the #116 contract, not a new decision.

No split-variant was needed: the ~144 × 95 mm footprint fits both target beds
(Bambu P2S 256², H2C 335 × 325), per the owner's bed-size note on #116.

## Key decision — construction (one lofted body, not primitives butted)

First attempt built the outer body as `cylinder` legs + a `rotate_extrude` bend
unioned with a small tangent overlap (`jov`). Two failures, each caught by a
gate, not by eye:

1. **Disconnected pieces (Volumes: 4).** The bend's sweep-centre offset
   (`+bend_radius` in x) was dropped, landing the bend 120 mm off in −x,
   detached from both legs. CGAL still reported `Simple: yes` — the render gate
   (`Volumes`) and the contact-sheet preview caught it, the syntax check would
   not have.
2. **Non-manifold edges (printcheck CRITICAL, score 43, not watertight).** Where
   a straight `cylinder` leg meets the `rotate_extrude` bend they are *coaxial
   and tangent* at the junction, so the overlap produced coincident-but-
   mismatched faces on export — the classic trap this repo's libraries warn
   about. The slice still succeeded (slicers repair it), so only printcheck's
   watertightness check flagged it.

Fix: build the **whole tube — inlet leg, bend, outlet leg — as one lofted solid**
(`elbow_solid`), a chain of `hull()` segments that *share* their boundary discs
(the top disc of one segment IS the bottom disc of the next, same primitive,
same tessellation). Straights need no subdivision (one hull spans them); only
the arc is stepped, by `arc_step` (2°). The bore is lofted the same way and
subtracted once, so the interior is smooth end to end with no junction ledge.
Result: `Simple: yes`, `Volumes: 2`, watertight, one body, **76/100**.

The loft's thin cross-section discs were bumped from `h = 0.01` to `h = 0.05` to
drop zero-area export triangles from 13 → 3 (a mesh-cleanliness WARNING, not a
gate failure).

## Print orientation

Inlet flange down, bore vertical at the inlet, the three inlet-port sector tips
as the bed contact (same as the NUGGS straight). printcheck: "current
orientation is as good as any axis-aligned alternative." Small bed-contact
patch (~530 mm²) → print with a brim. Bend-belly overhang tops out at the
designed 45° (2 % of surface, WARNING only).

## Verification (measured off the exported production mesh, $fa=2/$fs=0.5)

- Worst-point **bore ø = 79.99 mm** along the whole path (floor 70, target 80) —
  the bore never pinches through the bend. Measured as the minimum distance from
  any mesh vertex to the centerline polyline.
- **Tube OD = 85.10 mm** (target 84.8; 0.3 mm faceting, sub-nozzle).
- **Coupling-ring OD = 96.80 mm** — exactly `nuggs_r_out(cfg) × 2`, i.e. the
  standard, so it mates with every NUGGS module by construction.
- `gate.sh --slice nuggs-elbow` exits 0 (watertight, no CRITICAL, PrusaSlicer
  test-slice ~148 g).

## Coupling fit — not re-tuned here

The only tuned fit is the NUGGS bayonet, owned by `lib/nuggs-coupling.scad` and
gated by its `nuggs-coupling-mates.conf`. The elbow introduces no new mating
clearance (both ports are `nuggs_port(cfg)` at the standard defaults), so it
ships **no new coupon** — the lib's mate-check already proves the fit. Tune
`port_tol` on the `nuggs` coupon if your printer needs it; it is the same knob.

## Open questions from the brief — resolved

- Print orientation / bed size → single-part, inlet-flange-down, fits both beds.
- Bend-radius floor → 120 mm default; the bore stays a full circle at any radius
  above `ro` (asserted), so the floor is set by overhang, not radius.
- Second-end clocking → independent. The quarter-turn joint retains at any
  clocking, so a pair of elbows can aim the second outlet anywhere.
