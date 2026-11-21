"""LET series-row connectivity + J swap-invariance (#1048 / Copilot #1057).

Two regressions Copilot asked for as behavioral tests (not greps):

1. ``n_series=2`` must be ONE separable body (odd-row finger-parity flip
   unions facing fingers). Negative control: two unflipped harvest rows
   stacked at ``2·gap`` stay disconnected (bodies > 1).
2. ``let_joint_J(w, t) == let_joint_J(t, w)`` — the St-Venant approximation
   normalizes long/short sides so a swapped call cannot inflate J.

Which CI job exercises it: ``printcheck unit tests`` (``printcheck-tests``
in .github/workflows/ci.yml); the classifier forces that job on any
``lib/`` change (geo-infra). /preflight runs the same suite locally. Where
``openscad`` or ``xvfb-run`` is absent the tests SKIP (never error).

Honours OPENSCAD_BIN / OPENSCAD_ARGS like the repo scripts do, and sets
OPENSCADPATH itself.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from printcheck.fusecheck import count_stl

REPO = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "compliant_let_series.scad"
OPENSCAD = os.environ.get("OPENSCAD_BIN", "openscad")

needs_openscad = pytest.mark.skipif(
    shutil.which(OPENSCAD) is None or shutil.which("xvfb-run") is None,
    reason=f"needs {OPENSCAD} and xvfb-run on PATH (headless CGAL render); "
           "the printcheck-tests CI job installs both",
)


def _render(out: Path, *defines: str, scad: Path = FIXTURE) -> tuple[Path, str]:
    """Full CGAL render; returns (stl_path, combined stdout+stderr)."""
    env = dict(os.environ, OPENSCADPATH=f"{REPO / 'lib'}:{REPO}")
    cmd = ["xvfb-run", "-a", OPENSCAD,
           *os.environ.get("OPENSCAD_ARGS", "").split(),
           "--export-format", "binstl", "-o", str(out)]
    for d in defines:
        cmd += ["-D", d]
    cmd.append(str(scad))
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                         env=env, cwd=str(REPO))
    log = run.stdout + run.stderr
    assert run.returncode == 0, f"openscad failed ({run.returncode}):\n{log[-3000:]}"
    assert "ERROR" not in log and "WARNING" not in log, log[-3000:]
    assert out.is_file() and out.stat().st_size > 84, "no mesh exported"
    return out, log


@needs_openscad
def test_lib_two_row_is_one_body(tmp_path):
    """Library n_series=2: facing fingers union → exactly one body."""
    stl, _ = _render(tmp_path / "let-lib.stl", 'demo_mode="lib"')
    bodies, dropped = count_stl(str(stl), [])
    assert dropped == 0
    assert bodies == 1, (
        f"n_series=2 LET split into {bodies} bodies — odd-row finger parity "
        "flip likely failed to connect adjacent rows")


@needs_openscad
def test_unflipped_stack_is_disconnected(tmp_path):
    """Negative control: two unflipped harvest rows at 2·gap stay >1 body.
    Without this the one-body check is inert (any solid would pass)."""
    stl, _ = _render(tmp_path / "let-broken.stl", 'demo_mode="broken"')
    bodies, _ = count_stl(str(stl), [])
    assert bodies > 1, (
        f"unflipped two-row stack left {bodies} bodies (want > 1) — "
        "negative control is inert")


@needs_openscad
def test_J_swap_invariant(tmp_path):
    """let_joint_J(w,t) == let_joint_J(t,w); both paths echo the same number."""
    scad = tmp_path / "j_swap.scad"
    scad.write_text(
        "use <compliant.scad>\n"
        "echo(str(\"J_wt=\", let_joint_J(2.0, 1.2),\n"
        "         \" J_tw=\", let_joint_J(1.2, 2.0),\n"
        "         \" eq=\", let_joint_J(2.0, 1.2) == let_joint_J(1.2, 2.0)));\n"
        "cube(0.1);\n"
    )
    _, log = _render(tmp_path / "j_swap.stl", scad=scad)
    m = re.search(r'ECHO: "J_wt=([0-9.]+) J_tw=([0-9.]+) eq=(true|false)"', log)
    assert m, f"missing J swap echo:\n{log[-2000:]}"
    assert m.group(3) == "true", (
        f"let_joint_J not swap-invariant: J(2,1.2)={m.group(1)} "
        f"J(1.2,2)={m.group(2)}")
    # Production harvest value ~0.721 — swapped must land there too, not ~520.
    j = float(m.group(1))
    assert 0.5 < j < 1.0, f"J={j} outside the harvest envelope (~0.72)"
