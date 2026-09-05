---
name: preflight
description: Answer "would CI pass?" before pushing — run the exact checks CI runs, scoped the same way CI scopes them. Use before any push of design or tooling changes, when asked to preflight, pre-check, or verify a branch is green, or when invoked as /preflight.
---

# Preflight — run CI locally before pushing

Mirror `.github/workflows/ci.yml` on the working tree, so a push never
discovers a failure CI could have told you about locally. The contract:
**what you run here is what CI runs there** — same scripts, same scoping
rules. This is now literal, not aspirational: the scoping decision is one
script, `scripts/ci-classify.sh`, that both this skill and the workflow's
`changes` job run — so they cannot drift. If a *check* (the run list in §2)
ever disagrees with the workflow, the workflow is right; follow it and fix
this skill.

## 1. Scope — what changed?

Don't reason about scope by hand — **run the classifier CI runs**:

```bash
./scripts/ci-classify.sh --local
```

It computes the same diff this section used to describe (merge-base with the
default branch — which already covers committed, staged and unstaged tracked
work — plus untracked files) and prints CI's decision as `key=value` lines. It is the *same* `scripts/ci-classify.sh`
that ci.yml's `changes` job pipes its diff to on the server — so what it says
here is what CI does there, by construction rather than by a prose copy that
drifts. Read the outputs and run §2 accordingly:

| output | when `true`, run |
|---|---|
| `gate` | the render gate (§2), scoped to `gate_designs` — a space-separated list, `ALL` for the whole catalog, or empty for "run but gate nothing" |
| `scad` | `check.sh` |
| `styles` | `style-check.sh` |
| `docs_standards` | `docs-standards-check.sh` (selftest first, then the gate) |
| `printcheck_tests` | `pytest tools/printcheck/tests` |
| `stylelift_tests` | `pytest tools/stylelift/tests` |
| `lineage_tests` | `pytest tools/lineage/tests` |
| `backlog_burn_tests` | `pytest tools/backlog-burn/tests` |
| `backlog_groomer_tests` | `pytest tools/backlog-groomer/tests` |
| `model_registry_tests` | `pytest tools/model-registry/tests` |
| `reeve_tests` | `pytest tools/reeve/tests` |
| `brief_sources_tests` | `pytest tools/brief-sources/tests` |
| `telemetry_tests` | `pytest tools/telemetry/tests` |
| `ci_gates_tests` | `pytest tools/ci-gates/tests` |
| `growth_tests` | `pytest tools/growth/tests` |
| `andon_tests` | `pytest tools/andon/tests` |

The classifier already applies everything this section used to spell out by
hand — the geo/soft-infra split, blast radius (a changed design drags in its
derivatives), the style-conf reverse map, and the archived-design skip — so
`gate_designs` is already the exact set CI would gate. It prints the
changed-file list it classified to stderr if you want to see why it chose a
scope.

Two outputs are *not* in the table. `regen`/`regen_designs` name what CI
**regenerates** (previews, shots, gallery) — §3 explains that is CI's job, not
yours, so you run nothing for them. And `readme-gate.sh` is missing on purpose:
CI runs it on **every** PR regardless of scope (the `design-docs` job needs no
installs and takes seconds), so it is always in the §2 run list, never
conditional.

## 2. Run (in this order — fastest failure first)

```bash
# lint (CI runs these on every PR; locally, run when scripts/hooks/workflow changed)
shellcheck --severity=warning scripts/*.sh .claude/hooks/*.sh
actionlint .github/workflows/*.yml   # if missing: install pinned, same as ci.yml's lint job

./scripts/readme-gate.sh                             # product pages + committed GIFs + configured product shots (every PR)
./scripts/docs-standards-check.sh --selftest && ./scripts/docs-standards-check.sh   # if docs_standards=true: docs/page wiring (selftest proves the gate still fires)
./scripts/check.sh                                   # if scad=true
./scripts/lineage.sh selftest                        # before any gate run: proves the derivative check still fires
./scripts/gate.sh --slice <gate_designs...>          # if gate=true: pass the gate_designs list; no args when it is ALL; skip entirely when it is empty ("run but gate nothing")
./scripts/style-check.sh                             # if styles=true
python -m pytest tools/printcheck/tests -q           # if printcheck_tests=true
python -m pytest tools/stylelift/tests -q            # if stylelift_tests=true
python -m pytest tools/lineage/tests -q              # if lineage_tests=true
python -m pytest tools/backlog-burn/tests -q         # if backlog_burn_tests=true
python -m pytest tools/backlog-groomer/tests -q      # if backlog_groomer_tests=true
python -m pytest tools/model-registry/tests -q       # if model_registry_tests=true
python -m pytest tools/reeve/tests -q                # if reeve_tests=true
python -m pytest tools/brief-sources/tests -q        # if brief_sources_tests=true
python -m pytest tools/telemetry/tests -q            # if telemetry_tests=true
python -m pytest tools/ci-gates/tests -q             # if ci_gates_tests=true
python -m pytest tools/growth/tests -q               # if growth_tests=true
python -m pytest tools/andon/tests -q                # if andon_tests=true
```

The `if <output>=true` conditions above are exactly §1's table — read them off
`./scripts/ci-classify.sh --local`, don't re-derive them from the diff.

The pytest lines presume the suite's package is importable. CI pip-installs each
one before running it; locally the SessionStart hook installs only `printcheck`
and `stylelift`. Of the rest, the suites whose tests bootstrap `src/` into
`sys.path` themselves (`lineage`, `stylelift`, `model-registry`, `ci-gates`,
`backlog-burn`) collect with no install, while `reeve`, `backlog-groomer`,
`telemetry` and `brief-sources` die at collection with `ModuleNotFoundError` in
a fresh session — run `pip install -e 'tools/<t>[test]'` on those first (the
same command CI's job uses).

Missing tools (openscad, prusa-slicer, printcheck, stylelift) mean the SessionStart
hook hasn't run — run `.claude/hooks/session-start.sh` first, don't skip
the gate.

## 3. Two failures here that CI fixes for you

CI's `regen` job regenerates derived artifacts and commits them *before*
the jobs that judge them run. So two local failures are expected, not
blockers, and pushing is the fix:

- **`readme-gate.sh`: a `shots.conf` / `animations.conf` entry whose image
  isn't rendered yet.** CI renders and commits it. Only chase this locally
  if you want to look at the framing first (`/product-shots`).
- **`readme-gate.sh`: a product page that is missing or too thin.** CI
  drafts one with `product-page.sh` — but *only* when `ANTHROPIC_API_KEY`
  is set, and only if the draft then passes the gate (it restores the
  original otherwise). So unlike the images, this one is not guaranteed:
  if the key isn't configured, "Design product pages" is a real failure
  and the page is yours to write.
- **`check.sh`: "README gallery is stale".** CI runs `gallery.sh` and
  commits the result. `./scripts/gallery.sh` clears it locally if the noise
  bothers you.

Everything else in the list above is still yours to fix before pushing —
CI regenerates images and prose scaffolding, never geometry, never a gate
verdict. And the exception to both bullets: a PR from a **fork** cannot be
pushed to, so CI fails those instead of fixing them. On a fork branch,
treat both as real.

## 3. Verdict

Report a one-line verdict first: **"CI would pass"** or **"CI would fail:
<step>"**, then per-part printcheck scores (capture the gate output with
`tee` to a log file and run `python3 scripts/gate-summary.py <log>` for the
same table CI posts). A gate
failure is a stop: fix and re-run preflight before pushing. Never soften a
red result — a failed step with output beats a green summary that lies.
