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
2. **Five printed parts:** `body`, `lid` (hex cap nut), `screw-knob` (central
   screw + hex bolt head), `elevator` (carrier nut + 4 cups + anti-rotation
   tabs), `retainer` (base ring capturing the screw flange so it spins but can't
   lift out).
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
- `screw-knob` — hex head down on the bed; central screw points up.
- `elevator` — cups up; central female nut bore threads at the top of the print.
- `retainer` — flat, either face.

## Print this first

Before committing to the full tube, print `preroll-elevator-coupon.scad` — it
carries the production central-screw male stub + the elevator's female nut ring
(and the anti-rotation tab/slot pair) so you can dial `thread_tol` (and the slot
clearance) for your printer in ±0.1 mm steps. Dial until the elevator nut runs
free on the screw with slight play and the tab slides in the slot without
rotating.

## Open decisions (non-blocking)

- Central-screw pitch/starts vs travel (fast coarse multi-start vs smooth) —
  default a coarse multi-start; confirmed by the design panel.
- Retainer method: snap ring vs threaded base cap — default snap-fit.
- Full-length body thread vs top-only — parameterized; default prominent for the
  bolt look.

_(Numbers finalized during modeling — see the parameter block in
`preroll-elevator.scad` and the design-panel synthesis.)_
