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

# Does a chain FIT a workflow's literal ship-step walk (issue #544)? A routine's
# walk is a fixed sequence of literal steps — its layout, one provider per step
# in file order — and the conf's `provider:` names the head. This applies the
# same pure rule the drift guard pins (`walk_shape_errors`): link 1 on the head
# provider, exactly one link per step, link N on step N's provider. One
# `::error::` per violation naming the registry file, the conf and the link;
# exit 1 on any. Every chain-walking routine's resolve step runs it before a
# key is spent.
python3 -m model_registry shape backlog-burn --head zai \
  --conf .github/backlog-burn.conf --layout zai,zai,zai,anthropic,anthropic

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
and `.github/backlog-burn.conf`). Adding or reordering a model *within a slot's
provider* is a one-line edit there. Adding a **new provider** still needs a
reviewed workflow ship step too (its secret is literal), so the registry entry and
the ship step land together.

`auto-review.yml` is the first consumer: its `design-changes` job resolves the
`review` chain into `model1..model6` outputs, and the Jane/Drik/PM-triage/coach ship steps
read those instead of hardcoding `--model`. Every scheduled routine —
`design-run.yml`, `backlog-burn.yml`, `chunker.yml`, `labeler.yml` (issue
#326), `product-scout.yml`, `spike-converter.yml`, `adoption-assessor.yml`,
`growth-twitter.yml`, `reeve-growth.yml`, both jobs of `wright.yml` and the
`greenlight` job of `reeve.yml` (#544 Part B) — resolves its own chain in the
job that consumes it and walks the links, one ship step per link, so a dead
model falls through to the next instead of killing the run. Since #327 each
routine chain carries a multi-model tail, and since #544 every walk **crosses
providers**: a GLM head — three GLM links (glm-5.2 → 5.1 → 4.6) for the four
high-volume routines and for Reeve's sign-off (5.3 → 5.2 → 5.1), one link for
the rest — then an Anthropic tail (claude-sonnet-5 → claude-haiku-4-5), the
workflow's steps in file order — GLM link steps first, then the Anthropic link
steps, each gated on every earlier link not having succeeded and on its own
provider's key — so a whole-provider outage falls through instead of killing
every scheduled run. Under that contract a routine's `.github/<routine>.conf`
`provider:` names the **head** provider: link 1 must sit on it, and the tail
may cross to any other declared provider the workflow carries literal ship
steps for, in the workflow's step order. That shape is one pure rule,
`walk_shape_errors(links, head_provider, layout)` in `registry.py`, which the
resolve step runs as `model-registry shape <chain> --head <conf provider>
--layout <the file's ship-step order>` — `zai,zai,zai,anthropic,anthropic`
for the five-link walks, `zai,anthropic,anthropic` for the three-link ones —
before any key is spent, and which the drift guard runs pre-merge against the
layout it derives from the ship steps' actual wiring — so the runtime check
and the test cannot drift. Every tail leads with Sonnet, not Opus, the
review-tier routines included: the Anthropic account carries a monthly usage
cap, and an unattended fall-through must land on the cheap tier (promoting one
routine's tail to Opus is a one-line `models` edit). Spend note: the four
high-volume routines are where a GLM outage shifts the most spend to Anthropic
while it lasts — the cheap tail is for that reason too, and each run summary
names the link that served and warns when the head provider fell through.
`tests/test_workflow_drift.py` pins the registry and every consumer workflow
together so they cannot silently diverge — its `ROUTINES` table holds one row
per walk (twelve, two of them in `wright.yml`), and every routine pin loops
it — including, since #327, that the expressions reading the walk's *outcome*
cover every link (an expression still on link 1 after a chain deepened would
send a healthy link-2 run red), and since #544 that each link's ship step
wires that link's provider (secret and endpoint, position-derived), that
exactly one ship step exists per link, that every step gates on every earlier
link and on its own provider's key, and that the provider-triage gate
simulates correctly over every link of the walk — each with a negative
control.

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

- `src/model_registry/registry.py` — the parser (fail-loud, stdlib `configparser`),
  the `resolve(chain)` → ordered `ResolvedLink`s, and `walk_shape_errors` (the
  pure cross-provider walk-shape rule, issue #544, shared by `shape` and the
  drift guard).
- `src/model_registry/cli.py` — `check` / `resolve` / `chain` / `show` / `smoke` /
  `classify` / `shape`; `resolve` emits the `$GITHUB_OUTPUT` links a workflow
  consumes, `classify` emits `class` + `reason` for a workflow's exhaustion
  branch, `shape` fails a resolve step whose chain does not fit the walk.
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
the split can't misroute), the walk-shape rule (a fitting chain, a head off the
conf provider, a link on the wrong slot's provider, a chain the walk cannot
carry), and the drift guard that holds `.github/models/registry.conf` and its
consumer workflows in correspondence — including that every chain-walking
workflow stays wired to the shared `.github/actions/provider-triage` action on
its own chain.
