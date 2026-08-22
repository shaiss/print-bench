# Contributing to print-bench

Two kinds of contribution land here, with different front doors:

- **Contributing to the platform** — the scripts, gates, CI, shared
  libraries, tools, site, and autonomy routines that everything else runs
  on. Start with **[docs/contributing/](docs/contributing/README.md)**:
  the full contributor guide, from environment setup to landing a PR.
- **Designing a part** — bringing an idea and co-designing a printable
  model. A dedicated creator guide is planned; until then the co-design
  workflow in [CLAUDE.md](CLAUDE.md) and the design-brief front door
  (`/intake`, or the *Design brief* issue form) are the path in.

## The short version (platform)

```bash
.claude/hooks/session-start.sh --force   # install the toolchain
./scripts/check.sh                       # the fast pre-commit check set
./scripts/gate.sh --slice                # what CI enforces on designs
./scripts/site.sh                        # site unit tests + the deploy's build
```

Before any push, run `/preflight` in a Claude Code session, or the local
check set the guide walks through in
[Getting started](docs/contributing/getting-started.md) — the commands
above are the core of it, scoped to what you changed. Open PRs as drafts.
CI regenerates every derived artifact itself and commits the result onto
your branch — don't commit generated output by hand ([Pull
requests](docs/contributing/pull-requests.md) covers the mechanics, and
how the contract inverts on a fork).

Contributions are accepted under the repository's existing terms
(inbound = outbound): the first-party tree is CC-BY-SA-4.0 — see
[LICENSE](LICENSE), including the vendored-code boundary.

## These docs are AI-native

The platform docs are plain markdown in the repo, and the product site
serves them machine-readably — an [llms.txt](https://llmstxt.org/) index at
the site root, raw-markdown routes beside every rendered page. The serving
contract lives in one place: "How these docs work" in
[docs/contributing/](docs/contributing/README.md). Point an agent at the
site's `llms.txt` and it has the whole contributor guide without scraping
HTML.
