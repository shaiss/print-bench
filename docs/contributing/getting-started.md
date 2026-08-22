# Getting started

How to stand up the toolchain, understand the environment contract every script assumes, and get your first green check run — the on-ramp for platform contributions.

## Install the toolchain

The repo installs its own tools. One script owns the recipe:

```bash
.claude/hooks/session-start.sh --force
```

That is the SessionStart hook, and its self-installing path is narrower than it looks: it installs automatically only in Claude Code **on the web** (`CLAUDE_CODE_REMOTE=true`); everywhere else — including a local Claude Code session — it is a deliberate silent no-op without `--force`. It is idempotent — re-run it any time a tool goes missing — and installs the render/slice/preview toolchain via apt plus editable installs of [`tools/printcheck`](../../tools/printcheck/README.md) and [`tools/stylelift`](../../tools/stylelift/README.md) with pytest. The exact package list lives in one place, the script itself — its header comments are the authoritative install documentation: [`.claude/hooks/session-start.sh`](../../.claude/hooks/session-start.sh).

Two tools are deliberately not in the default set:

- **`bpy`** (Blender as a Python module, behind `product-shot.sh`) is a ~1 GB wheel you only need to preview product shots locally — CI renders and commits them. Install with `.claude/hooks/session-start.sh --force --with-bpy` (both flags; the hook documents the Python-3.11 and `python3 -m pip` caveats).
- **`sca2d`** (behind the advisory `lint-scad.sh`) — `pip install sca2d` yourself if you want the static-analysis report.

You also need `python3` (3.10+) — several tools run straight out of `tools/*/src` with no install step — and Node.js for the site build (`./scripts/site.sh` below; skip that command if you won't touch the site).

## The environment contract

Every script in `scripts/` assumes three things; if you invoke `openscad` by hand you must supply them yourself:

- **Headless rendering.** There is no display here; every OpenSCAD invocation goes through `xvfb-run -a`. A bare `openscad` fails.
- **`OPENSCADPATH="$PWD/lib:$PWD"`** — `lib/` resolves library includes, the repo root resolves `include <styles/<name>/style.scad>`. This one is a silent-failure trap: without it, an unresolved `use <printability.scad>` produces only a WARNING, exit 0, and a watertight, sliceable STL *with the features missing*. Nothing about the exit code tells you the geometry is wrong.
- **`OPENSCAD_BIN` / `OPENSCAD_ARGS`** — the binary and extra flags are variables, never hardcoded (CI's fast render path runs `openscad-nightly` with `--backend=manifold`; the stable 2021.01 job keeps designs compatible with the release build). The rule and its enforcement are in [Conventions](conventions.md).

The general lesson behind all three: **never trust an OpenSCAD exit code**. The repo's checks grep output text or measure the exported mesh instead — see [Conventions](conventions.md).

## Your first green run

```bash
./scripts/check.sh          # the fast pre-commit check set
./scripts/gate.sh --slice   # what CI enforces on designs: printcheck + a real test-slice
./scripts/site.sh           # site unit tests + the same build Vercel runs (needs Node)
```

`check.sh` is much more than a syntax pass: it echo-checks every non-archived `.scad` (failing on wrong-geometry warnings OpenSCAD emits while exiting 0; a design frozen by an `ARCHIVED` marker is skipped), CGAL-renders every shared library's demo, runs the library guard and mate checks, the license boundary, the docs-drift check, and the selftest of nearly every gate script — the script's own body is the authoritative and still-growing list. If `check.sh` is green, the standing conventions are intact.

Two local failures are *expected* and CI fixes them for you (except on a fork — see [Pull requests](pull-requests.md)): a stale README gallery, and a product page missing an image that CI's regen job renders and commits itself. The `/preflight` skill ([`.claude/skills/preflight/SKILL.md`](../../.claude/skills/preflight/SKILL.md)) is the canonical "would CI pass?" answer — it runs the exact checks CI runs, scoped the same way CI scopes them, and documents which local reds to ignore.

## Orient yourself

- [docs/architecture/](../architecture/README.md) — the system's two-layer split (domain-agnostic CI platform, OpenSCAD design workflow) and the three seams joining them. Read `design-workflow.md` first (what the machine builds), then `ci-platform.md` (how it ships).
- [CLAUDE.md](../../CLAUDE.md) — the working reference for sessions: the command block, the repository layout with every script and library enumerated (that enumeration is mechanically enforced — see [Conventions](conventions.md)), and the co-design workflow.
- [PM.md](../../PM.md) — the platform charter: the non-negotiables (N1–N6), the "never" list, and the health invariants. Contributions that fight the charter bounce in review, so read it before proposing structural change.
