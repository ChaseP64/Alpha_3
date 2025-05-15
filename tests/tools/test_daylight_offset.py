import math

from digcalc_project.src.tools.daylight_offset_tool import offset_polygon


def test_offset_square():
    """Offsetting a square by 1 ft should expand side length from 10→12 (≈)."""
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    out = offset_polygon(square, 1.0)

    # Shapely may densify the buffer, so expect at least 4 vertices
    assert len(out) >= 4

    xs = [p[0] for p in out]
    ys = [p[1] for p in out]
    assert math.isclose(max(xs) - min(xs), 12.0, abs_tol=0.1)
    assert math.isclose(max(ys) - min(ys), 12.0, abs_tol=0.1)
