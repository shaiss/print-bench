# Jane's bench notes — print-experience reference

The facts Jane reviews against. These are *her* knowledge — cite them as
experience ("on a 0.4 that's one wobbly wall"), not as an audit of anyone
else's numbers. Defaults assume Bambu Studio stock profiles on a P2S/H2C
with a 0.4 mm nozzle; swap per the design's stated target.

## Extrusion-width arithmetic (the finding factory)

| Nozzle | Typical line width | Min. solid wall (2 lines) | Single-wall floor |
|---|---|---|---|
| 0.4 mm | 0.42–0.45 mm | ~0.85 mm | ~0.45 mm, wobbly |
| 0.6 mm | 0.62–0.68 mm | ~1.25 mm | ~0.65 mm |

- **Raised (embossed) text**: strokes < ~0.8 mm on a 0.4 nozzle print as a
  single squeezed wall — mushy corners, blobbed serifs. Legible text wants
  **≥ 0.8 mm strokes** and ≥ 0.6 mm height; sans-serif survives best.
- **Engraved (debossed) text**: a groove narrower than **2 line widths**
  (~0.9 mm on a 0.4) may be bridged over, filled by gap-fill, or reduced to
  a scratch depending on the slicer's mood. Engraved strokes at ~0.5 mm are
  a coin flip; call it.
- **Free-standing pins/posts**: below ~1.5 mm diameter they're a few
  perimeter loops with no infill — snap risk; suggest ribs or thickness.
- **V-grooves and chamfered slots**: the slicer quantizes the V into layer
  steps; below ~0.8 mm mouth width the V prints as a scratch.
- A dimension that clears every assert can still be a bad *print*. The repo
  floor (0.8 mm = 2 extrusion widths) is a floor, not a recommendation.

## First-layer reality

- First layer is squished (0.2 mm at ~0.25 width expansion): expect
  **elephant foot of 0.1–0.3 mm** outward on bed-contact edges.
- Any fit, bore, or print-in-place clearance that touches Z=0 loses
  ~0.1–0.2 mm per side to squish. A 0.35 mm PIP gap at the bed is a
  0.15–0.25 mm gap in practice — this is where "fused first print" comes
  from, and why coupons exist.
- A **0.4–0.6 mm 45° chamfer** on bed edges absorbs elephant foot and
  saves press-fits; flag its absence on any bed-contact fit.
- Textured PEI (stock on most Bambu plates) hides first-layer shine but
  costs ~0.05 mm of dimensional accuracy vs smooth.

## Stock-profile behavior (the defaults nobody changes)

- **Brim**: Bambu default is Auto ≈ 5 mm when it decides it's needed;
  OrcaSlicer draws a skirt by default. A brim cannot reach parts fully
  enclosed inside another part's outline — and when it *can* reach a
  clearance gap, it will invade it.
- **Seam**: default **Aligned** stacks every layer's seam into one vertical
  ridge — fatal on mating/sliding surfaces, ugly on show surfaces.
  Recommend Back or scarf seam in the settings section when it matters.
- **Bridge direction is the slicer's choice, not the geometry's**: auto
  bridge scoring can pick the diagonal over a square opening. If the design
  assumes a direction, the settings section must pin `bridge_angle` — and
  say "set it", not "it will".
- **Gap closing radius**: Bambu/Orca default 0.2 mm merges any gap
  narrower than that. PIP clearances at ≤ 0.5 mm deserve a troubleshooting
  line; below ~0.25 they're being actively eaten.
- **Bed fit is printable area, not nominal size**: stock X1/P1 profiles
  carve an 18 × 28 mm front-left exclusion out of the "256 bed"; the P2S
  uses the full 256². Bed-fit claims need per-printer awareness.
- **Supports weld print-in-place mechanisms.** When printcheck flags
  overhangs on a PIP design, the usual right answer is "keep auto-supports
  OFF" — and the settings section should say so, or a user will paint
  supports into the mechanism.

## Layer heights & quantization

Real preset heights: **0.12 / 0.16 / 0.20 / 0.24 / 0.28 / 0.30** — and
Bambu's draft profiles keep a **0.2 mm first layer** under 0.24/0.28, so
"n layers" claims shift on mixed profiles.

- Thin horizontal features (membranes, engrave depths, sacrificial layers)
  quantize to the layer grid: a 0.3 mm membrane at 0.2 mm layers is a
  1-vs-2-layer coin flip. Features intended as "exactly N layers" only hold
  at the layer height the README pins — check the pin exists.

## Clearance feel ladder (print-in-place, 0.4 nozzle, well-tuned machine)

| Radial clearance | What you get |
|---|---|
| < 0.15 mm | Fusion risk even on a good day |
| 0.15–0.25 mm | Snug; hot/squished first layer can weld it |
| 0.30–0.40 mm | The reliable PIP band — free after a flex |
| 0.45–0.60 mm | Loose; rattles, slaps |
| > 0.60 mm | Sloppy — only right for big/rough joints |

Vertical clearances quantize to layers (a 0.25 mm vertical gap at 0.2 mm
layers is one layer, i.e. 0.2 mm). Judge feel, not just pass/fail: a joint
can clear the fitcheck and still rattle like a maraca.

## Overhangs & bridges

- 45° is the comfort line; 45–60° prints with degraded undersides; > 60°
  droops without supports. Chamfer beats fillet on the bottom edge.
- Teardrop horizontal holes print support-free; circular ones sag flat on
  top from ~6 mm diameter up.
- Free bridges: PLA is clean to ~20 mm on stock cooling; PETG sags far
  earlier — a long PETG bridge is a lottery, say "PLA for this part".

## Materials, quickly

| Material | Bench truth |
|---|---|
| PLA | Stiff, sharp detail, best bridges. Creeps under sustained load; dies in a hot car. |
| PETG | Tough, slightly flexy, strings; sags on bridges; welds to smooth PEI; needs +0.05–0.1 mm on fits vs PLA. |
| TPU | Squishy; clearances need +0.1–0.2 mm; text detail poor. |
| ABS/ASA | Shrinks ~0.5–1 % — fits tuned in PLA come out tight; needs enclosure. |

## Reading the printcheck sticky comment

CI posts per-part **score /100, verdict, warnings, est. print time, and
filament grams**. Treat scores and slice results as settled fact. Your
value-add per warning: *does the user act on it or ignore it?* — e.g. an
overhang warning on a reeded edge = "by design, supports off"; a thin-wall
warning on a load-bearing tab = real. Print time × filament = the cost of
one failed attempt; weigh it against the coupon/insurance story.
