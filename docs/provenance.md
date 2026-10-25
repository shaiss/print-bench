# Design provenance — the keyless who/how harvester

The design of record for `tools/provenance`, `.github/workflows/provenance.yml`,
`.github/provenance.conf`, the `provenance` and `provenance-site` data refs and
the closed contract `site/lib/provenance-contract.json`. Written for the
builders who implement it and for the owner who rules on it.

**Status.** P0 (evidence writer, tip continuity, run receipts, the #843
snapshot ingest) and P1a–e (fixtures and contract, extraction and episodes,
the serving-model join, views and the bundle, workflow wiring and
registration) are being built against this document. Arming the schedule
(P2) and every site change (P3) are out of scope and separate owner calls.
The approved plan this freezes is the red-teamed proposal recorded in the
2026-10-13 provenance audit (`audits/provenance-2026-10/README.md`); where
this document resolves something the plan left open, §Resolved questions
says what and why. It was revised once more after an adversarial review of
the frozen design (2026-10-14; items 22–33 of §Resolved questions).

**The deadline moved.** The #843 snapshot was merged to main on 2026-10-14
(merge commit `411a7565`), so every run created up to 2026-10-13T06:13:35Z is
durable in main's history whatever GitHub's retention does. P0 no longer
races the 2026-10-30 expiry of the first runs; the real deadline is for runs
created after the snapshot, the first of which expire about **2027-01-11**.
And the ingest's scope decisions (no check runs; only the nine watched
workflows) became reversible: a later ingest version can widen them from the
same committed snapshot.

## Contents

1. [Purpose](#purpose)
2. [Architecture](#architecture)
3. [Freeze units and settle rules](#freeze-units-and-settle-rules)
4. [Storage: the two refs](#storage-the-two-refs)
5. [The add-only guard](#the-add-only-guard)
6. [Tip continuity](#tip-continuity)
7. [The evidence digest](#the-evidence-digest)
8. [raw@1 payloads](#raw1-payloads)
9. [Receipts](#receipts)
10. [INGEST: the #843 snapshot](#ingest-the-843-snapshot)
11. [Capture sequences](#capture-sequences)
12. [Records and events](#records-and-events)
13. [Membership](#membership)
14. [Episodes](#episodes)
15. [Serving-model join](#serving-model-join)
16. [Trust tiers](#trust-tiers)
17. [Views, bundle and the derived tree](#views-bundle-and-the-derived-tree)
18. [Canonical JSON and the sort key](#canonical-json-and-the-sort-key)
19. [API budget and pacing](#api-budget-and-pacing)
20. [Conf keys](#conf-keys)
21. [Workflow](#workflow)
22. [Registration](#registration)
23. [Sizes](#sizes)
24. [Failure modes](#failure-modes)
25. [Out of scope (v2 and later)](#out-of-scope-v2-and-later)
26. [Resolved questions](#resolved-questions)
27. [Acceptance map](#acceptance-map)

## Purpose

A visitor should be able to see **who** made a design and **how**: the brief
and the routine that filed it, the routine and model that built it, every
review round, which reviewer sign-offs are trustworthy, when it merged and
deployed — for every design, with no per-design work. The audit measured that
the record exists on GitHub but almost none of it reaches the site, nothing
in CD captures it, and since 2026-10-01 GitHub deletes the Actions records
that hold the "how" (job steps, check runs, commit statuses) after 90 days.

The harvester is the CD half of the fix: a keyless, deterministic job that
reads GitHub (GET only), freezes structured facts once after a settle window,
and writes them to two data refs in git. The site (P3, later) reads one
SHA-pinned bundle from the derived ref at deploy time.

Constraints it honours (audit design brief, "hard constraints"):

| # | Constraint | How |
|---|---|---|
| N1 | CI writes everything derived | a workflow writes both refs; nothing is hand-committed |
| 2 | no workflow can push to main | nothing is written to main |
| 3 | owner option C — writes under `designs/` re-open review | nothing is written under `designs/` |
| N4 | data lives in git a clone carries | two data refs plus a committed conf and contract |
| N5 | no model-invented text on the site | no LLM anywhere; bodies are digested at capture; only structured fields and committed human-merged text reach the bundle |
| 6 | the AI andon cord | keyless: no provider secret, no claude-code-action, no cord gate leg — it keeps recording while the cord is pulled (the `andon.yml` precedent) |
| 8 | telemetry-branch parity test | the telemetry branch is not touched |
| 9 | every data-branch push makes a Vercel preview | both refs carry the shared in-tree guard (`.github/data-branch-guard/`) |
| 10 | a schedule must be watched | Reeve `ROUTINE_WORKFLOWS` and `cadence-sync-check.sh` |
| 11 | marker trust = author + anchored suffix | an exact port of `scripts/reviewer-posted.sh` / `coach-lock-check.sh` |
| #646 | the harvest is a read lens, never a policy store | `test_read_lens.py` |

## Architecture

```text
                GitHub REST (GET) + one read-only GraphQL query
                                  │
     ┌────────────────────────────┴───────────────────────────┐
     │  provenance.yml  (keyless, GITHUB_TOKEN only)          │
     │  gate job ─► harvest job (concurrency provenance-writer)│
     │   1 token-less fetch: both refs + every PR head         │
     │   2 tip continuity (newest tip-<ref> checkpoint)        │
     │   3 ingest the #843 snapshot from main (first run only) │
     │   4 receipts pass (watched workflows' runs → jobs)      │
     │   5 freeze pass (settled PRs / briefs / releases)       │
     │   6 add-only evidence commit + diff-tree guard          │
     │   7 derive records → views → bundle (pure, no fetch)    │
     │   8 plan.json + intents → upload intent artifacts       │
     │   9 publish: ff push provenance, then lease push -site  │
     │  10 upload tip-<ref>-<sha> checkpoints; verdict         │
     └───────────┬───────────────────────────────┬────────────┘
                 ▼                               ▼
   refs/heads/provenance               refs/heads/provenance-site
   EVIDENCE · linear · add-only         DERIVED · one squashed commit
   receipts/ raw/ state.json            records/ views/ site/bundle.json
                 │                               │
                 └── tip continuity: each tip must be the newest ──┘
                     checkpoint a default-branch run uploaded, or a
                     commit a later run declared on top of it
                                                 │
                                   site (P3): SITE_FETCH_PROVENANCE seam
                                   reads site/bundle.json at a pinned sha
```

Five parts, kept separate on purpose:

1. **Capture** — `provenance.yml` freezes structured facts once, after a
   settle window.
2. **Evidence** — the add-only `provenance` branch: run receipts, digested API
   payloads, the ingested snapshot, `state.json`.
3. **Derived** — the squashed `provenance-site` ref: records, per-design
   views and one bundle, recomputed as a pure function of (evidence tip, main
   sha, extractor version).
4. **Tip continuity** — both refs' tips must be the newest checkpoint a
   default-branch harvester run uploaded (or a commit a later run declared
   on top of it); anything else is refused (evidence) or overwritten
   (derived) and reported.
5. **The site seam** (P3, not in this build) — reads the bundle by sha.

## Freeze units and settle rules

Late activity never mutates a frozen unit. A unit is captured **once** into
revision 1; revision K ≥ 2 is added only by `refreeze` or when the unit's
terminal state changes (a PR closed unmerged, reopened and merged; a brief
reopened and closed again); every reader folds the highest revision.

| Unit | Due | Freezes when | Stored |
|---|---|---|---|
| Run receipt | as soon as the runs list shows it `completed` | `conclusion != skipped`, workflow ∈ `watched_workflows` | `receipts/YYYY/MM/DD/<run_id>.a<attempt>.json.gz` (full or stub, §Receipts) |
| PR | `closed_at + settle_hours` (6 h) | at/after due, **and** no watched run on its head branch is queued/in progress, **and** (merged) its Production deployment is terminal or `merged_at + deploy_wait_hours` (2 h) passed. Otherwise deferred; at `closed_at + max_defer_hours` (24 h) frozen anyway with `incomplete` naming why. A frozen PR whose listed `closed_at`/`merged_at` differ from its stored revision's goes through settle again and freezes the next revision | `raw/pr/<n>.json.gz` (`raw-pr@1`) |
| PR with no `designs/` file | — | never captured; re-evaluated if its `closed_at` changes | `state.skipped.pr[n] = {closed_at}` |
| Brief issue (carries, or carried, `design-brief`) | `closed_at + settle_hours` | as a PR; an OPEN brief a frozen PR links is captured as revision 1 with `incomplete: brief-open` and captured again (next revision) once its `state`/`closed_at` change and it settles. A linked issue that never carried the label is not a brief | `raw/brief/<n>.json.gz` (`raw-brief@1`) |
| Release | on publish (non-draft) | immediately | `raw/release/<tag>.json.gz` (`raw-release@1`) |
| Direct-to-main commit | — | derived from local git; no API; only a first-parent main commit with no PR subject, not committed by GitHub, in no frozen PR (§Records) | `records/commit/<sha40>.json` only |

**Admission and isolation** (`freeze.plan_freezes`). Every raw document
passes `contract.validate` before it is planned: a PR or brief that fails
stays pending with reason `contract-invalid` (a PR's linked briefs are held
with it), so nothing invalid ever reaches the add-only ref; a failing release
is skipped and retried by the next listing; `refreeze` raises
`ContractInvalid` (exit 1). An API refusal while considering one unit — the
`designs/` files check, the pending re-reads, a capture — holds only that
unit pending as `capture-failed` and the pass continues. Only 404/410/422 on
an optional section (a sha's statuses, a deployment's statuses) count as
gone; any other refusal fails the unit, which is retried. `refreeze` needs an
already-frozen PR (`RefreezeRefused`, before any request); a first capture is
`harvest pr=<n>`.

Revision paths: revision 1 is `<key>.json.gz`; revision K ≥ 2 is
`<key>.r<K>.json.gz`. Which units are frozen, at which revision, is read
from these paths (`state.frozen_from_paths`) — never from `state.json`, so
the two cannot drift. Settle times derive from `closed_at` (no wall clock is
stored); `now` is read once by `cli.py` and passed down.

## Storage: the two refs

Both refs are unprotected branches pushed with `GITHUB_TOKEN` by
`provenance.yml` only (the telemetry vehicle, #481). Every `on.push` in the
repository is filtered to main or tags, so pushes to the data refs trigger no
workflow.

### `provenance` — evidence, linear, add-only

| Path | Contents |
|---|---|
| `vercel.json` | bytes of `.github/data-branch-guard/vercel.json` at bootstrap (mode 100644); never rewritten |
| `scripts/vercel-ignore-build.sh` | bytes of `.github/data-branch-guard/vercel-ignore-build.sh` at bootstrap (mode 100755); never rewritten |
| `README.md` | generated at bootstrap from a template in `gitstore.py` ("evidence data branch — never hand-edit; see docs/provenance.md"); never changed after |
| `FORMAT` | `print-bench-provenance 1\n` |
| `state.json` | `state@1` — cursors, pending units, skipped PRs (with `closed_at`), ingest records, versions. No wall-clock stamp, no frozen list (the `raw/` paths are the record). The only path a push may modify |
| `receipts/YYYY/MM/DD/<run_id>.a<attempt>.json.gz` | `receipt@1`, day-sharded by the run's `created_at` (≤ ~230 entries per day directory, measured) |
| `raw/pr/<n>[.r<K>].json.gz` | `raw-pr@1` |
| `raw/brief/<n>[.r<K>].json.gz` | `raw-brief@1` |
| `raw/release/<tag>.json.gz` | `raw-release@1` |
| `raw/snapshot/<id>/runs/ci.yml.json.gz` | `raw-snapshot-runs@1` (from the #843 ingest) |
| `raw/snapshot/<id>/statuses/<sha40>.json.gz` | `raw-snapshot-statuses@1` (from the #843 ingest) |

Every `*.json.gz` is deterministic gzip (mtime 0, empty filename, level 9) of
canonical JSON (§Canonical JSON). Content identity — the writer's
same-content no-op, the ingest's identical-vs-conflict test, receipt parity
and `evidence.raw_sha256` — is defined on the **decompressed** canonical JSON;
the gzip bytes are storage only, because deflate output differs between zlib
builds (a runner image's and a builder's Python need not agree). Each publish
is one commit whose parent is the fetched tip, pushed fast-forward only.

### `provenance-site` — derived, squashed

| Path | Contents |
|---|---|
| `vercel.json`, `scripts/vercel-ignore-build.sh` | the same guard bytes |
| `FORMAT` | `print-bench-provenance-site 1\n` |
| `records/pr/<n>.json` | `record@1` kind `pr` (canonical JSON, not gzipped) |
| `records/brief/<n>.json` | `record@1` kind `brief` |
| `records/commit/<sha40>.json` | `record@1` kind `commit` |
| `records/release/<tag>.json` | `record@1` kind `release` |
| `views/<design>.json` | `view@1`, one per `designs/<name>/<name>.scad` on main |
| `site/bundle.json` | `bundle@1` — every view plus `main_sha`, `evidence_sha`, `producer_run`, `content_sha256`, `views_sha256` |

One parentless commit, pushed with `--force-with-lease` on the planned old
tip. Rebuilt every run; it is pushed when the current tip is not an accepted
checkpoint or its actual blobs differ from the new tree (§Views,
`bundle.same_content`) — a main push that touches no `designs/` file changes
nothing and pushes nothing. Re-extraction and refreeze never modify
evidence: a new extractor version simply produces a new derived tree.

## The add-only guard

`gitstore.py` is the only module that runs git. Every invocation sets
`GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_ALLOW_PROTOCOL=https`
(plus `file` in tests), `core.hooksPath=/dev/null`, `core.fsmonitor=false`,
`safe.bareRepository=explicit`; PR objects are read with `show` and
`merge-tree --write-tree` only, never checked out.

**Fetching, once.** At the start of the plan step `Git.fetch_all()` fetches,
token-less (the repository is public; the checkout uses
`persist-credentials: false`), both data refs and
`+refs/pull/*/head:refs/remotes/pull/*/head`. Nothing else fetches after
that — the one exception is the newest evidence checkpoint `C`, fetched by
sha when the evidence tip failed continuity and does not reach it (§Tip
continuity, Acting; and `recover`) — so derive reads only what is local and
its output is a pure function of (evidence, main, the fetched PR-ref set)
rather than flapping with a per-sha fetch. A commit still missing is permanently missing — 67 of the 1,289
distinct auto-review run heads in the #843 snapshot are in no PR's commit
list (force-pushed away) — and is a deterministic basis `none` with
`incomplete: codebasis-unavailable:<sha8>`. If the bulk fetch itself fails,
the run still publishes evidence but publishes no derived tree that run
(`derive_skipped`).

The evidence writer:

1. **Temp index.** `TreeBuilder` sets a temporary `GIT_INDEX_FILE`, seeds it
   with `git read-tree <tip>` (empty at bootstrap), writes each new blob with
   `git hash-object -w --stdin` and stages it with `git update-index --add
   --cacheinfo <mode>,<blob>,<path>`. `add()` of a path that already exists
   with the same **content** (decompressed for `*.json.gz`) is a no-op and
   keeps the existing blob; with different content it raises
   `GuardViolation` at once. Only `replace()` may change a path, and only one
   in `MUTABLE_EVIDENCE_PATHS` (`state.json`). No existing file is ever
   written through the working tree, so the `git show … > file || true`
   truncation that emptied the telemetry precedent log (#D2) cannot happen
   here by construction.
2. **Commit.** `git write-tree`, then `git commit-tree -p <tip>` with the
   Actions-bot identity (`github-actions[bot]`,
   `41898282+github-actions[bot]@users.noreply.github.com`).
3. **Guard.** `git diff-tree -r --no-renames -z <old tip> <new>` must show:
   - no `D` anywhere;
   - no `M` except on `state.json`;
   - no blob becoming 0 bytes;
   - no change to the two guard files after bootstrap;
   - nothing but `A` and that one `M`.
   An identical tree means **push nothing**. A violation names the first
   offending path and rule; nothing is pushed; the run exits 4. Each rule has
   a negative control in `tests/test_gitstore.py` and in
   `scripts/provenance.sh --selftest`. The guard files are written into the
   evidence tree **once, at bootstrap**; the writer never re-adds them, so an
   edit to `.github/data-branch-guard/*` on main cannot brick the evidence
   writer — the drift is a `::warning::` (harvest summary, `check --kind
   evidence`), and the derived tree always carries main's current bytes.
4. **Push.** `git push origin <new>:refs/heads/provenance`, never forced.
   A transport failure is retried up to 3 times with the **same** commit,
   then the run fails (exit 1). **Any** rejection is treated as foreign:
   inside the `provenance-writer` concurrency group no other default-branch
   harvester can move the tip, so a moved tip is foreign by construction —
   `::error::`, exit 3, nothing rebuilt, `provenance-site` not pushed.
5. **Credentials.** The checkout uses `persist-credentials: false`. Only the
   two push functions send a token, and never in argv: the header goes
   through the child's environment (`GIT_CONFIG_COUNT=1`,
   `GIT_CONFIG_KEY_0=http.https://github.com/.extraheader`,
   `GIT_CONFIG_VALUE_0=AUTHORIZATION: basic <b64>`), and `::add-mask::<b64>`
   is printed once before the first push (Actions masks the raw token, not
   its base64 form — the oracle.yml precedent). `GitError` messages are built
   from a redacted argv and stderr, never the environment; a test pins that a
   failing push's error contains neither the token nor its base64.

The derived ref is written by `DerivedTreeBuilder` (a fresh empty index —
nothing inherited) and pushed with `--force-with-lease=refs/heads/
provenance-site:<planned old tip>`, only after the evidence push succeeded,
was unnecessary, or the plan derived from the newest checkpoint because the
evidence tip is foreign (§Tip continuity); a lease failure is foreign too.

## Tip continuity

**The threat.** The data refs are unprotected and several tokens can push
them: `REGEN_TOKEN`, the `GITHUB_TOKEN` of every `contents: write` job,
attended owner sessions, and the owner PAT on the push step of the
`workflow_run` deliverers `design-run-deliver.yml` / `backlog-burn-deliver.yml`
(no agent code; the script pushes only `claude/issue-<N>-*` — the scheduled
ship agents themselves hold a contents-read `github.token` under `dontAsk`
since #861/#863); a ruleset cannot restrict a branch to the Actions bot. So
"single writer" cannot be enforced at push time — it is checked at the next
run instead.
The forms it must catch: a forged commit on top of the tip, a forced
**rollback** to an older genuine sha, a deleted ref, and a forged derived tip.

**Marks.** Each harvest job uploads two kinds of tiny artifact (retention 90
days, content `intent@1` / `checkpoint@1`):

- `intent-<ref>-<sha40>` — between planning and publishing, for each ref it
  will move (a declared-but-never-pushed sha is harmless: nobody else holds
  that object);
- `tip-<ref>-<sha40>` — the **checkpoint**, after every successful publish
  **including a no-op one**, naming the tip it has just verified (pushed by
  itself, or unchanged and accepted).

**Ordering: upload time, not artifact id.** The artifact list is sorted by
artifact id, but ids are **not** monotonic in upload time: of 817 small
artifacts measured GET-only (2026-08-31 → 2026-10-14), 258 were uploaded ≥ 5
minutes before some lower-id artifact, 45 ≥ 30 minutes and 3 ≥ 60 minutes —
worst 3,843 s (run 37221929629's `telemetry-record`, a LOWER id than run
37217895189's `stls`, uploaded 64 minutes later). Ordering by id let a
genuine newer tip read **foreign** and a forced rollback to the previous,
higher-id checkpoint read **ok** — without deleting anything, by anyone
holding `contents: write`. Marks therefore order by `(created, id)`
(`gitstore.mark_order`): the artifact's `created_at` (its upload time, 1 s
resolution) first, the id only to break a same-second tie. Within a run the
intent is uploaded before the push and the checkpoint after it, and the
concurrency group starts the next run after this one ends, so strict upload
order holds between every pair the rule compares; a late re-run attempt of an
old run orders by when it actually uploaded.

**Scanning** (`gitstore.scan_marks`). The repository's artifact list (`GET
/actions/artifacts`; 6,519 artifacts on 2026-10-14, about 70 a day, so one
page of 100 covers about 34 hours) is read in its own (id) order, and the scan
does **not** stop at the first verified `tip-` mark per ref: it reads on until
every ref has a verified tip **and** the oldest artifact seen is more than 6
hours (`MARK_ORDER_SLACK_SECONDS`, well above the measured 64-minute worst
inversion) older than the oldest of those refs' newest tips — so no unread,
lower-id artifact can be newer — or until `continuity_horizon_days` (90). In
steady state that is still one page. A mark counts only if its run is
verified: the artifact's `workflow_run` is on `main` with a `head_sha` on
main's first-parent history, and `GET /actions/runs/{id}` shows `path ==
.github/workflows/provenance.yml` and `event` ∈ {`schedule`,
`workflow_dispatch`}.

**The clock-free cross-check** (`gitstore.checkpoint_conflicts`). The
evidence ref is fast-forward-only, so every genuine checkpoint is an
ancestor of every later one. On an otherwise-**ok** evidence verdict the
newest checkpoint `C` must therefore equal or descend from every other
verified evidence checkpoint the scan read (`git merge-base --is-ancestor`;
Reeve: `GET /compare/{other}...{C}` answering `identical` or `ahead`). One it
does not descend from is a **mark-order conflict**: the verdict is
**foreign**, `conflicts` names it, and `C` is neither built on, derived from
nor a `recover` target until a human inspects the artifact list. The
derived ref is parentless and relies on upload order alone.

**Deciding** (`gitstore.continuity_verdict`, pure, implemented with the
scaffold; Reeve's `provenance-foreign-tip` ports it and both suites run the
shared table `tools/provenance/tests/fixtures/continuity_cases.json`). With
`C` the newest verified checkpoint for the ref:

| Tip | Verdict |
|---|---|
| equals `C` | **ok** |
| evidence: its first-parent chain reaches `C` through commits that are each an intent declared **after** `C` (a run pushed and died before checkpointing) | **ok** |
| derived: an intent declared after `C` | **ok** |
| present, anything else — a forged commit, or a **rollback** to an older checkpoint or intent | **foreign** |
| evidence: would be **ok**, but `C` does not descend from another verified checkpoint (a mark-order conflict) | **foreign** (`conflicts`) |
| absent, `C` exists | **deleted** |
| present, no checkpoint in the horizon | **unanchored** |
| absent, no checkpoint in the horizon | **bootstrap** |

Counting checkpoints rather than runs is what lets a quiet day — or a
disarmed month, whose scheduled runs are skipped outright — leave the live
tip anchored: the old "last 20 runs" window let it age out after about 20
hours and then treated an absent ref as a bootstrap. Only the newest
checkpoint **by upload time** anchors, so the rule is monotonic: a ref forced
back to an older genuine sha is refused, whatever the two checkpoints'
artifact ids — and if the clock itself were ever wrong, the evidence ref's
ancestry cross-check refuses the result instead of accepting it.

**Acting** (cli step 2):

- evidence **ok** → build on the tip;
- evidence **bootstrap** → the root is created only by a dispatch carrying
  `bootstrap=true`; otherwise `::error::`, exit 3. Never automatic;
- evidence **foreign / deleted / unanchored** → no evidence is written and
  the receipts and freeze passes are skipped; derive runs from `C` and
  `provenance-site` is pushed; the job then fails (exit 3) after the
  checkpoints are uploaded. `C` is local when the foreign tip descends from
  it; when it does not (the ref deleted, or forced onto history that does not
  contain `C`) the plan **fetches `C` by sha** — every run starts from a fresh
  checkout that holds only what the refs reach — and then re-runs the
  checkpoint cross-check with `C`'s history local (`cli._checkpoint_usable`).
  A forged derived tip is therefore replaced at the next run even while the
  evidence ref is forged or gone. If GitHub cannot serve `C`, or `C` has a
  mark-order conflict, derive is skipped and nothing is pushed to the derived
  ref (`::error::`);
- derived not **ok** → recomputed and overwritten (`::error::` for foreign or
  deleted, `::notice::` for bootstrap or unanchored); derived **ok** → pushed
  only when its actual blobs differ from the new tree.

**Recovery** (`recover confirm_sha=<sha40>`, dispatch only): refused unless
the evidence verdict is **foreign** or **deleted**, `confirm_sha` equals
`C`, and `C` (fetched by sha when not local) has no mark-order conflict. It
force-with-leases `C` over the current tip (or recreates the ref) —
the only non-fast-forward write to the evidence ref. Because it can only
restore the state the harvester itself last verified, a write-access
dispatcher (an agent included) gains nothing by running it; an Environment
with required reviewers on it (the lever docs/actions-security.md names) is
therefore optional and not wired. If `C` is no longer fetchable from GitHub,
any clone that holds it restores continuity by pushing exactly `C` — tip ==
`C` is **ok**.

**Residuals** (documented in `docs/actions-security.md`):

- a forged `provenance-site` tip is live until the next harvest run — at most
  about an hour once armed, but until the next dispatch while disarmed
  (before P2) — whatever the evidence ref's state, deleted or forced off
  `C`'s history included (the plan fetches `C` by sha). It outlives the next
  run only when GitHub genuinely cannot serve `C` by sha any more (its
  objects collected after it became unreachable), or `C` has a mark-order
  conflict — then until a human acts. Before P3 nothing reads the derived
  ref; after it, the content is escaped structured fields with constructed
  permalinks, so the harm is false attribution, not script injection;
- a rollback to `C` itself is accepted: it undoes only the pushes of runs that
  died before checkpointing, which the next run redoes from the cursors;
- checkpoints expire after 90 days: a harvester that has published nothing
  for 90 days leaves no anchor, and the next run reports **unanchored**
  (refused) until a human renames the old ref and re-bootstraps — no run may
  re-anchor a tip nobody verified. Reeve's `provenance-lag` stall check and
  `routine-dead` flag a stall long before that;
- the default-branch `if:` and checkout ref are defense in depth only: a
  dispatcher who selects another ref runs that ref's YAML (docs/actions-
  security.md). The control that holds is that such a run's marks are not
  accepted (head branch, first-parent history, workflow path and event);
- the one harvest job both parses untrusted API payloads and holds
  `contents: write` (§Workflow explains why it is not split);
- Reeve's port verifies a mark's run head by **reachability** from the
  default branch (`GET /compare/{head_sha}...{default}`, status `identical`
  or `ahead` — which refuses a run dispatched on a tag named like the default
  branch), not the harvester's first-parent rule (it holds no clone); a
  commit reachable only through a merged PR's second parent passes Reeve, and
  the harvester's own scan still refuses that mark;
- whoever holds `actions: write` can delete artifacts or runs: deleting the
  newest checkpoint makes an older genuine one the newest, and a force-push
  back to it then reads **ok** (the newer frozen units vanish and are later
  re-captured with late activity). No workflow here grants `actions: write`;
  keep it off the agents' token. An optional cross-check (not built): refuse
  an evidence tip whose `state.json` cursors or `raw/` path count went
  backwards against what the newest derived bundle was built from.

## The evidence digest

Bodies are never stored. At capture, while each body is still in memory,
`digest.py` replaces it with a digest that carries exactly what the
extractors need. Because the body is then gone, a new lead class or marker
shape cannot be applied to frozen units by re-extraction — it needs a
`refreeze` (comments and issues are outside Actions retention and can be
re-read), and every digest records its version.

### Body digest (`body-digest@2`)

For every issue body, PR body, issue comment, review, review comment and
release body:

| Field | Definition |
|---|---|
| `sha256` | lower-hex SHA-256 of the body's UTF-8 bytes exactly as the API returned it (`null` → `""`) |
| `length` | UTF-8 byte length |
| `head_marker` | the first line, when it is (stripped) a full-line marker; else `null` |
| `marker_lines` | the **last ≤ 10** lines (kept in body order) that, stripped, fully match the marker grammar `<!-- ?FAMILY( key=value){0,8} ?-->` — FAMILY `[A-Za-z][A-Za-z0-9_:-]{0,63}`, key `[A-Za-z_]{1,24}`, value `[A-Za-z0-9._,:/-]{1,128}`. A marker quoted inline in prose is not a full line and is not kept |
| `footer_ok` | the body ends with `"\n\n" + FOOTER`, FOOTER = `---\n_Generated by [Claude Code](https://claude.ai/code)_` (byte-identical to `reviewer_mcp.FOOTER` and both scripts' copies; drift-pinned) |
| `suffix_markers` | the ≤ 3 markers chained immediately before that footer: `body == … + M1 + "\n\n" + M2 + … + Mk + "\n\n" + FOOTER`, walked back from the end; `[]` when `footer_ok` is false |
| `suffix_ok` | `suffix_markers` is non-empty and its last element fully matches an MCP completion shape: `<!-- (JANE\|DRIK)_SIGNOFF sha=<40hex> verdict=(pass\|block) fuse=(none\|acknowledged) -->`, `<!-- PM_TRIAGE_DONE sha=<40hex> -->` or `<!-- COACH_DONE sha=<40hex> -->`. Author is not part of it |
| `table_verdicts` | for every GFM table whose header has a cell equal (case-folded, `*_\`` stripped) to `verdict`: one entry per data row, in body order — the sorted `+`-joined verdict tokens found in that row's verdict cell (`act-now`, `decline`, `no-action`, `queue`), or `unknown`. ≤ 200 rows |
| `lead` | the class of the lead line — the first non-blank line that is not a full-line marker — under the lead rules below; else `null` |
| `lead_fields` | validated fields the lead's class carries (below); `{}` otherwise |
| `refs_closes` | sorted unique issue numbers after a GitHub closing keyword (`close[sd]`, `fix(e[sd])`, `resolve[sd]`, optional colon); only a PR body's are used |
| `digest` | `body-digest@2`. An `@1` digest (the contract still accepts it) predates the deliverers' `shipped` line and the `ship_lock_settle` and `contract` classes, so its `lead` is `null` (or `ship_lock` for a settle stub) where `@2` classifies differently |

Lead rules (first match wins, anchored at the start of the stripped lead line):

| Class | Pattern | Fields |
|---|---|---|
| `ship_lock_withdrawn` | `🚢 SHIP-LOCK WITHDRAWN` | `design_name`, `death` (the line starts with `🚢 SHIP-LOCK WITHDRAWN — scheduled run died`, `scripts/routine-lock-cleanup.sh`'s `DEATH_PREFIX`, drift-pinned: a dead-run notice posted after the agent steps, not an agent releasing its own claim) |
| `ship_lock_settle` | exactly `🚢 SHIP-LOCK — settle claim` — the settle job's constant stub since #864 (`STOP_LOCK_MARKER` + ` — settle claim` in `scripts/design-run-deliver.sh`, drift-pinned). Its own class because the burn's /ship-issue lock carries the same `design-run-ship-lock:v1` marker | — |
| `ship_lock` | `🚢 SHIP-LOCK` | `design_name` |
| `declined` | `🚢 DECLINED` | `design_name` |
| `deferred` | `🚢 DEFERRED` | `design_name` |
| `shipped` | `✅ **SHIPPED … #N` or `📦 **Draft PR opened: #N**` (the agent's own line, before #858; `#0` names no PR), or exactly `🚢 design-run delivered — branch and draft PR verified` / `🚢 backlog-burn delivered — branch and draft PR verified` (the deliverers' line since #858 — drift-pinned to `DELIVERED_LINE` in `scripts/design-run-deliver.sh`; the PR comes from the body's `- pull request: https://github.com/<o>/<r>/pull/<N>` line) | `shipped_pr`, `design_name` |
| `decision_needed` | `🚦 DECISION NEEDED` | — |
| `coach_lock` | `🎓 COACH-LOCK` | — |
| `coach_round` | `Round <N><a-z?> — ` | `round`, `round_sub` |
| `bugbot_limit` | `<hN>Bugbot couldn't run - usage limit reached</hN>` | — |
| `qodo_paused` | `**ⓘ Qodo reviews are paused` | — |
| `clear_prs` | `**/clear-prs sweep` | — |
| `contract` | `**Design name:**` — an unattended design run's §2 scope contract, posted by the settle job as its own comment since #864 (settle's SHIP-LOCK is a constant stub naming nothing; drift-pinned to the design-run skill's §2 block) | `design_name` |

`design_name` is the slug on a `**Design name:** <slug>` line anywhere in the
body (backticks optional), validated `[a-z0-9][a-z0-9-]{0,63}`.

### Message digest (`message-digest@1`)

For every commit message: `sha256`, `length`, `subject_regen` (the subject
line equals `REGEN_SUBJECT`), `subject_pr` (a squash `(#N)` suffix or `Merge
pull request #N` on the subject line, else `null`), `trailers` (allow-listed
keys only, in message order, each value full-matching its key's pattern —
`Co-Authored-By` `<name ≤80> <email>`, `Claude-Session`
`https://claude.ai/code/session_<id>`, `Preview-Diff` `all-noise|content`; a
value failing its pattern is dropped, never truncated; ≤ 12), `digest`.

### What survives as text

A run's `display_title` (the PR title or commit subject GitHub shows), PR and issue **titles** (public metadata the owner set; needed by the
stacked-base membership rule and never rendered except main's squash subject,
owner decision 5), branch names, status descriptions **of Actions-bot-created
`reviewer-signoff` statuses only** (our own fixed sentences, from
`scripts/reviewer-signoff.sh`; any other creator's description is stored
`null`, because whoever holds `statuses: write` could otherwise write 140
characters of free text into add-only evidence), workflow/job/step
names and committer names/emails as in git history. Everything else that is
free text is a digest.

## raw@1 payloads

API responses are stored as closed projections (`rawdoc.py`; contract shapes
`raw-pr@1`, `raw-brief@1`, `raw-release@1`) — not whole payloads:

- **no prose** — bodies and messages are digests; verification payloads and
  signatures, patches and `author_association` are dropped;
- **no volatility** — reaction counts, URL templates, avatar URLs, node ids
  and nested repository objects never reach a stored byte, so refreezing an
  unchanged PR is byte-identical;
- **one shape per endpoint** — the extractor reads exactly these keys.

Ordering is part of the shape: `commits` and `timeline` keep API order
(round folding reads commit order); `files` sort by filename; reviews, review
comments, issue comments, ci runs and per-sha statuses by `(time, id)`;
deployments and their statuses by id; labels by name. The timeline drops
`commented`, `committed`, `line-commented` and `commit-commented` (their
content is captured by a richer endpoint).

`incomplete` (closed patterns): `settle-deferred`,
`deployment-not-terminal`, `graphql-unavailable`, `threads-unavailable`,
`brief-open`, `commits-truncated` (> 250), `ci-runs-truncated` (the
filtered `ci.yml` branch listing capped at 1,000 or short of its
`total_count`), `files-truncated` (> 3000),
`force-pushed-heads`, `no-ci-runs`, `statuses-unavailable:<sha8>`,
`receipts-missing:<run_id>`, `codebasis-unavailable:<sha8>`.

`captured` = `{run_id, harvester, digest}` (the fixtures use run 0 /
`fixture`). `raw-pr@1.linked_issues` = the body's `refs_closes` ∪ the
`claude/issue-<N>-*` head-ref number — every linked issue, brief or not.

## Receipts

The jobs response of an agent run is the only durable record of which chain
link served — and GitHub now deletes it after 90 days. Receipts copy it.

**Selection** — from the runs **list**, never by step name. For each
workflow in `watched_workflows` (auto-review, backlog-burn, chunker,
design-run, labeler, oracle, product-scout, spike-converter, wright), the
span `[cursor − receipt_lookback_hours, until or now]` is listed in UTC-day
windows, `GET /actions/workflows/<wf>/runs?created=<A>..<B>` (all pages).
GitHub returns **at most 1,000 results** for a runs list filtered by
`created`, `branch`, `event` or `status`, and auto-review alone has 1,434
completed non-skipped runs in the snapshot, so every window must return
exactly its `total_count` rows, and a window with `total_count ≥ 1000` is
halved recursively (to one minute, then that workflow's listing fails
rather than truncating). No other filter is sent. Every run with `status ==
completed` and `conclusion != skipped` whose receipt path is absent gets one
`GET /actions/runs/<id>/jobs?filter=all` (paged; every attempt). Runs still
queued or in progress hold the cursor back for the next pass. A fresh
cursor is the snapshot's end (set by the ingest), else `backfill_since`.

**Failure isolation.** A failure costs only its own run or workflow, never
the pass: a jobs GET that still fails after the client's retries (a
persistent 5xx, a 403 — anything but a 404/410 "gone" or a budget stop) is
recorded and treated like an in-flight run (the cursor holds at it, so the
next pass retries it) while the pass goes on to the next run; a window whose
listing fails (`total_count` disagreeing twice, a one-minute window still
capped, an API error) is recorded, that workflow's cursor is set to the
failing window's start, and the pass goes on to the next workflow. The plan
names both in the summary and `plan.json` (`counts.receipts.failed` /
`errors`), outputs `receipts_error=true` and still exits 0, so the ingest,
every other receipt and the freezes are published and checkpointed; the
workflow's `Verdict (receipts)` step then fails the job.

**The agent-step grammar** (`steps.py`, version 1) — a closed list of
anchored patterns, one per naming era, each with a fixture:

| Era | First seen | Shape | Model of record |
|---|---|---|---|
| E0 | 2026-08-12 (#200) | `Run /jane-review (unattended)` | inline `--model` pin |
| E1 | 2026-08-08 → 08-21 | `Run via Anthropic (Claude)`, `Ship via Z.AI (GLM)` | inline `--model` pin (pre-#326), or a registry chain output (`steps.<id>.outputs.link<N>_model`: product-scout's `Run via Z.AI (GLM)`) |
| E2 | 2026-08-12 → 08-20 | `/jane-review via Z.AI GLM 5.2`, `/pm triage via Anthropic Opus 5` | inline `--model` pin, or (from 08-16, when auto-review moved onto the registry) `needs.design-changes.outputs.model<N>` → `chain[N]` of `review`; the name's label is a cross-check only — a mismatch is `ambiguous` |
| E3 | 2026-08-21 → | `Run via Z.AI (GLM, chain link 3)`, `/drik-review via Anthropic (chain link 4)`, `Oracle via Z.AI GLM (chain link 1)`, `Ship via OpenRouter (OSS, chain link 6)`, `Propose via …` / `Sign off via …` (wright.yml) | `chain[link]` from `registry.conf` at the code basis |

Leads: `Run`, `Ship`, `Oracle`, `Propose`, `Sign off`, `/jane-review`,
`/drik-review`, `/design-coach`, `/pm triage`. `Run`/`Ship` take the
workflow's routine role; the others name theirs. A step named like `Restore
the coach posting surface from the base branch (before chain link 1)` is not
an agent step (the patterns are anchored at both ends). Measured over the
whole snapshot: every agent step of the nine watched workflows parses; zero
are suspicious.

**Fail-safe.** A step whose name carries LLM vocabulary (Claude, GLM, Z.AI,
Anthropic, OpenRouter, Opus, Sonnet, Haiku, "chain link") but parses as no
era and matches no known non-agent pattern is *suspicious*: its run's
receipt is kept full and the name is counted as `unknown.step` in the job
summary.

**Full vs stub.** A receipt is `full` — the complete jobs list, sorted
`(run_attempt, id)` — when any job has an agent step that ran (conclusion
not `skipped`) or a suspicious step. Otherwise it is a `stub` (each job's
name, conclusion and attempt) — e.g. a disarmed run. `jobs_sha256` digests
the jobs list either way. Measured over the snapshot: 1,635 full (2.6 MB gz)
and 2,103 stubs (1.3 MB gz) for 3,738 non-skipped watched runs.

**Shape** (`receipt@1`): `{format, source: "live"|"snapshot:pr843",
workflow, run: <RUN_FIELDS projection>, kind, step_grammar, jobs|null,
jobs_sha256, stub|null, suspicious_steps}`. The run projection is exactly the
#843 snapshot's row shape (`id, name, path, event, status, conclusion,
head_branch, head_sha, created_at, updated_at, run_started_at, run_attempt,
run_number, html_url, display_title`, plus `actor` / `triggering_actor`
logins and `pull_requests` numbers), so a live receipt and an ingested one
differ only in `source`.

**Path.** `receipts/YYYY/MM/DD/<run_id>.a<run_attempt>.json.gz`, the date of
`run.created_at` (UTC). A later re-run attempt is a new path; readers use the
highest attempt. A re-run of a run older than `receipt_lookback_hours` is not
re-captured (documented residual). Receipt parity with the fixtures and
receipt identity are on the decompressed canonical JSON.

## INGEST: the #843 snapshot

PR #843 holds a GET-only snapshot taken 2026-10-13 of every run created
2026-08-01T16:59Z → 2026-10-13T06:13:35Z: `runs.tar` (one `<workflow>.json.gz`
per workflow, 19,890 rows), `jobs.tar` (one `<run_id>.json.gz` = `{run_id,
jobs}` per non-skipped run of an agent-bearing workflow, 4,485 runs), `sha.tar`
(one `<sha>.json.gz` = `{sha, statuses, check_runs}` per PR commit and head,
1,992 shas), `prcommits.tar`, `pulls.json.gz`, `workflows.json.gz`,
`capture.py`, `MANIFEST.sha256`. It was **merged to main** on 2026-10-14
(merge commit `411a7565e1c6c8f2b96edf631286ceac798d7887`) and lives at
`audits/provenance-2026-10/rescue/`; its branch is deleted.

**Not a mode.** The dispatch modes stay harvest, refreeze and recover (owner
decision 12). `harvest` ingests automatically when `state.ingested.pr843` is
absent or records an older ingest version — in practice at the bootstrap
dispatch — at about zero API cost. The snapshot is read **only** from the
default-branch checkout's `snapshot_dir` (conf): no ref, branch or path
input exists, so nothing a dispatcher or a PAT-holding agent types can point
the ingest at bytes a human did not merge (`--snapshot-dir` exists for tests
and local dry-runs). The snapshot id (`pr843`, conf `snapshot_id`) names the
evidence subtree and the receipts' `source`.

**Authenticity, then integrity.** `MANIFEST.sha256` sits in the tree it
verifies, so on its own it proves only integrity. `ingest.verify_manifest`
first requires `sha256(MANIFEST.sha256)` to equal the conf's
`snapshot_manifest_sha256` pin (`c713379b…51c7`), then recomputes every line;
`runs.tar`, `jobs.tar` and `sha.tar` are required. An internally consistent
directory whose manifest is not the pin, a mismatch or a missing file aborts
the ingest with nothing planned. Tar members are read with `extractfile`
only; a member that is not a regular file or whose name does not full-match
`[A-Za-z0-9._-]+\.json\.gz` is refused. `snapshot_commit` is recorded in
`state.ingested` as provenance.

**Mapping** (`S` = `pr843`):

| Snapshot member | Evidence path | Rule |
|---|---|---|
| `runs.tar/<wf>.json.gz` row with wf ∈ `watched_workflows`, `status == completed`, `conclusion != skipped`, + `jobs.tar/<id>.json.gz` `jobs` | `receipts/YYYY/MM/DD/<id>.a<attempt>.json.gz` | `receipts.build_receipt(wf, row, jobs, "snapshot:S")` — full or stub by the live rule. A watched run with no `jobs.tar` member is counted `missing_jobs` and skipped (the live pass still fetches it while GitHub has it) |
| `runs.tar/ci.yml.json.gz` | `raw/snapshot/S/runs/ci.yml.json.gz` | `raw-snapshot-runs@1`, every row projected (2,013 rows, 146 KB gz) |
| `sha.tar/<sha>.json.gz` with ≥ 1 status | `raw/snapshot/S/statuses/<sha>.json.gz` | `raw-snapshot-statuses@1`: statuses projected (descriptions kept only for `reviewer-signoff`), `check_runs_dropped` = the member's check-run count (1,689 files, 758 KB gz) |
| `prcommits.tar`, `pulls.json.gz`, `workflows.json.gz`, `capture.py`, `README.md` | — | not ingested: `/pulls/{n}/commits` and `/pulls` are outside Actions retention and are re-read at freeze; per-SHA check runs are not part of the design (never rendered) |

These scope cuts are now reversible: the snapshot is permanent in main's
history, so a later `INGEST_VERSION` can add the dropped check runs, or the
agent-bearing workflows outside the watched nine (lifestyle-shot,
product-still, lifestyle-clip, which write designs' AI previews), as an
add-only ingest of the new paths.

**Cursors.** The ingest raises every watched workflow's receipts cursor to the
snapshot's end (the latest row `created_at`, 2026-10-13T06:13:35Z), so the
first live pass lists from `snapshot end − receipt_lookback_hours`
(2026-10-11T06:13:35Z) rather than from 2026-07-31.

`state.json` `ingested.S` records `{manifest_sha256, commit, version,
snapshot_end, receipts, statuses, runs_listings}`.

**Idempotence** — on content. A planned path already present with identical
decompressed bytes is skipped; present with different content (a live
receipt captured first) is counted as a `conflict` and never modified — the
add-only rule wins. A second ingest of the same snapshot and version plans
no file and pushes nothing.

**Consumption.** `freeze.capture_pr` unions the snapshot's ci.yml rows (same
branch/commit filter) into a PR's `ci_runs` and `raw/snapshot/S/statuses/<sha>`
into its `statuses`, by id, live rows winning. A PR frozen in the P2 backfill
therefore keeps its pushed heads and per-round `reviewer-signoff` statuses
after GitHub deleted them.

## Capture sequences

**PR** (`freeze.capture_pr`, ~17–25 GETs; bodies digested at capture):

1. `/pulls/{n}`
2. `/pulls/{n}/files` (all pages; every PR — all three merge methods are
   enabled, so a first-parent diff of a rebase merge would see only its last
   commit)
3. `/pulls/{n}/commits` (survives branch deletion)
4. `/issues/{n}/comments`
5. `/pulls/{n}/reviews` — a review body carrying an event marker is an event
   `review:<id>` (ts = `submitted_at`; the M3-era Jane sign-offs on #371/#397:
   15 of sbc-case's 31), every other review is counted — and 6.
   `/pulls/{n}/comments` (counted, never rendered)
7. `/issues/{n}/timeline`
8. the GraphQL query (thread `isResolved` counts, `lastEditedAt`)
9. `/actions/workflows/ci.yml/runs?branch=<head_ref>` — rows kept when
   `pull_requests` holds `n` or `head_sha` is a PR commit — ∪ snapshot rows
10. `/commits/{sha}/statuses` for **every PR commit** and every ci-run head,
    ∪ snapshot statuses (a commit carrying any status is a pushed head —
    §Episodes)
11. merged: `/deployments?sha=<merge>&environment=Production` and each
    deployment's `/statuses`
12. `linked_issues` = the PR body's `refs_closes` ∪ the `claude/issue-<N>-*`
    head-ref number; each is captured as a brief only if it carries or
    carried `design-brief` (`/issues/{N}` + its timeline's `labeled`
    events) — a backlog-burn PR's `autonomy-ok` issue stays a number

Per-SHA check runs are not read (54% of the audit's full profile, never
rendered). `registry.conf` and workflow files are read with local git.

**Brief** (`capture_brief`): `/issues/{b}`, comments, timeline, GraphQL
`lastEditedAt`. **Release**: the `/releases` row itself.

**Later revisions** (`refreeze`, or a changed terminal state) re-read
everything live, then union the retention-bound sections — `ci_runs`,
`statuses`, `deployments` — from the previous revision by id, live winning:
a refreeze more than 90 days after close (when GitHub has deleted the runs
and statuses) keeps the pushed heads, and so the rounds, the previous
revision froze. Comments, reviews, timeline, commits and files are taken
live (a comment deleted since stays in the earlier revision only).

**Selection** (`plan_freezes`): `/pulls?state=closed&sort=updated&direction=
desc` paged until `updated_at` < the PR cursor (minus the settle window; a
fresh cursor is `backfill_since`), and
`/issues?labels=design-brief&state=all&sort=updated&since=<cursor>`; with
`--pr`, only those PRs. A listed PR that is already frozen is compared with
its stored revision's `closed_at`/`merged_at` (a brief's `state`/`closed_at`);
only a difference re-enters settle — comment-only activity changes
`updated_at` and nothing else.

## Records and events

`record = extract(raw, extractor_version)` and `view = fold(records,
main@sha)` are both pure. The closed shapes live in
`site/lib/provenance-contract.json` (`record@1:pr|brief|commit|release`,
`event@1`, `field_sets`); both stacks validate against that one file with
hand-rolled validators.

### event@1

Derivation tags: **D** deterministic (a pure function of the payload or a
committed file), **J** join (needs a second lookup: receipts, registry at a
reconstructed sha, blame), **W** window (a time-window join; null when
ambiguous), **N** not derivable (null with an explicit basis, never inferred).

| Field | Tag | Definition |
|---|---|---|
| `id` | D | closed forms: `issue:<n>:filed`, `issuecomment:<id>`, `review:<id>` (a PR review body carrying an event marker), `timeline:<id>`, `pr:<n>:opened\|merged\|closed`, `commit:<sha40>`, `status:<id>`, `run:<id>`, `job:<id>`, `deployment:<id>`, `release:<id>`, `row:<design>:<PM\|NOTES>.md:<sha256[:16]>:<k>` |
| `ts` | D | RFC3339 UTC to the second: `created_at` / `submitted_at` / author date / job `started_at`; day rows `YYYY-MM-DDT00:00:00Z` |
| `ts_precision` | D | `second` \| `day` |
| `tz` | D | `UTC` |
| `kind` | D | closed enum (below) |
| `episode` | J | `E0:brief:<n>` \| `R:<pr>:<author-push sha8>` \| `M:<pr>` \| `C:<sha8>` \| `D:<date>` |
| `pr`, `issue`, `sha` | D | the PR / issue / the sha the event is ABOUT (marker sha, commit, status target) |
| `head_sha` | J | the pushed head live at `ts` |
| `stale_sha` | J | the marker sha is not among its round's heads |
| `after_merge` | D | `ts > merged_at` |
| `url` | D | constructed from validated ids and OWNER/REPO, never copied from `html_url`; every stored event has one (a review-sourced event links `pull/<n>#pullrequestreview-<id>`) |
| `signals` | D | raw identity facts: `login`, `login_type`, `app`, `marker`, `commit_author_name`, `commit_author_email`, `committer_login`, `status_context`, `regen_identity`, `trailer_coauthors`, `trailer_session` — identity is resolved at site build (P3c `people/actors.conf`), never in the data |
| `trust` | D\|W | `verified` \| `window` \| `claimed` \| `login` \| `ambiguous` \| `none` (§Trust tiers) |
| `trust_basis` | D | `actions-bot+suffix`, `actions-bot+head-marker`, `actions-status+receipt`, `receipt`, `window:run <id>`, `marker:owner-token\|other-author\|no-suffix\|edited`, `trailer`, `login`, `ambiguous`, `none` |
| `runtime.platform` | D | `github-actions`, `claude-code`, `cursor`, `copilot`, `coderabbit`, `vercel`, `github-web`, `unknown` |
| `runtime.harness` | D | `claude-code-action`, `claude-code`, `cursor-agent` or null |
| `runtime.role` | J\|W | the agent-step role (`jane`, `drik`, `pm`, `coach`, `oracle`, `wright`, `reeve-signoff`, `design-run`, `backlog-burn`, `product-scout`, `spike-converter`, `chunker`, `labeler`) |
| `runtime.workflow`, `job`, `job_id`, `run_id`, `attempt` | D\|W | D for receipts and Actions statuses, W for comments attributed by window |
| `runtime.chain`, `chain_link`, `links_not_served`, `provider`, `model` | J | §Serving-model join; `model` displayed "requested for chain link N" |
| `runtime.model_basis` | D | `step-window+registry@head(<sha8>)`, `…@merge(<main8>+<head8>)`, `…@main(<sha8>)`, `job-link+registry@…`, `provider-step+inline-pin@<sha8>`, `trailer`, `ambiguous`, `none` |
| `fields` | D | the closed per-kind set (`field_sets` in the contract) |
| `edges.verifies` | J | the fix shas a sign-off covers |

Kinds (closed): `brief.filed|claimed|shipped|declined|deferred|withdrawn|closed`,
`pr.opened|ready_for_review|merged|closed`,
`commit.design|fix|human|merge_main|regen`, `review.signoff`,
`triage.verdict`, `coach.lock`, `coach.round`, `oracle.review`,
`status.reviewer_signoff`, `job.reviewer`, `ci.gate`, `decision.pm_log`,
`decision.notes_log`, `field_test`, `changelog`, `deploy.production`,
`release`.

Per-kind fields (all required, closed): `brief.*` `design_name` (+
`settle` for claimed — true for the settle job's `ship_lock_settle` stub;
`death` for withdrawn — true for routine-lock-cleanup's dead-run notice;
`shipped_pr` for shipped; `state_reason`, `closed_by_pr` for closed);
`pr.opened` `draft`; `pr.merged` `merge_method`, `merged_by_login`,
`main_subject` (main's squash subject, owner decision 5); `commit.design|fix|
human` `parents`, `signature_verified`; `commit.merge_main` `parents`;
`commit.regen` `preview_diff` (`all-noise|content|absent|multiple`);
`review.signoff` `family`, `verdict` (`pass|block|fail` — `fail` is an M3
spelling), `fuse`, `edited`; `triage.verdict` `designs`, `act_now`, `queue`,
`decline`, `no_action`, `rows`, `completion_marker`, `edited`; `coach.lock`
`completion_sha`, `edited`; `coach.round` `round`, `sub`; `oracle.review`
`edited`; `status.reviewer_signoff` `state`, `verdict` (`PASS|BLOCK|PENDING`),
`reason` (`signed-off`, `fuse-acknowledged`, `not-signed`, `stale`, `blocked`,
`fuse-unacknowledged`, `overridden`, `other`); `job.reviewer` `conclusion`,
`posted`, `links_tried`; `ci.gate` `conclusion`, `event`; committed rows
`file`, `line` (the line's number in `added_in_sha`, from `blame
--porcelain`), `line_sha256`, `added_in_pr`, `added_in_sha` (required);
`deploy.production` `state`, `deployment_id`; `release` `tag`, `prerelease`,
`assets`.

**Counted, never stored as events** (`noise_counts`, closed keys): third-party
bot comments by app (`comment.bot.coderabbit|cursor|qodo|vercel|entelligence|
copilot|other`), lead-classified noise (`comment.bugbot_limit`,
`comment.qodo_paused`, `comment.decision_needed`, `comment.clear_prs`,
`comment.unclassified`), reviews that yield no event (`review.bot|empty_wrapper|human`), review
comments (`review_comment.bot|human`), statuses (`status.coderabbit|vercel|
other`, `status.reviewer_signoff.no_design_changes`), the three stickies
(`sticky.auto_review_stamp|printcheck_gate_report|argus_diff_report`),
timeline `deployed` (preview deployments) and other timeline events, and
`marker.unknown`. Unknown marker families and suspicious step names go to
`record.unknown.markers` / `.steps`.

**Deliberately not stored** (N5): comment, review, issue and branch-commit
prose; finding→triage links (0% deterministic, 63% by text match — refused);
reply-text "claims fixed" heuristics (SBC-7 is re-expressed as thread counts);
whether an owner-login event was a human click or an owner-token session
(shown as the `login` tier).

### record@1

| Kind | Key | Extra fields |
|---|---|---|
| `pr` | PR number | `state`, `created_at`, `closed_at`, `merged_at`, `merge_commit_sha`, `merge_method`, `head_ref`, `base_ref`, `linked_issues` (every linked issue), `briefs` (those with a `raw/brief/` document — design briefs only), `designs` (`{design: {membership, kinds}}`), `rounds`, `threads` (`{total, resolved}`), `noise_counts`, `unknown`, `evidence` |
| `brief` | issue number | `issue`, `state`, `state_reason`, `created_at`, `closed_at`, `labels`, `design_name`, `prs`, `evidence` |
| `commit` | sha40 | `sha`, `committed_at`, `designs`, `evidence` (`source: git`) |
| `release` | tag | `tag`, `published_at`, `designs`, `evidence` |

Every record carries `format`, `kind`, `extractor`
(`provenance-extract 2`), `incomplete` and `events` (sorted by the event sort
key). `evidence` = `{raw, raw_sha256, revision, receipts, source}`
(`raw_sha256` over the decompressed document). No record or view carries
main's sha: a main push that touches no `designs/` file must leave every
record and view byte-identical (the derived ref would otherwise churn on
every push to main).

**Direct-to-main commits** (`commit` records). A first-parent main commit
touching `designs/` is direct only when its subject carries no PR reference
(no squash `(#N)`, no `Merge pull request #N`), its committer is not GitHub
(`noreply@github.com` — GitHub commits squash, merge and rebase merges and web
edits), and it is in no frozen PR's commit list. A `(#N)` commit whose PR is
not yet frozen — inside its settle window, or before the P2 backfill reaches
it — yields no record (the site's "settling" state covers it), rather than a
`C:` record that would vanish when the PR freezes. Measured on main since
2026-07-31: 366 of 372 first-parent commits carry `(#N)`; the other six are
five owner-committed bootstrap commits (real direct commits) and `43030db9`
"Merge PR #196: …", which GitHub committed under a subject neither pattern
matches — the committer rule keeps it from becoming a false direct record.

The event-source table (which raw field yields which kind, id, ts, sha and
url), the commit-kind rules and the platform rules are in the docstring of
`tools/provenance/src/provenance/extract.py`.

## Membership

The audit's refined file-kind rule (P = 1.00 / R = 1.00 on the tuned designs,
0.94 / 1.00 held out), applied to `/pulls/{n}/files` for every PR, with paths
relative to `designs/<D>/`:

| Path | Kind |
|---|---|
| `previews/.regen-stamp` | stamp |
| `previews/lifestyle-*.png\|gif`, `previews/product-still-*.png` | ai |
| `*.md` anywhere (incl. `previews/CAMERAS.md`) | docs |
| `*.conf` anywhere (incl. `previews/cameras.conf`) | source |
| other `previews/*` | previews |
| `*.scad`, `ci.*`, `*.args`, `ARCHIVED` | source |
| anything else | other |

PR P is a **member** of D iff its D files include a source, docs or ai file,
except:

- **sweep** — D's only source files are `team.conf`/`catalog.conf`, D has no
  `.md`, and P substantively touches ≥ 5 designs;
- **stacked-excluded** — P is not merged, substantively touches ≥ 2 designs,
  and its title names (word-bounded, case-folded) at least one of them but
  not D.

Everything else under `designs/D/` is **regen-only** (stamp/previews/other) —
a maintenance row on the view. Main commits for CC-1: `substantive` (a
source/docs/ai file), `stamp-only` (only the stamp), else `previews-only`.
Records carry the rule version; a change re-derives every record from
evidence without a re-harvest.

## Episodes

**Push evidence.** REST exposes no push time. A sha is a pushed head when it
is the PR's final head, a ci.yml run names it, or it carries at least one
commit status (Vercel and CodeRabbit post one per pushed head even when
ci.yml did not run). `pushed_at` = the earliest of those runs' and statuses'
`created_at`; a final head with neither (a degraded capture: no ci runs, its
statuses unavailable) takes its committer date (author date if absent) when
that is later than every other pushed head's, else `null`. Measured on the fixtures, this reproduces every round count the
audit hand-built: #636 15 (NVC-1), #371 2 and #397 14 (SBC-1), #634 13 (CC-5
— #634's three one-second web commits are pushed heads only by the status
rule).

**Push groups.** Walk `/pulls/{n}/commits` in API order; each commit joins
the current group; a pushed head closes it. A pushed head absent from the
commit list (force-pushed away) is its own group, placed by `pushed_at`, and
the record gains `incomplete: force-pushed-heads`.

**Regen fold.** A group whose head commit is a regen commit-back — subject ==
`REGEN_SUBJECT`, author email == `REGEN_AUTHOR`, exactly one parent
(`scripts/reviewer-signoff.sh`'s constants, drift-pinned) — folds into the
preceding round whatever its `Preview-Diff` trailer says (the trailer is
recorded in `commit.regen.fields.preview_diff`). A merge-of-main commit is an
ordinary member of its group; a group whose **head** is a merge of main is an
author push and so a round (`R:636:f4e36eb9`).

**Rounds.** One per author group: `R:<pr>:<head8>`, `heads` = author head +
folded regen heads, `commits` = all their commits, `pushed_at`, `start` =
`pushed_at`, `end` = the next round's `pushed_at` (last: merged/closed).

**Assignment.** `brief.*` → `E0:brief:<n>` (a `brief.closed` closed by a PR's
merge → `M:<pr>`); `pr.merged`, `pr.closed`, `deploy.production` → `M:<pr>`;
`commit.*` → the round holding the commit; `job.reviewer` and
`status.reviewer_signoff` (their `sha` is the head the reviewer job ran on /
the status was posted to) → the round whose `heads` hold that sha, `head_sha`
that round's head — a reviewer job or `reviewer-signoff` status about head X
that starts or posts after head Y was pushed judged X's round, which is where
the audit golden puts every one of them (the ts rule misplaced 3 + 3
nuggs-vent-cap and 8 + 9 sbc-case jobs + statuses a round late, unflagged;
integration review round 2), falling back to the ts rule when the sha is in
no round's `heads`; every other PR event → the round whose `pushed_at` is the
latest ≤ `ts` (the first round if `ts` precedes every push); direct-to-main
commits → `C:<sha8>`; committed rows → `D:<date>`. `head_sha` = the live
pushed head at `ts` (for the two head-sha kinds, the head of the round they
were placed in); `stale_sha` = the event's marker sha is not one of its
round's `heads`; `after_merge` = `ts > merged_at` for an event kept in a live
round (it stays there) — never for `pr.merged` / `pr.closed` /
`deploy.production`, which follow the merge by definition.

**verifies.** A `review.signoff`'s `edges.verifies` = the
`commit.design|fix|human` shas at or before its marker sha in commit order and
after the same family's previous sign-off sha.

**Placement after the join.** The derive order is fixed: extract (events
placed from the raw document) → `serving.annotate_record` →
`serving.receipt_events` (the `job.reviewer` events, returned unplaced) →
`episodes.place` (assigns every unplaced event over
`episodes.rounds_from_record`) → views. Records are stored only after
placement, so every stored event has an episode. `protocols.Round` is the one
in-memory round type extract, serving and views share.

**Committed rows** (`episodes.decision_rows`), parsed from main at the
harvest's main sha with line-for-line ports of `site/lib/timeline.mjs`:
`PM.md ## Decision log` table rows → `decision.pm_log`; `NOTES.md ## Field
test log` `### YYYY-MM-DD — …` → `field_test`; `NOTES.md ## Changelog` `###
<v> — YYYY-MM-DD — <t>` → `changelog`; and, new, `NOTES.md ## Decisions log`
/ `## Decision log` dated top-level bullets → `decision.notes_log`. Each row's
`added_in_sha` and `line` come from `git blame --porcelain` (the commit that
added the line and its number there; `added_in_sha` is required — a blame
that does not cover the file line for line, an empty one from a failed git
call included, raises `episodes.BlameUnavailable` and derive fails closed:
the plan's `derive_error`, never a silently dropped row), and its URL is
`blob/<added_in_sha>/designs/<d>/<file>#L<line>` — none of which moves when
main moves; `added_in_pr` from the first-parent
main commit containing it (`(#N)` squash or `Merge pull request #N`), or, for
a rebase-merged sha, from the PR record whose commits hold it. Row ids hash
the line's text, so a row keeps its id when lines above it move; the site
matches rows by `line_sha256` and renders the committed text from its own
checkout. Rows read "charter decision (PM.md) · added in PR #N" — "added in",
never "by" (#496).

**Parity with `site/lib/timeline.mjs`.** `site/test/provenance-rows.test.mjs`
runs timeline.mjs and the Python ports (`python3`, `PYTHONPATH=
tools/provenance/src`) over every `designs/*/PM.md` and `NOTES.md` and asserts
the same line selection. It lives in the site's suite because timeline.mjs
imports `marked` (through `markdown.mjs`) and so needs `site/node_modules`;
the `site-build` job runs `npm --prefix site test` on every PR, so either
side drifting fails a required check (the `site/lib/lineage.mjs` ↔
`tools/lineage` precedent).

## Serving-model join

Pure (`serving.py`) over receipts, records and a `CodeBasis`
(`codebasis.py`). Every event records `model_basis`; nothing is guessed.

1. **Windows.** Every agent step that ran, in a full receipt, is a window
   `[started_at, completed_at]` (inclusive, seconds) with its run, job and
   parsed step.
2. **Containment.** An artifact at `ts` is attributed to a window when the
   window contains `ts`, its role is one the event kind allows (`KIND_ROLES`:
   a JANE_SIGNOFF → `jane`, a triage → `pm`, `brief.filed` →
   product-scout/spike-converter, `brief.claimed`/`commit.design`/`pr.opened`
   … → design-run/backlog-burn) and the artifact's author is one of that
   role's posting identities (`ROLE_IDENTITIES`: reviewers and the scout post
   as the Actions bot; the ship routines post as the owner or the Actions bot
   and commit as the Actions bot — see the key below). One window → attributed; none → `none`; windows of two or more runs →
   `ambiguous`. An owner-token sign-off inside a reviewer window is never
   attributed to it. A reviewer-role window (`jane`, `drik`, `pm`, `coach`,
   `oracle`) is a candidate only on a PR record whose run it is: the run's
   `pull_requests` holds the PR, or its `head_branch` is the record's
   `head_ref` and the run was created within the PR's `[created_at,
   closed_at]` (the step-5 job rule). Every reviewer posts as the Actions bot
   and auto-review runs of different PRs overlap constantly — over the #843
   snapshot a window's last 3 s overlaps another PR's same-role window for
   640/1,822 Jane, 515/1,766 Drik, 275/637 PM, 71/785 Oracle and 33/135 coach
   windows — so unscoped, 6 of #636's 12 verified sign-offs and all 5 of
   #634's come out ambiguous, and a PR whose own receipt is missing would be
   attributed to another PR's run.
   **A ship-routine window needs a key.** Who writes for the ship routines
   changed with #858/#864/#868. Their agents now hold `github.token` only:
   the backlog-burn agent posts its SHIP-LOCK and stops as the Actions bot
   inside its window; the design-run agent holds `issues: read`, and its
   SHIP-LOCK (a constant stub), stops and §2 contract are posted by the run's
   `settle` job as the Actions bot after every agent step; the draft PR is
   opened as the owner (the owner PAT) and the `🚢 <routine> delivered — …`
   comment posted as the Actions bot by `design-run-deliver.yml` /
   `backlog-burn-deliver.yml`, `workflow_run` runs that start after the
   routine run ends; claude-code-action's commits resolve to the Actions
   bot's login. So an owner OR Actions-bot artifact inside a ship window may
   be the owner's attended work, the other routine's settle, deliver or
   bundle step, or a previous run's deliverer. Such an artifact is
   attributed only through the issue that run claimed: `run_claims` maps a
   run to the one issue whose owner- or Actions-bot-authored SHIP-LOCK
   (`brief.claimed`) lies in its windows, counted only when the brief carries
   that routine's opt-in label (the selector claims one issue per run; a run
   whose windows hold SHIP-LOCKs on two or more distinct issues claims
   nothing; several locks on one issue, like #281's two in run 32026482297,
   are one claim). An Actions-bot `brief.withdrawn` that is the agent
   releasing its own claim (§0.6 edits the lock's first line to WITHDRAWN,
   keeping its time) counts as the lock it was. The settle job's stub
   (`settle: true`) and routine-lock-cleanup's dead-run notice (`death:
   true`) never count and are never window-attributed — both are posted
   after every agent step, so only other runs' windows can hold them — and
   an Actions-bot lock counts toward one routine: toward design-run
   when it names the design (the #860–#864 runs' agent posted its §2
   contract as the bot), toward backlog-burn when it does not (the
   /ship-issue contract names none), so the burn's lock on a brief carrying
   both opt-in labels is not also an overlapping design run's claim. The
   SHIP-LOCK itself and owner/bot `brief.*` events on that issue get
   `window`, as do owner/bot `pr.opened` / `commit.*` on a
   `claude/issue-<N>-…` branch whose N is the claimed issue; a settle stub
   never does. An Actions-bot `pr.opened` / `commit.*` also gets `window`
   (a claim on another issue does not block it: since #864 a design-run
   window's only locks are someone else's) when it predates the PR and N is
   an issue that routine selects — a captured brief (`briefs` — design
   briefs only) for design-run, any other issue for backlog-burn. Since #858
   the deliverer opens the PR after the run ends, so the agent's own commits
   all predate it, while the design coach's iterations (the same login,
   pushed after the open) and the other routine's bundle commits do not
   join. (An owner-PAT-era agent that pushed after opening its own PR keeps
   those commits through its owner claim; the claimless ones of that era —
   #340, #586, #807 — touch no `designs/` file and are never records.) Anything else stays `login`: an owner PR on another branch inside a
   routine window, a run that declined without claiming, a design-run settle
   lock, stop or delivered comment that lands inside a backlog-burn window
   (before this key it became the burn's work at trust `window`). `claude[bot]` keeps the plain rule. Run 34661448637 claimed
   #592 and #636's head is `claude/issue-592-nuggs-vent-cap`, so NVC-3 and
   NVC-4 hold.
   **Not joined yet.** Since #864 a design run's own claim, stops and
   delivered comment, and since #858 every routine PR's owner `pr.opened`,
   lie outside every agent window (settle and the deliverers run no agent
   step), so they stay `login` — lost attribution, not wrong attribution;
   the run link of those PRs comes from the agent's commits. Joining them
   through the run's `settle` job and the delivered comment's `- run:` URL is
   a separate change. **Known limit:** an attended owner SHIP-LOCK posted
   while a design run's window is open still becomes that run's claim, as it
   did before #858 (owner locks were then the run's own); telling the two
   eras apart needs the run's workflow revision, which this join does not
   read.
3. **Code basis** — what each run checked out:
   - `schedule` / `workflow_dispatch` (design-run, backlog-burn and the other
     routines): `run.head_sha`, exact;
   - `pull_request` in `auto-review.yml`: the design-changes job checked out
     the merge ref and resolved the chain there, so `git merge-tree
     --write-tree <main@created_at> <run.head_sha>`, reading
     `.github/models/registry.conf` and the workflow from that tree;
   - `pull_request` in `oracle.yml`: the job checks out
     `pull_request.base.ref` **by name when its checkout step runs**, which can
     be long after `created_at` on a busy queue, so the registry is main at
     that step's `started_at` (from the same receipt job); the workflow text
     (the resolve literal and the step's `--model`) is the PR merge commit's,
     because GitHub runs a pull_request workflow's definition from
     `GITHUB_SHA` — read from `git merge-tree --write-tree <main@checkout>
     <run.head_sha>`, which equals GitHub's merge from main@created_at unless
     main touched the workflow in between;
   - `main@T` = the last first-parent main commit with committer date ≤ T;
   - `ambiguous` when merge-tree conflicts on either file, or a main commit
     touching either landed within `ambiguity_window_minutes` (15) before
     `created_at` (merge: the merge ref GitHub built may predate it) or within
     15 minutes either side of the checkout step (main; for the workflow file
     the interval starts 15 minutes before `created_at`), or merge-tree
     conflicts on the workflow file (main);
   - a commit the basis needs that is not local after the job-start fetch (a
     force-pushed-away head; the Oracle's run head included) → basis `none`, `incomplete:
     codebasis-unavailable:<sha8>` — never a fetch. Bases are memoized per
     `(workflow, kind, main8, head8)`.
4. **Chain and model.** E3: the chain is the workflow's `model_registry
   resolve <chain>` literal at the basis (`oracle.yml` and `wright.yml` carry
   two; `CHAIN_DISCRIMINATORS` picks by lead and provider and the pick must be
   one of the literals). `model = chain[link − 1]` from that `registry.conf`,
   parsed with tools/model-registry's own strict parser (a historical file it
   refuses → model null, basis `none`, never a lenient re-parse).
   `links_not_served = link − 1`, rendered "links 1–(N−1) did not serve",
   never "failed" (auto-review walks on `served`; a link can exit 0 having
   posted nothing, #762). E0–E2: the step's inline `--model` literal in the
   workflow at the basis — found by a line scanner (the job by `name:`, the
   step by exact `- name:`), not a YAML parser. A step with no literal pin
   whose `--model` is a registry chain output gets the E3 rule with link = N
   and the `model_registry resolve` literal of step `<id>`; the two forms are
   `${{ needs.<job>.outputs.<out> }}`, traced to that job's `<out>: ${{
   steps.<id>.outputs.link<N>_model }}`, and `${{
   steps.<id>.outputs.link<N>_model }}` itself. Over the snapshot this covers
   139 of the 213 local E2 windows (auto-review from 08-16) and
   product-scout's 3 E1 windows; the other 74 E2 windows carry a literal pin.
   The E2 name label is a cross-check: a label that spells a different id than
   the pin or the chain output gives `ambiguous` (0 of 213 disagree).
5. **Job-level** (`job.reviewer`): the last non-skipped link step
   (`continue-on-error` masks step conclusions) with basis `job-link+…`;
   `posted` = some event of the record is attributed to that job (Drik's job
   in run 38161046420 tried all six links and posted nothing).
6. **Trailers.** `Co-Authored-By: Claude <Name> <noreply@anthropic.com>` →
   `model = Name` (e.g. `Claude Opus 5.5`), basis `trailer`, trust
   `claimed`; `Cursor Agent` → platform `cursor`, model null; `Claude Code`
   names the harness, not a model → harness `claude-code`, model null, basis
   `none` (31 commits carry it).

Displayed as "requested for chain link N": a provider-side alias swap or an
in-harness fallback is invisible to this join.

## Trust tiers

Computed from the digest and the author login (the body is gone), an exact
port of `scripts/reviewer-posted.sh` and `scripts/coach-lock-check.sh`,
drift-pinned to `reviewer_mcp.FOOTER`, the marker literals and both scripts.

| Tier | Rule | Basis |
|---|---|---|
| verified | sign-off: Actions-bot author (REST `github-actions[bot]`, GraphQL `github-actions`) **and** `suffix_ok` **and** `suffix_markers[-1]` is that sign-off — the body ends with `marker\n\nFOOTER` | `actions-bot+suffix` |
| verified | triage: Actions bot and `suffix_markers[-1]` is `PM_TRIAGE_DONE sha=` the triage sha | `actions-bot+suffix` |
| verified | coach lock: Actions bot and `suffix_markers[-2:] == [COACH_LOCK, COACH_DONE sha=…]` | `actions-bot+suffix` |
| verified | Oracle: Actions bot, `head_marker == <!-- ORACLE_REVIEW -->`, `footer_ok` | `actions-bot+head-marker` |
| verified | a `reviewer-signoff` status created by the Actions bot whose target run is an auto-review receipt; every receipt event | `actions-status+receipt`, `receipt` |
| window | the rule fails, the author is a posting identity of the role, and exactly one compatible window contains the artifact (`serving.py`) | `window:run <id>` |
| claimed | a marker or trailer is present but the rule fails: the owner's token, another author (markers quoted by cursor[bot]), an Actions-bot post without the suffix, or a post edited ≥ `edit_grace_seconds` (60) after creation — an edit demotes even a verified suffix; trailers; an issue body with `lastEditedAt` | `marker:owner-token\|other-author\|no-suffix\|edited`, `trailer` |
| login | only the authoring login is known | `login` |
| ambiguous / none | no single attribution | `ambiguous`, `none` |

"Verified" means exactly what `reviewer-posted.sh` accepts and inherits that
rule's residuals (any session holding `GITHUB_TOKEN` can post as the Actions
bot). A PR **review** body is never `verified`: `reviewer-posted.sh` reads
only issue comments, so a review-sourced sign-off or triage is capped at
`claimed` / `marker:no-suffix` (`window` at best, through the serving join).
A judged kind with no marker of its own family — a `coach.lock` built from its
lead line alone — is `login`, not `claimed`. A `reviewer-signoff` status
carries the auto-review receipt's `runtime.workflow` / `run_id` only when it
is `verified` / `actions-status+receipt`. On #636 this yields 12 verified
sign-offs (6 Jane, 6 Drik) and 13
owner-token Drik sign-offs that are `claimed` (NVC-5, NVC-6). The display rule
(owner decision 6): owner-token sign-offs are shown tagged "unverified —
posted from the owner's token" and never count toward "Reviewed by".

**Marker eras** (`markers.ERAS`, one fixture each): M1 persona prose with no
marker (2026-08-01); M2 `PM_TRIAGE` posted with `gh` (08-21); M3
`JANE/DRIK_SIGNOFF` anywhere in a `gh`-posted body, often after the footer
(08-23/24); M4 MCP-assembled suffix (#790/#804, 10-04); M5 completion markers
`PM_TRIAGE_DONE` / `COACH_DONE` and the COACH_LOCK pair (#770/#820/#806, 10-06).
One attribute grammar parses all five; only placement differs, which is what
the tiers judge.

## Views, bundle and the derived tree

**Views** (`views.py`): one `view@1` per `designs/<name>/<name>.scad` on main,
including a design with no history. A view holds every event of every PR
record where the design is a `member`, every event of each brief linked to it
(by `design_name` or a member PR's `briefs`; brief numbers and a differing
slug go to `aliases`), its direct-to-main commit records, its committed rows
and its releases; `regen-only` and `sweep` PRs become `maintenance` rows.
Events are de-duplicated by id and sorted by the sort key; `episodes` and
`counts` are derived. A view carries no `main_sha` (the bundle's meta does).

**Bundle** (`bundle.py`, `bundle@1`): all views, `main_sha`, `evidence_sha`,
`producer_run`, `views_sha256` and `content_sha256` — a digest of the records'
digests, the views' digests and the extractor version, i.e. of everything
except the three meta fields — for the site's own integrity check. The push
decision never trusts that field: `bundle.same_content` reads the current
derived tip's actual blobs and requires the same paths, every path but
`site/bundle.json` byte-identical, and the bundle equal once its three meta
fields are removed; the tree is pushed when the tip is not an accepted
checkpoint or that comparison fails. A forged tip that copies the real
`content_sha256` but alters a view is therefore replaced. Because nothing but
the bundle's meta depends on main's sha, `main_sha` reads "the main commit
these views were last recomputed against". No cursors, no pending list, no
wall clock.

**Python↔Node parity.** `tests/test_bundle.py` rebuilds
`site/test/fixtures/provenance-bundle.json` in memory from committed synthetic
records (`tools/provenance/tests/fixtures/records/`: hand-authored,
contract-valid, every record kind and event field set) with fixed meta (main
`521d0928…`, evidence `"0"×40`, run 1) and asserts byte equality with the
committed file (it writes the file only under `PROVENANCE_UPDATE_FIXTURES=1`); `site/lib/provenance-contract.mjs` and
`contract.py` must both accept it and both reject a copy with one extra
field. The site ignores unknown kinds and fields (forward compatibility); the
validators do not.

## Canonical JSON and the sort key

Canonical JSON (`canonical.py`): sorted keys at every depth, `indent=1`,
`separators=(",", ": ")`, UTF-8 (`ensure_ascii=False`), LF, one trailing
newline, no floats anywhere (refused), no NaN.

Event sort key: `(ts, precision rank [day < second], source rank, numeric
github id, sub-index, id)` — source rank is the id prefix order `issue, pr,
timeline, commit, issuecomment, review, status, run, job, deployment, release, row`;
the github id is the first all-digit `:`-segment after the prefix (else 0);
the sub-index is the last all-digit segment when it is not the id. The site's
adapter (P3a) sorts with the same rule (contract `sort_key`).

## API budget and pacing

`GITHUB_TOKEN` allows 1,000 requests/hour per repository, shared with every
sibling workflow.

| Rule | Value |
|---|---|
| scheduled cap | `scheduled_max_requests` (400) non-304 responses; the request that would exceed it is not sent |
| floor | when `X-RateLimit-Remaining` < `rate_floor` (500): a scheduled run stops cleanly; a dispatch sleeps until `X-RateLimit-Reset` + 5 s |
| capture deadline | a dispatch stops capturing at the plan step's start (its one clock read, after the full-history checkout) + `dispatch_max_minutes` (330) − `derive_reserve_minutes` (8: sized to the case the reserve protects, a dispatch that reaches the deadline — a full backfill — whose derive projects to ~3–4 minutes from the integration dry run's 13–17 s over the full #843 ingest plus the fixture PRs at ~0.9 s per PR record; twice that, rounded up); derive and publish run after it, inside `timeout-minutes: 350`, the 20 minutes between 330 and 350 left for the checkout and a large publish; cursors resume on the next dispatch |
| ETag | `If-None-Match` on every GET from `<out-dir>/etag-cache/`; a 304 is free and not counted |
| retries | 5xx, 403/429 with `Retry-After` or a secondary-limit message, socket timeouts: 3 retries (2/4/8 s); 401/404/410/422 not retried |
| pagination | `per_page=100`; `rel="next"` followed only on `api.github.com`; more than `max_pages` raises rather than truncating |
| filtered-list cap | a runs list filtered by `created`/`branch`/`event`/`status` returns at most 1,000 results: receipts window by UTC day, assert `total_count`, halve at ≥ 1,000 (§Receipts); the gate's runs list is unfiltered; the continuity scan reads the repo-wide artifact list |
| continuity scan | about one artifact page per 1.4 days since the newest checkpoint, read on until an artifact 6 h older than the newest tips (one page in steady state) + one run GET per candidate run + (evidence, ok verdict) the ancestry of each other distinct checkpoint (local git; Reeve one `compare` GET each) |
| nothing new | a run with nothing new writes nothing (tested) |

Measured costs: 4,089 runs of the nine watched workflows since 2026-07-31
(351 skipped) → about 3,740 jobs GETs + 45 list pages for receipts, of which
the #843 ingest covers everything through 2026-10-13T06:13Z at ≈ 0 requests;
about 3,700 GETs for the 202 design-touching PRs and 52 briefs; a full
backfill is about 3,800 requests after the ingest ≈ 8 h self-paced (two
dispatches); incremental per merge 17–25.

## Conf keys

`.github/provenance.conf`, parsed by `tools/provenance/src/provenance/conf.py`
(its own strict parser; closed key set; `key: value`; `#` comments; unknown /
duplicate / colonless / malformed lines fail with `path:lineno`; integers only).

| Key | Value | Meaning |
|---|---|---|
| `enabled` | `true` | the in-git half of the schedule's two-key arming; a dispatch needs only this |
| `cadence` | `29 * * * *` | raw cron, identical to provenance.yml's `- cron: '29 * * * *'` |
| `settle_hours` | 6 | closed → due (≈ 4× the measured 1.42 h settle) |
| `max_defer_hours` | 24 | deferred → frozen with `incomplete` |
| `deploy_wait_hours` | 2 | wait for a terminal Production deployment |
| `scheduled_max_requests` | 400 | scheduled request cap |
| `rate_floor` | 500 | rate-limit floor |
| `dispatch_max_minutes` | 330 | a dispatch's capture budget from the plan step's start (with the reserve below) |
| `derive_reserve_minutes` | 8 | kept after capture for derive + publish; twice the projected derive of a full ~200-PR backfill (~3–4 min from the dry run's 13–17 s plus ~0.9 s per PR record), rounded up; the P2 backfill re-measures |
| `backfill_since` | 2026-07-31 | earliest `since`; floor of a fresh PR/brief cursor |
| `ambiguity_window_minutes` | 15 | code-basis ambiguity window |
| `edit_grace_seconds` | 60 | an edit at least this long after creation → `claimed` |
| `receipt_lookback_hours` | 48 | receipts re-list window (re-run attempts) |
| `continuity_horizon_days` | 90 | how far back the checkpoint scan reads (= artifact retention) |
| `watched_workflows` | the nine | runs that get receipts |
| `snapshot_id` | `pr843` | ingest subtree / receipt source |
| `snapshot_dir` | `audits/provenance-2026-10/rescue` | the snapshot's directory in the main checkout |
| `snapshot_commit` | `411a7565e1c6c8f2b96edf631286ceac798d7887` | the merge that brought it to main (recorded) |
| `snapshot_manifest_sha256` | `c713379b96e22480ebf40d5046adcee63802de5f47b82e1b3fea5eb63f1151c7` | the authenticity pin: sha256 of its `MANIFEST.sha256` |

There is no ref or path key for the snapshot and no `config --get`
subcommand. The live arming key is the `PROVENANCE_ENABLED` repository
variable (unset = disarmed — the house two-key convention of
`.github/reeve.conf` and `.github/backlog-groomer.conf`; compared
case-insensitively in both the YAML and `conf.armed`). Reeve's
`provenance-lag` threshold is Reeve's own `provenance_lag_hours` in
`.github/reeve.conf` (default 3).

## Workflow

`.github/workflows/provenance.yml`, "Provenance harvest (keyless)".

**Triggers.** `schedule: - cron: '29 * * * *'` (single-quoted — the form
`cadence-sync-check.sh` reads; two-key armed) and `workflow_dispatch` with
inputs `mode` (choice: `harvest` | `refreeze` | `recover` — owner decision 12;
the ingest is part of `harvest`), `since`, `until`, `pr`, `receipts_only`
(boolean), `max_requests`, `dry_run` (boolean), `bootstrap` (boolean),
`confirm_sha`. Rescue and backfill are both `harvest` with `since`.
Re-extraction needs no mode: the derived ref is recomputed whenever the
extractor version changes.

**Inputs** reach the code only through `env:` and are passed as CLI
arguments, where `cli.validate_inputs` full-matches each free-text one:
dates `[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)?`, pr
`[0-9]{1,7}(,[0-9]{1,7}){0,49}`, sha `[0-9a-f]{40}`, cap `[0-9]{1,5}`; the
booleans become flags. No `${{ inputs.… }}` or `${{ steps.… }}` appears
inside a `run:` block.

**Permissions.** Workflow default `contents: read`. The `gate` job: `contents:
read`, `actions: read`. The `harvest` job adds `contents: write` (data-ref
pushes only) plus read on `actions`, `pull-requests`, `issues`, `statuses`,
`deployments` (no `checks`: nothing reads check runs).

**Jobs.**

- `gate` — no concurrency group; job-level `if: github.event_name ==
  'workflow_dispatch' || vars.PROVENANCE_ENABLED == 'true'`, so a disarmed
  schedule's run is skipped outright (every job skipped: it costs nothing and
  uploads nothing). Checks out the default branch, runs `provenance gate`:
  `go` = the conf's `enabled`, and on a schedule also `conf.armed` and no
  OTHER provenance.yml run whose status is `queued`, `in_progress`, `pending`,
  `waiting` or `requested` in one unfiltered runs-list GET (a run blocked on
  the concurrency group reports `pending`/`waiting`; GitHub keeps one pending
  run per group and a newly queued run replaces it — without this check the
  :29 schedule would silently cancel an operator's pending backfill or
  refreeze).
- `harvest` — `needs: gate`, `if: needs.gate.outputs.go == 'true' &&
  github.ref == format('refs/heads/{0}',
  github.event.repository.default_branch)` (the full ref, so a tag named like
  the default branch never matches), job-level
  `concurrency: {group: provenance-writer, cancel-in-progress: false}`,
  `timeout-minutes: 350`. Steps:
  1. checkout (`ref` = default branch, `fetch-depth: 0`,
     `persist-credentials: false`);
  2. **plan** — `python3 -m provenance <harvest|refreeze|recover> … --out-dir
     .provenance`, env `GH_TOKEN` (read use only), `PYTHONPATH=
     tools/provenance/src:tools/model-registry/src`; it performs the
     token-less bulk fetch itself. An input the selected mode does not use is
     refused (`::error::`, exit 1), never silently dropped — recover's
     `dry_run` included, since recover has no dry run;
  3. **declare** — two `actions/upload-artifact` steps, `name:
     intent-<ref>-<sha>`, `retention-days: 90`, each `if:` its ref changed;
  4. **publish** — `python3 -m provenance publish`, env `GH_TOKEN` (the only
     step that pushes);
  5. **checkpoint** — two `actions/upload-artifact` steps, `name:
     tip-<ref>-<sha>` (file `.provenance/tip-<ref>.json`), `retention-days:
     90`, each `if: !cancelled() &&` publish named a verified tip for that ref
     (a no-op run checkpoints too; `!cancelled()` because publish can exit
     non-zero after a verified evidence push);
  6. **verdict** — fails the job (exit 3, `::error::`) when the plan found a
     foreign evidence tip — after the derived overwrite and the checkpoints;
     a second verdict step fails it (exit 1) when the plan reports
     `derive_error` (a derive layer raised: the evidence was published and
     checkpointed, `provenance-site` was not rebuilt), and a third (exit 1)
     when it reports `receipts_error` (a run's jobs GET or a workflow's
     listing failed after retries — isolated, §Receipts; everything else was
     published and checkpointed);
  7. **summary** (`if: always()`) — `.provenance/summary.md` →
     `$GITHUB_STEP_SUMMARY`: mode, requests used / 304s, receipts full/stub,
     units frozen / pending / deferred / re-captured, `unknown.step` and
     `unknown.marker` counts, ingest counts, continuity verdicts and the
     checkpoint shas, guard drift, any skip reason, the evidence and derived
     shas, and the packed sizes of both refs.

**One job, not two.** Splitting into a read-only `plan` job and a
`contents: write` `publish` job would keep the write token away from the
process that parses untrusted payloads, but Actions concurrency cannot hold a
lock across two jobs: with both jobs in `provenance-writer`, a later run's
`plan` can start between this run's `plan` and `publish` (planning against a
tip that is about to move), and a newly queued job replaces the group's one
pending job — a later `plan` would cancel this run's pending `publish`. So
the harvest stays one job, and the residual is recorded in
`docs/actions-security.md`: the process that parses API payloads and runs
`git merge-tree` on fetched PR objects holds `contents: write` for this
repository's unprotected branches. Mitigations: the token reaches only the
plan and publish steps' environment, pushes go through `gitstore` alone with
an env-only credential, git runs with hooks, fsmonitor and non-https
transports disabled, no PR content is checked out, and the payload parsing is
stdlib JSON.

**Keyless.** No `secrets.` reference, no claude-code-action, no
`AI_ANDON_CORD` gate leg (`tools/provenance/tests/test_workflow.py` pins all
three). Runtime: the runner's system Python, stdlib only, no pip.

## Registration

| Where | What | Builder |
|---|---|---|
| `tools/reeve` | `ROUTINE_WORKFLOWS += provenance.yml` (routine-dead). Detector `provenance-foreign-tip`: either ref's verdict under the continuity rule — a port of `gitstore.continuity_verdict` (upload-time mark order, the 6 h read-on, the checkpoint cross-check) over the same artifact scan (`GET /actions/artifacts`, run verification, `git/ref/heads/<ref>`, `GET /git/commits/<sha>` for first parents, `GET /compare/{other}...{C}` for the evidence checkpoint's ancestry), passing every row of the shared `tools/provenance/tests/fixtures/continuity_cases.json` so the two implementations cannot drift (a mark's run head is checked by reachability, §Tip continuity residuals); `foreign`, `deleted` and `unanchored` are findings. Detector `provenance-lag`: (a) the oldest pending unit past its anchor `+ provenance_lag_hours` (`GET contents/state.json?ref=provenance`) — the anchor is `due_at`, or `defer_until` for a unit deferred by design (every reason `in-flight-run` or `deployment-pending`), and (b) the **stall check** — one page of `/pulls?state=closed&sort=updated&direction=desc`: any PR closed more than `settle_hours + max_defer_hours + provenance_lag_hours` ago, last updated more than `provenance_lag_hours` ago and not before `backfill_since`, that is in none of frozen (the `raw/pr` tree listing), `pending` or `skipped` means the harvester has stopped seeing PRs (dropped schedule slots, a failing gate, a dead job) even though nothing is pending. Both report "not evaluated" only while `PROVENANCE_ENABLED` is unset (reeve.yml passes the variable's raw value, the andon pattern), offline, or when the armed gather itself failed (named in the reason; the rest of the report still renders); once armed, an absent ref is a finding. Every read lives in ONE module, `tools/reeve/src/reeve/provenance.py` (the read lens allow-lists it). Golden report pairs updated, each detector with a positive and a negative control; `provenance_lag_hours` key in its conf parser | H6 |
| `scripts/cadence-sync-check.sh` | `ROUTINES += provenance` (conf raw cron `29 * * * *` ↔ the workflow's single-quoted literal) | H6 |
| `scripts/ci-classify.sh` | new output `provenance_tests` (true for `tools/provenance/*`, `.github/provenance.conf`, `.github/workflows/provenance.yml`, `.github/data-branch-guard/*`, `site/lib/provenance-contract*`, `site/test/fixtures/provenance-bundle.json`, `scripts/provenance.sh`, the drift-pinned `scripts/reviewer-posted.sh` / `coach-lock-check.sh` / `reviewer-signoff.sh` / `.claude/reviewer-post/reviewer_mcp.py`, `tools/model-registry/*`, `audits/provenance-2026-10/fixtures/*`, `audits/provenance-2026-10/rescue/*` (the pinned snapshot), `site/lib/timeline.mjs`, Reeve's port `tools/reeve/src/reeve/provenance.py`, `ci.yml`), and a second output `provenance_read_lens` (any change under `scripts/`, `tools/`, `.github/`, `.claude/` or `site/` — the read lens's scan roots — on which `provenance-tests` runs only `test_read_lens.py` plus the sub-second pins that read files under those roots — `scripts/check.sh`'s selftest line, the watched workflows' existence, Reeve's mirrored deferral reasons and mark-order slack — so a new data-ref reader, or a change that breaks one of those pins, fails its own PR, not the post-merge push); `tools/provenance/*` and `.github/provenance.conf` join the soft-infra and required-context lists; the reeve-tests trigger also fires on `tools/provenance/tests/fixtures/continuity_cases.json`, `.github/provenance.conf` and `tools/provenance/src/provenance/freeze.py` (reeve's suite text-pins all three), and the provenance-tests trigger on `tools/reeve/src/reeve/provenance.py` (the harvester's suite pins Reeve's port back); the header's output count and the `--selftest` rows. (The timeline.mjs ↔ Python row parity itself runs in `site-build`, on every PR — §Episodes.) | H6 |
| `.github/workflows/ci.yml` | a `provenance-tests` job (`python3 -m pytest tools/provenance -q`, or the read lens alone) gated on either output and listed in `ci-ok`'s `needs` (`scripts/ci-ok-guard.sh`) | H6 |
| `scripts/check.sh` | `scripts/provenance.sh --selftest` | H6 |
| `CLAUDE.md`, `README.md` | the `tools/provenance/` bullets, `provenance.sh` in the scripts bullet, this document in the docs bullet (landed with the scaffold; `scripts/docs-check.sh`) | scaffold |
| `docs/actions-security.md` | a row: provenance.yml holds `contents: write` via `GITHUB_TOKEN`, is keyless and dispatchable; the default-branch `if:` is defense in depth; tip continuity (checkpoints, monotonic) is the control; the residuals of §Tip continuity — a forged derived tip lives until the next run (until the next dispatch while disarmed), a rollback to the newest checkpoint is accepted, the single job parses untrusted payloads while holding `contents: write` (§Workflow), and the optional Environment lever for `recover` | H6 |
| `docs/andon-cord.md` | a coverage row: provenance.yml is keyless and keeps running while the cord is pulled | H6 |
| `tools/provenance/tests/test_read_lens.py` | live with the scaffold (architect-owned): the two pinned patterns, one negative control per form, and the allow-list (`tools/provenance/`, the workflow, `tools/reeve/src/reeve/provenance.py`, `tools/reeve/tests/`, `site/lib/provenance-*`, `site/test/`) — #646 | arch |

## Sizes

Measured from the #843 snapshot with the real receipt writer (67 days,
2026-08-01 → 10-13): 3,738 receipts = 3.9 MB gz (full 2.6 MB, stubs
1.3 MB), the ci.yml listing 146 KB, 1,689 status files 758 KB — about 4.8 MB
for the ingest. Annualised, receipts grow about 21 MB/year and raw PR/brief
digests about 3 MB/year. `state.json` is rewritten by every evidence commit
(about one an hour once armed, since some watched routine runs most hours):
it holds about 1 KB of cursors, a handful of pending units and the skipped
PRs (about 35 B each, ≈ 40 KB/year at the measured rate — frozen units are no
longer listed in it), and git stores successive versions as deltas of a few
hundred bytes, so its history adds well under 5 MB/year — under the 30
MB/year line at which the owner is to be asked about partitioning (the plan's
P1e rule) in total. Fourteen workflows check out with `fetch-depth: 0` and so
fetch both refs; the derived ref is one squashed commit and adds only its
current tree. The harvest job alone also fetches every PR head (bounded by the
repository's total object size, 268 MB on 2026-10-14, most of which the
checkout already holds). The measured packed size of both refs (`git
count-objects -vH` after a fresh `git fetch origin provenance
provenance-site`), the added fetch time of a full-depth checkout and the
PR-head fetch time are recorded on the P2 checklist (§Acceptance map) once
the refs exist — this build pushes nothing.

## Failure modes

| Failure | Detection | Effect | Recovery |
|---|---|---|---|
| Another `contents: write` holder (the deliverers' owner PAT, `REGEN_TOKEN`, a contents-write job, an attended session) pushes to `provenance` (forged commit or rollback) | tip continuity at the next run; Reeve `provenance-foreign-tip` | no evidence written; the derived ref is recomputed from the newest checkpoint and overwritten; the run goes red (exit 3) | inspect; `recover confirm_sha=<newest checkpoint>` |
| A forged `provenance-site` tip | tip continuity / `same_content`; Reeve | overwritten at the next run with `::error::`, whatever the evidence ref's state; until then (and until the next dispatch while disarmed) it can show false attribution (escaped fields only; nothing reads it before P3) | automatic |
| The `provenance` ref is deleted | continuity verdict `deleted` | run red; never re-bootstrapped; the derived ref is still rebuilt from `C`, fetched by sha | `recover` to the newest checkpoint, or push exactly that sha from any clone |
| Artifact ids out of upload order (measured up to 64 min) | ordering by `(created_at, id)`; the scan reads on 6 h past the newest tips | none: a genuine newer tip stays ok, a rollback to an older higher-id checkpoint is foreign | none needed |
| The newest checkpoint does not descend from another verified one (a mark-order conflict) | `checkpoint_conflicts` (evidence) | verdict foreign with `conflicts`; no evidence, no derive, `recover` refused; run red | inspect the artifact list; push the true newest checkpoint from a clone that holds it |
| Harvester published nothing for 90 days (checkpoints expired) | Reeve `provenance-lag` stall check and `routine-dead` long before | verdict `unanchored`: refused (no run may re-anchor a tip nobody verified) | rename the old ref (it keeps its history), then dispatch `harvest bootstrap=true`: a new root, the ingest re-runs from main, and PRs re-freeze from GitHub plus what the snapshot holds |
| A guard rule would break | `guard_diff` | exit 4, nothing pushed | a bug: fix the writer, never the guard |
| `.github/data-branch-guard/*` changes on main | guard drift check | `::warning::`; the evidence ref keeps its bootstrap bytes, the derived ref takes the new ones | none needed; a re-root only if the evidence ref must carry the new guard |
| A push is rejected or the remote tip moved since the plan | `publish` | `::error::`, exit 3; nothing further pushed | inspect: inside the concurrency group only a foreign writer can move a tip |
| Push transport failure after 3 retries | `publish` | exit 1; the declared intent is harmless | next run |
| The bulk PR-head fetch fails | `fetch_all` | evidence still published, no derived push that run (`derive_skipped`) | next run |
| A derive layer raises (a bug in views/bundle/episodes/serving, or a blame that does not cover a design file) | plan step `::error::`, `derive_error=true` | evidence still published and checkpointed, no derived push; the derive verdict step fails the job after the checkpoints | fix the bug; the next run rebuilds `provenance-site` |
| Rate-limit floor / request cap / capture deadline (the continuity scan included) | `BudgetExhausted` | clean stop, cursors saved, exit 0; a stop inside the continuity scan is a no-op plan (old == new == the fetched tip, verdict unknown) that publishes and checkpoints nothing | next run / next dispatch |
| A filtered runs list would hit GitHub's 1,000-result cap | `total_count` check | the window is halved; a one-minute window still capped fails that workflow's listing loudly (receipts pass error, below) | none expected (a minute holds far fewer than 1,000 runs) |
| Receipts pass error — a run's jobs GET or a workflow's listing still fails after the client's retries (a persistent 5xx, a 403, `total_count` disagreeing twice) | `receipts_error=true`, `::error::` per failure, `counts.receipts.failed` / `errors` in `plan.json` | isolated to that run / workflow: its cursor holds at the failure, every other receipt, the ingest and the freezes are published and checkpointed; `Verdict (receipts)` fails the job | none for a transient; the next pass retries. A persistent one stays red hourly until fixed (or until GitHub deletes the run — then a 404, `gone`) |
| A scheduled run would evict a pending dispatch | the `gate` job | the schedule skips that hour | none needed |
| GraphQL unavailable | `GraphQLUnavailable` | `incomplete: graphql-unavailable`, thread counts absent | `refreeze` later |
| A watched run still in flight at 24 h | settle | frozen with `incomplete: settle-deferred` | `refreeze` |
| A PR reopened after it was frozen, or a brief reopened | the closed listing vs the stored revision | next revision once it closes again and settles | none needed |
| Refreeze after GitHub deleted the runs and statuses | — | the retention-bound sections are carried from the previous revision | none needed |
| A fifth step-naming era | `unknown.step` in the summary; receipts kept full | serving gives `none` for it | add the era to `steps.py` (version bump) |
| A new marker family / lead line | `unknown.marker` counts | not rendered | extend markers/digest (version bump) + `refreeze` |
| A historical `registry.conf` the strict parser refuses | basis `none`, `codebasis-unavailable` | model not shown | none — never guessed |
| A run head that was force-pushed away | not local after the fetch | basis `none`, `codebasis-unavailable:<sha8>` (5% of auto-review heads in the snapshot) | none — never guessed |
| Overlapping routine windows, or an owner artifact without the claimed-issue key | containment / `run_claims` | model null or trust `login` | v2 receipt status |
| A registry/workflow change on main within 15 min of a PR run (or of the Oracle's checkout) | ambiguity window | `ambiguous` | none — never guessed |
| Force-pushed PR branch | heads missing from `/commits` | `incomplete: force-pushed-heads`; rounds by `pushed_at` | none |
| Vercel builds a data-ref push | Vercel's own deployment state for the pushed sha | a preview deploy | the console's Ignored Build Step / git settings (owner) |
| The snapshot does not match its pin or manifest | `verify_manifest` | ingest refused, nothing planned | inspect main's `audits/provenance-2026-10/rescue/` |
| A re-run attempt older than 48 h | — | not re-captured | `harvest since=` |
| GitHub's scheduled delivery drops slots | Reeve `routine-dead` / the `provenance-lag` stall check | catch-up at the next delivered slot (idempotent) | none |

## Out of scope (v2 and later)

- **P0.1** log-fact salvage (needs probe outcome B and owner decision 4).
- **P2** arming `PROVENANCE_ENABLED` and the backfill dispatches.
- **P3** every site change: the `SITE_FETCH_PROVENANCE` seam, "How it was
  made", the history route, "Built on" lineage, `people/actors.conf`, the
  derived roster, the `SITE_FETCH_HISTORY` cutover.
- **P4** the isolated routine receipt status; **P5** the weekly drift audit,
  a deploy hook, a `provenance` ruleset.
- No MCP provenance stamp, no CodeRabbit/Copilot/Bugbot prose, no
  text-matched finding→fix edges, thread resolution as counts only, no
  per-SHA check runs.

## Resolved questions

Points the approved plan left open or stated differently, resolved here:

1. **Merge-of-main heads are rounds.** The plan said merge-main heads "fold";
   the audit's golden timelines (NVC-1 = 15, NVC-8's `R:636:f4e36eb9`) count a
   push whose head is a merge of main as a round. The golden wins: merge-main
   *commits* fold into their push, a merge-main *head* is an author push.
2. **Regen folds by identity, not by trailer.** Every regen commit-back
   (REGEN_SUBJECT + REGEN_AUTHOR + one parent) folds, including pre-#470 ones
   with no `Preview-Diff` trailer (`77cbb164` on #636); the trailer is a field.
3. **Push evidence includes statuses.** ci.yml runs alone miss #634's three
   web commits; any commit status marks a pushed head. So statuses are read
   with `/commits/{sha}/statuses` (the list, with `creator`, superseded
   per-round statuses included) for **every** PR commit, not the combined
   `/status` per head the plan named.
4. **Stickies are not events.** `AUTO_REVIEW_STAMP`, the gate report and the
   argus report are edited in place and keep only the last round; they are
   counted (`sticky.*`), and the per-round truth comes from statuses and
   sign-offs. No `ci.sticky` kind was added.
5. **`brief.withdrawn` added.** `🚢 SHIP-LOCK WITHDRAWN` (59 occurrences) is
   the closing bracket of a failed claim; without it a dead run's claim reads
   as live.
6. **The digest carries more than the plan's five fields** — `head_marker`,
   `suffix_markers`, `footer_ok`, `lead`, `lead_fields`, `refs_closes` — so the
   coach-lock rule, the Oracle rule, coach rounds, SHIP-LOCK design names and
   brief links survive the body being dropped. `suffix_ok` is defined as "the
   last suffix marker is an MCP completion shape"; trust adds the author.
7. **raw@1 payloads are closed projections**, not complete payloads, to keep
   prose and volatile fields out and make refreezes byte-stable.
8. **Contended pushes are not rebuilt** and are foreign. A rebuilt commit
   would carry no declared intent, and inside the concurrency group no other
   default-branch harvester can move the tip, so any rejection is exit 3
   (revised in the critique round: the earlier "declared → warning, exit 5"
   case cannot occur).
9. **Intents are declared between plan and publish**, as two CLI steps
   (`harvest`/`refreeze`/`recover` plan; `publish` pushes), with
   `actions/upload-artifact` in between; a declared-but-unpushed sha is
   harmless. Checkpoints (`tip-<ref>-<sha>`) follow every successful publish.
10. **The no-op test compares content, and nothing but the bundle's meta
    depends on main.** Revised in the critique round: the view no longer
    carries `main_sha` (it digested into `content_sha256`, so every main push
    churned the derived ref), committed rows point at the commit that added
    them, and `same_content` reads the tip's blobs instead of trusting its
    `content_sha256` field.
11. **Receipt paths carry the attempt** (`.a<attempt>`), so a re-run is a new
    add-only path rather than a modification.
12. **Ingest scope**: watched-workflow receipts, the ci.yml listing and
    statuses only; check runs, PR commits and pulls are not ingested (re-
    readable, or not part of the design). Revised: the snapshot is on main
    (merge commit `411a7565`), read only from the default-branch checkout and
    pinned by its manifest digest; the scope is reversible by an ingest
    version bump.
13. **`codebasis.py` and `protocols.py` were added** to the module list:
    serving stays pure behind a `CodeBasis` protocol, and the git-backed
    implementation composes `gitstore`'s read primitives with the
    model-registry parser without running git itself. **`freeze.py` and
    `selftest.py`** hold the capture sequences and the selftest aggregator.
14. **Window attribution needs the right identity** (`ROLE_IDENTITIES`), so an
    owner-token sign-off inside a reviewer's job window is never attributed to
    that job.
15. **The Oracle's and wright's two chains** are told apart by the step's lead
    and provider (`CHAIN_DISCRIMINATORS`).
16. **Unparseable historical registries give `none`**, not a lenient parse.
17. **Revision numbering**: revision 1 is the bare path, `.r<K>` from K = 2;
    an open brief linked to a frozen PR is revision 1 with `brief-open`.
18. **`deploy.production` links the merge commit**, because every URL is
    constructed and GitHub has no per-deployment page; the deployment id is a
    field.
19. **The house arming convention**: the conf ships `enabled: true` and the
    `PROVENANCE_ENABLED` variable unset (disarmed); a dispatch's `go` is the
    conf's `enabled` alone, so the bootstrap and backfill can run before
    arming; a disarmed schedule's run is skipped outright.
20. **Reeve owns its lag threshold** (`provenance_lag_hours` in reeve.conf)
    rather than reading provenance.conf.
21. **GraphQL in the sandbox** returns 403, so the fixtures carry thread
    counts from the sandbox's CCR review-thread route (`threads.source:
    "ccr-fixture"`); production uses the one GraphQL query, tested on canned
    responses.

Resolved in the adversarial review of the frozen design (2026-10-14; the
per-item dispositions, including the two rebutted fixes, are in the build's
work plan):

22. **Checkpoints, not a run window.** Tip continuity anchors on the newest
    `tip-<ref>-<sha>` checkpoint, uploaded by every successful publish
    including no-op ones and found by reading the repo's artifact list; the
    rule is monotonic in upload time (`created_at`, never the artifact id,
    which round 2 of the integration review measured out of order by up to
    64 minutes), so a rollback to an older genuine sha is refused, and nothing
    bootstraps without `bootstrap=true`.
23. **`recover` restores only the newest checkpoint**, and only while the tip
    fails continuity; an Environment gate on it is optional, not wired.
24. **A foreign evidence tip no longer freezes the derived ref**: derive runs
    from the newest checkpoint and the forged derived tip is overwritten, then
    the run goes red.
25. **The ingest is not a mode and reads only main**, pinned by
    `snapshot_manifest_sha256`; tar members are regular, flat `*.json.gz`
    files read with `extractfile`.
26. **One bulk, token-less fetch at job start**; derive fetches nothing but,
    on a foreign evidence tip, the newest checkpoint `C` by sha, and a
    commit missing after it is a deterministic basis `none` — not a
    fail-closed derive, which the 67 force-pushed-away auto-review heads in
    the snapshot would have wedged forever.
27. **The owner's token needs the claimed issue as a key** (§Serving-model
    join), so an attended owner PR inside a routine window stays `login`.
28. **Direct-to-main commits** exclude PR subjects, GitHub-committed commits
    and frozen PRs' commits; an unfrozen PR's merge yields no record.
29. **Frozen state lives in the tree's `raw/` paths**, not in `state.json`;
    a changed terminal state (reopened, re-merged, re-closed) adds the next
    revision; later revisions carry the retention-bound sections forward.
30. **Content identity is the decompressed canonical JSON**, never gzip bytes.
31. **Guard files are written once, at bootstrap**; drift from main is a
    warning, never a bricked writer.
32. **The harvest stays one job.** Actions concurrency cannot lock across a
    plan job and a publish job (a later run's plan interleaves, and a newly
    queued job replaces the group's one pending job); the residual is
    recorded instead (§Workflow).
33. **The timeline.mjs parity runs in the site's suite** (it needs
    `marked`), which `site-build` runs on every PR; and the `ingest` and
    `config` subcommands and `check --ref` are cut (N6).

## Acceptance map

The plan's acceptance criteria and where each lives (every placeholder test's
docstring states its criterion; skip markers are removed as builders land
them; `tests/test_integration_complete.py` fails once integration flips its
`INTEGRATED` flag if any stub or placeholder survives).

| Phase | Criterion | Test |
|---|---|---|
| P0 | guard negatives: D, M under receipts/raw, raw file → 0 B, guard-file change | `test_gitstore.py::test_guard_refuses_*` |
| P0 | tip continuity: the shared table (ok, quiet day, died-before-checkpoint, forged, rollback, deleted, unanchored, bootstrap, derived) | `test_gitstore.py::test_continuity_table` (live) |
| P0 | foreign tip → `::error::`, nothing pushed to evidence, the derived ref rebuilt from the checkpoint, non-zero | `test_cli.py::test_foreign_evidence_tip_derives_from_checkpoint`, `test_forged_derived_tip_is_replaced` |
| P0 | a quiet day keeps the tip; a deleted ref after it is refused; a rollback is refused | `test_gitstore.py::test_quiet_day_then_deleted_ref`, `test_rollback_to_an_older_declared_sha_is_refused` |
| P0 | `recover` refuses while continuity holds, and any sha but the newest checkpoint | `test_cli.py::test_recover_*` |
| P0 | bootstrap only with the flag; the ingest runs once, from the pinned snapshot | `test_cli.py::test_bootstrap_needs_the_flag`, `test_auto_ingest_runs_once`, `test_ingest.py` |
| P0 | run 31364447108 stored complete; a disarmed run is a stub; windows survive the 1,000 cap | `test_receipts.py`, `test_steps.py` |
| P0 | no token or its base64 in a failing push's error | `test_gitstore.py::test_push_error_never_carries_the_token` |
| P0 | workflow keyless, no inputs in `run:`, job-level permissions, step order, modes | `test_workflow.py` |
| P0 | purity: network only in github.py, git only in gitstore.py | `test_purity.py` (live) |
| P1a | membership P/R on the tuned and held-out sets | `test_membership.py` |
| P1a | CC-1, NVC-6, NVC-7, CC-6, verified = 12 | `test_acceptance.py`, `test_trust.py` |
| P1a | every reviewer-posted.sh selftest row agrees; FOOTER drift pin | `test_trust.py`, `test_digest.py` (live) |
| P1a | no fixture field outside the contract (no prose) | `test_contract.py`, `test_fixtures.py` (live) |
| P1b | NVC-1, 8, 9, 11, 12b, 13, 14; SBC-1, 6, 7 (sbc-case threads across #371 + #397: 26 total / 6 resolved — #371 4/0, #397 22/6); sbc-case's 31 sign-offs, 15 from PR review bodies, matched to the golden; CC-5, 7; NVC-12 re-baselined | `test_acceptance.py`, `test_episodes.py`, `test_extract.py` |
| P1b | merge-method fixtures map blamed rows (original line, adding commit); direct-commit rule; extractor has no clock | `test_extract.py`, `test_episodes.py`, `test_purity.py` |
| P1b | timeline.mjs ↔ Python row parity over every design | `site/test/provenance-rows.test.mjs` (site-build, every PR) |
| P1c | NVC-2, 3, 4, 5; merge-tree basis; 5-minute ambiguity; oracle at its checkout; pre-#326 pin; overlapping windows; owner key negatives; missing commit = none; basis always set | `test_serving.py`, `test_codebasis.py` |
| P1d | fixture bundle byte-identical (in memory); both validators accept, both reject an extra field; one view per design; no-op rerun; a main commit outside designs/ pushes nothing; forged tip with a copied digest replaced | `test_bundle.py`, `test_views.py`, `test_cli.py` |
| P1e | gate semantics; no-op pushes nothing; 2 h pending / 7 h frozen / 24 h forced; changed terminal state; refreeze after retention; cap 5 stops and resumes; refreeze adds r2; cadence-sync; Reeve goldens incl. the stall check and the shared continuity table; read lens | `test_cli.py`, `test_freeze.py`, `test_github.py`, `test_receipts.py`, `test_read_lens.py` (live), tools/reeve tests, `cadence-sync-check.sh --selftest` |

**P2 checklist** (post-merge, live — this build pushes nothing, so these move
here from P0 and P1e):

- the bootstrap dispatch (`harvest bootstrap=true receipts_only=true`): the
  root carries the guard files, the ingest's 3,738 receipts and 1,689 status
  files, and receipts from 2026-10-11T06:13:35Z on; its summary's receipt
  count equals the snapshot's watched rows ∪ the windowed live listing;
- a repeat dispatch pushes no commit and uploads both checkpoints;
- the backfill (`harvest since=2026-07-31`, ≈ two dispatches): no job exceeds
  5.5 h, no sibling routine logs a rate-limit failure, and the measured derive
  time replaces `derive_reserve_minutes`;
- Vercel shows no deployment, or CANCELED, for every pushed sha;
- the packed size of both refs, the full-depth checkout's added fetch time and
  the PR-head fetch time are recorded here; projected evidence growth above
  30 MB/year is raised to the owner;
- arm `PROVENANCE_ENABLED` (owner decision 8).
