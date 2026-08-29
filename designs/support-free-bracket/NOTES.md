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
| Bore positions | x = 20 / 60 mm, z = 11 / 18 mm (staggered) | assumed (stagger resists pull-out better than a vertical pair); moved from 10 / 28 for socket-head envelope clearance (round 2), then upper 25 → 18 for the hex-key driver envelope (round 4) — see the two findings below |
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

## The teardrop orientation finding (issue #398 — closed by #424; workaround removed)

At authoring time `teardrop_hole()`'s docstring said the point faces +Z but the
export measured it facing **−Z**. Unrotated, our bores came out with round
roofs plus a downward void spike — the exact droop this design exists to
avoid — so this branch carried a local `rotate([180, 0, 0])` workaround in
`fastener_bores()`. Main's **#424** then fixed the lib to the documented +Z
(pinned by `lib/printability-mates.conf`'s gauge plug), which turned the local
flip into a **double-flip**: on the merged tree the cutter cut point-down
again, measured on the export (a probe box inside the would-be +Z apex void
came back solid; its −Z mirror came back void). The workaround is removed and
the bores use the lib orientation directly — re-verified on the merged export:
the apex void sits **+4.4 mm above centre** (0.8·d) and the region below the
bore is solid, i.e. apex **up**, no downward spike.

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
- **socket-head envelope** (added in the PR #401 review round — the guard whose
  absence let the 10/28 bore heights through): the lower head rim clears the
  arm face (`bore_z_lo − head_d/2 ≥ arm_t`) and the upper head rim clears the
  vault ceiling plane (`bore_z_hi + head_d/2 ≤ web_in_z − head_h/tan(vault_deg)`),
  head envelope from `socket_head()` incl. its 0.5 mm diameter clearance
- **tool envelope** (added in round 4 — the guard whose absence let 25 seat a
  screw no key could drive): at each bore, the straight run from the hex
  recess floor to the vault ceiling plane must be ≥
  `tool_run·(cos(tool_tilt) − sin(tool_tilt)·tan(vault_deg))` — derivation
  and measurements in the tool-envelope finding above

## Use-frame dimensions

Overall in use: **80 wide × 60 deep × 50 tall** (as printed: 80 × 66 × 50 —
plate 6 + arm 60 along Y). Bores sit 11 mm and 18 mm below the shelf line,
heads landing inside the cavity. No counterbore is needed **because the bore
heights place the head envelope**, not because it was never checked: the
review round measured a max-spec M5 socket head fouling the arm underside by
0.25 mm at the old 10 mm bore and the vault ceiling by ~2 mm at the old 28 mm
bore, so the bores moved to 11 / 25 and the head-envelope guards now refuse
any placement where the head rim would touch the arm face or the vault plane.
The cavity opens down and out — ≈ 27 mm deep × 30 mm tall clearance — so
nothing collects on the vault.

### The head-envelope finding, measured (PR #401 review round)

Both reviewers converged on the defect (the guards covered the teardrop apex
and the bed, never the hardware): at 10 / 28 an ISO 4762 M5 head (d 8.5, k 5)
interferes on both bores. The review's sanctioned lower-bore move was
**10 → 9, which has the sign inverted**: `bore_z_lo` is height on the bed and
the arm face sits at z = `arm_t` = 6 *below* the bore, so moving down moves
the head *into* the arm. Measured by intersecting the d 8.5 head envelope
(y = 6→11) with the exported mesh: z = 9 interferes **25.9 mm³**, z = 10
interferes 2.4 mm³ (the 0.25 mm kiss), z = 11 is **clear** — so the landed
move is 10 → **11**, and the new lower-head guard refuses both 9 and 10.
Upper bore per the sanctioned route: 28 → **25**; the d 8.5 envelope at 25
measures zero interference against the vault, with the guard holding
0.95 mm of margin on the preset envelope. (25 was itself superseded in
round 4 — the head fit but its *driver* did not; next section.)

### The tool-envelope finding, measured (PR #401 round 4)

The round-2 guards place the **head**; nothing placed the **tool**. The vault
ceiling plane closes over a bore at `y(z) = plate_t + (web_in_z − z)·tan 42°`,
and the hex key's short arm needs its straight run along the bore axis, out
of the head's hex recess (floor ≈ 0.5 mm above the seat — a socket cap is
drilled nearly through — so the run starts at y ≈ 6.5; the hex *mouth* is at
y = 6 + 5 = 11). At the old `bore_z_hi = 25` the ceiling sits at y ≈ 15.9, a
run of **~9.4 mm** — a 4 mm L-key's short arm is **17–19 mm** tip-to-elbow,
so the screw seats but cannot be driven.

The fix drops `bore_z_hi` 25 → **18** and adds the tool-envelope guard.
Derivation of the guard's inequality: a key tilted down by `tool_tilt` spans
only `tool_run·cos(tool_tilt)` of run, and its elbow drops
`tool_run·sin(tool_tilt)` into the open cavity below the bore, where the
ceiling sits `tan(vault_deg)` farther out per mm dropped — so the run needed
is `tool_run·(cos(tool_tilt) − sin(tool_tilt)·tan(vault_deg))` = 17 ×
(cos 10° − sin 10°·tan 42°) = **14.08 mm**. Measured at 18 on the exported
mesh (thin-slab intersection across the bore axis at z = 18): ceiling entry
y = **22.16**, run = **15.66 mm** — a 17 mm short arm clears at ~4.7° of
tilt, the conservative 19 mm arm at ~10.1°, and the guard holds 1.6 mm of
run margin. Negative control: with `bore_z_hi = 25` the assert fires
("hex-key run at bore z=25 is 9.40444 mm; the tilted short arm needs
14.0837 mm") and the render aborts. Trade accepted: the stagger drops
14 → **7 mm**; pull-out resistance still beats a level pair.

## Status log

- v0 (superseded): rod-holder draft, pre-brief.
- 2026-08-24 — full rewrite to the brief #385 geometry. Iteration 1 (no bores)
  scored 100/100; iteration 2 (teardrop bores, #398 workaround) 92/100 with the
  benign crown caveat above, `gate.sh --slice` exit 0, test-slice OK. G1/G2
  green; preview shots frozen (`previews/cameras.conf`, descriptions in
  `previews/CAMERAS.md`). Found #398 (teardrop sign) and #400 (render.sh
  `--render` argv bug) on the way.
- 2026-08-29 — PR #401 review round landed: merged main (bringing #424's
  `teardrop_hole()` +Z fix), removed the local `rotate([180, 0, 0])`
  workaround it had turned into a double-flip (apex re-verified up on the
  merged export), moved the bores 10 / 28 → 11 / 25 for socket-head envelope
  clearance (the lower move corrected from the reviewed 10 → 9, whose sign
  was inverted — measurements above) and added the two head-envelope guards.
  README: material line split (PLA vs PETG/ASA + textured-plate note), seam
  line added, load claim de-rated to "assumed, no field test", L-key/anchor
  install sentence added, counterbore claim grounded in the guards.
- 2026-08-29 — round 4 (tool access): `bore_z_hi` 25 → 18 — at 25 the screw
  seated but could not be driven (~9.4 mm of run vs the 17–19 mm a 4 mm
  L-key short arm needs; measurements in the tool-envelope finding) — and
  the tool-envelope guard landed beside the head-envelope pair, negative
  control proven (assert fires at 25). Stagger 14 → 7 mm, trade accepted.
  Cameras: two NEW frozen lines, `bore-detail` (one teardrop close up, arm
  edge in frame for scale) and `side-elevation` (true orthographic side);
  existing lines untouched, with CAMERAS.md wording honesty touches on
  `bottom-iso` (plate edge hides the teardrop roofs) and `side-vault`
  (a soft 3/4, not an elevation).

## Print-orientation reminder for reviewers

Do **not** "improve" this by adding a fillet at the arm/plate junction or on
the vault edges — a bottom fillet is exactly the overhang this design exists
to avoid. The chamfers and the vault angle are load-bearing.
