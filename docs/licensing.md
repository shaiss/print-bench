# Licensing policy: what may combine with what

**Status: decided.** This is the standing print-bench policy on GPL/copyleft
libraries, resolving issue [#160](https://github.com/shaiss/print-bench/issues/160)
(decided 2026-08-10). It generalises the case that prompted it — vendoring
NopSCADlib (GPL-3.0) for the assembly-docs feature ([#98](https://github.com/shaiss/print-bench/issues/98) → [#155](https://github.com/shaiss/print-bench/issues/155)) —
into a rule for GPL/copyleft libraries generally, not just NopSCADlib.

It is written so a contributor **and** an agent can apply it without re-arguing
the licensing question case-by-case. Where it needs teeth it has a check
(`scripts/license-boundary-check.sh`); where the obligation is legal it is
stated in [`LICENSE`](../LICENSE).

> This is repository policy, not legal advice. The `LICENSE` file governs; this
> doc explains how we apply it.

## The one rule

**Copyleft stays in the design layer. It never reaches shared first-party core.**

A single design may opt into a GPL/copyleft library; the shared libraries,
the tooling, and the site may not. That split is the whole policy — everything
below is what it means in each corner of the tree.

## The license layers

| What | License | Reach |
|---|---|---|
| The first-party tree (`designs/`, `lib/*.scad`, `styles/`, `scripts/`, `tools/`, `site/`, docs) | **CC-BY-SA-4.0** | copyleft, but for creative works — see the `LICENSE` caveat |
| `lib/BOSL2/` (vendored) | **BSD-2-Clause** | permissive — no copyleft reach |
| `lib/NopSCADlib/` (vendored) | **GPL-3.0** | copyleft — reaches **combined works** |

BOSL2 and NopSCADlib are both vendored as **mere aggregation**: upstream terms
intact, never edited, kept the same way (see `lib/BOSL2/LICENSE`,
`lib/NopSCADlib/COPYING`, and `lib/NopSCADlib/VENDORED.md`). The difference is
what happens when first-party code *uses* them.

## Aggregation vs. combination

- **Aggregation** — a library sitting vendored in the tree, unused, or used only
  by things kept isolated. Fine for any license. A GPL library can live in
  `lib/` forever with no obligation on the rest of the repo.
- **Combination** — first-party code that `include`s / links / bundles the
  library so the exported artifact is built from it. For GPL-3.0 this produces a
  **combined work** carrying the GPL obligation. This is the line the policy
  governs.

The question is never "is NopSCADlib in the tree" (aggregation, always fine).
It is "does *this* first-party unit combine with it, and if so, is that unit a
single opted-in design or shared core?"

## The policy, corner by corner

### 1. Shared first-party libraries (`lib/*.scad`) — **hard no**

No shared `lib/*.scad` module may `use` / `include` a copyleft-vendored library.

A shared library is used by many designs. If it combined with GPL, **every**
design that used it would become a combined work — the copyleft obligation would
spread across the catalogue, the exact opposite of design-layer isolation. So
this is the strictest line, and the one the check enforces first.

Use permissive libraries in shared code freely: BOSL2 (BSD-2-Clause), the
first-party `lib/*.scad` helpers, MCAD (system-installed, see below).

### 2. Tooling (`scripts/`) — invoking is fine, bundling is not

The line for core tooling is **distributed source**, not tool use:

- **Allowed: invoking GPL tools the repo does not ship.** `scripts/` shells out
  to OpenSCAD and PrusaSlicer, and drives Blender in-process via `import bpy`
  (`tools/photoshot/`). All three are GPL, none is conveyed by print-bench — the
  user or CI installs them. Running a separate GPL program, or using a library
  the repo does not distribute, conveys no GPL. This is fine.
- **Allowed: a generator that emits a per-design opt-in.** `scripts/assembly.sh`
  writes a `.scad` that `include`s NopSCADlib to render a design's exploded view
  and BOM — but only for a design that ships an `assembly.conf`, i.e. a design
  that has already opted into NopSCADlib at the design layer ([#156](https://github.com/shaiss/print-bench/issues/156)).
  The generator is the mechanism that realises that one design's opt-in; the
  combined work it produces is scoped to that design, not to core. The tool
  itself is first-party CC-BY-SA-4.0 code that emits an include *string*; it does
  not itself combine with GPL.
- **Forbidden: bundling vendored copyleft source into distributed first-party
  code.** A script may not copy `lib/NopSCADlib/` into a first-party distributed
  artifact, nor make a shared first-party module combine with it.

### 3. The site (`site/`) and distributed build artifacts

- **The site build** may not vendor copyleft source into the served bytes. The
  site is first-party CC-BY-SA-4.0; bundling `lib/NopSCADlib/` into `build/site`
  would make the served bundle a combined work. (In practice the site renders
  *product pages and previews already committed*, so it has no reason to.)
- **A product page for a design that opted into GPL** carries that design's
  disclosure (the product-page requirement below) and, because the page offers
  the design for download, links its corresponding source. Scoped to that page.
- **Release bundles** (`scripts/release-bundle.sh`, the "Release bundles"
  workflow) that ship a GPL-opted design's STLs: see distribution, below.

### 4. The design layer — opt-in, disclose, isolate (already decided, [#155](https://github.com/shaiss/print-bench/issues/155))

A single design **may** use a GPL/copyleft library. When it does:

- it **discloses on its product page** (`README.md`) that it incorporates a
  GPL-3.0 part — enforced presence-only by `scripts/readme-gate.sh`;
- the derivative/lineage system (`derives.conf`, `docs/derivative-designs.md`)
  keeps it an **isolated, attributed unit**, so the obligation does not silently
  spread to designs that don't use the library;
- the opt-in is **per design**: a design that doesn't include the library is
  entirely unaffected.

## Distribution: conveying a GPL-opted design

When print-bench **distributes** the artifacts of a design that opted into a
GPL/copyleft library — the release-bundle STLs, the site download links — GPL's
convey-with-notice-and-source obligation applies, **scoped to that one design**:

- that design's release bundle and product page carry the GPL notice and link
  the **corresponding source** (the design `.scad` plus the vendored library
  under `lib/NopSCADlib/`, which the repo already ships);
- **every other design, and all of core, is untouched** — the obligation rides
  with the opted-in unit and nothing else.

Core and non-GPL designs stay CC-BY-SA-4.0 with no GPL notice, because they
convey no GPL. Today no design ships an `assembly.conf` or otherwise opts in, so
no bundle carries a GPL notice yet; this is the rule for when one does.

## Enforcement

The split is enforced by construction, not memory:

- **`scripts/license-boundary-check.sh`** (run by `scripts/check.sh`, so by
  `/preflight` and CI) — fails if a shared first-party `.scad` includes a
  copyleft-vendored library (Rule A) or if core/site code bundles the vendored
  copyleft source tree (Rule B). It deliberately does **not** flag design-layer
  opt-ins, tool invocation, or a generator emitting a per-design include string.
  Its `--selftest` proves both rules still fire on a planted violation.
- **`scripts/readme-gate.sh`** — presence-only check that a design using a
  GPL part discloses it on its product page (the design-layer obligation).
- **`LICENSE`** — the legal statement of the boundary and the design-layer
  disclosure rule.
- **`lib/NopSCADlib/VENDORED.md`** — the per-library provenance and the same
  boundary in short form.

## Extending this when vendoring another copyleft library

Vendoring a new GPL/AGPL/copyleft library is a real license event, not a drop-in.
In one PR:

1. Vendor it as mere aggregation (upstream terms intact, never edited), with a
   `VENDORED.md` like `lib/NopSCADlib/`'s.
2. Add its include-root to `COPYLEFT_ROOTS` in
   `scripts/license-boundary-check.sh` (this is what makes the gate cover it).
3. Name it and its license in `LICENSE` (the vendored-code notice) and in this
   doc's layer table.
4. Add it to the `CLAUDE.md` library list with the boundary note, the way
   NopSCADlib is listed.

A **permissive** library (BSD/MIT/Apache/…, like BOSL2) skips step 2 — core may
combine with it — but still gets vendored cleanly and named in `LICENSE`.

## Scope notes

- **MCAD** is system-installed (not vendored in `lib/`) and used by designs via
  `include <MCAD/...>`. Like OpenSCAD and PrusaSlicer, it is a tool the repo does
  not ship, so it is out of scope for the vendored-source gate here. It is not
  vendored copyleft source in the tree.
- **CC-BY-SA-4.0 vs. software.** The first-party tree's own copyleft is a
  creative-works license, chosen deliberately to keep one license over a tree
  whose code and designs are inseparable in the artifact they produce; the
  trade-off is recorded in `LICENSE`. It is unrelated to the GPL boundary this
  doc governs.

## Can I…? (quick reference)

| Situation | Verdict |
|---|---|
| Use BOSL2 in a shared `lib/*.scad` | ✅ permissive, always fine |
| Use NopSCADlib in one design (and disclose on its page) | ✅ design-layer opt-in ([#155](https://github.com/shaiss/print-bench/issues/155)) |
| `include <NopSCADlib/...>` in a shared `lib/*.scad` | ❌ spreads GPL to every consumer — Rule A fails |
| A `scripts/` tool shells out to OpenSCAD/PrusaSlicer | ✅ invoking a tool we don't ship |
| `import bpy` in `tools/photoshot/` | ✅ same — Blender is not conveyed |
| `assembly.sh` emits a per-design `include <NopSCADlib/...>` | ✅ realises a design opt-in, scoped to it ([#156](https://github.com/shaiss/print-bench/issues/156)) |
| Copy `lib/NopSCADlib/` into `build/site` or a first-party bundle | ❌ bundles vendored GPL source — Rule B fails |
| Ship a GPL-opted design's STLs in a release bundle | ✅ with scoped GPL notice + corresponding-source link |

## References

- `LICENSE` — the legal boundary and the CC-BY-SA-4.0 caveat.
- `lib/NopSCADlib/VENDORED.md` — provenance and the short-form boundary.
- `docs/derivative-designs.md` — how the lineage system keeps a design isolated.
- Issue [#160](https://github.com/shaiss/print-bench/issues/160) — this decision.
  Issue [#155](https://github.com/shaiss/print-bench/issues/155) — the design-layer decision it builds on.
  Epic [#98](https://github.com/shaiss/print-bench/issues/98) — the assembly-docs feature that surfaced it.
