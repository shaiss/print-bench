"""Policy tests for the backlog-burn selector.

Each guard is proved two ways: an issue that trips it is excluded, and the
*same* issue with the disqualifier removed is selected. That pairing is the
negative control — delete the guard from ``select.py`` and the "excluded"
half of the pair fails, so a weakened policy cannot pass silently (the
``lib/*-guards.conf`` discipline, applied to Python).
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from backlog_burn.select import render_summary, select_issue

LABEL = "autonomy-ok"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def issue(number, created, *, labels=(LABEL,), comments=()):
    return {
        "number": number,
        "title": f"issue {number}",
        "createdAt": created,
        "labels": list(labels),
        "comments": list(comments),
    }


def decline(hours_ago, **extra):
    """A 🚢 DECLINED marker comment `hours_ago` before NOW."""
    return {
        "body": "🚢 DECLINED — needs a decision (blocking question unanswered).",
        "createdAt": _iso(NOW - timedelta(hours=hours_ago)),
        **extra,
    }


def snap(issues, *, open_prs=(), branches=()):
    return {
        "issues": list(issues),
        "openPRs": list(open_prs),
        "branches": list(branches),
    }


# --------------------------------------------------------------------------
# Ordering + the hard cap
# --------------------------------------------------------------------------

def test_selects_oldest_eligible():
    s = snap([
        issue(10, "2026-08-07T23:00:00Z"),
        issue(11, "2026-08-06T23:00:00Z"),  # older
        issue(12, "2026-08-08T23:00:00Z"),
    ])
    r = select_issue(s)
    assert r["selected"] == 11


def test_hard_cap_one_per_firing():
    # Five eligible issues; exactly one is selected, the rest deferred.
    s = snap([issue(n, f"2026-08-0{n}T00:00:00Z") for n in range(1, 6)])
    r = select_issue(s)
    assert r["selected"] == 1
    assert r["eligible_count"] == 5
    assert r["deferred"] == [2, 3, 4, 5]


def test_deterministic_tie_break_by_number():
    s = snap([
        issue(20, "2026-08-07T00:00:00Z"),
        issue(19, "2026-08-07T00:00:00Z"),  # same timestamp, lower number wins
    ])
    assert select_issue(s)["selected"] == 19


def test_nothing_eligible_returns_none():
    s = snap([issue(3, "2026-08-01T00:00:00Z", labels=["enhancement"])])
    r = select_issue(s)
    assert r["selected"] is None
    assert r["considered"] == 1


# --------------------------------------------------------------------------
# Guard: the autonomy-ok opt-in label
# --------------------------------------------------------------------------

def test_requires_optin_label():
    without = issue(30, "2026-08-01T00:00:00Z", labels=["enhancement"])
    # Excluded without the label...
    assert select_issue(snap([without]))["selected"] is None
    # ...and selected once it carries it (negative control).
    withlabel = copy.deepcopy(without)
    withlabel["labels"].append(LABEL)
    assert select_issue(snap([withlabel]))["selected"] == 30


def test_custom_label():
    s = snap([issue(31, "2026-08-01T00:00:00Z", labels=["ship-me"])])
    assert select_issue(s, required_label="ship-me")["selected"] == 31


# --------------------------------------------------------------------------
# Guard: an active SHIP-LOCK claim (and a WITHDRAWN one must release it)
# --------------------------------------------------------------------------

def test_active_ship_lock_excludes():
    locked = issue(40, "2026-08-01T00:00:00Z", comments=[
        {"body": "🚢 SHIP-LOCK — shipping this as one PR.", "createdAt": "2026-08-02T00:00:00Z"},
    ])
    assert select_issue(snap([locked]))["selected"] is None
    assert select_issue(snap([locked]))["excluded"]["40"].startswith("an active")


def test_withdrawn_lock_is_re_eligible():
    # Newest lock comment is a withdrawal -> the issue is claimable again.
    issue_ = issue(41, "2026-08-01T00:00:00Z", comments=[
        {"body": "🚢 SHIP-LOCK — shipping.", "createdAt": "2026-08-02T00:00:00Z"},
        {"body": "🚢 SHIP-LOCK WITHDRAWN — yielding.", "createdAt": "2026-08-03T00:00:00Z"},
    ])
    assert select_issue(snap([issue_]))["selected"] == 41


def test_latest_lock_wins_even_if_reclaimed():
    # withdrawn, then re-claimed by another run: newest is active -> excluded.
    issue_ = issue(42, "2026-08-01T00:00:00Z", comments=[
        {"body": "🚢 SHIP-LOCK — a.", "createdAt": "2026-08-02T00:00:00Z"},
        {"body": "🚢 SHIP-LOCK WITHDRAWN — a yields.", "createdAt": "2026-08-03T00:00:00Z"},
        {"body": "🚢 SHIP-LOCK — b.", "createdAt": "2026-08-04T00:00:00Z"},
    ])
    assert select_issue(snap([issue_]))["selected"] is None


def test_stale_lock_with_no_branch_or_pr_is_takeable():
    # An un-withdrawn claim older than the staleness window, with nothing
    # backing it (no branch, no closing PR), is the skill's takeover case:
    # the burn must not be frozen out of it.
    stale = issue(44, "2026-08-01T00:00:00Z", comments=[
        {"body": "🚢 SHIP-LOCK — shipping.", "createdAt": _iso(NOW - timedelta(hours=9))},
    ])
    assert select_issue(snap([stale]), now=NOW)["selected"] == 44
    # Negative control: the SAME lock, only an hour old, still blocks.
    fresh = issue(44, "2026-08-01T00:00:00Z", comments=[
        {"body": "🚢 SHIP-LOCK — shipping.", "createdAt": _iso(NOW - timedelta(hours=1))},
    ])
    assert select_issue(snap([fresh]), now=NOW)["selected"] is None


def test_stale_lock_still_blocked_when_a_branch_backs_it():
    # Old lock, but a claude/issue-<N>-* branch exists -> the run is alive /
    # real; the branch guard fires first and it stays excluded.
    stale = issue(45, "2026-08-01T00:00:00Z", comments=[
        {"body": "🚢 SHIP-LOCK — shipping.", "createdAt": _iso(NOW - timedelta(hours=9))},
    ])
    assert select_issue(
        snap([stale], branches=["claude/issue-45-wip"]), now=NOW
    )["selected"] is None


def test_stale_lock_still_blocked_when_a_pr_backs_it():
    stale = issue(46, "2026-08-01T00:00:00Z", comments=[
        {"body": "🚢 SHIP-LOCK — shipping.", "createdAt": _iso(NOW - timedelta(hours=9))},
    ])
    assert select_issue(
        snap([stale], open_prs=[{"number": 9, "headRefName": "x", "body": "Closes #46"}]),
        now=NOW,
    )["selected"] is None


def test_no_now_treats_undated_lock_as_active():
    # Without a reference time, staleness cannot be judged; a claim is never
    # selected over (the conservative reading).
    old = issue(47, "2026-08-01T00:00:00Z", comments=[
        {"body": "🚢 SHIP-LOCK — shipping.", "createdAt": "2000-01-01T00:00:00Z"},
    ])
    assert select_issue(snap([old]))["selected"] is None


def test_non_ship_lock_comment_does_not_lock():
    # A comment that merely mentions ship-lock but isn't the marker line.
    issue_ = issue(43, "2026-08-01T00:00:00Z", comments=[
        {"body": "discussion about 🚢 SHIP-LOCK semantics", "createdAt": "2026-08-02T00:00:00Z"},
    ])
    # First line does not START with the marker -> not a claim.
    assert select_issue(snap([issue_]))["selected"] == 43


# --------------------------------------------------------------------------
# Guard: an open PR already closes the issue
# --------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    "Closes #50",
    "closes #50",
    "This fixes #50 in full",
    "Resolved: #50",
    "resolve #50",
    "fixed #50",
])
def test_open_pr_closing_keyword_excludes(body):
    s = snap([issue(50, "2026-08-01T00:00:00Z")],
             open_prs=[{"number": 200, "headRefName": "feature", "body": body}])
    assert select_issue(s)["selected"] is None


def test_open_pr_unrelated_does_not_exclude():
    # Negative control: a PR that closes a *different* issue leaves #50 free.
    s = snap([issue(50, "2026-08-01T00:00:00Z")],
             open_prs=[{"number": 200, "headRefName": "feature", "body": "Closes #51"}])
    assert select_issue(s)["selected"] == 50


def test_closing_keyword_does_not_match_number_prefix():
    # "#5" must not disqualify issue 50.
    s = snap([issue(50, "2026-08-01T00:00:00Z")],
             open_prs=[{"number": 200, "headRefName": "x", "body": "Closes #5"}])
    assert select_issue(s)["selected"] == 50


def test_open_pr_issue_branch_excludes():
    s = snap([issue(52, "2026-08-01T00:00:00Z")],
             open_prs=[{"number": 201, "headRefName": "claude/issue-52-foo", "body": "wip"}])
    assert select_issue(s)["selected"] is None


# --------------------------------------------------------------------------
# Guard: a claude/issue-<N>-* branch already exists
# --------------------------------------------------------------------------

def test_existing_issue_branch_excludes():
    excluded = select_issue(snap(
        [issue(60, "2026-08-01T00:00:00Z")],
        branches=["main", "claude/issue-60-wip"],
    ))
    assert excluded["selected"] is None
    # Negative control: without that branch the same issue is selected.
    assert select_issue(snap(
        [issue(60, "2026-08-01T00:00:00Z")],
        branches=["main", "claude/other-work"],
    ))["selected"] == 60


def test_issue_branch_prefix_is_boundary_safe():
    # A branch for issue 6 must not disqualify issue 60.
    s = snap([issue(60, "2026-08-01T00:00:00Z")], branches=["claude/issue-6-thing"])
    assert select_issue(s)["selected"] == 60


def test_malformed_issue_number_is_not_a_regex():
    # A malformed snapshot number must be treated as a literal, never as a
    # pattern: without re.escape, ".*" would match the unrelated #99 branch
    # and PR and be wrongly excluded. Escaped, it matches neither and stays
    # eligible.
    evil = issue(".*", "2026-08-01T00:00:00Z")
    s = snap(
        [evil],
        branches=["claude/issue-99-x"],
        open_prs=[{"number": 1, "headRefName": "y", "body": "Closes #99"}],
    )
    assert select_issue(s)["selected"] == ".*"


# --------------------------------------------------------------------------
# Guard: an issue parked for a human decision (needs-decision, issue #161)
# --------------------------------------------------------------------------

def test_needs_decision_excludes():
    # An otherwise-eligible issue parked for a human yes/no is skipped...
    parked = issue(90, "2026-08-01T00:00:00Z", labels=[LABEL, "needs-decision"])
    r = select_issue(snap([parked]))
    assert r["selected"] is None
    assert r["excluded"]["90"].startswith("awaiting a human decision")
    # ...and once the decision is recorded and the label cleared, it is
    # selectable again (negative control).
    resolved = issue(90, "2026-08-01T00:00:00Z", labels=[LABEL])
    assert select_issue(snap([resolved]))["selected"] == 90


def test_needs_decision_blocks_even_when_lock_is_stale():
    # The durable block: a decision-pending issue must stay excluded even after
    # a SHIP-LOCK the pausing run left has gone stale — the whole reason the
    # decision state is a label, not a lock. The guard's placement before the
    # lock check is what this proves.
    stale_locked = issue(
        91, "2026-08-01T00:00:00Z", labels=[LABEL, "needs-decision"],
        comments=[{"body": "🚢 SHIP-LOCK — shipping.",
                "createdAt": _iso(NOW - timedelta(hours=9))}],
    )
    assert select_issue(snap([stale_locked]), now=NOW)["selected"] is None
    # Negative control: the SAME stale lock WITHOUT needs-decision is takeable,
    # so it is the decision label — not the lock — doing the exclusion above.
    stale_only = issue(
        91, "2026-08-01T00:00:00Z", labels=[LABEL],
        comments=[{"body": "🚢 SHIP-LOCK — shipping.",
                "createdAt": _iso(NOW - timedelta(hours=9))}],
    )
    assert select_issue(snap([stale_only]), now=NOW)["selected"] == 91


# --------------------------------------------------------------------------
# Guard: a recent decline parks the brief until the owner replies (issue #530)
# --------------------------------------------------------------------------

def test_recent_decline_skips_for_the_next_brief():
    # The #515 shape: the oldest brief sits freshly declined, so the hourly
    # firing must move past it to the runnable brief behind, instead of
    # re-picking it, re-declining it and starving that one.
    blocked = issue(100, "2026-08-01T00:00:00Z", comments=[decline(3)])
    runnable = issue(101, "2026-08-02T00:00:00Z")
    r = select_issue(snap([blocked, runnable]), now=NOW)
    assert r["selected"] == 101
    assert "declin" in r["excluded"]["100"]


def test_decline_cooldown_expires():
    # A decline must never bury: only the decline timestamp varies, and past
    # the 24 h window the brief is eligible again.
    fresh = issue(102, "2026-08-01T00:00:00Z", comments=[decline(23)])
    assert select_issue(snap([fresh]), now=NOW)["selected"] is None
    expired = issue(102, "2026-08-01T00:00:00Z", comments=[decline(25)])
    assert select_issue(snap([expired]), now=NOW)["selected"] == 102


def test_owner_reply_re_arms_regardless_of_window():
    # A human comment newer than the latest decline re-arms immediately —
    # the owner answering the blocking question is exactly when the next
    # firing should take the brief (the #515 "Bottle answer" shape).
    answered = issue(103, "2026-08-01T00:00:00Z", comments=[
        decline(2),
        {"body": "**Bottle answer — the blocking question is closed: PCO-1881.**",
         "createdAt": _iso(NOW - timedelta(hours=1))},
    ])
    assert select_issue(snap([answered]), now=NOW)["selected"] == 103


def test_latest_decline_wins_and_restarts_the_window():
    # An old decline a run has since re-declined is fresh again: the marker
    # is a state read from the *latest* comment, exactly like a SHIP-LOCK.
    redeclined = issue(104, "2026-08-01T00:00:00Z", comments=[
        decline(30),
        decline(2),
    ])
    assert select_issue(snap([redeclined]), now=NOW)["selected"] is None


def test_run_comment_newer_than_the_decline_does_not_re_arm():
    # Withdrawals, parks, triage labels and chunk markers are machine posts
    # through the same PAT identity as the owner (#515: the declines, the
    # withdrawals and the owner's answer are all one login), so none of them
    # may re-arm the cooldown — only owner activity does.
    for body in (
        "🚢 SHIP-LOCK WITHDRAWN — yielding.",
        "🚦 DECISION NEEDED — `which-bottle`",
        "🏷️ Triaged: `autonomy-ok` — selector fix.",   # labeler emits the
        "🏷 Triaged: bare marker, no selector.",        # selector both ways
        "🧩 CHUNKED — sub-issues filed.",
    ):
        chattered = issue(105, "2026-08-01T00:00:00Z", comments=[
            decline(2),
            {"body": body, "createdAt": _iso(NOW - timedelta(hours=1))},
        ])
        assert select_issue(snap([chattered]), now=NOW)["selected"] is None, body


def test_bot_authored_comment_does_not_re_arm():
    # The marker-free leg of the run test: anything GitHub types as a Bot is
    # machine-posted whatever it wrote.
    botnoise = issue(106, "2026-08-01T00:00:00Z", comments=[
        decline(2),
        {"body": "workflow notification", "createdAt": _iso(NOW - timedelta(hours=1)),
         "authorType": "Bot"},
    ])
    assert select_issue(snap([botnoise]), now=NOW)["selected"] is None


def test_decline_marker_requires_the_first_line():
    # Prose that merely mentions a decline is not a decline — the same
    # first-line rule the SHIP-LOCK marker follows.
    mention = issue(107, "2026-08-01T00:00:00Z", comments=[
        {"body": "the last run posted a 🚢 DECLINED here, but that was answered",
         "createdAt": _iso(NOW - timedelta(hours=1))},
    ])
    assert select_issue(snap([mention]), now=NOW)["selected"] == 107


def test_withdrawn_lock_comment_is_not_a_decline():
    # 🚢 SHIP-LOCK WITHDRAWN shares the 🚢 prefix with DECLINED but is a
    # release, not a decline; dated and read by the decline guard it must
    # not trip it (test_withdrawn_lock_is_re_eligible covers the undated
    # path).
    withdrawn = issue(108, "2026-08-01T00:00:00Z", comments=[
        {"body": "🚢 SHIP-LOCK WITHDRAWN — yielding.",
         "createdAt": _iso(NOW - timedelta(hours=1))},
    ])
    assert select_issue(snap([withdrawn]), now=NOW)["selected"] == 108


def test_no_now_treats_decline_as_fresh():
    # Without a reference time the window cannot be judged; the conservative
    # reading keeps the brief out (mirrors the lock's undated-claim rule).
    undated = issue(109, "2026-08-01T00:00:00Z", comments=[decline(48)])
    assert select_issue(snap([undated]))["selected"] is None


# --------------------------------------------------------------------------
# The outcome record (AC4)
# --------------------------------------------------------------------------

def test_record_reports_reasons():
    s = snap(
        [
            issue(70, "2026-08-01T00:00:00Z", labels=["enhancement"]),  # no label
            issue(71, "2026-08-02T00:00:00Z"),                          # eligible
        ],
        branches=[],
    )
    r = select_issue(s)
    assert r["selected"] == 71
    assert "70" in r["excluded"]
    assert r["considered"] == 2


def test_render_summary_selected_and_empty():
    chosen = render_summary(select_issue(snap([issue(80, "2026-08-01T00:00:00Z")])))
    assert "#80" in chosen
    none = render_summary(select_issue(snap([issue(81, "2026-08-01T00:00:00Z", labels=[])])))
    assert "No issue selected" in none
