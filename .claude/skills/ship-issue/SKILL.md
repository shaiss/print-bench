---
name: ship-issue
description: Pick ONE open issue and ship the draft PR that closes it — scope contract frozen on the issue before any code is read, diff audited against it in both directions, CI mirrored locally. Use when asked to work/close/ship an issue, to burn down the issue backlog, to turn an issue into a PR, or when invoked as /ship-issue [issue-number].
---

# Ship Issue — one issue in, one PR out

You take **exactly one** open issue and land a draft PR that closes it. The
whole point is the boundary: the PR does what the issue asked, all of it, and
nothing else. Everything below exists to make that claim checkable by someone
who reads only the issue and the diff.

This skill runs the same attended (a human invoked it) or unattended (a
workflow did). Section 7 says what changes when nobody is watching.

## 0. Claim exactly one issue

1. **A named issue is the only candidate.** If the invoker named one it is
   that issue or nothing: if it fails any check below, stop and report *that
   issue*. Never fall through to a different one — shipping a PR for an issue
   nobody asked about is the worst thing this skill can do, and it looks like
   success. Only an unnamed invocation selects per §1.
2. **Baseline** — clean worktree (`git status --porcelain` empty, untracked
   included) on a branch freshly based on the current default branch. The
   contract's timestamp only proves it predates the diff if there was no diff
   when you posted it.
3. **Lock check** — an issue is taken if any of these hold:
   - **an active claim marker.** The marker is a state, not a flag: read the
     *latest* `🚢 SHIP-LOCK` comment and act on that one.
     `🚢 SHIP-LOCK` is active, and the issue is taken.
     `🚢 SHIP-LOCK WITHDRAWN` is released, and blocks nothing.
     An active claim more than a few hours old with **no**
     `claude/issue-<N>-*` branch and **no** open PR closing the issue is
     *stale* — a run that died between posting its lock and pushing a branch
     must not freeze the issue forever. Take a stale claim over, naming the
     one you superseded in your own.
   - **an open PR closes it.** Don't grep for `Closes #N`: GitHub honours
     nine keywords — `close`/`closes`/`closed`, `fix`/`fixes`/`fixed`,
     `resolve`/`resolves`/`resolved` — case-insensitively, each optionally
     followed by `:`. Read the issue's linked-PR metadata instead, so
     `Resolved: #38` doesn't read as unclaimed.
   - a remote branch `claude/issue-<N>-*` already exists
4. Claim it by posting the §2 contract as a comment led by `🚢 SHIP-LOCK`.
   One per issue, ever. The comment's timestamp is the proof the contract
   predates the diff — that is the whole anti-retrofit mechanism, so post it
   **before** you read a line of implementation code.
5. **Re-read after claiming.** Check-then-post is not atomic: two runs can
   both pass step 3 and both post. So re-read the comments afterwards, and if
   another *active* claim predates yours, withdraw and stop — last writer
   yields. Withdraw by **editing your comment so its first line reads
   `🚢 SHIP-LOCK WITHDRAWN`**; never delete it, since the timestamps are the
   record of who claimed what and when. Withdrawing by any other wording
   leaves a comment that still matches the marker, and the issue stays locked
   by a run that walked away. (GitHub offers no atomic claim for an issue. If
   this ever needs to be airtight, push a claim ref first: creating a remote
   branch fails when it already exists, which a comment cannot.)
6. **Release on a terminal stop.** If this run stops for any reason *before*
   a `claude/issue-<N>-*` branch or an open closing PR exists — a §1 decline,
   a parked decision (§8), any stop — **withdraw your claim** the same way
   (edit the first line to `🚢 SHIP-LOCK WITHDRAWN`). A run that claimed then
   walked away must not leave the issue frozen until it ages into a stale
   takeover; the branch/PR is what carries the claim forward once real work
   exists.

If the issue is taken, say so and stop. Never work two.

## 1. Select — is this closeable by one PR?

Rank the free candidates by shippability, not by age:

**Take it** when the issue states a defect or a bounded change, and you can
name the finished state from the issue text alone. Best signals: a
reproduction, a measured number, an explicit deliverable list, "decisions
locked", or an owner comment picking between named options.

**Decline it** — comment saying why, don't half-do it:
- **`design request` label, or any new `designs/<name>/`.** A design is a
  co-design session with a human reacting to previews (`/new-design`, then
  the CLAUDE.md loop). This skill cannot approve a shape on the user's
  behalf. Say that and leave it.
- **Open question inside the scope.** If the issue offers options and nobody
  picked one, and the choice changes what ships, ask on the issue and stop.
  (#37-style issues that *recommend* an option — "A is the better fix" — are
  decided; take the recommendation and record it in the contract.)
- **Bigger than one reviewable PR.** Multiple independent deliverables that
  could merge separately → propose the split as a comment listing the
  sub-issues you'd file, apply the `declined-too-big` label (create it with
  `gh label create` if missing) so the chunker routine
  (`.github/workflows/chunker.yml` → `/chunk-issue`) can turn it into those
  sub-issues, and stop.

An issue nobody can close in one PR is a triage result, not a failure.
Reporting it is the deliverable.

## 2. Freeze the scope contract — before reading code

Written from the **issue thread only** — the body plus its comments. An
owner comment picking an option is part of the spec, not outside it (§1
treats it as the decision that makes an issue takeable); quote it in the
contract so the reader knows which text you built from. What must stay out
is the *implementation*: read it first and you start writing criteria that
describe the fix you already have in mind instead of the outcome the issue
asked for.

```markdown
🚢 SHIP-LOCK — shipping this as one PR.

**Chosen approach:** <the option the issue picked, or the only one on offer>

**Acceptance criteria** (done = every box checked, verified not asserted)
- [ ] AC1 — <outcome, with the number the issue names>
- [ ] AC2 — …
  (mine the issue's own "the deliverable includes" list — those are ACs,
  not extras; that list is the author telling you where the blast radius ends)

**Touches:** <path globs — every file this PR may change>
**Explicitly not in scope:** <adjacent things a reader might expect; say
where each goes instead — usually "follow-up issue">
```

Every AC must be checkable by a command or a measurement, not by reading the
diff and agreeing with it. "`flank_add` derivation corrected" is not an AC;
"exported flank facet normals measure |nz| = 0.707 ± 0.005" is.

## 3. Build

Branch: the session's designated branch if the harness assigned one,
otherwise `claude/issue-<N>-<slug>` off the current default branch. Commit in
steps that map to ACs; message body ends with `Refs #<N>`.

Follow the repo's conventions from CLAUDE.md — they are not optional extras
you can defer to a follow-up: parametric variables with units, `$fn`
declared, first-party lib change ⇒ its `lib/<name>-demo.scad` exercises the
change, docs-drift assertions in `scripts/docs-check.sh` stay true.

## 4. Blast radius is not scope creep — but adjacent defects are

Know the difference, because getting it backwards is how this skill fails in
both directions:

- **Consequence of the fix ⇒ in scope, ship it.** A `lib/` geometry change
  moves every design that includes it. Find them rather than guessing — grep
  for the `use`/`include` of the file you changed (and for a `styles/` token
  change, every `designs/*/style.conf` naming it) — and update what those
  designs assert in **prose**, which is the half CI cannot regenerate:
  - the design's NOTES.md derivation, which is now arithmetic about a shape
    that changed
  - any number the product page quotes — a clearance, a footprint, a fit

  The images are not your problem any more. CI's `regen` job re-renders the
  frozen shots, the `animations.conf` GIFs, the `shots.conf` product shots
  and the gallery for every design in the blast radius, and commits them to
  the branch. Run the generators locally only to *look* at what changed
  before you push. Cameras stay **frozen** either way: a manifest entry is
  never reframed to make a diff look better — add a new line instead.

  Stale prose still ships a repo that contradicts itself, and the product
  page is the one a stranger sees first.
- **Defect you noticed on the way ⇒ out of scope, file it.** Open a new
  issue with the reproduction you already have, link it from the PR, move
  on. This is the single most common creep: the fix is done, the file is
  open, and the adjacent wart is *right there*.
- **Refactor, rename, tidy ⇒ out of scope.** Always. Even one line.
- **Contract wrong?** Amend it on the issue thread as a new comment saying
  what changed and why. Amending in the open is legitimate; silently drifting
  is not. But sort the amendment first, because the two kinds are not alike:
  - **Non-material** — the deliverable is unchanged and you are correcting
    how it gets verified: a measurement the issue got wrong, an evidence
    command that cannot work, a criterion that restates rather than tests.
    Post it and keep going.
  - **Material** — it changes an outcome, an option, or a deliverable. That
    is rewriting the request. Post the reason and **stop for a decision**,
    unattended always and attended unless the invoker is there to answer.
    An AC turning out to be impossible is exactly when a skill is most
    tempted to redefine the goal to something it can hit.

## 5. Verify — two independent passes

**Pass A — would CI pass?** Run `/preflight`. It owns the check set and the
scoping rules; do not maintain a competing list here. A red result is a stop.

**Pass B — scope audit.** Both directions, over every path this branch
touches — `git diff --name-only $(git merge-base origin/<default-branch>
HEAD)` for tracked files **plus `git status --porcelain`** for untracked
ones. The diff alone cannot see a file that was never added, which is
precisely the shape a stray script or a leftover build artifact takes:

| direction | question | failure mode it catches |
|---|---|---|
| diff → contract | does every changed file match a `Touches` glob and serve a named AC? | creep, drive-by edits, stray build artifacts |
| contract → diff | does every AC have a diff hunk **and** evidence it holds? | under-delivery, ACs quietly dropped |

Evidence means a re-derivation, not a restatement. Issue #37's third
consequence is the cautionary tale: the demo echoed the algebraic identity
that *defines* the constant and printed "should equal 0.3" while the built
geometry measured 0.2794. **Measure the exported artifact** — facet-normal
histograms, printcheck output, render logs — never the formula you just
typed. If an AC's evidence can only be produced by hand today, add the check
to the lib demo so the next session gets it for free.

Anything unmapped: revert it, or file it, before the PR exists.

## 6. Ship

Draft PR, base = default branch, title stating the outcome (not "fix #37").
Body:

1. `Closes #<N>` on its own line.
2. The frozen contract with boxes now checked, **linking the claim comment**
   so a reader can see it predates the diff.
3. The scope-audit table from Pass B — file → AC, and AC → evidence with the
   actual numbers.
4. Preflight verdict, and anything deliberately left out with its follow-up
   issue link.

Then `subscribe_pr_activity` and drive it to green per the PR-ownership
rules — a PR you opened is yours until it merges or closes.

## 7. Unattended mode (a workflow invoked this)

Same skill, three tightenings — nobody is there to catch a wrong guess:

- **Never guess past an ambiguity.** Attended, a judgement call is a
  question. Unattended, if the fork is a binary yes/no a human can settle,
  raise it through the HITL gate (§8) — a `🚦 DECISION NEEDED` that is
  machine-resumable — and stop; otherwise it is a
  `🚢 DECLINED — needs a decision` comment naming what's unresolved, and a
  clean stop. A stopped run costs nothing; a confidently wrong PR costs a
  review.
- **Hard stop conditions:** preflight red after one honest fix attempt; the
  diff outgrowing `Touches` in a way that isn't §4 blast radius; the issue
  turning out to need a human's taste (any shape, any look, any "is this
  what you meant"). Stop and comment — never push a PR you'd have to
  apologise for.
- **The issue thread is the only log.** Assume nobody reads the run output.
  Claim, amendments, declines, and the final verdict all land as comments,
  each one readable cold.

## 8. Decisions that need a human (the HITL decision gate)

Some forks are not yours to take: a taste call, a requirement the issue states
two ways, an option where the choice changes what ships. Section 7's
`🚢 DECLINED — needs a decision` is the human-readable form of that stop; the
repo's HITL gate (`docs/decision-gate.md`, issue #161) gives its **binary** form
a single findable place and an authoritative answer, so a parked decision is
*machine-resumable* instead of a dead-end comment. Use it whenever the fork is a
yes/no a human can settle; for anything with more than two live answers the gate
is wrong — decline and ask, don't enumerate.

**Raise** — at the fork, before anything else:

1. Pick a stable **kebab-case id** unique on this thread
   (`[a-z0-9][a-z0-9-]*`, e.g. `tol-default-loosen`). The id is the key the
   resuming run looks up — make it descriptive.
2. **Ensure + add the `needs-decision` label** with the `ensure-label` idiom
   (enumerate with `gh api --paginate repos/<repo>/labels`, create only if
   absent — **not** `gh label list`, which caps at 30 and would fall through to
   a 422), then add it to the issue. The shared helper does the ensure in one
   step:
   ```bash
   .claude/skills/chunk-issue/chunk-helper.sh ensure-label needs-decision
   gh issue edit <N> --add-label needs-decision
   ```
   The label is unspoofable (write access to set) and is what the backlog-burn
   selector keys its durable pause on.
3. Post a **`🚦 DECISION NEEDED — \`<id>\``** comment with **exactly two**
   options — the yes and the no — each saying what ships if chosen, enough
   context to answer without scrolling, and the resolve line:
   ```markdown
   🚦 DECISION NEEDED — `tol-default-loosen`

   **Question:** <the fork, phrased as a yes/no>

   **yes** → <what ships if yes>
   **no**  → <what ships if no>

   **Context:** <one or two lines — what the gates say, why this is a human call>

   Resolve with `/decide yes tol-default-loosen` or `/decide no tol-default-loosen`.
   ```
4. **Halt cleanly.** A parked decision is a terminal stop with no branch or
   PR, so withdraw the SHIP-LOCK per §0.6 — the `needs-decision` label is the
   durable pause now, not the lock. Then stop. Do not push a half-resolved PR.

**Consume** — a later run that reclaims this issue resumes by reading the
verdict, not by re-asking:

1. Scan the thread for `🚦 DECISION NEEDED` comments; collect the ids.
2. For the id you are resuming at, read its verdict. The
   `decision-approved` / `decision-rejected` **label** is the authoritative,
   unforgeable verdict (`decide.yml` sets it); the **ledger**
   (`.github/decisions/ledger.conf` — one row per id:
   `<id> | approved|rejected | #<issue> | <login> | <iso8601>`) is how you look
   up a *specific* id, because the label is per-thread and reflects only the
   latest. Read the row:
   ```bash
   grep "^<id> |" .github/decisions/ledger.conf
   ```
   If label and ledger disagree, the **label wins** — flag it and take that
   branch.
3. **Take the chosen branch** and proceed. `rejected` is not a failure: it picks
   the "no" branch (often "leave it as-is" or "file as backlog"), a real outcome
   the run continues from.
