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
| `contact-sheet` | render.sh's standard 2×2 (iso / top / front / bottom-iso). The bottom-iso quadrant is the support-free proof: one solid bed footprint, nothing hanging over air. |
