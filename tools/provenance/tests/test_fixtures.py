"""The committed fixtures: prose-free, self-consistent, and reproducible from the raw capture.

``test_fixture_regeneration_is_byte_identical`` runs only where the
uncommitted raw capture exists (``PROVENANCE_RAW_DIR`` and
``PROVENANCE_SNAPSHOT_DIR`` set — a builder's sandbox), never in CI.
"""

from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys

import pytest

from conftest import FIXTURES, REPO, receipt_paths

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


@pytest.mark.skipif(not (os.environ.get("PROVENANCE_RAW_DIR") and os.environ.get("PROVENANCE_SNAPSHOT_DIR")),
                    reason="needs the uncommitted raw capture (dev sandbox only)")
def test_fixture_regeneration_is_byte_identical():
    env = dict(os.environ, PYTHONPATH=str(REPO / "tools" / "provenance" / "src"))
    rc = subprocess.run([sys.executable, str(FIXTURES.parent / "dev" / "build_fixtures.py"),
                         "--raw", os.environ["PROVENANCE_RAW_DIR"], "--snapshot", os.environ["PROVENANCE_SNAPSHOT_DIR"],
                         "--out", str(FIXTURES), "--check"], env=env).returncode
    assert rc == 0
