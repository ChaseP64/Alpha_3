import math
from digcalc_project.src.tools.daylight_offset_tool import offset_polygon


def test_square_offset():
    """Offsetting a 10×10 square outward by 2 ft → expect 14×14 bounding box."""
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    out = offset_polygon(sq, 2)  # 2 ft outward

    xs = [p[0] for p in out]
    ys = [p[1] for p in out]

    assert math.isclose(max(xs) - min(xs), 14, abs_tol=0.1)
    assert math.isclose(max(ys) - min(ys), 14, abs_tol=0.1) 