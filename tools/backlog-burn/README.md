# backlog-burn

The selection engine behind the **scheduled backlog burn**
(`.github/workflows/backlog-burn.yml`, issue #95): a nightly routine that
picks **one** open issue and runs `/ship-issue` on it unattended, leaving a
draft PR for human review.

This tool owns the one decision that must be reproducible and testable —
*which* issue — and nothing else. The agentic `/ship-issue` run is the
workflow's job; the off-switch and the live invocation are the workflow's
job. Here lives the policy.

## The policy

From a snapshot of the repo's open issues (plus the open PRs and remote
branches that reveal what is already claimed), `select` returns **at most
one** issue, applying, in order:

1. **opt-in** — the issue must carry the `autonomy-ok` label. Nothing is
   eligible until a human adds it, so the routine ships nothing on the day it
   lands: it waits for a curated backlog. This is the per-issue on-ramp that
   complements the workflow's repo-variable off-switch.
2. **not awaiting a human decision** — excluded if the issue carries the
   `needs-decision` label: an agentic run parked it for a human yes/no (the
   HITL decision gate, issue #161), and it must not be re-selected until
   `/decide` records the verdict and clears the label. This guard is checked
   **before every claim check below** (matching `exclusion_reason`), because
   unlike a SHIP-LOCK the block is *durable* — it never goes stale, since a
   pending decision does not expire, so it must not sit behind the staleness
   logic. See `../../docs/decision-gate.md`.
3. **not already claimed** — excluded if any of the `/ship-issue` §0 lock
   signals hold: an active `🚢 SHIP-LOCK` marker comment (a `WITHDRAWN` one
   releases it), an open PR that closes the issue (any of GitHub's nine
   closing keywords, or a `claude/issue-<N>-*` head branch), or an existing
   remote `claude/issue-<N>-*` branch. A SHIP-LOCK more than a few hours old
   with **no** backing branch and **no** closing PR is a *stale* claim — a run
   that died between posting its lock and pushing — and, exactly as the skill's
   §0.3 takeover rule allows, it does **not** block: otherwise a dead run would
   freeze the issue out of the burn forever, since the skill's own takeover
   only runs for an issue this selector actually hands it.
4. **not freshly declined** (issue #530) — excluded while the thread's
   *latest* `🚢 DECLINED` comment is inside a 24 h cooldown: a run already
   looked at the brief and walked away (a blocking open question nobody has
   answered), so an unanswered decline must not monopolize every hourly
   firing while the runnable briefs behind it starve — #515 measured seven
   declines in three days. Two properties hold by construction: a decline
   **expires, never buries** — after the window the brief is eligible again,
   and each later decline restarts it — and **any owner activity re-arms
   immediately**: a comment newer than the latest decline that is not
   machine-posted makes the brief eligible regardless of the window.
   Because the routines post through the same PAT identity as the owner
   (#515: the declines, the withdrawals and the owner's own answer are all
   one login), "machine-posted" cannot be an author test — it is a first-line
   marker test (`🚢`/`🚦`/`🏷`/`🧩` prefixes) plus GitHub's `Bot` author type.
5. **oldest-first** — among what survives, the oldest issue by creation time
   (tie-broken by number, so the pick is deterministic across runs).
6. **cap of one** — everything past the first eligible issue is deferred to
   the next firing, so a bad night costs one PR, not five.

`select` is a **pure function of the snapshot** — no network — which is what
lets every guard above carry a negative-control test (see
`tests/test_select.py`: remove a guard and its "excluded" assertion fails).
That mirrors the repo's `lib/*-guards.conf` discipline in Python: a policy
that silently stops refusing what it exists to refuse is the failure this
suite exists to catch.

The `/ship-issue` skill re-verifies all of §2 before it touches code, so this
is a best-effort *pre-filter*: its contract is only to never *hand* the run
an issue that is plainly taken, and never more than one.

## Usage

```bash
# Pure policy: snapshot JSON on stdin -> selection record on stdout
backlog-burn select --input snapshot.json

# Live read: build the snapshot from the GitHub REST API (needs GH_TOKEN)
GH_TOKEN=... backlog-burn gather --repo owner/name

# What the workflow runs: gather then select
GH_TOKEN=... backlog-burn run --repo owner/name --label autonomy-ok

# Read the committed policy (what the workflow gates on)
backlog-burn config --get enabled      # -> true|false
backlog-burn config --get label        # -> autonomy-ok
backlog-burn config --get cadence      # -> 4x  (preset name)

# Update a config key (what the backlog-burn-config workflow calls)
backlog-burn config set enabled false
backlog-burn config set label my-label
backlog-burn config set cadence weekly   # preset names: hourly, 4x, 2x, daily, weekly
backlog-burn config set cadence '17 0,6,12,18 * * *'  # raw cron also accepted
```

The `/backlog-burn set` GitHub Actions command (see
`.github/workflows/backlog-burn-config.yml`) is the human interface for the
same operations without a full PR:

```
/backlog-burn set enabled true|false
/backlog-burn set label <label-name>
/backlog-burn set provider anthropic|zai
/backlog-burn set cadence hourly|4x|2x|daily|weekly|<raw-cron>
```

Post the comment (with the leading `/`) on any PR or issue to which you have
write access, or trigger the workflow manually from the Actions tab.  A
`REGEN_TOKEN` PAT with `contents:write` is required to commit the change;
without it the workflow validates the change and tells you what file to edit
by hand.  For `cadence`, both `.github/backlog-burn.conf` **and** the `cron:`
literal in `.github/workflows/backlog-burn.yml` are patched in a single
atomic commit.

`select` and `run` also honour `$GITHUB_OUTPUT` (writes `issue=<n>`, empty
when nothing was selected) and `$GITHUB_STEP_SUMMARY` (a markdown outcome
block), so the workflow stays a few lines of glue.

## Config: where the on/off, label, provider, and cadence live

`.github/backlog-burn.conf` is the **git-tracked source of truth** for the
routine's policy — the same idea as `.github/ci-gates/registry.conf`:

```
enabled: true
label:   autonomy-ok
provider: anthropic   # or: zai
cadence: 4x           # preset: hourly | 4x | 2x | daily | weekly, or a raw 5-field cron
```

`config.py` parses it strictly (a typo'd key, bad value, or unknown provider
fails loudly, so the routine never runs on a policy nobody wrote). The workflow
reads `enabled`, `label`, `provider`, and `cadence` from it.

**Cadence** is stored both in this file (as a human-readable preset name or raw
cron) and as the `cron:` literal in `backlog-burn.yml` (GitHub Actions cannot
read a file or variable for `on.schedule`).  The `/backlog-burn set cadence`
command keeps both in sync.  Preset names:

| Preset | Cron | Fires |
|--------|------|-------|
| `hourly` | `17 * * * *` | Every hour, at :17 |
| `4x` | `17 0,6,12,18 * * *` | Every 6 hours |
| `2x` | `17 6,18 * * *` | Twice daily |
| `daily` | `17 6 * * *` | Once a day |
| `weekly` | `17 6 * * 1` | Mondays 06:17 UTC |

The routine acts only when **both** the committed `enabled: true` **and** the
`BACKLOG_BURN_ENABLED` repo variable agree — the committed file is the
reproducible intent (change it in a reviewed PR or via `/backlog-burn set`);
the variable is the fast, human-only arming/kill switch (not in git on
purpose).

### Choosing the LLM provider

`provider:` selects which PROVIDER the `/ship-issue` walk STARTS on — the
head provider (issue #544) — not which model. Each known provider
(`KNOWN_PROVIDERS`) has explicit ship steps in the workflow — a provider is a
reviewed, git-tracked step because GitHub Actions can only reference a secret
by its literal name, so a runtime label can't pick the secret on its own:

- `anthropic` — Claude via `api.anthropic.com`, secret `ANTHROPIC_API_KEY`.
- `zai` — Z.AI GLM via its Anthropic-compatible endpoint
  (`ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`), secret `ZAI_KEY`
  (the default head).

Which MODEL each link runs is the registry's call (issue #326): the workflow
resolves `[chain:backlog-burn]` from `.github/models/registry.conf` and walks
its links in file order across both providers (three GLM links, then the
Anthropic tail) — the design-run, chunker and labeler siblings each resolve
their own chain the same way — so swapping a model is a registry edit, not a
workflow edit. Link 1 of the chain must sit on the provider this conf names,
and every link must sit on the provider its ship step is wired for; the
workflow's resolve step (`model-registry shape`) checks that before any key is
spent.

Switching is this one line in the config. Adding a new provider is a new ship
step in the workflow plus its label in `KNOWN_PROVIDERS`. Note: `/ship-issue`
is a Claude Code skill and Anthropic doesn't officially support routing Claude
Code to non-Claude models, so non-`anthropic` providers are best-effort and
quality may vary.

## Layout

- `src/backlog_burn/select.py` — the pure policy (tested)
- `src/backlog_burn/github.py` — the thin live GitHub read (stdlib `urllib`)
- `src/backlog_burn/config.py` — the committed-policy parser (tested)
- `src/backlog_burn/cli.py` — `select` / `gather` / `run` / `config`
- `tests/` — pytest; CI runs it when the tool changes

Stdlib-only on purpose (empty `dependencies` in `pyproject.toml`): the
routine runs on the system Python in a scheduled CI job, so a third-party
import would mean a pip step in front of the step that decides what to ship.

## Tests

```bash
pip install -e 'tools/backlog-burn[test]'
python -m pytest tools/backlog-burn/tests -q
```
