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
opt-in, GET-only live read that runs only when a repo is named: the run-health
gather (issue #313: the routines' workflow-run conclusions and any leaked 🚢
SHIP-LOCK claims), the greenlight queue (issue #443: the open
`needs-decision` issues and which already carry a greenlight marker — the
input to the LLM drafter's trusted Select step, `cli.py greenlight-select`),
and the greenlight rounds gather (issue #445: every greenlighted thread with
its resolution state — the observer's snapshot). No HTTP write verb appears
anywhere in the package (a test scans for them).

The scheduled workflow's `report` job writes exactly one thing: the
marker-matched sticky "bench health" report issue — keyless, agent-free (the
model-registry drift guard pins both). The greenlight loop (#296 stage 2,
issue #443) — an LLM drafter that posts ONE advisory greenlight comment per
parked decision, through the wrapper in `.claude/skills/reeve-greenlight/`
behind its own deny backstop — is a **separate job** built on this tool's
reads, not a part of it: the package stays deterministic, and its writes stay
outside. The loop's **learning half** (issue #445) keeps that line: the
precedent log's pure core (`greenlights.py` — parse, derive, load) lives here,
its two verbs (`cli.py greenlight-context` / `greenlight-append`) only read
threads and write a local file, and the push of the updated log to the
`telemetry` data branch is trusted workflow bash in reeve.yml's keyless
`observe` job. Humans (or the other routines) act on what it surfaces; Reeve
mutates nothing else. The charter it serves is `PM.md` at the repo root.
"""
