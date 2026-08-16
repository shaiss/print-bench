# reeve

The deterministic **bench-health report** behind Reeve, print-bench's platform
PM (issue #272). Reeve owns the *system* — the gates, the autonomy loop, the
site, the telemetry — as a running whole, and this tool is how it reads the ops
pulse. It is the platform-ops sibling of `tools/backlog-groomer`: same
advisory-only, no-LLM, one-sticky-issue shape, pointed at a different question.

## The PM split

print-bench splits the PM role three ways (issue #229 established the first two):

- **Remy** (`/product-scout`) — *generative*: proposes what designs should exist.
- **Vera** (`/pm <design>`) — *enforcement*: holds one design's scope.
- **Reeve** (`/pm print-bench`) — *operational*: owns the bench's own health.

Reeve is advisory. The human lead stays primary and owns every merge; Reeve
never gates one. Its charter is the repo-root `PM.md`.

## What it reads (committed files only)

No GitHub GET even to gather — the pulse is entirely file-read, so the tool
holds no token and makes no network read:

- **`telemetry/log.ndjson`** (issue #93) — per-run gate history: printcheck
  scores, per-design wall time, preview-budget headroom, archived skips,
  derivative outcomes. Starts empty; "no history yet" is a valid state.
- **Live committed previews** — `designs/*/previews/*.{gif,png}` sizes against
  the `scripts/preview-budget.sh` caps. The one pulse that works with an empty
  log.
- **`telemetry/REPORT.md`** — to detect roll-up drift (log has runs, report
  didn't regenerate).

## The detectors

Six pure functions of one snapshot, deterministic order, byte-stable report:

| Detector | Fires when |
|---|---|
| `budget-tightening` | a committed preview's size headroom is under `low_headroom_pct` (or over budget) |
| `gate-failing` | the latest run has pre-fails, a part with no score / criticals / a failed slice, or a false derivative override |
| `score-regression` | a part is below `score_floor`, or down ≥ `score_drop` vs the prior full-catalog run |
| `walltime-regression` | a design's gate wall time rose ≥ `walltime_ratio`× (and past `walltime_min_seconds`) |
| `archived-creep` | a design newly dropped out of gating vs the prior full-catalog run |
| `report-drift` | `log.ndjson` has runs but `REPORT.md` is still the empty placeholder |

Comparisons only use full-catalog (`designs=ALL`) runs — a scoped run gates
fewer parts. A detector whose input is absent is reported **not evaluated** with
a reason, never silently empty (the groomer's honesty rule).

## Advisory-only, checkable

- The tool never writes: a test asserts no HTTP write verb (`POST`/`PATCH`/
  `PUT`/`DELETE`) appears anywhere in the package, and the pure core imports
  nothing network-capable.
- The scheduled workflow's single write is upserting one marker-matched sticky
  `reeve-report` issue, keyed belt-and-braces by its label and the body's first
  line. No provider secret is held, so it needs no deny-backstop.
- The LLM "hands" (auto-filing/labeling follow-up issues) are a staged
  follow-up (charter backlog B1) carrying the labeler's wrapper + deny-backstop,
  because acting on the pulse from model output over untrusted text crosses into
  agentic-writer territory.

## Arming (two keys, shipped disarmed)

The routine runs only when **both** agree: `.github/reeve.conf`'s `enabled: true`
(committed intent) **and** the `REEVE_ENABLED` repo variable (the live human-only
switch). Shipped with the variable unset, so a clone/fork can't silently arm it.
The 2×2 decision is code (`reeve armed`), unit-tested.

## CLI

```bash
reeve report --input snapshot.json          # snapshot JSON -> markdown report
reeve gather --root .                        # committed files -> snapshot JSON
reeve run --root . --conf .github/reeve.conf # gather then report (the workflow)
reeve config --get enabled                   # read the committed policy
reeve armed --variable "$REEVE_ENABLED" --conf-enabled "$enabled"
```

## Tests

Stdlib-only; the `[test]` extra is just pytest.

```bash
pip install -e 'tools/reeve[test]'
python -m pytest tools/reeve/tests -q
```

The golden-file test (`tests/fixtures/report.golden.md`) pins the report bytes;
each detector has a positive case and a negative control. CI runs the suite when
`tools/reeve/**` or `.github/reeve.conf` changes (`scripts/ci-classify.sh`).
