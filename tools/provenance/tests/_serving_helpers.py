"""Shared builders for test_serving / test_codebasis (H4's helper module, per tests/fakes.py).

Nothing here is a fake of another builder's module: the probe events are built
directly from the committed raw fixtures (the shape serving.annotate_record
consumes — any contract-valid event@1), and the code basis is
``codebasis.GitCodeBasis`` over a ``fakes.FakeGitReader`` loaded from
``fixtures/main_history.json.gz`` + ``fixtures/codebasis/``. test_acceptance
(H3) may reuse :func:`fixture_codebasis` at integration.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Optional

from conftest import OWNER, OWNER_LOGIN, REPO_NAME, codebasis_blob, codebasis_index, main_history
from fakes import FakeCommit, FakeGitReader
from provenance import codebasis, serving
from provenance.serving import ts_epoch

MAIN_REF = "refs/remotes/origin/main"
REGISTRY = ".github/models/registry.conf"
ACTIONS_BOT = "github-actions[bot]"


# ---------------------------------------------------------------------------
# Code basis from the fixtures.

def fixture_commits() -> dict[str, FakeCommit]:
    """Every main commit since 2026-07-31 (parents, committer epoch, which watched paths its
    first-parent diff touches) plus the PR-head commits the codebasis index carries; files at
    the shas the index covers."""
    mh = main_history()
    index = codebasis_index()
    touches = mh["touches"]
    commits: dict[str, FakeCommit] = {}
    for row in mh["commits"]:
        sha = row["sha"]
        commits[sha] = FakeCommit(
            sha=sha, parents=list(row["parents"]), epoch=ts_epoch(row["committed_at"]),
            changed=sorted(p for p, shas in touches.items() if sha in shas))
    for sha, paths in index.items():
        c = commits.setdefault(sha, FakeCommit(sha=sha))
        for path in paths:
            c.files[path] = codebasis_blob(sha, path)
    return commits


def fixture_git(*, extra: Iterable[FakeCommit] = (), drop: Iterable[str] = (),
                merges: Optional[dict] = None, auto_merge: Iterable[tuple[str, str]] = (),
                tip: Optional[str] = None) -> FakeGitReader:
    """A FakeGitReader over :func:`fixture_commits`. ``auto_merge`` pairs ``(main, head)`` get a
    merge-tree result = main's files overlaid with the head's (a merge with no conflict on the
    files the join reads; on the fixture heads the two blobs are identical anyway). ``tip``
    moves ``origin/main`` (e.g. onto an ``extra`` commit stacked on a fixture commit)."""
    commits = fixture_commits()
    for c in extra:
        commits[c.sha] = c
    for sha in drop:
        commits.pop(sha, None)
    tip = tip or main_history()["commits"][0]["sha"]
    m = dict(merges or {})
    for main, head in auto_merge:
        files = dict(commits[main].files) if main in commits else {}
        files.update(commits[head].files if head in commits else {})
        m[(main, head)] = (files, set())
    return FakeGitReader(list(commits.values()), refs={MAIN_REF: tip}, merges=m)


def fixture_codebasis(**kw: Any) -> codebasis.GitCodeBasis:
    return codebasis.GitCodeBasis(fixture_git(**kw))


def pr_merge_inputs(receipts: Iterable[dict], head_ref: str) -> tuple[list[FakeCommit], list[tuple[str, str]]]:
    """The ``(main@created_at, head)`` merge pairs of every auto-review run on ``head_ref``, plus a
    bare commit for each head the codebasis index does not carry (local, as after the job-start
    fetch — its files then come from the merge result)."""
    git = fixture_git()
    pairs, extra = set(), {}
    for r in receipts:
        run = r["run"]
        if r["workflow"] == "auto-review.yml" and run["head_branch"] == head_ref:
            pairs.add((codebasis.main_at(git, MAIN_REF, ts_epoch(run["created_at"])), run["head_sha"]))
            if not git.has_commit(run["head_sha"]):
                extra[run["head_sha"]] = FakeCommit(run["head_sha"])
    return list(extra.values()), sorted(p for p in pairs if p[0])


def pr_codebasis(receipts: Iterable[dict], head_ref: str, *, extra: Iterable[FakeCommit] = (),
                 **kw: Any) -> codebasis.GitCodeBasis:
    """``GitCodeBasis`` for one PR's reviews: :func:`fixture_git` with every merge pair of
    :func:`pr_merge_inputs` resolvable (e.g. #636 on ``claude/issue-592-nuggs-vent-cap`` — NVC-5)."""
    heads, pairs = pr_merge_inputs(receipts, head_ref)
    return codebasis.GitCodeBasis(fixture_git(extra=list(heads) + list(extra), auto_merge=pairs, **kw))


# ---------------------------------------------------------------------------
# Probe events and records (the shapes annotate_record consumes).

def runtime(platform: str = "unknown") -> dict[str, Any]:
    return {"platform": platform, "harness": None, "role": None, "workflow": None, "job": None,
            "job_id": None, "run_id": None, "attempt": None, "chain": None, "chain_link": None,
            "links_not_served": None, "provider": None, "model": None, "model_basis": "none"}


def signals(login: Optional[str], **kw: Any) -> dict[str, Any]:
    out = {"login": login, "login_type": "Bot" if login and login.endswith("[bot]") else "User",
           "app": None, "marker": None, "commit_author_name": None, "commit_author_email": None,
           "committer_login": None, "status_context": None, "regen_identity": False,
           "trailer_coauthors": [], "trailer_session": None}
    out.update(kw)
    return out


def event(eid: str, kind: str, ts: str, *, login: Optional[str], trust: str = "login",
          trust_basis: str = "login", pr: Optional[int] = None, issue: Optional[int] = None,
          sha: Optional[str] = None, fields: Optional[dict] = None, url: str = "",
          platform: str = "unknown", **sig: Any) -> dict[str, Any]:
    return {"id": eid, "ts": ts, "ts_precision": "second", "tz": "UTC", "kind": kind,
            "episode": None, "pr": pr, "issue": issue, "sha": sha, "head_sha": None,
            "stale_sha": False, "after_merge": False,
            "url": url or f"https://github.com/{OWNER}/{REPO_NAME}/pull/{pr or issue or 1}",
            "signals": signals(login, **sig), "trust": trust, "trust_basis": trust_basis,
            "runtime": runtime(platform), "fields": dict(fields or {}), "edges": {"verifies": []}}


def evidence(raw: Optional[str] = None) -> dict[str, Any]:
    return {"raw": raw, "raw_sha256": None, "revision": 1, "receipts": [], "source": "evidence"}


def pr_record(n: int, events: list[dict], *, head_ref: Optional[str], created_at: str,
              closed_at: Optional[str]) -> dict[str, Any]:
    return {"format": "record@1", "kind": "pr", "key": str(n), "extractor": "provenance-extract 1",
            "incomplete": [], "events": events, "pr": n, "state": "merged", "created_at": created_at,
            "closed_at": closed_at, "merged_at": closed_at, "merge_commit_sha": None,
            "merge_method": None, "head_ref": head_ref, "base_ref": "main", "linked_issues": [],
            "briefs": [], "designs": {}, "rounds": [], "threads": None, "noise_counts": {},
            "unknown": {"markers": {}, "steps": {}}, "evidence": evidence(f"raw/pr/{n}.json.gz")}


def brief_record(n: int, events: list[dict], *, labels: Iterable[str] = ("design-brief",),
                 created_at: str = "2026-09-01T00:00:00Z") -> dict[str, Any]:
    return {"format": "record@1", "kind": "brief", "key": str(n), "extractor": "provenance-extract 1",
            "incomplete": [], "events": events, "issue": n, "state": "closed", "state_reason": "completed",
            "created_at": created_at, "closed_at": None, "labels": sorted(labels), "design_name": None,
            "prs": [], "evidence": evidence(f"raw/brief/{n}.json.gz")}


_LEAD_KIND = {"ship_lock": "brief.claimed", "shipped": "brief.shipped", "declined": "brief.declined",
              "deferred": "brief.deferred", "ship_lock_withdrawn": "brief.withdrawn"}


def brief_from_raw(raw: dict) -> dict[str, Any]:
    """record@1:brief probe from a raw-brief@1 fixture: filed + the lead-classified comments."""
    issue = raw["issue"]
    n = issue["number"]
    url = f"https://github.com/{OWNER}/{REPO_NAME}/issues/{n}"
    evs = [event(f"issue:{n}:filed", "brief.filed", issue["created_at"], login=issue["user"]["login"],
                 issue=n, url=url, fields={"design_name": None})]
    for c in raw["comments"]:
        kind = _LEAD_KIND.get(c["body"]["lead"])
        if kind is None:
            continue
        lead = c["body"].get("lead_fields") or {}
        fields = {"design_name": lead.get("design_name")}
        if kind == "brief.shipped":
            fields["shipped_pr"] = lead.get("shipped_pr")
        evs.append(event(f"issuecomment:{c['id']}", kind, c["created_at"], login=c["user"]["login"],
                         issue=n, url=f"{url}#issuecomment-{c['id']}", fields=fields))
    return brief_record(n, evs, labels=issue["labels"], created_at=issue["created_at"])


def signoffs_from_raw(raw: dict) -> list[dict[str, Any]]:
    """review.signoff probes: every comment whose last suffix/marker line is a JANE/DRIK sign-off.
    Trust as trust.comment_tier would give it (Actions bot + suffix → verified; the owner's
    token → claimed/marker:owner-token; anything else → claimed/no-suffix)."""
    out = []
    n = raw["pr"]
    for c in raw["issue_comments"]:
        body = c["body"]
        lines = body["suffix_markers"] or body["marker_lines"]
        last = lines[-1] if lines else ""
        family = next((f for f in ("JANE_SIGNOFF", "DRIK_SIGNOFF") if f in last), None)
        if family is None:
            continue
        sha = last.split("sha=")[1].split()[0]
        login = c["user"]["login"]
        if login == ACTIONS_BOT and body["suffix_ok"]:
            trust, basis = "verified", "actions-bot+suffix"
        elif login == OWNER_LOGIN:
            trust, basis = "claimed", "marker:owner-token"
        else:
            trust, basis = "claimed", "marker:no-suffix"
        out.append(event(f"issuecomment:{c['id']}", "review.signoff", c["created_at"], login=login,
                         trust=trust, trust_basis=basis, pr=n, sha=sha,
                         url=f"https://github.com/{OWNER}/{REPO_NAME}/pull/{n}#issuecomment-{c['id']}",
                         platform="github-actions" if login == ACTIONS_BOT else "unknown",
                         fields={"family": family, "verdict": "pass", "fuse": "none", "edited": False},
                         marker=family))
    return out


def commit_from_raw(raw: dict, sha_prefix: str, kind: str = "commit.design") -> dict[str, Any]:
    c = next(x for x in raw["commits"] if x["sha"].startswith(sha_prefix))
    coauthors = [t["value"] for t in c["commit"]["message"]["trailers"] if t["key"] == "Co-Authored-By"]
    n = raw["pr"]
    return event(f"commit:{c['sha']}", kind, c["commit"]["author"]["date"], login=(c["author"] or {}).get("login"),
                 pr=n, sha=c["sha"], url=f"https://github.com/{OWNER}/{REPO_NAME}/pull/{n}/commits/{c['sha']}",
                 fields={"parents": len(c["parents"]), "signature_verified": bool(c["commit"]["verified"])},
                 trailer_coauthors=coauthors, commit_author_name=c["commit"]["author"]["name"])


def pr_from_raw(raw: dict, events: list[dict]) -> dict[str, Any]:
    pull = raw["pull"]
    return pr_record(raw["pr"], events, head_ref=pull["head"]["ref"], created_at=pull["created_at"],
                     closed_at=pull["closed_at"])


def pr_opened(raw: dict) -> dict[str, Any]:
    pull = raw["pull"]
    return event(f"pr:{raw['pr']}:opened", "pr.opened", pull["created_at"], login=pull["user"]["login"],
                 pr=raw["pr"], fields={"draft": bool(pull["draft"])})


def shifted_receipt(receipt: dict, *, run_id: int, seconds: int, workflow: Optional[str] = None) -> dict:
    """A copy of ``receipt`` as another run, every timestamp moved by ``seconds``."""
    from provenance.serving import ts_str

    r = copy.deepcopy(receipt)

    def move(obj: dict, key: str) -> None:
        if obj.get(key):
            obj[key] = ts_str(ts_epoch(obj[key]) + seconds)

    r["run"]["id"] = run_id
    if workflow:
        r["workflow"] = workflow
        r["run"]["path"] = ".github/workflows/" + workflow
    for k in ("created_at", "updated_at", "run_started_at"):
        move(r["run"], k)
    for job in r["jobs"] or []:
        job["id"] = job["id"] + run_id % 1000
        for k in ("started_at", "completed_at", "created_at"):
            move(job, k)
        for step in job.get("steps") or []:
            move(step, "started_at")
            move(step, "completed_at")
    return r


def window_of(index: serving.ReceiptIndex, run_id: int, step_name: str, attempt: Optional[int] = None):
    return next(w for w in index.windows() if w.run_id == run_id and w.step_name == step_name
                and (attempt is None or w.attempt == attempt))
