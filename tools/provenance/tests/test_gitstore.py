"""gitstore — add-only writer, diff-tree guard, pushes, tip continuity (P0 acceptance). Real temp repos (git init), no network.

Owner: H1 (the placeholders). The continuity-table and mark-name tests are
LIVE: ``continuity_verdict`` and the name helpers are architect-implemented
and frozen, and ``fixtures/continuity_cases.json`` is the table Reeve's
``provenance-foreign-tip`` port must also pass (critique item 16).
"""

from __future__ import annotations

import base64
import gzip
import json
import subprocess

import pytest

from conftest import FIXTURES, GUARD_DIR

CASES = json.loads((FIXTURES / "continuity_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_continuity_table(case):
    from provenance.gitstore import Mark, continuity_verdict, parents_is_ancestor
    kw = {"max_chain": case["max_chain"]} if "max_chain" in case else {}
    v = continuity_verdict(ref=case["ref"], tip=case["tip"], marks=[Mark(**m) for m in case["marks"]],
                           first_parent=lambda s: case["parents"].get(s),
                           is_ancestor=parents_is_ancestor(case["parents"]), **kw)
    assert v.verdict == case["expect"], v.reason
    if "chain" in case:
        assert list(v.chain) == case["chain"]
    assert list(v.conflicts) == case.get("conflicts", [])
    assert v.accepted == (case["expect"] == "ok")


def test_continuity_table_orders_by_upload_time_not_artifact_id():
    """The panel's measured inversion (2026-10-04: a LOWER artifact id uploaded 3,843 s later) is in
    the table both ways round, and replaying it with id order — the pre-fix rule — flips both verdicts,
    so the rows cannot pass by accident."""
    from provenance.gitstore import Mark, continuity_verdict
    by_name = {c["name"]: c for c in CASES}
    genuine = by_name["upload-order-beats-artifact-id-genuine-newer-tip"]
    rollback = by_name["foreign-rollback-to-a-higher-id-older-checkpoint"]
    for case, want in ((genuine, "ok"), (rollback, "foreign")):
        marks = [Mark(**m) for m in case["marks"]]
        assert sorted(marks, key=lambda m: m.seq) != sorted(marks, key=lambda m: m.created)
        assert continuity_verdict(ref=case["ref"], tip=case["tip"], marks=marks,
                                  first_parent=case["parents"].get).verdict == want
        # The id-ordered replay: created forced into id order → the opposite verdict.
        by_id = [Mark(**dict(m, created=m["seq"])) for m in case["marks"]]
        assert continuity_verdict(ref=case["ref"], tip=case["tip"], marks=by_id,
                                  first_parent=case["parents"].get).verdict != want


def test_checkpoint_conflict_needs_is_ancestor_and_spares_the_derived_ref():
    """Without is_ancestor the cross-check is skipped (the pure rule alone); the derived ref is
    parentless and never checked; an is_ancestor answering None (unknown) is a conflict."""
    from provenance.gitstore import Mark, checkpoint_conflicts, continuity_verdict
    case = next(c for c in CASES if c["name"] == "foreign-checkpoint-order-conflict")
    marks = [Mark(**m) for m in case["marks"]]
    assert continuity_verdict(ref=case["ref"], tip=case["tip"], marks=marks,
                              first_parent=case["parents"].get).verdict == "ok"
    v = continuity_verdict(ref=case["ref"], tip=case["tip"], marks=marks, first_parent=case["parents"].get,
                           is_ancestor=lambda a, d: None)
    assert v.verdict == "foreign" and v.conflicts and "mark-order conflict" in v.reason
    site = [Mark(**dict(m, ref="provenance-site")) for m in case["marks"]]
    assert checkpoint_conflicts(ref="provenance-site", checkpoint=case["tip"], marks=site,
                                is_ancestor=lambda a, d: False) == ()


def test_continuity_table_covers_every_verdict_and_both_refs():
    from provenance.gitstore import VERDICTS
    assert {c["expect"] for c in CASES} == set(VERDICTS)
    assert {c["ref"] for c in CASES} == {"provenance", "provenance-site"}


def test_reeve_mirrors_the_mark_order_slack():
    """Reeve's port mirrors gitstore.MARK_ORDER_SLACK_SECONDS (the tools stay independently installable):
    the two scans must read on equally far past an id inversion. Pinned from this side, and
    scripts/ci-classify.sh re-runs this suite when tools/reeve/src/reeve/provenance.py changes."""
    import ast
    import re

    from conftest import REPO
    from provenance.gitstore import MARK_ORDER_SLACK_SECONDS
    text = (REPO / "tools" / "reeve" / "src" / "reeve" / "provenance.py").read_text(encoding="utf-8")
    m = re.search(r"^MARK_ORDER_SLACK_SECONDS = (.+)$", text, re.MULTILINE)
    assert m, "tools/reeve/src/reeve/provenance.py lost MARK_ORDER_SLACK_SECONDS"
    tree = ast.parse(m.group(1), mode="eval")
    assert all(isinstance(n, (ast.Expression, ast.BinOp, ast.Mult, ast.Constant)) for n in ast.walk(tree))
    assert eval(compile(tree, "<reeve>", "eval"), {"__builtins__": {}}) == MARK_ORDER_SLACK_SECONDS


def test_mark_names_round_trip_and_refuse():
    from provenance.gitstore import intent_name, parse_mark_name, tip_name
    sha = "a1" * 20
    assert parse_mark_name(tip_name("provenance-site", sha)) == ("tip", "provenance-site", sha)
    assert parse_mark_name(intent_name("provenance", sha)) == ("intent", "provenance", sha)
    for bad in ("tip-provenance-" + "A1" * 20, "tip-provenance-" + sha[:39], "tip-other-" + sha,
                "checkpoint-provenance-" + sha, "intent-provenance-site-" + sha + "0", "site"):
        assert parse_mark_name(bad) is None
    with pytest.raises(ValueError):
        tip_name("telemetry", sha)


# ---------------------------------------------------------------------------
# H1 — the writer, the guard, pushes and continuity over real temp repos.

from _gitstore_helpers import ALLOW, NOW_EPOCH, Artifacts, Sandbox, sh  # noqa: E402

from fakes import FakeGitHub  # noqa: E402

from provenance import canonical, gitstore  # noqa: E402
from provenance.gitstore import (  # noqa: E402
    DERIVED_REF, EVIDENCE_REF, ForeignTip, GitError, GuardViolation, TreeBuilder, continuity_verdict,
    guard_diff,
)

GUARD_BYTES = {"vercel.json": (GUARD_DIR / "vercel.json").read_bytes(),
               "scripts/vercel-ignore-build.sh": (GUARD_DIR / "vercel-ignore-build.sh").read_bytes()}
GUARD_MODES = {"scripts/vercel-ignore-build.sh": "100755"}


@pytest.fixture
def sb(tmp_path):
    return Sandbox(tmp_path)


def _evidence(extra=None):
    files = dict(GUARD_BYTES)
    files.update({"FORMAT": b"print-bench-provenance 1\n", "README.md": b"readme\n",
                  "state.json": b'{"format": "state@1"}\n',
                  "receipts/2026/08/10/1.a1.json.gz": canonical.dumps_gz({"r": 1}),
                  "raw/pr/1.json.gz": canonical.dumps_gz({"pr": 1})})
    files.update(extra or {})
    return files


def _base(sb, extra=None):
    return sb.commit(_evidence(extra), None, modes=GUARD_MODES)


def _first_parent(git):
    def fp(sha):
        p = git.parents(sha)
        return p[0] if p else None
    return fp


def test_treebuilder_adds_new_blobs_without_touching_existing(sb):
    """Seeded from a tip, add() of a new path writes it; add() of an existing path with identical CONTENT is a no-op (False) — for *.json.gz compared decompressed, so a re-gzipped identical document (other zlib, other level) is a no-op too (critique 19); with different content raises GuardViolation; no existing blob ever passes through the working tree."""
    base = _base(sb)
    before = {p: sb.git.tree_entries(base)[p][1] for p in ("raw/pr/1.json.gz", "state.json")}
    index_before = (sb.checkout / ".git" / "index").read_bytes()
    regz = gzip.compress(canonical.dumps_bytes({"pr": 1}), compresslevel=1, mtime=12345)
    assert regz != canonical.dumps_gz({"pr": 1})  # other gzip bytes, same document

    tb = TreeBuilder(sb.git, base)
    assert tb.add("raw/pr/2.json.gz", canonical.dumps_gz({"pr": 2})) is True
    assert tb.add("raw/pr/1.json.gz", regz) is False                       # identical content: no-op
    assert tb.add("raw/pr/2.json.gz", canonical.dumps_gz({"pr": 2})) is False  # planned twice: no-op
    with pytest.raises(GuardViolation, match="raw/pr/1.json.gz"):
        tb.add("raw/pr/1.json.gz", canonical.dumps_gz({"pr": 999}))
    with pytest.raises(GuardViolation):
        tb.add("FORMAT", b"other\n")                                          # plain bytes compare
    with pytest.raises(GuardViolation):
        tb.replace("raw/pr/1.json.gz", b"x")                                  # only state.json is mutable
    with pytest.raises(GuardViolation):
        tb.add("raw/pr/1.json.gz/x", b"x")                                    # file → dir collision
    with pytest.raises(GuardViolation):
        tb.add("../escape", b"x")
    tb.replace("state.json", b'{"format": "state@1", "x": 1}\n')
    tree = tb.write_tree()
    new = gitstore.commit_tree(sb.git, tree, base, "t")
    after = sb.git.tree_entries(new)
    assert after["raw/pr/1.json.gz"][1] == before["raw/pr/1.json.gz"]       # the existing blob is kept
    assert after["state.json"][1] != before["state.json"]
    assert "raw/pr/2.json.gz" in after
    # Nothing went through the work tree or the repository's own index.
    assert not (sb.checkout / "raw").exists() and not (sb.checkout / "state.json").exists()
    assert sh(sb.checkout, "status", "--porcelain") == ""
    assert (sb.checkout / ".git" / "index").read_bytes() == index_before
    assert {c.status for c in guard_diff(sb.git, base, new)} == {"A", "M"}


def test_guard_refuses_delete(sb):
    """Negative: a new commit missing any old path → GuardViolation('D …')."""
    base = _base(sb)
    files = _evidence()
    del files["receipts/2026/08/10/1.a1.json.gz"]
    new = sb.commit(files, base, modes=GUARD_MODES)
    # The D rule's own text: with the rule deleted the "only A/M" rule would still refuse a "D …".
    with pytest.raises(GuardViolation, match=r"^D receipts/2026/08/10/1\.a1\.json\.gz: add-only evidence never deletes"):
        guard_diff(sb.git, base, new)


def test_guard_refuses_modify_outside_state_json(sb):
    """Negative: M under receipts/ or raw/ → GuardViolation; M of state.json passes."""
    base = _base(sb)
    for path in ("receipts/2026/08/10/1.a1.json.gz", "raw/pr/1.json.gz", "README.md"):
        new = sb.commit(_evidence({path: canonical.dumps_gz({"changed": path})}), base, modes=GUARD_MODES)
        with pytest.raises(GuardViolation, match=f"^M {path}"):
            guard_diff(sb.git, base, new)
    ok = sb.commit(_evidence({"state.json": b'{"format": "state@1", "n": 2}\n'}), base, modes=GUARD_MODES)
    changes = guard_diff(sb.git, base, ok)
    assert [(c.status, c.path) for c in changes] == [("M", "state.json")]
    # A mode flip is a modification too.
    flip = sb.commit(_evidence(), base, modes={**GUARD_MODES, "raw/pr/1.json.gz": "100755"})
    with pytest.raises(GuardViolation, match="raw/pr/1.json.gz"):
        guard_diff(sb.git, base, flip)


def test_guard_refuses_zero_byte_blob(sb):
    """Negative: 'a raw file becomes 0 B' → GuardViolation (the telemetry #D2 class)."""
    base = _base(sb)
    emptied = sb.commit(_evidence({"state.json": b""}), base, modes=GUARD_MODES)
    with pytest.raises(GuardViolation, match="^0B state.json"):
        guard_diff(sb.git, base, emptied)
    added_empty = sb.commit(_evidence({"raw/pr/2.json.gz": b""}), base, modes=GUARD_MODES)
    with pytest.raises(GuardViolation, match="^0B raw/pr/2.json.gz"):
        guard_diff(sb.git, base, added_empty)
    # And a bootstrap root may not carry an empty blob either.
    root_empty = sb.commit(_evidence({"raw/pr/3.json.gz": b""}), None, modes=GUARD_MODES)
    with pytest.raises(GuardViolation, match="^0B"):
        guard_diff(sb.git, None, root_empty)


def test_guard_refuses_guard_file_change(sb):
    """Negative: changing vercel.json or scripts/vercel-ignore-build.sh after bootstrap → GuardViolation (the writer never re-adds them, so this fires only on a forged tree)."""
    base = _base(sb)
    for path in ("vercel.json", "scripts/vercel-ignore-build.sh"):
        new = sb.commit(_evidence({path: GUARD_BYTES[path] + b"\n"}), base, modes=GUARD_MODES)
        with pytest.raises(GuardViolation, match=f"^guard {path}"):
            guard_diff(sb.git, base, new)
    demoted = sb.commit(_evidence(), base)  # the script loses its 100755
    with pytest.raises(GuardViolation, match="^guard scripts/vercel-ignore-build.sh"):
        guard_diff(sb.git, base, demoted)
    # At bootstrap (no old commit) the guard files are plain additions.
    assert {c.status for c in guard_diff(sb.git, None, base)} == {"A"}


def test_identical_tree_pushes_nothing(sb):
    """guard_diff returns [] for an identical tree and the orchestrator skips the push (a repeat dispatch pushes no commit)."""
    base = _base(sb)
    same = sb.commit(_evidence(), base, modes=GUARD_MODES, message="another message, same tree")
    assert same != base and guard_diff(sb.git, base, same) == []
    tb = TreeBuilder(sb.git, base)
    for path, data in _evidence().items():
        assert tb.add(path, data, GUARD_MODES.get(path, "100644")) is False
    assert tb.write_tree() == gitstore.tree_of(sb.git, base)
    # The orchestrator-level "no push" is test_cli.py::test_repeat_harvest_pushes_nothing.


def _verified_page(arts):
    return {"artifacts": arts, "total_count": len(arts)}


def test_scan_marks_reads_the_artifact_list(sb):
    """scan_marks over a FakeGitHub /actions/artifacts with 150 unrelated artifacts (site, stls…) before the checkpoint: pages until a VERIFIED tip mark per ref AND an artifact 6 h older than those tips has been seen (ids are not upload-ordered, so nothing unread can then be newer), then stops; a mark from a run on another branch, with event pull_request, path other than provenance.yml, or head_sha off main's first-parent history is rejected (counted); the horizon stops paging."""
    main = sb.main_sha
    off_main = "f" * 40
    c, d, x = "c" * 40, "d" * 40, "e" * 40
    fake = FakeGitHub()
    runs = {
        1: {"event": "workflow_dispatch", "head_branch": "main", "head_sha": main, "path": gitstore.WORKFLOW_PATH},
        2: {"event": "pull_request", "head_branch": "main", "head_sha": main, "path": gitstore.WORKFLOW_PATH},
        3: {"event": "schedule", "head_branch": "main", "head_sha": main, "path": ".github/workflows/evil.yml"},
        4: {"event": "schedule", "head_branch": "evil", "head_sha": main, "path": gitstore.WORKFLOW_PATH},
        5: {"event": "schedule", "head_branch": "main", "head_sha": off_main, "path": gitstore.WORKFLOW_PATH},
    }
    for rid, run in runs.items():
        fake.responses[(f"/actions/runs/{rid}", frozenset())] = dict(run, id=rid)

    def art(seq, name, run_id, branch="main", head=main, created="2026-10-14T10:00:00Z"):
        return {"created_at": created, "id": seq, "name": name,
                "workflow_run": {"head_branch": branch, "head_sha": head, "id": run_id}}

    page1 = [art(10_000 - i, f"site-{i}", 99) for i in range(100)]
    page2 = [art(9_900 - i, f"stls-{i}", 99) for i in range(50)] + [
        art(9_800, gitstore.intent_name(EVIDENCE_REF, x), 1),           # newer than the checkpoint: kept
        art(9_799, gitstore.tip_name(EVIDENCE_REF, "1" * 40), 2),        # pull_request run: rejected
        art(9_798, gitstore.tip_name(EVIDENCE_REF, "2" * 40), 3),        # other workflow path: rejected
        art(9_797, gitstore.tip_name(EVIDENCE_REF, "3" * 40), 4, branch="evil"),  # other branch: rejected
        art(9_796, gitstore.tip_name(EVIDENCE_REF, "4" * 40), 5, head=off_main),  # off main: rejected
        art(9_795, gitstore.tip_name(EVIDENCE_REF, c), 1),
        art(9_794, gitstore.tip_name(DERIVED_REF, d), 1),
        art(9_793, gitstore.tip_name(DERIVED_REF, "9" * 40), 1, created="2026-10-14T03:30:00Z"),  # older: read, loses
        art(9_792, "telemetry-record", 99, created="2026-10-14T03:00:00Z"),  # 7 h before the tips: settles the scan
    ]
    page3 = [art(1, gitstore.tip_name(EVIDENCE_REF, "8" * 40), 1)]
    fake.pages[("/actions/artifacts", frozenset())] = [_verified_page(page1), _verified_page(page2),
                                                      _verified_page(page3)]
    marks, counts = gitstore.scan_marks(fake, sb.git, now_epoch=NOW_EPOCH, horizon_days=90)
    assert [(m.kind, m.ref, m.sha) for m in marks] == [
        ("intent", EVIDENCE_REF, x), ("tip", EVIDENCE_REF, c), ("tip", DERIVED_REF, d),
        ("tip", DERIVED_REF, "9" * 40)]
    assert [gitstore.mark_order(m) for m in marks] == sorted((gitstore.mark_order(m) for m in marks), reverse=True)
    assert counts["pages"] == 2 and counts["marks_rejected"] == 4
    artifact_gets = [c_ for c_ in fake.calls if c_[0] == "/actions/artifacts"]
    assert [c_[1]["page"] for c_ in artifact_gets] == ["1", "2"]                # page 3 never requested
    run_gets = [c_[0] for c_ in fake.calls if c_[0].startswith("/actions/runs/")]
    assert len(run_gets) == len(set(run_gets)) == 3                             # each run verified once
    v = continuity_verdict(ref=EVIDENCE_REF, tip=c, marks=marks, first_parent=lambda s: None)
    assert v.verdict == "ok"
    assert continuity_verdict(ref=DERIVED_REF, tip=d, marks=marks, first_parent=lambda s: None).verdict == "ok"

    # The horizon: an old checkpoint (and everything after the page that reached it) is ignored.
    fake2 = FakeGitHub(responses=dict(fake.responses))
    old = "2026-07-01T00:00:00Z"
    fake2.pages[("/actions/artifacts", frozenset())] = [
        _verified_page([art(20, "x", 99), art(19, gitstore.tip_name(EVIDENCE_REF, c), 1, created=old)]),
        _verified_page([art(5, gitstore.tip_name(DERIVED_REF, d), 1)])]
    marks2, counts2 = gitstore.scan_marks(fake2, sb.git, now_epoch=NOW_EPOCH, horizon_days=90)
    assert marks2 == [] and counts2["pages"] == 1
    assert continuity_verdict(ref=EVIDENCE_REF, tip=c, marks=marks2, first_parent=lambda s: None).verdict == "unanchored"


def test_scan_marks_reads_past_an_id_inversion(sb):
    """The panel's measured inversion, through the scan: the OLDER checkpoints (16:46) carry the HIGHER
    ids and sit on page 1; the genuine newer ones (17:50) have lower ids and sit on page 2. The old rule
    (stop at the first verified tip per ref in list order) anchored on page 1's — a genuine tip read
    foreign and a rollback read ok. The scan now reads on until an artifact 6 h older than the newest
    tips is seen (page 2's filler), picks the newest by upload time, and never requests page 3."""
    main = sb.main_sha
    e1, e2, s1, s2 = "61" * 20, "62" * 20, "63" * 20, "64" * 20
    fake = FakeGitHub()
    fake.responses[("/actions/runs/1", frozenset())] = {
        "event": "schedule", "head_branch": "main", "head_sha": main, "id": 1, "path": gitstore.WORKFLOW_PATH}
    fake.responses[("/actions/runs/2", frozenset())] = {
        "event": "schedule", "head_branch": "main", "head_sha": main, "id": 2, "path": gitstore.WORKFLOW_PATH}

    def art(seq, name, run_id, created):
        return {"created_at": created, "id": seq, "name": name,
                "workflow_run": {"head_branch": "main", "head_sha": main, "id": run_id}}

    page1 = [art(11309400085, gitstore.tip_name(DERIVED_REF, s1), 1, "2026-10-13T16:46:06Z"),
             art(11309400084, gitstore.tip_name(EVIDENCE_REF, e1), 1, "2026-10-13T16:46:05Z")]
    page2 = [art(11309379811, gitstore.tip_name(DERIVED_REF, s2), 2, "2026-10-13T17:50:09Z"),
             art(11309379810, gitstore.tip_name(EVIDENCE_REF, e2), 2, "2026-10-13T17:50:08Z"),
             art(11309379790, gitstore.intent_name(EVIDENCE_REF, e2), 2, "2026-10-13T17:49:50Z"),
             art(11309300000, "stls", 99, "2026-10-13T08:00:00Z")]
    page3 = [art(1, gitstore.tip_name(EVIDENCE_REF, "8" * 40), 1, "2026-10-13T19:00:00Z")]
    fake.pages[("/actions/artifacts", frozenset())] = [_verified_page(page1), _verified_page(page2),
                                                      _verified_page(page3)]
    marks, counts = gitstore.scan_marks(fake, sb.git, now_epoch=NOW_EPOCH, horizon_days=90)
    assert counts["pages"] == 2
    assert [c_[1]["page"] for c_ in fake.calls if c_[0] == "/actions/artifacts"] == ["1", "2"]
    assert [(m.kind, m.sha) for m in marks][:2] == [("tip", s2), ("tip", e2)]
    parents = {e2: e1}
    anc = gitstore.parents_is_ancestor(parents)
    for ref, genuine, rolled_back in ((EVIDENCE_REF, e2, e1), (DERIVED_REF, s2, s1)):
        ok = continuity_verdict(ref=ref, tip=genuine, marks=marks, first_parent=parents.get, is_ancestor=anc)
        assert ok.verdict == "ok" and ok.checkpoint == genuine, ok.reason
        back = continuity_verdict(ref=ref, tip=rolled_back, marks=marks, first_parent=parents.get, is_ancestor=anc)
        assert back.verdict == "foreign", back.reason


def _tip(sb, ref):
    sb.git.fetch_all()
    return sb.git.rev_parse(f"refs/remotes/origin/{ref}")


def _verdict(sb, fake, ref):
    marks, _ = gitstore.scan_marks(fake, sb.git, now_epoch=NOW_EPOCH, horizon_days=90)
    return continuity_verdict(ref=ref, tip=_tip(sb, ref), marks=marks, first_parent=_first_parent(sb.git))


def test_quiet_day_then_deleted_ref(sb):
    """Critique 3, end to end over a temp repo: 25 no-op runs (each re-uploading tip-provenance-C) keep the tip ok; deleting the ref then makes the next harvest refuse (deleted, exit 3) — never a silent re-bootstrap."""
    fake = FakeGitHub()
    art = Artifacts(fake, sb.main_sha)
    c = _base(sb)
    sb.push(c, EVIDENCE_REF)
    art.tip(EVIDENCE_REF, c, 1)
    for run in range(2, 27):  # 25 no-op runs: each checkpoints the unchanged tip again
        v = _verdict(sb, fake, EVIDENCE_REF)
        assert v.verdict == "ok" and v.checkpoint == c, (run, v.reason)
        art.tip(EVIDENCE_REF, c, run)
    sb.delete(EVIDENCE_REF)
    v = _verdict(sb, fake, EVIDENCE_REF)
    assert v.verdict == "deleted" and v.tip is None and v.checkpoint == c
    assert sb.git.rev_parse(f"refs/remotes/origin/{EVIDENCE_REF}") is None    # fetch_all pruned it
    # The harvest's refusal of a deleted ref (no re-bootstrap) is test_cli.py's
    # test_deleted_ref_is_refused_not_rebootstrapped.


def test_rollback_to_an_older_declared_sha_is_refused(sb):
    """Critique 4, over a temp repo: force-pushing provenance back to an older checkpointed sha → foreign, exit 3."""
    fake = FakeGitHub()
    art = Artifacts(fake, sb.main_sha)
    c1 = _base(sb)
    sb.push(c1, EVIDENCE_REF)
    art.tip(EVIDENCE_REF, c1, 1)
    c2 = sb.commit(_evidence({"raw/pr/2.json.gz": canonical.dumps_gz({"pr": 2})}), c1, modes=GUARD_MODES)
    art.intent(EVIDENCE_REF, c2, 2)
    sb.push(c2, EVIDENCE_REF)
    assert _verdict(sb, fake, EVIDENCE_REF).verdict == "ok"         # pushed, died before checkpointing
    art.tip(EVIDENCE_REF, c2, 2)
    assert _verdict(sb, fake, EVIDENCE_REF).verdict == "ok"
    sb.push(c1, EVIDENCE_REF, force=True)                           # the rollback
    v = _verdict(sb, fake, EVIDENCE_REF)
    assert v.verdict == "foreign" and v.tip == c1 and v.checkpoint == c2
    # A forged commit on top of the checkpoint is foreign too.
    forged = sb.commit(_evidence({"raw/pr/3.json.gz": b"x"}), c2, modes=GUARD_MODES)
    sb.push(forged, EVIDENCE_REF, force=True)
    assert _verdict(sb, fake, EVIDENCE_REF).verdict == "foreign"


def _record_runs(monkeypatch):
    calls = []
    real = gitstore.subprocess.run

    def spy(argv, *a, **kw):
        proc = real(argv, *a, **kw)
        calls.append((list(argv), dict(kw.get("env") or {}), proc))
        return proc
    monkeypatch.setattr(gitstore.subprocess, "run", spy)
    return calls


def test_push_ff_retries_transport_not_rejections(sb, monkeypatch):
    """A transport failure retries the SAME commit up to 3x then raises GitError; ANY non-ff rejection raises ForeignTip and never rebuilds (critique 21)."""
    c1 = _base(sb)
    sb.push(c1, EVIDENCE_REF)
    c2 = sb.commit(_evidence({"raw/pr/2.json.gz": b"x"}), c1, modes=GUARD_MODES)
    # Happy path first: a fast-forward pushes once.
    res = gitstore.push_fast_forward(sb.git, EVIDENCE_REF, c2, c1)
    assert res.pushed and res.attempts == 1 and sb.remote(EVIDENCE_REF) == c2

    # Rejection: the remote holds a commit that is not an ancestor of ours → ForeignTip, one attempt.
    other = sb.commit(_evidence({"raw/pr/9.json.gz": b"y"}), c1, modes=GUARD_MODES)
    calls = _record_runs(monkeypatch)
    with pytest.raises(ForeignTip):
        gitstore.push_fast_forward(sb.git, EVIDENCE_REF, other, c2)   # planned old == remote, non-ff
    pushes = [a for a, _, _ in calls if "push" in a]
    assert len(pushes) == 1 and sb.remote(EVIDENCE_REF) == c2
    # The pre-check: a remote that moved since the plan is refused before any push.
    calls.clear()
    with pytest.raises(ForeignTip, match="not the planned"):
        gitstore.push_fast_forward(sb.git, EVIDENCE_REF, other, c1)
    assert not [a for a, _, _ in calls if "push" in a]

    # Transport: the remote's URL breaks AFTER the pre-check → 1 + 3 attempts with the same refspec.
    c3 = sb.commit(_evidence({"raw/pr/3.json.gz": b"z"}), c2, modes=GUARD_MODES)
    monkeypatch.setattr(gitstore, "remote_tip", lambda git, ref: c2)
    sh(sb.checkout, "remote", "set-url", "origin", str(sb.root / "gone.git"))
    calls.clear()
    with pytest.raises(GitError, match="4 attempts"):
        gitstore.push_fast_forward(sb.git, EVIDENCE_REF, c3, c2)
    pushes = [a for a, _, _ in calls if "push" in a]
    assert len(pushes) == 4 and len({tuple(p) for p in pushes}) == 1
    assert pushes[0][-1] == f"{c3}:refs/heads/{EVIDENCE_REF}" and "--force" not in " ".join(pushes[0])


def test_derived_push_uses_force_with_lease(sb, monkeypatch):
    """provenance-site is pushed with --force-with-lease on the planned old tip; a lease failure raises ForeignTip."""
    d1 = sb.commit({"FORMAT": b"site 1\n"}, None)
    gitstore.push_force_with_lease(sb.git, DERIVED_REF, d1, None)       # create (lease: must not exist)
    assert sb.remote(DERIVED_REF) == d1
    d2 = sb.commit({"FORMAT": b"site 2\n"}, None)                        # parentless: not a fast-forward
    calls = _record_runs(monkeypatch)
    gitstore.push_force_with_lease(sb.git, DERIVED_REF, d2, d1)
    push = next(a for a, _, _ in calls if "push" in a)
    assert f"--force-with-lease=refs/heads/{DERIVED_REF}:{d1}" in push
    assert sb.remote(DERIVED_REF) == d2
    d3 = sb.commit({"FORMAT": b"site 3\n"}, None)
    with pytest.raises(ForeignTip):
        gitstore.push_force_with_lease(sb.git, DERIVED_REF, d3, d1)      # stale lease
    with pytest.raises(ForeignTip):
        gitstore.push_force_with_lease(sb.git, DERIVED_REF, d3, None)    # "must not exist", but it does
    assert sb.remote(DERIVED_REF) == d2


def test_push_error_never_carries_the_token(sb, monkeypatch, capsys):
    """Critique 12: a push to a local remote that fails with token 'ghs_TESTTOKEN' set raises GitError whose message contains neither the token nor base64('x-access-token:ghs_TESTTOKEN'); the credential reached git through GIT_CONFIG_COUNT/KEY_0/VALUE_0 (env), not argv; '::add-mask::<b64>' was printed once; fetches ran with no credential."""
    token = "ghs_TESTTOKEN"
    b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    monkeypatch.setattr(gitstore, "_MASKED", set())
    c = _base(sb)
    git = gitstore.Git(str(sb.checkout), env=ALLOW, token=token)
    calls = _record_runs(monkeypatch)
    git.fetch_all()                                                      # token-less, though git holds one
    # A remote path that CONTAINS the secrets, so git's own stderr echoes them (the negative control:
    # without redact() they would reach the message).
    bad = sb.root / f"x-{token}-{b64.replace('/', '_').replace('=', '')}"
    sh(sb.checkout, "remote", "set-url", "origin", str(bad / "missing.git"))
    monkeypatch.setattr(gitstore, "remote_tip", lambda g, ref: None)
    for _ in range(2):
        with pytest.raises(GitError) as exc:
            gitstore.push_fast_forward(git, EVIDENCE_REF, c, None)
        msg = str(exc.value)
        assert token not in msg and b64 not in msg and "***" in msg
    pushes = [(a, env, p) for a, env, p in calls if "push" in a]
    assert pushes and any(token.encode() in p.stderr for _, _, p in pushes)   # git did echo it
    for argv, env, _ in pushes:
        assert token not in " ".join(argv) and b64 not in " ".join(argv)
        assert env["GIT_CONFIG_COUNT"] == "1"
        assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
        assert env["GIT_CONFIG_VALUE_0"] == f"AUTHORIZATION: basic {b64}"
    others = [(a, env) for a, env, _ in calls if "push" not in a]
    assert others and any("fetch" in a for a, _ in others)
    for argv, env in others:
        assert "GIT_CONFIG_COUNT" not in env and not any(token in v for v in env.values())
    out = capsys.readouterr().out
    assert out.count(f"::add-mask::{b64}") == 1


def test_guard_blobs_come_from_data_branch_guard(sb, repo_root):
    """guard_blobs: vercel.json and scripts/vercel-ignore-build.sh (mode 100755) equal .github/data-branch-guard/* byte-for-byte; guard_drift names a path whose evidence bytes differ from main's."""
    guard = gitstore.guard_blobs(str(repo_root))
    assert guard == {"scripts/vercel-ignore-build.sh": ("100755", GUARD_BYTES["scripts/vercel-ignore-build.sh"]),
                     "vercel.json": ("100644", GUARD_BYTES["vercel.json"])}
    base = _base(sb)
    assert gitstore.guard_drift(gitstore.GitTreeReader(sb.git, base), guard) == []
    drifted = sb.commit(_evidence({"vercel.json": b"{}\n"}), None, modes=GUARD_MODES)
    assert gitstore.guard_drift(gitstore.GitTreeReader(sb.git, drifted), guard) == ["vercel.json"]
    demoted = sb.commit(_evidence(), None)
    assert gitstore.guard_drift(gitstore.GitTreeReader(sb.git, demoted), guard) == ["scripts/vercel-ignore-build.sh"]
    with pytest.raises(GuardViolation):
        gitstore.guard_blobs(str(sb.root))                                   # no guard sources there


def test_redact_replaces_longest_first():
    assert gitstore.redact("a TOKEN b QkFTRTY0 c", ["TOKEN", "QkFTRTY0", ""]) == "a *** b *** c"
    assert gitstore.redact("nothing", []) == "nothing"


# Pattern fixtures for scrub()/redact_patterns() — public diag artifacts must
# never carry these shapes even when the value was never in the env.
_PATTERN_FIXTURES = [
    ("ghp_" + "A" * 36, "ghp_"),
    ("gho_" + "B" * 36, "gho_"),
    ("ghs_" + "C" * 36, "ghs_"),
    ("ghu_" + "D" * 36, "ghu_"),
    ("ghr_" + "E" * 36, "ghr_"),
    ("github_pat_" + "F" * 40, "github_pat_"),
    ("sk-or-" + "G" * 40, "sk-or-"),
    ("sk-ant-" + "H" * 40, "sk-ant-"),
    ("AKIA" + ("I" * 16), "AKIA"),
    ("ASIA" + ("J" * 16), "ASIA"),
    ("AKIA" + ("K" * 16) + " secret=" + ("L" * 40), "aws-pair"),
    ("Authorization: Bearer " + ("m" * 48), "auth-bearer"),
    ("Bearer " + ("n" * 48), "bare-bearer"),
    ("https://user:passw0rd@github.com/x", "url-userpass"),
    ("https://x-access-token:deadbeefDEADBEEFdeadbeefDE@github.com/x.git", "x-access"),
    ("AUTHORIZATION: basic " + ("YWJj" * 10) + "==", "basic-auth"),
    (
        "eyJhbGciOiJIUzI1NiJ9."
        + "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        + "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        "jwt",
    ),
    ("ghs_server.token-with.dots-and-dashes_ABCDEF", "ghs-dotted"),
    # Documented Z.AI key shape: 32 hex + '.' + 16 alnum.
    ("a" * 32 + "." + "B" * 16, "zai-dotted"),
    ("ANTHROPIC_AUTH_TOKEN=" + "c" * 32 + "." + "D" * 16, "zai-auth-env"),
    # Trailing '.' must not defeat the match (lookahead omits '.').
    ("a" * 32 + "." + "B" * 16 + ".", "zai-followed-by-dot"),
    # Non-hex letter prefix — old [A-Za-z0-9.] lookbehind leaked these.
    ("z" + "a" * 32 + "." + "B" * 16, "zai-letter-prefix"),
    # Literal backslash-n sequence (two chars), not a newline.
    ("\\n" + "a" * 32 + "." + "B" * 16, "zai-backslash-n-prefix"),
    # Uppercase hex id half.
    ("A" * 32 + "." + "Bb0Cd1Ef2Gh3Ij45", "zai-uppercase-hex"),
]



def test_redact_patterns_keeps_sha256_and_git_sha():
    """The Z.AI dotted pattern must not swallow hex digests (Bugbot)."""
    sha256 = "a" * 64
    git_sha = "b" * 40
    out = gitstore.redact_patterns(f"pin {sha256} commit {git_sha}")
    assert sha256 in out and git_sha in out


def test_redact_patterns_keeps_bare_64_hex_digest():
    """A bare SHA-256 hex digest must not match the Z.AI dotted key pattern."""
    digest = "0123456789abcdef" * 4  # 64 hex, no dot
    assert len(digest) == 64
    out = gitstore.redact_patterns(f"checksum {digest} end")
    assert digest in out


@pytest.mark.parametrize("secret,label", _PATTERN_FIXTURES)
def test_redact_patterns_covers_each_shape(secret, label):
    text = f"prefix {secret} suffix"
    out = gitstore.redact_patterns(text)
    assert secret not in out, f"pattern left {label!r}-shaped secret intact: {out!r}"
    assert "***" in out


def test_scrub_applies_exact_then_patterns():
    known = "EXACTKNOWNSECRETVALUE999"
    pat = "ghp_" + "Z" * 36
    out = gitstore.scrub(f"{known} and {pat}", [known])
    assert known not in out and pat not in out
    assert out.count("***") >= 2


def test_scrub_exact_runtime_env_shaped_values_before_truncate():
    """Capture feeds ZAI_KEY / ANTHROPIC_API_KEY / GITHUB_TOKEN via SECRETS_FILE.

    Tests use fake values only — never real credentials, never print them.
    """
    fake_zai = "f" * 32 + "." + "FakeZaiKey000001"
    fake_anthropic = "sk-ant-fake-test-value-not-real-0001"
    fake_github = "ghp_FakeGitHubTokenForUnitTest000001"
    # Opaque runtime values that patterns alone would miss (no well-known prefix).
    fake_opaque = "opaque-runtime-secret-value-XYZ-999"
    text = f"zai={fake_zai} ant={fake_anthropic} gh={fake_github} op={fake_opaque} TAIL"
    # Scrub-then-truncate must replace exact values BEFORE cutting.
    out = gitstore.scrub_then_truncate(
        text, limit=len(text), secrets=[fake_zai, fake_anthropic, fake_github, fake_opaque]
    )
    assert fake_zai not in out
    assert fake_anthropic not in out
    assert fake_github not in out
    assert fake_opaque not in out
    # Truncation boundary through an opaque secret: leading half must not leak.
    half = len(fake_opaque) // 2
    prefix = "p" * 100
    straddling = prefix + fake_opaque + "END"
    cut = len(prefix) + half
    truncated = gitstore.scrub_then_truncate(
        straddling, limit=cut, secrets=[fake_opaque]
    )
    assert fake_opaque not in truncated
    assert fake_opaque[:half] not in truncated


def test_scrub_then_truncate_redacts_before_cutting():
    # Secret straddles the truncation boundary: truncate-first would leak the
    # leading half; scrub-first replaces the whole token then cuts.
    token = "ghp_" + ("Q" * 36)
    assert len(token) == 40
    prefix = "x" * 480
    text = prefix + token + "TAIL"
    # Boundary at 500 sits 20 chars into the token.
    assert text[480:500] == token[:20]
    right = gitstore.scrub_then_truncate(text, 500)
    assert token not in right
    assert "ghp_" not in right
    assert token[:20] not in right
    # Document the trap: a naive truncate-first still contains the prefix.
    assert "ghp_" in text[:500]


def test_git_reader_primitives(tmp_path):
    """The GitReader surface H3/H4 consume, over a real repo: rev_parse, show, parents, subject,
    committer e-mail/epoch, first_parent_log (with paths, merges by first parent), changed_paths,
    is_ancestor, merge_tree_read (clean / conflicted path / missing), blame_lines (ORIGINAL line
    numbers), list_dir — and every one total on a missing object."""
    r = tmp_path / "r"
    sh(tmp_path, "init", "-q", "-b", "main", str(r))
    (r / "a.txt").write_text("one\ntwo\n")
    (r / "d").mkdir()
    (r / "d" / "x.conf").write_text("x\n")
    sh(r, "add", "-A")
    sh(r, "commit", "-qm", "first line\n\nbody")
    c1 = sh(r, "rev-parse", "HEAD")
    sh(r, "checkout", "-qb", "side")
    (r / "d" / "y.conf").write_text("y\n")
    sh(r, "add", "-A")
    sh(r, "commit", "-qm", "side")
    side = sh(r, "rev-parse", "HEAD")
    sh(r, "checkout", "-q", "main")
    (r / "a.txt").write_text("zero\none\ntwo\n")
    sh(r, "commit", "-qam", "prepend")
    c2 = sh(r, "rev-parse", "HEAD")
    sh(r, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    m = sh(r, "rev-parse", "HEAD")
    sh(r, "checkout", "-qb", "conflict", c1)
    (r / "a.txt").write_text("other\n")
    sh(r, "commit", "-qam", "conflict")
    cf = sh(r, "rev-parse", "HEAD")
    sh(r, "checkout", "-q", "main")
    g = gitstore.Git(str(r))
    missing = "0" * 40
    assert g.rev_parse("main") == m and g.rev_parse(c1[:10]) == c1
    assert g.rev_parse("nope") is None and g.rev_parse("--all") is None
    assert g.has_commit(c1) and not g.has_commit(missing)
    assert g.show(c1, "a.txt") == b"one\ntwo\n" and g.show(c1, "nope") is None and g.show(missing, "a.txt") is None
    assert g.parents(m) == [c2, side] and g.parents(c1) == [] and g.parents(missing) == []
    assert g.subject(c1) == "first line" and g.subject(missing) is None
    assert g.committer_email(c1) == "owner@example.com" and isinstance(g.committed_epoch(c1), int)
    assert [s for s, _ in g.first_parent_log("main")] == [m, c2, c1]
    assert [s for s, _ in g.first_parent_log("main", ("d/y.conf",))] == [m]      # the merge, by first parent
    assert [s for s, _ in g.first_parent_log("main", ("a.txt",))] == [c2, c1]
    assert g.first_parent_log("nope") == []
    assert g.changed_paths(m) == ["d/y.conf"] and g.changed_paths(c1) == ["a.txt", "d/x.conf"]
    assert g.changed_paths(missing) == []
    assert g.is_ancestor(c1, m) and not g.is_ancestor(m, c1) and not g.is_ancestor(missing, m)
    assert g.merge_tree_read(c2, side, "d/y.conf") == (b"y\n", False)
    content, conflicted = g.merge_tree_read(c2, cf, "a.txt")
    assert conflicted and b"<<<<<<<" in content
    assert g.merge_tree_read(c2, cf, "d/x.conf") == (b"x\n", False)            # another path stays clean
    assert g.merge_tree_read(missing, side, "a.txt") == (None, False)
    blame = g.blame_lines("main", "a.txt")
    assert blame == [(c2, 1), (c1, 1), (c1, 2)]                                  # original line numbers
    assert g.blame_lines("main", "nope") == [] and g.blame_lines(missing, "a.txt") == []
    assert g.list_dir("main", "d") == ["x.conf", "y.conf"] and g.list_dir("main", "") == ["a.txt", "d"]
    assert g.list_dir("main", "nope") == []
    reader = gitstore.GitTreeReader(g, m)
    assert reader.paths() == ["a.txt", "d/x.conf", "d/y.conf"] and reader.paths("d/") == ["d/x.conf", "d/y.conf"]
    assert reader.read("d/y.conf") == b"y\n" and reader.read("nope") is None and reader.mode("a.txt") == "100644"
    assert gitstore.GitTreeReader(g, None).paths() == []


def test_dir_tree_reader(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c.json").write_bytes(b"c")
    (tmp_path / "top").write_bytes(b"t")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_bytes(b"x")
    r = gitstore.DirTreeReader(str(tmp_path))
    assert r.paths() == ["a/b/c.json", "top"] and r.paths("a/") == ["a/b/c.json"]
    assert r.read("a/b/c.json") == b"c" and r.read("../top") is None and r.read(".git/HEAD") is None
    assert r.read("missing") is None and r.mode("top") == "100644"


def test_fetch_all_tracks_the_remote_exactly(sb):
    """fetch_all: a present data ref is fetched (force-updated), an absent one leaves no stale
    local tracking ref, and a PR-head refspec with nothing to match is ok."""
    c = _base(sb)
    sb.push(c, EVIDENCE_REF)
    ok = sb.git.fetch_all()
    assert all(ok.values()) and sb.git.rev_parse(f"refs/remotes/origin/{EVIDENCE_REF}") == c
    assert sb.git.rev_parse(f"refs/remotes/origin/{DERIVED_REF}") is None
    sb.delete(EVIDENCE_REF)
    sb.git.fetch_all()
    assert sb.git.rev_parse(f"refs/remotes/origin/{EVIDENCE_REF}") is None
    assert gitstore.remote_tip(sb.git, EVIDENCE_REF) is None
    # A by-sha fetch of an object origin does not hold answers False (not raise) — the contract
    # recover relies on — and leaves nothing local.
    absent = "1" * 40
    assert sb.git.fetch(absent) is False and not sb.git.has_commit(absent)


def test_selftest_cases_all_hold():
    cases = gitstore.selftest_cases()
    labels = [label for label, _ in cases]
    assert len(labels) == len(set(labels)) and len(cases) == 7 + len(CASES)
    failing = [label for label, fn in cases if not fn()]
    assert failing == []


def test_selftest_guard_case_can_fail():
    """Negative controls: a mutation the guard accepts makes its selftest case report False, and so
    does a refusal by a DIFFERENT rule than the case names (each case pins its own rule)."""
    heads = gitstore.GUARD_RULE_HEADS
    assert gitstore._guard_case(lambda d: dict(d, **{"raw/pr/7.json.gz": b"new"}), "")() is False

    def drop(d):
        d.pop("raw/pr/1.json.gz")
        return d

    def guard_change(d):
        return dict(d, **{"vercel.json": b'{"x": 1}\n'})
    assert gitstore._guard_case(drop, heads["D"].format(path="raw/pr/1.json.gz"))() is True
    assert gitstore._guard_case(drop, heads["M"].format(path="raw/pr/1.json.gz"))() is False
    assert gitstore._guard_case(guard_change, heads["guard"].format(path="vercel.json"))() is True
    # The guard-file change is ALSO an M outside state.json: only the guard rule's head counts.
    assert gitstore._guard_case(guard_change, heads["M"].format(path="vercel.json"))() is False


def test_selftest_cases_fail_without_their_rule(monkeypatch):
    """Each guard selftest case fails when its own rule is removed from guard_diff, even though a
    later rule still refuses the same change (the D → "only A/M" and guard → "M" fall-throughs),
    and the token case fails when redact() is disabled."""
    real = gitstore.guard_diff

    def without(rule):
        def guard(git, old, new, mutable=gitstore.MUTABLE_EVIDENCE_PATHS):
            try:
                return real(git, old, new, mutable)
            except gitstore.GuardViolation as exc:
                if str(exc).startswith(rule + " "):
                    # Re-run the rest of the rules for that change: what a deleted rule leaves.
                    msg = str(exc)
                    path = msg.split(" ", 1)[1].split(":", 1)[0]
                    if rule == "D":
                        raise gitstore.GuardViolation(f"D {path}: only additions are allowed") from None
                    if rule == "guard":
                        raise gitstore.GuardViolation(f"M {path}: only state.json may be modified") from None
                    return []
                raise
        return guard
    cases = dict(gitstore.selftest_cases())
    for rule, label in (("D", "gitstore guard refuses D"), ("guard", "gitstore guard refuses a guard-file change"),
                        ("0B", "gitstore guard refuses a 0-byte blob"),
                        ("M", "gitstore guard refuses M outside state.json")):
        assert cases[label]() is True
        monkeypatch.setattr(gitstore, "guard_diff", without(rule))
        assert cases[label]() is False, rule
        monkeypatch.setattr(gitstore, "guard_diff", real)
    label = "gitstore failing push error carries neither token nor base64"
    assert cases[label]() is True
    monkeypatch.setattr(gitstore, "redact", lambda text, secrets: text)
    assert cases[label]() is False


def test_token_is_never_in_a_repr():
    """The credential rule does not depend on caller discipline: repr() (an f-string, a debugger, a
    pytest locals dump) of a Git or a Client never carries the token."""
    from provenance import github
    git = gitstore.Git(".", token="ghs_LEAKME")
    client = github.Client(repo="o/r", token="ghs_LEAKME",
                           budget=github.Budget(max_requests=None, floor=500, pace=False))
    for obj in (git, client):
        assert "ghs_LEAKME" not in repr(obj) and "ghs_LEAKME" not in f"{obj}" and obj.token == "ghs_LEAKME"


def test_iter_changes_parses_and_refuses():
    raw = b":100644 100644 " + b"a" * 40 + b" " + b"b" * 40 + b" M\0state.json\0"
    (c,) = gitstore.iter_changes(raw.split(b"\0"))
    assert (c.status, c.path, c.old_blob[:1], c.new_blob[:1]) == ("M", "state.json", "a", "b")
    with pytest.raises(GitError):
        gitstore.iter_changes([b"garbage"])


def test_subprocess_is_only_called_with_hardened_options(sb, monkeypatch):
    calls = _record_runs(monkeypatch)
    sb.git.rev_parse("HEAD")
    argv, env, _ = calls[-1]
    for opt in ("core.hooksPath=/dev/null", "core.fsmonitor=false", "safe.bareRepository=explicit",
                "credential.helper="):
        assert opt in argv
    assert env["GIT_TERMINAL_PROMPT"] == "0" and env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_ALLOW_PROTOCOL"] == "https:file"   # widened by the sandbox's Git.env
    assert gitstore.ALLOW_PROTOCOL == "https"           # production default
    assert isinstance(calls[-1][2], subprocess.CompletedProcess)
