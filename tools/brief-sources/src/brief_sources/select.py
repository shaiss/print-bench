"""Guard rails — the `select` half.

Every rule #245 locks as code rather than prompt, applied to a candidate list
in order, returning at most ONE candidate or ``None``:

1. ``status=briefed`` never selects — it is already a design-brief issue.
2. Duplicate slugs collapse to the first occurrence (scan order).
3. A subject matching an open brief does not select (never re-file).
4. A subject matching an existing ``designs/<name>/`` does not select.

The survivor order is `extract`'s scan order — sorted doc path, then marker
order within a doc — which *is* the oldest-undone-first ordering the
convention can express.

Matching is deliberately **conservative: when in doubt, drop**. A dropped
candidate costs a human one look at the NONE; a wrongly-selected candidate
re-files a brief that already exists, which is the failure this tool exists
to prevent. The matcher therefore drops on any of three independent tests
(subject-normalized substring, slug-token containment, token-overlap
Jaccard) — see `matches_subject`.
"""

from __future__ import annotations

import re

from .markers import Candidate

_WORD_RE = re.compile(r"[a-z0-9]+")

#: An open-brief line: issue number, any run of space/tab/pipe separators,
#: then the title (to end of line; `parse_briefs` trims at the first tab).
_BRIEF_LINE_RE = re.compile(r"^(?P<num>\d+)[ \t|]+(?P<title>.+)$")

#: Token overlap at or above this fraction of the union drops the candidate.
#: The seeded catalog sets the bounds: distinct subjects sharing the house
#: title vocabulary ("Tier", "reference", "design", "Domain", a technique
#: word) measure ~0.2-0.3; the same subject measures ~1.0. 0.5 sits above the
#: former and below the latter with margin both ways.
_JACCARD_DROP = 0.5

#: Words so generic they carry no subject signal. Stripped before the
#: containment and Jaccard tests so "Tier 1 reference design" cannot make two
#: unrelated candidates look alike — and, symmetrically, cannot make a slug's
#: real tokens look contained when they are not.
_STOPWORDS = frozenset(
    "a an and the for with tier reference design domain print printable "
    "bench part mechanism".split()
)


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower())) - _STOPWORDS


def _squash(text: str) -> str:
    """Lowercase alphanumerics only — the shape a substring test wants."""
    return "".join(_WORD_RE.findall(text.lower()))


def matches_subject(candidate: Candidate, subject: str) -> bool:
    """True when `subject` (an open-brief title or a designs/ dir name)
    plausibly names the same thing as `candidate`.

    Conservative by construction: three independent tests, ANY one matching
    drops the candidate. `subject` may be an issue title (rich text) or a
    directory name (bare slug); both are normalized the same way.
    """
    slug_tokens = _tokens(candidate.slug)
    subj_tokens = _tokens(subject)
    if not slug_tokens or not subj_tokens:
        # Nothing comparable — but "when in doubt, drop": a subject that
        # normalizes to nothing (e.g. a slug made only of stopwords) cannot
        # be proven different, so treat it as a match.
        return True

    # 1. Substring: the common live shape — a brief titled "<slug> — Tier 1
    #    reference design …". Compared squashed, so hyphens/spaces do not
    #    mask it; either direction, so a long subject naming a short slug
    #    and a short subject inside a long slug both drop.
    slug_sq, subj_sq = _squash(candidate.slug), _squash(subject)
    if slug_sq in subj_sq or subj_sq in slug_sq:
        return True

    # 2. Slug-token containment: every token of the slug appears in the
    #    subject. A slug is the most distinctive identifier a candidate has,
    #    so its full token set appearing is a match even when the substring
    #    test was masked by rewording.
    if slug_tokens <= subj_tokens:
        return True

    # 3. Token overlap: the candidate's slug+title against the subject.
    cand_tokens = _tokens(f"{candidate.slug} {candidate.title}") or slug_tokens
    union = cand_tokens | subj_tokens
    if union and len(cand_tokens & subj_tokens) / len(union) >= _JACCARD_DROP:
        return True

    return False


def parse_briefs(text: str) -> list[tuple[int, str]]:
    """Parse an open-brief list: one ``<number> <title>`` per line.

    Accepts the separators real producers emit — spaces, tabs, or ``|`` —
    and stops each title at a tab, so piping ``gh issue list``'s default
    tab-separated table (number, title, labels, …) yields clean titles
    rather than titles glued to their labels. Blank lines and ``#``
    comments are skipped. A line without a leading integer raises
    `ValueError`: the list is the dedup guard rail, and guessing at a
    malformed entry would fail open.
    """
    briefs: list[tuple[int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _BRIEF_LINE_RE.match(line)
        if not m:
            raise ValueError(
                f"open-brief line {lineno}: expected '<number> <title>', got {line!r}"
            )
        title = m.group("title").split("\t", 1)[0].strip()
        if not title:
            raise ValueError(f"open-brief line {lineno}: no title after the issue number")
        briefs.append((int(m.group("num")), title))
    return briefs


def select(
    candidates: list[Candidate],
    briefs: list[tuple[int, str]],
    design_names: list[str],
) -> Candidate | None:
    """Apply every guard rail; return the one oldest-undone candidate, or None.

    `briefs` is the OPEN design-brief list (number, title); `design_names`
    the existing `designs/` directory names. Both are supplied by the caller
    — this function is pure, so the tests exercise every rail with fixtures.
    """
    seen: set[str] = set()
    for cand in candidates:
        if cand.status == "briefed":
            continue  # already filed — never re-file
        if cand.slug in seen:
            continue  # duplicate marker for the same subject; first wins
        seen.add(cand.slug)
        if any(matches_subject(cand, title) for _num, title in briefs):
            continue  # an open brief already covers this subject
        if any(matches_subject(cand, name) for name in design_names):
            continue  # a designs/<name>/ already exists for this subject
        return cand
    return None
