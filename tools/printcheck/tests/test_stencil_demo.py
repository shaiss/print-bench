"""The stencil-glyphs counter-tether proof, run as a test (#612, #618 review).

lib/stencil-glyphs-demo.scad cuts every digit THROUGH a plate; each counter
(the hole in 0, 4, 6, 8, 9) is an island of plate held only by two bridge
tethers, so the plate is ONE body exactly when every tether is real.
check.sh CGAL-renders that demo but fails it only on ERROR/WARNING, never on
the body count, so a regression that removed or misplaced the bridge bars
would pass check.sh while every counter came loose. This test closes that:

- render the demo as committed and assert fusecheck counts exactly 1 body;
- render it with ``-D demo_bridged=false`` (the demo's own parameter, which
  strips the bars from the through-cuts only) and assert MORE than 1 — the
  negative control proving the count is measuring the tethers.

Which CI job exercises it: ``printcheck unit tests`` (``printcheck-tests`` in
.github/workflows/ci.yml), which installs OpenSCAD 2021.01 + xvfb through the
same cached apt step scad-check uses; the classifier forces that job on any
``lib/`` change (geo-infra), so a PR that could move a tether re-proves it.
/preflight runs the same suite locally. Where ``openscad`` or ``xvfb-run`` is
absent the two tests SKIP (never error), which is why the CI step matters.

Honours OPENSCAD_BIN / OPENSCAD_ARGS like the repo scripts do, and sets
OPENSCADPATH itself: without it ``use <stencil-glyphs.scad>`` resolves to
nothing, OpenSCAD only WARNs, and the plate renders uncut — one body, a
false pass — so a WARNING in the render log fails the test outright.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from printcheck.fusecheck import count_stl

REPO = Path(__file__).resolve().parents[3]
DEMO = REPO / "lib" / "stencil-glyphs-demo.scad"
OPENSCAD = os.environ.get("OPENSCAD_BIN", "openscad")

needs_openscad = pytest.mark.skipif(
    shutil.which(OPENSCAD) is None or shutil.which("xvfb-run") is None,
    reason=f"needs {OPENSCAD} and xvfb-run on PATH (headless CGAL render); "
           "the printcheck-tests CI job installs both",
)


def _render_demo(out: Path, *defines: str) -> Path:
    """Full CGAL render of the demo to a binary STL, exactly as check.sh does."""
    env = dict(os.environ, OPENSCADPATH=f"{REPO / 'lib'}:{REPO}")
    cmd = ["xvfb-run", "-a", OPENSCAD,
           *os.environ.get("OPENSCAD_ARGS", "").split(),
           "--export-format", "binstl", "-o", str(out)]
    for d in defines:
        cmd += ["-D", d]
    cmd.append(str(DEMO))
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                         env=env, cwd=str(REPO))
    log = run.stdout + run.stderr
    assert run.returncode == 0, f"openscad failed ({run.returncode}):\n{log[-3000:]}"
    # check.sh's own bar for a demo: a WARNING is a regression, and here the
    # specific one to fear is an unresolved include rendering the plate uncut.
    assert "ERROR" not in log and "WARNING" not in log, log[-3000:]
    assert out.is_file() and out.stat().st_size > 84, "no mesh exported"
    return out


@needs_openscad
def test_demo_plate_is_one_body(tmp_path):
    """Every counter tethered: the whole demo (cut plate + raised zone, which
    is fused to it by construction) is exactly one separable body."""
    stl = _render_demo(tmp_path / "demo-bridged.stl")
    bodies, dropped = count_stl(str(stl), [])
    assert dropped == 0
    assert bodies == 1, (
        f"the demo plate split into {bodies} bodies — a counter island came "
        "loose, so a bridge bar is missing or misplaced")


@needs_openscad
def test_demo_without_bridges_frees_the_counters(tmp_path):
    """The negative control: with the through-cuts' bars stripped, every
    counter is a freed island and the count must climb above 1 (the ten
    counters in "0123456789" + "12 05 10 00" make it 11). If this ever reads 1
    the test above is not measuring the tethers."""
    stl = _render_demo(tmp_path / "demo-unbridged.stl", "demo_bridged=false")
    bodies, _ = count_stl(str(stl), [])
    assert bodies > 1, "stripping the bridge bars freed no counter"
