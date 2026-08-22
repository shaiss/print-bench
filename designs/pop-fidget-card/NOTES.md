# pop-fidget-card — engineering notes

## Goal

A print-in-place 1st-birthday keepsake card (brief: issue #342) themed on a
bubble/"POP" party motif — built for the **parents**, who keep fidgeting with
it after the party. Flat landscape card, displays on a shelf via a punched
easel flap, with four working fidgets printed in place on its face. Hard
constraint: test-slice under 2 h; target 60 min on a fast modern printer.

## Given / assumed measurements

Everything is **assumed** (stated defaults from the brief; nothing external
constrains the card — resize freely against the slice clock):

- Card 112 × 80 × 2.4 mm landscape, corner r 6, bottom chamfer 0.5 (brief
  said 120 × 85 × 2.8 assumed; slimmed one step against the slice clock per
  the brief's own "resize freely" — see Time budget below).
- Feature height above the face ≤ 8 mm (shelf profile + print time).
- Slider travel ≥ 40 mm (ships 40: `track_y1 − track_y0` = 58 − 18).
- Shelf prop angle 70–75° (ships ~72°, set by the easel's rotation stop).
- Printer: Bambu/MK4-class, 0.4 mm nozzle, 0.20 mm layers, PLA.

## Key decisions

- **Mechanism sourcing.** The spinner and pop-button geometries are re-hosted
  on the card **without including** the source designs (an include would make
  this a derivative and drag in lineage machinery for what is really a
  clearance-discipline reuse). Values kept verbatim: spinner xy_tol 0.2 /
  z gaps in whole layers / 45° cone cap (captive-spinner, CC3+CC2); arch
  rise/t ≥ 2.3 bistability floor (bistable-toggle). The easel hinge DOES
  consume `lib/print-in-place.scad` directly (`pip_hinge`/`pip_hinge_pin` —
  the offset-teardrop bore).
- **Slider ≠ lib rail stack.** The brief sketched the slider on the lib's
  castellated rail clearances. Measured against the card: the rail stack needs
  `pip_rail_h()` ≈ 5.7 mm of wall above its floor — hosted on a 2.8 mm card
  that is a 5.7 mm fence on the face, over the height budget and ugly. Shipped
  instead as a **linear captive spinner**: an under-card channel (open to the
  bed) with a 45° hulled roof narrowing to the face slot, capturing a mushroom
  bead's foot. Same CC3 anisotropy: radial slide fit 0.25/side (spread-
  limited), axial gaps in whole layers (sag-limited). Engagement =
  (ch_w − slot_w)/2 − foot_side_clear = 1.5 mm/side, guarded ≥ 1.2.
- **No sacrificial membranes anywhere** (brief assumed some): every through-
  cut body — flap, arch, bead foot — prints as a **bed-anchored island**, and
  the one roof (the slider channel) is 45° self-supporting by construction
  (hull of channel-width and slot-width stadium slabs, ends included). A
  membrane protects a bridge over a gap; this design has no such bridge.
- **Bead anchor nib (CC2).** The bead is otherwise a free body on a Ø9 bed
  patch carrying an 8 mm mushroom — printable but bump-sensitive. One 0.8 ×
  0.3 mm breakaway nib ties the foot to the channel end wall: the deliberate
  weak fusion you shear on the first slide, exactly the captive-spinner's
  break-free move. It is drawn OUTSIDE the fitcheck bodies as a declared weld,
  so the clearance proof stays honest.
- **Easel stop = root relief ramp.** The flap swings out the back; nothing
  external limits it, so the flap's own root geometry is the stop: the hinge
  tongue's underside relief ramp (ramp_h/ramp_run) contacts the card's
  window-bottom edge at the stop angle. Flap flat-on-ground + stop ⇒ shelf
  prop angle = 180° − stop ≈ 72° (brief band 70–75). `fitcheck` proves the
  swing is FREE at six sampled angles 0/25/50/75/90/100° (4° margin below
  the measured 104° free boundary); **`fitcheck_neg` proves the stop
  EXISTS** (118° must interfere) — the negative control is the mechanism's
  own proof.
- **Flap root castellation.** The main plate's root sits R_k + 0.4 beyond the
  axis with a 2.5 mm 45° underside chamfer, because a full-width root at the
  hinge line sweeps into the card barrels and webs mid-swing (derived by
  sweep-radius analysis, confirmed by the fitcheck angles). The hinge slot
  this opens is visually filled by the knuckle bar.
- **Per-mechanism fit checks (post-signoff round).** `fitcheck`/`fitcheck_neg`
  proved only the easel; the spinner and slider clearances rested on asserts,
  and a formula that asserts itself proves nothing about the built mesh
  (issue #37) — the sweep above found real emboss-into-rotor interference
  that no guard fired on. `fitcheck_spin` / `fitcheck_slide` now intersect
  each rotor and the weld-free bead against the whole fixed body in CI, each
  with a deliberately-broken `_neg` falsifier (rotor raised past its axial
  float; bead shoved past both side gaps).
- **Name privacy.** `card_name` defaults to "" — committed previews and CI
  renders stay generic ("HAPPY 1st BIRTHDAY!"). The real name is a slice-time
  `-D` override. Per the brief, the family's invitation image and the child's
  name stay OUT of the repo.
- **Multi-part choice:** single entry `.scad`; `part` selects fitchecks only.
  The coupon is `coupon = true` re-layout of the same modules (wrapper file).
- **Pin end inset (round 2).** `hinge_len − 0.6` centered put the pin's end
  faces EXACTLY coplanar with the outer barrel end faces (both reduce to
  `hx0 + 0.3`) — a kiss contact CGAL coin-flips (the coupon fused it, the
  card didn't) and Manifold exports as a bad shell: CI's first run scored
  both parts 59/100 with a watertightness critical. Pin is now
  `hinge_len − 1.6` (0.5 real gap past each barrel face); every emboss/boss
  bury was also deepened from 0.01 to ≥ 0.2 for the same sliver reason.
- **Layout is edge-derived** (round 2): track/toggle/spinner-2/easel window
  positions are expressions of `card_w`/`card_h`, so the face can shrink
  against the slice clock as one knob without re-placing every feature.
- **The pairwise interference matrix (round 3).** CI's fitcheck reported 400
  facets of interference that local CGAL sweeps could not localize in
  reasonable time. Method that worked: export each body once
  (`part="body_*"`), then compute every pairwise boolean intersection in
  Python with trimesh + manifold3d — the same engine as CI's nightly gate —
  rotating the flap about the hinge axis in Python (seconds per angle vs
  minutes per CGAL probe). Findings, all confirmed by bounding box:
  1. **"POP!" at size 20 is ~64 mm wide, not the ~50 the flat 0.62-em factor
     predicted** — the "!" landed under spinner 2's rotor, whose float gap
     (0.4 mm) is less than the emboss height (0.8 mm). Glyph widths now come
     from a per-glyph advance table, POP! dropped to size 17, and the matrix
     is the verifier, not the estimate.
  2. **`teardrop_hole`'s point faces DOWN in this hinge's frame** (measured
     on the export: pin tail to `z_ax − 0.8·pin_d`, not the circle bottom).
     Pin and bore agree (both built from the same profile, so the joint is
     fine), but the flap tongue was built to plate height straight under the
     tail. Tongue root retracted to `y_ax + 1.9`, outside the tail envelope;
     the flap web carries the plate-to-barrel connection.
  3. **The measured envelope (round-3 geometry): free through 104°, first
     stop contact at 108° (0.17 mm³), solid by 116°** — the committed empty
     sweep stays at 100° with margin because a tessellation-sensitive
     boundary angle is not a stable CI assertion; the prop angle is claimed
     from measurement, not the guard's estimate.

## Time budget & drop order

The brief's cap is "under 2 hours on a stock profile" of a **Bambu/MK4-class
machine**. Two meters, both reported:

- **Gate meter** (surfaced by `gate.sh --slice`): PrusaSlicer with bare CLI
  defaults — no real printer's stock profile, and ~2.5–3× slower than one.
  CI's first run read 2 h 54 m at 120 × 85 × 2.8; the round-2 slimming
  (112 × 80 × 2.4) exists to pull this number down.
- **Brief meter** (G4's hard cap): the same STL sliced at MK4-class stock
  speeds (perimeter/infill/travel overrides recorded in the PR) — this is
  the "stock profile" the brief names, and must be ≤ 120 min (target 60).

Drop order from the brief if the brief meter busts: spinner #2
(`spinner_count=1`) → shorter track (`track_y1`) → shrink card face further.
The toggle and easel stay. Slice data, not vibes, picks the step — and the
sweep below is that data.

### The 60-minute question, measured (post-signoff sweep)

An 8-config sweep — every config sliced with the same MK4-stock flags on one
machine, every size change verified with the pairwise manifold matrix, one
baseline control re-slice to normalise the harness (this box's slicer reads
~7 % above the PR's canonical meter; ratios below are harness-internal):

| Config | Time | Clean? |
|---|---|---|
| baseline 112 × 80, 2 spinners, 15 % | 1 h 24 m | ✓ (control) |
| 10 % infill | 1 h 23 m | ✓ — infill is nearly free already (plate is skins) |
| `spinner_count=1` | 1 h 13 m | ✓ — **the one lever that pays: −11 min** |
| `spinner_count=1` + 10 % | 1 h 12 m | ✓ — the measured floor, ≈ 67 min canonical |
| 108 × 78 | 1 h 22 m | ✓ — size barely pays (−2 min) |
| 104 × 74 | — | ✗ POP! emboss into rotor 1 (0.45 mm³) AND rotor 2 (5.5 mm³) |
| 100 × 70 | — | ✗ worse (5.8 + 11.6 mm³ — the rendered "POP!" is 52.7 mm wide, wider than the advance table predicts) |
| `card_t=2.2` | — | ✗ guard-refused (slot-wall assert), as designed |

Verdict: **the 60-minute bonus is not reachable on the brief's 0.2 mm stock
profile without changing the card's content.** The face-size lever dies at
the POP!-vs-spinner-1 collision (clean at `card_h=78`, colliding by 74 —
POP! sits at `[16, card_h−24]` while spinner 1 is fixed at `[20, 40]`, so
shrinking the face walks the headline into the rotor), and size barely moves
the meter anyway. Nearest honest fast config: `spinner_count=1` at ~67 min.
No assert covers the emboss-vs-rotor class — which is why `fitcheck_spin`
(below) now measures it in CI. The collision numbers also feed the
greeting-line-v2 open decision in PM.md.

## Print settings

- Face-up (fidgets up), no supports, no brim; PLA, 0.2 mm layers, 0.4 nozzle.
- First motion after printing: spin both rotors and push the bead firmly once
  (shears the drape/anchor welds); pop the button a few times; fold the easel.

## Print this first

`pop-fidget-card-coupon.scad` — a 72 × 56 tile with **all four mechanisms**:
one spinner, a short slider track, the easel hinge, and the pop button (Drik
round: the button has no clearance to tune, but *feel isn't clearance* — the
arch lives near its bistability floor, and a fat first layer can turn the
snap mushy; the coupon is where that surfaces). Tune in this order, ±0.05
steps:

1. `xy_tol` (0.2): rotor fused → raise; rotor rattles → lower.
2. `slide_tol` (0.25): bead stiff after the first-slide shear → raise.
3. `hinge_clear` (0.4): flap stiff → raise; flap floppy → lower (0.3 floor).
4. Button feel (no parameter): pop it a few times — a crisp two-state click
   is right; mushy or single-stable means first-layer squish widened the
   arch — drop first-layer flow/width a step and reprint the coupon.

The card's square side edges are intentional: at 2.4 mm plate thickness a
side chamfer buys nothing a thumb can feel and costs face area.

The coupon ships no committed preview, also intentionally: it is a utility
tile, not a product — the card's previews show every mechanism the tile
carries, and a preview set would double the regen cost of a part whose whole
job is to be printed, tuned and recycled.

The easel dwelling at its stop for months is a considered non-issue (Drik
round 3 hunch, answered) — by reasoning, not yet by test: unlike the button
— a sprung member storing bending strain in both states — the flap at its
stop is a rigid body against a rigid ramp, and the ~24 g card puts
micro-scale contact stress on the ramp, little for PLA creep to work with.
The fit checks prove clearance and the stop, not long-term angle retention;
the dwell claim stays an engineering assumption until a shelf-months
FIELD-TEST entry speaks. Expected worst case if it is wrong: the lean eases
a degree or two, cosmetically, and the flap re-seats on the next fold.

## Field test log

(none yet)
