"""The six primitives: each draws where it is told, refuses what it cannot
draw honestly, and reports a footprint the checker's own ruler agrees with
(parity — so the emitter's bookkeeping and the file's actual geometry can
never silently disagree)."""

from __future__ import annotations

import math

import pytest

from concept_preview import palette as P
from concept_preview import primitives as prim
from concept_preview.check import measure
from concept_preview.geom import BBox

CASES = [
    prim.hatched_rect(170, 250, 8, 310),
    prim.hatched_ring(330, 380, 120, 108),
    prim.hatched_ring(330, 380, 30),
    prim.threaded_shank(170, 260, 160, 368, 12, ident="thr-x"),
    prim.hex_head(158, 628, 184, 72, 12, "both", 3),
    prim.hex_head(162, 182, 176, 78, 16, "top"),
    prim.hex_head(10, 10, 80, 30, 0, "none"),
    prim.dimension_line((384, 182), (384, 700), "≈ 130", (338, 342)),
    prim.dimension_line((384, 182), (384, 700), "≈ 130", (420,), flip=True),
    prim.dimension_line((210, 540), (450, 540), "Ø40", (386,)),
    prim.dimension_line((210, 540), (450, 540), "Ø40", (600,), flip=True),
    prim.balloon(120, 176, "1", (196, 176)),
    prim.balloon(250, 420, "*"),
    prim.leader(140, 210, (176, 214), "HEX CAP-NUT LID", "unscrew to open"),
    prim.leader(512, 300, (358, 372), "central screw Ø10"),
    prim.leader(330, 238, (330, 266), "SLOT ×3", anchor="middle"),
    prim.leader(330, 300, (330, 250), "ABOVE", sub="two lines", anchor="middle"),
    prim.leader(140, 474, (170, 470), "Ø40", tone="amber"),
]


@pytest.mark.parametrize("frag", CASES, ids=range(len(CASES)))
def test_footprint_matches_the_checkers_ruler(frag):
    measured, texts = measure(frag.svg)
    assert measured.rounded() == frag.bbox.rounded()
    # every text a primitive draws is one of its declared labels (balloon
    # numbers excepted: the balloon's circle is its label)
    if "<circle class=\"bal\"" not in frag.svg:
        assert sorted(t.rounded() for t in texts) == sorted(b.rounded() for b in frag.labels)


@pytest.mark.parametrize("frag", CASES, ids=range(len(CASES)))
def test_fragments_use_only_palette_classes(frag):
    import re
    for cls in re.findall(r'class="([^"]+)"', frag.svg):
        assert cls in P.SHAPE_CLASSES or cls in P.TEXT_CLASSES, cls


# ── hatched section ───────────────────────────────────────────────────────
def test_ring_leaves_the_bore_unpainted_and_disc_is_one_cut_circle():
    ring = prim.hatched_ring(0 + 200, 200, 50, 40).svg
    assert ring.count("<circle") == 3 and 'class="cut-ring"' in ring and 'stroke-width="10"' in ring
    disc = prim.hatched_ring(200, 200, 50).svg
    assert disc.count("<circle") == 1 and 'class="cut"' in disc


@pytest.mark.parametrize("args", [(10, 10, 0, 5), (10, 10, 5, -1)])
def test_hatched_rect_refuses_degenerate_sizes(args):
    with pytest.raises(ValueError):
        prim.hatched_rect(*args)


@pytest.mark.parametrize("r, ri", [(0, 0), (10, 10), (10, 12), (10, -1)])
def test_hatched_ring_refuses_impossible_radii(r, ri):
    with pytest.raises(ValueError):
        prim.hatched_ring(50, 50, r, ri)


# ── threaded shank ────────────────────────────────────────────────────────
def test_thread_pattern_is_anchored_to_the_shank_so_flanks_land_on_its_edges():
    svg = prim.threaded_shank(230, 300, 40, 260, 11, ident="thr-L9").svg
    assert '<pattern id="thr-L9" x="230" y="300" width="40" height="11"' in svg
    assert 'fill="url(#thr-L9)"' in svg


@pytest.mark.parametrize("w, h, pitch", [(40, 260, 5), (40, 260, 31), (6, 260, 12), (40, 10, 12)])
def test_threaded_shank_refuses_what_it_cannot_draw(w, h, pitch):
    with pytest.raises(ValueError):
        prim.threaded_shank(0, 0, w, h, pitch)


# ── hex head / nut ────────────────────────────────────────────────────────
def test_hex_face_edges_sit_at_the_true_across_corners_quarter_points():
    svg = prim.hex_head(100, 50, 200, 60, 10).svg
    assert 'x1="150" y1="50" x2="150" y2="110"' in svg
    assert 'x1="250" y1="50" x2="250" y2="110"' in svg


def test_hex_chamfer_lines_follow_the_chamfered_ends():
    both = prim.hex_head(0, 0, 100, 40, 8, "both").svg
    top = prim.hex_head(0, 0, 100, 40, 8, "top").svg
    none = prim.hex_head(0, 0, 100, 40, 8, "none").svg
    assert 'y1="8" x2="100" y2="8"' in both and 'y1="32" x2="100" y2="32"' in both
    assert 'y1="8" x2="100" y2="8"' in top and 'y2="32"' not in top
    assert "y1=\"8\" x2=\"100\"" not in none


def test_hex_default_chamfer_is_bounded():
    frag = prim.hex_head(0, 0, 184, 72)
    assert "M0,12 L12,0" in frag.svg


@pytest.mark.parametrize("kw", [
    {"chamfer": 25},                 # >= w/4 on a 100-wide head
    {"chamfer": -1},
    {"chamfer": 20, "ends": "both", "h": 40},   # 2 x 20 eats the whole height
    {"ends": "sideways"},
    {"grip": 3},                     # only 2 ticks fit outboard of the faces on w=100
])
def test_hex_refuses_what_it_cannot_draw(kw):
    h = kw.pop("h", 40)
    with pytest.raises(ValueError):
        prim.hex_head(0, 0, 100, h, **kw)


def test_hex_grip_limit_matches_the_face_edge():
    assert prim.grip_fit(100) == 2
    prim.hex_head(0, 0, 100, 40, grip=2)   # the limit itself draws


# ── dimension line ────────────────────────────────────────────────────────
def test_vertical_dimension_text_sits_beside_the_line_and_flip_mirrors_it():
    right = prim.dimension_line((300, 100), (300, 400), "120").labels[0]
    left = prim.dimension_line((300, 100), (300, 400), "120", flip=True).labels[0]
    assert math.isclose(right.x0, 300 + P.DIM_TEXT_GAP)
    assert math.isclose(left.x1, 300 - P.DIM_TEXT_GAP)
    assert right.y0 < 250 < right.y1          # centred on the line


def test_horizontal_dimension_text_sits_above_and_flip_puts_it_below():
    above = prim.dimension_line((100, 300), (400, 300), "120").labels[0]
    below = prim.dimension_line((100, 300), (400, 300), "120", flip=True).labels[0]
    assert math.isclose(above.y1, 300 - P.DIM_TEXT_GAP)
    assert math.isclose(below.y0, 300 + P.DIM_TEXT_GAP)


def test_extension_lines_run_from_the_feature_past_the_dimension_line():
    svg = prim.dimension_line((384, 182), (384, 700), "x", (338, 342)).svg
    assert '<line class="ln2" x1="338" y1="182" x2="392" y2="182"/>' in svg
    assert '<line class="ln2" x1="342" y1="700" x2="392" y2="700"/>' in svg
    assert 'marker-start="url(#dim)" marker-end="url(#dim)"' in svg


@pytest.mark.parametrize("a, b, ext", [
    ((0, 0), (100, 100), ()),        # diagonal
    ((50, 50), (50, 50), ()),        # zero length
    ((50, 0), (50, 100), (50,)),     # ext on the line itself
    ((50, 0), (50, 100), (1, 2, 3)),
])
def test_dimension_refuses_what_it_cannot_draw(a, b, ext):
    with pytest.raises(ValueError):
        prim.dimension_line(a, b, "x", ext)


# ── balloon ───────────────────────────────────────────────────────────────
def test_balloon_leader_starts_at_the_rim():
    svg = prim.balloon(100, 100, "2", (150, 100)).svg
    assert 'x1="110" y1="100" x2="150" y2="100"' in svg


@pytest.mark.parametrize("n, to", [("1234", None), ("", None), ("1", (103, 103))])
def test_balloon_refuses_what_it_cannot_draw(n, to):
    with pytest.raises(ValueError):
        prim.balloon(100, 100, n, to)


# ── leader ────────────────────────────────────────────────────────────────
def test_leader_anchor_defaults_from_the_target_side():
    right = prim.leader(140, 210, (176, 214), "LID")
    left = prim.leader(512, 300, (358, 372), "SCREW")
    assert 'text-anchor="end"' in right.svg
    assert "text-anchor" not in left.svg            # start is the SVG default
    assert right.labels[0].x1 == 140 and left.labels[0].x0 == 512


def test_leader_second_line_sits_below_without_touching():
    frag = prim.leader(140, 210, (176, 214), "HEX CAP-NUT LID", "unscrew to open")
    main, sub = frag.labels
    assert sub.y0 > main.y1
    assert '<text class="t-sub"' in frag.svg


def test_amber_tone_is_the_callout_voice():
    assert '<text class="t-amb"' in prim.leader(140, 474, (170, 470), "Ø40", tone="amber").svg


@pytest.mark.parametrize("kw", [
    {"to": (100, 214), "anchor": "end"},      # target behind an end-anchored label
    {"to": (200, 214), "anchor": "start"},    # target behind a start-anchored label
    {"to": (146, 206.1)},                     # target on the leader's own start point
    {"to": (176, 214), "tone": "loud"},
    {"to": (176, 214), "anchor": "left"},
    {"to": (176, 214), "text": ""},
])
def test_leader_refuses_what_it_cannot_draw(kw):
    args = {"x": 140, "y": 210, "text": "LID"} | kw
    with pytest.raises(ValueError):
        prim.leader(**args)


def test_bbox_overlap_is_positive_area_only():
    a = BBox(0, 0, 10, 10)
    assert a.overlaps(BBox(9, 9, 20, 20))
    assert not a.overlaps(BBox(10, 0, 20, 10))     # flush edges do not collide
    assert not a.overlaps(BBox(11, 0, 20, 10))


@pytest.mark.parametrize("a, b, crosses", [
    ((-5, 5), (15, 5), True),       # straight through
    ((-5, -5), (15, 15), True),     # through on the diagonal
    ((2, 2), (8, 8), True),         # wholly inside
    ((5, 5), (5, 20), True),        # starts inside, leaves
    ((-5, 0), (15, 0), False),      # runs along an edge (flush)
    ((10, -5), (10, 15), False),
    ((-5, 5), (5, 15), False),      # touches only the corner at (0,10)
    ((-5, 5), (0, 5), False),       # ends on an edge
    ((20, 0), (30, 30), False),     # elsewhere entirely
    ((5, 5), (5, 5), False),        # a point is not a crossing
])
def test_bbox_is_crossed_only_by_a_segment_through_its_interior(a, b, crosses):
    assert BBox(0, 0, 10, 10).crossed_by(a, b) is crosses
