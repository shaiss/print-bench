"""The growth approval-board Stage policy, plus the two drift guards that keep
it in lockstep with the bash provisioning recipe and Lark's marker strings.

A positive case per Stage and a negative control per precedence rule — the
house discipline — because a board that mislabels where a post sits is worse
than no board: a human would approve the wrong card.
"""

from pathlib import Path

from growth import board
from growth.board import (
    BOARD_STAGE_OPTIONS,
    DRYRUN_MARKER,
    POSTED_MARKER,
    stage_of,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _item(state="open", labels=(), comments="", **extra):
    it = {"state": state, "labels": [{"name": n} for n in labels],
          "comments": comments, "url": "https://github.com/x/y/issues/1"}
    it.update(extra)
    return it


# ---- one positive case per Stage ------------------------------------------

def test_filed_but_undrafted_is_queued():
    assert stage_of(_item(labels=["growth-queue", "channel:twitter"])) == "Queued"


def test_dry_run_comment_is_drafted():
    assert stage_of(_item(labels=["growth-queue"], comments=DRYRUN_MARKER)) == "Drafted"


def test_approved_label_is_approved():
    it = _item(labels=["growth-queue", "approved-to-post"], comments=DRYRUN_MARKER)
    assert stage_of(it) == "Approved"


def test_posted_and_closed_is_posted():
    it = _item(state="closed", labels=["growth-queue"], comments=POSTED_MARKER)
    assert stage_of(it) == "Posted"


def test_needs_decision_is_parked():
    it = _item(labels=["growth-queue", "needs-decision"], comments=DRYRUN_MARKER)
    assert stage_of(it) == "Parked"


def test_posted_marker_but_still_open_is_attention():
    # A claim was written (posted marker) but the issue never closed — a
    # mid-thread failure or an in-flight post a human must look at.
    it = _item(state="open", labels=["growth-queue"], comments=POSTED_MARKER)
    assert stage_of(it) == "Attention"


# ---- negative controls: the precedence order actually bites ---------------

def test_closed_without_a_posted_marker_is_not_a_card():
    # A human closed/rejected the item; it must not appear as Posted.
    assert stage_of(_item(state="closed", labels=["growth-queue"])) is None


def test_posted_beats_every_open_label():
    # An open claim outranks approval/parking — Attention wins, not Approved.
    it = _item(state="open",
               labels=["growth-queue", "approved-to-post", "needs-decision"],
               comments=POSTED_MARKER + "\n" + DRYRUN_MARKER)
    assert stage_of(it) == "Attention"


def test_parked_beats_approved():
    it = _item(labels=["growth-queue", "approved-to-post", "needs-decision"])
    assert stage_of(it) == "Parked"


def test_approved_beats_drafted():
    it = _item(labels=["growth-queue", "approved-to-post"], comments=DRYRUN_MARKER)
    assert stage_of(it) == "Approved"


def test_posted_closed_beats_labels():
    it = _item(state="closed", labels=["growth-queue", "needs-decision"],
               comments=POSTED_MARKER)
    assert stage_of(it) == "Posted"


# ---- shape tolerance -------------------------------------------------------

def test_plain_string_labels_work():
    assert stage_of({"state": "open", "labels": ["growth-queue", "needs-decision"]}) == "Parked"


def test_explicit_marker_booleans_override_comments():
    # A caller that pre-scanned can pass booleans instead of raw comment text.
    assert stage_of({"state": "open", "labels": ["growth-queue"],
                     "has_dryrun_marker": True}) == "Drafted"
    assert stage_of({"state": "closed", "labels": ["growth-queue"],
                     "has_posted_marker": True}) == "Posted"


def test_every_returned_stage_is_a_real_board_option():
    options = set(BOARD_STAGE_OPTIONS.split(","))
    for it in (
        _item(labels=["growth-queue"]),
        _item(labels=["growth-queue"], comments=DRYRUN_MARKER),
        _item(labels=["growth-queue", "approved-to-post"]),
        _item(state="closed", labels=["growth-queue"], comments=POSTED_MARKER),
        _item(labels=["growth-queue", "needs-decision"]),
        _item(state="open", labels=["growth-queue"], comments=POSTED_MARKER),
    ):
        assert stage_of(it) in options


# ---- drift guards: the policy vs the two files that must agree with it -----

def test_stage_options_match_the_gh_project_growth_board_spec():
    """scripts/gh-project.sh provisions the board; this policy fills its Stage.
    If the two named different stages, the sync would set a Stage the board has
    no option for and every write would fail. Pin them together."""
    text = (REPO_ROOT / "scripts" / "gh-project.sh").read_text(encoding="utf-8")
    assert f'STAGE_OPTIONS="{BOARD_STAGE_OPTIONS}"' in text, (
        "the `growth` board's STAGE_OPTIONS in scripts/gh-project.sh must equal "
        f"growth.board.BOARD_STAGE_OPTIONS ({BOARD_STAGE_OPTIONS!r})")


def test_marker_strings_match_the_posting_tool():
    """growth_mcp.py writes the markers; this policy reads them. It imports
    nothing from here (stdlib-only), so the strings are duplicated — assert the
    copies agree, or a rename there silently blinds the board."""
    text = (REPO_ROOT / ".claude" / "skills" / "growth-twitter"
            / "growth_mcp.py").read_text(encoding="utf-8")
    assert f'POSTED_MARKER = "{POSTED_MARKER}"' in text
    assert f'DRYRUN_MARKER = "{DRYRUN_MARKER}"' in text
