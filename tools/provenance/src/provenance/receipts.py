"""Run receipts — the durable record of every agent run, captured before GitHub deletes it.

Since 2026-10-01 GitHub deletes workflow runs, jobs, check runs and statuses
after 90 days. The jobs response of an agent run is the ONLY place the
serving model is recorded (which ``(chain link N)`` step ran, and when), so
the harvester copies it into the evidence branch (docs/provenance.md
§Receipts).

**Selection** — from the runs LIST, never by step name: for each workflow in
``watched_workflows``, the window ``[cursor − receipt_lookback_hours, until or
now]`` (``--since`` replaces the cursor) is split into UTC-day windows and
each is listed with ``GET /actions/workflows/{wf}/runs?created=<A>..<B>``
(``gh.iter_pages``, all pages). GitHub returns at most 1,000 results for a
FILTERED runs list (``created``/``branch``/``event``/``status``), and
auto-review alone has 1,434 non-skipped runs in the snapshot, so (critique
item 8): a window whose ``total_count >= 1000`` is halved recursively (down
to one minute, then :class:`github.Truncated`); every window's rows must
number exactly its ``total_count`` (``B`` never exceeds the ``now`` the CLI
read, so a closed window's membership is fixed; a mismatch is retried once,
then ``Truncated``). No other filter is ever sent. Every run with ``status ==
"completed"`` and ``conclusion != "skipped"`` whose receipt path is absent
from the evidence tree gets ONE ``GET /actions/runs/{id}/jobs?filter=all``
(paged; every attempt). Runs still queued/in progress are left for the next
pass.

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
else of the newest completed run processed. A fresh state's cursor is set by
the ingest to the snapshot's end (2026-10-13T06:13:35Z); with no ingest it is
``backfill_since``. Add-only paths make re-listing idempotent.

**Identity is content** (critique item 19): two receipts are the same when
their DECOMPRESSED canonical JSON is byte-identical; ``.gz`` bytes are
storage only (deflate output differs between zlib builds — the runner's and a
builder's Python need not agree).

The reference for :func:`build_receipt` is
``tests/dev/build_fixtures.py::build_receipt``; tests/test_receipts.py pins
the decompressed bytes equal over every committed fixture receipt.

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
    """The receipt@1 document (canonical JSON identical to tests/dev/build_fixtures.py's reference)."""
    raise NotImplementedError("builder H1")


@dataclass
class ReceiptPass:
    """Result of one receipts pass: new files to add, updated cursors, counts for the summary."""

    files: dict[str, bytes] = field(default_factory=dict)
    cursors: dict[str, str] = field(default_factory=dict)
    listed: int = 0
    windows: int = 0
    skipped_runs: int = 0
    in_progress: int = 0
    full: int = 0
    stub: int = 0
    suspicious: dict[str, int] = field(default_factory=dict)
    budget_stopped: bool = False


def run_windows(start: str, end: str) -> list[tuple[str, str]]:
    """UTC-day windows ``[(A, B)]`` covering ``[start, end]`` (RFC3339 seconds; ``B`` inclusive)."""
    raise NotImplementedError("builder H1")


def list_runs(gh: GitHubAPI, workflow: str, created_from: str, created_to: str) -> list[dict[str, Any]]:
    """Every run created in ``[created_from, created_to]``: ``total_count`` asserted, halving on
    ``>= 1000`` (module docstring). Raises ``github.Truncated`` when a one-minute window still caps."""
    raise NotImplementedError("builder H1")


def harvest_receipts(gh: GitHubAPI, *, workflows: tuple[str, ...], cursors: dict[str, str],
                     since: Optional[str], until: Optional[str], now: str, lookback_hours: int,
                     default_cursor: str, exists: Callable[[str], bool]) -> ReceiptPass:
    """One receipts pass (module docstring). ``exists(path)`` answers from the evidence tree.

    Catches ``github.BudgetExhausted``: returns what it has with
    ``budget_stopped=True`` and cursors that resume exactly where it stopped.
    """
    raise NotImplementedError("builder H1")


def load_receipt(data: bytes) -> dict[str, Any]:
    """Parse one stored receipt (gzip canonical JSON). Shape validation is ``check``'s job
    (``contract.validate_tree``); the write path never calls the contract module."""
    raise NotImplementedError("builder H1")
