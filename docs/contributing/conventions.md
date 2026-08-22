# Conventions

The standing rules platform code is held to — each one enforced by a check, each check born from a real failure. Knowing the rule is optional; the checks make sure of that. Knowing *why* saves you a red CI round.

## Derived artifacts are CI's job

Never commit generated output. The `regen` job regenerates a design's derived artifacts (previews, GIFs, product shots, exploded views, the gallery, drafted product pages) and commits them in the same run that gates the source, which is what keeps presence-only gates honest (a committed image cannot be older than the source beside it). Two derived files follow different pipelines but the same rule: `telemetry/` is appended by the `render-gate` job on default-branch runs (never hand-edit it), and release bundles are built by `release.yml` and published as GitHub Release assets, never committed at all. Run the generators locally only to *look* at the output. The single exception is a PR from a fork, where CI cannot push — see [Pull requests](pull-requests.md).

## Docs are drift-checked

[`scripts/docs-check.sh`](../../scripts/docs-check.sh) mechanically asserts the docs match the tree — its numbered checks are the full list; these are the ones an ordinary change hits most:

- A new file in `scripts/` must be named in **CLAUDE.md's single "`scripts/`" layout bullet** (a mention anywhere else in CLAUDE.md does not count — a script once landed named only in the Commands block while the layout enumeration silently went stale) *and* in README.md.
- A new first-party `lib/<name>.scad` must be named in CLAUDE.md, backticked in README.md's `## Layout` section, and must ship a `lib/<name>-demo.scad`.
- A new skill under `.claude/skills/` must be mentioned in CLAUDE.md as `/<name>` — and every `/<name>` CLAUDE.md mentions must exist.
- A new top-level directory (and each `tools/<name>/`) must be mentioned in both CLAUDE.md and README.md.
- Every style pack must be complete and listed in `styles/README.md`.

The scope discipline stated in that script's header binds new checks too: every docs check is a **mechanical fact** (a file exists, a name is mentioned), never a prose judgment. The corollary for doc writers: link the one authoritative enumeration instead of restating it — a second copy is a drift surface no check covers.

## Every check proves it can fail

A check that cannot fail checks nothing, so the house pattern is a selftest or negative control beside every gate:

- Gate scripts ship a `--selftest` that plants each failure and requires the gate to catch it. Note the wiring gotcha: `check.sh` invokes each selftest **explicitly by name**, so a new script's selftest does nothing until `check.sh` is edited to call it. (Library demos and the `*-guards.conf`/`*-mates.conf` cases, by contrast, are discovered by glob.)
- A library whose modules carry asserts ships `lib/<name>-guards.conf` — cases the library must *refuse* ([`scripts/guard-check.sh`](../../scripts/guard-check.sh)). A library with a tuned fit ships `lib/<name>-mates.conf` — fits that must *assemble*, plus at least one deliberately-interfering case proving the check can fail ([`scripts/mate-check.sh`](../../scripts/mate-check.sh)).
- Tool test suites carry a negative control per guard, and workflow-consuming tools carry drift guards that pin the tool and its consumer workflows together (the model registry's `test_workflow_drift.py` is the model).

## Never trust an OpenSCAD exit code

OpenSCAD 2021.01 exits 0 on a failed assert under echo and CSG export, treats an unresolvable `use`/`include` as a warning-then-success, and hands you a watertight, 100/100-scoring STL with the features missing. Every check here therefore greps message text or measures the exported mesh — and a new check built on OpenSCAD's exit status is broken by construction. Related trap: byte-hashing an exported STL *seems* to work on small models and silently stops working on real ones (facet order is not stable between renders); use the canonicalising `mesh-hash` from [`tools/lineage`](../../tools/lineage/README.md) and reuse `lineage.sh`'s sourced helpers for the empty-vs-broken distinction.

## Shell and workflow floors

- **Bash 3.2** (stock macOS) is the floor for locally-run scripts: no associative arrays, and guard empty-array `"${arr[@]}"` expansions under `set -u`.
- The **committed** executable bit is what counts: a `scripts/` file with a shebang must be committed mode 100755 (`git update-index --chmod=+x`, not a local `chmod`), and a sourced helper without a shebang stays 100644.
- A hardcoded `openscad` binary works everywhere except the one CI job that installs only the nightly — which is exactly where it fails — so route every invocation through `"$OPENSCAD_BIN"` (docs-check enforces it).
- The default Actions shell has no `pipefail`: any `cmd | tee log` in a workflow step masks the failure unless the step sets `set -o pipefail` first.
- Apt packages cached via `cache-apt-pkgs-action` must be verified postinst-free (`dpkg -I`) and added to docs-check's allowlist in the same PR — the cache restore skips postinst, so alternatives-managed binaries come back dangling one run *later*.
- `gate.sh`'s output line shapes (`time  <name>: gated in <N>s`, the derivative-check lines) are machine-parsed by `gate-summary.py` and `telemetry.sh` — changing an output format silently breaks the PR comment or telemetry capture.

## The license boundary

The first-party tree is CC-BY-SA-4.0; vendored code keeps its own terms — `lib/BOSL2/` (BSD-2-Clause) and `lib/NopSCADlib/` (GPL-3.0) are never edited. The standing decision ([docs/licensing.md](../licensing.md), enforced by [`scripts/license-boundary-check.sh`](../../scripts/license-boundary-check.sh)): **copyleft never reaches shared first-party core** — no shared `lib/*.scad`, `scripts/` or `site/` code may combine with or bundle a copyleft library — while an individual *design* may opt in and must then disclose GPL-3.0 on its product page. Core may freely *invoke* GPL tools it doesn't ship (OpenSCAD, PrusaSlicer, Blender). Don't "fix" the check's deliberate scope (designs are unscanned on purpose), and vendoring any new copyleft library means extending `COPYLEFT_ROOTS`, `LICENSE` and the policy doc in one PR.

## Source of truth lives in git

Policy that automation reads is a committed file — the smart-CI registry, each routine's `.github/<routine>.conf`, the model registry — never a GitHub setting alone. GitHub supplies interaction and authorization (comment commands checked against real repository permission); git supplies the reproducible decision. Live arming switches (the `*_ENABLED` repo variables) are the deliberate exception: kept *out* of git so a clone or fork can never inherit an armed agent. When you add configuration, follow that split rather than inventing a third place for state.

## Review history is preserved

`audits/` holds before/after render comparisons from review rounds, and designs may carry closed work-phase docs beside `NOTES.md`. Treat both as history: keep them current or mark them closed, never delete them as scratch. The same instinct applies platform-wide — a decision worth making is worth recording where the next contributor will look (a script header, a doc, PM.md's decision log).
