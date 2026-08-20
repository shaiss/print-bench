# print-bench vs. Foreman/eve — baseline audit & punch list

**Audit date: 2026-08-20.** A competitive baseline of print-bench's
AI-automation and CI pipeline against Vercel's **Foreman** — the software
factory implemented by
[`vercel-labs/eve-software-factory-template`](https://github.com/vercel-labs/eve-software-factory-template)
(site: [ask-foreman.dev](https://ask-foreman.dev/)) on **eve**, Vercel's
open-source framework for durable AI agents. The two names the audit started
from collapse to one strong reference. Both are mutable upstreams: the
comparison reflects their public docs as of the audit date, not a pinned
revision.

This file is the durable record of that audit and the punch list it produced.
It is preserved review history (see `audits/`), not a live spec.

## The one-line finding

On the axis the 2025–26 market has actually shifted to — **verification
harnesses and governance, not model quality** — print-bench holds its own and
in specific places (falsifiable gates, deterministic gate selection,
provenance) is *ahead of shipping commercial products*. It is **not** a peer as
a *system*, for three reasons that have nothing to do with cleverness: it skips
the expensive layer (per-task isolation), its orchestration is bespoke where
theirs is a durable runtime, and its governance apparatus is years ahead of its
demonstrated need (empty telemetry log, empty decision ledger, one real
field-test entry).

## The architectures converge

Every serious pipeline in this cohort — Foreman included — is the same six
layers. print-bench has a hand-rolled analog of each:

| Layer | Foreman / cohort | print-bench equivalent |
|---|---|---|
| 1 · Isolated execution | Per-task cloud VM / Vercel Sandbox | Runs inside the GitHub Actions runner (weaker) |
| 2 · Task intake | Assign issue / @mention / Linear | `label-issues` → `autonomy-ok`; backlog-burn selector |
| 3 · Agent loop | plan→edit→test→iterate | `/ship-issue`, `/design-run` (delegated to claude-code-action) |
| 4 · Self-verification | Repo's own tests/build/lint | gate.sh + printcheck + PrusaSlicer test-slice + geometry-diff |
| 5 · Human gate | Draft-PR-only, never merges | Draft PRs + SHIP-LOCK + `needs-decision` gate |
| 6 · Orchestration/fleet | eve durable execution + OTel | Scheduled routines + model-registry + telemetry log |

print-bench built by convention what Vercel built as a framework.

## Scorecard (weighted where print-bench actually competes)

The dimensions below are the axes worth scoring, not a strict 1:1 with the six
layers above — several (provider abstraction, security backstops, self-measurement,
proportionality) are cross-cutting concerns rather than layers.

| Dimension | print-bench | Foreman/eve |
|---|:---:|:---:|
| Verification gate rigor (layer 4) | **A** | B+ |
| Gate-selection determinism | **A** | B |
| Provenance / anti-staleness | **A** | B |
| Human-in-the-loop design (layer 5) | A– | **A** |
| Execution isolation (layer 1) | **C** | A |
| Durable orchestration (layer 6) | B– | **A** |
| Provider abstraction (cross-cutting) | C+ | B+ |
| Security backstops (cross-cutting) | B | **A** |
| Self-measurement in practice (cross-cutting) | **F** | B |
| Proportionality / scope control (cross-cutting) | **D** | A |

## Where print-bench is genuinely ahead (keep these)

1. **Falsifiable gates / negative controls** — `mate-check.sh` fails if a
   declared interference *stops* interfering; `guard-check.sh` fails if a guard
   stops refusing; the perms-checks ship `--selftest` proving they can go red.
   "A check that can't fail is worthless" is mechanically enforced. Most
   vendors ship no proof their gate can fail.
2. **Deterministic gate selection, mirrored locally** — `ci-classify.sh` runs
   verbatim in CI and `/preflight --local`, with a selftest, so "would CI
   pass?" provably can't drift.
3. **Provenance that makes staleness structurally impossible** (issue #69).
4. **A durable HITL decision gate** (`needs-decision`) distinct from a stale lock.
5. **The derivative gate** — proves an OpenSCAD override actually changed the mesh.
6. **GitHub Actions mechanics depth** above a typical pro team.

## Where Foreman/eve is ahead (the targets)

1. Per-task sandbox isolation (their moat — correctly out of scope for us).
2. Cross-vendor, reasoning-blind review.
3. Durable execution as a substrate.
4. Bounded self-healing CI scoped to its own branches.
5. Factory Brain — cross-run memory.

---

# Scored punch list

**Scoring key.** Effort: **S** = hours (≤½ day) · **M** = ~1 day · **L** =
multi-day. Impact: 1–5, where **5 = flips a scorecard cell from ≤Foreman to
>Foreman, or fixes a real defect.** Priority: **P0** = small effort + high
impact or a real bug → do first.

## P0 — cheap, and each fixes something real

| # | Item | Effort | Impact | Status |
|---|------|:---:|:---:|--------|
| 1 | **Wire the model registry into the ship routines + walk a fallback chain.** `backlog-burn.yml` / `design-run.yml` hardcoded `claude-opus-4-8` (in no chain, no fallback) and bypassed the registry. | S | 5 | **IMPLEMENTED — PENDING MERGE** in issue #297 / PR #306 (migrates all four routines: design-run, backlog-burn, chunker, labeler). #306 still needs a rebase + merge; mark DONE once it lands. |
| 2 | **Guard `ci-ok`'s needs-list.** The file admits: "a job missing from needs can fail without blocking merge, and nothing detects the omission." A check parses `ci.yml`, lists every job + `ci-ok.needs`, fails if any job is missing (bar a justified exclusion set). | S | 4 | **THIS PR** — `scripts/ci-ok-guard.sh` |
| 3 | **Fire `model-smoke` on registry change.** It was `workflow_dispatch`-only, so a registry edit shipped an unservable id until a human remembered. Runs automatically on same-repo PRs touching `.github/models/**` or `tools/model-registry/**` (and the workflow itself), smoking every chain; `workflow_dispatch` is preserved (a named chain, or blank = all). | S | 3 | **THIS PR** — `model-smoke.yml` |
| 4 | **Turn on secret + dependency scanning.** No SAST/dep-scan existed. gitleaks over the PR's new commits (advisory / non-blocking — not a required `ci-ok` context until promoted in branch protection) + Dependabot for Actions and pip. | S | 3 | **THIS PR** — `security-scan.yml`, `dependabot.yml` |

## P1 — the leapfrogs and the credibility fixes

| # | Item | Effort | Impact |
|---|------|:---:|:---:|
| 5 | **Cross-vendor, reasoning-blind reviewer** — Foreman's core bet; combined with our falsifiable gates it *exceeds* them. | M | 5 |
| 6 | **Shrink `auto-review`'s `bypassPermissions` blast radius** — give the personas the deny-backstop the scheduled routines already have. | M | 4 |
| 7 | **Populate telemetry** — the loop has zero data because the trigger rarely matches (preview-only merges → `gate_designs=''`). Broaden capture or record autonomy-routine outcomes. | M | 5 |
| 8 | **Retire self-documented accidental complexity** — require only `ci-ok` in branch protection, delete the "run-but-gate-nothing" mode, fix docs-only-PR mergeability. | M | 4 |
| 9 | **Enforce strict shellcheck on the security-critical shell** — the gating shellcheck gate is `state=proposed` and never runs. | S–M | 3 |

## P2 — compounding advantages

| # | Item | Effort | Impact |
|---|------|:---:|:---:|
| 10 | **Factory-brain: committed cross-run memory** the ship/design routines read at start. | M | 3 |
| 11 | **Formalize bounded, branch-scoped self-healing autofix** (2 attempts, `claude/*` only). | M–L | 3 |
| 12 | **DRY the mirrored SHIP-LOCK / closing-keyword policy** into one importable module + import guard. | M | 2 |

## P3 — explicitly do NOT do

- **Per-task VM isolation** — the cloud vendors' moat; wrong spend for a hobby repo.
- **Durable-execution runtime rewrite** — harden the cheap bash analog instead.
- **SBOM** — negligible value at this scale.

## Where the waves land you

The scorecard above is **today's** state: print-bench leads on 3 dimensions
(verification rigor, gate determinism, provenance) and trails on the other 7.
The waves are what close that gap. **Projected after Waves 1+2**, the fixes flip
five more cells — provider abstraction (item 1), security backstops (items 4/6),
self-measurement (item 7), plus independent review (item 5) — leaving
print-bench **ahead on ~8 of 10 axes** and behind on exactly two: execution
isolation and durable orchestration. Those two are the paid-cloud moat, and
correctly out of scope (P3). You can't out-Vercel Vercel on cloud infra; you can
beat their *factory design* wherever it is made of judgment rather than money.

---

*Credit: this baseline and the ideas it borrows (cross-vendor reasoning-blind
review, bounded branch-scoped self-healing, factory-brain memory) are inspired
by Vercel Labs' publicly documented Foreman / eve software-factory template.*
