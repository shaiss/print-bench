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


# ---------------------------------------------------------------------------
# _get_with_retry — transient blips are absorbed, real errors surface at once
# ---------------------------------------------------------------------------

def _http_error(status):
    return github.urllib.error.HTTPError("https://x", status, "err", hdrs=None, fp=None)


def _flaky(monkeypatch, outcomes):
    """Serve ``outcomes`` in order: an exception instance is raised, anything
    else is returned. Records every call and every sleep; no sleep is real."""
    calls, sleeps = [], []
    queue = list(outcomes)

    def _fake(url, token):
        calls.append((url, token))
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(github, "_get", _fake)
    monkeypatch.setattr(github.time, "sleep", lambda s: sleeps.append(s))
    return calls, sleeps


def test_retry_absorbs_two_503s_then_returns_the_result(monkeypatch):
    calls, sleeps = _flaky(monkeypatch, [_http_error(503), _http_error(503), ([_issue(4, "2026-09-01T00:00:00Z")], "")])
    assert github.find_open_status_issue("o/r", "tok").number == 4
    assert len(calls) == 3
    assert sleeps == list(github._RETRY_DELAYS)


@pytest.mark.parametrize("status", sorted(github._RETRY_STATUSES))
def test_every_transient_status_is_retried_once_then_served(monkeypatch, status):
    calls, sleeps = _flaky(monkeypatch, [_http_error(status), ([], "")])
    assert github.find_open_status_issue("o/r", "tok") is None
    assert len(calls) == 2 and sleeps == [github._RETRY_DELAYS[0]]


@pytest.mark.parametrize("exc", [
    github.urllib.error.URLError("connection reset"),
    TimeoutError("timed out"),
])
def test_network_errors_and_socket_timeouts_are_retried(monkeypatch, exc):
    calls, sleeps = _flaky(monkeypatch, [exc, ([], "")])
    assert github.find_open_status_issue("o/r", "tok") is None
    assert len(calls) == 2 and len(sleeps) == 1


@pytest.mark.parametrize("status", [401, 404, 422])
def test_a_real_http_error_is_raised_immediately_with_one_call(monkeypatch, status):
    # Waiting cannot fix a bad token, a missing repo or a bad query; the
    # step must fail on the first attempt, not after six silent seconds.
    calls, sleeps = _flaky(monkeypatch, [_http_error(status), ([], "")])
    with pytest.raises(github.urllib.error.HTTPError) as info:
        github.find_open_status_issue("o/r", "tok")
    assert info.value.code == status
    assert len(calls) == 1 and sleeps == []


def test_three_503s_raise_after_exactly_three_calls(monkeypatch, capsys):
    # The bound: the last transient error is re-raised, never swallowed, so
    # a real outage still reds the step instead of deciding from nothing.
    calls, sleeps = _flaky(monkeypatch, [_http_error(503), _http_error(503), _http_error(503), ([], "")])
    with pytest.raises(github.urllib.error.HTTPError) as info:
        github.find_open_status_issue("o/r", "tok")
    assert info.value.code == 503
    assert len(calls) == 3
    assert sleeps == list(github._RETRY_DELAYS)
    assert capsys.readouterr().err.count("transient GitHub API failure") == 2


def test_a_non_http_non_network_error_is_never_retried(monkeypatch):
    # Negative control on the classifier: a programming error is not a blip.
    calls, sleeps = _flaky(monkeypatch, [ValueError("boom"), ([], "")])
    with pytest.raises(ValueError):
        github.find_open_status_issue("o/r", "tok")
    assert len(calls) == 1 and sleeps == []


def test_retry_budget_is_short_enough_for_the_job_bound():
    # Three attempts, two sleeps summing to seconds — never minutes.
    assert len(github._RETRY_DELAYS) == 2
    assert sum(github._RETRY_DELAYS) < 60


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
