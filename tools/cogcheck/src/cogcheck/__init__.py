"""Cogcheck: prove an assembled object stands up, not just that it prints.

The repo's gates prove a part prints (printcheck) and that a multi-part
deliverable imports as its parts (plate.sh). None of them proves the finished
object STANDS: two heavy spheres cantilevered high on thin stalks over a low
airy truss slices and scores 100/100 and still tips over on a desk bump. This
package is that missing check (issue #623):

- mesh-derived CoG — volume-weighted tetrahedron decomposition of each gated
  STL, exact for any closed polyhedron;
- a per-part density manifest (``designs/<name>/ci.cog``, house ``key: value``
  conf) carrying what an STL cannot infer — per-part material densities, the
  non-printed masses (brass stalks, ballast fill, PCB) with positions, and the
  transforms that place each printed part in the assembled standing frame;
- support footprint — the convex hull of the standing-orientation contact
  geometry;
- a verdict — the assembled CoG's ground projection must fall inside the
  footprint, clearing its boundary by a tunable stability margin.

Stdlib-only on purpose (see pyproject.toml): the check runs inside gate.sh
wherever the gate runs. The verdict lands as an ADVISORY WARN there — a tip
risk is a design call to look at, not a gate failure; promoting it to blocking
is a separate human decision (the fusecheck precedent).
"""

from cogcheck.conf import Manifest, ManifestError, parse
from cogcheck.mesh import MeshError
from cogcheck.verdict import CheckResult, assemble

__all__ = [
    "Manifest",
    "ManifestError",
    "MeshError",
    "parse",
    "assemble",
    "CheckResult",
]
