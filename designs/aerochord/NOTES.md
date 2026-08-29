# aerochord — engineering notes

## Goal

A musical wind instrument that (a) prints in place as **one piece** with no
supports, (b) does not correspond to any instrument in the historical record,
and (c) is only really designable/printable with an FDM machine and a computed
internal geometry. The brief was an explicit stress test of the whole
co-design pipeline.

## What it is (and why it is new)

**aerochord is a polyphonic fipple vessel: one breath sounds a whole chord.**

A single mouthpiece feeds a shared **plenum**. The plenum splits into `N`
parallel **windways**, each ending in its own **fipple** (a flue that forms a
flat air jet and a **labium** edge that splits it). Each fipple voices an
independent **closed-pipe resonator** — a capped tube whose length is *solved*
so its pitch is one note of a chosen chord. Blow once and all `N` voices speak
together.

Why this isn't just "some pipes":

- **Pan pipes / siku** are separate open tubes, blown one at a time across the
  top, and are monophonic in normal play. aerochord's tubes are internally
  fipple-voiced (you don't aim your breath) and sound **in parallel** from one
  plenum.
- **Harmonicas / accordions / concertinas** make chords, but with free reeds,
  not edge tones, and they aren't a single hand-held printed vessel.
- **Pipe-organ ranks** voice many flue pipes in parallel, but they're an
  installation with a wind chest and separate pipes — not a palm-sized object
  printed as one supportless piece.
- **Multi-chamber ocarinas** (double/triple) exist, but the chambers are played
  **sequentially** with finger holes, or one drones — not a fixed chord struck
  in a single breath from parallel internal fipples.

The combination — parallel internal fipples + per-voice computed resonators +
fixed just-intonation chord + single-piece print-in-place — is the novel part.
The "only AI could design it" claim is narrow and honest: the internal air path
(one plenum → `N` windways → `N` fipples → `N` tuned bores) is **co-solved** and
laid out so the whole thing prints without supports, which is not something you
would lay out by hand.

## Acoustic derivation (nominal — see caveats)

Each voice is treated as a **stopped (closed-end) cylindrical pipe**: the window
is the acoustic open end, the printed cap is the closed end. For a stopped pipe

    f = c / (4 · L_eff)      ⇒      L_eff = c / (4 · f)

with `c = 343 m/s` at ~20 °C. The design solves `L_eff` per voice from its
target frequency, then places the cap base a lumped **end correction**
(`end_corr`) *below* that so the physical air column matches `L_eff`
(`tube_top(i) = labium_z + reson_len(i) − end_corr`). `end_corr` has two
constant parts:

- **`r_bore`** — the conical cap, which extends the column from the cap base to
  the cone apex (geometric, exact); and
- **`window_corr`** — the open-window end correction, the extra effective length
  the mouth adds beyond the labium (acoustic, ~0.3–0.6 × bore radius; default
  2 mm ≈ 0.4 × the 5 mm bore radius, refined by a physical print).

This matters for the chord: both parts add the *same* length to every voice, and
a constant offset distorts the interval **ratios** (leaving `window_corr` out
drifts the default triad to ~1.244 / 1.487 instead of 1.25 / 1.5). Subtracting
the whole `end_corr` keeps each column proportional to `1/f`. A global `tune`
(a multiplier) cannot fix an additive error, which is why the offset is removed
geometrically rather than tuned out.

Default chord: **just-intonation major triad**, ratios `[1, 5/4, 3/2]`, root
`root_freq = 1046.5 Hz` (C6). That gives nominal resonator lengths of ~82 / 66 /
55 mm and voices near C6 / E6 / G6.

`tune` scales every resonator length together. It exists because the simple
stopped-pipe model ignores several real effects (see caveats), so the printed
pitch will be off by a roughly constant factor that one physical calibration
print pins down.

### Honest caveats (what the gate does NOT prove)

The repo gate proves the mesh is watertight, printable, and sliceable. It says
**nothing** about sound. Specifically:

1. **Pitch is nominal.** `end_corr` models the window's open-end correction
   only *approximately* — a single lumped constant (`window_corr`), not a
   per-voice, frequency-dependent value — and the model still omits the
   flue/plenum coupling, the conical cap's departure from a flat stopped end,
   and temperature. Expect the real pitch to differ; correct it with `tune`
   after one print (and `window_corr` if the intervals, not just the overall
   pitch, are off).
2. **Voicing is not guaranteed by geometry.** Whether a fipple *speaks* at all
   depends on flue geometry, jet velocity, and cut-up in ways a mesh can't
   confirm. The dimensions here follow documented tin-whistle/recorder practice
   (flue ~1 mm, cut-up ≈ ¼ window width), but a physical test print is the only
   proof. This is why the coupon exists.
3. **Parallel voices share one plenum.** Three fipples drawing from one pressure
   reservoir can interact — one may dominate, or they may pull slightly on each
   other. The plenum is deliberately generous, but airflow balancing across
   voices is the most likely thing to need real-world tuning.

None of these block the deliverable (a novel, printable object); they're the
work a *musician* does after the *printer* succeeds, and they're called out on
the product page too.

## Geometry / print orientation

- Prints **standing on the base bar**, tubes pointing up. This is the FDM-ideal
  orientation: the resonator bores are vertical holes (self-supporting), the
  windways are vertical slots (self-supporting), and the closed tops are cones.
- **No supports.** Self-supporting throughout by construction:
  - bore roof = 45° cone (`d2 = 0`, clean apex);
  - plenum roof = a short (~9 mm) flat bridge — chosen over a gable on purpose
    (see decision log): a thin windway punching a *flat* roof is a clean
    transverse crossing, whereas grazing a 45° gable tangentially made the
    CGAL mesh non-manifold;
  - labium = an extruded wedge steeper than 45°, leaving a `labium_land` (~0.5
    mm) printable tip instead of a zero-thickness knife;
  - mouthpiece = a **bed-resting snout** (flat on the plate), so nothing
    cantilevers in free air; its bore is a teardrop (support-free horizontal
    hole) whose point is fully enclosed by a `wall` of material.
- **Tall and thin** (default ~106 mm tall on a 22 mm-deep base). PrusaSlicer
  flags generic "stability"; print with a **brim** and it's fine. Bed contact
  is a solid base bar, so adhesion is good.

## Gate status (this revision)

- `printcheck`: **92/100**, watertight, single body. One warning only: ~3%
  surface overhang (the flat plenum bridge + the labium bevels). No criticals.
  (At the production `$fn = 96` the window/round-tube tangency no longer samples
  below 0.8 mm; the labium tip is a deliberate ~0.5 mm land — sharp on purpose,
  as on any recorder — and does not read as a thin wall at this resolution.)
- Test-slice (PrusaSlicer, 0.2 mm layer / 0.4 mm nozzle): succeeds, ~3 h 50 m,
  ~25 g PLA. The coupon: ~1 h 40 m, ~11 g.
- `gate.sh --slice aerochord`: exit 0.

## Print this first

`aerochord-coupon.scad` is the **single root voice**, straight from the
production modules (`chord_ratios = [1]`), ~1 h print. Print it before
committing to the full ~4 h chord and check, in this order:

1. **Does it speak?** Blow gently. If nothing, the flue is likely closed or
   fuzzed — raise `flue_h` in 0.1 mm steps (0.8 → 1.2) and reprint. Make sure
   the windway printed open (no strings across it).
2. **Is the tone clean?** Breathy/airy → nudge `cutup` down (sharper labium
   response); shrieky/overblown → nudge `cutup` up, or blow softer.
3. **Is the pitch right?** Measure the sounding pitch, then set
   `tune = (measured_freq / target_freq)` and carry `flue_h`, `cutup`, `tune`
   into the full instrument. Pitch is inversely proportional to `tune` (longer
   tubes → lower pitch), so a print that sounds *sharp* (measured > target)
   needs `tune > 1` to lengthen the tubes.

The coupon is the hardest voice to get speaking (longest resonator, most air),
so if it works the full chord's shorter voices should follow.

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-03 | Vertical print orientation, base on bed | Bores/windways become self-supporting vertical features; only the labium and plenum roof need care |
| 2026-08-03 | Stopped-pipe resonator model | Simple, closed cap prints cleanly and gives a compact tube per pitch; `tune` absorbs the model error |
| 2026-08-03 | Flat-roofed plenum, not a gable | A thin windway grazing a 45° gable tangentially produced a non-manifold edge (CGAL, at the gable line); a flat roof the windway crosses transversely is clean. Costs a little overhang (a short bridge), which is only a warning |
| 2026-08-03 | Labium as extruded wedge + `labium_land` | Eliminated the degenerate/near-zero-thickness faces the rotated-cube bevel produced; land gives a printable ~1-nozzle tip |
| 2026-08-03 | Teardrop mouthpiece bore (`mouth_d = 6`) | Support-free horizontal hole; small enough that its teardrop point clears the top of the base bar |
| 2026-08-03 | Default root C6, major triad | A bright, clearly-audible register at a printable tube length; lower roots make taller, floppier prints (documented) |
| 2026-08-25 | Mouthpiece bore orientation, post-#398 | `teardrop_hole()`'s point faced −Z all along (issue #398, fixed in `lib/printability.scad` while this design was archived). The design was authored to the documented +Z — `mouth_z = floor_t + mouth_d/2 + 0.6`, beak `td_top = mouth_z + 0.8·mouth_d + wall` = `block_top`, apex 10.0 leaving exactly `wall` above — so the lib fix moves the built part onto its own derivation and no number here is falsified (pre-fix the point spike reached z = 0.4, nearly through the 1.6 floor). Committed previews/STL predate the fix — regenerate on revival or in a scoped design PR. Stale cross-reference left as-is with the freeze: `window_void()`'s labium-bevel comment cites the module's old `rotate([-90,0,0])` convention; the bevel's own geometry is unaffected. |
