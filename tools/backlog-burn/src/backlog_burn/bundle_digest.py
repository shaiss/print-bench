"""Ship-bundle digest handoff check (mirrors backlog-burn.yml bundle_verify).

``match`` is True only when both digests are nonempty and equal. The workflow
writes ``match=true`` solely on that path; otherwise ``match=false`` (or the
step is skipped and the output is absent).
"""

from __future__ import annotations


def digest_match(expect_sha: str | None, got_sha: str | None) -> bool:
    """Return True iff ``got_sha`` equals a nonempty ``expect_sha``."""
    if not expect_sha or not got_sha:
        return False
    return expect_sha == got_sha
