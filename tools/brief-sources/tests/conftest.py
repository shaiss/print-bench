"""Shared fixtures: a throwaway repo shape (docs/ + designs/) per test.

Every fixture lives under pytest's ``tmp_path`` — the ``--root`` isolation
AC1 demands. The helper names say which half of a positive/negative pair a
doc plays: ``older``/``newer`` for ordering, ``decided``/``briefed`` for the
status rail.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


def marker(slug: str, title: str | None = None, *, status: str = "decided",
           ref: int | None = None, doc: str | None = None,
           anchor: str = "the-section") -> str:
    """Build one marker line, defaulting to the un-filed `decided` shape.

    `doc=None` (the default) emits the ``@self`` placeholder, which
    `write_doc` rewrites to the doc actually being written — so a fixture
    marker's provenance is always its own file, as the convention requires.
    Pass an explicit ``doc=`` only to test the mismatch error.
    """
    title = title if title is not None else f"{slug} — a decided demonstrator"
    doc = doc if doc is not None else "@self"
    fields = [
        slug,
        title,
        f"source={doc}#{anchor}",
        f"status={status}",
    ]
    if ref is not None:
        fields[-1] += f" ref={ref}"
    return "<!-- brief-candidate: " + " | ".join(fields) + " -->"


def write_doc(root: Path, name: str, body: str) -> Path:
    doc = root / "docs" / name
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        textwrap.dedent(body).replace("source=@self#", f"source=docs/{name}#"),
        encoding="utf-8",
    )
    return doc


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    """An empty repo shape: docs/ and designs/ exist, nothing in them."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "designs").mkdir()
    return tmp_path
