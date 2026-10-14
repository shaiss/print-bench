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
says what and why.

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
     │   1 fetch refs, tip continuity                          │
     │   2 receipts pass (watched workflows' runs → jobs)      │
     │   3 freeze pass (settled PRs / briefs / releases)       │
     │   4 add-only evidence commit + diff-tree guard          │
     │   5 derive records → views → bundle (pure)              │
     │   6 plan.json + intent files → upload intent artifacts  │
     │   7 publish: ff push provenance, lease push -site       │
     └───────────┬───────────────────────────────┬────────────┘
                 ▼                               ▼
   refs/heads/provenance               refs/heads/provenance-site
   EVIDENCE · linear · add-only         DERIVED · one squashed commit
   receipts/ raw/ state.json            records/ views/ site/bundle.json
                 │                               │
                 └──── tip continuity: every tip must be a sha a ────┘
                       previous default-branch run declared
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
4. **Tip continuity** — both refs' tips must be shas a default-branch
   harvester run declared in an artifact; anything else is refused and
   reported.
5. **The site seam** (P3, not in this build) — reads the bundle by sha.

## Freeze units and settle rules

Late activity never mutates a frozen unit. A unit is captured **once** into
revision 1; only `refreeze` adds revision K ≥ 2; every reader folds the
highest revision.

| Unit | Due | Freezes when | Stored |
|---|---|---|---|
| Run receipt | as soon as the runs list shows it `completed` | `conclusion != skipped`, workflow ∈ `watched_workflows` | `receipts/YYYY/MM/DD/<run_id>.a<attempt>.json.gz` (full or stub, §Receipts) |
| PR | `closed_at + settle_hours` (6 h) | at/after due, **and** no watched run on its head branch is queued/in progress, **and** (merged) its Production deployment is terminal or `merged_at + deploy_wait_hours` (2 h) passed. Otherwise deferred; at `closed_at + max_defer_hours` (24 h) frozen anyway with `incomplete` naming why | `raw/pr/<n>.json.gz` (`raw-pr@1`) |
| PR with no `designs/` file | — | never captured | `state.skipped.pr` |
| Brief issue (`design-brief`) | `closed_at + settle_hours` | as a PR; an OPEN brief a frozen PR links is captured as revision 1 with `incomplete: brief-open` and captured again (next revision) once it closes and settles | `raw/brief/<n>.json.gz` (`raw-brief@1`) |
| Release | on publish (non-draft) | immediately | `raw/release/<tag>.json.gz` (`raw-release@1`) |
| Direct-to-main commit | — | derived from local git; no API | `records/commit/<sha40>.json` only |

Revision paths: revision 1 is `<key>.json.gz`; revision K ≥ 2 is
`<key>.r<K>.json.gz`. `state.frozen.<kind>.<key>` records the highest
revision. Settle times derive from `closed_at` (no wall clock is stored);
`now` is read once by `cli.py` and passed down.

## Storage: the two refs

Both refs are unprotected branches pushed with `GITHUB_TOKEN` by
`provenance.yml` only (the telemetry vehicle, #481). Every `on.push` in the
repository is filtered to main or tags, so pushes to the data refs trigger no
workflow.

### `provenance` — evidence, linear, add-only

| Path | Contents |
|---|---|
| `vercel.json` | bytes of `.github/data-branch-guard/vercel.json` (mode 100644) |
| `scripts/vercel-ignore-build.sh` | bytes of `.github/data-branch-guard/vercel-ignore-build.sh` (mode 100755) |
| `README.md` | generated at bootstrap from a template in `gitstore.py` ("evidence data branch — never hand-edit; see docs/provenance.md"); never changed after |
| `FORMAT` | `print-bench-provenance 1\n` |
| `state.json` | `state@1` — cursors, pending units, frozen revisions, skipped PRs, ingest records, versions. No wall-clock stamp. The only path a push may modify |
| `receipts/YYYY/MM/DD/<run_id>.a<attempt>.json.gz` | `receipt@1`, day-sharded by the run's `created_at` (≤ ~230 entries per day directory, measured) |
| `raw/pr/<n>[.r<K>].json.gz` | `raw-pr@1` |
| `raw/brief/<n>[.r<K>].json.gz` | `raw-brief@1` |
| `raw/release/<tag>.json.gz` | `raw-release@1` |
| `raw/snapshot/<id>/runs/ci.yml.json.gz` | `raw-snapshot-runs@1` (from the #843 ingest) |
| `raw/snapshot/<id>/statuses/<sha40>.json.gz` | `raw-snapshot-statuses@1` (from the #843 ingest) |

Every `*.json.gz` is deterministic gzip (mtime 0, empty filename, level 9) of
canonical JSON (§Canonical JSON). Each publish is one commit whose parent is
the fetched tip, pushed fast-forward only.

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
tip. Rebuilt every run; a run whose `content_sha256` equals the current tip's
pushes nothing (§Views). Re-extraction and refreeze never modify evidence: a
new extractor version simply produces a new derived tree.

## The add-only guard

`gitstore.py` is the only module that runs git. The evidence writer:

1. **Temp index.** `TreeBuilder` sets a temporary `GIT_INDEX_FILE`, seeds it
   with `git read-tree <tip>` (empty at bootstrap), writes each new blob with
   `git hash-object -w --stdin` and stages it with `git update-index --add
   --cacheinfo <mode>,<blob>,<path>`. `add()` of a path that already exists
   with the same blob is a no-op; with a different blob it raises
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
   `scripts/provenance.sh --selftest`.
4. **Push.** `git push origin <new>:refs/heads/provenance`, never forced.
   A transport failure is retried up to 3 times with the **same** commit. A
   non-fast-forward rejection is **not** rebuilt on the new remote tip (inside
   the `provenance-writer` concurrency group only a foreign writer can move
   the tip): the run re-fetches and runs tip continuity on the new tip — a
   foreign tip is `::error::` and exit 3; a declared one (another harvester
   run raced this one) is `::warning::` and exit 5, and the cursors redo the
   work next run.
5. **Credentials.** The checkout uses `persist-credentials: false`;
   `gitstore` passes `GH_TOKEN` to `fetch`/`push` only, through `git -c
   http.https://github.com/.extraheader=…` on that one invocation, never into
   `.git/config` and never in a logged argument.

The derived ref is written by `DerivedTreeBuilder` (a fresh empty index —
nothing inherited) and pushed with `--force-with-lease=refs/heads/
provenance-site:<planned old tip>`.

## Tip continuity

**The threat.** The design-run and backlog-burn ship steps run
`bypassPermissions` agents holding the owner PAT with `contents: write`; a
ruleset cannot restrict a branch to the Actions bot. So "single writer"
cannot be enforced at push time — it is checked at the next run instead.

**Declaring.** Before publishing, the harvest job uploads one tiny artifact
per ref it will move, named `intent-<ref>-<sha40>` (`intent-provenance-…`,
`intent-provenance-site-…`), retention 90 days, content `intent@1`
(`{format, ref, sha, parent, run_id, run_attempt}`). The upload happens
**between** the planning step and the publish step: a declared-but-never-
pushed sha is harmless (nobody else holds that object).

**Checking** (`gitstore.declared_intents`, `check_tip_continuity`), at the
start of every run, for each ref:

1. List the last `intent_window_runs` (20) runs of `provenance.yml` with
   `head_branch == "main"` and `event` ∈ {`schedule`, `workflow_dispatch`},
   newest first, keeping only runs whose `head_sha` is on main's
   first-parent history (local git; fetch-depth 0).
2. Read each run's artifact names (`GET /actions/runs/{id}/artifacts`),
   newest run first, stopping as soon as the tip is found — usually 2 GETs.
3. The tip must be one of the declared shas. Otherwise: `::error::`, nothing
   is written, exit 3 (red). Reeve's `provenance-foreign-tip` detector reports
   the same condition independently.

| Tip state | Intents ever seen in the window | Verdict |
|---|---|---|
| present, declared | — | ok |
| present, not declared | — | **foreign** → refuse (evidence); the derived ref is recomputed anyway and the foreign tip overwritten with `::error::` |
| absent | none | **bootstrap** → create the root commit |
| absent | some | **deleted** → refuse like a foreign tip |

**Recovery** (`recover --confirm-sha <sha40>`, dispatch only): reset
`provenance` to a sha that is itself a declared intent, with
`--force-with-lease` on the current tip — the only non-fast-forward write to
the evidence ref. An undeclared sha is refused.

**Residuals** (documented in `docs/actions-security.md`):

- a forged `provenance-site` tip can reach one Vercel deploy before the next
  harvest overwrites it (the site resolves the tip without API access). The
  content is limited to escaped structured fields with constructed
  permalinks, so the harm is false attribution, not script injection;
- intent artifacts expire after 90 days: a harvester stalled that long leaves
  no declared intent, and the next run refuses until a human re-bootstraps
  (rename the old ref, let the next run bootstrap, then re-ingest). Reeve's
  `provenance-lag` flags a stall long before that;
- the default-branch `if:` and checkout ref are defense in depth only: a
  dispatcher who selects another ref runs that ref's YAML (docs/actions-
  security.md). The control that holds is that such a run cannot declare an
  intent a main run accepts.

## The evidence digest

Bodies are never stored. At capture, while each body is still in memory,
`digest.py` replaces it with a digest that carries exactly what the
extractors need. Because the body is then gone, a new lead class or marker
shape cannot be applied to frozen units by re-extraction — it needs a
`refreeze` (comments and issues are outside Actions retention and can be
re-read), and every digest records its version.

### Body digest (`body-digest@1`)

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
| `digest` | `body-digest@1` |

Lead rules (first match wins, anchored at the start of the stripped lead line):

| Class | Pattern | Fields |
|---|---|---|
| `ship_lock_withdrawn` | `🚢 SHIP-LOCK WITHDRAWN` | `design_name` |
| `ship_lock` | `🚢 SHIP-LOCK` | `design_name` |
| `declined` | `🚢 DECLINED` | `design_name` |
| `deferred` | `🚢 DEFERRED` | `design_name` |
| `shipped` | `✅ **SHIPPED … #N` or `📦 **Draft PR opened: #N**` | `shipped_pr`, `design_name` |
| `decision_needed` | `🚦 DECISION NEEDED` | — |
| `coach_lock` | `🎓 COACH-LOCK` | — |
| `coach_round` | `Round <N><a-z?> — ` | `round`, `round_sub` |
| `bugbot_limit` | `<hN>Bugbot couldn't run - usage limit reached</hN>` | — |
| `qodo_paused` | `**ⓘ Qodo reviews are paused` | — |
| `clear_prs` | `**/clear-prs sweep` | — |

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
owner decision 5), branch names, status descriptions **of the
`reviewer-signoff` context only** (our own fixed sentences), workflow/job/step
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
`brief-open`, `commits-truncated` (> 250), `files-truncated` (> 3000),
`force-pushed-heads`, `no-ci-runs`, `statuses-unavailable:<sha8>`,
`receipts-missing:<run_id>`, `codebasis-unavailable:<sha8>`.

`captured` = `{run_id, harvester, digest}` (the fixtures use run 0 /
`fixture`).

## Receipts

The jobs response of an agent run is the only durable record of which chain
link served — and GitHub now deletes it after 90 days. Receipts copy it.

**Selection** — from the runs **list**, never by step name. For each
workflow in `watched_workflows` (auto-review, backlog-burn, chunker,
design-run, labeler, oracle, product-scout, spike-converter, wright):
`GET /actions/workflows/<wf>/runs?created=>=<cursor − receipt_lookback_hours>`
(all pages; under `--since`, oldest window first). Every run with `status ==
completed` and `conclusion != skipped` whose receipt path is absent gets one
`GET /actions/runs/<id>/jobs?filter=all` (paged; every attempt). Runs still
queued or in progress hold the cursor back for the next pass.

**The agent-step grammar** (`steps.py`, version 1) — a closed list of
anchored patterns, one per naming era, each with a fixture:

| Era | First seen | Shape | Model of record |
|---|---|---|---|
| E0 | 2026-08-12 (#200) | `Run /jane-review (unattended)` | inline `--model` pin |
| E1 | 2026-08-08 → 08-21 | `Run via Anthropic (Claude)`, `Ship via Z.AI (GLM)` | inline `--model` pin (pre-#326) |
| E2 | 2026-08-12 → 08-20 | `/jane-review via Z.AI GLM 5.2`, `/pm triage via Anthropic Opus 5` | inline `--model` pin (the name's label is a cross-check only) |
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
re-captured (documented residual).

## INGEST: the #843 snapshot

The repository's first runs expire from about 2026-10-30. PR #843 (branch
`ccr-d0be94c3-o4sati-rescue`, directory `audits/provenance-2026-10/rescue/`)
holds a GET-only snapshot taken 2026-10-13: `runs.tar` (one `<workflow>.json.gz`
per workflow, every run since 2026-08-01, 19,890 rows), `jobs.tar` (one
`<run_id>.json.gz` = `{run_id, jobs}` per non-skipped run of an agent-bearing
workflow, 4,485 runs), `sha.tar` (one `<sha>.json.gz` = `{sha, statuses,
check_runs}` per PR commit and head, 1,992 shas), `prcommits.tar`,
`pulls.json.gz`, `workflows.json.gz`, `capture.py`, `MANIFEST.sha256`.

**Locating it.** Dispatch `mode=ingest`. The snapshot ref and path default to
the conf's `snapshot_ref` / `snapshot_path` and may be overridden by the
`snapshot_ref` / `snapshot_path` inputs (validated, no `..`). `ingest.
materialize_from_ref` (through `gitstore`) runs `git fetch origin <ref>` and
`git show <ref>:<path>/<file>` for each manifest file into a temp directory.
Locally, `--snapshot-dir DIR` reads an extracted directory. The snapshot id
(`pr843`, conf `snapshot_id`) names the evidence subtree and the receipts'
`source`.

**Verification first.** Every line of `MANIFEST.sha256` is recomputed;
`runs.tar`, `jobs.tar` and `sha.tar` are required. A mismatch or a missing
file aborts the ingest with nothing planned.

**Mapping** (`S` = `pr843`):

| Snapshot member | Evidence path | Rule |
|---|---|---|
| `runs.tar/<wf>.json.gz` row with wf ∈ `watched_workflows`, `status == completed`, `conclusion != skipped`, + `jobs.tar/<id>.json.gz` `jobs` | `receipts/YYYY/MM/DD/<id>.a<attempt>.json.gz` | `receipts.build_receipt(wf, row, jobs, "snapshot:S")` — full or stub by the live rule. A watched run with no `jobs.tar` member is counted `missing_jobs` and skipped (the live pass still fetches it while GitHub has it) |
| `runs.tar/ci.yml.json.gz` | `raw/snapshot/S/runs/ci.yml.json.gz` | `raw-snapshot-runs@1`, every row projected (2,013 rows, 146 KB gz) |
| `sha.tar/<sha>.json.gz` with ≥ 1 status | `raw/snapshot/S/statuses/<sha>.json.gz` | `raw-snapshot-statuses@1`: statuses projected (descriptions kept only for `reviewer-signoff`), `check_runs_dropped` = the member's check-run count (1,689 files, 758 KB gz) |
| `prcommits.tar`, `pulls.json.gz`, `workflows.json.gz`, `capture.py`, `README.md` | — | not ingested: `/pulls/{n}/commits` and `/pulls` are outside Actions retention and are re-read at freeze; per-SHA check runs are not part of the design (never rendered) |

`state.json` `ingested.S` records `{manifest_sha256, receipts, statuses,
runs_listings}`.

**Idempotence.** A planned path already present with identical bytes is
skipped; present with different bytes (a live receipt captured first) is
counted as a `conflict` and never modified — the add-only rule wins. A second
ingest of the same snapshot plans no file and pushes nothing.

**Consumption.** `freeze.capture_pr` unions the snapshot's ci.yml rows (same
branch/commit filter) into a PR's `ci_runs` and `raw/snapshot/S/statuses/<sha>`
into its `statuses`, by id, live rows winning. A PR frozen in the P2 backfill
therefore keeps its pushed heads and per-round `reviewer-signoff` statuses
after GitHub deleted them.

**Order of operations.** P0 merges → dispatch `ingest` (≈ 0 API requests; one
`git fetch` of the snapshot ref) → dispatch `harvest receipts_only=true
since=2026-07-31` for runs after the snapshot window (or runs the snapshot
lacks) → P1e merges → the owner arms (P2).

## Capture sequences

**PR** (`freeze.capture_pr`, ~17–25 GETs; bodies digested at capture):

1. `/pulls/{n}`
2. `/pulls/{n}/files` (all pages; every PR — all three merge methods are
   enabled, so a first-parent diff of a rebase merge would see only its last
   commit)
3. `/pulls/{n}/commits` (survives branch deletion)
4. `/issues/{n}/comments`
5. `/pulls/{n}/reviews` and 6. `/pulls/{n}/comments` (counted, never rendered)
7. `/issues/{n}/timeline`
8. the GraphQL query (thread `isResolved` counts, `lastEditedAt`)
9. `/actions/workflows/ci.yml/runs?branch=<head_ref>` — rows kept when
   `pull_requests` holds `n` or `head_sha` is a PR commit — ∪ snapshot rows
10. `/commits/{sha}/statuses` for **every PR commit** and every ci-run head,
    ∪ snapshot statuses (a commit carrying any status is a pushed head —
    §Episodes)
11. merged: `/deployments?sha=<merge>&environment=Production` and each
    deployment's `/statuses`
12. `briefs` = the PR body's `refs_closes` ∪ the `claude/issue-<N>-*` head-ref
    number

Per-SHA check runs are not read (54% of the audit's full profile, never
rendered). `registry.conf` and workflow files are read with local git.

**Brief** (`capture_brief`): `/issues/{b}`, comments, timeline, GraphQL
`lastEditedAt`. **Release**: the `/releases` row itself.

**Selection** (`plan_freezes`): `/pulls?state=closed&sort=updated&direction=
desc` paged until `updated_at` < the PR cursor (minus the settle window), and
`/issues?labels=design-brief&state=all&sort=updated&since=<cursor>`; with
`--pr`, only those PRs.

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
| `id` | D | closed forms: `issue:<n>:filed`, `issuecomment:<id>`, `timeline:<id>`, `pr:<n>:opened\|merged\|closed`, `commit:<sha40>`, `status:<id>`, `run:<id>`, `job:<id>`, `deployment:<id>`, `release:<id>`, `row:<design>:<PM\|NOTES>.md:<sha256[:16]>:<k>` |
| `ts` | D | RFC3339 UTC to the second: `created_at` / `submitted_at` / author date / job `started_at`; day rows `YYYY-MM-DDT00:00:00Z` |
| `ts_precision` | D | `second` \| `day` |
| `tz` | D | `UTC` |
| `kind` | D | closed enum (below) |
| `episode` | J | `E0:brief:<n>` \| `R:<pr>:<author-push sha8>` \| `M:<pr>` \| `C:<sha8>` \| `D:<date>` |
| `pr`, `issue`, `sha` | D | the PR / issue / the sha the event is ABOUT (marker sha, commit, status target) |
| `head_sha` | J | the pushed head live at `ts` |
| `stale_sha` | J | the marker sha is not among its round's heads |
| `after_merge` | D | `ts > merged_at` |
| `url` | D | constructed from validated ids and OWNER/REPO, never copied from `html_url`; every stored event has one |
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
`file`, `line`, `line_sha256`, `added_in_pr`, `added_in_sha`;
`deploy.production` `state`, `deployment_id`; `release` `tag`, `prerelease`,
`assets`.

**Counted, never stored as events** (`noise_counts`, closed keys): third-party
bot comments by app (`comment.bot.coderabbit|cursor|qodo|vercel|entelligence|
copilot|other`), lead-classified noise (`comment.bugbot_limit`,
`comment.qodo_paused`, `comment.decision_needed`, `comment.clear_prs`,
`comment.unclassified`), reviews (`review.bot|empty_wrapper|human`), review
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
| `pr` | PR number | `state`, `created_at`, `closed_at`, `merged_at`, `merge_commit_sha`, `merge_method`, `head_ref`, `base_ref`, `briefs`, `designs` (`{design: {membership, kinds}}`), `rounds`, `threads` (`{total, resolved}`), `noise_counts`, `unknown`, `evidence` |
| `brief` | issue number | `issue`, `state`, `state_reason`, `created_at`, `closed_at`, `labels`, `design_name`, `prs`, `evidence` |
| `commit` | sha40 | `sha`, `committed_at`, `designs`, `evidence` (`source: git`) |
| `release` | tag | `tag`, `published_at`, `designs`, `evidence` |

Every record carries `format`, `kind`, `key`, `extractor`
(`provenance-extract 1`), `incomplete` and `events` (sorted by the event sort
key). `evidence` = `{raw, raw_sha256, revision, receipts, source}`.

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
`created_at`. Measured on the fixtures, this reproduces every round count the
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
`commit.*` → the round holding the commit; every other PR event → the round
whose `pushed_at` is the latest ≤ `ts` (the first round if `ts` precedes every
push); direct-to-main commits → `C:<sha8>`; committed rows → `D:<date>`.
`head_sha` = the live pushed head at `ts`; `stale_sha` = the event's marker
sha is not one of its round's `heads`; `after_merge` = `ts > merged_at`
(the event stays in its live round).

**verifies.** A `review.signoff`'s `edges.verifies` = the
`commit.design|fix|human` shas at or before its marker sha in commit order and
after the same family's previous sign-off sha.

**Committed rows** (`episodes.decision_rows`), parsed from main at the
harvest's main sha with line-for-line ports of `site/lib/timeline.mjs`:
`PM.md ## Decision log` table rows → `decision.pm_log`; `NOTES.md ## Field
test log` `### YYYY-MM-DD — …` → `field_test`; `NOTES.md ## Changelog` `###
<v> — YYYY-MM-DD — <t>` → `changelog`; and, new, `NOTES.md ## Decisions log`
/ `## Decision log` dated top-level bullets → `decision.notes_log`. Each row's
`added_in_sha` comes from `git blame`; `added_in_pr` from the first-parent
main commit containing it (`(#N)` squash or `Merge pull request #N`), or, for
a rebase-merged sha, from the PR record whose commits hold it. Row ids hash
the line's text, so a row keeps its id when lines above it move; the site
matches rows by `line_sha256` and renders the committed text from its own
checkout. Rows read "charter decision (PM.md) · added in PR #N" — "added in",
never "by" (#496).

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
   as the Actions bot; the ship routines as the owner's PAT and commit as a
   bot). One window → attributed; none → `none`; windows of two or more runs →
   `ambiguous`. An owner-token sign-off inside a reviewer window is never
   attributed to it.
3. **Code basis** — what each run checked out:
   - `schedule` / `workflow_dispatch` (design-run, backlog-burn and the other
     routines): `run.head_sha`, exact;
   - `pull_request` in `auto-review.yml`: the design-changes job checked out
     the merge ref and resolved the chain there, so `git merge-tree
     --write-tree <main@created_at> <run.head_sha>`, reading
     `.github/models/registry.conf` and the workflow from that tree;
   - `pull_request` in `oracle.yml`: base main, so `main@created_at`;
   - `main@T` = the last first-parent main commit with committer date ≤ T;
   - `ambiguous` when merge-tree conflicts on either file, or a main commit
     touching either landed within `ambiguity_window_minutes` (15) before
     `created_at` (the merge ref GitHub built may predate it).
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
   step by exact `- name:`), not a YAML parser.
5. **Job-level** (`job.reviewer`): the last non-skipped link step
   (`continue-on-error` masks step conclusions) with basis `job-link+…`;
   `posted` = some event of the record is attributed to that job (Drik's job
   in run 38161046420 tried all six links and posted nothing).
6. **Trailers.** `Co-Authored-By: Claude <Name> <noreply@anthropic.com>` →
   `model = Name` (e.g. `Claude Opus 5.5`), basis `trailer`, trust
   `claimed`; `Cursor Agent` → platform `cursor`, model null.

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
bot). On #636 this yields 12 verified sign-offs (6 Jane, 6 Drik) and 13
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
`counts` are derived.

**Bundle** (`bundle.py`, `bundle@1`): all views, `main_sha`, `evidence_sha`,
`producer_run`, `views_sha256` and `content_sha256` — a digest of the records'
digests, the views' digests and the extractor version, i.e. of everything
except the three meta fields. A run whose `content_sha256` equals the current
derived tip's pushes nothing, so `main_sha` reads "the main commit these views
were last recomputed against". No cursors, no pending list, no wall clock.

**Python↔Node parity.** `tests/test_bundle.py` regenerates
`site/test/fixtures/provenance-bundle.json` from committed synthetic records
(`tools/provenance/tests/fixtures/records/`: hand-authored, contract-valid,
every record kind and event field set) with fixed meta (main `521d0928…`, evidence `"0"×40`, run 1) and asserts byte
equality with the committed file; `site/lib/provenance-contract.mjs` and
`contract.py` must both accept it and both reject a copy with one extra
field. The site ignores unknown kinds and fields (forward compatibility); the
validators do not.

## Canonical JSON and the sort key

Canonical JSON (`canonical.py`): sorted keys at every depth, `indent=1`,
`separators=(",", ": ")`, UTF-8 (`ensure_ascii=False`), LF, one trailing
newline, no floats anywhere (refused), no NaN.

Event sort key: `(ts, precision rank [day < second], source rank, numeric
github id, sub-index, id)` — source rank is the id prefix order `issue, pr,
timeline, commit, issuecomment, status, run, job, deployment, release, row`;
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
| dispatch deadline | `dispatch_max_minutes` (330 = 5.5 h); cursors resume on the next dispatch |
| ETag | `If-None-Match` on every GET from `<out-dir>/etag-cache/`; a 304 is free and not counted |
| retries | 5xx, 403/429 with `Retry-After` or a secondary-limit message, socket timeouts: 3 retries (2/4/8 s); 401/404/410/422 not retried |
| pagination | `per_page=100`; `rel="next"` followed only on `api.github.com`; more than `max_pages` raises rather than truncating |
| nothing new | a run with nothing new writes nothing (tested) |

Measured costs: 4,089 runs of the nine watched workflows since 2026-07-31
(351 skipped) → about 3,740 jobs GETs + 45 list pages for receipts, of which
the #843 ingest covers everything through 2026-10-13 at ≈ 0 requests; about
3,700 GETs for the 202 design-touching PRs and 52 briefs; a full backfill is
about 7,500 requests ≈ 15 h self-paced, or about two dispatches after the
ingest; incremental per merge 17–25.

## Conf keys

`.github/provenance.conf`, parsed by `tools/provenance/src/provenance/conf.py`
(its own strict parser; closed key set; `key: value`; `#` comments; unknown /
duplicate / colonless / malformed lines fail with `path:lineno`; integers only).

| Key | Value | Meaning |
|---|---|---|
| `enabled` | `true` | the in-git half of the schedule's two-key arming; dispatch needs only this |
| `cadence` | `29 * * * *` | raw cron, identical to provenance.yml's `- cron:` |
| `settle_hours` | 6 | closed → due (≈ 4× the measured 1.42 h settle) |
| `max_defer_hours` | 24 | deferred → frozen with `incomplete` |
| `deploy_wait_hours` | 2 | wait for a terminal Production deployment |
| `scheduled_max_requests` | 400 | scheduled request cap |
| `rate_floor` | 500 | rate-limit floor |
| `dispatch_max_minutes` | 330 | self-paced dispatch stop |
| `backfill_since` | 2026-07-31 | earliest `since` |
| `ambiguity_window_minutes` | 15 | code-basis ambiguity window |
| `edit_grace_seconds` | 60 | an edit at least this long after creation → `claimed` |
| `receipt_lookback_hours` | 48 | receipts re-list window (re-run attempts) |
| `intent_window_runs` | 20 | tip-continuity search depth |
| `watched_workflows` | the nine | runs that get receipts |
| `snapshot_id` | `pr843` | ingest subtree / receipt source |
| `snapshot_ref` | `ccr-d0be94c3-o4sati-rescue` | the ingest's default ref |
| `snapshot_path` | `audits/provenance-2026-10/rescue` | the ingest's default path |

The live arming key is the `PROVENANCE_ENABLED` repository variable (unset =
disarmed — the house two-key convention of `.github/reeve.conf` and
`.github/backlog-groomer.conf`). Reeve's `provenance-lag` threshold is Reeve's
own `provenance_lag_hours` in `.github/reeve.conf` (default 3).

## Workflow

`.github/workflows/provenance.yml`, "Provenance harvest (keyless)".

**Triggers.** `schedule: '29 * * * *'` (two-key armed) and `workflow_dispatch`
with inputs `mode` (choice: `harvest` | `ingest` | `refreeze` | `recover`),
`since`, `until`, `pr`, `receipts_only` (boolean), `max_requests`, `dry_run`
(boolean), `confirm_sha`, `snapshot_ref`, `snapshot_path`. Rescue and backfill
are both `harvest` with `since`. Re-extraction needs no mode: the derived ref
is recomputed whenever the extractor version changes.

**Inputs** reach the code only through `env:` and are passed as CLI
arguments, where `cli.validate_inputs` full-matches each: dates
`[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)?`, pr
`[0-9]{1,7}(,[0-9]{1,7}){0,49}`, sha `[0-9a-f]{40}`, cap `[0-9]{1,5}`, ref and
path `[A-Za-z0-9][A-Za-z0-9._/-]{0,199}` without `..`, snapshot id
`pr[0-9]{1,7}`. No `${{ inputs.… }}` appears inside a `run:` block.

**Permissions.** Workflow default `contents: read`. The `gate` job: `contents:
read`, `actions: read`. The `harvest` job adds `contents: write` (data-ref
pushes only) plus read on `actions`, `pull-requests`, `issues`, `statuses`,
`checks`, `deployments`.

**Jobs.**

- `gate` — no concurrency group. Checks out the default branch, runs
  `provenance gate`: on a schedule, `go=true` only when the conf's `enabled`
  and `vars.PROVENANCE_ENABLED == 'true'` agree **and** one runs-list GET finds
  no queued or in-progress `workflow_dispatch` run of provenance.yml
  (GitHub keeps one pending run per concurrency group and a newly queued run
  replaces it — without this job the :29 schedule would silently cancel an
  operator's pending ingest, backfill or refreeze); on a dispatch, `go` =
  the conf's `enabled`.
- `harvest` — `needs: gate`, `if: needs.gate.outputs.go == 'true' &&
  github.ref_name == github.event.repository.default_branch`, job-level
  `concurrency: {group: provenance-writer, cancel-in-progress: false}`,
  `timeout-minutes: 350`. Steps: checkout (`ref` = default branch,
  `fetch-depth: 0`, `persist-credentials: false`); **plan** (`python3 -m
  provenance <mode> … --out-dir .provenance`, env `GH_TOKEN`, `PYTHONPATH=
  tools/provenance/src:tools/model-registry/src`); **declare** (two
  `actions/upload-artifact` steps, `name: intent-<ref>-<sha>`, `retention-
  days: 90`, each `if:` its ref changed); **publish** (`python3 -m provenance
  publish`); **recover** (mode `recover` only, instead of plan/declare/
  publish); **summary** (`.provenance/summary.md` → `$GITHUB_STEP_SUMMARY`:
  mode, requests used / 304s, receipts full/stub, units frozen / pending /
  deferred, `unknown.step` and `unknown.marker` counts, ingest counts, any
  skip reason, the evidence and derived shas, and the packed sizes of both
  refs).

**Keyless.** No `secrets.` reference, no claude-code-action, no
`AI_ANDON_CORD` gate leg (`tools/provenance/tests/test_workflow.py` pins all
three). Runtime: the runner's system Python, stdlib only, no pip.

## Registration

| Where | What | Builder |
|---|---|---|
| `tools/reeve` | `ROUTINE_WORKFLOWS += provenance.yml` (routine-dead); detector `provenance-lag` (the oldest pending unit past `due_at + provenance_lag_hours`, from one `GET contents/state.json?ref=provenance`); detector `provenance-foreign-tip` (either ref's tip not among the declared intents — `git/ref/heads/<ref>` + the provenance.yml runs' artifacts); both "not evaluated" offline or before the ref exists; golden report pairs updated, each detector with a positive and a negative control; `provenance_lag_hours` key in its conf parser | H6 |
| `scripts/cadence-sync-check.sh` | `ROUTINES += provenance` (conf raw cron `29 * * * *` ↔ the workflow literal) | H6 |
| `scripts/ci-classify.sh` | new output `provenance_tests` (true for `tools/provenance/*`, `.github/provenance.conf`, `.github/workflows/provenance.yml`, `.github/data-branch-guard/*`, `site/lib/provenance-contract*`, `site/test/fixtures/provenance-bundle.json`, `scripts/provenance.sh`, the drift-pinned `scripts/reviewer-posted.sh` / `coach-lock-check.sh` / `reviewer-signoff.sh` / `.claude/reviewer-post/reviewer_mcp.py`, `tools/model-registry/*`, `audits/provenance-2026-10/fixtures/*`, `ci.yml`); `tools/provenance/*` and `.github/provenance.conf` join the soft-infra and required-context lists; the header's output count and the `--selftest` rows | H6 |
| `.github/workflows/ci.yml` | a `provenance-tests` job (`python3 -m pytest tools/provenance -q`) gated on that output and listed in `ci-ok`'s `needs` (`scripts/ci-ok-guard.sh`) | H6 |
| `scripts/check.sh` | `scripts/provenance.sh --selftest` | H6 |
| `CLAUDE.md`, `README.md` | the `tools/provenance/` bullets, `provenance.sh` in the scripts bullet, this document in the docs bullet (landed with the scaffold; `scripts/docs-check.sh`) | scaffold |
| `docs/actions-security.md` | a row: provenance.yml holds `contents: write` via `GITHUB_TOKEN`, is keyless and dispatchable; the default-branch `if:` is defense in depth; tip continuity is the control; the forged-derived-tip residual | H6 |
| `docs/andon-cord.md` | a coverage row: provenance.yml is keyless and keeps running while the cord is pulled | H6 |
| `tools/provenance/tests/test_read_lens.py` | fails if anything outside `site/`, `tools/provenance/`, Reeve's two detectors and the workflow reads either ref (#646) | H6 |

## Sizes

Measured from the #843 snapshot with the real receipt writer (67 days,
2026-08-01 → 10-13): 3,738 receipts = 3.9 MB gz (full 2.6 MB, stubs
1.3 MB), the ci.yml listing 146 KB, 1,689 status files 758 KB — about 4.8 MB
for the ingest. Annualised, receipts grow about 21 MB/year and raw PR/brief
digests about 3 MB/year, under the 30 MB/year line at which the owner is to
be asked about partitioning (the plan's P1e rule). Fourteen workflows check
out with `fetch-depth: 0` and so fetch both refs; the derived ref is one
squashed commit and adds only its current tree. P1e records the measured
packed size of both refs (`git count-objects -vH` after a fresh `git fetch
origin provenance provenance-site`) and the added fetch time of a full-depth
checkout here once the refs exist.

## Failure modes

| Failure | Detection | Effect | Recovery |
|---|---|---|---|
| A routine with the owner PAT pushes to `provenance` | tip continuity at the next run; Reeve `provenance-foreign-tip` | run red (exit 3), nothing written | inspect; `recover confirm_sha=<last declared>` |
| A forged `provenance-site` tip | tip continuity; Reeve | the next harvest overwrites it with `::error::`; one deploy may show false attribution (escaped fields only) | automatic on the next run |
| The `provenance` ref is deleted | tip continuity (intents exist, ref absent) | run red | `recover` to a declared sha (if still fetchable) or re-bootstrap + re-ingest |
| Harvester stalled > 90 days (intents expired) | Reeve `provenance-lag` long before | next run refuses | manual re-bootstrap (rename the ref, bootstrap, re-ingest) |
| A guard rule would break | `guard_diff` | exit 4, nothing pushed | a bug: fix the writer, never the guard |
| Non-fast-forward push from a racing harvester | push rejection + continuity | `::warning::`, exit 5 | cursors redo it next run |
| Rate-limit floor / request cap | `BudgetExhausted` | clean stop, cursors saved, exit 0 | next run / next dispatch |
| A scheduled run would evict a pending dispatch | the `gate` job | the schedule skips that hour | none needed |
| GraphQL unavailable | `GraphQLUnavailable` | `incomplete: graphql-unavailable`, thread counts absent | `refreeze` later |
| A watched run still in flight at 24 h | settle | frozen with `incomplete: settle-deferred` | `refreeze` |
| A fifth step-naming era | `unknown.step` in the summary; receipts kept full | serving gives `none` for it | add the era to `steps.py` (version bump) |
| A new marker family / lead line | `unknown.marker` counts | not rendered | extend markers/digest (version bump) + `refreeze` |
| A historical `registry.conf` the strict parser refuses | basis `none`, `codebasis-unavailable` | model not shown | none — never guessed |
| Overlapping routine windows | containment finds ≥ 2 runs | model null, `ambiguous`, dotted/unattributed | v2 receipt status |
| A registry/workflow change on main within 15 min of a PR run | ambiguity window | `ambiguous` | none — never guessed |
| Force-pushed PR branch | heads missing from `/commits` | `incomplete: force-pushed-heads`; rounds by `pushed_at` | none |
| Vercel builds a data-ref push | Vercel's own deployment state for the pushed sha | a preview deploy | the console's Ignored Build Step / git settings (owner) |
| The snapshot does not match its manifest | `verify_manifest` | ingest refused | re-fetch the snapshot ref |
| A re-run attempt older than 48 h | — | not re-captured | `harvest since=` |
| GitHub's scheduled delivery drops slots | Reeve `routine-dead` / `provenance-lag` | catch-up at the next delivered slot (idempotent) | none |

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
8. **Contended pushes are not rebuilt.** A rebuilt commit would carry no
   declared intent; inside the concurrency group a moved tip can only be
   foreign or a racing harvester, so the run warns and retries next hour.
9. **Intents are declared between plan and publish**, as two CLI steps
   (`harvest`/`ingest`/`refreeze` plan; `publish` pushes), with
   `actions/upload-artifact` in between; a declared-but-unpushed sha is
   harmless.
10. **The bundle's no-op test ignores its meta fields** (`content_sha256`),
    or every main push would churn the derived ref.
11. **Receipt paths carry the attempt** (`.a<attempt>`), so a re-run is a new
    add-only path rather than a modification.
12. **Ingest scope**: watched-workflow receipts, the ci.yml listing and
    statuses only; check runs, PR commits and pulls are not ingested (re-
    readable, or not part of the design). The snapshot stays on its branch.
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
    `PROVENANCE_ENABLED` variable unset (disarmed); dispatches need only the
    conf so the ingest can run before arming.
20. **Reeve owns its lag threshold** (`provenance_lag_hours` in reeve.conf)
    rather than reading provenance.conf.
21. **GraphQL in the sandbox** returns 403, so the fixtures carry thread
    counts from the sandbox's CCR review-thread route (`threads.source:
    "ccr-fixture"`); production uses the one GraphQL query.

## Acceptance map

The plan's acceptance criteria and where each lives (every placeholder test's
docstring states its criterion; skip markers are removed as builders land
them).

| Phase | Criterion | Test |
|---|---|---|
| P0 | guard negatives: D, M under receipts/raw, raw file → 0 B | `test_gitstore.py::test_guard_refuses_*` |
| P0 | foreign tip → `::error::`, nothing pushed, non-zero | `test_gitstore.py::test_tip_continuity_refuses_a_foreign_tip`, `test_cli.py::test_foreign_tip_exit_3` |
| P0 | `recover` refuses an undeclared sha | `test_gitstore.py::test_recover_refuses_undeclared_sha` |
| P0 | run 31364447108 stored complete; a disarmed run is a stub | `test_receipts.py`, `test_steps.py` |
| P0 | workflow keyless, no inputs in `run:`, job-level permissions | `test_workflow.py` |
| P0 | purity: network only in github.py, git only in gitstore.py | `test_purity.py` (live) |
| P0 | ingest: manifest, mapping, idempotence | `test_ingest.py` |
| P1a | membership P/R on the tuned and held-out sets | `test_membership.py` |
| P1a | CC-1, NVC-6, NVC-7, CC-6, verified = 12 | `test_acceptance.py`, `test_trust.py` |
| P1a | every reviewer-posted.sh selftest row agrees; FOOTER drift pin | `test_trust.py`, `test_digest.py` (live) |
| P1a | no fixture field outside the contract (no prose) | `test_contract.py`, `test_fixtures.py` (live) |
| P1b | NVC-1, 8, 9, 11, 12b, 13, 14; SBC-1, 6, 7; CC-5, 7; NVC-12 re-baselined | `test_acceptance.py`, `test_episodes.py`, `test_extract.py` |
| P1b | merge-method fixtures map blamed rows; extractor has no clock | `test_extract.py`, `test_purity.py` |
| P1c | NVC-2, 3, 5; merge-tree basis; 5-minute ambiguity; oracle on main; pre-#326 pin; overlapping windows; basis always set | `test_serving.py`, `test_codebasis.py` |
| P1d | fixture bundle byte-identical; both validators accept, both reject an extra field; one view per design; no-op rerun; foreign derived tip replaced | `test_bundle.py`, `test_views.py`, `test_gitstore.py` |
| P1e | gate go=false with a queued dispatch; no-op pushes nothing; 2 h pending / 7 h frozen / 24 h forced; cap 5 stops and resumes; refreeze adds r2; cadence-sync; Reeve goldens; read lens | `test_workflow.py`, `test_freeze.py`, `test_github.py`, `test_receipts.py`, `test_read_lens.py`, tools/reeve tests, `cadence-sync-check.sh --selftest` |
