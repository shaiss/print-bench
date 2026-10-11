"""The emitter: four sheets, one drafting system, deterministic bytes, and
furniture that refuses to overflow rather than reflow."""

from __future__ import annotations

import re

import pytest
from conftest import BASE, replacing, with_lines

from concept_preview import palette as P
from concept_preview.emit import FILENAMES, render_all
from concept_preview.spec import SpecError, parse

SPEC = parse(BASE, "valid.conf")
SHEETS = render_all(SPEC)


def test_four_canonical_sheets_in_order():
    assert list(SHEETS) == [f"concept-{k}.svg" for k in P.SHEETS] == list(FILENAMES.values())


def test_the_drafting_system_is_defined_once_and_embedded_identically():
    # The AC: palette / title-block / dimension conventions are defined once
    # and reused by every sheet — drift-proof by construction. Every sheet
    # carries the byte-identical stylesheet and shared defs from palette.py.
    styles = {re.search(r"<style>\n(.*?)\n</style>", s, re.S).group(1) for s in SHEETS.values()}
    defs = {re.search(r"<defs>\n(.*?)\n</defs>", s, re.S).group(1) for s in SHEETS.values()}
    assert styles == {P.stylesheet()}
    assert defs == {P.defs()}


def test_every_colour_on_every_sheet_is_a_palette_token():
    tokens = {v.lower() for k, v in vars(P).items() if k.isupper() and isinstance(v, str)
              and (v.startswith("#") or v.startswith("rgba"))}
    for name, svg in SHEETS.items():
        used = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b|rgba\([^)]*\)", svg)}
        assert used <= tokens, f"{name} uses colours outside the palette: {used - tokens}"


def test_no_web_font_or_network_reference_in_any_sheet():
    for svg in SHEETS.values():
        assert "googleapis" not in svg and "@import" not in svg and "<link" not in svg
        # the only URL in a sheet is the SVG namespace name (an identifier,
        # never fetched)
        assert re.findall(r"https?://\S+", svg) == ['http://www.w3.org/2000/svg"']


def test_output_is_deterministic():
    assert render_all(parse(BASE, "valid.conf")) == SHEETS


@pytest.mark.parametrize("n, kind", list(enumerate(P.SHEETS, 1)))
def test_sheet_numbering_title_block_and_artboard(n, kind):
    svg = SHEETS[f"concept-{kind}.svg"]
    w, h = P.SHEET_DEFAULTS[kind][0]
    assert f'width="{w}" height="{h}" viewBox="0 0 {w} {h}"' in svg
    assert f"SHEET {n} / 4</text>" in svg
    tb = re.search(r'<g class="cp-titleblock"[^>]*>(.*?)</g>', svg).group(1)
    assert "HEX-BOLT CANISTER" in tb and "SCALE NTS · mm · REV A" in tb
    assert svg.count('class="cp-titleblock"') == 1


def test_rows_draw_in_file_order_and_name_their_line():
    svg = SHEETS["concept-exterior.svg"]
    lines = [int(m) for m in re.findall(r'<g class="cp-(?:hatch|shank|hex|dim|balloon|leader)" data-src="L(\d+)"', svg)]
    assert lines == sorted(lines) and len(lines) == len(SPEC.rows_for("exterior"))


def test_bill_of_parts_lists_every_part_on_the_exploded_sheet_only():
    for kind in P.SHEETS:
        svg = SHEETS[f"concept-{kind}.svg"]
        assert ('class="cp-bom"' in svg) == (kind == "exploded")
    bom = re.search(r'<g class="cp-bom"[^>]*>(.*?)</g>', SHEETS["concept-exploded.svg"]).group(1)
    for part in SPEC.parts:
        assert f">{part.name}<" in bom and f">{part.n}<" in bom


def test_size_override_changes_the_artboard():
    svg = render_all(parse(replacing("sheet: section | ", "sheet: section | size=700x800 | "), "s"))
    assert 'viewBox="0 0 700 800"' in svg["concept-section.svg"]


@pytest.mark.parametrize("text, needle", [
    (replacing("title: HEX-BOLT CANISTER", "title: A TITLE TOO LONG FOR THE BLOCK")
     .replace("sheet: exterior | ", "sheet: exterior | heading=SHORT | "),
     "title-block title"),
    (replacing("title: HEX-BOLT CANISTER", "title: A TITLE TOO LONG FOR THE HEADING"),
     "sheet heading"),
    (replacing("sheet: exploded | ", "sheet: exploded | caption=A CAPTION FAR TOO LONG FOR THE BLOCK | "),
     "title-block caption"),
    (replacing("sheet: section | heading=TOP SECTION A–A", "sheet: section | heading=" + "W" * 40),
     "sheet heading"),
    (replacing("part: n=4 | name=Elevator — travelling nut", "part: n=4 | name=Elevator — travelling nut, the long way"),
     "part name"),
    (replacing("part: n=1 | name=Lid — hex cap nut | print=open up", "part: n=1 | name=Lid | print=open side up"),
     "part print note"),
    (replacing("line=the payload circles it, nothing is lost.",
               "line=the payload circles it, and nothing whatsoever is lost along the way"),
     "note line"),
])
def test_furniture_overflow_is_a_spec_error_naming_the_line(text, needle):
    with pytest.raises(SpecError) as e:
        render_all(parse(text, "s"))
    assert needle in e.value.message and e.value.line > 0
    assert "does not wrap" in e.value.message


def test_a_primitive_refusal_becomes_a_spec_error_at_its_row():
    text = with_lines("hex: exterior | at=400,300 | size=100x40 | chamfer=30")
    with pytest.raises(SpecError) as e:
        render_all(parse(text, "s"))
    assert e.value.line == len(BASE.rstrip("\n").splitlines()) + 1
    assert e.value.message.startswith("hex: hex chamfer")


def test_a_note_needs_room_beside_the_title_block():
    section = next(ln for ln in BASE.splitlines() if ln.startswith("sheet: section"))
    text = replacing(section, "sheet: section | size=420x760 | heading=A–A | subtitle=S")
    with pytest.raises(SpecError) as e:
        render_all(parse(text, "s"))
    assert "too narrow for a note" in e.value.message


def test_the_readme_example_spec_builds_clean():
    # The README's worked example is documentation a model will copy; it must
    # stay a spec the tool accepts and draws cleanly.
    from conftest import TOOL

    from concept_preview.build import build_text
    readme = (TOOL / "README.md").read_text(encoding="utf-8")
    example = re.search(r"```text\n(.*?)```", readme, re.S).group(1)
    assert build_text(example, "README.md").findings == []
