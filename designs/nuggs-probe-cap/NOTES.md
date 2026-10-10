# nuggs-probe-cap — engineering notes

The resume-cold log for this design: the goal, the decisions and why, the
numbers that were derived rather than guessed, and the intended print
orientation. The product page (README.md) is what a stranger reads; this is
what the next session reads. Brief: issue #732.

## Goal

A **sealed sensor end-cap** for NUGGS tube systems: the plate-and-port piece
that closes the open end of any module while letting a temperature probe and a
thin sensor cable pass through the wall — without opening the tube to bedding,
seed husks or drafts. The NUGGS mandate names a "sensor or tool mount"
end-cap; the open-module briefs (#514 gauge, #515 bottle adapter) want an open
end and #592's vent-cap deliberately *breathes* — nothing in the catalog both
seals the bore **and** passes a sensor. That gap is this design.

Sealing here means **printed split-finger grip**: each pass-through is a bore
at nominal + clearance whose boss wall is slit into compliant fingers, so the
bore wall conforms around what passes and closes the annulus. It keeps out
bedding, husks and drafts. It is **not rated airtight** and the README says so.

## It consumes the shared standard; it does not redefine it

A **consumer** of `lib/nuggs-coupling.scad`, exactly like `designs/nuggs` and
`designs/nuggs-den` (no `derives.conf`): one `cfg` from `nuggs_cfg()` at the
standard defaults (bore 80 mm, wall 2.4, `port_tol` 0.30), handed to
`nuggs_port()` / `nuggs_bore_cut()` with the mirrored-port call-site pattern.
Every coupling guard — bore floor, bayonet clearance, travel — fires inside
`nuggs_cfg()`; none is restated here. The port fit is the standard's
(`port_tol`), tuned on `designs/nuggs`'s coupon, not this one. If the port
standard changes, this module inherits it.

## Given / assumed measurements (from the brief, marked)

| Measurement | Value | Status |
|---|---|---|
| NUGGS port | bore 80, wall 2.4, `port_tol` 0.30 | **given** (the standard) |
| Cap plate thickness | 2.4 mm (= port wall) | **given** |
| Probes | 2 × Ø 6.0 × ~30 mm DS18B20 stainless | **assumed** — brief says caliper the owner's; clones vary |
| Probe cable take-up | Ø 3.4 (brief band 3.0–3.5) | **assumed** |
| Cable gland | 1 × Ø 4.0 (brief band 4.0–5.0) | **assumed** |
| Grip clearance | +0.2 mm diametral | **assumed** — repo sliding-fit convention; coupon-tuned |
| Orientation | port face down, grips in-plane, no supports | **given** (brief) |
| Material | PETG preferred (fatigue-tolerant fingers); PLA workable | **given** (brief) |

Style: `none` (the brief's decision — functional part, no pack).

## Key decisions

1. **Print pose = use pose.** Port-down on the three sector tips (every NUGGS
   module's pose), plate stacked above, grip bosses rising from the
   keeper-side face. Every grip surface prints as in-plane vertical arcs; bed
   contact is the sector tips and their ribs alone. The model frame IS the
   print frame (bed at z = 0), so printcheck scores the part exactly as it
   prints — this is why the unmirrored-port alternative (sectors pointing up)
   is wrong for a cap: the sectors would print pointing at the bed.

2. **Ceiling relief: concentric 50° V-grooves.** The plate's habitat-side
   face is the ceiling over the mate's Ø 80 bore — 5027 mm² of flat
   overhang, which printcheck flagged at 4951 mm² unbridgeable (84/100,
   iteration 1). Issue #34 measured the supportless ceiling for enclosed
   NUGGS bores at 45° (45° → 92/100 clean, 60° → 9 % overhang); nuggs-den's
   rule is "no flat internal ceiling", nuggs-frieda's house angle is 50°.
   So the underside carries 12 concentric V-grooves (1.2 mm deep, 3.2 mm
   pitch, flank 50° from horizontal = 40° from vertical, under printcheck's
   45° threshold): every downward surface is either a 50° flank or a flat
   ring/island narrower than the 5 mm bridge span (the centre island is
   Ø 2.9). Score went 84 → **92** with the overhang warning gone. The groove
   root leaves 1.2 mm = 3 perimeters of plate (asserted); the keeper-side
   face stays **flat** — it is the face the grips stand on — and the plate
   is 2.4 at every tooth. This is the one deviation from the brief's "flat
   cap plate 2.4": the seal is honoured at every tooth, the flat is not, and
   the alternative (slicer supports) the brief forbids.

3. **Fitcheck proxies at NOMINAL, never bore-size.** A proxy cut at exactly
   the bore size shares boundary faces with the bore wall at the same
   tessellation; CGAL resolves that as a zero-volume shell of facets and the
   fitcheck reads "interference" — 656/108 false facets in iteration 1, the
   exact false reading the check exists to prevent. Proxies are now
   `d + grow`: seats at grow = 0 (nominal Ø 6.0 through Ø 6.2 bore), jams at
   grow = `grip_clearance + jam_oversize` = 0.8 (Ø 6.8 — past the whole
   tunable band, so it must interfere however the coupon was tuned).

4. **The grip, in one breath.** Straight bore at nominal + `grip_clearance`
   through plate and boss; boss wall split by three axial slots
   (`slot_w` 1.5) into fingers, each a 1.6 mm vertical wall rooted in the
   plate; 0.8 mm lead-in chamfer at the mouth self-centers what passes.
   Slots stop at the plate, so the seal face is never cut. The split is what
   lets one gland take up everything from the probe's Ø 3.4 cable to a
   Ø 4–5 hygrometer lead (asserted: gland bore − take-up ≥ 0).

5. **Gland round, not mouse-slotted** — the brief left it to the session on
   the coupon. A round bore at Ø 4.2 with split fingers already closes onto
   the Ø 3.4 cable; a mouse slot would trade round-probe compatibility for
   cable-only grip the fingers already provide. Revisit on the coupon if a
   real cable squirms.

6. **Layout** — 3 features at `port_radius` 20, 120° apart, the tight probe
   pair aft. Asserts hold every feature edge ≥ 1.2 mm inside the plate rim,
   probe gaps ≥ 8 mm of solid plate, and ≥ 6 mm clear to the axis (solid
   land under the island).

7. **Open product policy (not this PR).** Sealed-cap / blind-terminus (N3)
   and bore-side probe protrusion (N6) are parked for Keel — no geometry
   change until those decisions land.

8. **Probe depth is the keeper's, not the cap's.** A fully-home Ø 6 × 30
   probe projects ~25 mm past the plate underside; the mate's bore wall is
   40 mm off-axis, so a centered probe cannot touch it. The cap presents no
   sharp edge to blunt stainless (corrugated ceiling, vertical tunnel
   mouths).

## Print settings

- **Orientation:** as rendered — port face down on the sector tips. No
  supports; brim recommended (sector-tip contact, same as sibling NUGGS
  modules).
- **Cleaning:** hand wash only, ≤ 50 °C; never a dishwasher (NUGGS N7).
- **Material:** PETG preferred (fingers fatigue-tolerant); PLA workable with
  coupon-tuned thinner/clearanced fingers.
- **Layer height:** 0.2 mm. **Walls:** 3 perimeters (finger wall 1.6 = 4).
- **Infill:** 15 % gyroid is plenty; the part is shell-dominated.
- **Approx:** Ø 94.9 × 32.4 mm, ~40 g, ~3 h 20 m.

## Print this first

The coupon (`nuggs-probe-cap-coupon.scad`, ~18 min, 1.75 g) carries both
grips at production parameters. Tune `grip_clearance` on it in ±0.05 steps:

1. **0.20 (default)** — Ø 6 probe slides free; annulus seals bedding/drafts.
2. **0.10** — light pinch, holds the probe by friction (good for a cap that
   gets knocked by bedding).
3. **0.05** — hard grip, needs PETG fingers; PLA may crack them.

Also verify on the coupon: the gland closes onto the owner's actual cable
(drop the Ø 3.4–5 lead through the gland grip — it should slide at 0.20 and
grip at 0.10). **Caliper the owner's probes before freezing `probe_d`** — the
brief's own warning: DS18B20 clones vary.

## Session log

- **Iteration 1** (gate): exit 1 — `probe_seats`/`gland_seats` FAIL (656/108
  facets, the bore-size proxy CGAL artifact) + cap printcheck 84/100 with
  4951 mm² unbridgeable overhang (the flat ceiling). Coupon 100/100.
- **Iteration 2** (gate): **exit 0** — nominal proxies clear (seats empty),
  jams interfere (1208/474 facets, negative controls fire), cap printcheck
  **92/100** (only "2 degenerate faces" warning remains, post-slicer-repair
  class), coupon 100/100. Ceiling grooves verified in the mesh: 12 apex
  rings at r = 37.8 → 2.4 mm on the computed 3.214 mm pitch.
- **Copilot review nits** (PR #737, hourly Quill pass): README brim aligned
  with NUGGS sector-tip guidance (no “no brim” claim); fitcheck dispatch was
  changed to pass `at_*` placement + proxy depth explicitly (probe vs gland
  cannot collapse when `probe_d == gland_d`); README + NOTES carry N7
  hand-wash ≤ 50 °C / no dishwasher. Skipped: N3 blind-terminus, N6 bore
  protrusion, grip-preload redesign (Keel / larger eng).
- **Fitcheck collapse (CI red on #737 tip 2f08c00)**: the Copilot nit's
  `fitcheck(at, …)` / `at() grip_proxy(…)` is invalid OpenSCAD — modules are
  not values. Every seat/jam render warned `Ignoring unknown variable
  'at_probes'|'at_gland'` and `Ignoring unknown module 'at'`, then reduced
  to `intersection(){ nuggs_probe_cap(); }` (single child = the full cap).
  That is why CI reported the **same** 12534 Manifold facets for
  `probe_seats`, `gland_seats`, `probe_jams`, and `gland_jams` (empty failed;
  interferes "passed" vacuously on the same solid). Fix: dispatch on a role
  string (`"probe"` / `"gland"`) and call `at_probes()` / `at_gland()`
  directly — still distinct when `probe_d == gland_d`, and the proxy `below`
  depth parameter from that nit is kept.
