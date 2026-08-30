"""Post-time jitter: pick ONE of a day's candidate firing hours, per date.

Lark posts at most once a day, but a fixed cron makes every tweet land at the
same clock time — a robotic drumbeat. To make the feed read organic without
posting more than once a day, the workflow fires at SEVERAL candidate slots
across a daily window (the cron's hour field, e.g. ``19 13-21/2 * * *`` →
13:19, 15:19, 17:19, 19:19, 21:19 UTC) and only ONE of them ACTS each day —
which one is chosen pseudo-randomly *per date*, so the post lands at a time
that varies day to day.

The choice is **deterministic and reproducible** — seeded by the UTC date
alone, no external state — so the same date always resolves to the same slot
(a run can be re-derived, tested, and simulated), yet the slot walks across
the window as the date changes. It is the growth desk's own small scheduling
policy, tested here rather than hidden in workflow YAML, the same discipline
`queue.drain_order` and `tweetlen` follow.

A cadence with a SINGLE candidate hour (the shape every other routine here
uses, and Lark's own before this feature) always resolves to that one hour —
``is_post_slot`` is a no-op there, so nothing else changes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from .cron import Cron


def candidate_hours(cadence: str) -> list[int]:
    """The sorted candidate posting hours a cadence fires at — its cron hour
    field expanded. ``19 13-21/2 * * *`` → ``[13, 15, 17, 19, 21]``."""
    return sorted(Cron(cadence).hours)


def chosen_hour(date_iso: str, hours: list[int]) -> int:
    """The one hour (from ``hours``) chosen for the UTC date ``date_iso``
    (``YYYY-MM-DD``). A deterministic, uniform-over-days pick: the SHA-256 of
    the date indexes the sorted candidate list, so the same date + hours always
    give the same hour, and the choice walks the window across dates. Raises on
    an empty candidate list — a cadence that fires at no hour posts nothing."""
    if not hours:
        raise ValueError("no candidate hours to choose from")
    digest = hashlib.sha256(date_iso.encode()).hexdigest()
    return hours[int(digest, 16) % len(hours)]


def is_post_slot(now: datetime, cadence: str) -> bool:
    """True iff ``now``'s hour is the chosen posting hour for ``now``'s UTC
    date, among the cadence's candidate hours. ``now`` is a naive-UTC datetime
    (the repo's crons are UTC, matching :mod:`growth.cron`). A single-candidate
    cadence always matches its one hour, so this is inert for the fixed-slot
    routines and only jitters a multi-slot window."""
    hours = candidate_hours(cadence)
    if now.hour not in hours:
        # This firing's hour is not a scheduled slot at all (a clock skew that
        # crossed the hour, or a hand-run at an off-schedule time) — do not act.
        return False
    return now.hour == chosen_hour(now.date().isoformat(), hours)
