---
name: clear-prs
description: Drive the whole open-PR backlog to merged — diagnose every open PR in parallel, fix each to a mergeable green state, then merge them serially in a conflict-aware order, closing only what is genuinely superseded. Use when asked to clean up, burn down, or clear the open PRs, to get the backlog mergeable and merged, or when invoked as /clear-prs.
---

# Clear PRs — the backlog sweep that ends at zero

You take **every** open PR in the repository and end with each one merged,
closed-as-superseded with a comment saying why, or left open with a named
blocker only a human can clear. Nothing ends the sweep "still red, nobody
looked" — that is the state the sweep exists to eliminate.

This is a **human-authorized** sweep: merging is the one act the repo's own
autonomy routines never perform (`/ship-issue` and `/design-run` stop at a
draft PR precisely so a human decides the merge). Being invoked with an
explicit "merge them" **is** that decision, delegated in bulk — so record in
the final report exactly what was merged under it. Without that instruction,
stop at "everything green and un-drafted" and hand the human the merge list.

## 0. Inventory, then diagnose everything at once

List the open PRs once. Then diagnose **all of them in parallel, read-only**
— one pass per PR, no fixes yet, because the fix order depends on the whole
board (two PRs that touch the same file must be serialized; a superseded PR
must be found before someone spends an hour fixing it). Per PR collect:

- `mergeable_state` and draft status,
- every check run, classified passed / pending / failed — and for each
  failure the **root cause from its logs** (the gate name and error, not
  "CI is red"),
- unresolved review threads, each summarized with whether the diff already
  addresses it,
- ahead/behind counts vs the default branch, and whether a textual merge
  conflict exists (`git merge-tree` on the merge base — no checkout needed),
- the blast scope: which changed files lie **outside** the PR's own design
  or tool directory (those are the cross-PR conflict surface).

Verdict per PR: `ready-to-merge` / `needs-base-update-only` / `needs-ci-fix`
/ `needs-conflict-resolution` / `needs-review-response` / `questionable`.

## 1. Triage — the whole board before any fix

Three decisions, made from the diagnosis table, before touching a branch:

1. **Close, fix, or merge.** A PR whose change already landed on the default
   branch by another route, or whose subject was rebuilt and merged under a
   newer PR, is **closed with a comment naming its successor** — never
   force-fixed into a second copy of merged work, and never merged to "get
   the count down". When in doubt whether a PR is superseded, it isn't:
   fix it. A PR that is genuinely half-built (red for a reason its own issue
   thread says is unsolved) is left open and reported, not merged.
2. **Merge order.** Serialize by conflict surface, not by age:
   - PRs already green and conflict-free go first, cheapest first — every
     early merge shrinks the board and the retry surface.
   - PRs that regenerate shared artifacts (the gallery README, telemetry,
     site inputs) conflict with *each other*, not just with main: after each
     one merges, the next needs a base update and a CI re-run. Budget one
     CI round-trip each; don't fix them all in parallel to byte-identical
     green and then watch each merge invalidate the next.
   - Tooling/infra PRs that widen CI (new gates, workflow changes) go
     **last** unless trivially green — merging them mid-sweep re-scopes
     every later PR's required checks.
3. **Required contexts.** Read what branch protection actually requires
   (here: `ci-ok`, and `reviewer-signoff` on design PRs) and treat those as
   the definition of green. A design PR missing a current reviewer sign-off
   needs the review workflow re-run (push after base update re-triggers it),
   or the escape-hatch label a human already sanctioned — never a bypass you
   invented.

## 2. Fix — parallel fan-out, one worktree per PR

Fixers run in parallel **only across PRs with disjoint conflict surfaces**
(design PRs each in their own directory qualify; two PRs touching the same
script do not). Each fixer, in its own clone/worktree of the PR head:

1. **Merge the default branch into the head** — never rebase, never
   force-push someone else's branch; a merge commit keeps every checkout and
   review anchor valid. Resolve conflicts; regenerate generated files with
   the repo's own tooling (lockfiles, `gallery.sh`, stamps), never by hand.
   For a **derived-artifact conflict** (here: `previews/.regen-stamp` and
   regen-rendered PNGs, re-stamped catalog-wide whenever a `lib/` input
   moves on main) there are exactly three sound resolutions, and which one
   is deliberate: take the **branch side** when it keeps the design tree
   byte-identical to what reviewers signed off; **recompute with the tool**
   when both sides are stale for the merged inputs; **leave the stamp stale
   on purpose** when only CI's canonical runner can honestly re-render the
   artifact (a Cycles hero) — the regen job re-renders and re-stamps in one
   commit. Never hand-pick binary artifact bytes any other way.
2. **Hunt the semantic trap before trusting a clean merge.** A textually
   clean merge is not a semantically clean one: when the base moved a
   shared library this branch calls, a local workaround for the old
   behavior becomes a double-applied bug (this repo's `teardrop_hole()`
   +Z fix turned every branch-side `rotate([180,0,0])` workaround into an
   upside-down cut that stale-green CI had never seen). Diff the base's
   `lib/` changes against the design's call sites, not just the conflict
   list.
3. **Fix the diagnosed root cause** — the specific failing gate from §0,
   not a speculative cleanup. Keep each fix minimal; widening a PR mid-sweep
   is how a mergeable backlog becomes a review backlog. Verify a claimed
   geometry defect against the mesh before implementing the prescribed fix —
   a reviewer's localization can be wrong while the defect is real.
4. **Validate locally the way CI will** — run the repo's scoped check
   entry point (here `/preflight`, which mirrors `ci.yml`'s own classifier)
   before pushing. One validated push beats three speculative ones.
5. **Fetch before you push.** CI here commits regenerated artifacts back
   onto PR branches (the `regen` job); a fixer that pushes blind will be
   rejected non-fast-forward or, worse, race the bot. Pull, merge, push.

A fixer that discovers its PR is unsalvageable reports `questionable` with
evidence; it does not close, merge, or comment — that verdict returns to the
sweep lead, who decides with the whole board in view. And after the fan-out
returns, the lead **sweeps the worktrees for stranded work**: a fixer that
died mid-validation leaves a committed, unpushed fix behind — validate and
push it centrally rather than redoing it.

## 3. Merge — serial, greenest-first, re-verify each time

The merge loop is **serial by design**; the board changes under every merge:

1. Pick the greenest un-merged PR per the §1 order.
2. Re-read its live state (a diagnosis older than the last merge is stale):
   required contexts green on the **current** head, no conflict, not draft.
   Un-draft it if needed — the repo's routines open drafts, and a draft
   cannot merge.
3. If it fell behind (an earlier merge moved main): update the branch,
   let CI re-run, and move on to the next PR in the meantime — the loop
   interleaves waiting, it never blocks the whole queue on one CI round.
4. Merge with the repo's convention (here: squash; the subject line keeps
   the `(#N)` suffix pattern of the existing history).
5. After every merge, re-check the remaining board: freshly conflicted PRs
   go back to §2, freshly green ones into the queue.

While waiting on CI rounds, subscribe to the PRs' activity events rather
than polling; schedule a check-in (an hour out) so a quiet CI failure can't
end the sweep silently.

## 4. Report — the board at zero

End with one table: PR, what it was blocked on, what was done (fix commits
pushed, base merges, un-drafted), and its terminal state — merged (with
SHA), closed-superseded (with successor), or open (with the one named
blocker and who has to clear it). Anything left open gets its blocker
posted as a PR comment too, so the state survives the session.

## Repo-specific gotchas (print-bench)

- The `regen` job pushes artifact commits onto PR branches with
  `REGEN_TOKEN`; the second CI run is the verification pass. Always
  `git fetch` a PR branch immediately before acting on it. A regen
  commit-back also moves which sha carries the `reviewer-signoff` status —
  an "absent" status on the newest head may just mean the round finished on
  the sha before it, or is still running; read the auto-review run list
  before calling it red.
- `mergeable_state` tells you what protection actually requires: `blocked`
  = a required context (`ci-ok`) is failing or pending, `unstable` = only
  non-required statuses are red, `dirty` = conflicts. Drafts read `blocked`
  regardless — poll their check runs directly.
- `reviewer-signoff` goes stale by design-tree currency: a push that
  touches the design tree needs Jane/Drik to re-sign (auto-review runs on
  push, ~30 min a round). Distinguish its two reds before acting: a
  **verdict** (`Jane blocked (verdict=block)`) is content — fix what the
  review says, through PM triage; a **dead review chain** (every provider
  failing in ~300 ms at $0 — the #298 signature) is infra, and the
  escape-hatch labels are the sanctioned human call, never self-applied.
  A re-review after a base update can produce a *new* block on a design
  that was green last round — that is the gate working, not flaking.
- Design PRs regenerate the root README gallery and `telemetry/`; the
  per-design gallery rows auto-merge cleanly, so design PRs mostly don't
  conflict with each other — but re-verify with `merge-tree` after every
  merge rather than assuming.
- An archived design (`designs/<name>/ARCHIVED`) is only gated by a PR
  scoped to its own files — a sweep must not "revive" one by bundling its
  fix into a wider PR.
