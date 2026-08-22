# CI and the gates

How CI decides what to run for your PR, what each gate proves, and the one behavior that surprises newcomers most: CI pushes commits onto your branch.

## One classifier decides what runs

CI's gate selection lives in exactly one script: [`scripts/ci-classify.sh`](../../scripts/ci-classify.sh). The workflow's `changes` job pipes your PR's changed-file list into it; `/preflight` runs the same script with `--local` on your working tree. That is why the local "would CI pass?" answer cannot drift from what CI actually does — and why, when you want to know what your PR will run, you can just ask:

```bash
./scripts/ci-classify.sh --local
```

The script's header documents its outputs, and its case arms (pinned by its own `--selftest`) are the authoritative tier membership — the shapes below are the map, with examples, not the inventory:

- **Docs-only PRs** (`docs/` and nothing else) select exactly one job: `docs-standards` — a light presence/wiring gate over the architecture docs and the site's How-it-works page ([`scripts/docs-standards-check.sh`](../../scripts/docs-standards-check.sh)). No render toolchain spins up. A PR touching only `CLAUDE.md` or `README.md` selects *nothing* — those paths match no classifier case. Either way the always-on jobs (lint, regen, design-docs, site-build, smart-ci) still appear on the PR's checks tab; they just do no heavy work.
- **Design PRs** gate the designs they touch, plus the *blast radius*: derivative descendants (via `./scripts/lineage.sh blast-radius`) and, for a style edit, every design declaring that style. Archived designs are dropped unless the PR touched their own files.
- **Soft infra** — paths that can't move geometry but must stay honest (most of `scripts/`, `site/`, the non-geometry `tools/` trees the classifier lists, workflow files other than `ci.yml`…) — makes the required contexts *run* but gate an empty design list. That is deliberate: a check reported as "skipped" does not satisfy branch protection (the PR #50 lesson recorded at the top of [`ci.yml`](../../.github/workflows/ci.yml)), so required jobs run as fast formalities instead of skipping.
- **Geo infra** — anything that can move an exported STL or the gate's own scope (`lib/`, `gate.sh`, `lineage.sh`, `ci-classify.sh` itself, `tools/printcheck`, `tools/lineage`, `ci.yml`, `.github/actions/`…) — gates the **entire design catalog**. Expect a slow CI run; that is the point.

The consequence for you: **a new top-level directory must be taught to the classifier**, or PRs touching only it either strand or merge untested, depending on the branch-protection regime — the recipe (and both failure modes) is in [Extending the platform](extending.md#a-new-top-level-directory).

## What the gates prove

Each gate exists because a cheaper signal was proven insufficient. In rough pipeline order:

| Gate | Proves | Where |
|---|---|---|
| `check.sh` (stable + nightly jobs) | every `.scad` evaluates clean, shared-library demos still render, every guard still refuses, every declared fit still assembles, docs match the tree | [`scripts/check.sh`](../../scripts/check.sh) |
| `gate.sh --slice` | each printable part renders, scores through [printcheck](../../tools/printcheck/README.md), survives a real PrusaSlicer test-slice, and every derivative's claimed override actually changed the mesh | [`scripts/gate.sh`](../../scripts/gate.sh) |
| `readme-gate.sh` | every design ships a complete product page (the full requirement list is in the script header) | [`scripts/readme-gate.sh`](../../scripts/readme-gate.sh) |
| `style-check.sh` | style packs are internally consistent and styled designs obey their pack's rules | [`scripts/style-check.sh`](../../scripts/style-check.sh) |
| `site-build` | the site's unit tests pass and the same build Vercel runs resolves every local reference | [`scripts/site.sh`](../../scripts/site.sh) |
| `lint` (always on) | shellcheck, actionlint, and a Python-3.10 syntax parse of every first-party `.py` — the safety net for paths no classifier case selects | [`ci.yml`](../../.github/workflows/ci.yml) |
| `geo-diff` (advisory) | a geometric STL diff of merge-base vs head whenever designs are gated, posted as a sticky comment; job-level `continue-on-error`, so it can never block a merge | [`ci.yml`](../../.github/workflows/ci.yml) |

Everything funnels into **`ci-ok`**, the summary context branch protection is *designed* to require — whether it actually does is a live GitHub setting no in-repo check can verify, and [`scripts/ci-ok-guard.sh`](../../scripts/ci-ok-guard.sh)'s header says exactly that; `ci.yml`'s own CAUTION still names five required job contexts, which is why the "run but gate nothing" formality modes exist and why job `name:` strings must stay stable. `ci-ok`'s `needs:` list is hand-maintained, so a new gating job must be added to it in the same PR that creates the job — the guard (run by `check.sh`) fails on the omission. In `ci-ok`, a *skipped* job counts as passing by design: a skip is the classifier's verdict that the job had nothing to judge.

## CI commits to your branch

Anything **derived** from a design — preview PNGs, animation GIFs, product shots, the README gallery, drafted product pages — is CI's job to generate, not yours. The `regen` job re-runs the generators for every design your PR touches — blast radius included, and the whole non-archived catalog when `lib/` or a generator script moves — and **commits the result back onto your PR branch**. Don't commit generated artifacts by hand, and don't be surprised by the bot commit; the presence-only gates on those artifacts are safe precisely because the same run that gates the source regenerates the images beside it.

Three mechanics worth knowing (the full rationale is in [CLAUDE.md](../../CLAUDE.md) and [docs/architecture/ci-platform.md](../architecture/ci-platform.md)):

- The commit-back is pushed with the `REGEN_TOKEN` PAT, not `GITHUB_TOKEN` — a `GITHUB_TOKEN` push triggers no workflow, which would strand the PR head on a commit carrying no required checks. The PAT push re-triggers CI, so **a regenerating PR runs CI twice**; the second run is the verification pass, bounded by a loop guard that recognizes regen's own commit and refuses to push again.
- A design is skipped when its input fingerprint ([`scripts/regen-stamp.sh`](../../scripts/regen-stamp.sh)) matches the committed `.regen-stamp` — re-rendering a Cycles shot to find it byte-identical costs minutes.
- **On a fork PR the contract inverts** — see [Pull requests](pull-requests.md), the home of the fork differences.

## Smart CI: gates that don't exist yet

On top of the deterministic classifier sits [`tools/ci-gates`](../../tools/ci-gates/README.md): detectors propose checks that would apply to your PR (a shell script with no shellcheck gate, a directory the classifier doesn't cover), and the committed registry [`.github/ci-gates/registry.conf`](../../.github/ci-gates/registry.conf) records each gate's decision and tier. **Advisory** gates run automatically and only warn; **gating** gates stay proposals in a sticky PR comment until a maintainer crosses one with a PR comment — `/ci-gate approve <id>` (also `decline`, `list`). The registry, not any prose summary, is the source of truth for what is currently enforced — gates get crossed over time, so check the file, and treat the sticky comment on your PR as live state.

## Before you push

Run `/preflight` (or its command set by hand — [`.claude/skills/preflight/SKILL.md`](../../.claude/skills/preflight/SKILL.md)). It classifies your working tree exactly as CI will, runs the same checks in fastest-failure-first order, and tells you which local failures are expected because CI's regen job fixes them — and which are real. One validated push beats three speculative ones.
