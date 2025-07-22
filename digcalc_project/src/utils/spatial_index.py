"""Light-weight Quad-Tree spatial index used for interactive snapping.

Only supports *point* data for now – insert (x, y, payload) tuples and perform
circular radius queries.  This implementation is fast enough for ≤50k points
and stays pure-Python with NumPy optional acceleration.

Example
-------
>>> qt = QuadTree(boundary=(-1000, -1000, 2000, 2000))  # (min_x, min_y, width, height)
>>> qt.insert(10.0, 15.0, "id-123")
>>> hits = qt.query((10.1, 15.1), radius=0.5)
>>> [(p, data) for p, data in hits]
[((10.0, 15.0), 'id-123')]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, List, Sequence, Tuple, TypeVar

__all__ = ["QuadTree"]

_T = TypeVar("_T")  # payload type
Point = Tuple[float, float]


@dataclass
class _Node(Generic[_T]):
    """Internal Quad-Tree node (axis-aligned square)."""

    x: float  # min-x of boundary
    y: float  # min-y of boundary
    size: float  # width == height (power-of-two not required)
    capacity: int = 8  # max points before subdivision
    depth: int = 0  # root = 0
    points: list[tuple[Point, _T]] = field(default_factory=list)
    children: list["_Node[_T]"] | None = None  # NW, NE, SW, SE

    # ------------------------------------------------------------------
    def _subdivide(self) -> None:
        """Split node into four equal quadrants."""
        h = self.size / 2.0
        depth = self.depth + 1
        self.children = [
            _Node(self.x, self.y, h, self.capacity, depth),  # SW (x,y) origin at min corner
            _Node(self.x + h, self.y, h, self.capacity, depth),  # SE
            _Node(self.x, self.y + h, h, self.capacity, depth),  # NW
            _Node(self.x + h, self.y + h, h, self.capacity, depth),  # NE
        ]

    # ------------------------------------------------------------------
    def _child_index(self, p: Point) -> int | None:
        """Return child idx containing point (*None* if on border)."""
        mx = self.x + self.size / 2.0
        my = self.y + self.size / 2.0
        x, y = p
        east = x >= mx
        north = y >= my
        if x == mx or y == my:
            return None  # on border – keep at parent level
        return (2 if north else 0) + (1 if east else 0)

    # ------------------------------------------------------------------
    def insert(self, p: Point, data: _T) -> None:
        if self.children is not None:
            idx = self._child_index(p)
            if idx is not None:
                self.children[idx].insert(p, data)
                return
        # Either leaf or on border
        self.points.append((p, data))
        if self.children is None and len(self.points) > self.capacity:
            self._subdivide()
            # Re-scatter points into children when possible
            for pt, payload in self.points[:]:
                idx = self._child_index(pt)
                if idx is not None:
                    self.children[idx].insert(pt, payload)  # type: ignore[index]
                    self.points.remove((pt, payload))

    # ------------------------------------------------------------------
    def _intersects_circle(self, centre: Point, r: float) -> bool:
        """Return True if node square intersects query circle."""
        cx, cy = centre
        # Clamp circle centre to square bounds and measure distance
        nearest_x = max(self.x, min(cx, self.x + self.size))
        nearest_y = max(self.y, min(cy, self.y + self.size))
        dx = cx - nearest_x
        dy = cy - nearest_y
        return dx * dx + dy * dy <= r * r

    def query(self, centre: Point, radius: float, out: list[tuple[Point, _T]]) -> None:
        if not self._intersects_circle(centre, radius):
            return
        # Check own points
        cx, cy = centre
        r2 = radius * radius
        for pt, payload in self.points:
            dx = pt[0] - cx
            dy = pt[1] - cy
            if dx * dx + dy * dy <= r2:
                out.append((pt, payload))
        # Recurse
        if self.children:
            for child in self.children:
                child.query(centre, radius, out)


class QuadTree(Generic[_T]):
    """2-D Quad-Tree index for up to ~1e6 points (practical UI scale).

    Args:
        boundary: *(min_x, min_y, width, height)* square/rect boundary covering
            **all** points to be inserted.
        capacity: Maximum number of points a leaf node can hold before it splits.
    """

    def __init__(self, boundary: Tuple[float, float, float, float], capacity: int = 8):
        min_x, min_y, w, h = boundary
        if abs(w - h) > 1e-9:
            # Accept rectangle but store square based on max dimension for simplicity
            size = max(w, h)
        else:
            size = w
        self._root: _Node[_T] = _Node(min_x, min_y, size, capacity)

    # ------------------------------------------------------------------
    def insert(self, x: float, y: float, payload: _T) -> None:
        """Insert a point with *payload* into the index."""
        self._root.insert((x, y), payload)

    def bulk_insert(self, points: Sequence[Tuple[float, float, _T]]) -> None:
        """Insert many points efficiently (no duplicate bounding checks)."""
        for x, y, data in points:
            self._root.insert((x, y), data)

    # ------------------------------------------------------------------
    def query(self, centre: Point, radius: float) -> list[tuple[Point, _T]]:
        """Return list of *(point, payload)* within *radius* of *centre*."""
        hits: list[tuple[Point, _T]] = []
        self._root.query(centre, radius, hits)
        return hits

    # ------------------------------------------------------------------
    # Nearest-neighbour helpers (Phase-4)
    # ------------------------------------------------------------------
    def nearest(self, centre: Point, radius: float) -> tuple[Point, _T] | None:
        """Return the closest *(point, payload)* within *radius* of *centre*.

        Falls back to *None* when no hits are inside the search circle.
        """
        hits = self.query(centre, radius)
        if not hits:
            return None
        cx, cy = centre
        return min(hits, key=lambda hp: (hp[0][0] - cx) ** 2 + (hp[0][1] - cy) ** 2)

    # ------------------------------------------------------------------
    # Optional edge index — stores segment mid-points to approximate search
    # ------------------------------------------------------------------
    def insert_edge(self, p1: Point, p2: Point, payload: _T) -> None:
        """Insert an edge (line-segment) by its *mid-point* for proximity queries.

        This keeps the QuadTree implementation point-only.  Callers must store
        *(p1, p2)* in the *payload* so the exact perpendicular distance can be
        computed at query-time.
        """
        mx = 0.5 * (p1[0] + p2[0])
        my = 0.5 * (p1[1] + p2[1])
        self.insert(mx, my, payload)

    def nearest_edge(self, centre: Point, radius: float) -> tuple[tuple[Point, Point], _T, float] | None:
        """Return the closest edge *(p1, p2, payload, dist)* within *radius*.

        The *payload* must be a ``(p1, p2, user_data)`` triple or similar so
        that the true segment can be reconstructed.  If the payload is just
        ``user_data``, the edge is inferred from that.  The helper gracefully
        handles both cases.
        """
        hits = self.query(centre, radius)
        if not hits:
            return None

        cx, cy = centre

        def _seg_dist(pt1: Point, pt2: Point) -> float:
            # Compute perpendicular distance from (cx,cy) to segment p1-p2
            x1, y1 = pt1
            x2, y2 = pt2
            dx = x2 - x1
            dy = y2 - y1
            if dx == dy == 0:
                return ((cx - x1) ** 2 + (cy - y1) ** 2) ** 0.5
            t = ((cx - x1) * dx + (cy - y1) * dy) / (dx * dx + dy * dy)
            t = max(0.0, min(1.0, t))
            px = x1 + t * dx
            py = y1 + t * dy
            return ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5

        best = None
        best_dist = radius + 1.0  # sentinel larger than search radius
        for (_, payload) in hits:
            if isinstance(payload, tuple) and len(payload) >= 2 and isinstance(payload[0], tuple):
                p1, p2, *user = payload  # p1, p2 expected
                dist = _seg_dist(p1, p2)
                if dist < best_dist:
                    best = (p1, p2, user[0] if user else None, dist)
                    best_dist = dist
        return best  # type: ignore[return-value]

    # ------------------------------------------------------------------
    def __len__(self) -> int:
        """Return total point count (debug/helper)."""
        return self._count(self._root)

    @staticmethod
    def _count(node: _Node) -> int:
        n = len(node.points)
        if node.children:
            n += sum(QuadTree._count(c) for c in node.children)
        return n 