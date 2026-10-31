# Camera descriptions

Per-shot descriptions for `cameras.conf` (the freeze convention: a camera is
fixed once reviewed; a new region gets a new line).

- **contact-sheet** — the whole clock, 2×2 iso / top / front / bottom-iso. The
  bottom-iso is the overhang / bed-contact check on the truss chords.
- **hero** — three-quarter of the assembled clock: two faceted balls on brass
  stalks over the tapered truss, with the red gear-trains and PCB in the base.
- **hours-ball** — a single ball three-quarter: flush pentagon plaques,
  cut-through numerals (read as dark voids / red preview interior depending on
  the shot), helical slot framing the interior.
- **slot-corner** — close three-quarter of numeral plaques with the helical slot
  peeking at the frame edge (original #768 evidence ask; the corner-crossing
  story is carried by `slot-path` after Drik R2 noted this framing). Description
  corrected to match the committed pixels — freeze rule: no reframe. Embedded
  on the product page beside `slot-path`.
- **slot-path** — near-equator view of the helical slot band cutting across
  corner facets (the #768 corner-cut money shot). CGAL `render` (inside-face
  green may still show in the void — renderer tint, not filament). Scale in
  frame: adjacent numeral = 14 mm cap height; slot = 10 mm wide. The tight
  pass-by a numeral plaque is the measured #768 clearance. Added after Drik R2
  noted `slot-corner` framed numerals; new line, not a reframe.
- **slot-window** — numeral close-up: "08" sits on its face (~a fifth of the
  frame); the 10 mm helical slot cuts across the lower half. OpenCSG so
  preview-coloured ball_core can read through; cut walls may tint green
  (renderer, not filament). New line; reframed while unfrozen; caption synced
  to the frozen framing (camera held).
- **base-mech** — the base drivetrain alone: geared stepper + reduction train at
  each pod, bevel take-off up each stalk, central electronics bay.
- **base-mech-in-situ** — the same drivetrain seated in the truss so the gears
  have scale and a home (companion to frozen `base-mech`; new line). Drivetrain
  shown at its mid-base authored pose — the outer pods can read as clipping the
  needle taper; the #604 drive re-seats the pods into the taper.
- **what-ships** — single-material honesty shot: shells + bare truss, balls
  standing pole-down *in front of* the base on a shared ground plane (clear of
  wing tips — an earlier on-axis placement nested the nose under the pole).
  CGAL `render` (inside-face green may still show in the voids — renderer tint,
  not filament). Beside the v0 banner; must not replace the hero.
