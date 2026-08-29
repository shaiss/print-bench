# Frozen preview cameras

Shot descriptions for `cameras.conf`. Cameras are frozen now that the PR is up:
before/after comparisons across review rounds must align, so a new region gets a
**new** `cameras.conf` line — never move or reframe an existing one
(`./scripts/render.sh compliant-gripper --previews` re-renders them all).

| Shot | What it shows |
|---|---|
| `hero3q` | The 3/4 hero: the whole flat mechanism — parallel jaw pads at the right, leaf flexures, arch beam along the far edge, push tab at the left. The shape a reviewer reacts to first. |
| `top-plan` | Steeply tilted top view (30° off vertical — straight-down renders as a flat silhouette): the mechanism *layout*. Jaw gap, plunger channel with the diagonal notches, arch beam and detent wing all readable in one frame. |
| `cam-closeup` | The actuator cam: the diagonal edge-notch cut into the plunger blade, with a pin post riding in it. The feature that converts tab push into parallel jaw travel. |
| `detent` | The bistable detent: the pre-buckled arch beam dipping along the edge, its tip over the ramp/crest/valley tooth profile on the plunger wing. The feature that holds the clamped state. |
| `side-section` | Added round 2 (Jane's freeze-window ask): a cross-section at the detent station (`part="side_section"`, keeps x ≥ 65), looking at the cut face. The one angle that shows the z-stack — leaves floating 2 layers over the pocket floor, the wing table 2 layers over the leaf tops, the wing band and tooth 2 layers over the table, the arch beam 2 layers over the corridor shelf, the blade 2 layers over the base. Fixed-over-air, the defect class round 1 blocked on, is visible here and only here. |
| `loaded` | Added round 2 (Drik's "no preview shows it holding anything"): the LOADED pose (`part="loaded"`) — the as-printed part with a Ø 25 mm prop rod (a cut-dowel segment, the as-shipped grip size) lying in the trough between the jaws, tail overhanging the base's front edge. The jaws sit at their printed OPEN pose (gap 33 mm), so the 4 mm running clearance per side is honest; the rod is a camera prop, never a printable part. The one frame that answers the stranger's "will it hold *my* rod?" |
| `loaded-end` | Added round 3 (Jane's companion ask): the `loaded` pose from a low, near-axial **end view** down the trough — the angle the `loaded` shot hides. Orthographic on purpose: a perspective axial view lets the overhanging tail's end cap swallow the gaps. The rod's cross-section reads as a circle seated between the two pad faces, with the 4 mm per-side running daylight visible as the slots beside it — the open-pose fit, in committed bytes. Same prop-rod caveat as `loaded`: never a printable part. |
| `contact-sheet` | render.sh's standard 2×2 (iso / top / front / bottom-iso). The bottom-iso quadrant shows the bed face: one solid footprint. It cannot show z-stacking above the base skin — that is what `side-section` is for. |
