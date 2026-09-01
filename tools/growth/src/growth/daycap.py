"""Per-UTC-day live-post guard: has Lark already posted LIVE today?

Lark drains at most one queue item per calendar day (docs/growth.md). But
GitHub's scheduled workflow fires *unreliably* — heavily delayed, at an
arbitrary hour, and it drops most of a day's cron slots under load (observed:
deliveries at 21:55, 19:31 and 00:39 UTC on three consecutive days, ~one a
day). So the drain must run on WHATEVER firing GitHub delivers, not a specific
one — and the ≤1-post/day floor cannot be an hour lottery (that was the bug:
gating on ``now.hour == chosen_hour`` meant the single delayed firing almost
never matched, so the drain was skipped every day and nothing posted).

Instead the floor is a per-UTC-calendar-day guard, and this module owns its one
decision: given the desk's marker comments and today's UTC date, has a LIVE post
already gone out today? The signal is the posting tool's own claim-first marker
(``<!-- growth-twitter:posted -->``, imported from :mod:`growth.board` so there
is one marker string in the package, pinned to ``growth_mcp.py`` by
``test_board.py``), written BEFORE the live tweet and never removed — so a
same-day re-firing sees it and holds. The trusted Select step calls this
(``python3 -m growth daycap``) rather than deciding in bash, so the policy is
unit-tested.

Keyed on the LIVE marker ONLY: a dry-run writes only the ``dry-run`` marker, so
it never consumes the day — a dry-run-then-arm-live progression on the same
date still posts. The comparison is on the calendar DATE alone (a post at
23:59Z and one at 00:01Z are different days), which is exactly the
≤1-per-calendar-day contract and is immune to GitHub's delivery delay.
"""

from __future__ import annotations

from .board import POSTED_MARKER


def posted_today(comments: list[dict], today_iso: str) -> bool:
    """True iff any comment is a live-post marker dated ``today_iso`` (UTC
    ``YYYY-MM-DD``). ``comments`` is a list of ``{"body", "createdAt"}`` dicts
    in GitHub's shape (``createdAt`` an ISO-8601 UTC timestamp).

    A malformed comment must never CRASH the guard: a raised exception in the
    workflow's `growth daycap` call produces no ``posted`` on stdout, which the
    Select step reads as "clear" and posts — i.e. an exception fails OPEN. So a
    non-string ``body``/``createdAt`` (or a missing key) is coerced away and the
    comment skipped, never `in`-tested or sliced. A skipped malformed comment
    can only fail toward "clear", but GitHub always returns well-formed string
    comment fields, so this is defensive, not a real path."""
    for c in comments:
        body = c.get("body")
        created = c.get("createdAt")
        if not isinstance(body, str) or not isinstance(created, str):
            continue
        if POSTED_MARKER in body and created[:10] == today_iso:
            return True
    return False
