"""extract / marker parsing — AC1.

Positive and negative control per rule: a well-formed marker parses into
every field (positive), and each malformation raises `MarkerError` naming
file and line rather than being skipped (negative — the silently-skipped
marker is the decided recommendation nobody acts on).
"""

from __future__ import annotations

import pytest

from brief_sources import MarkerError, extract

from conftest import marker, write_doc


# --- parsing ---------------------------------------------------------------

def test_well_formed_marker_parses_into_every_field(root):
    write_doc(root, "research.md", f"""
        # Research

        ## The section

        Substance.

        {marker("bistable-toggle", "bistable-toggle — Tier 2 reference design",
                status="briefed", ref=389)}
    """)
    (cand,) = extract(root)
    assert cand.slug == "bistable-toggle"
    assert cand.title == "bistable-toggle — Tier 2 reference design"
    assert cand.doc == "docs/research.md"
    assert cand.anchor == "the-section"
    assert cand.source == "docs/research.md#the-section"
    assert cand.status == "briefed"
    assert cand.ref == 389
    assert cand.as_dict() == {
        "slug": "bistable-toggle",
        "title": "bistable-toggle — Tier 2 reference design",
        "source": "docs/research.md#the-section",
        "status": "briefed",
        "ref": 389,
    }


def test_ordinary_comments_prose_and_quoted_markup_parse_as_nothing(root):
    # The negative control for "the prefix is what parses": a doc quoting the
    # convention at length — in prose, in a differently-named comment, inside
    # an inline code span, and inside a fenced block (all places that
    # *display* markup rather than decide anything) — yields zero candidates
    # and raises nothing. Without the code-span/fence skip this doc would
    # crash extract, and any doc explaining the convention became unscannable.
    write_doc(root, "research.md", f"""
        <!-- brief-candidates: not the singular prefix -->
        <!-- other-convention: slug | title | source=x#y | status=decided -->
        Write a marker like `<!-- brief-candidate: ... -->` to mark a decision.

        The canonical shape:

        ```
        {marker("fenced-away")}
        ```

        ~~~
        {marker("tilde-fenced-away")}
        ~~~

        Back for one real decision.

        {marker("the-real-one")}
    """)
    assert [c.slug for c in extract(root)] == ["the-real-one"]


def test_ref_is_absent_for_decided_and_in_the_dict_only_when_set(root):
    write_doc(root, "research.md", marker("snap-clip", status="decided"))
    (cand,) = extract(root)
    assert cand.ref is None
    assert cand.as_dict() == {
        "slug": "snap-clip",
        "title": "snap-clip — a decided demonstrator",
        "source": "docs/research.md#the-section",
        "status": "decided",
    }


@pytest.mark.parametrize(
    "body",
    [
        # too few fields
        "only-slug",
        "only-slug | only-title | status=decided",
        # bad slug
        "Not_A_Slug | title | source=docs/a.md#s | status=decided",
        "-leading-dash | title | source=docs/a.md#s | status=decided",
        # empty title
        "good-slug |  | source=docs/a.md#s | status=decided",
        # bad source
        "good-slug | title | source=no-anchor | status=decided",
        "good-slug | title | source=docs/a.md #spaced | status=decided",
        "good-slug | title | status=decided",
        # bad status
        "good-slug | title | source=docs/a.md#s | status=maybe",
        "good-slug | title | source=docs/a.md#s",
        # ref discipline
        "good-slug | title | source=docs/a.md#s | status=briefed",
        "good-slug | title | source=docs/a.md#s | status=briefed ref=notanumber",
        "good-slug | title | source=docs/a.md#s | status=decided ref=385",
        # unknown / duplicated / non-kv fields
        "good-slug | title | source=docs/a.md#s | status=decided | extra=x",
        "good-slug | title | source=docs/a.md#s | status=decided status=decided",
        "good-slug | title | source=docs/a.md#s | status=decided | freetext",
    ],
)
def test_each_malformation_raises_naming_the_location(root, body):
    write_doc(root, "research.md", f"<!-- brief-candidate: {body} -->")
    with pytest.raises(MarkerError, match=r"docs/research\.md:1"):
        extract(root)


def test_source_must_name_the_containing_doc(root):
    # A marker copy-pasted between docs still claiming the other doc's
    # section is bad provenance — fail loud, don't extract it.
    write_doc(root, "research.md", marker("good-slug", doc="docs/other.md"))
    with pytest.raises(MarkerError, match="sits in 'docs/research.md'"):
        extract(root)


# --- scan shape ------------------------------------------------------------

def test_scan_is_sorted_doc_path_then_marker_order(root):
    write_doc(root, "b-second.md", marker("from-b-first") + "\n" + marker("from-b-second"))
    write_doc(root, "a-first.md", marker("from-a"))
    write_doc(root, "c-third.md", marker("from-c"))
    # docs/ subdirectories are not scanned (the convention is docs/*.md), and
    # non-markdown files are not read.
    write_doc(root, "nested/deep.md", marker("from-nested"))
    (root / "docs" / "notes.txt").write_text(marker("from-txt"), encoding="utf-8")
    assert [c.slug for c in extract(root)] == [
        "from-a",
        "from-b-first",
        "from-b-second",
        "from-c",
    ]


def test_missing_docs_dir_is_empty_not_an_error(tmp_path):
    # A root with no docs/ at all (a bare fixture, a fresh checkout of
    # something else) has no candidates — that is an answer, not a crash.
    assert extract(tmp_path) == []


# --- fixture isolation (AC1) -----------------------------------------------

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]


def test_root_fixture_never_sees_the_real_tree(root):
    # Positive: the fixture's own marker extracts. Negative: none of the
    # real tree's seeded slugs (all present under the repo's docs/) leak
    # into the fixture's result, and the fixture's slug is not in the real
    # tree's either — both directions of the isolation claim.
    write_doc(root, "research.md", marker("fixture-only-candidate"))
    fixture_slugs = [c.slug for c in extract(root)]
    assert fixture_slugs == ["fixture-only-candidate"]

    real_slugs = [c.slug for c in extract(REPO_ROOT)]
    assert "fixture-only-candidate" not in real_slugs
    assert not set(fixture_slugs) & set(real_slugs)


def test_root_flag_wins_over_the_cwd(root, monkeypatch, capsys):
    # The leak path that matters: running from the real repo root with
    # --root pointing at a fixture must read the fixture, not the cwd.
    from brief_sources.cli import main

    write_doc(root, "research.md", marker("fixture-only-candidate"))
    monkeypatch.chdir(REPO_ROOT)
    assert main(["extract", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "fixture-only-candidate" in out
    assert "support-free-bracket" not in out
