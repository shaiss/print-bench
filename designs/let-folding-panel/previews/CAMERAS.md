# Frozen preview cameras — what each shot shows

Rendered by `./scripts/render.sh let-folding-panel --previews` from
`cameras.conf`. Cameras are frozen across review rounds; a new region to
show gets a new camera entry, never a moved one.

| Shot | Shows |
|---|---|
| `contact-sheet` | The as-printed flat part: 2×2 iso / top / front / bottom-iso. This is the bed-side-up geometry the slicer sees — one flat sheet, panels at 3 mm, hinge zone thin. The bottom-iso quadrant is the overhang/bed-contact check (there is nothing to support: it prints flat). |
| `folded-pose` | The brief's fold-to-90° evidence: panel B posed at `demo_fold=95` (just past vertical so the hinge line reads clearly), panel A flat. The interdigitated fingers and the thin torsion bar are visible where the panels meet. Preview-only pose — the printed part is always `demo_fold=0`. |
| `hinge-closeup` | The joint itself, close enough to judge: the 2 mm torsion bar between interdigitated fingers, the root fillets at each finger↔bar junction, and both panels' 1.2 → 3.0 mm Z-step edges in frame for scale. This is the frozen before/after frame for any change to `r`, `finger_w`, `w` or `L`. As-printed flat (`demo_fold=0`). |
