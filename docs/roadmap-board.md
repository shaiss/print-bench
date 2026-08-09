# Autonomy roadmap board (GitHub Projects v2)

The tracked design is [issue #148](https://github.com/shaiss/print-bench/issues/148).
This is the roadmap/tracking layer on top of the autonomy loop: a **GitHub
Project (v2)** where the chunker's sub-issues, design briefs, and HITL gates get
story points, status, milestones, and a roadmap view — the surface a human
triages what the automation produces.

It is the *surface* job of the same three-part split as the decision gate
([`decision-gate.md`](decision-gate.md)): labels/ledger/issues stay the
git-native source of truth; the board is a **lens** over them.

## Why the board is provisioned by a committed `gh` recipe

This session's automation **cannot create or populate a Projects v2 board** — the
board/field/item API is GraphQL-only and unavailable to the tooling here, and a
Project is settings-shaped anyway. So we keep the board's **schema in git** as the
source of truth and generate the exact, idempotent `gh` commands to create it:

```bash
scripts/gh-project.sh setup          # print the recipe (review it)
scripts/gh-project.sh setup | bash   # run it
```

The spec lives at the top of `scripts/gh-project.sh`; `--selftest` (run by
`check.sh`) proves the emitted recipe is valid, idempotent bash. Editing the spec
and re-running the recipe reconciles the live board — repeatable, reviewable, and
carried by a clone, exactly like the rest of the repo's config.

## The board spec (slice 1)

| Piece | Value | Notes |
|---|---|---|
| Title | `print-bench autonomy` | owner `shaiss` (a user, not an org) |
| `Stage` (single-select) | Backlog · Ready · In progress · In review · Done | our pipeline. See the built-in-Status note below |
| `Story points` (number) | Fibonacci 1/2/3/5/8 | a chunked one-PR sub-issue is 1–3; bigger = re-chunk |
| Milestone | GitHub's built-in Milestone field | fed by repo milestones (`gh api …/milestones`) — groups chunked epics + children |

**Two things the CLI can't do (documented one-time UI steps):**

- **The built-in `Status` field (Todo/In Progress/Done) can't be reshaped via
  `gh`** (there's no `field-edit`), so the recipe adds a distinct `Stage`
  single-select instead of fighting it. This keeps the recipe idempotent and
  re-runnable with no delete-and-recreate that could wipe field values. Group the
  board's **Board view** by `Stage` in the UI.
- **Views (Board / Roadmap) can't be created or configured from the CLI** — view
  layout/grouping is UI-only. Add the Board and Roadmap views once in the UI;
  everything else is scripted.

## Auth / token scope (important)

`gh project` requires the **`project`** token scope:

- **Provisioning (slice 1)** runs as *you*: `gh auth refresh -s project` grants it
  to your `gh` login (the recipe does this first).
- **The Actions `GITHUB_TOKEN` cannot touch Projects v2** at all.
- **`REGEN_TOKEN` (a `contents:write` fine-grained PAT) does NOT include Projects
  access.** The slice-2 automation that *populates* the board needs a
  project-scoped token — either a classic PAT with `project`, or a fine-grained
  PAT with **Account permissions → Projects: Read and write** — stored as a new
  secret (e.g. `PROJECT_TOKEN`), or the Projects permission added to
  `REGEN_TOKEN`. (Fine-grained tokens have had a documented gap for *user-owned*
  projects; a classic `project` PAT is the safe default — verify before wiring.)

## Slices

- **Slice 1 (this):** the committed spec + `scripts/gh-project.sh` recipe + this
  doc. You run the recipe once to create the board.
- **Slice 2+ (follow-ups on #148):** the automation that *populates* the board —
  add issues on `/chunk-issue` and `/intake`, set `Stage` + `Story points` via
  the Projects GraphQL API (needs the project-scoped token); estimation in the
  chunker; the HITL `needs-decision` gate surfaced as a board column; and the
  Roadmap view + milestones. These need the board to exist and the token scope
  above, so they follow provisioning.

## How it maps onto the existing loop

- `/chunk-issue` files dependency-ordered sub-issues → they become board items
  (slice 2), estimated in `Story points`, at `Stage: Backlog`.
- The backlog burn's `autonomy-ok` gate and the decision gate's `needs-decision`
  label are the machine state; the board *reflects* them (a `needs-decision` item
  is visible as awaiting a human), it does not replace them.
- Milestones group a chunked epic (parent) with its children for the roadmap.
