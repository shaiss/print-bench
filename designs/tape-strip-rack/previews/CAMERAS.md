# Camera descriptions — tape-strip-rack

Rendered by `./scripts/render.sh tape-strip-rack --previews`. Cameras are
frozen once reviewed: a new region to show gets a NEW line in
`cameras.conf`, never a moved camera (before/after comparisons across
review rounds must align).

- **contact-sheet** — the 2×2 iso / top / front / bottom-iso of the default
  render: the assembled rack with rolls and cut tape. Cradle, racks and end
  cap are in their print orientation here (the spindle prints on end). The
  bottom-iso is the bed-contact check: flat bases, the dovetail keys and
  sockets, nothing hanging.
- **hero** — the whole assembly in 3/4 view after one pull and its cuts: the
  two tape ends parked on the fin nearest the rolls, one strip per lane on
  every later fin, the tails on the end cap's ledge.
- **cradle** — close on the roll end from the front: two rolls on the
  spindle in the leaned saddle slots, both tapes passing under the gate
  lintel and down onto the first fin, and the threading room behind the
  gate (26 mm with the 50 mm rolls drawn; 20 mm with a full 62 mm roll).
- **pad** — the roll end from behind and above: the palm pad with its four
  grip ribs and rounded back corners, the set-in back wall, and the rolls
  on the spindle between the side walls.
- **section** — orthographic cut through the middle of the first lane
  (`part="cutaway"`, cut faces grey): roll and hub, the tape's tangent off
  the roll, the lintel it passes under, the fin lands it sits on, the palm
  pad, and the drafted joint between cradle and rack in profile. The frame
  stops after the seventh fin.
- **fins** — close on three fins with no tape: the three land ribs per lane,
  the relief between them, and the guide posts running from the base past
  the land into their horns.
- **joint** — the cradle's nose from low at the side, with every part
  lifted 16 mm off its upstream neighbour (`explode=16`): the drafted
  dovetail key standing on the table, wider at the bed than at the top,
  under the rack that is lowered onto it. The socket's shape is on the
  coupon shot.
- **nested** — two rack segments stored together (`part="nested"`): one
  turned over and shifted half a pitch, its fins in the other's gaps. The
  upper segment is drawn lighter so the two read as two (the camera did not
  move).
- **coupon** — the print-this-first joint coupon: the key stub (left) and
  the socket stub (right), each as wide as a rack, loose on the bed.
- **section-pull** — orthographic cut through the joint's key, close on the
  gate, the first joint and the first two fins (`part="cutaway"`,
  `cut_at="key"`, `tape_pose="pulled"`; cut faces grey). The cut is half a
  millimetre inside the second lane, so that lane's tape shows beyond it.
  The tape is drawn just pulled and not yet pressed: off the roll, under
  the lintel, then taut toward the end cap, clear of the fin tops. The
  leaning hairline in the base is the clearance between the cradle's
  drafted key (left) and the rack's socket (right). The tape is drawn
  0.3 mm thick so that it shows; real tape is about a sixth of that, so the
  real gap over the first fin is 2.8 mm against the 2.5 mm drawn.
- **nested-side** — the nested pair in side elevation (`part="nested"`,
  orthographic): the lower segment's fins pointing up, the upper segment's
  pointing down between them, each post tip 0.2 mm short of the other
  segment's base.
