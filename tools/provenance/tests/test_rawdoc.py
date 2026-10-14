"""rawdoc: raw@1 projections keep no prose and no volatile fields (scaffold-implemented; H3 owns)."""

from __future__ import annotations

from provenance import rawdoc


def test_pull_projection_digests_the_body_and_drops_bulk():
    pull = {"number": 1, "state": "closed", "title": "T", "body": "secret prose", "user": {"login": "a", "type": "User", "avatar_url": "x"},
            "head": {"ref": "r", "sha": "1" * 40, "repo": {"full_name": "o/r", "private": False}},
            "base": {"ref": "main", "sha": "2" * 40}, "labels": [{"name": "b"}, {"name": "a"}],
            "reactions": {"+1": 3}, "author_association": "OWNER", "merged_at": None}
    p = rawdoc.project_pull(pull)
    assert "secret prose" not in repr(p)
    assert p["labels"] == ["a", "b"] and p["user"] == {"login": "a", "type": "User"}
    assert "reactions" not in p and "author_association" not in p


def test_status_description_survives_only_for_reviewer_signoff():
    keep = rawdoc.project_status({"context": "reviewer-signoff", "description": "PASS x", "creator": {"login": "github-actions[bot]"}})
    drop = rawdoc.project_status({"context": "CodeRabbit", "description": "free text", "creator": {"login": "coderabbitai[bot]"}})
    assert keep["description"] == "PASS x" and drop["description"] is None
    assert keep["creator"] == "github-actions[bot]"


def test_timeline_drops_body_bearing_events():
    tl = rawdoc.project_timeline([{"event": "commented", "body": "prose"}, {"event": "committed", "message": "m"},
                                  {"event": "ready_for_review", "id": 7, "created_at": "2026-10-03T15:19:37Z", "actor": {"login": "o"}}])
    assert [e["event"] for e in tl] == ["ready_for_review"]


def test_sorted_sections_and_kept_order():
    """Ordering is part of the shape: files by filename, comments/reviews/runs/statuses by (time, id),
    deployment statuses by id, labels by name; commits and timeline keep API order."""
    files = rawdoc.project_files([{"filename": "b"}, {"filename": "a", "status": "added"}])
    assert [f["filename"] for f in files] == ["a", "b"] and files[0] == {"filename": "a", "previous_filename": None, "status": "added"}
    comments = rawdoc.project_issue_comments([{"id": 2, "created_at": "2026-01-01T00:00:01Z", "body": "x"},
                                              {"id": 9, "created_at": "2026-01-01T00:00:00Z", "body": "y"},
                                              {"id": 1, "created_at": "2026-01-01T00:00:01Z", "body": "z"}])
    assert [c["id"] for c in comments] == [9, 1, 2]
    statuses = rawdoc.project_statuses([{"id": 5, "created_at": "b", "context": "c"}, {"id": 4, "created_at": "a", "context": "c"}])
    assert [s["id"] for s in statuses] == [4, 5]
    dep = rawdoc.project_deployment({"id": 1}, [{"id": 3, "state": "success"}, {"id": 2, "state": "pending"}])
    assert [s["id"] for s in dep["statuses"]] == [2, 3]
    shas = ["c" * 40, "a" * 40]
    commits = rawdoc.project_commits([{"sha": s, "parents": [], "commit": {"message": "m"}} for s in shas])
    assert [c["sha"] for c in commits] == shas
    timeline = rawdoc.project_timeline([{"event": "labeled", "id": 2}, {"event": "closed", "id": 1}])
    assert [e["id"] for e in timeline] == [2, 1]


def test_raw_pr_doc_normalises_sets():
    """linked_issues and incomplete are sorted unique; statuses are keyed in sha order."""
    doc = rawdoc.raw_pr_doc(number=1, revision=1, captured={}, incomplete=["no-ci-runs", "brief-open", "no-ci-runs"],
                            pull={}, files=[], commits=[], reviews=[], review_comments=[], issue_comments=[],
                            timeline=[], threads={}, ci_runs=[], statuses={"b" * 40: [], "a" * 40: []},
                            deployments=[], linked_issues=[592, 5, 592])
    assert doc["linked_issues"] == [5, 592] and doc["incomplete"] == ["brief-open", "no-ci-runs"]
    assert list(doc["statuses"]) == ["a" * 40, "b" * 40] and doc["format"] == "raw-pr@1"


def test_run_projection_is_the_snapshot_row_shape():
    """project_run keeps exactly RUN_FIELDS + actor logins + sorted PR numbers (a snapshot row and a live run agree)."""
    run = {k: None for k in rawdoc.RUN_FIELDS}
    run.update(id=7, actor={"login": "a", "avatar_url": "x"}, triggering_actor="b",
               pull_requests=[{"number": 3, "url": "u"}, 1, {"number": 3}], repository={"full_name": "o/r"})
    out = rawdoc.project_run(run)
    assert set(out) == set(rawdoc.RUN_FIELDS) | {"actor", "triggering_actor", "pull_requests"}
    assert out["actor"] == "a" and out["triggering_actor"] == "b" and out["pull_requests"] == [1, 3]


def test_commit_projection_keeps_trailers_not_message():
    c = rawdoc.project_commits([{"sha": "a" * 40, "parents": [{"sha": "b" * 40}], "author": {"login": "claude"},
                                 "committer": None, "commit": {"author": {"name": "Claude", "email": "noreply@anthropic.com", "date": "2026-10-03T15:44:15Z"},
                                                               "committer": None, "message": "Fix\n\nprose\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
                                                               "verification": {"verified": True, "reason": "valid", "payload": "prose", "signature": "sig"}}}])[0]
    assert "prose" not in repr(c) and "sig" not in repr(c)
    assert c["commit"]["message"]["trailers"][0]["value"].startswith("Claude Opus 5.5")
