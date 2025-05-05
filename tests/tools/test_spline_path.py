from PySide6.QtCore import QPointF

from digcalc_project.src.tools.spline import catmull_rom


def test_spline_passes_through_endpoints():
    """catmull_rom output should start and end exactly at the provided endpoints."""

    pts = [QPointF(0, 0), QPointF(10, 0), QPointF(20, 10)]
    path = catmull_rom(pts, samples_per_seg=4)

    assert path.elementCount() > 0

    # First element (moveTo) is at index 0
    first = path.elementAt(0)
    assert first.x == 0 and first.y == 0

    # Last element coordinates should match last control point
    last = path.elementAt(path.elementCount() - 1)
    assert int(last.x) == 20 and int(last.y) == 10 