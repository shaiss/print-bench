"""Cross-axis wedge-mask body-count proof (#1047 / Copilot+CodeRabbit #1052).

Demo station 9 renders a large accepted span (L=120, arc_wall=1.6) that the
old fixed ``r_out+10`` wedge severs into disconnected arcs. ``check.sh``
CGAL-renders the demo but fails it only on ERROR/WARNING, never on a volume
count, so a regression that restored the fixed wedge would pass check.sh
while the station split. This test closes that:

- render the fixture via the library (derived rb) and assert fusecheck
  counts exactly 1 body;
- render it with ``-D demo_fixed_wedge=true`` (the fixture's inline copy of
  the old ``r_out+10`` wedge, frame+stage only) and assert MORE than 1 —
  the negative control proving the count is measuring the wedge defect.

Which CI job exercises it: ``printcheck unit tests`` (``printcheck-tests``
in .github/workflows/ci.yml); the classifier forces that job on any
``lib/`` change (geo-infra). /preflight runs the same suite locally. Where
``openscad`` or ``xvfb-run`` is absent the two tests SKIP (never error).

Honours OPENSCAD_BIN / OPENSCAD_ARGS like the repo scripts do, and sets
OPENSCADPATH itself.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from printcheck.fusecheck import count_stl

REPO = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "compliant_xafp_wedge.scad"
OPENSCAD = os.environ.get("OPENSCAD_BIN", "openscad")

needs_openscad = pytest.mark.skipif(
    shutil.which(OPENSCAD) is None or shutil.which("xvfb-run") is None,
    reason=f"needs {OPENSCAD} and xvfb-run on PATH (headless CGAL render); "
           "the printcheck-tests CI job installs both",
)


def _render(out: Path, *defines: str) -> Path:
    """Full CGAL render of the fixture to a binary STL."""
    env = dict(os.environ, OPENSCADPATH=f"{REPO / 'lib'}:{REPO}")
    cmd = ["xvfb-run", "-a", OPENSCAD,
           *os.environ.get("OPENSCAD_ARGS", "").split(),
           "--export-format", "binstl", "-o", str(out)]
    for d in defines:
        cmd += ["-D", d]
    cmd.append(str(FIXTURE))
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                         env=env, cwd=str(REPO))
    log = run.stdout + run.stderr
    assert run.returncode == 0, f"openscad failed ({run.returncode}):\n{log[-3000:]}"
    assert "ERROR" not in log and "WARNING" not in log, log[-3000:]
    assert out.is_file() and out.stat().st_size > 84, "no mesh exported"
    return out


@needs_openscad
def test_lib_wedge_keeps_one_body(tmp_path):
    """Derived rb clears the bore: the large-span pivot is one separable body."""
    stl = _render(tmp_path / "xafp-fixed.stl")
    bodies, dropped = count_stl(str(stl), [])
    assert dropped == 0
    assert bodies == 1, (
        f"large-span cross-axis pivot split into {bodies} bodies — the "
        "wedge mask likely severed the rigid arcs")


@needs_openscad
def test_old_fixed_wedge_severs_arcs(tmp_path):
    """Negative control: the pre-fix ``r_out+10`` wedge severs frame from
    stage (and each arc from itself), so the body count must climb above 1.
    If this ever reads 1 the test above is not measuring the wedge defect."""
    stl = _render(tmp_path / "xafp-broken.stl", "demo_fixed_wedge=true")
    bodies, _ = count_stl(str(stl), [])
    assert bodies > 1, (
        "the old fixed r_out+10 wedge freed no arc — negative control is inert")
