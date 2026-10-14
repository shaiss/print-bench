"""The offline negative-control suite behind ``scripts/provenance.sh --selftest`` (run by check.sh).

Each case is a ``(label, callable)`` returning ``True`` when the rule held
(the guard fired, the refusal refused). The suite collects
``gitstore.selftest_cases()`` (guard D / M / 0-byte / guard-file change,
identical tree pushes nothing, every row of
``tests/fixtures/continuity_cases.json`` — ok / foreign / rollback / deleted /
unanchored / bootstrap — a rejected push raising ForeignTip, a failing push's
error free of the token and its base64 — in a throwaway repo with a local
bare remote, no network), ``membership.selftest_cases()`` and
``trust.selftest_cases()``,
prints one ``selftest ok|FAIL <label>`` line per case and returns 0 only
when every case held (house selftest format, cf. reviewer-posted.sh).

Owner: H6 (aggregator); the cases belong to their modules' owners.
"""

from __future__ import annotations

import importlib
import sys
from typing import Callable, Optional, TextIO

Case = tuple[str, Callable[[], bool]]

#: The modules whose ``selftest_cases()`` the suite collects, in run order.
MODULES = ("gitstore", "membership", "trust")


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _failing(label: str) -> Case:
    return label, lambda: False


def cases() -> list[Case]:
    """Every case from every module (import errors are a FAIL, not a skip)."""
    out: list[Case] = []
    for name in MODULES:
        try:
            module = importlib.import_module(f"provenance.{name}")
            got = list(module.selftest_cases())
        except Exception as exc:  # an import error or a scaffold stub is a FAIL, never a skip
            out.append(_failing(f"{name}: cases unavailable ({type(exc).__name__}: "
                                f"{_one_line(exc)[:120]})"))
            continue
        if not got:
            out.append(_failing(f"{name}: selftest_cases() returned no case"))
        for item in got:
            if (not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], str)
                    or not callable(item[1])):
                out.append(_failing(f"{name}: malformed case {_one_line(repr(item))[:80]}"))
                continue
            out.append((f"{name}: {_one_line(item[0])}", item[1]))
    return out


def run(stream: Optional[TextIO] = None) -> int:
    """Run :func:`cases`; 0 when all held, 1 otherwise."""
    out = stream or sys.stdout
    suite = cases()
    failed = 0
    for label, fn in suite:
        try:
            held = fn() is True      # strictly True: a truthy non-bool proves nothing
            note = ""
        except Exception as exc:
            held, note = False, f" (raised {type(exc).__name__}: {_one_line(exc)[:120]})"
        failed += not held
        out.write(f"selftest {'ok' if held else 'FAIL'} {label}{note}\n")
    out.write(f"provenance selftest: {len(suite) - failed} held, {failed} failed\n")
    return 0 if suite and not failed else 1
