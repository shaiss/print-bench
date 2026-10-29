"""markers — one parser, five eras, unknown.marker counting.

Owner: H2. Each test's docstring is its acceptance criterion (docs/provenance.md,
final plan P0/P1a–e).
"""

from __future__ import annotations

import collections
import re

import pytest

from conftest import OWNER_LOGIN, REPO, raw_pr
from provenance import digest, markers, trust

#: One committed fixture comment per era: (pr, comment id, kind it would yield or None).
ERA_FIXTURES = {
    "M1": (316, 5352016668, None),               # Actions-bot persona prose, no marker
    "M2": (343, 5377853277, "triage.verdict"),   # PM_TRIAGE posted with gh, no footer
    "M3": (371, 5389187451, "review.signoff"),   # DRIK_SIGNOFF, gh-posted, no MCP suffix
    "M4": (634, 5982882179, "review.signoff"),   # MCP-assembled DRIK_SIGNOFF suffix
    "M5": (636, 6112250646, "triage.verdict"),   # PM_TRIAGE + PM_TRIAGE_DONE completion suffix
}
REVIEW_FAMILIES = {"JANE_SIGNOFF", "DRIK_SIGNOFF", "PM_TRIAGE", "PM_TRIAGE_DONE", "COACH_LOCK", "COACH_DONE",
                   "ORACLE_REVIEW"}


def _comment(pr, cid):
    hits = [c for c in raw_pr(pr)["issue_comments"] if c["id"] == cid]
    assert len(hits) == 1, (pr, cid)
    return hits[0]


def _event_sha(kind, d):
    """The sha of the marker the extractor builds the event from (extract.py's rule)."""
    parsed = [markers.parse_marker(m) for m in d["suffix_markers"] + d["marker_lines"]]
    if kind == "review.signoff":
        hits = [markers.parse_signoff(m) for m in parsed if m and m.family in markers.SIGNOFF_FAMILIES]
    else:
        hits = [markers.parse_pm_triage(m) for m in parsed if m and m.family == "PM_TRIAGE"]
    return hits[0]["sha"]


def test_one_fixture_per_era():
    """M1..M5 each have a fixture comment (digest) from the committed raw PRs with the tier ERAS states: M1 no event, M2/M3 window at best, M4/M5 verified."""
    assert [e.name for e in markers.ERAS] == ["M1", "M2", "M3", "M4", "M5"]
    assert set(ERA_FIXTURES) == {e.name for e in markers.ERAS}
    best = {e.name: e.best_tier for e in markers.ERAS}
    assert best == {"M1": "none", "M2": "window", "M3": "window", "M4": "verified", "M5": "verified"}
    for era, (pr, cid, kind) in ERA_FIXTURES.items():
        c = _comment(pr, cid)
        assert markers.era_of(c["created_at"]) == era, (era, c["created_at"])
        assert trust.is_actions_bot(c["user"]["login"]), era
        d = c["body"]
        families = {markers.parse_marker(m).family for m in d["marker_lines"]}
        if kind is None:
            # M1: persona prose — no review marker and no lead, so no review event
            assert not families & REVIEW_FAMILIES and d["lead"] is None, era
            continue
        tier, basis = trust.comment_tier(kind=kind, login=c["user"]["login"], owner_login=OWNER_LOGIN, digest=d,
                                         created_at=c["created_at"], updated_at=c["updated_at"],
                                         edit_grace_seconds=60, marker_sha=_event_sha(kind, d))
        if best[era] == "verified":
            assert (tier, basis) == ("verified", "actions-bot+suffix"), era
        else:
            # "window at best": the rule fails here; only serving's window join can lift it
            assert (tier, basis) == ("claimed", "marker:no-suffix"), era


def test_era_boundaries():
    assert markers.era_of("2026-07-31T22:36:04Z") == "M1"   # the bootstrap predates M1's since
    assert markers.era_of("2026-08-20T23:59:59Z") == "M1"
    assert markers.era_of("2026-08-21T00:00:00Z") == "M2"
    assert markers.era_of("2026-08-23") == "M3"
    assert markers.era_of("2026-10-03T23:59:59Z") == "M3"
    assert markers.era_of("2026-10-04T00:00:00Z") == "M4"
    assert markers.era_of("2026-10-06T00:00:00Z") == "M5"
    assert markers.era_of("2027-01-01T00:00:00Z") == "M5"
    for bad in ("2026-10-04T00:00:00", "yesterday", "", None):
        with pytest.raises(ValueError):
            markers.era_of(bad)


def test_one_grammar_parses_every_era():
    """Every marker line of every committed raw PR parses (the digest kept only full-line markers)."""
    total = 0
    for n in (316, 343, 371, 397, 634, 636):
        for c in raw_pr(n)["issue_comments"]:
            for line in c["body"]["marker_lines"] + c["body"]["suffix_markers"]:
                assert markers.parse_marker(line) is not None, line
                total += 1
    assert total == 207
    assert markers.parse_marker("not a marker") is None
    assert markers.parse_marker("<!-- X --> trailing") is None
    assert markers.parse_marker("  <!-- AUTO_REVIEW_STAMP -->  ").family == "AUTO_REVIEW_STAMP"


def test_pm_triage_designs_split_on_comma():
    """<!-- PM_TRIAGE design=a,b sha=… --> → designs [a, b]."""
    sha = "c" * 40
    m = markers.parse_marker(f"<!-- PM_TRIAGE design=b,a,b sha={sha} -->")
    assert markers.parse_pm_triage(m) == {"designs": ["a", "b"], "sha": sha}
    assert markers.parse_pm_triage(markers.parse_marker(f"<!-- PM_TRIAGE design=a, sha={sha} -->")) is None
    assert markers.parse_pm_triage(markers.parse_marker(f"<!-- PM_TRIAGE design=A sha={sha} -->")) is None
    assert markers.parse_pm_triage(markers.parse_marker("<!-- PM_TRIAGE design=a sha=abc -->")) is None
    assert markers.parse_pm_triage(markers.parse_marker(f"<!-- PM_TRIAGE_DONE sha={sha} -->")) is None
    assert markers.completion_sha(markers.parse_marker(f"<!-- PM_TRIAGE_DONE sha={sha} -->")) == sha
    assert markers.completion_sha(markers.parse_marker(f"<!-- COACH_DONE sha={sha} -->")) == sha
    assert markers.completion_sha(markers.parse_marker("<!-- COACH_LOCK -->")) is None


def test_verdict_fail_is_kept():
    """An M3 'verdict=fail' parses with verdict 'fail'."""
    sha = "d" * 40
    m = markers.parse_marker(f"<!-- JANE_SIGNOFF sha={sha} verdict=fail -->")
    assert markers.parse_signoff(m) == {"family": "JANE_SIGNOFF", "fuse": None, "sha": sha, "verdict": "fail"}
    # … but it is never an MCP completion shape, so it can never be verified
    body = f"x\n\n<!-- JANE_SIGNOFF sha={sha} verdict=fail fuse=none -->\n\n{digest.FOOTER}"
    assert not digest.body_digest(body)["suffix_ok"]
    for bad in (f"verdict=maybe sha={sha}", f"sha={sha} verdict=pass fuse=sometimes", "sha=abc verdict=pass"):
        assert markers.parse_signoff(markers.parse_marker(f"<!-- DRIK_SIGNOFF {bad} -->")) is None


def test_unknown_family_counted_only_for_our_identities():
    """An unknown family in an Actions-bot or owner body is counted; a CodeRabbit *_start marker is not."""
    lines = ["<!-- mystery-family x=1 -->", "<!-- walkthrough_start -->", "<!-- printcheck-gate-report -->",
             "<!-- provider-escalation:billing -->", "<!-- reeve-greenlight v=1 -->", "<!-- mystery-family -->"]
    unknown = ["mystery-family", "walkthrough_start", "mystery-family"]
    assert markers.unknown_families("github-actions[bot]", OWNER_LOGIN, lines) == unknown
    assert markers.unknown_families("github-actions", OWNER_LOGIN, lines) == unknown
    assert markers.unknown_families("SHAISS", OWNER_LOGIN, lines) == unknown
    assert markers.unknown_families("coderabbitai[bot]", OWNER_LOGIN, lines) == []
    assert markers.unknown_families("cursor[bot]", OWNER_LOGIN, lines) == []
    assert markers.unknown_families(None, OWNER_LOGIN, lines) == []
    assert markers.unknown_families("", OWNER_LOGIN, lines) == []
    # an ignored own family must match the WHOLE family
    assert markers.unknown_families("github-actions[bot]", OWNER_LOGIN, ["<!-- reeve-greenlight-x -->"]) == [
        "reeve-greenlight-x"]
    assert all(markers.is_known_family(f) for f in markers.KNOWN_FAMILIES)
    # the settle SHIP-LOCK's marker (#864), pinned to scripts/design-run-deliver.sh's literal
    deliver = (REPO / "scripts" / "design-run-deliver.sh").read_text(encoding="utf-8")
    settle = re.search(r"^SHIP_LOCK_HTML_MARKER='([^']*)'$", deliver, re.M).group(1)
    assert markers.unknown_families("github-actions[bot]", OWNER_LOGIN, [settle]) == []
    assert markers.unknown_families("github-actions[bot]", OWNER_LOGIN, ["<!-- design-run-ship-lock:v1x -->"]) == [
        "design-run-ship-lock:v1x"]
    # over the committed fixtures: CodeRabbit's and qodo's markers are never counted, ours are
    counts = collections.Counter()
    for n in (316, 343, 371, 397, 634, 636):
        doc = raw_pr(n)
        bodies = ([(c["user"], c["body"]) for c in doc["issue_comments"] + doc["reviews"] + doc["review_comments"]]
                  + [(doc["pull"]["user"], doc["pull"]["body"])])
        for user, d in bodies:
            counts.update(markers.unknown_families((user or {}).get("login"), OWNER_LOGIN, d["marker_lines"]))
    # the M2-era Actions-bot `drik-review` head marker, and Cursor's markers in owner-authored bodies
    assert counts == {"drik-review": 3, "CURSOR_AGENT_PR_BODY_BEGIN": 1, "CURSOR_AGENT_PR_BODY_END": 1,
                      "CURSOR_SUMMARY": 1}
