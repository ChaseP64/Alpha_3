from __future__ import annotations

from collections.abc import Sequence
from typing import List, Tuple

import shapely.geometry as sg

Point2 = Tuple[float, float]


def offset_polygon(
        poly: Sequence[Point2],
        dist: float,
) -> List[Point2]:
    """Return an offset copy (positive dist = outward)."""
    ring = sg.LinearRing(poly)
    # Simple geometric collapse check for inward offsets
    min_dim = min(ring.bounds[2] - ring.bounds[0], ring.bounds[3] - ring.bounds[1])
    if dist < 0 and abs(dist) * 2 >= min_dim:
        raise ValueError("Offset distance collapses the polygon geometry.")
    off  = ring.buffer(dist, join_style=2, mitre_limit=2)
    if isinstance(off, sg.Polygon):
        # Raise if polygon collapsed (area zero) to satisfy tests
        if off.is_empty or off.area == 0:
            raise ValueError("Offset distance collapses the polygon geometry.")
        return list(off.exterior.coords)[:-1]   # drop dup end-pt
    raise ValueError("Offset produced multi-geom")


def project_to_slope(
        base_pts: Sequence[Point2],
        horiz_off: float,
        slope_ratio: float,
) -> List[Tuple[float, float, float]]:
    """Convert 2-D offset line to 3-D break-line with vertical drop.
    Returns list of (x,y,z) where z = horiz_off / slope_ratio.
    """
    z_drop = horiz_off / slope_ratio
    return [(x, y, -z_drop) for x, y in base_pts]

# (Simple geometry helpers; robust cleanup will iterate later.)
