"""The offline negative-control suite behind ``scripts/provenance.sh --selftest`` (run by check.sh).

Each case is a ``(label, callable)`` returning ``True`` when the rule held
(the guard fired, the refusal refused). The suite collects
``gitstore.selftest_cases()`` (guard D / M / 0-byte / guard-file change,
identical tree pushes nothing, tip continuity foreign / deleted / bootstrap
/ declared, recover refusing an undeclared sha — in a throwaway repo, no
network), ``membership.selftest_cases()`` and ``trust.selftest_cases()``,
prints one ``selftest ok|FAIL <label>`` line per case and returns 0 only
when every case held (house selftest format, cf. reviewer-posted.sh).

Owner: H6 (aggregator); the cases belong to their modules' owners.
"""

from __future__ import annotations

from typing import Callable

Case = tuple[str, Callable[[], bool]]


def cases() -> list[Case]:
    """Every case from every module (import errors are a FAIL, not a skip)."""
    raise NotImplementedError("builder H6")


def run() -> int:
    """Run :func:`cases`; 0 when all held, 1 otherwise."""
    raise NotImplementedError("builder H6")
