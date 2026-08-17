# Metamaterials & 4D printing — survey of the frontier

This is the research note **[#201](https://github.com/shaiss/print-bench/issues/201)**
asked for: whether and where programmable / architected-material technique
earns a place in this repo — as a `lib/` primitive, a reference design, a
documented technique note, or nothing yet. The issue's framing holds: this is
the *frontier* — furthest from anything in the repo today, higher-risk, and
not obviously reducible to one parametric module. This note is the survey plus
the per-technique recommendation a human uses to decide follow-on work; **no
geometry or gate is promised by the issue, and none is delivered here.**

Companion threads — the adjacent, more tractable families this note keeps
bumping into — are already in flight:

- `docs/advanced-techniques.md` is the knowledge layer (physics + maneuvers);
  it explicitly parks this family in #201 and cross-links back.
- **[#202](https://github.com/shaiss/print-bench/issues/202)** is the
  *compliant-mechanisms* thread (`lib/compliant.scad`, flexures, bistable
  arches). §5 below flags the boundary with it deliberately: bistability is
  the one family where the two threads genuinely overlap, and double-covering
  it would produce two libraries where one belongs.

Method, and its honesty limits: sources are primary-first (arXiv, *Nature*,
*Science*, *Int. J. Mech. Sci.*, *Materials & Design*, *Chem. Mater.*, CHI),
reached via web search. Where a number is load-bearing it is cited; where the
evidence is practitioner folklore it is flagged as such, never laundered into
a citation. Entries tagged *found by title* were located but **not
independently retrieved** — research leads, not confirmed results. FDM-reality
caveats are derivations from process physics, consistent with the sources but
not measured on this repo's toolchain: nothing below has been printed here.

---

## 1. Auxetic structures (negative Poisson's ratio)

**What it is.** A lattice that gets *fatter* when stretched and denser when
compressed (ν < 0), because the cell geometry rotates/unfolds rather than
stretching its ligaments. Canonical cells:

| Cell | Mechanics | What it buys | Primary source |
|---|---|---|---|
| Re-entrant honeycomb | inward-pointing ribs buckle/rotate outward on tension | energy absorption, synclastic bending (dome, not saddle) | Lakes, *Science* 235, 1038 (1987); Yang et al., *Int. J. Solids Struct.* 75–76, 61–74 (2015) — *journal records verified* |
| Chiral / anti-chiral | circular nodes + tangent ligaments; nodes rotate under load | ν ≈ −1 over a wide strain range, near-isotropic in-plane | Prall & Lakes, *Int. J. Mech. Sci.* 39(3), 305–314 (1997) — *verified*; Alderson et al. (2010) 3/4/6-connected chiral families — *found by title* |
| Rotating rigid units | squares/triangles connected at corners; rigid rotation is the whole mechanism | ν → −1 analytically, huge geometric amplification, near-zero stiffness along the mechanism path | Grima & Evans, *J. Mater. Sci. Lett.* 19, 1563–1565 (2000) — *verified*; Grima et al., rotating triangles/squares, CMST 10(2) (2004) — *found by title* |

**How it parameterizes for FDM.** This is the family that parameterizes
*cleanly* — which is why it lands where it does in §8:

- **Cell size vs the line-width floor.** The unit cell is 2–3 numbers (cell
  pitch, rib angle, rib thickness) and every one is bounded below by the same
  process constant the repo already encodes: rib thickness ≥ ~1 line width
  (0.75–1.5 × nozzle Ø; ≈ 0.4–0.6 mm on the stock 0.4 mm nozzle), so the
  smallest honest cell is ~3–4 mm pitch with 0.5 mm ribs. Below that the
  slicer over-extrudes single-wall ribs and the lattice stops matching its own
  geometry. This is the `printer_xy_tol` / `printer_nozzle_d` vocabulary
  `lib/printer-conf.scad` already speaks.
- **Printability of re-entrant angles.** The inward-pointing rib is a small
  cantilever per layer; at re-entrant angles steeper than ~45° from vertical
  each successive layer overhangs the last, so print-flat-in-plane lattices
  self-cap around 45–60° rib inclination. Flatter lattices print supportless
  on the bed; steeper ones need orientation tricks or accept droop. A
  parameterizing module would expose rib angle with exactly this constraint
  documented, and a guards config would refuse `rib_angle > 60` absent an
  explicit override.
- **Layer-line anisotropy.** FDM parts are weakest along Z (interlayer). A
  lattice printed flat whose ribs rise in Z will delaminate under the very
  rotation the cell needs; ribs must lie **in-plane** for the mechanism to
  survive cycling. That is an orientation contract a `lib/` module can state
  but not enforce — the kind of thing a `NOTES.md` derivation and a coupon
  carry.

**FDM-reality caveats.** The papers' cells are usually SLA/multi-jet or FE
meshes with 0.1 mm features; FDM reality is 5–10× coarser, so published
Poisson ratios are upper bounds, not expectations. Re-entrant honeycomb in
*thick* (multi-layer, Z-growing) form is a support nightmare the 2D papers
never show. And the family's headline property — auxetic response over strain
— degrades when rib joints print with fillets (they do; extrusion beads round
over), so measured ν drifts toward −0.4…−0.7 when the design says −1.
Farshbaf et al., arXiv:2503.18736 (2025) documents the negative-to-positive ν
transition under large deformation — *verified by abstract* — relevant
because FDM-printed cells are squat (thick ribs) and hit that transition
early.

**Repo mapping.** Single-nozzle FDM ✓ (parameterizes above the line-width
floor). `$fn`/line-width floors ✓ (the constraint *is* the module's parameter
space). Gate/coupon/mate model — a coupon is natural and cheap: one 3×3 or
4×4 lattice tile, print, squeeze, observe lateral expansion; no mate needed
(no mated pair). GPL boundary ✓ trivially (all-first-party geometry, no
vendored include).

---

## 2. Mechanical metamaterials generally

The issue names three sub-families; they share one property — the *mechanism*
lives in the geometry, not the material — and differ in how they're driven.

### 2a. Pattern-transformation (buckling-induced)

**What it is.** A periodic structure whose buckling mode is *designed*: at a
critical compressive strain the whole array switches pattern at once (the
canonical image: a square array of circular holes in an elastomer sheet
flipping to alternating orthogonal ellipses), and the switch is reversible
and repeatable because it's elastic, not plastic. Foundational: **Mullin,
Deschanel, Bertoldi & Boyce, "Pattern Transformation Triggered by
Deformation," *Phys. Rev. Lett.* 99, 084301 (2007)** — *verified*; and
Overvelde et al., "Compaction through Buckling in 2D Periodic, Soft and
Porous Structures" (2012) — *found by title*. Recent: Barvenik et al.
(2025), inflation-induced buckling of soft porous metamaterials — *found by
title*; He et al. (2018) — *found by title*.

**What it buys.** A mechanism with no joints: macroscopic actuation from a
flat sheet, negative-stiffness events on demand, programmable sequential
folding (buckling order encoded in hole-size gradients).

**FDM-reality caveats.** The literature's hole arrays are silicone (Sylgard)
or TPU, strained 10–30% — strain regimes PLA cannot survive elastically
(PLA yields ~2–3%). On rigid FDM stock the transformation either snaps
brittle or needs TPU, and TPU on a stock single-nozzle bowden machine prints
these arrays poorly (stringing bridges hole to hole, feeding TPU is its own
craft). The honest read: **pattern transformation on this repo's stock PLA
is a no**, and on TPU it's a materials problem before it's a geometry
problem. The one durable exception is *macro-scale* pattern transformation
where the "material" is a 3 mm-thick PLA wall — there the strains are
geometry-amplified and small. That's really §5's lattice domain.

### 2b. Programmable stiffness

**What it is.** Stiffness set by cell topology rather than material choice —
same filament spanning a stiffness range of orders of magnitude via cell
geometry (stretch-dominated vs bending-dominated lattices, graded lattices).
The governing relation is classical: stretch-dominated lattices scale as
E/ρ (ideal), bending-dominated as (E/ρ)² — Deshpande, Ashby, Fleck,
*Acta Mater.* 49, 1035 (2001) — *found by title; the octet truss paper*.

**What it buys for this repo.** This is the quiet workhorse of the whole
survey: a parametric lattice with a stiffness dial is a *functional print*
(gasket, grip, cushion, protective insert), not a demo. It needs no
actuation, no exotic material, no post-print trigger — it's just a spring
you can parameterize. It is also the family with the closest existing
neighbour: `styles/` is a *look* vocabulary; this would be a *mechanics*
vocabulary, and the two compose.

**FDM-reality caveats.** Stiffness claims transfer only if struts print
true-to-CAD, and single-line-width struts don't (they print as one bead ≈
0.4–0.45 mm regardless of the drawn 0.3 mm). So the honest module
quantizes strut thickness to integer line widths and says so. graded
lattices need variable strut count *per cell*, which is fine, but smooth
gradients across a boundary layer are where slicer path planning wobbles.
Yang, Gao et al. and the TPU lattice work (de la Rosa et al., *Rapid
Prototyp. J.* 30(11), 2024 — *found by title*) parameterize exactly this
design-space for pressure cushions.

### 2c. Negative stiffness / energy trapping

**What it is.** A structure whose force–displacement curve has a
*descending* branch (force decreases as displacement grows) over some range.
Energy is trapped in a metastable configuration and released on trigger —
the physics of snap-through, used for vibration isolation (Q → very high
damping), shock trapping, and reusable "impact absorbers." Primary: Lakes,
Lee, Bersie & Wang, "Extreme damping in composite materials with
negative-stiffness inclusions," *Nature* 410, 565 (2001) — *verified*; the
displaced-phase inclusions are the canonical demonstration. Follow-on:
Dong, Stone & Lakes, "Advanced damper with negative structural stiffness
elements," *Smart Mater. Struct.* 21, 075026 (2012) — *found by title*.
arXiv:2507.00396 (2025), negative-extensibility metamaterial isolation —
*found by abstract*.

**What it buys.** Peak damping tan δ beyond any passive constituent; a
mechanical "fuse" that absorbs a shock and self-recovers; tunable
quasi-zero-stiffness isolators.

**FDM-reality caveats.** The Nature paper's inclusions are *phase-
transforming* materials near their instability (BaTiO₃-class ceramics in a
matrix) — a materials system a printer cannot lay down. The printable route
is geometric negative stiffness: pre-shaped curved beams (the §5 / #202
domain), and at that point the unit cell *is* a bistable mechanism and the
boundary with the compliant-mechanisms thread is crossed. **Printable
negative stiffness without bistability** is essentially confined to
viscoelastic TPU lattices, which is §2b again. So §2c resolves to: the
*effect* is real and desirable; the *printable embodiment* routes through
#202's curved-beam cells or §2b's TPU lattices — no separate repo surface.

---

## 3. Bistable / multistable & programmable geometry

**What it is.** Structures with two or more stable equilibrium states, no
holding force needed in either — arrays of snap-through cells giving
shape-memory without shape-memory material, deployable surfaces, mechanical
logic (AND/OR gates from coupled bistables), reconfigurable armor.
Programmable geometry: the *set* of stable states is chosen at design time
by grading cell geometry. Sources: the snap-through review line — Yan et al.,
"Snap-through instability in mechanical metamaterials" (Wiley, 2025,
doi:10.1002/rpm.20240035) — *found by title*; Yue et al., "SIMMs"
review, *Int. J. Ext. Manuf.* (2026) — *found by title*; Mao et al.,
modular multistable (2022) — *found by title*; the von Mises truss /
bistable arch mechanics with the constants already in
`docs/advanced-techniques.md`'s governing-relations table.

**What it buys.** Set-and-forget actuation (a latch that stays latched with
zero energy), signal-free mechanical logic, shock-wave tripping chains
(fusee-like sequential collapse), shape change without hinges.

**FDM-reality caveats.** PLA is *good* at this — the snap-through constants
for shallow arches are already catalogued in
`docs/advanced-techniques.md` (f_s·l³/E·I·h_mid = 1486.57; u_tr/h_mid =
1.98) and PLA's modulus and yield strain are enough for shallow arches —
but cycle life is the enemy: a PLA bistable cycled past a few hundred
counts fatigues at the arch roots (fillet r ≥ 0.5t is the known
mitigation, also already in that table). The literature's multistable
arrays are again mostly silicone/TPU; PLA arrays work at *coarser* cell
sizes with *steeper* design margins. Fatigue here is a coupon-measurable:
cycle-to-failure on the "print this first" coupon is the honest number,
not the paper's.

**Boundary with the compliant-mechanisms thread (#202) — flagging it
deliberately, as the issue asks.** This family is where the two threads
meet, and the boundary is:

- **#202 owns the *joint***: the single bistable arch / von Mises truss as a
  *compliant-mechanism primitive* — the thing a mechanism *uses* (a latch, a
  constant-force element, a hard stop). One cell, mechanics-first, gated by
  the lib contract (demo, guards, stiffness coupon).
- **This survey (#201) assessed the *array***: coupled chains and 2D arrays
  of those cells — multistable *materials*, mechanical logic, deployable
  surfaces. Different design questions (interaction energies, sequential
  tripping, defect sensitivity), different failure modes (a mis-tripping
  chain), and — the survey's finding — **no repo need for the array today**.
  Nothing in the design backlog asks for a multistable surface; one design
  (a snap-fit) asks for *a* bistable, which is #202's single cell.

So the recommendation below keeps the array out of `lib/` not because it
can't be built but because #202's single cell covers the known need and the
array doubles the surface without a customer.

---

## 4. 4D printing / self-folding / shape-memory

**What it is.** A printed object changes shape over time (time = the 4th
dimension) in response to a stimulus — heat, moisture, light, current. Term
coined by Tibbits (2013, MIT Self-Assembly Lab; the TED introduction) with
multi-material jetting + SMP; the field has since spread across processes.

**The honest stock-FDM read the issue explicitly asks for.** Three routes,
only one of which runs on this repo's machines:

1. **Single-material anisotropic-path self-folding — the one that works on
   stock FDM.** Exploit what the printer already does: deposited beads carry
   residual stress and contract anisotropically on reheating (more along the
   bead axis, less across), and bilayers with mismatched contraction curl
   toward the denser face. No exotic material; the "actuator" is print-path
   design. Primary: **Goo, Hong & Park, "4D printing using anisotropic
   thermal deformation of 3D-printed thermoplastic parts," *Materials &
   Design* 188, 108485 (2020)** — *verified*; single thermoplastic, MEX/FDM,
   no shape-memory material. And **Wang, Zhang & Yao, "Thermorph:
   Democratizing 4D Printing of Self-Folding Materials and Interfaces," CHI
   2018** — *verified*; the gap-layer technique (dense top face, sparse
   gap, dense bottom) on a stock Ultimaker with plain PLA, folding on
   uniform heating, with the curved-folding origami compiler. These two are
   the load-bearing citations for "stock machine, plain filament, real
   result."
2. **Shape-memory polymers (SMP).** PLA itself is a weak SMP (Tg ~60 °C,
   one-way, few cycles before the effect degrades; Rahmatabadi et al. 2024
   review — *found by title*). Real SMP 4D printing uses purpose filaments
   (SMP urethane, PLA/PCL blends, PLA/CNT) — off-the-shelf but a *materials
   adoption*, not a stock assumption, and one-way only: the print can't
   un-actuate without manual re-programming (heat above Tg, deform, cool).
3. **Multi-material jetting / hydrogels / high-force SMP.** The Tibbits
   original and most of the flashy literature. Not FDM; out of scope for
   this repo's machine assumptions.

**What route 1 actually requires, and why it doesn't reduce to `lib/`.**
Print-path self-folding is not a geometry problem — it is a *slicer
G-code* problem. The fold lives in the infill pattern, densities and
per-extrusion widths of specific layers (Thermorph's gap layer; Goo's
bead-direction bilayer), and OpenSCAD emits an STL that carries none of
that. An STL says "here is a solid"; the anisotropy contract — which
regions are dense, which sparse, which direction the beads run — is
invisible to the geometry pipeline and unpreservable through the
STL→slicer→print chain this repo's gates sit on. A `lib/` module cannot
gate what it cannot express; a design would need per-layer slicer
modifiers (PrusaSlicer modifier meshes with per-region infill) plus a
heating protocol plus a calibration coupon, and the repo has no mechanism
to gate any of that end-to-end. The technique is real, cheap and worth a
*reference design* (see §8) — but as a *documented technique*, not a
parametric primitive.

**FDM-reality caveats.** Even route 1 is not turnkey: fold angle depends on
heating rate and uniformity (oven/hot-air/hot-water each give different
results), on filament batch residual stress (measurably varies by
manufacturer and color), and on ambient aging of the printed part (PLA
relaxes over weeks). Thermorph reports ~±few-degrees repeatability under
*uniform* heating; a heat gun does not qualify. Cycle life: each
re-heat/cool is one cycle of the same thermal fatigue that kills PLA
living hinges — few cycles, then drift. Any design here ships with a
calibration coupon and "your filament will differ" as a first-class
parameter.

**Repo mapping.** Single-nozzle FDM ✓ (route 1 only). `$fn`/line-width
floors — irrelevant (the parameters are infill densities and bead
directions, not geometric feature sizes). Gate/coupon/mate model — **the
gap**: geometry gates can't see the actuation; a coupon is mandatory and
*manual* (print, dunk in 60–70 °C water, measure fold angle). GPL boundary
✓ (pure first-party slicer technique).

---

## 5. Compliant / architected lattices for functional parts

**What it is.** The applied end: lattices and lattice-like structures as
*product* — cushioning, damping, grip surfaces, seals, springs, protective
inserts — where the lattice is sized to a target force–deflection curve
rather than studied for its exotic index. Sources: de la Rosa et al. (2024,
2025) TPU lattice families for pressure cushions — *found by title*; Ma et
al. (2025) lattice metamaterial review — *found by title*; the
geometry-process-property FDM TPU framework work — *found by title*.

**What it buys.** The only family in the survey whose output is an everyday
functional print: a watch strap segment, a tool grip, a vibration-isolating
foot, a custom gasket, a crush zone. Tunable stiffness (§2b) + a real part
at the end.

**FDM-reality caveats.** TPU is the honest material for most of it (PLA
lattices are stiff springs, fine for crush zones and locators, poor for
cushions/gaskets) and TPU brings the usual single-nozzle TPU craft
problems: slow print, stringing across cells, retract tuning, hygroscopic
filament. Cell walls below one line width don't print; closed cells need
drain/vent holes or trapped-air springiness you didn't design; thin
ligaments on a bed print *flatter* than CAD and the first-layer squish
dominates the response of a 2–3 mm cell. The framework literature's own
headline is that process and geometry are inseparable for TPU lattices —
exactly the print-feedback-loop insight (`docs/print-feedback.md`) this
repo already runs on: the coupon *is* the instrument.

---

## 6. What the literature agrees on, and where it thins

Convergent across families: geometry can carry mechanism; cell-scale
features are bounded by process floor (line width, layer height); anisotropy
is a first-class design variable in extrusion printing, not a defect; and
every applied paper lands on a coupon-calibrate-then-design loop. That last
point is the strongest signal in the survey for *this* repo — it's the
repo's existing print-feedback philosophy rediscovered by the metamaterials
literature.

Where it thins: published Poisson ratios, damping peaks and stiffness
constants are measured on SLA/multi-jet/silicone systems with features 5–10×
finer than FDM's floor; almost no controlled study isolates FDM process
effects (bead rounding, first-layer squish, interlayer weakness) on
metamaterial *indices* — the numbers transfer as *directions*, not
magnitudes. Anyone building from this note should treat §1–§5's citations as
the mechanism-confirmation layer and re-derive magnitudes on the repo's own
coupon, exactly as `lib/threads-fdm.scad`'s `tol` had to be measured, not
assumed (the #37 lesson, again).

---

## 7. Recommendation summary

One line per family, from the issue's four-way menu (encode as `lib/`
primitive / build a reference design / document-only / not yet):

| # | Family | Recommendation | The one-sentence reasoning |
|---|---|---|---|
| 1 | Auxetic lattices (re-entrant, chiral, rotating-unit) | **Encode as `lib/` primitive** (when a design asks for it) | The only family whose parameters map 1:1 onto the process constants the repo already encodes (line-width floor, nozzle Ø, orientation contract), with a cheap coupon and no mate needed. |
| 2a | Buckling-induced pattern transformation | **Not yet** | Strain regimes (10–30%, silicone/TPU) are beyond stock PLA's elastic range; the TPU route is a materials adoption before it's a geometry one. |
| 2b | Programmable-stiffness lattices | **Build a reference design** | A parameterized lattice *part* (grip/cushion/insert) is the family's real product and the natural first customer for #1's cell modules — one design exercises the vocabulary. |
| 2c | Negative stiffness / energy trapping | **Not yet** (routes through #202 / §2b) | The printable embodiment is bistable curved beams (#202) or TPU lattices (§2b); a phase-transforming-inclusion materials system is unprintable. No separate surface needed. |
| 3 | Bistable/multistable arrays | **Not yet** — single cell owned by #202 | #202's single bistable cell covers the known need (snap-fit); arrays (logic, deployables) have no design-backlog customer and double the library surface. Boundary flagged in §3. |
| 4 | 4D printing / self-folding | **Document-only** (this note) + revisit via reference design | Route 1 (anisotropic-path, single-material) is real on stock FDM but is a slicer-G-code technique an STL pipeline cannot carry or gate; a `lib/` module would gate nothing. |
| 5 | Compliant/architected lattices for functional parts | **Build a reference design** (paired with #1) | Everyday functional output (grip, foot, gasket, crush zone) with a natural coupon; the applied face of §2b and the first real customer for the cell library. |

**The one-paragraph synthesis.** Nothing here justifies a metamaterials
library *today*: the only cleanly-encodable family (#1 auxetics) has no
design asking for it yet, and the families with customers (#2b, #5) are
served by one reference design plus a small set of cell modules, not a
standing library. The right next move, when a need appears, is a **cell
vocabulary in `lib/`** (re-entrant/chiral/rotating-unit generators, each
with rib thickness quantized to line widths, angle guards, orientation
contract in the header) exercised by **one functional reference design**
(a stiffness-tunable cushion/foot/grip) — at which point #1 and #2b/#5
land together, and #3's arrays and #4's folding stay parked until a
design asks for them. Everything else stays what it is now: a documented
frontier with primary citations, which is exactly what this note is.

---

## 8. Repo-constraint mapping (issue requirement, one table)

How each family meets the four constraints the issue names — single-nozzle
FDM, `$fn`/line-width floors, the gate/coupon/mate-test model, and the GPL
boundary. One row per family; ✓ clean fit, ◐ conditional, ✗ blocked.

| Family | single-nozzle FDM | line-width floors | gate / coupon / mate | GPL boundary |
|---|---|---|---|---|
| **#1 Auxetic lattices** | ✓ plain PLA | ✓ the floor *is* the parameter space (rib ≥ 1 line width) | ✓ tile coupon, no mate needed | ✓ all first-party |
| **#2a Pattern transformation** | ✗ needs silicone/TPU strains | ✗ published features ≪ line width | n/a — not buildable on stock | — |
| **#2b Programmable stiffness** | ✓ PLA or TPU | ✓ struts quantized to integer line widths | ✓ force–deflection coupon | ✓ |
| **#2c Negative stiffness** | ◐ only via #202 curved beams or TPU lattice | ✓ beam dims are coarse | ✓ inherits #202's coupon | ✓ |
| **#3 Bistable arrays** | ✓ PLA at coarse cell sizes | ✓ | ✓ cycle-life coupon (fatigue is the metric) | ✓ |
| **#4 4D / self-folding** | ✓ route 1 only (anisotropic path) | n/a — parameters are infill/bead directions, not feature sizes | ✗ geometry gates are **blind** to the actuation; coupon is manual | ✓ pure first-party slicer technique |
| **#5 Functional lattices** | ✓ TPU preferred, PLA for crush zones | ✓ quantize struts; closed cells need vents | ✓ force–deflection coupon | ✓ |

The one structural finding in this table: **every family clears the GPL
boundary trivially** (first-party geometry all the way down), and the only
family the *gate model* cannot express is #4 — which is why §7 parks it as
document-only rather than trying to gate the ungateable.

---

## Sources & provenance

Research was primary-source-first, reached via web search under the usual
network constraints; where a source was located but not independently
retrieved it is tagged **found by title / found by abstract** in place, per
the `docs/advanced-techniques.md` convention. Verified means the record
(authors, venue, year, DOI/arXiv id) was confirmed against the publisher or
arXiv listing during this survey.

**Auxetics**
- R. S. Lakes, "Foam structures with a negative Poisson's ratio," *Science*
  235, 1038–1040 (1987) — the re-entrant origin. *Verified by listing.*
- D. Prall & R. S. Lakes, "Properties of a chiral honeycomb with a Poisson's
  ratio of −1," *Int. J. Mech. Sci.* 39(3), 305–314 (1997) — *verified*
  (ScienceDirect record + author full text at
  [lakeslab](https://silver.neep.wisc.edu/~lakes/PoissonChiral.html)).
- J. N. Grima & K. E. Evans, "Auxetic behavior from rotating squares,"
  *J. Mater. Sci. Lett.* 19(17), 1563–1565 (2000),
  doi:10.1023/A:1006781224002 — *verified* (Springer record; idealized
  ν = −1).
- L. Yang et al., "Mechanical properties of 3D re-entrant honeycomb auxetic
  structures realized via additive manufacturing," *Int. J. Solids Struct.*
  75–76, 61–74 (2015) — *verified* (ScienceDirect record). S. Farshbaf et
  al., "Large
  deformation and collapse analysis of re-entrant auxetic and hexagonal
  honeycomb lattice structures…," arXiv:2503.18736 (2025) — *verified by
  abstract.*
- Grima, Farrugia, Gatt, Attard (rotating triangles), CMST 10(2) (2004);
  Alderson et al., chiral/anti-chiral elastic constants (2010); Luo et al.
  (2023) chiral/anti-chiral lattice; Elsamanty (2023) rotating-squares
  tailoring — *found by title.*

**Mechanical metamaterials**
- T. Mullin, S. Deschanel, K. Bertoldi, M. C. Boyce, "Pattern
  Transformation Triggered by Deformation," *Phys. Rev. Lett.* 99, 084301
  (2007) — *verified* (APS record); the founding hole-array paper.
  Overvelde, Shan, Bertoldi et al., compaction through buckling in 2D
  periodic porous structures (2012); Barvenik et al. (2025) inflation-
  buckling porous metamaterials; He et al. (2018); Gao et al., *Sci. Rep.*
  (2018) — *found by title.*
- V. S. Deshpande, M. F. Ashby, N. A. Fleck, "Foam topology: bending versus
  stretching dominated architectures," *Acta Mater.* 49(6), 1035–1040
  (2001) — *verified* (ScienceDirect record); the octet-truss
  stretch-dominated result.
- R. S. Lakes, T. Lee, A. Bersie, Y. C. Wang, "Extreme damping in composite
  materials with negative-stiffness inclusions," *Nature* 410, 565–567
  (2001), doi:10.1038/35069035 — *verified* (PubMed + author PDF at
  [rodlakes.com](https://rodlakes.com/NegStfNat.pdf)); companion *Phil. Mag.
  Lett.* 81, 95 (2001) — *found by title.* arXiv:2507.00396 (2025)
  negative-extensibility isolation — *found by abstract.*
- Dong, Stone & Lakes, "Advanced damper with negative structural stiffness
  elements," *Smart Mater. Struct.* 21, 075026 (2012) — *found by title*;
  the quasi-zero-stiffness
  isolator literature — *found by title.*

**Bistable / multistable**
- Yan et al., snap-through instability review (2025); Yue et al., SIMM
  review, *Int. J. Ext. Manuf.* (2026); Mao et al. modular multistable
  (2022); Liang et al. inverse-design multistable (2023); Srivastava et
  al., arXiv:2511.06039 — *found by title / abstract*, except the last,
  *read in full for the #202 thread and quoted in
  `docs/advanced-techniques.md`.*

**4D printing / self-folding / SMP**
- S. Tibbits, "The emergence of 4D printing" (TED 2013; MIT Self-Assembly
  Lab) — the coining; multi-material jetting origin. *Found.*
- Z. Wang, Y. J. Zhang, L. Yao, "Thermorph: Democratizing 4D Printing of
  Self-Folding Materials and Interfaces," *Proc. CHI 2018*, ACM — *verified*
  (authors/venue confirmed; full text at
  [morphingmatter.org](https://morphingmatter.org/projects/thermorph)).
  Gap-layer self-folding on stock FDM, plain PLA, uniform heating.
- B. Goo, C. Hong, K. Park, "4D printing using anisotropic thermal
  deformation of 3D-printed thermoplastic parts," *Materials & Design* 188,
  108485 (2020), doi:10.1016/j.matdes.2020.108485 — *verified* (journal
  record). Single-thermoplastic MEX/FDM self-morphing, no SMP.
- Rahmatabadi et al., sustainable SMP / 4D printing review (2024);
  Mehrpouya et al., 4D printing of shape-memory PLA (2021); Pandeya et al.
  thermo-responsive self-morphing (2022); Zhang et al. pre-stressed
  self-folding mechanism (2023) — *found by title.*

**Functional / architected lattices**
- S. de la Rosa et al., 3D-printed TPU lattice structures for pressure
  cushions, *Rapid Prototyp. J.* 30(11) (2024) and the 2025 open/closed-
  cell follow-up — *found by title.*
- Ma et al., multi-physical lattice metamaterials review, *Adv. Sci.*
  (2025); the geometry–process–property FDM TPU framework line — *found by
  title.*
- Kang et al., multiscale printing via active nozzle control, *Sci. Adv.*
  (2024) — *found by title*; cited here only for the line-width floor
  statement, which is also common practitioner knowledge.

**Tooling prior art.** No established OpenSCAD auxetic/metamaterial library
exists (community threads ask for one; scattered Printables models are
single-cell demos, not parametric families). The ecosystem's lattice
generators live in slicers (infill) and commercial CAD. For this repo that
is good news: a first-party `lib/` cell vocabulary would be genuine
first-of-kind tooling in the OpenSCAD ecosystem, BSD-clean, with no GPL
exposure.

**Honesty notes.** (1) Every FDM-reality caveat in §1–§5 is a physics
derivation or practitioner consensus, not a measurement on this repo's
toolchain — nothing here has been printed, and the numbers (line-width
floors, 45° overhang, ν drift) are the repo's existing conventions, already
documented in `CLAUDE.md` and `docs/advanced-techniques.md`, applied to new
families. (2) Most non-arXiv sources were reached through search-result
summaries rather than full-text retrieval; the *found by title* tag marks
every one, and none of them is load-bearing for a recommendation — the
load-bearing citations (Prall & Lakes 1997, Grima & Evans 2000, Lakes et al.
*Nature* 2001, Wang et al. CHI 2018, Goo et al. 2020, Farshbaf 2025) are
individually verified. (3) Cycle-life, fold-angle-repeatability and
Poisson-ratio-drift magnitudes are qualitative throughout: no controlled
FDM-specific study of them was found, which is itself a survey finding —
the repo would be measuring, not looking up, if it built any of this.
