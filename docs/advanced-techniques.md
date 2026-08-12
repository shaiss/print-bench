# Advanced FDM design techniques

This is a **design-expertise reference** — the *why* beneath the design rules, and
the advanced techniques that let you design **around** a constraint instead of
merely obeying it. It is deliberately not a rules list: `lib/print-in-place.scad`,
`lib/threads-fdm.scad`, `lib/printability.scad` and `printer-conf.scad` already
encode the rules and gate them. This doc captures the *technique* layer so a
design session (human or agent) can reach for a maneuver by name.

It is a research synthesis with cited primary sources. Vendor-blog numbers are
flagged as calibration starting points, not constants — the honest provenance is
in [Sources & provenance](#sources--provenance) at the end.

Companion work: the flexure library this doc argues for is tracked in
**[#202](https://github.com/shaiss/print-bench/issues/202)**; the frontier
(metamaterials / 4D) is parked as a research spike in
**[#201](https://github.com/shaiss/print-bench/issues/201)**.

---

## The one principle

Every "rule" is a **shadow of a physical process**, and advanced technique is
reshaping the geometry so the process stops mattering:

- *"Overhangs fail past 45°"* → each layer must overlap the one below by ~half a
  bead. **Reshape:** make it a **bridge** (tension, anchored both ends) instead of
  a cantilever, and near-flat spans print.
- *"Print-in-place needs ~0.3 mm clearance"* → the gap is closed by three
  separable mechanisms (bead spread in XY, sag on a Z-roof, ooze). **Reshape:**
  **orient** so a sag-limited roof becomes a spread-limited wall, and the gap can
  roughly halve.
- *"Hinges wear and rattle"* → a pin-in-bore joint has a clearance you must tune
  and can never make silent. **Reshape:** use a **flexure** with zero clearance,
  and wear, rattle, assembly and backlash all evaporate.

Hold the process and the number becomes a *derivation*, not folklore — the same
instinct as `printer-conf.scad`'s `printer_fit(nominal)`, generalized to every
mechanism family.

---

## Four cross-cutting techniques

These recur across every domain below; they are the transferable moves.

1. **Orientation is the master variable.** The single decision that appears
   everywhere: in supports it turns an overhang into a bridge or a flat bed; in
   print-in-place it turns a sag-limited gap (~0.35 mm) into a spread-limited one
   (tight at ~0.15 mm); in flexures it sets fatigue life (flex axis **parallel**
   to layers, or the beam delaminates on cycle one). *Orient first, then dimension
   locally* — the DFAM ordering.
2. **Design the thing you intend to break.** Sacrificial membranes, breakaway
   supports with a one-layer interface gap and a break notch, the "break-free
   first motion" that shears a print-in-place bearing's micro-fused race — all one
   idea: a deliberate weak feature that serves the print, then yields. A design
   primitive, not a workaround.
3. **Derive clearance from process constants, never hardcode.**
   `xy_gap = max(clear, line_width)`; `z_gap = ceil(clear / layer_h) · layer_h`
   (snap to integer layers so the gap's floor and roof land on real layer
   boundaries). **Anisotropy is the key insight: separate `xy_tol` from `z_tol`**
   — they are governed by different physics (spread vs sag). A single global `tol`
   is the hidden bug.
4. **Grow profiles by true offset, not scale.** Scaling a teardrop bore leaves its
   45° flank planes coincident with the pin's and welds the print; only
   `offset(r=clear)` opens a real gap along each edge normal. Generalizes to any
   clearance on a faceted profile. (`lib/print-in-place.scad`'s `pip_hinge`
   already documents this for one case.)

---

## Domain 1 — Compliant mechanisms

Replace pin joints, springs and latches with monolithic elastic elements: zero
clearance, zero assembly, no rattle. This is the deepest lever, because it makes
the entire clearance problem of Domain 3 disappear.

### Pseudo-Rigid-Body Model (PRBM) — the design theory

The PRBM (Howell & Midha) replaces a flexible beam with **rigid links joined by a
pin and a torsional spring**, so all rigid-linkage math applies to a flexure.

- **Characteristic radius factor γ** locates the equivalent pin. End-force-loaded
  cantilever: γ ≈ **0.85** (arc within ~0.5% of the true path over large
  deflection).
- **Equivalent spring:** `K = γ · Kθ · (E·I / L)`, with the stiffness coefficient
  Kθ ≈ **2.65** (2-D end-force case).
- **Small-length flexural pivot (SLFP)** — the clean, dominant case for FDM: a
  short thin segment between two stiff bodies. γ → 0.5 and stiffness collapses to
  **`K = E·I / L`**, with `I = w·t³/12` (t = thickness in the bending direction).
  Root stress for a pure-moment SLFP: **`σ_max ≈ E·t·θ / (2L)`** — stress scales
  with `t/L`, so *thinner + longer lowers stress for the same rotation*, while
  stiffness scales with `t³`. Thickness `t` is the highest-leverage knob.

### Flexure joint families

| Joint | Range of motion | Off-axis stiffness | When to use |
|---|---|---|---|
| Small-length flexural pivot | low–med | low | simplest; center-of-rotation drifts under load |
| Notch / living hinge | high (1 axis) | very low | cheap, prints flat; poor center, high root stress |
| Cross-axis flexure pivot | up to ~85° | good in tension, **weak in compression** | near-fixed virtual center |
| Cartwheel / butterfly pivot | med–high | better than cross-axis | symmetric variants reduce center shift |
| **LET (lamina-emergent torsional)** | very high angular | low (by design) | **flat-print, ideal for FDM** |
| Ortho-planar / lamina-emergent spring | large out-of-plane | tuned | print flat, deflect normal to sheet |

The universal trade: **range of motion vs off-axis stiffness vs stress.**
Cross-pivots buy a stable virtual center but buckle in compression. Compound
(series/parallel) arrays raise off-axis stiffness and cut center-shift
independently of primary ROM. **LET joints** are the best FDM match: alternating
torsion bars and bending segments printed flat, most compliance coming from
torsion of thin bars, so large angular ROM with deliberately low off-axis
stiffness; add rows to tune (series = softer, parallel = stiffer).

### Bistable & constant-force

A pre-shaped fixed–fixed **buckled arch** has two stable states separated by a
**negative-stiffness** region — power is needed only to switch, not to hold
(switches, latches, valves, closures). Dimension it from two nondimensional
constants:

- switch force: **`f_s · l³ / (E·I·h_mid) = 1486.57`**
- travel: **`u_tr / h_mid = 1.98`**

Choose target force + travel, solve for span `l` and mid-rise `h_mid`.
**Constant-force / quasi-zero-stiffness** mechanisms put a negative-stiffness
element (a bistable/buckled beam) in parallel with a positive one (a V-beam) so
the slopes cancel over a stroke — vibration isolation, constant-preload grippers,
force-limited contact.

### Fatigue & material reality (FDM)

Where the digital gate lies and the physical coupon rules.

- **Material ranking for cyclic flex:** TPU ≈ PP > Nylon > PETG ≫ **PLA**. PLA's
  crystalline chains can't slide; it fatigues in a handful of cycles — **never use
  PLA for a live flexure.**
- **Orientation (the #1 rule):** layers **parallel** to the flex axis, so bending
  stress acts across roads within a layer, not between layer bonds. An
  upright-printed beam delaminates on the first cycle.
- **Stress-concentration control:** fillet the flexure root at **`r ≥ 0.5·t`**.
- **Hard stops:** the real limit is fatigue/yield/buckling under *off-axis
  overload*, not primary-DOF motion. Add rigid motion-limiting contact surfaces,
  sized to keep peak stress under the material endurance limit, and fillet their
  edges.

### Lamina-emergent mechanisms (LEMs)

Fabricated **flat from a single layer**, deploying into 3-D motion — a perfect
match for FDM's flat-bed strength anisotropy. The LET joint is the canonical
building block; membrane-enhanced (M-LET) variants bias one-way deployment.

**Parameterization:** core knobs every time — `t` (dominant), `L`, `w`, root
fillet `r ≥ 0.5t`, target `θ_max`. Echo predicted `K` and root `σ`; for bistables
echo predicted `f_s`, `u_tr`. A coupon measures the three numbers the model can't
self-verify: torque-vs-angle (stiffness), snap force + travel, cycles-to-failure
at `θ_max`. Sweep `t` (and `r`) — the `t³` sensitivity makes it highest-leverage.

---

## Domain 2 — Designing around supports

Eliminate support material by reshaping geometry, not by obeying "no overhang past
45°."

### The physics

Each layer is offset outward by `layer_h / tan(angle_from_vertical)`. At 45° the
new bead overlaps the previous by ~50% — enough to anchor the strand before
gravity droops it. At 60° overlap is ~29%, at 70° ~18% (the strand curls from
differential cooling). The rule is **geometric, not a material limit**: aggressive
cooling (PLA freezes fast, T_g ≈ 60 °C) reaches clean **60–70°**; thinner layers
help (smaller outward step); slower/cooler perimeters reduce droop time.

A **bridge** is different: a strand anchored at *both* ends, printed in one pass,
held straight by longitudinal **tension** as it cools — so ~flat spans up to
~5–10 mm+ print where a cantilever of the same angle collapses. **The master move
is to convert overhangs into bridges by design.**

### Sacrificial bridging & horizontal-hole compensation

- **Sacrificial layer:** to print a horizontal counterbore/recess without support,
  close the large opening with *one* bridged layer, print the feature on that
  fresh flat bridge, cut the skin out after. OrcaSlicer/PrusaSlicer expose this as
  "Bridge Counterbore Holes" (None / Partially-bridged / Sacrificial-layer).
- **Horizontal holes print undersized** (the slicer samples at each layer's
  mid-height; the top/bottom step into the bore and bridged strands droop). Fixes:
  (a) offset — the printable profile is the **hull of the circle shifted up ½ layer
  and down ½ layer**: `hull(){ translate([0,0,layer_h/2]) circle(r);
  translate([0,0,-layer_h/2]) circle(r); }`; (b) **teardrop** — peaked roof, apex
  ~90° included (45° sides), self-supporting; (c) large teardrops: a flat roof
  ~1–2 layers above the true circle for droop clearance.

### Designed-in / breakaway supports

Model your own support: a column whose top stops **exactly one layer height below**
the down-face (`z_gap = layer_h`). The first part layer droops microscopically
onto it, bonds just enough to print, and peels off clean — deterministic where a
slicer's fractional Z-distance is not. Add a **break notch** for a chosen scar,
minimize **contact area**, place the witness mark on a non-cosmetic face. Or ship
**support-enforcer/blocker** modifier bodies so the slicer generates only where you
dictate.

### Self-supporting substitution

- Flat ceiling over a cavity → **cone / dome / vault** at ≤45°.
- **Chamfer, not fillet, on down-facing edges** (a bottom fillet starts horizontal
  → severe overhang that curls; keep fillets for up-facing stress reliefs).
- All internal surfaces ≤45° by construction; teardrop horizontal fastener holes;
  countersinks self-support (they *are* cones), counterbores do not.

### Orientation & part-splitting (the Slant3D approach)

The cheapest support is a rotation. When one orientation can't satisfy the whole
part, **split on the problem plane** and print each half optimally, then rejoin
with **dovetails** (~10–15°, 0.1–0.2 mm/side clearance), stepped Z-dovetails, keys
or snaps. Also dodges build-volume limits.

### Non-planar / multi-axis slicing (frontier)

Depositing along 3-D curves removes stair-stepping and support that planar slicing
forces. **3-axis non-planar** (QuickCurve, CurviSlicer) mainly kills stair-stepping
on gently-sloped top surfaces, bounded by **nozzle gouging**. **Conical / 4-axis**
(RotBot / Slicer4RTN) tilts the build so cone-shaped layers give a ±90° overhang
window in all directions — genuinely support-free on a modified 3-axis machine.
**5-axis conformal** (Open5x, S3-Slicer) inclines the nozzle to follow slopes.
Tooling is still experimental; relevance here is directional (curved lids/domes are
candidates, most parts stay planar).

**Parameterization:** `overhang_limit = 45` (→60 with cooling) drives all internal
wall angles; teardrop apex `= 90°`; sacrificial layer `= 1·layer_h`; support gap
`= layer_h` (a function, never a constant); down-edge chamfer `45°`; split-joint
`dovetail_angle ≈ 12°`, `clearance ≈ 0.15 mm/side`.

---

## Domain 3 — Print-in-place kinematics

Mechanisms that come off the plate assembled and moving. The whole discipline is
one problem: engineer a **gap the printer wants to close but must not**, then trap
geometry across it so it is captive but free.

### Clearance theory (why the gap works)

Three physical mechanisms shrink the design gap, each controlled differently:

- **Bead spread (XY):** a wall's true edge lands ~0.05–0.10 mm proud of nominal;
  two facing walls each encroach. Controlled by flow calibration; keep the gap
  ≥ **one line width**.
- **Overhang sag into the gap (Z-roof):** the dominant fuser when the gap's roof
  is unsupported. Controlled by bridge/cooling settings; keep the Z gap ≥ **one
  layer height**.
- **Ooze / stringing bridge:** a travel string bonds both walls. Controlled by
  retraction/temperature.

**Anisotropy is the key insight:** a vertical wall-to-wall gap is spread-limited
(tight, ~0.15–0.20 mm); a horizontal roof-over-part gap is sag-limited (~0.25–0.40
mm, or angle the roof to dodge sag). **Orientation is therefore a clearance
decision** — printing an axle pointing up converts a sag-limited interface into a
spread-limited one. **Integer-layer quantization:** snap the Z gap to `n·layer_h`
so its floor and roof land on real boundaries.

### Captive joints

A part topologically trapped yet kinematically free — native to layer-wise
printing because the printer lays material *over* a moving part. A **locking
overhang / castellation** (printed as a ≤45° lip, support-free) obstructs the
escape direction while leaving the motion axis open. **Ball-and-socket** captives
use an annular undercut; the **capture ratio** (throat/ball) trades retention
against swing angle. Chain links, gimbals and print-in-place bearings are the same
trick with the gap tuned per axis.

### Hinges

Pin-in-bore, living hinge, or flexure. A horizontal bore's roof is an overhang →
**teardrop/elliptical bore**. **The scaled-teardrop-vs-offset subtlety (critical):**
scaling a teardrop to add clearance leaves its upper 45° flank planes *coincident*
with the pin's — the print welds along the flat. Grow the bore with a true
**`offset(r=clear)`** instead. Barrel/piano hinges suffer axial **tolerance
stacking** — split into short segments or add per-knuckle axial clearance.

### Sliding / prismatic joints

Rail-and-tab **castellation** captures a door along its slide axis; **end stops**
bound travel (guard the weld gap). A thin fused **break-in bridge** shears on the
first firm push — thin enough to break clean, not so thick it tears. The
**acoustic/rattle criterion** (from hidden-information games: a loaded cell must
not sound different from an empty one) means you tune the **door-side fit, never
the rail clearance**, which carries the acoustic property.

### Gears & rotary

**Backlash** is set by center distance / tooth-thickness allowance, **not** profile
shift (open center 0.2–0.4 mm or thin the tooth — no reprint of the mate).
**Module** is the master printability knob (too small → sub-line-width teeth).
**Profile shift** (+0.08–0.15 on ≤15-tooth pinions, negative on the mate) removes
undercut without adding backlash. **Herringbone** self-centers axially and retains
print-in-place planets. **Orientation:** print bore-axis vertical so layers run
around the tooth, not across the root (Z strength is only 25–40% of XY); 3–4
perimeters beat high infill for root strength.

### Bearings & first motion

A print-in-place bearing prints with micro-fusion across the race; the **break-free
first motion** shears it — design for a deliberate low-torque break-in, not a
seized part. **Sacrificial membranes/rafts** inside cavities catch droop: a
one-layer film spanning a roofless internal void gives the overhang something to
print onto (its raised start *is* the membrane).

**Parameterization:** `clear_xy = k_xy · line_w`, `clear_z` snapped to integer
layers; `line_w ≈ 1.1–1.2 × nozzle_d`. **Never one global `tol`** — separate
`xy_tol` (spread) from `z_tol` (sag). A mate coupon measures the *assembled* result
(interference facets == 0) with a deliberately-interfering negative control.

---

## Governing relations (memorize these)

| Quantity | Relation |
|---|---|
| Flexure stiffness (small-length pivot) | `K = E·I / L`, `I = w·t³/12` |
| Flexure root stress | `σ ≈ E·t·θ / (2L)`; fillet `r ≥ 0.5t` |
| Bistable arch switch force | `f_s · l³ / (E·I·h) = 1486.57` |
| Bistable arch travel | `u_tr / h = 1.98` |
| Overhang overlap step | `layer_h / tan(angle_from_vertical)` (45°≈50%, 70°≈18%) |
| Print-in-place XY gap | `≥ one line width` (spread-limited) |
| Print-in-place Z gap | `≥ one layer height`, snapped to `n·layer_h` (sag-limited) |
| Gear backlash | center-distance / tooth-thickness allowance (not profile shift) |

---

## What should become a `lib/` module

The repo encodes the rules; none of these advanced families exist as gated
primitives yet. Ranked:

1. **`lib/compliant.scad` (flagship, [#202](https://github.com/shaiss/print-bench/issues/202)).**
   Flexure family — small-length pivot, cross-axis pivot, LET joint, bistable
   arch. Dissolves the exact clearance/rattle/wear problem `print-in-place.scad`
   fights; lamina-emergent joints print flat. Fits the library contract cleanly
   (demo + guards for zero-fillet / over-stress / PLA-flexure, a stiffness coupon).
   First-party, BSD-clean.
2. **`lib/dfm-supports.scad` (complement).** Sacrificial-layer helper, designed-in
   breakaway support (`z_gap = layer_h`, break-notch, tunable contact/scar),
   self-supporting cone ceiling, chamfer-down-edge. Extends `printability.scad`'s
   existing `teardrop_hole()` rather than duplicating it.
3. **Anisotropy-aware clearance in `printer-conf.scad` (small, high-value).** Split
   `printer_fit()` into `printer_fit_xy()` / `printer_fit_z()` with the
   integer-layer snap.

Gears: lean on BOSL2 `gears.scad` and document the rules, rather than build fresh.
Metamaterials / 4D: parked in [#201](https://github.com/shaiss/print-bench/issues/201)
— the one family that doesn't yet reduce to a clean parametric primitive.

---

## Sources & provenance

Research was primary-source-first (arXiv via the alphaXiv connector, slicer
manuals, empirical testers), with vendor blogs used only for the FDM-practical
layer and flagged as such.

**Compliant mechanisms**
- Srivastava et al., "Design of an engaging-disengaging compliant mechanism by
  using bistable arches," arXiv:2511.06039 (2025) — *read in full*; bistable-arch
  constants, worked FDM example.
- Chen et al. (UCLA), "Hard-Stop Synthesis for Multi-DOF Compliant Mechanisms,"
  arXiv:2507.13455 (2025) — *read in full*; fatigue/yield/buckling as governing
  limit.
- L. Howell, *Compliant Mechanisms* (Wiley, 2001) and *Handbook of Compliant
  Mechanisms* — PRBM origin (γ, Kθ), SLFP method. *Textbook, not fetched.*
- BYU Compliant Mechanisms Research — <https://compliantmechanisms.byu.edu/> —
  cross-axis/cartwheel/LET joints, downloadable reference STLs.
- LET-joint stiffness, cross-axis pivot modeling, constant-force survey — *Mech.
  Mach. Theory* (found by title).

**Designing around supports**
- Nophead / HydraRaptor — "Horiholes", "Polyholes" (2011/2020) — *empirical
  hole-compensation data + the ±½-layer hull method* (read via search extract).
- Ottonello, Hugron, Parmiggiani, Lefebvre, "QuickCurve: revisiting slightly
  non-planar 3D printing," arXiv:2406.03966 (2024) — *read in full*; nozzle-gouging
  limit.
- CurviSlicer (ACM TOG 2019), Open5x (arXiv:2202.11426, CHI 2022), S3-Slicer (TOG
  2022), Hornus & Lefebvre "Iterative carving for self-supporting cavities" (EG
  2018) — found by title.
- OrcaSlicer / PrusaSlicer bridging + sacrificial-layer docs; Slant3D
  mass-production / dovetail splitting; CNC Kitchen RotBot 4-axis — found.

**Print-in-place kinematics**
- "AgentsCAD: Automated Design for Manufacturing of FDM Parts," arXiv:2607.02448
  (CMU, 2026) — *read in full*; ~45° limit, teardrop bore, reorient-before-modify
  ordering.
- "Wear-Clearance-Impact Coupling in the Jansen Linkage," arXiv:2606.25208 — found.
- Protolabs/Hubs living-hinge & snap-fit knowledge base; Formlabs snap-fit
  enclosures; Snapmaker hinge/45°-rule guides; a print-in-place herringbone
  planetary reference (Printables); Maker's Muse tolerance gauge — read
  (summary) / found.

**Honesty notes.** Material-specific clearance numbers (PLA 0.3 sliding / 0.5
rotating, etc.) come from vendor/aggregator blogs, not peer-reviewed measurement —
treat as **calibration starting points, not constants**. The anisotropy and
integer-layer reasoning is physically derived and consistent across sources but no
single controlled study isolating Z-sag vs XY-spread was found. The exact textbook
PRBM constants (γ ≈ 0.85, Kθ ≈ 2.65) are widely cited to Howell but were not
verified against the book directly. FDM flexure cycle-life figures are practitioner
estimates. WebFetch was network-blocked during research, so most non-arXiv sources
are via search-snippet extraction rather than full-text retrieval.
