"""The GET-only GitHub seam behind `growth dedup-context --repo` — exercised
entirely through the monkeypatched `_get`, never the network."""

import io
import urllib.error
import urllib.parse
from datetime import datetime, timezone

import pytest

from growth import github


def _query(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


class FakeAPI:
    """Serves the labels listing and per-(state, label) issue listings."""

    def __init__(self, labels, issues):
        self.labels = labels
        self.issues = issues          # {(state, label): [items]}
        self.calls = []

    def __call__(self, url, token):
        self.calls.append(url)
        path = urllib.parse.urlsplit(url).path
        if path.endswith("/labels"):
            return [{"name": n} for n in self.labels], ""
        q = _query(url)
        return list(self.issues.get((q["state"], q["labels"]), [])), ""


CUTOFF = datetime(2026, 6, 5, 18, 0, tzinfo=timezone.utc)


def test_lists_open_and_recently_closed_items_for_every_channel_label(monkeypatch):
    api = FakeAPI(
        labels=["bug", "channel:twitter", "channel:youtube", "growth-queue"],
        issues={
            ("open", "channel:twitter"): [{"number": 597}, {"number": 753}],
            ("closed", "channel:twitter"): [{"number": 754}],
            ("open", "channel:youtube"): [{"number": 800}],
        },
    )
    monkeypatch.setattr(github, "_get", api)
    items = github.channel_issues("o/r", "tok", CUTOFF)
    assert [i["number"] for i in items] == [597, 753, 754, 800]
    issue_calls = [_query(u) for u in api.calls if "/issues?" in u]
    # Exactly the channel labels — never `bug` or `growth-queue` on their own.
    assert {c["labels"] for c in issue_calls} == {"channel:twitter", "channel:youtube"}
    closed = [c for c in issue_calls if c["state"] == "closed"]
    assert closed and all(c["since"] == "2026-06-05T18:00:00Z" for c in closed)
    # Open listings are never bounded by `since`: an old open item is live state.
    assert all("since" not in c for c in issue_calls if c["state"] == "open")


def test_an_item_under_two_channel_labels_is_returned_once(monkeypatch):
    both = {"number": 5, "title": "Growth post: both"}
    api = FakeAPI(["channel:twitter", "channel:youtube"],
                  {("open", "channel:twitter"): [both], ("open", "channel:youtube"): [both]})
    monkeypatch.setattr(github, "_get", api)
    assert [i["number"] for i in github.channel_issues("o/r", "", CUTOFF)] == [5]


def test_no_channel_labels_means_no_issue_listing(monkeypatch):
    api = FakeAPI(["bug"], {})
    monkeypatch.setattr(github, "_get", api)
    assert github.channel_issues("o/r", "", CUTOFF) == []
    assert not [u for u in api.calls if "/issues?" in u]


def test_pagination_follows_link_next(monkeypatch):
    pages = {
        "https://api.github.com/p1": ([{"number": 1}], '<https://api.github.com/p2>; rel="next"'),
        "https://api.github.com/p2": ([{"number": 2}], ""),
    }
    monkeypatch.setattr(github, "_get", lambda url, token: pages[url])
    assert github._paged("https://api.github.com/p1", "") == [{"number": 1}, {"number": 2}]


def test_page_cap_raises_rather_than_truncating(monkeypatch):
    monkeypatch.setattr(github, "_MAX_PAGES", 2)
    monkeypatch.setattr(github, "_get", lambda url, token: (
        [{"number": 1}], '<https://api.github.com/again>; rel="next"'))
    with pytest.raises(RuntimeError, match="silently-truncated"):
        github._paged("https://api.github.com/start", "")


def test_a_non_list_body_raises(monkeypatch):
    monkeypatch.setattr(github, "_get", lambda url, token: ({"message": "Bad"}, ""))
    with pytest.raises(RuntimeError, match="non-list"):
        github._paged("https://api.github.com/x", "")


def _http_error(code):
    return urllib.error.HTTPError("u", code, "err", {}, io.BytesIO(b""))


def test_a_transient_failure_is_retried(monkeypatch):
    attempts = []

    def flaky(url, token):
        attempts.append(url)
        if len(attempts) < 3:
            raise _http_error(502)
        return [], ""

    monkeypatch.setattr(github, "_get", flaky)
    monkeypatch.setattr(github.time, "sleep", lambda s: None)
    assert github._get_with_retry("u", "") == ([], "")
    assert len(attempts) == 3


def test_a_real_error_is_not_retried(monkeypatch):
    attempts = []

    def not_found(url, token):
        attempts.append(url)
        raise _http_error(404)

    monkeypatch.setattr(github, "_get", not_found)
    monkeypatch.setattr(github.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        github._get_with_retry("u", "")
    assert len(attempts) == 1


def test_a_persistent_transient_failure_surfaces(monkeypatch):
    monkeypatch.setattr(github, "_get", lambda url, token: (_ for _ in ()).throw(_http_error(503)))
    monkeypatch.setattr(github.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        github._get_with_retry("u", "")


def test_the_request_is_a_bodiless_get(monkeypatch):
    # The seam itself, with urlopen captured: no body, so urllib can only GET.
    captured = {}

    class Resp:
        headers = {"Link": ""}

        def read(self):
            return b"[]"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        captured["method"] = req.get_method()
        captured["data"] = req.data
        captured["auth"] = req.get_header("Authorization")
        return Resp()

    monkeypatch.setattr(github.urllib.request, "urlopen", fake_urlopen)
    assert github._get("https://api.github.com/x", "tok") == ([], "")
    assert captured == {"method": "GET", "data": None, "auth": "Bearer tok"}
