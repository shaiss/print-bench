"""Shared guard for agent-posted issue comment bodies (Cipher, #864).

Used by adoption-assessor and reeve-signoff MCP servers (and any sibling that
posts free-text as github-actions[bot]). A body that smuggles the settle
SHIP-LOCK HTML marker — even mid-comment — would otherwise authenticate as
an active lock. Normalize then reject: NFKC, strip Cf (incl. zero-width),
collapse whitespace per line; refuse ``<!--`` / ``-->`` and any line matching
``/ship[\\s_-]*lock/i``.
"""

from __future__ import annotations

import re
import unicodedata

_SHIP_LOCK_LINE = re.compile(r"ship[\s_-]*lock", re.I)
_WS = re.compile(r"\s+")


def normalize_comment_body(text: str) -> str:
    """NFKC, strip Cf, collapse whitespace per line. Raises on failure."""
    if text is None:
        raise ValueError("comment body is None")
    folded = unicodedata.normalize("NFKC", text)
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")
    lines = [_WS.sub(" ", line.strip()) for line in folded.splitlines()]
    return "\n".join(lines)


def comment_body_reject_reason(text: str) -> str | None:
    """Return a short reject reason, or ``None`` when the body is allowed.

    Fail closed: a normalizer error is itself a rejection reason.
    """
    try:
        normalized = normalize_comment_body(text or "")
    except Exception as exc:  # noqa: BLE001 — fail closed
        return f"body normalizer failed: {exc}"
    raw = text or ""
    if "<!--" in raw or "-->" in raw:
        return "contains an HTML comment marker"
    if "<!--" in normalized or "-->" in normalized:
        return "contains an HTML comment marker after normalization"
    for line in normalized.splitlines():
        if _SHIP_LOCK_LINE.search(line):
            return "matches ship-lock after normalization"
    return None
