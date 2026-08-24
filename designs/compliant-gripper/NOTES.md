# compliant-gripper — engineering notes

**Tier-3 reference design — fuses all three domains** of
`docs/advanced-techniques.md` into one part that prints assembled and working.
Child 7 of 9 of #204; reuses the landed siblings' recipes rather than
re-deriving them (lineage table at the bottom).

## Goal

A monolithic print-in-place **parallel-jaw** gripper. Each jaw rides a
parallelogram of two leaf flexures, so the grip faces stay mutually parallel
while they translate in Y. A captive push-plunger drives both jaws through
diagonal edge-notches; a pre-buckled arch (the #389 solve) drops its apex tip
into a valley detent on the plunger wing and holds the clamped state with zero
applied force. Push the tab → jaws close in parallel → tip passes the crest and
seats in the valley → held. Pull the tab → tip climbs back over the crest →
flexures spring the jaws open. One piece, no supports, no assembly.

## The fusion (why it's a Tier-3 part)

| Domain | Where it lives here |
|---|---|
| **D1 compliant** | jaw parallelogram leaves (in-plane S-bend) + the pre-buckled detent arch |
| **D3 print-in-place** | the plunger prints captive in its race (walls XY, bridged rail roof, jaw pin-arms over the blade); the detent tip prints captive in the wing band |
| **D2 supports / CC1** | printed FLAT: profile in XY, extruded in Z. Every moving interface is a vertical wall (spread-limited `xy_tol=0.2`) or a horizontal roof gap quantized to whole layers (`z_layers=2` → 0.4 mm) — the CC3 anisotropy, two different numbers |
| **CC3 anisotropy** | same split as above: `xy_tol` ≠ `z_tol`, each limited by its physics |

## The three fused interactions (the brief's acceptance)

The point of the tier is that the techniques **interact** — each row below is
the conflict, its resolution, and the artifact that proves it.

### 1. Flexure orientation vs support-free orientation

**Conflict.** The #1 orientation rule says flexures must flex in-layer (a leaf
bending out-of-plane loads the interlayer bond and delaminates). A gripper's
"natural" pose — jaws up, actuating vertically — puts the leaf bends
out-of-plane *and* hangs the jaws over the bed.

**Resolution.** Print flat: the whole mechanism is one XY profile extruded in
Z. The leaves are thin in Y (2.2 mm) and bend in the XY plane — bending stress
in-layer. The price of flat is that the jaws sweep **horizontally** over the
base, so the base carries a pocket whose floor is 2 roof-gaps below every
sweeping underside (jaw blocks, leaves, plunger floor, pin arms): each moving
body floats `z_tol = 2 × 0.2` over solid material, never printing on air and
never welding (sag-limited, the #387 recipe).

**Proof.** `previews/contact-sheet.png` bottom-iso: the bed face is one solid
footprint. The test-slice gcode contains **zero support-material
extrusions**. printcheck reports the expected PIP signature — 92/100 with a
"8 % needs support" warning that is exactly those 2-layer roof-gap first
layers; the landed #387 captive-spinner scores the same class (92/100, 11 %).
That warning is the cost of print-in-place, not an orientation defect.

### 2. Detent force vs jaw stiffness — the gripper must not unclamp itself

**The trap.** At the clamped seat the leaves are deflected `d_jaw` and push the
plunger backwards through the notch walls with

```
jaw_react = 2 · k_jaw · d_jaw · tan(ramp_ang)  = 3.92 N
```

(k_jaw = 2 leaves in parallel = E·leg_z·leg_t³/leg_l³ = 0.754 N/mm.) If the
detent cannot hold that, the gripper quietly pushes itself open. **The first
geometry failed exactly here**: a 53° hold wall with the tip seated at flank
level — zero arch deflection, so the arch supplied zero seating force, and no
wall angle can hold a drive through a spring that isn't loaded. The drive
(6.31 N with the original stiffer leaves) climbed the wall and popped the
crest. 53° is also below the friction self-lock angle (≈62° at μ = 0.3), so
not even friction saved it.

**The fix — two changes, both load-bearing:**

1. **A preloaded valley seat.** The tooth is no longer a sawtooth; it is a
   ramp → crest → hold-face → **valley** profile. The seated tip rests on the
   valley floor, which holds the arch deflected `seat_u = 2.2` mm, so the arch
   presses the tip against the hold face with R(seat) > 0 before any load
   arrives.
2. **A steep hold face + a rebalanced drive.** The hold face is 80° off
   horizontal (wedge ratio tan80° = 5.67) and the leaves were softened/lengthened
   (leg_z 4.6→3.8, leg_l 50→55) to cut the drive from 6.31 N to 3.92 N.

**The numbers (all echoed by the render, asserted by guards()):**

```
R(u)      = 192·E·I/l³·u  +  4·T(u)·u/l        (two-term conservative model)
T(u)      = E·A·ε(u)/l,  ε(u) = π²(2hu−u²)/4l  (flattening a fixed-end arch
                                                must stretch it — catenary)
R(seat_u = 2.2) = 1.10 N  →  hold = tan(80°)·R = 6.23 N  = 1.59 × jaw_react
R(crest_u = 3.0) = 1.68 N  →  release pull ≈ 0.6·tan(80°)·R(crest) ≈ 5.7 N
```

The R(u) model is deliberately pessimistic (small-deflection bending + catenary,
ignoring root rotational restraint); #389's `f_s·l³/(E·I·h) = 1486.57` brackets
the same arch's peak from above (f_snap = 3.81 N ∈ the brief's 2–4 N band, at
u→h). Even under the pessimistic model the seat holds with 59 % margin — the
guard `tan(hold_ang)·R_seat ≥ 1.25·jaw_react` refuses any parameter set that
loses that margin. The crest sits at 3.0 < arch_rise 3.8, so the detent never
drives the arch through its unstable flat (that would need a follower body the
one-part constraint forbids — the full-flip coupling was declined for that
reason).

**Found on the export (and fixed): the arch wasn't the modeled arch.** The
beam's rise curve fed **world** x into its cosine instead of span-local x, so
the built arch dipped fully at x=60 — 10 mm ahead of `apex_x` where the detent
tip rides — and was skewed, not symmetric. Every formula above (R(u), f_snap,
the bistability ratio) models the symmetric arch, and the **built** apex
region measured rise/t = **1.83**, under the 2.3 bistability bar the guard
exists to hold: as built, the detent "would just spring back". All gates were
green — the guard checks the *parameters*, the render checks watertightness,
nothing compared the two. Measuring the export caught it; the fix is one
parenthesis (`yc(x−x_arch0)`), and the measured contract above now reads
rise 3.800 / t 1.600 = **2.375** on the real mesh.

**Payload interaction.** With a rigid Ø25 rod in, the pins jam the advance at
s ≈ stroke − 0.63 (the jaws stop at rod contact; the channel ends there), so
the **valley is placed at the footprint of that stalled pose** — the tip
reaches the floor *with the payload present*. A seat only reachable empty
would park the tip on the crest and pop straight back.

**Proof.** The guard + echoes above (render-time), the coupon (the tab must
snap over the crest and stay), and the field-test log (force reading on the
full part — a mesh cannot measure newtons).

### 3. Actuator clearance vs flexure deflection path

**Conflict.** The plunger must clear the jaws *while the jaws are sweeping
±4.5 mm in Y* — a static gap that is fine at rest can be invaded mid-motion.

**Resolution.** Every plunger↔jaw interface is derived from the **swept path**,
not the rest pose: the cam notch is the hull of the pin circle swept along the
exact a→b path the pin traces (`notch_2d()`, grown by `pin_r + xy_tol`) — the
same "clip masks derive their oversize from what they must clear" discipline as
`lib/threads-fdm.scad`. The pin arms ride over the blade on a 2-layer roof gap;
the plunger band floats 2 layers over the base top; the race walls bound it in
XY at `xy_tol`. The detent tooth profile is *designed* contact (the moving
interface itself), so its clearance story is the valley floor, not a gap.

**Found on the export (and fixed): the cam was disconnected.** The first
notch hulled the pin circle at `a` with one **2r short of `b`** — a truncated
stadium. With these parameters the truncated cap's deepest point landed
*exactly tangent* to the blade's edge (y = −plunger_w/2): the cut removed
**zero material**, the pin post (y −11…−8) never engaged the plunger at all,
and pushing the tab could not close the jaws. Every gate was green — watertight,
sliced clean, printcheck 92/100, fitcheck "empty" *because* nothing touched,
fusecheck 4 bodies. A kinematic disconnect is invisible to a geometry-only
gate. The fix is the full a→b hull (whose far cap is also the intended stroke
stop), a formula-level guard (`notch opens through the blade edge by > 0.1`),
and a **geometry-level** proof: `drive_mouth` in `ci.fitchecks` renders the
pin's own swept body above the blade edge ∩ plunger and requires it **empty**
— a tangent or short notch leaves solid blade there and the gate fails. The
mouth now measures on the export: cap centre (95.206, −5.000), tangent wall
29.43°, bite 1.7 mm deep.

**Proof.** `ci.fitchecks`: the plunger ∩ (frame + both jaws) renders **empty**
at rest, `drive_mouth` proves the cam mouth exists, and the negative control
(walls grown onto the blade) still interferes — the checks can fail.
`ci.fusecheck`: with the leaf middles dropped, the sliced part separates into
4 bodies (frame+arch, jaw A, jaw B, plunger) — nothing is welded that
shouldn't be, and each jaw's only connection to the frame is its leaf pair.

## The measured contract (G4 — measured on the export, not the variable)

Measured with a stdlib Python vertex probe on the ASCII STL
(`build/compliant-gripper.stl`, the gate's own export — a `linear_extrude`
mesh carries vertices only on the extrusion rings and at profile corners, so
each row probes a known ring: the jaw blocks' z=18 top ring for the pad faces,
the plunger band's z=12.6 ring for the notch, the arch beam's z=11.6 ring for
rise/thickness). Full script output is in the PR's audit table.

| Brief row | Parameter | Measured on export |
|---|---|---|
| Gripped object Ø 25 | `grip_od = 25` | pad faces ±16.500 → open gap **33.000**; clamped gap = 33 − 2×d_jaw = **24.000** = 25 − 2×0.5 preload |
| Jaw travel ≥ 8 | `jaw_travel = 8` | notch b-cap centre (95.206, −5.000) → d_jaw **4.500** → travel 2×(4.5−0.5) = **8.000** |
| Actuator stroke | derived | ramp wall on the export: 5 tangent verts, **29.43°** across the tessellation (design 30°) → stroke = d_jaw/tan30° = **7.794** |
| Detent toggle 2–4 N | `arch_rise/arch_t` | posts cl 33.000 ± 0.800, apex cl 29.200 → rise **3.800**, t **1.600**, ratio **2.375** ≥ 2.3 bistable; f_snap = 3.81 N derived per #389 |
| One piece, zero supports | — | gcode: **0** `;TYPE:Support material` extrusions, `support_material = 0`; fusecheck 4 bodies |

Two of those probes found real defects on the first green build — both are
the "measure the export, not the variable" lesson of issue #37, and both are
recorded under their interaction below: the cam notch that cut **nothing**
(drive disconnected, every gate green) and the arch skewed 10 mm off its tip
(built bistability ratio 1.83, under the 2.3 bar). The `drive_mouth` entry in
`ci.fitchecks` now gates the first class on geometry, not on formula.

## Derivations worth keeping

- **Why the jaws are leaf pairs, not LET joints.** The brief says "LET flexure
  jaws" after #388, but a LET is a *torsion* joint — interdigitated fingers
  twisting a thin strip — and torsion produces relative **rotation** (that is
  how #388 folds its panels). This design's acceptance criterion is jaws that
  **translate without rotating** (parallel grip faces through the full travel),
  and a constant-section leaf parallelogram is the translation-side member of
  the same lamina-emergent family: same discipline reused from #388 — thickness
  `t` as the stiffness knob, flex in-layer by construction, root strain
  budgeted (< 2.5 %) — with the torsion topology swapped for the blade pair the
  kinematics demand.
- **Parallelism.** A parallelogram of two leaves gives pure translation (no
  rotation), so the grip faces stay parallel through the whole 8 mm travel —
  that's why the pads can pre-load a cylinder at 0.5 mm without point-loading.
- **Stroke.** `stroke = d_jaw/tan(ramp_ang)`; ramp 30° is the compromise: the
  cam force ratio (×1.73 grip per unit tab force) and self-return on release
  (the pin slides the 30° wall at μ = 0.3 — anything shallower than ~25°
  friction-locks and the gripper stops self-opening).
- **Notch as edge-notch.** The channel opens onto the blade's side so the pin
  arm can wrap over the blade and drop in — a closed slot would need the arm
  to print *through* the blade.
- **Capture.** The plunger cannot escape: race walls in XY, bridged rail above
  (the part's one deliberate bridge), jaw pin-arms over the blade's nose, race
  front / tab rear as the stroke ends (#387 capture recipe).

## Print this first

`compliant-gripper-coupon.scad` — the production mechanism with the grip zone
shortened (32→16 mm) and **everything else at production values**, leaves
included: the detent hold guard is a force balance, and a shortened leaf is a
stiffer leaf — it would out-drive the detent (the guards refuse it), and the
coupon would prove a fit the real part doesn't have. Print it, work the tab:
fused plunger → raise `xy_tol` 0.05 and reprint; rattles → lower it. The
detent's snap feel reads on this coupon too (same arch, same tooth).

## Print

- PETG (the leaves and the arch are live flexures; PLA tires), 0.2 mm layers,
  0.4 mm nozzle, as modelled (flat), **no supports**, 30–40 % infill.
- First use: work the tab once through full stroke to free the race.

## Status

- Renders clean; gates green through iteration 4 (printcheck 92/100 both
  parts, test-slice zero supports, fitcheck + drive_mouth + negative control,
  fusecheck + control). Telemetry: iterations 1–4 captured; scores flat at 92
  after iteration 1 (the PIP signature — see interaction 1), the middle
  iterations were *correctness* fixes the score cannot see.
- Three defects found and fixed, none visible to a score: the detent that
  couldn't hold (interaction 2, found by the force balance), the arch that
  wasn't the modeled arch (interaction 2, found by measuring the export), and
  the disconnected cam (interaction 3, found the same way — the gates were all
  green on a gripper whose jaws could not close). `drive_mouth` now gates the
  last class on geometry.
- Detent force estimate is model + coupon territory: the field-test log owns
  the real number.

## Lineage (the sibling recipes this reuses, per the brief's "reuse, don't
re-derive")

| Sibling | What this design takes from it |
|---|---|
| #385 orientation discipline (`docs/advanced-techniques.md` CC1/D2) | the flat print: whole mechanism one XY profile in Z, flex in-layer (interaction 1) |
| #387 `captive-spinner` | the PIP clearance split — `xy_tol = 0.2` walls, `z_layers = 2` roof gaps — and the capture recipe (race walls, one bridged rail, ends as stroke stops) |
| #388 `let-folding-panel` | the D1 parameterization discipline: thickness as the knob, in-layer flex, root-strain budget — **not** its torsion topology, which folds; these jaws translate (see Derivations) |
| #389 `bistable-toggle` | the buckled-arch solve: the rise/t ≥ 2.3 bistability bar and the `f_s·l³/(E·I·h)` force estimate (f_snap = 3.81 N) |

