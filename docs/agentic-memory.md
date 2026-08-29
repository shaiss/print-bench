# Agentic memory (per-agent episodic recall)

The tracked design is [issue #426](https://github.com/shaiss/print-bench/issues/426)
— the spike where the decisions below were made. This doc is the **bigger
picture** the build sub-issues hang off: each sub-issue ships one slice, this
doc says how the slices fit and why each mechanism is the way it is. It is the
narrative; #426 is the decision record.

The one-line goal: **a scheduled routine should start a firing with recall of
its own past runs, instead of cold every time.**

## The problem: a write-mostly paper trail

print-bench already produces an unusually rich, committed record — `telemetry/log.ndjson`,
`.github/decisions/ledger.conf`, `designs/*/NOTES.md` (incl. the `## Field test log`
sections), git history, agent PR/issue comments. Tulving's three memory types are
literally in the file tree: **episodic** (telemetry, field-tests, git log),
**semantic** (`CLAUDE.md`, `docs/`, `PM.md`), **procedural** (`.claude/skills/`,
`scripts/`).

But it is **write-mostly**. Every scheduled routine (backlog-burn, design-run,
chunker, labeler, product-scout, Oracle, Jane/Drik) starts each firing **cold**:
the workflow hands the skill a one-line prompt (`/ship-issue <N>`) with no run
history. No routine reads its own past runs; the prose is not indexed; there is
no salience, consolidation, or retrieval. `telemetry/log.ndjson` records *system
gate runs*, not *agent decisions/outcomes* — there is no "agent episode log." The
gap is the **read side** of memory for an individual routine, and this feature is
that read side.

## The frame: "Inside Out, minus the emotions"

The design was framed by the Pixar model — **core memories**, **anchor events**,
**memory degradation** — translated honestly onto buildable mechanisms. Three
guards come from where the metaphor *lies*:

- **Memory is not a recording.** Real episodic memory (and RAG) is reconstructive
  and lossy; it confabulates. Recall is **re-grounded against a source of truth**
  before it is acted on — the `/resume-design` "verify before you trust" rule,
  made standing.
- **A "core memory" can be vivid and wrong** (flashbulb confidence ≠ accuracy).
  Pin the decision *and* keep an executable check that re-verifies it — the
  `guard-check.sh` / `*-perms-check.sh` pattern.
- **Consolidation that smooths away the anomaly is the failure mode** (Bartlett
  "leveling"). Any summary copies pinned anomalies **verbatim**, never abstracts
  them.

## Three layers

| Layer | What | Scope | Status |
|---|---|---|---|
| **Semantic / shared** | CI checks, gates, telemetry, ledger, `CLAUDE.md` | Read by every agent | **Exists — untouched** |
| **Episodic (new)** | A routine's own run history — what it tried, chose, how it turned out | **Per-agent, private** | The thing we build |
| **Core memories** | PM decisions that impact others — pinned, high-salience | Originate in a PM, **broadcast to impacted agents** | Pin + surface existing `PM.md`/ledger records |

**Memory is strictly per-agent** — a routine remembers *its own* runs. Shared
context already exists (the CI gates are the shared "islands" every agent stands
on). The one thing that crosses the per-agent boundary is a **core memory**: a PM
decision that impacts others, which already lives in the `PM.md` decision log and
`.github/decisions/ledger.conf`, so "core memory" here means *pin + surface*, not
a new store.

## Two scores, never conflated

Everything turns on keeping these apart.

| | **Importance / salience** | **Relevance** |
|---|---|---|
| Computed when | **Write time** (once, stored on the memory) | **Recall time** (every run) |
| Relative to | The memory itself — was it consequential/surprising? | The **current task** |
| How | **Deterministic** (no LLM) | **Lite-LLM + deterministic** hybrid, **1–99** |
| Purpose | What to keep / pin / decay | What to inject now, and at what weight |

### Importance — the write-time term (deterministic)

- **Prediction error — the engine of anchor events.** `importance ∝ |expected −
  actual|`. print-bench already knows the expectation (the prior telemetry record,
  the coupon, gate history), so a gate expected-to-pass that *fails* is
  high-surprise → high importance; the 400th green run is ~zero.
- **Unfinished business (Zeigarnik).** Incomplete/interrupted/failed runs are
  retained above completed-clean: a dead SHIP-LOCK, an unconverged design, a
  `needs-decision` park, a withdrawn run.
- **Core (pinned):** a PM cross-cutting decision — pinned, never decays.

### Relevance — the recall-time term (lite-LLM + deterministic)

Humans recall the *relevant* memories, not all of them. At context-load time a
fast step scores each candidate against the current task and injects a **ranked,
weighted subset**:

1. **Deterministic pre-filter** — narrow by cheap overlap (same design,
   technique family — NUGGS, threads, print-in-place — tags, recency). No model
   call; also the fallback if the lite model is unavailable.
2. **Lite-LLM relevance score (1–99)** — rank the shortlist against the task (a
   cheap-tier model from the [#206 registry](../tools/model-registry/README.md), **scoring
   only** — it emits a number over untrusted text, never executes instructions in
   a memory). `99` = critical for the task; `1` = a **floor, not exclusion**.
   *Worked example:* a NUGGS-fit memory scores ~99 for a NUGGS print and ~1 for a
   box; the box run may still carry it, at weight ~1.
3. **Associative expansion (spreading activation)** — pull in the strongest-linked
   neighbors of each hit via `links[]`, so related lessons the task did not
   directly cue still surface.
4. **Weighted, ordered injection** — inject the top set annotated with weights,
   ordered highest-nearest-the-task (serial-position); a budget bounds context;
   the *weight* (floor 1), not a hard cutoff, is what fades an old memory.
5. **Metamemory return** — recall hands back an explicit **"no relevant memory" /
   confidence** signal, so the agent proceeds fresh instead of over-trusting a
   thin hit.

## The other mechanisms

- **Selective encoding depth (salience-proportional + gist decay).** Human
  encoding is not uniform; depth tracks how much an event mattered. Note depth is
  set by the importance score: salient events get a **rich** structured note
  (what changed, why, outcome, full context tags, links); routine events get a
  **gist** note (a line + a couple tags). As a rich note ages, its **verbatim
  detail is pruned to gist** at consolidation while the gist persists
  (fuzzy-trace theory) — the raw episode still lives permanently in git.
- **Decay = retrieval strength (Bjork), not a flat timer.** Two coupled strengths
  per memory. **Storage strength** (the raw episode) is permanent in git —
  *archive, don't erase*. **Retrieval strength** governs the active recall index:
  it fades with disuse and is **reinforced by a useful recall** (recall → good
  outcome → strengthen; recalled-but-useless → fade faster). The store self-tunes
  which memories matter, **with no LLM deciding**.
- **Interference — cluster near-duplicates.** Repeated similar episodes are
  collapsed (400 green runs → count + exemplar) so the one anomaly (the fused-hinge
  lesson) is never drowned.
- **Immutable episodes.** Memories are **append-only**; corrections are new
  *linked* episodes, never destructive rewrites. Clean audit trail; the store
  still self-corrects via retrieval strength, not edits. (This is our one
  deliberate divergence from A-MEM's note-evolution — see below.)
- **Provenance & trust weighting (source monitoring).** Every note records origin
  (`run_id`, model, human|agent) and whether it was **`verified`** against a
  source of truth (field-test / gate / render) or only **`model-asserted`**.
  Recall trust-weights by provenance; at equal relevance, verified outranks
  asserted.

Recall order ≈ `relevance × retrieval_strength × provenance_weight × recency`,
pinned core memories always eligible (still relevance-weighted so an irrelevant
one rides light).

## The store

`tools/agent-memory/`, a **committed, file-based** store, **one per routine**
(e.g. `.claude/memory/<routine>.*`), written with the non-re-triggering
`GITHUB_TOKEN` commit pattern telemetry already uses. Backend is an open
build-time decision (evaluate file-based options — NDJSON/JSON, SQLite +
`.dump` textconv, TinyDB, DuckDB, LMDB, or an embedded graph — against
git-diffable, light-dependency, embeddable, safe-committed criteria).

Note shape (A-MEM-flavored, append-only):

```text
ts, run_id, issue|design, action, choice, outcome,
importance, depth[gist|rich], retrieval_strength,
provenance{model, human|agent, verified: source-confirmed|model-asserted},
tags[], links[]
```

## Trust boundary (non-negotiable)

Episodes derive from untrusted issue text and prior model output, so memory must
not become a prompt-injection sink:

- **Recall is read-only**; recalled content is **untrusted data, never
  instructions**; an agent acting on recall **re-grounds it against a source of
  truth** (the render / STL / CI output).
- The **lite-LLM relevance scorer is scoring-only** — it emits a 1–99 number and
  never acts on memory content.
- **Provenance weighting** keeps `model-asserted` memories (the injection path an
  attacker could seed) from ever outranking `source-confirmed` ones.
- **Record** goes through the established writer pattern — an MCP tool (JSON args,
  not a shell line under `--permission-mode dontAsk`) behind the routine's
  `.claude/*-settings.json` deny-backstop, with each routine's backstop denying
  the *other* routines' memory files.

Blast radius stays **mis-ranking, not mis-acting**.

## Phased build-out (the sub-issues)

- **Slice 0 — store backend decision.** Resolve the file-based-DB choice above; a
  prerequisite for everything, and a human design call.
- **Slice 1 — per-agent episodic recall for one routine.** Pilot: **`design-run`**.
  The store + `record` (deterministic importance, salience-proportional depth,
  provenance, append-only) + relevance-gated `recall` (pre-filter → lite-LLM →
  link expansion → weighted injection → confidence signal) + the retrieval-strength
  reinforcement loop + near-duplicate clustering. No LLM in the write path; the
  lite-LLM appears only in the recall gate. Blast radius = one routine.
- **Slice 2 — core memories.** PM **declares** cross-cutting decisions
  (`core: yes | impacts: <who>` on the `PM.md` decision log / ledger); pin them and
  **broadcast to all** routines' recall (still relevance-gated).
- **Phase 3 — consolidation / reflection (deferred).** A scheduled "sleep" job
  distils episode clusters into durable gist (anomalies verbatim), runs gist decay,
  and prunes the active index. Evaluate adopting agent **trajectory**
  capture/replay tooling rather than inventing.

Explicitly **not now**: no vector/embedding index (relevance uses lite-LLM +
deterministic overlap until that demonstrably fails); no LLM in the write path; no
shared episode store; no reconsolidation (episodes are immutable); prospective
(future-triggered) memory is parked.

## A-MEM — candidate to learn from, maybe adopt

[A-MEM](https://arxiv.org/abs/2502.12110) applies the Zettelkasten method: each
memory is a structured note dynamically **linked** to related notes. That model is
the closest published match, so evaluate its code as a starting point during
build-out. Reconcile with our constraints: it is a research reference impl, it is
**LLM-in-the-loop** for note generation (we keep the write path deterministic), and
it ships against ChromaDB (we want committed file-first). Adopt the *model*
(notes + links); rework the *substrate*. Our one conscious divergence: we chose
**immutable** episodes over A-MEM's note-evolution (its evolution ≈ reconsolidation,
which we rejected for audit-cleanliness).

## References

Park et al., *Generative Agents* (arXiv:2304.03442) — `recency × importance ×
relevance` + reflection; Tulving (episodic/semantic/procedural); Craik & Lockhart
(levels of processing); Reyna & Brainerd (fuzzy-trace / gist vs verbatim); Collins
& Loftus (spreading activation); Bartlett (reconstructive memory / leveling);
Ebbinghaus + Bjork & Bjork (forgetting curve; New Theory of Disuse — storage vs
retrieval strength; testing effect); Brown & Kulik / Talarico & Rubin (flashbulb,
vividness ≠ accuracy); Zeigarnik (interrupted-task retention); Loftus
(misinformation / false memory); Schacter (source monitoring); A-MEM
(arXiv:2502.12110). Managed frameworks surveyed and set aside for the
server/LLM-on-write/nondeterminism mismatch: Mem0, Zep/Graphiti, Letta/MemGPT,
Cognee, LangMem, Memary, txtai, Memori.
