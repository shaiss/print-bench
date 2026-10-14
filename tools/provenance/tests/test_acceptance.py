"""The audit's 21 acceptance checks (audits/provenance-2026-10/fixtures/bin/check_acceptance.py) ported over the HARVESTER's output for the fixture PRs, as of 2026-10-13T00:00Z: 18 byte-equal, NVC-12 re-baselined, SBC-7 re-expressed, SBC-8 moved to the site (P3c). Identity is resolved by a test-only lens (marker family → jane/drik, product-scout window → remy) because actors.conf is P3c.

Owner: H3. "The harvester's output" is ``_extract_helpers.harvest()``: the
fixture PRs and briefs through extract → run_claims → annotate_record →
receipt_events → place (the serving steps once H4's join exists). A check
whose value depends on another builder's function carries ``@needs`` and runs
at integration; the structural checks run now (``standins`` covers H2's
still-unimplemented calls) and again, unchanged, at integration.
"""

from __future__ import annotations

import collections
import json

import pytest

from conftest import CONTRACT, FIXTURES, OWNER_LOGIN, golden_full, needs, raw_pr
from _extract_helpers import design_rows, events_of, handle, harvest as run_harvest, standins  # noqa: F401

from provenance import codebasis, membership, serving, trust, views

SERVING = (serving.ReceiptIndex, serving.run_claims, serving.annotate_record, serving.receipt_events,
           codebasis.GitCodeBasis.basis_for, codebasis.GitCodeBasis.file_at, codebasis.GitCodeBasis.chain_models)
NVC = "nuggs-vent-cap"


@pytest.fixture
def harvest(standins):
    return run_harvest()


def _r_episodes(record):
    return {e["episode"] for e in record["events"] if e["episode"].startswith("R:")}


def _view(harvest, design):
    records = list(harvest["prs"].values()) + list(harvest["briefs"].values())
    return views.build_view(design, records=records, rows=design_rows(design), owner="shaiss", repo="print-bench")


def test_nvc1_rounds(harvest):
    """NVC-1: 15 R: episodes for nuggs-vent-cap."""
    rec = harvest["prs"][636]
    assert len(rec["rounds"]) == 15 and len(_r_episodes(rec)) == 15
    assert _r_episodes(rec) == {r["id"] for r in rec["rounds"]}


@needs(views.build_view, membership.classify_pr)
def test_nvc1_rounds_in_the_view(harvest):
    """NVC-1 on the curated view: 15 R: episodes."""
    assert sum(1 for e in _view(harvest, NVC)["episodes"] if e["id"].startswith("R:")) == 15


@needs(*SERVING)
def test_nvc2_brief_filer(harvest):
    """NVC-2: brief.filed → (remy, run 34112970240, glm-5.2) — window tier."""
    (filed,) = events_of(harvest["briefs"][592], "brief.filed")
    assert (handle(filed, NVC), filed["runtime"]["run_id"], filed["runtime"]["model"]) == ("remy", 34112970240, "glm-5.2")
    assert filed["trust"] == "window"


@needs(*SERVING)
def test_nvc3_design_commit_model(harvest):
    """NVC-3: commit.design → (9a751b26, glm-4.6, chain link 3)."""
    (design,) = events_of(harvest["prs"][636], "commit.design")
    assert (design["sha"][:8], design["runtime"]["model"], design["runtime"]["chain_link"]) == ("9a751b26", "glm-4.6", 3)


@needs(*SERVING)
def test_nvc4_ship_lock_link1(harvest):
    """NVC-4: the SHIP-LOCK claim (issuecomment-5642215092) → (chain link 1, glm-5.2)."""
    claim = next(e for e in harvest["briefs"][592]["events"] if e["id"] == "issuecomment:5642215092")
    assert (claim["runtime"]["chain_link"], claim["runtime"]["model"]) == (1, "glm-5.2")


@needs(*SERVING, trust.comment_tier)
def test_nvc5_gha_signoffs(harvest):
    """NVC-5: 12 github-actions sign-offs, models [glm-5.3]."""
    gha = [e for e in events_of(harvest["prs"][636], "review.signoff") if e["signals"]["login"] == "github-actions[bot]"]
    assert (len(gha), sorted({e["runtime"]["model"] for e in gha})) == (12, ["glm-5.3"])
    assert [e["trust"] for e in gha] == ["verified"] * 12                    # P1a: verified = 12


@needs(trust.comment_tier)
def test_nvc6_owner_token_signoffs(harvest):
    """NVC-6: 13 owner-token sign-offs, all non-verified."""
    own = [e for e in events_of(harvest["prs"][636], "review.signoff") if e["signals"]["login"] == OWNER_LOGIN]
    assert (len(own), all(e["trust"] != "verified" for e in own)) == (13, True)
    assert {e["trust_basis"] for e in own} == {"marker:owner-token"}


def test_nvc7_distinct_owner_pairs(harvest):
    """NVC-7: 9 distinct (reviewer, sha) owner pairs."""
    own = [e for e in events_of(harvest["prs"][636], "review.signoff") if e["signals"]["login"] == OWNER_LOGIN]
    assert len(own) == 13 and len({(handle(e, NVC), e["sha"]) for e in own}) == 9


def test_nvc8_stale_signoff(harvest):
    """NVC-8: ('9a751b26', 'R:636:f4e36eb9')."""
    st = next(e for e in harvest["prs"][636]["events"] if e["url"].endswith("6111973609"))
    assert (st["sha"][:8], st["episode"]) == ("9a751b26", "R:636:f4e36eb9") and st["stale_sha"] is True


def test_nvc9_triage(harvest):
    """NVC-9: 6 triage events, handle None (no team.conf)."""
    tri = events_of(harvest["prs"][636], "triage.verdict")
    assert (len(tri), {handle(e, NVC) for e in tri}) == (6, {None})
    assert {tuple(e["fields"]["designs"]) for e in tri} == {(NVC,)}
    assert handle(events_of(harvest["prs"][634], "pr.opened")[0], "calibration-cube") is None
    assert handle({"kind": "triage.verdict"}, "sbc-case") == "cass"           # the lens CAN name a PM


def test_nvc11_deploy(harvest):
    """NVC-11: 1 deploy.production at 2026-10-11T22:57:47Z."""
    dep = events_of(harvest["prs"][636], "deploy.production")
    assert (len(dep), dep[0]["ts"]) == (1, "2026-10-11T22:57:47Z")
    assert dep[0]["fields"]["deployment_id"] == 7003033324 and dep[0]["episode"] == "M:636"


def test_nvc12_noise_rebaselined(harvest):
    """NVC-12 (re-baselined): (noise_counts['comment.bugbot_limit'], ['comment.qodo_paused'], ['timeline.deployed'], ['status.coderabbit']) equals the tuple committed in tests/fixtures/acceptance.json with its derivation (the golden's 21, 1, 46, 33 counted per-SHA check runs and the Deployments API, which the harvester does not read)."""
    spec = json.loads((FIXTURES / "acceptance.json").read_text(encoding="utf-8"))["NVC-12"]
    noise = harvest["prs"][spec["pr"]]["noise_counts"]
    assert tuple(noise.get(k, 0) for k in spec["keys"]) == tuple(spec["expected"]) == (21, 1, 22, 33)
    assert noise[spec["same_source_as_golden_third"]["key"]] == spec["same_source_as_golden_third"]["value"] == 46
    full = collections.Counter(e["kind"] for e in golden_full(NVC)["events"])
    golden = (full["noise.bugbot_limit"], full["noise.qodo_paused"], full["deploy.preview"], full["noise.coderabbit_status"])
    assert golden == tuple(spec["golden"])                                   # the derivation names the real golden
    assert spec["derivation"]


def test_nvc12b_noise_absent(harvest):
    """NVC-12b: 0 noise events in the curated view."""
    kinds = set(json.loads(CONTRACT.read_text(encoding="utf-8"))["enums"]["kind"])
    raw = raw_pr(636)
    noise_ids = ({f"issuecomment:{c['id']}" for c in raw["issue_comments"] if c["body"]["lead"] in ("bugbot_limit", "qodo_paused")}
                 | {f"status:{s['id']}" for v in raw["statuses"].values() for s in v if s["context"] != "reviewer-signoff"})
    for rec in list(harvest["prs"].values()) + list(harvest["briefs"].values()):
        assert {e["kind"] for e in rec["events"]} <= kinds
        assert not noise_ids & {e["id"] for e in rec["events"]}
        assert all(e["kind"] != "deploy.production" or e["id"] == "deployment:7003033324"
                   for e in rec["events"] if rec.get("pr") == 636)


@needs(views.build_view, membership.classify_pr)
def test_nvc12b_noise_absent_in_the_view(harvest):
    """NVC-12b on the curated view: no event id from a noise source."""
    raw = raw_pr(636)
    noise_ids = {f"issuecomment:{c['id']}" for c in raw["issue_comments"] if c["body"]["lead"] in ("bugbot_limit", "qodo_paused")}
    assert not noise_ids & {e["id"] for e in _view(harvest, NVC)["events"]}


def test_nvc13_act_now_after_last_fix(harvest):
    """NVC-13: 21 act-now rows in triage events after the last commit.fix."""
    rec = harvest["prs"][636]
    last_fix = max(e["ts"] for e in events_of(rec, "commit.fix"))
    assert sum(e["fields"]["act_now"] for e in events_of(rec, "triage.verdict") if e["ts"] > last_fix) == 21


def test_nvc14_urls(harvest):
    """NVC-14: every displayed event has a url."""
    for rec in list(harvest["prs"].values()) + list(harvest["briefs"].values()):
        assert rec["events"] and all(e["url"].startswith("https://github.com/shaiss/print-bench/") for e in rec["events"])


@needs(views.build_view, membership.classify_pr)
def test_nvc14_urls_in_the_view(harvest):
    """NVC-14 on the curated view."""
    view = _view(harvest, NVC)
    assert view["events"] and all(e["url"] for e in view["events"])


def test_sbc1_rounds_per_pr(harvest):
    """SBC-1: {371: 2, 397: 14}."""
    assert {n: len(_r_episodes(harvest["prs"][n])) for n in (371, 397)} == {371: 2, 397: 14}


def test_sbc6_coach_rounds(harvest):
    """SBC-6: 13 coach.round events."""
    assert len(events_of(harvest["prs"][397], "coach.round")) == 13
    assert not events_of(harvest["prs"][371], "coach.round")


def test_sbc7_threads_reexpressed(harvest):
    """SBC-7 (re-expressed): #397 threads (total 26, resolved 6) — reply-text claims are not stored."""
    threads = [harvest["prs"][n]["threads"] for n in (371, 397)]               # the sbc-case design: both PRs
    assert (sum(t["total"] for t in threads), sum(t["resolved"] for t in threads)) == (26, 6)
    assert harvest["prs"][397]["threads"] == {"resolved": 6, "total": 22}
    assert set(harvest["prs"][397]["threads"]) == {"total", "resolved"}       # counts only, no reply prose


@pytest.mark.skip(reason="P3c: SBC-8 is a site test (actors.conf / #496), not in this build")
def test_sbc8_moved_to_site():
    """SBC-8: P3c site test (22 PM.md rows, none of the 12 naming Vera credited to roster.pm) — skipped here by design."""


@needs(membership.main_commit_class)
def test_cc1_main_commits():
    """CC-1: (54, 49, 19, 19, 11)."""
    mc = [e for e in golden_full("calibration-cube")["events"] if e["kind"].startswith("main.commit")]
    nm = [e for e in mc if e["refs"]["parents"] <= 1]
    c = collections.Counter(membership.main_commit_class(e["refs"]["files"]) for e in nm)
    assert (len(mc), len(nm), c["substantive"], c["stamp-only"], c["previews-only"]) == (54, 49, 19, 19, 11)


def test_cc5_rounds_634(harvest):
    """CC-5: 13 rounds for #634."""
    assert len(_r_episodes(harvest["prs"][634])) == 13


def test_cc6_owner_token_drik(harvest):
    """CC-6: 11 owner-token Drik sign-offs on #634."""
    own = [e for e in events_of(harvest["prs"][634], "review.signoff")
           if e["signals"]["login"] == OWNER_LOGIN and e["fields"]["family"] == "DRIK_SIGNOFF"]
    assert len(own) == 11


@needs(trust.comment_tier)
def test_cc6_owner_token_drik_are_claimed(harvest):
    """CC-6's sign-offs are owner-token claims, never verified."""
    own = [e for e in events_of(harvest["prs"][634], "review.signoff") if e["signals"]["login"] == OWNER_LOGIN]
    assert len(own) == 11 and {e["trust_basis"] for e in own} == {"marker:owner-token"}


def test_cc7_no_triage(harvest):
    """CC-7: 0 triage events on #634."""
    assert events_of(harvest["prs"][634], "triage.verdict") == []


def test_every_stored_event_is_placed(harvest):
    """After place() no stored event lacks an episode (the derive order's invariant)."""
    for rec in list(harvest["prs"].values()) + list(harvest["briefs"].values()):
        assert all(e["episode"] for e in rec["events"])
