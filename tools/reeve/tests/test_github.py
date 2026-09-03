"""Run-health + greenlight-queue gather tests — ``_get`` is the single network seam.

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
        # A PR that also carries the adoption-study label — still a PR, so the
        # pull_request guard drops it before the label scan; must NOT appear
        # under adoptionStudies.
        {"number": 4, "title": "PR wearing the adoption-study label", "comments": 0,
         "pull_request": {"url": "..."}, "labels": [{"name": "adoption-study"}]},
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
        # An adoption-study submission awaiting a disposition. Zero comments, but
        # still collected — the label scan precedes the comments skip.
        {"number": 305, "title": "Adoption study: BOSL2 gears", "comments": 0,
         "labels": [{"name": "adoption-study"}],
         "created_at": "2026-08-12T05:00:00Z", "updated_at": "2026-08-13T05:00:00Z",
         "html_url": "https://github.com/o/r/issues/305"},
        # An unlabeled issue — the control; must NOT appear under adoptionStudies.
        {"number": 306, "title": "Unlabeled issue", "comments": 0, "labels": []},
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


def test_gather_collects_adoption_studies_and_drops_pr(monkeypatch):
    calls: list[str] = []
    fake_get(monkeypatch, calls)
    health = github.gather_run_health(REPO, "tok")
    # The labeled issue is collected with its labels + timestamps; the unlabeled
    # control (#306) is absent, and the labeled PR (#4) is dropped as a PR.
    assert health["adoptionStudies"] == [
        {"number": 305, "title": "Adoption study: BOSL2 gears",
         "labels": ["adoption-study"],
         "createdAt": "2026-08-12T05:00:00Z", "updatedAt": "2026-08-13T05:00:00Z",
         "url": "https://github.com/o/r/issues/305"},
    ]
    # A zero-comment study is gathered without ever fetching its comments.
    assert not any("/issues/305/comments" in url for url in calls)


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


# ---------------------------------------------------------------------------
# The greenlight queue (issue #443): open needs-decision issues that carry no
# greenlight marker comment yet. Same discipline — _get monkeypatched, no
# request leaves the process.
# ---------------------------------------------------------------------------

def _gl_responses():
    """URL -> (json body, Link header) for the greenlight endpoints."""
    responses = {}
    responses[f"{github.API_ROOT}/repos/{REPO}/issues"
              f"?state=open&labels={github.NEEDS_DECISION_LABEL}&per_page=100"] = ([
        # A PR wearing the gate label — dropped as a PR, never queued.
        {"number": 12, "title": "PR parked?", "pull_request": {"url": "..."}},
        # Parked, no comments at all — queued (a comments GET still happens:
        # the marker scan is per-comment, and an empty list carries none).
        {"number": 230, "title": "Decision: platform X", "html_url": "u/230"},
        # Parked, comments but no marker — queued.
        {"number": 265, "title": "Decision: platform Y", "html_url": "u/265"},
        # Parked and already greenlighted — NOT queued (the loop posts only
        # where no marker exists, any verdict, any version).
        {"number": 267, "title": "Decision: platform Z", "html_url": "u/267"},
        # Parked, marker NOT on the comment's first line — a greenlight always
        # opens with the marker, so this is ordinary text; queued.
        {"number": 269, "title": "Decision: quoted marker mid-body", "html_url": "u/269"},
    ], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/230/comments?per_page=100"] = ([], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/265/comments?per_page=100"] = ([
        {"body": "parking this for the lead", "created_at": "2026-08-20T05:00:00Z"},
    ], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/267/comments?per_page=100"] = ([
        {"body": "some discussion", "created_at": "2026-08-20T05:00:00Z"},
        {"body": "<!-- reeve-greenlight v1 issue=267 verdict=no -->\nGREENLIGHT: NO\nreasoning"},
        {"body": "<!-- reeve-greenlight v2 issue=267 verdict=route -->\nGREENLIGHT: ROUTE"},
    ], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/269/comments?per_page=100"] = ([
        {"body": "\n\n  an ordinary comment quoting \"<!-- reeve-greenlight v1 ...\" mid-body\n"},
    ], "")
    return responses


def _gl_fake(monkeypatch, responses):
    def _fake(url, token):
        return responses[url]
    monkeypatch.setattr(github, "_get", _fake)


def test_greenlight_queue_lists_unmarked_parked_issues(monkeypatch):
    _gl_fake(monkeypatch, _gl_responses())
    out = github.gather_greenlight_queue(REPO, "tok")
    assert [i["number"] for i in out["queue"]] == [230, 265, 269]  # oldest first
    assert [i["number"] for i in out["parked"]] == [230, 265, 267, 269]  # PR dropped


def test_greenlight_queue_never_reads_a_pr_thread(monkeypatch):
    calls: list[str] = []
    responses = _gl_responses()

    def _fake(url, token):
        calls.append(url)
        return responses[url]

    monkeypatch.setattr(github, "_get", _fake)
    github.gather_greenlight_queue(REPO, "tok")
    assert not any("/issues/12/" in url for url in calls)


# A provider-triage escalation (issue #544: every converted walk can raise
# one on exhaustion) wears the gate label but is an account/key ask with a
# fixed remedy, not a charter call — the queue must skip it. The body shape
# is the action's own: marker first line, then the tailored remediation.
_ESCALATION_MARKER_LINE = "<!-- provider-escalation:scout -->\n"
_ESCALATION_BODY = (
    _ESCALATION_MARKER_LINE
    + "## Provider escalation: `scout` chain\n\n"
    "The provider account is **out of credit** (a billing/balance rejection). "
    "**Fund the account**, then confirm.\n"
)


def _gl_with_escalation(marker: bool):
    """The greenlight fixture plus one more parked issue, #271: the
    provider-triage escalation with its marker (``marker=True``) or the SAME
    issue with the marker line removed (the negative control)."""
    responses = _gl_responses()
    listing = (f"{github.API_ROOT}/repos/{REPO}/issues"
               f"?state=open&labels={github.NEEDS_DECISION_LABEL}&per_page=100")
    body = _ESCALATION_BODY if marker else _ESCALATION_BODY.replace(_ESCALATION_MARKER_LINE, "")
    responses[listing][0].append(
        {"number": 271, "title": "Provider escalation: scout", "html_url": "u/271", "body": body})
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/271/comments?per_page=100"] = ([], "")
    return responses


def test_greenlight_queue_skips_a_provider_escalation(monkeypatch):
    calls: list[str] = []
    responses = _gl_with_escalation(marker=True)

    def _fake(url, token):
        calls.append(url)
        return responses[url]

    monkeypatch.setattr(github, "_get", _fake)
    out = github.gather_greenlight_queue(REPO, "tok")
    # Not draftable: the queue is exactly what it was without #271 ...
    assert [i["number"] for i in out["queue"]] == [230, 265, 269]
    # ... though it IS at the gate, so the inventory keeps it, flagged ...
    flagged = next(i for i in out["parked"] if i["number"] == 271)
    assert flagged["providerEscalation"] is True
    # ... and the skip happens before the comments GET: its thread is never read.
    assert not any("/issues/271/" in url for url in calls)


def test_greenlight_queue_selects_the_same_issue_without_the_marker(monkeypatch):
    # NEGATIVE CONTROL: strip only the marker line from #271 — same title,
    # same remediation prose, same label — and it is selected like any other
    # parked decision, so the skip is the marker, not the wording.
    _gl_fake(monkeypatch, _gl_with_escalation(marker=False))
    out = github.gather_greenlight_queue(REPO, "tok")
    assert [i["number"] for i in out["queue"]] == [230, 265, 269, 271]
    assert next(i for i in out["parked"] if i["number"] == 271)["providerEscalation"] is False


@pytest.mark.parametrize("body,expected", [
    ("<!-- provider-escalation:scout -->\n## Provider escalation", True),
    ("\n\nsome preamble\n<!-- provider-escalation:reeve-greenlight -->\nlater", True),
    # Prose that merely names the mechanism carries no marker.
    ("please look at the provider-escalation issue the scout filed", False),
    ("", False),
    (None, False),
])
def test_is_provider_escalation_matches_the_body_marker(body, expected):
    assert github.is_provider_escalation(body) is expected


@pytest.mark.parametrize("body,expected", [
    ("<!-- reeve-greenlight v1 issue=5 verdict=yes -->\nGREENLIGHT: YES", True),
    ("\n\n  <!-- reeve-greenlight v1 issue=5 verdict=no -->\nNO", True),  # first non-blank line
    ("a comment that merely mentions reeve-greenlight", False),
    ("", False),
])
def test_carries_greenlight_matches_the_marker_first_line(body, expected):
    assert github.carries_greenlight([{"body": body}]) is expected


# ---------------------------------------------------------------------------
# The greenlight rounds gather (issue #445): every greenlighted thread with its
# resolution state — the observer's snapshot. Same discipline, _get monkeypatched.
# ---------------------------------------------------------------------------

def _search_url():
    import urllib.parse

    query = urllib.parse.quote(
        f'repo:{REPO} {github._SEARCH_PHRASE} type:issue', safe=""
    )
    return f"{github.API_ROOT}/search/issues?q={query}&per_page=100"


def _rounds_responses():
    """URL -> (json body, Link header) for the rounds gather."""
    responses = {}
    # Search candidates: a resolved thread, an open one, and a body that merely
    # QUOTES the marker (issue #296's spec) — the third must not count.
    responses[_search_url()] = (
        {
            "total_count": 3,
            "incomplete_results": False,
            "items": [
                {
                    "number": 502, "title": "Decision: live one", "state": "open",
                    "labels": [{"name": "needs-decision"}],
                },
                {
                    "number": 501, "title": "Decision: resolved one", "state": "closed",
                    "labels": [],
                },
                # A quoted marker is mid-body, no real first-line marker: dropped.
                {
                    "number": 503, "title": "The spec issue", "state": "open",
                    "labels": [{"name": "needs-decision"}],
                },
            ],
        },
        "",
    )
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/501/comments?per_page=100"] = ([
        {"body": "parking this", "created_at": "2026-09-01T05:00:00Z",
         "author_association": "OWNER", "author": {"login": "the-owner"}},
        {"body": "<!-- reeve-greenlight v1 issue=501 verdict=yes -->\nGREENLIGHT: YES\nbecause",
         "created_at": "2026-09-01T06:00:00Z", "author_association": "NONE"},
        # Owner reply AFTER the greenlight — counts.
        {"body": "good call, approved",
         "created_at": "2026-09-01T07:00:00Z",
         "author_association": "OWNER", "author": {"login": "the-owner"}},
        # Before the greenlight — does not.
        {"body": "earlier owner note", "created_at": "2026-09-01T04:00:00Z",
         "author_association": "OWNER", "author": {"login": "the-owner"}},
        # After, but not write-associated — an outsider's reply is not the owner's.
        {"body": "random commenter", "created_at": "2026-09-01T08:00:00Z",
         "author_association": "NONE", "author": {"login": "rando"}},
    ], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/502/comments?per_page=100"] = ([
        {"body": "<!-- reeve-greenlight v1 issue=502 verdict=route -->\nGREENLIGHT: ROUTE\nhanding off",
         "created_at": "2026-09-01T06:00:00Z", "author_association": "NONE"},
    ], "")
    # 503's comments: no real marker first line — the verify step drops it.
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/503/comments?per_page=100"] = ([
        {"body": 'the spec says the marker is "<!-- reeve-greenlight v1 ... -->"',
         "created_at": "2026-08-30T05:00:00Z", "author_association": "NONE"},
    ], "")
    # The closing-PR timeline read — closed threads only.
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/501/timeline?per_page=100"] = ([
        {"event": "commented"},
        {"event": "cross-referenced", "source": {"issue": {"number": 499}}},
        {"event": "cross-referenced", "source": {
            "issue": {"number": 512, "pull_request": {"url": "..."}}}},
    ], "")
    return responses


def test_greenlight_rounds_gathers_verified_threads_with_resolution_state(monkeypatch):
    _gl_fake(monkeypatch, _rounds_responses())
    out = github.gather_greenlight_rounds(REPO, "tok")
    assert [t["number"] for t in out["threads"]] == [501, 502]  # 503 was a quoted body
    resolved, live = out["threads"]
    assert resolved["state"] == "closed"
    assert resolved["greenlight_verdict"] == "yes"
    assert "because" in resolved["greenlight_reasoning"]
    assert resolved["closing_pr"] == 512  # the LAST cross-referenced PR
    # Owner replies: after the greenlight, write-associated, markers excluded.
    assert [r["author"] for r in resolved["owner_replies"]] == ["the-owner"]
    assert resolved["owner_replies"][0]["text"] == "good call, approved"
    assert live["state"] == "open"
    assert live["greenlight_verdict"] == "route"
    assert live["closing_pr"] is None  # open thread, no timeline read


def test_greenlight_rounds_skips_the_closing_pr_read_for_open_threads(monkeypatch):
    calls: list[str] = []

    def _fake(url, token):
        calls.append(url)
        return _rounds_responses()[url]

    monkeypatch.setattr(github, "_get", _fake)
    github.gather_greenlight_rounds(REPO, "tok")
    assert any("/issues/501/timeline" in url for url in calls)
    assert not any("/issues/502/timeline" in url for url in calls)


def test_greenlight_rounds_bounds_replies_at_three(monkeypatch):
    responses = _rounds_responses()
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/501/comments?per_page=100"] = ([
        {"body": "<!-- reeve-greenlight v1 issue=501 verdict=yes -->\nGREENLIGHT: YES",
         "created_at": "2026-09-01T06:00:00Z", "author_association": "NONE"},
    ] + [
        {"body": f"owner note {i}", "created_at": f"2026-09-01T0{i}:30:00Z",
         "author_association": "OWNER", "author": {"login": "the-owner"}}
        for i in (7, 8, 9, 10)
    ], "")
    _gl_fake(monkeypatch, responses)
    threads = github.gather_greenlight_rounds(REPO, "tok")["threads"]
    resolved = next(t for t in threads if t["number"] == 501)
    assert [r["text"] for r in resolved["owner_replies"]] == [
        "owner note 7", "owner note 8", "owner note 9",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"total_count": 0, "incomplete_results": True, "items": []},   # truncated
        {"total_count": 101, "incomplete_results": False, "items": []},  # over the page bound
        {"total_count": 0},                                            # no items list
        [1, 2, 3],                                                     # not an object at all
    ],
)
def test_greenlight_rounds_refuses_a_bad_search_payload(monkeypatch, payload):
    responses = {_search_url(): (payload, "")}
    _gl_fake(monkeypatch, responses)
    with pytest.raises(RuntimeError):
        github.gather_greenlight_rounds(REPO, "tok")


def test_greenlight_rounds_a_marker_naming_another_issue_does_not_count(monkeypatch):
    # A copied marker bound to a different issue is not this thread's greenlight.
    responses = _rounds_responses()
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/501/comments?per_page=100"] = ([
        {"body": "<!-- reeve-greenlight v1 issue=999 verdict=yes -->\nGREENLIGHT: YES",
         "created_at": "2026-09-01T06:00:00Z", "author_association": "NONE"},
    ], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/502/comments?per_page=100"] = ([], "")
    responses[f"{github.API_ROOT}/repos/{REPO}/issues/503/comments?per_page=100"] = ([], "")
    _gl_fake(monkeypatch, responses)
    assert github.gather_greenlight_rounds(REPO, "tok")["threads"] == []
