# nuggs-bottle-adapter — engineering log

## Goal

The NUGGS **bottle adapter** (issue #515): the part that turns an
off-the-shelf PCO-1881 water bottle into a drop-in habitat module. One
printed body, two interfaces — the standard genderless quarter-turn NUGGS
port below (80 mm bore, full library defaults), a threaded throat above that
takes a stock bottle finish. The animal never passes *through* this module:
the passage narrows to the bottle's own orifice by design, so this is a
service module (water/bedding), not a transit module — the 70 mm bore floor
governs entrances an animal uses, and the port below it stays full standard.

## Given / assumed measurements

| Measurement | Value | Source |
|---|---|---|
| NUGGS bore | 80.0 mm | given — the standard, `lib/nuggs-coupling.scad` defaults |
| `port_tol` | 0.30 mm | given — the standard's default, coupon-tunable |
| Thread crest OD | 27.4 mm | given — ISBT PCO-1881, cross-checked vs BOSL2 `bottlecaps.scad` |
| Thread pitch / starts | 2.7 mm, **single**-start | given — the standard (see Key decisions #1) |
| Thread engagement | 650° (travel 4.875 mm) | given — the standard |
| Thread root (bottle) | 24.20 mm (depth 1.6) | given — the standard, reference only |
| Orifice ID | 21.74 mm | given — the standard; the land opening must not pinch below it |
| Lip OD / lip-to-thread | 25.07 mm / 1.70 mm | given — the standard |
| Tamper ring | Ø28, spans to 10.8 mm below lip face | derived from standard dims (BOSL2's pco1881 model) — rim-height clearance only |
| Body OD | envelope Ø96.8 mm | **assumed-derived** — the brief said ≤96, computed from bore+wall only; the coupling ring adds `lug_r` 6 → Ø96.8. Two still sit side by side on a 210 mm bed |
| `bottle_tol` | 0.25 mm | **assumed** — the tuning knob, swept 0.15–0.38 on the coupon |
| Watertightness | none (printed land) | non-blocking per brief — proceed on the default; see backlog |

Owner's ruling on the brief (comment, 2026-09-02): "Model to the PCO-1881
standard … No caliper numbers will follow; the standard is the spec."

## Key decisions

1. **Single-start, per the standard.** The brief's Must-fit row said
   "~2.7 mm effective pitch, multi-start". PCO-1881 is a single-start
   2.7 mm thread with 650° of engagement; BOSL2's `bottlecaps.scad`, the
   ISBT thread-spec tables and the community cap designs all agree. The
   owner's "the standard is the spec" settles it. `bottle_thread_starts`
   stays exposed so a sibling finish (PCO-1880, 3-start) is a table edit.
2. **Female thread = the FDM library profile, not the bottle's.** The
   bottle's ~15° flanks would bridge/sag printed as a female cavity.
   `lib/threads-fdm.scad`'s 45°-flank trapezoidal helix is printable in a
   vertical bore; used here grown by `bottle_tol` off the bottle's crest
   diameter, with the minor bore derived per the lib's caller contract
   (`d_major − 2·depth + 2·tol`).
3. **The depth cap, worked through.** The lib's guard requires the FDM
   profile to fit inside one pitch: `0.25·pitch + flank_add(tol) + 2·depth <
   pitch`. At pitch 2.7 that caps depth at ≈0.85 (tol 0.25). Chose **0.60**:
   ridge land between grooves 0.618 mm (floor 0.5, asserted), radial
   engagement 0.35 mm at the default tol. The bottle's own 1.6 mm thread
   depth is simply not reachable with a printable female profile at this
   pitch — the engagement is smaller than a cap-molded thread's, which is
   exactly why the coupon is mandatory before trusting the body.
4. **Load path corrected from the brief.** The brief pictured the bottle
   hanging with "threads in tension". Mouth-down above the adapter, gravity
   seats the bottle's lip *onto* the printed land annulus — the land carries
   the weight in compression and the thread only resists rotation. This is
   the stronger arrangement; thread depth is sized for retention (decision 3).
5. **No counterbore for the lip.** The minor bore (Ø26.7 at default tol)
   already clears the bottle's lip (Ø25.07) by ~0.8 mm/side, so a recessed
   lip seat would be geometry for geometry's sake.
6. **Rim height capped by the tamper ring.** The bottle's tamper band spans
   to 10.8 mm below its lip face; the rim tops out 9.9 mm above the land
   (asserted ≤ 10.3), so the ring clears by ~0.9 mm at full seat. The
   support ring (Ø33) never reaches the rim during travel — it stays above
   it throughout.
7. **Interior funnel at 44°, exterior shoulder at ~40°** — both under the
   45° supportless ceiling (issue #34's measured limit), so the part prints
   supportless in the family pose: standing on the port's sector tips.
8. **Coupon layout.** Two stations on one plate: the library's own
   `nuggs_neck` stub in the family coupon pose, plus four labelled rings
   carrying the production `throat_cavity` verbatim at tol 0.15/0.22/0.30/0.38.
   Two disconnected bodies on purpose (printcheck notes them as INFO) — the
   coupon is a hand fixture.
9. **The land opening drifted, and the export caught it.** The §6 audit
   measures the gated STL, not the parameters (issue #37's lesson): the land
   pinch measured **Ø22.96 against the 22.0 parameter**. Cause: the throat's
   bore cut starts 0.5 mm below the land plane (the overlap that keeps the
   union of cuts free of coincident faces), and the bore is the wider surface
   there — so the *bore* truncates the funnel, and a cone aimed at `land_ir`
   at `z_land` is cut 0.5 mm early, leaving the opening slope·0.5 wide. Fix:
   the cone is now aimed *past* the plane so it crosses `land_ir` exactly at
   `z_floor` (where the bore begins and the lip seats), keeping exactly
   `funnel_deg` over its visible span; `z_land` is the throat origin, 0.5
   above the land plane. Re-measured off the re-gated export: **Ø21.997**.
   Side effect: rim +0.5 mm (part height 66.43).

## Print settings

- **Orientation:** port down — standing on the coupling sector tips (the
  family pose). No supports anywhere: steepest surface is the 44° funnel.
- **Material:** PLA for dry service; PETG if the bottle will be washed hot.
- **Layer height:** 0.2 mm, 0.4 mm nozzle. The thread ridge (0.6 mm land) is
  3 layers wide — do not go coarser.
- **Walls:** 3 perimeters minimum (the throat wall is sized 3.0 mm = 6
  perimeters at 0.4 mm).
- **Infill:** 15% gyroid/gird; the working surfaces are all perimeters.
- **Brim:** none needed; the sector-tip foot is the family bed patch.

## Print this first

The coupon (`nuggs-bottle-adapter-coupon.scad`, gated by CI like any part)
carries both fits. In order:

1. **Port station** — the stub. Insert a mating NUGGS module and quarter-turn
   it: it should lock with a definite stop and slight spring, no rattle. If
   loose/tight, tune `nuggs_port_tol` (0.10–0.60, ±0.05 steps). Tight only at
   the very start of insertion and free after is elephant foot, not tolerance
   — a knife pass on the tips (or less first-layer squish) fixes that; tune
   only when it's tight through the whole engagement.
2. **Thread stations** — four rings labelled 0.15–0.38. Screw a real
   PCO-1881 bottle (any soda/water bottle, washed) into each: find the
   station that grips firmly without cracking or skipping threads when you
   try to rotate the bottle by hand. Set `bottle_tol` in the design to that
   value and slice the adapter.
3. The label is cut into the strip beside each ring (outboard of its row).

A station whose thread skips (crest rides over the ridge) is too tight;
one that spins freely is too loose. If *none* grip, raise `f_thread_depth`
toward the 0.85 cap (ridge land thins as you do — see Key decisions 3).
