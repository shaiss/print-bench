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
import gzip
import json
import posixpath
import tarfile
from typing import Any, Iterable, Optional

from conftest import OWNER, OWNER_LOGIN, REPO, REPO_NAME, codebasis_blob, codebasis_index, main_history
from fakes import FakeCommit, FakeGitReader
from provenance import codebasis, serving
from provenance.serving import ts_epoch

MAIN_REF = "refs/remotes/origin/main"
REGISTRY = ".github/models/registry.conf"
ACTIONS_BOT = "github-actions[bot]"
#: The committed #843 snapshot (main 411a756) — every watched run's jobs before retention.
RESCUE = REPO / "audits" / "provenance-2026-10" / "rescue"
WATCHED = ("auto-review.yml", "backlog-burn.yml", "chunker.yml", "design-run.yml", "labeler.yml",
           "oracle.yml", "product-scout.yml", "spike-converter.yml", "wright.yml")


# ---------------------------------------------------------------------------
# Receipts for the whole #843 snapshot (the real, concurrent run set).

def _reference_build_receipt():
    """The production writer, ``receipts.build_receipt`` (integration: it reproduces every
    committed fixture receipt byte for byte — test_receipts pins that — so the whole-snapshot
    index is built exactly as a live harvest would build it)."""
    from provenance import receipts
    return receipts.build_receipt


def snapshot_receipts(run_ids: Optional[Iterable[int]] = None) -> list[dict[str, Any]]:
    """receipt@1 for every completed, non-skipped watched run of the committed #843 snapshot
    (``rescue/runs.tar`` + ``rescue/jobs.tar``, read with ``extractfile`` only), or only for
    ``run_ids``. ~3 s for all 3,738 — the concurrent other-PR runs the 166 fixture receipts
    leave out (review round 2, issue 1)."""
    build = _reference_build_receipt()
    wanted = None if run_ids is None else set(run_ids)
    runs: dict[int, tuple[str, dict]] = {}
    with tarfile.open(RESCUE / "runs.tar") as tf:
        for m in tf.getmembers():
            wf = posixpath.basename(m.name)[: -len(".json.gz")]
            if m.isfile() and wf in WATCHED:
                for run in json.loads(gzip.decompress(tf.extractfile(m).read())):
                    if wanted is None or run["id"] in wanted:
                        runs[run["id"]] = (wf, run)
    out = []
    with tarfile.open(RESCUE / "jobs.tar") as tf:
        for m in tf.getmembers():
            name = posixpath.basename(m.name)
            if not (m.isfile() and name.endswith(".json.gz") and name.split(".")[0].isdigit()):
                continue
            hit = runs.get(int(name.split(".")[0]))
            if hit is None:
                continue
            wf, run = hit
            if run.get("status") != "completed" or run.get("conclusion") == "skipped":
                continue
            jobs = json.loads(gzip.decompress(tf.extractfile(m).read()))["jobs"]
            out.append(build(wf, run, jobs, "snapshot:pr843"))
    return sorted(out, key=lambda r: r["run"]["id"])


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
    return {"format": "record@1", "kind": "pr", "extractor": "provenance-extract 1",
            "incomplete": [], "events": events, "pr": n, "state": "merged", "created_at": created_at,
            "closed_at": closed_at, "merged_at": closed_at, "merge_commit_sha": None,
            "merge_method": None, "head_ref": head_ref, "base_ref": "main", "linked_issues": [],
            "briefs": [], "designs": {}, "rounds": [], "threads": None, "noise_counts": {},
            "unknown": {"markers": {}, "steps": {}}, "evidence": evidence(f"raw/pr/{n}.json.gz")}


def brief_record(n: int, events: list[dict], *, labels: Iterable[str] = ("design-brief",),
                 created_at: str = "2026-09-01T00:00:00Z") -> dict[str, Any]:
    return {"format": "record@1", "kind": "brief", "extractor": "provenance-extract 1",
            "incomplete": [], "events": events, "issue": n, "state": "closed", "state_reason": "completed",
            "created_at": created_at, "closed_at": None, "labels": sorted(labels), "design_name": None,
            "prs": [], "evidence": evidence(f"raw/brief/{n}.json.gz")}


_LEAD_KIND = {"ship_lock": "brief.claimed", "ship_lock_settle": "brief.claimed", "shipped": "brief.shipped",
              "declined": "brief.declined", "deferred": "brief.deferred", "ship_lock_withdrawn": "brief.withdrawn"}


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
        if kind == "brief.claimed":
            fields["settle"] = c["body"]["lead"] == "ship_lock_settle"
        if kind == "brief.withdrawn":
            fields["death"] = lead.get("death") is True
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

# ---------------------------------------------------------------------------
# auto-review.yml + registry.conf at 14745efd (run 31939632623's PR head, 2026-08-16).

#: The head of run 31939632623 (an E2 auto-review pull_request run: '/drik-review via Z.AI GLM 5.2').
E2_HEAD = "14745efd2042c9b13709b168d2a97110e00a3d30"
#: Verbatim lines of ``.github/workflows/auto-review.yml`` at :data:`E2_HEAD` (full file sha256
#: a1f71872…41c4): the name, ``on:``, ``jobs:``, ``design-changes`` up to its chain-resolve step, and
#: the whole ``drik-review`` job; each elided range is a whole-line comment saying so. The E2 steps
#: read ``--model ${{ needs.design-changes.outputs.model<N> }}`` — no literal pin (review round 2,
#: issue 2).
AUTO_REVIEW_E2 = """name: Auto design review (Jane / Drik / coach)
# [excerpt: lines 2-44 elided]
on:
  pull_request:
    types:
      - opened
      - ready_for_review
      - synchronize
      - reopened

# [excerpt: lines 53-63 elided]
jobs:
# [excerpt: lines 65-68 elided]
  design-changes:
    name: Check for design file changes
    runs-on: ubuntu-latest
    # Honour the opt-out label before doing any work.
    if: >-
      !contains(github.event.pull_request.labels.*.name, 'no-auto-review')
      && !github.event.pull_request.draft
    outputs:
      designs_changed: ${{ steps.check.outputs.designs_changed }}
      changed_designs: ${{ steps.check.outputs.changed_designs }}
      is_new_round: ${{ steps.round.outputs.is_new_round }}
      # The reviewer fallback chain, sourced from .github/models/registry.conf
      # (issue #206) instead of hardcoded per job. Reordering or swapping a model
      # within the chain is now a registry edit; the drift-guard test
      # (tools/model-registry/tests/test_workflow_drift.py) pins these to the
      # registry so the two cannot diverge. The per-provider secret wiring stays
      # literal in each ship step below (the Actions constraint).
      model1: ${{ steps.chain.outputs.link1_model }}
      model2: ${{ steps.chain.outputs.link2_model }}
      model3: ${{ steps.chain.outputs.link3_model }}
      model4: ${{ steps.chain.outputs.link4_model }}
    steps:
      - uses: actions/checkout@v5
        with:
          persist-credentials: false
          fetch-depth: 0

      # Resolve the ordered model ids for the `review` chain from the committed
      # registry. Stdlib-only, so it runs straight from the checkout with no pip
      # step in front of the review pipeline; a malformed registry fails loudly
      # here (and is caught pre-merge by the model-registry tests + `check`).
      - name: Resolve the reviewer model chain (issue #206)
        id: chain
        env:
          PYTHONPATH: tools/model-registry/src
        run: |
          python3 -m model_registry resolve review --gh-output "$GITHUB_OUTPUT"

# [excerpt: lines 107-292 elided]
  drik-review:
    name: Drik review (fitness for purpose)
    needs: design-changes
    if: >-
      needs.design-changes.outputs.designs_changed == 'true'
      && needs.design-changes.outputs.is_new_round == 'true'
    runs-on: ubuntu-latest
    # Provider fallback chain — see the jane-review job for the rationale and
    # ordering (Z.AI glm-5.2 → glm-5.1 → glm-4.6 → Anthropic claude-opus-4-8;
    # first success wins; a missing key degrades gracefully). Issue #206.
    env:
      HAS_ZAI: ${{ secrets.ZAI_KEY != '' }}
      HAS_ANTHROPIC: ${{ secrets.ANTHROPIC_API_KEY != '' }}
    steps:
      - uses: actions/checkout@v5
        with:
          persist-credentials: false

      - name: /drik-review via Z.AI GLM 5.2
        id: p1
        if: env.HAS_ZAI == 'true'
        continue-on-error: true
        uses: anthropics/claude-code-action@7ff6806c8ebd129a7043b947af920074d3819dc8  # v1
        env:
          ANTHROPIC_BASE_URL: https://api.z.ai/api/anthropic
          ANTHROPIC_AUTH_TOKEN: ${{ secrets.ZAI_KEY }}
          API_TIMEOUT_MS: "3000000"
        with:
          anthropic_api_key: ${{ secrets.ZAI_KEY }}
          github_token: ${{ github.token }}
          claude_args: --permission-mode bypassPermissions --model ${{ needs.design-changes.outputs.model1 }}
          prompt: >-
            /drik-review ${{ github.event.pull_request.number }}

      - name: /drik-review via Z.AI GLM 5.1
        id: p2
        if: env.HAS_ZAI == 'true' && steps.p1.outcome != 'success'
        continue-on-error: true
        uses: anthropics/claude-code-action@7ff6806c8ebd129a7043b947af920074d3819dc8  # v1
        env:
          ANTHROPIC_BASE_URL: https://api.z.ai/api/anthropic
          ANTHROPIC_AUTH_TOKEN: ${{ secrets.ZAI_KEY }}
          API_TIMEOUT_MS: "3000000"
        with:
          anthropic_api_key: ${{ secrets.ZAI_KEY }}
          github_token: ${{ github.token }}
          claude_args: --permission-mode bypassPermissions --model ${{ needs.design-changes.outputs.model2 }}
          prompt: >-
            /drik-review ${{ github.event.pull_request.number }}

      - name: /drik-review via Z.AI GLM 4.6
        id: p3
        if: env.HAS_ZAI == 'true' && steps.p1.outcome != 'success' && steps.p2.outcome != 'success'
        continue-on-error: true
        uses: anthropics/claude-code-action@7ff6806c8ebd129a7043b947af920074d3819dc8  # v1
        env:
          ANTHROPIC_BASE_URL: https://api.z.ai/api/anthropic
          ANTHROPIC_AUTH_TOKEN: ${{ secrets.ZAI_KEY }}
          API_TIMEOUT_MS: "3000000"
        with:
          anthropic_api_key: ${{ secrets.ZAI_KEY }}
          github_token: ${{ github.token }}
          claude_args: --permission-mode bypassPermissions --model ${{ needs.design-changes.outputs.model3 }}
          prompt: >-
            /drik-review ${{ github.event.pull_request.number }}

      - name: /drik-review via Anthropic Opus 4.8
        id: p4
        if: >-
          env.HAS_ANTHROPIC == 'true'
          && steps.p1.outcome != 'success'
          && steps.p2.outcome != 'success'
          && steps.p3.outcome != 'success'
        continue-on-error: true
        uses: anthropics/claude-code-action@7ff6806c8ebd129a7043b947af920074d3819dc8  # v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ github.token }}
          claude_args: --permission-mode bypassPermissions --model ${{ needs.design-changes.outputs.model4 }}
          prompt: >-
            /drik-review ${{ github.event.pull_request.number }}

      - name: No provider key configured
        if: env.HAS_ZAI != 'true' && env.HAS_ANTHROPIC != 'true'
        run: |
          echo "::notice::Neither ZAI_KEY nor ANTHROPIC_API_KEY is set — skipping /drik-review for PR #${{ github.event.pull_request.number }}"

      - name: Every configured provider failed
        if: >-
          (env.HAS_ZAI == 'true' || env.HAS_ANTHROPIC == 'true')
          && steps.p1.outcome != 'success'
          && steps.p2.outcome != 'success'
          && steps.p3.outcome != 'success'
          && steps.p4.outcome != 'success'
        run: |
          echo "::error::/drik-review failed on every configured provider (Z.AI glm-5.2 → glm-5.1 → glm-4.6 → Anthropic claude-opus-4-8). See the failed step logs above."
          exit 1

"""
#: ``.github/models/registry.conf`` at :data:`E2_HEAD` from its first stanza on (the leading
#: comment block elided): ``[chain:review] = glm-5.2, glm-5.1, glm-4.6, claude-opus-4-8``.
REGISTRY_E2 = """[provider:zai]
secret   = ZAI_KEY
base_url = https://api.z.ai/api/anthropic
notes    = Z.AI GLM family via the Anthropic-compatible endpoint. Cheap, fast,
           best-effort for routing a Claude Code skill to a non-Claude model.

[provider:anthropic]
secret   = ANTHROPIC_API_KEY
notes    = Anthropic native endpoint. Frontier quality; the last-resort link.

# ── Models (ordered preference is expressed by the chains, not here) ──────────

[model:glm-5.2]
provider = zai
notes    = First choice for review: newest GLM, cheapest capable option. Good
           enough for the reviewer personas' verification passes at a fraction of
           frontier cost.

[model:glm-5.1]
provider = zai
notes    = Fallback if 5.2 is unavailable — prior GLM, near-equivalent quality.

[model:glm-4.6]
provider = zai
notes    = Last GLM fallback: older, larger context, still capable enough for a
           review when the newer GLMs are down.

[model:claude-opus-4-8]
provider = anthropic
notes    = Frontier final fallback. Highest quality (and cost); reached only when
           every GLM link failed, so a review is never silently lost.

# ── Chains (named, ordered — the thing a job routes to) ───────────────────────

# The reviewer personas (jane / drik / coach) in auto-review.yml. GLM first,
# cheapest-capable to oldest, then Anthropic frontier as the never-lose-a-review
# backstop. Migrating auto-review onto this chain changed nothing that runs today.
[chain:review]
models = glm-5.2, glm-5.1, glm-4.6, claude-opus-4-8
"""
