"""canonical: the byte rules (scaffold-implemented; H2 owns from here)."""

from __future__ import annotations

import gzip
import json

import pytest

from conftest import contract
from provenance import canonical


def test_dumps_is_sorted_indent1_lf_trailing_newline():
    text = canonical.dumps({"b": [1, {"d": 2, "c": "é"}], "a": None})
    assert text == '{\n "a": null,\n "b": [\n  1,\n  {\n   "c": "é",\n   "d": 2\n  }\n ]\n}\n'


def test_floats_and_non_string_keys_are_refused():
    with pytest.raises(TypeError):
        canonical.dumps({"x": 1.5})
    with pytest.raises(TypeError):
        canonical.dumps({1: "x"})


def test_gzip_is_deterministic_and_round_trips():
    a = canonical.dumps_gz({"k": "v"})
    b = canonical.dumps_gz({"k": "v"})
    assert a == b
    assert a[4:8] == b"\x00\x00\x00\x00"  # mtime 0 in the gzip header
    assert json.loads(gzip.decompress(a)) == {"k": "v"}
    assert canonical.loads_gz(a) == {"k": "v"}


def test_sort_key_orders_ties_by_precision_source_and_id():
    day = {"id": "row:d:PM.md:" + "0" * 16 + ":0", "ts": "2026-10-05T00:00:00Z", "ts_precision": "day"}
    issue = {"id": "issue:592:filed", "ts": "2026-10-05T00:00:00Z", "ts_precision": "second"}
    c1 = {"id": "issuecomment:5", "ts": "2026-10-05T00:00:00Z", "ts_precision": "second"}
    c2 = {"id": "issuecomment:40", "ts": "2026-10-05T00:00:00Z", "ts_precision": "second"}
    later = {"id": "commit:" + "a" * 40, "ts": "2026-10-05T00:00:01Z", "ts_precision": "second"}
    events = [later, c2, c1, issue, day]
    assert sorted(events, key=canonical.event_sort_key) == [day, issue, c1, c2, later]


def test_source_rank_matches_the_contract():
    assert list(canonical.SOURCE_RANK) == contract()["enums"]["source_rank"]
    assert list(canonical.PRECISION_RANK) == contract()["enums"]["precision_rank"]
