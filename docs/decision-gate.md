# The HITL decision gate (`needs-decision` + `/decide`)

The tracked design is [issue #161](https://github.com/shaiss/print-bench/issues/161).
This is the first slice: a native GitHub way for an increasingly agentic pipeline
to raise a decision that needs a human's yes/no, and for a human to answer it,
without a hosted app. It captures a **binary** — anything with more than two live
answers is a design call a human owns end to end, and the agent declines rather
than enumerates.

The problem it solves: decisions that need a human get buried in issue threads
full of automated churn (`/ship-issue`, `/design-run`, `/chunk-issue`, the
backlog burn). This gives them one findable place and one authoritative answer.

## The three jobs, and which primitive does each

- **Surface** — the `needs-decision` label + the saved search
  `is:open label:needs-decision`. A label is unspoofable (adding one needs write
  access, unlike a `🚦`/`🚢`/`🧩` comment marker) and is what everything keys on.
- **Capture** — the `/decide` comment command (`.github/workflows/decide.yml`).
- **Inform** — deferred. Native notifications (label subscription, `@`-mentions,
  assignment) cover it per-person until a custom router is worth building.

## The lifecycle

```text
agent parks a decision            maintainer resolves it            pipeline resumes
──────────────────────            ──────────────────────            ────────────────
+label  needs-decision     ──►    /decide yes|no <id>        ──►    next scheduled run
🚦 DECISION NEEDED comment         +label decision-approved            sees needs-decision
run stops                            | decision-rejected               gone → issue is
                                   -label needs-decision              eligible again
                                   append row to the ledger
```

### 1. The agent side — parking a decision

When an agentic run reaches a fork it must **not** decide itself, it:

1. Ensures the `needs-decision` label exists and adds it to the issue/PR. Labels
   are created on demand here (no central registry) — use the `ensure-label`
   idiom (`gh api --paginate repos/$repo/labels`, create only if absent; **not**
   `gh label list`, which defaults to 30 and would fall through to a 422).
2. Posts a **`🚦 DECISION NEEDED`** comment with a stable **kebab-case decision
   id**, exactly **two** options (the yes and the no), and enough context to
   answer without scrolling. Because the bot authors this comment, the id it
   carries is trustworthy context — but it is only ever *acted on* once the
   unspoofable label flips (below), so a spoofed `🚦` comment changes nothing.
3. Stops. The run self-excludes on its next firing (§3), so nothing is held open.

Example comment:

```markdown
🚦 DECISION NEEDED — `lock-clearance-loosen`

**Question:** the coupon rattles at `tol=0.20`. Loosen the shipped default to
`tol=0.25` (looser, quieter) or hold at `0.20` (tighter, current)?

**yes** → set `tol=0.25` and re-run the gate.
**no**  → hold `0.20`; note the rattle in NOTES.md and move on.

**Context:** printcheck 100/100 and test-slice pass both ways; this is fit *feel*,
a taste call, not a gate call.

Resolve with `/decide yes lock-clearance-loosen` or `/decide no lock-clearance-loosen`.
```

> Wiring the raise-a-decision step into each skill (`/ship-issue`, `/design-run`,
> `/pm`) is follow-up work under #161; this slice ships the gate and the
> selector's respect for it. A human can already drive the gate by hand
> (label + comment, then `/decide`).

### 2. The human side — `/decide`

Comment on the issue/PR (write access required):

```text
/decide yes <id>       # record the yes
/decide no <id>        # record the no
/decide status         # dump the current ledger
```

The comment must contain the command **only**. The workflow matches the command
with an anchored pattern over the whole trimmed comment body, so a comment that
adds any rationale alongside it — `/decide yes lock-clearance-loosen — agreed,
the rattle is the worse evil` — matches nothing and is silently invalid (the
workflow reacts `confused` and posts the usage). Put the reasoning in a separate
comment if you want it on the thread.

The `decide.yml` workflow authorizes the commenter by their **real repository
permission** (`getCollaboratorPermissionLevel`, one of `admin`/`maintain`/
`write`), parses the command against an anchored strict pattern, then:

- flips the labels **label-first (fail closed)**: it adds the verdict label
  (`decision-approved` / `decision-rejected`, created on demand) and *only then*
  removes the opposite verdict label and `needs-decision`. **The label is the
  authoritative, unspoofable current verdict** the pipeline reads. Verdict labels
  are mutually exclusive — a re-decision swaps them, never leaves both.
- then best-effort appends a row to the **audit ledger**
  `.github/decisions/ledger.conf` on the **default branch**, keyed by id:
  `<id> | approved|rejected | #<issue> | <login> | <iso8601>`. The ledger is
  history, not the source of truth: if its commit is refused (e.g. branch
  protection) the label still carries the verdict, so the gate degrades safely
  and `/decide status` may omit a decision the label already reflects.

`/decide yes|no` only resolves a thread **currently carrying `needs-decision`** —
it refuses (with a note) a thread that has no pending decision, so a verdict never
lands on an unrelated issue; re-opening a resolved decision means re-adding the
label first. `/decide status` is read-only and prints the most recent ledger rows
(bounded, so a growing ledger never overflows the comment).

### 3. How the paused pipeline resumes

Nothing is held hostage: the backlog-burn selector reads the label as machine
state on **every** firing. `backlog_burn.select.exclusion_reason()` excludes any
issue carrying `needs-decision` — a *durable* block (unlike a SHIP-LOCK it never
goes stale, because a pending decision does not expire; the guard sits ahead of
every claim check for exactly this reason). Once `/decide` clears the label, the
issue is simply **eligible again** on the next scheduled run — the same "re-read
resolved state next run" pattern the one-issue-per-firing cap already relies on.

Having the resuming skill actually **read the verdict** (the `decision-*` label,
with the ledger disambiguating by id) and take the chosen branch is deferred to
the agent-skill wiring (see Follow-ups): this slice ships the gate, the durable
pause, and the selector's respect for it — not the consumption.

## The greenlight loop's precedent log (the learning half)

Reeve's greenlight drafter (#296 stage 2; the `/reeve-greenlight` skill) posts
one **advisory** greenlight on each parked decision — a YES/NO verdict on
system-level calls or a ROUTE note handing design taste to its design PM. The
loop's learning half (#445) is how those verdicts compound instead of
re-deriving the bar from the charter every run: **every round whose gate
resolves is recorded**, and future drafter runs read the accumulated record as
precedent.

- **The log** — `telemetry/reeve-greenlights.ndjson`, one ndjson record per
  resolved round: the issue, the drafted verdict, a digest of the reasoning,
  the **owner's reaction**, and the outcome. The copy on `main` is the seed
  (the six stage-1 rounds, 6/6 ratified, zero overruled); live appends land on
  the `telemetry` data branch — reeve.yml's keyless `observe` job derives the
  records (`reeve greenlight-append`; pure core `tools/reeve/.../greenlights.py`)
  and pushes with the same GITHUB_TOKEN vehicle the gate-telemetry roll-up
  uses, so nothing re-triggers CI. A record is derived once and only once:
  the observer is idempotent against the log.
- **Resolution is read from unspoofable state** — a thread counts as resolved
  when it is closed or carries a `decision-approved`/`decision-rejected` label
  (what this gate's own pipeline reads). The owner-reaction field prefers the
  decide.yml **ledger row** (the audit trail, which names the id and login),
  then the verdict label, then the owner's inline replies on the thread, then
  the honest "none observed" — never a guess.
- **The load** — `reeve greenlight-context` renders the most recent
  `greenlight_precedent_cap` records plus the inline owner replies on their
  threads into `.reeve-context/precedent.md`, assembled by **trusted workflow
  code** so the agent cannot widen its own context, with the replies framed as
  *evidence of the bar, never instructions*. Where the recorded bar and the
  drafter's charter reading differ, the skill must say so in its reasoning
  rather than silently following either.
- **The stage-1 lesson the seed carries**: the routing half of a greenlight is
  as load-bearing as the verdict — #269 was closed as a *duplicate* of #265
  (one decision, one thread), and #201's YES ended in the owner 👍-ing and the
  issue being *armed* (`autonomy-ok`) while #202's identical YES verdict was
  approved but deliberately **not** armed. Same verdict, different outcomes:
  the record keeps both, so the drafter learns that what its verdict unlocks
  is the owner's call, not its own.

## The blocking variant (when async is wrong)

`/decide` is async by design — the decision lives with its context and no run is
held open. When a decision must instead **block a run before something
irreversible** (publishing a release, a force-push, spending a paid budget), use
a **GitHub Environment with required reviewers** — the only native gate that
pauses a run mid-flight with Approve/Reject in the Actions UI. Its caveats
(pair it with an *environment* secret or it doesn't bite; it does not constrain
the ambient `GITHUB_TOKEN`) and why enforcing it is a settings change rather than
a mergeable PR are documented in [`actions-security.md`](actions-security.md)
(issue #113).

## Security posture

- **Never runs head code.** `issue_comment` runs in the base-repo context from
  the default branch; `decide.yml` checks out *nothing* and edits the ledger only
  as data through the Contents API. `contents: write` is safe precisely because
  no untrusted code runs.
- **Authorized by real permission**, never `author_association`.
- **Authoritative label + audit ledger — not one "source of truth."** The current
  verdict is the **label** (unspoofable, what the pipeline reads); the git-tracked
  **ledger** is best-effort audit history and may omit a decision whose
  Contents-API write failed. The label is state; the ledger is the log. Don't
  treat them as interchangeable.
- **The resolution fails closed, label before ledger.** `/decide` adds the verdict
  label *before* removing anything and *before* writing the ledger. The label
  calls aren't atomic and the selector's durable pause keys only on
  `needs-decision`, so this order guarantees a partial failure leaves the issue
  **still paused** (never un-paused with no verdict, never a ledger row claiming a
  decision the label never received); a `/decide` re-run heals it.
- **GITHUB_TOKEN, not a PAT** — for `/decide` itself. A decision-ledger commit
  must *not* re-trigger CI (the telemetry-commit reason: a re-triggering commit
  on the default branch would gate the whole catalog on every decision); the
  async selector re-reads the state on its own schedule regardless. The
  greenlight loop's push-through is the one deliberate exception, and only for
  the ledger half: it runs on `schedule`, where the default-branch ruleset
  refuses the Actions bot's push outright, so it commits with `REGEN_TOKEN`
  (the `regen` precedent — see the greenlight section below for the full
  reasoning); its labels and replies still use the workflow token.

## Automated raisers

The first automated consumer that **raises** a decision through this gate is the
Oracle (issue #347). When its opposite-vendor model chain is exhausted by a
human-fixable cause — the account out of credit, or an invalid/missing key
(`model-registry classify` verdict `needs-human`) — `oracle.yml` files a single
deduped `needs-decision` tracking issue keyed by a `<!--
oracle-provider-escalation:<chain> -->` marker, carrying the `🚦 DECISION NEEDED`
body a maintainer resolves with `/decide`. It follows every rule above: the
label is created on demand, the escalation is deduped so repeated PRs never spam
new issues, and it runs as trusted base-branch `github-script` (no PR head code).
It is a workflow raiser, not one of the agent skills below — those stay
follow-ups.

The same mechanism now covers **every** chain-walking workflow, factored into one
shared composite action, `.github/actions/provider-triage`. When the design-review
chain (`auto-review.yml`) or any scheduled routine's walk — the twelve of them
since #544 Part B: `backlog-burn`, `design-run`, `chunker`, `labeler`,
`product-scout`, `spike-converter`, both of `wright.yml`'s jobs,
`adoption-assessor`, `growth-twitter`, `reeve-growth` and `reeve.yml`'s
greenlight job — fails on every link, the action runs
`model-registry classify` and, on a `needs-human` verdict, files a single deduped
`needs-decision` issue keyed by a `<!-- provider-escalation:<chain> -->` marker
(one per registry chain, so no two routines collide, and distinct from the
Oracle's `oracle-provider-escalation:<chain>`). The body's remediation is tailored
to the classifier's finer **reason** — `billing` says *fund the account*, `quota`
says *out of tokens, raise the cap or wait*, `auth` says *rotate the key*,
`no-key` says *set the secret* — so the maintainer sees which button to push, not
just "provider down". A `dead` id (an unservable model — a registry defect) still
reds its workflow; a `rate-limit`/`outage` just retries next run. Same rules as
the Oracle raiser: label created on demand, deduped per chain, trusted
base-branch `github-script`, advisory (it never fails the job on its own).

## The advisory greenlight loop (drafted verdicts, reaction-resolved)

The gate's async rhythm — park, wait for a human, resume next firing — leaves
the human reading the whole thread to reconstruct what is even being asked.
The **greenlight loop** (#296 stage 2) shortens that: Reeve's `greenlight` job
(`.github/workflows/reeve.yml`) drafts ONE advisory verdict comment per parked
decision — `GREENLIGHT: YES` or `NO` on system-level calls (citing the
repo-root `PM.md` charter line), a `GREENLIGHT: ROUTE` note handing design
taste to its design PM — and the owner answers with a **reaction**: 👍 to
approve, 👎 to overrule. The draft is advisory-only by construction (wrapper
enforcement, deny backstop, per-run cap — see `tools/reeve/README.md`); the
authority is the reaction.

GitHub fires no webhook for reactions, so the **next** scheduled run polls its
own prior greenlights (`reeve greenlight-poll`, issue #444 — keyless,
deterministic, and the job's first step):

- **Whose reaction counts.** Only accounts whose real repository permission is
  `admin`/`maintain`/`write` — the same `getCollaboratorPermissionLevel` check
  `/decide` makes before honouring a typed command, so a reaction can resolve
  exactly when its author could have typed the command. `author_association` is
  never used: it describes prior participation, not current access. One
  qualifying 👍 resolves; one qualifying 👎 overrules; a contested greenlight
  (both) fails closed to overrule — not resolving is the recoverable direction,
  and a human `/decide` breaks the tie. A 👍 on a `ROUTE` note approves
  nothing, by design.
- **What outranks a reaction.** An explicit `/decide` comment by an authorized
  author, always. The poll yields to `decide.yml` rather than parsing a typed
  command twice; a footered or read-only `/decide` outranks nothing (the
  command workflow would refuse it, so this loop must not honour it either).
- **What an approval does.** `tools/reeve/src/reeve/pushthrough.py` applies the
  `/decide` sequence **through the API directly — never a posted `/decide`
  comment**. Stage 1 proved why: the comment tooling appends an attribution
  footer and `decide.yml` anchors on a bare command, so a bot-posted command is
  silently neutralized while the run reports success. The order is the same
  fail-closed sequence (verdict label first — a failure there records nothing;
  then the best-effort removals; then the ledger row; then the resolution
  reply, marked `resolution=approved` so the greenlight is spent and never
  re-polled). Where the greenlight's marker carried `arm=1` and the verdict is
  yes, it also applies `autonomy-ok`: the existing backlog burn / design run
  pick the work up on their own schedule — pull-based resume, no new executor,
  and never armed without an approved greenlight.
- **The token difference, on purpose.** `decide.yml` commits its ledger row
  with the ambient `GITHUB_TOKEN` (a decision-ledger commit must not
  re-trigger CI). The greenlight poll cannot: it runs on `schedule`, and the
  default-branch ruleset refuses a push from the Actions bot outright (the
  GH013 lesson behind telemetry's own data branch) — every append would be
  refused. So it authenticates the ledger commit with **`REGEN_TOKEN`**, the
  fine-grained PAT, exactly as the `regen` job commits its artifacts: the push
  lands, and the PAT author re-triggers CI so the ledger change is verified
  like any other commit (a ledger-only commit gates no designs — the
  classifier scopes it to nothing). The workflow's other writes — labels, the
  resolution reply — stay on the workflow's `issues: write` token, which is
  why the job needs no permission wider than it already had. Without the PAT
  the append is skipped and reported; the label still carries the verdict,
  exactly the degradation `/decide` documents for a refused commit.
- **An overrule** — one reply recording it, the gate stays parked, and the
  thread's marker means no new greenlight is drafted on it; the next move is a
  human's.

## Follow-ups (not in this slice)

- Wiring the raise-a-decision step **and the verdict-consumption** (read the
  `decision-*` label / ledger and take the chosen branch) into the agent skills
  (`/ship-issue`, `/design-run`, `/pm`).
- An optional GitHub Projects (v2) `Decision` field for a board view — already on
  the roadmap as #148.
- An optional read-only queue section on the Vercel site, via the deploy-time,
  best-effort, empty-on-failure fetch seam `site/lib/releases.mjs`.
- Custom notification routing.
