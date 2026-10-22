"""serving — the join (P1c). Receipts and code bases from the committed fixtures; synthetic FakeCodeBasis/FakeGitReader for the edge cases.

Owner: H4. Each test's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items 9, 14,
15, 26). Probe events are built straight from the raw fixtures
(``_serving_helpers``), never through the extractor, so the join is tested on
any contract-shaped record.
"""

from __future__ import annotations

import copy
import functools
import gzip
import json
import re

import pytest

import _serving_helpers as H
from conftest import GOLDEN, OWNER, OWNER_LOGIN, REPO_NAME, FIXTURES, contract, needs, raw_brief, raw_pr, \
    receipt, receipt_paths, receipts
from fakes import FakeCodeBasis, FakeCommit, FakeGitReader
from provenance import contract as contract_mod, serving, steps
from provenance.codebasis import GitCodeBasis
from provenance.protocols import Basis
from provenance.serving import ReceiptIndex, annotate_record, receipt_events, resolve, run_claims, ts_epoch

A720 = "a720a6bddcd1c2d9ecc6bd5ae2c8b161f3e95e9f"
M0987 = "0987cd19e462779505d8e19c8b7375325fdcd3a5"
F4E3 = "f4e36eb91e2d2c8306a55e262575b417d0a27a20"
SCOUT_RUN, DESIGN_RUN, BURN_RUN, PRE326_RUN, REVIEW_RUN = 34112970240, 34661448637, 34654859877, 31364447108, 38161046420
BRANCH = "claude/issue-592-nuggs-vent-cap"
REGISTRY = ".github/models/registry.conf"


@functools.lru_cache(maxsize=None)
def _receipts() -> tuple:
    return tuple(receipts())


def index(*extra) -> ReceiptIndex:
    return ReceiptIndex(list(_receipts()) + list(extra))


def _636_merge_pairs() -> tuple[list[FakeCommit], list[tuple[str, str]]]:
    return H.pr_merge_inputs(_receipts(), BRANCH)


def cb636(**kw) -> GitCodeBasis:
    return H.pr_codebasis(_receipts(), BRANCH, **kw)


def rec636(*events) -> dict:
    return H.pr_from_raw(raw_pr(636), list(events))


def brief592() -> dict:
    return H.brief_from_raw(raw_brief(592))


def ev(record: dict, eid: str) -> dict:
    return next(e for e in record["events"] if e["id"] == eid)


def annotate(record, *, idx=None, cb=None, briefs=None):
    idx = idx or index()
    claims = run_claims(briefs if briefs is not None else [brief592()], idx, owner_login=OWNER_LOGIN)
    return annotate_record(record, idx, cb or cb636(), owner_login=OWNER_LOGIN, claims=claims)


# ---------------------------------------------------------------------------
# The acceptance values (NVC-2..5).

def test_nvc2_scout_window():
    """NVC-2: brief #592 filed 10:49:36Z by github-actions[bot] sits in exactly one product-scout window (run 34112970240, link 1 10:44:13–10:51:20) → role product-scout, model glm-5.2 (registry@a720a6bd chain scout), trust window."""
    idx = index()
    b = brief592()
    filed = ev(b, "issue:592:filed")
    assert filed["ts"] == "2026-09-07T10:49:36Z"
    cands = serving.containing_windows(idx, ts=filed["ts"], roles=serving.KIND_ROLES["brief.filed"],
                                       author_login="github-actions[bot]", owner_login=OWNER_LOGIN)
    assert [(w.run_id, w.started, w.completed) for w in cands] == [(SCOUT_RUN, "2026-09-07T10:44:13Z", "2026-09-07T10:51:20Z")]
    out = annotate(b, idx=idx)
    e = ev(out, "issue:592:filed")
    rt = e["runtime"]
    assert (rt["role"], rt["run_id"], rt["workflow"], rt["chain"], rt["chain_link"], rt["model"]) == \
        ("product-scout", SCOUT_RUN, "product-scout.yml", "scout", 1, "glm-5.2")
    assert rt["model_basis"] == "step-window+registry@head(a720a6bd)" and rt["links_not_served"] == 0
    assert (e["trust"], e["trust_basis"]) == ("window", f"window:run {SCOUT_RUN}")
    assert "receipts/2026/09/07/34112970240.a1.json.gz" in out["evidence"]["receipts"]
    # Negative control: the same brief filed by the owner is no scout's (identities are the Actions bot).
    owner_filed = copy.deepcopy(b)
    ev(owner_filed, "issue:592:filed")["signals"]["login"] = OWNER_LOGIN
    assert ev(annotate(owner_filed, idx=idx), "issue:592:filed")["trust"] == "login"


def test_nvc3_design_run_link3():
    """NVC-3: commit 9a751b26 at 02:06:03Z → design-run run 34661448637 attempt 2, link 3, glm-4.6, links_not_served 2, basis step-window+registry@head(a720a6bd) (bot-authored: plain containment)."""
    c = H.commit_from_raw(raw_pr(636), "9a751b26")
    assert (c["ts"], c["signals"]["login"]) == ("2026-09-12T02:06:03Z", "github-actions[bot]")
    e = ev(annotate(rec636(c)), c["id"])
    rt = e["runtime"]
    assert (rt["role"], rt["run_id"], rt["attempt"], rt["chain"], rt["chain_link"], rt["links_not_served"], rt["model"]) == \
        ("design-run", DESIGN_RUN, 2, "design-run", 3, 2, "glm-4.6")
    assert rt["model_basis"] == "step-window+registry@head(a720a6bd)"
    assert (rt["provider"], rt["platform"], rt["harness"]) == ("zai", "github-actions", "claude-code-action")
    assert (rt["job"], rt["job_id"]) == ("Pick one design-brief and run /design-run", 103466431808)
    assert e["trust"] == "window"


def test_nvc4_ship_lock_link1():
    """The SHIP-LOCK at 00:35:31Z (owner PAT) → link 1, glm-5.2, trust window — it is the only OWNER brief.claimed in run 34661448637's windows, so run_claims gives {34661448637: 592}."""
    idx = index()
    b = brief592()
    lock = ev(b, "issuecomment:5642215092")
    assert (lock["kind"], lock["ts"], lock["signals"]["login"]) == ("brief.claimed", "2026-09-12T00:35:31Z", OWNER_LOGIN)
    # Two ship-routine windows contain it (the owner re-ran both at 00:34) — the key decides.
    cands = serving.containing_windows(idx, ts=lock["ts"], roles=serving.KIND_ROLES["brief.claimed"],
                                       author_login=OWNER_LOGIN, owner_login=OWNER_LOGIN)
    assert sorted(w.run_id for w in cands) == [BURN_RUN, DESIGN_RUN]
    assert run_claims([b], idx, owner_login=OWNER_LOGIN) == {DESIGN_RUN: 592}
    out = annotate(b, idx=idx)
    e = ev(out, "issuecomment:5642215092")
    rt = e["runtime"]
    assert (rt["run_id"], rt["attempt"], rt["chain_link"], rt["model"], e["trust"]) == (DESIGN_RUN, 2, 1, "glm-5.2", "window")
    shipped = ev(out, "issuecomment:5642757801")         # brief.shipped 02:07:44, the claim's link 3
    assert (shipped["runtime"]["chain_link"], shipped["runtime"]["model"], shipped["trust"]) == (3, "glm-4.6", "window")
    # Negative control: were #592 ALSO an autonomy-ok issue, the backlog burn could have claimed
    # it in its overlapping window — the SHIP-LOCK is then ambiguous and nothing is guessed.
    both = copy.deepcopy(b)
    both["labels"] = ["autonomy-ok", "design-brief"]
    assert run_claims([both], idx, owner_login=OWNER_LOGIN) == {BURN_RUN: 592, DESIGN_RUN: 592}
    amb = ev(annotate(both, idx=idx, briefs=[both]), "issuecomment:5642215092")
    assert (amb["trust"], amb["runtime"]["model"], amb["runtime"]["model_basis"]) == ("login", None, "ambiguous")


def test_owner_artifacts_need_the_claimed_issue():
    """Critique 15 (negatives): inside a design-run window that claimed #592, an OWNER pr.opened on a non-claude branch stays login; an OWNER pr.opened on claude/issue-700-x stays login; an OWNER brief.declined on #700 stays login; a window holding two OWNER SHIP-LOCKs claims nothing (both stay login); the OWNER pr.opened of #636 (claude/issue-592-…) becomes window."""
    idx = index()
    ts = "2026-09-12T01:30:00Z"                           # inside run 34661448637 a2 link 3, no other window
    assert [w.run_id for w in serving.containing_windows(idx, ts=ts, roles=serving.SHIP_ROLES,
                                                         author_login=OWNER_LOGIN, owner_login=OWNER_LOGIN)] == [DESIGN_RUN]

    def opened(head_ref, n):
        return H.pr_record(n, [H.event(f"pr:{n}:opened", "pr.opened", ts, login=OWNER_LOGIN, pr=n, fields={"draft": False})],
                           head_ref=head_ref, created_at=ts, closed_at=None)

    for head_ref, n in (("feature/owner-attended", 901), ("claude/issue-700-x", 902)):
        e = annotate(opened(head_ref, n), idx=idx)["events"][0]
        assert (e["trust"], e["runtime"]["run_id"]) == ("login", None), head_ref
    declined = H.brief_record(700, [H.event("issuecomment:9000000001", "brief.declined", ts, login=OWNER_LOGIN, issue=700,
                                            fields={"design_name": None})])
    assert annotate(declined, idx=idx)["events"][0]["trust"] == "login"
    # Positive control: the same owner decline on the CLAIMED issue is the run's.
    on592 = H.brief_record(592, [H.event("issuecomment:9000000002", "brief.declined", ts, login=OWNER_LOGIN, issue=592,
                                         fields={"design_name": None})])
    assert annotate(on592, idx=idx)["events"][0]["trust"] == "window"
    # Two OWNER SHIP-LOCKs in one run's windows: the run claims nothing.
    locks = [H.brief_record(n, [H.event(f"issuecomment:{9000000010 + n}", "brief.claimed", t, login=OWNER_LOGIN, issue=n,
                                        fields={"design_name": None})])
             for n, t in ((701, "2026-09-12T01:00:00Z"), (702, "2026-09-12T01:40:00Z"))]
    assert run_claims(locks, idx, owner_login=OWNER_LOGIN) == {}
    for b in locks:
        assert annotate(b, idx=idx, briefs=locks)["events"][0]["trust"] == "login"
    # The #636 open (02:07:11, link 3) on claude/issue-592-… is the run's.
    e = ev(annotate(rec636(H.pr_opened(raw_pr(636))), idx=idx), "pr:636:opened")
    assert (e["trust"], e["runtime"]["run_id"], e["runtime"]["chain_link"], e["runtime"]["model"]) == \
        ("window", DESIGN_RUN, 3, "glm-4.6")


def test_two_locks_on_one_issue_are_one_claim():
    """Review round 2, issue 4: brief #281's SHIP-LOCKs 5315682248 (11:54:09Z) and 5316408268 (13:02:28Z) both lie in design-run run 32026482297's link window (11:52:11–13:02:53) — one issue, so one claim, and PR #316's OWNER open at 13:02:05Z on claude/issue-281-nuggs-hopper becomes the run's (trust window). Locks on two DISTINCT issues in one run's windows still claim nothing."""
    idx = index()
    b = H.brief_from_raw(raw_brief(281))
    locks = [e for e in b["events"] if e["kind"] == "brief.claimed"
             and serving.containing_windows(idx, ts=e["ts"], roles=serving.SHIP_ROLES, author_login=OWNER_LOGIN,
                                            owner_login=OWNER_LOGIN)[0].run_id == 32026482297]
    assert [(e["id"], e["ts"]) for e in locks] == [("issuecomment:5315682248", "2026-08-17T11:54:09Z"),
                                                   ("issuecomment:5316408268", "2026-08-17T13:02:28Z")]
    claims = run_claims([b], idx, owner_login=OWNER_LOGIN)
    assert claims[32026482297] == 281
    raw = raw_pr(316)
    assert (raw["pull"]["head"]["ref"], raw["pull"]["created_at"]) == ("claude/issue-281-nuggs-hopper", "2026-08-17T13:02:05Z")
    e = annotate_record(H.pr_from_raw(raw, [H.pr_opened(raw)]), idx, H.fixture_codebasis(), owner_login=OWNER_LOGIN,
                        claims=claims)["events"][0]
    assert (e["trust"], e["trust_basis"], e["runtime"]["run_id"]) == ("window", "window:run 32026482297", 32026482297)
    for lock in locks:
        assert ev(annotate(b, idx=idx, briefs=[b]), lock["id"])["runtime"]["run_id"] == 32026482297
    # Negative control: a second issue's lock in the same window → the run claims nothing.
    other = H.brief_record(282, [H.event("issuecomment:9000000282", "brief.claimed", "2026-08-17T12:30:00Z",
                                         login=OWNER_LOGIN, issue=282, fields={"design_name": None})])
    assert 32026482297 not in run_claims([b, other], idx, owner_login=OWNER_LOGIN)


def test_actions_bot_ship_artifacts_need_the_key():
    """§2b since #858/#864/#868: the Actions bot writes for BOTH ship routines (the burn agent's SHIP-LOCK, design-run's post-agent settle job, the deliverers' delivered comment, claude-code-action's commits), so a bot artifact inside a ship window is keyed like an owner one. A design-run settle lock on a design-brief issue inside a backlog-burn window stays login (it used to become the burn's, trust window); the burn's own bot lock on an issue carrying autonomy-ok claims it; a delivered comment on an issue the run did not claim stays login; a bot commit joins a run with no claim only on a branch that routine can select."""
    bot = "github-actions[bot]"
    burn = H.shifted_receipt(receipt(BURN_RUN), run_id=34654859999, seconds=6 * 3600)
    idx = index(burn)
    t_burn = "2026-09-12T06:37:00Z"                      # inside the shifted burn link 1 only
    assert [(w.role, w.run_id) for w in serving.containing_windows(
        idx, ts=t_burn, roles=serving.SHIP_ROLES, author_login=bot, owner_login=OWNER_LOGIN)] == \
        [("backlog-burn", 34654859999)]

    def lock(n, labels):
        return H.brief_record(n, [H.event(f"issuecomment:{9100000000 + n}", "brief.claimed", t_burn, login=bot,
                                          issue=n, fields={"design_name": None})], labels=labels)

    settle = lock(710, ("design-brief",))
    assert run_claims([settle], idx, owner_login=OWNER_LOGIN) == {}
    e = annotate(settle, idx=idx, briefs=[settle])["events"][0]
    assert (e["trust"], e["runtime"]["run_id"], e["runtime"]["model_basis"]) == ("login", None, "none")
    # Positive control: the burn's own bot lock on an issue carrying its opt-in label claims it.
    own = lock(711, ("autonomy-ok", "design-brief"))
    assert run_claims([own], idx, owner_login=OWNER_LOGIN) == {34654859999: 711}
    e = annotate(own, idx=idx, briefs=[own])["events"][0]
    assert (e["trust"], e["runtime"]["run_id"]) == ("window", 34654859999)

    # A delivered comment (bot brief.shipped) inside design-run run 34661448637, which claimed #592.
    t_dr = "2026-09-12T01:30:00Z"

    def delivered(n):
        return H.brief_record(n, [H.event(f"issuecomment:{9100001000 + n}", "brief.shipped", t_dr, login=bot, issue=n,
                                          fields={"design_name": None, "shipped_pr": 950})])

    assert annotate(delivered(712), idx=idx)["events"][0]["trust"] == "login"
    on592 = annotate(delivered(592), idx=idx)["events"][0]
    assert (on592["trust"], on592["runtime"]["run_id"]) == ("window", DESIGN_RUN)

    # Bot commits: a run with a claim needs claude/issue-<claim>; a run with none needs a branch its
    # routine can select (a captured brief for design-run, anything else for the burn).
    def commit_pr(ts, n, briefs):
        rec = H.pr_record(960 + n % 10, [H.event(f"commit:{n:040d}", "commit.design", ts, login=bot, sha=f"{n:040d}")],
                          head_ref=f"claude/issue-{n}-x", created_at=ts, closed_at=None)
        rec["briefs"] = list(briefs)
        return rec

    def joined(rec, *, claims_from):
        out = annotate(rec, idx=idx, briefs=claims_from)["events"][0]
        return out["trust"], out["runtime"]["run_id"]

    assert joined(commit_pr(t_dr, 713, [713]), claims_from=None) == ("login", None)       # run claimed #592
    assert joined(commit_pr(t_dr, 713, [713]), claims_from=[]) == ("window", DESIGN_RUN)  # no claim, a brief
    assert joined(commit_pr(t_dr, 714, []), claims_from=[]) == ("login", None)            # no claim, not a brief
    assert joined(commit_pr(t_burn, 715, [715]), claims_from=[]) == ("login", None)       # design brief in a burn window
    assert joined(commit_pr(t_burn, 716, []), claims_from=[]) == ("window", 34654859999)  # the burn's own issue
    # claude[bot] keeps plain containment.
    plain = commit_pr(t_burn, 715, [715])
    plain["events"][0]["signals"]["login"] = "claude[bot]"
    assert joined(plain, claims_from=[]) == ("window", 34654859999)


def test_nvc5_reviewers_glm53():
    """NVC-5: the 12 verified sign-offs on #636 resolve to glm-5.3 via chain review link 1 at the merge-tree basis."""
    so = H.signoffs_from_raw(raw_pr(636))
    out = annotate(rec636(*so))
    verified = [e for e in out["events"] if e["trust"] == "verified"]
    assert len(verified) == 12
    assert {(e["runtime"]["chain"], e["runtime"]["chain_link"], e["runtime"]["model"]) for e in verified} == \
        {("review", 1, "glm-5.3")}
    assert all(re.fullmatch(r"step-window\+registry@merge\(0987cd19\+[0-9a-f]{8}\)", e["runtime"]["model_basis"])
               for e in verified)
    assert {e["runtime"]["role"] for e in verified} == {"jane", "drik"}
    assert all(e["trust_basis"] == "actions-bot+suffix" for e in verified)      # tier kept
    # The 13 owner-token sign-offs gain nothing (NVC-6's other half).
    owner = [e for e in out["events"] if e["signals"]["login"] == OWNER_LOGIN]
    assert len(owner) == 13 and all(e["runtime"]["model"] is None and e["trust"] == "claimed" for e in owner)


@functools.lru_cache(maxsize=None)
def _snapshot() -> tuple:
    """Every receipt of the committed #843 snapshot (the real, concurrent run set; ~3 s)."""
    return tuple(H.snapshot_receipts())


#: #636 sign-off -> (the PR's own run whose window holds it, other PRs' runs whose windows also do).
CONCURRENT = {"issuecomment:6113266518": (38170476665, (38165474200,)),
              "issuecomment:6114336402": (38177985892, (38174908441, 38177914382))}


def test_reviewer_windows_are_scoped_to_the_prs_runs():
    """Review round 2, issue 1: auto-review runs of other PRs overlap #636's. Run 38165474200 (PR #674) holds Jane sign-off 6113266518 beside #636's own run 38170476665; runs 38177914382 (#737) and 38174908441 (#674) hold 6114336402 beside 38177985892. Scoped to the record's PR's runs (serving.window_belongs: pull_requests holds the PR, or head_branch == head_ref within the PR's window — #636's runs carry an empty pull_requests), NVC-5 stays 12/12 glm-5.3 and job.reviewer posted stays Jane 6 / Drik 4; with the PR's own receipt missing, the other PR's run is never the answer."""
    wanted = {r for _, rs in CONCURRENT.values() for r in rs}
    other = [r for r in _snapshot() if r["run"]["id"] in wanted]
    assert {r["run"]["id"]: r["run"]["pull_requests"] for r in other} == \
        {38165474200: [674], 38174908441: [674], 38177914382: [737]}
    idx = index(*other)
    rec = rec636()
    so = H.signoffs_from_raw(raw_pr(636))
    for cid, (own, others) in CONCURRENT.items():
        e = next(x for x in so if x["id"] == cid)
        cands = serving.containing_windows(idx, ts=e["ts"], roles=frozenset({"jane"}),
                                           author_login=e["signals"]["login"], owner_login=OWNER_LOGIN)
        # The hazard: time + role + identity alone puts the sign-off in two or three runs' windows.
        assert sorted(w.run_id for w in cands) == sorted((own, *others)), cid
        assert serving.pick_window(cands, e["ts"]) == ("ambiguous", None)
        assert [w.run_id for w in cands if serving.window_belongs(w, rec)] == [own]
        assert receipt(own)["run"]["pull_requests"] == [] and receipt(own)["run"]["head_branch"] == BRANCH
    out = annotate(rec636(*so), idx=idx)
    verified = [e for e in out["events"] if e["trust"] == "verified"]
    assert len(verified) == 12 and {(e["runtime"]["chain"], e["runtime"]["model"]) for e in verified} == {("review", "glm-5.3")}
    for cid, (own, _) in CONCURRENT.items():
        assert ev(out, cid)["runtime"]["run_id"] == own
    jobs = receipt_events(out, idx, cb636(), owner=OWNER, repo=REPO_NAME)
    assert {r: sum(1 for j in jobs if j["runtime"]["role"] == r and j["fields"]["posted"]) for r in ("jane", "drik")} == \
        {"jane": 6, "drik": 4}
    assert not any(j["runtime"]["run_id"] in (38165474200, 38174908441, 38177914382) for j in jobs)
    assert not any(str(r) in p for r in (38165474200, 38174908441, 38177914382) for p in out["evidence"]["receipts"])
    # Negative control: the PR's own receipt missing → the other PR's run is the ONLY candidate by
    # time and identity, and the sign-off is still not attributed to it (no window, never a guess).
    cid = "issuecomment:6113266518"
    gone = ReceiptIndex([r for r in list(_receipts()) + other if r["run"]["id"] != 38170476665])
    e = next(x for x in so if x["id"] == cid)
    assert [w.run_id for w in serving.containing_windows(gone, ts=e["ts"], roles=frozenset({"jane"}),
                                                         author_login=e["signals"]["login"],
                                                         owner_login=OWNER_LOGIN)] == [38165474200]
    lone = ev(annotate(rec636(e), idx=gone), cid)
    assert (lone["runtime"]["run_id"], lone["runtime"]["model"], lone["runtime"]["model_basis"], lone["trust"]) == \
        (None, None, "none", "verified")
    # A reviewer window is never a candidate on a non-PR record; a ship-role window is not PR-scoped.
    jane_w = next(w for w in idx.windows() if w.run_id == 38170476665 and w.role == "jane")
    assert serving.window_belongs(jane_w, rec) and not serving.window_belongs(jane_w, brief592())
    assert not serving.window_belongs(jane_w, H.pr_record(674, [], head_ref="claude/issue-667-sand-bath",
                                                          created_at="2026-10-01T00:00:00Z", closed_at=None))
    ship_w = H.window_of(idx, DESIGN_RUN, "Run via Z.AI (GLM, chain link 1)", attempt=2)
    assert serving.window_belongs(ship_w, brief592()) and serving.window_belongs(ship_w, rec)
    # A branch-name-only match outside the PR's [created_at, closed_at] is another PR on a reused branch.
    reused = dict(rec636(), created_at="2026-10-12T00:00:00Z", closed_at=None)
    assert not serving.window_belongs(jane_w, reused)


def test_reviewer_join_on_the_whole_snapshot():
    """Review round 2, issue 1, on EVERY receipt of the #843 snapshot (3,738, the real concurrency): #636's 12 verified sign-offs → glm-5.3 at chain review link 1 (NVC-5); #634's Actions-bot sign-offs join Jane 3 + Drik 2, the audit golden's calibration-cube join_stats; all 14 of #397's Actions-bot Drik sign-offs join (one window each; the model there is the code basis's business, not the window's). The snapshot-built receipts of the 166 fixture runs ARE the fixture receipts."""
    snap = _snapshot()
    assert len(snap) == 3738
    by_id = {r["run"]["id"]: r for r in snap}
    assert all(serving.canonical.dumps(by_id[r["run"]["id"]]) == serving.canonical.dumps(r) for r in _receipts())
    idx = ReceiptIndex(snap)
    out = annotate(rec636(*H.signoffs_from_raw(raw_pr(636))), idx=idx)
    verified = [e for e in out["events"] if e["trust"] == "verified"]
    assert len(verified) == 12
    assert {(e["runtime"]["chain"], e["runtime"]["chain_link"], e["runtime"]["model"]) for e in verified} == {("review", 1, "glm-5.3")}
    jobs = receipt_events(out, idx, cb636(), owner=OWNER, repo=REPO_NAME)
    assert {r: sum(1 for j in jobs if j["runtime"]["role"] == r and j["fields"]["posted"]) for r in ("jane", "drik")} == \
        {"jane": 6, "drik": 4}
    stats = json.load(gzip.open(GOLDEN / "join_stats.json.gz"))["calibration-cube"]
    for n, want in ((634, {"jane": stats["jane:joined"], "drik": stats["drik:joined"]}), (397, {"drik": 14})):
        raw = raw_pr(n)
        cb = H.pr_codebasis(snap, raw["pull"]["head"]["ref"])
        bot = [e for e in H.signoffs_from_raw(raw) if e["signals"]["login"] == "github-actions[bot]"]
        got = annotate_record(H.pr_from_raw(raw, bot), idx, cb, owner_login=OWNER_LOGIN, claims={})["events"]
        joined = {}
        for e in got:
            assert e["runtime"]["run_id"] is not None, (n, e["id"])
            assert by_id[e["runtime"]["run_id"]]["run"]["head_branch"] == raw["pull"]["head"]["ref"]
            joined[e["runtime"]["role"]] = joined.get(e["runtime"]["role"], 0) + 1
        assert joined == want, n
    assert (stats["jane:artifacts"], stats["drik:artifacts"]) == (3, 2)


def _review_registry_git(registry: bytes) -> GitCodeBasis:
    files = {REGISTRY: registry,
             ".github/workflows/auto-review.yml": H.fixture_commits()[M0987].files[".github/workflows/auto-review.yml"]}
    extra, pairs = _636_merge_pairs()
    git = H.fixture_git(extra=extra, auto_merge=pairs)
    git.merges[(M0987, F4E3)] = (files, set())
    return GitCodeBasis(git)


def test_merge_tree_basis_when_head_registry_differs():
    """A fixture PR whose head registry differs from main's at created_at resolves to the merge tree's model, basis step-window+registry@merge(<main8>+<head8>)."""
    main_reg = H.fixture_commits()[M0987].files[REGISTRY]
    head_reg = main_reg.replace(b"[chain:review]\nmodels = glm-5.3, glm-5.2,", b"[chain:review]\nmodels = glm-5.2, glm-5.3,")
    assert head_reg != main_reg
    jane = next(e for e in H.signoffs_from_raw(raw_pr(636)) if e["id"] == "issuecomment:6111970233")
    e = ev(annotate(rec636(jane), cb=_review_registry_git(head_reg)), jane["id"])
    assert (e["runtime"]["model"], e["runtime"]["model_basis"]) == ("glm-5.2", "step-window+registry@merge(0987cd19+f4e36eb9)")
    # Negative control: main's own registry at that instant names glm-5.3.
    assert GitCodeBasis(H.fixture_git()).chain_models(Basis("main", None, M0987), "review")[0] == "glm-5.3"


def test_registry_change_within_15_minutes_is_ambiguous():
    """A main registry change 5 minutes before created_at → model null, basis ambiguous."""
    jane = next(e for e in H.signoffs_from_raw(raw_pr(636)) if e["id"] == "issuecomment:6111970233")
    created = ts_epoch(receipt(REVIEW_RUN)["run"]["created_at"])          # 17:46:29

    def with_change(seconds_before: int) -> dict:
        x = "c" * 40
        base = H.fixture_commits()[M0987]
        change = FakeCommit(x, [M0987], created - seconds_before, files=dict(base.files), changed=[REGISTRY])
        extra, pairs = _636_merge_pairs()
        git = H.fixture_git(extra=extra + [change], tip=x,
                            auto_merge=[(x if m == M0987 else m, h) for m, h in pairs])
        return ev(annotate(rec636(jane), cb=GitCodeBasis(git)), jane["id"])

    e = with_change(300)
    assert (e["runtime"]["model"], e["runtime"]["model_basis"]) == (None, "ambiguous")
    assert (e["trust"], e["runtime"]["run_id"], e["runtime"]["chain_link"]) == ("verified", REVIEW_RUN, 1)
    # Negative control: the same change 20 minutes earlier is outside the window.
    far = with_change(1200)
    assert (far["runtime"]["model"], far["runtime"]["model_basis"]) == ("glm-5.3", "step-window+registry@merge(cccccccc+f4e36eb9)")


ORACLE_WF = b"""name: Oracle
on:
  pull_request:
jobs:
  oracle:
    name: Oracle review (opposite-vendor, blind)
    steps:
      # model_registry resolve not-a-literal (a comment never counts)
      - name: Resolve the oracle-anthropic chain
        run: python3 -m model_registry resolve oracle-anthropic --gh-output "$GITHUB_OUTPUT"
      - name: Resolve the oracle-glm chain
        run: python3 -m model_registry resolve oracle-glm --gh-output "$GITHUB_OUTPUT"
"""


def _oracle_registry(anthropic_head: str) -> bytes:
    return (f"[provider:anthropic]\nsecret = ANTHROPIC_API_KEY\n\n[provider:zai]\nsecret = ZAI_KEY\n\n"
            f"[model:claude-opus-4-8]\nprovider = anthropic\nnotes = n\n\n[model:claude-sonnet-5]\nprovider = anthropic\nnotes = n\n\n"
            f"[model:glm-5.3]\nprovider = zai\nnotes = n\n\n"
            f"[chain:oracle-anthropic]\nmodels = {anthropic_head}\n\n[chain:oracle-glm]\nmodels = glm-5.3\n").encode()


def _oracle_receipt(*, checkout_delay: int, glm: bool = False) -> dict:
    """Oracle run 32548387083 (created 03:13:28) with its checkout step and every later step moved
    ``checkout_delay`` seconds later (a busy queue); ``glm`` swaps which vendor's links ran."""
    r = copy.deepcopy(receipt(32548387083))
    job = r["jobs"][0]
    moving = False
    for s in job["steps"]:
        moving = moving or s["name"].startswith("Run actions/checkout")
        if moving:
            for k in ("started_at", "completed_at"):
                s[k] = serving.ts_str(ts_epoch(s[k]) + checkout_delay)
        p = steps.parse_step_name(s["name"])
        if glm and p and p.lead == "Oracle":
            s["conclusion"] = "success" if (p.provider == "zai" and p.link == 1) else "skipped"
            if p.provider == "zai" and p.link == 1:
                s["started_at"], s["completed_at"] = serving.ts_str(ts_epoch(r["run"]["created_at"]) + checkout_delay + 30), \
                    serving.ts_str(ts_epoch(r["run"]["created_at"]) + checkout_delay + 90)
    return r


ORACLE_HEAD = receipt(32548387083)["run"]["head_sha"]


def _oracle_git(*, change_at: int, head_wf: bytes = ORACLE_WF) -> FakeGitReader:
    """main m0 (T−2h, oracle-anthropic = claude-opus-4-8), m1 (T+change_at, claude-sonnet-5), m2
    (T+4h); the run's PR head carries ``head_wf`` as its oracle.yml — the merge tree's text."""
    t = ts_epoch("2026-08-22T03:13:28Z")
    m0, m1, m2 = "1" * 40, "2" * 40, "3" * 40
    wf = ".github/workflows/oracle.yml"
    merged = {wf: head_wf}
    return FakeGitReader([
        FakeCommit(m0, [], t - 7200, files={REGISTRY: _oracle_registry("claude-opus-4-8"), wf: ORACLE_WF}, changed=[REGISTRY, wf]),
        FakeCommit(m1, [m0], t + change_at, files={REGISTRY: _oracle_registry("claude-sonnet-5"), wf: ORACLE_WF}, changed=[REGISTRY]),
        FakeCommit(m2, [m1], t + 4 * 3600, files={REGISTRY: _oracle_registry("claude-sonnet-5"), wf: ORACLE_WF}, changed=["README.md"]),
        FakeCommit(ORACLE_HEAD, [m0], t - 60, files={wf: head_wf}, changed=[wf] if head_wf != ORACLE_WF else []),
    ], refs={H.MAIN_REF: m2}, merges={(m, ORACLE_HEAD): (dict(merged), set()) for m in (m0, m1, m2)})


def _oracle_review(r: dict) -> dict:
    """An oracle.review by the Actions bot in the middle of the receipt's first Oracle step that ran."""
    w = next(w for w in ReceiptIndex([r]).windows() if w.role == "oracle")
    ts = serving.ts_str((ts_epoch(w.started) + ts_epoch(w.completed)) // 2)
    n = 999
    return H.pr_record(n, [H.event("issuecomment:9100000001", "oracle.review", ts, login="github-actions[bot]",
                                   trust="verified", trust_basis="actions-bot+head-marker", pr=n,
                                   fields={"edited": False})],
                       head_ref=r["run"]["head_branch"], created_at="2026-08-22T03:00:00Z", closed_at=None)


def test_oracle_resolves_against_main_at_checkout():
    """Critique 26: an oracle pull_request run created at T whose checkout step started at T+40 min resolves against main@(T+40 min) — a registry change landing between T and T+40 min is the one it read; a registry change within 15 min either side of the checkout step → ambiguous; its two resolve literals — the PR merge commit's text, not main's (review round 2, issue 5) — are discriminated by the step provider group."""
    r = _oracle_receipt(checkout_delay=40 * 60)
    idx = ReceiptIndex([r])
    cb = GitCodeBasis(_oracle_git(change_at=20 * 60))       # registry change at T+20 min
    e = annotate_record(_oracle_review(r), idx, cb, owner_login=OWNER_LOGIN, claims={})["events"][0]
    assert (e["runtime"]["chain"], e["runtime"]["model"], e["runtime"]["model_basis"]) == \
        ("oracle-anthropic", "claude-sonnet-5", "step-window+registry@main(22222222)")
    # Negative control: at created_at (T) main still named claude-opus-4-8.
    assert cb.chain_models(Basis("main", None, "1" * 40), "oracle-anthropic") == ("claude-opus-4-8",)
    # A registry change 5 minutes before the checkout step → ambiguous.
    near = GitCodeBasis(_oracle_git(change_at=35 * 60))
    e = annotate_record(_oracle_review(r), idx, near, owner_login=OWNER_LOGIN, claims={})["events"][0]
    assert (e["runtime"]["model"], e["runtime"]["model_basis"]) == (None, "ambiguous")
    # The GLM provider group picks the other literal.
    g = _oracle_receipt(checkout_delay=40 * 60, glm=True)
    e = annotate_record(_oracle_review(g), ReceiptIndex([g]), cb, owner_login=OWNER_LOGIN, claims={})["events"][0]
    assert (e["runtime"]["chain"], e["runtime"]["model"], e["runtime"]["provider"]) == ("oracle-glm", "glm-5.3", "zai")
    # A pick that is not among the workflow's literals is ambiguous, never a guess.
    w = next(w for w in ReceiptIndex([r]).windows() if w.role == "oracle")
    bad = FakeCodeBasis(default=Basis("main", None, "1" * 40), files={("main", None, "1" * 40, ".github/workflows/oracle.yml"):
                        ORACLE_WF.replace(b"oracle-anthropic", b"oracle-x").replace(b"oracle-glm", b"oracle-y")})
    assert resolve(w, bad).model_basis == "ambiguous"
    # Review round 2, issue 5: the literals are the PR MERGE COMMIT's text, not main's. A PR whose
    # oracle.yml renames the anthropic chain is judged against its own literals (the pick
    # oracle-anthropic is no longer among them → ambiguous), though main's text would have named it.
    renamed = ORACLE_WF.replace(b"resolve oracle-anthropic", b"resolve oracle-claude")
    reader = _oracle_git(change_at=20 * 60, head_wf=renamed)
    pr_cb = GitCodeBasis(reader)
    e = annotate_record(_oracle_review(r), idx, pr_cb, owner_login=OWNER_LOGIN, claims={})["events"][0]
    assert (e["runtime"]["model"], e["runtime"]["model_basis"]) == (None, "ambiguous")
    b = pr_cb.basis_for("oracle.yml", "pull_request", ORACLE_HEAD, r["run"]["created_at"], checkout=w.checkout)
    assert serving.chain_literals(pr_cb.file_at(b, ".github/workflows/oracle.yml").decode()) == ["oracle-claude", "oracle-glm"]
    assert serving.chain_literals(reader.show("2" * 40, ".github/workflows/oracle.yml").decode()) == \
        ["oracle-anthropic", "oracle-glm"]
    # ...and with the head gone (force-pushed away) the text is unknown: none + unavailable, never main's text.
    gone = _oracle_git(change_at=20 * 60)
    del gone.commits[ORACLE_HEAD]
    out = annotate_record(_oracle_review(r), idx, GitCodeBasis(gone), owner_login=OWNER_LOGIN, claims={})
    assert (out["events"][0]["runtime"]["model_basis"], out["incomplete"]) == \
        ("none", [f"codebasis-unavailable:{ORACLE_HEAD[:8]}"])


def test_pre_326_inline_pin():
    """Run 31364447108 → step 'Run via Anthropic (Claude)' → inline pin claude-opus-4-8 from design-run.yml@dae83d67, chain_link null, basis provider-step+inline-pin@dae83d67."""
    idx = index()
    w = H.window_of(idx, PRE326_RUN, "Run via Anthropic (Claude)")
    assert (w.step.era, w.role, w.run_head_sha[:8]) == ("E1", "design-run", "dae83d67")
    j = resolve(w, GitCodeBasis(H.fixture_git()))
    assert (j.model, j.chain, j.chain_link, j.links_not_served, j.model_basis, j.provider) == \
        ("claude-opus-4-8", None, None, None, "provider-step+inline-pin@dae83d67", "anthropic")
    # The run's Z.AI step was skipped (no window); were it the one that ran, its own pin applies —
    # not the "--model line" in the comment above it.
    zai = serving.StepWindow(**{**w.__dict__, "step_name": "Run via Z.AI (GLM)",
                                "step": steps.parse_step_name("Run via Z.AI (GLM)")})
    assert resolve(zai, GitCodeBasis(H.fixture_git())).model == "glm-5.2"
    # Negative control: no such step in that job → no pin, basis none.
    nope = serving.StepWindow(**{**w.__dict__, "job_name": "Explain a disarmed run"})
    assert (resolve(nope, GitCodeBasis(H.fixture_git())).model_basis) == "none"


E2_RUN = 31939632623


def _e2_git(registry: str = H.REGISTRY_E2) -> tuple[FakeGitReader, str]:
    """Main (2 h before run 31939632623's created_at) and the run's head 14745efd both carry
    auto-review.yml + registry.conf as at 14745efd; the merge tree of the two is the same files."""
    created = ts_epoch("2026-08-16T09:39:49Z")
    main = "5" * 40
    files = {REGISTRY: registry.encode(), ".github/workflows/auto-review.yml": H.AUTO_REVIEW_E2.encode()}
    git = FakeGitReader([FakeCommit(main, [], created - 7200, files=dict(files), changed=sorted(files)),
                         FakeCommit(H.E2_HEAD, [main], created - 6, files=dict(files))],
                        refs={H.MAIN_REF: main}, merges={(main, H.E2_HEAD): (dict(files), set())})
    return git, main


def test_e2_registry_output_model():
    """Review round 2, issue 2: run 31939632623 (2026-08-16, head 14745efd) ran '/drik-review via Z.AI GLM 5.2', whose --model is ${{ needs.design-changes.outputs.model1 }} — no literal pin. registry_pin traces model1 → design-changes' `model1: ${{ steps.chain.outputs.link1_model }}` → step `chain`'s `model_registry resolve review`, so the model is review[0] = glm-5.2 (registry@14745efd: glm-5.2, glm-5.1, glm-4.6, claude-opus-4-8), chain_link 1, basis step-window+registry@merge(…); the job.reviewer gets job-link+registry@merge(…)."""
    r = next(x for x in _snapshot() if x["run"]["id"] == E2_RUN)
    assert (r["run"]["head_sha"], r["run"]["event"], r["workflow"]) == (H.E2_HEAD, "pull_request", "auto-review.yml")
    idx = ReceiptIndex([r])
    w = next(x for x in idx.windows() if x.role == "drik")
    assert (w.step_name, w.step.era, w.job_name) == ("/drik-review via Z.AI GLM 5.2", "E2", "Drik review (fitness for purpose)")
    text = H.AUTO_REVIEW_E2
    assert serving.inline_pin(text, w.job_name, w.step_name) is None          # the pre-fix answer: no model
    for label, link in (("Z.AI GLM 5.2", 1), ("Z.AI GLM 5.1", 2), ("Z.AI GLM 4.6", 3), ("Anthropic Opus 4.8", 4)):
        assert serving.registry_pin(text, w.job_name, f"/drik-review via {label}") == ("review", link)
    git, main = _e2_git()
    j = resolve(w, GitCodeBasis(git))
    assert (j.model, j.chain, j.chain_link, j.links_not_served, j.provider, j.model_basis) == \
        ("glm-5.2", "review", 1, 0, "zai", f"step-window+registry@merge({main[:8]}+14745efd)")
    # The Opus link, had it been the one that ran: review[3], links 1–3 did not serve.
    opus = serving.StepWindow(**{**w.__dict__, "step_name": "/drik-review via Anthropic Opus 4.8",
                                 "step": steps.parse_step_name("/drik-review via Anthropic Opus 4.8")})
    j4 = resolve(opus, GitCodeBasis(git))
    assert (j4.model, j4.chain_link, j4.links_not_served, j4.provider) == ("claude-opus-4-8", 4, 3, "anthropic")
    # Job level: the Drik job's last link that ran is the 5.2 step.
    rec = H.pr_record(231, [], head_ref=r["run"]["head_branch"], created_at="2026-08-16T00:00:00Z", closed_at=None)
    drik = next(e for e in receipt_events(rec, idx, GitCodeBasis(git), owner=OWNER, repo=REPO_NAME)
                if e["runtime"]["role"] == "drik")
    assert (drik["runtime"]["model"], drik["runtime"]["chain_link"], drik["runtime"]["model_basis"]) == \
        ("glm-5.2", 1, f"job-link+registry@merge({main[:8]}+14745efd)")
    # Cross-check: a registry whose review chain starts with glm-5.1 contradicts the '5.2' label —
    # the basis (or the name) is not what ran, so nothing is claimed.
    swapped = H.REGISTRY_E2.replace("models = glm-5.2, glm-5.1,", "models = glm-5.1, glm-5.2,")
    assert swapped != H.REGISTRY_E2
    js = resolve(w, GitCodeBasis(_e2_git(swapped)[0]))
    assert (js.model, js.model_basis, js.chain, js.chain_link) == (None, "ambiguous", "review", 1)
    # Negative control: without a registry at the basis the model is unreadable (basis none, counted).
    files = {".github/workflows/auto-review.yml": H.AUTO_REVIEW_E2.encode()}
    bare = FakeGitReader([FakeCommit(main, [], ts_epoch("2026-08-16T07:39:49Z"), files=dict(files), changed=sorted(files)),
                          FakeCommit(H.E2_HEAD, [main], ts_epoch("2026-08-16T09:39:43Z"), files=dict(files))],
                         refs={H.MAIN_REF: main}, merges={(main, H.E2_HEAD): (dict(files), set())})
    jb = resolve(w, GitCodeBasis(bare))
    assert (jb.model, jb.model_basis, jb.chain, jb.unavailable) == (None, "none", "review", H.E2_HEAD)


@pytest.mark.parametrize("label,want", [
    ("/jane-review via Z.AI GLM 5.2", "glm-5.2"), ("/pm triage via Z.AI GLM 4.6", "glm-4.6"),
    ("/drik-review via Anthropic Opus 4.8", "claude-opus-4-8"), ("/design-coach via Anthropic Sonnet 5", "claude-sonnet-5"),
    ("/jane-review via Anthropic Haiku 4.5", "claude-haiku-4-5"),
    ("/jane-review via Anthropic 5", None),                         # a bare number names no Anthropic model
    ("/jane-review via Z.AI GLM (chain link 1)", None),             # E3: no label
    ("Run via Z.AI (GLM)", None),                                   # E1: no label
])
def test_e2_label_model(label, want):
    assert serving.e2_label_model(steps.parse_step_name(label)) == want


REG_WF = """name: R
jobs:
  resolve:
    name: Resolve
    outputs:
      model1: ${{ steps.chain.outputs.link1_model }}
      model2: ${{ steps.chain.outputs.link2_model }}
      flat: ${{ vars.MODEL }}
      other: ${{ steps.twice.outputs.link1_model }}
    steps:
      - name: Resolve the chain
        id: chain
        run: |
          # model_registry resolve not-this-one
          python3 -m model_registry resolve review --gh-output "$GITHUB_OUTPUT"
      - name: Two literals
        id: twice
        run: python3 -m model_registry resolve a && python3 -m model_registry resolve b
  use:
    name: Use
    steps:
      - name: Needs output
        run: claude --model ${{ needs.resolve.outputs.model2 }}
      - name: Step output
        id: local
        run: |
          python3 -m model_registry resolve scout
          claude --model ${{ steps.local.outputs.link3_model }}
      - name: Flat output
        run: claude --model ${{ needs.resolve.outputs.flat }}
      - name: Vars
        run: claude --model ${{ vars.MODEL }}
      - name: Two literals
        run: claude --model ${{ needs.resolve.outputs.other }}
      - name: Unknown job
        run: claude --model ${{ needs.nope.outputs.model1 }}
      - name: Unknown step id
        run: claude --model ${{ steps.nope.outputs.link1_model }}
      - name: Commented
        # claude --model ${{ needs.resolve.outputs.model1 }}
        run: claude
"""


@pytest.mark.parametrize("step,want", [
    ("Needs output", ("review", 2)),          # needs.<job>.outputs.<out> → that job's link output; comment skipped
    ("Step output", ("scout", 3)),            # steps.<id>.outputs.link<N>_model in the same job
    ("Flat output", None),                    # an output that is not a chain link
    ("Vars", None),
    ("Two literals", None),                   # the resolve step must carry exactly one literal
    ("Unknown job", None),
    ("Unknown step id", None),
    ("Commented", None),
])
def test_registry_pin_scanner(step, want):
    assert serving.registry_pin(REG_WF, "Use", step) == want


def test_registry_pin_agrees_with_the_e3_step_names_in_the_fixture_workflows():
    """On every committed fixture workflow blob, each E3 agent step's --model traces to (chain, link) with link == the step name's chain link and chain == the chain resolve() picks from the workflow's literals — the scanner reads the real files the way the step names say."""
    seen = 0
    for sha, paths in H.codebasis_index().items():
        for path in paths:
            if not path.startswith(".github/workflows/"):
                continue
            text = H.codebasis_blob(sha, path).decode()
            wfname = path.rsplit("/", 1)[1]
            wf = serving._Workflow(text)
            for key, name, k, e in wf.jobs:
                for i, nxt in wf._steps((k, e)):
                    p = steps.parse_step_name(serving._item_name(wf.struct, i, nxt) or "")
                    if p is None or p.era != "E3":
                        continue
                    stepname = serving._item_name(wf.struct, i, nxt)
                    lits = serving.chain_literals(text)
                    chain = lits[0] if len(lits) == 1 else serving.CHAIN_DISCRIMINATORS.get((wfname, p.lead, p.provider))
                    assert serving.registry_pin(text, name or key, stepname) == (chain, p.link), (sha[:8], path, stepname)
                    seen += 1
    assert seen >= 60


def test_overlapping_windows_are_ambiguous():
    """Overlapping design-run and backlog-burn windows → model null, basis ambiguous, trust not upgraded."""
    c = H.commit_from_raw(raw_pr(636), "9a751b26")
    c["signals"]["login"] = "claude[bot]"
    burn = H.shifted_receipt(receipt(DESIGN_RUN), run_id=34661448999, seconds=60, workflow="backlog-burn.yml")
    out = annotate(rec636(c), idx=index(burn))
    e = ev(out, c["id"])
    assert (e["runtime"]["model"], e["runtime"]["model_basis"], e["runtime"]["run_id"]) == (None, "ambiguous", None)
    assert (e["trust"], e["trust_basis"]) == ("login", "login")
    assert out["evidence"]["receipts"] == sorted(out["evidence"]["receipts"])
    assert not any("34661448999" in p or "34661448637" in p for p in out["evidence"]["receipts"])
    # Negative control: without the overlapping run the same commit is the design run's.
    assert ev(annotate(rec636(c)), c["id"])["trust"] == "window"


def test_boundary_second_of_one_job():
    """Two links of the SAME job share a boundary second: strictly inside the earlier one → that link; on the boundary → ambiguous."""
    idx = index()
    link1 = H.window_of(idx, DESIGN_RUN, "Run via Z.AI (GLM, chain link 1)", attempt=2)
    link2 = H.window_of(idx, DESIGN_RUN, "Run via Z.AI (GLM, chain link 2)", attempt=2)
    assert link1.completed == link2.started == "2026-09-12T00:38:50Z"
    assert serving.pick_window([link1, link2], "2026-09-12T00:38:50Z") == ("ambiguous", None)
    assert serving.pick_window([link1], "2026-09-12T00:38:49Z") == ("one", link1)
    assert serving.pick_window([], "2026-09-12T00:38:49Z") == ("none", None)
    other_job = serving.StepWindow(**{**link2.__dict__, "job_id": 1})
    assert serving.pick_window([link1, other_job], "2026-09-12T00:38:50Z")[0] == "ambiguous"


def test_missing_commit_is_none_not_a_fetch():
    """Critique 9: a run whose head sha is absent from the FakeGitReader (force-pushed away) → model null, basis none, the record gains codebasis-unavailable:<sha8>; the same input twice gives identical output (GitReader has no fetch method to call)."""
    c = H.commit_from_raw(raw_pr(636), "9a751b26")

    def run():
        cb = GitCodeBasis(H.fixture_git(drop=[A720]))
        assert not any(hasattr(cb.git, m) for m in ("fetch", "fetch_all", "ensure_commit"))
        return annotate(rec636(c), cb=cb)

    first, second = run(), run()
    assert first == second
    e = ev(first, c["id"])
    assert (e["runtime"]["model"], e["runtime"]["model_basis"], e["runtime"]["run_id"]) == (None, "none", DESIGN_RUN)
    assert e["trust"] == "window"              # the containment still holds; only the model is unknown
    assert "codebasis-unavailable:a720a6bd" in first["incomplete"]
    assert first["incomplete"] == sorted(set(first["incomplete"]))
    # A brief record (no job-level joins to muddy it): the SHIP-LOCK's run head is gone → the entry;
    # negative control: with the head present the record carries none.
    gone = annotate(brief592(), cb=GitCodeBasis(H.fixture_git(drop=[A720])))
    assert gone["incomplete"] == ["codebasis-unavailable:a720a6bd"]
    assert ev(gone, "issuecomment:5642215092")["runtime"]["model_basis"] == "none"
    assert annotate(brief592())["incomplete"] == []


def test_non_null_model_has_basis():
    """Every event with a non-null model carries a basis other than none."""
    raw = raw_pr(636)
    so = H.signoffs_from_raw(raw)
    commits = [H.commit_from_raw(raw, s) for s in ("9a751b26", "7c25f888", "4862566b")]
    idx = index()
    out = annotate(rec636(*so, *commits, H.pr_opened(raw)), idx=idx)
    out["events"] += receipt_events(out, idx, cb636(), owner=OWNER, repo=REPO_NAME)
    b = annotate(brief592(), idx=idx)
    pattern = contract()["types"]["runtime"]["fields"]["model_basis"]["re"]
    seen = 0
    for e in out["events"] + b["events"]:
        rt = e["runtime"]
        assert re.fullmatch(pattern, rt["model_basis"]), rt["model_basis"]
        if rt["model"] is not None:
            seen += 1
            assert rt["model_basis"] not in ("none", "ambiguous"), e["id"]
        if e["trust"] == "window":
            assert re.fullmatch(r"window:run [0-9]+", e["trust_basis"]) and rt["run_id"] is not None
    assert seen >= 20


def test_owner_token_signoff_never_window(monkeypatch):
    """A DRIK_SIGNOFF by the owner inside a Drik job window stays claimed (ROLE_IDENTITIES: reviewers post as the Actions bot)."""
    so = next(e for e in H.signoffs_from_raw(raw_pr(636)) if e["signals"]["login"] == OWNER_LOGIN)
    so = copy.deepcopy(so)
    so["ts"] = "2026-10-11T18:00:00Z"                       # inside run 38161046420's Drik link 2
    assert so["trust_basis"] == "marker:owner-token"
    e = annotate(rec636(so))["events"][0]
    assert (e["trust"], e["trust_basis"], e["runtime"]["run_id"], e["runtime"]["model"]) == \
        ("claimed", "marker:owner-token", None, None)
    # Second guard: even were the owner a Drik identity, an owner-token tier is never upgraded.
    monkeypatch.setitem(serving.ROLE_IDENTITIES, "drik", frozenset({serving.OWNER, "github-actions[bot]"}))
    e = annotate(rec636(so))["events"][0]
    assert (e["trust"], e["runtime"]["run_id"]) == ("claimed", REVIEW_RUN)
    # Negative control: the same sign-off by the Actions bot is attributed and upgraded.
    monkeypatch.undo()
    bot = copy.deepcopy(so)
    bot["signals"]["login"], bot["trust"], bot["trust_basis"] = "github-actions[bot]", "claimed", "marker:no-suffix"
    e = annotate(rec636(bot))["events"][0]
    assert (e["trust"], e["trust_basis"], e["runtime"]["chain_link"]) == ("window", f"window:run {REVIEW_RUN}", 2)


def test_job_reviewer_posted_nothing():
    """Drik job 38161046420 (all six links tried, nothing posted) → job.reviewer posted false, links_tried 6; receipt_events returns it unplaced (episode None) for episodes.place."""
    idx = index()
    cb = cb636()
    out = annotate(rec636(*H.signoffs_from_raw(raw_pr(636))), idx=idx, cb=cb)
    jobs = receipt_events(out, idx, cb, owner=OWNER, repo=REPO_NAME)
    drik = next(e for e in jobs if e["id"] == "job:114533888297")
    assert (drik["fields"]["posted"], drik["fields"]["links_tried"], drik["fields"]["conclusion"]) == (False, 6, "failure")
    assert (drik["episode"], drik["head_sha"], drik["stale_sha"], drik["after_merge"]) == (None, None, False, False)
    assert (drik["trust"], drik["trust_basis"], drik["kind"], drik["sha"], drik["pr"]) == \
        ("verified", "receipt", "job.reviewer", F4E3, 636)
    assert drik["url"] == f"https://github.com/{OWNER}/{REPO_NAME}/actions/runs/38161046420/job/114533888297"
    rt = drik["runtime"]
    assert (rt["role"], rt["chain_link"], rt["links_not_served"], rt["model"], rt["model_basis"]) == \
        ("drik", 6, 5, "claude-haiku-4-5", "job-link+registry@merge(0987cd19+f4e36eb9)")
    # Its link-1 sign-off names the stale 9a751b26 (NVC-8): attributed to the job, not served.
    stale = ev(out, "issuecomment:6111973609")
    assert stale["runtime"]["job_id"] == 114533888297 and stale["sha"].startswith("9a751b26")
    jane = next(e for e in jobs if e["id"] == "job:114533888272")
    assert (jane["fields"]["posted"], jane["fields"]["links_tried"], jane["runtime"]["model"]) == (True, 1, "glm-5.3")
    # Negative control: the same sign-off naming the run's head would have served.
    fixed = copy.deepcopy(out)
    ev(fixed, "issuecomment:6111973609")["sha"] = F4E3
    drik2 = next(e for e in receipt_events(fixed, idx, cb, owner=OWNER, repo=REPO_NAME) if e["id"] == "job:114533888297")
    assert drik2["fields"]["posted"] is True
    # One event per reviewer job of the PR's runs, sorted, every one in the PR's window.
    assert jobs == sorted(jobs, key=lambda e: (e["ts"], int(e["id"].split(":")[1])))
    assert all(e["ts"] >= "2026-09-12T02:07:11Z" for e in jobs) and len({e["id"] for e in jobs}) == len(jobs)
    with pytest.raises(ValueError):
        receipt_events(out, idx, cb, owner="bad owner", repo=REPO_NAME)


def test_trailer_claimed_model():
    """7c25f888's 'Co-Authored-By: Claude Opus 5.5' → model 'Claude Opus 5.5', basis trailer, harness claude-code."""
    c = H.commit_from_raw(raw_pr(636), "7c25f888", kind="commit.fix")
    assert c["signals"]["trailer_coauthors"] == ["Claude Opus 5.5 <noreply@anthropic.com>"]
    e = ev(annotate(rec636(c)), c["id"])
    assert (e["runtime"]["model"], e["runtime"]["model_basis"], e["runtime"]["harness"]) == ("Claude Opus 5.5", "trailer", "claude-code")
    assert (e["trust"], e["trust_basis"], e["runtime"]["run_id"]) == ("claimed", "trailer", None)
    # Negative controls: an unnamed Claude co-author names no model; Cursor is a platform.
    assert serving.trailer_runtime({"trailer_coauthors": ["Claude <noreply@anthropic.com>"]}) is None
    assert serving.trailer_runtime({"trailer_coauthors": []}) is None
    # 'Claude Code' (31 commits, e.g. 0987cd1 on #738) names the harness, never a model.
    code = {"trailer_coauthors": ["Claude Code <noreply@anthropic.com>"]}
    assert serving.trailer_runtime(code) == {"harness": "claude-code", "model": None, "model_basis": "none"}
    assert serving.trailer_runtime({"trailer_coauthors": ["Claude Code <noreply@anthropic.com>",
                                                         "Claude Opus 4.8 <noreply@anthropic.com>"]}) == \
        {"harness": "claude-code", "model": "Claude Opus 4.8", "model_basis": "trailer"}
    cc = copy.deepcopy(c)
    cc["signals"]["trailer_coauthors"] = list(code["trailer_coauthors"])
    e = ev(annotate(rec636(cc)), cc["id"])
    assert (e["runtime"]["model"], e["runtime"]["model_basis"], e["runtime"]["harness"], e["trust"], e["trust_basis"]) == \
        (None, "none", "claude-code", "claimed", "trailer")
    assert serving.trailer_runtime({"trailer_coauthors": ["Cursor Agent <cursoragent@cursor.com>"]}) == \
        {"platform": "cursor", "harness": "cursor-agent", "model": None, "model_basis": "none"}
    two = serving.trailer_runtime({"trailer_coauthors": ["Claude Opus 4.8 <noreply@anthropic.com>",
                                                         "Claude Fable 5 <noreply@anthropic.com>"]})
    assert (two["model"], two["model_basis"]) == (None, "ambiguous")


# ---------------------------------------------------------------------------
# Tables, scanners, index.

def test_tables_match_the_contract():
    c = contract()
    assert serving.MODEL_RE.pattern == c["types"]["runtime"]["fields"]["model"]["re"]
    roles = set(c["enums"]["role"])
    assert set(serving.ROLE_IDENTITIES) == set(steps.ROLES) == roles
    assert serving.SHIP_ROLES | serving.REVIEWER_ROLES <= roles and set(serving.SHIP_ROUTINE_LABELS) == serving.SHIP_ROLES
    kinds = set(c["enums"]["kind"])
    families = set(c["field_sets"]["review.signoff"]["family"]["of"])
    for key, rs in serving.KIND_ROLES.items():
        kind, _, family = key.partition(":")
        assert kind in kinds and (not family or family in families) and rs <= roles, key
    chain_re = c["types"]["runtime"]["fields"]["chain"]["re"]
    assert all(re.fullmatch(chain_re, v) for v in serving.CHAIN_DISCRIMINATORS.values())
    assert serving.CONCLUSIONS == set(c["field_sets"]["job.reviewer"]["conclusion"]["of"])


def test_receipt_paths_match_the_evidence_layout():
    idx = index()
    for p in receipt_paths():
        rel = p.relative_to(FIXTURES).as_posix()
        rid = int(p.name.split(".")[0])
        assert idx.path_of(rid) == rel


def test_index_reads_the_highest_attempt_and_full_receipts_only():
    r2 = receipt(DESIGN_RUN)
    r1 = copy.deepcopy(r2)
    r1["run"]["run_attempt"] = 1
    r1["jobs"] = [j for j in r1["jobs"] if j["run_attempt"] == 1]
    for order in ([r1, r2], [r2, r1]):
        idx = ReceiptIndex(order)
        assert idx.path_of(DESIGN_RUN).endswith(".a2.json.gz")
        assert {w.attempt for w in idx.windows()} == {1, 2}
    # Windows only from steps that ran, with timestamps; stubs make none.
    assert all(w.step_name != "Run via Anthropic (Claude, chain link 4)" or w.attempt == 1 for w in ReceiptIndex([r2]).windows())
    stub = next(r for r in _receipts() if r["kind"] == "stub")
    assert ReceiptIndex([stub]).windows() == [] and ReceiptIndex([stub]).path_of(stub["run"]["id"])
    no_ts = copy.deepcopy(r2)
    for j in no_ts["jobs"]:
        for s in j["steps"]:
            s["completed_at"] = None
    assert ReceiptIndex([no_ts]).windows() == []
    ws = index().windows()
    assert ws == sorted(ws, key=lambda w: (ts_epoch(w.started), w.run_id, w.job_id, w.step_name))


def test_chain_literals():
    text = ORACLE_WF.decode()
    assert serving.chain_literals(text) == ["oracle-anthropic", "oracle-glm"]
    assert serving.chain_literals(text + "      run: model_registry resolve oracle-glm\n") == ["oracle-anthropic", "oracle-glm"]
    assert serving.chain_literals('run: model_registry resolve "$CHAIN"\n') == []
    assert serving.chain_literals("# model_registry resolve review\n") == []


PIN_WF = """name: X
on: push
jobs:
  ship:
    name: "Ship it"
    steps:
      - uses: actions/checkout@v5
      - name: Run via Anthropic (Claude)
        # pin note: change the --model line below
        with:
          claude_args: --model ${{ vars.MODEL }} --model claude-opus-4-8
      - name: Run via Z.AI (GLM)
        with:
          claude_args: |
            --effort max
            --model glm-5.2
      - name: Twice
        run: echo --model a
      - name: Twice
        run: echo --model b
    env:
      X: "--model nope"
  keyonly:
    steps:
    - name: Run via Z.AI (GLM)
      run: claude --model=glm-4.6
"""


@pytest.mark.parametrize("job,step,want", [
    ("Ship it", "Run via Anthropic (Claude)", "claude-opus-4-8"),   # quoted job name, ${{ }} skipped, comment skipped
    ("Ship it", "Run via Z.AI (GLM)", "glm-5.2"),                   # inside a block scalar
    ("Ship it", "Twice", None),                                      # the step name is not unique
    ("Ship it", "Missing", None),
    ("keyonly", "Run via Z.AI (GLM)", "glm-4.6"),                    # no name: → the key; same-indent sequence
    ("Nope", "Run via Z.AI (GLM)", None),
])
def test_inline_pin_scanner(job, step, want):
    assert serving.inline_pin(PIN_WF, job, step) == want


def test_annotate_is_idempotent_and_returns_a_new_record():
    idx = index()
    raw = raw_pr(636)
    rec = rec636(*H.signoffs_from_raw(raw), H.commit_from_raw(raw, "9a751b26"), H.pr_opened(raw))
    before = copy.deepcopy(rec)
    once = annotate(rec, idx=idx)
    assert rec == before and once is not rec
    assert annotate(once, idx=idx) == once
    assert once["evidence"]["receipts"] == sorted(set(once["evidence"]["receipts"]))
    assert "receipts/2026/10/11/38161046420.a1.json.gz" in once["evidence"]["receipts"]


def test_suspicious_steps_of_the_prs_receipts_are_counted():
    r = copy.deepcopy(receipt(REVIEW_RUN))
    r["suspicious_steps"] = ["Run via Gemini (chain link 1)"]
    idx = ReceiptIndex([x for x in _receipts() if x["run"]["id"] != REVIEW_RUN] + [r])
    out = annotate(rec636(), idx=idx)
    assert out["unknown"]["steps"] == {"Run via Gemini (chain link 1)": 1}
    assert annotate(out, idx=idx)["unknown"]["steps"] == {"Run via Gemini (chain link 1)": 1}
    assert annotate(rec636())["unknown"]["steps"] == {}


@needs(contract_mod.validate)
def test_joined_events_are_contract_valid():
    """Every annotated probe event and every job.reviewer event validates as event@1 once placed."""
    raw = raw_pr(636)
    idx = index()
    cb = cb636()
    out = annotate(rec636(*H.signoffs_from_raw(raw), H.commit_from_raw(raw, "9a751b26"),
                          H.commit_from_raw(raw, "7c25f888", kind="commit.fix"), H.pr_opened(raw)), idx=idx, cb=cb)
    brief = annotate(brief592(), idx=idx)
    evs = out["events"] + receipt_events(out, idx, cb, owner=OWNER, repo=REPO_NAME) + brief["events"]
    for e in evs:
        e = dict(e, episode="M:636")
        assert contract_mod.validate("event@1", e) == [], e["id"]
    # The record-level effects (incomplete, evidence.receipts, unknown.steps) keep both records valid.
    placed = dict(out, events=sorted((dict(e, episode="M:636") for e in evs if e.get("pr") == 636),
                                     key=serving.canonical.event_sort_key))
    assert contract_mod.validate("record@1:pr", placed) == []
    brief = dict(brief, events=[dict(e, episode="E0:brief:592") for e in brief["events"]])
    assert contract_mod.validate("record@1:brief", brief) == []
