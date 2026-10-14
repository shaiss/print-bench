"""raw@1 projections — REST payload → the closed shape stored under ``raw/`` on ``provenance``.

The evidence branch keeps API payloads, but never whole: each endpoint's
response is projected onto a closed field list (contract ``raw-pr@1``,
``raw-brief@1``, ``raw-release@1``, ``receipt@1`` ``run``) with every body
replaced by a digest (:mod:`provenance.digest`). Projection does three jobs:

* **no prose** — ``body``/``message`` fields become digests; a status
  ``description`` survives only for a ``reviewer-signoff`` status the Actions
  bot created (our own fixed sentences — :func:`project_status`); verification
  payloads/signatures, patches and
  ``author_association`` are dropped;
* **no volatility** — reaction counts, avatar/URL templates, node ids and
  nested repository objects never reach a stored byte, so a refreeze of an
  unchanged PR is byte-identical;
* **one shape per endpoint** — the extractor (``extract.py``) reads exactly
  these keys, and the contract validator refuses any other.

Ordering is part of the shape: ``commits`` and ``timeline`` keep API order
(chronological; round folding depends on commit order), everything else is
sorted by a stated key (:data:`SORT_KEYS`).

Implemented in full by the scaffold: the freezer (``freeze.py``, H6) writes
through these functions and the extractor (``extract.py``, H3) reads their
output, so the shape has one author. H3 owns this module from here —
extending a projection is a contract change (site/lib/provenance-contract.json)
plus a fixture regeneration (tests/dev/build_fixtures.py).

Pure: no I/O, no clock.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .digest import body_digest, message_digest

RAW_PR_FORMAT = "raw-pr@1"
RAW_BRIEF_FORMAT = "raw-brief@1"
RAW_RELEASE_FORMAT = "raw-release@1"

#: The run-object projection shared by receipts and ``ci_runs`` — identical to
#: the field set of the #843 snapshot's ``runs.tar`` rows (capture.py), so an
#: ingested receipt and a live one have the same run shape.
RUN_FIELDS = (
    "id", "name", "path", "event", "status", "conclusion", "head_branch", "head_sha",
    "created_at", "updated_at", "run_started_at", "run_attempt", "run_number",
    "html_url", "display_title",
)

#: Status contexts whose ``description`` is kept verbatim when the Actions bot created the status
#: (our own fixed sentences); every other context's — and another creator's — is dropped (``null``).
STATUS_DESCRIPTION_CONTEXTS = frozenset({"reviewer-signoff"})

#: Timeline events that are dropped: their content is captured by a richer
#: endpoint (``commented`` → issue comments, ``committed`` → commits,
#: ``reviewed`` bodies → reviews; ``reviewed`` itself is kept, body-less).
TIMELINE_DROP = frozenset({"commented", "committed", "line-commented", "commit-commented"})

#: How each sorted list is ordered (documentation; the functions below apply it).
SORT_KEYS = {
    "files": "filename",
    "reviews": "(submitted_at, id)",
    "review_comments": "(created_at, id)",
    "issue_comments": "(created_at, id)",
    "ci_runs": "(created_at, id)",
    "statuses[sha]": "(created_at, id)",
    "deployments": "id",
    "deployment statuses": "id",
    "labels": "name",
}


def user(obj: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """``{login, type}`` of a REST user object, or ``None``."""
    if not isinstance(obj, dict) or not obj.get("login"):
        return None
    return {"login": obj["login"], "type": obj.get("type")}


def login(obj: Any) -> Optional[str]:
    """A login from a user object or an already-projected login string."""
    if isinstance(obj, str):
        return obj or None
    if isinstance(obj, dict):
        return obj.get("login") or None
    return None


def app_slug(obj: Any) -> Optional[str]:
    """``performed_via_github_app.slug`` or ``None``."""
    return obj.get("slug") if isinstance(obj, dict) else None


def project_run(run: dict[str, Any]) -> dict[str, Any]:
    """REST workflow-run object (or a snapshot row) → the receipt/ci_runs run shape."""
    out = {k: run.get(k) for k in RUN_FIELDS}
    out["actor"] = login(run.get("actor"))
    out["triggering_actor"] = login(run.get("triggering_actor"))
    prs = run.get("pull_requests") or []
    out["pull_requests"] = sorted(
        {p if isinstance(p, int) else p.get("number") for p in prs} - {None}
    )
    return out


def project_pull(p: dict[str, Any]) -> dict[str, Any]:
    head = p.get("head") or {}
    base = p.get("base") or {}
    repo = head.get("repo") or {}
    return {
        "base": {"ref": base.get("ref"), "sha": base.get("sha")},
        "body": body_digest(p.get("body")),
        "changed_files": p.get("changed_files"),
        "closed_at": p.get("closed_at"),
        "commits": p.get("commits"),
        "created_at": p.get("created_at"),
        "draft": bool(p.get("draft")),
        "head": {"ref": head.get("ref"), "repo": repo.get("full_name"), "sha": head.get("sha")},
        "labels": sorted(lbl.get("name") for lbl in p.get("labels") or [] if lbl.get("name")),
        "merge_commit_sha": p.get("merge_commit_sha"),
        "merged": bool(p.get("merged") or p.get("merged_at")),
        "merged_at": p.get("merged_at"),
        "merged_by": user(p.get("merged_by")),
        "number": p.get("number"),
        "state": p.get("state"),
        "title": p.get("title"),
        "updated_at": p.get("updated_at"),
        "user": user(p.get("user")),
    }


def project_files(files: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [
        {"filename": f.get("filename"), "previous_filename": f.get("previous_filename"),
         "status": f.get("status")}
        for f in files
    ]
    return sorted(out, key=lambda f: f["filename"] or "")


def _ident(obj: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not isinstance(obj, dict):
        return None
    return {"date": obj.get("date"), "email": obj.get("email"), "name": obj.get("name")}


def project_commits(commits: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """``/pulls/{n}/commits`` items, API order kept (round folding reads the order)."""
    out = []
    for c in commits:
        inner = c.get("commit") or {}
        verification = inner.get("verification") or {}
        out.append({
            "author": user(c.get("author")),
            "commit": {
                "author": _ident(inner.get("author")),
                "committer": _ident(inner.get("committer")),
                "message": message_digest(inner.get("message")),
                "verification_reason": verification.get("reason"),
                "verified": bool(verification.get("verified")),
            },
            "committer": user(c.get("committer")),
            "parents": [p.get("sha") for p in c.get("parents") or []],
            "sha": c.get("sha"),
        })
    return out


def project_reviews(reviews: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [
        {"body": body_digest(r.get("body")), "commit_id": r.get("commit_id"), "id": r.get("id"),
         "state": r.get("state"), "submitted_at": r.get("submitted_at"), "user": user(r.get("user"))}
        for r in reviews
    ]
    return sorted(out, key=lambda r: (r["submitted_at"] or "", r["id"] or 0))


def project_review_comments(comments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [
        {"body": body_digest(c.get("body")), "commit_id": c.get("commit_id"),
         "created_at": c.get("created_at"), "id": c.get("id"),
         "in_reply_to_id": c.get("in_reply_to_id"), "path": c.get("path"),
         "pull_request_review_id": c.get("pull_request_review_id"),
         "updated_at": c.get("updated_at"), "user": user(c.get("user"))}
        for c in comments
    ]
    return sorted(out, key=lambda c: (c["created_at"] or "", c["id"] or 0))


def project_issue_comments(comments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [
        {"app": app_slug(c.get("performed_via_github_app")), "body": body_digest(c.get("body")),
         "created_at": c.get("created_at"), "id": c.get("id"),
         "updated_at": c.get("updated_at"), "user": user(c.get("user"))}
        for c in comments
    ]
    return sorted(out, key=lambda c: (c["created_at"] or "", c["id"] or 0))


def project_timeline(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Issue/PR timeline, API order kept, :data:`TIMELINE_DROP` events removed."""
    out = []
    for e in events:
        kind = e.get("event")
        if kind in TIMELINE_DROP or not kind:
            continue
        source = (e.get("source") or {}).get("issue") or {}
        label = (e.get("label") or {}).get("name")
        requested = e.get("requested_reviewer")
        out.append({
            "actor": user(e.get("actor") or e.get("user")),
            "app": app_slug(e.get("performed_via_github_app")),
            "commit_id": e.get("commit_id"),
            "created_at": e.get("created_at") or e.get("submitted_at"),
            "event": kind,
            "id": e.get("id"),
            "label": label,
            "requested_reviewer": login(requested),
            "source_is_pr": (bool(source.get("pull_request")) if source else None),
            "source_issue": source.get("number") if source else None,
            "state": e.get("state"),
            "state_reason": e.get("state_reason"),
        })
    return out


def project_runs(runs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [project_run(r) for r in runs]
    return sorted(out, key=lambda r: (r["created_at"] or "", r["id"] or 0))


def _actions_bot(name: Optional[str]) -> bool:
    """``github-actions[bot]`` (REST) / ``github-actions`` (GraphQL) — trust.is_actions_bot's rule,
    restated here so the raw projection imports nothing above it."""
    if not isinstance(name, str):
        return False
    n = name.strip().lower()
    return (n[:-5] if n.endswith("[bot]") else n) == "github-actions"


def project_status(s: dict[str, Any]) -> dict[str, Any]:
    """One commit status (``/commits/{sha}/statuses`` item or a #843 snapshot row).

    ``description`` survives only for a :data:`STATUS_DESCRIPTION_CONTEXTS` status the Actions bot
    created — the fixed sentences ``scripts/reviewer-signoff.sh`` posts. Any other creator (a
    statuses:write PAT, any workflow granted ``statuses: write``) could write 140 characters of free
    text, and evidence is add-only forever, so theirs is stored ``null`` (its reason then reads
    ``other``; its trust tier is already ``claimed``/``login``)."""
    context = s.get("context")
    creator = login(s.get("creator"))
    keep = context in STATUS_DESCRIPTION_CONTEXTS and _actions_bot(creator)
    return {
        "context": context,
        "created_at": s.get("created_at"),
        "creator": creator,
        "description": s.get("description") if keep else None,
        "id": s.get("id"),
        "state": s.get("state"),
        "target_url": s.get("target_url"),
        "updated_at": s.get("updated_at"),
    }


def project_statuses(statuses: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [project_status(s) for s in statuses]
    return sorted(out, key=lambda s: (s["created_at"] or "", s["id"] or 0))


def project_deployment(d: dict[str, Any], statuses: Iterable[dict[str, Any]]) -> dict[str, Any]:
    st = sorted(
        ({"created_at": s.get("created_at"), "creator": login(s.get("creator")),
          "id": s.get("id"), "state": s.get("state")} for s in statuses),
        key=lambda s: s["id"] or 0,
    )
    return {"created_at": d.get("created_at"), "creator": login(d.get("creator")),
            "environment": d.get("environment"), "id": d.get("id"), "ref": d.get("ref"),
            "sha": d.get("sha"), "statuses": st}


def project_threads(nodes: Iterable[dict[str, Any]], source: str,
                    pr_last_edited_at: Optional[str]) -> dict[str, Any]:
    """Review-thread resolution counts (``source`` is ``graphql`` or ``ccr-fixture``).

    ``nodes`` items carry ``resolved``, ``outdated`` and ``first_comment_id``
    (the GraphQL normaliser in github.py and the CCR fixture adapter both map
    onto these three keys). Sorted by first comment id.
    """
    items = sorted(
        ({"first_comment_id": n.get("first_comment_id"), "outdated": bool(n.get("outdated")),
          "resolved": bool(n.get("resolved"))} for n in nodes),
        key=lambda n: n["first_comment_id"] or 0,
    )
    return {"nodes": items, "pr_last_edited_at": pr_last_edited_at, "source": source,
            "total": len(items)}


def project_issue(i: dict[str, Any], last_edited_at: Optional[str]) -> dict[str, Any]:
    return {
        "app": app_slug(i.get("performed_via_github_app")),
        "body": body_digest(i.get("body")),
        "closed_at": i.get("closed_at"),
        "created_at": i.get("created_at"),
        "labels": sorted(lbl.get("name") for lbl in i.get("labels") or [] if lbl.get("name")),
        "last_edited_at": last_edited_at,
        "number": i.get("number"),
        "state": i.get("state"),
        "state_reason": i.get("state_reason"),
        "title": i.get("title"),
        "updated_at": i.get("updated_at"),
        "user": user(i.get("user")),
    }


def project_release(r: dict[str, Any]) -> dict[str, Any]:
    assets = sorted(
        ({"content_type": a.get("content_type"), "name": a.get("name"), "size": a.get("size")}
         for a in r.get("assets") or []),
        key=lambda a: a["name"] or "",
    )
    return {
        "assets": assets, "author": user(r.get("author")), "body": body_digest(r.get("body")),
        "created_at": r.get("created_at"), "draft": bool(r.get("draft")), "id": r.get("id"),
        "name": r.get("name"), "prerelease": bool(r.get("prerelease")),
        "published_at": r.get("published_at"), "tag_name": r.get("tag_name"),
        "target_commitish": r.get("target_commitish"),
    }


def raw_pr_doc(*, number: int, revision: int, captured: dict[str, Any], incomplete: list[str],
               pull: dict[str, Any], files: list[dict[str, Any]], commits: list[dict[str, Any]],
               reviews: list[dict[str, Any]], review_comments: list[dict[str, Any]],
               issue_comments: list[dict[str, Any]], timeline: list[dict[str, Any]],
               threads: dict[str, Any], ci_runs: list[dict[str, Any]],
               statuses: dict[str, list[dict[str, Any]]], deployments: list[dict[str, Any]],
               linked_issues: list[int]) -> dict[str, Any]:
    """Assemble one ``raw-pr@1`` document from ALREADY-PROJECTED parts.

    ``linked_issues`` = the PR body's ``refs_closes`` ∪ the ``claude/issue-<N>-*``
    head-ref number — EVERY linked issue, brief or not. Which of them are design
    briefs is decided at derive time from the evidence tree (an issue is a brief
    iff ``raw/brief/<n>`` exists — freeze captures a linked issue as a brief only
    if it carries or carried the ``design-brief`` label); the record splits
    ``linked_issues`` from ``briefs`` (critique item 24).
    """
    return {
        "captured": captured, "ci_runs": ci_runs, "linked_issues": sorted(set(linked_issues)),
        "commits": commits, "deployments": deployments, "files": files,
        "format": RAW_PR_FORMAT, "incomplete": sorted(set(incomplete)),
        "issue_comments": issue_comments, "pr": number, "pull": pull, "review_comments": review_comments,
        "reviews": reviews, "revision": revision,
        "statuses": {sha: statuses[sha] for sha in sorted(statuses)},
        "threads": threads, "timeline": timeline,
    }


def raw_brief_doc(*, number: int, revision: int, captured: dict[str, Any], incomplete: list[str],
                  issue: dict[str, Any], comments: list[dict[str, Any]],
                  timeline: list[dict[str, Any]]) -> dict[str, Any]:
    """Assemble one ``raw-brief@1`` document from already-projected parts."""
    return {"captured": captured, "comments": comments, "format": RAW_BRIEF_FORMAT,
            "incomplete": sorted(set(incomplete)), "issue": issue, "number": number,
            "revision": revision, "timeline": timeline}


def raw_release_doc(*, tag: str, revision: int, captured: dict[str, Any],
                    release: dict[str, Any]) -> dict[str, Any]:
    """Assemble one ``raw-release@1`` document."""
    return {"captured": captured, "format": RAW_RELEASE_FORMAT, "release": release,
            "revision": revision, "tag": tag}
