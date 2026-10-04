"""The six drafting primitives — pure functions from explicit coordinates to
one SVG fragment plus its footprint.

Each returns a :class:`Fragment`: the SVG elements (unwrapped — the emitter
adds the ``<g class="cp-<kind>">`` group that names the spec line), the
bounding box of everything drawn, and the label footprints (text and
balloons) the collision check holds pairwise disjoint.

Placement is explicit by design: a primitive draws exactly where it is told
and never nudges, wraps or reflows anything. A primitive refuses (raises
:class:`ValueError`) only a request it cannot draw honestly — a chamfer
wider than a hex face, a leader whose target sits behind its own label —
and the emitter turns that into a spec error naming the line.

Every element uses absolute coordinates and only the element/path vocabulary
the checker can measure (:mod:`concept_preview.check`), so the checker can
re-derive each footprint from the file instead of trusting this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import palette as P
from .geom import BBox, esc, fmt, text_box, union_all

Point = tuple[float, float]


@dataclass(frozen=True)
class Fragment:
    svg: str
    bbox: BBox
    labels: tuple[BBox, ...] = ()


def _pts(points) -> str:
    return " L".join(f"{fmt(x)},{fmt(y)}" for x, y in points)


def _line(cls: str, a: Point, b: Point, extra: str = "") -> str:
    return (f'<line class="{cls}" x1="{fmt(a[0])}" y1="{fmt(a[1])}" '
            f'x2="{fmt(b[0])}" y2="{fmt(b[1])}"{extra}/>')


def _text(cls: str, x: float, y: float, size: float, text: str,
          anchor: str = "start", rotate: float = 0) -> str:
    attrs = f'class="{cls}" x="{fmt(x)}" y="{fmt(y)}" font-size="{fmt(size)}"'
    if anchor != "start":
        attrs += f' text-anchor="{anchor}"'
    if rotate:
        attrs += f' transform="rotate({fmt(rotate)} {fmt(x)} {fmt(y)})"'
    return f"<text {attrs}>{esc(text)}</text>"


# ── 1. hatched section ────────────────────────────────────────────────────
def hatched_rect(x: float, y: float, w: float, h: float) -> Fragment:
    """A cut face in a half-section: the wall or nut the cutting plane
    passes through, hatched at 45°."""
    if w <= 0 or h <= 0:
        raise ValueError("hatched section needs a positive size")
    svg = (f'<rect class="cut" x="{fmt(x)}" y="{fmt(y)}" '
           f'width="{fmt(w)}" height="{fmt(h)}"/>')
    return Fragment(svg, BBox(x, y, x + w, y + h))


def hatched_ring(cx: float, cy: float, r: float, ri: float = 0.0) -> Fragment:
    """A cut ring (a tube wall in plan section) — or, with ``ri=0``, a cut
    solid disc (a screw in plan section). The hatch is the stroke paint of a
    mid-radius circle, so the bore stays genuinely empty (the grid shows
    through) instead of being painted over."""
    if r <= 0:
        raise ValueError("hatched section ring needs r > 0")
    if not 0 <= ri < r:
        raise ValueError(f"hatched section ring needs 0 <= ri < r (ri={fmt(ri)}, r={fmt(r)})")
    c = f'cx="{fmt(cx)}" cy="{fmt(cy)}"'
    if ri == 0:
        svg = f'<circle class="cut" {c} r="{fmt(r)}"/>'
    else:
        svg = (f'<circle class="cut-ring" {c} r="{fmt((r + ri) / 2)}" '
               f'stroke-width="{fmt(r - ri)}"/>'
               f'<circle class="ln" {c} r="{fmt(r)}"/>'
               f'<circle class="ln" {c} r="{fmt(ri)}"/>')
    return Fragment(svg, BBox(cx - r, cy - r, cx + r, cy + r))


# ── 2. threaded shank ─────────────────────────────────────────────────────
def threaded_shank(x: float, y: float, w: float, h: float, pitch: float = 12,
                   ident: str = "thr") -> Fragment:
    """A threaded shank in side elevation: the body outline, a thread
    profile repeating every ``pitch`` px (crest lines across, the V flanks
    on both sides), and heavy flank lines. The pattern is anchored to the
    shank's own origin and width, so its flanks land on the shank's edges
    whatever the shank's position."""
    if w < 8 or h <= 0:
        raise ValueError("threaded shank needs w >= 8 and h > 0")
    if not 6 <= pitch <= 30:
        raise ValueError(f"thread pitch must be 6..30 px (got {fmt(pitch)})")
    if h < pitch:
        raise ValueError(f"threaded shank is shorter ({fmt(h)}) than one pitch ({fmt(pitch)})")
    tooth = min(7.0, w / 6)
    depth = pitch * 0.55
    pattern = (f'<defs><pattern id="{ident}" x="{fmt(x)}" y="{fmt(y)}" '
               f'width="{fmt(w)}" height="{fmt(pitch)}" patternUnits="userSpaceOnUse">'
               f'<path d="M0,3 H{fmt(w)} M0,3 L{fmt(tooth)},{fmt(3 + depth)} '
               f'M{fmt(w)},3 L{fmt(w - tooth)},{fmt(3 + depth)}" fill="none" '
               f'stroke="{P.THREAD}" stroke-width="1"/></pattern></defs>')
    svg = (pattern
           + f'<rect class="metal" x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>'
           + f'<rect x="{fmt(x + 1)}" y="{fmt(y + 1)}" width="{fmt(w - 2)}" '
           f'height="{fmt(h - 2)}" fill="url(#{ident})" opacity="0.9"/>'
           + _line("ln", (x, y), (x, y + h))
           + _line("ln", (x + w, y), (x + w, y + h)))
    return Fragment(svg, BBox(x, y, x + w, y + h))


# ── 3. hex head / nut ─────────────────────────────────────────────────────
HEX_ENDS = ("both", "top", "bottom", "none")


def hex_head(x: float, y: float, w: float, h: float, chamfer: float | None = None,
             ends: str = "both", grip: int = 0) -> Fragment:
    """A hex head or nut in side elevation, viewed across the corners: the
    outline with 45° chamfers on the chosen ends, the two face edges at the
    true across-corners positions (a quarter-width in from each side), a
    chamfer line per chamfered end, and optional knurl ticks for a grip."""
    if w <= 0 or h <= 0:
        raise ValueError("hex head needs a positive size")
    if ends not in HEX_ENDS:
        raise ValueError(f"hex ends must be one of {', '.join(HEX_ENDS)} (got {ends!r})")
    c = min(w / 8, h / 4, 12.0) if chamfer is None else chamfer
    if c < 0 or c >= w / 4:
        raise ValueError(f"hex chamfer {fmt(c)} must be >= 0 and narrower than a face (< {fmt(w / 4)})")
    n_cham = {"both": 2, "top": 1, "bottom": 1, "none": 0}[ends]
    if n_cham * c >= h:
        raise ValueError(f"hex chamfer {fmt(c)} leaves no flat height on a {fmt(h)} px head")
    if grip < 0 or (grip and grip_fit(w) < grip):
        raise ValueError(f"hex grip of {grip} ticks does not fit inside the outer faces "
                         f"(max {grip_fit(w)} on a {fmt(w)} px head)")
    top = ends in ("both", "top")
    bot = ends in ("both", "bottom")
    pts = ([(x, y + c), (x + c, y), (x + w - c, y), (x + w, y + c)] if top
           else [(x, y), (x + w, y)])
    pts += ([(x + w, y + h - c), (x + w - c, y + h), (x + c, y + h), (x, y + h - c)] if bot
            else [(x + w, y + h), (x, y + h)])
    parts = [f'<path class="metal" d="M{_pts(pts)} Z"/>']
    for fx in (x + w / 4, x + 3 * w / 4):
        parts.append(_line("ln2", (fx, y), (fx, y + h)))
    if top and c > 0:
        parts.append(_line("ln2", (x, y + c), (x + w, y + c)))
    if bot and c > 0:
        parts.append(_line("ln2", (x, y + h - c), (x + w, y + h - c)))
    for i in range(grip):
        for gx in (x + P.GRIP_PITCH * (i + 1), x + w - P.GRIP_PITCH * (i + 1)):
            parts.append(_line("ln2", (gx, y + 0.3 * h), (gx, y + 0.8 * h)))
    return Fragment("".join(parts), BBox(x, y, x + w, y + h))


def grip_fit(w: float) -> int:
    """Most knurl ticks that stay outboard of a hex's face edges."""
    return max(0, int((w / 4 - 2) // P.GRIP_PITCH))


# ── 4. dimension line ─────────────────────────────────────────────────────
def dimension_line(a: Point, b: Point, text: str, ext: tuple[float, ...] = (),
                   flip: bool = False) -> Fragment:
    """An axis-aligned dimension: the amber line with arrowheads at both
    ends, optional extension lines from the feature (``ext`` is the
    feature's coordinate on the perpendicular axis — one value for both
    ends, or one per end), and the value text beside the line (right of a
    vertical dimension, reading upward; above a horizontal one; ``flip``
    puts it on the other side)."""
    if not text:
        raise ValueError("dimension needs its text")
    vertical = math.isclose(a[0], b[0])
    horizontal = math.isclose(a[1], b[1])
    if vertical == horizontal:
        raise ValueError("dimension must be axis-aligned and non-zero "
                         f"(from {fmt(a[0])},{fmt(a[1])} to {fmt(b[0])},{fmt(b[1])})")
    if len(ext) not in (0, 1, 2):
        raise ValueError("dimension ext takes one value, or one per end")
    exts = (ext[0], ext[0]) if len(ext) == 1 else tuple(ext)
    s = P.SIZE_DIM
    parts = [_line("dimln", a, b, ' marker-start="url(#dim)" marker-end="url(#dim)"')]
    boxes = [BBox.of_points([a, b])]
    for end, e in zip((a, b), exts):
        if vertical:
            if math.isclose(e, end[0]):
                raise ValueError("dimension ext coordinate sits on the dimension line itself")
            tip = end[0] + (P.DIM_EXT_OVERSHOOT if end[0] > e else -P.DIM_EXT_OVERSHOOT)
            p, q = (e, end[1]), (tip, end[1])
        else:
            if math.isclose(e, end[1]):
                raise ValueError("dimension ext coordinate sits on the dimension line itself")
            tip = end[1] + (P.DIM_EXT_OVERSHOOT if end[1] > e else -P.DIM_EXT_OVERSHOOT)
            p, q = (end[0], e), (end[0], tip)
        parts.insert(0, _line("ln2", p, q))
        boxes.append(BBox.of_points([p, q]))
    if vertical:
        ty = (a[1] + b[1]) / 2
        tx = (a[0] - P.DIM_TEXT_GAP - P.DESCENT * s) if flip else (a[0] + P.DIM_TEXT_GAP + P.ASCENT * s)
        label = text_box(tx, ty, text, s, "t-amb", "middle", rotate=-90)
        parts.append(_text("t-amb", tx, ty, s, text, "middle", rotate=-90))
    else:
        tx = (a[0] + b[0]) / 2
        ty = (a[1] + P.DIM_TEXT_GAP + P.ASCENT * s) if flip else (a[1] - P.DIM_TEXT_GAP - P.DESCENT * s)
        label = text_box(tx, ty, text, s, "t-amb", "middle")
        parts.append(_text("t-amb", tx, ty, s, text, "middle"))
    boxes.append(label)
    return Fragment("".join(parts), union_all(boxes), (label,))


# ── 5. balloon ────────────────────────────────────────────────────────────
def balloon(cx: float, cy: float, n: str, to: Point | None = None) -> Fragment:
    """A numbered part balloon, optionally with a plain leader from its rim
    to the part. The number keys the exploded sheet's bill of parts."""
    if not 1 <= len(n) <= 3:
        raise ValueError(f"balloon number must be 1-3 characters (got {n!r})")
    r = P.BALLOON_R
    parts = []
    boxes = [BBox(cx - r, cy - r, cx + r, cy + r)]
    if to is not None:
        dx, dy = to[0] - cx, to[1] - cy
        dist = math.hypot(dx, dy)
        if dist <= r:
            raise ValueError("balloon leader target lies inside the balloon")
        rim = (cx + r * dx / dist, cy + r * dy / dist)
        parts.append(_line("lead", rim, to))
        boxes.append(BBox.of_points([rim, to]))
    parts.append(f'<circle class="bal" cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}"/>')
    parts.append(_text("t-amb", cx, cy + 4, P.SIZE_BALLOON, n, "middle"))
    return Fragment("".join(parts), union_all(boxes), (boxes[0],))


# ── 6. leader ─────────────────────────────────────────────────────────────
LEADER_ANCHORS = ("start", "middle", "end")
LEADER_TONES = ("label", "amber")


def leader(x: float, y: float, to: Point, text: str, sub: str | None = None,
           anchor: str | None = None, tone: str = "label") -> Fragment:
    """A label with a leader ending in a dot on the feature it names.
    ``(x, y)`` is the label's baseline anchor; ``anchor`` defaults to
    ``end`` when the target is to the right (the label reads into its
    leader) and ``start`` when it is to the left. ``tone=amber`` is the
    callout voice — a diameter, a bolt-circle — in the accent colour."""
    if not text:
        raise ValueError("leader needs its text")
    if tone not in LEADER_TONES:
        raise ValueError(f"leader tone must be one of {', '.join(LEADER_TONES)}")
    if anchor is None:
        anchor = "end" if to[0] >= x else "start"
    if anchor not in LEADER_ANCHORS:
        raise ValueError(f"leader anchor must be one of {', '.join(LEADER_ANCHORS)}")
    cls, size = ("t-lbl", P.SIZE_LABEL) if tone == "label" else ("t-amb", P.SIZE_CALLOUT)
    if anchor == "end":
        if to[0] <= x:
            raise ValueError("leader target lies behind its own label (anchor=end needs the target to the right)")
        start = (x + P.LEADER_GAP, y - 0.3 * size)
    elif anchor == "start":
        if to[0] >= x:
            raise ValueError("leader target lies behind its own label (anchor=start needs the target to the left)")
        start = (x - P.LEADER_GAP, y - 0.3 * size)
    else:
        if to[1] >= y:
            bottom = (y + P.LABEL_SUB_DY + P.DESCENT * P.SIZE_LABEL_SUB) if sub else (y + P.DESCENT * size)
            start = (x, bottom + 4)
        else:
            start = (x, y - P.ASCENT * size - 4)
    if math.hypot(to[0] - start[0], to[1] - start[1]) < 4:
        raise ValueError("leader is too short to draw (target sits on the label)")
    labels = [text_box(x, y, text, size, cls, anchor)]
    parts = [f'<path class="lead" d="M{fmt(start[0])},{fmt(start[1])} '
             f'L{fmt(to[0])},{fmt(to[1])}" marker-end="url(#dot)"/>',
             _text(cls, x, y, size, text, anchor)]
    if sub:
        sy = y + P.LABEL_SUB_DY
        labels.append(text_box(x, sy, sub, P.SIZE_LABEL_SUB, "t-sub", anchor))
        parts.append(_text("t-sub", x, sy, P.SIZE_LABEL_SUB, sub, anchor))
    bbox = union_all([BBox.of_points([start, to]), *labels])
    return Fragment("".join(parts), bbox, tuple(labels))
