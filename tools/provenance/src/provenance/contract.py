"""Python validator for the closed contract ``site/lib/provenance-contract.json``.

One committed contract, two hand-rolled validators (this one and
``site/lib/provenance-contract.mjs``), no JSON Schema dependency in either
stack (docs/provenance.md §Contract). The type language is stated in the
contract's own ``typelang`` block; the rules this module must implement
exactly, because the Node validator implements the same ones:

* ``obj`` is CLOSED — a key not in ``fields`` (or ``optional_fields``) is an
  error; every ``fields`` key is required; ``null`` is accepted only where the
  type says ``"null": true``.
* ``open`` requires its ``fields`` and ignores extra keys (complete API job
  objects inside receipts).
* ``int`` rejects ``bool`` and any float (``True`` is not ``1`` here).
* ``str`` ``re`` is a FULL match (``re.fullmatch``); ``max`` bounds the
  length in code points.
* ``list`` ``unique`` compares canonical JSON; ``sorted`` means
  ``value == sorted(value)``.
* ``map`` keys full-match ``key``.
* ``ref`` resolves in ``types`` then ``shapes``; ``kindfields`` resolves
  ``field_sets[<the object's own "kind">]`` as a closed ``obj``.
* Errors are collected (never raise on the first) as ``"$.path: message"``
  strings in document order; :func:`check` raises :class:`ContractError`
  carrying all of them.

:func:`validate_tree` checks a whole data-ref tree: ``FORMAT`` bytes; the
guard files equal ``.github/data-branch-guard/*``; every ``receipts/`` path
agrees with its receipt's run id/attempt/date; every ``raw/`` and
``records/`` blob validates against its shape; ``site/bundle.json``'s
``views_sha256`` and ``content_sha256`` recompute.

Owner: H2. tests/test_contract.py must prove each rule with a negative
control, and that the Python and Node validators agree on a shared corpus
(``site/test/fixtures/provenance-bundle.json`` plus one extra-field negative).
"""

from __future__ import annotations

import os
from typing import Any, Optional

from .protocols import TreeReader

#: The contract file, relative to the repository root.
CONTRACT_RELPATH = os.path.join("site", "lib", "provenance-contract.json")
CONTRACT_VERSION = 1


class ContractError(ValueError):
    """A value failed validation; ``errors`` lists every failure."""

    def __init__(self, shape: str, errors: list[str]) -> None:
        super().__init__(f"{shape}: {len(errors)} contract error(s): " + "; ".join(errors[:5]))
        self.shape = shape
        self.errors = errors


def repo_root() -> str:
    """The repository root, from this file's location (tools/provenance/src/provenance/)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def load_contract(path: Optional[str] = None) -> dict[str, Any]:
    """Parse the contract JSON (default: :data:`CONTRACT_RELPATH` under :func:`repo_root`)."""
    raise NotImplementedError("builder H2")


def validate(shape: str, value: Any, contract: Optional[dict[str, Any]] = None) -> list[str]:
    """Every error of ``value`` against ``shapes[shape]`` (``[]`` = valid)."""
    raise NotImplementedError("builder H2")


def check(shape: str, value: Any, contract: Optional[dict[str, Any]] = None) -> None:
    """:func:`validate`, raising :class:`ContractError` when anything fails."""
    raise NotImplementedError("builder H2")


def validate_tree(reader: TreeReader, kind: str, contract: Optional[dict[str, Any]] = None) -> list[str]:
    """Every error of one data-ref tree (``kind`` = ``evidence`` | ``derived``)."""
    raise NotImplementedError("builder H2")
