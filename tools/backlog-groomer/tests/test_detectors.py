"""Detector tests — every detector proved able to fire AND to stay silent.

The suite keeps the same negative-control discipline as
``tools/backlog-burn/tests/test_select.py`` (itself the ``lib/*-guards.conf``
idea applied to Python), inverted for finding-detectors: each detector is
proved two ways — a snapshot that should trip it produces the finding, and
the SAME snapshot with the qualifying condition removed produces silence.
Delete a detector's condition from ``detectors.py`` and one half of its pair
fails.
"""

from __future__ import annotations

import ast
import copy
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from backlog_groomer import detectors
from backlog_groomer.config import Config

NOW = datetime(2026, 8, 15, 6, 0, 0, tzinfo=timezone.utc)


def iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def issue(number, title="A perfectly ordinary issue", labels=(), created=1.0,
          updated=1.0, sub=None, is_pull=False):
    record = {
        "number": number,
        "title": title,
        "labels": list(labels),
        "createdAt": iso(created),
        "updatedAt": iso(updated),
    }
    if sub is not None:
        record["subIssues"] = sub
    if is_pull:
        record["isPull"] = True
    return record


def snap(issues, prs=(), generated=None):
    return {
        "generatedAt": generated or NOW.isoformat(),
        "issues": list(issues),
        "openPRs": list(prs),
    }


CFG = Config()  # the documented defaults: 14 / 7 / 7 / 0.6 / 10


# ---------------------------------------------------------------------------
# Timestamp plumbing
# ---------------------------------------------------------------------------

def test_parse_ts_accepts_github_z_suffix():
    # GitHub emits trailing-Z timestamps; 3.10's fromisoformat does not.
    assert detectors.parse_ts("2026-08-15T06:00:00Z") == NOW


def test_days_since_floors_partial_days():
    assert detectors._days_since(NOW, iso(14.9)) == 14


# ---------------------------------------------------------------------------
# Detector: stale
# ---------------------------------------------------------------------------

def test_stale_fires_past_threshold():
    found = detectors.stale([issue(10, updated=15)], NOW, CFG.staleness_days)
    assert [f["number"] for f in found] == [10]
    assert found[0]["days"] == 15


def test_stale_silent_when_recently_updated():
    # Negative control: the same issue, freshly touched.
    assert detectors.stale([issue(10, updated=2)], NOW, CFG.staleness_days) == []


def test_stale_boundary_is_strictly_greater():
    # Exactly at the threshold is not yet stale — the conf says "in >N days".
    assert detectors.stale([issue(10, updated=14)], NOW, CFG.staleness_days) == []


def test_stale_sorted_oldest_first():
    found = detectors.stale(
        [issue(11, updated=20), issue(10, updated=30)], NOW, CFG.staleness_days
    )
    assert [f["number"] for f in found] == [10, 11]


# ---------------------------------------------------------------------------
# Detector: armed-stuck (and the closing-keyword matcher under it)
# ---------------------------------------------------------------------------

def _armed(number=20, quiet=10.0):
    # `quiet` drives updatedAt — the label-age proxy the detector measures.
    return issue(number, labels=[detectors.ARMED_LABEL], created=quiet, updated=quiet)


def test_armed_stuck_fires_without_closing_pr():
    found = detectors.armed_stuck([_armed()], [], NOW, CFG.armed_stuck_days)
    assert [f["number"] for f in found] == [20]
    assert found[0]["days"] == 10


def test_armed_stuck_silent_with_closing_pr():
    # Negative control: the same issue, but an open PR closes it.
    prs = [{"number": 100, "body": "Does things.\n\nCloses #20"}]
    assert detectors.armed_stuck([_armed()], prs, NOW, CFG.armed_stuck_days) == []


def test_armed_stuck_silent_when_recently_active():
    assert detectors.armed_stuck([_armed(quiet=6)], [], NOW, CFG.armed_stuck_days) == []


def test_armed_stuck_measures_quiet_not_issue_age():
    # The review's false-positive scenario: a month-old issue armed an hour
    # ago (labeling bumps updatedAt). Age must not read as stuckness — the
    # burn's next firing hasn't even had a chance yet.
    fresh_armed = issue(300, labels=[detectors.ARMED_LABEL], created=30, updated=0.04)
    assert detectors.armed_stuck([fresh_armed], [], NOW, CFG.armed_stuck_days) == []


def test_armed_stuck_silent_without_label():
    plain = issue(20, created=10, updated=10)
    assert detectors.armed_stuck([plain], [], NOW, CFG.armed_stuck_days) == []


@pytest.mark.parametrize("keyword", [
    "close", "closes", "closed", "fix", "fixes", "fixed",
    "resolve", "resolves", "resolved",
])
@pytest.mark.parametrize("colon", ["", ":"])
def test_closing_keyword_matrix(keyword, colon):
    prs = [{"number": 100, "body": f"{keyword}{colon} #20"}]
    assert detectors.has_open_closing_pr(20, prs)


def test_closing_number_is_compared_not_prefix_matched():
    # 'fixes #24' must not read as closing #244, nor 'fixes #244' as #24 —
    # the captured number is compared as an int, so prefixes can't half-match.
    prs = [{"number": 100, "body": "fixes #24"}]
    assert not detectors.has_open_closing_pr(244, prs)
    prs = [{"number": 100, "body": "fixes #244"}]
    assert not detectors.has_open_closing_pr(24, prs)


def test_closing_keyword_needs_word_boundary():
    # 'prefixes #20' contains 'fixes' but is not a closing reference.
    prs = [{"number": 100, "body": "prefixes #20"}]
    assert not detectors.has_open_closing_pr(20, prs)


def test_closing_handles_null_body():
    assert not detectors.has_open_closing_pr(20, [{"number": 100, "body": None}])


# ---------------------------------------------------------------------------
# Detector: unsized-armed
# ---------------------------------------------------------------------------

def test_unsized_armed_fires():
    found = detectors.unsized_armed([issue(22, labels=[detectors.ARMED_LABEL])])
    assert [f["number"] for f in found] == [22]


def test_unsized_armed_silent_with_points_label():
    # Negative control: the same issue, now estimated.
    sized = issue(22, labels=[detectors.ARMED_LABEL, "points-2"])
    assert detectors.unsized_armed([sized]) == []


def test_unsized_armed_silent_when_not_armed():
    assert detectors.unsized_armed([issue(22, labels=["points-2"])]) == []


def test_unsized_armed_rejects_malformed_points_label():
    # 'points-x' is not an estimate; the detector must still fire.
    fake = issue(22, labels=[detectors.ARMED_LABEL, "points-x"])
    assert [f["number"] for f in detectors.unsized_armed([fake])] == [22]


# ---------------------------------------------------------------------------
# Detector: decision-resolved-parked
# ---------------------------------------------------------------------------

def test_decision_parked_fires_with_verdict():
    parked = issue(30, labels=[detectors.DECISION_PENDING_LABEL, "decision-approved"])
    found = detectors.decision_resolved_parked([parked])
    assert [(f["number"], f["verdict"]) for f in found] == [(30, "decision-approved")]


def test_decision_parked_fires_on_rejected_too():
    parked = issue(30, labels=[detectors.DECISION_PENDING_LABEL, "decision-rejected"])
    assert len(detectors.decision_resolved_parked([parked])) == 1


def test_decision_parked_silent_without_verdict():
    # Negative control: still genuinely waiting on the human.
    waiting = issue(30, labels=[detectors.DECISION_PENDING_LABEL])
    assert detectors.decision_resolved_parked([waiting]) == []


def test_decision_parked_silent_without_pending_label():
    # A verdict label alone means the gate already cleaned up — nothing parked.
    done = issue(30, labels=["decision-approved"])
    assert detectors.decision_resolved_parked([done]) == []


# ---------------------------------------------------------------------------
# Detector: unchunked-oversized
# ---------------------------------------------------------------------------

def test_unchunked_oversized_fires_when_quiet():
    big = issue(40, labels=[detectors.OVERSIZED_LABEL], updated=8)
    assert [f["number"] for f in detectors.unchunked_oversized(
        [big], NOW, CFG.oversized_stuck_days)] == [40]


def test_unchunked_oversized_silent_when_active():
    # Negative control: same label, live discussion.
    big = issue(40, labels=[detectors.OVERSIZED_LABEL], updated=2)
    assert detectors.unchunked_oversized([big], NOW, CFG.oversized_stuck_days) == []


def test_unchunked_oversized_silent_without_label():
    quiet = issue(40, updated=8)
    assert detectors.unchunked_oversized([quiet], NOW, CFG.oversized_stuck_days) == []


# ---------------------------------------------------------------------------
# Detector: dup-candidates
# ---------------------------------------------------------------------------

def test_dup_fires_on_similar_titles():
    pair = [
        issue(60, title="Widget mount bracket for the shelf"),
        issue(61, title="Widget mount bracket for a shelf"),
    ]
    found, total = detectors.dup_candidates(pair, CFG.dup_threshold, CFG.max_dup_pairs)
    assert total == 1
    assert (found[0]["a"], found[0]["b"]) == (60, 61)
    assert found[0]["score"] == 1.0  # stopwords the/a drop out


def test_dup_silent_on_dissimilar_titles():
    # Negative control: nothing shared beyond stopwords.
    pair = [
        issue(60, title="Widget mount bracket"),
        issue(61, title="Telemetry report renderer"),
    ]
    found, total = detectors.dup_candidates(pair, CFG.dup_threshold, CFG.max_dup_pairs)
    assert (found, total) == ([], 0)


def test_dup_cap_returns_top_and_discloses_total():
    crowd = [issue(60 + n, title=f"Widget mount bracket {n}") for n in range(6)]
    found, total = detectors.dup_candidates(crowd, CFG.dup_threshold, 10)
    assert total == 15  # C(6,2)
    assert len(found) == 10


def test_dup_ordered_by_score_then_pair_numbers():
    # Two 1.0 pairs and four 0.6 pairs, fed in scrambled input order so a
    # stable sort preserving insertion order cannot fake the tie-break —
    # dropping either half of the (-score, a, b) key must fail this.
    crowd = [
        issue(63, title="Widget mount bracket beta"),
        issue(60, title="Widget mount bracket alpha"),
        issue(62, title="Widget mount bracket beta"),
        issue(61, title="Widget mount bracket alpha"),
    ]
    found, total = detectors.dup_candidates(crowd, CFG.dup_threshold, 10)
    assert total == 6
    assert [(f["a"], f["b"]) for f in found] == [
        (60, 61), (62, 63),                    # score 1.0, (a, b) tie-break
        (60, 62), (60, 63), (61, 62), (61, 63) # score 0.6, (a, b) tie-break
    ]


def test_dup_skips_all_stopword_titles():
    ghost = issue(60, title="The of and")
    other = issue(61, title="The of and")
    assert detectors.dup_candidates([ghost, other], 0.1, 10) == ([], 0)


# ---------------------------------------------------------------------------
# Detector: epic-complete
# ---------------------------------------------------------------------------

def test_epic_complete_fires_when_all_children_closed():
    epic = issue(50, sub={"total": 2, "completed": 2})
    assert [f["number"] for f in detectors.epic_complete([epic])] == [50]


def test_epic_complete_silent_when_partial():
    # Negative control: same epic, one child still open.
    epic = issue(50, sub={"total": 3, "completed": 1})
    assert detectors.epic_complete([epic]) == []


def test_epic_complete_silent_with_no_children():
    childless = issue(50, sub={"total": 0, "completed": 0})
    assert detectors.epic_complete([childless]) == []


# ---------------------------------------------------------------------------
# evaluate(): coverage honesty and defensive filtering
# ---------------------------------------------------------------------------

def test_evaluate_marks_armed_stuck_not_evaluated_without_pr_data():
    snapshot = snap([_armed()])
    del snapshot["openPRs"]
    result = detectors.evaluate(snapshot, CFG)
    assert "armed-stuck" in result["not_evaluated"]
    assert result["findings"]["armed-stuck"] == []


def test_evaluate_treats_empty_pr_list_as_a_real_answer():
    # [] means "no open PRs", which evaluates normally — only a *missing*
    # key is "couldn't look".
    result = detectors.evaluate(snap([_armed()]), CFG)
    assert "armed-stuck" not in result["not_evaluated"]
    assert [f["number"] for f in result["findings"]["armed-stuck"]] == [20]


def test_evaluate_marks_epic_not_evaluated_without_sub_data():
    snapshot = snap([issue(10), issue(11)])
    result = detectors.evaluate(snapshot, CFG)
    assert "epic-complete" in result["not_evaluated"]


def test_evaluate_drops_pull_request_entries():
    snapshot = snap([issue(10, updated=30), issue(11, updated=30, is_pull=True)])
    result = detectors.evaluate(snapshot, CFG)
    assert [f["number"] for f in result["findings"]["stale"]] == [10]
    assert result["issue_count"] == 1


def test_evaluate_is_pure_and_repeatable():
    snapshot = snap([_armed(), issue(10, updated=30)])
    first = detectors.evaluate(copy.deepcopy(snapshot), CFG)
    second = detectors.evaluate(copy.deepcopy(snapshot), CFG)
    assert first == second


# ---------------------------------------------------------------------------
# AC4: the pure core imports nothing network-capable, and the whole package
# performs no write verbs anywhere — advisory-only, checkable.
# ---------------------------------------------------------------------------

_PKG = pathlib.Path(detectors.__file__).parent
_FORBIDDEN_IMPORTS = {"urllib", "socket", "http", "subprocess", "requests"}
_PURE_MODULES = ("detectors.py", "report.py", "config.py", "cli.py")


def _imports_of(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("module", _PURE_MODULES)
def test_pure_modules_import_nothing_network_capable(module):
    assert not _imports_of(_PKG / module) & _FORBIDDEN_IMPORTS


def test_package_contains_no_write_verbs():
    # The single I/O module is GET-only: no POST/PATCH/PUT/DELETE anywhere
    # in the package source (word-bounded, so GITHUB_OUTPUT's "PUT" doesn't
    # trip it). The workflow's upsert is the sole write surface.
    import re as _re

    verb_re = _re.compile(r"\b(POST|PATCH|PUT|DELETE)\b")
    for path in _PKG.glob("*.py"):
        match = verb_re.search(path.read_text(encoding="utf-8"))
        assert match is None, f"{path.name} mentions {match.group(0) if match else ''}"
