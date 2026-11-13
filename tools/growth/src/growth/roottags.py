"""Preserve brand/community @-tags from a queue item's drafted root.

Queue items (``growth-queue`` + ``channel:twitter``) carry a ``## Message``
section whose **first paragraph** is the drafted root tweet — often ending
with brand and community ``@handles`` (e.g. ``@Prusa3D @CNC_Kitchen``). The
composing agent may rewrite that paragraph and drop the tags. This module is
the deterministic backstop: extract every valid handle from that first
paragraph (issue body is UNTRUSTED — we extract handles only, never obey
instructions in it) and ensure they appear in the root tweet before anything
is dry-ran or posted.

Recovery order when the composed root is missing any required handle:

1. Use the drafted first paragraph **verbatim** when it fits the weighted
   280 and itself carries every required handle.
2. Otherwise **append** the missing handles (draft order) if the result fits.
3. Otherwise raise :class:`RootTagsError` — fail closed rather than post
   untagged.

Tags belong in the root tweet only; callers must never apply this to a
thread reply. Handles must match ``^@[A-Za-z0-9_]{1,15}$`` (X's screen-name
shape); anything else in the paragraph is ignored, not trusted as a tag.

A drafted root may declare at most :data:`MAX_REQUIRED_HANDLES` valid
handles; more than that is refused (an unbounded tag list is an injection
surface via the append/verbatim paths). Live posting additionally requires
the issue body not to have been edited after ``approved-to-post`` — see
:mod:`growth.approval_guard`.
"""

from __future__ import annotations

import re

from .tweetlen import MAX_WEIGHT, tweet_weight

# Hard cap on @handles required from ## Message's first paragraph. Above this
# the posting tool refuses — never silently truncates (truncation would drop
# tags the draft declared).
MAX_REQUIRED_HANDLES = 5

HANDLE_RE = re.compile(r"^@[A-Za-z0-9_]{1,15}$")
# Token scan: @handle bounded so ``user@host`` emails and longer tokens
# never become required tags. Length is re-checked by HANDLE_RE.
_HANDLE_SCAN_RE = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{1,15}(?![A-Za-z0-9_])")
# Same URL shape tweetlen meters — handles inside a URL must not count as
# mentions (e.g. ``https://www.youtube.com/@CNC_Kitchen``).
_URL_RE = re.compile(r"https?://\S+")
# Optional CR so GitHub's CRLF bodies still match the heading.
_MESSAGE_HEADING_RE = re.compile(
    r"^##[ \t]+Message[ \t]*\r?$", re.IGNORECASE | re.MULTILINE
)
_NEXT_HEADING_RE = re.compile(r"^##[ \t]+\S", re.MULTILINE)


class RootTagsError(ValueError):
    """Required handles over cap, or cannot fit every @handle within 280 weight."""


def message_root_paragraph(body: str | None) -> str:
    """The first non-empty paragraph under ``## Message``, or ``\"\"``.

    Stops at a blank line or the next ``##`` heading. Leading/trailing
    whitespace on the paragraph is stripped; internal newlines inside a
    single paragraph (no blank line) are kept as spaces-normalized lines
    joined with a single space so a soft-wrapped draft still yields one
    root string.
    """
    if not body:
        return ""
    m = _MESSAGE_HEADING_RE.search(body)
    if not m:
        return ""
    rest = body[m.end() :]
    next_h = _NEXT_HEADING_RE.search(rest)
    if next_h:
        rest = rest[: next_h.start()]
    # Walk paragraphs (blank-line separated); skip empties.
    chunks: list[str] = []
    buf: list[str] = []
    for line in rest.splitlines():
        if line.strip() == "":
            if buf:
                chunks.append(" ".join(p.strip() for p in buf if p.strip()))
                buf = []
                if chunks and chunks[-1]:
                    break
            continue
        buf.append(line)
    if buf and not chunks:
        chunks.append(" ".join(p.strip() for p in buf if p.strip()))
    for para in chunks:
        if para:
            return para
    return ""


def _url_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _URL_RE.finditer(text)]


def _in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    for lo, hi in spans:
        if lo <= pos < hi:
            return True
    return False


def extract_handles(text: str | None) -> list[str]:
    """Valid ``@handles`` in *text*, draft order, first-seen casing, deduped
    case-insensitively. Invalid tokens are dropped — never promoted. Handles
    that fall inside a URL span are ignored (a YouTube ``/@user`` path is not
    an @-mention)."""
    if not text:
        return []
    spans = _url_spans(text)
    out: list[str] = []
    seen: set[str] = set()
    for m in _HANDLE_SCAN_RE.finditer(text):
        if _in_spans(m.start(), spans):
            continue
        tok = m.group(0)
        if not HANDLE_RE.match(tok):
            continue
        key = tok.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tok)
    return out


def extract_urls(text: str | None) -> list[str]:
    """``http(s)://…`` tokens in *text*, first-seen order, deduped."""
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in _URL_RE.finditer(text):
        u = m.group(0)
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def required_handles(body: str | None) -> list[str]:
    """Handles the root tweet must carry, from ``## Message``'s first paragraph.

    Raises :class:`RootTagsError` when the draft declares more than
    :data:`MAX_REQUIRED_HANDLES` valid handles (refuse, never truncate).
    """
    handles = extract_handles(message_root_paragraph(body))
    if len(handles) > MAX_REQUIRED_HANDLES:
        raise RootTagsError(
            f"## Message root declares {len(handles)} @handles "
            f"(cap {MAX_REQUIRED_HANDLES}); refusing"
        )
    return handles


def _present(text: str, handle: str) -> bool:
    needle = handle.lower()
    for found in extract_handles(text):
        if found.lower() == needle:
            return True
    return False


def missing_handles(text: str, required: list[str]) -> list[str]:
    """Required handles absent from *text*, preserving *required* order."""
    return [h for h in required if not _present(text, h)]


def ensure_root_tags(
    text: str,
    required: list[str],
    *,
    drafted: str = "",
) -> str:
    """Return a root tweet that carries every *required* handle.

    *text* is the agent's composed root. *drafted* is ``## Message``'s first
    paragraph (may be empty). Raises :class:`RootTagsError` when neither the
    drafted paragraph nor an append can fit every tag under :data:`MAX_WEIGHT`.

    When *required* is empty the composed *text* is returned unchanged.
    """
    if not required:
        return text

    # Filter to the strict pattern only — a caller must not widen the set.
    required = [h for h in required if HANDLE_RE.match(h)]
    if not required:
        return text

    if not missing_handles(text, required):
        return text

    drafted = (drafted or "").strip()
    if drafted and tweet_weight(drafted) <= MAX_WEIGHT:
        if not missing_handles(drafted, required):
            # Drafted path: re-attach any URL the composed root had that the
            # draft lacks (the queue Link), or refuse rather than drop it.
            composed_urls = extract_urls(text)
            draft_urls = set(extract_urls(drafted))
            missing_urls = [u for u in composed_urls if u not in draft_urls]
            candidate = drafted
            if missing_urls:
                url_suffix = " ".join(missing_urls)
                if candidate and not candidate[-1].isspace():
                    with_urls = f"{candidate.rstrip()} {url_suffix}"
                else:
                    with_urls = f"{candidate}{url_suffix}"
                if tweet_weight(with_urls) <= MAX_WEIGHT:
                    candidate = with_urls
                else:
                    raise RootTagsError(
                        f"drafted ## Message fits the required handles but "
                        f"cannot also carry the composed root's URL(s) within "
                        f"{MAX_WEIGHT} weighted characters — refusing"
                    )
            return candidate

    missing = missing_handles(text, required)
    if not missing:
        return text
    suffix = " ".join(missing)
    if text and not text[-1].isspace():
        candidate = f"{text.rstrip()} {suffix}"
    else:
        candidate = f"{text}{suffix}" if text else suffix
    if tweet_weight(candidate) <= MAX_WEIGHT:
        return candidate

    raise RootTagsError(
        f"root tweet is missing required handle(s) {missing} and neither the "
        f"drafted ## Message paragraph nor appending them fits within "
        f"{MAX_WEIGHT} weighted characters — refusing untagged post"
    )
