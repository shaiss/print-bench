# Pull requests

The lifecycle of a PR here — what CI will do to your branch, who reviews what, and where the process differs from an ordinary repo.

## Opening

Open PRs as **drafts**. Branch names are free for humans; the `claude/issue-<N>-*` shape is a claim signal the autonomy selector reads, so don't use it for unrelated work. Before pushing, run `/preflight` (or its command set — see [CI and the gates](ci-and-gates.md)); a red gate is a stop, not a nuance.

## What happens to your branch

Expect CI to be an active participant, not just a judge:

- **The regen job may push a commit onto your branch** regenerating every derived artifact your change touches (previews and product shots through assembly views and drafted product pages — the regen job's header in [`ci.yml`](../../.github/workflows/ci.yml), and its fork failure message, carry the authoritative generator list), which re-triggers CI as a verification pass — so a regenerating PR runs twice by design. Don't fight the bot commit and don't commit derived artifacts yourself.
- **Sticky comments** accumulate on the PR: the printcheck gate report, smart-CI's gate selection (with any proposed gates a maintainer can cross via `/ci-gate approve <id>`), and — whenever designs are gated — the advisory geometric diff.
- **Everything funnels into `ci-ok`**, the summary context branch protection is designed to require; today `ci.yml`'s own CAUTION still names five required job contexts, so treat every job `name:` string as load-bearing — renaming one can strand PRs, and rewiring a job id breaks `ci-ok`'s `needs:` list, which [`scripts/ci-ok-guard.sh`](../../scripts/ci-ok-guard.sh) catches in `check.sh`. Job selection per change class is the classifier's business ([CI and the gates](ci-and-gates.md)).

## Reviews

- **Design PRs** get the reviewer personas automatically ([docs/reviewer-personas.md](../reviewer-personas.md)): Jane (printability experience) and Drik (fitness-for-purpose) post tagged findings, and the design's PM triages every tagged finding — act-now, queue, or decline with a cited reason. The reviewers are feedback; the PM is the gate; CI holds the numbers. `/design-coach` can drive the rounds.
- **Autonomy PRs** (`claude/*` heads) get one advisory Oracle review from the vendor that didn't ship the change — see [The autonomy loop](autonomy.md).
- **Platform PRs** are reviewed by humans against the charter ([PM.md](../../PM.md)) and the conventions ([Conventions](conventions.md)). The likeliest review asks: where is the negative control, which check enforces this, and which authoritative doc did you update instead of duplicating.

A PR that needs a human call an agent can't make gets parked with `needs-decision`; a maintainer answers with `/decide yes|no <id>` ([docs/decision-gate.md](../decision-gate.md)), and the label flip is what unblocks the work.

## PRs from forks

Four things invert on a fork, all for the same reason — CI cannot push to your branch and repo variables/secrets don't follow the fork:

1. The **regen job fails instead of committing**, listing the files to regenerate — this is the one case where you run the generators locally and commit their output yourself (the failure message names the exact commands).
2. **`/ci-gate approve` can't commit to your branch** — the reply tells you to edit `.github/ci-gates/registry.conf` in the PR yourself.
3. **The sticky comments are not posted** (fork PR tokens are read-only) — the printcheck report, smart-CI selection and geo-diff results are still in each job's log and summary, just not on the thread.
4. **No scheduled routine can arm itself** on your fork; the arming variables are deliberately uninherited.

## Merging

Merge when `ci-ok` is green and review is done. If your change added a gating CI job, the guard already forced you to wire it into `ci-ok`'s `needs:` — but remember the honest limitation recorded in [`scripts/ci-ok-guard.sh`](../../scripts/ci-ok-guard.sh): no in-repo check can prove branch protection actually requires `ci-ok`; that is a repository setting a maintainer owns.
