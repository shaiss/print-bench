# Camera descriptions

Per-shot descriptions for `cameras.conf` (the freeze convention: a camera is
fixed once reviewed; a new region gets a new line).

- **contact-sheet** — the whole clock, 2×2 iso / top / front / bottom-iso. The
  bottom-iso is the overhang / bed-contact check on the truss chords.
- **hero** — three-quarter of the assembled clock: two faceted balls on brass
  stalks over the tapered truss, with the red gear-trains and PCB in the base.
- **hours-ball** — a single ball three-quarter: flush pentagon plaques, bold
  cut-through numerals, helical slot framing the red interior.
- **slot-corner** — close three-quarter aimed at the helical slot where it
  crosses a corner facet. Added for #768 so the opened corner cut is visible as
  a shot, not only asserted in NOTES (new region = new line, never a reframe of
  `hours-ball`).
- **slot-path** — near-equator view of the helical slot band cutting across
  corner facets. Added after Drik R2 noted `slot-corner` mostly framed numerals;
  new line, not a reframe of `slot-corner`.
- **base-mech** — the base drivetrain alone: geared stepper + reduction train at
  each pod, bevel take-off up each stalk, central electronics bay.
- **base-mech-in-situ** — the same drivetrain seated in the truss so the gears
  have scale and a home (companion to frozen `base-mech`; new line).
- **what-ships** — single-material honesty shot: shells + bare truss, balls
  standing pole-down beside the base (the interim display; not on stalks).
  Rendered with CGAL (`render`) so cut faces stay one colour. Beside the v0
  banner; must not replace the hero.
