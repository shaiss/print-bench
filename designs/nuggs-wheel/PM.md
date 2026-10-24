# nuggs-wheel — product charter

## The product, in one paragraph

**nuggs-wheel** is the NUGGS exercise module: a Syrian-scale segmented rim
wheel on a free-standing stand that quarter-turns into a standard 80 mm
genderless port so it stays put in a habitat without hardware. The customer
is the owner; the user is the animal. The one thing it must do well is let
an adult Syrian run quietly on a closed-back wheel whose every printable
part clears a ~180 mm bound — and whose stand still anchors to the system.

Enforced by `/pm nuggs-wheel`. Inherits every NUGGS non-negotiable from
`designs/nuggs/PM.md`. Engineering log: `NOTES.md`. Brief: #834.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Every printable part ≤ part bound | **180 mm** | #673 / test-slice ceiling | Gate ceiling changes |
| N2 | Running surface Ø is a parameter; default is the Syrian floor | **280 mm** default | welfare practice (assumed) | Owner measures their animal |
| N3 | Back fully closed — no path behind the wheel | 0 openings in the back disc | wheel safety | Never |
| N4 | Rim joint flush; no butt gap; step ≤ 0.25 mm | **≤ 0.25 mm** | toe-pinch welfare | Measured injury threshold differs |
| N5 | Stand anchors via stock `nuggs_cfg()` port AND stands free | bore 80 / tol 0.30 / proj 10 / 3 lugs | N10 of the system charter | Port revision bumps |
| N6 | Quiet running — bearing clearance is a product knob | tune on coupon | bedroom-cage reality | Never waive for “good enough” |
| N7 | No slicer supports | 0 | repo FDM default | Never for v1 |

## Out of scope

**Deferred**

- Monolithic dwarf-hamster ≤ 200 mm variant (named follow-up, not v1).
- Print-in-place captive axle as the shipped stand (coupon may trial).

**Never**

- A second interlock standard (system N10).
- An open back or ladder-rung rim.
- Shipping without a port coupon.

## v1 — definition of done

- [ ] Identical rim segments assemble into a closed-back Ø280 × 90 wheel
- [ ] Stand free-stands and mates a stock NUGGS port
- [ ] Coupon tunes port, joint, and axle fits
- [ ] `ci.plate` multi-object 3MF is the deliverable
- [ ] Gate G1–G4 green; product page honest about unmeasured `port_tol`

## Product page & shots (art direction)

**Page promise.** A real exercise wheel for NUGGS — segmented because size
demands it, anchored because habitats move.

**Mechanism honesty.** Contact sheet shows as-printed parts (segment / stand);
assembled hero is labeled as assembly preview. Plate is the deliverable.

**Shot list — tier 1**

1. `product-hero` — assembled wheel on stand, three-quarter, open front readable
2. Contact sheet — default printable / assembled per cameras.conf

**Lifestyle / motion.** None for v1.

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-23 | **F1** — back-pie lightening is blind pockets (`back_pocket_d = 1.0`), not through-slots | N3: 0 openings in the back disc. 24× Ø14 through-holes (3 per segment) were a charter violation; wash ergonomics prefer closed, so pockets keep mass relief without a path behind the wheel |
| 2026-10-23 | **Back-pie shingle** — half-thickness circumferential lap (`back_clear_ang=0.25`, `back_z_clear=0.20`; lap = tread `joint_lap` angle); `back-closed` fitcheck gates the assembled seam | N3 reopen: a prior `back_half` short of `seg_ang/2` left ~4.27° sunburst through-slots between pies; blind pockets alone do not close inter-segment gaps. Covered seam keeps segments individually printable |
| 2026-10-23 | **F2** — `wheel_floor_clear = 15` (was 4); lip-to-footplate assert ≥ 5 mm | Drum lip OD is `r_outer + lip_h` (145.4 at defaults), not `r_run`. Clearance 4 buried the lip 5 mm under the footplate top. 15 → `axle_z = 155`, lip underside ~9.6, ~6 mm above the 3.6 mm footplate; use height ~164 mm; as-printed stand Z stays 178 (stand_depth + port). Do not lower `wheel_d` (N2) or split the stand |
| 2026-10-23 | **Jane lip** — `joint_lip = 1.0`; male tongue set back by `joint_lip + joint_step`; felt step stays `joint_step = 0.20` ≤ 0.25 | Decouple printable lip land from paw-felt step (N4). A 0.20 mm lip was under half an extrusion and either fattened or dropped in the slicer, turning the shingle into a butt seam |
