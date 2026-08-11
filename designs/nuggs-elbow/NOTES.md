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
`bend_radius` 120 mm (~1.5× bore). The brief's assumed ~30 mm straight lead-in
per end was dropped to a `port_stub` = 16 mm (just the straight shell each port
fuses to, plus a short grip) — see the construction note and the #116 amendment
comment; it is non-blocking and non-material (the deliverable is unchanged).

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

## Key decision — construction (one BOSL2 path_sweep, the Manifold saga)

The tube (and, subtracted, the bore) is **one BOSL2 `path_sweep`** of the round
section along the centerline path (inlet stub → arc → outlet stub). It is a
single stitched polyhedron — no booleans inside the sweep, no coincident faces —
capped perpendicular to the tangent at each end, which is exactly the coupling-
face plane. The two ports fuse onto the straight `port_stub` ends exactly as
they fuse to `designs/nuggs`'s straight `tube()`.

Getting here took four constructions, and the important lesson is that **only
CI's Manifold backend told the truth** — every failed build passed the local
CGAL render:

1. **hull-of-discs loft → 19 shells (Manifold), 1 body (CGAL).** Segments that
   only *share a face* stay separate volumes for Manifold; CGAL's exact kernel
   merges them. CGAL said watertight/76; Manifold said 51/100, CRITICAL,
   19 disconnected shells. (This is the exact divergence `nuggs-yard`'s curve
   construction documents.)
2. **`cylinder` stub butted onto a `rotate_extrude` bend → non-manifold edge at
   the tangent.** A straight primitive tangent to a curve never quite coincides
   with it; the near-coincident band exports non-manifold. 1 edge with the port
   fused straight to the curve, *more* with an explicit stub.
3. **overlapping oriented cylinders → non-manifold on export.** The many
   cylinder-intersection curves tessellate into edges shared by >2 triangles.
4. **BOSL2 `path_sweep` → clean.** One polyhedron, no junction to go wrong.
   watertight, one body, **76/100** under CGAL — and, by construction (a single
   stitched mesh + the same port-on-straight-stub union nuggs's straight uses),
   expected clean under Manifold. The `normal = [0,1,0]` argument locks the
   section frame to the bend plane so the sweep does not twist.

Takeaway for the next curved design here: **verify on the Manifold backend, not
just CGAL** (`OPENSCAD_BIN=openscad-nightly OPENSCAD_ARGS=--backend=manifold`, or
push and read CI), and reach for `path_sweep` before hand-rolled unions.

## Print orientation

Inlet flange down, bore vertical at the inlet, the three inlet-port sector tips
as the bed contact (same as the NUGGS straight). printcheck: "current
orientation is as good as any axis-aligned alternative." Small bed-contact
patch (~530 mm²) → print with a brim. Bend-belly overhang tops out at the
designed 45° (2 % of surface, WARNING only).

## Verification (measured off the exported mesh)

- Worst-point **bore ø = 79.83 mm** along the whole path (floor 70, target 80) —
  the bore never pinches through the bend. Measured as the minimum distance from
  any mesh vertex to the centerline polyline (rises toward 80 at production
  `tube_fn`).
- **Tube OD = 85.10 mm** (target 84.8; sub-nozzle faceting).
- **Coupling-ring OD = 96.80 mm** — exactly `nuggs_r_out(cfg) × 2`, i.e. the
  standard, so it mates with every NUGGS module by construction.
- `gate.sh --slice nuggs-elbow` exits 0 (watertight, no CRITICAL, PrusaSlicer
  test-slice ~126 g). Envelope 134 × 95 × 161 mm — fits both target beds.

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
