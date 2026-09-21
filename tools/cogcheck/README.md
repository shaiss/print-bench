# cogcheck — will the assembled object stand up?

The repo can prove a part *prints*: watertight, sliceable, printcheck 100/100.
It could not prove an assembled object **stands**. The shape that motivated
this (issue #623, the `ovodyo` review): two heavy spheres cantilevered high on
thin stalks over a low airy truss. Every per-part gate is green — the truss
slices beautifully, the spheres are perfect shells — and the thing tips over
on the first desk bump, because nowhere in the pipeline does anyone compute
where the mass actually is.

```
$ ./scripts/cog-check.sh ovodyo
== ovodyo: cogcheck (CoG / tip-over stability) ==
  parts: 2 printed, 1 non-printed mass(es)
  ...
  assembled: 96.4 g  CoG=(0.00, 0.00, 62.81) mm
  ground z=0.00  footprint: 4-vertex hull, 1580.0 mm²
  CoG projection (21.30, 0.00): signed margin -11.30 mm (required 2.00 mm)
VERDICT: TIP-RISK — CoG ground projection is 11.30 mm OUTSIDE the support
  footprint (margin 2.00 mm) — the object tips
```

Stdlib only, no runtime dependencies — `gate.sh` runs it inside its own job
with nothing installed, the `tools/lineage` discipline.

## The check

A rigid body stands if its centre of gravity's ground projection falls inside
its support polygon. cogcheck measures each term from what the repo already
produces:

- **Per-part mass, from the mesh.** Each `part:` names an STL the gate
  rendered. A signed tetrahedron decomposition (every facet plus the origin)
  gives the part's volume and centroid exactly for a closed polyhedron — no
  tessellation-density error, because the decomposition is exact, not a
  Monte-Carlo or voxel approximation. Density comes from the manifest, so
  mass = density · volume.
- **Non-printed masses, from the manifest.** Brass stalks, steel ballast, a
  PCB: `mass:` entries with grams and a position. These are usually what tips
  a design — plastic is ~1.24 g/cm³ and brass is ~8.5, so the hardware
  dominates the CoG while being invisible to every mesh-based gate.
- **Assembly, from manifest transforms.** `translate:` / `rotate:` place each
  printed part in the standing frame (rotate first, then translate — the
  OpenSCAD convention, `rotate([x,y,z])` = Rz·Ry·Rx). Centroids transform
  affinely, so the assembled CoG is the mass-weighted mean.
- **Support footprint.** The convex hull of every mesh vertex within 0.05 mm
  of the assembly's lowest vertex — the contact geometry of the object
  standing on a table, including a tessellated curved bottom's whole lowest
  ring rather than one vertex of it. Point masses never contribute contact:
  hardware hangs on the printed structure, it is not a foot.
- **Verdict.** Signed distance from the CoG projection to the footprint
  boundary — positive inside, negative outside — compared against the
  manifest's `margin:`. A degenerate footprint (the hull collapses to a line
  or point: the object balances on an edge) is TIP-RISK by name, never a
  distance computed along a line.

## The manifest: `designs/<name>/ci.cog`

House key:value conf, `|`-separated fields, `#` comments. Opt-in by presence,
the `ci.plate` zero-blast-radius pattern: a design with no `ci.cog` is never
looked at.

```
# designs/ovodyo/ci.cog — densities g/cm³, masses g, positions mm
margin: 2.0
part: ovodyo-base.stl | density: 1.24
part: ovodyo-head.stl | density: 1.24 | translate: 0,0,86 | rotate: 0,0,15
mass: stalk | grams: 42 | at: 0,0,43
```

| Key | Fields | Notes |
|---|---|---|
| `margin` | one number, mm | Required CoG clearance inside the footprint. Default `0` (projection strictly inside is enough). Once, not twice. |
| `part` | `density` (required, g/cm³, > 0), `translate: x,y,z`, `rotate: rx,ry,z` | The STL name must be a **single basename** (no `/`, `\`, or `..`) resolved under `--stl-dir` / `build/`. `gate.sh` additionally requires that basename to be one it rendered for this design — a CoG computed on a stale mesh proves nothing. |
| `mass` | `grams` (required, > 0), `at: x,y,z` (required) | A non-printed mass with its position in the standing frame. |

Parsing fails loudly, `file:line` in the error: unknown keys and fields,
missing required fields, malformed or non-finite (`nan`/`inf`) numbers,
duplicate declarations (top-level keys, part/mass field names, part STL
basenames, mass labels), path-escaping STL names, a manifest with no `part:`
at all. There is deliberately **no default density** — a verdict silently
assuming PLA for a brass-stalked lamp would be worse than no verdict.

## Exit codes and the gate

Exit codes carry the verdict so wiring never parses prose:

- `0` — STABLE
- `3` — TIP-RISK
- `1` — broken input (unreadable STL, malformed manifest, open/inverted mesh)
- `2` — usage

In human mode the last stdout line is always `VERDICT: <STABLE|TIP-RISK> — <detail>`;
`--json` emits **only** the full result JSON (per-part volumes, masses, CoGs,
contact points, footprint hull, margins) so tooling can `json.loads` stdout —
no trailing VERDICT line.

`scripts/cog-check.sh <name>` re-emits the verdict as gate line shapes:

```
ok    cogcheck ovodyo: CoG ground projection clears the support footprint
warn  cogcheck ovodyo: TIP RISK — CoG ground projection is 11.30 mm OUTSIDE...
FAIL  cogcheck ovodyo: ci.cog:2: no density — ...
```

TIP-RISK is a **WARN, not a gate failure** — the `fusecheck` precedent: a tip
risk is a design call to look at (maybe the margin is pessimistic, maybe the
desk is fine), and promoting it to blocking is a separate human decision. A
broken manifest or unmeasurable mesh is a hard FAIL: a check that cannot run
is not a check. `gate.sh` additionally fails a manifest naming an STL it did
not render for this design — that containment needs the gate's rendered list,
so it lives there.

`scripts/cog-check.sh --selftest` (run by `check.sh`) proves the verdict
discriminates both ways on synthetic fixtures: a stable configuration passes,
an out-of-footprint one is flagged, and a malformed manifest is refused —
issue #37's rule that a check which cannot fail is worthless.

## What it deliberately does not do

- **No dynamics.** It computes the static stability criterion. It does not
  model a bump impulse, a carrying handle's grip, or how far you can tilt
  before no return — the margin is the tunable proxy for all of that.
- **No inverted-pendulum exceptions.** A floor lamp is stable with a tiny
  footprint because it is bolted down; this check will WARN on it. That is
  the advisory tier working as designed — a human reads the WARN and decides.
- **No CoG-under-table cases.** The check is tipping on a ground plane
  (`z` = the assembly's lowest vertex). Wall-mounts and hanging objects have
  no support polygon to be inside.

## Layout

```
src/cogcheck/
  stl.py       ASCII/binary STL reader (normals read, then discarded)
  mesh.py      signed-tetrahedron mass properties, transforms, ground contact
  conf.py      the ci.cog manifest parser (fail-loud, file:line)
  hull.py      2-D convex hull + inside/distance/degeneracy predicates
  verdict.py   assembly, footprint, margin, the verdict and its detail
  cli.py       report, VERDICT line, --json, exit codes
tests/         pytest suite, every rule with a positive and a negative control
```

Install: `pip install -e 'tools/cogcheck[test]'` for the pytest extra; the
tool itself needs none — `scripts/cog-check.sh` imports it straight from
`src/` (the `lineage.sh` wrapper pattern), so `gate.sh` runs it uninstalled.

Run tests: `python -m pytest tools/cogcheck/tests -q` — no install required,
`tests/conftest.py` puts `src/` on the path.
