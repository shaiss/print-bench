# tape-strip-rack — engineering notes

## Goal

A blade-free multi-strip tape rack for gift wrapping: two rolls on a drop-in spindle, a row of thin fins, and eighteen 40 mm strips per pull — snipped mid-gap with scissors and left hanging by their middles, ready to grab one-handed.

Brief: issue #1062, filed from a product photo the owner supplied. Built in the same session at the owner's instruction, with no interview round: every number in the brief is a stated default.

## Given / assumed measurements

| Measurement | Value | Status | Where it lives |
|---|---|---|---|
| Lanes (rolls side by side) | 2 | **given** (photo) | `lanes` |
| Fins in the default assembly | 10 | assumed (counted from the photo) | `fins_per_rack` × `racks` |
| Tape core inner Ø | 25.4 mm | assumed (1 in core) | `core_id` |
| Tape width | 19 mm | assumed (3/4 in) | `tape_w` |
| Roll outer Ø, maximum | 62 mm | assumed | `roll_od_max` |
| Strip length = fin pitch | 40 mm | assumed (estimated from photo) | `strip_len` |
| Tape plane above the base | 26 mm (brief: ≥ 25) | assumed | `fin_h` |
| Clear gap between fins at the top | 35.4 mm (brief: ≥ 28) | derived | `strip_len` − post length |
| Largest printed part | 208.0 × 57.2 × 42 mm (brief: ≤ 210 long) | derived | `rack` |
| Tallest printed part | 58 mm (brief: ≤ 200) | derived | `cradle` |
| Assembled length | 517 mm (brief: about 500) | derived | cradle + 2 racks + end cap |

None of these was measured from a real roll or a real print. `core_id`, `tape_w` and `roll_od_max` are the three to caliper before printing.

## Multi-part layout

One entry file, `tape-strip-rack.scad`, with a `part` selector. The default, `assembly`, is the preview and is never a deliverable.

- Printable: `cradle`, `spindle`, `rack`, `end-cap` (`ci.parts`).
- Deliverable: the four of them as one multi-object plate, `build/tape-strip-rack-plate.3mf` (`ci.plate`). One of each is already a working five-fin rack; print `rack` twice for the ten fins the preview shows.
- Coupon: `tape-strip-rack-coupon.scad` sets `part = "joint-coupon"`.
- Fit proofs, never printed: `joint-fit`, `spindle-fit`, `roll-fit`, each with a `-ctrl` twin (`ci.fitchecks`).
- `cutaway` and the `explode` parameter exist only for the preview cameras.

## Key decisions

**D1 — Blade-free; the cut is scissors.** The brief's design review looked for how the reference cuts and found that it very likely does not: a product matching the photo is sold as having no blades, with the tape stuck to the bars and cut with scissors. That identification came from search-result text and was not confirmed. The same review estimated the alternative from first principles: an FDM tooth has a tip radius near 0.2 mm, and pressing 50 µm polypropylene tape onto such teeth takes roughly 0.5–3 N per tooth, on tips that hurt a fingertip at that load. Paper tape would cut, matte acetate would half-cut, glossy polypropylene would dimple. No printed cutter is in v1. A pull-over tear edge is on the backlog (`PM.md`).

**D2 — Every part prints upright, as it stands.** The first candidate printed the rack on its side so that printed teeth would come out sharp. With the teeth gone, that reason went too, and the on-side rack had costs: guide posts could only have a 45° ramp on one side of each lane, and the cradle, which cannot print on its side, would have needed a dovetail socket on a vertical face. That socket's upper lip starts as a line in mid-air. It scores 100/100 in printcheck, because printcheck reads face angles, not whether a feature has anything under it. Upright, the posts get steep lane faces on both sides and every joint feature is a plain vertical wall.

**D3 — A drafted drop-in dovetail, key on the downstream end.** The joint is a dovetail in plan, lofted with 10° of draft so the key is wider at the bed than at the top. A socket part can only be lowered onto a key. Lifting a key part therefore carries the socket part hanging on it, so the whole chain lifts from the cradle, which is the end a hand picks up. Lifting a socket part straight up is how it comes apart. Key and socket print in the same orientation, so one clearance, `joint_clear`, covers every joint. Details that exist for a reason:
- the key is drawn in by 0.4 mm over its first 0.5 mm and the socket flared out by the same, so first-layer squish is not the tight spot;
- the socket's two lips are squared back 1.6 mm so they end in a flat, not a 60° knife edge;
- the key's tip corners are cut back 0.8 mm and the socket's are left sharp, so a seam blob in the corner has room;
- the socket rim has a 0.5 mm lead-in.

**D4 — A hold-down gate at the cradle nose.** Both tapes pass under a lintel between the rolls and the first fin. Three things follow. The tape meets the rack at a fixed height whatever the roll diameter. The pull on the spindle is always forward and down, into its seat, so an open saddle is enough. And because the gate sits 3 mm *above* the tape plane (`gate_rise`), a level pull clears every fin; the sticky side touches down only when the tape is lowered. A gate below the tape plane would lay the tape on every fin by itself, but it would also drag the adhesive across the first fin during the pull. The lintel is a 2 mm flat flared at 50°, so it prints as two 22 mm bridges, one per lane, and then grows.

**D5 — Tapered fins with buttress posts.** A fin is loaded across its layer lines, the weak direction. It is 3.2 mm at the land and 5.2 mm at the root, and each guide post is a column 7.2 mm long at the root that runs past the land into an 8 mm horn. Each post is one lofted solid.

**D6 — Ribbed lands.** Peeling a strip is resisted by the width of the bond, not its length, and a full-width bond on a 19 mm tape can take more force to break than the rack weighs. Each land is three 2.4 mm ribs per lane (`land_ribs`, `land_rib_w`), 38 % of the tape width. This is an estimate, not a measurement: `land_ribs = 0` gives a flat land if strips fall off, fewer or narrower ribs if they cling.

**D7 — An end cap with a tail ledge, one pitch past the last fin.** The two tape tails need somewhere to be stuck down so both hands are free to press and cut. Putting the ledge a full pitch past the last fin means the last fin still yields a full-length strip.

**D8 — One spindle, blind saddle pockets.** A plain 24.6 mm hub for a 25.4 mm core, a 29 mm flange between the rolls with 40° shoulders, standing on end to print. The saddles are 2.8 mm pockets in 4.4 mm walls; the 1.6 mm skin stops the spindle walking out sideways. The slots lean back 25°.

**D9 — Style `none`; chamfers at 50°, not 45°.** As the brief decided. Bed chamfers and the lintel flare are 50° from horizontal because printcheck treats exactly 45° as a float coin-flip.

**D10 — No feet modelled; the underside is flat.** A recess for a stick-on foot is a ceiling over the bed, which printcheck counts as overhang. A flat underside takes 2 mm bumper dots anywhere.

**D11 — `lanes = 1` needs a narrower joint.** The default key is 24 mm at its tip and a one-lane base is 30.8 mm wide. The render stops with an assert that says so; `-D joint_neck=8 -D joint_tip=14` fits.

## Print orientations

- `cradle` — on its floor. The saddle slots lean 25° and the lintel is two 22 mm bridges; nothing else overhangs.
- `spindle` — standing on end. The flange shoulders are 40° from vertical.
- `rack` — on its base, fins up. Nothing overhangs except the socket walls, which lean 10°.
- `end-cap` — on its base.
- `joint-coupon` — both stubs flat on the bed.

## Print settings

- **Material:** PLA.
- **Nozzle / layer:** 0.4 mm / 0.2 mm.
- **Perimeters:** 3.
- **Infill:** 15–20 %.
- **Supports:** none. The gate lintel is meant to be bridged.
- **Order:** the joint coupon first, then the plate.
- **Slicer estimate** (PrusaSlicer bare defaults, the gate's test-slice): cradle 4 h 34 m / 51 g, spindle 48 m / 12 g, rack 6 h 03 m / 76 g each, end cap 1 h 18 m / 18 g, coupon 33 m / 7 g. Ten-fin set: about 232 g and 18 h 45 m at those settings.

## Print this first

`tape-strip-rack-coupon.scad` prints the production key and the production socket as two loose stubs (33 minutes, 7 g). `gate.sh` renders and gates it automatically.

Lower the socket stub onto the key stub. It should drop on under light finger pressure, and lifting the key stub should carry the socket stub.

- Will not go on, or needs force → raise `joint_clear` by 0.05 (0.20 → 0.25 → 0.30) and reprint the coupon.
- Rattles, or the socket stub tilts more than a few degrees → lower `joint_clear` by 0.05.
- Tight only for the last millimetre at the bed → that is first-layer squish; raise `joint_ef` in the Derived block rather than loosening the whole joint.

`./scripts/render.sh tape-strip-rack --sweep joint_clear=0.10:0.30:0.05` prints the ladder in one go.

The spindle is a loose running fit, not a tuned one, but roll cores vary: measure yours and set `core_id` before printing it.

## Fit proofs (what CI renders, never prints)

- `joint-fit` — key in socket, posed as joined: empty. `joint-fit-ctrl` — socket cut at −0.15 mm: interferes (128 facets).
- `spindle-fit` — spindle in its pockets against the whole cradle: empty. `spindle-fit-ctrl` — hub grown 1.2 mm: interferes (1142 facets).
- `roll-fit` — two 62 × 19 mm rolls on a 25.4 mm core, on the spindle in the cradle: empty. `roll-fit-ctrl` — rolls 8 mm larger: interfere with the floor (64 facets).

## Gate evidence (2026-11-21, OpenSCAD 2021.01, PrusaSlicer 2.7)

`./scripts/gate.sh --slice tape-strip-rack` exits 0 in 12 s.

| Part | printcheck | Test-slice |
|---|---|---|
| `cradle` | 100/100 | 4 h 34 m, 50.5 g |
| `spindle` | 100/100 | 48 m, 12.4 g |
| `rack` | 100/100 | 6 h 03 m, 75.5 g |
| `end-cap` | 100/100 | 1 h 18 m, 17.7 g |
| `tape-strip-rack-coupon` | 100/100 (2 bodies, intended) | 33 m, 7.3 g |

Plate: `build/tape-strip-rack-plate.3mf`, 4 separate objects for 4 declared parts.

## Brief audit — measured on the exports, not read from the variables

Sections and bounding boxes taken from the gated STLs with trimesh.

| Brief row | Brief | Measured |
|---|---|---|
| Lanes | 2 | 2 lanes between 3 posts per fin |
| Fins, default assembly | 10 | 5 lands per rack × 2 racks |
| Strip length | 40 | land centres at 20, 60, 100, 140, 180 mm: pitch 40.000 |
| Tape plane above base | ≥ 25 | land top z = 34.000, base top z = 8.000: 26.000 |
| Lane for a 19 mm tape | 19 + clearance | 22.22 mm between posts at the tape plane |
| Clear gap between fins at the top | ≥ 28 | 35.56 mm between posts |
| Core Ø 25.4 | hub must run in it | hub Ø 24.600, 0.800 clear on diameter |
| Roll Ø 62 max | must clear the cradle | `roll-fit` empty; the 8 mm larger control interferes |
| Largest part | ≤ 210 long, ≤ 200 tall | rack 208.02 × 57.20 × 42.00; cradle 58.00 tall |
| Assembled length | about 500 | 86.1 + 200 + 200 + 31 = 517.1 |

## Bugs caught (and what caught them)

- **A dovetail socket on the upright cradle's end face.** Scored 100/100 and would have printed with a drooping lip. Caught by an independent printability review slicing a mock, not by the gate. Led to D2 and D3.
- **Zero-area triangles on the cradle.** Where one piece's edge ended part-way along a coplanar face of another (the floor's top edge under the wall ends, the back wall's top edge across them), the export carried collinear triangles and printcheck took 8 points. Fixed by never letting two pieces share a plane unless one covers the other's edge: the walls stop 0.4 mm short of the floor's back edge, the back wall is set in 0.8 mm, inner pieces start inside the floor and stop inside the walls.
- **Feather edges at the socket mouth.** A bed chamfer on the joint's end face met the socket's flare and left slivers 0.05 mm thick; squaring the lips first left a second sliver between the mouth and the flank. Joint end faces now have no bed chamfer and the squared mouth runs past the flank at every height.

## Session-resume context

- Entry: `tape-strip-rack.scad`. Coupon: `tape-strip-rack-coupon.scad`. Style: none.
- Branch `ccr-8541794c-mwyuwk`; the draft PR closes #1062.
- Nothing has been printed. The first field test should answer, in this order: does the joint coupon fit at 0.20; does a strip stay on a ribbed land through the cut and peel off without lifting the rack; does the lintel bridge cleanly; does the rack need feet on your table.
- CI's render gate uses openscad-nightly with the Manifold backend, which was not available in the build session. Every union here overlaps by real volume for that reason, but the first CI run is the first time this geometry meets Manifold.
- Open, for the owner: whether to publish a functional look-alike of a commercial product (`PM.md`, Open decisions).

## Field test log

_Real prints of this design, newest at the bottom. See templates/FIELD-TEST.md
and docs/print-feedback.md for the convention._

(none yet)
