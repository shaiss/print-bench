"""The CLI and the shell wrapper: build writes a clean set whole or not at
all, --verify catches a stale sheet, and the selftest itself fails whenever
one of its negative controls stops firing (the meta-control: the selftest
is only worth running if it can go red)."""

from __future__ import annotations

import shutil
import subprocess

import pytest
from conftest import BASE, FIXTURES, REPO, with_lines

from concept_preview import selftest
from concept_preview.cli import main

SHEETS = ["concept-cutaway.svg", "concept-exploded.svg", "concept-exterior.svg", "concept-section.svg"]


def write_spec(tmp_path, text: str):
    p = tmp_path / "preview-spec.conf"
    p.write_text(text, encoding="utf-8")
    return p


def test_build_writes_four_sheets_that_recheck_clean(tmp_path, capsys):
    out = tmp_path / "previews"
    assert main(["build", str(write_spec(tmp_path, BASE)), "--out", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == SHEETS
    assert main(["check", *(str(out / n) for n in SHEETS)]) == 0
    assert "wrote 4 checked sheets" in capsys.readouterr().out


def test_build_refuses_a_bad_spec_with_exit_2_and_writes_nothing(tmp_path, capsys):
    out = tmp_path / "previews"
    assert main(["build", str(write_spec(tmp_path, with_lines("gear: exterior | at=1,1"))), "--out", str(out)]) == 2
    assert not out.exists()
    assert "preview-spec.conf:" in capsys.readouterr().out


def test_build_with_a_failing_check_exits_1_and_writes_nothing(tmp_path, capsys):
    out = tmp_path / "previews"
    spec = write_spec(tmp_path, with_lines("hex: exterior | at=600,300 | size=60x40"))
    assert main(["build", str(spec), "--out", str(out)]) == 1
    assert not out.exists()
    printed = capsys.readouterr().out
    assert "FAIL  bounds:" in printed and "nothing written" in printed


def test_build_of_a_missing_spec_is_exit_2(tmp_path):
    assert main(["build", str(tmp_path / "absent.conf"), "--out", str(tmp_path)]) == 2


def test_verify_passes_fresh_and_fails_stale_or_missing(tmp_path, capsys):
    spec, out = write_spec(tmp_path, BASE), tmp_path / "previews"
    assert main(["build", str(spec), "--out", str(out)]) == 0
    assert main(["build", str(spec), "--out", str(out), "--verify"]) == 0
    (out / "concept-section.svg").write_text("<svg/>", encoding="utf-8")
    assert main(["build", str(spec), "--out", str(out), "--verify"]) == 1
    assert "concept-section.svg is stale" in capsys.readouterr().out
    (out / "concept-section.svg").unlink()
    assert main(["build", str(spec), "--out", str(out), "--verify"]) == 1
    assert "is missing" in capsys.readouterr().out


def test_verify_never_writes(tmp_path):
    out = tmp_path / "previews"
    assert main(["build", str(write_spec(tmp_path, BASE)), "--out", str(out), "--verify"]) == 1
    assert not out.exists()


def test_check_flags_a_bad_sheet(tmp_path):
    bad = tmp_path / "bad.svg"
    bad.write_text("<svg", encoding="utf-8")
    assert main(["check", str(bad)]) == 1


def test_vocab(capsys):
    assert main(["vocab"]) == 0
    assert "leader: <sheet> | k=v" in capsys.readouterr().out


# ── the selftest, and the selftest's own negative controls ────────────────
def test_shipped_selftest_passes():
    lines = []
    assert selftest.run(FIXTURES, lines.append) == 0
    assert sum(ln.startswith("ok   [neg-") for ln in lines) == 3


def _fixture_copy(tmp_path):
    dst = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, dst)
    return dst


def test_selftest_fails_when_a_control_stops_firing(tmp_path):
    fx = _fixture_copy(tmp_path)
    (fx / "neg-overlapping-labels.conf").write_text("# expect: collision\n# neutered\n", encoding="utf-8")
    lines = []
    assert selftest.run(fx, lines.append) == 1
    assert any("negative control did not fire" in ln for ln in lines)


def test_selftest_fails_when_a_control_fires_the_wrong_check(tmp_path):
    fx = _fixture_copy(tmp_path)
    (fx / "neg-overlapping-labels.conf").write_text(
        "# expect: collision\nhex: exterior | at=600,300 | size=60x40\n", encoding="utf-8")
    lines = []
    assert selftest.run(fx, lines.append) == 1
    assert any("fired the wrong check" in ln for ln in lines)


@pytest.mark.parametrize("control", ["neg-malformed.conf", "neg-out-of-bounds.conf",
                                     "neg-overlapping-labels.conf"])
def test_selftest_fails_when_a_control_is_deleted(tmp_path, control):
    fx = _fixture_copy(tmp_path)
    (fx / control).unlink()
    lines = []
    assert selftest.run(fx, lines.append) == 1
    assert any(ln.startswith("FAIL [coverage]") for ln in lines)


def test_selftest_fails_when_the_base_fixture_is_broken(tmp_path):
    fx = _fixture_copy(tmp_path)
    (fx / "valid.conf").write_text(with_lines("leader: section | at=154,340 | to=220,372 | text=x x x x"),
                                   encoding="utf-8")
    lines = []
    assert selftest.run(fx, lines.append) == 1
    assert lines[0].startswith("FAIL [valid]")


def test_selftest_requires_the_expect_header(tmp_path):
    fx = _fixture_copy(tmp_path)
    (fx / "neg-extra.conf").write_text("hex: exterior | at=1,1\n", encoding="utf-8")
    lines = []
    assert selftest.run(fx, lines.append) == 1
    assert any("first line must be" in ln for ln in lines)


# ── the shell wrapper (what check.sh and a design session actually run) ───
def _sh(*args):
    return subprocess.run([str(REPO / "scripts" / "concept-preview.sh"), *args],
                          capture_output=True, text=True, cwd=REPO, check=False)


def test_wrapper_selftest_and_vocab():
    r = _sh("--selftest")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "3 negative controls passed" in r.stdout
    assert _sh("--vocab").returncode == 0


@pytest.mark.parametrize("args", [(), ("--bogus",), ("../etc",), ("no-such-design",),
                                  ("--check",), ("a", "b")])
def test_wrapper_refuses_bad_invocations_with_exit_2(args):
    assert _sh(*args).returncode == 2
