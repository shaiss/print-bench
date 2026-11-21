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
- **cradle** — close on the roll end: two rolls on the spindle in the leaned
  saddle slots, both tapes passing under the gate lintel and down onto the
  first fin.
- **section** — orthographic cut through the middle of the first lane
  (`part="cutaway"`): roll and hub, the tape's tangent off the roll, the
  lintel it passes under, the fin lands it sits on, and the drafted joint
  between cradle and rack in profile.
- **fins** — close on three fins with no tape: the three land ribs per lane,
  the relief between them, and the guide posts running from the base past
  the land into their horns.
- **joint** — the roll end with every part lifted 16 mm off its upstream
  neighbour (`explode=16`): the cradle's dovetail key and the rack's socket
  about to be lowered onto it.
- **coupon** — the print-this-first joint coupon: the key stub (left) and
  the socket stub (right), loose on the bed.
