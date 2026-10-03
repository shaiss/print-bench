# agent-memory

Per-agent **episodic memory** for the autonomy routines — the store and its
deterministic **record** (write) path. This is Slice 1a of the agentic-memory
build (design guide: [`docs/agentic-memory.md`](../../docs/agentic-memory.md);
decision record: issue #426; this slice: issue #429).

A routine hands `record` an **event** — what it did, chose and got, plus the
salience facts it already knows — and the package encodes it into an
immutable **note**: importance scored deterministically, encoding depth set by
salience, provenance classed by what vouches for it. **No LLM in the write
path**: every derived field is a pure function of the event, recomputable by a
reviewer from the note itself.

Not here, on purpose: recall (Slice 1b, #430), retrieval-strength
reinforcement and near-duplicate clustering (1c, #431), and wiring any routine
to it (1d, #432). Nothing in the repo calls this package yet, and no workflow
runs it beyond its own test job and `check.sh`.

The mold is `tools/lineage` / `tools/brief-sources`: stdlib-only, src layout,
its own pytest suite with a positive case and a negative control per rule,
zero network.

## The store (Slice 0's decision, #428)

```text
tools/agent-memory/store/<agent>/<id>.json
```

One file per note; `<id>` is the SHA-256 of the note's canonical content, so
the path *is* the content:

- **Concurrent writers never collide.** Two routines recording two episodes
  in overlapping windows write two different paths — git merges added files
  with no shared line to conflict on. (The reason per-memory-files won Slice
  0 over a shared NDJSON log or a SQLite file.)
- **Writes are idempotent.** The same episode recorded twice — a retried
  run-end step — lands on the same path with the same bytes; the second
  `record` is a no-op that reports `unchanged`.
- **Diffable.** Each note is pretty-printed, sorted-key, UTF-8 JSON with a
  trailing newline: a review UI shows a new note as one readable file.
- **Read-cold.** `load` is a glob and a strict parse of each file — no index,
  no cache, nothing to warm at job start. A missing store is an empty store.
- **Per-agent.** Memory is strictly per-agent (#426): a note's `links` must
  name existing notes in the **same** agent's directory.

The store directory does not exist until Slice 1d wires a routine to write
into it; `check` treats its absence as empty.

## Immutable, append-only

#426 rejected reconsolidation: a memory is never rewritten. The package has
no update and no delete — only `record` (create-only: the file is opened
`"xb"`, so the existence test and the write are one syscall), `load` and
`check`. A `record` that finds *different* bytes already at its path refuses
(`ImmutableNoteError`): with content-addressed ids that can only mean the file
was edited after it was written. **A correction is a new note whose `links`
point at the one it corrects**; the original stays byte-identical.

`check` catches what the write path cannot see — an edit made by hand or by a
script. It re-derives every note from its own inputs and refuses: a field
edit (the id no longer matches the content hash), a promoted importance or
depth, a self-flipped `verified`, a reformatted file (non-canonical bytes), a
renamed or misfiled note, a stray file, a dangling link, an unknown schema
version. What it cannot see is a *deleted* note nothing links to — that is a
git-history question, flagged for Slice 1d (see "Open for later slices").

## The event (what a routine supplies)

| Field | Required | Meaning |
|---|---|---|
| `agent` | yes | the routine, kebab-case (`design-run`) — also its store directory |
| `ts` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ`, supplied by the caller — the write path never reads a clock, so a retry is byte-identical |
| `run_id` | yes | the run that produced the episode (a GitHub run id) |
| `issue` / `design` | at least one | what the episode is about (#429's `issue\|design`); both is fine |
| `action` / `choice` / `outcome` | yes | what it did, what it chose, how it turned out |
| `detail` | no | the longer story — kept only in a **rich** note |
| `status` | yes | `completed` · `failed` · `incomplete` · `parked` · `withdrawn` |
| `expected` / `actual` | as a pair | the prior and the realized outcome on [0, 1] (e.g. the gate's pass rate vs 0/1) |
| `signals` | no | consequence signals, a closed set (below) |
| `author` | yes | `agent` or `human` |
| `model` | iff `agent` | the model that wrote it; a human note carries none |
| `sources` | no | `{kind, ref}` — what vouches for it; `kind` ∈ `ci` · `field-test` · `gate` · `render` |
| `tags` | no | recall cues (design, technique family, printer, material) — case-folded, deduped, sorted |
| `links` | no | ids of related notes of the same agent (A-MEM adjacency) |

Strict and fail-loud: an unknown key, a missing key, a malformed value, or a
**derived** key (`importance`, `depth`, `verified`, `provenance`, `salience`,
`retrieval_strength`, `id`, `schema`) is refused. A model writing its own
episode cannot raise its own importance, promote itself to a rich note, or
certify itself confirmed.

Text is normalized before hashing (NFC, LF line endings, outer whitespace
stripped) so the same words land on the same id on every machine.

## The rules

All constants live in `src/agent_memory/rules.py`; the golden tests pin them,
so a retune is a deliberate one-file diff (#426's "Still open" item 3).

### 1. Importance (write time, deterministic)

```text
importance = round_half_up(60 × |expected − actual|)   # prediction error
           + ZEIGARNIK[status]                          # unfinished business
           + Σ CONSEQUENCE[signal]                      # baseline consequences
clamped to [0, 100]
```

| Term | Values |
|---|---|
| Prediction error | `60 × \|expected − actual\|` — the largest single term, "the engine of anchor events"; 0 when unmeasured |
| Zeigarnik | `completed` 0 · `withdrawn` 35 · `parked` 35 · `incomplete` 40 · `failed` 40 |
| Consequence | `field-test-failure` 25 · `fuse-strong-warn` 20 · `escalation` 15 · `resolved-after-retries` 10 |

The 400th green run scores 0; a gate expected to pass that fails scores high.
Additive on purpose: every term is stored in the note's `salience` block, so
the number can be recomputed by hand — and `check` does.

### 2. Encoding depth (salience-proportional)

`importance ≥ 35` → **rich**: full text, `detail`, every tag. Below →
**gist**: each of `action`/`choice`/`outcome` cut to its first line (≤ 120
characters, an ellipsis when clipped), no `detail`, at most 2 tags. Every
unfinished status scores ≥ 35 on its own, so an unfinished run is always
rich. `links` and `sources` survive into a gist — they are structure and
trust, not detail.

### 3. Provenance

`verified` is `source-confirmed` **iff** the event cites at least one source
of truth; otherwise `model-asserted`, whoever wrote it — the class recall must
re-ground before acting on (#426's false-memory guard). Untrusted text
(an issue comment) is not a source kind, so it can seed an asserted memory
but never a confirmed one.

### 4. Immutability

Above: create-only writes, no update/delete surface, `check` re-derives
everything.

## The note (what is stored)

```json
{
  "schema": 1,
  "id": "<sha256 of the canonical content>",
  "agent": "design-run",
  "ts": "2026-08-30T16:00:00Z",
  "run_id": "17000000001",
  "issue": 440,
  "design": "czs-slider",
  "action": "widened the flexure chamber cut 0.2 mm",
  "choice": "widen the cut rather than thin the flexure",
  "outcome": "fusecheck now splits 2 bodies",
  "detail": "Flexure welded on the sliced STL until the chamber cut was widened.",
  "salience": {"status": "failed", "expected": 0.9, "actual": 0.0, "signals": ["fuse-strong-warn"]},
  "importance": 100,
  "depth": "rich",
  "retrieval_strength": 1.0,
  "provenance": {"author": "agent", "model": "glm-5.2", "verified": "source-confirmed",
                 "sources": [{"kind": "gate", "ref": "fusecheck czs-slider run 1"}]},
  "tags": ["flexure", "fusecheck", "petg"],
  "links": []
}
```

(Shown compact; the committed file is two-space-indented with sorted keys.)
`retrieval_strength` starts at 1.0 and is **excluded from the id** — it is
index state, not what happened — so Slice 1c can evolve it without renaming a
note. Until 1c owns that rule, `check` refuses any other value.

## CLI

Run from the repo root (`--store` defaults to `tools/agent-memory/store`).

```bash
PYTHONPATH=tools/agent-memory/src python3 -m agent_memory score  --event event.json   # dry run: print the note
PYTHONPATH=tools/agent-memory/src python3 -m agent_memory record --event event.json   # write it if absent
PYTHONPATH=tools/agent-memory/src python3 -m agent_memory check                       # validate the store
PYTHONPATH=tools/agent-memory/src python3 -m agent_memory --selftest                  # prove the rules fire
```

`--event -` reads stdin. Exit codes: `0` success (an `unchanged` idempotent
record is success); `1` `check` found problems or a selftest control failed;
`2` a bad invocation, a refused event, or a refused overwrite.

`check.sh` runs `--selftest` and `check` on every run, uninstalled.

## Tests

`python -m pytest tools/agent-memory/tests -q` (a `conftest.py` path shim
makes it run uninstalled; CI pip-installs `tools/agent-memory[test]` first).
A positive case and a negative control per rule:

- `test_importance.py` — prediction error (proportional, symmetric, paired,
  bounded), Zeigarnik (every unfinished status outranks completed-clean),
  consequence signals (closed set, no double count), the clamp, half-up
  rounding, and golden pins for the constants;
- `test_depth.py` — salient → rich, routine → gist, the threshold boundary,
  idempotent clipping, and a hand-promoted gist note refused;
- `test_provenance.py` — a cited source confirms, none asserts, no
  self-certification, author/model consistency, a hand-flipped `verified`
  refused;
- `test_immutability.py` — create-only, idempotent re-record, refused
  overwrite, corrections as linked notes, per-agent links, no update/delete
  surface, and `check` catching each kind of edit;
- `test_store.py` — the diffable artifact, read-cold loading, determinism
  (input order, line endings, Unicode composition), and the strict schema;
- `test_cli.py` — exit codes and output shapes, plus the **live control**:
  the committed store passes `check`;
- `test_purity.py` — no network import anywhere, no clock or random source
  in the write path, `rules`/`note` free of I/O, only `store` (and the
  selftest's temp dir) writing — each AST scanner with a planted violation
  proving it fires;
- `test_selftest.py` — the `--selftest` passes, and **fails** when a rule
  under it is broken.

## Open for later slices

Settled here so 1b–1d inherit them; each is called out in the PR for the
owner:

- **Committing the notes** (1d): #429 named the telemetry `GITHUB_TOKEN`
  data-branch pattern; the Slice 0 research proposed riding the routine's own
  reviewed PR. This slice writes files only — the commit vehicle is the
  wiring slice's choice.
- **Append-only across git history** (1d): a deleted note nothing links to
  is invisible to `check`; a diff-based guard (no `M`/`D` under
  `store/` in a PR) belongs with the first routine that writes.
- **Who supplies `sources`** (1d): the rule is only as strong as its input —
  the trusted workflow step, not the model's MCP arguments, should populate
  them.

## Layout

- `src/agent_memory/rules.py` — importance, depth, provenance: the pure rules and their constants
- `src/agent_memory/note.py` — event validation, encoding, canonical bytes, the content id, the strict reader
- `src/agent_memory/store.py` — `record` / `load` / `check`; the only filesystem module
- `src/agent_memory/selftest.py` — the offline `--selftest` check.sh runs
- `src/agent_memory/cli.py` — `record` / `score` / `check` / `--selftest`
- `tests/` — the suite above
