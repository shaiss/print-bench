"""Marker parsing — the `extract` half.

The convention is one HTML comment per DECIDED recommendation, placed in the
research doc whose section is the recommendation's provenance:

    <!-- brief-candidate: <slug> | <title> | source=<doc>#<anchor> | status=<status> [ref=<n>] -->

The marker **records a decision that doc already made** (a demonstrator a human
decision names, or a spike conclusion marked build-it); the convention never
invents candidates. `status=briefed ref=<n>` marks one already filed as a
design-brief issue, and never selects again.

Parsing is fail-loud in the house style (`tools/ci-gates`' registry parser,
`tools/backlog-groomer`'s conf parser): a marker with the prefix but wrong
fields raises `MarkerError` naming file and line, because a silently-skipped
marker is a decided recommendation nobody acts on — the exact quiet failure
this tool exists to prevent. Non-marker comments parse as nothing and never
raise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# The marker prefix, anchored so ordinary prose quoting the convention at
# length still only matches a real `brief-candidate:` comment opener.
_MARKER_RE = re.compile(r"<!--\s*brief-candidate:\s*(?P<body>.*?)\s*-->")

# A fenced code block (``` or ~~~) and an inline code span (`…`) both
# *display* markup rather than execute it — a doc explaining the convention
# shows markers there, and those are documentation, not decisions. Skipping
# them is what lets a doc quote the convention without extract reading the
# quote as a candidate.
_FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
_INLINE_CODE_RE = re.compile(r"`[^`]+`")

# Field shapes. The slug shares the HITL decision-id grammar (issue #161):
# kebab-case, so a candidate is addressable the same way a parked decision is.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SOURCE_RE = re.compile(r"^(?P<doc>\S+#\S+)$")

#: `status=` values the convention defines. `decided` is the un-filed default;
#: `briefed` is already a design-brief issue and carries `ref=<n>`.
STATUSES = ("decided", "briefed")


class MarkerError(ValueError):
    """A malformed brief-candidate marker — raised, never skipped."""


@dataclass(frozen=True)
class Candidate:
    """One decided recommendation, with the provenance #245 requires.

    `doc` is the containing file path relative to the extract root (always
    where the marker physically lives), `anchor` the section anchor inside it;
    together they are the `source=` field verbatim. `order` is the position in
    the scan (sorted doc path, then line order within a doc) — the
    oldest-undone-first ordering `select` consumes.
    """

    slug: str
    title: str
    doc: str
    anchor: str
    status: str
    ref: int | None
    order: int

    @property
    def source(self) -> str:
        return f"{self.doc}#{self.anchor}"

    def as_dict(self) -> dict:
        out = {
            "slug": self.slug,
            "title": self.title,
            "source": self.source,
            "status": self.status,
        }
        if self.ref is not None:
            out["ref"] = self.ref
        return out


def parse_marker(body: str, *, where: str = "<marker>") -> dict:
    """Parse one marker body (the text between `brief-candidate:` and `-->`).

    Returns the fields: slug, title, doc, anchor, status, ref. Raises
    `MarkerError` on any malformation, `where` naming the file:line for the
    message. Field order after the positional slug and title is free; within
    a field, whitespace-separated `key=value` tokens each count (the
    canonical shape carries the ref beside the status:
    ``status=briefed ref=385``). Unknown keys raise rather than being
    dropped — an unrecognized field is a convention change nobody updated
    the parser for.
    """
    parts = [p.strip() for p in body.split("|")]
    if len(parts) < 4:
        raise MarkerError(
            f"{where}: expected 'slug | title | source=<doc>#<anchor> | "
            f"status=<status> [ref=<n>]' (4+ pipe-separated fields), got {body!r}"
        )
    slug, title, kv = parts[0], parts[1], parts[2:]
    if not _SLUG_RE.match(slug):
        raise MarkerError(f"{where}: slug {slug!r} is not kebab-case [a-z0-9][a-z0-9-]*")
    if not title:
        raise MarkerError(f"{where}: empty title")

    fields: dict[str, str] = {}
    for part in kv:
        for token in part.split():
            key, sep, value = token.partition("=")
            if not sep:
                raise MarkerError(f"{where}: field {token!r} is not key=value")
            if key in fields:
                raise MarkerError(f"{where}: duplicate field {key!r}")
            if key not in ("source", "status", "ref"):
                raise MarkerError(
                    f"{where}: unknown field {key!r} (known: source, status, ref)"
                )
            fields[key] = value

    if "source" not in fields:
        raise MarkerError(f"{where}: missing source=<doc>#<anchor>")
    m = _SOURCE_RE.match(fields["source"])
    if not m:
        raise MarkerError(
            f"{where}: source {fields['source']!r} is not <doc>#<anchor> "
            "(no spaces; the anchor has no leading '#')"
        )
    doc, anchor = fields["source"].split("#", 1)

    status = fields.get("status", "")
    if status not in STATUSES:
        raise MarkerError(f"{where}: status {status!r} is not one of {', '.join(STATUSES)}")

    ref_s = fields.get("ref")
    ref: int | None = None
    if status == "briefed":
        if ref_s is None:
            raise MarkerError(f"{where}: status=briefed requires ref=<issue number>")
        if not ref_s.isdigit():
            raise MarkerError(f"{where}: ref {ref_s!r} is not an issue number")
        ref = int(ref_s)
    elif ref_s is not None:
        raise MarkerError(f"{where}: ref= is only valid with status=briefed (status is {status!r})")

    return {"slug": slug, "title": title, "doc": doc, "anchor": anchor, "status": status, "ref": ref}


def extract(root: Path) -> list[Candidate]:
    """Scan ``<root>/docs/*.md`` (top level, sorted) and parse every marker.

    Candidates come back in scan order — sorted doc path, then line order
    within a doc — which is exactly the oldest-undone-first order `select`
    consumes. Doc order is *sorted path order*, deliberately not git mtime:
    commit timestamps are not stable across clones, and a selector whose
    ordering depends on them could pick differently on two machines from
    byte-identical trees.

    A marker whose `source=` doc disagrees with the file it physically sits in
    raises: that is a marker copy-pasted between docs still claiming the other
    doc's section as provenance.
    """
    docs_dir = root / "docs"
    if not docs_dir.is_dir():
        return []

    out: list[Candidate] = []
    order = 0
    for path in sorted(docs_dir.glob("*.md")):
        rel = f"docs/{path.name}"
        in_fence = False
        for lineno, raw in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _FENCE_RE.match(raw):
                in_fence = not in_fence
                continue
            if in_fence:
                continue  # displayed markup, not a decision
            line = _INLINE_CODE_RE.sub("", raw)
            m = _MARKER_RE.search(line)
            if not m:
                continue
            where = f"{rel}:{lineno}"
            fields = parse_marker(m.group("body"), where=where)
            if fields["doc"] != rel:
                raise MarkerError(
                    f"{where}: source names {fields['doc']!r} but the marker "
                    f"sits in {rel!r} — provenance must be the containing doc"
                )
            out.append(Candidate(order=order, **fields))
            order += 1
    return out
