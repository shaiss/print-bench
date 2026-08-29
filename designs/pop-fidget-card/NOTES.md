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
- Shelf prop angle 70–75° (**now ships ~76–80°** — the v0.2 hinge field fix
  traded ~5–8° of prop for a rigid, grounded hinge neck; see "Hinge field
  fix" below and the Field test log).
- Printer: Bambu/MK4-class, 0.4 mm nozzle, 0.20 mm layers, PLA.

## Key decisions

- **Mechanism sourcing.** The spinner and pop-button geometries are re-hosted
  on the card **without including** the source designs (an include would make
  this a derivative and drag in lineage machinery for what is really a
  clearance-discipline reuse). Values kept verbatim: spinner xy_tol (now 0.21,
  field-bumped +0.01 — see field log) /
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
- **Easel stop = plate-root chamfer corner.** The flap swings out the back;
  nothing external limits it, so the flap's own root geometry is the stop.
  Since v0.3 (below) that stop is the **plate-root chamfer corner** contacting
  the card's window-bottom edge — the tongue relief ramp is gone. Flap
  flat-on-ground + stop ⇒ shelf prop angle = 180° − stop. The stop engages
  ~97–99° ⇒ prop ~76–80°. `fitcheck` proves the swing is FREE at six sampled
  angles 0/25/50/75/90/**92°** (below the ~96° free boundary);
  **`fitcheck_neg` proves the stop EXISTS** (`easel_deploy + easel_overshoot`
  = 110° must interfere) — the negative control is the mechanism's own proof.
- **Hinge field fix (v0.2 — the living-hinge/mid-air failure).** The first
  real print (field log) showed the flap's plate-to-tongue root as *a very
  thin living hinge that printed in mid air*: it cracked at the fold in PLA.
  Measured on the export at the flap-knuckle centreline (x=48): the root
  neck was **0.36 mm thick, floating ~1.8–2.1 mm off the bed** — a flexure
  where a rigid link belongs, printed as an unsupported sagging bridge. Root
  cause: the pivot is elevated (`z_ax = R_k = 3.7`, the Ø7.4 barrel is 3× the
  2.4 card, so it rests on the bed *above* the plate), and the swing reliefs
  compensated by cutting the whole root underside — `root_chamfer = 2.5`
  (> `card_t`, so it removed the full plate thickness at the root edge) and
  `ramp_run = 5.75` (tapered the ramp all the way up into the neck). But the
  fold collision is entirely at the *window-bottom edge* (y ≈ 12), never at
  the neck (y ≈ 21) — proven by sweeping the flap over the card with reliefs
  off: no contact through 96°, first contact only at ~100°, and only in the
  bottom 0.9 mm near the bed. So the neck needs *no* relief. Fix:
  `root_chamfer 2.5 → 0.6` (a modest bottom-corner chamfer that clears the
  0.9 mm-deep collision) and `ramp_run 5.75 → 2.0` (the ramp tapers to zero
  *before* the neck at y ≈ 20.1). Result, re-measured on the export: neck
  **2.15 mm thick, grounded (bottom 0.08 mm off the bed)** — a rigid link, no
  flexure, no mid-air bridge. The cost is ~10° of fold (stop 108° → ~100°),
  i.e. ~5–8° more upright prop (76–80° vs 72°): the plate-root corner *is*
  the fold limiter with this pivot, so reaching 108° requires relieving it,
  and relieving it is what thinned the neck. A rigid hinge that props a few
  degrees steeper beats a flexure that cracks. Config-off is unchanged and
  clean: `with_easel = false` drops the window, knuckles, flap and pin, and
  the card fills solid where the window was.
- **Hinge field fix v0.3 — kill the residual living hinge (owner call).** v0.2
  *grounded* the plate-side neck but only *shortened* the tongue relief ramp
  (`ramp_run 5.75 → 2.0`); it left the ramp cutting `ramp_h = 1.6` deep at the
  tongue root (y ≈ 18.15), so the tongue still had a **~0.8 mm ramped section**
  there — a living-hinge flexure sitting in *series* with the real pin hinge.
  The owner, reprinting, flagged exactly this: *"we have a real hinge; we don't
  need a living hinge too."* Correct — a thin PLA flexure across the fold line
  is the crack-prone part, and it does a job the swivel pin already does. Fix:
  **remove the tongue relief ramp entirely** (`ramp_h`/`ramp_run` deleted). The
  tongue is now a **full-thickness (card_t = 2.4 mm) rigid link**; all folding
  is the pin hinge. Re-proven on the interference sweep (flap ∩ fixed body, the
  Manifold engine): with the ramp gone the flap is **free through 96°**, first
  contacts the plate-root chamfer stop at **97°** (0.006 mm³), firm by 98–99°.
  So the ramp was **vestigial** — the plate-root chamfer corner, not the ramp,
  was always the actual stop (v0.2's own comment admitted "the plate-root
  corner *is* the fold limiter"). Net: same stop (~97–99° vs ~98–104°), same
  prop (~76–80°), a rigid tongue with no thin flexure anywhere. Also nudged the
  embossed **"1" down 1 mm** (`(plate_root+ftop)/2 − 8.5 → − 9.5`) so its base
  sits clear of the fold line — the "1" already cleared the hinge by ~6 mm in
  the mesh, so what read as *the "1" fusing the kickstand* on the v0.1 print was
  the living-hinge blob, now removed; the nudge is cosmetic margin. `easel-open`
  preview pose and the `easel-fold` animation retimed 100° → 96°/95° to track
  the new stop (camera frozen; only the pose angle moved).
- **Flap root castellation.** The main plate's root sits R_k + 0.4 beyond the
  axis with the (now 0.6 mm) bottom-corner chamfer, because a full-width root
  at the hinge line sweeps into the card barrels and webs mid-swing (derived
  by sweep-radius analysis, confirmed by the fitcheck angles). The hinge slot
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
     **(Superseded by the issue #398 lib fix, 2026-08-25: the point now
     faces UP — the old measurement was the module's orientation bug, not a
     property to design around. The retraction stays valid: the tail's
     y-spread (flank corner 0.51·pin_d, bore + `hinge_clear` ≈ ±1.67) is
     mirror-symmetric about the bore axis, so `tongue_root = y_ax + 1.9`
     clears the bore whichever way the point aims. Pin and bore flipped
     together, so the fit and the sweep envelope are unchanged.)**
  3. **The measured envelope (round-3 geometry): free through 104°, first
     stop contact at 108° (0.17 mm³), solid by 116°** — the committed empty
     sweep stayed at 100° with margin because a tessellation-sensitive
     boundary angle is not a stable CI assertion; the prop angle was claimed
     from measurement, not the guard's estimate. **(Superseded by the v0.2
     hinge field fix: envelope now free through ~96°, first contact ~98–100°,
     solid by ~104°; the committed empty sweep terminal dropped to 92°.)**

- **Bubble-shine: crescent → dot (v0.2 field fix).** The rotor tops and bead
  cap carried an engraved *crescent* bubble-highlight (two offset circles).
  A crescent tapers to zero-width horns at its tips; below the nozzle line
  (0.4 mm) the slicer silently drops that material, so on the real print the
  cutout "gets hidden and doesn't work". Replaced with a constant-width
  engraved **dot** (`shine_d = 1.6`, guard `shine_d == 0 || shine_d >= 1.2`,
  0 disables) — a circle has no sub-nozzle region by construction. The
  deterministic lesson: cosmetic engravings must be constant-width; a
  tapering profile (crescent, sharp wedge) is the anti-pattern, and the
  general guard is "the feature must survive a morphological open at one
  nozzle width" — the dot passes trivially; a future geometric min-width
  check (render the feature, erode/dilate, compare) would catch a *new*
  tapering shape the parameter assert can't.
- **Pop-button beam thinned for PLA (v0.2 field fix).** `tog_beam_t 1.5 → 1.3`.
  The bistable snap worked at 1.5 but was too stiff in PLA (field note: "in
  pla needed a bit thinner"; PLA is ~2× PETG modulus and snap force scales
  ~t³, so 1.3 softens it ~35%). Still above the 1.2 mm 3-perimeter floor, and
  thinner *raises* `rise/beam_t` so the ≥ 2.3 bistability guard only gets
  safer. It is a tunable parameter: PETG can return to 1.5.
- **Greeting v2: auto-shorten when named (v0.2 field fix — PM.md B2 decision,
  field-validated).** The named card used the full greeting + name
  ("HAPPY 1st BIRTHDAY, <name>!"), which overran the readable width on the
  real print for a **6-letter** name — the owner hand-shortened it to
  "HAPPY 1st, <name>!" to make it fit. That workaround *is* the fix: the
  named card now auto-uses a short greeting (`greeting_named = "HAPPY 1st"`),
  so "HAPPY 1st, <name>!" holds the full 5.4 mm stroke for names up to ~13
  letters (the unnamed card keeps the full "HAPPY 1st BIRTHDAY!"). The fit
  guard tightened from `line_size ≥ 4.5` to `≥ 5.0` — the old floor passed a
  line the owner couldn't fit (5.32 mm), so the readable floor is now higher
  and the failure message names the two levers (shorten the name, or set
  `greeting_named`). See "Greeting fit" below.

### Greeting fit (v2)

`line_size = min(5.4, (card_w − 16) / line_ems)` with a per-glyph advance
table (`chr_w`); the guard is `line_size ≥ 5.0`. Because dropping "BIRTHDAY"
from the named line frees ~5.8 ems, the named greeting stays pinned at the
5.4 mm cap for realistic names:

| Named line | ems | line_size |
|---|---|---|
| `HAPPY 1st, MARLEY!` (6-letter, field) | 12.2 | 5.4 (cap) |
| `HAPPY 1st, ALEXANDER!` (9-letter) | 14.3 | 5.4 (cap) |
| ~15-letter name | ~19.2 | ~5.0 (floor — the guard's edge) |

The old full-greeting named line (`HAPPY 1st BIRTHDAY, MARLEY!`) measured
18.4 ems → line_size 5.23, which *passed* the old 4.5 guard yet did not fit
on the card in practice — the reason the guard was tightened and the greeting
auto-shortened rather than just re-floored.

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

1. `xy_tol` (0.21): rotor fused → raise; rotor rattles → lower.
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

_Real prints of this design, newest at the bottom. See templates/FIELD-TEST.md
and docs/print-feedback.md for the convention._

### 2026-08-22 — Bambu-class printer (owner), PLA
- **Printed from:** v0.1 (merged PR #343). Two cards printed, one two-tone
  (filament swap at the text layer), personalised via `-D card_name=...` at
  slice time (a 6-letter name).
- **Part(s):** the full card (all four mechanisms), face-up, no supports.
- **Slicer settings:** ~stock 0.20 mm profile · 0.4 nozzle · PLA · ~15 % infill
  · no supports.
- **Result:**
  - **Spinners — great.** Both captive rotors came free and spin. Tolerance
    on the H2C was "just right, could use .005–.01 more." Called out as proof
    that vertically-separated print-in-place layers reliably come apart.
  - **Slider — perfect tolerance.** Bead glides, came free on the first slide.
  - **Easel hinge — FAILED (the big one).** The flap's plate-to-tongue root
    printed as *a very thin living hinge, partly in mid air*, in addition to
    the intended swivel (pin) hinge. PLA living hinges crack where PETG would
    flex — QA that should have been caught before shipping. (Root-caused and
    fixed in v0.2 — see "Hinge field fix" above: the root neck went from a
    0.36 mm floating flexure to a grounded 2.15 mm rigid link.)
  - **Pop button — worked, but stiff in PLA.** Demonstrated the bistable
    snap; would likely have been right in PETG, but in PLA needed a thinner
    beam. (v0.2: `tog_beam_t 1.5 → 1.3`.)
  - **Cap-top bubble-shine — sliced away.** The tiny engraved crescent on a
    knob top got hidden when sliced (sub-nozzle horns) and didn't render —
    a class our deterministic checks should catch. (v0.2: crescent → a
    constant-width dot; guard added.)
  - **Name fit — the full greeting overran.** With "HAPPY 1st BIRTHDAY" +
    the 6-letter name the line didn't fit; the owner hand-shortened it to
    "HAPPY 1st, <name>!" to make it work. Field data: a 5-letter name might
    fit, 6 does not, with the full greeting. (v0.2: named cards auto-shorten
    the greeting; fit guard tightened.)
- **Measured deviations:** spinner `xy_tol` 0.20 slightly tight (owner:
  "+0.005–0.01") → bumped to 0.21. Button beam too stiff in PLA at 1.5 mm →
  1.3 mm. (Slider `slide_tol` 0.25 spot-on — no change.)
- **Carry forward:** the spinner radial clearance runs a touch tight on a
  Bambu-class H2C in PLA (0.20 → 0.21). Not yet promoted to `printer.conf`
  (single data point); revisit if a second print agrees.
