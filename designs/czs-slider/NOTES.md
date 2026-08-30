# czs-slider — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 1 (bistable &
constant-force) fused with Domain 3 (print-in-place kinematics)**. Tier 3
("advanced"). Built to brief **#393** (child 9/9 of the reference-design
catalog #204; the D1+D3 fusion row).

## The name (vs `designs/constant-force-slider/`)

`constant-force-slider` was already taken by an ungated earlier sketch, and the
owner's call on the brief thread (**#393**, comment thread) was to build this
one as **`czs-slider`** (constant-*zero-stiffness*) with the distinction
recorded here. The two are different parts:

- `constant-force-slider/` — a typed-by-feel sketch (arch_t 1.4, arch_rise 6,
  no force solve, no Z-capture — its own NOTES.md says so), never gated, kept
  as history.
- `czs-slider/` — this design: every spring dimension **derived from the
  brief's force targets** via the #389 solve, full captive slide (Z-deck),
  coupons, fitchecks, fusecheck, gated.

## Goal

A one-piece captive slider whose resistive force is **near-constant across its
stroke** — push the knob and it glides at ~2 N instead of fighting a rising
spring — printed in place, support-free, in PETG.

## Given / assumed measurements (brief #393)

| Quantity | Value | Status |
|---|---|---|
| Stroke | 20 mm | assumed (brief default) |
| Plateau force | ~2 N across the flat zone | assumed (brief: "feelable") |
| Ripple over flat zone | ±25% | assumed (brief default) |
| Flat zone | middle 70% of stroke | assumed (brief default) |
| Bistable element | per the #389 solve | derived (below) |
| V-beam | sized to cancel the arch's slope | derived (below) |
| One piece / captive / zero supports | — | given |
| Process | 0.4 mm nozzle, 0.2 mm layers, PETG | given |
| Style | `none` | given (no style.conf) |

## The solve

Every number below is derived from the table above; the `.scad` re-derives
`f_s` from the built parameters and asserts it against the target, so the
solve cannot drift from the geometry (the #37 lesson: a variable restating
itself proves nothing — the assert closes the loop the other way).

**Arch (negative stiffness), by the #389 constants** — fixed-fixed shallow
arch, `I = w·t³/12`, `E = 2000` MPa (PETG):

1. Flat zone = 70% of 20 = 14 mm, centred → `u ∈ [3, 17]`. Snap travel
   `u_tr = 16 mm` (the flat zone + 1 mm shoulders).
2. `u_tr/h = 1.98` → **h = 8.081 mm** mid-rise.
3. **t = 0.82 mm** (h/t = 9.9 ≥ 2.3 bistable with margin; 0.82 = the #389
   production thickness — the value that clears the 0.8 thin-wall floor on a
   *curved* band's normal-ray samples, #389's iteration-3 finding).
4. **w = 6 mm** (the #389 floor w ≥ 3, same value as that solve; doubles as
   the slider's Z height so both springs are one band).
5. `f_s = 2.4 N` chosen → **l = 140.26 mm** from
   `f_s·l³/(E·I·h) = 1486.57` (l/h = 17.4 ≥ 10 ✓).
6. Mean slope over the snap: **k_a = −2·f_s/u_tr = −0.30 N/mm** (linear
   idealization — the force falls +f_s → −f_s between the limit points, the
   zero-net-energy signature of a symmetric bistable).

**V-beam (positive stiffness)**, same two anchor points (genuinely parallel):

7. Leg-angle stiffness `k_v = E·w·t_v³·sin²θ/L³`, θ = leg angle off the stroke
   axis. Apex offset **a₀ = 50 mm** at the relaxed pose (why 50: the chevron
   *geometrically stiffens* as it straightens — sin²θ grows with the apex
   excursion; a₀ = 50 keeps that growth to ~1.4× across the flat zone, the
   sweet spot — see "Ripple" below).
8. **t_v = 3.34 mm** from `k_v(3) + k_v(17) = 2·|k_a|` — matched at the
   flat-zone ENDS, not the middle (also below). k_v(10) = 0.301 N/mm.
9. Working point: the V's relaxed geometry sits at **u_free = 4.33 mm**, so
   `F_flat = f_s + k_v·(u_a − u_free) ≈ 2.0 N` — the plateau *level* is a
   placement of u_free, independent of f_s.

**Sanity**: V-beam leg bending strain ≈ 1.0% over the full stroke (estimate
`1.5·t_v·δ_apex/L²`; PETG yield ~2–3%) — the arch carries the deeper
stress, same band proportions #389 verified.

## The two-element model (predicted force–stroke)

Positive = resisting further advance. F_arch: 0 → +f_s at the limit point
(u = 3), linear to −f_s at u = 19, relaxing to 0 at the stop. F_v:
`∫[u_free→u] k_v du` with k_v(u) from the geometry (the stiffening term —
not a constant). F_sum is what the thumb feels.

| u (mm) | F_arch (N) | F_v (N) | **F_sum (N)** |
|---|---|---|---|
| 0 | 0 | −1.06 | −1.06 |
| 2 | 1.60 | −0.59 | 1.01 |
| **3** | 2.40 | −0.34 | **2.06** |
| 5 | 1.80 | +0.17 | **1.97** |
| 7 | 1.20 | +0.72 | **1.92** |
| 9 | 0.60 | +1.30 | **1.90** |
| 10 | 0.30 | +1.59 | **1.89** |
| 11 | 0.00 | +1.90 | **1.90** |
| 13 | −0.60 | +2.53 | **1.93** |
| 15 | −1.20 | +3.19 | **1.99** |
| **17** | −1.80 | +3.87 | **2.07** |
| 19 | −2.40 | +4.58 | 2.18 |
| 20 | −1.20 | +4.94 | 3.74 |

**Flat zone [3, 17]: mean 1.97 N, ripple ±5%** on the model (brief allowed
±25%). Two designed behaviours outside it: at u = 0 the pair *self-advances*
(−1.06 N) — the V's pre-compression holds the slider against the −Y stop
with a ~1 N preload, so it does not rattle at rest; past u = 17 the arch is
spent and the V alone carries the last 3 mm (2.2 → 3.7 N) — a firm arrival
at the +Y stop, no clatter.

### Ripple — why the ends, not the middle

The chevron's k_v is not constant: it goes 0.25 → 0.35 N/mm across the flat
zone (sin²θ stiffening, +38%). Matching k_v to |k_a| only at mid-stroke
leaves the residual slope negative in the first half and **+0.21 N/mm** in
the second — the plateau ends ~1.4 N high, i.e. ±35% ripple, outside the
brief's ±25%. Matching at the ends makes the residual straddle zero
(−0.05 / +0.05 N/mm), which is where the ±5% model ripple comes from. The
sizing rule lives in the `.scad` assert (`k_v(mid) within 10% of |k_a|`,
checked at 0.30 vs 0.30) and in the comment above `v_t`.

### Model honesty

Three idealizations, all one-directional-safe (they misestimate the *level*
and the *exact* ripple, not the existence of the plateau): the arch's force
between limit points is linearized (true shape is smooth-sinusoidal); k_v is
the small-deflection first-order form; E = 2000 MPa is nominal PETG (batches
±20%). **No digital gate can measure force** — the coupon finds the real
plateau, the FIELD-TEST entry below is the verification path. That split is
the brief's own acceptance wording, and the reason `target_force` is a
parameter with an echo, not an assert.

## Fusion interactions (D1 × D3 — where the two domains touch)

- **One anchor plate.** Both springs anchor into the slider's head (the
  plate spanning x ∈ [−16, 6]) and into the far bar. Parallel means *sharing
  endpoints*, not sharing a postcode — the arch's line is x = −12, the V's
  x = +2, and the arch's full snap sweep (band mirrored through the chord,
  ±8.49 mm) stays 0.61 mm clear of both the V's anchor and the chamber wall.
- **The springs are the retainer.** A monolith: bodies = 1 is *correct* (as
  with #389's fixed-fixed arch) — the flex proof is the travel-sweep
  fitcheck plus the fusecheck's chamber-drop (drop the chamber, the STL must
  fall into 2 bodies: frame + slider).
- **Anisotropic clearances** (#387's CC3): the slide's xy gap
  `k_xy·line_w = 0.45·(1.15·0.4) = 0.207 mm` (vertical wall-to-wall,
  spread-limited) is a *different number* from the roof gap
  `z_layers·layer_h = 2·0.2 = 0.4 mm` (sag-limited, whole layers). One
  global tolerance is the classic PIP bug — tuned to the first it welds the
  roof, tuned to the second it rattles.
- **The deck is the only bridge** — 10.4 mm over the channel (the slider is
  deliberately 10 mm wide to keep it routine). Sag into the 0.4 roof gap is
  the budget the z-derivation already charges for; the coupon's fit cells
  verify it empirically.
- **Break-free first motion** (CC2): the slider micro-welds to the deck's
  first bridge layer and to the walls across 0.207 mm; the first push shears
  it. Expected. The ~2 N plateau is ~10× the shear force of those films.
- **Off-axis stops everywhere** (the doc's fatigue rule): ±X the channel
  walls, then the chamber walls 0.6 mm past the arch's full sweep and past
  the V's fullest apex; +Z the deck; ±Y the body stops. The primary-DOF
  travel never loads a flexure in its weak direction.

## Iteration record (the gate loop)

Three gate iterations to green (telemetry captured per run; records went
fail → pass → pass, i.e. converged, not thrashed):

1. **Fitcheck: 108-facet interference.** The first travel sweep was a swept
   hull of the whole mover at u = 0 and u = stroke — a hull *bridges* the
   arch's concave side, so the swept envelope bit into the arch band where
   the two curves run near-parallel at mid-stroke. Fix: per-feature sweeps
   (each moving feature — head, tongue, knob — hulled between its own two
   poses, unioned) and the chamber built as
   `difference() { frame_2d(false); below_deck_cuts_2d(xy_tol) }`, so the
   cavity is the frame minus the mover's true tolerance-grown envelope.
   fitcheck → 0 facets; fitcheck_neg → 736 (the negative control still
   fires, so the emptiness is measured, not assumed).
2. **Fusecheck: the chamber-drop read 1 body, not 2.** The slider's *rest*
   face sat at zero gap against the stop bar — a designed-touch that the
   printed pose seam-welds. Generalising #387's lesson: **a zero-gap stop
   face is a weld, not a stop.** Fix: `stop_clear = 1` — at the printed
   pose the mover touches nothing but its two designed spring welds, which
   *are* the mechanism. Same discipline in the coupon: its three free
   sliders stand `stop_clear` off their label walls (iteration 1 caught
   them welded — the coupon read 4 bodies, not 7).
3. **Converged.** fusecheck 2 (part) / 7 (coupon) / 1 (the known-fused
   control), printcheck + test-slice green on both STLs.

One more designed-weld fix folded in: the V-leg far anchor initially ended
inside the far bar's cut face — an accidental weld across a clearance, not
an intentional one at an anchor. The leg now ends `0.05 mm` short of
`y_far − v_t/2`, so its only attachment is the anchor it was sized for.

## Known gate warnings (accepted, with reasons)

- **Main part, printcheck 92/100** — WARNING: 291 mm² flagged unbridgeable,
  which is the 10.4 mm capture-deck bridge over the slider channel.
  PrusaSlicer bridges it (the test-slice completes); its ~0.2–0.4 mm sag is
  exactly what the `z_layers = 2` roof-gap budget charges for, and the
  coupon's fit cells verify the post-sag clearance empirically. Accepted:
  the deck *is* the Z-capture; the alternative (a separate lid) breaks the
  one-piece brief line.
- **Coupon, printcheck 76/100** — support 176 mm² (the feeler's chamber
  roof, same class as above), a thin-wall warning at 0.01 mm² under the
  floor (the size-3.2 digit glyphs graze the 0.8 mm floor on a few
  tessellated triangles — cosmetic, the digits are through-cuts, not
  structure; verified legible in the straight-down coupon preview), and 2
  zero-area triangles (the same glyph tessellation; harmless after slicer
  repair).

Slice times on the test-slice: ~2 h 18 / 29.8 g (part), ~2 h 50 / 32.9 g
(coupon), 0.2 mm PETG.

## Print this first

`czs-slider-coupon.scad` — three fit cells (the production channel section,
free sliders) sweeping `k_xy` and a QZS feeler cell. Same process constants
as the production part, so what it prints is what the part gets:

1. **Cells 1/2/3** (k_xy = 0.40/0.45/0.50; cell 2 is production): push each
   slider's knob along its slot. Welded → move up a cell; rattles → down;
   free with a hint of drag → that k_xy for the full print. Carry the tuned
   *k_xy* (not a tuned gap — the clearance stays derived) into the part.
2. **Feeler cell** (the long one): push its knob through the full 12 mm. It
   is a ~9 N plateau (shorter span = firmer, by the l³ law) — what you are
   checking is the *character*: near-constant glide, no rising ramp, no
   snap-through. If it ramps up hard, your E is above the 2000 MPa datum →
   thin the production `v_t` by ~5% and re-derive nothing else; if it snaps
   through (force dips then jumps), the arch is over-driving → drop
   `target_fs` one step (2.4 → 2.2).
3. Then print the part with the tuned `k_xy`.

## Print settings

- **Material:** PETG (live flexures — not PLA; PP or nylon also fine).
- **Orientation:** as modeled — flat, profile on the bed. Every flexure is a
  vertical band bending in the layer plane.
- **Layer height:** 0.20 mm (the z-gap derivation's quantum).
- **Supports:** none. The one bridge is the capture deck (10.4 mm).
- **Perimeters/effective:** walls ≥ 1.2 mm except the springs by design
  (t = 0.82 ≥ 0.8 floor, w = 6).
- **Elephant foot:** compensate ~0.1–0.2 mm — the xy gaps are at z = 0.
- **Bed:** ~200 × 93 mm footprint — any bed with one axis ≥ 210 mm (Prusa
  MK3-class 210 × 250 fits rotated; the default printcheck volume
  250 × 210 × 220 covers it).
- **Time:** ~4–5 h for the part, ~2 h for the coupon.

## Field test log

(to be appended per `templates/FIELD-TEST.md` — the force verification path)

The acceptance the brief names: a FIELD-TEST entry that pushes the printed
slider with a kitchen scale (thumb on the scale, or scale-on-block vs the
knob) and records plateau force and ripple over the middle 70%. Expected on
the model: ~2.0 N ± the E batch error; ripple ±25% is the pass bar.
