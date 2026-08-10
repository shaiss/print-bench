# NopSCADlib — vendored third-party code

This directory is **vendored upstream code**. It is GPL-3.0 (see `COPYING`,
intact from upstream) and is here as *mere aggregation*, the same treatment
`lib/BOSL2/` (BSD-2-Clause) gets:

- **Never edit these files.** They are a verbatim copy of upstream, kept so
  the license boundary and the provenance below stay truthful. If upstream
  has a bug, fix it upstream and re-vendor; do not patch in place.
- **Keep the boundary mechanical:** first-party code under `lib/*.scad` must
  not `use`/`include` this tree. A design may (issue #155, design-layer GPL
  disclosure); shared core tooling may not (see `LICENSE`, `docs/licensing.md`
  and `CLAUDE.md`), and `scripts/license-boundary-check.sh` enforces it.

## What is here and what is not

Copied from [nophead/NopSCADlib](https://github.com/nophead/NopSCADlib) at:

| | |
|---|---|
| upstream | `https://github.com/nophead/NopSCADlib.git` |
| commit | `c9baa0ed0faa23e849141c3d8c6728545d6af910` |
| date | 2025-10-08 |

The **includable library** is vendored verbatim: `core.scad`, `global_defs.scad`,
`lib.scad`, and the `utils/`, `vitamins/`, `printed/` directories — the parts a
design resolves through `OPENSCADPATH="$PWD/lib:$PWD"` when it writes
`include <NopSCADlib/core.scad>`. None of these files has a real
`use`/`include` into the dropped directories (verified).

Deliberately **not** vendored — they are upstream's own dev harness and
showcase, not the library itself, and excluding them keeps this tree under
4 MB instead of 73 MB:

| dropped | why |
|---|---|
| `tests/`, `libtest.scad`, `libtest.png` | upstream's own test/render harness |
| `examples/` | upstream's example gallery (STLs, PNGs) |
| `gallery/` | upstream's rendered showcase images |
| `docs/` | upstream's docgen output (the `//! ![](docs/...)` image refs in `.scad` headers point here; they are docgen comments, not include deps, so the library resolves without them) |
| `scripts/` | upstream's Python tooling (`bom.py`, `doc_scripts.py`, …), not `.scad` |
| `readme.md`, `CHANGELOG.md` | upstream project docs |
| `.git/` | version control metadata |

This matches how `lib/BOSL2/` is treated: upstream's showcase and test trees
are dropped, the includable library and its license are kept verbatim.

## License boundary (GPL-3.0)

NopSCADlib is **GPL-3.0**, which is materially different from this repo's
CC-BY-SA-4.0 and from BOSL2's BSD-2-Clause — see `LICENSE` (the vendored-code
paragraph), `docs/licensing.md` (the full policy), and `CLAUDE.md` (the library
list) for the full boundary. The short form: vendoring as mere aggregation is
fine; **a design that `include`s NopSCADlib and exports geometry is a GPL-3.0
combined work**, and must disclose that on its product page. GPL/copyleft must
not reach the shared first-party core (`scripts/`, the site, `lib/*.scad`):
that is a **standing decision** (issue #160), enforced by
`scripts/license-boundary-check.sh`, not a deferral. Core may vendor NopSCADlib
as aggregation and invoke GPL tools it does not ship, but a shared unit may not
combine with it.
