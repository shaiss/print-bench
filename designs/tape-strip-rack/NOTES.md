# tape-strip-rack — engineering notes

## Goal

A blade-free multi-strip tape rack for gift wrapping: two rolls on a drop-in spindle, a row of thin fins, and eighteen 40 mm strips per pull — snipped mid-gap with scissors and left hanging by their middles, ready to grab one-handed.

Brief: issue #1062, filed from a product photo the owner supplied. Built in the same session at the owner's instruction, with no interview round: every number in the brief is a stated default. The owner then asked for the design to be refined; the palm pad, the rounded free ends and the nesting check come from that request.

## Given / assumed measurements

| Measurement | Value | Status | Where it lives |
|---|---|---|---|
| Lanes (rolls side by side) | 2 | **given** (photo) | `lanes` |
| Fins in the default assembly | 10 | assumed (counted from the photo) | `fins_per_rack` × `racks` |
| Tape core inner Ø | 25.4 mm | assumed (1 in core) | `core_id` |
| Tape width | 19 mm | assumed (3/4 in) | `tape_w` |
| Roll outer Ø, maximum | 62 mm | assumed | `roll_od_max` |
| Strip length = fin pitch | 40 mm | assumed (estimated from photo) | `strip_len` |
| Tape plane above the base | 26 mm (brief: ≥ 25) | assumed | `fin_h` |
| Clear gap between fins at the top | 35.4 mm (brief: ≥ 28) | derived | `strip_len` − post length |
| Largest printed part | 207.8 × 57.2 × 42 mm (brief: ≤ 210 long) | derived | `rack` |
| Tallest printed part | 58 mm (brief: ≤ 200) | derived | `cradle` |
| Assembled length | 561 mm (brief: about 500) | derived | palm pad + cradle + 2 racks + end cap |

None of these was measured from a real roll or a real print. `core_id`, `tape_w` and `roll_od_max` are the three to caliper before printing. The assembly is 61 mm longer than the brief's estimate: 30 mm is the palm pad (the owner's refinement request), 12 mm is threading room at the gate (added after review), and the other 19 mm is the brief's round "about 500" against a build that was already 519.

The brief gave the strip length as a parameter from 30 to 60 mm. As built it is 40 to 60 (36 with `ledge_l = 8`): under 35.2 mm the gap between fins drops below the brief's own 28 mm, and under 39.5 mm the socket would run under the end cap's ledge. Both stop the render with a message.

## Multi-part layout

One entry file, `tape-strip-rack.scad`, with a `part` selector. The default, `assembly`, is the preview and is never a deliverable.

- Printable: `cradle`, `spindle`, `rack`, `end-cap` (`ci.parts`).
- Deliverable: the four of them as one multi-object plate, `build/tape-strip-rack-plate.3mf` (`ci.plate`). One of each is already a working five-fin rack; print `rack` twice for the ten fins the preview shows.
- Coupon: `tape-strip-rack-coupon.scad` sets `part = "joint-coupon"`.
- Fit proofs, never printed (`ci.fitchecks`): `joint-fit`, `joint-pull`, `joint-lift`, `joint-drop`, `spindle-fit`, `roll-fit`, `nest-fit`, and their `-ctrl` twins.
- `cutaway`, `nested` and the `explode` parameter exist only for the preview cameras.

## Key decisions

**D1 — Blade-free; the cut is scissors.** The brief's design review looked for how the reference cuts and found that it very likely does not: a product matching the photo is sold as having no blades, with the tape stuck to the bars and cut with scissors. That identification came from search-result text and was not confirmed. The same review estimated the alternative from first principles: an FDM tooth has a tip radius near 0.2 mm, and pressing 50 µm polypropylene tape onto such teeth takes roughly 0.5–3 N per tooth, on tips that hurt a fingertip at that load. Paper tape would cut, matte acetate would half-cut, glossy polypropylene would dimple. No printed cutter is in v1. A pull-over tear edge is on the backlog (`PM.md`).

**D2 — Every part prints upright, as it stands.** The first candidate printed the rack on its side so that printed teeth would come out sharp. With the teeth gone, that reason went too, and the on-side rack had costs: guide posts could only have a 45° ramp on one side of each lane, and the cradle, which cannot print on its side, would have needed a dovetail socket on a vertical face. That socket's upper lip starts as a line in mid-air. It scores 100/100 in printcheck, because printcheck reads face angles, not whether a feature has anything under it. Upright, the posts get steep lane faces on both sides and every joint feature is a plain vertical wall.

**D3 — A drafted drop-in dovetail, key on the downstream end.** The joint is a dovetail in plan, lofted with 8° of draft so the key is wider at the bed than at the top. A socket part can only be lowered onto a key, and lifting it straight up is how it comes apart. Key and socket print in the same orientation, so one clearance, `joint_clear`, covers every joint.

What the draft does and does not guarantee, as measured on the meshes by review:
- **Along the tape it is positive.** The key's tip overlaps the socket's mouth by 1.8 mm a side; the joint cannot pull apart (`joint-pull`).
- **A straight lift of a key part catches the socket part** after about 1.4 mm of travel (`joint-lift`).
- **A part hanging off a lifted key is held by friction only.** A rack cantilevered from a lifted cradle can pivot nose-down and walk its socket lips up the taper; a collision-free path exists at every tilt. Holding needs a friction coefficient above about tan 8° = 0.14, which printed PLA on PLA probably has and which nobody has tested. The draft was cut from 10° to 8° for that margin. So the page says: slide it, or carry it with a hand under the racks.
- **Lifting a socket part leaves everything upstream on the table.** That includes the end cap, the lightest part.

Details that exist for a reason:
- the key is drawn in by `joint_ef` (0.4 mm) over its first 0.5 mm and the socket flared out by the same, so first-layer squish is not the tight spot;
- the socket's two lips are squared back 1.6 mm so they end in a flat, not a 60° knife edge;
- the key's tip corners are cut back 0.8 mm and the socket's are left sharp, so a seam blob in the corner has room;
- the socket rim has a 0.5 mm lead-in.

**D4 — A hold-down gate at the cradle nose.** Both tapes pass under a lintel between the rolls and the first fin. The tape then meets the rack at a fixed height whatever the roll diameter, and the pull on the spindle runs downhill to the gate, into the seat, so an open saddle is enough (an assert holds the tape at least 5° below the saddle's lean). The gate sits 3 mm *above* the tape plane (`gate_rise`), so a level pull clears every fin. The cost is that the tape does not lie on the fins by itself: lowered onto the end cap's ledge, a taut tape hovers 2.8 mm over the first fin and 0.3 mm over the last until a fingertip presses it down. A gate below the tape plane would lay the tape on every fin, but it would also drag the adhesive across the first fin during the pull. The lintel is a 2 mm flat flared at 50°, so it prints as two 22 mm bridges, one per lane, and then grows.

**D5 — Tapered fins with buttress posts.** A fin is loaded across its layer lines, the weak direction. It is 3.2 mm at the land and 5.2 mm at the root, and each guide post is a column 7.2 mm long at the root that runs past the land into an 8 mm horn. Each post is one lofted solid.

**D6 — Ribbed lands, on the fins and on the end cap's ledge.** Peeling a strip is resisted by the width of the bond, not its length, and a full-width bond on a 19 mm tape can take more force to break than the rack weighs. Each land is three 2.4 mm ribs per lane (`land_ribs`, `land_rib_w`), 38 % of the tape width. This is an estimate, not a measurement: `land_ribs = 0` gives a flat land if strips fall off, fewer or narrower ribs if they cling. The ledge was flat at first; review measured it at ten times a fin's contact area on an 18 g part that lifts straight off its key, so it is ribbed too.

**D7 — An end cap with a tail ledge, one pitch past the last fin.** The two tape tails need somewhere to be stuck down so both hands are free to press and cut. Putting the ledge a full pitch past the last fin means the last fin still yields a full-length strip.

**D8 — One spindle, blind saddle pockets.** A plain 24.6 mm hub for a 25.4 mm core, a 29 mm flange between the rolls with 40° shoulders, standing on end to print. The saddles are 2.8 mm pockets in 4.4 mm walls; the 1.6 mm skin stops the spindle walking out sideways. The slots lean back 25°. The spindle has 1.6 mm of end play in total, because it goes in blind with a roll on each side.

**D9 — 20 mm between the largest roll and the gate.** Review measured the first cut of this at 8.1 mm and pointed out that the side walls are solid, so that slot is the only way to the back of the gate with the rolls seated. It is now a finger's width for a full 62 mm roll.

**D10 — A palm pad behind the rolls, rounded at the back.** The rack with rolls weighs about 3.3 N and two tapes pull at 2–8 N, so it slides unless it is held, and a hand pressed on top of the cradle lands on the rolls. The floor runs on 30 mm behind the back wall with four grip ribs (`heel_l`; 0 removes it). The two free ends, the pad and the end cap, have 4 mm corners (`corner_r`): a rounded corner lifts off the bed less than a square one.

**D11 — Style `none`, as the brief decided; chamfers at 50°, not the brief's 45° habit.** Bed chamfers and the lintel flare are 50° from horizontal because printcheck treats exactly 45° as a float coin-flip.

**D12 — No feet modelled; the underside is flat.** A recess for a stick-on foot is a ceiling over the bed, which printcheck counts as overhang. A flat underside takes 2 mm bumper dots anywhere. Feet help; they do not replace the steadying hand.

**D13 — `lanes = 1` needs a narrower joint.** The default key is 24 mm at its tip and a one-lane base is 30.8 mm wide. The render stops with an assert that says so; `-D joint_neck=6 -D joint_tip=13` fits, with 1.4 mm of pull-apart hold a side against the default 1.8.

**D14 — Print cost is near its floor; the slicer is the lever.** Measured with the gate's test-slice on a rack segment (6 h 02 m, 75.5 g): slightly thinner fins save nothing (2.6 mm land, 4.0 mm root: 6 h 11 m, 75.3 g — the fins are almost all perimeter already), and only fins near the 1.6 mm floor save filament (about 12 %), at the cost of the stiffness D5 is for. A 6 mm base saves 9 % of the filament and 5 % of the time, and shortens the joint. Two perimeters and 15 % infill save 18 % of the filament and 13 % of the time on the ten-fin set (198 g, 17 h 10 m) with no geometry change.

## Print orientations

- `cradle` — on its floor. The saddle slots lean 25° and the lintel is two 22 mm bridges; nothing else overhangs.
- `spindle` — standing on end. The flange shoulders are 40° from vertical.
- `rack` — on its base, fins up. Nothing overhangs except the socket walls, which lean 8°.
- `end-cap` — on its base.
- `joint-coupon` — both stubs flat on the bed.

## Print settings

- **Material:** PLA.
- **Nozzle / layer:** 0.4 mm / 0.2 mm.
- **Perimeters:** 2 or 3.
- **Infill:** 15–20 %.
- **Supports:** none. The gate lintel is meant to be bridged, 22 mm per lane, strands running from post to post (bridging angle 90° with the cradle as exported, if the slicer does not choose it). A slight wave underneath is expected. Its underside is the surface the tape slides on, so trim any bridge whiskers before the first pull.
- **Seam:** rear. An aligned seam that lands on a dovetail flank leaves a ridge there, and the coupon then reads it as too little clearance. The same ridge on the spindle's hub takes up some of the 0.4 mm of air under a roll's core, so a tight roll means look at the seam before `hub_clear`. Printability review, not yet checked on a print.
- **Bed:** the rack is 207.8 mm long. On a 220 mm bed it leaves 6 mm at each end, so use a skirt distance of 2 mm, or no skirt, or turn the rack 45°.
- **Order:** the joint coupon first, then the plate.
- **Slicer estimate** (PrusaSlicer bare defaults, the gate's test-slice: 3 perimeters, 20 % infill): cradle 5 h 22 m / 60 g, spindle 47 m / 12 g, rack 6 h 02 m / 75 g each, end cap 1 h 24 m / 18 g, coupon 44 m / 10 g. Ten-fin set: about 242 g and 19 h 40 m at those settings.
- The end cap printed alone has only three post tips on its last layers; print it on the plate with the rack so the layers have time to cool.

## Print this first

`tape-strip-rack-coupon.scad` prints the production key and the production socket as two loose stubs (44 minutes, 10 g). The stubs are as wide as a rack, so the socket's arms are as stiff as the real ones. `gate.sh` renders and gates the coupon automatically.

Lower the socket stub onto the key stub. It should drop on under light finger pressure. Then, with both flat on the table, push and pull the socket stub along the joint: about 0.6 mm of play is right at the default.

- Will not go on, or needs force → raise `joint_clear` by 0.05 (0.20 → 0.25 → 0.30) and reprint the coupon.
- Clearly more than 1 mm of push-pull play → lower `joint_clear` by 0.05.
- Tight only for the last millimetre at the bed → that is first-layer squish; raise `joint_ef` rather than loosening the whole joint.
- A socket stub that tilts a few degrees on the key is normal for a drafted drop-in joint; it is not a reason to tighten.

`./scripts/render.sh tape-strip-rack --sweep joint_clear=0.10:0.30:0.05` prints the ladder in one go.

The coupon cannot show whether a hanging rack stays on a lifted cradle: its socket stub's mass centre is 2 mm past the key's tip, a rack's is 94 mm. That is a field test (below).

The spindle is a loose running fit, not a tuned one, but roll cores vary: measure yours and set `core_id` before printing it.

## Fit proofs (what CI renders, never prints)

- `joint-fit` — key in socket, posed as joined: empty. `joint-fit-ctrl` — socket cut at −0.15 mm: interferes.
- `joint-pull` — socket stub pulled 3 mm off along the tape: interferes. The joint holds.
- `joint-lift` — key stub lifted 3 mm, socket stub left behind: interferes. A straight lift catches.
- `joint-drop` — socket stub lifted 3 mm: empty. That is how it comes apart.
- `spindle-fit` — spindle in its pockets against the whole cradle: empty. `spindle-fit-ctrl` — hub grown 1.2 mm: interferes.
- `roll-fit` — two 62 × 19 mm rolls on a 25.4 mm core, on the spindle in the cradle: empty. `roll-fit-ctrl` — rolls 8 mm larger: interfere with the floor.
- `nest-fit` — two rack segments nested for storage, 0.2 mm of air between them: empty. `nest-fit-ctrl` — the same without the half-pitch shift: interferes.

## Gate evidence

Two backends gate this design, and they do not always agree. The local gate runs OpenSCAD 2021.01. CI's render gate runs openscad-nightly with the Manifold backend, and is the one a merge depends on.

| Part | Local, OpenSCAD 2021.01 | CI, nightly + Manifold, commit 2b96a24 | Test-slice (CI) |
|---|---|---|---|
| `cradle` | 100/100 | 100/100 | 5 h 22 m, 60.3 g |
| `spindle` | 100/100 | 100/100 | 47 m, 12.2 g |
| `rack` | 100/100 | 100/100 | 6 h 02 m, 75.5 g |
| `end-cap` | 100/100 | 100/100 | 1 h 24 m, 18.1 g |
| `tape-strip-rack-coupon` | 100/100 (2 bodies, intended) | 100/100 | 44 m, 9.9 g |

CI's first run, on commit e3eb9f4, scored the cradle 67/100 and the spindle 59/100 while the local gate had both at 100/100: see Bugs caught. CI gates every later push again; the printcheck report on the pull request is the current record.

Locally, `./scripts/gate.sh --slice tape-strip-rack` exits 0 in about 20 s (PrusaSlicer 2.7; its slice estimates are within a minute of CI's).

Eleven fit proofs pass: five `empty`, six `interferes`. Plate: `build/tape-strip-rack-plate.3mf`, 4 separate objects for 4 declared parts. As merged the plate is spread over about 370 × 155 mm, mostly off a 220 mm bed; pressing Arrange in the slicer packs it onto one.

`./scripts/check.sh` (whole tree) exits 0.

Layer-by-layer check by review, sections every 0.2 mm against the layer below: the only thing that starts in mid-air on any part is the gate lintel, two regions 2.00 mm wide by 22.000 mm span at z = 37, each anchored at both ends. The slicer prints them as five bridge strands per lane and drops no feature on any part.

## Brief audit — measured on the exports, not read from the variables

Sections and bounding boxes taken from the gated STLs with trimesh.

| Brief row | Brief | Measured |
|---|---|---|
| Lanes | 2 | 2 lanes between 3 posts per fin |
| Fins, default assembly | 10 | 5 lands per rack × 2 racks |
| Strip length | 40 | land centres at 20, 60, 100, 140, 180 mm: pitch 40.000 |
| Tape plane above base | ≥ 25 | land top z = 34.000, base top z = 8.000: 26.000 |
| Lane for a 19 mm tape | 19 + clearance | 22.03 mm between posts at the tape plane |
| Clear gap between fins at the top | ≥ 28 | 35.43 mm between posts, 36.8 mm between lands |
| Core Ø 25.4 | hub must run in it | hub Ø 24.600, 0.800 clear on diameter |
| Roll Ø 62 max | must clear the cradle | `roll-fit` empty; floor 3.0 mm, gate 20.1 mm, walls 1.5 mm each side |
| Largest part | ≤ 210 long, ≤ 200 tall | rack 207.75 × 57.20 × 42.00; cradle 58.00 tall |
| Assembled length | about 500 | 30 + 97.7 + 200 + 200 + 33 = 560.7 |
| Strip length a parameter, 30–60 | 30–60 | 40–60 as shipped, 36 with `ledge_l = 8`; under 35.2 breaks the brief's own 28 mm gap |
| "A taut tape lies on every fin top in one pull" | lies on the fins | not met, by design: it hovers 2.8 mm over the first fin and 0.3 mm over the last until pressed (D4) |
| "Snug enough to carry the chain when lifted" | carries the chain | a straight lift catches at 1.4 mm; a hanging rack is held by friction only, untested (D3) |

Strip count, traced by review on the assembly: cuts fall at x = 40, 80 … 400. The fin nearest the rolls keeps the feed parked; each of the other nine fins holds one 40 mm strip per lane; the ledge keeps a tail of about 26 mm plus whatever was in the fingers. Nine strips a lane, eighteen a pull. The plate as shipped, with one rack, gives four a lane, eight a pull.

## Bugs caught (and what caught them)

- **A dovetail socket on the upright cradle's end face.** Scored 100/100 and would have printed with a drooping lip. Caught by an independent printability review slicing a mock, not by the gate. Led to D2 and D3.
- **Zero-area triangles on the cradle.** Where one piece's edge ended part-way along a coplanar face of another (the floor's top edge under the wall ends, the back wall's top edge across them), the export carried collinear triangles and printcheck took 8 points. Fixed by never letting a piece's edge end on another's coplanar face: the floor runs past the wall ends, the back wall is set in 0.8 mm, inner pieces start inside the floor and stop inside the walls.
- **Feather edges at the socket mouth.** A bed chamfer on the joint's end face met the socket's flare and left slivers 0.05 mm thick; squaring the lips first left a second sliver between the mouth and the flank. Joint end faces now have no bed chamfer and the squared mouth runs past the flank at every height.
- **Socket cutter corner edges crossing at a point.** The cutter's loft, flare and lead-ins were hulls of one profile with different offset laws, so their mitred corner edges passed through single points. OpenSCAD 2021.01 exported that as vertex pairs 0.00001 mm apart and still scored 100/100; an emulation of CI's Manifold kernel (manifold3d over the same operands, not the nightly itself) exported the rack and end cap non-watertight. Caught by code review. Fixed by chamfering the offset corners of the flare and lead-ins and starting the two lead-ins at different heights; that emulation then came out watertight for every part in both union orders — wrongly for the cradle, as CI showed (next entry). The meshes gated locally have no vertex pair closer than 0.001 mm.
- **CI's first run failed the cradle (67/100) and the spindle (59/100), which the local gate and the emulation had both passed.** Caught by CI's real backend, nothing earlier. Two separate causes.
  - *Cradle.* OpenSCAD snaps a 2D profile to a fine grid before it extrudes it. The side walls are extruded profiles and the nose block is a cube; both started at `z_in` = 1.2, but the walls' 1.2 came out as 1.1999969. Where both meet the nose face, the Manifold kernel kept the two edges, 0.000003 mm apart, as real geometry, and the STL writer, which prints six significant digits, then wrote them as one line: four zero-area triangles and a mesh that was no longer watertight. OpenSCAD 2021.01's kernel merges the coplanar faces first and leaves no trace of either edge, so the local gate cannot see it. Fixed by starting the walls at a depth of their own (`z_wall_in`, 1.8). The solid did not change: the symmetric difference against the old cradle is 0.000 mm³.
  - *Spindle.* It was a single `rotate_extrude()` of a profile that touches the axis. The nightly exports a part that is one primitive as that primitive's raw mesh, and its raw revolve carries a zero-area triangle per side at each pole and along the axis: 384 of them, 190 of those duplicates. OpenSCAD 2021.01 builds the same 1,920-triangle revolve, but its STL writer leaves the degenerate ones out of the file (1,536 written), so the local gate never saw them. Fixed by building the spindle as one explicit polyhedron (`ring_loft`): every face a triangle, each end a fan about a centre point, 1,536 triangles with none degenerate and none duplicated. Volume about 0.05 mm³ from the old one. A review of the fix found that a `$fn` of 1, 2 or a fraction then wrote a broken spindle, where `rotate_extrude()` had coped; the side count is now clamped to a whole number of 3 or more, and `ring_loft` refuses anything else.
  - *Why the emulation missed the cradle.* It fed Manifold single-precision meshes, and Manifold takes its merge tolerance from the precision of its input, so it merged the two edges before the union; and it did not round its output the way the STL writer does. Fed double-precision meshes, and with the six-digit rounding, it reproduces the failure on the old geometry — on the same edge, the nose face at z = 1.2, where CI reported it — and is clean on the new, for every part in both union orders. It cannot see the spindle's failure at all: a part that is one primitive never passes through a boolean. The nightly's writer also keeps a triangle whose corners collapse onto each other, where 2021.01's leaves it out; the emulation counts those as defects.
  - The rule taken from it: a coordinate that comes from a 2D profile and one that comes from a 3D primitive must never be meant to coincide on a surface, and a part that is a single primitive must already be a clean mesh.
  - Confirmed by CI on commit 2b96a24: all five gated meshes 100/100 on the nightly's Manifold backend.
- **Rolls and tape in the exported STL.** The default render was the assembly with its payload drawn, and a full render exported the rolls and the tape as geometry: 22 of the 27 bodies in the file the site's workbench shows and offers for download. Caught by the owner, on the workbench. `show_payload` now defaults to false, as the owner asked: the default render, the workbench and its download hold the five printed bodies, and the preview shots that show the tape ask for it in `cameras.conf`. A first fix drew the payload only when `$preview` was true; it kept the previews as they were but left the workbench's `show_payload` switch doing nothing, because the workbench only ever does full renders. The default export is still a picture of the assembly, not the file to slice; that is the plate.
- **The carry claim.** "Pick it up by the cradle" was written from the straight-lift proof. Two reviewers independently found the pivot path a hanging rack can take. The claim is now what D3 says.
- **A flat end-cap ledge** on the lightest, lift-free part (D6), **8 mm of threading room** (D9), and **a coupon narrower than the joint it stands in for** (its socket arms were 4 mm against 14 mm on a rack) — all caught by review, all fixed.

## Session-resume context

- Entry: `tape-strip-rack.scad`. Coupon: `tape-strip-rack-coupon.scad`. Style: none.
- Branch `ccr-8541794c-mwyuwk`; the draft PR closes #1062.
- Nothing has been printed. The first field test should answer, in this order:
  1. does the joint coupon fit at 0.20, with about 0.6 mm of push-pull play;
  2. assemble cradle and one rack, lift by the cradle and shake: does the rack stay on;
  3. does a strip stay on a ribbed land through the cut, and does rolling it off sideways lift the rack or the end cap;
  4. does the lintel bridge cleanly;
  5. can both lanes be cut in one snip with your scissors (the far tape's far edge is 51 mm in), or is it one snip a lane;
  6. does the rack need feet on your table.
- CI's render gate uses openscad-nightly with the Manifold backend, which cannot be installed in a build session (its download hosts are blocked). The local gate runs OpenSCAD 2021.01 and cannot see what that backend does differently: the first CI run failed two parts it had passed (Bugs caught). The nearest local check is the emulation described there — manifold3d, each piece exported from 2021.01 as binary STL and loaded in double precision, the result rounded to six significant digits — and it is still not the nightly.
- A part that is one primitive hides degenerate triangles from the local gate: 2021.01 builds them and its STL writer leaves them out. The check is to compare the `Facets:` line of the render log with the triangle count in the file. For the spindle they are 1536 and 1536; before the fix they were 1920 and 1536.
- Open, for the owner: whether to publish a functional look-alike of a commercial product (`PM.md`, Open decisions).

## Field test log

_Real prints of this design, newest at the bottom. See templates/FIELD-TEST.md
and docs/print-feedback.md for the convention._

(none yet)
