# Frozen preview cameras — pip-micrometer-vice

Per-shot descriptions for `cameras.conf` (format in `scripts/render.sh`).
Cameras are **fixed** once a reviewer has seen a shot; a new region gets a new
`cameras.conf` line, never a reframed existing one.

| Shot | What it shows |
|---|---|
| `contact-sheet` | The 2×2 iso / top / front / bottom-iso of the printable assembly at the print pose (opening 12). The bottom-iso quadrant is the flat-bed / no-support proof: everything flat or steeply overhung, nothing printing on air. |
| `vice-top` | Straight down over the whole vice: the working gap between the two 40-wide jaw faces, the screw thread crossing the moving jaw's nut boss, the rails, and the two M5 holes on the 40 mm x-grid. |
| `section` | The cutaway (`part="cutaway"` removes the +y half), from +y in 3/4: the guide bore tunnel with the screw shaft inside it, the sealed thrust-collar chamber, the thread interleaved with the moving jaw's nut (the serrated band crossing the jaw), and the centre saddle under the screw's exposed underside — the whole support story in one view. |
| `jaws` | Close 3/4 on the working end from above: both jaw faces and the opening, the moving jaw straddling the saddle, the thread emerging past the jaw toward the rear block. (The knob sits on the far side of the rear block from this angle — see the contact sheet's iso.) |
| `coupon` | The print-this-first coupon in 3/4 from the thread-row side: thread row (digits 1/2/3 = `thread_tol` 0.25/0.30/0.35, production = 2) near, guide row (letters A/B/C = `clr_h` 0.25/0.30/0.35, production = B) far, digits cut into the nut front faces (facing this camera), letters into the slider tops. |
