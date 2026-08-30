# nuggs-turnaround-tee — NOTES

## Goal

The **three-port turnaround** for the N.U.G.G.S. run system: everything the
two-port `nuggs-turnaround` node is, plus a **third port on the chamber
crown**, anti-parallel to the two bed ports, so a run can pass **straight
through** the turnaround instead of only switching back. Issue #435 — the
2-vs-3-ports decision deferred from #394; the owner settled it on-thread:
build it **as a derivative** of `nuggs-turnaround`, same rule set, same port
revision, deliverable `designs/nuggs-turnaround-tee/`.

With the tee, a run entering port A can: exit B (the switchback the parent
gives), or **exit C straight over the crown** (the through-route this design
adds). Any port pairs with any other — the coupling is the standard
`lib/nuggs-coupling.scad` port, one `cfg`, unchanged revision (N10).

## Given / assumed measurements

| Quantity | Value | Status |
|---|---|---|
| Bore / body diameter | Ø80 mm (`bore_d`) | given — the NUGGS system dimension, inherited |
| Port spacing (A–B axes) | 97 mm (`port_gap`) | given — inherited from the parent |
| Clear internal width (N2 break test) | 200 mm (`2*chamber_ay`) | given — inherited; the tee must not shrink it |
| Max body length between breaks | 360 mm (`body_len_mm`) | given — charter constant, inherited |
| Max incline (N4) | 15° (`max_incline_deg`) | given — charter constant, inherited |
| Print envelope | 256³ mm build volume; ≤199 mm Z | assumed — the gate's bare-default test-slice ceiling, same as the parent's `printcheck.args` posture |
| Chamber z semi-axis | 84 mm (`tee_az`) | **derived** — parent's 90 lowered 6 mm so port C's sectors top out at 197 mm (see decisions) |
| Port C axis position | x = +3 mm, y = 0 (`port_c_x`) | **derived** from N4 — see decisions |

## Key decisions

1. **Derivative, not a copy.** `include <../nuggs-turnaround/nuggs-turnaround.scad>`
   then redefine the modules that bake in the changed numbers. New `tee_*`
   names throughout — **no parent variable is reassigned** (OpenSCAD would
   WARN "overwritten" on every render, and `check.sh`'s echo-check surfaces
   it). Redefined: `chamber()`, `neck()`, `vents()`, `chamber_cavity()` (the
   repaired cap), `nuggs_turnaround()`, `animal_path_sweep()`. Inherited
   verbatim: the `cfg`, `bore_lead()`, `turnaround_coupon()`, the cutaway and
   fitcheck parts, the whole `part` dispatch (module instantiations bind
   after the merged scope is read, which is exactly why the parent's own
   coupon wrapper works).
   - **One OpenSCAD landmine found and documented in the .scad:** the
     parent's top-level `route_centres = concat(...)` assignment evaluates
     *eagerly, at include position* — so a redefinition of `cross_centre()`
     runs there with `tee_zc` not yet assigned and silently writes `undef`
     stations into the parent's list (WARNs, and would be a wrong-geometry
     trap if anything still read that list). The tee's crossing function is
     therefore named `tee_cross_centre()`, and the parent's dead list keeps
     the parent's definition. Top-level **assignments** evaluate in file
     order; only **module instantiations** get late binding.
2. **What moves and what doesn't.** The chamber's x/y semi-axes (47/100) and
   everything they carry — the N2 clear width, the dish, the A↔B route, the
   vents — are untouched. Only `chamber_az` 90→84 and `chamber_zc` 92.4→86.4
   (keeping `zc = az + wall` exactly, the parent's pole-flush belly rule), so
   the crown drops 6 mm: port C's ring + sectors on top must fit under the
   199 mm the gate's bare-default test-slice can cut. Total height
   `port_c_face + 2*port_proj` = **197 mm**.
3. **Port C is anti-parallel (straight up in the print pose), at (x=+3, y=0).**
   Two independent reasons:
   - *Clocking:* a port angled off vertical puts its own bore ceiling
     beyond 45° somewhere around the mouth — unprintable without supports
     (issue #34's measured ceiling). Anti-parallel keeps every port-mouth
     overhang at the same ≤45° class the parent already ships.
   - *Position:* the A→C route hands off from the dish floor (the ellipsoid's
     +x flank) onto port C's bore floor, the plane x = `port_c_x + ri`. That
     crossing's walking grade is the dish's own slope there. On-axis
     (x=0): crossing z*=130.5, grade **19.0° — over N4's 15°**. At x=+3:
     crossing z*=120.31, grade **13.87°, inside N4 with margin**, and the
     handoff is a pure widening (dish floor falls onto flat bore floor, no
     lip either way — N6/N11 clean). Asserted in the .scad.
4. **The crown cap is REPAIRED, not inherited — the parent has a roof slot.**
   The parent closes the chamber with a barrel vault whose ridge line runs
   along y at constant height; the ridge outruns the outer dome's y-falloff
   and the cavity pokes **through** the roof for |y| > 27.6 mm (parent
   numbers): a ridge-centred slot widening from a knife pierce to ~21 mm at
   |y| = 50, then the vault's **whole cross-section** outside the dome from
   |y| = 55 out to the vault edge (a gash up to ~60 mm wide, its ridge tip
   standing 37.3 mm proud of the dome; full derivation from the parent's
   committed constants in issue #499). The parent's two crown asserts sample only the y = 0 meridian, the one
   place the shell is thickest (3.41 mm) and the slot is absent, and its
   cutaway-cross camera sections exactly there, so nothing fires and no
   frozen shot shows it. The tee *cannot* inherit that cap: port
   C's collar stands on the crown spanning y = 0±48 and the slot band starts
   at |y|=32.8 in tee numbers — the port would open into open air.
   The repair: keep the vault's two ≥45° x-planes (the gable) and **add the
   hip it always needed** — two planes descending at 46° in |y|, placed to
   pass 1.5 mm under the inner ellipsoid where that surface crosses the ridge
   height (y_c = 22.5 mm), so the ellipsoid's shallow polar band (slope <45°)
   never governs the roof. Cavity ceiling = **min(ellipsoid, x-gable, y-hip)**
   pointwise, built as one `intersection()` of three solids — no truncation
   plane, no footprint prism; the ellipsoid bounds its own footprint. Every
   governing surface ≥45° ⇒ printable without supports; min roof shell
   **2.72 mm** (wall = 2.4). The follow-up issue on the parent is **#499**
   (it is active, not archived — not fixed in this PR).
   - The tee's asserts include the guards the parent lacked: **sampled**
     min-roof-shell over a 120×120 grid (not just y=0), and a sampled
     "wherever the ellipsoid governs above the equator, its slope ≥ 45°".
5. **Port C's junction discipline (from the y-splitter's notes).** Port C's
   neck shell is **unioned**, not hulled into the dome — a hull would flare a
   skirt where the tube leaves the dome; the union keeps the dome-and-tube
   silhouette and makes the junction a clean **transverse** pierce (the class
   CGAL tolerates and Manifold rejects only when surfaces *coincide*). Both
   base discs (shell at `port_c_base`, bore cut likewise) are buried strictly
   inside their ellipsoids — asserted by sampling the full rim (normalized
   ellipsoid radius ≤ 0.97, i.e. ~1.5 mm of real burial) so no cap crescent
   survives as an interior ledge and no coincident-surface seam is handed to
   the slicer. The port geometry itself is `nuggs_port(cfg)` under
   `rotate([180,0,0])` — a **proper** rotation (det=+1), a rigid reorientation
   of the standard port, never a mirror: any standard mate still fits.
6. **Fitchecks extended to three routes.** `ci.fitchecks` keeps the parent's
   pair, with the sweep rebuilt: A→B switchback (parent's, restated on
   `tee_zc`), then continuously (no jumps — a swept proof can't teleport)
   back up B, re-cross the bowl, **climb the port-C meridian** (floor-normal
   31 mm offsets at every station, the parent's degenerate-tangency
   discipline), and out port C past its face. `path-clear` must render zero
   facets (envelope never leaves the part's material); `path-clear-ctrl`
   (+6 mm toward the floor) must interfere — the negative control proving the
   check can fail. The part names are the parent's, and the tee's entry `.scad`
   **restates the two dispatch branches** (with a comment saying why): the
   fitcheck gate greps the *entry* file for the `part == "<name>"` selector — a
   derivative inherits the parent's chain, not its text, so without the
   restatement the gate can't tell `path-clear` from a typo. The restatement
   calls the parent's `fit_path_clear()`/`fit_path_ctrl()` (one source of truth
   for the boolean, including the +6 mm shift), which late-bind to the tee's
   rebuilt sweep; each branch therefore fires twice (parent chain + restated
   chain) and unions with itself, flipping neither verdict.
   **The check earned its keep on the first green-bound run:** the climb's
   floor-normal had a dropped `/tee_az` in its z-term, shipping a "unit"
   vector ~14× too long — every analytic assert (grades, handoff, roof) stayed
   green because they re-derive the formulas, but the *built* station list put
   the 31 mm standoff ~450 mm below the part and the climb capsule speared
   straight through the web: `path-clear` failed with 1796 facets of
   interference. Exactly issue #37's lesson (a formula equals itself while the
   geometry drifts), caught only by measuring the mesh. The fix is the one
   term; the guard is a new artifact-level `assert` on the built
   `tee_route_centres` (every station inside the part's z span), so a
   non-unit standoff can never again reach the render silently.
7. **Print pose = the parent's pose, plus C's ring on top.** Ports A and B
   stand on their sector tips (still the *only* bed contact — the belly dome
   closes pole-flush at the port plane); the chamber rises; port C's collar
   and sector ring print uppermost, mouth up, no supports anywhere. Brim
   advice is the parent's: the first ~50 layers print as twelve separate
   island feet that merge at the port plane — **do not brim across them**.

## Print settings

- **Orientation:** as-modelled — A/B sector tips on the bed, port C's mouth
  up. No supports (every overhang ≤45° by construction; the crown cap and
  port mouths are the designed-in supportless surfaces).
- **Material:** PLA if it lives at room temperature; PETG for a node that
  will be scrubbed or run warm (matches the README and the parent's page).
- **Layer height:** 0.2 mm; **perimeters:** 3 (wall = 2.4 mm at 0.4 mm nozzle);
  **infill:** 15–20% gyroid (the shell is the structure; the web is solid by
  geometry).
- **Brim:** none (see decision 7). Bed adhesion via the twelve tip feet.
- **Fits:** the NUGGS coupling — tune `port_tol` on the coupon, not on this
  part.

## Print this first

`nuggs-turnaround-tee-coupon.scad` — the library's own `nuggs_neck` stub
(inherited from the parent verbatim; port C is the same port rigidly rotated,
so one coupon covers all three mouths). Ten minutes, ~1 g.

1. Print the coupon as-is (`port_tol = 0.30`).
2. Mate it with a known-good module's port. **Too loose** (drops under its own
   weight, rattles): decrease `port_tol` by 0.05 and re-print. **Too tight**
   (won't seat, or needs force that flexes the sectors): increase by 0.05.
3. Also check the **quarter-turn feel**: it should index positively at the
   closed clocking without backdriving. Gummy indexing = first-layer
   elephant-foot on the sectors — calibrate first-layer height, don't open the
   tolerance for it.
4. The value you land on is the `port_tol` to use for every NUGGS module on
   that printer — record it in the design's `NOTES.md` or the repo
   `printer.conf` print-feedback profile if that loop is enabled.

The chamber/route geometry has **no** tunable fits — clearances there are
charter rules (bore Ø80, N2 width), not adjustments.

## Field test log

*(appended per `templates/FIELD-TEST.md` when a real print result exists —
keep this section last)*
