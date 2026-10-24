# Design provenance audit — 2026-10-13

The question: can a visitor see **who** made each design and **how** — the
timeline of every agent that touched it — and is that baked into CD so a
design never has to assemble it by hand?

Short answer: the record exists on GitHub, almost none of it reaches the
site, nothing in CD captures it, and since 2026-10-01 GitHub deletes the
Actions records that hold the "how" after 90 days.

This directory keeps what the audit produced that later work needs:

- `fixtures/` — hand-built golden who/how timelines for `nuggs-vent-cap`,
  `sbc-case` and `calibration-cube`, the event schema, PR→design membership
  labels, and `bin/check_acceptance.py` (21 checks). They are the acceptance
  target for the provenance harvester. Prose fields are stripped (replaced by
  `<stripped sha256:… len:…>`); only structured fields remain.
- The Actions/checks/statuses snapshot that retention would delete lives in
  the evidence-only draft PR #843 (`audits/provenance-2026-10/rescue/` on
  branch `ccr-d0be94c3-o4sati-rescue`), not here.

Method: 127 agents mapped eight areas (site code and a local build, the live
site via Vercel, committed data for all 43 designs, PR-thread markers, the
issue side, CI/CD capture points, lineage, identity); every high and medium
finding was re-checked by one or two independent skeptics; a completeness
critic drove six follow-up passes (durable per-SHA records, story scope,
prior decisions, content safety, golden fixtures, API cost). A nine-agent
panel then chose the architecture below and red-teamed it. Counts are as of
2026-10-13.

## What a visitor sees today

| Measure | Value |
|---|---|
| Design pages with no "Built by" and no History tab | 27 of 43 — both are gated on a hand-written `designs/<name>/team.conf` that nothing in CD creates; 11 of the 12 designs added since #381 have none |
| Live git-history rows credited to an agent | 0 of 225 — 194 "Shai Perednik", 31 unattributed |
| Live git rows that are regen noise (previews/`.regen-stamp` only) | 150 of 225 (67%) |
| Timeline events with a link | 0 of 316 |
| PM.md decision rows that render | 84 of 149 — 65 rows in 12 rosterless designs never do |

## Where the who and how actually lives

| Source | Identifies | On site | Notes |
|---|---|---|---|
| PR-thread markers (`JANE_SIGNOFF`, `DRIK_SIGNOFF`, `PM_TRIAGE`, `AUTO_REVIEW_STAMP`, gate report) | persona, via marker + author + anchored suffix (`scripts/reviewer-posted.sh`) | no | 81 design PRs, 1,328 comments; only 229 of 417 sign-off occurrences pass the trust rule (123 were posted with the owner's token) |
| PR branch commits | builder (design run, Cursor Agent, claude[bot], attended sessions) | no | `/pulls/N/commits` survives branch deletion |
| Brief issues (filing, 🚢 SHIP-LOCK, DECLINED, DEFERRED, SHIPPED) | routine, by run-window inference | no | 52 briefs, 0 with an origin marker; brief→design join deterministic for 22 of 43 designs |
| Actions job steps (`chain link N`) + `registry.conf` at that commit | the model that served | no | 135 of 135 review jobs resolve; **deleted after 90 days** |
| `reviewer-signoff` statuses + check runs per SHA | per-round verdicts | no | the sticky comments keep only the last round; **deleted after 90 days** |
| Commit trailers (Co-Authored-By, Claude-Session) | harness, claimed model | no | already downloaded by `site/lib/history.mjs`, discarded after line 1 |
| `people/` + `team.conf` | 17 profiles, one GitHub login | yes | no entry for the builder routine, Oracle, labeler, chunker, regen CI, Cursor Agent, CodeRabbit |

## Findings

**Coverage.** C1 History/"Built by"/git fetch gated on `team.conf`
(`site/build.mjs:328,382`, `templates.mjs:629,671`). C2 65 parseable decision
rows hidden. C3 ungating today fails the build on 4 designs (11 latent parse
problems). C4 the richest committed history (NOTES "Decisions/Session/Status
log", "Round N") is in shapes the timeline does not parse.

**Who.** W1 identity resolved only by GitHub login (`history.mjs:76`); squash
authorship collapses to the owner; `[bot]` logins can never map. W2 every
PM.md row credited to the roster PM (`timeline.mjs:27-30`, ~34 of 149 rows
record someone else's ruling). W3 reviewers and pipeline agents never appear
as events; "Reviewed by → Coach, Drik, Jane" is one static string. W4 many
actors have no registry entry. W5 persona handles collide with real GitHub
accounts (#559). W6 brief filers are unrecoverable without run windows.

**How.** H1 GLM-served work is labelled "Claude" (trailers, footers; #636 was
built by glm-4.6 on chain link 3). H2 the serving model exists only in run
metadata (last non-skipped link step + `registry.conf` at the checked-out
code; `continue-on-error` masks step conclusions). H3 that metadata now
expires at 90 days ([GitHub changelog 2026-08-27](https://github.blog/changelog/2026-08-27-actions-retention-will-cover-checks-workflow-runs-and-statuses/)).
H4 review rounds are overwritten in place (#636: 22 rounds, the sticky shows
one). H5 finding→triage links are prose only (0 of 243 rows linked).

**Noise.** N1 `regen-stamp.sh` hashes all of `lib/`, so zero-consumer lib PRs
land on 32–35 designs' timelines (373 of 625 per-design main commits are
regen churn). N2 the commit adapter drops sha, links, trailers and brief
refs. N3 the event shape is `{date, source, sourceTag, text, detail, handle}`
— no URL, kind, time or second actor; same-day events sort by source. N4 the
20-commit cap cuts origin commits.

**Sources.** S1 no PR-thread or issue source exists (the seam was built for
one, #146). S2 a file-kind membership rule scores P 0.94 / R 1.00 held-out vs
0.29 / 0.57 for the current path filter. S3 a live deploy-time fetch cannot
be deterministic: freeze once after a settle window (all activity settles
within 1.42 h of merge; 42% of PM triage lands after merge).

**Lineage.** L1 the include closure is computed (`site/lib/model.mjs`) and
discarded. L2 `derives.conf` covers 2 of 43 designs; supersession, drop-ins,
family charters, harvest sources are prose. L3 parent pages never list
derivatives. L4 Changelog adopted by 1 design; one repo-wide release
namespace, and the site reads only `/releases/latest`.

**Pipeline.** P1 nothing in CD captures provenance; main is closed to
workflows (409, #543). P2 the regen commit-back cannot carry it (owner option
C, re-renders, loop guard). P3 deploy-time fetches fail silently. P4 a lean
harvest is cheap: 1,097 requests for 151 merged design PRs, 6–9 per merge.

**Defects found along the way.** D1 `inlineExcerpt` emits `javascript:`
links (`[[x]](javascript:alert(1))`) and is super-linear on crafted input.
D2 the telemetry roll-up truncated `reeve-greenlights.ndjson` to 0 B on the
`telemetry` branch (`ci.yml:1413`, `reeve.yml:1022`). D3 the Oracle has never
posted a review (0 in 365 runs; #757). D4 the decision ledger has 0 rows
(#543). D5 reviewer jobs succeed while posting nothing (9 of 23 on #636).
D6 the bell shows 30 of 53 decisions; `people/work.conf` stale since 08-23.

## Recommended design

A keyless, deterministic harvester (`.github/workflows/provenance.yml`,
hourly + dispatch) freezes each merged PR, its brief and the runs that
touched it once activity has settled (6 h), and never edits a frozen record.
Raw evidence goes to an add-only `provenance` data branch; derived per-design
views and one `bundle.json` go to a squashed `provenance-site` branch (the
telemetry-branch pattern without its truncation bug). Nothing is written
under `designs/` or to main. The site reads the bundle through a
`SITE_FETCH_PROVENANCE` seam pinned by sha and renders a "How it was made"
section on every design page — structured fields only (marker family,
verdict, sha, timestamp, actor, trust tier, a permalink built from numeric
ids), never comment prose. The model is shown as "requested for chain link
N" from step windows and `registry.conf` at the code the run checked out;
ambiguity shows no model. A committed `people/actors.conf` maps signals to
actors with trust tiers (verified / window / claimed / login); `team.conf`
becomes optional. A tip-continuity check (the harvester only builds on tips a
previous main-branch harvest declared) defends the unprotected branches
against agents holding the owner PAT. "Built on" lineage comes from the
include closure, `derives.conf` and family charters.

Rejected: a provenance roll-up committed to main (recurring human merges,
history growth), a ruleset bypass, a stateless deploy-time reader
(non-deterministic, fails open), files under `designs/` (re-opens review),
appending to the telemetry branch, storing comment bodies, LLM summaries.

## Rollout

| Step | Scope | Points |
|---|---|---|
| Q1 | telemetry branch: no truncating seeds, restore the precedent log, keep data-branch pushes from deploying Vercel previews | 2 |
| Q2 | linear-time safe excerpt renderer | 2 |
| Q3 | build-generated Content-Security-Policy | 2 |
| Q4 | visible seam failure states, bell pagination, "Review specialists" wording | 2 |
| P0 | evidence writer, tip continuity, run receipts; ingest #843 | 3 |
| P1a–e | fixtures + contract, PR/brief extraction and rounds, serving-model join, derived views + bundle, schedule + registration | 13 |
| P2 | arm and backfill from 2026-07-31 | 1 |
| P3a–d | "How it was made" on every page, history route, "Built on", derived roster, retire the old git fetch | 8 |

Owner decisions before the core: un-defer B3 (PM.md) and accept its size;
approve the two data branches; #496 (PM.md rows read "charter decision
(PM.md) · added in PR #N", `team.conf` optional); show the 123 owner-token
sign-offs as "unverified"; allow squash-commit subjects (owner-merged PR
titles) as text; confirm the Vercel Ignored Build Step setting (docs-only
#825 deployed despite a SKIP classification).
