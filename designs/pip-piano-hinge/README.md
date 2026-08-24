# pip-piano-hinge

A multi-knuckle piano hinge that comes off the print bed **already assembled and
swinging** — three separate bodies (two leaves and a free pin) printed in place,
no supports, no assembly. It's built on the repo's `lib/print-in-place.scad`
hinge profile and adds the piano-hinge-specific defenses against tolerance
stacking (`docs/advanced-techniques.md`, Domain 3).

![Studio product shot of the steel-grey 3D-printed pip-piano-hinge](previews/hero.png)

![AI-styled scene: pip-piano-hinge staged in a real-world setting](previews/lifestyle-scene.png)

*AI-generated impression for general illustration only — geometry is approximate and may not exactly match the printed part; see the studio render above and the STL for the true shape.*

![4-view contact sheet](previews/contact-sheet.png)

Folded (preview pose):

![folded pose](previews/folded-pose.png)

## What you get

- `pip-piano-hinge` — one print, 60 mm long, rendering as **3 separate
  bodies**: leaf A, leaf B, and the free pin. The pin is **round** on purpose:
  the teardrop pin you'd expect from the library jams against the bore's
  flanks past a few degrees — rotation needs a rotationally symmetric pin
  riding the bore's circular zone (the teardrop stays where it earns its keep,
  as the bore's support-free roof). The committed `fold90` check proves the
  swing on the mesh, not just in a pose.

## Print settings

- **Material:** PLA/PETG both fine (the pin bore is a sliding fit, not a live flex)
- **Layer height:** 0.2 mm (the radial clearance is split xy/z and the z gap is
  snapped to whole layers — changing layer height re-derives it)
- **Infill:** 20–40 %
- **Supports:** none needed
- **Orientation:** flat, as modelled (leaves on the bed, barrels on top, pin axis
  horizontal). The bore roofs are 45° teardrops and print supportless.
- **First use:** work the hinge back and forth once to free the knuckles.

The bore is grown from the pin's profile by a true `offset(r = clear_xy)` —
**not** a scaled teardrop, which would leave the flank planes coincident and
weld the print. Clearances are split per the physics: **0.25 mm** on the
vertical (spread-limited) surfaces, **0.40 mm** — two whole layers — on the
horizontal (sag-limited) roof and floor. Tolerance stacking is defeated with a
**per-knuckle axial clearance** (0.65 → 0.95 mm, growing along the run) plus a
`leaf_gap` between each leaf and the opposing barrels. Committed checks prove
all three bodies clear, the ≥90° fold, and that the sliced STL is really three
separate bodies (`ci.fitchecks`, `ci.fusecheck`).

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `clear_xy` | 0.25 mm | THE tunable: radial clearance on vertical bore surfaces (≥ 0.25 guarded). `clear_z` derives from it on whole layers |
| `layer_h` | 0.2 mm | print layer height — drives the `clear_z = ceil(max(clear_xy, layer_h)/layer_h)·layer_h` snap |
| `axial_gap` | 0.6 mm | base axial gap between knuckles (2× bead spread + one extrusion width) |
| `axial_err` | 0.05 mm | stacking term: each knuckle's gap grows by `(2k+1)·axial_err` along the run |
| `leaf_gap` | 0.4 mm | gap between a leaf and the opposing barrels |
| `knuckles` | 5 | number of knuckles (≥ 3), alternating leaves |
| `hinge_len` | 60 mm | overall length |
| `pin_d` | 4 mm | pin diameter (round) |

All parameters are at the top of `pip-piano-hinge.scad`; override with
`-D 'clear_xy=0.3'`. If a knuckle binds, reprint with `clear_xy` +0.05.
