"""Per-UTC-day live-post cap: how many LIVE posts has Lark made today?

Lark drains a bounded number of queue items per calendar day (``max_posts_per_day``
in ``.github/growth-twitter.conf`` — docs/growth.md). But GitHub's scheduled
workflow fires *unreliably* — heavily delayed, at an arbitrary hour, and it
drops most of a day's cron slots under load (observed: deliveries at 21:55,
19:31 and 00:39 UTC on three consecutive days, ~one a day). So the drain must
run on WHATEVER firing GitHub delivers, not a specific one — and the daily cap
cannot be an hour lottery (that was the bug: gating on ``now.hour ==
chosen_hour`` meant the single delayed firing almost never matched, so the
drain was skipped every day and nothing posted).

Instead the cap is a per-UTC-calendar-day count, and this module owns its one
decision: given the desk's marker comments and today's UTC date, HOW MANY live
posts have already gone out today? The signal is the posting tool's own
claim-first marker (``<!-- growth-twitter:posted -->``, imported from
:mod:`growth.board` so there is one marker string in the package, pinned to
``growth_mcp.py`` by ``test_board.py``), written BEFORE the live tweet and
never removed — and exactly one per live post (the claim comment; the closing
comment carries only the header). So counting markers = counting posts. The
trusted Select step calls this (``python3 -m growth daycap``) rather than
deciding in bash, so the policy is unit-tested; it holds the firing once the
count reaches the configured cap.

Keyed on the LIVE marker ONLY: a dry-run writes only the ``dry-run`` marker, so
it never consumes the day — a dry-run-then-arm-live progression on the same
date still posts. The comparison is on the calendar DATE alone (a post at
23:59Z and one at 00:01Z are different days), which is exactly the
per-calendar-day contract and is immune to GitHub's delivery delay.

AUTHENTICATED: a marker is only trusted from the posting identity (the
workflow's GitHub Actions bot). Anyone can comment on a public queue issue, so
an unauthenticated marker would let an outsider suppress a day's post by
commenting the marker string — a denial-of-service. Only a marker authored by
a caller-supplied trusted login counts.

BOT-IDENTITY NORMALIZATION (the bug this module was silently carrying): GitHub
names the Actions bot two ways — the REST API's ``user.login`` is
``github-actions[bot]`` while the GraphQL ``author.login`` that ``gh issue view
--json comments`` returns is ``github-actions`` (no ``[bot]`` suffix). The
Select step reads authors via ``gh`` (GraphQL), so the marker's author arrives
as ``github-actions`` — but the guard was hardened to trust ``github-actions[bot]``
literally, so it rejected its OWN posting tool's markers and never held (the
≤N/day cap was effectively disabled; the unit test passed only because it fed
the REST spelling, which the live scan never produces). We normalize both the
trusted logins and each comment author by stripping a trailing ``[bot]`` before
comparing, so the two spellings of the same bot match — and the DoS guard is
unweakened, because a human cannot register a login of ``github-actions`` or
``github-actions[bot]`` (GitHub reserves both).
"""

from __future__ import annotations

from collections.abc import Iterable

from .board import POSTED_MARKER


def _norm(login: str) -> str:
    """Collapse a GitHub actor login to a spelling that matches across REST and
    GraphQL: strip a trailing ``[bot]`` (REST's ``github-actions[bot]`` and
    GraphQL's ``github-actions`` both become ``github-actions``). Reserved bot
    names mean this cannot let a human impersonate the poster."""
    return login[:-5] if login.endswith("[bot]") else login


def posts_today(comments: list[dict], today_iso: str,
                trusted_authors: Iterable[str]) -> int:
    """Count the LIVE-post markers (``POSTED_MARKER``) dated ``today_iso`` (UTC
    ``YYYY-MM-DD``) authored by one of ``trusted_authors`` (GitHub logins the
    posting tool posts as; matched with ``[bot]``-suffix normalization).
    ``comments`` is a list of ``{"body", "createdAt", "author"}`` dicts in
    GitHub's shape. The posting tool writes exactly one marker per live post, so
    this count IS the number of live posts made today.

    An EMPTY ``trusted_authors`` trusts nobody (count is always 0) — the caller
    must pass the poster identity; the CLI requires it.

    A malformed comment must never CRASH the guard: a raised exception in the
    workflow's `growth daycap` call produces no decision on stdout, which the
    Select step reads as "clear" and posts — i.e. an exception fails OPEN. So a
    non-string ``body``/``createdAt``/``author`` (or a missing key) is coerced
    away and the comment skipped, never `in`-tested or sliced. GitHub always
    returns well-formed string comment fields, so this is defensive."""
    trusted = {_norm(a) for a in trusted_authors}
    n = 0
    for c in comments:
        body = c.get("body")
        created = c.get("createdAt")
        author = c.get("author")
        if (not isinstance(body, str) or not isinstance(created, str)
                or not isinstance(author, str)):
            continue
        if _norm(author) in trusted and POSTED_MARKER in body and created[:10] == today_iso:
            n += 1
    return n


def posted_today(comments: list[dict], today_iso: str,
                 trusted_authors: Iterable[str], cap: int = 1) -> bool:
    """True iff today's live-post count has REACHED ``cap`` — i.e. the daily cap
    is spent and this firing must hold. With the default ``cap=1`` this is the
    ≤1/day question ("has any live post gone out today?"); the workflow passes
    the configured ``max_posts_per_day``."""
    return posts_today(comments, today_iso, trusted_authors) >= cap
