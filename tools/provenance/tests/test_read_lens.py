"""#646: both refs are a READ LENS — no gate, selector or signoff consumes them.

Owner: H6. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_only_allowed_readers_name_the_refs():
    """Outside site/, tools/provenance/, tools/reeve/ (its two detectors), .github/workflows/provenance.yml and docs/CLAUDE.md/README.md, no file in scripts/, tools/, .github/, .claude/ names 'provenance-site', 'refs/heads/provenance' or 'ref=provenance'."""


@pytest.mark.skip(reason="builder: implement")
def test_injected_reader_fails():
    """Negative control: a synthetic workflow text reading either ref is flagged."""
