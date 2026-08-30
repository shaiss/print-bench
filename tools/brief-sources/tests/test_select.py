"""The guard rails — AC2.

One positive AND one negative control per rail, the repo's standing rule: a
guard never exercised can be weakened while every other check stays green.
The positive control for a drop rule is always *the same subject surviving
when the rail does not apply* — that is what proves the drop came from the
rail, not from something incidental.
"""

from __future__ import annotations

import pytest

from brief_sources import extract, select
from brief_sources.select import matches_subject, parse_briefs

from conftest import marker, write_doc


def cand(root, slug, **kw):
    """Extract a one-marker fixture and return its single candidate."""
    write_doc(root, "research.md", marker(slug, **kw))
    cands = extract(root)
    assert len(cands) == 1
    return cands[0]


# --- rail 1: status=briefed never selects ----------------------------------

def test_briefed_never_selects_even_with_an_empty_backlog(root):
    # Negative control: an already-filed marker is dropped even when nothing
    # else could possibly match it (no briefs, no designs) — the rail fires
    # on status alone, not on a dedup accident.
    c = cand(root, "bistable-toggle", status="briefed", ref=389)
    assert select([c], [], []) is None


def test_the_same_marker_decided_selects(root):
    # Positive control: identical subject, status=decided → selects. Only
    # the status differs, so the drop above is attributable to the rail.
    c = cand(root, "bistable-toggle", status="decided")
    assert select([c], [], []).slug == "bistable-toggle"


# --- rail 2: duplicate slugs collapse to the first --------------------------

def test_duplicate_slug_keeps_the_first_occurrence(root):
    write_doc(root, "research.md", marker("dupe", title="first wording")
              + "\n" + marker("dupe", title="second wording"))
    chosen = select(extract(root), [], [])
    assert chosen.title == "first wording"


def test_a_different_slug_is_not_collapsed(root):
    # Negative control: collapsing is by slug, so a genuinely different
    # subject still reaches the front of the queue.
    write_doc(root, "research.md", marker("first-slug") + "\n" + marker("second-slug"))
    assert select(extract(root), [], []).slug == "first-slug"


# --- rail 3: a matching open brief does not select --------------------------

def test_matching_open_brief_drops_the_candidate(root):
    # Negative control — the live shape: the marker's own slug leads the
    # brief's title, exactly how the nine seeded markers sit against
    # issues #385–#393 today.
    c = cand(root, "bistable-toggle",
             title="bistable-toggle — Tier 2 reference design (Domain 1, buckled-arch bistable switch)")
    briefs = [(389, "bistable-toggle — Tier 2 reference design (Domain 1, buckled-arch bistable switch)")]
    assert select([c], briefs, []) is None


def test_unmatched_subject_still_selects(root):
    # Positive control: a real open brief about something else does not
    # swallow an unrelated candidate — the matcher is conservative, not
    # total. Sibling tier-3 briefs are the sharpest live case: they share
    # "Tier 3 reference design" and the word "bistable" with this candidate.
    c = cand(root, "bistable-toggle",
             title="bistable-toggle — Tier 2 reference design (Domain 1, buckled-arch bistable switch)")
    briefs = [(392, "bistable-snap-box — Tier 3 reference design (living-hinge box with bistable latch)")]
    assert select([c], briefs, []).slug == "bistable-toggle"


# --- rail 4: an existing designs/<name>/ does not select --------------------

def test_existing_design_dir_drops_the_candidate(root):
    # Negative control: the subject is already BUILT — a directory exists.
    c = cand(root, "captive-spinner")
    (root / "designs" / "captive-spinner").mkdir()
    from brief_sources.cli import _design_names
    assert select([c], [], _design_names(root)) is None


def test_no_design_dir_still_selects(root):
    # Positive control: same candidate, empty designs/ → selects.
    c = cand(root, "captive-spinner")
    assert select([c], [], []).slug == "captive-spinner"


# --- rail 5: exactly one, or NONE -------------------------------------------

def test_many_eligible_print_exactly_one_the_oldest(root):
    write_doc(root, "b.md", marker("later-candidate"))
    write_doc(root, "a.md", marker("earlier-candidate"))
    chosen = select(extract(root), [], [])
    assert chosen.slug == "earlier-candidate"


def test_all_dropped_yields_none(root):
    # Negative control: the NONE verdict, with every candidate dropped by a
    # different rail (one briefed, one matched to a brief, one built).
    write_doc(root, "a.md", marker("filed-one", status="briefed", ref=1))
    write_doc(root, "b.md", marker("open-one", title="open-one — a decided demonstrator"))
    write_doc(root, "c.md", marker("built-one"))
    cands = extract(root)
    assert select(cands, [(2, "open-one — something already filed as a brief")], ["built-one"]) is None


def test_marker_order_within_a_doc_breaks_the_tie(root):
    # Ordering is doc order, THEN marker order within a doc — the second
    # tie-break the issue names, exercised apart from the first.
    write_doc(root, "a.md", marker("first-in-doc") + "\n" + marker("second-in-doc"))
    assert select(extract(root), [], []).slug == "first-in-doc"


# --- conservative matching: when in doubt, drop -----------------------------
#
# "Conservative" has two failure directions and each needs its control:
# over-matching (drops everything, the tool is useless) and under-matching
# (re-files an existing subject, the failure the tool exists to prevent).
# Doubt — a subject that cannot be PROVEN different — drops. Proven-different
# — it shares only family vocabulary or generic title words — survives.

def test_slug_token_subset_drops_even_when_reworded(root):
    # Doubt → drop: the substring test is maskable by rewording, so the
    # second net catches it — every slug token appears in the subject.
    c = cand(root, "support-free-bracket",
             title="support-free-bracket — Tier 1 reference design")
    assert matches_subject(c, "bracket that is support free, by construction")


def test_an_unpronounceable_subject_is_a_doubt_and_drops(root):
    # Doubt → drop: a subject that normalizes to nothing (all stopwords)
    # cannot be proven different from the candidate.
    c = cand(root, "some-design")
    assert matches_subject(c, "the design")


def test_family_word_overlap_alone_is_proven_different(root):
    # Proven-different → survives: two subjects in the same technique
    # family ("constant force") sharing its name but nothing else. Dropping
    # here would mean the family's SECOND design can never be filed —
    # over-matching, not conservatism.
    c = cand(root, "constant-force-slider",
             title="constant-force-slider — quasi-zero-stiffness captive slider")
    assert not matches_subject(c, "constant-force-spring — a different mechanism, same family word")


def test_generic_vocabulary_alone_never_drops(root):
    # Proven-different → survives: the house title vocabulary
    # ("Tier 1 reference design Domain 2") is stopworded, so a subject that
    # shares ONLY that with the candidate is not a doubt.
    c = cand(root, "support-free-bracket",
             title="support-free-bracket — Tier 1 reference design (Domain 2)")
    assert not matches_subject(c, "compliant-gripper — Tier 1 reference design (Domain 2)")


# --- the open-brief list parser ---------------------------------------------

def test_parse_briefs_accepts_space_pipe_and_gh_tab_shapes():
    assert parse_briefs("385 support-free-bracket — Tier 1\n") == [
        (385, "support-free-bracket — Tier 1")
    ]
    assert parse_briefs("386 | snap-cantilever-clip\n") == [
        (386, "snap-cantilever-clip")
    ]
    # gh issue list default output: tab-separated columns; the title is the
    # first tab field, labels and friends are not glued onto it.
    assert parse_briefs("387\tcaptive-spinner\tenhancement,design-brief\t2026-08-26") == [
        (387, "captive-spinner")
    ]
    assert parse_briefs("# comment\n\n388 let-folding-panel\n") == [
        (388, "let-folding-panel")
    ]


@pytest.mark.parametrize(
    "bad",
    [
        "support-free-bracket — no leading number",
        "389",  # a bare number is not a brief — there is no title to dedup on
        "389 ",
        "nope|389 backwards",
    ],
)
def test_parse_briefs_fails_loud_on_malformed_lines(bad):
    with pytest.raises(ValueError, match="open-brief line"):
        parse_briefs(bad + "\n")


def test_an_empty_or_comment_only_list_is_legitimately_empty():
    # The empty backlog is a real state (nothing open yet), not an error —
    # and `printf '' | select -` is the documented way to ask for it.
    assert parse_briefs("") == []
    assert parse_briefs("\n\n# a comment\n") == []


# --- rail 2 addendum: a briefed slug claims itself against a later dup ------

def test_a_decided_dup_of_a_briefed_slug_does_not_reselect(root):
    # Negative control (rail 2): a `briefed` marker claims its slug, so a
    # later duplicate-slug `decided` marker collapses to it and selects
    # nothing — otherwise a subject whose brief was closed-as-declined (not
    # caught by the designs/ rail) could be silently re-filed.
    write_doc(root, "research.md", "\n".join([
        marker("gamma-clip", "gamma-clip — filed", status="briefed", ref=100),
        marker("gamma-clip", "gamma-clip — decided again", status="decided"),
    ]))
    cands = extract(root)
    assert [c.status for c in cands] == ["briefed", "decided"]
    assert select(cands, [], []) is None


def test_a_decided_new_slug_after_a_briefed_one_selects(root):
    # Positive control: the briefed slug is claimed, but a *different* decided
    # slug is untouched by that claim and selects — proving the drop above is
    # the duplicate-slug rail, not the mere presence of a briefed marker.
    write_doc(root, "research.md", "\n".join([
        marker("gamma-clip", "gamma-clip — filed", status="briefed", ref=100),
        marker("delta-clip", "delta-clip — fresh", status="decided"),
    ]))
    got = select(extract(root), [], [])
    assert got is not None and got.slug == "delta-clip"
