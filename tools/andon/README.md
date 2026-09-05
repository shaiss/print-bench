# andon — the AI andon cord's status-issue reconciler

The AI andon cord ([docs/andon-cord.md](../../docs/andon-cord.md)) is one
repo variable, `AI_ANDON_CORD`: set to `pulled`, it bypasses every
AI-consuming workflow job in the repository — grey/skipped, never red, no
provider API call, no `needs-decision` escalation. A skipped job is mute,
though, so nothing in the Actions tab says *when* the cord was pulled or for
how long. This package is that record: a pure, tested, stdlib-only tool that
decides — from the variable's raw value and one GET of the open issues —
whether the hourly `andon.yml` workflow should open the sticky status issue,
close it, or do nothing, and renders every byte the workflow writes.

## Lifecycle

| Observed state | Open status issue? | Decision |
|---|---|---|
| pulled | no | **open** — the first observation of a pull opens ONE issue (label `andon-cord` + `notice`, body starting with `<!-- andon-cord -->`) |
| pulled | yes | none — "still pulled since \<opened_at\>"; the issue stands |
| released | yes | **close** — the first observation of release comments the observed timespan and closes the issue |
| released | no | none — steady state |

A re-pull opens a **new** issue, so the closed `andon-cord` issues are the
episode history. Timestamps are *observation* times at the reconciler's
hourly granularity (it runs hourly at :43 and on `workflow_dispatch` —
dispatch it after pulling or releasing to stamp the issue immediately), not
the moment the variable changed. The reconciler itself is **never** gated on
the cord: it has to run while pulled (to open) and while released (to close).

## CLI

```bash
export PYTHONPATH=tools/andon/src          # or: pip install -e 'tools/andon[test]'

# The workflow's step. Reads GH_TOKEN/GITHUB_TOKEN (empty = unauthenticated
# GET), appends action=/issue_number=/pulled=/opened_at= to --gh-output,
# writes <out-dir>/body.md on open or <out-dir>/comment.md on close.
python3 -m andon decide --repo owner/name --cord="$AI_ANDON_CORD" \
    --gh-output "$GITHUB_OUTPUT" --out-dir .andon

# Offline (no GET; the status issue is treated as absent) — for demos/tests.
python3 -m andon decide --offline --repo owner/name --cord=Pulled --out-dir /tmp/andon

# The rendered text on its own.
python3 -m andon render-open  [--now 2026-09-01T10:00:00Z]
python3 -m andon render-close --since 2026-09-01T10:00:00Z [--now ...]
```

`--cord` takes the variable's **raw** value and compares it exactly the way
GitHub's expression `vars.AI_ANDON_CORD == 'pulled'` does — case-insensitive,
**no whitespace trimming**: the exact word — so `Pulled` and `PULLED` pull it,
while `pulled ` (trailing space), ` pulled`, an unset variable, `released`,
`false` or `true` all read as released (the cord is the *word*, not a
boolean). The no-trim rule is deliberate, not an omission: GitHub's own
comparison does not trim, so a padded value leaves every workflow gate
released and the AI jobs running; a tool that forgave the padding would open
the status issue and banner a bypass that is not happening — a split brain.
Pass it as `--cord="$CORD"` (the `--opt=value` form) so a value that happens
to start with a dash cannot be mistaken for an option. Exit 0 on any
decision (a `none` is not an error), 1 on a configuration error (a bad ISO
timestamp; `--repo` missing without `--offline`), 2 on an argparse error.

## Modules and the purity rule

* `policy.py` — **pure** (no I/O; imports neither `os` nor `urllib`): the
  constants (`MARKER`, `LABEL`, `NOTICE_LABEL`, `TITLE`, `VARIABLE`),
  `is_pulled`, the four-branch `decide`, and the renderers
  (`render_open_body`, `render_close_comment`, `format_duration`).
* `github.py` — the **only** module allowed to import `urllib`: the
  groomer's `_get`/`_paged` seam (fail-loud page cap, non-list guard) and
  `find_open_status_issue` (open issues with the label, PRs dropped,
  marker-less bodies dropped, oldest wins, more-than-one logged to stderr).
  `_get` stays the single one-request seam the tests monkeypatch;
  `_get_with_retry` wraps it with up to three attempts and a short backoff
  (`_RETRY_DELAYS`, slept through `time.sleep` so tests can stub it) **only**
  on a transient blip — an HTTP 403/429/500/502/503/504 (GitHub's
  secondary-rate-limit 403 included) or a `URLError`/socket timeout — so the
  hourly keyless reconciler does not go red on every API hiccup. Any other
  HTTP status (401, 404, 422 …) is a real error and is re-raised on the
  first attempt; after the last attempt the transient error is re-raised.
* `cli.py` — argparse over the two.

The package **never writes to GitHub** — its only writes are local scratch
(`<out-dir>/body.md` / `comment.md` and the `KEY=VALUE` lines appended to
`--gh-output`, both consumed by the workflow's write step). `tests/test_purity.py`
holds the network half checkable: an
AST import scan (only `github.py` may import anything network-capable) and a
word-bounded scan for HTTP write verbs over every `*.py` in the package —
comments and docstrings included, **zero exemptions** (the backlog-groomer's
shape, minus its narrative carve-out: this package has no model call). The
single GitHub write — create the issue, or comment on and close it — lives in
a `github-script` step of `.github/workflows/andon.yml`, driven by this
package's decision and rendered files, so the write surface is one reviewed
workflow step and the tool scans clean. `tests/test_workflow.py` pins that
workflow to the tool: the script's `MARKER`/`LABEL`/`NOTICE_LABEL`/`TITLE`
literals equal `policy`'s constants, the reconcile job carries the
default-branch pin and **no** cord leg, `issues: write` sits on the job with
a `contents: read` workflow default, exactly one `- cron: '43 * * * *'`, no
`secrets.` anywhere, and the decide step is invoked with
`--gh-output "$GITHUB_OUTPUT"` and `--cord="$CORD"` (env-indirected, never
interpolated into a `run:` block; the `--opt=value` form so a dash-leading
value is never read as an option). The workflow also carries a keyless
`offbranch-notice` sibling — `permissions: {}`, no `issues:` grant — that
runs only when a dispatch targets a ref other than the default branch, so
the reconcile job's default-branch pin is a visible no-op rather than a
mute, fully-skipped run; the pins hold that sibling to zero permissions.

## Labels

* `andon-cord` (red, `b60205`) — the status issue's finder label, created
  idempotently by the workflow on first use.
* `notice` (`bfdadc`) — informational only; one alert when opened, one when
  closed.

Never `needs-decision`: that label parks the autonomy selector and would
make a pulled cord look like a decision request.

## Tests

```bash
PYTHONPATH=tools/andon/src python3 -m pytest tools/andon/tests -q
```

A positive and a negative control per rule: `is_pulled` variants (case
folded, whitespace-padded values rejected exactly as GitHub rejects them),
all four `decide` branches, marker-first bodies, duration formatting
(clamped, never negative), the seam's pagination cap and non-list guard, the
retry wrapper (a 503 twice then success returns; a 401 raises on the first
call; three 503s raise after three calls), the CLI's outputs
and exit codes, the purity scans, and the workflow pins — each pin with a
tamper negative where the regex is cheap to invert. Stdlib-only, like
`tools/lineage` and `tools/reeve`: the workflow runs it straight from the
checkout with no pip step.
