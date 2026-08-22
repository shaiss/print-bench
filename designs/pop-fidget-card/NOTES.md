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

- Card 120 × 85 × 2.8 mm landscape, corner r 6, bottom chamfer 0.5.
- Feature height above the face ≤ 8 mm (shelf profile + print time).
- Slider travel ≥ 40 mm (ships 42).
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
  swing is FREE at 0/35/70/104°; **`fitcheck_neg` proves the stop EXISTS**
  (118° must interfere) — the negative control is the mechanism's own proof.
- **Flap root castellation.** The main plate's root sits R_k + 0.4 beyond the
  axis with a 2.5 mm 45° underside chamfer, because a full-width root at the
  hinge line sweeps into the card barrels and webs mid-swing (derived by
  sweep-radius analysis, confirmed by the fitcheck angles). The hinge slot
  this opens is visually filled by the knuckle bar.
- **Name privacy.** `card_name` defaults to "" — committed previews and CI
  renders stay generic ("HAPPY 1st BIRTHDAY!"). The real name is a slice-time
  `-D` override. Per the brief, the family's invitation image and the child's
  name stay OUT of the repo.
- **Multi-part choice:** single entry `.scad`; `part` selects fitchecks only.
  The coupon is `coupon = true` re-layout of the same modules (wrapper file).

## Time budget & drop order

Test-slice (PrusaSlicer, 0.2 mm) is the G4 measure: ≤ 120 min hard, 60 min
target. Drop order from the brief if over: spinner #2 (`spinner_count=1`) →
shorter track (`track_y1`) → shrink card face. The toggle and easel stay.

## Print settings

- Face-up (fidgets up), no supports, no brim; PLA, 0.2 mm layers, 0.4 nozzle.
- First motion after printing: spin both rotors and push the bead firmly once
  (shears the drape/anchor welds); pop the button a few times; fold the easel.

## Print this first

`pop-fidget-card-coupon.scad` — a 66 × 46 tile with one spinner, a short
slider track, and the easel hinge (the three tuned fits; the pop button has no
clearance to tune). Tune in this order, ±0.05 steps:

1. `xy_tol` (0.2): rotor fused → raise; rotor rattles → lower.
2. `slide_tol` (0.25): bead stiff after the first-slide shear → raise.
3. `hinge_clear` (0.4): flap stiff → raise; flap floppy → lower (0.3 floor).

## Field test log

(none yet)
