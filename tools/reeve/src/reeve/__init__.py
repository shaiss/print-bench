"""reeve — deterministic bench-health report for the platform PM (issue #272).

print-bench splits the PM role three ways: Remy (`/product-scout`) proposes
what designs should exist, Vera (`/pm`) enforces one design's scope, and
**Reeve owns the system** — the bench as a running whole. This tool is how
Reeve reads the ops pulse: it is deliberately **not** an LLM agent — every
finding is a recomputable fact about the committed telemetry log, the live
preview sizes and the routine confs, so the report can be trusted the way a
gate is trusted.

It is **advisory-only**: the tool itself never writes. Its primary pulse is
committed files (`signals.py`); the one other read seam is `github.py` — an
opt-in, GET-only live read that runs only when a repo is named: the run-health
gather (issue #313: the routines' workflow-run conclusions and any leaked 🚢
SHIP-LOCK claims) and the greenlight queue (issue #443: the open
`needs-decision` issues and which already carry a greenlight marker — the
input to the LLM drafter's trusted Select step, `cli.py greenlight-select`).
The package gained exactly one confined write seam in #444 — `pushthrough.py`,
the greenlight loop's push-through (below) — and a test confines every HTTP
write verb to that module alone; everything else stays GET-only by scan.

The scheduled workflow's `report` job writes exactly one thing: the
marker-matched sticky "bench health" report issue — keyless, agent-free (the
model-registry drift guard pins both). The greenlight loop (#296 stage 2,
issues #443 and #444) — an LLM drafter that posts ONE advisory greenlight
comment per parked decision, through the wrapper in
`.claude/skills/reeve-greenlight/` behind its own deny backstop, plus the
deterministic approval poll that follows — is a **separate job** built on
this tool's reads. The loop's authority half (#444) lives in this package
because it is pure decision logic plus fixed API calls, nothing
model-shaped: the NEXT scheduled run polls its own prior greenlights'
reactions (GitHub fires no webhook for them), counts only reactions from
write/maintain/admin accounts (`getCollaboratorPermissionLevel`, never
`author_association`), lets an explicit authorized `/decide` comment outrank
any reaction, and applies an approval through decide.yml's own sequence —
the fail-closed label flip first, then `autonomy-ok` where the marker
carried `arm=1`, then the PAT-backed ledger append, then the resolution
reply. Never a posted `/decide` command: decide.yml anchors on a bare
command and the comment tooling appends an attribution footer, so a
bot-posted command is silently neutralized while the run reports success —
observed live in stage 1, and the reason the push goes through the API.
Humans (or the other routines) act on what it surfaces; Reeve mutates
nothing else. The charter it serves is `PM.md` at the repo root.
"""
