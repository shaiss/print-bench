"""Run receipts — the durable record of every agent run, captured before GitHub deletes it.

Since 2026-10-01 GitHub deletes workflow runs, jobs, check runs and statuses
after 90 days. The jobs response of an agent run is the ONLY place the
serving model is recorded (which ``(chain link N)`` step ran, and when), so
the harvester copies it into the evidence branch (docs/provenance.md
§Receipts).

**Selection** — from the runs LIST, never by step name: for each workflow in
``watched_workflows``, ``GET /actions/workflows/{wf}/runs?created=>=<cursor -
receipt_lookback_hours>`` (all pages, oldest window first under ``--since``);
every run with ``status == "completed"`` and ``conclusion != "skipped"``
whose receipt path is absent from the evidence tree gets ONE ``GET
/actions/runs/{id}/jobs?filter=all`` (paged; every attempt). Runs still
queued/in progress are left for the next pass.

**Full vs stub** (:func:`build_receipt`) — the receipt keeps the COMPLETE
jobs list (``kind: "full"``) when any job has an agent step that ran
(``steps.jobs_have_agent_step``) or any suspicious step
(``steps.suspicious_step_names``, the fail-safe); otherwise a stub
(``kind: "stub"``: each job's name/conclusion/attempt) — e.g. a disarmed
run. ``jobs_sha256`` is the canonical-JSON digest of the jobs list either
way, so a stub still pins what it summarised.

**Shape** (contract ``receipt@1``)::

    {"format": "receipt@1", "source": "live" | "snapshot:pr843",
     "workflow": "design-run.yml", "run": <rawdoc.project_run>,
     "kind": "full"|"stub", "step_grammar": 1,
     "jobs": [<complete job objects, sorted (run_attempt, id)>] | null,
     "jobs_sha256": "<hex>", "stub": {"jobs": [...]} | null,
     "suspicious_steps": [<names>]}

**Path** (:func:`receipt_path`) — ``receipts/YYYY/MM/DD/<run_id>.a<run_attempt>.json.gz``
with the date of ``run.created_at`` (UTC); day-sharding keeps every tree
object under ~200 entries. A later re-run attempt is a NEW path; the
serving join reads the highest attempt it has.

**Cursor** — per workflow, ``state.cursors.receipts[wf]`` = the
``created_at`` of the oldest run seen still not completed in this pass, or
else of the newest completed run processed. Add-only paths make re-listing
idempotent.

The byte-exact reference for :func:`build_receipt` is
``tests/dev/build_fixtures.py::build_receipt``; tests/test_receipts.py pins
them equal over every committed fixture receipt.

Owner: H1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .protocols import GitHubAPI

RECEIPT_FORMAT = "receipt@1"
SOURCE_LIVE = "live"


def receipt_path(run: dict[str, Any]) -> str:
    """``receipts/YYYY/MM/DD/<id>.a<attempt>.json.gz`` from a (projected or raw) run object."""
    raise NotImplementedError("builder H1")


def build_receipt(workflow: str, run: dict[str, Any], jobs: Optional[list[dict[str, Any]]],
                  source: str) -> dict[str, Any]:
    """The receipt@1 document (byte-identical to tests/dev/build_fixtures.py's reference)."""
    raise NotImplementedError("builder H1")


@dataclass
class ReceiptPass:
    """Result of one receipts pass: new files to add, updated cursors, counts for the summary."""

    files: dict[str, bytes] = field(default_factory=dict)
    cursors: dict[str, str] = field(default_factory=dict)
    listed: int = 0
    skipped_runs: int = 0
    in_progress: int = 0
    full: int = 0
    stub: int = 0
    suspicious: dict[str, int] = field(default_factory=dict)
    budget_stopped: bool = False


def harvest_receipts(gh: GitHubAPI, *, workflows: tuple[str, ...], cursors: dict[str, str],
                     since: Optional[str], until: Optional[str], lookback_hours: int,
                     exists: Callable[[str], bool]) -> ReceiptPass:
    """One receipts pass (module docstring). ``exists(path)`` answers from the evidence tree.

    Catches ``github.BudgetExhausted``: returns what it has with
    ``budget_stopped=True`` and cursors that resume exactly where it stopped.
    """
    raise NotImplementedError("builder H1")


def load_receipt(data: bytes) -> dict[str, Any]:
    """Parse one stored receipt (gzip canonical JSON). Shape validation is ``check``'s job
    (``contract.validate_tree``); the write path never calls the contract module."""
    raise NotImplementedError("builder H1")
