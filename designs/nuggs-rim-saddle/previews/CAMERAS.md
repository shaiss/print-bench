# Frozen preview cameras — nuggs-rim-saddle

Cameras are **fixed** once a reviewer has seen them (see CLAUDE.md, Design
conventions). A new region gets a NEW line in `cameras.conf`; never move or
reframe an existing one. Descriptions below say what each shot exists to show.

| Shot | Part | What it shows |
|---|---|---|
| `contact-sheet` | default (`body`) | 2×2 contact sheet of the as-printed default pose — iso / top / front / bottom-iso. The bottom-iso quadrant is the overhang/bed-contact check. The default part is the printable `body`, never a preview pose. |
| `hero` | `assembled` | The whole saddle clamped on the rim, seen from the outboard/tank side: the inclined tube, the bridge straddling the rim, both arms strapped down the outer face. The shape a stranger sees first. |
| `cutaway` | `cutaway` | Half-section along the bore-axis plane (y = 0): the 15° bore running straight from port face to mouth — the internal ramp IS the tube invert (one straight inclined bore, no step). Full `render` (CGAL) so the section faces are solid. |
| `cutaway-tight` | `cutaway` | The same section framed tight (added per review — the frozen `cutaway` wide shot stays): the 15° bore filling the frame, port face to mouth, so the design's central claim is legible at a glance. Full `render` (CGAL) like `cutaway`. |
| `clamp` | `assembled` | Close-up of the latch from outboard: one strap arm descending the outer skirt, its pad bearing the frame lip, the hook latched under the skirt-foot flange. |
| `print-pose` | `body` | The body as it stands on the bed, from below: port-down on the three sector tips, the shell growing out of the vertical tube. The bed-contact and support picture (see NOTES.md, Print settings). |
