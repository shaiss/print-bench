# hex-bit-rail — engineering notes

## Goal

A bench-top rail that stores ¼″ hex driver bits standing up, every one held
by a printed hex pocket and presented label-up — the workshop basic the
catalog had zero designs for (no tool-storage part existed). The engineering
is the fit: a hex pocket registering six faces accurately enough to grip a
hardened steel shank printed against PLA. Brief: issue #594. Design run:
SHIP-LOCK contract in the issue thread.

## Given / assumed measurements

| Dimension | Value (mm) | Given / assumed |
|---|---|---|
| Bit shank hex, across flats | 6.35 (¼″) | given by the de-facto standard; **verify with a caliper** before trusting the coupon |
| Pocket depth (short rail) | 12.0 | assumed — seats the shank past the fluted end without bottoming (~15 mm shank on a 25 mm bit) |
| Ball-detent clearance | floor ≥ 0.5 past the detent | assumed (detent at ~11.5 from the tip) |
| Short-bit stick-up | ≈ 13 | assumed (25 mm bit − 12 mm pocket) |
| Pockets per rail | 12 | assumed |
| Pocket pitch | 16 | assumed |
| Footprint | ≤ 200 × 40 | assumed — 12 pockets + margins, fits any bed |
| Long-bit pocket depth | 18.0 | assumed — the brief's "deeper floor sockets", picked as 12 + floor margin |

## Key decisions

- **Press fit is the only retention mechanism in v1.** No printed latch, no
  magnet — the magnet pocket is the brief's own named follow-up and needs a
  real magnet's dimensions (a `Must fit` row nobody has measured).
- **The hex fit is a parameter, never a literal.** `hex_fit` is added to the
  across-flats; printed hex holes come out undersize, so the production
  default is +0.1 and the coupon sweeps pairs at −0.15 / 0 / +0.15. The
  owner prints the rail at the value their bits like (`-D 'hex_fit=<v>'`).
- **Pockets open upward and print as drawn** — no bridge, no support, and
  the bore walls never see first-layer squish, which is what makes the fit
  tunable at all. The mouths get a 45° break (0.6 mm leg, the style's
  chamfer grammar) as the one-handed insertion aid.
- **Hex flats normal to Y** (corners on the rail axis), so across-flats is
  the pocket's Y extent and `measure_fit.py` can read it straight off the
  exported wall planes.
- **Two rails, one design:** `part = "rail-short"` / `"rail-long"` share
  every module and parameter; the long rail is the same vocabulary with a
  deeper socket. They print separately, so the deliverable is the 3MF plate
  (`ci.plate`), never a merged STL.
- **Mouth-break cutters overlap, never kiss:** the break frustum starts
  0.02 inside the bore so the two cutters' walls are never coplanar (the
  face-touching-union shell failure `alcove-rod-socket` records).
- **Label bosses (per-pocket bit-type glyphs) are v1.1** — deferred by the
  brief; glyph legibility has its own measured failure class
  (`perspective-coin`: 0.25 mm engraving closes on a textured sheet). The
  coupon's fit-value labels are not deferred: a sweep without labels is
  unusable, and raised 0.4 mm text on a vertical wall has no such failure
  class.
- **Glyph shapes are walls to the thin-wall checker** (gate iterations
  2–3). printcheck samples faces and casts a ray inward per face; on an
  embossed glyph that ray crosses a stroke, a bar's height, an inter-glyph
  gap or a digit's counter and reads each as wall thickness. At
  `size = 3.2` the strokes measured 0.2–0.4 mm and 25 % of the coupon's
  sampled surface fell under the 0.8 mm floor — a CRITICAL. Fix, measured
  before re-gating: `size 6`, `spacing 1.2`, `offset(r = 0.25)` drives every
  such span to ~1 mm, and the coupon's pitch widens 16 → 24 because a
  "-0.15" label this fat needs ≈ 22 mm. Related: a *floating* label is its
  own 0.5 mm shell (the 21-body coupon of iteration 1) — embed 0.15 mm so
  the union welds.
- **Wall between labelled pockets is the pitch constraint that bit** —
  not the fit. The production rail carries no text, so its 16 mm pitch
  holds (5.7 mm between pockets after mouth breaks); only the coupon pays
  the label tax.

## Print settings

- **Orientation:** flat-side-down, pockets up — as rendered. No supports.
- **Material:** PLA (a stiff rail, not a flexing member); PETG if the
  pockets wear loose.
- **Layer height:** 0.2 mm — a 6.35 mm across-flats hex resolves cleanly.
- **Infill:** 15 % grid is plenty; the walls carry the load.
- **Perimeters:** 3 (the floor is 2.4 mm — 3 perimeters both sides of any
  flex).
- **Print the coupon first** (below), then the rail at the winning fit.

## Print this first

`hex-bit-rail-coupon.scad` — a 6-pocket strip of the production rail
sweeping the hex fit: two pockets each of −0.15 / 0 / +0.15 across flats,
values embossed on the front wall. Gate it like any part
(`./scripts/gate.sh --slice hex-bit-rail` covers it). Procedure:

1. Caliper two or three of your own bits across the flats. If they are not
   ≈6.35, set `bit_af` to your measurement before anything else.
2. Print the coupon in the rail's material.
3. Drop a bit in each pocket pair: you want the tightest pocket the bit
   still **clicks into and pulls out one-handed** without rocking. The
   undersize pairs grip hardest; the oversize pair is the fallback if your
   printer runs large.
4. Print the rail at the winner: `-D 'hex_fit=<value>'`.
5. Record the result in the field-test log below — the next owner starts
   from your measurement.

## Fit proofs (what CI renders, never prints)

- `fit-bit` — a nominal steel shank seated exactly as the bit seats,
  intersected with the production rail solid: must be **empty** (clears
  every face by `hex_fit/2`).
- `fit-bit-ctrl` — the shank grown 0.4 across flats: must **interfere**.
  The negative control proving the check can fail.

`designs/hex-bit-rail/measure_fit.py` measures the *exported* STL —
footprint, pitch, pocket depth, and across-flats per pocket — so the brief's
numbers are checked against the mesh, not the parameters (issue #37's
lesson).

## Session-resume context

- Entry: `hex-bit-rail.scad` (part dispatch at the bottom; default
  `assembly`). Coupon: `hex-bit-rail-coupon.scad` (include-and-override).
- Style: `workshop-utility` (`style.conf`) — build from its tokens; never
  retype them.
- **Gate history (3 iterations of the 8 cap; telemetry captured each):**
  75 → 67 → 92 lowest score; disconnected shells 21 → 1 → 1; thin-wall
  fraction 71 % → 25 % → 0 %. Green at iteration 3 (only the coupon's
  degenerate-faces WARNING remains — 4 zero-area triangles, −8 points,
  non-blocking, slices clean). `measure_fit.py` (in this directory)
  re-derives the brief's numbers from the exported STLs and exits 0.
- Previews: six frozen cameras in `previews/cameras.conf`
  (descriptions in `previews/CAMERAS.md`), all rendered and committed. No
  `shots.conf` this version — the path-traced hero is backlog B4 in
  PM.md.
- Open questions from the brief, all non-blocking: owner calipers their
  bits (coupon covers ±0.2 anyway); wall-mount flange is brief #396's
  territory (default bench-top); detent feel-test is a coupon-adjacent
  feel test — record it in the field-test log.

## Field test log
