# pip-ball-socket-head — product charter

## The product, in one paragraph

A print-in-place **ball-and-socket positioner**: a stem that bolts to a desk
or shelf, and a head that comes off the bed with its ball already captive
inside a clamping socket. Tilt it, aim it, pinch the printed slit-collar
wings to hold the pose. The customer is anyone aiming a webcam, reading
light, mic or sensor at a fixed angle — and the designer who needs the
spherical (3-DOF rotary) primitive the rest of the PIP shelf does not have.
The one thing it must do well is **print un-welded** with the ball captive,
then hold a light payload after a documented break-in.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Ball printed captive; separable after slice | ≥ 2 bodies on sliced `head` STL | brief #593; `ci.fusecheck` | A support-free capture that still fuses is shown impossible |
| N2 | Designed parts clear at rest and through tilt | `fitcheck` / `fitcheck_tilt` empty | brief; perspective-coin pattern | A measured pose that must grip is named |
| N3 | No slicer supports inside the joint | 0 auto-supports in the cavity | brief; Domain 2 undercut | A printer that cannot land the ≤25° cone |
| N4 | Finger-pressure slit collar, no metal clamp screw | wings + `slit_w` | brief assumptions | FIELD-TEST shows 250 g unaided is impossible in PETG |
| N5 | ¼″-20 payload stud ~12 mm | camera standard | brief Must-fit | Thread fails printability (then payload-plate amendment) |

## Out of scope

**Deferred** — ranked backlog below.

**Never** — a two-joint articulated arm (named follow-up, not this SKU);
metal hardware in the clamp; slicer supports as the capture strategy;
claiming a measured payload hold the kitchen scale has not yet recorded;
look changes beyond `workshop-utility`.

## v1 — definition of done

- [ ] `render.sh` clean; `gate.sh --slice` exit 0 including coupon
- [ ] `ci.fitchecks` empty + both negative controls fire
- [ ] `ci.fusecheck`: head 2 bodies, coupon 8, fused control stays 1
- [ ] Every *Must fit / hold* row measured on the export (NOTES G4 table)
- [ ] Product page passes `readme-gate.sh`; as-printed contact-sheet embedded
- [ ] Human approves the shape (the merge)

## Product page & shots (art direction)

**Page promise.** One PIP print, a captive ball, pinch to lock — and the page
does not promise a payload hold the gate cannot prove.

**Mechanism honesty.** The as-printed `contact-sheet` (default pose, no `-D`)
is embedded beside the hero. Tilted-pose is labelled a preview pose; its
clearance is the `fitcheck_tilt` gate, not a pretty camera.

**Shot list — tier 1.**

| Shot | What it sells | View | Look | Pose |
|---|---|---|---|---|
| hero (shots.conf) | head seated, slightly tilted | 35,22 iso | 8a8d91 satin | `demo_tilt=12` |
| contact-sheet | the as-printed truth (4-view) | default | — | none |
| tilted-pose | articulation through the dome | cameras.conf | — | `part="head" demo_tilt=15` |
| collar-closeup | slit, rim, wings | cameras.conf | — | `part="head"` |

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | FIELD-TEST: break-in torque + 250 g hold in PETG | The payload number is a target, not a measurement | one print + kitchen scale |
| B2 | Parameterized shelf-clamp jaw (the v1-not-chosen mount) | Second user; v1 is the M4 foot | new `part` + coupon |
| B3 | Two-joint articulated arm | Brief's named follow-up | new design SKU |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Shelf clamp vs M4 foot? | No | v1 = M4 foot (D6) |
| Stud up vs camera-standard ball-under? | No | Stud up: printability (D3) wins over camera convention |
| Named payload device? | No | ≤ 250 g at 60 mm lever, field-test |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-12 | M4 foot plate in v1, not a shelf clamp | Plate prints flat, zero tuned fits; clamp hard-codes one shelf |
| 2026-09-12 | Stem-down, stud up | Capture cone/dome print supportless; stud-down bridges the ball |
| 2026-09-12 | Rim capture, dome sized for the tilted stud | Pinch-cone interferes at height or kills tilt |
| 2026-10-04 | stylelift files a fused sphere as form | Ø20 ball is a Must-fit, not a 10 mm family fillet |
