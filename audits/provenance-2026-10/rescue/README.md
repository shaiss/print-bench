# Actions / checks / statuses snapshot — 2026-10-13

**Evidence only. Do not merge as-is.** This directory exists so the
records below survive GitHub's retention change until the provenance
harvester (the design-provenance plan's P0 phase) ingests them into its own
evidence branch.

## Why it exists

Since **2026-10-01**, GitHub applies the repository's Actions retention
setting to *workflow runs, check runs and commit statuses*, not only to
logs and artifacts. The default is 90 days, and **90 days is the maximum
for public repositories** ([changelog, 2026-08-27](https://github.blog/changelog/2026-08-27-actions-retention-will-cover-checks-workflow-runs-and-statuses/)).
Before the change these records were kept 400+ days.

Those records are the only durable source for two parts of a design's
"who and how" story:

- **The serving model.** Each agent job's step names (`Run via Z.AI (GLM,
  chain link 3)`, pre-#326 `Run via Z.AI (GLM)`) plus `registry.conf` at the
  commit the run checked out give the model that actually served. Commit
  trailers and comment footers say "Claude" even when a GLM link served.
- **Review-round history.** The `reviewer-signoff` commit status and the
  reviewer check runs record a verdict per pushed SHA; the
  `AUTO_REVIEW_STAMP` and gate-report comments are edited in place and
  keep only the last round.

The repo's first runs (2026-08-01) would start expiring around
2026-10-30. Comments, issues, reviews and git history are *not* affected
by the retention change and are deliberately **not** captured here — the
harvester can re-read them at any time, and keeping comment bodies out of
git avoids republishing prose.

## Contents

| File | What | Count |
|---|---|---|
| `workflows.json.gz` | `GET /actions/workflows` | 40 workflows |
| `runs.tar` | one `<workflow>.json.gz` per workflow: every run since 2026-08-01 (id, event, status, conclusion, head branch/sha, timestamps, attempt, actor, linked PRs) | 19,890 runs |
| `jobs.tar` | one `<run_id>.json.gz` per non-skipped run of an agent-bearing workflow: the complete `GET /actions/runs/{id}/jobs?filter=all` response (every job, every step with name, status, conclusion, start/end) | 4,485 runs, 106,096 steps; 2,665 runs carry provider/chain-link steps |
| `prcommits.tar` | one `<pr>.json.gz` per PR: `GET /pulls/{n}/commits` (sha, author/committer login, author/committer identity and date, message) | 433 PRs |
| `sha.tar` | one `<sha>.json.gz` per PR commit and PR head: `GET /commits/{sha}/statuses` (all, incl. superseded) and `GET /commits/{sha}/check-runs?filter=all` (name, app, status, conclusion, times, output title/summary) | 1,992 SHAs, 8,254 statuses (872 `reviewer-signoff`), 57,700 check runs |
| `pulls.json.gz` | `GET /pulls?state=all` (number, title, state, timestamps, opener, head/base, merge sha) | 433 PRs |
| `capture.py` | the GET-only script that produced this (resumable; stdlib only) | — |
| `MANIFEST.sha256` | SHA-256 of every file above | — |

Agent-bearing workflows (jobs captured): adoption-assessor, auto-review,
backlog-burn, chunker, design-run, growth-twitter, labeler, oracle,
product-scout, reeve-growth, reeve, spike-converter, wright, decide,
ci-gate-approve, lifestyle-shot, product-still, lifestyle-clip, auto-arm,
growth-twitter-reply, lark-oneshot-650-reply, model-smoke, and the dynamic
Copilot agents. CI's own jobs (`ci.yml`) are listed in `runs.tar` but their
step data was not fetched: CI runs carry no serving model.

Window: runs created 2026-08-01T16:59Z through 2026-10-13T06:13Z. Captured
2026-10-13 with 10,022 GET requests, 0 errors. Every inner file is
deterministic gzip (mtime 0) of canonical JSON (sorted keys); tars are
name-sorted with fixed owner and mtime.

## Reading it

```bash
cd audits/provenance-2026-10/rescue
sha256sum -c MANIFEST.sha256
tar -xf jobs.tar -C /tmp/jobs
python3 -c 'import gzip,json,sys; d=json.load(gzip.open(sys.argv[1])); \
  print([s["name"] for j in d["jobs"] for s in j["steps"]])' /tmp/jobs/34661448637.json.gz
```

`34661448637` is the design run that built `nuggs-vent-cap` (#636): its
steps show chain links 1–2 (glm-5.2, glm-5.1) ending early and link 3
(glm-4.6) running from 00:42:05Z to 02:08:18Z.

## Content note

Everything here is metadata GitHub already serves publicly for this repo.
It includes commit messages and committer identities (as in git history) and
third-party check-run titles/summaries. None of it is site content: the
provenance plan renders structured fields only and never republishes prose.
