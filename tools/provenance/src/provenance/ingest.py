"""INGEST — the #843 Actions/status snapshot → ``receipts/`` and ``raw/snapshot/`` on ``provenance``.

The first runs' records expire from ~2026-10-30 at GitHub's 90-day
retention, before the scheduled harvester can be armed (P2). PR #843
(branch ``ccr-d0be94c3-o4sati-rescue``, directory
``audits/provenance-2026-10/rescue/``) holds a GET-only snapshot of them
taken 2026-10-13. ``ingest`` moves the parts the extractors consume into the
evidence branch, in the same shapes the live harvester writes, so a run that
GitHub has deleted is indistinguishable downstream from one captured live
(docs/provenance.md §INGEST).

**Locating the snapshot.** ``--snapshot-dir DIR`` (local), or ``--ref REF
[--path P]`` (the dispatch): :func:`materialize_from_ref` runs ``git fetch
origin <REF>`` then ``git show <REF>:<P>/<file>`` for each manifest file
into a temp dir (via ``gitstore``; this module runs no git itself). ``REF``
and ``P`` default to the conf's ``snapshot_ref``/``snapshot_path``.

**Verification first.** :func:`verify_manifest` recomputes the SHA-256 of
every file ``MANIFEST.sha256`` lists and requires ``runs.tar``,
``jobs.tar``, ``sha.tar``; any mismatch or missing file raises
:class:`IngestError` and nothing is planned.

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

A watched run with no ``jobs.tar`` member is counted (``missing_jobs``) and
skipped — the live receipts pass still fetches it while GitHub has it.

**Idempotence.** A planned path already present with identical bytes is
skipped; present with different bytes (a live receipt captured first, whose
``source`` differs) is counted as ``conflicts`` and never modified — the
add-only rule wins. ``state.json`` ``ingested[S]`` records the manifest
digest and counts; a second ingest of the same snapshot plans zero new
files and pushes nothing.

**Consumption.** ``freeze.capture_pr`` unions ``raw/snapshot/S/runs/ci.yml``
rows (by run id, matching the PR's head branch / commits) into the PR's
``ci_runs`` and ``raw/snapshot/S/statuses/<sha>`` into its ``statuses`` (by
status id) — live rows win on an id collision. That is how a PR frozen in
the P2 backfill keeps its pushed heads and per-round ``reviewer-signoff``
statuses after GitHub deleted them.

Owner: H1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

REQUIRED_FILES = ("MANIFEST.sha256", "runs.tar", "jobs.tar", "sha.tar")
IGNORED_FILES = ("prcommits.tar", "pulls.json.gz", "workflows.json.gz", "capture.py", "README.md")
RUNS_FORMAT = "raw-snapshot-runs@1"
STATUSES_FORMAT = "raw-snapshot-statuses@1"


class IngestError(Exception):
    """The snapshot failed verification (manifest mismatch, missing file, bad member)."""


@dataclass
class SnapshotData:
    """The parsed snapshot: run rows by workflow file, jobs by run id, statuses by sha."""

    snapshot_id: str
    manifest_sha256: str
    runs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    jobs: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    statuses: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    check_runs: dict[str, int] = field(default_factory=dict)


@dataclass
class IngestPlan:
    """Files to add to the evidence tree plus the counts the job summary reports."""

    files: dict[str, bytes] = field(default_factory=dict)
    receipts_full: int = 0
    receipts_stub: int = 0
    receipts_existing: int = 0
    statuses: int = 0
    runs_listings: int = 0
    skipped_runs: int = 0
    missing_jobs: int = 0
    conflicts: int = 0
    state_entry: dict[str, Any] = field(default_factory=dict)


def verify_manifest(snapshot_dir: str) -> str:
    """Check every MANIFEST.sha256 line; return the manifest file's own sha256. Raises IngestError."""
    raise NotImplementedError("builder H1")


def read_snapshot(snapshot_dir: str, snapshot_id: str) -> SnapshotData:
    """Verify, then parse the tars (stdlib ``tarfile``; members are gzip canonical JSON)."""
    raise NotImplementedError("builder H1")


def plan_ingest(data: SnapshotData, *, watched: tuple[str, ...],
                existing: Callable[[str], Optional[bytes]]) -> IngestPlan:
    """The mapping table of the module docstring. ``existing(path)`` reads the evidence tree."""
    raise NotImplementedError("builder H1")


def materialize_from_ref(git: Any, ref: str, path: str, dest_dir: str) -> str:
    """Fetch ``ref`` and copy ``<path>/<file>`` for every manifest file into ``dest_dir``
    via ``gitstore.Git`` (``fetch`` + ``show``); returns ``dest_dir``."""
    raise NotImplementedError("builder H1")
