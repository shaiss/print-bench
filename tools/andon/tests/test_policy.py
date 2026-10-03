"""The pure core — a positive and a negative control per rule."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from andon import policy
from andon.policy import Decision, OpenIssue

T0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
OPEN = OpenIssue(number=77, created_at=T0)


# ---------------------------------------------------------------------------
# is_pulled — mirrors GitHub's case-insensitive expression == EXACTLY:
# case-folded, never whitespace-trimmed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["pulled", "Pulled", "PULLED", "pULLED"])
def test_is_pulled_accepts_case_variants(raw):
    assert policy.is_pulled(raw) is True


@pytest.mark.parametrize("raw", [None, "", "released", "false", "true", "pull", "pulled!", "un-pulled"])
def test_is_pulled_rejects_everything_else(raw):
    # 'true' is NOT pulled: the cord is the WORD, not a boolean, so a habit
    # from the *_ENABLED arming variables cannot pull it by accident.
    assert policy.is_pulled(raw) is False


@pytest.mark.parametrize("raw", ["pulled ", " pulled", " pulled ", "\tPulled\n", "pulled\n", "PULLED "])
def test_is_pulled_rejects_whitespace_padding_exactly_like_github(raw):
    # The split-brain guard. GitHub's `vars.AI_ANDON_CORD == 'pulled'` is
    # case-insensitive but does NOT trim, so a padded value is RELEASED to
    # every workflow gate (the AI jobs keep running). If the tool forgave
    # the padding it would open the status issue and Reeve would banner a
    # bypass that is not happening — so the tool must read it as released.
    assert policy.is_pulled(raw) is False


def test_is_pulled_is_exactly_githubs_rule_side_by_side():
    # The three cases the doc names, pinned together: case is folded,
    # whitespace is not.
    assert policy.is_pulled("PULLED") is True
    assert policy.is_pulled("pulled ") is False
    assert policy.is_pulled(" pulled") is False


# ---------------------------------------------------------------------------
# decide — all four branches
# ---------------------------------------------------------------------------

def test_pulled_with_nothing_open_opens():
    d = policy.decide(True, None)
    assert d.action == "open"
    assert d.issue_number is None


def test_pulled_with_open_issue_is_a_noop_naming_the_since():
    d = policy.decide(True, OPEN)
    assert d.action == "none"
    assert d.issue_number == 77
    assert "still pulled since 2026-09-01T10:00:00Z" in d.reason


def test_released_with_open_issue_closes():
    d = policy.decide(False, OPEN)
    assert d.action == "close"
    assert d.issue_number == 77


def test_released_with_nothing_open_is_a_noop():
    d = policy.decide(False, None)
    assert d.action == "none"
    assert d.issue_number is None


def test_decision_refuses_an_unknown_action():
    # Negative control on the closed action set the workflow branches on.
    with pytest.raises(ValueError, match="unknown action"):
        Decision("reopen", None, "?")


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["2026-09-01T10:00:00Z", "2026-09-01T10:00:00+00:00",
                                  "2026-09-01T12:00:00+02:00", "2026-09-01T10:00:00"])
def test_parse_iso_normalises_to_utc(text):
    assert policy.parse_iso(text) == T0


def test_parse_iso_rejects_garbage():
    with pytest.raises(ValueError):
        policy.parse_iso("garbage")


def test_iso_renders_z_form_in_utc():
    assert policy.iso(T0) == "2026-09-01T10:00:00Z"
    assert policy.iso(datetime(2026, 9, 1, 12, 0, tzinfo=timezone(timedelta(hours=2)))) == "2026-09-01T10:00:00Z"


@pytest.mark.parametrize("delta, expected", [
    (timedelta(0), "under an hour"),
    (timedelta(minutes=59), "under an hour"),
    (timedelta(minutes=90), "about 1 hour"),
    (timedelta(hours=2), "about 2 hours"),
    (timedelta(hours=24), "about 1 day"),
    (timedelta(days=3, hours=4), "about 3 days 4 hours"),
    (timedelta(days=1, hours=1, minutes=30), "about 1 day 1 hour"),
    (timedelta(hours=-5), "under an hour"),  # clamped, never negative
])
def test_format_duration(delta, expected):
    assert policy.format_duration(delta) == expected


def test_format_duration_never_says_minus():
    assert "-" not in policy.format_duration(timedelta(days=-2))


# ---------------------------------------------------------------------------
# Rendered text
# ---------------------------------------------------------------------------

def test_open_body_starts_with_the_marker_on_its_own_line():
    body = policy.render_open_body(T0)
    assert body.startswith(policy.MARKER + "\n")


def test_open_body_names_the_variable_the_doc_and_the_observation_time():
    body = policy.render_open_body(T0)
    assert policy.VARIABLE in body
    assert policy.DOC in body
    assert "2026-09-01T10:00:00Z" in body
    assert "closes itself" in body
    assert "signoff-override" in body  # the design-PR consequence is stated
    assert "hourly" in body  # the granularity caveat


def test_open_body_link_is_absolute_when_the_repo_is_known():
    assert "https://github.com/o/r/blob/main/docs/andon-cord.md" in policy.render_open_body(T0, "o/r")
    assert "https://github.com" not in policy.render_open_body(T0)


def test_status_issue_labels_are_never_the_decision_gate():
    # The status issue must never look like a decision request (#161):
    # `needs-decision` parks the autonomy selector, and the issue is
    # informational. tests/test_workflow.py pins the workflow's labels array
    # to exactly these two.
    assert "needs-decision" not in (policy.LABEL, policy.NOTICE_LABEL)


def test_close_comment_names_both_timestamps_and_the_span():
    now = T0 + timedelta(days=3, hours=4, minutes=7)
    text = policy.render_close_comment(T0, now)
    assert "2026-09-01T10:00:00Z" in text
    assert "2026-09-04T14:07:00Z" in text
    assert "about 3 days 4 hours" in text
    assert text.startswith("🟢 AI andon cord released")


def test_close_comment_clamps_a_skewed_clock():
    text = policy.render_close_comment(T0, T0 - timedelta(hours=2))
    assert "under an hour" in text


_VERB = re.compile(r"\b(POST|PATCH|PUT|DELETE)\b")


def test_rendered_output_contains_no_write_verbs():
    # The rendered text is what the workflow writes; it must not carry a
    # write verb either, or the purity scan's promise would be hollow.
    assert _VERB.search(policy.render_open_body(T0, "o/r")) is None
    assert _VERB.search(policy.render_close_comment(T0, T0 + timedelta(hours=5), "o/r")) is None


def test_constants_are_the_shape_the_workflow_expects():
    assert policy.MARKER.startswith("<!--") and policy.MARKER.endswith("-->")
    assert policy.LABEL == "andon-cord"
    assert policy.NOTICE_LABEL == "notice"
    assert policy.TITLE.startswith("🛑")
    assert policy.VARIABLE == "AI_ANDON_CORD"
