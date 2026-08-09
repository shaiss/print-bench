---
name: chunk-issue
description: Break ONE oversized issue (declined as bigger than a single reviewable PR) into dependency-ordered sub-issues that are each closeable by one PR, filed as native GitHub sub-issues and auto-armed for the backlog burn. Use when asked to chunk, split, or break up an issue, to turn a "too big" issue into shippable pieces, or when invoked as /chunk-issue [issue-number].
---

# Chunk Issue — one epic in, shippable sub-issues out

You take **exactly one** open issue that is too big for a single PR and turn it
into a set of **sub-issues that each are** closeable by one PR. The point is the
loop: `/ship-issue` declines oversized issues (its §1) and labels them
`declined-too-big`; you convert those back into small work the backlog burn can
actually attack. You file issues — you never push code or open a PR.

This skill runs the same attended (a human invoked it) or unattended (the
`chunker.yml` workflow did). Section 6 says what changes when nobody is watching.

## 0. Claim exactly one issue

1. **A named issue is the only candidate.** If the invoker named one, it is that
   issue or nothing — never fall through to a different one. An unnamed
   invocation may select the oldest open issue carrying `declined-too-big`.
2. **It must be oversized.** Proceed only if the issue carries the
   `declined-too-big` label, **or** its thread contains a `🚢 DECLINED` comment
   giving size ("bigger than one reviewable PR", "big bet", staged deliverables)
   as the reason. If neither holds, stop and say so — chunking an issue nobody
   judged too big is scope you were not asked for.
3. **Not already chunked.** If the thread already has a `🧩 CHUNKED` comment, or
   the issue already has open sub-issues, **first remove the `declined-too-big`
   label** (selection reads the label, not the `🧩 CHUNKED` comment — leaving it
   on burns a scheduled run every day on an already-chunked issue), then stop and
   report it. Re-chunking double-files. This early-exit and §4 are the two paths
   that must both clear the label; that is the idempotency latch the daily
   schedule relies on.

## 1. Read the whole thread first

Read the issue **body and every comment**. An earlier `/ship-issue` decline
often already proposes the split — a dependency-ordered sub-issue list is exactly
what its §1 emits (see the #98 decline for the canonical shape). **Reuse that
proposal when it exists**: it was written from the same source you are reading,
and honoring it keeps the human's and the machine's plan aligned. Only deviate
where the proposal is stale against the current tree.

## 2. Design the split

Produce an ordered set of sub-issues where:

- **Each is closeable by one reviewable PR.** That is the whole product — a
  sub-issue that is *still* too big has bought nothing. If a piece cannot be made
  PR-sized, that is a signal to decline the split (§5), not to file a mini-epic.
- **The order is the dependency order.** Name blockers explicitly ("depends on
  #<n>") so the backlog burn's oldest-first pick and a human reading the epic
  both see what is unblocked.
- **Each sub-issue is self-contained**: a title, a *what*, a *why*, an explicit
  acceptance/"done" statement (the thing `/ship-issue` freezes its contract
  from), and its dependencies. Write them so a cold `/ship-issue` run can build
  from the sub-issue text alone.
- **Together they close the parent.** The union of the sub-issues must deliver
  the whole parent — no silent under-delivery. Say so in the summary.

## 3. File the sub-issues

For each piece, in dependency order:

1. Create it as a normal GitHub issue with the body from §2.
2. Link it as a **native sub-issue** of the parent (GitHub's sub-issue
   relationship), so the parent becomes a tracked epic — not just a comment
   list. Carry over the parent's domain labels (e.g. `enhancement`) where they
   apply.
3. **Auto-arm the genuinely-small ones** with `autonomy-ok` so the backlog burn
   can pick them up with no second human step. This is the operator's chosen
   gate placement: the human curates what gets `declined-too-big` upstream; the
   small sub-issues arm automatically. **Do not auto-arm** a sub-issue that
   `/ship-issue` would itself decline — a design task (new `designs/<name>/`, or
   a `design request`), an open question needing a human decision, or a piece
   that is still bigger than one PR. Those get filed (and labeled
   `design-brief` when they are designs, so `/design-run` can see them) but
   **not** `autonomy-ok`. Filing a piece that will only re-decline wastes a burn.

Create labels that do not yet exist rather than failing (`gh label create` is
available in the run environment).

## 4. Close the loop on the parent

- **Remove the `declined-too-big` label** from the parent, so the chunker's own
  selector will not pick it again. This is the idempotency latch — do it even if
  you filed nothing, when §5 applies.
- Post one **`🧩 CHUNKED`** comment on the parent listing every sub-issue you
  filed (with numbers), which are armed vs. left for a human, and the assertion
  that together they close the parent. This comment is the durable record.
- **Leave the parent open** as the tracking epic (its sub-issues close it as they
  land). Do not close it yourself — that is a human's call once the children
  merge.

## 5. When to decline instead of splitting

Chunking is not always right. Post a comment saying why, remove
`declined-too-big` (so it is not retried blindly), and stop, when:

- **The work is genuinely indivisible** — one big change that cannot honestly be
  cut into independently-mergeable PRs. Say that plainly; a forced split that
  produces sub-issues nobody can ship separately is worse than none.
- **The split needs a human's taste** — the pieces depend on a product or design
  decision nobody has made (which features, which order matters to the roadmap).
  Propose the split as a comment for a human to file, the way `/ship-issue`
  declines a decision, and leave it.

A refusal to split, explained, is a valid outcome — the same discipline
`/ship-issue` uses when it declines.

## 6. Unattended runs

When a workflow invoked you, the **issue thread is the only durable log**: the
`🧩 CHUNKED` comment (or the §5 decline) is the record a human reads later. End
every comment you author with the attribution footer:

```
---
_Generated by [Claude Code](https://claude.ai/code)_
```

You file issues only — never push a branch, never open a PR. If you find
yourself wanting to write code, you have the wrong skill: file the sub-issue and
let the backlog burn's `/ship-issue` ship it.
