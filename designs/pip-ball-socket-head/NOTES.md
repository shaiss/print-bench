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
  cylinder; the M4 nut sits in a side-entry trap with a 1.6 mm floor (the
  bolt pulls the head, Drik R4); the nut-slot roof is a 7.4 mm bridge; the
  only other horizontal ceiling is the 2 mm top annulus around
  the stud aperture, landing on the dome cone. Printed stud-down, the dome
  becomes a bridge over the whole ball — the design forbids it by geometry.
- **D4 — ¼″-20 stud = BOSL2 machine threads** (repo rule: BOSL2 for machine
  threads, printed threads for printed-on-printed fits). `tolerance="1A"`
  (loosest UTS class) plus a tunable `stud_undersize` = 0.15 mm off the major
  diameter, raised in 0.05 steps if a camera body rejects it. **This is the
  style pack's one recorded deviation**: `workshop-utility`'s fastener
  vocabulary is M3; the payload stud is the camera standard, not the family's.
  The base's M4s are the brief's own call, same deviation, same record.
- **D5 — Head-to-base joint: one M4×8 (or ×10) socket-cap into a captured
  M4 nut.** Drik R4: an open-bed hex lets the nut walk toward the bolt, so
  torque clamps nut-to-base and the head floats. Drik R5: a window cube to
  x = +AC/2 at Y = ±AC/2 erased every hex flat and the nut spun. The trap
  is a 1.6 mm floor with Ø4.5 through it, hex pocket, and an AF-wide
  window at −X that **stops at x = 0** so the +X hex half keys the nut.
  Slot 3.8 mm (0.2 mm extra for PETG roof sag). Relief to z=8.5. M4×8
  ends at the nut top at the nominal 0.8 mm seat; M4×10 still 1.7 mm
  under the relief. Lift-by-the-head *and* torque-without-holding-the-nut
  are the checks.
- **D6 — v1 base = M4 foot plate** (the brief's "one choice, not both").
  Evidence: a plate prints flat with zero tuned fits and mounts to a desk
  edge, a shelf underside or a wall with two M4s; a fixed-width clamp jaw
  hard-codes one shelf dimension and needs its own screw mechanism. The clamp
  jaw stays a parameterized v2 (PM backlog), not scope creep here.
- **D7 — The coupon tests what a thumb can feel; CI tests what it can't.**
  Coupon cells are open-top (no dome): break-in fusion at the floor,
  capture-cone clearance and rim fit are hand-checkable. The dome-aperture
  tilt sweep is not — that is exactly what `fitcheck_tilt` measures on every
  gate run. Round-2 honesty: the strip is **not** a 20-minute print. CI's
  slice is 3 h 36 m / 40.1 g vs the head's 1 h 14 m / 12.8 g (four
  production-scale balls). The "print this first" cost story is "know the
  printer before a PETG head," not "this is cheaper than the head." Shrinking
  the cells is PM backlog B4. Round 2 also adds an 8 mm ¼″-20 stub so a
  rejected thread is not a head reprint (Jane R2).

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
- **Seam:** Scarf (or Back) — Aligned lands a ridge on the ball of the same
  order as `ball_xy_clear`.
- **First motion (break-in):** in PETG, lever on the stud (a metal ¼″-20 nut
  on the thread is a spanner point), not the wings; work it firmly through
  the tilt cone. It shears the one-layer fusion with a soft crack and then
  moves. Coupon cells are rigid no-slit rings and read slightly harder than
  the production collar. If it will not free, check gap-closing / flow before
  raising `ball_xy_clear` 0.05.

### Print this first

`openscad -o coupon.stl designs/pip-ball-socket-head/pip-ball-socket-head-coupon.scad`
(or slice `build/pip-ball-socket-head-coupon.stl` from `gate.sh`). Five
stations, one strip, **same PETG and profile as the head**. This gate's slice
is 3 h 36 m / 40.1 g vs the head's 1 h 14 m / 12.8 g — skip
it only when you already know the printer.

1. Cells 1–3 sweep the ball-to-socket clearance: 0.15 / 0.20 / 0.25 mm
   (production = 0.20). Work each ball free; the cell where the ball
   frees and *then* moves without rattle is your printer's value — set
   `ball_xy_clear` to it. If all three weld, check slicer gap-closing / flow
   before raising clearance.
2. Cell 4 is the slit-collar station (production clearance): pinch the wings —
   the ball should lock against a firm twist and release when released. If the
   wings bottom out before it grips, `wing_t` is the knob to raise.
3. Cell 5 is an 8 mm ¼″-20 stub on a 12 mm pad: try it in the camera body
   before committing to the head (`stud_undersize` in 0.05 steps if it
   refuses).

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
  slot plus the cavity behind it, not a 3–5 mm gap. Round 2 keeps that
  camera frozen and adds `collar-oblique` (~30° around Z) plus a caption
  so the page does not ask the first-time viewer to reconstruct this.
- printcheck caveats recorded honestly in README + Print settings: head and
  coupon each flag ~5 % support-needing surface — the wings' external
  undersides (the interior is answered by angle per D1/D3). The supports
  claim is now scoped to the joint, with the wings disclosed.
- `previews/hero.png` (shots.conf) is CI's to render: this session pushes
  with a user PAT, so ci.yml fires and regen renders + commits the shot on
  the PR branch. Local cameras.conf previews (contact-sheet, tilted-pose,
  collar-closeup) are rendered and committed here.
- `/pm` checkpoint against the brief: scope held — the diff is exactly
  head / base / coupon + their manifests, previews and product page; every
  out-of-scope item from the contract is absent (no two-joint arm, no metal
  clamp screw, no second base, no payload-plate fallback); the named fits
  are realized as parameters AND measured off the exports (see above); the
  payload figure stays honest (design target, field-test number). The one
  recorded style deviation remains D4 (¼″-20 + M4 vs the pack's M3
  vocabulary).
- **D8 — stylelift form classification (resolved 2026-10-04).** The 2026-09-12
  run stopped because `stylelift check` filed the Ø20 ball as the head's
  `corner-radius` (dominant 10.01 mm vs family 4 ±35 %). The ball is the
  brief's Must-fit, not a fillet. Detector faults: (1) union-find joined
  every usable fold that merely touched, so the sphere and the ¼″-20 thread
  became one region whose turn blew past the closed-form cap; (2) the 0.35
  form-vs-edge bar used the *assembly's* longest extent, so r=10 on a ~46 mm
  head scored 0.22; (3) after the ball was filed as form, tessellated
  capture-cone/dome fragments still sat in the rounding vocabulary as fake
  8.5 / 13 mm fillets (sweep ~1°). Fix: join folds only when they share a
  facet *and* a radius; judge the 0.35 bar against a continuously-turning
  region's own AABB; drop rounding modes whose sweep is under 20°. Head now
  measures form r=10.02 and corner-radius 5.04 (in-family 4 ±35). Proven by
  `test_a_sphere_on_a_taller_body_is_form_not_a_corner_radius`. Hole-vocabulary
  advisory (hex pocket 8.55 vs family 3.4) is D4, not a fail. Geometry games
  stay refused.
- **Round 2 (Jane + Drik, 2026-10-04, PR #811).** PM triage: honest coupon
  print time (this gate 3 h 36 m vs head 1 h 14 m — D7's "20-minute" claim was
  false); hex-pocket 0.5 mm bed-side lead-in; ¼″-20 stub on the coupon
  (fusecheck 8 → 9); Scarf seam + gap-close troubleshooting; PETG break-in
  via the stud; nut-from-below + wing-clock assembly copy; collar-closeup
  caption plus a new frozen camera `collar-oblique` (~30° around Z — added,
  never moved). Queued: FIELD-TEST cycle count + PETG 24 h creep (B1);
  shrinking coupon cells (B4). Declined this round: cable-hung test as a
  `[hunch]` (rides B1).
- **Jane delayed-sha `8c0cd83` (after R2).** Seam / gap-fill already on the
  page; landed the rest of the cheap set: 0.5 mm tenon bed chamfer (elephant
  foot vs 0.3 mm recess clearance), plate filament-per-object sentence,
  Arachne/gap-fill "won't free at 0.25" line, ±20° is trim. Declined moving
  `collar-closeup` (frozen at R1; companion already added). Queued B5:
  cylindrical tenon for the full recess — today's cone wedges after ~1 mm;
  that rebuild adds height and a camera, not a freeze-move.
- **Drik R3.1 (sha `352bb2ad`).** The rotate_extrude "chamfer" was a V-groove:
  the flare grows to r+0.95z, so the cut's (r, 0.5) apex left a knife-edge
  Ø14 skirt. Replaced with a 0.5 mm 45° cylinder *under* the original flare
  (`tenon_bed_chamfer`); zc() includes it. Coupon support should stay ~4%.
- **Drik R3.2 BLOCK (sha `f6a794b4`).** Three assembly faults, none of them
  the joint: (1) M4×16 vs 4 mm blind pocket + 8 mm plate — bolt jacks;
  (2) mount-then-bolt order, underside is the mount face; (3) base lead-in
  cone inverted, living above the plate. Fix: M4×8 socket-cap, underside
  counterbore, 2.4 mm recess (c'bore + 1.6 mm web), mouth lead-in flipped,
  Ø4.5 relief above the nut pocket, assemble head-to-base first, preview
  seats at `tenon_seat` 0.8 mm. B5 still the cylindrical tenon.
- **Drik R4 BLOCK (sha `826cddcc`).** R3.2 length/order/lead-in landed, and
  walking the M4×8 to the end showed the nut pocket opened toward the bolt:
  torque clamped nut-to-web, head held only by the flare wedge. Side-entry
  nut trap with a 1.6 mm floor; lift-by-the-head is the check. M4×8 still
  the measured length (counterbore floor at 4, nut on the floor at head
  z=1.6 → base 8.8, 8 mm shank ends at the nut top).
- **Drik R5 BLOCK (sha `29a9485a`).** Direction was right; the window cube
  ran to x = +AC/2 at Y = ±AC/2 and swallowed every hex flat, so the nut
  spun in a 8.55 mm slot. Window is now AF-wide (7.4) and stops at x = 0;
  slot 3.8 mm; hardware line is M4×8 or M4×10. Torque-without-holding-the-
  nut plus lift-by-the-head.
