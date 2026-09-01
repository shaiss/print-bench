"""The per-UTC-day live-post guard: does a today-dated `posted` marker hold?

A positive case and a negative control per rule, plus the properties the ≤1
live-post/day guarantee rests on: only the LIVE marker counts, only TODAY
counts, and the comparison is on the calendar date alone.
"""

from growth import daycap
from growth.board import DRYRUN_MARKER, POSTED_MARKER

TODAY = "2026-09-01"


def _c(body, created):
    return {"body": body, "createdAt": created}


def test_posted_marker_today_holds():
    comments = [_c(f"tweet is live\n{POSTED_MARKER}", "2026-09-01T14:22:07Z")]
    assert daycap.posted_today(comments, TODAY) is True


def test_posted_marker_yesterday_does_not_hold():
    # The whole point: a post yesterday must not block today's post.
    comments = [_c(f"live\n{POSTED_MARKER}", "2026-08-31T23:59:00Z")]
    assert daycap.posted_today(comments, TODAY) is False


def test_dryrun_marker_today_does_not_hold():
    # Keyed on the LIVE marker only, so a dry-run never consumes the day —
    # a dry-run-then-arm-live progression on the same date still posts.
    comments = [_c(f"would have posted\n{DRYRUN_MARKER}", "2026-09-01T09:00:00Z")]
    assert daycap.posted_today(comments, TODAY) is False


def test_no_markers_does_not_hold():
    comments = [_c("just a human comment", "2026-09-01T10:00:00Z"),
                _c("another", "2026-09-01T11:00:00Z")]
    assert daycap.posted_today(comments, TODAY) is False


def test_empty_comments_does_not_hold():
    assert daycap.posted_today([], TODAY) is False


def test_finds_the_marker_among_many_comments():
    comments = [
        _c("human note", "2026-09-01T08:00:00Z"),
        _c(f"{DRYRUN_MARKER}\nold dry run", "2026-08-30T09:00:00Z"),
        _c(f"posted\n{POSTED_MARKER}", "2026-09-01T15:00:00Z"),
    ]
    assert daycap.posted_today(comments, TODAY) is True


def test_compares_on_calendar_date_not_time():
    # A post at 00:01Z today counts for today; the boundary is the date, so
    # 23:59Z yesterday and 00:01Z today are correctly different days.
    assert daycap.posted_today([_c(POSTED_MARKER, "2026-09-01T00:01:00Z")], TODAY) is True
    assert daycap.posted_today([_c(POSTED_MARKER, "2026-08-31T23:59:00Z")], TODAY) is False


def test_malformed_comment_never_crashes_into_a_double_post():
    # Missing keys are treated as empty, not an error — a malformed comment
    # must not throw (which a caller might swallow into "clear -> post again").
    comments = [{}, {"body": None, "createdAt": None},
                {"body": POSTED_MARKER, "createdAt": "2026-09-01T12:00:00Z"}]
    assert daycap.posted_today(comments, TODAY) is True
    assert daycap.posted_today([{}, {"body": None}], TODAY) is False
