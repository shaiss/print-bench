"""H3's shared test helpers (extract / episodes / acceptance): the fixture git, contexts, stand-ins.

Not a test module (no ``test_`` prefix). ``fixture_git()`` is a
``fakes.FakeGitReader`` over the committed fixtures only — main's commits
from ``main_history.json.gz`` (sha, parents, committer date and e-mail,
subject, the six tracked path touches), every fixture PR's commits, and the
``codebasis/`` blobs at the shas the index names — so a test never reads the
repository's own git history (a CI checkout may be shallow).

``standins`` (a pytest fixture) replaces, for one test, each function another
builder owns that is STILL the scaffold's ``NotImplementedError`` stub with a
neutral stand-in, so the structural tests run during the parallel build and,
unchanged, against the real implementations at integration. A test whose
assertion depends on such a function's VALUES carries ``@needs(...)`` instead.
"""

from __future__ import annotations

import calendar
import pathlib
from typing import Any, Optional

import pytest

from conftest import (FIXTURE_MAIN_SHA, FIXTURES, OWNER, OWNER_LOGIN, REPO, REPO_NAME, _is_scaffold_stub,
                      codebasis_blob, codebasis_index, main_history, raw_brief, raw_pr, raw_release, receipts)
from fakes import FakeCommit, FakeGitReader

from provenance import extract, markers, membership, trust

FIXTURE_PRS = (636, 371, 397, 634, 343, 316)
FIXTURE_BRIEFS = (281, 342, 363, 592)
MAIN_REF = "refs/remotes/origin/main"
REGISTRY = ".github/models/registry.conf"
DESIGN_FILES = FIXTURES / "design-files"


def epoch(ts: str) -> int:
    return calendar.timegm((int(ts[0:4]), int(ts[5:7]), int(ts[8:10]), int(ts[11:13]),
                            int(ts[14:16]), int(ts[17:19]), 0, 0, 0))


def design_names() -> frozenset[str]:
    """``designs/<name>/<name>.scad`` in the checkout (stable enough for prefix matching)."""
    root = REPO / "designs"
    return frozenset(p.name for p in root.iterdir() if (p / f"{p.name}.scad").is_file())


def _codebasis_files(sha: str) -> dict[str, bytes]:
    return {path: codebasis_blob(sha, path) for path in codebasis_index().get(sha, {})}


def main_at(rows: list[dict[str, Any]], tip: str, ts: str) -> Optional[str]:
    """The last first-parent main commit with committer date ``<= ts``."""
    by_sha = {r["sha"]: r for r in rows}
    sha: Optional[str] = tip
    while sha in by_sha:
        if by_sha[sha]["committed_at"] <= ts:
            return sha
        parents = by_sha[sha]["parents"]
        sha = parents[0] if parents else None
    return None


def fixture_git() -> FakeGitReader:
    """The FakeGitReader of the module docstring (refs: ``refs/remotes/origin/main``, ``main``).

    ``merges`` holds, for every ``auto-review.yml`` pull_request fixture receipt, the merge-tree
    result of (main@created_at, head) for the registry and the workflow: main's blob (no fixture PR
    touches ``.github/``, so the merge carries main's file), else the head's."""
    history = main_history()
    rows = history["commits"]
    touched: dict[str, list[str]] = {}
    for path, shas in history["touches"].items():
        for sha in shas:
            touched.setdefault(sha, []).append(path)
    commits = {r["sha"]: FakeCommit(sha=r["sha"], parents=list(r["parents"]), epoch=epoch(r["committed_at"]),
                                    subject=r.get("subject") or "", files=_codebasis_files(r["sha"]),
                                    changed=sorted(touched.get(r["sha"], [])),
                                    committer_email=r.get("committer_email") or "")
               for r in rows}
    for n in FIXTURE_PRS:
        for c in raw_pr(n)["commits"]:
            if c["sha"] in commits:
                continue
            committer = c["commit"]["committer"] or c["commit"]["author"] or {}
            commits[c["sha"]] = FakeCommit(sha=c["sha"], parents=list(c["parents"]),
                                           epoch=epoch(committer["date"]) if committer.get("date") else 0,
                                           files=_codebasis_files(c["sha"]),
                                           committer_email=committer.get("email") or "")
    tip = rows[0]["sha"]
    merges: dict[tuple[str, str], tuple[dict[str, bytes], set[str]]] = {}
    for rec in receipts():
        run = rec["run"]
        if rec["workflow"] != "auto-review.yml" or run.get("event") != "pull_request" or not run.get("head_sha"):
            continue
        base = main_at(rows, tip, run["created_at"])
        if base is None:
            continue
        files = {}
        for path in (REGISTRY, ".github/workflows/auto-review.yml"):
            blob = codebasis_blob(base, path) or codebasis_blob(run["head_sha"], path)
            if blob is not None:
                files[path] = blob
        merges[(base, run["head_sha"])] = (files, set())
    return FakeGitReader(list(commits.values()), refs={MAIN_REF: tip, "main": tip}, merges=merges)


def auto_review_run_ids() -> frozenset[int]:
    return frozenset(r["run"]["id"] for r in receipts() if r["workflow"] == "auto-review.yml")


def fixture_ctx(git=None, **overrides: Any) -> extract.ExtractContext:
    """The ExtractContext of the fixture harvest (main = #636's merge)."""
    merge_shas = {}
    for n in FIXTURE_PRS:
        pull = raw_pr(n)["pull"]
        if pull.get("merged_at") and pull.get("merge_commit_sha"):
            merge_shas[pull["merge_commit_sha"]] = n
    values = dict(owner=OWNER, repo=REPO_NAME, owner_login=OWNER_LOGIN,
                  git=git if git is not None else FakeGitReader([]), main_sha=FIXTURE_MAIN_SHA,
                  design_names=design_names(), merge_shas=merge_shas,
                  brief_numbers=frozenset(FIXTURE_BRIEFS), auto_review_run_ids=auto_review_run_ids())
    values.update(overrides)
    return extract.ExtractContext(**values)


def design_file(design: str, name: str) -> Optional[str]:
    p = DESIGN_FILES / design / name
    return p.read_text(encoding="utf-8") if p.is_file() else None


def _classify_standin(paths: list[str], *, title: str, merged: bool) -> dict[str, dict[str, Any]]:
    designs: dict[str, set[str]] = {}
    for p in paths:
        parts = p.split("/")
        if len(parts) >= 3 and parts[0] == "designs":
            designs.setdefault(parts[1], set()).add("source")
    return {d: {"kinds": sorted(k), "membership": "member"} for d, k in sorted(designs.items())}


#: (module, function, neutral stand-in) for the other builders' functions extraction calls.
STANDINS = (
    (trust, "comment_tier", lambda **kw: ("login", "login")),
    (trust, "status_tier", lambda status, run_ids: ("login", "login")),
    (markers, "unknown_families", lambda author, owner, lines: []),
    (membership, "classify_pr", _classify_standin),
)


@pytest.fixture
def standins(monkeypatch):
    """Neutral stand-ins for still-unimplemented H2 functions (a no-op once they land)."""
    for module, name, fn in STANDINS:
        if _is_scaffold_stub(getattr(module, name)):
            monkeypatch.setattr(module, name, fn)
    return monkeypatch


def pr_record(n: int, ctx: Optional[extract.ExtractContext] = None) -> dict[str, Any]:
    return extract.extract_pr(raw_pr(n), ctx or fixture_ctx())


def brief_record(n: int, ctx: Optional[extract.ExtractContext] = None) -> dict[str, Any]:
    return extract.extract_brief(raw_brief(n), ctx or fixture_ctx())


def release_record(tag: str = "v2.0", ctx: Optional[extract.ExtractContext] = None) -> dict[str, Any]:
    return extract.extract_release(raw_release(tag), ctx or fixture_ctx())


def events_of(record: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [e for e in record["events"] if e["kind"] == kind]


# ---------------------------------------------------------------------------
# The harvest of the fixture PRs, in the derive order (docs/provenance.md §Episodes):
# extract → run_claims → annotate_record → receipt_events → place. The serving
# steps run once H4's join exists (``joined()``); until then the records are
# placed straight from extraction, which every structural acceptance check
# already holds for (the join adds runtime and job.reviewer events, never
# rounds, kinds or noise).

def _serving_functions():
    from provenance import codebasis, serving
    return (serving.ReceiptIndex, serving.run_claims, serving.annotate_record, serving.receipt_events,
            codebasis.GitCodeBasis.basis_for, codebasis.GitCodeBasis.file_at,
            codebasis.GitCodeBasis.chain_models)


def joined() -> bool:
    """True once the serving join and the code basis are implemented."""
    return not any(_is_scaffold_stub(f) for f in _serving_functions())


def harvest() -> dict[str, Any]:
    """``{"prs": {n: record}, "briefs": {n: record}, "joined": bool, "git": FakeGitReader}``."""
    from provenance import codebasis, episodes, serving

    git = fixture_git()
    ctx = fixture_ctx(git)
    prs = {n: extract.extract_pr(raw_pr(n), ctx) for n in FIXTURE_PRS}
    briefs = {b: extract.extract_brief(raw_brief(b), ctx) for b in FIXTURE_BRIEFS}
    is_joined = joined()
    if is_joined:
        index = serving.ReceiptIndex(receipts())
        basis = codebasis.GitCodeBasis(git)
        claims = serving.run_claims(list(briefs.values()), index, owner_login=OWNER_LOGIN)
        briefs = {b: serving.annotate_record(r, index, basis, owner_login=OWNER_LOGIN, claims=claims)
                  for b, r in briefs.items()}
        joined_prs = {}
        for n, r in prs.items():
            r = serving.annotate_record(r, index, basis, owner_login=OWNER_LOGIN, claims=claims)
            r = dict(r, events=list(r["events"]) + serving.receipt_events(r, index, basis, owner=OWNER,
                                                                           repo=REPO_NAME))
            joined_prs[n] = r
        prs = joined_prs
    prs = {n: episodes.place(r) for n, r in prs.items()}
    briefs = {b: episodes.place(r) for b, r in briefs.items()}
    return {"briefs": briefs, "git": git, "joined": is_joined, "prs": prs}


def design_rows(design: str) -> list[dict[str, Any]]:
    """The design's committed rows from the fixture design files, every line blamed to the fixture
    main commit itself (the acceptance checks count rows, not their adding PRs)."""
    from provenance import episodes

    files, blame = {}, {}
    for name in ("PM.md", "NOTES.md"):
        text = design_file(design, name)
        if text is not None:
            path = f"designs/{design}/{name}"
            files[path] = text.encode("utf-8")
            blame[path] = [(FIXTURE_MAIN_SHA, i + 1) for i in range(len(text.split("\n")))]
    git = FakeGitReader([FakeCommit(FIXTURE_MAIN_SHA, [], 0, "Add design (#636)", files=files, blame=blame)])
    return episodes.decision_rows(git, FIXTURE_MAIN_SHA, design, owner=OWNER, repo=REPO_NAME, commit_to_pr={})


def roster_pm(design: str) -> Optional[str]:
    """``pm:`` of the design's team.conf at the fixture main, else None (the NVC-9 lens)."""
    text = design_file(design, "team.conf")
    for line in (text or "").splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "pm" and not line.lstrip().startswith("#"):
            return value.strip() or None
    return None


#: The test-only identity lens (actors.conf is P3c): marker family → reviewer, scout window → remy.
LENS_FAMILY = {"JANE_SIGNOFF": "jane", "DRIK_SIGNOFF": "drik"}
LENS_ROLE = {"product-scout": "remy"}


def handle(event: dict[str, Any], design: str) -> Optional[str]:
    if event["kind"] == "review.signoff":
        return LENS_FAMILY.get(event["fields"]["family"])
    if event["kind"] == "triage.verdict":
        return roster_pm(design)
    return LENS_ROLE.get(event["runtime"].get("role") or "")


def path_of(*parts: str) -> pathlib.Path:
    return FIXTURES.joinpath(*parts)
