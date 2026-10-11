"""The 2D convex hull and the distance predicates the verdict rests on.

Andrew's monotone chain, stdlib-only, O(n log n). The contact geometry of a
standing object can be thousands of vertices (a tessellated sphere's lowest
ring, every foot of a truss), and the verdict needs three questions of its
hull, each answered here exactly rather than by eye:

- is the CoG's ground projection inside the hull?
- how far is it from the hull boundary — signed, positive inside and
  negative outside, so one number carries both the verdict and its margin?
- is the hull degenerate (fewer than three corners, or collinear ones)?
  A part standing on an edge or a vertex has a footprint that cannot
  stabilise any CoG, and the verdict must say that instead of quietly
  computing a distance along a line.
"""

from __future__ import annotations

from math import hypot

#: Points closer than this (mm) to a hull edge are ON it. Small on purpose:
#: it absorbs float noise from the tetrahedron decomposition without ever
#: moving a verdict a real margin could care about.
EPS = 1e-9

Point = tuple[float, float]


def convex_hull(points: list[Point]) -> list[Point]:
    """Return the convex hull of ``points``, counter-clockwise, no collinear
    vertices. Fewer than three distinct points collapse naturally: one or two
    points come back as-is (the degenerate case the caller flags)."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= EPS:
            lower.pop()
        lower.append(p)
    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= EPS:
            upper.pop()
        upper.append(p)
    # Last point of each chain is the first of the other: drop both.
    return lower[:-1] + upper[:-1]


def hull_is_degenerate(hull: list[Point]) -> bool:
    """True when the hull cannot enclose an area (fewer than three corners,
    or collinear ones — which the chain reduces to two corners)."""
    return len(hull) < 3 or polygon_area(hull) <= EPS


def polygon_area(hull: list[Point]) -> float:
    """Shoelace area of a polygon (any orientation); 0 for degeneracies."""
    if len(hull) < 3:
        return 0.0
    total = 0.0
    for i, (x0, y0) in enumerate(hull):
        x1, y1 = hull[(i + 1) % len(hull)]
        total += x0 * y1 - x1 * y0
    return abs(total) / 2.0


def point_in_hull(point: Point, hull: list[Point]) -> bool:
    """True when ``point`` is inside (or on) the counter-clockwise hull."""
    if len(hull) < 3:
        return distance_to_boundary(point, hull) <= EPS
    for i, a in enumerate(hull):
        b = hull[(i + 1) % len(hull)]
        # Left of every edge (cross >= 0) <=> inside a CCW polygon.
        if (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]) < -EPS:
            return False
    return True


def distance_to_boundary(point: Point, hull: list[Point]) -> float:
    """Shortest distance from ``point`` to the hull's boundary polyline."""
    if not hull:
        return 0.0
    if len(hull) == 1:
        return hypot(point[0] - hull[0][0], point[1] - hull[0][1])
    best = float("inf")
    n = len(hull)
    edges = (
        [(hull[i], hull[(i + 1) % n]) for i in range(n)]
        if n >= 3
        else [(hull[0], hull[1])]
    )
    for a, b in edges:
        best = min(best, _point_segment_distance(point, a, b))
    return best


def signed_margin(point: Point, hull: list[Point]) -> float:
    """Distance from ``point`` to the hull boundary, positive inside and
    negative outside — the one number the verdict compares against the
    manifest's stability margin."""
    d = distance_to_boundary(point, hull)
    return d if point_in_hull(point, hull) else -d


def _point_segment_distance(point: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = point
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= EPS:
        return hypot(px - ax, py - ay)
    # Clamp the projection parameter to the segment.
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return hypot(px - (ax + t * dx), py - (ay + t * dy))
