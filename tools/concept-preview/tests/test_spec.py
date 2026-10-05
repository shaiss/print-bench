"""The spec parser: the fixture parses, and every refusal fires naming its
line. Each negative is the clean fixture with one defect, so the defect is
the only reason it fails (and a passing fixture proves the rule does not
over-fire)."""

from __future__ import annotations

import pytest
from conftest import BASE, replacing, with_lines, without

from concept_preview import palette as P
from concept_preview.spec import PRIMITIVES, SpecError, parse, vocabulary

APPENDED = len(BASE.rstrip("\n").splitlines()) + 1   # line number of an appended row


def refused(text: str) -> SpecError:
    with pytest.raises(SpecError) as e:
        parse(text, "spec.conf")
    return e.value


def test_fixture_parses_into_four_sheets_parts_and_rows():
    spec = parse(BASE, "spec.conf")
    assert spec.title == "HEX-BOLT CANISTER"
    assert set(spec.sheets) == set(P.SHEETS)
    assert [p.n for p in spec.parts] == ["1", "2", "3", "4"]
    assert {r.kind for r in spec.rows} == set(PRIMITIVES)   # every primitive exercised
    assert set(spec.notes) == set(P.SHEETS)
    # defaults: the exterior heading falls back to the title
    assert spec.sheets["exterior"].heading == "HEX-BOLT CANISTER"
    assert spec.sheets["exterior"].size == (620, 940)
    assert spec.rev == "A" and spec.scale == "NTS" and spec.units == "mm"


def test_rows_keep_file_order_and_line_numbers():
    spec = parse(BASE, "spec.conf")
    lines = [r.line for r in spec.rows]
    assert lines == sorted(lines)
    first = spec.rows[0]
    assert BASE.splitlines()[first.line - 1].startswith(f"{first.kind}:")


def test_comments_and_blank_lines_are_ignored_and_hash_survives_in_values():
    spec = parse(with_lines("", "   # a comment", "leader: section | at=600,700 | to=560,700 | text=M6 #2"), "s")
    assert spec.rows[-1].fields["text"] == "M6 #2"


def test_error_message_names_path_and_line():
    e = refused(with_lines("gear: exterior | at=1,1"))
    assert e.line == APPENDED
    assert str(e).startswith(f"spec.conf:{APPENDED}: ")


@pytest.mark.parametrize("row, needle", [
    ("gear: exterior | at=1,1", "unknown key or primitive 'gear'"),
    ("hex: exterior | at=1,1 | size=10x10 | colour=red", "unknown field 'colour'"),
    ("hex: exterior | at=1,1", "missing required field size="),
    ("hex: exterior | at=1,1 | at=2,2 | size=10x10", "given twice"),
    ("hex: exterior | at=1,1 | size", "is not key=value"),
    ("hex: exterior | at=1,1 || size=10x10", "empty field"),
    ("hex: exterior | at=1,1 | size=10x10 |", "empty field"),
    ("hex: exterior | at=one,1 | size=10x10", "is not an x,y point"),
    ("hex: exterior | at=1,1 | size=10", "is not a WxH size"),
    ("hex: exterior | at=1,1 | size=0x10", "must be positive"),
    ("hex: exterior | at=1,1 | size=10x10 | chamfer=wide", "is not a number"),
    ("hex: exterior | at=1,1 | size=10x10 | chamfer=inf", "is not a number"),
    ("hex: exterior | at=1,1 | size=10x10 | grip=2.5", "is not a whole number"),
    ("hex: exterior | at=1,1 | size=10x10 | ends=left", "must be one of"),
    ("dim: exterior | from=1,1 | to=1,9 | text=x | flip=maybe", "must be yes or no"),
    ("dim: exterior | from=1,1 | to=1,9 | text=x | ext=1,2,3", "one number or two"),
    ("balloon: exterior | at=1,1 | n=1234", "must be 1-3"),
    ("leader: exterior | at=1,1 | to=9,9 | text=   ", "is empty"),
    ("hex: garage | at=1,1 | size=10x10", "unknown sheet 'garage'"),
    ("hex: at=1,1 | size=10x10", "first field must be the sheet name"),
    ("hex exterior at=1,1", "expected 'key: value'"),
    ("hex: ", "has no value"),
    ("rev: B", "rev: given twice"),
    ("balloon: exterior | at=500,500 | n=9", "names no declared part"),
    ("part: n=1 | name=Again", "declared twice"),
    ("part: name=No number", "missing required field n="),
    ("note: exterior | head=Second note", "already has a note"),
    ("note: exterior2 | head=x", "unknown sheet"),
    ("sheet: section", "declared twice"),
    ("hatch: section | at=1,1 | size=5x5 | center=3,3 | r=2", "not both"),
    ("hatch: section | at=1,1", "needs both at= and size="),
    ("hatch: section | ri=4", "needs center= and r="),
    ("hatch: section | at=1,1 | size=5x5 | ri=1", "not both"),
])
def test_each_malformation_is_refused_at_its_line(row, needle):
    e = refused(with_lines(row))
    assert needle in e.message, e.message
    assert e.line == APPENDED


def test_control_characters_in_text_are_refused():
    e = refused(with_lines("leader: exterior | at=1,1 | to=9,9 | text=bell\x07"))
    assert "control character" in e.message


def test_a_hatch_with_neither_form_is_refused():
    e = refused(with_lines("hatch: section"))
    assert "needs at=+size= (rect) or center=+r= (ring)" in e.message


@pytest.mark.parametrize("sheet", P.SHEETS)
def test_every_canonical_sheet_is_required(sheet):
    e = refused(without(f"sheet: {sheet} "))
    assert e.line == 0
    assert f"sheet: {sheet}" in e.message


def test_title_is_required():
    e = refused(without("title:"))
    assert "title:" in e.message and e.line == 0


def test_bom_belongs_on_the_exploded_sheet_only():
    e = refused(replacing("sheet: section | ", "sheet: section | bom=10,10 | "))
    assert "exploded sheet only" in e.message
    e = refused(replacing(" | bom=372,176", ""))
    assert "needs bom=x,y" in e.message


def test_at_least_one_part_is_required():
    e = refused(without("part:"))
    assert "at least one" in e.message


def _line_starting(prefix: str) -> str:
    return next(ln for ln in BASE.splitlines() if ln.startswith(prefix))


def test_note_line_cap():
    four = "note: section | head=WHY | line=a | line=b | line=c | line=d"
    assert parse(replacing(_line_starting("note: section"), four), "s").notes["section"].lines == list("abcd")
    e = refused(replacing(_line_starting("note: section"), four + " | line=e"))
    assert "at most 4" in e.message


@pytest.mark.parametrize("size, ok", [("320x320", True), ("2400x2400", True),
                                      ("319x900", False), ("900x2401", False),
                                      ("620.5x940", False)])
def test_sheet_size_limits(size, ok):
    text = replacing("sheet: exterior | ", f"sheet: exterior | size={size} | ")
    if ok:
        assert parse(text, "s").sheets["exterior"].size == tuple(int(v) for v in size.split("x"))
    else:
        refused(text)


def test_non_utf8_file_is_refused(tmp_path):
    from concept_preview.spec import load
    p = tmp_path / "preview-spec.conf"
    p.write_bytes(b"title: \xff\xfe\n")
    with pytest.raises(SpecError) as e:
        load(p)
    assert "not UTF-8" in e.value.message


def test_vocabulary_lists_every_primitive_and_field():
    text = vocabulary()
    for kind, schema in PRIMITIVES.items():
        assert f"{kind}: <sheet>" in text
        for key in schema:
            assert f"  {key}=" in text
    for sheet in P.SHEETS:
        assert sheet in text
