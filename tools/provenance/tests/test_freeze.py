"""freeze — settle/defer/re-capture/refreeze (P1e).

Owner: H6. Every GitHub answer here is SYNTHETIC (invented short REST shapes
served by ``fakes.FakeGitHub``); the real-capture parity — the scratch GET
capture fed through ``capture_pr`` reproduces ``fixtures/raw/pr/<n>.json.gz``
on every key but ``statuses`` (and ``threads.source``) — is a dev-only check
that never runs in CI (WORKPLAN H6). The acceptance criteria are the
docstrings (docs/provenance.md, the critique round's items 10, 11, 24).
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from conftest import REPO, needs
from fakes import FakeGitHub
from provenance import canonical, conf, contract, episodes, freeze, state
from provenance.github import APIError, BudgetExhausted

CONF = conf.load(str(REPO / ".github" / "provenance.conf"))
T0 = "2026-10-10T12:00:00Z"   # the scenario PR closes (merges) here
BASE_SHA = "b0" * 20
C1, C2, MERGE = "c1" * 20, "c2" * 20, "e7" * 20
N, BRIEF = 900, 901
N2 = 905   # a second, healthy design PR (the per-unit isolation tests)


def at(hours: float, base: str = T0) -> str:
    t = datetime.fromisoformat(base.replace("Z", "+00:00")) + timedelta(hours=hours)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_state() -> dict:
    return {"format": "state@1",
            "versions": {"harvester": "provenance 0.1.0", "digest": "body-digest@1",
                         "step_grammar": 1, "contract": 1},
            "cursors": {"receipts": {}, "prs_updated": None, "briefs_updated": None,
                        "releases_published": None},
            "pending": {"pr": {}, "brief": {}}, "skipped": {"pr": {}}, "ingested": {}}


# --- synthetic REST shapes ---------------------------------------------------

USER = {"login": "shaiss", "type": "User"}


def rest_pull(n=N, *, closed_at=T0, merged_at=T0, head_ref="claude/issue-901-widget",
              head_sha=C2, merge_sha=MERGE, commits=2, changed_files=1,
              body="Ships the widget.\n\nCloses #901", state_="closed", updated_at=None):
    return {"number": n, "state": state_, "title": f"Add design: widget {n}", "body": body,
            "draft": False, "created_at": "2026-10-09T00:00:00Z",
            "updated_at": updated_at or closed_at, "closed_at": closed_at, "merged_at": merged_at,
            "merged": merged_at is not None, "merge_commit_sha": merge_sha if merged_at else None,
            "user": USER, "merged_by": USER if merged_at else None,
            "head": {"ref": head_ref, "sha": head_sha, "repo": {"full_name": "shaiss/print-bench"}},
            "base": {"ref": "main", "sha": BASE_SHA}, "labels": [{"name": "design"}],
            "commits": commits, "changed_files": changed_files}


def rest_commit(sha, parent, date):
    ident = {"name": "Claude", "email": "noreply@anthropic.com", "date": date}
    return {"sha": sha, "parents": [{"sha": parent}], "author": USER, "committer": USER,
            "commit": {"author": ident, "committer": ident, "message": "Add design: widget",
                       "verification": {"verified": False, "reason": "unsigned"}}}


def rest_run(run_id, head_sha, created, *, prs=(N,), branch="claude/issue-901-widget",
             status="completed", conclusion="success", path=".github/workflows/ci.yml"):
    return {"id": run_id, "name": "CI", "path": path, "event": "pull_request", "status": status,
            "conclusion": conclusion, "head_branch": branch, "head_sha": head_sha,
            "created_at": created, "updated_at": created, "run_started_at": created,
            "run_attempt": 1, "run_number": run_id,
            "html_url": f"https://github.com/shaiss/print-bench/actions/runs/{run_id}",
            "display_title": "Add design: widget", "actor": USER, "triggering_actor": USER,
            "pull_requests": [{"number": p} for p in prs]}


def rest_status(status_id, context, created, state_="success"):
    return {"id": status_id, "context": context, "state": state_, "created_at": created,
            "updated_at": created, "creator": {"login": "github-actions[bot]", "type": "Bot"},
            "description": "Jane + Drik signed off", "target_url": "https://example.invalid/x"}


def rest_issue(n=BRIEF, *, state_="closed", closed_at=T0, labels=("design-brief",)):
    return {"number": n, "state": state_, "state_reason": "completed" if state_ == "closed" else None,
            "title": f"Design brief: widget {n}", "body": "**Design name:** widget\n",
            "created_at": "2026-10-01T00:00:00Z", "updated_at": closed_at or "2026-10-01T00:00:00Z",
            "closed_at": closed_at if state_ == "closed" else None, "user": USER,
            "labels": [{"name": x} for x in labels]}


class World:
    """Synthetic GitHub keyed by path — params ignored, one scenario per world — plus
    ``refuse(path, status)``: that path raises ``APIError`` with ``status`` (``get`` and
    ``get_paged`` alike), the shape of a GitHub refusal after the client's retries."""

    def __init__(self) -> None:
        self.by_path: dict[str, object] = {}
        self.refused: dict[str, object] = {}

    def set(self, path, value):
        self.by_path[path] = value
        return self

    def refuse(self, path, status=422):
        self.refused[path] = status
        return self

    def _answer(self, path, params):
        if path in self.refused:
            raise api_error(f"HTTP {self.refused[path]} GET {path}", self.refused[path])
        return copy.deepcopy(self.by_path.get(path))

    def fake(self, **kw) -> FakeGitHub:
        # GraphQL answers by default (no review threads); pass threads={} for a refusal.
        kw.setdefault("threads", {n: {"nodes": [], "last_edited_at": None} for n in (N, N2)})
        return FakeGitHub(responder=self._answer, **kw)


_ORIGINAL_VALIDATE = contract.validate


def _ready() -> bool:
    try:
        _ORIGINAL_VALIDATE("raw-release@1", {})
    except NotImplementedError:
        return False
    return True


_VALIDATOR_READY = _ready()


def _base_validate(shape, value, c=None):
    """H2's validator once it lands; until then every document is admitted."""
    return _ORIGINAL_VALIDATE(shape, value) if _VALIDATOR_READY else []


def api_error(message: str, status) -> APIError:
    """An ``APIError`` carrying ``status`` (H1's attribute; set by hand so this also builds
    against the scaffold's bare exception)."""
    exc = APIError(message)
    exc.status = status
    return exc


@pytest.fixture(autouse=True)
def _contract_until_integration(monkeypatch):
    """Admission (freeze's contract check) needs H2's validator. Until it lands every document
    is admitted, so the capture tests run now; from integration on the REAL validator judges
    every document these tests plan (``test_captured_documents_satisfy_the_contract`` and the
    ``@needs`` rows assert it directly)."""
    if not _VALIDATOR_READY:
        monkeypatch.setattr(freeze.contract, "validate", _base_validate)


def pr_world(*, closed_at=T0, merged=True, files=("designs/widget/widget.scad",),
             in_flight=(), deploy_state="success", body="Ships the widget.\n\nCloses #901",
             brief=True, brief_labels=("design-brief",), brief_timeline=(), runs=None,
             statuses=None, deployments=True) -> World:
    merged_at = closed_at if merged else None
    pull = rest_pull(closed_at=closed_at, merged_at=merged_at, body=body)
    w = World()
    w.set("/pulls", [pull]).set(f"/pulls/{N}", pull)
    w.set(f"/pulls/{N}/files", [{"filename": f, "status": "added", "patch": "@@"} for f in files])
    w.set(f"/pulls/{N}/commits", [rest_commit(C1, BASE_SHA, at(-30, closed_at)),
                                  rest_commit(C2, C1, at(-10, closed_at))])
    for p in (f"/issues/{N}/comments", f"/pulls/{N}/reviews", f"/pulls/{N}/comments",
              f"/issues/{N}/timeline"):
        w.set(p, [])
    if runs is None:
        runs = [rest_run(101, C1, at(-30, closed_at)), rest_run(102, C2, at(-10, closed_at))]
    w.set("/actions/workflows/ci.yml/runs", {"total_count": len(runs), "workflow_runs": runs})
    if statuses is None:
        statuses = {C1: [rest_status(11, "Vercel", at(-30, closed_at))],
                    C2: [rest_status(12, "reviewer-signoff", at(-9, closed_at))]}
    for sha, rows in statuses.items():
        w.set(f"/commits/{sha}/statuses", rows)
    if merged and deployments:
        w.set("/deployments", [{"id": 7, "sha": MERGE, "ref": "main", "environment": "Production",
                                "created_at": at(0.1, closed_at), "creator": USER}])
        w.set("/deployments/7/statuses", [{"id": 70, "state": deploy_state,
                                           "created_at": at(0.2, closed_at), "creator": USER}])
    w.set("/actions/runs", {"total_count": len(in_flight), "workflow_runs": list(in_flight)})
    if brief:
        w.set(f"/issues/{BRIEF}", rest_issue(labels=brief_labels))
        w.set(f"/issues/{BRIEF}/timeline", list(brief_timeline))
        w.set(f"/issues/{BRIEF}/comments", [])
    w.set("/releases", []).set("/issues", [])
    return w


def add_pr(w: World, n: int, *, closed_at=T0, files=("designs/gadget/gadget.scad",)) -> World:
    """A second closed, merged design PR in ``w`` (same commits, runs and statuses as #N — the
    capture filters runs by head sha — and no linked issue), listed AFTER the scenario PR."""
    pull = rest_pull(n=n, closed_at=closed_at, head_ref=f"claude/gadget-{n}", body="Ships a gadget.")
    w.set("/pulls", list(w.by_path.get("/pulls") or []) + [pull]).set(f"/pulls/{n}", pull)
    w.set(f"/pulls/{n}/files", [{"filename": f, "status": "added", "patch": "@@"} for f in files])
    w.set(f"/pulls/{n}/commits", [rest_commit(C1, BASE_SHA, at(-30, closed_at)),
                                  rest_commit(C2, C1, at(-10, closed_at))])
    for p in (f"/issues/{n}/comments", f"/pulls/{n}/reviews", f"/pulls/{n}/comments",
              f"/issues/{n}/timeline"):
        w.set(p, [])
    return w


def tree(files: dict) -> object:
    return lambda path: files.get(path)


def plan(gh, *, now, st=None, frozen=None, files=None, **kw):
    return freeze.plan_freezes(gh, state=st or empty_state(), frozen=frozen or {}, conf=CONF,
                               now=now, read=tree(files or {}), **kw)


def doc_of(p, path):
    return canonical.loads_gz(p.files[path])


def calls_to(gh, path):
    return [c for c in gh.calls if c[0] == path]


# --- raw_path / settle (pure) ------------------------------------------------

def test_raw_path_revisions_and_refusals():
    assert freeze.raw_path("pr", "636", 1) == "raw/pr/636.json.gz"
    assert freeze.raw_path("pr", 636, 2) == "raw/pr/636.r2.json.gz"
    assert freeze.raw_path("brief", "592", 3) == "raw/brief/592.r3.json.gz"
    assert freeze.raw_path("release", "v2.0", 1) == "raw/release/v2.0.json.gz"
    for kind, key, rev in (("pr", "0", 1), ("pr", "6a", 1), ("pr", "636", 0), ("pr", "636", True),
                           ("release", "..", 1), ("release", "../x", 1), ("release", ".hidden", 1),
                           ("release", "a/b", 1), ("record", "1", 1), ("brief", "-1", 1)):
        with pytest.raises(ValueError):
            freeze.raw_path(kind, key, rev)


def _settle(now, **kw):
    args = dict(closed_at=T0, merged_at=T0, in_flight_runs=0, deployment_terminal=True, now=now,
                settle_hours=6, max_defer_hours=24, deploy_wait_hours=2)
    args.update(kw)
    return freeze.settle_pr(**args)


def test_settle_pr_table():
    s = _settle(at(2))
    assert (s.action, s.due_at, s.defer_until, s.reasons, s.incomplete) == (
        "pending", at(6), at(24), (), ())
    assert _settle(at(6)).action == "freeze"                       # due is inclusive
    assert _settle(at(7), in_flight_runs=1).reasons == ("in-flight-run",)
    assert _settle(at(7), in_flight_runs=1).action == "defer"
    forced = _settle(at(24), in_flight_runs=2)
    assert (forced.action, forced.incomplete) == ("freeze", ("settle-deferred",))
    unmerged = _settle(at(7), merged_at=None, deployment_terminal=None)
    assert (unmerged.action, unmerged.incomplete) == ("freeze", ())


def test_settle_brief_table():
    kw = dict(now=at(7), settle_hours=6, max_defer_hours=24)
    assert freeze.settle_brief(state="closed", closed_at=T0, linked_by_frozen_pr=False, **kw).action == "freeze"
    early = freeze.settle_brief(state="closed", closed_at=T0, linked_by_frozen_pr=True,
                                now=at(1), settle_hours=6, max_defer_hours=24)
    assert (early.action, early.due_at) == ("pending", at(6))
    open_linked = freeze.settle_brief(state="open", closed_at=None, linked_by_frozen_pr=True, **kw)
    assert (open_linked.action, open_linked.incomplete) == ("freeze", ("brief-open",))
    open_alone = freeze.settle_brief(state="open", closed_at=None, linked_by_frozen_pr=False, **kw)
    assert (open_alone.action, open_alone.due_at) == ("pending", "")   # not recorded by the pass


# --- the acceptance criteria --------------------------------------------------

def test_pr_merged_2h_ago_is_pending():
    """A PR merged 2 h ago lands in state.pending with due_at = closed_at + 6 h, not in raw/."""
    gh = pr_world().fake()
    p = plan(gh, now=at(2))
    assert p.files == {} and p.frozen == []
    assert p.pending["pr"][str(N)] == {"closed_at": T0, "due_at": at(6), "defer_until": at(24),
                                       "reasons": []}
    # Not due: no settle GETs (in-flight runs, deployments) and no capture.
    assert calls_to(gh, "/actions/runs") == [] and calls_to(gh, "/deployments") == []
    assert calls_to(gh, f"/pulls/{N}") == [] and calls_to(gh, f"/pulls/{N}/commits") == []
    assert p.cursors["prs_updated"] == T0


def test_pr_at_7h_freezes():
    """The same PR at 7 h freezes to raw/pr/<n>.json.gz."""
    gh = pr_world().fake()
    p = plan(gh, now=at(7))
    path = f"raw/pr/{N}.json.gz"
    assert path in p.files and ("pr", str(N), 1) in p.frozen
    assert str(N) not in p.pending["pr"]
    d = doc_of(p, path)
    assert (d["format"], d["pr"], d["revision"], d["incomplete"]) == ("raw-pr@1", N, 1, [])
    assert d["captured"] == {"digest": "body-digest@1", "harvester": "provenance 0.1.0", "run_id": 0}
    assert d["linked_issues"] == [BRIEF]
    assert [c["sha"] for c in d["commits"]] == [C1, C2]
    assert [r["id"] for r in d["ci_runs"]] == [101, 102]
    assert [x["id"] for x in d["deployments"]] == [7]
    assert d["threads"] == {"nodes": [], "pr_last_edited_at": None, "source": "graphql", "total": 0}
    assert "patch" not in d["files"][0]                                # a closed projection
    # The files listing read for the designs/ check is reused by the capture (one GET).
    assert len(calls_to(gh, f"/pulls/{N}/files")) == 1
    # The linked brief (closed at merge, settled) froze with its PR, as one unit.
    assert ("brief", str(BRIEF), 1) in p.frozen and f"raw/brief/{BRIEF}.json.gz" in p.files


def test_captured_records_the_run_and_graphql_threads():
    gh = pr_world().fake(threads={N: {"nodes": [{"first_comment_id": 5, "resolved": True,
                                                  "outdated": False}],
                                       "last_edited_at": "2026-10-09T01:00:00Z"}})
    d = doc_of(plan(gh, now=at(7), run_id=4242), f"raw/pr/{N}.json.gz")
    assert d["captured"]["run_id"] == 4242
    assert d["threads"]["total"] == 1 and d["threads"]["source"] == "graphql"
    assert d["threads"]["pr_last_edited_at"] == "2026-10-09T01:00:00Z"
    assert "graphql-unavailable" not in d["incomplete"]


def test_graphql_unavailable_is_recorded():
    # FakeGitHub with no threads raises GraphQLUnavailable (the sandbox's 403).
    d = doc_of(plan(pr_world().fake(threads={}), now=at(7)), f"raw/pr/{N}.json.gz")
    assert d["incomplete"] == ["graphql-unavailable"]
    assert d["threads"] == {"nodes": [], "pr_last_edited_at": None, "source": "graphql", "total": 0}
    b = doc_of(plan(pr_world().fake(threads={}), now=at(7)), f"raw/brief/{BRIEF}.json.gz")
    assert b["incomplete"] == []        # FakeGitHub's issue lastEditedAt answers (None)

    class NoIssueGraphQL(FakeGitHub):
        def graphql_issue_edited(self, number):
            from provenance.github import GraphQLUnavailable
            raise GraphQLUnavailable("403")

    w = pr_world()
    gh = NoIssueGraphQL(responder=lambda path, params: copy.deepcopy(w.by_path.get(path)))
    brief = freeze.capture_brief(gh, BRIEF, revision=1,
                                 captured={"run_id": 0, "harvester": "t", "digest": "body-digest@1"})
    assert brief["incomplete"] == ["graphql-unavailable"] and brief["issue"]["last_edited_at"] is None


def test_in_flight_run_defers_then_forces():
    """One with an in-flight watched run defers; at 24 h it freezes with incomplete ['settle-deferred']."""
    flying = [rest_run(555, C2, at(6.5), status="in_progress", conclusion=None,
                       path=".github/workflows/auto-review.yml")]
    p7 = plan(pr_world(in_flight=flying).fake(), now=at(7))
    assert p7.files == {}
    assert p7.pending["pr"][str(N)]["reasons"] == ["in-flight-run"]
    for status in ("queued", "pending", "waiting", "requested"):
        run = dict(flying[0], status=status)
        assert plan(pr_world(in_flight=[run]).fake(), now=at(7)).files == {}, status
    p24 = plan(pr_world(in_flight=flying).fake(), now=at(24))
    d = doc_of(p24, f"raw/pr/{N}.json.gz")
    assert d["incomplete"] == ["settle-deferred"]
    # Negative controls: an in-flight run of an UNWATCHED workflow, or a completed watched run,
    # does not defer.
    other = [dict(flying[0], path=".github/workflows/ci.yml")]
    assert f"raw/pr/{N}.json.gz" in plan(pr_world(in_flight=other).fake(), now=at(7)).files
    done = [dict(flying[0], status="completed", conclusion="success")]
    assert f"raw/pr/{N}.json.gz" in plan(pr_world(in_flight=done).fake(), now=at(7)).files


def test_deployment_wait():
    """A merged PR whose Production deployment is not terminal waits up to deploy_wait_hours, then freezes with incomplete deployment-not-terminal."""
    kw = dict(deployment_terminal=False, settle_hours=1, deploy_wait_hours=2)
    waiting = _settle(at(1.5), **kw)
    assert (waiting.action, waiting.reasons) == ("defer", ("deployment-pending",))
    out = _settle(at(2), **kw)
    assert (out.action, out.incomplete) == ("freeze", ("deployment-not-terminal",))
    assert _settle(at(1.5), deployment_terminal=True, settle_hours=1).incomplete == ()
    # Through the pass (decision-9 values: due at 6 h > the 2 h wait): an in-progress
    # deployment freezes at due with the reason; a successful one freezes clean.
    stuck = doc_of(plan(pr_world(deploy_state="in_progress").fake(), now=at(7)), f"raw/pr/{N}.json.gz")
    assert stuck["incomplete"] == ["deployment-not-terminal"]
    clean = doc_of(plan(pr_world(deploy_state="success").fake(), now=at(7)), f"raw/pr/{N}.json.gz")
    assert clean["incomplete"] == []
    none = doc_of(plan(pr_world(deployments=False).fake(), now=at(7)), f"raw/pr/{N}.json.gz")
    assert none["incomplete"] == ["deployment-not-terminal"] and none["deployments"] == []
    unmerged = doc_of(plan(pr_world(merged=False).fake(), now=at(7)), f"raw/pr/{N}.json.gz")
    assert unmerged["incomplete"] == [] and unmerged["deployments"] == []


def _frozen_r1(world=None, now=None):
    p = plan((world or pr_world()).fake(), now=now or at(7))
    files = dict(p.files)
    frozen = {"pr": {str(N): 1}, "brief": {str(BRIEF): 1}}
    return files, frozen


def test_refreeze_adds_r2_and_modifies_nothing():
    """refreeze adds raw/pr/<n>.r2.json.gz; the plan holds no other path."""
    files, frozen = _frozen_r1()
    gh = pr_world().fake()
    p = freeze.refreeze(gh, N, state=empty_state(), frozen=frozen, conf=CONF, read=tree(files))
    assert list(p.files) == [f"raw/pr/{N}.r2.json.gz"]
    assert p.frozen == [("pr", str(N), 2)] and p.recaptured == []
    d = doc_of(p, f"raw/pr/{N}.r2.json.gz")
    assert d["revision"] == 2
    # Nothing but the revision differs from r1 for an unchanged PR (no volatile field stored).
    r1 = canonical.loads_gz(files[f"raw/pr/{N}.json.gz"])
    assert {k: v for k, v in d.items() if k != "revision"} == {
        k: v for k, v in r1.items() if k != "revision"}


def _retention_world() -> World:
    # GitHub deleted the runs, statuses and deployments (> 90 days after close).
    return pr_world(runs=[], statuses={C1: [], C2: []}, deployments=False).set(
        "/deployments", []).set("/actions/workflows/ci.yml/runs", {"total_count": 0, "workflow_runs": []})


def test_refreeze_after_retention_keeps_rounds_sections():
    """Critique 10 (section half, no other builder needed): r1's ci_runs, statuses and deployments are carried into r2 by id; a live row with an r1 id wins."""
    files, frozen = _frozen_r1()
    r1 = canonical.loads_gz(files[f"raw/pr/{N}.json.gz"])
    p = freeze.refreeze(_retention_world().fake(), N, state=empty_state(), frozen=frozen,
                        conf=CONF, read=tree(files))
    r2 = doc_of(p, f"raw/pr/{N}.r2.json.gz")
    for section in freeze.RETENTION_BOUND:
        assert r2[section] == r1[section], section
    # Live wins on an id collision; a live-only id joins; r1-only ids stay.
    w = _retention_world().set("/actions/workflows/ci.yml/runs", {"total_count": 2, "workflow_runs": [
        rest_run(102, C2, at(-10), conclusion="failure"), rest_run(103, C2, at(-5))]})
    w.set(f"/commits/{C2}/statuses", [rest_status(12, "reviewer-signoff", at(-9), state_="failure")])
    r2b = doc_of(freeze.refreeze(w.fake(), N, state=empty_state(), frozen=frozen, conf=CONF,
                                 read=tree(files)), f"raw/pr/{N}.r2.json.gz")
    by_id = {r["id"]: r for r in r2b["ci_runs"]}
    assert sorted(by_id) == [101, 102, 103] and by_id[102]["conclusion"] == "failure"
    assert [s["state"] for s in r2b["statuses"][C2]] == ["failure"]
    assert [s["id"] for s in r2b["statuses"][C1]] == [11]


@needs(episodes.rounds)
def test_refreeze_after_retention_keeps_rounds():
    """Critique 10: a refreeze whose live /actions/workflows/ci.yml/runs, /commits/{sha}/statuses and /deployments all answer empty (GitHub deleted them) carries r1's ci_runs, statuses and deployments into r2 by id, so episodes.rounds(r2) == episodes.rounds(r1); a live row with an r1 id wins."""
    files, frozen = _frozen_r1()
    r1 = canonical.loads_gz(files[f"raw/pr/{N}.json.gz"])
    p = freeze.refreeze(_retention_world().fake(), N, state=empty_state(), frozen=frozen,
                        conf=CONF, read=tree(files))
    r2 = doc_of(p, f"raw/pr/{N}.r2.json.gz")
    assert episodes.rounds(r2) == episodes.rounds(r1)
    # Negative control: without the union (no previous), the deleted pushes lose the rounds' heads.
    bare = freeze.capture_pr(_retention_world().fake(), N, revision=2, captured=r1["captured"],
                             snapshot_runs=lambda: [], snapshot_statuses=lambda sha: None)
    assert bare["ci_runs"] == [] and bare["statuses"] == {}


def test_changed_terminal_state_is_recaptured():
    """Critique 11: a PR frozen closed-unmerged (r1 pull.merged_at null) that the closed listing now shows merged goes back through settle and freezes r2 once due; a frozen PR whose listing differs only in updated_at (a late comment) is NOT recaptured; a skipped PR with a new closed_at is re-evaluated; a brief frozen with brief-open that is now closed gets r2 after settle."""
    # (a) frozen closed-unmerged at T0, reopened, then merged 30 h later.
    files, frozen = _frozen_r1(pr_world(merged=False, brief=False))
    t1 = at(30)
    merged_world = pr_world(closed_at=t1, brief=False)
    early = plan(merged_world.fake(), now=at(2, t1), frozen=frozen, files=files)
    assert early.files == {} and early.pending["pr"][str(N)]["due_at"] == at(6, t1)
    due = plan(merged_world.fake(), now=at(7, t1), frozen=frozen, files=files)
    assert list(due.files) == [f"raw/pr/{N}.r2.json.gz"]
    assert due.frozen == [("pr", str(N), 2)] and due.recaptured == [("pr", str(N), 2)]
    r2 = doc_of(due, f"raw/pr/{N}.r2.json.gz")
    assert (r2["revision"], r2["pull"]["merged_at"]) == (2, t1)
    # (b) frozen, the listing differs only in updated_at: nothing planned, no per-PR GET.
    late_comment = pr_world()
    late_comment.set("/pulls", [rest_pull(updated_at=at(40))])
    files1, frozen1 = _frozen_r1()
    gh = late_comment.fake()
    quiet = plan(gh, now=at(41), frozen=frozen1, files=files1)
    assert quiet.files == {} and quiet.frozen == [] and quiet.pending["pr"] == {}
    assert [c[0] for c in gh.calls if c[0].startswith(f"/pulls/{N}")] == []
    # (c) a skipped PR is re-evaluated only when its closed_at changes.
    st = empty_state()
    st["skipped"]["pr"][str(N)] = {"closed_at": T0}
    gh_same = pr_world().fake()
    assert plan(gh_same, now=at(1), st=st).pending["pr"] == {}
    assert calls_to(gh_same, f"/pulls/{N}/files") == []
    t2 = at(50)
    gh_new = pr_world(closed_at=t2).fake()
    again = plan(gh_new, now=at(1, t2), st=st)
    assert len(calls_to(gh_new, f"/pulls/{N}/files")) == 1
    assert again.pending["pr"][str(N)]["closed_at"] == t2
    # (d) a brief frozen open (brief-open) and now closed: r2 after settle, not before.
    open_doc = freeze.capture_brief(
        World().set(f"/issues/{BRIEF}", rest_issue(state_="open", closed_at=None))
        .set(f"/issues/{BRIEF}/timeline", []).set(f"/issues/{BRIEF}/comments", []).fake(),
        BRIEF, revision=1, captured={"run_id": 0, "harvester": "t", "digest": "body-digest@1"})
    assert "brief-open" in open_doc["incomplete"]
    bfiles = {f"raw/brief/{BRIEF}.json.gz": canonical.dumps_gz(open_doc)}
    bfrozen = {"brief": {str(BRIEF): 1}}
    closed_at = at(60)
    bw = World().set("/pulls", []).set("/releases", []).set(
        "/issues", [rest_issue(closed_at=closed_at)]).set(
        f"/issues/{BRIEF}", rest_issue(closed_at=closed_at)).set(
        f"/issues/{BRIEF}/timeline", []).set(f"/issues/{BRIEF}/comments", [])
    b_early = plan(bw.fake(), now=at(1, closed_at), frozen=bfrozen, files=bfiles)
    assert b_early.files == {} and b_early.pending["brief"][str(BRIEF)]["due_at"] == at(6, closed_at)
    b_due = plan(bw.fake(), now=at(7, closed_at), frozen=bfrozen, files=bfiles)
    assert list(b_due.files) == [f"raw/brief/{BRIEF}.r2.json.gz"]
    assert b_due.recaptured == [("brief", str(BRIEF), 2)]
    rb = doc_of(b_due, f"raw/brief/{BRIEF}.r2.json.gz")
    assert rb["issue"]["state"] == "closed" and "brief-open" not in rb["incomplete"]
    # … and an unchanged frozen brief in the listing is left alone.
    rfiles = dict(bfiles, **{f"raw/brief/{BRIEF}.r2.json.gz": b_due.files[f"raw/brief/{BRIEF}.r2.json.gz"]})
    assert plan(bw.fake(), now=at(9, closed_at), frozen={"brief": {str(BRIEF): 2}},
                files=rfiles).files == {}


def test_linked_issue_becomes_a_brief_only_with_the_label():
    """Critique 24: a PR linking #N (closes #N) where #N never carried design-brief captures no raw/brief/N (capture_brief returns None); with a timeline 'labeled design-brief' event (label since removed) it does."""
    cap = {"run_id": 0, "harvester": "t", "digest": "body-digest@1"}
    plain = pr_world(brief_labels=("autonomy-ok",))
    assert freeze.capture_brief(plain.fake(), BRIEF, revision=1, captured=cap) is None
    p = plan(plain.fake(), now=at(7))
    assert list(p.files) == [f"raw/pr/{N}.json.gz"]
    assert doc_of(p, f"raw/pr/{N}.json.gz")["linked_issues"] == [BRIEF]   # still linked, a number
    assert p.pending["brief"] == {}
    labeled = [{"id": 1, "event": "labeled", "label": {"name": "design-brief"},
                "created_at": "2026-10-01T00:00:01Z", "actor": USER},
               {"id": 2, "event": "unlabeled", "label": {"name": "design-brief"},
                "created_at": "2026-10-02T00:00:00Z", "actor": USER}]
    once = pr_world(brief_labels=("autonomy-ok",), brief_timeline=labeled)
    doc = freeze.capture_brief(once.fake(), BRIEF, revision=1, captured=cap)
    assert doc is not None and doc["format"] == "raw-brief@1" and doc["number"] == BRIEF
    p2 = plan(once.fake(), now=at(7))
    assert sorted(p2.files) == [f"raw/brief/{BRIEF}.json.gz", f"raw/pr/{N}.json.gz"]
    # A PR, not an issue, is never a brief; neither is an issue GitHub cannot serve.
    assert freeze.capture_brief(World().set(f"/issues/{BRIEF}", dict(
        rest_issue(), pull_request={"url": "x"})).fake(), BRIEF, revision=1, captured=cap) is None
    assert freeze.capture_brief(World().fake(), BRIEF, revision=1, captured=cap) is None
    # is_design_brief over the projected shapes.
    assert freeze.is_design_brief({"labels": ["design-brief"]}, [])
    assert freeze.is_design_brief({"labels": []}, [{"event": "labeled", "label": "design-brief"}])
    assert not freeze.is_design_brief({"labels": ["design"]}, [{"event": "labeled", "label": "design"}])
    assert not freeze.is_design_brief({"labels": []}, [{"event": "unlabeled", "label": "design-brief"}])


def test_open_linked_brief_is_captured_with_brief_open():
    w = pr_world()
    w.set(f"/issues/{BRIEF}", rest_issue(state_="open", closed_at=None))
    d = doc_of(plan(w.fake(), now=at(7)), f"raw/brief/{BRIEF}.json.gz")
    assert "brief-open" in d["incomplete"] and d["issue"]["state"] == "open"


def test_capture_unions_snapshot_rows():
    """capture_pr unions snapshot ci runs and statuses by id, live winning on a collision."""
    from provenance import rawdoc
    snap_runs = rawdoc.project_runs([
        rest_run(102, C2, at(-10), conclusion="failure"),        # collides with a live id
        rest_run(90, C1, at(-40)),                                # snapshot-only: deleted live
        rest_run(91, "f0" * 20, at(-40), prs=()),                 # neither the PR nor its commit
        rest_run(92, C1, at(-40), branch="other-branch"),         # another branch
    ])
    snap_status = {C1: rawdoc.project_statuses([rest_status(11, "Vercel", at(-30), state_="pending"),
                                                rest_status(10, "Vercel", at(-31))])}
    w = pr_world()
    doc = freeze.capture_pr(w.fake(), N, revision=1,
                            captured={"run_id": 0, "harvester": "t", "digest": "body-digest@1"},
                            snapshot_runs=lambda: snap_runs,
                            snapshot_statuses=lambda sha: snap_status.get(sha))
    by_id = {r["id"]: r for r in doc["ci_runs"]}
    assert sorted(by_id) == [90, 101, 102]
    assert by_id[102]["conclusion"] == "success"                         # live wins
    assert [r["id"] for r in doc["ci_runs"]] == [90, 101, 102]          # (created_at, id) order
    assert [(s["id"], s["state"]) for s in doc["statuses"][C1]] == [(10, "success"), (11, "success")]


def test_capture_fetches_statuses_for_every_commit():
    """Statuses are fetched for every PR commit and ci head (/commits/{sha}/statuses), not the combined /status."""
    orphan = "d4" * 20   # a ci head no longer among the PR's commits (force-pushed away)
    runs = [rest_run(101, C1, at(-30)), rest_run(104, orphan, at(-20))]
    gh = pr_world(runs=runs).fake()
    doc = freeze.capture_pr(gh, N, revision=1,
                            captured={"run_id": 0, "harvester": "t", "digest": "body-digest@1"},
                            snapshot_runs=lambda: [], snapshot_statuses=lambda sha: None)
    asked = sorted(c[0] for c in gh.calls if c[0].startswith("/commits/"))
    assert asked == sorted(f"/commits/{s}/statuses" for s in (C1, C2, orphan))
    assert not [c for c in gh.calls if c[0].endswith("/status")]
    assert sorted(doc["statuses"]) == [C1, C2]          # an empty answer stores no key
    # A sha GitHub refuses as unknown (422 / 404 / 410), with no snapshot or earlier copy, is
    # recorded — never guessed.
    cap = {"run_id": 0, "harvester": "t", "digest": "body-digest@1"}
    for status in (422, 404, 410):
        gh2 = pr_world(runs=runs).refuse(f"/commits/{orphan}/statuses", status).fake()
        doc2 = freeze.capture_pr(gh2, N, revision=1, captured=cap,
                                 snapshot_runs=lambda: [], snapshot_statuses=lambda sha: None)
        assert f"statuses-unavailable:{orphan[:8]}" in doc2["incomplete"], status
    # … but a TRANSIENT refusal (a 5xx after retries, a transport failure) is not "gone": it fails
    # the capture, so the unit is retried next run instead of freezing a permanent gap.
    for status in (502, 500, None):
        gh3 = pr_world(runs=runs).refuse(f"/commits/{orphan}/statuses", status).fake()
        with pytest.raises(APIError):
            freeze.capture_pr(gh3, N, revision=1, captured=cap,
                              snapshot_runs=lambda: [], snapshot_statuses=lambda sha: None)


def test_truncated_listings_are_recorded():
    w = pr_world()
    w.set(f"/pulls/{N}", rest_pull(commits=251, changed_files=3001))
    doc = freeze.capture_pr(w.fake(), N, revision=1,
                            captured={"run_id": 0, "harvester": "t", "digest": "body-digest@1"},
                            snapshot_runs=lambda: [], snapshot_statuses=lambda sha: None)
    assert {"commits-truncated", "files-truncated"} <= set(doc["incomplete"])


def test_no_design_files_is_skipped():
    """A closed PR touching no designs/ path is recorded in state.skipped.pr with its closed_at and never captured."""
    gh = pr_world(files=("docs/provenance.md", "scripts/x.sh")).fake()
    p = plan(gh, now=at(7))
    assert p.skipped_prs == {N: T0} and p.files == {} and p.pending["pr"] == {}
    assert calls_to(gh, f"/pulls/{N}") == [] and calls_to(gh, f"/pulls/{N}/commits") == []
    # A rename OUT of designs/ still touches designs/ (previous_filename).
    w = pr_world(files=())
    w.set(f"/pulls/{N}/files", [{"filename": "attic/w.scad", "previous_filename": "designs/w/w.scad",
                                 "status": "renamed"}])
    assert plan(w.fake(), now=at(7)).skipped_prs == {}


def test_pending_pr_outside_the_listing_is_reevaluated():
    st = empty_state()
    st["cursors"]["prs_updated"] = at(100)       # the cursor moved far past the PR
    st["pending"]["pr"][str(N)] = {"closed_at": T0, "due_at": at(6), "defer_until": at(24),
                                   "reasons": ["in-flight-run"]}
    w = pr_world()
    w.set("/pulls", [])
    p = plan(w.fake(), now=at(7), st=st)
    assert f"raw/pr/{N}.json.gz" in p.files and str(N) not in p.pending["pr"]
    assert p.cursors["prs_updated"] == at(100)
    # Reopened while pending: it leaves pending without freezing.
    w.set(f"/pulls/{N}", rest_pull(state_="open", closed_at=None, merged_at=None))
    gone = plan(w.fake(), now=at(7), st=st)
    assert gone.files == {} and gone.pending["pr"] == {} and gone.cleared == [("pr", str(N))]


def test_capture_failure_stays_pending():
    w = pr_world()
    w.set(f"/pulls/{N}", None)       # the listing has it, the object endpoint answers nothing
    p = plan(w.fake(), now=at(7))
    assert p.files == {} and p.pending["pr"][str(N)]["reasons"] == ["capture-failed"]

    # A refusal anywhere in the unit — here its linked brief's timeline — plans none of it.
    class Refusing(FakeGitHub):
        def get_paged(self, path, params=None, key=None, max_pages=50):
            if path == f"/issues/{BRIEF}/timeline":
                raise APIError("422 /issues/901/timeline")
            return super().get_paged(path, params, key, max_pages)

    w2 = pr_world()
    gh = Refusing(responder=lambda path, params: copy.deepcopy(w2.by_path.get(path)),
                  threads={N: {"nodes": [], "last_edited_at": None}})
    p2 = plan(gh, now=at(7))
    assert p2.files == {} and p2.frozen == []
    assert p2.pending["pr"][str(N)]["reasons"] == ["capture-failed"] and p2.pending["brief"] == {}
    # An in-flight lookup GitHub refuses counts as in flight (defer), never as clear.
    class NoRuns(FakeGitHub):
        def get(self, path, params=None):
            if path == "/actions/runs":
                raise APIError("422 /actions/runs")
            return super().get(path, params)

    gh3 = NoRuns(responder=lambda path, params: copy.deepcopy(w2.by_path.get(path)),
                 threads={N: {"nodes": [], "last_edited_at": None}})
    assert plan(gh3, now=at(7)).pending["pr"][str(N)]["reasons"] == ["in-flight-run"]


def test_budget_stop_plans_whole_units_and_resumes():
    for budget in range(1, 12):
        gh = pr_world().fake(budget=budget, exhausted_with=BudgetExhausted)
        p = plan(gh, now=at(7))
        assert p.budget_stopped, budget
        # A PR and its brief freeze together or not at all; no listing cursor advanced.
        assert set(p.files) in (set(), {f"raw/pr/{N}.json.gz", f"raw/brief/{BRIEF}.json.gz"}), budget
        assert "prs_updated" not in p.cursors, budget
    resumed = plan(pr_world().fake(), now=at(7))
    assert not resumed.budget_stopped and f"raw/pr/{N}.json.gz" in resumed.files
    assert resumed.cursors == {"prs_updated": T0, "briefs_updated": None, "releases_published": None}


def test_only_prs_restricts_the_pass():
    w = pr_world()
    w.set("/pulls", [rest_pull(n=901)])
    gh = w.fake()
    p = plan(gh, now=at(7), only_prs=(N,))
    assert f"raw/pr/{N}.json.gz" in p.files and p.cursors == {}
    assert calls_to(gh, "/pulls") == [] and calls_to(gh, "/releases") == []


def test_releases_freeze_on_publish():
    rel = {"id": 3, "tag_name": "v2.0", "name": "v2.0", "draft": False, "prerelease": False,
           "created_at": at(-1), "published_at": at(-1), "author": USER, "target_commitish": "main",
           "body": "notes", "assets": [{"name": "a.zip", "size": 10, "content_type": "application/zip",
                                        "download_count": 9}]}
    draft = dict(rel, id=4, tag_name="v3.0", draft=True, published_at=None)
    evil = dict(rel, id=5, tag_name="../x")
    w = World().set("/pulls", []).set("/issues", []).set("/releases", [rel, draft, evil])
    p = plan(w.fake(), now=at(0))
    assert list(p.files) == ["raw/release/v2.0.json.gz"] and p.frozen == [("release", "v2.0", 1)]
    d = doc_of(p, "raw/release/v2.0.json.gz")
    assert d["format"] == "raw-release@1" and "download_count" not in d["release"]["assets"][0]
    assert p.cursors["releases_published"] == at(-1)
    again = plan(w.fake(), now=at(1), frozen={"release": {"v2.0": 1}})
    assert again.files == {}


def test_no_op_harvest_writes_nothing():
    """A harvest with nothing new plans no file and an unchanged state.json."""
    files, frozen = _frozen_r1()
    st = empty_state()
    st["cursors"].update(prs_updated=T0, briefs_updated=T0, releases_published=None)
    st["skipped"]["pr"]["800"] = {"closed_at": at(-1)}
    st["pending"]["pr"]["902"] = {"closed_at": at(46), "due_at": at(52), "defer_until": at(70),
                                  "reasons": []}
    w = pr_world()
    # Newest-first, as GitHub sorts it: the pending PR, the frozen one, the skipped one, and one
    # older than the cursor's settle window (never looked at).
    w.set("/pulls", [rest_pull(n=902, closed_at=at(46)), rest_pull(),
                     rest_pull(n=800, closed_at=at(-1), merged_at=None),
                     rest_pull(n=700, closed_at=at(-90), merged_at=None)])
    w.set("/pulls/902", rest_pull(n=902, closed_at=at(46)))
    w.set("/issues", [rest_issue()])
    gh = w.fake()
    p = plan(gh, now=at(47), st=st, frozen=frozen, files=files)
    assert p.files == {} and p.frozen == [] and p.skipped_prs == {} and p.cleared == []
    assert p.pending == st["pending"]
    touched = {c[0] for c in gh.calls}
    assert not touched & {"/pulls/800/files", "/pulls/700/files", f"/pulls/{N}/files", "/pulls/902/files"}
    assert {k: p.cursors[k] for k in p.cursors} == {
        "prs_updated": at(46), "briefs_updated": T0, "releases_published": None}
    # Strict no-op: with the cursor already at the newest listed update, the plan's cursors
    # equal the state's.
    st2 = copy.deepcopy(st)
    st2["cursors"]["prs_updated"] = at(46)
    p2 = plan(w.fake(), now=at(47), st=st2, frozen=frozen, files=files)
    assert p2.files == {} and p2.pending == st2["pending"]
    assert all(st2["cursors"][k] == v for k, v in p2.cursors.items())


@needs(state.load_state, state.dump_state, state.set_pending, state.clear_pending, state.set_skipped)
def test_no_op_harvest_state_json_is_byte_identical():
    """The same no-op pass applied through state.py writes the identical state.json bytes."""
    files, frozen = _frozen_r1()
    st = empty_state()
    st["cursors"].update(prs_updated=T0, briefs_updated=T0)
    before = state.dump_state(st)
    p = plan(pr_world().fake(), now=at(47), st=st, frozen=frozen, files=files)
    new = state.load_state(before, st["versions"])
    for kind, entries in p.pending.items():
        for key, e in entries.items():
            state.set_pending(new, kind, key, closed_at=e["closed_at"], due_at=e["due_at"],
                              defer_until=e["defer_until"], reasons=e["reasons"])
    for kind, key, _rev in p.frozen:
        state.clear_pending(new, kind, key)
    for n, closed_at in p.skipped_prs.items():
        state.set_skipped(new, n, closed_at)
    new["cursors"].update(p.cursors)
    assert state.dump_state(new) == before


@needs(contract.validate)
def test_captured_documents_satisfy_the_contract():
    p = plan(pr_world().fake(), now=at(7))
    assert contract.validate("raw-pr@1", doc_of(p, f"raw/pr/{N}.json.gz")) == []
    assert contract.validate("raw-brief@1", doc_of(p, f"raw/brief/{BRIEF}.json.gz")) == []
    stuck = plan(pr_world(in_flight=[rest_run(9, C2, at(6.5), status="queued", conclusion=None,
                                              path=".github/workflows/oracle.yml")]).fake(), now=at(25))
    assert contract.validate("raw-pr@1", doc_of(stuck, f"raw/pr/{N}.json.gz")) == []
    st = empty_state()
    st["pending"] = plan(pr_world().fake(), now=at(2)).pending
    assert contract.validate("state@1", st) == []


# --- review round: Closes #0, admission, per-unit isolation, refreeze, since --------------

def test_closes_zero_links_nothing():
    """An untrusted body reading "Closes #0" puts no 0 into linked_issues (raw-pr@1: min 1): the
    PR still freezes, linking only #901; the head-ref path drops issue-0 the same way."""
    p = plan(pr_world(body="Ships the widget.\n\nCloses #0\nCloses #901").fake(), now=at(7))
    assert doc_of(p, f"raw/pr/{N}.json.gz")["linked_issues"] == [BRIEF]
    assert freeze._linked_issues({"refs_closes": [0, -3, True, 901, 10 ** 7]},
                                 "claude/issue-0-widget") == [901]
    assert freeze._linked_issues({"refs_closes": []}, "claude/issue-0-widget") == []
    assert freeze._linked_issues({"refs_closes": [5]}, "claude/issue-12-widget") == [5, 12]


@needs(contract.validate)
def test_closes_zero_document_satisfies_the_contract():
    """At integration: the "Closes #0" PR's whole document — its pull.body digest included — is
    contract-valid and frozen (needs digest.refs_closes to drop 0 too: the reported H2 delta)."""
    p = plan(pr_world(body="Ships the widget.\n\nCloses #0\nCloses #901").fake(), now=at(7))
    assert p.pending["pr"] == {}, p.pending["pr"]
    assert contract.validate("raw-pr@1", doc_of(p, f"raw/pr/{N}.json.gz")) == []


def _reject(monkeypatch, *shapes, message="$.pull.title: 'evil\n::set-output name=x::y' bad"):
    """Make the admission check reject ``shapes`` with ``message`` (an untrusted value inside)."""
    monkeypatch.setattr(freeze.contract, "validate", lambda shape, value, c=None: (
        [message] if shape in shapes else _base_validate(shape, value)))


RELEASE = {"id": 3, "tag_name": "v2.0", "name": "v2.0", "draft": False, "prerelease": False,
           "created_at": at(-1), "published_at": at(-1), "author": USER,
           "target_commitish": "main", "body": "notes", "assets": []}


def test_contract_invalid_document_is_never_planned(monkeypatch):
    """Admission: a document the closed contract rejects never reaches the add-only ref. The PR
    (with its linked brief — one unit) stays pending contract-invalid; a brief from the listing
    likewise; a release is skipped; refreeze raises. The message names a JSON path, no value."""
    _reject(monkeypatch, "raw-pr@1")
    p = plan(pr_world().fake(), now=at(7))
    assert p.files == {} and p.frozen == []
    assert p.pending["pr"][str(N)]["reasons"] == ["contract-invalid"]
    assert p.pending["brief"] == {}
    with pytest.raises(freeze.ContractInvalid) as err:
        freeze._admit("pr", {"format": "raw-pr@1"})
    text = str(err.value)
    assert "raw-pr@1" in text and "$.pull.title" in text
    assert "evil" not in text and "\n" not in text and "::" not in text
    assert isinstance(err.value, freeze.CaptureError)            # the cli maps it to exit 1
    # The linked brief failing admission holds the whole unit.
    _reject(monkeypatch, "raw-brief@1")
    p2 = plan(pr_world().fake(), now=at(7))
    assert p2.files == {} and p2.pending["pr"][str(N)]["reasons"] == ["contract-invalid"]
    # A brief from the listing (closed and settled, no PR involved).
    bw = World().set("/pulls", []).set("/releases", []).set("/issues", [rest_issue()]).set(
        f"/issues/{BRIEF}", rest_issue()).set(f"/issues/{BRIEF}/timeline", []).set(
        f"/issues/{BRIEF}/comments", [])
    pb = plan(bw.fake(), now=at(7))
    assert pb.files == {} and pb.pending["brief"][str(BRIEF)]["reasons"] == ["contract-invalid"]
    # A release: never planned (the next full listing retries it).
    _reject(monkeypatch, "raw-release@1")
    pr_ = plan(World().set("/pulls", []).set("/issues", []).set("/releases", [RELEASE]).fake(),
               now=at(0))
    assert pr_.files == {} and pr_.frozen == []
    # refreeze: the ContractInvalid propagates, nothing planned.
    files, frozen = _frozen_r1()
    _reject(monkeypatch, "raw-pr@1")
    with pytest.raises(freeze.ContractInvalid):
        freeze.refreeze(pr_world().fake(), N, state=empty_state(), frozen=frozen, conf=CONF,
                        read=tree(files))


def test_one_refusing_pr_never_blocks_the_pass():
    """Per-unit isolation: PR #900's /files is refused 422 (a documented answer of that endpoint)
    and the healthy PR #905 listed after it still freezes; #900 stays pending capture-failed —
    never skipped, since its designs/ check decided nothing — and re-runs that check next pass."""
    w = add_pr(pr_world(), N2).refuse(f"/pulls/{N}/files", 422)
    p = plan(w.fake(), now=at(7))
    assert f"raw/pr/{N2}.json.gz" in p.files and ("pr", str(N2), 1) in p.frozen
    assert f"raw/pr/{N}.json.gz" not in p.files and p.skipped_prs == {}
    assert p.pending["pr"][str(N)] == {"closed_at": T0, "due_at": at(6), "defer_until": at(24),
                                       "reasons": ["capture-failed"]}
    assert p.cursors["prs_updated"] == T0
    # Negative control: without the refusal both freeze.
    ok = plan(add_pr(pr_world(), N2).fake(), now=at(7))
    assert {f"raw/pr/{N}.json.gz", f"raw/pr/{N2}.json.gz"} <= set(ok.files)
    # Next pass, the files answer: a held PR touching no designs/ path leaves pending for skipped …
    st = empty_state()
    st["pending"] = copy.deepcopy(p.pending)
    st["cursors"]["prs_updated"] = T0
    done = {"pr": {str(N2): 1}}
    have = {f"raw/pr/{N2}.json.gz": p.files[f"raw/pr/{N2}.json.gz"]}
    gh_doc = add_pr(pr_world(files=("docs/x.md",)), N2).fake()
    again = plan(gh_doc, now=at(8), st=st, frozen=done, files=have)
    assert again.skipped_prs == {N: T0} and str(N) not in again.pending["pr"] and again.files == {}
    assert len(calls_to(gh_doc, f"/pulls/{N}/files")) == 1
    # … one that does touch designs/ freezes (the files read once, reused by the capture).
    gh_ok = add_pr(pr_world(), N2).fake()
    healed = plan(gh_ok, now=at(8), st=st, frozen=done, files=have)
    assert f"raw/pr/{N}.json.gz" in healed.files and str(N) not in healed.pending["pr"]
    assert len(calls_to(gh_ok, f"/pulls/{N}/files")) == 1
    # A 5xx inside the capture (#900's statuses — #905 shares the sha, so both hold) never ends
    # the pass either: both stay pending, the brief and release listings still run.
    w5 = add_pr(pr_world(), N2).refuse(f"/commits/{C1}/statuses", 502).set("/releases", [RELEASE])
    p5 = plan(w5.fake(), now=at(7))
    assert list(p5.files) == ["raw/release/v2.0.json.gz"]
    assert p5.pending["pr"][str(N)]["reasons"] == p5.pending["pr"][str(N2)]["reasons"] == [
        "capture-failed"]


def test_refused_reread_of_a_pending_unit_keeps_it_and_the_pass_goes_on():
    """A pending PR / brief the listing did not reach is re-read by number; GitHub refusing that
    re-read keeps its entry (marked capture-failed, times unchanged) and later units still freeze."""
    st = empty_state()
    st["cursors"]["prs_updated"] = at(100)
    st["pending"]["pr"][str(N)] = {"closed_at": T0, "due_at": at(6), "defer_until": at(24),
                                   "reasons": ["in-flight-run"]}
    st["pending"]["brief"]["777"] = {"closed_at": T0, "due_at": at(6), "defer_until": at(24),
                                     "reasons": []}
    w = pr_world().set("/pulls", []).set("/releases", [RELEASE])
    w.refuse(f"/pulls/{N}", 502).refuse("/issues/777", 502)
    p = plan(w.fake(), now=at(7), st=st)
    assert p.pending["pr"][str(N)] == {"closed_at": T0, "due_at": at(6), "defer_until": at(24),
                                       "reasons": ["capture-failed", "in-flight-run"]}
    assert p.pending["brief"]["777"]["reasons"] == ["capture-failed"]
    assert list(p.files) == ["raw/release/v2.0.json.gz"]           # the pass reached releases
    assert p.cursors["prs_updated"] == at(100) and p.cleared == []


def test_deployment_lookup_refusals():
    """Settle: a refused deployment lookup reads NOT terminal, never terminal and never the end of
    the pass; in the capture a 5xx holds the unit, while a deleted deployment's statuses (404)
    record as empty."""
    p = plan(pr_world().refuse("/deployments", 502).fake(), now=at(7))
    assert p.files == {} and p.pending["pr"][str(N)]["reasons"] == ["capture-failed"]
    d = doc_of(plan(pr_world().refuse("/deployments/7/statuses", 404).fake(), now=at(7)),
               f"raw/pr/{N}.json.gz")
    assert d["incomplete"] == ["deployment-not-terminal"]
    assert [x["id"] for x in d["deployments"]] == [7] and d["deployments"][0]["statuses"] == []


def test_refreeze_refuses_an_unfrozen_pr():
    """refreeze is "capture this frozen unit again" — never a bypass of settle and the designs/
    filter: an OPEN, non-design PR with no frozen revision (and already skipped) is refused
    before any request, with the CaptureError subclass the cli maps to exit 1."""
    w = pr_world(files=("docs/x.md",))
    w.set(f"/pulls/{N}", rest_pull(state_="open", closed_at=None, merged_at=None))
    st = empty_state()
    st["skipped"]["pr"][str(N)] = {"closed_at": T0}
    gh = w.fake()
    with pytest.raises(freeze.RefreezeRefused) as err:
        freeze.refreeze(gh, N, state=st, frozen={}, conf=CONF, read=tree({}))
    assert isinstance(err.value, freeze.CaptureError) and "harvest --pr" in str(err.value)
    assert gh.calls == []
    # Another unit's revisions (a brief with the same number) do not make the PR frozen.
    with pytest.raises(freeze.RefreezeRefused):
        freeze.refreeze(gh, N, state=st, frozen={"pr": {"901": 1}, "brief": {str(N): 1}},
                        conf=CONF, read=tree({}))


def test_since_lowers_both_listing_cursors_never_below_backfill():
    """plan_freezes(since=…): a cursor far past the PR hides it; since lowers the PR cutoff and the
    briefs listing's since= parameter, so it is listed and frozen; a since before backfill_since
    is clamped to that floor; with no cursor the floor is the start; cursors never move back."""
    st = empty_state()
    st["cursors"].update(prs_updated="2026-12-01T00:00:00Z", briefs_updated="2026-12-01T00:00:00Z")

    def brief_since(gh):
        calls = [c for c in gh.calls if c[0] == "/issues"]
        assert len(calls) == 1
        assert {"labels": "design-brief", "state": "all", "sort": "updated"}.items() <= calls[0][1].items()
        return calls[0][1]["since"]

    gh0 = pr_world().fake()
    assert plan(gh0, now=at(7), st=st).files == {}
    assert brief_since(gh0) == "2026-12-01T00:00:00Z"
    gh1 = pr_world().fake()
    p = plan(gh1, now=at(7), st=st, since="2026-10-01T00:00:00Z")
    assert f"raw/pr/{N}.json.gz" in p.files
    assert brief_since(gh1) == "2026-10-01T00:00:00Z"
    assert p.cursors["prs_updated"] == "2026-12-01T00:00:00Z"
    gh2 = pr_world().fake()
    plan(gh2, now=at(7), st=st, since="2020-01-01")
    assert brief_since(gh2) == f"{CONF.backfill_since}T00:00:00Z"
    gh3 = pr_world().fake()
    plan(gh3, now=at(7))
    assert brief_since(gh3) == f"{CONF.backfill_since}T00:00:00Z"
    # The PR listing asks closed / updated / desc and stops at the cutoff (since − the settle
    # window): an older row is never looked at.
    w = pr_world()
    w.set("/pulls", [rest_pull(), rest_pull(n=700, closed_at="2026-09-01T00:00:00Z", merged_at=None)])
    gh4 = w.fake()
    plan(gh4, now=at(7), st=st, since="2026-10-01T00:00:00Z")
    listing = [c for c in gh4.calls if c[0] == "/pulls"]
    assert listing and all({"state": "closed", "sort": "updated", "direction": "desc"}.items()
                           <= c[1].items() for c in listing)
    assert calls_to(gh4, "/pulls/700/files") == []


def test_reeve_mirrors_the_deferral_reasons():
    """Reeve's provenance-lag measures a unit deferred BY DESIGN from defer_until and every other
    pending unit from due_at; its DEFER_REASONS must be exactly this module's two deferral
    reasons (tools/reeve pins the same pair from its side, so a rename in either suite fails)."""
    import re as _re
    text = (REPO / "tools" / "reeve" / "src" / "reeve" / "provenance.py").read_text(encoding="utf-8")
    m = _re.search(r"^DEFER_REASONS = frozenset\(\{(.*?)\}\)$", text, _re.MULTILINE)
    assert m, "tools/reeve/src/reeve/provenance.py: DEFER_REASONS not found"
    assert set(_re.findall(r'"([a-z-]+)"', m.group(1))) == {freeze.REASON_IN_FLIGHT,
                                                           freeze.REASON_DEPLOYMENT}
    assert freeze.CAPTURE_FAILED not in m.group(1) and freeze.CONTRACT_INVALID not in m.group(1)
