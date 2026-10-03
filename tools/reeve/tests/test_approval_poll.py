"""Standing approval modes (issue #446) — the poll, the Select step, the wiring.

``test_approval.py`` pins the pure classification; this file pins what the
loop DOES with it, each case with a negative control:

- ``greenlight.poll_outcome``'s precedence with a mode: /decide > route >
  deny > 👎 > 👍 > a standing auto-approve of a YES (after the grace window);
- ``pushthrough.run_poll`` end to end over the recorded seams — a deny thread
  is never written to, not even with a 👍; an auto thread resolves with no
  reaction only when its docs label was applied by a write-permission human;
- ``reeve greenlight-select`` never hands the drafter a deny issue (#446's
  Done-when: "A deny category never receives a greenlight post (pinned)");
- the workflow passes the committed conf to both commands, without which
  the rules would silently never apply.

The push-through seam fixtures are ``test_pushthrough.py``'s own, reused.
"""

from __future__ import annotations

import base64
import pathlib
import re
from datetime import datetime, timezone

from reeve import approval, github, greenlight, pushthrough
from reeve.cli import main

from test_pushthrough import (  # the push-through's own recorded seams
    PAT, REPO, ROOT, TOKEN, _no_decide_command_anywhere, _posted_comments,
    comment, greenlight_thread, install, react,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
REEVE_YML = REPO_ROOT / ".github" / "workflows" / "reeve.yml"

OWNER_RULES = approval.Rules(auto=frozenset({"docs"}), deny=frozenset({"gates"}))
DOCS_LABEL = approval.CATEGORY_LABELS["docs"]
GATES_LABEL = approval.CATEGORY_LABELS["gates"]

# The greenlight fixtures post at 2026-08-20T06:00:00Z; the next daily run.
NEXT_DAY = datetime(2026, 8, 21, 5, 53, tzinfo=timezone.utc)
SAME_DAY = datetime(2026, 8, 20, 6, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# poll_outcome — the precedence table with a mode
# ---------------------------------------------------------------------------

def _gl(verdict="yes", arm=False):
    return {"verdict": verdict, "arm": arm, "created_at": "2026-08-20T06:00:00Z"}


def _poll(gl, approvers=(), overrulers=(), decide=None, mode=approval.MODE_ASK,
          categories=(), grace=True):
    return greenlight.poll_outcome(gl, list(approvers), list(overrulers), decide,
                                   mode=mode, categories=categories, grace_elapsed=grace)


def test_default_mode_is_ask_and_waits():
    # A caller that never classified gets #444's behaviour exactly.
    out = greenlight.poll_outcome(_gl(), [], [])
    assert out["outcome"] == greenlight.OUTCOME_WAIT


def test_auto_yes_after_grace_approves_as_the_standing_rule():
    out = _poll(_gl(arm=True), mode=approval.MODE_AUTO, categories={"docs"})
    assert out["outcome"] == greenlight.OUTCOME_APPROVE
    assert out["approvers"] == ["standing-rule:docs"]
    assert out["standing_rule"] == "docs"
    assert out["verdict"] == "yes" and out["arm"] is True


def test_ask_yes_with_no_reaction_waits():
    # NEGATIVE CONTROL for the line above: the same greenlight, mode ask.
    out = _poll(_gl(), mode=approval.MODE_ASK, categories={"docs"})
    assert out["outcome"] == greenlight.OUTCOME_WAIT


def test_auto_yes_inside_grace_waits():
    out = _poll(_gl(), mode=approval.MODE_AUTO, categories={"docs"}, grace=False)
    assert out["outcome"] == greenlight.OUTCOME_WAIT
    assert "grace window" in out["reason"]


def test_auto_no_still_asks():
    # Only a YES is pre-approved (owner sub-choice iii).
    out = _poll(_gl("no"), mode=approval.MODE_AUTO, categories={"docs"})
    assert out["outcome"] == greenlight.OUTCOME_WAIT
    assert "only a YES" in out["reason"]


def test_auto_route_waits():
    out = _poll(_gl("route"), mode=approval.MODE_AUTO, categories={"docs"})
    assert out["outcome"] == greenlight.OUTCOME_WAIT


def test_auto_overrule_beats_the_standing_rule():
    out = _poll(_gl(), overrulers=["shaiss"], mode=approval.MODE_AUTO, categories={"docs"})
    assert out["outcome"] == greenlight.OUTCOME_OVERRULE


def test_auto_decide_yields():
    decide = {"verb": "no", "id": "x", "author": "shaiss"}
    out = _poll(_gl(), decide=decide, mode=approval.MODE_AUTO, categories={"docs"})
    assert out["outcome"] == greenlight.OUTCOME_YIELD


def test_auto_human_upvote_resolves_inside_grace():
    # A 👍 is a human approval — it never waits for the rule's window.
    out = _poll(_gl(), approvers=["shaiss"], mode=approval.MODE_AUTO,
                categories={"docs"}, grace=False)
    assert out["outcome"] == greenlight.OUTCOME_APPROVE
    assert out["approvers"] == ["shaiss"] and "standing_rule" not in out


def test_deny_never_approves_even_with_an_upvote():
    out = _poll(_gl(), approvers=["shaiss"], mode=approval.MODE_DENY, categories={"gates"})
    assert out["outcome"] == greenlight.OUTCOME_WAIT
    assert "human only" in out["reason"]


def test_ask_with_an_upvote_approves():
    # NEGATIVE CONTROL for the deny line: the same 👍, mode ask → approve.
    out = _poll(_gl(), approvers=["shaiss"], mode=approval.MODE_ASK)
    assert out["outcome"] == greenlight.OUTCOME_APPROVE


def test_deny_writes_no_overrule_either():
    out = _poll(_gl(), overrulers=["shaiss"], mode=approval.MODE_DENY, categories={"gates"})
    assert out["outcome"] == greenlight.OUTCOME_WAIT


def test_deny_still_yields_to_a_human_decide():
    decide = {"verb": "yes", "id": "x", "author": "shaiss"}
    out = _poll(_gl(), decide=decide, mode=approval.MODE_DENY, categories={"gates"})
    assert out["outcome"] == greenlight.OUTCOME_YIELD


# ---------------------------------------------------------------------------
# run_poll — end to end over the recorded seams
# ---------------------------------------------------------------------------

PARKED_URL = f"{ROOT}/repos/{REPO}/issues?state=open&labels=needs-decision&per_page=100"


def _events_url(number):
    return f"{ROOT}/repos/{REPO}/issues/{number}/events?per_page=100"


def install_classified(monkeypatch, *, threads, label_events=None, **kw):
    """``test_pushthrough.install`` plus the two reads #446 adds: the parked
    listing carries each thread's ``labels``/``title``, and the label-events
    endpoint answers from ``label_events`` (``{number: [(label, actor)]}``).
    Returns ``(writes, gets)`` — ``gets`` records every URL read."""
    writes = install(monkeypatch, threads=threads, **kw)
    inner = github._get
    gets: list[str] = []
    label_events = label_events or {}

    def fake_get(url, token):
        gets.append(url)
        if url == PARKED_URL:
            return ([{"number": t["number"], "title": t.get("title", ""), "url": "",
                      "body": t.get("body", ""),
                      "labels": [{"name": n} for n in t.get("labels", ())]}
                     for t in threads], "")
        m = re.fullmatch(rf"{ROOT}/repos/{REPO}/issues/(\d+)/events\?per_page=100", url)
        if m:
            return ([{"event": "labeled", "label": {"name": label}, "actor": {"login": actor},
                      "created_at": "2026-08-19T00:00:00Z"}
                     for label, actor in label_events.get(int(m.group(1)), [])], "")
        return inner(url, token)

    monkeypatch.setattr(github, "_get", fake_get)
    return writes, gets


def docs_thread(number=301, verdict="yes", arm=False, body_extra=""):
    thread = greenlight_thread(number, verdict=verdict, arm=arm)
    thread["labels"] = ["needs-decision", DOCS_LABEL]
    thread["title"] = "Fix the stale paragraph in docs/growth.md"
    thread["body"] += body_extra
    return thread


def _label_posts(writes, number):
    return [w["payload"]["labels"] for w in writes
            if w["method"] == "POST" and w["url"].endswith(f"/issues/{number}/labels")]


def test_auto_docs_yes_resolves_with_no_reaction(monkeypatch):
    thread = docs_thread(301)
    writes, _ = install_classified(
        monkeypatch, threads=[thread], permissions={"shaiss": "admin"},
        label_events={301: [(DOCS_LABEL, "shaiss")]}, ledger="# header\n")
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert results[0]["outcome"] == "approved"
    assert results[0]["standing_rule"] == "docs"
    # decide.yml's fail-closed order, unchanged: the verdict label first.
    assert _label_posts(writes, 301)[0] == ["decision-approved"]
    # The ledger row names the rule, never a person.
    ledger = [w for w in writes if w["method"] == "PUT"][0]
    row = base64.b64decode(ledger["payload"]["content"]).decode().splitlines()[-1]
    assert row.split(" | ")[3] == "standing-rule:docs"
    assert ledger["token"] == PAT
    reply = _posted_comments(writes)[-1]
    assert "resolution=approved" in reply.splitlines()[0]
    assert "Approved by standing rule `approve_auto: docs`" in reply
    assert "label `docs-only` (applied by a write-permission human)" in reply
    _no_decide_command_anywhere(writes)


def test_auto_docs_yes_with_arm_applies_autonomy_ok(monkeypatch):
    # Owner sub-choice (i): an auto-approved YES arms exactly like a 👍 would.
    thread = docs_thread(302, arm=True)
    writes, _ = install_classified(
        monkeypatch, threads=[thread], permissions={"shaiss": "admin"},
        label_events={302: [(DOCS_LABEL, "shaiss")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert results[0]["armed"] is True
    assert ["autonomy-ok"] in _label_posts(writes, 302)


def test_same_thread_without_the_rules_writes_nothing(monkeypatch):
    # NEGATIVE CONTROL: no rules (the poll never handed the conf) → it asks,
    # and with no reaction nothing is written. The rules are what resolved it.
    writes, gets = install_classified(
        monkeypatch, threads=[docs_thread(301)], permissions={"shaiss": "admin"},
        label_events={301: [(DOCS_LABEL, "shaiss")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY)
    assert results[0]["outcome"] == "wait"
    assert writes == []
    assert _events_url(301) not in gets   # nothing could loosen — no history read


def test_auto_inside_the_grace_window_writes_nothing(monkeypatch):
    writes, _ = install_classified(
        monkeypatch, threads=[docs_thread(301)], permissions={"shaiss": "admin"},
        label_events={301: [(DOCS_LABEL, "shaiss")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=SAME_DAY, rules=OWNER_RULES)
    assert results[0]["outcome"] == "wait"
    assert "grace window" in results[0]["reason"]
    assert writes == []


def test_auto_no_verdict_writes_nothing(monkeypatch):
    writes, _ = install_classified(
        monkeypatch, threads=[docs_thread(301, verdict="no")], permissions={"shaiss": "admin"},
        label_events={301: [(DOCS_LABEL, "shaiss")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert results[0]["outcome"] == "wait"
    assert writes == []


def test_a_bot_applied_docs_label_cannot_auto_approve(monkeypatch):
    # The security case: an agentic routine holding issues:write applies the
    # label. The applier is a bot → untrusted → ask → no reaction → no write.
    writes, gets = install_classified(
        monkeypatch, threads=[docs_thread(301)], permissions={},
        label_events={301: [(DOCS_LABEL, "github-actions[bot]")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert results[0]["outcome"] == "wait"
    assert writes == []
    assert _events_url(301) in gets
    # No permission lookup was spent on the bot.
    assert not any("/collaborators/github-actions" in g for g in gets)


def test_a_read_only_applier_cannot_auto_approve(monkeypatch):
    writes, _ = install_classified(
        monkeypatch, threads=[docs_thread(301)], permissions={"driveby": "read"},
        label_events={301: [(DOCS_LABEL, "driveby")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert results[0]["outcome"] == "wait"
    assert writes == []


def test_auto_overruled_by_a_downvote(monkeypatch):
    writes, _ = install_classified(
        monkeypatch, threads=[docs_thread(301)], permissions={"shaiss": "admin"},
        reactions={1201: [react("-1", "shaiss")]},
        label_events={301: [(DOCS_LABEL, "shaiss")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert results[0]["outcome"] == "overruled"
    assert _label_posts(writes, 301) == []           # an overrule flips no label


def test_auto_yields_to_an_authorized_decide(monkeypatch):
    thread = docs_thread(301)
    thread["comments"].append(comment(5001, "/decide no issue-301-decision", login="shaiss"))
    writes, _ = install_classified(
        monkeypatch, threads=[thread], permissions={"shaiss": "admin"},
        label_events={301: [(DOCS_LABEL, "shaiss")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert results[0]["outcome"] == greenlight.OUTCOME_YIELD
    assert writes == []


def _deny_thread(number=401):
    thread = greenlight_thread(number, verdict="yes", arm=True)
    thread["title"] = "Tighten the gate"
    thread["body"] += "\n\nThis edits `.github/workflows/ci.yml`."
    return thread


def test_deny_thread_with_an_upvote_is_never_written(monkeypatch):
    # #446's Done-when, poll side: a deny category is human-only — even a
    # live greenlight with an authorized 👍 resolves nothing, writes nothing.
    writes, gets = install_classified(
        monkeypatch, threads=[_deny_thread()], permissions={"shaiss": "admin"},
        reactions={1301: [react("+1", "shaiss")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert results[0]["outcome"] == "wait"
    assert "human only" in results[0]["reason"]
    assert writes == []
    assert _events_url(401) not in gets   # deny is final before any label history


def test_the_same_upvote_without_the_deny_rule_approves(monkeypatch):
    # NEGATIVE CONTROL: the identical thread and 👍 with no deny rule → approved.
    writes, _ = install_classified(
        monkeypatch, threads=[_deny_thread()], permissions={"shaiss": "admin"},
        reactions={1301: [react("+1", "shaiss")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY,
                                   rules=approval.Rules(auto=frozenset({"docs"})))
    assert results[0]["outcome"] == "approved"
    assert _label_posts(writes, 401)[0] == ["decision-approved"]


def test_deny_thread_with_a_downvote_is_never_written(monkeypatch):
    writes, _ = install_classified(
        monkeypatch, threads=[_deny_thread()], permissions={"shaiss": "admin"},
        reactions={1301: [react("-1", "shaiss")]})
    pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert writes == []


def test_docs_label_cannot_launder_gate_text(monkeypatch):
    # A verified docs-only label on a thread whose body names gate machinery
    # is a deny: tighten wins, and no label history is even read.
    thread = docs_thread(303, body_extra="\nalso `scripts/reeve-perms-check.sh`")
    writes, gets = install_classified(
        monkeypatch, threads=[thread], permissions={"shaiss": "admin"},
        label_events={303: [(DOCS_LABEL, "shaiss")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT, now=NEXT_DAY, rules=OWNER_RULES)
    assert results[0]["outcome"] == "wait" and "gates" in results[0]["reason"]
    assert writes == []
    assert _events_url(303) not in gets


# ---------------------------------------------------------------------------
# gather — the seam carries what the classification reads
# ---------------------------------------------------------------------------

def test_list_label_events_keeps_only_label_events(monkeypatch):
    def fake_get(url, token):
        assert url == _events_url(7)
        return ([
            {"event": "labeled", "label": {"name": DOCS_LABEL}, "actor": {"login": "shaiss"},
             "created_at": "t1"},
            {"event": "commented", "actor": {"login": "x"}, "created_at": "t2"},
            {"event": "unlabeled", "label": {"name": DOCS_LABEL}, "actor": {"login": "y"},
             "created_at": "t3"},
        ], "")

    monkeypatch.setattr(github, "_get", fake_get)
    assert github.list_label_events(REPO, TOKEN, 7) == [
        {"event": "labeled", "label": DOCS_LABEL, "actor": "shaiss", "created_at": "t1"},
        {"event": "unlabeled", "label": DOCS_LABEL, "actor": "y", "created_at": "t3"},
    ]


def test_gather_greenlight_poll_carries_labels(monkeypatch):
    install_classified(monkeypatch, threads=[docs_thread(301)])
    threads = github.gather_greenlight_poll(REPO, TOKEN)
    assert threads[0]["labels"] == ["needs-decision", DOCS_LABEL]


# ---------------------------------------------------------------------------
# greenlight-select — a deny issue never reaches the drafter (pinned)
# ---------------------------------------------------------------------------

def _select_fixture(monkeypatch, issues):
    """The real gather_greenlight_queue over a faked ``_get``: each issue is
    ``(number, title, body, labels)`` with an empty comment thread."""
    listing = [{"number": n, "title": t, "html_url": f"u/{n}", "body": b,
                "labels": [{"name": name} for name in labels]}
               for n, t, b, labels in issues]

    def fake_get(url, token):
        if url == PARKED_URL:
            return (listing, "")
        if re.fullmatch(rf"{ROOT}/repos/{REPO}/issues/\d+/comments\?per_page=100", url):
            return ([], "")
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(github, "_get", fake_get)


ISSUES = [
    (501, "Platform call", "Should the burn run twice a day?", ["needs-decision"]),
    (502, "Gate tweak", "Edit `scripts/gate.sh` to add a check", ["needs-decision"]),
    (503, "Docs follow-up", "Reword docs/growth.md", ["needs-decision", DOCS_LABEL]),
    (504, "Backstop", "Fine", ["needs-decision", GATES_LABEL]),
]


def _conf(tmp_path, text):
    path = tmp_path / "reeve.conf"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_select_never_hands_over_a_deny_issue(tmp_path, monkeypatch, capsys):
    _select_fixture(monkeypatch, ISSUES)
    gh_out = tmp_path / "gh_output"
    conf = _conf(tmp_path, "approve_auto: docs\napprove_deny: gates\n")
    rc = main(["greenlight-select", "--repo", REPO, "--conf", conf, "--gh-output", str(gh_out)])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "501 503\n"       # text-denied 502 and label-denied 504 dropped
    assert "#502 skipped" in captured.err and "#504 skipped" in captured.err
    written = gh_out.read_text(encoding="utf-8")
    assert "issues=501 503\n" in written
    assert "denied=502 504\n" in written


def test_select_without_a_deny_rule_hands_over_everything(tmp_path, monkeypatch, capsys):
    # NEGATIVE CONTROL: same issues, no approve_deny → nothing is dropped.
    _select_fixture(monkeypatch, ISSUES)
    conf = _conf(tmp_path, "approve_auto: docs\n")
    assert main(["greenlight-select", "--repo", REPO, "--conf", conf]) == 0
    assert capsys.readouterr().out == "501 502 503 504\n"


def test_select_drops_deny_before_the_cap(tmp_path, monkeypatch, capsys):
    # A denied issue costs no slot: cap 2 still yields two draftable issues.
    _select_fixture(monkeypatch, [ISSUES[1], ISSUES[0], ISSUES[2]])
    conf = _conf(tmp_path, "approve_deny: gates\ngreenlight_cap: 2\n")
    assert main(["greenlight-select", "--repo", REPO, "--conf", conf]) == 0
    assert capsys.readouterr().out == "501 503\n"


# ---------------------------------------------------------------------------
# greenlight-poll — the conf reaches the poll
# ---------------------------------------------------------------------------

def test_poll_passes_the_conf_rules_and_reports_standing(tmp_path, monkeypatch, capsys):
    seen = {}

    def fake_run_poll(repo, token, pat, now=None, rules=None):
        seen["rules"] = rules
        return [{"number": 301, "outcome": "approved", "standing_rule": "docs", "notes": []},
                {"number": 302, "outcome": "approved", "standing_rule": None, "notes": []}]

    monkeypatch.setattr("reeve.pushthrough.run_poll", fake_run_poll)
    gh_out = tmp_path / "gh_output"
    conf = _conf(tmp_path, "approve_auto: docs\napprove_deny: gates\n")
    assert main(["greenlight-poll", "--repo", REPO, "--conf", conf,
                 "--gh-output", str(gh_out)]) == 0
    assert seen["rules"] == OWNER_RULES
    out = capsys.readouterr().out
    assert "#301: approved (standing rule auto-approve: docs)" in out
    assert "#302: approved\n" in out
    written = gh_out.read_text(encoding="utf-8")
    assert "resolved=301 302\n" in written
    assert "standing=301\n" in written


# ---------------------------------------------------------------------------
# reeve.yml — both commands get the committed conf
# ---------------------------------------------------------------------------

def _invocation(text: str, verb: str) -> str:
    """The full (backslash-continued) command line that runs ``reeve <verb>`` —
    anchored at a line's start, so a comment that merely names the verb is
    never mistaken for the invocation."""
    match = re.search(rf"^[ \t]*reeve {verb}\b(?:[^\n]*\\\n)*[^\n]*", text, re.MULTILINE)
    assert match, f"reeve.yml no longer runs `reeve {verb}`"
    return match.group(0)


def _passes_conf(text: str, verb: str) -> bool:
    return "--conf .github/reeve.conf" in _invocation(text, verb)


def test_workflow_hands_the_conf_to_poll_and_select():
    # Without --conf the rule set is empty: the committed approve_auto /
    # approve_deny would silently never apply — a deny issue drafted, a
    # docs-only YES never auto-resolved — with every test still green.
    text = REEVE_YML.read_text(encoding="utf-8")
    assert _passes_conf(text, "greenlight-poll")
    assert _passes_conf(text, "greenlight-select")


def test_conf_wiring_check_catches_a_dropped_flag():
    # NEGATIVE CONTROL for the wiring check itself.
    text = REEVE_YML.read_text(encoding="utf-8")
    dropped = text.replace(
        _invocation(text, "greenlight-poll"),
        'reeve greenlight-poll --repo "$GITHUB_REPOSITORY" --gh-output "$GITHUB_OUTPUT"')
    assert not _passes_conf(dropped, "greenlight-poll")
