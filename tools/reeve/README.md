# reeve

The deterministic **bench-health report** behind Reeve, print-bench's platform
PM (issue #272). Reeve owns the *system* — the gates, the autonomy loop, the
site, the telemetry — as a running whole, and this tool is how it reads the ops
pulse. It is the platform-ops sibling of `tools/backlog-groomer`: same
advisory-only, no-LLM, one-sticky-issue shape, pointed at a different question.
That stays true of the *tool*: the package is deterministic end to end. The
greenlight loop (#296 stage 2, #443) — an LLM drafter that advises on parked
`needs-decision` issues — is built **on top of** this tool's GET seam, not into
it; see "The greenlight loop" below.

## The PM split

print-bench splits the PM role three ways (issue #229 established the first two):

- **Remy** (`/product-scout`) — *generative*: proposes what designs should exist.
- **Vera** (`/pm <design>`) — *enforcement*: holds one design's scope.
- **Reeve** (`/pm print-bench`) — *operational*: owns the bench's own health.

Reeve is advisory. The human lead stays primary and owns every merge; Reeve
never gates one. Its charter is the repo-root `PM.md`.

## What it reads

The primary pulse is entirely file-read from the committed tree:

- **`telemetry/log.ndjson`** (issue #93) — per-run gate history: printcheck
  scores, per-design wall time, preview-budget headroom, archived skips,
  derivative outcomes. Starts empty; "no history yet" is a valid state.
- **Live committed previews** — `designs/*/previews/*.{gif,png}` sizes against
  the `scripts/preview-budget.sh` caps. The one pulse that works with an empty
  log.
- **`telemetry/REPORT.md`** — to detect roll-up drift (log has runs, report
  didn't regenerate).

Plus one opt-in, GET-only live read (`src/reeve/github.py`, the groomer's
pattern; issue #313) — only when `--repo` is passed:

- **Workflow-run conclusions** for the scheduled routines (`design-run.yml`,
  `backlog-burn.yml`, `chunker.yml`, `labeler.yml`) — the ten newest completed
  runs each.
- **Open issues carrying an active 🚢 SHIP-LOCK** claim, and the open PRs and
  `claude/issue-<N>-*` branches that would corroborate one (the selector's
  lock semantics, mirrored from `tools/backlog-burn`, not imported).

The same `github.py` serves the greenlight loop's trusted Select step (issue
#443): `gather_greenlight_queue` lists the open `needs-decision` issues and
reads each thread to see which already carry a greenlight marker — and the
loop's **learning half** (issue #445): `gather_greenlight_rounds` finds every
greenlighted thread (a search probe over the marker phrase, per-candidate
verified against a real marker first line, so a body that merely quotes the
marker never counts) with its resolution state — still all GET, still the only
network-capable module in the package.

## The detectors

Eight pure functions of one snapshot, deterministic order, byte-stable report:

| Detector | Fires when |
|---|---|
| `budget-tightening` | a committed preview's size headroom is under `low_headroom_pct` (or over budget) |
| `gate-failing` | the latest run has pre-fails, a part with no score / criticals / a failed slice, or a false derivative override |
| `routine-dead` | none of a routine's last `routine_dead_runs` completed runs succeeded and at least one hard-failed (a pure-cancelled streak is queue noise) |
| `lock-leak` | an active 🚢 SHIP-LOCK is older than `lock_leak_hours` with no corroborating branch or closing PR — a killed run's ghost claim (issue #312) |
| `score-regression` | a part is below `score_floor`, or down ≥ `score_drop` vs the prior full-catalog run |
| `walltime-regression` | a design's gate wall time rose ≥ `walltime_ratio`× (and past `walltime_min_seconds`) |
| `archived-creep` | a design newly dropped out of gating vs the prior full-catalog run |
| `report-drift` | `log.ndjson` has runs but `REPORT.md` is still the empty placeholder |

Comparisons only use full-catalog (`designs=ALL`) runs — a scoped run gates
fewer parts. A detector whose input is absent is reported **not evaluated** with
a reason, never silently empty (the groomer's honesty rule); an offline run
(no `--repo`) reports both run-health detectors that way.

## Advisory-only, checkable

- The tool never writes: a test asserts no HTTP write verb (`POST`/`PATCH`/
  `PUT`/`DELETE`) appears anywhere in the package, and the pure core imports
  nothing network-capable — `github.py` is the one module allowed `urllib`,
  and everything it does is a GET.
- The scheduled workflow's `report` job has a single write: upserting one
  marker-matched sticky `reeve-report` issue, keyed belt-and-braces by its label
  and the body's first line. That job holds no provider secret and runs no
  agent, so the package itself needs no deny-backstop — the drift guard pins
  the keylessness structurally (`tools/model-registry/tests/`).
- The first "hand" — the greenlight drafter — is shipped (#296 stage 2, #443)
  as a **separate job** in the same workflow, so neither claim above leaks into
  it: it holds the provider secret, and its write is a wrapper-mediated comment
  behind `.claude/reeve-settings.json` (the #442 deny backstop), outside this
  package. The wider hands (auto-filing/labeling follow-up issues) stay staged
  behind the labeler's wrapper + deny-backstop, because acting on the pulse
  from model output over untrusted text crosses into agentic-writer territory.

## The greenlight loop (issue #443, #296 stage 2)

The LLM half of the HITL decision gate, wired on this tool's containment
pieces. A separate `greenlight` job in `.github/workflows/reeve.yml` runs after
the keyless report and:

- resolves the registry's `[chain:reeve-greenlight]` (`.github/models/
  registry.conf`), cross-checked up front against the conf's `provider:` label
  — the #326 pattern, no model id in the workflow;
- selects the work **as trusted workflow code** (`reeve greenlight-select`):
  the open `needs-decision` issues carrying no greenlight marker, oldest first,
  bounded by the `greenlight_cap` conf key;
- runs the drafter (`/reeve-greenlight`, `.claude/skills/reeve-greenlight/`)
  with `--permission-mode dontAsk` over the #442 wrapper — its only shell
  surface — behind `.claude/reeve-settings.json`, its writes bound to the
  selected set and capped per run.

It drafts **advisory** verdicts: a YES/NO on system-level decisions (citing the
repo-root `PM.md` charter line) or a ROUTE note handing design taste to its
design PM — never a label, never a resolved gate, advisory until a human 👍.
The reaction poll and push-through are piece #444, deliberately not this.

## The learning half (issue #445)

The loop converges on the bar the owner actually applies, instead of re-deriving
it from the charter every run, through a committed **precedent log**:
`telemetry/reeve-greenlights.ndjson`, one ndjson record per greenlight round
whose gate resolved (closed, or verdict-labeled by `decide.yml`):

```json
{"issue": 267, "verdict": "yes", "reasoning": "…digest…",
 "owner_reaction": "…", "outcome": "merged #299", "recorded_at": "…"}
```

`src/reeve/greenlights.py` is its pure core — a strict, loud-failing parser
(a malformed record names its line, never silently drops), the observer's
derive rule (one record per resolved-and-unrecorded round, idempotent, owner
reaction from the decide.yml ledger row → the verdict label → inline owner
replies → the honest "none observed"), and the capped context digest the
drafter reads. Two CLI verbs compose it over the GET seam:

- **`reeve greenlight-context`** — the *load* half. Renders the most recent
  `greenlight_precedent_cap` records plus the inline owner replies on their
  threads to `.reeve-context/precedent.md`, assembled by trusted workflow
  code (the `.oracle-context/` pattern) so the agent cannot widen its own
  context, with replies framed as evidence, never instructions. The seed
  committed on the default branch records the stage-1 round (#296): six
  verdicts, 6/6 ratified, zero overruled.
- **`reeve greenlight-append`** — the *observe* half. Gathers every
  greenlighted thread's resolution state, derives records for the newly
  resolved, and writes the updated log in place. The push to the `telemetry`
  data branch is trusted workflow bash: a third `observe` job in
  `reeve.yml` (after the drafter, keyless, `contents: write` only) rebuilds
  the branch with git plumbing — GITHUB_TOKEN, so the push triggers no
  workflow — and `ci.yml`'s roll-up carries the file in the same tree, so
  neither builder can silently delete the other's records
  (`tests/test_learning_wiring.py` pins that parity, tamper negative
  included).

Both halves share the loop's gates (`greenlight: true` + arming); a dry run
builds the context but derives and pushes nothing.

## Arming (two keys, shipped disarmed)

The routine runs only when **both** agree: `.github/reeve.conf`'s `enabled: true`
(committed intent) **and** the `REEVE_ENABLED` repo variable (the live human-only
switch). Shipped with the variable unset, so a clone/fork can't silently arm it.
The 2×2 decision is code (`reeve armed`), unit-tested. The greenlight job adds a
third, keyless-until-lit gate of its own: `greenlight: true` in the conf
(**shipped `false`** — the loop is built but not lit) plus the conf-declared
provider's secret actually being set; a missing secret is a `::notice::` skip,
never a red run.

## CLI

```bash
reeve report --input snapshot.json          # snapshot JSON -> markdown report
reeve gather --root .                        # committed files -> snapshot JSON
reeve run --root . --conf .github/reeve.conf # gather then report (the workflow)
reeve run --root . --repo owner/name         # + the GET-only run-health read
reeve config --get enabled                   # read the committed policy
reeve armed --variable "$REEVE_ENABLED" --conf-enabled "$enabled"
reeve greenlight-select --repo owner/name    # the draftable parked-decision queue
reeve greenlight-context --repo owner/name   # the drafter's precedent digest (#445)
reeve greenlight-append --repo owner/name    # records for newly-resolved rounds (#445)
```

`--repo` (on `gather` and `run`) attaches the run-health block; the token comes
from `GH_TOKEN`/`GITHUB_TOKEN`. Without it the run is fully offline and the
run-health detectors read "not evaluated".

## Tests

Stdlib-only; the `[test]` extra is just pytest.

```bash
pip install -e 'tools/reeve[test]'
python -m pytest tools/reeve/tests -q
```

The golden-file test (`tests/fixtures/report.golden.md`) pins the report bytes;
each detector has a positive case and a negative control, the precedent log has
a golden round-trip against the committed seed, and `tests/test_learning_wiring.py`
pins the workflow wiring (context channel, three-file branch parity, keyless
observer). CI runs the suite when `tools/reeve/**`, `.github/reeve.conf`,
`.github/workflows/reeve.yml` or the precedent-log seed changes
(`scripts/ci-classify.sh`).
