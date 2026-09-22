# pip-cable-chain — engineering log

A print-in-place energy chain (drag chain): `links` identical links printed
captured inside their neighbors, flexed free on the bed, routing a moving
cable loom with ±45° of articulation per joint and hard printed stops.
Brief: issue #705. Style: ribbed-industrial.

## Goal

One flat print produces an articulated chain — no assembly, no hardware in
the joints, no supports. Each link's pin stubs are printed inside the next
link's blind bores; the run flexes to break the sacrificial fusion and is a
working drag chain.

## Brief measurements → parameters

| Brief row | Given/assumed | Parameter | Built value |
|---|---|---|---|
| Cable passage | assumed 12×12 mm | `passage_w`/`passage_h` | 12 tall × 18.8 wide inside (ears at \|y\|=9.4), vaulted to 20.98 headroom over the center |
| Link pitch | assumed 16 mm | `pitch` | 16 (axis to axis) |
| Articulation ±45° with printed stops | assumed | `stop_angle` | 45, enforced by plate placement + pose checks |
| Pin-to-bore XY clearance | **given** 0.15–0.25 | `clear_xy` | 0.25 (the brief's top of band = pip_hinge's weld floor) |
| Pin-to-bore Z clearance | **given** 0.20–0.40, whole layers | `clear_z` | derived 0.4 = 2×0.2 layers |
| Run length | assumed 20 links ≈ 300 mm | `links` | **11** ≈ 189 mm — see D5 |
| Mounting | assumed M4 tabs, ends only | `end_tabs`, `screw_hole("M4")` | tabs on link 1 and link N |

## Key decisions

- **D1 — round pin, teardrop bore** (inherited from pip-piano-hinge's
  articulation finding). The teardrop lives on the bore only (its roof must
  bridge supportless); the pin stubs are plain cylinders, rotationally
  symmetric, so the joint clears at every angle through ±45°. A teardrop pin
  jams on the bore flanks within a few degrees.
- **D2 — xy≠z bore** (the doc's clearance theory, no scaling anywhere): bore
  = `offset(r=clear_xy)` of `_pip_teardrop2d(pin_d)` UNION two copies
  shifted ±(clear_z−clear_xy) in Z. Sides stay spread-limited at clear_xy;
  the roof over the pin AND the floor gap under it (the two horizontal gaps
  a sagging layer must cross) open to clear_z. CC4 intact: nothing scaled.
- **D3 — captivity by blind bore.** Each ear's bore is cut from the ear's
  inner face to one `cap_t` short of the outer face; the stub ends
  `axial_gap` (0.6 ≥ one extrusion width) short of the cup floor. A through
  bore lets the chain slide apart along its own pin axes; the cap makes each
  joint captive with no added parts.
- **D4 — the end stops ARE the pocket plates.** The ±45° limit is contact
  geometry, derived, not a rib or boss (those choke the passage). The
  mechanism had to be found twice — iteration 1 failed BOTH stop checks and
  the measurement (bodies.py clustering of the rendered intersections)
  falsified the first theory:
  - **What cannot work (measured).** A corner-on-REAR-EDGE landing. In the
    rotating plate's frame the fixed lug-tip corner travels on
    `x''(t) = lug_tip·cos t − lug_hz·sin t` (decreasing) and
    `z''(t) = −(lug_tip·sin t + lug_hz·cos t)` (decreasing) — so it can
    only transit the plate and EXIT through the rear face; a "landing"
    placed on that face is a graze whose interference window CLOSES at the
    stop angle. With plate_x0 = 1.225 the up-corner's window closed at
    46.6° and the ±47° check rendered empty (the down side only passed by
    the accident of a 0.06 mm radius mismatch digging a 0.07 sliver).
  - **What works: the corner rides ONTO the plate's INNER face** (tunnel
    floor / ceiling). Penetration
    `lug_tip·sin t + lug_hz·cos t − passage_h/2` is monotone in t, so
    contact at exactly θ=45° and deepening past it:
    `lug_tip = (passage_h/2 − lug_hz·cos θ)/sin θ` (5.29 mm).
  - `plate_x0 = 1.0` is then a WINDOW constraint, not a landing point: the
    corner must still be on the plate at θ=45°+2 (the check pose) — it
    exits the rear face at `lug_tip·cos 47° − lug_hz·sin 47°` ≈ 1.26, so
    1.0 leaves 0.26 mm of window margin, and the θ=45° contact sits
    `lug_tip·cos45° − lug_hz·sin45° − plate_x0` ≈ 0.47 mm in from the rear
    edge, on material. Asserted in the file.
  - The plates' front edge must clear the PREVIOUS link's plate corner
    sweeping back through the same range: `plate_back =
    (passage_h/2 + wall)·sin θ − plate_x0·cos θ + plate_gap` (6.36 mm
    behind the next axis — the outer corner at ±(passage_h/2+wall) is the
    binding one, not the inner one D4.v1 solved for), giving
    `plate_x1 = pitch − plate_back`. Gap kept: `plate_gap` 0.7.
  - Both plate INNER faces stay flat (the roof chamfers its outer face
    only; the floor plate is a plain slab): they are the stop surfaces, and
    a chamfer on the floor plate's top would slope the landing zone (the
    chamfer band reaches 1 mm in from the rear edge; the contact sits
    0.47 mm in). Lug tip corners stay SHARP for the same reason.
  - Verified by the pose checks, not the algebra: ±44° renders EMPTY
    (0.027 mm clearance), ±47° interferes (0.048 mm deep) — both sweep
    directions, symmetric 16 facets each.
- **D5 — bed layout: straight, 11 links default.** The brief's 20-link
  ≈300 mm run exceeds the 200 mm test-slice ceiling, and a serpentine
  (folded) bed layout is **geometrically impossible** for this joint: the
  pin axes are all Y, so every joint is a single-DOF hinge bending only in
  the XZ plane — a chain of them cannot turn in XY to snake across the bed.
  Default is therefore 11 links ≈ 189 mm (fits a 200 mm bed with margin,
  rear tab to front lug tip); `-D links=20` for a longer bed is a supported
  parameter, not a different design.
- **D6 — open joint mouths (measured on the mesh).** Each joint mouth
  (~7 mm, the span between one link's plate front edge and the next link's
  plate rear edge) is open **top and bottom** over |y| < 6: no ceiling (the
  previous roof plate ends `plate_back` behind the axis, the next starts
  1 mm ahead of it) and no floor over ~6.9 mm — the floor's rear extension
  can only reach `floor_ext_x0` before its bed-level corner sweeps into the
  previous plate (D9). The previous link's bar crosses the mouth at
  |y| ∈ [6, 9] (z 5.8–12.2); the ear-band sides are walled by the ear noses
  except a 2.85 mm slot between one nose's front face and the next ear's
  rear face. Between joints the cable is fully enclosed (floor, ear side
  walls at |y| = 9.4, ceiling). A snap-lid over the mouths is the named
  follow-up (README "what is not in v1").
- **D7 — ear rear: stepped, and its rear-top corner is CHAMFERED.** The ear's
  y-band (9.4→15.1) is `side_gap` clear of the previous link's LUG band
  (6→9) for all rotations (both rotate about the same axis) and the
  previous PLATES live in the plate bands — but v3's ear NOSE broke the
  old "cannot collide at any angle" claim: the previous link's own EAR
  shares this band, and the nose presents its front face at radius
  √((pitch−ear_nose)² + (ear_main_z0−z_pin)²) = 8.03 from the joint axis.
  The ear's sharp rear-top corner sat at 8.13 and rode 0.4 mm into that
  face at 44° up (measured, 0.92 mm³ per ear). The corner now carries a
  1 mm 45° chamfer (worst radius 7.59, assert in the file); the chamfer
  is `style_edge_chamfer`, so the style's edge break and the sweep
  clearance are the same cut. The stepped rear (`ear_main_z0 =
  bore_z_floor + 0.3 = 6.4`, below it the low web at `ear_low_x0 = −1.0`)
  is structural: material around the bore floor, tying the ear down into
  the floor plate with volumetric overlaps (0.6 into the plate, 0.3 into
  the main box). The low web's rear corner sits at radius √(1² + 6.4²)
  = 6.48 — inside everything the previous link sweeps.
- **D8 — v2 y-stack topology (the shell-separation redesign).** v1 put the
  lug INSIDE the passage side walls and the ears as narrow strips beside
  them: the lug band (y 0–5.6) touched nothing — it floated as a separate
  shell — and it blocked the cable passage through the joint besides. v2
  moves the whole capture stack outside the passage: |y| ≤ 6 is passage the
  whole length; the LUG is the tunnel-wall band (6→9) continued forward at
  reduced height; the EAR (9.4→15.1) hangs from the FULL-WIDTH roof/floor
  plates (plate_w = 2·ear_y_out = 30.2), not from side walls — a tall side
  wall would sweep-collide with the previous link's lug, which shares the
  lug band. The only side wall left is the short arm post (x 8.4→plate_x1),
  forward of everything the previous link sweeps. Every intra-link joint
  overlaps volumetrically ≥ 0.3 mm (face-only contacts export as
  coincident-facet non-manifold shells — found the hard way, iter 0).
  Consequence: between joints the passage's sides are the EAR NOSES (grown
  forward, D9); the openness that remains is the joint mouths themselves
  — D6.
- **D9 — the vault, and the three sweep constraints it cost (v3).** v2
  failed style-check twice: support-free 0.1215 (a flat 12 mm tunnel
  ceiling is a downward face shallower than 45°, and stylelift's metric
  gives no bridge credit) and chunky-sections p05 1.24 (ear walls under
  2 mm). v3 fixed both by geometry — and every addition was then bounded
  by the joint sweep:
  - **The vault.** The ceiling over |y| < 6 is two exact-45° planes
    meeting at a 2 mm flat crest (z = 23): headroom rises 15 → 20.98 at
    center, and every downward roof face is at or steeper than 45° —
    support-free by geometry, not by bridging. printcheck's unsupported-
    overhang warning vanished with it (92 → 100). Cost: the ridge stands
    above the plate, and a rear face at plate_x0 landed the CREST 0.65 mm
    behind the previous plate's front edge at 44° up (measured 13.2 mm³).
    `ridge_x0` (5.10) is derived from exactly that landing inequality at
    stop_angle−1; behind it the ceiling stays flat over x ∈ [plate_x0,
    ridge_x0] — the honest 0.0888 support-free share that remains.
  - **The ear nose.** The ears grow forward to arm_x0, closing the
    passage's sides between joints. Cost: the nose's front face is a new
    sweep obstacle for the previous EAR's rear-top corner — D7's chamfer.
  - **The floor extension.** The floor plate grows rearward to
    floor_ext_x0 (0.6): the joint mouth keeps ~0.4 mm of cable floor and
    the ear low webs print on material instead of a 1.6 mm bridge. Cost:
    at bed level the corner sits z_pin from the axis — outside the
    previous plate's front-TOP-corner radius — and a rear edge at −1.0
    rode onto that plate at 44° down (measured 4.0 mm³, full width).
    floor_ext_x0 is derived so the corner lands ahead of plate_x1 at
    stop_angle.
  - **Thickening.** ear_t 5.7 / cap_t 2.0 lift every ear wall to ≥ 2 mm
    (p05 = 2.0 exactly, the style floor); plate_w grows to 30.2, overall
    height to 23.0.
  After: style 6/6, printcheck 100/100 both parts, all six fitchecks
  behave (±44 empty, ±47 fire 24/16 facets), coupon 3 clean bodies.

## Print orientation

Exactly as rendered: flat and straight on the bed, pin axes horizontal (Y),
teardrop roofs up (+Z). Orientation IS the clearance decision — rotating a
joint 90° puts the whole-layer clearances on the spread-limited plane and
the chain welds. No supports anywhere: the bore roofs bridge at 45°, the
tunnel ceiling is VAULTED at exactly 45° over the passage center — every
downward roof face is at or steeper than 45°, support-free by geometry
(style-measured, printcheck 100/100) — and the tab undersides are on the
bed.

## Iteration log

- **v0 → v1** — first full geometry rendered non-manifold with 8 shells
  (expected 3). Bisected with a single-link render + per-body bbox
  clustering (`build/bodies.py`): three causes — face-only contacts
  (plates/lug/stubs touching without overlap), the roof rib extruded
  vertically as a tower, and one stub extruded away from its lug. v1 fixed
  the unions and the rib, still 4 shells.
- **v1 → v2 (D8)** — the remaining shells were topological, not tolerance:
  the lug band floated (touched nothing) and blocked the passage. Full
  redesign per D8; coupon then rendered 3 clean bodies/link-identical.
- **v2 bore mirror fix** — coupon rendered as ONE welded body; the
  `fitcheck` part's overlap bbox named it: exactly the −Y stub volume. The
  bore cutter extrudes −Y (so the teardrop roof stays up on both sides),
  so its origin must sit at the +Y bore floor but 0.01 outside the inner
  face on −Y. After: 3 identical clean bodies.
- **bed-face fix** — middle links floated 0.01 mm (floor plate's bottom
  chamfer). All links span z 0.00→18.70.
- **stop-mechanism fix (gate iter 1 → 2)** — iter 1 failed `pose_dn44`
  (8-facet sliver: the moving floor plate's rear corner sweeping into the
  fixed plate's front edge) and `stop_up47` (empty). bodies.py clustering
  of the ±47° intersections falsified the corner-on-rear-edge theory and
  forced the D4 rewrite: the stop is the lug-tip corner riding ONTO the
  plate's inner face (monotone), `plate_x0` shrunk 1.225 → 1.0 to keep the
  corner on the plate through the +2° check pose, `plate_back` re-solved
  for the OUTER plate corner (5.26 → 6.36, fixing the 44° sliver),
  `arm_x0` 9.5 → 8.4, floor plate made a plain slab (flat stop surface +
  flat bed face). After: all six fit parts behave as labeled, ±47°
  symmetric at 16 facets each direction.
- **v2 → v3 (the style-driven shell redesign, D9)** — style-check failed
  v2 on support-free (0.1215 — the flat 12 mm ceiling) and
  chunky-sections (p05 1.24). Redesigned per D9: 45° vault + ridge, ear
  noses to arm_x0, floor extension, ear/cap thickening. Two render bugs
  caught by body clustering: a bad rotate on the YZ prisms (profile landed
  along Y instead of Z — strays below the bed), then 0.4 mm³ slivers per
  link where the ridge polygon's feet hung below the vault void's base —
  material neither the void nor the plate covered, surviving detached.
  Feet raised onto the ceiling plane: 3 clean bodies.
- **gate iter 3 → 4 (the sweep pays for the vault)** — v3.0 passed style
  (6/6, support-free 0.0658) but failed pose_up44 (36 facets) and
  pose_dn44 (40 facets). Clustering the interference bodies named three
  causes, each then closed by a DERIVED constant with its own assert so
  it cannot silently regress: the ridge's rear face (13.2 mm³ at 44° up)
  → `ridge_x0` = 5.10 from the crest-landing inequality; the floor
  extension's bed-level rear corner (4.0 mm³ at 44° down, full width) →
  `floor_ext_x0` = 0.6; the ear's rear-top corner vs the new ear nose
  (0.92 mm³ per ear at 44° up) → 1 mm chamfer, worst radius 7.59 vs the
  nose face's 8.03. After (iter 4, green): ±44 empty, ±47 fire (24/16
  facets), style 6/6 at support-free 0.0888 (the flat ceiling band
  x ∈ [1, 5.1] is the honest cost), printcheck 100/100 on both parts,
  fusecheck 11/1. Telemetry: scores 92→92→100→100, fail lines 2→0→2→0.

## Print this first

Print `pip-cable-chain-coupon.scad` (3 links, no tabs, 58 × 30.2 × 23 mm,
~1 h 55 m) before the full run. It carries two full joints in exactly the
production cross-section.

1. Print it flat as laid out, in the same material/layer height you'll use
   for the chain.
2. Flex each joint once to shear the break-in fusion. Both joints should
   swing to both stops and back freely, with a click at each end.
3. If a joint binds (most likely: welds in the bore): raise `clear_xy` by
   0.05 (clear_z re-derives to the next whole layer automatically) and
   reprint. Do not go below 0.25 — that is pip_hinge's measured weld floor.
4. If a stub snaps out of its bore on flexing (too loose, or layer adhesion
   poor): lower clear_xy by 0.05 rather than raising print temperature.

Tune `clear_xy` in one place — the coupon and the chain share every
parameter through the include.

## Field test log
