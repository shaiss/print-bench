"""The checker: proves a concept sheet is well-formed, self-contained,
in-bounds and collision-free — measured from the emitted file, not taken
from the emitter's word.

Rules (each finding carries its rule name, which the selftest keys on):

``xml``        the sheet parses as XML.
``contract``   the sheet stays inside the vocabulary this checker can
               measure: an ``<svg>`` root with a ``0 0 W H`` viewBox; every
               drawable element inside a ``cp-<kind>`` group of a known
               kind; the ground, header and title block present exactly
               once; only absolute ``M L H V Z`` path commands; no transform
               but a text quarter-turn; the palette's stylesheet byte for
               byte, with no inline ``style=`` and no presentation attribute
               on a container — root, group, defs, marker (the rulers are the
               palette's); markers only at the ends of an open outline.
               Anything else is refused, never skipped — an element the
               checker cannot measure is an element it could not have
               checked.
``external``   no external reference of any kind: no ``href``/``url()`` that
               is not a ``#fragment``, no ``@import``, no script, image or
               foreign object, no event-handler attribute. A served sheet
               must be self-contained (issue #474's no-CDN rule).
``bounds``     everything each group *paints* lies inside the viewBox: the
               geometry grown by half its stroke width, every miter tip, and
               every marker (a leader's dot, a dimension's arrowheads) as its
               own ``<marker>`` draws it at the vertex.
``collision``  no two labels overlap — leader and dimension text and
               balloons, measured with the deterministic monospace model in
               :mod:`concept_preview.geom` — neither a label nor a drawn
               shape intrudes on the sheet furniture (header band, title
               block, note, bill of parts), and no connecting line (a
               leader, a balloon's leader, a dimension or extension line)
               runs through a label or the furniture, measured segment by
               segment.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import palette as P
from .geom import EPS, BBox, fmt, text_box, union_all

SHAPE_KINDS = ("hatch", "shank", "hex")
LABEL_KINDS = ("dim", "balloon", "leader")
FURNITURE_KINDS = ("header", "titleblock", "note", "bom")
KINDS = ("ground", *FURNITURE_KINDS, *SHAPE_KINDS, *LABEL_KINDS)
REQUIRED_ONCE = ("ground", "header", "titleblock")

DESCRIBE = {
    "ground": "sheet ground", "header": "header band", "titleblock": "title block",
    "note": "note box", "bom": "bill of parts", "hatch": "hatched section",
    "shank": "threaded shank", "hex": "hex head", "dim": "dimension",
    "balloon": "balloon", "leader": "leader label",
}

# The attributes each container may carry. Properties inherit, so anything
# else on a container (a stroke-width on a group, the root, <defs> or a
# <marker>) would restyle what it holds where the checker does not look.
CONTAINER_ATTRS = {
    "svg": {"width", "height", "viewBox", "data-sheet"},
    "g": {"class", "data-src"},
    "defs": set(),
    "marker": {"id", "markerWidth", "markerHeight", "refX", "refY", "orient",
               "markerUnits", "viewBox", "overflow"},
}
ALLOWED_TAGS = {"svg", "title", "desc", "style", "defs", "pattern", "marker", "g",
                "path", "line", "rect", "circle", "ellipse", "polygon", "polyline", "text"}
MEASURED_TAGS = {"path", "line", "rect", "circle", "ellipse", "polygon", "polyline", "text"}

_NUM = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_PATH_TOKEN = re.compile(rf"([A-Za-z])|({_NUM})")
_ROTATE = re.compile(rf"^\s*rotate\(\s*({_NUM})\s+({_NUM})\s+({_NUM})\s*\)\s*$")
_URL = re.compile(r"url\(\s*(['\"]?)([^)'\"]*)\1\s*\)", re.I)


@dataclass(frozen=True)
class Finding:
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.message}"


class _Refuse(Exception):
    """An element the checker cannot measure: becomes a contract finding."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _num(el: ET.Element, attr: str, default: float | None = None) -> float:
    raw = el.get(attr)
    if raw is None:
        if default is None:
            raise _Refuse(f"<{_local(el.tag)}> has no {attr}=")
        return default
    if not re.fullmatch(_NUM, raw.strip()):
        raise _Refuse(f"<{_local(el.tag)}> {attr}={raw!r} is not a plain number")
    return float(raw)


def _path_subpaths(d: str) -> list:
    """The polylines a path draws, one ``[points, closed]`` per subpath."""
    subs: list = []
    cur = None
    cmd = None
    nums: list = []

    def extend(points):
        nonlocal cur
        if cur is None:
            raise _Refuse("path data does not start with a moveto (M)")
        if subs[-1][1]:                       # drawing on after Z starts a new subpath
            subs.append([[cur], False])
        for p in points:
            cur = p
            subs[-1][0].append(p)

    def flush():
        nonlocal cur
        if cmd in ("M", "L"):
            if len(nums) % 2 or not nums:
                raise _Refuse(f"path {cmd} needs coordinate pairs")
            pairs = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
            if cmd == "M":
                cur = pairs[0]
                subs.append([[cur], False])
                pairs = pairs[1:]             # further pairs are an implicit L
            extend(pairs)
        elif cmd == "H":
            extend([(v, cur[1] if cur else 0.0) for v in nums])
        elif cmd == "V":
            extend([(cur[0] if cur else 0.0, v) for v in nums])
        elif cmd == "Z":
            if nums:
                raise _Refuse("path Z takes no coordinates")
            if not subs:
                raise _Refuse("path data does not start with a moveto (M)")
            subs[-1][1] = True
            cur = subs[-1][0][0]

    for m in _PATH_TOKEN.finditer(d):
        letter, number = m.group(1), m.group(2)
        if letter:
            flush()
            if letter not in "MLHVZ":
                raise _Refuse(f"path command {letter!r} is outside the measurable set (absolute M L H V Z)")
            cmd, nums = letter, []
        else:
            if cmd is None:
                raise _Refuse("path data does not start with a command")
            nums.append(float(number))
    flush()
    if not subs:
        raise _Refuse("path draws nothing")
    return subs


def _path_box(d: str) -> BBox:
    return BBox.of_points(p for points, _closed in _path_subpaths(d) for p in points)


def _points(raw: str) -> list:
    vals = [float(v) for v in re.findall(_NUM, raw or "")]
    if len(vals) < 2 or len(vals) % 2:
        raise _Refuse("points= needs coordinate pairs")
    return list(zip(vals[0::2], vals[1::2]))


def _points_box(raw: str) -> BBox:
    return BBox.of_points(_points(raw))


def _text_box(el: ET.Element) -> BBox:
    cls = el.get("class", "")
    if cls not in P.TEXT_CLASSES:
        raise _Refuse(f"<text> class {cls!r} is not a palette text class")
    if len(el):
        raise _Refuse("<text> with child elements (tspan) is outside the measurable set")
    x, y, size = _num(el, "x"), _num(el, "y"), _num(el, "font-size")
    anchor = el.get("text-anchor", "start")
    if anchor not in ("start", "middle", "end"):
        raise _Refuse(f"<text> text-anchor={anchor!r}")
    rotate = 0.0
    tf = el.get("transform")
    if tf is not None:
        m = _ROTATE.match(tf)
        if not m or float(m.group(1)) not in (-90.0, 90.0) \
                or float(m.group(2)) != x or float(m.group(3)) != y:
            raise _Refuse(f"<text> transform={tf!r} (only a quarter-turn about its own x,y)")
        rotate = float(m.group(1))
    return text_box(x, y, el.text or "", size, cls, anchor, rotate)


def _element_box(el: ET.Element) -> BBox:
    tag = _local(el.tag)
    if tag != "text" and el.get("transform") is not None:
        raise _Refuse(f"<{tag}> carries a transform the checker does not model")
    if tag == "rect":
        x, y = _num(el, "x", 0.0), _num(el, "y", 0.0)
        return BBox(x, y, x + _num(el, "width"), y + _num(el, "height"))
    if tag == "circle":
        cx, cy, r = _num(el, "cx", 0.0), _num(el, "cy", 0.0), _num(el, "r")
        return BBox(cx - r, cy - r, cx + r, cy + r)
    if tag == "ellipse":
        cx, cy = _num(el, "cx", 0.0), _num(el, "cy", 0.0)
        rx, ry = _num(el, "rx"), _num(el, "ry")
        return BBox(cx - rx, cy - ry, cx + rx, cy + ry)
    if tag == "line":
        return BBox.of_points([(_num(el, "x1", 0.0), _num(el, "y1", 0.0)),
                               (_num(el, "x2", 0.0), _num(el, "y2", 0.0))])
    if tag == "path":
        return _path_box(el.get("d", ""))
    if tag in ("polygon", "polyline"):
        return _points_box(el.get("points", ""))
    if tag == "text":
        return _text_box(el)
    raise _Refuse(f"<{tag}> is outside the measurable set")


# ── painted extent: what the bounds check holds inside the sheet ──────────
# An element's geometry is not what it paints: a stroke reaches half its
# width past the outline (further at a sharp miter join), and a marker draws
# its own shape at a vertex — a leader's dot is a 2.3 px disc centred on the
# target, so a target on the sheet edge paints off it. The bounds check
# measures all of it; the collision checks keep the geometry (a label's
# legibility is not a matter of a hairline's half-width).
MARKABLE_TAGS = {"path", "line", "polyline", "polygon"}
_MARKER_REF = re.compile(r"^\s*url\(\s*#([^)\s]+)\s*\)\s*$")


def _prop(el: ET.Element, name: str, default: str | None = None) -> str | None:
    """A presentation property as the sheet paints it: a palette class rule
    wins over the element's own attribute (CSS outranks presentation
    attributes), the attribute over the SVG initial value. The stylesheet is
    held to the palette's byte for byte, so the palette is the ruler."""
    classes = el.get("class", "").split()
    found = None
    for cls, decls in P.SHAPE_CLASSES.items():      # stylesheet order: a later rule wins
        if cls in classes:
            for decl in decls.split(";"):
                key, _, val = decl.partition(":")
                if key.strip() == name:
                    found = val.strip()
    return found if found is not None else el.get(name, default)


def _prop_num(el: ET.Element, name: str, default: str) -> float:
    raw = _prop(el, name, default)
    if not re.fullmatch(_NUM, raw.strip()):
        raise _Refuse(f"<{_local(el.tag)}> {name} {raw!r} is not a plain number")
    return float(raw)


def _polylines(el: ET.Element) -> list:
    """The ``[points, closed]`` outlines a stroke follows, for the elements
    whose joins can miter and which carry markers."""
    tag = _local(el.tag)
    if tag == "path":
        return _path_subpaths(el.get("d", ""))
    if tag == "line":
        return [[[(_num(el, "x1", 0.0), _num(el, "y1", 0.0)),
                  (_num(el, "x2", 0.0), _num(el, "y2", 0.0))], False]]
    if tag in ("polyline", "polygon"):
        return [[_points(el.get("points", "")), tag == "polygon"]]
    if tag == "rect":
        b = _element_box(el)
        return [[[(b.x0, b.y0), (b.x1, b.y0), (b.x1, b.y1), (b.x0, b.y1)], True]]
    return []


def _distinct(points: list, closed: bool) -> list:
    out = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
    if closed and len(out) > 1 and out[-1] == out[0]:
        out.pop()
    return out


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy)
    return (dx / d, dy / d)


def _miter_tips(points: list, closed: bool, half: float, limit: float) -> list:
    """Every miter tip a stroke of half-width ``half`` paints past the
    outline: at each join, ``half / sin(θ/2)`` along the outer bisector —
    unless that ratio exceeds the miter limit, where SVG bevels the join
    (and a bevel stays inside the half-width box). Round and bevel joins
    paint less than the miter, so measuring the miter is conservative."""
    pts = _distinct(points, closed)
    n = len(pts)
    if n < 3 and not (closed and n == 2):
        return []
    tips = []
    for i in (range(n) if closed else range(1, n - 1)):
        prev, v, nxt = pts[i - 1], pts[i], pts[(i + 1) % n]
        u1, u2 = _unit(prev, v), _unit(v, nxt)
        s = math.sqrt(max(0.0, (1 + (u1[0] * u2[0] + u1[1] * u2[1])) / 2))   # sin(θ/2)
        bx, by = u1[0] - u2[0], u1[1] - u2[1]
        bl = math.hypot(bx, by)
        if s < EPS or 1 / s > limit or bl < EPS:
            continue
        reach = half / s
        tips.append((v[0] + bx / bl * reach, v[1] + by / bl * reach))
    return tips


def _ends(el: ET.Element):
    """((start vertex, direction°), (end vertex, direction°)) of a markable
    element — where marker-start and marker-end sit, and which way an
    ``orient=auto`` marker turns."""
    lines = _polylines(el)
    if any(closed for _points, closed in lines):
        raise _Refuse(f"<{_local(el.tag)}> a marker on a closed outline is outside the measurable set")
    first, last = _distinct(lines[0][0], False), _distinct(lines[-1][0], False)

    def angle(a, b):
        return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))

    start = (first[0], angle(first[0], first[1]) if len(first) > 1 else 0.0)
    end = (last[-1], angle(last[-2], last[-1]) if len(last) > 1 else 0.0)
    return start, end


def _marker_box(marker: ET.Element, stroke_w: float, at, angle: float) -> BBox | None:
    """What one marker paints at vertex ``at``: its content's painted box,
    clipped to the marker viewport (``overflow`` is hidden for a marker),
    shifted so (refX, refY) lands on the vertex, scaled by the stroke width
    (``markerUnits=strokeWidth``, the default) and turned by ``angle``."""
    if marker.get("viewBox") is not None:
        raise _Refuse("a <marker> viewBox is outside the measurable set")
    units = marker.get("markerUnits", "strokeWidth")
    if units not in ("strokeWidth", "userSpaceOnUse"):
        raise _Refuse(f"<marker> markerUnits={units!r}")
    scale = stroke_w if units == "strokeWidth" else 1.0
    mw, mh = _num(marker, "markerWidth", 3.0), _num(marker, "markerHeight", 3.0)
    rx, ry = _num(marker, "refX", 0.0), _num(marker, "refY", 0.0)
    content = [_painted_box(child, None) for child in _measured(marker)]
    if not content:
        return None
    box = union_all(content)
    if marker.get("overflow", "hidden") not in ("visible", "auto"):
        box = BBox(max(box.x0, 0.0), max(box.y0, 0.0), min(box.x1, mw), min(box.y1, mh))
        if box.x0 > box.x1 or box.y0 > box.y1:
            return None
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    corners = [((x - rx) * scale, (y - ry) * scale) for x in (box.x0, box.x1) for y in (box.y0, box.y1)]
    return BBox.of_points((at[0] + x * c - y * s, at[1] + x * s + y * c) for x, y in corners)


def _painted_box(el: ET.Element, markers: dict | None) -> BBox:
    """The element's geometry grown by everything it paints past it: half
    the stroke width all round, each miter tip, and each marker. ``markers``
    maps the sheet's marker ids to their elements; ``None`` inside a marker,
    where a further marker is refused."""
    box = _element_box(el)
    tag = _local(el.tag)
    if _prop(el, "stroke", "none").strip() != "none":
        half = _prop_num(el, "stroke-width", "1") / 2
        join = _prop(el, "stroke-linejoin", "miter").strip()
        if join not in ("miter", "round", "bevel"):
            raise _Refuse(f"<{tag}> stroke-linejoin {join!r} is outside the measurable set")
        limit = _prop_num(el, "stroke-miterlimit", "4")
        box = box.grown(half)
        for points, closed in _polylines(el):
            for tip in _miter_tips(points, closed, half, limit):
                box = box.union(BBox(tip[0], tip[1], tip[0], tip[1]))
    if _prop(el, "marker-mid", "none").strip() != "none":
        raise _Refuse(f"<{tag}> marker-mid is outside the measurable set")
    refs = [(which, _prop(el, f"marker-{which}", "none").strip()) for which in ("start", "end")]
    refs = [(which, ref) for which, ref in refs if ref != "none"]
    if refs and tag in MARKABLE_TAGS:
        if markers is None:
            raise _Refuse("a marker inside a <marker> is outside the measurable set")
        stroke_w = _prop_num(el, "stroke-width", "1")
        ends = dict(zip(("start", "end"), _ends(el)))
        for which, ref in refs:
            m = _MARKER_REF.match(ref)
            if not m or m.group(1) not in markers:
                raise _Refuse(f"<{tag}> marker-{which}={ref!r} names no marker this sheet defines")
            marker = markers[m.group(1)]
            at, direction = ends[which]
            orient = marker.get("orient", "0").strip()
            if orient == "auto":
                angle = direction
            elif orient == "auto-start-reverse":
                angle = direction + (180.0 if which == "start" else 0.0)
            elif re.fullmatch(_NUM, orient):
                angle = float(orient)
            else:
                raise _Refuse(f"<marker> orient={orient!r} is outside the measurable set")
            painted = _marker_box(marker, stroke_w, at, angle)
            if painted is not None:
                box = box.union(painted)
    return box


def _segments(el: ET.Element) -> list:
    """The straight runs a connecting line draws — what a leader, a
    balloon's leader or a dimension can strike through a label with."""
    if _local(el.tag) not in MARKABLE_TAGS:
        return []
    out = []
    for points, closed in _polylines(el):
        pts = points + points[:1] if closed else points
        out.extend((a, b) for a, b in zip(pts, pts[1:]) if a != b)
    return out


def _measured(group: ET.Element):
    """Every measurable descendant of a group, skipping <defs> subtrees
    (patterns are paint, not placement). A nested <g> or any other
    unmeasurable element is refused."""
    for child in group:
        tag = _local(child.tag)
        if tag == "defs":
            continue
        if tag not in MEASURED_TAGS:
            raise _Refuse(f"<{tag}> inside a checked group is outside the measurable set")
        yield child


def measure(fragment: str) -> tuple[BBox, list]:
    """(footprint, text footprints) of one unwrapped primitive fragment,
    measured the way :func:`check_svg` measures a group — the hook the
    tests use to hold each primitive's own bookkeeping to the checker's
    ruler. Raises ValueError for anything the checker would refuse."""
    group = ET.fromstring(f'<g xmlns="http://www.w3.org/2000/svg">{fragment}</g>')
    try:
        elements = list(_measured(group))
        boxes = [_element_box(el) for el in elements]
    except _Refuse as e:
        raise ValueError(str(e)) from None
    texts = [b for el, b in zip(elements, boxes) if _local(el.tag) == "text"]
    return union_all(boxes), texts


def _external(root: ET.Element, name: str) -> list:
    out = []
    for el in root.iter():
        tag = _local(el.tag)
        if tag not in ALLOWED_TAGS:
            rule = "external" if tag in ("script", "image", "foreignObject", "use", "a",
                                         "iframe", "link", "feImage") else "contract"
            out.append(Finding(rule, f"{name}: <{tag}> is not allowed in a concept sheet"))
        for attr, val in el.attrib.items():
            a = _local(attr)
            if a.lower().startswith("on"):
                out.append(Finding("external", f"{name}: event attribute {a}= on <{tag}>"))
            if a == "href" and not val.startswith("#"):
                out.append(Finding("external", f"{name}: <{tag}> href={val!r} is not a #fragment"))
            for m in _URL.finditer(val):
                if not m.group(2).startswith("#"):
                    out.append(Finding("external", f"{name}: <{tag}> {a}= references url({m.group(2)})"))
        if tag == "style":
            css = el.text or ""
            if re.search(r"@import", css, re.I):
                out.append(Finding("external", f"{name}: <style> uses @import"))
            for m in _URL.finditer(css):
                if not m.group(2).startswith("#"):
                    out.append(Finding("external", f"{name}: <style> references url({m.group(2)})"))
    return out


def _src(group: ET.Element) -> str:
    raw = group.get("data-src", "")
    return f" (spec line {raw[1:]})" if re.fullmatch(r"L\d+", raw) else ""


def check_svg(text: str, name: str = "<svg>") -> list:
    """Every finding for one sheet; an empty list is a pass."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return [Finding("xml", f"{name}: not well-formed XML ({e})")]
    if _local(root.tag) != "svg":
        return [Finding("contract", f"{name}: root element is <{_local(root.tag)}>, not <svg>")]
    vb = (root.get("viewBox") or "").split()
    try:
        if len(vb) != 4 or float(vb[0]) != 0 or float(vb[1]) != 0:
            raise ValueError
        W, H = float(vb[2]), float(vb[3])
        if W <= 0 or H <= 0:
            raise ValueError
    except ValueError:
        return [Finding("contract", f"{name}: viewBox {root.get('viewBox')!r} is not '0 0 W H'")]
    findings = _external(root, name)
    for attr, want in (("width", W), ("height", H)):
        try:
            if float(root.get(attr, "nan")) != want:
                raise ValueError
        except ValueError:
            findings.append(Finding("contract", f"{name}: {attr}= does not match the viewBox"))
    # Stroke widths and text metrics are read from the palette, so the sheet
    # must paint with exactly the palette's stylesheet — and nothing may
    # restyle an element where the checker does not look: no inline style=,
    # and no presentation attribute on a container to inherit down.
    styles = [el for el in root.iter() if _local(el.tag) == "style"]
    if len(styles) != 1 or (styles[0].text or "").strip("\n") != P.stylesheet():
        findings.append(Finding("contract", f"{name}: the stylesheet is not the palette's, byte for "
                                "byte (strokes and text are measured with the palette)"))
    for el in root.iter():
        tag = _local(el.tag)
        if "style" in el.attrib:
            findings.append(Finding("contract", f"{name}: <{tag}> carries an inline "
                                    "style= the checker does not model"))
        extra = sorted(set(el.attrib) - CONTAINER_ATTRS.get(tag, set(el.attrib)) - {"style"})
        if extra:
            findings.append(Finding("contract", f"{name}: <{tag} class={el.get('class', '')!r}> carries "
                                    f"{' '.join(a + '=' for a in extra)} (it would inherit into "
                                    "what it holds)"))
    markers = {el.get("id"): el for el in root.iter() if _local(el.tag) == "marker"}

    groups = []
    counts: dict = {}
    for child in root:
        tag = _local(child.tag)
        if tag in ("title", "desc", "style", "defs"):
            continue
        cls = child.get("class", "")
        kind = cls[3:] if tag == "g" and cls.startswith("cp-") else None
        if kind not in KINDS:
            findings.append(Finding("contract", f"{name}: <{tag} class={cls!r}> sits outside "
                                    f"every checked group (known: {' '.join('cp-' + k for k in KINDS)})"))
            continue
        counts[kind] = counts.get(kind, 0) + 1
        groups.append((kind, child))
    for kind in REQUIRED_ONCE:
        if counts.get(kind, 0) != 1:
            findings.append(Finding("contract", f"{name}: expected exactly one {DESCRIBE[kind]} "
                                    f"(cp-{kind}), found {counts.get(kind, 0)}"))

    labels = []      # (box, description, owning group)
    shapes = []      # (box, description)
    furniture = []   # (box, description, None)
    lines = []       # (a, b, description, owning group, kind) — connecting lines
    for gi, (kind, group) in enumerate(groups):
        desc = DESCRIBE[kind] + _src(group)
        try:
            elements = list(_measured(group))
            boxes = [_element_box(el) for el in elements]
            painted = [_painted_box(el, markers) for el in elements]
            if kind in LABEL_KINDS:
                lines += [(a, b, desc, gi, kind) for el in elements for a, b in _segments(el)]
        except _Refuse as e:
            findings.append(Finding("contract", f"{name}: {desc}: {e}"))
            continue
        except ValueError as e:
            findings.append(Finding("contract", f"{name}: {desc}: {e}"))
            continue
        if not boxes:
            findings.append(Finding("contract", f"{name}: {desc} draws nothing"))
            continue
        bbox = union_all(boxes)
        paint = union_all(painted)
        if not paint.inside(W, H):
            findings.append(Finding("bounds", f"{name}: {desc} paints {paint} (stroke and markers "
                                    f"included), leaving the {int(W)}x{int(H)} sheet"))
        if kind in FURNITURE_KINDS:
            furniture.append((bbox, DESCRIBE[kind], None))
        elif kind in SHAPE_KINDS:
            shapes.append((bbox, desc))
        elif kind == "balloon":
            number = next((el.text or "" for el in elements if _local(el.tag) == "text"), "")
            for el, b in zip(elements, boxes):
                if _local(el.tag) == "circle":
                    labels.append((b, f"{desc} {number.strip()!r}", gi))
        elif kind in ("leader", "dim"):
            for el, b in zip(elements, boxes):
                if _local(el.tag) == "text":
                    labels.append((b, f"{desc} {el.text!r}", gi))

    # Every pair, including two lines of the same leader: nothing in a sheet
    # is allowed to print over a label, whoever drew it.
    every_label = labels + furniture
    for i in range(len(every_label)):
        for j in range(i + 1, len(every_label)):
            a, b = every_label[i], every_label[j]
            if a[0].overlaps(b[0]):
                findings.append(Finding("collision", f"{name}: {a[1]} {a[0]} overlaps {b[1]} {b[0]}"))
    for box, desc in shapes:
        for fbox, fdesc, _owner in furniture:
            if box.overlaps(fbox):
                findings.append(Finding("collision", f"{name}: {desc} {box} intrudes on the {fdesc} {fbox}"))
    # A connecting line — a leader, a balloon's leader, a dimension line or
    # its extension lines — struck through a label is as illegible as two
    # labels on top of each other, and may not cross the furniture either.
    # Measured as the segment itself, never the annotation's bounding box
    # (which would refuse every leader that merely angles past a label).
    # A balloon's leader starts on its own rim, so it is not held against
    # its own circle; every other line is held against its own text too.
    for a, b, desc, owner, kind in lines:
        for box, bdesc, bowner in every_label:
            if bowner == owner and kind == "balloon":
                continue
            if box.crossed_by(a, b):
                findings.append(Finding("collision", f"{name}: {desc} line {fmt(a[0])},{fmt(a[1])} → "
                                        f"{fmt(b[0])},{fmt(b[1])} crosses {bdesc} {box}"))
    return findings
