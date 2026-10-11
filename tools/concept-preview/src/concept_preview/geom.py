"""Geometry shared by the emitter and the checker: boxes, number formatting,
XML escaping, and the deterministic text-footprint model.

The checker re-derives every footprint from the emitted SVG with these same
functions, so "the emitter's bookkeeping" and "what the file actually draws"
are measured with one ruler (and a test holds them equal per primitive).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import palette

EPS = 1e-6


@dataclass(frozen=True)
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @staticmethod
    def of_points(points) -> "BBox":
        pts = list(points)
        if not pts:
            raise ValueError("bbox of no points")
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return BBox(min(xs), min(ys), max(xs), max(ys))

    def union(self, other: "BBox") -> "BBox":
        return BBox(min(self.x0, other.x0), min(self.y0, other.y0),
                    max(self.x1, other.x1), max(self.y1, other.y1))

    def overlaps(self, other: "BBox") -> bool:
        """Positive-area intersection. Boxes that merely touch do not
        overlap — two labels may sit flush."""
        return (min(self.x1, other.x1) - max(self.x0, other.x0) > EPS
                and min(self.y1, other.y1) - max(self.y0, other.y0) > EPS)

    def grown(self, d: float) -> "BBox":
        return BBox(self.x0 - d, self.y0 - d, self.x1 + d, self.y1 + d)

    def crossed_by(self, a, b) -> bool:
        """The segment a→b runs through this box's interior for a positive
        length (Liang–Barsky against the open box). A segment that only
        touches an edge or a corner does not cross — the flush rule
        :meth:`overlaps` uses."""
        x0, y0, x1, y1 = self.x0 + EPS, self.y0 + EPS, self.x1 - EPS, self.y1 - EPS
        if x0 >= x1 or y0 >= y1:
            return False
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
            if p == 0:
                if q <= 0:
                    return False
            elif p < 0:
                t0 = max(t0, q / p)
            else:
                t1 = min(t1, q / p)
        return (t1 - t0) * (dx * dx + dy * dy) ** 0.5 > EPS

    def inside(self, w: float, h: float) -> bool:
        return (self.x0 >= -EPS and self.y0 >= -EPS
                and self.x1 <= w + EPS and self.y1 <= h + EPS)

    def rounded(self) -> tuple[float, float, float, float]:
        return (round(self.x0, 2), round(self.y0, 2),
                round(self.x1, 2), round(self.y1, 2))

    def __str__(self) -> str:
        x0, y0, x1, y1 = self.rounded()
        return f"[{fmt(x0)},{fmt(y0)} .. {fmt(x1)},{fmt(y1)}]"


def union_all(boxes) -> BBox:
    boxes = list(boxes)
    out = boxes[0]
    for b in boxes[1:]:
        out = out.union(b)
    return out


def fmt(v: float) -> str:
    """Stable number formatting: at most 2 decimals, no trailing zeros, no
    negative zero — so the same spec always emits the same bytes."""
    s = f"{round(float(v), 2):.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def text_width(text: str, size: float, cls: str) -> float:
    adv, spacing = palette.advance(cls)
    return len(text) * (adv * size + spacing)


def text_box(x: float, y: float, text: str, size: float, cls: str,
             anchor: str = "start", rotate: float = 0) -> BBox:
    """Footprint of one line of text drawn at baseline (x, y).

    ``rotate`` is the SVG ``rotate(<deg> x y)`` about the anchor point; only
    the quarter turns a dimension uses (0, -90, 90) are modelled — the
    checker refuses any other text transform rather than guess.
    """
    w = text_width(text, size, cls)
    if anchor == "start":
        lx0, lx1 = 0.0, w
    elif anchor == "middle":
        lx0, lx1 = -w / 2, w / 2
    elif anchor == "end":
        lx0, lx1 = -w, 0.0
    else:
        raise ValueError(f"unknown text anchor {anchor!r}")
    ly0, ly1 = -palette.ASCENT * size, palette.DESCENT * size
    if rotate == 0:
        return BBox(x + lx0, y + ly0, x + lx1, y + ly1)
    if rotate == -90:
        # (dx, dy) -> (dy, -dx)
        return BBox(x + ly0, y - lx1, x + ly1, y - lx0)
    if rotate == 90:
        # (dx, dy) -> (-dy, dx)
        return BBox(x - ly1, y + lx0, x - ly0, y + lx1)
    raise ValueError(f"unsupported text rotation {rotate}")
