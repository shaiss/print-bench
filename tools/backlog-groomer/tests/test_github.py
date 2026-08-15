"""Gather-layer tests — ``_get`` is the single network seam.

Every test monkeypatches ``_get``; no request ever leaves the process (the
same discipline ``tools/backlog-burn/tests/test_github.py`` states).  The
fail-loud pagination cap is proved by lowering it and expecting a raise —
a silently-truncated snapshot would make the report lie about coverage.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backlog_groomer import github

NOW = datetime(2026, 8, 15, 6, 0, 0, tzinfo=timezone.utc)


def _issues_pages():
    page1 = [
        {
            "number": 1,
            "title": "First issue",
            "labels": [{"name": "bug"}],
            "created_at": "2026-08-01T00:00:00Z",
            "updated_at": "2026-08-02T00:00:00Z",
            "sub_issues_summary": {"total": 2, "completed": 1},
        },
        {
            "number": 2,
            "title": "A PR in issue clothing",
            "labels": [],
            "created_at": "2026-08-01T00:00:00Z",
            "updated_at": "2026-08-01T00:00:00Z",
            "pull_request": {"url": "..."},
        },
    ]
    page2 = [
        {
            "number": 3,
            "title": "Second-page issue",
            "labels": [],
            "created_at": "2026-08-03T00:00:00Z",
            "updated_at": "2026-08-04T00:00:00Z",
        },
    ]
    return page1, page2


def fake_get(monkeypatch, calls):
    page1, page2 = _issues_pages()
    responses = {
        f"{github.API_ROOT}/repos/o/r/issues?state=open&per_page=100":
            (page1, '<https://next.example/issues2>; rel="next"'),
        "https://next.example/issues2": (page2, ""),
        f"{github.API_ROOT}/repos/o/r/pulls?state=open&per_page=100":
            ([{"number": 9, "body": None}, {"number": 8, "body": "Fixes #1"}], ""),
    }

    def _fake(url, token):
        calls.append(url)
        return responses[url]

    monkeypatch.setattr(github, "_get", _fake)


def test_gather_paginates_maps_and_drops_prs(monkeypatch):
    calls: list[str] = []
    fake_get(monkeypatch, calls)
    snapshot = github.gather_snapshot("o/r", "tok", now=NOW)

    assert [i["number"] for i in snapshot["issues"]] == [1, 3]  # PR entry dropped
    first = snapshot["issues"][0]
    assert first["labels"] == ["bug"]
    assert first["createdAt"] == "2026-08-01T00:00:00Z"
    assert first["subIssues"] == {"total": 2, "completed": 1}
    assert "subIssues" not in snapshot["issues"][1]  # absent upstream stays absent

    # A null PR body normalises to "" so the detectors never see None.
    assert snapshot["openPRs"] == [{"number": 9, "body": ""}, {"number": 8, "body": "Fixes #1"}]

    assert snapshot["generatedAt"] == NOW.isoformat()
    assert len(calls) == 3  # two issue pages + one PR page


def test_pagination_cap_raises_instead_of_truncating(monkeypatch):
    def endless(url, token):
        return [], '<https://next.example/again>; rel="next"'

    monkeypatch.setattr(github, "_get", endless)
    monkeypatch.setattr(github, "_MAX_PAGES", 3)
    with pytest.raises(RuntimeError, match="more than 3 pages"):
        github.gather_snapshot("o/r", "tok", now=NOW)
