# Printer profiles — measured fit clearances

The measured half of the print-feedback loop ([print-feedback.md](print-feedback.md)):
what fit clearance each machine actually prints, per **(machine × nozzle ×
material)**. The digital gates prove a design is printable in theory; this records
what a real print does, so the *next* design starts from a measured tolerance
instead of a generic default.

This file is **reference data** — a shareable catalog, like `styles/`. It does not
change the mechanism and adds no dependency. Your *active* profile still lives in
the repo-root `printer.conf` — which is **committed as an inert stub** (so
`include <printer.conf>` always resolves); fill it in for whatever machine+material
you're printing right now and **keep that local edit uncommitted** (it's personal).

## How it feeds `printer.conf`

`printer.conf` carries a single scalar, and `lib/printer-conf.scad` exposes it as:

```scad
function printer_fit(nominal) = nominal + printer_xy_tol;   // grow a nominal dim by the clearance
```

So a machine's profile sets `printer_xy_tol` to that material's **free-slide**
clearance, and an opted-in design writes `printer_fit(tab_width)` once and gets the
right gap per machine. Copy the matching snippet below into your local
`printer.conf` before a run.

## The fit ladder (the key idea)

A tolerance gauge gives a **ladder**, not a single number. For one
(machine × material) there are three useful clearances:

| Class | Behavior | Use |
|---|---|---|
| **Slide** (free) | parts move freely | the default; this is `printer_xy_tol` |
| **Friction** (snug) | not fused, grips | detents, knobs, press-in-by-hand, no hardware |
| **Press** (aggressive) | max grip | permanent-ish; verify no fusion per design |

Below the **fusion floor** the two walls weld into one solid — never design under
it. The mechanism only holds *one* scalar (`printer_xy_tol` = the slide value);
friction and press are **per-design choices below it** (`nominal + 0.10` instead of
`printer_fit(nominal)`), recorded here in the catalog's notes, not in the profile.

## How a row is measured

1. Print a clearance sweep of a fit coupon on the **target machine + material,
   dried**:
   ```
   ./scripts/render.sh <coupon> --sweep fit=0.05:0.45:0.05
   ```
   (one emboss-labeled copy per step, in a single print).
2. **Slide** = the tightest step that still moves freely. **Friction** = the
   tightest step that grips but isn't fused. **Fusion floor** = the first step that
   welds.
3. Log it as a `## Field test log` entry in the relevant design's NOTES.md
   (`templates/FIELD-TEST.md`), and copy the **Carry forward** number here and into
   `printer.conf`.

> A generic **clearance-calibration coupon** (a slot+tab reading `printer_fit()`,
> swept) is the natural instrument for this and isn't built yet — see
> [Not yet](#not-yet).

## Catalog

`xy_tol` in millimeters. **Always label measured vs assumed, and date every
measured row** — an assumed number that looks measured is the trap.

| Machine | Nozzle | Material | Slide | Friction | Press | Fusion floor | Status | Date |
|---|---|---|---|---|---|---|---|---|
| H2C | 0.4 | PLA | **0.15** | 0.10 | 0.05 | < 0.10 (nothing fused ≥ 0.10; 0.05 not yet confirmed unfused) | **measured** | 2026-08-12 |
| P2S | 0.4 | PLA | ~0.10 | ~0.05 | — | — | **assumed** (H2C − 0.05; direction unconfirmed) | — |

**Notes**
- **H2C / PLA** ran *loose* across the whole gauge from 0.45 down to 0.15, with 0.10
  snug-but-free and nothing fused even at 0.10 — so this machine tolerates unusually
  tight print-in-place gaps without welding (useful for tight captive joints and
  quiet, non-rattling clearances). Treat 0.10 as a friction knob and 0.05 as an
  aggressive grip to confirm per design.
- **P2S** is an **untested assumption** (`H2C − 0.05`). Even the *direction* (does
  the P2S run tighter or looser?) needs one confirming gauge print before relying on
  it — taken literally the ~0.10 slide is aggressively tight for an unvalidated
  machine. Do not ship a P2S design on this row without gauging it.
- **Filament varies the fit.** Each new material (and sometimes each brand) gets its
  own gauge; the `Material` + `Date` columns keep "measured" honest. This is a
  *good-enough starting profile refined on contact*, not a spec.

## Ready-to-copy `printer.conf` snippets

Paste one into the repo-root `printer.conf` and **keep your edit uncommitted** (the file itself is committed inert):

```scad
// H2C · PLA · 0.4 nozzle — measured free-slide (gauge 2026-08-12: loose 0.45→0.15,
// 0.10 snug, nothing fused ≥0.10). Friction ≈ 0.10, aggressive ≈ 0.05 per design.
printer_xy_tol   = 0.15;
printer_nozzle_d = 0.40;
printer_material = "PLA";
```

```scad
// P2S · PLA · 0.4 nozzle — ASSUMED (H2C − 0.05), UNVERIFIED. Gauge before trusting.
printer_xy_tol   = 0.10;
printer_nozzle_d = 0.40;
printer_material = "PLA";
```

## Not yet

- **Clearance-calibration coupon** — a small parametric slot+tab (or pin+bore) that
  reads `printer_fit()` and sweeps it, so a single print yields the number that
  drops straight into `printer_xy_tol`. The reusable measurement instrument for this
  whole catalog; a natural small first build.
- **`profiles/*.conf` swappable files** — if machine/material swapping becomes
  frequent, promote the embedded snippets above into drop-in files you
  `cp … printer.conf`. Held off for now to avoid a new top-level directory for two
  rows.
- **Material-keyed `printer_fit(nominal, material)`** — so an opted-in design
  auto-selects the clearance for its material rather than swapping `printer.conf`.
  Real feature work on `lib/printer-conf.scad` (issue #101 follow-on); worth it only
  once a live design opts in.
