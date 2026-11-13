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
thread reply. Handles extracted as *required* must match
``^@[A-Za-z0-9_]{1,15}$`` (ASCII only — never emit full-width markers).

Posted-text gates (every return path, and every thread part the caller
posts):

* refuse any text containing full-width at-signs ``＠`` (U+FF20) or ``﹫``
  (U+FE6B) — X treats them as mentions, and we never emit them;
* NFKC-normalize, then count every mention-shaped token
  (``@`` / ``＠`` / ``﹫`` + handle chars of any length); refuse above
  :data:`MAX_REQUIRED_HANDLES`.

A drafted root may declare at most :data:`MAX_REQUIRED_HANDLES` valid
ASCII handles; more than that is refused. Live posting additionally
requires the issue body not to have been edited after ``approved-to-post``
and a trusted dry-run digest binding — see :mod:`growth.approval_guard`.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from .tweetlen import MAX_WEIGHT, tweet_weight

# Hard cap on @handles required from ## Message's first paragraph AND on
# mentions actually posted (root + each thread part). Above this the posting
# tool refuses — never silently truncates.
MAX_REQUIRED_HANDLES = 5

# Full-width at-signs X also treats as mention markers. Never emit these;
# count them (via NFKC → `@`) toward the posted-mention cap.
FULLWIDTH_AT = ("\uff20", "\ufe6b")  # ＠  ﹫

HANDLE_RE = re.compile(r"^@[A-Za-z0-9_]{1,15}$")
# Token scan for *required* ASCII handles (URL-excluded). Full-width markers
# are NOT promoted into required handles — they only feed the posted cap /
# refuse gates.
_HANDLE_SCAN_RE = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{1,15}(?![A-Za-z0-9_])")
# Posted-mention count: any of the three markers + handle chars of ANY length.
_POSTED_MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9_])[@\uff20\ufe6b][A-Za-z0-9_]+"
)
# Same URL shape tweetlen meters — handles inside a URL must not count as
# mentions (e.g. ``https://www.youtube.com/@CNC_Kitchen``). Case-insensitive
# so ``HTTPS://`` / ``HtTp://`` cannot bypass the allowlist or URL-@ skip.
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
# Optional CR so GitHub's CRLF bodies still match the heading.
# Accept h2 (``##``, MCP / template filings) and h3 (``###``, GitHub
# issue-form field labels) — both are the same section in practice.
_MESSAGE_HEADING_RE = re.compile(
    r"^#{2,3}[ \t]+Message[ \t]*\r?$", re.IGNORECASE | re.MULTILINE
)
_LINK_HEADING_RE = re.compile(
    r"^#{2,3}[ \t]+Link[ \t]*\r?$", re.IGNORECASE | re.MULTILINE
)
_NEXT_HEADING_RE = re.compile(r"^#{2,3}[ \t]+\S", re.MULTILINE)

# Dry-run / live digest: sha256 of NFKC(## Message first paragraph) + '\n' +
# NFKC(## Link value) (empty string when Link is absent). The writer emits
# exactly ``{DRYRUN_MARKER}\n{digest_line}\n...`` with the marker at column 0;
# :func:`parse_message_digest` trusts only that prefix (issue #1021). Leading
# whitespace, quoted / mid-body / fenced copies, a digest not immediately
# after the marker, and the old marker-only format are never trusted.
DRYRUN_MARKER = "<!-- growth-twitter:dry-run -->"
DIGEST_PREFIX = "<!-- growth-twitter:message-digest:sha256="
DIGEST_LINE_RE = re.compile(
    r"^<!-- growth-twitter:message-digest:sha256=([0-9a-f]{64}) -->$"
)


class RootTagsError(ValueError):
    """Required handles over cap, unsafe full-width markers, or cannot fit
    every @handle within 280 weight."""


def _section_first_paragraph(body: str | None, heading_re: re.Pattern[str]) -> str:
    """First non-empty paragraph under *heading_re*, or ``\"\"``.

    Stops at a blank line or the next ``##``/``###`` heading. Leading /
    trailing whitespace on the paragraph is stripped; soft-wrapped lines
    inside one paragraph join with a single space.
    """
    if not body:
        return ""
    m = heading_re.search(body)
    if not m:
        return ""
    rest = body[m.end() :]
    next_h = _NEXT_HEADING_RE.search(rest)
    if next_h:
        rest = rest[: next_h.start()]
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


def message_root_paragraph(body: str | None) -> str:
    """The first non-empty paragraph under ``## Message``, or ``\"\"``."""
    return _section_first_paragraph(body, _MESSAGE_HEADING_RE)


def message_link_value(body: str | None) -> str:
    """The first non-empty paragraph under ``## Link``, or ``\"\"``.

    This is the queue item's one canonical URL (may be empty). Bound into
    the message-digest alongside the ``## Message`` first paragraph.
    """
    return _section_first_paragraph(body, _LINK_HEADING_RE)


def message_digest(body: str | None) -> str:
    """sha256 hex of NFKC(``## Message`` first para) + ``\\n`` + NFKC(``## Link``).

    Dry-run / preview comments record this; live posts re-check it — binding
    approval to the drafted root text **and** the queue Link. An empty Link
    still contributes the trailing newline + empty string so the format is
    stable. Live copy may be recomposed under the length, tag, and URL
    gates; only URLs from the bound paragraph and Link may appear.
    """
    para = unicodedata.normalize("NFKC", message_root_paragraph(body))
    link = unicodedata.normalize("NFKC", message_link_value(body))
    return hashlib.sha256((para + "\n" + link).encode("utf-8")).hexdigest()


def digest_comment_line(body: str | None) -> str:
    """The HTML comment line to embed in a dry-run outcome comment."""
    return f"{DIGEST_PREFIX}{message_digest(body)} -->"


def parse_message_digest(comment_body: str | None) -> str | None:
    """sha256 from a preview whose body *begins* with marker + digest line.

    The dry-run / preview writer emits exactly::

        {DRYRUN_MARKER}\\n{digest_line}\\n...

    with the marker at column 0 (no leading whitespace). Trust requires that
    same prefix: :meth:`str.startswith` ``DRYRUN_MARKER + \"\\n\"``, then a
    line matching :data:`DIGEST_LINE_RE` exactly. Newlines are normalized
    (CRLF → LF) but the body is **not** stripped — leading whitespace is a
    deliberate reject (issue #1021). Quoted / mid-body / fenced copies of
    the marker, a digest line that is not immediately after the marker, and
    the old marker-only format all return ``None``.
    """
    if not comment_body:
        return None
    text = comment_body.replace("\r\n", "\n").replace("\r", "\n")
    prefix = DRYRUN_MARKER + "\n"
    if not text.startswith(prefix):
        return None
    line2, _sep, _tail = text[len(prefix) :].partition("\n")
    m = DIGEST_LINE_RE.fullmatch(line2)
    return m.group(1) if m else None


def assert_thread_mention_cap(root: str, thread: list[str] | None = None) -> None:
    """Refuse when root + all thread parts together exceed the mention cap.

    Full-width markers are still refused per-part via :func:`assert_postable_text`.
    """
    parts = [root or ""] + list(thread or [])
    total = sum(count_posted_mentions(p) for p in parts)
    if total > MAX_REQUIRED_HANDLES:
        raise RootTagsError(
            f"thread carries {total} mention(s) across root+replies "
            f"(cap {MAX_REQUIRED_HANDLES}); refusing"
        )


def _url_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _URL_RE.finditer(text)]


def _in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    for lo, hi in spans:
        if lo <= pos < hi:
            return True
    return False


def extract_handles(text: str | None) -> list[str]:
    """Valid ASCII ``@handles`` in *text*, draft order, first-seen casing,
    deduped case-insensitively. Invalid tokens and URL-path ``@`` are
    dropped — never promoted. Full-width markers are never returned."""
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


def allowed_urls(body: str | None) -> frozenset[str]:
    """URLs the root/thread may carry: those in ``## Message`` para + ``## Link``."""
    return frozenset(
        extract_urls(message_root_paragraph(body))
        + extract_urls(message_link_value(body))
    )


def assert_only_allowed_urls(
    text: str | None,
    allowed: frozenset[str] | set[str] | list[str],
) -> str:
    """Refuse any ``http(s)://`` token in *text* not in *allowed*."""
    raw = text if text is not None else ""
    allow = frozenset(allowed)
    bad = [u for u in extract_urls(raw) if u not in allow]
    if bad:
        raise RootTagsError(
            f"postable text carries URL(s) not in the approved ## Message "
            f"first paragraph or ## Link: {bad} — refusing"
        )
    return raw


def count_posted_mentions(text: str | None) -> int:
    """Mention-shaped tokens after NFKC, counting ``@``/``＠``/``﹫`` + any
    length of ``[A-Za-z0-9_]``. URL-path ``@`` (e.g. YouTube ``/@user``) is
    skipped — X does not treat those as mentions. Used for the posted-text
    cap."""
    nfkc = unicodedata.normalize("NFKC", text or "")
    spans = _url_spans(nfkc)
    return sum(
        1
        for m in _POSTED_MENTION_RE.finditer(nfkc)
        if not _in_spans(m.start(), spans)
    )


def assert_postable_text(text: str | None) -> str:
    """Refuse full-width at-signs and over-cap mention counts on text that
    would be posted (root or thread part). Returns *text* unchanged on
    success (never rewrites markers into ASCII for emission)."""
    raw = text if text is not None else ""
    for ch in FULLWIDTH_AT:
        if ch in raw:
            raise RootTagsError(
                f"full-width at-sign (U+{ord(ch):04X}) in postable text — "
                f"refusing (never emit full-width mentions)"
            )
    n = count_posted_mentions(raw)
    if n > MAX_REQUIRED_HANDLES:
        raise RootTagsError(
            f"postable text carries {n} mention(s) "
            f"(cap {MAX_REQUIRED_HANDLES}); refusing"
        )
    return raw


def required_handles(body: str | None) -> list[str]:
    """Handles the root tweet must carry, from ``## Message``'s first paragraph.

    Raises :class:`RootTagsError` when the draft declares more than
    :data:`MAX_REQUIRED_HANDLES` valid ASCII handles (refuse, never truncate),
    or when the paragraph itself fails :func:`assert_postable_text` (e.g.
    full-width markers or NFKC mention count over the cap).
    """
    para = message_root_paragraph(body)
    # Posted-cap on the draft itself — catches ``@A1 ＠B1 …`` before restore.
    assert_postable_text(para)
    handles = extract_handles(para)
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
    link: str = "",
) -> str:
    """Return a root tweet that carries every *required* handle.

    *text* is the agent's composed root. *drafted* is ``## Message``'s first
    paragraph (may be empty). *link* is the ``## Link`` value (may be empty).
    On the drafted-restore path only the issue's ``## Link`` URL(s) are
    re-attached — never arbitrary URLs from the model composition. Every
    return path also refuses URLs outside ``drafted`` ∪ ``link`` via
    :func:`assert_only_allowed_urls`.

    Raises :class:`RootTagsError` when neither the drafted paragraph nor an
    append can fit every tag under :data:`MAX_WEIGHT`, when the chosen root
    fails :func:`assert_postable_text`, or when a disallowed URL is present.

    When *required* is empty the composed *text* is still run through the
    posted-mention and allowed-URL gates.
    """
    # Filter to the strict ASCII pattern only — never emit full-width handles.
    required = [h for h in required if HANDLE_RE.match(h)] if required else []
    allow = frozenset(extract_urls(drafted) + extract_urls(link))

    def _finish(candidate: str) -> str:
        return assert_only_allowed_urls(assert_postable_text(candidate), allow)

    if not required:
        return _finish(text)

    if not missing_handles(text, required):
        return _finish(text)

    drafted = (drafted or "").strip()
    if drafted and tweet_weight(drafted) <= MAX_WEIGHT:
        # Refuse drafted path when it carries full-width markers or too many
        # mentions — never publish it verbatim in that case.
        assert_postable_text(drafted)
        if not missing_handles(drafted, required):
            # Drafted path: re-attach ONLY the issue ## Link URL(s) the draft
            # lacks. Model-composed URLs are never appended (digest does not
            # cover them). If Link re-attach overflows 280, fall through to
            # append-on-composed — append may still fit.
            draft_urls = set(extract_urls(drafted))
            missing_link_urls = [
                u for u in extract_urls(link) if u not in draft_urls
            ]
            candidate = drafted
            use_drafted = True
            if missing_link_urls:
                url_suffix = " ".join(missing_link_urls)
                if candidate and not candidate[-1].isspace():
                    with_urls = f"{candidate.rstrip()} {url_suffix}"
                else:
                    with_urls = f"{candidate}{url_suffix}"
                if tweet_weight(with_urls) <= MAX_WEIGHT:
                    candidate = with_urls
                else:
                    use_drafted = False
            if use_drafted:
                return _finish(candidate)

    missing = missing_handles(text, required)
    if not missing:
        return _finish(text)
    suffix = " ".join(missing)
    if text and not text[-1].isspace():
        candidate = f"{text.rstrip()} {suffix}"
    else:
        candidate = f"{text}{suffix}" if text else suffix
    if tweet_weight(candidate) <= MAX_WEIGHT:
        return _finish(candidate)

    raise RootTagsError(
        f"root tweet is missing required handle(s) {missing} and neither the "
        f"drafted ## Message paragraph nor appending them fits within "
        f"{MAX_WEIGHT} weighted characters — refusing untagged post"
    )
