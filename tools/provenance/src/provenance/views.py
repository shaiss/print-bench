"""Views — every record folded into one ``view@1`` per design directory on main.

``view = fold(records, main@sha)`` is pure (docs/provenance.md §Views). One
view exists for EVERY ``designs/<name>/`` directory with an entry
``<name>.scad`` at the harvest's main sha — including a design with no PR,
brief or row (an empty view, so the site shows "No recorded build history"
rather than "settling" forever).

What lands in a design's view:

* every event of every PR record whose ``designs[<name>].membership`` is
  ``member`` (the PR's whole story — its rounds are the design's rounds);
* PR records where the design is ``regen-only`` or ``sweep`` → one
  ``maintenance`` row each (``{pr, membership, at: merged_at or closed_at,
  url}``), no events;
* every event of every brief record linked to the design: the brief's
  ``design_name`` equals the design, OR a member PR lists the brief in
  ``briefs``; brief numbers and any ``design_name`` slug that differs from
  the directory name are recorded in ``aliases`` (#393 → czs-slider);
* every direct-to-main commit record touching the design as a member;
* the design's committed rows (``episodes.decision_rows`` at main);
* releases whose ``designs`` contain the design → ``releases`` (+ their
  ``release`` events).

Events are de-duplicated by ``id`` (a brief event reached through two PRs is
one event) and sorted by ``canonical.event_sort_key``. ``episodes`` is
``episodes.episodes_of`` over the view's events. ``counts``: events, rounds
(``R:`` episodes), prs, maintenance rows, sign-offs by tier
(verified/window/claimed), triage events, and ``job.reviewer`` events with
``posted: false`` ("ran, posted nothing").

Owner: H5.
"""

from __future__ import annotations

from typing import Any

from .protocols import GitReader

VIEW_FORMAT = "view@1"


def design_names(git: GitReader, main_sha: str) -> list[str]:
    """Sorted ``designs/<name>/`` directories at ``main_sha`` that carry ``<name>.scad``."""
    raise NotImplementedError("builder H5")


def build_view(design: str, *, records: list[dict[str, Any]], rows: list[dict[str, Any]],
               main_sha: str, owner: str, repo: str) -> dict[str, Any]:
    """One view@1 (module docstring)."""
    raise NotImplementedError("builder H5")


def build_views(records: list[dict[str, Any]], *, git: GitReader, main_sha: str, owner: str,
                repo: str, commit_to_pr: dict[str, int]) -> dict[str, dict[str, Any]]:
    """``{design: view@1}`` for every design on main."""
    raise NotImplementedError("builder H5")
