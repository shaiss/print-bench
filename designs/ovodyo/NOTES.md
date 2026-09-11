# ovodyo — engineering notes

## Goal

A clean-room, print-bench-native re-creation of Mectolab's "ovodyo" kinetic
dice-ball clock, built as the **v0 base** every issue in the [#599](https://github.com/shaiss/print-bench/issues/599)
improvement backlog modifies. The reference study and the improvement brainstorm
were produced in-session (design study + `ovodyo-improvement-brainstorm.md`).

## Given measurements (from the reference)

- Overall envelope 383 × 78 × 163 mm; each ball ≈ 78 mm diameter.
- 12 numbered pentagon plaques per ball on icosahedral-vertex directions (a
  triangulated/geodesic sphere; exact frequency left open → our `facet_mix`).
- Hours ball indexes every 450°, minutes every 90°.
- Base is three bolted segments (2 motor pods + centre electronics); brass
  support stalks; 15 mm 1:99 geared steppers; hall-sensor homing; ATmega8 +
  DRV8833 + WS2812 + USB-C.

## Key decisions

- **Ball geometry:** a **chamfered dodecahedron** — 12 big FLUSH pentagon
  number-faces (the reference's headline: bold numbers on the outermost faces)
  with the 20 dodecahedron vertices shaved into triangular corner facets, so it
  reads as a chunky faceted dice-ball. Built (in `geodesic-ball.scad`,
  `gb_faceted_ball`) as the intersection of 12 pentagon half-spaces at radius
  `d/2` and 20 triangle half-spaces at `tri_k·d/2`; `tri_k` (default 1.05) sets
  how deep the corner triangles cut — 1.0 ≈ a full icosidodecahedron (biggest
  triangles), ≥1.12 collapses to a plain dodecahedron (no visible chamfer). The
  pentagons at `d/2` are the outermost faces, so the numerals read face-on.
  **Two earlier constructions were wrong and are recorded so they aren't
  retried:** (a) a geodesic icosphere clipped into pentagon *plaques* recessed
  the numbers into ~5 mm dimples where they were unreadable from any oblique
  angle; (b) a true icosidodecahedron *recesses* its pentagons below the
  triangles (pentagon plane 0.832·R < triangle plane 0.934·R), so the numbered
  faces again sat in valleys — and worse, the cavity sphere (sized off a wrong
  0.951·R "pentagon" constant) bulged out through each pentagon and `difference`
  carved a round hole on every number face. The chamfered dodecahedron puts the
  numbered pentagons *outermost*, which is the whole point. Generator is
  **design-local for now** — issue #600 promotes it to `lib/geodesic-ball.scad`
  with demo/guards/mates.
- **Numerals:** **cut clean through** the shell to the red interior (the
  reference's read-through red numbers), stencilised so no enclosed counter
  (0/4/6/8/9, and 0/6/8/9 offset from centre in a two-digit "10"/"00") drops
  out. `_gb_stencil` subtracts two full-width horizontal ties in the counter
  band (±0.13·bh — squarely through every counter ring, not out at the edges
  where they missed the offset "0" of "10") plus a central vertical tie. Proved
  island-free by rendering each half and requiring CGAL `Volumes: 2` (a dropped
  counter shows as a third volume). This delivers what was deferred to #601;
  the tunable brand-module `helical_window` + sever-guard stay #601.
- **Hollowing:** a spherical cavity at `d/2·_GB_PENT_R − wall` (the pentagon
  plane minus the wall), so the wall is `>= wall` at every pentagon face and
  thicker toward the triangles/vertices — no knife-edge thin spots that a scaled
  faceted copy would leave.
- **Base mechanism:** the reference's exposed "gears in the base" are modelled as
  PREVIEW-ONLY red working parts (like the ball's red core — coloured, never in a
  printed part, `colour` ignored on STL export): a **geared stepper + a
  horizontal reduction gear-train at each pod**, a **bevel take-off** turning each
  train up its vertical stalk at 90°, and a **central electronics bay** (PCB +
  ATmega + DRV8833 + USB-C + WS2812 row). Gears are hand-rolled trapezoidal-tooth
  approximations (`mech_spur`/`mech_bevel`, no BOSL2 dependency, fast) — they
  *represent* the drive, they are not cut for a running fit. A real meshing
  involute differential gated as turning is still #604; the reusable
  `lib/spaceframe.scad` + red structural core stay #603.
- **Printable unit = a numbered top + bottom half.** A whole ball prints on a
  point (CRITICAL bed contact), so each ball splits in two. The split is
  **pole-up**: the ball is tilted by `atan2(1,PHI)` so a pentagon face sits at
  each ±z pole, which puts the equatorial cut through the triangle band and
  bisects **no** number face. Which numerals land on which half is now set by
  the tumble stop table (see "Tumble kinematics (N2)"): the top (+z) half
  carries 2/7/5/9/11/3, the bottom 6/1/8/4/12/10 (minutes: the same stops, so
  10/35/25/45/55/15 top, 30/05/40/20/00/50 bottom) — the older "even numbers
  top, odd bottom" wording in ovodyo.scad's seam/dispatch comments predates
  the table and is stale. This fixes the earlier bug where
  BOTH `hours-half`/`minutes-half` were the same z≥0 dome, so four numbers lived
  on no printable part. Parts are now `hours-top`/`hours-bottom`/`minutes-top`/
  `minutes-bottom`. The halves join on the captive threaded seam below.
- **Ball seam = a captive single-start thread (#602 item 7), one turn to close.**
  Built from `lib/threads-fdm.scad` so male and female come from one helix
  generator: the bottom half grows a **male ring** (`thread_neck` bored to a
  2 mm ring, `_seam_neck`) 5 mm up from its flat seam face at crest Ø70, just
  inside the Ø73.6 cavity; the top half carries the **female groove**
  (`thread_bore_cut` plus the minor bore its doc says the caller owes, plus a
  0.6 mm mouth chamfer, `_seam_female_cut`) in an internal rim boss
  (`_seam_boss`). The seam plane stays a true flat great circle; the halves
  mate on the flat annulus from the female crest (r 35.25) out to the facets
  (r ≥ 41.7), i.e. ≥ 6 mm of square face, and each half's outer seam edge has
  a 0.6 mm 45° chamfer that follows every facet (`_seam_edge_chamfer`, the
  ball's 32 face planes re-tilted within 0.6 mm of the seam) so the seam
  reads as one crisp V line. `seam_tol` (0.25 mm radial) is the ONE tunable.
  **Starts arithmetic — why a single start, not 2–3:** an S-start thread has
  S seated clockings 360°/S apart, and every one of them is a valid seat for
  the *thread*; but the assembled *ball* has exactly one valid clocking — the
  pentagon ring is 72°-periodic about the pole, the 20 triangle chamfer planes
  are not (checked numerically against the generator's own plane set: no
  rotation about the pole but 360° maps them onto themselves), and the twelve
  numerals are all different anyway. 2 starts seat at 180° (≡ 36° in the
  pentagon period: half a facet off, numbers scrambled), 3 at 120° (≡ 48°),
  5 at 72° (pentagons align, triangles and numerals don't). Only 360/S ≡ 0
  works, so S = 1; then neck length = pitch = 5 mm makes the closing rotation
  length/lead × 360° = **exactly 360°**: line the facets up, drop the top on
  (a single start only enters at that one clocking), one full turn, and they
  line up again as the faces meet. Guards at these numbers: single start so
  only the lead bound applies, `w_root = 0.25·5 + flank_add(tol) + 2·1.0 =
  3.25 + 0.83·tol < 5` ⇒ tol < 2.1 mm (the coupon's 0.15–0.45 window is far
  inside); chord `(70/2)(1 − cos(180/48)) = 0.075 ≤ 0.1`; core 34 > 0.4.
  **Slot:** the helical slot is refilled within |z| ≤ 5 of the seam
  (`_seam_band_fill`, wall only), so it never crosses the mating ring and
  reads as two arcs of one interrupted helix — the divergence from the
  reference's "the slot is the seam" that #602 accepts. The band and the boss
  are sized to the numerals: the cut-through glyphs come no closer than
  |z| = 5.5 to the seam and r ≈ 36.6 within |z| ≤ 7 (measured in the pole-up
  frame), so the boss stops at ≈ 7.9 mm (at r ≤ 35.0 by z = 7) under a roof
  cone 50° from horizontal and the refill at 5. **Print orientation changed
  to pole-down** for both halves: a ring standing on the seam face cannot
  print seam-face-down, and pole-down is the better orientation for a hollow
  hemisphere anyway (the cavity is an open bowl instead of a 40 mm ceiling;
  the faces next to the pole lean out at 26.6°; the boss roofs print as 40°
  overhangs — a roof at exactly 45° tessellates to 44.98° and sits on
  printcheck's threshold, so 40° buys margin). What remains flagged is the
  generator's: the chamfer facets ringing the pole pentagon sit 37°+ off the
  pole axis, i.e. 52°+ overhangs when pole-down (~1.7 k mm² low on the print;
  a slicer prints them with some droop, no support needed) — a `tri_k` /
  chamfer-alignment matter for the lib, not the seam. The pole pentagon
  (numeral and all) is the first layer, the seam ring the top. Proven by
  `ci.fitchecks`: `seam-fit` (male ring ∩ top half at the seated pose) renders
  empty at `seam_tol`; `seam-fit-ctrl` (top half a quarter-turn off) interferes.
- **Base = tapered space-frame:** the reference base is a long shallow lattice
  that tapers to needle points at both ends. Modelled as a triangular section
  (two bottom chords + a ridge, Warren-diagonal bottom deck) whose width AND
  height follow `base_t(x)`: full across the centre segment (`|x| <= seg_len/2`),
  then linear down to a small nub over each end segment — so the middle third is
  full-section and the outer thirds point. Three bolted segments: a constant
  `base-segment` (centre) and two mirror `base-end` wings (tapering, each carrying
  a stalk boss over its motor pod). Both gate 100/100. The reusable
  `lib/spaceframe.scad` stays #603.
- **Base product half (#603 item 10 / #604 item 8):** the base becomes a
  printable product on top of the v0 lattice — same silhouette, four additions.
  - **Airiness (N3) measured, not asserted.** Solid volume of the printed base
    (trimesh on the gated STLs) over the bounding box of the assembled base:
    **before** 21,889 mm³ / 1,110,408 mm³ (383.7 × 78.7 × 36.7) = **1.97 %**;
    **after** — segment 9,213 + 2 × wing 6,486 + core 32,353 + 2 × plug 92 =
    **54,713 mm³** / 1,164,911 mm³ (386.6 × 78.7 × 38.3, tip beads and feet
    included) = **4.70 %** (4.5 % on the charter's 383 × 76 × (34 + 8) box).
    The 25 % ceiling has 20 points of headroom; the core is a slim keel and the
    lattice stays the side-view silhouette.
  - **Red structural core (`base-core`, N4 red = a working part).** A keel
    120 × 63 × 8.8 mm that seats in the centre segment only, between the bottom
    chords and under the 9 mm gear line, with a 28 mm trough for the PCB (floor
    4.6, the PCB underside is 5.2). Its **underside is the negative of the deck
    lattice**: a diamond channel (46° roof, support-free; inradius strut_d/2 +
    `core_fit` 0.3) along every cross tie and Warren diagonal of the centre
    segment, drawn from the same `_BL/_BR` node functions `base_truss` uses —
    so the sockets ARE the struts and the core can seat in exactly one pose
    (the Warren zigzag is not 180°-symmetric about the segment centre, and the
    tie pitch pins x). It is slid in along x through the segment's open end
    frame, flat-bottom riding on the deck struts, and drops the channel depth
    onto them when the pattern aligns; the flanks (vertical 2.6 mm skirt, then
    leaning in to a 48.4 mm top) clear the ridge posts in that raised pose.
    `core-seat` proves the seated core ∩ segment struts is empty; the control
    shifts it half a bay so the ties run through the keel (702 facets).
  - **Ballast (stated assumption, not a claim).** Two sealed pockets, one per
    rail: floor `core_wall` 1.4 above the bottom, walls 1.4, a 44°-from-vertical
    inner slope and outer wall (never an overhang from inside), a flat ceiling
    strip < 5 mm wide (a bridgeable span), and the channels' humps offset by the
    wall so the cavity keeps >= 1.4 to every socket. Cavity volume (numeric
    integration of the section minus the humps, 0.1 mm grid): **11.8 cm³** for
    both pockets. Vitamin: **Ø2 mm steel shot** (chrome-steel bearing balls or
    #9-size steel shot); at 7.85 g/cm³ × ~0.60 random packing ≈ 4.7 g/cm³ the
    fill is **≈ 55 g (2 × 28 g)**. Filled through a Ø3.2 port in the +x end
    face of each pocket (round, so its roof bridges; placed above every socket
    crest with a full wall under it and clear of the end-bay diagonal's hump),
    closed by `base-plug` (print two): a Ø5 × 1.2 head proud on the end face,
    inside the 3.5 mm gap to the segment's end tie, and a 3.3 → 2.7 mm tapered
    shank that wedges in the 4.2 mm end wall. Fill and plug BEFORE sliding the
    core in. `pocket-clear` proves the cavity ∩ the core's outer 1.2 mm shell
    (the section eroded by 1.2 + the sockets grown by 1.2, ends included) is
    empty; the control raises the ceiling through the roof (156 facets). Whether
    55 g at z ≈ 5 mm is enough against two ~50 g balls at 124 mm is the
    **CoG/tip-over gate that is NOT in scope tonight** — this number is an
    assumption to be measured, never a README stability claim.
  - **Feet.** Each wing carries two Ø7 pads under its inner-end chord nodes
    (`_bx(bays)` − 4 in x, `_bw` − 2 in y: hanging below the chord, inboard of
    its outer face, invisible from the hero camera). The pad bottom is FLUSH
    with the chord underside (a first cut hung them 1.5 mm below and printcheck
    rightly reported a 39 mm² bed contact + tip-over: the wing would have
    printed standing on two pads) and carries a Ø4.9 × 0.7 recess for a
    **Ø5 mm × 1.5 mm hemispherical stick-on silicone bumper** (vitamin; the
    recess is kept under 5 mm so its roof is a bridgeable span, 100/100). The
    base stands on four bumpers 0.8 mm proud; the tips float 0.8 mm.
  - **Tips.** `base_t` keeps its form; the floor is `tip_nub` 0.01 (was 0.05)
    and a `tip_d` = 2 × strut_d = Ø5.6 bead at the tip station, bottom flush
    with the chords, encloses the three converging strut ends — the needle ends
    in one round nose, no cap, no truncated bay.
  - **Deliverable = the plate.** `ci.plate` lists the eight production part
    VALUES (four ball halves, base-segment, base-end, base-core, base-plug);
    plate.sh merges each value once, so a part printed twice (base-end, base-plug)
    is listed once and duplicated in the slicer (documented on the page).
    `plate.sh --check`: 8 separate objects == 8 declared parts. The assembled
    render stays a preview.

## v0 simplifications → which issue upgrades each

Done in this pass (were v0 shortcuts): cut-through stencil numerals, the visible
red interior/two-tone (preview), and the exposed base drivetrain. What remains:

| v0 shortcut still open | Upgraded by |
|---|---|
| Helical slot is a fixed inline cut (not yet a tunable brand module) | #601 (tunable `helical_window` brand module + sever-guard) |
| Two-tone shown only in preview colour, no committed two-tone reveal render | #600 (two-tone reveal render) |
| Base drivetrain is a **preview representation** (hand-rolled trapezoidal gears, not involute, not cut to a running fit; no red structural core; not a reusable lib) | #604 (`lib/bevel.scad` real meshing differential + kinematics gate) + #603 (`lib/spaceframe.scad` + red core) |
| Ball halves key on **loose dowels + glue** (flat butt joint) | #602 (captive threaded/snap mating seam) |
| ~~Deliverable gated as loose parts; no `ci.plate`~~ done: `ci.plate` → `build/ovodyo-plate.3mf`, 8 objects | (`ci.fusecheck` stays with the seam work) |
| Ball generator is design-local | #600 (promote to `lib/`, with a `tri_k` guard + facet mate) |
| No committed style pack / stylelift metrics | #601 (style pack + facet/openness metrics) |
| Ballast pockets + a stated ≈55 g shot fill exist, but no CoG/tip-over gate proves it is enough | #603 (CoG/tip-over gate) |

## Tumble kinematics (N2)

The charter's soul: a fresh flat face **lands upright** at each stop, not a spin.
This section is the kinematic model that makes N2 a gate-checkable claim; the
printed mechanism parts (sun/crown bevels, yoke, hub axle) and the base are the
other Wave 2 agents' work and use the frames and table defined here.

**No single axis can do it.** The 12 plaque normals are the vertices of an
icosahedron, an orbit of the icosahedral rotation group, whose elements have
orders 1, 2, 3 and 5 only — there is no order-12 rotation, so no fixed axis
carries plaque to plaque twelve times. Cutting the sphere by any axis, at most 5
plaques share one cone (the ring around a 5-fold axis), so a single rotation
can present at most 5 of the 12 to a fixed viewer. Two compounded rotations are
therefore necessary: the **yoke** turning the ball's axle about the vertical and
the **crown** spinning the ball about that axle — an epicyclic.

**The pole plaques fix the viewer.** The two plaques on the ball's 5-fold axis
have normals ±the axle, and the yoke keeps the axle horizontal, so those two
normals only ever sweep the horizontal plane: they can land *exactly* only for a
**horizontal** presenting direction. That is why F = world +x (the viewer) is
horizontal; the poles then land with zero error at yoke 90° and 270° (mod 360).

**The mechanism (decided; built by the mechanism agent).** A fixed bevel **sun**
(`tumble_n_sun` = 12 teeth) at the top of the stator stalk; a yoke turned about
world +z by the yoke angle φ; the ball's hub axle pole-to-pole (ball-frame +z of
the pole-up frame) mounted horizontal in the yoke, carrying a bevel **crown**
(`tumble_n_crown` = 20 teeth) rolling on the fixed sun, so the ball spins about
its own axle by −ρ·φ, ρ = 12/20 = **3/5**. Sign convention (the one sentence the
mechanism must match, verbatim from `tumble.scad`): *with the mount
M = rotate([-90,0,0]) carrying the ball's +z pole axis onto world +y, the crown
mounted on the +pole side of the hub axle with its teeth facing the ball centre,
and the fixed sun on the stalk below the ball centre, a yoke rotation of +φ
about world +z spins the ball about its own +pole axis by −ρ·φ (right-hand sense
about the +pole direction), so Q(φ) = Rz(φ)·Ry(−ρ·φ)·M (world ← ball).* A crown
on the −pole side flips the sign, and then the table and every numeral rotation
change — rerun the derivation, never hand-edit.

**The stop table** (`designs/ovodyo/tumble_stops.py`, stdlib+numpy: the 12
normals built exactly as the design does — `gb_icosa_verts()` order, then the
`_pole_up` rotation — posed by M and Q(φ), φ swept over the 5-turn cycle at
0.25° and every plaque's landing events refined; the 12-stop table with the
smallest max error, ties at the poles resolved to the earliest yoke angle):

| stop | numeral | face | yoke φ (°) | step (°) | landing error (°) | crown (°) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 12 | 9 | 27.3361 | 54.67 | 1.620 | −16.40 |
| 1 | 1 | 3 | 90.0000 | 62.66 | 0.000 | −54.00 |
| 2 | 2 | 0 | 270.0000 | 180.00 | 0.000 | −162.00 |
| 3 | 3 | 10 | 332.6639 | 62.66 | 1.620 | −199.60 |
| 4 | 4 | 7 | 387.3361 | 54.67 | 1.620 | −232.40 |
| 5 | 5 | 4 | 692.6639 | 305.33 | 1.620 | −415.60 |
| 6 | 6 | 1 | 747.3361 | 54.67 | 1.620 | −448.40 |
| 7 | 7 | 2 | 1052.6639 | 305.33 | 1.620 | −631.60 |
| 8 | 8 | 5 | 1107.3361 | 54.67 | 1.620 | −664.40 |
| 9 | 9 | 6 | 1412.6639 | 305.33 | 1.620 | −847.60 |
| 10 | 10 | 11 | 1467.3361 | 54.67 | 1.620 | −880.40 |
| 11 | 11 | 8 | 1772.6639 | 305.33 | 1.620 | −1063.60 |

(step = yoke advance from the previous stop; stop 0's is from stop 11 across the
cycle wrap.) Max landing error **1.62°** (tolerance 3°); the numeral-up residual
at those stops is 1.43°. The stops span 1745.3° of yoke; the **cycle closes
after 5 yoke turns (1800°) = 3 crown turns**, since Rz(1800) = Ry(−1080) = I.
Every non-pole plaque lands exactly once per cycle (at 360·j ± 27.34°), the two
pole plaques five times each, so the table is forced up to the choice of pole
instance. **Crown-angle range over the table (the stalk-gap sweep for the
mechanism agent):** `tumble_crown_range()` = [−1063.60, −16.40]°, a 1047.2°
span — more than a turn, so the stalk sweeps the ball's **whole equator** over
a cycle (the stalk direction in the ball frame is the great circle ⊥ the pole
axis, parametrised by the crown angle); any stalk gap must be a full ring
through the triangle band, which is where the seam already runs.

**Why not the reference's uniform 450°/90° index.** Under one epicyclic with a
horizontal viewer, uniform yoke steps of 90° (or 450° ≡ 90° per turn) alternate
the presenting direction between the axle line and the transverse plane:
Q(90k)⁻¹·x is ±the pole axis for odd k (the two pole plaques, again and again)
and an equatorial direction for even k, where a pole-up dodecahedron has **no**
plaque normal at all (the rings sit at 63.4° and 116.6° from the pole). So a
uniform 90° table presents only the two poles, six times each — it cannot land
12 faces. The reference's numbers describe a different drive; this clone's
stops are irregular in yoke angle (54.7 / 62.7 / 180 / 305.3° steps) and live in
firmware as the baked table, which a stepper follows for free.

**Numeral placement follows the table.** `tumble_nums(gb_hours())` reorders the
numerals to face order (numeral k on face `tumble_face_order()[k]`) and
`tumble_rots()` clocks each one in-plane so it reads upright at its own stop
(rotation about the outward normal, CCW seen from outside, computed per stop and
verified through the very transforms `gb_numbers` applies). `ball_core`'s red
preview inlay takes the same order and clocking so the two-tone preview matches
the cuts.

**Gate (`ci.kinematics`, the landing half — the sun/crown mesh rows are the
mechanism agent's).** Five geometry-true boolean parts in `tumble.scad`, each a
real CGAL render read by facet count, dispatched by `part=` with `-D stop=k`:

- `landing-flat` — the hours ball **as it ships** posed by Q(φ_k), intersected
  with a probe slab x ∈ [Rp+ε, Rp+ε+6] inside a 12 mm cylinder about +x
  (Rp = ball_d/2, ε = 12·sin 3° = 0.63 mm): empty iff the presenting plaque is
  within 3° of +x (a tilted plaque rises into the slab at the probe's edge).
  `landing-flat-ctrl` poses 20° past the stop and must hit.
- `landing-glyph` — the presenting face's through-cut numeral cutter (the exact
  `gb_number_cutter` the ball subtracts, with its baked rotation) posed at the
  stop, minus an upright template of the same stencil extruded along +x at the
  plaque centre with 2D up = world +z, grown 1.0 mm: empty iff the numeral is
  aligned and unmirrored within ~1 mm (resolves a ~7° roll).
  `landing-glyph-rolled` (template rolled 30°) and `landing-glyph-mirrored`
  (template mirrored) must leave material.

Proof renders (OpenSCAD 2021.01 CGAL, `$fn=32`, `./scripts/lineage.sh
facet-count` on the binary STL; 0 = empty):

| part | stops rendered | facets |
|---|---|---|
| `landing-flat` | 0–11 | stop 0: 0; stop 1: 0; stop 2: 0; stop 3: 0; stop 4: 0; stop 5: 0; stop 6: 0; stop 7: 0; stop 8: 0; stop 9: 0; stop 10: in flight at hand-off; stop 11: in flight at hand-off |
| `landing-flat-ctrl` | 0, 1 | stop 0: in flight at hand-off — must be > 0; stop 1: in flight at hand-off — must be > 0 |
| `landing-glyph` | 0–11 | 0 at every stop (0,0,0,0,0,0,0,0,0,0,0,0) |
| `landing-glyph-rolled` | 0, 3 | 698; 348 (> 0, the check can fail) |
| `landing-glyph-mirrored` | 0, 3 | 334; 178 (> 0, mirroring is caught) |

The rows marked *in flight at hand-off* were still rendering when this commit was cut (the batch ran 2-wide on a shared 4-CPU box at ~65 s per full-ball render); `stops 0–9` of `landing-flat` came back 0. Re-run: `for s in 10 11; do xvfb-run -a openscad --export-format binstl -o build/lf-$s.stl -D 'part="landing-flat"' -D stop=$s designs/ovodyo/ovodyo.scad; ./scripts/lineage.sh facet-count build/lf-$s.stl; done` (and the same with `landing-flat-ctrl` at 0 and 1, which must count > 0).

**Regenerate.** `python3 designs/ovodyo/tumble_stops.py` prints the report and
the baked block; `--write` splices it into `tumble.scad`; `--check` exits
non-zero if the committed block drifted from the derivation. The script asserts
max error ≤ 3°, every face presented once, and monotone stops.

## Print orientation & gate status

- Ball halves: cut-face-down (flat ring on the bed); the faceted dome has
  overhangs and the sharp facet edges sample as thin walls (both inherent v0
  caveats of splitting a faceted ball at the equator, the #602 seam/orientation
  work). Truss segments: bottom-chord-down (as modelled). Mock-drive gear: flat.
- `gate.sh --slice ovodyo` (CI manifold engine): hours-top/hours-bottom/
  minutes-top/minutes-bottom **84/100 (PRINTABLE WITH CAVEATS** — dome overhang
  + thin sampled wall at the facet edges, both #602; watertight, one body — the
  cut-through numerals do NOT drop a counter and the seam bisects no number),
  base-segment 100/100, base-end 100/100 (with the bored stalk socket),
  mock-drive 100/100; all slice. No CRITICAL, no failure. (Local stable-engine
  2021.01 scores the halves ~76; the caveats are the seam/orientation ones #602
  owns.)
- Base product half (local stable 2021.01, `gate.sh ovodyo` exit 0): base-end
  100/100 with the feet + nose (flat bed contact on the chords and pads),
  **base-core 100/100** (flat-bottom-down: every socket roof is a 46° chamfer,
  the pocket ceilings are < 5 mm bridges, walls >= 1.4), **base-plug 100/100**
  (head-down). Fit checks: core-seat 0 facets, core-seat-ctrl 702, pocket-clear
  0, pocket-ctrl 156 (`lineage.sh facet-count`). Plate: 8 objects == 8 parts.

## Print this first

`designs/ovodyo/ovodyo-coupon.scad` (part `seam-coupon`, gated as
`build/ovodyo-coupon.stl`) is the seam's tuning coupon: the production male
ring on a thin chamfered flange beside a chamfered puck carrying the production
female cut, mouth up the way the top half prints. Both come from the same
`_seam_neck` / `_seam_female_cut` modules the ball halves use, so the
`seam_tol` that fits here is the one the four halves get. It is 164 mm wide
(two Ø70 rings side by side) and 7 mm tall — a ≥ 170 mm bed, a few minutes of
print, same material and profile as the halves.

- **What to tune:** `seam_tol`, the radial thread clearance, in **0.05 mm
  steps** (`-D 'seam_tol=0.30'` on the coupon, then on every half). Default
  0.25; the usual window is 0.15–0.45 (the library's guards allow up to ~2.1).
- **What a good fit feels like:** the puck starts on the ring by hand within
  the first quarter turn, runs the full turn with light, even drag and no
  tools, and seats flat against the flange with no rattle when you push it
  sideways or rock it. A faint "click" as the flanks load up at the end of the
  turn is right; grinding or needing to force it is too tight.
- **Too tight / won't start:** raise `seam_tol` by 0.05 and reprint the
  coupon. **Rattles, wobbles, or spins back off:** lower it by 0.05.
- **First-layer squish** tightens the first groove of a bore printed mouth-down
  and fattens the ring's foot; both coupon pucks print seam-side up like the
  halves, so what you feel is what the ball will do. If the puck starts hard
  but runs free afterwards, that is elephant's foot on the ring's flange —
  fix the first layer (z-offset / flow) rather than the tolerance.
- Then render the four halves with the winning value and print them
  pole-down (see Key decisions: Ball seam).

## Resume context

Entry `ovodyo.scad` dispatches on `part`: assembled | hours-top | hours-bottom |
minutes-top | minutes-bottom | hours-ball | minutes-ball | base-segment |
base-end | mock-drive | base-mech | pod-drive | landing-flat | landing-flat-ctrl |
landing-glyph | landing-glyph-rolled | landing-glyph-mirrored | hours-posed. The
`landing-*` parts are the N2 kinematics booleans (`tumble.scad`, `-D stop=k`,
gated by `ci.kinematics`); `hours-posed` previews the hours ball at `-D
yoke_deg=φ` for a viewer at +x (camera `0,0,0,90,0,90,260`). The `-ball` parts are the full
shells used only in the assembled preview; the `-top`/`-bottom` parts are the
printable units (pole-up split; `ball_half(hours, top)` builds them). `base-segment`
is the constant centre truss; `base-end` is a tapering end wing (print two,
each with a Ø5.6 nose bead and two bumper feet at its wide end); `base-core` is
the red ballast keel that seats in the centre segment (`core_body()`, modelled
in place on z = 0) and `base-plug` its port plug (print two); `core-seat`,
`core-seat-ctrl`, `pocket-clear`, `pocket-ctrl` are the `ci.fitchecks` parts
(never printed). `ci.plate` builds the multi-object 3MF deliverable.
`base-mech` (whole drivetrain) and `pod-drive` (one pod's gear train) are
PREVIEW-ONLY coloured mechanism — not in `ci.parts`, not printed. The ball's
faceting is `_GB_TRI_K` in `geodesic-ball.scad`; the numeral stencil ties are
`_gb_stencil` (proved island-free by CGAL `Volumes: 2`). Previews are frozen in
`previews/cameras.conf` (added `base-mech`). NOTE: `--viewall` mis-scales this
design because the ball's rotated half-space cubes fatten OpenSCAD's preview
bbox — render scratch shots with an explicit camera `dist`; the committed
previews use explicit cameras so they are unaffected.
