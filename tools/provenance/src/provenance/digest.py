"""Body digests — what the evidence branch keeps instead of comment prose.

Prose is never stored (docs/provenance.md §Evidence digest; N5): deleted
content and pasted secrets would otherwise persist in git forever, and the
site renders structured fields only. Every free-text body the harvester
reads (issue and PR bodies, issue comments, reviews, review comments,
release notes) is replaced, at capture time and while the body is still in
memory, by a **body digest** (:func:`body_digest`); every commit message by a
**message digest** (:func:`message_digest`). The digest carries exactly what
the extractors need — markers, the trust suffix, triage verdict cells, one
classified lead line and a few validated fields — and nothing an extractor
could turn back into prose.

Because the body is gone after capture, a new lead class or a new marker
shape cannot be applied to frozen units by re-extraction; it needs a
``refreeze`` (comments and issues are not under Actions retention, so their
bodies can be re-read). Every digest therefore records :data:`DIGEST_VERSION`.

Body digest fields (contract ``body-digest@3``; an ``@1`` digest was computed
before the ``delivered`` alternative of ``shipped`` and the ``ship_lock_settle``
and ``contract`` classes existed, so its ``lead`` is ``null`` (or ``ship_lock``
for a settle stub) where a later version would classify differently, and an
``@2`` digest before the ``burn_cooldown`` class, so a cooldown's ``lead`` is
``null`` there):

``sha256``
    lower-hex SHA-256 of the body's UTF-8 bytes, exactly as the API returned
    it (a ``null`` body digests as ``""``).
``length``
    the body's UTF-8 byte length.
``head_marker``
    the body's first line, when that line — stripped — is a full-line
    marker (:data:`MARKER_LINE_RE`); else ``null``. The Oracle's trust rule
    reads it (its marker leads the post).
``marker_lines``
    the LAST ≤ :data:`MAX_MARKER_LINES` lines (kept in body order) that,
    stripped, fully match :data:`MARKER_LINE_RE`. A marker quoted inline in
    prose (``sticky `<!-- printcheck-gate-report -->` for…``) is not a
    full line and is not kept.
``footer_ok``
    the body ends with ``"\\n\\n" + FOOTER`` exactly (FOOTER is
    byte-identical to ``.claude/reviewer-post/reviewer_mcp.py``'s, pinned by
    a drift test).
``suffix_markers``
    the ≤ 3 markers chained immediately before that footer:
    ``body == <anything> + M1 + "\\n\\n" + M2 … + Mk + "\\n\\n" + FOOTER``,
    each ``Mi`` matching :data:`MARKER_TEXT_RE`, walked back from the end
    (:func:`suffix_markers`). Empty when ``footer_ok`` is false. This is the
    exact information ``scripts/reviewer-posted.sh`` (``endswith(marker +
    "\\n\\n" + FOOTER)``) and ``scripts/coach-lock-check.sh``
    (``COACH_LOCK\\n\\nCOACH_DONE\\n\\nFOOTER`` at end) test, so ``trust.py``
    reproduces both rules from the digest alone.
``suffix_ok``
    ``suffix_markers`` is non-empty and its last element fully matches one
    of the MCP completion shapes (:data:`MCP_COMPLETION_RE`): a
    ``JANE_SIGNOFF``/``DRIK_SIGNOFF`` with sha/verdict/fuse, a
    ``PM_TRIAGE_DONE sha=`` or a ``COACH_DONE sha=``. Author is NOT part of
    it — ``trust.py`` adds the author half.
``table_verdicts``
    for every GFM table whose header row has a cell equal (case-folded,
    emphasis stripped) to ``verdict``: one entry per data row, in body
    order — the sorted ``+``-joined set of verdict tokens found in that
    row's verdict cell (``act-now``, ``decline``, ``no-action``, ``queue``),
    or ``unknown`` when it holds none. Capped at :data:`MAX_TABLE_ROWS`.
``lead``
    the class of the body's lead line (the first non-blank line that is not a
    full-line marker) under :data:`LEAD_RULES`, or ``null``.
``lead_fields``
    validated fields the lead's class carries (``design_name``,
    ``shipped_pr``, ``death``, ``round``, ``round_sub``); ``{}`` otherwise. A
    ``ship_lock_withdrawn`` lead's ``death`` is true when the line starts with
    :data:`DEATH_PREFIX` — routine-lock-cleanup.sh's notice for a run that
    died, as opposed to an agent releasing its own claim. A
    ``shipped`` lead takes ``shipped_pr`` from the lead line (``✅ **SHIPPED …
    #N``, ``📦 **Draft PR opened: #N**``) or, for the delivery step's
    ``🚢 <routine> delivered — …`` line, from the body's ``- pull request:
    …/pull/<N>`` line (:data:`DELIVERED_PR_RE`); a ``0`` (``#0``, ``pull/00``)
    names no PR and is ``null``, as in ``refs_closes`` — the contract's ``min
    1`` would otherwise hold the unit back as contract-invalid.
``refs_closes``
    sorted unique issue numbers named by a GitHub closing keyword
    (``Closes #N`` …) anywhere in the body — only a PR body's are used.
    ``#0`` (or ``#00`` …) names no issue and is dropped: the contract's
    ``min 1`` means no contract-valid digest ever held a 0, so dropping it
    changes no stored value and needs no ``DIGEST_VERSION`` bump.
``digest``
    :data:`DIGEST_VERSION`.

Message digest fields (contract ``message-digest@1``): ``sha256``,
``length``, ``subject_regen`` (the subject line equals ``REGEN_SUBJECT``),
``subject_pr`` (a squash ``(#N)`` suffix or ``Merge pull request #N`` on
the subject line, else ``null``), ``trailers`` (allow-listed keys only, each
value charset-validated, in message order) and ``digest``.

Implemented in full by the scaffold (every builder's fixtures depend on
these bytes); H2 owns it from here. Pure: no I/O, no clock.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

#: Recorded in every digest; bump on ANY change to the rules below.
DIGEST_VERSION = "body-digest@3"
MESSAGE_DIGEST_VERSION = "message-digest@1"

#: Byte-identical to ``.claude/reviewer-post/reviewer_mcp.py`` FOOTER and to
#: the copies in scripts/reviewer-posted.sh and scripts/coach-lock-check.sh
#: (tests/test_trust.py drift-pins all three).
FOOTER = "---\n_Generated by [Claude Code](https://claude.ai/code)_"

#: Byte-identical to scripts/reviewer-signoff.sh REGEN_SUBJECT (drift-pinned
#: by tests/test_episodes.py).
REGEN_SUBJECT = "CI: regenerate previews and product pages"

MAX_MARKER_LINES = 10
MAX_SUFFIX_MARKERS = 3
MAX_TABLE_ROWS = 200
MAX_TRAILERS = 12
MAX_CLOSES = 20

_MARKER_BODY = (
    r"<!-- ?[A-Za-z][A-Za-z0-9_:-]{0,63}"
    r"(?: [A-Za-z_]{1,24}=[A-Za-z0-9._,:/-]{1,128}){0,8} ?-->"
)
#: A full-line marker (matched with ``fullmatch`` against the stripped line).
MARKER_LINE_RE = re.compile(_MARKER_BODY)
#: The same marker text, anchored at the END of a string (the suffix walk).
MARKER_TEXT_RE = re.compile(_MARKER_BODY + r"\Z")

#: The four MCP completion shapes, exact (``fullmatch``).
MCP_COMPLETION_RE = re.compile(
    r"<!-- (?:JANE|DRIK)_SIGNOFF sha=[0-9a-f]{40} verdict=(?:pass|block) "
    r"fuse=(?:none|acknowledged) -->"
    r"|<!-- PM_TRIAGE_DONE sha=[0-9a-f]{40} -->"
    r"|<!-- COACH_DONE sha=[0-9a-f]{40} -->"
)

_DESIGN_NAME_RE = re.compile(r"^\*\*Design name:\*\*\s*`?([a-z0-9][a-z0-9-]{0,63})`?\s*$", re.M)

#: The delivery step's success lead, byte-identical to the two ``DELIVERED_LINE``
#: assignments in scripts/design-run-deliver.sh (drift-pinned by tests/test_digest.py).
#: Posted by ``design-run-deliver.yml`` / ``backlog-burn-deliver.yml`` since #858; the
#: line carries no number, so the PR comes from the body's ``- pull request:`` line.
DELIVERED_LINES = (
    "🚢 design-run delivered — branch and draft PR verified",
    "🚢 backlog-burn delivered — branch and draft PR verified",
)
#: The settle job's constant SHIP-LOCK first line: ``STOP_LOCK_MARKER`` + `` — settle claim`` in
#: scripts/design-run-deliver.sh's ``SHIP_LOCK_SETTLE_BODY`` (drift-pinned by tests/test_digest.py).
#: Its own class because both the settle stub and the burn's /ship-issue lock carry the
#: ``design-run-ship-lock:v1`` marker, and only this line tells the stub apart.
SETTLE_LOCK_LINE = "🚢 SHIP-LOCK — settle claim"
#: scripts/routine-lock-cleanup.sh's ``DEATH_PREFIX`` (drift-pinned by tests/test_digest.py): the
#: first line of the withdrawal it posts for a run that died, after the run's agent steps. Every
#: other ``SHIP-LOCK WITHDRAWN`` is an agent releasing its own claim, edited or posted in its window.
DEATH_PREFIX = "🚢 SHIP-LOCK WITHDRAWN — scheduled run died"
#: scripts/routine-lock-cleanup.sh's ``COOLDOWN_MARKER`` (drift-pinned by tests/test_digest.py): the
#: first line of the picker cooldown it posts, since #924, for a run that neither delivered nor
#: declined — after the run's agent steps, like the dead-run notice it often follows.
COOLDOWN_LINE = "🚢 BURN-COOLDOWN"
#: The ``- pull request: <url>`` line ``post_success`` writes under the delivered lead.
DELIVERED_PR_RE = re.compile(
    r"^- pull request: https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+/pull/(?P<pr>[0-9]{1,7})$", re.M)

#: (class, compiled regex) — the first rule matching the stripped lead line
#: wins. Anchored at the start of the line. Extending this list is a
#: DIGEST_VERSION bump. ``contract`` is the unattended design run's §2 scope
#: contract, posted by the settle job as its own comment since #864 (the
#: settle SHIP-LOCK is a constant stub with no ``**Design name:**``).
#: ``burn_cooldown`` is the whole line, exactly (body-digest@3).
LEAD_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ship_lock_withdrawn", re.compile(r"^🚢 SHIP-LOCK WITHDRAWN\b")),
    ("ship_lock_settle", re.compile("^" + re.escape(SETTLE_LOCK_LINE) + "$")),
    ("ship_lock", re.compile(r"^🚢 SHIP-LOCK\b")),
    ("declined", re.compile(r"^🚢 DECLINED\b")),
    ("deferred", re.compile(r"^🚢 DEFERRED\b")),
    ("burn_cooldown", re.compile("^" + re.escape(COOLDOWN_LINE) + "$")),
    ("shipped", re.compile(r"^(?:✅ \*\*SHIPPED\b.*?#(?P<pr1>[0-9]{1,7})\b|📦 \*\*Draft PR opened: #(?P<pr2>[0-9]{1,7})\*\*"
                           r"|(?P<delivered>" + "|".join(map(re.escape, DELIVERED_LINES)) + r")$)")),
    ("decision_needed", re.compile(r"^🚦 DECISION NEEDED\b")),
    ("coach_lock", re.compile(r"^🎓 COACH-LOCK\b")),
    ("coach_round", re.compile(r"^Round (?P<round>[0-9]{1,3})(?P<sub>[a-z]?) — ")),
    ("bugbot_limit", re.compile(r"^<h[1-6]>Bugbot couldn't run - usage limit reached</h[1-6]>$")),
    ("qodo_paused", re.compile(r"^\*\*ⓘ Qodo reviews are paused\b")),
    ("clear_prs", re.compile(r"^\*\*/clear-prs sweep\b")),
    ("contract", re.compile(r"^\*\*Design name:\*\*")),
)
LEAD_CLASSES = tuple(name for name, _ in LEAD_RULES)

#: Lead classes that carry a ``design_name`` field when the body has one.
_DESIGN_NAME_LEADS = frozenset({"ship_lock", "ship_lock_withdrawn", "declined", "deferred", "shipped",
                                "contract"})

_CLOSES_RE = re.compile(
    r"(?i)\b(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved):?\s+#([0-9]{1,7})\b"
)

#: Verdict tokens recognised in a triage table's verdict cell.
VERDICT_TOKENS = ("act-now", "decline", "no-action", "queue")
_TOKEN_RES = (
    ("act-now", re.compile(r"act[- ]now")),
    ("decline", re.compile(r"\bdecline[ds]?\b")),
    ("no-action", re.compile(r"\bno[- ]action\b")),
    ("queue", re.compile(r"\bqueue[ds]?\b")),
)
_EMPHASIS_RE = re.compile(r"[*_`]")
_SEP_CELL_RE = re.compile(r":?-+:?")

#: Allow-listed commit trailers: canonical key -> value pattern (fullmatch).
TRAILER_RULES: dict[str, re.Pattern[str]] = {
    "Co-Authored-By": re.compile(
        r"[A-Za-z0-9 ._'()\[\]+-]{1,80} <[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,64}>"
    ),
    "Claude-Session": re.compile(r"https://claude\.ai/code/session_[A-Za-z0-9]{8,64}"),
    "Preview-Diff": re.compile(r"all-noise|content"),
}
_TRAILER_KEYS = {k.lower(): k for k in TRAILER_RULES}
_TRAILER_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z-]{0,40}):[ \t]+(.+?)[ \t]*$")
_SUBJECT_PR_RE = re.compile(r"\(#([0-9]{1,7})\)$|^Merge pull request #([0-9]{1,7})\b")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_marker_line(line: str) -> bool:
    """True when ``line``, stripped, is one full-line HTML-comment marker."""
    return MARKER_LINE_RE.fullmatch(line.strip()) is not None


def suffix_markers(body: str) -> list[str]:
    """The ≤3 markers chained immediately before ``"\\n\\n" + FOOTER`` at the end.

    Walk: require ``body.endswith("\\n\\n" + FOOTER)``; strip it; then while
    the remainder ends with a marker (:data:`MARKER_TEXT_RE`), take it, strip
    it, and continue only if the remainder then ends with ``"\\n\\n"``.
    """
    tail = "\n\n" + FOOTER
    if not body.endswith(tail):
        return []
    rest = body[: -len(tail)]
    out: list[str] = []
    while len(out) < MAX_SUFFIX_MARKERS:
        m = MARKER_TEXT_RE.search(rest)
        if not m:
            break
        out.insert(0, m.group(0))
        rest = rest[: m.start()]
        if not rest.endswith("\n\n"):
            break
        rest = rest[:-2]
    return out


def _table_cells(row: str) -> list[str]:
    """GFM row -> trimmed cells (``\\|`` is literal; outer empty cells dropped).

    The same splitting rule as site/lib/timeline.mjs ``tableCells``.
    """
    cells, cur, i = [], "", 0
    while i < len(row):
        ch = row[i]
        if ch == "\\" and i + 1 < len(row) and row[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "|":
            cells.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    cells.append(cur)
    cells = [c.strip() for c in cells]
    if cells and cells[0] == "":
        cells.pop(0)
    if cells and cells[-1] == "":
        cells.pop()
    return cells


def _norm_cell(cell: str) -> str:
    return _EMPHASIS_RE.sub("", cell).strip().lower()


def verdict_tokens(cell: str) -> str:
    """The sorted ``+``-joined verdict tokens of one cell, or ``"unknown"``."""
    text = _norm_cell(cell)
    found = sorted({tok for tok, rx in _TOKEN_RES if rx.search(text)})
    return "+".join(found) if found else "unknown"


def table_verdicts(body: str) -> list[str]:
    """One verdict-token string per data row of every table with a ``Verdict`` column."""
    lines = body.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines) and len(out) < MAX_TABLE_ROWS:
        line = lines[i].strip()
        if not line.startswith("|"):
            i += 1
            continue
        header = [_norm_cell(c) for c in _table_cells(line)]
        sep = lines[i + 1].strip() if i + 1 < len(lines) else ""
        sep_cells = _table_cells(sep) if sep.startswith("|") else []
        if not sep_cells or not all(_SEP_CELL_RE.fullmatch(c) for c in sep_cells):
            i += 1
            continue
        col = header.index("verdict") if "verdict" in header else -1
        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            if col >= 0 and len(out) < MAX_TABLE_ROWS:
                cells = _table_cells(lines[j].strip())
                out.append(verdict_tokens(cells[col]) if col < len(cells) else "unknown")
            j += 1
        i = j
    return out


def lead_line(body: str) -> Optional[str]:
    """The first non-blank line that is not a full-line marker, stripped; else ``None``."""
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped and not is_marker_line(stripped):
            return stripped
    return None


def classify_lead(body: str) -> tuple[Optional[str], dict[str, Any]]:
    """``(lead class, lead_fields)`` for ``body`` under :data:`LEAD_RULES`."""
    line = lead_line(body)
    if line is None:
        return None, {}
    for name, rx in LEAD_RULES:
        m = rx.match(line)
        if not m:
            continue
        fields: dict[str, Any] = {}
        if name == "shipped":
            pr = m.group("pr1") or m.group("pr2")
            if pr is None and m.group("delivered"):
                pm = DELIVERED_PR_RE.search(body)
                pr = pm.group("pr") if pm else None
            n = int(pr) if pr else 0
            fields["shipped_pr"] = n if n >= 1 else None
        if name == "ship_lock_withdrawn":
            fields["death"] = line.startswith(DEATH_PREFIX)
        if name == "coach_round":
            fields["round"] = int(m.group("round"))
            fields["round_sub"] = m.group("sub") or None
        if name in _DESIGN_NAME_LEADS:
            dm = _DESIGN_NAME_RE.search(body)
            fields["design_name"] = dm.group(1) if dm else None
        return name, fields
    return None, {}


def refs_closes(body: str) -> list[int]:
    """Sorted unique issue numbers ≥ 1 after a closing keyword (≤ :data:`MAX_CLOSES`)."""
    return sorted({int(n) for n in _CLOSES_RE.findall(body)} - {0})[:MAX_CLOSES]


def body_digest(body: Optional[str]) -> dict[str, Any]:
    """The ``body-digest@3`` object for ``body`` (``None`` digests as ``""``)."""
    text = body if isinstance(body, str) else ""
    lines = text.split("\n")
    first = lines[0].strip() if lines else ""
    markers = [ln.strip() for ln in lines if is_marker_line(ln)]
    suffix = suffix_markers(text)
    lead, lead_fields = classify_lead(text)
    return {
        "digest": DIGEST_VERSION,
        "footer_ok": text.endswith("\n\n" + FOOTER),
        "head_marker": first if first and is_marker_line(first) else None,
        "lead": lead,
        "lead_fields": lead_fields,
        "length": len(text.encode("utf-8")),
        "marker_lines": markers[-MAX_MARKER_LINES:],
        "refs_closes": refs_closes(text),
        "sha256": _sha256(text),
        "suffix_markers": suffix,
        "suffix_ok": bool(suffix) and MCP_COMPLETION_RE.fullmatch(suffix[-1]) is not None,
        "table_verdicts": table_verdicts(text),
    }


def parse_trailers(message: str) -> list[dict[str, str]]:
    """Allow-listed ``Key: value`` trailer lines, canonical key, in message order.

    Any line of the message may carry one (agents append trailers to the last
    paragraph, squash merges concatenate paragraphs). A value failing its
    key's pattern is dropped, never truncated.
    """
    out: list[dict[str, str]] = []
    for line in message.split("\n"):
        m = _TRAILER_LINE_RE.match(line.strip())
        if not m:
            continue
        key = _TRAILER_KEYS.get(m.group(1).lower())
        if key is None or not TRAILER_RULES[key].fullmatch(m.group(2)):
            continue
        out.append({"key": key, "value": m.group(2)})
        if len(out) >= MAX_TRAILERS:
            break
    return out


def message_digest(message: Optional[str]) -> dict[str, Any]:
    """The ``message-digest@1`` object for a commit message."""
    text = message if isinstance(message, str) else ""
    subject = text.split("\n", 1)[0].strip()
    m = _SUBJECT_PR_RE.search(subject)
    subject_pr = int(m.group(1) or m.group(2)) if m else None
    return {
        "digest": MESSAGE_DIGEST_VERSION,
        "length": len(text.encode("utf-8")),
        "sha256": _sha256(text),
        "subject_pr": subject_pr,
        "subject_regen": subject == REGEN_SUBJECT,
        "trailers": parse_trailers(text),
    }
