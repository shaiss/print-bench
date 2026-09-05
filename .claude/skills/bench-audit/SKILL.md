---
name: bench-audit
description: Audit the whole automation machine — is it clean? Runs the bench's own deterministic self-checks (Reeve, the groomer, the perms/drift/parity guards), verifies every scheduled routine is firing and succeeding (not dead or livelocked), measures whether the issue autonomy loop is actually shipping or deadlocked, checks provider/billing, ghost locks, main-branch CI and the telemetry commit-back, then reports a per-dimension verdict and a HITL menu of the decisions only a human can make. Read-only and advisory — it never merges, arms, labels, or resolves. Use when asked whether the automation/machine is healthy or clean, to audit the workflow, to sweep the routines, or when invoked as /bench-audit.
---

# Bench audit — is the machine clean?

You produce one thing: a **confident health verdict on the automation as a
running whole**, plus a **HITL menu** of the decisions only the human can
make. "The machine" is everything that runs without a human in the loop —
the scheduled routines, the CI gates, the model chains, the issue autonomy
loop, the site deploy — graded as a system.

The trap this skill exists to defeat: **the machine can look alive and ship
nothing.** Every routine can fire on cadence and report success while the
backlog produces zero PRs for days, because one orphaned lock deadlocks the
selector. Green run conclusions are necessary, not sufficient — you must
measure *throughput*, not just liveness.

Two hard rules:

1. **Compose; do not re-derive.** The bench already grades itself. Reeve
   (`tools/reeve`) is the deterministic bench-health report; the groomer
   (`tools/backlog-groomer`) is the deterministic backlog-health report; a
   dozen `*-perms-check.sh` / drift / parity scripts are the config
   backstops. Your job is to **run them, read them, and reconcile them with
   live GitHub state** — not to reinvent a detector that already exists
   (N6). When your live reading and a committed report disagree, that
   contradiction is itself a finding (e.g. the groomer's `updatedAt`-age
   proxy misses an issue that is declined every hour because each decline
   bumps `updatedAt`).

2. **Read-only and advisory.** This skill **never merges, never `/decide`s,
   never applies a routing label, never flips an arming variable, never
   pushes to a routine's config.** Those are the human's calls (or a
   routine's), by design. The only write you may make — and only when the
   human asks — is filing a **follow-up issue** for a machine *defect* you
   found (a dead routine, a failing backstop, a billing wall, a stuck lock).
   Surfacing beats acting: the point is to hand the human a clean picture
   and a short, answerable menu.

For speed, fan the six dimensions out with the Workflow tool (one agent per
dimension, each returning a structured findings object), then synthesize.
Solo is fine for a quick check.

## 0. What "clean" means — the six dimensions

| # | Dimension | Clean looks like |
|---|-----------|------------------|
| 1 | Routine run-health | every scheduled routine that should have fired recently *succeeded* — none dead, silent, or livelocked (fires but every run dies) |
| 2 | Governance self-checks | every perms-backstop, drift-guard, cadence-parity and `ci-ok`-guard passes; the model registry validates |
| 3 | Backlog flow (throughput) | the loop *ships* — labeler triages, the burn opens PRs, nothing is deadlocked behind an orphan lock or a dependency chain |
| 4 | Provider / billing | the model chains can serve; a dead *fallback* tail is human-fixable degradation, a dead *primary* is an outage |
| 5 | Locks, main CI & commit-back | no ghost 🚢 SHIP-LOCK starving the selector; `main` CI is green; the regen/telemetry push-back to `main` is not rejected |
| 6 | Self-reports | Reeve's and the groomer's sticky report issues exist, are recent, and read mostly clean |

A dimension is **red** only when its core is broken (the loop ships nothing,
a security backstop fails, `main` is red, a primary provider is down).
**Yellow** is a real but non-blocking problem (a dead fallback, a stale
report, a large parked queue). **Green** is what it says.

## 1. Read the machine's own reports first

Don't recompute what the bench already computed. Find the two sticky report
issues (both upserted daily by `github-actions[bot]`, keyed by a label):

- **Reeve** — the bench-health report (label `reeve-report`; `tools/reeve`,
  `.github/reeve.conf`, ~05:53 UTC). Detectors: budget-tightening,
  gate-failing, score-regression, walltime-regression, archived-creep,
  report-drift, routine-dead, lock-leak. Read the latest body; record each
  detector's reading. Note the pulse line's gate-run record count — if it is
  **0**, four gate-side detectors are "not evaluated" (the self-measurement
  is half-dark; see dimension 5, telemetry commit-back). A 🛑 **AI andon cord**
  banner at the top of the report (or an open `andon-cord` status issue) means
  every AI-consuming job is *intentionally* bypassed (`docs/andon-cord.md`):
  read skipped routine runs as expected, not dead, and put "release the
  cord?" in the HITL menu.
- **Groomer** — the backlog-health report (label `groomer-report`;
  `tools/backlog-groomer`, ~05:41 UTC). Detectors: stale, armed-stuck,
  unsized-armed, decision-resolved-parked, unchunked-oversized,
  dup-candidates, epic-complete.

A missing or stale report is a dimension-6 finding — cross-check against
whether `reeve.yml` / `backlog-groomer.yml` actually ran (dimension 1). Both
tools are stdlib-only; you can run them locally for a fresh read, but their
run-health / lock-leak detectors need `--repo` + a token and degrade to
"not-evaluated" offline — note that, don't report a false clean.

## 2. Run the governance self-checks locally

The config/backstop integrity proofs. Work in the repo checkout (read-only;
a detached HEAD on `origin/main` is fine). **Do not** run OpenSCAD renders or
the full `check.sh` — you want the fast governance subset:

```bash
bash scripts/cadence-sync-check.sh --selftest && bash scripts/cadence-sync-check.sh
bash scripts/chunker-perms-check.sh
bash scripts/labeler-perms-check.sh
bash scripts/scout-perms-check.sh
bash scripts/oracle-perms-check.sh
bash scripts/adoption-assessor-perms-check.sh
bash scripts/wright-perms-check.sh           # both forge halves in one script
bash scripts/ci-ok-guard.sh --selftest
bash scripts/ci-classify.sh --selftest
bash scripts/reviewer-signoff.sh --selftest
bash scripts/license-boundary-check.sh --selftest
bash scripts/docs-check.sh

# the provider/model registry: it is a src-layout stdlib package with no
# console entry on PATH — run from the repo root:
PYTHONPATH=tools/model-registry/src python3 -m model_registry check
python3 -m pytest tools/model-registry/tests/ -q   # includes test_workflow_drift.py
```

A failing perms-backstop, drift-guard, cadence-parity, or `ci-ok`-guard is
**critical** — those keep an unattended, prompt-injectable routine inside its
box and a new gating job from silently letting a red PR merge. A docs-drift
failure is a warn. Read `.github/models/registry.conf` and summarize which
providers carry which secret and which chains sit on which provider (you need
this for dimension 4).

## 3. Backlog flow — measure throughput, not just liveness

Pull the open-issue label distribution and the open-PR list, then answer the
one question that matters: **is the loop actually shipping?**

- **Is the burn producing PRs?** If there are 0 open PRs and 0 recent merges
  from `claude/issue-*` despite armed (`autonomy-ok`) issues, the loop is
  deadlocked *even though backlog-burn reports success every hour.* Find the
  head of the burn's oldest-first queue and read its recent run comments — a
  string of DECLINE notices on one issue is the signature.
- **The orphan-lock deadlock (the #438 pattern).** An issue whose run pushed
  a `claude/issue-N-*` branch but **died before opening a PR** is
  self-perpetuating: its SHIP-LOCK is not §0-stale (the branch corroborates
  it), so the selector skips it forever, and no run reopens the PR. If a
  *dependent* issue is next in oldest-first order, the burn selects and
  declines it every firing and ships nothing behind it. This is invisible to
  the groomer's `armed-stuck` detector because each decline bumps
  `updatedAt`. Look for: an `autonomy-ok` issue with a pushed branch, no open
  PR, `closed_by_pull_requests` empty, an active SHIP-LOCK.
- **The groomer detectors, reconciled live:** armed-stuck (quiet armed with
  no PR), unsized-armed (`autonomy-ok` without `points-<n>`),
  decision-resolved-parked (a `/decide` verdict landed but `needs-decision`
  still set — the answer nobody un-parked), unchunked-oversized
  (`declined-too-big` gone quiet), dup-candidates, epic-complete.
- **Is the labeler keeping up?** Untriaged issues (no routing label) sitting
  for many days mean the labeler's conservatism is stranding items it won't
  confidently route.

The loop is **red** when it ships nothing; **yellow** for a pileup or stuck
subset; **green** when PRs flow.

## 4. Provider / billing

The chains are the machine's fuel. Read any open "Provider unusable" /
"Oracle provider unusable" escalation issues (the #206/#298/#347
chain-exhaustion gate) — chain + provider + cause (billing / out-of-tokens /
needs-human / transient). Then measure **current impact** from recent run
conclusions: if the primary (GLM/`zai`) is serving reviews, shipping and
labeling and only the *Anthropic fallback tail* is dead, that is a
**human-fixable degradation, not an outage** — say so plainly. An escalation
issue can be *stale* (it claimed full-chain failure at 06:04 but the GLM head
has served every run since) — verify against live runs, don't trust the
issue's timestamp. Watch for **duplicate** escalations (a single classify
pass double-filing the same `needs-decision` id seconds apart) — flag the
dedup gap and recommend closing the copy. If the 🛑 andon banner is on Reeve's
report (or an `andon-cord` issue is open), the chains are deliberately not
being exercised — no run since the pull tells you anything about provider
health, the open escalations are not being refreshed, and "release the cord?"
belongs in the HITL menu beside the funding question.

## 5. Locks, main CI, and the commit-back path

- **Ghost SHIP-LOCKs** (Reeve's `lock-leak`): an active 🚢 SHIP-LOCK on an
  issue with **no** corroborating `claude/*` branch and **no** open closing
  PR is a ghost that starves the selector. A live design-run/ship-issue
  session with a real branch is not a ghost. But the **dead-but-branched**
  lock (dimension 3's orphan) is the one `routine-lock-cleanup.sh` won't
  clear — it only withdraws locks whose run died *without* a branch. Flag it.
- **`main` CI**: is the latest push to `main` green (`ci.yml` success)? A red
  required check on `main` is systemic.
- **The commit-back path (the ruleset trap).** CI's `regen` job (on the
  default-branch push) and the telemetry-capture job both push *directly to
  `main`* — regen commits regenerated previews, telemetry appends
  `log.ndjson`. If a repository **ruleset** forbids direct pushes to `main`
  ("Changes must be made through a pull request", `GH013`), both pushes are
  rejected, which fails the required `ci-ok` on *every* regen-touching main
  push **and** leaves `telemetry/log.ndjson` empty (blinding Reeve's four
  gate-side detectors — the corroboration you saw in dimension 1/6). Check
  the latest `main` push's `regen` job for a `GH013` / "push declined due to
  repository rule violations" error. The fix is a human decision: add the
  `REGEN_TOKEN` / `GITHUB_TOKEN` actor to the ruleset's bypass list, or
  route the commit-back through a PR instead of a direct push.

## 6. Synthesize — the verdict and the menu

**A. The verdict.** A per-dimension green/yellow/red table with a one-line
reason each, then a single headline: *is the machine clean?* Lead with what
needs action. Distinguish **machine defects** (a dead routine, a failing
backstop, a stuck lock, a billing wall, a red-main ruleset — file these as
follow-up issues if asked) from **HITL decisions** (taste, scope, arming,
provider funding — these go in the menu).

**B. The HITL menu.** This is why the human ran you. Group the open
`needs-decision` items (plus any resolved-but-parked, and any escalation or
break that needs a human act) into a **short, answerable menu** with
`AskUserQuestion` — one question per coherent group, each option a concrete
disposition picked in one click. Lead with the throughput-unblockers (an
orphan-lock deadlock, a red-main ruleset) — those buy the most. Then cluster
the rest: provider/billing, parked design briefs, a parked feature epic, a
parked correctness bug, growth-queue posts awaiting approval, platform
decisions. Keep each option **decidable from its text alone** — the human
should not have to open the issue. Carry the issue number in the option so
the answer maps back to a `/decide`, a label, or an arming toggle **the human
applies**. You surface and recommend; the human decides and acts (or tells
you to file the follow-up issues for the defects, or to drive an unblocker
like opening the orphaned PR).

## Boundaries (repeat, because it matters)

- Never merge, never `/decide`, never apply a routing label, never flip a
  `*_ENABLED` variable, never edit a routine's conf, never touch a ruleset.
  This skill only reads and reports.
- The one write you may make, only on request: file a follow-up issue for a
  machine **defect**. Never file for a taste/scope decision — that goes in
  the menu.
- Infer arming from run activity; never assert a routine is on/off from the
  conf alone (the `*_ENABLED` repo variable is the other, unreadable, key).
- Attribution footer on every GitHub post you author.
