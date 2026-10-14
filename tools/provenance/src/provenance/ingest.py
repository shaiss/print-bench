"""INGEST — the #843 Actions/status snapshot → ``receipts/`` and ``raw/snapshot/`` on ``provenance``.

GitHub deletes workflow runs, jobs, check runs and statuses after 90 days
(since 2026-10-01). PR #843 holds a GET-only snapshot of every run created
2026-08-01T16:59Z → 2026-10-13T06:13Z; it was merged at 2026-10-14T01:23Z
(merge commit ``411a7565e1c6c8f2b96edf631286ceac798d7887``) and so lives in
MAIN's history at ``audits/provenance-2026-10/rescue/``. Ingest moves the
parts the extractors consume into the evidence branch, in the same shapes the
live harvester writes, so a run GitHub has deleted is indistinguishable
downstream from one captured live (docs/provenance.md §INGEST).

**Not a mode** (critique items 2, 17; owner decision 12 keeps the dispatch
modes to harvest / refreeze / recover). ``cli.cmd_harvest`` ingests
automatically when ``state.ingested[<snapshot_id>]`` is absent or records an
older :data:`INGEST_VERSION` — at the bootstrap run in practice — at ≈ 0 API
cost. The ONLY source is the default-branch checkout's ``snapshot_dir``
(conf), i.e. bytes a human merged into main; no ref, branch or path input
can redirect it. ``--snapshot-dir`` exists for tests and local dry-runs.

**Authenticity first.** :func:`verify_manifest` refuses unless
``sha256(MANIFEST.sha256)`` equals the conf's ``snapshot_manifest_sha256``
pin (``c713379b…51c7``) — MANIFEST.sha256 lives in the tree it verifies, so
on its own it proves integrity, not authenticity: the pin, reviewed on main,
is what makes an internally consistent forged directory fail. Then every
manifest line is recomputed; ``runs.tar``, ``jobs.tar``, ``sha.tar`` are
required. Any failure raises :class:`IngestError`; nothing is planned.

**Reading tars** (:func:`read_snapshot`, stdlib ``tarfile``): members are read
with ``TarFile.extractfile`` only — never ``extract``/``extractall`` — and a
member that is not a regular file, or whose name does not full-match
:data:`MEMBER_RE` (``[A-Za-z0-9._-]+\\.json\\.gz``: no directory, no ``..``),
is an :class:`IngestError`. Members are gzip canonical JSON.

**Mapping** (snapshot id ``S`` = ``pr843``):

========================================  ===========================================
snapshot member                            evidence path
========================================  ===========================================
``runs.tar`` / ``<wf>.json.gz`` row,       ``receipts/YYYY/MM/DD/<id>.a<attempt>.json.gz``
wf ∈ watched_workflows, status completed,  — ``receipts.build_receipt(wf, row,
conclusion != skipped, + ``jobs.tar`` /    jobs, "snapshot:S")`` (full or stub by the
``<id>.json.gz`` ``jobs``                  same rule as live)
``runs.tar`` / ``ci.yml.json.gz``          ``raw/snapshot/S/runs/ci.yml.json.gz`` —
                                           ``raw-snapshot-runs@1`` (every row,
                                           ``rawdoc.project_runs``)
``sha.tar`` / ``<sha>.json.gz`` with ≥1    ``raw/snapshot/S/statuses/<sha>.json.gz`` —
status                                     ``raw-snapshot-statuses@1``
                                           (``rawdoc.project_statuses``; check runs
                                           dropped, counted)
``prcommits.tar``, ``pulls.json.gz``,      not ingested: ``/pulls/{n}/commits`` and
``workflows.json.gz``, ``capture.py``      ``/pulls`` are outside Actions retention
                                           and are re-read live at freeze time
========================================  ===========================================

Scope is now REVERSIBLE: the snapshot is permanent in main's history, so a
later :data:`INGEST_VERSION` may widen it (the dropped check runs; the
agent-bearing workflows outside the watched nine, e.g. lifestyle-shot /
product-still / lifestyle-clip) and re-run as an add-only ingest of the new
paths only.

A watched run with no ``jobs.tar`` member is counted (``missing_jobs``) and
skipped — the live receipts pass still fetches it while GitHub has it.

**Cursors.** The plan sets every watched workflow's ``state.cursors.receipts``
to :attr:`SnapshotData.snapshot_end` (the latest ``created_at`` of any row,
2026-10-13T06:13Z) when the cursor is absent or older, so the first live pass
lists from ``snapshot_end − receipt_lookback_hours`` instead of a full
backfill (critique item 8).

**Idempotence** — on CONTENT, never gzip bytes (critique item 19): a planned
path already present whose decompressed bytes are identical is skipped;
present with different content (a live receipt captured first — its
``source`` differs) is counted as ``conflicts`` and never modified — the
add-only rule wins. ``state.ingested[S]`` records the manifest digest, the
main commit, the version, ``snapshot_end`` and counts; a second ingest of
the same snapshot and version plans zero files and pushes nothing.

**Consumption.** ``freeze.capture_pr`` unions ``raw/snapshot/S/runs/ci.yml``
rows (by run id, matching the PR's head branch / commits) into the PR's
``ci_runs`` and ``raw/snapshot/S/statuses/<sha>`` into its ``statuses`` (by
status id) — live rows win on an id collision. That is how a PR frozen in
the P2 backfill keeps its pushed heads and per-round ``reviewer-signoff``
statuses after GitHub deleted them.

Owner: H1. Pure except for reading ``snapshot_dir`` (files only; no git).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

REQUIRED_FILES = ("MANIFEST.sha256", "runs.tar", "jobs.tar", "sha.tar")
IGNORED_FILES = ("prcommits.tar", "pulls.json.gz", "workflows.json.gz", "capture.py", "README.md")
RUNS_FORMAT = "raw-snapshot-runs@1"
STATUSES_FORMAT = "raw-snapshot-statuses@1"

#: Bump to re-run the ingest with a wider scope (add-only: only new paths are planned).
INGEST_VERSION = 1

#: Every tar member name must full-match this (critique item 2).
MEMBER_RE = re.compile(r"[A-Za-z0-9._-]+\.json\.gz")


class IngestError(Exception):
    """The snapshot failed verification (pin or manifest mismatch, missing file, bad member)."""


@dataclass
class SnapshotData:
    """The parsed snapshot: run rows by workflow file, jobs by run id, statuses by sha."""

    snapshot_id: str
    manifest_sha256: str
    snapshot_end: str
    runs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    jobs: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    statuses: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    check_runs: dict[str, int] = field(default_factory=dict)


@dataclass
class IngestPlan:
    """Files to add to the evidence tree, cursor updates and the counts the job summary reports."""

    files: dict[str, bytes] = field(default_factory=dict)
    cursors: dict[str, str] = field(default_factory=dict)
    receipts_full: int = 0
    receipts_stub: int = 0
    receipts_existing: int = 0
    statuses: int = 0
    runs_listings: int = 0
    skipped_runs: int = 0
    missing_jobs: int = 0
    conflicts: int = 0
    state_entry: dict[str, Any] = field(default_factory=dict)


def verify_manifest(snapshot_dir: str, expected_manifest_sha256: str) -> str:
    """Check the pin, then every MANIFEST.sha256 line; return the manifest's own sha256.
    Raises IngestError on a pin mismatch (even for an internally consistent directory),
    a line mismatch, or a missing required file."""
    raise NotImplementedError("builder H1")


def read_snapshot(snapshot_dir: str, snapshot_id: str, expected_manifest_sha256: str) -> SnapshotData:
    """Verify, then parse the tars (``extractfile`` only; regular members; :data:`MEMBER_RE`)."""
    raise NotImplementedError("builder H1")


def needs_ingest(state: dict[str, Any], snapshot_id: str) -> bool:
    """True when ``state.ingested[snapshot_id]`` is absent or its ``version`` < :data:`INGEST_VERSION`."""
    raise NotImplementedError("builder H1")


def plan_ingest(data: SnapshotData, *, watched: tuple[str, ...], commit: str,
                cursors: dict[str, str],
                existing: Callable[[str], Optional[bytes]]) -> IngestPlan:
    """The mapping table of the module docstring. ``existing(path)`` reads the evidence tree;
    ``cursors`` are the current receipts cursors (raised to ``snapshot_end``, never lowered)."""
    raise NotImplementedError("builder H1")
