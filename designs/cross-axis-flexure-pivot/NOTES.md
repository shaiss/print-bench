# cross-axis-flexure-pivot — engineering notes

**Tier-2 technique reference for** `docs/advanced-techniques.md` **Domain 1
(flexure joint families)** — the cross-axis row ("good in tension, WEAK IN
COMPRESSION, near-fixed virtual center"), the one joint family the catalog
lacked (`snap-cantilever-clip` = SLFP, `let-folding-panel` = LET,
`bistable-toggle` = buckled arch, `constant-force-slider` = CF). Brief #630,
run through `/design-run` — claim comment:
<https://github.com/shaiss/print-bench/issues/630#issuecomment-5648324190>.

## Goal

A desk-scale, monolithic, support-free hinge that rotates **about a near-fixed
virtual center**: two slender beams cross at mid-span and weld at the
crossing, so the stage's rotation center stays put under light load — the
property a single small-length flexural pivot (SLFP) lacks. A finger tab
twists the stage ±40° between hard stops; over-twist bottoms out on plastic,
not on the beams. The brief's demo physics: PRBM crossed-beam kinematics
(virtual center), FDM fatigue orientation (layers parallel to flex), and the
compression weakness as a deliberate, invited demo — not a surprise failure.

## Given (brief #630)

| Quantity | Value | Status | Realised as |
|---|---|---|---|
| Angular ROM | ±40° | assumed (below the ~85° doc ceiling) | `stop_angle`, hard stops face-to-face; **measured bound ±0.5° off the export** (below) |
| Beam thickness `t` | 0.8 mm | assumed (≥ 2× 0.4 nozzle) | `t`, echo warns below the 0.8 floor |
| Beam free span `L` | 28 mm | assumed (derived from θ, σ ≈ E·t·θ/2L) | `L` = distance between the arcs' inner faces |
| Beam width `w` | 8.0 mm | assumed (multi-perimeter) | `w` = part height |
| Root fillet `r` | ≥ 0.5·t | **given** (doc fatigue rule) | `root_fillet`, asserted ≥ 0.5·t at the 8 ring roots **and** the 4 weld corners |
| Overall footprint | ≈ 60 × 40 × 12 | assumed | measured off the export: 61.0 × 38.5 × 12.0 |
| Hard-stop angle | ±40° vs rigid pads | assumed | arc end faces meet face-to-face at ±40° both sides |
| Coupon cycle target | ≥ 200 cycles @ ±40° | assumed | the coupon protocol (below); cycles-to-whitening is the record |
| Material | PETG default, PLA coupon twin | given | print settings; coupon ships the twins |

Style: `none` (the mechanism is the look) — honoured, no style pack.

**Open-question rulings** (all three were non-blocking; decided during the
run, recorded here):
- **Cross-axis vs cartwheel for v1:** cross-axis, planar and monolithic — the
  brief names it as the gap. A cartwheel (four-beam) variant stays open as a
  possible derivative; the two-beam X is what ships.
- **E for the echo table:** stated assumed E = 2000 MPa, carried on every
  surface that quotes a force or stress ("assumed" printed in the echo, the
  README and here). The coupon is the truth.
- **Compression-demo lever:** hand overload only — the README invites the
  axial push; no extra labelled pad parameter. `h_pad` stays the finger pad.

## Derivation — welded (pinned-crossing) model

The beams **weld** at the origin. That pin forbids the lateral drift a
pure-moment leaf assumes, so each strip is two half-beams of length `L/2`
clamped at both ends and forced into an S. Evaluated at render time (echoed;
values at the shipped defaults, E = 2000 MPa assumed):

```
I  = w·t³/12              = 8·0.8³/12           = 0.341333 mm⁴
θ  = 40°                                        = 0.698132 rad
K  = 8·E·I/L              = 8·2000·0.341333/28  = 195.047 N·mm/rad
σ_weld = 2·E·t·θ/L        = 2·2000·0.8·0.698132/28 = 79.786 MPa
σ_leaf = E·t·θ/(2L)       = 2000·0.8·0.698132/56   = 19.947 MPa  (unwelded reference)
F_handle = K·θ/tab_cx     = 195.047·0.698132/25.5  = 5.340 N
```

- **Why 8·EI/L, not 2·EI/L.** Beam-element stiffness with δ = 0 at the
  crossing: a half-beam of length ℓ = L/2 with end rotations 0 and θ/2
  carries M_weld = (4·EI/ℓ)·(θ/2) = 4·EI·θ/L. Four half-beams
  (2 strips × 2) store U = 4 · (EI θ² / L); (1/2) K θ² = U ⇒ K = 8·EI/L.
  The earlier K = 2·EI/L was the *series* leaf model (crossing free to
  drift) — the geometry the weld exists to forbid.
- **σ_weld ≈ 80 MPa** at ±40° is past PETG's ~50 MPa yield. That is an
  honest echo, not a pass/fail: full-travel cycling will whiten at the X;
  the beams are wear items and the hard stops keep a stranger from going
  further. Lower `stop_angle` or `t` if you want the nominal stress inside
  the band.
- **σ_leaf ≈ 20 MPa** is kept in the echo as the unwelded reference so the
  ~4× gap stays visible — it is *not* a property of this part.
- **Fingertip force ≈ 5.3 N** at the 25.5 mm handle: still finger-friendly
  at desk-demo scale, about 4× the leaf-model 1.3 N the page used to quote.

## Key decisions

- **Orientation (CC1, structural):** the entire part is one 2D bed-plane
  silhouette extruded up in Z to `w` = 8 (+4 finger pad on the stage tab).
  Every beam bends **in the layer plane** — stress crosses roads inside a
  layer, never the inter-layer bond. Upright beams are out of scope (brief:
  "orientation is the product"). This is why the X prints support-free with
  no mid-air spans: the "cross" is planar.
- **Rigid arcs, compliant beams:** the frame and stage arcs are 6.5 mm ring
  walls — deliberately stiff so all compliance belongs in the beams. The
  arcs' **end faces are the hard stops**: the stage arc's face meets the
  frame arc's face exactly at ±stop_angle, face-to-face over the full ring
  wall, so overload in torsion bottoms out on plastic.
- **Stop geometry derivation:** each arc spans `arc_half = (180 −
  stop_angle)/2` on its side of the frame↔stage axis, so the arcs' facing
  end faces coincide exactly at ±stop_angle — the ROM is a geometric
  consequence of the parameter, not a separate tuned clearance. This is what
  lets the ROM be a **measured bound** (below).
- **Virtual center left open:** neither arc covers the origin, and the fitcheck
  probes the four pockets flanking the crossing to keep them open. The weld
  is the only material at the crossing.
- **Root fillets by nested single-axis mirrors** — see the bug entry below;
  composed wrongly, two of eight roots silently had no fillet.
- **Weld-corner fillets (r ≥ 0.5·t)** — the four re-entrant corners of the X
  carry the same fatigue rule as the ring roots. `weld_fillets_2d()` places a
  `notch_fillet_2d` on each bisector (air angle 2·α on ±x, 180−2·α on ±y).
  Review blocker on PR #644: the page quoted leaf K/σ while the sharp weld
  was the highest-moment real estate and the coupon never saw it.

### The mirror([1,1]) fillet bug (issue #37's lesson, again)

The first fillet implementation applied both corner flips with one
`mirror([1,1])` — a reflection about y = −x. The canonical corner piece
(outside the quarter-disc, in x[−f,0] × y[0,f]) is *symmetric under that
reflection*, so the double-flipped corner came back **identical to the
unflipped one**: two of the eight beam roots silently had no fillet at all.
`printcheck` scored the part 100/100 through all of it — a missing concave
fillet is invisible to watertightness, body count and slice. The export
caught it: the mesh measurement (vertices at distance 0.6 from each expected
fillet-arc center) reported **6/8 corners carrying the arc**. The fix is
nested single-axis mirrors (`mirror([e<0?1:0,0]) mirror([0,s<0?1:0])`), and
the measurement now reports **8/8 at r = 0.6**. A render cannot measure
itself; measure the export.

### The coupon pitch bug

First coupon layout spaced specimens by `L + tab_len` — overlapping grips:
the export measured **2 bodies, not 5**, and adjacent grips were fused.
Fix: `coupon_pitch_x = L + 2·tab_len + 4` (full specimen length plus 4 mm
clearance). Measured after: 5 independent components, x-gaps 4.0 / 4.0 / 3.7
mm, row y-gap 6.0 mm.

### Label fixes

- `str(1.0)` renders "1" — a typo-looking label next to 0.6/0.8. `fmt_t()`
  appends ".0" to integral values: "0.6", "0.8", "1.0", verified in the mesh
  (third label's facet count consistent with a three-glyph string + dot).
- Labels are **embossed** 0.6 mm on the +x grip top, raised so they survive
  handling.
- **Label size now caps at what the pad fits.** Measured off the export: the
  4-glyph "PETG" at a fixed size 3 spanned 10.6 mm against the 10 mm pad and
  hung **0.30 mm of letter past each edge into mid-air** (75 vertices right,
  15 left; the 3-glyph labels fit). No gate catches a floating 0.6 mm letter
  — printcheck scored 92/100 through it and the slice succeeded — the export
  measurement found it, the same way it found the missing fillets. Fix:
  `size = min(3, (tab_len − 1)/(0.9·len(label)))`, where 0.9·size per glyph
  is the measured width constant; at the shipped defaults only "PETG"
  shrinks (3 → 2.5). Re-measured after: **0 overhang vertices on all five
  labels**, every other mesh number unchanged.

### Preview-camera findings (recorded so the next session doesn't re-derive)

- **`src=` is an OPT (field 4) in `cameras.conf`, not a define.** In the
  defines slot it becomes a no-op `-D` and the shot silently renders the
  entry `.scad` instead of the wrapper — detected by content bbox (the
  pivot's 61×38.5 mm footprint, not the strip's 152×50) and md5 A/B.
- **Embossed labels vs normal-based shading:** OpenSCAD shades by surface
  normal, and a label's readable top face is **parallel to the pad it sits
  on** — same shade — so the letters separate only via their thin dark side
  walls. A straight plan view renders them invisible (measured); the dist
  ladder 420 → 300 → 175 progressively fills the frame (~5.8 → ~10 px/mm),
  but at strip scale the walls still read as relief, not letterforms. The
  letterform proof is the separate **coupon-label** close-up (dist=45,
  ~40 px/mm), verified by read-back: "0.6", raised letterforms, correct
  orientation, not mirrored. The wide `coupon` shot stays the layout proof
  (five independent specimens, labels on pads); the two rows overlap in
  projection at the working tilt — that is the price of giving the side
  walls any contrast, and why there are two shots instead of one.

## Measured off the export (G4 evidence, `/tmp/measure_export.py`)

All numbers below are facet measurements off the exported STLs — not the
parameters — re-derived for the §6 audit:

- **Footprint:** 61.0 × 38.5 × 12.0 mm (brief ≈60 × 40 × 12: X +1.7 %,
  Y −3.8 %, Z exact; the finger pad makes Z = 8 + 4).
- **Beam cross-section** (plane slice at 10 mm along the +45° strip,
  corridor-filtered to the beam): **t = 0.800 mm, w = 8.000 mm**.
- **Arc radii** (vertex radius peaks): r_in 13.98–14.00 mm ⇒ **L = 2·r_in =
  28.0 mm**; r_out 20.48–20.50 ⇒ arc_wall = 6.5 mm.
- **Root fillets:** 8/8 ring corners carrying the r = 0.6 arc (see the bug
  entry); 4/4 weld corners carry the same r via `weld_fillets_2d()`.
- **ROM measured bound** (`ci.fitchecks`, boolean emptiness off the export):
  stage at −39.5° **empty** (clear of the frame), at +40.5° **interferes** —
  the ROM is 40° ± 0.5°, measured, not asserted. At rest the rigid bodies'
  overlap plus the pocket probes are **empty** (the mechanism is not a
  fused block); driven 5° past the stop it **interferes** (the stops bite,
  and the check can fail).
- **Coupon:** 5 independent watertight components, each 48 × 22 × 8.6 mm;
  within-row x-gaps 4.0 / 4.0 / 4.0 mm; row y-gap 6.0 mm; all five labels
  present, on their own pads, **zero overhang** past any pad edge.

**Gates:** pivot printcheck **100/100** (bodies: 1, watertight, 1452
triangles; slice 31 m 50 s, 6.79 g). Coupon **92/100** (bodies: 5,
watertight, 9136 triangles; slice 1 h 3 m, 12.94 g) — the only WARN is the
deliberate 0.6 mm coupon row below the 0.8 floor (that row exists to show
why the floor exists), plus the multiple-bodies INFO that *is* the coupon.

## §6 audit — the brief against the diff, both directions

Run at ship time over the branch's full changed-file list (Pass A `/preflight`
verdict: green except the expected hero-via-CI `readme-gate` failure the skill
sanctions; Pass B below).

**diff → brief (no creep):** every changed file serves a contract item —
`cross-axis-flexure-pivot.scad` (pivot body, brief part 1);
`cross-axis-flexure-pivot-coupon.scad` (mandatory coupon, part 2);
`ci.fitchecks` (fused-block + ROM check, part 3 — the brief prescribes this
manifest); README/NOTES/catalog/previews/shots.conf (the G3 product page and
§5 preview/hero manifests); the root README gallery row is the mechanical
regen output of adding a design (CI's regen commits the same). Nothing else.

**brief → diff (no under-delivery):** every Must-fit row → parameter →
**measured off the export** (values re-derived at ship time; see the
"Measured off the export" section above for the full bank):

| Brief row | Parameter | Measured off the export |
|---|---|---|
| ROM ±40° | `stop_angle` | fitcheck: −39.5° empty, +40.5° interferes ⇒ **40° ± 0.5°** |
| Beam t 0.8 | `t` | plane slice through a beam: **t = 0.800** |
| Beam L 28 | `L` | arc inner-face radius peaks 13.98–14.0 ⇒ **L = 2·r_in = 28.0** |
| Beam w 8.0 | `w` | same slice: **w = 8.000** |
| Root fillet ≥ 0.5·t | `root_fillet` + assert | **8/8 ring + 4/4 weld corners carry r = 0.6** |
| Footprint ≈ 60 × 40 × 12 | derived from `r_in`,`arc_wall`,`tab_*` | **61.0 × 38.5 × 12.0** (assumed row; X +1.7 %, Y −3.8 %, Z exact) |
| Hard stops ±40° vs rigid pads | arc end faces | the same ±0.5° fitcheck bound; faces meet face-to-face |
| Coupon ≥ 200 cycles, PETG/PLA | coupon strip + protocol | 5 independent components (gaps 4.0/4.0/4.0 mm), twins labelled PETG/PLA; the 200-cycle bar is a physical criterion the "Print this first" method records |
| No supports / flat / monolithic | CC1 silhouette | bodies: 1, watertight, printcheck "orientation as good as any"; bottom-iso inspected (G1) |
| K/σ echo + not-fused check | echoes + `ci.fitchecks` | welded-model echoes at render (K ≈ 195, σ_weld ≈ 80); fitcheck empty at rest, interferes 5° past |

## Print settings

- PETG default (design datum), 0.2 mm layers, 15–20 % infill, **no
  supports**, printed **flat exactly as modelled** (CC1). Seam parked off
  the thin beams if the slicer allows. Full user-facing version: README.md.

## Print this first

`cross-axis-flexure-pivot-coupon.scad` — five **straight** single-beam
specimens on one strip, straight from the production modules
(include-and-override wrapper, ≤10 lines, no copied geometry): row 0 is the
`t` ladder **0.6 / 0.8 / 1.0**, row 1 two identical production-t twins
labelled **PETG** and **PLA**. ~1 h, ≈ 13 g.

**Scope (honest):** the coupon has no crossing and no weld. It qualifies the
straight-beam `t` ladder and the material twin. The pivot's highest-stress
junction is the welded X — cycle the **production pivot** for that (hard
stops + true load path). A welded-X coupon specimen is backlog (B1), not
shipped in this round.

**Method (cycles-to-whitening, per coupon specimen):** hold one grip flat on
the desk, swing the other grip in the **layer plane** to ≈ ±40°, return,
repeat. Whitening at a root is the warning; a crack is the verdict. Record
the cycle count next to the label. ≥ 200 cycles at ±40° on the **pivot** is
the not-broken-out-of-the-gate bar, not a lifetime number.

**Tune order:**
1. **Read the ladder.** Thicker is stiffer and more stressed per degree
   (σ ∝ t at fixed angle). 0.6 is the print-quality floor demo (under two
   extrusion widths); judge production between 0.8 and 1.0.
2. **Rank PETG vs PLA** — print the strip once per material and read the
   twin named for what is loaded. The material answer is measured, not
   assumed (Domain 1: PETG ≫ PLA in cyclic flex; verify on your printer).
3. Retune the pivot: **`t`** first (K ∝ t³, σ ∝ t), **`L`** second (σ ∝ 1/L,
   free until the footprint grows), **`root_fillet`** last (keep ≥ 0.5·t at
   ring roots and weld corners, asserted). Raising `stop_angle` raises weld
   stress linearly — climb toward 60° only if the production pivot survived
   full-travel cycling.
   Sweep: `./scripts/render.sh cross-axis-flexure-pivot --sweep t=0.6:1.2:0.2`

## Deferred / out of scope

- **Cartwheel (four-beam) variant** — the brief's symmetric upgrade if
  center-shift shows up on a real print. Not modelled: it is a derivative
  (`derives.conf`) waiting for coupon evidence, per the brief's open
  question. No follow-up issue yet — file it if the coupon shows shift.
- **A measured E** for the echo table — needs a real filament's tensile data
  or a coupon calibration; until then every quoted force/stress carries
  "assumed".
- **A labelled compression-demo pad** (brief open question 3) — declined for
  v1; hand overload is the demo (README "Use"), bounded in wording to a
  millimetre or two.
- **Welded-X coupon specimen (B1)** — the straight-beam strip stays; a
  crossing specimen that tests the weld is the coupon-scope follow-up once
  field evidence says the page's honesty isn't enough.

## Field test log

*(none yet — log real prints here via `templates/FIELD-TEST.md`)*

## Status

Gates green at the shipped defaults (pivot 100/100, coupon 92/100 with only
the honest coupon WARNs; ROM measured bound ±0.5°; readme-gate pending one
CI-rendered hero shot). Draft PR open against `main`; awaiting human review —
the shape is the reviewer's call, the gates are the machine's.
