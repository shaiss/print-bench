"""contract — the hand-rolled Python validator (one negative control per typelang rule).

Owner: H2. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_every_fixture_validates():
    """All fixtures/raw/**, fixtures/receipts/** validate against raw-*@1 / receipt@1."""


@pytest.mark.skip(reason="builder: implement")
def test_closed_object_refuses_an_extra_field():
    """Negative: one extra key anywhere → an error naming the path (P1d: 'both reject a fixture with an extra field')."""


@pytest.mark.skip(reason="builder: implement")
def test_int_refuses_bool_and_float():
    """Negative: True and 1.0 are not ints."""


@pytest.mark.skip(reason="builder: implement")
def test_patterns_fullmatch():
    """Negative: a sha with a trailing newline or a 41st char fails."""


@pytest.mark.skip(reason="builder: implement")
def test_kindfields_closed_per_kind():
    """Negative: review.signoff fields with a triage key fail; every contract kind has a field set."""


@pytest.mark.skip(reason="builder: implement")
def test_no_fixture_field_outside_the_contract():
    """P1a: a walk of every committed fixture finds no key the contract does not name, so no prose is present."""


@pytest.mark.skip(reason="builder: implement")
def test_python_and_node_agree():
    """When node is on PATH: site/lib/provenance-contract.mjs gives the same accept/reject verdicts as contract.validate on a shared corpus (the fixture bundle, the extra-field negative, a bad-enum negative)."""
