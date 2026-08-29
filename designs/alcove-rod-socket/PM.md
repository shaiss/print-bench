# Alcove rod socket — product charter

## The product, in one paragraph

A screw-together end socket for a 40 mm curtain/closet rod that spans an
alcove or recess, printed in pairs: a wall boss screwed to each facing wall,
a knurled collar hand-threaded onto it capturing the rod end. For the person
whose curtains come down for washing a few times a year; the one thing it
must do well is **hold the rod between two walls and let it go tool-free**.

## Non-negotiables

Each carries an `assert` in the .scad where a number can guard itself.

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Rod bore = measured rod + slip | 40.0 + 0.6 mm | brief, given row (user's rod) | calipered barrel ≠ 40.0 where it sits |
| N2 | Structural walls, not floor-thin | 3.2 mm (≥ 3 brief floor) | brief (chunky, load-bearing) | a field test shows deflection at the collar rim |
| N3 | Tool-free removal | unthread collar, ≤ ~1½ turns | brief (Drik: the frequent action) | engagement redesign changes lead |
| N4 | Supportless, axis-Z prints | 0 support faces | brief printer section | any part gains an overhang a stock profile can't bridge |
| N5 | Printed thread = `lib/threads-fdm` fixed profile | 45° flanks, pitch 4, 2 starts | brief + Jane's review | a field test jams or strips at `thread_tol` 0.3 |
| N6 | Knurl flute width floor | ≥ 1.2 mm printed | brief + Jane's review | nozzle ≠ 0.4 mm becomes the default |
| N7 | Screw head below the rod seat plane | assert in .scad | brief (rod seats on shoulder) | screw size/count change |

## Out of scope

**Deferred** — backlog below.

**Never:**
- Flat-wall face-mount variant (rod ∥ wall) — set aside in the brief's
  ideation for the confirmed alcove use.
- Machine threads (BOSL2 `screws.scad`) — 60° internal flanks droop printed
  axis-up; the FDM trapezoid is the point.
- Scaled reference meshes — the deliverable is the parametric .scad.

## v1 — definition of done

- [ ] `render.sh` clean, `gate.sh --slice` exit 0 on boss / collar / both
      coupons; `fit-mate` empty, `fit-mate-ctrl` interferes (negative control)
- [ ] `readme-gate.sh` passes (the style claim is withdrawn — NOTES D10:
      the printed thread's tessellated crest cannot satisfy the pack's
      required rounding rules; tokens still used)
- [ ] Both coupons committed and documented ("Print this first" in NOTES)
- [ ] A stranger can answer *does this fit my pole* from the README alone
- [ ] Field test: one printed pair holds a real 40 mm rod in a real alcove
      — stays open until the **v2 proving print** (the plate, laid out side
      by side; v1's failure was packaging, so the holder itself is still
      unproven in the field). NOTES "Field test log" when it happens

## Product page & shots (art direction)

**Page promise.** Curtains down for washing without a screwdriver.

**Shot list — tier 1 (real studio renders).** Ranked; the first is the hero.

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the assembled socket — boss, threaded collar, scale | hero, slight high angle to read the collar mouth | graphite-blue `7d8a97` satin | `part="assembly"` |

**AI product stills — tier 1.5.** None for v1 — the tier-1 hero and cutaway
carry the shape; AI hops add nothing a utility part needs.

**Lifestyle scenes — tier 2.** None for v1 (a curtain-rod alcove scene is
stageable later if the page under-converts).

**Motion clips — tier 2.** None for v1. If ever: the collar unthreading —
the one motion the part really performs — seeded from the hero.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B3 | Ship the shallow collar as a gated part (`engagement_depth=12` in `ci.parts`, exported with the Release) | #1: the deep+shallow install is now the documented trick, and the page has to tell the reader to hand-render the far-side collar with `-D` — the exact foot-gun the deliverable rules exist to stop. (The old item's docs half landed in #379; what remains is shipping the part.) | small: one `ci.parts` row + re-gate |
| B4 | PETG/ASA field test in a hot window | the page now tells permanent installs to print PETG/ASA with retune numbers — unproven advice until this prints | one print + NOTES entry |
| B1 | Witness slot / seat detent ("is the rod fully in?") | brief's optional ask; install confidence — plus vibration insurance: ~730 axial curtain-tugs/yr vs single-digit unthreads, and a steep 2-start lead is what walks loose under cyclic load; nothing on the rod resists a slow unthread. Measured by the proving print's week-of-use seat check; a walked collar promotes B1 to #1 | small geometry + re-gate |
| B2 | Anti-rotation rib (screwless alternative to `screw_count=2`) | protects drywall anchors from spin torque | small geometry + re-gate |
| B5 | Sizes other than 40 (25 mm reference origin) | parameters exist but are untested at other rods — the page now says so outright, so this is the proof, not the disclosure | coupon set per size |

Re-ranked 2026-08-24 per the #379 thread's ruling (Vera's note: the issue
body's order was two rounds stale — the committed order wins). A "B6" appears
in early thread drafts but never gained a recoverable definition; it is not
carried here.

## Open decisions

All four are the brief's own open questions, non-blocking for modeling.

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Actual rod barrel Ø where it sits | before printing, not modeling | 40.0 given value; bore coupon verifies |
| Alcove width vs rod length (install gap) | install, not modeling | deep+shallow pair via `engagement_depth` |
| Mount surface (drywall/wood/masonry) | no | M5 wood screw, recessed; anchor is the user's call |
| Witness slot wanted? | no | not in v1 (B1) |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-23 | Thread major 47.0 = bore + 2·wall (brief said ≈ 50) | brief's "+clearance" read as female-side fit clearance (`thread_tol`, collar OD wall stack); recorded in NOTES D2 and the PR audit |
| 2026-08-23 | `lead_in` 1.6 mm (8 layers at the pinned 0.2 mm height) vs brief's "~1–2" | doubles as the thread phase offset that makes the mate boolean exact (NOTES D3/D4) |
| 2026-08-23 | One tier-1 hero shot only | utility part; cutaway + contact sheet carry the internals |
| 2026-08-23 | 2-start thread (lead 8 mm) | ~1¼ turns to full engagement = tool-free both directions (N3) |
| 2026-08-23 | Withdraw the `workshop-utility` claim, keep the tokens | the pack's required corner-radius/curve-smoothness rules fire on the male thread's tessellated crest (phantom r=1.76/fn≈8 rounding) and no waiver exists; printability wins (CLAUDE.md), amending the pack is the owner's call — NOTES D10 |
| 2026-08-24 | The deliverable is the multi-object 3MF plate, never one STL of both parts (NOTES D11) | v1's field test printed fused — STL carries no object separation, so a boss+collar export slices as one welded body (#377) |
| 2026-08-24 | Field test FAILED on packaging, not the holder | the parts were exported stacked/assembled: they fused, and the stack put the extruder over a mid-air discontinuity (spaghetti ~10 layers in) — the geometry never got tested |
| 2026-08-24 | Correction: the 3MF cures the *fuse*, not the *spaghetti* | two separate objects re-stacked vertically still print the upper over open air; the plate's side-by-side flat layout is the safe way, and stacking is never a space-saving option |
| 2026-08-24 | v1 → v2 numbering (not v0.2) | the field-test failure forced a second version before any release shipped: v1 = the frozen geometry, v2 = the packaging fix |
