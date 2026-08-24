# support-free-bracket — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 2 (designing
around supports)** and cross-cutting technique **CC1 (orientation is the master
variable)**. Tier-1 demonstrator per brief #385: one part, one idea — the part
prints with **zero support material**, and every feature that would have forced
supports in a naive design is reshaped instead.

> This supersedes the rod-holder draft that previously lived under this name
> (the directory arrived carrying it; history is in the repo). The brief's
> Must-fit rows were a shelf bracket, which that geometry failed — full
> rewrite rather than adaptation.

## Goal

A wall shelf bracket: an 80 × 50 wall plate fastened by 2 × M5 screws, with a
60 mm deep × 6 mm thick shelf arm, closing the cavity under the arm with a
**vaulted ceiling ≤ 45°** so it never prints as a bridge roof. The point of the
design is not the bracket; it is the demonstration that every support-needing
feature can be designed out.

## Given / assumed measurements

| Quantity | Value | Source |
|---|---|---|
| Plate width × height × thickness | 80 × 50 × 6 mm | given (brief) |
| Wall fasteners | 2 × M5, clearance bores | given (brief) |
| Arm depth × thickness | 60 × 6 mm | given (brief) |
| Cavity ceiling | vaulted, ≤ 45° from vertical | given (brief); modeled at **42°** — assumed margin |
| Bore positions | x = 20 / 60 mm, z = 10 / 28 mm (staggered) | assumed (stagger resists pull-out better than a vertical pair) |
| Reference load | 1 kg per bracket (loaded shelf board between two brackets) | assumed |
| Style | none | given (brief) |

## Orientation rationale (CC1)

Authored **in the print orientation**: arm flat on the bed (z = 0, its
shelf-bearing face down — so the shelf rests on the smooth first-layer face),
plate standing vertically at the back, vault brace rising between them.

This one choice is what makes everything else work:

- the arm becomes a trivial slab (largest face on the bed, zero overhang);
- the M5 bores end up **horizontal** in the print frame → they must be
  teardrops (fine — that's a demonstrated technique);
- the cavity ceiling becomes a plane whose angle is a *design parameter*
  (`vault_deg`), held ≤ 45° instead of being a flat bridge roof by accident.

**In use**, flip the print **180° about X**: the plate is still vertical
against the wall, the arm is now at the **top**, and the vault brace hangs
beneath it as the ceiling over the downward-open cavity. (A 90° rotation would
lay the plate flat — the plate is *already* vertical in the print frame; the
flip is what moves the arm from the bottom to the top.)

## Technique map (Domain 2 → this geometry)

| Naive feature | Would need supports because | Support-free form used | Where |
|---|---|---|---|
| M5 bores on a horizontal axis | round roof bridges over Ø5.5 | **teardrop**, 45° hat up | `fastener_bores()` |
| Ceiling over the arm cavity | flat ceiling = unsupported bridge roof | **42° vault** — both brace faces ≤ 45° from vertical | `vault_brace()` |
| Plate/arm bed-contact edges | sharp edge → elephant foot | 45° `bottom_chamfer` (0.8 mm) | `rounded_box()` |
| Arm-to-plate junction | bottom fillet starts horizontal, curls into an overhang | brace springs off the plate as a sloped plane — no fillet anywhere | `vault_brace()` |

## The teardrop orientation finding (issue #398)

`teardrop_hole()`'s docstring says the point faces +Z; measured on the export it
faces **−Z**. Unrotated, our bores came out with round roofs plus a downward
void spike — the exact droop this design exists to avoid. The local workaround
is the `rotate([180, 0, 0])` wrapper in `fastener_bores()`; verified on the
exported mesh: each bore's surface spans z from −2.75 mm (circle bottom) to
**+4.4 mm above centre** (the 45° hat's apex, = 0.8·d), i.e. apex **up**.
The lib fix belongs to its own PR (blast radius: aerochord, nuggs-den,
print-in-place, printability-demo) — tracked as #398.

## The printcheck caveat, measured (benign)

`gate.sh --slice` scores **92/100 — printable with caveats**, watertight, one
body. The single warning is "41 mm² unbridgeable overhang", and every flagged
facet is one of the two teardrop crowns: the lib caps the 45° hat with a blend
arc, which at `$fn = 64` tessellates into 32 facets of 1.30 mm² each (8.4–14.1°
from horizontal). Each facet spans a horizontal chord of ≈ **0.3 mm — under the
0.4 mm nozzle width** — so a single extrusion pass spans it without sagging;
printcheck's own overhang *area share* rounds to 0%. Accepted with this
measurement rather than traded away: a knife-edge teardrop needs the #398 lib
change, not a design change. Test-slice (supports disabled): OK, ~3 h 44 m,
46.7 g.

## Rib-on-arm decision (left to modeling time by the brief)

**No rib.** The vault brace *is* the arm's stiffener — it ties the full 80 mm
width of arm to the plate continuously, strictly better than a discrete rib.
The only span a rib could add is the ~26 mm arm tip cantilever beyond the
vault foot (arm ends at y = 66, vault foot at y ≈ 40); at the 1 kg reference
load that span sees negligible bending (~0.6 N·m at the plate, carried as
compression down the 80 × 8 mm vault band ≈ 1.2 MPa — an order below any
filament's strength). A rib on the arm's underside would also hang into the
cavity, shrinking the clear opening the vault spans, and would need its own
self-support analysis at the vault face. Rejected; revisit only if a field
test shows tip deflection.

## Guards (asserts in `main()`)

- `vault_deg ∈ (0, 45]` — the design invariant; a steeper ceiling needs supports
- `web_out_foot_y ≤ arm tip − 4` — the brace foot stays on the arm
- upper bore teardrop apex ≤ vault springing − 2 — bores never breach the vault
- lower bore ≥ 3 mm off the bed; bores ≥ 3 mm from the plate ends (screw heads)
- `arm_t ≥ 4` — three perimeters plus infill

## Use-frame dimensions

Overall in use: **80 wide × 60 deep × 50 tall** (as printed: 80 × 66 × 50 —
plate 6 + arm 60 along Y). Bores sit 10 mm and 28 mm below the shelf line,
heads landing inside the cavity (no counterbore needed for socket heads). The
cavity opens down and out — ≈ 27 mm deep × 30 mm tall clearance — so nothing
collects on the vault.

## Status log

- v0 (superseded): rod-holder draft, pre-brief.
- 2026-08-24 — full rewrite to the brief #385 geometry. Iteration 1 (no bores)
  scored 100/100; iteration 2 (teardrop bores, #398 workaround) 92/100 with the
  benign crown caveat above, `gate.sh --slice` exit 0, test-slice OK. G1/G2
  green; preview shots frozen (`previews/cameras.conf`, descriptions in
  `previews/CAMERAS.md`). Found #398 (teardrop sign) and #400 (render.sh
  `--render` argv bug) on the way.

## Print-orientation reminder for reviewers

Do **not** "improve" this by adding a fillet at the arm/plate junction or on
the vault edges — a bottom fillet is exactly the overhang this design exists
to avoid. The chamfers and the vault angle are load-bearing.
