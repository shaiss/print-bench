# preroll-elevator — engineering notes

Resume context, decisions, and derivations. Product page is `README.md`; the
product charter is `PM.md`; this file is the log.

## Goal

A chapstick / glue-stick–style twist tube that stores and *presents* pre-rolls.
Unscrew the hex cap-nut lid, twist the hex knob at the base → a central screw
raises an internal elevator carrying 4 pre-rolls in a ring so their tops rise
out the top to grab; twist back to retract, cap the lid to close and protect.
Styled deliberately as an **industrial hex bolt with a nut on top** — the
mechanical look is the point, and the interior echoes it (the elevator is
literally a nut climbing a bolt).

Design brief: issue #471. Approved concept canvas (blueprint sheets):
https://claude.ai/code/artifact/b3e488f9-be4b-4bb9-a8c3-b8bc56c484d3

## Given / assumed measurements

All **assumed** (no physical sample supplied) — driven by a size-preset selector,
default = slim dogwalker. Presets (length / diameter, mm):

| Preset | Roll length | Roll dia | Notes |
|---|---|---|---|
| **dogwalker** (default) | 70 | 7 | slim mini pre-roll |
| 1¼ | 84 | 7.5 | |
| 98-special | 98 | 8.5 | |
| king | 109 | 8.5 | full size |
| custom | (param) | (param) | user override |

- **Preset length = the roll's TOTAL finished length** (standard cone
  nomenclature: the "70 mm dogwalker" / "109 mm king" number is the whole cone,
  filter tip included — not cone-paper plus a separate tip). `roll_len` drives
  `z_rim` directly, so a standard roll seats `retract_gap` below the rim and the
  lid closes. Long-crutch variants (e.g. a 40 mm-crutch dogwalker) go to `custom`.
  (Round-1 review double-count, resolved — see PM.md decision log.)
- Roll count: **4** (given by user).
- Pop-up above rim: ~36 mm (assumed, grab comfort).
- Cup bore = roll dia + ~1.5 mm slip clearance.
- Body OD (dogwalker): ~40 mm, derived from a 4-roll ring around the central
  screw (see packing math once the design panel confirms).

## Key decisions

1. **Mechanism = central-screw elevator (glue-stick topology), NOT
   print-in-place.** A central printable trapezoidal screw down the middle; the
   elevator is a nut (female central thread) with anti-rotation tabs riding
   full-length slots in the body wall; the base hex knob spins the screw; the
   elevator (held from rotating) travels vertically. The 4 rolls sit in a ring
   *around* the screw, so the mechanism occupies the dead centre and steals no
   roll space. Parts print separately and assemble by hand.
2. **Six printed parts:** `body`, `lid` (hex cap nut), `screw` (central lead-screw
   + capture flange + hex torque stub), `knob` (hex bolt head; presses onto the stub
   and captures the screw against the floor), `elevator` (carrier nut + 4 cups +
   anti-rotation tabs), `cap` (press-on pop-up stop on the screw tip). No separate
   retainer (floor-capture) and no on-screw collar (it would trap the nut — the
   pop-up stop is the press-on cap; see "Bugs caught").
3. **Threads via `lib/threads-fdm.scad`** (printable trapezoidal, 45° flanks,
   supportless in a vertical bore). Two thread pairs: the central screw
   (male on screw-knob ↔ female nut in elevator) and the lid (male on body top
   OD ↔ female in lid). Same `d_major/depth/pitch/starts/seg` on each pair;
   `thread_tol` (0.3 default) on the female only; the **mandatory minor bore**
   is cut on every female. Mirror `alcove-rod-socket`'s idiom, including the
   `lead_in` phase offset that makes the boolean fit-mate proof exact.
4. **Deliverable = multi-object 3MF plate** (`ci.plate`): the parts print
   separately, so a single fused STL would import as one welded body. Also ship
   a "print this first" coupon for the tuned fits.
5. **Assembly instructions:** ship `assembly.conf` (**parts-only, no NopSCADlib
   vitamins → no GPL boundary**) → `ASSEMBLY.md` + `previews/exploded.png`. One
   of the first designs to ship assembly instructions.
6. **Style = none** — bespoke industrial hex-bolt aesthetic intrinsic to the
   mechanism (not lifted from a `styles/` pack).

## Print orientations (intended)

- `body` — knob-end (base) down; external lid thread at top, internal
  anti-rotation slots run the full length; the top rim thread prints last.
- `lid` — open end up (internal thread at the top of the print, never sees
  first-layer squish — the `alcove-rod-socket` collar trick).
- `screw` — thread up, the unthreaded Ø8 tip and hex torque stub on the bed (a tall
  part on a small base — print with a brim + slow outer wall, and dress the stub
  after; the flange adds mass low down).
- `knob` — hex flat down, hex socket up (blind socket, supportless).
- `elevator` — cups up; the central female nut is at the bed, but its first engaged
  turn now starts above the Ø11.6 disk bore (which took the lead-in), so it bridges
  in — slightly gritty until it beds in, compensated by the coupon-tuned `thread_tol`.
- `cap` — flat, blind bore up (supportless); pressed onto the screw tip after assembly.

## Print this first

Before committing to the full tube, print the two coupons. `preroll-elevator-coupon.scad`
carries the production central-screw male stub + the elevator's female nut ring — dial
`thread_tol` in ±0.1 mm steps (or a labelled `--sweep` strip) until the nut runs free
with slight play; the same `thread_tol` sets the lid. The `tab-fit-coupon` part (a
Customizer `part` value) carries the anti-rotation slot + tab pair — open `slot_w` by
0.1 mm if the tab scrapes. The knob→screw hex key (`knob_key_clear`) and the cap→tip
press (`cap_fit`) are firm presses; a touch of glue is optional (neither is needed for
screw capture, which is mechanical via the floor). A backlog item folds lid-ring,
knob-block and cap blocks into the coupon so every fit is print-this-first.

## Open decisions (non-blocking)

- Central-screw starts — RESOLVED: single-start, for self-locking (N1); the cost is
  9 turns of travel, accepted as the "dispenser feel".
- Retainer method — RESOLVED: no separate retainer. The screw is captured by the
  body floor between its flange (above) and the press-on knob (below).
- Top-stop method — RESOLVED (round 2/3): a separate press-on `cap`, not an on-screw
  collar (a collar wider than the nut bore traps the nut — see "Bugs caught").
- Full-length body thread vs top-only — parameterized; default prominent for the
  bolt look.

## Resolved dimensions (v1, dogwalker)

From the design panel + gate iteration; full set with units in the `.scad`.

- **Central screw:** d_major 10, depth 1.2, pitch 4, **single start**, tol 0.3,
  seg 64. Root 7.6; female minor bore 8.2 (mandatory). Threaded run 48 (nut 12 +
  travel 36). Guard: w_root 3.649 < lead 4 ✓. Self-locking (lead angle ≈ 8.3°).
- **Lid thread:** d_major 42.6 (= body_id 37 + 2·1.6 + 2·1.2), depth 1.2, pitch 4,
  single start, tol 0.3, seg 96. Minor bore 40.8 (mandatory). 8 mm engage = 2 turns.
- **Packing (derived):** cup_id 7.6, cup_od 10.0, hub_od 13.8, BCD 25.4 (r_cup 12.7),
  body_id 37.0, body_od 41.0. Cups clear the hub by g_in 0.8 and the bore by g_out 0.8.
- **Anti-rotation:** 4 through-slots (open at the top rim), slot_w 4.0, tab_w 3.5
  (0.5 total slop), tab_len 8, disk-rooted.
- **Base (floor-capture):** flange OD 18 with a 45° conical underside seating in
  the floor countersink (down-thrust); journal Ø12 in a Ø12.5 floor bore; the
  screw's hex torque stub (key_af 9) protrudes below and the knob (eff AF =
  max(42, body_od+4)) presses onto it (socket clear 0.25) — the knob captures the
  screw against the floor (up-stop) and carries the twist. `knob_body_gap` 0.4.
  No separate retainer.
- **Top cap (pop-up stop):** unthreaded Ø8 tip above the thread (`cap_tip_d` ≤ nut
  minor bore 8.2, so the elevator threads on over it), then a press-on `cap` Ø13 × 8,
  bore Ø8.2 (`cap_fit` 0.2). The cap flange is the elevator's up-stop. Replaces the
  old Ø10 on-screw collar, which trapped the nut. Guarded by an assert (no top
  feature > nut bore) + the `tip-clear` fitcheck.

## Gate result

`gate.sh --slice` exits 0. Body / screw / knob / elevator / coupons all 100/100
watertight; lid 92/100 (inherent female-thread crest thin-wall sampling, same
class as the reference `alcove-rod-socket` collar — a WARNING, not a fail). All
twelve fit proofs pass: central thread + lid thread (`empty` + 180° `interferes`),
the knob hex key (`empty` + 30° `interferes`), the base-disk screw clearance, the
cap press, and the `tip-clear` assembly-feasibility proof (the nut passes the screw
tip) — each `empty` + an interfering control. Plate = 6 separate objects.

## Bugs caught (and the tooling that caught them)

- **Solid membrane in the base (printcheck).** The first body had a ~0.39 mm
  solid membrane across the centre (a gap between two base cuts) that would have
  blocked the screw journal — invisible in `assembly()` (union hides it), caught
  by printcheck's thin-wall/overhang flags on the body part. Fixed by making the
  central passage continuous.
- **Screw-knob couldn't be assembled (adversarial verification fan-out, HIGH).**
  The one-piece screw-knob's Ø18 flange can't pass the Ø12.5 floor bore from
  below, and the Ø42 knob can't enter the Ø37 mouth from above — no assembly path
  exists. The gate can't see it (each part is watertight alone; `assembly()`
  unions the overlap). Fixed by splitting the knob from the screw (floor-capture,
  above).
- **Retainer had no positive retention (verification, MEDIUM).** The old snap
  retainer was a 0.1 mm-clearance ring with no snap geometry — friction only.
  Eliminated by the floor-capture rework.
- **False "relief" claim on the elevator nut (verification, MEDIUM).** The nut's
  "plain counterbore protects the near-bed turns" was untrue (bore = thread land
  dia; the cutter runout reached the bed anyway). Corrected to thread the full
  height (matching the fitcheck) and the docs now state the coupon compensates.
- **knob_af didn't track body_od (verification, MEDIUM).** A fixed 42 mm head was
  narrower than the shank for the 98/king presets. Now `eff_knob_af =
  max(42, body_od+4)` with a guard assert.
- **Containment overclaim (verification, MEDIUM) + pop-up wording + collar
  overhang (LOW).** README/PM now say the body is a vented cage (not sealed) and
  that pop_up is travel (~32 mm rise); the top-stop collar is at the thread crest
  diameter (no overhang).
- **Elevator base disk blocked the lead-screw (round-1 review, MAJOR — the
  mechanism could not be assembled).** Found while framing the new elevator-
  underside preview: the base disk was a SOLID cylinder with no screw-clearance
  hole, so the lead-screw could not pass through the elevator at all. The fit-mate
  proof tests only the bare nut ring (no disk) and `assembly()` unions the overlap,
  so neither the gate nor the earlier adversarial verification saw it — an
  interference render (elevator ∩ screw = 1887 facets, non-empty) confirmed it.
  Fixed by boring `screw_clear_d` (Ø11.6, clears the crest) through the disk while
  the nut above keeps its 9 mm of thread grip, and closed the blind spot with a new
  `base-clear` fitcheck (`empty` + a solid-disk interfering control) so the class
  can't regress. Nothing had been field-printed, which is why it survived to here —
  a standing argument for backlog #1.
- **Top-stop collar trapped the elevator nut — assembly-feasibility showstopper #2
  (round 2/3, MAJOR).** The Ø10 top-stop collar (= thread crest) exceeded the nut
  bore (Ø8.2); with the Ø18 flange below it, the thread was capped at both ends and
  the nut could never be threaded on — the mechanism could not be assembled. Same
  blind spot as the disk (gate, fitchecks and all three review rounds don't simulate
  assembly kinematics); proven by `intersection(elevator, Ø10 collar-path)` =
  non-empty. Fixed (owner-decided, Option A) by dropping the collar to an unthreaded
  Ø8 tip (≤ nut bore) and making the stop a separate press-on `cap` — the 6th part.
  Now guarded by an assert AND a `tip-clear` fitcheck (the nut passes the tip, in the
  mesh), so assembly feasibility is gated, not just reasoned about. Chosen over a
  stopless design (elevator winds off the top) and a base/bottom-load redesign.

## Review-triage log (rounds 4–5) + session-resume gotchas

Round 4–5 review triage (Vera's `pm-triage` verdicts on Jane/Drik). All copy /
orientation, no fit-dimension change; the full decision reasoning is in PM.md's
decision log — this is the engineering-log short form.

- **Cap was EXPORTED bore-down (round 4, Jane `[bench-sense]`).** The `cap()`
  module modeled the blind bore opening at the bed, so the gated part printed
  bore-down: the 0.2 mm `cap_fit` mouth landed in first-layer squish and the
  pocket ceiling bridged (the cap's lone 92/100). Flipped so `cap()` IS the print
  orientation (bore up) and `cap_use()` flips it bore-down onto the tip for
  assembly — the `knob()`/`knob_use()` split. Orientation only: same `difference()`
  boolean, identical assembled position, all fitchecks + plate unchanged; cap →
  100/100.
- **Payload diameter is tube-class by decision (round 5, Drik).** Preset `roll_d`
  (7.0–8.5) is straight-tube / hand-rolled sizing, not tapered pre-rolled-cone
  mouths (~Ø10–12.5). Cone sits loose / won't seat mouth-down; page now discloses
  it and routes cone users to `custom` + `cup_slip`-down. Cone-true **tapered
  cups** are backlog #4, gated on ①'s measured sample + an N2 re-proof. Mirrors the
  round-1 length ruling (disclose the convention, defer the geometry).
- **`tab-slot` camera froze at a zoom-IN (dist 150).** Round 4 pulled it back
  (both slot ends); Vera's round-5 triage adjudicated the reviewer conflict and
  ruled the opposite — zoom in so the tab owns the frame (slot walls for scale),
  `show_lid=false`. Frozen at `0,0,33,68,0,60,150`.
- **GOTCHA — the `body` printcheck score is non-deterministic (100 ↔ 92).** CGAL
  renders the body with slightly different tessellation each run (different STL
  md5 from identical source), and printcheck's SAMPLED thin-wall check catches the
  ~0.07 mm male lid-thread crest about half the time → the body flips between
  100/100 and 92/100 (a thin-wall WARNING) across runs of the same source. It is
  NOT a regression and NOT tunable here (the crest is the trapezoidal thread tip,
  same ignore-class as the lid's 92). Don't chase it; if CI's body render shows 92,
  that's the sampling, not a defect. (Platform-level printcheck-determinism issue,
  out of this design's scope.)
- **GOTCHA — GitHub dropped `ci.yml`/auto-review `synchronize` events (repeatedly).**
  During a GitHub Actions incident window, pushes landed CodeQL/Vercel/CodeRabbit
  but produced no `ci.yml` or auto-review run at all, leaving `ci-ok`/
  `reviewer-signoff` unposted and the PR unmergeable. Recovery is narrow: `ci.yml`
  has no `workflow_dispatch`, and **re-running an existing run keeps that run's
  original commit SHA** — so when NO `ci.yml` run exists for the affected head, a
  re-run cannot produce `ci-ok` for it. A **fresh push** (or close/reopen, which
  fires a new `pull_request` run) is the only re-trigger; `workflow_dispatch` would
  only help for a manual run if the workflow had it (it doesn't). If a legitimate
  fresh push still yields no `ci.yml` run, the dispatch failure is GitHub-side and
  needs a maintainer (close/reopen, or check the repo's Actions status).

