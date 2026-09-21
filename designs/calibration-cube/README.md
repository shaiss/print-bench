# calibration-cube

A 20 mm test cube for checking your printer's dimensional accuracy — and the
starter design demonstrating this repo's parameter conventions. The bottom
edges carry a 0.6 mm 45° chamfer so the first layer releases cleanly, and the
top face is engraved with the cube's edge length, so every print labels its
own intended size.

![Product shot: the printed cube, satin orange PLA on a studio backdrop](previews/product-hero.png)

![AI-styled scene: calibration-cube staged in a real-world setting](previews/lifestyle-bench-calipers.png)

*AI-generated impression for general illustration only — geometry is approximate and may not exactly match the printed part; see the studio render above and the STL for the true shape.*

![Product shot: the engraved 20 mm size marker, high three-quarter view, satin orange PLA](previews/size-marker.png)

![Turntable: chamfered bottom edges and the engraved size marker](previews/turntable.gif)

![AI-styled scene: calibration-cube in motion, staged in a real-world setting](previews/lifestyle-turntable.gif)

*AI-generated motion impression for general illustration only — geometry is approximate and may not exactly match the printed part, and the movement shown is illustrative, not a simulation; see the deterministic previews above and the STL for the true shape.*

![4-view contact sheet](previews/contact-sheet.png)

## What you get

No assembly. Two ways to print:

- `cube` — the starter single cube, 20 × 20 × 20 mm at default settings
  (`size` is parametric), with chamfered bottom edges and the edge length
  engraved 0.4 mm deep into the top face.
- **Multi-size strip** — four separate cubes (5 / 10 / 20 / 30 mm), each
  labeling its own size. They print as distinct objects on one plate, not
  a fused bar.

**Deliverable for the strip.** STL carries no object separation, so the
printable strip is the multi-object 3MF from
`./scripts/plate.sh calibration-cube`
(`build/calibration-cube-plate.3mf`). Import that, or import the four part
STLs and keep them as separate objects. Lay them **side by side and flat**.

## Print settings

- **Material:** any — use the filament you want to calibrate
- **Layer height:** 0.2 mm or finer (the engraved marker is sized to survive
  slicing at 0.2 mm layers)
- **Infill:** 100% if you'll check dimensional accuracy under load; otherwise
  your usual default
- **Supports:** none needed
- **Orientation:** as modeled — flat face down

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `part` | `cube` | `cube` (parametric), `cube5`/`cube10`/`cube20`/`cube30` (fixed strip sizes), or `sweep` (layout preview) |
| `size` | 20 mm | Edge length of the `cube` part; the engraved marker updates to match (ignored by fixed-size parts) |
| `bottom_chamfer` | 0.6 mm | 45° chamfer on the bottom edges so the first layer releases cleanly (0 to disable) |
| `$fn` | 64 | Curve resolution — 32 while iterating, 64+ for production |

All parameters are at the top of `calibration-cube.scad`, grouped in
Customizer sections; override on the command line with `-D 'size=25'` or
`-D 'part="cube10"'`.

## Assembly & use

Nothing to assemble. Print a cube (or the strip plate), then measure the
X, Y, and Z faces with calipers and compare against the number engraved on
top. If you want a different single reference size, change `size` and
reprint — the marker follows automatically. The strip gives four reference
sizes in one print so you can see whether error scales with size.

Design rationale and modeling decisions live in [NOTES.md](NOTES.md).
