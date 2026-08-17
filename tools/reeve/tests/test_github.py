"""Run-health gather tests — ``_get`` is the single network seam.

Every test monkeypatches ``_get``; no request ever leaves the process (the
same discipline ``tools/backlog-groomer/tests/test_github.py`` states). The
runs endpoint returns an object keyed ``workflow_runs`` — never a list — so
the unwrap has its own coverage, and the fail-loud pagination cap is proved
by lowering it and expecting a raise.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from reeve import github

REPO = "o/r"


def _runs_url(wf):
    return (f"{github.API_ROOT}/repos/{REPO}/actions/workflows/{wf}/runs"
            f"?status=completed&per_page={github._RUNS_FETCHED}&exclude_pull_requests=true")


def _runs_body(wf, conclusions):
    return {
        "total_count": len(conclusions),
        "workflow_runs": [
            {"conclusion": c, "created_at": f"2026-08-{16 - i:02d}T05:23:00Z",
             "html_url": f"https://github.com/{REPO}/actions/runs/{wf}/{i}"}
            for i, c in enumerate(conclusions)
        ],
    }


def _lock(body, created_at):
    return {"body": body, "created_at": created_at}


def _responses():
    """URL -> (json body, Link header) map shaped like the real endpoints."""
    responses = {}
    for wf in github.ROUTINE_WORKFLOWS:
        conclusions = ["success"] if wf != "design-run.yml" else ["cancelled", "failure"]
        responses[_runs_url(wf)] = (_runs_body(wf, conclusions), "")

    issues_page1 = [
        # An entry from the interleaved PR listing — must be dropped.
        {"number": 2, "title": "A PR in issue clothing", "comments": 3,
         "pull_request": {"url": "..."}},
        # Zero comments — the comments endpoint must never be fetched for it.
        {"number": 3, "title": "Quiet issue", "comments": 0},
        # An active lock (the #312 ghost).
        {"number": 281, "title": "Design brief: NUGGS desiccant tower", "comments": 2},
    ]
    issues_page2 = [
        # Latest lock comment is WITHDRAWN — released, must be omitted.
        {"number": 283, "title": "Design brief: released", "comments": 2},
        # Comments but none of them a lock.
        {"number": 290, "title": "Chatty issue", "comments": 1},
    ]
    responses[f"{github.API_ROOT}/repos/{REPO}/issues?state=open&per_page=100"] = (
        issues_page1, '<https://next.example/issues2>; rel="next"')
    responses["https://next.example/issues2"] = (issues_page2, "")

    responses[f"{github.API_ROOT}/repos/{REPO}/issues/281/comments?per_page=100"] = ([
        _lock("🚢 SHIP-LOCK claimed by run 1", "2026-08-10T05:23:00Z"),
        # The newest lock's first NON-BLANK line is the marker line — leading
        # blank lines must not hide it.
        _lock("\n\n  🚢 SHIP-LOCK claimed by run 2\n\ndetails", "2026-08-14T05:23:00Z"),
    ], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/283/comments?per_page=100"] = ([
        _lock("🚢 SHIP-LOCK claimed by run 3", "2026-08-10T05:23:00Z"),
        _lock("🚢 SHIP-LOCK WITHDRAWN — stale claim", "2026-08-11T05:23:00Z"),
    ], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/290/comments?per_page=100"] = ([
        {"body": "just a comment", "created_at": "2026-08-10T05:23:00Z"},
    ], "")

    responses[f"{github.API_ROOT}/repos/{REPO}/pulls?state=open&per_page=100"] = ([
        {"number": 9, "head": {"ref": "claude/issue-100-x"}, "body": None},
        {"number": 8, "head": {"ref": "feature"}, "body": "Fixes #1"},
    ], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/branches?per_page=100"] = ([
        {"name": "main"}, {"name": "claude/issue-100-x"},
    ], "")
    return responses


def fake_get(monkeypatch, calls):
    responses = _responses()

    def _fake(url, token):
        calls.append(url)
        return responses[url]

    monkeypatch.setattr(github, "_get", _fake)


def test_gather_unwraps_the_runs_object(monkeypatch):
    # /actions/workflows/<file>/runs returns an OBJECT keyed workflow_runs,
    # not a list — one plain _get and unwrap, never _paged.
    calls: list[str] = []
    fake_get(monkeypatch, calls)
    health = github.gather_run_health(REPO, "tok")
    by_file = {w["file"]: w["runs"] for w in health["workflows"]}
    assert sorted(by_file) == sorted(github.ROUTINE_WORKFLOWS)
    assert by_file["design-run.yml"] == [
        {"conclusion": "cancelled", "createdAt": "2026-08-16T05:23:00Z",
         "url": f"https://github.com/{REPO}/actions/runs/design-run.yml/0"},
        {"conclusion": "failure", "createdAt": "2026-08-15T05:23:00Z",
         "url": f"https://github.com/{REPO}/actions/runs/design-run.yml/1"},
    ]


def test_gather_latest_lock_wins_and_withdrawn_releases(monkeypatch):
    calls: list[str] = []
    fake_get(monkeypatch, calls)
    health = github.gather_run_health(REPO, "tok")
    # #281's newest lock is active (blank-padded first line still counts);
    # #283's newest is WITHDRAWN; #290 has no lock at all.
    assert health["issues"] == [
        {"number": 281, "title": "Design brief: NUGGS desiccant tower",
         "lockCreatedAt": "2026-08-14T05:23:00Z"},
    ]


def test_gather_drops_pr_entries_from_the_issues_listing(monkeypatch):
    calls: list[str] = []
    fake_get(monkeypatch, calls)
    github.gather_run_health(REPO, "tok")
    assert not any("/issues/2/comments" in url for url in calls)


def test_gather_fetches_comments_only_when_count_positive(monkeypatch):
    calls: list[str] = []
    fake_get(monkeypatch, calls)
    github.gather_run_health(REPO, "tok")
    assert not any("/issues/3/comments" in url for url in calls)
    assert any("/issues/281/comments" in url for url in calls)


def test_gather_maps_prs_and_branches(monkeypatch):
    calls: list[str] = []
    fake_get(monkeypatch, calls)
    health = github.gather_run_health(REPO, "tok")
    # A null PR body normalises to "" so the detectors never see None.
    assert health["openPRs"] == [
        {"number": 9, "headRefName": "claude/issue-100-x", "body": ""},
        {"number": 8, "headRefName": "feature", "body": "Fixes #1"},
    ]
    assert health["branches"] == ["main", "claude/issue-100-x"]
    assert health["gatheredAt"].endswith("Z")


def test_missing_workflow_runs_key_raises(monkeypatch):
    # An error payload has no workflow_runs list — fail loud at the seam.
    monkeypatch.setattr(github, "_get", lambda url, token: ({"message": "Not Found"}, ""))
    with pytest.raises(RuntimeError, match="no workflow_runs list"):
        github.gather_run_health(REPO, "tok")


def test_pagination_cap_raises_instead_of_truncating(monkeypatch):
    responses = _responses()

    def endless(url, token):
        if "/issues?" in url or url.startswith("https://next.example/"):
            return [], '<https://next.example/again>; rel="next"'
        return responses[url]

    monkeypatch.setattr(github, "_get", endless)
    monkeypatch.setattr(github, "_MAX_PAGES", 3)
    with pytest.raises(RuntimeError, match="more than 3 pages"):
        github.gather_run_health(REPO, "tok")


def test_non_list_page_raises_instead_of_extending(monkeypatch):
    responses = _responses()

    def bad_issues(url, token):
        if "/issues?" in url:
            return {"message": "API rate limit exceeded"}, ""
        return responses[url]

    monkeypatch.setattr(github, "_get", bad_issues)
    with pytest.raises(RuntimeError, match="non-list response"):
        github.gather_run_health(REPO, "tok")


def test_github_module_stays_get_only():
    # The reeve-side copy of the groomer's guard: github.py may import urllib
    # and nothing else network-capable, and no HTTP write verb appears in it
    # (test_detectors.py scans the whole package; this pins the one module
    # allowed a network import).
    src = pathlib.Path(github.__file__)
    tree = ast.parse(src.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    assert not names & {"socket", "http", "subprocess", "requests"}
    verb_re = re.compile(r"\b(POST|PATCH|PUT|DELETE)\b")
    match = verb_re.search(src.read_text(encoding="utf-8"))
    assert match is None, f"github.py mentions {match.group(0) if match else ''}"
