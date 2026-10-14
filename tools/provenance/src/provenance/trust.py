"""Trust tiers — an exact port of ``scripts/reviewer-posted.sh`` and ``scripts/coach-lock-check.sh``.

Computed from the DIGEST (``digest.body_digest``) plus the author login, so
a re-extraction years later reaches the same verdict without the body
(docs/provenance.md §Trust tiers). Tiers, strongest first:

``verified``
    exactly what the repo's own artifact checks accept:

    * a sign-off (``JANE_SIGNOFF``/``DRIK_SIGNOFF``): the author is the
      Actions bot (REST ``github-actions[bot]``, GraphQL ``github-actions``
      — :func:`is_actions_bot`, the reviewer-posted.sh normalisation) AND
      ``digest.suffix_ok`` AND ``suffix_markers[-1]`` is that sign-off
      (family, sha, verdict, fuse exact) — i.e. the body ENDS with
      ``marker + "\\n\\n" + FOOTER``; basis ``actions-bot+suffix``;
    * a PM triage: Actions bot AND ``suffix_markers[-1]`` is
      ``<!-- PM_TRIAGE_DONE sha=S -->`` with ``S`` the triage marker's sha;
    * a coach lock: Actions bot AND ``suffix_markers[-2:] ==
      ["<!-- COACH_LOCK -->", "<!-- COACH_DONE sha=S -->"]`` (coach-lock-check.sh's
      ``SUFFIX_RE``);
    * an Oracle review: Actions bot AND ``head_marker == "<!-- ORACLE_REVIEW -->"``
      AND ``footer_ok``; basis ``actions-bot+head-marker``;
    * a ``reviewer-signoff`` commit status created by the Actions bot whose
      ``target_url`` run id is an ``auto-review.yml`` receipt
      (``actions-status+receipt``); every receipt event (``receipt``).

    Verified inherits that rule's residuals (any session holding
    GITHUB_TOKEN can post as the Actions bot) — documented, not fixed here.
``window`` (assigned by ``serving.py``, not here)
    the rule fails, the author is a posting identity of the role, and
    exactly one agent-step window of that role contains the artifact.
``claimed``
    a marker or trailer is present but the rule fails: owner-token
    sign-offs (``marker:owner-token``), another author (``marker:other-author``,
    e.g. markers quoted by cursor[bot]), an Actions-bot post without the
    MCP suffix (``marker:no-suffix``), or a post EDITED
    ``>= edit_grace_seconds`` after creation (``marker:edited`` — an edit
    demotes even a verified suffix); commit trailers (``trailer``); an issue
    body with a non-null ``lastEditedAt``.
``login``
    only the authoring login is known (basis ``login``).
``ambiguous`` / ``none``
    no single attribution (set by ``serving.py`` / for unattributable rows).

:func:`served` is the parity surface: it runs over RAW comment JSON (the
shape reviewer-posted.sh reads, bodies included), digests each body and
answers exactly like ``reviewer-posted.sh check`` — tests/test_trust.py
replays every ``row`` of ``reviewer-posted.sh --selftest`` and every row of
``coach-lock-check.sh --selftest`` through it, and drift-pins
``digest.FOOTER`` against ``reviewer_mcp.FOOTER`` and both scripts'
``REVIEWER_FOOTER``/``COACH_FOOTER`` literals (a 1-byte change fails).

Owner: H2. Pure.
"""

from __future__ import annotations

from typing import Any, Optional

ACTIONS_BOT = "github-actions"
REVIEWER_FAMILIES = {"jane": "JANE_SIGNOFF", "drik": "DRIK_SIGNOFF",
                     "pm": "PM_TRIAGE_DONE", "coach": "COACH_DONE"}
COACH_LOCK_MARKER = "<!-- COACH_LOCK -->"
ORACLE_MARKER = "<!-- ORACLE_REVIEW -->"


def is_actions_bot(login: Optional[str]) -> bool:
    """REST ``github-actions[bot]`` or GraphQL ``github-actions`` (case-insensitive, stripped)."""
    raise NotImplementedError("builder H2")


def served(comments: list[dict[str, Any]], *, reviewer: str, sha: str,
           since: Optional[str] = None) -> bool:
    """reviewer-posted.sh ``check`` over raw comments (``jane|drik|pm|coach``); ValueError on a
    bad reviewer or sha, exactly like the script's refusals."""
    raise NotImplementedError("builder H2")


def coach_lock_served(comments: list[dict[str, Any]], *, since: Optional[str] = None) -> bool:
    """coach-lock-check.sh over raw comments."""
    raise NotImplementedError("builder H2")


def comment_tier(*, kind: str, login: Optional[str], owner_login: str, digest: dict[str, Any],
                 created_at: str, updated_at: Optional[str], edit_grace_seconds: int,
                 marker_sha: Optional[str] = None) -> tuple[str, str]:
    """``(tier, trust_basis)`` for a marker-bearing comment event — ``verified``/``claimed``/
    ``login``/``none`` (window is serving's)."""
    raise NotImplementedError("builder H2")


def status_tier(status: dict[str, Any], auto_review_run_ids: set[int]) -> tuple[str, str]:
    """``(tier, basis)`` for a ``reviewer-signoff`` status (raw-pr@1 status shape)."""
    raise NotImplementedError("builder H2")


def selftest_cases() -> list:
    """Offline negatives for ``selftest.run``: planted human/cursor markers, no footer, sibling
    plant, case-folded marker, stale sha, edited post, coach pair order."""
    raise NotImplementedError("builder H2")
