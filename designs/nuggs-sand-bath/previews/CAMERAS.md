# Frozen preview cameras — nuggs-sand-bath

Cameras are **fixed** once a reviewer has seen them (see CLAUDE.md, Design
conventions). A new region gets a NEW line in `cameras.conf`; never move or
reframe an existing one. Descriptions below say what each shot exists to show.

| Shot | Part | What it shows |
|---|---|---|
| `contact-sheet` | default (`body`) | 2×2 contact sheet of the as-printed default pose — iso / top / front / bottom-iso. The bottom-iso quadrant is the overhang/bed-contact check. The default part is the printable `body`, never a preview pose. |
| `hero` | `hero` | Use pose (rotate 90° of the same solid): mouth up, port horizontal in the run wall — the bath as mounted at the end of a run, the open trough and its fill line legible from above. |
| `cutaway` | `cutaway` | Half-section on the run-axis plane (x = 0), cut face to camera: bore at the bottom, the 42.27° beach ramp up to the flat sand floor, the sloped far wall rising to the rim. Full `render` (CGAL) so the section face is solid. |
| `print-pose` | `body` | The body as it stands on the bed, from below: port-down on the three sector tips, both staged widening skirts (tube → circle → dish) visible between the tube and the trough. The bed-contact and support picture (see NOTES.md, Print settings). |
