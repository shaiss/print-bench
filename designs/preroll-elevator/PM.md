# preroll-elevator — product charter

The enforceable owner of what this design is, who it is for, and what is out of
scope. Engineering log is `NOTES.md`; the stranger-facing page is `README.md`.

## The product, in one paragraph

A twist-up pre-roll dispenser styled deliberately as an industrial hex bolt with
a nut on top: unscrew the cap-nut lid, twist the bolt-head base, and a central
lead-screw presents four rolls out the top; twist back to retract and cap to
close. The mechanical look is a feature, not a coincidence — the interior *is* a
nut climbing a bolt. It is for someone who wants a durable, tactile, refillable
carrier that protects fragile rolls and looks like a shop object, printed with no
hardware.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Rolls hold their presented height (no back-drive) | single-start, lead angle ≈ 8.3° < PLA friction | design panel | a multi-start screw is proposed for faster travel |
| N2 | Mechanism steals no roll space | 4 rolls ring a central screw | user brief | roll count or layout changes |
| N3 | No metal fasteners / bought-in parts | 5 printed parts, snap retainer | user ("design as multiple objects", parts-only assembly) | a metal ring/screw is proposed |
| N4 | Pure first-party OpenSCAD (no GPL) | assembly.conf parts-only, no `vitamin:` | licensing policy #160 | a NopSCADlib vitamin is added |
| N5 | Deliverable is the separable plate, not a fused STL | `ci.plate` = 5 objects | multi-part-fuse field test | parts are re-merged into one body |
| N6 | Every tuned fit is dialable + gated | coupon + `thread_tol`; `ci.fitchecks` empty+interferes | repo fit-gate convention | a fit is hardcoded without a coupon/fitcheck |

## Out of scope

**Deferred:** king-size default (dogwalker is the shipped default; king is a
preset); a printed detent/click at the pop-up stop; a keyed lid orientation;
per-printer profile via `printer.conf`.

**Never:** storing anything but the intended payload's geometry in the shots
(rolls are the user's, not printed); a design that only slices as one fused body.

## v1 — definition of done

- `render.sh` clean, `gate.sh --slice` exits 0 (printcheck watertight, test-slice,
  the 5-object plate check, all four thread-mate fitchecks).
- Both threads (central + lid) proven by an `empty` fitcheck and a 180° `interferes`
  control.
- Product page complete with the CI-generated hero, open, cutaway, exploded, GIF
  and contact-sheet.
- Assembly instructions generated (`assembly.conf` → `ASSEMBLY.md` + exploded.png).
- Human approves the shape (the merge decision).

## Product page & shots (art direction)

The page promise: "a pre-roll dispenser that looks and works like a real
machined object." Tier-1 shots (geometry-true): a **closed** hero (the iconic
hex-bolt), an **open/presenting** shot (cups raised), and a **cutaway** for the
mechanism. The **elevator GIF** is the money shot — the twist-to-present motion.
No AI/lifestyle tiers for v1. Rolls appear only as ghost payload in the
deterministic previews, never in the geometry-true studio shots.

## Backlog, ranked by user value

1. Field-print the coupon and record the real `thread_tol` (print-feedback).
2. A subtle detent at the top stop so "fully up" is felt, not just hit.
3. Knurl or flute band on the body for extra twist grip (keep the bolt read).
4. King-size validation (Ø10 screw stiffness over longer travel; see NOTES open q).

## Open decisions

- Central screw stays Ø10 across presets, or grow to Ø12 for king? (torque vs
  pack) — deferred, dogwalker default unaffected.
- `pop_up` fixed at 36 mm for all presets vs scaled with roll length — fixed for
  v1 (keeps screw length constant).

## Decision log

- Body is a **round** partially-threaded bolt shank, not a hex shank: a real bolt
  has a hex head + round shank, so this reads more correctly as "bolt", matches
  the approved concept, and the hex head + hex nut carry the mechanical look.
- **Single-start** central screw chosen over multi-start: self-locking is the
  product requirement (N1); the cost is 9 turns of travel, accepted as a
  deliberate "dispenser feel".
- Anti-rotation via **through-slots open at the top rim** (not blind grooves):
  avoids a thin groove floor and lets the wide elevator tabs enter from the top;
  interrupts the lid thread into 4 arcs, which still engages and self-locks.
