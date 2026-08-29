# model-registry

The provider/model registry + chain resolver behind the agentic workflows
(issue #206). `.github/models/registry.conf` is the single source of truth for
**which models the workflows run, in what preference order, and why** — so
reordering or swapping a model is a registry edit, not a hunt through every job's
YAML. Before it, every agentic workflow hard-coded its provider + model +
fallback order inline, duplicated across jobs.

The registry is the *decision*; the workflow still supplies the *literal* secret
wiring per provider, because GitHub Actions can only reference a secret by its
literal name (the same constraint `backlog-burn.yml` documents). This tool picks
which model and in what order; the YAML owns the secrets.

## The format

`.github/models/registry.conf` is INI stanzas (stdlib `configparser`), one per
entity, the bracketed name being `<kind>:<id>`:

- **`[provider:<id>]`** — `secret` (the repo secret, referenced literally in the
  workflow), optional `base_url` (an Anthropic-compatible endpoint; omit for the
  native one), optional `notes`.
- **`[model:<id>]`** — `provider` (must resolve), and **required** `notes` saying
  *when/why* to use it. The registry must say why a model is where it is.
- **`[chain:<id>]`** — `models`, a comma-separated **ordered** list of model ids
  (every id must resolve). A job routes to a chain by name and walks its links.

Unknown fields, missing required fields, duplicate stanzas, a model naming an
undeclared provider, and a chain naming an undeclared model all fail the load
loudly with the offending stanza's id — a registry no one wrote never runs.

## Usage

```bash
# Validate the whole registry (fail loud) — run in CI and before a change.
python3 -m model_registry check                 # or: model-registry check

# Resolve a chain: JSON to stdout (position/model/provider/base_url, no secret),
# and link_count + link<N>_model/link<N>_provider lines to $GITHUB_OUTPUT for a
# workflow to read into its ship steps. The secret name and base_url are NOT
# emitted to $GITHUB_OUTPUT (a secret can't be dereferenced by a runtime name, and
# echoing a secret name to a step-output sink trips secret-logging scanners).
python3 -m model_registry resolve review --gh-output "$GITHUB_OUTPUT"

# The ordered model ids, one per line (drift-guard / humans).
python3 -m model_registry chain review

# A human summary of every provider, model, and chain.
python3 -m model_registry show

# Prove each chain link is actually CALLABLE (issue #298): a real 1-token
# Messages request per link whose provider secret is set in the environment.
# Exit 0 only when every attempted link answered; a run that could attempt
# nothing (no secret set) fails too. `check` proves the file parses — it cannot
# prove a model id is servable by a key; only a live request can (the review
# chain's old claude-opus-4-8 backstop passed every static check and was
# rejected at $0 on its first real call). The model-smoke.yml workflow runs
# this with the repo secrets — automatically on any same-repo PR that edits the
# registry or this tool (smoking every chain), and on demand via
# workflow_dispatch: a named chain smokes only that one (default `review`), a
# blank chain input smokes every declared chain. Dispatch it before pointing a
# new routine at a chain.
ZAI_KEY=... ANTHROPIC_API_KEY=... python3 -m model_registry smoke review

# Diagnose a chain that just failed on EVERY link (issue #347). Where `smoke`
# asks "is any id a registry defect?", `classify` asks "what should be done about
# a chain that exhausted?" — a live 1-token probe per link recovers the HTTP cause
# the ship steps hide and reduces it to two signals: an aggregate `class` (the
# action bucket — servable / dead / needs-human / transient) AND a finer `reason`
# (the cause behind it — billing / quota / auth / no-key / rate-limit / outage /
# bad-model-id / served). With --gh-output it appends `class=…` and `reason=…` so
# a workflow can route *out of credit* vs *out of tokens* vs *a bad key* each to
# its own remediation instead of one undifferentiated red. Exit 0 regardless —
# the class/reason ARE the signal. The shared `.github/actions/provider-triage`
# composite action runs this and escalates the human-fixable causes through the
# decision gate; every chain-walking workflow invokes it on exhaustion.
ZAI_KEY=... ANTHROPIC_API_KEY=... python3 -m model_registry classify review
```

Stdlib-only, so a workflow runs it straight from the checkout with
`PYTHONPATH=tools/model-registry/src python3 -m model_registry …` — no pip step in
front of the review pipeline.

## Where the decision lives

`.github/models/registry.conf` is the committed, git-tracked source of truth,
read identically every run (the same pattern as `.github/ci-gates/registry.conf`
and `.github/backlog-burn.conf`). Adding or reordering a model *within an existing
provider* is a one-line edit there. Adding a **new provider** still needs a
reviewed workflow ship step too (its secret is literal), so the registry entry and
the ship step land together.

`auto-review.yml` is the first consumer: its `design-changes` job resolves the
`review` chain into `model1..model6` outputs, and the Jane/Drik/PM-triage/coach ship steps
read those instead of hardcoding `--model`. `product-scout.yml` and the four
scheduled routines — `design-run.yml`, `backlog-burn.yml`, `chunker.yml`,
`labeler.yml` (issue #326) — resolve their own chains in the job that consumes
them and walk the links, one ship step per link per provider, so a dead model
falls through to the next instead of killing the run. Since #327 each routine
chain carries a multi-model tail *within its routine's provider* (the GLM
routines walk glm-5.2 → 5.1 → 4.6 — the chunker among them since #347/#358
rerouted it off the unfunded Anthropic account), so no routine bottoms out on a
single id. Each routine's chain must
sit on the provider its `.github/<routine>.conf` declares; the workflow's
resolve step cross-checks that before any key is spent.
`tests/test_workflow_drift.py` pins the registry and every consumer workflow
together so they cannot silently diverge — including, since #327, that the
expressions reading the walk's *outcome* cover every link (an expression still
on link 1 after a chain deepened would send a healthy link-2 run red).

When a chain *does* exhaust every link, each consumer invokes the shared
`.github/actions/provider-triage` composite action, which runs `classify` to
recover the cause and escalates a human-fixable one (out of credit / out of
tokens / bad or missing key) through the `needs-decision` gate — so a scheduled
red nobody is watching becomes one deduped, reason-tailored ask instead. A dead
model id still reds (a registry defect); a rate limit or outage just retries.

The `review` chain's Anthropic backstop is itself a chain — Opus 4.8 → Sonnet 5
→ Haiku 4.5 — rather than a single model (issue #298): a single hardcoded id can
be unservable by a key (a deprecation, an access tier), so one dead id must never
be the whole "never lose a review" backstop, and `model-smoke` proves each link
live. (The tail now leads with `claude-opus-4-8` — the Anthropic model the team's
design work rates highest and the ship-routine default; whether a given key can
serve it is exactly what the live smoke confirms, rather than a static claim.)

## Layout

- `src/model_registry/registry.py` — the parser (fail-loud, stdlib `configparser`)
  and the `resolve(chain)` → ordered `ResolvedLink`s.
- `src/model_registry/cli.py` — `check` / `resolve` / `chain` / `show` / `smoke` /
  `classify`; `resolve` emits the `$GITHUB_OUTPUT` links a workflow consumes,
  `classify` emits `class` + `reason` for a workflow's exhaustion branch.
- `src/model_registry/smoke.py` — the live-callability proof (issue #298) and the
  package's single network seam (`_post`); everything else stays statically
  network-free, and a test enforces that confinement. `diagnose_chain` reduces an
  exhausted chain to `(class, reason)`; `_reason_fine` is the finest cause and
  the coarse `_classify_fine` verdict is DERIVED from it, so the two cannot drift.
- `src/model_registry/__main__.py` — `python -m model_registry` for the no-install
  workflow invocation.

Stdlib-only by policy: the resolver runs from a bare checkout in the review
pipeline and on the system Python in CI, so a third-party import would force a pip
step in front of the routine that decides which model runs — the rule
`tools/lineage`, `tools/ci-gates` and `tools/backlog-burn` all keep.

## Tests

```bash
pip install -e 'tools/model-registry[test]'
python -m pytest tools/model-registry/tests -q
```

A positive case and a negative control for every parser rule, the CLI's
`$GITHUB_OUTPUT` emission, the smoke command's judgement (served / failed /
skipped, and never green with nothing attempted) through its injected seam,
`classify`'s class **and** reason for every cause (billing vs quota vs auth vs
rate-limit vs outage vs a dead id, with the reason↔class consistency pinned so
the split can't misroute), and the drift guard that holds
`.github/models/registry.conf` and its consumer workflows in correspondence —
including that every chain-walking workflow stays wired to the shared
`.github/actions/provider-triage` action on its own chain.
