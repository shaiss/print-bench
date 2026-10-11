"""A ``claude/issue-<N>-*`` branch claims its issue only while it carries
unmerged work.

Before this rule any matching branch was a claim forever, so an orphan
starved its issue out of every firing: #565's ``claude/issue-565-scout-cap-state``
pointed at a commit already on main (its PR closed with head == base, the fix
landed as another commit), and the burn logged ``eligible_count 0`` while the
branch said "taken". The fix is a compare against the default branch —
``ahead_by == 0`` releases the branch, anything else keeps it a claim.

Each rule is proved both ways, the suite's negative-control discipline: the
#565 shape is selected, and the same issue with the compare showing work,
missing, failed or malformed is still excluded. Delete the ``_known_empty``
check from ``select.py`` and the positive half fails; make it read "unknown"
as empty and every fail-conservative half fails. The live layer is covered
through ``_get``, the single network seam, so no request leaves the process.
"""

from __future__ import annotations

import io
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from backlog_burn import github
from backlog_burn.select import (
    branches_needing_compare,
    render_summary,
    select_issue,
)

LABEL = "autonomy-ok"
NOW = datetime(2026, 10, 3, 13, 28, 0, tzinfo=timezone.utc)
ORPHAN = "claude/issue-565-scout-cap-state"


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def issue(number, *, labels=(LABEL,), comments=(), created="2026-09-20T00:00:00Z"):
    return {
        "number": number,
        "title": f"issue {number}",
        "createdAt": created,
        "labels": list(labels),
        "comments": list(comments),
    }


def snap(issues, *, branches=(), open_prs=(), ahead_by=None):
    s = {
        "issues": list(issues),
        "openPRs": list(open_prs),
        "branches": list(branches),
    }
    if ahead_by is not None:
        s["branchAheadBy"] = ahead_by
    return s


def lock(hours_ago):
    return {
        "body": "🚢 SHIP-LOCK — shipping this as one PR.",
        "createdAt": _iso(NOW - timedelta(hours=hours_ago)),
    }


# --------------------------------------------------------------------------
# The policy: ahead_by == 0 releases, everything else claims
# --------------------------------------------------------------------------

def test_orphan_branch_with_nothing_ahead_is_not_a_claim():
    # The #565 shape: the branch's head is already on main.
    r = select_issue(snap([issue(565)], branches=["main", ORPHAN],
                          ahead_by={ORPHAN: 0}), now=NOW)
    assert r["selected"] == 565
    assert r["empty_branches"] == [ORPHAN]
    assert ORPHAN in render_summary(r)


def test_branch_with_unmerged_work_still_claims():
    # Negative control: the same branch holding one commit main lacks (the
    # #622 shape — lib/spaceframe.scad, never on main) is a live claim.
    r = select_issue(snap([issue(565)], branches=[ORPHAN],
                          ahead_by={ORPHAN: 1}), now=NOW)
    assert r["selected"] is None
    assert "branch already exists" in r["excluded"]["565"]
    assert r["empty_branches"] == []


@pytest.mark.parametrize("ahead_by", [
    None,                       # snapshot has no compare data at all
    {},                         # compare data, but not for this branch
    {"claude/other": 0},        # an unrelated branch's zero proves nothing
    {ORPHAN: None},             # the compare failed
    {ORPHAN: "0"},              # malformed: a string is not a count
    {ORPHAN: False},            # malformed: bool is an int subclass in Python
    {ORPHAN: 0.0},              # malformed: a float is not a count
    [ORPHAN],                   # malformed: not even a mapping
], ids=["absent", "empty-map", "other-branch", "none", "str", "bool", "float", "list"])
def test_unknown_compare_keeps_the_claim(ahead_by):
    # Fail-conservative: only a positively observed integer zero releases.
    s = snap([issue(565)], branches=[ORPHAN])
    s["branchAheadBy"] = ahead_by
    r = select_issue(s, now=NOW)
    assert r["selected"] is None
    assert "branch already exists" in r["excluded"]["565"]


def test_one_live_branch_among_orphans_still_claims():
    live = "claude/issue-565-second-try"
    excluded = select_issue(snap([issue(565)], branches=[ORPHAN, live],
                                 ahead_by={ORPHAN: 0, live: 3}), now=NOW)
    assert excluded["selected"] is None
    # Negative control: both empty -> nothing claims.
    released = select_issue(snap([issue(565)], branches=[ORPHAN, live],
                                 ahead_by={ORPHAN: 0, live: 0}), now=NOW)
    assert released["selected"] == 565
    assert released["empty_branches"] == sorted([ORPHAN, live])


def test_empty_branch_does_not_keep_a_stale_lock_alive():
    # A dead run's 9 h-old claim plus an orphan branch: the branch backs
    # nothing, so this is the skill's stale-takeover case, not a claim.
    stale = issue(565, comments=[lock(9)])
    r = select_issue(snap([stale], branches=[ORPHAN], ahead_by={ORPHAN: 0}), now=NOW)
    assert r["selected"] == 565
    # Negative control: the same stale lock backed by real work stays taken.
    r = select_issue(snap([stale], branches=[ORPHAN], ahead_by={ORPHAN: 2}), now=NOW)
    assert r["selected"] is None


def test_empty_branch_does_not_release_a_fresh_lock():
    # The branch rule only stops the branch from claiming; an active claim
    # comment still holds the issue on its own.
    fresh = issue(565, comments=[lock(1)])
    r = select_issue(snap([fresh], branches=[ORPHAN], ahead_by={ORPHAN: 0}), now=NOW)
    assert r["selected"] is None
    assert r["excluded"]["565"].startswith("an active")


def test_empty_branch_does_not_release_other_exclusions():
    pr = {"number": 585, "headRefName": "feature", "body": "Closes #565"}
    r = select_issue(snap([issue(565)], branches=[ORPHAN], open_prs=[pr],
                          ahead_by={ORPHAN: 0}), now=NOW)
    assert r["excluded"]["565"].startswith("an open PR")
    parked = issue(565, labels=[LABEL, "needs-decision"])
    r = select_issue(snap([parked], branches=[ORPHAN], ahead_by={ORPHAN: 0}), now=NOW)
    assert r["excluded"]["565"].startswith("awaiting a human decision")


# --------------------------------------------------------------------------
# branches_needing_compare: one request per otherwise-eligible candidate
# --------------------------------------------------------------------------

def test_compare_requested_only_for_otherwise_eligible_candidates():
    pr = {"number": 900, "headRefName": "x", "body": "Fixes #11"}
    s = snap(
        [
            issue(10),                                    # eligible but for its branch
            issue(11),                                    # an open PR claims it anyway
            issue(12, labels=["enhancement"]),            # not opted in
            issue(13, labels=[LABEL, "needs-decision"]),  # parked
            issue(14, comments=[lock(1)]),                # active SHIP-LOCK
            issue(15, comments=[lock(9)]),                # stale lock: takeover-eligible
            issue(16),                                    # eligible, no branch at all
        ],
        branches=[
            "main", "claude/other-work",
            "claude/issue-10-b", "claude/issue-10-a",
            "claude/issue-11-x", "claude/issue-12-x", "claude/issue-13-x",
            "claude/issue-14-x", "claude/issue-15-x",
            "claude/issue-1-x",  # boundary: issue 1 is not 10..16
        ],
        open_prs=[pr],
    )
    assert branches_needing_compare(s, LABEL, NOW) == [
        "claude/issue-10-a", "claude/issue-10-b", "claude/issue-15-x",
    ]


def test_compare_set_follows_the_label():
    s = snap([issue(20, labels=["design-brief"])], branches=["claude/issue-20-x"])
    assert branches_needing_compare(s, LABEL, NOW) == []
    assert branches_needing_compare(s, "design-brief", NOW) == ["claude/issue-20-x"]


# --------------------------------------------------------------------------
# The live layer: compare through _get, failures keep the claim
# --------------------------------------------------------------------------

def _gather(monkeypatch, routes, *, issues_payload=None, branches=(ORPHAN,)):
    """Run gather_snapshot over canned routes; return (snapshot, urls)."""
    issues_payload = issues_payload if issues_payload is not None else [
        {"number": 565, "title": "scout cap state", "created_at": "2026-09-20T00:00:00Z",
         "labels": [{"name": LABEL}], "comments": 0},
    ]
    base_routes = {
        "/issues?state=open": (issues_payload, {}),
        "/pulls?state=open": ([], {}),
        "/branches": ([{"name": "main"}] + [{"name": b} for b in branches], {}),
    }
    urls: list[str] = []

    def _get(url, token):
        urls.append(url)
        path, _, query = url.partition("?")
        for key, served in {**base_routes, **routes}.items():
            kpath, _, kquery = key.partition("?")
            if path.endswith(kpath) and kquery in query:
                if isinstance(served, BaseException):
                    raise served
                return served
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(github, "_get", _get)
    return github.gather_snapshot("o/r", "t", LABEL, NOW), urls


def _http_error(code):
    return urllib.error.HTTPError("u", code, "err", hdrs=None, fp=io.BytesIO(b""))


def test_gather_compares_against_the_default_branch(monkeypatch):
    snapshot, urls = _gather(monkeypatch, {
        "/repos/o/r": ({"default_branch": "trunk"}, {}),
        f"/compare/trunk...{ORPHAN}": ({"ahead_by": 0, "behind_by": 40}, {}),
    })
    assert snapshot["branchAheadBy"] == {ORPHAN: 0}
    assert any(u.endswith(f"/repos/o/r/compare/trunk...{ORPHAN}") for u in urls)
    # And the selection the workflow makes from it takes the issue.
    assert select_issue(snapshot, LABEL, NOW)["selected"] == 565


def test_gather_failed_compare_keeps_the_claim(monkeypatch, capsys):
    snapshot, _ = _gather(monkeypatch, {
        "/repos/o/r": ({"default_branch": "main"}, {}),
        f"/compare/main...{ORPHAN}": _http_error(404),
    })
    assert snapshot["branchAheadBy"] == {}
    assert "keeping the branch as a claim" in capsys.readouterr().err
    assert select_issue(snapshot, LABEL, NOW)["selected"] is None


def test_gather_compare_without_ahead_by_keeps_the_claim(monkeypatch):
    snapshot, _ = _gather(monkeypatch, {
        "/repos/o/r": ({"default_branch": "main"}, {}),
        f"/compare/main...{ORPHAN}": ({"message": "No common ancestor"}, {}),
    })
    assert snapshot["branchAheadBy"] == {}
    assert select_issue(snapshot, LABEL, NOW)["selected"] is None


def test_gather_unreadable_default_branch_keeps_every_claim(monkeypatch):
    snapshot, urls = _gather(monkeypatch, {"/repos/o/r": _http_error(500)})
    assert snapshot["branchAheadBy"] == {}
    assert not any("/compare/" in u for u in urls)
    assert select_issue(snapshot, LABEL, NOW)["selected"] is None


def test_gather_does_not_swallow_programming_errors(monkeypatch):
    # The fail-conservative catch is for request failures only: an
    # AssertionError (here, the double's "unexpected URL") must propagate.
    with pytest.raises(AssertionError, match="unexpected URL"):
        _gather(monkeypatch, {"/repos/o/r": ({"default_branch": "main"}, {})})


def test_gather_makes_no_compare_when_nothing_is_a_candidate(monkeypatch):
    # The issue is not opted in, so its branch cannot change the pick: no
    # default-branch read, no compare — the cost stays at zero.
    unlabeled = [{"number": 565, "title": "t", "created_at": "2026-09-20T00:00:00Z",
                  "labels": [], "comments": 0}]
    snapshot, urls = _gather(monkeypatch, {}, issues_payload=unlabeled)
    assert snapshot["branchAheadBy"] == {}
    assert not any(u.endswith("/repos/o/r") or "/compare/" in u for u in urls)


def test_gather_percent_encodes_refs_but_keeps_slashes(monkeypatch):
    odd = "claude/issue-565-a#b"
    snapshot, urls = _gather(monkeypatch, {
        "/repos/o/r": ({"default_branch": "main"}, {}),
        "/compare/main...claude/issue-565-a%23b": ({"ahead_by": 0}, {}),
    }, branches=(odd,))
    assert snapshot["branchAheadBy"] == {odd: 0}
    assert any(u.endswith("/compare/main...claude/issue-565-a%23b") for u in urls)


# --------------------------------------------------------------------------
# The CLI threads the routine's label into the compare set
# --------------------------------------------------------------------------

def test_run_asks_for_compares_under_the_routines_label(monkeypatch, tmp_path):
    # design-run and the chunker call `run --label <theirs>`; the compare set
    # must follow that label, or a design-brief's orphan branch would never
    # be compared and would keep starving it.
    from backlog_burn import cli

    seen = {}

    def fake_gather(repo, token, required_label=LABEL, now=None):
        seen.update(repo=repo, label=required_label, now=now)
        return snap([issue(20, labels=["design-brief"])],
                    branches=["claude/issue-20-x"], ahead_by={"claude/issue-20-x": 0})

    monkeypatch.setattr(github, "gather_snapshot", fake_gather)
    out = tmp_path / "out"
    rc = cli.main(["run", "--repo", "o/r", "--label", "design-brief",
                   "--gh-output", str(out), "--summary", str(tmp_path / "sum")])
    assert rc == 0
    assert seen["label"] == "design-brief"
    assert seen["now"] is not None and seen["now"].tzinfo is not None
    assert out.read_text(encoding="utf-8") == "issue=20\n"
