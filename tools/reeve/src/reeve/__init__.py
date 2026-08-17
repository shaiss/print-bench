"""reeve — deterministic bench-health report for the platform PM (issue #272).

print-bench splits the PM role three ways: Remy (`/product-scout`) proposes
what designs should exist, Vera (`/pm`) enforces one design's scope, and
**Reeve owns the system** — the bench as a running whole. This tool is how
Reeve reads the ops pulse: it is deliberately **not** an LLM agent — every
finding is a recomputable fact about the committed telemetry log, the live
preview sizes and the routine confs, so the report can be trusted the way a
gate is trusted.

It is **advisory-only**: the tool itself never writes. Its primary pulse is
committed files (`signals.py`); the one other seam is `github.py` — an
opt-in, GET-only run-health read (issue #313: the routines' workflow-run
conclusions and any leaked 🚢 SHIP-LOCK claims) that only runs when a repo is
named. No HTTP write verb appears anywhere in the package (a test scans for
them), and the scheduled workflow's sole write is upserting one
marker-matched sticky "bench health" report issue. Humans (or the other
routines) act on what it surfaces; Reeve mutates nothing else. The charter
it serves is `PM.md` at the repo root.
"""
