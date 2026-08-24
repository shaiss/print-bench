# over-center-toggle-clamp — engineering log

## Goal

Brief #285: promote bistable-toggle's buckled-beam physics to a load-carrying
**print-in-place over-center toggle clamp** for bench-top workholding. One
PETG print, no hardware: squeeze a lever, the moving jaw closes on the
workpiece, the linkage passes dead center and self-locks, and a buckled-beam
arch makes the toggle bistable so it stays both closed and open with a
positive snap.

## Given / assumed (from the brief)

| Requirement | Value | Source |
|---|---|---|
| Jaw opening (workpiece thickness) | 0–25 mm | given |
| Jaw depth (Y) | 30 mm | given |
| Holding force | ~30 N | given (PETG flexure sizing target, coupon-verified by hanging weight) |
| Switch (snap-through) force | 8–15 N | given |
| Base mount | two M5 screws at 40 mm centres | given |
| Material | PETG (PP acceptable; PLA excluded) | given |
| Style | none | given |
| Open question: 30 N achievability in PETG | non-blocking; degrade honestly | brief |
| Open question: moving-jaw parallelism through travel | non-blocking | brief |

Assumed: PETG modulus E = 2000 MPa (±20%, `E_mod`), yield ~48 MPa; the flexure
bends **across** roads (flat-printed, in-plane arch) per the fatigue rule in
`docs/advanced-techniques.md`.

## Mechanism architecture (the decisions)

Planar XY mechanism, printed flat in the open pose, all pivots vertical Z
pins. Four moving bodies, all captured at print:

- **base** — plate, fixed jaw, guide rails + capture lips, the arch, lever
  pivot pedestal + pin, two hard-stop posts, two M5 countersunk mounts
- **carrier** — sliding slab under the lips + the moving jaw wall + the P3
  pin tower (the only part that touches the workpiece)
- **lever** — boss on the base pivot, crank arm to P2, handle paddle, and the
  **cam tail** whose flank is carved by the swept arch nub
- **link** — P2→P3, the only rod that converts crank rotation to jaw travel

### Why the cam tail (and not pushing the lever directly)

The arch exerts its spring force perpendicular to its span (±Y), but the
lever only responds to torque about B. A circular-arc flank carved as
`tail − ∪ rotate(−t)·disk(nub(t))` makes contact **tangential by
construction** at every lever angle t in the sweep, and the carve is the
nub's own radius + 0.25 mm film, so the printed pose carries no seam at the
contact. The apex map is linear in t from the first stable state (as printed,
apex y = arch_line_y − arch_rise) at pick-up (θ = 42°) to just past the
second stable state at the closed seat (+0.8 mm preload past state 2).

### Over-center sign (the self-locking direction)

The closed seat is at θ_closed = +5°, i.e. **past** dead center (P2 above the
B→P3 line). A workpiece pushing the moving jaw back (+X on the carrier) pulls
P3 +X, which torques the lever **further into** the closed stop — the load
holds itself; releasing the clamp always requires deliberately lifting the
handle over center. The doc's rule (closed pose a few degrees past center,
hard stops sized to keep the flexure elastic) is honoured by construction and
asserted (`0 < theta_closed < 12`).

### Off-axis overload paths (the brief's showcase concern)

- **Arch, Z-down**: the arch stands directly on the plate (z 7..12), so a
  downward blow on the apex seats the beam on the plate — rigid, no flexure
  involvement. Z-up: the cam tail rides 0.4 mm above the beam — capped.
- **Arch, in-plane**: that is the working direction; stress budget below.
- **Jaw, Y (spread)**: rail walls take it (3 mm walls, 5 mm tall).
- **Jaw, Z-down**: the carrier slab settles 0.4 mm onto the plate, then rigid.
- **Lever over-travel**: both stops seat the paddle on Ø6 posts before the
  arch map exceeds its elastic schedule (max deflection = state 2 + 0.8 mm).

## PRBM derivation (docs/advanced-techniques.md)

`I = w·t³/12 = 5·1.2³/12 = 0.72 mm⁴`; bistability needs `rise/t = 3/1.2 =
2.5 ≥ 2.3` ✓ (asserted).

- **f_snap** = 1486.57·E·I·h/l³ = 1486.57·2000·0.72·3/85³ ≈ **10.5 N**
- **u_travel** = 1.98·h = **5.94 mm** apex travel between states
- **Switch force at the handle rim** = f_snap · arm_flank / handle_r_out
  = 10.5 · 43.1 / 33 ≈ **13.7 N** (mid-band of the 8–15 N brief; asserted)
- **σ_max** ≈ 1.3 · E·(t/2)·κ_state1 = 1.3·2000·0.6·(2π²·3/85²) ≈
  **12.8 MPa**, where the 1.3 covers the +0.8 mm preload overshoot past
  state 2 at the closed seat. PETG yield ~48 MPa → ~26% utilisation;
  fatigue rule (bending across roads) satisfied by the flat-printed arch.

The 30 N holding-force row is **not** carried by the arch — it is carried by
the linkage geometry (self-locking) and reacted at the closed stop post; the
arch only supplies preload (a few N at the flank). That is the honest split:
the brief's 30 N is a structural budget on walls/pins/posts (all < 8 MPa at
30 N), while the arch sets the 8–15 N switch feel. Coupon measures f_snap.

## Linkage solve (closed form)

Link has one length L between P2 (crank at angle t) and P3 (carrier, X-only
motion). Requiring the same L at θ_closed (face on the fixed jaw) and
θ_open (gap = 25 mm) gives, with `q = p3_x − crank_r·cosθ`,
`s = crank_r·sinθ`:

```
B_x = [(q_o² + s_o²) − (q_c² + s_c²)] / (2 (q_o − q_c))   →  −12.77
L    = sqrt((q_c − B_x)² + s_c²)                           →  47.10
```

Echoed by the .scad (`[over-center]` lines) together with the closure
identity `face_at(θ_open) − face_at(θ_closed) = 25.000` (asserted to 1e-6).
crank R = 45, θ_closed = 5°, θ_open = 44.8°, p3 offset 13 mm behind the face.

## Z stack (films are `pip_z = 0.4` = 2 layers at 0.2; the lever clears the
rail tops so nothing needs notching)

| Layer | Z | Notes |
|---|---|---|
| plate | 0–7 | M5 countersunk mounts at (−26, 0) and (14, 0) — 40 apart |
| rails + lips | 7–12 | lips (10.6–12) only x ≤ 60.7: past that the jaw wall travels |
| carrier slab | 7.4–10.2 | 0.4 above plate, 0.4 under lips |
| arch beam | 7–12 | stands ON the plate (no bridge); w = 5 in Z |
| nub | 11–15 | rooted 1 mm into the beam, engaged by the flank |
| lever band | 12.4–16.4 | clears rails/arch tops by 0.4 everywhere |
| link band | 16.8–20.8 | 0.4 above the lever; over rails by 4.8 |
| pin heads | +1.5 cones | one 0.4 gap above what each traps |
| jaw walls | 7.4–27 | 20 mm of face above the plate top |

Pins: Ø5 through Ø5.5 bores (0.25 radial film), bosses Ø16/eyes Ø13, heads
Ø5→Ø8 45° cones (self-supporting) that overhang the bore rims — captured.

The carrier slab is 2.8 mm thick (rails topped at 12 to let the lever overfly
them without notches). At 30 N clamp that is ~0.4 MPa shear and ~8 MPa
bending at the wall root — fine in PETG; trade recorded here, `carrier` slab
length and the rail stack are parameters if a field test wants it stouter.

## Print this first

`over-center-toggle-clamp-coupon.scad` — the brief's force-measuring
artifact: the **production arch** between two M5-anchored posts with a pull
tab on the apex. Bolt the posts to anything rigid with the tab hanging DOWN,
hang weight on the tab hole until the beam snaps through: that weight is
f_snap (~10.5 N predicted ≈ 1.05 kg). The clamp's switch force is that
weight × arm_flank / handle_r_out (43.1/33 ≈ 1.31×). If your snap weight is
> ~35% off, your PETG modulus differs — tune `E_mod` (or `arch_rise`) and
re-derive, don't eyeball the geometry.

Second coupon function: if the coupon's beam fuses to its posts or snaps
brittle, drop `pip`-adjacent params — no, the coupon has no films; a fused
coupon means over-extrusion: check flow before printing the clamp. The
clamp's own films are checked deterministically by `ci.fusecheck`.

## Print pose & orientation

Everything prints flat as rendered (plate down, open pose). No supports:
the only bridges are the lever band over the arch/rails (0.4 mm films, PIP
standard), the link's 47 mm span at z 16.8 (PETG bridges this fine; sag
lands in a 4.8 mm clearance — inspect), and the lips' leading 2 mm. Bottom
edges of the plate get a 0.6 mm chamfer via `rounded_box`.

## Gate round 1 — two real defects the fusecheck control caught (fixed)

The first `gate.sh --slice` run failed on the fusecheck **control**
(`fused` read 2 bodies, not 1) — and chasing it exposed two real geometry
defects, both invisible to printcheck (a disconnected shell is only an INFO
"multiple bodies" there, and a weld is by definition watertight):

1. **Handle paddle was an island.** `annulus_sector(handle_r_in=18 …)` never
   reached the boss (r = 8) and shares no angular range with the cam tail, so
   the 2D lever profile was two disjoint regions — the exported "lever" was
   really lever + a floating 68-facet paddle. Fix: `handle_r_in = 6` (same
   inner radius as the cam tail, 2 mm inside the boss rim). The seating
   geometry is untouched: the stop posts meet the paddle at its *outer*
   angular edges, which the inner radius never touches.
2. **The printed pose was never carved — tail welded to the nub.** The cam
   carve loop ran `t = [theta_closed : 1 : theta_engage]`, but the lever is
   *printed* at `theta_open` = pick-up + `engage_free`; the pose the printer
   actually builds had no cavity for the nub, and `apex_y_at` extrapolated
   linearly past pick-up (−31.5) instead of holding the state-1 apex (−31).
   The tail was fused into the base through ~2.6 mm of embedded nub: the
   printed clamp would have been one immovable lump. Fix: clamp the map above
   pick-up (the unloaded arch sits in state 1) and carve through
   `theta_open` itself at 0.5° steps across the free window, so the printed
   pose carries the designed 0.25 mm film with no seam.

The manifest changed with them: the over-large `flexure` AABB (which was
*masking* defect 2 by deleting the weld zone before counting, and broke the
control by severing the fused monolith's handle lobe) is gone — nothing here
is joined through a flexure, so the raw shell count is the truth — and the
assert tightened from ≥ 4 to the true count, **7 shells** (base, carrier,
lever, link + three trapped pin heads; the head cones ride one `pip_z` film
above what they retain). The `fused` control now also interferes the cam carve
0.3 mm (`eff_cam = -0.3`) so the known-fused weld is a guaranteed overlap,
not a curved-surface coincidence handed to CGAL.

## Deferred / out of scope (per the contract)

- Box-lid variant (clamping a lid down with two clamps) — noted here only;
  needs a brief of its own if wanted.
- Look/styling: brief says style `none`.
- PLA qualification: excluded by the brief (fatigue across layer lines).
- Parallelism of the moving jaw face through travel: the linkage keeps the
  jaw wall parallel to the fixed face at both ends of travel by construction
  (pure X translation); mid-travel is also pure X (the carrier cannot
  rotate — rails + lips). Open question resolved geometrically.
