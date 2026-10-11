"""Shared fixtures: a throwaway store per test, and an event builder.

The path shim lets ``python -m pytest tools/agent-memory/tests`` run from a
bare checkout (the docs/contributing/extending.md rule — check.sh runs this
package uninstalled, so the suite must too); CI pip-installs it first anyway.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

#: A routine, clean, unsurprising episode — the shape most runs produce. Each
#: test overrides only the fields its rule is about.
BASE_EVENT = {
    "agent": "design-run",
    "ts": "2026-08-30T16:00:00Z",
    "run_id": "17000000001",
    "issue": 440,
    "design": "czs-slider",
    "action": "sliced the flexure at the default gap",
    "choice": "kept the 0.3 mm chamber",
    "outcome": "fusecheck split 2 bodies; gate green",
    "status": "completed",
    "author": "agent",
    "model": "glm-5.2",
}


def make_event(**over) -> dict:
    ev = dict(BASE_EVENT)
    for k, v in over.items():
        if v is DROP:
            ev.pop(k, None)
        else:
            ev[k] = v
    return ev


class _Drop:
    def __repr__(self) -> str:
        return "DROP"


#: Pass as a value to ``make_event`` to remove a key from the base event.
DROP = _Drop()


@pytest.fixture()
def store(tmp_path: pathlib.Path) -> pathlib.Path:
    """A store root that does not exist yet — record must create what it needs."""
    return tmp_path / "store"
