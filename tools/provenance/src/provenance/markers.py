"""Marker parsing — the HTML-comment markers agents and CI leave on PR and issue threads.

A marker is a full-line ``<!-- FAMILY key=value … -->`` (``digest.MARKER_LINE_RE``).
The digest keeps the last ten marker lines of every body plus the suffix chain
before the Claude Code footer; this module turns those strings into typed
markers and classifies them. Prose is never consulted.

**Our families** (:data:`KNOWN_FAMILIES`): ``JANE_SIGNOFF``/``DRIK_SIGNOFF``
(``sha= verdict= fuse=``), ``PM_TRIAGE`` (``design=<d>[,<d>…] sha=``),
``PM_TRIAGE_DONE`` / ``COACH_DONE`` (``sha=``), ``COACH_LOCK``,
``ORACLE_REVIEW``, ``AUTO_REVIEW_STAMP`` (``[sha=]``),
``printcheck-gate-report``, ``argus-diff-report`` and the routine markers
that never belong to a design thread (``provider-escalation:*``,
``reeve-greenlight``, ``andon-cord``, ``growth-twitter:*`` …) listed in
:data:`IGNORED_OWN_FAMILIES`, plus the settle SHIP-LOCK's
``design-run-ship-lock:v1`` (#864; the lock is read through its
``ship_lock`` lead, not its marker). A marker in a body authored by one of OUR
identities (``github-actions[bot]`` or the repo owner) whose family is in
neither set is counted as ``unknown.marker`` (``record.unknown.markers``),
never rendered. Third-party bots' markers (CodeRabbit ``*_start``/``*_end``,
``qodo:*``) are not ours and are not counted.

**The five marker eras** (:data:`ERAS`, each pinned by a fixture comment —
its digest only — in tests/test_markers.py with the trust tier the rules
give it):

=====  ===========================  =========================================================
era    since                        shape → best trust tier
=====  ===========================  =========================================================
M1     2026-08-01                   persona prose, NO marker → no review event (counted
                                    ``comment.unclassified``)
M2     2026-08-21 (PM_TRIAGE)       ``<!-- PM_TRIAGE design=… sha=… -->`` posted with ``gh``;
                                    footer variants → ``window`` at best
M3     2026-08-23 (DRIK) / 08-24    ``<!-- {JANE,DRIK}_SIGNOFF sha= verdict= fuse= -->``
       (JANE)                       anywhere in the body (often AFTER the footer, trailing
                                    newline) → ``window`` at best
M4     2026-10-04 (#790, #804)      the reviewer MCP assembles ``{body}\\n\\n{marker}\\n\\n{FOOTER}``
                                    server-side → ``verified`` for sign-offs
M5     2026-10-06 (#770, #820)      completion markers ``PM_TRIAGE_DONE``/``COACH_DONE``
                                    appended last; ``COACH_LOCK`` pair (#806) → ``verified``
                                    for triage and the coach lock
=====  ===========================  =========================================================

Eras are documentation and fixtures, not branches in the parser: one
attribute grammar parses every era; what differs is where the marker sits,
which is what ``trust.py`` judges. ``verdict=fail`` (an M3 spelling) parses
and is stored as ``fail``.

``parse_marker``, ``parse_signoff``, ``parse_pm_triage`` and ``completion_sha``
are implemented by the scaffold (the extractor, H3, calls them during the
parallel build); H2 owns the module, its era fixtures and the
unknown-family counting.

Owner: H2. Pure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .digest import MARKER_LINE_RE

_FAMILY_RE = re.compile(r"<!-- ?([A-Za-z][A-Za-z0-9_:-]{0,63})((?: [A-Za-z_]{1,24}=[A-Za-z0-9._,:/-]{1,128}){0,8}) ?-->")
_ATTR_RE = re.compile(r" ([A-Za-z_]{1,24})=([A-Za-z0-9._,:/-]{1,128})")
_SHA_RE = re.compile(r"[0-9a-f]{40}")
_DESIGN_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")

KNOWN_FAMILIES = frozenset({
    "JANE_SIGNOFF", "DRIK_SIGNOFF", "PM_TRIAGE", "PM_TRIAGE_DONE", "COACH_LOCK", "COACH_DONE",
    "ORACLE_REVIEW", "AUTO_REVIEW_STAMP", "printcheck-gate-report", "argus-diff-report",
})
IGNORED_OWN_FAMILIES_RE = r"(provider-escalation:[a-z-]+|reeve-greenlight|andon-cord|growth-twitter:[a-z-]+|growth-queue|backlog-groomer|reeve-report|chunked|wright:[a-z-]+|design-run-ship-lock:v[0-9]+)"
SIGNOFF_FAMILIES = ("JANE_SIGNOFF", "DRIK_SIGNOFF")
STICKY_FAMILIES = {"AUTO_REVIEW_STAMP": "sticky.auto_review_stamp",
                   "printcheck-gate-report": "sticky.printcheck_gate_report",
                   "argus-diff-report": "sticky.argus_diff_report"}


@dataclass(frozen=True)
class Marker:
    """One parsed marker: ``family``, ``attrs`` (ordered ``(key, value)`` pairs), ``raw`` line."""

    family: str
    attrs: tuple[tuple[str, str], ...]
    raw: str

    def get(self, key: str) -> Optional[str]:
        return next((v for k, v in self.attrs if k == key), None)


@dataclass(frozen=True)
class Era:
    """One marker era (documentation + fixture pointer)."""

    name: str
    since: str
    shape: str
    best_tier: str


ERAS: tuple[Era, ...] = (
    Era("M1", "2026-08-01", "persona prose, no marker", "none"),
    Era("M2", "2026-08-21", "PM_TRIAGE posted with gh", "window"),
    Era("M3", "2026-08-23", "SIGNOFF marker anywhere, gh-posted", "window"),
    Era("M4", "2026-10-04", "MCP-assembled marker + FOOTER suffix", "verified"),
    Era("M5", "2026-10-06", "completion markers PM_TRIAGE_DONE / COACH_DONE (+COACH_LOCK pair)", "verified"),
)


def parse_marker(line: str) -> Optional[Marker]:
    """Parse one full-line marker; ``None`` when ``line`` is not one (scaffold-implemented)."""
    raw = line.strip() if isinstance(line, str) else ""
    if MARKER_LINE_RE.fullmatch(raw) is None:
        return None
    m = _FAMILY_RE.fullmatch(raw)
    if m is None:
        return None
    return Marker(m.group(1), tuple(_ATTR_RE.findall(m.group(2))), raw)


def parse_signoff(marker: Marker) -> Optional[dict]:
    """``{family, sha, verdict, fuse}`` for a JANE/DRIK sign-off with a 40-hex sha, else ``None``.

    ``verdict`` is one of pass/block/fail (``fail`` is an M3 spelling); ``fuse``
    is none/acknowledged or ``None`` when absent (scaffold-implemented).
    """
    if marker.family not in SIGNOFF_FAMILIES:
        return None
    sha, verdict, fuse = marker.get("sha"), marker.get("verdict"), marker.get("fuse")
    if sha is None or not _SHA_RE.fullmatch(sha) or verdict not in ("pass", "block", "fail"):
        return None
    if fuse not in (None, "none", "acknowledged"):
        return None
    return {"family": marker.family, "fuse": fuse, "sha": sha, "verdict": verdict}


def parse_pm_triage(marker: Marker) -> Optional[dict]:
    """``{designs: [..], sha}`` for ``PM_TRIAGE`` (designs split on ``,``, each a design slug;
    sorted unique); ``None`` when the sha or a design is malformed (scaffold-implemented)."""
    if marker.family != "PM_TRIAGE":
        return None
    sha, designs = marker.get("sha"), marker.get("design")
    if sha is None or not _SHA_RE.fullmatch(sha) or not designs:
        return None
    names = designs.split(",")
    if not all(_DESIGN_RE.fullmatch(n) for n in names):
        return None
    return {"designs": sorted(set(names)), "sha": sha}


def completion_sha(marker: Marker) -> Optional[str]:
    """The sha of a ``PM_TRIAGE_DONE``/``COACH_DONE`` marker (scaffold-implemented)."""
    if marker.family not in ("PM_TRIAGE_DONE", "COACH_DONE"):
        return None
    sha = marker.get("sha")
    return sha if sha is not None and _SHA_RE.fullmatch(sha) else None


_IGNORED_OWN_RE = re.compile(IGNORED_OWN_FAMILIES_RE)
_TS_RE = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2})(?:T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)?")


def is_known_family(family: str) -> bool:
    """True for one of :data:`KNOWN_FAMILIES` or an ignored own family (full match)."""
    return family in KNOWN_FAMILIES or _IGNORED_OWN_RE.fullmatch(family) is not None


def unknown_families(author_login: Optional[str], owner_login: str, marker_lines: list[str]) -> list[str]:
    """Families to count as ``unknown.marker`` for one body (our identities only).

    Our identities are the Actions bot (``trust.is_actions_bot``) and the repo
    owner (case-insensitive); any other author's markers — CodeRabbit's
    ``*_start``/``*_end``, ``qodo:*`` — return ``[]``. One entry per unknown
    marker LINE, in body order (a family repeated in one body counts each
    time), so the caller's ``Counter`` is ``record.unknown.markers``.
    """
    from .trust import is_actions_bot  # bound lazily so trust may import this module

    login = author_login.strip().lower() if isinstance(author_login, str) else ""
    ours = is_actions_bot(author_login) or (bool(login) and login == (owner_login or "").strip().lower())
    if not ours:
        return []
    out = []
    for line in marker_lines:
        marker = parse_marker(line)
        if marker is not None and not is_known_family(marker.family):
            out.append(marker.family)
    return out


def era_of(created_at: str) -> str:
    """The era name for a timestamp (``M1``..``M5``) — documentation helper for fixtures.

    The last era whose ``since`` date is on or before the timestamp's UTC
    date; anything before M2 (including the 2026-07-31 bootstrap) is M1.
    A string that is neither a contract ``ts`` nor a ``date`` raises ValueError.
    """
    m = _TS_RE.fullmatch(created_at) if isinstance(created_at, str) else None
    if m is None:
        raise ValueError(f"era_of: not a UTC timestamp or date: {created_at!r}")
    day = m.group(1)
    name = ERAS[0].name
    for era in ERAS:
        if era.since <= day:
            name = era.name
    return name
