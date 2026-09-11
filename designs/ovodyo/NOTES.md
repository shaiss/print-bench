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
  bisects **no** number face — the top half carries 12/2/4/6/8/10, the bottom
  1/3/5/7/9/11 (and the minutes equivalents). This fixes the earlier bug where
  BOTH `hours-half`/`minutes-half` were the same z≥0 dome, so four numbers lived
  on no printable part. Parts are now `hours-top`/`hours-bottom`/`minutes-top`/
  `minutes-bottom`; the bottom half is flipped 180° so it too prints
  flat-cut-face-down. The halves **key on three dowels** (Ø2.8, irregular
  azimuths 24/150/262° so they seat at one clocking) drilled through bosses on
  the inner wall at the seam, in the whole ball before the split so the two
  halves' holes register by construction. The captive threaded/snap seam stays
  #602; the faceted dome still has light overhangs (v0 caveat, #602).
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

## Resume context

Entry `ovodyo.scad` dispatches on `part`: assembled | hours-top | hours-bottom |
minutes-top | minutes-bottom | hours-ball | minutes-ball | base-segment |
base-end | mock-drive | base-mech | pod-drive. The `-ball` parts are the full
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
