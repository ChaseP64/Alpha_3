from __future__ import annotations
"""Dangling edge detection utilities (Phase-7).

This helper identifies *boundary* edges in a TIN surface – edges that belong
only to a single triangle.  Such edges reveal open contour chains or holes in
the triangulation and are a common culprit when surfaces fail to close.

The API is intentionally lightweight so that the Scene/Debug overlay can call
`detect_dangling_edges(surface)` directly without pulling in heavy
dependencies.
"""

from typing import List, Tuple, Dict, FrozenSet

from digcalc_project.src.models.surface import Surface, Point3D, Triangle

__all__ = ["detect_dangling_edges", "edge_midpoints"]


Edge = Tuple[Point3D, Point3D]


def _triangle_edges(tri: Triangle) -> List[Edge]:
    """Return the three directed edges of *tri* as *(a, b)* pairs.

    The returned order is arbitrary but consistent.
    """

    p1, p2, p3 = tri.get_points()
    return [(p1, p2), (p2, p3), (p3, p1)]


def detect_dangling_edges(surface: Surface) -> List[Edge]:
    """Return a list of *dangling* edges in *surface*.

    An edge is considered *dangling* when it is referenced by **exactly one**
    triangle in the TIN.  Edges that appear twice are shared between two
    neighbouring triangles and therefore form an interior edge; these are not
    returned.

    The function returns the *undirected* edge – i.e. the order of the two
    vertices is normalised so that `(a, b)` and `(b, a)` are treated the same.

    Args
    -----
    surface: Surface
        Surface with populated ``triangles`` and ``points`` dictionaries.

    Returns
    -------
    list[Edge]
        List of vertex pairs marking boundary edges.  The list is empty when
        the surface is watertight.
    """

    edge_usage: Dict[FrozenSet[str], int] = {}

    for tri in surface.triangles.values():
        for p_a, p_b in _triangle_edges(tri):
            key: FrozenSet[str] = frozenset((p_a.id, p_b.id))
            edge_usage[key] = edge_usage.get(key, 0) + 1

    dangling: List[Edge] = []
    id_to_pt = surface.points  # shortcut

    for key, count in edge_usage.items():
        if count == 1:
            id_a, id_b = tuple(key)
            pa = id_to_pt[id_a]
            pb = id_to_pt[id_b]
            dangling.append((pa, pb))

    return dangling


def edge_midpoints(edges: List[Edge]) -> List[Tuple[float, float, float]]:
    """Return (x, y, z) mid-points of *edges* for convenient plotting."""
    mids: List[Tuple[float, float, float]] = []
    for a, b in edges:
        mids.append(((a.x + b.x) * 0.5, (a.y + b.y) * 0.5, (a.z + b.z) * 0.5))
    return mids
