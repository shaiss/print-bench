"""episodes — rounds, folds, flags, edges, decision rows.

Owner: H3. Each test's docstring is its acceptance criterion (docs/provenance.md,
final plan P0/P1a–e). Fixture PRs come from tests/fixtures/raw/pr; structural
tests need no other builder's code (``standins`` covers the H2 calls
extraction makes).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re

import pytest

from conftest import OWNER, REPO, REPO_NAME, golden, raw_pr
from fakes import FakeCommit, FakeGitReader
from _extract_helpers import design_file, events_of, fixture_ctx, pr_record, standins  # noqa: F401  (standins is a fixture)

from provenance import canonical, digest, episodes, extract
from provenance.protocols import Round

SHA = {c: c * 40 for c in "abcdef0123456789"}
GOLDEN_DESIGN = {636: "nuggs-vent-cap", 371: "sbc-case", 397: "sbc-case", 634: "calibration-cube"}


def _golden_round_ids(pr: int) -> set[str]:
    return {e["id"] for e in golden(GOLDEN_DESIGN[pr])["episodes"] if e["id"].startswith(f"R:{pr}:")}


def test_rounds_nvc1_sbc1_cc5():
    """rounds(): #636 → 15 (NVC-1); #371 → 2, #397 → 14 (SBC-1); #634 → 13 (CC-5)."""
    for pr, want in ((636, 15), (371, 2), (397, 14), (634, 13)):
        rs = episodes.rounds(raw_pr(pr))
        assert len(rs) == want, pr
        assert {r.id for r in rs} == _golden_round_ids(pr), pr        # the very rounds the audit hand-built
        assert all(r.start == r.pushed_at for r in rs)
        assert [r.end for r in rs[:-1]] == [r.pushed_at for r in rs[1:]]
        assert rs[-1].end == raw_pr(pr)["pull"]["merged_at"]
        commits = [c["sha"] for c in raw_pr(pr)["commits"]]
        assert [s for r in rs for s in r.commits] == commits          # every commit in exactly one round
    r636 = {r.id: r for r in episodes.rounds(raw_pr(636))}
    assert r636["R:636:9a751b26"].heads == ("9a751b26e18dac7f9c8c9464fd37a2e4c6c63f2c",
                                            "77cbb164" + r636["R:636:9a751b26"].heads[1][8:])
    assert r636["R:636:f4e36eb9"].heads[1].startswith("173ef373")     # a merge-main HEAD is a round; regen folds in
    # Negative control: without the regen fold every regen push would be a round of its own.
    unfolded = [p for p in episodes.pushes(raw_pr(636))]
    assert len(unfolded) == 23 and sum(p.regen for p in unfolded) == 8


def test_cc5_status_only_pushes_are_rounds():
    """#634's three one-second web commits are pushed heads only by the status rule."""
    raw = raw_pr(634)
    web = ["856831c4", "0443cba6"]                                     # cb7e8903, the third, also has a ci run
    assert not any(r["head_sha"].startswith(tuple(web)) for r in raw["ci_runs"])
    assert len(episodes.rounds(raw)) == 13
    stripped = copy.deepcopy(raw)
    stripped["statuses"] = {sha: v for sha, v in raw["statuses"].items() if not any(sha.startswith(s) for s in web)}
    assert len(episodes.rounds(stripped)) == 11                       # the control: runs alone miss them


def test_regen_constants_drift_pin():
    """REGEN_SUBJECT / REGEN_AUTHOR / REGEN_TRAILER equal scripts/reviewer-signoff.sh's literals."""
    text = (REPO / "scripts" / "reviewer-signoff.sh").read_text(encoding="utf-8")

    def literal(name: str, source: str) -> str:
        m = re.search(rf'^{name}="([^"]*)"$', source, re.M)
        assert m, name
        return m.group(1)
    for name in ("REGEN_SUBJECT", "REGEN_AUTHOR", "REGEN_TRAILER"):
        assert getattr(episodes, name) == literal(name, text), name
    assert digest.REGEN_SUBJECT == episodes.REGEN_SUBJECT
    drifted = text.replace('REGEN_SUBJECT="CI: regenerate', 'REGEN_SUBJECT="CI: re-generate')
    assert literal("REGEN_SUBJECT", drifted) != episodes.REGEN_SUBJECT  # the pin can fail


def test_is_regen_commit_needs_all_three():
    """Subject flag AND author e-mail AND exactly one parent — each alone is not a regen commit."""
    def commit(regen=True, email=episodes.REGEN_AUTHOR, parents=1):
        return {"commit": {"author": {"email": email}, "message": {"subject_regen": regen}},
                "parents": [SHA["a"]] * parents}
    assert episodes.is_regen_commit(commit())
    assert not episodes.is_regen_commit(commit(regen=False))
    assert not episodes.is_regen_commit(commit(email="owner@example.com"))
    assert not episodes.is_regen_commit(commit(parents=2))


def test_stale_signoff_nvc8(standins):
    """NVC-8: the sign-off at issuecomment-6111973609 (sha 9a751b26) lands in R:636:f4e36eb9 with stale_sha true."""
    rec = pr_record(636)
    e = next(e for e in rec["events"] if e["id"] == "issuecomment:6111973609")
    assert (e["sha"][:8], e["episode"], e["stale_sha"]) == ("9a751b26", "R:636:f4e36eb9", True)
    assert e["head_sha"].startswith("f4e36eb9")
    fresh = next(e for e in rec["events"] if e["id"] == "issuecomment:6111970233")       # Jane, same round, live sha
    assert (fresh["episode"], fresh["stale_sha"]) == ("R:636:f4e36eb9", False)
    regen_head = next(e for e in rec["events"] if e["id"] == "issuecomment:6112336954")  # names the folded 173ef373
    assert regen_head["sha"].startswith("173ef373") and regen_head["stale_sha"] is False
    assert not any(e["stale_sha"] for e in rec["events"] if e["kind"] not in episodes.MARKER_SHA_KINDS)


def _round(rid: str, head: str, pushed: str, commits=(), heads=None) -> Round:
    return Round(id=rid, head=head, heads=tuple(heads or (head,)), commits=tuple(commits or (head,)),
                 pushed_at=pushed, start=pushed, end=None)


def test_after_merge_flag():
    """An event after merged_at has after_merge true and stays in the live round."""
    rs = [_round("R:9:aaaaaaaa", SHA["a"], "2026-01-01T00:00:00Z"),
          _round("R:9:bbbbbbbb", SHA["b"], "2026-01-02T00:00:00Z")]
    merged = "2026-01-03T00:00:00Z"
    late = {"id": "issuecomment:5", "kind": "review.signoff", "ts": "2026-01-04T00:00:00Z", "sha": SHA["b"]}
    p = episodes.assign(late, rs, pr=9, merged_at=merged)
    assert (p.episode, p.after_merge, p.stale_sha, p.head_sha) == ("R:9:bbbbbbbb", True, False, SHA["b"])
    early = dict(late, ts="2026-01-02T12:00:00Z")
    assert episodes.assign(early, rs, pr=9, merged_at=merged).after_merge is False
    assert episodes.assign(late, rs, pr=9, merged_at=None).after_merge is False
    merge = {"id": "pr:9:merged", "kind": "pr.merged", "ts": merged, "sha": SHA["c"]}
    pm = episodes.assign(merge, rs, pr=9, merged_at=merged)
    assert (pm.episode, pm.after_merge, pm.head_sha) == ("M:9", False, SHA["b"])
    before = {"id": "pr:9:opened", "kind": "pr.opened", "ts": "2025-12-31T00:00:00Z", "sha": None}
    pb = episodes.assign(before, rs, pr=9, merged_at=merged)
    assert (pb.episode, pb.head_sha) == ("R:9:aaaaaaaa", None)          # before every push: the first round
    assert episodes.assign(before, [], pr=9, merged_at=None).episode == "M:9"


def test_assign_episode_forms():
    """brief, merge, commit (by round membership), direct commit, row and release placements."""
    rs = [_round("R:9:aaaaaaaa", SHA["a"], "2026-01-01T00:00:00Z", commits=(SHA["e"], SHA["a"], SHA["f"], SHA["c"]),
                 heads=(SHA["a"], SHA["c"]))]
    a = episodes.assign
    assert a({"kind": "brief.claimed", "ts": "x", "issue": 5, "fields": {}}, rs, pr=None, merged_at=None).episode == "E0:brief:5"
    closed = {"kind": "brief.closed", "ts": "x", "issue": 5, "fields": {"closed_by_pr": 9}}
    assert a(closed, rs, pr=None, merged_at=None).episode == "M:9"
    closed["fields"]["closed_by_pr"] = None
    assert a(closed, rs, pr=None, merged_at=None).episode == "E0:brief:5"
    early_commit = {"kind": "commit.fix", "ts": "2000-01-01T00:00:00Z", "sha": SHA["e"]}
    p = a(early_commit, rs, pr=9, merged_at=None)
    assert (p.episode, p.head_sha) == ("R:9:aaaaaaaa", SHA["a"])        # by membership, not by time
    assert a({"kind": "commit.regen", "ts": "2026-02-01T00:00:00Z", "sha": SHA["f"]}, rs, pr=9,
             merged_at=None).head_sha == SHA["c"]                       # its own push group's head
    assert a({"kind": "commit.human", "ts": "2026-02-01T00:00:00Z", "sha": SHA["d"]}, [], pr=None,
             merged_at=None).episode == f"C:{SHA['d'][:8]}"
    assert a({"kind": "decision.pm_log", "ts": "2026-03-04T00:00:00Z"}, rs, pr=None, merged_at=None).episode == "D:2026-03-04"
    assert a({"kind": "release", "ts": "2026-03-05T10:00:00Z"}, [], pr=None, merged_at=None).episode == "D:2026-03-05"
    assert a({"kind": "deploy.production", "ts": "2026-03-05T10:00:00Z"}, rs, pr=9, merged_at=None).episode == "M:9"


def test_verifies_edges(standins):
    """A re-sign-off's verifies lists the fix commits since that family's previous sign-off (fix→re-sign-off 100% at SHA level)."""
    rec = pr_record(636)
    edges = {e["id"]: e["edges"]["verifies"] for e in events_of(rec, "review.signoff")}
    kinds = {e["sha"]: e["kind"] for e in rec["events"] if e["kind"].startswith("commit.")}
    first_jane = edges["issuecomment:6111970233"]                      # first Jane: everything up to f4e36eb9
    assert [s[:8] for s in first_jane][:2] == ["9a751b26", "7c25f888"] and len(first_jane) == 11
    assert all(kinds[s] in episodes.VERIFIABLE_COMMIT_KINDS for s in first_jane)
    assert [s[:8] for s in edges["issuecomment:6113266518"]] == ["4a338fd0"]        # Jane re-sign-off after a fix
    assert [s[:8] for s in edges["issuecomment:6114741331"]] == ["f55dd2c7", "72366aa6"]
    assert edges["issuecomment:6112350140"] == []                      # same sha as the previous Jane: nothing new
    assert edges["issuecomment:6111973609"] == []                      # stale: names a commit before the previous Drik
    every_fix = {s for s, k in kinds.items() if k in episodes.VERIFIABLE_COMMIT_KINDS}
    covered = {s for e in events_of(rec, "review.signoff") if e["fields"]["family"] == "JANE_SIGNOFF"
               for s in e["edges"]["verifies"]}
    assert covered == every_fix                                         # 100% at SHA level for Jane
    # Negative control: a sign-off naming a sha that is not a PR commit verifies nothing.
    fake = {"id": "issuecomment:1", "kind": "review.signoff", "ts": "2026-10-12T00:00:00Z", "sha": SHA["9"],
            "fields": {"family": "JANE_SIGNOFF"}}
    assert episodes.verifies_edges([fake], raw_pr(636)) == {"issuecomment:1": []}


PM_TEXT = """# PM

## Decision log

An append-only note | with a pipe in prose is not the header.

| Date | Decision | Reason |
|---|---|---|
| 2026-08-01 | Keep it | because |
| 2026-02-30 | Not a real date | skipped |
| 2026-08-02 | Too | many | cells |
| 2026-08-03 |  | empty decision |
| 2026-08-04 | Escaped \\| pipe | ok |

| 2026-08-05 | After the blank line | not read |

## Other
| 2026-08-06 | Outside the section | not read |
"""

NOTES_TEXT = """# Notes

## Field test log

### 2026-09-01 — Prusa MK4
### 2026-09-02 - Bambu X1C
### 2026-13-01 — not a month
### not-a-date
#### 2026-09-03 — a level-4 heading

## Changelog

### v0.2 — 2026-09-04 — field-driven
### v0.3 - 2026-09-05 - hyphens do not separate
### v0.4 — 2026-02-29 — not a leap year
### v0.5 — 2024-02-29 — X

## Decisions log

- 2026-09-06: a dated bullet
- **2026-09-07** — a bold-dated bullet
  - 2026-09-08: an indented bullet is not top-level
- 2026-09-31: not a real date
* 2026-09-09: a star bullet is not the shape
- an undated bullet

## Decision log

- 2026-09-10: the singular heading counts too
"""


def test_decision_rows_select_the_documented_lines():
    """parse_pm_decision_log / parse_field_test_log / parse_changelog / parse_notes_decisions over synthetic texts: header + separator + rows until a blank or pipe-less line, a real YYYY-MM-DD first cell, ### headings by date, dated top-level bullets only. The cross-stack parity proof is site/test/provenance-rows.test.mjs (H3), run by the site-build job on every PR (critique 25)."""
    pm = episodes.parse_pm_decision_log(PM_TEXT)
    assert [(r.line, r.date) for r in pm] == [(9, "2026-08-01"), (13, "2026-08-04")]
    assert pm[0].text == "| 2026-08-01 | Keep it | because |" and pm[0].kind == "decision.pm_log"
    assert [(r.line, r.date) for r in episodes.parse_field_test_log(NOTES_TEXT)] == [(5, "2026-09-01"), (6, "2026-09-02")]
    assert [(r.line, r.date) for r in episodes.parse_changelog(NOTES_TEXT)] == [(13, "2026-09-04"), (16, "2024-02-29")]
    assert [(r.line, r.date) for r in episodes.parse_notes_decisions(NOTES_TEXT)] == [
        (20, "2026-09-06"), (21, "2026-09-07"), (29, "2026-09-10")]
    # Negative controls: a wrong header, a missing separator, a missing section → nothing.
    assert episodes.parse_pm_decision_log(PM_TEXT.replace("| Date | Decision | Reason |", "| Date | What | Why |")) == []
    assert episodes.parse_pm_decision_log(PM_TEXT.replace("|---|---|---|", "|---|")) == []
    assert episodes.parse_pm_decision_log("# PM\n\n## Backlog\n\n| Date | Decision | Reason |\n") == []
    assert episodes.parse_field_test_log("no sections") == [] and episodes.parse_changelog("") == []
    # CRLF files: the JS port ignores the trailing \r exactly as timeline.mjs does.
    crlf = PM_TEXT.replace("\n", "\r\n")
    assert [(r.line, r.date) for r in episodes.parse_pm_decision_log(crlf)] == [(9, "2026-08-01"), (13, "2026-08-04")]
    assert episodes.is_real_date("0000-02-29") and not episodes.is_real_date("1900-02-29")
    assert not episodes.is_real_date("２０２６-01-01") and not episodes.is_real_date("2026-1-01")


def test_rows_json_is_the_parity_entry_point():
    """rows_json maps {path: text} to the selected rows the Node parity test compares."""
    out = json.loads(episodes.rows_json({"designs/x/PM.md": PM_TEXT, "designs/x/NOTES.md": NOTES_TEXT,
                                         "designs/x/README.md": PM_TEXT}))
    assert [r["line"] for r in out["designs/x/PM.md"]] == [9, 13]
    assert [r["kind"] for r in out["designs/x/NOTES.md"]] == ["field_test", "field_test", "changelog", "changelog",
                                                              "decision.notes_log", "decision.notes_log",
                                                              "decision.notes_log"]
    assert out["designs/x/README.md"] == []


def _row_git(lines_before: int, sha_rows: str, row_line: int):
    pm = ("x\n" * lines_before + "## Decision log\n\n| Date | Decision | Reason |\n|---|---|---|\n"
          "| 2026-08-01 | Keep it | because |\n").encode()
    total = pm.count(b"\n")
    blame = [(SHA["0"], i + 1) for i in range(total)]
    blame[total - 1] = (sha_rows, row_line)
    return pm, blame


def test_rows_use_the_original_line_and_adding_commit():
    """Critique 6: a row whose blame is (sha S, original line 12) carries fields.line 12, added_in_sha S and url blob/S/designs/<d>/PM.md#L12; inserting lines above it on a later main commit changes neither (same row event bytes)."""
    s = SHA["5"]
    pm1, blame1 = _row_git(0, s, 12)
    pm2, blame2 = _row_git(30, s, 12)
    git = FakeGitReader([
        FakeCommit(SHA["0"], [], 1, "root"),
        FakeCommit(s, [SHA["0"]], 2, "Add the row (#21)"),
        FakeCommit(SHA["6"], [s], 3, "x (#22)", files={"designs/d/PM.md": pm1}, blame={"designs/d/PM.md": blame1}),
        FakeCommit(SHA["7"], [SHA["6"]], 4, "y (#23)", files={"designs/d/PM.md": pm2}, blame={"designs/d/PM.md": blame2}),
    ])
    a = episodes.decision_rows(git, SHA["6"], "d", owner=OWNER, repo=REPO_NAME, commit_to_pr={})
    b = episodes.decision_rows(git, SHA["7"], "d", owner=OWNER, repo=REPO_NAME, commit_to_pr={})
    assert len(a) == 1 and canonical.dumps(a) == canonical.dumps(b)
    (row,) = a
    line = "| 2026-08-01 | Keep it | because |"
    sha256 = hashlib.sha256(line.encode()).hexdigest()
    assert row["fields"] == {"added_in_pr": 21, "added_in_sha": s, "file": "PM.md", "line": 12, "line_sha256": sha256}
    assert row["url"] == f"https://github.com/{OWNER}/{REPO_NAME}/blob/{s}/designs/d/PM.md#L12"
    assert row["id"] == f"row:d:PM.md:{sha256[:16]}:0" and row["episode"] == "D:2026-08-01"
    assert (row["ts"], row["ts_precision"], row["trust"]) == ("2026-08-01T00:00:00Z", "day", "none")
    assert SHA["6"] not in canonical.dumps(a) and SHA["7"] not in canonical.dumps(b)
    # Identical text twice → occurrence index 0 and 1 (the third row has its own text).
    twice = (b"## Decision log\n\n| Date | Decision | Reason |\n|---|---|---|\n"
             b"| 2026-08-01 | Same | r |\n| 2026-08-01 | Same | r |\n| 2026-08-02 | Third | r |\n")
    git.commits[SHA["8"]] = FakeCommit(SHA["8"], [SHA["7"]], 5, "z (#24)", files={"designs/d/PM.md": twice},
                                       blame={"designs/d/PM.md": [(s, i + 1) for i in range(7)]})
    rows = episodes.decision_rows(git, SHA["8"], "d", owner=OWNER, repo=REPO_NAME, commit_to_pr={})
    assert sorted(r["id"].rsplit(":", 1)[1] for r in rows) == ["0", "0", "1"]
    assert episodes.git_line_count(twice) == 7 and episodes.git_line_count(twice[:-1]) == 7
    assert episodes.git_line_count(b"") == 0 and episodes.git_line_count(b"x") == 1


def test_rows_fail_closed_when_blame_does_not_cover_the_file():
    """A file holding rows whose blame is shorter than the file, longer than it, or empty (a failed
    `git blame` reads as []) raises BlameUnavailable — derive aborts like a failed bulk fetch; no
    row is silently dropped. A file with no rows needs no blame at all (the control)."""
    pm = (b"## Decision log\n\n| Date | Decision | Reason |\n|---|---|---|\n"
          b"| 2026-08-01 | Keep | r |\n| 2026-08-02 | Also | r |\n")
    full = [(SHA["1"], i + 1) for i in range(episodes.git_line_count(pm))]

    def rows(blame, text=pm):
        git = FakeGitReader([FakeCommit(SHA["1"], [], 1, "Add (#5)", files={"designs/d/PM.md": text},
                                        blame={"designs/d/PM.md": blame})])
        return episodes.decision_rows(git, SHA["1"], "d", owner=OWNER, repo=REPO_NAME, commit_to_pr={})
    assert len(rows(full)) == 2                                          # the positive control
    for broken in (full[:-1], [], full + [(SHA["1"], 7)]):
        with pytest.raises(episodes.BlameUnavailable):
            rows(broken)
    assert rows([], text=b"# PM\n\nno decision log here\n") == []        # no rows: blame never consulted


def test_place_assigns_unplaced_events(standins):
    """Critique 14: place() gives a job.reviewer event (episode None, ts inside round 3) episode R:<pr>:<round3 head8>, head_sha, after_merge per merged_at; already-placed events are unchanged; rounds_from_record(round_dict(r)) == r for every round of #636."""
    rs = episodes.rounds(raw_pr(636))
    assert [episodes.rounds_from_record({"rounds": [episodes.round_dict(r)]})[0] for r in rs] == rs
    assert episodes.rounds_from_record({"kind": "brief"}) == []
    rec = pr_record(636)
    third = rs[2]
    job = {"after_merge": False, "edges": {"verifies": []}, "episode": None, "fields": {}, "head_sha": None,
           "id": "job:1", "issue": None, "kind": "job.reviewer", "pr": 636, "runtime": extract.empty_runtime(),
           "sha": None, "signals": extract.empty_signals(), "stale_sha": False, "trust": "verified",
           "trust_basis": "receipt", "ts": third.pushed_at, "ts_precision": "second", "tz": "UTC",
           "url": "https://github.com/shaiss/print-bench/actions/runs/1/job/1"}
    late = dict(copy.deepcopy(job), id="job:2", ts="2026-10-12T00:00:00Z")
    before = copy.deepcopy(rec["events"])
    rec["events"] = rec["events"] + [job, late]
    placed = episodes.place(rec)
    got = {e["id"]: e for e in placed["events"]}
    assert (got["job:1"]["episode"], got["job:1"]["head_sha"], got["job:1"]["after_merge"]) == (
        third.id, third.head, False)
    assert got["job:2"]["episode"] == rs[-1].id and got["job:2"]["after_merge"] is True
    assert [e for e in placed["events"] if e["id"] not in ("job:1", "job:2")] == before
    assert placed["events"] == sorted(placed["events"], key=canonical.event_sort_key)
    assert job["episode"] is None                                        # place() returns a NEW record


def test_notes_decisions_nuggs_vent_cap():
    """decision.notes_log rows for nuggs-vent-cap at L233, 238, 241, 244, 248, 254, 258, 265, 271 (golden)."""
    rows = episodes.parse_notes_decisions(design_file("nuggs-vent-cap", "NOTES.md"))
    assert [r.line for r in rows] == [233, 238, 241, 244, 248, 254, 258, 265, 271]
    golden_rows = [e for e in golden("nuggs-vent-cap")["events"] if e["kind"] == "decision.notes_log"]
    assert sorted(r.date for r in rows) == sorted(e["ts"][:10] for e in golden_rows)
    assert episodes.parse_pm_decision_log(design_file("sbc-case", "PM.md"))           # 22 rows (SBC-8's input)
    assert len(episodes.parse_pm_decision_log(design_file("sbc-case", "PM.md"))) == 22


def test_blame_fallbacks():
    """added_in_pr from '(#N)' (squash), 'Merge pull request #N' (merge), and commit_to_pr for a rebase-merged sha."""
    root, squash, branch, merge, rebased, direct = (SHA[c] for c in "012345")
    git = FakeGitReader([
        FakeCommit(root, [], 1, "init"),
        FakeCommit(squash, [root], 2, "Squashed (#31)"),
        FakeCommit(branch, [root], 3, "on the branch"),
        FakeCommit(merge, [squash, branch], 4, "Merge pull request #32 from o/b"),
        FakeCommit(rebased, [merge], 5, "rebased commit"),
        FakeCommit(direct, [rebased], 6, "a direct push"),
    ])
    added = episodes._AddedIn(git, direct, {rebased: 33})
    assert added.pr(squash) == 31 and added.pr(branch) == 32 and added.pr(rebased) == 33
    assert added.pr(direct) is None                                      # no PR anywhere: null, not guessed
    assert added.pr(SHA["9"]) is None                                    # unknown sha
    assert episodes.subject_pr("Merge PR #196: AI shots") is None        # the 43030db9 shape names no PR
    assert episodes.subject_pr("x (#12)") == 12 and episodes.subject_pr("Merge pull request #7 from a/b") == 7


def test_force_pushed_head_is_its_own_push():
    """A pushed head missing from commits forms a push with no commits, placed by pushed_at; the
    record gains force-pushed-heads (not under commits-truncated)."""
    raw = raw_pr(371)
    gone = SHA["d"]
    raw["ci_runs"] = raw["ci_runs"] + [dict(raw["ci_runs"][0], id=1, head_sha=gone, created_at="2026-08-23T20:00:00Z")]
    ps = episodes.pushes(raw)
    orphan = next(p for p in ps if p.head == gone)
    assert orphan.commits == () and ps.index(orphan) == 2              # after the 17:2x regen push, before 23:41
    assert [r.id for r in episodes.rounds(raw)] == ["R:371:1c91268b", f"R:371:{gone[:8]}", "R:371:69c14983"]


def test_force_pushed_heads_incomplete(standins):
    """extract_pr records force-pushed-heads for an orphan head, and not when the commits list was truncated."""
    raw = raw_pr(371)
    raw["ci_runs"] = raw["ci_runs"] + [dict(raw["ci_runs"][0], id=1, head_sha=SHA["d"], created_at="2026-08-23T20:00:00Z")]
    assert "force-pushed-heads" in extract.extract_pr(raw, fixture_ctx())["incomplete"]
    raw["incomplete"] = ["commits-truncated"]
    assert extract.extract_pr(raw, fixture_ctx())["incomplete"] == ["commits-truncated"]
    assert pr_record(371)["incomplete"] == []


def test_final_head_without_push_evidence_falls_back_to_its_commit_date(standins):
    """#371 with the final head 69c14983's ci runs and statuses removed (a degraded capture:
    no-ci-runs + statuses-unavailable): the final round's pushed_at is 69c14983's committer date
    (23:41:38, a lower bound four seconds before its first status), so the previous round ends
    there and the three sign-offs naming the live head land in R:371:69c14983, not stale. Negative
    controls: a committer date not after every other push, or a final head absent from commits,
    keeps pushed_at None."""
    raw = raw_pr(371)
    final = raw["pull"]["head"]["sha"]
    assert final.startswith("69c14983")
    raw["ci_runs"] = [r for r in raw["ci_runs"] if r["head_sha"] != final]
    raw["statuses"] = {sha: v for sha, v in raw["statuses"].items() if sha != final}
    rs = episodes.rounds(raw)
    assert [(r.id, r.pushed_at, r.end) for r in rs] == [
        ("R:371:1c91268b", "2026-08-23T17:20:54Z", "2026-08-23T23:41:38Z"),
        ("R:371:69c14983", "2026-08-23T23:41:38Z", raw["pull"]["merged_at"])]
    rec = extract.extract_pr(raw, fixture_ctx())
    naming = [e for e in rec["events"] if e["kind"] == "review.signoff" and e["sha"] == final]
    assert len(naming) == 3                                              # Drik + Jane (comment) + Jane (review)
    assert all((e["episode"], e["stale_sha"], e["head_sha"]) == ("R:371:69c14983", False, final) for e in naming)
    # Controls: the fallback is refused when it is not later than every other push …
    early = copy.deepcopy(raw)
    for c in early["commits"]:
        if c["sha"] == final:
            c["commit"]["committer"]["date"] = "2026-08-23T17:20:00Z"
    assert episodes.push_times(early)[final] is None
    stale = extract.extract_pr(early, fixture_ctx())
    assert {e["stale_sha"] for e in stale["events"] if e["kind"] == "review.signoff" and e["sha"] == final} == {True}
    # … falls back to the author date when there is no committer date …
    no_committer = copy.deepcopy(raw)
    for c in no_committer["commits"]:
        if c["sha"] == final:
            c["commit"]["committer"] = None
    assert episodes.push_times(no_committer)[final] == "2026-08-23T23:41:38Z"
    # … and is absent for a final head not in commits; a head WITH push evidence never uses it.
    gone = copy.deepcopy(raw)
    gone["commits"] = [c for c in gone["commits"] if c["sha"] != final]
    assert episodes.push_times(gone)[final] is None
    assert episodes.push_times(raw_pr(371))[final] == "2026-08-23T23:41:42Z"


def test_regen_first_push_is_its_own_round():
    """A regen push with no preceding round cannot fold and is a round."""
    raw = raw_pr(371)
    first = raw["commits"][0]["sha"]
    raw["commits"] = raw["commits"][1:]                                 # drop the design commit and its push
    raw["ci_runs"] = [r for r in raw["ci_runs"] if r["head_sha"] != first]
    raw["statuses"] = {sha: v for sha, v in raw["statuses"].items() if sha != first}
    assert [r.id for r in episodes.rounds(raw)] == ["R:371:d820c6e4", "R:371:69c14983"]


def test_episodes_of():
    """view@1 episodes: one per episode of the events, R from its round, sorted by (start, id)."""
    rs = [_round("R:9:aaaaaaaa", SHA["a"], "2026-01-02T00:00:00Z")]
    ev = [{"id": "commit:" + SHA["a"], "kind": "commit.fix", "ts": "2026-01-02T00:00:00Z", "episode": "R:9:aaaaaaaa", "sha": SHA["a"], "ts_precision": "second"},
          {"id": "pr:9:merged", "kind": "pr.merged", "ts": "2026-01-03T00:00:00Z", "episode": "M:9", "sha": SHA["b"], "ts_precision": "second"},
          {"id": "issue:5:filed", "kind": "brief.filed", "ts": "2026-01-01T00:00:00Z", "episode": "E0:brief:5", "sha": None, "ts_precision": "second"},
          {"id": "row:d:PM.md:0123456789abcdef:0", "kind": "decision.pm_log", "ts": "2026-01-01T00:00:00Z", "episode": "D:2026-01-01", "sha": None, "ts_precision": "day"},
          {"id": "commit:" + SHA["c"], "kind": "commit.human", "ts": "2026-01-04T00:00:00Z", "episode": f"C:{SHA['c'][:8]}", "sha": SHA["c"], "ts_precision": "second"}]
    eps = episodes.episodes_of(ev, rs)
    assert [e["id"] for e in eps] == ["D:2026-01-01", "E0:brief:5", "R:9:aaaaaaaa", "M:9", f"C:{SHA['c'][:8]}"]
    by = {e["id"]: e for e in eps}
    assert by["R:9:aaaaaaaa"]["kind"] == "round" and by["R:9:aaaaaaaa"]["head"] == SHA["a"] and by["R:9:aaaaaaaa"]["pr"] == 9
    assert by["M:9"]["head"] == SHA["b"] and by["E0:brief:5"]["issue"] == 5 and by[f"C:{SHA['c'][:8]}"]["head"] == SHA["c"]
    assert by["D:2026-01-01"]["start"] == by["D:2026-01-01"]["end"] == "2026-01-01T00:00:00Z"
    assert all(set(e) == {"id", "kind", "pr", "issue", "head", "start", "end", "events"} for e in eps)
