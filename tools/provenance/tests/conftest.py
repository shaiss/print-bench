"""Shared paths and loaders for the provenance suite.

Fixture sources (all committed, all prose-free):

* ``tools/provenance/tests/fixtures/`` — produced by
  ``tests/dev/build_fixtures.py`` from the scaffold's GET-only raw capture
  and the #843 snapshot: ``raw/{pr,brief,release}/`` (raw@1),
  ``receipts/Y/M/D/<id>.a<k>.json.gz`` (receipt@1), ``codebasis/`` (registry
  + workflow blobs at the fixture runs' code bases), ``main_history.json.gz``,
  ``membership/pr_files.json.gz``, ``snapshot-mini/`` (#843 format).
* ``audits/provenance-2026-10/fixtures/`` — the audit's golden who/how
  timelines (``golden/*.golden.json.gz``, ``*.full.json.gz``, the
  ``timeline-event.schema.json.gz``), the membership labels
  (``membership/membership.csv``, ``refined_membership.json``) and
  ``bin/check_acceptance.py`` (the 21 checks ``test_acceptance.py`` ports).

``sys.path`` gains ``tools/provenance/src`` and ``tools/model-registry/src``
(the serving join reuses the registry's own parser).
"""

from __future__ import annotations

import csv
import gzip
import inspect
import json
import pathlib
import sys

import pytest

TESTS = pathlib.Path(__file__).resolve().parent
TOOL = TESTS.parent
REPO = TOOL.parents[1]
sys.path.insert(0, str(TOOL / "src"))
sys.path.insert(0, str(REPO / "tools" / "model-registry" / "src"))

FIXTURES = TESTS / "fixtures"
AUDIT = REPO / "audits" / "provenance-2026-10" / "fixtures"
GOLDEN = AUDIT / "golden"
MEMBERSHIP = AUDIT / "membership"
CONTRACT = REPO / "site" / "lib" / "provenance-contract.json"
GUARD_DIR = REPO / ".github" / "data-branch-guard"

#: The acceptance cut-off every golden value is "as of".
AS_OF = "2026-10-13T00:00:00Z"
#: The main commit the fixture bundle is built against (#636's merge).
FIXTURE_MAIN_SHA = "521d092813b78a88bd9a74b1052cfef1f230d86b"
OWNER, REPO_NAME, OWNER_LOGIN = "shaiss", "print-bench", "shaiss"


def _gz_json(path: pathlib.Path):
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def raw_pr(n: int) -> dict:
    return _gz_json(FIXTURES / "raw" / "pr" / f"{n}.json.gz")


def raw_brief(n: int) -> dict:
    return _gz_json(FIXTURES / "raw" / "brief" / f"{n}.json.gz")


def raw_release(tag: str) -> dict:
    return _gz_json(FIXTURES / "raw" / "release" / f"{tag}.json.gz")


def receipt_paths() -> list[pathlib.Path]:
    return sorted((FIXTURES / "receipts").rglob("*.json.gz"))


def receipts() -> list[dict]:
    return [_gz_json(p) for p in receipt_paths()]


def receipt(run_id: int) -> dict:
    hits = [p for p in receipt_paths() if p.name.startswith(f"{run_id}.a")]
    if not hits:
        raise KeyError(run_id)
    return _gz_json(sorted(hits)[-1])


def codebasis_index() -> dict:
    return json.loads((FIXTURES / "codebasis" / "index.json").read_text(encoding="utf-8"))


def codebasis_blob(sha: str, path: str) -> bytes | None:
    entry = codebasis_index().get(sha, {}).get(path)
    if entry is None:
        return None
    return gzip.decompress((FIXTURES / "codebasis" / "blobs" / f"{entry}.gz").read_bytes())


def main_history() -> dict:
    return _gz_json(FIXTURES / "main_history.json.gz")


def pr_files() -> dict:
    return _gz_json(FIXTURES / "membership" / "pr_files.json.gz")


def golden(design: str) -> dict:
    return _gz_json(GOLDEN / f"{design}.golden.json.gz")


def golden_full(design: str) -> dict:
    return _gz_json(GOLDEN / f"{design}.full.json.gz")


def membership_rows() -> list[dict]:
    with open(MEMBERSHIP / "membership.csv", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def refined_membership() -> dict:
    return json.loads((MEMBERSHIP / "refined_membership.json").read_text(encoding="utf-8"))


def contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _is_scaffold_stub(obj) -> bool:
    target = obj.__init__ if inspect.isclass(obj) else obj
    try:
        src = inspect.getsource(target)
    except (OSError, TypeError):
        return False
    return 'NotImplementedError("builder' in src


def needs(*objs):
    """Skip a test until every named function/class is implemented.

    The parallel build's cross-builder seam: a test that exercises another
    builder's module (e.g. test_acceptance needs trust, membership and
    serving) is written now, decorated ``@needs(trust.comment_tier, …)``, and
    runs automatically once those bodies stop raising the scaffold's
    ``NotImplementedError("builder …")`` — at integration at the latest.
    """
    missing = [f"{o.__module__}.{o.__qualname__}" for o in objs if _is_scaffold_stub(o)]
    return pytest.mark.skipif(bool(missing), reason="waits for " + ", ".join(missing))


@pytest.fixture
def fixtures_dir() -> pathlib.Path:
    return FIXTURES


@pytest.fixture
def repo_root() -> pathlib.Path:
    return REPO
