"""
Catmull-Rom spline helper for DigCalc.

Provides a utility to convert a list of QPointF control points into a smoothed
QPainterPath using the Catmull-Rom interpolation scheme. When fewer than three
control points are supplied, the helper gracefully falls back to drawing a
straight poly-line so that callers do not need to special-case their input size.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath

__all__ = ["catmull_rom"]


def catmull_rom(pts: List[QPointF], samples_per_seg: int = 8) -> QPainterPath:  # noqa: D401,E501
    """Return a Catmull-Rom interpolated ``QPainterPath``.

    The helper walks the provided *pts* list and creates a smoothed
    :class:`~PySide6.QtGui.QPainterPath` that passes through each control
    point. Internally, intermediate sample points are inserted for every
    segment using the Catmull-Rom basis matrix.  If the caller passes fewer
    than three points, the routine simply returns a straight poly-line so that
    all inputs remain valid.

    Args:
        pts (List[QPointF]): Control points to interpolate. The list is **not**
            modified.
        samples_per_seg (int, optional): The number of sub-samples that will be
            generated *per segment* between control points.  Higher values
            yield smoother curves at the expense of more geometry.  Defaults to
            ``8``.

    Returns:
        QPainterPath: A path that starts at ``pts[0]`` and ends at the last
            control point while smoothly passing through the intermediate
            points.
    """

    # Defensive programming – allow any iterable, but materialise once.
    pts = list(pts)

    if len(pts) < 3:
        # Degenerate cases fall back to straight lines – at most one line
        # between points – so callers do not need to special-case small lists.
        path = QPainterPath()
        if pts:
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
        return path

    path = QPainterPath()
    path.moveTo(pts[0])

    # Iterate over successive sets of 4 points (p0..p3) to build the spline.
    # We start at i=1 so that p1 is the *current* control point; p0 is the
    # previous one.  The loop therefore runs until len(pts)-2 so that p3 exists.
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1 : i + 3]  # slice is inclusive-exclusive

        for j in range(1, samples_per_seg + 1):
            t = j / samples_per_seg
            t2 = t * t
            t3 = t2 * t

            # Catmull-Rom basis matrix applied component-wise.
            x = 0.5 * (
                (2 * p1.x())
                + (-p0.x() + p2.x()) * t
                + (2 * p0.x() - 5 * p1.x() + 4 * p2.x() - p3.x()) * t2
                + (-p0.x() + 3 * p1.x() - 3 * p2.x() + p3.x()) * t3
            )
            y = 0.5 * (
                (2 * p1.y())
                + (-p0.y() + p2.y()) * t
                + (2 * p0.y() - 5 * p1.y() + 4 * p2.y() - p3.y()) * t2
                + (-p0.y() + 3 * p1.y() - 3 * p2.y() + p3.y()) * t3
            )

            path.lineTo(x, y)

    # Ensure we end exactly at the last control point.
    path.lineTo(pts[-1])
    return path 