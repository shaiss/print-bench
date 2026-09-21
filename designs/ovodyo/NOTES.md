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

- Ball halves: **pole-down** — the flat pole pentagon on the bed, the seam ring
  at the top of the print (see Key decisions: Ball seam). The chamfer facets
  ringing the pole sample as ~52° overhangs and the sharp facet edges sample as
  thin walls (both inherent v0 caveats of a faceted ball, tracked to the
  generator #600, not the seam). Truss segments: bottom-chord-down (as
  modelled). Mock-drive gear: flat.
- `gate.sh --slice ovodyo` (CI manifold engine): hours-top/hours-bottom/
  minutes-top/minutes-bottom **84/100 (PRINTABLE WITH CAVEATS** — near-pole facet overhang
  + thin sampled wall at the facet edges, both #602; watertight, one body — the
  cut-through numerals do NOT drop a counter and the seam bisects no number),
  base-segment 100/100, base-end 100/100 (with the bored stalk socket),
  mock-drive 100/100; all slice. No CRITICAL, no failure. (Local stable-engine
  2021.01 scores the halves ~76; the caveats are the seam/orientation ones #602
  owns.)

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
  and fattens a ring's foot. The **female** puck prints bore-mouth-down like the
  top half, so its fit is faithful. The **male** puck, though, stands on a flange
  *on the bed*, while the production male ring prints at the *top* of the
  pole-down bottom half — so the male coupon can show a first-flank elephant's
  foot the ball never gets. If the male starts hard but runs free afterwards,
  that is coupon-only flange foot: fix the first layer (z-offset / flow), and do
  **not** loosen `seam_tol` to chase it — prefer the looser-feeling end of a
  clean seat before locking the value for the halves. (Printing the coupon male
  top-down like the half is a coupon-fidelity follow-up.)
- Then render the four halves with the winning value and print them
  pole-down (see Key decisions: Ball seam).

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
