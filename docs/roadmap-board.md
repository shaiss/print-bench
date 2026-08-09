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
- **Projects needs its own token — `PROJECT_TOKEN`.** `GITHUB_TOKEN` can't touch
  Projects v2; `REGEN_TOKEN` (contents:write) doesn't include it; and the repo's
  `GH_TOKEN` was checked and carries **no Projects permission** either. So the
  sync workflow (`roadmap-sync.yml`) reads a dedicated **`PROJECT_TOKEN`** secret
  — a **classic PAT with only the `project` scope** (the reliable path for a
  *user-owned* board; fine-grained PATs have a documented gap there). Create it at
  <https://github.com/settings/tokens/new>, then `gh secret set PROJECT_TOKEN
  --repo shaiss/print-bench`. Without the secret the workflow logs a `::notice::`
  and does nothing — it is the on/off switch.

## Adding an issue to the board

Once the board exists, place an issue/PR on it and set its fields — same
emit-a-recipe pattern as `setup`:

```bash
scripts/gh-project.sh add-item https://github.com/shaiss/print-bench/issues/<N> \
  --stage Backlog --points 3 | bash
```

It's **idempotent**: it reuses the existing board item for that URL instead of
duplicating, so re-running reconciles the fields. `--stage` must be one of the
board's `Stage` options; `--points` is a number; both are optional. This is the
building block the chunker/intake wiring calls in slice 2 part 2.

## Slices

- **Slice 1 (done, #164):** the committed spec + `scripts/gh-project.sh setup`
  recipe + this doc. Run the recipe once to create the board.
- **Slice 2 part 1 (done, #166):** `scripts/gh-project.sh add-item` — the
  idempotent add-issue-and-set-fields recipe above (via `gh project item-add` /
  `item-edit`).
- **Slice 2 part 2 (this):** `.github/workflows/roadmap-sync.yml` — on an
  `issues` event, adds any issue carrying an autonomy-loop label (`autonomy-ok` /
  `design-brief` / `declined-too-big` / `needs-decision`) to the board via
  `add-item --stage-if-new Backlog`. Gated on `PROJECT_TOKEN` (no token → logs a
  notice and does nothing). The initial `Stage: Backlog` is bound to **item
  creation**, not to which event won the race, so a re-add or an out-of-order
  opened/labeled run never clobbers a card a human moved.
- **Slice 2 part 3+ (follow-ups on #148):** story-point estimation on the board
  (map the chunker's one-PR sizing → points), the HITL `needs-decision` gate as a
  board column, and the Roadmap view + milestones.

## How it maps onto the existing loop

- `/chunk-issue` files dependency-ordered sub-issues → they become board items
  (slice 2), estimated in `Story points`, at `Stage: Backlog`.
- The backlog burn's `autonomy-ok` gate and the decision gate's `needs-decision`
  label are the machine state; the board *reflects* them (a `needs-decision` item
  is visible as awaiting a human), it does not replace them.
- Milestones group a chunked epic (parent) with its children for the roadmap.
