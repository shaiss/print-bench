# The print-feedback loop

The digital gates in this repo prove a design is printable *in theory*:
watertight, no thin walls, slices clean. But the coupons exist precisely
because reality disagrees per printer — the clearance that slides on one
machine binds on another. This is the lightweight loop that carries that
reality back into the repo, so the *next* design (or the next print of this
one) starts from measured tolerances instead of a generic default.

It is deliberately small (issue #101): a config file, a NOTES.md convention,
and one GitHub Action. **Nothing else in the toolchain may grow a hard
dependency on it**, and it is **off by default** — a fresh clone behaves
exactly as it did before any of this existed.

Three pieces.

## 1. `printer.conf` — the measured profile

`printer.conf` at the repo root records a printer's measured characteristics:

```scad
printer_xy_tol   = 0.20;   // horizontal fit clearance you actually get
printer_nozzle_d = 0.40;   // nozzle diameter
printer_material = "PLA";  // default material
```

As committed it is **inert**: every line is a comment, so it overrides nothing
and a design that opts in falls back to the generic defaults. That is the off
state. Fill in the values you measured — from a coupon sweep
(`./scripts/render.sh <name> --sweep <param>=<lo>:<hi>:<step>`) or a real
print — to make opted-in designs build to your machine.

### How a design reads it

A design opts in by including the library, then reading the profile (or
calling `printer_fit()`, which grows a nominal horizontal dimension by the
measured clearance):

```scad
include <printer-conf.scad>            // generic defaults + your profile
slot_width = printer_fit(tab_width);   // = tab_width + printer_xy_tol
```

`lib/printer-conf.scad` defines the generic defaults, then does
`include <printer.conf>` so a filled-in profile overrides them —
last-assignment-wins, the same mechanism a style pack's tokens are `include`d
with. The repo-root `printer.conf` resolves through the `OPENSCADPATH` entry
the scripts export (`$PWD`), exactly like `include <styles/<name>/style.scad>`.

### Why `printer.conf` is committed, even empty

OpenSCAD has no conditional include and no file-exists test, and
`scripts/check.sh` treats `Can't open include file` as a **fatal
wrong-geometry** warning (a missing include silently drops features, so it
must fail). So `printer.conf` is committed as an inert stub rather than left
absent: the include always resolves, and inert-vs-absent is the same thing to
a design (generic defaults either way).

Because no design in the tree opts in today, `printer.conf` moves no gated
geometry — CI classifies it as soft infra. The day a *live* (non-archived)
design starts including it, whoever does that should revisit that
classification so a `printer.conf` change re-gates the design it now moves.

## 2. The FIELD-TEST convention

A design records each real print under a `## Field test log` section in its
`NOTES.md`. It is a convention plus a template (`templates/FIELD-TEST.md`),
not a tool and not a gate — nothing content-judges an entry.

```markdown
## Field test log

### 2026-08-08 — Bambu A1
- **Printed from:** v0.2
- **Part(s):** slot coupon
- **Slicer settings:** 0.20 mm layer · 0.4 nozzle · PLA · 15% infill · no supports
- **Result:** slot fit snug after tuning
- **Measured deviations:** slot 0.15 mm tight at the generic 0.20 default
- **Carry forward:** printer_xy_tol = 0.35
```

Keep the section **last** in NOTES.md — entries append to the end (newest at
the bottom). When a measured deviation is worth carrying across designs, copy
it into `printer.conf` under **Carry forward** so opted-in designs pick it up.

**Printed from** anchors a print to the design version it came from, so a
result is traceable to the exact geometry that produced it — the
missing link that made "which version did this print test?" unanswerable. It
pairs with the changelog below.

## 2a. The changelog convention — in-place version lineage

A **derivative** design gets its lineage from `derives.conf` (a new design
built on a parent). A design iterated **in place** — v1 → v2, same directory,
same name — records its lineage in a `## Changelog` section in `NOTES.md`:

```markdown
## Changelog

### v0.2 — 2026-08-20 — field-driven refinement
Driven by the first two field prints. Loop tab derived from the bore …

### v0.1 — 2026-08-18 — first shipped version
Two-sided coin + print-in-place flipper …
```

Each version is a `### <version> — <YYYY-MM-DD> — <title>` subheading
(em-dashes separate the three fields so a hyphenated title stays
unambiguous), newest first, with the prose saying **what changed and why**
and citing the field prints that drove it. A version is *cut* as a release
(`scripts/release-bundle.sh`, whose `manifest.json` carries the version); this
section is the human-read "why" beside those bytes.

Like the field-test log this is a **convention, not a gate** — but it is
*rendered*: `site/lib/timeline.mjs`'s `changelogSource` parses it, so a
rostered design's product page shows its version history on one timeline
beside the field-test prints and the git history. That is the design →
print → iterate lineage made visible: the process, not just the latest STL.

## 3. The "Log a print result" Action

`.github/workflows/log-print-result.yml` is a `workflow_dispatch` form in the
Actions tab: fill in design, printer, result, and the optional fields, and it
appends a FIELD-TEST entry to that design's NOTES.md and opens a **draft PR**
for review — so logging a print is a form, not a local ritual. The workflow
calls the testable `scripts/field-test.sh` for the formatting and file editing.

### The off switch

The whole thing is gated on a single repo variable, **`PRINT_FEEDBACK_ENABLED`**
(Settings → Secrets and variables → Actions → Variables), mirroring
`BACKLOG_BURN_ENABLED`. Unset — or anything but `true` — and the Action runs
but does nothing, emitting a `::notice::`. `printer.conf` is independently
inert, so the feature is fully off until you both fill in a profile and (for
the logging form) set the variable.

The PR is opened with `REGEN_TOKEN` (a fine-grained PAT) when that secret is
set, so its CI runs; without it the Action falls back to `GITHUB_TOKEN` and
warns that CI will not auto-trigger — the same tradeoff, and the same reason,
as the `regen` job.

## What this is *not*

- **Not a new gate.** `check.sh` gains two presence/mechanism checks
  (`scripts/printer-conf-check.sh`, which proves the default/override
  resolution reaches the exported mesh, and `field-test.sh --selftest`); no
  gate content-judges a `printer.conf` or a FIELD-TEST entry.
- **Not closed-loop auto-calibration.** A human reads a deviation and decides
  whether to carry it into `printer.conf`; nothing writes tolerances back
  automatically.
- **Not telemetry.** Field-test outcomes are a natural future input to the
  telemetry work (issue #93), but this loop has no dependency on it.
