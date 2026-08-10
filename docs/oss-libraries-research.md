# OSS libraries & tooling: research and adoption record

Two research passes over the open-source OpenSCAD ecosystem, evaluated
against this repo's stack (vendored BOSL2, `lib/printability.scad`,
`tools/printcheck`, PrusaSlicer CI gate), with the second pass verified
claim-by-claim against live repo/release pages on **2026-08-02** and the
winners implemented in the same PR that adds this document.

## Adoption scorecard

| Recommendation (pass 1, Aug 1) | Verdict after verification | Status |
|---|---|---|
| OpenSCAD nightly + Manifold backend | Confirmed, biggest win | **✅ Implemented** — render-gate + a new check job run `openscad-nightly --backend=manifold` (OBS repo); stable 2021.01 job kept as compatibility baseline |
| SCA2D linter | Confirmed, project revived (v0.4.0, Jun 2026) | **✅ Implemented** — `scripts/lint-scad.sh`, report-only CI step (0 errors / 18 structural warnings baseline) |
| Tweaker-3 auto-orientation | Still OSS state of the art (active Mar 2026), but printcheck's native `orientation.py` covers the gate's needs | **Superseded natively** — revisit only if scored support-volume orientation is wanted |
| NopSCADlib | Solid, but no current design needs vitamins/BOM | **✅ Vendored** — `lib/NopSCADlib/` (GPL-3.0, issue #155); the first stage of the assembly-docs feature (#98). Vendored as mere aggregation like BOSL2, with the GPL-3.0 vs BSD-2-Clause vs CC-BY-SA-4.0 boundary documented in `LICENSE`, `CLAUDE.md`, and `lib/NopSCADlib/VENDORED.md`. No design includes it yet; `scripts/nopscadlib-check.sh` proves the include resolves. |
| Round-Anything | Fine, no current pain point (BOSL2 covers rounding) | **Deferred** — adopt per-design |
| openscad_docsgen | Fine, `lib/` is still two files | **Deferred** |
| PrusaSlicer upgrade (pass 2 idea) | **Refuted in verification**: upstream stopped shipping Linux binaries after 2.9.0 — 2.9.4/2.9.5/2.9.6 are Windows/macOS/source only, Linux is Flatpak-only (too heavy for CI) | **Dropped** — apt 2.7.x stays; noted in `ci.yml` |

Also implemented while here: `ci.yml`'s push trigger still pointed at the
pre-rename default branch (`claude/3d-printable-openscad-5341we`), so CI
never ran on pushes to `main` — fixed to `branches: [main]`; and
`printcheck` gained `--repair` (below) plus a verified `trimesh>=4,<6` pin
(suite passes on trimesh 5.0.0, released 2026-08-01).

## printcheck `--repair`

`manifold3d` (already a printcheck dependency; 3.5.2 as of Jun 2026)
provides guaranteed-manifold booleans. `printcheck --repair` splits a
defective mesh into connected components, rebuilds each as a Manifold, and
boolean-unions the set — exactly the fix for the most common export
mistake here ("shells concatenated instead of unioned", the
`sushi-battleship-top` failure class). It writes `<model>.repaired.stl`
for slicing experiments; the exit code still judges the original mesh
because the real fix belongs in the `.scad` source. Kiss contacts and open
holes are design problems it deliberately won't paper over.

## Ecosystem state, verified Aug 2026

### OpenSCAD core
- **Still no stable release after 2021.01**, but a 2026.0X RC is in
  preparation: release-checklist [issue #6410](https://github.com/openscad/openscad/issues/6410)
  open since Nov 2025, `openscad-2026.01.01-TEST2` machinery-test tags on
  GitHub. Dev snapshots are the de-facto current OpenSCAD; **Manifold is
  the default backend** in snapshots (`--backend` help text: "'CGAL'
  (old/slow) or 'Manifold' (new/fast) [default]").
- Nightly-only CLI features relevant to CI: `--summary-file` (JSON
  bbox/area/geometry stats), `-O section/key=value` export options, color
  3MF export (still lossy into some slicers, [#5994](https://github.com/openscad/openscad/issues/5994)),
  experimental Python (`--trust-python`).
- Install routes: OBS apt repo (`home:t-paul`, used by our CI),
  [official Docker images](https://github.com/openscad/docker-openscad)
  with date-pinned `dev.*` tags, snap. The 2021-era
  `Irev-Dev/action-install-openscad-nightly` action is dead (2 commits,
  2022) — don't use it.

### Editor/format/lint tooling
- **[SCA2D](https://gitlab.com/bath_open_instrumentation_group/sca2d)**
  revived: v0.3.x Aug 2025, v0.4.0 Jun 2026. Honors `OPENSCADPATH`.
  Adopted here report-only; promote to a gate by flipping `REPORT_ONLY`
  in `scripts/lint-scad.sh` once the signal proves trustworthy.
- **[Topiary](https://github.com/tweag/topiary)** (tree-sitter formatter)
  gained first-class OpenSCAD support (v0.6.0, Jan 2025; queries written
  against BOSL2 idioms); [openscad-LSP](https://github.com/Leathong/openscad-LSP)
  v2.0.2 (May 2026) embeds it. The credible `.scad` format-check option if
  we ever want one; `scadformat` (Go, last commit Sep 2025) is the simpler
  but less-alive alternative. Not adopted — formatting drift isn't a
  problem here yet.
- **[openscad-playground](https://github.com/openscad/openscad-playground)**
  (official WASM port, commits Jul 2026) — zero-install browser previews
  with Customizer; a nice hand-off channel for finished designs.
  openscad-wasm can't render PNG (no GL) so it can't replace xvfb in CI.

### Mesh QA / repair (printcheck's neighborhood)
- **trimesh 5.0.0** (2026-08-01): supported; pinned `>=4,<6`, suite green.
- **manifold3d 3.5.2**: backs the new `--repair`.
- **[argus-diff](https://github.com/mikelmyers/argus-diff)** (MIT,
  v0.1.1, Jun 2026): "git diff for CAD" — geometric STL/3MF diff with a
  GitHub Action that comments rendered before/after + volume/bbox deltas
  on PRs, plus CI gates. The missing review layer for design PRs; still
  v0.1.x, so adopt as a non-blocking job when we try it. Runner-up
  diff3d is interactive-only.
- **[PyMeshLab](https://pypi.org/project/pymeshlab/)** (2025.7.post1,
  Jan 2026, GPL): heavier second-tier repair (self-intersections,
  T-junctions) if manifold3d union ever isn't enough — subprocess only,
  keep the GPL boundary clean.
- Ruled out: MeshLib (non-commercial license), PyMeshFix (AGPL),
  Open3D (no release in 19 months), vedo (duplicates trimesh),
  PySLM (metal-AM heavy; only credible support-*volume* estimator if we
  ever want one).
- **Reversed:** bpy headless was ruled out here on wheel size alone. It
  was later *adopted* as the product-shot renderer (`tools/photoshot/`),
  replacing POV-Ray: it is the only OSS renderer that is simultaneously
  alive, pip-installable (the sole reachable registry in these sessions),
  headless without an X display, and CPU-competent — and unlike POV-Ray
  it is thread-count invariant, so reproducible output costs no render
  time. The wheel is 356 MB (801 MB installed), which is the price.
- **3MF as CI artifact**: [lib3mf](https://github.com/3MFConsortium/lib3mf)
  2.5.0 is healthy, but STL stays right for this repo until the nightly's
  color-3MF quirks settle and slicer support catches up.

### Slicers / CI integration
- **PrusaSlicer**: 2.9.6 (Jun 2026) exists upstream but Linux binaries
  were discontinued after 2.9.0 (Flatpak-only) — apt 2.7.x remains the
  CI slicer. Its G-code still carries `estimated printing time`, which
  `gate.sh` surfaces.
- **OrcaSlicer 2.4.2** (Jul 2026): headless CLI works but is fragile
  (profile-JSON ordering, `.gcode.3mf` output, silent failures) — only
  worth it to gate against Bambu/Orca profiles. CuraEngine: no standalone
  binary distribution. klipper_estimator: **archived Jan 2026**, skip.
- **[f3d](https://github.com/f3d-app/f3d)** (v3.5.0, Apr 2026, very
  active): headless CLI PNG renders of the exported STL artifact with
  consistent lighting — worth a spike for PR-comment previews of what the
  slicer actually sees (complements, not replaces, the OpenSCAD source
  contact sheet). stl-thumb is semi-dormant by comparison.
- G-code previews: no maintained toolpath renderer; the practical path is
  PrusaSlicer-embedded thumbnails +
  [gcode-thumbnail-tool](https://github.com/OctoPrint/gcode-thumbnail-tool)
  (active Jun 2026). Turntable GIFs: every dedicated tool is dead; use
  OpenSCAD `--animate` + ImageMagick if wanted.

### Design libraries (adopt per-design, nothing to vendor today)
- **Gridfinity**: [kennetek/gridfinity-rebuilt-openscad](https://github.com/kennetek/gridfinity-rebuilt-openscad)
  shipped a big v2.0.0 rewrite (Aug 2025) then went quiet; active
  development lives in [ostat/gridfinity_extended_openscad](https://github.com/ostat/gridfinity_extended_openscad)
  (commits Jul 2026, GPL-3). Start from ostat for organizer sessions.
- **[QuackWorks](https://github.com/AndyLevesque/QuackWorks)** (CC
  BY-NC-SA — mind the NC): the Underware/openGrid/Multiconnect
  cable-management + mounting ecosystem, BOSL2-based, huge MakerWorld
  user base. The go-to for wall/desk mounting interfaces.
- **[YAPP_Box](https://github.com/mrWheel/YAPP_Box)** (MIT, v3.3.8 Aug
  2025): PCB-driven project-box generator — fills the enclosure gap
  outright when an electronics box comes up.
- **BOSL2** upstream still tags v2.0.747 (bot-bumped Jun 2026) — our
  vendored copy is current. Its `hinges.scad` already covers
  print-in-place joints; snap-fit/compliant-mechanism libraries elsewhere
  are all dead (agentscad, 2023).
- **[openscad-library-manager](https://github.com/openscad/openscad-library-manager)**
  (official org, index updated Jul 2026): a real package manager is
  coming; watch it — it may eventually replace hand-vendoring.
- Niche watches: [omdl](https://github.com/royasutton/omdl)
  (docs-first mechanical framework),
  [openscad_attachable_text3d](https://github.com/jon-gilbert/openscad_attachable_text3d)
  (BOSL2-attachable labels, quiet since 2024).

## Backlog (deliberately not in this PR)

1. **argus-diff spike** — non-blocking PR job commenting geometric diffs
   of `build/*.stl` between base and head. Wait for >v0.1.x or accept
   comment-only.
2. **f3d artifact previews** — render gated STLs to PNG in CI, attach to
   the sticky comment.
3. **Round-Anything / openscad_docsgen** — adopt per-design when a design
   needs polyRound profiles or generated lib docs. (NopSCADlib, formerly in
   this backlog item, was vendored in issue #155.)
4. **Topiary format check** — only if formatting drift appears.
5. **`--summary-file` gating** — once CI is proven on nightly, printcheck
   could cross-check its numbers against OpenSCAD's own JSON summary.

## Sources

Pass 1 (2026-08-01) and pass 2 (2026-08-02) primary sources:

- https://github.com/openscad/openscad (releases, issues #6410/#6664/#5849/#5994, `src/openscad.cc` on master)
- https://lists.openscad.org/empathy/thread/D6KV3ZLXHLBHSITSQ5GPUZUKHURU4ABE
- https://github.com/openscad/docker-openscad · https://hub.docker.com/r/openscad/openscad
- https://gitlab.com/bath_open_instrumentation_group/sca2d (tags)
- https://github.com/tweag/topiary (PR #845, releases) · https://github.com/Leathong/openscad-LSP · https://github.com/hugheaves/scadformat
- https://github.com/openscad/openscad-playground · https://github.com/openscad/openscad-wasm
- https://pypi.org/project/trimesh/ · https://pypi.org/project/manifold3d/ · https://pypi.org/project/pymeshlab/ · https://pypi.org/project/meshlib/ · https://pypi.org/project/pymeshfix/ · https://pypi.org/project/open3d/ · https://pypi.org/project/bpy/ · https://pypi.org/project/PythonSLM/
- https://github.com/mikelmyers/argus-diff · https://github.com/bdlucas1/diff3d
- https://github.com/ChristophSchranz/Tweaker-3 (commits)
- https://github.com/3MFConsortium/lib3mf (releases)
- https://github.com/prusa3d/PrusaSlicer/releases (2.9.4–2.9.6 asset lists) · https://packages.ubuntu.com/noble/prusa-slicer
- https://github.com/OrcaSlicer/OrcaSlicer (releases, discussion #8593) · https://github.com/Ultimaker/CuraEngine
- https://github.com/Annex-Engineering/klipper_estimator (archived)
- https://github.com/f3d-app/f3d (releases) · https://github.com/unlimitedbacon/stl-thumb · https://github.com/OctoPrint/gcode-thumbnail-tool
- https://github.com/kennetek/gridfinity-rebuilt-openscad · https://github.com/ostat/gridfinity_extended_openscad · https://github.com/AndyLevesque/QuackWorks · https://github.com/mrWheel/YAPP_Box · https://github.com/royasutton/omdl · https://github.com/jon-gilbert/openscad_attachable_text3d · https://github.com/openscad/openscad-library-manager
- https://github.com/BelfrySCAD/BOSL2 · https://github.com/nophead/NopSCADlib · https://github.com/Irev-Dev/Round-Anything · https://github.com/JustinSDK/dotSCAD
