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

- **Ball geometry:** a true geodesic icosphere, matching the reference far more
  closely than the v0 icosidodecahedron did. Each of the icosahedron's 20
  triangular faces is subdivided to frequency `facet_freq` (default 3) and every
  point projected to the sphere; the convex hull of those points is the geodesic
  ball (a fine triangular field whose only sharp points are the 12 fivefold icosa
  vertices). Intersecting with 12 planes — one per vertex direction, at radius
  `r*plaque` — slices each fivefold tip into a flat **pentagon number-plaque**.
  `facet_freq` sets the triangle fineness (2–3 ≈ the reference's snub-dodeca-like
  density; 4+ reads too smooth and the plaques dissolve); `plaque` sets plaque
  size (0.92 gives prominent number faces with a safe wall). Generator is
  `geodesic-ball.scad`, **design-local for now** — issue #600 promotes it to a
  first-party `lib/geodesic-ball.scad` with demo/guards/mates.
- **Hollowing:** a spherical cavity sized to the plaque inradius minus `wall`, so
  the wall is `>= wall` at every face and thicker toward the vertices — no
  knife-edge thin spots (a scaled faceted copy leaves them).
- **Printable unit = hemisphere:** a whole ball prints on a point (CRITICAL bed
  contact). The ball halves cut at the equator and print flat-face-down.

## v0 simplifications → which issue upgrades each

| v0 shortcut | Upgraded by |
|---|---|
| Numerals **debossed**, not cut-through; arbitrary per-face rotation; default font | #601 (parametric stencil glyphs + two-sided `fusecheck` counter gate) |
| Two-tone invisible in single-material render | #600 (two-tone reveal render) |
| Helical slot is a fixed inline cut | #601 (tunable `helical_window` brand module + sever-guard) |
| Base is a **straight rectangular** truss (reference tapers to needle points) | #603 (`lib/spaceframe.scad`) |
| Ball splits as a **crude flat hemisphere**, glued | #602 (flat great-circle mating ring, threaded/snap) |
| Deliverable gated as loose parts; no `ci.plate` | #604 (`ci.plate`/`ci.fusecheck` multi-object 3MF) |
| Drive is a **placeholder** spur-disc cluster | #604 (`lib/bevel.scad` real differential) + #600 (kinematics gate proves it lands upright) |
| Ball generator is design-local | #600 (promote to `lib/`) |
| No committed style pack / stylelift metrics | #601 (style pack + facet/openness metrics) |
| No stability/CoG check; balls high on thin stalks | #603 (ballast + CoG/tip-over gate) |

## Print orientation & gate status

- Ball halves: cut-face-down (flat ring on the bed); faceted dome has overhangs
  (v0 caveat, #602). Truss segment: as modelled. Mock drive: flat.
- `gate.sh --slice ovodyo`: hours-half/minutes-half 84/100 (PRINTABLE WITH
  CAVEATS — dome overhang, some thin wall), base-segment 100/100, mock-drive
  100/100; all slice. No CRITICAL, no failure.

## Resume context

Entry `ovodyo.scad` dispatches on `part`: assembled | hours-half | minutes-half |
hours-ball | minutes-ball | base-segment | mock-drive. The `-ball` parts are the
full shells used only in the assembled preview; the `-half` parts are the
printable units. Previews are frozen in `previews/cameras.conf`.
