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


def test_commit_projection_keeps_trailers_not_message():
    c = rawdoc.project_commits([{"sha": "a" * 40, "parents": [{"sha": "b" * 40}], "author": {"login": "claude"},
                                 "committer": None, "commit": {"author": {"name": "Claude", "email": "noreply@anthropic.com", "date": "2026-10-03T15:44:15Z"},
                                                               "committer": None, "message": "Fix\n\nprose\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
                                                               "verification": {"verified": True, "reason": "valid", "payload": "prose", "signature": "sig"}}}])[0]
    assert "prose" not in repr(c) and "sig" not in repr(c)
    assert c["commit"]["message"]["trailers"][0]["value"].startswith("Claude Opus 5.5")
