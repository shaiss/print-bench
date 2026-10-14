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
  ``evidence_sha``, ``producer_run``). It is for the site's own integrity
  check; the no-op decision never trusts it (critique item 5).
* **No churn** (critique item 6): nothing in a record or a view depends on
  main's sha — the view has no ``main_sha`` (the bundle's meta does), and a
  committed row's line and URL point at the commit that added it — so a main
  push that touches no ``designs/`` file changes no record, no view and no
  ``content_sha256``, and pushes nothing. ``main_sha`` then reads "the main
  commit these views were last recomputed against".
* :func:`same_content` compares the CURRENT derived tip's actual blobs with
  the new tree: the same path set, every path except ``site/bundle.json``
  byte-identical, and ``site/bundle.json`` equal once the three meta fields
  are removed from both — so a forged tip that copies the real
  ``content_sha256`` but alters a view is not "same content". The push
  decision is ``site_changed = not derived_continuity.accepted or not
  same_content(tip, new)`` (a non-checkpointed tip is overwritten even when
  its content matches).
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

**Fixture parity** — ``tests/test_bundle.py`` rebuilds
``site/test/fixtures/provenance-bundle.json`` IN MEMORY from the committed
SYNTHETIC records under ``tools/provenance/tests/fixtures/records/``
(hand-authored, contract-valid, covering every record kind and every event
field set) with fixed meta (``main_sha =
521d092813b78a88bd9a74b1052cfef1f230d86b``, ``evidence_sha = "0"*40``,
``producer_run = 1``) and asserts byte equality with the committed file; it
writes the file only when ``PROVENANCE_UPDATE_FIXTURES=1`` is set (a test
never writes into the repo by default — critique item 27). The test needs
``episodes.episodes_of`` (H3) and so carries ``@needs``; the committed file is
regenerated once at integration. The Node validator
(``site/lib/provenance-contract.mjs``) must accept that file and reject a copy
with one extra field, as the Python validator does.

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


#: The bundle fields that describe the bundle rather than its content.
META_FIELDS = ("main_sha", "evidence_sha", "producer_run")


def same_content(tip: Optional[TreeReader], new_files: dict[str, tuple[str, bytes]]) -> bool:
    """True when the current derived tip (``None`` = absent → False) holds exactly ``new_files``
    up to the bundle's :data:`META_FIELDS` (module docstring). Reads the tip's blobs; never its
    ``content_sha256`` field. Modes are compared too."""
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

    ``evidence`` is the evidence commit the bundle will name — this run's new
    commit, the unchanged tip, or the newest checkpoint when the tip is foreign
    (cli step 2). The order is fixed (critique item 14):

    1. read every ``raw/**`` (highest revision per key) and ``receipts/**``
       (highest attempt per run);
    2. ``extract.extract_pr`` / ``extract_brief`` / ``extract_release`` per raw
       doc (``ExtractContext.brief_numbers`` from the ``raw/brief/`` paths),
       ``extract.extract_direct_commits`` from main;
    3. ``serving.ReceiptIndex(receipts)``; ``claims = serving.run_claims(brief
       records, …)``; ``serving.annotate_record(…, claims=claims)`` per record;
       ``serving.receipt_events`` appended to each PR record (unplaced);
    4. ``episodes.place`` per record — after this every event has an episode;
    5. ``views.build_views`` (rows via ``episodes.decision_rows``, rounds via
       ``episodes.rounds_from_record``);
    6. :func:`build_bundle` and :func:`derived_tree_files`.

    No fetch happens here: ``git`` reads only what the job-start fetch made
    local (a missing commit is basis ``none``). The orchestrator compares the
    result with the current derived tip via :func:`same_content`.
    """
    raise NotImplementedError("builder H5")
