# printcheck — STL printability analysis

Give it an STL (or OBJ/3MF/PLY), get back a scored printability report:

```
$ printcheck examples/bad_gadget.stl

printcheck report — examples/bad_gadget.stl
============================================================
  size:      34.0 × 24.0 × 42.0 mm
  triangles: 1,416   bodies: 3   watertight: False

  SCORE: 59/100 — NOT PRINTABLE AS-IS

  ✗ [CRITICAL] Mesh is not watertight
  ⚠ [WARNING ] 11% of surface overhangs beyond 45°
  ⚠ [WARNING ] Small bed contact patch
  · [INFO    ] Multiple bodies
```

Everything is deterministic geometry — no AI in the loop unless you
explicitly ask for it (see [AI layer](#the-optional-ai-layer)). 100% open
source dependencies.

## Install & use

```bash
pip install -e .                 # from this repo
python examples/make_demo_models.py
printcheck examples/good_bracket.stl examples/bad_gadget.stl

printcheck model.stl --json                      # machine-readable
printcheck model.stl --nozzle 0.6 --overhang-angle 50
printcheck model.stl --build-volume 220x220x250
printcheck model.stl --fail-under 80             # CI gate: exit 1 below 80
printcheck model.stl --repair                    # also write model.repaired.stl
```

Exit code is `1` when a model is not printable as-is (or under
`--fail-under`), so it drops straight into CI — e.g. gate every STL your
OpenSCAD build exports.

`--repair` re-unions shells that were concatenated instead of
boolean-unioned (via [manifold3d](https://github.com/elalish/manifold)) and
writes `<model>.repaired.stl`. It triggers on integrity failures or on
overlapping bodies — a disjoint plate of parts is left alone. The repaired
file is a convenience for slicing experiments: the exit code still judges
the original mesh, because the real fix belongs in the source model.
Zero-volume "kiss" contacts and open holes are design problems it will not
paper over.

## What it checks

| Check | Method | Flags |
|---|---|---|
| Mesh integrity | topology via trimesh | holes/naked edges, non-manifold edges, inverted or inconsistent normals, duplicate & degenerate faces, stray shells |
| Overhangs | face-normal angle vs build direction (default 45°), bed-touching faces excluded, then **bridgeable regions removed** | area that is too wide to bridge and needs support |
| Wall thickness | inward ray-casting from area-weighted surface samples | walls under 2× nozzle (default 0.8 mm) |
| Bed adhesion & stability | first-layer contact area, center-of-mass vs contact patch | point/edge contact, tiny contact patch, tip-over risk |
| Size | bounding box vs build volume; unit-mix-up detection | oversize, microscopic (meters/inches-as-mm), sub-nozzle features |
| Orientation | scores 6 axis-aligned poses by support need | suggests a rotation when it clearly wins |

Wall-thickness rays are skipped on non-watertight meshes (inside/outside
is undefined on an open surface) — fix the holes first, re-run.

**Overhang = support need, not raw downward area.** A downward face steeper
than 45° only needs support if a bridge cannot span it. So the overhang check
groups the downward faces into connected regions and drops any region that is
everywhere narrower than `--bridge-max` (default 5 mm, the widest span FDM
bridges cleanly) — tested by morphologically eroding the region's footprint,
which handles strokes, rings and annular chamfers correctly, not just boxes. A
debossed letter's ceiling, a thin relief chamfer, and a print-in-place socket
roof are self-supporting and do not score as overhangs; a wide flat shelf still
does. The metrics report both the raw downward area (`raw_overhang_area_mm2`)
and the support-needing remainder (`overhang_area_mm2`).

## The optional AI layer

`printcheck model.stl --ai` appends a plain-English assessment written by
Claude *from the heuristic findings only* — it prioritizes fixes and maps
findings to slicer settings, but never decides printability itself. Needs
`pip install '.[ai]'` and `ANTHROPIC_API_KEY` set. Without the flag the
tool is fully offline.

## `fusecheck` — deterministic fuse detection for print-in-place mechanisms

The package ships a second console entry point, `fusecheck`, for a failure
printcheck structurally cannot see: a print-in-place mechanism (a living-hinge
lid, a snap clamshell) that **welds shut** still exports watertight, and — for a
living hinge — as a *single connected body*, so the integrity checks above all
pass while the part cannot open. A hand-written interference test can catch
fusion, but only in the pose its author intersects, and that pose can be the
wrong one (print-bench's first `sweetheart-hamster` shipped a fitcheck that
tested the *closed* pose while CI sliced the *flat* one, and missed a
1378-facet weld at the hinge).

`fusecheck` answers the un-mis-aimable question on the **sliced STL**, never a
parametric pose: remove the declared thin-flexure zone(s) and count the
separable bodies that remain. A living hinge that joins the two halves *only*
through its flexure splits into 2 once the flexure is removed; a large-area
weld stays 1.

```bash
# both halves of a print-in-place locket, joined only by a hinge web at the
# dorsal seam (rested frame, lowest point at z=0):
fusecheck build/locket.stl --ignore-aabb=-4,-9,-0.1:4,9,1.0
# → 2   (the halves separate)   |   → 1   (fused: the weld reaches past the web)

fusecheck build/locket.stl --ignore-aabb=... --json   # {stl, bodies, dropped_faces, aabbs}
fusecheck --selftest                                  # in-memory positive+negative fixtures
```

It prints the body count and nothing else — a pure measurement, like
`lineage facet-count`. Pass `--ignore-aabb=` with the leading `=` so a
negative first coordinate isn't parsed as a flag. `dropped_faces` in `--json`
is the calibration signal: a zero-drop means the flexure AABB missed the web.
Reuses the same loader and `body_count` as the analyzer above, so a fused
export reads identically to printcheck's `bodies`.

In print-bench, `scripts/gate.sh` drives it from a `designs/<name>/ci.fusecheck`
manifest and applies the per-design thresholds, including a **mandatory
negative control** (a known-fused pose that must still read fused, so the check
can never become unfalsifiable) — the same issue-#37 discipline as
`ci.fitchecks`.

## The OSS landscape (why this exists)

Surveyed before building; use these instead of or alongside printcheck:

- **[trimesh](https://github.com/mikedh/trimesh)** (MIT) — the Python
  workhorse for mesh analysis: watertightness, volume, ray casting,
  sections, repair. printcheck is a thin opinionated layer on top of it.
- **[Blender 3D-Print Toolbox](https://docs.blender.org/manual/en/latest/addons/mesh/3d_print_toolbox.html)**
  (GPL) — ships with Blender; checks manifoldness, intersections,
  thickness, overhangs. Scriptable headless (`blender -b -P script.py`)
  but heavy as a pipeline dependency.
- **[PrusaSlicer](https://github.com/prusa3d/PrusaSlicer) /
  [OrcaSlicer](https://github.com/SoftFever/OrcaSlicer)** (AGPL) — the
  ground truth: if it slices cleanly, it prints. Both have CLIs
  (`prusa-slicer --export-gcode --repair`); pairing printcheck's fast
  triage with a real test-slice is the strongest combo.
- **[admesh](https://github.com/admesh/admesh)** (GPL) — venerable C
  tool/library for STL diagnostics and repair; CLI one-liner for facet
  and edge statistics.
- **[Tweaker-3](https://github.com/ChristophSchranz/Tweaker-3)** (MIT/GPL
  mix) — auto-orientation with an evolutionary-tuned scoring function;
  printcheck's orientation pass is a simplified nod to it.
- **[MeshLab / PyMeshLab](https://github.com/cnr-isti-vclab/meshlab)**
  (GPL) — heavy-duty geometry processing and repair filters, scriptable
  from Python.
- **[Manifold](https://github.com/elalish/manifold)** (Apache-2.0) — the
  robust boolean/manifold kernel (used here via `manifold3d` for the demo
  models; also what OpenSCAD's fast backend uses).

What did *not* make the cut: the pile of "AI STL checker" web tools —
closed-source, upload-your-model services wrapping the same geometric
checks in marketing. Heuristics first; AI only to explain.

## Layout

```
src/printcheck/
  analyzer.py     load mesh, run checks, assemble report
  checks.py       the geometric heuristics (integrity, overhangs, walls,
                  stability, size) + Config
  orientation.py  axis-aligned orientation advisor
  report.py       Finding/Report, scoring, text & JSON rendering
  ai.py           optional Claude summary of the findings
  cli.py          argument parsing, exit codes
tests/            pytest suite w/ programmatically built good & bad meshes
examples/         make_demo_models.py generates demo STLs
```

Run tests: `python -m pytest tests/`
