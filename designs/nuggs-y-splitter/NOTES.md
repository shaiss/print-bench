# nuggs-y-splitter — engineering log

Design brief: issue #284 (`design-brief`). This is the resume-cold record;
README.md is the product page.

## Goal

A first-party NUGGS junction module: branch an 80 mm-bore NUGGS run into two
paths — one inlet port, two symmetric outlets at a 60° included angle — with
all three faces carrying the standard genderless quarter-turn bayonet port
(`nuggs_port()` from `lib/nuggs-coupling.scad`). Branching was the one topology
the ecosystem could not do; every other module is two-port single-path. A
consumer of the port standard, exactly like `designs/nuggs` and
`designs/nuggs-elbow`: one `cfg` built from `nuggs_cfg()` defaults, handed to
every port call, never a redefined coupling number.

## Given measurements (all from the NUGGS standard / brief)

Inherited from `nuggs_cfg()` defaults: bore 80.0, wall 2.4, lug_r 6,
port_proj 10, collar_t 3, n_lug 3, lug_deg 40, rib_h 1.0, rib_w 2.4,
rib_deg 12, twist_deg 14, bite 0.8, port_tol 0.30 (untouched — issue #56's
tuning stays where it is), min_bore 70 (DTSchB welfare floor), nozzle 0.4
(mm/deg). Derived: tube OD 84.8, coupling-ring OD 96.8.

**Assumed (brief, stated):** branch half-angle 30° with a junction overhang
ceiling ≤45° and **zero support inside any bore**; inlet-to-fork ~80 mm.

## Key decision 1 — ports, not necks (the 17:09Z amendment)

Announced on the issue before geometry: the arms are built from
`nuggs_port(cfg)` at the standard defaults fused to straight full-round shells,
with **one continuous cavity subtracted through all three arms** — not
`nuggs_neck()`, whose full-round shell shares a cylindrical surface with a
neighbouring arm's shell where two arms run side by side. The
shared-cylindrical-surface class is exactly what CGAL tolerates and CI's
Manifold backend rejects (nuggs-yard defect 5); port + straight shell keeps
every intersection transverse. No gate changed.

## Key decision 2 — the bed, not the brief, sets the inlet length

The brief assumed inlet-to-fork ~80 mm. Rendered at 80, the part's print-pose
envelope is 94.9 × 192.9 × **211.0 mm** — and PrusaSlicer's stock build height
is **250 mm hard** (measured by probe: 200 mm passes, 201 mm fails with
"exceeds the maximum build volume height"; the gate's test-slice uses the
stock profile, so this is the wall the gate enforces). The height budget is
`inlet_len + port_proj + (branch_len + port_proj)·cos(30°)`, and the branch
length is already pinned from below by the **assembly clearance** (see
decision 3) — so the inlet is the only free length, and 60 mm is what fits
with margin. `inlet_len = 60` + a `YSPLIT BED FIT` assert holding the pose
height ≤200 mm. The brief's "~80 mm" named the atom this module is comparable
to (the straight module's body); the assert keeps the miter clear of the port
zone, and anything past ~64 mm puts the sector tips over the slicer wall.
Recorded as a deviation, not silently taken.

## Key decision 3 — branch length is derived from assembly, not looks

`branch_len = max(port_stub + 5, 2·r_out + 5)` = 101.8 mm. Sliding a mating
module onto outlet A sweeps its sector tips (radius `r_out` about A's axis)
down past A's face; outlet B's own ring must stay out of that sweep. The
closest approach works out to the two face centres' separation minus the two
ring radii, so the arms must be ≥ 2·r_out apart at the faces. Asserted
(`YSPLIT ASSEMBLY`); measured real clearance ~16 mm at 30°.

## Construction

Union(shells) − union(cavities), never per-arm — the ordering that stops an
interior wall standing across a fork (nuggs-yard's wye lesson). Three
mitered straight arms meet at the fork centre O; their union IS the miter.
The cavity is **one union** of three ri cylinders **plus a junction blend
sphere** at O (R = ro − 3·nozzle = 41.2), subtracted afterwards.

The sphere is what makes the bore **ledge-free rather than merely open**:
three flat cylinder caps meeting near each other's walls leave sub-mm exposed
crescents (measured 0.45 mm at a 12 mm overrun — a lip on the passage wall),
and a sphere of radius ro − 3·nozzle swallows every cap disc whole (farthest
cap point √(ri² + overrun²) = 40.45 mm against the sphere's 41.2), so **no
cap face exists in the finished geometry**. Asserted (`YSPLIT CAP BURIAL`).
The passage only ever widens; a widening wall cannot catch a paw.

Why a miter and not swept arcs: at 30° half-angle the two branch tubes
(OD 84.8) stay fused until 84.8 mm from O whatever the path — the fork is
intrinsically a long wedge — so arcs buy bulk, not welfare. A straight miter
also puts every junction surface at 30° from vertical in the print pose,
under the ~45° supportless ceiling issue #34 measured and the elbow documents
as its own limit.

No cap lands flush on a free face or on another cavity's wall: port faces are
cut square on the coupling planes, every interior cap is buried in the sphere,
every intersection transverse — the coincident-surface class CI's Manifold
backend rejects is absent by construction.

## Print orientation

Inlet port down, exactly like the NUGGS straight and elbow: the inlet's three
coupling-sector tips are the bed contact, the bore vertical at the inlet, both
branches rising at 30°. printcheck: "current orientation is as good as any
axis-aligned alternative." Small bed-contact patch (~527 mm², same as the
elbow) → print with a brim. The 3 % beyond-45° surface printcheck flags is
entirely **exterior** — bed-side port faces and branch sector tips (measured
off the mesh: 0.000 mm² of cavity surface lies beyond 45°); nothing inside any
bore needs support.

## Measured off the export (gate evidence, not the parameters)

- Bore diameter **79.83 mm** (2 × min vertex radius over the mesh; brief 80.0,
  floor 70). Sub-nozzle faceting below the nominal, same class as the elbow's
  85.10 tube OD.
- Tube OD **84.80 mm**, coupling-ring OD **96.80 mm** — the standard, so it
  mates with every NUGGS module by construction.
- Fork half-angles **29.98° / 30.00°** measured from the mouth-rim centroids.
- Print-pose envelope **94.9 × 192.9 × 191.0 mm**; PrusaSlicer test-slice
  clean, ~200 g.
- `gate.sh --slice nuggs-y-splitter` exits 0 (watertight, no CRITICAL, both
  parts test-sliced).

## Print this first

The bayonet fit is owned by `lib/nuggs-coupling.scad` and gated by its
`mates.conf` — **this design ships the coupon anyway** (the adopted contract
says so), because a Y-splitter is the part you least want to discover a
shrunken bore on: it is the biggest single print in the family.

Print `nuggs-y-splitter-coupon.scad` (two production port stubs side by side,
straight from the production `cfg` — nothing copied) and:

1. Mate the two stubs to each other, quarter-turn. They should lock with a
   firm click and no rattle.
2. Caliper the bore: **under 79.0 mm means your printer is shrinking** —
   raise `port_tol` in ±0.05 steps on the coupon until the pair mates, then
   set the same value in the splitter before committing to the full print.
3. Only then print the splitter (with a brim — small bed patch).

## Open items

None blocking. `inlet_len = 60` deviates from the brief's assumed ~80 mm for
the measured bed reason above; a bigger-bed owner can raise it (the assert
will stop anything over ~64 mm until they also relax the height budget).
