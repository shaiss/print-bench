# The AI andon cord (`AI_ANDON_CORD`)

An andon cord is the rope on a factory line that any worker can pull to stop
the line the moment something is wrong, without asking anyone. This is the
bench's: **one repo variable, `AI_ANDON_CORD`, set to the word `pulled`**, and
every AI-consuming workflow job in the repository is bypassed — grey/skipped,
never red, no provider API call, no `needs-decision` escalation — with exactly
one `::notice::` line per run saying why. Every deterministic job keeps running
unchanged. Release the cord and the AI jobs resume on their next firing.

The reason it exists is the day of 2026-09-04. Both providers ran out of quota
inside a few hours, and the bench — working exactly as designed — turned that
into a wall of red scheduled runs, a failure email per firing, and **seven**
per-chain `🚦 Provider unusable` escalation issues (#554–#558, #560, #562)
filed within seventeen hours, one per chain that walked to exhaustion. None of
that noise was wrong; all of it was the same fact restated by twelve routines.
What was missing was one control that says *"I know — stop trying"* and greys
everything out at info level until a human says otherwise. The arming variables
are the wrong tool for that: there are twelve of them, each halts one routine,
and none of them touches the reviewers, the Oracle, CI's product-page drafting,
the image generators or the model smoke. The cord sits above all of it.

## Pulling and releasing it

**Pull:** Settings → Secrets and variables → Actions → Variables → new variable
`AI_ANDON_CORD` with the value `pulled`. The comparison is GitHub's own
case-insensitive string compare, so `Pulled` and `PULLED` pull it too; it is
the exact word, so a trailing space or a different word (`true`, `yes`, `on`)
does **not** — the cord is the word, not a boolean.

**Release:** delete the variable, or set it to anything but `pulled`. An unset
variable is the released state, so a fresh clone, a fork, or a repo that has
never heard of the cord behaves exactly as before — released is fail-open by
design, the opposite of the fail-closed two-key arming.

**When it takes effect:** on the next firing of each workflow. A run already in
flight when the variable changes is not interrupted — `vars` is read when a job
is evaluated, and a job that already started keeps going — so a pull lands
within one firing interval (an hour for the burn and the design run, a day for
most of the rest, the next PR event for the reviewers). Same for release.

**Making it visible:** the reconciler workflow (`Andon cord status (AI
bypass)`, `.github/workflows/andon.yml`) records the state as a sticky issue
within the hour; dispatch it from the Actions tab right after pulling or
releasing to stamp (or close) the issue immediately.

## What the cord covers

Every job that can spend a provider key, run an agent, or escalate a provider
failure carries the gate leg `vars.AI_ANDON_CORD != 'pulled'` at **job level**
(the one exception is CI's product-page step, gated at step level because its
`regen` job is a required-context dependency). Job-level gating is the point:
nothing inside a gated job runs while the cord is pulled — not the keyless
Select and resolve steps, not the provider-triage probe that files
`needs-decision` escalations, not the "turn red" tail steps. A skipped job is
mute, so each workflow has a keyless sibling (or an inverse-gated step) that
emits the one notice.

| Workflow | Bypassed | Who says so |
|---|---|---|
| `backlog-burn.yml` | the `burn` job (the burn did not run) | `disarmed-notice` — cord message first, then the disarmed/off-branch messages only when the cord is released |
| `design-run.yml` | the `run` job | `disarmed-notice` |
| `chunker.yml` | the `chunk` job | `disarmed-notice` |
| `labeler.yml` | the `label` job — untriaged issues wait; the loop's front door pauses | `disarmed-notice` |
| `product-scout.yml` | the scout job — no briefs filed | `disarmed-notice` |
| `spike-converter.yml` | the `convert` job — decided recommendations wait | `disarmed-notice` |
| `adoption-assessor.yml` | the `assess` job — filed studies wait for their draft verdict (a human can still disposition by hand) | `disarmed-notice` |
| `growth-twitter.yml` | the drain — no dry-run comment, no live post, the per-UTC-day cap guard does not run; queued items simply wait | `disarmed-notice` |
| `reeve-growth.yml` | the queueing job and its dedup-context steps — nothing queued | `disarmed-notice` |
| `wright.yml` | **both** agent jobs, propose and sign-off | `disarmed-notice` |
| `reeve.yml` | the `greenlight` drafter job only; `report` and `observe` keep running | `disarmed-notice` (cord message wins even if `REEVE_ENABLED` is also unset) |
| `backlog-groomer.yml` | the two narrative steps only — the report still renders, upserts and publishes; the summary reads "narrative layer (skipped)" | the `Note an andon-paused narrative` step |
| `auto-review.yml` | Jane, Drik, PM triage and the design coach; `design-changes`, `review-stamp` and `signoff-status` keep running | `review-stamp` posts a `⏸️ Auto-review bypassed` comment (no `sha=` marker) and the workflow's one notice |
| `oracle.yml` | the `oracle` job — no probe, no classify, no #347 escalation | the keyless `oracle-andon` sibling; neither runs on a PR labeled `no-oracle-review` |
| `ci.yml` | the `Draft product pages that do not pass their gate (Claude API)` **step** of `regen` — previews, animations, product shots, the gallery and the commit-back all still run | the `AI andon cord — product-page drafting bypassed` step (only when the PR touched designs; a docs-only PR shows no cord notice in CI at all) |
| `lifestyle-shot.yml`, `product-still.yml`, `lifestyle-clip.yml` | the `generate` job (the only `ZAI_KEY` spend), manual dispatch included; `detect` still runs its deterministic input validation | the `andon-notice` sibling |
| `model-smoke.yml` | the `smoke` job on both its paths (a registry-touching PR and a dispatch) | the `andon-notice` sibling |

## What keeps running

Everything deterministic, unchanged and un-noticed: the CI gates (`render-gate`,
printcheck, the test-slice, `readme-gate`, every `*-tests` job, `check.sh`),
`regen`'s preview/animation/product-shot/gallery regeneration and its
commit-back, the `geo-diff` and site builds, Reeve's bench-health `report` and
its `observe` learning job, the groomer's deterministic report, the telemetry
roll-up, the decide command (`decide.yml`), the release bundles, the security
scan, the avatar and the two Projects-board syncs (`growth-board-sync.yml`,
`roadmap-sync.yml`), auto-arm, the config and ci-gate comment commands, the
print-result logger — and the reconciler itself, which must run while the cord
is pulled to open the status issue and while it is released to close it.

## The noise contract

- **Grey, never red.** A bypassed job is *skipped*; no job goes to failure
  because the cord is pulled, and `ci-ok` treats a classifier-skipped test job
  as green exactly as before.
- **One `::notice::` per bypassed run**, no `::warning::`, no `::error::`. Two
  known exceptions, both pre-existing and deterministic: the three image
  workflows also print their #302 `ai-lifestyle.conf enabled != 'true'`
  notice from `detect` while that conf is off (it is today), so a cord-pulled
  run there shows two notices; and `design-changes` in `auto-review.yml` keeps
  its own diagnostic notices.
- **No escalation.** The provider-triage composite (the step that files
  `needs-decision` escalations) lives inside the gated jobs, so a pulled cord
  can never open a new `🚦 Provider unusable` issue.
- **No provider call.** Not even the 1-token classify probe: the diagnose step
  is unreachable.
- **The cord's own writes** are exactly these: the status issue, opened once on
  the first observed pull and closed once on the first observed release;
  Reeve's daily report line; and, on a design PR that fires a review round,
  the stamp comment and the `reviewer-signoff` status the workflow would have
  written anyway — the cord only changes their text.

## The status issue

A skipped job is mute, so nothing in the Actions tab says *when* the cord was
pulled or for how long. `andon.yml` — hourly at :43 UTC and on
`workflow_dispatch` (with a `dry_run` input that prints the decision and
writes nothing) — is that record. It is keyless, conf-less, holds
`issues: write` on its one job, pins itself to the default branch, and is
deliberately **not** in `cadence-sync-check.sh`'s twelve-routine roster (the
`growth-board-sync.yml` precedent: a lightweight reconcile, not an armed
routine). It is also **never gated on the cord** — the tool's tests pin the
absence of the gate leg on its job.

| Observed | Open status issue? | Action |
|---|---|---|
| pulled | none | open **one** issue: `🛑 AI andon cord pulled — AI usage bypassed`, labels `andon-cord` (red) + `notice`, body starting with the `<!-- andon-cord -->` marker |
| pulled | open | nothing — "still pulled since \<opened_at\>" |
| released | open | comment the observed timespan ("about 3 days 4 hours"; "under an hour"; never negative) and close it, `state_reason: completed` |
| released | none | nothing |

A re-pull opens a **new** issue, so the closed `andon-cord` issues are the
episode history. Both labels are created idempotently on first use. The issue
never carries `needs-decision` (that label parks the autonomy selector and
would make a pulled cord look like a decision request), and the labeler's
sweep excludes `andon-cord` (`NON_TRIAGE_LABELS` in `label-helper.sh`) so no
routine can route the status record. Timestamps on the issue and in the
closing comment are **observation** times at hourly granularity, not the
moment the variable changed — dispatch the workflow to stamp or close it now.
If you close the status issue by hand while the cord is still pulled, the next
hourly run opens a fresh one: release the cord instead. Every decision and every
rendered byte comes from `tools/andon` (pure, GET-only, stdlib-only); the
workflow's `github-script` step is the single write.

## The Reeve banner

Reeve's deterministic bench-health report keeps running under the cord, and
that is where a reader of the sticky `reeve-report` issue learns the many
skipped AI runs are intentional rather than a dead routine: `reeve.yml` hands
the report job the variable's raw value (`reeve run --andon "$AI_ANDON_CORD"`,
env-indirected, never inline), and the report carries one `🛑` banner line
directly under its H1 while the cord is pulled — released renders today's
bytes exactly, pinned by the golden pair in `tools/reeve/tests/fixtures/`.
Downstream readers of that report (Wright's `pulse`, `/bench-audit`) should
read the banner as "the skipped runs are expected": a pulled cord is not
`routine-dead`, and not a gap for Wright to propose an agent to heal.

## What the cord does not do

- It does **not** close the seven open `🚦 Provider unusable` escalations, or
  any other issue. The cord silences the symptom; it does not change the credit
  state. Fund the account, rotate the key, or close the escalations by hand.
- It does **not** fix a quota. Release it before the reset and the routines
  will walk their chains to exhaustion again.
- It does **not** stop a human-dispatched deterministic job — a dispatched
  release bundle, avatar, print-result log or config update runs as always.
  (A dispatched *AI* job is bypassed: the image generators and the model smoke
  go grey even by hand.)
- It does **not** touch the arming variables or any `.github/*.conf`. It
  overrides an armed routine without disarming it, and releasing it restores
  exactly the arming that was there.
- On a fork or clone it is unset — released. It carries nothing across.

## Design PRs under the cord

The reviewers are AI, and the required `reviewer-signoff` commit status is
fail-closed by design (the sweetheart-hamster lesson). So, with the cord
pulled:

- `scripts/reviewer-signoff.sh --andon true` **BLOCKs** a design PR that lacks
  two clean, *current* sign-offs, with the status description `andon cord
  pulled — reviews bypassed; release the cord or add signoff-override`. Once
  that status is armed as a required check, no such PR can merge until the
  cord is released and a round runs, or a maintainer applies
  `signoff-override` (or `no-auto-review`).
- Sign-offs that already happened still **PASS**: a review that ran is a fact
  about the design tree (same head, or the same `designs/` tree), and the cord
  stops AI consumption, not merging. Pushing a `designs/` change while pulled
  goes stale → BLOCK with the andon description. Non-design PRs pass
  unaffected.
- The `review-stamp` comment carries no `sha=` marker, so the round is *not*
  marked reviewed. After release, **any push** (docs-only included) re-fires a
  full round; or **close and reopen** the PR — the one gesture that also
  re-fires the design coach (it runs only on opened/ready_for_review/reopened)
  and the Oracle. A PR opened while the cord was pulled gets its coach only
  that way.
- `design-changes` is deliberately *not* gated: its `designs_changed` output
  is what keeps `signoff-status` fail-closed. A skipped `design-changes` would
  read as "no design changes" and the cord would *open* the required gate.
- Masking: a pre-existing real problem (a block verdict, a malformed marker,
  an unacknowledged fuse warning) that is still current is reported with the
  andon text instead of its own reason while the cord is pulled — release the
  cord to see the underlying reason.
- Under the cord a design's product page is not auto-drafted, so a README that
  already fails `readme-gate` stays red on `Design product pages` until the
  cord is released and CI re-runs (or a human writes the page).

## Collateral to know

- **A 👍 waits.** The greenlight loop's keyless approval poll lives inside the
  skipped `greenlight` job, so a thumbs-up on a prior greenlight is not
  applied while the cord is pulled — it waits, unlost, and is polled on the
  first run after release.
- **An orphaned SHIP-LOCK stands.** The per-run lock cleanup is inside the
  gated burn/design-run job, so a lock left by a run that died right before
  the pull stays until release; Reeve's `lock-leak` detector still surfaces
  it, and no new lock is ever posted while pulled.
- **Label bootstraps skip with their jobs.** Wright's idempotent `agent-brief`
  label creation and growth-twitter's `approved-to-post` one run inside the
  gated jobs; on a repo that has never had an armed run, a form-filed brief
  could drop its label if the cord is pulled first.
- **`observe` un-couples from the report.** While pulled, Reeve's `observe`
  no longer inherits a `report` failure through `greenlight`'s skip, so it
  runs even when the report failed — harmless, it never reads `report.md`.
- **A registry edit ships unproven.** `model-smoke` is skipped, so a chain
  edit merged under the cord has not been live-proven; dispatch `Model chain
  smoke` after release.
- **Product-page drafting resumes on the next `regen`** that touches the
  design.
- **Re-running a cord-time run** from the Actions UI after release is expected
  to read the released value (`vars` is run-time context) but is not provable
  from the repo — verify on the first live release; the guaranteed paths are a
  push or close-and-reopen.

## How it is enforced

- The **drift-guard coverage test** in `tools/model-registry`
  (`tests/test_workflow_drift.py`): a job is AI-consuming iff its block spends
  a provider secret (`ANTHROPIC_API_KEY`, `ZAI_KEY`, `CLAUDE_KEY` — presence
  probes excluded) or runs the claude-code-action or the provider-triage
  composite, enumerated over the workflows rather than a hand-kept list, so a
  future AI job is enrolled the moment it references a key; every such job
  must carry the gate leg as the last folded line of its `if:` (the two
  step-gated exceptions, `ci.yml`'s `regen` and the groomer's `groom`, must
  carry it on each key-spending step), every workflow with one must emit a
  `::notice::` on the explain leg, a hand roster (`ANDON_AI_JOBS`) catches a
  silent shrink or grow of the set, and a sanity pin proves `andon.yml` is
  neither AI-consuming nor corded. Four tamper negatives prove the guard can
  fail: a job that shed its leg, a future uncorded AI job, a workflow that
  stopped explaining, a step-gated job that shed its step leg. Because it pins
  the cord across every workflow, `ci-classify.sh` now selects
  `model_registry_tests` on **any** `.github/workflows/*` edit.
- `tools/andon`'s own suite (`andon_tests`, wired into `ci-ok`) pins the
  reconciler's shape: marker/label/title parity between the workflow's script
  literals and `andon.policy`, the default-branch pin, `issues: write` on the
  job, the single cron literal, no `secrets.` anywhere, the `--cord "$CORD"`
  env-indirection, and the *absence* of the gate leg on the reconcile job. A
  purity scan holds the package write-free with zero exemptions.
- `scripts/reviewer-signoff.sh --selftest` (run by `check.sh`) pins the BLOCK
  description byte-for-byte, plus a negative control that the released path
  never blames the cord and rows proving clean sign-offs and the label hatches
  still pass under it.
- Reeve's golden pair pins the banner: `report.andon-pulled.golden.md` is the
  pulled rendering, and `report.golden.md` is asserted equal to the released
  one.
- The case rule is structural: every workflow compares
  `vars.AI_ANDON_CORD == 'pulled'` in the expression layer and hands bash only
  a `true`/`false` string (`ANDON`, `ANDON_PULLED`, `--andon`), so GitHub's
  comparison is authoritative everywhere and the variable's value is never
  interpolated into a `run:` block.

## Why a repo variable, not a committed file

N4 says the reproducible source of truth lives in git and a repo variable may
only *enable or disable* committed policy, never define it. The cord is exactly
that shape: it defines nothing — the policy (which jobs are AI-consuming, what
the bypass does) is committed in every workflow and pinned by the drift guard —
and it only switches that policy on or off. A committed file would be the wrong
speed: when the account is out of credit at 01:00 the fix must not be a PR that
waits for CI, a review and a merge, and the default-branch ruleset blocks a bot
commit to `main` anyway. A variable is one human, one form, seconds — the same
reasoning as the `*_ENABLED` arming variables, applied once for the whole
machine.

## Failure modes

| Failure | What happens | Recovery |
|---|---|---|
| A typo'd value (`pull`, `pulled `, `true`) | Released. Nothing is bypassed and no status issue opens — the absence of the issue within the hour is the tell | Set the exact word `pulled` |
| Set on a fork | Bypasses that fork's own AI jobs only (it has no secrets to spend anyway); nothing reaches upstream | — |
| A run already in flight | Finishes as it would have; only the next firing is bypassed | Wait one firing, or cancel the run by hand |
| The hourly lag | A pull is recorded within about an hour; after release the issue closes within about an hour. Meanwhile the AI jobs are already bypassed/resumed — the issue lags, it never lies | Dispatch `Andon cord status (AI bypass)` to stamp or close now |
| Two notices in the image workflows | The #302 conf-off notice from `detect` plus the cord's | Expected while `ai-lifestyle.conf` is off |
| The reconciler itself dies | No issue opens or closes; the bypass is unaffected because every gate reads the variable, not the issue | Read the variable; re-dispatch the reconciler |
| Someone closes the status issue while pulled | The next hourly run opens a fresh one | Release the cord instead |
| More than one open issue carries the marker | The tool uses the oldest and logs a stderr warning naming the others (never the reconciler's doing) | Close the extras by hand |
| A design PR must merge during a pull | `reviewer-signoff` blocks it | Release the cord, or apply `signoff-override` |
| The cord is released before the quota resets | The routines walk their chains to exhaustion again and the (deduplicated) escalations re-fire | Pull it again; the closed status issues keep the history |
