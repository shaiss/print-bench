# Preview cameras

Every shot regenerates with `./scripts/render.sh gridfinity-starter
--previews`. Cameras are frozen once reviewed; a new region to show is a new
line in `cameras.conf`, never a moved camera.

| Shot | What it shows |
|---|---|
| `contact-sheet` | The 4-view sheet (iso / top / front / bottom-iso) of the assembled preview — overall shape and bed-side overhang check |
| `iso` | Assembled hero angle: 3×3 plate with the 2×1 and 1×1 3U bins and two 1U trays seated, one column of sockets left empty so the grid is visible. Embedded in README |
| `top` | Straight-down assembled view — grid alignment, empty sockets, bin placement |
| `plate-bedface` | The baseplate's bed face viewed square-on (print orientation, grid-down): the 3×3 socket mouths opening at the bed and the four M4 counterbores in the margin — the face a reviewer must check for the grid-down print. Square-on, not oblique: at 55° the funnel walls self-shadow and the face reads illegibly dark |
