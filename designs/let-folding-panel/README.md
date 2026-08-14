# let-folding-panel

Two rigid panels joined by a **Lamina-Emergent Torsional (LET) joint** — a
compliant hinge fabricated flat from a single sheet that folds up to ~90° with
zero clearance, zero assembly and no rattle. LET joints are the best flexure
match for FDM because they print dead flat (`docs/advanced-techniques.md`,
Domain 1, lamina-emergent family).

![Studio product shot of the teal 3D-printed let-folding-panel](previews/hero.png)

![AI-styled scene: let-folding-panel staged in a real-world setting](previews/lifestyle-scene.png)

*AI-generated impression for general illustration only — geometry is approximate and may not exactly match the printed part; see the studio render above and the STL for the true shape.*

![4-view contact sheet](previews/contact-sheet.png)

Folded to ~90° (preview pose — the printed part is always flat):

![folded pose](previews/folded-pose.png)

## What you get

- `let-folding-panel` — one flat part, ≈ 56 × 46 × 2 mm, that folds along its
  centre.

## Print settings

- **Material:** PETG / PP / nylon / TPU (they fold for many cycles). **Not PLA**
  — it cracks at a live flexure.
- **Layer height:** 0.2 mm
- **Infill:** 100 % or high perimeters (it's a thin sheet)
- **Supports:** none — it's flat
- **Orientation:** flat on the bed (the only orientation). The torsion strip
  twists in the layer plane, which is what makes the joint durable.

How it works: a thin **torsion strip** on the fold line is reached by each panel
through interdigitated **fingers**. Folding twists the strip segments between
fingers (torsion) and bends the finger roots — high range of motion, low stress.

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `strip_w` | 2.2 mm | torsion-strip width — **highest-leverage** stiffness knob (thinner = softer) |
| `fingers` | 9 | more fingers = softer joint (distributes strain) |
| `finger_reach` | 6 mm | bending length of the finger roots |
| `sheet_t` | 2.0 mm | whole-sheet thickness |

All parameters are at the top of `let-folding-panel.scad`; override with
`-D 'strip_w=1.6'`. `demo_fold` is a preview pose only — print at 0.
