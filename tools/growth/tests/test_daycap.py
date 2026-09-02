"""The per-UTC-day live-post cap: how many today-dated `posted` markers from
the trusted poster are there, and does the count hold at the cap?

A positive case and a negative control per rule, plus the properties the
≤`max_posts_per_day`/day guarantee rests on: only the LIVE marker counts, only
TODAY counts, only a TRUSTED AUTHOR counts (so an outsider can't suppress a
day), the comparison is on the calendar date alone, the bot's REST spelling
(`github-actions[bot]`) and GraphQL spelling (`github-actions`) both match (the
live bug — the Select step reads the GraphQL spelling), and the count holds the
firing only once it reaches the cap.
"""

from growth import daycap
from growth.board import DRYRUN_MARKER, POSTED_MARKER

TODAY = "2026-09-01"
BOT = "github-actions[bot]"          # the posting identity
TRUSTED = {BOT}


def _c(body, created, author=BOT):
    return {"body": body, "createdAt": created, "author": author}


def test_posted_marker_today_from_bot_holds():
    comments = [_c(f"tweet is live\n{POSTED_MARKER}", "2026-09-01T14:22:07Z")]
    assert daycap.posted_today(comments, TODAY, TRUSTED) is True


def test_posted_marker_yesterday_does_not_hold():
    # The whole point: a post yesterday must not block today's post.
    comments = [_c(f"live\n{POSTED_MARKER}", "2026-08-31T23:59:00Z")]
    assert daycap.posted_today(comments, TODAY, TRUSTED) is False


def test_dryrun_marker_today_does_not_hold():
    # Keyed on the LIVE marker only, so a dry-run never consumes the day —
    # a dry-run-then-arm-live progression on the same date still posts.
    comments = [_c(f"would have posted\n{DRYRUN_MARKER}", "2026-09-01T09:00:00Z")]
    assert daycap.posted_today(comments, TODAY, TRUSTED) is False


def test_marker_from_untrusted_author_does_not_hold():
    # The DoS guard: anyone can comment on a public queue issue. A `posted`
    # marker dated today from an OUTSIDER must be ignored — otherwise commenting
    # the marker string would suppress the day's real post.
    comments = [_c(f"nice tweet\n{POSTED_MARKER}", "2026-09-01T10:00:00Z",
                   author="random-outsider")]
    assert daycap.posted_today(comments, TODAY, TRUSTED) is False
    # ...but the SAME marker+date from the trusted bot does hold.
    comments.append(_c(POSTED_MARKER, "2026-09-01T15:00:00Z"))
    assert daycap.posted_today(comments, TODAY, TRUSTED) is True


def test_empty_trusted_set_holds_nothing():
    # Trust nobody -> nothing ever holds (the CLI requires a non-empty --author,
    # so this is a defensive property, not a live path).
    comments = [_c(POSTED_MARKER, "2026-09-01T12:00:00Z")]
    assert daycap.posted_today(comments, TODAY, set()) is False


def test_no_markers_does_not_hold():
    comments = [_c("just a human comment", "2026-09-01T10:00:00Z", author="someone"),
                _c("another", "2026-09-01T11:00:00Z")]
    assert daycap.posted_today(comments, TODAY, TRUSTED) is False


def test_empty_comments_does_not_hold():
    assert daycap.posted_today([], TODAY, TRUSTED) is False


def test_finds_the_marker_among_many_comments():
    comments = [
        _c("human note", "2026-09-01T08:00:00Z", author="someone"),
        _c(f"{DRYRUN_MARKER}\nold dry run", "2026-08-30T09:00:00Z"),
        _c(f"posted\n{POSTED_MARKER}", "2026-09-01T15:00:00Z"),
    ]
    assert daycap.posted_today(comments, TODAY, TRUSTED) is True


def test_compares_on_calendar_date_not_time():
    # A post at 00:01Z today counts for today; the boundary is the date, so
    # 23:59Z yesterday and 00:01Z today are correctly different days.
    assert daycap.posted_today([_c(POSTED_MARKER, "2026-09-01T00:01:00Z")], TODAY, TRUSTED) is True
    assert daycap.posted_today([_c(POSTED_MARKER, "2026-08-31T23:59:00Z")], TODAY, TRUSTED) is False


def test_malformed_comment_never_crashes_into_a_double_post():
    # Missing keys, None, AND non-string truthy values are all skipped, not an
    # error — a raised exception produces no "posted" on stdout, which the
    # workflow reads as "clear" and posts (fails OPEN). `POSTED_MARKER in 5` or
    # slicing an int would raise, so these must be coerced away, not tested.
    comments = [
        {},
        {"body": None, "createdAt": None, "author": None},
        {"body": 5, "createdAt": 20260901, "author": 7},          # non-string truthy
        {"body": ["x"], "createdAt": {"z": 1}, "author": ["a"]},  # non-string truthy
        _c(POSTED_MARKER, "2026-09-01T12:00:00Z"),
    ]
    assert daycap.posted_today(comments, TODAY, TRUSTED) is True
    # No real marker anywhere → clear, and still no crash on the junk values.
    assert daycap.posted_today([{}, {"body": None}, {"body": 5, "createdAt": 1, "author": 2}],
                               TODAY, TRUSTED) is False


def test_gh_graphql_bot_spelling_is_recognized():
    # THE live bug this fix closes. The Select step reads the comment author via
    # `gh issue view --json comments` (GraphQL), whose Actor.login for the
    # Actions bot is "github-actions" (NO "[bot]" suffix), while the workflow
    # passes the trusted login as the REST spelling "github-actions[bot]". The
    # guard MUST match the two spellings of the same bot — otherwise it rejects
    # its OWN posting tool's marker and never holds, silently disabling the
    # ≤N/day cap (only noticed on a day two firings both post). The original
    # test passed only because it fed the REST spelling the live scan never
    # produces; this feeds the GraphQL spelling that it does.
    graphql = _c(f"live\n{POSTED_MARKER}", "2026-09-01T14:22:07Z", author="github-actions")
    assert daycap.posts_today([graphql], TODAY, {"github-actions[bot]"}) == 1
    assert daycap.posted_today([graphql], TODAY, {"github-actions[bot]"}) is True


def test_bot_suffix_normalized_both_directions():
    # Whichever spelling the comment carries and whichever the caller trusts,
    # the same bot matches.
    for comment_author, trusted in [
        ("github-actions", {"github-actions[bot]"}),   # GraphQL comment, REST trust (the live path)
        ("github-actions[bot]", {"github-actions"}),   # REST comment, GraphQL trust
        ("github-actions[bot]", {"github-actions[bot]"}),
        ("github-actions", {"github-actions"}),
    ]:
        c = [_c(POSTED_MARKER, "2026-09-01T12:00:00Z", author=comment_author)]
        assert daycap.posts_today(c, TODAY, trusted) == 1, (comment_author, trusted)


def test_dos_guard_survives_normalization():
    # Stripping a trailing "[bot]" must NOT let an outsider count. A human named
    # "random-outsider" never matches, and even a "[bot]"-suffixed impostor that
    # normalizes to "eve" is not the poster — and GitHub reserves the real bot
    # names, so no human can register one that normalizes to "github-actions".
    c = [_c(POSTED_MARKER, "2026-09-01T10:00:00Z", author="random-outsider"),
         _c(POSTED_MARKER, "2026-09-01T11:00:00Z", author="eve[bot]")]  # normalizes to "eve"
    assert daycap.posts_today(c, TODAY, {"github-actions[bot]"}) == 0


def test_posts_today_counts_each_live_post():
    # One POSTED_MARKER per live post (the claim comment; the close comment
    # carries only the header), so the count IS the number of posts made today —
    # what a cap > 1 is compared against.
    comments = [
        _c(f"post A\n{POSTED_MARKER}", "2026-09-01T13:19:00Z"),
        _c(f"post B\n{POSTED_MARKER}", "2026-09-01T15:19:00Z"),
        _c(f"yesterday\n{POSTED_MARKER}", "2026-08-31T13:19:00Z"),  # not today
        _c(f"dry run\n{DRYRUN_MARKER}", "2026-09-01T17:19:00Z"),    # not a live post
    ]
    assert daycap.posts_today(comments, TODAY, TRUSTED) == 2


def test_cap_holds_only_when_count_reaches_it():
    two = [
        _c(f"A\n{POSTED_MARKER}", "2026-09-01T13:19:00Z"),
        _c(f"B\n{POSTED_MARKER}", "2026-09-01T15:19:00Z"),
    ]
    one = two[:1]
    # cap of 2 (the shipped default): one post -> clear, two posts -> hold
    assert daycap.posted_today(one, TODAY, TRUSTED, cap=2) is False
    assert daycap.posted_today(two, TODAY, TRUSTED, cap=2) is True
    # cap of 1 (the strict ≤1 posture): the first post already holds
    assert daycap.posted_today(one, TODAY, TRUSTED, cap=1) is True
