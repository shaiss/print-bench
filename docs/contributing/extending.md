# Extending the platform

Recipes for each kind of platform change, each step tied to the check that enforces it where one exists. Where a check exists the linked file is the enforcement — and when a recipe and a check disagree, the check wins and this page has drifted. The remaining steps (a script's `--selftest` and its `check.sh` wiring, the Bash 3.2 floor, a tool's README and negative-control suite, the site house rules) are conventions review holds you to — no check will catch skipping them, which is exactly why they're listed.

## A new script in `scripts/`

1. Ship it with a shebang and the **committed** executable bit (`git update-index --chmod=+x`); a sourced helper gets neither.
2. Route any OpenSCAD invocation through `"$OPENSCAD_BIN"`, never a literal binary.
3. Name it in CLAUDE.md's "`scripts/`" layout bullet **and** in README.md — [`scripts/docs-check.sh`](../../scripts/docs-check.sh) fails otherwise.
4. Give it a `--selftest` proving it can fail, and wire that selftest into [`scripts/check.sh`](../../scripts/check.sh) by name — selftests are invoked explicitly, not discovered.
5. Keep it Bash 3.2-clean and shellcheck-clean (the always-on `lint` job runs shellcheck over `scripts/*.sh`).

## A new shared library in `lib/`

1. `lib/<name>.scad`, named in CLAUDE.md and in README.md's `## Layout` section (backticked).
2. `lib/<name>-demo.scad` exercising every module — `check.sh` CGAL-renders it automatically from the day it lands; this is the library's regression test.
3. If any module carries guards: `lib/<name>-guards.conf`, one line per parameter set the library must **refuse** ([`scripts/guard-check.sh`](../../scripts/guard-check.sh) documents the format and why it matches messages, not exit codes).
4. If the library carries a tuned fit: `lib/<name>-mates.conf`, one line per pair that must **assemble** plus at least one deliberately-interfering negative control ([`scripts/mate-check.sh`](../../scripts/mate-check.sh) documents the format and the zero-facets measurement).
5. Never `include` a copyleft-vendored library from shared `lib/` — [`scripts/license-boundary-check.sh`](../../scripts/license-boundary-check.sh) fails it.

Changing `lib/` is geo-infra: CI re-gates the entire design catalog. Budget for the slow run.

## A new tool under `tools/`

Follow the shape of [`tools/lineage`](../../tools/lineage/README.md) or [`tools/ci-gates`](../../tools/ci-gates/README.md):

1. **Stdlib-only at runtime** if CI runs it before installing anything (the classifier, smart-CI, telemetry capture and the scheduled routines all run on system Python); the `[test]` extra pulls pytest and nothing else. The tools CI must run from a bare checkout also carry a `tests/conftest.py` path shim so `python -m pytest tools/<name>/tests` works uninstalled; the `<tool>-tests` CI jobs pip-install each tool first either way.
2. A README of its own, and a pytest suite with a negative control per guard.
3. Wiring, all in one PR: a `tools/<name>/` mention in CLAUDE.md and README.md (docs-check's census covers `tools/` one level deep); a new classifier output plus case arms in [`scripts/ci-classify.sh`](../../scripts/ci-classify.sh) (a tools-only PR must still *run* the required contexts — soft infra); a `<name>-tests` job in [`ci.yml`](../../.github/workflows/ci.yml); and that job added to `ci-ok`'s `needs:` list ([`scripts/ci-ok-guard.sh`](../../scripts/ci-ok-guard.sh) fails `check.sh` if you forget).

## A new smart-CI gate

Three parts, kept separate on purpose ([`tools/ci-gates/README.md`](../../tools/ci-gates/README.md)):

1. A stanza in [`.github/ci-gates/registry.conf`](../../.github/ci-gates/registry.conf) declaring `tier`, `title`, `run`, optionally `setup` — and, required for a gating gate, `cross` (the approval command shown in the proposal comment; the parser refuses a gating stanza without one). A **gating** gate auto-lands as `proposed` and cannot fail a PR until a maintainer crosses it with `/ci-gate approve <id>` — a new blocking check never lands unannounced. An **advisory** gate defaults to on and only warns.
2. Optionally, a detector in `tools/ci-gates/src/ci_gates/detectors.py` — a pure function of the changed-file list and tree that narrows when the gate applies. A gate with no detector applies to every PR.
3. Tests in the tool's suite (the selection is pure and testable; a malformed stanza must fail).

## A new scheduled agentic routine

The heaviest recipe, because an unattended agent with a secret is the platform's most dangerous surface. Copy an existing sibling wholesale — [`.github/labeler.conf`](../../.github/labeler.conf) is the canonical annotated conf, and the workflows share one skeleton — then check off:

1. **Two-key arming**: a committed `.github/<routine>.conf` (`enabled`, `provider`, `cadence` in the house format) *and* a repo Actions variable (`<ROUTINE>_ENABLED`) that ships unset, so no clone or fork inherits an armed agent.
2. **Cadence in two places** (Actions cannot read a file for `on.schedule`): the conf key and the workflow `cron:` literal — and add the routine to the `ROUTINES` array in [`scripts/cadence-sync-check.sh`](../../scripts/cadence-sync-check.sh), or the parity between them is simply never checked.
3. **Model from the registry, never pinned**: a `[chain:<routine>]` in [`.github/models/registry.conf`](../../.github/models/registry.conf), resolved by the workflow at run time, one ship step per link, every outcome expression covering every link. Extend `tools/model-registry`'s drift-guard tests to pin your workflow, and dispatch `model-smoke.yml` after editing a chain — static checks cannot prove a model id is servable by a key.
4. **A write surface split by direction**: reads on a narrow shell wrapper with trivial arguments; any rich multi-line write as an MCP tool (under `--permission-mode dontAsk`, the Bash matcher denies arguments that read as shell structure — a markdown table pipe is enough, and no quoting fixes it). The wrapper enforces authorization itself, not just the prompt.
5. **A deny backstop plus its guard**: a `.claude/<routine>-settings.json` denying every dev Bash allow and every sibling routine's write surface (allow rules merge additively across settings sources, so `--allowedTools` alone is never exclusive), never denying the routine's own surface — and a `scripts/<routine>-perms-check.sh` with a selftest, wired into `check.sh`.
6. **Workflow hygiene from the siblings**: minimal graded permissions; job gated on the default branch and checkout pinned to it with `persist-credentials: false`; a concurrency group with `cancel-in-progress: false`; a `::notice::`-and-stop path when the provider secret is absent; the action pinned by commit SHA. If the routine takes a `🚢 SHIP-LOCK` (today the burn and the design run), add the lock lifecycle too: step timeouts strictly below the job timeout so the cleanup ([`scripts/routine-lock-cleanup.sh`](../../scripts/routine-lock-cleanup.sh)) stays reachable, plus a final step that turns a dead run red. Lock-free routines need only the job timeout — their terminal ship step failing is the red signal.

Then update CLAUDE.md (the routine's bullet and skill mention), README.md's "Operating the automation" list, and the platform charter if the routine changes what the system *is*. The full architecture of the loop is in [The autonomy loop](autonomy.md).

## A new skill

Create `.claude/skills/<name>/SKILL.md` and mention `/<name>` in CLAUDE.md (docs-check verifies both directions). For a reviewer persona specifically, [docs/reviewer-personas.md](../reviewer-personas.md) is the pattern and registration checklist — one lens, one reference pack, PM-gated tags, never a merge verdict.

## A new top-level directory

Mention it in CLAUDE.md and README.md (docs-check), and give it a case arm in [`scripts/ci-classify.sh`](../../scripts/ci-classify.sh) — that is what makes PRs against it verifiable. Without one, a PR touching only the new directory either strands (under branch protection that names the required jobs, required contexts never run) or merges green having tested nothing (under a ci-ok-only protection, where skipped counts as passing) — both wrong. The advisory `classifier-coverage` gate flags an uncovered directory, but note its criterion is a literal `<dir>/` token in `ci.yml`'s text (it predates the classifier's extraction into the script), so the warning can outlive the fix until `ci.yml` mentions the directory.

## A site change

Read [site/README.md](../../site/README.md) first — it states the three scoped guarantees new code must respect (deterministic offline build; deploy-time fetches only through best-effort, flag-gated, empty-on-failure seams like `lib/releases.mjs`; served bytes reference nothing external — vendored assets only, no CDN). House rules that follow: new `site/lib/` modules get listed in site/README's Layout and tested in `site/test/` (`node --test`, fixture repos in a tmpdir, a negative control per rule); anything a page links must resolve on disk or the build fails; and remember Vercel runs only install+build — the tests run in `./scripts/site.sh` and CI's `site-build` job, so never skip those locally. If your change adds or removes site *inputs*, update [`scripts/vercel-ignore-build.sh`](../../scripts/vercel-ignore-build.sh)'s classification and selftest to match.
