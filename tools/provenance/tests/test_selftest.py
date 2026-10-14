"""selftest — the suite scripts/provenance.sh --selftest runs.

Owner: H6. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_suite_passes():
    """selftest.run() returns 0 and prints one 'selftest ok' line per case."""


@pytest.mark.skip(reason="builder: implement")
def test_suite_fails_when_a_case_fails():
    """Negative: a case returning False makes run() return 1."""


@pytest.mark.skip(reason="builder: implement")
def test_script_wrapper():
    """scripts/provenance.sh --selftest exits 0; with an unknown flag exits 2."""
