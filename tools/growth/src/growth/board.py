"""Growth approval-board Stage policy — a pure function of one queue item.

The growth desk (docs/growth.md) surfaces its queue on a GitHub Projects board
so a human can SEE where each queued post is and approve it at a glance. Which
board Stage a ``growth-queue`` issue belongs in is a deterministic function of
its open/closed state, its labels, and the two hidden marker comments Lark's
posting tool leaves — and that decision lives HERE, not in a workflow's jq or a
model's judgment. It is the sibling of :func:`growth.queue.drain_order`.

Unlike the autonomy roadmap board (docs/roadmap-board.md), whose Stage is
human-owned — a card a person drags, so its sync sets the Stage only when the
item is first added — the growth board's Stage is a pure LENS: it reflects the
issue's real state, so the sync always re-derives and re-sets it. The one human
write that changes flow is still applying the ``approved-to-post`` label, which
this policy reflects as the Approved stage. Dragging a card changes only the
board's own field, never the label Lark actually reads — see docs/growth.md.

The marker strings are defined here as the single source. ``growth_mcp.py``
(stdlib-only, importing nothing from this tree) carries its own copies, and
``tests/test_board.py`` pins the two together so a rename there can never
silently blind the board.
"""

from __future__ import annotations

# The board's Stage options, ordered as the pipeline reads left to right. Kept
# in lockstep with the `growth` board spec's STAGE_OPTIONS in
# scripts/gh-project.sh — tests/test_board.py reads that file and fails if the
# two disagree, so the Python policy and the bash provisioning recipe can never
# drift into naming different stages.
STAGE_QUEUED = "Queued"        # filed; Lark has not drafted a post yet
STAGE_DRAFTED = "Drafted"      # Lark posted its dry-run — awaiting a human's approval
STAGE_APPROVED = "Approved"    # a human applied approved-to-post — awaiting the next live sweep
STAGE_POSTED = "Posted"        # published, and the issue closed
STAGE_PARKED = "Parked"        # needs-decision — a human paused it
STAGE_ATTENTION = "Attention"  # a live-post claim stands but the issue never closed — a human must look

BOARD_STAGES = [
    STAGE_QUEUED,
    STAGE_DRAFTED,
    STAGE_APPROVED,
    STAGE_POSTED,
    STAGE_PARKED,
    STAGE_ATTENTION,
]
BOARD_STAGE_OPTIONS = ",".join(BOARD_STAGES)

QUEUE_LABEL = "growth-queue"
APPROVAL_LABEL = "approved-to-post"
NEEDS_DECISION_LABEL = "needs-decision"

# The two hidden marker comments Lark's posting tool writes on a queue issue.
# Single source of the strings; growth_mcp.py keeps its own literal copies (it
# imports nothing from here on purpose), and tests/test_board.py asserts the two
# agree so the board's marker detection can never drift from what Lark writes.
DRYRUN_MARKER = "<!-- growth-twitter:dry-run -->"
POSTED_MARKER = "<!-- growth-twitter:posted -->"


def _labels(item: dict) -> list[str]:
    """Label names off an item, accepting either bare strings or ``{name: ...}``
    dicts (the two shapes `gh issue list --json labels` and a hand-built
    snapshot produce) — the same normalization :mod:`growth.queue` uses."""
    out = []
    for lbl in item.get("labels") or []:
        out.append(lbl.get("name", "") if isinstance(lbl, dict) else str(lbl))
    return out


def _has_marker(item: dict, bool_key: str, marker: str) -> bool:
    """True when the item carries ``marker``. A caller may pre-scan and pass an
    explicit boolean (``bool_key``); otherwise the marker is looked up in the
    concatenated ``comments`` text. Keeping the marker strings on this side
    means the sync workflow passes raw comment text and never hardcodes a marker
    of its own — one tested place owns them."""
    if bool_key in item:
        return bool(item[bool_key])
    return marker in (item.get("comments") or "")


def stage_of(item: dict) -> str | None:
    """The board Stage for one ``growth-queue`` issue, or ``None`` to leave it
    OFF the board.

    ``item`` keys:
      * ``state`` — ``"open"`` / ``"closed"``
      * ``labels`` — a list of label names, or ``{name: ...}`` dicts
      * ``comments`` — the concatenated comment bodies (for marker detection);
        or, in place of it, explicit ``has_dryrun_marker`` /
        ``has_posted_marker`` booleans.

    ``None`` means a closed issue that was never posted — a human closed/rejected
    it, so it is not a live card. Every other item maps to exactly one Stage.
    """
    labels = _labels(item)
    closed = (item.get("state") or "").lower() == "closed"
    posted = _has_marker(item, "has_posted_marker", POSTED_MARKER)
    drafted = _has_marker(item, "has_dryrun_marker", DRYRUN_MARKER)

    # A live post writes the posted marker BEFORE the first tweet (claim-first
    # dedup) and closes the issue on success. Closed + claim = Posted; open +
    # claim = a claim that never resolved to a close — an in-flight or
    # mid-thread-failed post a human must check.
    if posted:
        return STAGE_POSTED if closed else STAGE_ATTENTION
    # Closed with no claim = a human closed/rejected the item; not a live card.
    if closed:
        return None
    # Open and unposted — surface the most-blocking state first. A parked item
    # is excluded from Lark's drain selector, so it never advances until a human
    # clears it; that takes precedence over an approval that can't act yet.
    if NEEDS_DECISION_LABEL in labels:
        return STAGE_PARKED
    if APPROVAL_LABEL in labels:
        return STAGE_APPROVED
    if drafted:
        return STAGE_DRAFTED
    return STAGE_QUEUED
