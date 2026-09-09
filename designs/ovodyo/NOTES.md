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
  `lib/spaceframe.scad` and the red structural core stay #603.

## v0 simplifications → which issue upgrades each

Done in this pass (were v0 shortcuts): cut-through stencil numerals, the visible
red interior/two-tone (preview), and the exposed base drivetrain. What remains:

| v0 shortcut still open | Upgraded by |
|---|---|
| Helical slot is a fixed inline cut (not yet a tunable brand module) | #601 (tunable `helical_window` brand module + sever-guard) |
| Two-tone shown only in preview colour, no committed two-tone reveal render | #600 (two-tone reveal render) |
| Base drivetrain is a **preview representation** (hand-rolled trapezoidal gears, not involute, not cut to a running fit; no red structural core; not a reusable lib) | #604 (`lib/bevel.scad` real meshing differential + kinematics gate) + #603 (`lib/spaceframe.scad` + red core) |
| Ball halves key on **loose dowels + glue** (flat butt joint) | #602 (captive threaded/snap mating seam) |
| Deliverable gated as loose parts; no `ci.plate` | #604 (`ci.plate`/`ci.fusecheck` multi-object 3MF) |
| Ball generator is design-local | #600 (promote to `lib/`, with a `tri_k` guard + facet mate) |
| No committed style pack / stylelift metrics | #601 (style pack + facet/openness metrics) |
| No stability/CoG check; balls high on thin stalks | #603 (ballast + CoG/tip-over gate) |

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

## Resume context

Entry `ovodyo.scad` dispatches on `part`: assembled | hours-top | hours-bottom |
minutes-top | minutes-bottom | hours-ball | minutes-ball | base-segment |
base-end | mock-drive | base-mech | pod-drive. The `-ball` parts are the full
shells used only in the assembled preview; the `-top`/`-bottom` parts are the
printable units (pole-up split; `ball_half(hours, top)` builds them). `base-segment`
is the constant centre truss; `base-end` is a tapering end wing (print two).
`base-mech` (whole drivetrain) and `pod-drive` (one pod's gear train) are
PREVIEW-ONLY coloured mechanism — not in `ci.parts`, not printed. The ball's
faceting is `_GB_TRI_K` in `geodesic-ball.scad`; the numeral stencil ties are
`_gb_stencil` (proved island-free by CGAL `Volumes: 2`). Previews are frozen in
`previews/cameras.conf` (added `base-mech`). NOTE: `--viewall` mis-scales this
design because the ball's rotated half-space cubes fatten OpenSCAD's preview
bbox — render scratch shots with an explicit camera `dist`; the committed
previews use explicit cameras so they are unaffected.
