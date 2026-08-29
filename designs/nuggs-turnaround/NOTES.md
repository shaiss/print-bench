# nuggs-turnaround — engineering log

## Goal

The NUGGS **turnaround node** (issue #394, charter backlog B4): the run-resetter.
A module carrying the standard genderless quarter-turn port on **two faces of
one widened chamber**, so an adult Syrian hamster can enter port A, pivot 180°,
and leave port B — doubling a run back on itself. This is the module that makes
layouts larger than one straight legal: charter **N2** caps any continuously
enclosed run at 2 × body length between *breaks*, and a turnaround node of
**clear internal width ≥ body_len_mm that is itself open to ventilated space**
is one of only three breaks. Without this part, no layout bigger than one
straight tube is legal.

## Given / assumed measurements

| Measurement | Value | Source |
|---|---|---|
| Bore / port standard | 80 mm bore, full `nuggs_cfg()` defaults | given — `lib/nuggs-coupling.scad` |
| `port_tol` | 0.30 mm | given — the standard's default, coupon-tuned |
| Body length (Syrian) | 180 mm | **assumed** — Merck upper range, the recorded system assumption (`designs/nuggs/NOTES.md`); the brief's default |
| Body width envelope | 60 mm round (fitcheck r=30) | **assumed** — the N1 pouched-face criterion (a full-cheeked face), over the ~45 mm shoulder |
| Standing gnaw-reach | ceiling itself reachable | measured geometry, see Vents below |
| Max incline | 15° | given — charter N4, non-negotiable |
| Max axis change per port | 0° (ports parallel) | given — issue #34's 45° print ceiling; 0° is the compliant choice, see Topology |
| Printer | 256×256×256 bed class, 250 mm Z | given — family standard (`printcheck.args`) |
| Style | none — functional shell language | given — the brief; den is the closest precedent |

## Key decisions

### Topology — a widened chamber, never a U-bend tube (brief: "oblate … on the
den's pattern, not a box")

The obvious shape for "turn around" is a swept 180° tube. Rejected: its ceiling
at the top of the hairpin is a horizontal overhang (90° to the bed) — issue #34
measured the supportless ceiling for enclosed bores at **45°** (45°→92/100
clean, 60°→9% overhang), and the elbow records 90° as needing support *inside*
the bore, which violates the smooth-bore welfare rule. So the ports stay
**parallel** (0° axis change per port — under the 45° ceiling with maximum
margin) and the turn happens in a **widened chamber**: an oblate ellipsoid on
the den's bulb pattern. A box was rejected the way the brief rejects it: flat
walls make interior ledges at every corner (N6) and corners collect bedding.

### Construction — union(shells) − union(cavities), and why the cavity is a
UNION, not a hull

Shell: convex hull of the two full-round neck shells (r=ro, z 0…95) plus the
outer ellipsoid — the hull fills the 12.2 mm gap between the necks **solid**
(the web; see Bridge below). Cavity: **union** of the two ri bores plus the
inner ellipsoid. A hull for the cavity was considered and rejected explicitly:
the hull of the two bore cylinders bridges the gap *between* them at every
height they span, hollowing the web out under the chamber floor and leaving a
racetrack tunnel between the ports below the dish. The union keeps each bore a
bore until the ellipsoid swallows its cap. Cap burial, the y-splitter's
discipline: each bore's top cap (disc r=40 at z=95) sits strictly inside the
inner ellipsoid — worst rim point at (x=±40, y=48.5) tests (40/47)² +
(48.5/100)² = 0.960 < 1, and the asserted proxy (x-extent at the mouth's y =
41.08 > 40.5) covers it. The passage only ever widens from each mouth.

Each bore overruns below the sector tips (`bore_over = port_proj + 2 = 12`) —
the `nuggs_bore_cut` every `nuggs_port()` caller owes. The port is not
bore-clean; without that cut the part ships watertight, sliceable, scoring
100/100 with plastic standing in the bore (the library header's trap).

### Frame mapping (print ↔ use)

Print pose = model frame: both ports vertical, sectors on the bed. **Use:**
print z (port axes) → travel axis; print **+x → down** (the ellipsoid's +x
flank is the floor — the "dish"); print y → the turn axis. The animal's route:
up bore A, across the dish at the equator height, pivot, back across, down
bore B.

### The floor — dish meets the bore's own arc (N6/N11)

The dish is the inner ellipsoid's +x flank. Sized (a_x=47, a_y=100) so at the
mouth centreline (y=48.5) the dish stands **1.08 mm below** the bore floor
(41.08 vs 40): the route *steps down* onto the dish — a widening, never a lip —
and the union's transition spreads the 1.08 mm over ~19 mm of wall. Route grade
across the dish peaks at the mouth lines: **14.63°**, inside N4's 15° (asserted;
the assert is parametric, so narrowing `chamber_ay` fails the render). At the
bowl bottom the grade eases to 0°. For scale: the bore's own invert arc is
steeper than 15° beyond ±10.3 mm either side of centre in *every* NUGGS tube —
N4 governs the walkable route, which this satisfies.

### The clear width (the N2 number)

Clear internal width = the widest straight line through the cavity = 2·a_y =
**200 mm ≥ 180** body length (asserted against `body_len_mm`). At floor level
the cavity is narrower (±52.5 mm at the mouth lines) — the mouths sit inside
that, and the *turn* happens in the bowl where the width is the full 200.

### Assembly bound

`port_gap = 97 ≥ 2·r_out = 96.8`: a mating module sliding onto either port
sweeps its sector tips at r_out about that axis; the other port's ring stays
out of the sweep (the y-splitter's bound; ~0.2 mm minimum, conservative because
the sweep bands are tilted, not facing — same margin the splitter records).

### The underside — a pole-flush dome, no suspended span

Below the port face plane a mating tube's full-round body (r = ro about each
port axis) must swing in unobstructed, so the chamber's material cannot start
before that plane — the hull's underside between the necks is the belly dome
itself, and `chamber_zc = chamber_az + wall` puts its bottom pole exactly ON
the bed plane (zc = 90 left it 2.4 mm *under*, hanging over air — ~800 mm² of
measured unbridgeable overhang in iteration 3's facet scan). Pole-flush, the
dome prints from the bed up, each layer resting on the one below (~one
extrusion width of per-layer offset near the pole). The residual printcheck
warning — 2% / 3449 mm² — is this surface near the pole plus the bore mouths:
the den-class warning the family ships with (den: 4% @ 76/100; this design:
2% @ 84/100), watched by printcheck + the test-slice gate.

### Vents — sizing and the reach argument (brief's open question, resolved
smallest-first)

The chamber is the family's first enclosed wide volume, so it must be **open to
ventiated space** to be a legal N2 break (and N3 forbids dead volumes).
Derivation, smallest-first on the den's chimney vocabulary: the den vents its
refuge with **six Ø9 mm** teardrop chimneys; this chamber has ~2.4× the den's
air volume but the same occupancy (one animal passing, not nesting), so six
Ø9 was taken as the **ceiling-conservative match, then checked against the
minimum**: cross-section at the equator is a ~94×200 mm oval; six Ø9 teardrops
give ~380 mm² of open area ≈ 0.6% of the floor area — comfortably past the
"large opening within a body length" reading of the welfare floor, and small
enough that no bedding load blocks more than a fraction. Fewer/smaller risks
the dead-volume reading; more/larger spends wall and reach margin for nothing.
Placement: the use-ceiling flank (print −x), at the equator height, spread
±0.6·a_y — every vent strictly on the **inverted** ceiling half (asserted).
On *reach*: "vents out of reach" (the brief's assumption line) is not literally
available in any NUGGS-scale chamber — the ceiling itself is within a standing
animal's reach (94 mm clear height). The realized welfare line is the den's
recorded standard: an **inverted** teardrop hole gives a gnawing incisor no
purchase (you cannot power a bite upward into a ceiling with a held edge), and
a recess is not a protrusion (N6 governs protrusions). Recorded here as the
derivation the brief asked for.

### Fitchecks (ci.fitchecks)

- `path-clear empty` — the 60 mm swept-animal envelope along the full transit
  (bore A → dish → bore B), r=30 spheres swept as **consecutive capsules**
  (a union of 2-sphere hulls — see the traps below). The bore legs ride 9 mm
  off the bore axis, 1 mm off the bore wall; the crossing holds its centres
  31 mm off the dish floor **along the floor normal** — a plain −x offset
  leaves the sphere *tangent* to the tilted floor (the dish grades 14.6° at
  the mouth line, and 31·cos 14.6° = 30.0 = the envelope radius: zero air).
  Verified numerically before any render: the r=30 ball clears floor, walls
  and ceiling at 658 sample stations along the route, worst air **1.00 mm**
  (the bore walls), and the +6 mm control interferes at every station.
  Three construction traps were found and fixed on the way there: one
  `hull()` over every route sphere takes the **convex hull** of a U-shaped
  route — it reaches 61 mm past centre at the bowl, straight through the
  floor; one route point was typed as its standoff constant (31) instead of
  its position, putting the capsule through the mouth shoulder; and the
  tangency above. `gate.sh` measures the export.
- `path-clear-ctrl interferes` — the mandatory negative control: the same
  sweep pushed 6 mm into the floor flank must produce a non-empty mesh,
  proving the empty check can fail.

### Coupon

`nuggs-turnaround-coupon.scad` → the library's own `nuggs_neck(cfg, z_top+8)`
stub. The fit being tuned is the *coupling's*, owned by the standard.

## Print this first

1. Print the coupon (`part = "coupon"`, ~21 mm stub) in the material you'll
   use for the module.
2. Mate it with a printed port from any other NUGGS module (or a second
   coupon). It must insert to the collar face and lock with a light quarter
   turn — firm, no rattle, no forcing.
3. Forcing loose → raise `port_tol` in +0.05 steps and reprint the coupon.
   Will not lock / grinds → lower 0.05. If it inserts but the quarter-turn
   grinds near the lock, deburr the sector tips' first layer with a blade
   before touching `port_tol` — or set elephant-foot compensation
   (initial-layer horizontal expansion) to 0.2 mm for the coupon and the node.
   Caliper the bore while you're at it: under 79.0 mm means the printer is
   shrinking.
4. Only then commit the full module (~195 mm tall, ~7 h at 0.2 mm).

## Print settings

- **Orientation:** as rendered — both ports down, sector tips on the bed, bore
  vertical at both ports (the family idiom). No supports; the only spans are
  the two bore ceilings (45°-class at the coupling collar, the family's proven
  pose) and the 12.2 mm anchored web bridge (see above).
- **Material:** PETG or PLA; the part is a pass-through, not a load-bearing
  joint, so either serves. PETG if the run lives in a warm room.
- **Layer height:** 0.2 mm, 3 perimeters (wall 2.4 mm ≈ 3×0.4 nozzle exactly).
- **Brim:** off. Only the sector tips touch the bed — ~10 cm² total; the web
  is a bridge at the port plane, 10 mm up — so the first ~50 layers print as
  twelve small islands that merge at the port plane. Expected, not a fault; a
  brim would weld across the mating feet.
- **Bed:** 256×256×256 class (what `printcheck.args` gates), **194.8 mm used
  height**. The binding constraint is the gate's test-slice, which runs
  PrusaSlicer on bare defaults: that build volume caps Z at **exactly
  200.0 mm** (measured here — a 200.0 mm box slices, a 201 mm box does not;
  XY is *not* enforced, 250 mm boxes slice clean). Not the 250 mm Z of stock
  printer definitions, not printcheck's 256 class. The design sits 5.2 mm
  under it and asserts 199 parametrically.

## Session log

- 2026-08-25: scaffolded from issue #394 (design-run). Topology, construction,
  dish/grade math, vents derivation, fitchecks and asserts written before the
  first render; the cavity-hull dead end (web hollowed under the floor) and the
  missing bore overrun below the tips were both caught against the library
  contract before any mesh existed. First render clean (no CGAL errors, no
  warnings, all asserts passing); bottom-iso inspected — both port rings on
  their sector tips, solid web between, no visible defects.
- 2026-08-25 (gate iteration 1 → 2): two findings off the first
  `gate.sh --slice`. **(1) The test-slice failed: 202.4 mm tall.** The gate
  slices with bare-default PrusaSlicer, whose build volume caps Z at exactly
  200.0 mm (probed with 190/200/201/205 mm boxes; XY unenforced) — the gate's
  real bed law, not the 250 mm of stock profiles nor printcheck's 256 class.
  Fix: `chamber_zc` 95 → 90 (197.4 mm total). Every dish/width/grade number
  is an x-y-plane property — untouched; the chamber's 190 mm clear height is
  untouched; only the plain bore above the port zone shortened by 5 mm. The
  bed-fit assert tightened 250 → 199 with the measured story in it.
  **(2) `path-clear` failed, 992 facets.** Three stacked defects in the sweep
  (recorded in the Fitchecks section): the convex-hull-of-a-U-route, a route
  point typed as its standoff constant, and floor tangency from −x offsets.
  Route rebuilt as derived centres + consecutive-capsule sweep and verified
  numerically first (658 stations, worst air 1.00 mm, control interferes
  everywhere). Printcheck itself passed both parts clean on iteration 1 —
  the failures were the slice ceiling and the fitcheck only.
- 2026-08-25 (gate iteration 2 → 3): gate GREEN at iteration 2 (exit 0 — both
  fitchecks pass, both parts printcheck-clean and sliced). One printcheck
  WARNING was a real printability cost, not taste: **9274 mm² of unbridgeable
  >45° overhang**. First diagnosis — the belly — and first fix (`chamber_az`
  95 → 90) were WRONG: a flatter-in-z ellipsoid has a *bigger* near-horizontal
  polar cap, and the figure moved the wrong way (9459). Chamber dims now
  94×200×180; every gated number (clear width, dish, grade, cap burial) is an
  x-y property, untouched; route re-verified numerically at az = 90.
- 2026-08-25 (gate iterations 3 → 5, the crown cap): a facet scan of the
  export bucketed the overhang by z — the bulk sat at **z = 160..180: the
  inner ellipsoid's polar cap, i.e. the cavity's far-end ceiling**, not the
  belly (issue #34's physics: an *enclosed* near-horizontal ceiling is
  unbridgeable; the supportless limit is 45°). Two fixes, one dead end:
  - **Dead end (iteration 4): a single-apex elliptic cone** over the z=142
    cross-section (39×84), height set to make the x-profile exactly 45°. The
    figure got WORSE (9459 → 15835 mm²): one apex over an elliptic footprint
    cannot be 45° in both profiles — matching x forces the y-profile to
    a/b ≈ 0.47, i.e. **25° from horizontal over most of the roof**. Recorded
    so the next crown isn't sent down the same path.
  - **Fix (iteration 5): a barrel vault.** From z=140 the cavity closes on a
    gable — two roof planes at atan(41.4/39.9) ≈ 46° meeting at a ridge line
    along y — intersected with the vertical elliptic prism over the same
    z=140 cross-section, so the y-end walls are vertical. Every surface of
    the cap is ≥45° **in every direction by construction**. Overhang figure
    15835 → **3449 mm² (9% → 2% of surface)**; a facet re-scan puts the
    residue at z = −20..20 (the belly pole) plus 137 mm² at the bore mouths,
    nothing at the crown. Ridge at z=181.4, 3.4 mm under the outer crown;
    the route's highest envelope point (124.8) is 15 mm below the vault's
    eaves, so it costs the animal nothing.
  - **Belly pole flush (same edit): `chamber_zc` 90 → 92.4 = az + wall**,
    putting the outer belly's bottom pole exactly at the bed plane instead of
    2.4 mm under it — the dome now prints pole-down *onto* the bed, each
    layer resting on the one below (~one extrusion width of per-layer offset
    near the pole), rather than hanging over air under the web bridge.
    Bottom-iso inspected: nothing below the port plane, no defects.
  - The residual 2% is the den-class warning the family ships with (den:
    4% @ 76/100; this design: 2% @ 84/100) — the pole-flush dome and the
    12.2 mm anchored web bridge, both watched by printcheck + the test-slice
    gate, which stay green.

- **Post-iteration-5 preview add (not a gate iteration — geometry unchanged):
  `cutaway-profile` camera.** The PM checkpoint flagged that `cutaway-cross`
  alone doesn't show the vault unambiguously — from its 15° elevation the
  outer dome's silhouette (pole z=184.8) nearly coincides with the ridge
  (z=181.4), and two independent vision reads called the ceiling a "smooth
  rounded dome". The new shot is the same y=0 section **dead-on** (rx=90, eye
  along +y): no elevation, so the two straight roof planes and the ridge
  corner read as a drawing. Vision read of the new render: "pointed
  gable/tent … two straight sloping lines meet at a distinct corner/ridge
  point". Camera added to `previews/cameras.conf` (new line, nothing moved)
  and documented in `previews/CAMERAS.md`.
