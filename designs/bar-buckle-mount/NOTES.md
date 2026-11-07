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
| Clamp bore clearance | +0.3 mm diametral (= take-up) | **assumed** — repo FDM 0.2–0.4; coupon ladder |
| Buckle channel width | 28.6 mm | **assumed (community-measured)** — Jay Abbott 2014 `quickrelease_clip.scad` (`j-h-a/go-pro-mounts`), caliper-fit to a genuine male buckle |
| Buckle channel height | 4.9 mm | **assumed (community-measured)** — same source |
| Buckle engagement length | 25.6 mm | **assumed (community-measured)** — same source |
| Roof overhang / wall / roof-top | 3.0 / 3.3–3.95 / 7.3 mm | **assumed (community-measured)** — same source |
| Centre guide W×H×L | 3.5 × 2.0 × 34 mm | **assumed (community-measured)** — same source; truncated short of the latch recess so the lock tab can seat |
| Entry ease-in / hook backlash | 3.8 / 1.4 mm | **assumed (community-measured)** — same source |
| Latch window W×L×depth | 6.0 × 2.5 × 1.0 mm | **assumed** — common community latch recess (habi/smart_gopro.scad); coupon-tuned on the closed strip |
| Buckle fit clearance | +0.2 mm on W/H | **assumed** — FDM; open troughs sweep 0.0 / 0.2 / 0.4 |
| Retention | firm pull holds; thumb press releases | **assumed** — qualitative; latch follows measured buckle; closed coupon strip hears the click |
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
   blank-plate sibling (brief non-blocking Q) is deferred. The receiver
   is pedestaled to `y >= bar_d/2 + 0.5 + pad_margin` so a continuing bar
   past the clamp end never intersects the fin — gated by `ci.fitchecks`
   (`fit-close` / `fit-insert`). Fin side walls take sideways knock as a
   layer-line load across the blade height; the field ride settles whether
   that path needs thickening.
3. **`buckle_rot` parameter (0 / 1)** rotates the receiver 90° on the pad:
   `0` = slide radially (over the bar), `1` = slide across. No setting
   slides along the bar — the channel lives in the end-pad plane, normal
   to the bar axis.
4. **Style `workshop-utility`** from scaffold: `style_corner_r` 4,
   `style_edge_chamfer` 0.6 on the clamp body bed edges, `style_fn` 64,
   M5 vocabulary via `printability.scad`. No text, no decoration.
5. **Hardware is purchased M5 + nyloc** — socket counterbore on the
   receiver half (cheek-chamfered outer rim), hex recess on the plain
   half so the nyloc cannot spin. Bolt length rule: `2·half_y + nyloc
   stack` (`bolt_len` in the `.scad`; defaults land at **M5×110** —
   order-online, not a hardware-store bin).
6. **Coupon covers both tuned fits** — short bore section for the Ø22.2
   slide-vs-grip, three open troughs at `buckle_fit` 0.0 / 0.2 / 0.4 for
   W/H drag (tight → loose), plus one closed production-geometry strip
   (roof lips + latch) for the click. Same material as the clamp (brief).
7. **Clamping take-up** — each half leaves `bore_clear/2` at the split so
   the flanges can close onto the bar (effective bore → `bar_d`) instead
   of bottoming shell-to-shell on an oversized hole.

## Print settings

- **Orientation:** each half as the STL sits — end face on the bed, bore
  vertical, receiver channel opening upward. Do not auto-orient.
- **Supports:** none.
- **Material:** PLA for print #1 (bridged roof); PETG outdoors once the
  buckle seats clean under the roof. Coupon in the same material as the
  part.
- **Layer height:** 0.2 mm; walls ≥ 1.2 mm (3 perimeters @ 0.4 nozzle).
- **Infill:** 30–40 % on the clamp (vibration-loaded).
- **Seam:** Back (or scarf) — keep the ridge off the bore wall.

## Print this first

Print `bar-buckle-mount-coupon.scad` before the halves:

1. Slide the bore section onto a real Ø22.2 grip (or a turned pin). Too
   tight → raise `bore_clear` by 0.1; rattles → lower it.
2. Push a genuine two-finger buckle into each **open** trough (ordering
   tight → loose = 0.0 / 0.2 / 0.4). Too tight → raise `buckle_fit`.
   These troughs test width/height drag only — they have no latch.
3. Click the buckle into the **closed** latch strip. No latch click →
   lower `buckle_fit` or deepen `latch_depth` by 0.2.
4. Only then print `clamp-receiver` + `clamp-plain`.

## Gate contract (design-run) — verified

- [x] G1 — `render.sh bar-buckle-mount` + `--previews` complete, no CGAL errors
- [x] G2 — `gate.sh bar-buckle-mount` exits 0 on the post-relief head
      (local printcheck: clamp-receiver 100/100, clamp-plain 100/100,
      coupon 92/100 — WARN degenerate faces on the closed latch strip;
      `ci.plate` packs both halves; CI sticky after this push is the
      source of truth for --slice timings)
- [x] G3 — `readme-gate.sh bar-buckle-mount` ok
- [x] G4 — receiver envelope ~60.5 × 51.4 × 28.7 mm (pedestal extends Y past
      the bar crown); bore still `bar_d + bore_clear`
- [x] G5 — fitchecks green: `fit-close` / `fit-insert` empty; both controls
      interfere

## Use orientation note

Print Z = bar axis. The buckle pad sits on the +Z end, pedestaled clear of
the continuing bar, so once clamped the receiver faces **radially** (or
across at `buckle_rot=1`), not along the bar. Aiming is loosen–swivel–
re-snug. Camera body overflies the bar ~10–17 mm — site the clamp clear of
housings and the stem.
