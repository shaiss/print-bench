# Frozen preview shots

Rendered by `./scripts/render.sh extrusion-spool-holder --previews` from
`cameras.conf`. **Cameras are fixed** once a reviewer has seen the shot —
before/after comparisons across rounds must align. A new region gets a new
entry, never a moved one.

| Shot | Camera (tx,ty,tz,rx,ry,rz,dist) | What it shows |
|---|---|---|
| `contact-sheet` | built-in 4-view (iso / top / front / bottom-iso) | whole peg as printed — overhang/bed-contact check |
| `peg-hero` | 23,0,51,60,0,30,320 | three-quarter hero: blade T-lugs + plate at the base, trunk flare, Ø58 seat shoulder, hollow stub with its open bore |
| `peg-bed` | 23,0,51,235,0,55,470 | print pose from below: the two hammer-head lugs flat on the bed, the plate bridging onto the blade web, the stub standing vertical |
| `coupon` | 111,0,5,60,0,15,560 | the print-this-first coupon alone (renders `extrusion-spool-holder-coupon.scad`): lug strip + the 0.3/0.6/0.9 bore-clearance ring sweep |
| `lug-closeup` | 23,0,8,90,0,90,120 | dead-on along the blade at bed level: the T-lug profile reads as a T — head 10.4 wide over the 5.7 neck — with the plate spanning wider above and the trunk rising out of frame |

Framing was verified by measuring each render's content bounding box
(ImageMagick `%@`): every shot keeps ≥49 px of margin on all four edges —
except `lug-closeup`, where the stub intentionally runs off the top of the
frame (the close-up is about the T profile at bed level; T0 is that choice,
not a miss — the other three edges hold L84/R84/B305). Not by eye — this
part is tall and looms under perspective, and eyeballed distances both
under- and overshot before the pixel rule settled it.
