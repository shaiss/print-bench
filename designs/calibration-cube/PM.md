# calibration-cube — product charter

## The product, in one paragraph

A 20 mm test cube for checking a printer's dimensional accuracy, and the
repo's **starter design** demonstrating the parameter conventions. The
customer is **anyone dialing in a new printer or filament** who wants a fast,
honest accuracy check. The one thing it must do well: print flat-face-down
with no supports and come out dimensionally true, with the top face labeling
its own intended size so a measured print is unambiguous.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Prints supportless, flat-face-down | 0 support material | Brief; bottom chamfer releases the first layer | Never |
| N2 | Bottom edges chamfered so the first layer releases | `bottom_chamfer ≥ 0.4` mm | Repo FDM convention | A better first-layer release is proven |
| N3 | Size marker survives slicing at 0.2 mm layers | 0.4 mm engrave depth | NOTES.md | Never — a marker that slices away defeats the point |

## Out of scope

**Deferred** — good ideas, not now:

- A multi-size sweep strip (5/10/20/30 mm cubes on one plate).
- Optional X/Y/Z axis letters on the side faces.

**Never:**

- **Overhang/bridging test features.** This is a *dimensional* cube; bolting
  on a torture-test tree makes it a different design. Keep it the clean
  reference part newcomers open first.

## Product page & shots (art direction)

The page's job is to make a stranger trust the part in five seconds and
understand its one trick — **every print labels its own size**. Run
`./scripts/shot-spec.sh views` / `… palette` for the vocabularies.

**Page promise.** "A clean, honest 20 mm accuracy check that tells you what
it's supposed to measure."

**Shot list — tier 1 (real studio renders).** Ranked; the first is the hero.
Frozen once reviewed — add a row, never repurpose one.

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the printed part, at a glance | hero (low ¾) | orange / satin | — |
| size-marker | the self-labeling top face — the whole point | high ¾, elevated (`18,58,0.92`) | orange / satin | — |

**AI product stills — tier 1.5 (AI, bare product, disclosed).** The bare cube,
no scene, image-to-image seeded from a tier-1 render — angle = which render it
seeds. Shown on the page; a lifestyle scene may later seed from it.

| Still | Seeds from (tier-1 shot) | Prompt/notes |
|---|---|---|
| hero | product-hero | the bare orange cube on a seamless studio sweep, chamfered edges legible — the clean object shot |

**Lifestyle scenes — tier 2 (AI, cosmetic, disclosed).** Describe the setting.
`Seed` names the render each scene starts from (a tier-1 shot or a product still).

| Shot | Seed | Scene |
|---|---|---|
| bench-calipers | product-hero | the cube on a heated printer bed beside digital calipers, workshop light |

**Motion clips — tier 2 (AI, cosmetic, disclosed).** Only motion the print can
plausibly perform — for a static part, that means the camera moves, not the
cube; the deterministic turntable GIF stays the motion-true artifact.

| Shot | Seed | Scene/Motion |
|---|---|---|
| turntable | product-hero | slow camera orbit around the cube on a heated printer bed, light sweeping over the engraved size marker |

## v1 — definition of done

- [x] Prints supportless, dimensionally true (N1–N3).
- [x] Product page explains the part and the self-labeling marker.
- [x] Hero shot plus a shot that makes the engraved marker the subject.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Multi-size sweep strip | Most-asked variation; one plate, several sizes | design only |
| B2 | Optional X/Y/Z face letters | Helps attribute which axis is off | design only |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Keep both studio shots the same orange, or vary color? | No | Same orange — one part, read as one filament |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-08 | Add a high three-quarter `size-marker` studio shot beside the hero | The hero shows the engraved size edge-on; the marker is the product's one trick and deserves a shot that makes it the subject |
| 2026-08-08 | Add a `bench-calipers` tier-2 lifestyle scene | A cube-with-calipers scene reinforces the calibration use case; cosmetic and disclosed |
