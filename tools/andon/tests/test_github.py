"""Gather-layer tests — ``_get`` is the single network seam.

Every test monkeypatches ``_get``; no request ever leaves the process (the
groomer's discipline). The fail-loud pagination cap is proved by lowering it
and expecting a raise — a truncated listing could miss the open status issue
and open a duplicate beside it.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from andon import github, policy

LIST_URL = f"{github.API_ROOT}/repos/o/r/issues?state=open&labels=andon-cord&per_page=100"


def _issue(number, created, body=policy.MARKER + "\nbody", **extra):
    return {"number": number, "created_at": created, "body": body, **extra}


def _serve(monkeypatch, pages, calls=None):
    """Serve ``pages`` (a list of item lists) as a Link-chained listing."""
    responses = {}
    url = LIST_URL
    for i, page in enumerate(pages):
        nxt = f"https://next.example/p{i + 1}" if i + 1 < len(pages) else None
        responses[url] = (page, f'<{nxt}>; rel="next"' if nxt else "")
        url = nxt

    def _fake(url, token):
        if calls is not None:
            calls.append((url, token))
        return responses[url]

    monkeypatch.setattr(github, "_get", _fake)


def test_empty_listing_means_no_open_issue(monkeypatch):
    calls = []
    _serve(monkeypatch, [[]], calls)
    assert github.find_open_status_issue("o/r", "tok") is None
    assert calls == [(LIST_URL, "tok")]


def test_oldest_marked_issue_wins_across_pages(monkeypatch, capsys):
    _serve(monkeypatch, [
        [_issue(10, "2026-09-03T00:00:00Z")],
        [_issue(4, "2026-09-01T00:00:00Z"), _issue(12, "2026-09-05T00:00:00Z")],
    ])
    found = github.find_open_status_issue("o/r", "")
    assert found == policy.OpenIssue(4, datetime(2026, 9, 1, tzinfo=timezone.utc))
    # More than one candidate is never silent.
    err = capsys.readouterr().err
    assert "3 open andon status issues" in err and "#4" in err


def test_single_candidate_logs_nothing(monkeypatch, capsys):
    _serve(monkeypatch, [[_issue(4, "2026-09-01T00:00:00Z")]])
    assert github.find_open_status_issue("o/r", "").number == 4
    assert capsys.readouterr().err == ""


def test_pull_requests_are_dropped(monkeypatch):
    _serve(monkeypatch, [[_issue(3, "2026-08-01T00:00:00Z", pull_request={"url": "..."}),
                          _issue(9, "2026-09-01T00:00:00Z")]])
    assert github.find_open_status_issue("o/r", "").number == 9


def test_marker_less_bodies_are_dropped(monkeypatch):
    # A human-applied label on an unrelated issue is not the status record.
    _serve(monkeypatch, [[_issue(3, "2026-08-01T00:00:00Z", body="not ours"),
                          _issue(5, "2026-08-02T00:00:00Z", body=None),
                          _issue(6, "2026-08-03T00:00:00Z", body="x" + policy.MARKER),
                          _issue(9, "2026-09-01T00:00:00Z")]])
    assert github.find_open_status_issue("o/r", "").number == 9


def test_only_marker_less_bodies_means_none(monkeypatch):
    _serve(monkeypatch, [[_issue(3, "2026-08-01T00:00:00Z", body="not ours")]])
    assert github.find_open_status_issue("o/r", "") is None


def test_pagination_cap_raises_instead_of_truncating(monkeypatch):
    monkeypatch.setattr(github, "_get",
                        lambda url, token: ([], '<https://next.example/again>; rel="next"'))
    monkeypatch.setattr(github, "_MAX_PAGES", 3)
    with pytest.raises(RuntimeError, match="more than 3 pages"):
        github.find_open_status_issue("o/r", "tok")


def test_non_list_page_raises_instead_of_extending(monkeypatch):
    monkeypatch.setattr(github, "_get",
                        lambda url, token: ({"message": "API rate limit exceeded"}, ""))
    with pytest.raises(RuntimeError, match="non-list response"):
        github.find_open_status_issue("o/r", "tok")


def test_request_carries_the_andon_user_agent_and_bearer(monkeypatch):
    seen = {}

    class _Resp:
        headers = {"Link": ""}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"[]"

    def _urlopen(req, timeout):
        seen["ua"] = req.get_header("User-agent")
        seen["auth"] = req.get_header("Authorization")
        seen["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(github.urllib.request, "urlopen", _urlopen)
    assert github.find_open_status_issue("o/r", "tok") is None
    assert seen == {"ua": "print-bench-andon", "auth": "Bearer tok", "timeout": github._TIMEOUT_S}
