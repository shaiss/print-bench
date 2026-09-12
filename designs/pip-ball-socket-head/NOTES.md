# NOTES — pip-ball-socket-head

The engineering log. What happened, what was decided, and why — the README is
what a stranger reads, this is what a later session resumes from.

## Goal

A tilting head on a print-in-place ball-and-socket joint (brief #593): a stem
that bolts to a desk or shelf, and a head that comes off the bed with its ball
**captived inside a clamping socket**. The PIP shelf already covers prismatic
sliders (`czs-slider`), hinges (`pip-piano-hinge`), planetary gears
(`pip-planetary`), captive rings (`captive-spinner`) and a screw joint — the
**spherical (3-DOF rotary) joint is the one primitive none of them cover**, and
the hardest honest case: the socket's upper hemisphere is an undercut over the
ball that no orientation removes. Aimed at anyone mounting a webcam, reading
light, mic or sensor at a fixed angle: the printed answer to the ubiquitous
small ball-head mount.

## Given / assumed measurements

| Dimension | Value | Given / assumed |
|---|---|---|
| Ball diameter | 20.0 mm | assumed (design target) |
| Ball–socket XY clearance | 0.20 mm start, coupon-swept | assumed start (doc rule `k_xy·line_w ≈ 0.15–0.25`) |
| Ball–socket Z / break-free gap | whole layers, 0.20–0.40 | given as a rule, value tuned |
| Socket slit width | ≥ 1.2 wall each side, slit a parameter | assumed (repo minimum-wall convention) |
| Payload attachment | ¼″-20 stud, ~12 mm long | assumed (camera standard) |
| Payload the lock must hold | ≤ 250 g at 60 mm lever | assumed (typical webcam 100–200 g) |
| Base mounting | two M4 through-holes in v1 | assumed; shelf-clamp jaw parameterized as the v2 alternative |
| Captive after break-in, holds pose unaided | boolean, fitchecked | given — the product |

## Key decisions

- **D1 — Capture by a rim, not a pinch-cone; the aperture is free to exceed
  the ball.** A throat that pinches below the ball's *local* radius
  interferes with the ball at that height (designed parts must be
  interference-free at every z — only the *whole ball* must fail to pass the
  hole), and a tight bore above the ball kills tilt (the stud sweeps a wide
  cone). So the cavity is four regimes: offset-sphere cup → capture cone
  (≤ 25° from vertical) → **rim** at `capture_depth` = 1.5 inside the ball's
  max radius (the capture) → dome re-opening at 15° to an aperture sized for
  the **tilted stud sweep**, not the ball (Ø21.4 > ball Ø20 — intentional;
  the rim is what captures). Rim clearance to the ball is asserted
  (0.35 mm ≥ clearance + 0.05); the tilt sweep is *measured* by
  `fitcheck_tilt` (the `perspective-coin` `fitcheck_flip` pattern), never
  promised by a pose.
- **D2 — No sacrificial column; the break-in fusion is the cup floor.** The
  ball's first layer sits exactly one layer (0.2 mm) above the cavity floor,
  sags onto it and micro-fuses — the doc's "deliberate low-torque break-in":
  a firm twist shears it. A separate support column under the pole would add
  a scar *and* a second fusion point; the floor's witness mark is hidden at
  the cup's bottom pole where nothing touches. (The brief allowed
  "sacrificial layer / designed-in support"; the geometry made it free.)
- **D3 — Orientation is the clearance decision (doc CC1).** Stem-down. The
  cup's lower hemisphere is then an every-layer-supported bowl; capture cone
  and dome close at ≤ 25° / 15° from vertical; the stud is a vertical
  cylinder; the hex nut pocket opens *down at the bed* (first-layer hex ring,
  zero overhang); the only horizontal ceiling is the 2 mm top annulus around
  the stud aperture, landing on the dome cone. Printed stud-down, the dome
  becomes a bridge over the whole ball — the design forbids it by geometry.
- **D4 — ¼″-20 stud = BOSL2 machine threads** (repo rule: BOSL2 for machine
  threads, printed threads for printed-on-printed fits). `tolerance="1A"`
  (loosest UTS class) plus a tunable `stud_undersize` = 0.15 mm off the major
  diameter, raised in 0.05 steps if a camera body rejects it. **This is the
  style pack's one recorded deviation**: `workshop-utility`'s fastener
  vocabulary is M3; the payload stud is the camera standard, not the family's.
  The base's M4s are the brief's own call, same deviation, same record.
- **D5 — Head-to-base joint: one M4 bolt into a printed hex nut pocket.** The
  pocket opens down at the head's bed (printable as a first-layer ring, zero
  overhang); the base recess leads with a 0.6 chamfer. Hardware is already in
  the brief's assumptions for mounting; the joint adds one bolt + one nut, no
  glue, no inserts. Torque path is the tenon shoulder against the recess
  ceiling, not the bolt.
- **D6 — v1 base = M4 foot plate** (the brief's "one choice, not both").
  Evidence: a plate prints flat with zero tuned fits and mounts to a desk
  edge, a shelf underside or a wall with two M4s; a fixed-width clamp jaw
  hard-codes one shelf dimension and needs its own screw mechanism. The clamp
  jaw stays a parameterized v2 (PM backlog), not scope creep here.
- **D7 — The coupon tests what a thumb can feel; CI tests what it can't.**
  Coupon cells are open-top (no dome, no stud): break-in fusion at the floor,
  capture-cone clearance and rim fit are hand-checkable in a 20-minute print.
  The dome-aperture tilt sweep is not — that is exactly what
  `fitcheck_tilt` measures on every gate run.

## Print settings

- **Orientation:** head stem-down (flare on the bed); base flat. Never
  stud-down (see D3).
- **Material:** PETG for the head (the slit collar is creep-loaded — the
  `pop-fidget-card` field test recorded PLA cracking at a flexing feature);
  PLA fine for the base.
- **Layer height:** 0.2 mm. The break-in fusion and the Z gaps are whole-layer
  numbers; a 0.12 or 0.28 layer shifts them (re-tune on the coupon).
- **Supports:** none inside the joint — ever. An auto-support inside the
  socket welds the joint; that is the exact failure this design exists to
  defeat. The capture cone (≤ 25°) and dome (15°) are designed so no slicer
  support can find a surface to cling to in there. The clamp wings'
  undersides are the one external overhang (printcheck: 350 mm² on the
  head); PETG at 3 perimeters prints them, and a support block under the
  wings alone cannot reach the joint.
- **Infill:** 15–20 % gyroid; perimeters 3 (walls are 2.5 mm ≈ 3× 0.42 line).
- **First motion (break-in):** grip the head, twist the ball firmly — it
  shears the one-layer fusion with a soft crack and then moves freely. Work
  it through its full tilt cone a dozen times. If it will not free, raise
  `ball_xy_clear` 0.05 and reprint the coupon cell, not the head.

### Print this first

`openscad -o coupon.stl designs/pip-ball-socket-head/pip-ball-socket-head-coupon.scad`
(or slice `build/pip-ball-socket-head-coupon.stl` from `gate.sh`). Four cells,
one strip:

1. Cells 1–3 sweep the ball-to-socket clearance: 0.15 / 0.20 / 0.25 mm
   (production = 0.20). Snap-and-twist each ball free; the cell where the ball
   frees with a firm twist and *then* moves without rattle is your printer's
   value — set `ball_xy_clear` to it.
2. Cell 4 is the slit-collar station (production clearance): pinch the wings —
   the ball should lock against a firm twist and release when released. If the
   wings bottom out before it grips, `wing_t` is the knob to raise.

## Session log

- Scaffolded from brief #593 under the SHIP-LOCK contract (claim comment on
  the issue). Geometry, manifests and product page in one session; see the
  contract for what was kept out of scope (two-joint arm, metal clamp screw,
  second base option, payload-plate fallback).
- Iterated to gates-green in 2 gate iterations, telemetry captured per run
  (fail 1 → 0). Iteration 1's only FAIL was the fusecheck manifest naming the
  default assembled render instead of a gated part STL — CI was right to
  refuse it ("a fuse check on an unsliced STL proves nothing"); fixed to
  `pip-ball-socket-head-head.stl`. G2 green at iteration 2: head / base /
  coupon all 92 printcheck, all four fitchecks ok with both negative
  controls interfering as expected, fusecheck 2 (head) / 8 (coupon) bodies
  with the fused control staying 1.
- G4 evidence measured off the exported meshes, not the parameters: ball
  Ø 19.98–19.99 (= 20 at the $fn=96 chord), the coupon clearance sweep is
  real in the mesh (ball-bottom gaps 0.16 / 0.21 / 0.26 over the 8.5 floor
  = the 0.15 / 0.20 / 0.25 cells + tessellation), stud thread 12.0 exactly,
  slit 1.200 exactly (planar faces y = ±0.6, running z 14.3 → 34.7, up
  through the dome per D1's rim capture), capture throat Ø17.00 vs ball
  20.00 (the capture, measured), ring OD 25.40, base 48 × 48 × 8.
- Vision reconciliation, for the next reviewer of `previews/collar-closeup.png`:
  at that camera angle the render can read as a "floating wing" and a "wide
  slit". The connected-component measurement is authoritative — the head is
  2 bodies, the wings fused into the socket body (a detached wing would
  read 3, and fusecheck asserts on the sliced STL every gate run). The
  camera looks down the slit axis: between the wings it sees the 1.2 mm
  slot plus the cavity behind it, not a 3–5 mm gap.
- printcheck caveats recorded honestly in README + Print settings: head and
  coupon each flag ~5 % support-needing surface — the wings' external
  undersides (the interior is answered by angle per D1/D3). The supports
  claim is now scoped to the joint, with the wings disclosed.
- `previews/hero.png` (shots.conf) is CI's to render: this session pushes
  with a user PAT, so ci.yml fires and regen renders + commits the shot on
  the PR branch. Local cameras.conf previews (contact-sheet, tilted-pose,
  collar-closeup) are rendered and committed here.
