"""extract — raw@1 → record@1 (validated by contract.check).

Owner: H3. Each test's docstring is its acceptance criterion (docs/provenance.md,
final plan P0/P1a–e). Tests that need another builder's VALUES carry
``@needs``; the rest run now through ``standins`` (neutral stand-ins for H2's
still-unimplemented functions, a no-op once they land).
"""

from __future__ import annotations

import copy
import json
import re

import pytest

from conftest import CONTRACT, FIXTURE_MAIN_SHA, OWNER, OWNER_LOGIN, REPO_NAME, needs, raw_brief, raw_pr
from fakes import FakeCommit, FakeGitReader
from _extract_helpers import (CONTRACT_DELTA, FIXTURE_BRIEFS, FIXTURE_PRS, SOURCE_RANK_AFTER, brief_record,
                              contract_with_delta, delta_state, events_of, fixture_ctx, fixture_git, pr_record,
                              release_record, standins)  # noqa: F401  (standins is a fixture)

from provenance import canonical, contract, digest, episodes, extract, markers, membership, trust

#: The contract's url pattern WITH H3's requested review delta (a no-op once the integrator applies it).
DELTA_CONTRACT = contract_with_delta()
URL_RE = re.compile(DELTA_CONTRACT["types"]["url"]["re"])
EVENT_ID_RE = re.compile(DELTA_CONTRACT["types"]["event_id"]["re"])
SHA = {c: c * 40 for c in "abcdef0123456789"}


@needs(contract.validate, contract.load_contract)
def test_pr_records_validate(standins):
    """extract_pr over every fixture raw PR yields a record that contract.check('record@1:pr') accepts
    (the contract with H3's requested review delta applied — review:<id> events)."""
    ctx = fixture_ctx(fixture_git())
    for n in FIXTURE_PRS:
        assert contract.validate("record@1:pr", pr_record(n, ctx), DELTA_CONTRACT) == [], n
    for b in FIXTURE_BRIEFS:
        assert contract.validate("record@1:brief", brief_record(b, ctx), DELTA_CONTRACT) == [], b
    assert contract.validate("record@1:release", release_record(ctx=ctx), DELTA_CONTRACT) == []
    broken = pr_record(636, ctx)
    broken["events"][0]["extra"] = 1
    assert contract.validate("record@1:pr", broken, DELTA_CONTRACT) != []
    if delta_state(json.loads(CONTRACT.read_text(encoding="utf-8"))) == "pending":
        # The control the delta exists for: the frozen contract refuses a review-sourced event.
        assert contract.validate("record@1:pr", pr_record(397, ctx)) != []


def test_requested_contract_delta_is_exact(standins):
    """The frozen contract is either untouched by H3's review delta (pending) or carries every
    part of it exactly (applied) — never half of it; extraction's url pattern is the delta-applied
    contract's, and every extracted event id full-matches the delta-applied event_id pattern."""
    frozen = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert delta_state(frozen) in ("pending", "applied")
    assert delta_state(DELTA_CONTRACT) == "applied" and delta_state(contract_with_delta()) == "applied"
    rank = DELTA_CONTRACT["enums"]["source_rank"]
    assert rank[rank.index(SOURCE_RANK_AFTER) + 1] == "review" and rank.count("review") == 1
    assert extract._URL_RE.pattern == DELTA_CONTRACT["types"]["url"]["re"]
    assert len(CONTRACT_DELTA) == 2
    half = json.loads(CONTRACT.read_text(encoding="utf-8"))
    half["enums"]["source_rank"] = list(rank)                            # rank applied, the regexes not
    if delta_state(frozen) == "pending":
        assert delta_state(half) == "partial"                             # the check can fail
    ctx = fixture_ctx(fixture_git())
    for n in FIXTURE_PRS:
        for e in pr_record(n, ctx)["events"]:
            assert EVENT_ID_RE.fullmatch(e["id"]), e["id"]


def test_every_event_has_a_constructed_url(standins):
    """NVC-14: every event has a url matching the contract pattern, built from ids (no payload html_url copied)."""
    for n in FIXTURE_PRS:
        rec = pr_record(n)
        assert rec["events"]
        for e in rec["events"]:
            assert URL_RE.fullmatch(e["url"]), (n, e["id"], e["url"])
            assert e["url"].startswith(f"https://github.com/{OWNER}/{REPO_NAME}/")
    for b in FIXTURE_BRIEFS:
        for e in brief_record(b)["events"]:
            assert URL_RE.fullmatch(e["url"]), e
    # Construction, not copying: poisoned html_url / target_url values never reach an event.
    raw = raw_pr(636)
    for run in raw["ci_runs"]:
        run["html_url"] = "https://evil.example/run"
    rec = extract.extract_pr(raw, fixture_ctx())
    gate = events_of(rec, "ci.gate")[0]
    assert gate["url"] == f"https://github.com/{OWNER}/{REPO_NAME}/actions/runs/{gate['id'].split(':')[1]}"
    assert "evil" not in json.dumps(rec)


def test_url_for_refuses_bad_ids():
    """url_for validates every id (negative controls) and builds each documented form."""
    ctx = fixture_ctx()
    base = f"https://github.com/{OWNER}/{REPO_NAME}/"
    assert extract.url_for(ctx, "issue", number=592) == base + "issues/592"
    assert extract.url_for(ctx, "issuecomment", number=592, comment=7) == base + "issues/592#issuecomment-7"
    assert extract.url_for(ctx, "pull", number=636) == base + "pull/636"
    assert extract.url_for(ctx, "pull", number=636, comment=9) == base + "pull/636#issuecomment-9"
    assert extract.url_for(ctx, "review", number=397, review=5) == base + "pull/397#pullrequestreview-5"
    assert extract.url_for(ctx, "pr_commit", number=636, sha=SHA["a"]) == base + f"pull/636/commits/{SHA['a']}"
    assert extract.url_for(ctx, "commit", sha=SHA["b"]) == base + f"commit/{SHA['b']}"
    assert extract.url_for(ctx, "job", run=1, job=2) == base + "actions/runs/1/job/2"
    assert extract.url_for(ctx, "release", tag="v2.0") == base + "releases/tag/v2.0"
    assert (extract.url_for(ctx, "blob", sha=SHA["c"], design="sbc-case", file="PM.md", line=12)
            == base + f"blob/{SHA['c']}/designs/sbc-case/PM.md#L12")
    bad = [("issue", {"number": "592"}), ("issue", {"number": True}), ("issue", {"number": 0}),
           ("commit", {"sha": "a" * 39}), ("commit", {"sha": "A" * 40}), ("nope", {"number": 1}),
           ("issue", {"number": 1, "extra": 2}), ("pr_commit", {"number": 1}),
           ("blob", {"sha": SHA["a"], "design": "Bad", "file": "PM.md", "line": 1}),
           ("blob", {"sha": SHA["a"], "design": "d", "file": "README.md", "line": 1}),
           ("release", {"tag": "v 2"}), ("run", {"run": -1}),
           ("review", {"number": 397}), ("review", {"number": 397, "review": "5"}),
           ("review", {"number": 397, "review": 5, "comment": 6})]
    for kind, ids in bad:
        with pytest.raises(ValueError):
            extract.url_for(ctx, kind, **ids)
    with pytest.raises(ValueError):
        extract.build_url("bad owner", "r", "issue", number=1)


def test_noise_never_becomes_an_event(standins):
    """NVC-12b: no event of a noise class (bugbot limit, qodo paused, preview deploys, CodeRabbit statuses) is stored."""
    raw = raw_pr(636)
    rec = pr_record(636)
    ids = {e["id"] for e in rec["events"]}
    noisy = {f"issuecomment:{c['id']}" for c in raw["issue_comments"]
             if c["body"]["lead"] in ("bugbot_limit", "qodo_paused", "clear_prs")}
    assert noisy and not noisy & ids
    third_party = {f"status:{s['id']}" for v in raw["statuses"].values() for s in v if s["context"] != "reviewer-signoff"}
    assert len(third_party) == 79 and not third_party & ids
    signoff_statuses = {f"status:{s['id']}" for v in raw["statuses"].values() for s in v if s["context"] == "reviewer-signoff"}
    assert signoff_statuses <= ids                       # the control: reviewer-signoff statuses ARE events
    assert [e["id"] for e in events_of(rec, "deploy.production")] == ["deployment:7003033324"]
    assert rec["noise_counts"]["comment.bugbot_limit"] == 21
    assert rec["noise_counts"]["status.coderabbit"] == 33 and rec["noise_counts"]["timeline.deployed"] == 22
    assert set(rec["noise_counts"]) <= set(json.loads(CONTRACT.read_text())["enums"]["noise_key"])
    # Synthetic: a preview deployment and a "no design changes" reviewer-signoff status are noise.
    raw2 = raw_pr(636)
    dep = copy.deepcopy(raw2["deployments"][0])
    dep.update(id=1, environment="Preview")
    raw2["deployments"].append(dep)
    sha = sorted(raw2["statuses"])[0]
    raw2["statuses"][sha].append({"context": "reviewer-signoff", "created_at": "2026-10-05T18:15:15Z",
                                  "creator": "github-actions[bot]", "id": 1,
                                  "description": "no design changes — reviewer sign-off not required",
                                  "state": "success", "target_url": None, "updated_at": None})
    rec2 = extract.extract_pr(raw2, fixture_ctx())
    assert "deployment:1" not in {e["id"] for e in rec2["events"]} and "status:1" not in {e["id"] for e in rec2["events"]}
    assert rec2["noise_counts"]["status.reviewer_signoff.no_design_changes"] == 1


def test_commit_kinds_636(standins):
    """#636: 9a751b26 commit.design; 8 commit.regen; 3 commit.merge_main (4862566b, f4e36eb9, d7bfd77c); the Cursor commits commit.fix."""
    rec = pr_record(636)
    kinds = {e["sha"][:8]: e["kind"] for e in rec["events"] if e["kind"].startswith("commit.")}
    assert len(kinds) == 26
    assert [s for s, k in kinds.items() if k == "commit.design"] == ["9a751b26"]
    assert sum(k == "commit.regen" for k in kinds.values()) == 8
    assert sorted(s for s, k in kinds.items() if k == "commit.merge_main") == ["4862566b", "d7bfd77c", "f4e36eb9"]
    cursor = {c["sha"][:8] for c in raw_pr(636)["commits"]
              if (c["author"] or {}).get("login") == "cursoragent" and len(c["parents"]) == 1}
    assert len(cursor) == 13 and all(kinds[s] == "commit.fix" for s in cursor)
    assert kinds["7c25f888"] == "commit.fix"            # claude (attended), agent trailer
    by_sha = {e["sha"][:8]: e for e in rec["events"] if e["kind"].startswith("commit.")}
    assert by_sha["9a751b26"]["runtime"]["platform"] == "github-actions"
    assert by_sha["9a751b26"]["runtime"]["harness"] == "claude-code-action"
    assert by_sha["7c25f888"]["runtime"]["platform"] == "claude-code"
    assert by_sha["d8574661"]["runtime"]["platform"] == "cursor"
    assert by_sha["f4e36eb9"]["runtime"]["platform"] == "github-web"
    assert by_sha["9a751b26"]["trust"] == "claimed" and by_sha["9a751b26"]["trust_basis"] == "trailer"
    assert by_sha["77cbb164"]["fields"] == {"preview_diff": "absent"}
    assert by_sha["173ef373"]["fields"] == {"preview_diff": "all-noise"}
    assert by_sha["7c25f888"]["signals"]["trailer_session"].startswith("https://claude.ai/code/session_")


def test_human_commits_634(standins):
    """#634: 856831c4, 0443cba6, cb7e8903 are commit.human (owner, no agent trailer)."""
    rec = pr_record(634)
    human = sorted(e["sha"][:8] for e in events_of(rec, "commit.human"))
    assert human == ["0443cba6", "856831c4", "cb7e8903"]
    assert not events_of(rec, "commit.design")         # a Cursor-opened PR has no builder commit


def test_commit_kind_rules():
    """commit_kind's rule order with a negative control per rule."""
    def commit(login="x", parents=1, regen=False, email="e@x", name="n", trailers=()):
        return {"author": {"login": login, "type": "User"}, "parents": [SHA["a"]] * parents, "sha": SHA["b"],
                "commit": {"author": {"date": "2026-01-01T00:00:00Z", "email": email, "name": name},
                           "committer": None, "verified": False, "verification_reason": None,
                           "message": {"subject_regen": regen, "trailers": [dict(t) for t in trailers]}}}
    regen = commit(regen=True, email=episodes.REGEN_AUTHOR, login="github-actions[bot]")
    kind = extract.commit_kind
    assert kind(regen, first_builder_commit=True, owner_login="o") == "commit.regen"
    assert kind(commit(regen=True), first_builder_commit=False, owner_login="o") != "commit.regen"   # wrong author
    assert kind(commit(parents=2), first_builder_commit=True, owner_login="o") == "commit.merge_main"
    assert kind(commit(login="github-actions[bot]"), first_builder_commit=True, owner_login="o") == "commit.design"
    assert kind(commit(name="claude[bot]"), first_builder_commit=True, owner_login="o") == "commit.design"
    assert kind(commit(login="github-actions[bot]"), first_builder_commit=False, owner_login="o") == "commit.fix"
    assert kind(commit(login="o"), first_builder_commit=True, owner_login="o") == "commit.human"
    assert kind(commit(login="O"), first_builder_commit=False, owner_login="o") == "commit.human"
    agent = [{"key": "Co-Authored-By", "value": "Claude Opus 5.5 <noreply@anthropic.com>"}]
    assert kind(commit(login="o", trailers=agent), first_builder_commit=False, owner_login="o") == "commit.fix"
    session = [{"key": "Claude-Session", "value": "https://claude.ai/code/session_abcdefgh"}]
    assert kind(commit(login="o", trailers=session), first_builder_commit=False, owner_login="o") == "commit.fix"
    assert kind(commit(login="cursoragent"), first_builder_commit=False, owner_login="o") == "commit.fix"


def _main(commits: list[FakeCommit], tip: str) -> FakeGitReader:
    return FakeGitReader(commits, refs={"main": tip})


def test_merge_method_fixtures():
    """squash, merge-commit and rebase fixtures (synthetic FakeGitReader main with blame_lines) each give the right merge_method and map a blamed PM.md line to the right PR."""
    root, squash, branch, merge, rebased, tip = (SHA[c] for c in "012345")
    pm = (b"# PM\n\n## Decision log\n\n| Date | Decision | Reason |\n|---|---|---|\n"
          b"| 2026-08-01 | A | r |\n| 2026-08-02 | B | r |\n| 2026-08-03 | C | r |\n")
    blame = [(root, i + 1) for i in range(6)] + [(squash, 7), (branch, 3), (rebased, 9)]
    git = _main([
        FakeCommit(root, [], 1, "init"),
        FakeCommit(squash, [root], 2, "Add A (#10)"),
        FakeCommit(branch, [root], 3, "feature commit"),
        FakeCommit(merge, [squash, branch], 4, "Merge pull request #11 from o/feature"),
        FakeCommit(rebased, [merge], 5, "rewritten by a rebase merge"),
        FakeCommit(tip, [rebased], 6, "Tip (#13)", files={"designs/d/PM.md": pm}, blame={"designs/d/PM.md": blame}),
    ], tip)
    assert extract.merge_method(git, squash, 10) == "squash"
    assert extract.merge_method(git, merge, 11) == "merge"
    assert extract.merge_method(git, rebased, 12) == "rebase"
    assert extract.merge_method(git, squash, 99) == "rebase"     # (#10) is not (#99): no squash claim
    assert extract.merge_method(git, SHA["9"], 10) is None       # not local
    assert extract.merge_method(git, None, 10) is None
    rows = episodes.decision_rows(git, tip, "d", owner=OWNER, repo=REPO_NAME, commit_to_pr={rebased: 12})
    assert [(r["fields"]["added_in_sha"], r["fields"]["line"], r["fields"]["added_in_pr"]) for r in rows] == [
        (squash, 7, 10), (branch, 3, 11), (rebased, 9, 12)]


def test_brief_records(standins):
    """#592: brief.filed (github-actions[bot]), brief.claimed (design_name nuggs-vent-cap), brief.shipped (shipped_pr 636), brief.closed closed_by_pr 636; record.design_name nuggs-vent-cap."""
    rec = brief_record(592)
    assert rec["design_name"] == "nuggs-vent-cap" and rec["prs"] == [636] and rec["state"] == "closed"
    by_kind = {e["kind"]: e for e in rec["events"]}
    assert [e["kind"] for e in rec["events"]] == ["brief.filed", "brief.claimed", "brief.shipped", "brief.closed"]
    assert by_kind["brief.filed"]["signals"]["login"] == "github-actions[bot]"
    assert by_kind["brief.filed"]["fields"] == {"design_name": None}
    assert by_kind["brief.filed"]["trust"] == "login" and by_kind["brief.filed"]["runtime"]["platform"] == "github-actions"
    assert by_kind["brief.claimed"]["fields"] == {"design_name": "nuggs-vent-cap", "settle": False}
    assert by_kind["brief.claimed"]["ts"] == "2026-09-12T00:35:31Z" and by_kind["brief.claimed"]["signals"]["login"] == OWNER_LOGIN
    assert by_kind["brief.shipped"]["fields"]["shipped_pr"] == 636 and by_kind["brief.shipped"]["pr"] == 636
    assert by_kind["brief.closed"]["fields"] == {"closed_by_pr": 636, "design_name": "nuggs-vent-cap",
                                                 "state_reason": "completed"}
    assert by_kind["brief.closed"]["episode"] == "M:636"
    assert {e["episode"] for e in rec["events"][:3]} == {"E0:brief:592"}
    # Negative controls: no frozen merge sha → no closing PR; an edited body → claimed.
    raw = raw_brief(592)
    raw["issue"]["last_edited_at"] = "2026-09-08T00:00:00Z"
    rec2 = extract.extract_brief(raw, fixture_ctx(merge_shas={}))
    closed = events_of(rec2, "brief.closed")[0]
    assert closed["fields"]["closed_by_pr"] is None and closed["episode"] == "E0:brief:592"
    assert events_of(rec2, "brief.filed")[0]["trust"] == "claimed"
    # The last SHIP-LOCK carrying a name wins; with none, the title slug; else null.
    assert brief_record(281)["design_name"] == "nuggs-hopper"
    raw = raw_brief(592)
    for c in raw["comments"]:
        c["body"]["lead"] = None
    assert extract.extract_brief(raw, fixture_ctx())["design_name"] == "nuggs-vent-cap"     # title prefix
    raw["issue"]["title"] = "Design brief: NUGGS vent cap"
    assert extract.extract_brief(raw, fixture_ctx())["design_name"] is None


def test_brief_after_settle_and_delivery(standins):
    """Since #858/#864 an unattended design run claims with settle's constant stub (no name), posts its
    §2 contract as a separate Actions-bot comment (lead ``contract``), and the deliverer announces the
    PR with ``🚢 design-run delivered — …``. The name comes from the trusted contract, never from the
    title once a trusted claim exists; an outsider's lock or contract names nothing; the delivered
    comment is a brief.shipped carrying the PR."""
    bot = {"login": "github-actions[bot]", "type": "Bot"}
    settle = "🚢 SHIP-LOCK — settle claim\n\n<!-- design-run-ship-lock:v1 -->\n"
    contract = "**Design name:** nuggs-vent-cap\n**Brief parts:** cap\n**Style:** none\n\n**Gate contract**\n- [ ] G1\n"
    delivered = ("🚢 design-run delivered — branch and draft PR verified\n\n- branch: `claude/issue-592-x` (`"
                 + "a" * 40 + "`)\n- pull request: https://github.com/shaiss/print-bench/pull/950\n"
                 "- run: https://github.com/shaiss/print-bench/actions/runs/1\n")

    def comment(cid, body, user, at):
        return {"app": None, "body": digest.body_digest(body), "created_at": at, "id": cid, "updated_at": at,
                "user": user}

    def build(*comments, title="Design brief: wall-mounted spool holder"):
        raw = raw_brief(592)
        raw["issue"]["title"] = title
        raw["comments"] = list(comments)
        return extract.extract_brief(raw, fixture_ctx())

    lock = comment(1, settle, bot, "2026-09-12T00:40:00Z")
    named = comment(2, contract, bot, "2026-09-12T00:40:05Z")
    shipped = comment(3, delivered, bot, "2026-09-12T02:10:00Z")
    rec = build(lock, named, shipped)
    assert rec["design_name"] == "nuggs-vent-cap" and 950 in rec["prs"]
    ship = events_of(rec, "brief.shipped")[0]
    assert (ship["pr"], ship["fields"]["shipped_pr"], ship["signals"]["login"]) == (950, 950, "github-actions[bot]")
    assert events_of(rec, "brief.claimed")[0]["fields"] == {"design_name": None, "settle": True}
    # A claimed brief with no trusted contract stays null — never the title's first word.
    assert build(lock)["design_name"] is None
    # An outsider's contract is ignored; so is an outsider's named lock.
    outsider = {"login": "mallory", "type": "User"}
    assert build(lock, comment(4, contract, outsider, "2026-09-12T00:41:00Z"))["design_name"] is None
    forged = comment(5, "🚢 SHIP-LOCK\n\n**Design name:** evil-name\n", outsider, "2026-09-12T00:41:00Z")
    assert build(forged, title="Design brief: NUGGS vent cap")["design_name"] is None
    # The owner's attended SHIP-LOCK still names the design; an unclaimed brief keeps the title slug.
    owner = {"login": OWNER_LOGIN, "type": "User"}
    attended = comment(6, "🚢 SHIP-LOCK — running\n\n**Design name:** `spool-arm`\n", owner, "2026-09-12T00:41:00Z")
    assert build(attended)["design_name"] == "spool-arm"
    assert events_of(build(attended), "brief.claimed")[0]["fields"]["settle"] is False
    assert build()["design_name"] == "wall-mounted"


def test_release_record(standins):
    """The release names the LONGEST design prefixing each asset; one release event on its publication day."""
    rec = release_record()
    assert rec["designs"] == ["alcove-rod-socket"] and rec["published_at"] == "2026-09-20T15:56:02Z"
    (event,) = rec["events"]
    assert event["episode"] == "D:2026-09-20" and event["fields"] == {"assets": 7, "prerelease": False, "tag": "v2.0"}
    ctx = fixture_ctx(design_names=frozenset({"alcove", "alcove-rod-socket"}))
    assert release_record(ctx=ctx)["designs"] == ["alcove-rod-socket"]
    ctx = fixture_ctx(design_names=frozenset({"alcove"}))
    assert release_record(ctx=ctx)["designs"] == ["alcove"]
    ctx = fixture_ctx(design_names=frozenset({"alcove-rod"}))
    assert release_record(ctx=ctx)["designs"] == ["alcove-rod"]        # alcove-rod-socket-… starts "alcove-rod-"
    ctx = fixture_ctx(design_names=frozenset({"alc"}))
    assert release_record(ctx=ctx)["designs"] == []                    # a bare prefix is no design


def test_extractor_has_no_clock(standins):
    """Covered by test_purity; this asserts two extractions of the same raw are byte-identical."""
    ctx = fixture_ctx(fixture_git())
    for n in FIXTURE_PRS:
        assert canonical.dumps(pr_record(n, ctx)) == canonical.dumps(pr_record(n, ctx))
    for b in FIXTURE_BRIEFS:
        assert canonical.dumps(brief_record(b, ctx)) == canonical.dumps(brief_record(b, ctx))


def test_direct_commit_rule(standins):
    """Critique 7, over a synthetic FakeGitReader main: an owner-committed commit touching designs/ with no PR subject → one commit record (C:<sha8>); a '(#N)' squash commit whose PR is NOT frozen → no record; a 'Merge pull request #N' commit → no record; a GitHub-committed (noreply@github.com) rebase-merge commit with an ordinary subject → no record; a commit in a frozen PR's commit list → no record; the real 43030db9 shape ('Merge PR #196: …', committed by GitHub) → no record."""
    owner_mail = "owner@example.com"
    real_196 = "43030db97b7ec0a17c70c1727288efed7130e4d7"
    commits = [
        FakeCommit(SHA["0"], [], 100, "bootstrap", changed=["designs/d/d.scad"], committer_email=owner_mail),
        FakeCommit(SHA["1"], [SHA["0"]], 200, "Add d (#5)", changed=["designs/d/d.scad"], committer_email=owner_mail),
        FakeCommit(SHA["2"], [SHA["1"], SHA["a"]], 300, "Merge pull request #6 from o/x",
                   changed=["designs/d/d.scad"], committer_email=owner_mail),
        FakeCommit(SHA["3"], [SHA["2"]], 400, "rewritten by rebase", changed=["designs/d/d.scad"]),
        FakeCommit(SHA["4"], [SHA["3"]], 500, "pushed straight from the PR branch", changed=["designs/d/d.scad"],
                   committer_email=owner_mail),
        FakeCommit(real_196, [SHA["4"], SHA["b"]], 600,
                   "Merge PR #196: AI shots for nuggs-den (lifestyle) + nuggs-frieda (motion)",
                   changed=["designs/nuggs-den/previews/lifestyle-x.png"]),
        FakeCommit(SHA["5"], [real_196], 700, "tooling only", changed=["scripts/x.sh"], committer_email=owner_mail),
        FakeCommit(SHA["6"], [SHA["5"]], 800, "owner fix", changed=["designs/d/NOTES.md"], committer_email=owner_mail),
        FakeCommit(SHA["a"], [SHA["0"]], 250, "branch", changed=["designs/d/d.scad"], committer_email=owner_mail),
        FakeCommit(SHA["b"], [SHA["0"]], 550, "branch", changed=["designs/d/d.scad"], committer_email=owner_mail),
    ]
    git = FakeGitReader(commits, refs={"main": SHA["6"]})
    ctx = fixture_ctx(git, main_sha=SHA["6"])
    frozen = {SHA["4"]}
    assert extract.is_direct_commit(git, SHA["0"], frozen)
    for sha in (SHA["1"], SHA["2"], SHA["3"], SHA["4"], real_196):
        assert not extract.is_direct_commit(git, sha, frozen), sha
    assert not extract.is_direct_commit(git, SHA["9"], frozen)           # not local: never direct
    assert extract.is_direct_commit(git, SHA["4"], set())                # the frozen-list rule is what excluded it
    records = extract.extract_direct_commits(ctx, frozen)
    assert [r["sha"] for r in records] == [SHA["0"], SHA["6"]]          # 5 touches no designs/
    rec = records[0]
    assert rec["kind"] == "commit" and rec["sha"] == SHA["0"] and rec["committed_at"] == "1970-01-01T00:01:40Z"
    (event,) = rec["events"]
    assert event["episode"] == f"C:{SHA['0'][:8]}" and event["kind"] == "commit.human"
    assert event["url"].endswith(f"/commit/{SHA['0']}") and event["pr"] is None
    assert rec["evidence"]["source"] == "git" and rec["evidence"]["raw"] is None
    assert set(rec["designs"]) == {"d"}


def test_direct_commit_rule_on_real_main():
    """The measurement behind critique 7, over the committed main history: of main's 372 first-parent commits
    since 2026-07-31, six carry no PR subject; the five owner-committed bootstrap commits pass the rule and
    43030db9 ("Merge PR #196: …", committed by GitHub) is refused by the committer clause alone."""
    git = fixture_git()
    first_parent = [s for s, _ in git.first_parent_log("main")]
    no_pr = [s for s in first_parent if episodes.subject_pr(git.subject(s)) is None]
    assert len(first_parent) == 372 and len(no_pr) == 6
    direct = [s for s in no_pr if extract.is_direct_commit(git, s, set())]
    assert len(direct) == 5 and "43030db97b7ec0a17c70c1727288efed7130e4d7" not in direct
    assert git.committer_email("43030db97b7ec0a17c70c1727288efed7130e4d7") == extract.GITHUB_COMMITTER
    assert not any(extract.is_direct_commit(git, s, set()) for s in first_parent if s not in no_pr)


def test_linked_issues_vs_briefs(standins):
    """Critique 24: record.linked_issues = raw.linked_issues; record.briefs = those in ctx.brief_numbers (#636 → linked [592], briefs [592]; with brief_numbers empty → briefs [])."""
    rec = pr_record(636)
    assert rec["linked_issues"] == [592] and rec["briefs"] == [592]
    rec = pr_record(636, fixture_ctx(brief_numbers=frozenset()))
    assert rec["linked_issues"] == [592] and rec["briefs"] == []
    raw = raw_pr(636)
    raw["linked_issues"] = [592, 700]
    rec = extract.extract_pr(raw, fixture_ctx())
    assert rec["linked_issues"] == [592, 700] and rec["briefs"] == [592]


def test_records_carry_no_main_sha(standins):
    """Critique 6: extracting the same raw PR against two different ctx.main_sha values (the second a main commit touching no designs/ file) yields byte-identical records."""
    git = fixture_git()
    later = SHA["e"]
    git.commits[later] = FakeCommit(later, [FIXTURE_MAIN_SHA], 2_000_000_000, "tooling (#999)", changed=["scripts/x.sh"])
    a = fixture_ctx(git, main_sha=FIXTURE_MAIN_SHA)
    b = fixture_ctx(git, main_sha=later)
    for n in FIXTURE_PRS:
        ra, rb = pr_record(n, a), pr_record(n, b)
        assert canonical.dumps(ra) == canonical.dumps(rb)
        assert FIXTURE_MAIN_SHA not in canonical.dumps(ra) or n == 636     # #636's merge IS that sha
    assert pr_record(636, a)["merge_method"] == "squash"
    assert events_of(pr_record(636, a), "pr.merged")[0]["fields"]["main_subject"].endswith("(#636)")


def test_comment_marker_selection(standins):
    """The event comes from the suffix's completion marker, else the last valid event-family line;
    a malformed sign-off or a non-event family yields no event; an edit past the grace sets edited."""
    def comment(lines, suffix=(), lead=None, login="github-actions[bot]", updated="2026-10-11T17:57:29Z"):
        dg = {"digest": "body-digest@1", "footer_ok": bool(suffix), "head_marker": None, "lead": lead,
              "lead_fields": {}, "length": 10, "marker_lines": list(lines), "refs_closes": [],
              "sha256": "0" * 64, "suffix_markers": list(suffix), "suffix_ok": bool(suffix), "table_verdicts": []}
        return {"app": None, "body": dg, "created_at": "2026-10-11T17:57:29Z", "id": 42, "updated_at": updated,
                "user": {"login": login, "type": "Bot"}}
    ok = f"<!-- JANE_SIGNOFF sha={SHA['a']} verdict=pass fuse=none -->"
    drik = f"<!-- DRIK_SIGNOFF sha={SHA['b']} verdict=block fuse=none -->"
    malformed = "<!-- JANE_SIGNOFF sha=abc verdict=pass fuse=none -->"
    ctx = fixture_ctx()

    def ev(c):
        return extract._comment_event(c, 636, ctx)
    assert ev(comment([ok], [ok]))["fields"]["family"] == "JANE_SIGNOFF"
    assert ev(comment([ok, drik]))["sha"] == SHA["b"]                    # last valid line
    assert ev(comment([ok, drik], [ok]))["sha"] == SHA["a"]              # the suffix's completion marker wins
    assert ev(comment([ok, malformed]))["sha"] == SHA["a"]              # a malformed line is skipped
    assert ev(comment([malformed])) is None
    assert ev(comment(["<!-- AUTO_REVIEW_STAMP -->"])) is None
    assert ev(comment([], lead="coach_round")) is not None and ev(comment([], lead="coach_round"))["kind"] == "coach.round"
    assert ev(comment([ok], updated="2026-10-11T17:58:29Z"))["fields"]["edited"] is True
    assert ev(comment([ok], updated="2026-10-11T17:58:28Z"))["fields"]["edited"] is False


def test_trust_is_delegated(monkeypatch, standins):
    """Marker events take trust.comment_tier (marker sha passed); reviewer-signoff statuses take
    trust.status_tier with ctx.auto_review_run_ids and owner_login; ci.gate is verified/receipt."""
    calls, status_calls = [], []

    def tier(**kw):
        calls.append(kw)
        return ("verified", "actions-bot+suffix")

    def stier(status, ids, *, owner_login):
        status_calls.append((status["id"], frozenset(ids), owner_login))
        return ("verified", "actions-status+receipt")
    monkeypatch.setattr(trust, "comment_tier", tier)
    monkeypatch.setattr(trust, "status_tier", stier)
    rec = pr_record(636, fixture_ctx(auto_review_run_ids=frozenset({38161046420})))
    signoff = next(e for e in rec["events"] if e["id"] == "issuecomment:6111973609")
    assert signoff["trust"] == "verified"
    call = next(c for c in calls if c["marker_sha"] == "9a751b26e18dac7f9c8c9464fd37a2e4c6c63f2c")
    assert call["kind"] == "review.signoff" and call["login"] == "github-actions[bot]" and call["owner_login"] == OWNER_LOGIN
    assert len(calls) == 25 + 6                                          # sign-offs + triages, nothing else
    assert status_calls and all(ids == frozenset({38161046420}) and who == OWNER_LOGIN for _, ids, who in status_calls)
    stale = next(e for e in rec["events"] if e["id"] == "status:56095459342")
    assert stale["runtime"]["run_id"] == 38161046420 and stale["runtime"]["workflow"] == "auto-review.yml"
    assert stale["fields"] == {"reason": "stale", "state": "failure", "verdict": "BLOCK"}
    other = next(e for e in rec["events"] if e["id"] == "status:56096060766")
    assert other["runtime"]["run_id"] is None                            # not an auto-review receipt run
    assert {e["trust"] for e in events_of(rec, "ci.gate")} == {"verified"}


def test_signoff_reason_table():
    """status.reviewer_signoff reasons for reviewer-signoff.sh's sentences (first clause), else other."""
    table = {"Jane and Drik signed off on this design": "signed-off",
             "Jane and Drik signed off and acknowledged the fuse warn": "fuse-acknowledged",
             "Jane has not signed off; Drik sign-off is stale (reviewed 7c25f888; design changed since)": "not-signed",
             "Drik sign-off is stale (reviewed 9a751b26; design changed since)": "stale",
             "Jane blocked (verdict=block)": "blocked",
             "Drik has not acknowledged the fusecheck STRONG WARN": "fuse-unacknowledged",
             "overridden by the signoff-override label (a maintainer accepted the risk)": "overridden",
             "Jane sign-off is malformed": "other", "": "other", None: "other"}
    for text, reason in table.items():
        assert extract.signoff_reason(text) == reason, text


def test_runtime_and_signals_shapes():
    """empty_runtime refuses an unknown platform; every join field starts null with basis none."""
    rt = extract.empty_runtime("cursor")
    assert rt["platform"] == "cursor" and rt["model_basis"] == "none"
    assert all(v is None for k, v in rt.items() if k not in ("platform", "model_basis"))
    with pytest.raises(ValueError):
        extract.empty_runtime("gitlab")
    assert extract.empty_signals()["regen_identity"] is False and extract.empty_signals()["trailer_coauthors"] == []


def test_pr_record_shape(standins):
    """Rounds, threads, incomplete and the evidence pointer of the fixture PRs."""
    rec = pr_record(636)
    assert rec["state"] == "merged" and rec["merge_commit_sha"] == FIXTURE_MAIN_SHA
    assert rec["threads"] == {"resolved": 8, "total": 8} and rec["incomplete"] == []
    assert rec["evidence"] == {"raw": "raw/pr/636.json.gz", "raw_sha256": canonical.content_sha256(raw_pr(636)),
                               "receipts": [], "revision": 1, "source": "evidence"}
    assert rec["extractor"] == extract.EXTRACTOR_VERSION and rec["pr"] == 636
    assert all(e["episode"] for e in rec["events"])                       # placed at extraction
    assert rec["events"] == sorted(rec["events"], key=canonical.event_sort_key)
    raw = raw_pr(636)
    raw["revision"] = 2
    raw["incomplete"] = ["threads-unavailable"]
    rec2 = extract.extract_pr(raw, fixture_ctx())
    assert rec2["evidence"]["raw"] == "raw/pr/636.r2.json.gz" and rec2["threads"] is None
    opened = events_of(rec, "pr.opened")[0]
    assert opened["fields"] == {"draft": True}                           # opened as draft: ready_for_review follows


def test_review_bodies_yield_signoffs(standins):
    """A PR review body is selected like an issue comment (the M3 era posted Jane with `gh pr
    review`): #397's 14 Jane review sign-offs and #371's one become review.signoff events with id
    review:<id>, ts submitted_at, the marker's sha (not the review's commit_id), url
    pull/<n>#pullrequestreview-<id>, never edited; reviews with no event marker stay noise."""
    for n, want in ((371, 1), (397, 14)):
        raw = raw_pr(n)
        marked = {r["id"]: r for r in raw["reviews"] if any("_SIGNOFF" in m for m in r["body"]["marker_lines"])}
        assert len(marked) == want
        rec = pr_record(n)
        got = {e["id"]: e for e in events_of(rec, "review.signoff") if e["id"].startswith("review:")}
        assert set(got) == {f"review:{i}" for i in marked}
        for ident, review in marked.items():
            e = got[f"review:{ident}"]
            sha = markers.parse_signoff(markers.parse_marker(review["body"]["marker_lines"][-1]))["sha"]
            assert (e["ts"], e["sha"], e["fields"]["family"], e["fields"]["edited"]) == (
                review["submitted_at"], sha, "JANE_SIGNOFF", False)
            assert e["url"] == f"https://github.com/{OWNER}/{REPO_NAME}/pull/{n}#pullrequestreview-{ident}"
            assert e["signals"]["login"] == "github-actions[bot]" and e["signals"]["app"] is None
            assert e["runtime"]["platform"] == "github-actions" and e["episode"].startswith(f"R:{n}:")
        noise = rec["noise_counts"]
        assert noise["review.bot"] == 1                                      # the Copilot review only
        assert noise["review.empty_wrapper"] == {371: 4, 397: 29}[n]
    odd = next(e for e in events_of(pr_record(397), "review.signoff") if e["id"] == "review:5009969812")
    assert odd["sha"].startswith("8ebc3443")                             # the marker's sha, not commit_id 99fdc73d
    # A pending review (no submitted_at) yields nothing and is counted.
    raw = raw_pr(371)
    for r in raw["reviews"]:
        if r["id"] == 5003707361:
            r["submitted_at"] = None
    rec = extract.extract_pr(raw, fixture_ctx())
    assert "review:5003707361" not in {e["id"] for e in rec["events"]} and rec["noise_counts"]["review.bot"] == 2
    # A PM_TRIAGE marker in a review body is a triage.verdict the same way (synthetic: no fixture has one).
    triage = {"body": {"digest": "body-digest@1", "footer_ok": False, "head_marker": None, "lead": None,
                       "lead_fields": {}, "length": 40, "marker_lines": [f"<!-- PM_TRIAGE design=sbc-case sha={SHA['a']} -->"],
                       "refs_closes": [], "sha256": "0" * 64, "suffix_markers": [], "suffix_ok": False,
                       "table_verdicts": ["act-now", "decline"]},
              "commit_id": SHA["b"], "id": 77, "state": "COMMENTED", "submitted_at": "2026-08-24T01:00:00Z",
              "user": {"login": "github-actions[bot]", "type": "Bot"}}
    ev = extract._review_event(triage, 371, fixture_ctx())
    assert (ev["id"], ev["kind"], ev["sha"], ev["fields"]["designs"], ev["fields"]["act_now"]) == (
        "review:77", "triage.verdict", SHA["a"], ["sbc-case"], 1)


def test_review_trust_is_capped_below_verified(monkeypatch, standins):
    """reviewer-posted.sh reads only issue comments, so a review body is never verified: with
    comment_tier answering verified for everything, the issue-comment sign-offs stay verified and
    every review-sourced one is claimed/marker:no-suffix (incl. #397's review whose digest ends
    with the MCP suffix); a non-verified tier passes through unchanged."""
    calls = []

    def tier(**kw):
        calls.append(kw)
        return ("verified", "actions-bot+suffix")
    monkeypatch.setattr(trust, "comment_tier", tier)
    signoffs = events_of(pr_record(397), "review.signoff")
    assert {e["trust"] for e in signoffs if e["id"].startswith("issuecomment:")} == {"verified"}
    capped = [e for e in signoffs if e["id"].startswith("review:")]
    assert len(capped) == 14 and {(e["trust"], e["trust_basis"]) for e in capped} == {("claimed", "marker:no-suffix")}
    suffixed = next(r for r in raw_pr(397)["reviews"] if r["body"]["suffix_ok"])
    assert next(e for e in capped if e["id"] == f"review:{suffixed['id']}")["trust"] == "claimed"
    review_call = next(c for c in calls if c["created_at"] == suffixed["submitted_at"])
    assert review_call["updated_at"] is None and review_call["kind"] == "review.signoff"
    monkeypatch.setattr(trust, "comment_tier", lambda **kw: ("claimed", "marker:owner-token"))
    assert {e["trust_basis"] for e in events_of(pr_record(397), "review.signoff")} == {"marker:owner-token"}


def _signoff_statuses(raw: dict, run: int) -> dict:
    """Two reviewer-signoff statuses naming the same auto-review run: one by the Actions bot (id
    11), one created from the owner's token (id 12)."""
    sha = sorted(raw["statuses"])[0]
    base = {"context": "reviewer-signoff", "created_at": "2026-10-05T18:15:15Z",
            "description": "Jane blocked (verdict=block)", "state": "failure",
            "target_url": f"https://github.com/{OWNER}/{REPO_NAME}/actions/runs/{run}", "updated_at": None}
    raw["statuses"][sha] = raw["statuses"][sha] + [dict(base, id=11, creator="github-actions[bot]"),
                                                   dict(base, id=12, creator=OWNER_LOGIN)]
    return raw


def test_status_runtime_join_follows_the_trust_rule(monkeypatch, standins):
    """The reviewer-signoff status runtime join (run_id + auto-review.yml) is made only when
    status_tier verified the status as an Actions-bot status on an auto-review receipt run: an
    owner-created status whose target_url names the same receipt run gets no runtime."""
    run = 38161046420

    def faithful(status, ids, *, owner_login):                           # status_tier's rule, by creator
        ok = status.get("creator") in ("github-actions[bot]", "github-actions")
        return ("verified", "actions-status+receipt") if ok and run in ids else ("login", "login")
    monkeypatch.setattr(trust, "status_tier", faithful)
    rec = extract.extract_pr(_signoff_statuses(raw_pr(636), run), fixture_ctx(auto_review_run_ids=frozenset({run})))
    bot, owner = (next(e for e in rec["events"] if e["id"] == f"status:{i}") for i in (11, 12))
    assert (bot["runtime"]["run_id"], bot["runtime"]["workflow"], bot["trust"]) == (run, "auto-review.yml", "verified")
    assert (owner["runtime"]["run_id"], owner["runtime"]["workflow"], owner["trust"]) == (None, None, "login")
    rec = extract.extract_pr(_signoff_statuses(raw_pr(636), run), fixture_ctx(auto_review_run_ids=frozenset()))
    assert next(e for e in rec["events"] if e["id"] == "status:11")["runtime"]["run_id"] is None


@needs(trust.status_tier)
def test_status_runtime_join_with_the_real_tier(standins):
    """The same split through H2's real status_tier: an owner-created status on an auto-review run is not joined."""
    run = 38161046420
    rec = extract.extract_pr(_signoff_statuses(raw_pr(636), run), fixture_ctx(auto_review_run_ids=frozenset({run})))
    bot, owner = (next(e for e in rec["events"] if e["id"] == f"status:{i}") for i in (11, 12))
    assert bot["runtime"]["run_id"] == run and bot["trust"] == "verified"
    assert owner["runtime"]["run_id"] is None and owner["trust"] != "verified"


def test_platform_rules():
    """The platform rule order of the module docstring, with the claude[bot] cases: its comments
    are claude-code-action inside Actions (github-actions, harness claude-code-action), a user-login
    comment via the claude app is claude-code, an unknown bot is unknown."""
    p = extract._platform
    assert p(login="github-actions[bot]") == p(login="github-actions") == "github-actions"
    assert p(login="claude[bot]") == "github-actions"
    assert p(login=OWNER_LOGIN, app="claude") == "claude-code"
    assert p(login="claude") == "claude-code"
    assert p(login="cursor[bot]") == "cursor" and p(login="coderabbitai[bot]") == "coderabbit"
    assert p(login="someone[bot]") == "unknown" and p(login=OWNER_LOGIN) == "unknown"
    assert p(login="x", author_name="claude[bot]") == "github-actions"          # a builder commit by name
    assert p(login="x", committer_login="web-flow") == "github-web"
    comment = {"app": "claude", "body": {"digest": "body-digest@1", "footer_ok": False, "head_marker": None,
                                         "lead": "coach_round", "lead_fields": {"round": 2, "round_sub": None},
                                         "length": 10, "marker_lines": [], "refs_closes": [], "sha256": "0" * 64,
                                         "suffix_markers": [], "suffix_ok": False, "table_verdicts": []},
               "created_at": "2026-10-11T17:57:29Z", "id": 42, "updated_at": None,
               "user": {"login": "claude[bot]", "type": "Bot"}}
    ev = extract._comment_event(comment, 636, fixture_ctx())
    assert (ev["runtime"]["platform"], ev["runtime"]["harness"]) == ("github-actions", "claude-code-action")
    comment["user"] = {"login": OWNER_LOGIN, "type": "User"}
    ev = extract._comment_event(comment, 636, fixture_ctx())
    assert (ev["runtime"]["platform"], ev["runtime"]["harness"]) == ("claude-code", "claude-code")
    comment["user"], comment["app"] = {"login": "github-actions[bot]", "type": "Bot"}, None
    ev = extract._comment_event(comment, 636, fixture_ctx())
    assert (ev["runtime"]["platform"], ev["runtime"]["harness"]) == ("github-actions", None)
