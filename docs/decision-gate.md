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

```
agent parks a decision            maintainer resolves it            pipeline resumes
──────────────────────            ──────────────────────            ────────────────
+label  needs-decision     ──►    /decide yes|no <id>        ──►    next scheduled run
🚦 DECISION NEEDED comment         -label needs-decision              sees the label gone,
run stops                          +label decision-approved            reads the verdict,
                                     | decision-rejected               takes the branch
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

The `decide.yml` workflow authorizes the commenter by their **real repository
permission** (`getCollaboratorPermissionLevel`, one of `admin`/`maintain`/
`write`), parses the command against an anchored strict pattern, then:

- flips the label: `needs-decision` → `decision-approved` / `decision-rejected`
  (creating the verdict label on demand). **This label is the authoritative,
  unspoofable verdict.**
- appends a row to `.github/decisions/ledger.conf` on the **default branch** —
  the reproducible audit trail, keyed by id:
  `<id> | approved|rejected | #<issue> | <login> | <iso8601>`. If the ledger
  commit is refused (e.g. branch protection), the label still carries the
  verdict, so the gate degrades safely.

### 3. How the paused pipeline resumes

Nothing is held hostage: the backlog-burn selector reads the label as machine
state on **every** firing. `backlog_burn.select.exclusion_reason()` excludes any
issue carrying `needs-decision` — a *durable* block (unlike a SHIP-LOCK it never
goes stale, because a pending decision does not expire; the guard sits ahead of
the lock check for exactly this reason). Once `/decide` clears the label, the
issue is eligible again on the next scheduled run, and the resuming skill reads
the verdict (the `decision-*` label; the ledger disambiguates by id) and takes
the chosen branch. This is the same "re-read resolved state next run" pattern the
one-issue-per-firing cap already relies on.

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
- **Committed source of truth.** The verdict lives in a label (state) and a
  git-tracked ledger (audit) — reproducible, diffable, carried by a clone.
- **The label flip fails closed.** `/decide` adds the verdict label *before*
  removing `needs-decision`. The two calls are not atomic and the selector's
  durable pause keys only on `needs-decision`, so this order guarantees a
  partial failure leaves the issue **still paused** (never un-paused with no
  verdict), which a `/decide` re-run then heals.
- **GITHUB_TOKEN, not a PAT.** A decision-ledger commit must *not* re-trigger CI
  (the telemetry-commit reason: a re-triggering commit on the default branch
  would gate the whole catalog on every decision); the async selector re-reads
  the state on its own schedule regardless.

## Follow-ups (not in this slice)

Wiring the raise-a-decision step into the agent skills; an optional GitHub
Projects (v2) `Decision` field; an optional read-only queue section on the Vercel
site (via the deploy-time, best-effort, empty-on-failure fetch seam
`site/lib/releases.mjs`); custom notification routing.
