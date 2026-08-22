# Contributing to the print-bench platform

The contributor guide for the system underneath the designs — the scripts, gates, CI, shared libraries, tools, product site, and autonomy routines. If you want to *design a printable part*, this is not your guide: the co-design workflow lives in [CLAUDE.md](../../CLAUDE.md), and a dedicated creator guide is planned.

## The map

Read [Getting started](getting-started.md) first; after that the pages stand alone.

| Page | What it covers |
|---|---|
| [Getting started](getting-started.md) | The toolchain, the environment contract (`OPENSCADPATH`, `OPENSCAD_BIN`, headless rendering), and your first green check run |
| [CI and the gates](ci-and-gates.md) | What CI runs, how it decides what to run for your PR, what each gate proves, and the regen job that commits derived artifacts onto your branch |
| [Conventions](conventions.md) | The standing rules the checks enforce — derived artifacts are CI's job, docs are drift-checked, every check proves it can fail, never trust an OpenSCAD exit code, the license boundary, and more |
| [Extending the platform](extending.md) | Recipes for each kind of change: a new script, library, tool, smart-CI gate, scheduled routine, skill, top-level directory, or site change |
| [The autonomy loop](autonomy.md) | The agent routines that triage, ship, chunk, propose and report — and the safety architecture that keeps each one advisory, narrowly scoped, or human-gated behind a draft PR |
| [Pull requests](pull-requests.md) | The lifecycle of a PR here: what CI does to your branch, the review personas, the decision gate, and how forks differ |

## How these docs work

Three rules keep this guide trustworthy, and they bind you when you edit it:

- **Route, don't duplicate.** Anything already documented authoritatively once — the script inventory in [CLAUDE.md](../../CLAUDE.md), the architecture deep-dives in [docs/architecture/](../architecture/README.md), a tool's own README — is *linked* from here, not restated. A duplicated fact is a future lie: this repo's docs-drift check ([`scripts/docs-check.sh`](../../scripts/docs-check.sh)) mechanically verifies enumerations against the tree, and it only covers the enumerations that live in the files it checks.
- **Docs are served, not just stored.** The product site serves these pages verbatim as raw markdown under `/docs/contributing/`, and indexes them (with every other markdown source it serves) at `/llms.txt`, following the [llms.txt](https://llmstxt.org/) convention — so an LLM agent can consume the whole guide without scraping HTML. `/llms-full.txt` is this guide plus the architecture docs in a single fetch. The index is derived from the docs' own titles and first paragraphs by [`site/lib/llms.mjs`](../../site/lib/llms.mjs), never hand-maintained.
- **Broken links fail the build.** Because these pages are served, their local references are checked against the repo tree by the site build (`npm --prefix site test` runs the census; `./scripts/site.sh` runs both). Served verbatim means never rewritten: a repo-relative link here resolves in a checkout or on GitHub, not necessarily on the site host — that trade is deliberate and documented in [site/README.md](../../site/README.md). Open every new page with a prose paragraph whose **first sentence** works standalone — that sentence becomes the page's annotation in `/llms.txt`, and the census requires this index to link every sibling page.

## The platform in one paragraph

print-bench is a co-design bench: humans bring design ideas, AI sessions model them in OpenSCAD, and a gauntlet of deterministic gates — full CGAL renders, mesh printability scoring, a real slicer pass, product-page and docs-drift checks — decides what ships. Around that core sits an automation layer that regenerates every derived artifact in CI (previews, galleries, product shots), a static product site generated from the committed tree, and a set of scheduled agent routines that triage the backlog, ship small issues, and report on the system's health — each one advisory-only, boxed in by narrow tool surfaces and deny backstops, or (for the ship routines) landing nothing a human hasn't reviewed, because their only output is a draft PR. The platform charter ([PM.md](../../PM.md)) names the non-negotiables; contributions that fight them will bounce in review.
