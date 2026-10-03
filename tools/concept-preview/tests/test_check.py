"""The checker, rule by rule: a clean emitted sheet passes, and each rule
fires on a sheet carrying exactly one defect of its class. Defects are
injected into real emitted sheets (not hand-written toy SVG), so a rule is
proven against the shape the emitter actually produces."""

from __future__ import annotations

import pytest
from conftest import BASE, with_lines

from concept_preview.build import build_text
from concept_preview.check import check_svg
from concept_preview.emit import render_all
from concept_preview.geom import text_box
from concept_preview.spec import parse

SHEETS = render_all(parse(BASE, "valid.conf"))
EXTERIOR = SHEETS["concept-exterior.svg"]


def rules(svg: str) -> set:
    return {f.rule for f in check_svg(svg, "t.svg")}


def inject(svg: str, fragment: str) -> str:
    """Add a fragment just before the closing tag."""
    return svg.replace("\n</svg>", "\n" + fragment + "\n</svg>")


@pytest.mark.parametrize("name", sorted(SHEETS))
def test_every_emitted_sheet_passes_every_check(name):
    assert check_svg(SHEETS[name], name) == []


# ── xml ───────────────────────────────────────────────────────────────────
def test_not_well_formed_is_an_xml_finding():
    assert rules(EXTERIOR.replace("</svg>", "")) == {"xml"}
    assert rules(EXTERIOR.replace("HEX-BOLT", "HEX&BOLT", 1)) == {"xml"}


# ── contract ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("mutate", [
    lambda s: s.replace('viewBox="0 0 620 940"', 'viewBox="10 0 620 940"'),
    lambda s: s.replace('viewBox="0 0 620 940"', 'viewBox="0 0 620"'),
    lambda s: s.replace('width="620" height="940" viewBox', 'width="600" height="940" viewBox'),
    lambda s: inject(s, '<rect x="1" y="1" width="2" height="2"/>'),                  # outside any group
    lambda s: inject(s, '<g class="cp-gear" data-src="L1"><rect x="1" y="1" width="2" height="2"/></g>'),
    lambda s: inject(s, '<g class="cp-hex"><path class="ln" d="M10,10 l5,5"/></g>'),  # relative command
    lambda s: inject(s, '<g class="cp-hex"><path class="ln" d="M10,10 A5 5 0 0 0 20 20"/></g>'),
    lambda s: inject(s, '<g class="cp-hex"><rect x="1" y="1" width="2" height="2" transform="scale(2)"/></g>'),
    lambda s: inject(s, '<g class="cp-leader"><text class="t-lbl" x="300" y="300" font-size="9">a<tspan>b</tspan></text></g>'),
    lambda s: inject(s, '<g class="cp-leader"><text class="t-loud" x="300" y="300" font-size="9">a</text></g>'),
    lambda s: inject(s, '<g class="cp-leader"><text class="t-lbl" x="300" y="300" font-size="9" transform="rotate(30 300 300)">a</text></g>'),
    lambda s: inject(s, '<g class="cp-hex"><g><rect x="1" y="1" width="2" height="2"/></g></g>'),       # nested group
    lambda s: inject(s, '<g class="cp-hex"></g>'),                                    # draws nothing
    lambda s: inject(s, '<g class="cp-hex"><rect x="1" y="1" width="w" height="2"/></g>'),
    # strokes and markers are measured from the palette and the sheet's own
    # <marker>s, so nothing may restyle or re-mark where the checker can't see
    lambda s: s.replace("stroke-width:1.6", "stroke-width:40", 1),
    lambda s: inject(s, '<g class="cp-hex"><rect class="metal" x="300" y="300" width="2" height="2" style="stroke-width:40"/></g>'),
    lambda s: inject(s, '<g class="cp-hex" stroke-width="40"><rect class="metal" x="300" y="300" width="2" height="2"/></g>'),
    lambda s: s.replace('data-sheet="exterior"', 'data-sheet="exterior" stroke-width="40"'),
    lambda s: s.replace("<defs>\n", '<defs stroke-width="40">\n', 1),
    lambda s: s.replace('<marker id="dot"', '<marker id="dot" stroke-width="40"'),
    lambda s: inject(s, '<g class="cp-hex"><path class="ln" d="L300,300 L310,310"/></g>'),
    lambda s: inject(s, '<g class="cp-hex"><path class="ln" stroke-linejoin="arcs" d="M300,300 L310,300 L300,310"/></g>'),
    lambda s: inject(s, '<g class="cp-leader"><path class="lead" d="M300,300 L310,300 L320,310" marker-mid="url(#dot)"/></g>'),
    lambda s: inject(s, '<g class="cp-leader"><path class="lead" d="M300,300 L310,300" marker-end="url(#nope)"/></g>'),
    lambda s: inject(s, '<g class="cp-leader"><path class="lead" d="M300,300 L310,300 L310,310 Z" marker-end="url(#dot)"/></g>'),
    lambda s: s.replace('<marker id="dot"', '<marker id="dot" viewBox="0 0 9 9"'),
], ids=["viewbox-origin", "viewbox-short", "width-mismatch", "loose-element", "unknown-kind",
        "relative-path", "arc-path", "shape-transform", "tspan", "foreign-text-class",
        "odd-rotation", "nested-group", "empty-group", "non-numeric",
        "restyled-stylesheet", "inline-style", "group-presentation-attr", "root-presentation-attr",
        "defs-presentation-attr", "marker-presentation-attr",
        "path-without-moveto", "unmodelled-linejoin", "marker-mid", "unknown-marker",
        "marker-on-closed-outline", "marker-viewbox"])
def test_contract_refuses_what_it_cannot_measure(mutate):
    assert "contract" in rules(mutate(EXTERIOR))


@pytest.mark.parametrize("kind", ["cp-titleblock", "cp-header", "cp-ground"])
def test_title_block_header_and_ground_are_required_once(kind):
    start = EXTERIOR.index(f'<g class="{kind}"')
    end = EXTERIOR.index("</g>", start) + len("</g>")
    missing = EXTERIOR[:start] + EXTERIOR[end:]
    assert "contract" in rules(missing)
    doubled = inject(EXTERIOR, EXTERIOR[start:end])
    assert "contract" in rules(doubled)


# ── external ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("fragment", [
    '<g class="cp-hex"><rect x="1" y="1" width="2" height="2" fill="url(https://cdn.example/x.svg#p)"/></g>',
    '<g class="cp-hex"><rect x="1" y="1" width="2" height="2" onclick="alert(1)"/></g>',
    '<script>alert(1)</script>',
    '<image href="https://cdn.example/x.png" x="0" y="0" width="1" height="1"/>',
    '<g class="cp-hex" xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="https://x/y#z"/></g>',
])
def test_external_references_are_refused(fragment):
    assert "external" in rules(inject(EXTERIOR, fragment))


def test_style_imports_and_remote_urls_are_refused():
    imp = EXTERIOR.replace("<style>\n", "<style>\n@import url(https://fonts.googleapis.com/css2?family=Oswald);\n")
    assert "external" in rules(imp)
    remote = EXTERIOR.replace("<style>\n", "<style>\n.x{background:url(//cdn.example/a.png)}\n")
    assert "external" in rules(remote)


def test_internal_fragment_references_are_allowed():
    # every emitted sheet already uses url(#grid), url(#hatch), url(#dim)...
    assert "url(#" in EXTERIOR and rules(EXTERIOR) == set()


# ── bounds ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("rect", [
    'x="-1" y="300" width="20" height="20"',
    'x="610" y="300" width="20" height="20"',
    'x="300" y="-5" width="20" height="20"',
    'x="300" y="930" width="20" height="20"',
])
def test_an_element_leaving_the_sheet_is_a_bounds_finding(rect):
    found = check_svg(inject(EXTERIOR, f'<g class="cp-hatch" data-src="L99"><rect class="cut" {rect}/></g>'), "t.svg")
    assert {f.rule for f in found} == {"bounds"}
    assert "spec line 99" in found[0].message


def test_paint_flush_with_the_edge_is_in_bounds_and_geometry_flush_is_not():
    # .cut strokes 1.5 px: geometry flush with the edge paints 0.75 px off it.
    paint_flush = '<g class="cp-hatch"><rect class="cut" x="599.25" y="300" width="20" height="20"/></g>'
    geometry_flush = '<g class="cp-hatch"><rect class="cut" x="600" y="300" width="20" height="20"/></g>'
    assert rules(inject(EXTERIOR, paint_flush)) == set()
    assert rules(inject(EXTERIOR, geometry_flush)) == {"bounds"}


@pytest.mark.parametrize("d, out", [
    ("M590,300 L619,310 L590,320", True),    # half-stroke reaches 619.8, the miter tip 621.45
    ("M587,300 L616,310 L587,320", False),   # the same join inset 3 px
    ("M560,300 L619,305 L560,310", False),   # sharper than miterlimit 4: SVG bevels it
])
def test_a_sharp_join_is_measured_to_its_miter_tip(d, out):
    frag = f'<g class="cp-hex"><path class="ln" d="{d}"/></g>'
    assert rules(inject(EXTERIOR, frag)) == ({"bounds"} if out else set())


@pytest.mark.parametrize("row, out", [
    # the leader's dot is a 2.3 px disc centred on the target
    ("leader: exterior | at=60,560 | to=1,560 | text=EDGE", True),
    ("leader: exterior | at=60,560 | to=2.3,560 | text=EDGE", False),
    # the dimension arrowhead's miter tip runs 1.31 px past the line's end
    ("dim: section | from=400,620 | to=679,620 | text=X | ext=600", True),
    ("dim: section | from=400,620 | to=678.6,620 | text=X | ext=600", False),
], ids=["dot-off", "dot-flush", "arrow-off", "arrow-in"])
def test_an_edge_marker_is_measured_by_what_it_paints(row, out):
    found = build_text(with_lines(row), "valid.conf").findings
    assert {f.rule for f in found} == ({"bounds"} if out else set()), found


# ── collision ─────────────────────────────────────────────────────────────
def test_two_overlapping_labels_collide_and_flush_labels_do_not():
    box = text_box(300, 400, "LABEL", 13, "t-lbl")
    a = '<g class="cp-leader" data-src="L1"><text class="t-lbl" x="300" y="400" font-size="13">LABEL</text></g>'
    over = '<g class="cp-leader" data-src="L2"><text class="t-lbl" x="310" y="404" font-size="13">OTHER</text></g>'
    flush = (f'<g class="cp-leader" data-src="L3"><text class="t-lbl" x="{box.x1}" y="400" '
             f'font-size="13">NEXT</text></g>')
    found = check_svg(inject(inject(EXTERIOR, a), over), "t.svg")
    assert {f.rule for f in found} == {"collision"}
    assert "spec line 1" in found[0].message and "spec line 2" in found[0].message
    assert rules(inject(inject(EXTERIOR, a), flush)) == set()


def test_a_label_on_the_title_block_collides():
    tb = '<g class="cp-leader"><text class="t-lbl" x="400" y="860" font-size="13">ON THE TITLE BLOCK</text></g>'
    assert rules(inject(EXTERIOR, tb)) == {"collision"}


def test_a_balloon_on_a_label_collides():
    bal = '<g class="cp-balloon"><circle class="bal" cx="100" cy="206" r="10"/><text class="t-amb" x="100" y="210" font-size="11">9</text></g>'
    assert rules(inject(EXTERIOR, bal)) == {"collision"}


def test_a_shape_intruding_on_the_furniture_collides():
    into_header = '<g class="cp-hex"><rect class="metal" x="300" y="80" width="40" height="40"/></g>'
    into_note = '<g class="cp-hex"><rect class="metal" x="100" y="820" width="40" height="40"/></g>'
    assert rules(inject(EXTERIOR, into_header)) == {"collision"}
    assert rules(inject(EXTERIOR, into_note)) == {"collision"}


@pytest.mark.parametrize("row, crosses", [
    # a leader run down through the title block (and its text)
    ("leader: exterior | at=450,750 | to=450,900 | text=TARGET | anchor=middle", "title block"),
    ("leader: exterior | at=450,750 | to=450,820 | text=TARGET | anchor=middle", None),
    # a leader struck through another leader's label
    ("leader: section | at=100,450 | to=100,300 | text=PROBE | anchor=middle", "'body wall 2.0'"),
    ("leader: section | at=100,450 | to=100,345 | text=PROBE | anchor=middle", None),
    # a balloon's leader run through the bill of parts
    ("balloon: exploded | at=700,700 | n=4 | to=600,150", "bill of parts"),
    ("balloon: exploded | at=700,700 | n=4 | to=600,400", None),
    # a dimension line struck through the exterior's leader labels
    ("dim: exterior | from=90,400 | to=90,700 | text=300", "'THREADED BODY'"),
    ("dim: exterior | from=20,400 | to=20,700 | text=300", None),
    # a diagonal balloon leader starts on its own rim — not a crossing
    ("balloon: section | at=560,470 | n=3 | to=500,530", None),
], ids=["leader-titleblock", "leader-short", "leader-label", "leader-clear",
        "balloon-bom", "balloon-clear", "dim-labels", "dim-clear", "balloon-own-rim"])
def test_a_connecting_line_may_not_cross_a_label_or_the_furniture(row, crosses):
    # Each crossing case passed before segments were checked: the line's own
    # label and target are clear, only the line itself strikes through.
    found = build_text(with_lines(row), "valid.conf").findings
    if crosses is None:
        assert found == []
    else:
        assert {f.rule for f in found} == {"collision"}, found
        assert any(" line " in f.message and " crosses " in f.message and crosses in f.message
                   for f in found), found


def test_a_label_over_a_shape_is_allowed():
    # A balloon sitting on the part it names is a drafting convention (the
    # reference canvas does it); only label-on-label and furniture count.
    on_shank = '<g class="cp-balloon"><circle class="bal" cx="250" cy="400" r="10"/><text class="t-amb" x="250" y="404" font-size="11">3</text></g>'
    assert rules(inject(EXTERIOR, on_shank)) == set()


# ── the text ruler ────────────────────────────────────────────────────────
def test_text_box_model():
    b = text_box(100, 200, "ABCD", 10, "t-lbl")           # 4 x 6 px, no tracking
    assert b.rounded() == (100, 192, 124, 202)
    assert text_box(100, 200, "ABCD", 10, "t-sub").rounded() == (100, 192, 128, 202)  # +1 px tracking
    assert text_box(100, 200, "ABCD", 10, "t-lbl", "end").rounded() == (76, 192, 100, 202)
    assert text_box(100, 200, "ABCD", 10, "t-lbl", "middle").rounded() == (88, 192, 112, 202)
    up = text_box(100, 200, "ABCD", 10, "t-lbl", "middle", rotate=-90)
    assert up.rounded() == (92, 188, 102, 212)
    down = text_box(100, 200, "ABCD", 10, "t-lbl", "middle", rotate=90)
    assert down.rounded() == (98, 188, 108, 212)
    with pytest.raises(ValueError):
        text_box(0, 0, "x", 10, "t-lbl", rotate=45)
