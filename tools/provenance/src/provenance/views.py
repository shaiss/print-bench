"""Views — every record folded into one ``view@1`` per design directory on main.

``view = fold(records, main@sha)`` is pure (docs/provenance.md §Views). One
view exists for EVERY ``designs/<name>/`` directory with an entry
``<name>.scad`` at the harvest's main sha — including a design with no PR,
brief or row (an empty view, so the site shows "No recorded build history"
rather than "settling" forever). The view does NOT carry the main sha (the
bundle's meta does): a main push that touches no ``designs/`` file must leave
every view byte-identical (critique item 6).

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
``episodes.episodes_of`` over the view's events and the member records'
rounds (``episodes.rounds_from_record``). ``counts``: events, rounds
(``R:`` episodes), prs, maintenance rows, sign-offs by tier
(verified/window/claimed), triage events, and ``job.reviewer`` events with
``posted: false`` ("ran, posted nothing").

Precisions this implementation fixes (all deterministic, none read main's
sha into a view):

* ``prs`` lists the MEMBER PRs only (maintenance PRs are the
  ``maintenance`` rows; a ``stacked-excluded`` PR appears nowhere in the
  design's view). ``briefs`` and ``aliases.briefs`` are the same set — every
  linked brief number (by ``design_name`` or a member PR's ``briefs``) — the
  first is the content list, the second the lookup set the site routes an old
  brief link through. ``aliases.slugs`` = every ``design_name`` (record or
  brief event field) of a linked brief that differs from the directory name.
* Dedup keeps, for one id carried by two records with DIFFERENT bytes (one
  commit in two stacked member PRs, each copy placed in its own PR's round),
  the copy with the smallest canonical JSON, so the view never depends on the
  order of ``records``.
* ``maintenance`` and ``releases`` are sorted by their timestamp (undated
  last), then PR number / tag; ``counts.rounds`` counts the ``R:`` entries of
  ``episodes``; ``counts.prs`` = ``len(prs)``.
* ``design_names`` keeps only directory names that full-match the contract's
  ``design`` slug (anything else could not carry a ``views/<design>.json``).

Owner: H5.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from . import canonical, episodes
from .extract import EXTRACTOR_VERSION
from .protocols import GitReader

VIEW_FORMAT = "view@1"

#: The contract's ``design`` slug (``types.design``).
DESIGN_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_OWNER_RE = re.compile(r"[A-Za-z0-9-]+")
_REPO_RE = re.compile(r"[A-Za-z0-9._-]+")
_TAG_RE = re.compile(r"[A-Za-z0-9._-]{1,100}")

#: The membership verdicts that collapse into a ``maintenance`` row (no events).
MAINTENANCE = ("regen-only", "sweep")
#: The sign-off tiers ``counts.signoffs`` reports (login/ambiguous/none sign-offs are not counted).
SIGNOFF_TIERS = ("verified", "window", "claimed")


def _base_url(owner: str, repo: str) -> str:
    if not _OWNER_RE.fullmatch(owner or "") or not _REPO_RE.fullmatch(repo or ""):
        raise ValueError(f"views: invalid owner/repo {owner!r}/{repo!r}")
    return f"https://github.com/{owner}/{repo}"


def _pull_url(owner: str, repo: str, pr: Any) -> str:
    if not isinstance(pr, int) or isinstance(pr, bool) or pr < 1:
        raise ValueError(f"views: invalid PR number {pr!r}")
    return f"{_base_url(owner, repo)}/pull/{pr}"


def _release_url(owner: str, repo: str, tag: Any) -> str:
    if not isinstance(tag, str) or not _TAG_RE.fullmatch(tag):
        raise ValueError(f"views: invalid release tag {tag!r}")
    return f"{_base_url(owner, repo)}/releases/tag/{tag}"


def design_names(git: GitReader, main_sha: str) -> list[str]:
    """Sorted ``designs/<name>/`` directories at ``main_sha`` that carry ``<name>.scad``."""
    names = set()
    for name in git.list_dir(main_sha, "designs"):
        if DESIGN_RE.fullmatch(name) and git.show(main_sha, f"designs/{name}/{name}.scad") is not None:
            names.add(name)
    return sorted(names)


def _membership(record: dict[str, Any], design: str) -> Optional[str]:
    entry = (record.get("designs") or {}).get(design)
    return entry.get("membership") if isinstance(entry, dict) else None


def _dedupe(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique by ``id`` (smallest canonical JSON wins), sorted by ``canonical.event_sort_key``."""
    best: dict[str, tuple[bytes, dict[str, Any]]] = {}
    for event in events:
        blob = canonical.dumps_bytes(event)
        held = best.get(event["id"])
        if held is None or blob < held[0]:
            best[event["id"]] = (blob, event)
    return sorted((pair[1] for pair in best.values()), key=canonical.event_sort_key)


def build_view(design: str, *, records: list[dict[str, Any]], rows: list[dict[str, Any]],
               owner: str, repo: str) -> dict[str, Any]:
    """One view@1 (module docstring)."""
    if not isinstance(design, str) or not DESIGN_RE.fullmatch(design):
        raise ValueError(f"views: invalid design name {design!r}")
    by_kind: dict[str, list[dict[str, Any]]] = {"pr": [], "brief": [], "commit": [], "release": []}
    for record in records:
        kind = record.get("kind")
        if kind not in by_kind:
            raise ValueError(f"views: unknown record kind {kind!r}")
        by_kind[kind].append(record)

    prs = sorted(by_kind["pr"], key=lambda r: r["pr"])
    member_prs = [r for r in prs if _membership(r, design) == "member"]
    maintenance_prs = [r for r in prs if _membership(r, design) in MAINTENANCE]
    via_prs = {b for r in member_prs for b in r.get("briefs", [])}
    briefs = [r for r in sorted(by_kind["brief"], key=lambda r: r["issue"])
              if r.get("design_name") == design or r["issue"] in via_prs]
    commits = [r for r in sorted(by_kind["commit"], key=lambda r: r["sha"])
               if _membership(r, design) == "member"]
    releases = [r for r in sorted(by_kind["release"], key=lambda r: r["tag"])
                if design in (r.get("designs") or [])]

    brief_numbers = sorted(via_prs | {r["issue"] for r in briefs})
    slugs: set[str] = set()
    for record in briefs:
        names = [record.get("design_name")]
        names += [(e.get("fields") or {}).get("design_name") for e in record.get("events", [])]
        slugs.update(n for n in names if isinstance(n, str) and n != design)

    events = _dedupe([e for r in member_prs + briefs + commits + releases for e in r["events"]]
                     + list(rows))
    rounds = [rd for r in member_prs for rd in episodes.rounds_from_record(r)]
    episode_list = episodes.episodes_of(events, rounds)

    maintenance = sorted(
        ({"pr": r["pr"], "membership": _membership(r, design),
          "at": r.get("merged_at") or r.get("closed_at"),
          "url": _pull_url(owner, repo, r["pr"])} for r in maintenance_prs),
        key=lambda m: (m["at"] is None, m["at"] or "", m["pr"]))
    release_rows = sorted(
        ({"tag": r["tag"], "published_at": r.get("published_at"),
          "url": _release_url(owner, repo, r["tag"])} for r in releases),
        key=lambda m: (m["published_at"] is None, m["published_at"] or "", m["tag"]))

    signoffs = {tier: 0 for tier in SIGNOFF_TIERS}
    for event in events:
        if event["kind"] == "review.signoff" and event.get("trust") in signoffs:
            signoffs[event["trust"]] += 1
    counts = {
        "events": len(events),
        "rounds": sum(1 for ep in episode_list if str(ep.get("id", "")).startswith("R:")),
        "prs": len(member_prs),
        "maintenance": len(maintenance),
        "signoffs": signoffs,
        "triage": sum(1 for e in events if e["kind"] == "triage.verdict"),
        "jobs_posted_nothing": sum(1 for e in events if e["kind"] == "job.reviewer"
                                   and (e.get("fields") or {}).get("posted") is False),
    }
    return {
        "format": VIEW_FORMAT,
        "design": design,
        "extractor": EXTRACTOR_VERSION,
        "aliases": {"briefs": brief_numbers, "slugs": sorted(slugs)},
        "prs": [r["pr"] for r in member_prs],
        "briefs": brief_numbers,
        "commits": [r["sha"] for r in commits],
        "episodes": episode_list,
        "events": events,
        "maintenance": maintenance,
        "releases": release_rows,
        "counts": counts,
    }


def build_views(records: list[dict[str, Any]], *, git: GitReader, main_sha: str, owner: str,
                repo: str, commit_to_pr: dict[str, int]) -> dict[str, dict[str, Any]]:
    """``{design: view@1}`` for every design on main."""
    out: dict[str, dict[str, Any]] = {}
    for design in design_names(git, main_sha):
        rows = episodes.decision_rows(git, main_sha, design, owner=owner, repo=repo,
                                      commit_to_pr=commit_to_pr)
        out[design] = build_view(design, records=records, rows=rows, owner=owner, repo=repo)
    return out
