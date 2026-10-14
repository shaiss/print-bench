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
``backfill_since``. Add-only paths make re-listing idempotent. Every cursor
value is a ``created_at`` copied from a payload (never the clock), so a pass
with nothing new leaves state byte-identical. Two refinements (H1): a pass
over an explicit ``--since``/``--until`` range never moves a cursor FORWARD
past an incomplete run nor BACKWARD past the live cursor when it completes
(``max(old, newest)``); a budget stop sets the cursor to the stop point (the
run whose jobs GET was refused, or the window whose listing was) or the
oldest incomplete run before it, so the next pass lists exactly what is not
yet receipted. A workflow that listed no run keeps its cursor.

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

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from . import canonical, rawdoc
from .github import APIError, BudgetExhausted, Truncated
from .protocols import GitHubAPI
from .steps import STEP_GRAMMAR_VERSION, jobs_have_agent_step, suspicious_step_names

RECEIPT_FORMAT = "receipt@1"
SOURCE_LIVE = "live"

#: GitHub's result cap for a filtered runs list (critique item 8).
LIST_CAP = 1000
#: A window this short (seconds) that still hits the cap is not halved again: Truncated.
MIN_WINDOW_SECONDS = 60
#: Pages per listed window (100 rows each — never reached below the cap).
WINDOW_MAX_PAGES = 11

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
_TS_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_DAY_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, _TS_FMT).replace(tzinfo=timezone.utc)


def _fmt(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime(_TS_FMT)


def normalize_bound(value: str, *, end: bool) -> str:
    """A dispatch date bound as RFC3339 seconds: ``YYYY-MM-DD`` → that day's first (``end``
    False) or last (``end`` True) second; a full timestamp is returned as is."""
    if _TS_RE.fullmatch(value):
        return value
    if _DAY_RE.fullmatch(value):
        return value + ("T23:59:59Z" if end else "T00:00:00Z")
    raise ValueError(f"not a date or RFC3339 timestamp: {value!r}")


def receipt_path(run: dict[str, Any]) -> str:
    """``receipts/YYYY/MM/DD/<id>.a<attempt>.json.gz`` from a (projected or raw) run object."""
    run_id = run.get("id")
    created = run.get("created_at")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
        raise ValueError(f"run id {run_id!r}")
    if not isinstance(created, str) or not _TS_RE.fullmatch(created):
        raise ValueError(f"run {run_id}: created_at {created!r}")
    attempt = run.get("run_attempt") or 1
    y, m, d = created[:10].split("-")
    return f"receipts/{y}/{m}/{d}/{run_id}.a{int(attempt)}.json.gz"


def build_receipt(workflow: str, run: dict[str, Any], jobs: Optional[list[dict[str, Any]]],
                  source: str) -> dict[str, Any]:
    """The receipt@1 document (canonical JSON identical to tests/dev/build_fixtures.py's reference)."""
    jobs = sorted(jobs or [], key=lambda j: (j.get("run_attempt") or 0, j.get("id") or 0))
    full = jobs_have_agent_step(jobs) or bool(suspicious_step_names(jobs))
    return {
        "format": RECEIPT_FORMAT,
        "jobs": jobs if full else None,
        "jobs_sha256": canonical.content_sha256(jobs),
        "kind": "full" if full else "stub",
        "run": rawdoc.project_run(run),
        "source": source,
        "step_grammar": STEP_GRAMMAR_VERSION,
        "stub": None if full else {
            "jobs": [{"conclusion": j.get("conclusion"), "name": j.get("name"),
                      "run_attempt": j.get("run_attempt")} for j in jobs],
        },
        "suspicious_steps": suspicious_step_names(jobs),
        "workflow": workflow,
    }


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
    gone: int = 0


def run_windows(start: str, end: str) -> list[tuple[str, str]]:
    """UTC-day windows ``[(A, B)]`` covering ``[start, end]`` (RFC3339 seconds; ``B`` inclusive)."""
    a, z = _parse(start), _parse(end)
    out: list[tuple[str, str]] = []
    while a <= z:
        day_end = a.replace(hour=23, minute=59, second=59)
        b = min(day_end, z)
        out.append((_fmt(a), _fmt(b)))
        a = b + timedelta(seconds=1)
    return out


def _list_window(gh: GitHubAPI, workflow: str, a: datetime, b: datetime) -> list[dict[str, Any]]:
    """One ``created=A..B`` window, halved while capped; ``total_count`` asserted (retried once)."""
    path = f"/actions/workflows/{workflow}/runs"
    params = {"created": f"{_fmt(a)}..{_fmt(b)}"}
    for attempt in (1, 2):
        rows: list[dict[str, Any]] = []
        total: Optional[int] = None
        capped = False
        for items, page_total in gh.iter_pages(path, params, key="workflow_runs",
                                               max_pages=WINDOW_MAX_PAGES):
            if total is None:
                total = page_total
            if total is not None and total >= LIST_CAP:
                capped = True
                break
            rows.extend(items)
        if capped:
            span = int((b - a).total_seconds()) + 1
            if span <= MIN_WINDOW_SECONDS:
                raise Truncated(f"runs list {workflow} {params['created']}: {total} results in "
                                f"{span} s (GitHub caps a filtered list at {LIST_CAP})")
            mid = a + timedelta(seconds=(span - 1) // 2)
            return (_list_window(gh, workflow, a, mid)
                    + _list_window(gh, workflow, mid + timedelta(seconds=1), b))
        if total is None or len(rows) == total:
            return rows
    raise Truncated(f"runs list {workflow} {params['created']}: {len(rows)} rows, "
                    f"total_count {total} (twice)")


def list_runs(gh: GitHubAPI, workflow: str, created_from: str, created_to: str) -> list[dict[str, Any]]:
    """Every run created in ``[created_from, created_to]``: ``total_count`` asserted, halving on
    ``>= 1000`` (module docstring). Raises ``github.Truncated`` when a one-minute window still caps.

    Rows are de-duplicated by run id (first wins) and returned sorted by
    ``(created_at, id)``.
    """
    rows = _list_window(gh, workflow, _parse(created_from), _parse(created_to))
    seen: dict[int, dict[str, Any]] = {}
    for r in rows:
        seen.setdefault(r.get("id"), r)
    return sorted(seen.values(), key=lambda r: (r.get("created_at") or "", r.get("id") or 0))


def harvest_receipts(gh: GitHubAPI, *, workflows: tuple[str, ...], cursors: dict[str, str],
                     since: Optional[str], until: Optional[str], now: str, lookback_hours: int,
                     default_cursor: str, exists: Callable[[str], bool]) -> ReceiptPass:
    """One receipts pass (module docstring). ``exists(path)`` answers from the evidence tree.

    Catches ``github.BudgetExhausted``: returns what it has with
    ``budget_stopped=True`` and cursors that resume exactly where it stopped.
    ``since``/``until`` accept ``YYYY-MM-DD`` (a whole day) or RFC3339 seconds;
    ``end`` is clamped to ``now``. A jobs GET answered 404/410 (the run was
    deleted between listing and fetching) is counted in ``gone`` and skipped.
    """
    rp = ReceiptPass()
    explicit = bool(since or until)
    end = normalize_bound(until, end=True) if until else now
    if end > now:
        end = now
    lookback = timedelta(hours=lookback_hours)
    for wf in workflows:
        old = cursors.get(wf)
        base = normalize_bound(since, end=False) if since else (old or default_cursor)
        start = _fmt(_parse(base) - lookback)
        incomplete: list[str] = []
        newest: Optional[str] = None
        stop_at: Optional[str] = None
        try:
            for a, b in run_windows(start, end):
                stop_at = a
                runs = list_runs(gh, wf, a, b)
                rp.windows += 1
                rp.listed += len(runs)
                for run in runs:
                    created = run.get("created_at")
                    stop_at = created
                    if run.get("status") != "completed":
                        rp.in_progress += 1
                        incomplete.append(created)
                        continue
                    newest = created if newest is None or created > newest else newest
                    if run.get("conclusion") == "skipped":
                        rp.skipped_runs += 1
                        continue
                    path = receipt_path(run)
                    if path in rp.files or exists(path):
                        continue
                    try:
                        jobs = gh.get_paged(f"/actions/runs/{run['id']}/jobs", {"filter": "all"},
                                            key="jobs")
                    except APIError as exc:
                        if getattr(exc, "status", None) in (404, 410):
                            rp.gone += 1
                            continue
                        raise
                    doc = build_receipt(wf, run, jobs, SOURCE_LIVE)
                    rp.files[path] = canonical.dumps_gz(doc)
                    if doc["kind"] == "full":
                        rp.full += 1
                    else:
                        rp.stub += 1
                    for name in doc["suspicious_steps"]:
                        rp.suspicious[name] = rp.suspicious.get(name, 0) + 1
            stop_at = None
        except BudgetExhausted:
            rp.budget_stopped = True
        if rp.budget_stopped:
            resume = min([stop_at] + incomplete) if stop_at else (min(incomplete) if incomplete else None)
            # Stopped before anything of this workflow was listed: the cursor already says
            # where to start (re-setting it to the window start would walk it back a lookback).
            if resume is not None and not (resume == start and old is not None and not since):
                rp.cursors[wf] = resume
            break
        if incomplete:
            oldest = min(incomplete)
            rp.cursors[wf] = min(oldest, old) if (explicit and old) else oldest
        elif newest is not None:
            rp.cursors[wf] = max(newest, old) if (explicit and old) else newest
    return rp


def load_receipt(data: bytes) -> dict[str, Any]:
    """Parse one stored receipt (gzip canonical JSON). Shape validation is ``check``'s job
    (``contract.validate_tree``); the write path never calls the contract module."""
    return canonical.loads_gz(data)
