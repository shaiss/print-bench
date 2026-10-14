"""github.Client — GET-only, ETag, cap, floor, pacing, pagination (docs/provenance.md §API budget).

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items);
replace the skip with the test.
"""

from __future__ import annotations

import json
import os
from urllib.parse import parse_qs, urlsplit

import pytest

from provenance import github
from provenance.github import (GONE, APIError, Budget, BudgetExhausted, Client, GraphQLUnavailable,
                               Truncated)

REPO = "shaiss/print-bench"
TOKEN = "ghs_SECRETTOKENVALUE"
BASE = f"https://api.github.com/repos/{REPO}"


class Transport:
    """A canned transport: ``script`` is a list of responses (or exceptions) served in order, or a
    callable ``(method, url, headers, body) -> response``. Every call is recorded."""

    def __init__(self, script):
        self.script = script
        self.calls: list[tuple[str, str, dict, bytes | None]] = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        if callable(self.script):
            r = self.script(method, url, headers, body)
        else:
            r = self.script.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


def ok(body, headers=None, status=200):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    return status, dict({"X-RateLimit-Remaining": "4000", "X-RateLimit-Reset": "0"}, **(headers or {})), data


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t
        self.sleeps: list[float] = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def client(script, *, max_requests=None, floor=500, pace=False, deadline=None, cache_dir=None, clock=None):
    clock = clock or Clock()
    t = Transport(script)
    c = Client(repo=REPO, token=TOKEN, budget=Budget(max_requests=max_requests, floor=floor, pace=pace,
                                                       deadline_epoch=deadline),
               cache_dir=cache_dir, transport=t, sleep=clock.sleep, clock=clock)
    return c, t, clock


def test_get_sends_if_none_match_and_304_is_free(tmp_path):
    """A cached ETag is sent as If-None-Match; a 304 returns the cached body, increments budget.not_modified and NOT budget.used."""
    c, t, _ = client([ok({"id": 1}, {"ETag": '"abc"'}), (304, {"ETag": '"abc"'}, b"")], cache_dir=str(tmp_path))
    assert c.get("/pulls/1") == {"id": 1}
    assert "If-None-Match" not in t.calls[0][2]
    assert c.get("/pulls/1") == {"id": 1}
    assert t.calls[1][2]["If-None-Match"] == '"abc"'
    assert (c.budget.used, c.budget.not_modified) == (1, 1)
    method, url, headers, body = t.calls[0]
    assert (method, url, body) == ("GET", f"{BASE}/pulls/1", None)
    assert headers["Accept"] == "application/vnd.github+json" and headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert headers["User-Agent"] == "print-bench-provenance" and headers["Authorization"] == f"Bearer {TOKEN}"
    # Params are sorted into the query; a second URL is a second cache entry.
    c2, t2, _ = client([ok([])], cache_dir=str(tmp_path))
    c2.get("/pulls", {"state": "closed", "direction": "desc"})
    assert t2.calls[0][1] == f"{BASE}/pulls?direction=desc&state=closed"
    with pytest.raises(ValueError):
        c2.get("pulls")


def test_request_cap_raises_before_sending():
    """With max_requests=5 the 6th request raises BudgetExhausted before the transport is called (P1e: 'a request cap of 5 stops cleanly')."""
    c, t, _ = client(lambda *a: ok({}), max_requests=5)
    for i in range(5):
        c.get(f"/issues/{i}")
    with pytest.raises(BudgetExhausted, match="cap 5"):
        c.get("/issues/6")
    assert len(t.calls) == 5 and c.budget.used == 5 and c.budget.stopped
    with pytest.raises(BudgetExhausted):  # sticky: every later request stops too
        c.get("/issues/7")
    assert len(t.calls) == 5


def test_scheduled_floor_stops_and_dispatch_floor_sleeps():
    """Remaining < rate_floor: pace=False raises BudgetExhausted; pace=True calls sleep(reset - now + 5) and continues; a sleep that would pass deadline_epoch (the capture deadline) raises instead."""
    low = {"X-RateLimit-Remaining": "10", "X-RateLimit-Reset": str(1_000_100)}
    c, t, clock = client([ok({}, low), ok({})], pace=False)
    c.get("/a")
    with pytest.raises(BudgetExhausted, match="floor"):
        c.get("/b")
    assert len(t.calls) == 1 and clock.sleeps == []

    c, t, clock = client([ok({}, low), ok({"x": 1})], pace=True)
    c.get("/a")
    assert c.get("/b") == {"x": 1}
    assert clock.sleeps == [100 + 5] and len(t.calls) == 2

    c, t, clock = client([ok({}, low), ok({})], pace=True, deadline=1_000_050)
    c.get("/a")
    with pytest.raises(BudgetExhausted, match="deadline"):
        c.get("/b")
    assert clock.sleeps == [] and len(t.calls) == 1

    # The deadline alone stops a request (capture deadline reached), before it is sent.
    c, t, clock = client([ok({})], deadline=999_999)
    with pytest.raises(BudgetExhausted, match="deadline"):
        c.get("/a")
    assert t.calls == []

    # The floor guards the REST pool: a low GraphQL pool (its own resource) does not stop REST.
    gql_low = (200, {"X-RateLimit-Resource": "graphql", "X-RateLimit-Remaining": "10"},
               json.dumps({"data": {"repository": {"issueOrPullRequest": {"lastEditedAt": None}}}}).encode())
    c, t, clock = client([gql_low, ok({"z": 1})], pace=False)
    c.graphql_issue_edited(1)
    assert c.get("/b") == {"z": 1} and c.budget.last_remaining == 4000

    # A primary rate-limit 403 (remaining 0): a schedule stops, a dispatch waits for the reset.
    limited = (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(1_000_030)}, b'{"message": "API rate limit exceeded"}')
    c, t, _ = client([limited])
    with pytest.raises(BudgetExhausted, match="rate limit"):
        c.get("/a")
    c, t, clock = client([limited, ok({"y": 2})], pace=True)
    assert c.get("/a") == {"y": 2} and clock.sleeps == [35]


def test_link_next_is_followed_on_api_host_only():
    """rel=next on api.github.com is followed (including a /repositories/<id>/ link rewritten to /repos/<owner>/<repo>/); a next link to any other host is refused."""
    nxt = '<https://api.github.com/repositories/123456/actions/artifacts?per_page=100&page=2>; rel="next", <https://api.github.com/repositories/123456/actions/artifacts?page=9>; rel="last"'
    c, t, _ = client([ok({"artifacts": [1, 2]}, {"Link": nxt}), ok({"artifacts": [3]})])
    assert c.get_paged("/actions/artifacts", key="artifacts") == [1, 2, 3]
    assert t.calls[0][1] == f"{BASE}/actions/artifacts?per_page=100"
    assert t.calls[1][1] == f"{BASE}/actions/artifacts?per_page=100&page=2"
    for evil in ('<https://evil.example.com/repos/shaiss/print-bench/x?page=2>; rel="next"',
                 '<http://api.github.com/repos/shaiss/print-bench/x?page=2>; rel="next"',
                 '<https://api.github.com/repos/other/repo/x?page=2>; rel="next"'):
        c, t, _ = client([ok([1], {"Link": evil}), ok([2])])
        with pytest.raises(APIError, match="refusing a next link"):
            c.get_paged("/x")
        assert len(t.calls) == 1


def _pages(n, total=None):
    def script(method, url, headers, body):
        page = int(parse_qs(urlsplit(url).query).get("page", ["1"])[0])
        link = {"Link": f'<{BASE}/actions/runs?per_page=100&page={page + 1}>; rel="next"'} if page < n else {}
        return ok({"total_count": total, "workflow_runs": [page]}, link)
    return script


def test_iter_pages_is_lazy_and_reports_total_count():
    """iter_pages yields (items, total_count) one GET per page and sends no further request once the caller stops iterating (the artifact scan's early stop); past max_pages raises Truncated."""
    c, t, _ = client(_pages(3, total=250))
    it = c.iter_pages("/actions/runs", {"created": "2026-10-12T00:00:00Z..2026-10-12T23:59:59Z"}, key="workflow_runs")
    assert t.calls == []                                           # a generator: nothing sent yet
    assert next(it) == ([1], 250) and len(t.calls) == 1
    assert "created=2026-10-12T00%3A00%3A00Z..2026-10-12T23%3A59%3A59Z" in t.calls[0][1]
    assert next(it) == ([2], 250) and len(t.calls) == 2
    it.close()
    assert len(t.calls) == 2
    c, t, _ = client(_pages(3))
    got = []
    with pytest.raises(Truncated):
        for items, total in c.iter_pages("/actions/runs", key="workflow_runs", max_pages=2):
            got.append((items, total))
    assert got == [([1], None), ([2], None)] and len(t.calls) == 2
    c, t, _ = client([ok({"no": "list"})])
    with pytest.raises(APIError, match="not a JSON list"):
        list(c.iter_pages("/x"))


def test_truncation_raises():
    """More pages than max_pages raises Truncated, never a short list."""
    c, t, _ = client(_pages(4))
    with pytest.raises(Truncated, match="more than 3 pages"):
        c.get_paged("/actions/runs", key="workflow_runs", max_pages=3)
    c, t, _ = client(_pages(3))
    assert c.get_paged("/actions/runs", key="workflow_runs", max_pages=3) == [1, 2, 3]


def test_retries_5xx_and_secondary_limits_not_404():
    """5xx / 403+Retry-After retried 3x with backoff; 404/410 return GONE; 401/422 raise APIError."""
    c, t, clock = client([(502, {}, b""), (503, {}, b""), ok({"ok": 1})])
    assert c.get("/a") == {"ok": 1} and clock.sleeps == [2, 4] and len(t.calls) == 3
    assert c.budget.used == 3                                     # retries are responses too
    c, t, clock = client([(500, {}, b"")] * 4)
    with pytest.raises(APIError, match="HTTP 500 GET /a") as exc:
        c.get("/a")
    assert exc.value.status == 500 and clock.sleeps == [2, 4, 8] and len(t.calls) == 4
    c, t, clock = client([(403, {"Retry-After": "30"}, b"{}"), ok({"ok": 2})])
    assert c.get("/a") == {"ok": 2} and clock.sleeps == [30]
    c, t, clock = client([(403, {}, b'{"message": "You have exceeded a secondary rate limit"}'), ok({"ok": 3})])
    assert c.get("/a") == {"ok": 3} and clock.sleeps == [2]
    c, t, clock = client([TimeoutError("read timed out"), ConnectionResetError(), ok({"ok": 4})])
    assert c.get("/a") == {"ok": 4} and clock.sleeps == [2, 4]
    c, t, clock = client([TimeoutError()] * 4)
    with pytest.raises(APIError, match="transport failure"):
        c.get("/a")
    for status in (404, 410):
        c, t, clock = client([(status, {}, b"{}")])
        assert c.get("/a") is GONE and len(t.calls) == 1 and clock.sleeps == []
    for status in (401, 422, 403):
        c, t, clock = client([(status, {}, b"{}"), ok({})])
        with pytest.raises(APIError) as exc:
            c.get("/a")
        assert exc.value.status == status and len(t.calls) == 1 and clock.sleeps == []
    c, t, _ = client([(404, {}, b"{}")])
    with pytest.raises(APIError) as exc:
        c.get_paged("/actions/runs/1/jobs", key="jobs")
    assert exc.value.status == 404                                # a list has no GONE form
    c, t, _ = client([(301, {"Location": "https://evil.example.com/"}, b"")])
    with pytest.raises(APIError, match="HTTP 301"):
        c.get("/a")


def _gql(data=None, errors=None, status=200):
    payload = {"data": data} if errors is None else {"data": data, "errors": errors}
    return status, {"X-RateLimit-Remaining": "4000"}, json.dumps(payload).encode()


def test_graphql_unavailable_on_403():
    """A 403 or an errors payload from the GraphQL endpoint raises GraphQLUnavailable."""
    for resp in ((403, {}, b'{"message": "Resource not accessible by integration"}'),
                 _gql(None, errors=[{"message": "boom"}]), (200, {}, b"not json"),
                 _gql({"repository": {"issueOrPullRequest": None}})):
        c, t, _ = client([resp])
        with pytest.raises(GraphQLUnavailable):
            c.graphql_pr_threads(636)
    c, t, _ = client([(502, {}, b"")] * 4)
    with pytest.raises(GraphQLUnavailable):
        c.graphql_issue_edited(592)
    assert len(t.calls) == 4


def test_graphql_parser_on_canned_responses():
    """Critique 27: the production parser — exercised nowhere else, the sandbox returns 403 — maps canned reviewThreads responses (two pages via pageInfo.endCursor, an outdated thread, a thread with no comments) to {nodes: [{first_comment_id, resolved, outdated}], last_edited_at}, and an issue response to lastEditedAt."""
    page1 = {"repository": {"issueOrPullRequest": {
        "lastEditedAt": "2026-09-12T01:00:00Z",
        "reviewThreads": {"totalCount": 3, "pageInfo": {"hasNextPage": True, "endCursor": "Y3Vyc29yOjI="},
                          "nodes": [{"isResolved": True, "isOutdated": False, "comments": {"nodes": [{"databaseId": 11}]}},
                                    {"isResolved": False, "isOutdated": True, "comments": {"nodes": [{"databaseId": 12}]}}]}}}}
    page2 = {"repository": {"issueOrPullRequest": {
        "lastEditedAt": "2026-09-12T01:00:00Z",
        "reviewThreads": {"totalCount": 3, "pageInfo": {"hasNextPage": False, "endCursor": None},
                          "nodes": [{"isResolved": False, "isOutdated": False, "comments": {"nodes": []}}]}}}}
    c, t, _ = client([_gql(page1), _gql(page2)])
    got = c.graphql_pr_threads(636)
    assert got == {"last_edited_at": "2026-09-12T01:00:00Z", "nodes": [
        {"first_comment_id": 11, "outdated": False, "resolved": True},
        {"first_comment_id": 12, "outdated": True, "resolved": False},
        {"first_comment_id": None, "outdated": False, "resolved": False}]}
    bodies = [json.loads(b) for _, _, _, b in t.calls]
    assert [b["variables"]["after"] for b in bodies] == [None, "Y3Vyc29yOjI="]
    assert all(b["query"] == github.GRAPHQL_QUERY for b in bodies)
    assert bodies[0]["variables"] == {"after": None, "name": "print-bench", "number": 636, "owner": "shaiss"}
    assert {(m, u) for m, u, _, _ in t.calls} == {("POST", github.GRAPHQL_URL)}
    assert c.budget.used == 2
    c, t, _ = client([_gql({"repository": {"issueOrPullRequest": {"lastEditedAt": "2026-08-01T00:00:00Z"}}})])
    assert c.graphql_issue_edited(592) == "2026-08-01T00:00:00Z"
    c, t, _ = client([_gql({"repository": {"issueOrPullRequest": {"lastEditedAt": None}}})])
    assert c.graphql_pr_threads(592) == {"last_edited_at": None, "nodes": []}   # an issue: no threads
    loop = {"repository": {"issueOrPullRequest": {"lastEditedAt": None, "reviewThreads": {
        "pageInfo": {"hasNextPage": True, "endCursor": "x"}, "nodes": []}}}}
    c, t, _ = client(lambda *a: _gql(loop))
    with pytest.raises(Truncated):
        c.graphql_pr_threads(1)
    assert len(t.calls) == github.GRAPHQL_MAX_PAGES


def test_token_never_logged(tmp_path):
    """APIError / Truncated messages and the ETag cache files carry status, method and path, never the Authorization header value."""
    msgs = []
    c, t, _ = client([(401, {}, b'{"message": "Bad credentials"}')], cache_dir=str(tmp_path))
    with pytest.raises(APIError) as exc:
        c.get("/pulls/1", {"state": "closed"})
    msgs.append(str(exc.value))
    assert str(exc.value) == "HTTP 401 GET /pulls/1"
    c, t, _ = client(_pages(3), cache_dir=str(tmp_path))
    with pytest.raises(Truncated) as exc:
        c.get_paged("/actions/runs", key="workflow_runs", max_pages=1)
    msgs.append(str(exc.value))
    c, t, _ = client([TimeoutError(f"echo {TOKEN}")] * 4)
    with pytest.raises(APIError) as exc:
        c.get("/a")
    msgs.append(str(exc.value))
    c, t, _ = client([ok({"x": 1}, {"ETag": '"e1"'})], cache_dir=str(tmp_path))
    c.get("/cached")
    for m in msgs:
        assert TOKEN not in m and "Bearer" not in m
    files = os.listdir(tmp_path)
    assert files
    for name in files:
        text = (tmp_path / name).read_text()
        assert TOKEN not in text and "Authorization" not in text
        assert set(json.loads(text)) == {"body", "etag", "link"}
    assert all(TOKEN in h["Authorization"] for _, _, h, _ in t.calls)   # it IS sent — in the header only
