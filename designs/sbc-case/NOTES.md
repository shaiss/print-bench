# sbc-case — engineering log

## Goal

A hardware-rich single-board-computer case (Raspberry Pi 4 primary target) that
is deliberately the **reference / stress-test design for the
assembly-instructions feature** (issue #158): it ships an `assembly.conf`
declaring real `vitamin:` entries — board, inserts, three screw types, washers,
fan — so it exercises the NopSCADlib vitamin path, the BOM collection pass, and
the GPL-3.0 product-page disclosure no existing design carries.

Second goal, from the brief: the board standoff pattern is **generated from
`pcb_screw_positions(RPI4)` at build time**, never hand-typed — proven by a
boolean fitcheck (`fit-pins`), not by restating the formula.

## Given / assumed measurements

**Given** — everything the case is sized *around* comes from the vendored
NopSCADlib vitamins (the brief's named source), read at build time:

| item | value (from the vitamin) |
|---|---|
| RPI4 outline | 85 × 56 × 1.4 mm |
| RPI4 mounting holes | Ø2.75, at x = −39 / +19, y = ±24.5 (58 × 49 pitch, pattern centred at x = −10 — verified by the render echo, not assumed) |
| usb_Ax2 (stacked USB-A) | body to x = +44.5 (2.0 past the board edge), 15.6 tall |
| rj45 (Ethernet) | body to x = +44.5, 13.5 tall |
| usb_C (power) | body to y = −29.575 (1.6 past the board edge) |
| 2×20 GPIO header | at (−10, +24.5), ~8.5 above the board |
| `fan40x11` | 40 × 40 × 11, bore Ø37, hole pitch 16 mm (32 mm across), M3 screws |
| `F1BM3` insert | Ø4.0 melt-in hole × 5.8 long, M3 thread |
| `M2p5_cap_screw` | pilot (tap) radius from `screw_pilot_hole()` |

**Assumed** (stated defaults, tunable in the Customizer):

- wall 2.0, floor 2.0, lid plate 2.5 mm — a rigid case, 3–4 perimeters at 0.4 nozzle
- `board_clr` 0.75 mm board-to-wall clearance
- `standoff_h` 5 mm (brief allows 4–6; 5 clears under-board pin headers)
- `interior_h` 24 mm = standoff 5 + board 1.4 + tallest connector 15.6 + ~2 spare
- `fit_clearance` 0.25 mm on the lid register lip — the number the coupon tunes
- fan centred at (−10, 0), biased toward the RPI4 SoC (the hot part)
- `fan40x11` (the vendored catalog's 40 mm fan; the brief's "40×10" was an
  assumption the brief explicitly allowed swapping for the catalog value)

## Key decisions

1. **Standoffs from the vitamin, not typed.** `translate([0,0,board_z])
   pcb_screw_positions(board) standoff();` — retargeting `board` re-generates
   the pattern. `ci.fitchecks` proves it on the export: pins at the same
   generated positions pass through the printed pilots (`fit-pins` empty);
   the same pins shifted 0.6 mm must interfere (`fit-pins-shift`).
2. **Board fastener: M2.5 cap screws into printed pilots, not inserts.**
   `F1BM2p5` exists in the vendored tree (the brief assumed it didn't) but is
   5.8 mm long — taller than the 5 mm standoff it would live in. The brief left
   the choice open ("screw into boss" vs "insert"); the boss won on that
   measurement. Noted here because it contradicts a factual claim in the brief.
3. **Three open edges above a 6.5 mm skirt.** +X (USB-A ×2 / Ethernet), −X
   (micro-SD), −Y (USB-C / 2× micro-HDMI / audio jack) are open above the
   skirt, so every cable connector — which overhangs the board edge by up to
   2.0 mm — enters through a gap, not a tight hole. The skirt top (6.5) sits
   below the board underside (7.0), so the open edges never weaken the board
   mounting, and nothing anywhere needs support: the skirt's top face is a
   bridgeable 2 mm-wall span.
4. **GPIO access is a notch down from the +Y wall's top edge** (55 mm wide
   over the 2×20 header), not a window — no bridging, and the wall keeps its
   bottom half for stiffness.
5. **Fan bolts flush to the lid's outer face; the insert bosses are on the
   inner face.** Aperture = the fan's own Ø37 bore (from `fan_bore(fan_type)`).
   Fan screws (M3 dome ×20, washer under each head) pass through the fan frame
   and the plate into the inner bosses — 11 + 2.5 + 5.8 = 19.3 mm of stack, so
   ×20. The bosses hang 7 mm into the cavity at the fan's corner pitch
   (±16 about (−10, 0)), clear of the board's connector envelope (the `fit-lid`
   fitcheck proves it against every solid in the base). The brief's "intake"
   duty: airflow blows into the case.
6. **Lid-screw posts at (±40, ±32.75), merged into the side walls.** The
   constraint set: posts must clear the board's mounting-hole band
   (y ±24.5 + standoff radius → |y| ≥ 28), must not block the ±X or −Y cable
   entry bands, and must be reachable by a screwdriver through the lid. Posts
   at the ±X ends collide with the USB/Ethernet cable bodies; wall pilasters
   on ±X can't clear the board footprint in a snug cavity. Widening the cavity
   in Y by one post diameter puts the posts in the walls' corners at
   (±40, ±32.75) — clear of everything, 0.25 mm fused into the wall.
   Their insert holes are **through-bored** so an M3×10's tip bottoms out in
   free space below the post, not in plastic.
7. **Lid prints outer-face-down; the register lip is notched around the four
   lid-screw posts.** The first draft printed lip-face-down and the gate
   rejected it for the reason worth logging: the lip is a *ring*, so the plate
   would bridge the ring's whole ~86 × 68 mm interior 2.5 mm above the bed —
   4716 mm² of unbridgeable overhang, printcheck 75/100, and the same pose put
   the lip 2.5 mm *below* z=0 in the export (the coupon's "empty layer" slice
   warning). With the bosses inside (decision 5) the flip is free: the bed face
   is the flat outer plate, the lip ring and the four boss cylinders print as
   standing features, insert holes opening up, nothing bridging anywhere. The
   posts rise to the lid's underside, so the lip is notched around them
   (Ø7.7 vs the Ø7.2 posts) — post + notch is what locates the lid in x/y,
   proven by the `fit-lid` fitcheck (empty at +0.05 seated) and its `fit-lid-crush`
   negative control (1 mm low still interferes on the wall tops).
8. **Coupon = two crops of the same corner that nest.** The base's −X,+Y
   corner in place (real wall the lid lip registers against, skirt profile,
   through-insert post, one generated board standoff — the RPI4 hole pattern
   centres at x = −10, so the −X corner is the one that carries a standoff)
   and the lid's −X,+Y corner at print pose, which the flip lands on the far
   side of the plate. Flip the lid crop over and drop it on the base crop:
   the lip notch engages the post, the lip face meets the wall — feel the
   register before committing to the full lid. (Measured on the export: the
   lid crop's cube must reach `lid_top_z`, not `base_top_z` — the plate sits
   *above* `base_top_z`, and a base-height crop left the lip ring standing on
   a 0.5 mm plate sliver, which the pre-ship audit caught as coupon 84/100
   with slicer stability warnings; fixed, the coupon measures 100/100.)
9. **GPL-3.0 combined work, by design.** The entry `.scad` includes
   NopSCADlib for the vitamins and the assembly manifest declares them, which
   is exactly the design-layer opt-in `docs/licensing.md` describes: disclosed
   on the product page (readme-gate requirement 11), isolated to this design,
   shared core untouched (`license-boundary-check.sh` enforces that part).
10. **Vents: four 12 × 4.5 stadium slots** in the +Y wall at z = 12, on a 15 mm
    pitch (3 mm webs) — each slot top is a real 12 mm bridge inside the
    bridgeable band; they sit opposite the fan's exhaust path across the board.
    (First draft was five slots at 11.5 mm pitch — corrected, decision 13.)
11. **`rounded_box` is corner-anchored — the shell needed a translate.** The
    first base render passed every presence-only gate with the shell
    displaced (+47.25, +38.10) from the origin-centred frame every other
    feature speaks: `rounded_box` spans `[0, size]` like `cube`, so an
    un-translated call put the walls around (+X, +Y) while the posts,
    standoffs, skirt cuts and lid stayed centred. Measured on the export
    (STL body decomposition): **7 disjoint bodies** — the shifted shell
    absorbing one post and one standoff, 3 posts and 3 standoffs floating
    free — yet printcheck scored 92/100 ("multiple bodies … fine if
    intentional"), the test-slice passed, and both fitchecks rendered
    empty because the interference regions landed outside the crops. The
    frozen previews *showed* it and the iteration-2 vision checks
    mis-read them. What caught it was the pre-ship "measure the export"
    audit — the same class as issue #69: presence-only gates cannot see a
    frame defect. Fix: `translate([-outer_l/2, -outer_w/2, 0])` around the
    `rounded_box` call (the house idiom — snap-clamshell-box does the
    same). After: **1 connected body**, bounds x[−47.25, 47.25]
    y[−38.10, 38.10] z[0, 26], printcheck 100/100 with no issues. The
    coupon moved 92 → 84 for an honest reason: the 92 was measuring two
    floating cylinders; the 84 was a real corner crop whose lid half was a
    lip ring standing on a 0.5 mm plate sliver (decision 8's measured fix) —
    with the crop corrected the coupon is 100/100.
12. **assembly.conf names wrapper modules, not raw vitamin constants.**
    `scripts/assembly.sh`'s generated preview `use`s the design file and
    includes only `NopSCADlib/core.scad`; `use` re-exports this file's
    *modules* (the whole include chain's, so `pcb` itself resolves) but **not
    its top-level variables** — a manifest line like `pcb(RPI4)` reaches
    `pcb()` with `RPI4` undefined and aborts inside the vitamin (measured:
    `rounded_rectangle.scad` line 25 assert; a constants probe confirmed
    `RPI4`/`F1BM3`/`fan40x11` undefined through core alone while
    `M3_cap_screw`/`M3_washer` resolve). The seven `vitamin_*()` origin-only
    wrappers close over this file's scope, where every catalog constant
    resolves, and the manifest names those. Screw lengths in the wrappers and
    the BOM descriptions in assembly.conf state the same hardware — keep them
    in sync. Generator-side fix (emit `include` of the design file, or document
    the wrapper requirement) is a follow-up issue, not this design's diff.
13. **Vent re-web (review round 2).** The five-slot layout (decision 10, first
    draft) put 12 mm slots on an 11.5 mm pitch — a 0.5 mm overlap that fused
    them into a single ~58 mm opening whose top bridged as one 58 mm curtain.
    It passed printcheck 100/100 (watertight, sliceable), but a 58 mm bridge
    sags in PETG — the README's first-listed material — exactly the bench
    judgment no geometry gate produces (Jane, PR #371 review). Fix: four slots
    on a 15 mm pitch, so 3 mm webs separate them and each top is a real 12 mm
    bridge, at nearly the same ~57 mm overall span. "Supports: none" is now
    honest in PETG too. Re-gated: base/lid/coupon 100/100, all four fitchecks
    unchanged.
14. **Round-2 product-page pass (PR #371 triage, Vera).** Merged v1 shipped
    with the reviewers' act-now list open; this round lands it. Geometry: only
    the vent re-web (decision 13). Everything else is manifests and page copy:
    a `base-board` render pose (base + Pi on the standoffs, no lid) drives a
    `product-populated` still that actually shows the board on the generated
    standoffs — the empty `product-base` tray undersold the promise; a `notch`
    preview camera (on the `base-board` pose, so the 2×20 header reaches through
    the notch and the GPIO-access feature reads); the print-settings lines the
    page lacked (seam, PETG textured plate, ASA enclosure, lid elephant-foot);
    and the serviceability / care lines (lid-on SD swap, serviceable inserts,
    adhesive feet, dust maintenance) plus the "shown for fit, purchased
    separately" hero caption. The insert-seating fix is the assembly.conf
    "flush with the post top" step; the stepped bore that would enforce it in
    geometry is backlogged (PM.md B4). New shots/cameras are regen-owned — the
    manifests and embeds are ours, CI renders the pixels.
15. **Round 2b (PR #397 review round).** Jane and Drik passed again; Vera's
    pm-triage act-now'd four copy/framing touches, no geometry: the `notch`
    camera widened `dist` 170→230 while its freeze window was still open (this
    was the first round to see it; at 170 it cropped the notch and 3 of 4
    slots — verified the wider frame shows all four slots, both notch ends, the
    wall top and the header); a vents "supports off / PETG slot droop is normal"
    settings line; an ASA fits clause (ASA prints the register tighter than a
    PETG coupon suggests, eating the 0.25 mm `fit_clearance` budget); and
    softening the fan-life claim to "typically". SD-swap ergonomics parked as
    B10 (a field-test on the first real print).
16. **B0 — the floating skirt (round 2c, PR #397).** The three open-edge cuts
    (+X / −X / −Y) carried `center = true` under a `translate(..., skirt_top)`,
    so each cut was centred ON z = skirt_top (6.5), spanning z[−3.75, 16.75].
    That deleted the 6.5 mm skirt and left the wall as a 9.25 mm band floating
    16.75 mm over the bed on those three sides — anchored only at the corner
    posts: unprintable, yet watertight, sliceable and 100/100 (angle-only
    overhang logic can't see a vertical curtain over air, and the posts keep it
    one connected body). It is the **second #69-class escape** on this design
    (the 7-body `rounded_box` frame miss, decision 11, was the first) and it was
    **inherited from merged #371** — `main` carried it until this PR repaired
    it. Caught by Drik's round-2b "finger run up the wall from the bed," missed
    by every gate; Jane passed the same head. Fix: **keep `center = true`** —
    the translate points are the wall *centrelines*, so the cut must straddle
    the wall in X/Y; deleting center (as both Drik and Vera proposed) shifts the
    cut onto the centreline, leaving an inner sliver and missing the −Y wall —
    and **lift the Z centre by half the cut height** so the cube *floor* rests
    on skirt_top (z[6.5, 27]). Re-verified: skirt restored on all three edges
    (ortho profile), base re-gated 100/100. The micro-SD-clearance consequence
    of the restored −X rim is B10, measured on the first real print.
17. **Round 3 — page currency & honesty (PR #397).** With B0 landed, both
    reviewers passed at head `3984950` (Drik's block cleared; Jane re-signed,
    making a wall-to-bed check on `part="base"` permanent in her routine).
    Vera's triage ruled an act-now list that is **all page-side —
    `sbc-case.scad` stays frozen**: (a) `previews/contact-sheet.png` was
    byte-identical to the PR base `978c9ba` and `cameras.conf` carried no
    `contact-sheet` row, so `render.sh --previews`/regen had **no path to
    refresh it** — the page's only as-printed exhibit still showed the pre-B0
    floating-skirt base. That is the **third #69-class escape** here (7-body
    frame → decision 11; floating skirt → decision 16; ownerless exhibit →
    this). Fix: add the bare `contact-sheet` row so regen re-renders it from the
    fixed base every run and it tracks the source forever. (b) The README droop
    clause "hidden once the lid is on" was false — the vents are in the
    *external* +Y wall (z 9.75–14.25), not under the lid (z ≥ 26); rewritten to
    the honest mechanism (droop faces down into the tunnel, seen only from vent
    height). (c) The SD-swap promise was flatter than B10's own measurement,
    softened to an interim "*should* come out — the first print verifies the
    rim." (d) `product-populated.png` reads as an empty tray in monochrome — a
    caption now points to the color `notch` view; the multi-color-render fix is
    a pipeline property and was declined. (e) The coupon size (~14 → ~33 mm in
    X, stale from 2c's own crop widen; measured 32.6 mm) and (f) the ASSEMBLY
    step-1 "see NOTES.md backlog" pointer (trimmed to "a planned refinement" in
    `assembly.conf`) were corrected in the same pass.
18. **Round 4 — the last page nits (PR #397).** Both reviewers passed again at
    `42b8bea`; act-now was two text lines and a free PR-body edit, no geometry —
    the `sbc-case.scad` freeze held through rounds 3 and 4 (both page-only), so
    the geometry verification stamped at 2c/3 is what ships. (a) The README
    short-version "melt the inserts in" gained the **flush with the post top**
    caveat — the one irreversible build step's warning had been one click deep
    in ASSEMBLY.md step 1. (b) "Print this first" step 4 synced its print times
    to the gate's (~5 h / ~2.5 h → ~2h45m / ~1h40m). (c) The PR description's
    stale "only geometry change is the vent re-web" line was corrected to name
    the B0 skirt repair. B10 widened to card + the four front-edge plugs (the
    RPI4 vitamin draws USB-C / micro-HDMI / jack top-side, so no render can
    witness overmold-vs-rim); Vera did not block a merge on the two passes at
    this head.
19. **Round 5 — BOM notation (PR #397).** Both reviewers passed again at
    `47bd7ce` (geometry frozen since 2c). Act-now was three `assembly.conf` BOM
    strings: the screw *lengths* `x6` / `x10` / `x20` read as *quantities* next
    to the Qty-4 column, so they became `×6 mm` / `×10 mm` / `×20 mm` (regen
    re-emits ASSEMBLY.md). The BOM is this design's N2 deliverable and the
    strings are ours (authored, not vendored), so the fix was in-scope. Backlog:
    **B7 above B4** (Drik's recoverability principle — a sunken insert walks back
    with a soldering iron; a scraped card / blocked ribbon socket don't); new
    **B11**, a fan-aperture finger guard (queued — N4 proof + airflow cost
    checked when built). The `sbc-case.scad` freeze held rounds 3–5 (all
    page-only), so the 2c/3 geometry verification is what ships.
20. **Round 6 — hardware-honesty strings + the dome note (PR #397).** Both
    reviewers' substance passed; Drik re-signed at `21325fc` (Jane's round here
    failed to complete during a total LLM-provider outage, her `47bd7ce` pass one
    text-only commit behind). Act-now was two N2-surface strings: the README
    hardware line now tells the **three-cart** truth — the 8 heat-set inserts are
    a separate purchase no screw assortment carries, so "one assortment plus a
    fan, not five orders" had undercounted the shopping list by a cart — and the
    `assembly.conf` insert BOM reads "4 **base** lid-screw posts, 4 **lid** fan
    bosses" (it had read "4 lid posts, 4 fan bosses", backwards for two seconds).
    Recorded, not changed: the **dome-screw choice** — M3×20 *dome* heads sit on
    the lid's visible exterior under a washer, which is why the BOM specifies them
    over caps (Drik's "dome or cap" is a future considered choice, not a
    hunch-driven BOM edit). Two keep-guards for future page passes: the SD-swap
    *should* asterisk stays until B10's first field test logs, and ASSEMBLY steps
    1–6 stay verbatim (the fan bolts on **last** from outside the closed lid, so
    the fan wire is never trapped — a pinch the step order avoids for free). The
    `sbc-case.scad` freeze held rounds 3–6, all page-only since 2c.

## Print settings

- **Material:** PETG or ASA (ASA if the case lives near a heat source —
  electronics enclosures are its use case)
- **Layer height:** 0.2 mm
- **Perimeters:** 3 (walls are 2.0 mm ≈ 5 perimeters; the value just ensures
  the pilots and insert holes keep their walls solid)
- **Infill:** 15 %, gyroid
- **Supports:** none — both parts are oriented support-free by design
  (`base` floor-down as modeled; `lid` outer-face-down, which is the rendered
  `part="lid"` orientation)
- **Orientation:** as rendered per part; no rotation needed in the slicer
- **Coupon:** print with a **brim** — it is cropped corners of a 26 mm-tall
  wall, so the bed patch is small relative to the height

## Print this first

Print `sbc-case-coupon.scad` (the `coupon` part) before the full case — it is
two cropped corners of the real parts, ~40 min. Since PR #397 the base crop
also carries the restored skirt rim and the leftmost vent slot, so it rehearses
the **PETG bridge the full base stands on** — the coupon is now the fit *and*
structure proof:

1. **Insert fit:** an F1BM3 should press into the post's Ø4.0 hole and grab.
   Loose → drop `post_d` shell or check hole size first; the hole diameter is
   `2 * insert_hole_radius(F1BM3)` from the vitamin, so tune by printer, not
   by editing the vitamin value.
2. **Register fit:** flip the lid corner over and drop it onto the base
   corner — the lip notch should pass the post and the lip face seat against
   the wall with light friction, no force. Tight → `fit_clearance` +0.05
   steps; sloppy → −0.05. **Do not go below 0.15** on a typical FDM printer.
3. **Board pilot fit:** an M2.5 cap screw should self-tap the Ø2.05 pilot in
   the standoff sample and hold firm.
4. Only then print `base` (~2h45m) and `lid` (~1h40m) — the head-stamped gate
   times; your slicer and material may differ.

## Derivations worth keeping

- `cavity_x_half = 45.25`: board half 42.5 + usb_A/rj45 overhang 2.0 + 0.75
  clearance — the connectors physically pass the board edge, so the cavity
  must clear *their* extent, not the board's.
- `cavity_y_half = 36.1`: board half 28 + clearance 0.75 + post diameter 7.2 +
  0.15 — widened by exactly one post so the lid-screw posts live in the walls
  (decision 6). The −Y usb_C overhang (1.6) is inside this by a wide margin;
  the −Y wall is open above the skirt anyway.
- `skirt_top = 6.5` = floor 2 + standoff 5 − 0.5 margin: the highest open edge
  that still leaves full wall below the board plane.
- `interior_h = 24` ≥ 5 + 1.4 + 15.6 + 2 = 24.0 measured against usb_Ax2, the
  tallest RPI4 connector in the vendored layout.
- Fan screw length M3 × 20 = fan frame 11 + plate 2.5 + insert 5.8: the screw
  passes through the fan and the plate into the inner-face bosses (×10, the
  first draft's length, bottomed out in the plate before reaching the insert).
