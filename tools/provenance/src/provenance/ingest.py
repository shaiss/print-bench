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

import gzip
import hashlib
import json
import os
import re
import tarfile
import zlib
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from . import canonical, rawdoc
from .receipts import build_receipt, receipt_path

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


_MANIFEST_LINE_RE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)")
_SNAPSHOT_ID_RE = re.compile(r"pr[0-9]+")
_SHA_RE = re.compile(r"[0-9a-f]{40}")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(snapshot_dir: str, expected_manifest_sha256: str) -> str:
    """Check the pin, then every MANIFEST.sha256 line; return the manifest's own sha256.
    Raises IngestError on a pin mismatch (even for an internally consistent directory),
    a line mismatch, or a missing required file.

    Every required tar must also be LISTED in the manifest — a tar the pinned
    manifest does not cover would be unauthenticated however its bytes look.
    """
    for name in REQUIRED_FILES:
        if not os.path.isfile(os.path.join(snapshot_dir, name)):
            raise IngestError(f"snapshot: required file {name} is missing")
    manifest_path = os.path.join(snapshot_dir, "MANIFEST.sha256")
    with open(manifest_path, "rb") as fh:
        manifest = fh.read()
    digest = hashlib.sha256(manifest).hexdigest()
    if digest != expected_manifest_sha256:
        raise IngestError(f"snapshot: MANIFEST.sha256 digest {digest} is not the pinned "
                          f"snapshot_manifest_sha256 {expected_manifest_sha256}")
    listed: dict[str, str] = {}
    for lineno, line in enumerate(manifest.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        m = _MANIFEST_LINE_RE.fullmatch(line)
        if m is None:
            raise IngestError(f"snapshot: MANIFEST.sha256:{lineno}: malformed line")
        want, name = m.groups()
        if name in listed:
            raise IngestError(f"snapshot: MANIFEST.sha256:{lineno}: {name} listed twice")
        listed[name] = want
        path = os.path.join(snapshot_dir, name)
        if not os.path.isfile(path):
            raise IngestError(f"snapshot: {name} (MANIFEST.sha256:{lineno}) is missing")
        got = _sha256_file(path)
        if got != want:
            raise IngestError(f"snapshot: {name} sha256 {got} does not match MANIFEST.sha256:{lineno}")
    for name in REQUIRED_FILES:
        if name != "MANIFEST.sha256" and name not in listed:
            raise IngestError(f"snapshot: {name} is not covered by MANIFEST.sha256")
    return digest


def _members(path: str) -> list[tuple[str, Any]]:
    """``[(name, parsed JSON)]`` of one snapshot tar — regular, flat ``*.json.gz`` members only,
    read with ``extractfile`` (nothing is ever written to disk)."""
    out: list[tuple[str, Any]] = []
    try:
        with tarfile.open(path, mode="r:") as tf:
            for member in tf.getmembers():
                if not member.isreg():
                    raise IngestError(f"snapshot: {os.path.basename(path)} member {member.name!r} "
                                      "is not a regular file")
                if MEMBER_RE.fullmatch(member.name) is None:
                    raise IngestError(f"snapshot: {os.path.basename(path)} member {member.name!r} "
                                      f"does not match {MEMBER_RE.pattern}")
                fh = tf.extractfile(member)
                if fh is None:
                    raise IngestError(f"snapshot: {member.name!r} is unreadable")
                try:
                    value = json.loads(gzip.decompress(fh.read()).decode("utf-8"))
                except (OSError, EOFError, zlib.error, UnicodeDecodeError, ValueError) as exc:
                    raise IngestError(f"snapshot: {member.name!r} is not gzip JSON ({type(exc).__name__})") from None
                out.append((member.name, value))
    except tarfile.TarError as exc:
        raise IngestError(f"snapshot: {os.path.basename(path)} is not a tar ({exc})") from None
    return out


def _stem(name: str) -> str:
    return name[: -len(".json.gz")]


def read_snapshot(snapshot_dir: str, snapshot_id: str, expected_manifest_sha256: str) -> SnapshotData:
    """Verify, then parse the tars (``extractfile`` only; regular members; :data:`MEMBER_RE`).

    ``snapshot_end`` is the latest ``created_at`` of any ``runs.tar`` row (every
    workflow, skipped rows included) — the instant the snapshot is complete up to.
    """
    if not _SNAPSHOT_ID_RE.fullmatch(snapshot_id or ""):
        raise IngestError(f"snapshot id {snapshot_id!r} does not match pr<N>")
    digest = verify_manifest(snapshot_dir, expected_manifest_sha256)
    runs: dict[str, list[dict[str, Any]]] = {}
    end = ""
    for name, rows in _members(os.path.join(snapshot_dir, "runs.tar")):
        if not isinstance(rows, list):
            raise IngestError(f"snapshot: runs.tar/{name} is not a list of runs")
        runs[_stem(name)] = rows
        for r in rows:
            created = r.get("created_at") if isinstance(r, dict) else None
            if isinstance(created, str) and created > end:
                end = created
    if not end:
        raise IngestError("snapshot: runs.tar holds no run")
    jobs: dict[int, list[dict[str, Any]]] = {}
    for name, doc in _members(os.path.join(snapshot_dir, "jobs.tar")):
        if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), list):
            raise IngestError(f"snapshot: jobs.tar/{name} is not {{run_id, jobs}}")
        run_id = doc.get("run_id")
        if not isinstance(run_id, int) or str(run_id) != _stem(name):
            raise IngestError(f"snapshot: jobs.tar/{name} names run {run_id!r}")
        jobs[run_id] = doc["jobs"]
    statuses: dict[str, list[dict[str, Any]]] = {}
    check_runs: dict[str, int] = {}
    for name, doc in _members(os.path.join(snapshot_dir, "sha.tar")):
        sha = doc.get("sha") if isinstance(doc, dict) else None
        if not isinstance(sha, str) or not _SHA_RE.fullmatch(sha) or sha != _stem(name):
            raise IngestError(f"snapshot: sha.tar/{name} names sha {sha!r}")
        statuses[sha] = list(doc.get("statuses") or [])
        check_runs[sha] = len(doc.get("check_runs") or [])
    return SnapshotData(snapshot_id=snapshot_id, manifest_sha256=digest, snapshot_end=end,
                        runs=runs, jobs=jobs, statuses=statuses, check_runs=check_runs)


def needs_ingest(state: dict[str, Any], snapshot_id: str) -> bool:
    """True when ``state.ingested[snapshot_id]`` is absent or its ``version`` < :data:`INGEST_VERSION`."""
    entry = (state.get("ingested") or {}).get(snapshot_id)
    if not isinstance(entry, dict):
        return True
    version = entry.get("version")
    return not isinstance(version, int) or version < INGEST_VERSION


def _content(path: str, data: bytes) -> bytes:
    """Content identity: the decompressed bytes of a ``*.json.gz`` blob, else the bytes."""
    if path.endswith(".json.gz"):
        try:
            return gzip.decompress(data)
        except (OSError, EOFError, zlib.error):
            return data
    return data


def plan_ingest(data: SnapshotData, *, watched: tuple[str, ...], commit: str,
                cursors: dict[str, str],
                existing: Callable[[str], Optional[bytes]]) -> IngestPlan:
    """The mapping table of the module docstring. ``existing(path)`` reads the evidence tree;
    ``cursors`` are the current receipts cursors (raised to ``snapshot_end``, never lowered).

    Counts: ``receipts_full``/``receipts_stub`` are NEW receipts planned,
    ``receipts_existing`` receipts already present with identical content,
    ``conflicts`` paths present with other content (never modified);
    ``state_entry.receipts`` / ``statuses`` / ``runs_listings`` count every
    mapped file the evidence holds afterwards (planned + identical).
    """
    sid = data.snapshot_id
    plan = IngestPlan()
    held = {"receipts": 0, "statuses": 0, "runs_listings": 0}

    def offer(path: str, blob: bytes, kind: str) -> bool:
        present = existing(path)
        if present is None:
            plan.files[path] = blob
            held[kind] += 1
            return True
        if _content(path, present) == _content(path, blob):
            held[kind] += 1
            if kind == "receipts":
                plan.receipts_existing += 1
            return False
        plan.conflicts += 1
        return False

    watched_set = set(watched)
    for wf in sorted(data.runs):
        if wf not in watched_set:
            continue
        for row in sorted(data.runs[wf], key=lambda r: (r.get("created_at") or "", r.get("id") or 0)):
            if row.get("status") != "completed" or row.get("conclusion") == "skipped":
                plan.skipped_runs += 1
                continue
            jobs = data.jobs.get(row.get("id"))
            if jobs is None:
                plan.missing_jobs += 1
                continue
            doc = build_receipt(wf, row, jobs, f"snapshot:{sid}")
            if offer(receipt_path(row), canonical.dumps_gz(doc), "receipts"):
                if doc["kind"] == "full":
                    plan.receipts_full += 1
                else:
                    plan.receipts_stub += 1
    if "ci.yml" in data.runs:
        doc = {"format": RUNS_FORMAT, "runs": rawdoc.project_runs(data.runs["ci.yml"]),
               "snapshot": sid, "workflow": "ci.yml"}
        offer(f"raw/snapshot/{sid}/runs/ci.yml.json.gz", canonical.dumps_gz(doc), "runs_listings")
    for sha in sorted(data.statuses):
        rows = data.statuses[sha]
        if not rows:
            continue
        doc = {"check_runs_dropped": data.check_runs.get(sha, 0), "format": STATUSES_FORMAT,
               "sha": sha, "snapshot": sid, "statuses": rawdoc.project_statuses(rows)}
        offer(f"raw/snapshot/{sid}/statuses/{sha}.json.gz", canonical.dumps_gz(doc), "statuses")
    plan.statuses = held["statuses"]
    plan.runs_listings = held["runs_listings"]
    for wf in watched:
        cur = cursors.get(wf)
        if cur is None or cur < data.snapshot_end:
            plan.cursors[wf] = data.snapshot_end
    plan.state_entry = {
        "commit": commit, "manifest_sha256": data.manifest_sha256, "receipts": held["receipts"],
        "runs_listings": held["runs_listings"], "snapshot_end": data.snapshot_end,
        "statuses": held["statuses"], "version": INGEST_VERSION,
    }
    return plan
