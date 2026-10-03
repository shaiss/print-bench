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
               but a text quarter-turn. Anything else is refused, never
               skipped — an element the checker cannot measure is an
               element it could not have checked.
``external``   no external reference of any kind: no ``href``/``url()`` that
               is not a ``#fragment``, no ``@import``, no script, image or
               foreign object, no event-handler attribute. A served sheet
               must be self-contained (issue #474's no-CDN rule).
``bounds``     every group's footprint lies inside the viewBox.
``collision``  no two labels overlap — leader and dimension text and
               balloons, measured with the deterministic monospace model in
               :mod:`concept_preview.geom` — and neither a label nor a drawn
               shape intrudes on the sheet furniture (header band, title
               block, note, bill of parts).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import palette as P
from .geom import BBox, text_box, union_all

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


def _path_box(d: str) -> BBox:
    pts: list = []
    cur = (0.0, 0.0)
    cmd = None
    nums: list = []

    def flush():
        nonlocal cur
        if cmd in ("M", "L"):
            if len(nums) % 2 or not nums:
                raise _Refuse(f"path {cmd} needs coordinate pairs")
            for i in range(0, len(nums), 2):
                cur = (nums[i], nums[i + 1])
                pts.append(cur)
        elif cmd == "H":
            for v in nums:
                cur = (v, cur[1])
                pts.append(cur)
        elif cmd == "V":
            for v in nums:
                cur = (cur[0], v)
                pts.append(cur)
        elif cmd == "Z":
            if nums:
                raise _Refuse("path Z takes no coordinates")

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
    if not pts:
        raise _Refuse("path draws nothing")
    return BBox.of_points(pts)


def _points_box(raw: str) -> BBox:
    vals = [float(v) for v in re.findall(_NUM, raw or "")]
    if len(vals) < 2 or len(vals) % 2:
        raise _Refuse("points= needs coordinate pairs")
    return BBox.of_points(zip(vals[0::2], vals[1::2]))


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

    labels = []      # (box, description)
    shapes = []      # (box, description)
    furniture = []   # (box, description)
    for kind, group in groups:
        desc = DESCRIBE[kind] + _src(group)
        try:
            elements = list(_measured(group))
            boxes = [_element_box(el) for el in elements]
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
        if not bbox.inside(W, H):
            findings.append(Finding("bounds", f"{name}: {desc} {bbox} leaves the "
                                    f"{int(W)}x{int(H)} sheet"))
        if kind in FURNITURE_KINDS:
            furniture.append((bbox, DESCRIBE[kind]))
        elif kind in SHAPE_KINDS:
            shapes.append((bbox, desc))
        elif kind == "balloon":
            number = next((el.text or "" for el in elements if _local(el.tag) == "text"), "")
            for el, b in zip(elements, boxes):
                if _local(el.tag) == "circle":
                    labels.append((b, f"{desc} {number.strip()!r}"))
        elif kind in ("leader", "dim"):
            for el, b in zip(elements, boxes):
                if _local(el.tag) == "text":
                    labels.append((b, f"{desc} {el.text!r}"))

    # Every pair, including two lines of the same leader: nothing in a sheet
    # is allowed to print over a label, whoever drew it.
    every_label = labels + furniture
    for i in range(len(every_label)):
        for j in range(i + 1, len(every_label)):
            a, b = every_label[i], every_label[j]
            if a[0].overlaps(b[0]):
                findings.append(Finding("collision", f"{name}: {a[1]} {a[0]} overlaps {b[1]} {b[0]}"))
    for box, desc in shapes:
        for fbox, fdesc in furniture:
            if box.overlaps(fbox):
                findings.append(Finding("collision", f"{name}: {desc} {box} intrudes on the {fdesc} {fbox}"))
    return findings
