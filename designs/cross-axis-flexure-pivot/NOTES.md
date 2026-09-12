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
| Root fillet `r` | ≥ 0.5·t | **given** (doc fatigue rule) | `root_fillet`, asserted ≥ 0.5·t; measured 8/8 corners at r = 0.6 |
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

## Derivation — the doc's relations, not guesses

Evaluated at render time (echoed; values at the shipped defaults):

```
I  = w·t³/12            = 8·0.8³/12      = 0.341333 mm⁴
K  = 2·E·I/L            = 2·2000·0.341333/28 = 48.7619 N·mm/rad
θ  = 40°                                 = 0.698132 rad
σ_doc = E·t·θ/(2L)      = 2000·0.8·0.698132/56 = 19.9466 MPa  (pure-moment ideal)
σ_pk  = 2·σ_doc                          = 39.8932 MPa  (×2 bound: a real S-bend
                                                          brackets these)
F_handle = K·θ/tab_cx    = 48.7619·0.698132/25.5 = 1.33499 N at r = 25.5 mm
```

- **K = 2·E·I/L**, not E·I/L: each strip is two half-beams in series through
  the welded crossing (EI/L per strip, the doc's pure-moment leaf value), and
  the two strips act in parallel.
- The **×2 stress bound** brackets the real deflected shape: the pure-moment
  ideal is the floor, a tip-loaded S-bend the ceiling. At the bound the root
  sits at ~0.8 × PETG's ≈50 MPa yield at full travel — static-safe, cyclic
  marginal, which is exactly what the coupon ladder is for.
- **Fingertip force 1.33 N** at the 25.5 mm handle radius: firm but
  comfortable at desk-demo scale — the brief's "feel a pinless hinge" target.

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
- **Root fillets:** 8/8 corners carrying the r = 0.6 arc (see the bug entry).
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
| Root fillet ≥ 0.5·t | `root_fillet` + assert | **8/8 corners carry the r = 0.6 arc** |
| Footprint ≈ 60 × 40 × 12 | derived from `r_in`,`arc_wall`,`tab_*` | **61.0 × 38.5 × 12.0** (assumed row; X +1.7 %, Y −3.8 %, Z exact) |
| Hard stops ±40° vs rigid pads | arc end faces | the same ±0.5° fitcheck bound; faces meet face-to-face |
| Coupon ≥ 200 cycles, PETG/PLA | coupon strip + protocol | 5 independent components (gaps 4.0/4.0/4.0 mm), twins labelled PETG/PLA; the 200-cycle bar is a physical criterion the "Print this first" method records |
| No supports / flat / monolithic | CC1 silhouette | bodies: 1, watertight, printcheck "orientation as good as any"; bottom-iso inspected (G1) |
| K/σ echo + not-fused check | echoes + `ci.fitchecks` | echoes at render; fitcheck empty at rest, interferes 5° past |

## Print settings

- PETG default (design datum), 0.2 mm layers, 15–20 % infill, **no
  supports**, printed **flat exactly as modelled** (CC1). Seam parked off
  the thin beams if the slicer allows. Full user-facing version: README.md.

## Print this first

`cross-axis-flexure-pivot-coupon.scad` — five single-beam specimens on one
strip, straight from the production modules (include-and-override wrapper,
≤10 lines, no copied geometry): row 0 is the `t` ladder **0.6 / 0.8 / 1.0**,
row 1 two identical production-t twins labelled **PETG** and **PLA**. ~1 h,
≈ 13 g.

**Method (cycles-to-whitening, per specimen):** hold one grip flat on the
desk, twist the other grip in the **layer plane** to ≈ ±40° (match the
pivot's stop), return, repeat. Whitening at a root is the warning; a crack
is the verdict. Record the cycle count next to the label. The brief's bar is
≥ 200 cycles at ±40°; the production row (0.8 PETG) is the one that must
clear it.

**Tune order:**
1. **Read the ladder.** 0.6 is under the 0.8 floor on purpose — expect it to
   feel best and die first. 1.0 is the durability ceiling at this L (and the
   stress ceiling per degree).
2. **Rank PETG vs PLA** on the twins — the material answer is measured, not
   assumed (Domain 1: PETG ≫ PLA in cyclic flex; verify on your printer).
3. Retune the pivot: **`t`** first (K ∝ t³, σ ∝ t), **`L`** second (σ ∝ 1/L,
   free until the footprint grows), **`root_fillet`** last (keep ≥ 0.5·t,
   asserted). Raising `stop_angle` raises root stress linearly — climb
   toward 60° only if a coupon row survived.
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
  v1; hand overload is the demo (README "Use").

## Field test log

*(none yet — log real prints here via `templates/FIELD-TEST.md`)*

## Status

Gates green at the shipped defaults (pivot 100/100, coupon 92/100 with only
the honest coupon WARNs; ROM measured bound ±0.5°; readme-gate pending one
CI-rendered hero shot). Draft PR open against `main`; awaiting human review —
the shape is the reviewer's call, the gates are the machine's.
