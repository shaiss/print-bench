# nuggs-shutter-valve — engineering notes

Design brief: issue #99. An inline **stop-gate** module for an 80 mm-bore NUGGS
run — a print-in-place sliding shutter that seals a run and retracts fully clear
to reopen it. First real consumer of `lib/print-in-place.scad`; consumer of the
NUGGS port standard (`lib/nuggs-coupling.scad`), redefining neither.

## Goal & given measurements

- **Bore 80 mm, wall 2.4 mm, tube OD 84.8 mm** — inherited from `nuggs_cfg()`
  defaults so the valve mates with every existing NUGGS module. Every coupling
  number is the standard's; the coupling guards fire inside `nuggs_cfg()`.
- **Slide clearances** — the battleship-tuned values `lib/print-in-place.scad`
  carries (rail 0.4 vertical / 0.5 horizontal tabs, lip engagement). Do **not**
  loosen the rail clearances (the acoustic property); tune only the door-side
  `door_fit` on the coupon.
- **Target printers** — Bambu P2S (256 mm bed) / H2C (bigger). Gated against the
  smaller P2S bed. Jane runs the same hardware.
- **Welfare non-negotiable** — when open, the shutter retracts entirely out of
  the 80 mm bore; the bore is continuous and smooth with no interior ledge.

## Key decisions (co-design session, issue #99)

1. **Orientation: vertical tube / horizontal sideways gate** (maintainer call).
   The shutter is a flat plate in the XY plane sliding in +Y; the tube prints
   vertical, standing on the bottom port's sector tips like every NUGGS module.
   This keeps the ports printing the normal way and the slide plane horizontal
   so `slide_rail`'s 45° lip undersides face the bed.
   - The alternative (horizontal tube / vertical guillotine) prints the bore
     axis-horizontal (overhang ceiling, #34) and turns the slide vertical
     (lips no longer face the bed). printcheck measured the guillotine pose as
     ~½ the overhang, but it trades the bore surface and the slide's supportless
     property — declined in favour of the NUGGS-standard print pose.

2. **Mechanism: continuous lip, not `slide_rail`'s castellated one.**
   `slide_rail`'s castellated lips are a **lift-out** door mechanism — it
   asserts `travel > tab_len` precisely so the door frees at full slide. A
   full-bore shutter must stay **captive across its whole travel**, so the valve
   runs a **continuous** lip built from the library's exposed clearance
   derivations (`pip_lip_z()`, `pip_rail_h()`, `pip_lip_profile()`) plus
   `slide_tab` for the door-side tabs and its acoustic `fit`. It consumes the
   library's clearance *math* (the point of being its first consumer), not its
   lift-out *geometry*. Recorded here because it is a deliberate divergence from
   the obvious `slide_rail()` call.

3. **Print pose: gate parked OPEN.** The printable `valve` part renders the gate
   in its open position, over the solid pedestal. There it prints as a trivial
   0.6 mm bridge onto solid material. Modelled closed, the plate would have to
   bridge the whole 80 mm open bore — an 86 mm bridge that sags. Print-in-place
   parts print in the pose that prints best; the operator slides it closed after.

4. **Supported base (the printability fix).** A full-bore gate that retracts
   sideways makes a wide flat drawer. Printed tube-up, that drawer's underside
   faces the bed with only the narrow tube beneath it — printcheck read the
   first cut at **26 % overhang, CRITICAL**. Two additions bring it to a passing
   **12 % (WARNING), 84/100 PRINTABLE WITH CAVEATS**:
   - a **45° self-supporting skirt** under the bore housing, down to the tube
     (bottoming out above the port zone so the coupling stays free to mate);
   - a **solid pedestal** under the +Y drawer, reaching the true bed plane
     (`z = -port_proj`, where the port sector tips land), so the drawer is
     carried on bed contact with vertical walls instead of cantilevering. The
     pedestal doubles as the print bed the parked gate sits over (decision 3).

5. **Ride-gap correctness.** The slide-chamber void starts at `z_deck`, not
   `z_deck + gap_z`, so the 0.6 mm band under the plate is genuinely void. An
   earlier cut left an `eps` sliver there — the mesh showed two bodies (looks
   captive) but a slicer would fuse the plate to the seat solid. The valve now
   exports as two bodies with a real 0.6 mm gap.

6. **End handle; detent deferred** (co-design choice was a light detent). The
   handle is a pull-tab off the drawer's outboard edge (not a knob through a
   roof slot, which would breach the enclosure over the bore). The detent turned
   out not to be feasible where the brief imagined it: the CLOSED position sits
   over the *open bore*, so there is no deck under the plate there to carry a
   detent bump. Travel is bounded by the housing walls themselves (the -Y wall
   is the closed stop, the +Y pocket end the open stop) and friction holds the
   gate; a detent, if wanted, would go on the rail/tab pair as a follow-up. The
   coupon keeps a deck detent (it prints over a solid base) so the feel is still
   testable.

7. **Manifold fragmentation fix (the "only Manifold tells the truth" trap).**
   The design gated clean on the local CGAL backend (watertight, 84/100) but
   CI's OpenSCAD **Manifold** backend reported the valve as **~20 bodies,
   non-watertight** — a CRITICAL. Root cause, found by exporting every leaf
   solid and re-running the boolean under **manifold3d** locally (which returned
   a single clean body — proof the *geometry* was correct and the fault was an
   OpenSCAD-Manifold tessellation artifact): a **grazing tangential cut**. An
   earlier "open the pocket roof" cut ran a flat box through `z > z_slotT,
   y > ri-1`, which sliced *tangentially into the round upper tube and the top
   port's +Y sectors*. CGAL and manifold3d absorb such a graze; OpenSCAD-Manifold
   shatters the port's ~10 sub-solids (×2 ports ≈ 20 shells) along it. The cut
   was also useless — nothing is built above the slot ceiling over the drawer,
   so the pocket is *already* open-topped — so it was simply deleted. A prior
   pass had also hardened the joins (one full-height tube the housing wraps
   instead of two segments butting it; the slot ceiling raised to the rail
   height so the housing pillar backs the whole lip, deleting the separate rail
   wall; lips rooted deep with `lip_bury` and unioned after the cuts; skirt
   overlapping by a real `weld`) and removed the fragile detent/end-stop bits
   (decision 6). Lesson for this repo's designs: never cut a flat plane so it
   lands tangent to a coupling's round shell — bound the cut clear of `ro`.

## Print orientation

Tube axis vertical, standing on the bottom port's sector tips + the pedestal
base (both reach the bed plane). Bore prints vertical (best bore surface). Gate
parked open, prints over the pedestal. `previews/print-pose.png` is the view to
scrutinise (bottom-iso): the 45° skirt and the pedestal contact.

## Print this first

Print **`nuggs-shutter-valve-coupon.scad`** before committing to the full valve
(it is a ~100 × 50 × 9 mm fixture, minutes to print, straight from the same
rail/lip/tab modules — nothing copied):

1. Print the coupon at `door_fit = 0`.
2. Try to slide the captive gate. It should slide **freely but without
   rattling** — the rattle-free fit is the acoustic property carried from the
   battleship; a loose gate is not "better".
3. If it is welded or stiff, raise `door_fit` in **+0.1** steps and reprint the
   coupon. If it rattles, lower it (down to −0.2). Do **not** touch the rail
   clearances.
4. Feel the closed-position detent click. Carry the tuned `door_fit` into the
   full valve.

## Open items / caveats (for review)

- **Big / long print.** The pedestal + the module's size make the valve a large,
  long print (test-slices ~16 h at draft settings). It is inherent to a full-bore
  sideways gate printed tube-up. The pedestal is currently a solid block (the
  slicer infills it); slimming it with an internal rib grid is the obvious
  follow-up if the print time matters.
- **Asymmetric footprint.** The retract drawer sticks out one side (module
  ~114 × 195 mm). Acceptable per the brief ("a wider module is acceptable if it
  keeps the slide supportless"); confirm it clears whatever the run sits on.
- **8 zero-area triangles** (printcheck WARNING) — harmless degenerate faces
  from the boolean stack; not yet chased down.
- **Not yet printed.** All clearances are the library defaults / the NUGGS
  standard; nothing here has touched a bed. The coupon exists to close that gap.
