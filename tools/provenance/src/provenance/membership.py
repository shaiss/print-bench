"""PR × design membership — the audit's refined file-kind rule (P=1.00/R=1.00 tuned, 0.94/1.00 held-out).

Applied to ``/pulls/{n}/files`` for EVERY PR (all three merge methods are
enabled, so a first-parent diff of a rebase merge would see only its last
commit). Paths are taken relative to ``designs/<D>/``.

**File kinds** (:func:`file_kind`, first rule wins):

====================================================  ========
``previews/.regen-stamp``                             stamp
``previews/lifestyle-*.png|gif``,
``previews/product-still-*.png``                      ai
``*.md`` anywhere (incl. ``previews/CAMERAS.md``)      docs
``*.conf`` anywhere (incl. ``previews/cameras.conf``)  source
other ``previews/*``                                  previews
``*.scad``, ``ci.*``, ``*.args``, ``ARCHIVED``         source
anything else                                         other
====================================================  ========

**The rule** (:func:`classify_pr`): PR ``P`` is a ``member`` of design ``D``
iff ``P``'s files under ``designs/D/`` include at least one ``source``,
``docs`` or ``ai`` file — with two exclusions:

* ``sweep`` — ``D``'s only source files are ``team.conf``/``catalog.conf``,
  it has no ``.md``, and ``P`` substantively (member-kind) touches ≥ 5
  designs (catalog sweeps);
* ``stacked-excluded`` — ``P`` is NOT merged, substantively touches ≥ 2
  designs, and its title names (``(?<![a-z0-9-])<d>(?![a-z0-9-])``,
  case-folded) at least one of those designs but not ``D`` (a stacked base
  carrying another PR's design).

Everything else under ``designs/D/`` (stamp/previews/other only) is
``regen-only`` — the upstream-impact rows the views collapse into
"Maintenance".

**Main commits** (:func:`main_commit_class`, CC-1): a first-parent main
commit touching ``designs/D/`` is ``substantive`` when its files include a
source/docs/ai kind, ``stamp-only`` when its only file is the stamp, else
``previews-only``. CC-1 over the golden: (54 total, 49 with ≤ 1 parent,
19 / 19 / 11).

Records carry :data:`RULE_VERSION`; a rule change is an extractor-version
bump that re-derives every record from evidence without a re-harvest.

Implementation notes (the rule as built, measured against the audit's
``membership.csv``: 670 of its 671 PR × design verdicts are reproduced, and
tests/test_membership.py pins the one difference — #86 × ``nuggs``, a PR
whose only file is a PDF, kind ``other``, which the audit's script counted as
a member while the rule above, and docs/provenance.md §Membership, make an
``other``-only PR ``regen-only``):

* Kinds are decided on the path RELATIVE to ``designs/<D>/``; glob ``*``
  never crosses a ``/`` (``previews/lifestyle-*.png`` is a direct child of
  ``previews/``; ``*.md``/``*.conf``/``*.scad``/``*.args``/``ci.*``/
  ``ARCHIVED`` are matched on the basename at any depth). Matching is
  case-sensitive (git paths are).
* The sweep exclusion reads "D's only source files" as "D's member-kind
  files are exactly ``team.conf`` and/or ``catalog.conf`` at the design
  root" — an AI shot or a doc keeps a PR a member.
* The sweep test runs before the stacked-base test (a sweep is merged, so
  the two never compete in practice; the order is fixed for determinism).

Owner: H2. Pure.
"""

from __future__ import annotations

import re
from typing import Any

RULE_VERSION = "membership 1"
FILE_KINDS = ("source", "docs", "previews", "stamp", "ai", "other")
MEMBER_KINDS = frozenset({"source", "docs", "ai"})
VERDICTS = ("member", "regen-only", "sweep", "stacked-excluded")
SWEEP_MIN_DESIGNS = 5
STACKED_MIN_DESIGNS = 2

#: The design-root metadata files a catalog sweep touches (``team.conf``, ``catalog.conf``).
SWEEP_FILES = frozenset({"team.conf", "catalog.conf"})

_STAMP = "previews/.regen-stamp"
_AI_RE = re.compile(r"previews/(?:lifestyle-[^/]*\.(?:png|gif)|product-still-[^/]*\.png)")
_SOURCE_BASENAME_RE = re.compile(r"[^/]*\.scad|ci\.[^/]*|[^/]*\.args|ARCHIVED")


def file_kind(rel_path: str) -> str:
    """The kind of one path relative to its ``designs/<D>/`` directory."""
    if not isinstance(rel_path, str) or not rel_path:
        raise ValueError(f"file_kind: not a relative path: {rel_path!r}")
    base = rel_path.rsplit("/", 1)[-1]
    if rel_path == _STAMP:
        return "stamp"
    if _AI_RE.fullmatch(rel_path):
        return "ai"
    if base.endswith(".md"):
        return "docs"
    if base.endswith(".conf"):
        return "source"
    if rel_path.startswith("previews/"):
        return "previews"
    if _SOURCE_BASENAME_RE.fullmatch(base):
        return "source"
    return "other"


def design_files(paths: list[str]) -> dict[str, list[str]]:
    """``{D: [rel paths]}`` for every ``designs/<D>/…`` path (``designs/<file>`` at the root is ignored).

    Rel paths keep their input order with duplicates dropped; the dict is
    keyed in first-seen order (callers sort when order matters).
    """
    out: dict[str, list[str]] = {}
    for path in paths:
        if not isinstance(path, str):
            raise ValueError(f"design_files: not a path: {path!r}")
        parts = path.split("/")
        if len(parts) < 3 or parts[0] != "designs" or not parts[1] or not parts[-1]:
            continue
        rel = "/".join(parts[2:])
        bucket = out.setdefault(parts[1], [])
        if rel not in bucket:
            bucket.append(rel)
    return out


def _title_names(title: str, design: str) -> bool:
    """The title names ``design`` as a whole slug token (case-folded)."""
    rx = re.compile(r"(?<![a-z0-9-])" + re.escape(design) + r"(?![a-z0-9-])")
    return rx.search(title.casefold()) is not None


def classify_pr(paths: list[str], *, title: str, merged: bool) -> dict[str, dict[str, Any]]:
    """``{D: {"membership": verdict, "kinds": sorted kinds}}`` for every touched design."""
    files = design_files(paths)
    title_cf = title if isinstance(title, str) else ""
    kinds = {d: sorted({file_kind(r) for r in rels}) for d, rels in files.items()}
    substantive = sorted(d for d, ks in kinds.items() if MEMBER_KINDS & set(ks))
    named = {d for d in substantive if _title_names(title_cf, d)}
    out: dict[str, dict[str, Any]] = {}
    for design in sorted(files):
        ks = kinds[design]
        if not MEMBER_KINDS & set(ks):
            verdict = "regen-only"
        else:
            member_files = {r for r in files[design] if file_kind(r) in MEMBER_KINDS}
            if member_files <= SWEEP_FILES and len(substantive) >= SWEEP_MIN_DESIGNS:
                verdict = "sweep"
            elif (not merged and len(substantive) >= STACKED_MIN_DESIGNS
                  and named and design not in named):
                verdict = "stacked-excluded"
            else:
                verdict = "member"
        out[design] = {"membership": verdict, "kinds": ks}
    return out


def main_commit_class(rel_paths: list[str]) -> str:
    """``substantive`` | ``stamp-only`` | ``previews-only`` for one main commit's design files."""
    rels = list(rel_paths)
    if not rels:
        raise ValueError("main_commit_class: a main commit touching designs/<D>/ has at least one file")
    kinds = {file_kind(r) for r in rels}
    if kinds & MEMBER_KINDS:
        return "substantive"
    if set(rels) == {_STAMP}:
        return "stamp-only"
    return "previews-only"


def selftest_cases() -> list:
    """Offline negatives: a stamp-only PR is not a member; a sweep is excluded; a stacked base is
    excluded; an AI lifestyle PNG makes a member; cameras.conf is source."""
    six = [f"designs/d{i}/team.conf" for i in range(6)]

    def verdict(paths: list[str], design: str, *, title: str = "x", merged: bool = True) -> str:
        return classify_pr(paths, title=title, merged=merged)[design]["membership"]

    stacked = ["designs/alpha/alpha.scad", "designs/beta/beta.scad"]
    return [
        ("membership: a stamp-only PR is regen-only, not a member",
         lambda: verdict(["designs/x/previews/.regen-stamp"], "x") == "regen-only"),
        ("membership: a previews-only PR is regen-only",
         lambda: verdict(["designs/x/previews/a.png"], "x") == "regen-only"),
        ("membership: a team.conf sweep over >= 5 designs is excluded",
         lambda: all(verdict(six, f"d{i}") == "sweep" for i in range(6))),
        ("membership: the same team.conf edit on 4 designs stays a member (sweep bound)",
         lambda: verdict(six[:4], "d0") == "member"),
        ("membership: an unmerged stacked base is excluded from the design its title omits",
         lambda: verdict(stacked, "beta", title="Add design: alpha", merged=False) == "stacked-excluded"),
        ("membership: the stacked base stays a member of the design its title names",
         lambda: verdict(stacked, "alpha", title="Add design: alpha", merged=False) == "member"),
        ("membership: a merged multi-design PR is never stacked-excluded",
         lambda: verdict(stacked, "beta", title="Add design: alpha", merged=True) == "member"),
        ("membership: an AI lifestyle PNG makes a member",
         lambda: verdict(["designs/x/previews/lifestyle-desk.png"], "x") == "member"),
        ("membership: previews/cameras.conf is source",
         lambda: file_kind("previews/cameras.conf") == "source"),
        ("membership: previews/CAMERAS.md is docs",
         lambda: file_kind("previews/CAMERAS.md") == "docs"),
        ("membership: a stamp-only main commit is stamp-only, a png one previews-only",
         lambda: (main_commit_class(["previews/.regen-stamp"]) == "stamp-only"
                  and main_commit_class(["previews/.regen-stamp", "previews/a.png"]) == "previews-only")),
    ]
