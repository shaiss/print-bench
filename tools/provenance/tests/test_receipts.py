"""receipts — runs-list selection, day windows, full vs stub, day-sharded paths (P0).

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md §Receipts, the critique round's items 8 and 19);
replace the skip with the test.
"""

from __future__ import annotations

import gzip
import json
import tarfile
from datetime import datetime, timedelta, timezone

import pytest

import conftest
from conftest import REPO
from fakes import FakeGitHub

from provenance import canonical, receipts
from provenance.github import APIError, BudgetExhausted, Truncated

RESCUE = REPO / "audits" / "provenance-2026-10" / "rescue"
TS = "%Y-%m-%dT%H:%M:%SZ"


def _ts(t: datetime) -> str:
    return t.strftime(TS)


def _snapshot_rows_and_jobs(run_ids: set[int]) -> tuple[dict[int, tuple[str, dict]], dict[int, list]]:
    """The committed #843 snapshot (main): the runs.tar row and jobs.tar jobs of ``run_ids``."""
    rows: dict[int, tuple[str, dict]] = {}
    with tarfile.open(RESCUE / "runs.tar") as tf:
        for m in tf.getmembers():
            wf = m.name[: -len(".json.gz")]
            for r in json.loads(gzip.decompress(tf.extractfile(m).read())):
                if r["id"] in run_ids:
                    rows[r["id"]] = (wf, r)
    jobs: dict[int, list] = {}
    with tarfile.open(RESCUE / "jobs.tar") as tf:
        names = set(tf.getnames())
        for rid in run_ids:
            name = f"{rid}.json.gz"
            if name in names:
                jobs[rid] = json.loads(gzip.decompress(tf.extractfile(name).read()))["jobs"]
    return rows, jobs


def test_build_receipt_matches_every_committed_fixture():
    """For every fixture receipt, receipts.build_receipt(workflow, run, jobs, source) reproduces the committed DOCUMENT: its canonical JSON equals the fixture's decompressed bytes (gzip bytes are storage only and may differ across zlib builds — critique 19)."""
    paths = conftest.receipt_paths()
    assert len(paths) == 166
    docs = {p: json.loads(gzip.decompress(p.read_bytes())) for p in paths}
    rows, jobs = _snapshot_rows_and_jobs({d["run"]["id"] for d in docs.values()})
    kinds = set()
    for p, doc in docs.items():
        rid = doc["run"]["id"]
        wf, row = rows[rid]
        assert wf == doc["workflow"]
        built = receipts.build_receipt(wf, row, jobs[rid], doc["source"])
        assert canonical.dumps_bytes(built) == gzip.decompress(p.read_bytes()), p.name
        assert p.relative_to(conftest.FIXTURES).as_posix() == receipts.receipt_path(row)
        kinds.add(built["kind"])
        if built["kind"] == "full":  # a stored full receipt rebuilds from itself (projection idempotent)
            assert receipts.build_receipt(wf, doc["run"], doc["jobs"], doc["source"]) == doc
    assert kinds == {"full", "stub"}
    # Negative control: a one-field change to a job is caught by the byte comparison.
    p = paths[0]
    doc = docs[p]
    rid = doc["run"]["id"]
    tampered = [dict(j, name=j["name"] + "x") for j in jobs[rid]]
    assert canonical.dumps_bytes(receipts.build_receipt(doc["workflow"], rows[rid][1], tampered, doc["source"])) \
        != gzip.decompress(p.read_bytes())


def test_pre_326_run_is_stored_complete():
    """Design-run run 31364447108 (2026-08-10; steps 'Run via Anthropic (Claude)' and 'Run via Z.AI (GLM)') is stored with its complete jobs response (kind full)."""
    rows, jobs = _snapshot_rows_and_jobs({31364447108})
    wf, row = rows[31364447108]
    doc = receipts.build_receipt(wf, row, jobs[31364447108], "snapshot:pr843")
    assert doc["kind"] == "full" and doc["stub"] is None
    assert doc["jobs"] == sorted(jobs[31364447108], key=lambda j: (j["run_attempt"], j["id"]))
    names = {s["name"] for j in doc["jobs"] for s in j["steps"]}
    assert {"Run via Anthropic (Claude)", "Run via Z.AI (GLM)"} <= names
    assert receipts.receipt_path(row) == "receipts/2026/08/10/31364447108.a1.json.gz"
    assert doc == conftest.receipt(31364447108)


def _job(jid, steps, attempt=1, conclusion="success", name="job"):
    return {"conclusion": conclusion, "id": jid, "name": name, "run_attempt": attempt,
            "steps": [{"conclusion": c, "name": n, "number": i + 1} for i, (n, c) in enumerate(steps)]}


def _run(rid, created, *, status="completed", conclusion="success", attempt=1, wf="design-run.yml"):
    return {"conclusion": conclusion if status == "completed" else None, "created_at": created,
            "display_title": "t", "event": "schedule", "head_branch": "main", "head_sha": "a" * 40,
            "html_url": f"https://github.com/shaiss/print-bench/actions/runs/{rid}", "id": rid, "name": wf,
            "path": f".github/workflows/{wf}", "pull_requests": [], "run_attempt": attempt, "run_number": 1,
            "run_started_at": created, "status": status, "updated_at": created}


def test_disarmed_run_is_a_stub():
    """A run whose only job that ran is 'Explain a disarmed run' is kind stub with jobs null and the stub job list; jobs_sha256 still digests the jobs."""
    jobs = [_job(2, [("Run via Z.AI (GLM, chain link 1)", "skipped"), ("Explain a disarmed run", "success")],
                 name="ship"),
            _job(1, [("Set up job", "success")], name="gate")]
    doc = receipts.build_receipt("design-run.yml", _run(9, "2026-10-12T01:02:03Z"), jobs, "live")
    assert doc["kind"] == "stub" and doc["jobs"] is None
    assert doc["stub"] == {"jobs": [{"conclusion": "success", "name": "gate", "run_attempt": 1},
                                    {"conclusion": "success", "name": "ship", "run_attempt": 1}]}
    assert doc["jobs_sha256"] == canonical.content_sha256(sorted(jobs, key=lambda j: (j["run_attempt"], j["id"])))
    assert doc["suspicious_steps"] == []
    # Controls: the same run with its link step RUN is full; an unparsed LLM-vocabulary step keeps it full.
    ran = [_job(2, [("Run via Z.AI (GLM, chain link 1)", "success")])]
    assert receipts.build_receipt("design-run.yml", _run(9, "2026-10-12T01:02:03Z"), ran, "live")["kind"] == "full"
    odd = [_job(2, [("Ask Claude nicely", "success")])]
    full = receipts.build_receipt("design-run.yml", _run(9, "2026-10-12T01:02:03Z"), odd, "live")
    assert full["kind"] == "full" and full["suspicious_steps"] == ["Ask Claude nicely"]


def test_receipt_path_is_day_sharded_with_attempt():
    """receipts/YYYY/MM/DD/<id>.a<attempt>.json.gz from run.created_at (UTC)."""
    assert receipts.receipt_path(_run(7, "2026-09-12T00:23:08Z", attempt=2)) == "receipts/2026/09/12/7.a2.json.gz"
    assert receipts.receipt_path({"id": 7, "created_at": "2026-12-31T23:59:59Z"}) == "receipts/2026/12/31/7.a1.json.gz"
    for bad in ({"id": "7", "created_at": "2026-09-12T00:23:08Z"}, {"id": 7, "created_at": "2026-09-12"},
                {"id": True, "created_at": "2026-09-12T00:23:08Z"}, {"id": 7}):
        with pytest.raises(ValueError):
            receipts.receipt_path(bad)


class _Runs:
    """A responder serving ``/actions/workflows/<wf>/runs?created=A..B`` from a table, honouring
    GitHub's 1,000-result cap; ``/actions/runs/<id>/jobs`` from a jobs table."""

    def __init__(self, table: dict[str, list[dict]], jobs: dict[int, list] | None = None, *,
                 lie: bool = False) -> None:
        self.table, self.jobs, self.lie = table, jobs or {}, lie

    def __call__(self, path: str, params: dict):
        if path.endswith("/jobs"):
            rid = int(path.split("/")[3])
            if rid not in self.jobs:
                raise APIError("HTTP 404 GET jobs", status=404)
            return {"jobs": self.jobs[rid]}
        assert set(params) == {"created"}, params           # no other filter, ever
        wf = path.split("/")[3]
        a, _, b = params["created"].partition("..")
        rows = [r for r in self.table.get(wf, []) if a <= r["created_at"] <= b]
        return {"total_count": len(rows) + (1 if self.lie else 0), "workflow_runs": rows[:1000]}


def test_selection_is_by_runs_list_not_step_name():
    """Every completed, non-skipped watched run without a receipt gets one jobs GET; skipped runs get none; in-progress runs are left for the next pass and hold the cursor back."""
    rows = [_run(1, "2026-10-12T01:00:00Z"), _run(2, "2026-10-12T02:00:00Z", conclusion="skipped"),
            _run(3, "2026-10-12T03:00:00Z", status="in_progress"), _run(4, "2026-10-12T04:00:00Z"),
            _run(5, "2026-10-12T05:00:00Z", conclusion="failure"), _run(6, "2026-10-12T06:00:00Z", status="queued")]
    jobs = {rid: [_job(rid * 10, [("Explain an empty selection", "success")])] for rid in range(1, 7)}
    fake = FakeGitHub(responder=_Runs({"design-run.yml": rows}, jobs))
    have = {receipts.receipt_path(rows[3])}  # run 4 already receipted
    rp = receipts.harvest_receipts(fake, workflows=("design-run.yml",), cursors={"design-run.yml": "2026-10-12T00:00:00Z"},
                                   since=None, until=None, now="2026-10-12T12:00:00Z", lookback_hours=48,
                                   default_cursor="2026-07-31T00:00:00Z", exists=have.__contains__)
    gets = [p for p, _ in fake.calls if p.endswith("/jobs")]
    assert gets == ["/actions/runs/1/jobs", "/actions/runs/5/jobs"]
    assert sorted(rp.files) == [receipts.receipt_path(rows[0]), receipts.receipt_path(rows[4])]
    assert rp.skipped_runs == 1 and rp.in_progress == 2 and rp.stub == 2 and rp.listed == 6
    assert rp.cursors == {"design-run.yml": "2026-10-12T03:00:00Z"}     # the oldest incomplete run
    doc = receipts.load_receipt(rp.files[receipts.receipt_path(rows[0])])
    assert doc["source"] == "live" and doc["run"]["id"] == 1
    # Once everything completed, the cursor is the newest completed run's created_at (data, not clock).
    for r in rows:
        if r["status"] != "completed":
            r.update(status="completed", conclusion="success")
    rp2 = receipts.harvest_receipts(fake, workflows=("design-run.yml",), cursors=rp.cursors, since=None, until=None,
                                    now="2026-10-12T13:00:00Z", lookback_hours=48,
                                    default_cursor="2026-07-31T00:00:00Z",
                                    exists=lambda p: p in have or p in rp.files)
    assert sorted(rp2.files) == [receipts.receipt_path(rows[2]), receipts.receipt_path(rows[5])]
    assert rp2.cursors == {"design-run.yml": "2026-10-12T06:00:00Z"}
    # A run deleted between listing and its jobs GET (404) is skipped, not fatal.
    rows.append(_run(7, "2026-10-12T07:00:00Z"))
    rp3 = receipts.harvest_receipts(fake, workflows=("design-run.yml",), cursors=rp2.cursors, since=None, until=None,
                                    now="2026-10-12T13:00:00Z", lookback_hours=48,
                                    default_cursor="2026-07-31T00:00:00Z",
                                    exists=lambda p: p in have or p in rp.files or p in rp2.files)
    assert rp3.gone == 1 and rp3.files == {}


def test_windows_halve_at_the_1000_cap():
    """Critique 8: a FakeGitHub responder that answers any created=A..B window holding more than 1,000 runs with total_count >= 1000 and only the first 1,000 rows: list_runs halves until every window is under the cap, returns all 2,500 runs exactly once, and only ever sends the created filter; a window whose rows != total_count is retried once then raises Truncated; a one-minute window still capped raises Truncated."""
    t0 = datetime(2026, 10, 12, tzinfo=timezone.utc)
    rows = [_run(10_000 + i, _ts(t0 + timedelta(seconds=30 * i)), wf="auto-review.yml") for i in range(2500)]
    fake = FakeGitHub(responder=_Runs({"auto-review.yml": rows}))
    got = receipts.list_runs(fake, "auto-review.yml", "2026-10-12T00:00:00Z", "2026-10-12T23:59:59Z")
    assert [r["id"] for r in got] == [r["id"] for r in rows]          # all 2,500, once, in order
    assert all(set(p) == {"created", "page"} for _, p in fake.calls)   # only the created filter
    windows = [p["created"].split("..") for _, p in fake.calls]
    count = {tuple(w): sum(1 for r in rows if w[0] <= r["created_at"] <= w[1]) for w in windows}
    assert windows[0] == ["2026-10-12T00:00:00Z", "2026-10-12T23:59:59Z"] and count[tuple(windows[0])] >= 1000
    accepted = sorted(w for w in map(tuple, windows) if count[w] < 1000)
    assert sum(count[w] for w in accepted) == 2500                     # the accepted windows partition the day
    for (_, b), (a, _) in zip(accepted, accepted[1:]):
        assert datetime.strptime(a, TS) - datetime.strptime(b, TS) == timedelta(seconds=1)

    # rows != total_count: retried once, then Truncated (two GETs of the same window).
    liar = FakeGitHub(responder=_Runs({"auto-review.yml": rows[:10]}, lie=True))
    with pytest.raises(Truncated):
        receipts.list_runs(liar, "auto-review.yml", "2026-10-12T00:00:00Z", "2026-10-12T23:59:59Z")
    assert len(liar.calls) == 2 and liar.calls[0][1] == liar.calls[1][1]

    # A one-minute window that still holds >= 1,000 runs cannot be halved further.
    burst = [_run(50_000 + i, "2026-10-12T06:00:30Z", wf="auto-review.yml") for i in range(1001)]
    capped = FakeGitHub(responder=_Runs({"auto-review.yml": burst}))
    with pytest.raises(Truncated, match="GitHub caps"):
        receipts.list_runs(capped, "auto-review.yml", "2026-10-12T00:00:00Z", "2026-10-12T23:59:59Z")


def test_run_windows_are_utc_days():
    """run_windows('2026-10-11T06:13:35Z', '2026-10-13T00:00:00Z') → three windows split at UTC midnight, contiguous, inclusive bounds, none past the end."""
    w = receipts.run_windows("2026-10-11T06:13:35Z", "2026-10-13T00:00:00Z")
    assert w == [("2026-10-11T06:13:35Z", "2026-10-11T23:59:59Z"),
                 ("2026-10-12T00:00:00Z", "2026-10-12T23:59:59Z"),
                 ("2026-10-13T00:00:00Z", "2026-10-13T00:00:00Z")]
    for (_, b), (a, _) in zip(w, w[1:]):
        assert datetime.strptime(a, TS) - datetime.strptime(b, TS) == timedelta(seconds=1)
    assert receipts.run_windows("2026-10-11T05:00:00Z", "2026-10-11T04:00:00Z") == []
    assert receipts.run_windows("2026-10-11T05:00:00Z", "2026-10-11T05:00:00Z") == [("2026-10-11T05:00:00Z",) * 2]


def _table(n: int):
    t0 = datetime(2026, 10, 11, tzinfo=timezone.utc)
    rows = [_run(100 + i, _ts(t0 + timedelta(hours=3 * i))) for i in range(n)]
    jobs = {r["id"]: [_job(r["id"] * 10, [("Run via Z.AI (GLM, chain link 1)", "success")])] for r in rows}
    return rows, jobs


def test_budget_stop_resumes_from_cursor():
    """BudgetExhausted mid-pass returns budget_stopped=True and cursors that, on the next pass with a fresh budget, list exactly the runs not yet receipted."""
    rows, jobs = _table(12)  # 2026-10-11T00:00 → 10-12T09:00, every 3 h
    kw = dict(workflows=("design-run.yml",), since=None, until=None, now="2026-10-12T12:00:00Z", lookback_hours=48,
              default_cursor="2026-07-31T00:00:00Z")
    cursors = {"design-run.yml": "2026-10-11T00:00:00Z"}
    stopped = FakeGitHub(responder=_Runs({"design-run.yml": rows}, jobs), budget=7, exhausted_with=BudgetExhausted)
    rp1 = receipts.harvest_receipts(stopped, cursors=cursors, exists=lambda p: False, **kw)
    assert rp1.budget_stopped and 0 < len(rp1.files) < 12
    stop_cursor = rp1.cursors["design-run.yml"]
    first_missing = min(r["created_at"] for r in rows if receipts.receipt_path(r) not in rp1.files)
    assert stop_cursor == first_missing
    fresh = FakeGitHub(responder=_Runs({"design-run.yml": rows}, jobs))
    rp2 = receipts.harvest_receipts(fresh, cursors=rp1.cursors, exists=rp1.files.__contains__, **kw)
    assert not rp2.budget_stopped
    jobs_gets = {int(p.split("/")[3]) for p, _ in fresh.calls if p.endswith("/jobs")}
    assert jobs_gets == {r["id"] for r in rows if receipts.receipt_path(r) not in rp1.files}
    assert set(rp1.files) | set(rp2.files) == {receipts.receipt_path(r) for r in rows}
    assert not set(rp1.files) & set(rp2.files)
    # A stop before anything of a workflow was listed keeps its cursor (no walk-back by the lookback).
    zero = FakeGitHub(responder=_Runs({"design-run.yml": rows}, jobs), budget=0, exhausted_with=BudgetExhausted)
    rp0 = receipts.harvest_receipts(zero, cursors=cursors, exists=lambda p: False, **kw)
    assert rp0.budget_stopped and rp0.cursors == {}


def test_cap_of_five_stops_and_resumes_with_the_real_client():
    """P1e 'a request cap of 5 stops cleanly' — with the production github.Client (a canned
    transport, no network): each pass spends at most 5 requests, stops with budget_stopped, and the
    next pass resumes from its cursor until every run is receipted exactly once."""
    from urllib.parse import parse_qs, urlsplit

    from provenance import github

    rows, jobs = _table(8)

    def transport(method, url, headers, body):
        parts = urlsplit(url)
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        segs = parts.path.split("/")
        if parts.path.endswith("/jobs"):
            payload = {"jobs": jobs[int(segs[-2])], "total_count": 1}
        else:
            a, _, b = q["created"].partition("..")
            hit = [r for r in rows if a <= r["created_at"] <= b]
            payload = {"total_count": len(hit), "workflow_runs": hit}
        return 200, {"X-RateLimit-Remaining": "4000"}, json.dumps(payload).encode()

    have: dict[str, bytes] = {}
    cursors = {"design-run.yml": "2026-10-11T00:00:00Z"}
    passes = 0
    while True:
        passes += 1
        assert passes < 20
        gh = github.Client(repo="shaiss/print-bench", token="", transport=transport, sleep=lambda s: None,
                           budget=github.Budget(max_requests=5, floor=500, pace=False))
        rp = receipts.harvest_receipts(gh, workflows=("design-run.yml",), cursors=cursors, since=None, until=None,
                                       now="2026-10-12T12:00:00Z", lookback_hours=48,
                                       default_cursor="2026-07-31T00:00:00Z", exists=have.__contains__)
        assert gh.budget.used <= 5
        assert not set(rp.files) & set(have)
        have.update(rp.files)
        cursors.update(rp.cursors)
        if not rp.budget_stopped:
            break
    assert passes > 2 and set(have) == {receipts.receipt_path(r) for r in rows}


def test_receipt_count_equals_non_skipped_runs():
    """Over a FakeGitHub runs list, the pass's full+stub count equals the non-skipped completed runs listed (the shape of the P2 live check, which compares snapshot rows ∪ the windowed live listing)."""
    rows, jobs = _table(10)
    rows[2]["conclusion"] = "skipped"
    rows[5]["conclusion"] = "cancelled"
    rows[7]["status"], rows[7]["conclusion"] = "in_progress", None
    other, other_jobs = _table(3)
    for r in other:
        r["id"] += 1000
        r["path"] = ".github/workflows/oracle.yml"
    jobs.update({r["id"]: other_jobs[r["id"] - 1000] for r in other})
    fake = FakeGitHub(responder=_Runs({"design-run.yml": rows, "oracle.yml": other}, jobs))
    rp = receipts.harvest_receipts(fake, workflows=("design-run.yml", "oracle.yml"), cursors={}, since="2026-10-11",
                                   until=None, now="2026-10-13T00:00:00Z", lookback_hours=48,
                                   default_cursor="2026-07-31T00:00:00Z", exists=lambda p: False)
    listed = rows + other
    expected = [r for r in listed if r["status"] == "completed" and r["conclusion"] != "skipped"]
    assert rp.full + rp.stub == len(rp.files) == len(expected) == 11
    assert rp.listed == len(listed) and rp.in_progress == 1 and rp.skipped_runs == 1
    assert rp.cursors["design-run.yml"] == rows[7]["created_at"]
    assert rp.cursors["oracle.yml"] == other[-1]["created_at"]


def test_explicit_range_never_moves_a_cursor_backward():
    """H1 refinement: a dispatch over an explicit since/until range never walks the live cursor back
    (it may only hold it at an incomplete run)."""
    rows, jobs = _table(4)  # 10-11T00, 03, 06, 09
    fake = FakeGitHub(responder=_Runs({"design-run.yml": rows}, jobs))
    live = "2026-10-12T12:00:00Z"
    rp = receipts.harvest_receipts(fake, workflows=("design-run.yml",), cursors={"design-run.yml": live},
                                   since="2026-10-11", until="2026-10-11", now="2026-10-13T00:00:00Z",
                                   lookback_hours=48, default_cursor="2026-07-31T00:00:00Z", exists=lambda p: False)
    assert len(rp.files) == 4 and rp.cursors == {"design-run.yml": live}
    windows = [p["created"] for p_, p in fake.calls if "created" in p]
    assert windows[-1].endswith("..2026-10-11T23:59:59Z")        # until is the day's last second
    with pytest.raises(ValueError):
        receipts.normalize_bound("2026/10/11", end=False)
