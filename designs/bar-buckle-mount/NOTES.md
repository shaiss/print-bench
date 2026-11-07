# bar-buckle-mount — engineering log

## Goal

A **split clamp for the ISO 4210 Ø22.2 mm flat-handlebar grip section** that
presents the de-facto **action-cam two-finger quick-release buckle**
receiver, so a camera / light / remote / phone clamp that ships with the
buckle clicks on and off the bar with no tools beyond the initial clamp
install. Customer: a cyclist with a drawer of buckle-mounted accessories
and a bare bar. Brief: issue #978 (`design-brief`, `workshop-utility`).

## Given / assumed measurements

| Measurement | Value | Status |
|---|---|---|
| Handlebar clamp bore | Ø22.2 mm | **given** — ISO 4210-2 flat-handlebar grip section |
| Clamp width along bar | 20 mm | **assumed** — brief default; enough bearing without crowding grips/shifters |
| Clamp bolt | M5×0.8 + nylon-insert nut, purchased | **assumed** — brief; nothing printed threads into plastic |
| Clamp bore clearance | +0.3 mm diametral | **assumed** — repo FDM 0.2–0.4; coupon ladder |
| Buckle channel width | 28.6 mm | **assumed (community-measured)** — Jay Abbott 2014 `quickrelease_clip.scad` (`j-h-a/go-pro-mounts`), caliper-fit to a genuine male buckle |
| Buckle channel height | 4.9 mm | **assumed (community-measured)** — same source |
| Buckle engagement length | 25.6 mm | **assumed (community-measured)** — same source |
| Roof overhang / wall / roof-top | 3.0 / 3.3–3.95 / 7.3 mm | **assumed (community-measured)** — same source |
| Centre guide W×H×L | 3.5 × 2.0 × 34 mm | **assumed (community-measured)** — same source |
| Entry ease-in / hook backlash | 3.8 / 1.4 mm | **assumed (community-measured)** — same source |
| Latch window W×L×depth | 6.0 × 2.5 × 1.0 mm | **assumed** — common community latch recess (habi/smart_gopro.scad); coupon-tuned |
| Buckle fit clearance | +0.2 mm on W/H | **assumed** — FDM; coupon sweeps 0.0 / 0.2 / 0.4 |
| Retention | firm pull holds; thumb press releases | **assumed** — qualitative; latch follows measured buckle |
| Other bar Øs (25.4, 31.8) | via `bar_d` | **assumed** — brief: parameters, not separate designs |

The brief marked buckle geometry **blocking** until measured. This session
adopts the Abbott 2014 community caliper set as the sourced stand-in (the
brief's own rule: "measured-with-source or absent") and keeps every
buckle number parametric so a later field measurement of a specific buckle
is a parameter edit, not a redesign. The coupon is the proof before a
full clamp print.

## Key decisions

1. **Two mirrored halves, split on the bore axis, bore-axis-vertical.**
   Brief left hinged one-piece vs two halves open; chose two halves on
   print-orientation grounds: each half prints with the bar axis vertical
   (end face on the bed), the bore is a vertical half-cylinder (no
   supports), bolt holes are horizontal teardrops across the split, and
   the buckle channel sits on a fully-supported top pad facing up. Roof
   lips are a 3 mm shelf (under printcheck's 5 mm bridge budget). A
   tool-free lever clamp is out of scope (brief).
2. **Buckle receiver lives on the clamp-receiver half**, not a separate
   plate. One print, one interface; the plain half is the nut side. A
   blank-plate sibling (brief non-blocking Q) is deferred.
3. **`buckle_rot` parameter (0 / 1)** rotates the receiver 90° on the pad
   so the slide axis runs along the bar or across it — the brief's cheap
   non-blocking orientation option.
4. **Style `workshop-utility`** from scaffold: `style_corner_r` 4,
   `style_edge_chamfer` 0.6 on the clamp body bed edges, `style_fn` 64,
   M5 vocabulary via `printability.scad`. No text, no decoration.
5. **Hardware is purchased M5 + nyloc** — socket counterbore on the
   receiver half, hex recess on the plain half so the nyloc cannot spin.
6. **Coupon covers both tuned fits** — short bore section for the Ø22.2
   slide-vs-grip, plus three buckle-channel strips at `buckle_fit`
   0.0 / 0.2 / 0.4. Same material as the clamp (brief).

## Print settings

- **Orientation:** each half flat on its split face; receiver channel
  opens upward. Coupon same.
- **Supports:** none.
- **Material:** PETG preferred (outdoor, vibration, drop); PLA for dry
  weather trials. Coupon in the same material as the part.
- **Layer height:** 0.2 mm; walls ≥ 1.2 mm (3 perimeters @ 0.4 nozzle).
- **Infill:** 30–40 % on the clamp (vibration-loaded).

## Print this first

Print `bar-buckle-mount-coupon.scad` before the halves:

1. Slide the bore section onto a real Ø22.2 grip (or a turned pin). Too
   tight → raise `bore_clear` by 0.1; rattles → lower it.
2. Push a genuine two-finger buckle into each channel strip. Too tight →
   raise `buckle_fit`; falls out / no latch click → lower it or deepen
   `latch_depth` by 0.2.
3. Only then print `clamp-receiver` + `clamp-plain`.

## Gate contract (design-run) — verified

- [x] G1 — `render.sh bar-buckle-mount` + `--previews` complete, no CGAL errors
- [x] G2 — `gate.sh --slice bar-buckle-mount` exits 0
      - clamp-receiver 92/100 (5% overhang warning on 3 mm roof bridges; under
        bridge budget as bridgeable area)
      - clamp-plain 100/100, coupon 100/100
- [x] G3 — `readme-gate.sh bar-buckle-mount` ok
- [x] G4 — measured on export (trimesh section):
      - bore Ø 22.487 mm vs expected 22.5 (bar_d 22.2 + bore_clear 0.3) ± 0.05
      - receiver envelope 60.5 × 40.0 × 28.7 mm; channel outer span 36.7 mm
        (= buckle_w 28.6 + 2·wall_max 3.95 + buckle_fit 0.2)
- [x] G5 — preflight classify: gate_designs=bar-buckle-mount; check.sh /
      gate --slice / style-check / readme-gate green

## Use orientation note

Print Z = bar axis. The buckle pad sits on the +Z end, so once clamped the
receiver faces **along the bar** (forward/aft), not radially above it. That
is the support-free choice the brief allows; a radial-up receiver would put
the bore horizontal and need supports.
