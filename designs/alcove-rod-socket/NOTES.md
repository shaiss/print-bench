# alcove-rod-socket — engineering notes

## Goal

A parametric, two-part **screw-together end socket** for a 40 mm round
curtain/closet rod spanning a recess or alcove, used in pairs: a wall boss
screwed flat to each facing wall, the rod's ends plugging into knurled collars
that hand-thread onto the bosses. Removing the rod for washing = unthread the
collar, no tools. Brief: issue #355 (reworked from MakerWorld #1200171, a
2-part fixed-STL 25 mm holder, scaled intent not mesh).

## Given / assumed measurements

From the brief's *Must fit / hold* table:

| Quantity | Value | Status | Where it lives |
|---|---|---|---|
| Rod barrel Ø | 40.0 mm | **given** (verify with calipers — blocking before printing) | `rod_d` |
| Socket bore Ø | 40.6 mm (rod + 0.6) | assumed slip default | `bore_d = rod_d + rod_clearance` |
| Rod engagement depth | 28 mm | assumed (deep side of the deep+shallow install pair) | `engagement_depth` |
| Wall thickness | 3.2 mm | assumed structural (≥ 3 mm brief floor) | `wall` |
| Thread major Ø | ≈ 50 mm per brief, built **47.0** = bore + 2·wall exactly | assumed+derived | `thread_major` — see decision D2 |
| Mounting screw | M5, recessed head | assumed | `screw_size`, `screw_count` |
| Grip Ø | brief "thread major + ~4", built major + 7.0 (wall stack over the groove) | assumed+derived | `collar_lower_od` |

## Multi-part layout

One `.scad` with a `part` parameter (`assembly` default renders the seated
preview). Two coupon wrappers exist as sibling files
(`alcove-rod-socket-coupon.scad`, `…-bore-coupon.scad`) — include-and-override,
never copied geometry; `gate.sh` picks them up automatically.

## Key decisions

- **D1 — Thread is the fixed FDM profile, only the major scales.**
  `lib/threads-fdm.scad` 45° trapezoid, depth 1.2, pitch 4, **2 starts** →
  lead 8 mm/turn, so the 10 mm neck engages in ~1¼ turns: tool-free on and
  off, exactly the "collars come down for washing" action. Machine threads
  (BOSL2 `screws.scad`) were rejected per the brief: a 60° internal flank
  droops printed axis-up.
- **D2 — Thread major 47.0 = bore + 2·wall.** The brief's row said "≈ 50
  (bore + 2·wall + clearance)". Reading: the clearance term is the *fit*
  clearance, which lives female-side (`thread_tol` grows the collar's bore,
  and the collar OD = groove root + 2·wall = 54.0 carries the wall). Built
  this way the boss neck's thread root sits 3.2 wall outboard of nothing
  (the rod never enters the boss), and the collar keeps ≥ 3.2 mm over the
  groove root before the knurl. Recorded as a decision because the built
  number differs from the brief's ≈ 50; the audit in the PR states it.
- **D3 — Phase alignment makes the mate boolean a proof, not a coincidence.**
  The boss lifts its male thread `lead_in` = 1.6 mm above the flange face;
  the collar cuts its female groove the same 1.6 mm above its rim. Seated
  (rim on flange face), rib and groove are exactly in phase, so
  `part=fit-mate` (their intersection) rendering **zero facets** is an exact
  assembly proof, and `fit-mate-ctrl` (collar turned 90° — at 2 starts that
  parks every rib half a pitch off every groove) interfering with 7688
  facets is the negative control that keeps the empty check falsifiable.
- **D4 — `lead_in` 1.6 mm is 4 layers, not the brief's "~1–2".** It has a
  second job: it is the shared phase offset (D3). It also keeps the collar
  rim's seating plane clear of the flange's elephant foot. Satisfies the
  brief's intent (first-layer squish cannot fatten the first turns) with
  margin.
- **D5 — Print orientations.** Boss flange-down (its use orientation). Collar
  **rod-mouth-down**: the internal thread prints at the *top* of the print,
  never on the first layer, and the bore's 45° mouth lead-in (D7) faces up.
- **D6 — BOSL2 `cyl` is origin-centered; kissing unions are not manifolds.**
  Iteration 1 shipped a flange floating 3.2 mm below z=0 (printcheck: 2
  bodies, empty layer 6.35–9.75) and a coupon shoulder that merely *touched*
  the thread core at z=3.6 (non-manifold edges, printcheck 67/100). Fixes:
  `anchor=BOTTOM` on every `cyl`, and every union in this file embeds
  0.5 mm+ real overlap instead of face contact. Lesson is general — see
  also `docs/derivative-designs.md`'s silent-failure family.
- **D7 — Bore mouth gets a 45° lead-in** (Ø40.6 → 42.6 over 1 mm at the rod
  entry) so a slightly-oversize rod or a raised rim reads as drag, not a
  wedge jam; both coupon bore mouths are chamfered for the same reason.
- **D8 — Knurl = cylindrical cutters parked outside the surface**, axis at
  `od/2 + r_cutter − depth`, so groove bottoms land exactly `knurl_depth`
  under the rim. Guards (as asserts): flute count ≥ 6, printed groove width
  ≥ `knurl_min_width` 1.2 mm (3 extrusion widths), flutes can't merge
  (pitch ≥ groove + 0.8), and ≥ 2.0 mm wall kept over the thread groove
  (`knurl_depth ≤ wall − 1.2`).
- **D9 — Screw head geometry.** 90° countersink, Ø = M5 socket head + 0.5,
  flush at the *neck's* top face; assert keeps the head below the plane the
  rod bottoms on (rod seats on the collar shoulder, never on the screw).
  `screw_count=2` grows the flange so both off-axis heads clear the neck —
  the brief's anti-spin option.
- **D10 — Style: builds from the `workshop-utility` tokens, does not claim
  the pack (printability wins).** The brief named the pack and the geometry
  uses its tokens (`style_fn` 64 everywhere but the lib-pinned thread helix
  at 96; `style_edge_chamfer` 0.6 on every rim; holes are M5 per the brief,
  not the family's `style_hole_d` 3.4). But the pack's two *required* rules —
  `corner-radius` (4 mm ±35%) and `curve-smoothness` (implied $fn ≥ 44) —
  fire on the boss and can never pass: stylelift reads the male thread's
  tessellated crest (a swept six-point polygon, `lib/threads-fdm`) as the
  part's dominant *edge rounding* — r = 1.76 mm at ~8 segments, 68% of
  curved edge length (measured off the export; the collar escapes because
  its female groove corners are concave and bucket as inner fillets). No
  honest geometry removes it — the thread profile is the mate-proven,
  non-negotiable function (N5), and no waiver mechanism exists between
  `style.conf` and `stylelift check`. Per CLAUDE.md ("a style is a
  constraint on look, not on printability: when the two conflict,
  printability wins"), the claim is withdrawn rather than the pack amended —
  changing the family's rule applicability is a pack-owner decision, not
  this design's. Re-adding `style.conf` needs that upstream call (follow-up
  issue on the PR).

## Print settings

- **Material:** PLA default; PETG or ASA for a hot/sunny window (heat + UV).
- **Nozzle / layer:** 0.4 mm / 0.2 mm.
- **Perimeters:** 3 (walls are 3.2 mm by design — the wall *is* the part).
- **Infill:** 20% gyroid (the socket is wall-dominated; infill is backup).
- **Supports:** none on any part, by design.
- **Orientation:** boss flange-down; collar rod-mouth-down (thread up top);
  both coupons as-rendered (flat sides down). All parts < 60 mm across.
- **Order:** coupons first (see below), then a boss + collar pair.

## Print this first

Two fits to tune, two coupons. Both are include-override wrappers on the
production modules — what you print *is* what ships.

1. **Thread coupon** (`alcove-rod-socket-coupon.scad`): male stub + female
   ring from the production thread. Screw the ring on: it should run free
   with slight play and hold without cross-threading.
   - Won't start or binds → raise `thread_tol` +0.05 mm and reprint.
   - Sloppy / rocks radially → lower `thread_tol` 0.05 mm.
   - A strip of values in one print:
     `./scripts/render.sh alcove-rod-socket --sweep thread_tol=0.2:0.4:0.05`
2. **Bore coupon** (`alcove-rod-socket-bore-coupon.scad`): a production
   rod-bore ring. Slide it along the real pole past both mouths.
   - Won't slide → raise `rod_clearance` +0.1 mm.
   - Visible wobble → lower it 0.1 mm.

Measure the pole with calipers first and set `rod_d` to the *barrel* reading
(where the socket sits), not the finial/ring size.
