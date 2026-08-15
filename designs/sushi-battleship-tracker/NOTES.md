# sushi-battleship-tracker — engineering log

Shot-tracker refit of the archived [sushi-battleship](../sushi-battleship/)
(frozen at v0.1). Built by the LaundryDev team as a *derivative* — the
revival path the parent's `ARCHIVED` marker prescribes — to exercise the
contribution-rehydration process end to end: lineage record, derivative
render gate, PM charter, art-directed product page, current CI pipeline.

## Goal

The parent tracks hits structurally (an opened door is an eaten cell) but
leaves **misses** to memory, and "did we already call B3?" is the real
failure mode of a leisurely dinner game. The refit adds a shallow spherical
**miss-marker seat** to the top face of every print-in-place shutter door:
park any small round marker (dried soybean, 6 mm airsoft BB, peppercorn) on
a called cell and nobody re-calls it. The product charter lives in PM.md
beside this file.

<!-- No markdown links in the Goal paragraph above, on purpose: gallery.sh
     scrapes it verbatim into the repo-root README gallery row, where a
     design-relative link like [PM.md](PM.md) resolves against the repo
     root and 404s. -->

## The delta, and only the delta

`sushi-battleship-tracker.scad` `include`s the parent's entry `.scad`
verbatim and redefines **`door()`** — nothing else. The parent's own call
sites route to the redefinition, so the print-in-place `top` inherits the
seat on all 16 doors. Lineage is recorded in `derives.conf`
(`replaces: sushi-battleship:top, sushi-battleship:door`), and `gate.sh`
proves both overrides by mesh comparison against the parent
(`docs/derivative-designs.md`).

The restated door body, tabs, grip bar and engravings are verbatim from the
parent (OpenSCAD has no way to extend a module); the parent is frozen at
v0.1, so the restatement cannot drift. Fit surfaces — tab/lip dimensions and
every clearance — are untouched (PM.md N1): a `door_fit` tuned on the
parent's coupon transfers unchanged.

## Given / assumed measurements

- Markers are household objects, assumed roughly spherical, 4–10 mm
  (peppercorn ~4–5, airsoft BB 6, dried soybean 7–9); the range is asserted
  in the `.scad` and `marker_d` defaults to 8.
- Everything else — cell pitch 58, lid 250 × 250, door 47.6 × 50 × 2.4,
  every clearance — is inherited from the frozen parent unchanged; see the
  parent's NOTES.md for those derivations.

## Seat derivation

- `marker_d = 8` mm default (dried soybean; a parameter because soybeans run
  7–9 mm and BBs are 6 mm).
- `seat_depth = 1.0` mm into the 2.4 mm door plate leaves a 1.4 mm floor
  (≥ 1.2 mm asserted — FDM min-feature rule).
- Contact-circle radius `seat_r = sqrt(r² − (r − depth)²)` ≈ 2.65 mm at the
  defaults, so the dish opening is ~5.3 mm.
- Placement: centred in the free band between the engraved coordinate
  (spans to door-local y = +3.5) and the push arrow (base at
  `dl/2 − 9 = 16`), i.e. y ≈ 9.75; both clearances ≈ 3.6 mm, asserted ≥ 0.8.
- The rim needs no chamfer: the sphere meets the top face at ~41° from
  vertical at the defaults, so the edge is already obtuse and the marker
  self-centres.
- Printability: a dish cut from the top face means every layer's hole is
  wider than the one below it — fully self-supporting, no change to the
  print-in-place scheme, zero added height (the grip bar still clears the
  rails by 0.3 mm).

## Key decisions

- Contribute as a **derivative**, not an in-place edit: the parent is
  ARCHIVED at v0.1 and its marker names the derivative route as the revival
  path.
- The seat is a **cut, not a raised feature**: zero added height (grip
  still clears the rails by 0.3 mm), no new overhangs, no change to the
  sliding envelope.
- Claim only `top` and `door` in `replaces:` — the tray is inherited
  unchanged, and a claimed part whose mesh matches the parent's reads as a
  typo'd override and fails the gate.
- No printed marker pegs (PM.md, out of scope): the frozen parent's
  part-selection else-branch draws the assembled preview for any unknown
  `part` value, so a clean `-D part=peg` render needs machinery this refit
  doesn't want to invent.

## Print settings

Identical to the parent: both parts flat, no supports, top prints with all
doors captive. See the parent's NOTES.md for the membrane/bridge scheme —
none of it moved.

## Print this first: the coupon

`sushi-battleship-tracker-coupon.scad` is the production lid at grid 1×1 —
one complete door with rails, lips, ridges, membrane, chamfers and the
marker seat (~30–45 min print). Before committing to the full board:

1. Free the door (one firm push toward the arrow), punch the membrane, and
   check the slide — tune `door_fit` in ±0.1 steps exactly as on the parent.
2. Sit your actual marker in the seat and tilt the coupon to **20°** —
   comfortably past anything a bumped dinner table reaches — and check the
   marker stays seated; record the angle, `marker_d` and `seat_depth` in
   the field-test entry. If your markers are smaller than 8 mm, set
   `marker_d` to match and reprint the coupon.

## Product-shot provenance

The committed `previews/lifestyle-product-hero.png` and `lifestyle-product-hero.gif`
were generated **blind (text-to-image)**, before the pipeline gained image-to-image
seeding. The `seed` now resolving to `product-hero` in `lifestyle.conf` pins the
shape to the real mesh only from the **next re-roll** onward — it does not
retroactively describe the currently committed image.

## Deterministic animations

`animations.conf` (issue #236) gives the page a motion depiction that is
*measured*, not modeled: the AI clip above it is an impression, and a
customer who watches a shutter slide there deserves to see the real
mechanism do the same thing. Two entries, both inherited from the parent —
the tracker includes it verbatim and redefines only `door()`, so
`anim="shutter"` drives the parent's keyframes on the refit's own doors
(seat and all) through `lid_assembly()`:

- **`shutter-slide`** — same camera/frames/delay/size as the parent's
  entry (the D1 corner framing, where the 6.7 mm travel reads clearly), so
  the two boards' animations are visually comparable. The seat dish is
  visible on the sliding door top — verified on the rendered frames before
  committing, since manifest cameras freeze at commit.
- **`turntable`** — full-board 360°, D1 open with the demo piece visible;
  camera-only motion, no `$t` dependency.

No `.scad` change: the parent's `anim` machinery is inherited verbatim, and
per repo convention the `$t`-dependent values live inside the parent's
geometry blocks, so `-D '$t=…'` lands correctly. GIFs render at 72.6 KB and
301 KB — far inside the 6 MiB `MAX_GIF_BYTES` budget.

## Field test log

(None yet — B1 on the PM backlog. Append entries per
`templates/FIELD-TEST.md`.)
