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
`review` chain into `model1..model4` outputs, and the Jane/Drik/coach ship steps
read those instead of hardcoding `--model`. `tests/test_workflow_drift.py` pins the
registry and the workflow together so they cannot silently diverge.

## Layout

- `src/model_registry/registry.py` — the parser (fail-loud, stdlib `configparser`)
  and the `resolve(chain)` → ordered `ResolvedLink`s.
- `src/model_registry/cli.py` — `check` / `resolve` / `chain` / `show`; `resolve`
  emits the `$GITHUB_OUTPUT` links a workflow consumes.
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
`$GITHUB_OUTPUT` emission, and the drift guard that holds `.github/models/registry.conf`
and `.github/workflows/auto-review.yml` in correspondence.
