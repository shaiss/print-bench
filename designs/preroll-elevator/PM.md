# preroll-elevator — product charter

The enforceable owner of what this design is, who it is for, and what is out of
scope. Engineering log is `NOTES.md`; the stranger-facing page is `README.md`.

## The product, in one paragraph

A twist-up pre-roll dispenser styled deliberately as an industrial hex bolt with
a nut on top: unscrew the cap-nut lid, twist the bolt-head base, and a central
lead-screw presents four rolls out the top; twist back to retract and cap to
close. The mechanical look is a feature, not a coincidence — the interior *is* a
nut climbing a bolt. It is for someone who wants a durable, tactile, refillable
carrier that holds and presents fragile rolls and looks like a shop object,
printed with no hardware. (It is a vented cage, not a sealed/odor-proof
container — see the decision log.)

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Rolls hold their presented height (no back-drive) | single-start, lead angle ≈ 8.3° < PLA friction | design panel | a multi-start screw is proposed for faster travel |
| N2 | Mechanism steals no roll space | 4 rolls ring a central screw | user brief | roll count or layout changes |
| N3 | No metal fasteners / bought-in parts | 6 printed parts; screw floor-captured (flange + press-on hex knob), pop-up stop a separate press-on cap | user ("design as multiple objects", parts-only assembly) | a metal ring/screw is proposed |
| N4 | Pure first-party OpenSCAD (no GPL) | assembly.conf parts-only, no `vitamin:` | licensing policy #160 | a NopSCADlib vitamin is added |
| N5 | Deliverable is the separable plate, not a fused STL | `ci.plate` = 6 objects | multi-part-fuse field test | parts are re-merged into one body |
| N6 | Every tuned fit is dialable + gated | coupon + `thread_tol`; `ci.fitchecks` empty+interferes | repo fit-gate convention | a fit is hardcoded without a coupon/fitcheck |

## Out of scope

**Deferred:** king-size default (dogwalker is the shipped default; king is a
preset); a printed detent/click at the pop-up stop; a keyed lid orientation;
per-printer profile via `printer.conf`.

**Never:** storing anything but the intended payload's geometry in the shots
(rolls are the user's, not printed); a design that only slices as one fused body.

## v1 — definition of done

- `render.sh` clean, `gate.sh --slice` exits 0 (printcheck watertight, test-slice,
  the 6-object plate check, all twelve fit proofs).
- The tuned fits proven by an `empty` fitcheck and an interfering control: central
  thread + lid thread (180° / half-lead), the knob hex key (30°) and the cap press
  (`cap-fit`); plus the clearance proofs `base-clear` (the base disk clears the
  lead-screw) and `tip-clear` (the elevator nut passes the screw tip during install).
- Assemblable by construction — now GATED, not just reviewed: `tip-clear` proves in
  the mesh that the nut can thread onto the screw (closing the assembly-feasibility
  blind spot that hid two showstoppers), the screw top-loads and is floor-captured,
  and the pop-up stop is a cap pressed on after the elevator.
- Product page complete with the CI-generated hero, open, cutaway, exploded, GIF
  and contact-sheet.
- Assembly instructions generated (`assembly.conf` → `ASSEMBLY.md` + exploded.png).
- Human approves the shape (the merge decision).

## Product page & shots (art direction)

The page promise: "a pre-roll dispenser that looks and works like a real
machined object." Tier-1 shots (geometry-true): a **closed** hero (the iconic
hex-bolt), a **presenting** shot looking into the raised carrier (cups stop ~12 mm short of the mouth; only a loaded roll clears the rim), and a **cutaway** for the
mechanism. The **elevator GIF** is the money shot — the twist-to-present motion.
No AI/lifestyle tiers for v1. Rolls appear only as ghost payload in the
deterministic previews, never in the geometry-true studio shots.

## Backlog, ranked by user value

1. Field-print and record the real fits — it also evidences every feel-claim on the
   page (self-locking hold, twist feel), **calipers one real cone of each preset
   size** (the measured-sample gate the tapered-cup work at #4 waits on), and carries
   four named look-fors: carry-state cone rattle (now **expected-confirmed** from
   Drik's round-5 chart arithmetic — Ø7.6 bore vs ~Ø5.7 cone at the cup line; the
   field print measures how bad and whether the page needs a warning line),
   knob/cap retention when the closed bolt is inverted, lid tick over the four slot
   arcs, and whether the first grab crushes or crumples the cone mouth before the
   roll releases from the cup (Drik's round-4 hunch — a hunch drives a look-for,
   never geometry, until the field print answers it).
2. **Coupon coverage for the fits with no coupon today** (Drik + Jane): a shallow
   lid-thread ring, a knob key-block (stub + socket), a cap tip+bore block, a
   bored-disk row (so the coupon's first turn matches the production part's), a
   `tab-fit-coupon` wrapper file, and grip flats on the coupon rings. All twelve
   fitchecks pass, so this is coverage, not an N6 violation — the maintenance path's
   insurance.
3. A **cap-the-raised-state lid** (Drik): a deeper lid or presentation stop that caps
   the elevator while raised, cutting the solo between-grabs cycle from ~22 turns to
   ~4. Interacts with the `pop_up` open decision. **Promoted over the detent (round 4
   triage):** the solo user pays all ~22 turns per roll (~8–16 k knob turns/year) and
   this deletes ~80% of them — the biggest cut available on the hottest path.
4. **Payload re-balance / tapered cups** (Drik round 5, promoted from #7): the preset
   diameters are tube-class (Ø7–8.5); real pre-rolled cones taper (~Ø10–12.5 mouth →
   ~Ø5 filter) and sit loose or won't seat. Only a **tapered cup** grips a cone — a
   mouth-sized straight bore touches the taper nowhere and makes the rattle worse.
   Gated on ①'s measured sample (a hunch does not drive geometry) **and** an N2
   re-proof: the cup-Ø → ring-radius → body-Ø cascade changes the 4-around-1 layout
   (dogwalker body ~41 → ~47, king → ~52), which is N2's reopen condition. The **desk
   study** (ring math on the nominal chart, N2 re-proof, page-promise impact) can
   start any time; the geometry waits on ①. The page already discloses the tube-class
   sizing (decision log).
5. A subtle detent so the stop is felt — and the **bottom** stop is the hot one
   (every session ends by winding fully down to cap); soften/click the last quarter
   turn of the descent, not just the top. Its value shrinks once #3 lands — a detent
   announcing the end of 18 turns matters less when there are ~4.
6. Knurl or flute band on the body for extra twist grip (keep the bolt read) — it
   sits on the hot path, above the solid-wall variant. (Chamfered slot ends — Drik's
   round-5 feel note — ride this wall-work, gated on the field print's thumb verdict.)
7. A **solid-wall variant** (blind slots / a closable window) for containment over
   the see-through cage — a real geometry change (top-inserted tabs need the slots
   open, so it means bottom-loading). Guard the promise: closing the walls closes
   the *sightline*, not the smell (a vented PLA cage carries scent in the plastic),
   and half-closes the usage-history stain leak. Must not slide into implying odor-
   sealing.
8. King-size validation (Ø10 screw stiffness over longer travel) — and a measured
   cone taper before any tapered-cup geometry (today's cups are straight bores).

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
- Base capture reworked after the adversarial assembly-feasibility review: the
  original one-piece screw-knob **could not be assembled** (the Ø18 flange can't
  pass the floor bore from below; the Ø42 knob can't enter the mouth from above).
  Fixed by **splitting the knob from the screw**: the shaft top-loads and is
  captured by the body **floor** between its flange (above) and the press-on hex
  knob (below) — positive mechanical retention, no separate retainer, torque via
  a hex key. Chose this over an open-bottom + snap cap because the floor (part of
  the body) carries the running thrust rather than a snapped-on ring.
- Containment: the vented cage is accepted for v1 as part of the mechanical look
  and the "see how many are left" affordance; the README/PM say plainly it is not
  sealed. A solid-wall variant is backlogged rather than forced into v1 (closing
  the windows conflicts with top-inserted tabs).
- **Payload length resolved as a double-count (round-1 review, Drik `[used-it]`).**
  Drik read the presets (70/84/98/109) as cone-only and expected real rolls ~25 mm
  longer (tip added), i.e. the default wouldn't fit and the lid wouldn't close.
  Declined: the cited industry sources (Custom Cones, The Cones Factory, STM Canna)
  define the size number as the cone's **total** length with the filter *inside* it
  (a 70 mm dogwalker is 70 mm end-to-end; a King is 109 mm total, not 135), and the
  geometry agrees — `z_rim = z_thread_start + elevator_plate_t + roll_len +
  retract_gap` makes `roll_len` the finished roll's full length, so a standard
  dogwalker seats 4 mm below the rim and the lid closes on the default. The
  surviving kernel — state the convention so long-crutch buyers pick `custom` — is
  in the README. Recorded here so a later session doesn't re-litigate it.
- **Ghost rolls in the product shot (round-1 review, Jane `[saw-it]`, act-now).**
  The Never-list line ("rolls appear only as ghost payload in the deterministic
  previews, never in the geometry-true studio shots") was right; the implementation
  missed it — the ghost loop was unconditional and STL export drops `color()`, so
  the committed `product-open.png` showed sage-painted plastic columns. Fixed with a
  `ghost_rolls` flag the product-shot manifests set false; the deterministic
  previews keep the ghosts. No Never-list amendment — the rule held, the code didn't.
- **Top stop reworked to a press-on cap — assembly-feasibility showstopper #2
  (round 2/3; owner-decided, Option A).** The Ø10 top-stop collar (= thread crest)
  was wider than the nut bore (Ø8.2); with the Ø18 capture flange below it, the
  thread was capped at both ends and the elevator nut was **trapped** — it could
  not be threaded onto the screw, so the mechanism could not be assembled. Proven by
  interference render (elevator ∩ Ø10 collar-path non-empty); no gate, fitcheck or
  review round caught it (assembly kinematics is their blind spot — the same one that
  hid the disk block). Resolved by dropping the collar to an unthreaded **Ø8 tip**
  (≤ nut bore, so the nut threads on over it) and making the pop-up stop a **separate
  press-on cap** added after the elevator — the 6th printed part. Guarded two ways so
  the class can't return: an assert (no top feature may exceed the nut bore) and a
  `tip-clear` fitcheck (nut passes tip, in the mesh). Chose the cap over a stopless
  design (the elevator could wind off the top) and over a base/bottom-load redesign
  (a larger change) — the owner picked the cap.
- **Cleaning is no longer a knob teardown (follow-on from the cap).** With the cap
  removable, a routine clean pops the cap and winds the elevator off the open top;
  pressing the knob off (screw removal) is deep-clean only. This reverses Drik's
  round-2 "every clean cycles the knob" finding — the cap fix incidentally fixed it.
- **Payload modeled as straight cylinders (round 2/3, Drik `[hunch]`).** Real cones
  taper (crutch narrower than the mouth); the cups and ghost rolls are straight.
  Disclosed on the page (close `cup_slip` if a capped roll rattles); tapered-cup
  geometry waits for a measured sample (folded under king validation). A hunch does
  not drive geometry.
- **Presenting-shot arithmetic (round 2/3).** Wound fully up, the empty cups only
  reach the mouth (~12 mm inside) — only a *loaded* roll (~44 mm proud of its cup)
  clears the rim. So a geometry-true, ghost-free "raised" studio shot is a rim, not
  proud cups. The art-direction presenting shot is reworded to "looking into the
  raised carrier," product-open's caption is made honest, and `product-raised` looks
  down into the mouth. Physics the caption must respect, not a defect.
- **Caption sync completed (round 4, Jane `[saw-it]`).** The arithmetic above was
  decided in round 2/3, but the captions still overstated it — Jane caught the
  committed `product-raised.png` showing cups ~12 mm below the rim under a caption
  that said "raised to the rim." Fixed at all five sites (README:56/58/143, the
  `shots.conf` header, and the art-direction parenthetical above): "empty cups stop
  ~12 mm short of the mouth; a loaded roll stands ~32 mm proud to grab." Jane's
  option (b) — grow `pop_up` to ~48 so empty cups reach the rim — declined for v1:
  it reopens the fixed `pop_up`=36 open decision and lengthens the screw; a caption
  is the fix, not a geometry change.
- **Cap exported bore-up (round 4, Jane `[bench-sense]`).** The cap's blind bore was
  modeled opening at the bed, so the exported/gated part printed bore-down: the
  0.2 mm `cap_fit` press mouth sat in first-layer squish and the pocket ceiling
  bridged (the cap's lone 92/100 warning). Flipped so `cap()` is the print
  orientation (bore up — plain disc on the bed, clean vertical bore, mouth 8 mm
  clear of squish) and `cap_use()` flips it bore-down onto the tip for assembly —
  the knob()/knob_use() split. Orientation only: same difference() boolean, same
  assembled position, all 12 fitchecks and the 6-object plate unchanged; the cap now
  scores 100/100 and the "bore up" print-orientation line is finally true.
- **Hero scale cue declined as intentional (round 4, Drik `[customer-sense]`).** A
  cold read of the closed-bolt hero can guess a pocket object; the real bolt is
  110 mm. Declined: the page text carries the true size prominently ("a benchtop
  object, not a pocket one"), and a scale prop would put non-product geometry into a
  geometry-true studio shot — the same discipline that keeps ghost rolls out of the
  shots (Never list). Recorded here so a later round links this rather than re-raising
  it; if a *visual* scale cue is ever wanted, it belongs in a future lifestyle tier,
  not the tier-1 set.
- **Payload DIAMETER is tube-class by decision (round 5, Drik `[customer-sense]`).**
  The round-1 length convention settled correctly; the *diameter* is the other axis
  of the same question. Drik's homework against the vendor chart: the preset `roll_d`
  (7.0/7.5/8.5/8.5) is the straight pre-rolled-tube / hand-rolled class, not the wide
  mouth of a pre-rolled cone (~Ø10.2/10.8/11.8/12.5, tapering to ~Ø5 at the filter).
  A tapered cone sits loose (grips only near the rim, ~Ø5.7 in a Ø7.6 bore) and
  rattles; mouth-down it won't seat and holds the lid open. Mirrors the length ruling:
  **decline the geometry change for v1, ship the convention statement** — the README
  now says plainly the presets are tube-class, that cones taper and sit loose, and
  routes cone users to `custom` (set `roll_d` to the mouth Ø) + `cup_slip`-down.
  Cone-true **tapered cups** are backlog #4 (promoted from #7), gated on ①'s measured
  sample and an N2 re-proof (the cup-Ø→ring→body-Ø cascade reopens the 4-around-1
  layout). Recorded so a later session doesn't re-litigate it the way round 1 almost
  re-litigated length.
