# nuggs-yard — engineering log

> **Status banner, 2026-08-03 — the joint is superseded.** N.U.G.G.S. is
> now a system with one genderless interlock standard: `nuggs`'s
> quarter-turn port. This design's lap-skirt joint (`joint_lap`, `joint_h`,
> `joint_t`, `joint_tol`, `joint_skirt()`) is gendered and keyed to a flat
> two-sidewall section, so it can only ever join troughs to troughs — it
> does **not** mate with a `nuggs` module. A rebuild onto the shared port,
> as open modules with a **round arc floor** rather than a flat trough
> floor, is planned as its own PR; nothing below has been rebuilt yet.
> Also re-attributed on the same date: the "covered length ≤ 2 × body
> length" limit inherited below is the **Deutscher Tierschutzbund**
> position paper's, **not** TVT Merkblatt 62's, and it is now measured
> **per run** between breaks rather than as a system total. See
> [`designs/nuggs/PM.md`](../nuggs/PM.md) N2 and
> [`docs/nuggs-research.md`](../../docs/nuggs-research.md) §11. This file
> is preserved as recorded history and is not rewritten here.

Product page: `README.md`. Design request and the measurements behind it:
[issue #73](https://github.com/shaiss/print-bench/issues/73). Sibling design
(the enclosed wall-crossing tunnel, and the source of the welfare limits):
[`designs/nuggs`](../nuggs/).

## Goal

An open-top run for an adult Syrian hamster's **playpen** — free-roam time
outside the cage. The ask was "loops and twists, turns, branches, all the
stuff to keep him busy". It is a floor-standing kit of modules the owner
lays out themselves, not a fixed object. Despite the `nuggs-` name, it is a
sibling of the NUGGS tunnel system, not a module in it — its lap-skirt joint
does not mate with the NUGGS port.

This is *not* a change to `nuggs` and not a derivative of it: no shared
geometry, no include, no `derives.conf`. `nuggs` is an enclosed bore that
crosses an enclosure wall; this is an open trough that sits on a pen floor.
They share an animal and a research dossier, nothing else.

## Given / assumed measurements

| Value | Status | Note |
|---|---|---|
| Filament budget 250–500 g | **given** (2026-08-03) | Sizes the whole kit; drove the module dimensions more than anything else |
| Animal fits the default 80 mm width | **given** (2026-08-03) | Owner confirmed rather than measured; `body_len_mm` stays at Merck's 180 mm upper figure |
| Bore floor 70 mm for covered segments | inherited from `nuggs` N1 | DTSchB pouch-full entrance minimum |
| Covered length ≤ 2 × body length | inherited from `nuggs` N2 | ⚠️ recorded here as TVT Merkblatt 62; re-attributed to the DTSchB position paper and re-scoped per run on 2026-08-03 — see the banner at the top |
| Max incline 15°, no vertical runs | inherited from `nuggs` N4 | v1 is entirely flat, so this is satisfied by construction |
| Playpen dimensions | **still unknown** | Not blocking: the kit is modular and the budget bounds the layout. The preview circuit is 409 × 409 mm |
| PLA vs PETG | **assumed PLA** | The gate slices at 1.24 g/cm³, so every gram below is PLA. PETG is ~2.4% heavier and wants `joint_tol` re-tuned |
| Pen floor surface | unknown | Y8 (stability) is currently met by a wide flat footprint, not by feet |

## Why open-topped — the load-bearing decision

`nuggs`'s charter forbids exactly what was asked for here (loops, branches,
long runs). Rather than argue with it, each limit was tested against the
failure mode it exists to prevent. **Four of seven dissolve when the roof
comes off, three do not**, and the three that survive are the three about
the animal's body rather than about the tube:

| Limit | Survives? | Why |
|---|---|---|
| N2 enclosed length ≤ 360 mm | No, for open channel | The limit exists because an animal cannot reverse in a long tube and cannot be reached. He steps out anywhere; so does a hand. **Applies in full to any covered segment** (Y2) |
| N3 no dead air / dead ends | No | Nothing encloses air. A closed circuit has no terminus at all |
| N5 opens by hand in one action | No | There is nothing to open |
| N1 70 mm bore floor | **Yes** | Becomes Y1 wherever a roof exists |
| N4 no vertical, ≤ 15° incline | **Yes** | Y3. Syrians climb well but have almost no depth perception, so they fall |
| N6 no protrusions / chew edges | **Yes** | Y5 |
| N7 hand wash ≤ 50 °C | **Yes** | Y7 |

## Key decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-08-03 | Open-top channel, not enclosed tube | Dissolves N2/N3/N5, which is the only way the requested loops and branches can be welfare-compliant at all |
| 2026-08-03 | "Loop" means a **closed circuit**, never a helix or vertical loop | A circuit is the only topology with zero dead ends, so Y6 holds by construction. A vertical loop is refused under Y3 |
| 2026-08-03 | **Flat floor, not a round bore** | A round tube floor makes the animal walk the bottom of an arc. Flat is better footing, and it is also what lets every module print flat-on-bed with no support |
| 2026-08-03 | `side_h = 47`, and it is set by the **refuge**, not the open run | The open channel would be happy at 30 mm and 16% cheaper. 47 is the minimum that lets a gable-roofed covered segment clear the 70 mm bore floor. The open run pays for the refuge's legality |
| 2026-08-03 | **Gable roof, not an arch** on the refuge | Both 45° slopes are self-supporting; an arch's crown is a horizontal overhang |
| 2026-08-03 | Horizontal **90° curves are one part**, not two 45s | #34's "45° is the printable ceiling" applies to a bend that tilts a bore out of the build direction. A channel turning in plan never leaves the print plane — measured 100/100 at 90°. This halved the curve count |
| 2026-08-03 | Lap-skirt joint, gendered (skirt end + bare end) | Cheap, prints flat, nothing enters the walking surface, and because the skirts never pass under the neighbour's floor a module **lifts straight out** of an assembled run for cleaning. Genderless was `nuggs`'s big win but needs a bayonet, which an open cross-section cannot carry. Backlogged as B3 |
| 2026-08-03 | Wye crotch fixed by **moving the junction**, not by a boolean patch | Two attempted booleans (a plan-footprint opening, then a cavity closing) either did nothing or created a worse feather edge (printcheck 0.00 mm walls). The wedge thickness is analytic; putting the junction back so it has room to thicken is the actual cure, and `wye_end_wedge` asserts it |
| 2026-08-03 | Cavities overrun the shell at every free face, not just the top | A flush port face is a coplanar face pair. CGAL tolerates it, Manifold does not, and the asymmetry only shows on a rotated (non-axis-aligned) end. Overrunning everywhere is cheaper than reasoning about which faces are axis-aligned |
| 2026-08-03 | `wye_ang` bounded 15–75° | It sits in a trig denominator: 0° divides by zero, 90° makes `tan` infinite and the crotch assert pass vacuously. Raised in review on PR #76 |
| 2026-08-03 | Bed chamfer rises 1.3× its inset instead of a true 45° | A 45° chamfer sits exactly on printcheck's overhang threshold and books the whole strip as unsupported (335 mm², 8 points) for a surface that prints fine |

## Defects found and fixed this session

Recorded because each one was silent, and five of the six were only caught
by a check rather than by reading the code. Two of them — 4 and 6 — passed
every gate in the repo while being wrong.

1. **Joint skirt was a separate body.** The two halves of the lap were
   reversed, putting the rooted half outside the module. OpenSCAD said
   nothing; it surfaced as `bodies: 2` in printcheck. A skirt that is not
   attached simply falls off the plate.
2. **Skirt merely touched the shell.** After fixing the order, the skirt met
   the sidewall face-to-face — coincident faces stay separate volumes through
   CGAL (`bodies: 3`). Fixed by biting `wall/2` into the sidewall.
3. **Overlapping boxes broke watertightness.** Interpenetrating cubes shared
   a coplanar top face → naked edges, non-watertight, 59/100. Fixed by
   building the skirt as one stepped extruded profile with no internal faces.
4. **The bore-floor assert was wrong, and passed.** ⚠️ The most serious one.
   `covered_bore` was computed as `2*(inner_w/2 + side_h)/(1+√2)` = 70.42 mm
   and the assert passed — but the trough **floor sits at z = wall**, not
   z = 0, so the real figure is `2*(peak_i − wall)/(1+√2)` = 69.09 mm. The
   exported mesh measured **69.09**, i.e. the design was 0.9 mm under the
   welfare floor while reporting itself compliant. Fixed the formula and
   raised `side_h` 45 → 47; the mesh now measures **70.75**.

   This is exactly the failure mode `nuggs` backlog item B1c describes — a
   doc (or an assert) claiming something the model does not do — and it is
   why the measurement below is mandatory rather than optional.

5. **Non-manifold wye under CI's Manifold backend, watertight under CGAL.**
   ⚠️ The one a local gate could not catch. Cavity sweeps ran flush with the
   shell at the port faces, making every port a coplanar face pair. CGAL
   resolved them exactly and reported watertight 100/100; CI renders with
   `openscad-nightly --backend=manifold`, which returned **edges shared by
   more than two triangles — 75/100 NOT PRINTABLE**, 614 triangles against
   CGAL's 540.

   Only the wye failed, and the reason is worth keeping: a flush end is
   *exactly* coincident only when the end face is axis-aligned. The branch is
   rotated 45°, so its vertices land on irrationals and the two faces coincide
   only to within floating point — which a boolean handles worse than exact
   coincidence. All 13 non-manifold clusters sat at the branch's far-end +Y
   corner, computed as `(50 + 0.7071(130−41.6), 0.7071·171.6)` =
   **(112.5, 121.3)**, and every reported z (3–13) fell inside the floor-fillet
   band `wall … wall+fillet_r` = 1.6–13.6 mm.

   Fixed by sweeping cavities `cav_over` past the shell at every free face
   (`cav_over = 0.6`), which removes the coincidence for **every** module
   rather than special-casing the one that failed. Same lesson as the open
   top, which already ran the cavity above the shell for exactly this reason —
   it just was not applied along the sweep axis.

   **This backend gap is now a known hole in local preflight**: `gate.sh`
   here runs stock CGAL 2021.01, CI's render gate runs the Manifold dev
   snapshot, and a mesh can be watertight under one and not the other. The
   nightly could not be installed in this session (the OBS repo is blocked by
   network policy), so the fix was reasoned from the CI log's non-manifold
   coordinates and verified under CGAL only — CI is the real check. Backlogged
   as B7.

6. **The curve's joint lap was inverted, and it filled the tolerance gap.**
   ⚠️ Raised by a review bot on PR #76, which called it a "disconnected
   shell" — it is not; the part is one watertight body at 100/100 either way.
   The real fault is worse. `curve()` placed its skirt with `port_skirt(...,
   90)` while the port frame needs `-90` (the same rotation `chain_curve`
   derives), so the lap ran backwards: the **rooted** half — which carries no
   clearance, because it is meant to fuse into our own wall — landed in the
   band the neighbour's wall must occupy, and the overlapping half sat inside
   the curve where it laps nothing.

   Consequence: a curve would interfere with every module it joins by a full
   wall thickness, and a run containing one could not be assembled. Every
   mesh-level check in the repo passed it — watertight, one body, 100/100,
   correct bounding box. Caught only by **sampling the tolerance band for
   material**, below.

## Checking the joint as a FIT, not as a mesh (required after any joint change)

printcheck judges a mesh. It cannot see that a clearance has been filled in,
which is how defect 6 survived every gate. Sample the joint band directly:

```bash
./scripts/gate.sh nuggs-yard        # exports build/nuggs-yard-curve90.stl
python3 - <<'PY_'
import trimesh, numpy as np
m = trimesh.load('build/nuggs-yard-curve90.stl')
ow, r, tol, jt = 83.2, 80, 0.30, 2.4
outer = r + ow/2
for desc, p, want in [
    ("overlap half laps the neighbour", [outer+tol+jt/2, -6, 10], True),
    ("tolerance gap stays CLEAR",       [outer+tol/2,    -6, 10], False),
    ("rooted half bites into shell",    [outer-0.4,       6, 10], True),
]:
    got = bool(m.contains(np.array([p]))[0])
    print(("ok   " if got == want else "FAIL "), desc, "inside=", got)
PY_
```

The middle case is the one that matters: **material in the tolerance band
means the joint cannot close.** This is the same gap `lib/*-mates.conf`
exists to cover for libraries, and this design has no equivalent — see B8.

## Measuring the bore floor on the mesh (required, not optional)

The assert is arithmetic and can be wrong. Re-measure on the exported STL
after any change to `side_h`, `wall`, `inner_w` or the roof:

```bash
./scripts/gate.sh nuggs-yard          # exports build/nuggs-yard-refuge.stl
python3 - <<'PY_'
import sys, trimesh
from shapely.geometry import Polygon
m = trimesh.load('build/nuggs-yard-refuge.stl')
FLOOR, seen = 70.0, []
for x in (15, 40, 70, 100, 130, 155):
    sec = m.section(plane_origin=[x,0,0], plane_normal=[1,0,0])
    if sec is None:
        sys.exit(f"FAIL x={x}: no cross-section")
    p2, _ = sec.to_planar()
    rings = [r for poly in p2.polygons_full for r in poly.interiors]
    if not rings:
        sys.exit(f"FAIL x={x}: no enclosed void — is this part actually covered?")
    for ring in rings:
        g = Polygon(ring); lo, hi = 0.0, 100.0
        for _ in range(60):
            mid = (lo+hi)/2
            if g.buffer(-mid).is_empty: hi = mid
            else: lo = mid
        seen.append(2*lo)
        print(f"x={x:4} inscribed = {2*lo:.2f} mm")
if min(seen) < FLOOR:
    sys.exit(f"FAIL: minimum {min(seen):.2f} mm is under the {FLOOR} mm floor")
print(f"ok  {len(seen)} stations, min {min(seen):.2f} mm >= {FLOOR}")
PY_
```

It **exits non-zero** on a station below the floor, on a station with no
enclosed void, and on a missing section — a check that only prints is how
defect 4 stayed invisible, so this one has to fail closed to be worth running.

Verified against a negative control, because a check that cannot fail proves
nothing: rendered at the old `side_h = 45` (with `min_covered_bore` lowered to
get past the assert) it reports `FAIL: minimum 69.09 mm is under the 70.0 mm
floor` and exits 1.

Needs `networkx` alongside trimesh/shapely (`pip install networkx`).
**Every slice must read ≥ 70.00 mm.** Current: 70.75 mm at every station.

Only the refuge is measured because it is the only covered part — an open
channel has no enclosed void and the script correctly reports none.

## Guards, and that they fire

All eleven refuse what they exist to refuse (verified 2026-08-03 by rendering
each deliberately-broken value):

| Guard | Broken with | Fires |
|---|---|---|
| Y1 bore floor | `side_h=40` | ✓ |
| Y2 covered length | `refuge_len=400` | ✓ |
| Y4 run width | `inner_w=70` | ✓ |
| wall ≥ 3 perimeters | `wall=1.0` | ✓ |
| wye crotch sliver | `wye_junction=100` | ✓ (reports 3.43 mm, matching the analytic prediction) |
| skirt proud of sidewall | `joint_h=60` | ✓ |
| `wye_ang` out of trig range | `wye_ang=0` / `90` | ✓ |
| refuge/straight length invariant | `refuge_len=140` | ✓ |
| wye/straight length invariant | `wye_len=200` | ✓ |
| `cav_over` zeroed (reinstates the non-manifold wye) | `cav_over=0` | ✓ |
| curve profile crosses the rotation axis | `curve_r=40` | ✓ |

**Test the guards by the error they raise, not by the exit code.** A syntax
error also exits non-zero, so a broken file makes every guard look like it
fires — which happened while adding these (OpenSCAD does not concatenate
adjacent string literals; `str(...)` is required). Assert that the render
of *good* values succeeds first, then match on `ERROR: Assertion`.

## Print this first — the coupon

`nuggs-yard-coupon.scad` prints two 45 mm stubs (40 g, ~3h40). Slide the
skirted end of one onto the bare end of the other.

- **Too loose / rocks:** drop `joint_tol` 0.05 at a time.
- **Will not seat, or the skirt splays:** raise it 0.05 at a time.
- Start at **0.30**. It is one number and it is the only fit in the design.

Do not print a 92 g wye before this stub mates properly.

## Print settings this design assumes

- **Orientation:** every module flat on the bed, exactly as it renders.
  printcheck reports "current orientation is as good as any axis-aligned
  alternative" for all six.
- **Supports:** none, anywhere. The steepest downward surface is the roof
  gable at 45°.
- **Material:** PLA assumed (all masses are PLA at 1.24 g/cm³). PETG is
  welfare-preferable for the same Tg reason as `nuggs` and is ~2.4% heavier.
- **Layer height:** 0.2 mm, 0.4 nozzle, 1.6 mm wall = 4 perimeters.
- **Brim:** not required. Unlike the `nuggs` straight — which stands 160 mm
  tall on a 2.4 mm ring — every module here has a full flat footprint.

## Open items / backlog

| # | Item | Why |
|---|---|---|
| **B1** | **Print the coupon and tune `joint_tol`** | Top. The joint is geometry-only; 0.30 is a guess |
| B2 | Forage / sand stop module | The argument in #73 is that stops, not run length, are the actual enrichment — a widened open pad off the circuit. Meanwhile a ceramic dish beside the run costs 0 g and does the job |
| B3 | Genderless joint | Today's lap is gendered, so all modules must face the same way round a circuit. Workable, documented, but `nuggs`'s "one knob, no orphan ends" argument still stands |
| B4 | Ramp module | Only ≤ 15° (Y3), which buys very little height over a printable length. Needs its own evidence before it exists |
| B5 | Measure the real playpen and publish a fitted layout | Currently the README gives generic BOMs and a footprint |
| B6 | A layout/topology check | Y6 (no dead ends) is a property of the *assembly*, and nothing in the repo can gate it. Same class of gap as `nuggs` B1c |
| B8 | A mates-style fit check for the joint | Defect 6 filled the clearance and passed every mesh gate. `lib/*-mates.conf` covers exactly this for libraries; designs have no equivalent, so the check above is a manual procedure that nothing enforces |
| B7 | Make the backend gap visible locally | A part can be watertight under CGAL and non-manifold under CI's Manifold backend — defect 5 above, and it cost a red CI run. Either preflight should render with the nightly, or the repo should say plainly that a green local gate does not cover it |
