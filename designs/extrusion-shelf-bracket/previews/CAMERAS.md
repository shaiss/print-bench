# Frozen preview shots

Rendered by `./scripts/render.sh extrusion-shelf-bracket --previews` from
`cameras.conf`. **Cameras are fixed** once a reviewer has seen the shot —
before/after comparisons across rounds must align. A new region gets a new
entry, never a moved one.

| Shot | Camera (tx,ty,tz,rx,ry,rz,dist) | What it shows |
|---|---|---|
| `contact-sheet` | built-in 4-view (iso / top / front / bottom-iso) | whole part, overhang/bed-contact check |
| `iso-hero` | 0,0,0,55,0,25,320 | whole bracket front-left: both lug fins against the plate, gussets, stop lip |
| `slot-closeup` | -8,30,5,60,0,150,60 | the lower lug fin's T-outline (neck 5.7 through the mouth, head 10.4 hooking the lips) — the fit the coupon tunes |
| `coupon` | 0,30,25,55,0,25,180 (ortho) | the print-this-first coupon part alone (renders `extrusion-shelf-bracket-coupon.scad`) |

Note: OpenSCAD 2021.01 here rejects `--render` on PNG export, so no shot
uses the `render` opt; all four are preview renders of closed geometry.
