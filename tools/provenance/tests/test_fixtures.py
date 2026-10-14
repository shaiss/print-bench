"""The committed fixtures: prose-free, self-consistent, and reproducible from the raw capture.

``test_fixture_regeneration_is_byte_identical`` runs only where the
uncommitted raw capture exists (``PROVENANCE_RAW_DIR`` and
``PROVENANCE_SNAPSHOT_DIR`` set — a builder's sandbox), never in CI.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import subprocess
import sys

import pytest

from conftest import FIXTURES, REPO, main_history, receipt_paths

PROSE_KEYS = {"body", "message"}


def _walk(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield f"{path}.{k}", k, v
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def _docs():
    for p in sorted(FIXTURES.rglob("*.json.gz")):
        if "snapshot-mini" in p.parts or "codebasis" in p.parts:
            continue
        yield p, json.loads(gzip.decompress(p.read_bytes()))


def test_no_prose_field_anywhere():
    for p, doc in _docs():
        for path, key, value in _walk(doc):
            if key in PROSE_KEYS:
                assert isinstance(value, dict) and value.get("digest", "").endswith("digest@1"), f"{p}: {path}"


def test_receipt_paths_agree_with_their_runs():
    assert receipt_paths(), "no fixture receipts"
    for p in receipt_paths():
        doc = json.loads(gzip.decompress(p.read_bytes()))
        run = doc["run"]
        y, m, d = run["created_at"][:10].split("-")
        assert p.relative_to(FIXTURES).as_posix() == f"receipts/{y}/{m}/{d}/{run['id']}.a{run['run_attempt']}.json.gz"


def test_main_history_carries_what_the_fake_git_needs():
    """Every main row has sha, parents, committer date + e-mail and subject (merge method, main subject and the
    direct-commit rule read them); main's root is the 2026-07-31 bootstrap commit."""
    rows = main_history()["commits"]
    assert len(rows) > 800
    for row in rows:
        assert set(row) == {"committed_at", "committer_email", "parents", "sha", "subject", "subject_pr"}
        assert re.fullmatch(r"[0-9a-f]{40}", row["sha"]) and isinstance(row["subject"], str)
    by_sha = {r["sha"]: r for r in rows}
    merge = by_sha["521d092813b78a88bd9a74b1052cfef1f230d86b"]
    assert merge["subject"].endswith("(#636)") and merge["subject_pr"] == 636
    assert merge["committer_email"] == "noreply@github.com"
    pr196 = by_sha["43030db97b7ec0a17c70c1727288efed7130e4d7"]
    assert pr196["subject"].startswith("Merge PR #196:") and pr196["subject_pr"] is None and len(pr196["parents"]) == 2


def test_design_files_are_main_copies():
    """design-files/<d>/ holds only PM.md / NOTES.md / team.conf of the three golden designs."""
    found = sorted(p.relative_to(FIXTURES / "design-files").as_posix()
                   for p in (FIXTURES / "design-files").rglob("*") if p.is_file())
    assert found == ["calibration-cube/NOTES.md", "calibration-cube/PM.md", "calibration-cube/team.conf",
                     "nuggs-vent-cap/NOTES.md", "sbc-case/NOTES.md", "sbc-case/PM.md", "sbc-case/team.conf"]


def _has_fixture_main() -> bool:
    try:
        return subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", "521d092813b78a88bd9a74b1052cfef1f230d86b"],
                              capture_output=True).returncode == 0
    except OSError:
        return False


@pytest.mark.skipif(not _has_fixture_main(), reason="the checkout does not hold 521d092 (shallow clone)")
def test_design_files_match_main_521d092():
    """Each copy is byte-identical to the file at #636's merge (only checkable with full history)."""
    for p in sorted((FIXTURES / "design-files").rglob("*")):
        if p.is_file():
            rel = p.relative_to(FIXTURES / "design-files").as_posix()
            res = subprocess.run(["git", "-C", str(REPO), "show", f"521d092813b78a88bd9a74b1052cfef1f230d86b:designs/{rel}"],
                                 capture_output=True, check=True)
            assert res.stdout == p.read_bytes(), rel


def test_acceptance_fixture_shape():
    """tests/fixtures/acceptance.json: the re-baselined NVC-12 tuple with its derivation and the golden it replaces."""
    spec = json.loads((FIXTURES / "acceptance.json").read_text(encoding="utf-8"))
    nvc12 = spec["NVC-12"]
    assert set(nvc12) == {"derivation", "expected", "golden", "keys", "pr", "same_source_as_golden_third"}
    assert len(nvc12["keys"]) == len(nvc12["expected"]) == len(nvc12["golden"]) == 4
    assert all(isinstance(line, str) and line for line in nvc12["derivation"])


@pytest.mark.skipif(not (os.environ.get("PROVENANCE_RAW_DIR") and os.environ.get("PROVENANCE_SNAPSHOT_DIR")),
                    reason="needs the uncommitted raw capture (dev sandbox only)")
def test_fixture_regeneration_is_byte_identical():
    env = dict(os.environ, PYTHONPATH=str(REPO / "tools" / "provenance" / "src"))
    rc = subprocess.run([sys.executable, str(FIXTURES.parent / "dev" / "build_fixtures.py"),
                         "--raw", os.environ["PROVENANCE_RAW_DIR"], "--snapshot", os.environ["PROVENANCE_SNAPSHOT_DIR"],
                         "--out", str(FIXTURES), "--check"], env=env).returncode
    assert rc == 0
