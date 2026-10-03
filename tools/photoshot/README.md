# photoshot — STL → studio product shot

Point it at an STL exported by OpenSCAD and it path-traces a product-page hero
image with Blender's Cycles: seamless studio backdrop, soft key/fill/rim
lighting, a glossy floor carrying the contact shadow, and a plastic material
with faint FDM layer lines. It is the render half of
`./scripts/product-shot.sh` (which does the geometry-true STL export first and
drives this from each design's `shots.conf`), but it runs standalone on any STL.

```bash
python3 tools/photoshot/photoshot.py build/calibration-cube.stl \
  -o designs/calibration-cube/previews/product-hero.png \
  --color e8734a --finish satin --rotz 35 --elev 18 --zoom 0.85 --size 1280x960
```

## Requirements

- **`bpy`** — Blender as an importable Python module, `pip install 'bpy~=4.5.0'`.
  No apt package, no X display, no `xvfb-run`. A missing `bpy` is a hard exit
  pointing at the installer; the SessionStart hook installs it, so run
  `.claude/hooks/session-start.sh --force` rather than work around it.
- Nothing else. Blender's own STL importer does the mesh loading, so this tool
  has no `trimesh` dependency.

The wheel is large (≈356 MB download, ≈801 MB installed) and its wheels are
built per Python minor version, so it needs the interpreter Blender 4.5
targets (3.11). The pin is to the 4.5 LTS series deliberately: output is
byte-reproducible across point releases within a series, but not promised
across them, and these PNGs are committed and diffed.

## Usage

| Argument | Default | Notes |
|---|---|---|
| `stl ...` | required | one or more; all composed into a single scene |
| `-o`, `--output` | required | output PNG; parent directories are created |
| `--color` | `#e8734a` | repeatable, one per STL in order; `#rrggbb`, bare `rrggbb`, or the 3-digit short form |
| `--finish` | `satin` | `satin` \| `gloss` \| `matte` |
| `--rotz` | `35` | orbit angle around the grounded model, degrees |
| `--elev` | `18` | camera elevation, degrees |
| `--zoom` | `1.0` | scales an automatic bounding-box fit; must be > 0 |
| `--size` | `1280x960` | output `WxH` in pixels; each dimension must be 4..65536 (Blender's own range — it clamps silently below 4, so a smaller value would render at 4px while the tool reported the size you asked for) |
| `--layers` | `0.2` | FDM layer-line pitch in mm for the surface texture; `0` or negative = smooth, `nan`/`inf` rejected |
| `--samples` | `48` | Cycles path-tracing samples; with denoising, more than ~48 buys very little |
| `--verbose` | off | let Blender's render log through instead of capturing it |
| `--threads` | `0` | Cycles render threads; `0` uses every core. Raising or lowering it does **not** change the pixels |

`--rotz`/`--elev`/`--zoom`/`--layers` reject `nan`/`inf`, `--zoom` rejects
values ≤ 0, and `--samples` rejects values < 1. Coordinates are OpenSCAD's —
z-up, millimeters.

`--help` returns instantly: the `bpy` import is deferred until after argument
parsing, so a usage error never pays Blender's multi-second load.

## How the scene is built

Everything is generated in `build_scene()`; there is no `.blend` template on
disk.

- **Framing.** All meshes are translated by one shared offset that centres the
  combined bounding box in xy and grounds it on `z = 0` (so multi-part
  assemblies keep their relative positions). The camera is a 30° *horizontal*
  FOV mild telephoto (`sensor_fit = HORIZONTAL`), looking at 42% of the model
  height; `solve_camera()` pushes it back until every bbox corner clears
  **both** the horizontal and the vertical FOV, times a 1.06 margin, divided by
  `--zoom`. That is why a tall part cannot silently lose its top edge.
- **Clip range.** Sized from the solved distance (`dist * 0.001` to
  `dist * 10`). This is not cosmetic: Blender's default `clip_end` is 1000 and
  these scenes are in millimetres, so a 250 mm part framed from ~1.4 m away
  falls entirely beyond the far plane and **renders blank with no error at
  all**.
- **Backdrop.** A world shader with a vertical gradient from light grey to
  white, driven by the z component of the generated texture coordinate through
  a map-range and a colour ramp. It is both the visible seamless-studio
  background and the ambient light bath.
- **Light rig**, scaled to the model's bbox diagonal: a key area light high and
  camera-left; a fill camera-right and a rim behind and above, both with
  `use_shadow = False` so only the key casts the one clean shadow. Area-light
  power is in watts and falls off with distance squared, so energy is scaled by
  the diagonal squared to hold exposure constant across designs of any size.
- **Floor.** A large near-white plane at `z = 0`, roughness 0.22. The soft
  floor reflection and contact shadow, the area-light penumbra and Cycles'
  bounced light are what make the output read as photographed rather than as a
  viewport render.
- **Colour management.** `view_transform = "Standard"`. Blender 4.x defaults to
  AgX, a film emulation that visibly mutes saturated plastics; a product shot
  must show the filament colour that was asked for.
- **Material.** Each STL gets a Principled BSDF with an sRGB→linear base
  colour, `IOR 1.46`, and the parameters below. When `--layers > 0` a wave
  texture (bands along z at the layer pitch) drives a bump node — a shading
  perturbation only, it never changes geometry. Meshes are auto-smoothed at a
  15° angle (see below), so genuinely curved surfaces smooth while real facets stay
  faceted; the shot cannot imply a smoothness the printed part will not have.

  | finish | roughness | specular level | coat weight | coat roughness |
  |---|---|---|---|---|
  | `satin` | 0.38 | 0.45 | 0.12 | 0.35 |
  | `gloss` | 0.18 | 0.60 | 0.35 | 0.10 |
  | `matte` | 0.62 | 0.25 | 0.00 | 0.50 |

Cycles runs on CPU with OpenImageDenoise. Blender's per-sample progress goes
straight to fd 1, below Python's `sys.stdout`, so it is diverted with a
file-descriptor redirect for the duration of the render — into a temp file
rather than `/dev/null`, so a failed render can still show what Blender said.
`--verbose` leaves the fd alone.

A render is only reported as successful if `bpy.ops.render.render()` returns
`FINISHED` **and** the output file's mtime changed. The output path is usually
a committed PNG that already exists, so "the file is there afterwards" would
prove nothing — without the mtime check, a failed render would leave the
previous image in place and report success.

Note on smoothing: `bpy.ops.object.shade_auto_smooth()` cannot be used. It
appends a "Smooth by Angle" geometry-nodes asset, and asset loading never
completes in the headless `bpy` module — it returns `{'CANCELLED'}` and
silently smooths nothing. `shade_smooth()` plus the mesh-level
`set_sharp_from_angle()` gets the same result through the data API.

The threshold (`SMOOTH_ANGLE`) is **15°**, not the 30° that would be the
obvious default, and the difference matters for honesty. At 30° a `$fn=16`
cylinder — 22.5° facets — renders perfectly smooth, implying a roundness the
printed part will not have. At 15°, everything from `$fn=32` up smooths, which
covers the `$fn >= 64` this repo requires for production curves, while coarse
iteration values stay visibly faceted.

## Determinism

Same STL, same args, same machine ⇒ byte-identical PNG. Shots are committed and
diffed across review rounds, so a shot that moves without a geometry change
means something else drifted (manifest, scene code, Blender version). What is
pinned to make that hold:

- The sampling **seed** is fixed, so the stochastic path tracer replays the
  same random sequence every run.
- **Thread count** is set explicitly. Cycles is genuinely thread-count
  invariant here — 1, 2 and 4 threads produce identical pixels, verified — so
  unlike the POV-Ray renderer this replaced, reproducibility costs no render
  time and every core stays usable.
- Blender stamps the PNG with wall-clock `tEXt` chunks (`Date`, `RenderTime`,
  `cycles.*` timings). Those are dropped after the render by a chunk-level
  rewrite that never re-encodes, so pixels are untouched.
- PNG **compression** is raised from Blender's default 15 to 100. Lossless, and
  it takes about a quarter off what lands in git.

**The one caveat that matters across machines:** Cycles dispatches one of two
CPU kernels (SSE4.2 or AVX2) by what the host supports, and their
floating-point rounding differs — on the order of 0.3–0.6% of pixels. Output is
stable on a given machine and across thread counts, but two different machines
produce a near-identical, not byte-identical, image. Compare renders from
different hardware perceptually (RMSE/SSIM), not byte-wise. This matters if a
CI regeneration gate is ever added.

## Colors in `shots.conf`

The manifest field is bare `rrggbb`, **no leading `#`**: `product-shot.sh`
truncates each manifest line at the first `#` (`line="${line%%#*}"`), so a `#`
would comment out the rest of the shot. `parse_color()` here `lstrip("#")`s
either way, so on the command line both forms work.

## Multi-STL composition

Multiple positional STLs render into one scene and `--color` maps to them in
order — a two-tone assembly is `photoshot.py body.stl lid.stl --color 333
--color e8734a -o shot.png`. Any mesh past the last `--color` falls back to the
default orange; more colors than STLs is an error rather than a silent
truncation, since the extra ones name nothing. Note that
`shots.conf` drives exactly one STL export per entry, so multi-STL scenes are
run by hand (see the `/product-shots` skill).

## No tests yet

Unlike `tools/printcheck/`, this tool ships no pytest suite and no
`pyproject.toml` — it is one script invoked by `scripts/product-shot.sh`. Its
pure functions (`parse_size`, `parse_color`, `finite_float`, `srgb_to_linear`,
`strip_png_metadata`, `solve_camera`) are unit-testable as they stand and do
not need `bpy` imported, but any end-to-end check needs the Blender module,
which CI does not install — CI only verifies, via `scripts/readme-gate.sh`,
that every `shots.conf` entry has a committed README-embedded PNG within the
size budget. Re-rendering an unchanged design and confirming `git status` stays
clean is the practical regression test.
