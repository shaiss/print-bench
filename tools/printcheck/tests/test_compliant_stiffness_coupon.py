"""Stiffness-coupon goldens + failability (#1049 stage 4).

Behavioral checks (not greps):

1. Harvest-site predicted K / f_s / u_tr still match the recorded goldens
   the coupon protocol compares measurements against. A formula drift fails.
2. Negative control: a deliberately wrong golden MUST abort the render —
   without this, the assert harness is inert (issue #37).

Which CI job: ``printcheck unit tests`` (``printcheck-tests`` in ci.yml);
classifier forces that job on any ``lib/`` change. /preflight runs the same
suite. Where openscad / xvfb-run is absent the tests SKIP.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from printcheck.analyzer import load_mesh
from printcheck.fusecheck import count_stl

REPO = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "compliant_stiffness_goldens.scad"
BODY_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "compliant_coupon_bodies.scad"
PLATE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "compliant_coupon_plate.scad"
OPENSCAD = os.environ.get("OPENSCAD_BIN", "openscad")

# Printable units must fit a 220×220 mm bed (256 mm P2S class with margin).
COUPON_BED_MM = 220

needs_openscad = pytest.mark.skipif(
    shutil.which(OPENSCAD) is None or shutil.which("xvfb-run") is None,
    reason=f"needs {OPENSCAD} and xvfb-run on PATH (headless CGAL render); "
           "the printcheck-tests CI job installs both",
)


def _run(out: Path, *defines: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, OPENSCADPATH=f"{REPO / 'lib'}:{REPO}")
    cmd = ["xvfb-run", "-a", OPENSCAD,
           *os.environ.get("OPENSCAD_ARGS", "").split(),
           "--export-format", "binstl", "-o", str(out)]
    for d in defines:
        cmd += ["-D", d]
    cmd.append(str(FIXTURE))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          env=env, cwd=str(REPO))


@needs_openscad
def test_harvest_goldens_still_hold(tmp_path):
    """Production K / f_s / u_tr match the coupon protocol's recorded goldens."""
    out = tmp_path / "goldens.stl"
    run = _run(out, 'demo_mode="ok"')
    log = run.stdout + run.stderr
    assert run.returncode == 0, f"golden asserts aborted:\n{log[-3000:]}"
    assert "ERROR" not in log and "WARNING" not in log, log[-3000:]
    assert out.is_file() and out.stat().st_size > 84
    m = re.search(
        r"GOLDEN_OK arch_fs=([0-9.]+) slfp_K=([0-9.]+) "
        r"xafp_K=([0-9.]+) let_K=([0-9.]+)",
        log,
    )
    assert m, f"missing GOLDEN_OK echo:\n{log[-2000:]}"
    arch_fs, slfp_k, xafp_k, let_k = map(float, m.groups())
    assert abs(arch_fs - 3.0) < 1e-6, f"arch f_s={arch_fs}"
    assert abs(slfp_k - 208.333333333) < 1e-3, f"SLFP K={slfp_k}"
    assert abs(xafp_k - 195.047619048) < 1e-3, f"XAFP K={xafp_k}"
    assert abs(let_k - 110.388081894) < 1e-3, f"LET K={let_k}"


@needs_openscad
def test_wrong_golden_aborts(tmp_path):
    """Negative control: a wrong K golden must fail the render.

    Without this the golden assert is unfalsifiable — any solid would "pass".
    """
    out = tmp_path / "bad.stl"
    run = _run(out, 'demo_mode="bad_k"')
    log = run.stdout + run.stderr
    assert run.returncode != 0, (
        "wrong golden rendered successfully — assert harness is inert:\n"
        f"{log[-2000:]}"
    )
    assert "deliberate wrong golden" in log or "Assertion" in log or "ERROR" in log, (
        f"expected assertion failure, got:\n{log[-2000:]}"
    )


def _render_body(out: Path, mode: str) -> Path:
    env = dict(os.environ, OPENSCADPATH=f"{REPO / 'lib'}:{REPO}")
    cmd = ["xvfb-run", "-a", OPENSCAD,
           *os.environ.get("OPENSCAD_ARGS", "").split(),
           "--export-format", "binstl", "-o", str(out),
           "-D", f'demo_mode="{mode}"', str(BODY_FIXTURE)]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                         env=env, cwd=str(REPO))
    log = run.stdout + run.stderr
    assert run.returncode == 0, f"{mode} render failed:\n{log[-3000:]}"
    assert "ERROR" not in log and "WARNING" not in log, log[-3000:]
    assert out.is_file() and out.stat().st_size > 84
    return out


@pytest.mark.parametrize("mode", ["arch", "slfp", "xafp", "let"])
@needs_openscad
def test_production_twin_is_one_body(mode, tmp_path):
    """Each production twin is one watertight body (issue #1049 Done-when)."""
    stl = _render_body(tmp_path / f"{mode}.stl", mode)
    bodies, dropped = count_stl(str(stl), [])
    assert dropped == 0
    mesh = load_mesh(str(stl))
    assert mesh.is_watertight, f"{mode} production twin is not watertight"
    assert bodies == 1, (
        f"{mode} production twin split into {bodies} bodies — "
        "label glyphs must be debossed into the grip, not free solids"
    )


@needs_openscad
def test_xafp_label_removes_material(tmp_path):
    """Cross-axis label cutter sits in the +X tab and actually debosses it.

    Without this, a cutter translated onto the empty Y axis still yields one
    watertight body — the body-count test cannot see a missed label.
    """
    labeled = _render_body(tmp_path / "xafp_labeled.stl", "xafp")
    unlabeled = _render_body(tmp_path / "xafp_nolabel.stl", "xafp_nolabel")
    v_labeled = float(load_mesh(str(labeled)).volume)
    v_unlabeled = float(load_mesh(str(unlabeled)).volume)
    assert v_labeled < v_unlabeled, (
        f"XAFP label did not remove material: labeled={v_labeled} "
        f"unlabeled={v_unlabeled}"
    )


def _render_plate(out: Path, mode: str, *defines: str) -> Path:
    env = dict(os.environ, OPENSCADPATH=f"{REPO / 'lib'}:{REPO}")
    cmd = ["xvfb-run", "-a", OPENSCAD,
           *os.environ.get("OPENSCAD_ARGS", "").split(),
           "--export-format", "binstl", "-o", str(out),
           "-D", f'demo_mode="{mode}"']
    for d in defines:
        cmd += ["-D", d]
    cmd.append(str(PLATE_FIXTURE))
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                         env=env, cwd=str(REPO))
    log = run.stdout + run.stderr
    assert run.returncode == 0, f"{mode} plate render failed:\n{log[-3000:]}"
    assert "ERROR" not in log, log[-3000:]
    assert out.is_file() and out.stat().st_size > 84
    return out


def _xy_extents(stl: Path) -> tuple[float, float]:
    mesh = load_mesh(str(stl))
    lo, hi = mesh.bounds
    return float(hi[0] - lo[0]), float(hi[1] - lo[1])


@pytest.mark.parametrize("mode", ["plate0", "plate1", "plate2"])
@needs_openscad
def test_print_plate_fits_bed(mode, tmp_path):
    """Each coupon_plate index fits a 220×220 mm bed (measured AABB).

    The pre-fix single plate was ~420×302 mm — beyond 256 mm and 220 mm.
    A grep on constants cannot catch a packing regression; render + bounds do.
    """
    stl = _render_plate(tmp_path / f"{mode}.stl", mode)
    dx, dy = _xy_extents(stl)
    assert dx <= COUPON_BED_MM and dy <= COUPON_BED_MM, (
        f"{mode} AABB {dx:.1f}×{dy:.1f} mm exceeds {COUPON_BED_MM} mm bed"
    )


@needs_openscad
def test_print_plate_fits_bed_with_extended_xafp_ladder(tmp_path):
    """Extended XAFP ladder still fits on its own print plate."""
    stl = _render_plate(
        tmp_path / "plate1_ext.stl",
        "plate1",
        "coupon_ts_xafp=[0.6,0.8,1.0,1.2,1.4]",
    )
    dx, dy = _xy_extents(stl)
    assert dx <= COUPON_BED_MM and dy <= COUPON_BED_MM, (
        f"extended plate1 AABB {dx:.1f}×{dy:.1f} mm exceeds "
        f"{COUPON_BED_MM} mm bed"
    )


def _expected_specimen_count(n_arch=3, n_slfp=3, n_xafp=3, n_let=3) -> int:
    # Each strip: ladder cells + PETG twin + PLA twin.
    return (n_arch + 2) + (n_slfp + 2) + (n_xafp + 2) + (n_let + 2)


@needs_openscad
def test_full_plate_specimens_do_not_intersect(tmp_path):
    """Default full plate: every specimen is a separate body (no overlaps)."""
    stl = _render_plate(tmp_path / "all.stl", "all")
    bodies, dropped = count_stl(str(stl), [])
    assert dropped == 0
    want = _expected_specimen_count()
    assert bodies == want, (
        f"default full plate has {bodies} bodies, want {want} — "
        "overlapping specimens fuse and drop the count"
    )


@needs_openscad
def test_extended_xafp_ladder_does_not_intersect_let(tmp_path):
    """Extended XAFP ladder: LET origin tracks row count; no fuse with LET.

    Regression for the fixed LET y=280 layout: with
    coupon_ts_xafp=[0.6,0.8,1.0,1.2,1.4] the PLA twin sat on row 3 and
    shared volume with the first LET grip.
    """
    stl = _render_plate(
        tmp_path / "all_ext.stl",
        "all",
        "coupon_ts_xafp=[0.6,0.8,1.0,1.2,1.4]",
    )
    bodies, dropped = count_stl(str(stl), [])
    assert dropped == 0
    want = _expected_specimen_count(n_xafp=5)
    assert bodies == want, (
        f"extended-XAFP full plate has {bodies} bodies, want {want} — "
        "XAFP/LET overlap fuses specimens"
    )


@needs_openscad
def test_overlap_control_fuses_bodies(tmp_path):
    """Negative control: deliberate overlap must drop the body count.

    Without this, a always-1 or always-N counter would make the
    non-intersection checks unfalsifiable (issue #37).
    """
    stl = _render_plate(tmp_path / "overlap.stl", "overlap_control")
    bodies, dropped = count_stl(str(stl), [])
    assert dropped == 0
    assert bodies == 1, (
        f"overlap control produced {bodies} bodies — expected a single "
        "fused body so the intersection check can still fire"
    )
