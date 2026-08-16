"""reeve — deterministic bench-health report for the platform PM (issue #272).

print-bench splits the PM role three ways: Remy (`/product-scout`) proposes
what designs should exist, Vera (`/pm`) enforces one design's scope, and
**Reeve owns the system** — the bench as a running whole. This tool is how
Reeve reads the ops pulse: it is deliberately **not** an LLM agent — every
finding is a recomputable fact about the committed telemetry log, the live
preview sizes and the routine confs, so the report can be trusted the way a
gate is trusted.

It is **advisory-only**, and reads only committed files (no GitHub GET even
to gather): the tool itself never writes, and the scheduled workflow's sole
write is upserting one marker-matched sticky "bench health" report issue.
Humans (or the other routines) act on what it surfaces; Reeve mutates
nothing else. The charter it serves is `PM.md` at the repo root.
"""
