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
loop's approval poll (issue #444): `gather_greenlight_poll` returns the same
threads with comment ids intact, `list_reactions` one greenlight's reactions,
and `permission_of` each reactor's real permission — and the loop's
**learning half** (issue #445): `gather_greenlight_rounds` finds every
greenlighted thread (a search probe over the marker phrase, per-candidate
verified against a real marker first line, so a body that merely quotes the
marker never counts) with its resolution state. Still all GET, still the only
network-capable *read* module in the package; the writes those reads can earn
live in `pushthrough.py`, never here.

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

- The tool never writes — with exactly one confined exception: a test asserts
  no HTTP write verb (`POST`/`PATCH`/`PUT`/`DELETE`) appears anywhere in the
  package **outside `pushthrough.py`**, and a second test pins that the seam
  is real (it exists and still carries the pushes it exists for) and imports
  nothing beyond the package's own modules — the backlog groomer's `github.py`
  shape the greenlight loop's parent issue named. The pure core imports
  nothing network-capable — `github.py` is the one read module allowed
  `urllib`, and everything it does is a GET.
- The scheduled workflow's `report` job has a single write: upserting one
  marker-matched sticky `reeve-report` issue, keyed belt-and-braces by its label
  and the body's first line. That job holds no provider secret and runs no
  agent, so the package itself needs no deny-backstop — the drift guard pins
  the keylessness structurally (`tools/model-registry/tests/`).
- The first "hand" — the greenlight drafter — is shipped (#296 stage 2, #443)
  as a **separate job** in the same workflow, so neither claim above leaks into
  it: it holds the provider secret, and its write is a wrapper-mediated comment
  behind `.claude/reeve-settings.json` (the #442 deny backstop), outside this
  package. Its follow-through — the approval poll and push-through (#444) —
  joined it as the job's first step and is deterministic, keyless code (below).
  The wider hands (auto-filing/labeling follow-up issues) stay staged behind
  the labeler's wrapper + deny-backstop, because acting on the pulse from
  model output over untrusted text crosses into agentic-writer territory.

## The greenlight loop (issue #443, #296 stage 2)

The LLM half of the HITL decision gate, wired on this tool's containment
pieces. A separate `greenlight` job in `.github/workflows/reeve.yml` runs after
the keyless report and:

- resolves the registry's `[chain:reeve-greenlight]` (`.github/models/
  registry.conf`) and walks it across providers (#544): the GLM head on the
  conf's `provider:`, then the Anthropic tail, one ship step per link — the
  resolve step's `model-registry shape` check fails up front on a chain that
  does not fit that walk; no model id in the workflow;
- selects the work **as trusted workflow code** (`reeve greenlight-select`):
  the open `needs-decision` issues carrying no greenlight marker, oldest first,
  bounded by the `greenlight_cap` conf key — skipping any that is a
  `provider-triage` escalation (its body carries the `<!--
  provider-escalation:<chain> -->` marker; #544): an account/key ask with a
  fixed remedy is not a decision a charter verdict can rule on;
- runs the drafter (`/reeve-greenlight`, `.claude/skills/reeve-greenlight/`)
  with `--permission-mode dontAsk` over the #442 wrapper — its only shell
  surface — behind `.claude/reeve-settings.json`, its writes bound to the
  selected set and capped per run.

It drafts **advisory** verdicts: a YES/NO on system-level decisions (citing the
repo-root `PM.md` charter line) or a ROUTE note handing design taste to its
design PM — never a label, never a resolved gate, advisory until a human 👍.
A ROUTE note's footer says a reaction on it approves nothing, and the poll
agrees structurally: `route` markers are never resolved by reactions.

### The approval poll and push-through (issue #444)

The loop's authority half — the job's **first** step, keyless and deterministic
so it runs even without the provider secret, and before `greenlight-select` so
a resolution this run shrinks the drafter's set. GitHub fires no webhook for
reactions, so the NEXT scheduled run polls its own prior marker-carrying
greenlights (`reeve greenlight-poll`):

- **whose reaction counts** — only accounts whose real repository permission is
  `admin`/`maintain`/`write`, read per user via the collaborators permission
  endpoint. That is the same check `decide.yml` makes before honouring a typed
  command; `author_association` is never used (it describes prior
  participation, not current access). One 👍 resolves, one 👎 overrules, none
  keeps waiting, and a contested greenlight fails closed to overrule.
- **what outranks a reaction** — an explicit `/decide` comment by an authorized
  author, always. The loop yields to `decide.yml` rather than parsing a human's
  typed command twice; a read-only author's `/decide` outranks nothing (the
  command workflow itself would refuse it).
- **what an approval does** — `pushthrough.py` applies decide.yml's own
  sequence **via the API, never a posted `/decide` comment**: the stage-1
  lesson, observed live, is that the comment tooling appends an attribution
  footer and `decide.yml` anchors on a bare command, so a bot-posted command
  is silently neutralized while the run reports success. The order is
  fail-closed: verdict label first (a failure there records nothing at all),
  then best-effort removals of the opposite label and `needs-decision`, then
  `autonomy-ok` where the marker carried `arm=1` **and** the verdict is yes
  (the existing backlog burn / design run pick the work up — pull-based
  resume, no new executor), then the ledger row, then the resolution reply.
- **two tokens, on purpose** — labels and comments use the workflow's
  `issues: write` token; the ledger commit to the default branch uses
  `REGEN_TOKEN`, the fine-grained PAT, exactly as the `regen` job commits its
  artifacts: the default-branch ruleset refuses a push from the Actions bot
  (the GH013 lesson), and a PAT-authored commit re-triggers CI so the ledger
  change lands verified. The workflow therefore needs no permission wider
  than its present `issues: write`. Without the PAT the append is skipped and
  reported — decide.yml's documented degradation: the label is the
  authoritative verdict.
- **an overrule** — one reply recording it, the gate stays parked, and the
  thread's resolution marker means no new greenlight is drafted on it.

`greenlight.py` holds the pure decision table and the ledger append (mirrored
from `decide.yml`'s own algorithm, round-tripped through its parser in the
tests); `pushthrough.py` is the one write seam; `test_pushthrough.py` pins the
five Done-when cases from the issue, including the injected mid-sequence
failure that must leave `decision-approved` set with `needs-decision` still in
place — never the reverse.

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
(**shipped `false`** — the loop is built but not lit) plus at least one of the
walk's provider secrets actually being set (a keyless head falls through to the
Anthropic tail, #544); no key on any provider is a `::notice::` skip, never a
red run.

## CLI

```bash
reeve report --input snapshot.json          # snapshot JSON -> markdown report
reeve gather --root .                        # committed files -> snapshot JSON
reeve run --root . --conf .github/reeve.conf # gather then report (the workflow)
reeve run --root . --repo owner/name         # + the GET-only run-health read
reeve run --root . --andon "$AI_ANDON_CORD"  # 'pulled' adds the 🛑 andon banner line
reeve config --get enabled                   # read the committed policy
reeve armed --variable "$REEVE_ENABLED" --conf-enabled "$enabled"
reeve greenlight-select --repo owner/name    # the draftable parked-decision queue
reeve greenlight-poll --repo owner/name      # poll prior greenlights; push approvals
                                             # (reads REGEN_TOKEN for the ledger commit)
reeve greenlight-context --repo owner/name   # the drafter's precedent digest (#445)
reeve greenlight-append --repo owner/name    # records for newly-resolved rounds (#445)
```

`--repo` (on `gather` and `run`) attaches the run-health block; the token comes
from `GH_TOKEN`/`GITHUB_TOKEN`. Without it the run is fully offline and the
run-health detectors read "not evaluated".

`--andon` (on `report` and `run`, default `$AI_ANDON_CORD`) is the value of the
AI andon cord repo variable (docs/andon-cord.md): only the word `pulled` —
case-insensitive, the same normalization `armed` applies and the same comparison
GitHub's `vars.AI_ANDON_CORD == 'pulled'` makes — inserts the one `🛑` banner
line under the H1, so a reader of the sticky report learns the skipped AI runs
are intentional rather than a dead routine; anything else renders today's bytes.
The cord is live repo state: never a conf key, never in the snapshot.

## Tests

Stdlib-only; the `[test]` extra is just pytest.

```bash
pip install -e 'tools/reeve[test]'
python -m pytest tools/reeve/tests -q
```

The golden-file test (`tests/fixtures/report.golden.md`) pins the report bytes,
and its pair `report.andon-pulled.golden.md` pins the pulled rendering — the same
bytes with exactly the banner line and its blank inserted once (released is
asserted equal to the golden as the negative control);
each detector has a positive case and a negative control, the precedent log has
a golden round-trip against the committed seed, and `tests/test_learning_wiring.py`
pins the workflow wiring (context channel, three-file branch parity, keyless
observer). CI runs the suite when `tools/reeve/**`, `.github/reeve.conf`,
`.github/workflows/reeve.yml` or the precedent-log seed changes
(`scripts/ci-classify.sh`).
