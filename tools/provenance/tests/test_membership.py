"""membership — the refined file-kind rule over fixtures/membership/pr_files.json.gz vs the audit labels.

Owner: H2. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_tuned_sets_precision_and_recall():
    """Over sbc-case, alcove-rod-socket, constant-force-slider, nuggs-turnaround, snap-clamshell-box ground truth (the audit's hand labels, GAP2): P = 1.00 and R = 1.00."""


@pytest.mark.skip(reason="builder: implement")
def test_held_out_sets():
    """Over sweetheart-hamster, preroll-elevator, pip-ratchet, ovodyo: P >= 0.94 and R = 1.00 (the known FP is #381)."""


@pytest.mark.skip(reason="builder: implement")
def test_verdicts_match_membership_csv():
    """For every row of audits/.../membership.csv whose PR is in pr_files, classify_pr's verdict maps to the CSV verdict (member / member:ai-shot→member / regen-only / excluded:catalog-sweep→sweep / excluded:stacked-base→stacked-excluded)."""


@pytest.mark.skip(reason="builder: implement")
def test_cc1_main_commit_classes():
    """CC-1 from the calibration-cube golden full main.commit events (refs.files, refs.parents): (54, 49, 19, 19, 11)."""


@pytest.mark.skip(reason="builder: implement")
def test_file_kind_table():
    """cameras.conf → source, CAMERAS.md → docs, lifestyle-x.png → ai, .regen-stamp → stamp, a.png → previews."""
