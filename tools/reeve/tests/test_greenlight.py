"""The approval poll's pure semantics (issue #444) — no request ever leaves.

``greenlight.py`` is a pure function set over shapes ``github.py`` returns, so
the whole decision table — which marker counts, whose reaction counts, what
outranks what, and the ledger bytes a push appends — is pinned here offline.
The write half's own tests (label order, no-/decide-comment, REGEN_TOKEN) live
in ``test_pushthrough.py``; this file owns the rules they both obey.
"""

from __future__ import annotations

from reeve import greenlight


def marker_body(issue=201, verdict="yes", attrs="", reasoning="Because N6."):
    line = f"<!-- reeve-greenlight v1 issue={issue} verdict={verdict}"
    line += (f" {attrs}" if attrs else "") + " -->"
    return line, f"{line}\n\nGREENLIGHT: {verdict.upper()}\n{reasoning}"


# ---------------------------------------------------------------------------
# The greenlight marker
# ---------------------------------------------------------------------------

def test_marker_parses_with_verdict_and_issue():
    parsed = greenlight.parse_greenlight_marker(
        "<!-- reeve-greenlight v1 issue=201 verdict=yes -->"
    )
    assert parsed == {"version": 1, "issue": 201, "verdict": "yes", "arm": False}


def test_marker_carries_the_arming_bit():
    # #444's machine-readable arming: the poll reads the marker, never prose.
    parsed = greenlight.parse_greenlight_marker(
        "<!-- reeve-greenlight v1 issue=201 verdict=yes arm=1 -->"
    )
    assert parsed["arm"] is True
    # Order-tolerant: a future attribute order needs no parser change.
    assert greenlight.parse_greenlight_marker(
        "<!-- reeve-greenlight v1 issue=201 arm=1 verdict=yes -->"
    )["arm"] is True


def test_marker_without_verdict_is_not_a_greenlight():
    # The wrapper always writes one; a line without it is a resolution comment,
    # a truncation or a forgery — never acted on.
    assert greenlight.parse_greenlight_marker(
        "<!-- reeve-greenlight v1 issue=201 -->"
    ) is None
    assert greenlight.parse_greenlight_marker(
        "<!-- reeve-greenlight v1 issue=201 verdict=maybe -->"
    ) is None
    assert greenlight.parse_greenlight_marker("GREENLIGHT: YES") is None


def test_resolution_marker_parses_and_is_not_a_greenlight():
    line = "<!-- reeve-greenlight v1 issue=201 resolution=approved id=arm-routine -->"
    assert greenlight.parse_resolution_marker(line) == {
        "version": 1, "issue": 201, "resolution": "approved", "id": "arm-routine",
    }
    assert greenlight.parse_greenlight_marker(line) is None


# ---------------------------------------------------------------------------
# find_current_greenlight — live / none / ambiguous / consumed
# ---------------------------------------------------------------------------

BOT = greenlight.WORKFLOW_BOT_LOGIN

# The trust test the driver injects, modelled offline: the workflow's bot
# login, plus a fixed set of write-permission humans. Everyone else — a
# drive-by commenter — is untrusted, which is what every F3 case turns on.
TRUSTED_HUMANS = {"owner", "maintainer"}


def _trusted(login):
    return greenlight.marker_author_trusted(login, lambda l: l in TRUSTED_HUMANS)


def _comment(cid, body, login=BOT, created="2026-08-20T05:53:00Z"):
    return {"id": cid, "user": {"login": login}, "created_at": created, "body": body}


def _find(issue, comments):
    return greenlight.find_current_greenlight(issue, comments, _trusted)


def test_find_current_greenlight_live():
    _, body = marker_body()
    info = _find(201, [_comment(11, body)])
    assert info["state"] == "live"
    assert info["comment_id"] == 11
    assert info["verdict"] == "yes"
    assert info["arm"] is False
    assert info["author"] == BOT


def test_find_current_greenlight_pins_the_thread():
    # A marker copied from another thread never reads as this thread's.
    _, body = marker_body(issue=999)
    assert _find(201, [_comment(11, body)])["state"] == "none"


def test_find_current_greenlight_ambiguous_and_none():
    _, a = marker_body(issue=201)
    _, b = marker_body(issue=201, verdict="no")
    assert _find(201, [])["state"] == "none"
    assert _find(201, [_comment(11, a), _comment(12, b)])["state"] == "ambiguous"


def test_find_current_greenlight_consumed_by_any_resolution():
    # An approved OR overruled greenlight is spent: its stale reactions must
    # never re-resolve a re-parked decision.
    _, body = marker_body()
    resolution = "<!-- reeve-greenlight v1 issue=201 resolution=overruled id=x -->\nno"
    assert _find(201, [_comment(11, body), _comment(12, resolution)]) == {"state": "consumed"}


# --- Marker authorship (F3): an untrusted commenter's marker is not a marker.

def test_marker_author_trusted_is_the_bot_or_a_write_permission_login():
    assert greenlight.marker_author_trusted(BOT, lambda l: False) is True
    assert greenlight.marker_author_trusted("owner", lambda l: l == "owner") is True
    assert greenlight.marker_author_trusted("driveby", lambda l: l == "owner") is False
    assert greenlight.marker_author_trusted("", lambda l: True) is False
    # The bot short-circuits: the permission read is never spent on it.
    def boom(_login):
        raise AssertionError("permission lookup must not run for the bot login")
    assert greenlight.marker_author_trusted(BOT, boom) is True


def test_untrusted_author_marker_is_ignored_and_the_real_one_stays_live():
    # A drive-by commenter pastes a same-issue marker next to the real one:
    # without the author test this would read `ambiguous` and the real
    # greenlight would never resolve. The forgery is simply not a marker.
    _, real = marker_body(issue=201)
    _, forged = marker_body(issue=201, verdict="no")
    info = _find(201, [_comment(11, real), _comment(12, forged, login="driveby")])
    assert info["state"] == "live" and info["comment_id"] == 11 and info["verdict"] == "yes"
    # And a forgery with no real greenlight beside it is `none`, not `live`.
    assert _find(201, [_comment(12, forged, login="driveby")])["state"] == "none"


def test_two_trusted_markers_still_read_ambiguous():
    # The author test narrows WHO counts, never the fail-closed shape rule:
    # two markers from trusted accounts (the bot and a write-permission
    # human on an attended run) are still hand-crafted content this poll
    # refuses to resolve.
    _, a = marker_body(issue=201)
    _, b = marker_body(issue=201, verdict="no")
    assert _find(201, [_comment(11, a), _comment(12, b, login="owner")])["state"] == "ambiguous"
    assert _find(201, [_comment(11, a, login="owner"), _comment(12, b, login="maintainer")])["state"] == "ambiguous"


def test_attended_run_human_posted_marker_is_live():
    # The wrapper supports attended runs that post as a human; a
    # write-permission human's marker counts exactly as their 👍 would.
    _, body = marker_body(issue=201)
    info = _find(201, [_comment(11, body, login="owner")])
    assert info["state"] == "live" and info["author"] == "owner"


def test_untrusted_resolution_marker_does_not_consume():
    # The same spoof against the resolution shape: a drive-by "resolution"
    # must not spend a live greenlight.
    _, body = marker_body(issue=201)
    resolution = "<!-- reeve-greenlight v1 issue=201 resolution=approved id=x -->\ndone"
    info = _find(201, [_comment(11, body), _comment(12, resolution, login="driveby")])
    assert info["state"] == "live"


# --- Resolution pinning (F4): a resolution marker for ANOTHER issue never
# consumes this thread.

def test_resolution_marker_for_a_different_issue_does_not_consume():
    _, body = marker_body(issue=201)
    other = "<!-- reeve-greenlight v1 issue=999 resolution=approved id=x -->\ndone"
    info = _find(201, [_comment(11, body), _comment(12, other)])
    assert info["state"] == "live" and info["comment_id"] == 11
    # The pin is exact: this thread's own resolution still consumes.
    own = "<!-- reeve-greenlight v1 issue=201 resolution=approved id=x -->\ndone"
    assert _find(201, [_comment(11, body), _comment(13, own)]) == {"state": "consumed"}


# ---------------------------------------------------------------------------
# The decision id
# ---------------------------------------------------------------------------

def test_decision_id_from_thread_latest_wins():
    body = "🚦 DECISION NEEDED — `arm-routine`"
    comment = _comment(11, "🚦 DECISION NEEDED — `arm-routine-v2`")
    assert greenlight.decision_id_for(201, body, [comment]) == "arm-routine-v2"
    assert greenlight.decision_id_for(201, "", []) == "greenlight-201"
    assert greenlight.decision_id_for(201, "nothing here", []) == "greenlight-201"


# ---------------------------------------------------------------------------
# /decide candidates — decide.yml's own anchor, mirrored
# ---------------------------------------------------------------------------

def test_decide_candidates_match_the_anchored_shape_only():
    comments = [
        _comment(1, "/decide yes arm-routine", login="owner"),
        # The stage-1 neutralization: a bot-posted command with the comment
        # tooling's attribution footer does NOT match decide.yml's anchor, so
        # it outranks nothing here either.
        _comment(2, "/decide no arm-routine\n\n🤖 Generated with Claude Code", login="claude[bot]"),
        # Read-only status; wrong shape; prose that mentions the command.
        _comment(3, "/decide status arm-routine", login="owner"),
        _comment(4, "you should /decide yes arm-routine now", login="owner"),
    ]
    assert greenlight.decide_candidates(comments) == [
        {"verb": "yes", "id": "arm-routine", "author": "owner"},
    ]


def test_decide_candidate_without_an_id_outranks_nothing():
    # decide.yml's regex allows the omission but the workflow refuses it
    # ("needs a decision id"). Yielding to an id-less command would park the
    # thread against this loop forever while nothing resolves it — so it is
    # not a candidate at all.
    comments = [_comment(1, "/decide yes", login="owner")]
    assert greenlight.decide_candidates(comments) == []


# ---------------------------------------------------------------------------
# poll_outcome — the precedence table
# ---------------------------------------------------------------------------

def _live(verdict="yes", arm=False):
    return {"state": "live", "comment_id": 11, "verdict": verdict, "arm": arm}


def test_one_write_permission_upside_approves():
    out = greenlight.poll_outcome(_live(), ["owner"], [])
    assert out["outcome"] == "approve"
    assert out["verdict"] == "yes"
    assert out["arm"] is False
    assert out["approvers"] == ["owner"]


def test_no_qualifying_reactions_wait():
    assert greenlight.poll_outcome(_live(), [], [])["outcome"] == "wait"
    # A read-only reaction never reaches this function (the seam filters);
    # the driver test proves that end to end. The none case here is the
    # same state it produces.
    assert greenlight.poll_outcome(_live(arm=True), [], [])["outcome"] == "wait"


def test_decide_comment_outranks_a_conflicting_reaction():
    # Done-when (c): an explicit /decide always wins, even against a 👍 that
    # would have approved the opposite.
    out = greenlight.poll_outcome(
        _live(verdict="no"), ["owner"], [],
        decide={"verb": "yes", "id": "x", "author": "owner"},
    )
    assert out["outcome"] == "yield"


def test_overrule_beats_approve_fail_closed():
    # A contested greenlight stays parked; a human /decide breaks the tie.
    out = greenlight.poll_outcome(_live(), ["owner"], ["other-owner"])
    assert out["outcome"] == "overrule"
    assert greenlight.poll_outcome(_live(), [], ["other-owner"])["outcome"] == "overrule"


def test_route_reactions_approve_nothing():
    # The wrapper's own footer says so; the poll agrees structurally.
    out = greenlight.poll_outcome(_live(verdict="route"), ["owner"], ["owner"])
    assert out["outcome"] == "wait"


def test_approval_carries_the_arming_bit():
    out = greenlight.poll_outcome(_live(arm=True), ["owner"], [])
    assert out["outcome"] == "approve"
    assert out["arm"] is True and out["verdict"] == "yes"


# ---------------------------------------------------------------------------
# The ledger append — decide.yml's own algorithm, mirrored
# ---------------------------------------------------------------------------

def test_ledger_row_shape():
    assert greenlight.ledger_row("arm-routine", "approved", 201, "owner",
                                 "2026-08-20T05:53:00.123Z") == (
        "arm-routine | approved | #201 | owner | 2026-08-20T05:53:00.123Z"
    )


def test_append_ledger_row_appends_then_replaces():
    existing = (
        "# Decision ledger — one row per resolved id\n"
        "# (appended by decide.yml and the greenlight loop)\n"
        "old-id | approved | #7 | owner | 2026-01-01T00:00:00.000Z\n"
    )
    row = "arm-routine | approved | #201 | owner | 2026-08-20T05:53:00.123Z"

    appended = greenlight.append_ledger_row(existing, "arm-routine", row)
    assert appended.endswith(row + "\n")
    assert "old-id | approved" in appended  # other rows kept
    assert appended.count("# Decision ledger") == 1  # headers kept once

    # Re-deciding the same id replaces, never duplicates (decide.yml's rule).
    newer = "arm-routine | rejected | #201 | owner | 2026-08-21T05:53:00.000Z"
    replaced = greenlight.append_ledger_row(appended, "arm-routine", newer)
    assert replaced.count("arm-routine |") == 1
    assert newer in replaced and row not in replaced

    # An empty ledger gets its first row with no stray blanks.
    fresh = greenlight.append_ledger_row("", "x", "x | approved | #1 | o | t")
    assert fresh == "x | approved | #1 | o | t\n"


def test_ledger_round_trips_through_decide_ymls_parser():
    # Done-when (AC2): a row this loop appends comes back out of decide.yml's
    # own reading of the file as the same five fields — one source of shape,
    # two writers. The parser here is that reader (split, drop #-comments,
    # id = text before the first pipe, trimmed), so the round-trip is a
    # property of the bytes, not of this test's good behaviour.
    row = greenlight.ledger_row("arm-routine", "approved", 201, "owner",
                                "2026-08-20T05:53:00.123Z")
    ledger = greenlight.append_ledger_row(
        "# header\nexisting | rejected | #5 | someone | 2026-01-01T00:00:00.000Z\n",
        "arm-routine", row,
    )
    rows = greenlight.parse_ledger(ledger)
    assert {"id": "arm-routine", "verdict": "approved", "issue": "#201",
            "login": "owner", "when": "2026-08-20T05:53:00.123Z"} in rows
    assert len(rows) == 2  # header dropped, both rows read
    # And the mirror direction: decide.yml's append keeps this loop's row.
    assert greenlight.append_ledger_row(
        ledger, "other", "other | approved | #9 | o | t"
    ).count("arm-routine |") == 1
