"""Cross-axis wedge-mask body-count proof (#1047 / Copilot+CodeRabbit+Bugbot #1052).

Demo station 9 renders a large accepted span (L=120, arc_wall=1.6) that the
old fixed ``r_out+10`` wedge severs into disconnected arcs. ``check.sh``
CGAL-renders the demo but fails it only on ERROR/WARNING, never on a volume
count, so a regression that restored the fixed wedge would pass check.sh
while the station split. This test closes that with three renders:

- ``demo_mode="lib"``: full library pivot → fusecheck counts exactly 1 body;
- ``demo_mode="arcs_ok"``: beam-free frame+stage with the derived rb →
  exactly 2 bodies (frame and stage, intentionally disconnected so the
  wedge is isolated from beam bridging);
- ``demo_mode="arcs_broken"``: same beam-free geometry with the old
  ``r_out+10`` wedge → more than 2 bodies (each arc severed).

The arcs_ok / arcs_broken pair is the falsifiable negative control: without
matching beam-free geometry the broken mode would read ``bodies > 1`` even
with a correct wedge (frame≠stage), which is inert (Bugbot/CodeRabbit).

Which CI job exercises it: ``printcheck unit tests`` (``printcheck-tests``
in .github/workflows/ci.yml); the classifier forces that job on any
``lib/`` change (geo-infra). /preflight runs the same suite locally. Where
``openscad`` or ``xvfb-run`` is absent the tests SKIP (never error).

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
    """Full library pivot at the large span: one separable body."""
    stl = _render(tmp_path / "xafp-lib.stl", 'demo_mode="lib"')
    bodies, dropped = count_stl(str(stl), [])
    assert dropped == 0
    assert bodies == 1, (
        f"large-span cross-axis pivot split into {bodies} bodies — the "
        "wedge mask likely severed the rigid arcs")


@needs_openscad
def test_arcs_ok_is_exactly_two_bodies(tmp_path):
    """Beam-free frame+stage with the derived rb: exactly two bodies.
    Establishes the baseline the broken-wedge control must beat."""
    stl = _render(tmp_path / "xafp-arcs-ok.stl", 'demo_mode="arcs_ok"')
    bodies, _ = count_stl(str(stl), [])
    assert bodies == 2, (
        f"beam-free derived-wedge fixture has {bodies} bodies, want exactly 2 "
        "(frame + stage); a severed arc here means the 'ok' rb is wrong")


@needs_openscad
def test_arcs_broken_severs_past_two(tmp_path):
    """Negative control: same beam-free geometry, old r_out+10 wedge.
    Must climb above 2 — if it stays at 2 the control is not measuring the
    wedge defect (Bugbot/CodeRabbit on the inert no-beams-only control)."""
    stl = _render(tmp_path / "xafp-arcs-broken.stl", 'demo_mode="arcs_broken"')
    bodies, _ = count_stl(str(stl), [])
    assert bodies > 2, (
        f"old fixed r_out+10 wedge left {bodies} bodies (want > 2) — "
        "negative control is inert")
