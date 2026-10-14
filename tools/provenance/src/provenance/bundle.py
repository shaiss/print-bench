"""The site bundle and the ``provenance-site`` tree — the one thing the site reads.

``site/bundle.json`` (contract ``bundle@1``)::

    {"format": "bundle@1", "contract": 1, "extractor": "provenance-extract 1",
     "main_sha": <sha40>, "evidence_sha": <sha40>, "producer_run": <run id>,
     "content_sha256": <hex>,
     "views": {"<design>": <view@1>},
     "views_sha256": {"<design>": sha256(canonical(view))}}

* ``content_sha256`` = ``canonical.content_sha256({"records": {path:
  sha256}, "views_sha256": …, "extractor": …})`` — a digest of everything
  EXCEPT the three provenance-of-the-bundle fields (``main_sha``,
  ``evidence_sha``, ``producer_run``). :func:`same_content` compares it with
  the current derived tip's bundle: equal → the run pushes nothing, so a
  main push that changes no view does not churn the derived ref and the
  bundle's ``main_sha`` reads "the main commit these views were last
  recomputed against".
* No cursors, no pending list, no wall clock: the bundle changes only when
  a view or a record changes.

The derived tree (:func:`derived_tree_files`), one parentless commit pushed
with ``--force-with-lease`` (``gitstore.push_force_with_lease``):

==================================  ==========================================
``vercel.json``,                    the guard bytes (``gitstore.guard_blobs``)
``scripts/vercel-ignore-build.sh``
``FORMAT``                          ``print-bench-provenance-site 1\\n``
``records/pr/<n>.json``             record@1 (canonical JSON, not gzipped)
``records/brief/<n>.json``
``records/commit/<sha40>.json``
``records/release/<tag>.json``
``views/<design>.json``             view@1
``site/bundle.json``                bundle@1
==================================  ==========================================

**Fixture parity** — ``tests/test_bundle.py`` regenerates
``site/test/fixtures/provenance-bundle.json`` from the committed SYNTHETIC
records under ``tools/provenance/tests/fixtures/records/`` (hand-authored,
contract-valid, covering every record kind and every event field set — so
the parity proof does not wait on the extractor) with fixed meta (``main_sha = 521d092813b78a88bd9a74b1052cfef1f230d86b``,
``evidence_sha = "0"*40``, ``producer_run = 1``) and asserts byte equality
with the committed file (the growth server-parity pattern); the Node
validator (``site/lib/provenance-contract.mjs``) must accept that file and
reject a copy with one extra field, as the Python validator does.

Owner: H5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .protocols import CodeBasis, GitReader, TreeReader

BUNDLE_FORMAT = "bundle@1"
DERIVED_FORMAT_BYTES = b"print-bench-provenance-site 1\n"
EVIDENCE_FORMAT_BYTES = b"print-bench-provenance 1\n"
BUNDLE_PATH = "site/bundle.json"


def build_bundle(views: dict[str, dict[str, Any]], *, records: dict[str, bytes], main_sha: str,
                 evidence_sha: str, producer_run: int, extractor: str) -> dict[str, Any]:
    """bundle@1 from views and the serialized records (``{tree path: canonical bytes}``)."""
    raise NotImplementedError("builder H5")


def same_content(old_bundle: Optional[dict[str, Any]], new_bundle: dict[str, Any]) -> bool:
    """True when ``content_sha256`` is equal (meta fields ignored)."""
    raise NotImplementedError("builder H5")


def record_path(record: dict[str, Any]) -> str:
    """``records/<kind>/<key>.json`` for one record@1."""
    raise NotImplementedError("builder H5")


def derived_tree_files(records: list[dict[str, Any]], views: dict[str, dict[str, Any]],
                       bundle: dict[str, Any],
                       guard: dict[str, tuple[str, bytes]]) -> dict[str, tuple[str, bytes]]:
    """``{path: (mode, bytes)}`` for the whole provenance-site tree (table above)."""
    raise NotImplementedError("builder H5")


@dataclass
class DerivedTree:
    """The result of :func:`derive`: the tree's files, the bundle, and summary counts."""

    files: dict[str, tuple[str, bytes]] = field(default_factory=dict)
    bundle: dict[str, Any] = field(default_factory=dict)
    records: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def derive(evidence: TreeReader, *, git: GitReader, codebasis: CodeBasis, main_sha: str,
           owner: str, repo: str, owner_login: str, evidence_sha: str, producer_run: int,
           edit_grace_seconds: int, guard: dict[str, tuple[str, bytes]]) -> DerivedTree:
    """The whole derivation, evidence tree → provenance-site tree (pure given its readers).

    1. read every ``raw/**`` (highest revision per key) and ``receipts/**``;
    2. ``extract.extract_pr`` / ``extract_brief`` / ``extract_release`` per raw doc,
       ``extract.extract_direct_commits`` from main;
    3. ``serving.ReceiptIndex(receipts)``; ``serving.annotate_record`` +
       ``serving.receipt_events`` per PR record (H4);
    4. ``views.build_views`` (rows via ``episodes.decision_rows``);
    5. :func:`build_bundle` and :func:`derived_tree_files`.

    The orchestrator (``cli.cmd_harvest``) calls this once per run and compares
    ``bundle.content_sha256`` with the current derived tip (:func:`same_content`).
    """
    raise NotImplementedError("builder H5")
