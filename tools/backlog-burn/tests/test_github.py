"""Tests for the live GitHub snapshot layer.

The policy tests in ``test_select.py`` cover the pure selector; these cover the
I/O contract around it — pagination, the fail-loud page cap, the snapshot
normalisation (dropping PRs from the issues list, keeping whole comment
threads: body, createdAt, authorType), and ``_get``'s bounded retry on
transient failures. Higher-level tests monkeypatch ``_get`` so no request
leaves the process; the retry cases drive ``urlopen`` directly and patch
``_sleep`` so the suite never waits on the wall clock.
"""

from __future__ import annotations

import http.client
import io
import urllib.error

import pytest

from backlog_burn import github


def _fake_get(pages_by_url):
    """Build a `_get` replacement serving canned (body, headers) per URL."""
    def _get(url, token):
        for key, (body, headers) in pages_by_url.items():
            if key in url:
                return body, headers
        raise AssertionError(f"unexpected URL: {url}")
    return _get


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("u", code, "err", {}, io.BytesIO(b""))


class _JsonResp:
    """Minimal urlopen context-manager response returning a JSON body."""

    def __init__(self, payload: bytes = b'{"ok": true}'):
        self._payload = payload
        self.headers = {"Content-Type": "application/json"}

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# --------------------------------------------------------------------------
# _get retry (transient 5xx / connection errors)
# --------------------------------------------------------------------------

def test_get_retries_502_then_succeeds(monkeypatch):
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky(req, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise _http_error(502)
        return _JsonResp(b'{"ok": true}')

    monkeypatch.setattr(github.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(github, "_sleep", sleeps.append)
    monkeypatch.setattr(github.random, "uniform", lambda a, b: 0.0)

    body, headers = github._get("https://api.github.com/x", "t")
    assert body == {"ok": True}
    assert headers["content-type"] == "application/json"
    assert attempts["n"] == 2
    assert len(sleeps) == 1
    assert sleeps[0] == github._GET_BACKOFF_BASE_S


def test_get_closes_5xx_response_before_retry(monkeypatch):
    """A retryable HTTPError must close its response before sleep (#904)."""
    attempts = {"n": 0}
    events: list[str] = []

    def flaky(req, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            err = _http_error(502)
            orig_close = err.close

            def tracked_close():
                events.append("close")
                orig_close()

            err.close = tracked_close  # type: ignore[method-assign]
            raise err
        return _JsonResp(b'{"ok": true}')

    def tracked_sleep(seconds: float) -> None:
        events.append("sleep")

    monkeypatch.setattr(github.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(github, "_sleep", tracked_sleep)
    monkeypatch.setattr(github.random, "uniform", lambda a, b: 0.0)

    body, _ = github._get("https://api.github.com/x", "t")
    assert body == {"ok": True}
    assert attempts["n"] == 2
    assert events == ["close", "sleep"]


def test_get_persistent_5xx_raises_after_bounded_tries(monkeypatch):
    attempts = {"n": 0}
    sleeps: list[float] = []
    closes = {"n": 0}

    def always_502(req, timeout=None):
        attempts["n"] += 1
        err = _http_error(502)
        orig_close = err.close

        def tracked_close():
            closes["n"] += 1
            orig_close()

        err.close = tracked_close  # type: ignore[method-assign]
        raise err

    monkeypatch.setattr(github.urllib.request, "urlopen", always_502)
    monkeypatch.setattr(github, "_sleep", sleeps.append)
    monkeypatch.setattr(github.random, "uniform", lambda a, b: 0.0)

    with pytest.raises(urllib.error.HTTPError) as caught:
        github._get("https://api.github.com/x", "t")
    assert caught.value.code == 502
    assert attempts["n"] == github._GET_ATTEMPTS
    assert len(sleeps) == github._GET_ATTEMPTS - 1
    # Close only on the retry path (before each sleep), not on the final raise.
    assert closes["n"] == github._GET_ATTEMPTS - 1


def test_get_4xx_is_not_retried(monkeypatch):
    attempts = {"n": 0}

    def not_found(req, timeout=None):
        attempts["n"] += 1
        raise _http_error(404)

    monkeypatch.setattr(github.urllib.request, "urlopen", not_found)
    monkeypatch.setattr(github, "_sleep", lambda s: (_ for _ in ()).throw(
        AssertionError(f"4xx must not sleep; got {s}")
    ))

    with pytest.raises(urllib.error.HTTPError) as caught:
        github._get("https://api.github.com/x", "t")
    assert caught.value.code == 404
    assert attempts["n"] == 1


def test_get_connection_error_is_retried(monkeypatch):
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky(req, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise urllib.error.URLError("connection reset")
        return _JsonResp(b'{"ok": true}')

    monkeypatch.setattr(github.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(github, "_sleep", sleeps.append)
    monkeypatch.setattr(github.random, "uniform", lambda a, b: 0.0)

    body, _ = github._get("https://api.github.com/x", "t")
    assert body == {"ok": True}
    assert attempts["n"] == 2
    assert len(sleeps) == 1


def test_get_incomplete_read_is_retried(monkeypatch):
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky(req, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise http.client.IncompleteRead(b"partial")
        return _JsonResp(b'{"ok": true}')

    monkeypatch.setattr(github.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(github, "_sleep", sleeps.append)
    monkeypatch.setattr(github.random, "uniform", lambda a, b: 0.0)

    body, _ = github._get("https://api.github.com/x", "t")
    assert body == {"ok": True}
    assert attempts["n"] == 2
    assert len(sleeps) == 1
    assert sleeps[0] == github._GET_BACKOFF_BASE_S


def test_get_bad_status_line_is_retried(monkeypatch):
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky(req, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise http.client.BadStatusLine("")
        return _JsonResp(b'{"ok": true}')

    monkeypatch.setattr(github.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(github, "_sleep", sleeps.append)
    monkeypatch.setattr(github.random, "uniform", lambda a, b: 0.0)

    body, _ = github._get("https://api.github.com/x", "t")
    assert body == {"ok": True}
    assert attempts["n"] == 2
    assert len(sleeps) == 1
    assert sleeps[0] == github._GET_BACKOFF_BASE_S


# --------------------------------------------------------------------------
# _next_link
# --------------------------------------------------------------------------

def test_next_link_extracts_next():
    hdr = ('<https://api.github.com/x?page=2>; rel="next", '
           '<https://api.github.com/x?page=5>; rel="last"')
    assert github._next_link(hdr) == "https://api.github.com/x?page=2"


def test_next_link_absent():
    assert github._next_link('<https://api.github.com/x?page=5>; rel="last"') == ""
    assert github._next_link("") == ""


def test_next_link_refuses_off_host():
    """Pager must not follow a Link next URL off api.github.com (#904)."""
    with pytest.raises(ValueError, match="off API host"):
        github._next_link('<https://evil.example/x?page=2>; rel="next"')


def test_next_link_refuses_wrong_scheme():
    with pytest.raises(ValueError, match="off API host"):
        github._next_link('<http://api.github.com/x?page=2>; rel="next"')


# --------------------------------------------------------------------------
# _paginate
# --------------------------------------------------------------------------

def test_paginate_follows_next(monkeypatch):
    calls = {"n": 0}

    def _get(url, token):
        calls["n"] += 1
        if "page=2" in url:
            return [{"id": 3}], {}
        return [{"id": 1}, {"id": 2}], {"link": '<https://api.github.com/r?page=2>; rel="next"'}

    monkeypatch.setattr(github, "_get", _get)
    out = github._paginate("/r", token="t")
    assert [o["id"] for o in out] == [1, 2, 3]
    assert calls["n"] == 2


def test_paginate_raises_past_cap(monkeypatch):
    # Every page advertises a next link, so the loop only stops at the cap.
    monkeypatch.setattr(github, "_MAX_PAGES", 3)

    def _get(url, token):
        return [{"id": 1}], {"link": '<https://api.github.com/r?page=x>; rel="next"'}

    monkeypatch.setattr(github, "_get", _get)
    with pytest.raises(RuntimeError, match="pagination exceeded 3 pages"):
        github._paginate("/r", token="t")


# --------------------------------------------------------------------------
# gather_snapshot
# --------------------------------------------------------------------------

def test_gather_snapshot_normalizes_and_filters(monkeypatch):
    issues_payload = [
        {  # a real issue with a comment thread to fetch
            "number": 5, "title": "real", "created_at": "2026-08-01T00:00:00Z",
            "labels": [{"name": "autonomy-ok"}, {"name": "enhancement"}],
            "comments": 2,
        },
        {  # a PR masquerading in the issues endpoint — must be dropped
            "number": 6, "title": "a pr", "created_at": "2026-08-02T00:00:00Z",
            "labels": [], "comments": 0, "pull_request": {"url": "..."},
        },
        {  # a comment-free issue — no extra request, empty locks
            "number": 7, "title": "fresh", "created_at": "2026-08-03T00:00:00Z",
            "labels": [], "comments": 0,
        },
    ]
    comments_payload = [
        {"body": "🚢 SHIP-LOCK — claimed\n\n<!-- design-run-ship-lock:v1 -->", "created_at": "2026-08-04T00:00:00Z",
         "user": {"login": "bot-pat", "type": "User"}},
        {"body": "just a normal comment", "created_at": "2026-08-05T00:00:00Z",
         "user": {"login": "owner", "type": "User"}},
        {"body": "status update from a workflow", "created_at": "2026-08-06T00:00:00Z",
         "user": {"login": "github-actions[bot]", "type": "Bot"}},
        {"body": "author deleted", "created_at": "2026-08-07T00:00:00Z"},
    ]
    pulls_payload = [
        {"number": 20, "head": {"ref": "claude/issue-5-x"}, "body": "Closes #5"},
    ]
    branches_payload = [{"name": "main"}, {"name": "claude/issue-5-x"}]

    calls: list[str] = []
    fake_get = _fake_get({
        "/issues?state=open": (issues_payload, {}),
        "/issues/5/comments": (comments_payload, {}),
        "/pulls?state=open": (pulls_payload, {}),
        "/branches": (branches_payload, {}),
    })

    def tracked_get(url, token):
        calls.append(url)
        return fake_get(url, token)

    monkeypatch.setattr(github, "_get", tracked_get)

    snap = github.gather_snapshot("owner/repo", "t")

    # PRs dropped from the issues list; both real issues kept.
    assert [i["number"] for i in snap["issues"]] == [5, 7]
    issue5 = snap["issues"][0]
    assert issue5["labels"] == ["autonomy-ok", "enhancement"]
    assert issue5["createdAt"] == "2026-08-01T00:00:00Z"
    # The whole thread is kept, normalised to body/createdAt/authorType — no
    # marker filtering here, because which prefixes mean a lock, a decline or
    # a machine post is policy and lives in select.py behind its tests. The
    # timestamps date stale locks and decline cooldowns; the author type is
    # the marker-free leg of the run-vs-owner test (a deleted author types
    # as "", which policy reads as a human).
    assert issue5["comments"] == [
        {"body": "🚢 SHIP-LOCK — claimed\n\n<!-- design-run-ship-lock:v1 -->", "createdAt": "2026-08-04T00:00:00Z",
         "authorType": "User", "authorLogin": "bot-pat", "ownerLogin": "owner"},
        {"body": "just a normal comment", "createdAt": "2026-08-05T00:00:00Z",
         "authorType": "User", "authorLogin": "owner", "ownerLogin": "owner"},
        {"body": "status update from a workflow", "createdAt": "2026-08-06T00:00:00Z",
         "authorType": "Bot", "authorLogin": "github-actions[bot]", "ownerLogin": "owner"},
        {"body": "author deleted", "createdAt": "2026-08-07T00:00:00Z",
         "authorType": "", "authorLogin": "", "ownerLogin": "owner"},
    ]
    # A comment-free issue gets an empty thread — and, the guard that keeps
    # gather cheap, no comment request is made for it at all.
    assert snap["issues"][1]["comments"] == []
    assert not any("/issues/7/comments" in url for url in calls)
    # PRs normalised to number/headRefName/body.
    assert snap["openPRs"] == [{"number": 20, "headRefName": "claude/issue-5-x", "body": "Closes #5"}]
    assert snap["branches"] == ["main", "claude/issue-5-x"]
