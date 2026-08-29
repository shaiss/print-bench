# Growth dry run — Twitter/X, accelerated timeline

Simulated window: **7 days** from **2026-08-30T00:00:00Z**, cadence `19 13 * * *`, at most **1** post(s) per firing.
Nothing here was posted anywhere — this is the committed preview of what the growth agent would have published, in order, had it been armed live over this window. Weighted lengths use the same rule the posting tool enforces (URLs = 23, wide code points = 2, cap 280).

Provenance: queue items #452–#459 filed 2026-08-29 (the PM-voiced seed set); copy composed attended by Lark's skill (one composer per item, every fact re-verified against the committed tree) and adversarially audited (one reviewer per draft; #459's hook was scoped down from "every safety check" to "every guard" — the repo itself documents presence-only gates). Schedule and drain order are the committed policy in .github/growth-twitter.conf, expanded by tools/growth.

## 1. 2026-08-30T13:19:00Z — queue item #452

_Growth post: introduce the bench — a human + AI workshop that gate-proves every design_

> Every design in this repo is co-designed with an AI, and none of it merges until CI proves it printable: printcheck watertightness plus a real PrusaSlicer test-slice. Parametric OpenSCAD in, a sliced-clean STL and an honest product page out. Nothing ships on vibes.

(265/280 weighted)

**2/** (thread)

> The AI team is named and registered in the repo, each agent bound to a committed charter. No agent can merge: the human lead stays primary and owns every merge. All of it is public: https://github.com/shaiss/print-bench #BuildInPublic

(220/280 weighted)

## 2. 2026-08-31T13:19:00Z — queue item #453

_Growth post: the acoustic anti-wallhack clearance — sound as game state_

> 0.5 mm horizontal, 0.4 mm vertical: the slide clearances on a printable Battleship board (played with real sushi) are acoustically tuned. A shutter that rattles differently over a loaded cell than an empty one is a wallhack — so the library forbids loosening them.

(264/280 weighted)

**2/** (thread)

> The lib header calls it THE ACOUSTIC PROPERTY: reviewed to slide freely AND not rattle. If a door sticks, tune the door-side fit on a coupon in ±0.1 steps — never the rail clearances upward, or the audible tell comes back. #PrintInPlace https://github.com/shaiss/print-bench/blob/main/lib/print-in-place.scad

(260/280 weighted)

## 3. 2026-09-01T13:19:00Z — queue item #454

_Growth post: threads that print supportless — the measured 45° flank story_

> Trapezoidal threads whose mating flanks sit at exactly 45°, so bolt and nut sides both print supportless in a vertical bore. Not eyeballed — measured on the exported mesh: surface normals at |nz| = 0.707, i.e. cos(45°), on a bare helix and a real part's neck.

(259/280 weighted)

**2/** (thread)

> Male and female profiles come from ONE generator — the female cutter is the male thread grown by the clearance — so they can't drift apart. The 45° fix cut the donor capsule's beyond-45° overhang from 4% of its surface to 1%.
> 
> https://github.com/shaiss/print-bench/blob/main/lib/threads-fdm.scad #OpenSCAD

(260/280 weighted)

## 4. 2026-09-02T13:19:00Z — queue item #455

_Growth post: the orrery that cannot be assembled — only printed_

> This print's assembled state cannot be assembled. Three orbit rings spin free around a cage of six helically twisted fins, printed in a second material on the same plate — and each ring's hole is smaller than the cage it circles. It can only exist by being printed.

(265/280 weighted)

**2/** (thread)

> It's also a functional hamster-tunnel module: standard genderless 80 mm-bore NUGGS port at both ends, and everything the animal touches is the plain bore — the sculpture is entirely external. #3DPrinting https://github.com/shaiss/print-bench/tree/main/designs/nuggs-orrery

(227/280 weighted)

## 5. 2026-09-03T13:19:00Z — queue item #456

_Growth post: the print that came out welded — and the CI gate it became_

> Our two-part curtain-rod socket printed welded shut in the field. Not a tolerance problem — a packaging one: the two parts went out as a single STL, and STL carries no object separation. The slicer imported one fused body and printed exactly that.

(247/280 weighted)

**2/** (thread)

> The fix is now a CI gate: plate.sh merges the gated per-part STLs into one multi-object 3MF and asserts object count == declared part count. Its selftest proves the gate can fail: two part STLs -> 2 objects, a fused body -> 1.
> https://github.com/shaiss/print-bench/tree/main/designs/alcove-rod-socket

(250/280 weighted)

## 6. 2026-09-04T13:19:00Z — queue item #457

_Growth post: the agent forge — an AI that proposes new AI agents, judged by another AI, merged by a human_

> Our 3D-print bench now grows its own tooling. Wright, a toolwright agent, reads the bench's pulse and files agent-brief proposals 4x/day. Reeve, the platform PM agent, rules on each. An approved brief gets built into a draft PR — and a human still merges everything.

(266/280 weighted)

**2/** (thread)

> Separation of powers, enforced in permissions: Wright's deny backstop denies Reeve's sign-off server; Reeve's denies Wright's filing server. The proposer can't judge its own briefs; the judge can't file. Same gated pipeline the designs use. https://github.com/shaiss/print-bench/blob/main/docs/agent-forge.md

(264/280 weighted)

## 7. 2026-09-05T13:19:00Z — queue item #458

_Growth post: 0.1754 mm³ of interference the test harness could never have seen_

> 0.1754 mm³ of interference in our quarter-turn coupling's fit at $fn=48. 0.0717 at 56. 0.0260 at 64. Free only from 96 segments up — and our mate-check harness renders at exactly 96, so it could never have seen the bug it existed to catch.

(239/280 weighted)

**2/** (thread)

> The fix: the library pins its own $fa/$fs inside every module body and ignores the caller's quality preset. The fit is split at one radius, so the clearance there moves with tessellation. Tessellation is a tolerance problem.
> 
> https://github.com/shaiss/print-bench/blob/main/lib/nuggs-coupling.scad
> #OpenSCAD

(259/280 weighted)

## Still queued after the window

- #459 Growth post: every safety check must prove it can fail

