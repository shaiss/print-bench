# pip-planetary — engineering log

## Goal

A print-in-place planetary (epicyclic) gear set — sun, three planets, internal
ring — printed as ONE assembled part, per brief #307: the catalog's first
toothed-gear design (Domain 3 "Gears & rotary" in `docs/advanced-techniques.md`).
Turn the sun's crank; the carrier walks round at **5:1**.

## Given measurements (from the brief)

| Quantity | Value | Source |
|---|---|---|
| Gear module | 2.0 mm | brief (assumed; printable tooth size, 0.4 nozzle) |
| Tooth counts | sun 12, planets 18 ×3, ring 48 | brief (assumed) |
| Reduction ratio | 1 + 48/12 = **5:1** | brief's arithmetic (its "4:1" label mis-evaluated; [amendment on the issue thread](https://github.com/shaiss/print-bench/issues/307#issuecomment-5323928659) keeps the counts, ships 5:1) |
| Mesh backlash | 0.25 mm total | brief (assumed; tuned on coupon) |
| Pin diametral clearance | 0.4 mm | brief 0.4–0.5 range (assumed; tuned on coupon) |
| Face width | 12 mm | brief (assumed) |
| Overall gear envelope | ≈ Ø100 | brief (ring pitch Ø 96) |

## Key decisions

1. **Mechanism = Willis arrangement** (ring fixed, sun input, carrier output):
   ratio = 1 + Zr/Zs = 5:1. Both assembly conditions hold by the counts:
   Zr = Zs + 2·Zp (48 = 12+36) and (Zs+Zr)/N = 60/3 = 20 integer, so three
   planets space at exactly 120° and all three mesh sun and ring simultaneously.
2. **Backlash by tooth-thinning** (BOSL2 `backlash=` = 0.125 per gear = 0.25 in
   the mesh), never center-distance: a planet meshes the sun (outside) and the
   ring (inside) at one fixed 30 mm axis radius, so growing the center distance
   opens one mesh by exactly what it closes the other. Center distance stays
   exactly 30.00. (Amendment 2 on the issue thread.)
3. **Mesh phasing** — the alignment constraint a slider never exercises. With
   gear centers on the line of centers, tooth phases must interleave at BOTH
   meshes of every planet at once. Calibrated against BOSL2's profile origin:
   sun `gear_spin` 15°, planet 10°, ring 0°. Analytic form: sun σ = 15 + 5θ,
   planet π = 10 − (5/3)θ at carrier angle θ; the phase-locus slope −Zs/Zp =
   −2/3 per the external counter-rotating mesh (verified empirically:
   σ=7.5/π=15 clean; σ=7.5/π=5 collides).
4. **Carrier = full disc, below the planets.** The pins rise as supported
   towers from the disc, and every planet's first layer prints 0.4 mm over
   carrier material — never over air (an earlier 3-arm spoke design hung the
   outer tooth bands in air; rejected from the render).
5. **Cavity boring** — the housing's inner wall face sits at the ring's tooth
   ROOTS (r 50.5) above and below the gear stratum; across the stratum itself
   only the tooth cutter carves the wall. Boring at the root radius would
   remove everything the cutter needs to bite, leaving no teeth at all (the
   ring-meshes-air failure — caught by measuring the export, not the render).
6. **BOSL2 center-anchoring** — `spur_gear` anchors at CENTER, so every gear
   body is translated to `z_gear0 + face_w/2`; and the planet bore cut must
   span the full centered band (−face_w/2 … +face_w/2) or the lower half
   keeps a solid core that fuses to the pin. Both are the "silent wrong
   geometry" class the fitcheck gate exists for.
7. **BOSL2 internal radii are named by extent, not tooth feature**: for
   `internal=true`, `root_radius` (46) is the tooth TIPS circle (innermost)
   and `outer_radius` (50.5) is the tooth ROOTS (outermost). Assigning them
   by name intuition swaps the wall face to the tips and the carrier collides
   with the wall band.

## Print orientation

Flat on the base plate, bore axes vertical, exactly as rendered. No supports.
The whole stack prints bottom-up: base → (gap) → carrier disc with pin towers
→ (gap) → gear train + ring teeth → (gap) → lip annulus → crank. All axial
gaps are whole 0.2 mm layers (2 layers = 0.4 mm, the Domain 3 sag limit).

## Print this first

Print `pip-planetary-coupon.scad` — one pocket of the train (sun + one planet
+ the ring segment they engage, as a ~100° wedge) at full production module,
backlash, and clearances. Measured on the gate's test-slice: **~2 h 50 m /
32 g** (the full unit is ~9 h / 103 g), i.e. a third of the full print to
de-risk all of it. The brief's "~20 min" is unachievable at these tooth
counts — the sun and one planet alone outweigh a 20-minute print at module 2
— so the coupon keeps the real gears and drops two planets' worth of structure
instead. [Amendment 3 on the issue thread.](https://github.com/shaiss/print-bench/issues/307)

Tuning steps, in order:

1. **Mesh backlash (`backlash_gear`)** — turn the sun. Stiff or fused mesh →
   raise `backlash_gear` by 0.025 (total mesh backlash +0.05); sloppy, rattly
   mesh → lower it 0.025. Production default 0.125.
2. **Pin clearance (`pin_diam_clear`)** — push a planet sideways and spin it.
   Seized planet → raise 0.1; wobbly/loose → lower 0.1. Production default
   0.4 (diametral, i.e. 0.2 radial).
3. Reprint the coupon after each change; only when both feel right commit to
   the full print.

## Assumptions & deliberate defaults

- Tooth counts 12/18/48 chosen for clean assembly arithmetic, not torque.
- Module 2.0 / face width 12 are printability defaults, not strength-derived.
- Sun input = molded crank arm (the brief's showier default; its open
  question settled from the render, non-blocking as the brief directed).
- Carrier capture = the housing lip over the planet tips (axial, from above)
  — the render chose it over the castellated alternative (brief's open
  question, non-blocking).
- Overall Ø110 (housing wall outside the ring teeth) vs the brief's ≈Ø100 gear
  envelope: the wall is a structural addition around the Ø100 tooth envelope.
- Elephant-foot chamfer on the pin bases: standard mitigation, decided on the
  first coupon print (brief's open question, non-blocking).

## Backlog (v0.2 candidates)

- Herringbone teeth — the brief's named v0.2 upgrade; cannot print PIP without
  splitting the print, out of scope for v0.1.
- Helical gearing, torque-derived module/face width — no load spec exists.

## Field test log
