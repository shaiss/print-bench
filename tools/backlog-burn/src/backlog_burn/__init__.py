"""backlog-burn: pick one unclaimed, autonomy-eligible issue for a scheduled
unattended /ship-issue run.

The policy lives in :mod:`backlog_burn.select` (pure, tested); the live
GitHub read lives in :mod:`backlog_burn.github` (thin I/O, stdlib only);
ship-outcome triage overlay lives in :mod:`backlog_burn.triage` (issue #897).
"""

from .select import DEFAULT_REQUIRED_LABEL, render_summary, select_issue
from .triage import classify_with_ship_outcomes

__all__ = [
    "select_issue",
    "render_summary",
    "DEFAULT_REQUIRED_LABEL",
    "classify_with_ship_outcomes",
]
