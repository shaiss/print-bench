# support-free-bracket — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 2 (designing
around supports)** and cross-cutting technique **CC1 (orientation is the master
variable)**. Tier-1 "easy" demonstrator: one part, one idea — every feature is
chosen so the part prints with *zero* support material.

## Goal

A wall/desk bracket that holds a rod (≤10 mm) in a horizontal bore, mounted with
two screws. The point of the design is not the bracket; it is that the same part
that would need supports in a naive orientation needs none here.

## The techniques it demonstrates

| Feature | Naive form (needs support) | Support-free form used |
|---|---|---|
| Rod bore (horizontal axis) | round hole → roof droops | **teardrop** (`teardrop_hole`), 45° peaked roof self-supports |
| Mount holes | — | vertical (build-axis) countersunk holes; the countersink cone opens upward and self-supports |
| Arm → plate junction | bottom fillet → curls into an overhang | **45° gusset chamfer** (a chamfer, whose sloped face self-supports) |
| Bed-contact edges | sharp → elephant-foot | small 45° `bottom_chamfer` |

## Print orientation (the whole trick)

Authored *in* the print orientation: **back plate flat on the bed (z = 0), arm
standing in +Z.** This is CC1 in miniature — choosing this orientation is what
turns the mount holes into trivial vertical holes and leaves exactly one
horizontal hole (the rod bore), which the teardrop then solves. In *use* you
rotate the part 90° so the plate is vertical against the wall.

## Key derivations / guards

- `arm_t >= bore_d + 2·1.2` — a horizontal bore only self-supports as a teardrop
  if it also *fits* the wall it passes through. The first render had `arm_t = 6 <
  bore_d = 10`: the bore was wider than the post and sheared the cap off into a
  floating bar. Now an `assert` refuses it.
- `bore_z + bore_d <= plate_t + arm_h - 3` — keeps the teardrop apex (~`bore_d`
  above centre) below the arm top so a solid cap remains. The same floating-cap
  failure mode, from the other direction; also asserted.

## Status

- Renders clean (CGAL, OpenSCAD 2021.01). Preview reviewed: teardrop roof and
  gusset visible, no severing.
- TODO before ship: `gate.sh --slice` green, product-page README, product shot.

## Print-orientation reminder for reviewers

Do **not** "improve" this by adding a fillet to the arm foot — a bottom fillet is
exactly the overhang this design exists to avoid. The chamfer is load-bearing.
