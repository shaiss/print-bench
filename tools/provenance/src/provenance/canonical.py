"""Canonical JSON and deterministic gzip — the byte rules every stored file obeys.

Every file the harvester writes to either data ref (``provenance`` evidence,
``provenance-site`` derived) and every committed fixture goes through
:func:`dumps` (JSON text) and, for ``*.json.gz``, :func:`gzip_bytes`. Two runs
over the same inputs therefore write byte-identical blobs, which is what makes
"an identical tree pushes nothing" (docs/provenance.md §Storage) a property of
the bytes rather than a hope.

The rules (docs/provenance.md §Canonical JSON):

* ``sort_keys=True`` at every depth;
* ``indent=1`` with ``separators=(",", ": ")`` — one key per line, so a git
  diff of a derived file is reviewable;
* ``ensure_ascii=False`` — UTF-8 text, never ``\\uXXXX`` escapes for
  non-ASCII (the bytes are UTF-8 encoded on write);
* LF line endings and exactly one trailing ``\\n``;
* no floats — every number in the contract is an integer, so float repr
  drift between Python versions cannot reach a stored byte (:func:`dumps`
  refuses a float anywhere in the value);
* ``NaN``/``Infinity`` refused (``allow_nan=False``).

Gzip: ``mtime=0``, no filename in the header (``filename=""``), compression
level 9, so the gzip stream depends on the JSON bytes alone.

This module is pure: no I/O, no clock.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from typing import Any

#: The gzip compression level every ``*.json.gz`` blob uses.
GZIP_LEVEL = 9


def _refuse_floats(value: Any, path: str = "$") -> None:
    """Raise ``TypeError`` if ``value`` contains a float (or bool-as-number misuse is fine)."""
    if isinstance(value, float):
        raise TypeError(f"{path}: float {value!r} — the provenance contract stores integers only")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path}: non-string key {key!r}")
            _refuse_floats(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _refuse_floats(item, f"{path}[{index}]")


def dumps(value: Any) -> str:
    """Return the canonical JSON text of ``value`` (sorted keys, indent 1, trailing LF).

    Raises ``TypeError`` on a float or a non-string key, ``ValueError`` on
    NaN/Infinity (never reached once floats are refused, kept as a belt).
    """
    _refuse_floats(value)
    text = json.dumps(
        value,
        sort_keys=True,
        indent=1,
        separators=(",", ": "),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text + "\n"


def dumps_bytes(value: Any) -> bytes:
    """``dumps(value)`` encoded as UTF-8."""
    return dumps(value).encode("utf-8")


def gzip_bytes(data: bytes) -> bytes:
    """Deterministic gzip of ``data``: mtime 0, empty filename, level :data:`GZIP_LEVEL`."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0,
                       compresslevel=GZIP_LEVEL) as fh:
        fh.write(data)
    return buf.getvalue()


def dumps_gz(value: Any) -> bytes:
    """Canonical JSON of ``value``, UTF-8 encoded, deterministically gzipped."""
    return gzip_bytes(dumps_bytes(value))


def loads_gz(data: bytes) -> Any:
    """Inverse of :func:`dumps_gz` (any gzip stream of JSON is accepted)."""
    return json.loads(gzip.decompress(data).decode("utf-8"))


def sha256_hex(data: bytes) -> str:
    """Lower-case hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def content_sha256(value: Any) -> str:
    """SHA-256 of the canonical JSON bytes of ``value`` — the digest the bundle's
    ``views_sha256`` map and ``content_sha256`` are built from."""
    return sha256_hex(dumps_bytes(value))


# ---------------------------------------------------------------------------
# The event sort key (docs/provenance.md §Canonical JSON and sort key).

#: Precision rank: a day-precision row sorts before second-precision events
#: that share its timestamp (``YYYY-MM-DDT00:00:00Z``).
PRECISION_RANK = ("day", "second")

#: Source rank: the event-id prefix order used to break timestamp ties. Mirrors
#: site/lib/provenance-contract.json ``enums.source_rank`` (pinned by a test).
SOURCE_RANK = ("issue", "pr", "timeline", "commit", "issuecomment", "review", "status", "run",
               "job", "deployment", "release", "row")


def event_sort_key(event: dict[str, Any]) -> tuple:
    """``(ts, precision rank, source rank, github id, sub-index, id)`` for one event@1.

    * ``github id`` — the first all-digit ``:``-segment after the id prefix
      (``issuecomment:6112250646`` → 6112250646, ``issue:592:filed`` → 592),
      else 0 (``commit:<sha40>``);
    * ``sub-index`` — the last ``:``-segment when it is all-digit and is not
      the github id segment (``row:d:PM.md:<sha16>:2`` → 2), else 0;
    * ``id`` — the full string, the final tie-break.

    The site's provenance adapter (P3a) must sort with the identical rule;
    the contract states it as ``sort_key``.
    """
    ident = event["id"]
    parts = ident.split(":")
    prefix = parts[0]
    rank = SOURCE_RANK.index(prefix) if prefix in SOURCE_RANK else len(SOURCE_RANK)
    gid_index = next((i for i in range(1, len(parts)) if parts[i].isdigit()), None)
    gid = int(parts[gid_index]) if gid_index is not None else 0
    last = len(parts) - 1
    sub = int(parts[last]) if last > 0 and last != gid_index and parts[last].isdigit() else 0
    prec = PRECISION_RANK.index(event.get("ts_precision", "second"))
    return (event["ts"], prec, rank, gid, sub, ident)
