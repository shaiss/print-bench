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

Owner: H2. Pure.
"""

from __future__ import annotations

from typing import Any

RULE_VERSION = "membership 1"
FILE_KINDS = ("source", "docs", "previews", "stamp", "ai", "other")
MEMBER_KINDS = frozenset({"source", "docs", "ai"})
VERDICTS = ("member", "regen-only", "sweep", "stacked-excluded")
SWEEP_MIN_DESIGNS = 5
STACKED_MIN_DESIGNS = 2


def file_kind(rel_path: str) -> str:
    """The kind of one path relative to its ``designs/<D>/`` directory."""
    raise NotImplementedError("builder H2")


def design_files(paths: list[str]) -> dict[str, list[str]]:
    """``{D: [rel paths]}`` for every ``designs/<D>/…`` path (``designs/<file>`` at the root is ignored)."""
    raise NotImplementedError("builder H2")


def classify_pr(paths: list[str], *, title: str, merged: bool) -> dict[str, dict[str, Any]]:
    """``{D: {"membership": verdict, "kinds": sorted kinds}}`` for every touched design."""
    raise NotImplementedError("builder H2")


def main_commit_class(rel_paths: list[str]) -> str:
    """``substantive`` | ``stamp-only`` | ``previews-only`` for one main commit's design files."""
    raise NotImplementedError("builder H2")


def selftest_cases() -> list:
    """Offline negatives: a stamp-only PR is not a member; a sweep is excluded; a stacked base is
    excluded; an AI lifestyle PNG makes a member; cameras.conf is source."""
    raise NotImplementedError("builder H2")
